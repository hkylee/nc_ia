"""Requirement workbook reader and matcher for NC policy documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Sequence
from xml.etree import ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS_DIR = PROJECT_ROOT / "input" / "requirements"
try:
    from runtime_paths import REQUIREMENTS_DB_PATH
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import REQUIREMENTS_DB_PATH

DEFAULT_REQUIREMENTS_DB_PATH = REQUIREMENTS_DB_PATH
REQUIREMENTS_DB_SCHEMA_VERSION = 4
REQUIREMENT_SHEET_NAME = "요구사항 통합 list"
POLICY_MODULE_MAPPING_SHEET_NAME = "모듈 맵핑표"
POLICY_MODULE_COLUMN_NAME = "정책서 모듈"
POLICY_MODULE_ID_COLUMN_NAME = "정책서 모듈 ID"
POLICY_MODULE_INCLUDE_COLUMN_NAME = "정책서 포함 여부"
POLICY_MODULE_SHARED_REASON_COLUMN_NAME = "정책서 공유/중복 사유"
POLICY_MODULE_STATUS_COLUMN_NAME = "정책서 전환 상태"
STRICT_TOPIC_DEPTH4_ALIASES: dict[str, tuple[str, ...]] = {
    # This service topic intentionally combines three workbook Depth 4 buckets.
    "가이드라인/ 공통/ 품질/ 적응형": ("가이드라인", "공통", "품질/적응형"),
    # UI labels may use a centered dot while the workbook uses a slash.
    "회원가입 · 회원탈퇴": ("회원 가입/탈퇴",),
}
MAPPING_DEPTH4_CELL_ALIASES: dict[str, tuple[str, ...]] = {
    # The mapping workbook writes this without the workbook's word spacing.
    "t플러스포인트": ("T 플러스 포인트",),
    "상품상세": ("상품 상세",),
}
EXCEL_ERROR_VALUES = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!"}


@dataclass(frozen=True)
class RequirementItem:
    source_number: str
    depth3: str
    depth4: str
    requirement_id: str
    parent_name: str
    parent_description: str
    detail_name: str
    detail_description: str
    requirement_type: str
    priority: str
    required: str
    source: str
    owner_team: str
    owner: str
    edit_status: str
    review_status: str
    policy_module: str = ""
    policy_module_id: str = ""
    policy_include: str = ""
    policy_shared_reason: str = ""
    policy_mapping_status: str = ""
    detail_id: str = ""


def load_requirements_for_topic(
    topic: str,
    requirements_dir: Path | str = DEFAULT_REQUIREMENTS_DIR,
    *,
    match_mode: str = "broad",
) -> List[RequirementItem]:
    """Load requirement rows for a topic.

    ``match_mode="strict"`` is the authoring-safe mode: only the current
    policy topic's Depth 4 bucket, plus explicitly registered aliases, is
    treated as mandatory first-priority scope. ``"broad"`` preserves the older
    tolerant matcher for exploratory search and legacy tooling.
    """
    root = Path(requirements_dir)
    if requirements_database_enabled():
        try:
            items = load_requirements_for_topic_from_database(topic, root, match_mode=match_mode)
            if items:
                return items
        except Exception:
            # Keep authoring resilient: fall back to direct workbook parsing.
            pass

    workbook_path = find_requirements_workbook(root)
    if not workbook_path:
        return []

    rows = read_xlsx_sheet(workbook_path, REQUIREMENT_SHEET_NAME)
    if not rows:
        return []

    headers = [header_key(value) for value in rows[0]]
    indexes = requirement_column_indexes(headers)

    items: List[RequirementItem] = []
    matcher = matches_policy_topic_strict if match_mode in {"strict", "scoped", "exact"} else matches_policy_topic
    for row_number, row in enumerate(rows[1:], start=2):
        depth4 = cell_text(row, indexes["depth4"])
        policy_module = cell_text(row, indexes["policy_module"])
        if not row_matches_policy_topic(
            depth4,
            policy_module,
            topic,
            matcher,
            match_mode,
            has_policy_module_column=indexes["policy_module"] >= 0,
        ):
            continue

        edit_status = cell_text(row, indexes["edit_status"])
        if edit_status == "삭제":
            continue

        detail_description = cell_text(row, indexes["detail_description"])
        detail_name = effective_detail_name(
            cell_text(row, indexes["detail_name"]),
            detail_description,
            parent_name=cell_text(row, indexes["parent_name"]),
            requirement_id=cell_text(row, indexes["requirement_id"]),
        )
        if not detail_name and not detail_description:
            continue

        items.append(
            RequirementItem(
                source_number=cell_text(row, indexes["number"]) or f"ROW{row_number}",
                depth3=cell_text(row, indexes["depth3"]),
                depth4=strip_depth_number(depth4),
                requirement_id=cell_text(row, indexes["requirement_id"]),
                parent_name=cell_text(row, indexes["parent_name"]),
                parent_description=cell_text(row, indexes["parent_description"]),
                detail_name=detail_name,
                detail_description=detail_description,
                requirement_type=cell_text(row, indexes["requirement_type"]),
                priority=cell_text(row, indexes["priority"]),
                required=cell_text(row, indexes["required"]),
                source=cell_text(row, indexes["source"]),
                owner_team=cell_text(row, indexes["owner_team"]),
                owner=cell_text(row, indexes["owner"]),
                edit_status=edit_status,
                review_status=cell_text(row, indexes["review_status"]),
                policy_module=policy_module,
                policy_module_id=cell_text(row, indexes["policy_module_id"]),
                policy_include=cell_text(row, indexes["policy_include"]),
                policy_shared_reason=cell_text(row, indexes["policy_shared_reason"]),
                policy_mapping_status=cell_text(row, indexes["policy_mapping_status"]),
                detail_id=cell_text(row, indexes["detail_id"]),
            )
        )

    return sorted(items, key=requirement_sort_key)


def effective_detail_name(
    detail_name: str,
    detail_description: str,
    *,
    parent_name: str = "",
    requirement_id: str = "",
) -> str:
    """Return a usable detail requirement name without mutating the source.

    Some source rows intentionally carry only a detailed description. The
    writing agents still need a stable short name for Topic Knowledge,
    must-cover lists, and trace reports, so derive one from the first sentence
    while preserving the original description in ``detail_description``.
    """

    current = clean_text(detail_name)
    if current:
        return current

    description = clean_text(detail_description)
    if description:
        first_sentence = re.split(r"(?<=[.!?。])\s+|[.!?。]", description, maxsplit=1)[0]
        candidate = re.sub(
            r"^(고객|운영자|관리자|상담사|시스템|BSS|연계 시스템)(은|는|이|가|에게|에서)?\s*",
            "",
            clean_text(first_sentence),
        )
        candidate = re.sub(
            r"\s*(할 수 있어야 한다|할 수 있어야 한다|수 있어야 한다|되어야 한다|해야 한다|한다)$",
            "",
            candidate,
        ).strip(" ,.;")
        if candidate:
            return truncate_detail_name(candidate)

    fallback = clean_text(parent_name) or clean_text(requirement_id)
    return truncate_detail_name(fallback) if fallback else ""


def truncate_detail_name(value: str, *, limit: int = 42) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def row_matches_policy_topic(
    depth4: str,
    policy_module: str,
    topic: str,
    depth4_matcher,
    match_mode: str,
    *,
    has_policy_module_column: bool,
) -> bool:
    """Prefer the normalized 34-module column when the workbook provides it."""

    if match_mode in {"strict", "scoped", "exact"} and has_policy_module_column:
        return matches_policy_module_cell(policy_module, topic)
    if has_policy_module_column and matches_policy_module_cell(policy_module, topic):
        return True
    return bool(depth4 and depth4_matcher(depth4, topic))


def matches_policy_module_cell(value: str, topic: str) -> bool:
    target = normalize_match(topic)
    if not target:
        return False
    return any(normalize_match(module) == target for module in split_policy_module_cell(value))


def split_policy_module_cell(value: str) -> List[str]:
    text = clean_text(value)
    if not text:
        return []
    return [
        item.strip()
        for item in re.split(r"\s*(?:\n|;|；|\|)\s*", text)
        if item.strip()
    ]


def load_scoped_requirements_for_topic(
    topic: str,
    requirements_dir: Path | str = DEFAULT_REQUIREMENTS_DIR,
) -> List[RequirementItem]:
    """Load mandatory authoring-scope requirements for one policy topic."""
    return load_requirements_for_topic(topic, requirements_dir, match_mode="strict")


def requirement_column_indexes(headers: Sequence[str]) -> dict[str, int]:
    """Resolve requirement workbook columns across old/new workbook variants."""

    return {
        "number": find_column(headers, "번호"),
        "depth3": find_column(headers, "depth3"),
        "depth4": find_column(headers, "depth4"),
        "requirement_id": find_column(headers, "요구사항id"),
        "parent_name": find_column_any(headers, ("상위요구사항명", "상위요구사항")),
        "parent_description": find_column(headers, "요구사항설명"),
        "detail_id": find_column(headers, "상세요구사항id"),
        "detail_name": find_column(headers, "상세요구사항명"),
        "detail_description": find_column(headers, "상세요구사항설명"),
        "requirement_type": find_column_any(headers, ("기능비기능", "필수여부")),
        "priority": find_column(headers, "우선순위"),
        "required": find_column(headers, "필수여부"),
        "source": find_column(headers, "출처"),
        "owner_team": find_column(headers, "요건담당팀"),
        "owner": find_column(headers, "요건담당자"),
        "edit_status": find_column(headers, "편집현황"),
        "review_status": find_column_any(headers, ("검토현황", "담당자검토")),
        "policy_module": find_column(headers, POLICY_MODULE_COLUMN_NAME),
        "policy_module_id": find_column(headers, POLICY_MODULE_ID_COLUMN_NAME),
        "policy_include": find_column(headers, POLICY_MODULE_INCLUDE_COLUMN_NAME),
        "policy_shared_reason": find_column(headers, POLICY_MODULE_SHARED_REASON_COLUMN_NAME),
        "policy_mapping_status": find_column(headers, POLICY_MODULE_STATUS_COLUMN_NAME),
    }


def requirements_database_enabled() -> bool:
    return str(os.environ.get("NC_REQUIREMENTS_DB_ENABLED", "1")).strip().casefold() not in {
        "0",
        "false",
        "no",
    }


def ensure_requirements_database(
    requirements_dir: Path | str = DEFAULT_REQUIREMENTS_DIR,
    database_path: Path | str = DEFAULT_REQUIREMENTS_DB_PATH,
) -> Path | None:
    """Build or refresh the requirement SQLite database from the source workbook."""

    root = Path(requirements_dir)
    workbook_path = find_requirements_workbook(root)
    if not workbook_path:
        return None

    db_path = Path(database_path)
    source_hash = file_sha256(workbook_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        initialize_requirements_database(conn)
        if requirements_database_is_current(conn, workbook_path, source_hash):
            return db_path
        rebuild_requirements_database(conn, workbook_path, source_hash)
    return db_path


def load_requirements_for_topic_from_database(
    topic: str,
    requirements_dir: Path | str = DEFAULT_REQUIREMENTS_DIR,
    *,
    match_mode: str = "broad",
    database_path: Path | str = DEFAULT_REQUIREMENTS_DB_PATH,
) -> List[RequirementItem]:
    db_path = ensure_requirements_database(requirements_dir, database_path)
    if not db_path:
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        has_policy_module_column = requirements_database_has_policy_module_column(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM requirement_rows
            WHERE COALESCE(detail_name, '') <> ''
               OR COALESCE(detail_description, '') <> ''
            ORDER BY source_row_number ASC, detail_name ASC
            """
        ).fetchall()

    items: List[RequirementItem] = []
    matcher = matches_policy_topic_strict if match_mode in {"strict", "scoped", "exact"} else matches_policy_topic
    for row in rows:
        depth4 = clean_text(row["depth4"])
        policy_module = clean_text(row["policy_module"])
        if match_mode in {"strict", "scoped", "exact"} and not has_policy_module_column:
            if not row_matches_database_strict_topic(depth4, topic):
                continue
        elif not row_matches_policy_topic(
            depth4,
            policy_module,
            topic,
            matcher,
            match_mode,
            has_policy_module_column=has_policy_module_column,
        ):
            continue
        if clean_text(row["edit_status"]) == "삭제":
            continue
        items.append(requirement_item_from_db_row(row))

    return sorted(items, key=requirement_sort_key)


def row_matches_database_strict_topic(depth4: str, topic: str) -> bool:
    """Strict matching without consulting mapping workbooks when DB labels are exact."""

    depth_key = normalize_match(depth4)
    if not depth_key:
        return False
    labels = [strip_depth_number(topic)]
    labels.extend(STRICT_TOPIC_DEPTH4_ALIASES.get(strip_depth_number(topic), ()))
    return depth_key in {normalize_match(label) for label in labels}


def requirement_item_from_db_row(row: sqlite3.Row) -> RequirementItem:
    return RequirementItem(
        source_number=clean_text(row["source_number"]) or f"ROW{row['source_row_number']}",
        depth3=clean_text(row["depth3"]),
        depth4=strip_depth_number(clean_text(row["depth4"])),
        requirement_id=clean_text(row["requirement_id"]),
        parent_name=clean_text(row["parent_name"]),
        parent_description=clean_text(row["parent_description"]),
        detail_name=clean_text(row["detail_name"]),
        detail_description=clean_text(row["detail_description"]),
        requirement_type=clean_text(row["requirement_type"]),
        priority=clean_text(row["priority"]),
        required=clean_text(row["required"]),
        source=clean_text(row["source"]),
        owner_team=clean_text(row["owner_team"]),
        owner=clean_text(row["owner"]),
        edit_status=clean_text(row["edit_status"]),
        review_status=clean_text(row["review_status"]),
        policy_module=clean_text(row["policy_module"]),
        policy_module_id=clean_text(row["policy_module_id"]),
        policy_include=clean_text(row["policy_include"]),
        policy_shared_reason=clean_text(row["policy_shared_reason"]),
        policy_mapping_status=clean_text(row["policy_mapping_status"]),
        detail_id=clean_text(row["detail_id"]),
    )


def initialize_requirements_database(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requirement_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            source_row_number INTEGER NOT NULL,
            source_number TEXT,
            category TEXT,
            module TEXT,
            depth3 TEXT,
            depth4 TEXT,
            normalized_depth4 TEXT,
            requirement_id TEXT,
            parent_name TEXT,
            parent_description TEXT,
            detail_id TEXT,
            detail_name TEXT,
            detail_description TEXT,
            requirement_type TEXT,
            priority TEXT,
            required TEXT,
            source TEXT,
            owner_team TEXT,
            owner TEXT,
            edit_status TEXT,
            review_status TEXT,
            policy_module TEXT,
            normalized_policy_module TEXT,
            policy_module_id TEXT,
            policy_include TEXT,
            policy_shared_reason TEXT,
            policy_mapping_status TEXT,
            raw_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requirement_rows_depth4 ON requirement_rows(normalized_depth4)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requirement_rows_policy_module ON requirement_rows(normalized_policy_module)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requirement_rows_detail_id ON requirement_rows(detail_id)")
    conn.commit()


def requirements_database_is_current(conn: sqlite3.Connection, workbook_path: Path, source_hash: str) -> bool:
    metadata = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
    return (
        metadata.get("schema_version") == str(REQUIREMENTS_DB_SCHEMA_VERSION)
        and metadata.get("source_path") == str(workbook_path.resolve(strict=False))
        and metadata.get("source_hash") == source_hash
    )


def rebuild_requirements_database(conn: sqlite3.Connection, workbook_path: Path, source_hash: str) -> None:
    rows = read_xlsx_sheet(workbook_path, REQUIREMENT_SHEET_NAME)
    conn.execute("DELETE FROM requirement_rows")
    conn.execute("DELETE FROM metadata")
    if not rows:
        write_requirements_metadata(conn, workbook_path, source_hash, row_count=0, detail_row_count=0, headers=[])
        conn.commit()
        return

    raw_headers = make_unique_headers(rows[0])
    headers = [header_key(value) for value in rows[0]]
    indexes = requirement_column_indexes(headers)
    detail_count = 0
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(clean_text(value) for value in row):
            continue
        record = requirement_record_from_row(workbook_path, row_number, row, raw_headers, indexes)
        if record["detail_name"] or record["detail_description"]:
            detail_count += 1
        conn.execute(
            """
            INSERT INTO requirement_rows (
                source_file, source_row_number, source_number, category, module, depth3, depth4,
                normalized_depth4, requirement_id, parent_name, parent_description, detail_id,
                detail_name, detail_description, requirement_type, priority, required, source,
                owner_team, owner, edit_status, review_status, policy_module,
                normalized_policy_module, policy_module_id, policy_include, policy_shared_reason,
                policy_mapping_status, raw_json
            )
            VALUES (
                :source_file, :source_row_number, :source_number, :category, :module, :depth3, :depth4,
                :normalized_depth4, :requirement_id, :parent_name, :parent_description, :detail_id,
                :detail_name, :detail_description, :requirement_type, :priority, :required, :source,
                :owner_team, :owner, :edit_status, :review_status, :policy_module,
                :normalized_policy_module, :policy_module_id, :policy_include, :policy_shared_reason,
                :policy_mapping_status, :raw_json
            )
            """,
            record,
        )
    write_requirements_metadata(conn, workbook_path, source_hash, row_count=len(rows) - 1, detail_row_count=detail_count, headers=raw_headers)
    conn.commit()


def requirement_record_from_row(
    workbook_path: Path,
    row_number: int,
    row: Sequence[str],
    raw_headers: Sequence[str],
    indexes: dict[str, int],
) -> dict[str, str | int]:
    category_index = find_raw_header_index(raw_headers, "구분")
    module_index = find_raw_header_index(raw_headers, "모듈")
    depth4 = cell_text(row, indexes["depth4"])
    policy_module = cell_text(row, indexes["policy_module"])
    detail_description = cell_text(row, indexes["detail_description"])
    detail_name = effective_detail_name(
        cell_text(row, indexes["detail_name"]),
        detail_description,
        parent_name=cell_text(row, indexes["parent_name"]),
        requirement_id=cell_text(row, indexes["requirement_id"]),
    )
    raw = {
        raw_headers[index]: cell_text(row, index)
        for index in range(len(raw_headers))
        if index < len(row) and cell_text(row, index)
    }
    return {
        "source_file": workbook_path.name,
        "source_row_number": row_number,
        "source_number": cell_text(row, indexes["number"]) or f"ROW{row_number}",
        "category": cell_text(row, category_index),
        "module": cell_text(row, module_index),
        "depth3": cell_text(row, indexes["depth3"]),
        "depth4": strip_depth_number(depth4),
        "normalized_depth4": normalize_match(depth4),
        "requirement_id": cell_text(row, indexes["requirement_id"]),
        "parent_name": cell_text(row, indexes["parent_name"]),
        "parent_description": cell_text(row, indexes["parent_description"]),
        "detail_id": cell_text(row, indexes["detail_id"]),
        "detail_name": detail_name,
        "detail_description": detail_description,
        "requirement_type": cell_text(row, indexes["requirement_type"]),
        "priority": cell_text(row, indexes["priority"]),
        "required": cell_text(row, indexes["required"]),
        "source": cell_text(row, indexes["source"]),
        "owner_team": cell_text(row, indexes["owner_team"]),
        "owner": cell_text(row, indexes["owner"]),
        "edit_status": cell_text(row, indexes["edit_status"]),
        "review_status": cell_text(row, indexes["review_status"]),
        "policy_module": policy_module,
        "normalized_policy_module": normalize_match(policy_module),
        "policy_module_id": cell_text(row, indexes["policy_module_id"]),
        "policy_include": cell_text(row, indexes["policy_include"]),
        "policy_shared_reason": cell_text(row, indexes["policy_shared_reason"]),
        "policy_mapping_status": cell_text(row, indexes["policy_mapping_status"]),
        "raw_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
    }


def write_requirements_metadata(
    conn: sqlite3.Connection,
    workbook_path: Path,
    source_hash: str,
    *,
    row_count: int,
    detail_row_count: int,
    headers: Sequence[str],
) -> None:
    metadata = {
        "schema_version": str(REQUIREMENTS_DB_SCHEMA_VERSION),
        "source_path": str(workbook_path.resolve(strict=False)),
        "source_name": workbook_path.name,
        "source_hash": source_hash,
        "source_mtime": str(workbook_path.stat().st_mtime),
        "sheet_name": REQUIREMENT_SHEET_NAME,
        "row_count": str(row_count),
        "detail_row_count": str(detail_row_count),
        "headers_json": json.dumps(list(headers), ensure_ascii=False),
    }
    conn.executemany("INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items())


def requirements_database_has_policy_module_column(conn: sqlite3.Connection) -> bool:
    headers_json = conn.execute("SELECT value FROM metadata WHERE key = 'headers_json'").fetchone()
    if not headers_json:
        return False
    try:
        headers = json.loads(headers_json[0])
    except json.JSONDecodeError:
        return False
    return any(header_key(header) == header_key(POLICY_MODULE_COLUMN_NAME) for header in headers)


def find_requirements_workbook(requirements_dir: Path) -> Path | None:
    explicit_path = os.environ.get("NC_REQUIREMENTS_WORKBOOK", "").strip()
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        if candidate.exists() and candidate.suffix.lower() == ".xlsx" and workbook_has_sheet(candidate, REQUIREMENT_SHEET_NAME):
            return candidate

    if requirements_dir.is_file() and requirements_dir.suffix.lower() == ".xlsx":
        return requirements_dir if workbook_has_sheet(requirements_dir, REQUIREMENT_SHEET_NAME) else None
    if not requirements_dir.exists():
        return None
    workbooks = [path for path in requirements_dir.glob("*.xlsx") if not path.name.startswith("~$")]
    if not workbooks:
        return None
    valid_workbooks = [path for path in workbooks if workbook_has_sheet(path, REQUIREMENT_SHEET_NAME)]
    if not valid_workbooks:
        return None
    return max(valid_workbooks, key=requirements_workbook_rank_key)


def requirements_workbook_rank_key(path: Path) -> tuple[int, int, float]:
    """Prefer the newest dated final requirements workbook over stale files.

    The requirements folder keeps historical workbooks for traceability. Using
    modification time alone is fragile because opening an old workbook can make
    it look newer than the authoritative final file.
    """
    name = path.name
    date_match = re.search(r"(20\d{6})", name)
    date_rank = int(date_match.group(1)) if date_match else 0
    final_rank = 1 if "최종" in name else 0
    return (date_rank, final_rank, path.stat().st_mtime)


def find_policy_module_mapping_workbook(requirements_dir: Path = DEFAULT_REQUIREMENTS_DIR) -> Path | None:
    if requirements_dir.is_file() and requirements_dir.suffix.lower() == ".xlsx":
        return requirements_dir if workbook_has_policy_module_mapping(requirements_dir) else None
    if not requirements_dir.exists():
        return None
    workbooks = [path for path in requirements_dir.glob("*.xlsx") if not path.name.startswith("~$")]
    mapping_workbooks = [path for path in workbooks if workbook_has_policy_module_mapping(path)]
    if not mapping_workbooks:
        return None
    return max(mapping_workbooks, key=lambda path: path.stat().st_mtime)


def workbook_has_policy_module_mapping(path: Path) -> bool:
    try:
        if not workbook_has_sheet(path, POLICY_MODULE_MAPPING_SHEET_NAME):
            return False
        rows = read_xlsx_sheet(path, POLICY_MODULE_MAPPING_SHEET_NAME)
    except (KeyError, ET.ParseError, zipfile.BadZipFile, FileNotFoundError):
        return False
    headers = [header_key(value) for value in rows[0]]
    return find_column(headers, "4depth") >= 0 and find_column(headers, "변경4depth") >= 0


def workbook_has_sheet(path: Path, sheet_name: str) -> bool:
    try:
        return sheet_name in workbook_sheet_names(path)
    except (KeyError, ET.ParseError, zipfile.BadZipFile, FileNotFoundError):
        return False


def workbook_sheet_names(path: Path) -> List[str]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        return [sheet.attrib.get("name", "") for sheet in workbook.findall(".//{*}sheet")]


def read_xlsx_sheet(path: Path, sheet_name: str) -> List[List[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = resolve_sheet_path(archive, sheet_name)
        if not sheet_path:
            return []

        root = ET.fromstring(archive.read(sheet_path))
        rows: List[List[str]] = []
        for row in root.findall(".//{*}sheetData/{*}row"):
            values: Dict[int, str] = {}
            max_col = 0
            for cell in row.findall("{*}c"):
                col_index = column_index_from_ref(cell.attrib.get("r", ""))
                if col_index < 0:
                    continue
                values[col_index] = read_cell(cell, shared_strings)
                max_col = max(max_col, col_index)
            if values:
                rows.append([values.get(index, "") for index in range(max_col + 1)])
        return rows


@lru_cache(maxsize=8)
def load_policy_module_mapping(
    requirements_dir: Path | str = DEFAULT_REQUIREMENTS_DIR,
) -> dict[str, List[str]]:
    """Return 34-module topic mapping as ``new_topic -> source Depth 4 labels``.

    The mapping sheet is authoritative for the policy-document module list, but
    the real requirement workbook remains the source of detailed requirements.
    Some mapping cells intentionally combine two source modules; those cells are
    expanded only when the exact workbook Depth 4 label does not exist.
    """
    root = Path(requirements_dir)
    mapping_path = find_policy_module_mapping_workbook(root)
    requirement_path = find_requirements_workbook(root)
    if not mapping_path or not requirement_path:
        return {}

    mapping_rows = read_xlsx_sheet(mapping_path, POLICY_MODULE_MAPPING_SHEET_NAME)
    requirement_rows = read_xlsx_sheet(requirement_path, REQUIREMENT_SHEET_NAME)
    if not mapping_rows or not requirement_rows:
        return {}

    known_depth4 = requirement_depth4_labels(requirement_rows)
    headers = [header_key(value) for value in mapping_rows[0]]
    old_index = find_column(headers, "4depth")
    new_index = find_column(headers, "변경4depth")
    if old_index < 0 or new_index < 0:
        return {}

    result: dict[str, List[str]] = {}
    by_known_key = {normalize_match(label): label for label in known_depth4}
    for row in mapping_rows[1:]:
        old_cell = cell_text(row, old_index)
        new_topic = cell_text(row, new_index)
        if not old_cell or not new_topic:
            continue
        if strip_depth_number(new_topic) == "삭제":
            continue
        new_topic = strip_depth_number(new_topic)
        new_topic_key = normalize_match(new_topic)
        if new_topic_key in by_known_key:
            result[new_topic] = [by_known_key[new_topic_key]]
            continue
        source_labels = expand_mapping_source_depth4(old_cell, known_depth4)
        if not source_labels:
            continue
        result.setdefault(new_topic, [])
        result[new_topic].extend(source_labels)

    return {topic: unique_axes(labels) for topic, labels in result.items()}


def requirement_depth4_labels(rows: Sequence[Sequence[str]]) -> List[str]:
    if not rows:
        return []
    headers = [header_key(value) for value in rows[0]]
    depth4_index = find_column(headers, "depth4")
    edit_status_index = find_column(headers, "편집현황")
    labels: List[str] = []
    for row in rows[1:]:
        if cell_text(row, edit_status_index) == "삭제":
            continue
        label = strip_depth_number(cell_text(row, depth4_index))
        if label:
            labels.append(label)
    return unique_axes(labels)


def expand_mapping_source_depth4(value: str, known_depth4: Sequence[str]) -> List[str]:
    label = strip_depth_number(value)
    if not label:
        return []

    by_key = {normalize_match(item): item for item in known_depth4}
    label_key = normalize_match(label)
    if label_key in by_key:
        return [by_key[label_key]]
    if label_key in MAPPING_DEPTH4_CELL_ALIASES:
        return [alias for alias in MAPPING_DEPTH4_CELL_ALIASES[label_key] if normalize_match(alias) in by_key]

    expanded: List[str] = []
    for part in re.split(r"\s*/\s*", label):
        part_key = normalize_match(part)
        if part_key in by_key:
            expanded.append(by_key[part_key])
            continue
        for alias in MAPPING_DEPTH4_CELL_ALIASES.get(part_key, ()):
            if normalize_match(alias) in by_key:
                expanded.append(by_key[normalize_match(alias)])
    return unique_axes(expanded)


def read_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("{*}si"):
        strings.append("".join(text.text or "" for text in item.findall(".//{*}t")))
    return strings


def resolve_sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib.get("Id"): rel.attrib.get("Target", "")
        for rel in rels.findall("{*}Relationship")
    }
    for sheet in workbook.findall(".//{*}sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        relationship_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_targets.get(relationship_id, "")
        if not target:
            return ""
        target = target.lstrip("/")
        return target if target.startswith("xl/") else f"xl/{target}"
    return ""


def read_cell(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return clean_text("".join(text.text or "" for text in cell.findall(".//{*}t")))

    value_node = cell.find("{*}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text
    if cell_type == "s":
        try:
            return clean_text(shared_strings[int(raw_value)])
        except (IndexError, ValueError):
            return ""
    return clean_text(raw_value)


def column_index_from_ref(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    if not letters:
        return -1
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def header_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", normalize(value)).casefold()


def find_column(headers: Sequence[str], expected: str) -> int:
    target = header_key(expected)
    for index, header in enumerate(headers):
        if header == target:
            return index
    for index, header in enumerate(headers):
        if target in header:
            return index
    return -1


def find_column_any(headers: Sequence[str], expected_values: Sequence[str]) -> int:
    for expected in expected_values:
        index = find_column(headers, expected)
        if index >= 0:
            return index
    return -1


def find_raw_header_index(headers: Sequence[str], expected: str) -> int:
    target = header_key(expected)
    for index, header in enumerate(headers):
        if header_key(header) == target or target in header_key(header):
            return index
    return -1


def make_unique_headers(values: Sequence[str]) -> List[str]:
    counts: dict[str, int] = {}
    headers: List[str] = []
    for index, value in enumerate(values, start=1):
        base = clean_text(value) or f"column_{index}"
        count = counts.get(base, 0) + 1
        counts[base] = count
        headers.append(base if count == 1 else f"{base}_{count}")
    return headers


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_text(row: Sequence[str], index: int) -> str:
    if index < 0 or index >= len(row):
        return ""
    return clean_text(row[index])


def clean_text(value: object) -> str:
    text = normalize(str(value if value is not None else ""))
    text = re.sub(r"\.0$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if text.lower() == "nan" or text.upper() in EXCEL_ERROR_VALUES:
        return ""
    return text


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def strip_depth_number(value: str) -> str:
    return re.sub(r"^\s*\d+\s*", "", normalize(value)).strip()


def normalize_match(value: str) -> str:
    text = strip_depth_number(value).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


@lru_cache(maxsize=128)
def strict_depth4_labels_for_topic(topic: str) -> List[str]:
    stripped_topic = strip_depth_number(topic)
    labels = [stripped_topic]
    module_mapping = load_policy_module_mapping()
    topic_key = normalize_match(stripped_topic)
    for mapped_topic, source_labels in module_mapping.items():
        if normalize_match(mapped_topic) == topic_key:
            labels.extend(source_labels)
            break
    labels.extend(STRICT_TOPIC_DEPTH4_ALIASES.get(stripped_topic, ()))
    return unique_axes(labels)


def matches_policy_topic_strict(depth4: str, topic: str) -> bool:
    depth_key = normalize_match(depth4)
    if not depth_key:
        return False
    return depth_key in {normalize_match(label) for label in strict_depth4_labels_for_topic(topic)}


def topic_match_axes(value: str) -> List[str]:
    """Return compact topic axes for tolerant requirement-depth matching.

    Requirement workbooks often write a single topic as ``회원 가입/탈퇴`` while
    the UI topic can be ``회원가입 · 회원탈퇴``. The matcher should understand
    those as the same scope, but it should not match on one broad word such as
    ``가입`` alone unless another axis also overlaps.
    """
    raw = strip_depth_number(value)
    if not raw:
        return []
    parts = re.split(r"\s*(?:/|,|，|·|\+|&|\b및\b|\band\b|\(|\)|\[|\])\s*", raw)
    axes: List[str] = []
    for part in parts:
        key = normalize_match(part)
        if len(key) >= 2 and key not in {"nc", "정책", "정책서", "통합채널"}:
            axes.append(key)
    if not axes:
        key = normalize_match(raw)
        if len(key) >= 2:
            axes.append(key)
    return unique_axes(axes)


def unique_axes(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def axis_matches(axis: str, target_key: str, target_axes: Sequence[str]) -> bool:
    if len(axis) < 2:
        return False
    if axis in target_key:
        return True
    return any(axis == target or axis in target or target in axis for target in target_axes if len(target) >= 2)


def matches_policy_topic(depth4: str, topic: str) -> bool:
    depth_key = normalize_match(depth4)
    topic_key = normalize_match(topic)
    if not depth_key or not topic_key:
        return False
    if depth_key == topic_key:
        return True
    if len(depth_key) >= 4 and len(topic_key) >= 4 and (depth_key in topic_key or topic_key in depth_key):
        return True

    depth_axes = topic_match_axes(depth4)
    topic_axes = topic_match_axes(topic)
    if not depth_axes or not topic_axes:
        return False

    depth_overlap = sum(1 for axis in depth_axes if axis_matches(axis, topic_key, topic_axes))
    topic_overlap = sum(1 for axis in topic_axes if axis_matches(axis, depth_key, depth_axes))
    required_depth_overlap = min(2, len(depth_axes))
    required_topic_overlap = min(2, len(topic_axes))
    if depth_overlap >= required_depth_overlap and topic_overlap >= 1:
        return True
    return topic_overlap >= required_topic_overlap and depth_overlap >= 1


def requirement_sort_key(item: RequirementItem) -> tuple[int, int, str]:
    """Keep requirement order stable without using unverified priority labels.

    Requirement IDs and workbook priority are trace/admin metadata. Authoring
    decisions should be driven by the detailed requirement name and description,
    so priority must not change which requirements are considered first.
    """
    number = int(item.source_number) if item.source_number.isdigit() else 999999
    return (number, item.detail_name)
