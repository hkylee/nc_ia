"""Artifact synchronization checks for rendered policy outputs."""

from __future__ import annotations

import json
import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

try:
    from runtime_paths import PROJECT_ROOT, OUTPUT_ROOT, REPORTS_ROOT
    from policy_versioning import policy_version_sort_key
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import PROJECT_ROOT, OUTPUT_ROOT, REPORTS_ROOT
    from .policy_versioning import policy_version_sort_key


POLICY_HTML_FILENAME_RE = re.compile(
    r"^NC_(?P<topic>.+)_정책서_(?P<template_label>간소화|Full)_(?P<version>v\d+\.\d+(?:_보완본)?)\.html$"
)
ARTIFACT_ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:ACT|US|ST|PR|PRC|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
SYNC_PREFIXES = ("ACT", "US", "ST", "PR", "FN", "PG", "PI")
HTML_RUNTIME_SOURCE_SPEC_REASONS = {
    "manual_edit_new_version",
    "manual_edit_overwrite",
    "html_upload",
    "diagram_edit",
    "agent_revision_current_version",
    "agent_revision_new_version",
}


def evaluate_policy_artifact_drift(
    policy_path: Path,
    *,
    output_root: Path | None = None,
    reports_root: Path | None = None,
) -> Dict[str, Any]:
    output_root = output_root or OUTPUT_ROOT
    reports_root = reports_root or REPORTS_ROOT
    policy_path = policy_path.resolve()
    parsed = parse_policy_filename(policy_path.name)
    issues: list[Dict[str, Any]] = []
    checks: list[Dict[str, Any]] = []

    html_text = read_text(policy_path)
    html_ids = set(ARTIFACT_ID_PATTERN.findall(html_text))
    spec_path = version_spec_path(policy_path, output_root)
    topic_spec_path = topic_spec_path_for(parsed.get("topic", ""), output_root)
    spec = read_spec(spec_path)
    spec_ids: set[str] = set()
    requirement_trace_count = 0
    requirement_count = 0
    html_runtime_source = False

    if spec is None:
        add_issue(issues, "DRIFT-SPEC-MISSING", "P1", "version_spec", f"버전 spec 파일이 없습니다: {spec_path.name}", "HTML 저장 시 동일 버전 spec JSON을 함께 저장하세요.")
    else:
        spec_ids = collect_spec_ids(spec)
        requirement_trace_count = count_trace_matrix(spec)
        requirement_count = spec_requirement_count(spec)
        meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
        html_runtime_source = spec_marks_html_runtime_source(spec)
        if str(meta.get("version", "") or "").strip() != str(parsed.get("version", "") or "").strip():
            add_issue(issues, "DRIFT-SPEC-VERSION", "P1", "version_spec", "HTML 파일명 버전과 spec meta.version이 다릅니다.", "HTML, 버전 spec, 주제 spec의 버전 값을 동일하게 저장하세요.")
        if str(meta.get("topic_slug", "") or meta.get("topic", "") or "").strip() not in {"", str(parsed.get("topic", "") or "").strip()}:
            add_issue(issues, "DRIFT-SPEC-TOPIC", "P2", "version_spec", "HTML 파일명 주제와 spec meta 주제 식별자가 다릅니다.", "주제 slug와 spec meta.topic_slug를 렌더링 대상 파일명과 맞추세요.")

    if spec_ids and html_text:
        missing_ids = sorted(spec_ids - html_ids)
        missing_ratio = len(missing_ids) / max(1, len(spec_ids))
        if html_runtime_source and missing_ids:
            if not spec_runtime_source_synced_with_html(spec, html_text):
                add_issue(
                    issues,
                    "DRIFT-HTML-RUNTIME-SOURCE",
                    "P2",
                    "html_spec",
                    f"직접 편집/업로드 HTML 기준 버전입니다. spec ID 차이 {len(missing_ids)}건은 HTML 덮어쓰기 대상에서 제외합니다.",
                    "사용자가 저장한 HTML을 기준으로 유지하고, 필요 시 HTML 기준 spec 보정을 실행하세요.",
                )
        elif len(missing_ids) >= 3 and missing_ratio > 0.15:
            add_issue(
                issues,
                "DRIFT-HTML-SPEC-ID",
                "P1",
                "html_spec",
                f"spec ID {len(missing_ids)}건이 HTML 본문에서 확인되지 않습니다.",
                f"렌더링 산출물을 spec 기준으로 재생성하세요. 예: {', '.join(missing_ids[:5])}",
            )
        elif missing_ids:
            add_issue(
                issues,
                "DRIFT-HTML-SPEC-ID-PARTIAL",
                "P2",
                "html_spec",
                f"spec ID 일부가 HTML 본문에서 확인되지 않습니다: {len(missing_ids)}건",
                f"누락 ID가 렌더링 제외 대상인지 확인하세요. 예: {', '.join(missing_ids[:5])}",
            )

    if topic_spec_path and topic_spec_path.exists() and spec is not None and is_latest_policy_version(policy_path, parsed, output_root):
        topic_spec = read_spec(topic_spec_path)
        topic_meta = topic_spec.get("meta", {}) if isinstance(topic_spec, Mapping) and isinstance(topic_spec.get("meta"), Mapping) else {}
        if (
            topic_spec is not None
            and topic_spec_template_type(topic_meta) in {"", parsed_template_type(parsed)}
            and str(topic_meta.get("version", "") or "").strip() not in {"", str(parsed.get("version", "") or "").strip()}
        ):
            add_issue(issues, "DRIFT-TOPIC-SPEC-LATEST", "P2", "topic_spec", "주제 대표 spec이 현재 HTML 버전과 다릅니다.", "현재 버전을 최신 대표본으로 쓰는 경우 topic policy spec도 함께 갱신하세요.")

    bpmn_result = evaluate_bpmn_sync(policy_path, spec, issues)
    trace_result = evaluate_trace_sync(parsed.get("topic", ""), requirement_count, requirement_trace_count, reports_root, issues)

    checks.extend(
        [
            {"id": "ART-1", "name": "version_spec", "passed": spec is not None, "path": str(spec_path)},
            {"id": "ART-2", "name": "html_spec_ids", "passed": not any(issue["id"].startswith("DRIFT-HTML-SPEC-ID") and issue["severity"] == "P1" for issue in issues), "specIdCount": len(spec_ids), "htmlIdCount": len(html_ids)},
            bpmn_result,
            trace_result,
        ]
    )
    p1_count = sum(1 for issue in issues if issue.get("severity") == "P1")
    p2_count = sum(1 for issue in issues if issue.get("severity") == "P2")
    status = "fail" if p1_count else "warn" if p2_count else "pass"
    return {
        "agent": "Artifact Drift Check",
        "version": "1.0",
        "status": status,
        "passed": status == "pass",
        "summary": artifact_drift_summary(status, p1_count, p2_count),
        "policyFile": policy_path.name,
        "htmlRuntimeSource": html_runtime_source,
        "htmlSpecSyncNeeded": bool(html_runtime_source and not spec_runtime_source_synced_with_html(spec, html_text)),
        "checks": checks,
        "issues": issues,
    }


def evaluate_bpmn_sync(policy_path: Path, spec: Optional[Mapping[str, Any]], issues: list[Dict[str, Any]]) -> Dict[str, Any]:
    bpmn_path = policy_path.with_name(f"{policy_path.stem}_전체업무흐름도.bpmn")
    process_ids = sorted(
        str(item.get("id", "") or "").strip()
        for item in (spec or {}).get("processes", [])
        if isinstance(item, Mapping) and item.get("id")
    )
    if not process_ids:
        return {"id": "ART-3", "name": "bpmn", "passed": True, "path": str(bpmn_path), "processIdCount": 0}
    if not bpmn_path.exists():
        add_issue(issues, "DRIFT-BPMN-MISSING", "P1", "bpmn", f"BPMN 파일이 없습니다: {bpmn_path.name}", "HTML/spec 저장 후 BPMN과 bpmn.io viewer를 함께 생성하세요.")
        return {"id": "ART-3", "name": "bpmn", "passed": False, "path": str(bpmn_path), "processIdCount": len(process_ids)}
    bpmn_text = read_text(bpmn_path)
    try:
        ET.fromstring(bpmn_text)
    except ET.ParseError as exc:
        add_issue(issues, "DRIFT-BPMN-XML", "P1", "bpmn", f"BPMN XML 파싱에 실패했습니다: {exc}", "BPMN을 spec 기준으로 재생성하세요.")
        return {"id": "ART-3", "name": "bpmn", "passed": False, "path": str(bpmn_path), "processIdCount": len(process_ids)}
    missing_process_ids = [process_id for process_id in process_ids if process_id not in bpmn_text]
    if len(missing_process_ids) >= max(2, len(process_ids) // 2):
        add_issue(
            issues,
            "DRIFT-BPMN-PROCESS",
            "P1",
            "bpmn",
            f"BPMN에서 프로세스 ID {len(missing_process_ids)}건이 확인되지 않습니다.",
            f"BPMN을 현재 spec으로 다시 렌더링하세요. 예: {', '.join(missing_process_ids[:5])}",
        )
    elif missing_process_ids:
        add_issue(
            issues,
            "DRIFT-BPMN-PROCESS-PARTIAL",
            "P2",
            "bpmn",
            f"BPMN에서 일부 프로세스 ID가 확인되지 않습니다: {len(missing_process_ids)}건",
            f"BPMN 표시명과 process.id 동기화를 확인하세요. 예: {', '.join(missing_process_ids[:5])}",
        )
    return {"id": "ART-3", "name": "bpmn", "passed": not missing_process_ids, "path": str(bpmn_path), "processIdCount": len(process_ids)}


def evaluate_trace_sync(
    topic: str,
    requirement_count: int,
    trace_count: int,
    reports_root: Path,
    issues: list[Dict[str, Any]],
) -> Dict[str, Any]:
    trace_reports = find_trace_reports(topic, reports_root)
    passed = requirement_count == 0 or trace_count > 0 or bool(trace_reports)
    if not passed:
        add_issue(
            issues,
            "DRIFT-TRACE-MISSING",
            "P1",
            "requirement_trace",
            "요구사항 수가 있지만 trace_matrix 또는 요구사항 Trace 리포트를 찾지 못했습니다.",
            "요구사항은 상세 ID 단위로 trace_matrix에 남기고, PM requirement trace 리포트를 함께 갱신하세요.",
        )
    return {
        "id": "ART-4",
        "name": "requirement_trace",
        "passed": passed,
        "requirementCount": requirement_count,
        "traceMatrixCount": trace_count,
        "traceReports": [str(path) for path in trace_reports[:5]],
    }


def parse_policy_filename(name: str) -> Dict[str, str]:
    normalized = unicodedata.normalize("NFC", str(name or ""))
    match = POLICY_HTML_FILENAME_RE.match(normalized)
    return match.groupdict() if match else {"topic": "-", "template_label": "-", "version": "-"}


def version_spec_path(policy_path: Path, output_root: Path) -> Path:
    return output_root / f"{policy_path.stem}_spec.json"


def topic_spec_path_for(topic: str, output_root: Path) -> Path | None:
    topic = str(topic or "").strip()
    if not topic or topic == "-":
        return None
    return output_root / f"{topic}_policy_spec.json"


def is_latest_policy_version(policy_path: Path, parsed: Mapping[str, str], output_root: Path) -> bool:
    topic = str(parsed.get("topic", "") or "").strip()
    template_label = str(parsed.get("template_label", "") or "").strip()
    if not topic or topic == "-" or not template_label or template_label == "-":
        return False
    candidates = [
        path
        for path in output_root.glob(f"NC_{topic}_정책서_{template_label}_v*.html")
        if path.is_file() and POLICY_HTML_FILENAME_RE.match(unicodedata.normalize("NFC", path.name))
    ]
    if not candidates:
        return False
    latest = max(candidates, key=policy_file_sort_key)
    return latest.resolve() == policy_path.resolve()


def parsed_template_type(parsed: Mapping[str, str]) -> str:
    return "full" if str(parsed.get("template_label", "") or "") == "Full" else "simple"


def topic_spec_template_type(meta: Mapping[str, Any]) -> str:
    raw = str(meta.get("template_type", "") or "").strip().lower()
    if raw in {"full", "simple"}:
        return raw
    document_type = str(meta.get("document_type", "") or "")
    if "Full" in document_type:
        return "full"
    if "간소화" in document_type:
        return "simple"
    return ""


def policy_file_sort_key(path: Path) -> tuple[int, int, int, int, float]:
    parsed = parse_policy_filename(path.name)
    version = str(parsed.get("version", "") or "")
    minor = re.match(r"^v\d+\.(\d+)", version)
    modern_label = 1 if minor and len(minor.group(1)) >= 2 else 0
    return (*policy_version_sort_key(version), modern_label, path.stat().st_mtime)


def read_spec(path: Path | None) -> Optional[Dict[str, Any]]:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    spec = payload.get("spec") if isinstance(payload, Mapping) and isinstance(payload.get("spec"), Mapping) else payload
    return dict(spec) if isinstance(spec, Mapping) else None


def spec_marks_html_runtime_source(spec: Mapping[str, Any]) -> bool:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    if not isinstance(meta, Mapping):
        return False
    raw_runtime_source = str(meta.get("html_runtime_source", "") or "").strip().casefold()
    if raw_runtime_source in {"1", "true", "yes", "y", "on"}:
        return True
    reason = str(meta.get("version_spec_reason", "") or "").strip()
    return reason in HTML_RUNTIME_SOURCE_SPEC_REASONS


def spec_runtime_source_synced_with_html(spec: Optional[Mapping[str, Any]], html_text: str) -> bool:
    if not isinstance(spec, Mapping):
        return False
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    if not isinstance(meta, Mapping):
        return False
    stored_hash = str(meta.get("html_spec_sync_content_hash", "") or "").strip()
    if not stored_hash:
        return False
    return stored_hash == hashlib.sha256(str(html_text or "").encode("utf-8")).hexdigest()


def collect_spec_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, Mapping):
        raw_id = value.get("id")
        if isinstance(raw_id, str) and any(raw_id.startswith(f"{prefix}-") for prefix in SYNC_PREFIXES):
            ids.add(raw_id)
        for child in value.values():
            ids.update(collect_spec_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(collect_spec_ids(child))
    return ids


def count_trace_matrix(spec: Mapping[str, Any]) -> int:
    trace = spec.get("trace_matrix")
    if isinstance(trace, list):
        return sum(1 for item in trace if isinstance(item, Mapping))
    if isinstance(trace, Mapping):
        return len(trace)
    return 0


def spec_requirement_count(spec: Mapping[str, Any]) -> int:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    for key in ("requirements_count", "detail_requirement_count"):
        try:
            value = int(meta.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if value:
            return value
    mapping_summary = spec.get("requirements_mapping_summary")
    if isinstance(mapping_summary, Mapping):
        try:
            return int(mapping_summary.get("total", 0) or mapping_summary.get("detail_requirement_count", 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def find_trace_reports(topic: str, reports_root: Path) -> list[Path]:
    normalized_topic = normalize_key(topic)
    manual_dir = reports_root / "manual_authoring"
    if not manual_dir.exists():
        return []
    candidates: list[Path] = []
    for path in manual_dir.glob("*requirement_trace*.md"):
        if not path.is_file():
            continue
        if not normalized_topic or normalized_topic in normalize_key(path.name):
            candidates.append(path)
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def add_issue(issues: list[Dict[str, Any]], issue_id: str, severity: str, target: str, detail: str, recommendation: str) -> None:
    issues.append(
        {
            "id": issue_id,
            "severity": severity,
            "target": target,
            "detail": detail,
            "recommendation": recommendation,
        }
    )


def artifact_drift_summary(status: str, p1_count: int, p2_count: int) -> str:
    if status == "pass":
        return "HTML, spec, BPMN, 요구사항 Trace 산출물 동기화가 확인되었습니다."
    if status == "warn":
        return f"산출물 동기화 주의 항목이 있습니다. P2 {p2_count}건입니다."
    return f"산출물 동기화 차단 항목이 있습니다. P1 {p1_count}건, P2 {p2_count}건입니다."


def normalize_key(value: str) -> str:
    return re.sub(r"[\s/_·.-]+", "", unicodedata.normalize("NFC", str(value or ""))).casefold()
