"""Policy specification builder.

The writer creates a structured JSON-like dict first. The validator checks this
dict before the renderer turns it into the final HTML document.

This module intentionally avoids topic-specific branches. Topic specialization
must come from requirements, references, Authoring Blueprint, Context Pack, and
the chapter agents rather than hardcoded rules for a single policy area.
"""

from __future__ import annotations

import re
from typing import List, Mapping, Sequence

try:
    from document_density import DensityProfile, build_density_profile
except ImportError:  # pragma: no cover - package import fallback.
    from .document_density import DensityProfile, build_density_profile


REQUIREMENT_STRUCTURE_ITEM_LIMIT = 2

POLICY_SPEC_LIST_KEYS = (
    "history",
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
    "trace_matrix",
    "evidence_gaps",
)


def build_policy_spec(ctx) -> dict:
    return build_generic_policy_spec(ctx)


def display_policy_topic(value: object) -> str:
    """Return a reader-facing topic label without changing the matching key."""

    text = str(value or "").strip()
    text = text.replace("_", " ")
    text = re.sub(r"\s*/\s*", "·", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def ensure_policy_spec_base_keys(spec: dict) -> dict:
    """Keep old checkpoints compatible with the current policy spec shape.

    Some simple-version runs skip full-only detail chapters, but the final JSON
    contract still expects those top-level arrays to exist. Older checkpoints
    can miss the keys entirely, so normalize the container shape without filling
    real content. Final validation still catches empty required business
    sections such as policies or final_check.
    """
    if not isinstance(spec, dict):
        return spec
    meta = spec.get("meta")
    if not isinstance(meta, dict):
        spec["meta"] = {}
    overview = spec.get("overview")
    if not isinstance(overview, dict):
        spec["overview"] = {"scope": [], "principles": []}
    else:
        if not isinstance(overview.get("scope"), list):
            overview["scope"] = []
        if not isinstance(overview.get("principles"), list):
            overview["principles"] = []
    for key in POLICY_SPEC_LIST_KEYS:
        if not isinstance(spec.get(key), list):
            spec[key] = []
    return spec


def build_base_meta(ctx, density_profile: DensityProfile | None = None) -> dict:
    doc_label = "Full" if ctx.template_type == "full" else "간소화"
    meta = {
        "topic": ctx.topic,
        "topic_display": display_policy_topic(ctx.topic),
        "topic_slug": ctx.topic_slug,
        "module_id": getattr(ctx, "module_id", "") or f"PM-{ctx.business_code}",
        "business_code": ctx.business_code,
        "document_id": f"POL-{ctx.business_code}",
        "document_type": f"{doc_label} 버전",
        "status": ctx.status,
        "version": ctx.version,
        "author": ctx.author,
        "date": ctx.today,
        "template_type": ctx.template_type,
        "requirements_count": len(getattr(ctx, "requirements", ()) or ()),
        "references_count": len(getattr(ctx, "references", ()) or ()),
        "user_brief": getattr(ctx, "brief", "").strip(),
        "authoring_basis": authoring_basis(ctx),
    }
    if density_profile:
        meta["density_profile"] = density_profile.to_dict()
    return meta


def authoring_basis(ctx) -> List[str]:
    basis = []
    req_count = len(getattr(ctx, "requirements", ()) or ())
    ref_count = len(getattr(ctx, "references", ()) or ())
    if req_count:
        basis.append(f"요구사항 통합 list의 관련 4depth 항목 {req_count}건을 분석해 정책 판단 기준으로 재구성한다.")
    else:
        basis.append("매칭된 요구사항이 없으면 AGENTS.md 공통 작성 기준과 샘플 정책서 구조를 기준으로 작성한다.")
    if ref_count:
        basis.append(f"references 폴더의 관련 참고자료 {ref_count}건을 분석해 채널 전략, 고객 불편, IA, 벤치마킹 관점을 반영한다.")
    else:
        basis.append("references 자료가 없으면 AGENTS.md와 샘플 기준을 우선 적용한다.")
    return basis


def build_history(ctx, change: str) -> List[dict]:
    brief = f" 작성 요청 메모는 '{ctx.brief}'로 기록한다." if getattr(ctx, "brief", "").strip() else ""
    return [
        {
            "version": ctx.version,
            "change": f"{change}{brief}",
            "date": ctx.today,
            "author": ctx.author,
        }
    ]


def principle(name: str, description: str) -> dict:
    return {"name": name, "description": description}


def transition(current: str, event: str, next_state: str, criteria: str, usecase_ids: Sequence[str] | None = None) -> dict:
    return {
        "usecase_ids": list(usecase_ids or []),
        "current_state": current,
        "event": event,
        "next_state": next_state,
        "criteria": criteria,
    }


def requirement_focus_items(ctx, max_items: int = 17) -> List[dict]:
    items: List[dict] = []
    seen = set()
    topic_text = clean_schema_text(str(getattr(ctx, "topic", "")))
    for index, requirement in enumerate(getattr(ctx, "requirements", ()) or (), 1):
        title = clean_schema_text(getattr(requirement, "detail_name", ""))
        description = clean_schema_text(getattr(requirement, "detail_description", ""))
        if not title:
            continue
        key = re.sub(r"\s+", "", title).casefold()
        if key in seen:
            continue
        seen.add(key)
        text = f"{title} {description}"
        actor = "운영자" if is_operator_requirement(text) else "고객"
        semantic_axis = requirement_semantic_axis(text, actor)
        semantic_focus = requirement_semantic_focus(text)
        semantic_label = requirement_semantic_label(text, actor)
        function_label = requirement_function_label(text, actor)
        policy_group = policy_group_for_requirement(text)
        if is_customer_center_store_topic(topic_text):
            semantic_axis = customer_center_store_requirement_semantic_axis(text)
            semantic_focus = customer_center_store_requirement_semantic_focus(text)
            semantic_label = customer_center_store_requirement_semantic_label(text)
            function_label = customer_center_store_requirement_function_label(text)
            policy_group = customer_center_store_policy_group_for_requirement(text)
        elif is_customer_center_faq_notice_topic(topic_text):
            semantic_axis = customer_center_faq_notice_requirement_semantic_axis(text)
            semantic_focus = customer_center_faq_notice_requirement_semantic_focus(text)
            semantic_label = customer_center_faq_notice_requirement_semantic_label(text)
            function_label = customer_center_faq_notice_requirement_function_label(text)
            policy_group = customer_center_faq_notice_policy_group_for_requirement(text)
        elif is_customer_center_hub_topic(topic_text) and actor != "운영자":
            semantic_axis = customer_center_hub_requirement_semantic_axis(text)
            semantic_focus = customer_center_hub_requirement_semantic_focus(text)
            semantic_label = customer_center_hub_requirement_semantic_label(text)
            function_label = customer_center_hub_requirement_function_label(text)
            policy_group = customer_center_hub_policy_group_for_requirement(text)
        elif "설정" in topic_text and actor != "운영자":
            semantic_axis = settings_requirement_semantic_axis(text)
            semantic_focus = settings_requirement_semantic_focus(text)
            semantic_label = settings_requirement_semantic_label(text)
            function_label = settings_requirement_function_label(text)
            policy_group = settings_policy_group_for_requirement(text)
        elif is_notification_topic(topic_text) and actor != "운영자":
            semantic_axis = notification_requirement_semantic_axis(text)
            semantic_focus = notification_requirement_semantic_focus(text)
            semantic_label = notification_requirement_semantic_label(text)
            function_label = notification_requirement_function_label(text)
            policy_group = notification_policy_group_for_requirement(text)
        elif is_terms_topic(topic_text) and actor != "운영자":
            semantic_axis = terms_requirement_semantic_axis(text)
            semantic_focus = terms_requirement_semantic_focus(text)
            semantic_label = terms_requirement_semantic_label(text)
            function_label = terms_requirement_function_label(text)
            policy_group = terms_policy_group_for_requirement(text)
        elif is_member_info_topic(topic_text) and actor != "운영자":
            semantic_axis = member_info_requirement_semantic_axis(text)
            semantic_focus = member_info_requirement_semantic_focus(text)
            semantic_label = member_info_requirement_semantic_label(text)
            function_label = member_info_requirement_function_label(text)
            policy_group = member_info_policy_group_for_requirement(text)
        items.append(
            {
                "index": len(items) + 1,
                "source_index": index,
                "title": compact_text(title, 90),
                "short_title": compact_requirement_title(title),
                "description": compact_text(description, 260),
                "actor": actor,
                "semantic_axis": semantic_axis,
                "semantic_focus": semantic_focus,
                "semantic_label": semantic_label,
                "function_label": function_label,
                "policy_group": policy_group,
            }
        )
        if len(items) >= max_items:
            break
    return items


def representative_requirement_items(items: Sequence[dict], max_items: int = REQUIREMENT_STRUCTURE_ITEM_LIMIT) -> List[dict]:
    """Pick a small, diverse set of requirements for structural scaffolding.

    The full requirement list is still covered by policy details. Usecases,
    processes, and functions should stay at 업무 단위 granularity, so we only
    lift representative requirement axes into the hierarchy.
    """
    if max_items <= 0:
        return []
    selected: List[dict] = []
    seen_titles = set()
    seen_groups = set()

    def add_item(item: dict) -> bool:
        title_key = re.sub(
            r"\s+",
            "",
            str(item.get("semantic_label") or item.get("short_title") or item.get("title") or ""),
        ).casefold()
        if not title_key or title_key in seen_titles:
            return False
        seen_titles.add(title_key)
        selected.append(item)
        return True

    for item in items:
        group_key = str(item.get("policy_group") or "").strip()
        if group_key and group_key in seen_groups:
            continue
        if add_item(item):
            if group_key:
                seen_groups.add(group_key)
        if len(selected) >= max_items:
            return selected

    for item in items:
        add_item(item)
        if len(selected) >= max_items:
            break
    return selected


def customer_usecase_themes(topic: str, items: Sequence[dict]) -> dict[str, dict]:
    """Derive a small set of customer-goal themes from detailed requirements.

    The generic skeleton intentionally keeps stable IDs (CS-001~003) so later
    process/function references stay valid, but the labels should be shaped by
    detailed requirement names/descriptions. This keeps mock mode useful without
    hardcoding any specific policy topic.
    """

    customer_items = [item for item in items if item.get("actor") != "운영자"]
    if not customer_items:
        return {}
    keys = ("CS-001", "CS-002", "CS-003")
    buckets: dict[str, List[dict]] = {key: [] for key in keys}
    for item in customer_items:
        buckets[usecase_bucket_for_requirement(item)].append(item)

    if not buckets["CS-001"]:
        buckets["CS-001"] = customer_items[:3]
    if not buckets["CS-002"]:
        buckets["CS-002"] = (customer_items[1:4] or customer_items[:3])
    if not buckets["CS-003"]:
        follow_candidates = [
            item
            for item in customer_items
            if contains_any(requirement_full_text(item), ("탈퇴", "해지", "취소", "해제", "로그아웃", "잠금", "차단", "만료", "오류", "에러", "폴백"))
        ]
        buckets["CS-003"] = follow_candidates[:3] or customer_items[-3:]

    themes: dict[str, dict] = {}
    for key in keys:
        selected = buckets[key][:3]
        if not selected:
            continue
        label = usecase_theme_label(topic, selected, key)
        description_focus = usecase_theme_description_focus(selected)
        if is_member_info_topic(topic):
            description_focus = member_info_usecase_description_focus(key)
        elif is_customer_center_store_topic(topic):
            description_focus = customer_center_store_usecase_description_focus(key)
        elif is_customer_center_faq_notice_topic(topic):
            description_focus = customer_center_faq_notice_usecase_description_focus(key)
        elif is_customer_center_hub_topic(topic):
            description_focus = customer_center_hub_usecase_description_focus(key)
        elif "설정" in clean_schema_text(topic):
            description_focus = settings_usecase_description_focus(key)
        elif is_notification_topic(topic):
            description_focus = notification_usecase_description_focus(key)
        elif is_terms_topic(topic):
            description_focus = terms_usecase_description_focus(key)
        themes[key] = {
            "label": label,
            "description_focus": description_focus,
            "source_titles": [requirement_theme_label(item) for item in selected],
        }
    return themes


def member_info_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "프로필, 연락처, 주소, 관계 정보의 조회 범위와 기준 시점"
    if bucket == "CS-002":
        return "회원정보 변경, 재인증, 증빙 제출, BSS 반영 기준"
    return "정보 불일치, 처리 중단, 복구, 상담 전환 기준"


def notification_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "알림함, 행동 필요 알림, 참고성 알림, 상세 컨텍스트와 후속 업무 연결"
    if bucket == "CS-002":
        return "수신 유형, 채널, 연락처, OS 권한, 조용한 시간, 필수 알림 예외"
    return "중복·만료·무효 알림 정리, 발송 실패 복구, 상담 전환, 처리 이력"


def settings_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "현재 설정 상태, 시스템 권한, 보안·세션, 접근성 적용 범위"
    if bucket == "CS-002":
        return "개인화, 홈 구성, 알림 환경, 언어·접근성, 데이터 절약 설정"
    return "설정 초기화, 기본값 복원, 기록 삭제, 변경 이력, 실패·대체 경로"


def customer_center_hub_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "문제 유형, 셀프 해결 가능 여부, 불가 사유, 해결 카드, 다음 행동"
    if bucket == "CS-002":
        return "상담 채널 선택, 1:1 문의 접수, 첨부·동의·준비 정보, 상담 요청"
    return "상담 전환, 문맥 유지, 처리 상태, 추가 정보 요청, 온라인 재유입"


def customer_center_faq_notice_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "FAQ, 이용안내, 가이드, 공지의 목적별 탐색과 최신성 확인"
    if bucket == "CS-002":
        return "단계별 해결 가이드, 관련 업무 바로가기, 미해결 후속 연결"
    return "장애·점검·정책 변경 공지, 영향 범위, 대체 경로, 공지 후속 행동"


def customer_center_store_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "위치, 단골 매장, 매장 속성, 처리 가능 업무를 기준으로 방문 가능한 매장을 찾는 흐름"
    if bucket == "CS-002":
        return "방문 목적, 예약 가능 여부, 준비 정보, 대리점 URL·공유 경로를 확인해 방문을 준비하는 흐름"
    return "매장 이용 제한, 휴무·정보 불일치, 예약 변경, 대체 매장·온라인·상담 경로를 확인하는 흐름"


def terms_usecase_description_focus(bucket: str) -> str:
    if bucket == "CS-001":
        return "약관 원문·요약 열람, 적용 서비스·채널 범위, 개인정보 제공·위탁·쿠키 고지, 거부권 보장 기준"
    if bucket == "CS-002":
        return "필수·선택 동의 구분, 목적별·서비스별 동의, 미동의 제한 범위, 법정대리인·예외 동의"
    return "동의 철회·재동의, 약관 개정 고지, 버전·시행일, 동의 증빙·감사 이력"


def usecase_bucket_for_requirement(item: Mapping[str, object]) -> str:
    text = requirement_full_text(item)
    if contains_any(
        text,
        (
            "빈 화면",
            "에러",
            "오류",
            "폴백",
            "상태 유지",
            "복귀",
            "후속",
            "탈퇴",
            "해지",
            "취소",
            "해제",
            "철회",
            "재시도",
            "로그아웃",
            "원격 로그아웃",
            "잠금",
            "차단",
            "만료",
        ),
    ):
        return "CS-003"
    if contains_any(
        text,
        (
            "필터",
            "정렬",
            "즐겨찾기",
            "찜",
            "자동완성",
            "추천",
            "최근",
            "인기",
            "입력",
            "인증",
            "가입",
            "신청",
            "변경",
            "주문",
            "결제",
            "동의",
            "처리",
            "설정",
            "관리",
        ),
    ):
        return "CS-002"
    return "CS-001"


def usecase_theme_label(topic: str, items: Sequence[Mapping[str, object]], bucket: str) -> str:
    """Return a customer-goal usecase name without promoting procedure steps.

    Detailed requirement titles can be very useful evidence, but using them
    verbatim as Y-usecase names often turns "조건 확인/입력/결과 안내" steps into
    top-level usecases. Keep the name at customer 업무 목적 level and retain the
    detailed titles in source_titles/description_focus instead.
    """

    topic_label = display_policy_topic(topic) or str(topic or "").strip()
    goal = usecase_theme_goal(items, bucket, topic=topic)
    if is_customer_center_store_topic(topic_label) and goal:
        return compact_text(goal, 58)
    if is_customer_center_faq_notice_topic(topic_label) and goal:
        return compact_text(goal, 58)
    if "회원정보" in topic_label and goal:
        return compact_text(f"회원정보 {goal}", 58)
    if goal == "알림 확인" and "알림" in topic_label:
        return compact_text(f"{topic_label} 확인", 58)
    if goal == "변경 실행" and contains_any(topic_label, ("변경", "수정", "전환")):
        return compact_text(f"{topic_label} 실행", 58)
    if topic_label and goal and goal not in topic_label:
        return compact_text(f"{topic_label} {goal}", 58)
    return compact_text(topic_label or goal or "고객 업무 수행", 58)


def requirement_theme_label(item: Mapping[str, object]) -> str:
    label = clean_schema_text(item.get("short_title") or item.get("title") or item.get("semantic_label") or "")
    label = re.sub(r"\([^)]*\)", "", label).strip()
    replacements = (
        ("UI 표준 정의", "기준"),
        ("표준 정의", "기준"),
        ("저장/관리", "관리"),
        ("조회/관리", "확인·관리"),
        ("검색어/", "검색어·"),
        ("(공통)", ""),
    )
    for before, after in replacements:
        label = label.replace(before, after)
    label = re.sub(r"\s+", " ", label).strip(" -·/")
    return compact_text(label, 32)


def usecase_theme_suffix(items: Sequence[Mapping[str, object]], bucket: str) -> str:
    text = " ".join(requirement_full_text(item) for item in items)
    if bucket == "CS-003":
        if contains_any(text, ("탈퇴", "해지", "취소", "철회")):
            return "후속 처리"
        return "예외·후속 처리"
    if bucket == "CS-002":
        if contains_any(text, ("필터", "정렬", "추천", "자동완성", "최근", "인기", "즐겨찾기", "찜")):
            return "조건 적용"
        if contains_any(text, ("인증", "동의", "권한")):
            return "조건 확인"
        return "요청 처리"
    if contains_any(text, ("검색", "조회", "탐색", "목록", "카테고리", "상세", "노출")):
        return "확인"
    return "업무 확인"


def usecase_theme_goal(items: Sequence[Mapping[str, object]], bucket: str, *, topic: str = "") -> str:
    text = " ".join(requirement_full_text(item) for item in items)
    topic_text = display_policy_topic(topic) or str(topic or "")
    if bucket == "CS-003":
        if is_customer_center_store_topic(topic_text):
            return "매장 이용 예외·대체 경로 확인"
        if is_customer_center_faq_notice_topic(topic_text):
            return "공지·변경 안내 확인"
        if is_customer_center_hub_topic(topic_text):
            return "상담 전환·후속 관리"
        if "알림" in topic_text:
            return "후속 처리·복구 관리"
        if "회원정보" in topic_text:
            return "정정·복구 관리"
        if "약관" in topic_text:
            return "변경·철회 관리"
        if "설정" in topic_text:
            return "초기화·삭제 관리"
        if contains_any(text, ("탈퇴", "해지", "취소", "철회", "해제")):
            return "변경·취소 관리"
        if contains_any(text, ("에러", "오류", "실패", "폴백", "재시도", "복구")):
            return "예외 복구 관리"
        return "후속 관리"
    if bucket == "CS-002":
        if is_customer_center_store_topic(topic_text):
            return "방문 준비·예약 실행"
        if is_customer_center_faq_notice_topic(topic_text):
            return "해결 가이드 실행·후속 연결"
        if is_customer_center_hub_topic(topic_text):
            return "상담·문의 접수 실행"
        if "회원정보" in topic_text:
            return "변경·검증 처리"
        if "알림" in topic_text:
            return "수신 설정 실행"
        if "약관" in topic_text:
            return "필수·선택 동의 관리"
        if "설정" in topic_text:
            return "개인화·알림 관리"
        if contains_any(text, ("검색", "조회", "탐색", "목록", "상세", "노출", "필터", "정렬", "추천")):
            return "탐색 조건 적용"
        if contains_any(topic_text, ("변경", "수정", "전환")) and not contains_any(
            topic_text, ("가입", "주문", "예약", "개통", "결제", "선물")
        ):
            return "변경 실행"
        if contains_any(text, ("가입", "신청", "주문", "예약", "접수", "개통")):
            return "신청 실행"
        if contains_any(text, ("변경", "수정", "전환", "전입", "전출")):
            return "변경 실행"
        if contains_any(text, ("혜택", "쿠폰", "포인트", "할인", "멤버십", "공유", "양도")):
            return "혜택 이용"
        if contains_any(text, ("결제", "청구", "수납", "환불", "정산")):
            return "결제 실행"
        if contains_any(text, ("인증", "본인확인", "권한", "동의", "대리", "명의")):
            return "권한 기반 실행"
        return "업무 실행"
    if is_customer_center_store_topic(topic_text):
        return "매장 탐색·방문 가능성 확인"
    if is_customer_center_faq_notice_topic(topic_text):
        return "FAQ·이용안내 탐색·확인"
    if is_customer_center_hub_topic(topic_text):
        return "셀프 해결 허브 이용"
    if "알림" in topic_text:
        return "알림 확인"
    if "약관" in topic_text:
        return "권리 관리"
    if "설정" in topic_text:
        return "상태·권한 관리"
    if "회원정보" in topic_text:
        return "통합 조회·이해"
    if contains_any(text, ("검색", "조회", "탐색", "목록", "카테고리", "상세", "노출")):
        return "정보 탐색"
    if contains_any(text, ("가입", "신청", "주문", "예약", "접수", "개통", "변경", "수정", "전환")):
        return "대상 판단"
    if contains_any(text, ("혜택", "쿠폰", "포인트", "할인", "멤버십")):
        return "혜택 이해"
    if contains_any(text, ("인증", "본인확인", "권한", "동의", "대리", "명의")):
        return "권한 이해"
    return "업무 목적 판단"


def usecase_theme_description_focus(items: Sequence[Mapping[str, object]]) -> str:
    labels = unique_policy_names([requirement_theme_label(item) for item in items if requirement_theme_label(item)])[:3]
    return ", ".join(labels) if labels else "대상 정보와 처리 조건"


def theme_value(themes: Mapping[str, Mapping[str, object]], key: str, fallback: str) -> str:
    theme = themes.get(key, {}) if isinstance(themes, Mapping) else {}
    value = str(theme.get("label", "")).strip() if isinstance(theme, Mapping) else ""
    return value or fallback


def theme_focus(themes: Mapping[str, Mapping[str, object]], key: str, fallback: str) -> str:
    theme = themes.get(key, {}) if isinstance(themes, Mapping) else {}
    value = str(theme.get("description_focus", "")).strip() if isinstance(theme, Mapping) else ""
    return value or fallback


def theme_process_base(themes: Mapping[str, Mapping[str, object]], key: str, fallback: str) -> str:
    theme = themes.get(key, {}) if isinstance(themes, Mapping) else {}
    label = theme_value(themes, key, fallback)
    label = re.sub(r"\s*(업무 확인|조건 확인|조건 적용|요청 처리|예외·후속 처리|후속 처리|확인)$", "", label).strip()
    return compact_text(label or fallback, 36)


def requirement_scope_line(items: Sequence[dict], topic: str) -> str:
    if is_member_info_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 통합 프로필·연락처·주소 조회, 변경 가능 항목과 영향 고지, "
            "민감 변경 재인증, 대표값·출처 정합화, 그룹·법인·대리 권한, 변경 이력과 상담 전환을 포함한다."
        )
    if is_notification_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 알림함 조회, 행동 필요 알림 우선순위, 수신 유형·채널 설정, "
            "OS 푸시 권한, 필수·선택 알림 구분, 중복·빈도 제어, 발송 실패 복구와 발송 이력을 포함한다."
        )
    if is_terms_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 약관 원문·요약 열람, 필수·선택 동의 구분, 목적별·서비스별 동의, "
            "거부권 보장, 개인정보 제공·위탁·쿠키 고지, 약관 개정·재동의, 철회·재동의 이력과 운영 증적을 포함한다."
        )
    if is_customer_center_store_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 매장 검색·위치 정렬, 단골 매장 관리, 대리점 마이크로사이트와 전용 URL, "
            "매장별 처리 가능 업무·예약 가능 여부, 방문 준비 정보, 대체 경로와 매장 정보 갱신 기준을 포함한다."
        )
    if is_customer_center_faq_notice_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 FAQ 탐색·추천, 이용안내·가이드, 공지·장애·점검, "
            "해결 실패 후 CS 연결, 안내 콘텐츠 최신성, 콘텐츠 운영·검수·노출 기준을 포함한다."
        )
    if is_customer_center_hub_topic(topic):
        return (
            "요구사항에서 확인된 핵심 판단축은 셀프 해결 가능 범위, 문제 유형별 해결 경로, 상담 채널 선택, "
            "1:1 문의 접수·상태 관리, 상담 문맥 전달, 콜센터·온라인 재유입, 운영 품질 기준을 포함한다."
        )
    if not items:
        return f"{topic}의 대상 정보 조회, 조건 확인, 처리 요청, 결과 확인, 예외 안내를 포함한다."
    labels = unique_policy_names([str(item.get("semantic_axis") or item.get("semantic_label") or "") for item in items])[:6]
    names = ", ".join(labels)
    return f"요구사항에서 확인된 핵심 판단축은 {names} 등을 포함한다."


def is_member_info_topic(topic: object) -> bool:
    text = clean_schema_text(topic)
    return "회원정보" in text and contains_any(text, ("조회", "변경", "수정", "/"))


def is_notification_topic(topic: object) -> bool:
    return "알림" in clean_schema_text(topic)


def is_terms_topic(topic: object) -> bool:
    return "약관" in clean_schema_text(topic)


def is_customer_center_hub_topic(topic: object) -> bool:
    text = clean_schema_text(topic)
    return "고객센터" in text and "통합허브" in text


def is_customer_center_faq_notice_topic(topic: object) -> bool:
    text = clean_schema_text(topic)
    return "고객센터" in text and contains_any(text, ("FAQ", "faq", "공지", "이용안내", "가이드")) and "통합허브" not in text and "매장" not in text


def is_customer_center_store_topic(topic: object) -> bool:
    text = clean_schema_text(topic)
    return "고객센터" in text and contains_any(text, ("매장", "대리점", "지점"))


def requirement_full_text(item: Mapping[str, object]) -> str:
    return clean_schema_text(f"{item.get('title', '')} {item.get('short_title', '')} {item.get('description', '')}")


def requirement_semantic_axis(text: str, actor: str | None = None) -> str:
    text = clean_schema_text(text)
    if actor == "운영자" or is_operator_requirement(text):
        return "운영 기준"
    if contains_any(text, ("약관", "동의", "철회", "재동의", "거부권", "쿠키", "개인정보 제공", "제3자 제공", "처리 위탁")):
        return "약관·동의"
    if contains_any(text, ("탈퇴", "해지", "취소", "철회", "삭제", "파기", "복구")):
        return "해지·취소"
    if contains_any(text, ("가입", "신청", "등록", "개통", "주문", "예약", "접수")):
        return "가입·신청"
    if contains_any(text, ("변경", "수정", "전환", "전입", "전출")):
        return "변경"
    if contains_any(text, ("검색", "조회", "탐색", "필터", "정렬", "상세", "목록", "노출", "카드")):
        return "조회·탐색"
    if contains_any(text, ("결제", "청구", "환불", "할인", "포인트", "쿠폰", "혜택", "정산")):
        return "결제·혜택"
    if contains_any(text, ("인증", "본인확인", "세션", "로그인", "권한", "명의", "대리")):
        return "인증·권한"
    if contains_any(text, ("알림", "고지", "안내", "통지", "메시지")):
        return "고지·안내"
    if contains_any(text, ("이력", "저장", "보관", "증적", "로그", "마스킹")):
        return "이력·보관"
    if contains_any(text, ("BSS", "연계", "동기화", "정합성", "원장", "회신", "외부")):
        return "연계 판정"
    return "업무 조건"


def settings_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("약관", "동의", "철회", "재동의", "거부", "개인정보", "제3자", "위탁", "권한")):
        return "동의·권한 설정"
    if contains_any(text, ("초기화", "삭제", "리셋", "기록", "이력", "저장", "보관", "학습 데이터")):
        return "기록·초기화 설정"
    if contains_any(text, ("로그아웃", "세션", "로그인", "생체", "인증", "보안", "잠금")):
        return "보안 설정"
    if contains_any(text, ("쉬운모드", "다국어", "언어", "접근성")):
        return "개인화·접근성 설정"
    if contains_any(text, ("알림", "수신", "표시", "채널", "푸시", "문자", "이메일")):
        return "알림 설정"
    if contains_any(text, ("개인화", "추천", "AI", "쉬운모드", "다국어", "언어", "접근성", "모드")):
        return "개인화·접근성 설정"
    if contains_any(text, ("변경", "수정", "설정", "ON", "OFF", "활성", "비활성")):
        return "설정 변경"
    return "설정 기준"


def settings_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("가능", "조건", "범위", "제한", "권한", "동의")):
        focuses.append("조건·범위")
    if contains_any(text, ("수신", "표시", "노출", "안내", "고지", "알림")):
        focuses.append("표시·고지")
    if contains_any(text, ("초기화", "삭제", "리셋", "보관", "이력", "저장")):
        focuses.append("이력·복구")
    if contains_any(text, ("실패", "오류", "불가", "상담", "대체")):
        focuses.append("예외")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def settings_requirement_semantic_label(text: str) -> str:
    axis = settings_requirement_semantic_axis(text)
    focus = settings_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    return f"{axis} {focus} 기준"


def settings_requirement_function_label(text: str) -> str:
    axis = settings_requirement_semantic_axis(text)
    if axis == "개인화·접근성 설정":
        return "개인화·접근성 적용"
    if axis == "알림 설정":
        return "알림 설정 적용"
    if axis == "동의·권한 설정":
        return "동의·권한 검증"
    if axis == "보안 설정":
        return "보안·세션 제어"
    if axis == "기록·초기화 설정":
        return "기록·초기화 처리"
    if axis == "설정 변경":
        return "설정 변경 처리"
    return "설정 조건"


def settings_policy_group_for_requirement(text: str) -> str:
    axis = settings_requirement_semantic_axis(text)
    if axis == "개인화·접근성 설정":
        return "개인화·접근성 설정 정책"
    if axis == "알림 설정":
        return "알림 설정 정책"
    if axis == "동의·권한 설정":
        return "동의·권한 설정 정책"
    if axis == "보안 설정":
        return "보안·세션 설정 정책"
    if axis == "기록·초기화 설정":
        return "기록·초기화 정책"
    return "설정 가능 여부 정책"


def customer_center_hub_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("셀프", "Self", "해결", "불가 사유", "해결 카드", "자동 분기", "지원 채널", "처리 범위", "환불조회", "다음 단계", "대체 경로")):
        return "셀프 해결 경로"
    if contains_any(text, ("문맥", "컨텍스트", "Single-view", "싱글뷰", "현재 설정", "조회 문맥", "상담 지원용", "디바이스", "앱 정보", "고객 KEY", "고객 기본", "상담이력", "여정", "재유입")):
        return "상담 문맥·이력"
    if contains_any(text, ("상담", "콜센터", "전화", "채팅", "카카오", "AI 상담", "상담원", "에스컬레이션", "이관", "전환", "대기", "운영시간", "준비 정보")):
        return "상담 채널·전환"
    if contains_any(text, ("1:1", "문의", "접수", "첨부", "추가 정보", "이의제기", "분쟁", "문제 신고", "피드백", "개선 제안", "상태 갱신", "답변")):
        return "문의 접수·상태 관리"
    if contains_any(text, ("운영자", "운영", "어드민", "공지사항 통합 관리", "모니터링", "품질", "표준 문구", "정책 관리")):
        return "운영·상담 Single-view"
    return "고객센터 허브 기준"


def customer_center_hub_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("가능", "불가", "범위", "제한", "처리 범위", "준비", "자료")):
        focuses.append("범위·조건")
    if contains_any(text, ("상담", "전화", "채팅", "AI", "상담원", "콜센터", "에스컬레이션", "이관")):
        focuses.append("상담·전환")
    if contains_any(text, ("문의", "접수", "첨부", "이의제기", "피드백", "신고", "답변", "상태")):
        focuses.append("접수·상태")
    if contains_any(text, ("문맥", "컨텍스트", "이력", "Single-view", "고객 KEY", "상담이력", "여정")):
        focuses.append("문맥·이력")
    if contains_any(text, ("실패", "불가", "지연", "대체", "재시도", "복구")):
        focuses.append("예외")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def customer_center_hub_requirement_semantic_label(text: str) -> str:
    axis = customer_center_hub_requirement_semantic_axis(text)
    focus = customer_center_hub_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def customer_center_hub_requirement_function_label(text: str) -> str:
    axis = customer_center_hub_requirement_semantic_axis(text)
    if axis == "셀프 해결 경로":
        return "셀프 해결 경로 판정"
    if axis == "상담 채널·전환":
        return "상담 채널 전환"
    if axis == "문의 접수·상태 관리":
        return "문의 접수·상태 처리"
    if axis == "상담 문맥·이력":
        return "상담 문맥·이력 구성"
    if axis == "운영·상담 Single-view":
        return "운영·상담 통합 관리"
    return "고객센터 허브 기준"


def customer_center_hub_policy_group_for_requirement(text: str) -> str:
    axis = customer_center_hub_requirement_semantic_axis(text)
    if axis == "셀프 해결 경로":
        return "후속 업무 연결 정책"
    if axis == "상담 채널·전환":
        return "예외·상담 전환 정책"
    if axis == "문의 접수·상태 관리":
        return "처리 요청 접수 정책"
    if axis == "상담 문맥·이력":
        return "처리 결과·이력 정책"
    if axis == "운영·상담 Single-view":
        return "운영 기준 정보 관리 정책"
    return "요구사항 반영 관리 정책"


def customer_center_faq_notice_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("운영자", "운영", "등록", "검수", "노출순서", "삭제", "게시", "승인", "버전", "최신화", "적용영역", "공통유의사항", "통합 운영", "FAQ 등록 방식")):
        return "콘텐츠 운영·버전 관리"
    if contains_any(text, ("장애", "점검", "긴급", "영향 범위", "복구 시점", "정책 변경", "변경 요약", "중요도", "공지")):
        return "공지·장애·점검"
    if contains_any(text, ("해결 실패", "미해결", "fallback", "폴백", "상담 연결", "문의하기", "CS", "추가 진단", "대체 탐색", "다음 행동", "바로가기")):
        return "해결 실패·CS 연결"
    if contains_any(text, ("이용안내", "가이드", "단계별", "동영상", "링크", "로밍", "외국인", "다국어", "접근성", "자가 진단", "체크리스트", "설정 가이드")):
        return "이용안내·가이드"
    if contains_any(text, ("FAQ", "faq", "자주 묻는", "Top", "검색", "카테고리", "추천", "문제 유형", "도움말", "고객지원 정보", "최종 업데이트")):
        return "FAQ 탐색·추천"
    return "안내 콘텐츠 기준"


def customer_center_faq_notice_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("목적", "유형", "카테고리", "검색", "추천", "우선", "Top")):
        focuses.append("탐색·추천")
    if contains_any(text, ("최신", "업데이트", "기준 시점", "버전", "변경", "요약")):
        focuses.append("최신성·변경")
    if contains_any(text, ("해결", "바로가기", "셀프", "실행", "다음 행동", "문의", "상담")):
        focuses.append("해결·연결")
    if contains_any(text, ("장애", "점검", "긴급", "영향", "복구", "대체")):
        focuses.append("영향·복구")
    if contains_any(text, ("등록", "검수", "게시", "노출", "삭제", "승인", "운영")):
        focuses.append("운영·노출")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def customer_center_faq_notice_requirement_semantic_label(text: str) -> str:
    axis = customer_center_faq_notice_requirement_semantic_axis(text)
    focus = customer_center_faq_notice_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def customer_center_faq_notice_requirement_function_label(text: str) -> str:
    axis = customer_center_faq_notice_requirement_semantic_axis(text)
    if axis == "FAQ 탐색·추천":
        return "FAQ 탐색·추천 구성"
    if axis == "이용안내·가이드":
        return "이용안내 가이드 연결"
    if axis == "공지·장애·점검":
        return "공지 영향 안내"
    if axis == "해결 실패·CS 연결":
        return "미해결 후속 연결"
    if axis == "콘텐츠 운영·버전 관리":
        return "안내 콘텐츠 운영 관리"
    return "안내 콘텐츠 기준"


def customer_center_faq_notice_policy_group_for_requirement(text: str) -> str:
    axis = customer_center_faq_notice_requirement_semantic_axis(text)
    if axis == "FAQ 탐색·추천":
        return "대상 정보 노출 정책"
    if axis == "이용안내·가이드":
        return "후속 업무 연결 정책"
    if axis == "공지·장애·점검":
        return "알림·고지 정책"
    if axis == "해결 실패·CS 연결":
        return "예외·상담 전환 정책"
    if axis == "콘텐츠 운영·버전 관리":
        return "운영 기준 정보 관리 정책"
    return "요구사항 반영 관리 정책"


def customer_center_store_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("홈페이지", "마이크로사이트", "전용 URL", "URL", "QR", "단축 링크", "공유", "리다이렉트", "콘텐츠", "프로모션", "상품", "추천 상품", "노출 기간")):
        return "대리점 사이트·URL 운영"
    if contains_any(text, ("단골", "선호 매장", "최근 방문", "방문 매장", "알림 수신", "혜택")):
        return "단골 매장·개인화"
    if contains_any(text, ("매장 찾기", "매장 검색", "지도", "리스트", "위치", "거리순", "지역", "지하철", "속성 필터", "주차", "외국어", "체험존", "주소")):
        return "매장 검색·위치 기준"
    if contains_any(text, ("처리 가능 업무", "예약 가능", "예약", "방문", "운영 여부", "영업시간", "휴무", "연락처", "운영 시간")):
        return "방문 가능성·예약 기준"
    if contains_any(text, ("재고", "팝업", "통합 운영", "공통 팝업", "전환 조건", "운영 가능 여부", "검토")):
        return "매장 안내 운영·통합 기준"
    return "매장 안내 기준"


def customer_center_store_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("위치", "거리순", "지도", "리스트", "지역", "지하철", "검색", "필터", "속성")):
        focuses.append("탐색·정렬")
    if contains_any(text, ("처리 가능", "예약 가능", "영업시간", "휴무", "운영 여부", "방문", "준비")):
        focuses.append("방문 가능성")
    if contains_any(text, ("URL", "QR", "공유", "마이크로사이트", "홈페이지", "콘텐츠", "프로모션")):
        focuses.append("노출·공유")
    if contains_any(text, ("단골", "선호", "최근 방문", "알림", "혜택")):
        focuses.append("개인화")
    if contains_any(text, ("재고", "팝업", "통합", "전환", "검토", "운영")):
        focuses.append("운영·통합")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def customer_center_store_requirement_semantic_label(text: str) -> str:
    axis = customer_center_store_requirement_semantic_axis(text)
    focus = customer_center_store_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def customer_center_store_requirement_function_label(text: str) -> str:
    axis = customer_center_store_requirement_semantic_axis(text)
    if axis == "대리점 사이트·URL 운영":
        return "대리점 사이트·URL 구성"
    if axis == "단골 매장·개인화":
        return "단골 매장 개인화"
    if axis == "매장 검색·위치 기준":
        return "매장 검색·위치 정렬"
    if axis == "방문 가능성·예약 기준":
        return "방문 가능성·예약 안내"
    if axis == "매장 안내 운영·통합 기준":
        return "매장 안내 운영 통합"
    return "매장 안내 기준"


def customer_center_store_policy_group_for_requirement(text: str) -> str:
    axis = customer_center_store_requirement_semantic_axis(text)
    if axis == "대리점 사이트·URL 운영":
        return "대리점 사이트·URL 운영 정책"
    if axis == "단골 매장·개인화":
        return "단골 매장·개인화 정책"
    if axis == "매장 검색·위치 기준":
        return "매장 검색·위치 기준 정책"
    if axis == "방문 가능성·예약 기준":
        return "방문 가능성·예약 정책"
    if axis == "매장 안내 운영·통합 기준":
        return "매장 안내 운영·통합 정책"
    return "매장 안내 기준 정책"


def notification_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("운영자", "운영", "관리", "모니터링", "템플릿", "문구", "승인", "품질", "정책 관리", "공지", "점검")):
        return "알림 운영 기준"
    if contains_any(text, ("OS", "푸시 권한", "권한", "허용", "거부", "재요청", "설정 앱", "권한 상태")):
        return "푸시 권한·수신 허용"
    if contains_any(text, ("수신 설정", "채널", "유형", "카테고리", "문자", "SMS", "Email", "이메일", "앱푸시", "카톡", "언어", "연락처", "토글", "ON", "OFF")):
        return "수신 설정·채널 기준"
    if contains_any(text, ("알림함", "알림센터", "상세", "클릭", "딥링크", "이동", "컨텍스트", "필터", "목록", "타임라인", "병합", "후속", "상담")):
        return "알림함·후속 연결"
    if contains_any(text, ("우선순위", "중복", "빈도", "피로", "조용한 시간", "다시알림", "snooze", "스누즈", "읽음", "삭제", "중요", "무효", "동기화", "상태")):
        return "우선순위·중복 제어"
    if contains_any(text, ("실패", "미발송", "발송 실패", "수신 실패", "재발송", "재시도", "fallback", "폴백", "복구", "장애", "제한")):
        return "발송 실패·복구"
    if contains_any(text, ("필수", "거래", "보안", "납부", "결제", "혜택", "만료", "가입", "유지기간", "배송", "주문", "답변", "인증 필요", "처리 필요", "잔고", "부족", "출금", "청구", "요금", "납기")):
        return "필수·거래성 알림"
    return "알림 기준"


def notification_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("수신", "채널", "연락처", "언어", "설정", "토글", "ON", "OFF")):
        focuses.append("수신·설정")
    if contains_any(text, ("발송", "푸시", "문자", "이메일", "카톡", "권한", "요청")):
        focuses.append("발송·권한")
    if contains_any(text, ("알림함", "알림센터", "상세", "클릭", "이동", "후속", "컨텍스트", "필터", "목록")):
        focuses.append("조회·연결")
    if contains_any(text, ("우선순위", "중복", "빈도", "조용한 시간", "다시알림", "무효", "동기화", "읽음")):
        focuses.append("우선순위·상태")
    if contains_any(text, ("실패", "오류", "장애", "재시도", "복구", "상담", "폴백", "제한")):
        focuses.append("예외·복구")
    if contains_any(text, ("이력", "저장", "증적", "로그", "보관")):
        focuses.append("이력")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def notification_requirement_semantic_label(text: str) -> str:
    axis = notification_requirement_semantic_axis(text)
    focus = notification_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def notification_requirement_function_label(text: str) -> str:
    axis = notification_requirement_semantic_axis(text)
    if axis == "푸시 권한·수신 허용":
        return "푸시 권한·수신 허용 처리"
    if axis == "수신 설정·채널 기준":
        return "수신 설정·채널 적용"
    if axis == "알림함·후속 연결":
        return "알림함·후속 연결"
    if axis == "우선순위·중복 제어":
        return "우선순위·중복 제어"
    if axis == "발송 실패·복구":
        return "발송 실패·복구 처리"
    if axis == "필수·거래성 알림":
        return "필수·거래성 알림 판정"
    if axis == "알림 운영 기준":
        return "알림 운영 기준"
    return "알림 기준"


def notification_policy_group_for_requirement(text: str) -> str:
    axis = notification_requirement_semantic_axis(text)
    if axis in {"푸시 권한·수신 허용", "수신 설정·채널 기준"}:
        return "알림 수신 설정 정책"
    if axis == "알림함·후속 연결":
        return "후속 업무 연결 정책"
    if axis == "우선순위·중복 제어":
        return "중복 요청 제한 정책"
    if axis == "발송 실패·복구":
        return "예외·상담 전환 정책"
    if axis == "필수·거래성 알림":
        return "알림·고지 정책"
    if axis == "알림 운영 기준":
        return "운영 기준 정보 관리 정책"
    return "알림·고지 정책"


def terms_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("법정대리인", "미성년", "외국인", "OMD", "USIM", "SMS 링크", "오프라인")):
        return "예외 동의·분기"
    if contains_any(text, ("제3자", "위탁", "개인정보", "개인위치", "위치기반", "쿠키", "민감", "다운로드", "열람/정정/삭제", "정정", "삭제")):
        return "개인정보·제3자 고지"
    if contains_any(text, ("철회", "재동의", "거부권", "거부", "동의 변경", "부분 철회")):
        return "철회·재동의"
    if contains_any(text, ("변경", "개정", "시행일", "버전", "이력", "증빙", "감사", "아카이브", "발행", "종료일")):
        return "버전·증적"
    if contains_any(text, ("필수", "선택", "동의 상태", "동의항목", "체크박스", "동적", "상품 선택", "미동의", "비활성", "제한", "결제 동의")):
        return "필수·선택 동의"
    if contains_any(text, ("검색", "열람", "목록", "다운로드", "요약", "상세", "고지", "원문", "적용 대상", "서비스/채널", "오픈소스")):
        return "약관 열람·고지"
    return "약관 기준"


def terms_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("필수", "선택", "목적별", "서비스별", "분리", "동의항목")):
        focuses.append("구분")
    if contains_any(text, ("철회", "재동의", "거부", "거부권")):
        focuses.append("철회")
    if contains_any(text, ("버전", "시행일", "개정", "변경", "이력", "증빙", "감사")):
        focuses.append("버전·이력")
    if contains_any(text, ("개인정보", "제3자", "위탁", "쿠키", "위치", "민감")):
        focuses.append("고지")
    if contains_any(text, ("법정대리인", "미성년", "외국인", "OMD", "USIM")):
        focuses.append("예외")
    if contains_any(text, ("제한", "차단", "미동의", "비활성", "영향")):
        focuses.append("영향")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def terms_requirement_semantic_label(text: str) -> str:
    axis = terms_requirement_semantic_axis(text)
    focus = terms_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def terms_requirement_function_label(text: str) -> str:
    axis = terms_requirement_semantic_axis(text)
    if axis == "약관 열람·고지":
        return "약관 열람·고지 구성"
    if axis == "필수·선택 동의":
        return "필수·선택 동의 판정"
    if axis == "철회·재동의":
        return "철회·재동의 처리"
    if axis == "개인정보·제3자 고지":
        return "개인정보·제3자 고지 구성"
    if axis == "버전·증적":
        return "약관 버전·증적 관리"
    if axis == "예외 동의·분기":
        return "예외 동의·분기 판정"
    return "약관 기준 처리"


def terms_policy_group_for_requirement(text: str) -> str:
    axis = terms_requirement_semantic_axis(text)
    if axis == "약관 열람·고지":
        return "대상 정보 노출 정책"
    if axis in {"필수·선택 동의", "철회·재동의", "예외 동의·분기"}:
        return "인증·동의 정책"
    if axis == "개인정보·제3자 고지":
        return "개인정보·로그 보호 정책"
    if axis == "버전·증적":
        return "처리 결과·이력 정책"
    return "인증·동의 정책"


def member_info_requirement_semantic_axis(text: str) -> str:
    text = clean_schema_text(text)
    if contains_any(text, ("운영자", "운영", "관리", "모니터링", "보정", "승인", "품질", "정책 관리", "기준값")):
        return "회원정보 운영 기준"
    if contains_any(text, ("법인", "위임", "대리", "대표자", "관리자", "그룹", "구성원", "법정대리인", "미성년")):
        return "권한·관계 정보 관리"
    if contains_any(text, ("조회", "목록", "용도", "마스킹", "노출", "조회 범위", "대표값", "보조값", "미검증", "출처", "우선순위", "불일치", "충돌", "정합", "비교", "기준 시점")):
        return "조회 범위·정합화"
    if contains_any(text, ("주소", "주소록", "연락처", "이메일", "환불 계좌", "계좌", "프로필", "기본 정보", "외국인")) and contains_any(
        text, ("변경", "수정", "등록", "삭제", "편집", "기본", "대표")
    ):
        return "회원정보 변경"
    if contains_any(text, ("인증", "본인확인", "재인증", "검증", "OTP", "링크", "세션", "로그아웃", "토큰")):
        return "검증·재인증"
    if contains_any(text, ("이력", "감사", "로그", "알림", "고지", "통지", "상태", "진행 현황", "중단", "복원", "fallback", "상담", "복구")):
        return "변경 이력·복구"
    if contains_any(text, ("결합", "할인", "명의변경", "공공 마이데이터", "전자공문서", "증빙", "서류")):
        return "증빙·외부 제출"
    return "회원정보 기준"


def member_info_requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("조회", "확인", "표시", "노출", "마스킹", "기준 시점")):
        focuses.append("조회·표시")
    if contains_any(text, ("변경", "수정", "등록", "삭제", "저장", "기본값", "대표값")):
        focuses.append("변경·저장")
    if contains_any(text, ("인증", "본인확인", "재인증", "권한", "대리", "법정", "법인")):
        focuses.append("권한·인증")
    if contains_any(text, ("영향", "알림", "고지", "안내", "세션", "로그아웃")):
        focuses.append("영향·고지")
    if contains_any(text, ("불일치", "충돌", "정합", "보정", "동기화", "출처")):
        focuses.append("정합화")
    if contains_any(text, ("실패", "오류", "불가", "상담", "fallback", "복구", "중단", "복원")):
        focuses.append("예외·복구")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def member_info_requirement_semantic_label(text: str) -> str:
    axis = member_info_requirement_semantic_axis(text)
    focus = member_info_requirement_semantic_focus(text)
    if focus == "판단":
        return f"{axis} 기준"
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    return f"{axis} {focus_label} 기준" if focus_label else f"{axis} 기준"


def member_info_requirement_function_label(text: str) -> str:
    axis = member_info_requirement_semantic_axis(text)
    if axis == "조회 범위·정합화":
        return "조회 범위·정합화"
    if axis == "회원정보 변경":
        return "회원정보 변경 처리"
    if axis == "권한·관계 정보 관리":
        return "권한·관계 검증"
    if axis == "검증·재인증":
        return "검증·재인증 처리"
    if axis == "변경 이력·복구":
        return "변경 이력·복구 처리"
    if axis == "증빙·외부 제출":
        return "증빙·외부 제출 처리"
    if axis == "회원정보 운영 기준":
        return "회원정보 운영 기준"
    return "회원정보 기준"


def member_info_policy_group_for_requirement(text: str) -> str:
    axis = member_info_requirement_semantic_axis(text)
    if axis == "조회 범위·정합화":
        return "대상 정보 노출 정책"
    if axis == "회원정보 변경":
        return "처리 요청 접수 정책"
    if axis in {"권한·관계 정보 관리", "검증·재인증"}:
        return "접근·권한 정책"
    if axis == "변경 이력·복구":
        return "처리 결과·이력 정책"
    if axis == "증빙·외부 제출":
        return "입력값 검증 정책"
    if axis == "회원정보 운영 기준":
        return "운영 기준 정보 관리 정책"
    return "가능 여부 검증 정책"


def requirement_semantic_focus(text: str) -> str:
    text = clean_schema_text(text)
    focuses = []
    if contains_any(text, ("인증", "본인확인", "세션", "로그인", "동의", "권한")):
        focuses.append("인증")
    if contains_any(text, ("상태", "제한", "가능", "조건", "보류", "중단")):
        focuses.append("상태·제한")
    if contains_any(text, ("결과", "안내", "고지", "알림", "통지", "회신")):
        focuses.append("결과·고지")
    if contains_any(text, ("BSS", "연계", "동기화", "정합성", "원장", "반영")):
        focuses.append("BSS 반영")
    if contains_any(text, ("이력", "저장", "보관", "증적", "로그", "파기", "삭제")):
        focuses.append("이력")
    if contains_any(text, ("입력", "필수", "형식", "검증", "수집")):
        focuses.append("입력")
    if contains_any(text, ("실패", "오류", "장애", "예외", "재시도", "상담")):
        focuses.append("예외")
    if not focuses:
        focuses.append("판단")
    return "·".join(focuses[:2])


def requirement_semantic_label(text: str, actor: str | None = None) -> str:
    axis = requirement_semantic_axis(text, actor)
    focus = requirement_semantic_focus(text)
    axis_tokens = set(axis.replace(" ", "·").split("·"))
    focus_tokens = [token for token in focus.replace(" ", "·").split("·") if token and token not in axis_tokens]
    focus_label = "·".join(focus_tokens[:2])
    if not focus_label or focus_label == "판단":
        return f"{axis} 기준"
    return f"{axis} {focus_label} 기준"


def requirement_function_label(text: str, actor: str | None = None) -> str:
    axis = requirement_semantic_axis(text, actor)
    if actor == "운영자" or axis == "운영 기준":
        return "운영 기준"
    if axis == "약관·동의":
        return "약관·동의 처리"
    if axis == "해지·취소":
        return "해지·취소 조건"
    if axis == "가입·신청":
        return "가입·신청 조건"
    if axis == "조회·탐색":
        return "조회·탐색 정보"
    if axis == "결제·혜택":
        return "결제·혜택 조건"
    if axis == "인증·권한":
        return "인증·권한 검증"
    if axis == "고지·안내":
        return "고지·안내 구성"
    if axis == "이력·보관":
        return "이력·보관 처리"
    if axis == "연계 판정":
        return "연계 판정"
    if axis == "변경":
        return "변경 조건"
    return "업무 조건"


def requirement_term_name(item: Mapping[str, object]) -> str:
    return compact_text(item.get("semantic_label") or derive_requirement_term_name(str(item.get("title", ""))), 34)


def derive_requirement_term_name(title: str) -> str:
    text = clean_schema_text(title)
    text = re.sub(r"\s*(제공|관리|조회|안내|처리|지원|정의)$", "", text).strip()
    return compact_text(text, 34)


def requirement_term_description(item: dict) -> str:
    label = item.get("semantic_label") or requirement_term_name(item)
    if item.get("actor") == "운영자":
        return f"{label}에 필요한 운영 기준, 적용 조건, 변경 이력, 품질 확인 기준을 뜻한다."
    return f"고객이 업무를 확인하거나 후속 행동을 선택할 때 적용하는 {label}의 정보·상태·권한 기준을 뜻한다."


def requirement_usecase_rows(items: Sequence[dict], max_items: int = 17) -> List[tuple[str, str, str, str, str]]:
    rows = []
    for item in items[:max_items]:
        suffix = f"RQCOV-{item['index']:03d}"
        actor = item.get("actor", "고객")
        label = item.get("semantic_label") or item["short_title"]
        name = f"{label} 관리" if actor == "운영자" and "관리" not in label else label
        description = (
            f"운영자가 {label}의 기준, 상태, 예외, 변경 이력을 관리하는 유즈케이스"
            if actor == "운영자"
            else f"고객이 {korean_object(label)} 확인하고 필요한 다음 행동을 선택하는 유즈케이스"
        )
        rows.append((suffix, actor, compact_text(name, 56), compact_text(description, 110), "Y"))
    return rows


def requirement_process_rows(items: Sequence[dict], max_items: int = 17) -> List[tuple[str, str, str, str, List[str], List[str]]]:
    rows = []
    for item in items[:max_items]:
        label = item.get("semantic_label") or item["short_title"]
        function_label = item.get("function_label") or requirement_function_label(requirement_full_text(item), item.get("actor"))
        process_name = f"{label} 처리"
        usecase_suffix = requirement_usecase_suffix_for_item(item)
        if item.get("actor") == "운영자":
            description = f"{label}과 예외 조건을 운영자가 관리하고 변경 이력을 남긴다."
            functions = [f"{function_label} 기준 관리", f"{function_label} 품질 확인"]
            policies = ["운영 기준 정보 관리 정책", "운영 변경 이력 관리 정책"]
        else:
            description = f"{label}에 필요한 상태·권한·후속 행동 기준을 확인한다."
            functions = [f"{function_label} 정보 구성", requirement_condition_function_name(function_label)]
            policies = policies_for_requirement(item)
        rows.append(
            (
                usecase_suffix,
                f"RQCOV-{item['index']:03d}",
                compact_text(process_name, 60),
                compact_text(description, 110),
                policies,
                [compact_text(function, 70) for function in functions],
            )
        )
    return rows


def requirement_function_rows(items: Sequence[dict], max_items: int = 17) -> List[tuple[str, str, str, str, List[str]]]:
    rows = []
    for item in items[:max_items]:
        label = item.get("semantic_label") or item["short_title"]
        function_label = item.get("function_label") or requirement_function_label(requirement_full_text(item), item.get("actor"))
        process_suffix = f"{requirement_usecase_suffix_for_item(item)}-RQCOV-{item['index']:03d}"
        if item.get("actor") == "운영자":
            rows.append(
                (
                    f"RQCOV-{item['index']:03d}-MNG",
                    process_suffix,
                    f"{function_label} 기준 관리",
                    f"{label}의 기준값, 노출 조건, 예외 조건을 운영 관리한다.",
                    ["기준값 등록", "적용 기간 관리", "예외 조건 관리", "변경 이력 저장"],
                )
            )
            rows.append(
                (
                    f"RQCOV-{item['index']:03d}-QUL",
                    process_suffix,
                    f"{function_label} 품질 확인",
                    f"{label}의 오류, 지연, 불일치, 고객 불편 지표를 확인한다.",
                    ["품질 지표 조회", "불일치 확인", "보정 대상 등록", "운영 결과 저장"],
                )
            )
            continue
        rows.append(
                (
                    f"RQCOV-{item['index']:03d}-INF",
                    process_suffix,
                    f"{function_label} 정보 구성",
                    f"{label}에 필요한 기준 정보와 고객별 적용 정보를 구성한다.",
                    ["대상 정보 조회", "상태 정보 구성", "기준일 표시", "다음 행동 연결"],
                )
            )
        rows.append(
            (
                    f"RQCOV-{item['index']:03d}-CHK",
                    process_suffix,
                    requirement_condition_function_name(function_label),
                    f"{label}의 권한, 상태, 제한, 후속 처리 가능 여부를 확인한다.",
                    ["권한 확인", "상태 확인", "제한 사유 확인", "고객 안내 생성"],
                )
        )
    return rows


def requirement_usecase_suffix_for_item(item: Mapping[str, object]) -> str:
    text = f"{item.get('title', '')} {item.get('short_title', '')} {item.get('description', '')}"
    if item.get("actor") == "운영자" or is_operator_requirement(text):
        return "OPR-001"
    if contains_any(text, ("탈퇴", "해지", "취소", "철회", "복구", "재시도", "후속", "상담")):
        return "CS-003"
    if contains_any(text, ("가입", "신청", "등록", "인증", "동의", "입력", "처리", "검증", "제한")):
        return "CS-002"
    return "CS-001"


def requirement_policy_details(code: str, policy_groups: Sequence[dict], items: Sequence[dict], max_items: int = 17) -> List[dict]:
    group_by_name = {group["name"]: group["id"] for group in policy_groups}
    details = []
    used_names: set[str] = set()
    for item in items[:max_items]:
        group_name = item.get("policy_group") or "대상 정보 노출 정책"
        policy_id = group_by_name.get(group_name, group_by_name.get("요구사항 반영 관리 정책", ""))
        if not policy_id:
            continue
        name = unique_requirement_policy_detail_name(requirement_policy_item_name(item), item, used_names)
        used_names.add(name)
        details.append(
            {
                "id": f"PI-{code}-RQCOV-{item['index']:03d}",
                "policy_id": policy_id,
                "name": name,
                "content": ensure_policy_decision_content(requirement_policy_content(item)),
            }
        )
    return details


def unique_requirement_policy_detail_name(name: str, item: Mapping[str, object], used_names: set[str]) -> str:
    base_name = compact_text(name, 60)
    if base_name and base_name not in used_names:
        return base_name
    candidates = []
    axis = str(item.get("semantic_axis") or "").strip()
    focus = str(item.get("semantic_focus") or "").strip()
    if axis or focus:
        candidates.append(compact_text(" ".join(part for part in (axis, focus, base_name) if part), 60))
    for candidate in candidates:
        if candidate and candidate not in used_names:
            return candidate
    index = int(item.get("index") or len(used_names) + 1)
    return compact_text(f"{base_name or '요구사항 판단 기준'} {index:02d}", 60)


def requirement_policy_content(item: dict) -> str:
    label = requirement_policy_item_name(item) or item.get("semantic_label")
    label_subject = korean_subject(label)
    axes = requirement_policy_axes(item)
    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or requirement_semantic_axis(text, item.get("actor")))
    focus = str(item.get("semantic_focus") or requirement_semantic_focus(text))
    axes_text = ", ".join(axes)
    index = int(item.get("index") or 0)
    if axis in {
        "대리점 사이트·URL 운영",
        "단골 매장·개인화",
        "매장 검색·위치 기준",
        "방문 가능성·예약 기준",
        "매장 안내 운영·통합 기준",
        "매장 안내 기준",
    }:
        return compact_text(with_requirement_decision_prefix(customer_center_store_policy_content(item, label, axes_text, index), index), 190)
    if axis in {
        "FAQ 탐색·추천",
        "이용안내·가이드",
        "공지·장애·점검",
        "해결 실패·CS 연결",
        "콘텐츠 운영·버전 관리",
        "안내 콘텐츠 기준",
    }:
        return compact_text(with_requirement_decision_prefix(customer_center_faq_notice_policy_content(item, label, axes_text, index), index), 190)
    if item.get("actor") == "운영자":
        variants = [
            f"{label_subject} 기준값, 예외 조건, 적용 기간, 승인 상태를 함께 등록한 경우에만 운영 기준으로 배포한다.",
            f"{label} 변경 시 변경 전후 값, 승인자, 배포 일시, 롤백 가능 여부를 운영 이력으로 저장한다.",
            f"{label}의 품질 확인은 오류율, 고객 불편, 기준 불일치, 보정 필요 여부를 기준으로 수행한다.",
        ]
        return compact_text(with_requirement_decision_prefix(variants[index % len(variants)], index), 170)
    if axis in {
        "셀프 해결 경로",
        "상담 채널·전환",
        "문의 접수·상태 관리",
        "상담 문맥·이력",
        "운영·상담 Single-view",
        "고객센터 허브 기준",
    }:
        return compact_text(with_requirement_decision_prefix(customer_center_hub_policy_content(item, label, axes_text, index), index), 190)
    if axis in {
        "조회 범위·정합화",
        "회원정보 변경",
        "권한·관계 정보 관리",
        "검증·재인증",
        "변경 이력·복구",
        "증빙·외부 제출",
        "회원정보 기준",
    }:
        return compact_text(with_requirement_decision_prefix(member_info_policy_content(item, label, axes_text, index), index), 190)
    if axis in {
        "푸시 권한·수신 허용",
        "수신 설정·채널 기준",
        "알림함·후속 연결",
        "우선순위·중복 제어",
        "발송 실패·복구",
        "필수·거래성 알림",
        "알림 운영 기준",
        "알림 기준",
    }:
        return compact_text(with_requirement_decision_prefix(notification_policy_content(item, label, axes_text, index), index), 190)
    if axis in {
        "개인화·접근성 설정",
        "알림 설정",
        "동의·권한 설정",
        "보안 설정",
        "기록·초기화 설정",
        "설정 변경",
        "설정 기준",
    }:
        return compact_text(with_requirement_decision_prefix(settings_policy_content(item, label, axes_text, index), index), 190)
    if axis == "해지·취소":
        return compact_text(with_requirement_decision_prefix(termination_refund_policy_content(item, label, axes_text, index), index), 190)
    elif axis == "가입·신청":
        variants = [
            f"{label_subject} {axes_text} 항목을 확인한 뒤 대상 고객과 제한 고객을 구분해 접수 가능 여부를 판정한다.",
            f"{label_subject} {axes_text} 중 미충족 항목이 있으면 보완 항목과 재시도 가능 조건을 안내하고 접수를 제한한다.",
            f"{label_subject} {axes_text} 완료 결과를 동의 이력, 제한 조건, 후속 안내 항목으로 저장해 다음 단계 기준으로 사용한다.",
        ]
    elif axis in {
        "약관·동의",
        "약관 열람·고지",
        "필수·선택 동의",
        "철회·재동의",
        "개인정보·제3자 고지",
        "버전·증적",
        "예외 동의·분기",
        "약관 기준",
    }:
        return compact_text(with_requirement_decision_prefix(terms_consent_policy_content(item, label, axes_text, index), index), 190)
    elif "인증" in axis or "인증" in focus:
        variants = [
            f"{label_subject} {axes_text} 항목을 검증해 민감정보 노출과 상태 변경 전 재인증 필요 여부를 결정한다.",
            f"{label_subject} {axes_text} 실패 시 가능 횟수, 유효시간, 재시도 가능 여부, 상담 전환 기준을 안내한다.",
            f"{label_subject} {axes_text} 결과를 인증 수단, 성공·실패 사유, 세션 유효성, 동의 이력으로 저장한다.",
        ]
    elif "연계" in axis or "BSS" in focus:
        variants = [
            f"{label_subject} {axes_text} 항목으로 BSS 또는 연계 시스템 판정 결과를 확정하고 불일치 시 보류한다.",
            f"{label_subject} {axes_text} 불일치가 발생하면 최신 원장 기준, 재조회 가능 여부, 운영 확인 필요 여부를 분류한다.",
            f"{label_subject} {axes_text} 회신 결과를 성공, 실패, 지연, 보류로 구분하고 상태 전환과 안내 이력을 저장한다.",
        ]
    elif "고지" in axis or "고지" in focus:
        variants = [
            f"{label_subject} {axes_text} 항목을 기준으로 필수 안내 대상, 안내 시점, 확인 필요 여부를 결정한다.",
            f"{label_subject} {axes_text} 누락 시 고객 오인 가능성이 있는 항목은 다음 단계 진행을 제한하고 확인 이력을 요구한다.",
            f"{label_subject} {axes_text} 발송 결과와 고객 확인 여부를 처리 이력에 저장하고 재안내 기준으로 사용한다.",
        ]
    elif "조회" in axis:
        variants = [
            f"{label_subject} {axes_text} 항목을 기준으로 고객에게 노출할 대상, 정렬, 제한 정보를 결정한다.",
            f"{label_subject} {axes_text} 개인화 결과 중 권한과 고객 상태가 충족된 항목만 제공하고 기준일을 표시한다.",
            f"{label_subject} {axes_text} 조회 실패 또는 결과 없음 상태를 대체 경로, 재조회 가능 여부, 상담 기준으로 안내한다.",
        ]
    else:
        variants = [
            f"{label_subject} {axes_text} 항목을 기준으로 처리 가능 여부와 고객 안내 기준을 판단한다.",
            f"{label} 중 필수 조건이 충족되지 않으면 제한 사유와 다음 행동을 분류해 고객에게 안내한다.",
            f"{label} 판정 결과는 요청 상태, 실패 사유, 재검증 기준, 처리 이력으로 저장한다.",
        ]
    return compact_text(with_requirement_decision_prefix(variants[index % len(variants)], index), 170)


def termination_refund_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write termination, refund, cancellation, and rollback details without repeated boilerplate."""

    text = requirement_full_text(item)
    label_text = clean_schema_text(label or item.get("semantic_label") or "해지·취소 기준")
    if contains_any(text, ("환불", "정산", "취소 금액", "결제 취소", "환급", "청구")):
        variants = [
            f"환불 산정은 결제 상태, 사용 이력, 제공 완료 여부, 취소 시점, 공제 대상 금액을 확인한 뒤 확정한다.",
            f"환불 제한 사유가 있으면 제한 항목, 산정 기준일, 고객 부담 금액, 상담 전환 가능 여부를 처리 전에 안내한다.",
            f"환불 처리 결과는 원결제 수단, 환불 금액, 반영 예정일, 실패 사유, 재처리 이력으로 저장한다.",
        ]
    elif contains_any(text, ("복구", "원복", "재개", "복원", "되돌림")):
        variants = [
            f"원복 가능 여부는 해지·취소 이전 상태, 원장 반영 여부, 혜택 회수 여부, 복구 제한 시간을 기준으로 판단한다.",
            f"복구가 불가하면 불가 사유, 대체 신청 경로, 재가입 필요 여부, 고객 영향 범위를 구분해 안내한다.",
            f"복구 요청 결과는 이전 상태, 복구 후 상태, BSS 반영 결과, 운영 승인 여부, 처리 이력으로 저장한다.",
        ]
    elif contains_any(text, ("철회", "취소", "예약", "신청 취소", "주문 취소")):
        variants = [
            f"취소·철회 허용은 접수 상태, 처리 진행 단계, 고객 확인 여부, 비용·혜택 영향 발생 전후를 기준으로 판단한다.",
            f"취소 제한 시에는 이미 진행된 처리 단계, 되돌릴 수 없는 항목, 예상 후속 조치, 상담 필요 여부를 안내한다.",
            f"철회 결과는 요청 상태, 취소 가능 시점, 원복 대상, 고객 고지 여부, 중복 요청 제한 이력으로 저장한다.",
        ]
    elif contains_any(text, ("탈퇴", "해지", "종료", "해제")):
        variants = [
            f"해지 접수는 본인확인, 대상 계약, 잔여 약정, 미납·정산, 보유 혜택 영향이 확인된 경우에만 허용한다.",
            f"해지 제한 조건이 있으면 인증 필요 여부, 처리 가능 상태, 제한 사유, 해소 방법, 처리 가능 시점, 고객이 선택할 수 있는 대체 경로를 안내한다.",
            f"해지 완료 결과는 계약 상태, 해지 일시, 회수·소멸 대상, 재가입 제한 여부, BSS 반영 이력으로 저장한다.",
        ]
    elif contains_any(text, ("상태", "진행", "보류", "완료", "실패")):
        variants = [
            f"상태 판정은 요청 접수, 검증 중, 처리 중, 완료, 실패, 보류, 제한 상태를 구분해 후속 행동을 결정한다.",
            f"상태가 보류 또는 실패이면 고객에게 필요한 보완 항목, 재시도 가능 여부, 운영 확인 예상 기준을 안내한다.",
            f"상태 변경 이력은 이전 상태, 다음 상태, 전이 사유, 처리 주체, 고객 안내 여부로 남긴다.",
        ]
    elif contains_any(text, ("안내", "알림", "고지", "통지")):
        variants = [
            f"고지 기준은 해지·취소·환불로 인한 비용, 혜택, 약정, 데이터, 재가입 영향이 발생하는 경우를 대상으로 한다.",
            f"고객 확인이 필요한 항목은 최종 처리 전 요약·상세 안내를 제공하고 확인 이력이 없으면 완료 처리하지 않는다.",
            f"알림 결과는 발송 채널, 수신 성공 여부, 재안내 필요 여부, 고객 후속 행동으로 저장한다.",
        ]
    else:
        variants = [
            f"{label_text}은 {axes_text} 항목을 기준으로 처리 가능 여부, 제한 사유, 후속 행동을 판단한다.",
            f"{label_text} 조건이 충족되지 않으면 보완 필요 항목, 재시도 가능 여부, 상담 전환 기준을 구분해 안내한다.",
            f"{label_text} 판정 결과는 요청 상태, 실패 사유, 재검증 기준, 처리 이력으로 저장한다.",
        ]
    return variants[index % len(variants)]


def customer_center_hub_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write customer-center hub details as routing/support criteria."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or customer_center_hub_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "고객센터 허브 기준")
    label_subject = korean_subject(label_text)
    if axis == "셀프 해결 경로":
        variants = [
            f"{label_subject} 문제 유형, 고객 상태, 처리 가능 범위, 준비 정보를 기준으로 셀프 해결 가능 여부를 먼저 판정한다.",
            f"{label_text}이 불가하면 불가 사유, 필요한 보완 정보, 상담·문의·매장 등 다음 경로를 함께 안내한다.",
            f"{label_text} 결과는 해결 시도, 실패 사유, 다음 행동, 상담 전환 여부와 함께 이력으로 저장한다.",
        ]
    elif axis == "상담 채널·전환":
        variants = [
            f"{label_subject} 문의 유형, 긴급도, 운영시간, 예상 대기, 인증·증빙 필요 여부를 기준으로 상담 채널을 추천한다.",
            f"{label_text} 지연 또는 이용 불가 시 대체 채널, 1:1 문의, 챗봇, 콜센터 전환 중 가능한 경로를 안내한다.",
            f"{label_text} 전환 시 직전 셀프 해결 시도, 고객 입력, 실패 사유, 준비 정보를 상담 문맥으로 함께 전달한다.",
        ]
    elif axis == "문의 접수·상태 관리":
        variants = [
            f"{label_subject} 문의 유형별 필수 입력, 첨부 허용 기준, 개인정보 마스킹, 동의 필요 여부를 충족한 경우에만 접수한다.",
            f"{label_text} 접수 후에는 접수, 확인, 조치 중, 답변 완료, 추가 정보 요청, 종결 상태를 고객에게 구분해 안내한다.",
            f"{label_text} 추가 정보가 필요하면 요청 사유, 제출 기한, 미제출 영향, 재접수 가능 여부를 함께 고지한다.",
        ]
    elif axis == "상담 문맥·이력":
        variants = [
            f"{label_subject} 고객 KEY, 직전 과업, 실패 사유, 문의·상담 이력, 디바이스·앱 정보를 상담 문맥으로 구성한다.",
            f"{label_text} 문맥 정보는 상담 목적에 필요한 범위만 전달하고 민감정보는 마스킹 또는 고객 동의 기준을 적용한다.",
            f"{label_text} 재유입 시 이전 상담 요약, 처리 상태, 남은 후속 행동을 유지해 고객이 같은 내용을 반복 설명하지 않게 한다.",
        ]
    elif axis == "운영·상담 Single-view":
        variants = [
            f"{label_subject} 셀프처리 가능 업무와 상담 이관 업무를 상품 복잡도, 처리 실패율, VOC 위험도, 운영시간 기준으로 구분한다.",
            f"{label_text} 운영 기준 변경 시 적용 기간, 승인 상태, 품질 지표, 롤백 가능 여부를 함께 관리한다.",
            f"{label_text} 상담 Single-view에는 고객 여정, 문의 상태, 실패 사유, 후속 조치가 한 화면 기준으로 연결되게 한다.",
        ]
    else:
        variants = [
            f"{label_subject} 고객 문제 유형, 처리 조건, 상담 필요 여부, 후속 안내 기준을 함께 판단한다.",
            f"{label_text} 조건이 충족되지 않으면 제한 사유와 다음 행동을 구분해 안내하고 상담 전환 가능 여부를 표시한다.",
            f"{label_text} 판정 결과는 고객센터 상태, 문의 이력, 상담 전환 문맥, 처리 결과 이력으로 저장한다.",
        ]
    return variants[index % len(variants)]


def customer_center_faq_notice_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write FAQ, notice, and guide details as content-governance and resolution criteria."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or customer_center_faq_notice_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "안내 콘텐츠 기준")
    label_subject = korean_subject(label_text)
    if axis == "FAQ 탐색·추천":
        variants = [
            f"{label_subject} 고객 목적, 문제 유형, 최근 급증 이슈, 개인 맥락을 기준으로 FAQ와 도움말 우선순위를 산정한다.",
            f"{label_text} 결과에는 해결 가능 여부, 관련 카테고리, 다음 행동, 최종 업데이트 기준일을 함께 표시한다.",
            f"{label_text} 검색 결과가 없으면 연관 카테고리, 추천 FAQ, 대표 문의 유형, 상담 연결 중 가능한 대체 경로를 제공한다.",
        ]
    elif axis == "이용안내·가이드":
        variants = [
            f"{label_subject} 고객이 안내 확인 후 1~2단계 안에 관련 셀프 처리, 조회, 설정, 신청 화면으로 이동할 수 있게 연결한다.",
            f"{label_text} 콘텐츠는 텍스트, 이미지, 영상, 링크 중 필요한 형식을 제공하되 최신 기준일과 적용 대상을 함께 표시한다.",
            f"{label_text} 외국인, 로밍, 접근성 대상 안내는 우선 제공 언어, 대체 경로, 상담 연결 가능 여부를 구분한다.",
        ]
    elif axis == "공지·장애·점검":
        variants = [
            f"{label_subject} 일반 안내, 중요 변경, 긴급 공지, 장애·점검 공지를 구분하고 고객 영향 범위와 예상 복구 시점을 표시한다.",
            f"{label_text} 정책 변경 공지는 변경 전후 핵심 차이, 적용일, 영향 범위, 고객 행동 필요 여부, 상세 원문 이동 경로를 함께 제공한다.",
            f"{label_text} 고객 회선·지역·상품 조건과 관련된 경우에는 해당 고객의 영향 범위를 판정해 공지를 우선 노출한다.",
        ]
    elif axis == "해결 실패·CS 연결":
        variants = [
            f"{label_subject} 미해결, 불만족, 검색 실패, 가이드 실패 시 현재 콘텐츠명, 검색어, 선택 경로를 유지해 문의·상담으로 연결한다.",
            f"{label_text} 상담 전환 전에는 추가 진단, 문의 템플릿, 필수 첨부, 대체 FAQ를 먼저 제시해 중복 설명을 줄인다.",
            f"{label_text} 전환 결과는 해결 여부, 재방문 콘텐츠, 상담 연결 여부, 개선 필요 콘텐츠 이력으로 저장한다.",
        ]
    elif axis == "콘텐츠 운영·버전 관리":
        variants = [
            f"{label_subject} 제목, 본문, 적용영역, 게시 기간, 노출순서, 승인 상태가 충족된 경우에만 프론트 노출 대상으로 배포한다.",
            f"{label_text} 변경 시 변경 전후 내용, 승인자, 게시 시작·종료일, 롤백 가능 여부, 삭제 가능 여부를 이력으로 저장한다.",
            f"{label_text} 콘텐츠 통합 운영 전환은 중복 안내 여부, FAQ 대체 가능성, 고객 영향, 기존 링크 유지 필요성을 기준으로 결정한다.",
        ]
    else:
        variants = [
            f"{label_subject} 고객 목적, 콘텐츠 유형, 최신성, 후속 행동, 상담 필요 여부를 함께 판단한다.",
            f"{label_text} 조건이 충족되지 않으면 안내 제한 사유와 대체 탐색 경로를 구분해 고객에게 제공한다.",
            f"{label_text} 판정 결과는 콘텐츠 상태, 노출 이력, 고객 피드백, 개선 필요 사유로 저장한다.",
        ]
    return variants[index % len(variants)]


def customer_center_store_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write store guide details as visit feasibility, URL, and store-operation criteria."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or customer_center_store_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "매장 안내 기준")
    label_subject = korean_subject(label_text)
    if axis == "대리점 사이트·URL 운영":
        variants = [
            f"{label_subject} 대리점 식별, 운영 상태, URL 규칙, 접근 권한, 만료·리다이렉트 기준이 충족된 경우에만 노출한다.",
            f"{label_text} 공유 경로는 전용 URL, QR, 단축 링크를 구분하고 공유 이후 접속 가능 기간과 폐쇄 시 대체 경로를 안내한다.",
            f"{label_text} 콘텐츠 변경 시 노출 기간, 예약·진행·종료 상태, 승인자, 변경 이력, 롤백 가능 여부를 저장한다.",
        ]
    elif axis == "단골 매장·개인화":
        variants = [
            f"{label_subject} 고객이 직접 등록·해제한 매장을 우선 적용하고 최근 방문·선호 매장은 추천 근거로만 사용한다.",
            f"{label_text} 혜택·알림 동의는 채널 공통 수신 동의와 분리해 안내하고 미동의 시 단골 등록 자체를 제한하지 않는다.",
            f"{label_text} 등록·해제 결과는 고객별 단골 목록, 동의 상태, 알림 수신 여부, 변경 이력으로 저장한다.",
        ]
    elif axis == "매장 검색·위치 기준":
        variants = [
            f"{label_subject} 위치 동의가 있으면 거리순을 기본으로 하되 매장명, 지역, 지하철, 매장 속성 필터를 함께 제공한다.",
            f"{label_text} 위치 동의가 없으면 지역·키워드 검색을 기본 경로로 제공하고 위치 기반 추천을 사용하지 않는다.",
            f"{label_text} 결과에는 영업시간, 휴무, 연락처, 주소, 제공 서비스, 처리 가능 업무, 정보 기준일을 함께 표시한다.",
        ]
    elif axis == "방문 가능성·예약 기준":
        variants = [
            f"{label_subject} 매장별 처리 가능 업무, 운영 여부, 예약 가능 여부, 준비물 필요 여부가 확인된 경우에만 방문 가능으로 안내한다.",
            f"{label_text} 예약 가능 여부가 불가하거나 방문 업무 처리가 제한되면 대체 매장, 온라인 처리, 상담 연결 중 가능한 경로를 안내한다.",
            f"{label_text} 고객이 가입·개통 매장을 조회할 때는 예약 가능 여부, 최신 운영 상태, 연락처, 위치 정보, 폐점·이전 여부를 함께 제공한다.",
        ]
    elif axis == "매장 안내 운영·통합 기준":
        variants = [
            f"{label_subject} 재고 수량, 고객 위치, 매장 속성, 처리 가능 업무를 기준으로 공통 팝업 전환 가능 여부를 검토한다.",
            f"{label_text} 통합 팝업 전환 전에는 기존 분기 기준, 고객 영향, 예외 매장, 롤백 조건을 운영 기준으로 남긴다.",
            f"{label_text} 운영 결과는 노출 조건, 적용 범위, 예외 사유, 고객 선택 이력, 변경 승인 이력으로 저장한다.",
        ]
    else:
        variants = [
            f"{label_subject} 고객 위치, 방문 목적, 매장 운영 상태, 처리 가능 업무, 대체 경로를 함께 판단한다.",
            f"{label_text} 조건이 충족되지 않으면 방문 제한 사유와 온라인·상담·대체 매장 경로를 구분해 안내한다.",
            f"{label_text} 판정 결과는 매장 안내 상태, 고객 선택, 예약·방문 준비, 정보 갱신 이력으로 저장한다.",
        ]
    return variants[index % len(variants)]


def notification_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write notification policy details as delivery/receipt/priority criteria."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or notification_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "알림 기준")
    label_subject = korean_subject(label_text)
    if axis == "푸시 권한·수신 허용":
        variants = [
            f"{label_subject} 권한 요청은 알림 필요성을 고객이 인지한 시점에만 노출하고, 거부 시 제한되는 수신 범위와 설정 이동 경로를 함께 안내한다.",
            f"{label_text} 권한이 꺼져 있으면 앱푸시 발송은 제한하고 필수 알림은 허용된 대체 채널 또는 알림함 노출 기준으로 전환한다.",
            f"{label_text} 재요청은 고객 행동 맥락, 거부 이력, 업무 중요도를 기준으로 제한하며 요청·거부·변경 이력을 저장한다.",
        ]
    elif axis == "수신 설정·채널 기준":
        variants = [
            f"{label_subject} 거래성·보안·마케팅·혜택 유형과 앱푸시·문자·이메일·카카오 채널을 분리해 수신 허용 여부를 관리한다.",
            f"{label_text} 변경 시 필수 알림은 거부 대상에서 제외하고 선택 알림은 변경 즉시 적용하며 적용 전후 값을 이력으로 저장한다.",
            f"{label_text} 수신 연락처는 대표 연락처와 개별 지정 연락처를 구분하고 대표값 변경 시 자동 갱신 여부를 고객에게 고지한다.",
        ]
    elif axis == "알림함·후속 연결":
        variants = [
            f"{label_subject} 알림 목록은 카테고리, 중요도, 행동 필요 여부, 유효 상태를 함께 표시해 고객이 후속 업무를 바로 선택할 수 있게 한다.",
            f"{label_text} 상세 진입 시 주문번호, 혜택 ID, 문의 ID처럼 후속 화면에 필요한 컨텍스트를 전달하고 실패 시 상담 전환 문맥을 유지한다.",
            f"{label_text} 동일 사건의 연속 알림은 타임라인으로 묶어 중복 노출을 줄이고 읽음·처리 완료·무효 상태를 동기화한다.",
        ]
    elif axis == "우선순위·중복 제어":
        variants = [
            f"{label_subject} 필수·행동 필요 알림을 우선 표시하고 선택·마케팅 알림은 고객 설정, 조용한 시간, 빈도 제한을 적용한다.",
            f"{label_text} 동일 사건 알림은 대상 업무, 발생 시점, 처리 상태가 같으면 병합하고 중복 발송을 제한한다.",
            f"{label_text} 다시알림은 고객이 지정한 시간과 알림 유형에만 허용하며 만료·처리 완료 알림은 자동으로 무효 처리한다.",
        ]
    elif axis == "발송 실패·복구":
        variants = [
            f"{label_subject} 발송 실패는 채널 오류, 권한 거부, 연락처 오류, 고객 설정 제한으로 구분하고 재시도 가능 여부를 판정한다.",
            f"{label_text} 필수 알림이 실패하면 대체 채널, 알림함 고정 노출, 상담 안내 중 하나로 복구 경로를 제공한다.",
            f"{label_text} 실패·재시도·대체 발송 결과는 발송 채널, 시점, 사유, 최종 도달 여부와 함께 이력으로 저장한다.",
        ]
    elif axis == "필수·거래성 알림":
        variants = [
            f"{label_subject} 결제, 납부, 보안, 주문, 혜택 만료, 상담 답변처럼 고객 행동이 필요한 알림은 수신 거부 예외 또는 알림함 필수 노출 대상으로 관리한다.",
            f"{label_text} 발송 시점은 업무 상태 전환, 만료 D-day, 처리 실패, 고객 후속 행동 필요 여부를 기준으로 결정한다.",
            f"{label_text} 고객에게는 대상 서비스, 발생 사유, 처리 기한, 바로가기 경로, 미처리 영향 중 필요한 항목을 함께 고지한다.",
        ]
    elif axis == "알림 운영 기준":
        variants = [
            f"{label_subject} 템플릿, 발송 조건, 우선순위, 적용 기간, 승인 상태가 등록된 경우에만 운영 기준으로 배포한다.",
            f"{label_text} 변경 시 변경 전후 기준, 승인자, 배포 일시, 롤백 가능 여부를 운영 이력으로 저장한다.",
            f"{label_text} 품질은 발송 성공률, 중복률, 클릭 후 완료율, 수신 거부 증가율, 고객 불편 접수 건수로 점검한다.",
        ]
    else:
        variants = [
            f"{label_subject} 알림 대상, 발송 채널, 고객 설정, 업무 중요도, 후속 행동 필요 여부를 기준으로 처리한다.",
            f"{label_text} 필수 조건이 충족되지 않으면 발송을 제한하고 알림함 노출, 재시도, 상담 전환 중 필요한 후속 경로를 제공한다.",
            f"{label_text} 판정 결과는 알림 상태, 발송 실패 사유, 고객 확인 여부, 후속 업무 연결 이력으로 저장한다.",
        ]
    return variants[index % len(variants)]


def member_info_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write member information policy details as concrete lookup/change criteria."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or member_info_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "회원정보 기준")
    label_subject = korean_subject(label_text)
    axes = axes_text or "조회 범위, 변경 가능 여부, 인증, 이력"
    if axis == "조회 범위·정합화":
        variants = [
            f"{label_subject} 대표값, 보조값, 미검증값, 기준 시점, 출처 우선순위를 함께 구분해 노출한다.",
            f"{label_text} 조회 시 인증 상태와 고객 유형에 따라 마스킹 수준을 적용하고 불일치 정보는 정정 경로로 연결한다.",
            f"{label_text}의 채널 간 값이 다르면 최신 출처와 기준일을 표시하고 정합화 필요 여부를 처리 이력에 남긴다.",
        ]
    elif axis == "회원정보 변경":
        variants = [
            f"{label_subject} 변경 가능 항목, 적용 대상, 변경 전후 영향 범위, 저장 결과를 고객 최종 확인 전에 안내한다.",
            f"{label_text} 변경 요청은 본인확인 또는 재인증이 완료된 경우에만 접수하고 변경 전후 값과 적용 대상을 이력으로 저장한다.",
            f"{label_text} 중 일부 계약·상품에만 적용 가능한 값은 적용 범위를 고객이 선택하게 하고 기본값 변경 여부를 별도 확인한다.",
        ]
    elif axis == "권한·관계 정보 관리":
        variants = [
            f"{label_subject} 대표자, 법정대리인, 위임대리인, 그룹 구성원의 역할별 조회·변경 가능 범위를 분리한다.",
            f"{label_text} 처리는 권한 증빙과 현재 관계 상태가 유효한 경우에만 허용하고 권한 변경 이력을 저장한다.",
            f"{label_text}의 권한이 만료되거나 철회되면 관련 회원정보 조회와 변경 업무를 제한하고 대체 경로를 안내한다.",
        ]
    elif axis == "검증·재인증":
        variants = [
            f"{label_subject} 민감정보 노출, 연락처·이메일·계좌 변경, 세션 영향 업무에는 재인증 필요 여부를 먼저 판정한다.",
            f"{label_text} 인증 실패 시 재시도 가능 횟수와 유효시간을 안내하고 반복 실패는 상담 전환 대상으로 분류한다.",
            f"{label_text} 검증 결과는 검증 수단, 성공·실패 사유, 유효 시점, 재검증 필요 시점을 함께 저장한다.",
        ]
    elif axis == "변경 이력·복구":
        variants = [
            f"{label_subject} 변경 항목, 이전 값, 변경 후 값, 요청 채널, 처리 일시, 처리 결과를 고객 확인과 감사 이력으로 저장한다.",
            f"{label_text} 처리 중단 시 입력값과 진행 단계를 임시 저장하고 재진입 시 복원 가능 여부를 안내한다.",
            f"{label_text} 셀프 복구가 불가하면 현재 문맥과 실패 사유를 유지한 채 상담 전환 기준으로 연결한다.",
        ]
    elif axis == "증빙·외부 제출":
        variants = [
            f"{label_subject} 전자문서, 공공 마이데이터, 업로드 증빙 중 사용할 제출 방식을 선택하게 하고 제출 결과를 접수 이력에 남긴다.",
            f"{label_text}은 자동 수집 가능 항목과 고객 직접 제출 항목을 구분하고 제출 실패 시 대체 제출 경로를 안내한다.",
            f"{label_text} 증빙 정보는 업무 목적에 필요한 범위만 사용하고 보관 기간, 마스킹, 삭제 기준을 함께 적용한다.",
        ]
    else:
        variants = [
            f"{label_subject} {axes} 항목을 기준으로 조회 가능 여부, 변경 허용 여부, 고객 안내 기준을 판단한다.",
            f"{label_text} 중 필수 조건이 충족되지 않으면 제한 사유, 보완 방법, 상담 전환 가능 여부를 고객에게 안내한다.",
            f"{label_text} 판정 결과는 요청 상태, 변경 이력, 실패 사유, 후속 행동 기준으로 저장한다.",
        ]
    return variants[index % len(variants)]


def terms_consent_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write terms/consent policy details without repeating a small template set."""

    title = clean_schema_text(item.get("short_title") or item.get("title") or label)
    text = requirement_full_text(item)
    label_text = clean_schema_text(label or title or "약관·동의 기준")
    label_subject = korean_subject(label_text)
    axes = axes_text or "동의 유형, 약관 버전, 동의 이력"
    if contains_any(text, ("상태 조회", "동의 상태", "현재 상태", "조회")):
        return (
            f"{label_subject} 필수·선택 동의의 현재 상태, 적용 서비스, 약관 버전, 마지막 변경 일시를 함께 제공한다. "
            "고객이 미동의 항목을 확인하면 제한되는 업무와 재동의 가능 경로를 같은 화면 흐름에서 안내한다."
        )
    if contains_any(text, ("개인정보", "제3자", "위탁", "수탁", "보관", "파기")):
        return (
            f"{label_subject} 수집·제공 목적, 제공 항목, 보관 기간, 제3자 제공 또는 처리 위탁 대상을 요약과 상세로 구분해 고지한다. "
            "고객 확인이 필요한 항목은 확인 일시와 고지 버전을 저장해 사후 증적 기준으로 사용한다."
        )
    if contains_any(text, ("쿠키", "추적", "맞춤", "광고", "개인화")):
        return (
            f"{label_subject} 쿠키·추적 기반 이용 목적, 보관 기간, 거부 방법, 거부 시 제한되는 개인화 기능을 명확히 구분한다. "
            "거부 후에도 필수 서비스가 유지되도록 기본 경험과 선택 기능 제한 기준을 분리한다."
        )
    if contains_any(text, ("미동의", "비활성", "기본 경험")):
        return (
            f"{label_subject} 선택 동의 미완료 고객에게도 기본 조회와 필수 업무를 허용하고, 동의가 필요한 부가 기능만 비활성 처리한다. "
            "비활성 사유와 동의 후 즉시 사용 가능 여부를 고객 안내 기준으로 남긴다."
        )
    if contains_any(text, ("변경", "개정", "시행", "재고지", "버전")):
        return (
            f"{label_subject} 약관 변경 요약, 시행일, 영향 범위, 재동의 필요 여부를 변경 전 고지한다. "
            "필수 약관 변경으로 서비스 이용 조건이 달라지면 고객 확인 전까지 제한되는 업무와 유지되는 업무를 구분한다."
        )
    if contains_any(text, ("결제", "주문", "청약", "신청")):
        return (
            f"{label_subject} 주문·결제·신청 진행 전에 필수 약관 동의 완료 여부와 최신 약관 버전을 확인한다. "
            "필수 동의가 없으면 다음 단계 진행을 제한하고, 동의 완료 후 동일 요청을 이어갈 수 있게 처리 상태를 보존한다."
        )
    if contains_any(text, ("오픈소스", "라이선스")):
        return (
            f"{label_subject} 오픈소스·라이선스 고지 대상, 고지 위치, 버전 변경 시 재고지 필요 여부를 관리한다. "
            "고지 누락이 확인되면 배포 전 보완 대상으로 분류하고 변경 이력을 운영 증적으로 저장한다."
        )
    if contains_any(text, ("이력", "로그", "증적", "저장")):
        return (
            f"{label_subject} 동의·철회·고지 확인 이력을 고객, 약관 버전, 처리 채널, 처리 시각 단위로 저장한다. "
            "분쟁 또는 감사 요청 시 조회 가능한 최소 증적 항목과 보관 기간을 정책 기준으로 둔다."
        )
    if contains_any(text, ("철회", "재동의", "거부권", "거부")):
        return (
            f"{label_subject} 목적별 선택 동의의 철회와 재동의를 허용하되, 필수 동의 철회가 업무 중단으로 이어지는 경우 제한 사유를 먼저 고지한다. "
            "철회·재동의 결과는 처리 채널, 적용 시점, 이전 동의값과 함께 이력으로 저장한다."
        )
    variants = [
        f"{label_subject} {axes} 항목을 기준으로 필수 동의와 선택 동의를 구분하고, 동의가 없을 때 제한되는 업무만 고객에게 고지한다.",
        f"{label_text} 처리 결과는 동의 유형, 약관 버전, 적용 시점, 고객 확인 여부를 기준으로 저장하고 후속 업무 판단에 사용한다.",
        f"{label_text}에서 필수 고지 또는 확인 이력이 누락되면 다음 단계 진행을 제한하고 상세 고지 확인 또는 재동의 경로를 제공한다.",
    ]
    return variants[index % len(variants)]


def settings_policy_content(item: Mapping[str, object], label: object, axes_text: str, index: int) -> str:
    """Write setting policy details as control criteria, not copied requirement titles."""

    text = requirement_full_text(item)
    axis = str(item.get("semantic_axis") or settings_requirement_semantic_axis(text))
    label_text = clean_schema_text(label or item.get("short_title") or item.get("title") or "설정 기준")
    label_subject = korean_subject(label_text)
    axes = axes_text or "설정 대상, 적용 범위, 변경 이력"
    if axis == "동의·권한 설정":
        return (
            f"{label_subject} 개인화·AI·민감 기능의 사용 여부를 필수·선택 동의, 권한 범위, 철회 가능 여부로 구분한다. "
            "고객이 동의를 변경하면 적용 범위와 제한되는 기능을 즉시 안내하고 변경 이력을 저장한다."
        )
    if axis == "기록·초기화 설정":
        return (
            f"{label_subject} 초기화 대상, 삭제 범위, 복구 가능 여부, 재학습 시작 시점을 처리 전에 고지한다. "
            "초기화가 완료되면 이전 개인화 결과 사용을 중단하고 처리 일시와 요청 주체를 이력으로 저장한다."
        )
    if axis == "보안 설정":
        return (
            f"{label_subject} 세션 유지 시간, 자동 로그아웃 조건, 재인증 필요 업무, 민감정보 보호 수준을 설정 기준으로 관리한다. "
            "고객이 보안 설정을 변경하면 즉시 적용 여부와 예외 업무를 안내하고 변경 이력을 저장한다."
        )
    if axis == "알림 설정":
        return (
            f"{label_subject} 알림 유형, 수신 채널, 표시 방식, 필수 알림 예외를 고객이 구분해 선택할 수 있게 한다. "
            "필수 고지성 알림은 수신 거부 대상에서 제외하고, 선택 알림은 변경 즉시 수신 기준에 반영한다."
        )
    if axis == "개인화·접근성 설정":
        return (
            f"{label_subject} 언어, 쉬운모드, 홈 우선 영역, 추천 노출 같은 개인화 항목을 고객이 직접 조정할 수 있게 한다. "
            "변경값은 고객 단위로 저장하고 기본값 복원 또는 기기 변경 시 적용 기준을 함께 안내한다."
        )
    if axis == "설정 변경":
        return (
            f"{label_subject} {axes} 항목을 확인한 뒤 변경 가능 여부와 즉시 적용 여부를 판정한다. "
            "변경 실패 시 이전 설정값을 유지하고 실패 사유, 재시도 가능 여부, 상담 전환 기준을 안내한다."
        )
    return (
        f"{label_subject} {axes} 항목을 기준으로 설정 가능 여부, 적용 범위, 고객 안내 기준을 판단한다. "
        "설정 결과와 변경 전후 값은 고객 확인과 운영 추적이 가능하도록 이력으로 저장한다."
    )


def requirement_policy_item_name(item: Mapping[str, object]) -> str:
    # 요구사항 상세명은 근거로 활용하되 정책 항목명에 그대로 복사하지 않는다.
    # 항목명은 개발/QA가 판단 기준으로 읽을 수 있도록 semantic label을 우선한다.
    semantic_label = clean_schema_text(item.get("semantic_label") or "")
    if semantic_label:
        return compact_text(semantic_label, 60)
    source_title = clean_schema_text(item.get("short_title") or item.get("title") or "")
    source_title = re.sub(r"^(상세\s*)?요구사항\s*", "", source_title).strip(" -:·")
    source_title = re.sub(r"\([^)]*\)", "", source_title).strip(" -:·")
    if source_title:
        return compact_text(requirement_semantic_label(requirement_full_text(item), str(item.get("actor") or "")), 60)
    return compact_text(item.get("semantic_label") or requirement_semantic_label(requirement_full_text(item), str(item.get("actor") or "")), 60)


def requirement_policy_axes(item: Mapping[str, object]) -> List[str]:
    text = requirement_full_text(item)
    axes: List[str] = []
    if contains_any(text, ("약관", "동의", "철회", "재동의", "거부권", "쿠키", "개인정보 제공", "제3자 제공", "처리 위탁")):
        axes.extend(["동의 유형", "필수·선택 구분", "철회 가능 여부", "약관 버전", "동의 이력"])
    if contains_any(text, ("탈퇴", "해지", "취소", "철회", "삭제", "파기", "복구")):
        axes.extend(["처리 가능 상태", "철회 가능 여부", "보관·삭제 기준", "처리 이력"])
    if contains_any(text, ("가입", "신청", "등록", "개통", "접수")):
        axes.extend(["처리 대상", "제한 조건", "필수 동의", "처리 결과"])
    if contains_any(text, ("인증", "본인확인", "세션", "로그인", "동의", "권한")):
        axes.extend(["인증 필요 여부", "세션·동의 유효성", "재인증 기준", "인증 이력"])
    if contains_any(text, ("상태", "제한", "가능", "조건", "보류", "중단")):
        axes.extend(["상태 조건", "제한 사유", "후속 행동", "재검증 기준"])
    if contains_any(text, ("BSS", "연계", "동기화", "정합성", "원장", "반영", "회신")):
        axes.extend(["연계 판정 결과", "BSS 반영 기준", "불일치 처리", "회신 이력"])
    if contains_any(text, ("알림", "고지", "안내", "통지", "메시지", "결과")):
        axes.extend(["고지 대상", "고지 시점", "필수 안내 항목", "발송 이력"])
    if contains_any(text, ("입력", "필수", "형식", "수집")):
        axes.extend(["필수 입력", "허용 형식", "오류 안내", "임시 저장"])
    if contains_any(text, ("검색", "조회", "필터", "정렬", "상세", "목록", "노출")):
        axes.extend(["노출 대상", "정렬 기준", "개인화 조건", "제한 노출"])
    if not axes:
        axes.extend(["권한", "상태", "기준일", "후속 행동"])
    return unique_policy_names(axes)[:5]


def requirement_condition_function_name(function_label: str) -> str:
    if function_label.endswith(("조건", "검증", "판정", "처리")):
        return f"{function_label} 확인"
    return f"{function_label} 조건 확인"


def korean_subject(value: object) -> str:
    text = clean_schema_text(value)
    if not text:
        return ""
    for char in reversed(text):
        if "가" <= char <= "힣":
            has_final_consonant = (ord(char) - ord("가")) % 28 != 0
            return f"{text}{'은' if has_final_consonant else '는'}"
    return f"{text}은"


def korean_object(value: object) -> str:
    text = clean_schema_text(value)
    if not text:
        return ""
    for char in reversed(text):
        if "가" <= char <= "힣":
            has_final_consonant = (ord(char) - ord("가")) % 28 != 0
            return f"{text}{'을' if has_final_consonant else '를'}"
    return f"{text}을"


def with_requirement_decision_prefix(sentence: str, index: int) -> str:
    # 정책 항목명과 본문이 이미 판단축을 담고 있으므로, 본문 앞에
    # "상담 전환 기준:" 같은 작성용 접두어를 다시 붙이지 않는다.
    del index
    return sentence


def rewrite_requirement_sentence(description: str) -> str:
    text = clean_schema_text(description)
    if not text:
        return ""
    text = re.sub(r"^서비스는\s*", "", text)
    text = re.sub(r"\s*해야 한다\.?$", "", text)
    text = re.sub(r"\s*할 수 있도록\s*", "하도록 ", text)
    return text


def policies_for_requirement(item: dict) -> List[str]:
    text = f"{item.get('title', '')} {item.get('description', '')}"
    primary = item.get("policy_group") or policy_group_for_requirement(text)
    secondary = "고객 상태 조회 정책"
    if contains_any(text, ("약관", "동의", "철회", "재동의", "개인정보 제공", "제3자 제공", "쿠키", "위탁")):
        secondary = "알림·고지 정책"
    elif contains_any(text, ("만료", "종료", "예정", "알림", "안내", "유의")):
        secondary = "알림·고지 정책"
    elif contains_any(text, ("권한", "명의", "실사용자", "대표", "인증")):
        secondary = "접근·권한 정책"
    elif contains_any(text, ("불일치", "동기화", "보정", "정합성", "연계")):
        secondary = "BSS 연계 판정 정책"
    elif contains_any(text, ("긴급", "분실", "도난", "정지", "미납", "재발급", "장애")):
        secondary = "예외·상담 전환 정책"
    return unique_policy_names([primary, secondary])


def policy_group_for_requirement(text: str) -> str:
    if is_operator_requirement(text):
        return "운영 기준 정보 관리 정책"
    if contains_any(text, ("긴급", "분실", "도난", "로밍", "미납", "재발급", "장애")):
        return "예외·상담 전환 정책"
    if contains_any(text, ("약관", "동의", "철회", "재동의", "거부권", "쿠키", "개인정보 제공", "제3자 제공", "처리 위탁")):
        return "인증·동의 정책"
    if contains_any(text, ("권한", "명의", "실사용자", "대표", "인증")):
        return "접근·권한 정책"
    if contains_any(text, ("만료", "종료", "예정", "알림", "고지", "유의")):
        return "알림·고지 정책"
    if contains_any(text, ("상태", "신청 중", "변경 중", "개통", "정지", "해지", "보류")):
        return "상태 전환 정책"
    if contains_any(text, ("불일치", "정합성", "동기화", "연계", "BSS")):
        return "BSS 연계 판정 정책"
    if contains_any(text, ("검색", "필터", "정렬", "우선", "노출", "홈", "상세", "목록", "카드")):
        return "대상 정보 노출 정책"
    return "가능 여부 검증 정책"


def compact_requirement_title(title: str) -> str:
    text = clean_schema_text(title)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\(.*?\)", "", text).strip()
    return compact_text(text, 46)


def function_label_for_requirement(title: str) -> str:
    text = clean_schema_text(title)
    text = text.replace(",", "·")
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+", " ", text)
    return compact_text(text, 42)


def is_operator_requirement(text: str) -> bool:
    return "운영자" in text or ("운영" in text and contains_any(text, ("관리", "모니터링", "보정", "승인", "매핑")))


def unique_policy_names(values: Sequence[str]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        cleaned = clean_schema_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def contains_any(text: object, keywords: Sequence[str]) -> bool:
    haystack = str(text or "")
    return any(keyword in haystack for keyword in keywords)


def clean_schema_text(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    replacements = {
        "조건 조건": "조건",
        "검증 검증": "검증",
        "조회 조회": "조회",
        "정보 정보": "정보",
        "기준 기준": "기준",
        "판정 판정": "판정",
        "구성 구성": "구성",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def compact_text(value: object, max_chars: int) -> str:
    text = clean_schema_text(value)
    if len(text) <= max_chars:
        return text
    # 문서 본문/표 셀에 말줄임표가 남으면 정책 기준이 덜 작성된 것처럼 보인다.
    # 렌더링 폭은 CSS가 처리하므로 텍스트 값 자체에는 생략 기호를 넣지 않는다.
    return text[:max_chars].rstrip(" ,.;·/")


def build_generic_policy_spec(ctx) -> dict:
    code = ctx.business_code
    topic = display_policy_topic(ctx.topic)
    density_profile = build_density_profile(ctx)
    requirement_items = requirement_focus_items(ctx, max_items=density_profile.requirement_policy_limit)
    density_profile = build_density_profile(ctx, requirement_items=requirement_items)
    structural_requirement_limit = density_profile.structural_requirement_limit
    usecase_themes = customer_usecase_themes(topic, requirement_items)
    policy_groups = generic_policy_groups(code)
    processes = generic_processes(
        code,
        topic,
        policy_groups,
        requirement_items,
        structural_requirement_limit,
        usecase_themes,
    )
    functions = generic_functions(code, requirement_items, structural_requirement_limit)
    attach_function_refs_to_processes(processes, functions)
    policy_details = build_policy_details(
        code,
        policy_groups,
        requirement_items,
        max_requirement_items=density_profile.requirement_policy_limit,
    )
    sync_policy_group_items_from_details(policy_groups, policy_details)
    return {
        "meta": build_base_meta(ctx, density_profile),
        "density_profile": density_profile.to_dict(),
        "history": build_history(ctx, f"{topic} 정책서 초안 작성. JSON 정책 스펙을 생성하고 검증 후 HTML로 렌더링한다."),
        "overview": {
            "scope": [
                f"본 정책서는 통합채널에서 제공하는 {topic} 업무의 처리 기준을 정의한다.",
                requirement_scope_line(requirement_items, topic),
                "대상 채널은 앱·웹 FO이며 고객이 직접 조회, 조건 확인, 처리 요청, 결과 확인을 수행하는 셀프 처리 흐름을 포함한다.",
                "BSS와 연계 시스템이 수행하는 가능 여부 검증, 상태 판정, 처리 결과 회신은 정책 판단 기준에 포함한다.",
                "화면 UI 상세, API 필드, DB 컬럼, 운영자 화면 상세는 제외하되 정책 판단에 필요한 기준은 포함한다.",
                "상세 화면 설계, API 필드, DB 컬럼, 테스트 케이스는 후속 화면 설계서와 기능 상세 명세서에서 상세화한다.",
            ],
            "principles": [
                principle("고객 과업 중심", f"{topic}은 내부 시스템 단위가 아니라 고객이 완료하려는 목적을 기준으로 구성한다."),
                principle("셀프 처리 우선", "고객이 앱·웹에서 직접 완료할 수 있는 업무는 상담 전환보다 셀프 처리 경로를 우선 제공한다."),
                principle("BSS 판단 통합", "고객 상태, 가입 정보, 요금, 혜택, 제한 조건처럼 BSS 판단이 필요한 정보는 프로세스와 정책에 포함한다."),
                principle("영향도 사전 고지", "비용, 혜택, 약정, 포인트, 쿠폰, 회선, 주문 상태에 영향이 있으면 처리 전에 안내한다."),
                principle("권한·보안 우선", "민감정보 노출 또는 변경 처리는 본인확인, 동의, 권한 기준을 충족한 경우에만 허용한다."),
                principle("근거 기반 운영", "요구사항과 참고자료에서 확인한 기준은 프로세스, 기능, 정책 중 하나 이상으로 추적 가능하게 관리한다."),
            ],
        },
        "terms": generic_terms(code, topic, requirement_items),
        "actors": generic_actors(code, topic),
        "usecases": generic_usecases(code, topic, requirement_items, usecase_themes),
        "states": generic_states(code),
        "state_transitions": generic_state_transitions(),
        "processes": processes,
        "process_details": [],
        "functions": functions,
        "function_details": [],
        "policy_groups": policy_groups,
        "policy_details": policy_details,
        "final_check": generic_final_check(topic),
    }


def generic_terms(code: str, topic: str, requirement_items: Sequence[dict] = ()) -> List[dict]:
    topic_object = korean_object(topic)
    terms = [
        (topic, f"통합채널에서 고객이 {topic_object} 조회, 확인, 선택, 신청, 변경 또는 관리하기 위해 수행하는 업무 단위"),
        ("대상 고객", f"{topic} 업무를 이용하는 고객. 로그인 여부와 고객 상태는 액터가 아니라 권한 조건과 상태 기준으로 관리한다."),
        ("처리 가능 상태", f"고객 상태와 업무 조건이 {topic} 진행 기준을 충족한 상태"),
        ("처리 제한 상태", f"정책 조건, 권한, 인증, 시스템 응답, 고객 상태 때문에 {topic_object} 완료할 수 없는 상태"),
        ("BSS 검증 결과", "BSS가 고객 상태, 가입 상품, 청구, 혜택, 약정, 제한 조건, 처리 가능 여부를 판정해 채널에 회신한 결과"),
        ("연계 결과", "외부 또는 내부 연계 시스템이 요청 처리 가능 여부, 처리 성공, 처리 실패, 보류 사유를 회신한 결과"),
        ("영향도 고지", "고객이 처리 전에 알아야 하는 비용, 혜택, 약정, 쿠폰, 포인트, 회선, 주문 상태, 이용 제한 영향을 안내하는 기준"),
        ("처리 이력", "고객 요청, 시스템 검증, 처리 결과, 실패 사유, 상담 전환, 운영 변경을 추적하기 위해 저장하는 기록"),
        ("운영 확인 필요", "자동 판단만으로 처리할 수 없어 운영자 확인, 상담 전환, 기준 보정이 필요한 상태"),
    ]
    for item in requirement_items[:6]:
        term_name = requirement_term_name(item)
        if not term_name or any(term_name == name for name, _ in terms):
            continue
        terms.append((term_name, requirement_term_description(item)))
    return [{"id": f"TM-{code}-{index:03d}", "name": name, "description": description} for index, (name, description) in enumerate(terms, 1)]


def generic_actors(code: str, topic: str) -> List[dict]:
    actors = [
        ("고객", f"{topic} 정보를 확인하고 조건을 판단한 뒤 필요한 후속 업무를 직접 수행하는 주체"),
        ("운영자", f"{topic} 기준 정보, 노출 조건, 제한 기준, 품질 지표를 관리하는 내부 담당자"),
        ("BSS", "고객 상태, 가입 상품, 요금, 혜택, 약정, 회선, 제한 조건, 처리 결과를 판정하고 채널에 회신하는 시스템"),
        ("인증기관", "본인확인, 추가 인증, 인증 성공·실패 결과를 제공하는 외부 또는 내부 인증 시스템"),
        ("연계 시스템", f"{topic} 업무 처리에 필요한 기준 정보와 연계 결과를 제공하는 시스템"),
        ("채널 업무 시스템", "고객 입력, 세션, 상태 전환, 처리 요청, 결과 안내, 이력 저장을 담당하는 채널 시스템"),
    ]
    return [{"id": f"ACT-{code}-{index:03d}", "name": name, "description": description} for index, (name, description) in enumerate(actors, 1)]


def generic_usecases(
    code: str,
    topic: str,
    requirement_items: Sequence[dict] = (),
    usecase_themes: Mapping[str, Mapping[str, object]] | None = None,
) -> List[dict]:
    themes = usecase_themes or customer_usecase_themes(topic, requirement_items)
    default_cs1, default_cs2, default_cs3 = default_customer_usecase_labels(topic)
    cs1 = theme_value(themes, "CS-001", default_cs1)
    cs2 = theme_value(themes, "CS-002", default_cs2)
    cs3 = theme_value(themes, "CS-003", default_cs3)
    cs1_focus = theme_focus(themes, "CS-001", f"{topic} 대상과 본인에게 적용되는 기준")
    cs2_focus = theme_focus(themes, "CS-002", f"{topic} 처리 조건과 고객 요청")
    cs3_focus = theme_focus(themes, "CS-003", f"{topic} 처리 이후 변경, 취소, 재시도, 상담 연결")
    rows = [
        ("CS-001", "고객", cs1, f"고객이 {korean_object(cs1_focus)} 확인하고 다음 행동을 결정하는 유즈케이스", "Y"),
        ("CS-002", "고객", cs2, f"고객이 {korean_object(cs2_focus)} 적용해 필요한 요청 또는 선택을 완료하는 유즈케이스", "Y"),
        ("CS-003", "고객", cs3, f"고객이 {cs3_focus} 등 결과 이후 후속 업무를 수행하는 유즈케이스", "Y"),
        ("OPR-001", "운영자", f"{topic} 운영 기준 및 품질 관리", f"운영자가 기준 정보, 제한 기준, 예외 기준, 품질 지표를 관리하는 유즈케이스", "Y"),
        ("BSS-001", "BSS", f"{topic} 고객·업무 조건 판정", f"BSS가 {topic}에 필요한 고객 상태, 자격, 제한 조건, 처리 결과를 판정하는 유즈케이스", "N"),
        ("AUT-001", "인증기관", f"{topic} 인증 결과 제공", f"인증기관이 {topic}에 필요한 본인확인 또는 추가 인증 결과를 제공하는 유즈케이스", "N"),
        ("EXT-001", "연계 시스템", f"{topic} 연계 결과 제공", f"연계 시스템이 {topic} 업무 처리에 필요한 기준 정보와 처리 결과를 제공하는 유즈케이스", "N"),
        ("SYS-001", "채널 업무 시스템", f"{topic} 상태·이력 처리", f"채널 업무 시스템이 {topic} 세션, 상태, 요청, 결과, 이력을 처리하는 유즈케이스", "N"),
    ]
    return [{"id": f"US-{code}-{suffix}", "actor": actor, "name": name, "description": desc, "process_target": target} for suffix, actor, name, desc, target in rows]


def default_customer_usecase_labels(topic: str) -> tuple[str, str, str]:
    topic_label = display_policy_topic(topic) or str(topic or "").strip()
    if "회원정보" in topic_label:
        return (
            "회원정보 통합 조회·이해",
            "회원정보 변경·검증 처리",
            "회원정보 정정·복구 관리",
        )
    if "약관" in topic_label:
        return (
            f"{topic_label} 권리 관리",
            "필수·선택 동의 관리",
            "동의 변경·철회 관리",
        )
    if "설정" in topic_label:
        return (
            f"{topic_label} 상태·권한 관리",
            "개인화·알림 관리",
            "초기화·삭제 관리",
        )
    if is_customer_center_store_topic(topic_label):
        return (
            "매장 탐색·방문 가능성 확인",
            "방문 준비·예약 실행",
            "매장 이용 예외·대체 경로 확인",
        )
    if is_customer_center_faq_notice_topic(topic_label):
        return (
            "FAQ·이용안내 탐색·확인",
            "해결 가이드 실행·후속 연결",
            "공지·변경 안내 확인",
        )
    if is_customer_center_hub_topic(topic_label):
        return (
            "고객센터 셀프 해결 허브 이용",
            "상담·문의 접수 실행",
            "상담 전환·후속 관리",
        )
    if "알림" in topic_label:
        return (
            f"{topic_label} 확인",
            f"{topic_label} 수신 설정 실행",
            f"{topic_label} 후속 처리·복구 관리",
        )
    return (
        f"{topic_label} 정보 확인",
        f"{topic_label} 조건 적용 및 업무 실행",
        f"{topic_label} 예외·후속 처리",
    )


def generic_states(code: str) -> List[dict]:
    rows = [
        ("001", "진입 전", "고객이 업무를 시작하기 전 상태", "업무 진입 경로와 기본 안내를 제공한다."),
        ("002", "정보 조회 중", "대상 정보와 기준 정보를 조회하는 상태", "공개 정보와 개인화 정보의 조회 가능 여부를 확인한다."),
        ("003", "조건 확인 중", "고객 상태, 권한, 업무 조건, 연계 결과를 확인하는 상태", "처리 가능 여부와 인증·동의 필요 여부를 판단한다."),
        ("004", "인증·동의 필요", "본인확인, 약관 동의, 고객 확인이 필요한 상태", "인증·동의 경로로 전환하고 결과를 저장한다."),
        ("005", "처리 요청 가능", "필수 조건을 충족해 처리 요청을 접수할 수 있는 상태", "영향도 고지와 최종 확인 후 처리 요청을 접수한다."),
        ("006", "처리 진행 중", "처리 요청이 접수되어 BSS 또는 연계 시스템 처리가 진행 중인 상태", "중복 요청을 제한하고 처리 결과를 대기한다."),
        ("007", "처리 완료", "요청한 업무가 성공 처리되고 결과가 반영된 상태", "완료 결과를 안내하고 처리 이력을 저장한다."),
        ("008", "처리 제한", "권한, 고객 상태, 정책 조건, 연계 결과 때문에 처리를 진행할 수 없는 상태", "제한 사유와 대체 경로를 안내한다."),
        ("009", "처리 실패", "연계 오류, 입력 오류, 인증 실패, 처리 실패가 발생한 상태", "재시도 가능 여부와 상담 전환 기준을 안내한다."),
        ("010", "처리 보류", "처리 결과를 즉시 확정할 수 없어 추가 확인이 필요한 상태", "운영 확인 또는 연계 결과 재확인 대상으로 등록한다."),
        ("011", "상담 전환", "자동 처리보다 상담 연결이 적절하다고 판정된 상태", "상담 이관 정보와 전환 사유를 저장한다."),
        ("012", "운영 확인 필요", "기준 정보 불일치, 반복 실패, 고객 이력 충돌로 운영자 확인이 필요한 상태", "운영 확인 큐에 등록하고 고객에게 후속 조치를 안내한다."),
    ]
    return [{"id": f"ST-{code}-{suffix}", "name": name, "description": desc, "next_action": action} for suffix, name, desc, action in rows]


def generic_state_transitions() -> List[dict]:
    return [
        transition("진입 전", "고객이 업무에 진입", "정보 조회 중", "대상 정보와 기본 기준 정보를 조회한다."),
        transition("정보 조회 중", "대상 정보 확인 완료", "조건 확인 중", "고객 상태, 권한, 처리 조건을 확인한다."),
        transition("조건 확인 중", "인증 또는 동의 필요", "인증·동의 필요", "본인확인, 약관 동의, 고객 확인 경로로 전환한다."),
        transition("조건 확인 중", "조건 충족", "처리 요청 가능", "영향도 고지와 최종 확인 후 처리 요청을 허용한다."),
        transition("인증·동의 필요", "인증·동의 완료", "처리 요청 가능", "인증·동의 이력을 저장하고 요청 가능 상태로 전환한다."),
        transition("인증·동의 필요", "인증 실패 또는 동의 거부", "처리 제한", "처리를 제한하고 실패 사유와 재시도 가능 기준을 안내한다."),
        transition("처리 요청 가능", "고객이 최종 요청", "처리 진행 중", "BSS 또는 연계 시스템에 처리 요청을 전달한다."),
        transition("처리 진행 중", "처리 성공", "처리 완료", "결과 반영과 고객 안내, 이력 저장을 완료한다."),
        transition("처리 진행 중", "일시 오류 또는 응답 지연", "처리 보류", "처리 결과 재확인 또는 운영 확인 대상으로 등록한다."),
        transition("처리 진행 중", "처리 실패", "처리 실패", "실패 사유와 재시도 또는 상담 전환 기준을 안내한다."),
        transition("조건 확인 중", "정책 제한 또는 권한 부족", "처리 제한", "제한 사유와 대체 경로를 안내한다."),
        transition("처리 제한", "자동 처리 불가", "상담 전환", "상담 이관 정보와 제한 사유를 생성한다."),
        transition("처리 보류", "운영자 확인 필요", "운영 확인 필요", "운영 확인 큐에 등록하고 처리 지연 사유를 안내한다."),
        transition("운영 확인 필요", "운영 보정 또는 수동 처리 완료", "처리 완료", "처리 결과와 보정 이력을 저장한다."),
    ]


def generic_processes(
    code: str,
    topic: str,
    policy_groups: Sequence[dict],
    requirement_items: Sequence[dict] = (),
    structural_requirement_limit: int = REQUIREMENT_STRUCTURE_ITEM_LIMIT,
    usecase_themes: Mapping[str, Mapping[str, object]] | None = None,
) -> List[dict]:
    policy_ref_by_name = {group["name"]: f'{group["id"]} {group["name"]}' for group in policy_groups}
    themes = usecase_themes or customer_usecase_themes(topic, requirement_items)
    cs1 = theme_value(themes, "CS-001", f"{topic} 정보 확인")
    cs2 = theme_value(themes, "CS-002", f"{topic} 조건 적용")
    cs3 = theme_value(themes, "CS-003", f"{topic} 후속 처리")
    cs1_focus = theme_focus(themes, "CS-001", f"{topic} 대상 정보")
    cs2_focus = theme_focus(themes, "CS-002", f"{topic} 처리 조건")
    cs3_focus = theme_focus(themes, "CS-003", f"{topic} 결과 이후 후속 업무")
    cs1_base = theme_process_base(themes, "CS-001", topic)
    cs2_base = theme_process_base(themes, "CS-002", topic)
    cs3_base = theme_process_base(themes, "CS-003", topic)
    rows = [
        ("CS-001", "01", compact_text(f"{cs1_base} 진입 기준 확인", 60), f"고객이 {cs1} 업무에 진입하면 채널은 {cs1_focus}의 목적과 기본 안내를 제공한다.", ["접근·권한 정책", "대상 정보 노출 정책"], ["업무 진입 경로 제공", "고객 목적 분류"]),
        ("CS-001", "02", compact_text(f"{cs1_base} 대상 정보 조회", 60), f"채널은 {cs1_focus}에 필요한 기준 정보와 고객별 적용 가능 정보를 조회한다.", ["대상 정보 노출 정책", "고객 상태 조회 정책"], ["대상 정보 조회", "기준 정보 구성"]),
        ("CS-001", "03", compact_text(f"{cs1_base} 조건·권한 확인", 60), f"{cs1_focus}에 적용되는 고객 상태, 권한, 제한 여부를 확인해 다음 행동을 판정한다.", ["고객 상태 조회 정책", "접근·권한 정책"], ["고객 상태 조회", "권한 기준 검증"]),
        ("CS-001", "04", compact_text(f"{cs1_base} 결과 및 후속 경로 안내", 60), f"고객에게 {cs1_focus}의 기준일, 제한 가능성, 후속 업무 경로를 안내한다.", ["대상 정보 노출 정책", "후속 업무 연결 정책"], ["대상 정보 노출", "후속 업무 연결"]),
        ("CS-002", "01", compact_text(f"{cs2_base} 목적 선택", 60), f"고객이 {cs2_focus}의 처리 목적과 대상을 선택하고 채널은 처리 유형을 분류한다.", ["처리 요청 접수 정책", "대상 정보 노출 정책"], ["고객 목적 분류", "처리 유형 분류"]),
        ("CS-002", "02", compact_text(f"{cs2_base} 가능 조건 검증", 60), f"{cs2_focus}의 가능 여부와 제한 사유를 정책 조건과 연계 결과 기준으로 검증한다.", ["가능 여부 검증 정책", "BSS 연계 판정 정책"], ["업무 가능 여부 검증", "제한 사유 생성"]),
        ("CS-002", "03", compact_text(f"{cs2_base} 입력·인증·동의 처리", 60), f"{cs2_focus}에 필요한 입력, 본인확인, 동의 이력을 수집하고 요청 가능 상태를 만든다.", ["인증·동의 정책", "입력값 검증 정책"], ["요청 정보 입력 처리", "인증·동의 연결"]),
        ("CS-002", "04", compact_text(f"{cs2_base} 영향도 확인 및 고지", 60), f"{cs2_focus} 적용 전 비용, 혜택, 상태, 연계 서비스 영향을 산정해 고객에게 고지한다.", ["영향도 고지 정책", "개인정보·로그 보호 정책"], ["영향도 산정", "고객 고지·확인 수집"]),
        ("CS-002", "05", compact_text(f"{cs2_base} 요청 접수", 60), f"고객 최종 확인 후 {cs2_focus} 요청을 접수하고 중복 요청을 제한한다.", ["처리 요청 접수 정책", "중복 요청 제한 정책"], ["처리 요청 접수", "중복 요청 제한"]),
        ("CS-002", "06", compact_text(f"{cs2_base} 결과 반영 및 안내", 60), f"BSS 또는 연계 시스템 처리 결과를 반영하고 {cs2_focus}의 완료, 실패, 보류, 제한 결과를 안내한다.", ["BSS 연계 판정 정책", "처리 결과·이력 정책"], ["BSS 처리 요청", "처리 결과 안내"]),
        ("CS-003", "01", compact_text(f"{cs3_base} 대상 선택", 60), f"고객이 {cs3_focus} 중 필요한 후속 업무를 선택한다.", ["후속 업무 연결 정책", "접근·권한 정책"], ["후속 업무 연결", "권한 기준 검증"]),
        ("CS-003", "02", compact_text(f"{cs3_base} 가능 여부 확인", 60), f"이전 처리 결과와 고객 상태를 기준으로 {cs3_focus}의 가능 여부와 제한 사유를 확인한다.", ["가능 여부 검증 정책", "상태 전환 정책"], ["업무 가능 여부 검증", "제한 사유 생성"]),
        ("CS-003", "03", compact_text(f"{cs3_base} 요청·상태 반영", 60), f"{cs3_focus} 요청을 접수하고 처리 상태, 상담 전환, 재시도 가능 여부를 반영한다.", ["상태 전환 정책", "예외·상담 전환 정책"], ["처리 요청 접수", "상담 전환 정보 생성"]),
        ("CS-003", "04", compact_text(f"{cs3_base} 결과 안내 및 이력 저장", 60), f"{cs3_focus} 결과와 다음 행동을 안내하고 요청, 검증, 고지 이력을 저장한다.", ["처리 결과·이력 정책", "알림·고지 정책"], ["처리 결과 안내", "처리 이력 저장"]),
        ("OPR-001", "01", "운영 기준 정보 관리", "운영자가 기준 정보, 제한 조건, 안내 기준, 적용 기간을 승인 상태로 관리한다.", ["운영 기준 정보 관리 정책", "운영 변경 이력 관리 정책"], ["운영 기준 정보 관리", "운영 변경 이력 관리"]),
        ("OPR-001", "02", "예외 기준 및 승인 관리", "운영자가 예외 허용 조건, 예외 불가 조건, 운영 확인 대상을 관리한다.", ["예외·상담 전환 정책", "운영 기준 정보 관리 정책"], ["예외 기준 관리", "운영 승인 처리"]),
        ("OPR-001", "03", "품질 지표 및 개선 과제 관리", "운영자가 완료율, 실패율, 보류율, 상담 전환율, 고객 피드백을 모니터링하고 개선 과제를 관리한다.", ["품질 관리 정책", "요구사항 반영 관리 정책"], ["품질 지표 모니터링", "개선 과제 등록"]),
    ]
    rows.extend(
        requirement_process_rows(
            representative_requirement_items(requirement_items, structural_requirement_limit),
            structural_requirement_limit,
        )
    )
    return [
        {
            "id": f"PR-{code}-{usecase}-{step}",
            "usecase_id": f"US-{code}-{usecase}",
            "name": name,
            "description": desc,
            "related_functions": functions,
            "related_policies": [policy_ref_by_name[policy] for policy in policies if policy in policy_ref_by_name],
        }
        for usecase, step, name, desc, policies, functions in rows
    ]


def generic_functions(
    code: str,
    requirement_items: Sequence[dict] = (),
    structural_requirement_limit: int = REQUIREMENT_STRUCTURE_ITEM_LIMIT,
) -> List[dict]:
    rows = [
        ("NAV-001", "CS-001-01", "업무 진입 경로 제공", "고객이 업무를 시작할 수 있도록 진입 경로와 기본 안내를 제공한다.", ["업무 진입 경로 제공", "기본 안내 제공", "세션 생성", "진입 이력 저장"]),
        ("CLS-001", "CS-001-01", "고객 목적 분류", "고객이 수행하려는 목적을 분류해 다음 처리 경로를 결정한다.", ["업무 목적 확인", "처리 유형 분류", "위험 업무 식별", "후속 경로 결정"]),
        ("INF-001", "CS-001-02", "대상 정보 조회", "업무 대상 정보와 고객별 적용 가능 정보를 조회한다.", ["기준 정보 조회", "고객별 정보 조회", "연계 정보 조회", "조회 실패 안내"]),
        ("INF-002", "CS-001-02", "기준 정보 구성", "조회된 기준 정보를 고객이 이해할 수 있는 업무 기준으로 구성한다.", ["기준 정보 정리", "적용 조건 구성", "제한 조건 구성", "안내 정보 생성"]),
        ("CST-001", "CS-001-03", "고객 상태 조회", "고객 상태와 업무 제한 여부를 조회해 제공 가능 범위를 판정한다.", ["고객 상태 조회", "보유 정보 조회", "제한 이력 조회", "처리 가능 상태 확인"]),
        ("AUT-001", "CS-001-03", "권한 기준 검증", "고객 권한과 대리 처리 가능 여부를 검증해 노출 가능 범위를 판정한다.", ["로그인 여부 확인", "권한 보유 확인", "대리 처리 기준 확인", "권한 부족 안내"]),
        ("INF-003", "CS-001-04", "대상 정보 노출", "업무 완료에 필요한 대상 정보와 주요 조건을 고객에게 제공한다.", ["대상 정보 제공", "주요 조건 제공", "제한 가능성 안내", "관련 경로 제공"]),
        ("NEXT-001", "CS-001-04", "후속 업무 연결", "조회 결과에 따라 다음 업무, 재시도, 상담, 관련 메뉴 경로를 제공한다.", ["다음 업무 연결", "재시도 경로 제공", "상담 경로 제공", "관련 메뉴 연결"]),
        ("CLS-002", "CS-002-01", "처리 유형 분류", "고객이 선택한 처리 목적을 업무 유형과 위험 수준으로 분류한다.", ["처리 유형 분류", "위험 업무 식별", "필수 확인 항목 산정", "후속 경로 결정"]),
        ("VAL-001", "CS-002-02", "업무 가능 여부 검증", "정책 조건과 연계 결과를 기준으로 업무 가능 여부를 판정한다.", ["필수 조건 검증", "BSS 결과 확인", "연계 결과 확인", "가능 여부 판정"]),
        ("VAL-002", "CS-002-02", "제한 사유 생성", "처리 제한 조건을 고객 안내와 운영 이력에 사용할 수 있는 사유로 생성한다.", ["제한 유형 분류", "제한 사유 생성", "대체 경로 연결", "제한 이력 저장"]),
        ("INP-001", "CS-002-03", "요청 정보 입력 처리", "고객 요청에 필요한 입력 정보를 수집하고 세션에 반영한다.", ["필수 항목 수집", "선택 항목 구분", "입력 중 임시 저장", "입력 취소 처리"]),
        ("AUTH-001", "CS-002-03", "인증·동의 연결", "필요한 본인확인, 추가 인증, 약관 동의 경로로 고객을 연결한다.", ["본인확인 연결", "추가 인증 연결", "약관 동의 연결", "인증·동의 결과 수신"]),
        ("IMP-001", "CS-002-04", "영향도 산정", "처리 전 비용, 혜택, 계약, 상태, 연계 서비스 영향을 산정한다.", ["비용 영향 산정", "혜택 영향 산정", "상태 영향 산정", "연계 영향 확인"]),
        ("IMP-002", "CS-002-04", "고객 고지·확인 수집", "처리 영향과 제한 조건을 고지하고 고객 확인 결과를 저장한다.", ["필수 고지 제공", "고객 확인 수집", "미확인 항목 제한", "고지 이력 저장"]),
        ("REQ-001", "CS-002-05", "처리 요청 접수", "고객 최종 확인 후 처리 요청을 접수하고 처리 상태를 생성한다.", ["최종 요청 접수", "요청 상태 생성", "요청 번호 생성", "접수 이력 저장"]),
        ("REQ-002", "CS-002-05", "중복 요청 제한", "동일 조건의 반복 요청을 확인해 중복 처리와 고객 혼선을 방지한다.", ["중복 요청 조회", "진행 중 요청 확인", "반복 요청 제한", "재요청 가능 시점 안내"]),
        ("LNK-001", "CS-002-06", "BSS 처리 요청", "BSS에 처리 가능 여부 또는 상태 변경 처리를 요청한다.", ["처리 요청 전달", "판정 결과 수신", "상태 변경 요청", "처리 실패 수신"]),
        ("RSLT-001", "CS-002-06", "처리 결과 안내", "처리 결과와 고객이 수행할 다음 행동을 안내한다.", ["성공 안내", "실패 안내", "보류 안내", "다음 행동 안내"]),
        ("FUP-001", "CS-003-01", "후속 업무 후보 제공", "처리 결과와 고객 상태에 따라 선택 가능한 후속 업무를 제공한다.", ["후속 업무 후보 조회", "재시도 가능 시점 확인", "상담 필요 여부 확인", "관련 경로 제공"]),
        ("FUP-002", "CS-003-02", "후속 처리 가능 여부 검증", "이전 처리 이력과 정책 조건을 기준으로 후속 처리 가능 여부를 판정한다.", ["이전 처리 이력 조회", "상태 조건 확인", "제한 사유 생성", "가능 여부 판정"]),
        ("CNS-001", "CS-003-03", "상담 전환 정보 생성", "상담 이관에 필요한 고객 요청, 제한 사유, 처리 이력을 생성한다.", ["상담 사유 생성", "이관 정보 구성", "고객 식별정보 마스킹", "상담 경로 연결"]),
        ("RSLT-002", "CS-003-04", "처리 이력 저장", "요청, 검증, 처리, 결과, 고객 고지 이력을 감사 가능하게 저장한다.", ["요청 이력 저장", "검증 이력 저장", "처리 결과 저장", "고지 확인 저장"]),
        ("NTC-001", "CS-003-04", "알림 발송", "처리 결과와 후속 조치가 필요한 경우 고객에게 알림을 발송한다.", ["알림 대상 판정", "알림 내용 생성", "발송 결과 저장", "발송 실패 재처리"]),
        ("OPR-001", "OPR-001-01", "운영 기준 정보 관리", "운영자가 기준 정보와 제한 조건을 승인 상태로 관리한다.", ["기준 정보 등록", "적용 기간 설정", "승인 상태 관리", "배포 이력 저장"]),
        ("OPR-002", "OPR-001-02", "예외 기준 관리", "운영자가 예외 허용 조건과 예외 불가 조건을 관리한다.", ["예외 조건 등록", "예외 불가 조건 등록", "적용 대상 설정", "예외 적용 이력 저장"]),
        ("QUL-001", "OPR-001-03", "품질 지표 모니터링", "완료율, 실패율, 보류율, 상담 전환율, 고객 피드백을 모니터링한다.", ["완료율 조회", "실패율 조회", "상담 전환율 조회", "피드백 지표 조회"]),
        ("QUL-002", "OPR-001-03", "개선 과제 등록", "고객 불편, 요구사항 누락, 반복 실패를 개선 과제로 등록한다.", ["개선 대상 식별", "개선 과제 생성", "담당자 배정", "처리 상태 관리"]),
    ]
    rows.extend(
        requirement_function_rows(
            representative_requirement_items(requirement_items, structural_requirement_limit),
            structural_requirement_limit,
        )
    )
    return [
        {
            "id": f"FN-{code}-{suffix}",
            "process_id": f"PR-{code}-{process_suffix}",
            "process_ids": [f"PR-{code}-{process_suffix}"],
            "name": name,
            "description": description,
            "details": details,
        }
        for suffix, process_suffix, name, description, details in rows
    ]


def attach_function_refs_to_processes(processes: Sequence[dict], functions: Sequence[dict]) -> None:
    refs_by_process: dict[str, List[str]] = {}
    for function in functions:
        if not isinstance(function, dict):
            continue
        process_ids = function_process_ids(function)
        function_id = str(function.get("id", "")).strip()
        function_name = str(function.get("name", "")).strip()
        function_ref = " ".join(item for item in (function_id, function_name) if item).strip()
        for process_id in process_ids:
            if process_id and function_ref:
                refs_by_process.setdefault(process_id, []).append(function_ref)
    for process in processes:
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("id", "")).strip()
        if process_id in refs_by_process:
            process["related_functions"] = refs_by_process[process_id][:8]


def function_process_ids(function: Mapping[str, object]) -> List[str]:
    values = []
    process_id = str(function.get("process_id", "")).strip()
    if process_id:
        values.append(process_id)
    raw = function.get("process_ids")
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw if str(item).strip())
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def generic_policy_groups(code: str) -> List[dict]:
    rows = [
        ("ACC-001", "접근·권한 정책", "업무 접근 가능 고객, 로그인, 권한, 대리 처리 기준을 정의한다."),
        ("INF-001", "대상 정보 노출 정책", "업무 대상 정보, 기준일, 출처, 노출 제한 기준을 정의한다."),
        ("CST-001", "고객 상태 조회 정책", "고객 상태와 업무 가능 조건 조회 기준을 정의한다."),
        ("VAL-001", "가능 여부 검증 정책", "업무 처리 가능 여부와 제한 사유 판정 기준을 정의한다."),
        ("AUT-001", "인증·동의 정책", "본인확인, 추가 인증, 약관·동의 적용 기준을 정의한다."),
        ("INP-001", "입력값 검증 정책", "고객 입력 항목, 필수 여부, 형식, 중복 검증 기준을 정의한다."),
        ("IMP-001", "영향도 고지 정책", "처리 전 비용, 혜택, 상태, 연계 서비스 영향 고지 기준을 정의한다."),
        ("REQ-001", "처리 요청 접수 정책", "최종 요청 접수, 요청 상태 생성, 접수 이력 저장 기준을 정의한다."),
        ("DUP-001", "중복 요청 제한 정책", "동일 조건 반복 요청과 진행 중 요청 제한 기준을 정의한다."),
        ("BSS-001", "BSS 연계 판정 정책", "BSS 조회, 판정, 상태 변경, 결과 회신 기준을 정의한다."),
        ("STAT-001", "상태 전환 정책", "업무 상태값과 정상·예외·보류·제한 상태 전환 기준을 정의한다."),
        ("RSLT-001", "처리 결과·이력 정책", "처리 결과 구분, 고객 안내, 감사 이력 저장 기준을 정의한다."),
        ("NEXT-001", "후속 업무 연결 정책", "처리 결과 이후 다음 업무, 재시도, 상담, 관련 메뉴 연결 기준을 정의한다."),
        ("ERR-001", "예외·상담 전환 정책", "자동 처리 불가, 반복 실패, 고객 피해 가능 상황의 상담 전환 기준을 정의한다."),
        ("NTC-001", "알림·고지 정책", "처리 결과, 지연, 실패, 추가 확인 필요 상황의 알림 기준을 정의한다."),
        ("PRV-001", "개인정보·로그 보호 정책", "개인정보, 민감정보, 로그, 이력의 마스킹·보관·파기 기준을 정의한다."),
        ("OPR-001", "운영 기준 정보 관리 정책", "기준 정보, 제한 조건, 안내 문구, 적용 기간의 운영 관리 기준을 정의한다."),
        ("OPR-002", "운영 변경 이력 관리 정책", "운영 기준 변경 전후 값, 승인, 배포, 롤백 이력 기준을 정의한다."),
        ("QUL-001", "품질 관리 정책", "완료율, 실패율, 보류율, 상담 전환율, 고객 피드백 관리 기준을 정의한다."),
        ("REQMAP-001", "요구사항 반영 관리 정책", "요구사항과 산출물의 반영, 미반영, 근거 부족 관리 기준을 정의한다."),
        ("ERR-002", "연계 오류·장애 처리 정책", "BSS와 연계 시스템 장애, 지연, 부분 실패 처리 기준을 정의한다."),
        ("DATA-001", "데이터 보관·파기 정책", "처리 이력, 고객 확인, 증적 데이터의 보관·파기 기준을 정의한다."),
    ]
    return [{"id": f"PG-{code}-{suffix}", "name": name, "description": desc} for suffix, name, desc in rows]


def build_policy_details(
    code: str,
    policy_groups: Sequence[dict],
    requirement_items: Sequence[dict] = (),
    max_requirement_items: int = 17,
) -> List[dict]:
    details: List[dict] = []
    for group in policy_groups:
        suffix = group["id"].removeprefix(f"PG-{code}-")
        for index, (name, content) in enumerate(policy_detail_templates(group["name"]), 1):
            details.append(
                {
                    "id": f"PI-{code}-{suffix}-{index:02d}",
                    "policy_id": group["id"],
                    "name": name,
                    "content": ensure_policy_decision_content(content),
                }
            )
    details.extend(requirement_policy_details(code, policy_groups, requirement_items, max_items=max_requirement_items))
    return details


def sync_policy_group_items_from_details(policy_groups: Sequence[dict], policy_details: Sequence[dict]) -> None:
    details_by_policy: dict[str, list[str]] = {}
    for detail in policy_details:
        if not isinstance(detail, dict):
            continue
        policy_id = str(detail.get("policy_id", "")).strip()
        name = str(detail.get("name", "")).strip()
        if policy_id and name:
            details_by_policy.setdefault(policy_id, []).append(name)
    for group in policy_groups:
        if not isinstance(group, dict):
            continue
        policy_id = str(group.get("id", "")).strip()
        if policy_id in details_by_policy:
            group["items"] = details_by_policy[policy_id]


def policy_detail_templates(policy_name: str) -> List[tuple[str, str]]:
    if "접근" in policy_name or "권한" in policy_name:
        return [
            ("접근 허용 범위", "공개 정보는 비로그인 조회를 허용하고, 개인화 정보와 처리 요청은 로그인 또는 본인확인 후 허용한다."),
            ("권한 제한 대상", "대리 처리, 법정대리인, 법인, 미성년, 제한 고객은 업무별 권한 기준을 충족한 경우에만 진행한다."),
            ("인증 전환 대상", "민감정보 노출, 비용 발생, 상태 변경, 계약 영향 업무는 본인확인 또는 추가 인증 단계로 전환한다."),
            ("권한 이력 저장 항목", "고객ID, 접근 결과, 제한 사유, 인증 전환 여부, 요청 채널, 처리 일시를 저장한다."),
        ]
    if "대상 정보" in policy_name or "노출" in policy_name:
        return [
            ("노출 대상", "고객에게 제공하는 대상 정보는 업무 완료에 필요한 기준 정보, 상태 정보, 안내 정보로 제한한다."),
            ("노출 우선순위", "고객 조건에 직접 맞는 정보, 진행 중 업무, 최근 이용 정보, 공통 안내 순으로 노출 우선순위를 둔다."),
            ("노출 제한", "고객 권한, 약관 동의, 보안 기준, 기준일이 충족되지 않은 정보는 개인화 결과에서 제외한다."),
            ("기준일 표시", "요금, 혜택, 약정, 상품 조건처럼 변동 가능한 정보는 기준일 또는 적용 시점을 함께 안내한다."),
        ]
    if "고객 상태" in policy_name:
        return [
            ("상태 조회", "고객 상태는 정상, 제한, 보류, 처리 중, 운영 확인 필요로 구분하고 업무 진입 시 최신 상태를 조회한다."),
            ("상태 사용 기준", "상태값은 업무 가능 여부, 인증 필요 여부, 고지 필요 여부, 상담 전환 여부를 판단하는 기준으로 사용한다."),
            ("상태 불일치 처리", "채널 상태와 BSS 상태가 다르면 BSS 최신 결과를 우선하고 불일치 이력을 운영 확인 대상으로 저장한다."),
            ("상태 이력", "상태 조회 결과, 조회 시점, 상태 전환 사유, 고객 안내 여부는 감사 가능한 이력으로 저장한다."),
        ]
    if "가능 여부" in policy_name:
        return [
            ("검증 항목", "고객 상태, 가입 정보, 보유 상품, 미납·제한, 약정, 혜택, 처리 가능 시간을 검증 항목으로 관리한다."),
            ("가능 판정", "필수 검증 항목이 모두 충족되고 연계 시스템 성공 응답이 확인된 경우에만 처리 가능으로 판정한다."),
            ("제한 판정", "미납, 권한 부족, 약정 제한, 진행 중 업무, 연계 실패가 있으면 처리 제한으로 판정하고 사유를 안내한다."),
            ("재검증 기준", "고객이 조건을 변경하거나 일정 시간이 지나면 가능 여부를 다시 조회해 최신 기준으로 판정한다."),
        ]
    if "인증" in policy_name or "동의" in policy_name:
        return [
            ("인증 수단", "휴대폰 본인확인, PASS 인증, 공동인증서, 간편인증 중 업무 보안 수준에 맞는 수단을 제공한다."),
            ("인증 가능 횟수", "동일 업무 세션 기준 최대 5회까지 허용한다."),
            ("인증번호 유효시간", "인증번호는 발송 후 3분 동안 유효하다."),
            ("인증 실패 처리", "가능 횟수를 초과하거나 유효시간이 만료되면 재요청 또는 상담 경로를 안내하고 상태 변경은 제한한다."),
            ("동의 이력 저장 항목", "동의 항목, 약관 버전, 동의 일시, 철회 여부, 처리 채널을 저장한다."),
        ]
    if "입력값" in policy_name:
        return [
            ("필수 입력 항목", "업무 처리에 필요한 최소 항목만 필수로 지정하고 선택 항목과 구분한다."),
            ("입력 허용 범위", "이름, 연락처, 이메일, 주소, 식별값, 요청값은 업무별 형식과 허용 범위를 검증한다."),
            ("입력 오류 안내 항목", "오류 항목, 수정 방법, 재시도 가능 여부를 안내한다."),
            ("민감정보 제한", "비밀번호, 인증번호, 결제정보 등 민감정보는 저장과 화면 노출 범위를 제한하고 로그에서 마스킹한다."),
        ]
    if "영향도" in policy_name:
        return [
            ("고지 대상", "비용, 혜택, 약정, 회선, 쿠폰, 포인트, 주문, 환불, 데이터 보관에 영향이 있으면 처리 전 고지한다."),
            ("고지 시점", "고객이 최종 처리 요청을 확정하기 전에 영향도, 제한 사유, 적용 시점, 철회 가능 여부를 안내한다."),
            ("확인 기준", "고객이 필수 고지 항목을 확인한 경우에만 다음 단계 또는 최종 처리 요청을 허용한다."),
            ("고지 이력", "고지 항목, 확인 여부, 확인 일시, 적용 기준은 처리 이력과 함께 저장한다."),
        ]
    if "처리 요청" in policy_name:
        return [
            ("접수 조건", "필수 입력, 인증·동의, 영향도 확인, 가능 여부 검증이 완료된 경우에만 처리 요청을 접수한다."),
            ("요청 상태값", "접수, 진행 중, 완료, 실패, 보류, 제한으로 구분한다."),
            ("접수 실패", "요청 접수 실패 시 고객에게 실패 사유와 재시도 가능 여부를 안내하고 완료 상태로 확정하지 않는다."),
            ("접수 이력 저장 항목", "요청자, 접수 일시, 요청 내용, 처리 상태, 접수 실패 사유를 저장한다."),
        ]
    if "중복" in policy_name:
        return [
            ("중복 판단 기준", "동일 고객, 동일 대상, 동일 요청 조건의 진행 중 요청이 있으면 중복 요청으로 판단한다."),
            ("중복 제한", "중복 요청은 추가 접수를 제한하고 기존 요청 상태와 예상 처리 기준을 안내한다."),
            ("재요청 허용", "이전 요청이 실패, 취소, 만료 상태이면 업무별 재요청 가능 기준에 따라 다시 접수할 수 있다."),
            ("중복 이력 저장 항목", "중복 제한 여부, 기존 요청 ID, 고객 안내 여부를 저장한다."),
        ]
    if "BSS" in policy_name:
        return [
            ("조회 기준", "BSS 조회는 고객 상태, 계약, 청구, 혜택, 제한 조건처럼 처리 가능 여부에 영향을 주는 항목으로 제한한다."),
            ("판정 우선순위", "채널 보유 정보와 BSS 결과가 다르면 BSS 최신 판정 결과를 우선 적용한다."),
            ("결과 반영", "BSS 성공 회신과 상태 변경 완료가 확인된 경우에만 처리 완료로 확정한다."),
            ("실패 처리 방식", "BSS 조회 실패 또는 처리 실패 시 개인화 처리와 상태 변경을 제한하고 공통 안내 또는 상담 경로를 제공한다."),
        ]
    if "상태 전환" in policy_name:
        return [
            ("전환 조건", "상태 전환은 필수 검증과 연계 처리 결과가 충족된 경우에만 수행한다."),
            ("전환 실패", "상태 전환 실패 시 완료로 확정하지 않고 보류, 실패, 운영 확인 필요 중 하나로 분류한다."),
            ("전환 고지", "고객 이용 가능 여부나 혜택에 영향을 주는 상태 전환은 고객에게 결과와 적용 시점을 안내한다."),
            ("전환 이력", "전환 전 상태, 전환 후 상태, 전환 사유, 처리자, 처리 시점은 감사 가능한 이력으로 저장한다."),
        ]
    if "처리 결과" in policy_name or "이력" in policy_name:
        return [
            ("결과 구분", "처리 결과는 성공, 실패, 보류, 제한, 운영 확인 필요로 구분하고 고객에게 다음 행동을 안내한다."),
            ("반영 기준", "연계 시스템 성공 회신과 상태 변경 완료가 모두 확인된 경우에만 처리 완료로 확정한다."),
            ("실패 안내", "실패 또는 제한 결과는 사유, 재시도 가능 여부, 상담 전환 가능 여부, 적용되지 않은 항목을 안내한다."),
            ("이력 저장", "요청자, 처리 일시, 결과, 실패 사유, 연계 응답, 고객 고지 여부는 감사 가능한 이력으로 저장한다."),
        ]
    if "후속 업무" in policy_name:
        return [
            ("연결 대상", "처리 완료, 실패, 제한, 보류 결과에 따라 다음 업무, 재시도, 상담, 관련 메뉴 중 하나 이상을 제공한다."),
            ("연결 제한", "권한 부족, 인증 필요, 고위험 업무, 연계 오류가 있으면 직접 연결 대신 안내 또는 상담 경로를 제공한다."),
            ("컨텍스트 전달", "후속 업무로 이동할 때 고객 요청, 대상 정보, 처리 결과, 제한 사유를 필요한 범위에서 전달한다."),
            ("연결 이력", "후속 업무 선택, 진입 성공 여부, 실패 사유는 품질 관리와 운영 개선 이력으로 저장한다."),
        ]
    if "예외" in policy_name or "상담" in policy_name:
        return [
            ("상담 전환 조건", "권한 불일치, 반복 실패, 고객 피해 가능성, 연계 장애, 자동 판정 불가는 상담 전환 대상으로 본다."),
            ("재시도 허용", "일시 오류와 입력 오류는 동일 조건에서 제한 횟수 내 재시도를 허용한다."),
            ("운영 확인", "기준 정보 불일치, 고객 이력 충돌, 반복 민원은 운영 확인 큐에 등록한다."),
            ("예외 안내", "예외 발생 시 고객에게 처리 지연 사유, 대체 경로, 예상 후속 조치를 안내한다."),
        ]
    if "알림" in policy_name or "고지" in policy_name:
        return [
            ("알림 대상", "처리 완료, 실패, 보류, 추가 확인 필요, 고객 영향 발생 건은 알림 대상으로 분류한다."),
            ("알림 채널", "알림은 고객 동의, 업무 중요도, 보안 수준에 따라 앱 알림, 문자, 이메일, 상담 안내 중 하나로 제공한다."),
            ("미발송 처리 방식", "알림 발송 실패 시 중요 업무는 재발송 또는 상담 안내 대상으로 분류한다."),
            ("발송 이력 저장 항목", "알림 내용, 발송 채널, 발송 시점, 성공 여부를 저장한다."),
        ]
    if "개인정보" in policy_name or "로그" in policy_name:
        return [
            ("최소 수집", "업무 처리와 품질 개선에 필요한 최소 정보만 수집하고 목적 외 활용을 제한한다."),
            ("마스킹 기준", "주민등록번호, 계좌번호, 카드번호, 인증번호, 비밀번호 등 민감정보는 화면과 로그에서 마스킹한다."),
            ("보관 기간", "처리 이력, 인증 이력, 고객 안내 이력은 목적과 법정 기준에 맞는 보관 기간을 적용한다."),
            ("열람 통제", "운영자 열람은 권한, 사유, 이력 저장 기준을 충족한 경우에만 허용한다."),
        ]
    if "운영 기준" in policy_name:
        return [
            ("기준 정보 관리", "운영자는 업무 기준 정보, 노출 조건, 제한 기준, 안내 문구, 적용 기간을 승인 상태로 관리한다."),
            ("변경 승인", "고객 영향이 있는 운영 기준 변경은 담당자 검토와 승인 후 적용한다."),
            ("배포 기준", "운영 기준은 적용 시작일, 종료일, 대상 채널, 예외 대상을 지정해 배포한다."),
            ("변경 이력", "변경자, 변경일, 변경 사유, 변경 전후 값, 승인자는 운영 이력으로 저장한다."),
        ]
    if "운영 변경" in policy_name:
        return [
            ("변경 대상", "고객 노출, 처리 가능 여부, 제한 조건, 안내 문구, 운영 예외 기준 변경은 이력 관리 대상으로 본다."),
            ("승인 절차", "고객 영향이 있는 변경은 작성자, 검토자, 승인자, 적용일을 지정한 뒤 반영한다."),
            ("롤백 기준", "변경 후 실패율 증가, 고객 민원 증가, 기준 오류가 확인되면 이전 기준으로 롤백할 수 있다."),
            ("감사 이력", "변경 전후 값, 사유, 승인자, 배포 결과, 롤백 여부는 감사 가능한 이력으로 저장한다."),
        ]
    if "품질" in policy_name:
        return [
            ("품질 지표", "완료율, 실패율, 재시도율, 상담 전환율, 처리 지연, 고객 피드백을 품질 지표로 관리한다."),
            ("모니터링 주기", "핵심 품질 지표는 일·주·월 단위로 확인하고 급증 오류는 즉시 검토 대상으로 분류한다."),
            ("개선 과제", "반복 실패, 상담 전환 과다, 고객 불만 반복, 기준 정보 오류는 개선 과제로 등록한다."),
            ("효과 추적", "운영 보정 후 완료율, 실패율, 상담 전환율, 고객 피드백 변화를 비교해 개선 효과를 확인한다."),
        ]
    if "요구사항" in policy_name:
        return [
            ("반영 기준", "요구사항은 유즈케이스, 상태, 프로세스, 기능, 정책 중 하나 이상에 반영해야 한다."),
            ("미반영 기준", "정책서 범위를 벗어나거나 후속 산출물에서 상세화할 항목은 미반영 사유와 후속 대상을 기록한다."),
            ("근거 부족", "요구사항 근거가 부족하면 Evidence Gap으로 표시하고 결정 주체와 추가 확인 필요 항목을 남긴다."),
            ("추적 관리", "요구사항 ID와 산출물 ID의 연결은 최종 검수와 변경 관리 기준으로 활용한다."),
        ]
    if "오류" in policy_name or "장애" in policy_name:
        return [
            ("장애 구분", "BSS 장애, 연계 장애, 인증기관 장애, 채널 장애, 일시 지연을 구분해 처리 기준을 적용한다."),
            ("처리 제한", "정확한 판정이 불가능한 장애 상황에서는 상태 변경과 비용 발생 처리를 제한한다."),
            ("재시도 기준", "일시 장애는 제한 횟수 내 재시도를 허용하고 반복 장애는 상담 또는 운영 확인으로 전환한다."),
            ("장애 이력", "장애 유형, 발생 시점, 고객 영향, 처리 결과는 운영 모니터링 이력으로 저장한다."),
        ]
    if "데이터" in policy_name or "보관" in policy_name or "파기" in policy_name:
        return [
            ("보관 대상", "처리 이력, 인증 이력, 고지 확인, 연계 결과, 운영 변경 증적은 목적별 보관 대상으로 분류한다."),
            ("파기 대상", "업무 목적이 종료되고 법정 보관 사유가 없는 개인정보와 임시 데이터는 파기 대상으로 분류한다."),
            ("보관 기간", "보관 기간은 법령, 내부 기준, 감사 필요성, 고객 분쟁 가능성을 기준으로 적용한다."),
            ("파기 이력", "파기 대상, 파기 시점, 파기 방식, 처리자는 감사 가능한 이력으로 저장한다."),
        ]
    return [
        ("적용 조건", f"{policy_name}은 고객 상태, 업무 조건, 인증·동의 여부, 연계 시스템 응답이 충족된 경우 적용한다."),
        ("제한 처리값", "필수 조건이 충족되지 않으면 처리 제한, 재시도, 상담 전환, 운영 확인 중 하나로 분류한다."),
        ("고객 안내 항목", "제한 사유, 다음 행동, 재시도 가능 여부, 상담 경로를 안내한다."),
        ("이력 저장 항목", "판정 결과, 처리 일시, 요청자, 실패 사유, 연계 응답을 저장한다."),
    ]


def ensure_policy_decision_content(content: str) -> str:
    decision_keywords = (
        "허용",
        "제한",
        "분류",
        "기준",
        "조건",
        "필수",
        "저장",
        "보관",
        "고지",
        "안내",
        "실패",
        "예외",
        "유효",
        "판정",
        "전환",
        "생성",
        "복원",
        "초기화",
        "종료",
        "폐기",
        "발급",
        "재발급",
        "구분",
        "조회",
        "확정",
        "성공",
        "중단",
        "소멸",
        "마스킹",
    )
    if any(keyword in content for keyword in decision_keywords):
        return content
    if re.search(r"\d|분|시간|일|회|개월|년|앱|웹|SMS|이메일|BSS|CI|DI|PASS|마스킹", content, flags=re.IGNORECASE):
        return content
    if any(separator in content for separator in (",", "·", "/", " 또는 ")):
        return content
    return f"{content} 이 항목은 기능 동작값 또는 제한 조건으로 관리한다."


def generic_final_check(topic: str) -> List[str]:
    return [
        f"{topic} 범위, 제외 범위, 후속 상세화 영역이 고객 과업 기준으로 명확한지 확인한다.",
        "고객이 업무를 시작해 완료하거나 제한 사유와 대체 경로를 확인할 수 있는지 확인한다.",
        "유즈케이스, 상태, 프로세스, 기능, 정책의 ID와 연결 관계가 누락 없이 이어지는지 확인한다.",
        "BSS와 연계 시스템의 조회, 판정, 상태 변경, 결과 회신 기준이 프로세스와 정책에 반영됐는지 확인한다.",
        "모든 프로세스가 관련 기능과 실제 정책 그룹명에 연결되어 있는지 확인한다.",
        "모든 기능이 화면 단위가 아니라 처리 단위이며 세부 기능 구성이 있는지 확인한다.",
        "정책 상세가 기능 설명이 아니라 실제 기능 동작값, 허용 목록, 횟수, 시간, 제한 조건, 채널, 고지, 저장 기준으로 작성됐는지 확인한다.",
        "개인정보, 민감정보, 로그, 이력, 보관·파기 기준이 포함되어 있는지 확인한다.",
        "운영 기준 관리, 변경 이력, 품질 모니터링, 개선 과제 관리 기준이 포함되어 있는지 확인한다.",
        "요구사항 통합 list의 관련 요구사항이 유즈케이스, 상태, 프로세스, 기능, 정책 중 하나 이상에 반영됐는지 확인한다.",
        "참고자료에서 확인한 고객 불편, 채널 전략, IA, VoC, 운영 기준이 정책 판단 기준으로 재구성됐는지 확인한다.",
    ]
