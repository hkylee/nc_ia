"""Policy generation orchestrator.

This module owns the run order: topic learning, blueprint creation, chapter
agent execution, inspector feedback loops, and handoff behavior.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Callable, Mapping, Sequence

try:
    from authoring_blueprint import build_authoring_blueprint, compact_blueprint_for_spec
    from blueprint_architect import build_architecture_contract, enhance_architecture_contract_with_llm
    from blueprint_quality import validate_blueprint_quality
    from chain_matrix import chain_matrix_fingerprint
    from chapter_agents import (
        AgentRuntime,
        ChapterStage,
        build_agent_guideline,
        chapter_stages,
        emit_progress,
        enhance_learning_with_llm,
        initialize_spec,
        learn_topic,
        manual_review_feedback,
        manual_revision_requested,
        request_manual_stage_review,
    )
    from evidence_store import build_evidence_store
    from evidence_map import build_topic_evidence_map
    from gate_policy import gate_required_score, gate_rule_summary, gate_tier, stage_max_loops
    from llm_client import LLMClient
    from llm_routing import client_for_route, routing_plan
    from policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE
    from schema import build_policy_spec, ensure_policy_spec_base_keys
    from validator import validate_stage_critical
except ImportError:  # pragma: no cover - package import fallback.
    from .authoring_blueprint import build_authoring_blueprint, compact_blueprint_for_spec
    from .blueprint_architect import build_architecture_contract, enhance_architecture_contract_with_llm
    from .blueprint_quality import validate_blueprint_quality
    from .chain_matrix import chain_matrix_fingerprint
    from .chapter_agents import (
        AgentRuntime,
        ChapterStage,
        build_agent_guideline,
        chapter_stages,
        emit_progress,
        enhance_learning_with_llm,
        initialize_spec,
        learn_topic,
        manual_review_feedback,
        manual_revision_requested,
        request_manual_stage_review,
    )
    from .evidence_store import build_evidence_store
    from .evidence_map import build_topic_evidence_map
    from .gate_policy import gate_required_score, gate_rule_summary, gate_tier, stage_max_loops
    from .llm_client import LLMClient
    from .llm_routing import client_for_route, routing_plan
    from .policy_inspector import DEFAULT_INSPECTOR_MIN_SCORE
    from .schema import build_policy_spec, ensure_policy_spec_base_keys
    from .validator import validate_stage_critical


INSPECTOR_PASS_CACHE_VERSION = "inspector-pass-v5-first-draft-local-gate"


STAGE_NARRATIVES = {
    "learning": {
        "start": "요구사항, 참고자료 DB, 템플릿과 샘플을 먼저 맞춰 보고 있어요. 이 단계에서는 바로 문장을 쓰기보다 어떤 관점으로 정책서를 써야 할지 기준선을 잡습니다.",
        "update": "수집한 근거를 장별로 나누고 있어요. 각 Agent가 전체 자료를 다시 읽지 않아도 필요한 근거만 보게 만드는 준비 단계입니다.",
        "complete": "주제 학습이 끝났습니다. 이제 이 기준을 바탕으로 장별 Agent가 같은 방향을 보고 작성하도록 넘깁니다.",
    },
    "overview": {
        "start": "개요를 작성합니다. 고객이 인식하는 업무 범위, 제외 범위, 설계 원칙을 먼저 잡아 뒤 장의 기준선으로 쓰겠습니다.",
        "validate": "개요가 너무 넓거나 추상적이지 않은지 확인합니다. 이후 액터와 유즈케이스가 이 범위를 벗어나지 않게 하려는 단계입니다.",
        "complete": "개요 기준이 잡혔습니다. 다음 장에서는 이 범위 안에서 정책 판단에 필요한 용어를 정리합니다.",
    },
    "terms": {
        "start": "주요 용어를 정리합니다. 일반 명사보다는 상태, 권한, 인증, 동의, 보관처럼 뒤에서 판단 기준으로 쓰일 표현을 고릅니다.",
        "validate": "용어가 너무 많거나 일반 설명으로 흐르지 않는지 확인합니다. 이후 장에서 같은 개념을 다른 이름으로 쓰지 않게 맞춥니다.",
        "complete": "용어 기준을 정리했습니다. 다음에는 독립 책임 주체인 액터를 구분합니다.",
    },
    "actors": {
        "start": "액터를 정의합니다. 로그인/정상/제한 같은 고객 상태는 액터로 쪼개지 않고, 책임이 다른 주체만 분리합니다.",
        "validate": "액터가 과도하게 쪼개지지 않았는지, 유즈케이스를 시작하거나 결과를 만드는 책임 주체인지 확인합니다.",
        "complete": "액터 책임 경계를 정리했습니다. 다음에는 각 액터가 완결해야 하는 업무 단위인 유즈케이스를 작성합니다.",
    },
    "usecases": {
        "start": "유즈케이스를 작성합니다. 고객이나 운영자가 끝내려는 상위 업무 목적을 중심으로 잡고, 인증/입력/확인 같은 절차는 프로세스로 내려보냅니다.",
        "validate": "사람 액터 유즈케이스는 프로세스 정의 대상인지, 시스템 액터 유즈케이스는 보조 처리로 정리됐는지 확인합니다.",
        "complete": "유즈케이스 구조가 잡혔습니다. 다음에는 이 관계를 다이어그램으로 시각화합니다.",
    },
    "usecase_diagram": {
        "start": "유즈케이스 다이어그램을 작성합니다. 액터와 유즈케이스 관계를 UML 2.0 기준에 맞춰 한눈에 보이게 정리합니다.",
        "validate": "다이어그램이 UI 단계가 아니라 액터와 업무 관계를 표현하는지 확인합니다.",
        "complete": "유즈케이스 관계를 시각화했습니다. 다음에는 유즈케이스가 바꾸는 업무 상태와 전이를 정의합니다.",
    },
    "state": {
        "start": "상태와 상태 전이를 작성합니다. 액터-유즈케이스 관계에서 상태 후보를 도출하고, 전이 이벤트는 상태를 바꾸는 업무 사건으로 정리합니다.",
        "validate": "현재 상태와 다음 상태가 상태 목록에 있는지, 전이 이벤트가 업무 사건이고 usecase_ids로 유즈케이스 추적성이 남았는지 확인합니다.",
        "complete": "상태 전이 기준을 정리했습니다. 다음에는 사람 액터 유즈케이스를 완료하는 세부 프로세스를 작성합니다.",
    },
    "process": {
        "start": "프로세스를 작성합니다. 유즈케이스 하나를 하나의 프로세스로 끝내지 않고, 시작·판단·입력·검증·요청·결과 안내 같은 세부 절차로 나눕니다.",
        "validate": "프로세스가 유즈케이스와 상태 기준을 잘 이어받았는지 확인합니다. 관련 기능과 정책은 아직 예측하지 않고 뒤에서 연결합니다.",
        "complete": "프로세스 흐름을 정리했습니다. 다음에는 각 프로세스를 수행하는 기능을 정의합니다.",
    },
    "functions": {
        "start": "기능을 정의합니다. 화면 단위가 아니라 프로세스를 수행하는 조회, 검증, 저장, 알림, 연동 같은 처리 역량으로 묶습니다.",
        "validate": "각 프로세스가 필요한 기능으로 연결됐는지 확인합니다. 정책값은 기능 설명에 길게 쓰지 않고 정책 장으로 넘깁니다.",
        "complete": "기능 목록을 정리했습니다. 다음에는 기능이 동작하기 위해 필요한 정책값과 제한 기준을 정의합니다.",
    },
    "policies": {
        "start": "정책을 작성합니다. 일반 원칙이 아니라 인증 수단, 가능 횟수, 유효시간, 제한 조건, 고지와 이력 저장처럼 실제 기능 동작에 필요한 값을 정의합니다.",
        "validate": "정책이 기능 설명으로 흐르지 않고, 정책 그룹과 정책 상세가 항목별 값으로 선언됐는지 확인합니다.",
        "complete": "정책 기준을 정리했습니다. 이제 프로세스와 기능이 참조할 정책 기준이 갖춰졌습니다.",
    },
    "process_detail": {
        "start": "Full 버전 프로세스 상세를 작성합니다. 각 프로세스의 진입 조건, 종료 조건, 선행·후행 관계를 상세 설계 입력 수준으로 보강합니다.",
        "validate": "프로세스 상세가 기존 프로세스, 기능, 정책 ID를 정확히 참조하는지 확인합니다.",
        "complete": "프로세스 상세를 정리했습니다. 다음에는 기능 상세를 보강합니다.",
    },
    "function_detail": {
        "start": "Full 버전 기능 상세를 작성합니다. 입력 정보, 처리 로직, 출력 정보, 실패·예외 케이스를 구현자가 이해할 수 있는 수준으로 확장합니다.",
        "validate": "기능 상세가 정책값을 직접 풀어쓰지 않고 관련 정책으로 연결되는지 확인합니다.",
        "complete": "기능 상세를 정리했습니다. 다음에는 전체 문서를 보고 용어를 다시 맞춥니다.",
    },
    "terms_refinement": {
        "start": "용어를 한 번 더 점검합니다. 기능과 정책까지 작성한 뒤 실제로 쓰인 판단 용어가 빠졌는지 확인합니다.",
        "validate": "새 용어가 일반 명사가 아니라 정책 판단에 필요한 용어인지 확인합니다.",
        "complete": "용어 재정비를 마쳤습니다. 이제 최종 점검 기준을 작성합니다.",
    },
    "final_check": {
        "start": "최종 점검 기준을 작성합니다. 범위, 고객 완결성, 상태 전이, 프로세스-기능-정책 연결, 개인정보와 운영 기준을 확인할 수 있게 정리합니다.",
        "validate": "최종 점검 항목이 현재 주제에 맞고, 실제 검토자가 확인할 수 있는 기준인지 확인합니다.",
        "complete": "최종 점검 기준을 정리했습니다. 마지막으로 전체 JSON과 HTML을 저장하고 Final Inspector를 실행합니다.",
    },
    "finalize": {
        "start": "전체 문서를 마무리합니다. 장별 JSON 연결성을 확인하고 HTML 템플릿에 최종 렌더링합니다.",
        "update": "최종 Inspector가 문서 전체를 다시 보고 있습니다. 장별로 놓친 정합성이나 샘플 수준 차이가 있는지 마지막으로 확인합니다.",
        "complete": "정책서 생성이 완료됐습니다. 이제 문서 작업실에서 미리보기, 직접 편집, Agent 보완 요청을 이어갈 수 있습니다.",
    },
}


def stage_narrative(stage_name: str, moment: str, fallback: str = "") -> str:
    key = str(stage_name or "").strip()
    moment_key = str(moment or "").strip()
    stage_map = STAGE_NARRATIVES.get(key, {})
    return stage_map.get(moment_key) or stage_map.get("update") or fallback


def orchestrate_policy_generation(
    ctx,
    template_html: str,
    sample_htmls: Sequence[str],
    after_stage: Callable[[dict, ChapterStage, int], Mapping[str, object] | None] | None = None,
    resume_checkpoint: Mapping[str, object] | None = None,
) -> dict:
    guideline = build_agent_guideline(template_html, sample_htmls)
    llm_client = LLMClient.from_context(ctx)
    target_spec = build_policy_spec(ctx)
    evidence_store = build_evidence_store(ctx, guideline)
    resume_spec = checkpoint_spec(resume_checkpoint)

    emit_progress(
        ctx,
        "stage_start",
        stage_key="00",
        stage_name="learning",
        label="주제 학습",
        message=stage_narrative("learning", "start"),
    )
    if resume_spec:
        learning = resume_learning(resume_spec) or enhance_learning_with_llm(ctx, learn_topic(ctx), guideline, llm_client)
        emit_progress(
            ctx,
            "stage_update",
            stage_key="00",
            stage_name="learning",
            label="주제 학습",
            message="체크포인트의 주제 학습 결과를 불러와 이어서 작성합니다. 이전에 정리한 기준을 유지하면서 아직 작성하지 않은 장부터 계속 진행합니다.",
        )
    else:
        learning = enhance_learning_with_llm(ctx, learn_topic(ctx), guideline, llm_client)
    resumed_blueprint = resume_authoring_blueprint(resume_spec) if resume_spec else None
    if resumed_blueprint:
        authoring_blueprint = resumed_blueprint
        blueprint_quality = authoring_blueprint.get("quality_gate", {})
        if not isinstance(blueprint_quality, Mapping) or not blueprint_quality:
            blueprint_quality = validate_blueprint_quality(authoring_blueprint, learning)
            authoring_blueprint["quality_gate"] = blueprint_quality
        emit_progress(
            ctx,
            "stage_update",
            stage_key="00",
            stage_name="learning",
            label="Blueprint Architect",
            message="체크포인트에 저장된 Blueprint 계층 계약을 재사용합니다. 이미 확정한 작성 전략을 유지하고 중복 LLM 호출을 건너뜁니다.",
        )
    else:
        authoring_blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=evidence_store,
            learning=learning,
            guideline=guideline,
        )
        emit_progress(
            ctx,
            "stage_update",
            stage_key="00",
            stage_name="learning",
            label="Blueprint Architect",
            message="Blueprint Architect가 작성 전 계층 계약을 설계합니다. 액터-유즈케이스-프로세스-기능-세부 기능 구성과 프로세스-정책-정책 항목의 입자도를 먼저 고정합니다.",
        )
        architecture_contract = build_architecture_contract(
            ctx=ctx,
            authoring_blueprint=authoring_blueprint,
            learning=learning,
            evidence_store=evidence_store,
        )
        architecture_contract = enhance_architecture_contract_with_llm(
            ctx=ctx,
            authoring_blueprint=authoring_blueprint,
            learning=learning,
            contract=architecture_contract,
            llm_client=client_for_route(llm_client, "blueprint_architect"),
        )
        authoring_blueprint["architecture_contract"] = architecture_contract
        blueprint_quality = validate_blueprint_quality(authoring_blueprint, learning)
        authoring_blueprint["quality_gate"] = blueprint_quality
    emit_blueprint_quality_progress(ctx, blueprint_quality)
    emit_progress(
        ctx,
        "stage_complete",
        stage_key="00",
        stage_name="learning",
        label="주제 학습",
        score=blueprint_quality.get("score"),
        threshold=blueprint_quality.get("threshold"),
        preview=blueprint_quality_preview(blueprint_quality),
        message=stage_narrative("learning", "complete"),
    )

    min_score = int(getattr(ctx, "inspector_min_score", DEFAULT_INSPECTOR_MIN_SCORE) or DEFAULT_INSPECTOR_MIN_SCORE)
    max_loops = max(1, int(getattr(ctx, "inspector_max_loops", 3) or 3))
    spec = copy.deepcopy(resume_spec) if resume_spec else initialize_spec(ctx, learning, guideline)
    ensure_policy_spec_base_keys(spec)
    record_density_profile(spec, target_spec)
    spec.setdefault("meta", {})["topic_learning"] = learning
    spec.setdefault("meta", {})["chapter_agent_guideline"] = guideline
    spec.setdefault("meta", {})["writer_engine"] = {
        "mode": llm_client.writer_mode,
        "model": llm_client.model,
        "reasoning_effort": llm_client.reasoning_effort,
        "llm_enabled": llm_client.enabled,
        "routing": "role_based",
    }
    spec.setdefault("meta", {})["llm_routing_plan"] = routing_plan(llm_client)
    spec.setdefault("meta", {})["evidence_store"] = evidence_store.summary()
    spec.setdefault("meta", {})["authoring_blueprint"] = compact_blueprint_for_spec(authoring_blueprint)
    spec.setdefault("meta", {})["blueprint_quality_gate"] = blueprint_quality
    if not resume_spec:
        record_blueprint_gaps(spec, authoring_blueprint)
        record_blueprint_quality_findings(spec, blueprint_quality)
    spec.setdefault("meta", {})["inspector_gate"] = {
        "min_score": min_score,
        "max_loops": max_loops,
        "tier_policy": gate_rule_summary(min_score, max_loops),
        "review_mode": getattr(ctx, "review_mode", "auto"),
        "inspection_mode": getattr(ctx, "inspection_mode", "chapter-final"),
        "rule": (
            "chapter-final은 각 챕터 agent 작성 후 inspector가 검수하고 기준 미달 시 동일 agent가 보완한 뒤 최종 Inspector를 실행한다. "
            "final-only는 장별 inspector를 생략하고 전체 작성 완료 후 최종 Inspector만 실행한다. "
            "수동모드는 챕터 완료 HTML을 사용자에게 보여준 뒤 다음 단계 진행 또는 보완 요청을 받아 이어간다."
        ),
    }
    stages = chapter_stages(getattr(ctx, "template_type", ""))
    spec.setdefault("meta", {})["topic_evidence_map"] = build_topic_evidence_map(
        topic=getattr(ctx, "topic", ""),
        spec=spec,
        evidence_store=evidence_store,
        learning=learning,
        stages=[stage.agent.chapter_key for stage in stages],
        per_stage_limit=10,
    )
    emit_progress(
        ctx,
        "stage_update",
        stage_key="00",
        stage_name="learning",
        label="Evidence Map",
        preview=topic_evidence_map_preview(spec["meta"]["topic_evidence_map"]),
        message=stage_narrative("learning", "update"),
    )

    runtime = AgentRuntime(
        ctx=ctx,
        target_spec=target_spec,
        learning=learning,
        guideline=guideline,
        evidence_store=evidence_store,
        authoring_blueprint=authoring_blueprint,
        llm_client=llm_client,
    )

    start_index = resume_start_index(stages, resume_checkpoint)
    repair_start_index = resume_repair_start_index(stages, spec, ctx.business_code, start_index)
    if repair_start_index < start_index:
        repaired_stage = stages[repair_start_index]
        spec.setdefault("meta", {}).setdefault("resume_repairs", []).append(
            {
                "requested_start_index": start_index,
                "repair_start_index": repair_start_index,
                "repair_stage_key": repaired_stage.key,
                "repair_stage_name": repaired_stage.name,
                "reason": "legacy_checkpoint_failed_current_gate",
            }
        )
        emit_progress(
            ctx,
            "stage_update",
            stage_key=repaired_stage.key,
            stage_name=repaired_stage.name,
            label=repaired_stage.agent.display_name,
            message=(
                "체크포인트가 현재 검증 기준과 맞지 않아 이 장부터 다시 작성합니다. "
                "오래된 중간 산출물을 그대로 최종 저장하지 않도록 재검증합니다."
            ),
        )
        start_index = repair_start_index
    if start_index:
        resumed_stage = stages[start_index - 1]
        spec.setdefault("meta", {}).setdefault("resume_runs", []).append(
            {
                "from_stage_key": resumed_stage.key,
                "from_stage_name": resumed_stage.name,
                "next_stage_key": stages[start_index].key if start_index < len(stages) else "finalize",
            }
        )
        emit_progress(
            ctx,
            "stage_complete",
            stage_key=resumed_stage.key,
            stage_name=resumed_stage.name,
            label=resumed_stage.agent.display_name,
            message=f"체크포인트에서 {resumed_stage.agent.display_name} 완료 상태를 복원했습니다.",
        )

    backtrack_counts: dict[str, int] = {}
    for stage in stages[start_index:]:
        stage_min_score = gate_required_score(stage.agent.chapter_key, min_score)
        stage_loops = stage_max_loops(stage.agent.chapter_key, max_loops)
        spec = run_chapter_stage(
            ctx,
            spec,
            runtime,
            stage,
            stage_min_score,
            stage_loops,
            after_stage,
            all_stages=stages,
            backtrack_counts=backtrack_counts,
        )
    return spec


def record_density_profile(spec: dict, target_spec: Mapping[str, object]) -> None:
    profile = target_spec.get("density_profile")
    if not isinstance(profile, Mapping):
        meta = target_spec.get("meta", {})
        profile = meta.get("density_profile") if isinstance(meta, Mapping) else None
    if not isinstance(profile, Mapping):
        return
    profile_payload = dict(profile)
    spec["density_profile"] = profile_payload
    spec.setdefault("meta", {})["density_profile"] = profile_payload


def checkpoint_spec(resume_checkpoint: Mapping[str, object] | None) -> dict | None:
    if not isinstance(resume_checkpoint, Mapping):
        return None
    spec = resume_checkpoint.get("spec")
    if not isinstance(spec, dict):
        return None
    migrated = copy.deepcopy(spec)
    ensure_policy_spec_base_keys(migrated)
    return migrated


def resume_learning(spec: Mapping[str, object]) -> dict | None:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    learning = meta.get("topic_learning", {})
    return copy.deepcopy(learning) if isinstance(learning, dict) and learning else None


def resume_authoring_blueprint(spec: Mapping[str, object]) -> dict | None:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {})
    if not isinstance(blueprint, Mapping) or not blueprint:
        return None
    has_coverage = isinstance(blueprint.get("coverage_matrix"), list) and bool(blueprint.get("coverage_matrix"))
    has_chapters = isinstance(blueprint.get("chapter_blueprints"), list) and bool(blueprint.get("chapter_blueprints"))
    contract = blueprint.get("architecture_contract", {})
    has_contract = isinstance(contract, Mapping) and bool(contract)
    has_first_draft_plan = (
        isinstance(contract, Mapping)
        and isinstance(contract.get("first_draft_quality_plan"), Mapping)
        and bool(contract.get("first_draft_quality_plan", {}).get("stage_checks"))
    )
    if not (has_coverage and has_chapters and has_contract and has_first_draft_plan):
        return None
    return copy.deepcopy(dict(blueprint))


def resume_start_index(stages: Sequence[ChapterStage], resume_checkpoint: Mapping[str, object] | None) -> int:
    if not isinstance(resume_checkpoint, Mapping):
        return 0
    checkpoint = resume_checkpoint.get("checkpoint", {})
    stage_key = ""
    if isinstance(checkpoint, Mapping):
        stage_key = str(checkpoint.get("stage_key", "")).strip()
    if not stage_key:
        stage_key = str(resume_checkpoint.get("stage_key", "")).strip()
    if not stage_key:
        return 0
    for index, stage in enumerate(stages):
        if stage.key == stage_key:
            return min(index + 1, len(stages))
    return 0


def resume_repair_start_index(stages: Sequence[ChapterStage], spec: Mapping[str, object], business_code: str, start_index: int) -> int:
    """Return the earliest completed stage that should be rerun for old checkpoints."""
    if not isinstance(spec, Mapping) or start_index <= 0:
        return start_index
    bounded_start = min(max(start_index, 0), len(stages))
    for index, stage in enumerate(stages[:bounded_start]):
        result = validate_stage_critical(dict(spec), business_code, stage.scope)
        if not result.ok:
            return index
    return start_index


def record_blueprint_gaps(spec: dict, authoring_blueprint: Mapping[str, object]) -> None:
    for gap in authoring_blueprint.get("evidence_gaps", []) or []:
        if not isinstance(gap, Mapping):
            continue
        spec.setdefault("evidence_gaps", []).append(
            {
                "stage": "blueprint",
                "missing_kind": gap.get("kind", ""),
                "reason": f"{gap.get('title', '')}: {gap.get('detail', '')}",
            }
        )


def emit_blueprint_quality_progress(ctx, quality_report: Mapping[str, object]) -> None:
    status = str(quality_report.get("status", "") or "")
    score = quality_report.get("score")
    threshold = quality_report.get("threshold")
    passed = bool(quality_report.get("passed", False))
    message = (
        f"Blueprint Quality Gate 통과: {score}점 / 기준 {threshold}점"
        if passed
        else f"Blueprint Quality Gate에서 보완 위험을 감지했습니다: {score}점 / 기준 {threshold}점"
    )
    emit_progress(
        ctx,
        "stage_update",
        stage_key="00",
        stage_name="learning",
        label="Blueprint Quality Gate",
        score=score,
        threshold=threshold,
        preview=blueprint_quality_preview(quality_report),
        message=f"{message} ({status})",
    )


def blueprint_quality_preview(quality_report: Mapping[str, object]) -> dict:
    findings = quality_report.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    items = [
        f"{item.get('stage', 'blueprint')} · {item.get('title', '')}: {item.get('recommendation', '')}"
        for item in findings[:6]
        if isinstance(item, Mapping)
    ]
    if not items:
        items = ["요구사항, 참고자료, 장별 작성 기준이 본문 작성에 사용할 수 있는 상태입니다."]
    return {
        "title": "Blueprint Quality Gate",
        "items": items,
        "summary": quality_report.get("summary", ""),
    }


def topic_evidence_map_preview(topic_evidence_map: Mapping[str, object]) -> dict:
    stats = topic_evidence_map.get("stats", {}) if isinstance(topic_evidence_map, Mapping) else {}
    stages = topic_evidence_map.get("stages", {}) if isinstance(topic_evidence_map, Mapping) else {}
    if not isinstance(stages, Mapping):
        stages = {}
    items = []
    for stage, stage_map in list(stages.items())[:6]:
        if not isinstance(stage_map, Mapping):
            continue
        source_mix = stage_map.get("source_mix", {}) if isinstance(stage_map.get("source_mix", {}), Mapping) else {}
        mix_label = ", ".join(f"{key} {value}" for key, value in source_mix.items()) or "근거 없음"
        items.append(f"{stage}: {mix_label}")
    if not items:
        items = ["주제와 연결된 근거 카드가 아직 충분히 선별되지 않았습니다."]
    return {
        "title": "Topic Evidence Map",
        "items": items,
        "summary": (
            f"장 {stats.get('stage_count', 0)}개, 근거 {stats.get('evidence_id_count', 0)}개, "
            f"출처 {stats.get('source_count', 0)}개를 장별로 연결했습니다."
        ),
    }


def record_blueprint_quality_findings(spec: dict, quality_report: Mapping[str, object]) -> None:
    findings = quality_report.get("findings", [])
    if not isinstance(findings, list):
        return
    for item in findings:
        if not isinstance(item, Mapping):
            continue
        issue = {
            "chapter": item.get("stage", "blueprint"),
            "stage": item.get("stage", "blueprint"),
            "agent": "Blueprint Quality Gate",
            "risk_flag": not bool(quality_report.get("passed", False)),
            "risk_tier": "Hard" if item.get("severity") == "error" else "Soft",
            "severity": item.get("severity", "warn"),
            "score": quality_report.get("score"),
            "threshold": quality_report.get("threshold"),
            "feedback": [dict(item)],
            "handoff": "blueprint_quality_gate",
        }
        spec.setdefault("meta", {}).setdefault("open_inspector_issues", []).append(issue)
        if item.get("severity") == "error":
            spec.setdefault("meta", {}).setdefault("risk_flags", []).append(
                {
                    "chapter": item.get("stage", "blueprint"),
                    "agent": "Blueprint Quality Gate",
                    "tier": "Hard",
                    "score": quality_report.get("score"),
                    "threshold": quality_report.get("threshold"),
                    "reason": item.get("title", ""),
                }
            )
        if item.get("category") in {"evidence", "traceability", "scope"}:
            spec.setdefault("evidence_gaps", []).append(
                {
                    "stage": item.get("stage", "blueprint"),
                    "missing_kind": item.get("category", ""),
                    "reason": f"{item.get('title', '')}: {item.get('detail', '')}",
                }
            )


def run_chapter_stage(
    ctx,
    spec: dict,
    runtime: AgentRuntime,
    stage: ChapterStage,
    min_score: int,
    max_loops: int,
    after_stage: Callable[[dict, ChapterStage, int], Mapping[str, object] | None] | None,
    *,
    all_stages: Sequence[ChapterStage] = (),
    backtrack_counts: dict[str, int] | None = None,
    allow_backtrack: bool = True,
) -> dict:
    feedback: Sequence[Mapping[str, object]] | None = None
    attempt = 1
    best_spec = None
    best_gate_result = None
    best_feedback = None
    best_score = -1
    stagnant_attempts = 0
    repair_history: list[dict[str, object]] = []
    while True:
        emit_progress(
            ctx,
            "stage_start",
            stage_key=stage.key,
            stage_name=stage.name,
            label=stage.agent.display_name,
            attempt=attempt,
            message=stage_narrative(stage.name, "start", f"{stage.agent.display_name}가 현재까지 작성된 내용을 리뷰하고 담당 챕터를 작성합니다."),
        )
        before_hash = stage_payload_hash(stage, spec)
        candidate_spec = stage.agent.write(spec, runtime, attempt=attempt, feedback=feedback)
        emit_progress(
            ctx,
            "stage_update",
            stage_key=stage.key,
            stage_name=stage.name,
            label=stage.agent.display_name,
            attempt=attempt,
            message=stage_validation_message(ctx, stage.name),
        )

        after_hash = stage_payload_hash(stage, candidate_spec)
        if attempt > 1 and before_hash == after_hash:
            gate_result = unchanged_stage_gate_result(ctx, stage, attempt, feedback, min_score)
        else:
            cache_key = stage_cache_key(stage, candidate_spec, min_score)
            cached_gate = cached_passed_gate_result(candidate_spec, stage, cache_key, min_score)
            if cached_gate:
                gate_result = cached_gate
            else:
                gate_result = after_stage(candidate_spec, stage, attempt) if after_stage else {"passed": True}
                remember_passed_gate_result(candidate_spec, stage, cache_key, gate_result)
        gate_result = gate_result or {"passed": True}
        if gate_tier(stage.agent.chapter_key) == "log-only" and not gate_result.get("passed", True):
            gate_result = dict(gate_result)
            gate_result["passed"] = True
            gate_result["threshold"] = 0
            gate_result["log_only_handoff"] = True
        if gate_result.get("passed", True):
            decision = complete_passed_stage(ctx, stage, attempt, gate_result)
            if manual_revision_requested(decision):
                feedback = manual_review_feedback(decision)
                spec = candidate_spec
                emit_manual_retry(ctx, stage, attempt, gate_result, len(feedback))
                attempt += 1
                continue
            return candidate_spec

        feedback_value = gate_result.get("feedback", [])
        current_feedback = feedback_value if isinstance(feedback_value, list) else []
        current_score = safe_gate_score(gate_result)
        current_fingerprints = feedback_fingerprints(current_feedback)
        previous_fingerprints = (
            set(repair_history[-1].get("feedback_fingerprints", [])) if repair_history else set()
        )
        repeated_fingerprints = sorted(current_fingerprints & previous_fingerprints)
        repair_history.append(
            {
                "attempt": attempt,
                "score": current_score,
                "feedback_fingerprints": sorted(current_fingerprints),
                "repeated_fingerprints": repeated_fingerprints,
            }
        )
        backtracked_spec = maybe_run_upstream_backtrack(
            ctx=ctx,
            spec=candidate_spec,
            runtime=runtime,
            current_stage=stage,
            feedback=current_feedback,
            after_stage=after_stage,
            all_stages=all_stages,
            backtrack_counts=backtrack_counts,
            allow_backtrack=allow_backtrack,
        )
        if backtracked_spec is not None:
            spec = backtracked_spec
            feedback = current_chapter_feedback_after_backtrack(current_feedback)
            attempt += 1
            continue
        if current_score > best_score:
            stagnant_attempts = 0
            best_score = current_score
            best_spec = candidate_spec
            best_gate_result = gate_result
            best_feedback = list(current_feedback)
        else:
            stagnant_attempts += 1
            if current_score < best_score:
                result_message = f"이번 보완 결과가 기존 최고 점수 {best_score}점보다 낮아 최고 후보를 유지합니다."
            else:
                result_message = f"이번 보완 결과가 기존 최고 점수 {best_score}점에서 개선되지 않아 최고 후보를 유지합니다."
            emit_progress(
                ctx,
                "stage_update",
                stage_key=stage.key,
                stage_name=stage.name,
                label=stage.agent.display_name,
                attempt=attempt,
                message=result_message,
            )
        spec = copy.deepcopy(best_spec or candidate_spec)
        controller_event = build_repair_controller_event(
            stage=stage,
            attempt=attempt,
            current_score=current_score,
            best_score=best_score,
            stagnant_attempts=stagnant_attempts,
            repeated_finding_count=len(repeated_fingerprints),
            feedback_count=len(current_feedback),
        )
        feedback = dedupe_feedback(list(best_feedback or current_feedback))
        if controller_event:
            record_repair_controller_event(spec, controller_event)
            controller_feedback = repair_controller_feedback_item(stage, controller_event)
            feedback = dedupe_feedback(list(feedback or []) + [controller_feedback])
            emit_repair_controller_update(ctx, stage, attempt, controller_event)
        emit_gate_retry(ctx, stage, attempt, best_gate_result or gate_result, feedback)
        if should_handoff_stagnant_stage(stage, attempt, max_loops, stagnant_attempts):
            handoff_result = best_gate_result or gate_result
            decision = handoff_failed_stage(
                ctx,
                spec,
                stage,
                attempt,
                min_score,
                max_loops,
                handoff_result,
                feedback,
                handoff_reason="score_stagnated_continue_next_agent",
                handoff_items=[
                    f"점수가 {stagnant_attempts + 1}회 연속 개선되지 않았습니다.",
                    f"최고 점수 {best_score}점 / 기준 {handoff_result.get('threshold', min_score)}점입니다.",
                    "같은 보완을 반복하지 않고 남은 이슈를 후속 장과 Final Inspector로 인계합니다.",
                ],
            )
            if manual_revision_requested(decision):
                feedback = list(feedback or []) + manual_review_feedback(decision)
                emit_manual_retry(ctx, stage, attempt, gate_result, len(feedback), max_loop=True)
                attempt += 1
                continue
            return spec
        if attempt == max_loops:
            handoff_result = best_gate_result or gate_result
            decision = handoff_failed_stage(ctx, spec, stage, attempt, min_score, max_loops, handoff_result, feedback)
            if manual_revision_requested(decision):
                feedback = list(feedback or []) + manual_review_feedback(decision)
                emit_manual_retry(ctx, stage, attempt, gate_result, len(feedback), max_loop=True)
                attempt += 1
                continue
            return spec
        attempt += 1


def should_handoff_stagnant_stage(stage: ChapterStage, attempt: int, max_loops: int, stagnant_attempts: int) -> bool:
    if attempt >= max_loops:
        return False
    if gate_tier(stage.agent.chapter_key) == "log-only":
        return False
    return attempt >= 3 and stagnant_attempts >= 2


def maybe_run_upstream_backtrack(
    *,
    ctx,
    spec: dict,
    runtime: AgentRuntime,
    current_stage: ChapterStage,
    feedback: Sequence[Mapping[str, object]],
    after_stage: Callable[[dict, ChapterStage, int], Mapping[str, object] | None] | None,
    all_stages: Sequence[ChapterStage],
    backtrack_counts: dict[str, int] | None,
    allow_backtrack: bool,
) -> dict | None:
    if not allow_backtrack or not feedback or not all_stages:
        return None
    upstream_chapter = first_upstream_chapter(current_stage, feedback, all_stages)
    if not upstream_chapter:
        return None
    key = f"{current_stage.agent.chapter_key}->{upstream_chapter}"
    counts = backtrack_counts if backtrack_counts is not None else {}
    if counts.get(key, 0) >= 1:
        return None
    upstream_stage = stage_by_chapter(all_stages, upstream_chapter)
    if upstream_stage is None:
        return None
    counts[key] = counts.get(key, 0) + 1
    upstream_feedback = [
        dict(item)
        for item in feedback
        if str(item.get("fix_owner", "")) in {"upstream_chapter", "cross_chapter"}
        and str(item.get("upstream_chapter", "")).strip() == upstream_chapter
    ]
    emit_progress(
        ctx,
        "stage_update",
        stage_key=current_stage.key,
        stage_name=current_stage.name,
        label=current_stage.agent.display_name,
        message=(
            f"Inspector가 {upstream_stage.agent.display_name} 보완 필요성을 감지해 "
            "현재 장 재시도 전에 이전 장을 1회 보완합니다."
        ),
    )
    return run_chapter_stage(
        ctx,
        spec,
        runtime,
        upstream_stage,
        gate_required_score(upstream_stage.agent.chapter_key, DEFAULT_INSPECTOR_MIN_SCORE),
        1,
        after_stage,
        all_stages=all_stages,
        backtrack_counts=counts,
        allow_backtrack=False,
    )


def first_upstream_chapter(
    current_stage: ChapterStage,
    feedback: Sequence[Mapping[str, object]],
    all_stages: Sequence[ChapterStage],
) -> str:
    current_index = stage_index(all_stages, current_stage.agent.chapter_key)
    if current_index < 0:
        return ""
    candidates: list[str] = []
    for item in feedback:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("fix_owner", "")) not in {"upstream_chapter", "cross_chapter"}:
            continue
        upstream = str(item.get("upstream_chapter", "")).strip()
        if not upstream:
            continue
        upstream_index = stage_index(all_stages, upstream)
        if upstream_index < 0 or upstream_index >= current_index:
            continue
        candidates.append(upstream)
    return candidates[0] if candidates else ""


def stage_index(stages: Sequence[ChapterStage], chapter_key: str) -> int:
    for index, stage in enumerate(stages):
        if stage.agent.chapter_key == chapter_key:
            return index
    return -1


def stage_validation_message(ctx, stage_name: str = "") -> str:
    fallback = stage_narrative(stage_name, "validate", "")
    if str(getattr(ctx, "inspection_mode", "chapter-final") or "").strip() == "final-only":
        return (fallback + " 장별 Inspector는 이번 실행에서 생략하고, 최종 Inspector에서 전체 문서를 한 번에 검수합니다.").strip()
    if str(getattr(ctx, "inspection_mode", "chapter-final") or "").strip() == "none":
        return (fallback + " Inspector 없이 JSON Critical Gate만 통과하면 다음 Agent로 넘깁니다.").strip()
    return fallback or "작성 결과를 JSON Critical Gate로 먼저 확인한 뒤 Inspector로 넘깁니다."


def stage_by_chapter(stages: Sequence[ChapterStage], chapter_key: str) -> ChapterStage | None:
    for stage in stages:
        if stage.agent.chapter_key == chapter_key:
            return stage
    return None


def current_chapter_feedback_after_backtrack(feedback: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    current_items = []
    for item in feedback:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("fix_owner", "current_chapter")) in {"upstream_chapter", "cross_chapter"}:
            continue
        current_items.append(dict(item))
    current_items.append(
        {
            "issue_id": "BACKTRACK-REFRESH",
            "priority_tier": "P2",
            "batch_label": "Backtrack refresh / current chapter alignment",
            "must_resolve": "Y",
            "repair_scope": "이번 장",
            "fix_owner": "current_chapter",
            "upstream_chapter": "",
            "failure_type": "upstream_contract_changed",
            "severity": "warning",
            "category": "정합성",
            "title": "이전 장 보완 반영",
            "detail": "Inspector 판단에 따라 이전 장 Agent가 보완됐으므로 현재 장은 갱신된 승인 기준을 다시 이어받아야 합니다.",
            "recommendation": "현재 장의 명칭, 설명, 연결값을 갱신된 이전 장 기준에 맞춰 최소 범위로 보완하세요.",
            "acceptance_check": "현재 장이 갱신된 이전 장의 ID, 명칭, 상태명, 책임 경계를 벗어나지 않아야 합니다.",
        }
    )
    return dedupe_feedback(current_items)


def safe_gate_score(gate_result: Mapping[str, object]) -> int:
    try:
        return int(gate_result.get("score", -1))
    except (TypeError, ValueError):
        return -1


def feedback_fingerprints(feedback: Sequence[Mapping[str, object]] | None) -> set[str]:
    return {feedback_fingerprint(item) for item in feedback or [] if isinstance(item, Mapping)}


def feedback_fingerprint(item: Mapping[str, object]) -> str:
    stable_parts = []
    for key in (
        "target_path",
        "path",
        "section",
        "chapter",
        "fix_owner",
        "upstream_chapter",
        "failure_type",
        "category",
        "title",
    ):
        value = item.get(key)
        if value not in (None, ""):
            stable_parts.append(f"{key}={value}")
    if not stable_parts:
        return feedback_signature(item)
    normalized = " ".join(" ".join(stable_parts).casefold().split())
    return hashlib.sha1(normalized[:500].encode("utf-8")).hexdigest()


def build_repair_controller_event(
    *,
    stage: ChapterStage,
    attempt: int,
    current_score: int,
    best_score: int,
    stagnant_attempts: int,
    repeated_finding_count: int,
    feedback_count: int,
) -> dict[str, object] | None:
    if attempt <= 1:
        return None
    if stagnant_attempts <= 0 and repeated_finding_count <= 0:
        return None
    if current_score < best_score:
        decision = "score_regression_discard_candidate"
        message = "점수가 낮아진 보완 후보를 폐기하고 최고 후보 기준으로 다시 보완합니다."
    elif repeated_finding_count:
        decision = "same_findings_repeated_change_strategy"
        message = "동일 finding이 반복되어 보완 방식을 바꿔야 합니다."
    else:
        decision = "score_stagnation_change_strategy"
        message = "점수가 개선되지 않아 보완 범위와 해결 기준을 다시 좁힙니다."
    return {
        "stage": stage.agent.chapter_key,
        "agent": stage.agent.display_name,
        "attempt": attempt,
        "decision": decision,
        "current_score": current_score,
        "best_score": best_score,
        "stagnant_attempts": stagnant_attempts,
        "repeated_finding_count": repeated_finding_count,
        "feedback_count": feedback_count,
        "message": message,
    }


def repair_controller_feedback_item(
    stage: ChapterStage,
    event: Mapping[str, object],
) -> Mapping[str, object]:
    decision = str(event.get("decision", "score_stagnation_change_strategy"))
    repeated_count = int(event.get("repeated_finding_count", 0) or 0)
    priority = "P1" if decision == "score_regression_discard_candidate" or repeated_count else "P2"
    detail = (
        f"{stage.agent.display_name} 보완 {event.get('attempt')}회차에서 "
        f"최고 점수 {event.get('best_score')}점 대비 현재 점수 {event.get('current_score')}점, "
        f"반복 finding {repeated_count}건이 감지되었습니다."
    )
    return {
        "issue_id": f"REPAIR-CONTROLLER-{stage.agent.chapter_key}-{event.get('attempt')}",
        "priority_tier": priority,
        "batch_label": "Repair Controller / 보완 정체 차단",
        "must_resolve": "Y",
        "repair_scope": "이번 장",
        "fix_owner": "current_chapter",
        "failure_type": decision,
        "severity": "warning",
        "category": "보완 전략",
        "title": "동일 보완 반복 및 점수 회귀 방지",
        "detail": detail,
        "recommendation": (
            "이전 답변의 표현을 반복하지 말고 Inspector finding이 가리키는 JSON 항목의 값, ID 연결, "
            "상태명, 정책명, 설명 중 실제 산출물에 남는 구조를 최소 범위로 변경하세요. "
            "현재 장에서 해결할 수 없는 항목은 fix_owner 또는 upstream_chapter 성격을 명확히 남겨 후속 장에 인계하세요."
        ),
        "acceptance_check": (
            "담당 챕터 JSON hash가 이전 시도와 달라야 하며, 동일 finding의 target_path 또는 판단 기준이 실제로 해소되어야 합니다. "
            "점수가 최고 후보보다 낮아지는 변경은 채택하지 않습니다."
        ),
    }


def record_repair_controller_event(spec: Mapping[str, object], event: Mapping[str, object]) -> None:
    if not isinstance(spec, dict):
        return
    spec.setdefault("meta", {}).setdefault("repair_controller_events", []).append(dict(event))


def emit_repair_controller_update(
    ctx,
    stage: ChapterStage,
    attempt: int,
    event: Mapping[str, object],
) -> None:
    emit_progress(
        ctx,
        "stage_update",
        stage_key=stage.key,
        stage_name=stage.name,
        label=stage.agent.display_name,
        attempt=attempt,
        message=f"Repair Controller가 보완 정체를 감지했습니다. {event.get('message')}",
    )


def stage_payload_hash(stage: ChapterStage, spec: Mapping[str, object]) -> str:
    payload = stage.agent.extract_payload(dict(spec))
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def stage_cache_key(stage: ChapterStage, spec: Mapping[str, object], min_score: int) -> str:
    payload = {
        "cache_version": INSPECTOR_PASS_CACHE_VERSION,
        "scope": stage.scope,
        "chapter": stage.agent.chapter_key,
        "gate_tier": gate_tier(stage.agent.chapter_key),
        "payload_hash": stage_payload_hash(stage, spec),
        "contract_hash": stage_contract_hash(stage, spec),
        "matrix_hash": stage_matrix_hash(stage, spec),
        "min_score": min_score,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def stage_contract_hash(stage: ChapterStage, spec: Mapping[str, object]) -> str:
    keys_by_chapter = {
        "overview": (),
        "terms": ("overview",),
        "actors": ("overview", "terms"),
        "usecases": ("overview", "terms", "actors"),
        "usecase_diagram": ("actors", "usecases"),
        "state": ("terms", "actors", "usecases"),
        "process": ("terms", "actors", "usecases", "states", "state_transitions"),
        "functions": ("usecases", "processes"),
        "process_detail": ("usecases", "processes", "functions", "policy_groups", "policy_details"),
        "function_detail": ("processes", "functions", "policy_groups", "policy_details"),
        "policies": ("terms", "states", "processes", "functions"),
        "terms_refinement": ("terms", "policy_groups", "policy_details"),
        "final_check": (
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
        ),
    }
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    payload = {
        "topic": meta.get("topic", ""),
        "business_code": meta.get("business_code", ""),
        "template_type": meta.get("template_type", ""),
        "chapter": stage.agent.chapter_key,
        "contract": {key: spec.get(key) for key in keys_by_chapter.get(stage.agent.chapter_key, ())},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def stage_matrix_hash(stage: ChapterStage, spec: Mapping[str, object]) -> str:
    try:
        return chain_matrix_fingerprint(spec, stage.agent.chapter_key)
    except Exception:
        return ""


def cached_passed_gate_result(spec: Mapping[str, object], stage: ChapterStage, cache_key: str, min_score: int) -> Mapping[str, object] | None:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    cache = meta.get("inspector_pass_cache", {}) if isinstance(meta.get("inspector_pass_cache"), Mapping) else {}
    cached = cache.get(cache_key)
    if not isinstance(cached, Mapping):
        record_inspector_cache_event(spec, "miss")
        return None
    if cached.get("cache_version") != INSPECTOR_PASS_CACHE_VERSION:
        record_inspector_cache_event(spec, "miss")
        return None
    try:
        cached_threshold = int(cached.get("threshold", 0))
    except (TypeError, ValueError):
        record_inspector_cache_event(spec, "miss")
        return None
    if cached_threshold < min_score:
        record_inspector_cache_event(spec, "miss")
        return None
    record_inspector_cache_event(spec, "hit")
    return {
        "passed": True,
        "score": cached.get("score", 100),
        "threshold": cached.get("threshold", min_score),
        "feedback": [],
        "artifact": None,
        "checkpoint": None,
        "preview": {
            "title": f"{stage.agent.display_name} 검수 캐시 재사용",
            "items": [
                "동일한 JSON 산출물이 이미 Inspector 기준을 통과해 재검수를 생략했습니다.",
                f"Inspector 점수 {cached.get('score', 100)}점 / 기준 {cached.get('threshold', min_score)}점",
            ],
        },
        "gate": "inspector_pass_cache",
        "message": "동일 JSON 통과 이력을 재사용했습니다.",
    }


def remember_passed_gate_result(spec: dict, stage: ChapterStage, cache_key: str, gate_result: Mapping[str, object]) -> None:
    if not gate_result or not gate_result.get("passed", True):
        return
    meta = spec.setdefault("meta", {})
    meta.setdefault("inspector_pass_cache", {})[cache_key] = {
        "cache_version": INSPECTOR_PASS_CACHE_VERSION,
        "stage": stage.scope,
        "chapter": stage.agent.chapter_key,
        "gate_tier": gate_tier(stage.agent.chapter_key),
        "score": gate_result.get("score", 100),
        "threshold": gate_result.get("threshold"),
        "payload_hash": stage_payload_hash(stage, spec),
        "contract_hash": stage_contract_hash(stage, spec),
        "matrix_hash": stage_matrix_hash(stage, spec),
    }
    meta.setdefault("chapter_state", {})[stage.agent.chapter_key] = "passed"


def record_inspector_cache_event(spec: Mapping[str, object], event: str) -> None:
    if not isinstance(spec, dict):
        return
    stats = spec.setdefault("meta", {}).setdefault("inspector_cache_stats", {"hit": 0, "miss": 0})
    if event not in {"hit", "miss"}:
        return
    stats[event] = int(stats.get(event, 0) or 0) + 1
    total = int(stats.get("hit", 0) or 0) + int(stats.get("miss", 0) or 0)
    stats["hit_rate"] = round((int(stats.get("hit", 0) or 0) / total) * 100, 1) if total else 0.0


def unchanged_stage_gate_result(
    ctx,
    stage: ChapterStage,
    attempt: int,
    feedback: Sequence[Mapping[str, object]] | None,
    min_score: int,
) -> Mapping[str, object]:
    issue = {
        "issue_id": "NO-CHANGE",
        "must_resolve": "Y",
        "failure_type": "patch_no_change",
        "severity": "warning",
        "category": "보완 루프",
        "title": "보완 결과 무변경",
        "detail": "Writer가 Inspector 보완 요청을 받은 뒤에도 담당 챕터 JSON을 실제로 변경하지 않았습니다.",
        "recommendation": "기존 항목을 설명만 반복하지 말고, Inspector가 지적한 ID·명칭·설명·연결값 중 하나 이상을 실제로 수정하세요.",
        "acceptance_check": "다음 보완 결과의 담당 챕터 JSON hash가 이전 시도와 달라야 합니다.",
    }
    return {
        "passed": False,
        "score": max(0, min_score - 10),
        "threshold": min_score,
        "feedback": dedupe_feedback(list(feedback or []) + [issue]),
        "artifact": None,
        "preview": {
            "title": f"{stage.agent.display_name} 보완 무변경 감지",
            "items": [
                "담당 챕터 JSON이 이전 시도와 같아 Inspector 재호출을 생략했습니다.",
                "동일 피드백 반복 대신 실제 변경이 필요한 항목만 다시 전달합니다.",
            ],
        },
        "gate": "writer_no_change",
        "message": "보완 결과가 이전 시도와 동일해 Inspector 재검수를 생략했습니다.",
    }


def dedupe_feedback(feedback: Sequence[Mapping[str, object]] | None) -> list[Mapping[str, object]]:
    result: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for item in feedback or []:
        if not isinstance(item, Mapping):
            continue
        key = feedback_signature(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(item))
    return result


def feedback_signature(item: Mapping[str, object]) -> str:
    text = " ".join(
        str(item.get(key, ""))
        for key in ("failure_type", "category", "title", "detail", "recommendation")
        if item.get(key)
    )
    normalized = " ".join(text.casefold().split())
    return hashlib.sha1(normalized[:700].encode("utf-8")).hexdigest()


def complete_passed_stage(ctx, stage: ChapterStage, attempt: int, gate_result: Mapping[str, object]) -> Mapping[str, object]:
    message = (
        f"{stage_narrative(stage.name, 'complete', f'{stage.agent.display_name} 작성이 완료되었습니다.')} 장별 Inspector는 생략하고 최종 Inspector에서 검수합니다."
        if gate_result.get("inspection_skipped")
        else stage_narrative(stage.name, "complete", f"{stage.agent.display_name}가 inspector 기준을 통과했습니다.")
    )
    emit_progress(
        ctx,
        "stage_complete",
        stage_key=stage.key,
        stage_name=stage.name,
        label=stage.agent.display_name,
        attempt=attempt,
        score=gate_result.get("score"),
        threshold=gate_result.get("threshold"),
        artifact=gate_result.get("artifact"),
        preview=gate_result.get("preview"),
        message=message,
    )
    return request_manual_stage_review(ctx, stage, attempt, gate_result)


def emit_gate_retry(
    ctx,
    stage: ChapterStage,
    attempt: int,
    gate_result: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> None:
    emit_progress(
        ctx,
        "stage_retry",
        stage_key=stage.key,
        stage_name=stage.name,
        label=stage.agent.display_name,
        attempt=attempt,
        score=gate_result.get("score"),
        threshold=gate_result.get("threshold"),
        feedback_count=len(feedback),
        artifact=gate_result.get("artifact"),
        preview=gate_result.get("preview"),
        message=gate_result.get("message") or "검수 기준 미달로 보완점을 같은 agent에게 다시 전달합니다.",
    )


def emit_manual_retry(
    ctx,
    stage: ChapterStage,
    attempt: int,
    gate_result: Mapping[str, object],
    feedback_count: int,
    *,
    max_loop: bool = False,
) -> None:
    message = (
        "사용자 보완 요청을 반영해 기준 미달 챕터를 한 번 더 보완합니다."
        if max_loop
        else "사용자 보완 요청을 같은 agent에게 다시 전달합니다."
    )
    emit_progress(
        ctx,
        "stage_retry",
        stage_key=stage.key,
        stage_name=stage.name,
        label=stage.agent.display_name,
        attempt=attempt,
        score=gate_result.get("score"),
        threshold=gate_result.get("threshold"),
        feedback_count=feedback_count,
        artifact=gate_result.get("artifact"),
        preview=gate_result.get("preview"),
        message=message,
    )


def handoff_failed_stage(
    ctx,
    spec: dict,
    stage: ChapterStage,
    attempt: int,
    min_score: int,
    max_loops: int,
    gate_result: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
    *,
    handoff_reason: str = "max_loops_reached_continue_next_agent",
    handoff_items: Sequence[str] | None = None,
) -> Mapping[str, object]:
    score = gate_result.get("score", "N/A")
    threshold = gate_result.get("threshold", min_score)
    preview_items = list(
        handoff_items
        or [
            f"최대 {max_loops}회 보완 후 점수 {score}점 / 기준 {threshold}점입니다.",
            "작업은 중단하지 않고 다음 Agent로 진행합니다.",
            "남은 보완점은 후속 장과 최종 Inspector에서 다시 확인합니다.",
        ]
    )
    emit_progress(
        ctx,
        "stage_complete",
        stage_key=stage.key,
        stage_name=stage.name,
        label=stage.agent.display_name,
        attempt=attempt,
        score=score,
        threshold=threshold,
        artifact=gate_result.get("artifact"),
        preview={
            "title": f"{stage.agent.display_name} 기준 미달 후 다음 단계 진행",
            "items": preview_items,
        },
        message=f"{stage.agent.display_name}가 inspector 기준 미달 상태로 다음 단계에 인계되었습니다.",
    )
    spec.setdefault("meta", {}).setdefault("open_inspector_issues", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "risk_flag": True,
            "risk_tier": gate_tier(stage.agent.chapter_key),
            "attempt": attempt,
            "score": score,
            "threshold": threshold,
            "gate_blocker_count": gate_result.get("gate_blocker_count", 0),
            "feedback": list(feedback or []),
            "handoff": handoff_reason,
        }
    )
    spec.setdefault("meta", {}).setdefault("risk_flags", []).append(
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "tier": gate_tier(stage.agent.chapter_key),
            "score": score,
            "threshold": threshold,
            "reason": handoff_reason,
        }
    )
    return request_manual_stage_review(ctx, stage, attempt, gate_result)
