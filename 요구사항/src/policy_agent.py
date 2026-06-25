#!/usr/bin/env python3
"""Generate NC integrated-channel policy documents from an HTML template."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote

try:
    from timezone_utils import configure_local_timezone
except ImportError:  # pragma: no cover - package import fallback.
    from .timezone_utils import configure_local_timezone

APP_TIMEZONE = configure_local_timezone()

try:
    from bpmn_renderer import write_bpmn_artifacts
    from artifact_drift import evaluate_policy_artifact_drift
    from renderer import render_policy_html
    from llm_client import LLMClient, llm_preflight_enabled, load_env_files
    from llm_routing import client_for_revision, client_for_stage_inspector
    from orchestrator import orchestrate_policy_generation
    from policy_style_anchor import policy_style_anchor_for_prompt
    from runtime_paths import OUTPUT_ROOT, PROJECT_ROOT
    from authoring_blueprint import build_authoring_blueprint
    from chapter_agents import AgentRuntime, build_agent_guideline, chapter_stages, deduplicate_function_names, reconcile_process_function_links
    from evidence_store import build_evidence_store
    from gate_policy import gate_required_score, gate_tier, inspect_gate_decision
    from validator import blueprint_referenced_evidence_ids, policy_detail_quality_dimensions, uncovered_requirement_ids, validate_policy_spec, validate_stage_critical
    from policy_references import ReferenceInsight, load_reference_insights_for_topic
    from policy_requirements import RequirementItem, load_scoped_requirements_for_topic
    from policy_versioning import next_policy_version, parse_policy_version
    from topic_knowledge_builder import DEFAULT_TOPIC_KNOWLEDGE_DIR, POLICY_TOPICS, build_all_topic_knowledge_packs, build_and_save_topic_knowledge_pack
    from schema import build_policy_spec, display_policy_topic, ensure_policy_spec_base_keys
    from policy_inspector import (
        DEFAULT_INSPECTOR_MIN_SCORE,
        finding_actionability_issues,
        finding_tier,
        is_quality_gate_finding,
        inspect_policy_document,
        inspect_policy_json_spec,
        load_sample_htmls,
        merge_inspection_reports,
        save_inspection_report,
    )
except ImportError:  # pragma: no cover - package import fallback.
    from .bpmn_renderer import write_bpmn_artifacts
    from .artifact_drift import evaluate_policy_artifact_drift
    from .renderer import render_policy_html
    from .llm_client import LLMClient, llm_preflight_enabled, load_env_files
    from .llm_routing import client_for_revision, client_for_stage_inspector
    from .orchestrator import orchestrate_policy_generation
    from .policy_style_anchor import policy_style_anchor_for_prompt
    from .runtime_paths import OUTPUT_ROOT, PROJECT_ROOT
    from .authoring_blueprint import build_authoring_blueprint
    from .chapter_agents import AgentRuntime, build_agent_guideline, chapter_stages, deduplicate_function_names, reconcile_process_function_links
    from .evidence_store import build_evidence_store
    from .gate_policy import gate_required_score, gate_tier, inspect_gate_decision
    from .validator import blueprint_referenced_evidence_ids, policy_detail_quality_dimensions, uncovered_requirement_ids, validate_policy_spec, validate_stage_critical
    from .policy_references import ReferenceInsight, load_reference_insights_for_topic
    from .policy_requirements import RequirementItem, load_scoped_requirements_for_topic
    from .policy_versioning import next_policy_version, parse_policy_version
    from .topic_knowledge_builder import DEFAULT_TOPIC_KNOWLEDGE_DIR, POLICY_TOPICS, build_all_topic_knowledge_packs, build_and_save_topic_knowledge_pack
    from .schema import build_policy_spec, display_policy_topic, ensure_policy_spec_base_keys
    from .policy_inspector import (
        DEFAULT_INSPECTOR_MIN_SCORE,
        finding_actionability_issues,
        finding_tier,
        is_quality_gate_finding,
        inspect_policy_document,
        inspect_policy_json_spec,
        load_sample_htmls,
        merge_inspection_reports,
        save_inspection_report,
    )


DEFAULT_OUTPUT_DIR = OUTPUT_ROOT
DEFAULT_AUTHOR = "Policy Agent"


@dataclass(frozen=True)
class PolicyContext:
    topic: str
    topic_html: str
    topic_slug: str
    module_id: str
    business_code: str
    version: str
    version_number: str
    today: str
    status: str
    author: str
    brief: str
    brief_html: str
    template_path: Path
    template_type: str
    output_dir: Path
    requirements: Tuple[RequirementItem, ...]
    references: Tuple[ReferenceInsight, ...]
    writer_mode: str = "mock"
    disable_mock_env: bool = False
    review_mode: str = "auto"
    inspection_mode: str = "chapter-final"
    llm_model: str = ""
    reasoning_effort: str = ""
    inspector_min_score: int = DEFAULT_INSPECTOR_MIN_SCORE
    inspector_max_loops: int = 3
    progress_callback: object = None
    manual_review_callback: object = None


@dataclass(frozen=True)
class TemplateSelection:
    path: Path
    template_type: str


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "create":
        try:
            result = create_policy(args)
        except (FileNotFoundError, ValueError) as exc:
            parser.exit(1, f"error: {exc}\n")
        print(f"created: {result}")
        return
    if args.command == "inspect":
        try:
            report = inspect_policy_file(args)
        except (FileNotFoundError, ValueError) as exc:
            parser.exit(1, f"error: {exc}\n")
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            print_inspection_report(report)
        return
    if args.command == "prelearn":
        result = prelearn_topics(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    parser.print_help()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="통합채널 정책서 HTML 생성 CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    create = subparsers.add_parser(
        "create",
        help="주제와 HTML 템플릿을 기준으로 정책서 초안을 생성합니다.",
    )
    create.add_argument("--topic", required=True, help='정책서 주제. 예: "상품 상세"')
    create.add_argument(
        "--template",
        required=True,
        help="기준 HTML 템플릿 파일 또는 input/templates 폴더 경로. simple/full 별칭도 사용할 수 있습니다.",
    )
    create.add_argument(
        "--template-type",
        choices=("simple", "full"),
        default=None,
        help="템플릿 폴더나 template.html 예시 경로를 넣었을 때 선택할 템플릿 유형. 미지정 시 물어봅니다.",
    )
    create.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="생성 파일을 저장할 폴더. 기본값: output",
    )
    create.add_argument("--author", default=DEFAULT_AUTHOR, help="문서 작성자")
    create.add_argument("--status", default="작성중", help="문서 상태")
    create.add_argument("--brief", default="", help="정책서 작성 요청 메모")
    create.add_argument(
        "--requirements-dir",
        default="input/requirements",
        help="요구사항 엑셀 파일이 있는 폴더 또는 xlsx 파일 경로. 기본값: input/requirements",
    )
    create.add_argument(
        "--no-requirements",
        action="store_true",
        help="요구사항 엑셀 매칭과 반영을 생략합니다.",
    )
    create.add_argument(
        "--references-dir",
        default="input/references",
        help="참고자료 PDF/엑셀 파일이 있는 폴더 또는 파일 경로. 기본값: input/references",
    )
    create.add_argument(
        "--no-references",
        action="store_true",
        help="참고자료 분석과 반영을 생략합니다.",
    )
    create.add_argument(
        "--no-steps",
        action="store_true",
        help="단계별 HTML 스냅샷 저장을 생략합니다.",
    )
    create.add_argument(
        "--no-inspect",
        action="store_true",
        help="장별 inspector 검수와 리포트 저장을 생략합니다.",
    )
    create.add_argument(
        "--inspection-mode",
        choices=("chapter-final", "final-only", "none"),
        default="chapter-final",
        help=(
            "Inspector 실행 방식. chapter-final은 장별+최종 검수, "
            "final-only는 장별 Inspector를 생략하고 최종 Inspector만 실행, none은 전체 Inspector를 생략합니다."
        ),
    )
    create.add_argument(
        "--inspector-min-score",
        type=int,
        default=DEFAULT_INSPECTOR_MIN_SCORE,
        help=f"각 챕터가 다음 agent로 넘어가기 위한 inspector 최소 점수. 기본값: {DEFAULT_INSPECTOR_MIN_SCORE}",
    )
    create.add_argument(
        "--inspector-max-loops",
        type=int,
        default=3,
        help="각 챕터별 agent 작성-검수-보완 반복 최대 횟수. 기본값: 3",
    )
    create.add_argument(
        "--writer-mode",
        choices=("auto", "llm", "local", "mock"),
        default="mock",
        help="정책서 작성 엔진. mock은 API 호출 없이 LLM 경로를 테스트합니다.",
    )
    create.add_argument(
        "--review-mode",
        choices=("auto", "manual"),
        default="auto",
        help="진행 방식. manual은 각 챕터 완료 후 사용자 검수 응답을 기다립니다.",
    )
    create.add_argument(
        "--resume-from",
        default="",
        help="중단된 생성 작업을 이어서 작성할 체크포인트 JSON 경로입니다.",
    )
    create.add_argument(
        "--model",
        default="",
        help="LLM 작성에 사용할 OpenAI 모델 ID. 미지정 시 OPENAI_MODEL 또는 기본 모델을 사용합니다.",
    )
    create.add_argument(
        "--reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        default="",
        help="LLM 추론 강도. ChatGPT의 확장 추론에 가깝게 쓰려면 xhigh를 지정합니다.",
    )

    inspect = subparsers.add_parser(
        "inspect",
        help="생성된 정책서 HTML이 템플릿, 가이드, 샘플 수준을 충족하는지 검수합니다.",
    )
    inspect.add_argument("--file", required=True, help="검수할 정책서 HTML 파일")
    inspect.add_argument(
        "--template",
        default="input/templates",
        help="기준 HTML 템플릿 파일 또는 input/templates 폴더 경로",
    )
    inspect.add_argument(
        "--template-type",
        choices=("simple", "full"),
        default=None,
        help="검수 기준 템플릿 유형. 미지정 시 파일명에서 추정합니다.",
    )
    inspect.add_argument("--scope", default="full", help="검수 범위. 기본값: full")
    inspect.add_argument("--topic", default="", help="정책서 주제. 미지정 시 파일명에서 추정합니다.")
    inspect.add_argument(
        "--writer-mode",
        choices=("auto", "llm", "local", "mock"),
        default="mock",
        help="검수 엔진. llm을 명시한 경우에만 실제 LLM Inspector를 사용합니다.",
    )
    inspect.add_argument(
        "--requirements-dir",
        default="input/requirements",
        help="요구사항 엑셀 파일이 있는 폴더 또는 xlsx 파일 경로. 기본값: input/requirements",
    )
    inspect.add_argument("--json", action="store_true", help="검수 결과를 JSON으로 출력합니다.")

    prelearn = subparsers.add_parser(
        "prelearn",
        help="정책서 주제별 사전 Knowledge Pack을 생성합니다.",
    )
    prelearn.add_argument("--topic", default="", help="특정 주제만 사전 학습합니다. 미지정 시 전체 주제를 처리합니다.")
    prelearn.add_argument(
        "--output-dir",
        default=str(DEFAULT_TOPIC_KNOWLEDGE_DIR),
        help="Knowledge Pack 저장 폴더. 기본값: reports/evidence/topic_knowledge",
    )

    return parser


def prelearn_topics(args: argparse.Namespace) -> dict:
    output_dir = resolve_path(getattr(args, "output_dir", str(DEFAULT_TOPIC_KNOWLEDGE_DIR)))
    topic = str(getattr(args, "topic", "") or "").strip()
    if topic:
        path = build_and_save_topic_knowledge_pack(topic, output_dir=output_dir)
        return {
            "mode": "single",
            "topic": topic,
            "path": str(path),
        }
    manifest = build_all_topic_knowledge_packs(POLICY_TOPICS, output_dir=output_dir)
    return {
        "mode": "all",
        "topic_count": manifest.get("topic_count", 0),
        "manifest_path": str(output_dir / "manifest.json"),
    }


def create_policy(args: argparse.Namespace) -> Path:
    load_env_files()
    template_selection = resolve_template_path(args.template, args.template_type, args.topic)
    template_path = template_selection.path
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    topic = args.topic.strip()
    if not topic:
        raise ValueError("--topic 값이 비어 있습니다.")

    topic_slug = make_topic_slug(topic)
    resume_checkpoint = load_resume_checkpoint(getattr(args, "resume_from", ""))
    version = checkpoint_version(resume_checkpoint) or next_version(output_dir, topic_slug, template_selection.template_type)
    previous_history = load_previous_document_history(output_dir, topic_slug, template_selection.template_type, version)
    requirements = tuple(load_policy_requirements(topic, args))
    references = tuple(load_policy_references(topic, args))
    inspection_mode = normalized_inspection_mode(args)
    ctx = PolicyContext(
        topic=topic,
        topic_html=html.escape(display_policy_topic(topic)),
        topic_slug=topic_slug,
        module_id=make_module_id(topic),
        business_code=make_business_code(topic),
        version=version,
        version_number=version.removeprefix("v"),
        today=date.today().isoformat(),
        status=args.status,
        author=args.author,
        brief=getattr(args, "brief", ""),
        brief_html=html.escape(getattr(args, "brief", "").strip()),
        template_path=template_path,
        template_type=template_selection.template_type,
        output_dir=output_dir,
        requirements=requirements,
        references=references,
        writer_mode=getattr(args, "writer_mode", "auto"),
        disable_mock_env=str(getattr(args, "writer_mode", "auto") or "auto").strip().casefold() == "llm",
        review_mode=getattr(args, "review_mode", "auto"),
        inspection_mode=inspection_mode,
        llm_model=getattr(args, "model", ""),
        reasoning_effort=getattr(args, "reasoning_effort", ""),
        inspector_min_score=max(
            0,
            min(
                100,
                int(getattr(args, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE) or DEFAULT_INSPECTOR_MIN_SCORE),
            ),
        ),
        inspector_max_loops=max(1, int(getattr(args, "inspector_max_loops", 3) or 3)),
        progress_callback=getattr(args, "progress_callback", None),
        manual_review_callback=getattr(args, "manual_review_callback", None),
    )
    run_llm_preflight(ctx)
    template_html = template_path.read_text(encoding="utf-8")
    sample_htmls = load_sample_htmls(ctx.template_type)
    document = ""
    inspect_enabled = inspection_mode != "none"
    stage_inspect_enabled = inspection_mode == "chapter-final"
    inspector_llm_client = LLMClient.from_context(ctx) if inspect_enabled else None
    inspector_llm_required = inspect_enabled

    def after_chapter(stage_spec: dict, stage, attempt: int) -> dict:
        nonlocal document
        partial_validation = validate_policy_spec(stage_spec, ctx.business_code, allow_incomplete=True)
        if not partial_validation.ok:
            feedback = critical_validation_feedback(partial_validation.errors, "JSON 구조 검증")
            record_json_critical_gate_run(stage_spec, stage, attempt, partial_validation.errors, False)
            return json_critical_gate_result(stage_spec, stage, ctx, feedback, "JSON 구조 검증에서 보완이 필요합니다.")

        critical_validation = validate_stage_critical(stage_spec, ctx.business_code, stage.scope)
        if not critical_validation.ok:
            feedback = critical_validation_feedback(critical_validation.errors, "JSON Critical Gate")
            record_json_critical_gate_run(stage_spec, stage, attempt, critical_validation.errors, False)
            return json_critical_gate_result(stage_spec, stage, ctx, feedback, "JSON Critical Gate에서 연결성 보완이 필요합니다.")

        record_json_critical_gate_run(stage_spec, stage, attempt, (), True)
        document = render_policy_html(stage_spec, template_html, ctx.template_type, stage.key)
        document = normalize_sentence_breaks(document)
        preview = build_stage_activity_preview(stage_spec, stage)
        html_smoke_feedback = stage_html_smoke_feedback(document, stage)
        record_stage_html_smoke_check(stage_spec, stage, attempt, html_smoke_feedback)
        artifact = None
        if not stage_inspect_enabled:
            if not args.no_steps:
                artifact = stage_artifact_payload(save_stage_snapshot(document, ctx, stage.key, stage.name), ctx)
            skip_reason = (
                "최종 Inspector 전용 모드에서 장별 Inspector를 생략했습니다."
                if inspect_enabled
                else "Inspector 생략 모드에서 단계 작성 완료"
            )
            checkpoint = checkpoint_artifact_payload(
                save_generation_checkpoint(stage_spec, ctx, stage, attempt, True, skip_reason),
                ctx,
            )
            preview.setdefault("items", []).append(f"체크포인트 저장: {checkpoint['name']}")
            if inspect_enabled:
                preview.setdefault("items", []).append("장별 LLM Inspector 생략, 최종 Inspector에서 전체 문서 검수 예정")
            return {
                "passed": True,
                "score": None,
                "threshold": None,
                "feedback": [],
                "artifact": artifact,
                "checkpoint": checkpoint,
                "preview": preview,
                "inspection_skipped": True,
            }

        chunk_feedback = chunk_fallback_feedback(stage_spec, stage, attempt)
        html_smoke_errors = [item for item in html_smoke_feedback if item.get("severity") == "error"]
        local_report = inspect_policy_json_spec(
            stage_spec,
            template_type=ctx.template_type,
            scope=stage.scope,
            chapter_key=stage.agent.chapter_key,
            topic=ctx.topic,
            brief=ctx.brief,
            llm_client=None,
            llm_required=False,
        )
        local_gate_decision = inspect_gate_decision(local_report, stage.agent.chapter_key, ctx.inspector_min_score)
        local_threshold = int(local_gate_decision.get("threshold", ctx.inspector_min_score) or 0)
        local_score_breakdown = (
            local_report.metrics.get("score_breakdown", {})
            if isinstance(getattr(local_report, "metrics", {}), dict)
            else {}
        )
        local_has_errors = any(finding.severity == "error" for finding in local_report.findings)
        local_gate_blocker_count = int(
            local_gate_decision.get("gate_blocker_count", local_score_breakdown.get("gate_blocker_count", 0)) or 0
        )
        if html_smoke_errors or chunk_feedback or local_has_errors or local_gate_blocker_count:
            report_suffix = f"{stage.key}_{stage.name}_local_precheck_attempt{attempt}"
            save_inspection_report(local_report, make_output_filename(ctx), report_suffix)
            record_inspector_gate_run(stage_spec, stage, attempt, local_report, False, local_threshold, local_gate_decision)
            if not args.no_steps:
                artifact = stage_artifact_payload(save_stage_snapshot(document, ctx, stage.key, stage.name), ctx)
            preview.setdefault("items", []).append(
                f"로컬 구조 점검 {local_report.score}점 / 기준 {local_threshold}점 / LLM Inspector 전 보완 필요"
            )
            if html_smoke_feedback:
                preview.setdefault("items", []).append(f"HTML 기본 점검 {len(html_smoke_feedback)}건 확인")
            if chunk_feedback:
                preview.setdefault("items", []).append("일부 분할 작성 구간이 로컬 초안으로 대체되어 보완 우선순위로 전환했습니다.")
            feedback_items = html_smoke_feedback + chunk_feedback + inspection_feedback(
                local_report,
                local_threshold,
                attempt=attempt,
                chapter_key=stage.agent.chapter_key,
            )
            diagnostic = checkpoint_artifact_payload(
                save_failed_attempt_diagnostic(
                    stage_spec,
                    ctx,
                    stage,
                    attempt,
                    local_report,
                    local_threshold,
                    local_gate_decision,
                    feedback_items,
                ),
                ctx,
            )
            preview.setdefault("items", []).append(f"실패 진단 저장: {diagnostic['name']}")
            return {
                "passed": False,
                "score": local_report.score,
                "threshold": local_threshold,
                "gate_tier": local_gate_decision.get("tier"),
                "gate_blocker_count": local_gate_decision.get("gate_blocker_count", 0),
                "feedback": feedback_items,
                "artifact": artifact,
                "checkpoint": None,
                "preview": preview,
                "local_precheck": True,
            }

        report = inspect_policy_json_spec(
            stage_spec,
            template_type=ctx.template_type,
            scope=stage.scope,
            chapter_key=stage.agent.chapter_key,
            topic=ctx.topic,
            brief=ctx.brief,
            llm_client=client_for_stage_inspector(inspector_llm_client, final=False, attempt=attempt) if inspector_llm_client else None,
            llm_required=inspector_llm_required,
            llm_retry_callback=inspector_retry_callback(ctx, stage.key, stage.name, stage.agent.display_name),
        )
        report_suffix = f"{stage.key}_{stage.name}_attempt{attempt}"
        save_inspection_report(report, make_output_filename(ctx), report_suffix)
        gate_decision = inspect_gate_decision(report, stage.agent.chapter_key, ctx.inspector_min_score)
        threshold = int(gate_decision.get("threshold", ctx.inspector_min_score) or 0)
        passed = bool(gate_decision.get("passed", False)) and not chunk_feedback and not html_smoke_errors
        record_inspector_gate_run(stage_spec, stage, attempt, report, passed, threshold, gate_decision)
        if gate_decision.get("tier") == "log-only" and report.findings:
            record_log_only_open_issues(stage_spec, stage, attempt, report, threshold)
        if not args.no_steps:
            artifact = stage_artifact_payload(save_stage_snapshot(document, ctx, stage.key, stage.name), ctx)
        preview.setdefault("items", []).append(f"Inspector 점수 {report.score}점 / 기준 {threshold}점 / Gate {gate_decision.get('tier')}")
        if html_smoke_feedback:
            preview.setdefault("items", []).append(f"HTML 기본 점검 {len(html_smoke_feedback)}건 확인")
        if chunk_feedback:
            preview.setdefault("items", []).append("일부 분할 작성 구간이 로컬 초안으로 대체되어 보완 우선순위로 전환했습니다.")
        checkpoint = None
        feedback_items = html_smoke_feedback + chunk_feedback + inspection_feedback(
            report,
            threshold,
            attempt=attempt,
            chapter_key=stage.agent.chapter_key,
        )
        if passed:
            checkpoint = checkpoint_artifact_payload(
                save_generation_checkpoint(stage_spec, ctx, stage, attempt, True, report.summary),
                ctx,
            )
            preview.setdefault("items", []).append(f"체크포인트 저장: {checkpoint['name']}")
        else:
            diagnostic = checkpoint_artifact_payload(
                save_failed_attempt_diagnostic(
                    stage_spec,
                    ctx,
                    stage,
                    attempt,
                    report,
                    threshold,
                    gate_decision,
                    feedback_items,
                ),
                ctx,
            )
            preview.setdefault("items", []).append(f"실패 진단 저장: {diagnostic['name']}")
        return {
            "passed": passed,
            "score": report.score,
            "threshold": threshold,
            "gate_tier": gate_decision.get("tier"),
            "gate_blocker_count": gate_decision.get("gate_blocker_count", 0),
            "feedback": feedback_items,
            "artifact": artifact,
            "checkpoint": checkpoint,
            "preview": preview,
        }

    spec = orchestrate_policy_generation(
        ctx,
        template_html,
        sample_htmls,
        after_stage=after_chapter,
        resume_checkpoint=resume_checkpoint,
    )
    ensure_policy_spec_base_keys(spec)
    spec = apply_final_integration_pass(spec, ctx, "initial_authoring")
    ensure_policy_spec_base_keys(spec)
    merge_continued_document_history(spec, ctx, previous_history)
    emit_progress(ctx, "stage_start", stage_key="11", stage_name="finalize", label="최종 검증 및 저장", message="전체 JSON 정합성을 검증하고 최종 HTML을 저장합니다.")
    validation = validate_policy_spec(spec, ctx.business_code)
    if not validation.ok:
        formatted_errors = "\n".join(f"- {error}" for error in validation.errors)
        quality_artifact = quality_report_artifact_payload(
            save_quality_report(build_quality_report(ctx, spec, validation, None, None, "fail"), ctx),
            ctx,
        )
        emit_progress(
            ctx,
            "stage_error",
            stage_key="11",
            stage_name="finalize",
            message="최종 JSON 검증에 실패했습니다.",
            error=formatted_errors,
            artifact=quality_artifact,
        )
        raise ValueError(f"정책서 JSON 검증에 실패했습니다.\n{formatted_errors}")
    critical_validation = validate_stage_critical(spec, ctx.business_code, "full")
    if not critical_validation.ok:
        formatted_errors = "\n".join(f"- {error}" for error in critical_validation.errors)
        quality_artifact = quality_report_artifact_payload(
            save_quality_report(build_quality_report(ctx, spec, validation, critical_validation, None, "fail"), ctx),
            ctx,
        )
        emit_progress(
            ctx,
            "stage_error",
            stage_key="11",
            stage_name="finalize",
            message="최종 Critical Gate 검증에 실패했습니다.",
            error=formatted_errors,
            artifact=quality_artifact,
        )
        raise ValueError(f"정책서 Critical Gate 검증에 실패했습니다.\n{formatted_errors}")

    # A resumed run can skip all chapter callbacks, so the last rendered HTML
    # snapshot may be empty. Always render the completed spec before the final
    # Inspector so it evaluates the actual policy document, not a blank buffer.
    document = normalize_sentence_breaks(render_policy_html(spec, template_html, ctx.template_type, "full"))

    final_report = None
    final_quality_status = "pass"
    final_completion_message = "정책서 생성이 완료되었습니다."
    if inspect_enabled:
        repair_attempt = 0
        while True:
            report_suffix = "final" if repair_attempt == 0 else f"final_recheck{repair_attempt}"
            emit_progress(
                ctx,
                "stage_update",
                stage_key="11",
                stage_name="finalize",
                message=(
                    "전체 문서 LLM inspector 최종 검수를 실행합니다."
                    if repair_attempt == 0
                    else f"Agent 보완 후 Final Inspector가 전체 문서를 다시 검수합니다. ({repair_attempt}/{ctx.inspector_max_loops})"
                ),
            )
            final_report = inspect_final_document(
                document,
                template_html,
                sample_htmls,
                ctx,
                "full",
                report_suffix,
                density_profile=spec.get("density_profile") if isinstance(spec.get("density_profile"), Mapping) else None,
                spec=spec,
                llm_client=(
                    client_for_stage_inspector(
                        inspector_llm_client,
                        final=True,
                        inspection_mode=ctx.inspection_mode,
                    )
                    if inspector_llm_client
                    else None
                ),
                llm_required=inspector_llm_required,
                llm_retry_callback=inspector_retry_callback(ctx, "11", "finalize", "Final Inspector"),
            )
            if final_inspection_gate_passed(final_report, ctx):
                break
            if repair_attempt >= ctx.inspector_max_loops:
                feedback = "\n".join(
                    f"- {finding.severity} / {finding.category}: {finding.title} - {finding.detail}"
                    for finding in final_report.findings
                )
                record_unresolved_final_inspector_issues(spec, final_report, ctx, repair_attempt)
                final_quality_status = "needs_review"
                final_completion_message = (
                    "정책서 생성은 완료되었습니다. Final Inspector 기준에 아직 못 미친 항목은 보완 필요 항목으로 저장했습니다."
                )
                emit_progress(
                    ctx,
                    "stage_update",
                    stage_key="11",
                    stage_name="finalize",
                    label="최종 검증 및 저장",
                    score=getattr(final_report, "score", None),
                    threshold=ctx.inspector_min_score,
                    message="최종 Inspector 보완 루프를 완료했고, 남은 항목은 보완 필요 상태로 저장합니다.",
                    preview={
                        "title": "Final Inspector 잔여 보완 항목",
                        "items": [
                            f"보완/재검수 횟수: {repair_attempt}/{ctx.inspector_max_loops}",
                            f"최종 점수: {getattr(final_report, 'score', '-')}",
                            "산출물은 저장하고, 남은 이슈는 품질 리포트와 문서 작업실에서 이어서 보완할 수 있게 남깁니다.",
                            *[line for line in feedback.splitlines()[:5] if line],
                        ],
                    },
                )
                break

            repair_attempt += 1
            remediation = final_remediation_feedback_by_chapter(final_report, ctx.inspector_min_score, repair_attempt)
            if not remediation:
                remediation = {
                    "final_check": [
                        {
                            "issue_id": "FINAL-GATE-SCORE",
                            "priority_tier": "P2",
                            "batch_label": f"Final Inspector repair {repair_attempt} / score batch",
                            "must_resolve": "Y",
                            "repair_scope": "최종 점검 기준",
                            "severity": "warn",
                            "category": "최종 검수",
                            "title": "최종 Inspector 점수 미달",
                            "detail": f"최종 Inspector 점수 {final_report.score}점이 기준 {ctx.inspector_min_score}점보다 낮습니다.",
                            "recommendation": "최종 점검 기준을 현재 문서의 남은 검수 항목에 맞게 보완하세요.",
                        }
                    ]
                }
            revision_feedback, chapter_remediation = split_final_remediation_for_revision(remediation)
            remediation_before_digest = final_remediation_digest(spec)
            revision_result = {"status": "skipped", "applied_update_count": 0}
            if revision_feedback:
                spec, revision_result = run_final_revision_agent(
                    spec,
                    ctx,
                    final_report,
                    revision_feedback,
                    repair_attempt,
                )
            if chapter_remediation:
                spec = run_final_remediation_agents(
                    spec,
                    ctx,
                    template_html,
                    sample_htmls,
                    final_report,
                    chapter_remediation,
                    repair_attempt,
                )
            spec = apply_final_integration_pass(spec, ctx, f"final_remediation_{repair_attempt}")
            merge_continued_document_history(spec, ctx, previous_history)
            validation = validate_policy_spec(spec, ctx.business_code)
            if not validation.ok:
                formatted_errors = "\n".join(f"- {error}" for error in validation.errors)
                emit_progress(
                    ctx,
                    "stage_error",
                    stage_key="11",
                    stage_name="finalize",
                    message="최종 Inspector 보완 후 JSON 검증에 실패했습니다.",
                    error=formatted_errors,
                )
                raise ValueError(f"최종 Inspector 보완 후 JSON 검증에 실패했습니다.\n{formatted_errors}")
            critical_validation = validate_stage_critical(spec, ctx.business_code, "full")
            if not critical_validation.ok:
                formatted_errors = "\n".join(f"- {error}" for error in critical_validation.errors)
                record_unresolved_final_critical_issues(spec, critical_validation.errors, ctx, repair_attempt)
                final_quality_status = "needs_review"
                final_completion_message = (
                    "정책서 생성은 완료되었습니다. Final Inspector 보완 후 남은 Critical Gate 항목은 보완 필요 상태로 저장했습니다."
                )
                emit_progress(
                    ctx,
                    "stage_update",
                    stage_key="11",
                    stage_name="finalize",
                    label="최종 검증 및 저장",
                    message="최종 보완 후 남은 Critical Gate 항목을 보완 필요 상태로 저장합니다.",
                    error=formatted_errors,
                    preview={
                        "title": "Critical Gate 잔여 보완 항목",
                        "items": [
                            f"보완/재검수 횟수: {repair_attempt}/{ctx.inspector_max_loops}",
                            "산출물은 저장하고, 남은 구조 이슈는 문서 작업실에서 이어서 보완할 수 있게 남깁니다.",
                            *[line for line in formatted_errors.splitlines()[:6] if line],
                        ],
                    },
                )
                document = normalize_sentence_breaks(render_policy_html(spec, template_html, ctx.template_type, "full"))
                break
            document = normalize_sentence_breaks(render_policy_html(spec, template_html, ctx.template_type, "full"))
            if final_remediation_digest(spec) == remediation_before_digest:
                record_unresolved_final_inspector_issues(spec, final_report, ctx, repair_attempt)
                final_quality_status = "needs_review"
                final_completion_message = (
                    "정책서 생성은 완료되었습니다. Final Inspector 보완점은 자동 patch 대상이 명확하지 않아 보완 필요 항목으로 저장했습니다."
                )
                emit_progress(
                    ctx,
                    "stage_update",
                    stage_key="11",
                    stage_name="finalize",
                    label="최종 검증 및 저장",
                    score=getattr(final_report, "score", None),
                    threshold=ctx.inspector_min_score,
                    message="자동 보완이 실제 문서 내용을 바꾸지 않아 추가 LLM 재검수를 생략하고 잔여 항목으로 저장합니다.",
                    preview={
                        "title": "Final Inspector 보완 보류",
                        "items": [
                            f"보완/재검수 횟수: {repair_attempt}/{ctx.inspector_max_loops}",
                            "새 행 추가나 장 전체 재작성 없이 안전하게 고칠 수 있는 대상이 명확하지 않았습니다.",
                            "남은 항목은 문서 작업실의 보완 기능에서 선택적으로 이어서 처리할 수 있습니다.",
                        ],
                    },
                )
                break

    if merge_continued_document_history(spec, ctx, previous_history):
        document = normalize_sentence_breaks(render_policy_html(spec, template_html, ctx.template_type, "full"))

    emit_progress(ctx, "stage_update", stage_key="11", stage_name="finalize", message="검증된 JSON 스펙을 저장합니다.")
    spec_json = json.dumps(spec, ensure_ascii=False, indent=2)
    spec_path = output_dir / make_spec_filename(ctx)
    spec_path.write_text(spec_json, encoding="utf-8")
    versioned_spec_path = output_dir / make_versioned_spec_filename(ctx)
    versioned_spec_path.write_text(spec_json, encoding="utf-8")
    blueprint = spec.get("meta", {}).get("authoring_blueprint", {}) if isinstance(spec.get("meta"), dict) else {}
    if isinstance(blueprint, dict) and blueprint:
        blueprint_path = output_dir / make_blueprint_filename(ctx)
        blueprint_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")

    final_path = output_dir / make_output_filename(ctx)
    final_path.write_text(document, encoding="utf-8")
    bpmn_path = output_dir / make_bpmn_output_filename(ctx)
    write_bpmn_artifacts(spec, bpmn_path)
    artifact_drift = evaluate_policy_artifact_drift(final_path, output_root=output_dir, reports_root=PROJECT_ROOT / "reports")
    if artifact_drift.get("status") == "fail" and final_quality_status == "pass":
        final_quality_status = "needs_review"
    quality_report = build_quality_report(ctx, spec, validation, critical_validation, final_report, final_quality_status, artifact_drift=artifact_drift)
    quality_path = save_quality_report(quality_report, ctx)
    emit_progress(
        ctx,
        "stage_complete",
        stage_key="11",
        stage_name="finalize",
        label="최종 검증 및 저장",
        message=final_completion_message,
        artifact=stage_artifact_payload(final_path, ctx),
        checkpoint=quality_report_artifact_payload(quality_path, ctx),
        preview={
            "title": "최종 품질 리포트",
            "items": quality_preview_items(quality_report),
        },
    )
    return final_path


def normalized_inspection_mode(args: argparse.Namespace) -> str:
    if getattr(args, "no_inspect", False):
        return "none"
    value = str(getattr(args, "inspection_mode", "chapter-final") or "chapter-final").strip().casefold()
    if value in {"chapter-final", "chapter_final", "chapter", "all", "auto"}:
        return "chapter-final"
    if value in {"final-only", "final_only", "final"}:
        return "final-only"
    if value in {"none", "off", "no", "skip"}:
        return "none"
    return "chapter-final"


def emit_progress(ctx: PolicyContext, event: str, **payload: object) -> None:
    callback = getattr(ctx, "progress_callback", None)
    if not callable(callback):
        return
    callback(event, payload)


def run_llm_preflight(ctx: PolicyContext) -> None:
    if not llm_preflight_enabled():
        return
    client = LLMClient.from_context(ctx)
    if not client.enabled:
        return
    emit_progress(
        ctx,
        "stage_start",
        stage_key="00",
        stage_name="preflight",
        label="LLM 연결 점검",
        message="긴 정책서 작성을 시작하기 전에 API 키, 모델, 추론 강도, 네트워크 연결을 작은 호출로 먼저 확인합니다.",
        preview={
            "title": "LLM 사전 연결 점검",
            "items": [
                f"모델: {client.model}",
                f"추론 강도: {client.reasoning_effort or '기본값'}",
                "실패하면 본문 작성에 들어가지 않아 토큰 낭비를 줄입니다.",
            ],
        },
    )
    try:
        client.preflight_check()
    except Exception as exc:
        emit_progress(
            ctx,
            "stage_error",
            stage_key="00",
            stage_name="preflight",
            label="LLM 연결 점검",
            message="LLM 연결 사전 점검에 실패했습니다. 네트워크나 모델 설정이 안정화된 뒤 이어서 다시 시도해 주세요.",
            error=str(exc),
            preview={
                "title": "LLM 연결 점검 실패",
                "items": [
                    "정책서 본문 작성은 아직 시작하지 않았습니다.",
                    "API 키, 모델명, 추론 강도, 네트워크 연결을 확인해 주세요.",
                    str(exc)[:180],
                ],
            },
        )
        raise
    emit_progress(
        ctx,
        "stage_complete",
        stage_key="00",
        stage_name="preflight",
        label="LLM 연결 점검",
        message="LLM 연결 점검을 통과했습니다. 이제 주제 학습과 정책서 작성을 진행합니다.",
        preview={
            "title": "LLM 연결 점검 완료",
            "items": [
                "API 호출 성공",
                "모델 및 추론 강도 확인 완료",
                "이후 일시 오류는 Retry-After와 자동 재시도로 처리합니다.",
            ],
        },
    )


def inspector_retry_callback(ctx: PolicyContext, stage_key: str, stage_name: str, label: str):
    def callback(event: Mapping[str, object]) -> None:
        attempt = int(event.get("attempt") or 1)
        max_attempts = int(event.get("max_attempts") or attempt)
        retry_after = float(event.get("retry_after_seconds") or 0)
        error = str(event.get("error") or "")
        emit_progress(
            ctx,
            "stage_update",
            stage_key=stage_key,
            stage_name=stage_name,
            label=label,
            message=f"LLM Inspector 일시 오류로 {retry_after:.0f}초 후 자동 재시도합니다. ({attempt}/{max_attempts})",
            preview={
                "title": "Inspector 자동 재시도",
                "items": [
                    f"재시도 대상: {label}",
                    f"재시도 횟수: {attempt}/{max_attempts}",
                    f"대기 시간: {retry_after:.0f}초",
                    f"오류 요약: {error[:180]}",
                    "로컬 대체 작성은 수행하지 않고 같은 단계에서 LLM Inspector를 다시 호출합니다.",
                ],
            },
        )

    return callback


def inspect_final_document(
    document: str,
    template_html: str,
    sample_htmls: List[str],
    ctx: PolicyContext,
    scope: str,
    report_suffix: str,
    density_profile: Mapping[str, object] | None = None,
    spec: Mapping[str, object] | None = None,
    llm_client: object | None = None,
    llm_required: bool = False,
    llm_retry_callback: object | None = None,
) -> object:
    report = inspect_policy_document(
        document,
        template_html=template_html,
        sample_htmls=sample_htmls,
        template_type=ctx.template_type,
        scope=scope,
        topic=ctx.topic,
        brief=ctx.brief,
        inspection_mode=ctx.inspection_mode,
        density_profile=density_profile,
        llm_client=llm_client,
        llm_required=llm_required,
        llm_retry_callback=llm_retry_callback,
    )
    if spec is not None:
        json_llm_client = llm_client if str(getattr(llm_client, "writer_mode", "") or "").strip().casefold() == "mock" else None
        json_report = inspect_policy_json_spec(
            spec,
            template_type=ctx.template_type,
            scope=scope,
            chapter_key="",
            topic=ctx.topic,
            brief=ctx.brief,
            llm_client=json_llm_client,
            llm_required=False,
        )
        report = merge_inspection_reports(report, json_report, source_key="json_final_inspector")
    save_inspection_report(report, make_output_filename(ctx), report_suffix)
    return report


def apply_final_integration_pass(spec: dict, ctx: PolicyContext, source: str) -> dict:
    """Lightweight deterministic integration pass before final validation/render.

    This is intentionally not a new writing phase. It keeps the template/schema
    unchanged and records whether the document is ready for final Inspector from
    the perspective of cross-chapter links and policy-item decision dimensions.
    """
    if not isinstance(spec, dict):
        return spec
    deduplicate_function_names(spec)
    reconcile_process_function_links(spec)
    function_updates = normalize_process_related_refs(spec, "related_functions", "functions")
    policy_updates = normalize_process_related_refs(spec, "related_policies", "policy_groups")
    policy_detail_rows = spec.get("policy_details", []) if isinstance(spec.get("policy_details"), list) else []
    weak_policy_details = [
        str(detail.get("id", "") or detail.get("name", "")).strip()
        for detail in policy_detail_rows
        if isinstance(detail, Mapping) and not policy_detail_quality_dimensions(detail)
    ]
    duplicate_policy_names = duplicate_item_names(spec.get("policy_groups", []))
    duplicate_function_names = duplicate_item_names(spec.get("functions", []))
    manual_patch_candidates = build_final_integration_patch_candidates(
        spec,
        weak_policy_details=weak_policy_details,
        duplicate_policy_names=duplicate_policy_names,
        duplicate_function_names=duplicate_function_names,
    )
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta.setdefault("final_integration_runs", []).append(
            {
                "source": source,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "rule": (
                    "최종 렌더링 전 장별 산출물의 연결 표기와 정책 항목 판단축을 점검한다. "
                    "자동 수정은 안전한 참조 라벨 보정에 한정하고, 문서 양식과 챕터 구조 및 정책 본문은 변경하지 않는다."
                ),
                "updated_related_function_refs": function_updates,
                "updated_related_policy_refs": policy_updates,
                "safe_auto_update_count": function_updates + policy_updates,
                "weak_policy_detail_ids": weak_policy_details[:20],
                "duplicate_policy_names": duplicate_policy_names[:12],
                "duplicate_function_names": duplicate_function_names[:12],
                "manual_patch_candidates": manual_patch_candidates[:40],
                "manual_patch_candidate_count": len(manual_patch_candidates),
                "status": "watch" if manual_patch_candidates else "ok",
            }
        )
    return spec


def build_final_integration_patch_candidates(
    spec: Mapping[str, object],
    *,
    weak_policy_details: Sequence[str],
    duplicate_policy_names: Sequence[str],
    duplicate_function_names: Sequence[str],
) -> List[dict]:
    """Return bounded patch candidates without rewriting document content.

    Final integration is deliberately conservative. It may diagnose where a
    patch-only remediation should happen, but it must not invent new scope or
    rewrite chapters after they passed their own gates.
    """
    candidates: List[dict] = []
    candidates.extend(weak_policy_detail_candidates(spec, weak_policy_details))
    candidates.extend(duplicate_name_candidates("policy_group", duplicate_policy_names))
    candidates.extend(duplicate_name_candidates("function", duplicate_function_names))
    candidates.extend(process_link_gap_candidates(spec))
    candidates.extend(function_process_gap_candidates(spec))
    candidates.extend(policy_detail_group_gap_candidates(spec))
    return dedupe_final_integration_candidates(candidates)


def weak_policy_detail_candidates(spec: Mapping[str, object], weak_policy_details: Sequence[str]) -> List[dict]:
    if not weak_policy_details:
        return []
    details = {
        str(detail.get("id", "") or detail.get("name", "")).strip(): detail
        for detail in spec.get("policy_details", [])
        if isinstance(detail, Mapping)
    } if isinstance(spec.get("policy_details", []), list) else {}
    candidates: List[dict] = []
    for target_id in list(weak_policy_details)[:20]:
        detail = details.get(str(target_id))
        target_name = str(detail.get("name", "")).strip() if isinstance(detail, Mapping) else ""
        candidates.append(
            {
                "type": "weak_policy_detail_dimensions",
                "priority": "P2",
                "target": target_id,
                "scope": "policy_details",
                "safe_auto_fix": False,
                "title": "정책 항목 판단축 보강 필요",
                "detail": f"{target_id} {target_name}".strip(),
                "recommendation": "기존 정책 그룹 안에서 허용·제한·조건·예외·고지·이력·BSS 반영 중 필요한 판단축만 patch로 보강한다.",
            }
        )
    return candidates


def duplicate_name_candidates(kind: str, duplicate_names: Sequence[str]) -> List[dict]:
    label = "정책 그룹" if kind == "policy_group" else "기능"
    return [
        {
            "type": f"duplicate_{kind}_name",
            "priority": "P3",
            "target": name,
            "scope": f"{kind}s",
            "safe_auto_fix": False,
            "title": f"{label} 중복명 정리 후보",
            "detail": name,
            "recommendation": "ID와 연결 관계를 유지한 채 명칭만 역할 차이가 드러나도록 patch로 구분한다.",
        }
        for name in list(duplicate_names)[:12]
    ]


def process_link_gap_candidates(spec: Mapping[str, object]) -> List[dict]:
    processes = spec.get("processes", [])
    if not isinstance(processes, list):
        return []
    candidates: List[dict] = []
    for process in processes:
        if not isinstance(process, Mapping):
            continue
        process_id = str(process.get("id", "")).strip()
        process_name = str(process.get("name", "")).strip()
        if not process_id:
            continue
        if not list_values(process.get("related_functions")):
            candidates.append(
                {
                    "type": "process_missing_related_functions",
                    "priority": "P2",
                    "target": process_id,
                    "scope": "processes.related_functions",
                    "safe_auto_fix": False,
                    "title": "프로세스-기능 연결 보강 필요",
                    "detail": f"{process_id} {process_name}".strip(),
                    "recommendation": "새 기능을 만들기보다 기존 기능 ID 중 해당 프로세스를 수행하는 기능을 연결한다.",
                }
            )
        if not list_values(process.get("related_policies")):
            candidates.append(
                {
                    "type": "process_missing_related_policies",
                    "priority": "P2",
                    "target": process_id,
                    "scope": "processes.related_policies",
                    "safe_auto_fix": False,
                    "title": "프로세스-정책 연결 보강 필요",
                    "detail": f"{process_id} {process_name}".strip(),
                    "recommendation": "새 정책을 만들기보다 기존 정책 그룹 ID 중 해당 프로세스 판단 기준을 연결한다.",
                }
            )
    return candidates[:24]


def function_process_gap_candidates(spec: Mapping[str, object]) -> List[dict]:
    process_ids = {
        str(process.get("id", "")).strip()
        for process in spec.get("processes", [])
        if isinstance(process, Mapping) and str(process.get("id", "")).strip()
    } if isinstance(spec.get("processes", []), list) else set()
    candidates: List[dict] = []
    for function in spec.get("functions", []) if isinstance(spec.get("functions", []), list) else []:
        if not isinstance(function, Mapping):
            continue
        function_id = str(function.get("id", "")).strip()
        process_id = str(function.get("process_id", "")).strip()
        if function_id and process_id and process_id not in process_ids:
            candidates.append(
                {
                    "type": "function_unknown_process_id",
                    "priority": "P2",
                    "target": function_id,
                    "scope": "functions.process_id",
                    "safe_auto_fix": False,
                    "title": "기능의 프로세스 참조 확인 필요",
                    "detail": f"{function_id} → {process_id}",
                    "recommendation": "기능의 process_id를 실제 프로세스 ID로 patch하거나, 연결 대상이 없으면 프로세스 누락 여부를 별도 보완한다.",
                }
            )
    return candidates[:20]


def policy_detail_group_gap_candidates(spec: Mapping[str, object]) -> List[dict]:
    policy_ids = {
        str(group.get("id", "")).strip()
        for group in spec.get("policy_groups", [])
        if isinstance(group, Mapping) and str(group.get("id", "")).strip()
    } if isinstance(spec.get("policy_groups", []), list) else set()
    candidates: List[dict] = []
    for detail in spec.get("policy_details", []) if isinstance(spec.get("policy_details", []), list) else []:
        if not isinstance(detail, Mapping):
            continue
        detail_id = str(detail.get("id", "")).strip()
        policy_id = str(detail.get("policy_id", "")).strip()
        if detail_id and policy_id and policy_id not in policy_ids:
            candidates.append(
                {
                    "type": "policy_detail_unknown_policy_group",
                    "priority": "P1",
                    "target": detail_id,
                    "scope": "policy_details.policy_id",
                    "safe_auto_fix": False,
                    "title": "정책 항목의 정책 그룹 참조 확인 필요",
                    "detail": f"{detail_id} → {policy_id}",
                    "recommendation": "정책 항목의 policy_id를 실제 정책 그룹 ID로 patch하거나, 필요한 정책 그룹 누락 여부를 보완한다.",
                }
            )
    return candidates[:20]


def dedupe_final_integration_candidates(candidates: Sequence[Mapping[str, object]]) -> List[dict]:
    deduped: List[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            str(candidate.get("type", "")),
            str(candidate.get("target", "")),
            str(candidate.get("scope", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(candidate))
    return deduped


def list_values(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def normalize_process_related_refs(spec: dict, field_name: str, target_key: str) -> int:
    target_rows = spec.get(target_key, []) if isinstance(spec.get(target_key), list) else []
    targets = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in target_rows
        if isinstance(item, Mapping) and str(item.get("id", "")).strip()
    }
    if not targets:
        return 0
    updates = 0
    for process in spec.get("processes", []) if isinstance(spec.get("processes"), list) else []:
        if not isinstance(process, dict):
            continue
        refs = process.get(field_name, [])
        if not isinstance(refs, list):
            continue
        normalized = []
        for ref in refs:
            text = str(ref or "").strip()
            target_id = referenced_id(text, targets)
            if target_id and targets.get(target_id) and targets[target_id] not in text:
                text = f"{target_id} {targets[target_id]}"
                updates += 1
            normalized.append(text)
        process[field_name] = normalized
    return updates


def referenced_id(text: str, targets: Mapping[str, str]) -> str:
    if text in targets:
        return text
    for target_id in targets:
        if re.search(rf"(?<![A-Z0-9-]){re.escape(target_id)}(?![A-Z0-9-])", text):
            return target_id
    return ""


def duplicate_item_names(items: object) -> List[str]:
    if not isinstance(items, list):
        return []
    counts: Dict[str, int] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = re.sub(r"\s+", " ", str(item.get("name", "") or "")).strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def run_final_remediation_agents(
    spec: dict,
    ctx: PolicyContext,
    template_html: str,
    sample_htmls: Sequence[str],
    final_report,
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
    repair_attempt: int,
) -> dict:
    stages = chapter_stages(ctx.template_type)
    stage_by_key = {stage.agent.chapter_key: stage for stage in stages}
    runtime = build_final_remediation_runtime(ctx, template_html, sample_htmls, spec)
    repaired_spec = dict(spec)
    feedback_by_chapter = prioritize_final_remediation_feedback(feedback_by_chapter)
    feedback_by_chapter = expand_final_remediation_dependencies(feedback_by_chapter, repair_attempt)
    total_feedback = sum(len(items) for items in feedback_by_chapter.values())
    emit_progress(
        ctx,
        "stage_update",
        stage_key="11",
        stage_name="finalize",
        label="Final Inspector 보완",
        score=getattr(final_report, "score", None),
        threshold=ctx.inspector_min_score,
        preview={
            "title": f"최종 검수 보완 {repair_attempt}회차",
            "items": [
                f"Inspector 지적 {total_feedback}건을 담당 Agent별로 분배했습니다.",
                "각 Agent는 지적된 항목만 patch 방식으로 보완하고, 보완 후 Final Inspector가 다시 전체 문서를 검수합니다.",
            ],
        },
        message="Final Inspector 결과를 담당 Agent에게 나눠 보내 보완을 시작합니다.",
    )
    for stage in stages:
        chapter_feedback = list(feedback_by_chapter.get(stage.agent.chapter_key, ()) or ())
        if not chapter_feedback:
            continue
        emit_progress(
            ctx,
            "stage_start",
            stage_key=stage.key,
            stage_name=stage.name,
            label=stage.agent.display_name,
            attempt=repair_attempt,
            message=(
                f"Final Inspector가 찾은 보완점 {len(chapter_feedback)}건을 "
                f"{stage.agent.display_name}가 반영합니다."
            ),
        )
        if stage.agent.chapter_key not in stage_by_key:
            continue
        repaired_spec = stage.agent.write(
            repaired_spec,
            runtime,
            attempt=repair_attempt + 100,
            feedback=chapter_feedback,
        )
        emit_progress(
            ctx,
            "stage_complete",
            stage_key=stage.key,
            stage_name=stage.name,
            label=stage.agent.display_name,
            attempt=repair_attempt,
            message=(
                f"{stage.agent.display_name} 보완이 끝났습니다. "
                "다음 보완 대상이 있으면 이어서 처리하고, 마지막에 Final Inspector가 다시 검수합니다."
            ),
        )
        save_generation_checkpoint(
            repaired_spec,
            ctx,
            stage,
            repair_attempt + 100,
            True,
            f"Final Inspector 보완 {repair_attempt}회차 - {stage.agent.display_name} 완료",
        )
    record_final_remediation_run(repaired_spec, final_report, feedback_by_chapter, repair_attempt)
    save_generation_checkpoint(
        repaired_spec,
        ctx,
        SimpleNamespace(key="11", name="finalize", agent=SimpleNamespace(display_name="Final Inspector 보완")),
        repair_attempt + 100,
        True,
        f"Final Inspector 보완 {repair_attempt}회차 전체 완료",
    )
    return repaired_spec


FINAL_REVISION_COLLECTION_FIELDS = {
    "terms": {"name", "description"},
    "actors": {"name", "description"},
    "usecases": {"actor", "name", "description", "process_target"},
    "states": {"name", "description", "next_action"},
    "state_transitions": {"usecase_ids", "current_state", "event", "next_state", "criteria"},
    "processes": {"usecase_id", "name", "description", "related_functions", "related_policies"},
    "functions": {"process_id", "process_ids", "name", "description", "details"},
    "policy_groups": {"name", "description", "items"},
    "policy_details": {"policy_id", "name", "content"},
}
FINAL_REVISION_ID_PATTERN = re.compile(r"\b(?:TM|ACT|US|ST|PR|FN|PG|PI)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")


def split_final_remediation_for_revision(
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
) -> Tuple[Dict[str, List[Mapping[str, object]]], Dict[str, List[Mapping[str, object]]]]:
    """Split final findings into integrated patch work and chapter-agent work."""
    prioritized = prioritize_final_remediation_feedback(feedback_by_chapter)
    if final_remediation_has_root_p1(prioritized):
        return {}, prioritized
    revision_feedback: Dict[str, List[Mapping[str, object]]] = {}
    chapter_feedback: Dict[str, List[Mapping[str, object]]] = {}
    for chapter, items in feedback_by_chapter.items():
        for item in items or []:
            target = chapter_feedback if requires_chapter_final_remediation(str(chapter), item) else revision_feedback
            target.setdefault(str(chapter), []).append(item)
    return revision_feedback, chapter_feedback


def final_remediation_has_root_p1(feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]]) -> bool:
    for chapter in ("actors", "usecases", "state"):
        if any(str(item.get("priority_tier", "") or "").upper() == "P1" for item in feedback_by_chapter.get(chapter, ())):
            return True
    return False


def requires_chapter_final_remediation(chapter: str, item: Mapping[str, object]) -> bool:
    priority = str(item.get("priority_tier", "") or "").upper()
    mode = str(item.get("remediation_mode", "") or "").strip()
    text = " ".join(
        str(item.get(key, "") or "")
        for key in (
            "category",
            "title",
            "detail",
            "root_cause",
            "required_change",
            "recommendation",
            "target_path",
        )
    )
    if chapter == "policies":
        return priority == "P1" and policy_feedback_requires_chapter_remediation(text)
    structural_markers = (
        "구조",
        "계층",
        "입자도",
        "절차형",
        "process_target",
        "1:1",
        "상태 전이",
        "액터 경계",
        "actor_boundary",
        "유즈케이스",
        "blueprint",
        "Blueprint",
    )
    if mode in {"scoped_full_revision", "blueprint_realign_revision"}:
        return True
    if priority == "P1" and chapter in {"actors", "usecases", "state"}:
        return True
    if priority == "P1" and any(marker in text for marker in structural_markers):
        return True
    return False


def policy_feedback_requires_chapter_remediation(text: str) -> bool:
    """Keep policy content feedback patch-first unless new rows are required."""
    structural_markers = (
        "정책 그룹 누락",
        "정책 목록 누락",
        "정책 상세가 없음",
        "정책 상세 누락",
        "policy_group_without_detail",
        "새 정책",
        "신규 정책",
        "정책 그룹 추가",
        "정책 상세 추가",
        "행 추가",
        "ID 추가",
        "new policy",
        "missing policy",
    )
    return any(marker in text for marker in structural_markers)


FINAL_REMEDIATION_DIGEST_KEYS = (
    "overview",
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
    "final_check",
)


def final_remediation_digest(spec: Mapping[str, object]) -> str:
    """Hash document content touched by final remediation, excluding run metadata."""
    payload = {key: spec.get(key, []) for key in FINAL_REMEDIATION_DIGEST_KEYS}
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    payload["diagrams"] = {
        "usecase_diagram": meta.get("usecase_diagram", ""),
        "state_diagram": meta.get("state_diagram", ""),
        "process_diagram": meta.get("process_diagram", ""),
    }
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_final_revision_agent(
    spec: dict,
    ctx: PolicyContext,
    final_report,
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
    repair_attempt: int,
) -> Tuple[dict, dict]:
    feedback_items = flatten_feedback_items(feedback_by_chapter)
    result_meta = {
        "attempt": repair_attempt,
        "status": "skipped",
        "feedback_count": len(feedback_items),
        "applied_update_count": 0,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rule": (
            "Final Revision Agent가 Final Inspector finding 중 구조적 P1이 아닌 항목을 제한된 JSON patch로 먼저 보완한다. "
            "새 ID 생성, 삭제, 장 전체 재작성은 금지한다."
        ),
    }
    if not feedback_items:
        return spec, result_meta
    base_client = LLMClient.from_context(ctx)
    revision_client = client_for_revision(base_client, attempt=repair_attempt)
    if not revision_client.enabled:
        result_meta["status"] = "llm_disabled"
        record_final_revision_agent_run(spec, result_meta)
        return spec, result_meta
    emit_progress(
        ctx,
        "stage_update",
        stage_key="11",
        stage_name="finalize",
        label="Final Revision Agent",
        message="Final Inspector 보완점 중 통합 patch로 처리 가능한 항목을 먼저 보완합니다.",
        preview={
            "title": f"통합 보완 {repair_attempt}회차",
            "items": [
                f"통합 patch 후보: {len(feedback_items)}건",
                "기존 ID와 장 구조는 유지하고 지정 필드만 수정합니다.",
                "구조적 P1은 담당 Chapter Agent로 별도 이관합니다.",
            ],
        },
    )
    try:
        payload = revision_client.generate_json(
            schema_name="final_revision_patch",
            schema=final_revision_patch_schema(),
            instructions=final_revision_system_instructions(),
            input_messages=[
                {
                    "role": "user",
                    "content": build_final_revision_prompt(spec, ctx, final_report, feedback_by_chapter),
                }
            ],
        )
    except Exception as exc:  # Final chapter agents can still handle the fallback.
        result_meta["status"] = "error"
        result_meta["error"] = str(exc)[:500]
        record_final_revision_agent_run(spec, result_meta)
        return spec, result_meta
    revised_spec = copy.deepcopy(spec)
    applied = apply_final_revision_patch(revised_spec, payload)
    result_meta["status"] = "ok" if applied else "no_changes"
    result_meta["model"] = revision_client.model
    result_meta["reasoning_effort"] = revision_client.reasoning_effort
    result_meta["applied_update_count"] = len(applied)
    result_meta["applied_updates"] = applied[:30]
    result_meta["notes"] = payload.get("notes", []) if isinstance(payload.get("notes"), list) else []
    record_final_revision_agent_run(revised_spec, result_meta)
    if applied:
        save_generation_checkpoint(
            revised_spec,
            ctx,
            SimpleNamespace(key="11_revision", name="final_revision", agent=SimpleNamespace(display_name="Final Revision Agent")),
            repair_attempt + 100,
            True,
            f"Final Revision Agent 보완 {repair_attempt}회차 완료",
        )
    return revised_spec, result_meta


def flatten_feedback_items(feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]]) -> List[dict]:
    items: List[dict] = []
    for chapter, chapter_items in feedback_by_chapter.items():
        for item in chapter_items or []:
            if not isinstance(item, Mapping):
                continue
            payload = dict(item)
            payload.setdefault("chapter", str(chapter))
            items.append(payload)
    return items


def record_final_revision_agent_run(spec: dict, result_meta: Mapping[str, object]) -> None:
    spec.setdefault("meta", {}).setdefault("final_revision_agent_runs", []).append(dict(result_meta))


def final_revision_system_instructions() -> str:
    return (
        "You are Final Revision Agent for NC policy documents. "
        "Return only schema-valid JSON. Apply bounded patch edits only. "
        "Do not rewrite whole chapters, create new IDs, delete rows, change template structure, or copy requirements verbatim."
    )


def build_final_revision_prompt(
    spec: Mapping[str, object],
    ctx: PolicyContext,
    final_report,
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
) -> str:
    feedback_items = flatten_feedback_items(feedback_by_chapter)
    return "\n\n".join(
        [
            f"정책서 주제: {ctx.topic}",
            f"Final Inspector 점수: {getattr(final_report, 'score', '-')}",
            f"통과 기준: {ctx.inspector_min_score}",
            "역할: Final Inspector finding 중 구조적 P1이 아닌 항목을 기존 JSON 안에서 통합 patch로 보완한다.",
            policy_style_anchor_for_prompt("final_check"),
            (
                "수정 원칙:\n"
                "- 기존 ID, 장 구조, 템플릿 양식은 유지한다.\n"
                "- updates는 한 항목의 한 필드만 수정한다. field에는 수정 필드명을, 문자열 필드는 value에, 배열 필드는 values에 넣는다.\n"
                "- 새 행 추가, 삭제, 전체 장 재작성, 요구사항 원문 복사는 금지한다.\n"
                "- 수정 불가능하거나 구조 재설계가 필요한 항목은 updates를 만들지 말고 notes에 이유를 쓴다.\n"
                "- 정책 항목 보완은 허용·제한·조건·횟수·시간·예외·고지·이력·BSS 반영 기준 중 필요한 판단축만 추가한다."
            ),
            "Final Inspector 보완 요청:\n" + json.dumps(final_revision_feedback_pack(feedback_by_chapter), ensure_ascii=False, indent=2),
            "현재 정책서 JSON 요약:\n" + json.dumps(final_revision_spec_pack(spec, feedback_items), ensure_ascii=False, indent=2),
            "반환 형식: final_revision_patch schema에 맞춰 updates와 notes만 반환한다.",
        ]
    )


def final_revision_feedback_pack(feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]]) -> dict:
    return {
        "by_chapter": {
            str(chapter): [
                {
                    "issue_id": item.get("issue_id", ""),
                    "priority_tier": item.get("priority_tier", ""),
                    "category": item.get("category", ""),
                    "title": item.get("title", ""),
                    "target_path": item.get("target_path", ""),
                    "detail": short_text(item.get("detail", ""), 500),
                    "required_change": short_text(item.get("required_change", ""), 500),
                    "patch_hint": short_text(item.get("patch_hint", ""), 500),
                    "recommendation": short_text(item.get("recommendation", ""), 700),
                    "acceptance_check": short_text(item.get("acceptance_check", ""), 400),
                }
                for item in items or []
                if isinstance(item, Mapping)
            ]
            for chapter, items in feedback_by_chapter.items()
        }
    }


def final_revision_spec_pack(spec: Mapping[str, object], feedback_items: Sequence[Mapping[str, object]]) -> dict:
    target_ids = feedback_target_ids(feedback_items)
    feedback_text = final_revision_feedback_search_text(feedback_items)
    chapters = {str(item.get("chapter", "") or "") for item in feedback_items}
    return {
        "meta": {
            "topic": spec.get("meta", {}).get("topic", "") if isinstance(spec.get("meta"), Mapping) else "",
            "template_type": spec.get("meta", {}).get("template_type", "") if isinstance(spec.get("meta"), Mapping) else "",
        },
        "terms": compact_revision_collection(spec.get("terms", []), ("id", "name", "description"), target_ids, feedback_text, 24)
        if "terms_refinement" in chapters or has_prefix_id(target_ids, "TM")
        else [],
        "actors": compact_revision_collection(spec.get("actors", []), ("id", "name", "description"), target_ids, feedback_text, 24)
        if "actors" in chapters or has_prefix_id(target_ids, "ACT")
        else [],
        "usecases": compact_revision_collection(spec.get("usecases", []), ("id", "actor", "name", "description", "process_target"), target_ids, feedback_text, 40)
        if chapters & {"usecases", "state", "process"} or has_prefix_id(target_ids, "US")
        else [],
        "states": compact_revision_collection(spec.get("states", []), ("id", "name", "description", "next_action"), target_ids, feedback_text, 40)
        if "state" in chapters or has_prefix_id(target_ids, "ST")
        else [],
        "state_transitions": compact_revision_collection(spec.get("state_transitions", []), ("usecase_ids", "current_state", "event", "next_state", "criteria"), target_ids, feedback_text, 48)
        if "state" in chapters
        else [],
        "processes": compact_revision_collection(spec.get("processes", []), ("id", "usecase_id", "name", "description", "related_functions", "related_policies"), target_ids, feedback_text, 60)
        if chapters & {"process", "functions", "policies"} or has_prefix_id(target_ids, "PR")
        else [],
        "functions": compact_revision_collection(spec.get("functions", []), ("id", "process_id", "process_ids", "name", "description", "details"), target_ids, feedback_text, 60)
        if chapters & {"process", "functions", "policies"} or has_prefix_id(target_ids, "FN")
        else [],
        "policy_groups": compact_revision_collection(spec.get("policy_groups", []), ("id", "name", "description", "items"), target_ids, feedback_text, 60)
        if "policies" in chapters or has_prefix_id(target_ids, "PG")
        else [],
        "policy_details": compact_revision_collection(spec.get("policy_details", []), ("id", "policy_id", "name", "content"), target_ids, feedback_text, 80)
        if "policies" in chapters or has_prefix_id(target_ids, "PI")
        else [],
        "final_check": [short_text(item, 160) for item in spec.get("final_check", [])[:20]]
        if "final_check" in chapters and isinstance(spec.get("final_check"), list)
        else [],
    }


def feedback_target_ids(feedback_items: Sequence[Mapping[str, object]]) -> set[str]:
    ids: set[str] = set()
    for item in feedback_items:
        text = " ".join(str(item.get(key, "") or "") for key in ("target_path", "detail", "required_change", "patch_hint", "recommendation"))
        ids.update(FINAL_REVISION_ID_PATTERN.findall(text))
    return ids


def final_revision_feedback_search_text(feedback_items: Sequence[Mapping[str, object]]) -> str:
    parts: List[str] = []
    for item in feedback_items:
        parts.extend(
            str(item.get(key, "") or "")
            for key in ("target_path", "title", "detail", "required_change", "patch_hint", "recommendation", "acceptance_check")
        )
    return normalize_revision_match_text(" ".join(parts))


def has_prefix_id(ids: set[str], prefix: str) -> bool:
    return any(item.startswith(f"{prefix}-") for item in ids)


def compact_revision_collection(
    values: object,
    fields: Sequence[str],
    target_ids: set[str],
    feedback_text: str,
    max_items: int,
) -> List[dict]:
    if not isinstance(values, list):
        return []
    items = [item for item in values if isinstance(item, Mapping)]
    prioritized = sorted(
        items,
        key=lambda item: revision_item_priority(item, target_ids, feedback_text),
    )
    compacted: List[dict] = []
    for item in prioritized[:max_items]:
        compacted.append({field: compact_revision_value(item.get(field)) for field in fields if field in item})
    return compacted


def revision_item_priority(item: Mapping[str, object], target_ids: set[str], feedback_text: str) -> Tuple[int, str]:
    identity = revision_item_identity(item)
    if identity and identity in target_ids:
        return (0, identity)
    if feedback_text and revision_item_mentions_feedback(item, feedback_text):
        return (1, identity)
    return (2, identity)


def revision_item_identity(item: Mapping[str, object]) -> str:
    return str(item.get("id") or item.get("process_id") or item.get("function_id") or "").strip()


def revision_item_mentions_feedback(item: Mapping[str, object], feedback_text: str) -> bool:
    candidates = [
        item.get("id"),
        item.get("policy_id"),
        item.get("process_id"),
        item.get("function_id"),
        item.get("name"),
        item.get("current_state"),
        item.get("event"),
        item.get("next_state"),
    ]
    for candidate in candidates:
        token = normalize_revision_match_text(candidate)
        if len(token) >= 3 and token in feedback_text:
            return True
    return False


def normalize_revision_match_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().casefold()


def compact_revision_value(value: object) -> object:
    if isinstance(value, list):
        return [short_text(item, 100) for item in value[:12]]
    return short_text(value, 260)


def short_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def final_revision_patch_schema() -> dict:
    string_array = {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 24}
    allowed_patch_fields = sorted({field for fields in FINAL_REVISION_COLLECTION_FIELDS.values() for field in fields})
    update_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "collection": {"type": "string", "enum": list(FINAL_REVISION_COLLECTION_FIELDS)},
            "id": {"type": "string", "maxLength": 80},
            "match_current_state": {"type": "string", "maxLength": 80},
            "match_event": {"type": "string", "maxLength": 80},
            "match_next_state": {"type": "string", "maxLength": 80},
            "field": {"type": "string", "enum": allowed_patch_fields},
            "value": {"type": "string", "maxLength": 900},
            "values": string_array,
            "reason": {"type": "string", "maxLength": 260},
        },
        "required": [
            "collection",
            "id",
            "match_current_state",
            "match_event",
            "match_next_state",
            "field",
            "value",
            "values",
            "reason",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "updates": {"type": "array", "items": update_schema, "maxItems": 18},
            "notes": {"type": "array", "items": {"type": "string", "maxLength": 240}, "maxItems": 12},
        },
        "required": ["updates", "notes"],
    }


def apply_final_revision_patch(spec: dict, payload: Mapping[str, object]) -> List[dict]:
    if not isinstance(payload, Mapping):
        return []
    updates = payload.get("updates", [])
    if not isinstance(updates, list):
        return []
    applied: List[dict] = []
    for update in updates:
        if not isinstance(update, Mapping):
            continue
        collection = str(update.get("collection", "") or "").strip()
        allowed_fields = FINAL_REVISION_COLLECTION_FIELDS.get(collection)
        if not allowed_fields:
            continue
        target = find_final_revision_target(spec, collection, update)
        if target is None:
            continue
        changed_fields: List[str] = []
        update_fields = final_revision_update_fields(update, allowed_fields)
        for field, value in update_fields:
            if field not in allowed_fields:
                continue
            normalized_value = normalize_final_revision_update_value(field, value)
            if normalized_value is None:
                continue
            if target.get(field) == normalized_value:
                continue
            target[field] = normalized_value
            changed_fields.append(field)
        if changed_fields:
            applied.append(
                {
                    "collection": collection,
                    "id": str(update.get("id", "") or revision_item_identity(target)).strip(),
                    "fields": changed_fields,
                    "reason": short_text(update.get("reason", ""), 160),
                }
            )
    return applied


def final_revision_update_fields(update: Mapping[str, object], allowed_fields: set[str]) -> List[Tuple[str, object]]:
    compact_field = str(update.get("field", "") or "").strip()
    if compact_field:
        value = update.get("values") if compact_field in FINAL_REVISION_LIST_FIELDS else update.get("value")
        return [(compact_field, value)]
    # Backward compatibility for older tests or cached structured outputs.
    return [(field, update.get(field)) for field in allowed_fields if field in update]


FINAL_REVISION_LIST_FIELDS = {"usecase_ids", "related_functions", "related_policies", "process_ids", "details", "items"}


def normalize_final_revision_update_value(field: str, value: object) -> object | None:
    if field in FINAL_REVISION_LIST_FIELDS:
        if not isinstance(value, list):
            return None
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or None
    if not isinstance(value, str):
        return None
    normalized_text = value.strip()
    if not normalized_text:
        return None
    if field == "process_target" and normalized_text not in {"Y", "N"}:
        return None
    return normalized_text


def find_final_revision_target(spec: Mapping[str, object], collection: str, update: Mapping[str, object]) -> Optional[dict]:
    rows = spec.get(collection)
    if not isinstance(rows, list):
        return None
    if collection == "state_transitions":
        return find_state_transition_for_revision(rows, update)
    target_id = str(update.get("id", "") or "").strip()
    if not target_id:
        return None
    id_field = "id"
    for row in rows:
        if isinstance(row, dict) and str(row.get(id_field, "")).strip() == target_id:
            return row
    return None


def find_state_transition_for_revision(rows: Sequence[object], update: Mapping[str, object]) -> Optional[dict]:
    current_state = str(update.get("match_current_state", "") or "").strip()
    event = str(update.get("match_event", "") or "").strip()
    next_state = str(update.get("match_next_state", "") or "").strip()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if current_state and str(row.get("current_state", "")).strip() != current_state:
            continue
        if event and str(row.get("event", "")).strip() != event:
            continue
        if next_state and str(row.get("next_state", "")).strip() != next_state:
            continue
        return row
    return None


def expand_final_remediation_dependencies(
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
    repair_attempt: int,
) -> Dict[str, List[Mapping[str, object]]]:
    """Add deterministic follow-up chapters when upstream content changed.

    Final-only mode can revise an upstream chapter after the first full-document
    inspection. If usecases or actors change, the usecase diagram must be
    regenerated even when the Inspector did not explicitly mention it; otherwise
    the deterministic Critical Gate can fail on stale diagram content.
    """
    expanded: Dict[str, List[Mapping[str, object]]] = {
        str(chapter): list(items or []) for chapter, items in feedback_by_chapter.items()
    }
    upstream_changed = any(expanded.get(chapter) for chapter in ("actors", "usecases"))
    if upstream_changed and not expanded.get("usecase_diagram"):
        expanded["usecase_diagram"] = [
            {
                "issue_id": f"FINAL-DEPENDENCY-USECASE-DIAGRAM-{repair_attempt}",
                "priority_tier": "P1",
                "batch_label": f"Final Inspector repair {repair_attempt} / dependency sync",
                "must_resolve": "Y",
                "repair_scope": "유즈케이스 다이어그램",
                "severity": "error",
                "category": "연결성",
                "title": "액터·유즈케이스 보완에 따른 다이어그램 동기화",
                "detail": "Final Inspector 보완으로 액터 또는 유즈케이스가 변경되었습니다. 다이어그램은 현재 액터-유즈케이스 목록 전체를 기준으로 다시 맞춰야 합니다.",
                "recommendation": "현재 actors와 usecases 전체를 기준으로 누락 없이 샘플 양식의 SVG 유즈케이스 다이어그램을 갱신하세요.",
                "target_path": "meta.usecase_diagram",
            }
        ]
    return expanded


def prioritize_final_remediation_feedback(
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
) -> Dict[str, List[Mapping[str, object]]]:
    """Keep one final repair pass focused on the earliest root-cause chapter.

    A final Inspector pass can report many downstream symptoms after an upstream
    contract issue. Repairing usecases and then immediately rewriting process,
    functions, and policies in the same pass is expensive and often stale because
    those downstream chapters should react to the repaired upstream contract.
    """
    grouped: Dict[str, List[Mapping[str, object]]] = {
        str(chapter): list(items or []) for chapter, items in feedback_by_chapter.items() if items
    }
    for root_chapter in ("actors", "usecases", "state"):
        root_items = grouped.get(root_chapter, [])
        if not any(str(item.get("priority_tier", "") or "").upper() == "P1" for item in root_items):
            continue
        return {root_chapter: root_items}
    return grouped


def build_final_remediation_runtime(
    ctx: PolicyContext,
    template_html: str,
    sample_htmls: Sequence[str],
    spec: Mapping[str, object],
) -> AgentRuntime:
    guideline = build_agent_guideline(template_html, sample_htmls)
    learning = {}
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    if isinstance(meta.get("topic_learning"), Mapping):
        learning = dict(meta.get("topic_learning") or {})
    evidence_store = build_evidence_store(ctx, guideline)
    authoring_blueprint = reusable_authoring_blueprint_from_spec(spec)
    if authoring_blueprint is None:
        authoring_blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=evidence_store,
            learning=learning,
            guideline=guideline,
        )
    return AgentRuntime(
        ctx=ctx,
        target_spec=build_policy_spec(ctx),
        learning=learning,
        guideline=guideline,
        evidence_store=evidence_store,
        authoring_blueprint=authoring_blueprint,
        llm_client=LLMClient.from_context(ctx),
    )


def reusable_authoring_blueprint_from_spec(spec: Mapping[str, object]) -> Optional[dict]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta, Mapping) else {}
    if not isinstance(blueprint, Mapping):
        return None
    chapter_blueprints = blueprint.get("chapter_blueprints", [])
    document_strategy = blueprint.get("document_strategy", {})
    if not isinstance(chapter_blueprints, list) or not chapter_blueprints:
        return None
    if not isinstance(document_strategy, Mapping) or not document_strategy:
        return None
    return copy.deepcopy(dict(blueprint))


def final_remediation_feedback_by_chapter(report, min_score: int, attempt: int) -> Dict[str, List[Dict[str, str]]]:
    grouped_findings: Dict[str, List[object]] = {}
    for finding in getattr(report, "findings", []) or []:
        chapter = final_finding_chapter(finding)
        grouped_findings.setdefault(chapter, []).append(finding)

    grouped_feedback: Dict[str, List[Dict[str, str]]] = {}
    for chapter, findings in grouped_findings.items():
        chapter_report = type(
            "FinalChapterReport",
            (),
            {
                "findings": findings,
                "score": getattr(report, "score", 0),
                "scope": chapter_to_scope(chapter),
            },
        )()
        feedback = inspection_feedback(chapter_report, min_score, attempt=attempt, chapter_key=chapter)
        if feedback:
            grouped_feedback[chapter] = feedback
    return grouped_feedback


def final_finding_chapter(finding) -> str:
    upstream = str(getattr(finding, "upstream_chapter", "") or "").strip()
    if upstream:
        return normalize_chapter_key(upstream)
    target_path = str(getattr(finding, "target_path", "") or "").strip()
    chapter_from_path = chapter_from_target_path(target_path)
    if chapter_from_path:
        return chapter_from_path
    text = " ".join(
        str(value or "")
        for value in (
            getattr(finding, "category", ""),
            getattr(finding, "title", ""),
            getattr(finding, "detail", ""),
            getattr(finding, "recommendation", ""),
        )
    )
    return chapter_from_text(text)


def chapter_from_target_path(target_path: str) -> str:
    path = target_path.replace("current_chapter.", "").replace("spec.", "")
    path = path.strip().casefold()
    mapping = (
        ("overview", "overview"),
        ("scope", "overview"),
        ("principles", "overview"),
        ("terms", "terms_refinement"),
        ("actors", "actors"),
        ("usecase_diagram", "usecase_diagram"),
        ("usecases", "usecases"),
        ("state_transitions", "state"),
        ("states", "state"),
        ("process_details", "process_detail"),
        ("processes", "process"),
        ("function_details", "function_detail"),
        ("functions", "functions"),
        ("policy_details", "policies"),
        ("policy_groups", "policies"),
        ("final_check", "final_check"),
    )
    for marker, chapter in mapping:
        if marker in path:
            return chapter
    return ""


def chapter_from_text(text: str) -> str:
    if any(keyword in text for keyword in ("최종 점검", "제출 전 점검")):
        return "final_check"
    if any(keyword in text for keyword in ("절차형 Y 유즈케이스", "절차형 유즈케이스", "process_target=Y 유즈케이스")):
        return "usecases"
    if any(keyword in text for keyword in ("정책", "PI", "PG", "개인정보", "로그", "이력", "보관", "파기", "고지", "허용", "제한 조건")):
        return "policies"
    if "기능 상세" in text:
        return "function_detail"
    if "프로세스 상세" in text:
        return "process_detail"
    if "기능" in text:
        return "functions"
    if "프로세스" in text:
        return "process"
    if "상태" in text or "전이" in text:
        return "state"
    if "유즈케이스 다이어그램" in text or "다이어그램" in text:
        return "usecase_diagram"
    if "유즈케이스" in text:
        return "usecases"
    if "액터" in text or "책임 주체" in text:
        return "actors"
    if "용어" in text:
        return "terms_refinement"
    if any(keyword in text for keyword in ("범위", "개요", "설계 원칙")):
        return "overview"
    if any(keyword in text for keyword in ("문체", "UI", "상세 설계", "버튼")):
        return "policies"
    return "final_check"


def normalize_chapter_key(value: str) -> str:
    key = value.strip().casefold().replace("-", "_")
    aliases = {
        "policy": "policies",
        "policies": "policies",
        "policy_groups": "policies",
        "policy_details": "policies",
        "state_transitions": "state",
        "states": "state",
        "term": "terms_refinement",
        "terms": "terms_refinement",
    }
    return aliases.get(key, key)


def record_final_remediation_run(
    spec: dict,
    report,
    feedback_by_chapter: Mapping[str, Sequence[Mapping[str, object]]],
    repair_attempt: int,
) -> None:
    spec.setdefault("meta", {}).setdefault("final_inspector_remediation_runs", []).append(
        {
            "attempt": repair_attempt,
            "score_before": getattr(report, "score", None),
            "status_before": getattr(report, "status", ""),
            "feedback_by_chapter": {
                chapter: len(items or [])
                for chapter, items in feedback_by_chapter.items()
            },
            "rule": "Final Inspector finding을 담당 chapter agent에 분배하고 patch 보완 후 Final Inspector가 재검수한다.",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )


def record_unresolved_final_inspector_issues(
    spec: dict,
    report,
    ctx: PolicyContext,
    repair_attempt: int,
) -> None:
    findings = list(getattr(report, "findings", []) or [])
    issue = {
        "chapter": "final",
        "stage": "finalize",
        "agent": "Final Inspector",
        "risk_flag": True,
        "risk_tier": "Final",
        "severity": "warn",
        "score": getattr(report, "score", None),
        "threshold": getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE),
        "attempt": repair_attempt,
        "max_loops": getattr(ctx, "inspector_max_loops", None),
        "summary": getattr(report, "summary", ""),
        "feedback": [
            {
                "severity": getattr(finding, "severity", ""),
                "tier": finding_tier(finding),
                "category": getattr(finding, "category", ""),
                "title": getattr(finding, "title", ""),
                "detail": getattr(finding, "detail", ""),
                "recommendation": getattr(finding, "recommendation", ""),
                "target_path": getattr(finding, "target_path", ""),
                "fix_owner": getattr(finding, "fix_owner", ""),
                "upstream_chapter": getattr(finding, "upstream_chapter", ""),
            }
            for finding in findings
        ],
        "handoff": "final_inspector_needs_review",
    }
    meta = spec.setdefault("meta", {})
    if isinstance(meta, dict):
        meta.setdefault("open_inspector_issues", []).append(issue)
        meta.setdefault("risk_flags", []).append(
            {
                "chapter": "final",
                "agent": "Final Inspector",
                "tier": "Final",
                "score": getattr(report, "score", None),
                "threshold": getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE),
                "reason": "최종 Inspector 보완 루프 이후에도 잔여 보완 항목이 남았습니다.",
            }
        )


def record_unresolved_final_critical_issues(
    spec: dict,
    errors: Sequence[str],
    ctx: PolicyContext,
    repair_attempt: int,
) -> None:
    meta = spec.setdefault("meta", {})
    if not isinstance(meta, dict):
        return
    issue = {
        "chapter": "final",
        "stage": "finalize",
        "agent": "Critical Gate",
        "risk_flag": True,
        "risk_tier": "Final",
        "severity": "error",
        "score": None,
        "threshold": getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE),
        "attempt": repair_attempt,
        "max_loops": getattr(ctx, "inspector_max_loops", None),
        "summary": "최종 Inspector 보완 후 결정적 구조 검증에 남은 항목이 있습니다.",
        "feedback": [
            {
                "severity": "error",
                "tier": "P1",
                "category": "Critical Gate",
                "title": "Critical Gate 잔여 이슈",
                "detail": str(error),
                "recommendation": "문서 작업실에서 해당 장을 이어서 보완하세요.",
                "target_path": "",
                "fix_owner": chapter_from_text(str(error)),
                "upstream_chapter": chapter_from_text(str(error)),
            }
            for error in errors
            if str(error).strip()
        ],
        "handoff": "final_critical_gate_needs_review",
    }
    meta.setdefault("open_inspector_issues", []).append(issue)
    meta.setdefault("risk_flags", []).append(
        {
            "chapter": "final",
            "agent": "Critical Gate",
            "tier": "Final",
            "score": None,
            "threshold": getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE),
            "reason": "최종 Critical Gate 보완 항목이 남았습니다.",
        }
    )


def load_resume_checkpoint(raw_path: str) -> dict | None:
    if not str(raw_path or "").strip():
        return None
    path = resolve_path(str(raw_path).strip())
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"체크포인트 파일을 찾을 수 없습니다: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"체크포인트 JSON 형식이 올바르지 않습니다: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("체크포인트는 JSON 객체여야 합니다.")
    spec = data.get("spec")
    if not isinstance(spec, dict):
        raise ValueError("체크포인트에 spec 객체가 없습니다.")
    data["path"] = str(path)
    return data


def checkpoint_version(checkpoint: Mapping[str, object] | None) -> str:
    if not isinstance(checkpoint, Mapping):
        return ""
    spec = checkpoint.get("spec", {})
    meta = spec.get("meta", {}) if isinstance(spec, Mapping) and isinstance(spec.get("meta"), Mapping) else {}
    version = str(meta.get("version", "")).strip()
    return version if re.fullmatch(r"v\d+\.\d+", version) else ""


def save_generation_checkpoint(
    spec: dict,
    ctx: PolicyContext,
    stage,
    attempt: int,
    passed: bool,
    summary: str,
) -> Path:
    checkpoints_dir = ctx.output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    ensure_policy_spec_base_keys(spec)
    checkpoint = {
        "checkpoint": {
            "topic": ctx.topic,
            "topic_slug": ctx.topic_slug,
            "template_type": ctx.template_type,
            "version": ctx.version,
            "inspection_mode": ctx.inspection_mode,
            "writer_mode": ctx.writer_mode,
            "stage_key": stage.key,
            "stage_name": stage.name,
            "stage_label": stage.agent.display_name,
            "attempt": attempt,
            "passed": passed,
            "summary": summary,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "next_action": "resume_from_next_stage" if passed else "revise_current_stage",
        },
        "spec": spec,
    }
    path = checkpoints_dir / (
        f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_"
        f"{stage.key}_{stage.name}_checkpoint.json"
    )
    path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = checkpoints_dir / (
        f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_latest_checkpoint.json"
    )
    latest_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_failed_attempt_diagnostic(
    spec: dict,
    ctx: PolicyContext,
    stage,
    attempt: int,
    report,
    threshold: int,
    gate_decision: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> Path:
    checkpoints_dir = ctx.output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "diagnostic": {
            "topic": ctx.topic,
            "topic_slug": ctx.topic_slug,
            "template_type": ctx.template_type,
            "version": ctx.version,
            "inspection_mode": ctx.inspection_mode,
            "writer_mode": ctx.writer_mode,
            "stage_key": stage.key,
            "stage_name": stage.name,
            "stage_label": stage.agent.display_name,
            "attempt": attempt,
            "passed": False,
            "score": getattr(report, "score", None),
            "threshold": threshold,
            "gate_decision": dict(gate_decision or {}),
            "summary": getattr(report, "summary", ""),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "next_action": "revise_current_stage",
        },
        "counts": quality_counts(spec),
        "stage_payload": stage.agent.extract_payload(spec),
        "findings": [
            {
                "severity": getattr(finding, "severity", ""),
                "tier": getattr(finding, "tier", ""),
                "category": getattr(finding, "category", ""),
                "title": getattr(finding, "title", ""),
                "detail": getattr(finding, "detail", ""),
                "recommendation": getattr(finding, "recommendation", ""),
                "target_path": getattr(finding, "target_path", ""),
                "fix_owner": getattr(finding, "fix_owner", ""),
                "upstream_chapter": getattr(finding, "upstream_chapter", ""),
                "root_cause": getattr(finding, "root_cause", ""),
                "required_change": getattr(finding, "required_change", ""),
                "patch_hint": getattr(finding, "patch_hint", ""),
                "acceptance_check": getattr(finding, "acceptance_check", ""),
                "keep_constraints": getattr(finding, "keep_constraints", ""),
                "do_not_change": getattr(finding, "do_not_change", ""),
            }
            for finding in getattr(report, "findings", []) or []
        ],
        "local_precheck": (getattr(report, "metrics", {}) or {}).get("local_precheck", {}),
        "feedback": [dict(item) for item in feedback if isinstance(item, Mapping)],
    }
    path = checkpoints_dir / (
        f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_"
        f"{stage.key}_{stage.name}_attempt{attempt}_failed_diagnostic.json"
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def checkpoint_artifact_payload(path: Path, ctx: PolicyContext) -> dict:
    relative = path.relative_to(ctx.output_dir)
    return {
        "name": path.name,
        "path": str(relative),
        "url": f"/output/{quote(str(relative), safe='/')}",
    }


def build_quality_report(
    ctx: PolicyContext,
    spec: dict,
    validation,
    critical_validation,
    final_report,
    status: str,
    artifact_drift: Optional[Mapping[str, object]] = None,
) -> dict:
    requirement_summary = requirement_trace_summary(spec)
    inspector_summary = None
    if final_report is not None:
        inspector_summary = {
            "status": final_report.status,
            "score": final_report.score,
            "summary": final_report.summary,
            "findings": [
                {
                    "severity": finding.severity,
                    "category": finding.category,
                    "title": finding.title,
                    "detail": finding.detail,
                    "recommendation": finding.recommendation,
                }
                for finding in final_report.findings
            ],
            "metrics": final_report.metrics,
        }
    report = {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target": {
            "topic": ctx.topic,
            "template_type": ctx.template_type,
            "version": ctx.version,
            "html": make_output_filename(ctx),
            "spec": make_spec_filename(ctx),
        },
        "gates": {
            "json_schema": {
                "ok": bool(getattr(validation, "ok", False)),
                "errors": list(getattr(validation, "errors", []) or []),
            },
            "critical": {
                "ok": bool(getattr(critical_validation, "ok", False)) if critical_validation is not None else None,
                "errors": list(getattr(critical_validation, "errors", []) or []) if critical_validation is not None else [],
            },
            "inspector": inspector_summary,
            "artifact_drift": dict(artifact_drift) if isinstance(artifact_drift, Mapping) else None,
        },
        "counts": quality_counts(spec),
        "requirement_trace": requirement_summary,
        "open_inspector_issues": spec.get("meta", {}).get("open_inspector_issues", [])
        if isinstance(spec.get("meta"), dict)
        else [],
        "evidence_gaps": spec.get("evidence_gaps", []) if isinstance(spec.get("evidence_gaps"), list) else [],
        "recommendations": quality_recommendations(spec, final_report, requirement_summary),
    }
    return report


def save_quality_report(report: Mapping[str, object], ctx: PolicyContext) -> Path:
    quality_dir = ctx.output_dir / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    path = quality_dir / f"{Path(make_output_filename(ctx)).stem}_quality_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def quality_report_artifact_payload(path: Path, ctx: PolicyContext) -> dict:
    return checkpoint_artifact_payload(path, ctx)


def quality_preview_items(report: Mapping[str, object]) -> List[str]:
    gates = report.get("gates", {}) if isinstance(report.get("gates"), Mapping) else {}
    inspector = gates.get("inspector", {}) if isinstance(gates.get("inspector"), Mapping) else {}
    requirement_trace = report.get("requirement_trace", {}) if isinstance(report.get("requirement_trace"), Mapping) else {}
    items = [
        f"JSON Schema Gate: {'통과' if gates.get('json_schema', {}).get('ok') else '실패'}",
        f"Critical Gate: {'통과' if gates.get('critical', {}).get('ok') else '실패'}",
    ]
    if inspector:
        items.append(f"Inspector: {inspector.get('score', '-')}점 / {inspector.get('status', '-')}")
    if requirement_trace:
        items.append(
            f"요구사항 근거 연결: {requirement_trace.get('covered', 0)} / {requirement_trace.get('total', 0)}건"
        )
    recommendations = report.get("recommendations", []) if isinstance(report.get("recommendations"), list) else []
    items.extend(str(item) for item in recommendations[:4])
    return items


def quality_counts(spec: Mapping[str, object]) -> dict:
    return {
        key: len(spec.get(key, [])) if isinstance(spec.get(key), list) else 0
        for key in (
            "terms",
            "actors",
            "usecases",
            "states",
            "state_transitions",
            "processes",
            "functions",
            "policy_groups",
            "policy_details",
            "final_check",
            "trace_matrix",
            "evidence_gaps",
        )
    }


def requirement_trace_summary(spec: dict) -> dict:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), dict) else {}
    coverage_matrix = blueprint.get("coverage_matrix", [])
    if not isinstance(coverage_matrix, list):
        coverage_matrix = []
    evidence_ids = blueprint_referenced_evidence_ids(spec)
    missing = uncovered_requirement_ids(coverage_matrix, evidence_ids)
    total = len(
        [
            row
            for row in coverage_matrix
            if isinstance(row, dict) and str(row.get("requirement_id", "") or row.get("id", "")).strip()
        ]
    )
    return {
        "total": total,
        "covered": max(0, total - len(missing)),
        "missing": missing,
        "evidence_id_count": len([evidence_id for evidence_id in evidence_ids if evidence_id.startswith("REQ-")]),
    }


def quality_recommendations(spec: dict, final_report, requirement_summary: Mapping[str, object]) -> List[str]:
    recommendations: List[str] = []
    missing = requirement_summary.get("missing", []) if isinstance(requirement_summary, Mapping) else []
    if missing:
        recommendations.append("요구사항 근거가 연결되지 않은 항목을 다음 재개 생성에서 우선 Context Pack에 포함하세요.")
    if final_report is not None:
        metrics = getattr(final_report, "metrics", {}) or {}
        table_count = int(metrics.get("table_count", 0) or 0)
        sample_max = int(metrics.get("sample_max_table_count", 0) or 0)
        if sample_max and table_count > sample_max:
            recommendations.append("샘플 대비 표가 많으므로 프로세스/기능 표는 업무 단위로 묶고 정책 상세 중심으로 밀도를 조정하세요.")
        for finding in getattr(final_report, "findings", []):
            recommendations.append(f"{finding.category}: {finding.recommendation}")
    if spec.get("meta", {}).get("open_inspector_issues") if isinstance(spec.get("meta"), dict) else False:
        recommendations.append("최대 보완 후 인계된 Inspector 이슈가 남아 있어 최종 제출 전 사람이 확인해야 합니다.")
    return recommendations


def inspection_gate_passed(report, min_score: int, chapter_key: str = "") -> bool:
    return bool(inspect_gate_decision(report, chapter_key, min_score).get("passed", False))


def final_inspection_gate_passed(report, ctx: PolicyContext) -> bool:
    mode = str(getattr(ctx, "inspection_mode", "chapter-final") or "chapter-final").strip()
    min_score = int(getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE) or DEFAULT_INSPECTOR_MIN_SCORE)
    if mode == "final-only":
        findings = list(getattr(report, "findings", []) or [])
        error_count = sum(1 for finding in findings if getattr(finding, "severity", "") == "error")
        metrics = getattr(report, "metrics", {}) or {}
        score_breakdown = metrics.get("score_breakdown", {}) if isinstance(metrics, Mapping) else {}
        gate_blocker_count = int(score_breakdown.get("gate_blocker_count", 0) or 0)
        score = int(getattr(report, "score", 0) or 0)
        return score >= min_score and error_count == 0 and gate_blocker_count == 0
    return inspection_gate_passed(report, min_score)


def inspection_feedback(report, min_score: int, *, attempt: int = 1, chapter_key: str = "") -> List[Dict[str, str]]:
    feedback: List[Dict[str, str]] = []
    repair_scope = feedback_repair_scope(getattr(report, "scope", ""))
    selected_findings = feedback_batch_for_attempt(report.findings, attempt)
    remediation_mode = remediation_mode_for_report(
        getattr(report, "score", 0),
        min_score,
        selected_findings,
        chapter_key,
    )
    batch_tiers = sorted({finding_tier(finding) for finding in selected_findings})
    batch_label = f"Round {attempt} / {'+'.join(batch_tiers) if batch_tiers else 'score'} batch / {len(selected_findings)} items"
    for index, finding in enumerate(report.findings, start=1):
        if finding not in selected_findings:
            continue
        priority_tier = finding_tier(finding)
        fix_owner = getattr(finding, "fix_owner", "current_chapter") or "current_chapter"
        upstream_chapter = getattr(finding, "upstream_chapter", "") or ""
        required_change = getattr(finding, "required_change", "") or ""
        patch_hint = getattr(finding, "patch_hint", "") or ""
        keep_constraints = getattr(finding, "keep_constraints", "") or ""
        do_not_change = getattr(finding, "do_not_change", "") or ""
        actionability_issues = finding_actionability_issues(finding)
        recommendation = (
            upstream_feedback_recommendation(finding, upstream_chapter)
            if fix_owner in {"upstream_chapter", "cross_chapter"}
            else scoped_feedback_recommendation(
                detailed_patch_recommendation(
                    finding.recommendation,
                    required_change=required_change,
                    patch_hint=patch_hint,
                    keep_constraints=keep_constraints,
                    do_not_change=do_not_change,
                ),
                repair_scope,
            )
        )
        if actionability_issues:
            issue_text = ", ".join(actionability_issues)
            scope_guard = (
                "target_path 또는 명시된 수정 필드만 좁게 보완하고 전체 장 재작성으로 확대하지 마세요."
                if remediation_mode == "patch"
                else "지정된 보완 모드의 범위 안에서만 재구성하고 근거 없는 새 범위로 확장하지 마세요."
            )
            recommendation = (
                f"{recommendation} / 피드백명확화: Inspector 피드백에 {issue_text} 항목이 있으므로 "
                f"{scope_guard}"
            )
        feedback.append(
            {
                "issue_id": getattr(finding, "finding_id", "") or f"INS-{index:02d}",
                "priority_tier": priority_tier,
                "batch_label": batch_label,
                "must_resolve": "Y",
                "repair_scope": repair_scope,
                "fix_owner": fix_owner,
                "upstream_chapter": upstream_chapter,
                "inspector_score": report.score,
                "inspector_threshold": min_score,
                "remediation_mode": remediation_mode,
                "revision_policy": remediation_revision_policy(remediation_mode),
                "failure_type": classify_feedback_failure(finding),
                "severity": finding.severity,
                "category": finding.category,
                "is_quality_gate": "Y" if is_quality_gate_finding(finding) else "N",
                "feedback_quality": "needs_clarification" if actionability_issues else "actionable",
                "actionability_issues": ", ".join(actionability_issues),
                "target_path": getattr(finding, "target_path", ""),
                "title": finding.title,
                "detail": finding.detail,
                "root_cause": getattr(finding, "root_cause", ""),
                "required_change": required_change,
                "patch_hint": patch_hint,
                "keep_constraints": keep_constraints,
                "do_not_change": do_not_change,
                "recommendation": recommendation,
                "acceptance_check": feedback_acceptance_check(finding),
            }
        )
    if not feedback and report.score < min_score and gate_tier(chapter_key) != "log-only":
        feedback.append(
            {
                "issue_id": "INS-SCORE",
                "priority_tier": "P1" if gate_tier(chapter_key) == "hard" else "P2",
                "batch_label": f"Round {attempt} / score batch / 1 items",
                "must_resolve": "Y",
                "repair_scope": repair_scope,
                "inspector_score": report.score,
                "inspector_threshold": min_score,
                "remediation_mode": remediation_mode,
                "revision_policy": remediation_revision_policy(remediation_mode),
                "failure_type": "score_below_threshold",
                "feedback_quality": "score_only",
                "actionability_issues": "구체 finding 없음",
                "severity": "warning",
                "category": "점수",
                "title": "Inspector 점수 미달",
                "detail": f"Inspector 점수 {report.score}점이 기준 {min_score}점보다 낮습니다.",
                "recommendation": "현재 챕터는 간결하게 유지하되 누락된 판단축만 보완하고, 세부 조건·예외·이력 기준은 후속 프로세스·기능·정책 장에서 구체화하세요.",
                "acceptance_check": "다음 Inspector 검수에서 동일 챕터의 점수가 기준점 이상이거나 동일 원인의 finding이 재발하지 않아야 합니다.",
            }
        )
    return feedback


def detailed_patch_recommendation(
    recommendation: str,
    *,
    required_change: str = "",
    patch_hint: str = "",
    keep_constraints: str = "",
    do_not_change: str = "",
) -> str:
    parts = [str(recommendation or "").strip()]
    if required_change:
        parts.append(f"필수수정: {required_change}")
    if patch_hint:
        parts.append(f"패치힌트: {patch_hint}")
    if keep_constraints:
        parts.append(f"유지조건: {keep_constraints}")
    if do_not_change:
        parts.append(f"수정금지: {do_not_change}")
    return " / ".join(part for part in parts if part)


def remediation_mode_for_report(
    score: int,
    min_score: int,
    findings: Sequence[object],
    chapter_key: str = "",
) -> str:
    """Route failed inspections to the smallest useful repair strategy."""

    try:
        score_value = int(score or 0)
    except (TypeError, ValueError):
        score_value = 0
    threshold = int(min_score or DEFAULT_INSPECTOR_MIN_SCORE)
    text = " ".join(
        str(value or "")
        for finding in findings or []
        for value in (
            getattr(finding, "category", ""),
            getattr(finding, "title", ""),
            getattr(finding, "detail", ""),
            getattr(finding, "recommendation", ""),
            getattr(finding, "target_path", ""),
        )
    ).casefold()
    has_structure_signal = any(
        marker in text
        for marker in (
            "structure",
            "구조",
            "계층",
            "입자도",
            "전반",
            "전체",
            "1:1",
            "샘플 수준",
        )
    )
    has_many_findings = len(findings or []) > 8
    if chapter_key in {"process", "functions"} and has_targeted_current_chapter_findings(findings):
        return "patch"
    if score_value >= threshold:
        return "scoped_section_revision" if has_structure_signal or has_many_findings else "patch"
    if score_value >= max(0, threshold - 5) and not has_structure_signal and not has_many_findings:
        return "patch"
    if score_value >= 72:
        return "scoped_section_revision"
    if score_value >= 60:
        return "scoped_full_revision"
    return "blueprint_realign_revision"


def has_targeted_current_chapter_findings(findings: Sequence[object]) -> bool:
    """Prefer delta repair when Stage Inspector points at concrete rows.

    Process/functions chapters can be large and chunked. If the Inspector has
    already supplied target_path values for current_chapter rows, a full chunk
    rewrite wastes tokens and may disturb unaffected rows.
    """
    for finding in findings or []:
        path = str(getattr(finding, "target_path", "") or "").strip()
        if re.search(r"(?:current_chapter\.)?(?:processes|functions)\[\d+\]", path):
            return True
    return False


def remediation_revision_policy(mode: str) -> str:
    policies = {
        "patch": "보완 방식은 patch-only입니다. Inspector target_path와 직접 관련된 항목만 최소 수정합니다.",
        "scoped_section_revision": "보완 방식은 scoped section revision입니다. 문제 섹션과 같은 원인의 인접 항목은 재구성하되, 담당 장 밖으로 확대하지 않습니다.",
        "scoped_full_revision": "보완 방식은 scoped full revision입니다. 담당 장 전체를 승인된 Blueprint와 이전 장 기준에 맞춰 다시 정렬할 수 있습니다.",
        "blueprint_realign_revision": "보완 방식은 Blueprint realign revision입니다. Blueprint/이전 장 계층 기준을 먼저 재확인한 뒤 담당 장을 재작성합니다.",
    }
    return policies.get(mode, policies["patch"])


def upstream_feedback_recommendation(finding, upstream_chapter: str) -> str:
    upstream_label = feedback_repair_scope(chapter_to_scope(upstream_chapter))
    text = str(getattr(finding, "recommendation", "") or "").strip()
    required_change = str(getattr(finding, "required_change", "") or "").strip()
    patch_hint = str(getattr(finding, "patch_hint", "") or "").strip()
    prefix = f"수정 소유자는 {upstream_label}입니다. 이전 장 Agent가 최소 범위로 보완한 뒤 현재 장은 갱신된 기준에 맞춥니다."
    detail = detailed_patch_recommendation(text, required_change=required_change, patch_hint=patch_hint)
    return f"{prefix} {detail}".strip() if detail else prefix


def chapter_to_scope(chapter: str) -> str:
    return {
        "overview": "01_overview",
        "terms": "02_terms",
        "actors": "03_actors",
        "usecases": "04_usecases",
        "usecase_diagram": "05_usecase_diagram",
        "state": "06_state",
        "process": "07_process",
        "functions": "08_functions",
        "policies": "09_policies",
        "final_check": "10_final_check",
    }.get(str(chapter or "").strip(), "")


def feedback_batch_for_attempt(findings: Sequence[object], attempt: int) -> List[object]:
    deduped = dedupe_findings_by_target_and_category(findings)
    if attempt <= 1:
        selected = [finding for finding in deduped if finding_tier(finding) == "P1"]
        return selected or [finding for finding in deduped if finding_tier(finding) == "P2"] or deduped
    if attempt == 2:
        selected = [finding for finding in deduped if finding_tier(finding) in {"P1", "P2"}]
        return selected or deduped
    return deduped


def dedupe_findings_by_target_and_category(findings: Sequence[object]) -> List[object]:
    result: List[object] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        target = str(getattr(finding, "target_path", "") or getattr(finding, "title", "")).strip()
        category = str(getattr(finding, "category", "")).strip()
        key = (target, category)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result


def feedback_repair_scope(scope: str) -> str:
    labels = {
        "01_overview": "이번 장: 개요",
        "02_terms": "이번 장: 주요 용어",
        "03_actors": "이번 장: 액터",
        "04_usecases": "이번 장: 유즈케이스",
        "05_usecase_diagram": "이번 장: 유즈케이스 다이어그램",
        "06_state": "이번 장: 상태 코드·상태 전이",
        "07_process": "이번 장: 프로세스 목록·BPMN 업무 흐름도",
        "08_functions": "이번 장: 기능 목록",
        "09_policies": "이번 장: 정책 목록·정책 상세",
        "10_final_check": "이번 장: 최종 점검 기준",
    }
    return labels.get(str(scope or ""), "이번 장")


def scoped_feedback_recommendation(recommendation: str, repair_scope: str) -> str:
    text = str(recommendation or "").strip()
    prefix = f"수정 범위는 {repair_scope}으로 한정합니다. 이전 장은 기준선으로 유지하고 이번 장을 맞추세요."
    return f"{prefix} {text}".strip() if text else prefix


def classify_feedback_failure(finding) -> str:
    text = " ".join(
        str(getattr(finding, key, "") or "")
        for key in ("category", "title", "detail", "recommendation")
    )
    if any(keyword in text for keyword in ("참조", "불일치", "연결", "누락", "process_id", "policy_id", "actor", "usecase_id")):
        return "connection_integrity"
    if any(keyword in text for keyword in ("정책", "판단", "기준값", "허용", "제한", "예외", "고지", "이력")):
        return "policy_specificity"
    if any(keyword in text for keyword in ("상태", "전이", "완료", "보류", "실패", "취소", "만료")):
        return "state_consistency"
    if any(keyword in text for keyword in ("샘플", "장황", "문체", "일반론", "분량", "간결")):
        return "sample_concision"
    if any(keyword in text for keyword in ("HTML", "템플릿", "표", "줄바꿈", "CSS", "양식")):
        return "format_structure"
    return "content_quality"


def feedback_acceptance_check(finding) -> str:
    explicit = str(getattr(finding, "acceptance_check", "") or "").strip()
    if explicit:
        return explicit
    category = str(getattr(finding, "category", "") or "")
    title = str(getattr(finding, "title", "") or "")
    recommendation = str(getattr(finding, "recommendation", "") or "")
    combined = f"{category} {title} {recommendation}"
    if "액터" in combined or "actor" in combined.lower():
        return "액터명, 책임 설명, 유즈케이스 actor 값이 서로 같은 책임 경계를 유지해야 합니다."
    if "유즈케이스" in combined or "usecase" in combined.lower():
        return "유즈케이스의 actor, process_target, 설명의 완료 상태가 AGENTS.md 기준과 충돌하지 않아야 합니다."
    if "상태" in combined or "전이" in combined:
        return "상태명은 상태 목록과 전이표에서 동일하게 쓰이고, 각 결과 상태의 원인은 inbound 전이 criteria로 도달 가능해야 하며, 다시 조회는 판정 허브로 돌아가 재판정되어야 합니다."
    if "프로세스" in combined or "process" in combined.lower():
        return "process_target=Y 유즈케이스는 프로세스에 연결되고, 시작·판단·예외·완료 흐름이 한 문장 설명 안에 드러나야 합니다."
    if "기능" in combined or "function" in combined.lower():
        return "기능은 담당 process_id를 유지하고 프로세스 수행에 필요한 처리 역량을 중복 없이 설명해야 합니다."
    if "정책" in combined or "policy" in combined.lower():
        return "정책은 기능 설명이 아니라 판단값, 허용 조건, 제한 조건, 예외, 고지, 이력 기준 중 하나 이상을 포함해야 합니다."
    return "동일 finding 제목 또는 같은 원인의 지적이 다음 Inspector 결과에 반복되지 않아야 합니다."


def chunk_fallback_feedback(stage_spec: dict, stage, attempt: int) -> List[Dict[str, str]]:
    runs = stage_spec.get("meta", {}).get("llm_chunking_runs", [])
    if not isinstance(runs, list):
        return []
    relevant = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("chapter") == stage.agent.chapter_key
        and int(run.get("attempt", 0) or 0) == attempt
        and run.get("fallback_chunks")
    ]
    if not relevant:
        return []
    fallback_count = sum(len(run.get("fallback_chunks", []) or []) for run in relevant)
    return [
        {
            "severity": "error",
            "failure_type": "chunk_fallback",
            "category": "LLM 분할 작성",
            "title": "분할 작성 fallback 보완 필요",
            "detail": f"{stage.agent.display_name}의 분할 작성 중 {fallback_count}개 구간이 LLM 결과 대신 로컬 초안으로 대체되었습니다.",
            "recommendation": "같은 장을 다시 작성하되 fallback 구간의 기존 ID를 유지하고, 정책서 근거 기반 판단 조건과 연결성을 우선 보완하세요.",
        }
    ]


def critical_validation_feedback(errors: Iterable[str], category: str) -> List[Dict[str, str]]:
    feedback: List[Dict[str, str]] = []
    for error in list(errors):
        feedback.append(
            {
                "severity": "error",
                "priority_tier": "P1",
                "batch_label": "JSON Critical Gate / P1 batch",
                "failure_type": classify_failure_text(error),
                "category": category,
                "title": "구조 정합성 보완 필요",
                "detail": error,
                "recommendation": critical_recommendation(error),
            }
        )
    return feedback


def critical_recommendation(error: str) -> str:
    if "액터" in error and "유즈케이스" in error:
        return "액터 목록의 모든 액터가 유즈케이스에서 최소 1회 이상 정확한 액터명으로 사용되도록 보완하세요."
    if "process_target=Y" in error or "연결된 프로세스" in error:
        return "사람 액터가 수행하는 유즈케이스는 process_target=Y로 두고, 해당 유즈케이스를 4장 프로세스에 연결하세요."
    if "process_target=N" in error:
        return "시스템 보조 유즈케이스는 독립 프로세스로 만들지 말고 관련 고객/운영자 프로세스의 기능 또는 정책으로 흡수하세요."
    if "관련 기능명" in error:
        return "기능의 process_id를 기준으로 프로세스 related_functions가 실제 기능명과 정확히 일치하도록 보완하세요."
    if "관련 정책" in error:
        return "정책 목록의 정책 ID와 정책명을 기준으로 프로세스 related_policies가 정확히 연결되도록 보완하세요."
    if "상태" in error:
        return "상태 전이표의 현재 상태와 다음 상태는 상태 코드 목록의 상태명을 그대로 사용하세요."
    if "정책 상세" in error:
        return "모든 정책 그룹에 하나 이상의 정책 상세 항목을 연결하고, 금지 표현 대신 인증 수단, 가능 횟수, 유효시간, 제한 기간, 채널, 저장 항목 같은 실제 기능 동작값을 작성하세요."
    return "현재 챕터를 다시 작성할 때 기존 ID와 명칭을 유지하면서 누락된 연결성을 먼저 보완하세요."


def classify_failure_text(text: str) -> str:
    if any(keyword in text for keyword in ("액터", "유즈케이스", "프로세스", "기능", "정책", "참조", "연결")):
        return "connection_integrity"
    if any(keyword in text for keyword in ("상태", "전이")):
        return "state_consistency"
    if any(keyword in text for keyword in ("정책 상세", "기준", "예외", "허용", "제한")):
        return "policy_specificity"
    return "json_schema"


def json_critical_gate_result(stage_spec: dict, stage, ctx: PolicyContext, feedback: List[Dict[str, str]], message: str) -> Dict[str, object]:
    preview = build_stage_activity_preview(stage_spec, stage)
    preview["title"] = f"{stage.agent.display_name} JSON Critical Gate 미통과"
    preview.setdefault("items", [])
    preview["items"] = [
        "HTML/LLM inspector 호출 전에 JSON 연결성 오류를 먼저 감지했습니다.",
        "토큰을 쓰는 LLM 검수로 보내지 않고 같은 Agent에게 즉시 보완 요청합니다.",
    ] + [item["detail"] for item in feedback[:5]]
    return {
        "passed": False,
        "score": 0,
        "threshold": gate_required_score(stage.agent.chapter_key, ctx.inspector_min_score),
        "feedback": feedback,
        "artifact": None,
        "preview": preview,
        "gate": "json_critical",
        "message": message,
    }


def record_json_critical_gate_run(stage_spec: dict, stage, attempt: int, errors: Iterable[str], passed: bool) -> None:
    stage_spec.setdefault("meta", {}).setdefault("json_critical_gate_runs", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "attempt": attempt,
            "scope": stage.scope,
            "passed": passed,
            "errors": list(errors),
        }
    )


def record_inspector_gate_run(stage_spec: dict, stage, attempt: int, report, passed: bool, min_score: int, gate_decision: Mapping[str, object] | None = None) -> None:
    decision = dict(gate_decision or {})
    stage_spec.setdefault("meta", {}).setdefault("inspector_gate_runs", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "attempt": attempt,
            "scope": stage.scope,
            "gate_tier": decision.get("tier", gate_tier(stage.agent.chapter_key)),
            "score": report.score,
            "threshold": min_score,
            "gate_blocker_count": decision.get("gate_blocker_count", report.metrics.get("score_breakdown", {}).get("gate_blocker_count", 0) if isinstance(getattr(report, "metrics", {}), dict) else 0),
            "error_count": decision.get("error_count", sum(1 for finding in report.findings if finding.severity == "error")),
            "passed": passed,
            "status": report.status,
            "summary": report.summary,
            "findings": [
                {
                    "severity": finding.severity,
                    "tier": finding_tier(finding),
                    "category": finding.category,
                    "is_quality_gate": bool(is_quality_gate_finding(finding)),
                    "target_path": getattr(finding, "target_path", ""),
                    "title": finding.title,
                    "detail": finding.detail,
                    "recommendation": finding.recommendation,
                }
                for finding in report.findings
            ],
        }
    )


def record_log_only_open_issues(stage_spec: dict, stage, attempt: int, report, threshold: int) -> None:
    stage_spec.setdefault("meta", {}).setdefault("open_inspector_issues", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "attempt": attempt,
            "score": report.score,
            "threshold": threshold,
            "risk_flag": False,
            "risk_tier": "log-only",
            "feedback": inspection_feedback(report, threshold, attempt=3, chapter_key=stage.agent.chapter_key),
            "handoff": "log_only_recorded_continue_next_agent",
        }
    )


def inspect_policy_file(args: argparse.Namespace):
    target = resolve_path(args.file)
    if not target.exists():
        raise FileNotFoundError(f"검수할 파일을 찾을 수 없습니다: {target}")
    args.disable_mock_env = str(getattr(args, "writer_mode", "mock") or "mock").strip().casefold() == "llm"
    template_type = args.template_type or infer_template_type(target) or "simple"
    template_selection = resolve_template_path(args.template, template_type, args.topic or None)
    document = target.read_text(encoding="utf-8")
    template_html = template_selection.path.read_text(encoding="utf-8")
    topic = args.topic or infer_topic_from_policy_filename(target.name)
    report = inspect_policy_document(
        document,
        template_html=template_html,
        sample_htmls=load_sample_htmls(template_type),
        template_type=template_type,
        scope=args.scope,
        topic=topic,
        llm_client=client_for_stage_inspector(LLMClient.from_context(args), final=args.scope in {"full", "final"}),
        llm_required=True,
    )
    save_inspection_report(report, target.name, args.scope)
    return report


def load_policy_requirements(topic: str, args: argparse.Namespace) -> List[RequirementItem]:
    if getattr(args, "no_requirements", False):
        return []
    requirements_dir = resolve_path(getattr(args, "requirements_dir", "input/requirements"))
    return load_scoped_requirements_for_topic(topic, requirements_dir)


def load_policy_references(topic: str, args: argparse.Namespace) -> List[ReferenceInsight]:
    if getattr(args, "no_references", False):
        return []
    references_dir = resolve_path(getattr(args, "references_dir", "input/references"))
    return load_reference_insights_for_topic(topic, references_dir)


def print_inspection_report(report) -> None:
    print(report.summary)
    print(f"scope: {report.scope}")
    print(f"status: {report.status}")
    print(f"score: {report.score}")
    if not report.findings:
        print("findings: 없음")
        return
    print("findings:")
    for finding in report.findings:
        print(f"- [{finding.severity}] {finding.category} / {finding.title}: {finding.detail}")
        print(f"  recommendation: {finding.recommendation}")


def infer_topic_from_policy_filename(name: str) -> str:
    stem = name.removesuffix(".html")
    if not stem.startswith("NC_") or "_정책서_" not in stem:
        return ""
    return stem.removeprefix("NC_").split("_정책서_", 1)[0]


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return PROJECT_ROOT / path


def resolve_template_path(
    raw_path: str,
    template_type: Optional[str] = None,
    topic: Optional[str] = None,
) -> TemplateSelection:
    requested = resolve_path(raw_path)
    if requested.exists():
        if requested.is_dir():
            selected_type = template_type or ask_template_type(topic)
            return TemplateSelection(choose_template(requested, selected_type), selected_type)
        inferred_type = infer_template_type(requested)
        selected_type = template_type or inferred_type or ask_template_type(topic)
        return TemplateSelection(requested, selected_type)

    templates_dir = PROJECT_ROOT / "input" / "templates"
    alias = normalize_korean(raw_path).casefold()
    if alias in {"simple", "simplified", "간소화"}:
        return TemplateSelection(choose_template(templates_dir, "simple"), "simple")
    if alias in {"full", "전체"}:
        return TemplateSelection(choose_template(templates_dir, "full"), "full")

    if requested.name == "template.html":
        selected_type = template_type or ask_template_type(topic)
        return TemplateSelection(choose_template(templates_dir, selected_type), selected_type)

    raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {requested}")


def ask_template_type(topic: Optional[str] = None) -> str:
    if not sys.stdin.isatty():
        raise ValueError(
            "템플릿 버전을 선택해야 합니다. --template-type full 또는 --template-type simple을 지정하세요."
        )

    topic_text = f'"{topic}" 정책서' if topic else "정책서"
    print(f"{topic_text}를 어떤 버전으로 작성할까요?")
    print("1. Full 버전")
    print("2. 간소화 버전")

    while True:
        choice = input("선택 [1/2]: ").strip().casefold()
        if choice in {"1", "full", "f", "full 버전"}:
            return "full"
        if choice in {"2", "simple", "s", "간소화", "간소화 버전"}:
            return "simple"
        print("1 또는 2를 입력해 주세요.")


def choose_template(templates_dir: Path, template_type: str) -> Path:
    all_templates = sorted(templates_dir.glob("*.html"))
    if not all_templates:
        raise FileNotFoundError(f"템플릿 폴더에 HTML 파일이 없습니다: {templates_dir}")

    normalized_names = [(path, normalize_korean(path.name)) for path in all_templates]
    if template_type == "full":
        matches = [
            path
            for path, name in normalized_names
            if "full" in name.casefold() and "템플릿" in name
        ]
    else:
        matches = [
            path
            for path, name in normalized_names
            if "간소화" in name and "템플릿" in name
        ]

    if matches:
        return matches[0]

    available = ", ".join(path.name for path in all_templates)
    raise FileNotFoundError(
        f"{template_type} 템플릿을 찾을 수 없습니다: {templates_dir}. 사용 가능: {available}"
    )


def infer_template_type(path: Path) -> Optional[str]:
    normalized_name = normalize_korean(path.name).casefold()
    if "full" in normalized_name:
        return "full"
    if "간소화" in normalized_name:
        return "simple"
    return None

def make_topic_slug(topic: str) -> str:
    slug = re.sub(r"\s+", "", normalize_korean(topic))
    slug = re.sub(r"[^\w가-힣]", "", slug, flags=re.UNICODE)
    return slug or "정책서"


def normalize_korean(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def make_output_filename(ctx: PolicyContext) -> str:
    return f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}.html"


def make_bpmn_output_filename(ctx: PolicyContext) -> str:
    return f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_전체업무흐름도.bpmn"


def make_versioned_spec_filename(ctx: PolicyContext) -> str:
    return f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_spec.json"


def make_spec_filename(ctx: PolicyContext) -> str:
    return f"{ctx.topic_slug}_policy_spec.json"


def make_blueprint_filename(ctx: PolicyContext) -> str:
    return f"{ctx.topic_slug}_authoring_blueprint.json"


def load_previous_document_history(
    output_dir: Path,
    topic_slug: str,
    template_type: str,
    current_version: str,
) -> List[Dict[str, str]]:
    previous_path = previous_policy_version_path(output_dir, topic_slug, template_type, current_version)
    if not previous_path:
        return []
    try:
        return extract_document_history(previous_path.read_text(encoding="utf-8"))
    except OSError:
        return []


def previous_policy_version_path(
    output_dir: Path,
    topic_slug: str,
    template_type: str,
    current_version: str,
) -> Optional[Path]:
    file_label = template_file_label(template_type)
    current = version_tuple(current_version)
    if current is None:
        return None
    pattern = re.compile(
        rf"^NC_{re.escape(topic_slug)}_정책서_{re.escape(file_label)}_v(?P<major>\d+)\.(?P<minor>\d+)\.html$"
    )
    candidates: List[Tuple[Tuple[int, int], Path]] = []
    for path in output_dir.glob(f"NC_{topic_slug}_정책서_{file_label}_v*.html"):
        match = pattern.match(path.name)
        if not match:
            continue
        version_key = (int(match.group("major")), int(match.group("minor")))
        if version_key < current:
            candidates.append((version_key, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def version_tuple(version: str) -> Optional[Tuple[int, int]]:
    parsed = parse_policy_version(version)
    if parsed is None or parsed[2]:
        return None
    return parsed[0], parsed[1]


def extract_document_history(document: str) -> List[Dict[str, str]]:
    match = re.search(
        r"<h2>\s*0\.\s*문서 히스토리\s*</h2>.*?<tbody>(?P<body>.*?)</tbody>",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return []
    rows: List[Dict[str, str]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match.group("body"), flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 4:
            continue
        item = {
            "version": html_cell_text(cells[0]),
            "change": html_cell_text(cells[1]),
            "date": html_cell_text(cells[2]),
            "author": html_cell_text(cells[3]),
        }
        if item["version"] or item["change"]:
            rows.append(item)
    return rows


def html_cell_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def merge_continued_document_history(spec: Dict[str, Any], ctx: PolicyContext, previous_history: Sequence[Mapping[str, str]]) -> bool:
    if not previous_history:
        return False
    current_history = [item for item in spec.get("history", []) if isinstance(item, Mapping)]
    current_rows = [dict(item) for item in current_history if str(item.get("version", "")).strip() == ctx.version]
    if current_rows:
        current = current_rows[-1]
    else:
        current = {
            "version": ctx.version,
            "change": "",
            "date": ctx.today,
            "author": ctx.author,
        }
    previous_version = str(previous_history[-1].get("version", "") or "").strip()
    base_label = f"{previous_version} 문서" if previous_version else "기존 문서"
    brief = f" 작성 요청 메모는 '{ctx.brief}'로 기록한다." if getattr(ctx, "brief", "").strip() else ""
    current.update(
        {
            "version": ctx.version,
            "change": f"{base_label} 기준으로 신규 재작성. 기존 문서는 보존하고 본문은 새로 작성했으며 문서 히스토리는 이전 버전에서 이어간다.{brief}",
            "date": str(current.get("date") or ctx.today),
            "author": str(current.get("author") or ctx.author),
        }
    )
    carried: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for item in previous_history:
        version = str(item.get("version", "") or "").strip()
        change = str(item.get("change", "") or "").strip()
        if not version and not change:
            continue
        if version == ctx.version:
            continue
        key = (version, change)
        if key in seen:
            continue
        seen.add(key)
        carried.append(
            {
                "version": version,
                "change": change,
                "date": str(item.get("date", "") or "").strip(),
                "author": str(item.get("author", "") or "").strip(),
            }
        )
    spec["history"] = carried + [current]
    return True


def next_version(output_dir: Path, topic_slug: str, template_type: str) -> str:
    file_label = template_file_label(template_type)
    pattern = re.compile(
        rf"^NC_{re.escape(topic_slug)}_정책서_{re.escape(file_label)}_v(?P<major>\d+)\.(?P<minor>\d+)\.html$"
    )
    versions: List[str] = []

    for path in output_dir.glob(f"NC_{topic_slug}_정책서_{file_label}_v*.html"):
        match = pattern.match(path.name)
        if match:
            versions.append(f"v{match.group('major')}.{match.group('minor')}")

    return next_policy_version(versions)


def template_file_label(template_type: str) -> str:
    return "Full" if template_type == "full" else "간소화"


def make_business_code(topic: str) -> str:
    normalized = topic.replace(" ", "").upper()
    keyword_codes = {
        "AI검색": "AIS",
        "선물": "GFT",
        "상품변경": "CHG",
        "주문": "ORD",
        "계약": "ORD",
        "상품": "PRD",
        "시뮬레이션": "SIM",
        "할인": "SIM",
        "요금제": "PLN",
        "결제": "PAY",
        "납부": "PAY",
        "청구": "BIL",
        "회원": "MBR",
        "멤버십": "MBR",
        "장바구니": "CRT",
        "카트": "CRT",
        "담기": "CRT",
        "가입": "SUB",
        "해지": "TRM",
        "변경": "CHG",
        "인증": "AUT",
        "검색": "SRC",
    }

    for keyword, code in keyword_codes.items():
        if keyword in normalized:
            return code

    ascii_letters = re.findall(r"[A-Z]", normalized)
    if len(ascii_letters) >= 3:
        return "".join(ascii_letters[:3])

    digest = hashlib.sha1(topic.encode("utf-8")).digest()
    return "".join(chr(ord("A") + byte % 26) for byte in digest[:3])


def make_module_id(topic: str) -> str:
    """Return the stable PM module ID for the current 34-topic policy set."""

    target = normalize_topic_key(topic)
    for index, known_topic in enumerate(POLICY_TOPICS, start=1):
        if normalize_topic_key(known_topic) == target:
            return f"PM-{index:02d}"
    return ""


def normalize_topic_key(topic: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", normalize_korean(str(topic or ""))).casefold()


def generation_stages() -> Iterable[Tuple[str, str, str]]:
    return (
        ("01", "cover", "01_cover"),
        ("02", "history", "02_history"),
        ("03", "overview", "03_overview"),
        ("04", "terms", "04_terms"),
        ("05", "usecases", "05_usecases"),
        ("06", "process", "06_process"),
        ("07", "functions", "07_functions"),
        ("08", "policies", "08_policies"),
        ("09_terms_refinement", "terms_refinement", "09_terms_refinement"),
        ("10", "final_check", "10_final"),
    )


def save_stage_snapshot(document: str, ctx: PolicyContext, stage_key: str, stage_name: str) -> Path:
    steps_dir = ctx.output_dir / "steps"
    steps_dir.mkdir(parents=True, exist_ok=True)
    stage_path = steps_dir / (
        f"NC_{ctx.topic_slug}_정책서_{template_file_label(ctx.template_type)}_{ctx.version}_{stage_key}_{stage_name}.html"
    )
    stage_path.write_text(document, encoding="utf-8")
    return stage_path


def stage_artifact_payload(path: Path, ctx: PolicyContext) -> dict:
    relative = path.relative_to(ctx.output_dir)
    return {
        "name": path.name,
        "path": str(relative),
        "url": f"/output/{quote(str(relative), safe='/')}",
    }


def build_stage_activity_preview(spec: dict, stage) -> dict:
    counts = {
        "용어": len(spec.get("terms", [])),
        "액터": len(spec.get("actors", [])),
        "유즈케이스": len(spec.get("usecases", [])),
        "상태": len(spec.get("states", [])),
        "상태 전이": len(spec.get("state_transitions", [])),
        "프로세스": len(spec.get("processes", [])),
        "프로세스 상세": len(spec.get("process_details", [])),
        "기능": len(spec.get("functions", [])),
        "기능 상세": len(spec.get("function_details", [])),
        "정책 그룹": len(spec.get("policy_groups", [])),
        "정책 상세": len(spec.get("policy_details", [])),
    }
    items = [f"{label} {count}건" for label, count in counts.items() if count]
    if stage.agent.chapter_key == "overview":
        overview = spec.get("overview", {})
        items = [
            f"범위 {len(overview.get('scope', []))}건",
            f"설계 원칙 {len(overview.get('principles', []))}건",
        ]
    if stage.agent.chapter_key == "usecase_diagram":
        lines = spec.get("meta", {}).get("usecase_diagram", {}).get("lines", [])
        items = [f"다이어그램 관계 {len(lines)}건"]
    if stage.agent.chapter_key == "terms_refinement":
        items = [f"전체 문서 검토 후 용어 {len(spec.get('terms', []))}건으로 업데이트"]
    if stage.agent.chapter_key == "process_detail":
        items = [f"프로세스 상세 {len(spec.get('process_details', []))}건"]
    if stage.agent.chapter_key == "function_detail":
        items = [f"기능 상세 {len(spec.get('function_details', []))}건"]
    if stage.agent.chapter_key == "final_check":
        items = [f"최종 점검 기준 {len(spec.get('final_check', []))}건"]
    return {
        "title": f"{stage.agent.display_name} 임시 결과",
        "items": items[:12] or ["현재 장의 JSON 작성 결과를 HTML로 렌더링했습니다."],
    }


def stage_html_smoke_feedback(document: str, stage) -> List[Dict[str, str]]:
    """Catch renderer/template regressions cheaply without another LLM call."""
    feedback: List[Dict[str, str]] = []
    lowered = document.lower()
    required_tokens = {
        "<!doctype html": "HTML 문서 선언",
        "<html": "html 루트",
        "<head": "head 영역",
        "<body": "body 영역",
        "</html>": "html 종료 태그",
        "<style": "템플릿 CSS",
    }
    for token, label in required_tokens.items():
        if token not in lowered:
            feedback.append(html_smoke_issue("error", "HTML 렌더링", f"{label} 누락", f"렌더링 결과에서 {label}을 찾지 못했습니다."))
    unresolved = unresolved_template_tokens(document)
    if unresolved:
        feedback.append(
            html_smoke_issue(
                "error",
                "HTML 렌더링",
                "템플릿 치환값 잔존",
                f"렌더링 결과에 치환되지 않은 템플릿 토큰이 남아 있습니다: {', '.join(unresolved[:5])}",
            )
        )
    if stage.agent.chapter_key == "usecase_diagram" and ("uml-usecase-diagram" not in document or "<svg" not in lowered):
        feedback.append(
            html_smoke_issue(
                "error",
                "다이어그램 렌더링",
                "유즈케이스 SVG 다이어그램 누락",
                "다이어그램 작성 단계인데 샘플 양식의 SVG 유즈케이스 다이어그램을 찾지 못했습니다.",
            )
        )
    if stage.agent.chapter_key == "process" and '<pre class="mermaid">' not in document and "bpmn-process-diagram" not in document:
        feedback.append(
            html_smoke_issue(
                "error",
                "다이어그램 렌더링",
                "프로세스 다이어그램 누락",
                "프로세스 작성 단계인데 전체 업무 흐름도 렌더링 블록을 찾지 못했습니다.",
            )
        )
    if len(document.strip()) < 1200:
        feedback.append(
            html_smoke_issue(
                "warning",
                "HTML 렌더링",
                "렌더링 결과가 비정상적으로 짧음",
                "정책서 HTML 길이가 짧아 템플릿 또는 현재 장 렌더링 누락 가능성이 있습니다.",
            )
        )
    return feedback


def html_smoke_issue(severity: str, category: str, title: str, detail: str) -> Dict[str, str]:
    return {
        "issue_id": f"HTML-{hashlib.sha1((category + title + detail).encode('utf-8')).hexdigest()[:8].upper()}",
        "must_resolve": "Y" if severity == "error" else "N",
        "repair_scope": "HTML 렌더링 기본 구조",
        "failure_type": "format_structure",
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
        "recommendation": "JSON 산출물은 유지하되 렌더링 누락, 템플릿 치환, 다이어그램 출력 구조를 확인하세요.",
        "acceptance_check": "다음 단계 HTML 렌더링 결과에 동일한 구조 오류가 없어야 합니다.",
    }


def unresolved_template_tokens(document: str) -> List[str]:
    candidates = re.findall(r"\{[^{}\n]{1,80}\}", document)
    return sorted({token for token in candidates if any(ch in token for ch in ("업무", "작성", "버전", "YYYY", "정책", "기준"))})


def record_stage_html_smoke_check(stage_spec: dict, stage, attempt: int, feedback: Sequence[Mapping[str, object]]) -> None:
    stage_spec.setdefault("meta", {}).setdefault("html_smoke_checks", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "attempt": attempt,
            "scope": stage.scope,
            "passed": not any(item.get("severity") == "error" for item in feedback if isinstance(item, Mapping)),
            "finding_count": len(feedback),
            "findings": [
                {
                    "severity": item.get("severity"),
                    "category": item.get("category"),
                    "title": item.get("title"),
                    "detail": item.get("detail"),
                }
                for item in feedback
                if isinstance(item, Mapping)
            ],
        }
    )


def render_cover(document: str, ctx: PolicyContext) -> str:
    file_label = template_file_label(ctx.template_type)
    document = re.sub(
        r"<title>.*?</title>",
        f"<title>{ctx.topic_html} 정책서 {file_label} {ctx.version}</title>",
        document,
        count=1,
        flags=re.DOTALL,
    )
    replacements = {
        "통합채널 정책서 간소화 버전 템플릿": "통합채널 정책서 간소화 버전",
        "통합채널 정책서 Full 버전 템플릿": "통합채널 정책서 Full 버전",
        "{업무명}": ctx.topic_html,
        "{POL-업무코드}": f"POL-{ctx.business_code}",
        "{작성중 | 검토중 | 확정본}": html.escape(ctx.status),
        "{버전}": ctx.version_number,
        "{작성자}": html.escape(ctx.author),
        "{YYYY-MM-DD}": ctx.today,
        "{업무코드}": ctx.business_code,
    }
    return apply_replacements(document, replacements)


def render_history(document: str, ctx: PolicyContext) -> str:
    brief_text = f" 작성 요청: {ctx.brief_html}." if ctx.brief_html else ""
    history_body = f"""
<tr>
<td>{ctx.version}</td>
<td>{ctx.topic_html} 정책서 초안 작성. 문서 범위, 설계 원칙, 주요 용어, 유즈케이스, 프로세스, 기능, 정책 정의 구조를 생성.{brief_text}</td>
<td>{ctx.today}</td>
<td>{html.escape(ctx.author)}</td>
</tr>
"""
    pattern = r"(<h2>0\. 문서 히스토리</h2>.*?<tbody>).*?(</tbody>)"
    return re.sub(pattern, rf"\1{history_body}\2", document, count=1, flags=re.DOTALL)


def render_overview(document: str, ctx: PolicyContext) -> str:
    topic = ctx.topic_html
    replacements = {
        "{업무 영역}": f"{topic} 업무",
        "{핵심 업무 1}": f"{topic} 조회",
        "{핵심 업무 2}": f"{topic} 조건 확인",
        "{핵심 업무 3}": f"{topic} 처리 신청",
        "{대상 고객}": "통합채널 앱·웹을 이용하는 고객",
        "{제외 범위}": "BO 상세 운영 화면, API 필드, DB 컬럼, 상세 UI 문구",
        "{후속 산출물명}": "화면 설계서 및 기능 상세 명세서",
        "{원칙 1}": "고객 과업 중심",
        "{해당 원칙의 적용 기준을 한 문장으로 작성한다.}": (
            f"{topic} 업무는 고객이 원하는 정보를 확인하고 다음 행동을 선택할 수 있는 단위로 구성한다."
        ),
        "{원칙 2}": "채널·BSS 역할 분리",
        "{채널과 BSS의 역할 분담 기준을 작성한다.}": (
            "채널은 고객 입력과 안내를 담당하고, BSS는 가능 여부 검증과 상태 반영을 담당한다."
        ),
        "{원칙 3}": "정책 판단 우선",
        "{법률·보안·리스크 관련 상위 기준을 작성한다.}": (
            "고객 정보, 요금, 혜택, 약정 등 민감한 판단은 사전 고지와 인증 기준을 따른다."
        ),
        "{원칙 4}": "셀프 처리 우선",
        "{셀프 처리, 원스톱 처리, 예외 처리 기준을 작성한다.}": (
            "고객이 앱·웹에서 직접 완료할 수 있도록 하되 예외 상황은 상담 또는 후속 업무로 연결한다."
        ),
        "{원칙 5}": "이력 추적 가능성",
        "{업무 특성에 맞는 추가 원칙을 작성한다.}": (
            "주요 조회, 신청, 변경, 실패, 예외 처리 결과는 추적 가능한 이력으로 저장한다."
        ),
    }
    return apply_replacements(document, replacements)


def render_chapters(document: str, ctx: PolicyContext) -> str:
    topic = ctx.topic_html
    code = ctx.business_code
    replacements = {
        "{용어명}": ctx.topic_html,
        "{업무 또는 정책에서 사용하는 의미를 한 문장으로 정의한다.}": (
            f"통합채널에서 고객이 {topic} 정보를 확인하고 필요한 후속 처리를 진행하는 업무를 의미한다."
        ),
        "{상태/고객유형/처리유형}": "처리 가능 상태",
        "{다른 용어와 혼동되지 않도록 판단 기준을 포함한다.}": (
            f"고객 상태와 상품 조건이 {topic} 업무를 진행할 수 있는 기준을 충족한 상태를 의미한다."
        ),
        "{시스템/데이터/정책 용어}": "연계 처리 결과",
        "{채널·BSS·외부기관 간 해석 차이가 없도록 정의한다.}": (
            "BSS 또는 외부 연계 시스템이 검증, 조회, 반영 결과를 채널에 회신한 값을 의미한다."
        ),
        "{해당 업무를 직접 신청·조회·변경·종료하는 주체}": (
            f"{topic} 정보를 조회하고 조건을 확인하며 필요한 경우 후속 처리를 요청하는 주체"
        ),
        "{대리인/법정대리인/가족}": "대리인",
        "{대리 처리 또는 동의가 필요한 경우의 주체}": (
            f"고객 본인 외 권한 확인 또는 동의가 필요한 경우 {topic} 업무를 보조하는 주체"
        ),
        "{외부기관/BSS/제휴사}": "BSS",
        "{검증, 승인, 상태 변경, 결과 제공을 수행하는 시스템 또는 기관}": (
            f"{topic} 가능 여부, 고객 상태, 상품 조건, 처리 결과를 검증하고 회신하는 시스템"
        ),
        "{상위 유즈케이스명}": f"{topic} 확인 및 처리",
        "{고객이 이 업무를 수행하는 목적과 완료 상태를 한 문장으로 작성한다.}": (
            f"고객이 {topic} 정보를 확인하고 조건을 충족하면 필요한 후속 업무로 진입하기 위해 수행하는 유즈케이스"
        ),
        "{시스템 처리 유즈케이스명}": f"{topic} 가능 여부 검증",
        "{고객 업무를 지원하기 위해 시스템이 수행하는 검증·처리·저장 업무를 작성한다.}": (
            f"BSS가 고객 상태와 상품 조건을 조회하여 {topic} 업무 가능 여부와 제한 사유를 회신한다."
        ),
        "{유즈케이스 다이어그램 삽입 영역}": f"{topic} 유즈케이스 다이어그램 삽입 영역",
        "{STATE_CODE_001}": f"ST-{code}-001",
        "{STATE_CODE_002}": f"ST-{code}-002",
        "{상태명}": "처리 가능",
        "{이 상태로 판단되는 조건을 작성한다.}": (
            f"고객 상태와 상품 조건이 {topic} 업무 진행 기준을 충족한 경우"
        ),
        "{다음 가능 업무 또는 노출 기준을 작성한다.}": (
            "고객에게 상세 정보와 후속 처리 가능 경로를 노출한다."
        ),
        "{다음 가능 업무 또는 제한 기준을 작성한다.}": (
            "제한 사유와 대체 처리 경로를 고객에게 안내한다."
        ),
        "{현재 상태}": "처리 가능",
        "{전이 이벤트}": f"{topic} 처리 요청",
        "{예외/취소/실패 이벤트}": "검증 실패 또는 고객 취소",
        "{다음 상태}": "처리 완료",
        "{상태 변경 조건, 저장 이력, 고객 안내, 실패 시 처리 기준을 작성한다.}": (
            "BSS 검증이 성공하면 처리 완료 상태로 전환하고 처리 이력과 결과 안내를 저장한다."
        ),
        "{예외 처리 기준과 복구 또는 재시도 가능 여부를 작성한다.}": (
            "검증 실패 시 제한 사유를 안내하고 재시도 가능 여부 또는 상담 연결 기준을 제공한다."
        ),
        "{상태 전이 다이어그램 삽입 영역}": f"{topic} 상태 전이 다이어그램 삽입 영역",
        "{유즈케이스명}": f"{topic} 확인 및 처리",
        "{유즈케이스 ID}": f"US-{code}-CS-001",
        "{프로세스명}": f"{topic} 정보 확인",
        "{프로세스 ID}": f"PR-{code}-CS-001-01",
        "{고객 또는 시스템이 수행하는 처리 내용을 한 문장으로 작성한다.}": (
            f"고객이 {topic} 정보를 요청하면 채널은 기본 정보를 조회하고 BSS 검증을 요청한다."
        ),
        "{다음 처리 단계를 작성한다.}": (
            "검증 결과에 따라 고객에게 처리 가능 여부, 제한 사유, 후속 업무 진입 경로를 안내한다."
        ),
        "{두 번째 유즈케이스의 첫 프로세스를 작성한다.}": (
            f"{topic} 처리 결과와 주요 이력을 저장하고 고객에게 완료 결과를 안내한다."
        ),
        "{관련 기능명 1}": f"{topic} 정보 조회",
        "{관련 기능명 2}": "가능 여부 검증",
        "{관련 기능명}": f"{topic} 결과 안내",
        "{관련 정책명 1}": f"PG-{code}-ACC-001 조회 권한 정책",
        "{관련 정책명 2}": f"PG-{code}-VAL-001 처리 가능 조건 정책",
        "{관련 정책명}": f"PG-{code}-RSLT-001 결과 안내 정책",
        "{전체 업무 흐름도 삽입 영역}": f"{topic} 전체 업무 흐름도 삽입 영역",
        "{기능명}": f"{topic} 처리 기능",
        "{기능이 수행하는 처리 결과를 한 문장으로 작성한다.}": (
            f"{topic} 조회, 가능 여부 검증, 결과 안내를 수행하여 고객이 후속 업무를 선택할 수 있게 한다."
        ),
        "{기능 설명}": (
            f"{topic} 업무 진행에 필요한 고객 상태, 상품 조건, 처리 결과를 조회하고 안내한다."
        ),
        "{영역코드}": "COM",
        "{세부 기능 1}": "고객 상태 조회",
        "{세부 기능 2}": "상품 조건 및 제한 기준 검증",
        "{세부 기능 3}": "처리 결과 안내 및 이력 저장",
        "{정책영역}": "COM",
        "{정책명}": f"{topic} 처리 기준 정책",
        "{이 정책 그룹이 정의하는 판단 기준을 한 문장으로 작성한다.}": (
            f"{topic} 업무의 조회 가능 여부, 처리 가능 조건, 예외 안내 기준을 정의한다."
        ),
        "{정책 설명}": (
            f"{topic} 업무에서 고객 상태, 상품 조건, 연계 결과에 따라 적용할 처리 기준을 정의한다."
        ),
        "{정책 항목 1}": "조회 가능 대상",
        "{정책 항목 2}": "처리 제한 조건",
        "{정책 항목 3}": "예외 안내 기준",
        "{정책 ID}": f"PG-{code}-COM-001",
        "{정책 항목명}": "조회 가능 대상",
        "{정책 항목 ID}": f"PI-{code}-COM-001",
        "{정책 내용.<br/>실제 허용값, 제한 조건, 처리 기준을 명확히 작성한다.}": (
            f"{topic} 정보는 본인 확인 또는 세션 권한이 유효한 고객에게 제공한다.<br/>"
            "권한이 확인되지 않으면 상세 정보 대신 로그인 또는 인증 경로를 안내한다."
        ),
        "{정책 내용}": (
            "처리 기준이 미정인 항목은 TBD로 표시하고 결정 주체, 사유, 기한을 함께 기록한다."
        ),
        "{예외 기준}": "예외 안내 기준",
        "{예외 허용 조건, 예외 불가 조건, 후속 처리 기준을 작성한다.}": (
            "BSS 검증 실패, 고객 상태 제한, 상품 조건 불일치가 발생하면 제한 사유와 상담 또는 대체 경로를 안내한다."
        ),
    }

    return apply_replacements(document, replacements)


def apply_replacements(document: str, replacements: Dict[str, str]) -> str:
    for placeholder, value in replacements.items():
        document = document.replace(placeholder, value)
    return document


def normalize_sentence_breaks(document: str) -> str:
    """Add <br/> after sentence-ending periods without touching code-like blocks."""
    parts = re.split(
        r"(<style\b.*?</style>|<script\b.*?</script>|<pre\b.*?</pre>|<svg\b.*?</svg>|<[^>]+>)",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    normalized: List[str] = []

    for index, part in enumerate(parts):
        if not part or part.startswith("<"):
            normalized.append(part)
            continue

        next_token = next_non_empty_token(parts, index + 1)
        part = add_breaks_after_inline_sentence_periods(part)
        if ends_with_sentence_period(part) and not is_br_tag(next_token):
            part = re.sub(r"(?<!\d)([.!?])(\s*)$", r"\1<br/>\2", part)
        normalized.append(part)

    return "".join(normalized)


def add_breaks_after_inline_sentence_periods(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        preceding_text = value[: match.start()].strip()
        if re.fullmatch(r"[가-힣A-Za-z0-9]", preceding_text):
            return match.group(0)
        return f"{match.group(1)}<br/>"

    return re.sub(r"(?<!\d)([.!?])[\t ]+(?=\S)", replace, value)


def next_non_empty_token(parts: List[str], start_index: int) -> str:
    for token in parts[start_index:]:
        if token and token.strip():
            return token
    return ""


def ends_with_sentence_period(value: str) -> bool:
    return re.search(r"(?<!\d)[.!?]\s*$", value) is not None


def is_br_tag(value: str) -> bool:
    return re.fullmatch(r"<br\s*/?>", value.strip(), flags=re.IGNORECASE) is not None


if __name__ == "__main__":
    main()
