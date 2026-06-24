"""Offline quality audit for generated policy artifacts.

This module intentionally avoids LLM calls. It mines existing checkpoints,
inspection reports, and LLM call logs to validate the generation pipeline and
surface likely quality/cost risks.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

try:
    from policy_agent import remediation_mode_for_report
    from policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE, InspectionFinding, finding_actionability_issues
    from runtime_paths import OUTPUT_ROOT, PROJECT_ROOT, REPORTS_ROOT
    from validator import validate_policy_spec, validate_stage_critical
except ImportError:  # pragma: no cover - package import fallback.
    from .policy_agent import remediation_mode_for_report
    from .policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE, InspectionFinding, finding_actionability_issues
    from .runtime_paths import OUTPUT_ROOT, PROJECT_ROOT, REPORTS_ROOT
    from .validator import validate_policy_spec, validate_stage_critical


@dataclass(frozen=True)
class CheckpointAudit:
    path: str
    topic: str
    stage: str
    passed: bool
    counts: dict[str, int]
    validation_error_count: int
    critical_error_count: int
    sample_errors: list[str]


@dataclass(frozen=True)
class InspectionAudit:
    path: str
    topic: str
    scope: str
    status: str
    score: int
    finding_count: int
    actionability_issue_count: int
    remediation_mode: str
    sample_titles: list[str]


@dataclass(frozen=True)
class LlmLogAudit:
    rows: int
    requests: int
    successes: int
    errors: int
    total_tokens: int
    total_cost_usd: float
    top_schemas: list[dict[str, Any]]
    top_errors: list[dict[str, Any]]


@dataclass(frozen=True)
class ContextPackAudit:
    checkpoint_path: str
    topic: str
    chapter: str
    score: int | None
    status: str
    evidence_gap_count: int
    required_kind_coverage: float | None
    evidence_id_count: int


COUNT_FIELDS = (
    "history",
    "terms",
    "actors",
    "usecases",
    "states",
    "state_transitions",
    "processes",
    "process_details",
    "functions",
    "function_details",
    "policy_groups",
    "policy_details",
)


def run_offline_quality_audit(
    *,
    output_root: Path = OUTPUT_ROOT,
    reports_root: Path = REPORTS_ROOT,
    min_score: int = DEFAULT_INSPECTOR_MIN_SCORE,
) -> dict[str, Any]:
    checkpoints = audit_checkpoints(output_root / "checkpoints")
    inspections = audit_inspections(reports_root / "inspections", min_score=min_score)
    llm_logs = audit_llm_logs(reports_root / "logs" / "llm_calls.jsonl")
    context_runs = audit_context_pack_runs(output_root / "checkpoints")
    recommendations = build_recommendations(checkpoints, inspections, llm_logs, context_runs)
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "minScore": min_score,
        "summary": {
            "checkpointCount": len(checkpoints),
            "inspectionReportCount": len(inspections),
            "llmLogRows": llm_logs.rows,
            "validationErrorCheckpoints": sum(1 for item in checkpoints if item.validation_error_count),
            "criticalErrorCheckpoints": sum(1 for item in checkpoints if item.critical_error_count),
            "lowScoreInspections": sum(1 for item in inspections if item.score < min_score),
            "llmErrors": llm_logs.errors,
            "contextPackRunCount": len(context_runs),
            "lowContextQualityRuns": sum(1 for item in context_runs if item.score is not None and item.score < 70),
            "contextGapRuns": sum(1 for item in context_runs if item.evidence_gap_count > 0),
        },
        "checkpoints": [asdict(item) for item in checkpoints],
        "inspections": [asdict(item) for item in inspections],
        "contextPackRuns": [asdict(item) for item in context_runs],
        "inspectionModeCounts": dict(Counter(item.remediation_mode for item in inspections)),
        "llmLogs": asdict(llm_logs),
        "recommendations": recommendations,
    }


def audit_checkpoints(checkpoints_dir: Path) -> list[CheckpointAudit]:
    audits: list[CheckpointAudit] = []
    for path in sorted(checkpoints_dir.glob("*latest_checkpoint.json")):
        payload = read_json(path)
        if not isinstance(payload, Mapping):
            continue
        spec = payload.get("spec")
        checkpoint = payload.get("checkpoint", {})
        if not isinstance(spec, Mapping):
            continue
        meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
        topic = str(checkpoint.get("topic") or meta.get("topic") or path.name)
        stage = str(checkpoint.get("stage_name") or checkpoint.get("stage_key") or "-")
        business_code = str(meta.get("business_code", "") or "")
        validation_spec = spec_with_default_keys(spec)
        validation = validate_policy_spec(validation_spec, business_code, allow_incomplete=True)
        critical_scope = checkpoint_scope(checkpoint)
        critical = (
            validate_stage_critical(validation_spec, business_code, critical_scope)
            if critical_scope
            else SimpleNamespace(errors=[])
        )
        errors = list(validation.errors) + list(getattr(critical, "errors", []))
        audits.append(
            CheckpointAudit(
                path=path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else str(path),
                topic=topic,
                stage=stage,
                passed=bool(checkpoint.get("passed", False)),
                counts=spec_counts(spec),
                validation_error_count=len(validation.errors),
                critical_error_count=len(getattr(critical, "errors", [])),
                sample_errors=[str(error) for error in errors[:5]],
            )
        )
    return audits


def audit_inspections(inspections_dir: Path, *, min_score: int) -> list[InspectionAudit]:
    audits: list[InspectionAudit] = []
    for path in sorted(inspections_dir.glob("*.json")):
        payload = read_json(path)
        if not isinstance(payload, Mapping) or "score" not in payload:
            continue
        findings = [finding_from_dict(item) for item in payload.get("findings", []) if isinstance(item, Mapping)]
        score = safe_int(payload.get("score"), 0)
        mode = remediation_mode_for_report(score, min_score, findings)
        audits.append(
            InspectionAudit(
                path=path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else str(path),
                topic=topic_from_inspection_path(path),
                scope=str(payload.get("scope", "")),
                status=str(payload.get("status", "")),
                score=score,
                finding_count=len(findings),
                actionability_issue_count=sum(len(finding_actionability_issues(finding)) for finding in findings),
                remediation_mode=mode,
                sample_titles=[finding.title for finding in findings[:3]],
            )
        )
    return audits


def audit_llm_logs(log_path: Path) -> LlmLogAudit:
    rows = 0
    requests = 0
    successes = 0
    errors = 0
    total_tokens = 0
    total_cost = 0.0
    schema_counter: Counter[str] = Counter()
    error_counter: Counter[str] = Counter()
    if not log_path.exists():
        return LlmLogAudit(0, 0, 0, 0, 0, 0.0, [], [])
    for item in iter_jsonl(log_path):
        rows += 1
        event = str(item.get("event", ""))
        schema = str(item.get("schema_name", "unknown") or "unknown")
        if event == "request_start":
            requests += 1
            schema_counter[schema] += 1
        elif event == "request_success":
            successes += 1
            usage = item.get("usage", {}) if isinstance(item.get("usage"), Mapping) else {}
            total_tokens += safe_int(usage.get("total_tokens"), 0)
            total_cost += float(item.get("estimated_cost_usd", 0.0) or 0.0)
        elif event == "request_error":
            errors += 1
            error_counter[normalize_error(str(item.get("error", "")))] += 1
    return LlmLogAudit(
        rows=rows,
        requests=requests,
        successes=successes,
        errors=errors,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
        top_schemas=[{"schema": key, "count": count} for key, count in schema_counter.most_common(10)],
        top_errors=[{"error": key, "count": count} for key, count in error_counter.most_common(10)],
    )


def audit_context_pack_runs(checkpoints_dir: Path) -> list[ContextPackAudit]:
    audits: list[ContextPackAudit] = []
    for path in sorted(checkpoints_dir.glob("*latest_checkpoint.json")):
        payload = read_json(path)
        if not isinstance(payload, Mapping):
            continue
        spec = payload.get("spec")
        checkpoint = payload.get("checkpoint", {})
        if not isinstance(spec, Mapping):
            continue
        meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
        topic = str(checkpoint.get("topic") or meta.get("topic") or path.name)
        runs = meta.get("context_pack_runs", []) if isinstance(meta.get("context_pack_runs"), list) else []
        for run in runs:
            if not isinstance(run, Mapping):
                continue
            score_value = run.get("context_quality_score")
            audits.append(
                ContextPackAudit(
                    checkpoint_path=path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else str(path),
                    topic=topic,
                    chapter=str(run.get("chapter", "") or ""),
                    score=safe_int(score_value, -1) if score_value is not None else None,
                    status=str(run.get("context_quality_status", "") or "unknown"),
                    evidence_gap_count=safe_int(run.get("evidence_gap_count"), 0),
                    required_kind_coverage=safe_float_or_none(run.get("required_kind_coverage")),
                    evidence_id_count=len(run.get("evidence_ids", []) or []) if isinstance(run.get("evidence_ids", []), list) else 0,
                )
            )
    return audits


def build_recommendations(
    checkpoints: Sequence[CheckpointAudit],
    inspections: Sequence[InspectionAudit],
    llm_logs: LlmLogAudit,
    context_runs: Sequence[ContextPackAudit] = (),
) -> list[str]:
    recommendations: list[str] = []
    if any(item.critical_error_count for item in checkpoints):
        recommendations.append("최신 checkpoint 중 현재 stage 기준 critical validation 오류가 있습니다. LLM 없이도 재현되는 연결성 문제이므로 우선 수정 대상입니다.")
    low_modes = Counter(item.remediation_mode for item in inspections if item.score < DEFAULT_INSPECTOR_MIN_SCORE)
    if low_modes.get("scoped_full_revision", 0) or low_modes.get("blueprint_realign_revision", 0):
        recommendations.append("과거 inspection 기준으로 patch보다 scoped/full revision이 필요한 저품질 초안 사례가 있습니다. 최근 추가한 remediation_mode 라우팅을 유지하는 편이 안전합니다.")
    if sum(item.actionability_issue_count for item in inspections):
        recommendations.append("과거 inspection report에는 target_path 또는 required_change가 부족한 finding이 있습니다. 새 actionability guard가 이런 피드백을 줄이는지 다음 LLM 테스트에서 비교하세요.")
    if llm_logs.errors:
        recommendations.append("LLM 로그에 request_error가 있습니다. 네트워크/인증/재시도 정책은 계속 모니터링해야 합니다.")
    low_context_runs = [item for item in context_runs if item.score is not None and item.score < 70]
    if low_context_runs:
        recommendations.append("Context Pack 품질 점수가 낮은 장이 있습니다. 해당 장은 Writer 재시도보다 Evidence 선택/근거 보강을 먼저 확인하세요.")
    if not recommendations:
        recommendations.append("오프라인 감사 기준에서 즉시 수정해야 할 구조적 위험은 크지 않습니다.")
    return recommendations


def spec_counts(spec: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in COUNT_FIELDS:
        value = spec.get(field)
        counts[field] = len(value) if isinstance(value, list) else (1 if isinstance(value, Mapping) and value else 0)
    return counts


def looks_finalish(spec: Mapping[str, Any]) -> bool:
    return bool(spec.get("policy_details")) and bool(spec.get("functions")) and bool(spec.get("processes"))


def spec_with_default_keys(spec: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(spec)
    for field in COUNT_FIELDS:
        normalized.setdefault(field, [])
    normalized.setdefault("meta", {})
    normalized.setdefault("overview", {})
    normalized.setdefault("final_check", [])
    return normalized


def checkpoint_scope(checkpoint: Mapping[str, Any]) -> str:
    stage_key = str(checkpoint.get("stage_key", "") or "")
    stage_name = str(checkpoint.get("stage_name", "") or "")
    value = f"{stage_key} {stage_name}".casefold()
    if "finalize" in value or "final" in value:
        return "full"
    mapping = (
        ("terms_refinement", "09_policies"),
        ("process_detail", "09_process_detail"),
        ("function_detail", "09_function_detail"),
        ("usecase_diagram", "05_usecase_diagram"),
        ("overview", "01_overview"),
        ("terms", "02_terms"),
        ("actors", "03_actors"),
        ("usecases", "04_usecases"),
        ("state", "06_state"),
        ("process", "07_process"),
        ("functions", "08_functions"),
        ("policies", "09_policies"),
    )
    for key, scope in mapping:
        if key in value:
            return scope
    return ""


def finding_from_dict(item: Mapping[str, Any]) -> InspectionFinding:
    return InspectionFinding(
        severity=str(item.get("severity", "warn") or "warn"),
        category=str(item.get("category", "검수") or "검수"),
        title=str(item.get("title", "검수 항목") or "검수 항목"),
        detail=str(item.get("detail", "") or ""),
        recommendation=str(item.get("recommendation", "") or ""),
        finding_id=str(item.get("finding_id", "") or ""),
        tier=str(item.get("tier", "") or ""),
        is_quality_gate=bool(item.get("is_quality_gate", False)),
        target_path=str(item.get("target_path", "") or ""),
        fix_owner=str(item.get("fix_owner", "current_chapter") or "current_chapter"),
        upstream_chapter=str(item.get("upstream_chapter", "") or ""),
        root_cause=str(item.get("root_cause", "") or ""),
        required_change=str(item.get("required_change", "") or ""),
        patch_hint=str(item.get("patch_hint", "") or ""),
        acceptance_check=str(item.get("acceptance_check", "") or ""),
        keep_constraints=str(item.get("keep_constraints", "") or ""),
        do_not_change=str(item.get("do_not_change", "") or ""),
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            yield item


def topic_from_inspection_path(path: Path) -> str:
    name = path.name
    if ".html_" in name:
        return name.split(".html_", 1)[0]
    return name.rsplit("_", 1)[0]


def normalize_error(error: str) -> str:
    text = " ".join(error.split())
    if len(text) > 140:
        text = text[:137].rstrip() + "..."
    return text or "unknown"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_audit_files(report: Mapping[str, Any], reports_root: Path = REPORTS_ROOT) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / "offline_quality_audit.json"
    md_path = reports_root / "offline_quality_audit.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Offline Quality Audit",
        "",
        f"- generated_at: {report.get('generatedAt', '-')}",
        f"- min_score: {report.get('minScore', '-')}",
        "",
        "## Summary",
        "",
        f"- checkpoints: {summary.get('checkpointCount', 0)}",
        f"- inspection_reports: {summary.get('inspectionReportCount', 0)}",
        f"- low_score_inspections: {summary.get('lowScoreInspections', 0)}",
        f"- validation_error_checkpoints: {summary.get('validationErrorCheckpoints', 0)}",
        f"- critical_error_checkpoints: {summary.get('criticalErrorCheckpoints', 0)}",
        f"- llm_log_rows: {summary.get('llmLogRows', 0)}",
        f"- llm_errors: {summary.get('llmErrors', 0)}",
        f"- context_pack_runs: {summary.get('contextPackRunCount', 0)}",
        f"- low_context_quality_runs: {summary.get('lowContextQualityRuns', 0)}",
        "",
        "## Remediation Mode Counts",
        "",
    ]
    for mode, count in sorted((report.get("inspectionModeCounts") or {}).items()):
        lines.append(f"- {mode}: {count}")
    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Lowest Inspection Scores", ""])
    inspections = sorted(report.get("inspections", []), key=lambda item: int(item.get("score", 0)))[:10]
    for item in inspections:
        lines.append(
            f"- {item.get('score')}점 / {item.get('scope')} / {item.get('remediation_mode')} / {item.get('path')}"
        )
    lines.extend(["", "## Lowest Context Pack Quality", ""])
    context_runs = [
        item
        for item in report.get("contextPackRuns", [])
        if isinstance(item, Mapping) and item.get("score") is not None
    ]
    for item in sorted(context_runs, key=lambda row: int(row.get("score", 0)))[:10]:
        lines.append(
            f"- {item.get('score')}점 / {item.get('status')} / {item.get('topic')} / {item.get('chapter')} / gaps={item.get('evidence_gap_count', 0)}"
        )
    lines.extend(["", "## Checkpoint Validation Samples", ""])
    for item in [row for row in report.get("checkpoints", []) if row.get("validation_error_count") or row.get("critical_error_count")][:10]:
        lines.append(f"- {item.get('topic')} / {item.get('stage')}: {item.get('sample_errors')}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LLM-free quality audit against generated artifacts.")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--reports-root", type=Path, default=REPORTS_ROOT)
    parser.add_argument("--min-score", type=int, default=DEFAULT_INSPECTOR_MIN_SCORE)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    report = run_offline_quality_audit(output_root=args.output_root, reports_root=args.reports_root, min_score=args.min_score)
    if not args.no_write:
        json_path, md_path = write_audit_files(report, args.reports_root)
        print(f"Wrote {json_path}")
        print(f"Wrote {md_path}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
