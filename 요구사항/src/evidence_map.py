"""Topic evidence map for policy authoring.

The reference database is most useful when agents receive a stable map of
which evidence should guide each chapter.  This module builds that map with
deterministic ranking so LLM agents can focus on writing, not re-reading or
re-interpreting every source.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, List, Mapping, Sequence

try:
    from evidence_store import EvidenceStore, EvidenceItem, analysis_synthesis_alias_text, analysis_synthesis_topic_terms, evidence_authority_score, evidence_source_authority, evidence_source_authority_tier, evidence_source_precedence, stage_profile_terms, unique_terms
except ImportError:  # pragma: no cover - package import fallback.
    from .evidence_store import EvidenceStore, EvidenceItem, analysis_synthesis_alias_text, analysis_synthesis_topic_terms, evidence_authority_score, evidence_source_authority, evidence_source_authority_tier, evidence_source_precedence, stage_profile_terms, unique_terms


CHAPTER_ORDER = (
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


CHAPTER_EVIDENCE_PROFILES = {
    "overview": {
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "focus_terms": ("범위", "제외", "채널", "고객", "전략", "과제"),
    },
    "terms": {
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "focus_terms": ("용어", "상태", "권한", "인증", "동의", "보관"),
    },
    "terms_refinement": {
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "focus_terms": ("용어", "상태", "권한", "제한", "고지", "이력"),
    },
    "actors": {
        "required_kinds": ("requirement", "strategy", "guideline"),
        "focus_terms": ("액터", "고객", "운영자", "BSS", "연계", "책임"),
    },
    "usecases": {
        "required_kinds": ("requirement", "strategy", "voc", "research", "guideline"),
        "focus_terms": ("유즈케이스", "고객", "행위", "트리거", "불편", "완료"),
    },
    "usecase_diagram": {
        "required_kinds": ("guideline", "sample"),
        "focus_terms": ("액터", "유즈케이스", "관계", "include"),
    },
    "state": {
        "required_kinds": ("requirement", "strategy", "voc", "guideline"),
        "focus_terms": ("상태", "전이", "제한", "보류", "완료", "예외"),
    },
    "process": {
        "required_kinds": ("requirement", "voc", "ia", "strategy", "guideline"),
        "focus_terms": ("프로세스", "흐름", "시작", "판단", "완료", "BSS", "연계"),
    },
    "process_detail": {
        "required_kinds": ("requirement", "strategy", "ia", "guideline", "sample"),
        "focus_terms": ("진입", "종료", "선행", "후행", "흐름", "예외"),
    },
    "functions": {
        "required_kinds": ("requirement", "ia", "strategy", "guideline"),
        "focus_terms": ("기능", "조회", "검증", "산정", "저장", "알림", "연동"),
    },
    "function_detail": {
        "required_kinds": ("requirement", "strategy", "ia", "guideline", "sample"),
        "focus_terms": ("입력", "처리", "출력", "실패", "예외", "정책"),
    },
    "policies": {
        "required_kinds": ("requirement", "voc", "strategy", "guideline"),
        "focus_terms": ("정책", "판단", "조건", "허용", "제한", "예외", "고지", "이력"),
    },
    "final_check": {
        "required_kinds": ("requirement", "strategy", "guideline", "sample"),
        "focus_terms": ("점검", "정합성", "요구사항", "연결성", "근거", "누락"),
    },
}


def build_topic_evidence_map(
    *,
    topic: str,
    spec: Mapping[str, object],
    evidence_store: EvidenceStore,
    learning: Mapping[str, object],
    stages: Sequence[str] | None = None,
    per_stage_limit: int = 10,
) -> dict:
    """Build a stable, chapter-oriented evidence map for the current topic."""
    stage_keys = unique_texts(stages or CHAPTER_ORDER)
    stage_maps = {
        stage: build_stage_evidence_map(
            topic=topic,
            spec=spec,
            evidence_store=evidence_store,
            learning=learning,
            stage=stage,
            limit=per_stage_limit,
        )
        for stage in stage_keys
    }
    evidence_ids = unique_texts(
        evidence_id
        for stage_map in stage_maps.values()
        for evidence_id in stage_map.get("evidence_ids", [])
    )
    source_names = unique_texts(
        source
        for stage_map in stage_maps.values()
        for source in stage_map.get("source_names", [])
    )
    requirement_ids = unique_texts(
        evidence_id
        for evidence_id in evidence_ids
        if str(evidence_id).startswith("REQ-")
    )
    return {
        "version": "topic-evidence-map-v2-channel-strategy",
        "topic": str(topic or ""),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "principle": "참고자료 DB와 요구사항을 장별 근거 카드로 선별한다. 원문 전체를 반복 전달하지 않고, 작성·검수에 필요한 digest만 사용한다.",
        "stats": {
            "stage_count": len(stage_maps),
            "evidence_id_count": len(evidence_ids),
            "requirement_id_count": len(requirement_ids),
            "source_count": len(source_names),
            "available_store_items": len(getattr(evidence_store, "items", []) or []),
        },
        "source_names": source_names[:40],
        "stages": stage_maps,
        "gaps": [
            gap
            for stage_map in stage_maps.values()
            for gap in stage_map.get("evidence_gaps", [])
        ],
    }


def build_stage_evidence_map(
    *,
    topic: str,
    spec: Mapping[str, object],
    evidence_store: EvidenceStore,
    learning: Mapping[str, object],
    stage: str,
    limit: int = 10,
) -> dict:
    profile = CHAPTER_EVIDENCE_PROFILES.get(stage, CHAPTER_EVIDENCE_PROFILES["overview"])
    required_kinds = tuple(profile["required_kinds"])
    query_terms = collect_stage_query_terms(stage, topic, spec, learning, profile.get("focus_terms", ()))
    selected = evidence_store.select(
        stage=stage,
        topic=topic,
        query_terms=query_terms,
        required_kinds=required_kinds,
        limit=max(4, limit),
    )
    selected = merge_target_requirement_items(selected, evidence_store, stage_target_requirement_ids(spec, stage), limit)
    selected = merge_global_channel_strategy_evidence(selected, evidence_store, stage, limit)
    selected = merge_analysis_synthesis_evidence(selected, evidence_store, stage, topic, limit)
    selected = ensure_required_kind_coverage(selected, evidence_store, required_kinds, limit)
    present_kinds = {str(getattr(item, "kind", "") or "") for item in selected}
    gaps = [
        {
            "stage": stage,
            "missing_kind": kind,
            "reason": f"{stage} 작성에 필요한 {kind} 근거가 주제 근거 지도에 충분히 잡히지 않았습니다.",
        }
        for kind in required_kinds
        if kind not in present_kinds
    ]
    classified = classify_evidence_signals(selected)
    evidence_groups = grouped_evidence_ids(selected, required_kinds)
    return {
        "stage": stage,
        "required_kinds": list(required_kinds),
        "selection_strategy": {
            "query_template_terms": list(stage_profile_terms(stage))[:14],
            "rule": "장별 query template와 목표 요구사항을 우선하고, 동일 출처 chunk 반복은 제한한다.",
            "source_authority": "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 1순위 보강 근거인 현황 분석 종합 장표, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다. 분석 장표가 요구사항·TK 원천과 상충하면 원천을 따른다.",
            "authority_score": "근거 카드에는 authority_score가 포함되며, 같은 관련도에서는 높은 점수의 첨부 근거를 우선한다.",
        },
        "query_terms": query_terms[:18],
        "evidence_ids": [str(getattr(item, "id", "") or "") for item in selected],
        "essential_evidence_ids": evidence_groups["essential"],
        "supplemental_evidence_ids": evidence_groups["supplemental"],
        "requirement_ids": [
            str(getattr(item, "id", "") or "")
            for item in selected
            if str(getattr(item, "id", "") or "").startswith("REQ-")
        ],
        "source_mix": source_mix(selected),
        "source_names": unique_texts(str(getattr(item, "source", "") or "") for item in selected)[:8],
        "channel_integration_context": channel_integration_context(selected),
        "evidence_cards": [compact_evidence_card(item, stage, query_terms) for item in selected[: min(limit, 8)]],
        "customer_pain_points": classified["customer_pain_points"][:6],
        "decision_axes": classified["decision_axes"][:8],
        "bss_touchpoints": classified["bss_touchpoints"][:6],
        "flow_signals": classified["flow_signals"][:6],
        "exception_signals": classified["exception_signals"][:6],
        "evidence_gaps": gaps,
    }


def merge_global_channel_strategy_evidence(
    selected: Sequence[EvidenceItem],
    evidence_store: EvidenceStore,
    stage: str,
    limit: int,
) -> List[EvidenceItem]:
    if stage not in {"overview", "terms", "actors", "usecases", "state", "process", "functions", "policies", "process_detail", "function_detail", "terms_refinement", "final_check"}:
        return list(selected)[:limit]
    if any(is_global_channel_strategy_item(item) for item in selected):
        return list(selected)[:limit]
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if is_global_channel_strategy_item(item)
    ]
    if not candidates:
        return list(selected)[:limit]
    candidates.sort(key=global_channel_strategy_rank, reverse=True)
    selected_ids = {item.id for item in selected}
    addition = next((item for item in candidates if item.id not in selected_ids), None)
    if addition is None:
        return list(selected)[:limit]
    requirements = [item for item in selected if item.kind == "requirement"]
    others = [item for item in selected if item.kind != "requirement"]
    requirement_prefix_count = min(len(requirements), max(1, limit // 2))
    merged = requirements[:requirement_prefix_count] + [addition] + requirements[requirement_prefix_count:] + others
    result: List[EvidenceItem] = []
    seen: set[str] = set()
    for item in merged:
        if item.id in seen:
            continue
        result.append(item)
        seen.add(item.id)
        if len(result) >= limit:
            break
    return result


def merge_analysis_synthesis_evidence(
    selected: Sequence[EvidenceItem],
    evidence_store: EvidenceStore,
    stage: str,
    topic: str,
    limit: int,
) -> List[EvidenceItem]:
    if stage not in {"overview", "usecases", "state", "process", "functions", "process_detail", "function_detail", "policies", "final_check"}:
        return list(selected)[:limit]
    if any(str(getattr(item, "kind", "") or "") == "analysis_synthesis" for item in selected):
        return list(selected)[:limit]
    selected_ids = {str(getattr(item, "id", "") or "") for item in selected}
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if str(getattr(item, "kind", "") or "") == "analysis_synthesis"
        and str(getattr(item, "id", "") or "") not in selected_ids
    ]
    if not candidates:
        return list(selected)[:limit]
    candidates.sort(key=lambda item: analysis_synthesis_rank(item, topic), reverse=True)
    addition = candidates[0]
    requirements = [item for item in selected if item.kind == "requirement"]
    others = [item for item in selected if item.kind != "requirement"]
    requirement_prefix_count = min(len(requirements), max(1, limit // 2))
    merged = requirements[:requirement_prefix_count] + [addition] + requirements[requirement_prefix_count:] + others
    result: List[EvidenceItem] = []
    seen: set[str] = set()
    for item in merged:
        if item.id in seen:
            continue
        result.append(item)
        seen.add(item.id)
        if len(result) >= limit:
            break
    return result


def analysis_synthesis_rank(item: EvidenceItem, topic: str) -> tuple[int, int, int, str]:
    alias_text = analysis_synthesis_alias_text(item.source)
    text = " ".join(
        [
            item.source,
            item.title,
            alias_text,
            item.summary,
            " ".join(item.signals),
            " ".join(item.evidence),
            " ".join(item.tags),
        ]
    ).casefold()
    source_title = " ".join([item.source, item.title, alias_text]).casefold()
    term_score = 0
    focused_terms = analysis_synthesis_topic_terms(topic)
    for term in focused_terms:
        key = str(term or "").strip().casefold()
        if not key:
            continue
        if key in source_title:
            term_score += 8
        elif key in text:
            term_score += 1
    if not term_score and (
        item.source in {"benchmarking.html", "customer-research.html", "employee-interview.html", "ia-analysis.html", "voc-summary.html"}
        or str(item.source).startswith("function-inventory-")
    ):
        term_score += 3
    is_chunk = "source_chunk" in set(item.tags)
    return (term_score, item.score, 0 if is_chunk else 1, item.source)


def ensure_required_kind_coverage(
    selected: Sequence[EvidenceItem],
    evidence_store: EvidenceStore,
    required_kinds: Sequence[str],
    limit: int,
) -> List[EvidenceItem]:
    """Restore available required evidence kinds after map-level merges.

    Target requirement and channel-strategy merges can intentionally pull in
    extra high-value cards.  They should not silently evict sample/guideline
    anchors because those are the format and quality references writers need.
    """
    result = list(selected)
    selected_ids = {str(getattr(item, "id", "") or "") for item in result}
    present_kinds = {str(getattr(item, "kind", "") or "") for item in result}
    for kind in required_kinds:
        kind = str(kind or "").strip()
        if not kind or kind in present_kinds:
            continue
        candidate = best_required_kind_candidate(evidence_store, kind, selected_ids)
        if candidate is None:
            continue
        result.append(candidate)
        selected_ids.add(candidate.id)
        present_kinds.add(kind)
        result = trim_preserving_required_kinds(result, required_kinds, limit)
    return result[:limit]


def best_required_kind_candidate(
    evidence_store: EvidenceStore,
    kind: str,
    selected_ids: set[str],
) -> EvidenceItem | None:
    candidates = [
        item
        for item in getattr(evidence_store, "items", []) or []
        if str(getattr(item, "kind", "") or "") == kind and str(getattr(item, "id", "") or "") not in selected_ids
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (evidence_authority_score(item), item.score, item.source, item.title), reverse=True)
    return candidates[0]


def trim_preserving_required_kinds(
    selected: Sequence[EvidenceItem],
    required_kinds: Sequence[str],
    limit: int,
) -> List[EvidenceItem]:
    result = list(selected)
    required = {str(kind or "").strip() for kind in required_kinds if str(kind or "").strip()}
    while len(result) > max(1, limit):
        removable_index = removable_evidence_index(result, required)
        if removable_index is None:
            break
        result.pop(removable_index)
    return result


def removable_evidence_index(selected: Sequence[EvidenceItem], required_kinds: set[str]) -> int | None:
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
        if kind == "requirement" and kind_counts.get(kind, 0) > 2:
            return index
    for index in range(len(selected) - 1, -1, -1):
        kind = str(getattr(selected[index], "kind", "") or "")
        if kind_counts.get(kind, 0) > 1:
            return index
    return len(selected) - 1 if selected else None


def is_global_channel_strategy_item(item: EvidenceItem) -> bool:
    if item.kind != "strategy":
        return False
    text = " ".join([item.source, item.title, item.summary, " ".join(item.signals), " ".join(item.evidence)])
    return any(keyword in text for keyword in ("채널 방향성", "T월드", "T멤버십", "T다이렉트샵", "T우주", "통합지식"))


def global_channel_strategy_rank(item: EvidenceItem) -> tuple[int, int, int]:
    channel_hits = sum(1 for keyword in ("T월드", "T멤버십", "T다이렉트샵", "T우주") if keyword in evidence_text(item))
    is_chunk = "source_chunk" in set(item.tags)
    return (item.score, channel_hits, 0 if is_chunk else 1)


def channel_integration_context(selected: Sequence[EvidenceItem]) -> dict:
    channel_items = [item for item in selected if is_global_channel_strategy_item(item)]
    if not channel_items:
        return {}
    return {
        "rule": "통합채널 공개웹 지식은 채널별 책임 경계와 상태·정책 판단축으로 사용하고, 현재 주제 밖 업무를 본문 범위로 확장하지 않는다.",
        "channel_axes": [
            "T월드=회선·요금·납부·BSS 판정",
            "T멤버십=등급·혜택·쿠폰·바코드",
            "T다이렉트샵=구매·가입·배송·개통",
            "T우주=구독·정기결제·제휴 책임",
        ],
        "evidence_ids": [item.id for item in channel_items[:4]],
        "sources": unique_texts(item.source for item in channel_items)[:3],
    }


def compact_topic_evidence_map_for_stage(
    topic_evidence_map: Mapping[str, object],
    stage: str,
    *,
    max_cards: int = 6,
) -> dict:
    """Return only the current stage slice for prompts and inspector input."""
    if not isinstance(topic_evidence_map, Mapping):
        return {}
    stages = topic_evidence_map.get("stages", {})
    if not isinstance(stages, Mapping):
        return {}
    stage_map = stages.get(stage)
    if not isinstance(stage_map, Mapping) and stage == "terms_refinement":
        stage_map = stages.get("terms") or stages.get("policies")
    if not isinstance(stage_map, Mapping):
        return {}
    cards = stage_map.get("evidence_cards", [])
    if not isinstance(cards, list):
        cards = []
    return {
        "version": topic_evidence_map.get("version", ""),
        "stage": stage,
        "rule": "이 장은 아래 근거 카드와 판단축을 우선 반영한다. 근거가 부족한 내용은 확정값처럼 쓰지 않는다.",
        "evidence_ids": list(stage_map.get("evidence_ids", []) or [])[:16],
        "essential_evidence_ids": list(stage_map.get("essential_evidence_ids", []) or [])[:12],
        "supplemental_evidence_ids": list(stage_map.get("supplemental_evidence_ids", []) or [])[:8],
        "requirement_ids": list(stage_map.get("requirement_ids", []) or [])[:12],
        "selection_strategy": stage_map.get("selection_strategy", {}),
        "source_mix": stage_map.get("source_mix", {}),
        "source_names": list(stage_map.get("source_names", []) or [])[:6],
        "channel_integration_context": stage_map.get("channel_integration_context", {}),
        "evidence_cards": [dict(card) for card in cards[:max_cards] if isinstance(card, Mapping)],
        "customer_pain_points": list(stage_map.get("customer_pain_points", []) or [])[:4],
        "decision_axes": list(stage_map.get("decision_axes", []) or [])[:6],
        "bss_touchpoints": list(stage_map.get("bss_touchpoints", []) or [])[:4],
        "flow_signals": list(stage_map.get("flow_signals", []) or [])[:4],
        "exception_signals": list(stage_map.get("exception_signals", []) or [])[:4],
        "evidence_gaps": list(stage_map.get("evidence_gaps", []) or [])[:4],
    }


def collect_stage_query_terms(
    stage: str,
    topic: str,
    spec: Mapping[str, object],
    learning: Mapping[str, object],
    focus_terms: Sequence[object],
) -> List[str]:
    terms: List[object] = [topic, *stage_profile_terms(stage), *focus_terms]
    for key in ("customer_tasks", "policy_risks", "bss_implications", "decision_axes"):
        value = learning.get(key, []) if isinstance(learning, Mapping) else []
        terms.extend(value if isinstance(value, list) else [value])
    if stage in {"usecases", "usecase_diagram", "state", "process", "functions", "policies", "process_detail", "function_detail", "final_check", "terms_refinement"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("actors", [])))
    if stage in {"state", "process", "functions", "policies", "process_detail", "function_detail", "final_check", "terms_refinement"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("usecases", [])))
    if stage in {"process", "functions", "policies", "process_detail", "function_detail", "final_check", "terms_refinement"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("states", [])))
    if stage in {"functions", "policies", "process_detail", "function_detail", "final_check", "terms_refinement"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("processes", [])))
    if stage in {"policies", "function_detail", "final_check", "terms_refinement"}:
        terms.extend(row.get("name", "") for row in list_dicts(spec.get("functions", [])))
    return unique_texts(terms)


def grouped_evidence_ids(selected: Sequence[EvidenceItem], required_kinds: Sequence[str]) -> dict:
    required = set(required_kinds)
    essential: List[str] = []
    supplemental: List[str] = []
    for item in selected:
        if item.kind == "requirement" or item.kind in required or item.id.startswith(("GUIDE-", "SAMPLE-")):
            essential.append(item.id)
        else:
            supplemental.append(item.id)
    return {
        "essential": unique_texts(essential)[:20],
        "supplemental": unique_texts(supplemental)[:20],
    }


def stage_target_requirement_ids(spec: Mapping[str, object], stage: str) -> List[str]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    chapters = blueprint.get("chapter_blueprints", []) if isinstance(blueprint.get("chapter_blueprints"), list) else []
    for chapter in chapters:
        if isinstance(chapter, Mapping) and chapter.get("stage") == stage:
            return unique_texts(chapter.get("target_requirement_ids", []))
    return []


def merge_target_requirement_items(
    selected: Sequence[EvidenceItem],
    evidence_store: EvidenceStore,
    target_requirement_ids: Sequence[str],
    limit: int,
) -> List[EvidenceItem]:
    if not target_requirement_ids:
        return list(selected)[:limit]
    selected_ids = {str(getattr(item, "id", "") or "") for item in selected}
    requirement_items = [
        item for item in getattr(evidence_store, "items", []) if str(getattr(item, "kind", "") or "") == "requirement"
    ]
    supplements: List[EvidenceItem] = []
    for requirement_id in target_requirement_ids:
        item = find_requirement_item(requirement_items, requirement_id)
        if item is None or item.id in selected_ids:
            continue
        supplements.append(item)
        selected_ids.add(item.id)
        if len(supplements) >= max(2, min(8, limit // 2)):
            break
    merged = supplements + [item for item in selected if item.id not in {extra.id for extra in supplements}]
    return merged[:limit]


def find_requirement_item(items: Sequence[EvidenceItem], requirement_id: str) -> EvidenceItem | None:
    target = normalize_key(str(requirement_id).removeprefix("REQ-"))
    for item in items:
        item_key = normalize_key(str(item.id).removeprefix("REQ-"))
        if target and target == item_key:
            return item
    for item in items:
        item_key = normalize_key(str(item.id).removeprefix("REQ-"))
        if target and target in item_key:
            return item
    return None


def compact_evidence_card(item: EvidenceItem, stage: str, query_terms: Sequence[str]) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "source_authority": evidence_source_authority(item),
        "authority_tier": evidence_source_authority_tier(item),
        "authority_score": evidence_authority_score(item),
        "source_precedence": evidence_source_precedence(item),
        "source": limit_text(item.source, 70),
        "title": limit_text(item.title, 88),
        "summary": limit_text(item.summary, 180),
        "signals": [limit_text(value, 70) for value in list(item.signals)[:3]],
        "tags": [limit_text(value, 32) for value in list(item.tags)[:5]],
        "why_selected": evidence_selection_reason(item, stage, query_terms),
    }


def evidence_selection_reason(item: EvidenceItem, stage: str, query_terms: Sequence[str]) -> str:
    matched = [
        term
        for term in query_terms
        if len(str(term)) >= 2 and str(term).casefold() in evidence_text(item).casefold()
    ][:3]
    if matched:
        return f"{stage} 작성 질의어({', '.join(matched)})와 연결됨."
    if item.kind == "requirement":
        return "요구사항 최소 커버리지 확보를 위해 포함됨."
    if item.kind in {"guideline", "sample"}:
        return "템플릿·샘플 작성 기준 유지용 근거."
    return "참고자료 카테고리와 장별 작성 목적이 맞아 포함됨."


def classify_evidence_signals(items: Sequence[EvidenceItem]) -> dict:
    buckets = {
        "customer_pain_points": [],
        "decision_axes": [],
        "bss_touchpoints": [],
        "flow_signals": [],
        "exception_signals": [],
    }
    for item in items:
        text = " ".join([item.title, item.summary, " ".join(item.signals)])
        for sentence in digest_sentences(text):
            if has_any(sentence, ("불편", "어렵", "복잡", "문의", "요청", "기대", "Pain", "VoC")):
                buckets["customer_pain_points"].append(sentence)
            if has_any(sentence, ("기준", "조건", "허용", "제한", "정책", "동의", "고지", "이력", "저장", "우선순위")):
                buckets["decision_axes"].append(sentence)
            if has_any(sentence, ("BSS", "연계", "원장", "인증", "검증", "판정", "회신", "처리")):
                buckets["bss_touchpoints"].append(sentence)
            if has_any(sentence, ("프로세스", "흐름", "IA", "메뉴", "경로", "시작", "완료", "전환")):
                buckets["flow_signals"].append(sentence)
            if has_any(sentence, ("실패", "불가", "보류", "예외", "취소", "만료", "재시도", "복구")):
                buckets["exception_signals"].append(sentence)
    return {key: unique_texts(values) for key, values in buckets.items()}


def source_mix(items: Sequence[EvidenceItem]) -> dict:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    return counts


def evidence_text(item: EvidenceItem) -> str:
    return "\n".join(
        [
            item.source,
            item.title,
            item.summary,
            " ".join(item.signals),
            " ".join(item.evidence),
            " ".join(item.tags),
        ]
    )


def digest_sentences(text: object) -> List[str]:
    result: List[str] = []
    for part in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|[\n\r;]+", str(text or "")):
        cleaned = re.sub(r"\s+", " ", part).strip()
        if 8 <= len(cleaned) <= 150:
            result.append(cleaned)
        elif len(cleaned) > 150:
            result.append(cleaned[:149].rstrip(" ,.;·/") + "…")
    return result[:10]


def has_any(text: str, needles: Sequence[str]) -> bool:
    folded = text.casefold()
    return any(str(needle).casefold() in folded for needle in needles)


def list_dicts(value: object) -> List[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def unique_texts(values: Iterable[object]) -> List[str]:
    result: List[str] = []
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


def normalize_key(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()


def limit_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip(" ,.;·/") + "…"
