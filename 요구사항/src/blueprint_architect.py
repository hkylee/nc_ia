"""Blueprint Architect Agent for hierarchy-first policy authoring.

The architect does not write the policy body. It defines the hierarchy contract
that chapter writers and inspectors must follow before chapter writing starts.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

try:
    from llm_client import LLMClient, LLMError
    from policy_insight_rules import insight_applicability_for_prompt
    from runtime_paths import REPORTS_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .llm_client import LLMClient, LLMError
    from .policy_insight_rules import insight_applicability_for_prompt
    from .runtime_paths import REPORTS_ROOT


EXECUTION_CHAIN = ("actor", "usecase", "process", "function", "function_detail")
POLICY_CHAIN = ("process", "policy_group", "policy_item")
BLUEPRINT_ARCHITECT_CACHE_VERSION = "blueprint-architect-llm-v4-requirement-level-pdf"
BLUEPRINT_CACHE_DIR = REPORTS_ROOT / "cache"
CORE_STAGE_CONTRACTS = (
    "actors",
    "usecases",
    "state",
    "process",
    "functions",
    "function_detail",
    "policies",
    "final_check",
)


def build_architecture_contract(
    *,
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    evidence_store: object | None = None,
) -> dict:
    """Build a deterministic hierarchy contract for all downstream agents."""
    topic = str(getattr(ctx, "topic", "") or authoring_blueprint.get("meta", {}).get("topic", "")).strip()
    signals = authoring_blueprint.get("analysis_signals", {}) if isinstance(authoring_blueprint.get("analysis_signals"), Mapping) else {}
    architecture_evidence_pack = build_architecture_evidence_pack(
        ctx=ctx,
        evidence_store=evidence_store,
        authoring_blueprint=authoring_blueprint,
        learning=learning,
    )
    requirement_hierarchy_plan = (
        authoring_blueprint.get("requirement_hierarchy_plan", [])
        if isinstance(authoring_blueprint.get("requirement_hierarchy_plan", []), list)
        else []
    )
    core_design_map = build_core_design_map(signals, learning, requirement_hierarchy_plan)
    return {
        "version": "architecture-v1",
        "agent": "Blueprint Architect Agent",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "summary": (
            "본문 작성 전에 액터-유즈케이스-프로세스-기능-세부 기능 구성과 "
            "프로세스-정책-정책 항목의 계위를 고정한다."
        ),
        "blueprint_phases": blueprint_phase_contracts(),
        "hierarchy_chains": [
            {
                "name": "execution_chain",
                "path": list(EXECUTION_CHAIN),
                "principle": "사람 또는 시스템 책임 주체에서 시작해, 상위 업무 목적을 절차로 분해하고, 절차 수행에 필요한 처리 역량과 하위 처리명으로 내려간다.",
                "granularity_rule": "유즈케이스는 여러 프로세스로 분해 가능해야 하고, 기능은 프로세스 1:1 복사가 아니라 재사용 가능한 처리 역량이어야 한다.",
            },
            {
                "name": "policy_chain",
                "path": list(POLICY_CHAIN),
                "principle": "정책은 프로세스와 기능이 동작하려면 결정해야 하는 통제 지점에서 도출한다.",
                "granularity_rule": "정책 그룹은 판단 영역, 정책 항목은 하나의 값·조건·허용 범위·제한 기준 단위로 작성한다.",
            },
        ],
        "architecture_evidence_pack": architecture_evidence_pack,
        "hierarchy_skeleton": deterministic_hierarchy_skeleton(
            signals,
            learning,
            architecture_evidence_pack,
            requirement_hierarchy_plan,
        ),
        "core_design_map": core_design_map,
        "stage_contracts": deterministic_stage_contracts(signals, learning),
        "first_draft_quality_plan": deterministic_first_draft_quality_plan(signals, learning),
        "quality_gates": architecture_quality_gates(),
        "evidence_gaps": architecture_evidence_gaps(authoring_blueprint),
    }


def enhance_architecture_contract_with_llm(
    *,
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    contract: Mapping[str, object],
    llm_client: LLMClient,
) -> dict:
    """Let the LLM refine the hierarchy contract when LLM writing is enabled."""
    if not llm_client.enabled:
        return dict(contract)
    cached_contract = load_architecture_contract_cache(ctx, authoring_blueprint, learning, contract, llm_client)
    if cached_contract:
        cached_contract["llm_cache_hit"] = True
        return cached_contract
    prompt = {
        "topic": getattr(ctx, "topic", ""),
        "template_type": getattr(ctx, "template_type", ""),
        "base_contract": compact_contract(contract),
        "learning": compact_learning(learning),
        "blueprint_signals": compact_blueprint(authoring_blueprint),
    }
    try:
        result = llm_client.generate_json(
            schema_name="blueprint_architect_contract",
            schema=architecture_contract_schema(),
            instructions=(
                "너는 NC 정책서 Blueprint Architect Agent다. "
                "본문을 작성하지 말고, Stage A에서는 계층·입자도·근거 우선순위를 고정하고 Stage B에서는 장별 Writer 기준을 정리한다. "
                "템플릿과 샘플의 간결한 장 구조를 바꾸지 않는다. "
                "특정 도메인에만 맞는 규칙이 아니라 다양한 정책서 주제에 공통 적용 가능한 기준으로 쓴다.\n"
                + insight_applicability_for_prompt()
            ),
            input_messages=[
                {
                    "role": "user",
                    "content": (
                        "다음 자료를 보고 액터-유즈케이스-프로세스-기능-세부 기능 구성 계층과 "
                        "프로세스-정책-정책 항목 계층을 작성 전에 고정해줘. "
                        "blueprint_phases에는 Stage A 계층 결정과 Stage B 장별 기준이 어떻게 이어지는지 명확히 쓰고, "
                        "hierarchy_skeleton에는 실제 Writer가 참고할 후보 구조를 간결하게 작성해줘.\n"
                        + json.dumps(prompt, ensure_ascii=False)
                    ),
                }
            ],
        )
    except LLMError:
        if llm_client.forced:
            raise
        return dict(contract)
    enhanced = merge_architecture_contract(contract, result)
    enhanced["llm_cache_hit"] = False
    save_architecture_contract_cache(ctx, authoring_blueprint, learning, contract, llm_client, enhanced)
    return enhanced


def load_architecture_contract_cache(
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    contract: Mapping[str, object],
    llm_client: LLMClient,
) -> dict | None:
    path = architecture_contract_cache_path(ctx, authoring_blueprint, learning, contract, llm_client)
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(cached, Mapping):
        return None
    if cached.get("cache_version") != BLUEPRINT_ARCHITECT_CACHE_VERSION:
        return None
    if cached.get("signature") != architecture_contract_cache_signature(
        ctx,
        authoring_blueprint,
        learning,
        contract,
        llm_client,
    ):
        return None
    payload = cached.get("payload")
    return dict(payload) if isinstance(payload, Mapping) and valid_architecture_contract_payload(payload) else None


def save_architecture_contract_cache(
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    contract: Mapping[str, object],
    llm_client: LLMClient,
    payload: Mapping[str, object],
) -> None:
    if not valid_architecture_contract_payload(payload):
        return
    try:
        BLUEPRINT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        architecture_contract_cache_path(ctx, authoring_blueprint, learning, contract, llm_client).write_text(
            json.dumps(
                {
                    "cache_version": BLUEPRINT_ARCHITECT_CACHE_VERSION,
                    "topic": getattr(ctx, "topic", ""),
                    "template_type": getattr(ctx, "template_type", ""),
                    "model": llm_client.model,
                    "reasoning_effort": llm_client.reasoning_effort,
                    "signature": architecture_contract_cache_signature(
                        ctx,
                        authoring_blueprint,
                        learning,
                        contract,
                        llm_client,
                    ),
                    "payload": dict(payload),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def architecture_contract_cache_path(
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    contract: Mapping[str, object],
    llm_client: LLMClient,
) -> Path:
    signature = architecture_contract_cache_signature(ctx, authoring_blueprint, learning, contract, llm_client)
    digest = hashlib.sha256(json.dumps(signature, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    raw_topic = str(getattr(ctx, "topic_slug", "") or getattr(ctx, "topic", "") or "topic")
    safe_topic = re.sub(r"[^0-9A-Za-z가-힣_-]+", "", raw_topic) or "topic"
    return BLUEPRINT_CACHE_DIR / f"blueprint_architect_{safe_topic}_{digest}.json"


def architecture_contract_cache_signature(
    ctx: object,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    contract: Mapping[str, object],
    llm_client: LLMClient,
) -> dict:
    meta = authoring_blueprint.get("meta", {}) if isinstance(authoring_blueprint.get("meta"), Mapping) else {}
    blueprint_signals = compact_blueprint(authoring_blueprint)
    if isinstance(blueprint_signals.get("meta"), Mapping):
        stable_meta = dict(blueprint_signals.get("meta", {}))
        stable_meta.pop("generated_at", None)
        blueprint_signals["meta"] = stable_meta
    return {
        "cache_version": BLUEPRINT_ARCHITECT_CACHE_VERSION,
        "topic": getattr(ctx, "topic", ""),
        "business_code": getattr(ctx, "business_code", ""),
        "template_type": getattr(ctx, "template_type", ""),
        "model": llm_client.model,
        "reasoning_effort": llm_client.reasoning_effort,
        "blueprint_source_fingerprint": meta.get("source_fingerprint", ""),
        "base_contract": compact_contract(contract),
        "learning": compact_learning(learning),
        "blueprint_signals": blueprint_signals,
    }


def valid_architecture_contract_payload(payload: Mapping[str, object]) -> bool:
    return (
        isinstance(payload.get("hierarchy_chains"), list)
        and isinstance(payload.get("stage_contracts"), list)
        and isinstance(payload.get("first_draft_quality_plan"), Mapping)
        and bool(payload.get("hierarchy_chains"))
        and bool(payload.get("stage_contracts"))
    )


def blueprint_phase_contracts() -> list[dict]:
    return [
        {
            "phase": "stage_a_hierarchy_decision",
            "purpose": "본문 작성 전에 업무 계층, 입자도, 금지 기준, 근거 우선순위를 고정한다.",
            "inputs": ["attached requirements", "templates", "samples", "AGENTS.md", "references", "topic learning"],
            "outputs": ["hierarchy_chains", "hierarchy_skeleton", "evidence priority", "handoff_rules"],
            "quality_gate": "액터→유즈케이스→프로세스→기능→세부 기능 구성과 프로세스→정책→정책 항목 계층이 충돌 없이 설명된다.",
        },
        {
            "phase": "stage_b_stage_authoring_criteria",
            "purpose": "Stage A 계층 계약을 장별 Writer가 사용할 작성 기준과 검수 기준으로 변환한다.",
            "inputs": ["Stage A hierarchy contract", "stage evidence ids", "chapter order"],
            "outputs": ["stage_contracts", "first_draft_quality_plan", "quality_gates"],
            "quality_gate": "각 장이 무엇을 쓰고 무엇을 쓰지 않을지, 다음 장으로 무엇을 넘길지 명확하다.",
        },
    ]


def deterministic_hierarchy_skeleton(
    signals: Mapping[str, object],
    learning: Mapping[str, object],
    architecture_evidence_pack: Mapping[str, object] | None = None,
    requirement_hierarchy_plan: Sequence[Mapping[str, object]] = (),
) -> dict:
    customer_tasks = compact_list(list_values(signals.get("customer_tasks")) + list_values(learning.get("customer_tasks")), 5)
    policy_points = compact_list(list_values(signals.get("policy_decision_points")) + list_values(learning.get("policy_risks")), 6)
    bss_points = compact_list(list_values(signals.get("bss_touchpoints")) + list_values(learning.get("bss_implications")), 5)
    operation_points = compact_list(list_values(signals.get("operation_points")), 4)
    customer_goals = customer_tasks or ["고객이 현재 주제의 핵심 업무를 시작해 결과를 확인한다."]
    actor_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "actors")
    usecase_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "usecases")
    state_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "state")
    process_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "process")
    function_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "functions")
    policy_evidence_ids = stage_evidence_ids(architecture_evidence_pack, "policies")
    return {
        "actor_candidates": [
            {
                "name": "고객",
                "role": "업무를 시작하고 결과를 확인하는 주체",
                "include_reason": "대부분의 정책서에서 고객 완결 업무의 시작점이 된다.",
                "not_actor_examples": ["로그인 고객", "정상 고객", "제한 고객"],
                "evidence_ids": actor_evidence_ids,
            },
            {
                "name": "운영자",
                "role": "기준 관리, 예외 확인, 품질 모니터링 주체",
                "include_reason": "운영 관리나 예외 처리 근거가 있을 때만 포함한다.",
                "not_actor_examples": ["단순 승인자", "화면 관리자"],
                "evidence_ids": actor_evidence_ids,
            },
            {
                "name": "BSS/연계 시스템",
                "role": "검증, 판정, 상태 변경, 원장 반영, 결과 회신 주체",
                "include_reason": "업무 가능 여부나 결과 확정에 시스템 판정이 필요한 경우 포함한다.",
                "not_actor_examples": ["화면 컴포넌트", "DB 테이블"],
                "evidence_ids": state_evidence_ids or process_evidence_ids,
            },
        ],
        "usecase_groups": [
            {
                "actor": "고객",
                "goal": goal,
                "process_target": "Y",
                "process_pattern": ["진입 및 대상 확인", "조건 검증", "입력·선택 또는 동의", "처리 요청", "결과 안내"],
                "function_axes": ["조회", "검증", "저장", "알림", "이력"],
                "policy_axes": policy_points[:4],
                "evidence_ids": usecase_evidence_ids,
            }
            for goal in customer_goals[:4]
        ],
        "process_patterns": [
            {
                "usecase_type": "고객 처리형",
                "steps": ["업무 진입", "대상/권한 확인", "조건·상태 판정", "필요 정보 입력 또는 선택", "처리 요청", "결과 반영 및 안내"],
                "state_touchpoints": ["진행 중", "제한", "보류", "완료", "실패"],
                "bss_touchpoints": bss_points[:4],
                "evidence_ids": process_evidence_ids,
            },
            {
                "usecase_type": "운영 관리형",
                "steps": ["기준 확인", "등록 또는 검토", "승인 또는 반영", "변경 이력 저장", "품질 확인"],
                "state_touchpoints": ["운영 검토", "운영 반영 완료"],
                "bss_touchpoints": operation_points[:3],
                "evidence_ids": process_evidence_ids,
            },
        ],
        "function_capabilities": [
            {"name": "대상 정보 조회", "capability_type": "조회", "detail_granularity": ["조회 조건 구성", "대상 정보 수집", "조회 결과 정리"], "reuse_rule": "여러 프로세스에서 같은 대상 정보를 확인하면 하나의 기능을 process_ids로 재사용한다.", "evidence_ids": function_evidence_ids},
            {"name": "자격 및 조건 검증", "capability_type": "검증", "detail_granularity": ["권한 상태 검증", "조건 충족 여부 판정", "제한 사유 구성"], "reuse_rule": "가능 여부 판단이 반복되면 공통 검증 기능으로 둔다.", "evidence_ids": function_evidence_ids or policy_evidence_ids},
            {"name": "업무 처리 요청", "capability_type": "저장/연동", "detail_granularity": ["요청 정보 구성", "연계 요청", "처리 결과 수신"], "reuse_rule": "BSS 또는 외부 연계 요청이 필요한 프로세스에 연결한다.", "evidence_ids": function_evidence_ids or process_evidence_ids},
            {"name": "결과 안내 및 이력 저장", "capability_type": "알림/이력", "detail_granularity": ["결과 안내 구성", "고객 고지", "처리 이력 저장"], "reuse_rule": "완료·제한·실패 안내가 필요한 프로세스에서 재사용한다.", "evidence_ids": function_evidence_ids},
        ],
        "policy_taxonomy": [
            {
                "policy_group": "가능 여부 판단 정책",
                "derived_from": ["조건 검증", "자격 판정", "제한 상태"],
                "policy_items": ["허용 조건", "제한 조건", "우선순위", "예외 불가 조건"],
                "value_examples": policy_points[:4],
                "evidence_ids": policy_evidence_ids,
            },
            {
                "policy_group": "고지 및 이력 정책",
                "derived_from": ["결과 안내", "이력 저장", "운영 확인"],
                "policy_items": ["고지 채널", "고지 내용", "저장 항목", "보관 기준"],
                "value_examples": ["채널별 고지 기준", "처리 이력 저장 기준"],
                "evidence_ids": policy_evidence_ids or function_evidence_ids,
            },
        ],
        "requirement_derived_candidates": compact_requirement_derived_candidates(requirement_hierarchy_plan),
        "handoff_rules": [
            "Usecases Agent는 절차와 기능을 유즈케이스로 올리지 않는다.",
            "Process Agent는 유즈케이스별 절차를 만들고 기능·정책 연결은 후속 장으로 넘긴다.",
            "Functions Agent는 프로세스 수행 역량과 세부 기능 구성을 만들고 공통 기능을 재사용한다.",
            "Policies Agent는 프로세스와 기능의 통제 지점에서 정책 그룹과 항목값을 도출한다.",
        ],
    }


def build_architecture_evidence_pack(
    *,
    ctx: object,
    evidence_store: object | None,
    authoring_blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    limit_per_stage: int = 6,
    max_total_cards: int = 28,
) -> dict:
    if evidence_store is None or not hasattr(evidence_store, "select"):
        return {}
    topic = str(getattr(ctx, "topic", "") or authoring_blueprint.get("meta", {}).get("topic", "")).strip()
    signals = authoring_blueprint.get("analysis_signals", {}) if isinstance(authoring_blueprint.get("analysis_signals"), Mapping) else {}
    stage_profiles = {
        "actors": ("requirement", "guideline"),
        "usecases": ("requirement", "voc", "research", "guideline"),
        "state": ("requirement", "voc", "guideline"),
        "process": ("requirement", "voc", "ia", "guideline"),
        "functions": ("requirement", "ia", "guideline"),
        "policies": ("requirement", "voc", "strategy", "guideline"),
    }
    cards_by_id: dict[str, dict] = {}
    stage_card_ids: dict[str, list[str]] = {}
    for stage, required_kinds in stage_profiles.items():
        selected = evidence_store.select(
            stage=stage,
            topic=topic,
            query_terms=architecture_query_terms(stage, signals, learning),
            required_kinds=required_kinds,
            limit=limit_per_stage,
        )
        stage_ids: list[str] = []
        for item in selected:
            item_id = str(getattr(item, "id", "") or "")
            if not item_id:
                continue
            stage_ids.append(item_id)
            if item_id not in cards_by_id and len(cards_by_id) < max_total_cards:
                card = item.to_prompt_dict(max_chars=300) if hasattr(item, "to_prompt_dict") else {}
                card["stages"] = [stage]
                cards_by_id[item_id] = card
            elif item_id in cards_by_id:
                stages = cards_by_id[item_id].setdefault("stages", [])
                if isinstance(stages, list) and stage not in stages:
                    stages.append(stage)
        stage_card_ids[stage] = stage_ids[:limit_per_stage]
    return {
        "selection_rule": "Blueprint Architect는 원천 전체가 아니라 Evidence Store에서 계층 설계에 필요한 stage별 근거 카드를 직접 선별해 사용한다.",
        "stage_card_ids": stage_card_ids,
        "cards": list(cards_by_id.values()),
        "stats": {
            "stage_count": len(stage_profiles),
            "card_count": len(cards_by_id),
        },
    }


def architecture_query_terms(stage: str, signals: Mapping[str, object], learning: Mapping[str, object]) -> list[str]:
    common = (
        list_values(learning.get("customer_tasks"))
        + list_values(learning.get("requirement_implications"))
        + list_values(signals.get("customer_tasks"))
    )
    by_stage = {
        "actors": list_values(signals.get("bss_touchpoints")) + list_values(signals.get("operation_points")),
        "usecases": list_values(signals.get("voc_pain_points")) + list_values(signals.get("requirement_implications")),
        "state": list_values(signals.get("exception_points")) + list_values(signals.get("bss_touchpoints")),
        "process": list_values(signals.get("ia_flow_points")) + list_values(signals.get("bss_touchpoints")),
        "functions": list_values(signals.get("ia_flow_points")) + list_values(signals.get("data_log_points")),
        "policies": list_values(signals.get("policy_decision_points")) + list_values(signals.get("data_log_points")),
    }
    return compact_list(common + by_stage.get(stage, []), 18)


def compact_requirement_derived_candidates(rows: Sequence[Mapping[str, object]], limit: int = 18) -> list[dict]:
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "requirement_id": compact_string(row.get("requirement_id", ""), 80),
                "title": compact_string(row.get("title", ""), 100),
                "summary": compact_string(row.get("summary", ""), 220),
                "source_excerpt": compact_string(row.get("source_excerpt", ""), 240),
                "actor_candidates": compact_list(list_values(row.get("actor_candidates")), 5),
                "usecase_candidate": compact_string(row.get("usecase_candidate", ""), 100),
                "process_candidate": compact_string(row.get("process_candidate", ""), 100),
                "function_capabilities": compact_list(list_values(row.get("function_capabilities")), 6),
                "policy_decision_axes": compact_list(list_values(row.get("policy_decision_axes")), 6),
                "target_stages": compact_list(list_values(row.get("target_stages")), 10),
            }
        )
        if len(result) >= limit:
            break
    return result


def build_core_design_map(
    signals: Mapping[str, object],
    learning: Mapping[str, object],
    requirement_hierarchy_plan: Sequence[Mapping[str, object]],
) -> dict:
    rows: list[dict] = []
    for row in requirement_hierarchy_plan:
        if not isinstance(row, Mapping):
            continue
        policy_axes = compact_list(list_values(row.get("policy_decision_axes")), 6)
        rows.append(
            {
                "requirement_id": compact_string(row.get("requirement_id", ""), 80),
                "title": compact_string(row.get("title", ""), 100),
                "summary": compact_string(row.get("summary", ""), 180),
                "actors": compact_list(list_values(row.get("actor_candidates")), 5),
                "usecase": compact_string(row.get("usecase_candidate", ""), 100),
                "state_candidates": state_candidates_for_requirement(row),
                "process": compact_string(row.get("process_candidate", ""), 100),
                "functions": compact_list(list_values(row.get("function_capabilities")), 6),
                "policy_candidates": policy_candidates_from_axes(policy_axes),
                "policy_item_axes": policy_axes,
                "source_rule": "요구사항을 복사하지 않고 계층 후보로 해석한 설계 초안이다.",
            }
        )
        if len(rows) >= 24:
            break
    return {
        "agent_role": "Core Design Agent 역할을 Blueprint Architect가 수행한다.",
        "approval_status": "approved_baseline",
        "contract_rule": "이 Core Design Map은 장별 Writer가 공유하는 통합 설계 기준이다. Writer는 요구사항·첨부자료와 충돌하지 않는 한 이 후보 계층을 유지한다.",
        "purpose": "장별 Writer가 분리되어 있어도 같은 액터-유즈케이스-상태-프로세스-기능-정책 후보를 기준으로 작성하게 한다.",
        "design_rows": rows,
        "required_handoff": {
            "actors": "액터 후보는 책임 주체만 채택하고 고객 상태는 조건/정책으로 넘긴다.",
            "usecases": "유즈케이스 후보는 고객·운영자가 완료하려는 상위 업무 목표로 정제한다.",
            "state": "상태 후보는 승인된 유즈케이스 lifecycle에서 도출하고, 전이 이벤트는 상태를 바꾸는 업무 사건으로 쓰며 usecase_ids로 추적한다.",
            "process": "프로세스 후보는 process_target=Y 유즈케이스의 시작-판단-요청-반영-안내 흐름으로 분해한다.",
            "functions": "기능 후보는 프로세스 수행에 필요한 처리 역량으로 묶고 세부 기능 구성으로 내려간다.",
            "policies": "정책 후보는 프로세스와 기능이 동작하려면 결정해야 하는 판단값·조건·예외·고지·이력 기준으로 구체화한다.",
        },
        "fallback_axes": {
            "customer_jobs": compact_list(list_values(signals.get("customer_tasks")) + list_values(learning.get("customer_tasks")), 8),
            "policy_questions": compact_list(list_values(signals.get("policy_decision_points")) + list_values(learning.get("policy_risks")), 8),
            "bss_touchpoints": compact_list(list_values(signals.get("bss_touchpoints")) + list_values(learning.get("bss_implications")), 8),
        },
        "must_not": [
            "장별 Writer가 상위 계층을 임의로 다시 설계하지 않는다.",
            "요구사항 문구를 정책서 본문에 그대로 복사하지 않는다.",
            "기능명과 정책명을 프로세스명에서 1:1 복사하지 않는다.",
            "PM-XX 수동 작성 인사이트를 현재 주제 근거 없이 공통 규칙처럼 적용하지 않는다.",
        ],
    }


def state_candidates_for_requirement(row: Mapping[str, object]) -> list[str]:
    text = " ".join(
        list_values(row.get("policy_decision_axes"))
        + list_values(row.get("function_capabilities"))
        + [str(row.get("title", "")), str(row.get("summary", ""))]
    )
    states = ["진입 전", "요청 접수", "처리 완료"]
    if any(keyword in text for keyword in ("검증", "판정", "조건", "권한", "자격", "BSS", "연계")):
        states.insert(2, "판정 필요")
    if any(keyword in text for keyword in ("제한", "실패", "오류", "보류", "불가", "취소", "만료", "예외")):
        states.extend(["처리 제한", "처리 실패", "처리 보류"])
    return compact_list(states, 7)


def policy_candidates_from_axes(policy_axes: Sequence[str]) -> list[str]:
    candidates: list[str] = []
    for axis in policy_axes:
        if any(keyword in axis for keyword in ("대상", "허용", "제한", "조건")):
            candidates.append("가능 여부 판단 정책")
        elif any(keyword in axis for keyword in ("횟수", "시간", "기간")):
            candidates.append("횟수·시간 제한 정책")
        elif any(keyword in axis for keyword in ("채널", "고지")):
            candidates.append("고지 및 노출 정책")
        elif any(keyword in axis for keyword in ("예외", "실패")):
            candidates.append("예외 및 복구 정책")
        elif any(keyword in axis for keyword in ("이력", "보관", "동의")):
            candidates.append("동의·이력·보관 정책")
        elif any(keyword in axis for keyword in ("금액", "혜택")):
            candidates.append("금액·혜택 적용 정책")
        else:
            candidates.append(f"{axis} 정책")
    return compact_list(candidates or ["처리 결과 기준 정책"], 6)


def stage_evidence_ids(evidence_pack: Mapping[str, object] | None, stage: str, limit: int = 5) -> list[str]:
    if not isinstance(evidence_pack, Mapping):
        return []
    stage_card_ids = evidence_pack.get("stage_card_ids", {})
    if not isinstance(stage_card_ids, Mapping):
        return []
    raw_ids = stage_card_ids.get(stage, [])
    if not isinstance(raw_ids, list):
        return []
    return [str(item).strip() for item in raw_ids if str(item).strip()][:limit]


def deterministic_first_draft_quality_plan(signals: Mapping[str, object], learning: Mapping[str, object]) -> dict:
    """Define what writers must get right before the first Inspector pass."""
    customer_tasks = compact_list(list_values(signals.get("customer_tasks")) + list_values(learning.get("customer_tasks")), 5)
    policy_points = compact_list(list_values(signals.get("policy_decision_points")) + list_values(learning.get("policy_risks")), 6)
    bss_points = compact_list(list_values(signals.get("bss_touchpoints")) + list_values(learning.get("bss_implications")), 5)
    return {
        "purpose": "Inspector 보완 반복을 줄이기 위해 Writer가 출력 직전 계층·입자도·연결성 기준을 먼저 대조한다.",
        "stage_checks": [
            first_draft_stage_check(
                "overview",
                "요구사항 4depth와 주제 학습 결과로 고객 과업 범위를 고정한다.",
                "포함 범위, 제외 범위, 후속 상세화 영역, 4~6개 설계 원칙",
                "범위가 고객 과업 중심이며 내부 시스템 설명으로만 흐르지 않는다.",
                "일반론 원칙만 있고 기능·정책 판단으로 연결될 기준이 없다.",
                customer_tasks,
            ),
            first_draft_stage_check(
                "terms",
                "이후 장에서 판단값으로 쓰일 상태·권한·인증·동의·이력 용어만 고른다.",
                "일반 명사가 아니라 업무 판단 기준이 있는 용어 목록",
                "각 용어 설명에 유사 용어와 구분되는 판단 기준이 있다.",
                "상태값 후보를 용어장에서 새로 발명하거나 화면 표현을 용어로 올린다.",
            ),
            first_draft_stage_check(
                "actors",
                "유즈케이스를 시작하거나 결과를 생성하는 독립 책임 주체만 남긴다.",
                "고객, 운영자, BSS/연계 시스템 등 책임이 분리되는 액터",
                "로그인/비로그인/정상/제한 같은 고객 상태가 액터로 분리되지 않는다.",
                "권한·상태 조건을 액터로 쪼개거나 시스템 책임을 누락한다.",
            ),
            first_draft_stage_check(
                "usecases",
                "액터별 상위 업무 목표를 정의하고 절차·기능 수준 행위는 제외한다.",
                "사람 액터의 process_target=Y 유즈케이스와 시스템 보조 유즈케이스",
                "사람 액터 유즈케이스는 뒤에서 시작·판단·처리·결과 같은 여러 의미 전환점으로 분해 가능한 크기다.",
                "본인인증, 조회, 저장, 알림 같은 기능을 독립 유즈케이스로 과분해한다.",
                customer_tasks,
            ),
            first_draft_stage_check(
                "state",
                "액터-유즈케이스 관계에서 상태를 도출하고 전이 이벤트는 상태를 실제로 바꾸는 업무 사건으로 둔다.",
                "정상·제한·보류·실패·완료 상태와 유즈케이스 기반 전이표",
                "모든 전이는 상태 목록의 이름을 그대로 쓰고 event는 업무 사건, usecase_ids는 승인된 유즈케이스 ID다.",
                "기능명·프로세스명·내부 처리 단계명을 event로 쓰거나 UI 상태를 만든다.",
                bss_points,
            ),
            first_draft_stage_check(
                "process",
                "process_target=Y 유즈케이스를 고객/운영자 업무 전환점으로 분해한다.",
                "유즈케이스별 의미 있는 프로세스 경계, 시작·판단·입력/선택·요청·결과 안내 흐름",
                "프로세스는 기능명이 아니라 업무 절차이며 관련 기능·정책은 후속 장에서 확정한다.",
                "상위 유즈케이스를 포괄 프로세스 1개로 축약하거나, 개수 맞추기를 위해 조회·검증·저장을 유사 프로세스로 나열한다.",
            ),
            first_draft_stage_check(
                "functions",
                "프로세스를 수행하는 재사용 가능한 처리 역량으로 기능을 묶는다.",
                "조회·검증·산정·저장·알림·연동 기능과 짧은 세부 기능 구성",
                "하나의 기능이 여러 프로세스에 재사용될 수 있고 details는 하위 처리명이다.",
                "프로세스명 1:1 복사 기능 또는 정책값이 긴 기능 설명으로 들어간다.",
            ),
            first_draft_stage_check(
                "policies",
                "프로세스와 기능 동작에 필요한 값·조건·허용 범위·제한 기준을 정책으로 분리한다.",
                "정책 그룹과 정책 항목별 실제 값, 조건, 우선순위, 예외, 고지, 이력 기준",
                "정책 항목은 기능 동작값 또는 판단 기준 하나만 담고 샘플처럼 간결하다.",
                "기능 설명을 정책처럼 쓰거나 TBD만 남기고 결정 주체·사유·기한을 쓰지 않는다.",
                policy_points,
            ),
            first_draft_stage_check(
                "final_check",
                "전체 체인의 끊김과 입자도 오류를 최종 보정한다.",
                "유즈케이스→프로세스→기능→세부 기능 구성, 프로세스→정책→정책 항목 점검",
                "요구사항과 근거가 산출물에 연결되고 정책이 실제 판단값을 가진다.",
                "HTML 외형만 보고 구조 정합성, 정책 구체성, 근거 추적성을 놓친다.",
            ),
        ],
        "handoff_checks": [
            "Usecases 통과 후 State/Process는 유즈케이스명을 바꾸지 않는다.",
            "Process 통과 후 Functions는 프로세스별 필요 역량을 만들되 프로세스명을 복사하지 않는다.",
            "Functions 통과 후 Policies는 기능 동작에 필요한 정책값과 조건을 도출한다.",
            "Policies 통과 후 Process의 관련 기능·관련 정책은 ID와 명칭으로 역연결한다.",
        ],
        "token_efficiency_rule": "Writer는 이 기준을 내부 점검에만 사용하고 self_check 결과를 JSON에 출력하지 않는다.",
    }


def first_draft_stage_check(
    stage: str,
    before_write: str,
    must_produce: str,
    self_check: str,
    reject_if: str,
    topic_axes: Sequence[str] = (),
) -> dict:
    return {
        "stage": stage,
        "before_write": before_write,
        "must_produce": must_produce,
        "self_check": self_check,
        "reject_if": reject_if,
        "topic_axes": list(topic_axes)[:5],
    }


def compact_first_draft_quality_plan(plan: object) -> dict:
    if not isinstance(plan, Mapping):
        return {}
    return {
        "purpose": str(plan.get("purpose", ""))[:220],
        "stage_checks": [
            {
                "stage": item.get("stage", ""),
                "before_write": str(item.get("before_write", ""))[:180],
                "must_produce": str(item.get("must_produce", ""))[:180],
                "self_check": str(item.get("self_check", ""))[:180],
                "reject_if": str(item.get("reject_if", ""))[:180],
                "topic_axes": item.get("topic_axes", [])[:5] if isinstance(item.get("topic_axes", []), list) else [],
            }
            for item in plan.get("stage_checks", [])[:12]
            if isinstance(item, Mapping)
        ],
        "handoff_checks": [
            str(item)[:180]
            for item in plan.get("handoff_checks", [])[:8]
            if str(item).strip()
        ],
        "token_efficiency_rule": str(plan.get("token_efficiency_rule", ""))[:180],
    }


def deterministic_stage_contracts(signals: Mapping[str, object], learning: Mapping[str, object]) -> list[dict]:
    customer_tasks = compact_list(list_values(signals.get("customer_tasks")) + list_values(learning.get("customer_tasks")), 6)
    policy_points = compact_list(list_values(signals.get("policy_decision_points")) + list_values(learning.get("policy_risks")), 8)
    bss_points = compact_list(list_values(signals.get("bss_touchpoints")) + list_values(learning.get("bss_implications")), 6)
    return [
        stage_contract(
            "actors",
            "actor",
            "독립 책임 주체",
            "유즈케이스를 시작하거나 결과를 생성하는 주체만 둔다.",
            ("고객 상태, 자격, 로그인 여부를 액터로 분리하지 않는다.", "BSS·인증기관·연계 시스템의 판정 책임을 섞지 않는다."),
            ("usecases",),
            ("액터별 책임이 한 문장으로 구분된다.", "사람 액터와 시스템 액터의 책임이 충돌하지 않는다."),
        ),
        stage_contract(
            "usecases",
            "usecase",
            "상위 업무 목표",
            "고객·운영자 등 사람이 완료하려는 업무 목적이며 뒤에서 시작·판단·처리·결과 같은 의미 전환점으로 분해 가능해야 한다.",
            ("약관 동의, 본인인증, 정보 입력, 조회, 검증, 저장, 알림을 독립 유즈케이스로 만들지 않는다.",),
            ("state", "process"),
            ("사람 액터 유즈케이스는 process_target=Y다.", "절차·기능 수준 행위가 유즈케이스로 승격되지 않는다.", "한 Y 유즈케이스에 프로세스가 과도하게 몰릴 정도로 넓으면 고객·운영자 목표 기준으로 분리한다."),
            customer_tasks,
        ),
        stage_contract(
            "state",
            "state",
            "업무 가능 여부와 후속 처리 기준",
            "액터와 유즈케이스 관계에서 상태를 도출하고, 전이 이벤트는 승인된 유즈케이스 흐름에서 발생한 상태 변화 업무 사건으로 둔다.",
            ("기능명, 프로세스명, 내부 처리 단계명을 전이 이벤트로 쓰지 않는다.", "BSS 회신이나 기간 만료는 상태 변화 사건일 때만 event로 쓰고 상세 조건은 criteria에 둔다.", "화면 로딩이나 안내 노출을 상태로 만들지 않는다."),
            ("process",),
            ("상태 전이의 현재/다음 상태는 상태 목록에 존재한다.", "event는 상태를 바꾸는 업무 사건이고 usecase_ids는 승인된 유즈케이스 ID다."),
            bss_points,
        ),
        stage_contract(
            "process",
            "process",
            "유즈케이스 완료 절차",
            "상위 유즈케이스를 시작, 판단, 입력/선택, 인증/동의, 요청/반영, 결과 안내 같은 업무 전환점으로 분해한다.",
            ("프로세스를 조회·검증·저장 같은 기능명 나열로 쓰지 않는다.", "관련 기능과 정책은 후속 장 전에는 예측해 쓰지 않는다."),
            ("functions", "policies"),
            ("process_target=Y 유즈케이스는 실제 판단·처리·결과 경계가 드러난다.", "프로세스 설명에는 시작점, 판단, 예외 또는 완료 기준이 드러난다.", "한 Y 유즈케이스에 8개 이상 프로세스가 필요하면 유즈케이스가 너무 넓은지 재검토한다.", "개수 맞추기용 유사 프로세스를 만들지 않는다."),
        ),
        stage_contract(
            "functions",
            "function",
            "프로세스 수행 처리 역량",
            "프로세스를 수행하는 조회, 검증, 산정, 저장, 알림, 연동, 이력 같은 처리 역량으로 묶는다.",
            ("기능을 프로세스명 1:1 복사로 만들지 않는다.", "정책값을 기능 설명에 길게 쓰지 않는다."),
            ("function_detail", "policies"),
            ("공통 기능은 하나의 기능 ID를 여러 process_ids에 재사용한다.", "details는 짧은 하위 처리명이다."),
        ),
        stage_contract(
            "function_detail",
            "function_detail",
            "기능 하위 처리 구성",
            "Full 버전에서 기능의 입력, 처리 로직, 출력, 실패·예외, 세부 기능 구성을 구현 검토 가능한 수준으로 확장한다.",
            ("새 유즈케이스나 프로세스를 만들지 않는다.", "정책값을 직접 확정하지 않고 관련 정책으로 연결한다."),
            ("policies",),
            ("sub_functions는 기능 아래 하위 처리명이다.", "처리 로직은 상태, 액션, 결과 구분을 가진다."),
        ),
        stage_contract(
            "policies",
            "policy_group/policy_item",
            "기능 동작 판단값",
            "프로세스와 기능이 실제 동작하기 위해 결정해야 하는 값·조건·허용 범위·제한 기준을 정책 그룹과 항목으로 선언한다.",
            ("정책을 프로세스 설명이나 기능 설명으로 쓰지 않는다.", "정책 상세에 process_id를 직접 넣지 않는다."),
            ("final_check",),
            ("정책 그룹은 판단 영역이고 정책 항목은 하나의 값·조건 단위다.", "정책 내용에 실제 값, 조건, 우선순위, 예외, 고지, 이력 기준 중 하나 이상이 있다."),
            policy_points,
        ),
        stage_contract(
            "final_check",
            "quality_gate",
            "계층 정합성 제출 점검",
            "유즈케이스 → 프로세스 → 기능 → 세부 기능 구성과 프로세스 → 정책 → 정책 항목의 연결을 최종 확인한다.",
            ("단순 HTML 외형만 점검하지 않는다.", "점검 결과 장을 본문에 새로 추가하지 않는다."),
            (),
            ("계층 입자도, 연결성, 정책 구체성, 근거 추적성을 모두 점검한다.",),
        ),
    ]


def stage_contract(
    stage: str,
    layer: str,
    write_as: str,
    granularity: str,
    do_not_write_as: Sequence[str],
    handoff_to: Sequence[str],
    acceptance_checks: Sequence[str],
    topic_axes: Sequence[str] = (),
) -> dict:
    return {
        "stage": stage,
        "layer": layer,
        "write_as": write_as,
        "granularity": granularity,
        "do_not_write_as": list(do_not_write_as),
        "handoff_to": list(handoff_to),
        "acceptance_checks": list(acceptance_checks),
        "topic_axes": list(topic_axes)[:8],
    }


def architecture_quality_gates() -> list[dict]:
    return [
        {"scope": "usecases", "check": "절차·기능 수준 행위가 독립 유즈케이스로 올라오지 않는다."},
        {"scope": "state", "check": "상태 전이 event는 업무 사건이고 추적성은 승인된 usecase_ids로 확인된다."},
        {"scope": "process", "check": "사람 액터 Y 유즈케이스가 1개 프로세스로만 끝나면 유즈케이스 입자도 또는 프로세스 경계를 재점검한다."},
        {"scope": "functions", "check": "모든 프로세스가 기능 1개씩만 갖는 1:1 구조가 아니다."},
        {"scope": "policies", "check": "정책 항목은 실제 기능 동작값·조건·제한 기준 단위다."},
        {"scope": "final_check", "check": "두 계층 체인의 연결 끊김과 입자도 오류를 확인한다."},
    ]


def architecture_evidence_gaps(authoring_blueprint: Mapping[str, object]) -> list[dict]:
    gaps = []
    source_gaps = authoring_blueprint.get("evidence_gaps", [])
    if isinstance(source_gaps, list):
        for gap in source_gaps[:8]:
            if not isinstance(gap, Mapping):
                continue
            gaps.append(
                {
                    "stage": str(gap.get("kind", "blueprint")),
                    "gap": str(gap.get("title", "")),
                    "handling": str(gap.get("detail", ""))[:220],
                }
            )
    return gaps


def merge_architecture_contract(base: Mapping[str, object], result: Mapping[str, object]) -> dict:
    merged = dict(base)
    for key in (
        "summary",
        "blueprint_phases",
        "hierarchy_chains",
        "hierarchy_skeleton",
        "stage_contracts",
        "first_draft_quality_plan",
        "quality_gates",
        "evidence_gaps",
    ):
        value = result.get(key)
        if value:
            merged[key] = value
    merged["version"] = str(base.get("version", "architecture-v1"))
    merged["agent"] = "Blueprint Architect Agent"
    merged["llm_enhanced"] = True
    merged["stage_contracts"] = ensure_stage_contracts(merged.get("stage_contracts", []), base.get("stage_contracts", []))
    merged["hierarchy_skeleton"] = preserve_requirement_derived_candidates(
        merged.get("hierarchy_skeleton", {}),
        base.get("hierarchy_skeleton", {}),
    )
    return merged


def preserve_requirement_derived_candidates(candidate: object, fallback: object) -> object:
    if not isinstance(candidate, Mapping) or not isinstance(fallback, Mapping):
        return candidate
    if candidate.get("requirement_derived_candidates"):
        return candidate
    fallback_rows = fallback.get("requirement_derived_candidates", [])
    if not fallback_rows:
        return candidate
    merged = dict(candidate)
    merged["requirement_derived_candidates"] = fallback_rows
    return merged


def ensure_stage_contracts(candidate: object, fallback: object) -> list[dict]:
    rows = [dict(item) for item in candidate if isinstance(item, Mapping)] if isinstance(candidate, list) else []
    fallback_rows = [dict(item) for item in fallback if isinstance(item, Mapping)] if isinstance(fallback, list) else []
    by_stage = {str(item.get("stage", "")): item for item in rows}
    for item in fallback_rows:
        stage = str(item.get("stage", ""))
        if stage and stage not in by_stage:
            rows.append(item)
    return rows


def compact_contract(contract: Mapping[str, object]) -> dict:
    return {
        "summary": contract.get("summary", ""),
        "blueprint_phases": compact_object(contract.get("blueprint_phases", []), list_limit=6, string_limit=180),
        "hierarchy_chains": compact_object(contract.get("hierarchy_chains", []), list_limit=4, string_limit=220),
        "architecture_evidence_pack": compact_architecture_evidence_pack(contract.get("architecture_evidence_pack", {})),
        "hierarchy_skeleton": compact_object(contract.get("hierarchy_skeleton", {}), list_limit=6, string_limit=140),
        "core_design_map": compact_object(contract.get("core_design_map", {}), list_limit=6, string_limit=140),
        "stage_contracts": compact_object(contract.get("stage_contracts", []), list_limit=12, string_limit=180),
        "first_draft_quality_plan": compact_first_draft_quality_plan(contract.get("first_draft_quality_plan", {})),
        "quality_gates": compact_object(contract.get("quality_gates", []), list_limit=10, string_limit=180),
    }


def compact_architecture_evidence_pack(pack: object) -> dict:
    if not isinstance(pack, Mapping):
        return {}
    cards = pack.get("cards", [])
    return {
        "selection_rule": compact_string(pack.get("selection_rule", ""), 220),
        "stage_card_ids": compact_object(pack.get("stage_card_ids", {}), list_limit=8, string_limit=80),
        "cards": [
            {
                "id": compact_string(item.get("id", ""), 80),
                "kind": compact_string(item.get("kind", ""), 40),
                "authority_score": item.get("authority_score", 0),
                "source": compact_string(item.get("source", ""), 100),
                "title": compact_string(item.get("title", ""), 120),
                "summary": compact_string(item.get("summary", ""), 160),
                "signals": compact_list(list_values(item.get("signals")), 3),
                "evidence": compact_list(list_values(item.get("evidence")), 1),
                "stages": compact_list(list_values(item.get("stages")), 4),
            }
            for item in cards[:6]
            if isinstance(item, Mapping)
        ],
        "stats": compact_object(pack.get("stats", {}), list_limit=8, string_limit=80),
    }


def compact_blueprint(blueprint: Mapping[str, object]) -> dict:
    return {
        "meta": compact_object(blueprint.get("meta", {}), list_limit=6, string_limit=120),
        "source_profile": compact_object(blueprint.get("source_profile", {}), list_limit=8, string_limit=140),
        "document_strategy": compact_object(blueprint.get("document_strategy", {}), list_limit=8, string_limit=180),
        "analysis_signals": compact_analysis_signals(blueprint.get("analysis_signals", {}), limit=4),
        "coverage_matrix": compact_coverage_matrix(
            blueprint.get("coverage_matrix", [])
            if isinstance(blueprint.get("coverage_matrix"), list)
            else [],
            limit=6,
        ),
        "requirement_hierarchy_rule": compact_string(blueprint.get("requirement_hierarchy_rule", ""), 260),
        "requirement_hierarchy_plan": compact_requirement_derived_candidates(
            blueprint.get("requirement_hierarchy_plan", [])
            if isinstance(blueprint.get("requirement_hierarchy_plan", []), list)
            else [],
            limit=8,
        ),
        "evidence_gaps": compact_evidence_gaps(
            blueprint.get("evidence_gaps", [])
            if isinstance(blueprint.get("evidence_gaps"), list)
            else [],
            limit=8,
        ),
        "chapter_blueprints": [
            compact_chapter_blueprint(item)
            for item in (
                blueprint.get("chapter_blueprints", [])
                if isinstance(blueprint.get("chapter_blueprints", []), list)
                else []
            )[:12]
            if isinstance(item, Mapping)
        ],
    }


def compact_learning(learning: Mapping[str, object]) -> dict:
    return {
        "learning_summary": learning.get("learning_summary", ""),
        "scope_boundary": learning.get("scope_boundary", {}),
        "customer_tasks": list_values(learning.get("customer_tasks"))[:12],
        "bss_implications": list_values(learning.get("bss_implications"))[:12],
        "policy_risks": list_values(learning.get("policy_risks"))[:12],
    }


def list_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def compact_analysis_signals(signals: object, *, limit: int = 8) -> dict:
    if not isinstance(signals, Mapping):
        return {}
    priority_keys = (
        "customer_tasks",
        "core_customer_jobs",
        "policy_decision_points",
        "bss_touchpoints",
        "requirement_implications",
        "voc_pain_points",
        "ia_flow_points",
        "exception_points",
        "operation_points",
        "data_log_points",
        "actor_candidates",
        "usecase_candidates",
        "state_candidates",
        "process_candidates",
        "function_candidates",
        "policy_candidates",
        "privacy_compliance_points",
        "benchmark_points",
    )
    compacted: dict[str, object] = {}
    for key in priority_keys:
        if key not in signals:
            continue
        values = compact_list(list_values(signals.get(key)), limit)
        if values:
            compacted[key] = values
    for key, value in signals.items():
        if key in compacted or key in priority_keys:
            continue
        if isinstance(value, (int, float, bool)):
            compacted[str(key)] = value
        elif isinstance(value, str) and value.strip():
            compacted[str(key)] = compact_string(value, 160)
    return compacted


def compact_coverage_matrix(rows: Sequence[object], *, limit: int = 12) -> list[dict]:
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "requirement_id": compact_string(row.get("requirement_id", ""), 80),
                "title": compact_string(row.get("title", ""), 120),
                "target_stages": compact_list(list_values(row.get("target_stages")), 10),
                "evidence_ids": compact_list(list_values(row.get("evidence_ids")), 6),
            }
        )
        if len(result) >= limit:
            break
    return result


def compact_evidence_gaps(rows: Sequence[object], *, limit: int = 8) -> list[dict]:
    result: list[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        result.append(
            {
                "kind": compact_string(row.get("kind", ""), 60),
                "title": compact_string(row.get("title", ""), 120),
                "detail": compact_string(row.get("detail", ""), 220),
            }
        )
        if len(result) >= limit:
            break
    return result


def compact_chapter_blueprint(item: Mapping[str, object]) -> dict:
    raw_plan = item.get("requirement_hierarchy_plan", [])
    requirement_plan = raw_plan if isinstance(raw_plan, list) else []
    return {
        "stage": compact_string(item.get("stage", ""), 60),
        "focus": compact_string(item.get("focus", ""), 120),
        "must_cover": compact_list(list_values(item.get("must_cover")), 3),
        "target_requirement_ids": compact_list(list_values(item.get("target_requirement_ids")), 6),
        "evidence_ids": compact_list(list_values(item.get("evidence_ids")), 3),
        "requirement_hierarchy_plan": compact_requirement_derived_candidates(requirement_plan, limit=1),
        "analysis_focus": compact_analysis_signals(item.get("analysis_focus", {}), limit=2),
    }


def compact_list(values: Sequence[str], limit: int) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:120])
        if len(result) >= limit:
            break
    return result


def compact_string(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def compact_object(value: object, *, list_limit: int = 8, string_limit: int = 160, depth: int = 4) -> object:
    if depth <= 0:
        return compact_string(value, string_limit)
    if isinstance(value, Mapping):
        compacted: dict[str, object] = {}
        for index, (key, nested) in enumerate(value.items()):
            if index >= list_limit:
                break
            compacted[str(key)] = compact_object(
                nested,
                list_limit=list_limit,
                string_limit=string_limit,
                depth=depth - 1,
            )
        return compacted
    if isinstance(value, (list, tuple)):
        return [
            compact_object(item, list_limit=list_limit, string_limit=string_limit, depth=depth - 1)
            for item in list(value)[:list_limit]
        ]
    if isinstance(value, str):
        return compact_string(value, string_limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return compact_string(value, string_limit)


def architecture_contract_schema() -> dict:
    string_array = {"type": "array", "items": {"type": "string"}, "maxItems": 12}
    chain_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "path", "principle", "granularity_rule"],
        "properties": {
            "name": {"type": "string"},
            "path": string_array,
            "principle": {"type": "string"},
            "granularity_rule": {"type": "string"},
        },
    }
    phase_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["phase", "purpose", "inputs", "outputs", "quality_gate"],
        "properties": {
            "phase": {"type": "string"},
            "purpose": {"type": "string"},
            "inputs": string_array,
            "outputs": string_array,
            "quality_gate": {"type": "string"},
        },
    }
    stage_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "layer", "write_as", "granularity", "do_not_write_as", "handoff_to", "acceptance_checks", "topic_axes"],
        "properties": {
            "stage": {"type": "string"},
            "layer": {"type": "string"},
            "write_as": {"type": "string"},
            "granularity": {"type": "string"},
            "do_not_write_as": string_array,
            "handoff_to": string_array,
            "acceptance_checks": string_array,
            "topic_axes": string_array,
        },
    }
    gate_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["scope", "check"],
        "properties": {"scope": {"type": "string"}, "check": {"type": "string"}},
    }
    gap_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "gap", "handling"],
        "properties": {
            "stage": {"type": "string"},
            "gap": {"type": "string"},
            "handling": {"type": "string"},
        },
    }
    first_draft_stage_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["stage", "before_write", "must_produce", "self_check", "reject_if", "topic_axes"],
        "properties": {
            "stage": {"type": "string"},
            "before_write": {"type": "string"},
            "must_produce": {"type": "string"},
            "self_check": {"type": "string"},
            "reject_if": {"type": "string"},
            "topic_axes": string_array,
        },
    }
    first_draft_plan_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["purpose", "stage_checks", "handoff_checks", "token_efficiency_rule"],
        "properties": {
            "purpose": {"type": "string"},
            "stage_checks": {"type": "array", "items": first_draft_stage_schema, "maxItems": 12},
            "handoff_checks": string_array,
            "token_efficiency_rule": {"type": "string"},
        },
    }
    actor_candidate_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "role", "include_reason", "not_actor_examples", "evidence_ids"],
        "properties": {
            "name": {"type": "string"},
            "role": {"type": "string"},
            "include_reason": {"type": "string"},
            "not_actor_examples": string_array,
            "evidence_ids": string_array,
        },
    }
    usecase_group_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["actor", "goal", "process_target", "process_pattern", "function_axes", "policy_axes", "evidence_ids"],
        "properties": {
            "actor": {"type": "string"},
            "goal": {"type": "string"},
            "process_target": {"type": "string", "enum": ["Y", "N"]},
            "process_pattern": string_array,
            "function_axes": string_array,
            "policy_axes": string_array,
            "evidence_ids": string_array,
        },
    }
    process_pattern_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["usecase_type", "steps", "state_touchpoints", "bss_touchpoints", "evidence_ids"],
        "properties": {
            "usecase_type": {"type": "string"},
            "steps": string_array,
            "state_touchpoints": string_array,
            "bss_touchpoints": string_array,
            "evidence_ids": string_array,
        },
    }
    function_capability_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "capability_type", "detail_granularity", "reuse_rule", "evidence_ids"],
        "properties": {
            "name": {"type": "string"},
            "capability_type": {"type": "string"},
            "detail_granularity": string_array,
            "reuse_rule": {"type": "string"},
            "evidence_ids": string_array,
        },
    }
    policy_taxonomy_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["policy_group", "derived_from", "policy_items", "value_examples", "evidence_ids"],
        "properties": {
            "policy_group": {"type": "string"},
            "derived_from": string_array,
            "policy_items": string_array,
            "value_examples": string_array,
            "evidence_ids": string_array,
        },
    }
    skeleton_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["actor_candidates", "usecase_groups", "process_patterns", "function_capabilities", "policy_taxonomy", "handoff_rules"],
        "properties": {
            "actor_candidates": {"type": "array", "items": actor_candidate_schema, "maxItems": 8},
            "usecase_groups": {"type": "array", "items": usecase_group_schema, "maxItems": 10},
            "process_patterns": {"type": "array", "items": process_pattern_schema, "maxItems": 8},
            "function_capabilities": {"type": "array", "items": function_capability_schema, "maxItems": 10},
            "policy_taxonomy": {"type": "array", "items": policy_taxonomy_schema, "maxItems": 10},
            "handoff_rules": string_array,
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "blueprint_phases",
            "hierarchy_chains",
            "hierarchy_skeleton",
            "stage_contracts",
            "first_draft_quality_plan",
            "quality_gates",
            "evidence_gaps",
        ],
        "properties": {
            "summary": {"type": "string"},
            "blueprint_phases": {"type": "array", "items": phase_schema, "maxItems": 2},
            "hierarchy_chains": {"type": "array", "items": chain_schema, "maxItems": 4},
            "hierarchy_skeleton": skeleton_schema,
            "stage_contracts": {"type": "array", "items": stage_schema, "maxItems": 12},
            "first_draft_quality_plan": first_draft_plan_schema,
            "quality_gates": {"type": "array", "items": gate_schema, "maxItems": 12},
            "evidence_gaps": {"type": "array", "items": gap_schema, "maxItems": 12},
        },
    }
