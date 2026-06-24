#!/usr/bin/env python3
"""Sync requirement DB mapping status from authored policy trace outputs."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.build_manual_requirement_trace import TraceElement, build_trace_elements, flatten_text, match_requirement  # noqa: E402
from src.policy_requirements import DEFAULT_REQUIREMENTS_DB_PATH, RequirementItem, load_scoped_requirements_for_topic  # noqa: E402


DEFAULT_QUEUE_PATH = PROJECT_ROOT / "reports" / "manual_authoring" / "manual_authoring_queue.json"


@dataclass(frozen=True)
class TopicSyncResult:
    module_id: str
    topic: str
    total: int
    mapped: int
    review: int
    skipped: int
    spec: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--requirements-db", type=Path, default=DEFAULT_REQUIREMENTS_DB_PATH)
    parser.add_argument("--mapped-label", default="반영 완료")
    parser.add_argument("--review-label", default="검토 필요")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue_path = absolute_path(args.queue)
    db_path = absolute_path(args.requirements_db)
    results = sync_mapping_status(
        queue_path=queue_path,
        db_path=db_path,
        mapped_label=args.mapped_label,
        review_label=args.review_label,
        dry_run=args.dry_run,
    )
    report = {
        "requirements_db": str(db_path.relative_to(PROJECT_ROOT) if db_path.is_relative_to(PROJECT_ROOT) else db_path),
        "queue": str(queue_path.relative_to(PROJECT_ROOT) if queue_path.is_relative_to(PROJECT_ROOT) else queue_path),
        "topic_count": len(results),
        "total": sum(item.total for item in results),
        "mapped": sum(item.mapped for item in results),
        "review": sum(item.review for item in results),
        "skipped": sum(item.skipped for item in results),
        "dry_run": args.dry_run,
        "topics": [item.__dict__ for item in results],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["review"] == 0 and report["skipped"] == 0 else 1


def sync_mapping_status(
    *,
    queue_path: Path,
    db_path: Path,
    mapped_label: str,
    review_label: str,
    dry_run: bool,
) -> list[TopicSyncResult]:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    items = [item for item in queue.get("items", []) if isinstance(item, dict)]
    updates: dict[str, str] = {}
    results: list[TopicSyncResult] = []

    for item in items:
        result, topic_updates = mapping_status_for_queue_item(item, mapped_label=mapped_label, review_label=review_label)
        results.append(result)
        updates.update(topic_updates)

    if not dry_run:
        apply_mapping_status_updates(db_path, updates, review_label=review_label)
    return results


def mapping_status_for_queue_item(
    item: Mapping[str, Any],
    *,
    mapped_label: str,
    review_label: str,
) -> tuple[TopicSyncResult, dict[str, str]]:
    module_id = str(item.get("module_id") or "").strip()
    topic = str(item.get("topic") or "").strip()
    spec_path = first_existing_path(item.get("spec"), item.get("spec_path"))
    requirements = load_scoped_requirements_for_topic(topic) if topic else []
    updates: dict[str, str] = {}
    mapped = 0
    review = 0
    skipped = 0

    if not spec_path:
        skipped = len(requirements)
        for requirement in requirements:
            if requirement.detail_id:
                updates[requirement.detail_id] = review_label
        return (
            TopicSyncResult(
                module_id=module_id,
                topic=topic,
                total=len(requirements),
                mapped=0,
                review=0,
                skipped=skipped,
                spec="",
            ),
            updates,
        )

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    elements = build_trace_elements(spec)
    for requirement in requirements:
        if not requirement.detail_id:
            skipped += 1
            continue
        matches = match_requirement(requirement, elements)
        status = (
            detailed_mapping_status(requirement, spec, topic, matches, mapped_label=mapped_label)
            if matches
            else review_label
        )
        updates[requirement.detail_id] = status
        if matches:
            mapped += 1
        else:
            review += 1

    return (
        TopicSyncResult(
            module_id=module_id,
            topic=topic,
            total=len(requirements),
            mapped=mapped,
            review=review,
            skipped=skipped,
            spec=str(spec_path.relative_to(PROJECT_ROOT) if spec_path.is_relative_to(PROJECT_ROOT) else spec_path),
        ),
        updates,
    )


def apply_mapping_status_updates(db_path: Path, updates: Mapping[str, str], *, review_label: str) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"requirements DB not found: {db_path}")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE requirement_rows
            SET policy_mapping_status = ?
            WHERE COALESCE(edit_status, '') <> '삭제'
              AND COALESCE(detail_id, '') <> ''
            """,
            (review_label,),
        )
        conn.executemany(
            """
            UPDATE requirement_rows
            SET policy_mapping_status = ?
            WHERE detail_id = ?
            """,
            [(status, detail_id) for detail_id, status in updates.items()],
        )
        conn.commit()


def detailed_mapping_status(
    requirement: RequirementItem,
    spec: Mapping[str, Any],
    topic: str,
    matches: Sequence[Any],
    *,
    mapped_label: str,
) -> str:
    item_index = build_spec_item_index(spec)
    mapped_items = mapped_items_from_trace_rows(requirement, spec, item_index)
    if not mapped_items:
        mapped_items = mapped_items_from_matches(matches, item_index)
    if not mapped_items:
        return f"{mapped_label} · {topic} 정책서"
    return f"{mapped_label} · {topic} 정책서 · {summarize_mapping_items(mapped_items)}"


def build_spec_item_index(spec: Mapping[str, Any]) -> dict[str, str]:
    definitions = [
        ("usecases", "유즈케이스", ("id",), ("name",)),
        ("states", "상태", ("id",), ("name",)),
        ("state_codes", "상태", ("id",), ("name",)),
        ("state_transitions", "상태전이", ("id", "transition_id"), ("event", "name")),
        ("processes", "프로세스", ("id",), ("name",)),
        ("functions", "기능", ("id",), ("name",)),
        ("policy_groups", "정책", ("id",), ("name",)),
        ("policy_details", "정책항목", ("id",), ("name",)),
    ]
    result: dict[str, str] = {}
    for key, type_label, id_keys, name_keys in definitions:
        for row in spec.get(key, []) if isinstance(spec.get(key), list) else []:
            if not isinstance(row, Mapping):
                continue
            item_id = first_text(row, *id_keys)
            if not item_id:
                continue
            name = first_text(row, *name_keys)
            result[item_id] = f"{type_label} {item_id}" + (f" {name}" if name else "")
    return result


def mapped_items_from_trace_rows(
    requirement: RequirementItem,
    spec: Mapping[str, Any],
    item_index: Mapping[str, str],
) -> list[str]:
    trace_rows = spec.get("trace_matrix", []) if isinstance(spec.get("trace_matrix"), list) else []
    scored: list[tuple[int, list[str]]] = []
    for row in trace_rows:
        if not isinstance(row, Mapping):
            continue
        score = trace_row_match_score(requirement, row)
        if score <= 0:
            continue
        mapped_to = row.get("mapped_to")
        mapped_ids = [str(item or "").strip() for item in mapped_to] if isinstance(mapped_to, list) else []
        mapped_items = [item_index.get(item_id, item_id) for item_id in mapped_ids if item_id]
        if mapped_items:
            scored.append((score, mapped_items))
    scored.sort(key=lambda item: -item[0])
    result: list[str] = []
    for _score, items in scored[:3]:
        result.extend(items)
    return unique_texts(result)


def trace_row_match_score(requirement: RequirementItem, row: Mapping[str, Any]) -> int:
    text = normalize(" ".join(flatten_text(row)))
    detail_id = normalize(requirement.detail_id)
    parent_id = normalize(requirement.requirement_id)
    detail_name = normalize(requirement.detail_name)
    parent_name = normalize(requirement.parent_name)
    score = 0
    if detail_id and detail_id in text:
        score += 1000
    if detail_name and detail_name in text:
        score += 80
    if parent_id and parent_id in text:
        score += 20
    if parent_name and parent_name in text:
        score += 10
    for token in important_tokens(f"{requirement.detail_name} {requirement.detail_description}"):
        if token in text:
            score += 2
    return score


def mapped_items_from_matches(matches: Sequence[Any], item_index: Mapping[str, str]) -> list[str]:
    result: list[str] = []
    for match in matches[:5]:
        element = getattr(match, "element", None)
        if not isinstance(element, TraceElement):
            continue
        identifier = str(element.identifier or "").strip()
        result.append(item_index.get(identifier, f"{type_label_for_element(element.element_type)} {identifier} {element.name}".strip()))
    return unique_texts(result)


def summarize_mapping_items(items: Sequence[str], *, limit: int = 3) -> str:
    selected = list(items[:limit])
    suffix = f" 외 {len(items) - limit}건" if len(items) > limit else ""
    return " / ".join(selected) + suffix


def type_label_for_element(element_type: str) -> str:
    return {
        "usecase": "유즈케이스",
        "state": "상태",
        "transition": "상태전이",
        "process": "프로세스",
        "function": "기능",
        "policy": "정책",
        "policy_item": "정책항목",
        "trace": "Trace",
    }.get(element_type, element_type)


def first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def unique_texts(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def important_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in normalize(text).replace("/", " ").replace("·", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum() or "\uac00" <= ch <= "\ud7a3")
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens[:12]


def normalize(value: object) -> str:
    return " ".join(str(value or "").lower().split())


def first_existing_path(*values: object) -> Path | None:
    for value in values:
        if not value:
            continue
        path = absolute_path(Path(str(value)))
        if path.exists() and path.is_file():
            return path
    return None


def absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
