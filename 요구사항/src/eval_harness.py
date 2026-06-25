"""LLM-free evaluation harness for policy-agent regression checks.

The harness compares existing generated artifacts against small scenario
expectations. It is intentionally file-based so it can run locally, in CI, or
after Render runs without triggering new LLM calls.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from offline_quality_audit import audit_checkpoints, audit_context_pack_runs, audit_inspections
    from policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE
    from runtime_paths import OUTPUT_ROOT, PROJECT_ROOT, REPORTS_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .offline_quality_audit import audit_checkpoints, audit_context_pack_runs, audit_inspections
    from .policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE
    from .runtime_paths import OUTPUT_ROOT, PROJECT_ROOT, REPORTS_ROOT


@dataclass(frozen=True)
class EvalCheck:
    name: str
    passed: bool
    expected: Any
    actual: Any
    detail: str = ""


@dataclass(frozen=True)
class EvalScenarioResult:
    id: str
    topic: str
    status: str
    checks: list[EvalCheck]
    metrics: dict[str, Any]


def run_eval_harness(
    *,
    scenarios_root: Path,
    output_root: Path = OUTPUT_ROOT,
    reports_root: Path = REPORTS_ROOT,
    min_score: int = DEFAULT_INSPECTOR_MIN_SCORE,
) -> dict[str, Any]:
    scenarios = load_scenarios(scenarios_root)
    checkpoints = audit_checkpoints(output_root / "checkpoints")
    inspections = audit_inspections(reports_root / "inspections", min_score=min_score)
    context_runs = audit_context_pack_runs(output_root / "checkpoints")
    results = [
        evaluate_scenario(
            scenario,
            checkpoints=checkpoints,
            inspections=inspections,
            context_runs=context_runs,
            min_score=min_score,
        )
        for scenario in scenarios
    ]
    failed = sum(1 for result in results if result.status != "pass")
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "scenarioRoot": safe_relative_path(scenarios_root),
        "minScore": min_score,
        "summary": {
            "scenarioCount": len(results),
            "passed": sum(1 for result in results if result.status == "pass"),
            "failed": failed,
            "hasScenarios": bool(scenarios),
        },
        "results": [
            {
                **asdict(result),
                "checks": [asdict(check) for check in result.checks],
            }
            for result in results
        ],
        "recommendations": eval_recommendations(results, bool(scenarios)),
    }


def load_scenarios(scenarios_root: Path) -> list[dict[str, Any]]:
    if not scenarios_root.exists():
        return []
    scenarios: list[dict[str, Any]] = []
    for path in sorted(scenarios_root.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, Mapping):
            scenario = dict(payload)
            scenario.setdefault("id", path.stem)
            scenarios.append(scenario)
        elif isinstance(payload, list):
            for index, item in enumerate(payload, start=1):
                if isinstance(item, Mapping):
                    scenario = dict(item)
                    scenario.setdefault("id", f"{path.stem}-{index}")
                    scenarios.append(scenario)
    return scenarios


def evaluate_scenario(
    scenario: Mapping[str, Any],
    *,
    checkpoints: Sequence[Any],
    inspections: Sequence[Any],
    min_score: int,
    context_runs: Sequence[Any] = (),
) -> EvalScenarioResult:
    scenario_id = str(scenario.get("id", "") or "scenario")
    topic = str(scenario.get("topic", "") or "").strip()
    expectations = scenario.get("expectations", {})
    if not isinstance(expectations, Mapping):
        expectations = {}
    topic_checkpoints = [item for item in checkpoints if topic_matches(item.topic, topic)]
    topic_inspections = [item for item in inspections if topic_matches(item.topic, topic)]
    topic_context_runs = [item for item in context_runs if topic_matches(item.topic, topic)]
    latest_checkpoint = topic_checkpoints[-1] if topic_checkpoints else None
    latest_inspection = topic_inspections[-1] if topic_inspections else None
    checks: list[EvalCheck] = []

    checks.append(
        EvalCheck(
            name="checkpoint_exists",
            passed=latest_checkpoint is not None,
            expected=True,
            actual=latest_checkpoint is not None,
            detail="주제에 해당하는 latest checkpoint가 있어야 합니다.",
        )
    )

    min_counts = expectations.get("min_counts", {})
    if isinstance(min_counts, Mapping):
        counts = latest_checkpoint.counts if latest_checkpoint is not None else {}
        for field, expected in min_counts.items():
            expected_int = safe_int(expected, 0)
            actual = safe_int(counts.get(str(field)), 0)
            checks.append(
                EvalCheck(
                    name=f"min_count:{field}",
                    passed=actual >= expected_int,
                    expected=expected_int,
                    actual=actual,
                )
            )

    if "max_validation_errors" in expectations:
        actual = latest_checkpoint.validation_error_count if latest_checkpoint is not None else None
        expected = safe_int(expectations.get("max_validation_errors"), 0)
        checks.append(EvalCheck("max_validation_errors", actual is not None and actual <= expected, expected, actual))

    if "max_critical_errors" in expectations:
        actual = latest_checkpoint.critical_error_count if latest_checkpoint is not None else None
        expected = safe_int(expectations.get("max_critical_errors"), 0)
        checks.append(EvalCheck("max_critical_errors", actual is not None and actual <= expected, expected, actual))

    expected_min_score = safe_int(expectations.get("min_latest_inspection_score"), min_score)
    if topic_inspections or "min_latest_inspection_score" in expectations:
        actual_score = latest_inspection.score if latest_inspection is not None else None
        checks.append(
            EvalCheck(
                "min_latest_inspection_score",
                actual_score is not None and actual_score >= expected_min_score,
                expected_min_score,
                actual_score,
            )
        )

    if "min_context_quality_score" in expectations:
        expected = safe_int(expectations.get("min_context_quality_score"), 70)
        scores = [item.score for item in topic_context_runs if item.score is not None]
        actual = min(scores) if scores else None
        checks.append(
            EvalCheck(
                "min_context_quality_score",
                actual is not None and actual >= expected,
                expected,
                actual,
                "주제의 Context Pack 품질 점수 최저값이 기준 이상이어야 합니다.",
            )
        )

    if "max_context_gap_runs" in expectations:
        expected = safe_int(expectations.get("max_context_gap_runs"), 0)
        actual = sum(1 for item in topic_context_runs if item.evidence_gap_count > 0)
        checks.append(
            EvalCheck(
                "max_context_gap_runs",
                actual <= expected,
                expected,
                actual,
                "evidence_gap이 남은 Context Pack run 수가 기준 이하여야 합니다.",
            )
        )

    metrics = {
        "checkpointCount": len(topic_checkpoints),
        "inspectionCount": len(topic_inspections),
        "contextPackRunCount": len(topic_context_runs),
        "latestCheckpointPath": latest_checkpoint.path if latest_checkpoint is not None else "",
        "latestInspectionPath": latest_inspection.path if latest_inspection is not None else "",
        "latestInspectionScore": latest_inspection.score if latest_inspection is not None else None,
        "lowestInspectionScore": min((item.score for item in topic_inspections), default=None),
        "lowestContextQualityScore": min((item.score for item in topic_context_runs if item.score is not None), default=None),
    }
    status = "pass" if checks and all(check.passed for check in checks) else "fail"
    if not checks:
        status = "no_checks"
    return EvalScenarioResult(scenario_id, topic, status, checks, metrics)


def eval_recommendations(results: Sequence[EvalScenarioResult], has_scenarios: bool) -> list[str]:
    if not has_scenarios:
        return [
            "아직 eval scenario가 없습니다. reports/eval/scenarios/*.json에 대표 정책서 주제별 기대 count와 score 기준을 추가하면 변경 전후 회귀 비교가 가능합니다."
        ]
    failed = [result for result in results if result.status != "pass"]
    if not failed:
        return ["모든 eval scenario가 기대 기준을 충족했습니다."]
    return [
        f"{len(failed)}개 eval scenario가 실패했습니다. 실패 check를 기준으로 Writer/Inspector 변경 전후 회귀 여부를 확인하세요."
    ]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def topic_matches(value: str, topic: str) -> bool:
    if not topic:
        return False
    compact_value = "".join(str(value or "").split())
    compact_topic = "".join(topic.split())
    return compact_topic in compact_value


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_relative_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def write_eval_report(report: Mapping[str, Any], reports_root: Path = REPORTS_ROOT) -> tuple[Path, Path]:
    reports_dir = reports_root / "eval"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "eval_harness_report.json"
    md_path = reports_dir / "eval_harness_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# Eval Harness Report",
        "",
        f"- generated_at: {report.get('generatedAt', '-')}",
        f"- scenarios: {summary.get('scenarioCount', 0)}",
        f"- passed: {summary.get('passed', 0)}",
        f"- failed: {summary.get('failed', 0)}",
        "",
        "## Results",
        "",
    ]
    for result in report.get("results", []) if isinstance(report.get("results", []), list) else []:
        lines.append(f"- {result.get('status')} / {result.get('topic')} / {result.get('id')}")
        for check in result.get("checks", []) if isinstance(result.get("checks", []), list) else []:
            marker = "PASS" if check.get("passed") else "FAIL"
            lines.append(f"  - {marker} {check.get('name')}: expected={check.get('expected')} actual={check.get('actual')}")
    lines.extend(["", "## Recommendations", ""])
    for item in report.get("recommendations", []) if isinstance(report.get("recommendations", []), list) else []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LLM-free eval scenarios against generated artifacts.")
    parser.add_argument("--scenarios-root", type=Path, default=REPORTS_ROOT / "eval" / "scenarios")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--reports-root", type=Path, default=REPORTS_ROOT)
    parser.add_argument("--min-score", type=int, default=DEFAULT_INSPECTOR_MIN_SCORE)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    report = run_eval_harness(
        scenarios_root=args.scenarios_root,
        output_root=args.output_root,
        reports_root=args.reports_root,
        min_score=args.min_score,
    )
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        json_path, md_path = write_eval_report(report, args.reports_root)
        print(f"Wrote {json_path}")
        print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
