"""Agent-specific context assembly and traceability helpers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, List, Mapping, Sequence

try:
    from evidence_store import EvidenceStore, analysis_synthesis_alias_text, analysis_synthesis_topic_terms, evidence_authority_score, evidence_source_authority, evidence_source_authority_tier, evidence_source_precedence, stage_profile_terms
    from evidence_map import build_topic_evidence_map, compact_topic_evidence_map_for_stage
    from pi_agent import pi_context_for_stage
    from policy_style_anchor import policy_style_anchor_context, policy_style_anchor_questions
    from policy_graph import graph_context_for_spec
except ImportError:  # pragma: no cover - package import fallback.
    from .evidence_store import EvidenceStore, analysis_synthesis_alias_text, analysis_synthesis_topic_terms, evidence_authority_score, evidence_source_authority, evidence_source_authority_tier, evidence_source_precedence, stage_profile_terms
    from .evidence_map import build_topic_evidence_map, compact_topic_evidence_map_for_stage
    from .pi_agent import pi_context_for_stage
    from .policy_style_anchor import policy_style_anchor_context, policy_style_anchor_questions
    from .policy_graph import graph_context_for_spec


CONTEXT_PROFILES = {
    "overview": {
        "objective": "업무 범위, 제외 범위, 대상 채널·고객, 후속 상세화 영역을 근거 기반으로 고정한다.",
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "quality_gate": "포함/제외 범위가 명확하고 후속 장에서 상세화할 판단축이 분리되어야 한다.",
    },
    "terms": {
        "objective": "정책 판단에 필요한 상태, 권한, 인증, 상품·혜택, 데이터 보관 용어를 표준화한다.",
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "quality_gate": "일반 명사는 제외하고 후속 장에서 실제로 쓰일 기준 용어만 남긴다.",
    },
    "terms_refinement": {
        "objective": "기능과 정책까지 작성된 전체 문서를 기준으로 누락된 상태·권한·제한·예외·고지·이력 용어를 보강한다.",
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "quality_gate": "프로세스·기능·정책에서 실제로 쓰인 판단 용어가 주요 용어에 반영되어야 한다.",
    },
    "actors": {
        "objective": "독립 책임 주체를 정의하고 고객 상태·권한 조건, 세부 내부 운영 역할, 세부 시스템은 액터로 분리하지 않는다.",
        "required_kinds": ("requirement", "strategy", "guideline"),
        "quality_gate": "액터는 유즈케이스 시작 또는 결과 생성 책임이 있는 주체여야 하며, 내부 운영 역할은 운영자, 세부 시스템은 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합되어야 한다.",
    },
    "usecases": {
        "objective": "액터별 고객 과업, 운영 과업, 시스템 보조 처리를 뒤에서 프로세스로 분해 가능한 완료 목적 단위로 정의한다.",
        "required_kinds": ("requirement", "strategy", "voc", "research", "guideline"),
        "quality_gate": "모든 액터가 유즈케이스에 연결되고 사람 액터는 process_target=Y이며, 절차·기능 수준 행위가 독립 유즈케이스로 올라오지 않아야 한다.",
    },
    "usecase_diagram": {
        "objective": "액터와 유즈케이스 관계를 한눈에 확인할 수 있는 텍스트 도식으로 정리한다.",
        "required_kinds": ("guideline", "sample"),
        "quality_gate": "모든 유즈케이스가 다이어그램에 등장하고 UI 이동 단계는 제외한다.",
    },
    "state": {
        "objective": "액터와 유즈케이스 관계를 기준으로 업무 가능 여부, 제한, 예외, 운영 확인, 완료 기준을 상태와 전이로 정의한다.",
        "required_kinds": ("requirement", "strategy", "voc", "guideline"),
        "quality_gate": "상태 전이표의 현재/다음 상태는 상태 목록의 명칭과 일치하고, 전이 이벤트는 상태를 바꾸는 업무 사건이며 추적성은 usecase_ids로 확인되어야 한다.",
    },
    "process": {
        "objective": "상위 유즈케이스를 시작, 판단, 입력/선택, 인증/동의, 처리 요청, 결과 안내 같은 업무 절차로 분해한다.",
        "required_kinds": ("requirement", "voc", "ia", "strategy", "guideline"),
        "quality_gate": "process_target=Y 유즈케이스마다 시작·판단·완료·예외 흐름이 있어야 하며, 프로세스가 기능명 나열로 축소되거나 한 유즈케이스에 과도하게 집중되면 안 된다.",
    },
    "functions": {
        "objective": "프로세스를 수행하는 데 필요한 조회, 검증, 산정, 저장, 알림, 연동 기능을 정의한다.",
        "required_kinds": ("requirement", "ia", "strategy", "guideline"),
        "quality_gate": "각 기능은 process_id/process_ids를 가져야 하며, 프로세스 1:1 복사가 아니라 처리 역량 단위로 묶여야 한다.",
    },
    "process_detail": {
        "objective": "Full 버전에서 프로세스별 진입 조건, 종료 조건, 선행·후행 관계, 기능·정책 연결을 상세화한다.",
        "required_kinds": ("requirement", "strategy", "ia", "guideline", "sample"),
        "quality_gate": "모든 프로세스는 진입/종료 조건과 실제 관련 기능·정책 연결을 가지며, 기능 상세나 정책값을 새로 만들지 않아야 한다.",
    },
    "function_detail": {
        "objective": "Full 버전에서 기능별 입력, 처리 로직, 출력, 실패·예외 케이스, 관련 정책을 상세화한다.",
        "required_kinds": ("requirement", "strategy", "ia", "guideline", "sample"),
        "quality_gate": "모든 기능은 입력·처리·출력·예외·관련 정책이 비어 있지 않고, sub_functions는 기능 하위 처리 구성이어야 한다.",
    },
    "policies": {
        "objective": "프로세스와 기능에 필요한 정책을 먼저 정의하고, 정책별 세부 항목과 항목별 기능 동작값, 조건, 허용/제한, 횟수, 시간, 채널, 예외, 고지, 이력 저장 기준을 정의한다.",
        "required_kinds": ("requirement", "voc", "strategy", "guideline"),
        "quality_gate": "정책 상세는 policy_id로 정책 그룹에 연결하고, 작성 후 프로세스 related_policies는 정책 목록의 정책 ID와 정책명으로 업데이트되어야 한다.",
    },
    "final_check": {
        "objective": "범위, 요구사항, 유즈케이스-프로세스-기능-세부 기능-정책 연결성과 근거 부족 지점을 최종 확인한다.",
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "quality_gate": "최종 검수자는 계층 입자도, 연결 끊김, 정책 구체성, Evidence Gap을 확인할 수 있어야 한다.",
    },
}


STAGE_POLICY_QUESTIONS = {
    "overview": (
        "이 정책서가 해결해야 하는 고객 과업과 업무 문제는 무엇인가?",
        "이번 정책서에 포함할 범위와 후속 산출물로 넘길 범위는 어디서 갈리는가?",
        "채널과 BSS/연계 시스템의 책임 경계는 어떻게 나뉘는가?",
    ),
    "terms": (
        "후속 정책 판단에 반복 사용될 상태·권한·인증·동의·제한 용어는 무엇인가?",
        "고객 상태와 액터를 혼동하지 않으려면 어떤 용어를 분리해야 하는가?",
        "유사 용어 사이의 업무상 판단 차이는 무엇인가?",
    ),
    "terms_refinement": (
        "기능·정책 작성 후 새로 등장한 상태·제한·예외·고지·이력 용어가 있는가?",
        "정책 상세에서 쓰였지만 주요 용어에 없는 판단 기준 용어가 있는가?",
    ),
    "actors": (
        "누가 유즈케이스를 직접 시작하거나 결과를 생성하는 책임 주체인가?",
        "고객 상태나 권한 조건을 액터로 잘못 분리하고 있지 않은가?",
        "세부 내부 운영 역할을 운영자로 통합하고 역할 차이를 기능·정책으로 내렸는가?",
        "세부 엔진·저장소·알림·업무 시스템을 통합 시스템 액터로 묶었는가?",
        "BSS·외부기관·연계 시스템은 독립 책임이 있는가, 통합 액터로 충분한가?",
    ),
    "usecases": (
        "고객 또는 운영자가 완료해야 하는 상위 업무 목적은 무엇인가?",
        "사람 액터 유즈케이스와 시스템 보조 유즈케이스가 구분되어 있는가?",
        "각 유즈케이스의 시작 목적과 완료 상태는 무엇인가?",
    ),
    "usecase_diagram": (
        "모든 액터와 유즈케이스 관계가 누락 없이 표현되는가?",
        "include 관계가 반복 공통 처리에만 사용되는가?",
    ),
    "state": (
        "액터-유즈케이스 관계에서 어떤 상태 후보가 도출되는가?",
        "전이 이벤트가 상태를 실제로 바꾸는 업무 사건이고 승인된 유즈케이스 ID로 추적되는가?",
        "정상·예외·제한·보류·복구 흐름의 현재/다음 상태가 모두 상태 목록에 있는가?",
    ),
    "process": (
        "process_target=Y 유즈케이스가 어떤 업무 절차로 완료되는가?",
        "고객 시작점, 조건 판단, 요청, BSS/연계 반영, 결과 안내가 어디에 배치되는가?",
        "각 프로세스는 어떤 기능과 정책으로 이어지는가?",
    ),
    "process_detail": (
        "각 프로세스의 진입 조건, 종료 조건, 선행/후행 관계는 무엇인가?",
        "프로세스 상세가 기능 상세나 정책값을 대신 쓰고 있지 않은가?",
    ),
    "functions": (
        "각 프로세스를 실행하는 처리 역량은 조회·검증·산정·저장·알림·연동 중 무엇인가?",
        "기능이 프로세스명을 1:1 복사하지 않고 업무 완결 처리 단위로 묶였는가?",
        "세부 기능 구성은 개발자가 하위 처리로 이해할 수 있을 만큼 구체적인가?",
    ),
    "function_detail": (
        "각 기능의 입력·처리·출력·예외·관련 정책이 개발/QA 관점에서 이어지는가?",
        "기능 상세가 화면 단계나 API/DB 필드 상세로 흘러가지 않는가?",
    ),
    "policies": (
        "프로세스와 기능이 동작하려면 어떤 판단값·조건·제한·예외가 필요한가?",
        "누가 할 수 있고, 언제 할 수 있고, 몇 번까지 가능하며, 실패하면 어떻게 복구하는가?",
        "이력은 어디에 남고, BSS/연계 시스템은 어떤 상태나 원장을 변경하는가?",
    ),
    "final_check": (
        "액터-유즈케이스-상태-프로세스-기능-정책 연결이 끊기지 않았는가?",
        "정책 항목이 실제 판단 기준으로 작성되어 개발/QA가 테스트 가능한가?",
        "근거가 약한 확정값이나 공개웹 일반론이 첨부자료보다 앞서지 않았는가?",
    ),
}


STAGE_REQUIRED_OUTPUTS = {
    "overview": ("범위", "제외 범위", "설계 원칙", "후속 상세화 영역"),
    "terms": ("정책 판단 용어", "상태/권한/인증/동의 용어", "업무상 판단 기준"),
    "terms_refinement": ("누락 판단 용어", "기능·정책 기반 보강 용어"),
    "actors": ("독립 책임 액터", "액터별 책임", "액터 제외 기준 반영"),
    "usecases": ("액터별 유즈케이스", "process_target", "완료 상태"),
    "usecase_diagram": ("액터-유즈케이스 관계", "필요한 include 관계"),
    "state": ("상태 목록", "상태 전이표", "업무 사건 전이 이벤트", "usecase_ids 추적성"),
    "process": ("프로세스 목록", "관련 기능 후보", "관련 정책 후보", "예외 흐름"),
    "process_detail": ("진입/종료 조건", "선행/후행 관계", "기능·정책 연결"),
    "functions": ("기능 목록", "세부 기능 구성", "process_id 연결"),
    "function_detail": ("입력", "처리", "출력", "예외", "관련 정책"),
    "policies": ("정책 그룹", "정책 항목", "항목별 판단값/조건/제한/예외/고지/이력"),
    "final_check": ("요구사항 커버리지", "계층 연결성", "정책 구체성", "Evidence Gap"),
}


STAGE_MUST_DECIDE = {
    "overview": ("대상 고객", "대상 채널", "포함/제외 범위", "BSS 책임 경계"),
    "actors": ("사람 액터", "시스템 액터", "액터 제외 대상"),
    "usecases": ("상위 고객 과업", "보조 시스템 유즈케이스", "process_target=Y/N"),
    "state": ("상태 후보", "전이 이벤트", "복구/제한/보류 기준"),
    "process": ("유즈케이스별 절차 분해", "조건 판단 지점", "기능·정책 연결"),
    "functions": ("처리 역량 단위", "세부 기능 구성", "프로세스 연결"),
    "policies": ("허용/제한 조건", "횟수/시간/상태 기준", "예외/고지/이력/BSS 반영 기준"),
    "final_check": ("누락 요구사항", "연결 끊김", "일반론 정책", "근거 충돌"),
}


def assemble_context_pack(
    *,
    agent_key: str,
    spec: Mapping[str, object],
    evidence_store: EvidenceStore,
    topic: str,
    learning: Mapping[str, object],
    limit: int = 14,
) -> dict:
    profile = CONTEXT_PROFILES.get(agent_key, CONTEXT_PROFILES["overview"])
    topic_map = topic_evidence_map_for_spec(
        topic=topic,
        spec=spec,
        evidence_store=evidence_store,
        learning=learning,
        agent_key=agent_key,
        limit=limit,
    )
    stage_evidence_map = compact_topic_evidence_map_for_stage(topic_map, agent_key, max_cards=min(6, limit))
    query_terms = collect_query_terms(agent_key, spec, learning)
    selected = evidence_store.select(
        stage=agent_key,
        topic=topic,
        query_terms=query_terms,
        required_kinds=profile["required_kinds"],
        limit=limit,
    )
    selected = prioritize_stage_requirement_evidence(selected, evidence_store, spec, agent_key, limit)
    selected = merge_global_channel_strategy_evidence(selected, evidence_store, agent_key, limit)
    selected = merge_analysis_synthesis_evidence(selected, evidence_store, agent_key, topic, limit)
    selected = refine_context_pack_evidence(selected, agent_key, limit)
    selected = ensure_required_kind_coverage(
        selected,
        evidence_store=evidence_store,
        required_kinds=profile["required_kinds"],
        agent_key=agent_key,
        query_terms=query_terms,
        limit=limit,
    )
    stage_digest = build_stage_evidence_digest(agent_key, selected, learning)
    evidence_groups = grouped_evidence_ids(selected, profile["required_kinds"])
    present_kinds = {item.kind for item in selected}
    gaps = [
        {
            "stage": agent_key,
            "missing_kind": kind,
            "reason": f"{agent_key} 작성에 필요한 {kind} 근거가 Context Pack에 충분히 선별되지 않았습니다.",
        }
        for kind in profile["required_kinds"]
        if kind not in present_kinds
    ]
    if isinstance(stage_evidence_map, Mapping):
        gaps.extend(gap for gap in stage_evidence_map.get("evidence_gaps", []) or [] if isinstance(gap, Mapping))
    gaps = dedupe_gaps(gaps)
    context_quality = score_context_pack(
        profile=profile,
        selected=selected,
        gaps=gaps,
        stage_evidence_map=stage_evidence_map,
        limit=limit,
    )
    policy_graph_context = graph_context_for_spec(
        spec,
        stage=agent_key,
        topic=topic,
        limit=min(18, max(8, limit)),
    )
    return {
        "stage": agent_key,
        "objective": profile["objective"],
        "quality_gate": profile["quality_gate"],
        "required_evidence_kinds": list(profile["required_kinds"]),
        "policy_questions": stage_policy_questions(agent_key, spec, learning),
        "required_outputs": stage_required_outputs(agent_key),
        "must_decide": stage_must_decide(agent_key, spec, learning),
        "policy_detail_style_anchor": policy_style_anchor_context(agent_key),
        "pi_agent_context": pi_context_for_stage(agent_key),
        "selection_strategy": {
            "rule": "장별 query template, 필수 근거 종류, 목표 요구사항, 키워드/태그 앵커, 벡터 유사도 보조 점수, 중복 제거, 동일 출처 과다 선택 방지를 순서대로 적용한다.",
            "rag_role": "Evidence Store에서 현재 장과 관련된 요구사항·참고자료·샘플 근거를 검색해 selected_evidence로 제공한다.",
            "cag_role": "Topic Learning, Authoring Blueprint, Approved Contract는 장별 Agent가 공유하는 캐시/계약 기준으로 사용한다.",
            "source_authority": "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다. 하위 근거가 상위 근거와 상충하면 상위 근거를 따른다.",
            "authority_score": "Context Pack은 authority_score를 함께 제공하며, 같은 관련도에서는 높은 점수의 첨부 근거를 먼저 따른다.",
            "vector_guard": "벡터 유사도는 주제·키워드 앵커가 있는 후보에만 크게 반영하고, 앵커가 약한 후보는 가점 상한을 둔다.",
            "dedupe": "동일 요구사항은 유지하고, 참고자료 chunk는 출처·제목·요약 fingerprint가 같은 경우 1건만 유지한다.",
            "quality_guard": "필수 kind가 빠지면 evidence_gaps에 남기고, 근거가 부족한 확정값은 쓰지 않는다.",
        },
        "knowledge_mode": {
            "rag": {
                "source": "Evidence Store",
                "purpose": "현재 장 작성에 필요한 원천 근거 선별",
                "output": "selected_evidence, topic_evidence_map, evidence_digest",
            },
            "cag": {
                "source": "Topic Learning + Authoring Blueprint + Approved Contract",
                "purpose": "Agent 간 해석 일관성과 앞 장 기준 유지",
                "output": "chapter blueprint, hierarchy contract, traceability baseline",
            },
        },
        "prelearned_knowledge": compact_prelearned_knowledge(learning.get("prelearned_knowledge", {}) if isinstance(learning, Mapping) else {}),
        "query_terms": query_terms[:16],
        "selected_evidence_ids": [item.id for item in selected],
        "essential_evidence_ids": evidence_groups["essential"],
        "supplemental_evidence_ids": evidence_groups["supplemental"],
        "topic_evidence_map": stage_evidence_map,
        "evidence_digest": stage_digest,
        "channel_integration_context": channel_integration_context(selected),
        "policy_graph_context": policy_graph_context,
        "selected_evidence": [compact_evidence_for_prompt(item) for item in selected[: min(6, limit)]],
        "selected_source_count": len({item.source for item in selected}),
        "context_quality": context_quality,
        "evidence_gaps": gaps,
    }


def compact_prelearned_knowledge(value: object) -> dict:
    if not isinstance(value, Mapping) or not value:
        return {}
    return {
        "version": value.get("version", ""),
        "source_authority_rule": value.get("source_authority_rule", {}),
        "candidate_usage_policy": value.get("candidate_usage_policy", {}),
        "topic_direction_milestone": value.get("topic_direction_milestone", []),
        "topic_direction_strategy": value.get("topic_direction_strategy", []),
        "topic_direction_agent_guidance": value.get("topic_direction_agent_guidance", []),
        "tk_core_orientations": value.get("tk_core_orientations", []),
        "tk_process_function_guidance": value.get("tk_process_function_guidance", []),
        "topic_axes": value.get("topic_axes", {}),
        "chapter_guidance": value.get("chapter_guidance", {}),
        "candidate_inventory": value.get("candidate_inventory", {}),
        "evidence_gaps": value.get("evidence_gaps", []),
    }


def stage_policy_questions(agent_key: str, spec: Mapping[str, object], learning: Mapping[str, object]) -> List[str]:
    """Return compact decision questions that turn evidence into authoring intent."""
    questions: List[object] = list(STAGE_POLICY_QUESTIONS.get(agent_key, ()))
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    strategy = blueprint.get("document_strategy", {}) if isinstance(blueprint.get("document_strategy"), Mapping) else {}
    questions.extend(strategy.get("core_policy_questions", []) if isinstance(strategy.get("core_policy_questions"), list) else [])
    questions.extend(core_design_policy_questions(spec, agent_key))
    questions.extend(policy_style_anchor_questions(agent_key))
    if agent_key in {"policies", "final_check"}:
        questions.extend(learning.get("policy_risks", []) if isinstance(learning.get("policy_risks"), list) else [])
    return [limit_text(value, 120) for value in unique_texts(questions)[:10]]


def stage_required_outputs(agent_key: str) -> List[str]:
    return list(STAGE_REQUIRED_OUTPUTS.get(agent_key, ("담당 장 JSON", "상위/하위 계층 연결")))


def stage_must_decide(agent_key: str, spec: Mapping[str, object], learning: Mapping[str, object]) -> List[str]:
    decisions: List[object] = list(STAGE_MUST_DECIDE.get(agent_key, ()))
    decisions.extend(core_design_must_decide(spec, agent_key))
    if agent_key in {"process", "functions", "policies", "final_check"}:
        decisions.extend(learning.get("bss_implications", []) if isinstance(learning.get("bss_implications"), list) else [])
    return [limit_text(value, 120) for value in unique_texts(decisions)[:12]]


def core_design_policy_questions(spec: Mapping[str, object], agent_key: str) -> List[str]:
    core_design = authoring_core_design_map(spec)
    fallback = core_design.get("fallback_axes", {}) if isinstance(core_design.get("fallback_axes"), Mapping) else {}
    questions = list(fallback.get("policy_questions", []) if isinstance(fallback.get("policy_questions"), list) else [])
    if agent_key not in {"process", "functions", "policies", "final_check"}:
        return questions[:4]
    for row in core_design.get("design_rows", []) if isinstance(core_design.get("design_rows"), list) else []:
        if not isinstance(row, Mapping):
            continue
        usecase = str(row.get("usecase", "") or "").strip()
        process = str(row.get("process", "") or "").strip()
        axes = [str(axis).strip() for axis in row.get("policy_item_axes", []) if str(axis).strip()] if isinstance(row.get("policy_item_axes"), list) else []
        if usecase and process:
            questions.append(f"{usecase}를 {process}로 완료하려면 어떤 정책 판단 기준이 필요한가?")
        questions.extend(axes)
    return questions


def core_design_must_decide(spec: Mapping[str, object], agent_key: str) -> List[str]:
    core_design = authoring_core_design_map(spec)
    if not core_design:
        return []
    rows = core_design.get("design_rows", []) if isinstance(core_design.get("design_rows"), list) else []
    decisions: List[str] = []
    for row in rows[:10]:
        if not isinstance(row, Mapping):
            continue
        if agent_key == "usecases" and row.get("usecase"):
            decisions.append(f"{row.get('requirement_id', '')}: 유즈케이스 후보 {row.get('usecase')}")
        elif agent_key == "state" and row.get("state_candidates"):
            decisions.append(f"{row.get('requirement_id', '')}: 상태 후보 {', '.join(str(v) for v in row.get('state_candidates', [])[:4])}")
        elif agent_key == "process" and row.get("process"):
            decisions.append(f"{row.get('requirement_id', '')}: 프로세스 후보 {row.get('process')}")
        elif agent_key == "functions" and row.get("functions"):
            decisions.append(f"{row.get('requirement_id', '')}: 기능 후보 {', '.join(str(v) for v in row.get('functions', [])[:4])}")
        elif agent_key == "policies" and (row.get("policy_candidates") or row.get("policy_item_axes")):
            axes = row.get("policy_item_axes", []) if isinstance(row.get("policy_item_axes"), list) else []
            decisions.append(f"{row.get('requirement_id', '')}: 정책 항목 축 {', '.join(str(v) for v in axes[:4])}")
    return decisions


def authoring_core_design_map(spec: Mapping[str, object]) -> dict:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    contract = blueprint.get("architecture_contract", {}) if isinstance(blueprint.get("architecture_contract"), Mapping) else {}
    core_design = contract.get("core_design_map", {}) if isinstance(contract.get("core_design_map"), Mapping) else {}
    return dict(core_design) if core_design else {}


def score_context_pack(
    *,
    profile: Mapping[str, object],
    selected: Sequence[object],
    gaps: Sequence[Mapping[str, object]],
    stage_evidence_map: Mapping[str, object] | object,
    limit: int,
) -> dict:
    """Score whether a chapter received enough grounded context.

    This is not a quality score for the generated chapter. It is a cheap
    observability signal that tells us whether Writer/Inspector failures may be
    caused by weak evidence selection before spending more LLM tokens.
    """
    required_kinds = [str(kind) for kind in profile.get("required_kinds", []) or [] if str(kind).strip()]
    present_kinds = {str(getattr(item, "kind", "") or "") for item in selected}
    missing_kinds = [kind for kind in required_kinds if kind not in present_kinds]
    required_coverage = (
        round((len(required_kinds) - len(missing_kinds)) / len(required_kinds), 3)
        if required_kinds
        else 1.0
    )
    authority_scores = [evidence_authority_score(item) for item in selected]
    average_authority = round(sum(authority_scores) / len(authority_scores), 1) if authority_scores else 0.0
    source_mix = (
        stage_evidence_map.get("source_mix", {})
        if isinstance(stage_evidence_map, Mapping) and isinstance(stage_evidence_map.get("source_mix", {}), Mapping)
        else {}
    )
    gap_count = len(gaps)
    selected_count = len(selected)
    warnings: List[str] = []
    score = 100

    if selected_count == 0:
        score = 0
        warnings.append("selected_evidence가 없습니다.")
    elif selected_count < min(3, max(1, limit)):
        score -= 12
        warnings.append("선별된 evidence 수가 적어 장 작성 근거가 약할 수 있습니다.")

    if missing_kinds:
        score -= min(45, len(missing_kinds) * 15)
        warnings.append("필수 evidence kind가 누락되었습니다: " + ", ".join(missing_kinds))

    if gap_count:
        score -= min(30, gap_count * 6)
        warnings.append(f"evidence_gap {gap_count}건이 남아 있습니다.")

    if "requirement" in required_kinds and "requirement" not in present_kinds:
        score -= 15
        warnings.append("요구사항 근거 없이 장이 작성될 수 있습니다.")

    if selected_count and average_authority < 55:
        score -= 8
        warnings.append("선별 근거의 평균 권위 점수가 낮습니다.")

    primary_count = sum(
        1
        for item in selected
        if evidence_source_authority_tier(item) == 1
    )
    auxiliary_count = sum(
        1
        for item in selected
        if evidence_source_authority_tier(item) > 1
    )
    if auxiliary_count and primary_count == 0:
        score -= 20
        warnings.append("2~4순위 보조/참고 근거만 있고 1순위 첨부/사내/요구사항 근거가 없습니다.")

    score = max(0, min(100, score))
    if score >= 85:
        status = "good"
    elif score >= 70:
        status = "watch"
    else:
        status = "risk"
    return {
        "score": score,
        "status": status,
        "required_kind_coverage": required_coverage,
        "missing_required_kinds": missing_kinds,
        "selected_count": selected_count,
        "selected_source_count": len({str(getattr(item, "source", "") or "") for item in selected}),
        "average_authority_score": average_authority,
        "primary_evidence_count": primary_count,
        "auxiliary_evidence_count": auxiliary_count,
        "attached_evidence_count": primary_count,
        "web_auxiliary_count": auxiliary_count,
        "evidence_gap_count": gap_count,
        "source_mix": dict(source_mix),
        "warnings": warnings[:6],
    }


def merge_global_channel_strategy_evidence(
    selected: Sequence[object],
    evidence_store: EvidenceStore,
    agent_key: str,
    limit: int,
) -> List[object]:
    """Ensure the NC channel integration knowledge reaches core writing agents."""
    if agent_key not in {"overview", "terms", "actors", "usecases", "state", "process", "functions", "policies", "process_detail", "function_detail", "terms_refinement", "final_check"}:
        return list(selected)
    if any(is_global_channel_strategy_item(item) for item in selected):
        return list(selected)
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if is_global_channel_strategy_item(item)
    ]
    if not candidates:
        return list(selected)
    candidates.sort(key=global_channel_strategy_rank, reverse=True)
    selected_ids = {str(getattr(item, "id", "") or "") for item in selected}
    addition = next((item for item in candidates if str(getattr(item, "id", "") or "") not in selected_ids), None)
    if addition is None:
        return list(selected)
    requirements = [item for item in selected if str(getattr(item, "kind", "") or "") == "requirement"]
    others = [item for item in selected if str(getattr(item, "kind", "") or "") != "requirement"]
    requirement_prefix_count = min(len(requirements), max(1, limit // 2))
    merged = requirements[:requirement_prefix_count] + [addition] + requirements[requirement_prefix_count:] + others
    deduped: List[object] = []
    seen: set[str] = set()
    for item in merged:
        evidence_id = str(getattr(item, "id", "") or "")
        if not evidence_id or evidence_id in seen:
            continue
        deduped.append(item)
        seen.add(evidence_id)
        if len(deduped) >= limit:
            break
    return deduped


def is_global_channel_strategy_item(item: object) -> bool:
    if str(getattr(item, "kind", "") or "") != "strategy":
        return False
    text = " ".join(
        str(value or "")
        for value in (
            getattr(item, "source", ""),
            getattr(item, "title", ""),
            getattr(item, "summary", ""),
            " ".join(str(signal) for signal in getattr(item, "signals", ()) or ()),
            " ".join(str(evidence) for evidence in getattr(item, "evidence", ()) or ()),
        )
    )
    return any(keyword in text for keyword in ("채널 방향성", "T월드", "T멤버십", "T다이렉트샵", "T우주", "통합지식"))


def global_channel_strategy_rank(item: object) -> tuple[int, int, int]:
    tags = tuple(getattr(item, "tags", ()) or ())
    is_chunk = "source_chunk" in tags
    text = " ".join(str(value or "") for value in (getattr(item, "source", ""), getattr(item, "summary", "")))
    channel_hits = sum(1 for keyword in ("T월드", "T멤버십", "T다이렉트샵", "T우주") if keyword in text)
    return (
        int(getattr(item, "score", 0) or 0),
        channel_hits,
        0 if is_chunk else 1,
    )


def channel_integration_context(selected: Sequence[object]) -> dict:
    channel_items = [item for item in selected if is_global_channel_strategy_item(item)]
    if not channel_items:
        return {}
    return {
        "rule": "T월드·T멤버십·T다이렉트샵·T우주 지식은 통합채널의 공통 책임 경계와 정책 판단축으로 사용한다. 단, 현재 주제 밖 업무를 본문 범위로 확장하지 않는다.",
        "channel_axes": [
            "T월드: 회선, 요금, 납부, 가입 상품, BSS 판정, 고객 권한.",
            "T멤버십: 등급, 혜택, 쿠폰, 바코드, 사용 조건, 중복 사용 제한.",
            "T다이렉트샵: 상품 선택, 주문, 가입, 배송, 개통, USIM/eSIM, 단말/렌탈 상태.",
            "T우주: 구독, 정기결제, 쿠폰/이용권, 제휴 판매 책임, 해지/환불.",
        ],
        "evidence_ids": [str(getattr(item, "id", "") or "") for item in channel_items[:4]],
        "sources": unique_texts(str(getattr(item, "source", "") or "") for item in channel_items)[:3],
        "signals": unique_texts(
            signal
            for item in channel_items
            for signal in (getattr(item, "signals", ()) or ())
        )[:6],
    }


def merge_analysis_synthesis_evidence(
    selected: Sequence[object],
    evidence_store: EvidenceStore,
    agent_key: str,
    topic: str,
    limit: int,
) -> List[object]:
    """Keep one completed 현황 분석 synthesis card in core writing prompts."""
    if agent_key not in {"overview", "usecases", "state", "process", "functions", "policies", "process_detail", "function_detail", "final_check"}:
        return list(selected)
    if any(str(getattr(item, "kind", "") or "") == "analysis_synthesis" for item in selected):
        return list(selected)
    selected_ids = {str(getattr(item, "id", "") or "") for item in selected}
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if str(getattr(item, "kind", "") or "") == "analysis_synthesis"
        and str(getattr(item, "id", "") or "") not in selected_ids
    ]
    if not candidates:
        return list(selected)
    candidates.sort(key=lambda item: analysis_synthesis_rank(item, topic), reverse=True)
    addition = candidates[0]
    requirements = [item for item in selected if str(getattr(item, "kind", "") or "") == "requirement"]
    others = [item for item in selected if str(getattr(item, "kind", "") or "") != "requirement"]
    requirement_prefix_count = min(len(requirements), max(1, limit // 2))
    merged = requirements[:requirement_prefix_count] + [addition] + requirements[requirement_prefix_count:] + others
    deduped: List[object] = []
    seen: set[str] = set()
    for item in merged:
        evidence_id = str(getattr(item, "id", "") or "")
        if not evidence_id or evidence_id in seen:
            continue
        deduped.append(item)
        seen.add(evidence_id)
        if len(deduped) >= limit:
            break
    return deduped


def analysis_synthesis_rank(item: object, topic: str) -> tuple[int, int, int, str]:
    alias_text = analysis_synthesis_alias_text(getattr(item, "source", ""))
    text = " ".join(
        str(value or "")
        for value in (
            getattr(item, "source", ""),
            getattr(item, "title", ""),
            alias_text,
            getattr(item, "summary", ""),
            " ".join(str(signal) for signal in getattr(item, "signals", ()) or ()),
            " ".join(str(evidence) for evidence in getattr(item, "evidence", ()) or ()),
            " ".join(str(tag) for tag in getattr(item, "tags", ()) or ()),
        )
    ).casefold()
    term_score = 0
    source_title = " ".join(str(value or "") for value in (getattr(item, "source", ""), getattr(item, "title", ""), alias_text)).casefold()
    focused_terms = analysis_synthesis_topic_terms(topic)
    for term in focused_terms:
        key = str(term or "").strip().casefold()
        if not key:
            continue
        if key in source_title:
            term_score += 8
        elif key in text:
            term_score += 1
    source_name = str(getattr(item, "source", "") or "")
    if not term_score and (
        source_name in {"benchmarking.html", "customer-research.html", "employee-interview.html", "ia-analysis.html", "voc-summary.html"}
        or source_name.startswith("function-inventory-")
    ):
        term_score += 3
    tags = tuple(getattr(item, "tags", ()) or ())
    is_chunk = "source_chunk" in tags
    return (
        term_score,
        int(getattr(item, "score", 0) or 0),
        0 if is_chunk else 1,
        str(getattr(item, "source", "") or ""),
    )


def refine_context_pack_evidence(selected: Sequence[object], agent_key: str, limit: int) -> List[object]:
    """Keep high-signal, non-duplicated evidence without dropping requirements."""
    refined: List[object] = []
    selected_ids: set[str] = set()
    fingerprints: set[str] = set()
    source_counts: dict[str, int] = {}
    for item in selected:
        evidence_id = str(getattr(item, "id", "") or "")
        if not evidence_id or evidence_id in selected_ids:
            continue
        kind = str(getattr(item, "kind", "") or "")
        fingerprint = context_evidence_fingerprint(item)
        if kind != "requirement" and fingerprint and fingerprint in fingerprints:
            continue
        source = str(getattr(item, "source", "") or "")
        if kind not in {"requirement", "guideline", "sample"}:
            cap = max(2, min(4, max(1, limit // 3)))
            if source_counts.get(source, 0) >= cap:
                continue
        refined.append(item)
        selected_ids.add(evidence_id)
        if fingerprint:
            fingerprints.add(fingerprint)
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(refined) >= limit:
            break
    return refined


def ensure_required_kind_coverage(
    selected: Sequence[object],
    *,
    evidence_store: EvidenceStore,
    required_kinds: Sequence[str],
    agent_key: str,
    query_terms: Sequence[str],
    limit: int,
) -> List[object]:
    """Keep at least one item for every available required evidence kind.

    Blueprint coverage can add many requirement rows. Those are important, but
    Writer quality also depends on keeping sample/guideline/VOC/IA anchors in
    the prompt. This function restores one high-authority item for missing
    required kinds without increasing the token budget.
    """
    result = list(selected)
    selected_ids = {str(getattr(item, "id", "") or "") for item in result}
    present_kinds = {str(getattr(item, "kind", "") or "") for item in result}
    query_set = {normalize_trace_key(term) for term in query_terms if str(term).strip()}
    for kind in required_kinds:
        kind = str(kind or "").strip()
        if not kind or kind in present_kinds:
            continue
        candidate = best_required_kind_candidate(
            evidence_store=evidence_store,
            kind=kind,
            agent_key=agent_key,
            query_set=query_set,
            selected_ids=selected_ids,
        )
        if candidate is None:
            continue
        result.append(candidate)
        selected_ids.add(str(getattr(candidate, "id", "") or ""))
        present_kinds.add(kind)
        result = trim_context_pack_preserving_required_kinds(result, required_kinds, limit)
    return result[:limit]


def best_required_kind_candidate(
    *,
    evidence_store: EvidenceStore,
    kind: str,
    agent_key: str,
    query_set: set[str],
    selected_ids: set[str],
):
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if str(getattr(item, "kind", "") or "") == kind
        and str(getattr(item, "id", "") or "") not in selected_ids
    ]
    if not candidates:
        return None
    stage_terms = {normalize_trace_key(term) for term in stage_profile_terms(agent_key)}

    def rank(item: object) -> tuple[int, int, int, int]:
        text = normalize_trace_key(
            " ".join(
                str(value or "")
                for value in (
                    getattr(item, "id", ""),
                    getattr(item, "title", ""),
                    getattr(item, "summary", ""),
                    " ".join(str(signal) for signal in getattr(item, "signals", ()) or ()),
                    " ".join(str(tag) for tag in getattr(item, "tags", ()) or ()),
                )
            )
        )
        query_hits = sum(1 for term in query_set if term and term in text)
        stage_hits = sum(1 for term in stage_terms if term and term in text)
        return (
            evidence_authority_score(item),
            int(getattr(item, "score", 0) or 0),
            query_hits,
            stage_hits,
        )

    return max(candidates, key=rank)


def trim_context_pack_preserving_required_kinds(
    selected: Sequence[object],
    required_kinds: Sequence[str],
    limit: int,
) -> List[object]:
    if len(selected) <= limit:
        return list(selected)
    required = {str(kind) for kind in required_kinds if str(kind).strip()}
    result = list(selected)
    while len(result) > limit:
        removable_index = removable_context_index(result, required)
        if removable_index is None:
            removable_index = len(result) - 1
        result.pop(removable_index)
    return result


def removable_context_index(selected: Sequence[object], required_kinds: set[str]) -> int | None:
    kind_counts: dict[str, int] = {}
    for item in selected:
        kind = str(getattr(item, "kind", "") or "")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    for index in range(len(selected) - 1, -1, -1):
        kind = str(getattr(selected[index], "kind", "") or "")
        if kind not in required_kinds and kind not in {"requirement", "analysis_synthesis"}:
            return index
    for index in range(len(selected) - 1, -1, -1):
        kind = str(getattr(selected[index], "kind", "") or "")
        if kind_counts.get(kind, 0) > 1:
            kind_counts[kind] -= 1
            return index
    return None


def grouped_evidence_ids(selected: Sequence[object], required_kinds: Sequence[str]) -> dict:
    required = set(required_kinds)
    essential: List[str] = []
    supplemental: List[str] = []
    for item in selected:
        evidence_id = str(getattr(item, "id", "") or "")
        if not evidence_id:
            continue
        kind = str(getattr(item, "kind", "") or "")
        if kind == "requirement" or kind in required or evidence_id.startswith(("GUIDE-", "SAMPLE-")):
            essential.append(evidence_id)
        else:
            supplemental.append(evidence_id)
    return {
        "essential": unique_texts(essential)[:20],
        "supplemental": unique_texts(supplemental)[:20],
    }


def context_evidence_fingerprint(item: object) -> str:
    text = " ".join(
        value
        for value in (
            str(getattr(item, "source", "") or ""),
            str(getattr(item, "title", "") or ""),
            str(getattr(item, "summary", "") or ""),
        )
        if value
    )
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", text).casefold()[:220]


def topic_evidence_map_for_spec(
    *,
    topic: str,
    spec: Mapping[str, object],
    evidence_store: EvidenceStore,
    learning: Mapping[str, object],
    agent_key: str,
    limit: int,
) -> dict:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    existing = meta.get("topic_evidence_map", {}) if isinstance(meta, Mapping) else {}
    if isinstance(existing, Mapping) and existing.get("stages"):
        return dict(existing)
    return build_topic_evidence_map(
        topic=topic,
        spec=spec,
        evidence_store=evidence_store,
        learning=learning,
        stages=(agent_key,),
        per_stage_limit=max(8, limit),
    )


def build_stage_evidence_digest(
    agent_key: str,
    selected: Sequence[object],
    learning: Mapping[str, object],
) -> dict:
    """Return a compact stage-specific evidence digest instead of rereading sources."""
    by_kind: dict[str, int] = {}
    requirement_ids: List[str] = []
    source_names: List[str] = []
    decision_axes: List[str] = []
    customer_tasks: List[str] = []
    bss_or_linkage: List[str] = []
    exceptions: List[str] = []
    evidence_refs: List[dict] = []
    for item in selected:
        kind = str(getattr(item, "kind", "") or "reference")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        evidence_id = str(getattr(item, "id", "") or "")
        if evidence_id.startswith("REQ-"):
            requirement_ids.append(evidence_id)
        source_names.append(str(getattr(item, "source", "") or ""))
        text = " ".join(
            [
                str(getattr(item, "title", "") or ""),
                str(getattr(item, "summary", "") or ""),
                " ".join(str(signal) for signal in getattr(item, "signals", ()) or ()),
            ]
        )
        for value in digest_sentences(text):
            if any(keyword in value for keyword in ("고객", "사용자", "조회", "신청", "변경", "해지", "확인", "사용", "선택")):
                customer_tasks.append(value)
            if any(keyword in value for keyword in ("BSS", "연계", "원장", "인증", "검증", "판정", "회신")):
                bss_or_linkage.append(value)
            if any(keyword in value for keyword in ("실패", "제한", "불가", "보류", "예외", "취소", "만료", "재시도")):
                exceptions.append(value)
            if any(keyword in value for keyword in ("기준", "조건", "허용", "제한", "정책", "동의", "고지", "이력", "저장")):
                decision_axes.append(value)
        evidence_refs.append(
            {
                "id": evidence_id,
                "kind": kind,
                "title": limit_text(getattr(item, "title", ""), 80),
            }
        )
    return {
        "stage": agent_key,
        "rule": "원천 자료는 이 digest의 판단축과 evidence_refs를 기준으로 참조한다. 원문을 추정해 일반론을 만들지 않는다.",
        "source_mix": by_kind,
        "requirement_ids": unique_texts(requirement_ids)[:20],
        "source_names": unique_texts(source_names)[:8],
        "customer_tasks": unique_texts(list_values(learning.get("customer_tasks")) + customer_tasks)[:8],
        "decision_axes": unique_texts(decision_axes)[:10],
        "bss_or_linkage": unique_texts(list_values(learning.get("bss_implications")) + bss_or_linkage)[:8],
        "exceptions": unique_texts(exceptions)[:8],
        "evidence_refs": evidence_refs[:12],
    }


def compact_evidence_for_prompt(item: object) -> dict:
    return {
        "id": str(getattr(item, "id", "") or ""),
        "kind": str(getattr(item, "kind", "") or ""),
        "source_authority": evidence_source_authority(item),
        "authority_tier": evidence_source_authority_tier(item),
        "authority_score": evidence_authority_score(item),
        "source_precedence": evidence_source_precedence(item),
        "source": limit_text(getattr(item, "source", ""), 70),
        "title": limit_text(getattr(item, "title", ""), 90),
        "summary": limit_text(getattr(item, "summary", ""), 140),
        "signals": [limit_text(value, 70) for value in list(getattr(item, "signals", ()) or ())[:3]],
        "tags": [limit_text(value, 32) for value in list(getattr(item, "tags", ()) or ())[:5]],
    }


def digest_sentences(text: object) -> List[str]:
    result: List[str] = []
    for part in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|[;\n\r]+", str(text or "")):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if 8 <= len(cleaned) <= 150:
            result.append(cleaned)
        elif len(cleaned) > 150:
            result.append(cleaned[:149].rstrip(" ,.;·/") + "…")
    return result[:12]


def list_values(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if str(value or "").strip():
        return [str(value)]
    return []


def limit_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip(" ,.;·/") + "…"


def prioritize_stage_requirement_evidence(
    selected: Sequence[object],
    evidence_store: EvidenceStore,
    spec: Mapping[str, object],
    agent_key: str,
    limit: int,
) -> List[object]:
    target_requirement_ids = stage_target_requirement_ids(spec, agent_key)
    if not target_requirement_ids:
        return list(selected)
    selected_ids = {str(getattr(item, "id", "")) for item in selected}
    covered_requirement_ids = selected_requirement_evidence_ids(spec) | {
        str(getattr(item, "id", "")) for item in selected if str(getattr(item, "id", "")).startswith("REQ-")
    }
    requirement_items = [item for item in getattr(evidence_store, "items", []) if getattr(item, "kind", "") == "requirement"]
    supplements = []
    max_supplements = min(12, max(2, int(limit * 0.75)))
    for requirement_id in target_requirement_ids:
        item = find_requirement_evidence(requirement_items, requirement_id)
        if not item or str(getattr(item, "id", "")) in selected_ids:
            continue
        if requirement_evidence_matches_any(item, covered_requirement_ids):
            continue
        supplements.append(item)
        selected_ids.add(str(getattr(item, "id", "")))
        if len(supplements) >= max_supplements:
            break
    if not supplements:
        return list(selected)[:limit]
    merged = supplements + [item for item in selected if str(getattr(item, "id", "")) not in {str(getattr(extra, "id", "")) for extra in supplements}]
    return merged[:limit]


def stage_target_requirement_ids(spec: Mapping[str, object], agent_key: str) -> List[str]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    chapters = blueprint.get("chapter_blueprints", []) if isinstance(blueprint.get("chapter_blueprints"), list) else []
    for chapter in chapters:
        if isinstance(chapter, Mapping) and chapter.get("stage") == agent_key:
            return unique_texts(chapter.get("target_requirement_ids", []))
    return []


def selected_requirement_evidence_ids(spec: Mapping[str, object]) -> set[str]:
    ids: set[str] = set()
    rows = spec.get("trace_matrix", []) if isinstance(spec.get("trace_matrix"), list) else []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for evidence_id in row.get("evidence_ids", []) if isinstance(row.get("evidence_ids"), list) else []:
            text = str(evidence_id).strip()
            if text.startswith("REQ-"):
                ids.add(text)
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    runs = meta.get("context_pack_runs", []) if isinstance(meta.get("context_pack_runs"), list) else []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        for evidence_id in run.get("evidence_ids", []) if isinstance(run.get("evidence_ids"), list) else []:
            text = str(evidence_id).strip()
            if text.startswith("REQ-"):
                ids.add(text)
    return ids


def find_requirement_evidence(items: Sequence[object], requirement_id: str):
    target_key = normalize_trace_key(requirement_id)
    exact_matches = []
    contained_matches = []
    for item in items:
        evidence_id = str(getattr(item, "id", ""))
        evidence_key = normalize_trace_key(evidence_id.removeprefix("REQ-"))
        if target_key and target_key == evidence_key:
            exact_matches.append(item)
        elif target_key and target_key in evidence_key:
            contained_matches.append(item)
    return (exact_matches or contained_matches or [None])[0]


def requirement_evidence_matches_any(item: object, evidence_ids: set[str]) -> bool:
    item_key = normalize_trace_key(str(getattr(item, "id", "")).removeprefix("REQ-"))
    return any(item_key and item_key == normalize_trace_key(eid.removeprefix("REQ-")) for eid in evidence_ids)


def normalize_trace_key(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()


def collect_query_terms(agent_key: str, spec: Mapping[str, object], learning: Mapping[str, object]) -> List[str]:
    terms: List[object] = []
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    terms.extend([meta.get("topic", ""), meta.get("business_code", "")])
    terms.extend(stage_profile_terms(agent_key))
    terms.extend(learning.get("customer_tasks", []) if isinstance(learning.get("customer_tasks"), list) else [])
    terms.extend(learning.get("policy_risks", []) if isinstance(learning.get("policy_risks"), list) else [])

    if agent_key in {"terms_refinement", "usecases", "usecase_diagram", "state", "process", "process_detail", "functions", "function_detail", "policies", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("actors", [])))
    if agent_key in {"terms_refinement", "state", "process", "process_detail", "functions", "function_detail", "policies", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("usecases", [])))
    if agent_key in {"terms_refinement", "process", "process_detail", "functions", "function_detail", "policies", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("states", [])))
    if agent_key in {"terms_refinement", "process_detail", "functions", "function_detail", "policies", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("processes", [])))
    if agent_key in {"terms_refinement", "process_detail", "function_detail", "policies", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("functions", [])))
    if agent_key in {"terms_refinement", "final_check"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("policy_groups", [])))
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("policy_details", [])))

    return unique_texts(terms)


def update_traceability(spec: dict, agent_key: str, context_pack: Mapping[str, object]) -> None:
    evidence_ids = [
        str(item.get("id", ""))
        for item in context_pack.get("selected_evidence", [])
        if isinstance(item, Mapping) and item.get("id")
    ]
    map_ids = []
    stage_map = context_pack.get("topic_evidence_map", {})
    if isinstance(stage_map, Mapping):
        map_ids = [str(item) for item in stage_map.get("evidence_ids", []) or [] if str(item).strip()]
    evidence_ids = unique_texts([*evidence_ids, *map_ids, *blueprint_requirement_evidence_ids(spec, agent_key)])
    context_quality = context_pack.get("context_quality", {})
    if not isinstance(context_quality, Mapping):
        context_quality = {}
    spec.setdefault("meta", {}).setdefault("context_pack_runs", []).append(
        {
            "chapter": agent_key,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "evidence_ids": evidence_ids,
            "evidence_source_mix": stage_map.get("source_mix", {}) if isinstance(stage_map, Mapping) else {},
            "evidence_source_names": list(stage_map.get("source_names", []) or [])[:6] if isinstance(stage_map, Mapping) else [],
            "evidence_gap_count": len(context_pack.get("evidence_gaps", []) or []),
            "context_quality_score": context_quality.get("score"),
            "context_quality_status": context_quality.get("status"),
            "required_kind_coverage": context_quality.get("required_kind_coverage"),
            "policy_question_count": len(context_pack.get("policy_questions", []) or []),
            "must_decide_count": len(context_pack.get("must_decide", []) or []),
            "policy_graph_available": bool(
                isinstance(context_pack.get("policy_graph_context"), Mapping)
                and context_pack.get("policy_graph_context", {}).get("available")
            ),
            "policy_graph_coverage_gap_count": (
                context_pack.get("policy_graph_context", {}).get("coverage_gap_count", 0)
                if isinstance(context_pack.get("policy_graph_context"), Mapping)
                else 0
            ),
            "policy_graph_chain_gap_count": (
                context_pack.get("policy_graph_context", {}).get("chain_gap_count", 0)
                if isinstance(context_pack.get("policy_graph_context"), Mapping)
                else 0
            ),
        }
    )
    merge_evidence_gaps(spec, context_pack)
    merge_trace_matrix(spec, agent_key, evidence_ids)


def blueprint_requirement_evidence_ids(spec: Mapping[str, object], agent_key: str) -> List[str]:
    """Carry Blueprint requirement coverage into deterministic traceability.

    The Evidence DB may dedupe or miss an individual requirement row, but the
    authoring blueprint is still the authoritative source for which requirement
    IDs each chapter must cover. Keeping those IDs in trace_matrix prevents the
    final Critical Gate from failing on bookkeeping while the semantic Inspector
    remains responsible for checking whether the requirement was actually
    reflected in the content.
    """
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    coverage = blueprint.get("coverage_matrix", []) if isinstance(blueprint.get("coverage_matrix"), list) else []
    result: List[str] = []
    for row in coverage:
        if not isinstance(row, Mapping):
            continue
        targets = row.get("target_stages", [])
        if isinstance(targets, str):
            targets = [targets]
        if agent_key not in {str(stage).strip() for stage in targets if str(stage).strip()}:
            continue
        requirement_id = str(row.get("requirement_id", "") or row.get("id", "")).strip()
        if not requirement_id:
            continue
        result.append(requirement_id if requirement_id.startswith("REQ-") else f"REQ-{requirement_id}")
    return unique_texts(result)


def merge_evidence_gaps(spec: dict, context_pack: Mapping[str, object]) -> None:
    gaps = spec.setdefault("evidence_gaps", [])
    existing = {gap_key(gap) for gap in gaps if isinstance(gap, Mapping)}
    for gap in context_pack.get("evidence_gaps", []) or []:
        if not isinstance(gap, Mapping):
            continue
        key = gap_key(gap)
        if key in existing:
            continue
        gaps.append(dict(gap))
        existing.add(key)


def dedupe_gaps(gaps: Sequence[Mapping[str, object]]) -> List[dict]:
    result: List[dict] = []
    seen = set()
    for gap in gaps:
        key = gap_key(gap)
        if key in seen:
            continue
        result.append(dict(gap))
        seen.add(key)
    return result


def merge_trace_matrix(spec: dict, agent_key: str, evidence_ids: Sequence[str]) -> None:
    rows = spec.setdefault("trace_matrix", [])
    existing = {str(row.get("item_id", "")) for row in rows if isinstance(row, Mapping)}
    for item in trace_items_for_stage(spec, agent_key, evidence_ids):
        if item["item_id"] in existing:
            continue
        rows.append(item)
        existing.add(item["item_id"])


def trace_items_for_stage(spec: Mapping[str, object], agent_key: str, evidence_ids: Sequence[str]) -> List[dict]:
    if agent_key == "overview":
        return [
            {
                "item_type": "overview",
                "item_id": "OVERVIEW",
                "item_name": "개요",
                "links": {
                    "scope_count": len(list_dicts(spec.get("overview", {}).get("scope", []))) if isinstance(spec.get("overview"), Mapping) else 0,
                    "principle_count": len(list_dicts(spec.get("overview", {}).get("principles", []))) if isinstance(spec.get("overview"), Mapping) else 0,
                },
                "evidence_ids": list(evidence_ids),
            }
        ]
    if agent_key == "terms":
        return [
            {
                "item_type": "term",
                "item_id": f"TERM:{row.get('name', '')}",
                "item_name": row.get("name", ""),
                "links": {},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("terms", []))
        ]
    if agent_key == "actors":
        return [
            {
                "item_type": "actor",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {"type": row.get("type", ""), "responsibility": row.get("responsibility", "")},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("actors", []))
        ]
    if agent_key == "usecases":
        return [
            {
                "item_type": "usecase",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {"actor": row.get("actor", ""), "process_target": row.get("process_target", "")},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("usecases", []))
        ]
    if agent_key == "usecase_diagram":
        diagram = spec.get("meta", {}).get("usecase_diagram", {}) if isinstance(spec.get("meta"), Mapping) else {}
        lines = diagram.get("lines", []) if isinstance(diagram, Mapping) else []
        return [
            {
                "item_type": "usecase_diagram",
                "item_id": "USECASE_DIAGRAM",
                "item_name": "유즈케이스 다이어그램",
                "links": {"line_count": len(lines)},
                "evidence_ids": list(evidence_ids),
            }
        ]
    if agent_key == "state":
        states = [
            {
                "item_type": "state",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {"description": row.get("description", "")},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("states", []))
        ]
        transitions = [
            {
                "item_type": "state_transition",
                "item_id": f"TRANSITION:{index:03d}",
                "item_name": f"{row.get('current_state', '')} -> {row.get('next_state', '')}",
                "links": {
                    "usecase_ids": row.get("usecase_ids", row.get("usecase_id", "")),
                    "current_state": row.get("current_state", ""),
                    "event": row.get("event", ""),
                    "next_state": row.get("next_state", ""),
                },
                "evidence_ids": list(evidence_ids),
            }
            for index, row in enumerate(list_dicts(spec.get("state_transitions", [])), 1)
        ]
        return states + transitions
    if agent_key == "process":
        return [
            {
                "item_type": "process",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {
                    "usecase_id": row.get("usecase_id", ""),
                    "related_functions": row.get("related_functions", []),
                    "related_policies": row.get("related_policies", []),
                },
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("processes", []))
        ]
    if agent_key == "functions":
        return [
            {
                "item_type": "function",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {
                    "process_id": row.get("process_id", ""),
                    "process_ids": row.get("process_ids", []),
                },
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("functions", []))
        ]
    if agent_key == "process_detail":
        return [
            {
                "item_type": "process_detail",
                "item_id": row.get("process_id", ""),
                "item_name": row.get("process_id", ""),
                "links": {
                    "related_functions": row.get("related_functions", []),
                    "related_policies": row.get("related_policies", []),
                },
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("process_details", []))
        ]
    if agent_key == "function_detail":
        return [
            {
                "item_type": "function_detail",
                "item_id": row.get("function_id", ""),
                "item_name": row.get("function_id", ""),
                "links": {"related_policies": row.get("related_policies", [])},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("function_details", []))
        ]
    if agent_key == "policies":
        groups = [
            {
                "item_type": "policy_group",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("policy_groups", []))
        ]
        details = [
            {
                "item_type": "policy_item",
                "item_id": row.get("id", ""),
                "item_name": row.get("name", ""),
                "links": {"policy_id": row.get("policy_id", "")},
                "evidence_ids": list(evidence_ids),
            }
            for row in list_dicts(spec.get("policy_details", []))
        ]
        return groups + details
    if agent_key == "final_check":
        return [
            {
                "item_type": "final_check",
                "item_id": f"FINAL_CHECK:{index:03d}",
                "item_name": str(item),
                "links": {},
                "evidence_ids": list(evidence_ids),
            }
            for index, item in enumerate(spec.get("final_check", []) if isinstance(spec.get("final_check"), list) else [], 1)
            if str(item).strip()
        ]
    return []


def gap_key(gap: Mapping[str, object]) -> str:
    return f"{gap.get('stage', '')}:{gap.get('missing_kind', '')}:{gap.get('reason', '')}"


def list_dicts(value: object) -> List[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def unique_texts(values: Iterable[object]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) < 2:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result
