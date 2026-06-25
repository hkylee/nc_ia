"""Authoring blueprint builder for evidence-grounded NC policy documents.

The blueprint is the contract between collected source material and chapter
writers. It prevents agents from filling documents with generic consulting
language by making requirements, analysis signals, and evidence gaps explicit
before any chapter is written.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Iterable, List, Mapping, Sequence

try:
    from document_density import build_density_profile, density_prompt_contract
    from evidence_store import EvidenceStore, evidence_authority_score_for_values, evidence_authority_tier_for_authority, evidence_source_authority_for_values
except ImportError:  # pragma: no cover - package import fallback.
    from .document_density import build_density_profile, density_prompt_contract
    from .evidence_store import EvidenceStore, evidence_authority_score_for_values, evidence_authority_tier_for_authority, evidence_source_authority_for_values


STAGE_ORDER = (
    "overview",
    "terms",
    "actors",
    "usecases",
    "usecase_diagram",
    "state",
    "process",
    "functions",
    "policies",
    "process_detail",
    "function_detail",
    "terms_refinement",
    "final_check",
)


STAGE_GUIDES = {
    "overview": {
        "focus": "요구사항 4depth 기준으로 대상 업무, 포함/제외 범위, 후속 상세화 영역을 고정한다.",
        "must_cover": ("대상 업무", "대상 채널", "대상 고객", "포함 범위", "제외 범위", "후속 상세화"),
    },
    "terms": {
        "focus": "요구사항과 분석자료에서 반복되는 상태, 권한, 인증, 데이터, 정책 판단 용어를 표준화한다.",
        "must_cover": ("상태 용어", "권한/인증 용어", "정책 판단값", "데이터/이력 용어"),
    },
    "actors": {
        "focus": "요구사항을 수행하거나 결과를 생성하는 독립 책임 주체만 액터로 정의한다.",
        "must_cover": ("고객", "운영자", "BSS/연계 시스템", "외부기관 또는 AI 시스템"),
    },
    "usecases": {
        "focus": "고객 행위, VoC Pain Point, 업무 Trigger를 절차 단계가 아니라 고객 완결 목적 단위 유즈케이스로 재구성한다.",
        "must_cover": ("고객 완결 업무", "운영자 관리 행위", "시스템 보조 처리", "프로세스 정의 대상 판단", "절차 단계 과분해 방지"),
    },
    "usecase_diagram": {
        "focus": "액터와 유즈케이스 연결을 누락 없이 표현하고 UI 이동 단계는 제외한다.",
        "must_cover": ("모든 액터 연결", "모든 유즈케이스 등장", "시스템 보조 처리 구분"),
    },
    "state": {
        "focus": "요구사항의 가능/제한/실패/완료/운영 확인 조건을 상태와 전이로 정의한다.",
        "must_cover": ("정상 상태", "제한 상태", "실패/보류 상태", "운영 검토 상태", "완료 상태"),
    },
    "process": {
        "focus": "유즈케이스를 시작, 판단, 입력/선택, 인증/동의, 처리 요청, 결과 안내 흐름으로 분해한다.",
        "must_cover": ("시작점", "조건 판단", "BSS/연계 처리", "예외 흐름", "완료 안내"),
    },
    "functions": {
        "focus": "프로세스 수행에 필요한 조회, 검증, 산정, 저장, 알림, 연동 기능을 정의한다.",
        "must_cover": ("조회", "검증", "산정", "저장/이력", "알림/고지", "연동"),
    },
    "policies": {
        "focus": "SKT가 결정해야 하는 판단값, 조건, 허용/제한, 예외, 고지, 이력 저장 기준을 정책으로 분리한다.",
        "must_cover": ("기능 동작값", "허용 목록", "횟수", "시간", "채널", "제한 조건", "예외 기준", "고객 고지", "이력 저장"),
    },
    "process_detail": {
        "focus": "Full 버전에서 각 프로세스의 진입 조건, 종료 조건, 선행·후행 관계, 관련 기능·정책 연결을 상세화한다.",
        "must_cover": ("진입 조건", "종료 조건", "선행 프로세스", "후행 프로세스", "관련 기능", "관련 정책"),
    },
    "function_detail": {
        "focus": "Full 버전에서 각 기능의 입력, 처리 로직, 출력, 실패·예외, 관련 정책을 상세화한다.",
        "must_cover": ("입력 정보", "처리 로직", "세부 기능 구성", "출력 정보", "실패·예외 케이스", "관련 정책"),
    },
    "terms_refinement": {
        "focus": "기능과 정책까지 작성된 전체 문서를 검토해 주요 용어 누락을 보강한다.",
        "must_cover": ("상태 용어", "인증/동의", "제한/예외", "고객 고지", "이력 저장", "BSS 연계"),
    },
    "final_check": {
        "focus": "요구사항 커버리지, 근거 추적성, 유즈케이스-프로세스-기능-정책 연결성을 최종 점검한다.",
        "must_cover": ("요구사항 반영", "Evidence Gap", "연결성", "정책 구체성", "BSS 포함성"),
    },
}


def build_authoring_blueprint(
    *,
    ctx: object,
    evidence_store: EvidenceStore,
    learning: Mapping[str, object],
    guideline: Mapping[str, object],
) -> dict:
    requirements = list(getattr(ctx, "requirements", ()) or ())
    references = list(getattr(ctx, "references", ()) or ())
    requirement_cards = build_requirement_cards(requirements)
    reference_cards = build_reference_cards(references)
    density_profile = build_density_profile(
        ctx,
        requirement_items=requirement_cards,
        requirements=requirements,
        references=references,
    )
    analysis_signals = build_analysis_signals(ctx, requirement_cards, reference_cards, learning)
    evidence_gaps = build_blueprint_evidence_gaps(requirement_cards, reference_cards, analysis_signals)
    coverage_matrix = build_requirement_coverage_matrix(requirement_cards)
    requirement_hierarchy_plan = build_requirement_hierarchy_plan(requirement_cards)
    document_strategy = build_document_strategy(ctx, requirement_cards, analysis_signals, requirement_hierarchy_plan, learning)
    source_fingerprint = blueprint_source_fingerprint(requirement_cards, reference_cards, learning, guideline)
    chapter_blueprints = [
        build_stage_blueprint(
            stage,
            ctx,
            evidence_store,
            requirement_cards,
            analysis_signals,
            coverage_matrix,
            requirement_hierarchy_plan,
        )
        for stage in STAGE_ORDER
    ]
    return {
        "version": "v1",
        "rule": (
            "정책서 본문은 이 Authoring Blueprint의 요구사항, 분석 신호, 근거를 우선 반영한다. "
            "요구사항은 상세 요구사항명과 상세 요구사항 설명을 기준으로 해석하고, 요구사항 ID는 추적·커버리지 확인용으로만 사용한다. "
            "근거 없는 일반론은 작성하지 않고 evidence_gap으로 남긴다. "
            "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다. "
            "하위 순위 근거가 상위 순위 근거와 상충하면 상위 근거를 우선하고 상충되는 하위 근거는 폐기한다. "
            "사전 주제 Knowledge Pack의 후보는 작성 가설의 출발점일 뿐이며, 현재 주제의 요구사항·첨부근거·계층 연결로 검증된 경우에만 채택한다."
        ),
        "meta": {
            "topic": getattr(ctx, "topic", ""),
            "business_code": getattr(ctx, "business_code", ""),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "requirements_count": len(requirement_cards),
            "references_count": len(reference_cards),
            "evidence_store": evidence_store.summary(),
            "template_type": getattr(ctx, "template_type", ""),
            "density_profile": density_profile.to_dict(),
            "source_fingerprint": source_fingerprint,
        },
        "density_profile": density_prompt_contract(density_profile),
        "knowledge_strategy": {
            "mode": "RAG + CAG hybrid",
            "rag": (
                "Evidence Store와 Context Assembler가 장별로 필요한 요구사항, 참고자료, 샘플 근거를 검색해 제공한다."
            ),
            "cag": (
                "Topic Learning과 Authoring Blueprint는 검색된 근거를 압축한 작성 기준으로 캐시되어 장별 Agent의 공통 계약으로 쓰인다."
            ),
            "refresh_rule": (
                "요구사항, 참고자료 요약, 학습 결과, 템플릿/샘플 기준이 바뀌면 source_fingerprint가 바뀌며 Blueprint를 다시 생성해야 한다."
            ),
            "quality_guard": (
                "Blueprint는 확정 정답이 아니라 근거 기반 작성 가설이다. 장별 Context Pack과 Inspector가 근거 누락, 일반론, 하위 근거와 상위 근거의 충돌을 다시 검증한다."
            ),
            "source_authority": (
                "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다."
            ),
            "candidate_guard": (
                "Knowledge Pack 후보는 정답이 아니며, Writer는 요구사항·첨부근거·현재 프로세스/기능/정책 연결이 약한 후보를 제거해야 한다."
            ),
        },
        "source_profile": {
            "requirement_depth4": sorted({card["depth4"] for card in requirement_cards if card.get("depth4")}),
            "reference_categories": sorted({card["category"] for card in reference_cards if card.get("category")}),
            "reference_sources": [card["source_name"] for card in reference_cards[:40]],
            "guideline_rules": list(guideline.get("common_rules", []) or [])[:8] if isinstance(guideline, Mapping) else [],
        },
        "document_strategy": document_strategy,
        "requirement_hierarchy_rule": (
            "요구사항은 본문에 그대로 복사하지 않는다. 상세 요구사항명과 상세 요구사항 설명을 먼저 액터 후보, 유즈케이스 후보, "
            "프로세스 후보, 기능 역량, 정책 판단축으로 해석한 뒤 현재 장의 계층에 맞는 항목만 작성한다."
            " 요구사항 ID와 우선순위는 추적용 메타데이터이며 작성 의미 판단에 사용하지 않는다."
        ),
        "analysis_signals": analysis_signals,
        "requirement_cards": requirement_cards,
        "requirement_hierarchy_plan": requirement_hierarchy_plan,
        "reference_cards": reference_cards[:80],
        "chapter_blueprints": chapter_blueprints,
        "coverage_matrix": coverage_matrix,
        "evidence_gaps": evidence_gaps,
    }


def blueprint_source_fingerprint(
    requirement_cards: Sequence[Mapping[str, object]],
    reference_cards: Sequence[Mapping[str, object]],
    learning: Mapping[str, object],
    guideline: Mapping[str, object],
) -> str:
    payload = {
        "requirements": [
            {
                "id": card.get("id", ""),
                "title": card.get("title", ""),
                "summary": card.get("summary", ""),
                "source_excerpt": card.get("source_excerpt", ""),
                "target_stages": card.get("target_stages", []),
            }
            for card in requirement_cards
        ],
        "references": [
            {
                "source_name": card.get("source_name", ""),
                "category": card.get("category", ""),
                "source_authority": card.get("source_authority", ""),
                "authority_score": card.get("authority_score", 0),
                "score": card.get("score", 0),
                "summary": card.get("summary", ""),
                "read_scope": card.get("read_scope", ""),
            }
            for card in reference_cards[:120]
        ],
        "learning": {
            "topic_understanding": learning.get("topic_understanding", ""),
            "customer_tasks": learning.get("customer_tasks", []),
            "policy_risks": learning.get("policy_risks", []),
            "chapter_focus": learning.get("chapter_focus", {}),
            "tk_core_orientations": (
                learning.get("prelearned_knowledge", {}).get("tk_core_orientations", [])
                if isinstance(learning.get("prelearned_knowledge", {}), Mapping)
                else []
            ),
            "tk_process_function_guidance": (
                learning.get("prelearned_knowledge", {}).get("tk_process_function_guidance", [])
                if isinstance(learning.get("prelearned_knowledge", {}), Mapping)
                else []
            ),
            "topic_direction_milestone": (
                learning.get("prelearned_knowledge", {}).get("topic_direction_milestone", [])
                if isinstance(learning.get("prelearned_knowledge", {}), Mapping)
                else []
            ),
            "topic_direction_strategy": (
                learning.get("prelearned_knowledge", {}).get("topic_direction_strategy", [])
                if isinstance(learning.get("prelearned_knowledge", {}), Mapping)
                else []
            ),
            "topic_direction_agent_guidance": (
                learning.get("prelearned_knowledge", {}).get("topic_direction_agent_guidance", [])
                if isinstance(learning.get("prelearned_knowledge", {}), Mapping)
                else []
            ),
        },
        "guideline": {
            "common_rules": list(guideline.get("common_rules", []) or [])[:12]
            if isinstance(guideline, Mapping)
            else [],
            "sample_baseline": guideline.get("sample_baseline", {}) if isinstance(guideline, Mapping) else {},
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_requirement_cards(requirements: Sequence[object]) -> List[dict]:
    cards: List[dict] = []
    used_ids: set[str] = set()
    for index, item in enumerate(requirements, 1):
        detail_requirement_id = clean_text(getattr(item, "detail_id", ""))
        raw_requirement_id = clean_text(getattr(item, "requirement_id", ""))
        source_number = clean_text(getattr(item, "source_number", ""))
        base_requirement_id = (
            detail_requirement_id
            or (raw_requirement_id if meaningful_source_id(raw_requirement_id) else "")
            or source_number
            or f"REQ-{index:03d}"
        )
        requirement_id = unique_card_id(base_requirement_id, source_number, index, used_ids)
        detail_name = clean_text(getattr(item, "detail_name", ""))
        detail_description = clean_text(getattr(item, "detail_description", ""))
        parent_name = clean_text(getattr(item, "parent_name", ""))
        parent_description = clean_text(getattr(item, "parent_description", ""))
        title = detail_name or parent_name or requirement_id
        requirement_body = " ".join(value for value in (parent_description, detail_description) if value)
        summary = compact_text(requirement_body, 420) or title
        source_excerpt = compact_text(
            " ".join(
                value
                for value in (
                    f"상위 요구: {parent_name}" if parent_name else "",
                    parent_description,
                    f"세부 요구: {detail_name}" if detail_name else "",
                    detail_description,
                )
                if value
            ),
            520,
        ) or summary
        text = " ".join((title, summary, clean_text(getattr(item, "requirement_type", ""))))
        cards.append(
            {
                "id": requirement_id,
                "source_number": clean_text(getattr(item, "source_number", "")),
                "depth3": clean_text(getattr(item, "depth3", "")),
                "depth4": clean_text(getattr(item, "depth4", "")),
                "title": compact_text(title, 120),
                "summary": summary,
                "source_excerpt": source_excerpt,
                "requirement_type": clean_text(getattr(item, "requirement_type", "")),
                "required": clean_text(getattr(item, "required", "")),
                "signals": classify_requirement_signals(text),
                "target_stages": classify_requirement_stages(text),
            }
        )
    return cards


def build_document_strategy(
    ctx: object,
    requirement_cards: Sequence[Mapping[str, object]],
    analysis_signals: Mapping[str, object],
    requirement_hierarchy_plan: Sequence[Mapping[str, object]],
    learning: Mapping[str, object],
) -> dict:
    topic = clean_text(getattr(ctx, "topic", "")) or "현재 정책서"
    requirement_titles = unique_limited(
        [row.get("title", "") for row in requirement_hierarchy_plan if row.get("title")],
        3,
        70,
    )
    if requirement_titles:
        topic_definition = (
            f"{topic}에서 {', '.join(requirement_titles)} 등 요구사항을 "
            "고객 과업, 처리 흐름, 기능 범위, 정책 판단 기준으로 재구성한다."
        )
    else:
        topic_definition = first_non_empty(
            compact_list_values((learning.get("scope_boundary", {}) or {}).get("direct_scope", []), 2, 160)
            if isinstance(learning.get("scope_boundary", {}), Mapping)
            else [],
            list_values(analysis_signals.get("topic_learning_summary"))[:1],
            list_values(analysis_signals.get("requirement_implications"))[:1],
            [f"{topic}에서 고객 업무 완료와 정책 판단 기준을 구체화한다."],
        )
    direct_jobs = unique_limited(
        [row.get("usecase_candidate", "") for row in requirement_hierarchy_plan if "고객" in list_values(row.get("actor_candidates"))]
        + list_values(analysis_signals.get("customer_tasks")),
        8,
        120,
    )
    tk_core_orientations = unique_limited(list_values(analysis_signals.get("tk_core_orientations")), 8, 140)
    tk_process_function_guidance = unique_limited(
        list_values(analysis_signals.get("tk_process_function_guidance")),
        10,
        160,
    )
    topic_direction_milestone = unique_limited(list_values(analysis_signals.get("topic_direction_milestone")), 3, 160)
    topic_direction_strategy = unique_limited(list_values(analysis_signals.get("topic_direction_strategy")), 3, 160)
    topic_direction_agent_guidance = unique_limited(list_values(analysis_signals.get("topic_direction_agent_guidance")), 5, 160)
    condition_jobs = unique_limited(
        [
            f"{row.get('title', '')}: {', '.join(list_values(row.get('policy_decision_axes'))[:3])}"
            for row in requirement_hierarchy_plan
            if list_values(row.get("policy_decision_axes"))
        ]
        + list_values(analysis_signals.get("policy_decision_points")),
        8,
        140,
    )
    recovery_jobs = unique_limited(
        [
            f"{row.get('title', '')}: 실패·제한·보류 시 복구 기준 확인"
            for row in requirement_hierarchy_plan
            if contains_any(" ".join(list_values(row.get("policy_decision_axes")) + [row.get("summary", "")]), EXCEPTION_KEYWORDS)
        ]
        + list_values(analysis_signals.get("exception_points")),
        8,
        140,
    )
    return {
        "topic_definition": topic_definition,
        "topic_direction_milestone": topic_direction_milestone,
        "topic_direction_strategy": topic_direction_strategy,
        "topic_direction_agent_guidance": topic_direction_agent_guidance,
        "tk_core_orientations": tk_core_orientations,
        "tk_process_function_guidance": tk_process_function_guidance,
        "core_customer_jobs": {
            "direct_customer_actions": direct_jobs or [f"고객이 {topic} 업무를 시작하고 결과를 확인한다."],
            "conditions_to_understand": condition_jobs or ["고객이 업무 가능 조건, 제한 조건, 예외 기준을 이해한다."],
            "failure_recovery": recovery_jobs or ["실패, 제한, 보류 시 재시도·상담·후속 처리 기준을 확인한다."],
        },
        "core_policy_questions": [
            "누가 할 수 있는가?",
            "언제 할 수 있는가?",
            "몇 번까지 가능한가?",
            "어떤 조건이면 제한되는가?",
            "실패하면 어떻게 복구하는가?",
            "이력은 어디에 남기는가?",
            "BSS는 어떤 상태를 변경하는가?",
        ],
        "must_include": ["액터", "유즈케이스", "상태 전이", "프로세스", "기능", "정책", "정책 항목"],
        "must_not": [
            "일반 설명",
            "화면 설명 중심",
            "시스템 기준에 따름 같은 빈 정책",
            "근거 없는 인터넷 일반론",
        ],
    }


def build_requirement_hierarchy_plan(requirement_cards: Sequence[Mapping[str, object]]) -> List[dict]:
    """Interpret requirements into hierarchy candidates without copying them into the body.

    This plan is intentionally deterministic and compact. It gives Blueprint,
    Writer, and Inspector a shared starting point for what each requirement
    likely implies, while still letting chapter agents reshape the final policy
    structure according to template/sample constraints.
    """
    rows: List[dict] = []
    for card in requirement_cards:
        title = compact_text(card.get("title", ""), 100)
        summary = compact_text(card.get("summary", ""), 340)
        source_excerpt = compact_text(card.get("source_excerpt", "") or card.get("summary", ""), 360)
        text = " ".join(
            str(card.get(key, ""))
            for key in ("depth3", "depth4", "title", "summary", "source_excerpt", "requirement_type")
        )
        stages = list_values(card.get("target_stages"))
        signals = list_values(card.get("signals"))
        actor_candidates = infer_requirement_actor_candidates(text, stages)
        usecase_candidate = infer_requirement_usecase_candidate(title, text, actor_candidates, stages)
        process_candidate = infer_requirement_process_candidate(title, text, actor_candidates, stages)
        rows.append(
            {
                "requirement_id": card.get("id", ""),
                "source_number": card.get("source_number", ""),
                "title": title,
                "summary": summary,
                "source_excerpt": source_excerpt,
                "actor_candidates": actor_candidates,
                "usecase_candidate": usecase_candidate,
                "process_candidate": process_candidate,
                "function_capabilities": infer_requirement_function_capabilities(text, signals),
                "policy_decision_axes": infer_requirement_policy_axes(text, signals),
                "target_stages": stages,
                "interpretation_rule": "요구사항 문구를 복사하지 않고 정책서 계층 후보로 해석한다.",
            }
        )
    return rows


def first_non_empty(*groups: Sequence[object]) -> str:
    for group in groups:
        for value in group:
            text = clean_text(value)
            if text:
                return text
    return ""


def infer_requirement_actor_candidates(text: str, stages: Sequence[str]) -> List[str]:
    actors: List[str] = []
    if contains_any(text, ("고객", "사용자", "이용자", "회원", "가입자", "고객사")):
        actors.append("고객")
    if contains_any(text, ("운영", "관리", "관리자", "담당자", "검수", "승인", "등록", "배포")):
        actors.append("운영자")
    if contains_any(text, ("BSS", "원장", "시스템", "연계", "검증", "판정", "저장", "응답", "API", "처리")):
        actors.append("BSS/연계 시스템")
    if contains_any(text, ("법정대리인", "보호자")):
        actors.append("법정대리인")
    if contains_any(text, ("대리인",)):
        actors.append("대리인")
    if contains_any(text, ("외부", "기관", "제휴", "인증기관", "본인확인", "PG", "결제사")):
        actors.append("외부기관/제휴사")
    if not actors and any(stage in {"usecases", "process", "functions", "policies"} for stage in stages):
        actors.extend(["고객", "BSS/연계 시스템"])
    return unique_limited(actors, 5, 40)


def infer_requirement_usecase_candidate(
    title: str,
    text: str,
    actor_candidates: Sequence[str],
    stages: Sequence[str],
) -> str:
    base = hierarchy_candidate_base(title, text)
    if "usecases" not in stages and contains_any(text, ("시스템", "BSS", "연계", "검증", "저장", "판정")):
        return compact_text(f"{base} 보조 처리", 90)
    if actor_candidates and actor_candidates[0] == "운영자":
        return compact_text(f"{base} 관리", 90)
    if contains_any(base, ("조회", "검색", "확인", "신청", "변경", "해지", "취소", "납부", "결제", "등록", "관리")):
        return compact_text(base, 90)
    return compact_text(f"{base} 확인 및 처리", 90)


def infer_requirement_process_candidate(
    title: str,
    text: str,
    actor_candidates: Sequence[str],
    stages: Sequence[str],
) -> str:
    base = hierarchy_candidate_base(title, text)
    if "process" not in stages and "process_detail" not in stages:
        return compact_text(f"{base} 반영 절차", 90)
    if actor_candidates and actor_candidates[0] == "운영자":
        return compact_text(f"{base} 운영 처리 흐름", 90)
    if contains_any(text, ("BSS", "원장", "연계", "판정", "검증", "응답")):
        suffix = "연계 처리 흐름" if contains_any(base, ("검증", "판정", "확인")) else "검증·연계 처리 흐름"
        return compact_text(f"{base} {suffix}", 90)
    return compact_text(f"{base} 고객 처리 흐름", 90)


def infer_requirement_function_capabilities(text: str, signals: Sequence[str]) -> List[str]:
    capabilities: List[str] = []
    if contains_any(text, ("조회", "검색", "확인", "목록", "상세", "대상")):
        capabilities.append("대상 정보 조회")
    if contains_any(text, ("인증", "권한", "자격", "조건", "검증", "판정", "동의")):
        capabilities.append("자격 및 조건 검증")
    if contains_any(text, ("산정", "계산", "추천", "정렬", "우선순위", "요금", "혜택", "할인")):
        capabilities.append("값 산정 및 추천")
    if contains_any(text, ("신청", "변경", "해지", "취소", "등록", "저장", "반영", "납부", "결제", "처리")):
        capabilities.append("처리 요청 및 결과 반영")
    if contains_any(text, ("알림", "고지", "안내", "메시지", "결과", "노출")):
        capabilities.append("결과 안내 및 고지")
    if contains_any(text, ("이력", "로그", "보관", "파기", "삭제", "마스킹")) or "data_log" in signals:
        capabilities.append("이력 저장 및 보관")
    if contains_any(text, ("BSS", "연계", "외부", "기관", "원장", "응답", "API")):
        capabilities.append("연계 요청 및 결과 수신")
    if not capabilities:
        capabilities.extend(["업무 대상 확인", "처리 결과 관리"])
    return unique_limited(capabilities, 6, 50)


def infer_requirement_policy_axes(text: str, signals: Sequence[str]) -> List[str]:
    axes: List[str] = []
    if contains_any(text, ("대상", "조건", "기준", "허용", "제한", "필수", "선택", "권한", "자격")):
        axes.append("적용 대상·허용·제한 조건")
    if contains_any(text, ("횟수", "시간", "기간", "유효", "만료", "재시도", "보관")):
        axes.append("횟수·시간·기간 기준")
    if contains_any(text, ("채널", "노출", "고지", "안내", "알림", "메시지")):
        axes.append("채널·고지 기준")
    if contains_any(text, ("예외", "실패", "오류", "장애", "보류", "취소", "불가", "제한")):
        axes.append("예외·실패 처리 기준")
    if contains_any(text, ("우선순위", "추천", "정렬", "랭킹", "개인화")):
        axes.append("우선순위·정렬 기준")
    if contains_any(text, ("개인정보", "동의", "로그", "이력", "저장", "파기", "삭제", "마스킹")) or "data_log" in signals:
        axes.append("동의·이력·보관 기준")
    if contains_any(text, ("요금", "결제", "청구", "납부", "할인", "혜택", "쿠폰", "정산")):
        axes.append("금액·혜택 적용 기준")
    if not axes:
        axes.extend(["적용 대상 기준", "처리 결과 기준"])
    return unique_limited(axes, 6, 60)


def hierarchy_candidate_base(title: str, text: str) -> str:
    base = compact_text(title or text, 70)
    base = re.sub(r"(기능|정책|요구사항|화면|페이지|영역)$", "", base).strip(" -_/·")
    return base or "현재 주제 업무"


def unique_card_id(base_id: str, source_number: str, index: int, used_ids: set[str]) -> str:
    candidate = base_id
    if candidate not in used_ids:
        used_ids.add(candidate)
        return candidate
    suffix = source_number or f"{index:03d}"
    candidate = f"{base_id}-{suffix}"
    serial = 2
    while candidate in used_ids:
        candidate = f"{base_id}-{suffix}-{serial}"
        serial += 1
    used_ids.add(candidate)
    return candidate


def meaningful_source_id(value: object) -> bool:
    text = re.sub(r"[\s._-]+", "", str(value or ""))
    return bool(text and text.casefold() not in {"na", "none", "null"})


def build_reference_cards(references: Sequence[object]) -> List[dict]:
    cards: List[dict] = []
    for index, item in enumerate(references, 1):
        evidence = [compact_text(value, 180) for value in list(getattr(item, "evidence", ()) or ())[:4]]
        signals = [compact_text(value, 120) for value in list(getattr(item, "signals", ()) or ())[:8]]
        source_name = clean_text(getattr(item, "source_name", "")) or f"reference-{index}"
        category = clean_text(getattr(item, "category", "")) or "reference"
        authority = evidence_source_authority_for_values(
            category,
            source_name,
            " ".join([clean_text(getattr(item, "summary", "")), " ".join(signals)]),
        )
        authority_score = evidence_authority_score_for_values(category, source_name, " ".join(signals))
        cards.append(
            {
                "id": f"REF-{safe_key(source_name, index)}",
                "source_name": source_name,
                "source_type": clean_text(getattr(item, "source_type", "")),
                "category": category,
                "source_authority": authority,
                "authority_tier": evidence_authority_tier_for_authority(authority),
                "authority_score": authority_score,
                "source_precedence": source_precedence_for_values(category, source_name, " ".join(signals)),
                "summary": compact_text(getattr(item, "summary", ""), 260),
                "signals": signals,
                "evidence": evidence,
                "score": int(getattr(item, "score", 0) or 0),
                "text_chars": int(getattr(item, "text_chars", 0) or 0),
                "read_scope": clean_text(getattr(item, "read_scope", "")) or "full_document",
            }
        )
    cards.sort(key=lambda item: (item["authority_score"], item["score"], item["text_chars"], item["source_name"]), reverse=True)
    return cards


def source_precedence_for_values(kind: object, source: object, text: object = "") -> str:
    authority = evidence_source_authority_for_values(kind, source, text)
    # Reuse the central wording without constructing a full EvidenceItem here.
    if authority == "authority:attached_requirement":
        return "1순위 근거: 첨부자료, 사내자료, 요구사항을 확정 기준으로 사용한다."
    if authority == "authority:requirement_level_reference":
        return "1순위 근거: 채널 방향성과 TK 과제정의 PDF는 요구사항급 사내 기준으로 사용한다."
    if authority in {"authority:attached_template", "authority:attached_sample", "authority:attached_guideline"}:
        return "1순위 근거: 첨부 템플릿, 샘플, AGENTS.md 기준을 작성 형식과 품질 기준으로 우선한다."
    if authority == "authority:attached_reference":
        return "1순위 근거: 첨부자료와 사내자료를 업무 맥락과 정책 판단 근거로 우선한다."
    if authority == "authority:skt_official_auxiliary":
        return "2순위 보조 근거: SKT 공식 서비스 안내, 약관, 고객지원 페이지는 첨부 근거를 보강할 때만 사용한다."
    if authority == "authority:compliance_reference":
        return "3순위 컴플라이언스 근거: 법령, 규제기관, 개인정보보호위, 방통위 자료는 준수 필요성과 금지선을 확인할 때 사용한다."
    return "4순위 참고 근거: 공개웹 학습 지식은 보조 후보이며, 1순위 근거와 상충하면 폐기한다."


def build_analysis_signals(
    ctx: object,
    requirement_cards: Sequence[Mapping[str, object]],
    reference_cards: Sequence[Mapping[str, object]],
    learning: Mapping[str, object],
) -> dict:
    prelearned = learning.get("prelearned_knowledge", {}) if isinstance(learning, Mapping) else {}
    prelearned_axes = prelearned.get("topic_axes", {}) if isinstance(prelearned, Mapping) else {}
    prelearned_candidates = prelearned.get("candidate_inventory", {}) if isinstance(prelearned, Mapping) else {}
    prelearned_topic_milestone = prelearned.get("topic_direction_milestone", []) if isinstance(prelearned, Mapping) else []
    prelearned_topic_strategy = prelearned.get("topic_direction_strategy", []) if isinstance(prelearned, Mapping) else []
    prelearned_topic_agent_guidance = prelearned.get("topic_direction_agent_guidance", []) if isinstance(prelearned, Mapping) else []
    prelearned_tk_orientations = prelearned.get("tk_core_orientations", []) if isinstance(prelearned, Mapping) else []
    prelearned_tk_process_functions = prelearned.get("tk_process_function_guidance", []) if isinstance(prelearned, Mapping) else []
    texts = requirement_texts(requirement_cards) + reference_texts(reference_cards)
    return {
        "customer_tasks": unique_limited(
            list_values(learning.get("customer_tasks")) + select_texts_by_keywords(texts, CUSTOMER_TASK_KEYWORDS),
            18,
            150,
        ),
        "requirement_implications": unique_limited(
            list_values(learning.get("requirement_implications")) + [card.get("title", "") for card in requirement_cards[:40]],
            24,
            150,
        ),
        "voc_pain_points": unique_limited(
            select_reference_texts(reference_cards, {"voc", "research"}, PAIN_POINT_KEYWORDS),
            18,
            160,
        ),
        "ia_flow_points": unique_limited(
            select_reference_texts(reference_cards, {"ia"}, FLOW_KEYWORDS),
            18,
            160,
        ),
        "bss_touchpoints": unique_limited(
            list_values(learning.get("bss_implications")) + select_texts_by_keywords(texts, BSS_KEYWORDS),
            20,
            160,
        ),
        "policy_decision_points": unique_limited(
            list_values(learning.get("policy_risks")) + select_texts_by_keywords(texts, POLICY_KEYWORDS),
            24,
            160,
        ),
        "exception_points": unique_limited(select_texts_by_keywords(texts, EXCEPTION_KEYWORDS), 18, 160),
        "data_log_points": unique_limited(select_texts_by_keywords(texts, DATA_LOG_KEYWORDS), 18, 160),
        "operation_points": unique_limited(select_texts_by_keywords(texts, OPERATION_KEYWORDS), 18, 160),
        "channel_integration_axes": unique_limited(
            list_values(prelearned_axes.get("channel_axes") if isinstance(prelearned_axes, Mapping) else [])
            + select_reference_texts(reference_cards, {"strategy"}, CHANNEL_INTEGRATION_KEYWORDS),
            18,
            160,
        ),
        "topic_direction_milestone": unique_limited(
            list_values(prelearned_topic_milestone),
            8,
            160,
        ),
        "topic_direction_strategy": unique_limited(
            list_values(prelearned_topic_strategy),
            3,
            160,
        ),
        "topic_direction_agent_guidance": unique_limited(
            list_values(prelearned_topic_agent_guidance),
            5,
            160,
        ),
        "tk_core_orientations": unique_limited(
            [
                point
                for row in prelearned_tk_orientations
                if isinstance(row, Mapping)
                for point in list_values(row.get("core_points"))
            ],
            12,
            150,
        ),
        "tk_process_function_guidance": compact_tk_process_function_guidance_for_signals(
            prelearned_tk_process_functions,
            limit=14,
        ),
        "prelearned_policy_candidates": unique_limited(
            list_values(prelearned_candidates.get("policy_item_candidates") if isinstance(prelearned_candidates, Mapping) else []),
            18,
            160,
        ),
        "prelearned_process_patterns": unique_limited(
            list_values(prelearned_candidates.get("process_patterns") if isinstance(prelearned_candidates, Mapping) else []),
            18,
            160,
        ),
        "topic_learning_summary": compact_text(learning.get("learning_summary", ""), 500),
    }


def compact_tk_process_function_guidance_for_signals(value: object, limit: int = 12) -> List[str]:
    if not isinstance(value, list):
        return []
    rows: List[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        process_name = compact_text(item.get("process_name", ""), 70)
        functions = compact_list_values(item.get("major_functions", []), 4, 60)
        if not process_name and not functions:
            continue
        if functions:
            rows.append(f"{process_name}: {' / '.join(functions)}" if process_name else " / ".join(functions))
        else:
            rows.append(process_name)
    return unique_limited(rows, limit, 160)


def build_stage_blueprint(
    stage: str,
    ctx: object,
    evidence_store: EvidenceStore,
    requirement_cards: Sequence[Mapping[str, object]],
    analysis_signals: Mapping[str, object],
    coverage_matrix: Sequence[Mapping[str, object]],
    requirement_hierarchy_plan: Sequence[Mapping[str, object]],
) -> dict:
    guide = STAGE_GUIDES[stage]
    selected = evidence_store.select(
        stage=stage,
        topic=getattr(ctx, "topic", ""),
        query_terms=stage_query_terms(stage, analysis_signals),
        required_kinds=stage_required_kinds(stage),
        limit=10,
    )
    target_requirements = [
        row["requirement_id"]
        for row in coverage_matrix
        if stage in row.get("target_stages", [])
    ]
    target_requirement_set = set(target_requirements)
    stage_requirement_cards = [
        card
        for card in requirement_cards
        if card.get("id") in target_requirement_set
    ]
    stage_requirement_rows = [
        row
        for row in requirement_hierarchy_plan
        if row.get("requirement_id") in target_requirement_set
        and stage in (row.get("target_stages", []) if isinstance(row.get("target_stages", []), list) else [])
    ]
    return {
        "stage": stage,
        "focus": guide["focus"],
        "must_cover": list(guide["must_cover"]),
        "target_requirement_count": len(target_requirements),
        "target_requirement_ids": target_requirements,
        "selected_requirement_cards": [
            compact_requirement_card(card)
            for card in select_evenly(stage_requirement_cards, 18)
        ],
        "requirement_hierarchy_plan": [
            compact_requirement_hierarchy_row(row)
            for row in select_evenly(stage_requirement_rows, 14)
        ],
        "evidence_ids": [item.id for item in selected],
        "evidence_summaries": [item.to_prompt_dict(max_chars=220) for item in selected[:8]],
        "analysis_focus": stage_analysis_focus(stage, analysis_signals),
        "do_not_write": [
            "요구사항이나 분석 근거 없이 일반론을 새로 만들지 않는다.",
            "API 필드, DB 컬럼, 화면 UI 상세, 오류 코드 전체 목록을 본문 정책으로 쓰지 않는다.",
            "근거가 부족한 정책값은 확정값처럼 쓰지 말고 Evidence Gap으로 남긴다.",
        ],
    }


def stage_blueprint_for_prompt(blueprint: Mapping[str, object], stage: str) -> dict:
    chapters = blueprint.get("chapter_blueprints", []) if isinstance(blueprint, Mapping) else []
    selected = {}
    for chapter in chapters:
        if isinstance(chapter, Mapping) and chapter.get("stage") == stage:
            selected = dict(chapter)
            break
    return {
        "rule": blueprint.get("rule", ""),
        "document_strategy": compact_document_strategy(blueprint.get("document_strategy", {})),
        "requirement_hierarchy_rule": blueprint.get("requirement_hierarchy_rule", ""),
        "density_profile": blueprint.get("density_profile", {}),
        "source_profile": blueprint.get("source_profile", {}),
        "stage_blueprint": selected,
        "architecture_contract": architecture_contract_for_stage(blueprint.get("architecture_contract", {}), stage),
        "blueprint_quality_gate": compact_quality_gate_for_stage(blueprint.get("quality_gate", {}), stage),
        "global_analysis_signals": compact_analysis_signals(blueprint.get("analysis_signals", {}), stage),
        "evidence_gaps": blueprint.get("evidence_gaps", [])[:12] if isinstance(blueprint.get("evidence_gaps"), list) else [],
    }


def compact_blueprint_for_spec(blueprint: Mapping[str, object]) -> dict:
    return {
        "version": blueprint.get("version", ""),
        "rule": blueprint.get("rule", ""),
        "requirement_hierarchy_rule": blueprint.get("requirement_hierarchy_rule", ""),
        "meta": blueprint.get("meta", {}),
        "density_profile": blueprint.get("density_profile", {}),
        "source_profile": blueprint.get("source_profile", {}),
        "document_strategy": compact_document_strategy(blueprint.get("document_strategy", {})),
        "analysis_signals": blueprint.get("analysis_signals", {}),
        "requirement_cards": blueprint.get("requirement_cards", []),
        "requirement_hierarchy_plan": [
            compact_requirement_hierarchy_row(item)
            for item in blueprint.get("requirement_hierarchy_plan", [])
            if isinstance(item, Mapping)
        ][:120],
        "reference_cards": blueprint.get("reference_cards", []),
        "chapter_blueprints": [
            {
                "stage": item.get("stage", ""),
                "focus": item.get("focus", ""),
                "must_cover": item.get("must_cover", []),
                "target_requirement_ids": item.get("target_requirement_ids", []),
                "requirement_hierarchy_plan": item.get("requirement_hierarchy_plan", []),
                "evidence_ids": item.get("evidence_ids", []),
                "analysis_focus": item.get("analysis_focus", {}),
            }
            for item in blueprint.get("chapter_blueprints", [])
            if isinstance(item, Mapping)
        ],
        "coverage_matrix": blueprint.get("coverage_matrix", []),
        "evidence_gaps": blueprint.get("evidence_gaps", []),
        "architecture_contract": compact_architecture_contract(blueprint.get("architecture_contract", {})),
        "quality_gate": compact_quality_gate(blueprint.get("quality_gate", {})),
    }


def architecture_contract_for_stage(contract: object, stage: str) -> dict:
    if not isinstance(contract, Mapping):
        return {}
    stage_contracts = [
        compact_architecture_stage_contract(item)
        for item in contract.get("stage_contracts", [])
        if isinstance(item, Mapping) and item.get("stage") in {stage, "final_check"}
    ]
    quality_gates = [
        {
            "scope": item.get("scope", ""),
            "check": compact_text(item.get("check", ""), 180),
        }
        for item in contract.get("quality_gates", [])
        if isinstance(item, Mapping) and item.get("scope") in {stage, "final_check"}
    ]
    return {
        "agent": contract.get("agent", "Blueprint Architect Agent"),
        "summary": compact_text(contract.get("summary", ""), 240),
        "blueprint_phases": compact_blueprint_phases(contract.get("blueprint_phases", [])),
        "hierarchy_chains": contract.get("hierarchy_chains", [])[:2] if isinstance(contract.get("hierarchy_chains"), list) else [],
        "architecture_evidence_pack": architecture_evidence_pack_for_stage(contract.get("architecture_evidence_pack", {}), stage),
        "hierarchy_skeleton": architecture_skeleton_for_stage(contract.get("hierarchy_skeleton", {}), stage),
        "core_design_map": core_design_map_for_stage(contract.get("core_design_map", {}), stage),
        "stage_contracts": stage_contracts[:4],
        "first_draft_quality_plan": first_draft_quality_plan_for_stage(contract.get("first_draft_quality_plan", {}), stage),
        "quality_gates": quality_gates[:6],
    }


def compact_architecture_contract(contract: object) -> dict:
    if not isinstance(contract, Mapping):
        return {}
    return {
        "version": contract.get("version", ""),
        "agent": contract.get("agent", "Blueprint Architect Agent"),
        "summary": compact_text(contract.get("summary", ""), 260),
        "blueprint_phases": compact_blueprint_phases(contract.get("blueprint_phases", [])),
        "hierarchy_chains": contract.get("hierarchy_chains", [])[:3] if isinstance(contract.get("hierarchy_chains"), list) else [],
        "architecture_evidence_pack": compact_architecture_evidence_pack(contract.get("architecture_evidence_pack", {})),
        "hierarchy_skeleton": compact_architecture_skeleton(contract.get("hierarchy_skeleton", {})),
        "core_design_map": compact_core_design_map(contract.get("core_design_map", {})),
        "first_draft_quality_plan": compact_first_draft_quality_plan(contract.get("first_draft_quality_plan", {})),
        "stage_contracts": [
            compact_architecture_stage_contract(item)
            for item in contract.get("stage_contracts", [])
            if isinstance(item, Mapping)
        ],
        "quality_gates": [
            {"scope": item.get("scope", ""), "check": compact_text(item.get("check", ""), 180)}
            for item in contract.get("quality_gates", [])
            if isinstance(item, Mapping)
        ],
        "evidence_gaps": contract.get("evidence_gaps", [])[:12] if isinstance(contract.get("evidence_gaps"), list) else [],
    }


def compact_blueprint_phases(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [
        {
            "phase": item.get("phase", ""),
            "purpose": compact_text(item.get("purpose", ""), 160),
            "outputs": item.get("outputs", [])[:6] if isinstance(item.get("outputs", []), list) else [],
            "quality_gate": compact_text(item.get("quality_gate", ""), 180),
        }
        for item in value[:2]
        if isinstance(item, Mapping)
    ]


def compact_document_strategy(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    jobs = value.get("core_customer_jobs", {})
    jobs = jobs if isinstance(jobs, Mapping) else {}
    return {
        "topic_definition": compact_text(value.get("topic_definition", ""), 180),
        "topic_direction_milestone": compact_list_values(value.get("topic_direction_milestone", []), 8, 140),
        "topic_direction_strategy": compact_list_values(value.get("topic_direction_strategy", []), 3, 140),
        "topic_direction_agent_guidance": compact_list_values(value.get("topic_direction_agent_guidance", []), 5, 140),
        "tk_core_orientations": compact_list_values(value.get("tk_core_orientations", []), 6, 100),
        "tk_process_function_guidance": compact_list_values(value.get("tk_process_function_guidance", []), 8, 120),
        "core_customer_jobs": {
            "direct_customer_actions": compact_list_values(jobs.get("direct_customer_actions", []), 6, 100),
            "conditions_to_understand": compact_list_values(jobs.get("conditions_to_understand", []), 6, 120),
            "failure_recovery": compact_list_values(jobs.get("failure_recovery", []), 6, 120),
        },
        "core_policy_questions": compact_list_values(value.get("core_policy_questions", []), 8, 80),
        "must_include": compact_list_values(value.get("must_include", []), 8, 40),
        "must_not": compact_list_values(value.get("must_not", []), 8, 80),
    }


def core_design_map_for_stage(value: object, stage: str) -> dict:
    compacted = compact_core_design_map(value)
    if not compacted:
        return {}
    rows = compacted.get("design_rows", [])
    if not isinstance(rows, list):
        rows = []
    include_all = stage in {"final_check", "usecases", "state", "process", "functions", "function_detail", "policies"}
    return {
        "agent_role": compacted.get("agent_role", ""),
        "approval_status": compacted.get("approval_status", ""),
        "contract_rule": compacted.get("contract_rule", ""),
        "purpose": compacted.get("purpose", ""),
        "design_rows": rows[:12] if include_all else rows[:6],
        "required_handoff": compacted.get("required_handoff", {}),
        "fallback_axes": compacted.get("fallback_axes", {}),
        "must_not": compacted.get("must_not", []),
    }


def compact_core_design_map(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    rows = []
    for row in value.get("design_rows", []) if isinstance(value.get("design_rows", []), list) else []:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "requirement_id": row.get("requirement_id", ""),
                "title": compact_text(row.get("title", ""), 90),
                "actors": compact_list_values(row.get("actors", []), 5, 40),
                "usecase": compact_text(row.get("usecase", ""), 90),
                "state_candidates": compact_list_values(row.get("state_candidates", []), 7, 40),
                "process": compact_text(row.get("process", ""), 90),
                "functions": compact_list_values(row.get("functions", []), 6, 50),
                "policy_candidates": compact_list_values(row.get("policy_candidates", []), 6, 60),
                "policy_item_axes": compact_list_values(row.get("policy_item_axes", []), 6, 60),
            }
        )
    fallback_axes = value.get("fallback_axes", {}) if isinstance(value.get("fallback_axes", {}), Mapping) else {}
    return {
        "agent_role": compact_text(value.get("agent_role", ""), 120),
        "approval_status": compact_text(value.get("approval_status", ""), 40),
        "contract_rule": compact_text(value.get("contract_rule", ""), 180),
        "purpose": compact_text(value.get("purpose", ""), 200),
        "design_rows": rows[:24],
        "required_handoff": compact_required_handoff(value.get("required_handoff", {})),
        "fallback_axes": {
            "customer_jobs": compact_list_values(fallback_axes.get("customer_jobs", []), 6, 100),
            "policy_questions": compact_list_values(fallback_axes.get("policy_questions", []), 6, 100),
            "bss_touchpoints": compact_list_values(fallback_axes.get("bss_touchpoints", []), 6, 100),
        },
        "must_not": compact_list_values(value.get("must_not", []), 6, 100),
    }


def compact_required_handoff(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): compact_text(text, 120)
        for key, text in value.items()
        if str(key).strip() and str(text).strip()
    }


def first_draft_quality_plan_for_stage(plan: object, stage: str) -> dict:
    if not isinstance(plan, Mapping):
        return {}
    stage_checks = [
        compact_first_draft_stage_check(item)
        for item in plan.get("stage_checks", [])
        if isinstance(item, Mapping) and item.get("stage") in {stage, "final_check"}
    ]
    handoff_checks = []
    if stage in {"usecases", "state", "process", "functions", "function_detail", "policies", "final_check"}:
        handoff_checks = compact_list_values(plan.get("handoff_checks", []), 6, 160)
    return {
        "purpose": compact_text(plan.get("purpose", ""), 180),
        "stage_checks": stage_checks[:3],
        "handoff_checks": handoff_checks,
        "token_efficiency_rule": compact_text(plan.get("token_efficiency_rule", ""), 160),
    }


def compact_first_draft_quality_plan(plan: object) -> dict:
    if not isinstance(plan, Mapping):
        return {}
    return {
        "purpose": compact_text(plan.get("purpose", ""), 220),
        "stage_checks": [
            compact_first_draft_stage_check(item)
            for item in plan.get("stage_checks", [])
            if isinstance(item, Mapping)
        ][:12],
        "handoff_checks": compact_list_values(plan.get("handoff_checks", []), 8, 160),
        "token_efficiency_rule": compact_text(plan.get("token_efficiency_rule", ""), 160),
    }


def compact_first_draft_stage_check(item: Mapping[str, object]) -> dict:
    return {
        "stage": item.get("stage", ""),
        "before_write": compact_text(item.get("before_write", ""), 160),
        "must_produce": compact_text(item.get("must_produce", ""), 160),
        "self_check": compact_text(item.get("self_check", ""), 160),
        "reject_if": compact_text(item.get("reject_if", ""), 160),
        "topic_axes": compact_list_values(item.get("topic_axes", []), 5, 80),
    }


def architecture_skeleton_for_stage(skeleton: object, stage: str) -> dict:
    if not isinstance(skeleton, Mapping):
        return {}
    result: dict[str, object] = {}
    if stage in {"actors", "usecases", "state", "process", "functions", "function_detail", "policies", "final_check"}:
        result["requirement_derived_candidates"] = compact_skeleton_rows(
            skeleton.get("requirement_derived_candidates", []),
            (
                "requirement_id",
                "title",
                "actor_candidates",
                "usecase_candidate",
                "process_candidate",
                "function_capabilities",
                "policy_decision_axes",
                "target_stages",
            ),
            12,
        )
    if stage in {"actors", "usecases", "state", "process", "final_check"}:
        result["actor_candidates"] = compact_skeleton_rows(skeleton.get("actor_candidates", []), ("name", "role", "include_reason", "not_actor_examples", "evidence_ids"), 8)
    if stage in {"usecases", "state", "process", "final_check"}:
        result["usecase_groups"] = compact_skeleton_rows(skeleton.get("usecase_groups", []), ("actor", "goal", "process_target", "process_pattern", "function_axes", "policy_axes", "evidence_ids"), 10)
    if stage in {"state", "process", "functions", "policies", "final_check"}:
        result["process_patterns"] = compact_skeleton_rows(skeleton.get("process_patterns", []), ("usecase_type", "steps", "state_touchpoints", "bss_touchpoints", "evidence_ids"), 8)
    if stage in {"functions", "function_detail", "policies", "final_check"}:
        result["function_capabilities"] = compact_skeleton_rows(skeleton.get("function_capabilities", []), ("name", "capability_type", "detail_granularity", "reuse_rule", "evidence_ids"), 10)
    if stage in {"policies", "final_check"}:
        result["policy_taxonomy"] = compact_skeleton_rows(skeleton.get("policy_taxonomy", []), ("policy_group", "derived_from", "policy_items", "value_examples", "evidence_ids"), 10)
    if stage in {"process", "functions", "function_detail", "policies", "final_check"}:
        result["handoff_rules"] = compact_list_values(skeleton.get("handoff_rules", []), 8, 140)
    return result


def compact_architecture_skeleton(skeleton: object) -> dict:
    if not isinstance(skeleton, Mapping):
        return {}
    return {
        "requirement_derived_candidates": compact_skeleton_rows(
            skeleton.get("requirement_derived_candidates", []),
            (
                "requirement_id",
                "title",
                "actor_candidates",
                "usecase_candidate",
                "process_candidate",
                "function_capabilities",
                "policy_decision_axes",
                "target_stages",
            ),
            16,
        ),
        "actor_candidates": compact_skeleton_rows(skeleton.get("actor_candidates", []), ("name", "role", "include_reason", "evidence_ids"), 8),
        "usecase_groups": compact_skeleton_rows(skeleton.get("usecase_groups", []), ("actor", "goal", "process_target", "process_pattern", "evidence_ids"), 10),
        "process_patterns": compact_skeleton_rows(skeleton.get("process_patterns", []), ("usecase_type", "steps", "state_touchpoints", "evidence_ids"), 8),
        "function_capabilities": compact_skeleton_rows(skeleton.get("function_capabilities", []), ("name", "capability_type", "detail_granularity", "reuse_rule", "evidence_ids"), 10),
        "policy_taxonomy": compact_skeleton_rows(skeleton.get("policy_taxonomy", []), ("policy_group", "derived_from", "policy_items", "value_examples", "evidence_ids"), 10),
        "handoff_rules": compact_list_values(skeleton.get("handoff_rules", []), 10, 140),
    }


def architecture_evidence_pack_for_stage(pack: object, stage: str) -> dict:
    if not isinstance(pack, Mapping):
        return {}
    stage_card_ids = pack.get("stage_card_ids", {})
    ids = stage_card_ids.get(stage, []) if isinstance(stage_card_ids, Mapping) else []
    ids_set = {str(item) for item in ids if str(item).strip()}
    cards = [
        compact_architecture_evidence_card(item)
        for item in pack.get("cards", [])
        if isinstance(item, Mapping) and (str(item.get("id", "")) in ids_set or stage in (item.get("stages", []) if isinstance(item.get("stages", []), list) else []))
    ]
    return {
        "selection_rule": compact_text(pack.get("selection_rule", ""), 180),
        "stage_card_ids": list(ids_set)[:8],
        "cards": cards[:8],
    }


def compact_architecture_evidence_pack(pack: object) -> dict:
    if not isinstance(pack, Mapping):
        return {}
    return {
        "selection_rule": compact_text(pack.get("selection_rule", ""), 180),
        "stage_card_ids": pack.get("stage_card_ids", {}),
        "cards": [
            compact_architecture_evidence_card(item)
            for item in pack.get("cards", [])
            if isinstance(item, Mapping)
        ][:24],
        "stats": pack.get("stats", {}),
    }


def compact_architecture_evidence_card(item: Mapping[str, object]) -> dict:
    return {
        "id": item.get("id", ""),
        "kind": item.get("kind", ""),
        "source": compact_text(item.get("source", ""), 80),
        "title": compact_text(item.get("title", ""), 100),
        "summary": compact_text(item.get("summary", ""), 220),
        "signals": compact_list_values(item.get("signals", []), 4, 80),
        "evidence": compact_list_values(item.get("evidence", []), 2, 160),
        "stages": compact_list_values(item.get("stages", []), 5, 30),
    }


def compact_skeleton_rows(rows: object, fields: Sequence[str], limit: int) -> List[dict]:
    if not isinstance(rows, list):
        return []
    compacted: List[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item: dict[str, object] = {}
        for field in fields:
            value = row.get(field)
            if isinstance(value, list):
                item[field] = compact_list_values(value, 8, 80)
            elif value is not None:
                item[field] = compact_text(value, 160)
        compacted.append(item)
        if len(compacted) >= limit:
            break
    return compacted


def compact_list_values(values: object, limit: int, max_chars: int) -> List[str]:
    if not isinstance(values, list):
        return []
    return [compact_text(value, max_chars) for value in values if str(value).strip()][:limit]


def select_evenly(values: Sequence[object], limit: int) -> List[object]:
    """Pick a deterministic spread instead of only the first N items."""
    items = list(values)
    if limit <= 0 or len(items) <= limit:
        return items
    if limit == 1:
        return [items[0]]
    last_index = len(items) - 1
    indexes = sorted({round(index * last_index / (limit - 1)) for index in range(limit)})
    selected = [items[index] for index in indexes]
    if len(selected) < limit:
        selected_ids = {id(item) for item in selected}
        for item in items:
            if id(item) in selected_ids:
                continue
            selected.append(item)
            if len(selected) >= limit:
                break
    return selected[:limit]


def compact_architecture_stage_contract(item: Mapping[str, object]) -> dict:
    return {
        "stage": item.get("stage", ""),
        "layer": item.get("layer", ""),
        "write_as": compact_text(item.get("write_as", ""), 80),
        "granularity": compact_text(item.get("granularity", ""), 220),
        "do_not_write_as": list(item.get("do_not_write_as", []) or [])[:6] if isinstance(item.get("do_not_write_as"), list) else [],
        "handoff_to": list(item.get("handoff_to", []) or [])[:4] if isinstance(item.get("handoff_to"), list) else [],
        "acceptance_checks": list(item.get("acceptance_checks", []) or [])[:6] if isinstance(item.get("acceptance_checks"), list) else [],
        "topic_axes": list(item.get("topic_axes", []) or [])[:6] if isinstance(item.get("topic_axes"), list) else [],
    }


def compact_quality_gate(quality_gate: object) -> dict:
    if not isinstance(quality_gate, Mapping):
        return {}
    return {
        "status": quality_gate.get("status", ""),
        "passed": quality_gate.get("passed", False),
        "score": quality_gate.get("score", 0),
        "threshold": quality_gate.get("threshold", 0),
        "summary": quality_gate.get("summary", ""),
        "stage_risk_map": quality_gate.get("stage_risk_map", {}),
        "findings": [
            compact_quality_finding(item)
            for item in quality_gate.get("findings", [])
            if isinstance(item, Mapping)
        ][:24],
    }


def compact_quality_gate_for_stage(quality_gate: object, stage: str) -> dict:
    if not isinstance(quality_gate, Mapping):
        return {}
    stage_findings = [
        compact_quality_finding(item)
        for item in quality_gate.get("findings", [])
        if isinstance(item, Mapping) and item.get("stage") == stage
    ]
    blueprint_findings = [
        compact_quality_finding(item)
        for item in quality_gate.get("findings", [])
        if isinstance(item, Mapping) and item.get("stage") == "blueprint"
    ]
    return {
        "status": quality_gate.get("status", ""),
        "passed": quality_gate.get("passed", False),
        "score": quality_gate.get("score", 0),
        "threshold": quality_gate.get("threshold", 0),
        "summary": quality_gate.get("summary", ""),
        "stage_findings": (stage_findings + blueprint_findings)[:8],
        "rule": quality_gate.get("rule", ""),
    }


def compact_quality_finding(item: Mapping[str, object]) -> dict:
    return {
        "issue_id": item.get("issue_id", ""),
        "severity": item.get("severity", ""),
        "category": item.get("category", ""),
        "stage": item.get("stage", ""),
        "title": compact_text(item.get("title", ""), 90),
        "detail": compact_text(item.get("detail", ""), 180),
        "recommendation": compact_text(item.get("recommendation", ""), 180),
        "target_path": item.get("target_path", ""),
    }


def build_requirement_coverage_matrix(requirement_cards: Sequence[Mapping[str, object]]) -> List[dict]:
    return [
        {
            "requirement_id": card.get("id", ""),
            "source_number": card.get("source_number", ""),
            "title": card.get("title", ""),
            "depth4": card.get("depth4", ""),
            "required": card.get("required", ""),
            "target_stages": card.get("target_stages", []),
            "signals": card.get("signals", []),
            "coverage_rule": "요구사항은 유즈케이스, 상태, 프로세스, 기능, 정책 중 하나 이상에 반영한다.",
        }
        for card in requirement_cards
    ]


def build_blueprint_evidence_gaps(
    requirement_cards: Sequence[Mapping[str, object]],
    reference_cards: Sequence[Mapping[str, object]],
    analysis_signals: Mapping[str, object],
) -> List[dict]:
    gaps: List[dict] = []
    if not requirement_cards:
        gaps.append(gap("requirements", "관련 요구사항 없음", "요구사항 통합 list에서 주제 4depth와 매칭되는 항목이 없습니다."))
    if not reference_cards:
        gaps.append(gap("references", "참고자료 없음", "references 폴더에서 참고 가능한 분석자료가 없습니다."))
    categories = {str(card.get("category", "")) for card in reference_cards}
    if reference_cards and not categories.intersection({"voc", "research"}):
        gaps.append(gap("voc", "고객 불편 근거 약함", "VoC 또는 고객 조사 근거가 약해 고객 Pain Point가 일반화될 수 있습니다."))
    if reference_cards and "ia" not in categories:
        gaps.append(gap("ia", "IA/Flow 근거 약함", "IA 또는 Flow 근거가 약해 프로세스·기능 정의가 추상화될 수 있습니다."))
    if not list_values(analysis_signals.get("bss_touchpoints")):
        gaps.append(gap("bss", "BSS 판단 근거 약함", "BSS 검증, 상태 변경, 원장 반영, 연계 결과 회신 근거가 부족합니다."))
    if not list_values(analysis_signals.get("policy_decision_points")):
        gaps.append(gap("policy", "정책 동작값 근거 약함", "기능 동작값, 허용/제한, 횟수, 시간, 채널, 예외, 보관, 고지 기준으로 전환할 근거가 부족합니다."))
    return gaps


def gap(kind: str, title: str, detail: str) -> dict:
    return {"kind": kind, "title": title, "detail": detail, "severity": "warn"}


def stage_required_kinds(stage: str) -> Sequence[str]:
    mapping = {
        "overview": ("requirement", "strategy", "guideline"),
        "terms": ("requirement", "strategy", "guideline"),
        "actors": ("requirement", "strategy", "guideline"),
        "usecases": ("requirement", "strategy", "voc", "research", "guideline"),
        "usecase_diagram": ("guideline", "sample"),
        "state": ("requirement", "strategy", "voc", "guideline"),
        "process": ("requirement", "strategy", "voc", "ia", "guideline"),
        "functions": ("requirement", "strategy", "ia", "guideline"),
        "policies": ("requirement", "voc", "strategy", "guideline"),
        "process_detail": ("requirement", "strategy", "ia", "guideline", "sample"),
        "function_detail": ("requirement", "strategy", "ia", "guideline", "sample"),
        "final_check": ("requirement", "strategy", "guideline", "sample"),
    }
    return mapping.get(stage, ("requirement", "guideline"))


def stage_analysis_focus(stage: str, signals: Mapping[str, object]) -> dict:
    keys_by_stage = {
        "overview": ("topic_direction_milestone", "requirement_implications", "customer_tasks", "bss_touchpoints", "tk_core_orientations", "channel_integration_axes"),
        "terms": ("topic_direction_milestone", "requirement_implications", "policy_decision_points", "data_log_points", "tk_core_orientations", "channel_integration_axes"),
        "actors": ("topic_direction_milestone", "customer_tasks", "bss_touchpoints", "operation_points", "tk_core_orientations", "channel_integration_axes"),
        "usecases": ("topic_direction_milestone", "customer_tasks", "voc_pain_points", "requirement_implications", "tk_core_orientations", "tk_process_function_guidance", "channel_integration_axes"),
        "usecase_diagram": ("customer_tasks",),
        "state": ("topic_direction_milestone", "exception_points", "bss_touchpoints", "policy_decision_points", "tk_core_orientations", "channel_integration_axes"),
        "process": ("topic_direction_milestone", "customer_tasks", "bss_touchpoints", "ia_flow_points", "exception_points", "tk_core_orientations", "tk_process_function_guidance", "channel_integration_axes"),
        "functions": ("topic_direction_milestone", "ia_flow_points", "bss_touchpoints", "data_log_points", "tk_core_orientations", "tk_process_function_guidance", "channel_integration_axes"),
        "policies": ("topic_direction_milestone", "policy_decision_points", "exception_points", "data_log_points", "operation_points", "tk_core_orientations", "channel_integration_axes"),
        "process_detail": ("topic_direction_milestone", "customer_tasks", "bss_touchpoints", "ia_flow_points", "exception_points", "tk_core_orientations", "tk_process_function_guidance", "channel_integration_axes"),
        "function_detail": ("topic_direction_milestone", "ia_flow_points", "bss_touchpoints", "data_log_points", "exception_points", "tk_core_orientations", "tk_process_function_guidance", "channel_integration_axes"),
        "final_check": ("topic_direction_milestone", "requirement_implications", "policy_decision_points", "bss_touchpoints", "tk_core_orientations", "channel_integration_axes"),
    }
    return {key: list_values(signals.get(key))[:10] for key in keys_by_stage.get(stage, ())}


def compact_analysis_signals(signals: object, stage: str) -> dict:
    if not isinstance(signals, Mapping):
        return {}
    focused = stage_analysis_focus(stage, signals)
    focused["topic_learning_summary"] = compact_text(signals.get("topic_learning_summary", ""), 420)
    return focused


def stage_query_terms(stage: str, signals: Mapping[str, object]) -> List[str]:
    focus = stage_analysis_focus(stage, signals)
    terms: List[object] = []
    for values in focus.values():
        terms.extend(values if isinstance(values, list) else [values])
    return unique_limited(terms, 20, 80)


def compact_requirement_card(card: Mapping[str, object]) -> dict:
    return {
        "id": card.get("id", ""),
        "title": compact_text(card.get("title", ""), 100),
        "summary": compact_text(card.get("summary", ""), 260),
        "source_excerpt": compact_text(card.get("source_excerpt", ""), 280),
        "signals": card.get("signals", []),
        "target_stages": card.get("target_stages", []),
    }


def compact_requirement_hierarchy_row(row: Mapping[str, object]) -> dict:
    return {
        "requirement_id": row.get("requirement_id", ""),
        "title": compact_text(row.get("title", ""), 90),
        "summary": compact_text(row.get("summary", ""), 220),
        "source_excerpt": compact_text(row.get("source_excerpt", ""), 240),
        "actor_candidates": compact_list_values(row.get("actor_candidates", []), 5, 40),
        "usecase_candidate": compact_text(row.get("usecase_candidate", ""), 90),
        "process_candidate": compact_text(row.get("process_candidate", ""), 90),
        "function_capabilities": compact_list_values(row.get("function_capabilities", []), 6, 50),
        "policy_decision_axes": compact_list_values(row.get("policy_decision_axes", []), 6, 60),
        "target_stages": compact_list_values(row.get("target_stages", []), 10, 30),
    }


def classify_requirement_signals(text: str) -> List[str]:
    signals = []
    rules = (
        ("customer_task", CUSTOMER_TASK_KEYWORDS),
        ("bss", BSS_KEYWORDS),
        ("policy_decision", POLICY_KEYWORDS),
        ("exception", EXCEPTION_KEYWORDS),
        ("data_log", DATA_LOG_KEYWORDS),
        ("operation", OPERATION_KEYWORDS),
        ("flow", FLOW_KEYWORDS),
    )
    for label, keywords in rules:
        if contains_any(text, keywords):
            signals.append(label)
    return signals or ["general_requirement"]


def classify_requirement_stages(text: str) -> List[str]:
    stages = {"overview"}
    if contains_any(text, ("용어", "상태", "권한", "인증", "동의", "약관", "고객 유형")):
        stages.add("terms")
    if contains_any(text, ("고객", "운영자", "대리인", "기관", "시스템", "관리자")):
        stages.add("actors")
        stages.add("usecases")
    if contains_any(text, CUSTOMER_TASK_KEYWORDS + ("검색", "신청", "변경", "조회", "확인", "관리", "선택")):
        stages.add("usecases")
    if contains_any(text, ("상태", "완료", "실패", "제한", "보류", "취소", "만료", "전이")):
        stages.add("state")
    if contains_any(text, ("흐름", "프로세스", "처리", "요청", "결과", "연계", "BSS", "판정", "검증")):
        stages.add("process")
        stages.add("process_detail")
    if contains_any(text, ("기능", "조회", "검증", "산정", "저장", "알림", "연동", "이력")):
        stages.add("functions")
        stages.add("function_detail")
    if contains_any(text, POLICY_KEYWORDS + DATA_LOG_KEYWORDS + EXCEPTION_KEYWORDS):
        stages.add("policies")
    stages.add("final_check")
    return [stage for stage in STAGE_ORDER if stage in stages]


def requirement_texts(requirement_cards: Sequence[Mapping[str, object]]) -> List[str]:
    return [
        " ".join(
            str(card.get(key, ""))
            for key in ("id", "depth3", "depth4", "title", "summary", "source_excerpt", "requirement_type")
        )
        for card in requirement_cards
    ]


def reference_texts(reference_cards: Sequence[Mapping[str, object]]) -> List[str]:
    texts = []
    for card in reference_cards:
        parts = [
            str(card.get("source_name", "")),
            str(card.get("category", "")),
            str(card.get("summary", "")),
            " ".join(list_values(card.get("signals"))),
            " ".join(list_values(card.get("evidence"))),
        ]
        texts.append(" ".join(parts))
    return texts


def select_reference_texts(
    reference_cards: Sequence[Mapping[str, object]],
    categories: set[str],
    keywords: Sequence[str],
) -> List[str]:
    selected = []
    for card in reference_cards:
        category = str(card.get("category", "")).casefold()
        if category not in {item.casefold() for item in categories} and not contains_any(category, tuple(categories)):
            continue
        values = [card.get("summary", ""), *list_values(card.get("signals")), *list_values(card.get("evidence"))]
        selected.extend(value for value in values if contains_any(str(value), keywords) or not keywords)
    return selected


def select_texts_by_keywords(texts: Sequence[str], keywords: Sequence[str]) -> List[str]:
    return [text for text in texts if contains_any(text, keywords)]


def contains_any(text: object, keywords: Sequence[str]) -> bool:
    haystack = str(text or "").casefold()
    return any(str(keyword).casefold() in haystack for keyword in keywords)


def list_values(value: object) -> List[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, tuple):
        return [clean_text(item) for item in value if clean_text(item)]
    if value:
        return [clean_text(value)]
    return []


def unique_limited(values: Iterable[object], limit: int, max_chars: int) -> List[str]:
    result = []
    seen = set()
    for value in values:
        text = compact_text(value, max_chars)
        if len(text) < 2:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact_text(value: object, limit: int) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip(" ,.;·/") + "…"


def safe_key(value: object, index: int) -> str:
    key = re.sub(r"[^0-9A-Za-z가-힣]+", "-", clean_text(value)).strip("-")
    return key[:40] or f"{index:03d}"


CUSTOMER_TASK_KEYWORDS = ("고객", "사용자", "이용", "조회", "확인", "신청", "변경", "해지", "납부", "검색", "선택", "진입")
BSS_KEYWORDS = ("BSS", "원장", "가입", "회선", "요금", "청구", "납부", "계약", "상태", "판정", "검증", "연계", "응답")
POLICY_KEYWORDS = ("기준", "조건", "허용", "제한", "필수", "선택", "예외", "우선순위", "동의", "권한", "인증", "고지")
EXCEPTION_KEYWORDS = ("실패", "오류", "장애", "보류", "제한", "불가", "예외", "취소", "만료", "재시도", "상담")
DATA_LOG_KEYWORDS = ("개인정보", "민감정보", "로그", "이력", "저장", "보관", "파기", "삭제", "마스킹", "동의")
OPERATION_KEYWORDS = ("운영", "관리", "모니터링", "품질", "지표", "개선", "보정", "승인", "변경 이력")
FLOW_KEYWORDS = ("IA", "Flow", "흐름", "경로", "진입", "단계", "메뉴", "연결", "후속", "프로세스")
PAIN_POINT_KEYWORDS = ("불편", "Pain", "복잡", "어려움", "오류", "문의", "상담", "불만", "VOC", "개선")
CHANNEL_INTEGRATION_KEYWORDS = (
    "T월드",
    "T멤버십",
    "T다이렉트샵",
    "T우주",
    "통합",
    "회선",
    "요금",
    "멤버십",
    "혜택",
    "구독",
    "배송",
    "개통",
    "BSS",
    "정기결제",
)
