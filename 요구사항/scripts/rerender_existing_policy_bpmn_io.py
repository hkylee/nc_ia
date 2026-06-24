#!/usr/bin/env python3
"""Rerender existing policy HTML files and regenerate bpmn.io artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "output"
REPORTS_ROOT = PROJECT_ROOT / "reports"
TEMPLATES_ROOT = PROJECT_ROOT / "input" / "templates"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bpmn_renderer import write_bpmn_artifacts  # noqa: E402
from src.policy_agent import normalize_sentence_breaks  # noqa: E402
from src.renderer import render_policy_html  # noqa: E402
from src.timezone_utils import configure_local_timezone  # noqa: E402


HISTORY_CHANGE = "bpmn.io viewer 산출물 생성 및 문서 재렌더링"
POLICY_HTML_RE = re.compile(
    r"^NC_(?P<topic>.+)_정책서_(?P<template_label>간소화|Full)_(?P<version>v\d+\.\d+(?:_보완본)?)\.html$"
)


@dataclass(frozen=True)
class PolicyTarget:
    html_path: Path
    spec_path: Path
    topic: str
    template_label: str
    template_type: str
    version: str


def main() -> int:
    configure_local_timezone()
    parser = argparse.ArgumentParser(description="Rerender existing policy documents with bpmn.io viewer artifacts.")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT, help="정책서 output 폴더")
    parser.add_argument("--templates-root", type=Path, default=TEMPLATES_ROOT, help="HTML 템플릿 폴더")
    parser.add_argument("--reports-root", type=Path, default=REPORTS_ROOT, help="실행 리포트 저장 폴더")
    parser.add_argument("--topic", default="", help="특정 주제만 처리합니다. 예: 상품목록")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 대상만 확인합니다.")
    args = parser.parse_args()

    targets = discover_targets(args.output_root, topic=args.topic)
    templates = {
        "simple": find_template(args.templates_root, "간소화"),
        "full": find_template(args.templates_root, "Full"),
    }
    latest_specs = load_latest_topic_specs(args.output_root)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": bool(args.dry_run),
        "target_count": len(targets),
        "updated": [],
        "skipped": [],
    }

    for target in targets:
        spec = load_json(target.spec_path)
        before = {
            "html": file_sha256(target.html_path),
            "spec": file_sha256(target.spec_path),
        }
        align_spec_metadata(spec, target)
        history_added = append_history(spec, target.version)
        template_html = templates[target.template_type].read_text(encoding="utf-8")
        document = normalize_sentence_breaks(render_policy_html(spec, template_html, target.template_type, "full"))
        bpmn_path = target.html_path.with_name(f"{target.html_path.stem}_전체업무흐름도.bpmn")

        topic_spec_path = target.html_path.with_name(f"{target.topic}_policy_spec.json")
        update_latest_spec = should_update_latest_spec(latest_specs.get(target.topic), spec)

        if not args.dry_run:
            target.html_path.write_text(document, encoding="utf-8")
            spec_json = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
            target.spec_path.write_text(spec_json, encoding="utf-8")
            if update_latest_spec:
                topic_spec_path.write_text(spec_json, encoding="utf-8")
            artifacts = write_bpmn_artifacts(spec, bpmn_path)
            viewer_path = artifacts.viewer
        else:
            viewer_path = bpmn_path.with_name(f"{bpmn_path.stem}_viewer.html")

        report["updated"].append(
            {
                "html": project_relative(target.html_path),
                "spec": project_relative(target.spec_path),
                "topic_spec_updated": update_latest_spec,
                "bpmn": project_relative(bpmn_path),
                "bpmn_viewer": project_relative(viewer_path),
                "history_added": history_added,
                "before": before,
                "after": {
                    "html": file_sha256(target.html_path) if not args.dry_run else before["html"],
                    "spec": file_sha256(target.spec_path) if not args.dry_run else before["spec"],
                },
            }
        )

    report_path = args.reports_root / f"bpmn_io_rerender_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if not args.dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"targets={len(targets)}")
    print(f"updated={len(report['updated'])}")
    print(f"skipped={len(report['skipped'])}")
    if not args.dry_run:
        print(f"report={project_relative(report_path)}")
    return 0


def discover_targets(output_root: Path, *, topic: str = "") -> list[PolicyTarget]:
    targets: list[PolicyTarget] = []
    topic_filter = normalize_korean(topic).strip()
    for html_path in sorted(output_root.glob("NC_*_정책서_*_v*.html")):
        parsed = parse_policy_filename(html_path.name)
        if not parsed:
            continue
        if topic_filter and parsed["topic"] != topic_filter:
            continue
        spec_path = html_path.with_name(f"{html_path.stem}_spec.json")
        if not spec_path.exists():
            raise FileNotFoundError(f"Spec not found for {html_path}: {spec_path}")
        targets.append(
            PolicyTarget(
                html_path=html_path,
                spec_path=spec_path,
                topic=parsed["topic"],
                template_label=parsed["template_label"],
                template_type="full" if parsed["template_label"] == "Full" else "simple",
                version=parsed["version"],
            )
        )
    return targets


def parse_policy_filename(name: str) -> dict[str, str] | None:
    match = POLICY_HTML_RE.match(normalize_korean(name))
    if not match:
        return None
    return match.groupdict()


def find_template(templates_root: Path, keyword: str) -> Path:
    normalized_keyword = normalize_korean(keyword).casefold()
    for path in sorted(templates_root.glob("*.html")):
        name = normalize_korean(path.name).casefold()
        if normalized_keyword in name and "템플릿" in name:
            return path
    raise FileNotFoundError(f"Template not found: {templates_root} keyword={keyword}")


def load_latest_topic_specs(output_root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for path in sorted(output_root.glob("*_policy_spec.json")):
        topic = path.name[: -len("_policy_spec.json")]
        try:
            latest[topic] = load_json(path)
        except Exception:
            continue
    return latest


def should_update_latest_spec(latest_spec: dict[str, Any] | None, spec: dict[str, Any]) -> bool:
    if not latest_spec:
        return False
    latest_meta = latest_spec.get("meta", {}) if isinstance(latest_spec.get("meta"), dict) else {}
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    return (
        str(latest_meta.get("version", "")).strip() == str(meta.get("version", "")).strip()
        and str(latest_meta.get("document_type", "")).strip() == str(meta.get("document_type", "")).strip()
    )


def align_spec_metadata(spec: dict[str, Any], target: PolicyTarget) -> None:
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["topic"] = target.topic
        meta["topic_slug"] = target.topic
        meta["version"] = target.version
        meta["template_type"] = target.template_type
        meta["document_type"] = "Full 버전" if target.template_type == "full" else "간소화 버전"
        meta["updated_at"] = datetime.now().date().isoformat()
    if "version" in spec:
        spec["version"] = target.version


def append_history(spec: dict[str, Any], version: str) -> bool:
    history = spec.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        spec["history"] = history
    for row in history:
        if not isinstance(row, dict):
            continue
        if str(row.get("version", "")).strip() == version and str(row.get("change", "")).strip() == HISTORY_CHANGE:
            return False
    history.append(
        {
            "version": version,
            "change": HISTORY_CHANGE,
            "date": datetime.now().date().isoformat(),
            "author": "Codex",
        }
    )
    return True


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def normalize_korean(value: str) -> str:
    return unicodedata.normalize("NFC", str(value or ""))


if __name__ == "__main__":
    raise SystemExit(main())
