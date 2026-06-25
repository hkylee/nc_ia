#!/usr/bin/env python3
"""Refresh requirement source excerpts embedded in generated policy specs.

The authoring pipeline stores requirement cards inside ``*_spec.json`` files so
agents can reuse prior evidence without rereading the workbook every time. When
the requirement database column mapping changes, those embedded cards must be
rehydrated from the current database; otherwise later agents can keep seeing
stale ``상위 요구: <ID>`` evidence even after the DB is fixed.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from policy_graph import build_policy_graph  # noqa: E402
from policy_requirements import (  # noqa: E402
    DEFAULT_REQUIREMENTS_DB_PATH,
    clean_text,
    ensure_requirements_database,
)
from runtime_paths import POLICY_GRAPH_DB_PATH  # noqa: E402


@dataclass(frozen=True)
class RequirementRecord:
    source_number: str
    requirement_id: str
    parent_name: str
    parent_description: str
    detail_id: str
    detail_name: str
    detail_description: str

    @property
    def title(self) -> str:
        return self.detail_name or self.parent_name or self.detail_id or self.requirement_id

    @property
    def summary(self) -> str:
        return join_text(self.parent_description, self.detail_description) or self.title

    @property
    def source_excerpt(self) -> str:
        sections = []
        parent = join_text(self.parent_name, self.parent_description)
        detail = join_text(self.detail_name, self.detail_description)
        if parent:
            sections.append(f"상위 요구: {parent}")
        if detail:
            sections.append(f"세부 요구: {detail}")
        return " ".join(sections) or self.summary


def join_text(*parts: str) -> str:
    return " ".join(part for part in (clean_text(value) for value in parts) if part)


def normalize_requirement_ref(value: Any) -> str:
    text = clean_text(value)
    if text.startswith("REQ-"):
        text = text[4:]
    return text


def load_requirement_records(
    db_path: Path,
) -> tuple[
    dict[str, RequirementRecord],
    dict[tuple[str, str], RequirementRecord],
    dict[str, RequirementRecord],
    dict[str, str],
]:
    ensure_requirements_database(database_path=db_path)
    by_id: dict[str, RequirementRecord] = {}
    by_parent_title: dict[tuple[str, str], RequirementRecord] = {}
    by_unique_title: dict[str, RequirementRecord] = {}
    title_counts: dict[str, int] = {}
    parent_labels: dict[str, str] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT source_number, requirement_id, parent_name, parent_description, detail_id, detail_name, detail_description
            FROM requirement_rows
            WHERE COALESCE(detail_name, '') <> ''
               OR COALESCE(detail_description, '') <> ''
            """
        ).fetchall()

    for row in rows:
        record = RequirementRecord(
            source_number=clean_text(row["source_number"]),
            requirement_id=clean_text(row["requirement_id"]),
            parent_name=clean_text(row["parent_name"]),
            parent_description=clean_text(row["parent_description"]),
            detail_id=clean_text(row["detail_id"]),
            detail_name=clean_text(row["detail_name"]),
            detail_description=clean_text(row["detail_description"]),
        )
        for key in (
            record.source_number,
            record.detail_id,
            f"REQ-{record.detail_id}" if record.detail_id else "",
        ):
            if key:
                by_id[key] = record
        if record.requirement_id and record.detail_name:
            by_parent_title[(record.requirement_id, record.detail_name)] = record
        if record.detail_name:
            title_counts[record.detail_name] = title_counts.get(record.detail_name, 0) + 1
            by_unique_title[record.detail_name] = record
        if record.requirement_id and record.parent_name:
            parent_labels[record.requirement_id] = record.parent_name
    by_unique_title = {title: record for title, record in by_unique_title.items() if title_counts.get(title) == 1}
    return by_id, by_parent_title, by_unique_title, parent_labels


def record_for_node(
    node: Mapping[str, Any],
    by_id: Mapping[str, RequirementRecord],
    by_parent_title: Mapping[tuple[str, str], RequirementRecord],
    by_unique_title: Mapping[str, RequirementRecord],
) -> RequirementRecord | None:
    for key in ("detail_id", "id", "requirement_id", "source_id", "requirement_no", "source_number"):
        ref = normalize_requirement_ref(node.get(key))
        if ref in by_id:
            return by_id[ref]
    parent_ref = normalize_requirement_ref(node.get("requirement_id"))
    title = clean_text(node.get("title") or node.get("name"))
    if parent_ref and title:
        return by_parent_title.get((parent_ref, title))
    for key in ("requirement_name", "title", "name"):
        title_ref = clean_text(node.get(key))
        if title_ref in by_unique_title:
            return by_unique_title[title_ref]
    return None


def refresh_requirement_node(node: dict[str, Any], record: RequirementRecord) -> bool:
    changed = False
    replacements = {
        "title": record.title,
        "summary": record.summary,
        "source_excerpt": record.source_excerpt,
        "parent_name": record.parent_name,
        "parent_description": record.parent_description,
        "detail_id": record.detail_id,
        "detail_name": record.detail_name,
        "detail_description": record.detail_description,
    }
    current_requirement_id = node.get("requirement_id")
    if "requirement_id" in node and not clean_text(current_requirement_id) and record.detail_id:
        node["requirement_id"] = record.detail_id
        changed = True
    for key, value in replacements.items():
        if key in node and node.get(key) != value:
            node[key] = value
            changed = True
    return changed


def remove_excel_error_markers(text: str) -> str:
    return re.sub(r"\s*(?:#REF!|#N/A|#VALUE!|#DIV/0!|#NAME\\?|#NULL!|#NUM!)\s*", " ", text).strip()


def replace_parent_refs(
    text: str,
    parent_labels: Mapping[str, str],
    by_id: Mapping[str, RequirementRecord],
) -> str:
    def replace(match: re.Match[str]) -> str:
        requirement_id = match.group(1)
        parent_name = parent_labels.get(requirement_id)
        if not parent_name:
            return match.group(0)
        return f"상위 요구: {parent_name}"

    replaced = remove_excel_error_markers(text)
    replaced = re.sub(r"상위 요구:\s*([0-9A-Za-z][0-9A-Za-z_-]*)", replace, replaced)
    if "상위 요구:" in replaced:
        id_match = re.match(r"\s*(?:REQ-)?([0-9A-Za-z][0-9A-Za-z_-]*-\d{3})\b", replaced)
        if id_match:
            record = by_id.get(id_match.group(1))
            if record and re.search(r"상위 요구:\s*[0-9A-Za-z][0-9A-Za-z_-]*…", replaced):
                prefix = replaced.split("상위 요구:", 1)[0].rstrip()
                replaced = f"{prefix} {record.source_excerpt}".strip()
    return replaced


def walk_and_refresh(
    value: Any,
    by_id: Mapping[str, RequirementRecord],
    by_parent_title: Mapping[tuple[str, str], RequirementRecord],
    by_unique_title: Mapping[str, RequirementRecord],
    parent_labels: Mapping[str, str],
) -> int:
    updates = 0
    if isinstance(value, dict):
        record = record_for_node(value, by_id, by_parent_title, by_unique_title)
        if record and refresh_requirement_node(value, record):
            updates += 1
        for key, child in list(value.items()):
            if isinstance(child, str):
                replaced = replace_parent_refs(child, parent_labels, by_id)
                if replaced != child:
                    value[key] = replaced
                    updates += 1
            else:
                updates += walk_and_refresh(child, by_id, by_parent_title, by_unique_title, parent_labels)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                replaced = replace_parent_refs(child, parent_labels, by_id)
                if replaced != child:
                    value[index] = replaced
                    updates += 1
            else:
                updates += walk_and_refresh(child, by_id, by_parent_title, by_unique_title, parent_labels)
    return updates


def spec_topic(spec: Mapping[str, Any], fallback: str = "") -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    return clean_text(meta.get("topic_display") or meta.get("topic") or spec.get("topic") or fallback)


def iter_spec_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if path.is_dir():
            result.extend(sorted(path.rglob("*_spec.json")))
        elif path.is_file() and path.name.endswith("_spec.json"):
            result.append(path)
    return sorted(dict.fromkeys(result))


def iter_repair_paths(paths: Iterable[Path], *, include_checkpoints: bool = False) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if path.is_dir():
            result.extend(sorted(path.rglob("*_spec.json")))
            if include_checkpoints:
                result.extend(sorted(path.rglob("*_checkpoint.json")))
        elif path.is_file():
            if path.name.endswith("_spec.json") or (include_checkpoints and path.name.endswith("_checkpoint.json")):
                result.append(path)
    return sorted(dict.fromkeys(result))


def repair_specs(
    spec_paths: Iterable[Path],
    db_path: Path,
    *,
    dry_run: bool = False,
    include_checkpoints: bool = False,
) -> dict[str, Any]:
    by_id, by_parent_title, by_unique_title, parent_labels = load_requirement_records(db_path)
    files = []
    scanned = 0
    total_updates = 0
    for path in iter_repair_paths(spec_paths, include_checkpoints=include_checkpoints):
        scanned += 1
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            files.append({"path": str(path), "error": str(exc), "updates": 0})
            continue
        updates = walk_and_refresh(spec, by_id, by_parent_title, by_unique_title, parent_labels)
        if updates and not dry_run:
            path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if updates:
            files.append({"path": str(path), "updates": updates})
            total_updates += updates
    return {
        "scanned_files": scanned,
        "changed_files": len([item for item in files if item.get("updates")]),
        "total_updates": total_updates,
        "files": files,
    }


def rebuild_graph(spec_paths: Iterable[Path], graph_db_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    paths = iter_spec_paths(spec_paths)
    if dry_run:
        return {"db_path": str(graph_db_path), "rebuilt": False, "spec_files": len(paths), "documents": []}
    if graph_db_path.exists():
        graph_db_path.unlink()
    documents = []
    errors = []
    for path in paths:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            result = build_policy_graph(spec, topic=spec_topic(spec, path.stem), graph_db_path=graph_db_path)
            documents.append({"path": str(path), **result.to_dict()})
        except Exception as exc:  # pragma: no cover - operational report path.
            errors.append({"path": str(path), "error": str(exc)})
    return {
        "db_path": str(graph_db_path),
        "rebuilt": True,
        "spec_files": len(paths),
        "documents": documents,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[PROJECT_ROOT / "output"],
        help="Spec files or directories to repair. Defaults to output/.",
    )
    parser.add_argument("--requirements-db", type=Path, default=DEFAULT_REQUIREMENTS_DB_PATH)
    parser.add_argument("--graph-db", type=Path, default=POLICY_GRAPH_DB_PATH)
    parser.add_argument("--rebuild-graph", action="store_true")
    parser.add_argument(
        "--include-checkpoints",
        action="store_true",
        help="Also repair historical *_checkpoint.json files. Graph rebuild still uses *_spec.json files only.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_paths = [path if path.is_absolute() else PROJECT_ROOT / path for path in args.paths]
    db_path = args.requirements_db if args.requirements_db.is_absolute() else PROJECT_ROOT / args.requirements_db
    graph_path = args.graph_db if args.graph_db.is_absolute() else PROJECT_ROOT / args.graph_db
    report = {
        "repair": repair_specs(
            spec_paths,
            db_path,
            dry_run=args.dry_run,
            include_checkpoints=args.include_checkpoints,
        ),
    }
    if args.rebuild_graph:
        report["policy_graph"] = rebuild_graph(spec_paths, graph_path, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
