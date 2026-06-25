#!/usr/bin/env python3
"""Local web UI for requesting and previewing NC policy documents."""

from __future__ import annotations

import argparse
import base64
import binascii
import difflib
import hmac
import hashlib
import html
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import threading
import tempfile
import time
import unicodedata
import uuid
import zipfile
from argparse import Namespace
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from timezone_utils import configure_local_timezone
except ImportError:  # pragma: no cover - package import fallback.
    from .timezone_utils import configure_local_timezone

APP_TIMEZONE = configure_local_timezone()

try:
    from runtime_paths import (
        POLICY_GRAPH_DB_PATH,
        REFERENCE_DB_PATH,
        REPORTS_ROOT as RUNTIME_REPORTS_ROOT,
        REQUIREMENTS_DB_PATH,
    )
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import (
        POLICY_GRAPH_DB_PATH,
        REFERENCE_DB_PATH,
        REPORTS_ROOT as RUNTIME_REPORTS_ROOT,
        REQUIREMENTS_DB_PATH,
    )

from chapter_agents import build_agent_guideline, chapter_stages, is_recoverable_llm_generation_error
from artifact_drift import evaluate_policy_artifact_drift
from analysis_policy_alignment import build_analysis_policy_alignment_report
from channel_pi_status import (
    build_channel_pi_status_report,
    load_channel_pi_status_report,
    save_channel_pi_status_report,
)
from llm_client import LLMClient, LLM_LOG_PATH, llm_preflight_enabled
from dev_qa_agent import (
    dev_qa_action_check_instructions,
    dev_qa_action_check_prompt,
    dev_qa_action_check_schema,
    dev_qa_review_instructions,
    dev_qa_review_prompt,
    dev_qa_review_schema,
    extract_dev_qa_signals,
    normalize_dev_qa_action_check,
    normalize_dev_qa_review,
    save_dev_qa_review_report,
)
from health_check_evaluator import (
    build_health_remediation_plan,
    evaluate_health_check,
    load_health_check_rubric,
    save_health_check_report,
)
from llm_routing import client_for_revision, client_for_route, client_for_stage_inspector, routing_plan
from pi_agent import (
    PI_GATEKEEPER_DIMENSIONS,
    PI_INSPECTION_METHODS,
    enrich_pi_check_report,
    evaluate_pi_document_quality,
    load_pi_agent_knowledge,
    normalize_pi_check_document,
    pi_check_analysis_text,
    pi_checklist_with_methods,
)
from bpmn_renderer import write_bpmn_artifacts
from policy_agent import (
    DEFAULT_OUTPUT_DIR,
    PROJECT_ROOT,
    choose_template,
    create_policy,
    make_business_code,
    make_topic_slug,
    normalize_sentence_breaks,
    template_file_label,
)
from policy_versioning import next_policy_version, policy_version_sort_key
from policy_requirements import load_scoped_requirements_for_topic
from policy_graph import build_policy_graph, document_node_source_id
from policy_inspector import (
    DEFAULT_INSPECTOR_MIN_SCORE,
    REPORTS_DIR,
    inspect_policy_document,
    load_sample_htmls,
    save_inspection_report,
)
from renderer import build_usecase_static_diagram_from_data, render_policy_html
from schema import ensure_policy_spec_base_keys
from validator import validate_policy_spec, validate_stage_critical
from topic_scope_definitions import build_topic_scope_definitions, topic_scope_definition
from topic_knowledge_builder import (
    DEFAULT_TOPIC_KNOWLEDGE_DIR,
    TOPIC_KNOWLEDGE_VERSION,
    build_and_save_topic_knowledge_pack,
    save_topic_knowledge_pack,
    split_direction_milestone,
    topic_knowledge_path,
    update_topic_direction_display_milestone,
)


def env_positive_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def env_nonnegative_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().casefold()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on", "enabled"}


def resolve_runtime_file_path(env_key: str, default: Path) -> Path:
    raw = str(os.environ.get(env_key, "") or "").strip()
    candidate = Path(raw).expanduser() if raw else default
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve(strict=False)


WEB_ROOT = PROJECT_ROOT / "web"
OUTPUT_ROOT = DEFAULT_OUTPUT_DIR
LOCK_DIR = OUTPUT_ROOT / ".locks"
JOB_LOCK_TTL_SECONDS = 30 * 60
DOCUMENT_LOCK_TTL_SECONDS = 30 * 60
MAX_ACTIVE_POLICY_JOBS = env_positive_int("NC_MAX_ACTIVE_POLICY_JOBS", 2)
CLIENT_HEARTBEAT_TIMEOUT_SECONDS = int(os.environ.get("NC_CLIENT_HEARTBEAT_TIMEOUT_SECONDS", "180") or "180")
CLIENT_HEARTBEAT_CHECK_SECONDS = int(os.environ.get("NC_CLIENT_HEARTBEAT_CHECK_SECONDS", "15") or "15")
HTML_UPLOAD_MAX_BYTES = env_positive_int("NC_HTML_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
JSON_UPLOAD_MAX_BYTES = env_positive_int("NC_JSON_UPLOAD_MAX_BYTES", 10 * 1024 * 1024)
INTERMEDIATE_CLEANUP_ENABLED = env_flag("NC_INTERMEDIATE_CLEANUP_ENABLED", True)
INTERMEDIATE_CLEANUP_RETENTION_HOURS = env_nonnegative_int("NC_INTERMEDIATE_CLEANUP_RETENTION_HOURS", 24)
RUNTIME_BATCH_CLEANUP_RETENTION_HOURS = env_nonnegative_int("NC_RUNTIME_BATCH_CLEANUP_RETENTION_HOURS", 0)
RUNTIME_BATCH_DIR_PREFIXES = (
    "mock_",
    "llm_graph_test_",
    "policy_graph_test_",
    "batch_",
    "tmp_",
)
USER_EVENT_LOG_PATH = LLM_LOG_PATH.parent / "user_events.jsonl"
USER_EVENT_MAX_STRING_CHARS = env_positive_int("NC_USER_EVENT_MAX_STRING_CHARS", 1200, minimum=120)
USER_EVENT_MAX_PAYLOAD_BYTES = env_positive_int("NC_USER_EVENT_MAX_PAYLOAD_BYTES", 20 * 1024, minimum=1024)
POLICY_HTML_FILENAME_RE = re.compile(
    r"^NC_(?P<topic>.+)_정책서_(?P<template_label>간소화|Full)_(?P<version>v\d+\.\d+(?:_보완본)?)\.html$"
)
POLICY_ARTIFACT_ID_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:ACT|US|ST|PR|PRC|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])"
)
HTML_RUNTIME_SOURCE_SPEC_REASONS = {
    "manual_edit_new_version",
    "manual_edit_overwrite",
    "html_upload",
    "diagram_edit",
    "agent_revision_current_version",
    "agent_revision_new_version",
}
HTML_RUNTIME_SOURCE_HISTORY_PHRASES = (
    "사용자 직접 편집",
    "HTML 파일 업로드",
    "Agent 수정",
    "수정 Agent",
)
DEV_FORMAT_WARNING_SECTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("brokenRefs", "Broken cross-refs", "blocking"),
    ("orphans", "Orphan entities", "review"),
    ("nnMismatch", "N:N 양방향 불일치", "blocking"),
    ("invalidIdFormat", "ID 형식 위반", "blocking"),
    ("missingPolicies", "누락 의심 정책", "blocking"),
    ("silentFailure", "Silent failure 의심", "blocking"),
    ("unknownIdPrefix", "Unknown ID prefix", "review"),
)
BPMN_IO_HISTORY_CHANGE = "bpmn.io viewer 산출물 생성 및 문서 재렌더링"
ACCESS_ENTRY_CODE = os.environ.get("NC_ENTRY_CODE", "1111120").strip() or "1111120"
ACCESS_COOKIE_NAME = "ncstudio_access"
ACCESS_COOKIE_VALUE = hashlib.sha256(f"ncstudio|{ACCESS_ENTRY_CODE}|access-v2-session".encode("utf-8")).hexdigest()
LLM_ACCESS_KEY = os.environ.get("NC_LLM_ACCESS_KEY", "11111201111120").strip() or "11111201111120"
LLM_ACCESS_TOKEN_VALUE = hashlib.sha256(f"ncstudio|{LLM_ACCESS_KEY}|llm-v2-session".encode("utf-8")).hexdigest()
SITE_SETTINGS_LOCK = threading.Lock()
TOPIC_KNOWLEDGE_REFRESH_LOCK = threading.Lock()
TOPIC_KNOWLEDGE_REFRESHING: set[str] = set()
POLICY_GRAPH_BOOTSTRAP_ENABLED = env_flag("NC_POLICY_GRAPH_BOOTSTRAP_ENABLED", True)
POLICY_GRAPH_BOOTSTRAP_ASYNC = env_flag("NC_POLICY_GRAPH_BOOTSTRAP_ASYNC", True)
POLICY_GRAPH_BOOTSTRAP_FORCE = env_flag("NC_POLICY_GRAPH_BOOTSTRAP_FORCE", False)
POLICY_GRAPH_INCREMENTAL_ENABLED = env_flag("NC_POLICY_GRAPH_INCREMENTAL_ENABLED", True)
POLICY_GRAPH_BOOTSTRAP_MANIFEST_KEY = "bootstrap_spec_manifest_v1"
POLICY_GRAPH_BOOTSTRAP_SOURCE_KEY = "bootstrap_source_signature_v1"
POLICY_GRAPH_BOOTSTRAP_MODE_KEY = "bootstrap_mode"
POLICY_GRAPH_BOOTSTRAP_MANIFEST_VERSION = "1"
POLICY_GRAPH_BOOTSTRAP_LOCK = threading.Lock()
POLICY_GRAPH_BOOTSTRAP_STATUS: Dict[str, Any] = {
    "enabled": POLICY_GRAPH_BOOTSTRAP_ENABLED,
    "incrementalEnabled": POLICY_GRAPH_INCREMENTAL_ENABLED,
    "status": "not_started",
    "reason": "",
    "mode": "",
    "startedAt": "",
    "finishedAt": "",
    "elapsedMs": 0,
    "specFileCount": 0,
    "processedSpecFileCount": 0,
    "documentCount": 0,
    "changedSpecFileCount": 0,
    "deletedSpecFileCount": 0,
    "errorCount": 0,
    "errors": [],
}


def fallback_user_db_path() -> Path:
    return Path(tempfile.gettempdir()) / "ncstudio" / "auth" / "users.sqlite3"


def resolve_site_settings_path() -> Path:
    raw = os.environ.get("NC_SITE_SETTINGS_PATH", "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        return candidate.resolve(strict=False)

    if os.environ.get("NC_REPORTS_DIR", "").strip():
        return (RUNTIME_REPORTS_ROOT / "site_settings.json").resolve(strict=False)

    persistent_root_raw = os.environ.get("NC_PERSISTENT_ROOT", "").strip()
    if persistent_root_raw:
        return (Path(persistent_root_raw).expanduser() / "reports" / "site_settings.json").resolve(strict=False)

    persistent_root = Path("/var/data/ncstudio")
    if persistent_root.exists():
        return (persistent_root / "reports" / "site_settings.json").resolve(strict=False)

    return (RUNTIME_REPORTS_ROOT / "site_settings.json").resolve(strict=False)


SITE_SETTINGS_PATH = resolve_site_settings_path()


def resolve_user_db_path() -> Path:
    raw = os.environ.get("NC_USER_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()

    persistent_root = Path(os.environ.get("NC_PERSISTENT_ROOT", "/var/data/ncstudio")).expanduser()
    if persistent_root.exists():
        return persistent_root / "reports" / "auth" / "users.sqlite3"

    candidate = RUNTIME_REPORTS_ROOT / "auth" / "users.sqlite3"
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return fallback_user_db_path()
    except OSError:
        parent = candidate.parent
        probe = parent if parent.exists() else parent.parent
        if not os.access(probe, os.W_OK):
            return fallback_user_db_path()
    return candidate


USER_DB_PATH = resolve_user_db_path()
REVISION_CANDIDATE_DIR = REPORTS_DIR.parent / "cache" / "revision_candidates"
POLICY_COMMENTS_DIR = RUNTIME_REPORTS_ROOT / "comments"
POLICY_COMMENTS_LOCK = threading.Lock()
POLICY_COMMENT_STATUSES = {"Open", "반영됨", "보류"}
POLICY_COMMENT_MAX_ITEMS = env_positive_int("NC_POLICY_COMMENT_MAX_ITEMS", 500, minimum=10)
POLICY_COMMENT_MAX_TEXT_CHARS = env_positive_int("NC_POLICY_COMMENT_MAX_TEXT_CHARS", 2000, minimum=200)
POLICY_COMMENT_MAX_REPLY_ITEMS = env_positive_int("NC_POLICY_COMMENT_MAX_REPLY_ITEMS", 200, minimum=10)
USER_APPROVAL_REQUIRED = env_flag("NC_REQUIRE_USER_APPROVAL", False)
USER_MANAGEMENT_EMPLOYEE_IDS = {
    item.strip().casefold()
    for item in os.environ.get("NC_USER_MANAGEMENT_EMPLOYEE_IDS", "1111120").split(",")
    if item.strip()
}


def normalize_site_writer_mode(mode: Any) -> str:
    raw_mode = str(mode or "mock").strip().casefold()
    if raw_mode in {"llm", "real", "use", "used", "enabled", "on", "true", "1", "yes", "y", "사용"}:
        return "llm"
    if raw_mode in {
        "mock",
        "test",
        "mock-test",
        "mock_test",
        "unused",
        "disabled",
        "disable",
        "off",
        "false",
        "0",
        "no",
        "n",
        "api-free",
        "미사용",
        "",
    }:
        return "mock"
    raise ValueError("LLM 사용 여부는 사용 또는 미사용 중 하나여야 합니다.")


def default_site_settings() -> Dict[str, Any]:
    return {
        "version": 1,
        "writerMode": "mock",
        "updatedAt": "",
        "updatedBy": "",
        "updatedByEmployeeIdHash": "",
    }


def site_settings_read_paths() -> List[Path]:
    paths = [SITE_SETTINGS_PATH]
    legacy_path = (RUNTIME_REPORTS_ROOT / "site_settings.json").resolve(strict=False)
    if legacy_path != SITE_SETTINGS_PATH:
        paths.append(legacy_path)
    return paths


def _parse_site_settings_payload(data: Any) -> Dict[str, Any]:
    settings = default_site_settings()
    if not isinstance(data, Mapping):
        return settings
    try:
        settings["writerMode"] = normalize_site_writer_mode(data.get("writerMode", "mock"))
    except ValueError:
        settings["writerMode"] = "mock"
    for key in ("updatedAt", "updatedBy", "updatedByEmployeeIdHash"):
        settings[key] = str(data.get(key, "") or "")
    return settings


def _write_site_settings_unlocked(settings: Mapping[str, Any]) -> None:
    SITE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = SITE_SETTINGS_PATH.with_name(f"{SITE_SETTINGS_PATH.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(dict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, SITE_SETTINGS_PATH)


def _load_site_settings_unlocked() -> Dict[str, Any]:
    for path in site_settings_read_paths():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        settings = _parse_site_settings_payload(data)
        if path != SITE_SETTINGS_PATH and not SITE_SETTINGS_PATH.exists():
            try:
                _write_site_settings_unlocked(settings)
            except Exception:
                pass
        return settings
    return default_site_settings()


def load_site_settings() -> Dict[str, Any]:
    with SITE_SETTINGS_LOCK:
        return _load_site_settings_unlocked()


def can_update_site_writer_mode(user: Mapping[str, Any] | None) -> bool:
    return can_manage_users(user)


def public_site_settings_status(user: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    settings = load_site_settings()
    return {
        "writerMode": settings.get("writerMode", "mock"),
        "updatedAt": settings.get("updatedAt", ""),
        "persisted": SITE_SETTINGS_PATH.exists(),
        "canUpdate": can_update_site_writer_mode(user),
    }


def site_llm_mode_enabled() -> bool:
    return load_site_settings().get("writerMode") == "llm"


def save_site_writer_mode(mode: Any, user: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    normalized_mode = normalize_site_writer_mode(mode)
    user = user if isinstance(user, Mapping) else {}
    settings = {
        **default_site_settings(),
        "writerMode": normalized_mode,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "updatedBy": str(user.get("name", "") or ""),
        "updatedByEmployeeIdHash": masked_employee_id(user.get("employeeId", "")),
    }
    with SITE_SETTINGS_LOCK:
        _write_site_settings_unlocked(settings)
    return settings
USER_ROLE_USER = "user"
USER_ROLE_VIEWER = "viewer"
USER_ROLE_ALIASES = {
    USER_ROLE_USER: USER_ROLE_USER,
    "normal": USER_ROLE_USER,
    "editor": USER_ROLE_USER,
    "member": USER_ROLE_USER,
    "일반": USER_ROLE_USER,
    "편집": USER_ROLE_USER,
    "편집자": USER_ROLE_USER,
    USER_ROLE_VIEWER: USER_ROLE_VIEWER,
    "view": USER_ROLE_VIEWER,
    "read": USER_ROLE_VIEWER,
    "readonly": USER_ROLE_VIEWER,
    "read_only": USER_ROLE_VIEWER,
    "조회": USER_ROLE_VIEWER,
    "조회자": USER_ROLE_VIEWER,
}
USER_WRITE_ROLES = {USER_ROLE_USER}
USER_DEFAULT_NEW_ROLE = USER_ROLE_VIEWER
USER_PASSWORD_ITERATIONS = env_positive_int("NC_USER_PASSWORD_ITERATIONS", 210000, minimum=100000)
SESSION_SECRET = (
    os.environ.get("NC_SESSION_SECRET", "").strip()
    or hashlib.sha256(f"ncstudio-session|{ACCESS_ENTRY_CODE}|{LLM_ACCESS_KEY}".encode("utf-8")).hexdigest()
)
NOINDEX_HEADER_VALUE = "noindex, nofollow, noarchive, nosnippet, noimageindex"
CRAWLER_ROBOTS_TXT = """User-agent: *
Disallow: /
Noindex: /

User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: OAI-SearchBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Claude-User
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: CCBot
Disallow: /
"""


def session_cookie_header(name: str, value: str) -> str:
    return f"{name}={value}; Path=/; HttpOnly; SameSite=Lax"


def clear_cookie_header(name: str) -> str:
    return f"{name}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"


AUTH_LOCK = threading.Lock()
EMPLOYEE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{2,40}$")


def normalize_employee_id(value: Any) -> str:
    employee_id = str(value or "").strip()
    if not employee_id:
        raise ValueError("사번을 입력해 주세요.")
    if not EMPLOYEE_ID_PATTERN.match(employee_id):
        raise ValueError("사번은 영문, 숫자, '.', '_', '-' 조합 2~40자로 입력해 주세요.")
    return employee_id


def normalize_user_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())
    if not name:
        raise ValueError("이름을 입력해 주세요.")
    if len(name) > 40:
        raise ValueError("이름은 40자 이하로 입력해 주세요.")
    return name


def validate_password(value: Any) -> str:
    password = str(value or "")
    if len(password) < 6:
        raise ValueError("비밀번호는 6자 이상으로 입력해 주세요.")
    if len(password) > 128:
        raise ValueError("비밀번호는 128자 이하로 입력해 주세요.")
    return password


def normalize_user_role(value: Any) -> str:
    raw = str(value or USER_ROLE_USER).strip().casefold()
    return USER_ROLE_ALIASES.get(raw, USER_ROLE_USER)


def user_db_template() -> Dict[str, Any]:
    return {"version": 1, "users": []}


def user_db_uses_sqlite() -> bool:
    return USER_DB_PATH.suffix.lower() in {".sqlite", ".sqlite3", ".db"}


def legacy_user_json_path() -> Path:
    return USER_DB_PATH.with_name("users.json")


def sqlite_user_to_record(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "employeeId": str(row["employee_id"] or ""),
        "name": str(row["name"] or ""),
        "salt": str(row["salt"] or ""),
        "iterations": int(row["iterations"] or USER_PASSWORD_ITERATIONS),
        "passwordHash": str(row["password_hash"] or ""),
        "approved": bool(row["approved"]),
        "role": normalize_user_role(row["role"]),
        "active": bool(row["active"]),
        "createdAt": str(row["created_at"] or ""),
        "updatedAt": str(row["updated_at"] or ""),
        "lastLoginAt": str(row["last_login_at"] or ""),
    }


def open_user_sqlite_db() -> sqlite3.Connection:
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            employee_id TEXT PRIMARY KEY COLLATE NOCASE,
            name TEXT NOT NULL,
            salt TEXT NOT NULL,
            iterations INTEGER NOT NULL,
            password_hash TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 1,
            role TEXT NOT NULL DEFAULT 'viewer',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "last_login_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT NOT NULL DEFAULT ''")
        conn.commit()
    return conn


def insert_sqlite_user(conn: sqlite3.Connection, user: Mapping[str, Any], *, replace: bool = False) -> None:
    statement = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"""
        {statement} INTO users (
            employee_id,
            name,
            salt,
            iterations,
            password_hash,
            approved,
            role,
            active,
            created_at,
            updated_at,
            last_login_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(user.get("employeeId", "") or "").strip(),
            str(user.get("name", "") or "").strip(),
            str(user.get("salt", "") or "").strip(),
            int(user.get("iterations", USER_PASSWORD_ITERATIONS) or USER_PASSWORD_ITERATIONS),
            str(user.get("passwordHash", "") or "").strip(),
            1 if bool(user.get("approved", True)) else 0,
            normalize_user_role(user.get("role", USER_ROLE_USER)),
            1 if bool(user.get("active", True)) else 0,
            str(user.get("createdAt", "") or "").strip(),
            str(user.get("updatedAt", "") or "").strip(),
            str(user.get("lastLoginAt", "") or "").strip(),
        ),
    )


def migrate_legacy_user_json_if_needed(conn: sqlite3.Connection) -> None:
    legacy_path = legacy_user_json_path()
    if not legacy_path.exists():
        return
    existing_count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    if existing_count > 0:
        return
    try:
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(users, list):
        return
    for user in users:
        if not isinstance(user, Mapping):
            continue
        if not str(user.get("employeeId", "") or "").strip():
            continue
        insert_sqlite_user(conn, user)
    conn.commit()


def load_user_db() -> Dict[str, Any]:
    if user_db_uses_sqlite():
        try:
            with open_user_sqlite_db() as conn:
                migrate_legacy_user_json_if_needed(conn)
                rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC, employee_id ASC").fetchall()
        except sqlite3.Error as exc:
            raise ValueError("사용자 계정 DB를 읽을 수 없습니다.") from exc
        return {"version": 1, "users": [sqlite_user_to_record(row) for row in rows]}
    if not USER_DB_PATH.exists():
        return user_db_template()
    try:
        payload = json.loads(USER_DB_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("사용자 계정 DB를 읽을 수 없습니다.") from exc
    if not isinstance(payload, dict):
        return user_db_template()
    users = payload.get("users")
    if not isinstance(users, list):
        payload["users"] = []
    payload.setdefault("version", 1)
    return payload


def save_user_db(payload: Dict[str, Any]) -> None:
    if user_db_uses_sqlite():
        users = payload.get("users") if isinstance(payload, dict) else []
        if not isinstance(users, list):
            users = []
        try:
            with open_user_sqlite_db() as conn:
                conn.execute("DELETE FROM users")
                for user in users:
                    if isinstance(user, Mapping) and str(user.get("employeeId", "") or "").strip():
                        insert_sqlite_user(conn, user, replace=True)
                conn.commit()
        except sqlite3.Error as exc:
            raise ValueError("사용자 계정 DB를 저장할 수 없습니다.") from exc
        return
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = USER_DB_PATH.with_suffix(USER_DB_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(USER_DB_PATH)


def find_user_record(payload: Mapping[str, Any], employee_id: str) -> Optional[Dict[str, Any]]:
    target = employee_id.casefold()
    for user in payload.get("users", []) if isinstance(payload.get("users"), list) else []:
        if not isinstance(user, dict):
            continue
        if str(user.get("employeeId", "")).strip().casefold() == target:
            return user
    return None


def hash_user_password(password: str, *, salt: str | None = None, iterations: int = USER_PASSWORD_ITERATIONS) -> Dict[str, Any]:
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
    return {
        "salt": salt_hex,
        "iterations": iterations,
        "passwordHash": base64.b64encode(digest).decode("ascii"),
    }


def verify_user_password(password: str, user: Mapping[str, Any]) -> bool:
    salt = str(user.get("salt", "") or "").strip()
    stored = str(user.get("passwordHash", "") or "").strip()
    try:
        iterations = int(user.get("iterations", USER_PASSWORD_ITERATIONS))
    except (TypeError, ValueError):
        iterations = USER_PASSWORD_ITERATIONS
    if not salt or not stored:
        return False
    candidate = hash_user_password(password, salt=salt, iterations=iterations)["passwordHash"]
    return hmac.compare_digest(candidate, stored)


def public_user(user: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "employeeId": str(user.get("employeeId", "") or ""),
        "name": str(user.get("name", "") or ""),
        "approved": bool(user.get("approved", True)),
        "role": normalize_user_role(user.get("role", USER_ROLE_USER)),
    }


def can_manage_users(user: Mapping[str, Any] | None) -> bool:
    if not user:
        return False
    employee_id = str(user.get("employeeId", "") or "").strip().casefold()
    return bool(employee_id and employee_id in USER_MANAGEMENT_EMPLOYEE_IDS)


def can_write_documents(user: Mapping[str, Any] | None) -> bool:
    if not user:
        return False
    if can_manage_users(user):
        return True
    return normalize_user_role(user.get("role", USER_ROLE_USER)) in USER_WRITE_ROLES


def public_user_management_record(user: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "employeeId": str(user.get("employeeId", "") or ""),
        "name": str(user.get("name", "") or ""),
        "approved": bool(user.get("approved", True)),
        "active": bool(user.get("active", True)),
        "role": normalize_user_role(user.get("role", USER_ROLE_USER)),
        "createdAt": str(user.get("createdAt", "") or ""),
        "updatedAt": str(user.get("updatedAt", "") or ""),
        "lastLoginAt": str(user.get("lastLoginAt", "") or ""),
    }


def build_user_management_dashboard() -> Dict[str, Any]:
    with AUTH_LOCK:
        db = load_user_db()
    raw_users = db.get("users") if isinstance(db.get("users"), list) else []
    users = [
        public_user_management_record(user)
        for user in raw_users
        if isinstance(user, Mapping) and str(user.get("employeeId", "") or "").strip()
    ]
    users.sort(key=lambda user: (user.get("createdAt") or "", user.get("employeeId") or ""), reverse=True)
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "totalUsers": len(users),
            "approvedUsers": sum(1 for user in users if user.get("approved") and user.get("active")),
            "pendingUsers": sum(1 for user in users if not user.get("approved")),
            "inactiveUsers": sum(1 for user in users if not user.get("active")),
            "normalUsers": sum(1 for user in users if normalize_user_role(user.get("role")) == USER_ROLE_USER and user.get("active")),
            "viewerUsers": sum(1 for user in users if normalize_user_role(user.get("role")) == USER_ROLE_VIEWER and user.get("active")),
        },
        "items": users,
        "approvalRequired": USER_APPROVAL_REQUIRED,
    }


def withdraw_user_account(employee_id: Any, actor: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    target_employee_id = normalize_employee_id(employee_id)
    actor_employee_id = str((actor or {}).get("employeeId", "") or "").strip().casefold()
    if target_employee_id.casefold() == actor_employee_id:
        raise PermissionError("본인 계정은 사용자 관리에서 탈퇴 처리할 수 없습니다.")
    if target_employee_id.casefold() in USER_MANAGEMENT_EMPLOYEE_IDS:
        raise PermissionError("관리자 계정은 탈퇴 처리할 수 없습니다.")

    now = datetime.now().isoformat(timespec="seconds")
    with AUTH_LOCK:
        db = load_user_db()
        user = find_user_record(db, target_employee_id)
        if not user:
            raise ValueError("탈퇴 처리할 사용자를 찾을 수 없습니다.")
        user["active"] = False
        user["approved"] = False
        user["updatedAt"] = now
        save_user_db(db)
        return public_user_management_record(user)


def update_user_account_role(employee_id: Any, role: Any, actor: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    target_employee_id = normalize_employee_id(employee_id)
    next_role = normalize_user_role(role)
    actor_employee_id = str((actor or {}).get("employeeId", "") or "").strip().casefold()
    if target_employee_id.casefold() == actor_employee_id:
        raise PermissionError("본인 권한은 사용자 관리에서 변경할 수 없습니다.")
    if target_employee_id.casefold() in USER_MANAGEMENT_EMPLOYEE_IDS:
        raise PermissionError("관리자 계정 권한은 변경할 수 없습니다.")

    now = datetime.now().isoformat(timespec="seconds")
    with AUTH_LOCK:
        db = load_user_db()
        user = find_user_record(db, target_employee_id)
        if not user:
            raise ValueError("권한을 변경할 사용자를 찾을 수 없습니다.")
        if not bool(user.get("active", True)):
            raise ValueError("비활성 계정은 권한을 변경할 수 없습니다.")
        user["role"] = next_role
        user["updatedAt"] = now
        save_user_db(db)
        return public_user_management_record(user)


def masked_employee_id(employee_id: Any) -> str:
    normalized = str(employee_id or "").strip().casefold()
    if not normalized:
        return ""
    return hashlib.sha256(f"employee|{normalized}".encode("utf-8")).hexdigest()[:12]


def create_user_account(name: Any, employee_id: Any, password: Any, entry_code: Any, password_confirm: Any = None) -> Dict[str, Any]:
    normalized_name = normalize_user_name(name)
    normalized_employee_id = normalize_employee_id(employee_id)
    normalized_password = validate_password(password)
    if password_confirm is None or str(password_confirm or "") == "":
        raise ValueError("비밀번호 확인을 입력해 주세요.")
    if normalized_password != str(password_confirm or ""):
        raise ValueError("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
    code = str(entry_code or "").strip()
    if not code:
        raise ValueError("입장 코드를 입력해 주세요.")
    if code != ACCESS_ENTRY_CODE:
        raise PermissionError("입장 코드가 올바르지 않아 계정을 만들 수 없습니다.")

    now = datetime.now().isoformat(timespec="seconds")
    with AUTH_LOCK:
        db = load_user_db()
        if find_user_record(db, normalized_employee_id):
            raise ValueError("이미 가입된 사번입니다. 로그인해 주세요.")
        password_payload = hash_user_password(normalized_password)
        user = {
            "employeeId": normalized_employee_id,
            "name": normalized_name,
            **password_payload,
            "approved": not USER_APPROVAL_REQUIRED,
            "role": USER_DEFAULT_NEW_ROLE,
            "active": True,
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now if not USER_APPROVAL_REQUIRED else "",
        }
        db.setdefault("users", []).append(user)
        save_user_db(db)
    return public_user(user)


def authenticate_user(employee_id: Any, password: Any) -> Dict[str, Any]:
    normalized_employee_id = normalize_employee_id(employee_id)
    normalized_password = validate_password(password)
    with AUTH_LOCK:
        db = load_user_db()
        user = find_user_record(db, normalized_employee_id)
        if not user or not verify_user_password(normalized_password, user):
            raise PermissionError("사번 또는 비밀번호를 확인해 주세요. 회원 가입 후 이용 가능합니다.")
        if not bool(user.get("active", True)):
            raise PermissionError("비활성화된 계정입니다. 관리자에게 문의해 주세요.")
        if not bool(user.get("approved", True)):
            raise PermissionError("관리자 승인 후 이용할 수 있습니다.")
        user["lastLoginAt"] = datetime.now().isoformat(timespec="seconds")
        save_user_db(db)
        return public_user(user)


def reset_user_password(employee_id: Any, password: Any, password_confirm: Any, entry_code: Any) -> Dict[str, Any]:
    normalized_employee_id = normalize_employee_id(employee_id)
    normalized_password = validate_password(password)
    if password_confirm is None or str(password_confirm or "") == "":
        raise ValueError("비밀번호 확인을 입력해 주세요.")
    if normalized_password != str(password_confirm or ""):
        raise ValueError("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
    code = str(entry_code or "").strip()
    if not code:
        raise ValueError("입장 코드를 입력해 주세요.")
    if code != ACCESS_ENTRY_CODE:
        raise PermissionError("입장 코드가 올바르지 않아 비밀번호를 재설정할 수 없습니다.")

    now = datetime.now().isoformat(timespec="seconds")
    with AUTH_LOCK:
        db = load_user_db()
        user = find_user_record(db, normalized_employee_id)
        if not user:
            raise ValueError("가입된 사번이 없습니다. 회원 가입 후 이용해 주세요.")
        user.update(hash_user_password(normalized_password))
        user["updatedAt"] = now
        user["lastLoginAt"] = now
        save_user_db(db)

    if not bool(user.get("active", True)):
        raise PermissionError("비활성화된 계정입니다. 관리자에게 문의해 주세요.")
    if not bool(user.get("approved", True)):
        raise PermissionError("관리자 승인 후 이용할 수 있습니다.")
    return public_user(user)


def _base64_url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _base64_url_decode(payload: str) -> bytes:
    padded = payload + "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def create_user_session_token(user: Mapping[str, Any]) -> str:
    session_payload = {
        "employeeId": str(user.get("employeeId", "") or ""),
        "name": str(user.get("name", "") or ""),
        "issuedAt": int(time.time()),
    }
    body = _base64_url_encode(json.dumps(session_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def user_from_session_token(token: str) -> Optional[Dict[str, Any]]:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(SESSION_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_base64_url_decode(body).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    employee_id = str(payload.get("employeeId", "") or "").strip()
    if not employee_id:
        return None
    try:
        with AUTH_LOCK:
            db = load_user_db()
            user = find_user_record(db, employee_id)
    except ValueError:
        return None
    if not user or not bool(user.get("active", True)) or not bool(user.get("approved", True)):
        return None
    return public_user(user)


BLOCKED_CRAWLER_USER_AGENT_PARTS = tuple(
    part.casefold()
    for part in (
        "bot",
        "spider",
        "crawler",
        "slurp",
        "googlebot",
        "bingbot",
        "baiduspider",
        "yandexbot",
        "duckduckbot",
        "applebot",
        "facebookexternalhit",
        "meta-externalagent",
        "bytespider",
        "gptbot",
        "chatgpt-user",
        "oai-searchbot",
        "claudebot",
        "claude-user",
        "anthropic-ai",
        "perplexitybot",
        "ccbot",
        "cohere-ai",
        "diffbot",
        "omgilibot",
    )
)
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
JOBS_CONDITION = threading.Condition(JOBS_LOCK)
POLICY_JOB_SEMAPHORE = threading.BoundedSemaphore(MAX_ACTIVE_POLICY_JOBS)
JOB_WATCHDOG_STARTED = False
JOB_WATCHDOG_LOCK = threading.Lock()

DEFAULT_MODEL_PRICING_USD_PER_1M: Dict[str, Dict[str, float]] = {
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5-pro": {"input": 15.00, "cached_input": 15.00, "output": 120.00},
    "gpt-5.5-pro": {"input": 30.00, "cached_input": 30.00, "output": 180.00},
}
OPENAI_USAGE_BASE_URL = os.environ.get("OPENAI_USAGE_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_USAGE_LOOKBACK_DAYS = env_positive_int("OPENAI_USAGE_LOOKBACK_DAYS", 30, minimum=1)
OPENAI_USAGE_TIMEOUT_SECONDS = max(
    1,
    env_positive_int("OPENAI_USAGE_TIMEOUT_SECONDS", 5, minimum=1),
)


class JobCancelled(Exception):
    """Raised inside background workers when the user cancels a job."""


class RevisionInspectorGateError(Exception):
    """Raised when a revision candidate needs explicit user approval to save."""

    def __init__(
        self,
        message: str,
        *,
        old_path: Path,
        new_path: Path,
        revised_html: str,
        author: str,
        change_summary: str,
        score: Any,
        threshold: Any,
        save_mode: str = "new_version",
    ) -> None:
        super().__init__(message)
        self.old_path = old_path
        self.new_path = new_path
        self.revised_html = revised_html
        self.author = author
        self.change_summary = change_summary
        self.score = score
        self.threshold = threshold
        self.save_mode = save_mode


class JobConflict(Exception):
    """Raised when the same policy generation is already running."""

    def __init__(self, message: str, conflict: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.conflict = conflict or {}


CANCELABLE_JOB_STATUSES = {"queued", "running", "waiting_review", "review", "retry", "canceling"}
ACTIVE_LOCK_STATUSES = {"queued", "running", "waiting_review", "review", "retry", "canceling"}
TERMINAL_LOCK_STATUSES = {"completed", "failed", "aborted", "canceled", "cancelled", "error"}

REVISION_STAGE_MESSAGES = {
    "intent": {
        "start": "수정 요청을 먼저 읽고 있어요. 어떤 장을 고쳐야 하는지, 선택 영역만 바꾸면 되는지, 문서 전체 정합성까지 같이 봐야 하는지를 분리합니다.",
        "complete": "수정 의도 분석이 끝났습니다. 이제 수정 Agent가 건드릴 범위와 유지해야 할 기준을 잡고 실제 보완으로 넘어갑니다.",
    },
    "revise": {
        "start": "수정 Agent가 보완안을 적용합니다. 요청한 내용만 반영하되, 액터·유즈케이스·상태·프로세스·기능·정책 연결이 깨지지 않게 조심해서 고칩니다.",
        "complete": "수정안을 본문에 반영했습니다. 이제 Inspector가 양식과 연결성이 유지됐는지 다시 확인합니다.",
    },
    "inspect": {
        "start": "수정본 Inspector가 문서 전체를 다시 봅니다. 바뀐 부분뿐 아니라 변경 때문에 다른 장의 연결이 어긋나지 않았는지 확인합니다.",
        "retry": "Inspector가 보완점을 찾았습니다. 전체를 다시 쓰지 않고 지적된 문제를 중심으로 수정 Agent에게 다시 넘깁니다.",
        "complete": "수정본 검수를 통과했습니다. 이제 수정 전후 차이를 문서 히스토리에 남길 준비를 합니다.",
        "error": "수정본이 아직 기준을 넘지 못했습니다. 멈춘 지점의 점수와 보완 필요 항목을 확인해 이어서 조정할 수 있게 남겨둡니다.",
    },
    "history": {
        "start": "수정 전후 차이를 비교합니다. 사람이 나중에 버전 변경 이유를 이해할 수 있도록 문서 히스토리 문구를 정리합니다.",
        "complete": "문서 히스토리에 변경 내용을 반영했습니다. 이제 수정본을 저장합니다.",
    },
    "save": {
        "start": "수정본을 저장합니다. 수정 범위에 따라 현재 버전에 누적하거나 다음 버전 문서로 남깁니다.",
        "complete": "수정본 저장이 완료됐습니다. 문서 작업실에서 수정본을 열어 확인할 수 있습니다.",
    },
}


def revision_stage_message(stage_name: str, moment: str, fallback: str = "") -> str:
    stage = REVISION_STAGE_MESSAGES.get(str(stage_name or "").strip(), {})
    return stage.get(str(moment or "").strip()) or fallback


def revision_save_mode_from_payload(payload: Mapping[str, Any], selection: Optional[Mapping[str, Any]] = None) -> str:
    raw = str(payload.get("saveMode") or payload.get("revisionSaveMode") or "").strip().casefold()
    instruction = str(payload.get("instruction", "") or "")
    has_selection = bool(selection) and any(str(value or "").strip() for value in selection.values())
    if (
        has_selection
        and raw in {"current", "current_version", "overwrite", "same_version"}
        and not is_broad_revision_scope(instruction)
        and not is_qa_revision_scope(instruction)
    ):
        return "current_version"
    return "new_version"


def revision_save_stage_label(save_mode: str) -> str:
    return "현재 버전 반영" if save_mode == "current_version" else "새 버전 저장"


def revision_save_preview_title(save_mode: str) -> str:
    return "현재 버전 반영" if save_mode == "current_version" else "새 버전 저장"


def revision_save_completed_message(save_mode: str, *, forced: bool = False) -> str:
    if save_mode == "current_version":
        return "수정본이 사용자 확인 후 현재 버전에 반영되었습니다." if forced else "정책서 수정본이 현재 버전에 반영되었습니다."
    return "수정본이 사용자 확인 후 새 버전으로 저장되었습니다." if forced else "정책서 수정본이 새 버전으로 저장되었습니다."


STAGE_DEFINITIONS = [
    ("00", "learning", "주제 학습"),
    ("01", "overview", "Overview Agent"),
    ("02", "terms", "Terms Agent"),
    ("03", "actors", "Actors Agent"),
    ("04", "usecases", "Usecases Agent"),
    ("05", "usecase_diagram", "Usecase Diagram Agent"),
    ("06", "state", "State Agent"),
    ("07", "process", "Process Agent"),
    ("08", "functions", "Functions Agent"),
    ("09", "policies", "Policies Agent"),
    ("09_terms_refinement", "terms_refinement", "Terms Review Agent"),
    ("10", "final_check", "Final Check Agent"),
    ("11", "finalize", "최종 검증 및 저장"),
]

FULL_DETAIL_STAGE_DEFINITIONS = [
    ("09_process_detail", "process_detail", "Process Detail Agent"),
    ("09_function_detail", "function_detail", "Function Detail Agent"),
]

REVISION_STAGE_DEFINITIONS = [
    ("00", "intent", "수정 의도 분석"),
    ("01", "revise", "수정 Agent"),
    ("02", "inspect", "수정본 검수"),
    ("03", "history", "문서 히스토리 업데이트"),
    ("04", "save", "수정본 저장"),
]


def is_blocked_crawler_user_agent(user_agent: str | None) -> bool:
    normalized = str(user_agent or "").casefold()
    if not normalized:
        return False
    return any(part in normalized for part in BLOCKED_CRAWLER_USER_AGENT_PARTS)


def stage_definitions_for_template(template_type: str) -> List[tuple[str, str, str]]:
    if str(template_type or "").strip().casefold() != "full":
        return list(STAGE_DEFINITIONS)
    expanded: List[tuple[str, str, str]] = []
    for item in STAGE_DEFINITIONS:
        expanded.append(item)
        if item[1] == "policies":
            expanded.extend(FULL_DETAIL_STAGE_DEFINITIONS)
    return expanded


class PolicyWebHandler(BaseHTTPRequestHandler):
    server_version = "NCPolicyWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/robots.txt":
            self.send_text(CRAWLER_ROBOTS_TXT, content_type="text/plain; charset=utf-8")
            return

        if self.is_blocked_crawler_request():
            self.send_text("Crawling is not allowed.", status=403, content_type="text/plain; charset=utf-8")
            return

        if path == "/api/access/status":
            user = self.current_user()
            self.send_json({"ok": True, "authorized": bool(user), "user": user})
            return

        if path == "/api/access/llm-status":
            self.send_json({"ok": True, "authorized": False, "token": ""})
            return

        if path == "/api/site-settings":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "settings": public_site_settings_status(self.current_user())})
            return

        if path == "/api/policies":
            if not self.require_api_access():
                return
            self.send_json({"items": list_policy_files(), "drafts": list_resumable_drafts()})
            return

        if path == "/api/policies/comments":
            if not self.require_api_access():
                return
            self.handle_policy_comments_get(parsed)
            return

        if path == "/api/policies/diagram-data":
            if not self.require_api_access():
                return
            query = parse_qs(parsed.query)
            try:
                self.send_json({"ok": True, "diagram": policy_diagram_data_from_name(query.get("name", [""])[0])})
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
                self.send_json({"ok": False, "error": f"다이어그램 데이터를 불러오는 중 오류가 발생했습니다: {exc}"}, status=500)
            return

        if path == "/api/policies/health-check-rubric":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "rubric": load_health_check_rubric()})
            return

        if path == "/api/pi-check-rubric":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "rubric": pi_check_rubric_payload()})
            return

        if path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "llm": llm_health(),
                    "siteSettings": public_site_settings_status(),
                    "policyGraph": policy_graph_runtime_status(),
                }
            )
            return

        if path == "/api/dashboard":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "agents": build_agent_usage_dashboard()})
            return

        if path == "/api/channel-pi-status":
            if not self.require_channel_pi_status_access():
                return
            self.handle_channel_pi_status(force=False)
            return

        if path == "/api/topic-scopes":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "definitions": build_runtime_topic_scope_definitions()})
            return

        if path == "/api/requirements-summary":
            if not self.require_api_access():
                return
            query = parse_qs(parsed.query)
            topics = [str(value or "").strip() for value in query.get("topic", []) if str(value or "").strip()]
            try:
                self.send_json({"ok": True, **requirements_summary_for_topics(topics)})
            except Exception as exc:  # pragma: no cover - defensive UI boundary.
                self.send_json({"ok": False, "error": f"요구사항 건수 조회 중 오류가 발생했습니다: {exc}"}, status=500)
            return

        if path == "/api/requirements":
            if not self.require_api_access():
                return
            query = parse_qs(parsed.query)
            topic = str(query.get("topic", [""])[0] or "").strip()
            if not topic:
                self.send_json({"ok": False, "error": "요구사항을 조회할 주제를 선택해 주세요."}, status=400)
                return
            try:
                self.send_json({"ok": True, **requirements_payload_for_topic(topic)})
            except Exception as exc:  # pragma: no cover - defensive UI boundary.
                self.send_json({"ok": False, "error": f"요구사항 조회 중 오류가 발생했습니다: {exc}"}, status=500)
            return

        if path == "/api/admin/service-health":
            if not self.require_api_access():
                return
            self.send_json({"ok": True, "service": build_service_health_dashboard()})
            return

        if path == "/api/admin/users":
            if not self.require_api_access():
                return
            if not can_manage_users(self.current_user()):
                self.send_json({"ok": False, "error": "사용자 관리는 관리자만 확인할 수 있습니다."}, status=403)
                return
            self.send_json({"ok": True, "users": build_user_management_dashboard()})
            return

        if path.startswith("/api/jobs/"):
            if not self.require_api_access():
                return
            self.handle_job_status(path.removeprefix("/api/jobs/"))
            return

        if path.startswith("/output/"):
            if not self.is_authorized():
                self.send_error(403, "Forbidden")
                return
            self.serve_output_file(path.removeprefix("/output/"))
            return

        if path == "/":
            self.serve_static_file(WEB_ROOT / "index.html")
            return

        self.serve_static_file(WEB_ROOT / path.lstrip("/"))

    def do_POST(self) -> None:
        if self.is_blocked_crawler_request():
            self.send_text("Crawling is not allowed.", status=403, content_type="text/plain; charset=utf-8")
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/access/signup":
            self.handle_access_signup()
            return

        if parsed.path == "/api/access/login":
            self.handle_access_login()
            return

        if parsed.path == "/api/access/reset-password":
            self.handle_access_password_reset()
            return

        if parsed.path == "/api/access/logout":
            self.handle_access_logout()
            return

        if parsed.path == "/api/access/llm-login":
            self.handle_llm_access_login()
            return

        if parsed.path != "/api/health" and parsed.path.startswith("/api/") and not self.require_api_access():
            return

        if parsed.path == "/api/site-settings/writer-mode":
            self.handle_site_writer_mode_update()
            return

        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/cancel"):
            if not self.require_policy_write_access():
                return
            self.handle_job_cancel(parsed.path)
            return

        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/review"):
            if not self.require_policy_write_access():
                return
            self.handle_job_review(parsed.path)
            return

        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/heartbeat"):
            self.handle_job_heartbeat(parsed.path)
            return

        if parsed.path == "/api/usage-events":
            self.handle_usage_event()
            return

        if parsed.path == "/api/topic-scopes/update":
            if not self.require_policy_write_access():
                return
            self.handle_topic_scope_update()
            return

        if parsed.path == "/api/inspect":
            self.handle_inspect()
            return

        if parsed.path == "/api/policies/dev-qa-review":
            self.handle_dev_qa_review()
            return

        if parsed.path == "/api/policies/dev-qa-action-check":
            self.handle_dev_qa_action_check()
            return

        if parsed.path == "/api/policies/health-check":
            self.handle_health_check()
            return

        if parsed.path == "/api/policies/artifact-sync-repair":
            if not self.require_policy_write_access():
                return
            self.handle_artifact_sync_repair()
            return

        if parsed.path == "/api/policies/html-spec-sync":
            if not self.require_policy_write_access():
                return
            self.handle_html_spec_sync()
            return

        if parsed.path == "/api/policies/analysis-alignment":
            self.handle_analysis_alignment_check()
            return

        if parsed.path == "/api/channel-pi-status/diagnose":
            if not self.require_channel_pi_status_access():
                return
            self.handle_channel_pi_status(force=True)
            return

        if parsed.path == "/api/policies/health-check-export":
            self.handle_health_check_export()
            return

        if parsed.path == "/api/policies/dev-format-export":
            self.handle_dev_format_export()
            return

        if parsed.path == "/api/policies/diagram-edit":
            if not self.require_policy_write_access():
                return
            self.handle_diagram_edit()
            return

        if parsed.path == "/api/pi-check":
            self.handle_pi_check()
            return

        if parsed.path == "/api/pi-check-export":
            self.handle_pi_check_export()
            return

        if parsed.path == "/api/policies/edit":
            if not self.require_policy_write_access():
                return
            self.handle_manual_edit()
            return

        if parsed.path == "/api/reference-html/edit":
            if not self.require_policy_write_access():
                return
            self.handle_reference_html_edit()
            return

        if parsed.path == "/api/policies/upload":
            if not self.require_policy_write_access():
                return
            self.handle_policy_upload()
            return

        if parsed.path == "/api/policies/upload-json":
            if not self.require_policy_write_access():
                return
            self.handle_policy_json_upload()
            return

        if parsed.path == "/api/policies/full-from-simple":
            if not self.require_policy_write_access():
                return
            if not self.require_policy_admin_action_access("Full 버전 전환은 관리자만 실행할 수 있습니다."):
                return
            self.handle_full_from_simple()
            return

        if parsed.path == "/api/policies/revise":
            if not self.require_policy_write_access():
                return
            self.handle_revision_request()
            return

        if parsed.path == "/api/policies/status":
            if not self.require_policy_write_access():
                return
            self.handle_policy_status()
            return

        if parsed.path == "/api/policies/comments":
            self.handle_policy_comments_update()
            return

        if parsed.path == "/api/admin/locks/cleanup":
            if not self.require_policy_write_access():
                return
            self.handle_service_lock_cleanup()
            return

        if parsed.path == "/api/admin/users/withdraw":
            self.handle_user_withdrawal()
            return

        if parsed.path == "/api/admin/users/role":
            self.handle_user_role_update()
            return

        if parsed.path == "/api/admin/llm-preflight":
            self.handle_llm_preflight()
            return

        if parsed.path == "/api/live-feedback":
            self.handle_live_feedback()
            return

        if parsed.path != "/api/policies":
            self.send_error(404, "Not found")
            return

        try:
            if not self.require_policy_write_access():
                return
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            if policy_generation_admin_action_required(payload) and not self.require_policy_admin_action_access(
                policy_generation_admin_action_error(payload)
            ):
                return
            job = start_policy_job(payload)
            write_user_event(
                "policy_create_requested",
                event_payload_for_policy_request(payload, job=job, status="accepted"),
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "job": job}, status=202)
        except JobConflict as exc:
            write_user_event(
                "policy_create_conflict",
                {"error": str(exc), "conflict": exc.conflict},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "policy_create_failed",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="validation_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except PermissionError as exc:
            write_user_event(
                "policy_create_denied",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="permission_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "code": "admin_permission_required"}, status=403)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "policy_create_failed",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="server_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"정책서 생성 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_service_lock_cleanup(self) -> None:
        try:
            payload = self.read_json()
            result = cleanup_service_locks(payload)
            self.send_json({"ok": True, **result})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"작업 점유 기록 정리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_llm_preflight(self) -> None:
        try:
            self.send_json({"ok": False, "error": "LLM 연결 점검은 저장된 인증을 사용하지 않습니다. LLM 사용으로 전환할 때 인증키를 다시 입력해 주세요."}, status=403)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"LLM 연결 점검 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_live_feedback(self) -> None:
        try:
            payload = self.read_json()
            result = live_feedback_from_payload(payload)
            self.send_json({"ok": True, **result})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc), "fallback": True}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"Live feedback 생성 중 오류가 발생했습니다: {exc}", "fallback": True}, status=500)

    def handle_topic_scope_update(self) -> None:
        try:
            payload = self.read_json()
            topic = str(payload.get("topic", "")).strip()
            raw_lines = payload.get("lines", [])
            if not topic:
                raise ValueError("수정할 주제를 선택해 주세요.")
            if not isinstance(raw_lines, list):
                raise ValueError("작성 지향점은 줄 단위 목록으로 전달해 주세요.")
            lines = update_topic_direction_display_milestone(topic, raw_lines)
            cache_updated = update_cached_topic_direction(topic, lines)
            queue_topic_knowledge_refresh(topic, session_id=client_session_id_from_payload(payload))
            definition = runtime_topic_scope_definition(topic) or {}
            write_user_event(
                "topic_direction_updated",
                {"topic": topic, "lineCount": len(lines), "cacheUpdated": cache_updated, "refreshMode": "background"},
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json(
                {
                    "ok": True,
                    "topic": topic,
                    "lines": lines,
                    "definition": definition,
                    "knowledgeRefresh": "queued",
                }
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"작성 지향점 저장 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_full_from_simple(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            job = start_full_from_simple_job(payload)
            write_user_event(
                "policy_full_from_simple_requested",
                event_payload_for_policy_request(payload, job=job, status="accepted"),
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "job": job}, status=202)
        except JobConflict as exc:
            write_user_event(
                "policy_full_from_simple_conflict",
                {"error": str(exc), "conflict": exc.conflict},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "policy_full_from_simple_failed",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="validation_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except PermissionError as exc:
            write_user_event(
                "policy_full_from_simple_denied",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="permission_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "code": "admin_permission_required"}, status=403)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "policy_full_from_simple_failed",
                {"error": str(exc), **event_payload_for_policy_request(locals().get("payload", {}), status="server_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"Full 버전 작성 요청 중 오류가 발생했습니다: {exc}"}, status=500)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/policies":
            self.send_error(404, "Not found")
            return
        if not self.require_api_access():
            return
        if not self.require_policy_write_access():
            return

        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            deleted = delete_policy_from_payload(payload)
            user = self.current_user() or {}
            write_user_event(
                "policy_deleted",
                {
                    "name": payload.get("name"),
                    "draftResumeFrom": payload.get("draftResumeFrom"),
                    "deletedName": deleted.get("name"),
                    "deletedBy": user.get("name") or payload.get("author"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "deleted": deleted})
        except JobConflict as exc:
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "policy_delete_failed",
                {"name": locals().get("payload", {}).get("name"), "draftResumeFrom": locals().get("payload", {}).get("draftResumeFrom"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "policy_delete_failed",
                {"name": locals().get("payload", {}).get("name"), "draftResumeFrom": locals().get("payload", {}).get("draftResumeFrom"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"정책서 삭제 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_inspect(self) -> None:
        try:
            payload = self.read_json()
            name = str(payload.get("name", "")).strip()
            if not name:
                raise ValueError("검수할 정책서를 선택해 주세요.")
            base_client = llm_client_from_web_payload(payload)
            path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / name)
            if not path.exists() or not path.is_file():
                raise ValueError("검수할 정책서 파일을 찾을 수 없습니다.")
            parsed = parse_policy_filename(path.name)
            template_type = "full" if parsed["template_label"] == "Full" else "simple"
            template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
            report = inspect_policy_document(
                path.read_text(encoding="utf-8"),
                template_html=template_path.read_text(encoding="utf-8"),
                sample_htmls=load_sample_htmls(template_type),
                template_type=template_type,
                scope="full",
                topic=parsed["topic"],
                density_profile=load_policy_density_profile(path),
                llm_client=base_client,
                llm_required=True,
            )
            save_inspection_report(report, path.name, "web")
            self.send_json({"ok": True, "report": report.to_dict()})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"정책서 검수 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_dev_qa_review(self) -> None:
        try:
            payload = self.read_json()
            report = dev_qa_review_from_payload(payload)
            write_user_event(
                "document_qa_review_completed",
                {
                    "name": payload.get("name"),
                    "score": report.get("score"),
                    "status": report.get("status"),
                    "findingCount": len(report.get("findings", [])) if isinstance(report.get("findings"), list) else 0,
                    "actionItemCount": len(report.get("action_items", [])) if isinstance(report.get("action_items"), list) else 0,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report})
        except ValueError as exc:
            write_user_event(
                "document_qa_review_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "document_qa_review_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"개발/QA 검수 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_dev_qa_action_check(self) -> None:
        try:
            payload = self.read_json()
            report = dev_qa_action_check_from_payload(payload)
            write_user_event(
                "document_qa_action_check_completed",
                {
                    "name": payload.get("name"),
                    "checkedCount": len(payload.get("items", [])) if isinstance(payload.get("items"), list) else 0,
                    "resolvedCount": sum(1 for item in report.get("items", []) if isinstance(item, dict) and item.get("status") == "resolved")
                    if isinstance(report.get("items"), list)
                    else 0,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report})
        except ValueError as exc:
            write_user_event(
                "document_qa_action_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "document_qa_action_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"보완 여부 확인 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_health_check(self) -> None:
        try:
            payload = self.read_json()
            report = health_check_from_payload(payload)
            write_user_event(
                "health_check_completed",
                {
                    "name": payload.get("name"),
                    "score": report.get("score"),
                    "judgement": report.get("judgement"),
                    "mandatoryGatePassed": report.get("mandatoryGatePassed"),
                    "qualityGatePassed": report.get("qualityGatePassed"),
                    "gatekeeperGrade": (report.get("gatekeeper") or {}).get("grade") if isinstance(report.get("gatekeeper"), Mapping) else "",
                    "evaluationMode": report.get("evaluationMode"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report})
        except ValueError as exc:
            write_user_event(
                "health_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "health_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"Health Check 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_artifact_sync_repair(self) -> None:
        try:
            payload = self.read_json()
            result = repair_policy_artifact_sync_from_payload(payload)
            write_user_event(
                "artifact_sync_repair_completed",
                {
                    "name": payload.get("name"),
                    "beforeStatus": result.get("before", {}).get("status"),
                    "afterStatus": result.get("after", {}).get("status"),
                    "repairedCount": len(result.get("repaired", [])) if isinstance(result.get("repaired"), list) else 0,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, **result})
        except ValueError as exc:
            write_user_event(
                "artifact_sync_repair_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except JobConflict as exc:
            write_user_event(
                "artifact_sync_repair_conflict",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc), "conflict": exc.conflict},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "artifact_sync_repair_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"산출물 동기화 복구 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_html_spec_sync(self) -> None:
        try:
            payload = self.read_json()
            result = sync_policy_spec_from_runtime_html_from_payload(payload)
            write_user_event(
                "html_spec_sync_completed",
                {
                    "name": payload.get("name"),
                    "status": result.get("status"),
                    "htmlIdCount": (result.get("snapshot") or {}).get("html_id_count") if isinstance(result.get("snapshot"), Mapping) else 0,
                    "specIdCount": (result.get("snapshot") or {}).get("spec_id_count") if isinstance(result.get("snapshot"), Mapping) else 0,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, **result})
        except ValueError as exc:
            write_user_event(
                "html_spec_sync_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except JobConflict as exc:
            write_user_event(
                "html_spec_sync_conflict",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc), "conflict": exc.conflict},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "html_spec_sync_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"HTML 기준 spec 보정 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_health_check_export(self) -> None:
        try:
            payload = self.read_json()
            artifact = health_check_export_from_payload(payload)
            write_user_event(
                "health_check_export_completed",
                {"name": payload.get("name"), "artifact": artifact.get("name")},
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "artifact": artifact})
        except ValueError as exc:
            write_user_event(
                "health_check_export_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "health_check_export_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"Health Check 보고서 export 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_dev_format_export(self) -> None:
        try:
            payload = self.read_json()
            export = dev_format_export_from_payload(payload)
            write_user_event(
                "dev_format_export_completed",
                {
                    "name": payload.get("name"),
                    "outputDir": export.get("outputDir"),
                    "warningStatus": (export.get("warnings") or {}).get("status") if isinstance(export.get("warnings"), Mapping) else "",
                    "blockingCount": (export.get("warnings") or {}).get("blockingCount") if isinstance(export.get("warnings"), Mapping) else None,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "export": export})
        except ValueError as exc:
            write_user_event(
                "dev_format_export_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "dev_format_export_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"AI Input Export 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_analysis_alignment_check(self) -> None:
        try:
            payload = self.read_json()
            report = analysis_alignment_from_payload(payload)
            write_user_event(
                "analysis_alignment_check_completed",
                {
                    "name": payload.get("name"),
                    "score": report.get("score"),
                    "judgement": report.get("judgement"),
                    "analysisCoverageRate": report.get("analysisCoverageRate"),
                    "policyGroundingRate": report.get("policyGroundingRate"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report})
        except ValueError as exc:
            write_user_event(
                "analysis_alignment_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "analysis_alignment_check_failed",
                {"name": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"분석-정책 정렬 점검 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_channel_pi_status(self, *, force: bool) -> None:
        try:
            payload = self.read_json() if force else {}
            report = channel_pi_status_from_runtime(force=force, payload=payload)
            write_user_event(
                "channel_pi_status_diagnosed" if force else "channel_pi_status_viewed",
                {
                    "score": report.get("score"),
                    "judgement": report.get("judgement"),
                    "topicCount": report.get("topicCount"),
                    "force": force,
                    "alignmentAgent": report.get("alignmentAgent"),
                    "evaluationMode": report.get("evaluationMode"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report, "diagnosed": force})
        except ValueError as exc:
            write_user_event("channel_pi_status_failed", {"error": str(exc), "force": force})
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event("channel_pi_status_failed", {"error": str(exc), "force": force})
            self.send_json({"ok": False, "error": f"채널 PI 현황 진단 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_pi_check(self) -> None:
        try:
            payload = self.read_json()
            report = pi_check_from_payload(payload)
            write_user_event(
                "pi_check_completed",
                {
                    "fileName": report.get("fileName") or payload.get("name"),
                    "toBeFileName": (report.get("toBe") or {}).get("fileName") if isinstance(report.get("toBe"), Mapping) else "",
                    "asIsFileName": (report.get("asIs") or {}).get("fileName") if isinstance(report.get("asIs"), Mapping) else "",
                    "score": report.get("score"),
                    "judgement": report.get("judgement"),
                    "deltaScore": (report.get("comparison") or {}).get("deltaScore") if isinstance(report.get("comparison"), Mapping) else None,
                    "yesCount": report.get("yesCount"),
                    "partialCount": report.get("partialCount"),
                    "noCount": report.get("noCount"),
                    "antiPatternCount": report.get("antiPatternCount"),
                    "piReadinessGatePassed": report.get("piReadinessGatePassed"),
                    "qualityGatePassed": report.get("qualityGatePassed"),
                    "gatekeeperGrade": (report.get("gatekeeper") or {}).get("grade") if isinstance(report.get("gatekeeper"), Mapping) else "",
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "report": report})
        except ValueError as exc:
            write_user_event(
                "pi_check_failed",
                {
                    "fileName": locals().get("payload", {}).get("name"),
                    "toBeFileName": ((locals().get("payload", {}).get("toBe") or {}).get("name") if isinstance((locals().get("payload", {}).get("toBe") or {}), Mapping) else ""),
                    "asIsFileName": ((locals().get("payload", {}).get("asIs") or {}).get("name") if isinstance((locals().get("payload", {}).get("asIs") or {}), Mapping) else ""),
                    "error": str(exc),
                },
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "pi_check_failed",
                {
                    "fileName": locals().get("payload", {}).get("name"),
                    "toBeFileName": ((locals().get("payload", {}).get("toBe") or {}).get("name") if isinstance((locals().get("payload", {}).get("toBe") or {}), Mapping) else ""),
                    "asIsFileName": ((locals().get("payload", {}).get("asIs") or {}).get("name") if isinstance((locals().get("payload", {}).get("asIs") or {}), Mapping) else ""),
                    "error": str(exc),
                },
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"PI Check 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_pi_check_export(self) -> None:
        try:
            payload = self.read_json()
            artifact = pi_check_export_from_payload(payload)
            write_user_event(
                "pi_check_export_completed",
                {"fileName": (payload.get("report") or {}).get("fileName") if isinstance(payload.get("report"), Mapping) else "", "artifact": artifact.get("name")},
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "artifact": artifact})
        except ValueError as exc:
            write_user_event(
                "pi_check_export_failed",
                {"error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "pi_check_export_failed",
                {"error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"PI Check 보고서 export 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_manual_edit(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            result = save_manual_edit_from_payload(payload)
            write_user_event(
                "manual_edit_saved",
                {
                    "name": payload.get("name"),
                    "resultName": result.name,
                    "saveMode": payload.get("saveMode"),
                    "htmlChars": len(str(payload.get("html", "") or "")),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": describe_policy_file(result)})
        except JobConflict as exc:
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "manual_edit_failed",
                {"name": locals().get("payload", {}).get("name"), "saveMode": locals().get("payload", {}).get("saveMode"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "manual_edit_failed",
                {"name": locals().get("payload", {}).get("name"), "saveMode": locals().get("payload", {}).get("saveMode"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"정책서 수정 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_reference_html_edit(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            result = save_reference_html_edit_from_payload(payload)
            write_user_event(
                "reference_html_edit_saved",
                {
                    "id": payload.get("id"),
                    "url": payload.get("url"),
                    "resultName": result.name,
                    "htmlChars": len(str(payload.get("html", "") or "")),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": describe_reference_html_file(result)})
        except JobConflict as exc:
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "reference_html_edit_failed",
                {"id": locals().get("payload", {}).get("id"), "url": locals().get("payload", {}).get("url"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "reference_html_edit_failed",
                {"id": locals().get("payload", {}).get("id"), "url": locals().get("payload", {}).get("url"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"현황 분석 문서 수정 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_diagram_edit(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            result = save_policy_diagram_edit_from_payload(payload)
            write_user_event(
                "diagram_edit_saved",
                {
                    "name": payload.get("name"),
                    "resultName": result.name,
                    "saveMode": payload.get("saveMode"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": describe_policy_file(result)})
        except JobConflict as exc:
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "diagram_edit_failed",
                {"name": locals().get("payload", {}).get("name"), "saveMode": locals().get("payload", {}).get("saveMode"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "diagram_edit_failed",
                {"name": locals().get("payload", {}).get("name"), "saveMode": locals().get("payload", {}).get("saveMode"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"다이어그램 저장 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_policy_upload(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            result = upload_policy_html_from_payload(payload)
            write_user_event(
                "html_uploaded",
                {
                    "baseName": payload.get("baseName"),
                    "uploadedFileName": payload.get("name"),
                    "resultName": result.name,
                    "htmlChars": len(str(payload.get("html", "") or "")),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": describe_policy_file(result)})
        except ValueError as exc:
            write_user_event(
                "html_upload_failed",
                {"baseName": locals().get("payload", {}).get("baseName"), "uploadedFileName": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "html_upload_failed",
                {"baseName": locals().get("payload", {}).get("baseName"), "uploadedFileName": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"HTML 등록 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_policy_json_upload(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            result = upload_policy_json_from_payload(payload)
            warnings = json_upload_validation_warnings(result)
            write_user_event(
                "json_uploaded",
                {
                    "baseName": payload.get("baseName"),
                    "uploadedFileName": payload.get("name"),
                    "resultName": result.name,
                    "jsonChars": len(str(payload.get("json", "") or "")),
                    "warningCount": len(warnings),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": describe_policy_file(result), "warnings": warnings})
        except ValueError as exc:
            write_user_event(
                "json_upload_failed",
                {"baseName": locals().get("payload", {}).get("baseName"), "uploadedFileName": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "json_upload_failed",
                {"baseName": locals().get("payload", {}).get("baseName"), "uploadedFileName": locals().get("payload", {}).get("name"), "error": str(exc)},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"JSON 등록 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_revision_request(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            job = start_revision_job(payload)
            write_user_event(
                "revision_requested",
                event_payload_for_revision_request(payload, job=job, status="accepted"),
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "job": job}, status=202)
        except JobConflict as exc:
            write_user_event(
                "revision_conflict",
                {"error": str(exc), "conflict": exc.conflict, **event_payload_for_revision_request(locals().get("payload", {}), status="conflict")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            write_user_event(
                "revision_failed",
                {"error": str(exc), **event_payload_for_revision_request(locals().get("payload", {}), status="validation_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            write_user_event(
                "revision_failed",
                {"error": str(exc), **event_payload_for_revision_request(locals().get("payload", {}), status="server_error")},
                session_id=client_session_id_from_payload(locals().get("payload", {})),
            )
            self.send_json({"ok": False, "error": f"정책서 보완 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_policy_status(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            item = update_policy_lifecycle_from_payload(payload)
            write_user_event(
                "policy_status_changed",
                {"name": payload.get("name"), "status": payload.get("status"), "resultName": item.get("name")},
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "item": item})
        except JobConflict as exc:
            self.send_json({"ok": False, "error": str(exc), "conflict": exc.conflict}, status=409)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"정책서 상태 변경 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_policy_comments_get(self, parsed) -> None:
        try:
            query = parse_qs(parsed.query)
            name = str(query.get("name", [""])[0] or "").strip()
            if not name:
                raise ValueError("코멘트를 조회할 정책서를 선택해 주세요.")
            payload = load_policy_comments(name)
            self.send_json({"ok": True, **public_policy_comments_payload(payload)})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"정책서 코멘트 조회 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_policy_comments_update(self) -> None:
        try:
            payload = self.read_json()
            self.apply_authenticated_user(payload)
            user = self.current_user() or {}
            result = update_policy_comments_from_payload(payload, user)
            write_user_event(
                "policy_comment_updated",
                {
                    "name": payload.get("name"),
                    "action": payload.get("action"),
                    "commentCount": len(result.get("comments", [])) if isinstance(result.get("comments"), list) else 0,
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, **public_policy_comments_payload(result)})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"정책서 코멘트 저장 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_usage_event(self) -> None:
        try:
            payload = self.read_json()
            event_name = str(payload.get("event", "") or "").strip()
            if not event_name:
                raise ValueError("이벤트명이 없습니다.")
            write_user_event(
                event_name,
                payload.get("details") if isinstance(payload.get("details"), Mapping) else {},
                session_id=client_session_id_from_payload(payload),
                source="client",
            )
            self.send_json({"ok": True})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - analytics must not affect UI flows.
            self.send_json({"ok": False, "error": f"사용 로그 저장 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_job_status(self, job_id: str) -> None:
        job_id = job_id.strip()
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                self.send_json({"ok": False, "error": "작업을 찾을 수 없습니다."}, status=404)
                return
            self.send_json({"ok": True, "job": public_job(job)})

    def handle_job_cancel(self, path: str) -> None:
        try:
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "jobs"] or parts[3] != "cancel":
                raise ValueError("작업 중단 경로가 올바르지 않습니다.")
            job_id = parts[2].strip()
            payload = self.read_json()
            snapshot = request_job_cancel(job_id)
            write_user_event(
                "job_cancel_requested",
                {
                    "jobId": job_id,
                    "kind": snapshot.get("kind"),
                    "topic": snapshot.get("topic"),
                    "status": snapshot.get("status"),
                    "reason": payload.get("reason"),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "job": snapshot})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"작업 중단 처리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_job_review(self, path: str) -> None:
        try:
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "jobs"] or parts[3] != "review":
                raise ValueError("검수 응답 경로가 올바르지 않습니다.")
            job_id = parts[2].strip()
            payload = self.read_json()
            action = str(payload.get("action", "")).strip().casefold()
            instruction = str(payload.get("instruction", "")).strip()
            if action not in {"continue", "revise", "stop"}:
                raise ValueError("검수 응답은 다음 단계 진행, 보완 요청, 저장 중단 중 하나여야 합니다.")
            if action == "revise" and not instruction:
                raise ValueError("보완 요청 내용을 입력해 주세요.")
            if action == "continue":
                continued = continue_pending_revision_save(job_id)
                if continued:
                    self.send_json({"ok": True, "job": continued})
                    return

            with JOBS_CONDITION:
                job = JOBS.get(job_id)
                if not job:
                    raise ValueError("작업을 찾을 수 없습니다.")
                review = job.get("manualReview")
                if job.get("status") != "waiting_review" or not isinstance(review, dict):
                    raise ValueError("현재 사용자 검수를 기다리는 단계가 없습니다.")
                review["response"] = {"action": action, "instruction": instruction}
                job["message"] = "수정본 저장을 중단합니다." if action == "stop" else "검수 의견을 Agent에게 전달했습니다."
                job["status"] = "running"
                stage = stage_by_key(job, str(review.get("stageKey", "")))
                if stage:
                    stage["status"] = "error" if action == "stop" else "retry" if action == "revise" else "done"
                    stage["message"] = job["message"]
                update_policy_job_lock(job, "running", str(review.get("stageKey", "")))
                snapshot = public_job(job)
                JOBS_CONDITION.notify_all()
            write_user_event(
                "manual_review_response",
                {
                    "jobId": job_id,
                    "topic": snapshot.get("topic"),
                    "action": action,
                    "stageKey": review.get("stageKey", ""),
                    "stageLabel": review.get("stageLabel", ""),
                    "instructionPreview": instruction,
                    "instructionChars": len(instruction),
                },
                session_id=client_session_id_from_payload(payload),
            )
            self.send_json({"ok": True, "job": snapshot})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"검수 응답 처리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_job_heartbeat(self, path: str) -> None:
        try:
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "jobs"] or parts[3] != "heartbeat":
                raise ValueError("작업 연결 확인 경로가 올바르지 않습니다.")
            job_id = parts[2].strip()
            payload = self.read_json()
            session_id = normalize_client_session_id(
                self.headers.get("X-NC-Session-Id", "") or payload.get("clientSessionId", "")
            )
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if not job:
                    raise ValueError("작업을 찾을 수 없습니다.")
                if not refresh_job_heartbeat(job, session_id):
                    raise ValueError("작업을 시작한 브라우저 세션과 일치하지 않습니다.")
                snapshot = public_job(job)
            self.send_json({"ok": True, "job": snapshot})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"작업 연결 확인 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_access_signup(self) -> None:
        try:
            payload = self.read_json()
            try:
                user = create_user_account(
                    payload.get("name"),
                    payload.get("employeeId"),
                    payload.get("password"),
                    payload.get("code"),
                    payload.get("passwordConfirm"),
                )
            except PermissionError as exc:
                write_user_event(
                    "account_signup_failed",
                    {"reason": "invalid_code", "employeeHash": masked_employee_id(payload.get("employeeId"))},
                    session_id=client_session_id_from_payload(payload),
                    source="server",
                )
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            write_user_event(
                "account_signup_success",
                {
                    "employeeHash": masked_employee_id(user.get("employeeId")),
                    "name": user.get("name"),
                    "approved": user.get("approved"),
                    "approvalRequired": USER_APPROVAL_REQUIRED,
                },
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            if not user.get("approved", True):
                self.send_json({"ok": True, "authorized": False, "user": user, "approvalRequired": True})
                return
            self.send_json(
                {"ok": True, "authorized": True, "user": user, "approvalRequired": USER_APPROVAL_REQUIRED},
                headers={
                    "Set-Cookie": session_cookie_header(ACCESS_COOKIE_NAME, create_user_session_token(user))
                },
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"회원가입 처리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_access_login(self) -> None:
        try:
            payload = self.read_json()
            try:
                user = authenticate_user(payload.get("employeeId"), payload.get("password"))
            except PermissionError as exc:
                write_user_event(
                    "account_login_failed",
                    {"reason": "invalid_credentials", "employeeHash": masked_employee_id(payload.get("employeeId"))},
                    session_id=client_session_id_from_payload(payload),
                    source="server",
                )
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            write_user_event(
                "account_login_success",
                {"employeeHash": masked_employee_id(user.get("employeeId")), "name": user.get("name")},
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json(
                {"ok": True, "authorized": True, "user": user},
                headers={
                    "Set-Cookie": session_cookie_header(ACCESS_COOKIE_NAME, create_user_session_token(user))
                },
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"로그인 처리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_access_password_reset(self) -> None:
        try:
            payload = self.read_json()
            try:
                user = reset_user_password(
                    payload.get("employeeId"),
                    payload.get("password"),
                    payload.get("passwordConfirm"),
                    payload.get("code"),
                )
            except PermissionError as exc:
                write_user_event(
                    "account_password_reset_failed",
                    {"reason": "permission_denied", "employeeHash": masked_employee_id(payload.get("employeeId"))},
                    session_id=client_session_id_from_payload(payload),
                    source="server",
                )
                self.send_json({"ok": False, "error": str(exc)}, status=403)
                return
            write_user_event(
                "account_password_reset_success",
                {"employeeHash": masked_employee_id(user.get("employeeId")), "name": user.get("name")},
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json(
                {"ok": True, "authorized": True, "user": user},
                headers={
                    "Set-Cookie": session_cookie_header(ACCESS_COOKIE_NAME, create_user_session_token(user))
                },
            )
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"비밀번호 재설정 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_user_withdrawal(self) -> None:
        user = self.current_user()
        if not can_manage_users(user):
            self.send_json({"ok": False, "error": "사용자 관리는 관리자만 처리할 수 있습니다."}, status=403)
            return
        try:
            payload = self.read_json()
            target_employee_id = payload.get("employeeId")
            withdrawn = withdraw_user_account(target_employee_id, user)
            write_user_event(
                "account_admin_withdrawn",
                {
                    "employeeHash": masked_employee_id(withdrawn.get("employeeId")),
                    "name": withdrawn.get("name"),
                    "adminHash": masked_employee_id(user.get("employeeId") if user else ""),
                    "adminName": user.get("name") if user else "",
                },
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json({"ok": True, "user": withdrawn, "users": build_user_management_dashboard()})
        except PermissionError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=403)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"탈퇴 처리 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_user_role_update(self) -> None:
        user = self.current_user()
        if not can_manage_users(user):
            self.send_json({"ok": False, "error": "사용자 관리는 관리자만 처리할 수 있습니다."}, status=403)
            return
        try:
            payload = self.read_json()
            target_employee_id = payload.get("employeeId")
            role = payload.get("role")
            updated = update_user_account_role(target_employee_id, role, user)
            write_user_event(
                "account_admin_role_updated",
                {
                    "employeeHash": masked_employee_id(updated.get("employeeId")),
                    "name": updated.get("name"),
                    "role": updated.get("role"),
                    "adminHash": masked_employee_id(user.get("employeeId") if user else ""),
                    "adminName": user.get("name") if user else "",
                },
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json({"ok": True, "user": updated, "users": build_user_management_dashboard()})
        except PermissionError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=403)
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"권한 변경 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_access_logout(self) -> None:
        user = self.current_user() or {}
        write_user_event(
            "account_logout",
            {"employeeHash": masked_employee_id(user.get("employeeId")), "name": user.get("name")},
            session_id=normalize_client_session_id(self.headers.get("X-NC-Session-Id", "")),
            source="server",
        )
        self.send_json(
            {"ok": True, "authorized": False},
            headers={
                "Set-Cookie": clear_cookie_header(ACCESS_COOKIE_NAME)
            },
        )

    def handle_llm_access_login(self) -> None:
        if not self.require_api_access():
            return
        try:
            payload = self.read_json()
            key = str(payload.get("key", "")).strip()
            if not key:
                raise ValueError("LLM 사용 인증키를 입력해 주세요.")
            if key != LLM_ACCESS_KEY:
                write_user_event(
                    "llm_access_failed",
                    {"reason": "invalid_key"},
                    session_id=client_session_id_from_payload(payload),
                    source="server",
                )
                self.send_json({"ok": False, "error": "LLM 사용 인증키가 올바르지 않습니다."}, status=403)
                return
            write_user_event(
                "llm_access_success",
                {},
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json({"ok": True, "authorized": True, "token": LLM_ACCESS_TOKEN_VALUE})
        except ValueError as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"LLM 사용 인증 중 오류가 발생했습니다: {exc}"}, status=500)

    def handle_site_writer_mode_update(self) -> None:
        if not self.require_policy_admin_action_access("LLM 사용 설정은 관리자만 변경할 수 있습니다."):
            return
        try:
            payload = self.read_json()
            writer_mode = normalize_site_writer_mode(payload.get("writerMode", "mock"))
            if writer_mode == "llm":
                validate_llm_access_from_payload(payload, writer_mode, allow_site_setting=False)
            save_site_writer_mode(writer_mode, self.current_user())
            write_user_event(
                "site_writer_mode_changed",
                {"writerMode": writer_mode},
                session_id=client_session_id_from_payload(payload),
                source="server",
            )
            self.send_json({"ok": True, "settings": public_site_settings_status(self.current_user())})
        except ValueError as exc:
            message = str(exc)
            status = 403 if "권한" in message or "인증키" in message else 400
            self.send_json({"ok": False, "error": message}, status=status)
        except Exception as exc:  # pragma: no cover - defensive boundary for the UI.
            self.send_json({"ok": False, "error": f"LLM 사용 설정 저장 중 오류가 발생했습니다: {exc}"}, status=500)

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        if not raw_body:
            data: Dict[str, Any] = {}
            session_id = normalize_client_session_id(self.headers.get("X-NC-Session-Id", ""))
            if session_id:
                data["clientSessionId"] = session_id
            return data
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("요청 형식이 올바르지 않습니다.") from exc
        if not isinstance(data, dict):
            raise ValueError("요청 본문은 JSON 객체여야 합니다.")
        session_id = normalize_client_session_id(self.headers.get("X-NC-Session-Id", "") or data.get("clientSessionId", ""))
        if session_id:
            data["clientSessionId"] = session_id
        return data

    def send_json(self, payload: Dict[str, Any], status: int = 200, headers: Optional[Mapping[str, str]] = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, body_text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        body = body_text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header("X-Robots-Tag", NOINDEX_HEADER_VALUE)
        super().end_headers()

    def is_blocked_crawler_request(self) -> bool:
        return is_blocked_crawler_user_agent(self.headers.get("User-Agent", ""))

    def serve_static_file(self, path: Path) -> None:
        try:
            safe_path = safe_child_path(WEB_ROOT, path)
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if not safe_path.exists() or not safe_path.is_file():
            self.send_error(404, "Not found")
            return

        self.send_file(safe_path)

    def serve_output_file(self, raw_name: str) -> None:
        try:
            requested = OUTPUT_ROOT / unquote(raw_name)
            safe_path = safe_child_path(OUTPUT_ROOT, requested)
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if not safe_path.exists() or not safe_path.is_file():
            self.send_error(404, "Not found")
            return

        headers: Dict[str, str] = {}
        if safe_path.suffix.lower() in {".html", ".htm"}:
            headers["Content-Security-Policy"] = output_file_content_security_policy(safe_path)
            headers["X-Content-Type-Options"] = "nosniff"
        self.send_file(safe_path, headers=headers)

    def send_file(self, path: Path, headers: Optional[Mapping[str, str]] = None) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type = f"{content_type}; charset=utf-8"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def request_cookies(self) -> Dict[str, str]:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return {}
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return {}
        return {key: morsel.value for key, morsel in jar.items()}

    def current_user(self) -> Optional[Dict[str, Any]]:
        return user_from_session_token(self.request_cookies().get(ACCESS_COOKIE_NAME, ""))

    def apply_authenticated_user(self, payload: Dict[str, Any]) -> None:
        user = self.current_user()
        if not user:
            return
        payload["author"] = user.get("name") or "Policy Web"
        payload["updatedBy"] = user.get("name") or "Policy Web"
        payload["authenticatedUser"] = user

    def is_authorized(self) -> bool:
        return bool(self.current_user())

    def require_api_access(self) -> bool:
        if self.is_authorized():
            return True
        self.send_json({"ok": False, "error": "로그인 후 이용할 수 있습니다.", "code": "access_denied"}, status=401)
        return False

    def require_policy_write_access(self) -> bool:
        if can_write_documents(self.current_user()):
            return True
        self.send_json(
            {
                "ok": False,
                "error": "조회 권한은 문서 생성·수정·삭제를 실행할 수 없습니다.",
                "code": "write_permission_required",
            },
            status=403,
        )
        return False

    def require_policy_admin_action_access(self, message: str = "이 작업은 관리자만 실행할 수 있습니다.") -> bool:
        user = self.current_user()
        if can_manage_users(user):
            return True
        status = 401 if not user else 403
        code = "access_denied" if not user else "admin_permission_required"
        self.send_json({"ok": False, "error": message, "code": code}, status=status)
        return False

    def require_channel_pi_status_access(self) -> bool:
        user = self.current_user()
        if can_manage_users(user):
            return True
        status = 401 if not user else 403
        code = "access_denied" if not user else "admin_permission_required"
        message = "로그인 후 이용할 수 있습니다." if not user else "채널 PI 현황은 관리자만 확인할 수 있습니다."
        self.send_json({"ok": False, "error": message, "code": code}, status=status)
        return False


def truthy_payload_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "on", "사용", "재작성"}


def policy_generation_admin_action_required(payload: Mapping[str, Any]) -> bool:
    return bool(policy_generation_admin_action(payload))


def policy_generation_admin_action(payload: Mapping[str, Any]) -> str:
    if truthy_payload_value(payload.get("rewriteExisting") or payload.get("recreateExisting")):
        return "rewrite"
    if truthy_payload_value(payload.get("fullFromSimple")):
        return "full_from_simple"
    if str(payload.get("templateType", "") or "").strip().casefold() == "full":
        return "full"
    return ""


def policy_generation_admin_action_error(payload: Mapping[str, Any]) -> str:
    action = policy_generation_admin_action(payload)
    if action == "rewrite":
        return "정책서 다시 작성은 관리자만 실행할 수 있습니다."
    if action in {"full", "full_from_simple"}:
        return "Full 버전 작성은 관리자만 실행할 수 있습니다."
    return "이 작업은 관리자만 실행할 수 있습니다."


def start_full_from_simple_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    checkpoint_path: Optional[Path] = None
    prepared_payload: Dict[str, Any] = {}
    try:
        checkpoint_path, prepared_payload = prepare_full_from_simple_payload(payload)
        return start_policy_job(prepared_payload)
    except Exception:
        if checkpoint_path and checkpoint_path.exists():
            delete_file_if_exists(checkpoint_path)
            latest_path = full_continuation_latest_checkpoint_path(checkpoint_path)
            if latest_path != checkpoint_path:
                delete_file_if_exists(latest_path)
        raise


def prepare_full_from_simple_payload(payload: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
    source_name = str(payload.get("sourceName") or payload.get("name") or "").strip()
    if not source_name:
        raise ValueError("Full 버전으로 확장할 간소화 문서를 선택해 주세요.")
    source_path = policy_file_path(source_name)
    parsed = parse_policy_filename(source_path.name)
    if parsed.get("template_label") != "간소화":
        raise ValueError("Full 버전 작성은 간소화 버전 문서에서만 시작할 수 있습니다.")
    lifecycle = load_policy_lifecycle(source_path)
    if lifecycle.get("status") != "completed":
        raise ValueError("간소화 버전이 작성 완료 상태일 때만 Full 버전을 이어서 작성할 수 있습니다.")

    source_version = parsed.get("version", "")
    topic_slug = parsed.get("topic", "")
    topic = str(payload.get("topic") or topic_slug).strip() or topic_slug
    full_version = next_version_for_topic_template(topic_slug, "full")
    author = str(payload.get("author", "")).strip() or "Policy Web"
    spec = load_simple_spec_for_full_continuation(source_path)
    ensure_policy_spec_base_keys(spec)
    prepare_full_continuation_spec(
        spec,
        topic=topic,
        topic_slug=topic_slug,
        full_version=full_version,
        source_name=source_path.name,
        source_version=source_version,
        author=author,
    )

    review_mode = str(payload.get("reviewMode", "auto")).strip().casefold() or "auto"
    inspection_mode = str(payload.get("inspectionMode", "chapter-final")).strip().casefold() or "chapter-final"
    writer_mode = normalize_writer_mode_from_payload(payload)
    checkpoint_path = write_full_continuation_checkpoint(
        spec,
        topic=topic,
        topic_slug=topic_slug,
        full_version=full_version,
        review_mode=review_mode,
        inspection_mode=inspection_mode,
        writer_mode=writer_mode,
        source_name=source_path.name,
    )
    relative_checkpoint = checkpoint_path.relative_to(OUTPUT_ROOT)
    prepared = dict(payload)
    prepared.update(
        {
            "topic": topic,
            "templateType": "full",
            "reviewMode": review_mode,
            "inspectionMode": inspection_mode,
            "writerMode": writer_mode,
            "resumeFrom": str(relative_checkpoint),
            "fullFromSimple": True,
            "sourceSimpleName": source_path.name,
            "brief": str(payload.get("brief") or "").strip()
            or f"간소화 {source_version} 문서를 기준으로 Full 전용 상세 장만 이어서 작성한다.",
        }
    )
    return checkpoint_path, prepared


def load_simple_spec_for_full_continuation(source_path: Path) -> Dict[str, Any]:
    parsed = parse_policy_filename(source_path.name)
    topic_slug = parsed.get("topic", "")
    source_version = parsed.get("version", "")
    checkpoint_candidates = [
        policy_version_spec_path(source_path),
        OUTPUT_ROOT
        / "checkpoints"
        / f"NC_{topic_slug}_정책서_간소화_{source_version}_latest_checkpoint.json",
        OUTPUT_ROOT
        / "checkpoints"
        / f"NC_{topic_slug}_정책서_간소화_{source_version}_10_final_check_checkpoint.json",
        OUTPUT_ROOT
        / f"{topic_slug}_policy_spec.json",
    ]
    for path in checkpoint_candidates:
        if not path.exists() or not path.is_file():
            continue
        spec = read_policy_spec_payload(path)
        if spec is None:
            continue
        meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
        template_type = str(meta.get("template_type", "") or "").strip().casefold()
        version = str(meta.get("version", "") or "").strip()
        if template_type and template_type != "simple":
            continue
        if version and version != source_version:
            continue
        return json.loads(json.dumps(spec, ensure_ascii=False))
    raise ValueError(
        "Full 버전 작성에 필요한 간소화 구조 데이터가 없습니다. "
        "간소화 문서의 최신 체크포인트 또는 JSON spec이 남아 있는지 확인해 주세요."
    )


def prepare_full_continuation_spec(
    spec: Dict[str, Any],
    *,
    topic: str,
    topic_slug: str,
    full_version: str,
    source_name: str,
    source_version: str,
    author: str,
) -> None:
    meta = spec.setdefault("meta", {})
    meta.update(
        {
            "topic": topic,
            "topic_slug": topic_slug,
            "document_type": "Full 버전",
            "template_type": "full",
            "version": full_version,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author": author,
            "source_simple_document": {
                "name": source_name,
                "version": source_version,
                "mode": "full_from_simple_continuation",
            },
        }
    )
    meta.pop("inspector_pass_cache", None)
    meta.setdefault("continuation_runs", []).append(
        {
            "type": "full_from_simple",
            "sourceName": source_name,
            "sourceVersion": source_version,
            "targetVersion": full_version,
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        }
    )
    chapter_state = meta.get("chapter_state")
    if isinstance(chapter_state, dict):
        for key in ("process_detail", "function_detail", "terms_refinement", "final_check"):
            chapter_state.pop(key, None)
    spec["process_details"] = []
    spec["function_details"] = []
    history = spec.setdefault("history", [])
    if isinstance(history, list):
        history.append(
            {
                "version": full_version,
                "change": f"간소화 {source_version} 문서를 기준으로 Full 버전 상세 장 작성 시작",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "author": author,
            }
        )


def write_full_continuation_checkpoint(
    spec: Dict[str, Any],
    *,
    topic: str,
    topic_slug: str,
    full_version: str,
    review_mode: str,
    inspection_mode: str,
    writer_mode: str,
    source_name: str,
) -> Path:
    checkpoints_dir = OUTPUT_ROOT / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "checkpoint": {
            "topic": topic,
            "topic_slug": topic_slug,
            "template_type": "full",
            "version": full_version,
            "inspection_mode": inspection_mode,
            "writer_mode": writer_mode,
            "review_mode": review_mode,
            "stage_key": "09",
            "stage_name": "policies",
            "stage_label": "Policies Agent",
            "attempt": 1,
            "passed": True,
            "summary": "간소화 버전 작성 완료본을 기반으로 Full 전용 상세 장부터 이어서 작성합니다.",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "next_action": "resume_from_next_stage",
            "source_simple_name": source_name,
        },
        "spec": spec,
    }
    path = checkpoints_dir / f"NC_{topic_slug}_정책서_Full_{full_version}_full_from_simple_checkpoint.json"
    latest_path = checkpoints_dir / f"NC_{topic_slug}_정책서_Full_{full_version}_latest_checkpoint.json"
    payload = json.dumps(checkpoint, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    return path


def full_continuation_latest_checkpoint_path(path: Path) -> Path:
    name = path.name.replace("_full_from_simple_checkpoint.json", "_latest_checkpoint.json")
    return path.with_name(name)


def next_version_for_topic_template(topic_slug: str, template_type: str) -> str:
    label = template_file_label(template_type)
    versions: List[str] = []
    pattern = re.compile(
        rf"^NC_{re.escape(topic_slug)}_정책서_{re.escape(label)}_v(?P<major>\d+)\.(?P<minor>\d+)\.html$"
    )
    for path in OUTPUT_ROOT.glob(f"NC_{topic_slug}_정책서_{label}_v*.html"):
        match = pattern.match(path.name)
        if match:
            versions.append(f"v{match.group('major')}.{match.group('minor')}")
    return next_policy_version(versions)


def start_policy_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    authenticated_user = payload.get("authenticatedUser") if isinstance(payload.get("authenticatedUser"), Mapping) else None
    if authenticated_user is not None and policy_generation_admin_action_required(payload) and not can_manage_users(authenticated_user):
        raise PermissionError(policy_generation_admin_action_error(payload))
    args = build_create_args_from_payload(payload)
    validate_llm_access_from_payload(payload, args.writer_mode)
    session_id = client_session_id_from_payload(payload)
    existing = latest_policy_for_topic(args.topic)
    rewrite_existing = truthy_payload_value(payload.get("rewriteExisting") or payload.get("recreateExisting"))
    if existing and rewrite_existing and load_policy_lifecycle(existing).get("status") == "completed":
        raise ValueError("작성 완료 상태에서는 '작성 완료 취소' 후에만 다시 작성할 수 있습니다.")
    if existing and not rewrite_existing and not str(getattr(args, "resume_from", "") or "").strip():
        raise ValueError(
            f"이미 같은 주제로 생성된 정책서가 있습니다: {existing.name}. 신규 생성은 제한되며 기존 정책서를 수정해 주세요."
        )
    job_id = uuid.uuid4().hex
    lock_info = acquire_policy_job_lock(args.topic, args.template_type, job_id, session_id=session_id)
    full_from_simple = truthy_payload_value(payload.get("fullFromSimple"))
    job = {
        "id": job_id,
        "kind": "create",
        "status": "queued",
        "topic": args.topic,
        "templateType": args.template_type,
        "reviewMode": args.review_mode,
        "inspectionMode": args.inspection_mode,
        "writerMode": args.writer_mode,
        "rewriteExisting": rewrite_existing,
        "fullFromSimple": full_from_simple,
        "sourceSimpleName": str(payload.get("sourceSimpleName", "")).strip(),
        "message": "작업 대기열에 등록되었습니다. 앞선 작업이 없으면 곧바로 시작합니다.",
        "queueLimit": MAX_ACTIVE_POLICY_JOBS,
        "queuedAt": datetime.now().isoformat(timespec="seconds"),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "startedAt": None,
        "finishedAt": None,
        "elapsedMs": 0,
        "_startedMono": None,
        "_startedWall": None,
        "_lastClientHeartbeatMono": current_time() if session_id else None,
        "lastClientHeartbeatAt": datetime.now().isoformat(timespec="seconds") if session_id else "",
        "currentStageKey": "",
        "result": None,
        "error": "",
        "cancelRequested": False,
        "deletedFiles": [],
        "manualReview": None,
        "lockKey": lock_info["key"],
        "lockPath": lock_info["path"],
        "clientSessionId": session_id,
        "activity": [],
        "stages": [
            {
                "key": key,
                "name": name,
                "label": label,
                "status": "pending",
                "attempt": 0,
                "score": None,
                "threshold": None,
                "durationMs": 0,
                "message": "",
                "artifact": None,
                "checkpoint": None,
                "preview": None,
                "startedAt": None,
                "finishedAt": None,
                "_startedMono": None,
            }
            for key, name, label in stage_definitions_for_template(args.template_type)
        ],
    }
    if full_from_simple:
        job["message"] = "간소화 버전을 기준으로 Full 전용 상세 장 작성 대기열에 등록되었습니다."
        for stage in job["stages"]:
            if stage["key"] in {"00", "01", "02", "03", "04", "05", "06", "07", "08", "09"}:
                stage.update(
                    {
                        "status": "done",
                        "message": "간소화 버전 작성 완료본에서 승계되었습니다.",
                        "startedAt": job["createdAt"],
                        "finishedAt": job["createdAt"],
                    }
                )
    try:
        with JOBS_LOCK:
            JOBS[job_id] = job

        snapshot = public_job(job)
        thread = threading.Thread(target=run_policy_job, args=(job_id, payload), daemon=True)
        thread.start()
        return snapshot
    except Exception:
        update_policy_job_lock(job, "failed", "")
        raise


def acquire_policy_job_lock(topic: str, template_type: str, job_id: str, session_id: str = "") -> Dict[str, str]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    key = job_lock_key(topic, template_type)
    path = safe_child_path(LOCK_DIR, LOCK_DIR / f"{key}.lock")
    data = {
        "lock_key": key,
        "job_id": job_id,
        "topic": topic,
        "template_type": template_type,
        "session_id": normalize_client_session_id(session_id),
        "pid": os.getpid(),
        "status": "queued",
        "current_chapter": "",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "started_at_epoch": time.time(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    existing = claim_lock_file(path, data)
    if active_lock(existing):
        raise JobConflict(
            "같은 주제의 정책서 생성 작업이 이미 진행 중입니다. 현재 작업이 끝난 뒤 다시 시도해 주세요.",
            {
                "jobId": existing.get("job_id") or existing.get("jobId"),
                "status": existing.get("status"),
                "currentChapter": existing.get("current_chapter", ""),
                "startedAt": existing.get("started_at", ""),
            },
        )
    return {"key": key, "path": str(path)}


def job_lock_key(topic: str, template_type: str) -> str:
    topic_slug = make_topic_slug(topic)
    template = str(template_type or "simple").strip() or "simple"
    safe_topic = re.sub(r"[^\w가-힣.-]+", "_", topic_slug, flags=re.UNICODE).strip("._-") or "정책서"
    safe_template = re.sub(r"[^A-Za-z0-9_.-]+", "_", template).strip("._-") or "simple"
    digest = hashlib.sha1(f"{topic_slug}:{safe_template}".encode("utf-8")).hexdigest()[:8]
    return f"{safe_topic[:80]}_{safe_template}_{digest}"


def read_policy_job_lock(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_policy_job_lock(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def claim_lock_file(path: Path, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a lock with exclusive file creation, returning active conflicts."""
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        existing = read_policy_job_lock(path)
        if active_lock(existing):
            return existing
        write_policy_job_lock(path, data)
        return {}
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    return {}


def active_lock(data: Dict[str, Any]) -> bool:
    if not data:
        return False
    status = str(data.get("status", "")).strip().casefold()
    if status not in ACTIVE_LOCK_STATUSES:
        return False
    try:
        started = float(data.get("updated_at_epoch") or data.get("started_at_epoch") or 0)
    except (TypeError, ValueError):
        started = 0
    ttl = DOCUMENT_LOCK_TTL_SECONDS if str(data.get("lock_key", "")).startswith("doc_") else JOB_LOCK_TTL_SECONDS
    return bool(started and time.time() - started <= ttl)


def update_policy_job_lock(job: Dict[str, Any], status: str = "", current_chapter: str = "") -> None:
    raw_path = str(job.get("lockPath", "")).strip()
    if not raw_path:
        return
    try:
        path = safe_child_path(LOCK_DIR, Path(raw_path))
        data = read_policy_job_lock(path)
        data.update(
            {
                "lock_key": job.get("lockKey") or data.get("lock_key", ""),
                "job_id": job.get("id") or data.get("job_id", ""),
                "topic": job.get("topic") or data.get("topic", ""),
                "template_type": job.get("templateType") or data.get("template_type", ""),
                "pid": os.getpid(),
                "status": status or str(job.get("status", "") or data.get("status", "")),
                "current_chapter": current_chapter or str(job.get("currentStageKey", "") or data.get("current_chapter", "")),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at_epoch": time.time(),
            }
        )
        if not data.get("started_at_epoch"):
            data["started_at_epoch"] = time.time()
        if not data.get("started_at"):
            data["started_at"] = datetime.now().isoformat(timespec="seconds")
        write_policy_job_lock(path, data)
    except (OSError, ValueError):
        return


def normalize_client_session_id(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", raw)[:80]


def client_session_id_from_payload(payload: Mapping[str, Any]) -> str:
    return normalize_client_session_id(payload.get("clientSessionId", ""))


USER_EVENT_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:token|key|code|password|secret|cookie|html|document|api|basehash)",
    re.IGNORECASE,
)


def hashed_client_session_id(session_id: str) -> str:
    normalized = normalize_client_session_id(session_id)
    if not normalized:
        return ""
    return hashlib.sha256(f"ncstudio-user-event|{normalized}".encode("utf-8")).hexdigest()[:16]


def safe_user_event_payload(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[max-depth]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return limit_text(value.strip(), USER_EVENT_MAX_STRING_CHARS)
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            key_text = str(key)
            if key_text.casefold().endswith(("chars", "count")) and isinstance(item, (int, float)):
                result[key_text] = item
                continue
            if USER_EVENT_SENSITIVE_KEY_PATTERN.search(key_text):
                if isinstance(item, str):
                    result[f"{key_text}Chars"] = len(item)
                elif item is not None:
                    result[key_text] = "[redacted]"
                continue
            result[key_text] = safe_user_event_payload(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [safe_user_event_payload(item, depth=depth + 1) for item in list(value)[:50]]
    return limit_text(str(value), USER_EVENT_MAX_STRING_CHARS)


def write_user_event(
    event: str,
    payload: Mapping[str, Any] | None = None,
    *,
    session_id: str = "",
    source: str = "server",
) -> None:
    event_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(event or "").strip())[:80]
    if not event_name:
        return
    try:
        details = safe_user_event_payload(payload or {})
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "event": event_name,
            "source": source,
            "session": hashed_client_session_id(session_id),
            "details": details,
        }
        serialized = json.dumps(entry, ensure_ascii=False)
        if len(serialized.encode("utf-8")) > USER_EVENT_MAX_PAYLOAD_BYTES:
            entry["details"] = {
                "truncated": True,
                "summary": limit_text(json.dumps(details, ensure_ascii=False), USER_EVENT_MAX_STRING_CHARS),
            }
            serialized = json.dumps(entry, ensure_ascii=False)
        USER_EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with USER_EVENT_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(serialized + "\n")
    except OSError:
        return


def update_cached_topic_direction(topic: str, lines: List[str]) -> bool:
    """Apply edited direction lines to the cached knowledge pack immediately.

    Rebuilding a Topic Knowledge Pack can touch requirements, references, and
    evidence maps. For UI edits we first update the small direction fields so
    the user sees the saved value right away, then rebuild the full pack in the
    background.
    """

    path = topic_knowledge_path(topic, DEFAULT_TOPIC_KNOWLEDGE_DIR)
    if not path.exists():
        return False
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(pack, dict) or pack.get("version") != TOPIC_KNOWLEDGE_VERSION:
        return False

    display_lines, agent_lines = split_direction_milestone(lines)
    agent_guidance = list(dict.fromkeys([*display_lines, *agent_lines]))[:8]
    pack["topic_direction_milestone"] = lines
    pack["topic_direction_strategy"] = display_lines
    pack["topic_direction_agent_guidance"] = agent_guidance
    pack["direction_updated_at"] = datetime.now().isoformat(timespec="seconds")
    pack["knowledge_refresh_pending"] = True
    try:
        save_topic_knowledge_pack(pack, DEFAULT_TOPIC_KNOWLEDGE_DIR)
    except OSError:
        return False
    return True


def build_runtime_topic_scope_definitions() -> Dict[str, Dict[str, Any]]:
    return build_topic_scope_definitions(topic_knowledge_dir=DEFAULT_TOPIC_KNOWLEDGE_DIR, output_dir=OUTPUT_ROOT)


def runtime_topic_scope_definition(topic: str) -> Optional[Dict[str, Any]]:
    return topic_scope_definition(topic, topic_knowledge_dir=DEFAULT_TOPIC_KNOWLEDGE_DIR, output_dir=OUTPUT_ROOT)


def queue_topic_knowledge_refresh(topic: str, *, session_id: str = "") -> bool:
    normalized = make_topic_slug(topic)
    if not normalized:
        return False
    with TOPIC_KNOWLEDGE_REFRESH_LOCK:
        if normalized in TOPIC_KNOWLEDGE_REFRESHING:
            return False
        TOPIC_KNOWLEDGE_REFRESHING.add(normalized)

    thread = threading.Thread(
        target=run_topic_knowledge_refresh,
        args=(topic, normalized, session_id),
        daemon=True,
    )
    thread.start()
    return True


def run_topic_knowledge_refresh(topic: str, normalized: str, session_id: str = "") -> None:
    started = time.time()
    try:
        path = build_and_save_topic_knowledge_pack(topic)
        write_user_event(
            "topic_direction_refresh_completed",
            {"topic": topic, "path": str(path), "elapsedSeconds": round(time.time() - started, 3)},
            session_id=session_id,
        )
    except Exception as exc:  # pragma: no cover - background refresh boundary.
        write_user_event(
            "topic_direction_refresh_failed",
            {"topic": topic, "error": str(exc), "elapsedSeconds": round(time.time() - started, 3)},
            session_id=session_id,
        )
    finally:
        with TOPIC_KNOWLEDGE_REFRESH_LOCK:
            TOPIC_KNOWLEDGE_REFRESHING.discard(normalized)


def event_payload_for_policy_request(payload: Mapping[str, Any], *, job: Mapping[str, Any] | None = None, status: str = "") -> Dict[str, Any]:
    return {
        "jobId": job.get("id") if isinstance(job, Mapping) else "",
        "status": status,
        "topic": payload.get("topic", ""),
        "templateType": payload.get("templateType", ""),
        "reviewMode": payload.get("reviewMode", ""),
        "inspectionMode": payload.get("inspectionMode", ""),
        "writerMode": payload.get("writerMode", ""),
        "briefPreview": payload.get("brief", ""),
        "briefChars": len(str(payload.get("brief", "") or "")),
        "author": payload.get("author", ""),
        "resumeFrom": payload.get("resumeFrom") or payload.get("checkpointPath") or payload.get("draftResumeFrom") or "",
        "rewriteExisting": truthy_payload_value(payload.get("rewriteExisting") or payload.get("recreateExisting")),
    }


def event_payload_for_revision_request(payload: Mapping[str, Any], *, job: Mapping[str, Any] | None = None, status: str = "") -> Dict[str, Any]:
    selection = payload.get("selection") if isinstance(payload.get("selection"), Mapping) else {}
    instruction = str(payload.get("instruction", "") or "")
    return {
        "jobId": job.get("id") if isinstance(job, Mapping) else "",
        "status": status,
        "name": payload.get("name", ""),
        "writerMode": payload.get("writerMode", ""),
        "instructionPreview": instruction,
        "instructionChars": len(instruction),
        "hasSelection": bool(selection),
        "selectionTextPreview": selection.get("text", "") if isinstance(selection, Mapping) else "",
        "selectionTextChars": len(str(selection.get("text", "") if isinstance(selection, Mapping) else "")),
        "selectionSection": selection.get("sectionTitle", "") if isinstance(selection, Mapping) else "",
        "selectionHeadingPath": selection.get("headingPath", "") if isinstance(selection, Mapping) else "",
    }


def refresh_job_heartbeat(job: Dict[str, Any], session_id: str) -> bool:
    expected_session = normalize_client_session_id(job.get("clientSessionId", ""))
    if expected_session and session_id and expected_session != session_id:
        return False
    if expected_session and not session_id:
        return False
    job["_lastClientHeartbeatMono"] = current_time()
    job["lastClientHeartbeatAt"] = datetime.now().isoformat(timespec="seconds")
    update_policy_job_lock(job, str(job.get("status", "") or ""), str(job.get("currentStageKey", "")))
    return True


def client_heartbeat_stale(job: Mapping[str, Any], now: float) -> bool:
    if not normalize_client_session_id(job.get("clientSessionId", "")):
        return False
    status = str(job.get("status", "")).strip().casefold()
    if status not in {"queued", "running", "waiting_review", "review", "retry"}:
        return False
    try:
        last_seen = float(job.get("_lastClientHeartbeatMono") or job.get("_startedMono") or 0)
    except (TypeError, ValueError):
        last_seen = 0
    return bool(last_seen and now - last_seen > CLIENT_HEARTBEAT_TIMEOUT_SECONDS)


def mark_job_client_disconnected(job: Dict[str, Any]) -> None:
    if job.get("cancelRequested"):
        return
    message = (
        "브라우저 연결이 끊겨 정책서 작성을 자동 중단합니다. "
        "현재 LLM 호출이 진행 중이면 호출이 끝난 직후 체크포인트를 보관합니다."
    )
    job["cancelRequested"] = True
    job["status"] = "canceling"
    job["message"] = message
    stage = current_or_active_stage(job)
    if stage:
        stage["status"] = "canceling"
        stage["message"] = message
        job["currentStageKey"] = stage.get("key", "")
    checkpoint = latest_checkpoint_for_job(job)
    if checkpoint:
        job["checkpoint"] = checkpoint
    append_job_activity(
        job,
        {
            "event": "client_heartbeat_lost",
            "stageKey": job.get("currentStageKey", ""),
            "stageLabel": stage.get("label", "") if stage else "브라우저 연결 끊김",
            "status": "canceling",
            "attempt": stage.get("attempt", 0) if stage else 0,
            "score": None,
            "threshold": None,
            "message": message,
            "artifact": None,
            "checkpoint": checkpoint,
            "preview": {
                "title": "브라우저 연결 끊김",
                "items": ["사이트가 닫히거나 네트워크 연결이 끊겨 작업을 자동 중단합니다.", "저장된 체크포인트가 있으면 이어서 작성할 수 있습니다."],
            },
            "createdAt": datetime.now().isoformat(timespec="seconds"),
        },
    )
    update_policy_job_lock(job, "canceling", str(job.get("currentStageKey", "")))


def acquire_document_job_lock(
    file_name: str,
    *,
    job_id: str,
    operation: str,
    session_id: str = "",
) -> Dict[str, str]:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    key = document_lock_key(file_name)
    path = safe_child_path(LOCK_DIR, LOCK_DIR / f"{key}.lock")
    now = datetime.now().isoformat(timespec="seconds")
    data = {
        "lock_key": key,
        "job_id": job_id,
        "operation": operation,
        "file_name": file_name,
        "session_id": normalize_client_session_id(session_id),
        "pid": os.getpid(),
        "status": "queued",
        "current_chapter": "",
        "started_at": now,
        "started_at_epoch": time.time(),
        "updated_at": now,
        "updated_at_epoch": time.time(),
    }
    existing = claim_lock_file(path, data)
    if active_lock(existing):
        raise JobConflict(
            "같은 문서가 다른 작업에서 처리 중입니다. 현재 작업이 끝난 뒤 다시 시도해 주세요.",
            {
                "jobId": existing.get("job_id") or existing.get("jobId"),
                "status": existing.get("status"),
                "operation": existing.get("operation", ""),
                "fileName": existing.get("file_name", file_name),
                "sessionId": existing.get("session_id", ""),
                "updatedAt": existing.get("updated_at") or existing.get("started_at", ""),
            },
        )
    return {"key": key, "path": str(path)}


def document_lock_key(file_name: str) -> str:
    safe_name = re.sub(r"[^\w가-힣.-]+", "_", str(file_name or "").strip(), flags=re.UNICODE).strip("._-") or "policy"
    digest = hashlib.sha1(str(file_name or "").encode("utf-8")).hexdigest()[:10]
    return f"doc_{safe_name[:90]}_{digest}"


def update_document_lock(lock_info: Mapping[str, str], status: str) -> None:
    raw_path = str(lock_info.get("path", "")).strip()
    if not raw_path:
        return
    try:
        path = safe_child_path(LOCK_DIR, Path(raw_path))
        data = read_policy_job_lock(path)
        data.update(
            {
                "status": status,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "updated_at_epoch": time.time(),
            }
        )
        write_policy_job_lock(path, data)
    except (OSError, ValueError):
        return


def ensure_document_not_locked(file_name: str) -> None:
    key = document_lock_key(file_name)
    path = safe_child_path(LOCK_DIR, LOCK_DIR / f"{key}.lock")
    existing = read_policy_job_lock(path)
    if active_lock(existing):
        raise JobConflict(
            "같은 문서가 다른 작업에서 처리 중입니다. 현재 작업이 끝난 뒤 다시 시도해 주세요.",
            {
                "jobId": existing.get("job_id") or existing.get("jobId"),
                "status": existing.get("status"),
                "operation": existing.get("operation", ""),
                "fileName": existing.get("file_name", file_name),
                "sessionId": existing.get("session_id", ""),
                "updatedAt": existing.get("updated_at") or existing.get("started_at", ""),
            },
        )


def start_revision_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    instruction = str(payload.get("instruction", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("수정할 정책서를 선택해 주세요.")
    if not instruction:
        raise ValueError("수정 요청 내용을 입력해 주세요.")
    path = policy_file_path(name)
    if not path.exists() or not path.is_file():
        raise ValueError("수정할 정책서 파일을 찾을 수 없습니다.")
    validate_llm_access_from_payload(payload, normalize_writer_mode_from_payload(payload))

    job_id = uuid.uuid4().hex
    lock_info = acquire_document_job_lock(name, job_id=job_id, operation="revision", session_id=session_id)
    parsed = parse_policy_filename(path.name)
    job = {
        "id": job_id,
        "kind": "revision",
        "status": "queued",
        "topic": parsed["topic"],
        "templateType": "full" if parsed["template_label"] == "Full" else "simple",
        "message": "보완 작업 대기열에 등록되었습니다. 앞선 작업이 없으면 곧바로 시작합니다.",
        "queueLimit": MAX_ACTIVE_POLICY_JOBS,
        "queuedAt": datetime.now().isoformat(timespec="seconds"),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "startedAt": None,
        "finishedAt": None,
        "elapsedMs": 0,
        "_startedMono": None,
        "_startedWall": None,
        "_lastClientHeartbeatMono": current_time() if session_id else None,
        "lastClientHeartbeatAt": datetime.now().isoformat(timespec="seconds") if session_id else "",
        "currentStageKey": "",
        "result": None,
        "error": "",
        "cancelRequested": False,
        "deletedFiles": [],
        "lockKey": lock_info["key"],
        "lockPath": lock_info["path"],
        "clientSessionId": session_id,
        "activity": [],
        "stages": [
            {
                "key": key,
                "name": stage_name,
                "label": label,
                "status": "pending",
                "attempt": 0,
                "score": None,
                "threshold": None,
                "durationMs": 0,
                "message": "",
                "artifact": None,
                "checkpoint": None,
                "preview": None,
                "startedAt": None,
                "finishedAt": None,
                "_startedMono": None,
            }
            for key, stage_name, label in REVISION_STAGE_DEFINITIONS
        ],
    }
    try:
        with JOBS_LOCK:
            JOBS[job_id] = job

        snapshot = public_job(job)
        thread = threading.Thread(target=run_revision_job, args=(job_id, payload), daemon=True)
        thread.start()
        return snapshot
    except Exception:
        update_policy_job_lock(job, "failed", "")
        raise


def request_job_cancel(job_id: str) -> Dict[str, Any]:
    with JOBS_CONDITION:
        job = JOBS.get(job_id)
        if not job:
            raise ValueError("작업을 찾을 수 없습니다.")
        if job.get("status") not in CANCELABLE_JOB_STATUSES:
            return public_job(job)

        message = (
            "사용자 요청으로 정책서 작성을 중단합니다. "
            "검토 대기 중이면 즉시 멈추고, LLM 호출 중이면 현재 호출이 끝난 직후 중간 결과와 체크포인트를 보관합니다."
        )
        job["cancelRequested"] = True
        job["status"] = "canceling"
        job["message"] = message
        job["error"] = ""
        stage = current_or_active_stage(job)
        if stage:
            stage["status"] = "canceling"
            stage["message"] = message
            job["currentStageKey"] = stage.get("key", "")
        update_policy_job_lock(job, "canceling", str(job.get("currentStageKey", "")))
        checkpoint = latest_checkpoint_for_job(job)
        if checkpoint:
            job["checkpoint"] = checkpoint
        append_job_activity(
            job,
            {
                "event": "job_cancel_requested",
                "stageKey": job.get("currentStageKey", ""),
                "stageLabel": stage.get("label", "") if stage else "작업 중단",
                "status": "canceling",
                "attempt": stage.get("attempt", 0) if stage else 0,
                "score": None,
                "threshold": None,
                "message": message,
                "artifact": None,
                "checkpoint": checkpoint,
                "preview": {
                    "title": "작업 중단 요청",
                    "items": ["작성된 중간 HTML과 재개용 체크포인트를 보관합니다.", "좌측 주제 목록에서 이어서 작성할 수 있습니다."],
                },
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )
        snapshot = public_job(job)
        JOBS_CONDITION.notify_all()
        return snapshot


def finish_canceled_job(job_id: str, message: str) -> None:
    with JOBS_CONDITION:
        job = JOBS.get(job_id)
        if not job:
            return
        stage = current_or_active_stage(job)
        if stage:
            close_stage_duration(stage)
            stage["status"] = "canceled"
            stage["message"] = message
            stage["finishedAt"] = datetime.now().isoformat(timespec="seconds")
        job["cancelRequested"] = True
        job["status"] = "canceled"
        job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
        job["elapsedMs"] = elapsed_from_job(job)
        job["message"] = message
        job["error"] = ""
        job["manualReview"] = None
        job["currentStageKey"] = ""
        update_policy_job_lock(job, "aborted", "")
        checkpoint = latest_checkpoint_for_job(job)
        if checkpoint:
            job["checkpoint"] = checkpoint
        append_job_activity(
            job,
            {
                "event": "job_canceled",
                "stageKey": stage.get("key", "") if stage else "",
                "stageLabel": stage.get("label", "") if stage else "작업 중단",
                "status": "canceled",
                "attempt": stage.get("attempt", 0) if stage else 0,
                "score": None,
                "threshold": None,
                "message": message,
                "artifact": None,
                "checkpoint": checkpoint,
                "preview": {
                    "title": "작업 중단 완료",
                    "items": ["현재까지 작성된 중간 결과를 보관했습니다.", "미리보기 화면에서 이어서 작성할 수 있습니다."],
                },
                "createdAt": datetime.now().isoformat(timespec="seconds"),
            },
        )
        write_user_event(
            "job_canceled",
            {
                "jobId": job_id,
                "kind": job.get("kind"),
                "topic": job.get("topic"),
                "templateType": job.get("templateType"),
                "writerMode": job.get("writerMode"),
                "currentStage": stage.get("key", "") if stage else "",
                "message": message,
                "elapsedMs": job.get("elapsedMs"),
                "checkpoint": checkpoint,
            },
            session_id=str(job.get("clientSessionId", "")),
        )
        JOBS_CONDITION.notify_all()


def raise_if_job_cancelled(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job and job.get("cancelRequested"):
            raise JobCancelled("사용자 요청으로 정책서 생성이 중단되었습니다.")


def current_or_active_stage(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current = stage_by_key(job, str(job.get("currentStageKey", "")))
    if current:
        return current
    for status in ("running", "review", "retry", "canceling"):
        for stage in job.get("stages", []):
            if stage.get("status") == status:
                return stage
    return None


def merge_deleted_files(job: Dict[str, Any], deleted: List[str]) -> None:
    if not deleted:
        return
    existing = [str(item) for item in job.get("deletedFiles", []) if str(item).strip()]
    job["deletedFiles"] = sorted(set(existing + deleted))


def cleanup_generated_files_for_job(job: Dict[str, Any], *, preserve_checkpoints: bool = False) -> List[str]:
    exact_paths = collect_artifact_paths(job)
    exact_paths.update(infer_job_output_paths(job))
    if preserve_checkpoints:
        exact_paths = {path for path in exact_paths if not is_checkpoint_path(path)}
    version_stems = collect_version_stems(exact_paths)
    deleted: List[Path] = []

    for path in sorted(exact_paths, key=lambda item: str(item)):
        deleted.extend(delete_file_if_exists(path))

    for stem in sorted(version_stems):
        deleted.extend(delete_file_if_exists(safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / f"{stem}.html")))
        deleted.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*.bpmn"))
        deleted.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*_viewer.html"))
        deleted.extend(delete_matching_files(OUTPUT_ROOT / "steps", f"{stem}_*.html"))
        if not preserve_checkpoints:
            deleted.extend(delete_matching_files(OUTPUT_ROOT / "checkpoints", f"{stem}_*_checkpoint.json"))
        deleted.extend(delete_matching_files(OUTPUT_ROOT / "quality", f"{stem}_quality_report.json"))
        deleted.extend(delete_matching_files(REPORTS_DIR, f"{stem}.html_*_inspection.json"))
        deleted.extend(delete_topic_auxiliary_files_if_orphaned(stem))

    return sorted({project_relative_path(path) for path in deleted})


def is_checkpoint_path(path: Path) -> bool:
    try:
        path.resolve().relative_to((OUTPUT_ROOT / "checkpoints").resolve())
        return True
    except ValueError:
        return False


def infer_job_output_paths(job: Dict[str, Any]) -> set[Path]:
    topic = str(job.get("topic", "")).strip()
    template_type = str(job.get("templateType", "") or "simple").strip() or "simple"
    started_wall = float(job.get("_startedWall") or 0)
    if not topic or not started_wall:
        return set()

    topic_slug = make_topic_slug(topic)
    label = template_file_label(template_type)
    patterns = [
        (OUTPUT_ROOT, f"NC_{topic_slug}_정책서_{label}_v*.html"),
        (OUTPUT_ROOT / "steps", f"NC_{topic_slug}_정책서_{label}_v*_*.html"),
        (OUTPUT_ROOT / "checkpoints", f"NC_{topic_slug}_정책서_{label}_v*_checkpoint.json"),
        (OUTPUT_ROOT / "quality", f"NC_{topic_slug}_정책서_{label}_v*_quality_report.json"),
        (REPORTS_DIR, f"NC_{topic_slug}_정책서_{label}_v*.html_*_inspection.json"),
    ]
    paths: set[Path] = set()
    for root, pattern in patterns:
        if not root.exists():
            continue
        for path in sorted(root.glob(pattern)):
            try:
                safe_path = safe_child_path(root, path)
                if safe_path.is_file() and safe_path.stat().st_mtime >= started_wall - 2:
                    paths.add(safe_path)
            except (OSError, ValueError):
                continue
    return paths


def collect_artifact_paths(value: object) -> set[Path]:
    paths: set[Path] = set()
    if isinstance(value, dict):
        raw_path = value.get("path")
        if isinstance(raw_path, str) and raw_path.strip():
            path = output_path_from_artifact(raw_path)
            if path:
                paths.add(path)
        for child in value.values():
            paths.update(collect_artifact_paths(child))
    elif isinstance(value, list):
        for child in value:
            paths.update(collect_artifact_paths(child))
    return paths


def output_path_from_artifact(raw_path: str) -> Optional[Path]:
    relative = raw_path.strip().lstrip("/")
    if relative.startswith("output/"):
        relative = relative.removeprefix("output/")
    if not relative or relative.startswith(("http://", "https://")):
        return None
    try:
        return safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / unquote(relative))
    except ValueError:
        return None


def collect_version_stems(paths: set[Path]) -> set[str]:
    stems: set[str] = set()
    pattern = re.compile(r"^(NC_.+?_정책서_(?:간소화|Full)_v\d+\.\d+)(?:[_.].*)?$")
    for path in paths:
        match = pattern.match(path.name)
        if match:
            stems.add(match.group(1))
    return stems


def delete_topic_auxiliary_files_if_orphaned(version_stem: str) -> List[Path]:
    try:
        parsed = parse_policy_filename(f"{version_stem}.html")
    except ValueError:
        return []
    topic = parsed["topic"]
    remaining = [
        path
        for path in OUTPUT_ROOT.glob(f"NC_{topic}_정책서_*_v*.html")
        if path.is_file() and path.parent == OUTPUT_ROOT
    ]
    if remaining:
        return []
    deleted: List[Path] = []
    deleted.extend(delete_matching_files(OUTPUT_ROOT, f"NC_{topic}_정책서_*_v*_spec.json"))
    for name in (f"{topic}_policy_spec.json", f"{topic}_authoring_blueprint.json"):
        deleted.extend(delete_file_if_exists(safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / name)))
    return deleted


def delete_file_if_exists(path: Path) -> List[Path]:
    if path.exists() and path.is_file():
        return [delete_file(path)]
    return []


def project_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def requirements_payload_for_topic(topic: str) -> Dict[str, Any]:
    items = load_scoped_requirements_for_topic(topic)
    rows: List[Dict[str, str]] = []
    seen_details: set[str] = set()
    seen_parents: set[str] = set()
    for item in items:
        requirement_id = str(item.requirement_id or "").strip()
        parent_name = str(item.parent_name or "").strip()
        parent_description = str(item.parent_description or "").strip()
        parent_key = requirement_id or f"{parent_name}\n{parent_description}"
        if parent_key:
            seen_parents.add(parent_key)

        detail_id = str(item.detail_id or "").strip()
        detail_name = str(item.detail_name or "").strip()
        detail_description = str(item.detail_description or "").strip()
        if not detail_id and not detail_name and not detail_description:
            continue
        dedupe_key = detail_id or f"{item.source_number}\n{detail_name}\n{detail_description}"
        if dedupe_key in seen_details:
            continue
        seen_details.add(dedupe_key)
        rows.append(
            {
                "requirement_id": requirement_id,
                "requirement_name": detail_name,
                "requirement_description": detail_description,
                "parent_name": parent_name,
                "parent_description": parent_description,
                "detail_id": detail_id,
                "detail_name": detail_name,
                "detail_description": detail_description,
                "requirement_type": str(item.requirement_type or "").strip(),
                "priority": str(item.priority or "").strip(),
                "source": str(item.source or "").strip(),
                "policy_mapping_status": str(item.policy_mapping_status or "").strip(),
            }
        )
    return {
        "topic": topic,
        "columns": [
            "detail_id",
            "detail_name",
            "detail_description",
            "requirement_type",
            "priority",
            "source",
            "policy_mapping_status",
        ],
        "rows": rows,
        "requirementCount": len(seen_parents),
        "detailRequirementCount": len(rows),
    }


def requirements_summary_for_topics(topics: List[str]) -> Dict[str, Any]:
    summaries: List[Dict[str, Any]] = []
    total_requirement_count = 0
    total_detail_requirement_count = 0
    seen_topics: set[str] = set()
    for raw_topic in topics:
        topic = str(raw_topic or "").strip()
        normalized_topic = normalize_topic_key(topic)
        if not topic or normalized_topic in seen_topics:
            continue
        seen_topics.add(normalized_topic)
        payload = requirements_payload_for_topic(topic)
        requirement_count = int(payload.get("requirementCount", 0) or 0)
        detail_requirement_count = int(payload.get("detailRequirementCount", 0) or 0)
        total_requirement_count += requirement_count
        total_detail_requirement_count += detail_requirement_count
        summaries.append(
            {
                "topic": topic,
                "requirementCount": requirement_count,
                "detailRequirementCount": detail_requirement_count,
            }
        )
    return {
        "topics": summaries,
        "requirementCount": total_requirement_count,
        "detailRequirementCount": total_detail_requirement_count,
    }


def wait_for_policy_job_slot(job_id: str, action_label: str) -> bool:
    """Keep accepted jobs queued until a bounded worker slot is available."""
    mark_policy_job_queued(job_id, action_label)
    while True:
        raise_if_job_cancelled(job_id)
        if POLICY_JOB_SEMAPHORE.acquire(timeout=1):
            return True
        mark_policy_job_queued(job_id, action_label)


def mark_policy_job_queued(job_id: str, action_label: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        if job.get("cancelRequested"):
            return
        message = (
            f"동시 작업 수 제한({MAX_ACTIVE_POLICY_JOBS}건)으로 {action_label} 실행 순서를 기다리고 있습니다. "
            "앞선 작업이 끝나면 자동으로 시작합니다."
        )
        job["status"] = "queued"
        job["message"] = message
        job["queueLimit"] = MAX_ACTIVE_POLICY_JOBS
        job["queuedAt"] = job.get("queuedAt") or datetime.now().isoformat(timespec="seconds")
        update_policy_job_lock(job, "queued", str(job.get("currentStageKey", "")))
        if not job.get("_queueNoticeRecorded"):
            append_job_activity(
                job,
                {
                    "event": "job_queued",
                    "stageKey": "",
                    "stageLabel": "작업 대기",
                    "status": "queued",
                    "attempt": 0,
                    "score": None,
                    "threshold": None,
                    "message": message,
                    "artifact": None,
                    "checkpoint": None,
                    "preview": {
                        "title": "큐 대기 중",
                        "items": [
                            f"최대 {MAX_ACTIVE_POLICY_JOBS}건까지만 동시에 실행합니다.",
                            "대기 중에도 작업 중단이 가능합니다.",
                        ],
                    },
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            job["_queueNoticeRecorded"] = True


def mark_policy_job_running(job_id: str, message: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        if job.get("cancelRequested"):
            raise JobCancelled("사용자 요청으로 정책서 생성이 중단되었습니다.")
        job["status"] = "running"
        job["startedAt"] = datetime.now().isoformat(timespec="seconds")
        job["_startedMono"] = current_time()
        job["_startedWall"] = time.time()
        job["message"] = message
        update_policy_job_lock(job, "running", "")
        if not job.get("_queueStartRecorded"):
            append_job_activity(
                job,
                {
                    "event": "job_started_from_queue",
                    "stageKey": "",
                    "stageLabel": "작업 시작",
                    "status": "running",
                    "attempt": 0,
                    "score": None,
                    "threshold": None,
                    "message": message,
                    "artifact": None,
                    "checkpoint": None,
                    "preview": {
                        "title": "큐 실행 시작",
                        "items": ["동시 작업 슬롯을 확보해 실제 Agent 실행을 시작했습니다."],
                    },
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            job["_queueStartRecorded"] = True


def run_policy_job(job_id: str, payload: Dict[str, Any]) -> None:
    slot_acquired = False
    try:
        slot_acquired = wait_for_policy_job_slot(job_id, "정책서 생성")
        mark_policy_job_running(job_id, "정책서 생성을 시작했습니다.")
        raise_if_job_cancelled(job_id)
        args = build_create_args_from_payload(
            payload,
            progress_callback=make_job_progress_callback(job_id),
            manual_review_callback=make_manual_review_callback(job_id),
        )
        result = create_policy(args)
        raise_if_job_cancelled(job_id)
        with JOBS_LOCK:
            job = JOBS[job_id]
            result_item = describe_policy_file(result)
            job["status"] = "completed"
            job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["elapsedMs"] = elapsed_from_job(job)
            job["message"] = "정책서 생성이 완료되었습니다."
            job["result"] = result_item
            job["currentStageKey"] = ""
            update_policy_job_lock(job, "completed", "")
            append_job_activity(
                job,
                {
                    "event": "job_complete",
                    "stageKey": "11",
                    "stageLabel": "최종 검증 및 저장",
                    "status": "completed",
                    "attempt": 0,
                    "score": None,
                    "threshold": None,
                    "message": "최종 정책서 HTML이 저장되었습니다.",
                    "artifact": {"name": result_item["name"], "path": result_item["name"], "url": result_item["url"]},
                    "preview": {"title": "최종 산출물", "items": [result_item["name"]]},
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            write_user_event(
                "policy_create_completed",
                {
                    "jobId": job_id,
                    "topic": job.get("topic"),
                    "templateType": job.get("templateType"),
                    "reviewMode": job.get("reviewMode"),
                    "inspectionMode": job.get("inspectionMode"),
                    "writerMode": job.get("writerMode"),
                    "resultName": result_item.get("name"),
                    "elapsedMs": job.get("elapsedMs"),
                    "activityCount": len(job.get("activity", [])),
                },
                session_id=str(job.get("clientSessionId", "")),
            )
        cleanup = cleanup_stale_intermediate_artifacts()
        if cleanup.get("deletedFiles"):
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                if job:
                    job["intermediateCleanup"] = cleanup
                    append_job_activity(
                        job,
                        {
                            "event": "intermediate_cleanup",
                            "stageKey": "",
                            "stageLabel": "중간 파일 정리",
                            "status": "completed",
                            "attempt": 0,
                            "score": None,
                            "threshold": None,
                            "message": (
                                f"보관 기간이 지난 중간 파일 {len(cleanup['deletedFiles'])}개를 정리했습니다."
                            ),
                            "artifact": None,
                            "checkpoint": None,
                            "preview": {
                                "title": "디스크 정리",
                                "items": [f"{cleanup.get('deletedBytes', 0)} bytes 정리"],
                            },
                            "createdAt": datetime.now().isoformat(timespec="seconds"),
                        },
                    )
            write_user_event(
                "intermediate_cleanup_completed",
                {
                    "jobId": job_id,
                    "topic": payload.get("topic"),
                    "resultName": result.name,
                    "deletedCount": len(cleanup.get("deletedFiles", [])),
                    "deletedBytes": cleanup.get("deletedBytes", 0),
                    "retentionHours": cleanup.get("retentionHours"),
                },
                session_id=client_session_id_from_payload(payload),
            )
    except JobCancelled as exc:
        finish_canceled_job(job_id, str(exc) or "사용자 요청으로 정책서 생성이 중단되었습니다.")
    except Exception as exc:  # pragma: no cover - background job boundary.
        if job_cancel_requested(job_id):
            finish_canceled_job(job_id, "사용자 요청으로 정책서 생성이 중단되었습니다.")
            return
        with JOBS_LOCK:
            job = JOBS[job_id]
            checkpoint = latest_checkpoint_from_payload(payload)
            job["status"] = "error"
            job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["elapsedMs"] = elapsed_from_job(job)
            job["message"] = friendly_job_error_message(str(exc), "정책서 생성 중 오류가 발생했습니다.")
            job["error"] = str(exc)
            if checkpoint:
                job["checkpoint"] = checkpoint
            mark_running_stage_error(job, str(exc))
            update_policy_job_lock(job, "failed", str(job.get("currentStageKey", "")))
            if checkpoint:
                append_job_activity(
                    job,
                    {
                        "event": "checkpoint_available",
                        "stageKey": job.get("currentStageKey", ""),
                        "stageLabel": "체크포인트",
                        "status": "error",
                        "attempt": 0,
                        "score": None,
                        "threshold": None,
                        "message": "중단 전 마지막 완료 장의 체크포인트가 저장되어 있습니다.",
                        "artifact": None,
                        "checkpoint": checkpoint,
                        "preview": {"title": "재개 가능 체크포인트", "items": [checkpoint.get("name", "")]},
                        "createdAt": datetime.now().isoformat(timespec="seconds"),
                    },
                )
            write_user_event(
                "policy_create_error",
                {
                    "jobId": job_id,
                    "topic": job.get("topic"),
                    "templateType": job.get("templateType"),
                    "reviewMode": job.get("reviewMode"),
                    "inspectionMode": job.get("inspectionMode"),
                    "writerMode": job.get("writerMode"),
                    "currentStage": job.get("currentStageKey"),
                    "error": str(exc),
                    "elapsedMs": job.get("elapsedMs"),
                    "checkpoint": checkpoint,
                },
                session_id=str(job.get("clientSessionId", "")),
            )
    finally:
        if slot_acquired:
            POLICY_JOB_SEMAPHORE.release()


def run_revision_job(job_id: str, payload: Dict[str, Any]) -> None:
    slot_acquired = False
    revision_selection = revision_selection_from_payload(payload)
    save_mode = revision_save_mode_from_payload(payload, revision_selection)
    try:
        slot_acquired = wait_for_policy_job_slot(job_id, "정책서 보완")
        mark_policy_job_running(job_id, "수정 요청 처리를 시작했습니다.")
        raise_if_job_cancelled(job_id)
        result = revise_policy_from_payload(
            payload,
            progress_callback=make_job_progress_callback(job_id),
            review_callback=make_manual_review_callback(job_id),
        )
        raise_if_job_cancelled(job_id)
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "completed"
            job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["elapsedMs"] = elapsed_from_job(job)
            job["message"] = revision_save_completed_message(save_mode)
            job["result"] = describe_policy_file(result)
            job["currentStageKey"] = ""
            update_policy_job_lock(job, "completed", "")
            write_user_event(
                "revision_completed",
                {
                    "jobId": job_id,
                    "topic": job.get("topic"),
                    "resultName": job.get("result", {}).get("name") if isinstance(job.get("result"), dict) else "",
                    "elapsedMs": job.get("elapsedMs"),
                    "activityCount": len(job.get("activity", [])),
                },
                session_id=str(job.get("clientSessionId", "")),
            )
    except JobCancelled as exc:
        finish_canceled_job(job_id, str(exc) or "사용자 요청으로 정책서 수정이 중단되었습니다.")
    except RevisionInspectorGateError as exc:
        try:
            pending = persist_revision_candidate(job_id, exc)
        except Exception:
            pending = {}
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "error"
            job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["elapsedMs"] = elapsed_from_job(job)
            job["message"] = str(exc)
            job["error"] = str(exc)
            if pending:
                job["_pendingRevisionSave"] = pending
                job["pendingRevisionSave"] = pending_revision_save_public(pending)
            mark_running_stage_error(job, str(exc))
            update_policy_job_lock(job, "failed", str(job.get("currentStageKey", "")))
            write_user_event(
                "revision_inspector_gate_blocked",
                {
                    "jobId": job_id,
                    "topic": job.get("topic"),
                    "currentStage": job.get("currentStageKey"),
                    "score": exc.score,
                    "threshold": exc.threshold,
                    "canContinue": bool(pending),
                },
                session_id=str(job.get("clientSessionId", "")),
            )
    except Exception as exc:  # pragma: no cover - background job boundary.
        if job_cancel_requested(job_id):
            finish_canceled_job(job_id, "사용자 요청으로 정책서 수정이 중단되었습니다.")
            return
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "error"
            job["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["elapsedMs"] = elapsed_from_job(job)
            job["message"] = friendly_job_error_message(str(exc), "정책서 수정 중 오류가 발생했습니다.")
            job["error"] = str(exc)
            mark_running_stage_error(job, str(exc))
            update_policy_job_lock(job, "failed", str(job.get("currentStageKey", "")))
            write_user_event(
                "revision_error",
                {
                    "jobId": job_id,
                    "topic": job.get("topic"),
                    "currentStage": job.get("currentStageKey"),
                    "error": str(exc),
                    "elapsedMs": job.get("elapsedMs"),
                },
                session_id=str(job.get("clientSessionId", "")),
            )
    finally:
        if slot_acquired:
            POLICY_JOB_SEMAPHORE.release()


def make_job_progress_callback(job_id: str):
    def callback(event: str, payload: Dict[str, Any]) -> None:
        raise_if_job_cancelled(job_id)
        update_job_progress(job_id, event, payload)
        raise_if_job_cancelled(job_id)

    return callback


def job_cancel_requested(job_id: str) -> bool:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return bool(job and job.get("cancelRequested"))


def friendly_job_error_message(error: str, fallback: str) -> str:
    lowered = str(error or "").casefold()
    network_markers = (
        "llm 사전 연결 점검 실패",
        "openai api 연결 실패",
        "응답 대기 시간이 초과",
        "connection",
        "timed out",
        "timeout",
        "nodename nor servname",
        "ssl",
        "network",
        "502",
        "503",
        "504",
    )
    if any(marker in lowered for marker in network_markers):
        return "LLM 연결이 일시적으로 불안정합니다. 저장된 체크포인트를 유지한 뒤 네트워크가 안정되면 이어서 작성해 주세요."
    return fallback


def persist_revision_candidate(job_id: str, exc: RevisionInspectorGateError) -> Dict[str, Any]:
    REVISION_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    candidate_path = REVISION_CANDIDATE_DIR / f"{job_id}.html"
    candidate_path.write_text(exc.revised_html, encoding="utf-8")
    return {
        "candidatePath": str(candidate_path),
        "oldPath": str(exc.old_path),
        "newPath": str(exc.new_path),
        "author": exc.author,
        "changeSummary": exc.change_summary,
        "score": exc.score,
        "threshold": exc.threshold,
        "saveMode": exc.save_mode,
        "available": True,
    }


def pending_revision_save_public(pending: Mapping[str, Any]) -> Dict[str, Any]:
    save_mode = str(pending.get("saveMode") or "new_version")
    return {
        "available": bool(pending.get("available")),
        "score": pending.get("score"),
        "threshold": pending.get("threshold"),
        "newName": Path(str(pending.get("newPath", ""))).name if pending.get("newPath") else "",
        "saveMode": save_mode,
        "saveLabel": revision_save_stage_label(save_mode),
    }


def continue_pending_revision_save(job_id: str) -> Optional[Dict[str, Any]]:
    with JOBS_CONDITION:
        job = JOBS.get(job_id)
        if not job:
            raise ValueError("작업을 찾을 수 없습니다.")
        pending = job.get("_pendingRevisionSave")
        if not (str(job.get("status", "")).casefold() == "error" and isinstance(pending, dict) and pending.get("available")):
            return None
        job["status"] = "running"
        job["message"] = "사용자가 낮은 점수를 확인하고 수정본 저장을 선택했습니다."
        stage = stage_by_key(job, "02")
        if stage:
            stage["status"] = "done"
            stage["message"] = job["message"]
        update_policy_job_lock(job, "running", "03")
        JOBS_CONDITION.notify_all()

    candidate_root = REVISION_CANDIDATE_DIR
    candidate_path = safe_child_path(candidate_root, Path(str(pending.get("candidatePath", ""))))
    old_path = safe_child_path(OUTPUT_ROOT, Path(str(pending.get("oldPath", ""))))
    new_path = safe_child_path(OUTPUT_ROOT, Path(str(pending.get("newPath", ""))))
    save_mode = str(pending.get("saveMode") or "").strip() or ("current_version" if old_path == new_path else "new_version")
    if save_mode not in {"current_version", "new_version"}:
        save_mode = "new_version"
    if not candidate_path.exists():
        raise ValueError("저장할 수정 후보 파일을 찾을 수 없습니다. 다시 수정 요청을 실행해 주세요.")
    next_version = parse_policy_filename(new_path.name)["version"]
    author = str(pending.get("author", "") or "Policy Web")
    change_summary = str(pending.get("changeSummary", "") or "Inspector 기준 미달 수정본 사용자 확인 후 저장").strip()
    revised_html = candidate_path.read_text(encoding="utf-8")
    revised_html = sanitize_policy_html(update_document_version_and_history(revised_html, old_path.name, next_version, author, change_summary))

    with JOBS_CONDITION:
        job = JOBS.get(job_id)
        if not job:
            raise ValueError("작업을 찾을 수 없습니다.")
        job["currentStageKey"] = "03"
        job["message"] = "문서 히스토리를 업데이트하고 있습니다."
        stage = stage_by_key(job, "03")
        if stage:
            stage["status"] = "running"
            stage["message"] = job["message"]
        JOBS_CONDITION.notify_all()

    if save_mode == "current_version":
        backup_policy_html_before_overwrite(new_path, reason="agent_revision_current_version")
    new_path.write_text(revised_html, encoding="utf-8")
    sync_policy_version_spec_from_base(old_path, new_path, author=author, reason=f"agent_revision_{save_mode}")
    try:
        candidate_path.unlink()
    except OSError:
        pass

    with JOBS_CONDITION:
        job = JOBS.get(job_id)
        if not job:
            raise ValueError("작업을 찾을 수 없습니다.")
        now = datetime.now().isoformat(timespec="seconds")
        history_stage = stage_by_key(job, "03")
        if history_stage:
            history_stage["status"] = "done"
            history_stage["message"] = "문서 히스토리를 업데이트했습니다."
            history_stage["finishedAt"] = now
            history_stage["preview"] = {"title": "문서 히스토리", "items": [f"{next_version}: {change_summary}"]}
            record_job_activity(job, history_stage, "stage_complete", {"preview": history_stage["preview"]}, history_stage["message"])
        save_stage = stage_by_key(job, "04")
        artifact = output_artifact_payload(new_path)
        if save_stage:
            save_stage["status"] = "done"
            save_stage["label"] = revision_save_stage_label(save_mode)
            save_stage["message"] = "현재 버전에 반영했습니다." if save_mode == "current_version" else "새 버전을 저장했습니다."
            save_stage["finishedAt"] = now
            save_stage["artifact"] = artifact
            save_stage["preview"] = {"title": revision_save_preview_title(save_mode), "items": [new_path.name]}
            record_job_activity(job, save_stage, "stage_complete", {"artifact": artifact, "preview": save_stage["preview"]}, save_stage["message"])
        job["status"] = "completed"
        job["finishedAt"] = now
        job["elapsedMs"] = elapsed_from_job(job)
        job["message"] = revision_save_completed_message(save_mode, forced=True)
        job["result"] = describe_policy_file(new_path)
        job["currentStageKey"] = ""
        job.pop("_pendingRevisionSave", None)
        job.pop("pendingRevisionSave", None)
        update_policy_job_lock(job, "completed", "")
        write_user_event(
            "revision_forced_continue_saved",
            {
                "jobId": job_id,
                "topic": job.get("topic"),
                "resultName": new_path.name,
                "score": pending.get("score"),
                "threshold": pending.get("threshold"),
            },
            session_id=str(job.get("clientSessionId", "")),
        )
        snapshot = public_job(job)
        JOBS_CONDITION.notify_all()
    return snapshot


def make_manual_review_callback(job_id: str):
    def callback(payload: Dict[str, Any]) -> Dict[str, Any]:
        stage_key = str(payload.get("stage_key", ""))
        stage_label = str(payload.get("stage_label", "") or payload.get("stage_name", ""))
        review = {
            "id": uuid.uuid4().hex,
            "reviewType": str(payload.get("review_type", "") or "manual_chapter_review"),
            "stageKey": stage_key,
            "stageName": str(payload.get("stage_name", "")),
            "stageLabel": stage_label,
            "attempt": payload.get("attempt"),
            "score": payload.get("score"),
            "threshold": payload.get("threshold"),
            "passed": bool(payload.get("passed", True)),
            "artifact": payload.get("artifact"),
            "preview": payload.get("preview"),
            "message": str(
                payload.get("message")
                or "결과 HTML을 확인한 뒤 다음 단계 진행 또는 보완 요청을 선택해 주세요."
            ),
            "requestedAt": datetime.now().isoformat(timespec="seconds"),
            "response": None,
        }
        with JOBS_CONDITION:
            job = JOBS.get(job_id)
            if not job:
                return {"action": "continue"}
            if job.get("cancelRequested"):
                raise JobCancelled("사용자 요청으로 정책서 생성이 중단되었습니다.")
            stage = stage_by_key(job, stage_key)
            if stage:
                stage["status"] = "review"
                stage["message"] = review["message"]
                apply_stage_payload(stage, {"artifact": review.get("artifact"), "preview": review.get("preview")})
            job["status"] = "waiting_review"
            job["manualReview"] = review
            job["currentStageKey"] = stage_key
            job["message"] = review["message"]
            append_job_activity(
                job,
                {
                    "event": "stage_review",
                    "stageKey": stage_key,
                    "stageLabel": stage_label,
                    "status": "review",
                    "attempt": review.get("attempt"),
                    "score": review.get("score"),
                    "threshold": review.get("threshold"),
                    "message": review["message"],
                    "artifact": review.get("artifact"),
                    "preview": review.get("preview"),
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                },
            )
            JOBS_CONDITION.notify_all()
            while True:
                current = JOBS.get(job_id)
                if not current:
                    return {"action": "continue"}
                if current.get("cancelRequested"):
                    current["manualReview"] = None
                    raise JobCancelled("사용자 요청으로 정책서 생성이 중단되었습니다.")
                active_review = current.get("manualReview")
                if isinstance(active_review, dict) and active_review.get("response"):
                    response = dict(active_review["response"])
                    current["manualReview"] = None
                    current["status"] = "running"
                    response_action = str(response.get("action", "")).casefold()
                    if response_action == "stop":
                        current["message"] = "사용자가 수정본 저장을 중단했습니다."
                    elif response_action == "revise":
                        current["message"] = "사용자 보완 요청을 반영합니다."
                    else:
                        current["message"] = "사용자 검수가 완료되어 다음 단계로 진행합니다."
                    if stage:
                        stage["status"] = "error" if response_action == "stop" else "retry" if response_action == "revise" else "done"
                        stage["message"] = current["message"]
                    append_job_activity(
                        current,
                        {
                            "event": "stage_review_response",
                            "stageKey": stage_key,
                            "stageLabel": stage_label,
                            "status": stage["status"] if stage else "running",
                            "attempt": review.get("attempt"),
                            "score": review.get("score"),
                            "threshold": review.get("threshold"),
                            "message": current["message"],
                            "artifact": review.get("artifact"),
                            "preview": review.get("preview"),
                            "createdAt": datetime.now().isoformat(timespec="seconds"),
                        },
                    )
                    JOBS_CONDITION.notify_all()
                    return response
                update_policy_job_lock(current, "waiting_review", stage_key)
                JOBS_CONDITION.wait(timeout=60)

    return callback


def update_job_progress(job_id: str, event: str, payload: Dict[str, Any]) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["elapsedMs"] = elapsed_from_job(job)
        stage = stage_by_key(job, str(payload.get("stage_key", "")))
        if not stage:
            return

        message = str(payload.get("message", "") or stage.get("message", ""))
        if event == "stage_start":
            if stage["status"] == "running":
                return
            stage["status"] = "running"
            stage["attempt"] = int(payload.get("attempt") or stage.get("attempt") or 1)
            stage["message"] = message
            stage["startedAt"] = datetime.now().isoformat(timespec="seconds")
            stage["_startedMono"] = current_time()
            job["currentStageKey"] = stage["key"]
            job["message"] = message
            record_job_activity(job, stage, event, payload, message)
            return

        if event == "stage_update":
            stage["message"] = message
            apply_stage_payload(stage, payload)
            job["currentStageKey"] = stage["key"]
            job["message"] = message
            record_job_activity(job, stage, event, payload, message)
            return

        if event == "stage_retry":
            close_stage_duration(stage)
            stage["status"] = "retry"
            stage["attempt"] = int(payload.get("attempt") or stage.get("attempt") or 1)
            stage["score"] = payload.get("score")
            stage["threshold"] = payload.get("threshold")
            stage["message"] = message
            apply_stage_payload(stage, payload)
            job["currentStageKey"] = stage["key"]
            job["message"] = message
            record_job_activity(job, stage, event, payload, message)
            return

        if event == "stage_complete":
            close_stage_duration(stage)
            stage["status"] = "done"
            stage["attempt"] = int(payload.get("attempt") or stage.get("attempt") or 1)
            stage["score"] = payload.get("score")
            stage["threshold"] = payload.get("threshold")
            stage["message"] = message or "완료되었습니다."
            apply_stage_payload(stage, payload)
            stage["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["message"] = stage["message"]
            job["currentStageKey"] = ""
            record_job_activity(job, stage, event, payload, stage["message"])
            return

        if event == "stage_error":
            close_stage_duration(stage)
            stage["status"] = "error"
            stage["message"] = str(payload.get("error") or message or "오류가 발생했습니다.")
            stage["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            job["status"] = "error"
            job["message"] = stage["message"]
            job["currentStageKey"] = stage["key"]
            record_job_activity(job, stage, event, payload, stage["message"])


def apply_stage_payload(stage: Dict[str, Any], payload: Dict[str, Any]) -> None:
    if payload.get("artifact") is not None:
        stage["artifact"] = payload.get("artifact")
    if payload.get("checkpoint") is not None:
        stage["checkpoint"] = payload.get("checkpoint")
    if payload.get("preview") is not None:
        stage["preview"] = payload.get("preview")


def record_job_activity(job: Dict[str, Any], stage: Dict[str, Any], event: str, payload: Dict[str, Any], message: str) -> None:
    entry = {
        "event": event,
        "stageKey": stage.get("key", ""),
        "stageLabel": stage.get("label", ""),
        "status": stage.get("status", ""),
        "attempt": stage.get("attempt", 0),
        "score": stage.get("score"),
        "threshold": stage.get("threshold"),
        "message": message,
        "artifact": stage.get("artifact"),
        "checkpoint": stage.get("checkpoint"),
        "preview": stage.get("preview"),
        "createdAt": datetime.now().isoformat(timespec="seconds"),
    }
    append_job_activity(job, entry)


def append_job_activity(job: Dict[str, Any], entry: Dict[str, Any]) -> None:
    activity = job.setdefault("activity", [])
    activity.append(entry)
    del activity[:-30]
    update_policy_job_lock(job, str(job.get("status", "") or ""), str(job.get("currentStageKey", "") or entry.get("stageKey", "")))


def build_create_args_from_payload(payload: Dict[str, Any], progress_callback=None, manual_review_callback=None) -> Namespace:
    topic = str(payload.get("topic", "")).strip()
    template_type = str(payload.get("templateType", "")).strip()
    review_mode = str(payload.get("reviewMode", "auto")).strip().casefold() or "auto"
    inspection_mode = str(payload.get("inspectionMode", "chapter-final")).strip().casefold() or "chapter-final"
    writer_mode = normalize_writer_mode_from_payload(payload)
    author = str(payload.get("author", "")).strip() or "Policy Web"
    status = str(payload.get("status", "")).strip() or "작성중"
    brief = str(payload.get("brief", "")).strip()
    if not brief:
        scope_definition = runtime_topic_scope_definition(topic)
        if scope_definition:
            brief = str(scope_definition.get("brief") or "").strip()
    resume_from = str(payload.get("resumeFrom", "")).strip()

    if not topic:
        raise ValueError("정책서 주제를 입력해 주세요.")
    if template_type not in {"simple", "full"}:
        raise ValueError("Full 버전 또는 간소화 버전을 선택해 주세요.")
    if review_mode not in {"auto", "manual"}:
        raise ValueError("진행 방식은 자동모드 또는 수동모드 중 하나여야 합니다.")
    if inspection_mode in {"chapter_final", "chapter", "all", "auto"}:
        inspection_mode = "chapter-final"
    elif inspection_mode in {"final_only", "final"}:
        inspection_mode = "final-only"
    elif inspection_mode not in {"chapter-final", "final-only", "none"}:
        raise ValueError("검수 방식은 장별+최종 검수, 최종 검수만, 검수 생략 중 하나여야 합니다.")
    if resume_from:
        resume_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / resume_from)
        if not resume_path.exists() or not resume_path.is_file():
            raise ValueError("재개할 체크포인트 파일을 찾을 수 없습니다.")
        resume_from = str(resume_path)

    args = Namespace(
        command="create",
        topic=topic,
        template="input/templates",
        template_type=template_type,
        review_mode=review_mode,
        inspection_mode=inspection_mode,
        output_dir=str(OUTPUT_ROOT),
        author=author,
        status=status,
        brief=brief,
        requirements_dir="input/requirements",
        no_requirements=False,
        references_dir="input/references",
        no_references=False,
        no_steps=False,
        no_inspect=inspection_mode == "none",
        inspector_min_score=DEFAULT_INSPECTOR_MIN_SCORE,
        inspector_max_loops=3,
        writer_mode=writer_mode,
        model="",
        reasoning_effort="",
        resume_from=resume_from,
        progress_callback=progress_callback,
        manual_review_callback=manual_review_callback,
    )
    return args


def normalize_writer_mode_from_payload(payload: Mapping[str, Any]) -> str:
    if isinstance(payload.get("llmEnabled"), bool):
        return "llm" if payload.get("llmEnabled") else "mock"
    raw_mode = str(payload.get("writerMode", payload.get("llmMode", "mock")) or "mock").strip().casefold()
    if raw_mode in {"llm", "real", "use", "used", "enabled", "on", "true", "1", "yes", "y", "사용"}:
        return "llm"
    if raw_mode in {
        "mock",
        "test",
        "mock-test",
        "mock_test",
        "unused",
        "disabled",
        "disable",
        "off",
        "false",
        "0",
        "no",
        "n",
        "api-free",
        "미사용",
    }:
        return "mock"
    raise ValueError("LLM 사용 여부는 사용 또는 미사용 중 하나여야 합니다.")


def validate_llm_access_from_payload(
    payload: Mapping[str, Any],
    writer_mode: str,
    *,
    allow_site_setting: bool = True,
) -> None:
    if writer_mode != "llm":
        return
    token = str(payload.get("llmAccessToken", "")).strip()
    if token == LLM_ACCESS_TOKEN_VALUE:
        return
    if allow_site_setting and truthy_payload_value(payload.get("useSiteWriterMode")) and site_llm_mode_enabled():
        return
    raise ValueError("LLM 사용 권한이 확인되지 않았습니다. 인증키를 다시 입력해 주세요.")


def llm_client_from_web_payload(payload: Mapping[str, Any]) -> LLMClient:
    writer_mode = normalize_writer_mode_from_payload(payload)
    validate_llm_access_from_payload(payload, writer_mode)
    return LLMClient.from_context(
        Namespace(
            writer_mode=writer_mode,
            llm_model="",
            reasoning_effort="",
            disable_mock_env=writer_mode == "llm",
        )
    )


def optional_hybrid_llm_client_from_payload(payload: Mapping[str, Any], route_key: str) -> Tuple[Optional[LLMClient], str]:
    """Return a routed LLM client for hybrid evaluators, or a fallback reason."""
    writer_mode = normalize_writer_mode_from_payload(payload)
    if writer_mode != "llm":
        return None, ""
    base_client = llm_client_from_web_payload(payload)
    if not base_client.enabled:
        return None, ""
    try:
        if llm_preflight_enabled():
            base_client.preflight_check()
        return client_for_route(base_client, route_key), ""
    except Exception as exc:
        return None, str(exc)


def live_feedback_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    writer_mode = normalize_writer_mode_from_payload(payload)
    if writer_mode != "llm":
        return {"usedLlm": False, "message": "", "tone": "info"}

    base_client = llm_client_from_web_payload(payload)
    if not base_client.enabled:
        return {"usedLlm": False, "message": "", "tone": "info"}

    event = payload.get("event")
    if not isinstance(event, Mapping):
        raise ValueError("Live feedback 이벤트 정보가 올바르지 않습니다.")

    client = client_for_route(base_client, "live_feedback")
    result = client.generate_json(
        schema_name="live_feedback",
        schema=live_feedback_schema(),
        instructions=live_feedback_instructions(),
        input_messages=[
            {
                "role": "user",
                "content": json.dumps(normalize_live_feedback_event(event), ensure_ascii=False, sort_keys=True),
            }
        ],
    )
    message = re.sub(r"\s+", " ", str(result.get("message") or "")).strip()
    tone = str(result.get("tone") or "info").strip().casefold()
    if tone not in {"info", "done", "warn", "review"}:
        tone = "info"
    if not message:
        return {"usedLlm": False, "message": "", "tone": tone}
    return {
        "usedLlm": True,
        "message": limit_text(message, 180),
        "tone": tone,
        "model": client.model,
        "reasoningEffort": client.reasoning_effort,
    }


def live_feedback_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "message": {"type": "string"},
            "tone": {"type": "string", "enum": ["info", "done", "warn", "review"]},
        },
        "required": ["message", "tone"],
    }


def live_feedback_instructions() -> str:
    return "\n".join(
        [
            "너는 NOVA 문서 작성 진행 상황을 사용자가 안심하고 이해하도록 돕는 진행 코멘트 작성자다.",
            "입력된 이벤트 정보만 사용한다. 없는 사실, 점수, 완료 여부, 품질 판단을 만들지 않는다.",
            "한국어 한 문장으로 작성한다. 80자 안팎으로 짧고 자연스럽게 쓴다.",
            "토큰, API, 인증키, 내부 구현명은 언급하지 않는다.",
            "오류나 검수 대기 상황은 차분하게 다음 행동을 안내한다.",
            "반드시 JSON으로만 응답한다.",
        ]
    )


def normalize_live_feedback_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    current_stage = event.get("currentStage") if isinstance(event.get("currentStage"), Mapping) else {}
    recent_activity = event.get("recentActivity") if isinstance(event.get("recentActivity"), list) else []
    local_messages = event.get("localMessages") if isinstance(event.get("localMessages"), list) else []
    return {
        "eventType": limit_text(str(event.get("eventType") or ""), 40),
        "topic": limit_text(str(event.get("topic") or ""), 80),
        "status": limit_text(str(event.get("status") or ""), 40),
        "progress": bounded_int(event.get("progress"), default=0, minimum=0, maximum=100),
        "currentStage": {
            "key": limit_text(str(current_stage.get("key") or ""), 40),
            "label": limit_text(str(current_stage.get("label") or ""), 80),
            "status": limit_text(str(current_stage.get("status") or ""), 40),
            "score": current_stage.get("score") if isinstance(current_stage.get("score"), (int, float, str)) else "",
            "attempt": bounded_int(current_stage.get("attempt"), default=0, minimum=0, maximum=20),
            "message": limit_text(str(current_stage.get("message") or ""), 180),
        },
        "artifactCount": bounded_int(event.get("artifactCount"), default=0, minimum=0, maximum=999),
        "localMessages": [limit_text(str(item), 180) for item in local_messages[:3]],
        "recentActivity": [limit_text(str(item), 160) for item in recent_activity[-3:]],
    }


def bounded_int(value: Any, *, default: int = 0, minimum: int = 0, maximum: int = 100) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def create_policy_from_payload(payload: Dict[str, Any]) -> Path:
    args = build_create_args_from_payload(payload)
    validate_llm_access_from_payload(payload, args.writer_mode)
    return create_policy(args)


def dev_qa_review_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("검수할 정책서를 선택해 주세요.")
    path = policy_file_path(name)
    if not path.exists() or not path.is_file():
        raise ValueError("개발/QA 검수 대상 파일을 찾을 수 없습니다.")

    document = path.read_text(encoding="utf-8")
    parsed = parse_policy_filename(path.name)
    template_type = "full" if parsed["template_label"] == "Full" else "simple"
    signals = extract_dev_qa_signals(document)
    document_text = limit_text(visible_text(document), 70000)

    base_client = llm_client_from_web_payload(payload)
    if llm_preflight_enabled() and base_client.enabled:
        base_client.preflight_check()
    client = client_for_route(base_client, "dev_qa_review")
    report = client.generate_json(
        schema_name="dev_qa_review",
        schema=dev_qa_review_schema(),
        instructions=dev_qa_review_instructions(parsed["topic"], template_type),
        input_messages=[
            {
                "role": "user",
                "content": dev_qa_review_prompt(
                    file_name=path.name,
                    topic=parsed["topic"],
                    template_type=template_type,
                    document_text=document_text,
                    signals=signals,
                ),
            }
        ],
    )
    normalized = normalize_dev_qa_review(report)
    normalized["fileName"] = path.name
    normalized["topic"] = parsed["topic"]
    normalized["templateType"] = template_type
    normalized["clientSessionId"] = session_id
    normalized["signals"] = signals
    save_dev_qa_review_report(normalized, reports_dir=REPORTS_DIR, file_name=path.name)
    return normalized


def dev_qa_action_check_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    items = payload.get("items")
    if not name:
        raise ValueError("보완 여부를 확인할 정책서를 선택해 주세요.")
    if not isinstance(items, list) or not items:
        raise ValueError("확인할 보완 요청 항목을 선택해 주세요.")
    path = policy_file_path(name)
    if not path.exists() or not path.is_file():
        raise ValueError("보완 여부 확인 대상 파일을 찾을 수 없습니다.")

    document = path.read_text(encoding="utf-8")
    parsed = parse_policy_filename(path.name)
    document_text = limit_text(visible_text(document), 70000)
    check_items = normalize_dev_qa_action_check_items(items)
    base_client = llm_client_from_web_payload(payload)
    if llm_preflight_enabled() and base_client.enabled:
        base_client.preflight_check()
    client = client_for_route(base_client, "dev_qa_review")
    report = client.generate_json(
        schema_name="dev_qa_action_check",
        schema=dev_qa_action_check_schema(),
        instructions=dev_qa_action_check_instructions(parsed["topic"]),
        input_messages=[
            {
                "role": "user",
                "content": dev_qa_action_check_prompt(
                    file_name=path.name,
                    items=check_items,
                    document_text=document_text,
                ),
            }
        ],
    )
    normalized = normalize_dev_qa_action_check(report)
    normalized["fileName"] = path.name
    return normalized


def health_check_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    session_id = client_session_id_from_payload(payload)
    path, topic, template_type, file_name = resolve_health_check_target(payload)

    document = path.read_text(encoding="utf-8")
    recheck_item_ids = normalize_recheck_item_ids_from_payload(payload)
    previous_report = payload.get("previousReport") if isinstance(payload.get("previousReport"), Mapping) else None
    if recheck_item_ids and previous_report is None:
        previous_report = load_health_check_report(file_name)
    use_llm_health_check = truthy_payload_value(payload.get("healthCheckUseLlm")) or str(
        payload.get("healthCheckMode", "")
    ).strip().casefold() in {"llm", "ai", "hybrid"}
    client_payload = dict(payload)
    if not use_llm_health_check:
        # Health Check is a quick scorecard by default. It should not inherit the
        # global LLM authoring toggle and accidentally become a long-running API
        # call from the document workspace.
        client_payload["writerMode"] = "mock"
        client_payload["llmAccessToken"] = ""

    base_client = llm_client_from_web_payload(client_payload)
    client = base_client
    health_check_llm_error = ""
    if base_client.enabled and base_client.writer_mode != "mock":
        try:
            if llm_preflight_enabled():
                base_client.preflight_check()
            client = client_for_route(base_client, "health_check")
        except Exception as exc:
            # Health Check must remain available as a code-based scorecard even
            # when the optional LLM scoring path is temporarily unavailable.
            client = None
            health_check_llm_error = str(exc)
    else:
        client = client_for_route(base_client, "health_check")
    report = evaluate_health_check(
        document=document,
        file_name=file_name,
        topic=topic,
        template_type=template_type,
        llm_client=client,
        recheck_item_ids=recheck_item_ids,
        previous_report=previous_report,
    )
    if health_check_llm_error and not report.get("llmError"):
        report["llmError"] = health_check_llm_error
        report["summary"] = (
            f"{report.get('summary', '')} LLM 기반 보조 평가는 일시적으로 건너뛰고 코드 기반 Health Check로 완료했습니다."
        ).strip()
    drift = (
        evaluate_policy_artifact_drift(path, output_root=OUTPUT_ROOT, reports_root=RUNTIME_REPORTS_ROOT)
        if re_match_policy_filename(path.name)
        else skipped_artifact_drift(path)
    )
    attach_artifact_drift(report, drift)
    report["remediationPlan"] = build_health_remediation_plan(
        sections=report.get("sections", []) if isinstance(report.get("sections", []), list) else [],
        gates=report.get("mandatoryGates", []) if isinstance(report.get("mandatoryGates", []), list) else [],
        action_items=report.get("actionItems", []) if isinstance(report.get("actionItems", []), list) else [],
        previous_report=previous_report,
        recheck_item_ids=recheck_item_ids,
        artifact_drift=report.get("artifactDrift") if isinstance(report.get("artifactDrift"), Mapping) else None,
    )
    report["versionTrend"] = build_health_check_version_trend(path, current_report=report)
    report["clientSessionId"] = session_id
    save_health_check_report(report, reports_dir=REPORTS_DIR, file_name=file_name)
    return report


def normalize_recheck_item_ids_from_payload(payload: Mapping[str, Any]) -> List[str]:
    raw = payload.get("recheckItemIds") or payload.get("recheck_item_ids") or []
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    if not isinstance(raw, list):
        return []
    result: List[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return result[:50]


def attach_artifact_drift(report: Dict[str, Any], drift: Mapping[str, Any]) -> None:
    report["artifactDrift"] = dict(drift)
    report["artifactDriftGatePassed"] = bool(drift.get("passed"))
    if drift.get("status") == "pass":
        return
    blockers = list(report.get("blockers", [])) if isinstance(report.get("blockers", []), list) else []
    if drift.get("status") == "fail":
        blockers.append(
            {
                "id": "ARTIFACT-DRIFT",
                "type": "artifact_drift",
                "severity": "P1",
                "message": str(drift.get("summary", "산출물 동기화 오류가 있습니다.")),
            }
        )
        report["resultBlocked"] = True
    report["blockers"] = blockers
    action_items = list(report.get("actionItems", [])) if isinstance(report.get("actionItems", []), list) else []
    for issue in drift.get("issues", []) if isinstance(drift.get("issues", []), list) else []:
        if not isinstance(issue, Mapping):
            continue
        action_items.append(
            {
                "itemId": str(issue.get("id", "")),
                "section": "산출물 동기화",
                "priority": str(issue.get("severity", "P2")),
                "title": str(issue.get("detail", "산출물 동기화 확인 필요")),
                "targetLocation": str(issue.get("target", "HTML/spec/BPMN/Trace")),
                "evidence": str(issue.get("detail", "")),
                "suggestion": str(issue.get("recommendation", "")),
                "score": 0 if issue.get("severity") == "P1" else 1,
            }
        )
    report["actionItems"] = sorted(action_items, key=lambda item: {"P1": 0, "P2": 1, "P3": 2}.get(str(item.get("priority", "P3")), 3))[:24]
    report["summary"] = f"{report.get('summary', '')} {drift.get('summary', '')}".strip()


def skipped_artifact_drift(path: Path) -> Dict[str, Any]:
    return {
        "agent": "Artifact Drift Check",
        "version": "1.0",
        "status": "skipped",
        "passed": True,
        "summary": "작성 중 미리보기 문서는 HTML/spec/BPMN/Trace 동기화 Gate를 완료본 저장 후 적용합니다.",
        "policyFile": path.name,
        "checks": [],
        "issues": [],
    }


def repair_policy_artifact_sync_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("산출물 동기화 복구 대상 정책서를 선택해 주세요.")
    path = policy_file_path(name)
    if not path.exists() or not path.is_file():
        raise ValueError("산출물 동기화 복구 대상 파일을 찾을 수 없습니다.")
    ensure_policy_editable(path)
    lock_info = acquire_document_job_lock(path.name, job_id=uuid.uuid4().hex, operation="artifact_sync_repair", session_id=session_id)
    try:
        result = repair_policy_artifact_sync(path, author=author)
        update_document_lock(lock_info, "completed")
        return result
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def repair_policy_artifact_sync(policy_path: Path, *, author: str = "Policy Web") -> Dict[str, Any]:
    """Regenerate policy sidecar artifacts from the current spec."""

    before = evaluate_policy_artifact_drift(policy_path, output_root=OUTPUT_ROOT, reports_root=RUNTIME_REPORTS_ROOT)
    spec, source_path = load_policy_spec_for_policy_path(policy_path)
    if spec is None:
        synced_path = sync_policy_version_spec_from_base(policy_path, policy_path, author=author, reason="artifact_sync_repair")
        spec, source_path = load_policy_spec_for_policy_path(policy_path)
        if spec is None:
            raise ValueError("복구에 사용할 JSON spec을 찾지 못했습니다. 정책서 JSON 또는 최신 spec을 먼저 등록해 주세요.")
        if synced_path:
            source_path = synced_path
    html_runtime_source_before_repair = policy_html_is_runtime_source(policy_path, spec)

    repaired: List[Dict[str, str]] = []
    parsed = parse_policy_filename(policy_path.name)
    topic_slug = str(parsed.get("topic", "") or "").strip()
    version = str(parsed.get("version", "") or "").strip()
    template_type = "full" if parsed.get("template_label") == "Full" else "simple"
    spec = prepare_policy_spec_for_artifact_sync_repair(
        dict(spec),
        target_path=policy_path,
        topic_slug=topic_slug,
        version=version,
        template_type=template_type,
        author=author,
        source_path=source_path,
    )
    if html_runtime_source_before_repair:
        meta = spec.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["html_runtime_source"] = True
            meta.setdefault("html_runtime_source_reason", "runtime_html_preserved")
    html_runtime_source = html_runtime_source_before_repair or policy_html_is_runtime_source(policy_path, spec)

    issue_ids = {
        str(issue.get("id", "") or "")
        for issue in before.get("issues", [])
        if isinstance(issue, Mapping)
    }
    should_rerender_html = (
        not policy_html_has_bpmn_io_viewer(policy_path)
        or any(issue_id.startswith("DRIFT-HTML-SPEC-ID") for issue_id in issue_ids)
        or "DRIFT-SPEC-VERSION" in issue_ids
        or "DRIFT-SPEC-TOPIC" in issue_ids
    )
    if should_rerender_html and html_runtime_source:
        spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
        version_spec_path = policy_version_spec_path(policy_path)
        version_spec_path.write_text(spec_json, encoding="utf-8")
        repaired.append({"type": "html_preserved", "path": project_relative_path(policy_path)})
        repaired.append({"type": "spec", "path": project_relative_path(version_spec_path)})
    elif should_rerender_html:
        backup_path = backup_policy_html_before_overwrite(policy_path, reason="artifact_sync_repair")
        write_policy_document_from_spec(spec, policy_path)
        repaired.append({"type": "html", "path": project_relative_path(policy_path)})
        if backup_path:
            repaired.append({"type": "html_backup", "path": project_relative_path(backup_path)})
    else:
        spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
        version_spec_path = policy_version_spec_path(policy_path)
        version_spec_path.write_text(spec_json, encoding="utf-8")
        repaired.append({"type": "spec", "path": project_relative_path(version_spec_path)})
        topic_spec_path = topic_policy_spec_path(topic_slug) if topic_slug and topic_slug != "-" else None
        latest = latest_policy_for_topic(topic_slug, template_type) if topic_slug and topic_slug != "-" else None
        if topic_spec_path and (latest is None or latest.resolve() == policy_path.resolve() or not topic_spec_path.exists()):
            topic_spec_path.write_text(spec_json, encoding="utf-8")
            repaired.append({"type": "topic_spec", "path": project_relative_path(topic_spec_path)})

    bpmn_path = policy_path.with_name(f"{policy_path.stem}_전체업무흐름도.bpmn")
    artifacts = write_bpmn_artifacts(spec, bpmn_path)
    repaired.append({"type": "bpmn", "path": project_relative_path(artifacts.bpmn)})
    repaired.append({"type": "bpmn_viewer", "path": project_relative_path(artifacts.viewer)})

    trace_result = write_requirement_trace_report_for_policy(topic_slug, spec, policy_version_spec_path(policy_path))
    if trace_result:
        repaired.append(trace_result)

    after = evaluate_policy_artifact_drift(policy_path, output_root=OUTPUT_ROOT, reports_root=RUNTIME_REPORTS_ROOT)
    return {
        "name": policy_path.name,
        "item": describe_policy_file(policy_path),
        "before": before,
        "after": after,
        "repaired": repaired,
        "htmlRuntimeSource": html_runtime_source,
        "summary": f"산출물 동기화 복구를 완료했습니다. {before.get('status', '-')} → {after.get('status', '-')}",
    }


def prepare_policy_spec_for_artifact_sync_repair(
    spec: Dict[str, Any],
    *,
    target_path: Path,
    topic_slug: str,
    version: str,
    template_type: str,
    author: str,
    source_path: Optional[Path],
) -> Dict[str, Any]:
    ensure_policy_spec_base_keys(spec)
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["topic"] = topic_slug
        meta["topic_slug"] = topic_slug
        meta["version"] = version
        meta["template_type"] = template_type
        meta["document_type"] = "Full 버전" if template_type == "full" else "간소화 버전"
        meta["version_spec_file"] = policy_version_spec_path(target_path).name
        meta["version_spec_saved_at"] = datetime.now().isoformat(timespec="seconds")
        meta["version_spec_saved_by"] = author
        meta["version_spec_reason"] = "artifact_sync_repair"
        if source_path:
            meta["version_spec_source"] = source_path.name
    spec["version"] = version
    return spec


def write_requirement_trace_report_for_policy(topic: str, spec: Mapping[str, Any], spec_path: Path) -> Optional[Dict[str, str]]:
    topic = str(topic or "").strip()
    if not topic or topic == "-":
        return None
    try:
        from scripts.build_manual_requirement_trace import build_trace_elements, render_trace_report

        requirements = load_scoped_requirements_for_topic(topic)
        elements = build_trace_elements(dict(spec))
        trace_dir = RUNTIME_REPORTS_ROOT / "manual_authoring"
        trace_dir.mkdir(parents=True, exist_ok=True)
        safe_topic = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", topic).strip("_") or "policy"
        trace_path = trace_dir / f"{safe_topic}_requirement_trace.md"
        trace_path.write_text(render_trace_report(topic, requirements, elements, spec_path), encoding="utf-8")
        return {"type": "requirement_trace", "path": project_relative_path(trace_path)}
    except Exception as exc:
        return {"type": "requirement_trace_warning", "path": str(exc)}


def build_health_check_version_trend(policy_path: Path, *, current_report: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = parse_policy_filename(policy_path.name)
    topic = str(parsed.get("topic", "") or "")
    template_label = str(parsed.get("template_label", "") or "")
    rows: List[Dict[str, Any]] = []
    for candidate in OUTPUT_ROOT.glob(f"NC_{topic}_정책서_{template_label}_v*.html"):
        if not candidate.is_file() or not re_match_policy_filename(candidate.name):
            continue
        report = dict(current_report) if candidate.name == policy_path.name else (load_health_check_report(candidate.name) or {})
        if not report:
            continue
        candidate_parsed = parse_policy_filename(candidate.name)
        rows.append(
            {
                "fileName": candidate.name,
                "version": candidate_parsed.get("version", "-"),
                "score": report.get("score"),
                "judgement": report.get("judgement"),
                "mandatoryGatePassed": report.get("mandatoryGatePassed"),
                "qualityGatePassed": report.get("qualityGatePassed"),
                "artifactDriftGatePassed": report.get("artifactDriftGatePassed"),
                "gatekeeperGrade": (report.get("gatekeeper") or {}).get("grade") if isinstance(report.get("gatekeeper"), Mapping) else "",
                "checkedAt": report.get("checkedAt") or report.get("created_at") or "",
            }
        )
    rows.sort(key=lambda item: version_sort_key(str(item.get("version", ""))))
    current_index = next((index for index, row in enumerate(rows) if row.get("fileName") == policy_path.name), -1)
    previous = rows[current_index - 1] if current_index > 0 else None
    current_score = optional_int(current_report.get("score"))
    previous_score = optional_int(previous.get("score")) if previous else None
    return {
        "topic": topic,
        "templateLabel": template_label,
        "currentVersion": parsed.get("version", "-"),
        "versionCount": len(rows),
        "previousVersion": previous.get("version") if previous else "",
        "scoreDelta": (current_score - previous_score) if previous_score is not None and current_score is not None else None,
        "rows": rows[-8:],
    }


def version_sort_key(version: str) -> tuple[int, int, int]:
    return policy_version_sort_key(version)


def optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def health_check_export_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    path, topic, template_type, file_name = resolve_health_check_target(payload)
    report = payload.get("report") if isinstance(payload.get("report"), Mapping) else load_health_check_report(file_name)
    if not isinstance(report, Mapping):
        report = health_check_from_payload(payload)
    export_dir = OUTPUT_ROOT / "health_reports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"{Path(file_name).stem}_health_check_report.html"
    export_path.write_text(render_health_check_export_html(dict(report), topic=topic, template_type=template_type), encoding="utf-8")
    return output_artifact_payload(export_path)


def dev_format_slug_for_policy_path(path: Path) -> str:
    stem = path.stem.replace(" ", "_")
    return re.sub(r"[^\w가-힣ㄱ-ㅎㅏ-ㅣ_.-]", "", stem, flags=re.UNICODE) or "policy"


def dev_format_warning_summary(warnings_path: Path) -> Dict[str, Any]:
    if not warnings_path.exists() or not warnings_path.is_file():
        return {
            "status": "blocked",
            "blockingCount": 1,
            "reviewCount": 0,
            "totalCount": 1,
            "counts": {},
            "diagramNotes": {"totalCount": 0, "actionCount": 0, "items": []},
            "sections": [
                {
                    "key": "warningsMissing",
                    "label": "warnings.md",
                    "count": 1,
                    "tone": "blocking",
                }
            ],
        }

    text = warnings_path.read_text(encoding="utf-8")
    diagram_notes = dev_format_diagram_notes(text)
    counts: Dict[str, int] = {}
    sections: List[Dict[str, Any]] = []
    blocking_count = 0
    review_count = 0
    total_count = 0
    for key, label, tone in DEV_FORMAT_WARNING_SECTIONS:
        match = re.search(re.escape(label) + r".*?\((\d+)건\)", text)
        count = int(match.group(1)) if match else 0
        counts[key] = count
        total_count += count
        if count <= 0:
            continue
        sections.append({"key": key, "label": label, "count": count, "tone": tone})
        if tone == "blocking":
            blocking_count += count
        else:
            review_count += count

    status = "blocked" if blocking_count else "review" if review_count else "pass"
    return {
        "status": status,
        "blockingCount": blocking_count,
        "reviewCount": review_count,
        "totalCount": total_count,
        "counts": counts,
        "diagramNotes": diagram_notes,
        "sections": sections,
    }


def dev_format_diagram_notes(warnings_text: str) -> Dict[str, Any]:
    match = re.search(r"## Diagrams[^\n]*\((\d+)건\)(?P<body>.*)\Z", warnings_text, re.S)
    if not match:
        return {"totalCount": 0, "actionCount": 0, "items": []}
    total_count = int(match.group(1))
    body = match.group("body")
    items: List[Dict[str, Any]] = []
    for raw_note in re.findall(r"^- (.+)$", body, flags=re.M):
        note = raw_note.strip()
        if not note or note.startswith("_"):
            continue
        key, _, detail = note.partition(":")
        key = key.strip()
        detail = detail.strip() or note
        targets = dev_format_note_targets(detail)
        if key == "uc_diagram_low_confidence":
            # 모든 UC SVG→Mermaid 변환에 붙는 일반 안내라 웹의 경고/조치 목록에서는 제외한다.
            continue
        if key == "unmapped_uc_names":
            label = "유즈케이스 이름 매칭 확인"
            message = "Mermaid 변환 중 아래 이름을 유즈케이스 ID와 자동 매칭하지 못했습니다."
            action = "ID 기준 산출물은 mapping.csv와 entities.yaml에서 확인할 수 있습니다."
        elif key == "entities_based_supplement":
            label = "유즈케이스 다이어그램 보강"
            message = "원본 SVG에서 아래 ID를 관계선까지 안정적으로 읽지 못해 entities.yaml 기준으로 노드를 보강했습니다."
            action = "액터 연결 확인이 필요하면 diagrams/uc_1.svg 원본을 확인하세요."
        elif key == "bpmn_task_missing_from_mermaid":
            label = "BPMN 프로세스 표시 확인"
            message = "원본 BPMN SVG에 아래 프로세스가 task 노드로 그려져 있지 않습니다."
            action = "프로세스 추적은 mapping.csv와 entities.yaml 기준으로 확인하세요."
        elif key == "unknown_diagram_type":
            label = "다이어그램 유형 확인"
            message = "다이어그램 유형을 자동 분류하지 못했습니다."
            action = "정확한 형태는 diagrams 폴더의 원본 SVG와 warnings.md를 확인하세요."
        else:
            label = "다이어그램 변환 참고"
            message = "다이어그램 변환 중 참고할 항목이 있습니다."
            action = "정확한 다이어그램 구조가 필요하면 warnings.md와 diagrams/*.svg 원본을 함께 확인하세요."
        items.append({
            "key": key,
            "label": label,
            "detail": detail,
            "message": message,
            "action": action,
            "targets": targets,
        })
    return {"totalCount": total_count, "actionCount": len(items), "items": items}


def dev_format_note_targets(detail: str) -> List[str]:
    return [match[0] or match[1] for match in re.findall(r"'([^']+)'|\"([^\"]+)\"", detail)]


def dev_format_file_artifact(path: Path, label: str) -> Optional[Dict[str, str]]:
    if not path.exists() or not path.is_file():
        return None
    artifact = output_artifact_payload(path)
    artifact["label"] = label
    return artifact


def write_dev_format_zip(export_dir: Path, zip_path: Path) -> None:
    files = [
        path
        for path in sorted(export_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() != ".zip"
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(export_dir))


def dev_format_zip_tree(zip_path: Path, export_dir: Path, usecase_files: List[Path], diagram_files: List[Path]) -> Dict[str, Any]:
    preferred_root_order = ["00_INDEX.md", "README.md", "mapping.csv", "entities.yaml", "warnings.md"]
    available_root_files = {
        path.name
        for path in sorted(export_dir.iterdir())
        if path.is_file() and path.suffix.lower() != ".zip" and not path.name.startswith("usecase_")
    }
    root_files = [
        name for name in preferred_root_order if name in available_root_files
    ] + sorted(name for name in available_root_files if name not in preferred_root_order)
    return {
        "rootName": zip_path.name,
        "files": root_files,
        "groups": {
            "usecases": {
                "pattern": "usecase_*.md",
                "count": len(usecase_files),
            },
            "diagrams": {
                "name": "diagrams",
                "files": [path.name for path in diagram_files],
            },
        },
    }


def dev_format_export_payload(policy_path: Path, export_dir: Path, zip_path: Path) -> Dict[str, Any]:
    mapping_path = export_dir / "mapping.csv"
    mapping_rows = 0
    if mapping_path.exists() and mapping_path.is_file():
        with mapping_path.open("r", encoding="utf-8", newline="") as handle:
            mapping_rows = max(0, sum(1 for _ in handle) - 1)

    usecase_files = sorted(export_dir.glob("usecase_US-*.md"))
    diagram_files = sorted((export_dir / "diagrams").glob("*.svg")) if (export_dir / "diagrams").is_dir() else []
    parsed = parse_policy_filename(policy_path.name)
    artifact_candidates = [
        (export_dir / "00_INDEX.md", "AI 진입점"),
        (export_dir / "README.md", "사용 가이드"),
        (export_dir / "warnings.md", "검증 리포트"),
        (mapping_path, "매핑 CSV"),
        (export_dir / "entities.yaml", "엔티티 YAML"),
    ]
    artifacts = [
        artifact
        for artifact in (dev_format_file_artifact(path, label) for path, label in artifact_candidates)
        if artifact
    ]
    primary_artifact = dev_format_file_artifact(export_dir / "00_INDEX.md", "AI 진입점")
    zip_artifact = dev_format_file_artifact(zip_path, "ZIP 파일")
    if primary_artifact is None:
        raise ValueError("AI Input Export 산출물 00_INDEX.md를 생성하지 못했습니다.")
    if zip_artifact is None:
        raise ValueError("AI Input Export ZIP 산출물을 생성하지 못했습니다.")
    return {
        "sourceName": policy_path.name,
        "source": output_artifact_payload(policy_path),
        "topic": parsed.get("topic", ""),
        "templateType": "full",
        "templateLabel": parsed.get("template_label", "Full"),
        "version": parsed.get("version", ""),
        "outputDir": str(export_dir.resolve().relative_to(OUTPUT_ROOT.resolve())),
        "primaryArtifact": primary_artifact,
        "zipArtifact": zip_artifact,
        "zipTree": dev_format_zip_tree(zip_path, export_dir, usecase_files, diagram_files),
        "artifacts": artifacts,
        "counts": {
            "usecaseFiles": len(usecase_files),
            "diagramFiles": len(diagram_files),
            "mappingRows": mapping_rows,
            "totalFiles": sum(1 for path in export_dir.rglob("*") if path.is_file()),
        },
        "warnings": dev_format_warning_summary(export_dir / "warnings.md"),
    }


def dev_format_export_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    source_name = str(payload.get("name", "") or "").strip()
    if not source_name:
        raise ValueError("AI Input Export를 실행할 정책서를 선택해 주세요.")
    policy_path = policy_file_path(source_name)
    if not policy_path.exists() or not policy_path.is_file():
        raise ValueError("AI Input Export를 실행할 정책서 파일을 찾을 수 없습니다.")
    parsed = parse_policy_filename(policy_path.name)
    if parsed.get("template_label") != "Full":
        raise ValueError("AI Input Export는 Full 버전 정책서에서만 실행할 수 있습니다.")

    try:
        from exporters.dev_format import build_dev_format
    except ImportError:  # pragma: no cover - package import fallback.
        from .exporters.dev_format import build_dev_format

    exports_root = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / "exports")
    exports_root.mkdir(parents=True, exist_ok=True)
    slug = dev_format_slug_for_policy_path(policy_path)
    target_dir = safe_child_path(exports_root, exports_root / slug)
    staging_dir = safe_child_path(exports_root, exports_root / f".{slug}.tmp-{uuid.uuid4().hex}")
    backup_dir = safe_child_path(exports_root, exports_root / f".{slug}.backup-{uuid.uuid4().hex}")
    backup_created = False
    try:
        build_dev_format(policy_path, staging_dir)
        staging_zip = staging_dir / f"{slug}.zip"
        write_dev_format_zip(staging_dir, staging_zip)
        if target_dir.exists():
            if target_dir.is_dir():
                target_dir.rename(backup_dir)
                backup_created = True
            else:
                target_dir.unlink()
        staging_dir.rename(target_dir)
        if backup_created and backup_dir.exists():
            shutil.rmtree(backup_dir)
        return dev_format_export_payload(policy_path, target_dir, target_dir / f"{slug}.zip")
    except Exception:
        if backup_created and backup_dir.exists() and not target_dir.exists():
            backup_dir.rename(target_dir)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def analysis_alignment_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    path, _topic, _template_type, file_name = resolve_health_check_target(payload)
    spec, spec_source = load_policy_spec_for_policy_path(path)
    if spec is None:
        raise ValueError("분석-정책 정렬 점검에 필요한 정책서 spec 파일을 찾지 못했습니다.")
    report = build_analysis_policy_alignment_report(
        spec=spec,
        policy_file_name=file_name,
        evidence_db_path=REFERENCE_DB_PATH,
    )
    if spec_source:
        report["specSource"] = spec_source.name
    llm_client, llm_error = optional_hybrid_llm_client_from_payload(payload, "analysis_alignment")
    report["evaluationMode"] = "code"
    if llm_client is not None:
        report = apply_analysis_alignment_llm_review(report, llm_client=llm_client)
    elif llm_error:
        report["llmError"] = llm_error
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 trace 기반 정렬 Check로 완료했습니다.".strip()
    save_analysis_alignment_report(report, file_name=file_name)
    return report


def save_analysis_alignment_report(report: Mapping[str, Any], *, file_name: str) -> Path:
    target_dir = REPORTS_DIR / "analysis_alignment"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{Path(file_name).stem}_analysis_alignment.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def channel_pi_status_from_runtime(*, force: bool = False, payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cached = load_channel_pi_status_report(reports_dir=REPORTS_DIR)
    if not force and cached:
        cached["cached"] = True
        return cached
    try:
        report = build_channel_pi_status_report(
            output_root=OUTPUT_ROOT,
            evidence_db_path=REFERENCE_DB_PATH,
            requirements_db_path=REQUIREMENTS_DB_PATH,
        )
        llm_client, llm_error = optional_hybrid_llm_client_from_payload(payload or {}, "channel_pi_status")
        report["evaluationMode"] = "code"
        if llm_client is not None:
            report = apply_channel_pi_status_llm_review(report, llm_client=llm_client)
        elif llm_error:
            report["llmError"] = llm_error
            report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 trace 기반 채널 PI 진단으로 완료했습니다.".strip()
        save_channel_pi_status_report(report, reports_dir=REPORTS_DIR)
        report["cached"] = False
        return report
    except Exception as exc:
        if cached:
            cached["cached"] = True
            cached["refreshError"] = str(exc)
            cached["refreshFailedAt"] = datetime.now().isoformat(timespec="seconds")
            return cached
        raise


def hybrid_review_schema(kind: str) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "confidence", "actionItems"],
        "properties": {
            "summary": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "actionItems": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["priority", "title", "target", "evidence", "suggestion"],
                    "properties": {
                        "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                        "title": {"type": "string"},
                        "target": {"type": "string"},
                        "evidence": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                },
            },
        },
    }


def normalize_hybrid_review(review: Mapping[str, Any]) -> Dict[str, Any]:
    confidence = str(review.get("confidence") or "medium").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    action_items: List[Dict[str, str]] = []
    for item in review.get("actionItems", []) if isinstance(review.get("actionItems", []), list) else []:
        if not isinstance(item, Mapping):
            continue
        priority = str(item.get("priority") or "P2").strip().upper()
        if priority not in {"P1", "P2", "P3"}:
            priority = "P2"
        action_items.append(
            {
                "priority": priority,
                "title": limit_text(str(item.get("title") or "LLM 보조판정 보완"), 90),
                "target": limit_text(str(item.get("target") or "점검 결과"), 120),
                "evidence": limit_text(str(item.get("evidence") or ""), 220),
                "suggestion": limit_text(str(item.get("suggestion") or ""), 260),
            }
        )
    return {
        "summary": limit_text(str(review.get("summary") or ""), 420),
        "confidence": confidence,
        "actionItems": action_items[:6],
    }


def pi_check_hybrid_instructions() -> str:
    return """
당신은 PI Check의 LLM 보조판정자다.
규칙 기반 점수와 Gate를 대체하지 말고, 오탐 가능성, 누락된 판단 근거, 보완 액션만 짧게 보강한다.
문서에 없는 수치, KPI 목표, 조직명, 범위를 새로 만들지 않는다.
보완 액션은 정책서 작성자가 바로 반영할 수 있는 위치와 지시로 작성한다.
결과는 지정된 JSON 스키마만 반환한다.
""".strip()


def pi_check_hybrid_prompt(report: Mapping[str, Any], *, to_be_text: str, as_is_text: str = "") -> str:
    focus_checks = [
        {
            "id": item.get("id"),
            "status": item.get("status"),
            "question": item.get("question") or item.get("inspectionItem"),
            "targetLocation": item.get("targetLocation"),
            "statusReason": item.get("statusReason"),
            "suggestion": item.get("suggestion"),
        }
        for item in report.get("checks", [])
        if isinstance(item, Mapping) and str(item.get("status") or "").lower() != "yes"
    ][:18]
    payload = {
        "score": report.get("score"),
        "judgement": report.get("judgement"),
        "summary": report.get("summary"),
        "comparison": report.get("comparison"),
        "focusChecks": focus_checks,
        "antiPatterns": report.get("antiPatterns", [])[:8] if isinstance(report.get("antiPatterns"), list) else [],
        "actionItems": report.get("actionItems", [])[:10] if isinstance(report.get("actionItems"), list) else [],
    }
    parts = [
        "아래 PI Check 규칙 기반 결과를 검토해 보조판정 요약과 우선 보완 액션을 작성해 주세요.",
        json.dumps(payload, ensure_ascii=False),
        "To-Be 문서 텍스트 발췌:",
        limit_text(to_be_text, 12000),
    ]
    if as_is_text:
        parts.extend(["As-Is 문서 텍스트 발췌:", limit_text(as_is_text, 5000)])
    return "\n\n".join(parts)


def alignment_hybrid_instructions() -> str:
    return """
당신은 현황 분석과 정책서 간 trace 정렬 결과를 검토하는 LLM 보조판정자다.
규칙 기반 점수는 유지하고, 매칭 오탐 가능성, trace 보강 위치, 정책서 수정 없이 보강할 근거 연결을 제안한다.
분석 자료나 정책서에 없는 사실을 만들지 않는다.
결과는 지정된 JSON 스키마만 반환한다.
""".strip()


def alignment_hybrid_prompt(report: Mapping[str, Any]) -> str:
    payload = {
        "score": report.get("score"),
        "judgement": report.get("judgement"),
        "summary": report.get("summary"),
        "sourceCoverage": report.get("sourceCoverage", [])[:8] if isinstance(report.get("sourceCoverage"), list) else [],
        "analysisToPolicy": report.get("analysisToPolicy", [])[:10] if isinstance(report.get("analysisToPolicy"), list) else [],
        "policyToAnalysis": report.get("policyToAnalysis", [])[:10] if isinstance(report.get("policyToAnalysis"), list) else [],
        "actionItems": report.get("actionItems", [])[:10] if isinstance(report.get("actionItems"), list) else [],
    }
    return "\n\n".join(
        [
            "아래 분석-정책 정렬 Check 결과를 검토해 보조판정 요약과 trace 보강 액션을 작성해 주세요.",
            json.dumps(payload, ensure_ascii=False),
        ]
    )


def channel_pi_hybrid_instructions() -> str:
    return """
당신은 채널 PI 현황 대시보드의 LLM 보조판정자다.
전체 점수와 trace 산식은 바꾸지 않고, 경영/PM 관점에서 우선 보강 지점과 판단 리스크를 짧게 정리한다.
새로운 점수, 수치 목표, 사실을 만들지 않는다.
결과는 지정된 JSON 스키마만 반환한다.
""".strip()


def channel_pi_hybrid_prompt(report: Mapping[str, Any]) -> str:
    payload = {
        "score": report.get("score"),
        "judgement": report.get("judgement"),
        "summary": report.get("summary"),
        "topicCount": report.get("topicCount"),
        "dimensions": report.get("dimensions", [])[:8] if isinstance(report.get("dimensions"), list) else [],
        "sourceCoverage": report.get("sourceCoverage", [])[:8] if isinstance(report.get("sourceCoverage"), list) else [],
        "analysisItemCoverageSummary": report.get("analysisItemCoverageSummary"),
        "crossValidation": report.get("crossValidation"),
        "priorityActions": report.get("priorityActions", [])[:10] if isinstance(report.get("priorityActions"), list) else [],
    }
    return "\n\n".join(
        [
            "아래 채널 PI 현황 진단 결과를 검토해 보조판정 요약과 우선 보강 액션을 작성해 주세요.",
            json.dumps(payload, ensure_ascii=False),
        ]
    )


def apply_analysis_alignment_llm_review(report: Dict[str, Any], *, llm_client: LLMClient) -> Dict[str, Any]:
    try:
        review = llm_client.generate_json(
            schema_name="analysis_alignment_hybrid_review",
            schema=hybrid_review_schema("analysis_alignment"),
            instructions=alignment_hybrid_instructions(),
            input_messages=[{"role": "user", "content": alignment_hybrid_prompt(report)}],
        )
    except Exception as exc:
        report["llmError"] = str(exc)
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 trace 기반 정렬 Check로 완료했습니다.".strip()
        return report
    normalized = normalize_hybrid_review(review)
    report["evaluationMode"] = "hybrid"
    report["llmReview"] = normalized
    if normalized.get("summary"):
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정: {normalized['summary']}".strip()
    if normalized.get("actionItems"):
        current_actions = report.get("actionItems", []) if isinstance(report.get("actionItems"), list) else []
        llm_actions = [{**item, "type": "llm_alignment_review"} for item in normalized["actionItems"]]
        report["actionItems"] = [*current_actions, *llm_actions][:24]
    return report


def apply_channel_pi_status_llm_review(report: Dict[str, Any], *, llm_client: LLMClient) -> Dict[str, Any]:
    try:
        review = llm_client.generate_json(
            schema_name="channel_pi_status_hybrid_review",
            schema=hybrid_review_schema("channel_pi_status"),
            instructions=channel_pi_hybrid_instructions(),
            input_messages=[{"role": "user", "content": channel_pi_hybrid_prompt(report)}],
        )
    except Exception as exc:
        report["llmError"] = str(exc)
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 trace 기반 채널 PI 진단으로 완료했습니다.".strip()
        return report
    normalized = normalize_hybrid_review(review)
    report["evaluationMode"] = "hybrid"
    report["llmReview"] = normalized
    if normalized.get("summary"):
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정: {normalized['summary']}".strip()
    if normalized.get("actionItems"):
        current_actions = report.get("priorityActions", []) if isinstance(report.get("priorityActions"), list) else []
        llm_actions = [{**item, "type": "llm_channel_pi_review"} for item in normalized["actionItems"]]
        report["priorityActions"] = [*current_actions, *llm_actions][:24]
    return report


def render_health_check_export_html(report: Mapping[str, Any], *, topic: str, template_type: str) -> str:
    gatekeeper = report.get("gatekeeper", {}) if isinstance(report.get("gatekeeper"), Mapping) else {}
    artifact_drift = report.get("artifactDrift", {}) if isinstance(report.get("artifactDrift"), Mapping) else {}
    version_trend = report.get("versionTrend", {}) if isinstance(report.get("versionTrend"), Mapping) else {}
    template_profile = report.get("templateProfile", {}) if isinstance(report.get("templateProfile"), Mapping) else {}
    sections = report.get("sections", []) if isinstance(report.get("sections", []), list) else []
    gates = report.get("mandatoryGates", []) if isinstance(report.get("mandatoryGates", []), list) else []
    action_items = report.get("actionItems", []) if isinstance(report.get("actionItems", []), list) else []
    remediation_plan = report.get("remediationPlan", {}) if isinstance(report.get("remediationPlan"), Mapping) else {}
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(str(report.get('fileName', 'Health Check Report')))}</title>
<style>
body {{ margin: 0; background: #f6f8fb; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 42px 28px 64px; }}
h1 {{ margin: 0; font-size: 30px; letter-spacing: 0; }}
h2 {{ margin: 28px 0 12px; font-size: 18px; }}
p {{ line-height: 1.65; }}
.eyebrow {{ color: #2563eb; font-size: 12px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }}
.summary {{ border: 1px solid #dbeafe; border-radius: 12px; background: #fff; padding: 20px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 18px 0; }}
.stat, .card {{ border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; padding: 14px; }}
.stat span {{ display: block; color: #64748b; font-size: 12px; font-weight: 800; }}
.stat strong {{ display: block; margin-top: 4px; font-size: 18px; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; }}
th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px 12px; text-align: left; vertical-align: top; font-size: 13px; }}
th {{ background: #f8fafc; font-weight: 900; }}
.badge {{ display: inline-flex; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 900; }}
.pass {{ background: #dcfce7; color: #047857; }}
.warn {{ background: #fef3c7; color: #a16207; }}
.fail {{ background: #fee2e2; color: #dc2626; }}
</style>
</head>
<body>
<main>
<p class="eyebrow">Policy Health Check Export</p>
<h1>{html.escape(str(report.get('fileName', 'Health Check Report')))}</h1>
<section class="summary">
<p>{html.escape(str(report.get('summary', '')))}</p>
<div class="stats">
{health_export_stat('주제', topic)}
{health_export_stat('템플릿', template_type)}
{health_export_stat('검증 범위', template_profile.get('label', '-'))}
{health_export_stat('총점', f"{report.get('score', '-')} / {report.get('maxScore', 100)}")}
{health_export_stat('판정', report.get('judgement', '-'))}
{health_export_stat('GateKeeper', f"{gatekeeper.get('grade', '-')} · {'통과' if gatekeeper.get('passed') else '보완 필요'}")}
{health_export_stat('산출물 동기화', artifact_drift.get('status', '-'))}
{health_export_stat('버전 추이', health_trend_label(version_trend))}
</div>
</section>
<h2>필수 게이트</h2>
{health_export_gate_table(gates)}
<h2>GateKeeper 평가</h2>
{health_export_gatekeeper_table(gatekeeper)}
<h2>산출물 동기화</h2>
{health_export_drift_table(artifact_drift)}
<h2>버전 품질 추이</h2>
{health_export_trend_table(version_trend)}
<h2>보완 전략</h2>
{health_export_remediation_plan(remediation_plan)}
<h2>영역별 결과</h2>
{health_export_section_table(sections)}
<h2>주요 보완 항목</h2>
{health_export_action_table(action_items)}
</main>
</body>
</html>"""


def health_export_stat(label: str, value: Any) -> str:
    return f"<div class=\"stat\"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>"


def health_trend_label(trend: Mapping[str, Any]) -> str:
    delta = trend.get("scoreDelta")
    if delta is None:
        return f"{trend.get('versionCount', 0)}개 버전"
    sign = "+" if int(delta) >= 0 else ""
    return f"{trend.get('versionCount', 0)}개 버전 / {sign}{delta}점"


def health_export_gate_table(gates: List[Any]) -> str:
    rows = [
        (
            gate.get("id", ""),
            "통과" if gate.get("passed") else "미통과",
            gate.get("description", ""),
            gate.get("suggestion") or gate.get("reason") or "",
        )
        for gate in gates
        if isinstance(gate, Mapping)
    ]
    return health_export_table(("ID", "결과", "설명", "보완 제안"), rows)


def health_export_remediation_plan(plan: Mapping[str, Any]) -> str:
    if not plan:
        return '<div class="card">보완 전략 데이터가 없습니다.</div>'
    groups = (
        ("즉시 보완", plan.get("immediate", [])),
        ("잠재 보완", plan.get("potential", [])),
        ("산출물 동기화", plan.get("artifactSync", [])),
        ("신규 발견", plan.get("newlyDetected", [])),
        ("반복 지적", plan.get("repeated", [])),
        ("개선 완료", plan.get("improved", [])),
    )
    rows = []
    for label, items in groups:
        safe_items = items if isinstance(items, list) else []
        if not safe_items:
            rows.append((label, "0건", "-", "-"))
            continue
        titles = []
        for item in safe_items[:5]:
            if not isinstance(item, Mapping):
                continue
            title = str(item.get("title") or item.get("itemId") or "").strip()
            location = str(item.get("targetLocation") or "").strip()
            titles.append(f"{title} ({location})" if location else title)
        rows.append((label, f"{len(safe_items)}건", " / ".join(titles), str(plan.get("guidance", "") or "")))
    summary = html.escape(str(plan.get("summary", "") or ""))
    return f'<div class="card"><p>{summary}</p></div>{health_export_table(("구분", "건수", "대표 항목", "처리 기준"), rows)}'


def health_export_gatekeeper_table(gatekeeper: Mapping[str, Any]) -> str:
    dimensions = gatekeeper.get("dimensions", []) if isinstance(gatekeeper.get("dimensions", []), list) else []
    rows = [
        (
            item.get("label", ""),
            item.get("status", ""),
            f"{item.get('score', 0)} / {item.get('maxScore', 20)}",
            item.get("evidence", ""),
            item.get("suggestion", ""),
        )
        for item in dimensions
        if isinstance(item, Mapping)
    ]
    return health_export_table(("차원", "상태", "점수", "근거", "제안"), rows)


def health_export_drift_table(drift: Mapping[str, Any]) -> str:
    issues = drift.get("issues", []) if isinstance(drift.get("issues", []), list) else []
    if not issues:
        return "<div class=\"card\"><span class=\"badge pass\">PASS</span><p>산출물 동기화 이슈가 없습니다.</p></div>"
    rows = [
        (
            item.get("severity", ""),
            item.get("target", ""),
            item.get("detail", ""),
            item.get("recommendation", ""),
        )
        for item in issues
        if isinstance(item, Mapping)
    ]
    return health_export_table(("우선순위", "대상", "상세", "제안"), rows)


def health_export_trend_table(trend: Mapping[str, Any]) -> str:
    rows = [
        (
            item.get("version", ""),
            item.get("score", "-"),
            item.get("judgement", "-"),
            item.get("gatekeeperGrade", "-"),
            item.get("checkedAt", "-"),
        )
        for item in (trend.get("rows", []) if isinstance(trend.get("rows", []), list) else [])
        if isinstance(item, Mapping)
    ]
    return health_export_table(("버전", "점수", "판정", "GK", "실행 시각"), rows)


def health_export_section_table(sections: List[Any]) -> str:
    rows = [
        (
            item.get("name", ""),
            f"{item.get('score', 0)} / {item.get('maxScore', 10)}",
            item.get("judgement", ""),
            item.get("majorGap", ""),
        )
        for item in sections
        if isinstance(item, Mapping)
    ]
    return health_export_table(("영역", "점수", "판정", "주요 Gap"), rows)


def health_export_action_table(action_items: List[Any]) -> str:
    rows = [
        (
            item.get("priority", ""),
            item.get("section", ""),
            item.get("title", ""),
            item.get("targetLocation", ""),
            item.get("suggestion", ""),
        )
        for item in action_items
        if isinstance(item, Mapping)
    ]
    return health_export_table(("우선순위", "영역", "항목", "위치", "제안"), rows)


def health_export_table(headers: tuple[str, ...], rows: List[tuple[Any, ...]]) -> str:
    if not rows:
        return "<div class=\"card\"><p>표시할 항목이 없습니다.</p></div>"
    head = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def pi_check_rubric_payload() -> Dict[str, Any]:
    knowledge = load_pi_agent_knowledge()
    return {
        "agent": knowledge.get("agent", "PI Agent"),
        "version": knowledge.get("version", "1.0"),
        "checklist": pi_checklist_with_methods(),
        "inspectionMethods": knowledge.get("inspection_methods") or PI_INSPECTION_METHODS,
        "gatekeeperDimensions": knowledge.get("gatekeeper_dimensions") or PI_GATEKEEPER_DIMENSIONS,
        "antiPatterns": knowledge.get("anti_patterns", []),
        "principles": knowledge.get("principles", []),
    }


PI_CHECK_SUPPORTED_SUFFIXES = {".pptx", ".docx", ".pdf", ".html", ".htm", ".bpmn", ".md", ".txt", ".json"}
PI_CHECK_MAX_BYTES = 20 * 1024 * 1024


def pi_check_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    topic = str(payload.get("topic", "") or "").strip()
    to_be_upload = payload.get("toBe")
    as_is_upload = payload.get("asIs")
    if not isinstance(to_be_upload, Mapping):
        legacy_upload_present = bool(payload.get("name") or payload.get("contentBase64") or payload.get("content"))
        if "asIs" in payload and not legacy_upload_present:
            raise ValueError("PI Check 대상 To-Be 문서를 업로드해 주세요.")
        to_be_upload = payload
    if not isinstance(to_be_upload, Mapping):
        raise ValueError("PI Check 대상 To-Be 문서를 업로드해 주세요.")

    to_be_report = pi_check_single_upload(to_be_upload, topic=topic, role="to_be")
    as_is_report = pi_check_single_upload(as_is_upload, topic=topic, role="as_is") if isinstance(as_is_upload, Mapping) else None
    comparison = compare_pi_reports(as_is_report, to_be_report) if as_is_report else None
    llm_client, llm_error = optional_hybrid_llm_client_from_payload(payload, "pi_agent")

    summary = to_be_report.get("summary", "PI Check를 완료했습니다.")
    if comparison:
        delta = int(comparison.get("deltaScore") or 0)
        delta_label = f"+{delta}" if delta >= 0 else str(delta)
        summary = (
            f"To-Be 문서 기준 {summary} "
            f"As-Is 대비 PI 점수는 {delta_label}점이며, 개선 항목 {comparison.get('improvedCount', 0)}건, "
            f"후퇴/주의 항목 {comparison.get('regressedCount', 0)}건입니다."
        )

    report = enrich_pi_check_report(
        {
            **to_be_report,
            "summary": summary,
            "toBe": to_be_report,
            "asIs": as_is_report,
            "comparison": comparison,
            "evaluationMode": "code",
        },
        comparison=comparison,
    )
    if llm_client is not None:
        report = apply_pi_check_llm_review(
            report,
            llm_client=llm_client,
            to_be_text=str(to_be_report.get("_analysisTextPreview") or ""),
            as_is_text=str((as_is_report or {}).get("_analysisTextPreview") or ""),
        )
    elif llm_error:
        report["llmError"] = llm_error
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 규칙 기반 PI Check로 완료했습니다.".strip()
    return strip_internal_pi_fields(report)


def pi_check_single_upload(upload: Mapping[str, Any], *, topic: str, role: str) -> Dict[str, Any]:
    file_name = str(upload.get("name", "") or "").strip() or ("to_be_document.html" if role == "to_be" else "as_is_document.html")
    suffix = Path(file_name).suffix.lower()
    if suffix not in PI_CHECK_SUPPORTED_SUFFIXES:
        raise ValueError("현재 PI Check는 PPTX, DOCX, PDF, HTML, BPMN, Markdown, Text, JSON 문서만 지원합니다.")

    content_bytes = pi_check_uploaded_bytes(upload)
    if not content_bytes:
        label = "To-Be" if role == "to_be" else "As-Is"
        raise ValueError(f"PI Check 대상 {label} 문서 내용이 비어 있습니다.")
    if len(content_bytes) > PI_CHECK_MAX_BYTES:
        raise ValueError("PI Check 대상 문서는 20MB 이하만 업로드할 수 있습니다.")

    normalized_document = normalize_pi_check_document(content_bytes, file_name=file_name)
    analysis_text = pi_check_analysis_text(normalized_document)
    if not analysis_text.strip():
        raise ValueError("업로드 문서에서 PI Check에 사용할 수 있는 텍스트를 추출하지 못했습니다.")
    raw_report = evaluate_pi_document_quality(analysis_text, topic=topic)
    report = normalize_pi_check_report(
        raw_report,
        file_name=file_name,
        topic=topic,
        role=role,
        normalized_document=normalized_document,
    )
    report["_analysisTextPreview"] = limit_text(analysis_text, 18000)
    return report


def normalize_pi_check_report(
    raw_report: Mapping[str, Any],
    *,
    file_name: str,
    topic: str,
    role: str,
    normalized_document: Mapping[str, Any],
) -> Dict[str, Any]:
    checks = raw_report.get("checks", []) if isinstance(raw_report.get("checks"), list) else []
    yes_count = int(raw_report.get("yes_count") or 0)
    partial_count = int(raw_report.get("partial_count") or 0)
    no_count = int(raw_report.get("no_count") or 0)
    anti_patterns = raw_report.get("anti_patterns", []) if isinstance(raw_report.get("anti_patterns"), list) else []
    max_points = max(1, len(checks) * 2)
    score = round(((yes_count * 2) + partial_count) / max_points * 100)
    judgement = "우수" if score >= 90 and no_count == 0 and not anti_patterns else "양호" if score >= 80 else "보완 필요" if score >= 65 else "재검토 필요"
    summary = (
        f"PI 체크 {len(checks)}개 중 PASS {yes_count}건, PARTIAL {partial_count}건, FAIL {no_count}건입니다. "
        f"안티패턴은 {len(anti_patterns)}건 감지되었습니다."
    )
    return enrich_pi_check_report(
        {
            "agent": "PI Agent",
            "role": role,
            "fileName": file_name,
            "topic": topic,
            "checkedAt": datetime.now().isoformat(timespec="seconds"),
            "score": score,
            "maxScore": 100,
            "judgement": judgement,
            "summary": summary,
            "yesCount": yes_count,
            "partialCount": partial_count,
            "noCount": no_count,
            "antiPatternCount": len(anti_patterns),
            "normalizedDocument": {
                "kind": normalized_document.get("kind"),
                "metrics": normalized_document.get("metrics", {}),
            },
            "checks": checks,
            "legacyChecks": raw_report.get("legacy_checks", []),
            "antiPatterns": anti_patterns,
            "recommendations": raw_report.get("recommendations", []),
        }
    )


def strip_internal_pi_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: strip_internal_pi_fields(item) for key, item in value.items() if not str(key).startswith("_")}
    if isinstance(value, list):
        return [strip_internal_pi_fields(item) for item in value]
    return value


def apply_pi_check_llm_review(
    report: Dict[str, Any],
    *,
    llm_client: LLMClient,
    to_be_text: str,
    as_is_text: str = "",
) -> Dict[str, Any]:
    try:
        review = llm_client.generate_json(
            schema_name="pi_check_hybrid_review",
            schema=hybrid_review_schema("pi_check"),
            instructions=pi_check_hybrid_instructions(),
            input_messages=[
                {
                    "role": "user",
                    "content": pi_check_hybrid_prompt(report, to_be_text=to_be_text, as_is_text=as_is_text),
                }
            ],
        )
    except Exception as exc:
        report["llmError"] = str(exc)
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정은 일시적으로 건너뛰고 규칙 기반 PI Check로 완료했습니다.".strip()
        return report

    normalized = normalize_hybrid_review(review)
    report["evaluationMode"] = "hybrid"
    report["llmReview"] = normalized
    if normalized.get("summary"):
        report["summary"] = f"{report.get('summary', '')} LLM 보조판정: {normalized['summary']}".strip()
    extra_actions = [
        {**item, "type": "llm_pi_review", "itemId": item.get("itemId") or "PI-LLM"}
        for item in normalized.get("actionItems", [])
        if isinstance(item, Mapping)
    ]
    if extra_actions:
        current_actions = report.get("actionItems", []) if isinstance(report.get("actionItems"), list) else []
        report["actionItems"] = [*current_actions, *extra_actions][:24]
        report["actionItemCount"] = len(report["actionItems"])
    return report


def compare_pi_reports(as_is_report: Mapping[str, Any] | None, to_be_report: Mapping[str, Any]) -> Dict[str, Any] | None:
    if not as_is_report:
        return None

    status_rank = {"no": 0, "partial": 1, "yes": 2}
    status_label = {"yes": "PASS", "partial": "PARTIAL", "no": "FAIL"}
    as_is_checks = {
        str(item.get("id") or ""): item
        for item in as_is_report.get("checks", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    to_be_checks = {
        str(item.get("id") or ""): item
        for item in to_be_report.get("checks", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    improved: List[Dict[str, Any]] = []
    regressed: List[Dict[str, Any]] = []
    unchanged = 0
    for item_id, to_item in to_be_checks.items():
        as_item = as_is_checks.get(item_id)
        if not as_item:
            continue
        as_status = str(as_item.get("status") or "no").lower()
        to_status = str(to_item.get("status") or "no").lower()
        delta = status_rank.get(to_status, 0) - status_rank.get(as_status, 0)
        comparison_item = {
            "id": item_id,
            "question": to_item.get("question") or as_item.get("question") or item_id,
            "from": status_label.get(as_status, as_status.upper()),
            "to": status_label.get(to_status, to_status.upper()),
            "suggestion": to_item.get("suggestion") or as_item.get("suggestion") or "",
        }
        if delta > 0:
            improved.append(comparison_item)
        elif delta < 0:
            regressed.append(comparison_item)
        else:
            unchanged += 1

    delta_score = int(to_be_report.get("score") or 0) - int(as_is_report.get("score") or 0)
    anti_pattern_delta = int(to_be_report.get("antiPatternCount") or 0) - int(as_is_report.get("antiPatternCount") or 0)
    return {
        "enabled": True,
        "asIsFileName": as_is_report.get("fileName", ""),
        "toBeFileName": to_be_report.get("fileName", ""),
        "asIsScore": int(as_is_report.get("score") or 0),
        "toBeScore": int(to_be_report.get("score") or 0),
        "deltaScore": delta_score,
        "asIsJudgement": as_is_report.get("judgement", ""),
        "toBeJudgement": to_be_report.get("judgement", ""),
        "improvedCount": len(improved),
        "regressedCount": len(regressed),
        "unchangedCount": unchanged,
        "antiPatternDelta": anti_pattern_delta,
        "improvedItems": improved[:12],
        "regressedItems": regressed[:12],
    }


def pi_check_uploaded_bytes(payload: Mapping[str, Any]) -> bytes:
    raw_base64 = str(payload.get("contentBase64", "") or "").strip()
    if raw_base64:
        try:
            return base64.b64decode(raw_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("업로드 파일을 읽는 중 오류가 발생했습니다.") from exc
    return str(payload.get("content", "") or "").encode("utf-8")


def pi_check_export_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    report = payload.get("report")
    if not isinstance(report, Mapping):
        raise ValueError("Export할 PI Check 보고서가 없습니다.")
    comparison = report.get("comparison") if isinstance(report.get("comparison"), Mapping) else None
    if not isinstance(report.get("gatekeeper"), Mapping) or not isinstance(report.get("actionItems"), list):
        report = enrich_pi_check_report(report, comparison=comparison)
    export_dir = OUTPUT_ROOT / "pi_reports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = str(report.get("fileName") or ((report.get("toBe") or {}).get("fileName") if isinstance(report.get("toBe"), Mapping) else "") or "pi_check")
    safe_stem = re.sub(r"[^\w가-힣.-]+", "_", Path(file_name).stem, flags=re.UNICODE).strip("._-") or "pi_check"
    export_path = export_dir / f"{safe_stem}_pi_check_report.html"
    export_path.write_text(render_pi_check_export_html(report), encoding="utf-8")
    return output_artifact_payload(export_path)


def render_pi_check_export_html(report: Mapping[str, Any]) -> str:
    gatekeeper = report.get("gatekeeper", {}) if isinstance(report.get("gatekeeper"), Mapping) else {}
    readiness = report.get("piReadiness", {}) if isinstance(report.get("piReadiness"), Mapping) else {}
    comparison = report.get("comparison", {}) if isinstance(report.get("comparison"), Mapping) else {}
    checks = report.get("checks", []) if isinstance(report.get("checks", []), list) else []
    anti_patterns = report.get("antiPatterns", []) if isinstance(report.get("antiPatterns", []), list) else []
    action_items = report.get("actionItems", []) if isinstance(report.get("actionItems", []), list) else []
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(str(report.get('fileName', 'PI Check Report')))}</title>
<style>
body {{ margin: 0; background: #f6f8fb; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 42px 28px 64px; }}
h1 {{ margin: 0; font-size: 30px; letter-spacing: 0; }}
h2 {{ margin: 28px 0 12px; font-size: 18px; }}
p {{ line-height: 1.65; }}
.eyebrow {{ color: #2563eb; font-size: 12px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }}
.summary, .card {{ border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; padding: 16px; }}
.summary {{ border-color: #dbeafe; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 18px 0; }}
.stat {{ border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; padding: 14px; }}
.stat span {{ display: block; color: #64748b; font-size: 12px; font-weight: 800; }}
.stat strong {{ display: block; margin-top: 4px; font-size: 18px; }}
.check-section {{ margin: 14px 0; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; overflow: hidden; }}
.check-section-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; background: #f8fafc; }}
.check-section-head h3 {{ margin: 0; font-size: 16px; }}
.check-section-head p {{ margin: 4px 0 0; color: #64748b; font-size: 12px; font-weight: 800; }}
.check-section-stats {{ display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }}
.check-section-stats span {{ border-radius: 999px; background: #eef2ff; color: #1d4ed8; font-size: 11px; font-weight: 900; padding: 6px 9px; white-space: nowrap; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; }}
th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px 12px; text-align: left; vertical-align: top; font-size: 13px; }}
th {{ background: #f8fafc; font-weight: 900; }}
.muted {{ color: #64748b; }}
</style>
</head>
<body>
<main>
<p class="eyebrow">Process Innovation Check Export</p>
<h1>{html.escape(str(report.get('fileName', 'PI Check Report')))}</h1>
<section class="summary">
<p>{html.escape(str(report.get('summary', '')))}</p>
<div class="stats">
{health_export_stat('총점', f"{report.get('score', '-')} / {report.get('maxScore', 100)}")}
{health_export_stat('판정', report.get('judgement', '-'))}
{health_export_stat('PI 제출 Gate', pi_export_gate_label(readiness))}
{health_export_stat('GateKeeper', f"{gatekeeper.get('grade', '-')} · {'통과' if gatekeeper.get('passed') else '보완 필요'}")}
{health_export_stat('안티패턴', f"{report.get('antiPatternCount', 0)}건")}
{health_export_stat('보완 항목', f"{len(action_items)}건")}
</div>
</section>
{pi_export_comparison(comparison)}
<h2>검수 영역과 세부 방식</h2>
{pi_export_check_sections(checks)}
<h2>GateKeeper 재검수</h2>
{health_export_table(('ID', '항목', '상태', '설명'), [
    (item.get('id', ''), item.get('name', ''), pi_status_label(item.get('status', '')), item.get('detail', ''))
    for item in gatekeeper.get('dimensions', [])
    if isinstance(item, Mapping)
])}
<h2>안티패턴</h2>
{health_export_table(('ID', '안티패턴', '사유'), [
    (item.get('id', ''), item.get('name', ''), item.get('reason', ''))
    for item in anti_patterns
    if isinstance(item, Mapping)
])}
<h2>보완 실행 항목</h2>
{health_export_table(('우선순위', '항목', '대상 위치', '검수 방식', '근거', '제안'), [
    (
        item.get('priority', ''),
        item.get('title', ''),
        item.get('targetLocation', ''),
        item.get('inspectionMethod', ''),
        item.get('evidence', ''),
        item.get('suggestion', ''),
    )
    for item in action_items
    if isinstance(item, Mapping)
])}
</main>
</body>
</html>"""


def pi_export_check_sections(checks: List[Any]) -> str:
    groups: Dict[str, Dict[str, Any]] = {}
    for item in checks:
        if not isinstance(item, Mapping):
            continue
        order = int(item.get("sectionOrder") or item.get("section_order") or 99)
        name = str(item.get("sectionName") or item.get("section_name") or "기타 검수 항목")
        key = f"{order:02d}::{name}"
        group = groups.setdefault(key, {"order": order, "name": name, "items": [], "yes": 0, "partial": 0, "no": 0})
        status = str(item.get("status", "")).lower()
        if status in {"yes", "pass"}:
            group["yes"] += 1
        elif status in {"partial", "warn"}:
            group["partial"] += 1
        else:
            group["no"] += 1
        group["items"].append(item)
    if not groups:
        return "<div class=\"card\"><p>표시할 검수 항목이 없습니다.</p></div>"
    sections: List[str] = []
    for group in sorted(groups.values(), key=lambda value: (int(value.get("order", 99)), str(value.get("name", "")))):
        rows = [
            (
                item.get("id", ""),
                item.get("inspectionItem") or item.get("focus", ""),
                item.get("inspectionMethod", ""),
                pi_status_label(item.get("status", "")),
                pi_export_evidence(item),
                item.get("suggestion", ""),
            )
            for item in group.get("items", [])
            if isinstance(item, Mapping)
        ]
        sections.append(
            f"""<section class="check-section">
<div class="check-section-head">
<div><h3>{int(group.get('order', 99)):02d}. {html.escape(str(group.get('name', '검수 영역')))}</h3><p>{len(rows)}개 세부 검수 항목</p></div>
<div class="check-section-stats">
<span>PASS {group.get('yes', 0)}</span>
<span>PARTIAL {group.get('partial', 0)}</span>
<span>FAIL {group.get('no', 0)}</span>
</div>
</div>
{health_export_table(('ID', '검수 항목', '검수 방식', '판정', '근거', '보완 기준'), rows)}
</section>"""
        )
    return "\n".join(sections)


def pi_export_comparison(comparison: Mapping[str, Any]) -> str:
    if not comparison:
        return "<h2>As-Is/To-Be 비교</h2><div class=\"card\"><p class=\"muted\">As-Is 문서가 없어 To-Be 단독 점검으로 처리했습니다.</p></div>"
    return (
        "<h2>As-Is/To-Be 비교</h2>"
        + health_export_table(
            ("항목", "값"),
            [
                ("As-Is 파일", comparison.get("asIsFileName", "")),
                ("To-Be 파일", comparison.get("toBeFileName", "")),
                ("점수 변화", f"{comparison.get('asIsScore', '-')} → {comparison.get('toBeScore', '-')} ({comparison.get('deltaScore', '-')})"),
                ("개선 항목", comparison.get("improvedCount", 0)),
                ("후퇴 항목", comparison.get("regressedCount", 0)),
                ("안티패턴 증감", comparison.get("antiPatternDelta", 0)),
            ],
        )
    )


def pi_export_gate_label(readiness: Mapping[str, Any]) -> str:
    status = str(readiness.get("status", "") or "").lower()
    if status == "pass":
        return "통과"
    if status == "warn":
        return "보완 필요"
    if status == "fail":
        return "미통과"
    return "-"


def pi_export_evidence(item: Mapping[str, Any]) -> str:
    evidence = item.get("evidence", [])
    if isinstance(evidence, str):
        return evidence
    if isinstance(evidence, list):
        return " / ".join(str(value) for value in evidence if value)
    return str(item.get("statusReason", "") or "")


def pi_status_label(status: Any) -> str:
    value = str(status or "").lower()
    return {
        "yes": "PASS",
        "pass": "PASS",
        "partial": "PARTIAL",
        "warn": "WARN",
        "no": "FAIL",
        "fail": "FAIL",
        "regressed": "REGRESSED",
    }.get(value, str(status or "-").upper())


def resolve_health_check_target(payload: Mapping[str, Any]) -> tuple[Path, str, str, str]:
    name = str(payload.get("name", "")).strip()
    if name:
        path = policy_file_path(name)
        if not path.exists() or not path.is_file():
            raise ValueError("Health Check 대상 파일을 찾을 수 없습니다.")
        parsed = parse_policy_filename(path.name)
        template_type = "full" if parsed["template_label"] == "Full" else "simple"
        return path, parsed["topic"], template_type, path.name

    resume_from = str(payload.get("draftResumeFrom") or payload.get("resumeFrom") or "").strip()
    if not resume_from:
        raise ValueError("Health Check 대상 문서를 선택해 주세요.")
    checkpoint_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / resume_from)
    if not checkpoint_path.exists() or not checkpoint_path.is_file():
        raise ValueError("작성 중단 초안의 체크포인트를 찾을 수 없습니다.")
    try:
        checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("작성 중단 초안의 체크포인트를 읽을 수 없습니다.") from exc
    if not isinstance(checkpoint_payload, Mapping):
        raise ValueError("작성 중단 초안의 체크포인트 형식이 올바르지 않습니다.")
    checkpoint = checkpoint_payload.get("checkpoint", {})
    spec = checkpoint_payload.get("spec", {})
    if not isinstance(checkpoint, Mapping):
        raise ValueError("작성 중단 초안의 체크포인트 정보가 올바르지 않습니다.")
    preview = latest_draft_preview_artifact(checkpoint, spec if isinstance(spec, Mapping) else None)
    if not preview or not preview.get("path"):
        raise ValueError("작성 중단 초안의 미리보기 파일이 아직 없어 Health Check를 실행할 수 없습니다.")
    preview_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / str(preview.get("path", "")))
    if not preview_path.exists() or not preview_path.is_file():
        raise ValueError("작성 중단 초안의 미리보기 파일을 찾을 수 없습니다.")
    topic = str(checkpoint.get("topic", "") or parse_policy_filename(preview_path.name)["topic"]).strip() or "-"
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    file_name = str(preview.get("name") or preview_path.name)
    return preview_path, topic, template_type, file_name


def normalize_dev_qa_action_check_items(items: List[Any]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_key = str(item.get("item_key") or item.get("key") or "").strip()
        if not item_key:
            continue
        normalized.append(
            {
                "item_key": item_key,
                "perspective": str(item.get("perspective") or item.get("group") or "").strip(),
                "priority": str(item.get("priority") or "").strip(),
                "action_type": str(item.get("action_type") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "target_location": str(item.get("target_location") or "").strip(),
                "current_content": str(item.get("current_content") or "").strip(),
                "desired_change": str(item.get("desired_change") or "").strip(),
                "recommendation": str(item.get("recommendation") or "").strip(),
                "user_note": str(item.get("note") or "").strip(),
            }
        )
    if not normalized:
        raise ValueError("확인할 보완 요청 항목을 찾을 수 없습니다.")
    return normalized


def save_manual_edit_from_payload(payload: Dict[str, Any]) -> Path:
    name = str(payload.get("name", "")).strip()
    edited_html = str(payload.get("html", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    save_mode = str(payload.get("saveMode", "new_version")).strip() or "new_version"
    base_hash = str(payload.get("baseHash", "") or payload.get("baseDocumentHash", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("수정할 정책서를 선택해 주세요.")
    if not edited_html or "<html" not in edited_html.casefold():
        raise ValueError("수정된 HTML 내용을 확인할 수 없습니다.")
    if save_mode not in {"new_version", "overwrite"}:
        raise ValueError("수정 저장 방식이 올바르지 않습니다.")

    old_path = policy_file_path(name)
    if not old_path.exists() or not old_path.is_file():
        raise ValueError("수정할 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(old_path)
    lock_info = acquire_document_job_lock(old_path.name, job_id=uuid.uuid4().hex, operation="manual_edit", session_id=session_id)
    try:
        old_html = old_path.read_text(encoding="utf-8")
        current_hash = document_content_hash(old_html)
        if base_hash and base_hash != current_hash:
            raise ValueError(
                "다른 사용자가 이 문서를 먼저 수정했습니다. 최신 문서를 다시 불러온 뒤 편집 내용을 다시 반영해 주세요."
            )
        normalized_html = normalize_manual_edit_html(old_html, edited_html)
        change_summary = summarize_html_change(old_html, normalized_html, "사용자 직접 편집")
        if save_mode == "overwrite":
            result = write_existing_policy_version(old_path, normalized_html, author, change_summary)
        else:
            result = write_new_policy_version(old_path, normalized_html, author, change_summary)
        update_document_lock(lock_info, "completed")
        return result
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def reference_html_file_path(raw_path_or_url: str) -> Path:
    raw_value = str(raw_path_or_url or "").strip()
    if not raw_value:
        raise ValueError("수정할 현황 분석 문서를 선택해 주세요.")

    parsed = urlparse(raw_value)
    raw_path = parsed.path or raw_value
    if raw_path.startswith("/output/"):
        relative = raw_path.removeprefix("/output/")
    elif raw_path.startswith("output/"):
        relative = raw_path.removeprefix("output/")
    else:
        relative = raw_path.lstrip("/")

    try:
        path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / unquote(relative))
        relative_path = path.relative_to(OUTPUT_ROOT.resolve())
    except (OSError, ValueError):
        raise ValueError("현황 분석 문서 경로가 허용 범위를 벗어났습니다.") from None

    if not relative_path.parts or relative_path.parts[0] != "reference_html":
        raise ValueError("현황 분석 문서만 직접 편집할 수 있습니다.")
    if path.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("HTML 현황 분석 문서만 직접 편집할 수 있습니다.")
    if not path.exists() or not path.is_file():
        raise ValueError("수정할 현황 분석 문서 파일을 찾을 수 없습니다.")
    return path


def describe_reference_html_file(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    try:
        relative = path.resolve().relative_to(OUTPUT_ROOT.resolve())
    except ValueError:
        relative = Path(path.name)
    try:
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        content_hash = ""
    return {
        "name": path.name,
        "path": str(relative),
        "url": f"/output/{quote(str(relative), safe='/')}",
        "size": stat.st_size,
        "contentHash": content_hash,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def normalize_reference_html_edit(old_html: str, edited_html: str) -> str:
    normalized = restore_mermaid_source_blocks(old_html, edited_html)
    normalized = normalize_browser_markup_noise(normalized)
    normalized = sanitize_policy_html(normalized)
    return normalized


def save_reference_html_edit_from_payload(payload: Dict[str, Any]) -> Path:
    raw_path = str(payload.get("url") or payload.get("path") or payload.get("name") or "").strip()
    edited_html = str(payload.get("html", "")).strip()
    save_mode = str(payload.get("saveMode", "overwrite")).strip() or "overwrite"
    base_hash = str(payload.get("baseHash", "") or payload.get("baseDocumentHash", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not edited_html or "<html" not in edited_html.casefold():
        raise ValueError("수정된 HTML 내용을 확인할 수 없습니다.")
    if save_mode != "overwrite":
        raise ValueError("현황 분석 문서는 현재 HTML에 바로 반영하는 방식만 지원합니다.")

    path = reference_html_file_path(raw_path)
    relative_name = str(path.relative_to(OUTPUT_ROOT.resolve()))
    lock_info = acquire_document_job_lock(
        relative_name,
        job_id=uuid.uuid4().hex,
        operation="reference_html_edit",
        session_id=session_id,
    )
    try:
        old_html = path.read_text(encoding="utf-8")
        current_hash = document_content_hash(old_html)
        if base_hash and base_hash != current_hash:
            raise ValueError(
                "다른 사용자가 이 현황 분석 문서를 먼저 수정했습니다. 최신 문서를 다시 불러온 뒤 편집 내용을 다시 반영해 주세요."
            )
        normalized_html = normalize_reference_html_edit(old_html, edited_html)
        path.write_text(normalized_html, encoding="utf-8")
        update_document_lock(lock_info, "completed")
        return path
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


DIAGRAM_EDIT_SECTIONS = {
    "actors": "actors",
    "usecases": "usecases",
    "states": "states",
    "stateTransitions": "state_transitions",
    "processes": "processes",
}


def policy_diagram_data_from_name(name: str) -> Dict[str, Any]:
    policy_path = policy_file_path(str(name or "").strip())
    spec, source = load_policy_spec_for_policy_path(policy_path)
    if spec is None:
        raise ValueError("선택한 정책서의 JSON spec을 찾을 수 없어 다이어그램을 편집할 수 없습니다.")
    return {
        "name": policy_path.name,
        "specSource": source.name if source else "",
        "actors": spec.get("actors", []),
        "usecases": spec.get("usecases", []),
        "states": spec.get("states", []),
        "stateTransitions": spec.get("state_transitions", []),
        "processes": spec.get("processes", []),
    }


def save_policy_diagram_edit_from_payload(payload: Dict[str, Any]) -> Path:
    name = str(payload.get("name", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    save_mode = str(payload.get("saveMode", "new_version")).strip() or "new_version"
    base_hash = str(payload.get("baseHash", "") or payload.get("baseDocumentHash", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("다이어그램을 편집할 정책서를 선택해 주세요.")
    if save_mode not in {"new_version", "overwrite"}:
        raise ValueError("다이어그램 저장 방식이 올바르지 않습니다.")

    old_path = policy_file_path(name)
    if not old_path.exists() or not old_path.is_file():
        raise ValueError("다이어그램을 편집할 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(old_path)
    spec, _source = load_policy_spec_for_policy_path(old_path)
    if spec is None:
        raise ValueError("선택한 정책서의 JSON spec을 찾을 수 없어 다이어그램을 편집할 수 없습니다.")

    diagram_payload = payload.get("diagram") if isinstance(payload.get("diagram"), Mapping) else payload.get("diagrams")
    if not isinstance(diagram_payload, Mapping):
        raise ValueError("저장할 다이어그램 데이터가 없습니다.")

    lock_info = acquire_document_job_lock(old_path.name, job_id=uuid.uuid4().hex, operation="diagram_edit", session_id=session_id)
    try:
        old_html = old_path.read_text(encoding="utf-8")
        current_hash = document_content_hash(old_html)
        if base_hash and base_hash != current_hash:
            raise ValueError(
                "다른 사용자가 이 문서를 먼저 수정했습니다. 최신 문서를 다시 불러온 뒤 다이어그램 편집 내용을 다시 반영해 주세요."
            )

        target_path = old_path if save_mode == "overwrite" else next_policy_version_path(old_path)
        target_version = parse_policy_filename(target_path.name).get("version", "")
        updated_spec = apply_diagram_payload_to_spec(spec, diagram_payload)
        prepare_policy_spec_for_diagram_save(
            updated_spec,
            target_path=target_path,
            version=target_version,
            author=author,
            change_summary="다이어그램 원천 데이터 수정 및 산출물 재생성",
        )
        write_policy_document_from_spec(updated_spec, target_path)
        update_document_lock(lock_info, "completed")
        return target_path
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def load_policy_spec_for_policy_path(policy_path: Path) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
    parsed = parse_policy_filename(policy_path.name)
    topic = str(parsed.get("topic", "") or "").strip()
    candidates = [
        policy_version_spec_path(policy_path),
        OUTPUT_ROOT / "checkpoints" / f"{policy_path.stem}_latest_checkpoint.json",
        topic_policy_spec_path(topic),
    ]
    for candidate in candidates:
        spec = read_policy_spec_payload(candidate)
        if spec is not None:
            return spec, candidate
    return None, None


def apply_diagram_payload_to_spec(spec: Mapping[str, Any], payload: Mapping[str, Any]) -> Dict[str, Any]:
    updated: Dict[str, Any] = json.loads(json.dumps(spec, ensure_ascii=False))
    changed_sections = 0
    for payload_key, spec_key in DIAGRAM_EDIT_SECTIONS.items():
        if payload_key not in payload:
            continue
        rows = payload.get(payload_key)
        if not isinstance(rows, list):
            raise ValueError(f"{diagram_section_label(payload_key)} 데이터는 배열이어야 합니다.")
        updated[spec_key] = normalize_diagram_rows(payload_key, rows)
        changed_sections += 1
    if changed_sections == 0:
        raise ValueError("수정할 다이어그램 섹션이 없습니다.")
    validate_diagram_spec_links(updated)
    return updated


def normalize_diagram_rows(section: str, rows: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"{diagram_section_label(section)} {index}행은 객체여야 합니다.")
        item: Dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                continue
            if isinstance(value, list):
                item[str(key)] = [str(part).strip() for part in value if str(part).strip()]
            elif isinstance(value, Mapping):
                item[str(key)] = dict(value)
            else:
                item[str(key)] = str(value).strip()
        if section == "stateTransitions":
            item["current_state"] = str(item.get("current_state") or item.get("from") or "").strip()
            item["next_state"] = str(item.get("next_state") or item.get("to") or "").strip()
            item["from"] = item["current_state"]
            item["to"] = item["next_state"]
            item["usecase_ids"] = normalize_id_list(item.get("usecase_ids") or item.get("usecaseIds") or [])
        if section == "usecases":
            item["process_target"] = normalize_process_target(item.get("process_target") or item.get("processTarget"))
        if section == "processes":
            item["related_functions"] = normalize_id_list(item.get("related_functions") or item.get("relatedFunctions") or [])
            item["related_policies"] = normalize_id_list(item.get("related_policies") or item.get("relatedPolicies") or [])
        require_diagram_fields(section, item, index)
        normalized.append(item)
    return normalized


def normalize_id_list(value: Any) -> List[str]:
    if isinstance(value, str):
        parts = re.split(r"\s*(?:,|/|\n)\s*", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def normalize_process_target(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in {"Y", "YES", "TRUE", "1", "대상"}:
        return "Y"
    if normalized in {"N", "NO", "FALSE", "0", "비대상"}:
        return "N"
    return normalized or "N"


def require_diagram_fields(section: str, item: Mapping[str, Any], index: int) -> None:
    required_by_section = {
        "actors": ("id", "name"),
        "usecases": ("id", "name", "actor"),
        "states": ("id", "name"),
        "stateTransitions": ("current_state", "event", "next_state"),
        "processes": ("id", "usecase_id", "name"),
    }
    for key in required_by_section.get(section, ()):
        if not str(item.get(key, "")).strip():
            raise ValueError(f"{diagram_section_label(section)} {index}행의 {key} 값이 비어 있습니다.")


def validate_diagram_spec_links(spec: Mapping[str, Any]) -> None:
    actor_names = {str(item.get("name", "")).strip() for item in spec.get("actors", []) if isinstance(item, Mapping)}
    if actor_names:
        missing_actors = sorted(
            {
                str(item.get("actor", "")).strip()
                for item in spec.get("usecases", [])
                if isinstance(item, Mapping) and str(item.get("actor", "")).strip() and str(item.get("actor", "")).strip() not in actor_names
            }
        )
        if missing_actors:
            raise ValueError(f"유즈케이스 액터가 액터 목록에 없습니다: {', '.join(missing_actors[:5])}")

    usecase_ids = {str(item.get("id", "")).strip() for item in spec.get("usecases", []) if isinstance(item, Mapping)}
    if usecase_ids:
        missing_process_usecases = sorted(
            {
                str(item.get("usecase_id", "")).strip()
                for item in spec.get("processes", [])
                if isinstance(item, Mapping) and str(item.get("usecase_id", "")).strip() and str(item.get("usecase_id", "")).strip() not in usecase_ids
            }
        )
        if missing_process_usecases:
            raise ValueError(f"프로세스의 유즈케이스 ID가 유즈케이스 목록에 없습니다: {', '.join(missing_process_usecases[:5])}")

    state_names = {str(item.get("name", "")).strip() for item in spec.get("states", []) if isinstance(item, Mapping)}
    if state_names:
        missing_states = sorted(
            {
                state
                for item in spec.get("state_transitions", [])
                if isinstance(item, Mapping)
                for state in (str(item.get("current_state", "")).strip(), str(item.get("next_state", "")).strip())
                if state and state not in state_names
            }
        )
        if missing_states:
            raise ValueError(f"상태 전이의 상태명이 상태 코드 목록에 없습니다: {', '.join(missing_states[:5])}")


def prepare_policy_spec_for_diagram_save(
    spec: Dict[str, Any],
    *,
    target_path: Path,
    version: str,
    author: str,
    change_summary: str,
) -> None:
    parsed = parse_policy_filename(target_path.name)
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["version"] = version
        meta["topic_slug"] = parsed.get("topic", "")
        meta["version_spec_file"] = policy_version_spec_path(target_path).name
        meta["version_spec_saved_at"] = datetime.now().isoformat(timespec="seconds")
        meta["version_spec_saved_by"] = author
        meta["version_spec_reason"] = "diagram_edit"
    history = spec.setdefault("history", [])
    if isinstance(history, list):
        history.append(
            {
                "version": version or "수동 수정",
                "change": compact_history_text(change_summary),
                "date": datetime.now().date().isoformat(),
                "author": author,
            }
        )


def write_policy_document_from_spec(spec: Dict[str, Any], target_path: Path) -> None:
    parsed = parse_policy_filename(target_path.name)
    template_type = "full" if parsed.get("template_label") == "Full" else "simple"
    template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
    template_html = template_path.read_text(encoding="utf-8")
    stage_key = "full" if template_type == "full" else "10"
    document = normalize_sentence_breaks(render_policy_html(spec, template_html, template_type, stage_key))
    target_path.write_text(document, encoding="utf-8")

    spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
    policy_version_spec_path(target_path).write_text(spec_json, encoding="utf-8")
    topic_slug = str(parsed.get("topic") or "").strip()
    if topic_slug and topic_slug != "-":
        topic_policy_spec_path(topic_slug).write_text(spec_json, encoding="utf-8")
    bpmn_path = OUTPUT_ROOT / f"{target_path.stem}_전체업무흐름도.bpmn"
    write_bpmn_artifacts(spec, bpmn_path)


def diagram_section_label(section: str) -> str:
    return {
        "actors": "액터",
        "usecases": "유즈케이스",
        "states": "상태",
        "stateTransitions": "상태 전이",
        "processes": "프로세스",
    }.get(section, section)


def upload_policy_html_from_payload(payload: Dict[str, Any]) -> Path:
    original_name = str(payload.get("name", "")).strip()
    base_name = str(payload.get("baseName", "") or payload.get("targetName", "") or payload.get("policyName", "")).strip()
    uploaded_html = str(payload.get("html", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not original_name:
        raise ValueError("등록할 HTML 파일명을 확인할 수 없습니다.")
    validate_upload_html_source_name(original_name)
    if not base_name:
        raise ValueError("HTML을 등록할 기준 정책서를 선택해 주세요.")
    if not uploaded_html or "<html" not in uploaded_html.casefold():
        raise ValueError("등록할 HTML 파일 내용을 확인할 수 없습니다.")
    if len(uploaded_html.encode("utf-8")) > HTML_UPLOAD_MAX_BYTES:
        raise ValueError("HTML 파일은 10MB 이하만 등록할 수 있습니다.")

    base_path = policy_file_path(base_name)
    if not base_path.exists() or not base_path.is_file():
        raise ValueError("HTML을 등록할 기준 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(base_path)

    lock_info = acquire_document_job_lock(base_path.name, job_id=uuid.uuid4().hex, operation="html_upload", session_id=session_id)
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        target_path = next_policy_version_path(base_path)
        normalized_html = normalize_browser_markup_noise(uploaded_html)
        normalized_html = normalize_uploaded_policy_identity(
            normalized_html,
            target_path,
            author=str(payload.get("author", "") or "Policy Web"),
        )
        normalized_html = sanitize_policy_html(normalized_html)
        target_path.write_text(normalized_html, encoding="utf-8")
        sync_policy_version_spec_from_base(
            base_path,
            target_path,
            author=str(payload.get("author", "") or "Policy Web"),
            reason="html_upload",
        )
        update_document_lock(lock_info, "completed")
        return target_path
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def upload_policy_json_from_payload(payload: Dict[str, Any]) -> Path:
    original_name = str(payload.get("name", "")).strip()
    base_name = str(payload.get("baseName", "") or payload.get("targetName", "") or payload.get("policyName", "")).strip()
    uploaded_json = payload.get("json")
    author = str(payload.get("author", "") or "Policy Web")
    session_id = client_session_id_from_payload(payload)
    if not original_name:
        raise ValueError("등록할 JSON 파일명을 확인할 수 없습니다.")
    validate_upload_json_source_name(original_name)
    if not base_name:
        raise ValueError("JSON을 등록할 기준 정책서를 선택해 주세요.")
    if not isinstance(uploaded_json, str) or not uploaded_json.strip():
        raise ValueError("등록할 JSON 파일 내용을 확인할 수 없습니다.")
    if len(uploaded_json.encode("utf-8")) > JSON_UPLOAD_MAX_BYTES:
        raise ValueError("JSON 파일은 10MB 이하만 등록할 수 있습니다.")

    base_path = policy_file_path(base_name)
    if not base_path.exists() or not base_path.is_file():
        raise ValueError("JSON을 등록할 기준 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(base_path)

    lock_info = acquire_document_job_lock(base_path.name, job_id=uuid.uuid4().hex, operation="json_upload", session_id=session_id)
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        target_path = next_policy_version_path(base_path)
        spec = policy_spec_from_uploaded_json(uploaded_json)
        normalize_uploaded_policy_spec_identity(
            spec,
            base_path=base_path,
            target_path=target_path,
            original_name=original_name,
            author=author,
        )
        warnings = validate_uploaded_policy_spec(spec)
        meta = spec.setdefault("meta", {})
        if warnings:
            meta["json_upload_validation_warnings"] = warnings[:20]
            meta["json_upload_validation_warning_count"] = len(warnings)
        else:
            meta.pop("json_upload_validation_warnings", None)
            meta.pop("json_upload_validation_warning_count", None)

        parsed = parse_policy_filename(target_path.name)
        template_type = "full" if parsed.get("template_label") == "Full" else "simple"
        template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
        template_html = template_path.read_text(encoding="utf-8")
        document = normalize_sentence_breaks(render_policy_html(spec, template_html, template_type, "full"))
        target_path.write_text(document, encoding="utf-8")

        spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
        policy_version_spec_path(target_path).write_text(spec_json, encoding="utf-8")
        topic_policy_spec_path(parsed["topic"]).write_text(spec_json, encoding="utf-8")
        bpmn_path = OUTPUT_ROOT / f"{target_path.stem}_전체업무흐름도.bpmn"
        write_bpmn_artifacts(spec, bpmn_path)
        update_document_lock(lock_info, "completed")
        return target_path
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def policy_spec_from_uploaded_json(uploaded_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(uploaded_json)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON 파일 형식이 올바르지 않습니다.") from exc
    if isinstance(payload, dict) and isinstance(payload.get("spec"), dict):
        payload = payload["spec"]
    if not isinstance(payload, dict):
        raise ValueError("정책서 JSON은 객체이거나 spec 객체를 포함해야 합니다.")
    ensure_policy_spec_base_keys(payload)
    return payload


def normalize_uploaded_policy_spec_identity(
    spec: Dict[str, Any],
    *,
    base_path: Path,
    target_path: Path,
    original_name: str,
    author: str,
) -> None:
    base_parsed = parse_policy_filename(base_path.name)
    target_parsed = parse_policy_filename(target_path.name)
    topic = str(target_parsed.get("topic") or base_parsed.get("topic") or "").strip()
    version = str(target_parsed.get("version") or "").strip()
    template_label = str(target_parsed.get("template_label") or "").strip()
    template_type = "full" if template_label == "Full" else "simple"
    if not topic or topic == "-" or not version or version == "-":
        raise ValueError("기준 정책서의 주제와 버전을 확인할 수 없습니다.")

    meta = spec.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise ValueError("정책서 JSON의 meta는 객체여야 합니다.")

    uploaded_template_type = str(meta.get("template_type", "") or "").strip().casefold()
    if uploaded_template_type in {"simple", "full"} and uploaded_template_type != template_type:
        raise ValueError("업로드 JSON의 문서 유형이 선택한 기준 정책서와 다릅니다.")

    for candidate in (meta.get("topic"), meta.get("topic_slug"), meta.get("topic_display")):
        candidate_text = str(candidate or "").strip()
        if candidate_text and normalize_topic_key(candidate_text) != normalize_topic_key(topic):
            raise ValueError("업로드 JSON의 주제가 선택한 기준 정책서와 다릅니다.")

    base_spec = read_policy_spec_payload(policy_version_spec_path(base_path)) or read_policy_spec_payload(topic_policy_spec_path(topic))
    base_meta = base_spec.get("meta", {}) if isinstance(base_spec, Mapping) else {}
    business_code = (
        str(base_meta.get("business_code", "")).strip()
        or str(meta.get("business_code", "")).strip()
        or make_business_code(topic)
    )
    document_type = f"{template_label} 버전" if template_label and template_label != "-" else str(meta.get("document_type", "") or "")

    meta["topic"] = topic
    meta["topic_display"] = str(meta.get("topic_display") or topic).strip()
    meta["topic_slug"] = topic
    meta["template_type"] = template_type
    meta["document_type"] = document_type
    meta["business_code"] = business_code
    meta["module_id"] = str(meta.get("module_id") or base_meta.get("module_id") or f"PM-{business_code}").strip()
    meta["document_id"] = str(meta.get("document_id") or base_meta.get("document_id") or f"POL-{business_code}").strip()
    meta["status"] = str(meta.get("status") or base_meta.get("status") or "작성중").strip()
    meta["version"] = version
    meta["date"] = str(meta.get("date") or datetime.now().date().isoformat()).strip()
    meta["author"] = str(meta.get("author") or author).strip()
    if not meta.get("authoring_basis"):
        meta["authoring_basis"] = base_meta.get("authoring_basis") or ["JSON 업로드 파일을 서버 템플릿으로 렌더링해 정책서 새 버전으로 등록한다."]
    meta["version_spec_file"] = policy_version_spec_path(target_path).name
    meta["version_spec_saved_at"] = datetime.now().isoformat(timespec="seconds")
    meta["version_spec_saved_by"] = author
    meta["version_spec_reason"] = "json_upload"
    meta["version_spec_source"] = original_name

    append_json_upload_history(spec, version, author)


def append_json_upload_history(spec: Dict[str, Any], version: str, author: str) -> None:
    history = spec.get("history")
    if not isinstance(history, list):
        history = []
        spec["history"] = history
    history.append(
        {
            "version": version,
            "change": "JSON 파일 업로드로 서버 템플릿, SVG, BPMN 뷰어를 재생성해 새 버전을 등록했습니다.",
            "date": datetime.now().date().isoformat(),
            "author": author,
        }
    )


def validate_uploaded_policy_spec(spec: Dict[str, Any]) -> List[str]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    business_code = str(meta.get("business_code", "") or "").strip()
    validation = validate_policy_spec(spec, business_code)
    critical_validation = validate_stage_critical(spec, business_code, "full")
    errors = [*validation.errors, *critical_validation.errors]
    return [str(error) for error in errors]


def json_upload_validation_warnings(policy_path: Path) -> List[str]:
    spec = read_policy_spec_payload(policy_version_spec_path(policy_path))
    meta = spec.get("meta", {}) if isinstance(spec, Mapping) else {}
    warnings = meta.get("json_upload_validation_warnings") if isinstance(meta, Mapping) else None
    if not isinstance(warnings, list):
        return []
    return [str(warning) for warning in warnings]


def validate_upload_html_source_name(original_name: str) -> None:
    if "/" in original_name or "\\" in original_name:
        raise ValueError("HTML 파일명이 올바르지 않습니다.")
    safe_name = Path(original_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("HTML 파일명이 올바르지 않습니다.")
    suffix = Path(safe_name).suffix.casefold()
    if suffix not in {".html", ".htm"}:
        raise ValueError("HTML 파일(.html 또는 .htm)만 등록할 수 있습니다.")


def validate_upload_json_source_name(original_name: str) -> None:
    if "/" in original_name or "\\" in original_name:
        raise ValueError("JSON 파일명이 올바르지 않습니다.")
    safe_name = Path(original_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("JSON 파일명이 올바르지 않습니다.")
    if Path(safe_name).suffix.casefold() != ".json":
        raise ValueError("JSON 파일(.json)만 등록할 수 있습니다.")


def normalize_uploaded_policy_identity(document: str, target_path: Path, author: str) -> str:
    parsed = parse_policy_filename(target_path.name)
    topic = str(parsed.get("topic") or "").strip()
    template_label = str(parsed.get("template_label") or "").strip()
    version = str(parsed.get("version") or "").strip()
    if not topic or topic == "-" or not version or version == "-":
        return document

    document_type = f"{template_label} 버전" if template_label and template_label != "-" else ""
    updated = document
    title_text = " ".join(part for part in [f"{topic} 정책서", document_type, version] if part)
    updated = replace_single_html_tag_text(updated, "title", title_text)
    updated = replace_single_html_tag_text(updated, "h1", f"{topic} 정책서")
    if document_type:
        updated = replace_policy_meta_cell(updated, "문서 구분", document_type)
        updated = replace_policy_eyebrow(updated, document_type)
    updated = replace_policy_meta_cell(updated, "버전", version)
    return append_document_history_entry(updated, version, author, "HTML 파일 업로드로 서버 기준 새 버전을 등록했습니다.")


def replace_single_html_tag_text(document: str, tag: str, text: str) -> str:
    escaped = html.escape(text)
    pattern = rf"(<{tag}\b[^>]*>).*?(</{tag}>)"
    if re.search(pattern, document, flags=re.DOTALL | re.IGNORECASE):
        return re.sub(pattern, lambda m: m.group(1) + escaped + m.group(2), document, count=1, flags=re.DOTALL | re.IGNORECASE)
    if tag.casefold() == "title" and re.search(r"</head>", document, flags=re.IGNORECASE):
        return re.sub(r"</head>", f"<title>{escaped}</title></head>", document, count=1, flags=re.IGNORECASE)
    return document


def replace_policy_eyebrow(document: str, document_type: str) -> str:
    pattern = r"(<div\b(?=[^>]*\bclass=[\"'][^\"']*\beyebrow\b[^\"']*[\"'])[^>]*>).*?(</div>)"
    text = html.escape(f"NOVA 통합채널 정책서 {document_type}")
    return re.sub(pattern, lambda m: m.group(1) + text + m.group(2), document, count=1, flags=re.DOTALL | re.IGNORECASE)


def replace_policy_meta_cell(document: str, label: str, value: str) -> str:
    escaped = html.escape(value)
    pattern = (
        rf"(<tr>\s*<th\b[^>]*>\s*{re.escape(label)}\s*</th>\s*"
        rf"<td\b[^>]*>).*?(</td>\s*</tr>)"
    )
    return re.sub(pattern, lambda m: m.group(1) + escaped + m.group(2), document, count=1, flags=re.DOTALL | re.IGNORECASE)


def revise_policy_from_payload(payload: Dict[str, Any], progress_callback=None, review_callback=None) -> Path:
    name = str(payload.get("name", "")).strip()
    instruction = str(payload.get("instruction", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    old_path = policy_file_path(name)
    if not old_path.exists() or not old_path.is_file():
        raise ValueError("수정할 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(old_path)
    old_html = old_path.read_text(encoding="utf-8")
    selection = revision_selection_from_payload(payload)
    save_mode = revision_save_mode_from_payload(payload, selection)

    emit_job_progress(progress_callback, "stage_start", "00", "intent", "수정 의도 분석", revision_stage_message("intent", "start"))
    base_client = llm_client_from_web_payload(payload)
    if llm_preflight_enabled() and base_client.enabled:
        emit_job_progress(
            progress_callback,
            "stage_update",
            "00",
            "intent",
            "LLM 연결 점검",
            "수정 요청을 분석하기 전에 LLM 연결을 작은 호출로 먼저 확인합니다.",
            preview={
                "title": "수정 작업 LLM 연결 점검",
                "items": [
                    f"모델: {base_client.model}",
                    "연결 실패 시 수정 본문을 건드리지 않고 중단합니다.",
                ],
            },
        )
        base_client.preflight_check()
    client = client_for_revision_request(base_client, instruction, selection)
    parsed = parse_policy_filename(old_path.name)
    template_type = "full" if parsed["template_label"] == "Full" else "simple"
    template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
    template_html = template_path.read_text(encoding="utf-8")
    sample_htmls = load_sample_htmls(template_type)
    guideline = build_agent_guideline(template_html, sample_htmls)
    target_sections = revision_context_sections(instruction, selection)
    try:
        intent = client.generate_json(
            schema_name="revision_intent",
            schema=revision_schema(instruction, selection),
            instructions=revision_instructions(
                parsed["topic"],
                template_type,
                revision_agent_guidelines(guideline, template_type, target_sections),
                instruction,
                selection,
            ),
            input_messages=[
                {
                    "role": "user",
                    "content": revision_prompt(old_html, instruction, selection),
                }
            ],
        )
    except Exception as exc:
        if not is_recoverable_llm_generation_error(exc):
            raise
        intent = fallback_revision_intent(instruction, exc)
    intent = constrain_revision_plan_scope(intent, instruction, selection)
    emit_job_progress(
        progress_callback,
        "stage_complete",
        "00",
        "intent",
        "수정 의도 분석",
        revision_stage_message("intent", "complete"),
        preview={
            "title": "수정 의도 분석 결과",
            "items": [
                str(intent.get("summary", "")).strip() or "수정 요청을 분석했습니다.",
                "선택 영역 우선 수정" if selection else "",
                "대상 장: " + ", ".join(revision_target_sections(intent)[:6]),
            ],
        },
    )

    emit_job_progress(progress_callback, "stage_start", "01", "revise", "수정 Agent", revision_stage_message("revise", "start"))
    revised_html, applied_count = apply_revision_plan(old_html, intent, instruction, selection)
    revised_html, structural_changes = apply_structural_revision(revised_html, instruction)
    if applied_count == 0 and not structural_changes:
        revised_html = append_revision_section(revised_html, intent, instruction)
    revised_html = sanitize_policy_html(revised_html)
    emit_job_progress(
        progress_callback,
        "stage_complete",
        "01",
        "revise",
        "수정 Agent",
        revision_stage_message("revise", "complete"),
        preview={
            "title": "수정 Agent 적용 결과",
            "items": [
                f"문장 치환 {applied_count}건 적용",
                f"구조 보정 {len(structural_changes)}건 적용",
                str(intent.get("history_change", "")).strip() or "수정 요청 내용을 본문에 반영했습니다.",
            ],
        },
    )

    new_path = old_path if save_mode == "current_version" else next_policy_version_path(old_path)
    next_version = parse_policy_filename(new_path.name)["version"]

    report = None
    baseline_report = None
    for attempt in range(1, 3):
        emit_job_progress(
            progress_callback,
            "stage_start",
            "02",
            "inspect",
            "수정본 검수",
            f"{revision_stage_message('inspect', 'start')} {attempt}회차 검수입니다.",
            attempt=attempt,
        )
        report = inspect_policy_document(
            revised_html,
            template_html=template_html,
            sample_htmls=sample_htmls,
            template_type=template_type,
            scope="full",
            topic=parsed["topic"],
            density_profile=load_policy_density_profile(old_path),
            llm_client=client_for_stage_inspector(base_client, final=True, attempt=attempt),
            llm_required=True,
        )
        save_inspection_report(report, new_path.name, f"revision_attempt{attempt}")
        passed = revision_inspection_strict_pass(report)
        if passed:
            emit_job_progress(
                progress_callback,
                "stage_complete",
                "02",
                "inspect",
                "수정본 검수",
                f"{revision_stage_message('inspect', 'complete')} 점수 {report.score}점입니다.",
                attempt=attempt,
                score=report.score,
                threshold=DEFAULT_INSPECTOR_MIN_SCORE,
                preview={
                    "title": "수정본 Inspector 결과",
                    "items": [report.summary, f"점수 {report.score}점 / 기준 {DEFAULT_INSPECTOR_MIN_SCORE}점"],
                },
            )
            break
        if attempt == 2:
            baseline_report = baseline_report or inspect_policy_document(
                old_html,
                template_html=template_html,
                sample_htmls=sample_htmls,
                template_type=template_type,
                scope="full",
                topic=parsed["topic"],
                density_profile=load_policy_density_profile(old_path),
                llm_client=client_for_stage_inspector(base_client, final=True, attempt=attempt + 10),
                llm_required=True,
            )
            save_inspection_report(baseline_report, old_path.name, "revision_baseline")
            if callable(review_callback):
                decision = review_callback(
                    revision_inspection_review_payload(
                        old_path=old_path,
                        new_path=new_path,
                        save_mode=save_mode,
                        baseline_report=baseline_report,
                        revised_report=report,
                    )
                )
                if str(decision.get("action", "")).casefold() == "continue":
                    emit_job_progress(
                        progress_callback,
                        "stage_complete",
                        "02",
                        "inspect",
                        "수정본 검수",
                        f"사용자가 낮은 점수를 확인하고 저장을 선택했습니다. 점수 {report.score}점입니다.",
                        attempt=attempt,
                        score=report.score,
                        threshold=DEFAULT_INSPECTOR_MIN_SCORE,
                        preview={
                            "title": "수정본 저장 확인 완료",
                            "items": [
                                f"기존 {baseline_report.score}점 → 수정본 {report.score}점",
                                "남은 보완 필요 사항은 문서 검수 또는 Health Check에서 이어서 관리합니다.",
                            ],
                        },
                    )
                    break
                raise JobCancelled("사용자가 Inspector 기준 미달 수정본 저장을 중단했습니다.")
            if revision_delta_acceptable(baseline_report, report):
                emit_job_progress(
                    progress_callback,
                    "stage_complete",
                    "02",
                    "inspect",
                    "수정본 검수",
                    (
                        "수정본에 기존 문서의 남은 보완 이슈가 있으나, "
                        f"기존 대비 악화 없이 저장 가능한 수준입니다. 점수 {report.score}점입니다."
                    ),
                    attempt=attempt,
                    score=report.score,
                    threshold=DEFAULT_INSPECTOR_MIN_SCORE,
                    preview={
                        "title": "수정본 Inspector 결과",
                        "items": [
                            "기존 문서보다 점수나 P1/error가 악화되지 않았습니다.",
                            f"기존 {baseline_report.score}점 → 수정본 {report.score}점",
                            "남은 이슈는 별도 문서 검수 또는 Health Check 보완 대상으로 유지합니다.",
                        ],
                    },
                )
                break
            emit_job_progress(
                progress_callback,
                "stage_error",
                "02",
                "inspect",
                "수정본 검수",
                f"{revision_stage_message('inspect', 'error')} 점수 {report.score}점입니다.",
                attempt=attempt,
                score=report.score,
                threshold=DEFAULT_INSPECTOR_MIN_SCORE,
            )
            candidate_change_summary = structural_revision_history(structural_changes) or str(
                intent.get("history_change") or intent.get("summary") or ""
            ).strip()
            if not candidate_change_summary:
                candidate_change_summary = summarize_html_change(old_html, revised_html, f"수정 요청 반영: {instruction}")
            raise RevisionInspectorGateError(
                f"수정본이 Inspector 기준을 통과하지 못했습니다. 점수 {report.score}점 / 기준 {DEFAULT_INSPECTOR_MIN_SCORE}점",
                old_path=old_path,
                new_path=new_path,
                revised_html=revised_html,
                author=author,
                change_summary=candidate_change_summary,
                score=report.score,
                threshold=DEFAULT_INSPECTOR_MIN_SCORE,
                save_mode=save_mode,
            )
        emit_job_progress(
            progress_callback,
            "stage_retry",
            "02",
            "inspect",
            "수정본 검수",
            revision_stage_message("inspect", "retry"),
            attempt=attempt,
            score=report.score,
            threshold=DEFAULT_INSPECTOR_MIN_SCORE,
        )
        try:
            refinement_client = client_for_revision_request(base_client, instruction, selection, attempt=attempt + 1)
            refinement = refinement_client.generate_json(
                schema_name="revision_refinement",
                schema=revision_schema(instruction, selection),
                instructions=revision_instructions(
                    parsed["topic"],
                    template_type,
                    revision_agent_guidelines(guideline, template_type, target_sections),
                    instruction,
                    selection,
                ),
                input_messages=[
                    {
                        "role": "user",
                        "content": revision_refinement_prompt(revised_html, instruction, revision_feedback(report), selection),
                    }
                ],
            )
        except Exception as exc:
            if not is_recoverable_llm_generation_error(exc):
                raise
            refinement = fallback_revision_intent("Inspector 보완 요청 반영: " + instruction, exc)
        refinement = constrain_revision_plan_scope(refinement, instruction, selection)
        revised_html, refined_count = apply_revision_plan(revised_html, refinement, instruction, selection)
        revised_html, refined_structural_changes = apply_structural_revision(revised_html, instruction)
        structural_changes.extend(refined_structural_changes)
        if refined_count == 0 and not refined_structural_changes:
            revised_html = append_revision_section(revised_html, refinement, instruction)
        revised_html = sanitize_policy_html(revised_html)

    emit_job_progress(progress_callback, "stage_start", "03", "history", "문서 히스토리 업데이트", revision_stage_message("history", "start"))
    change_summary = structural_revision_history(structural_changes) or str(
        intent.get("history_change") or intent.get("summary") or ""
    ).strip()
    if not change_summary:
        change_summary = summarize_html_change(old_html, revised_html, f"수정 요청 반영: {instruction}")
    revised_html = sanitize_policy_html(update_document_version_and_history(revised_html, old_path.name, next_version, author, change_summary))
    emit_job_progress(
        progress_callback,
        "stage_complete",
        "03",
        "history",
        "문서 히스토리 업데이트",
        revision_stage_message("history", "complete"),
        preview={"title": "문서 히스토리", "items": [f"{next_version}: {change_summary}"]},
    )

    save_label = revision_save_stage_label(save_mode)
    emit_job_progress(progress_callback, "stage_start", "04", "save", save_label, revision_stage_message("save", "start"))
    if save_mode == "current_version":
        backup_policy_html_before_overwrite(new_path, reason="agent_revision_current_version")
    new_path.write_text(revised_html, encoding="utf-8")
    sync_policy_version_spec_from_base(old_path, new_path, author=author, reason=f"agent_revision_{save_mode}")
    emit_job_progress(
        progress_callback,
        "stage_complete",
        "04",
        "save",
        save_label,
        revision_stage_message("save", "complete"),
        artifact=output_artifact_payload(new_path),
        preview={"title": revision_save_preview_title(save_mode), "items": [new_path.name]},
    )
    return new_path


def revision_inspection_review_payload(
    *,
    old_path: Path,
    new_path: Path,
    baseline_report: Any,
    revised_report: Any,
    save_mode: str = "new_version",
) -> Dict[str, Any]:
    pending_save_text = (
        f"저장 예정: 현재 버전에 누적 반영 ({old_path.name})"
        if save_mode == "current_version"
        else f"저장 예정 버전: {new_path.name}"
    )
    return {
        "stage_key": "02",
        "stage_name": "inspect",
        "stage_label": "수정본 검수",
        "review_type": "revision_inspection_gate",
        "attempt": 2,
        "score": getattr(revised_report, "score", None),
        "threshold": DEFAULT_INSPECTOR_MIN_SCORE,
        "passed": False,
        "message": (
            "수정본이 Inspector 기준 점수보다 낮습니다. "
            "점수와 남은 보완 필요 사항을 확인한 뒤 저장 여부를 선택해 주세요."
        ),
        "preview": {
            "title": "수정본 Inspector 기준 미달",
            "items": [
                f"기존 문서: {old_path.name}",
                pending_save_text,
                f"기존 점수 {getattr(baseline_report, 'score', 'N/A')}점 → 수정본 점수 {getattr(revised_report, 'score', 'N/A')}점",
                *revision_review_finding_summaries(revised_report),
            ],
        },
    }


def revision_review_finding_summaries(report: Any, limit: int = 5) -> List[str]:
    findings = list(getattr(report, "findings", []) or [])
    if not findings:
        return ["세부 finding 없이 기준 점수만 미달했습니다."]
    summaries = []
    for finding in findings[:limit]:
        severity = str(getattr(finding, "severity", "") or "").upper()
        category = str(getattr(finding, "category", "") or "").strip()
        title = str(getattr(finding, "title", "") or "").strip()
        detail = str(getattr(finding, "detail", "") or "").strip()
        summaries.append(limit_text(f"{severity} · {category} · {title}: {detail}", 240))
    if len(findings) > limit:
        summaries.append(f"외 {len(findings) - limit}건의 보완 필요 사항이 있습니다.")
    return summaries


def revision_inspection_strict_pass(report: Any) -> bool:
    return int(getattr(report, "score", 0) or 0) >= DEFAULT_INSPECTOR_MIN_SCORE and not any(
        str(getattr(finding, "severity", "") or "").lower() == "error"
        for finding in getattr(report, "findings", []) or []
    )


def revision_delta_acceptable(baseline_report: Any, revised_report: Any) -> bool:
    """Allow saving scoped revisions when remaining failures are pre-existing.

    A revision request usually changes one narrow part of a policy document. If
    the whole document was already below the final Inspector threshold, blocking
    every small revision makes the editor unusable. We still reject changes that
    lower the score or introduce new blocking findings.
    """

    baseline_score = int(getattr(baseline_report, "score", 0) or 0)
    revised_score = int(getattr(revised_report, "score", 0) or 0)
    if revised_score < baseline_score:
        return False
    return not revision_new_blocking_findings(baseline_report, revised_report)


def revision_new_blocking_findings(baseline_report: Any, revised_report: Any) -> List[Any]:
    baseline_keys = {
        revision_blocking_finding_key(finding)
        for finding in getattr(baseline_report, "findings", []) or []
        if revision_is_blocking_finding(finding)
    }
    return [
        finding
        for finding in getattr(revised_report, "findings", []) or []
        if revision_is_blocking_finding(finding) and revision_blocking_finding_key(finding) not in baseline_keys
    ]


def revision_is_blocking_finding(finding: Any) -> bool:
    severity = str(getattr(finding, "severity", "") or "").lower()
    tier = str(getattr(finding, "tier", "") or "").upper()
    title_text = f"{getattr(finding, 'category', '')} {getattr(finding, 'title', '')} {getattr(finding, 'detail', '')}"
    return severity == "error" or tier == "P1" or any(
        keyword in title_text
        for keyword in (
            "필수 장 누락",
            "템플릿 구조",
            "연결성",
            "정책 구체성",
            "요구사항",
            "상태 전이",
            "프로세스 관련",
            "정책 상세",
        )
    )


def revision_blocking_finding_key(finding: Any) -> tuple[str, str, str]:
    return (
        normalize_revision_finding_text(str(getattr(finding, "severity", "") or "")),
        normalize_revision_finding_text(str(getattr(finding, "category", "") or "")),
        normalize_revision_finding_text(str(getattr(finding, "title", "") or "")),
    )


def normalize_revision_finding_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def emit_job_progress(callback, event: str, stage_key: str, stage_name: str, label: str, message: str, **extra: object) -> None:
    if not callable(callback):
        return
    callback(
        event,
        {
            "stage_key": stage_key,
            "stage_name": stage_name,
            "label": label,
            "message": message,
            **extra,
        },
    )


def client_for_revision_request(
    base_client: LLMClient,
    instruction: str,
    selection: Optional[Dict[str, str]] = None,
    *,
    attempt: int = 1,
) -> LLMClient:
    client = client_for_revision(base_client, attempt=attempt)
    if (
        attempt == 1
        and client.enabled
        and client.writer_mode != "mock"
        and not is_qa_revision_scope(instruction)
        and not is_broad_revision_scope(instruction)
        and not os.getenv("OPENAI_REASONING_EFFORT_REVISION")
    ):
        return client.with_overrides(reasoning_effort="low")
    return client


def revision_schema(instruction: str = "", selection: Optional[Dict[str, str]] = None) -> dict:
    budget = revision_output_budget(instruction, selection)
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": budget["summary_chars"]},
            "history_change": {"type": "string", "maxLength": budget["history_chars"]},
            "target_sections": {
                "type": "array",
                "items": {"type": "string", "maxLength": 32},
                "maxItems": budget["target_sections"],
            },
            "replacements": {
                "type": "array",
                "maxItems": budget["replacements"],
                "items": {
                    "type": "object",
                    "properties": {
                        "find": {"type": "string", "maxLength": budget["find_chars"]},
                        "replace": {"type": "string", "maxLength": budget["replace_chars"]},
                    },
                    "required": ["find", "replace"],
                    "additionalProperties": False,
                },
            },
            "append_title": {"type": "string", "maxLength": budget["append_title_chars"]},
            "append_items": {
                "type": "array",
                "items": {"type": "string", "maxLength": budget["append_item_chars"]},
                "maxItems": budget["append_items"],
            },
            "target_replacement_html": {"type": "string", "maxLength": budget["target_html_chars"]},
        },
        "required": [
            "summary",
            "history_change",
            "target_sections",
            "replacements",
            "append_title",
            "append_items",
            "target_replacement_html",
        ],
        "additionalProperties": False,
    }


def revision_output_budget(instruction: str, selection: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    replacement_limit, append_limit = revision_plan_limits(instruction, selection)
    selected = bool(selection)
    qa_scope = is_qa_revision_scope(instruction)
    if selected:
        return {
            "replacements": replacement_limit,
            "append_items": append_limit,
            "target_sections": 3,
            "summary_chars": 180,
            "history_chars": 120,
            "find_chars": 600,
            "replace_chars": 900,
            "append_title_chars": 80,
            "append_item_chars": 260,
            "target_html_chars": 4200,
        }
    if qa_scope:
        return {
            "replacements": replacement_limit,
            "append_items": append_limit,
            "target_sections": 8,
            "summary_chars": 260,
            "history_chars": 160,
            "find_chars": 700,
            "replace_chars": 1000,
            "append_title_chars": 100,
            "append_item_chars": 360,
            "target_html_chars": 0,
        }
    if is_broad_revision_scope(instruction):
        return {
            "replacements": replacement_limit,
            "append_items": append_limit,
            "target_sections": 8,
            "summary_chars": 260,
            "history_chars": 160,
            "find_chars": 700,
            "replace_chars": 1000,
            "append_title_chars": 100,
            "append_item_chars": 360,
            "target_html_chars": 0,
        }
    return {
        "replacements": replacement_limit,
        "append_items": append_limit,
        "target_sections": 5,
        "summary_chars": 220,
        "history_chars": 140,
        "find_chars": 520,
        "replace_chars": 760,
        "append_title_chars": 90,
        "append_item_chars": 280,
        "target_html_chars": 0,
    }


def fallback_revision_intent(instruction: str, exc: Exception) -> Dict[str, Any]:
    reason = str(exc).splitlines()[0][:160]
    return {
        "summary": "LLM API 일시 오류로 자동 보완 계획을 최소 범위로 생성했습니다.",
        "history_change": "LLM API 일시 오류 후 사용자 수정 요청을 보완 항목으로 반영",
        "target_sections": select_revision_sections(instruction),
        "replacements": [],
        "append_title": "수정 요청 반영 필요 사항",
        "append_items": [
            f"사용자 수정 요청: {instruction}",
            f"LLM API 일시 오류로 상세 보완 계획 생성이 지연되었습니다. 오류: {reason}",
            "후속 보완 시 해당 요청을 기준으로 대상 장의 정책 기준, 예외 조건, 프로세스·기능·정책 연결성을 재검토한다.",
        ],
        "target_replacement_html": "",
    }


def constrain_revision_plan_scope(
    plan: Mapping[str, Any],
    instruction: str,
    selection: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    constrained = dict(plan)
    replacement_limit, append_limit = revision_plan_limits(instruction, selection)
    replacements = plan.get("replacements") if isinstance(plan.get("replacements"), list) else []
    append_items = plan.get("append_items") if isinstance(plan.get("append_items"), list) else []
    replacement_count = len(replacements)
    append_count = len(append_items)
    constrained["replacements"] = replacements[:replacement_limit]
    constrained["append_items"] = append_items[:append_limit]
    if replacement_count > replacement_limit or append_count > append_limit:
        summary = str(constrained.get("summary", "") or "").strip()
        trimmed = (
            f"수정 범위 과다 제안으로 핵심 변경만 반영합니다"
            f"({replacement_count}->{len(constrained['replacements'])} replacements, "
            f"{append_count}->{len(constrained['append_items'])} append_items)."
        )
        constrained["summary"] = f"{summary} {trimmed}".strip()
    return constrained


def revision_plan_limits(instruction: str, selection: Optional[Dict[str, str]] = None) -> tuple[int, int]:
    if selection:
        return 3, 2
    if is_qa_revision_scope(instruction):
        return 20, 20
    if is_broad_revision_scope(instruction):
        return 10, 10
    return 6, 6


def is_qa_revision_scope(instruction: str) -> bool:
    normalized = normalize_history_text(instruction).casefold()
    return any(keyword in normalized for keyword in ("health check", "fail 항목", "개발/qa", "검수 결과", "선택된 보완 항목"))


def is_broad_revision_scope(instruction: str) -> bool:
    normalized = normalize_history_text(instruction).casefold()
    broad_keywords = (
        "전체",
        "전반",
        "구조",
        "정합성",
        "누락",
        "검증",
        "점검",
        "교차검증",
        "연결성",
        "커버리지",
        "trace",
        "트레이스",
        "요구사항",
        "현황 분석",
        "분석 내용",
        "잘 반영",
        "반영 여부",
        "최종본",
        "모든 ",
        "전부",
    )
    if any(keyword in normalized for keyword in broad_keywords):
        return True
    broad_phrases = (
        "검토하고 보완",
        "점검하고 보완",
        "검증하고 보완",
        "정리하고 보완",
        "전체 보완",
        "전반 보완",
        "구조 보완",
        "정합성 보완",
        "누락 보완",
    )
    return any(phrase in normalized for phrase in broad_phrases)


def revision_target_sections(intent: Dict[str, Any]) -> List[str]:
    sections = intent.get("target_sections", [])
    if isinstance(sections, list):
        return [str(item) for item in sections if str(item).strip()]
    if isinstance(sections, str) and sections.strip():
        return [sections.strip()]
    return []


def revision_instructions(
    topic: str,
    template_type: str,
    agent_guidance: str = "",
    instruction: str = "",
    selection: Optional[Dict[str, str]] = None,
) -> str:
    budget = revision_output_budget(instruction, selection)
    scope_label = (
        "선택 영역"
        if selection
        else (
            "개발/QA 선택 항목"
            if is_qa_revision_scope(instruction)
            else ("전반/정합성 보완" if is_broad_revision_scope(instruction) else "일반 보완")
        )
    )
    lines = [
        "너는 통합채널 정책서 수정 Agent다.",
        "사용자의 수정 요청 의도를 먼저 파악하고, 대상 장에 맞는 챕터 전문 Agent 지침으로 보완 계획을 작성한다.",
        "기존 템플릿 CSS와 HTML 구조는 유지해야 한다.",
        "직접 바꿀 수 있는 기존 문장은 replacements에 원문 find와 개선문 replace로 작성한다.",
        "사용자가 문서 일부를 선택한 경우 선택 블록 HTML을 우선 수정 대상으로 삼고, 전체 블록을 안전하게 교체할 수 있으면 target_replacement_html에 동일한 태그 구조의 교체 HTML을 작성한다.",
        "선택 영역 수정이라도 액터, 유즈케이스, 프로세스, 기능, 정책처럼 연결성이 있는 내용은 관련 장의 최소 보완 replacements를 함께 작성한다.",
        "원문을 정확히 찾기 어려우면 append_items에 추가 보완 내용을 작성한다.",
        "액터 제외, 유즈케이스 삭제, 정책명 변경처럼 구조 연결에 영향을 주는 요청은 대상 장만이 아니라 관련 표, 다이어그램, 프로세스, 기능, 정책 표현의 잔여 참조까지 함께 정리한다.",
        "특정 액터를 제외하라는 요청이면 액터 목록, 해당 액터가 수행하는 유즈케이스, 유즈케이스 다이어그램 관계를 제거하고 인증·권한 같은 업무 기준은 남은 시스템/정책 기준으로 재표현한다.",
        "정책서의 유즈케이스, 상태, 프로세스, 기능, 정책 연결성을 깨지 않도록 수정한다.",
        "문서 히스토리에 들어갈 변경 요약을 history_change에 간결하게 작성한다.",
        "출력 공간이 남아 있어도 수정 요청과 직접 관련 없는 배경 설명, 일반론, 동일 의미 반복은 추가하지 않는다.",
        "수정 내용은 사용자의 의도, 기존 근거, 연결성 보완에 필요한 문장만 남긴다.",
        f"수정 범위: {scope_label}.",
        f"출력 예산: replacements 최대 {budget['replacements']}개, append_items 최대 {budget['append_items']}개, target_sections 최대 {budget['target_sections']}개.",
        f"문장 예산: summary {budget['summary_chars']}자 이내, history_change {budget['history_chars']}자 이내, find {budget['find_chars']}자 이내, replace {budget['replace_chars']}자 이내, append_items 각 {budget['append_item_chars']}자 이내.",
        "예산을 넘는 보완 후보가 있으면 우선순위가 높은 항목만 JSON에 남기고 나머지는 작성하지 않는다.",
        "일반 보완 요청에서는 target_replacement_html을 빈 문자열로 둔다. target_replacement_html은 사용자가 본문 일부를 선택한 경우에만 작성한다.",
        "기존 장 전체를 다시 쓰거나 표 전체를 통째로 반환하지 않는다. 필요한 행, 문장, 항목만 교체·추가한다.",
        f"정책서 주제: {topic}",
        f"템플릿 유형: {template_type}",
        "반드시 요청된 JSON 스키마에 맞는 JSON만 작성한다.",
    ]
    if agent_guidance:
        lines.append("챕터별 전문 Agent 지침:\n" + agent_guidance)
    return "\n".join(lines)


def revision_agent_guidelines(
    guideline: Dict[str, Any],
    template_type: str = "simple",
    sections: Optional[Iterable[str]] = None,
) -> str:
    selected_sections = {str(section or "").strip() for section in (sections or []) if str(section or "").strip()}
    lines = ["공통 지침:"]
    lines.extend(f"- {rule}" for rule in guideline.get("common_rules", []))
    lines.append("챕터별 지침:")
    for stage in chapter_stages(template_type):
        if selected_sections and stage.agent.chapter_key not in selected_sections:
            continue
        lines.append(f"- {stage.agent.chapter_key}: {stage.agent.display_name} - {stage.agent.instruction(guideline)}")
    return "\n".join(lines)


def revision_prompt(old_html: str, instruction: str, selection: Optional[Dict[str, str]] = None) -> str:
    context = revision_document_context(old_html, instruction, selection)
    return "\n\n".join(
        [
            "사용자 수정 요청:\n" + instruction,
            revision_selection_prompt_block(selection),
            "정책서 구조 및 선택 장 요약:\n" + json.dumps(context["summary"], ensure_ascii=False, indent=2),
            "관련 장 텍스트 발췌:\n" + context["selected_text"],
            "관련 장 HTML 발췌:\n" + context["selected_html"],
            "요청:\n수정 의도를 분석한 뒤 대상 장의 전문 Agent 관점으로 기존 문서에 적용할 replacements, append_items, target_replacement_html을 작성해줘.",
        ]
    )


def revision_refinement_prompt(
    current_html: str,
    instruction: str,
    feedback: List[Dict[str, str]],
    selection: Optional[Dict[str, str]] = None,
) -> str:
    context = revision_document_context(current_html, instruction, selection)
    return "\n\n".join(
        [
            "사용자 수정 요청:\n" + instruction,
            revision_selection_prompt_block(selection),
            "Inspector 보완 요청:\n" + json.dumps(feedback, ensure_ascii=False, indent=2),
            "수정본 구조 및 선택 장 요약:\n" + json.dumps(context["summary"], ensure_ascii=False, indent=2),
            "관련 장 텍스트 발췌:\n" + context["selected_text"],
            "관련 장 HTML 발췌:\n" + context["selected_html"],
            "요청:\nInspector 보완 요청을 우선 반영해 replacements, append_items, target_replacement_html을 다시 작성해줘.",
        ]
    )


def revision_document_context(
    document: str,
    instruction: str,
    selection: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    selection_present = bool(selection)
    sections = revision_context_sections(instruction, selection)
    if selection_present:
        html_fragments = [
            fragment
            for fragment in (
                selection.get("block_html", "") if selection else "",
                selection.get("html", "") if selection else "",
            )
            if fragment
        ]
    else:
        html_fragments = [fragment for fragment in (revision_section_html(document, key) for key in sections) if fragment]
    if not html_fragments:
        html_fragments = [document]
    selected_html = "\n\n".join(html_fragments)
    selected_text = visible_text(selected_html)
    text_limit, html_limit = revision_context_char_limits(instruction, selection)
    return {
        "summary": {
            "selected_sections": sections,
            "target_selection": selection_summary(selection),
            "outline": revision_outline(document),
            "counts": {
                "actors": document.count("ACT-"),
                "usecases": document.count("US-"),
                "states": document.count("ST-"),
                "processes": document.count("PR-"),
                "functions": document.count("FN-"),
                "policy_groups": document.count("PG-"),
                "policy_items": document.count("PI-"),
            },
        },
        "selected_text": limit_text(selected_text, text_limit),
        "selected_html": limit_text(selected_html, html_limit),
    }


def revision_context_char_limits(instruction: str, selection: Optional[Dict[str, str]] = None) -> tuple[int, int]:
    if selection:
        return 2500, 4500
    if is_qa_revision_scope(instruction):
        return 6500, 9000
    if is_broad_revision_scope(instruction):
        return 6500, 10000
    return 3500, 8000


def revision_context_sections(instruction: str, selection: Optional[Dict[str, str]] = None) -> List[str]:
    selection_present = bool(selection)
    instruction_sections = select_revision_sections(instruction, include_default=not selection_present)
    selection_sections = select_revision_sections_from_selection(selection)
    return merge_revision_sections(instruction_sections, selection_sections)


def revision_selection_from_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    raw = payload.get("selection")
    if not isinstance(raw, dict):
        return {}
    return {
        "text": limit_text(normalize_history_text(str(raw.get("text", ""))), 1000),
        "html": limit_text(str(raw.get("html", "")).strip(), 3000),
        "block_text": limit_text(normalize_history_text(str(raw.get("blockText", ""))), 1400),
        "block_html": limit_text(str(raw.get("blockHtml", "")).strip(), 4000),
        "section_title": limit_text(normalize_history_text(str(raw.get("sectionTitle", ""))), 160),
        "heading_path": limit_text(normalize_history_text(" > ".join(str(item) for item in raw.get("headingPath", []) if str(item).strip())), 320)
        if isinstance(raw.get("headingPath"), list)
        else "",
    }


def revision_selection_prompt_block(selection: Optional[Dict[str, str]]) -> str:
    if not selection:
        return "선택 영역 정보:\n없음"
    return "\n".join(
        [
            "선택 영역 정보:",
            f"- 선택 위치: {selection.get('heading_path') or selection.get('section_title') or '확인 필요'}",
            "- 선택 텍스트:\n" + (selection.get("text") or ""),
            "- 선택 블록 텍스트:\n" + (selection.get("block_text") or ""),
            "- 선택 블록 HTML, target_replacement_html 작성 시 우선 교체 대상:\n" + (selection.get("block_html") or selection.get("html") or ""),
            "선택 영역을 우선 수정하되, 연결성 유지를 위해 필요한 관련 장 보완은 replacements로 최소 범위만 작성한다.",
        ]
    )


def selection_summary(selection: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not selection:
        return {}
    return {
        "section": selection.get("heading_path") or selection.get("section_title") or "",
        "text": limit_text(selection.get("text", ""), 300),
        "block_text": limit_text(selection.get("block_text", ""), 420),
    }


def select_revision_sections_from_selection(selection: Optional[Dict[str, str]]) -> List[str]:
    if not selection:
        return []
    scoped = revision_section_keys_from_heading(
        " ".join([selection.get("heading_path", ""), selection.get("section_title", "")])
    )
    if scoped:
        return scoped
    text = " ".join(
        [
            selection.get("section_title", ""),
            selection.get("heading_path", ""),
            selection.get("text", ""),
            selection.get("block_text", ""),
        ]
    )
    return select_revision_sections(text, include_default=False)


def revision_section_keys_from_heading(value: str) -> List[str]:
    text = normalize_history_text(value).casefold()
    if not text:
        return []
    ordered_rules = [
        ("final_check", ("최종 점검", "점검 기준")),
        ("policies", ("6. 정책", "정책 상세", "정책 목록")),
        ("functions", ("5. 기능", "기능 목록", "기능 정의")),
        ("process", ("4. 프로세스", "프로세스 목록", "업무 흐름")),
        ("state", ("상태 전이", "상태 전이표")),
        ("usecases", ("3. 유즈케이스", "유즈케이스 정의", "액터")),
        ("terms", ("2. 주요 용어", "주요 용어")),
        ("overview", ("1. 개요", "설계 원칙", "범위")),
    ]
    return [key for key, keywords in ordered_rules if any(keyword in text for keyword in keywords)]


def merge_revision_sections(primary: List[str], secondary: List[str]) -> List[str]:
    merged: List[str] = []
    for section in [*secondary, *primary]:
        if section and section not in merged:
            merged.append(section)
    return merged


def select_revision_sections(instruction: str, *, include_default: bool = True) -> List[str]:
    text = instruction.casefold()
    rules = [
        ("overview", ("개요", "범위", "원칙")),
        ("terms", ("용어", "주요 용어")),
        ("usecases", ("액터", "유즈케이스", "usecase", "use case", "주체")),
        ("state", ("상태", "전이")),
        ("process", ("프로세스", "흐름", "절차")),
        ("functions", ("기능", "처리 단위")),
        ("policies", ("정책", "기준", "예외", "제한", "고지", "이력", "개인정보", "bss")),
        ("final_check", ("점검", "체크", "gate", "검수")),
    ]
    selected = [key for key, keywords in rules if any(keyword in text for keyword in keywords)]
    if selected:
        return selected
    if not include_default:
        return []
    return ["overview", "usecases", "process", "functions", "policies"]


def revision_outline(document: str) -> List[Dict[str, str]]:
    outline = []
    for match in re.finditer(r"<h([234])\b[^>]*>(.*?)</h\1>", document, flags=re.DOTALL | re.IGNORECASE):
        outline.append({"level": match.group(1), "text": limit_text(visible_text(match.group(2)), 100)})
    return outline[:80]


def revision_section_html(document: str, section: str) -> str:
    ranges = {
        "overview": ("<h2>1. 개요</h2>", "<h2>2. 주요 용어</h2>"),
        "terms": ("<h2>2. 주요 용어</h2>", "<h2>3. 유즈케이스 정의</h2>"),
        "usecases": ("<h2>3. 유즈케이스 정의</h2>", "<h2>4. 프로세스 정의</h2>"),
        "state": ("<h3>라. 상태 전이표</h3>", "<h2>4. 프로세스 정의</h2>"),
        "process": ("<h2>4. 프로세스 정의</h2>", "<h2>5. 기능 정의</h2>"),
        "functions": ("<h2>5. 기능 정의</h2>", "<h2>6. 정책 정의</h2>"),
        "policies": ("<h2>6. 정책 정의</h2>", "<h2>최종 점검 기준</h2>"),
        "final_check": ("<h2>최종 점검 기준</h2>", "</div>"),
    }
    start, end = ranges.get(section, ("", ""))
    if not start:
        return ""
    return extract_html_between(document, start, end)


def extract_html_between(document: str, start: str, end: str) -> str:
    start_index = document.find(start)
    if start_index < 0:
        return ""
    end_index = document.find(end, start_index + len(start)) if end else -1
    if end_index < 0:
        return document[start_index:]
    return document[start_index:end_index]


def revision_feedback(report: Any) -> List[Dict[str, str]]:
    feedback = []
    for finding in getattr(report, "findings", [])[:12]:
        feedback.append(
            {
                "severity": str(getattr(finding, "severity", "")),
                "category": str(getattr(finding, "category", "")),
                "title": str(getattr(finding, "title", "")),
                "detail": str(getattr(finding, "detail", "")),
                "recommendation": str(getattr(finding, "recommendation", "")),
            }
        )
    if not feedback:
        feedback.append(
            {
                "severity": "warning",
                "category": "점수",
                "title": "Inspector 점수 미달",
                "detail": f"Inspector 점수 {getattr(report, 'score', 'N/A')}점이 기준 {DEFAULT_INSPECTOR_MIN_SCORE}점보다 낮습니다.",
                "recommendation": "샘플 수준에 맞춰 판단 기준, 예외, 이력 저장 기준을 더 구체화하세요.",
            }
        )
    return feedback


def apply_revision_plan(
    old_html: str,
    plan: Dict[str, Any],
    instruction: str,
    selection: Optional[Dict[str, str]] = None,
) -> tuple[str, int]:
    revised = old_html
    applied = 0
    target_replacement = str(plan.get("target_replacement_html", "")).strip()
    if target_replacement and selection:
        for target_block in (selection.get("block_html", ""), selection.get("html", "")):
            target_block = str(target_block or "").strip()
            if target_block and target_block in revised:
                revised = revised.replace(target_block, target_replacement, 1)
                applied += 1
                break

    replacements = plan.get("replacements", [])
    if isinstance(replacements, list):
        for item in replacements:
            if not isinstance(item, dict):
                continue
            find = str(item.get("find", "")).strip()
            replace = str(item.get("replace", "")).strip()
            if not find or not replace:
                continue
            candidates = [(find, replace)]
            if "<" not in find and ">" not in find:
                candidates.append((html.escape(find), html.escape(replace)))
            for candidate_find, candidate_replace in candidates:
                if candidate_find not in revised:
                    continue
                revised = revised.replace(candidate_find, candidate_replace, 1)
                applied += 1
                break
    if applied == 0 and selection:
        revised, selected_applied = apply_selected_text_instruction(revised, instruction, selection)
        applied += selected_applied
    return revised, applied


def apply_selected_text_instruction(
    document: str,
    instruction: str,
    selection: Mapping[str, str],
) -> tuple[str, int]:
    selected_text = normalize_history_text(str(selection.get("text", "") or ""))
    replacement = infer_selected_text_replacement(instruction, selected_text)
    if replacement is None or not selected_text or replacement == selected_text:
        return document, 0

    for target_block in (selection.get("block_html", ""), selection.get("html", "")):
        target_block = str(target_block or "").strip()
        if not target_block or target_block not in document:
            continue
        replacement_block = replace_text_in_html_fragment(target_block, selected_text, replacement)
        if replacement_block != target_block:
            return document.replace(target_block, replacement_block, 1), 1

    escaped_selected = html.escape(selected_text)
    escaped_replacement = html.escape(replacement)
    for find, replace in ((escaped_selected, escaped_replacement), (selected_text, escaped_replacement)):
        if find and find in document:
            return document.replace(find, replace, 1), 1
    return document, 0


def replace_text_in_html_fragment(fragment: str, selected_text: str, replacement: str) -> str:
    escaped_replacement = html.escape(replacement)
    candidates = [
        html.escape(selected_text),
        html.escape(selected_text, quote=False),
        selected_text,
    ]
    for candidate in candidates:
        if candidate and candidate in fragment:
            return fragment.replace(candidate, escaped_replacement, 1)
    return fragment


def infer_selected_text_replacement(instruction: str, selected_text: str) -> Optional[str]:
    request = normalize_history_text(str(instruction or ""))
    selected = normalize_history_text(str(selected_text or ""))
    if not request or not selected:
        return None

    if "띄어쓰기" in request and any(keyword in request for keyword in ("없", "제거", "삭제", "붙여")):
        return re.sub(r"\s+", "", selected)

    deletion_keywords = ("삭제", "제거", "지워", "없애", "빼줘", "빼 주세요", "빼주세요")
    replacement_markers = ("으로", "로 변경", "로 수정", "로 바꿔", "로 교체", "로 고쳐")
    if any(keyword in request for keyword in deletion_keywords) and not any(marker in request for marker in replacement_markers):
        return ""

    quoted_pattern = r"[\"'“”‘’`]([^\"'“”‘’`\n]{1,160})[\"'“”‘’`]\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)"
    match = re.search(quoted_pattern, request)
    if match:
        return clean_replacement_candidate(match.group(1))

    particle_pattern = r"(?:을|를)\s*([^\n]{1,160}?)\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)"
    match = re.search(particle_pattern, request)
    if match:
        return clean_replacement_candidate(match.group(1))

    direct_pattern = r"([^\n]{1,160}?)\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)"
    match = re.search(direct_pattern, request)
    if match:
        return clean_replacement_candidate(match.group(1))

    return None


def clean_replacement_candidate(value: str) -> str:
    candidate = normalize_history_text(value)
    candidate = candidate.strip(" \t\r\n.,:;\"'“”‘’`()[]{}")
    for delimiter in ("을 ", "를 "):
        if delimiter in candidate:
            candidate = candidate.rsplit(delimiter, 1)[-1].strip()
    candidate = re.sub(r"^(?:이걸|이것을|이 문구를|이 문구|선택 영역을|선택 영역|선택한 영역을|선택한 문구를|문구를|텍스트를)\s*", "", candidate)
    return candidate.strip(" \t\r\n.,:;\"'“”‘’`()[]{}")


def apply_structural_revision(document: str, instruction: str) -> tuple[str, List[str]]:
    revised = document
    changes: List[str] = []
    actor_targets = actor_exclusion_targets(revised, instruction)
    if actor_targets:
        revised, removed_actors = remove_table_rows_after_heading(
            revised,
            "<h3>가. 액터</h3>",
            lambda cells: len(cells) >= 2 and cells[1] in actor_targets,
        )
        if removed_actors:
            changes.append("지정 액터 행 삭제")

        revised, removed_usecases = remove_table_rows_after_heading(
            revised,
            "<h3>나. 유즈케이스</h3>",
            lambda cells: len(cells) >= 2 and cells[1] in actor_targets,
        )
        if removed_usecases:
            changes.append("지정 액터 유즈케이스 삭제")

        rebuilt_diagram = build_usecase_diagram_html(revised)
        if rebuilt_diagram:
            revised, diagram_changed = replace_usecase_diagram(revised, rebuilt_diagram)
            if diagram_changed:
                changes.append("유즈케이스 다이어그램 재생성")

        revised, reference_count = replace_residual_actor_references(revised, actor_targets)
        if reference_count:
            changes.append("잔여 액터 참조 보정")
    return revised, changes


def structural_revision_history(changes: List[str]) -> str:
    if not changes:
        return ""
    return "사용자 수정 요청에 따라 지정 액터를 제외하고 관련 유즈케이스, 다이어그램, 본문 참조를 정합성 있게 보완."


def actor_exclusion_targets(document: str, instruction: str) -> List[str]:
    text = instruction.strip()
    action_keywords = ("제외", "삭제", "제거", "빼", "빼줘", "빼주세요")
    if "액터" not in text or not any(keyword in text for keyword in action_keywords):
        return []
    actor_names = extract_actor_names(document)
    targets = [actor for actor in actor_names if actor and actor in text]
    if targets:
        return targets

    patterns = [
        r"액터(?:\s*목록)?(?:에서|에\s*있는)?\s*(?P<targets>[^.,\n]+?)\s*(?:을|를)?\s*(?:제외|삭제|제거|빼)",
        r"(?P<targets>[^.,\n]+?)\s*(?:을|를)?\s*액터(?:\s*목록)?(?:에서)?\s*(?:제외|삭제|제거|빼)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = split_actor_targets(match.group("targets"))
        return [target for target in parsed if target in actor_names]
    return []


def split_actor_targets(raw_targets: str) -> List[str]:
    cleaned = re.sub(r"(해줘|해주세요|해|요청|대상|에서)$", "", raw_targets.strip())
    parts = re.split(r"\s*(?:,|/| 및 | 그리고 |와 |과 )\s*", cleaned)
    targets = []
    for part in parts:
        target = part.strip(" '\"`[]()")
        target = re.sub(r"(을|를|은|는|이|가)$", "", target).strip()
        if target:
            targets.append(target)
    return targets


def extract_actor_names(document: str) -> List[str]:
    rows = table_rows_after_heading(document, "<h3>가. 액터</h3>")
    names: List[str] = []
    for row in rows:
        cells = row_cell_texts(row)
        if len(cells) >= 2 and cells[1]:
            names.append(cells[1])
    return names


def remove_table_rows_after_heading(document: str, heading: str, remove_row) -> tuple[str, List[List[str]]]:
    bounds = tbody_bounds_after_heading(document, heading)
    if not bounds:
        return document, []
    body_start, body_end = bounds
    tbody = document[body_start:body_end]
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", tbody, flags=re.DOTALL | re.IGNORECASE)
    if not rows:
        return document, []
    removed: List[List[str]] = []
    kept_rows: List[str] = []
    for row in rows:
        cells = row_cell_texts(row)
        if remove_row(cells):
            removed.append(cells)
            continue
        kept_rows.append(row)
    if not removed:
        return document, []
    new_tbody = "".join(kept_rows)
    return document[:body_start] + new_tbody + document[body_end:], removed


def table_rows_after_heading(document: str, heading: str) -> List[str]:
    bounds = tbody_bounds_after_heading(document, heading)
    if not bounds:
        return []
    body_start, body_end = bounds
    return re.findall(r"<tr\b[^>]*>.*?</tr>", document[body_start:body_end], flags=re.DOTALL | re.IGNORECASE)


def tbody_bounds_after_heading(document: str, heading: str) -> Optional[tuple[int, int]]:
    heading_index = document.find(heading)
    if heading_index < 0:
        return None
    tbody_open = document.find("<tbody>", heading_index)
    tbody_close = document.find("</tbody>", tbody_open)
    if tbody_open < 0 or tbody_close < 0:
        return None
    return tbody_open + len("<tbody>"), tbody_close


def row_cell_texts(row: str) -> List[str]:
    cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
    return [visible_text(cell) for cell in cells]


def build_usecase_diagram_html(document: str) -> str:
    actor_names = extract_actor_names(document)
    usecase_rows = []
    for row in table_rows_after_heading(document, "<h3>나. 유즈케이스</h3>"):
        cells = row_cell_texts(row)
        if len(cells) >= 3:
            usecase_rows.append(
                {
                    "id": cells[0],
                    "actor": cells[1],
                    "name": cells[2],
                    "process_target": cells[4] if len(cells) >= 5 else "",
                }
            )
    if not actor_names or not usecase_rows:
        return ""

    return build_usecase_static_diagram_from_data(actor_names, usecase_rows)


def mermaid_label(value: str) -> str:
    return html.unescape(value).replace('"', '\\"').replace("\n", " ").strip()


def replace_usecase_diagram(document: str, diagram_html: str) -> tuple[str, bool]:
    heading = "<h3>다. 유즈케이스 다이어그램</h3>"
    heading_index = document.find(heading)
    if heading_index < 0:
        return document, False
    wrap_start = document.find('<div class="diagram-wrap"', heading_index)
    if wrap_start < 0:
        return document, False
    next_heading = document.find("<h3>라. 상태 전이표</h3>", wrap_start)
    if next_heading < 0:
        next_heading = document.find("<h3", wrap_start + 1)
    if next_heading < 0:
        return document, False
    return document[:wrap_start] + diagram_html + "\n" + document[next_heading:], True


def replace_residual_actor_references(document: str, actor_targets: List[str]) -> tuple[str, int]:
    revised = document
    count = 0
    for actor in actor_targets:
        replacement = actor_reference_replacement(actor)
        particle_pairs = {
            "이": "가",
            "은": "는",
            "을": "를",
            "과": "와",
        }
        for source_particle, target_particle in particle_pairs.items():
            source = actor + source_particle
            target = replacement + target_particle
            occurrences = revised.count(source)
            if occurrences:
                revised = revised.replace(source, target)
                count += occurrences
        occurrences = revised.count(actor)
        if occurrences:
            revised = revised.replace(actor, replacement)
            count += occurrences
    return revised, count


def actor_reference_replacement(actor: str) -> str:
    if actor.upper() == "BSS":
        return "업무 처리 시스템"
    if actor.endswith("기관"):
        return actor.removesuffix("기관").strip() + " 처리"
    if actor.endswith("시스템"):
        return actor.removesuffix("시스템").strip() + " 처리"
    if actor.endswith("운영자"):
        return "운영 역할"
    return "해당 처리"


def append_revision_section(document: str, plan: Dict[str, Any], instruction: str) -> str:
    title = html.escape(str(plan.get("append_title") or "수정 요청 반영 사항"))
    items = plan.get("append_items", [])
    if not isinstance(items, list) or not items:
        items = [str(plan.get("summary") or instruction)]
    body = "\n".join(f'<p class="plain-text">{html.escape(str(item))}</p>' for item in items if str(item).strip())
    section = f"""
<h2>수정 요청 반영</h2>
<h3>{title}</h3>
{body}
"""
    if "<h2>최종 점검 기준</h2>" in document:
        return document.replace("<h2>최종 점검 기준</h2>", section + "\n<h2>최종 점검 기준</h2>", 1)
    return document.replace("</div>\n</body>", section + "\n</div>\n</body>", 1)


def write_new_policy_version(old_path: Path, document: str, author: str, change_summary: str) -> Path:
    new_path = next_policy_version_path(old_path)
    next_version = parse_policy_filename(new_path.name)["version"]
    updated = update_document_version_and_history(document, old_path.name, next_version, author, change_summary)
    updated = restore_policy_runtime_scripts(document, sanitize_policy_html(updated))
    new_path.write_text(updated, encoding="utf-8")
    sync_policy_version_spec_from_base(old_path, new_path, author=author, reason="manual_edit_new_version")
    return new_path


def write_existing_policy_version(path: Path, document: str, author: str, change_summary: str) -> Path:
    current_version = parse_policy_filename(path.name).get("version", "")
    updated = append_document_history_entry(document, current_version, author, change_summary)
    updated = restore_policy_runtime_scripts(document, sanitize_policy_html(updated))
    backup_policy_html_before_overwrite(path, reason="manual_edit_overwrite")
    path.write_text(updated, encoding="utf-8")
    sync_policy_version_spec_from_base(path, path, author=author, reason="manual_edit_overwrite")
    return path


def document_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def update_document_version_and_history(document: str, old_name: str, new_version: str, author: str, change_summary: str) -> str:
    parsed = parse_policy_filename(old_name)
    old_version = parsed.get("version", "")
    updated = document
    change_summary = compact_history_text(change_summary)
    if old_version and old_version != "-":
        version_pattern = re.escape(old_version)
        replacements = [
            rf"(<title>.*?)\b{version_pattern}\b(.*?</title>)",
            rf"(<td[^>]*class=[\"'][^\"']*\bmono\b[^\"']*[\"'][^>]*>[^<]*?)\b{version_pattern}\b([^<]*</td>)",
        ]
        for pattern in replacements:
            updated = re.sub(pattern, lambda m: m.group(1) + new_version + m.group(2), updated, count=1, flags=re.DOTALL)
    return append_document_history_entry(updated, new_version, author, change_summary)


def append_document_history_entry(document: str, version: str, author: str, change_summary: str) -> str:
    version_label = version if version and version != "-" else "수동 수정"
    row = (
        f"<tr><td>{html.escape(version_label)}</td>"
        f"<td>{html.escape(compact_history_text(change_summary))}</td>"
        f"<td>{datetime.now().date().isoformat()}</td>"
        f"<td>{html.escape(author)}</td></tr>"
    )
    pattern = r"(<h2>0\. 문서 히스토리</h2>.*?<tbody>)(.*?)(</tbody>)"
    if re.search(pattern, document, flags=re.DOTALL):
        return re.sub(pattern, lambda m: m.group(1) + m.group(2) + row + m.group(3), document, count=1, flags=re.DOTALL)
    return document


def summarize_html_change(before_html: str, after_html: str, prefix: str) -> str:
    changes = semantic_html_changes(before_html, after_html)
    if not changes:
        return f"{prefix}. 본문 표현 및 서식을 보완."

    sections: List[str] = []
    snippets: List[str] = []
    for change in changes:
        section = str(change.get("section") or "본문")
        if section not in sections:
            sections.append(section)
        snippet = history_change_fragment(str(change.get("after") or change.get("before") or ""))
        if snippet and snippet not in snippets:
            snippets.append(snippet)

    section_label = "·".join(short_history_section_name(section) for section in sections[:4])
    if len(sections) > 4:
        section_label += f" 외 {len(sections) - 4}개 영역"

    if len(changes) <= 3 and snippets:
        summary = f"{prefix}. 변경 위치: {section_label}. 주요 변경: {' / '.join(snippets[:3])}."
    else:
        summary = f"{prefix}. 변경 위치: {section_label}. 본문 {len(changes)}개 항목을 보완."
    return compact_history_text(summary)


MERMAID_PRE_PATTERN = re.compile(
    r"<pre\b(?=[^>]*\bclass=[\"'][^\"']*\bmermaid\b[^\"']*[\"'])[^>]*>.*?</pre>",
    re.DOTALL | re.IGNORECASE,
)
DANGEROUS_CONTAINER_TAG_PATTERN = re.compile(
    r"<(?P<tag>script|iframe|object|embed|form)\b[^>]*>.*?</(?P=tag)>",
    re.DOTALL | re.IGNORECASE,
)
DANGEROUS_VOID_TAG_PATTERN = re.compile(
    r"<(?:base|meta)\b(?=[^>]*(?:http-equiv\s*=\s*[\"']?refresh|content\s*=\s*[\"']?\s*\d+\s*;?\s*url=))[^>]*>",
    re.IGNORECASE,
)
SCRIPT_TAG_PATTERN = re.compile(r"<script\b(?P<attrs>[^>]*)>.*?</script>", re.DOTALL | re.IGNORECASE)
HTML_HEAD_PATTERN = re.compile(r"<head\b[^>]*>(?P<head>.*?)</head>", re.DOTALL | re.IGNORECASE)
HTML_BODY_PATTERN = re.compile(r"<body\b[^>]*>(?P<body>.*?)</body>", re.DOTALL | re.IGNORECASE)
HTML_ATTR_PATTERN = re.compile(
    r"(?P<name>[\w:-]+)\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s\"'>]+))",
    re.IGNORECASE,
)
TRUSTED_POLICY_SCRIPT_SRCS = {
    "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js",
    "https://unpkg.com/bpmn-js/dist/bpmn-viewer.production.min.js",
}
EVENT_HANDLER_ATTR_PATTERN = re.compile(
    r"\s+on[a-zA-Z][\w:-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
JAVASCRIPT_URL_ATTR_PATTERN = re.compile(
    r"(\s(?:href|src|xlink:href|action|formaction)\s*=\s*)([\"'])\s*javascript:[^\"']*\2",
    re.IGNORECASE,
)
UNQUOTED_JAVASCRIPT_URL_ATTR_PATTERN = re.compile(
    r"(\s(?:href|src|xlink:href|action|formaction)\s*=\s*)javascript:[^\s>]+",
    re.IGNORECASE,
)


def normalize_manual_edit_html(old_html: str, edited_html: str) -> str:
    """Remove browser-only mutations that should not become policy document changes."""
    normalized = restore_mermaid_source_blocks(old_html, edited_html)
    normalized = normalize_browser_markup_noise(normalized)
    normalized = sanitize_policy_html(normalized)
    normalized = restore_policy_runtime_scripts(old_html, normalized)
    return normalized


def restore_policy_runtime_scripts(old_html: str, sanitized_html: str) -> str:
    """Re-attach generated diagram runtime/data scripts removed by sanitization.

    Manual edits must not save newly injected executable scripts, but policy files
    generated by this service contain known Mermaid/BPMN runtime scripts and a
    non-executable BPMN XML JSON payload. Those blocks are restored only from the
    already-saved source document, never from the edited payload.
    """
    restored = sanitized_html
    head_scripts = policy_safe_head_scripts(old_html)
    if head_scripts:
        restored = insert_before_closing_tag(restored, "head", "\n".join(head_scripts) + "\n")
    body_data_scripts = policy_safe_body_data_scripts(old_html)
    if body_data_scripts:
        restored = insert_before_closing_tag(restored, "body", "\n".join(body_data_scripts) + "\n")
    return restored


def policy_safe_head_scripts(document: str) -> List[str]:
    match = HTML_HEAD_PATTERN.search(document or "")
    if not match:
        return []
    return unique_preserving_order(
        block.group(0)
        for block in SCRIPT_TAG_PATTERN.finditer(match.group("head"))
        if is_trusted_policy_head_script(block.group(0))
    )


def policy_safe_body_data_scripts(document: str) -> List[str]:
    match = HTML_BODY_PATTERN.search(document or "")
    if not match:
        return []
    return unique_preserving_order(
        block.group(0)
        for block in SCRIPT_TAG_PATTERN.finditer(match.group("body"))
        if is_trusted_policy_data_script(block.group(0))
    )


def script_attrs(block: str) -> Dict[str, str]:
    match = re.match(r"<script\b(?P<attrs>[^>]*)>", block or "", flags=re.IGNORECASE | re.DOTALL)
    raw_attrs = match.group("attrs") if match else ""
    attrs: Dict[str, str] = {}
    for attr_match in HTML_ATTR_PATTERN.finditer(raw_attrs):
        value = attr_match.group("double")
        if value is None:
            value = attr_match.group("single")
        if value is None:
            value = attr_match.group("bare")
        attrs[attr_match.group("name").lower()] = str(value or "")
    return attrs


def script_body(block: str) -> str:
    match = re.match(r"<script\b[^>]*>(?P<body>.*?)</script>", block or "", flags=re.IGNORECASE | re.DOTALL)
    return match.group("body") if match else ""


def is_trusted_policy_head_script(block: str) -> bool:
    attrs = script_attrs(block)
    src = attrs.get("src", "").strip()
    if src in TRUSTED_POLICY_SCRIPT_SRCS:
        return True
    if attrs.get("src"):
        return False
    body = script_body(block)
    return (
        "window.mermaid.initialize" in body
        and "renderBpmnViewers" in body
        and "data-bpmn-viewer" in body
        and "data-bpmn-download" in body
    )


def is_trusted_policy_data_script(block: str) -> bool:
    attrs = script_attrs(block)
    script_type = attrs.get("type", "").strip().lower()
    script_id = attrs.get("id", "").strip().lower()
    body = script_body(block)
    return script_type == "application/json" and script_id.startswith("bpmn-") and '"xml"' in body


def insert_before_closing_tag(document: str, tag: str, block: str) -> str:
    if not block.strip():
        return document
    closing = f"</{tag}>"
    if block.strip() in document:
        return document
    pattern = re.compile(re.escape(closing), re.IGNORECASE)
    if pattern.search(document):
        return pattern.sub(block + closing, document, count=1)
    return document + "\n" + block


def unique_preserving_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def restore_mermaid_source_blocks(old_html: str, edited_html: str) -> str:
    old_blocks = MERMAID_PRE_PATTERN.findall(old_html)
    if not old_blocks:
        return edited_html

    index = 0

    def replace_block(match: re.Match[str]) -> str:
        nonlocal index
        block = match.group(0)
        old_block = old_blocks[index] if index < len(old_blocks) else ""
        index += 1
        if old_block and is_rendered_mermaid_block(block) and not is_rendered_mermaid_block(old_block):
            return old_block
        return block

    return MERMAID_PRE_PATTERN.sub(replace_block, edited_html)


def is_rendered_mermaid_block(block: str) -> bool:
    lowered = block.casefold()
    return "<svg" in lowered or "data-processed" in lowered


def normalize_browser_markup_noise(document: str) -> str:
    return re.sub(r"<br\s*/?>", "<br/>", document, flags=re.IGNORECASE)


def sanitize_policy_html(document: str) -> str:
    """Remove executable HTML before saving user/agent revisions."""
    sanitized = DANGEROUS_CONTAINER_TAG_PATTERN.sub("", document)
    sanitized = DANGEROUS_VOID_TAG_PATTERN.sub("", sanitized)
    sanitized = EVENT_HANDLER_ATTR_PATTERN.sub("", sanitized)
    sanitized = JAVASCRIPT_URL_ATTR_PATTERN.sub(r'\1\2#\2', sanitized)
    sanitized = UNQUOTED_JAVASCRIPT_URL_ATTR_PATTERN.sub(r'\1"#"', sanitized)
    return sanitized


def semantic_html_changes(before_html: str, after_html: str) -> List[Dict[str, str]]:
    before_units = semantic_text_units(before_html)
    after_units = semantic_text_units(after_html)
    before_texts = [unit["text"] for unit in before_units]
    after_texts = [unit["text"] for unit in after_units]
    matcher = difflib.SequenceMatcher(None, before_texts, after_texts)
    changes: List[Dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "insert"}:
            for unit in after_units[j1:j2]:
                changes.append({"section": unit["section"], "after": unit["text"], "before": ""})
        if tag == "delete":
            for unit in before_units[i1:i2]:
                changes.append({"section": unit["section"], "before": unit["text"], "after": ""})
    return changes


def semantic_text_units(document: str) -> List[Dict[str, str]]:
    cleaned = strip_history_section(document)
    cleaned = re.sub(r"<title\b[^>]*>.*?</title>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = MERMAID_PRE_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"<style\b.*?</style>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<script\b.*?</script>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<svg\b.*?</svg>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)

    units: List[Dict[str, str]] = []
    section = "표지"
    block_pattern = re.compile(r"<(?P<tag>h[2-4]|p|li|tr)\b[^>]*>.*?</(?P=tag)>", re.DOTALL | re.IGNORECASE)
    for match in block_pattern.finditer(cleaned):
        tag = match.group("tag").lower()
        text = html_block_text(match.group(0))
        if not text:
            continue
        if tag == "h2":
            section = text
            continue
        if is_history_diff_noise(text):
            continue
        units.append({"section": section, "text": text})
    return units


def strip_history_section(document: str) -> str:
    return re.sub(
        r"<h2>\s*0\.\s*문서 히스토리\s*</h2>.*?</table>",
        " ",
        document,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )


def html_block_text(block: str) -> str:
    text = re.sub(r"<br\s*/?>", " / ", block, flags=re.IGNORECASE)
    text = re.sub(r"</(td|th)>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_history_text(text)


def normalize_history_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_history_diff_noise(text: str) -> bool:
    if not text:
        return True
    normalized = text.casefold()
    if normalized.startswith("버전 v"):
        return True
    if normalized.startswith("작성일 "):
        return True
    return False


def history_change_fragment(text: str) -> str:
    if text.startswith("문서 상태"):
        return "문서 상태 표현 보완"
    if text.startswith("버전 "):
        return ""
    if text.startswith("정책서 ID"):
        return "표지 메타 정보 보완"
    cleaned = re.sub(r"\b[A-Z]{2,3}-[A-Z0-9-]+\b", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" /")
    if len(cleaned) > 80:
        cleaned = cleaned[:80].rstrip() + "..."
    return cleaned


def short_history_section_name(section: str) -> str:
    section = normalize_history_text(section)
    if section == "표지":
        return section
    section = re.sub(r"^\d+\.\s*", "", section)
    return section or "본문"


def compact_history_text(value: str, limit: int = 180) -> str:
    text = normalize_history_text(value)
    text = re.sub(r"\s*/\s*", " / ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def next_policy_version_path(old_path: Path) -> Path:
    parsed = parse_policy_filename(old_path.name)
    topic = parsed["topic"]
    label = parsed["template_label"]
    versions: List[str] = []
    pattern = re.compile(rf"^NC_{re.escape(topic)}_정책서_{re.escape(label)}_v(?P<major>\d+)\.(?P<minor>\d+)\.html$")
    for path in OUTPUT_ROOT.glob(f"NC_{topic}_정책서_{label}_v*.html"):
        match = pattern.match(path.name)
        if match:
            versions.append(f"v{match.group('major')}.{match.group('minor')}")
    next_version = next_policy_version(versions)
    return OUTPUT_ROOT / f"NC_{topic}_정책서_{label}_{next_version}.html"


def policy_version_spec_path(policy_path: Path) -> Path:
    return OUTPUT_ROOT / f"{policy_path.stem}_spec.json"


def topic_policy_spec_path(topic_slug: str) -> Path:
    return OUTPUT_ROOT / f"{topic_slug}_policy_spec.json"


def read_policy_spec_payload(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    spec = payload.get("spec") if isinstance(payload, dict) and isinstance(payload.get("spec"), dict) else payload
    return spec if isinstance(spec, dict) else None


def sync_policy_version_spec_from_base(
    base_path: Path,
    target_path: Path,
    *,
    author: str = "",
    reason: str = "",
) -> Optional[Path]:
    """Keep a JSON spec file beside each HTML version whenever a source spec exists."""
    target_parsed = parse_policy_filename(target_path.name)
    target_topic = str(target_parsed.get("topic") or "").strip()
    target_version = str(target_parsed.get("version") or "").strip()
    if not target_topic or target_topic == "-" or not target_version or target_version == "-":
        return None

    base_parsed = parse_policy_filename(base_path.name)
    base_topic = str(base_parsed.get("topic") or target_topic).strip()
    candidates = [
        policy_version_spec_path(base_path),
        OUTPUT_ROOT / "checkpoints" / f"{base_path.stem}_latest_checkpoint.json",
        topic_policy_spec_path(base_topic),
        policy_version_spec_path(target_path),
        topic_policy_spec_path(target_topic),
    ]
    spec: Optional[Dict[str, Any]] = None
    source_path: Optional[Path] = None
    for candidate in candidates:
        spec = read_policy_spec_payload(candidate)
        if spec is not None:
            source_path = candidate
            break
    if spec is None:
        return None

    ensure_policy_spec_base_keys(spec)
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["version"] = target_version
        meta["topic_slug"] = target_topic
        meta["version_spec_file"] = policy_version_spec_path(target_path).name
        meta["version_spec_saved_at"] = datetime.now().isoformat(timespec="seconds")
        if author:
            meta["version_spec_saved_by"] = author
        if reason:
            meta["version_spec_reason"] = reason
        if policy_spec_reason_marks_html_runtime_source(reason):
            meta["html_runtime_source"] = True
            meta["html_runtime_source_reason"] = reason
            meta["html_runtime_source_updated_at"] = datetime.now().isoformat(timespec="seconds")
            meta["spec_sync_needed"] = True
            meta["html_spec_sync_status"] = "needs_review"
        if source_path:
            meta["version_spec_source"] = source_path.name

    spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
    version_spec_path = policy_version_spec_path(target_path)
    version_spec_path.write_text(spec_json, encoding="utf-8")
    topic_policy_spec_path(target_topic).write_text(spec_json, encoding="utf-8")
    return version_spec_path


def policy_spec_reason_marks_html_runtime_source(reason: str) -> bool:
    return str(reason or "").strip() in HTML_RUNTIME_SOURCE_SPEC_REASONS


def policy_spec_marks_html_runtime_source(spec: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(spec, Mapping):
        return False
    meta = spec.get("meta") if isinstance(spec.get("meta"), Mapping) else {}
    if not isinstance(meta, Mapping):
        return False
    if truthy_payload_value(meta.get("html_runtime_source")):
        return True
    return policy_spec_reason_marks_html_runtime_source(str(meta.get("version_spec_reason", "") or ""))


def policy_html_has_runtime_source_history(policy_path: Path) -> bool:
    try:
        document = policy_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return any(phrase in document for phrase in HTML_RUNTIME_SOURCE_HISTORY_PHRASES)


def policy_html_is_runtime_source(policy_path: Path, spec: Optional[Mapping[str, Any]]) -> bool:
    return policy_spec_marks_html_runtime_source(spec) or policy_html_has_runtime_source_history(policy_path)


def collect_policy_spec_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, Mapping):
        raw_id = value.get("id")
        if isinstance(raw_id, str) and POLICY_ARTIFACT_ID_PATTERN.match(raw_id):
            ids.add(raw_id)
        for child in value.values():
            ids.update(collect_policy_spec_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(collect_policy_spec_ids(child))
    return ids


def html_spec_sync_snapshot(policy_path: Path, document: str, spec: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    visible = visible_text(document)
    html_ids = sorted(set(POLICY_ARTIFACT_ID_PATTERN.findall(document)))
    spec_ids = sorted(collect_policy_spec_ids(spec or {}))
    missing_spec_ids = sorted(set(spec_ids) - set(html_ids))
    extra_html_ids = sorted(set(html_ids) - set(spec_ids))
    return {
        "policy_file": policy_path.name,
        "html_content_hash": document_content_hash(document),
        "html_visible_text_hash": document_content_hash(visible),
        "html_text_chars": len(visible),
        "html_outline": revision_outline(document)[:40],
        "html_id_count": len(html_ids),
        "spec_id_count": len(spec_ids),
        "missing_spec_id_count": len(missing_spec_ids),
        "extra_html_id_count": len(extra_html_ids),
        "missing_spec_ids_sample": missing_spec_ids[:30],
        "extra_html_ids_sample": extra_html_ids[:30],
    }


def html_spec_sync_status_for_policy(policy_path: Path) -> Dict[str, Any]:
    spec = read_policy_spec_payload(policy_version_spec_path(policy_path)) or read_policy_spec_payload(
        topic_policy_spec_path(parse_policy_filename(policy_path.name).get("topic", ""))
    )
    runtime_source = policy_html_is_runtime_source(policy_path, spec)
    meta = spec.get("meta", {}) if isinstance(spec, Mapping) and isinstance(spec.get("meta"), Mapping) else {}
    try:
        current_hash = document_content_hash(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        current_hash = ""
    synced_hash = str(meta.get("html_spec_sync_content_hash", "") or "").strip() if isinstance(meta, Mapping) else ""
    explicitly_needed = truthy_payload_value(meta.get("spec_sync_needed")) if isinstance(meta, Mapping) else False
    needed = bool(runtime_source and (explicitly_needed or not synced_hash or synced_hash != current_hash))
    status = "needs_review" if needed else "synced" if runtime_source else "spec_source"
    label = "Spec 보정 필요" if needed else "HTML 기준 보정됨" if runtime_source else "Spec 기준"
    return {
        "runtimeSource": runtime_source,
        "needed": needed,
        "status": status,
        "label": label,
        "syncedAt": str(meta.get("html_spec_sync_at", "") or "") if isinstance(meta, Mapping) else "",
        "reason": str(meta.get("html_runtime_source_reason", "") or meta.get("version_spec_reason", "") or "") if isinstance(meta, Mapping) else "",
    }


def sync_policy_spec_from_runtime_html_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("HTML 기준 spec 보정 대상 정책서를 선택해 주세요.")
    policy_path = policy_file_path(name)
    if not policy_path.exists() or not policy_path.is_file():
        raise ValueError("HTML 기준 spec 보정 대상 파일을 찾을 수 없습니다.")
    ensure_policy_editable(policy_path)
    lock_info = acquire_document_job_lock(policy_path.name, job_id=uuid.uuid4().hex, operation="html_spec_sync", session_id=session_id)
    try:
        result = sync_policy_spec_from_runtime_html(policy_path, author=author)
        update_document_lock(lock_info, "completed")
        return result
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def sync_policy_spec_from_runtime_html(policy_path: Path, *, author: str = "Policy Web") -> Dict[str, Any]:
    document = policy_path.read_text(encoding="utf-8")
    parsed = parse_policy_filename(policy_path.name)
    topic_slug = str(parsed.get("topic", "") or "").strip()
    version = str(parsed.get("version", "") or "").strip()
    template_type = "full" if parsed.get("template_label") == "Full" else "simple"
    spec, source_path = load_policy_spec_for_policy_path(policy_path)
    if spec is None:
        spec = {"meta": {}, "document_history": []}
        ensure_policy_spec_base_keys(spec)
    else:
        spec = dict(spec)
        ensure_policy_spec_base_keys(spec)
    snapshot = html_spec_sync_snapshot(policy_path, document, spec)
    now = datetime.now().isoformat(timespec="seconds")
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["topic"] = topic_slug or meta.get("topic", "")
        meta["topic_slug"] = topic_slug
        meta["template_type"] = template_type
        meta["document_type"] = "Full 버전" if template_type == "full" else "간소화 버전"
        meta["version"] = version
        meta["version_spec_file"] = policy_version_spec_path(policy_path).name
        meta["version_spec_saved_at"] = now
        meta["version_spec_saved_by"] = author
        meta["version_spec_reason"] = "html_runtime_spec_sync"
        meta["html_runtime_source"] = True
        meta["html_runtime_source_reason"] = str(meta.get("html_runtime_source_reason", "") or "html_runtime_spec_sync")
        meta["spec_sync_needed"] = False
        meta["html_spec_sync_status"] = "synced"
        meta["html_spec_sync_at"] = now
        meta["html_spec_sync_by"] = author
        meta["html_spec_sync_content_hash"] = snapshot["html_content_hash"]
        meta["html_spec_sync_text_hash"] = snapshot["html_visible_text_hash"]
        if source_path:
            meta["version_spec_source"] = source_path.name
    spec["version"] = version
    spec["html_runtime_snapshot"] = snapshot
    spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
    version_spec_path = policy_version_spec_path(policy_path)
    version_spec_path.write_text(spec_json, encoding="utf-8")
    latest = latest_policy_for_topic(topic_slug, template_type) if topic_slug and topic_slug != "-" else None
    topic_spec_written = False
    if topic_slug and topic_slug != "-" and (latest is None or latest.resolve() == policy_path.resolve() or not topic_policy_spec_path(topic_slug).exists()):
        topic_policy_spec_path(topic_slug).write_text(spec_json, encoding="utf-8")
        topic_spec_written = True
    bpmn_artifacts = write_bpmn_artifacts(spec, OUTPUT_ROOT / f"{policy_path.stem}_전체업무흐름도.bpmn")
    trace_result = write_requirement_trace_report_for_policy(topic_slug, spec, version_spec_path)
    after = evaluate_policy_artifact_drift(policy_path, output_root=OUTPUT_ROOT, reports_root=RUNTIME_REPORTS_ROOT)
    repaired: List[Dict[str, str]] = [
        {"type": "spec", "path": project_relative_path(version_spec_path)},
        {"type": "bpmn", "path": project_relative_path(bpmn_artifacts.bpmn)},
        {"type": "bpmn_viewer", "path": project_relative_path(bpmn_artifacts.viewer)},
    ]
    if topic_spec_written:
        repaired.append({"type": "topic_spec", "path": project_relative_path(topic_policy_spec_path(topic_slug))})
    if trace_result:
        repaired.append(trace_result)
    return {
        "name": policy_path.name,
        "item": describe_policy_file(policy_path),
        "status": "synced",
        "summary": "HTML 기준 spec 보정을 완료했습니다. 사용자가 저장한 HTML은 유지하고 spec 메타와 보조 산출물을 갱신했습니다.",
        "snapshot": snapshot,
        "after": after,
        "repaired": repaired,
    }


def backup_policy_html_before_overwrite(path: Path, *, reason: str) -> Optional[Path]:
    if not path.exists() or not path.is_file():
        return None
    safe_reason = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(reason or "overwrite")).strip("_") or "overwrite"
    backup_dir = OUTPUT_ROOT / "backups" / "policy_html"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"{path.stem}_{safe_reason}_{timestamp}{path.suffix}"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        return backup_path
    except OSError:
        return None


def refresh_topic_policy_spec_from_latest_version(topic: str, template_type: Optional[str] = None) -> Optional[Path]:
    latest_path = latest_policy_for_topic(topic, template_type)
    if not latest_path:
        return None
    spec = read_policy_spec_payload(policy_version_spec_path(latest_path))
    if spec is None:
        return None
    topic_slug = parse_policy_filename(latest_path.name).get("topic", "")
    if not topic_slug or topic_slug == "-":
        return None
    target = topic_policy_spec_path(topic_slug)
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def policy_file_path(name: str) -> Path:
    if "/" in name or "\\" in name or not is_policy_output_name(name):
        raise ValueError("정책서 파일명이 올바르지 않습니다.")
    return safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / name)


def policy_comments_legacy_storage_path_for_name(name: str) -> Path:
    normalized_name = str(name or "").strip()
    if "/" in normalized_name or "\\" in normalized_name or not is_policy_output_name(normalized_name):
        raise ValueError("정책서 파일명이 올바르지 않습니다.")
    digest = hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()[:24]
    return safe_child_path(POLICY_COMMENTS_DIR, POLICY_COMMENTS_DIR / f"policy_comments_{digest}.json")


def policy_comments_storage_path_for_topic(topic: str) -> Path:
    normalized_topic = unicodedata.normalize("NFC", str(topic or "").strip())
    if not normalized_topic or normalized_topic == "-" or "/" in normalized_topic or "\\" in normalized_topic:
        raise ValueError("정책서 주제가 올바르지 않습니다.")
    digest = hashlib.sha256(f"topic:{normalized_topic}".encode("utf-8")).hexdigest()[:24]
    return safe_child_path(POLICY_COMMENTS_DIR, POLICY_COMMENTS_DIR / f"policy_comments_topic_{digest}.json")


def policy_comments_storage_path_for_name(name: str) -> Path:
    normalized_name = str(name or "").strip()
    if "/" in normalized_name or "\\" in normalized_name or not is_policy_output_name(normalized_name):
        raise ValueError("정책서 파일명이 올바르지 않습니다.")
    parsed = parse_policy_filename(normalized_name)
    return policy_comments_storage_path_for_topic(parsed.get("topic", ""))


def policy_comments_storage_path(name: str) -> Path:
    path = policy_file_path(name)
    if not path.exists() or not path.is_file():
        raise ValueError("코멘트를 저장할 정책서 파일을 찾을 수 없습니다.")
    return policy_comments_storage_path_for_name(path.name)


def empty_policy_comments_payload(name: str) -> Dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    parsed = parse_policy_filename(name)
    return {
        "version": 1,
        "topic": parsed.get("topic", ""),
        "policyName": name,
        "createdAt": now,
        "updatedAt": now,
        "comments": [],
    }


def apply_policy_comment_context(comment: Dict[str, Any], name: str, *, content_hash: str = "") -> Dict[str, Any]:
    parsed = parse_policy_filename(name)
    version = parsed.get("version", "") or ""
    if name:
        comment.setdefault("originalPolicyName", name)
        comment.setdefault("lastMatchedPolicyName", name)
    if version:
        comment.setdefault("createdOnVersion", version)
        comment.setdefault("lastMatchedVersion", version)
    if content_hash and not comment.get("contentHash"):
        comment["contentHash"] = limit_comment_text(content_hash, 120)
    return comment


def normalize_policy_comments_for_policy(
    value: Any,
    name: str,
    *,
    preserve_author: bool = False,
    content_hash: str = "",
) -> List[Dict[str, Any]]:
    comments = normalize_policy_comment_list(value, preserve_author=preserve_author)
    return [apply_policy_comment_context(comment, name, content_hash=content_hash) for comment in comments]


def merge_policy_comment_lists(
    base: List[Dict[str, Any]],
    incoming: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    ordered: List[str] = []
    for comment in [*base, *incoming]:
        comment_id = str(comment.get("id", "") or "").strip()
        if not comment_id:
            continue
        if comment_id not in merged:
            ordered.append(comment_id)
        merged[comment_id] = comment
    comments = [merged[comment_id] for comment_id in ordered if comment_id in merged]
    comments.sort(key=lambda item: str(item.get("updatedAt") or item.get("createdAt") or ""), reverse=True)
    return comments[:POLICY_COMMENT_MAX_ITEMS]


def legacy_policy_comment_payloads_for_topic(topic: str) -> List[Tuple[Path, Dict[str, Any]]]:
    if not POLICY_COMMENTS_DIR.exists():
        return []
    payloads: List[Tuple[Path, Dict[str, Any]]] = []
    active_prefix = "policy_comments_topic_"
    for path in POLICY_COMMENTS_DIR.glob("policy_comments_*.json"):
        if not path.is_file() or path.name.startswith(active_prefix):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        policy_name = str(payload.get("policyName", "") or "").strip()
        if parse_policy_filename(policy_name).get("topic") != topic:
            continue
        payloads.append((path, payload))
    return payloads


def migrate_legacy_policy_comments(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    topic = str(payload.get("topic", "") or parse_policy_filename(name).get("topic", "")).strip()
    if not topic:
        return payload
    merged = normalize_policy_comments_for_policy(
        payload.get("comments"),
        name,
        preserve_author=True,
        content_hash=str(payload.get("contentHash", "") or ""),
    )
    migrated_paths: List[Path] = []
    created_at = str(payload.get("createdAt", "") or "")
    updated_at = str(payload.get("updatedAt", "") or "")
    content_hash = str(payload.get("contentHash", "") or "")
    for legacy_path, legacy_payload in legacy_policy_comment_payloads_for_topic(topic):
        legacy_name = str(legacy_payload.get("policyName", "") or name).strip() or name
        legacy_content_hash = str(legacy_payload.get("contentHash", "") or "")
        legacy_comments = normalize_policy_comments_for_policy(
            legacy_payload.get("comments"),
            legacy_name,
            preserve_author=True,
            content_hash=legacy_content_hash,
        )
        merged = merge_policy_comment_lists(merged, legacy_comments)
        migrated_paths.append(legacy_path)
        created_at = min(filter(None, [created_at, str(legacy_payload.get("createdAt", "") or "")]), default=created_at)
        updated_at = max(filter(None, [updated_at, str(legacy_payload.get("updatedAt", "") or "")]), default=updated_at)
        content_hash = content_hash or legacy_content_hash
    if not migrated_paths:
        return payload
    payload["comments"] = merged
    if created_at:
        payload["createdAt"] = created_at
    if updated_at:
        payload["updatedAt"] = updated_at
    if content_hash:
        payload["contentHash"] = content_hash
    saved = save_policy_comments(payload)
    for legacy_path in migrated_paths:
        delete_file_if_exists(legacy_path)
    return saved


def load_policy_comments(name: str) -> Dict[str, Any]:
    policy_path = policy_file_path(name)
    if not policy_path.exists() or not policy_path.is_file():
        raise ValueError("코멘트를 조회할 정책서 파일을 찾을 수 없습니다.")
    parsed = parse_policy_filename(policy_path.name)
    storage_path = policy_comments_storage_path_for_name(policy_path.name)
    if not storage_path.exists():
        payload = empty_policy_comments_payload(policy_path.name)
        return migrate_legacy_policy_comments(policy_path.name, payload)
    try:
        payload = json.loads(storage_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("정책서 코멘트 저장소를 읽을 수 없습니다.") from exc
    if not isinstance(payload, dict):
        payload = empty_policy_comments_payload(policy_path.name)
    payload["policyName"] = policy_path.name
    payload["topic"] = parsed.get("topic", "")
    payload["comments"] = normalize_policy_comments_for_policy(
        payload.get("comments"),
        policy_path.name,
        preserve_author=True,
        content_hash=str(payload.get("contentHash", "") or ""),
    )
    payload.setdefault("version", 1)
    payload.setdefault("createdAt", payload.get("updatedAt") or datetime.now().isoformat(timespec="seconds"))
    payload.setdefault("updatedAt", payload.get("createdAt") or datetime.now().isoformat(timespec="seconds"))
    return migrate_legacy_policy_comments(policy_path.name, payload)


def save_policy_comments(payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("policyName", "") or "").strip()
    if not name:
        raise ValueError("코멘트를 저장할 정책서가 없습니다.")
    parsed = parse_policy_filename(name)
    path = policy_comments_storage_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "version": 1,
        "topic": str(payload.get("topic", "") or parsed.get("topic", "") or ""),
        "policyName": name,
        "createdAt": str(payload.get("createdAt", "") or datetime.now().isoformat(timespec="seconds")),
        "updatedAt": str(payload.get("updatedAt", "") or datetime.now().isoformat(timespec="seconds")),
        "contentHash": str(payload.get("contentHash", "") or ""),
        "comments": normalize_policy_comments_for_policy(
            payload.get("comments"),
            name,
            preserve_author=True,
            content_hash=str(payload.get("contentHash", "") or ""),
        ),
    }
    tmp_path = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return normalized


def public_policy_comments_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "topic": str(payload.get("topic", "") or ""),
        "policyName": str(payload.get("policyName", "") or ""),
        "contentHash": str(payload.get("contentHash", "") or ""),
        "updatedAt": str(payload.get("updatedAt", "") or ""),
        "commentCount": len(payload.get("comments", [])) if isinstance(payload.get("comments"), list) else 0,
        "comments": normalize_policy_comment_list(payload.get("comments"), preserve_author=True),
    }


def update_policy_comments_from_payload(payload: Mapping[str, Any], user: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    name = str(payload.get("name", "") or payload.get("policyName", "") or "").strip()
    if not name:
        raise ValueError("코멘트를 저장할 정책서를 선택해 주세요.")
    action = str(payload.get("action", "") or "add").strip().casefold()
    now = datetime.now().isoformat(timespec="seconds")
    actor = public_comment_author(user, payload)
    content_hash = str(payload.get("contentHash", "") or "")
    with POLICY_COMMENTS_LOCK:
        stored = load_policy_comments(name)
        comments = normalize_policy_comments_for_policy(
            stored.get("comments"),
            name,
            preserve_author=True,
            content_hash=str(stored.get("contentHash", "") or ""),
        )
        if action == "replace":
            comments = normalize_policy_comments_for_policy(
                payload.get("comments"),
                name,
                preserve_author=True,
                content_hash=content_hash,
            )
        elif action == "add":
            raw_comment = dict(payload.get("comment") if isinstance(payload.get("comment"), Mapping) else {})
            raw_comment["author"] = actor
            raw_comment["createdAt"] = raw_comment.get("createdAt") or now
            raw_comment["updatedAt"] = now
            comment = normalize_policy_comment(raw_comment, preserve_author=True)
            apply_policy_comment_context(comment, name, content_hash=content_hash)
            comments = [item for item in comments if item.get("id") != comment.get("id")]
            comments.insert(0, comment)
        elif action == "status":
            comment_id = str(payload.get("id", "") or payload.get("commentId", "") or "").strip()
            status = normalize_policy_comment_status(payload.get("status", ""))
            if not comment_id:
                raise ValueError("상태를 변경할 코멘트를 찾을 수 없습니다.")
            found = False
            next_comments: List[Dict[str, Any]] = []
            for comment in comments:
                if comment.get("id") == comment_id:
                    found = True
                    next_comments.append({**comment, "status": status, "updatedAt": now, "updatedBy": actor})
                else:
                    next_comments.append(comment)
            if not found:
                raise ValueError("상태를 변경할 코멘트를 찾을 수 없습니다.")
            comments = next_comments
        elif action == "delete":
            comment_id = str(payload.get("id", "") or payload.get("commentId", "") or "").strip()
            if not comment_id:
                raise ValueError("삭제할 코멘트를 찾을 수 없습니다.")
            comments = [comment for comment in comments if comment.get("id") != comment_id]
        elif action == "reply":
            comment_id = str(payload.get("id", "") or payload.get("commentId", "") or "").strip()
            if not comment_id:
                raise ValueError("답글을 추가할 코멘트를 찾을 수 없습니다.")
            raw_reply = dict(payload.get("reply") if isinstance(payload.get("reply"), Mapping) else {})
            raw_reply["author"] = actor
            raw_reply["createdAt"] = raw_reply.get("createdAt") or now
            raw_reply["updatedAt"] = now
            reply = normalize_policy_comment_reply(raw_reply, preserve_author=True)
            found = False
            next_comments = []
            for comment in comments:
                if comment.get("id") != comment_id:
                    next_comments.append(comment)
                    continue
                found = True
                replies = normalize_policy_comment_replies(comment.get("replies"), preserve_author=True)
                replies = [item for item in replies if item.get("id") != reply.get("id")]
                replies.append(reply)
                next_comments.append({**comment, "replies": replies[-POLICY_COMMENT_MAX_REPLY_ITEMS:], "updatedAt": now, "updatedBy": actor})
            if not found:
                raise ValueError("답글을 추가할 코멘트를 찾을 수 없습니다.")
            comments = next_comments
        else:
            raise ValueError("지원하지 않는 코멘트 작업입니다.")

        stored["comments"] = comments[:POLICY_COMMENT_MAX_ITEMS]
        stored["updatedAt"] = now
        stored["contentHash"] = content_hash or str(stored.get("contentHash", "") or "")
        return save_policy_comments(stored)


def public_comment_author(user: Mapping[str, Any] | None, payload: Mapping[str, Any]) -> str:
    if user:
        name = str(user.get("name", "") or "").strip()
        if name:
            return limit_comment_text(name, 80)
    return limit_comment_text(str(payload.get("author", "") or payload.get("updatedBy", "") or "Policy Web"), 80) or "Policy Web"


def normalize_policy_comment_status(value: Any) -> str:
    status = str(value or "Open").strip()
    return status if status in POLICY_COMMENT_STATUSES else "Open"


def limit_comment_text(value: Any, limit: int = POLICY_COMMENT_MAX_TEXT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[: max(1, limit)]


def normalize_policy_comment_replies(value: Any, *, preserve_author: bool = False) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    replies = [normalize_policy_comment_reply(item, preserve_author=preserve_author) for item in value if isinstance(item, Mapping)]
    return [item for item in replies if item.get("note")][-POLICY_COMMENT_MAX_REPLY_ITEMS:]


def normalize_policy_comment_reply(value: Mapping[str, Any], *, preserve_author: bool = False) -> Dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    note = limit_comment_text(value.get("note"))
    return {
        "id": limit_comment_text(value.get("id") or f"reply-{uuid.uuid4().hex}", 80),
        "note": note,
        "author": limit_comment_text(value.get("author") if preserve_author else "", 80) or "Policy Web",
        "createdAt": limit_comment_text(value.get("createdAt") or now, 40),
        "updatedAt": limit_comment_text(value.get("updatedAt") or value.get("createdAt") or now, 40),
    }


def normalize_policy_comment(value: Mapping[str, Any], *, preserve_author: bool = False) -> Dict[str, Any]:
    now = datetime.now().isoformat(timespec="seconds")
    comment = {
        "id": limit_comment_text(value.get("id") or f"comment-{uuid.uuid4().hex}", 80),
        "targetText": limit_comment_text(value.get("targetText"), 300),
        "blockText": limit_comment_text(value.get("blockText"), 600),
        "headingPath": [
            limit_comment_text(item, 120)
            for item in value.get("headingPath", [])
            if str(item or "").strip()
        ][:8] if isinstance(value.get("headingPath"), list) else [],
        "targetKey": limit_comment_text(value.get("targetKey"), 360),
        "elementId": limit_comment_text(value.get("elementId"), 120),
        "tableType": limit_comment_text(value.get("tableType"), 120),
        "targetKind": limit_comment_text(value.get("targetKind") or value.get("kind"), 80),
        "note": limit_comment_text(value.get("note")),
        "status": normalize_policy_comment_status(value.get("status")),
        "author": limit_comment_text(value.get("author") if preserve_author else "", 80) or "Policy Web",
        "createdAt": limit_comment_text(value.get("createdAt") or now, 40),
        "updatedAt": limit_comment_text(value.get("updatedAt") or value.get("createdAt") or now, 40),
        "replies": normalize_policy_comment_replies(value.get("replies"), preserve_author=preserve_author),
    }
    if value.get("updatedBy"):
        comment["updatedBy"] = limit_comment_text(value.get("updatedBy"), 80)
    for field in (
        "originalPolicyName",
        "createdOnVersion",
        "lastMatchedPolicyName",
        "lastMatchedVersion",
        "contentHash",
    ):
        if value.get(field):
            comment[field] = limit_comment_text(value.get(field), 160)
    return comment


def normalize_policy_comment_list(value: Any, *, preserve_author: bool = False) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    comments = [normalize_policy_comment(item, preserve_author=preserve_author) for item in value if isinstance(item, Mapping)]
    comments = [item for item in comments if item.get("note")]
    return comments[:POLICY_COMMENT_MAX_ITEMS]


def output_artifact_payload(path: Path) -> Dict[str, str]:
    relative = path.resolve().relative_to(OUTPUT_ROOT.resolve())
    return {
        "name": path.name,
        "path": str(relative),
        "url": f"/output/{quote(str(relative), safe='/')}",
    }


def latest_checkpoint_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    topic = str(payload.get("topic", "")).strip()
    template_type = str(payload.get("templateType", "")).strip() or "simple"
    if not topic:
        return None
    topic_slug = make_topic_slug(topic)
    label = template_file_label(template_type)
    checkpoints_dir = OUTPUT_ROOT / "checkpoints"
    if not checkpoints_dir.exists():
        return None
    candidates = [
        path
        for path in checkpoints_dir.glob(f"NC_{topic_slug}_정책서_{label}_v*_latest_checkpoint.json")
        if path.is_file()
    ]
    if not candidates:
        candidates = [
            path
            for path in checkpoints_dir.glob(f"NC_{topic_slug}_정책서_{label}_v*_checkpoint.json")
            if path.is_file()
        ]
    if not candidates:
        return None
    return output_artifact_payload(max(candidates, key=lambda path: path.stat().st_mtime))


def latest_checkpoint_for_job(job: Dict[str, Any]) -> Optional[Dict[str, str]]:
    return latest_checkpoint_from_payload(
        {
            "topic": job.get("topic", ""),
            "templateType": job.get("templateType", "simple"),
        }
    )


def latest_policy_for_topic(topic: str, template_type: Optional[str] = None) -> Optional[Path]:
    topic_slug = make_topic_slug(topic)
    labels = [template_file_label(template_type)] if template_type else ["간소화", "Full"]
    files = [
        path
        for label in labels
        for path in OUTPUT_ROOT.glob(f"NC_{topic_slug}_정책서_{label}_v*.html")
        if path.is_file() and re_match_policy_filename(path.name)
    ]
    if not files:
        return None
    def sort_key(path: Path) -> tuple[int, int, int, int, float]:
        version = str(parse_policy_filename(path.name).get("version", "") or "")
        minor = re.match(r"^v\d+\.(\d+)", version)
        modern_label = 1 if minor and len(minor.group(1)) >= 2 else 0
        return (*policy_version_sort_key(version), modern_label, path.stat().st_mtime)

    return max(files, key=sort_key)


def visible_text(document: str) -> str:
    text = re.sub(r"<style\b.*?</style>", " ", document, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def limit_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...TRUNCATED..."


def current_time() -> float:
    return time.monotonic()


def elapsed_from_job(job: Dict[str, Any]) -> int:
    started = job.get("_startedMono")
    if not started:
        return 0
    return int((current_time() - float(started)) * 1000)


def stage_by_key(job: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    for stage in job.get("stages", []):
        if stage.get("key") == key:
            return stage
    return None


def close_stage_duration(stage: Dict[str, Any]) -> None:
    started = stage.get("_startedMono")
    if started:
        stage["durationMs"] = int(stage.get("durationMs", 0) + (current_time() - float(started)) * 1000)
        stage["_startedMono"] = None


def mark_running_stage_error(job: Dict[str, Any], message: str) -> None:
    for stage in job.get("stages", []):
        if stage.get("status") == "running":
            close_stage_duration(stage)
            stage["status"] = "error"
            stage["message"] = message
            stage["finishedAt"] = datetime.now().isoformat(timespec="seconds")
            return


def public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    hidden_keys = {"lockKey", "lockPath"}
    clone = {key: value for key, value in job.items() if not key.startswith("_") and key not in hidden_keys}
    if isinstance(clone.get("manualReview"), dict):
        clone["manualReview"] = {
            key: value
            for key, value in clone["manualReview"].items()
            if key != "response"
        }
    clone["elapsedMs"] = (
        elapsed_from_job(job)
        if job.get("status") in {"running", "waiting_review", "canceling"}
        else job.get("elapsedMs", 0)
    )
    stages = []
    now = current_time()
    for stage in job.get("stages", []):
        stage_clone = {key: value for key, value in stage.items() if not key.startswith("_")}
        if stage.get("status") in {"running", "review", "canceling"} and stage.get("_startedMono"):
            stage_clone["durationMs"] = int(stage.get("durationMs", 0) + (now - float(stage["_startedMono"])) * 1000)
        stages.append(stage_clone)
    clone["stages"] = stages
    return clone


def llm_health() -> Dict[str, Any]:
    try:
        client = LLMClient.from_context(Namespace(writer_mode="llm", llm_model="", reasoning_effort=""))
    except Exception as exc:
        return {
            "configured": False,
            "enabled": False,
            "error": str(exc),
        }
    return {
        "configured": client.writer_mode == "mock" or bool(client.api_key),
        "enabled": client.enabled,
        "mode": client.writer_mode,
        "mock": client.writer_mode == "mock",
        "model": client.model,
        "reasoningEffort": client.reasoning_effort,
        "baseUrl": client.base_url,
        "preflightEnabled": llm_preflight_enabled(),
        "routing": routing_plan(client),
    }


def run_llm_preflight_check() -> Dict[str, Any]:
    client = LLMClient.from_context(Namespace(writer_mode="llm", llm_model="", reasoning_effort=""))
    result = client.preflight_check()
    if isinstance(result, dict):
        return result
    return {"ok": True, "message": str(result)}


AGENT_USAGE_ORDER = [
    "Source Collector",
    "Overview Agent",
    "Terms Agent",
    "Actors Agent",
    "Usecase Agent",
    "Usecase Diagram Agent",
    "State Agent",
    "Process Agent",
    "Function Agent",
    "Policy Agent",
    "Process Detail Agent",
    "Function Detail Agent",
    "Terms Review Agent",
    "Final Check Agent",
    "Inspector Agent",
    "Final Revision Agent",
    "Custom Revision Agent",
    "Health Check Agent",
    "System Check",
    "기타",
]

SCHEMA_AGENT_LABELS = {
    "topic_learning": "Source Collector",
    "overview_chapter": "Overview Agent",
    "overview_chapter_patch": "Overview Agent",
    "terms_chapter": "Terms Agent",
    "terms_chapter_patch": "Terms Agent",
    "actors_chapter": "Actors Agent",
    "actors_chapter_patch": "Actors Agent",
    "usecases_chapter": "Usecase Agent",
    "usecases_chapter_patch": "Usecase Agent",
    "usecase_diagram_chapter": "Usecase Diagram Agent",
    "state_chapter": "State Agent",
    "state_chapter_patch": "State Agent",
    "process_chapter": "Process Agent",
    "process_chapter_chunk": "Process Agent",
    "process_chapter_patch": "Process Agent",
    "process_detail_chapter": "Process Detail Agent",
    "process_detail_chapter_chunk": "Process Detail Agent",
    "process_detail_chapter_patch": "Process Detail Agent",
    "functions_chapter": "Function Agent",
    "functions_chapter_chunk": "Function Agent",
    "functions_chapter_patch": "Function Agent",
    "function_detail_chapter": "Function Detail Agent",
    "function_detail_chapter_chunk": "Function Detail Agent",
    "function_detail_chapter_patch": "Function Detail Agent",
    "policies_chapter": "Policy Agent",
    "policies_chapter_chunk": "Policy Agent",
    "policies_chapter_patch": "Policy Agent",
    "terms_refinement_chapter": "Terms Review Agent",
    "final_check_chapter": "Final Check Agent",
    "policy_inspection": "Inspector Agent",
    "policy_json_inspection": "Inspector Agent",
    "final_revision_patch": "Final Revision Agent",
    "revision_intent": "Custom Revision Agent",
    "revision_refinement": "Custom Revision Agent",
    "policy_health_check": "Health Check Agent",
    "codex_connectivity_check": "System Check",
}


def build_agent_usage_dashboard(log_path: Path = LLM_LOG_PATH) -> Dict[str, Any]:
    pricing = load_model_pricing()
    rows: Dict[str, Dict[str, Any]] = {}
    total = empty_agent_usage_row("전체")
    last_updated = ""
    disk_usage_bytes = total_directory_usage_bytes([OUTPUT_ROOT, REPORTS_DIR.parent])
    if log_path.exists() and log_path.is_file():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(event.get("event", "")) not in {"request_success", "request_success_partial"}:
                continue
            schema_name = str(event.get("schema_name", "") or "unknown")
            agent_name = schema_agent_label(schema_name)
            row = rows.setdefault(agent_name, empty_agent_usage_row(agent_name))
            usage = event.get("usage", {})
            if not isinstance(usage, dict):
                usage = {}
            accumulate_agent_usage(row, usage, event, pricing)
            accumulate_agent_usage(total, usage, event, pricing)
            timestamp = str(event.get("timestamp", "")).strip()
            if timestamp and timestamp > last_updated:
                last_updated = timestamp

    public_rows = []
    for row in rows.values():
        public_row = {key: value for key, value in row.items() if not key.startswith("_")}
        public_row["lastUpdated"] = row.get("_lastUpdated", "")
        public_rows.append(public_row)
    ordered_rows = sorted(
        public_rows,
        key=lambda item: (
            AGENT_USAGE_ORDER.index(item["agent"]) if item["agent"] in AGENT_USAGE_ORDER else len(AGENT_USAGE_ORDER),
            item["agent"],
        ),
    )
    summary = {
        "calls": total["calls"],
        "inputTokens": total["inputTokens"],
        "outputTokens": total["outputTokens"],
        "reasoningTokens": total["reasoningTokens"],
        "totalTokens": total["totalTokens"],
        "cachedInputTokens": total["cachedInputTokens"],
        "estimatedCostUsd": round(float(total["estimatedCostUsd"]), 6),
        "diskUsageBytes": disk_usage_bytes,
        "unpricedCalls": total["unpricedCalls"],
        "lastUpdated": last_updated,
        "logPath": project_relative_path(log_path) if log_path.exists() else str(log_path),
        "usageSource": "local_log",
        "costBasis": "Local LLM call log estimate per 1M tokens; override with OPENAI_MODEL_PRICING_JSON.",
    }
    openai_summary = build_openai_usage_summary()
    if openai_summary:
        summary.update(openai_summary)
        summary["diskUsageBytes"] = disk_usage_bytes
        summary["logPath"] = project_relative_path(log_path) if log_path.exists() else str(log_path)
    return {
        "summary": summary,
        "items": ordered_rows,
    }


def build_openai_usage_summary() -> Optional[Dict[str, Any]]:
    """Return organization-level OpenAI Usage/Costs totals when configured.

    Agent-level attribution still comes from our local log because OpenAI's
    organization APIs do not know our internal route/schema names.
    """
    if not env_flag("OPENAI_USAGE_DASHBOARD_ENABLED", True):
        return {
            "usageSource": "local_log",
            "externalUsageStatus": "disabled",
            "externalUsageMessage": "OpenAI Usage API dashboard lookup is disabled by OPENAI_USAGE_DASHBOARD_ENABLED.",
            "costBasis": "OpenAI Usage/Costs API lookup is disabled; showing local LLM log estimate.",
        }
    api_key = openai_usage_api_key()
    if not api_key:
        return {
            "usageSource": "local_log",
            "externalUsageStatus": "not_configured",
            "externalUsageMessage": "Set OPENAI_API_KEY to show OpenAI organization usage totals. OPENAI_USAGE_API_KEY or OPENAI_ADMIN_API_KEY can override it when needed.",
            "costBasis": "OpenAI Usage/Costs API key is not configured; showing local LLM log estimate.",
        }
    end_time = int(time.time())
    days = min(max(OPENAI_USAGE_LOOKBACK_DAYS, 1), 31)
    start_time = end_time - (days * 24 * 60 * 60)
    try:
        usage_payloads = fetch_openai_usage_pages(
            "/organization/usage/completions",
            openai_usage_query_params(start_time, end_time, include_group_by=True),
            api_key,
        )
        cost_payloads = fetch_openai_usage_pages(
            "/organization/costs",
            openai_usage_query_params(start_time, end_time, include_group_by=False),
            api_key,
        )
    except RuntimeError as exc:
        error_payload = openai_usage_error_payload(str(exc))
        return {
            "usageSource": "local_log",
            "externalUsageStatus": error_payload["status"],
            "externalUsageError": str(exc),
            "externalUsageMessage": error_payload["message"],
            "externalUsageDetail": error_payload["detail"],
            "costBasis": error_payload["cost_basis"],
        }
    usage = summarize_openai_completion_usage(usage_payloads)
    cost = summarize_openai_costs(cost_payloads)
    generated_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return {
        "calls": usage["calls"],
        "inputTokens": usage["inputTokens"],
        "outputTokens": usage["outputTokens"],
        "reasoningTokens": usage["reasoningTokens"],
        "totalTokens": usage["totalTokens"],
        "cachedInputTokens": usage["cachedInputTokens"],
        "estimatedCostUsd": round(float(cost.get("estimatedCostUsd", 0.0)), 6),
        "unpricedCalls": 0,
        "lastUpdated": generated_at,
        "usageSource": "openai_api",
        "externalUsageStatus": "ok",
        "lookbackDays": days,
        "costCurrency": cost.get("currency", "usd"),
        "costBasis": "OpenAI organization Usage/Costs API summary; agent rows remain based on local LLM logs.",
    }


def openai_usage_api_key() -> str:
    return (
        os.environ.get("OPENAI_USAGE_API_KEY", "").strip()
        or os.environ.get("OPENAI_ADMIN_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )


def openai_usage_error_payload(error: str) -> Dict[str, str]:
    lower_error = error.lower()
    if "api.usage.read" in lower_error or "insufficient permissions" in lower_error or " 403" in lower_error:
        return {
            "status": "permission_denied",
            "message": "OpenAI Usage/Costs API 조회 권한(api.usage.read)이 없어 로컬 로그 추정치를 표시합니다.",
            "detail": "현재 키는 LLM 호출에는 사용할 수 있지만 조직 사용량 조회 권한이 없을 수 있습니다. OpenAI 키에 api.usage.read 권한을 부여하거나 해당 권한이 있는 키를 사용해야 합니다.",
            "cost_basis": "OpenAI Usage/Costs API 권한 부족으로 로컬 LLM 호출 로그 기준 추정치를 표시합니다.",
        }
    if " 401" in lower_error or "invalid api key" in lower_error or "incorrect api key" in lower_error:
        return {
            "status": "auth_failed",
            "message": "OpenAI Usage/Costs API 인증에 실패해 로컬 로그 추정치를 표시합니다.",
            "detail": "OPENAI_API_KEY 또는 Usage 조회용 키가 유효한지 확인해야 합니다.",
            "cost_basis": "OpenAI Usage/Costs API 인증 실패로 로컬 LLM 호출 로그 기준 추정치를 표시합니다.",
        }
    if "연결 실패" in error or "timed out" in lower_error or "timeout" in lower_error:
        return {
            "status": "network_error",
            "message": "OpenAI Usage/Costs API 연결이 실패해 로컬 로그 추정치를 표시합니다.",
            "detail": "네트워크, 방화벽, OPENAI_USAGE_BASE_URL, 응답 지연 여부를 확인해야 합니다.",
            "cost_basis": "OpenAI Usage/Costs API 연결 실패로 로컬 LLM 호출 로그 기준 추정치를 표시합니다.",
        }
    return {
        "status": "error",
        "message": "OpenAI Usage/Costs API 조회에 실패해 로컬 로그 추정치를 표시합니다.",
        "detail": "Usage 조회 키, 조직 설정, 프로젝트/API 키 필터, 네트워크 접근을 확인해야 합니다.",
        "cost_basis": "OpenAI Usage/Costs API 조회 실패로 로컬 LLM 호출 로그 기준 추정치를 표시합니다.",
    }


def openai_usage_query_params(start_time: int, end_time: int, *, include_group_by: bool) -> List[tuple[str, str]]:
    params: List[tuple[str, str]] = [
        ("start_time", str(start_time)),
        ("end_time", str(end_time)),
        ("bucket_width", "1d"),
        ("limit", str(min(max(OPENAI_USAGE_LOOKBACK_DAYS, 1), 31))),
    ]
    if include_group_by:
        params.append(("group_by", "model"))
    for key, env_name in (
        ("project_ids", "OPENAI_USAGE_PROJECT_IDS"),
        ("api_key_ids", "OPENAI_USAGE_API_KEY_IDS"),
        ("models", "OPENAI_USAGE_MODELS"),
    ):
        for value in env_csv_values(env_name):
            params.append((key, value))
    return params


def env_csv_values(name: str) -> List[str]:
    raw = os.environ.get(name, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def fetch_openai_usage_pages(path: str, params: List[tuple[str, str]], api_key: str) -> List[Mapping[str, Any]]:
    payloads: List[Mapping[str, Any]] = []
    page = ""
    for _ in range(10):
        page_params = list(params)
        if page:
            page_params.append(("page", page))
        payload = fetch_openai_usage_json(path, page_params, api_key)
        payloads.append(payload)
        next_page = str(payload.get("next_page", "") or "").strip()
        if not next_page:
            break
        page = next_page
    return payloads


def fetch_openai_usage_json(path: str, params: List[tuple[str, str]], api_key: str) -> Mapping[str, Any]:
    query = urlencode(params)
    url = f"{OPENAI_USAGE_BASE_URL}{path}?{query}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    organization = os.getenv("OPENAI_USAGE_ORG_ID", "").strip() or os.getenv("OPENAI_ORG_ID", "").strip()
    if organization:
        headers["OpenAI-Organization"] = organization
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=OPENAI_USAGE_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        raise RuntimeError(f"OpenAI Usage API {exc.code}: {detail or exc.reason}") from exc
    except (TimeoutError, URLError, OSError) as exc:
        raise RuntimeError(f"OpenAI Usage API 연결 실패: {exc}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI Usage API가 JSON이 아닌 응답을 반환했습니다.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI Usage API 응답 형식이 올바르지 않습니다.")
    return parsed


def summarize_openai_completion_usage(payloads: List[Mapping[str, Any]]) -> Dict[str, int]:
    calls = 0
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    cached_tokens = 0
    reasoning_tokens = 0
    for result in iter_openai_usage_results(payloads):
        calls += first_int(result, "num_model_requests", "num_requests", "requests")
        result_input = first_int(result, "input_tokens", "prompt_tokens")
        result_output = first_int(result, "output_tokens", "completion_tokens")
        result_cached = first_int(result, "input_cached_tokens", "cached_input_tokens", "cached_tokens")
        result_reasoning = first_int(result, "reasoning_tokens")
        result_total = first_int(result, "total_tokens")
        input_tokens += result_input
        output_tokens += result_output
        cached_tokens += result_cached
        reasoning_tokens += result_reasoning
        total_tokens += result_total or (result_input + result_output)
    return {
        "calls": calls,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "reasoningTokens": reasoning_tokens,
        "totalTokens": total_tokens,
        "cachedInputTokens": cached_tokens,
    }


def summarize_openai_costs(payloads: List[Mapping[str, Any]]) -> Dict[str, Any]:
    total = 0.0
    currency = "usd"
    for result in iter_openai_usage_results(payloads):
        amount = result.get("amount")
        if isinstance(amount, dict):
            value = parse_float(amount.get("value"))
            if value is not None:
                total += value
            currency = str(amount.get("currency", currency) or currency).casefold()
            continue
        value = first_float(result, "cost", "total_cost", "amount_value")
        if value is not None:
            total += value
    return {"estimatedCostUsd": total, "currency": currency}


def iter_openai_usage_results(payloads: List[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    results: List[Mapping[str, Any]] = []
    for payload in payloads:
        buckets = payload.get("data")
        if not isinstance(buckets, list):
            continue
        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            bucket_results = bucket.get("results")
            if isinstance(bucket_results, list):
                results.extend(item for item in bucket_results if isinstance(item, dict))
    return results


def first_int(source: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        if key in source:
            return safe_int(source.get(key))
    return 0


def first_float(source: Mapping[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = parse_float(source.get(key))
        if value is not None:
            return value
    return None


def total_directory_usage_bytes(paths: List[Path]) -> int:
    seen: set[Path] = set()
    total = 0
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        total += directory_usage_bytes(path)
    return total


def directory_usage_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    try:
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def infer_persistent_root() -> Optional[Path]:
    raw = os.environ.get("NC_PERSISTENT_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve(strict=False)

    candidate: Optional[Path] = None
    try:
        output_parent = OUTPUT_ROOT.resolve(strict=False).parent
        reports_root = REPORTS_DIR.parent.resolve(strict=False)
        common_parent = os.path.commonpath([str(output_parent), str(reports_root.parent)])
        candidate = Path(common_parent)
    except (OSError, ValueError):
        candidate = None

    try:
        project_root = PROJECT_ROOT.resolve(strict=False)
    except OSError:
        project_root = PROJECT_ROOT
    if candidate is not None and candidate != project_root and (candidate / "output").exists() and (candidate / "reports").exists():
        return candidate

    hosted_root = Path("/var/data/ncstudio")
    if hosted_root.exists():
        return hosted_root
    return None


def directory_child_usage(root: Path, *, limit: int = 12) -> List[Dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        return []
    children: List[Dict[str, Any]] = []
    try:
        candidates = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError:
        return []
    for child in candidates:
        try:
            safe_child = safe_child_path(root, child)
            if safe_child.is_dir():
                size = directory_usage_bytes(safe_child)
                kind = "directory"
            elif safe_child.is_file():
                size = safe_child.stat().st_size
                kind = "file"
            else:
                continue
        except (OSError, ValueError):
            continue
        children.append(
            {
                "name": safe_child.name,
                "path": str(safe_child),
                "kind": kind,
                "sizeBytes": size,
            }
        )
    return sorted(children, key=lambda item: int(item.get("sizeBytes", 0) or 0), reverse=True)[:limit]


def summarize_deleted_open_files(
    *,
    proc_root: Path = Path("/proc"),
    path_prefix: Optional[Path] = None,
    limit: int = 12,
) -> Dict[str, Any]:
    if not proc_root.exists() or not proc_root.is_dir():
        return {"supported": False, "totalBytes": 0, "items": []}

    prefix = ""
    if path_prefix is not None:
        try:
            prefix = str(path_prefix.resolve(strict=False))
        except OSError:
            prefix = str(path_prefix)

    items: List[Dict[str, Any]] = []
    total = 0
    try:
        pid_dirs = sorted(proc_root.iterdir(), key=lambda item: item.name)
    except OSError:
        return {"supported": True, "totalBytes": 0, "items": []}
    for pid_dir in pid_dirs:
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        if not fd_dir.exists() or not fd_dir.is_dir():
            continue
        try:
            fd_paths = sorted(fd_dir.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        process_name = ""
        try:
            process_name = (pid_dir / "comm").read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            process_name = ""
        for fd_path in fd_paths:
            try:
                target = os.readlink(fd_path)
            except OSError:
                continue
            if " (deleted)" not in target:
                continue
            target_path = target.replace(" (deleted)", "")
            if prefix and not target_path.startswith(prefix):
                continue
            try:
                size = fd_path.stat().st_size
            except OSError:
                size = 0
            total += size
            items.append(
                {
                    "pid": pid_dir.name,
                    "fd": fd_path.name,
                    "process": process_name,
                    "path": target_path,
                    "sizeBytes": size,
                }
            )
    return {
        "supported": True,
        "totalBytes": total,
        "items": sorted(items, key=lambda item: int(item.get("sizeBytes", 0) or 0), reverse=True)[:limit],
    }


def build_disk_usage_summary() -> Dict[str, Any]:
    output_bytes = directory_usage_bytes(OUTPUT_ROOT)
    reports_root = REPORTS_DIR.parent
    reports_bytes = directory_usage_bytes(reports_root)
    known_bytes = total_directory_usage_bytes([OUTPUT_ROOT, reports_root])
    persistent_root = infer_persistent_root()
    persistent_root_bytes = directory_usage_bytes(persistent_root) if persistent_root else 0
    untracked_bytes = max(0, persistent_root_bytes - known_bytes) if persistent_root else 0
    deleted_open_files = summarize_deleted_open_files(path_prefix=persistent_root)
    return {
        "outputBytes": output_bytes,
        "reportsBytes": reports_bytes,
        "totalBytes": known_bytes,
        "persistentRoot": str(persistent_root) if persistent_root else "",
        "persistentRootBytes": persistent_root_bytes,
        "persistentRootChildren": directory_child_usage(persistent_root) if persistent_root else [],
        "untrackedPersistentBytes": untracked_bytes,
        "deletedOpenFileBytes": deleted_open_files["totalBytes"],
        "deletedOpenFiles": deleted_open_files["items"],
        "deletedOpenFileCheckSupported": deleted_open_files["supported"],
    }


def build_service_health_dashboard() -> Dict[str, Any]:
    locks = summarize_service_locks()
    jobs = summarize_service_jobs()
    queue = summarize_service_queue(jobs)
    llm = summarize_service_llm_events()
    usage = summarize_service_user_events()
    disk = build_disk_usage_summary()
    status = "healthy"
    if locks["summary"]["staleLocks"] or jobs["summary"]["cancelingJobs"] or llm["summary"]["recentErrors"] >= 3:
        status = "risk"
    elif locks["summary"]["activeLocks"] or jobs["summary"]["activeJobs"] or llm["summary"]["recentErrors"]:
        status = "warning"
    recommendations = build_service_recommendations(locks, jobs, llm, disk)
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "summary": {
            "activeLocks": locks["summary"]["activeLocks"],
            "staleLocks": locks["summary"]["staleLocks"],
            "cleanupCandidates": locks["summary"]["cleanupCandidates"],
            "activeJobs": jobs["summary"]["activeJobs"],
            "runningJobs": jobs["summary"]["runningJobs"],
            "queuedJobs": queue["summary"]["queuedJobs"],
            "queueLimit": queue["summary"]["limit"],
            "availableQueueSlots": queue["summary"]["availableSlots"],
            "waitingReviewJobs": jobs["summary"]["waitingReviewJobs"],
            "recentLlmErrors": llm["summary"]["recentErrors"],
            "recentLlmRetries": llm["summary"]["recentRetries"],
            "recentUserEvents": usage["summary"]["recentEvents"],
            "recentUiErrors": usage["summary"]["recentErrors"],
            "recentRevisionRequests": usage["summary"]["revisionRequests"],
            "diskUsageBytes": disk.get("persistentRootBytes") or disk["totalBytes"],
        },
        "locks": locks,
        "jobs": jobs,
        "queue": queue,
        "llm": llm,
        "usage": usage,
        "disk": disk,
        "recommendations": recommendations,
    }


def summarize_service_locks() -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    if LOCK_DIR.exists():
        for path in sorted(LOCK_DIR.glob("*.lock"), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            try:
                safe_path = safe_child_path(LOCK_DIR, path)
            except ValueError:
                continue
            items.append(summarize_service_lock_file(safe_path))
    summary = {
        "totalLocks": len(items),
        "activeLocks": sum(1 for item in items if item["active"]),
        "staleLocks": sum(1 for item in items if item["stale"]),
        "inactiveLocks": sum(1 for item in items if not item["active"] and not item["stale"]),
        "cleanupCandidates": sum(1 for item in items if item["cleanupCandidate"]),
    }
    return {"summary": summary, "items": items}


def summarize_service_lock_file(path: Path) -> Dict[str, Any]:
    data = read_policy_job_lock(path)
    status = str(data.get("status", "") or "unknown").strip().casefold()
    active = active_lock(data)
    stale = status in ACTIVE_LOCK_STATUSES and not active
    terminal = status in TERMINAL_LOCK_STATUSES
    lock_key = str(data.get("lock_key") or path.stem)
    age_seconds = lock_age_seconds(data)
    cleanup_candidate = bool((stale or terminal) and not active)
    cleanup_reason = ""
    if stale:
        cleanup_reason = "보호 시간 만료"
    elif terminal:
        cleanup_reason = "종료된 기록"
    return {
        "fileName": path.name,
        "path": project_relative_path(path),
        "lockKey": lock_key,
        "kind": "document" if lock_key.startswith("doc_") else "policy",
        "status": status,
        "operation": str(data.get("operation", "") or ""),
        "topic": str(data.get("topic", "") or ""),
        "file": str(data.get("file_name", "") or ""),
        "jobId": str(data.get("job_id") or data.get("jobId") or ""),
        "sessionId": str(data.get("session_id", "") or ""),
        "currentChapter": str(data.get("current_chapter", "") or ""),
        "startedAt": str(data.get("started_at", "") or ""),
        "updatedAt": str(data.get("updated_at", "") or data.get("started_at", "") or ""),
        "ageSeconds": age_seconds,
        "remainingSeconds": lock_remaining_seconds(data),
        "ttlSeconds": lock_ttl_seconds(data),
        "active": active,
        "stale": stale,
        "cleanupCandidate": cleanup_candidate,
        "cleanupReason": cleanup_reason,
    }


def lock_ttl_seconds(data: Mapping[str, Any]) -> int:
    return DOCUMENT_LOCK_TTL_SECONDS if str(data.get("lock_key", "")).startswith("doc_") else JOB_LOCK_TTL_SECONDS


def lock_timestamp_epoch(data: Mapping[str, Any]) -> float:
    try:
        return float(data.get("updated_at_epoch") or data.get("started_at_epoch") or 0)
    except (TypeError, ValueError):
        return 0.0


def lock_age_seconds(data: Mapping[str, Any]) -> int:
    timestamp = lock_timestamp_epoch(data)
    if not timestamp:
        return 0
    return int(max(0, time.time() - timestamp))


def lock_remaining_seconds(data: Mapping[str, Any]) -> int:
    status = str(data.get("status", "")).strip().casefold()
    if status not in ACTIVE_LOCK_STATUSES:
        return 0
    timestamp = lock_timestamp_epoch(data)
    if not timestamp:
        return 0
    return int(max(0, lock_ttl_seconds(data) - (time.time() - timestamp)))


def summarize_service_jobs() -> Dict[str, Any]:
    with JOBS_LOCK:
        raw_jobs = list(JOBS.values())
    items = [summarize_service_job(job) for job in raw_jobs if isinstance(job, dict)]
    summary = {
        "totalJobs": len(items),
        "activeJobs": sum(1 for item in items if item["active"]),
        "runningJobs": sum(1 for item in items if item["status"] == "running"),
        "waitingReviewJobs": sum(1 for item in items if item["status"] in {"waiting_review", "review"}),
        "cancelingJobs": sum(1 for item in items if item["status"] == "canceling"),
        "errorJobs": sum(1 for item in items if item["status"] == "error"),
    }
    return {"summary": summary, "items": items}


def summarize_service_queue(jobs: Mapping[str, Any]) -> Dict[str, Any]:
    items = jobs.get("items", []) if isinstance(jobs, Mapping) else []
    if not isinstance(items, list):
        items = []
    queued_items = [item for item in items if isinstance(item, dict) and item.get("status") == "queued"]
    occupied_items = [
        item
        for item in items
        if isinstance(item, dict)
        and (
            item.get("status") in {"running", "waiting_review", "review", "retry"}
            or (item.get("status") == "canceling" and bool(item.get("startedAt")))
        )
    ]
    history = summarize_service_queue_history()
    occupied_slots = min(MAX_ACTIVE_POLICY_JOBS, len(occupied_items))
    return {
        "summary": {
            "limit": MAX_ACTIVE_POLICY_JOBS,
            "occupiedSlots": occupied_slots,
            "availableSlots": max(0, MAX_ACTIVE_POLICY_JOBS - occupied_slots),
            "queuedJobs": len(queued_items),
            "runningQueueJobs": len(occupied_items),
            "historyEvents": len(history),
        },
        "items": queued_items + occupied_items,
        "history": history,
    }


def summarize_service_queue_history(limit: int = 12) -> List[Dict[str, Any]]:
    queue_events = {
        "job_queued",
        "job_started_from_queue",
        "job_cancel_requested",
        "job_canceled",
        "client_heartbeat_lost",
    }
    rows: List[Dict[str, Any]] = []
    with JOBS_LOCK:
        jobs = list(JOBS.values())
    for job in jobs:
        if not isinstance(job, dict):
            continue
        topic = str(job.get("topic", "") or "")
        job_id = str(job.get("id", "") or "")
        for entry in job.get("activity", []):
            if not isinstance(entry, dict):
                continue
            event = str(entry.get("event", "") or "")
            if event not in queue_events:
                continue
            rows.append(
                {
                    "jobId": job_id,
                    "topic": topic,
                    "event": event,
                    "status": str(entry.get("status", "") or ""),
                    "stageLabel": str(entry.get("stageLabel", "") or ""),
                    "message": limit_text(str(entry.get("message", "") or ""), 220),
                    "createdAt": str(entry.get("createdAt", "") or ""),
                }
            )
    return sorted(rows, key=lambda item: item.get("createdAt", ""), reverse=True)[:limit]


def summarize_service_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    status = str(job.get("status", "") or "").strip().casefold()
    stage = current_or_active_stage(job) if isinstance(job, dict) else None
    return {
        "id": str(job.get("id", "") or ""),
        "topic": str(job.get("topic", "") or ""),
        "templateType": str(job.get("templateType", "") or ""),
        "writerMode": str(job.get("writerMode", "") or ""),
        "status": status,
        "currentStage": str(job.get("currentStageKey", "") or ""),
        "currentStageLabel": str(stage.get("label", "") if stage else ""),
        "message": str(job.get("message", "") or job.get("error", "") or ""),
        "queuedAt": str(job.get("queuedAt", "") or ""),
        "queueLimit": int(job.get("queueLimit", 0) or 0),
        "startedAt": str(job.get("startedAt", "") or ""),
        "finishedAt": str(job.get("finishedAt", "") or ""),
        "elapsedMs": elapsed_from_job(dict(job)) if status in {"running", "waiting_review", "canceling", "queued"} else int(job.get("elapsedMs", 0) or 0),
        "active": status in CANCELABLE_JOB_STATUSES,
    }


def summarize_service_llm_events(log_path: Path = LLM_LOG_PATH) -> Dict[str, Any]:
    events = read_recent_jsonl(log_path, max_bytes=2 * 1024 * 1024)
    errors = [event for event in events if event.get("event") == "request_error"]
    retries = [event for event in events if event.get("event") == "request_retry"]
    successes = [event for event in events if str(event.get("event", "")).startswith("request_success")]
    last_updated = ""
    for event in events:
        timestamp = str(event.get("timestamp", "") or "")
        if timestamp and timestamp > last_updated:
            last_updated = timestamp
    return {
        "summary": {
            "recentEvents": len(events),
            "recentSuccesses": len(successes),
            "recentErrors": len(errors),
            "recentRetries": len(retries),
            "lastUpdated": last_updated,
            "logPath": project_relative_path(log_path) if log_path.exists() else str(log_path),
        },
        "recentErrors": [summarize_service_llm_event(event) for event in errors[-5:]],
        "recentRetries": [summarize_service_llm_event(event) for event in retries[-5:]],
    }


def read_recent_jsonl(path: Path, *, max_bytes: int = 1_000_000) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            content = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return []
    events: List[Dict[str, Any]] = []
    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def summarize_service_llm_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": str(event.get("timestamp", "") or ""),
        "event": str(event.get("event", "") or ""),
        "schemaName": str(event.get("schema_name", "") or ""),
        "agent": schema_agent_label(str(event.get("schema_name", "") or "")),
        "model": str(event.get("model", "") or ""),
        "attempt": event.get("attempt", ""),
        "error": limit_text(str(event.get("error", "") or event.get("error_type", "") or event.get("retry_reason", "") or ""), 240),
    }


def summarize_service_user_events(log_path: Path = USER_EVENT_LOG_PATH) -> Dict[str, Any]:
    events = read_recent_jsonl(log_path, max_bytes=2 * 1024 * 1024)
    event_counts: Dict[str, int] = {}
    topic_counts: Dict[str, int] = {}
    errors: List[Mapping[str, Any]] = []
    revision_requests = 0
    for event in events:
        event_name = str(event.get("event", "") or "")
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
        details = event.get("details") if isinstance(event.get("details"), Mapping) else {}
        topic = str(details.get("topic") or details.get("selectedName") or details.get("name") or "")
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if event_name.endswith("_failed") or event_name.endswith("_error") or event_name == "ui_error":
            errors.append(event)
        if "revision" in event_name or event_name in {"manual_review_response", "manual_edit_saved"}:
            revision_requests += 1
    return {
        "summary": {
            "recentEvents": len(events),
            "recentErrors": len(errors),
            "revisionRequests": revision_requests,
            "logPath": project_relative_path(log_path) if log_path.exists() else str(log_path),
        },
        "topEvents": summarize_count_map(event_counts, limit=8),
        "topTargets": summarize_count_map(topic_counts, limit=8),
        "recentEvents": [summarize_service_user_event(event) for event in events[-12:]][::-1],
        "recentErrors": [summarize_service_user_event(event) for event in errors[-6:]][::-1],
    }


def summarize_count_map(counts: Mapping[str, int], *, limit: int = 8) -> List[Dict[str, Any]]:
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def summarize_service_user_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    details = event.get("details") if isinstance(event.get("details"), Mapping) else {}
    title = (
        details.get("topic")
        or details.get("selectedName")
        or details.get("name")
        or details.get("resultName")
        or details.get("mode")
        or details.get("status")
        or ""
    )
    detail_bits = [
        details.get("message"),
        details.get("error"),
        details.get("instructionPreview"),
        details.get("action"),
        details.get("writerMode"),
        details.get("reviewMode"),
    ]
    summary = " · ".join(limit_text(str(bit), 160) for bit in detail_bits if bit)
    return {
        "timestamp": str(event.get("timestamp", "") or ""),
        "event": str(event.get("event", "") or ""),
        "source": str(event.get("source", "") or ""),
        "session": str(event.get("session", "") or ""),
        "title": limit_text(str(title), 160),
        "summary": limit_text(summary, 320),
    }


def build_service_recommendations(
    locks: Mapping[str, Any],
    jobs: Mapping[str, Any],
    llm: Mapping[str, Any],
    disk: Mapping[str, Any],
) -> List[Dict[str, str]]:
    recommendations: List[Dict[str, str]] = []
    lock_summary = locks.get("summary", {}) if isinstance(locks.get("summary", {}), dict) else {}
    job_summary = jobs.get("summary", {}) if isinstance(jobs.get("summary", {}), dict) else {}
    llm_summary = llm.get("summary", {}) if isinstance(llm.get("summary", {}), dict) else {}
    if int(lock_summary.get("staleLocks", 0) or 0):
        recommendations.append(
            {
                "severity": "risk",
                "title": "오래된 작업 기록 정리 필요",
                "body": "작업이 비정상 종료되며 오래된 작업 점유 기록이 남아 있습니다. 서비스 관리 팝업에서 기록 정리를 실행해도 현재 진행 중인 작업은 건드리지 않습니다.",
            }
        )
    if int(job_summary.get("activeJobs", 0) or 0):
        recommendations.append(
            {
                "severity": "info",
                "title": "진행 중인 작업 확인",
                "body": "작성 또는 보완 작업이 진행 중입니다. 같은 주제나 같은 문서의 중복 작업은 작업 점유 기록으로 차단됩니다.",
            }
        )
    if int(llm_summary.get("recentErrors", 0) or 0):
        recommendations.append(
            {
                "severity": "warning",
                "title": "최근 LLM 오류 확인",
                "body": "최근 LLM 호출 오류가 있습니다. 대부분 자동 재시도되지만 반복되면 API 키, 네트워크, 모델 설정을 확인해 주세요.",
            }
        )
    effective_disk_bytes = max(
        int(disk.get("totalBytes", 0) or 0),
        int(disk.get("persistentRootBytes", 0) or 0),
    )
    if effective_disk_bytes > 5 * 1024**3:
        recommendations.append(
            {
                "severity": "warning",
                "title": "디스크 사용량 점검",
                "body": "출력물과 로그가 많이 쌓였습니다. 오래된 테스트 산출물 백업 또는 정리 정책을 검토해 주세요.",
            }
        )
    if int(disk.get("deletedOpenFileBytes", 0) or 0) > 0:
        recommendations.append(
            {
                "severity": "warning",
                "title": "삭제됐지만 열려 있는 파일 확인",
                "body": "파일은 삭제됐지만 프로세스가 아직 열고 있어 디스크에서 즉시 해제되지 않는 항목이 있습니다. 해당 작업을 종료하거나 서비스를 재시작하면 공간이 회수될 수 있습니다.",
            }
        )
    elif int(disk.get("untrackedPersistentBytes", 0) or 0) > 512 * 1024**2:
        recommendations.append(
            {
                "severity": "warning",
                "title": "미집계 디스크 영역 확인",
                "body": "output/reports 외 persistent disk 영역 사용량이 큽니다. 디스크 상세에서 상위 폴더를 확인해 정리 대상을 좁힐 수 있습니다.",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "severity": "healthy",
                "title": "서비스 상태 양호",
                "body": "진행 중인 작업과 작업 점유 기록이 정상 범위입니다. 문제가 생기면 이 화면에서 먼저 작업 점유 기록, 작업, LLM 오류를 확인하면 됩니다.",
            }
        )
    return recommendations


def cleanup_service_locks(payload: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    _ = payload or {}
    deleted: List[Dict[str, Any]] = []
    locks = summarize_service_locks()
    for item in locks["items"]:
        if not item.get("cleanupCandidate") or item.get("active"):
            continue
        path = safe_child_path(LOCK_DIR, LOCK_DIR / str(item.get("fileName", "")))
        if not path.exists() or not path.is_file():
            continue
        delete_file(path)
        deleted.append(
            {
                "fileName": item.get("fileName", ""),
                "lockKey": item.get("lockKey", ""),
                "reason": item.get("cleanupReason", ""),
            }
        )
    return {
        "deleted": deleted,
        "service": build_service_health_dashboard(),
    }


def cleanup_stale_intermediate_artifacts(*, now: Optional[float] = None, retention_hours: Optional[int] = None) -> Dict[str, Any]:
    if not INTERMEDIATE_CLEANUP_ENABLED:
        return {
            "enabled": False,
            "retentionHours": retention_hours if retention_hours is not None else INTERMEDIATE_CLEANUP_RETENTION_HOURS,
            "deletedFiles": [],
            "deletedBytes": 0,
        }
    deleted_files: List[str] = []
    deleted_bytes = 0
    if not OUTPUT_ROOT.exists():
        return {
            "enabled": True,
            "retentionHours": retention_hours if retention_hours is not None else INTERMEDIATE_CLEANUP_RETENTION_HOURS,
            "deletedFiles": [],
            "deletedBytes": 0,
        }
    for path in sorted(OUTPUT_ROOT.glob("NC_*_정책서_*_v*.html")):
        if not path.is_file() or not is_policy_output_name(path.name):
            continue
        result = cleanup_policy_intermediate_artifacts(path.name, now=now, retention_hours=retention_hours)
        deleted_files.extend(result.get("deletedFiles", []))
        deleted_bytes += int(result.get("deletedBytes", 0) or 0)
    return {
        "enabled": True,
        "retentionHours": retention_hours if retention_hours is not None else INTERMEDIATE_CLEANUP_RETENTION_HOURS,
        "deletedFiles": sorted(set(deleted_files)),
        "deletedBytes": deleted_bytes,
    }


def cleanup_policy_intermediate_artifacts(
    policy_name: str,
    *,
    now: Optional[float] = None,
    retention_hours: Optional[int] = None,
) -> Dict[str, Any]:
    retention = INTERMEDIATE_CLEANUP_RETENTION_HOURS if retention_hours is None else max(0, int(retention_hours))
    summary = {
        "enabled": INTERMEDIATE_CLEANUP_ENABLED,
        "policyName": policy_name,
        "retentionHours": retention,
        "deletedFiles": [],
        "deletedBytes": 0,
    }
    if not INTERMEDIATE_CLEANUP_ENABLED:
        return summary
    if "/" in policy_name or "\\" in policy_name or not is_policy_output_name(policy_name):
        return summary
    try:
        policy_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / policy_name)
    except ValueError:
        return summary
    if not policy_path.exists() or not policy_path.is_file():
        return summary

    cutoff = (now if now is not None else time.time()) - (retention * 3600)
    stem = policy_path.stem
    deleted: List[Path] = []
    deleted_bytes = 0

    for root, pattern in (
        (OUTPUT_ROOT / "steps", f"{stem}_*.html"),
        (OUTPUT_ROOT / "checkpoints", f"{stem}_*.json"),
    ):
        paths, bytes_removed = delete_stale_matching_files(root, pattern, cutoff)
        deleted.extend(paths)
        deleted_bytes += bytes_removed

    preserved_reports = {
        f"{policy_name}_final_inspection.json",
        f"{policy_name}_full_inspection.json",
        f"{policy_name}_web_inspection.json",
        f"{policy_name}_dev_qa_review.json",
    }
    report_paths, report_bytes = delete_stale_matching_files(
        REPORTS_DIR,
        f"{policy_name}_*.json",
        cutoff,
        preserve_names=preserved_reports,
    )
    deleted.extend(report_paths)
    deleted_bytes += report_bytes

    summary["deletedFiles"] = sorted({project_relative_path(path) for path in deleted})
    summary["deletedBytes"] = deleted_bytes
    return summary


def delete_stale_matching_files(
    root: Path,
    pattern: str,
    cutoff_epoch: float,
    *,
    preserve_names: Optional[set[str]] = None,
) -> tuple[List[Path], int]:
    if not root.exists():
        return [], 0
    preserved = preserve_names or set()
    deleted: List[Path] = []
    deleted_bytes = 0
    for path in sorted(root.glob(pattern)):
        try:
            safe_path = safe_child_path(root, path)
            if not safe_path.is_file() or safe_path.name in preserved:
                continue
            stat = safe_path.stat()
            if stat.st_mtime > cutoff_epoch:
                continue
            deleted_bytes += stat.st_size
            deleted.append(delete_file(safe_path))
        except (OSError, ValueError):
            continue
    return deleted, deleted_bytes


def is_stale_runtime_batch_dir_name(name: str) -> bool:
    if name in {"reference_html", "concept_prototypes", "status", "health_reports", "pi_reports"}:
        return False
    if name.startswith("."):
        return False
    return any(name.startswith(prefix) for prefix in RUNTIME_BATCH_DIR_PREFIXES)


def cleanup_stale_runtime_batch_dirs(
    *,
    now: Optional[float] = None,
    retention_hours: Optional[int] = None,
) -> Dict[str, Any]:
    retention = (
        RUNTIME_BATCH_CLEANUP_RETENTION_HOURS
        if retention_hours is None
        else max(0, int(retention_hours))
    )
    summary = {
        "enabled": INTERMEDIATE_CLEANUP_ENABLED,
        "retentionHours": retention,
        "deletedDirs": [],
        "deletedBytes": 0,
    }
    if not INTERMEDIATE_CLEANUP_ENABLED or not OUTPUT_ROOT.exists():
        return summary

    cutoff = (now if now is not None else time.time()) - (retention * 3600)
    deleted_dirs: List[str] = []
    deleted_bytes = 0
    for path in sorted(OUTPUT_ROOT.iterdir()):
        try:
            safe_path = safe_child_path(OUTPUT_ROOT, path)
            if not safe_path.is_dir() or not is_stale_runtime_batch_dir_name(safe_path.name):
                continue
            if safe_path.stat().st_mtime > cutoff:
                continue
            size = directory_usage_bytes(safe_path)
            shutil.rmtree(safe_path)
            deleted_dirs.append(project_relative_path(safe_path))
            deleted_bytes += size
        except (OSError, ValueError):
            continue

    summary["deletedDirs"] = deleted_dirs
    summary["deletedBytes"] = deleted_bytes
    return summary


def policy_graph_runtime_status() -> Dict[str, Any]:
    with POLICY_GRAPH_BOOTSTRAP_LOCK:
        status = dict(POLICY_GRAPH_BOOTSTRAP_STATUS)
        status["errors"] = list(POLICY_GRAPH_BOOTSTRAP_STATUS.get("errors", []))
    try:
        stat = POLICY_GRAPH_DB_PATH.stat()
        status.update(
            {
                "exists": True,
                "sizeBytes": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    except OSError:
        status.update({"exists": False, "sizeBytes": 0, "modifiedAt": ""})
    return status


def cleanup_policy_graph_runtime_artifacts() -> Dict[str, Any]:
    """Remove interrupted full-rebuild temp files around policy_graph.db."""

    graph_path = POLICY_GRAPH_DB_PATH
    root = graph_path.parent
    result: Dict[str, Any] = {"deleted": [], "deletedBytes": 0}
    if not root.exists() or not root.is_dir():
        return result
    patterns = (
        f".{graph_path.name}.*.tmp",
        f".{graph_path.name}.*.tmp-wal",
        f".{graph_path.name}.*.tmp-shm",
        f"{graph_path.name}.*.tmp",
        f"{graph_path.name}.*.tmp-wal",
        f"{graph_path.name}.*.tmp-shm",
    )
    seen: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path in seen:
                continue
            seen.add(path)
            try:
                safe_path = safe_child_path(root, path)
            except ValueError:
                continue
            if not safe_path.is_file():
                continue
            try:
                size = safe_path.stat().st_size
                safe_path.unlink()
            except OSError:
                continue
            result["deleted"].append(safe_path.name)
            result["deletedBytes"] += size
    return result


def start_policy_graph_bootstrap() -> None:
    if not POLICY_GRAPH_BOOTSTRAP_ENABLED:
        update_policy_graph_bootstrap_status(status="disabled", reason="NC_POLICY_GRAPH_BOOTSTRAP_ENABLED is disabled")
        return

    cleanup = cleanup_policy_graph_runtime_artifacts()
    if cleanup.get("deleted"):
        print(
            "[policy-graph] removed "
            f"{len(cleanup['deleted'])} stale temp artifact(s), "
            f"{cleanup.get('deletedBytes', 0)} bytes"
        )

    spec_paths = policy_graph_spec_paths()
    plan = policy_graph_bootstrap_plan(spec_paths, POLICY_GRAPH_DB_PATH)
    action = str(plan.get("action", "full") or "full")
    if action == "ready":
        update_policy_graph_bootstrap_status(
            status="ready",
            reason=str(plan.get("reason", "exists") or "exists"),
            mode=str(plan.get("mode", "ready") or "ready"),
            specFileCount=len(spec_paths),
            processedSpecFileCount=len(spec_paths),
            documentCount=len(spec_paths),
            changedSpecFileCount=0,
            deletedSpecFileCount=0,
        )
        return
    if action == "seed":
        seed_policy_graph_bootstrap_metadata(spec_paths, plan)
        update_policy_graph_bootstrap_status(
            status="ready",
            reason=str(plan.get("reason", "metadata_seeded") or "metadata_seeded"),
            mode="seed",
            specFileCount=len(spec_paths),
            processedSpecFileCount=len(spec_paths),
            documentCount=len(spec_paths),
            changedSpecFileCount=0,
            deletedSpecFileCount=0,
        )
        return
    if action == "skipped":
        update_policy_graph_bootstrap_status(status="skipped", reason="No policy spec files found")
        return

    if POLICY_GRAPH_BOOTSTRAP_ASYNC:
        thread = threading.Thread(
            target=run_policy_graph_bootstrap_plan,
            args=(spec_paths, plan),
            name="policy-graph-bootstrap",
            daemon=True,
        )
        thread.start()
        return

    run_policy_graph_bootstrap_plan(spec_paths, plan)


def update_policy_graph_bootstrap_status(**updates: Any) -> None:
    with POLICY_GRAPH_BOOTSTRAP_LOCK:
        POLICY_GRAPH_BOOTSTRAP_STATUS.update(updates)


def policy_graph_spec_paths() -> List[Path]:
    if not OUTPUT_ROOT.exists() or not OUTPUT_ROOT.is_dir():
        return []
    candidates: Dict[tuple[str, str], Path] = {}
    for path in OUTPUT_ROOT.iterdir():
        if not path.is_file() or path.parent != OUTPUT_ROOT or not re_match_policy_filename(path.name):
            continue
        parsed = parse_policy_filename(path.name)
        topic = str(parsed.get("topic", "") or "").strip()
        template_label = str(parsed.get("template_label", "") or "").strip()
        if not topic or not template_label or topic == "-" or template_label == "-":
            continue
        key = (normalize_topic_key(topic), template_label)
        previous = candidates.get(key)
        if previous is None or policy_graph_policy_html_sort_key(path) > policy_graph_policy_html_sort_key(previous):
            candidates[key] = path

    spec_paths: List[Path] = []
    seen: set[Path] = set()
    for policy_path in sorted(candidates.values(), key=lambda item: item.name):
        parsed = parse_policy_filename(policy_path.name)
        topic = str(parsed.get("topic", "") or "").strip()
        for spec_path in (policy_version_spec_path(policy_path), topic_policy_spec_path(topic)):
            try:
                resolved = spec_path.resolve(strict=False)
            except OSError:
                resolved = spec_path
            if resolved in seen or not spec_path.is_file():
                continue
            seen.add(resolved)
            spec_paths.append(spec_path)
            break
    return sorted(spec_paths)


def policy_graph_policy_html_sort_key(path: Path) -> tuple[tuple[int, int, int], int, str]:
    parsed = parse_policy_filename(path.name)
    try:
        mtime_ns = int(path.stat().st_mtime_ns)
    except OSError:
        mtime_ns = 0
    return (version_sort_key(str(parsed.get("version", "") or "")), mtime_ns, path.name)


def should_rebuild_policy_graph(spec_paths: List[Path], graph_path: Path) -> tuple[bool, str]:
    if POLICY_GRAPH_BOOTSTRAP_FORCE:
        return True, "forced"
    try:
        graph_stat = graph_path.stat()
    except OSError:
        return True, "missing"
    if graph_stat.st_size <= 0:
        return True, "empty"
    newest_spec_mtime = 0.0
    for path in spec_paths:
        try:
            newest_spec_mtime = max(newest_spec_mtime, path.stat().st_mtime)
        except OSError:
            continue
    if newest_spec_mtime and newest_spec_mtime > graph_stat.st_mtime:
        return True, "stale"
    return False, "exists"


def run_policy_graph_bootstrap_plan(spec_paths: List[Path], plan: Mapping[str, Any]) -> None:
    action = str(plan.get("action", "full") or "full")
    reason = str(plan.get("reason", action) or action)
    if action == "incremental":
        try:
            update_runtime_policy_graph_incrementally(spec_paths, plan)
            return
        except Exception as exc:  # pragma: no cover - operational fallback.
            print(f"[policy-graph] incremental bootstrap failed, falling back to full rebuild: {exc}")
            update_policy_graph_bootstrap_status(
                status="running",
                reason=f"incremental_fallback:{reason}",
                mode="full",
                errors=[{"path": project_relative_path(POLICY_GRAPH_DB_PATH), "error": str(exc)}],
            )
            rebuild_runtime_policy_graph(spec_paths, f"incremental_fallback:{reason}", plan.get("sourceSignature"))
            return
    rebuild_runtime_policy_graph(spec_paths, reason, plan.get("sourceSignature"))


def policy_graph_bootstrap_plan(spec_paths: List[Path], graph_path: Path) -> Dict[str, Any]:
    source_signature = policy_graph_source_signature()
    if not spec_paths:
        return {"action": "skipped", "reason": "no_spec_files", "mode": "skipped", "sourceSignature": source_signature}
    if POLICY_GRAPH_BOOTSTRAP_FORCE:
        return {"action": "full", "reason": "forced", "mode": "full", "sourceSignature": source_signature}
    try:
        graph_stat = graph_path.stat()
    except OSError:
        return {"action": "full", "reason": "missing", "mode": "full", "sourceSignature": source_signature}
    if graph_stat.st_size <= 0:
        return {"action": "full", "reason": "empty", "mode": "full", "sourceSignature": source_signature}
    if not POLICY_GRAPH_INCREMENTAL_ENABLED:
        rebuild, reason = should_rebuild_policy_graph(spec_paths, graph_path)
        return {
            "action": "full" if rebuild else "ready",
            "reason": reason,
            "mode": "full" if rebuild else "ready",
            "sourceSignature": source_signature,
        }

    metadata = read_policy_graph_metadata(graph_path)
    stored_source_signature = policy_graph_metadata_json(metadata, POLICY_GRAPH_BOOTSTRAP_SOURCE_KEY)
    if stored_source_signature and stored_source_signature != source_signature:
        return {"action": "full", "reason": "source_changed", "mode": "full", "sourceSignature": source_signature}
    if not stored_source_signature and policy_graph_sources_newer_than(graph_stat.st_mtime_ns):
        return {"action": "full", "reason": "source_stale", "mode": "full", "sourceSignature": source_signature}

    manifest = policy_graph_metadata_json(metadata, POLICY_GRAPH_BOOTSTRAP_MANIFEST_KEY)
    if not policy_graph_manifest_is_usable(manifest):
        if (
            policy_graph_document_count(graph_path) == len(spec_paths)
            and not policy_graph_specs_newer_than(spec_paths, graph_stat.st_mtime_ns)
        ):
            return {"action": "seed", "reason": "metadata_seed", "mode": "seed", "sourceSignature": source_signature}
        return {"action": "full", "reason": "manifest_missing", "mode": "full", "sourceSignature": source_signature}

    old_specs = manifest.get("specs", {}) if isinstance(manifest.get("specs"), Mapping) else {}
    current_keys = {policy_graph_spec_manifest_key(path) for path in spec_paths}
    changed_paths: List[Path] = []
    for path in spec_paths:
        key = policy_graph_spec_manifest_key(path)
        old_entry = old_specs.get(key, {}) if isinstance(old_specs.get(key), Mapping) else {}
        if not policy_graph_spec_signature_matches(path, old_entry):
            changed_paths.append(path)
    deleted_entries = [
        dict(entry)
        for key, entry in old_specs.items()
        if key not in current_keys and isinstance(entry, Mapping)
    ]
    if not changed_paths and not deleted_entries:
        if not stored_source_signature:
            return {"action": "seed", "reason": "metadata_seed", "mode": "seed", "sourceSignature": source_signature}
        return {"action": "ready", "reason": "exists", "mode": "ready", "sourceSignature": source_signature}
    return {
        "action": "incremental",
        "reason": "spec_delta",
        "mode": "incremental",
        "sourceSignature": source_signature,
        "changedPaths": [str(path) for path in changed_paths],
        "deletedEntries": deleted_entries,
        "changedSpecFileCount": len(changed_paths),
        "deletedSpecFileCount": len(deleted_entries),
    }


def policy_graph_file_signature(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "mtimeNs": 0, "sizeBytes": 0}
    return {"exists": True, "mtimeNs": int(stat.st_mtime_ns), "sizeBytes": int(stat.st_size)}


def policy_graph_source_signature() -> Dict[str, Any]:
    return {
        "version": POLICY_GRAPH_BOOTSTRAP_MANIFEST_VERSION,
        "requirements": policy_graph_file_signature(REQUIREMENTS_DB_PATH),
        "reference": policy_graph_file_signature(REFERENCE_DB_PATH),
    }


def policy_graph_sources_newer_than(mtime_ns: int) -> bool:
    for path in (REQUIREMENTS_DB_PATH, REFERENCE_DB_PATH):
        try:
            if path.stat().st_mtime_ns > mtime_ns:
                return True
        except OSError:
            continue
    return False


def policy_graph_specs_newer_than(spec_paths: List[Path], mtime_ns: int) -> bool:
    for path in spec_paths:
        try:
            if path.stat().st_mtime_ns > mtime_ns:
                return True
        except OSError:
            continue
    return False


def policy_graph_spec_manifest_key(path: Path) -> str:
    try:
        return str(path.relative_to(OUTPUT_ROOT))
    except ValueError:
        return project_relative_path(path)


def policy_graph_spec_manifest_entry(path: Path, document_id: str = "") -> Dict[str, Any]:
    signature = policy_graph_file_signature(path)
    return {
        "path": policy_graph_spec_manifest_key(path),
        "documentId": str(document_id or ""),
        "mtimeNs": signature["mtimeNs"],
        "sizeBytes": signature["sizeBytes"],
    }


def policy_graph_spec_signature_matches(path: Path, entry: Mapping[str, Any]) -> bool:
    signature = policy_graph_file_signature(path)
    try:
        return int(entry.get("mtimeNs", -1)) == signature["mtimeNs"] and int(entry.get("sizeBytes", -1)) == signature["sizeBytes"]
    except (TypeError, ValueError):
        return False


def read_policy_graph_metadata(graph_path: Path) -> Dict[str, str]:
    if not graph_path.exists():
        return {}
    try:
        with sqlite3.connect(graph_path) as conn:
            rows = conn.execute("SELECT key, value FROM graph_metadata").fetchall()
    except sqlite3.Error:
        return {}
    return {str(key): str(value) for key, value in rows}


def policy_graph_metadata_json(metadata: Mapping[str, str], key: str) -> Dict[str, Any]:
    raw = str(metadata.get(key, "") or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def policy_graph_manifest_is_usable(manifest: Mapping[str, Any]) -> bool:
    return (
        isinstance(manifest, Mapping)
        and str(manifest.get("version", "") or "") == POLICY_GRAPH_BOOTSTRAP_MANIFEST_VERSION
        and isinstance(manifest.get("specs"), Mapping)
    )


def policy_graph_document_count(graph_path: Path) -> int:
    try:
        with sqlite3.connect(graph_path) as conn:
            row = conn.execute("SELECT COUNT(DISTINCT document_id) FROM graph_nodes WHERE node_type = ?", ("DocumentVersion",)).fetchone()
    except sqlite3.Error:
        return 0
    return int(row[0] or 0) if row else 0


def policy_graph_document_id_from_spec_path(spec_path: Path) -> str:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, Mapping):
        raise ValueError("spec JSON root is not an object")
    topic = policy_graph_spec_topic(spec, spec_path.stem)
    return document_node_source_id(spec, topic)


def build_policy_graph_manifest(
    spec_paths: List[Path],
    *,
    existing_manifest: Mapping[str, Any] | None = None,
    built_document_ids: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    old_specs = existing_manifest.get("specs", {}) if isinstance(existing_manifest, Mapping) and isinstance(existing_manifest.get("specs"), Mapping) else {}
    built_ids = dict(built_document_ids or {})
    specs: Dict[str, Any] = {}
    for path in spec_paths:
        key = policy_graph_spec_manifest_key(path)
        old_entry = old_specs.get(key, {}) if isinstance(old_specs.get(key), Mapping) else {}
        document_id = built_ids.get(key) or str(old_entry.get("documentId", "") or "")
        if not document_id:
            document_id = policy_graph_document_id_from_spec_path(path)
        specs[key] = policy_graph_spec_manifest_entry(path, document_id=document_id)
    return {
        "version": POLICY_GRAPH_BOOTSTRAP_MANIFEST_VERSION,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "specs": specs,
    }


def write_policy_graph_bootstrap_metadata(
    graph_path: Path,
    *,
    manifest: Mapping[str, Any],
    source_signature: Mapping[str, Any],
    mode: str,
) -> None:
    with sqlite3.connect(graph_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        payloads = {
            POLICY_GRAPH_BOOTSTRAP_MANIFEST_KEY: json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            POLICY_GRAPH_BOOTSTRAP_SOURCE_KEY: json.dumps(source_signature, ensure_ascii=False, sort_keys=True),
            POLICY_GRAPH_BOOTSTRAP_MODE_KEY: mode,
        }
        conn.executemany("INSERT OR REPLACE INTO graph_metadata(key, value) VALUES (?, ?)", payloads.items())
        conn.commit()


def compact_policy_graph_database(graph_path: Path) -> Dict[str, Any]:
    if not graph_path.exists() or not graph_path.is_file():
        return {"compacted": False, "reason": "missing"}
    try:
        before = graph_path.stat().st_size
    except OSError:
        before = 0
    try:
        with sqlite3.connect(graph_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
            conn.execute("PRAGMA optimize")
            conn.commit()
    except sqlite3.Error as exc:
        return {"compacted": False, "reason": str(exc), "beforeBytes": before}
    try:
        after = graph_path.stat().st_size
    except OSError:
        after = before
    return {
        "compacted": True,
        "beforeBytes": before,
        "afterBytes": after,
        "savedBytes": max(0, before - after),
    }


def seed_policy_graph_bootstrap_metadata(spec_paths: List[Path], plan: Mapping[str, Any]) -> None:
    manifest = build_policy_graph_manifest(spec_paths)
    write_policy_graph_bootstrap_metadata(
        POLICY_GRAPH_DB_PATH,
        manifest=manifest,
        source_signature=plan.get("sourceSignature", policy_graph_source_signature()),
        mode="seed",
    )


def delete_policy_graph_document(conn: sqlite3.Connection, document_id: str) -> None:
    if not document_id:
        return
    conn.execute("DELETE FROM graph_edges WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM graph_nodes WHERE document_id = ?", (document_id,))


def update_runtime_policy_graph_incrementally(spec_paths: List[Path], plan: Mapping[str, Any]) -> None:
    started = time.time()
    started_at = datetime.now().isoformat(timespec="seconds")
    graph_path = POLICY_GRAPH_DB_PATH
    changed_paths = [Path(path) for path in plan.get("changedPaths", []) if str(path or "").strip()]
    deleted_entries = [dict(entry) for entry in plan.get("deletedEntries", []) if isinstance(entry, Mapping)]
    metadata = read_policy_graph_metadata(graph_path)
    existing_manifest = policy_graph_metadata_json(metadata, POLICY_GRAPH_BOOTSTRAP_MANIFEST_KEY)
    built_document_ids: Dict[str, str] = {}
    update_policy_graph_bootstrap_status(
        status="running",
        reason=str(plan.get("reason", "spec_delta") or "spec_delta"),
        mode="incremental",
        startedAt=started_at,
        finishedAt="",
        elapsedMs=0,
        specFileCount=len(spec_paths),
        processedSpecFileCount=0,
        documentCount=policy_graph_document_count(graph_path),
        changedSpecFileCount=len(changed_paths),
        deletedSpecFileCount=len(deleted_entries),
        errorCount=0,
        errors=[],
    )

    with sqlite3.connect(graph_path) as conn:
        for entry in deleted_entries:
            delete_policy_graph_document(conn, str(entry.get("documentId", "") or ""))
        conn.commit()

    errors: List[Dict[str, str]] = []
    old_specs = existing_manifest.get("specs", {}) if isinstance(existing_manifest.get("specs"), Mapping) else {}
    for index, spec_path in enumerate(changed_paths, start=1):
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            if not isinstance(spec, Mapping):
                raise ValueError("spec JSON root is not an object")
            topic = policy_graph_spec_topic(spec, spec_path.stem)
            result = build_policy_graph(spec, topic=topic, graph_db_path=graph_path)
            key = policy_graph_spec_manifest_key(spec_path)
            old_entry = old_specs.get(key, {}) if isinstance(old_specs.get(key), Mapping) else {}
            old_document_id = str(old_entry.get("documentId", "") or "")
            if old_document_id and old_document_id != result.document_id:
                with sqlite3.connect(graph_path) as conn:
                    delete_policy_graph_document(conn, old_document_id)
                    conn.commit()
            built_document_ids[key] = result.document_id
        except Exception as exc:  # pragma: no cover - operational fallback.
            errors.append({"path": project_relative_path(spec_path), "error": str(exc)})
        if index == 1 or index % 10 == 0 or index == len(changed_paths):
            update_policy_graph_bootstrap_status(
                processedSpecFileCount=index,
                errorCount=len(errors),
                errors=errors[:5],
                elapsedMs=int((time.time() - started) * 1000),
            )

    if errors:
        raise RuntimeError(f"{len(errors)} incremental graph update error(s)")

    manifest = build_policy_graph_manifest(spec_paths, existing_manifest=existing_manifest, built_document_ids=built_document_ids)
    write_policy_graph_bootstrap_metadata(
        graph_path,
        manifest=manifest,
        source_signature=plan.get("sourceSignature", policy_graph_source_signature()),
        mode="incremental",
    )
    compact_result = compact_policy_graph_database(graph_path)
    if compact_result.get("compacted"):
        print(
            "[policy-graph] compacted incremental db: "
            f"{compact_result.get('beforeBytes', 0)} -> {compact_result.get('afterBytes', 0)} bytes"
        )
    document_count = policy_graph_document_count(graph_path)
    update_policy_graph_bootstrap_status(
        status="ready",
        reason=str(plan.get("reason", "spec_delta") or "spec_delta"),
        mode="incremental",
        finishedAt=datetime.now().isoformat(timespec="seconds"),
        elapsedMs=int((time.time() - started) * 1000),
        processedSpecFileCount=len(spec_paths),
        documentCount=document_count,
        errorCount=0,
        errors=[],
        compacted=compact_result,
    )
    print(
        "[policy-graph] incremental bootstrap completed: "
        f"{len(changed_paths)} changed, {len(deleted_entries)} deleted, {document_count} document(s)"
    )


def rebuild_runtime_policy_graph(spec_paths: List[Path], reason: str, source_signature: Mapping[str, Any] | None = None) -> None:
    started = time.time()
    started_at = datetime.now().isoformat(timespec="seconds")
    graph_path = POLICY_GRAPH_DB_PATH
    temp_path = graph_path.with_name(f".{graph_path.name}.{uuid.uuid4().hex}.tmp")
    update_policy_graph_bootstrap_status(
        status="running",
        reason=reason,
        mode="full",
        startedAt=started_at,
        finishedAt="",
        elapsedMs=0,
        specFileCount=len(spec_paths),
        processedSpecFileCount=0,
        documentCount=0,
        changedSpecFileCount=len(spec_paths),
        deletedSpecFileCount=0,
        errorCount=0,
        errors=[],
    )
    documents = 0
    errors: List[Dict[str, str]] = []
    built_document_ids: Dict[str, str] = {}
    try:
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        if temp_path.exists():
            temp_path.unlink()
        for index, spec_path in enumerate(spec_paths, start=1):
            try:
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                if not isinstance(spec, Mapping):
                    raise ValueError("spec JSON root is not an object")
                topic = policy_graph_spec_topic(spec, spec_path.stem)
                result = build_policy_graph(spec, topic=topic, graph_db_path=temp_path)
                built_document_ids[policy_graph_spec_manifest_key(spec_path)] = result.document_id
                documents += 1
            except Exception as exc:  # pragma: no cover - operational fallback.
                errors.append({"path": project_relative_path(spec_path), "error": str(exc)})
            if index == 1 or index % 10 == 0 or index == len(spec_paths):
                update_policy_graph_bootstrap_status(
                    processedSpecFileCount=index,
                    documentCount=documents,
                    errorCount=len(errors),
                    errors=errors[:5],
                    elapsedMs=int((time.time() - started) * 1000),
                )
        if documents:
            manifest = build_policy_graph_manifest(spec_paths, built_document_ids=built_document_ids)
            write_policy_graph_bootstrap_metadata(
                temp_path,
                manifest=manifest,
                source_signature=source_signature or policy_graph_source_signature(),
                mode="full",
            )
            compact_result = compact_policy_graph_database(temp_path)
            if compact_result.get("compacted"):
                print(
                    "[policy-graph] compacted full db: "
                    f"{compact_result.get('beforeBytes', 0)} -> {compact_result.get('afterBytes', 0)} bytes"
                )
            os.replace(temp_path, graph_path)
        else:
            compact_result = {"compacted": False, "reason": "no_documents"}
        if not documents and temp_path.exists():
            temp_path.unlink()
        final_status = "ready" if documents and not errors else ("ready_with_errors" if documents else "failed")
        update_policy_graph_bootstrap_status(
            status=final_status,
            finishedAt=datetime.now().isoformat(timespec="seconds"),
            elapsedMs=int((time.time() - started) * 1000),
            processedSpecFileCount=len(spec_paths),
            documentCount=documents,
            changedSpecFileCount=len(spec_paths),
            deletedSpecFileCount=0,
            errorCount=len(errors),
            errors=errors[:5],
            compacted=compact_result,
        )
        print(
            "[policy-graph] bootstrap "
            f"{'completed' if not errors else 'completed with errors'}: "
            f"{documents}/{len(spec_paths)} spec file(s), {len(errors)} error(s)"
        )
    except Exception as exc:  # pragma: no cover - defensive startup boundary.
        update_policy_graph_bootstrap_status(
            status="failed",
            mode="full",
            finishedAt=datetime.now().isoformat(timespec="seconds"),
            elapsedMs=int((time.time() - started) * 1000),
            errorCount=len(errors) + 1,
            errors=[*errors[:4], {"path": project_relative_path(graph_path), "error": str(exc)}],
        )
        print(f"[policy-graph] bootstrap failed: {exc}")
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def policy_graph_spec_topic(spec: Mapping[str, Any], fallback: str = "") -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    return str(
        meta.get("topic_display")
        or meta.get("topic")
        or spec.get("topic")
        or fallback
        or ""
    ).strip()


def bootstrap_runtime_data() -> None:
    apply_runtime_cleanup_manifests()
    sync_seed_directory(PROJECT_ROOT / "output", OUTPUT_ROOT)
    sync_policy_seed_once(PROJECT_ROOT / "output", OUTPUT_ROOT)
    sync_seed_directory(PROJECT_ROOT / "reports", REPORTS_DIR.parent)
    bpmn_migration = migrate_runtime_bpmn_io_artifacts()
    if bpmn_migration.get("updated"):
        print(
            "[migration] bpmn.io rerendered "
            f"{len(bpmn_migration.get('updated', []))} persisted policy document(s)"
        )
    cleanup = cleanup_stale_intermediate_artifacts()
    if cleanup.get("deletedFiles"):
        print(
            "[cleanup] removed "
            f"{len(cleanup['deletedFiles'])} intermediate artifact(s), "
            f"{cleanup.get('deletedBytes', 0)} bytes"
        )
    batch_cleanup = cleanup_stale_runtime_batch_dirs()
    if batch_cleanup.get("deletedDirs"):
        print(
            "[cleanup] removed "
            f"{len(batch_cleanup['deletedDirs'])} runtime batch dir(s), "
            f"{batch_cleanup.get('deletedBytes', 0)} bytes"
        )
    start_policy_graph_bootstrap()


def sync_seed_directory(source_root: Path, target_root: Path) -> None:
    try:
        if source_root.resolve() == target_root.resolve():
            return
    except OSError:
        pass
    if not source_root.exists() or not source_root.is_dir():
        return
    target_root.mkdir(parents=True, exist_ok=True)
    reference_manifest = load_reference_seed_manifest(target_root)
    reference_manifest_changed = False
    copied = 0
    for source_path in source_root.rglob("*"):
        relative = source_path.relative_to(source_root)
        if should_skip_seed_path(relative):
            continue
        target_path = target_root / relative
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        if not source_path.is_file():
            continue
        overwrite_seed = should_overwrite_seed_path(relative)
        if target_path.exists() and not overwrite_seed:
            continue
        if target_path.exists() and overwrite_seed:
            should_update, manifest_changed = should_update_reference_seed_file(
                relative,
                source_path,
                target_path,
                reference_manifest,
            )
            reference_manifest_changed = reference_manifest_changed or manifest_changed
            if not should_update:
                continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source_path, target_path)
            if is_reference_seed_path(relative):
                reference_manifest_changed = record_reference_seed_manifest(
                    reference_manifest,
                    relative,
                    source_path,
                    target_path,
                    copied=True,
                ) or reference_manifest_changed
            copied += 1
        except OSError:
            continue
    if reference_manifest_changed:
        save_reference_seed_manifest(target_root, reference_manifest)
    if copied:
        print(f"[seed] {source_root} -> {target_root} ({copied} files)")


def should_skip_seed_path(relative: Path) -> bool:
    name = relative.name
    if name == ".DS_Store":
        return True
    if any(part == "__pycache__" for part in relative.parts):
        return True
    return False


def should_overwrite_seed_path(relative: Path) -> bool:
    return bool(relative.parts and relative.parts[0] == "reference_html")


def is_reference_seed_path(relative: Path) -> bool:
    return bool(relative.parts and relative.parts[0] == "reference_html")


def reference_seed_manifest_path(target_root: Path) -> Path:
    return target_root / ".seed_manifests" / "reference_html.json"


def load_reference_seed_manifest(target_root: Path) -> Dict[str, Any]:
    path = reference_seed_manifest_path(target_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "files": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "files": {}}
    files = payload.get("files")
    if not isinstance(files, dict):
        payload["files"] = {}
    payload["version"] = 1
    return payload


def save_reference_seed_manifest(target_root: Path, manifest: Mapping[str, Any]) -> None:
    path = reference_seed_manifest_path(target_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def should_update_reference_seed_file(
    relative: Path,
    source_path: Path,
    target_path: Path,
    manifest: Dict[str, Any],
) -> tuple[bool, bool]:
    if not is_reference_seed_path(relative):
        return False, False
    key = relative.as_posix()
    try:
        source_hash = file_sha256(source_path)
        target_hash = file_sha256(target_path)
    except OSError:
        return False, False

    files = manifest.setdefault("files", {})
    entry = files.get(key)
    if not isinstance(entry, dict):
        files[key] = {
            "sourceHash": source_hash,
            "targetHash": target_hash,
            "status": "seed" if source_hash == target_hash else "preserved_runtime_edit",
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
        }
        return False, True

    previous_source_hash = str(entry.get("sourceHash", "") or "")
    if target_hash == source_hash:
        changed = update_reference_seed_manifest_entry(
            files,
            key,
            source_hash=source_hash,
            target_hash=target_hash,
            status="seed",
        )
        return False, changed

    if previous_source_hash and target_hash == previous_source_hash and source_hash != previous_source_hash:
        return True, False

    changed = update_reference_seed_manifest_entry(
        files,
        key,
        source_hash=source_hash,
        target_hash=target_hash,
        status="preserved_runtime_edit",
    )
    return False, changed


def record_reference_seed_manifest(
    manifest: Dict[str, Any],
    relative: Path,
    source_path: Path,
    target_path: Path,
    *,
    copied: bool,
) -> bool:
    try:
        source_hash = file_sha256(source_path)
        target_hash = file_sha256(target_path)
    except OSError:
        return False
    files = manifest.setdefault("files", {})
    return update_reference_seed_manifest_entry(
        files,
        relative.as_posix(),
        source_hash=source_hash,
        target_hash=target_hash,
        status="copied" if copied else "seed",
    )


def update_reference_seed_manifest_entry(
    files: Dict[str, Any],
    key: str,
    *,
    source_hash: str,
    target_hash: str,
    status: str,
) -> bool:
    current = files.get(key)
    if (
        isinstance(current, Mapping)
        and current.get("sourceHash") == source_hash
        and current.get("targetHash") == target_hash
        and current.get("status") == status
    ):
        return False
    next_entry = {
        "sourceHash": source_hash,
        "targetHash": target_hash,
        "status": status,
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    if files.get(key) == next_entry:
        return False
    files[key] = next_entry
    return True


def output_file_content_security_policy(path: Path) -> str:
    if path.name.endswith("_전체업무흐름도_viewer.html"):
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self' data:"
        )
    return (
        "default-src 'self'; "
        "script-src 'none'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:"
    )


def sync_policy_seed_once(source_root: Path, target_root: Path) -> None:
    """One-time policy artifact sync for Render persistent output drift.

    Render keeps output files on a persistent disk. The generic seed copy avoids
    overwriting policy files so documents created in production are not lost.
    This migration is intentionally marker-gated: it aligns the current
    persisted policy artifacts to the repository seed once, then leaves future
    runtime edits alone.
    """

    marker_path = target_root / ".policy_seed_sync_20260517_trace_refresh_done.json"
    try:
        if source_root.resolve() == target_root.resolve():
            return
    except OSError:
        pass
    if marker_path.exists():
        return
    if not source_root.exists() or not source_root.is_dir():
        return
    target_root.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    for source_path in sorted(source_root.iterdir()):
        if not source_path.is_file() or not is_policy_seed_sync_file(source_path.name):
            continue
        target_path = target_root / source_path.name
        if target_path.exists():
            continue
        try:
            source_bytes = source_path.read_bytes()
            shutil.copy2(source_path, target_path)
            copied.append(source_path.name)
        except OSError:
            continue

    try:
        marker_path.write_text(
            json.dumps(
                {
                    "completedAt": datetime.now().isoformat(timespec="seconds"),
                    "copiedCount": len(copied),
                    "copied": copied,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return
    if copied:
        print(f"[seed] one-time policy sync copied {len(copied)} file(s)")


def is_policy_seed_sync_file(name: str) -> bool:
    normalized_name = unicodedata.normalize("NFC", str(name or ""))
    if re_match_policy_filename(normalized_name):
        return True
    if normalized_name.endswith("_spec.json"):
        html_name = normalized_name.removesuffix("_spec.json") + ".html"
        return re_match_policy_filename(html_name)
    if normalized_name.endswith("_전체업무흐름도.bpmn"):
        html_name = normalized_name.removesuffix("_전체업무흐름도.bpmn") + ".html"
        return re_match_policy_filename(html_name)
    if normalized_name.endswith("_전체업무흐름도_viewer.html"):
        html_name = normalized_name.removesuffix("_전체업무흐름도_viewer.html") + ".html"
        return re_match_policy_filename(html_name)
    return False


def migrate_runtime_bpmn_io_artifacts() -> Dict[str, Any]:
    """Rerender persisted policy files that predate the bpmn.io rollout.

    Render stores output files on a persistent disk, so files created only in the
    hosted runtime may not exist in the repository seed. This migration scans the
    active OUTPUT_ROOT itself and updates any policy HTML that lacks the embedded
    bpmn.io viewer or its sidecar BPMN artifacts.
    """

    summary: Dict[str, Any] = {"updated": [], "skipped": []}
    if not env_flag("NC_BPMN_IO_RUNTIME_MIGRATION_ENABLED", True):
        summary["disabled"] = True
        return summary
    if not OUTPUT_ROOT.exists() or not OUTPUT_ROOT.is_dir():
        return summary

    for html_path in sorted(OUTPUT_ROOT.glob("NC_*_정책서_*_v*.html")):
        if not html_path.is_file() or not re_match_policy_filename(html_path.name):
            continue
        bpmn_path = html_path.with_name(f"{html_path.stem}_전체업무흐름도.bpmn")
        viewer_path = bpmn_path.with_name(f"{bpmn_path.stem}_viewer.html")
        if policy_html_has_bpmn_io_viewer(html_path) and bpmn_path.exists() and viewer_path.exists():
            continue

        parsed = parse_policy_filename(html_path.name)
        topic_slug = str(parsed.get("topic", "") or "").strip()
        version = str(parsed.get("version", "") or "").strip()
        template_type = "full" if parsed.get("template_label") == "Full" else "simple"
        spec_path = policy_version_spec_path(html_path)
        spec = read_policy_spec_payload(spec_path) or read_policy_spec_payload(topic_policy_spec_path(topic_slug))
        if spec is None:
            summary["skipped"].append({"html": project_relative_path(html_path), "reason": "spec_missing"})
            continue
        try:
            prepared_spec = prepare_spec_for_bpmn_io_runtime_migration(dict(spec), topic_slug=topic_slug, version=version, template_type=template_type)
            template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
            template_html = template_path.read_text(encoding="utf-8")
            document = normalize_sentence_breaks(render_policy_html(prepared_spec, template_html, template_type, "full"))
            html_path.write_text(document, encoding="utf-8")
            spec_json = json.dumps(prepared_spec, ensure_ascii=False, indent=2)
            spec_path.write_text(spec_json, encoding="utf-8")
            topic_spec_path = topic_policy_spec_path(topic_slug)
            topic_spec = read_policy_spec_payload(topic_spec_path)
            if topic_spec is None or policy_spec_matches_version(topic_spec, version=version, template_type=template_type):
                topic_spec_path.write_text(spec_json, encoding="utf-8")
            artifacts = write_bpmn_artifacts(prepared_spec, bpmn_path)
            summary["updated"].append(
                {
                    "html": project_relative_path(html_path),
                    "spec": project_relative_path(spec_path),
                    "bpmn": project_relative_path(artifacts.bpmn),
                    "viewer": project_relative_path(artifacts.viewer),
                }
            )
        except Exception as exc:  # pragma: no cover - startup migration must not block service.
            summary["skipped"].append({"html": project_relative_path(html_path), "reason": str(exc)})
            continue

    if summary["updated"] or summary["skipped"]:
        write_runtime_bpmn_migration_report(summary)
    return summary


def policy_html_has_bpmn_io_viewer(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return (
        "bpmn-viewer.production.min.js" in text
        and 'data-bpmn-viewer="true"' in text
        and "bpmn-process-xml" in text
    )


def prepare_spec_for_bpmn_io_runtime_migration(
    spec: Dict[str, Any],
    *,
    topic_slug: str,
    version: str,
    template_type: str,
) -> Dict[str, Any]:
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["topic"] = topic_slug
        meta["topic_slug"] = topic_slug
        meta["version"] = version
        meta["template_type"] = template_type
        meta["document_type"] = "Full 버전" if template_type == "full" else "간소화 버전"
        meta["updated_at"] = datetime.now().date().isoformat()
    spec["version"] = version
    history = spec.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        spec["history"] = history
    if not any(isinstance(row, Mapping) and str(row.get("version", "")).strip() == version and str(row.get("change", "")).strip() == BPMN_IO_HISTORY_CHANGE for row in history):
        history.append(
            {
                "version": version,
                "change": BPMN_IO_HISTORY_CHANGE,
                "date": datetime.now().date().isoformat(),
                "author": "Codex",
            }
        )
    return spec


def policy_spec_matches_version(spec: Mapping[str, Any], *, version: str, template_type: str) -> bool:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    document_type = str(meta.get("document_type", "") if isinstance(meta, Mapping) else "")
    meta_template_type = str(meta.get("template_type", "") if isinstance(meta, Mapping) else "")
    return (
        str(meta.get("version", "") if isinstance(meta, Mapping) else "").strip() == version
        and (
            meta_template_type == template_type
            or ("Full" in document_type and template_type == "full")
            or ("간소화" in document_type and template_type == "simple")
        )
    )


def write_runtime_bpmn_migration_report(summary: Mapping[str, Any]) -> None:
    try:
        report_dir = REPORTS_DIR.parent if REPORTS_DIR.name == "inspections" else REPORTS_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "runtime_bpmn_io_migration_latest.json"
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            **dict(summary),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def apply_runtime_cleanup_manifests() -> None:
    """Delete persisted files listed by repository cleanup manifests.

    Render keeps output/reports on a persistent disk, so deleting generated
    artifacts from the repository alone does not remove stale server copies.
    Cleanup manifests are intentionally explicit and constrained to the runtime
    output/report roots to avoid broad or accidental deletion.
    """

    try:
        if OUTPUT_ROOT.resolve() == (PROJECT_ROOT / "output").resolve():
            return
    except OSError:
        pass

    manifest_root = PROJECT_ROOT / "reports"
    if not manifest_root.exists():
        return
    removed = 0
    manifest_patterns = (
        "module_34*_cleanup*.json",
        "source_knowledge*_cleanup*.json",
        "runtime_seed_refresh*_cleanup*.json",
    )
    for pattern in manifest_patterns:
        for manifest_path in sorted(manifest_root.glob(pattern)):
            for relative in cleanup_manifest_removed_paths(manifest_path):
                target = runtime_cleanup_target(relative)
                if not target or not target.exists():
                    continue
                try:
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                    removed += 1
                except OSError:
                    continue
    if removed:
        print(f"[cleanup] removed {removed} stale runtime artifact(s)")


def cleanup_manifest_removed_paths(manifest_path: Path) -> List[Path]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    removed = data.get("removed")
    if not isinstance(removed, list):
        return []
    paths: List[Path] = []
    for raw in removed:
        text = str(raw or "").strip()
        if not text:
            continue
        candidate = Path(text)
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        paths.append(candidate)
    return paths


def runtime_cleanup_target(relative: Path) -> Path | None:
    parts = relative.parts
    if len(parts) < 2:
        return None
    if is_protected_runtime_cleanup_path(relative):
        return None
    if parts[0] == "output":
        root = OUTPUT_ROOT
        rest = parts[1:]
    elif parts[0] == "reports":
        root = REPORTS_DIR.parent
        rest = parts[1:]
    else:
        return None
    try:
        target = safe_child_path(root, root.joinpath(*rest))
    except ValueError:
        return None
    if target.exists():
        return target
    return find_unicode_normalized_child(root, rest)


def is_protected_runtime_cleanup_path(relative: Path) -> bool:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts:
        return True
    if parts[0] == "reports" and len(parts) >= 2 and parts[1] == "auth":
        return True
    if parts[-1] in {"users.sqlite3", "users.sqlite", "users.db", "users.json"}:
        return True
    return False


def find_unicode_normalized_child(root: Path, parts: tuple[str, ...]) -> Path | None:
    """Resolve persisted files whose Hangul filename normalization differs.

    macOS-created cleanup manifests can contain a different Unicode
    normalization form than files generated on Render's Linux filesystem. Keep
    the cleanup manifest explicit, but allow NFC-equivalent path components to
    match so stale Korean-named artifacts do not survive a deploy.
    """

    current = root
    for part in parts:
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue
        if not current.exists() or not current.is_dir():
            return None
        target_name = unicodedata.normalize("NFC", part)
        matched: Path | None = None
        try:
            for child in current.iterdir():
                if unicodedata.normalize("NFC", child.name) == target_name:
                    matched = child
                    break
        except OSError:
            return None
        if matched is None:
            return None
        current = matched
    try:
        return safe_child_path(root, current)
    except ValueError:
        return None


def empty_agent_usage_row(agent_name: str) -> Dict[str, Any]:
    return {
        "agent": agent_name,
        "calls": 0,
        "inputTokens": 0,
        "outputTokens": 0,
        "reasoningTokens": 0,
        "totalTokens": 0,
        "cachedInputTokens": 0,
        "estimatedCostUsd": 0.0,
        "unpricedCalls": 0,
        "models": {},
        "_lastUpdated": "",
    }


def accumulate_agent_usage(
    row: Dict[str, Any],
    usage: Mapping[str, Any],
    event: Mapping[str, Any],
    pricing: Mapping[str, Mapping[str, float]],
) -> None:
    row["calls"] = int(row.get("calls", 0)) + 1
    row["inputTokens"] = int(row.get("inputTokens", 0)) + safe_int(usage.get("input_tokens"))
    row["outputTokens"] = int(row.get("outputTokens", 0)) + safe_int(usage.get("output_tokens"))
    row["totalTokens"] = int(row.get("totalTokens", 0)) + safe_int(usage.get("total_tokens"))
    input_details = usage.get("input_tokens_details")
    cached_input_tokens = 0
    if isinstance(input_details, dict):
        cached_input_tokens = safe_int(input_details.get("cached_tokens"))
    row["cachedInputTokens"] = int(row.get("cachedInputTokens", 0)) + cached_input_tokens
    reasoning_tokens = usage.get("reasoning_tokens")
    if reasoning_tokens is None:
        output_details = usage.get("output_tokens_details")
        if isinstance(output_details, dict):
            reasoning_tokens = output_details.get("reasoning_tokens")
    row["reasoningTokens"] = int(row.get("reasoningTokens", 0)) + safe_int(reasoning_tokens)
    model = str(event.get("model", "")).strip() or "-"
    models = row.setdefault("models", {})
    models[model] = int(models.get(model, 0)) + 1
    estimated_cost = estimate_llm_cost_usd(usage, model, pricing)
    if estimated_cost is None:
        row["unpricedCalls"] = int(row.get("unpricedCalls", 0)) + 1
    else:
        row["estimatedCostUsd"] = float(row.get("estimatedCostUsd", 0.0)) + estimated_cost
    timestamp = str(event.get("timestamp", "")).strip()
    if timestamp and timestamp > str(row.get("_lastUpdated", "")):
        row["_lastUpdated"] = timestamp


def load_model_pricing() -> Dict[str, Dict[str, float]]:
    pricing = {model: dict(rates) for model, rates in DEFAULT_MODEL_PRICING_USD_PER_1M.items()}
    override = os.getenv("OPENAI_MODEL_PRICING_JSON", "").strip()
    if not override:
        return pricing
    try:
        parsed = json.loads(override)
    except json.JSONDecodeError:
        return pricing
    if not isinstance(parsed, dict):
        return pricing
    for model, rates in parsed.items():
        if not isinstance(rates, dict):
            continue
        normalized = normalize_model_name(str(model))
        base = pricing.setdefault(normalized, {})
        for key in ("input", "cached_input", "output"):
            value = parse_float(rates.get(key))
            if value is not None:
                base[key] = value
    return pricing


def estimate_llm_cost_usd(
    usage: Mapping[str, Any],
    model: str,
    pricing: Mapping[str, Mapping[str, float]],
) -> Optional[float]:
    rates = model_pricing_rates(model, pricing)
    if not rates:
        return None
    input_tokens = safe_int(usage.get("input_tokens"))
    output_tokens = safe_int(usage.get("output_tokens"))
    input_details = usage.get("input_tokens_details")
    cached_tokens = safe_int(input_details.get("cached_tokens")) if isinstance(input_details, dict) else 0
    cached_tokens = max(0, min(cached_tokens, input_tokens))
    regular_input_tokens = max(0, input_tokens - cached_tokens)
    input_rate = float(rates.get("input", 0.0))
    cached_input_rate = float(rates.get("cached_input", input_rate))
    output_rate = float(rates.get("output", 0.0))
    return (
        (regular_input_tokens * input_rate)
        + (cached_tokens * cached_input_rate)
        + (output_tokens * output_rate)
    ) / 1_000_000


def model_pricing_rates(model: str, pricing: Mapping[str, Mapping[str, float]]) -> Optional[Mapping[str, float]]:
    normalized = normalize_model_name(model)
    if normalized in pricing:
        return pricing[normalized]
    candidates = sorted(pricing.keys(), key=len, reverse=True)
    for candidate in candidates:
        if normalized.startswith(f"{candidate}-") or normalized.startswith(f"{candidate}."):
            return pricing[candidate]
    return None


def normalize_model_name(model: str) -> str:
    return re.sub(r"\s+", "", str(model or "").strip().casefold())


def parse_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def schema_agent_label(schema_name: str) -> str:
    if schema_name in SCHEMA_AGENT_LABELS:
        return SCHEMA_AGENT_LABELS[schema_name]
    normalized = re.sub(r"_(chunk|patch)$", "", schema_name)
    if normalized in SCHEMA_AGENT_LABELS:
        return SCHEMA_AGENT_LABELS[normalized]
    return "기타"


def safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


POLICY_LIFECYCLE_LABELS = {
    "in_progress": "작성 중",
    "completed": "작성 완료",
}


def policy_lifecycle_dir() -> Path:
    return OUTPUT_ROOT / "status"


def policy_lifecycle_path(policy_path: Path) -> Path:
    return policy_lifecycle_dir() / f"{policy_path.stem}_status.json"


def default_policy_lifecycle(policy_path: Path) -> Dict[str, Any]:
    modified = ""
    try:
        modified = datetime.fromtimestamp(policy_path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        modified = datetime.now().isoformat(timespec="seconds")
    return {
        "status": "in_progress",
        "label": POLICY_LIFECYCLE_LABELS["in_progress"],
        "updatedAt": modified,
        "updatedBy": "",
        "history": [],
    }


def load_policy_lifecycle(policy_path: Path) -> Dict[str, Any]:
    lifecycle = default_policy_lifecycle(policy_path)
    path = policy_lifecycle_path(policy_path)
    if not path.exists() or not path.is_file():
        return lifecycle
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return lifecycle
    if not isinstance(payload, dict):
        return lifecycle
    status = str(payload.get("status", "")).strip()
    if status not in POLICY_LIFECYCLE_LABELS:
        status = "in_progress"
    lifecycle.update(
        {
            "status": status,
            "label": POLICY_LIFECYCLE_LABELS[status],
            "updatedAt": str(payload.get("updatedAt", "")).strip() or lifecycle["updatedAt"],
            "updatedBy": str(payload.get("updatedBy", "")).strip(),
            "history": payload.get("history", []) if isinstance(payload.get("history"), list) else [],
        }
    )
    return lifecycle


def update_policy_lifecycle_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    requested_status = str(payload.get("status", "")).strip()
    author = str(payload.get("author", "")).strip() or "Policy Web"
    if not name:
        raise ValueError("상태를 변경할 정책서를 선택해 주세요.")
    if requested_status not in POLICY_LIFECYCLE_LABELS:
        raise ValueError("정책서 상태 값이 올바르지 않습니다.")
    policy_path = policy_file_path(name)
    if not policy_path.exists() or not policy_path.is_file():
        raise ValueError("상태를 변경할 정책서 파일을 찾을 수 없습니다.")
    ensure_document_not_locked(policy_path.name)

    previous = load_policy_lifecycle(policy_path)
    now = datetime.now().isoformat(timespec="seconds")
    history = list(previous.get("history", []))
    if previous.get("status") != requested_status:
        history.append(
            {
                "from": previous.get("status", "in_progress"),
                "to": requested_status,
                "fromLabel": previous.get("label", POLICY_LIFECYCLE_LABELS["in_progress"]),
                "toLabel": POLICY_LIFECYCLE_LABELS[requested_status],
                "changedAt": now,
                "changedBy": author,
            }
        )

    path = policy_lifecycle_path(policy_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": policy_path.name,
                "topic": parse_policy_filename(policy_path.name)["topic"],
                "status": requested_status,
                "label": POLICY_LIFECYCLE_LABELS[requested_status],
                "updatedAt": now,
                "updatedBy": author,
                "history": history,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return describe_policy_file(policy_path)


def ensure_policy_editable(policy_path: Path) -> None:
    lifecycle = load_policy_lifecycle(policy_path)
    if lifecycle.get("status") == "completed":
        raise ValueError("작성 완료 상태에서는 '작성 완료 취소' 후에만 수정할 수 있습니다.")


def delete_policy_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    draft_resume_from = str(payload.get("draftResumeFrom", "") or payload.get("resumeFrom", "")).strip()
    if draft_resume_from:
        return delete_draft_from_payload(payload)

    name = str(payload.get("name", "")).strip()
    session_id = client_session_id_from_payload(payload)
    if not name:
        raise ValueError("삭제할 정책서를 선택해 주세요.")
    if "/" in name or "\\" in name:
        raise ValueError("삭제할 정책서 파일명이 올바르지 않습니다.")
    if not is_policy_output_name(name):
        raise ValueError("생성 결과 정책서만 삭제할 수 있습니다.")

    policy_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / name)
    if not policy_path.exists() or not policy_path.is_file():
        raise ValueError("삭제할 정책서 파일을 찾을 수 없습니다.")
    ensure_policy_editable(policy_path)
    lock_info = acquire_document_job_lock(policy_path.name, job_id=uuid.uuid4().hex, operation="delete", session_id=session_id)
    try:
        if not policy_path.exists() or not policy_path.is_file():
            raise ValueError("삭제할 정책서 파일을 찾을 수 없습니다.")
        stem = policy_path.stem
        parsed = parse_policy_filename(policy_path.name)
        template_type = "full" if parsed["template_label"] == "Full" else "simple"
        comments_storage_path = policy_comments_storage_path_for_name(name)
        deleted_files = [delete_file(policy_path)]
        deleted_files.extend(delete_file_if_exists(policy_version_spec_path(policy_path)))
        deleted_files.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*.bpmn"))
        deleted_files.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*_viewer.html"))
        deleted_files.extend(delete_file_if_exists(policy_lifecycle_path(policy_path)))
        deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "steps", f"{stem}_*.html"))
        deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "checkpoints", f"{stem}_*.json"))
        deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "quality", f"{stem}_quality_report.json"))
        deleted_files.extend(delete_matching_files(REPORTS_DIR, f"{name}_*_inspection.json"))
        deleted_files.extend(delete_matching_files(REPORTS_DIR, f"{stem}.html_*_inspection.json"))
        deleted_files.extend(delete_file_if_exists(REPORTS_DIR / f"{name}_health_check.json"))
        if not latest_policy_for_topic(parsed["topic"], template_type) and not remaining_drafts_for_topic(parsed["topic"], template_type):
            deleted_files.extend(delete_file_if_exists(comments_storage_path))
            for legacy_comment_path, _payload in legacy_policy_comment_payloads_for_topic(parsed["topic"]):
                deleted_files.extend(delete_file_if_exists(legacy_comment_path))
            for auxiliary_name in (f"{parsed['topic']}_policy_spec.json", f"{parsed['topic']}_authoring_blueprint.json"):
                deleted_files.extend(delete_file_if_exists(safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / auxiliary_name)))
            deleted_files.extend(delete_inactive_policy_job_lock(parsed["topic"], template_type))
        else:
            refresh_topic_policy_spec_from_latest_version(parsed["topic"], template_type)
        update_document_lock(lock_info, "completed")
        return {
            "name": name,
            "deletedFiles": sorted({project_relative_path(path) for path in deleted_files}),
        }
    except Exception:
        update_document_lock(lock_info, "failed")
        raise


def delete_draft_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_resume_from = str(payload.get("draftResumeFrom", "") or payload.get("resumeFrom", "")).strip()
    if not raw_resume_from:
        raise ValueError("삭제할 초안을 선택해 주세요.")
    checkpoint_path = safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / raw_resume_from)
    try:
        checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("삭제할 초안 체크포인트를 읽을 수 없습니다.") from exc
    checkpoint = checkpoint_payload.get("checkpoint", {}) if isinstance(checkpoint_payload, dict) else {}
    if not isinstance(checkpoint, dict):
        raise ValueError("초안 체크포인트 형식이 올바르지 않습니다.")

    topic = str(checkpoint.get("topic", "")).strip()
    topic_slug = str(checkpoint.get("topic_slug", "")).strip() or make_topic_slug(topic)
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    version = str(checkpoint.get("version", "")).strip()
    if not topic or not topic_slug or not version:
        raise ValueError("초안 식별 정보가 부족합니다.")

    label = template_file_label(template_type)
    stem = f"NC_{topic_slug}_정책서_{label}_{version}"
    deleted_files: List[Path] = []
    deleted_files.extend(delete_file_if_exists(checkpoint_path))
    deleted_files.extend(delete_file_if_exists(OUTPUT_ROOT / f"{stem}_spec.json"))
    deleted_files.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*.bpmn"))
    deleted_files.extend(delete_matching_files(OUTPUT_ROOT, f"{stem}_*_viewer.html"))
    deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "steps", f"{stem}_*.html"))
    deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "checkpoints", f"{stem}_*.json"))
    deleted_files.extend(delete_matching_files(OUTPUT_ROOT / "quality", f"{stem}_quality_report.json"))
    deleted_files.extend(delete_matching_files(REPORTS_DIR, f"{stem}.html_*_inspection.json"))

    if not latest_policy_for_topic(topic, template_type) and not remaining_drafts_for_topic(topic, template_type):
        for name in (f"{topic_slug}_policy_spec.json", f"{topic_slug}_authoring_blueprint.json"):
            deleted_files.extend(delete_file_if_exists(safe_child_path(OUTPUT_ROOT, OUTPUT_ROOT / name)))
        deleted_files.extend(delete_inactive_policy_job_lock(topic, template_type))
    else:
        refresh_topic_policy_spec_from_latest_version(topic, template_type)

    return {
        "name": f"{topic} 초안",
        "topic": topic,
        "deletedFiles": sorted({project_relative_path(path) for path in deleted_files}),
    }


def remaining_drafts_for_topic(topic: str, template_type: str) -> List[Dict[str, Any]]:
    topic_key = normalize_topic_key(topic)
    template = str(template_type or "simple").strip() or "simple"
    return [
        draft
        for draft in list_resumable_drafts()
        if normalize_topic_key(draft.get("topic", "")) == topic_key and draft.get("templateType") == template
    ]


def delete_file(path: Path) -> Path:
    path.unlink()
    return path


def delete_inactive_policy_job_lock(topic: str, template_type: str) -> List[Path]:
    if not LOCK_DIR.exists():
        return []
    path = safe_child_path(LOCK_DIR, LOCK_DIR / f"{job_lock_key(topic, template_type)}.lock")
    data = read_policy_job_lock(path)
    if active_lock(data):
        return []
    return delete_file_if_exists(path)


def delete_matching_files(root: Path, pattern: str) -> List[Path]:
    if not root.exists():
        return []
    deleted: List[Path] = []
    for path in sorted(root.glob(pattern)):
        safe_path = safe_child_path(root, path)
        if safe_path.is_file():
            deleted.append(delete_file(safe_path))
    return deleted


def is_policy_output_name(name: str) -> bool:
    return re_match_policy_filename(name)


def list_policy_files() -> List[Dict[str, Any]]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    restore_completed_policies_from_checkpoints()
    files = [
        path
        for path in OUTPUT_ROOT.iterdir()
        if path.is_file() and path.parent == OUTPUT_ROOT and re_match_policy_filename(path.name)
    ]
    return [describe_policy_file(path) for path in sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)]


def start_client_heartbeat_watchdog() -> None:
    global JOB_WATCHDOG_STARTED
    with JOB_WATCHDOG_LOCK:
        if JOB_WATCHDOG_STARTED:
            return
        JOB_WATCHDOG_STARTED = True
    thread = threading.Thread(target=client_heartbeat_watchdog_loop, daemon=True)
    thread.start()


def client_heartbeat_watchdog_loop() -> None:
    interval = max(5, CLIENT_HEARTBEAT_CHECK_SECONDS)
    while True:
        time.sleep(interval)
        now = current_time()
        with JOBS_CONDITION:
            stale_jobs = [
                job
                for job in JOBS.values()
                if isinstance(job, dict) and client_heartbeat_stale(job, now)
            ]
            for job in stale_jobs:
                mark_job_client_disconnected(job)
            if stale_jobs:
                JOBS_CONDITION.notify_all()


def list_resumable_drafts() -> List[Dict[str, Any]]:
    checkpoints_dir = OUTPUT_ROOT / "checkpoints"
    if not checkpoints_dir.exists():
        return []
    drafts: Dict[tuple[str, str], Dict[str, Any]] = {}
    for path in checkpoints_dir.glob("NC_*_정책서_*_v*_latest_checkpoint.json"):
        if not path.is_file():
            continue
        draft = describe_checkpoint_draft(path)
        if not draft:
            continue
        key = (normalize_topic_key(draft["topic"]), draft["templateType"])
        previous = drafts.get(key)
        if not previous or str(draft.get("savedAt", "")) > str(previous.get("savedAt", "")):
            drafts[key] = draft
    return sorted(drafts.values(), key=lambda item: item.get("savedAt", ""), reverse=True)


def describe_checkpoint_draft(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    checkpoint = payload.get("checkpoint", {})
    if not isinstance(checkpoint, dict):
        return None
    topic = str(checkpoint.get("topic", "")).strip()
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    version = str(checkpoint.get("version", "") or "-").strip()
    spec = payload.get("spec", {})
    if is_completed_generation_checkpoint(checkpoint):
        restore_completed_policy_from_checkpoint_payload(
            checkpoint,
            spec if isinstance(spec, Mapping) else {},
        )
        return None
    if not topic or latest_policy_for_topic(topic, template_type):
        return None
    preview = latest_draft_preview_artifact(checkpoint, spec if isinstance(spec, dict) else None)
    stat = path.stat()
    return {
        "id": path.stem,
        "topic": topic,
        "topicSlug": str(checkpoint.get("topic_slug", "")).strip() or make_topic_slug(topic),
        "templateType": template_type,
        "templateLabel": template_file_label(template_type),
        "inspectionMode": str(checkpoint.get("inspection_mode", "") or "chapter-final").strip() or "chapter-final",
        "writerMode": str(checkpoint.get("writer_mode", "") or "mock").strip() or "mock",
        "version": version,
        "stageKey": str(checkpoint.get("stage_key", "")).strip(),
        "stageName": str(checkpoint.get("stage_name", "")).strip(),
        "stageLabel": str(checkpoint.get("stage_label", "")).strip() or "작성 단계",
        "attempt": checkpoint.get("attempt"),
        "summary": str(checkpoint.get("summary", "")).strip(),
        "savedAt": str(checkpoint.get("saved_at", "")).strip() or datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "checkpoint": output_artifact_payload(path),
        "preview": preview,
        "resumeFrom": str(path.relative_to(OUTPUT_ROOT)),
        "status": "draft",
    }


def restore_completed_policies_from_checkpoints() -> List[Path]:
    checkpoints_dir = OUTPUT_ROOT / "checkpoints"
    if not checkpoints_dir.exists():
        return []
    restored: List[Path] = []
    for path in checkpoints_dir.glob("NC_*_정책서_*_v*_latest_checkpoint.json"):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        checkpoint = payload.get("checkpoint", {})
        spec = payload.get("spec", {})
        if not isinstance(checkpoint, Mapping) or not isinstance(spec, Mapping):
            continue
        restored_path = restore_completed_policy_from_checkpoint_payload(checkpoint, spec)
        if restored_path:
            restored.append(restored_path)
    return restored


def is_completed_generation_checkpoint(checkpoint: Mapping[str, Any]) -> bool:
    if not isinstance(checkpoint, Mapping):
        return False
    passed = checkpoint.get("passed")
    if isinstance(passed, str):
        passed = passed.strip().casefold() in {"1", "true", "yes", "y", "pass", "passed"}
    if passed is not True:
        return False
    stage_name = str(checkpoint.get("stage_name", "")).strip().casefold()
    stage_label = str(checkpoint.get("stage_label", "")).strip().casefold()
    return stage_name == "final_check" or "final check" in stage_label or "최종" in stage_label


def restore_completed_policy_from_checkpoint_payload(
    checkpoint: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> Optional[Path]:
    if not is_completed_generation_checkpoint(checkpoint) or not isinstance(spec, Mapping):
        return None
    topic = str(checkpoint.get("topic", "")).strip()
    topic_slug = str(checkpoint.get("topic_slug", "")).strip() or make_topic_slug(topic)
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    version = str(checkpoint.get("version", "")).strip()
    if not topic_slug or not version:
        return None
    label = template_file_label(template_type)
    target_path = OUTPUT_ROOT / f"NC_{topic_slug}_정책서_{label}_{version}.html"
    if target_path.exists() and target_path.is_file():
        return None
    try:
        template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
        template_html = template_path.read_text(encoding="utf-8")
        document = render_policy_html(dict(spec), template_html, template_type)
        document = normalize_sentence_breaks(document)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(document, encoding="utf-8")
        restored_spec = dict(spec)
        meta = restored_spec.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["topic"] = topic or meta.get("topic", "")
            meta["topic_slug"] = topic_slug
            meta["template_type"] = template_type
            meta["version"] = version
            meta["version_spec_file"] = policy_version_spec_path(target_path).name
            meta["version_spec_saved_at"] = datetime.now().isoformat(timespec="seconds")
            meta["version_spec_reason"] = "checkpoint_restore"
        spec_json = json.dumps(restored_spec, ensure_ascii=False, indent=2)
        policy_version_spec_path(target_path).write_text(spec_json, encoding="utf-8")
        topic_policy_spec_path(topic_slug).write_text(spec_json, encoding="utf-8")
        return target_path
    except Exception:
        return None


def latest_draft_preview_artifact(checkpoint: Mapping[str, Any], spec: Optional[Mapping[str, Any]] = None) -> Optional[Dict[str, str]]:
    topic_slug = str(checkpoint.get("topic_slug", "")).strip()
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    version = str(checkpoint.get("version", "")).strip()
    if not topic_slug or not version:
        return None
    label = template_file_label(template_type)
    steps_dir = OUTPUT_ROOT / "steps"
    stage_key = str(checkpoint.get("stage_key", "")).strip()
    stage_name = str(checkpoint.get("stage_name", "")).strip()
    candidates: List[Path] = []
    exact_exists = False
    if steps_dir.exists() and stage_key and stage_name:
        exact = steps_dir / f"NC_{topic_slug}_정책서_{label}_{version}_{stage_key}_{stage_name}.html"
        if exact.exists() and exact.is_file():
            candidates.append(exact)
            exact_exists = True
    if not exact_exists and spec:
        restored = restore_draft_preview_from_checkpoint(checkpoint, spec)
        if restored:
            return restored
    if steps_dir.exists():
        candidates.extend(
            path
            for path in steps_dir.glob(f"NC_{topic_slug}_정책서_{label}_{version}_*.html")
            if path.is_file()
        )
    if not candidates:
        return None
    return output_artifact_payload(max(candidates, key=lambda item: item.stat().st_mtime))


def restore_draft_preview_from_checkpoint(
    checkpoint: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> Optional[Dict[str, str]]:
    topic = str(checkpoint.get("topic", "")).strip()
    topic_slug = str(checkpoint.get("topic_slug", "")).strip() or make_topic_slug(topic)
    template_type = str(checkpoint.get("template_type", "") or "simple").strip() or "simple"
    version = str(checkpoint.get("version", "")).strip()
    stage_key = str(checkpoint.get("stage_key", "")).strip()
    stage_name = str(checkpoint.get("stage_name", "")).strip()
    if not topic_slug or not version or not stage_key or not stage_name:
        return None
    try:
        template_path = choose_template(PROJECT_ROOT / "input" / "templates", template_type)
        template_html = template_path.read_text(encoding="utf-8")
        document = render_policy_html(dict(spec), template_html, template_type, stage_key)
        document = normalize_sentence_breaks(document)
        steps_dir = OUTPUT_ROOT / "steps"
        steps_dir.mkdir(parents=True, exist_ok=True)
        label = template_file_label(template_type)
        path = steps_dir / f"NC_{topic_slug}_정책서_{label}_{version}_{stage_key}_{stage_name}.html"
        path.write_text(document, encoding="utf-8")
        return output_artifact_payload(path)
    except Exception:
        return None


def normalize_topic_key(value: str) -> str:
    return re.sub(r"[\s/_·.-]+", "", str(value or "")).casefold()


def describe_policy_file(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    parsed = parse_policy_filename(path.name)
    lifecycle = load_policy_lifecycle(path)
    spec_path = policy_version_spec_path(path)
    if not spec_path.exists():
        sync_policy_version_spec_from_base(
            path,
            path,
            author="system",
            reason="json_download_backfill",
        )
    spec_artifact = output_artifact_payload(spec_path) if spec_path.exists() and spec_path.is_file() else None
    try:
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        content_hash = ""
    return {
        "name": path.name,
        "topic": parsed["topic"],
        "templateLabel": parsed["template_label"],
        "templateType": "full" if parsed["template_label"] == "Full" else "simple",
        "version": parsed["version"],
        "url": f"/output/{quote(path.name)}",
        "json": spec_artifact,
        "size": stat.st_size,
        "contentHash": content_hash,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "inspection": load_latest_inspection_report(path.name),
        "quality": load_quality_report(path.name),
        "devQaReview": load_dev_qa_review_report(path.name),
        "healthCheck": load_health_check_report(path.name),
        "specSync": html_spec_sync_status_for_policy(path),
        "lifecycle": lifecycle,
        "documentStatus": lifecycle["label"],
    }


def load_latest_inspection_report(file_name: str) -> Optional[Dict[str, Any]]:
    if not REPORTS_DIR.exists():
        return None

    candidates = [
        REPORTS_DIR / f"{file_name}_web_inspection.json",
        REPORTS_DIR / f"{file_name}_full_inspection.json",
        REPORTS_DIR / f"{file_name}_final_inspection.json",
    ]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None

    latest = max(existing, key=lambda path: path.stat().st_mtime)
    try:
        return json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_quality_report(file_name: str) -> Optional[Dict[str, Any]]:
    path = OUTPUT_ROOT / "quality" / f"{Path(file_name).stem}_quality_report.json"
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_dev_qa_review_report(file_name: str) -> Optional[Dict[str, Any]]:
    path = REPORTS_DIR / f"{file_name}_dev_qa_review.json"
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_health_check_report(file_name: str) -> Optional[Dict[str, Any]]:
    path = REPORTS_DIR / f"{file_name}_health_check.json"
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_policy_filename(name: str) -> Dict[str, str]:
    normalized_name = unicodedata.normalize("NFC", str(name or ""))
    match = POLICY_HTML_FILENAME_RE.match(normalized_name)
    if match:
        return match.groupdict()

    marker = "_정책서_"
    stem = normalized_name.removesuffix(".html")
    if not stem.startswith("NC_") or marker not in stem:
        return {"topic": "-", "template_label": "-", "version": "-"}

    topic_part, rest = stem.removeprefix("NC_").split(marker, 1)
    if "_v" not in rest:
        return {"topic": topic_part, "template_label": rest, "version": "-"}

    template_label, version = rest.rsplit("_", 1)
    return {
        "topic": topic_part,
        "template_label": template_label,
        "version": version,
    }


def load_policy_density_profile(policy_path: Path) -> dict | None:
    parsed = parse_policy_filename(policy_path.name)
    topic_slug = str(parsed.get("topic", "") or "").strip()
    if not topic_slug or topic_slug == "-":
        return None
    spec = read_policy_spec_payload(policy_version_spec_path(policy_path)) or read_policy_spec_payload(topic_policy_spec_path(topic_slug))
    if spec is None:
        return None
    profile = spec.get("density_profile") if isinstance(spec, Mapping) else None
    if not isinstance(profile, Mapping):
        meta = spec.get("meta", {}) if isinstance(spec, Mapping) else {}
        profile = meta.get("density_profile") if isinstance(meta, Mapping) else None
    return dict(profile) if isinstance(profile, Mapping) else None


def re_match_policy_filename(name: str) -> bool:
    normalized_name = unicodedata.normalize("NFC", str(name or ""))
    return bool(POLICY_HTML_FILENAME_RE.match(normalized_name))


def safe_child_path(root: Path, requested: Path) -> Path:
    root_resolved = root.resolve()
    requested_resolved = requested.resolve()
    requested_resolved.relative_to(root_resolved)
    return requested_resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NC 정책서 작성 요청 웹사이트")
    parser.add_argument("--host", default="127.0.0.1", help="서버 호스트")
    parser.add_argument("--port", default=8000, type=int, help="서버 포트")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bootstrap_runtime_data()
    start_client_heartbeat_watchdog()
    server = ThreadingHTTPServer((args.host, args.port), PolicyWebHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"NC 정책서 작성 웹사이트가 실행 중입니다: {url}")
    print("종료하려면 Ctrl+C를 누르세요.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
