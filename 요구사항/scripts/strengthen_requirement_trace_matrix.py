#!/usr/bin/env python3
"""Add detail-level requirement mappings to policy spec trace_matrix rows.

The policy document body should stay concise.  Requirement traceability belongs
in spec metadata so graph, inspector, health check, and downstream agents can
verify every detailed requirement without turning the HTML into a requirements
dump.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(0, str(PROJECT_ROOT))

from policy_graph import build_policy_graph, requirement_coverage_gaps  # noqa: E402
from policy_requirements import RequirementItem, load_scoped_requirements_for_topic  # noqa: E402


QUEUE_PATH = PROJECT_ROOT / "reports" / "manual_authoring" / "manual_authoring_queue.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "requirement_trace_matrix_strengthening_20260516.json"

TARGET_LIST_KEYS = (
    "usecases",
    "states",
    "state_transitions",
    "processes",
    "functions",
    "policy_details",
    "policy_groups",
)


@dataclass(frozen=True)
class TargetCandidate:
    item_type: str
    item_id: str
    name: str
    text: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "output")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument(
        "--all-output-versions",
        action="store_true",
        help="Update every direct output spec for gap topics, not only queue canonical specs.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    gap_topics = detect_gap_topics(items)
    changed_files: list[dict[str, Any]] = []

    for item in items:
        topic = str(item.get("topic", "")).strip()
        if topic not in gap_topics:
            continue
        spec_paths = spec_paths_for_item(item, args.output_root, include_all_versions=args.all_output_versions)
        requirements = load_scoped_requirements_for_topic(topic)
        for spec_path in spec_paths:
            result = strengthen_spec_file(spec_path, topic, requirements, dry_run=args.dry_run)
            if result:
                changed_files.append(result)

    report = {
        "gap_topic_count": len(gap_topics),
        "gap_topics": gap_topics,
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def detect_gap_topics(items: Sequence[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    for item in items:
        topic = str(item.get("topic", "")).strip()
        spec_path = PROJECT_ROOT / str(item.get("spec") or item.get("spec_path") or "")
        if not topic or not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        requirements = load_scoped_requirements_for_topic(topic)
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "policy_graph.db"
            build = build_policy_graph(spec, topic=topic, requirements=requirements, graph_db_path=graph_path)
            if build.coverage_gap_count > 0:
                result.append(topic)
    return result


def spec_paths_for_item(item: Mapping[str, Any], output_root: Path, *, include_all_versions: bool) -> list[Path]:
    paths: list[Path] = []
    canonical = PROJECT_ROOT / str(item.get("spec") or item.get("spec_path") or "")
    if canonical.exists():
        paths.append(canonical)
    if include_all_versions:
        topic_slug = canonical.name.removesuffix("_policy_spec.json") if canonical.name.endswith("_policy_spec.json") else ""
        if topic_slug:
            paths.extend(sorted(output_root.glob(f"NC_{topic_slug}_정책서_*_v*_spec.json")))
    return unique_paths(paths)


def strengthen_spec_file(
    spec_path: Path,
    topic: str,
    requirements: Sequence[RequirementItem],
    *,
    dry_run: bool,
) -> dict[str, Any] | None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    before_rows = len(spec.get("trace_matrix") or [])
    before_gap = graph_gap_count(spec, topic, requirements)
    if before_gap == 0:
        return None

    candidates = build_target_candidates(spec)
    rows = list(spec.get("trace_matrix") or [])
    existing_keys = trace_existing_keys(rows)
    added = 0
    updated = 0

    for requirement in requirements:
        canonical_key = requirement.detail_id or requirement.source_number
        row_index = find_trace_row_index(rows, requirement)
        target_ids = select_target_ids(requirement, candidates)
        trace_row = build_trace_row(requirement, target_ids)
        if row_index is not None:
            merged = merge_trace_row(rows[row_index], trace_row)
            if merged != rows[row_index]:
                rows[row_index] = merged
                updated += 1
            continue
        if canonical_key in existing_keys:
            continue
        rows.append(trace_row)
        existing_keys.add(canonical_key)
        added += 1

    spec["trace_matrix"] = rows
    after_gap = graph_gap_count(spec, topic, requirements)
    if not dry_run:
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "path": str(spec_path.relative_to(PROJECT_ROOT)),
        "topic": topic,
        "before_rows": before_rows,
        "after_rows": len(rows),
        "added_rows": added,
        "updated_rows": updated,
        "before_gap": before_gap,
        "after_gap": after_gap,
    }


def graph_gap_count(spec: Mapping[str, Any], topic: str, requirements: Sequence[RequirementItem]) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        graph_path = Path(tmp) / "policy_graph.db"
        result = build_policy_graph(spec, topic=topic, requirements=requirements, graph_db_path=graph_path)
        return result.coverage_gap_count


def build_target_candidates(spec: Mapping[str, Any]) -> list[TargetCandidate]:
    result: list[TargetCandidate] = []
    for key in TARGET_LIST_KEYS:
        for row in spec.get(key, []) if isinstance(spec.get(key), list) else []:
            if not isinstance(row, Mapping):
                continue
            item_id = str(row.get("id") or row.get("state_id") or row.get("transition_id") or "").strip()
            if not item_id:
                continue
            name = str(row.get("name") or row.get("title") or row.get("event") or item_id).strip()
            result.append(
                TargetCandidate(
                    item_type=key.removesuffix("s"),
                    item_id=item_id,
                    name=name,
                    text=normalize(" ".join(flatten_text(row))),
                )
            )
    return result


def select_target_ids(requirement: RequirementItem, candidates: Sequence[TargetCandidate]) -> list[str]:
    query_tokens = important_tokens(
        " ".join(
            [
                requirement.detail_id,
                requirement.requirement_id,
                requirement.parent_name,
                requirement.detail_name,
                requirement.parent_description,
                requirement.detail_description,
            ]
        )
    )
    preferred = preferred_item_types(requirement)
    scored: list[tuple[int, int, TargetCandidate]] = []
    for candidate in candidates:
        score = 0
        if normalize(requirement.detail_name) and normalize(requirement.detail_name) in candidate.text:
            score += 60
        if normalize(requirement.parent_name) and normalize(requirement.parent_name) in candidate.text:
            score += 24
        if normalize(requirement.requirement_id) and normalize(requirement.requirement_id) in candidate.text:
            score += 20
        for token in query_tokens:
            if token in normalize(candidate.name):
                score += 4
            elif token in candidate.text:
                score += 2
        if candidate.item_type in preferred:
            score += 3
        if score:
            scored.append((score, type_rank(candidate.item_type), candidate))
    scored.sort(key=lambda item: (-item[0], item[1], item[2].item_id))
    selected = [candidate.item_id for _score, _rank, candidate in scored[:5]]
    if selected:
        return selected
    for item_type in preferred + ["policy_detail", "function", "process", "policy_group", "usecase"]:
        for candidate in candidates:
            if candidate.item_type == item_type:
                return [candidate.item_id]
    return []


def build_trace_row(requirement: RequirementItem, target_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "item_type": "requirement",
        "item_id": requirement.detail_id,
        "source_number": requirement.source_number,
        "requirement_id": requirement.detail_id,
        "parent_requirement_id": requirement.requirement_id,
        "parent_name": requirement.parent_name,
        "detail_name": requirement.detail_name,
        "requirement_type": requirement.requirement_type,
        "priority": requirement.priority,
        "mapped_to": list(target_ids),
        "mapping_type": mapping_type(target_ids),
        "coverage": "Y",
        "rationale": "상세 요구사항명과 설명을 정책서 산출물의 유즈케이스, 프로세스, 기능, 정책 또는 정책 항목에 직접 연결했다.",
        "evidence_ids": unique_texts([requirement.detail_id, requirement.source_number, f"REQ-{requirement.detail_id}"]),
    }


def merge_trace_row(current: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(current)
    for key in (
        "source_number",
        "requirement_id",
        "parent_requirement_id",
        "parent_name",
        "detail_name",
        "requirement_type",
        "priority",
        "coverage",
    ):
        if not str(result.get(key, "") or "").strip() and incoming.get(key):
            result[key] = incoming[key]
    result["evidence_ids"] = unique_texts([*list_values(result.get("evidence_ids")), *list_values(incoming.get("evidence_ids"))])
    result["mapped_to"] = unique_texts([*list_values(result.get("mapped_to")), *list_values(incoming.get("mapped_to"))])
    if not str(result.get("mapping_type", "") or "").strip():
        result["mapping_type"] = incoming.get("mapping_type", "")
    if not str(result.get("rationale", "") or "").strip():
        result["rationale"] = incoming.get("rationale", "")
    return result


def trace_existing_keys(rows: Sequence[Any]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in ("requirement_id", "detail_id", "source_number", "requirement_no", "item_id"):
            value = row.get(key)
            if str(value or "").strip():
                result.add(str(value).strip())
        for value in list_values(row.get("evidence_ids")):
            result.add(str(value).strip())
    return result


def find_trace_row_index(rows: Sequence[Any], requirement: RequirementItem) -> int | None:
    aliases = {
        normalize_key(requirement.detail_id),
        normalize_key(requirement.source_number),
        normalize_key(f"REQ-{requirement.detail_id}"),
        normalize_key(requirement.detail_name),
    }
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        values: list[str] = []
        for key in ("requirement_id", "detail_id", "source_number", "requirement_no", "item_id", "item_name", "detail_name", "source"):
            if row.get(key) is not None:
                values.append(str(row.get(key)))
        values.extend(list_values(row.get("evidence_ids")))
        if aliases & {normalize_key(value) for value in values}:
            return index
    return None


def preferred_item_types(requirement: RequirementItem) -> list[str]:
    text = f"{requirement.requirement_type} {requirement.detail_name} {requirement.detail_description}"
    if any(token in text for token in ("정책", "비기능", "기준", "권한", "보안", "이력")):
        return ["policy_detail", "policy_group", "function", "process", "usecase"]
    if any(token in text for token in ("상태", "전이", "단계")):
        return ["state_transition", "state", "process", "function", "policy_detail"]
    return ["function", "process", "policy_detail", "policy_group", "usecase"]


def mapping_type(target_ids: Sequence[str]) -> str:
    first = next((target for target in target_ids if target), "")
    if first.startswith("PI-"):
        return "policy_item"
    if first.startswith("PG-"):
        return "policy"
    if first.startswith("FN-"):
        return "function"
    if first.startswith("PR-"):
        return "process"
    if first.startswith("US-"):
        return "usecase"
    if first.startswith("ST-"):
        return "state"
    return "artifact"


def type_rank(item_type: str) -> int:
    return {
        "policy_detail": 0,
        "function": 1,
        "process": 2,
        "policy_group": 3,
        "usecase": 4,
        "state_transition": 5,
        "state": 6,
    }.get(item_type, 9)


def important_tokens(text: str) -> list[str]:
    stopwords = {
        "고객",
        "서비스",
        "정책",
        "기준",
        "관리",
        "처리",
        "확인",
        "제공",
        "조회",
        "정보",
        "업무",
        "기능",
        "화면",
        "채널",
        "상세",
        "목록",
        "운영",
        "설정",
        "사용",
        "지원",
        "연계",
        "결과",
        "데이터",
    }
    result: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[가-힣A-Za-z0-9]+", normalize(text)):
        if len(token) < 2 or token in stopwords or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result[:20]


def flatten_text(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        result: list[str] = []
        for child in value.values():
            result.extend(flatten_text(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(flatten_text(child))
        return result
    return [str(value)]


def list_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, dict):
        return [str(value).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


def normalize_key(text: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(text or "")).casefold()


def unique_texts(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def unique_paths(paths: Sequence[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        result.append(path)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
