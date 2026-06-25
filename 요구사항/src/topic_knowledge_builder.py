"""Prebuild topic knowledge packs for NC policy authoring.

The packs are deterministic summaries of requirements, attached references,
and public-web auxiliary knowledge. They let Topic Learning and Blueprint
Architect start from a stable baseline without asking every writer agent to
rediscover the same context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

try:
    from evidence_map import build_topic_evidence_map
    from evidence_store import EvidenceStore, build_evidence_store, evidence_authority_tier_for_authority, evidence_source_authority_for_values
    from policy_references import DEFAULT_REFERENCE_DB_PATH, ensure_project_source_database, load_reference_insights_for_topic
    from policy_requirements import load_scoped_requirements_for_topic
    from runtime_paths import INPUT_ROOT, PROJECT_ROOT, TOPIC_KNOWLEDGE_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .evidence_map import build_topic_evidence_map
    from .evidence_store import EvidenceStore, build_evidence_store, evidence_authority_tier_for_authority, evidence_source_authority_for_values
    from .policy_references import DEFAULT_REFERENCE_DB_PATH, ensure_project_source_database, load_reference_insights_for_topic
    from .policy_requirements import load_scoped_requirements_for_topic
    from .runtime_paths import INPUT_ROOT, PROJECT_ROOT, TOPIC_KNOWLEDGE_ROOT

DEFAULT_TOPIC_KNOWLEDGE_DIR = TOPIC_KNOWLEDGE_ROOT
TOPIC_KNOWLEDGE_VERSION = "topic-knowledge-v12-tk-process-function-guidance"
TOPIC_DIRECTION_MILESTONE_PATH = INPUT_ROOT / "references" / "34개_정책서_작성_지향점.md"
TK_ORIENTATION_POINT_MIN_SCORE = 18
TK_PROCESS_FUNCTION_MIN_SCORE = 18

POLICY_TOPICS = (
    "가이드라인/ 공통/ 품질/ 적응형",
    "전시/관리 기능",
    "상품 목록",
    "외부 BP 서비스 관리 체계",
    "AI 검색",
    "추천",
    "데이터 트래킹 체계",
    "이벤트/미션 프로그램",
    "외부 쿠폰",
    "멤버십 혜택/T 플러스포인트",
    "상품상세/담기",
    "카트/장바구니",
    "할인/시뮬레이션",
    "주문/계약/가입",
    "선물주문",
    "상품변경",
    "결제",
    "주문 상태/사후 관리",
    "해지/환불/취소",
    "나의 가입 정보",
    "회선 변경/관리",
    "멤버십 카드 관리",
    "청구 및 수납 관리",
    "나의 데이터·통화",
    "상품·서비스 혜택 이용/공유",
    "통합 쿠폰/이용권함",
    "회원 가입/탈퇴",
    "회원정보 조회/변경",
    "통합 알림",
    "통합 약관",
    "설정",
    "고객센터_통합허브",
    "고객센터_FAQ/공지/이용안내",
    "고객센터_매장안내",
)

STAGES = (
    "overview",
    "terms",
    "actors",
    "usecases",
    "state",
    "process",
    "functions",
    "policies",
    "final_check",
)


def build_topic_knowledge_pack(
    topic: str,
    *,
    project_root: Path = PROJECT_ROOT,
    requirements_dir: Path | str | None = None,
    references_dir: Path | str | None = None,
) -> dict:
    requirements_root = Path(requirements_dir) if requirements_dir else INPUT_ROOT / "requirements"
    references_root = Path(references_dir) if references_dir else INPUT_ROOT / "references"
    ensure_project_source_database(project_root, DEFAULT_REFERENCE_DB_PATH)
    requirements = load_scoped_requirements_for_topic(topic, requirements_root)
    references = filter_references_for_topic(
        topic,
        load_reference_insights_for_topic(topic, references_root),
    )
    guideline_stub = {
        "common_rules": [
            "1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF를 2~4순위 보조/참고 근거보다 우선한다.",
            "템플릿과 샘플의 장 구성, 표 구조, 문체, 정책 상세 수준을 유지한다.",
        ],
        "sample_baseline": {},
    }
    ctx = SimpleContext(topic=topic, requirements=requirements, references=references)
    evidence_store = build_evidence_store(ctx, guideline_stub)
    seed_learning = seed_learning_from_sources(topic, requirements, references)
    topic_evidence_map = build_topic_evidence_map(
        topic=topic,
        spec=empty_spec(topic),
        evidence_store=evidence_store,
        learning=seed_learning,
        stages=STAGES,
        per_stage_limit=8,
    )
    primary, auxiliary = split_references_by_authority(references)
    tk_core_orientations = build_tk_core_orientations(topic, primary, requirements)
    tk_process_function_guidance = build_tk_process_function_guidance(topic, primary, requirements)
    topic_direction_milestone = topic_direction_milestone_for(topic)
    topic_direction_strategy, topic_direction_agent_guidance = split_direction_milestone(topic_direction_milestone)
    topic_direction_agent_guidance = unique_texts([*topic_direction_strategy, *topic_direction_agent_guidance])[:8]
    pack = {
        "version": TOPIC_KNOWLEDGE_VERSION,
        "topic": topic,
        "topic_slug": topic_slug(topic),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_fingerprint": source_fingerprint(requirements, references),
        "source_authority_rule": {
            "priority": [
                "1순위 근거: 첨부자료 / 사내자료 / 요구사항 / 채널 방향성·TK 과제정의 PDF",
                "1순위 보강 근거: 현황 분석 종합 장표 / VoC 종합 장표",
                "2순위 보조 근거: SKT 공식 서비스 안내 / 약관 / 고객지원 페이지",
                "3순위 컴플라이언스 근거: 법령 / 규제기관 / 개인정보보호위 / 방통위 자료",
                "4순위 참고 근거: 경쟁사 / 벤치마킹 / 공개웹 자료",
            ],
            "conflict_policy": "하위 순위 근거가 상위 순위 근거와 상충하면 상위 순위 근거를 우선하고 상충되는 하위 근거는 작성 기준에서 폐기한다.",
            "analysis_synthesis_role": "현황 분석 종합 장표는 원천 자료를 정책서 작성 관점으로 정리한 내부 보강 근거로 사용하되, 요구사항·TK 원천과 충돌하면 원천을 우선한다.",
            "official_service_role": "SKT 공식 서비스 안내, 약관, 고객지원 페이지는 첨부·사내 근거를 보강하는 2순위 보조 근거로만 사용한다.",
            "compliance_role": "법령·규제기관 자료는 개인정보, 고지, 동의, 보관, 제한 같은 준수 필요성과 금지선을 확인하는 3순위 근거로 사용한다.",
            "public_web_role": "경쟁사, 벤치마킹, 공개웹 자료는 정책 후보와 표현 수준을 참고하는 4순위 근거로만 사용한다.",
        },
        "candidate_usage_policy": {
            "use_as_candidate_only": True,
            "rule": "이 Knowledge Pack의 액터, 유즈케이스, 상태, 프로세스, 기능, 정책 후보는 정답이 아니라 출발점이다.",
            "adoption_conditions": [
                "현재 주제의 첨부 요구사항 또는 첨부 참고자료와 직접 연결된다.",
                "현재 작성 중인 유즈케이스, 프로세스, 기능, 정책 계층 중 하나에 명확히 연결된다.",
                "샘플/템플릿의 작성 밀도와 장 구조를 벗어나지 않는다.",
                "범위를 넓히는 일반론이 아니라 현재 주제의 고객 과업 완료에 필요하다.",
            ],
            "rejection_conditions": [
                "2~4순위 보조/참고 근거에만 있고 1순위 첨부·사내·요구사항 근거가 약하다.",
                "현재 주제의 직접 범위가 아니라 인접 업무에 가깝다.",
                "후속 상세 설계, API, DB, 화면 UI 상세로 내려가야 하는 내용이다.",
                "프로세스나 기능과 연결되지 않는 독립 정책 후보이다.",
            ],
        },
        "topic_contract": build_topic_contract(topic, requirements, references),
        "source_profile": {
            "requirements_count": len(requirements),
            "references_count": len(references),
            "primary_reference_count": len(primary),
            "auxiliary_web_reference_count": len(auxiliary),
            "source_mix": source_mix(references),
            "authority_tier_mix": authority_tier_mix(references),
            "requirement_ids": compact_requirement_ids(requirements),
            "primary_sources": [source_name(item) for item in primary[:10]],
            "auxiliary_sources": [source_name(item) for item in auxiliary[:10]],
        },
        "topic_direction_milestone": topic_direction_milestone,
        "topic_direction_strategy": topic_direction_strategy,
        "topic_direction_agent_guidance": topic_direction_agent_guidance,
        "authoritative_signals": build_authoritative_signals(topic, requirements, primary),
        "tk_core_orientations": tk_core_orientations,
        "tk_process_function_guidance": tk_process_function_guidance,
        "auxiliary_web_signals": build_auxiliary_web_signals(auxiliary),
        "topic_axes": build_topic_axes(topic, requirements, references),
        "chapter_guidance": build_chapter_guidance(topic, requirements, references),
        "candidate_inventory": build_candidate_inventory(topic, requirements, references),
        "evidence_gaps": build_pack_evidence_gaps(topic, requirements, primary, auxiliary),
        "topic_evidence_map": compact_topic_evidence_map(topic_evidence_map),
    }
    return pack


class SimpleContext:
    def __init__(self, *, topic: str, requirements: Sequence[object], references: Sequence[object]):
        self.topic = topic
        self.requirements = requirements
        self.references = references


def empty_spec(topic: str) -> dict:
    return {
        "meta": {"topic": topic},
        "overview": {"scope": [], "principles": []},
        "terms": [],
        "actors": [],
        "usecases": [],
        "states": [],
        "state_transitions": [],
        "processes": [],
        "functions": [],
        "policy_groups": [],
        "policy_details": [],
        "final_check": [],
    }


def seed_learning_from_sources(topic: str, requirements: Sequence[object], references: Sequence[object]) -> dict:
    return {
        "topic": topic,
        "customer_tasks": unique_texts(
            [getattr(item, "detail_name", "") for item in requirements]
            + [signal for ref in references for signal in getattr(ref, "signals", ()) or () if has_any(signal, ("고객", "신청", "조회", "변경", "해지", "결제", "사용"))]
        )[:12],
        "policy_risks": unique_texts(
            [getattr(item, "detail_description", "") for item in requirements if has_any(getattr(item, "detail_description", ""), POLICY_KEYWORDS)]
            + [signal for ref in references for signal in getattr(ref, "signals", ()) or () if has_any(signal, POLICY_KEYWORDS)]
        )[:12],
        "bss_implications": unique_texts(
            [signal for ref in references for signal in getattr(ref, "signals", ()) or () if has_any(signal, ("BSS", "연계", "판정", "인증", "원장", "회신"))]
        )[:10],
    }


def build_authoritative_signals(topic: str, requirements: Sequence[object], primary_references: Sequence[object]) -> dict:
    return {
        "direct_scope": unique_texts(
            [getattr(item, "depth4", "") for item in requirements]
            + [getattr(item, "detail_name", "") for item in requirements[:20]]
        )[:14]
        or [topic],
        "requirement_summary": unique_texts(
            compact_sentence(getattr(item, "detail_description", "") or getattr(item, "detail_name", ""))
            for item in requirements
        )[:16],
        "attached_reference_signals": unique_texts(
            signal
            for item in primary_references
            for signal in getattr(item, "signals", ()) or ()
        )[:20],
        "attached_reference_evidence": unique_texts(
            evidence
            for item in primary_references
            for evidence in getattr(item, "evidence", ()) or ()
        )[:14],
    }


def build_tk_core_orientations(
    topic: str,
    primary_references: Sequence[object],
    requirements: Sequence[object] | None = None,
    limit: int = 8,
) -> List[dict]:
    """Extract TK PDF 핵심 지향점 as first-class authoring direction.

    The TK PDFs are table-heavy, so this keeps both normalized signals and a
    short source excerpt. Writers should use this as direction, not as a
    policy value to copy verbatim.
    """

    context_keywords = topic_context_keywords(topic, requirements or [])
    ranked_rows: List[tuple[int, dict]] = []
    for item in primary_references:
        if not is_tk_reference(item):
            continue
        excerpts = tk_core_orientation_excerpts(item)
        if not excerpts:
            continue
        candidates = unique_texts(
            [
                candidate
                for excerpt in excerpts
                for candidate in extract_tk_orientation_candidates(excerpt)
            ]
            + [
                signal
                for signal in getattr(item, "signals", ()) or ()
                if is_useful_orientation_candidate(signal)
            ]
        )[:12]
        scored_points: List[tuple[int, List[str], str]] = []
        for candidate in candidates:
            point_score, matched_keywords = tk_orientation_point_score(candidate, item, context_keywords)
            if point_score < TK_ORIENTATION_POINT_MIN_SCORE:
                continue
            scored_points.append((point_score, matched_keywords, candidate))
        if not scored_points:
            continue
        scored_points.sort(key=lambda scored: (scored[0], len(scored[2])), reverse=True)
        core_points = [candidate for _, _, candidate in scored_points[:5]]
        matched_keywords = unique_texts(
            keyword for _, keywords, _ in scored_points[:5] for keyword in keywords
        )[:10]
        relevance = tk_topic_affinity_score(topic, item, context_keywords) + scored_points[0][0]
        name = source_name(item)
        row = {
            "source_name": name,
            "source_authority": reference_authority(item),
            "authority_tier": evidence_authority_tier_for_authority(reference_authority(item)),
            "topic_relevance": relevance,
            "matched_keywords": matched_keywords,
            "core_points": core_points,
            "point_matches": [
                {"text": candidate, "score": score, "matched_keywords": keywords[:6]}
                for score, keywords, candidate in scored_points[:5]
            ],
            "evidence_excerpt": compact_sentence(excerpts[0], 520),
            "mapping_rule": "TK 하나의 핵심 지향점은 여러 정책 주제에 나뉘어 반영될 수 있으므로, 현재 주제·상세 요구사항과 직접 맞는 지향점 문장만 사용한다.",
            "usage_rule": "TK 핵심 지향점은 작성 방향과 누락 점검 기준으로 사용하고, 요구사항·템플릿·샘플과 상충하면 요구사항·템플릿·샘플을 우선한다.",
        }
        ranked_rows.append((relevance, row))
    ranked_rows.sort(key=lambda item: (item[0], str(item[1].get("source_name", ""))), reverse=True)
    return [row for _, row in ranked_rows[:limit]]


def tk_topic_affinity_score(topic: str, item: object, context_keywords: Sequence[str] | None = None) -> int:
    keywords = list(context_keywords or topic_focus_keywords(topic))
    name = source_name(item)
    text = reference_text_for_matching(item)
    score = int(getattr(item, "score", 0) or 0) // 20
    for keyword in keywords:
        if not keyword:
            continue
        if has_any(name, (keyword,)):
            score += 80
        elif has_any(text, (keyword,)):
            score += 14
    return score


def tk_orientation_point_score(candidate: str, item: object, context_keywords: Sequence[str]) -> tuple[int, List[str]]:
    """Score a single TK orientation point against the current policy topic.

    TK PDFs are broader than policy modules. A source may be relevant to many
    modules, but only some orientation sentences should flow into each module.
    This point-level score prevents a whole TK PDF from being injected into a
    topic just because the source file was generally related.
    """

    point_text = str(candidate or "")
    source_text = reference_text_for_matching(item)
    source_name_text = source_name(item)
    matched: List[str] = []
    point_score = 0
    source_bonus = 0
    for keyword in context_keywords:
        if not keyword:
            continue
        if has_any(point_text, (keyword,)):
            point_score += 18 + min(len(keyword), 8)
            matched.append(keyword)
        elif has_any(source_name_text, (keyword,)):
            source_bonus = max(source_bonus, 8)
        elif has_any(source_text, (keyword,)):
            source_bonus = max(source_bonus, 3)
    if point_score <= 0:
        return 0, []
    score = point_score + source_bonus
    if has_any(point_text, ("고객", "과업", "셀프", "통합", "AI", "BSS", "상태", "이력", "추천", "개인화")):
        score += 4
    if not matched and has_any(point_text, ("공통", "표준", "품질", "거버넌스", "정합성")):
        score += 6
    return score, unique_texts(matched)


def topic_context_keywords(topic: str, requirements: Sequence[object], limit: int = 36) -> List[str]:
    """Build matching keywords from topic and detailed requirements.

    Requirement priority values are intentionally ignored; the detailed
    requirement names/descriptions carry the actual scope signal.
    """

    primary_keywords = topic_focus_keywords(topic)
    topic_compact = re.sub(r"[\s/·,_-]+", "", str(topic or ""))
    if "고객센터" in topic_compact:
        primary_keywords.extend(["고객센터", "고객지원", "상담", "문의", "CS", "셀프"])
    if "청구" in topic_compact or "수납" in topic_compact:
        primary_keywords.extend(["청구", "수납", "납부", "요금"])
    if "결제" in topic_compact:
        primary_keywords.extend(["결제", "결제수단", "간편결제", "PG"])
    if "추천" in topic_compact:
        primary_keywords.extend(["추천", "오퍼", "개인화", "적합"])
    if "상품목록" in topic_compact:
        primary_keywords.extend(["상품", "목록", "전시", "필터", "카테고리"])
    primary_normalized = {keyword.casefold() for keyword in primary_keywords}
    keywords: List[str] = list(primary_keywords)
    for item in requirements:
        keywords.extend(
            extract_context_keywords(
                " ".join(
                    str(value or "")
                    for value in (
                        getattr(item, "depth3", ""),
                        getattr(item, "depth4", ""),
                        getattr(item, "detail_name", ""),
                        getattr(item, "detail_description", ""),
                    )
                )
            )
        )
    generic = {
        "고객",
        "고객이",
        "고객의",
        "서비스",
        "정책",
        "기준",
        "관리",
        "처리",
        "정보",
        "기능",
        "화면",
        "제공",
        "확인",
        "사용",
        "이용",
        "하도록",
        "있도록",
        "한다",
        "된다",
        "아니라",
        "중심",
        "중심으로",
        "기반",
        "목적",
        "안내",
        "진입",
        "단계",
        "완료",
        "결과",
        "선택",
        "핵심",
        "다음",
        "흐름",
        "주문",
        "상태",
        "실패",
        "재시도",
        "혜택",
        "멤버십",
        "상담",
        "문의",
        "요청",
        "현재",
        "이후",
        "자동",
        "취소",
        "청구",
        "구성",
        "표준화",
        "정보는",
        "이해할",
        "대상",
        "통합",
        "채널",
        "요구",
        "사항",
        "상세",
    }
    result = []
    for keyword in unique_texts(keywords):
        text = str(keyword or "").strip()
        if len(text) < 2:
            continue
        if text.casefold() in generic and text.casefold() not in primary_normalized:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def extract_context_keywords(text: object) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    values: List[str] = []
    for token in re.split(r"[^0-9A-Za-z가-힣]+", cleaned):
        token = token.strip()
        if len(token) >= 2:
            values.append(token)
    compact_phrases = re.findall(r"[0-9A-Za-z가-힣]+(?:[·/ ][0-9A-Za-z가-힣]+){1,3}", cleaned)
    values.extend(phrase.strip() for phrase in compact_phrases if len(phrase.strip()) >= 3)
    return unique_texts(values)


def is_tk_reference(item: object) -> bool:
    name = source_name(item)
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", name.casefold())
    return normalized.startswith("tkch") or "tkch" in normalized


def tk_core_orientation_excerpts(item: object) -> List[str]:
    texts: List[str] = []
    source_text = str(getattr(item, "source_text", "") or "")
    if source_text:
        texts.extend(extract_core_orientation_windows(source_text))
    for evidence in getattr(item, "evidence", ()) or ():
        evidence_text = str(evidence or "")
        if has_core_orientation_marker(evidence_text):
            texts.extend(extract_core_orientation_windows(evidence_text) or [evidence_text])
    return unique_texts(compact_core_orientation_text(text) for text in texts)[:3]


def extract_core_orientation_windows(text: object) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    windows: List[str] = []
    markers = list(re.finditer(r"(?:상위\s*)?핵심\s*지향(?:점)?|지향점\s*및\s*기대\s*효과", cleaned))
    for marker in markers:
        start = max(0, marker.start() - 80)
        tail = cleaned[marker.end() :]
        end_match = re.search(r"\s(?:주요\s*프로세스|타\s*과제\s*영향도|정량적\s*효과|과제\s*ID|관계\s*유형|$)", tail)
        end = marker.end() + (end_match.start() if end_match else min(len(tail), 1300))
        windows.append(cleaned[start:end])
    return windows


def extract_tk_orientation_candidates(excerpt: object) -> List[str]:
    text = compact_core_orientation_text(excerpt)
    text = re.sub(r".*?(?:상위\s*)?핵심\s*지향(?:점)?", "", text, count=1)
    text = re.sub(
        r"^(?:\s*To[-\s]*Do|\s*기대\s*효과|\s*측정\s*지표|\s*대표\s*KPI|\s*KPI|\s*\(?KPI\)?|\s*상세\s*설명|\s*주요\s*)+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    segments = re.split(r"\s+(?=\d+\s+)", text)
    candidates: List[str] = []
    for segment in segments:
        segment = re.sub(r"^\d+\s*", "", segment).strip(" -:·")
        if not segment:
            continue
        candidate = orientation_headline(segment)
        if candidate and is_useful_orientation_candidate(candidate):
            candidates.append(candidate)
    return unique_texts(candidates)[:5]


def orientation_headline(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"^(?:\(?KPI\)?|측정\s*지표|대표\s*KPI|상세\s*설명|주요\s*To\s*Do)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:To\s*Do|기대\s*효과|측정\s*지표|대표\s*KPI|KPI)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\(\s*\+\s*기존\s*회원\s*가입\s*전환\s*\)", "", cleaned).strip()
    if not cleaned:
        return ""
    if has_any(cleaned[:80], ("파일 변경됨", "작성자", "문서 링크", "관계 유형")):
        return ""
    full_sentence_match = re.match(r"(.{12,180}?(?:한다|된다|전환한다)\s*[.。])", cleaned)
    if full_sentence_match:
        return compact_sentence(full_sentence_match.group(1).rstrip(" .。"), 140)
    sentence_match = re.match(r"(.{12,120}?(?:한다|된다|제공|체계|구조|전환|경험|확보|안내|관리|통합|재구성|설계|지원))(?=\s|$)", cleaned)
    if sentence_match:
        return compact_sentence(sentence_match.group(1), 120)
    words = cleaned.split()
    return compact_sentence(" ".join(words[:12]), 120)


def is_useful_orientation_candidate(text: object) -> bool:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" -:·")
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", cleaned.casefold())
    if normalized in {"todo", "핵심지향점", "상위핵심지향", "kpi", "측정지표", "기대효과"}:
        return False
    if len(cleaned) < 5:
        return False
    if re.match(
        r"^(?:예\s*[:：]|팀\s|문서\s|연관\s*문서|파일\s*변경|번호\s|작성자\s|관계\s*유형|TK[_\s]|검색\s*및\s*정보\s*탐색|셀프\s*해결\s*및\s*후속\s*행동|예외\s*해결|AI\s*어시스턴트\s*기반\s*문제|자산\s*이용\s*가치|미사용\s*자산|통합\s*이력)",
        cleaned,
        re.IGNORECASE,
    ):
        return False
    if re.match(r"^\d{1,4}\s*[,년.]", cleaned):
        return False
    if has_any(cleaned[:120], ("문서 링크", "피그마 링크", "마지막 업데이트", "Confluence", "[p.", "MBR", "현 상태", "Root Cause", "Pain Point")):
        return False
    process_like_markers = (
        "모듈",
        "버튼 클릭",
        "비로그인 탐색",
        "완료 및 사후 관리",
        "납부 이력 조회",
        "계약 상세 정보 확인",
        "비교 대상 식별",
        "AI 추천안 생성",
        "상품 목록 조회상품",
        "상세 진입",
        "미납 납부",
        "결합 문의",
    )
    if has_any(cleaned, process_like_markers):
        return False
    hard_negative_markers = ("부족", "미흡", "연결되지", "유지되지", "반복 입력")
    if has_any(cleaned, hard_negative_markers):
        return False
    negative_markers = ("상이", "다르게", "달라", "제한적", "불편", "낮", "어렵", "어려", "분산되어", "많고", "머물고", "문제")
    positive_markers = ("전환", "구조", "체계", "제공", "확보", "관리", "통합", "재구성", "경험", "설계", "지원", "완료", "안내", "확대", "개선", "표준", "이해", "가입")
    strong_positive_markers = ("전환", "바꿔", "만들", "구현", "확대", "확보", "재구성", "설계", "지원", "개선", "표준화")
    if has_any(cleaned, negative_markers) and not has_any(cleaned, strong_positive_markers):
        return False
    if len(cleaned) < 8 and not has_any(cleaned, positive_markers):
        return False
    return True


def compact_core_orientation_text(text: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
    return cleaned


def has_core_orientation_marker(text: object) -> bool:
    return bool(re.search(r"(?:상위\s*)?핵심\s*지향(?:점)?|지향점\s*및\s*기대\s*효과", str(text or "")))


def build_tk_process_function_guidance(
    topic: str,
    primary_references: Sequence[object],
    requirements: Sequence[object] | None = None,
    limit: int = 12,
) -> List[dict]:
    """Extract TK '주요 프로세스 및 기능' rows as design candidates.

    A TK document can cover multiple policy topics. This therefore ranks rows
    at process/function level instead of injecting the whole TK section.
    """

    context_keywords = topic_context_keywords(topic, requirements or [])
    ranked_rows: List[tuple[int, dict]] = []
    for item in primary_references:
        if not is_tk_reference(item):
            continue
        if not tk_process_source_matches_topic(topic, item):
            continue
        excerpts = tk_process_function_excerpts(item)
        if not excerpts:
            continue
        for excerpt in excerpts:
            for candidate in extract_tk_process_function_candidates(excerpt):
                score, matched_keywords = tk_process_function_candidate_score(candidate, item, topic, context_keywords)
                if score < TK_PROCESS_FUNCTION_MIN_SCORE:
                    continue
                row = {
                    "source_name": source_name(item),
                    "source_authority": reference_authority(item),
                    "authority_tier": evidence_authority_tier_for_authority(reference_authority(item)),
                    "topic_relevance": score,
                    "matched_keywords": matched_keywords,
                    "process_name": candidate.get("process_name", ""),
                    "major_functions": candidate.get("major_functions", [])[:6],
                    "source_excerpt": compact_sentence(candidate.get("source_excerpt", "") or excerpt, 420),
                    "mapping_rule": "TK 하나의 주요 프로세스·기능 행은 여러 정책 주제에 나뉘어 반영될 수 있으므로, 현재 주제·상세 요구사항과 직접 맞는 행만 사용한다.",
                    "usage_rule": "TK 주요 프로세스·기능은 유즈케이스·프로세스·기능 후보를 정렬하는 보조 설계 근거로 사용하고, 요구사항·템플릿·샘플과 상충하면 요구사항·템플릿·샘플을 우선한다.",
                }
                ranked_rows.append((score, row))
    ranked_rows.sort(
        key=lambda item: (
            item[0],
            str(item[1].get("source_name", "")),
            str(item[1].get("process_name", "")),
        ),
        reverse=True,
    )
    deduped: List[dict] = []
    seen: set[str] = set()
    for _, row in ranked_rows:
        key = re.sub(r"\s+", "", f"{row.get('source_name', '')}|{row.get('process_name', '')}|{row.get('major_functions', [])}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def tk_process_function_excerpts(item: object) -> List[str]:
    texts: List[str] = []
    source_text = str(getattr(item, "source_text", "") or "")
    if source_text:
        texts.extend(extract_process_function_windows(source_text))
    for evidence in getattr(item, "evidence", ()) or ():
        evidence_text = str(evidence or "")
        if has_process_function_marker(evidence_text):
            texts.extend(extract_process_function_windows(evidence_text) or [evidence_text])
    return unique_texts(compact_core_orientation_text(text) for text in texts)[:4]


def tk_process_source_matches_topic(topic: str, item: object) -> bool:
    source = re.sub(r"[^0-9a-z가-힣]+", "", source_name(item).casefold())
    compact_topic = re.sub(r"[^0-9a-z가-힣]+", "", str(topic or "").casefold())
    if compact_topic and compact_topic in source:
        return True
    topic_compact = re.sub(r"[\s/·,_-]+", "", str(topic or ""))
    aliases = {
        "AI검색": ("ai", "검색", "탐색", "agent", "추천"),
        "추천": ("추천", "개인화", "오퍼", "ai"),
        "전시관리기능": ("전시", "노출", "홈", "배너", "관리"),
        "상품목록": ("상품", "목록", "탐색", "전시"),
        "상품상세담기": ("상품", "상세", "담기"),
        "상품서비스혜택이용공유": ("상품", "서비스", "혜택", "공유"),
        "데이터트래킹체계": ("데이터", "트래킹", "이벤트"),
    }
    keywords = [keyword for keyword in topic_focus_keywords(topic) if not is_weak_tk_process_keyword(keyword)]
    keywords.extend(aliases.get(topic_compact, ()))
    keywords = unique_texts(keywords)
    hit_count = sum(1 for keyword in keywords if keyword and re.sub(r"[^0-9a-z가-힣]+", "", str(keyword).casefold()) in source)
    if topic_compact in {"AI검색", "추천"}:
        return hit_count >= 2
    return hit_count >= 1


def has_process_function_marker(text: object) -> bool:
    return bool(re.search(r"주요\s*프로세스\s*및\s*기능", str(text or "")))


def extract_process_function_windows(text: object) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    windows: List[str] = []
    markers = list(re.finditer(r"주요\s*프로세스\s*및\s*기능", cleaned))
    end_pattern = r"\s(?:기대\s*효과|정량적\s*효과|측정\s*지표|대표\s*KPI|타\s*과제\s*영향도|관계\s*유형|과제\s*ID|파일\s*변경됨|변경\s*이력|$)"
    for marker in markers:
        max_end = min(len(cleaned), marker.end() + 3600)
        tail = cleaned[marker.end() : max_end]
        end = max_end
        for end_match in re.finditer(end_pattern, tail):
            if end_match.start() >= 500:
                end = marker.end() + end_match.start()
                break
        start = max(0, marker.start() - 40)
        windows.append(cleaned[start:end])
    return windows


def extract_tk_process_function_candidates(excerpt: object) -> List[dict]:
    text = compact_core_orientation_text(excerpt)
    text = re.sub(r".*?주요\s*프로세스\s*및\s*기능", "", text, count=1)
    text = re.sub(
        r"\b(?:번호|No\.?|구분|상위\s*여정|프로세스\s*명|프로세스명|주요\s*기능|설계\s*포인트|FE\s*/\s*BO|FE/BO)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text).strip(" -:·")
    if not text:
        return []
    segments = re.split(r"\s+(?=(?:\d{1,2}[.)]?|FE\s*/?\s*BO|FE|BO)\s+)", text)
    if len(segments) <= 1:
        segments = re.split(r"\s{2,}|(?<=\.)\s+", text)
    candidates: List[dict] = []
    for segment in segments:
        candidate = parse_tk_process_function_segment(segment)
        if candidate:
            candidates.append(candidate)
    return candidates[:18]


def parse_tk_process_function_segment(segment: object) -> dict | None:
    cleaned = re.sub(r"\s+", " ", str(segment or "")).strip(" -:·")
    cleaned = re.sub(r"^(?:\d{1,2}[.)]?|FE\s*/?\s*BO|FE|BO)\s+", "", cleaned, flags=re.IGNORECASE).strip(" -:·")
    if len(cleaned) < 12:
        return None
    if has_any(cleaned[:120], ("문서 링크", "피그마 링크", "파일 변경됨", "작성자", "마지막 업데이트", "관계 유형")):
        return None
    action_terms = (
        "진입",
        "입력",
        "분석",
        "분해",
        "검색",
        "탐색",
        "조회",
        "확인",
        "선택",
        "적용",
        "관리",
        "처리",
        "등록",
        "수정",
        "삭제",
        "발급",
        "사용",
        "노출",
        "설정",
        "저장",
        "안내",
        "추천",
        "비교",
        "신청",
        "접수",
        "검증",
        "승인",
        "배포",
        "반영",
        "결제",
        "가입",
        "변경",
        "해지",
        "환불",
        "취소",
        "반품",
        "교환",
    )
    action_pattern = "|".join(action_terms)
    match = re.match(rf"(.{{4,70}}?(?:{action_pattern}))(?=\s|$)", cleaned)
    if match:
        process_name = compact_sentence(match.group(1), 70).strip(" -:·")
        feature_text = cleaned[match.end() :].strip(" -:·")
        extension_match = re.match(rf"^(및|/|·)\s+(.{{2,24}}?(?:{action_pattern}))(?=\s|$)", feature_text)
        if extension_match and len(f"{process_name} {extension_match.group(1)} {extension_match.group(2)}") <= 70:
            process_name = compact_sentence(
                f"{process_name} {extension_match.group(1)} {extension_match.group(2)}",
                70,
            ).strip(" -:·")
            feature_text = feature_text[extension_match.end() :].strip(" -:·")
    else:
        words = cleaned.split()
        process_name = compact_sentence(" ".join(words[:6]), 70)
        feature_text = " ".join(words[6:])
    if len(process_name) < 3:
        return None
    functions = split_major_function_phrases(feature_text or cleaned, 6)
    if not functions:
        return None
    return {
        "process_name": process_name,
        "major_functions": functions,
        "source_excerpt": compact_sentence(cleaned, 420),
    }


def split_major_function_phrases(text: object, limit: int = 6) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" -:·")
    if not cleaned:
        return []
    boundary_terms = (
        "제공",
        "조회",
        "노출",
        "선택",
        "관리",
        "안내",
        "처리",
        "정의",
        "설계",
        "표준화",
        "연결",
        "저장",
        "확인",
        "입력",
        "추천",
        "생성",
        "분기",
        "수집",
        "표시",
        "적용",
        "발급",
        "등록",
        "수정",
        "삭제",
        "검수",
        "승인",
        "배포",
        "반영",
        "유도",
        "접수",
        "산정",
        "분석",
        "분류",
    )
    term_pattern = "|".join(re.escape(term) for term in boundary_terms)
    marked = re.sub(rf"({term_pattern})(?=\s+)", r"\1|", cleaned)
    parts = re.split(r"\|\s*", marked)
    phrases: List[str] = []
    for part in parts:
        phrase = compact_sentence(part, 90).strip(" -:·")
        if len(phrase) < 3:
            continue
        if re.match(r"^(?:\d{1,2}[.)]?|번호|구분|프로세스|주요)$", phrase):
            continue
        phrases.append(phrase)
        if len(phrases) >= limit:
            break
    return unique_texts(phrases)[:limit]


def tk_process_function_candidate_score(
    candidate: Mapping[str, object],
    item: object,
    topic: str,
    context_keywords: Sequence[str],
) -> tuple[int, List[str]]:
    major_functions = candidate.get("major_functions", [])
    major_functions = major_functions if isinstance(major_functions, list) else []
    candidate_text = " ".join(
        [str(candidate.get("process_name", ""))]
        + [str(value or "") for value in major_functions]
    )
    source_name_text = source_name(item)
    compact_topic = re.sub(r"[^0-9a-z가-힣]+", "", str(topic or "").casefold())
    compact_source = re.sub(r"[^0-9a-z가-힣]+", "", source_name_text.casefold())
    source_exact = bool(compact_topic and compact_topic in compact_source)
    matched: List[str] = []
    direct_score = 0
    source_score = 0
    for keyword in context_keywords:
        if not keyword:
            continue
        if has_any(candidate_text, (keyword,)) and not is_weak_tk_process_keyword(keyword):
            direct_score += 16 + min(len(keyword), 8)
            matched.append(keyword)
        elif has_any(source_name_text, (keyword,)):
            source_score = max(source_score, 10)
    if direct_score <= 0 and (not source_exact or tk_process_function_conflicts_with_topic(candidate_text, context_keywords)):
        return 0, []
    score = direct_score + source_score
    if source_exact:
        score += 14
    if has_any(candidate_text, ("조회", "확인", "선택", "검증", "신청", "처리", "저장", "반영", "안내", "관리", "추천", "검색")):
        score += 6
    if not major_functions:
        score -= 10
    if direct_score <= 0 and score < TK_PROCESS_FUNCTION_MIN_SCORE:
        return 0, []
    return score, unique_texts(matched)


def is_weak_tk_process_keyword(keyword: object) -> bool:
    text = re.sub(r"[\s/·,_-]+", "", str(keyword or "")).casefold()
    return text in {
        "ai",
        "서비스",
        "이용",
        "관리",
        "기능",
        "정보",
        "고객",
        "통합",
        "채널",
        "사용",
        "확인",
        "처리",
        "상품",
    }


def tk_process_function_conflicts_with_topic(candidate_text: object, context_keywords: Sequence[str]) -> bool:
    haystack = str(candidate_text or "")
    context = " ".join(str(keyword or "") for keyword in context_keywords)
    domain_groups = (
        ("청구", "납부", "수납", "미납", "요금"),
        ("배송", "교환", "반품", "회수"),
        ("결제", "PG", "할인", "시뮬레이션"),
        ("쿠폰", "이용권", "포인트", "멤버십"),
        ("회원", "가입", "탈퇴", "회원정보"),
        ("주문", "계약", "장바구니", "카트", "선물"),
        ("매장", "공지", "FAQ", "고객센터", "상담"),
    )
    for group in domain_groups:
        if has_any(haystack, group) and not has_any(context, group):
            return True
    return False


def build_auxiliary_web_signals(auxiliary_references: Sequence[object]) -> dict:
    return {
        "usage_rule": "1순위 근거와 상충하면 사용하지 않는다.",
        "authority_mix": source_mix(auxiliary_references),
        "authority_tier_mix": authority_tier_mix(auxiliary_references),
        "signals": unique_texts(
            signal
            for item in auxiliary_references
            for signal in getattr(item, "signals", ()) or ()
        )[:18],
        "evidence": unique_texts(
            evidence
            for item in auxiliary_references
            for evidence in getattr(item, "evidence", ()) or ()
        )[:10],
        "sources": [source_name(item) for item in auxiliary_references[:8]],
    }


def build_topic_axes(topic: str, requirements: Sequence[object], references: Sequence[object]) -> dict:
    corpus = source_corpus(topic, requirements, references)
    return {
        "customer_task_axes": keyword_hits(corpus, CUSTOMER_TASK_AXES),
        "state_axes": keyword_hits(corpus, STATE_AXES),
        "process_axes": keyword_hits(corpus, PROCESS_AXES),
        "function_axes": keyword_hits(corpus, FUNCTION_AXES),
        "policy_axes": keyword_hits(corpus, POLICY_AXES),
        "channel_axes": keyword_hits(corpus, CHANNEL_AXES),
    }


def build_topic_contract(topic: str, requirements: Sequence[object], references: Sequence[object]) -> dict:
    """Create the per-topic authoring contract used to keep modules separated.

    This is intentionally derived from scoped requirement detail names and
    descriptions. External/reference knowledge can add focus questions, but it
    must not redefine the topic boundary.
    """
    axes = build_topic_axes(topic, requirements, references)
    triggers = domain_candidate_triggers(topic_trigger_corpus(topic, requirements))
    requirement_names = requirement_detail_names(requirements)
    requirement_summaries = requirement_detail_summaries(requirements)
    direct_scope = build_direct_scope(requirements, topic)
    adjacent = adjacent_topics_for_topic(topic, requirements)
    return {
        "topic_definition": topic_definition(topic, requirement_names),
        "writing_goal": writing_goals(topic, axes),
        "requirement_basis": "작성 범위는 요구사항 ID나 임의 우선순위가 아니라 상세 요구사항명과 상세 요구사항 설명을 기준으로 해석한다.",
        "direct_scope": direct_scope,
        "must_cover": must_cover_items(topic, requirement_names, requirement_summaries, axes, triggers),
        "must_not_cover": must_not_cover_items(topic, adjacent),
        "focus_points": focus_points_for_topic(topic, axes, triggers),
        "core_policy_questions": core_policy_questions_for_topic(triggers),
        "adjacent_topics": adjacent,
        "boundary_rule": boundary_rule_for_topic(topic, adjacent),
    }


def requirement_detail_names(requirements: Sequence[object]) -> List[str]:
    return unique_texts(getattr(item, "detail_name", "") for item in requirements)[:16]


def requirement_detail_summaries(requirements: Sequence[object]) -> List[str]:
    return unique_texts(compact_sentence(getattr(item, "detail_description", ""), 150) for item in requirements)[:10]


def build_direct_scope(requirements: Sequence[object], topic: str) -> List[str]:
    scopes = unique_texts(
        [getattr(item, "depth4", "") for item in requirements]
        + [getattr(item, "detail_name", "") for item in requirements]
    )
    return scopes[:18] or [topic]


def topic_definition(topic: str, requirement_names: Sequence[str]) -> str:
    if requirement_names:
        anchor = ", ".join(requirement_names[:3])
        return f"{topic} 정책서는 {anchor} 등을 중심으로 고객·운영자·연계 시스템이 업무를 완료하기 위한 범위, 상태, 처리 흐름, 기능, 정책 기준을 정의한다."
    return f"{topic} 정책서는 해당 주제의 고객 과업을 완료하기 위한 범위, 상태, 처리 흐름, 기능, 정책 기준을 정의한다."


def writing_goals(topic: str, axes: Mapping[str, Sequence[str]]) -> List[str]:
    goals = [
        f"개발/QA가 {topic} 업무의 허용 조건, 제한 조건, 예외 처리, 이력 기준을 테스트 케이스로 전환할 수 있게 한다.",
        "고객 과업 시작부터 완료까지 유즈케이스, 상태, 프로세스, 기능, 정책 항목의 연결을 끊기지 않게 한다.",
        "BSS·연계 시스템의 판정, 상태 반영, 결과 회신, 이력 저장이 필요한 지점을 문서 안에 남긴다.",
    ]
    policy_axes = list(axes.get("policy_axes", []) or [])
    if policy_axes:
        goals.append(f"정책 항목은 {', '.join(policy_axes[:5])} 축을 기준으로 실제 판단값 또는 판단 조건을 갖게 한다.")
    return goals


def must_cover_items(
    topic: str,
    requirement_names: Sequence[str],
    requirement_summaries: Sequence[str],
    axes: Mapping[str, Sequence[str]],
    triggers: Sequence[str],
) -> List[str]:
    items = []
    if requirement_names:
        items.extend(f"상세 요구사항명 기준: {name}" for name in requirement_names[:12])
    elif requirement_summaries:
        items.extend(f"상세 요구사항 설명 기준: {summary}" for summary in requirement_summaries[:6])
    else:
        items.append(f"{topic}의 직접 고객 과업과 처리 결과")
    for axis_key, label in (
        ("customer_task_axes", "고객 과업 축"),
        ("state_axes", "상태 판단 축"),
        ("process_axes", "프로세스 축"),
        ("function_axes", "기능 처리 축"),
        ("policy_axes", "정책 판단 축"),
    ):
        values = list(axes.get(axis_key, []) or [])
        if values:
            items.append(f"{label}: {', '.join(values[:6])}")
    if triggers:
        items.append(f"도메인 주안점: {', '.join(triggers[:8])}")
    return unique_texts(items)[:22]


def must_not_cover_items(topic: str, adjacent_topics: Sequence[str]) -> List[str]:
    items = [
        "상세 요구사항명과 상세 요구사항 설명에 직접 없는 인접 정책서 업무를 현재 문서의 핵심 범위로 확장하지 않는다.",
        "API 필드, DB 컬럼, 화면 UI 상세, 운영자 화면 설계, 배치 설계로 내려가지 않는다.",
        "2~4순위 외부 지식만으로 기간, 횟수, 금액, 혜택명, 가격, 운영 조건을 확정 정책값으로 작성하지 않는다.",
        "요구사항 문구를 그대로 복사하지 않고 고객 과업, 상태, 프로세스, 기능, 정책 판단 기준으로 재구성한다.",
    ]
    for adjacent in adjacent_topics[:5]:
        items.append(f"인접 정책서 '{adjacent}'의 고객 과업은 현재 문서에서 전체 절차로 작성하지 않고 연계 조건이나 전후 관계로만 다룬다.")
    return unique_texts(items)[:12]


def focus_points_for_topic(topic: str, axes: Mapping[str, Sequence[str]], triggers: Sequence[str]) -> List[str]:
    points = [
        "요구사항 상세명/상세설명에서 고객이 완료해야 하는 업무 문제를 먼저 추출한다.",
        "유즈케이스는 절차 단계가 아니라 사람 액터의 업무 목표로 둔다.",
        "프로세스는 유즈케이스 목표를 완성하는 절차 흐름이며, 기능·정책 연결을 반드시 남긴다.",
    ]
    state_axes = list(axes.get("state_axes", []) or [])
    if state_axes:
        points.append(f"상태는 {', '.join(state_axes[:5])} 기준으로 기능 허용과 후속 처리를 결정할 때만 둔다.")
    policy_axes = list(axes.get("policy_axes", []) or [])
    if policy_axes:
        points.append(f"정책 항목은 {', '.join(policy_axes[:6])} 중 하나 이상의 실제 판단 기준을 포함한다.")
    if triggers:
        points.append(f"{topic} 작성 시 도메인 키워드({', '.join(triggers[:8])})가 범위 밖 일반론으로 확장되지 않도록 한다.")
    return unique_texts(points)[:10]


def core_policy_questions_for_topic(triggers: Sequence[str]) -> List[str]:
    questions = [
        "누가 할 수 있는가.",
        "어떤 상태 또는 조건에서 할 수 있는가.",
        "언제 제한되거나 보류되는가.",
        "실패하면 어떤 상태로 전환되고 어떻게 복구하는가.",
        "BSS 또는 연계 시스템은 어떤 판정, 상태 변경, 결과 회신을 하는가.",
        "고객에게 무엇을 언제 고지하는가.",
        "어떤 이력을 어느 업무 목적 기준으로 남기는가.",
    ]
    trigger_questions = {
        "결제": ["결제 승인 성공과 BSS 수납 반영 실패가 불일치하면 어떤 보류 상태와 재처리 기준을 둘 것인가."],
        "납부": ["청구 조회, 납부 요청, 수납 반영, 영수 확인을 어떤 상태와 이력으로 구분할 것인가."],
        "환불": ["환불 가능, 환불 불가, 환불 보류, 환불 완료 기준을 어떤 조건으로 나눌 것인가."],
        "배송": ["배송, 교환, 반품, 회수 상태를 주문/계약 상태와 어떻게 분리해 관리할 것인가."],
        "인증": ["인증 유효시간, 실패 제한, 재인증, 대리 권한 확인 기준은 무엇인가."],
        "쿠폰": ["쿠폰 발급, 사용 가능, 사용 완료, 만료, 복원 기준은 무엇인가."],
        "이용권": ["이용권 발급, 사용, 만료, 회수, 재발급 기준은 무엇인가."],
        "구독": ["정기결제, 일시중지, 해지 예약, 해지 완료 기준은 무엇인가."],
        "멤버십": ["등급, 바코드, 혜택 사용 가능 여부를 어떤 고객/회선 상태로 판단할 것인가."],
        "검색": ["AI/검색 결과가 직접 계약·결제·해지·환불을 확정하지 않도록 어떤 경계를 둘 것인가."],
        "추천": ["추천 후보 제외, 근거 표시, 고객 피드백 반영 기준은 무엇인가."],
        "알림": ["거래성/보안/마케팅 알림의 발송 대상, 동의, 빈도, 실패 재시도 기준은 무엇인가."],
        "회원": ["가입 가능 대상, 탈퇴 제한, 탈퇴 후 보관/분리/파기 기준은 무엇인가."],
        "포인트": ["포인트 적립, 사용, 차감, 복원, 소멸 기준은 무엇인가."],
        "혜택": ["혜택 사용, 공유, 양도, 중복, 회수 기준은 무엇인가."],
    }
    for trigger in triggers:
        questions.extend(trigger_questions.get(trigger, []))
    return unique_texts(questions)[:12]


def adjacent_topics_for_topic(topic: str, requirements: Sequence[object]) -> List[str]:
    topic_keywords = set(topic_focus_keywords(topic))
    requirement_text = topic_trigger_corpus(topic, requirements)
    scored: List[tuple[int, str]] = []
    for candidate in POLICY_TOPICS:
        if candidate == topic:
            continue
        candidate_keywords = topic_focus_keywords(candidate)
        overlap = len(topic_keywords.intersection(candidate_keywords))
        requirement_hit = 1 if has_any(requirement_text, candidate_keywords) else 0
        score = overlap * 2 + requirement_hit
        if score > 0:
            scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], POLICY_TOPICS.index(item[1])))
    return [candidate for _, candidate in scored[:6]]


def boundary_rule_for_topic(topic: str, adjacent_topics: Sequence[str]) -> str:
    if adjacent_topics:
        adjacent_text = ", ".join(adjacent_topics[:4])
        return f"{topic}의 상세 요구사항명/설명에 직접 포함된 고객 과업은 본문으로 작성하고, {adjacent_text} 등 인접 주제는 선행·후행 조건 또는 연계 결과로만 다룬다."
    return f"{topic}의 상세 요구사항명/설명에 직접 포함된 고객 과업만 본문 범위로 작성하고, 인접 업무는 선행·후행 조건 또는 연계 결과로만 다룬다."


def build_chapter_guidance(topic: str, requirements: Sequence[object], references: Sequence[object]) -> dict:
    axes = build_topic_axes(topic, requirements, references)
    policy_axes = axes["policy_axes"] or ["권한", "제한", "고지", "이력"]
    state_axes = axes["state_axes"] or ["신청 전", "진행 중", "완료", "제한", "취소"]
    return {
        "overview": [
            "첨부 요구사항 4depth 기준으로 직접 범위와 제외 범위를 먼저 고정한다.",
            "공개웹 지식은 채널 책임 경계를 보강할 때만 사용한다.",
        ],
        "terms": [
            "정책 판단값, 상태, 권한, 상품/혜택/결제 용어만 정의한다.",
            "공개웹에서만 나온 일반 마케팅 용어는 제외한다.",
        ],
        "actors": [
            "독립 책임 주체만 액터로 둔다.",
            "고객 상태나 등급은 액터가 아니라 상태·정책 조건으로 둔다.",
        ],
        "usecases": [
            "사람 액터가 완료하려는 상위 업무 목표를 유즈케이스로 둔다.",
            "검증, 저장, 알림, 조회 같은 내부 처리는 기능 또는 프로세스 단계로 내린다.",
        ],
        "state": [
            f"상태 후보는 {', '.join(state_axes[:6])} 축에서 고른다.",
            "상태 전이 이벤트에는 유즈케이스 흐름에서 발생한 상태 변화 업무 사건을 쓰고 추적성은 usecase_ids로 남긴다.",
        ],
        "process": [
            "process_target=Y인 사람 액터 유즈케이스를 세부 절차로 분해한다.",
            "시작, 조건 확인, 판단, 요청, 처리, 결과 안내, 이력 저장을 필요에 따라 포함한다.",
        ],
        "functions": [
            "프로세스를 수행하는 처리 역량을 기능으로 묶고, 세부 기능 구성은 짧은 하위 처리명으로 둔다.",
            "프로세스별 기능이 1개로만 끝나지 않도록 처리 목적별로 분해한다.",
        ],
        "policies": [
            f"정책 항목은 {', '.join(policy_axes[:8])} 같은 실제 판단값·조건·허용범위를 선언한다.",
            "기능 설명을 정책으로 쓰지 않는다.",
        ],
        "final_check": [
            "유즈케이스→프로세스→기능→정책 연결이 끊기지 않았는지 확인한다.",
            "1순위 근거와 상충하는 2~4순위 보조/참고 근거가 남아 있으면 제거한다.",
        ],
    }


def build_candidate_inventory(topic: str, requirements: Sequence[object], references: Sequence[object]) -> dict:
    corpus = candidate_source_corpus(topic, requirements, references)
    triggers = domain_candidate_triggers(topic)
    return {
        "actor_candidates": actor_candidates(corpus),
        "usecase_candidates": usecase_candidates(topic, requirements),
        "state_candidates": state_candidates(corpus, triggers),
        "process_patterns": process_patterns(corpus, triggers),
        "function_candidates": function_candidates(corpus, triggers),
        "policy_item_candidates": policy_item_candidates(corpus, triggers),
    }


def actor_candidates(corpus: str) -> List[str]:
    base = ["고객", "운영자", "채널 업무 시스템", "연계 시스템"]
    if has_any(corpus, ("법정대리인", "미성년")):
        base.append("법정대리인")
    if has_any(corpus, ("결제", "납부", "환불", "정기결제")):
        base.append("결제 시스템")
    if has_any(corpus, ("배송", "교환", "반품", "주문")):
        base.append("배송/주문 연계 시스템")
    if has_any(corpus, ("제휴", "쿠폰", "이용권", "멤버십", "T우주", "판매자")):
        base.extend(["제휴사 시스템", "판매자"])
    if has_any(corpus, ("인증", "본인확인", "권한")):
        base.append("인증 시스템")
    return unique_texts(base)[:10]


def usecase_candidates(topic: str, requirements: Sequence[object]) -> List[str]:
    names = [getattr(item, "detail_name", "") for item in requirements if getattr(item, "detail_name", "")]
    if names:
        return unique_texts(to_usecase_name(topic, name) for name in names)[:10]
    return [
        f"{topic} 확인",
        f"{topic} 신청 또는 처리",
        f"{topic} 변경 또는 취소",
        f"{topic} 결과 확인",
    ]


def state_candidates(corpus: str, triggers: Sequence[str] = ()) -> List[str]:
    candidates = ["신청 전", "진행 중", "처리 완료", "처리 제한", "취소"]
    for keyword, states in STATE_KEYWORD_CANDIDATES.items():
        if keyword in triggers:
            candidates.extend(states)
    return unique_texts(candidates)[:18]


def process_patterns(corpus: str, triggers: Sequence[str] = ()) -> List[str]:
    patterns = ["진입 및 대상 확인", "권한·조건 확인", "처리 요청 접수", "결과 안내 및 이력 저장"]
    trigger_text = " ".join(triggers)
    if "결제" in triggers or "정기결제" in triggers:
        patterns.extend(["결제수단 확인", "결제 가능 여부 산정"])
    if "납부" in triggers:
        patterns.extend(["납부수단 확인", "납부 가능 여부 산정"])
    if "환불" in triggers:
        patterns.extend(["환불 가능 여부 산정"])
    if has_any(trigger_text, ("인증", "본인확인", "권한")):
        patterns.extend(["본인확인 및 권한 검증"])
    if has_any(trigger_text, ("배송", "교환", "반품")):
        patterns.extend(["배송 상태 확인", "교환/반품 요청 접수"])
    if "쿠폰" in triggers:
        patterns.extend(["쿠폰 보유 및 사용 가능 여부 확인", "쿠폰 사용 처리"])
    if "이용권" in triggers:
        patterns.extend(["이용권 보유 및 사용 가능 여부 확인", "이용권 사용 처리"])
    if "혜택" in triggers:
        patterns.extend(["혜택 보유 및 사용 가능 여부 확인", "혜택 사용 처리"])
    if "멤버십" in triggers:
        patterns.extend(["멤버십 자격 확인", "멤버십 혜택 사용 처리"])
    return unique_texts(patterns)[:14]


def function_candidates(corpus: str, triggers: Sequence[str] = ()) -> List[str]:
    topic = first_corpus_line(corpus)
    candidates = [
        f"{topic} 대상 정보 조회",
        f"{topic} 조건 검증",
        f"{topic} 처리 요청 관리",
        f"{topic} 결과 안내",
        f"{topic} 이력 저장",
    ]
    for keyword, functions in FUNCTION_KEYWORD_CANDIDATES.items():
        if keyword in triggers:
            candidates.extend(functions)
    return unique_texts(candidates)[:18]


def policy_item_candidates(corpus: str, triggers: Sequence[str] = ()) -> List[str]:
    topic = first_corpus_line(corpus)
    candidates = [
        f"{topic} 대상 고객 기준",
        f"{topic} 권한 확인 기준",
        f"{topic} 처리 제한 기준",
        f"{topic} 고객 고지 기준",
        f"{topic} 이력 저장 기준",
    ]
    for keyword, policies in POLICY_KEYWORD_CANDIDATES.items():
        if keyword in triggers:
            candidates.extend(policies)
    return unique_texts(candidates)[:22]


def build_pack_evidence_gaps(topic: str, requirements: Sequence[object], primary: Sequence[object], auxiliary: Sequence[object]) -> List[dict]:
    gaps = []
    if not requirements:
        gaps.append({"type": "requirement_gap", "message": f"{topic}에 직접 매칭된 요구사항이 없습니다."})
    if not primary:
        gaps.append({"type": "attached_reference_gap", "message": "1순위 첨부·사내 참고자료에서 직접 근거가 약합니다. 2~4순위 근거는 보조/참고로만 사용해야 합니다."})
    if auxiliary and not primary:
        gaps.append({"type": "source_authority_warning", "message": "공개웹 보조 지식은 있으나 첨부 근거가 약하므로 확정 정책값은 TBD로 처리해야 합니다."})
    return gaps


def compact_topic_evidence_map(topic_evidence_map: Mapping[str, object]) -> dict:
    stages = topic_evidence_map.get("stages", {}) if isinstance(topic_evidence_map, Mapping) else {}
    return {
        "version": topic_evidence_map.get("version", "") if isinstance(topic_evidence_map, Mapping) else "",
        "stats": topic_evidence_map.get("stats", {}) if isinstance(topic_evidence_map, Mapping) else {},
        "stages": {
            stage: {
                "evidence_ids": data.get("evidence_ids", [])[:10],
                "source_mix": data.get("source_mix", {}),
                "decision_axes": data.get("decision_axes", [])[:6],
                "flow_signals": data.get("flow_signals", [])[:5],
                "evidence_cards": data.get("evidence_cards", [])[:4],
            }
            for stage, data in stages.items()
            if isinstance(data, Mapping)
        },
    }


def save_topic_knowledge_pack(pack: Mapping[str, object], output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = topic_knowledge_path(str(pack.get("topic", "")), output_dir)
    path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_and_save_topic_knowledge_pack(topic: str, *, output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> Path:
    return save_topic_knowledge_pack(build_topic_knowledge_pack(topic), output_dir)


def build_all_topic_knowledge_packs(topics: Sequence[str] = POLICY_TOPICS, *, output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for topic in topics:
        pack = build_topic_knowledge_pack(topic)
        paths.append(str(save_topic_knowledge_pack(pack, output_dir)))
    manifest = {
        "version": TOPIC_KNOWLEDGE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "topic_count": len(paths),
        "paths": paths,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_topic_knowledge_pack(topic: str, output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> dict:
    path = topic_knowledge_path(topic, output_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != TOPIC_KNOWLEDGE_VERSION:
        return refresh_topic_knowledge_pack(topic, output_dir)
    return data


def refresh_topic_knowledge_pack(topic: str, output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> dict:
    try:
        pack = build_topic_knowledge_pack(topic)
        save_topic_knowledge_pack(pack, output_dir)
        return pack
    except Exception:
        return {}


def compact_topic_knowledge_for_prompt(pack: Mapping[str, object], max_chars: int = 6000) -> dict:
    if not pack:
        return {}
    compact = {
        "version": pack.get("version", ""),
        "topic": pack.get("topic", ""),
        "source_authority_rule": pack.get("source_authority_rule", {}),
        "candidate_usage_policy": pack.get("candidate_usage_policy", {}),
        "topic_contract": pack.get("topic_contract", {}),
        "source_profile": pack.get("source_profile", {}),
        "topic_direction_milestone": pack.get("topic_direction_milestone", []),
        "topic_direction_strategy": pack.get("topic_direction_strategy", []),
        "topic_direction_agent_guidance": pack.get("topic_direction_agent_guidance", []),
        "authoritative_signals": pack.get("authoritative_signals", {}),
        "tk_core_orientations": pack.get("tk_core_orientations", []),
        "tk_process_function_guidance": pack.get("tk_process_function_guidance", []),
        "auxiliary_web_signals": pack.get("auxiliary_web_signals", {}),
        "topic_axes": pack.get("topic_axes", {}),
        "chapter_guidance": pack.get("chapter_guidance", {}),
        "candidate_inventory": pack.get("candidate_inventory", {}),
        "evidence_gaps": pack.get("evidence_gaps", []),
    }
    text = json.dumps(compact, ensure_ascii=False)
    if len(text) <= max_chars:
        return compact
    compact["authoritative_signals"] = trim_mapping_lists(compact.get("authoritative_signals", {}), 8)
    compact["tk_core_orientations"] = trim_tk_core_orientations(compact.get("tk_core_orientations", []), 4)
    compact["tk_process_function_guidance"] = trim_tk_process_function_guidance(
        compact.get("tk_process_function_guidance", []),
        6,
    )
    compact["auxiliary_web_signals"] = trim_mapping_lists(compact.get("auxiliary_web_signals", {}), 5)
    compact["candidate_inventory"] = trim_mapping_lists(compact.get("candidate_inventory", {}), 8)
    compact["topic_contract"] = trim_topic_contract(compact.get("topic_contract", {}), 8)
    return compact


def trim_tk_core_orientations(value: object, limit: int = 4) -> object:
    if not isinstance(value, list):
        return value
    trimmed = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        trimmed.append(
            {
                "source_name": item.get("source_name", ""),
                "topic_relevance": item.get("topic_relevance", 0),
                "matched_keywords": item.get("matched_keywords", [])[:8] if isinstance(item.get("matched_keywords", []), list) else [],
                "core_points": item.get("core_points", [])[:4] if isinstance(item.get("core_points", []), list) else [],
                "point_matches": item.get("point_matches", [])[:4] if isinstance(item.get("point_matches", []), list) else [],
                "evidence_excerpt": compact_sentence(item.get("evidence_excerpt", ""), 260),
                "mapping_rule": item.get("mapping_rule", ""),
                "usage_rule": item.get("usage_rule", ""),
            }
        )
    return trimmed


def trim_tk_process_function_guidance(value: object, limit: int = 6) -> object:
    if not isinstance(value, list):
        return value
    trimmed = []
    for item in value[:limit]:
        if not isinstance(item, Mapping):
            continue
        trimmed.append(
            {
                "source_name": item.get("source_name", ""),
                "topic_relevance": item.get("topic_relevance", 0),
                "matched_keywords": item.get("matched_keywords", [])[:8] if isinstance(item.get("matched_keywords", []), list) else [],
                "process_name": compact_sentence(item.get("process_name", ""), 80),
                "major_functions": item.get("major_functions", [])[:5] if isinstance(item.get("major_functions", []), list) else [],
                "source_excerpt": compact_sentence(item.get("source_excerpt", ""), 220),
                "mapping_rule": item.get("mapping_rule", ""),
                "usage_rule": item.get("usage_rule", ""),
            }
        )
    return trimmed


def trim_topic_contract(value: object, limit: int = 8) -> object:
    if not isinstance(value, Mapping):
        return value
    trimmed = {}
    for key, item in value.items():
        if isinstance(item, list):
            trimmed[key] = item[:limit]
        else:
            trimmed[key] = item
    return trimmed


def topic_knowledge_path(topic: str, output_dir: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> Path:
    return output_dir / f"{topic_slug(topic)}.json"


def topic_slug(topic: str) -> str:
    slug = re.sub(r"\s+", "", unicodedata.normalize("NFC", str(topic or "")))
    slug = re.sub(r"[^\w가-힣]", "", slug, flags=re.UNICODE)
    return slug or "정책서"


def clean_milestone_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def is_agent_direction_line(value: object) -> bool:
    text = str(value or "")
    markers = (
        "개발/QA",
        "테스트 케이스",
        "Agent",
        "agent",
        "Context",
        "context",
        "컨텍스트",
        "내부 지침",
        "검수 기준",
    )
    return any(marker in text for marker in markers)


def split_direction_milestone(lines: Sequence[object]) -> tuple[List[str], List[str]]:
    display: List[str] = []
    agent: List[str] = []
    for line in lines:
        text = clean_milestone_text(line)
        if not text:
            continue
        if is_agent_direction_line(text):
            agent.append(text)
        else:
            display.append(text)
    if not display and agent:
        display = [agent[0]]
        agent = agent[1:]
    return unique_texts(display)[:3], unique_texts(agent)[:5]


def load_topic_direction_milestones(path: Path | str = TOPIC_DIRECTION_MILESTONE_PATH) -> dict[str, List[str]]:
    """Parse the human-authored 34-topic direction guide into per-topic lines.

    The source markdown is intentionally readable for humans. For agent use we
    split it by topic so retrieval chunks from adjacent topics cannot bleed into
    the current topic's authoring baseline.
    """
    md_path = Path(path)
    if not md_path.exists():
        return {}
    milestones: dict[str, List[str]] = {}
    current_topic = ""
    for raw_line in md_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        heading_match = re.match(r"^##\s+\d+\.\s*(.+?)\s*$", line)
        if heading_match:
            current_topic = clean_milestone_text(heading_match.group(1))
            milestones[current_topic] = []
            continue
        if current_topic and line.startswith("- "):
            item = clean_milestone_text(line[2:])
            if item:
                milestones[current_topic].append(item)
    return {topic: lines[:8] for topic, lines in milestones.items() if lines}


def topic_direction_milestone_for(
    topic: str,
    milestones: Mapping[str, Sequence[str]] | None = None,
) -> List[str]:
    rows = milestones if milestones is not None else load_topic_direction_milestones()
    if not rows:
        return []
    target_slug = topic_slug(topic)
    for source_topic, lines in rows.items():
        if topic_slug(source_topic) == target_slug:
            return [compact_sentence(line, 180) for line in list(lines)[:8] if clean_milestone_text(line)]
    return []


def update_topic_direction_milestone(
    topic: str,
    lines: Sequence[object],
    path: Path | str = TOPIC_DIRECTION_MILESTONE_PATH,
) -> List[str]:
    """Persist edited per-topic direction lines back to the source markdown."""
    topic_text = clean_milestone_text(topic)
    if not topic_text:
        raise ValueError("수정할 주제를 찾을 수 없습니다.")
    cleaned_lines = [compact_sentence(clean_milestone_text(line), 220) for line in lines if clean_milestone_text(line)]
    cleaned_lines = unique_texts(cleaned_lines)[:8]
    if not cleaned_lines:
        raise ValueError("작성 지향점을 1개 이상 입력해 주세요.")
    if len(cleaned_lines) > 8:
        raise ValueError("작성 지향점은 최대 8개까지만 입력할 수 있습니다.")

    md_path = Path(path)
    existing = md_path.read_text(encoding="utf-8") if md_path.exists() else "# 34개 정책서 작성 지향점\n"
    raw_lines = existing.splitlines()
    target_slug = topic_slug(topic_text)
    heading_index = -1
    next_heading_index = len(raw_lines)
    heading_pattern = re.compile(r"^##\s+\d+\.\s*(.+?)\s*$")
    for index, raw_line in enumerate(raw_lines):
        match = heading_pattern.match(raw_line.strip())
        if not match:
            continue
        if heading_index >= 0:
            next_heading_index = index
            break
        if topic_slug(match.group(1)) == target_slug:
            heading_index = index

    replacement = [f"- {line}" for line in cleaned_lines]
    if heading_index >= 0:
        before = raw_lines[: heading_index + 1]
        after = raw_lines[next_heading_index:]
        new_lines = before + replacement + [""]
        if after:
            new_lines.extend(after)
    else:
        number = 1 + sum(1 for raw_line in raw_lines if heading_pattern.match(raw_line.strip()))
        new_lines = raw_lines
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.extend([f"## {number}. {topic_text}", *replacement, ""])

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
    return cleaned_lines


def update_topic_direction_display_milestone(
    topic: str,
    lines: Sequence[object],
    path: Path | str = TOPIC_DIRECTION_MILESTONE_PATH,
) -> List[str]:
    """Update only the service-facing direction while preserving agent notes.

    The first milestone line is treated as the public/service-facing authoring
    direction. Remaining lines are kept as internal generation guardrails so a
    UI edit does not accidentally remove agent context.
    """

    topic_text = clean_milestone_text(topic)
    if not topic_text:
        raise ValueError("수정할 주제를 찾을 수 없습니다.")
    cleaned_display = [
        compact_sentence(clean_milestone_text(line), 220)
        for line in lines
        if clean_milestone_text(line)
    ]
    cleaned_display = unique_texts(cleaned_display)[:3]
    if not cleaned_display:
        raise ValueError("작성 지향점을 1개 이상 입력해 주세요.")

    current_lines = topic_direction_milestone_for(
        topic_text,
        load_topic_direction_milestones(path),
    )
    _, hidden_lines = split_direction_milestone(current_lines)
    display_keys = {clean_milestone_text(item) for item in cleaned_display}
    hidden_lines = [line for line in hidden_lines if clean_milestone_text(line) not in display_keys]
    return update_topic_direction_milestone(topic_text, [*cleaned_display, *hidden_lines][:8], path)


def split_references_by_authority(references: Sequence[object]) -> tuple[List[object], List[object]]:
    primary: List[object] = []
    auxiliary: List[object] = []
    for item in references:
        authority = reference_authority(item)
        if evidence_authority_tier_for_authority(authority) == 1:
            primary.append(item)
        else:
            auxiliary.append(item)
    return primary, auxiliary


def filter_references_for_topic(topic: str, references: Sequence[object]) -> List[object]:
    """Keep public-web auxiliary references only when they fit the topic.

    Attached references are authoritative and already selected by the source DB.
    Public-web cards are intentionally broader, so we apply a stricter second
    pass to avoid attaching every auxiliary card to every policy topic.
    """
    filtered: List[object] = []
    for item in references:
        if evidence_authority_tier_for_authority(reference_authority(item)) == 1:
            filtered.append(item)
            continue
        if auxiliary_reference_matches_topic(topic, item):
            filtered.append(item)
    return filtered


def auxiliary_reference_matches_topic(topic: str, item: object) -> bool:
    text = reference_text_for_matching(item)
    explicit_topics = extract_applied_topics(text)
    if explicit_topics:
        return topic_matches_explicit_topics(topic, explicit_topics)
    if "적용 범위: 통합채널 정책서 작성 시 공통 참고" in text:
        return True
    focus_keywords = topic_focus_keywords(topic)
    if focus_keywords and has_any(text, focus_keywords):
        return True
    return False


def reference_text_for_matching(item: object) -> str:
    return "\n".join(
        str(value or "")
        for value in [
            getattr(item, "source_name", ""),
            getattr(item, "summary", ""),
            " ".join(str(signal) for signal in getattr(item, "signals", ()) or ()),
            " ".join(str(evidence) for evidence in getattr(item, "evidence", ()) or ()),
            getattr(item, "source_text", ""),
        ]
    )


def extract_applied_topics(text: str) -> List[str]:
    match = re.search(r"적용\s*주제\s*:\s*([^\n]+)", str(text or ""))
    if not match:
        return []
    return [part.strip() for part in re.split(r"[,，]", match.group(1)) if part.strip()]


def topic_matches_explicit_topics(topic: str, explicit_topics: Sequence[str]) -> bool:
    topic_key = topic_slug(topic)
    for candidate in explicit_topics:
        candidate_key = topic_slug(candidate)
        if not candidate_key:
            continue
        if topic_key == candidate_key:
            return True
        if len(candidate_key) >= 4 and candidate_key in topic_key:
            return True
        if len(topic_key) >= 4 and topic_key in candidate_key:
            return True
    return False


def reference_authority(item: object) -> str:
    return evidence_source_authority_for_values(
        getattr(item, "category", ""),
        getattr(item, "source_name", ""),
        " ".join([str(getattr(item, "summary", "") or ""), " ".join(str(value) for value in getattr(item, "signals", ()) or ())]),
    )


def source_mix(references: Sequence[object]) -> dict:
    result: dict[str, int] = {}
    for item in references:
        key = reference_authority(item)
        result[key] = result.get(key, 0) + 1
    return result


def authority_tier_mix(references: Sequence[object]) -> dict:
    result: dict[str, int] = {}
    for item in references:
        tier = evidence_authority_tier_for_authority(reference_authority(item))
        key = f"tier_{tier}"
        result[key] = result.get(key, 0) + 1
    return result


def compact_requirement_ids(requirements: Sequence[object]) -> List[str]:
    return unique_texts(
        getattr(item, "detail_id", "") or getattr(item, "requirement_id", "") or getattr(item, "source_number", "")
        for item in requirements
    )[:40]


def source_name(item: object) -> str:
    return str(getattr(item, "source_name", "") or getattr(item, "source", "") or "")


def source_fingerprint(requirements: Sequence[object], references: Sequence[object]) -> str:
    payload = {
        "requirements": [
            [
                getattr(item, "detail_id", ""),
                getattr(item, "requirement_id", ""),
                getattr(item, "depth4", ""),
                getattr(item, "detail_name", ""),
                getattr(item, "detail_description", ""),
                getattr(item, "requirement_type", ""),
                getattr(item, "required", ""),
            ]
            for item in requirements
        ],
        "references": [
            [getattr(item, "source_name", ""), getattr(item, "category", ""), getattr(item, "score", 0), getattr(item, "text_chars", 0)]
            for item in references
        ],
        "topic_direction_milestone": file_fingerprint(TOPIC_DIRECTION_MILESTONE_PATH),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def file_fingerprint(path: Path | str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]


def source_corpus(topic: str, requirements: Sequence[object], references: Sequence[object]) -> str:
    parts = [topic]
    for item in requirements:
        parts.extend(
            [
                getattr(item, "depth3", ""),
                getattr(item, "depth4", ""),
                getattr(item, "detail_name", ""),
                getattr(item, "detail_description", ""),
            ]
        )
    for item in references:
        parts.extend(
            [
                getattr(item, "source_name", ""),
                getattr(item, "summary", ""),
                " ".join(str(value) for value in getattr(item, "signals", ()) or ()),
                " ".join(str(value) for value in getattr(item, "evidence", ()) or ()),
            ]
        )
    return "\n".join(str(part or "") for part in parts)


def candidate_source_corpus(topic: str, requirements: Sequence[object], references: Sequence[object]) -> str:
    """Build a narrower corpus for candidate inventories.

    Broad channel strategy and public-web knowledge are useful context, but if
    every candidate list reads all of it, unrelated policy items such as
    payment or subscription leak into every topic. Candidate generation should
    therefore start from requirements and only add references that carry a
    topic-specific anchor.
    """
    parts = [topic]
    for item in requirements:
        parts.extend(
            [
                getattr(item, "depth3", ""),
                getattr(item, "depth4", ""),
                getattr(item, "detail_name", ""),
                getattr(item, "detail_description", ""),
            ]
        )
    focus_keywords = topic_focus_keywords(topic)
    for item in references:
        text = " ".join(
            [
                getattr(item, "source_name", ""),
                getattr(item, "summary", ""),
                " ".join(str(value) for value in getattr(item, "signals", ()) or ()),
                " ".join(str(value) for value in getattr(item, "evidence", ()) or ()),
            ]
        )
        authority_tier = evidence_authority_tier_for_authority(reference_authority(item))
        if authority_tier > 1 and not has_any(text, focus_keywords):
            continue
        if authority_tier == 1 and not has_any(text, focus_keywords):
            if len(requirements) > 0:
                continue
        parts.append(text)
    return "\n".join(str(part or "") for part in parts)


def topic_focus_keywords(topic: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(topic or "")).strip()
    compact = re.sub(r"[\s/·,]+", "", cleaned)
    parts = [part for part in re.split(r"[\s/·,]+", cleaned) if len(part) >= 2]
    keywords = [cleaned, compact, *parts]
    for suffix in (
        "주문",
        "조회",
        "설정",
        "관리",
        "변경",
        "처리",
        "상세",
        "목록",
        "정보",
        "혜택",
        "결제",
        "납부",
        "환불",
        "취소",
        "교환",
        "반품",
        "인증",
        "검색",
        "가입",
        "탈퇴",
    ):
        if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
            keywords.extend([compact[: -len(suffix)], suffix, f"{compact[: -len(suffix)]} {suffix}"])
    generic = {"통합", "공통", "품질", "기능", "관리", "처리", "설정", "정보"}
    return [keyword for keyword in unique_texts(keywords) if keyword.casefold() not in generic]


def topic_trigger_corpus(topic: str, requirements: Sequence[object]) -> str:
    parts = [topic]
    for item in requirements:
        parts.extend(
            [
                getattr(item, "depth3", ""),
                getattr(item, "depth4", ""),
                getattr(item, "detail_name", ""),
                getattr(item, "detail_description", ""),
            ]
        )
    return "\n".join(str(part or "") for part in parts)


def domain_candidate_triggers(trigger_corpus: str) -> List[str]:
    """Derive candidate expansion keywords from the policy topic name only.

    Requirements and references can legitimately mention adjacent domains as
    examples or search/result targets. They should not by themselves trigger
    payment, delivery, coupon, or subscription policy candidates for an
    unrelated topic.
    """
    corpus = str(trigger_corpus or "")
    candidate_keys = set(STATE_KEYWORD_CANDIDATES) | set(FUNCTION_KEYWORD_CANDIDATES) | set(POLICY_KEYWORD_CANDIDATES)
    triggers = [keyword for keyword in sorted(candidate_keys) if keyword in corpus]
    if "본인확인" in corpus or "권한" in corpus:
        triggers.append("인증")
    if "요금제" in corpus or "요금" in corpus:
        triggers.append("납부")
    if "알림" in corpus or "고지" in corpus:
        triggers.append("알림")
    if "회원" in corpus or "가입" in corpus or "탈퇴" in corpus:
        triggers.append("회원")
    if "포인트" in corpus:
        triggers.append("포인트")
    if "혜택" in corpus:
        triggers.append("혜택")
    return unique_texts(triggers)


def first_corpus_line(corpus: str) -> str:
    for line in str(corpus or "").splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            return cleaned
    return "해당 업무"


def keyword_hits(text: str, groups: Mapping[str, Sequence[str]]) -> List[str]:
    hits = []
    for label, keywords in groups.items():
        if has_any(text, keywords):
            hits.append(label)
    return hits


def has_any(text: object, keywords: Iterable[object]) -> bool:
    target = str(text or "").casefold()
    return any(str(keyword or "").casefold() in target for keyword in keywords)


def unique_texts(values: Iterable[object]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
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


def compact_sentence(text: object, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip(" ,.;·/") + "…"


def to_usecase_name(topic: str, name: object) -> str:
    text = re.sub(r"\s+", " ", str(name or "")).strip()
    if not text:
        return f"{topic} 처리"
    text = re.sub(r"(버튼|화면|팝업|영역|API|DB|필드)$", "", text).strip()
    if topic not in text and len(text) < 8:
        return f"{topic} {text}"
    return text


def trim_mapping_lists(value: object, limit: int) -> object:
    if not isinstance(value, Mapping):
        return value
    trimmed = {}
    for key, item in value.items():
        if isinstance(item, list):
            trimmed[key] = item[:limit]
        elif isinstance(item, dict):
            trimmed[key] = trim_mapping_lists(item, limit)
        else:
            trimmed[key] = item
    return trimmed


CUSTOMER_TASK_AXES = {
    "조회/확인": ("조회", "확인", "내역", "상세", "안내서"),
    "신청/가입": ("신청", "가입", "계약", "주문"),
    "변경/관리": ("변경", "관리", "설정", "수정"),
    "취소/해지/환불": ("취소", "해지", "환불", "철회", "반품", "교환"),
    "사용/공유/선물": ("사용", "공유", "선물", "혜택", "쿠폰", "이용권"),
    "상담/문의": ("상담", "문의", "FAQ", "공지"),
}

STATE_AXES = {
    "신청 생애주기": ("신청", "접수", "진행", "완료"),
    "인증/권한": ("인증", "권한", "본인확인", "법정대리인"),
    "결제/정산": ("결제", "납부", "환불", "정산", "청구"),
    "배송/개통": ("배송", "개통", "USIM", "eSIM", "교환", "반품"),
    "혜택/이용권": ("혜택", "쿠폰", "이용권", "포인트", "멤버십"),
    "제한/예외": ("제한", "실패", "보류", "만료", "중단"),
}

PROCESS_AXES = {
    "대상 확인": ("대상", "조회", "선택", "진입"),
    "조건 판단": ("조건", "판정", "검증", "권한"),
    "요청 접수": ("신청", "요청", "접수", "입력"),
    "연계 처리": ("BSS", "연계", "회신", "판매자", "제휴사"),
    "결과/이력": ("결과", "고지", "알림", "이력", "저장"),
}

FUNCTION_AXES = {
    "조회": ("조회", "검색", "목록", "상세"),
    "검증": ("검증", "판정", "권한", "인증"),
    "산정": ("산정", "시뮬레이션", "계산", "할인"),
    "처리": ("신청", "변경", "해지", "취소", "저장"),
    "연동": ("연계", "BSS", "외부", "제휴"),
    "고지": ("알림", "고지", "안내", "이력"),
}

POLICY_AXES = {
    "허용 기준": ("허용", "가능", "대상", "자격"),
    "제한 기준": ("제한", "불가", "거절", "보류"),
    "기간/횟수": ("기간", "횟수", "유효", "만료", "기한"),
    "금액/비율": ("금액", "요금", "환불", "할인", "비율", "포인트"),
    "우선순위": ("우선", "순위", "중복", "배타"),
    "고지/동의": ("고지", "동의", "약관", "알림"),
    "이력/보관": ("이력", "저장", "보관", "로그"),
}

CHANNEL_AXES = {
    "T월드": ("T월드", "회선", "요금", "납부", "BSS"),
    "T멤버십": ("T멤버십", "멤버십", "등급", "바코드"),
    "T다이렉트샵": ("T다이렉트샵", "다이렉트", "배송", "개통", "USIM", "eSIM"),
    "T우주": ("T우주", "우주패스", "구독", "정기결제", "패밀리"),
}

POLICY_KEYWORDS = ("기준", "정책", "조건", "허용", "제한", "동의", "고지", "이력", "환불", "우선")

STATE_KEYWORD_CANDIDATES = {
    "결제": ["결제 대기", "결제 완료", "결제 실패"],
    "납부": ["납부 대기", "납부 완료", "납부 실패", "미납"],
    "배송": ["배송 준비", "배송 중", "배송 완료", "교환/반품 진행"],
    "개통": ["개통 신청", "개통 진행", "개통 완료", "개통 실패"],
    "인증": ["인증 필요", "인증 완료", "인증 실패"],
    "쿠폰": ["쿠폰 발급", "쿠폰 사용 가능", "쿠폰 사용 완료", "쿠폰 만료"],
    "이용권": ["이용권 발급", "이용권 사용 가능", "이용권 사용 완료", "이용권 만료"],
    "구독": ["구독 신청", "구독 활성", "구독 일시중지", "구독 해지 예약", "구독 해지 완료"],
    "해지": ["해지 접수", "해지 예약", "해지 완료", "해지 취소 가능"],
    "알림": ["알림 대기", "알림 발송", "알림 실패", "수신 제한"],
    "회원": ["가입 전", "가입 진행", "가입 완료", "탈퇴 접수", "탈퇴 완료"],
    "환불": ["환불 신청", "환불 산정", "환불 완료", "환불 불가"],
    "포인트": ["포인트 사용 가능", "포인트 적립 완료", "포인트 차감 완료", "포인트 소멸"],
    "혜택": ["혜택 사용 가능", "혜택 사용 완료", "혜택 만료"],
}

FUNCTION_KEYWORD_CANDIDATES = {
    "결제": ["결제수단 확인", "결제 요청", "결제 실패 처리"],
    "납부": ["납부수단 관리", "납부 요청", "납부 결과 확인"],
    "배송": ["배송 상태 조회", "배송 요청 연계", "교환/반품 접수"],
    "인증": ["본인확인", "권한 검증", "인증 결과 저장"],
    "쿠폰": ["쿠폰 발급", "쿠폰 사용 검증", "쿠폰 사용 이력 저장"],
    "이용권": ["이용권 발급", "이용권 사용 처리", "이용권 만료 관리"],
    "멤버십": ["등급 조회", "혜택 사용 검증", "바코드 제공"],
    "검색": ["검색 의도 분석", "결과 구성", "추천/필터 적용"],
    "알림": ["수신 대상 산정", "알림 발송 요청", "수신 이력 저장"],
    "회원": ["회원 자격 확인", "가입/탈퇴 요청 접수", "회원 상태 반영"],
    "환불": ["환불 대상 확인", "환불 금액 산정", "환불 결과 안내"],
    "포인트": ["포인트 잔액 조회", "포인트 사용 검증", "포인트 적립/차감 이력 저장"],
    "혜택": ["혜택 보유 조회", "혜택 사용 검증", "혜택 사용 이력 저장"],
}

POLICY_KEYWORD_CANDIDATES = {
    "결제": ["허용 결제수단 기준", "결제 실패 재시도 기준", "결제 취소 기준"],
    "납부": ["납부수단 등록 기준", "실시간 납부 반영 기준", "미납 제한 기준"],
    "배송": ["배송 가능 조건", "교환/반품 가능 기준", "배송비 부담 기준"],
    "인증": ["인증 수단 기준", "인증 유효시간 기준", "인증 실패 제한 기준"],
    "쿠폰": ["쿠폰 발급 기준", "쿠폰 중복 사용 제한", "쿠폰 유효기간 기준"],
    "이용권": ["이용권 사용 가능 기준", "이용권 유효기간 기준", "이용권 사용 제한 기준"],
    "구독": ["구독 가입 기준", "정기결제일 기준", "구독 일시중지 기준", "구독 해지 기준"],
    "멤버십": ["멤버십 등급 기준", "혜택 사용 기준", "바코드 노출 기준"],
    "환불": ["환불 가능 기준", "환불 금액 산정 기준", "환불 불가 기준"],
    "검색": ["검색 대상 범위 기준", "검색 결과 제외 기준", "개인화 결과 노출 기준"],
    "알림": ["알림 발송 대상 기준", "수신 동의 적용 기준", "재발송 제한 기준"],
    "회원": ["가입 가능 대상 기준", "탈퇴 제한 조건", "회원 상태 보관 기준"],
    "포인트": ["포인트 사용 가능 기준", "포인트 적립 기준", "포인트 소멸 기준"],
    "혜택": ["혜택 제공 대상 기준", "혜택 사용 가능 기준", "혜택 중복 사용 제한"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="NC 정책서 주제별 사전 Knowledge Pack 생성")
    parser.add_argument("--topic", default="", help="특정 주제만 생성합니다.")
    parser.add_argument("--all", action="store_true", help="전체 정책서 주제 Knowledge Pack을 생성합니다.")
    parser.add_argument("--output-dir", default=str(DEFAULT_TOPIC_KNOWLEDGE_DIR), help="Knowledge Pack 저장 폴더")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    if args.all or not args.topic:
        manifest = build_all_topic_knowledge_packs(output_dir=output_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    path = build_and_save_topic_knowledge_pack(args.topic, output_dir=output_dir)
    print(path)


if __name__ == "__main__":
    main()
