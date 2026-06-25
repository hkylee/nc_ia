"""Evidence store for NC policy generation.

The source collectors read raw requirements and reference files once. This
module converts those collector outputs into a normalized evidence index that
chapter agents can query without rereading every source.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    kind: str
    source: str
    title: str
    summary: str
    signals: Sequence[str]
    evidence: Sequence[str]
    tags: Sequence[str]
    score: int = 0

    def to_prompt_dict(self, max_chars: int = 320) -> dict:
        data = asdict(self)
        data["source_authority"] = evidence_source_authority(self)
        data["authority_score"] = evidence_authority_score(self)
        data["source_precedence"] = evidence_source_precedence(self)
        data["summary"] = limit_text(self.summary, max_chars)
        data["signals"] = [limit_text(value, 120) for value in list(self.signals)[:4]]
        data["evidence"] = [limit_text(value, 220) for value in list(self.evidence)[:3]]
        data["tags"] = [limit_text(value, 40) for value in list(self.tags)[:8]]
        return data


class EvidenceStore:
    def __init__(self, items: Sequence[EvidenceItem]):
        self.items = list(items)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
        return {
            "total": len(self.items),
            "by_kind": counts,
        }

    def select(
        self,
        *,
        stage: str,
        topic: str,
        query_terms: Sequence[str] = (),
        required_kinds: Sequence[str] = (),
        limit: int = 8,
    ) -> List[EvidenceItem]:
        terms = unique_terms([topic, *query_terms, *stage_profile_terms(stage)])
        required = set(required_kinds)
        ranked = []
        for item in self.items:
            authority_score = evidence_authority_score(item)
            score = item.score
            score += evidence_source_rank_boost(item)
            if item.kind in required:
                score += 25
            score += stage_kind_boost(stage, item.kind)
            score += keyword_score(item, terms)
            score += stage_query_template_score(stage, topic, item)
            ranked.append((score, authority_score, item))
        ranked.sort(key=lambda pair: (pair[0], pair[1], pair[2].source, pair[2].title), reverse=True)
        selected: List[EvidenceItem] = []
        selected_ids = set()
        selected_fingerprints: set[str] = set()
        source_counts: dict[str, int] = {}
        for kind in required_kinds:
            candidates = [(score, authority_score, item) for score, authority_score, item in ranked if item.kind == kind]
            if not candidates:
                continue
            take_count = required_kind_take_count(kind, limit)
            for _, _, item in candidates[:take_count]:
                if len(selected) >= limit:
                    break
                if evidence_can_be_selected(
                    item,
                    selected_ids=selected_ids,
                    selected_fingerprints=selected_fingerprints,
                    source_counts=source_counts,
                    stage=stage,
                    required_slot=True,
                    limit=limit,
                ):
                    selected.append(item)
                    remember_selected_evidence(item, selected_ids, selected_fingerprints, source_counts)
        for score, _, item in ranked:
            if len(selected) >= limit:
                break
            if not evidence_can_be_selected(
                item,
                selected_ids=selected_ids,
                selected_fingerprints=selected_fingerprints,
                source_counts=source_counts,
                stage=stage,
                required_slot=False,
                limit=limit,
            ):
                continue
            if score <= 0 and item.kind not in required:
                continue
            selected.append(item)
            remember_selected_evidence(item, selected_ids, selected_fingerprints, source_counts)
        return order_selected_evidence_by_authority(selected[:limit])


def required_kind_take_count(kind: str, limit: int) -> int:
    if kind == "requirement":
        return min(8, max(2, limit // 2))
    if kind in {"guideline", "sample"}:
        return 1
    return min(3, max(1, limit // 4))


def build_evidence_store(ctx, guideline: Mapping[str, object]) -> EvidenceStore:
    items: List[EvidenceItem] = []
    items.extend(requirement_evidence_items(getattr(ctx, "requirements", ()) or ()))
    items.extend(reference_evidence_items(getattr(ctx, "references", ()) or ()))
    items.extend(guideline_evidence_items(guideline))
    return EvidenceStore(items)


def requirement_evidence_items(requirements: Sequence[object]) -> List[EvidenceItem]:
    items = []
    used_ids = set()
    for index, item in enumerate(requirements, 1):
        source_number = str(getattr(item, "source_number", "") or "")
        detail_requirement_id = str(getattr(item, "detail_id", "") or "")
        raw_requirement_id = str(getattr(item, "requirement_id", "") or "")
        requirement_id = (
            detail_requirement_id
            or (raw_requirement_id if meaningful_source_id(raw_requirement_id) else "")
            or source_number
            or str(index)
        )
        title = str(getattr(item, "detail_name", "") or getattr(item, "parent_name", "") or requirement_id)
        summary = " ".join(
            value
            for value in (
                str(getattr(item, "parent_description", "") or ""),
                str(getattr(item, "detail_description", "") or ""),
            )
            if value
        )
        tags = unique_terms(
            [
                getattr(item, "depth3", ""),
                getattr(item, "depth4", ""),
                getattr(item, "requirement_type", ""),
                getattr(item, "priority", ""),
                getattr(item, "required", ""),
            ]
        )
        items.append(
            EvidenceItem(
                id=unique_requirement_evidence_id(requirement_id, source_number, index, used_ids),
                kind="requirement",
                source="요구사항 통합 list",
                title=title,
                summary=summary or title,
                signals=tuple(signal for signal in tags if signal),
                evidence=tuple(value for value in (summary, title) if value),
                tags=tuple(tags),
                score=80,
            )
        )
    return items


def meaningful_source_id(value: object) -> bool:
    text = re.sub(r"[\s._-]+", "", str(value or ""))
    return bool(text and text.casefold() not in {"na", "none", "null"})


def unique_requirement_evidence_id(requirement_id: object, source_number: object, index: int, used_ids: set) -> str:
    base = f"REQ-{safe_id(requirement_id, index)}"
    if base not in used_ids:
        used_ids.add(base)
        return base
    suffix = safe_id(source_number, index)
    candidate = f"{base}-{suffix}"
    serial = 2
    while candidate in used_ids:
        candidate = f"{base}-{suffix}-{serial}"
        serial += 1
    used_ids.add(candidate)
    return candidate


def reference_evidence_items(references: Sequence[object]) -> List[EvidenceItem]:
    items = []
    used_ids = set()
    for index, item in enumerate(references, 1):
        category = str(getattr(item, "category", "") or "reference")
        source_name = str(getattr(item, "source_name", "") or f"reference-{index}")
        items.append(
            EvidenceItem(
                id=unique_evidence_id("REF", source_name, index, used_ids),
                kind=category,
                source=source_name,
                title=str(getattr(item, "summary", "") or getattr(item, "source_name", "") or f"참고자료 {index}"),
                summary=str(getattr(item, "summary", "") or ""),
                signals=tuple(getattr(item, "signals", ()) or ()),
                evidence=tuple(getattr(item, "evidence", ()) or ()),
                tags=(category, str(getattr(item, "source_type", "") or ""), evidence_source_authority_for_values(category, source_name, "")),
                score=int(getattr(item, "score", 0) or 0) + 40,
            )
        )
        items.extend(reference_chunk_evidence_items(item, source_name, category, index, used_ids))
    return items


def reference_chunk_evidence_items(
    reference: object,
    source_name: str,
    category: str,
    source_index: int,
    used_ids: set,
) -> List[EvidenceItem]:
    source_text = str(getattr(reference, "source_text", "") or "")
    if not source_text:
        source_text = "\n".join(str(value) for value in getattr(reference, "evidence", ()) or ())
    if len(source_text.strip()) < 80:
        return []

    chunks = chunk_reference_text(source_text)
    items: List[EvidenceItem] = []
    base_score = int(getattr(reference, "score", 0) or 0) + 25
    source_type = str(getattr(reference, "source_type", "") or "")
    signals = tuple(getattr(reference, "signals", ()) or ())
    for chunk_index, chunk in enumerate(chunks, 1):
        chunk_score = base_score + chunk_relevance_score(chunk, source_name, signals)
        items.append(
            EvidenceItem(
                id=unique_evidence_id("REFCH", f"{source_name}-{chunk_index:03d}", source_index * 1000 + chunk_index, used_ids),
                kind=category,
                source=source_name,
                title=f"{source_name} 근거 문단 {chunk_index:03d}",
                summary=limit_text(chunk, 420),
                signals=signals[:3],
                evidence=(limit_text(chunk, 500),),
                tags=(category, source_type, "source_chunk", evidence_source_authority_for_values(category, source_name, chunk), f"chunk:{chunk_index:03d}"),
                score=chunk_score,
            )
        )
    return items


def chunk_reference_text(text: str, target_chars: int = 900, max_chunks: int = 80) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_size = 0
    for fragment in split_evidence_fragments(text):
        fragment_size = len(fragment)
        if current and current_size + fragment_size > target_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_size = 0
            if len(chunks) >= max_chunks:
                break
        current.append(fragment)
        current_size += fragment_size + 1
    if current and len(chunks) < max_chunks:
        chunks.append(" ".join(current).strip())
    return [chunk for chunk in chunks if len(chunk) >= 80]


def split_evidence_fragments(text: str, min_chars: int = 25) -> Iterable[str]:
    for fragment in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|[\n\r]+", str(text or "")):
        cleaned = re.sub(r"\s+", " ", fragment).strip()
        if len(cleaned) >= min_chars:
            yield cleaned


def chunk_relevance_score(chunk: str, source_name: str, signals: Sequence[str]) -> int:
    score = 0
    haystack = f"{source_name}\n{chunk}".casefold()
    policy_terms = (
        "고객",
        "불편",
        "요구",
        "프로세스",
        "상태",
        "정책",
        "기준",
        "조건",
        "제한",
        "예외",
        "인증",
        "동의",
        "BSS",
        "연계",
        "원장",
        "이력",
        "저장",
        "알림",
        "고지",
    )
    for term in policy_terms:
        if term.casefold() in haystack:
            score += 2
    for signal in signals:
        for token in unique_terms(re.split(r"[\s·,/]+", str(signal))):
            if len(token) >= 3 and token.casefold() in haystack:
                score += 1
    return min(score, 35)


def guideline_evidence_items(guideline: Mapping[str, object]) -> List[EvidenceItem]:
    common_rules = list(guideline.get("common_rules", []) or []) if isinstance(guideline, Mapping) else []
    sample = guideline.get("sample_baseline", {}) if isinstance(guideline, Mapping) else {}
    sample_summary = (
        f"샘플 기준 body_bytes={sample.get('body_bytes', 0)}, "
        f"table_count={sample.get('table_count', 0)}, policy_item_count={sample.get('policy_item_count', 0)}"
        if isinstance(sample, Mapping)
        else "샘플 정책서의 표 기반 구조와 간결한 작성 밀도를 기준으로 삼는다."
    )
    return [
        EvidenceItem(
            id="GUIDE-AGENTS",
            kind="guideline",
            source="AGENTS.md",
            title="NC 정책서 작성 기준",
            summary="업무 구조, BSS 판단, 요구사항 반영, 정책 구체성, 장별 작성 순서를 정의한다.",
            signals=tuple(common_rules[:6]),
            evidence=tuple(common_rules[:6]),
            tags=("작성 기준", "ID 규칙", "품질 gate"),
            score=95,
        ),
        EvidenceItem(
            id="SAMPLE-BASELINE",
            kind="sample",
            source="input/samples",
            title="샘플 정책서 구조 기준",
            summary=sample_summary,
            signals=("샘플 수준의 표 밀도", "짧은 문장", "정책 상세 항목 분리"),
            evidence=(sample_summary,),
            tags=("샘플", "HTML 구조", "간소화"),
            score=90,
        ),
    ]


STAGE_QUERY_TEMPLATES = {
    "overview": {
        "primary": ("범위", "제외", "채널", "고객", "요구사항", "전략"),
        "secondary": ("대상", "목적", "후속", "통합채널", "셀프"),
    },
    "terms": {
        "primary": ("용어", "상태", "인증", "권한", "정책 판단"),
        "secondary": ("동의", "보관", "제한", "예외", "고지"),
    },
    "terms_refinement": {
        "primary": ("용어", "상태", "권한", "제한", "고지", "이력"),
        "secondary": ("정책 항목", "예외", "BSS", "저장", "감사"),
    },
    "actors": {
        "primary": ("액터", "주체", "책임", "고객", "운영자", "BSS", "연계"),
        "secondary": ("인증기관", "외부", "관리자", "승인", "처리 결과"),
    },
    "usecases": {
        "primary": ("유즈케이스", "고객 행위", "운영자", "완료", "트리거"),
        "secondary": ("VoC", "Pain Point", "신청", "조회", "변경", "확인", "요청"),
    },
    "usecase_diagram": {
        "primary": ("유즈케이스", "액터", "관계", "include"),
        "secondary": ("시스템 경계", "고객", "보조 처리"),
    },
    "state": {
        "primary": ("상태", "상태 변경", "전이", "제한", "보류", "완료", "예외"),
        "secondary": ("만료", "실패", "운영 확인", "판정", "재시도", "취소"),
    },
    "process": {
        "primary": ("프로세스", "업무 흐름", "시작", "판단", "완료", "예외"),
        "secondary": ("BSS", "연계", "인증", "동의", "입력", "선택", "결과 안내"),
    },
    "process_detail": {
        "primary": ("프로세스 상세", "진입 조건", "종료 조건", "선행", "후행"),
        "secondary": ("관련 기능", "관련 정책", "예외", "처리 기준", "흐름"),
    },
    "functions": {
        "primary": ("기능", "조회", "검증", "산정", "저장", "알림", "연동"),
        "secondary": ("IA", "처리", "결과", "BSS", "이력", "고지"),
    },
    "function_detail": {
        "primary": ("기능 상세", "입력", "처리 로직", "출력", "실패", "예외"),
        "secondary": ("관련 정책", "검증", "저장", "회신", "알림", "연동"),
    },
    "policies": {
        "primary": ("정책", "판단", "조건", "허용", "제한", "예외", "기준값"),
        "secondary": ("횟수", "시간", "채널", "고지", "이력", "저장", "우선순위", "BSS"),
    },
    "final_check": {
        "primary": ("점검", "정합성", "요구사항", "연결성", "근거", "누락"),
        "secondary": ("Evidence Gap", "정책 구체성", "프로세스", "기능", "정책"),
    },
}


def stage_query_template(stage: str) -> Mapping[str, Sequence[str]]:
    return STAGE_QUERY_TEMPLATES.get(stage, STAGE_QUERY_TEMPLATES["overview"])


def stage_profile_terms(stage: str) -> Sequence[str]:
    profile = stage_query_template(stage)
    return tuple(profile.get("primary", ())) + tuple(profile.get("secondary", ()))


def stage_kind_boost(stage: str, kind: str) -> int:
    if kind == "analysis_synthesis":
        return {
            "overview": 22,
            "terms": 8,
            "actors": 10,
            "usecases": 24,
            "usecase_diagram": 8,
            "state": 16,
            "process": 24,
            "process_detail": 20,
            "functions": 24,
            "function_detail": 20,
            "policies": 22,
            "final_check": 20,
        }.get(stage, 12)
    boosts = {
        "overview": {"requirement": 30, "strategy": 30, "research": 15, "guideline": 20, "sample": 10},
        "terms": {"requirement": 25, "guideline": 25, "sample": 10},
        "actors": {"requirement": 25, "strategy": 15, "guideline": 25},
        "usecases": {"requirement": 35, "voc": 30, "research": 20, "guideline": 15},
        "usecase_diagram": {"guideline": 30, "sample": 25, "requirement": 15},
        "state": {"requirement": 30, "voc": 20, "guideline": 20},
        "process": {"requirement": 35, "voc": 20, "ia": 20, "strategy": 15, "guideline": 15},
        "process_detail": {"requirement": 30, "ia": 25, "guideline": 20, "sample": 20},
        "functions": {"requirement": 30, "ia": 35, "strategy": 15, "guideline": 15},
        "function_detail": {"requirement": 30, "ia": 30, "guideline": 20, "sample": 20},
        "policies": {"requirement": 40, "voc": 25, "strategy": 20, "guideline": 25},
        "final_check": {"requirement": 30, "guideline": 30, "sample": 25, "voc": 15},
    }
    return boosts.get(stage, {}).get(kind, 0)


def stage_query_template_score(stage: str, topic: str, item: EvidenceItem) -> int:
    haystack = evidence_text(item)
    folded = haystack.casefold()
    profile = stage_query_template(stage)
    score = 0
    topic_terms = unique_terms([topic, *re.split(r"[\s·,/()]+", str(topic or ""))])
    for term in topic_terms[:6]:
        key = term.casefold()
        if not key:
            continue
        if key in str(item.title).casefold():
            score += 18
        elif key in folded:
            score += 8
    primary_hits = sum(1 for term in profile.get("primary", ()) if str(term).casefold() in folded)
    secondary_hits = sum(1 for term in profile.get("secondary", ()) if str(term).casefold() in folded)
    score += min(primary_hits * 7, 28)
    score += min(secondary_hits * 3, 12)
    if item.kind in {"guideline", "sample"}:
        score += 6
    return score


def evidence_can_be_selected(
    item: EvidenceItem,
    *,
    selected_ids: set[str],
    selected_fingerprints: set[str],
    source_counts: Mapping[str, int],
    stage: str,
    required_slot: bool,
    limit: int,
) -> bool:
    if item.id in selected_ids:
        return False
    fingerprint = evidence_fingerprint(item)
    if item.kind != "requirement" and fingerprint and fingerprint in selected_fingerprints:
        return False
    if item.kind not in {"requirement", "guideline", "sample"}:
        cap = max(2, min(4, max(1, limit // 3)))
        if int(source_counts.get(item.source, 0) or 0) >= cap and not required_slot:
            return False
    return True


def remember_selected_evidence(
    item: EvidenceItem,
    selected_ids: set[str],
    selected_fingerprints: set[str],
    source_counts: dict[str, int],
) -> None:
    selected_ids.add(item.id)
    fingerprint = evidence_fingerprint(item)
    if fingerprint:
        selected_fingerprints.add(fingerprint)
    source_counts[item.source] = source_counts.get(item.source, 0) + 1


def order_selected_evidence_by_authority(items: Sequence[EvidenceItem]) -> List[EvidenceItem]:
    """Keep selected evidence relevant, but present authoritative sources first."""
    return sorted(
        list(items),
        key=lambda item: (
            evidence_authority_score(item),
            required_prompt_kind_priority(item.kind),
            item.score,
            item.source,
            item.title,
        ),
        reverse=True,
    )


def required_prompt_kind_priority(kind: str) -> int:
    return {
        "requirement": 5,
        "template": 4,
        "sample": 4,
        "guideline": 4,
    }.get(str(kind or ""), 1)


def evidence_fingerprint(item: EvidenceItem) -> str:
    if item.kind == "requirement":
        return item.id
    text = " ".join(
        value
        for value in (
            item.source,
            item.title,
            item.summary,
            " ".join(list(item.evidence)[:1]),
        )
        if value
    )
    normalized = re.sub(r"[^0-9A-Za-z가-힣]+", "", text).casefold()
    return normalized[:220]


ATTACHED_SOURCE_KINDS = {"requirement", "template", "sample", "guideline"}
OFFICIAL_SERVICE_SOURCE_MARKERS = (
    "skt 공식",
    "sk텔레콤 공식",
    "tworld.co.kr",
    "shop.tworld",
    "tmembership",
    "sktuniverse",
    "고객지원",
    "이용약관",
    "서비스 안내",
    "공식 서비스",
)
COMPLIANCE_SOURCE_MARKERS = (
    "법령",
    "법률",
    "시행령",
    "시행규칙",
    "규제기관",
    "개인정보보호위원회",
    "개인정보보호위",
    "pipc",
    "방송통신위원회",
    "방통위",
    "kcc",
    "과학기술정보통신부",
    "전자상거래",
    "전기통신사업법",
    "개인정보 보호법",
    "정보통신망법",
    "위치정보",
)
BENCHMARK_SOURCE_MARKERS = (
    "벤치마킹",
    "경쟁사",
    "타사",
    "benchmark",
    "competitor",
)
LEARNED_WEB_SOURCE_MARKERS = (
    "공개웹",
    "공식웹",
    "웹_",
    "sktuniverse",
    "tworld.co.kr",
    "shop.tworld",
    "tmembership",
    "public-web",
    "통합지식",
)
REQUIREMENT_LEVEL_REFERENCE_MARKERS = (
    "채널방향성pdf",
    "tkch",
)
ANALYSIS_SYNTHESIS_SOURCE_ALIASES = {
    "benchmarking.html": "벤치마킹 경쟁사 비교 선택 실행 완료 통합채널 전시 노출",
    "customer-research.html": "고객 조사 인사이트 고객 불편 신뢰 이해 탐색",
    "employee-interview.html": "임직원 인터뷰 채널 방향성 운영 현장 제약",
    "function-inventory-biz.html": "T 월드 Biz 기능 내역 법인 기업 회선 요금 부가서비스 인증 관리",
    "function-inventory-direct.html": "T 다이렉트 기능 내역 상품 탐색 주문 가입 배송 개통",
    "function-inventory-integrated.html": "통합 기능 목록 공통 기능 중복 기능 표준화 통합채널",
    "function-inventory-membership.html": "T 멤버십 기능 내역 혜택 리워드 등급 포인트 사용처",
    "function-inventory-tworld.html": "T 월드 기능 내역 요금 가입정보 로밍 고객지원 셀프 처리",
    "function-inventory-universe.html": "T 우주 기능 내역 구독 상품 상세 담기 결제 이용 마이",
    "ia-analysis.html": "IA 분석 메뉴 구조 탐색 경로 모듈 통합채널 전시 노출",
    "voc-summary.html": "VoC 분석 종합 고객 불편 상담 전환 실패 복구",
    "voc-add-on-cancel.html": "부가서비스 해지 해지 환불 취소",
    "voc-add-on-join.html": "부가서비스 가입 신청",
    "voc-address-change.html": "주소 변경 회원정보 조회 변경",
    "voc-auto-payment-apply-change.html": "자동 납부 신청 변경 요금 납부 결제 수납",
    "voc-auto-payment-apply.html": "자동 납부 신청 요금 납부 결제 수납",
    "voc-auto-payment-cancel.html": "자동 납부 해지 취소 요금 납부 수납",
    "voc-bank-transfer-payment.html": "계좌 이체 요금 납부 결제 수납",
    "voc-bill-info.html": "청구서 정보 청구 요금 납부 수납",
    "voc-bundle.html": "결합 가족 결합상품 가입 혜택",
    "voc-card-payment.html": "신용 카드 요금 납부 결제 수납",
    "voc-contact-change.html": "연락처 변경 회원정보 조회 변경 알림",
    "voc-contract-discount.html": "약정 할인 선택약정 할인 시뮬레이션",
    "voc-data-gift.html": "데이터 선물 선물주문 데이터 통화",
    "voc-direct-shop.html": "다이렉트샵 주문 가입 배송 개통 주문 계약 가입",
    "voc-discount-change.html": "할인 변경 할인 시뮬레이션 상품변경",
    "voc-lost-device.html": "분실 고객센터 정지 일시정지 매장 안내",
    "voc-membership.html": "멤버십 혜택 포인트 플러스포인트 카드",
    "voc-mobile-cancel.html": "휴대폰 해지 번호 해지 환불 취소",
    "voc-paper-bill.html": "우편 청구서 청구 요금 납부 수납",
    "voc-plan-change.html": "요금제 변경 상품변경 상품 목록 요금",
    "voc-refill-coupon.html": "리필 쿠폰 쿠폰 이용권",
    "voc-suspension-release.html": "정지 해제 일시정지 해제 고객센터",
    "voc-t-universe-subscription.html": "T우주 우주패스 구독 상품 서비스 혜택 이용 공유 정기결제",
    "voc-temporary-suspension.html": "일시 정지 고객센터 회선 관리",
    "voc-wave-flo.html": "웨이브 플로 구독 상품 서비스 혜택 이용 공유",
}
ANALYSIS_SYNTHESIS_GENERIC_QUERY_TERMS = {
    "고객",
    "정책",
    "기능",
    "프로세스",
    "상태",
    "요구사항",
    "처리",
    "기준",
    "조건",
    "예외",
    "고지",
    "이력",
    "조회",
    "저장",
    "검증",
    "완료",
    "판단",
    "범위",
    "채널",
    "전략",
    "관리",
    "정보",
    "상품",
    "업무",
    "통합",
}


def evidence_source_authority(item: EvidenceItem) -> str:
    return evidence_source_authority_for_values(item.kind, item.source, " ".join([item.title, item.summary, " ".join(item.tags)]))


def evidence_source_authority_for_values(kind: object, source: object, text: object = "") -> str:
    kind_text = str(kind or "")
    if is_requirement_level_reference_source(source):
        return "authority:requirement_level_reference"
    if kind_text == "requirement":
        return "authority:attached_requirement"
    if kind_text == "analysis_synthesis":
        return "authority:analysis_synthesis"
    if kind_text in {"template", "sample"}:
        return f"authority:attached_{kind_text}"
    if kind_text == "guideline":
        return "authority:attached_guideline"
    if kind_text in {"compliance", "law", "regulation"}:
        return "authority:compliance_reference"
    if kind_text in {"official", "official_service"}:
        return "authority:skt_official_auxiliary"
    if kind_text == "benchmark":
        return "authority:public_benchmark_reference"
    haystack = " ".join([str(source or ""), str(text or "")]).casefold()
    if any(marker.casefold() in haystack for marker in COMPLIANCE_SOURCE_MARKERS):
        return "authority:compliance_reference"
    if any(marker.casefold() in haystack for marker in OFFICIAL_SERVICE_SOURCE_MARKERS):
        return "authority:skt_official_auxiliary"
    if any(marker.casefold() in haystack for marker in BENCHMARK_SOURCE_MARKERS):
        return "authority:public_benchmark_reference"
    if any(marker.casefold() in haystack for marker in LEARNED_WEB_SOURCE_MARKERS):
        return "authority:learned_web_auxiliary"
    return "authority:attached_reference"


def is_requirement_level_reference_source(value: object) -> bool:
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", unicodedata.normalize("NFKC", str(value or "")).casefold())
    return any(marker in normalized for marker in REQUIREMENT_LEVEL_REFERENCE_MARKERS)


def evidence_source_precedence(item: EvidenceItem) -> str:
    authority = evidence_source_authority(item)
    if authority == "authority:attached_requirement":
        return "1순위 근거: 첨부자료, 사내자료, 요구사항을 확정 기준으로 사용한다."
    if authority == "authority:requirement_level_reference":
        return "1순위 근거: 채널 방향성과 TK 과제정의 PDF는 요구사항급 사내 기준으로 사용한다."
    if authority in {"authority:attached_template", "authority:attached_sample", "authority:attached_guideline"}:
        return "1순위 근거: 첨부 템플릿, 샘플, AGENTS.md 기준을 작성 형식과 품질 기준으로 우선한다."
    if authority == "authority:analysis_synthesis":
        return "1순위 보강 근거: 현황 분석 종합 장표는 원천 자료를 정책서 작성 관점으로 정리한 내부 분석 근거로 사용하되, 요구사항·TK 원천과 충돌하면 원천을 우선한다."
    if authority == "authority:attached_reference":
        return "1순위 근거: 첨부자료와 사내자료를 업무 맥락과 정책 판단 근거로 우선한다."
    if authority == "authority:skt_official_auxiliary":
        return "2순위 보조 근거: SKT 공식 서비스 안내, 약관, 고객지원 페이지는 첨부 근거를 보강할 때만 사용한다."
    if authority == "authority:compliance_reference":
        return "3순위 컴플라이언스 근거: 법령, 규제기관, 개인정보보호위, 방통위 자료는 준수 필요성과 제한 조건 확인에 사용한다."
    if authority == "authority:public_benchmark_reference":
        return "4순위 참고 근거: 경쟁사, 벤치마킹, 공개웹 자료는 참고 후보로만 사용한다."
    return "4순위 참고 근거: 공개웹 학습 지식은 보조 후보이며, 1순위 근거와 상충하면 폐기한다."


def evidence_source_authority_tier(item: EvidenceItem) -> int:
    return evidence_authority_tier_for_authority(evidence_source_authority(item))


def evidence_authority_tier_for_authority(authority: object) -> int:
    return {
        "authority:attached_requirement": 1,
        "authority:requirement_level_reference": 1,
        "authority:attached_template": 1,
        "authority:attached_sample": 1,
        "authority:attached_guideline": 1,
        "authority:analysis_synthesis": 1,
        "authority:attached_reference": 1,
        "authority:skt_official_auxiliary": 2,
        "authority:compliance_reference": 3,
        "authority:public_benchmark_reference": 4,
        "authority:learned_web_auxiliary": 4,
    }.get(str(authority or ""), 4)


def evidence_source_rank_boost(item: EvidenceItem) -> int:
    return evidence_authority_score(item)


def evidence_authority_score(item: EvidenceItem) -> int:
    return evidence_authority_score_for_values(
        item.kind,
        item.source,
        " ".join([item.title, item.summary, " ".join(item.tags)]),
    )


def evidence_authority_score_for_values(kind: object, source: object, text: object = "") -> int:
    authority = evidence_source_authority_for_values(kind, source, text)
    return {
        "authority:attached_requirement": 100,
        "authority:requirement_level_reference": 100,
        "authority:attached_template": 95,
        "authority:attached_sample": 90,
        "authority:attached_guideline": 90,
        "authority:analysis_synthesis": 85,
        "authority:attached_reference": 90,
        "authority:skt_official_auxiliary": 65,
        "authority:compliance_reference": 55,
        "authority:public_benchmark_reference": 35,
        "authority:learned_web_auxiliary": 30,
    }.get(authority, 50)


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


def analysis_synthesis_alias_text(source: object) -> str:
    source_name = str(source or "").strip()
    return ANALYSIS_SYNTHESIS_SOURCE_ALIASES.get(source_name, "")


def analysis_synthesis_query_terms(query_terms: Sequence[object]) -> List[str]:
    terms: List[str] = []
    seen: set[str] = set()
    for term in query_terms:
        cleaned = re.sub(r"\s+", " ", str(term or "")).strip()
        if len(cleaned) < 2:
            continue
        if cleaned in ANALYSIS_SYNTHESIS_GENERIC_QUERY_TERMS:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(cleaned)
    return terms


def analysis_synthesis_topic_terms(topic: object) -> List[str]:
    cleaned = re.sub(r"\s+", " ", str(topic or "")).strip()
    compact = re.sub(r"[\s/·,_-]+", "", cleaned)
    parts = [part for part in re.split(r"[\s/·,_-]+", cleaned) if len(part) >= 2]
    return analysis_synthesis_query_terms([cleaned, compact, *parts])


def keyword_score(item: EvidenceItem, terms: Sequence[str]) -> int:
    haystack = evidence_text(item).casefold()
    score = 0
    for term in terms:
        key = term.casefold()
        if key and key in haystack:
            score += 8 if key in item.title.casefold() else 3
    return score


def unique_terms(values: Iterable[object]) -> List[str]:
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


def safe_id(value: object, index: int) -> str:
    text = re.sub(r"[^0-9A-Za-z가-힣]+", "-", str(value or "")).strip("-")
    if not text:
        text = f"{index:03d}"
    return text[:40]


def unique_evidence_id(prefix: str, value: object, index: int, used_ids: set) -> str:
    base = f"{prefix}-{safe_id(value, index)}"
    candidate = base
    if candidate in used_ids:
        candidate = f"{base}-{index:03d}"
    while candidate in used_ids:
        index += 1
        candidate = f"{base}-{index:03d}"
    used_ids.add(candidate)
    return candidate


def limit_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"
