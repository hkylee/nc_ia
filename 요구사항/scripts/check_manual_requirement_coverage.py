#!/usr/bin/env python3
"""Validate topic-level requirement coverage for manual authoring outputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_manual_requirement_trace import build_trace_elements, match_requirement
from src.policy_requirements import load_scoped_requirements_for_topic


QUEUE_PATH = PROJECT_ROOT / "reports" / "manual_authoring" / "manual_authoring_queue.json"


@dataclass(frozen=True)
class CoverageResult:
    module_id: str
    topic: str
    db_count: int
    queue_count: int
    matched_count: int
    review_count: int
    trace_count: int
    trace_path: str
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH, help="Manual authoring queue JSON path.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    results = check_queue(args.queue)
    if args.json:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    else:
        print_summary(results)
    return 0 if all(result.ok for result in results) else 1


def check_queue(queue_path: Path) -> list[CoverageResult]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    return [check_item(item) for item in queue.get("items", []) if isinstance(item, dict)]


def check_item(item: dict) -> CoverageResult:
    module_id = str(item.get("module_id", "")).strip()
    topic = str(item.get("topic", "")).strip()
    issues: list[str] = []

    requirements = load_scoped_requirements_for_topic(topic)
    queue_count = int(item.get("detail_requirement_count", 0) or 0)
    if len(requirements) != queue_count:
        issues.append(f"requirements_count_mismatch: db={len(requirements)} queue={queue_count}")

    spec_path = first_existing_path(item.get("spec"), item.get("spec_path"))
    spec: dict = {}
    if not spec_path:
        issues.append("missing_spec")
    else:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

    trace_path = first_existing_path(item.get("trace"), item.get("trace_path"))
    if not trace_path:
        issues.append("missing_trace_report")
    else:
        issues.extend(trace_report_issues(trace_path))

    elements = build_trace_elements(spec)
    matched = 0
    review = 0
    for requirement in requirements:
        if match_requirement(requirement, elements):
            matched += 1
        else:
            review += 1
    if review:
        issues.append(f"unmatched_requirements={review}")

    return CoverageResult(
        module_id=module_id,
        topic=topic,
        db_count=len(requirements),
        queue_count=queue_count,
        matched_count=matched,
        review_count=review,
        trace_count=len(spec.get("trace_matrix") or []),
        trace_path=str(trace_path.relative_to(PROJECT_ROOT)) if trace_path else "",
        issues=tuple(issues),
    )


def trace_report_issues(trace_path: Path) -> list[str]:
    text = trace_path.read_text(encoding="utf-8")
    coverage = re.search(r"커버리지:\s*([0-9]+)\s*/\s*([0-9]+)", text)
    if coverage:
        covered, total = map(int, coverage.groups())
        return [] if covered == total else [f"trace_coverage_mismatch: {covered}/{total}"]

    auto = re.search(r"자동 매칭:\s*([0-9]+)", text)
    review = re.search(r"수동 검토 필요:\s*([0-9]+)", text)
    if auto and review:
        review_count = int(review.group(1))
        return [] if review_count == 0 else [f"trace_review_required={review_count}"]

    return ["trace_coverage_marker_missing"]


def first_existing_path(*values: object) -> Path | None:
    for value in values:
        if not value:
            continue
        path = PROJECT_ROOT / str(value)
        if path.exists() and path.is_file():
            return path
    return None


def print_summary(results: Iterable[CoverageResult]) -> None:
    results = list(results)
    print("| ID | 주제 | DB | Queue | 매칭 | 검토필요 | trace행 | 상태 |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    for result in results:
        status = "OK" if result.ok else "; ".join(result.issues)
        print(
            f"| {result.module_id} | {result.topic} | {result.db_count} | {result.queue_count} | "
            f"{result.matched_count} | {result.review_count} | {result.trace_count} | {status} |"
        )
    total = sum(result.db_count for result in results)
    matched = sum(result.matched_count for result in results)
    review = sum(result.review_count for result in results)
    print(f"TOTAL requirements={total} matched={matched} review={review}")


if __name__ == "__main__":
    raise SystemExit(main())
