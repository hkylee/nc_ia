#!/usr/bin/env python3
"""Ensure manual authoring queue entries have HTML, spec, and BPMN assets.

Manual authoring outputs are often created outside the main policy_agent flow.
This guard keeps the queue from drifting into a half-complete state where HTML
and spec exist but the BPMN artifact path is empty.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bpmn_renderer import (  # noqa: E402
    bpmn_io_viewer_path_for,
    bpmn_title_from_spec,
    build_bpmn_io_viewer_html,
    write_bpmn_artifacts,
)


DEFAULT_QUEUE = PROJECT_ROOT / "reports/manual_authoring/manual_authoring_queue.json"


@dataclass
class AssetCheckResult:
    total_items: int
    generated_bpmn: list[Path]
    generated_bpmn_viewers: list[Path]
    missing: list[str]
    xml_errors: list[str]
    history_version_errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.xml_errors and not self.history_version_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure manual authoring assets are complete.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE, help="manual_authoring_queue.json path")
    parser.add_argument("--check", action="store_true", help="Only validate. Do not generate missing BPMN files.")
    args = parser.parse_args()

    result = ensure_manual_authoring_assets(args.queue, repair=not args.check)
    print(f"queue_items={result.total_items}")
    print(f"generated_bpmn={len(result.generated_bpmn)}")
    for path in result.generated_bpmn:
        print(f"GENERATED {path}")
    print(f"generated_bpmn_viewers={len(result.generated_bpmn_viewers)}")
    for path in result.generated_bpmn_viewers:
        print(f"GENERATED_VIEWER {path}")
    print(f"missing={len(result.missing)}")
    for message in result.missing:
        print(f"MISSING {message}")
    print(f"xml_errors={len(result.xml_errors)}")
    for message in result.xml_errors:
        print(f"XML_ERROR {message}")
    print(f"history_version_errors={len(result.history_version_errors)}")
    for message in result.history_version_errors:
        print(f"HISTORY_VERSION_ERROR {message}")
    return 0 if result.ok else 1


def ensure_manual_authoring_assets(queue_path: Path, repair: bool = True) -> AssetCheckResult:
    queue_path = queue_path.resolve()
    root = queue_path.parents[2] if queue_path.name == "manual_authoring_queue.json" else PROJECT_ROOT
    data = json.loads(queue_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"Unsupported queue format: {queue_path}")

    generated: list[Path] = []
    generated_viewers: list[Path] = []
    missing: list[str] = []
    xml_errors: list[str] = []
    history_version_errors: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("module_id") or item.get("id") or "(unknown)")
        topic = str(item.get("topic") or item.get("name") or "")
        html_path = resolve_asset_path(root, item.get("html_path") or item.get("html"))
        spec_path = resolve_asset_path(root, item.get("spec_path") or item.get("spec"))
        bpmn_path = resolve_asset_path(root, item.get("bpmn_path") or item.get("bpmn"))

        if not html_path or not html_path.exists():
            missing.append(format_missing(module_id, topic, "html", html_path))
        if not spec_path or not spec_path.exists():
            missing.append(format_missing(module_id, topic, "spec", spec_path))
            continue
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception as exc:
            missing.append(f"{module_id} {topic} spec read error: {spec_path} ({exc})")
            continue

        history_version_errors.extend(validate_history_versions(module_id, topic, spec_path, spec))

        if not bpmn_path or not bpmn_path.exists():
            if repair:
                bpmn_path = default_bpmn_path(spec_path)
                artifacts = write_bpmn_artifacts(spec, bpmn_path)
                rel = str(path_relative_to_root(root, bpmn_path))
                item["bpmn_path"] = rel
                item["bpmn"] = rel
                viewer_rel = str(path_relative_to_root(root, artifacts.viewer))
                item["bpmn_viewer_path"] = viewer_rel
                generated.append(artifacts.bpmn)
                generated_viewers.append(artifacts.viewer)
            else:
                missing.append(format_missing(module_id, topic, "bpmn", bpmn_path))
                continue
        elif repair:
            viewer_path = resolve_asset_path(root, item.get("bpmn_viewer_path") or item.get("bpmn_viewer"))
            if not viewer_path or not viewer_path.exists():
                viewer_path = bpmn_io_viewer_path_for(bpmn_path)
                viewer_path.write_text(
                    build_bpmn_io_viewer_html(
                        bpmn_path.read_text(encoding="utf-8"),
                        title=bpmn_title_from_spec(spec),
                        bpmn_file_name=bpmn_path.name,
                    ),
                    encoding="utf-8",
                )
                viewer_rel = str(path_relative_to_root(root, viewer_path))
                item["bpmn_viewer_path"] = viewer_rel
                generated_viewers.append(viewer_path)

        if bpmn_path and bpmn_path.exists():
            try:
                ET.parse(bpmn_path)
            except Exception as exc:  # pragma: no cover - error detail depends on parser.
                xml_errors.append(f"{module_id} {topic}: {bpmn_path} ({exc})")

    if repair and (generated or generated_viewers):
        queue_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return AssetCheckResult(len(items), generated, generated_viewers, missing, xml_errors, history_version_errors)


def validate_history_versions(module_id: str, topic: str, spec_path: Path, spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    version_pattern = re.compile(r"^v\d+\.\d+(?:_보완본)?$")
    for key in ("history", "document_history"):
        rows = spec.get(key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            version = str(row.get("version") or "").strip()
            if version and not version_pattern.fullmatch(version):
                errors.append(f"{module_id} {topic} {spec_path} {key}[{index}].version={version}")
    return errors


def resolve_asset_path(root: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else root / path


def default_bpmn_path(spec_path: Path) -> Path:
    stem = spec_path.name
    if stem.endswith("_manual_spec.json"):
        stem = stem[: -len("_manual_spec.json")] + "_manual_전체업무흐름도"
    elif stem.endswith("_spec.json"):
        stem = stem[: -len("_spec.json")] + "_전체업무흐름도"
    elif stem.endswith(".json"):
        stem = stem[: -len(".json")] + "_전체업무흐름도"
    return spec_path.with_name(stem + ".bpmn")


def path_relative_to_root(root: Path, path: Path) -> Path:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path


def format_missing(module_id: str, topic: str, label: str, path: Path | None) -> str:
    path_text = str(path) if path else "(empty)"
    return f"{module_id} {topic} {label}: {path_text}"


if __name__ == "__main__":
    raise SystemExit(main())
