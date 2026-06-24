#!/usr/bin/env python3
"""Register Codex-authored manual policy documents as service drafts.

The web app lists policy documents from the runtime ``output/`` root. Manual
authoring drafts were created under ``output/manual_authoring_*`` directories,
so this script promotes those drafts into the service-visible root while
normalizing version, lifecycle status, and document history.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "output"
REPORTS_ROOT = PROJECT_ROOT / "reports"
QUEUE_PATH = REPORTS_ROOT / "manual_authoring" / "manual_authoring_queue.json"

RUNTIME_ONLY_STALE_ARTIFACTS = [
    "output/NC_나의데이터통화_정책서_Full_v0.10.html",
    "output/NC_나의데이터통화_정책서_Full_v0.10_전체업무흐름도.bpmn",
    "output/NC_나의데이터통화_정책서_Full_v0.10_전체업무흐름도_viewer.html",
    "output/NC_요금납부납부수단관리_정책서_Full_v0.10.html",
    "output/NC_요금납부납부수단관리_정책서_Full_v0.10_전체업무흐름도.bpmn",
    "output/NC_요금납부납부수단관리_정책서_Full_v0.10_전체업무흐름도_viewer.html",
    "output/NC_청구및수납관리_정책서_Full_v0.10.html",
    "output/NC_청구및수납관리_정책서_Full_v0.10_전체업무흐름도.bpmn",
    "output/NC_청구및수납관리_정책서_Full_v0.10_전체업무흐름도_viewer.html",
    "output/status/NC_나의데이터통화_정책서_Full_v0.10_status.json",
    "output/status/NC_요금납부납부수단관리_정책서_Full_v0.10_status.json",
    "output/status/NC_청구및수납관리_정책서_Full_v0.10_status.json",
]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bpmn_renderer import bpmn_io_viewer_path_for, write_bpmn_artifacts  # noqa: E402
from src.policy_versioning import INITIAL_POLICY_VERSION  # noqa: E402
from src.renderer import render_policy_html  # noqa: E402


def simple_template_path() -> Path:
    templates_dir = PROJECT_ROOT / "input" / "templates"
    for path in sorted(templates_dir.glob("*.html")):
        normalized = unicodedata.normalize("NFC", path.name)
        if "간소화" in normalized and "템플릿" in normalized:
            return path
    raise FileNotFoundError(f"간소화 템플릿을 찾을 수 없습니다: {templates_dir}")


@dataclass
class RegisteredPolicy:
    module_id: str
    topic: str
    source_html: Path
    source_spec: Path
    source_bpmn: Path | None
    root_html: Path
    root_spec: Path
    root_bpmn: Path
    root_bpmn_viewer: Path
    status_path: Path
    spec: dict[str, Any]


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def policy_topic_slug_from_name(name: str) -> str:
    stem = name.removesuffix(".html")
    if not stem.startswith("NC_") or "_정책서_" not in stem:
        raise ValueError(f"정책서 파일명이 아닙니다: {name}")
    return stem.removeprefix("NC_").split("_정책서_", 1)[0]


def service_html_name(source_html: Path) -> str:
    name = source_html.name
    name = name.replace("_manual.html", ".html")
    name = name.replace("_direct.html", ".html")
    name = re.sub(r"_v\d+\.\d+(?:_[^.]*)?\.html$", f"_{INITIAL_POLICY_VERSION}.html", name)
    if "_정책서_간소화_" in name and not name.startswith("NC_"):
        name = f"NC_{name}"
    return name


def normalize_policy_spec(spec: dict[str, Any], today: str) -> dict[str, Any]:
    meta = spec.setdefault("meta", {})
    meta["version"] = INITIAL_POLICY_VERSION
    meta["status"] = "작성중"
    meta["document_status"] = "작성중"
    meta["author"] = "Codex"
    meta["updated_at"] = today
    meta.setdefault("created_at", today)
    meta["date"] = meta.get("date") or meta.get("created_at") or today
    spec["history"] = [
        {
            "version": INITIAL_POLICY_VERSION,
            "change": "Codex 기반 초안 작성",
            "date": today,
            "author": "Codex",
        }
    ]
    return spec


def collect_registered_policies(queue: dict[str, Any], today: str) -> list[RegisteredPolicy]:
    policies: list[RegisteredPolicy] = []
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("module_id", "")).strip()
        topic = str(item.get("topic", "")).strip()
        source_html_text = str(item.get("html") or item.get("html_path") or "").strip()
        source_spec_text = str(item.get("spec") or item.get("spec_path") or "").strip()
        source_bpmn_text = str(item.get("bpmn") or item.get("bpmn_path") or "").strip()
        if not module_id or not topic or not source_html_text or not source_spec_text:
            raise ValueError(f"수동 작성 큐 항목의 산출물 경로가 부족합니다: {module_id or topic}")

        source_html = PROJECT_ROOT / source_html_text
        source_spec = PROJECT_ROOT / source_spec_text
        source_bpmn = PROJECT_ROOT / source_bpmn_text if source_bpmn_text else None
        if not source_html.exists():
            raise FileNotFoundError(source_html)
        if not source_spec.exists():
            raise FileNotFoundError(source_spec)
        if source_bpmn and not source_bpmn.exists():
            source_bpmn = None

        root_html = OUTPUT_ROOT / service_html_name(source_html)
        topic_slug = policy_topic_slug_from_name(root_html.name)
        root_spec = OUTPUT_ROOT / f"{topic_slug}_policy_spec.json"
        root_bpmn = OUTPUT_ROOT / f"{root_html.stem}_전체업무흐름도.bpmn"
        root_bpmn_viewer = bpmn_io_viewer_path_for(root_bpmn)
        status_path = OUTPUT_ROOT / "status" / f"{root_html.stem}_status.json"
        spec = normalize_policy_spec(load_json(source_spec), today)
        policies.append(
            RegisteredPolicy(
                module_id=module_id,
                topic=topic,
                source_html=source_html,
                source_spec=source_spec,
                source_bpmn=source_bpmn,
                root_html=root_html,
                root_spec=root_spec,
                root_bpmn=root_bpmn,
                root_bpmn_viewer=root_bpmn_viewer,
                status_path=status_path,
                spec=spec,
            )
        )
    if len(policies) != 34:
        raise ValueError(f"등록 대상 정책서가 34개가 아닙니다: {len(policies)}개")
    return policies


def collect_service_artifacts_for_cleanup() -> list[Path]:
    paths: set[Path] = set()
    if OUTPUT_ROOT.exists():
        for path in OUTPUT_ROOT.iterdir():
            if path.name == ".DS_Store":
                paths.add(path)
            elif path.is_file() and is_service_policy_artifact(path):
                paths.add(path)
            elif path.is_dir() and should_delete_output_dir(path):
                paths.add(path)
        for folder_name in ("status", "steps", "checkpoints", "quality", ".locks"):
            folder = OUTPUT_ROOT / folder_name
            if folder.exists():
                paths.add(folder)
    inspections = REPORTS_ROOT / "inspections"
    if inspections.exists():
        for path in inspections.glob("*.json"):
            paths.add(path)
    return sorted(paths, key=lambda item: project_relative(item))


def is_service_policy_artifact(path: Path) -> bool:
    name = path.name
    if name.startswith("NC_") and "_정책서_" in name and name.endswith((".html", ".bpmn")):
        return True
    if name.endswith("_policy_spec.json") or name.endswith("_authoring_blueprint.json"):
        return True
    return False


def should_delete_output_dir(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("manual_authoring_")
        or name.startswith("direct_authoring")
        or name.startswith("mock_")
        or name.startswith("llm_")
        or name in {"state_transition_test"}
    )


def remove_paths(paths: Iterable[Path]) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)
    return removed


def write_registered_policy(policy: RegisteredPolicy, template_html: str, now_iso: str) -> None:
    policy.root_html.parent.mkdir(parents=True, exist_ok=True)
    document = render_policy_html(dict(policy.spec), template_html, "simple", "full")
    policy.root_html.write_text(document, encoding="utf-8")
    write_json(policy.root_spec, policy.spec)
    write_bpmn_artifacts(policy.spec, policy.root_bpmn)
    write_json(
        policy.status_path,
        {
            "name": policy.root_html.name,
            "topic": policy_topic_slug_from_name(policy.root_html.name),
            "status": "in_progress",
            "label": "작성 중",
            "updatedAt": now_iso,
            "updatedBy": "Codex",
            "history": [],
        },
    )


def update_queue_paths(queue: dict[str, Any], policies: list[RegisteredPolicy]) -> dict[str, Any]:
    by_module = {policy.module_id: policy for policy in policies}
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        policy = by_module.get(str(item.get("module_id", "")).strip())
        if not policy:
            continue
        item["spec"] = project_relative(policy.root_spec)
        item["html"] = project_relative(policy.root_html)
        item["bpmn"] = project_relative(policy.root_bpmn)
        item["bpmn_viewer"] = project_relative(policy.root_bpmn_viewer)
        item["spec_path"] = project_relative(policy.root_spec)
        item["html_path"] = project_relative(policy.root_html)
        item["bpmn_path"] = project_relative(policy.root_bpmn)
        item["bpmn_viewer_path"] = project_relative(policy.root_bpmn_viewer)
        item["service_status"] = "작성 중"
        item["registered_version"] = INITIAL_POLICY_VERSION
        item["registered_by"] = "Codex"
        item["registered_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    queue["current_policy_module_id"] = policies[-1].module_id
    queue["registered_policy_count"] = len(policies)
    return queue


def write_cleanup_manifest(cleanup_paths: list[Path], registered: list[RegisteredPolicy], now_iso: str) -> Path:
    manifest_path = REPORTS_ROOT / "module_34_codex_draft_registration_cleanup_20260510.json"
    registered_paths = []
    for policy in registered:
        registered_paths.extend(
            [
                project_relative(policy.root_html),
                project_relative(policy.root_spec),
                project_relative(policy.root_bpmn),
                project_relative(policy.status_path),
            ]
        )
    runtime_cleanup_roots = [
        "output/status",
        "output/steps",
        "output/checkpoints",
        "output/quality",
        "output/.locks",
        "reports/inspections",
    ]
    output_cleanup_dirs = [
        f"output/manual_authoring_{policy.module_id}_{slugify_path_part(policy.topic)}"
        for policy in registered
    ]
    removed_paths = {
        project_relative(path)
        for path in cleanup_paths
    }
    removed_paths.update(registered_paths)
    removed_paths.update(runtime_cleanup_roots)
    removed_paths.update(output_cleanup_dirs)
    removed_paths.update(RUNTIME_ONLY_STALE_ARTIFACTS)
    write_json(
        manifest_path,
        {
            "createdAt": now_iso,
            "reason": f"기존 작성중/작성완료 정책서 산출물을 정리하고 Codex 작성본 34개를 {INITIAL_POLICY_VERSION} 작성중 상태로 재등록한다.",
            "removed": sorted(removed_paths),
            "registered": sorted(set(registered_paths)),
            "preserved": [
                "input/requirements",
                "input/references",
                "input/templates",
                "input/samples",
                "reports/evidence",
                "reports/manual_authoring",
            ],
        },
    )
    return manifest_path


def slugify_path_part(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "policy"


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Register manual authoring policies as {INITIAL_POLICY_VERSION} drafts.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing files.")
    args = parser.parse_args()

    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    queue = load_json(QUEUE_PATH)
    policies = collect_registered_policies(queue, today)
    cleanup_paths = collect_service_artifacts_for_cleanup()

    if args.dry_run:
        print(f"register={len(policies)} cleanup={len(cleanup_paths)}")
        for policy in policies[:5]:
            print(f"- {policy.module_id}: {project_relative(policy.root_html)}")
        print("...")
        return

    template_html = simple_template_path().read_text(encoding="utf-8")
    removed = remove_paths(cleanup_paths)
    for policy in policies:
        write_registered_policy(policy, template_html, now_iso)
    updated_queue = update_queue_paths(queue, policies)
    write_json(QUEUE_PATH, updated_queue)
    manifest = write_cleanup_manifest(cleanup_paths, policies, now_iso)
    print(
        json.dumps(
            {
                "removed": len(removed),
                "registered": len(policies),
                "manifest": project_relative(manifest),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
