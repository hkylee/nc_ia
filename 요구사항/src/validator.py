"""Validation rules for policy JSON specifications."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence


REQUIRED_TOP_LEVEL_KEYS = (
    "meta",
    "history",
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

FORBIDDEN_POLICY_PHRASES = (
    "검토 필요",
    "추후 협의",
    "시스템에서 처리",
    "가능하도록 한다",
    "정책에 따라 처리한다",
    "관련 부서 확인 필요",
)
POLICY_DECISION_CRITERIA_PATTERN = re.compile(
    r"(\d+|TBD|Y|N|최대|최소|이상|이하|초과|미만|허용|제한|필수|선택|회|횟수|분|시간|일|개월|만료|보관|저장|고지|예외|우선순위|동의|인증|상태|대상|조건|기한|재시도|상담 전환|운영 확인|불가|가능)"
)
POLICY_DETAIL_DIMENSION_PATTERNS = {
    "allowed_values": re.compile(r"(허용|가능|대상|적용 대상|제공|수락|승인|필수|선택)"),
    "restricted_values": re.compile(r"(제한|불가|차단|거절|중단|보류|제외|금지)"),
    "count_limit": re.compile(r"(\d+\s*회|횟수|최대\s*\d+|최소\s*\d+)"),
    "time_limit": re.compile(r"(\d+\s*(분|시간|일|개월|년)|유효\s*시간|만료|기한|기간|유예)"),
    "amount_limit": re.compile(r"(금액|원|포인트|할인|한도|청구액|결제액)"),
    "state_condition": re.compile(r"(상태|완료|실패|보류|취소|만료|승인|대기|처리중|처리 중)"),
    "exception_rule": re.compile(r"(예외|단,|다만|복구|재처리|재시도|상담 전환|운영 확인)"),
    "notification_rule": re.compile(r"(고지|안내|알림|통지|회신|결과 제공)"),
    "history_rule": re.compile(r"(이력|로그|기록|저장|보관|삭제|파기|변경 내역)"),
    "bss_reflection_rule": re.compile(r"(BSS|원장|연계|반영|동기화|외부 시스템 응답)"),
    "external_system_rule": re.compile(r"(외부|제휴|PG|인증기관|배송사|결제기관|승인기관)"),
}
WEAK_POLICY_DETAIL_MARKERS = (
    "원활하게",
    "적절히",
    "필요에 따라",
    "상황에 따라",
    "관련 기준에 따라",
    "일반적으로",
    "관리한다",
    "처리한다",
)
WEAK_POLICY_CONTENT_PATTERNS = (
    re.compile(r"(상태|상황|조건|대상).{0,10}따라.{0,10}(처리|관리)한다"),
    re.compile(r"(업무|서비스|정보).{0,10}(원활하게|적절히).{0,10}(처리|관리)한다"),
)
BODY_ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:TM|ACT|US|ST|PR|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
FUNCTION_DETAIL_SENTENCE_PATTERN = re.compile(
    r"(한다|된다|받는다|만든다|남긴다|불러온다|표시한다|제공한다|반환한다)\.?$"
)
FUNCTION_PROCESSING_LOGIC_PATTERN = re.compile(
    r"^\s*\(상태\)\s*.+?\s*→\s*\(액션\)\s*.+?\s*→\s*\(결과\)\s*.+"
)
MAX_PROCESSES_PER_Y_USECASE = 7

STATE_IMPACT_SYSTEM_USECASE_ANCHORS = (
    "BSS",
    "원장",
    "연계",
    "외부",
    "제휴",
    "분석",
    "시스템",
)
STATE_IMPACT_DECISION_KEYWORDS = (
    "상태",
    "조건",
    "권한",
    "자격",
    "판정",
    "반영",
    "회신",
    "저장",
    "이력",
    "동기화",
    "실패",
    "복구",
    "가능 여부",
    "노출 가능",
    "처리 결과",
)

@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: Sequence[str]


def validate_policy_spec(spec: dict, business_code: str | None = None, allow_incomplete: bool = False) -> ValidationResult:
    errors: List[str] = []
    if not isinstance(spec, dict):
        return ValidationResult(False, ["정책서 JSON 스펙은 객체여야 합니다."])

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in spec:
            errors.append(f"필수 키가 없습니다: {key}")

    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    code = business_code or str(meta.get("business_code", "")).strip()
    if not code:
        errors.append("meta.business_code가 없습니다.")

    errors.extend(check_list(spec, "history", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "terms", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "actors", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "usecases", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "states", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "state_transitions", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "processes", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "functions", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "policy_groups", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "policy_details", allow_empty=allow_incomplete))
    errors.extend(check_list(spec, "final_check", allow_empty=allow_incomplete))
    if not allow_incomplete:
        errors.extend(validate_final_document_value_completeness(spec, code))
        errors.extend(validate_state_transition_integrity(spec))

    if code:
        errors.extend(validate_id_pattern(spec.get("actors", []), "actor.id", "id", rf"^ACT-{re.escape(code)}-\d{{3}}$"))
        errors.extend(validate_id_pattern(spec.get("usecases", []), "usecase.id", "id", rf"^US-{re.escape(code)}-.+"))
        errors.extend(validate_id_pattern(spec.get("processes", []), "process.id", "id", rf"^PR-{re.escape(code)}-.+"))
        errors.extend(validate_id_pattern(spec.get("functions", []), "function.id", "id", rf"^FN-{re.escape(code)}-.+"))
        errors.extend(validate_id_pattern(spec.get("policy_groups", []), "policy.id", "id", rf"^PG-{re.escape(code)}-.+"))
        errors.extend(validate_id_pattern(policy_detail_items(spec), "policy item id", "id", rf"^PI-{re.escape(code)}-.+"))

    errors.extend(validate_unique_ids(spec, ("actors", "usecases", "states", "processes", "functions", "policy_groups", "policy_details")))
    errors.extend(validate_actor_definition_granularity(spec))
    errors.extend(validate_actor_links(spec, allow_incomplete=allow_incomplete))
    errors.extend(validate_usecase_links(spec))
    errors.extend(validate_process_policy_links(spec, allow_incomplete=allow_incomplete))
    errors.extend(validate_policy_detail_links(spec, allow_incomplete=allow_incomplete))
    errors.extend(validate_policy_detail_content(spec, allow_incomplete=allow_incomplete))
    errors.extend(validate_overview(spec, allow_incomplete=allow_incomplete))
    if is_full_template(spec) and not allow_incomplete:
        errors.extend(validate_full_process_details(spec))
        errors.extend(validate_full_function_details(spec))

    return ValidationResult(not errors, errors)


def validate_stage_critical(spec: dict, business_code: str | None = None, scope: str = "full") -> ValidationResult:
    """Fast JSON gate for errors that should be fixed before expensive HTML/LLM inspection."""
    base_result = validate_policy_spec(spec, business_code, allow_incomplete=True)
    errors: List[str] = list(base_result.errors)
    rank = scope_rank(scope)

    if rank >= 4:
        errors.extend(validate_actor_usecase_coverage(spec))
        errors.extend(validate_usecase_process_target(spec))
        errors.extend(validate_usecase_granularity(spec))
    if rank >= 2:
        errors.extend(validate_terms_critical_fields(spec, business_code or ""))
    if rank >= 3:
        errors.extend(validate_actor_definition_granularity(spec))
    if rank >= 5:
        errors.extend(validate_usecase_diagram_coverage(spec))
    if rank >= 6:
        errors.extend(validate_state_transition_integrity(spec))
        errors.extend(validate_state_text_quality(spec))
        errors.extend(validate_state_impact_system_usecase_coverage(spec))
    if rank >= 7:
        errors.extend(validate_process_critical_links(spec))
    if rank >= 9 and is_full_template(spec) and scope in {"09_process_detail", "process_detail", "09_function_detail", "function_detail", "full"}:
        errors.extend(validate_full_process_details(spec))
    if rank >= 8:
        errors.extend(validate_function_critical_links(spec))
    if rank >= 9 and is_full_template(spec) and scope in {"09_function_detail", "function_detail", "full"}:
        errors.extend(validate_full_function_details(spec))
    if rank >= 9:
        errors.extend(validate_policy_critical_links(spec))
        errors.extend(validate_policy_specificity(spec))
        errors.extend(validate_topic_specific_coverage(spec))
    if rank >= 10:
        errors.extend(validate_final_document_value_completeness(spec, business_code or ""))
        errors.extend(validate_blueprint_grounding(spec))
        errors.extend(validate_open_inspector_issues(spec))

    deduped = dedupe(errors)
    return ValidationResult(not deduped, deduped)


def validate_final_document_value_completeness(spec: dict, business_code: str | None = None) -> List[str]:
    """Catch final-document blanks that render as empty cells or broken references.

    The rule is intentionally scoped to real policy documents that carry authoring
    metadata, so small unit-test fixtures and partial chapter payloads are not
    over-constrained.
    """
    if not should_enforce_document_value_completeness(spec):
        return []

    errors: List[str] = []
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    code = str(business_code or meta.get("business_code", "")).strip()

    required_meta_fields = (
        ("module_id", "meta.module_id"),
        ("topic", "meta.topic"),
        ("business_code", "meta.business_code"),
    )
    for field, label in required_meta_fields:
        if not str(meta.get(field, "")).strip():
            errors.append(f"Final Gate: {label} 값이 비어 있습니다.")

    if not str(meta.get("status", "") or meta.get("document_status", "")).strip():
        errors.append("Final Gate: 문서 상태 값이 비어 있습니다. meta.status 또는 meta.document_status가 필요합니다.")
    if not str(meta.get("date", "") or meta.get("created_at", "")).strip():
        errors.append("Final Gate: 작성일 값이 비어 있습니다. meta.date 또는 meta.created_at이 필요합니다.")
    if not nonempty_text_or_list(meta.get("authoring_basis")):
        errors.append("Final Gate: 작성 기준(meta.authoring_basis)이 비어 있습니다.")

    history = list_items(spec, "history")
    if not history:
        errors.append("Final Gate: 문서 히스토리가 비어 있습니다.")
    for index, item in enumerate(history, start=1):
        label = f"history[{index}]"
        if not str(item.get("version", "")).strip():
            errors.append(f"Final Gate: {label}.version 값이 비어 있습니다.")
        if not str(item.get("date", "")).strip():
            errors.append(f"Final Gate: {label}.date 값이 비어 있습니다.")
        if not str(item.get("change", "") or item.get("changes", "") or item.get("description", "") or item.get("summary", "")).strip():
            errors.append(f"Final Gate: {label}.change 값이 비어 있습니다.")

    term_id_pattern = re.compile(rf"^TM-{re.escape(code)}-\d{{3}}$") if code else None
    for index, term in enumerate(list_items(spec, "terms"), start=1):
        label = str(term.get("id", "")).strip() or f"terms[{index}]"
        term_id = str(term.get("id", "")).strip()
        if not term_id:
            errors.append(f"Final Gate: 용어 ID가 비어 있습니다: terms[{index}]")
        elif term_id_pattern and not term_id_pattern.match(term_id):
            errors.append(f"Final Gate: 용어 ID 형식이 올바르지 않습니다: {term_id}")
        if not str(term.get("name", "") or term.get("term", "")).strip():
            errors.append(f"Final Gate: 용어명이 비어 있습니다: {label}")
        if not str(term.get("description", "") or term.get("definition", "")).strip():
            errors.append(f"Final Gate: 용어 설명이 비어 있습니다: {label}")

    for process in list_items(spec, "processes"):
        process_id = str(process.get("id", "")).strip() or "processes[]"
        for field in ("description", "related_functions", "related_policies"):
            if field.startswith("related_"):
                if not nonempty_list(process.get(field)):
                    errors.append(f"Final Gate: 프로세스 {field} 값이 비어 있습니다: {process_id}")
            elif not str(process.get(field, "")).strip():
                errors.append(f"Final Gate: 프로세스 {field} 값이 비어 있습니다: {process_id}")

    for function in list_items(spec, "functions"):
        function_id = str(function.get("id", "")).strip() or "functions[]"
        if not str(function.get("description", "")).strip():
            errors.append(f"Final Gate: 기능 설명이 비어 있습니다: {function_id}")
        if not nonempty_list(function.get("details")):
            errors.append(f"Final Gate: 기능 세부 기능 구성이 비어 있습니다: {function_id}")

    return errors


def should_enforce_document_value_completeness(spec: dict) -> bool:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    indicators = ("module_id", "document_status", "status", "created_at", "date", "authoring_basis")
    return any(meta.get(field) for field in indicators)


def validate_actor_usecase_coverage(spec: dict) -> List[str]:
    actors = list_items(spec, "actors")
    usecases = list_items(spec, "usecases")
    actor_names = {str(actor.get("name", "")).strip() for actor in actors if str(actor.get("name", "")).strip()}
    actor_ids = {str(actor.get("id", "")).strip() for actor in actors if str(actor.get("id", "")).strip()}
    used = {str(usecase.get("actor", "")).strip() for usecase in usecases if str(usecase.get("actor", "")).strip()}
    errors = []
    for usecase in usecases:
        actor = str(usecase.get("actor", "")).strip()
        if actor and actor not in actor_names and actor not in actor_ids:
            errors.append(f"Critical Gate: 유즈케이스 actor가 액터 목록에 없습니다: {usecase.get('id', '')} / {actor}")
    missing = [
        str(actor.get("name", "")).strip()
        for actor in actors
        if str(actor.get("name", "")).strip()
        and str(actor.get("name", "")).strip() not in used
        and str(actor.get("id", "")).strip() not in used
    ]
    if missing:
        errors.append(f"Critical Gate: 액터가 유즈케이스에 연결되지 않았습니다: {', '.join(missing[:8])}")
    return errors


def validate_actor_definition_granularity(spec: dict) -> List[str]:
    actors = list_items(spec, "actors")
    if not actors:
        return []
    errors: List[str] = []
    actor_names = [str(actor.get("name", "")).strip() for actor in actors if str(actor.get("name", "")).strip()]
    if len(actor_names) > 8:
        errors.append(
            "Critical Gate: 액터가 8개를 초과해 과분화 가능성이 큽니다. "
            "고객, 운영자, 상담사, 채널 업무 시스템, 도메인/BSS 연계 시스템처럼 책임 단위로 통합하세요."
        )
    for name in actor_names:
        reason = actor_granularity_violation_reason(name)
        if reason:
            errors.append(f"Critical Gate: 액터 정의가 과분화되었습니다: {name} / {reason}")
    detailed_internal_operators = [
        name for name in actor_names if is_detailed_internal_operator_actor(name)
    ]
    if len(detailed_internal_operators) >= 2:
        errors.append(
            "Critical Gate: 내부 운영 역할이 여러 액터로 과분화되었습니다. "
            f"{', '.join(detailed_internal_operators[:6])}는 기본적으로 '운영자'로 통합하고 차이는 기능·정책 책임으로 내려 작성하세요."
        )
    detailed_systems = [
        name for name in actor_names if is_detailed_system_actor(name)
    ]
    if len(detailed_systems) >= 2:
        errors.append(
            "Critical Gate: 세부 시스템이 여러 액터로 과분화되었습니다. "
            f"{', '.join(detailed_systems[:6])}는 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합하고 세부 책임은 기능·정책에 반영하세요."
        )
    return errors


def validate_terms_critical_fields(spec: dict, business_code: str | None = "") -> List[str]:
    """Prevent rendered term rows with blank IDs or descriptions.

    The renderer exposes a dedicated "용어 ID" column, so term IDs need to be
    present from the terms chapter onward rather than discovered only at final
    save time.
    """

    terms = list_items(spec, "terms")
    if not terms:
        return []
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    code = str(business_code or meta.get("business_code", "")).strip()
    term_id_pattern = re.compile(rf"^TM-{re.escape(code)}-\d{{3}}$") if code else None
    errors: List[str] = []
    for index, term in enumerate(terms, start=1):
        label = str(term.get("id", "")).strip() or f"terms[{index}]"
        term_id = str(term.get("id", "")).strip()
        if not term_id:
            errors.append(f"Critical Gate: 용어 ID가 비어 있습니다: terms[{index}]")
        elif term_id_pattern and not term_id_pattern.match(term_id):
            errors.append(f"Critical Gate: 용어 ID 형식이 올바르지 않습니다: {term_id}")
        if not str(term.get("name", "") or term.get("term", "")).strip():
            errors.append(f"Critical Gate: 용어명이 비어 있습니다: {label}")
        if not str(term.get("description", "") or term.get("definition", "")).strip():
            errors.append(f"Critical Gate: 용어 설명이 비어 있습니다: {label}")
    return errors


def validate_usecase_granularity(spec: dict) -> List[str]:
    errors: List[str] = []
    for usecase in list_items(spec, "usecases"):
        if str(usecase.get("process_target", "")).strip().upper() != "Y":
            continue
        name = str(usecase.get("name", "")).strip()
        if is_step_like_usecase_name(name):
            errors.append(
                "Critical Gate: 절차 단계가 process_target=Y 유즈케이스로 작성되었습니다. "
                f"상위 업무 목적 유즈케이스로 묶고 해당 항목은 프로세스로 내려 작성하세요: {usecase.get('id', '')} / {name}"
            )
    return errors


def validate_usecase_process_target(spec: dict) -> List[str]:
    actor_by_name = {
        str(actor.get("name", "")).strip(): actor
        for actor in list_items(spec, "actors")
        if str(actor.get("name", "")).strip()
    }
    errors = []
    for usecase in list_items(spec, "usecases"):
        actor_name = str(usecase.get("actor", "")).strip()
        process_target = str(usecase.get("process_target", "")).strip().upper()
        if actor_name in actor_by_name and is_human_actor_name(actor_name) and process_target != "Y":
            errors.append(
                f"Critical Gate: 사람 액터 유즈케이스는 process_target=Y여야 합니다: {usecase.get('id', '')} / {actor_name}"
            )
        if actor_name in actor_by_name and is_system_actor_name(actor_name) and process_target == "Y":
            errors.append(
                f"Critical Gate: 시스템/기관 액터 유즈케이스는 process_target=N이어야 합니다: {usecase.get('id', '')} / {actor_name}"
            )
    return errors


def validate_usecase_diagram_coverage(spec: dict) -> List[str]:
    diagram = spec.get("meta", {}).get("usecase_diagram", {}) if isinstance(spec.get("meta"), dict) else {}
    lines = diagram.get("lines", []) if isinstance(diagram, dict) else []
    joined = "\n".join(str(line) for line in lines if line)
    missing = []
    disconnected = []
    for usecase in list_items(spec, "usecases"):
        name = str(usecase.get("name", "")).strip()
        actor = str(usecase.get("actor", "")).strip()
        if not name:
            continue
        if name not in joined:
            missing.append(name)
            continue
        if actor and not any(actor in str(line) and name in str(line) for line in lines):
            disconnected.append(f"{actor} → {name}")
    if missing:
        return [f"Critical Gate: 유즈케이스 다이어그램에 누락된 유즈케이스가 있습니다: {', '.join(missing[:8])}"]
    if disconnected:
        return [f"Critical Gate: 유즈케이스 다이어그램에서 액터와 유즈케이스가 같은 관계선에 연결되지 않았습니다: {', '.join(disconnected[:8])}"]
    return []


def validate_state_transition_integrity(spec: dict) -> List[str]:
    states = list_items(spec, "states")
    transitions = list_items(spec, "state_transitions")
    usecases = list_items(spec, "usecases")
    state_names = [str(state.get("name", "")).strip() for state in states if str(state.get("name", "")).strip()]
    state_name_set = set(state_names)
    state_id_set = {str(state.get("id", "")).strip() for state in states if str(state.get("id", "")).strip()}
    usecase_ids = {str(usecase.get("id", "")).strip() for usecase in usecases if str(usecase.get("id", "")).strip()}
    errors = []
    duplicates = sorted({name for name in state_names if state_names.count(name) > 1})
    for name in duplicates:
        errors.append(f"Critical Gate: 상태명이 중복되었습니다: {name}")
    if states and not transitions:
        errors.append("Critical Gate: 상태 코드가 있으나 상태 전이 기준이 없습니다.")
    for transition in transitions:
        transition_usecase_ids = transition_usecase_ids_value(transition)
        if usecase_ids and not transition_usecase_ids:
            errors.append("Critical Gate: 상태 전이에 상태 변경을 발생시키는 usecase_ids가 없습니다.")
        invalid_usecase_ids = [value for value in transition_usecase_ids if value not in usecase_ids]
        if invalid_usecase_ids:
            errors.append(f"Critical Gate: 상태 전이 usecase_ids가 유즈케이스 목록에 없습니다: {', '.join(invalid_usecase_ids[:6])}")
        if transition_usecase_ids and not str(transition.get("event", "")).strip():
            errors.append("Critical Gate: 상태 전이 이벤트가 비어 있습니다.")
        current = str(transition.get("current_state", "")).strip()
        next_state = str(transition.get("next_state", "")).strip()
        if current and current not in state_name_set and current not in state_id_set:
            errors.append(f"Critical Gate: 현재 상태가 상태 목록의 ID/이름에 없습니다: {current}")
        if next_state and next_state not in state_name_set and next_state not in state_id_set:
            errors.append(f"Critical Gate: 다음 상태가 상태 목록의 ID/이름에 없습니다: {next_state}")
    return errors


def transition_usecase_ids_value(transition: Mapping[str, object]) -> List[str]:
    values = transition.get("usecase_ids")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    legacy = str(transition.get("usecase_id", "")).strip()
    return [legacy] if legacy else []


def validate_state_text_quality(spec: dict) -> List[str]:
    errors = []
    state_fields = ("name", "description", "next_action")
    transition_fields = ("event", "criteria")
    for index, state in enumerate(list_items(spec, "states"), start=1):
        state_id = str(state.get("id", "")).strip() or f"states[{index}]"
        if not str(state.get("name", "") or "").strip():
            errors.append(f"Critical Gate: 상태 name가 비어 있습니다: {state_id}")
        for field in ("description", "next_action"):
            value = str(state.get(field, "") or "").strip()
            if not value:
                errors.append(f"Critical Gate: 상태 {field}가 비어 있습니다: {state_id}")
        for field in state_fields:
            value = str(state.get(field, "") or "")
            if BODY_ID_PATTERN.search(value):
                errors.append(f"Critical Gate: 상태 {field} 본문에 내부 ID가 노출되었습니다: {state_id}")
    for index, transition in enumerate(list_items(spec, "state_transitions"), start=1):
        label = f"{transition.get('current_state', '')}->{transition.get('next_state', '')}" or f"state_transitions[{index}]"
        for field in transition_fields:
            value = str(transition.get(field, "") or "")
            if not value.strip():
                errors.append(f"Critical Gate: 상태 전이 {field}가 비어 있습니다: {label}")
            if BODY_ID_PATTERN.search(value):
                errors.append(f"Critical Gate: 상태 전이 {field} 본문에 내부 ID가 노출되었습니다: {label}")
    return errors


def validate_state_impact_system_usecase_coverage(spec: dict) -> List[str]:
    """Ensure system/BSS judgement usecases are not left outside state flow.

    `process_target=N` usecases should not become standalone processes, but
    they still need to appear in state transitions when their judgement changes
    customer-visible availability, reflection, failure, or recovery states.
    """

    transitions = list_items(spec, "state_transitions")
    if not transitions:
        return []
    used_usecase_ids = {
        usecase_id
        for transition in transitions
        for usecase_id in transition_usecase_ids_value(transition)
    }
    errors: List[str] = []
    for usecase in list_items(spec, "usecases"):
        usecase_id = str(usecase.get("id", "")).strip()
        if not usecase_id or usecase_id in used_usecase_ids:
            continue
        if str(usecase.get("process_target", "")).strip().upper() != "N":
            continue
        text = " ".join(
            normalize_space(usecase.get(field, ""))
            for field in ("id", "actor", "name", "description")
        )
        if not system_usecase_affects_state_flow(text):
            continue
        errors.append(
            "Critical Gate: 시스템/BSS 유즈케이스가 상태 전이에 연결되지 않았습니다. "
            "process_target=N이어도 고객 상태, 표시 가능 여부, BSS/외부 회신, 실패·복구 결과를 바꾸는 판단은 "
            f"state_transitions.usecase_ids에 함께 연결하세요: {usecase_id} / {usecase.get('name', '')}"
        )
    return errors


def system_usecase_affects_state_flow(text: object) -> bool:
    normalized = normalize_space(text)
    if not normalized:
        return False
    has_system_anchor = is_system_actor_name(normalized) or any(
        keyword in normalized for keyword in STATE_IMPACT_SYSTEM_USECASE_ANCHORS
    )
    if not has_system_anchor:
        return False
    return any(keyword in normalized for keyword in STATE_IMPACT_DECISION_KEYWORDS)


def validate_process_critical_links(spec: dict) -> List[str]:
    usecases = list_items(spec, "usecases")
    processes = list_items(spec, "processes")
    usecase_by_id = {str(usecase.get("id", "")).strip(): usecase for usecase in usecases if str(usecase.get("id", "")).strip()}
    process_usecase_ids = {str(process.get("usecase_id", "")).strip() for process in processes}
    process_count_by_usecase = Counter(str(process.get("usecase_id", "")).strip() for process in processes)
    errors = []
    y_usecase_ids = []
    for usecase in usecases:
        usecase_id = str(usecase.get("id", "")).strip()
        process_target = str(usecase.get("process_target", "")).strip().upper()
        if process_target == "Y" and usecase_id:
            y_usecase_ids.append(usecase_id)
            count = process_count_by_usecase.get(usecase_id, 0)
            if count == 0:
                errors.append(f"Critical Gate: process_target=Y 유즈케이스에 연결된 프로세스가 없습니다: {usecase_id}")
            elif count == 1:
                errors.append(
                    "Critical Gate: process_target=Y 유즈케이스가 프로세스 1개로만 작성되었습니다. "
                    f"유즈케이스가 너무 작은지 확인하고, 시작·판단·처리·결과·예외 중 실제 업무 경계가 드러나도록 분해하세요: {usecase_id}"
                )
            elif count > MAX_PROCESSES_PER_Y_USECASE:
                errors.append(
                    "Critical Gate: process_target=Y 유즈케이스에 프로세스가 과도하게 집중되었습니다. "
                    "절차 단계로 잘게 쪼개지는 것은 피하되, 고객·운영자의 목표가 실제로 달라지는 경우에는 유즈케이스를 분리하세요: "
                    f"{usecase_id} / {count}개"
                )
    if (
        len(y_usecase_ids) >= 4
        and processes
        and all(process_count_by_usecase.get(usecase_id, 0) == 1 for usecase_id in y_usecase_ids)
    ):
        errors.append(
            "Critical Gate: 모든 process_target=Y 유즈케이스가 프로세스 1개씩으로만 작성되었습니다. "
            "유즈케이스가 절차 단계처럼 쪼개졌는지 확인하고, 상위 업무 목표별로 묶은 뒤 시작·판단·처리·결과·예외 경계의 프로세스로 분해하세요."
        )
    for process in processes:
        process_id = str(process.get("id", "")).strip()
        usecase_id = str(process.get("usecase_id", "")).strip()
        if usecase_id and usecase_id not in usecase_by_id:
            errors.append(f"Critical Gate: 프로세스 usecase_id가 유즈케이스 목록에 없습니다: {process_id} / {usecase_id}")
            continue
        linked_usecase = usecase_by_id.get(usecase_id, {})
        if str(linked_usecase.get("process_target", "")).strip().upper() == "N":
            errors.append(f"Critical Gate: process_target=N 유즈케이스가 독립 프로세스로 작성되었습니다: {process_id} / {usecase_id}")
    return errors


def validate_function_critical_links(spec: dict) -> List[str]:
    processes = list_items(spec, "processes")
    functions = list_items(spec, "functions")
    process_ids = {str(process.get("id", "")).strip() for process in processes if str(process.get("id", "")).strip()}
    function_names = {str(function.get("name", "")).strip() for function in functions if str(function.get("name", "")).strip()}
    function_names_by_id = {
        str(function.get("id", "")).strip(): str(function.get("name", "")).strip()
        for function in functions
        if str(function.get("id", "")).strip()
    }
    errors = []
    for function in functions:
        function_id = str(function.get("id", "")).strip()
        linked_process_ids = function_process_ids(function)
        if not linked_process_ids:
            errors.append(f"Critical Gate: 기능 process_id/process_ids가 비어 있습니다: {function_id}")
        for process_id in linked_process_ids:
            if process_id not in process_ids:
                errors.append(f"Critical Gate: 기능 process_id가 프로세스 목록에 없습니다: {function_id} / {process_id}")
        details = function.get("details", [])
        if not isinstance(details, list) or len([item for item in details if str(item).strip()]) < 2:
            errors.append(f"Critical Gate: 기능 세부 기능 구성이 2개 미만입니다: {function_id}")
        for detail in details if isinstance(details, list) else []:
            if function_detail_item_is_sentence_like(detail):
                errors.append(f"Critical Gate: 기능 세부 기능 구성은 설명문이 아니라 짧은 하위 처리명이어야 합니다: {function_id} / {detail}")
    for process in processes:
        process_id = str(process.get("id", "")).strip()
        if process_id and not nonempty_list(process.get("related_functions")):
            errors.append(f"Critical Gate: 기능 작성 후 프로세스 관련 기능이 연결되지 않았습니다: {process_id}")
        for function_ref in process.get("related_functions", []) if isinstance(process.get("related_functions"), list) else []:
            function_id, function_name = split_function_reference(function_ref)
            if function_id:
                expected_name = function_names_by_id.get(function_id)
                if expected_name is None:
                    errors.append(f"Critical Gate: 프로세스 관련 기능 ID가 기능 목록에 없습니다: {process_id} / {function_id}")
                elif function_name and function_name != expected_name:
                    errors.append(f"Critical Gate: 프로세스 관련 기능명이 기능 ID와 일치하지 않습니다: {process_id} / {function_ref}")
            elif str(function_ref).strip() in function_names:
                errors.append(f"Critical Gate: 프로세스 관련 기능은 기능 ID로 연결해야 합니다: {process_id} / {function_ref}")
            else:
                errors.append(f"Critical Gate: 프로세스 관련 기능명이 기능 목록에 없습니다: {process_id} / {function_ref}")
    return errors


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


def validate_full_process_details(spec: dict) -> List[str]:
    processes = list_items(spec, "processes")
    details = list_items(spec, "process_details")
    process_ids = {str(process.get("id", "")).strip() for process in processes if str(process.get("id", "")).strip()}
    process_names_by_id = {
        str(process.get("id", "")).strip(): str(process.get("name", "")).strip()
        for process in processes
        if str(process.get("id", "")).strip()
    }
    function_names_by_id = {
        str(function.get("id", "")).strip(): str(function.get("name", "")).strip()
        for function in list_items(spec, "functions")
        if str(function.get("id", "")).strip()
    }
    policy_names_by_id = {
        str(group.get("id", "")).strip(): str(group.get("name", "")).strip()
        for group in list_items(spec, "policy_groups")
        if str(group.get("id", "")).strip()
    }
    detail_by_process = {
        str(detail.get("process_id", "")).strip(): detail
        for detail in details
        if str(detail.get("process_id", "")).strip()
    }
    errors: List[str] = []
    if processes and not details:
        return ["Critical Gate: Full 버전 프로세스 상세가 없습니다."]
    for process_id in sorted(process_ids - set(detail_by_process)):
        errors.append(f"Critical Gate: Full 버전 프로세스 상세가 누락되었습니다: {process_id}")
    for process_id, detail in detail_by_process.items():
        if process_id not in process_ids:
            errors.append(f"Critical Gate: 프로세스 상세 process_id가 프로세스 목록에 없습니다: {process_id}")
            continue
        for field in ("entry_condition", "exit_condition"):
            if is_empty_or_tbd(detail.get(field, "")):
                errors.append(f"Critical Gate: 프로세스 상세 {field}가 비어 있습니다: {process_id}")
        if normalize_space(detail.get("entry_condition", "")) == normalize_space(detail.get("exit_condition", "")):
            errors.append(f"Critical Gate: 프로세스 상세 진입 조건과 종료 조건이 동일합니다: {process_id}")
        for field in ("previous_processes", "next_processes", "related_functions", "related_policies"):
            if not nonempty_list(detail.get(field)):
                errors.append(f"Critical Gate: 프로세스 상세 {field}가 비어 있습니다: {process_id}")
        errors.extend(validate_process_flow_refs(detail.get("previous_processes", []), process_ids, process_names_by_id, "선행 프로세스", process_id))
        errors.extend(validate_process_flow_refs(detail.get("next_processes", []), process_ids, process_names_by_id, "후행 프로세스", process_id))
        errors.extend(validate_named_refs(detail.get("related_functions", []), function_names_by_id, split_function_reference, "관련 기능", process_id))
        errors.extend(validate_named_refs(detail.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", process_id))
    errors.extend(validate_repeated_full_process_detail_phrases(details))
    return errors


def validate_full_function_details(spec: dict) -> List[str]:
    functions = list_items(spec, "functions")
    details = list_items(spec, "function_details")
    function_ids = {str(function.get("id", "")).strip() for function in functions if str(function.get("id", "")).strip()}
    policy_names_by_id = {
        str(group.get("id", "")).strip(): str(group.get("name", "")).strip()
        for group in list_items(spec, "policy_groups")
        if str(group.get("id", "")).strip()
    }
    detail_by_function = {
        str(detail.get("function_id", "")).strip(): detail
        for detail in details
        if str(detail.get("function_id", "")).strip()
    }
    errors: List[str] = []
    if functions and not details:
        return ["Critical Gate: Full 버전 기능 상세가 없습니다."]
    for function_id in sorted(function_ids - set(detail_by_function)):
        errors.append(f"Critical Gate: Full 버전 기능 상세가 누락되었습니다: {function_id}")
    required_fields = (
        "input_information",
        "processing_logic",
        "sub_functions",
        "output_information",
        "failure_exception_cases",
        "related_policies",
    )
    for function_id, detail in detail_by_function.items():
        if function_id not in function_ids:
            errors.append(f"Critical Gate: 기능 상세 function_id가 기능 목록에 없습니다: {function_id}")
            continue
        for field in required_fields:
            if not nonempty_list(detail.get(field)):
                errors.append(f"Critical Gate: 기능 상세 {field}가 비어 있습니다: {function_id}")
        for sub_function in detail.get("sub_functions", []) if isinstance(detail.get("sub_functions"), list) else []:
            if function_detail_item_is_sentence_like(sub_function):
                errors.append(f"Critical Gate: 기능 상세 sub_functions는 설명문이 아니라 짧은 하위 처리명이어야 합니다: {function_id} / {sub_function}")
        processing_logic = detail.get("processing_logic", [])
        if isinstance(processing_logic, list):
            logic_lines = [normalize_space(item) for item in processing_logic if normalize_space(item)]
            if logic_lines and len(logic_lines) < 3:
                errors.append(f"Critical Gate: 기능 상세 processing_logic은 정상·분기·예외를 구분할 수 있도록 최소 3개 이상 작성해야 합니다: {function_id}")
            for line in logic_lines:
                if not function_processing_logic_is_state_action_result(line):
                    errors.append(
                        "Critical Gate: 기능 상세 processing_logic은 샘플처럼 "
                        f"'(상태) ... → (액션) ... → (결과) ...' 형식이어야 합니다: {function_id} / {line}"
                    )
        errors.extend(validate_named_refs(detail.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", function_id))
    errors.extend(validate_repeated_full_function_detail_phrases(details))
    return errors


def validate_policy_critical_links(spec: dict) -> List[str]:
    processes = list_items(spec, "processes")
    groups = list_items(spec, "policy_groups")
    details = list_items(spec, "policy_details")
    policy_names = {str(group.get("name", "")).strip() for group in groups if str(group.get("name", "")).strip()}
    policy_ids = {str(group.get("id", "")).strip() for group in groups if str(group.get("id", "")).strip()}
    policy_name_by_id = {
        str(group.get("id", "")).strip(): str(group.get("name", "")).strip()
        for group in groups
        if str(group.get("id", "")).strip()
    }
    detail_policy_ids = {str(detail.get("policy_id", "")).strip() for detail in details if str(detail.get("policy_id", "")).strip()}
    errors = []
    for process in processes:
        process_id = str(process.get("id", "")).strip()
        if process_id and not nonempty_list(process.get("related_policies")):
            errors.append(f"Critical Gate: 정책 작성 후 프로세스 관련 정책이 연결되지 않았습니다: {process_id}")
        for policy_ref in process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []:
            policy_id, policy_name = split_policy_reference(policy_ref)
            if policy_id:
                expected_name = policy_name_by_id.get(policy_id, "")
                if not expected_name:
                    errors.append(f"Critical Gate: 프로세스 관련 정책 ID가 정책 목록에 없습니다: {process_id} / {policy_id}")
                elif policy_name and policy_name != expected_name:
                    errors.append(f"Critical Gate: 프로세스 관련 정책명이 정책 ID와 일치하지 않습니다: {process_id} / {policy_ref}")
            elif str(policy_ref).strip() not in policy_names:
                errors.append(f"Critical Gate: 프로세스 관련 정책명이 정책 목록에 없습니다: {process_id} / {policy_ref}")
    for policy_id in sorted(policy_ids - detail_policy_ids):
        errors.append(f"Critical Gate: 정책 그룹에 연결된 정책 상세가 없습니다: {policy_id}")
    for detail in details:
        detail_id = str(detail.get("id", "")).strip()
        policy_id = str(detail.get("policy_id", "")).strip()
        if policy_id and policy_id not in policy_ids:
            errors.append(f"Critical Gate: 정책 상세 policy_id가 정책 그룹에 없습니다: {detail_id} / {policy_id}")
        content = str(detail.get("content", ""))
        for phrase in FORBIDDEN_POLICY_PHRASES:
            if phrase in content:
                errors.append(f"Critical Gate: 정책 상세에 금지 표현이 있습니다: {detail_id} / {phrase}")
    return errors


def split_policy_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(PG-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def validate_policy_specificity(spec: dict) -> List[str]:
    details = list_items(spec, "policy_details")
    if not details:
        return []
    errors = []
    generic_names = sum(
        1
        for detail in details
        if any(keyword in str(detail.get("name", "")) for keyword in ("적용 기준", "예외 기준", "이력 기준", "기본 적용 기준"))
    )
    if len(details) >= 20 and generic_names / len(details) >= 0.65:
        errors.append("Critical Gate: 정책 상세명이 적용 기준/예외 기준/이력 기준 중심으로 반복되어 실제 판단축이 드러나지 않습니다.")
    boilerplate = sum(
        1
        for detail in details
        if "고객 상태, 인증 결과, 동의 여부, 연계 시스템 응답" in str(detail.get("content", ""))
        or "고객 영향도를 기준으로 재시도, 상담 전환, 운영 확인" in str(detail.get("content", ""))
    )
    if boilerplate >= 5:
        errors.append(f"Critical Gate: 정책 상세 {boilerplate}건이 공통 템플릿 문구로 반복되어 정책값과 제한 기준이 약합니다.")
    weak_details = [
        str(detail.get("id", "")).strip() or str(detail.get("name", "")).strip()
        for detail in details
        if not policy_detail_has_decision_criteria(detail)
    ]
    weak_threshold = max(5, int(len(details) * 0.4))
    if len(details) >= 8 and len(weak_details) >= weak_threshold:
        errors.append(
            "Critical Gate: 정책 상세에 실제 판단 기준(값, 조건, 횟수, 시간, 제한, 허용, 예외, 고지, 이력 기준)이 부족합니다: "
            + ", ".join(weak_details[:8])
        )
    errors.extend(validate_policy_style_density(spec))
    return errors


def validate_policy_style_density(spec: dict) -> List[str]:
    details = list_items(spec, "policy_details")
    if len(details) < 12:
        return []
    errors: List[str] = []
    dimension_names = [
        dimension
        for detail in details
        for dimension in policy_detail_quality_dimensions(detail)
    ]
    unique_dimensions = set(dimension_names)
    if len(details) >= 16 and len(unique_dimensions) < 4:
        errors.append(
            "Critical Gate: 정책 상세의 판단 차원이 좁습니다. 허용/제한/횟수/시간/상태/예외/고지/이력/BSS 기준 중 여러 축으로 분리해야 합니다."
        )
    repeated_prefixes: dict[str, int] = {}
    for detail in details:
        prefix = normalize_policy_sentence_prefix(detail.get("content", ""))
        if prefix:
            repeated_prefixes[prefix] = repeated_prefixes.get(prefix, 0) + 1
    repeated = [prefix for prefix, count in repeated_prefixes.items() if count >= 5]
    if repeated:
        errors.append("Critical Gate: 정책 상세 문장이 같은 패턴으로 반복되어 샘플 정책서 수준의 밀도가 부족합니다.")
    return errors


def policy_detail_has_decision_criteria(detail: Mapping[str, object]) -> bool:
    content = str(detail.get("content", "") or "").strip()
    if not content:
        return False
    if any(pattern.search(content) for pattern in WEAK_POLICY_CONTENT_PATTERNS):
        return False
    dimensions = policy_detail_quality_dimensions(detail)
    has_criteria = bool(dimensions) or bool(POLICY_DECISION_CRITERIA_PATTERN.search(content))
    has_weak_marker = any(marker in content for marker in WEAK_POLICY_DETAIL_MARKERS)
    if has_weak_marker and not dimensions:
        return False
    return has_criteria


def policy_detail_quality_dimensions(detail: Mapping[str, object]) -> List[str]:
    """Classify whether a policy item contains implementation-grade decision axes."""
    text = " ".join(
        str(value or "")
        for value in (
            detail.get("name", ""),
            detail.get("content", ""),
        )
    )
    if any(pattern.search(text) for pattern in WEAK_POLICY_CONTENT_PATTERNS):
        return []
    return [
        dimension
        for dimension, pattern in POLICY_DETAIL_DIMENSION_PATTERNS.items()
        if pattern.search(text)
    ]


def normalize_policy_sentence_prefix(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) < 24:
        return ""
    text = re.sub(r"\d+", "0", text)
    return text[:32]


def validate_topic_specific_coverage(spec: dict) -> List[str]:
    topic = re.sub(r"\s+", "", str(spec.get("meta", {}).get("topic", "")))
    axes = topic_required_axes(topic)
    if not axes:
        return []
    text = "\n".join(spec_text_values(spec))
    missing = [label for label, keywords in axes if not any(keyword in text for keyword in keywords)]
    if len(missing) >= 2:
        return [f"Critical Gate: 주제별 필수 판단축이 부족합니다: {', '.join(missing)}"]
    return []


def validate_blueprint_grounding(spec: dict) -> List[str]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), dict) else {}
    if not blueprint:
        return []
    bp_meta = blueprint.get("meta", {}) if isinstance(blueprint.get("meta"), dict) else {}
    requirements_count = int(bp_meta.get("requirements_count", 0) or 0)
    errors = []
    if requirements_count > 0:
        coverage_matrix = blueprint.get("coverage_matrix", [])
        if not isinstance(coverage_matrix, list) or not coverage_matrix:
            errors.append("Critical Gate: Authoring Blueprint에 요구사항 coverage_matrix가 없습니다.")
        evidence_ids = blueprint_referenced_evidence_ids(spec)
        if not any(evidence_id.startswith("REQ-") for evidence_id in evidence_ids):
            errors.append("Critical Gate: 작성 결과 trace_matrix/context_pack에 요구사항 근거(REQ-)가 연결되지 않았습니다.")
        missing_requirements = uncovered_requirement_ids(coverage_matrix, evidence_ids)
        if missing_requirements:
            errors.append(
                "Critical Gate: 요구사항 근거가 최종 산출물 trace_matrix/context_pack에 연결되지 않았습니다: "
                + ", ".join(missing_requirements[:10])
            )
        policy_targets = [
            row
            for row in coverage_matrix
            if isinstance(row, dict) and "policies" in (row.get("target_stages") or [])
        ]
        if policy_targets and not list_items(spec, "policy_details"):
            errors.append("Critical Gate: 정책 반영 대상 요구사항이 있으나 정책 상세가 없습니다.")
    return errors


def validate_open_inspector_issues(spec: dict) -> List[str]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    issues = meta.get("open_inspector_issues", [])
    if not isinstance(issues, list) or not issues:
        return []
    blocking = [
        issue
        for issue in issues
        if isinstance(issue, dict)
        and str(issue.get("risk_tier", "")).strip().lower() != "log-only"
        and str(issue.get("severity", "")).strip().lower() in {"error", "critical", "major"}
    ]
    if not blocking:
        return []
    labels = []
    for issue in blocking[:8]:
        chapter = str(issue.get("chapter", "") or issue.get("stage", "") or "").strip()
        title = str(issue.get("title", "") or issue.get("detail", "") or "Inspector 미해결 이슈").strip()
        labels.append(f"{chapter}:{title}" if chapter else title)
    return ["Critical Gate: Inspector 미해결 이슈가 남아 있습니다: " + ", ".join(labels)]


def uncovered_requirement_ids(coverage_matrix: object, evidence_ids: set[str]) -> List[str]:
    if not isinstance(coverage_matrix, list):
        return []
    missing = []
    for row in coverage_matrix:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id", "") or row.get("id", "")).strip()
        source_number = str(row.get("source_number", "")).strip()
        if not requirement_id:
            continue
        if not requirement_id_has_evidence(requirement_id, evidence_ids, source_number=source_number):
            missing.append(requirement_id)
    return dedupe(missing)


def requirement_id_has_evidence(requirement_id: str, evidence_ids: set[str], *, source_number: str = "") -> bool:
    key = normalize_trace_key(requirement_id)
    source_key = normalize_trace_key(source_number)
    if not key:
        return False
    for evidence_id in evidence_ids:
        if not evidence_id.startswith("REQ-"):
            continue
        evidence_key = normalize_trace_key(evidence_id.removeprefix("REQ-"))
        if key == evidence_key or key in evidence_key:
            return True
        if source_key and source_key in evidence_key:
            return True
    return False


def normalize_trace_key(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()


def blueprint_referenced_evidence_ids(spec: dict) -> set[str]:
    ids: set[str] = set()
    for row in spec.get("trace_matrix", []) if isinstance(spec.get("trace_matrix"), list) else []:
        if not isinstance(row, dict):
            continue
        for evidence_id in row.get("evidence_ids", []) if isinstance(row.get("evidence_ids"), list) else []:
            if str(evidence_id).strip():
                ids.add(str(evidence_id).strip())
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    for run in meta.get("context_pack_runs", []) if isinstance(meta.get("context_pack_runs"), list) else []:
        if not isinstance(run, dict):
            continue
        for evidence_id in run.get("evidence_ids", []) if isinstance(run.get("evidence_ids"), list) else []:
            if str(evidence_id).strip():
                ids.add(str(evidence_id).strip())
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), dict) else {}
    chapters = blueprint.get("chapter_blueprints", []) if isinstance(blueprint.get("chapter_blueprints"), list) else []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        for requirement_id in chapter.get("target_requirement_ids", []) if isinstance(chapter.get("target_requirement_ids"), list) else []:
            text = str(requirement_id).strip()
            if text:
                ids.add(text if text.startswith("REQ-") else f"REQ-{text}")
    return ids


def check_list(spec: dict, key: str, allow_empty: bool = False) -> List[str]:
    if key not in spec:
        return []
    if not isinstance(spec[key], list):
        return [f"{key}는 배열이어야 합니다."]
    if not allow_empty and key not in {"history"} and not spec[key]:
        return [f"{key}는 비어 있을 수 없습니다."]
    return []


def scope_rank(scope: str) -> int:
    ranks = {
        "01_overview": 1,
        "overview": 1,
        "02_terms": 2,
        "terms": 2,
        "03_actors": 3,
        "actors": 3,
        "04_usecases": 4,
        "usecases": 4,
        "05_usecase_diagram": 5,
        "usecase_diagram": 5,
        "06_state": 6,
        "state": 6,
        "07_process": 7,
        "process": 7,
        "08_functions": 8,
        "functions": 8,
        "09_policies": 9,
        "policies": 9,
        "09_process_detail": 9,
        "process_detail": 9,
        "09_function_detail": 9,
        "function_detail": 9,
        "09_terms_refinement": 2,
        "terms_refinement": 2,
        "10_final_check": 0,
        "final_check": 0,
        "full": 10,
    }
    return ranks.get(str(scope), 10)


def list_items(spec: dict, key: str) -> List[dict]:
    value = spec.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def policy_detail_items(spec: dict) -> List[dict]:
    """Return policy detail items regardless of flat or grouped payload shape."""
    raw_details = spec.get("policy_details", [])
    if not isinstance(raw_details, list):
        return []
    details: List[dict] = []
    for detail in raw_details:
        if not isinstance(detail, dict):
            continue
        raw_items = detail.get("items")
        if isinstance(raw_items, list):
            policy_id = detail.get("policy_id", "")
            policy_name = detail.get("policy_name", "")
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                normalized = dict(item)
                normalized.setdefault("policy_id", policy_id)
                normalized.setdefault("policy_name", policy_name)
                details.append(normalized)
            continue
        details.append(detail)
    return details


def is_full_template(spec: dict) -> bool:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), dict) else {}
    return str(meta.get("template_type", "")).strip().casefold() == "full"


def nonempty_list(value: object) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def nonempty_text_or_list(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return nonempty_list(value)


def function_detail_item_is_sentence_like(value: object) -> bool:
    text = normalize_space(value)
    if not text:
        return False
    return text.endswith(".") or bool(FUNCTION_DETAIL_SENTENCE_PATTERN.search(text))


def is_step_like_usecase_name(name: object) -> bool:
    text = normalize_space(name)
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return False
    if is_composite_business_usecase_name(text):
        return False
    exact_step_names = {
        "대상확인",
        "조건확인",
        "가능여부확인",
        "유형선택",
        "정보입력",
        "요청정보입력",
        "처리요청",
        "요청접수",
        "약관동의",
        "최종확인",
        "본인확인",
        "본인인증",
        "인증",
        "복귀",
        "사유확인",
        "차단사유확인",
        "제한사유확인",
        "완료",
        "완료확인",
        "처리완료",
        "결과확인",
        "결과안내",
        "후속조치",
    }
    if compact in exact_step_names:
        return True
    step_phrases = (
        "대상 확인",
        "조건 확인",
        "가능 여부",
        "유형 선택",
        "정보 입력",
        "요청 정보",
        "처리 요청",
        "요청 접수",
        "약관 동의",
        "최종 확인",
        "사유 확인",
        "차단 사유",
        "제한 사유",
        "결과 확인",
        "결과 안내",
        "후속 조치",
        "요청 및 결과 확인",
    )
    auth_step_phrases = (
        "본인인증",
        "본인확인",
        "추가인증",
        "재인증",
        "명의인증",
        "회선인증",
        "카드인증",
        "계좌인증",
        "인증번호",
        "인증결과",
        "인증상태",
        "인증복귀",
        "인증완료",
        "인증수행",
    )
    return any(phrase in text for phrase in step_phrases) or any(phrase in compact for phrase in auth_step_phrases)


def is_composite_business_usecase_name(name: object) -> bool:
    text = normalize_space(name)
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 20 or not re.search(r"(?:\s및\s|/|·|,)", text):
        return False
    business_markers = (
        "가입",
        "탈퇴",
        "신청",
        "변경",
        "해지",
        "취소",
        "주문",
        "결제",
        "환불",
        "배송",
        "반품",
        "교환",
        "상품",
        "서비스",
        "BP",
        "목록",
        "상세",
        "검색",
        "추천",
        "혜택",
        "쿠폰",
        "포인트",
        "이벤트",
        "미션",
        "참여",
        "멤버십",
        "알림",
        "상담",
        "고객센터",
        "매장",
        "인증",
        "연동",
        "공유",
        "관리",
        "등록",
        "검수",
        "승인",
        "데이터",
        "트래킹",
        "청구",
        "수납",
        "약관",
        "동의",
        "개인정보",
        "고객",
        "경험",
        "회원정보",
        "주소록",
    )
    decision_markers = (
        "대상",
        "조건",
        "가능",
        "기준",
        "유형",
        "상태",
        "결과",
        "예외",
        "제한",
        "권한",
        "안내",
        "점검",
        "지원",
        "조회",
        "제공",
        "적용",
        "표준",
        "사전",
        "진입",
        "종료",
        "검증",
        "판정",
        "분기",
        "흐름",
        "처리",
        "이력",
        "고지",
        "회신",
        "확정",
    )
    business_score = sum(1 for marker in business_markers if marker in compact)
    decision_score = sum(1 for marker in decision_markers if marker in compact)
    return business_score >= 1 and decision_score >= 1 and (business_score + decision_score) >= 3


def is_system_actor_name(name: str) -> bool:
    if any(keyword in name for keyword in ("고객", "운영자", "법정대리인", "대리인", "관리자", "상담사")):
        return False
    return any(keyword in name for keyword in ("BSS", "시스템", "기관", "연계", "엔진", "외부", "제휴사", "배송사", "결제기관"))


def is_human_actor_name(name: str) -> bool:
    return any(keyword in name for keyword in ("고객", "운영자", "법정대리인", "대리인", "관리자", "상담사")) and not is_system_actor_name(name)


CUSTOMER_CONDITION_ACTOR_PATTERNS = (
    re.compile(r"(로그인|비로그인|정상|제한|휴면|미성년|성인|VIP|우수|일반|신규|기존|개인|법인)\s*고객"),
    re.compile(r"고객\s*(상태|등급|유형|세그먼트)"),
)
DETAILED_OPERATOR_PREFIXES = (
    "전시",
    "상품",
    "콘텐츠",
    "쿠폰",
    "멤버십",
    "마케팅",
    "이벤트",
    "미션",
    "보상",
    "검색",
    "추천",
    "데이터",
    "태깅",
    "알림",
    "배포",
    "승인",
    "검수승인",
    "정산",
    "카테고리",
    "혜택",
)
ALLOWED_OPERATOR_ACTOR_NAMES = {"운영자", "제휴처 운영자"}
ALLOWED_HUMAN_ACTOR_NAMES = {
    "고객",
    "운영자",
    "상담사",
    "법정대리인",
    "대리인",
    "관리자",
    "품질 검수자",
    "제휴처 운영자",
}
DETAILED_SYSTEM_ACTOR_MARKERS = (
    "AI 검색 엔진",
    "추천 엔진",
    "AI 추천 엔진",
    "상품 마스터",
    "지식 베이스",
    "알림센터",
    "장바구니 시스템",
    "검색 시스템",
    "추천 시스템",
    "상품정보 시스템",
    "혜택 시스템",
    "주문 시스템",
    "재고 시스템",
    "결제 시스템",
    "상담 시스템",
    "데이터 플랫폼",
)
GENERAL_SYSTEM_ACTOR_NAMES = {
    "BSS",
    "인증기관",
    "연계 시스템",
    "채널 업무 시스템",
    "BSS/연계 시스템",
}
COMPOSITE_HUMAN_ACTOR_SEPARATOR_PATTERN = re.compile(
    r"(고객|운영자|상담사|관리자|법정대리인|대리인)\s*(?:/|·|,|및)\s*"
    r"(고객|운영자|상담사|관리자|법정대리인|대리인)"
)


def actor_granularity_violation_reason(name: str) -> str:
    text = normalize_space(name)
    if not text:
        return ""
    if is_composite_human_actor_name(text):
        return "여러 사람 책임 주체를 '/'·'및' 등으로 묶은 복합 액터는 금지합니다. 책임이 같으면 하나의 책임명으로 통합하고, 다르면 별도 액터로 분리하세요."
    for pattern in CUSTOMER_CONDITION_ACTOR_PATTERNS:
        if pattern.search(text):
            return "로그인 여부, 고객 상태, 등급, 세그먼트는 액터가 아니라 상태·권한 조건·정책 상세로 관리해야 합니다."
    if is_detailed_internal_operator_actor(text):
        return "세부 내부 운영 역할은 기본적으로 '운영자'로 통합하고, 역할 차이는 유즈케이스 설명·기능·정책 항목으로 내려 작성해야 합니다."
    if is_detailed_system_actor(text):
        return "세부 엔진·저장소·업무 시스템은 독립 액터보다 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합하는 것이 안전합니다."
    return ""


def is_composite_human_actor_name(name: str) -> bool:
    text = normalize_space(name)
    if not text:
        return False
    return bool(COMPOSITE_HUMAN_ACTOR_SEPARATOR_PATTERN.search(text))


def is_detailed_internal_operator_actor(name: str) -> bool:
    text = normalize_space(name)
    if not text or text in ALLOWED_OPERATOR_ACTOR_NAMES:
        return False
    if "운영자" not in text and "관리자" not in text:
        return False
    if text in ALLOWED_HUMAN_ACTOR_NAMES:
        return False
    if "제휴처" in text:
        return False
    return any(prefix in text for prefix in DETAILED_OPERATOR_PREFIXES)


def is_detailed_system_actor(name: str) -> bool:
    text = normalize_space(name)
    if not text or text in GENERAL_SYSTEM_ACTOR_NAMES:
        return False
    if "·BSS 연계 시스템" in text or "/BSS 연계 시스템" in text:
        return False
    if text.endswith("연계 시스템") and "BSS" in text:
        return False
    return any(marker in text for marker in DETAILED_SYSTEM_ACTOR_MARKERS)


def split_function_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(FN-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def validate_named_refs(
    values: object,
    names_by_id: Mapping[str, str],
    splitter,
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"Critical Gate: {owner_id}의 {label}은 배열이어야 합니다."]
    known_names = {name for name in names_by_id.values() if name}
    errors: List[str] = []
    for value in values:
        text = normalize_space(value)
        if not text:
            continue
        ref_id, ref_name = splitter(text)
        if not ref_id:
            if text in known_names:
                errors.append(f"Critical Gate: {owner_id}의 {label}은 ID와 명칭을 함께 작성해야 합니다: {text}")
            else:
                errors.append(f"Critical Gate: {owner_id}의 {label}이 목록에 없습니다: {text}")
            continue
        expected_name = names_by_id.get(ref_id)
        if not expected_name:
            errors.append(f"Critical Gate: {owner_id}의 {label} ID가 목록에 없습니다: {ref_id}")
        elif normalize_space(ref_name) != normalize_space(expected_name):
            errors.append(f"Critical Gate: {owner_id}의 {label} 명칭이 ID와 일치하지 않습니다: {text}")
    return errors


def validate_process_flow_refs(
    values: object,
    process_ids: set[str],
    process_names_by_id: Mapping[str, str],
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"Critical Gate: {owner_id}의 {label}은 배열이어야 합니다."]
    known_names = {name for name in process_names_by_id.values() if name}
    allowed_texts = {"-", "없음", "업무 진입 조건 충족", "결과 안내 또는 후속 업무 연결"}
    errors: List[str] = []
    for value in values:
        text = normalize_space(value)
        if not text or text in allowed_texts:
            continue
        match = re.match(r"^(PR-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
        if match:
            process_id = match.group(1).strip()
            process_name = normalize_space(match.group(2))
            expected_name = normalize_space(process_names_by_id.get(process_id, ""))
            if process_id not in process_ids:
                errors.append(f"Critical Gate: {owner_id}의 {label} ID가 프로세스 목록에 없습니다: {process_id}")
            elif process_id == owner_id:
                errors.append(f"Critical Gate: {owner_id}의 {label}이 자기 자신을 참조합니다.")
            elif process_name and process_name != expected_name:
                errors.append(f"Critical Gate: {owner_id}의 {label} 명칭이 프로세스 ID와 일치하지 않습니다: {text}")
            continue
        if text not in known_names:
            errors.append(f"Critical Gate: {owner_id}의 {label}이 프로세스 목록에 없습니다: {text}")
    return errors


def validate_repeated_full_process_detail_phrases(details: Sequence[Mapping[str, object]]) -> List[str]:
    if len(details) < 8:
        return []
    errors: List[str] = []
    for field, label in (("entry_condition", "진입 조건"), ("exit_condition", "종료 조건")):
        values = [normalize_space(detail.get(field, "")) for detail in details if normalize_space(detail.get(field, ""))]
        repeated = max((values.count(value) for value in set(values)), default=0)
        if repeated >= max(4, int(len(details) * 0.35)):
            errors.append(f"Critical Gate: Full 프로세스 상세 {label}이 {repeated}건 반복되어 프로세스별 시작/종료 기준이 구분되지 않습니다.")
    return errors


def validate_repeated_full_function_detail_phrases(details: Sequence[Mapping[str, object]]) -> List[str]:
    if len(details) < 8:
        return []
    errors: List[str] = []
    for field, label in (
        ("input_information", "입력 정보"),
        ("processing_logic", "처리 로직"),
        ("output_information", "출력 정보"),
        ("failure_exception_cases", "실패/예외 케이스"),
    ):
        signatures = [
            tuple(normalize_space(item) for item in detail.get(field, []) if normalize_space(item))
            for detail in details
            if isinstance(detail.get(field), list)
        ]
        signatures = [signature for signature in signatures if signature]
        repeated = max((signatures.count(signature) for signature in set(signatures)), default=0)
        if repeated >= max(4, int(len(details) * 0.35)):
            errors.append(f"Critical Gate: Full 기능 상세 {label}이 {repeated}건 동일하게 반복되어 기능별 처리 책임이 구분되지 않습니다.")
    return errors


def function_processing_logic_is_state_action_result(value: object) -> bool:
    return bool(FUNCTION_PROCESSING_LOGIC_PATTERN.search(normalize_space(value)))


def dedupe(values: Sequence[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def spec_text_values(value: object) -> List[str]:
    texts: List[str] = []
    if isinstance(value, dict):
        for item in value.values():
            texts.extend(spec_text_values(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(spec_text_values(item))
    elif isinstance(value, str):
        texts.append(value)
    return texts


def topic_required_axes(compact_topic: str) -> List[tuple[str, tuple[str, ...]]]:
    # Topic-specific axes must come from requirements/evidence, not hardcoded branches.
    return []


def validate_id_pattern(items: object, label: str, field: str, pattern: str) -> List[str]:
    if not isinstance(items, list):
        return []
    regex = re.compile(pattern)
    errors = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"{label} #{index} 항목은 객체여야 합니다.")
            continue
        value = str(item.get(field, ""))
        if not regex.match(value):
            errors.append(f"{label} 형식이 올바르지 않습니다: {value}")
    return errors


def validate_unique_ids(spec: dict, keys: Iterable[str]) -> List[str]:
    errors = []
    for key in keys:
        values = []
        items = policy_detail_items(spec) if key == "policy_details" else (
            spec.get(key, []) if isinstance(spec.get(key), list) else []
        )
        for item in items:
            if isinstance(item, dict) and item.get("id"):
                values.append(str(item["id"]))
        duplicates = sorted({value for value in values if values.count(value) > 1})
        for value in duplicates:
            errors.append(f"{key}에 중복 ID가 있습니다: {value}")
    return errors


def validate_actor_links(spec: dict, allow_incomplete: bool = False) -> List[str]:
    actors = spec.get("actors", [])
    usecases = spec.get("usecases", [])
    if not isinstance(actors, list) or not isinstance(usecases, list):
        return []
    actor_names = {str(actor.get("name", "")) for actor in actors if isinstance(actor, dict)}
    actor_ids = {str(actor.get("id", "")) for actor in actors if isinstance(actor, dict)}
    allowed = actor_names | actor_ids
    errors = []
    for usecase in usecases:
        if not isinstance(usecase, dict):
            continue
        actor = str(usecase.get("actor", ""))
        if actor not in allowed:
            errors.append(f"유즈케이스의 actor가 actors에 존재하지 않습니다: {usecase.get('id', '')} / {actor}")
    if not allow_incomplete and usecases:
        used = {
            str(usecase.get("actor", ""))
            for usecase in usecases
            if isinstance(usecase, dict) and usecase.get("actor")
        }
        missing = [
            str(actor.get("name", ""))
            for actor in actors
            if isinstance(actor, dict)
            and str(actor.get("name", ""))
            and str(actor.get("name", "")) not in used
            and str(actor.get("id", "")) not in used
        ]
        for actor_name in missing:
            errors.append(f"액터가 유즈케이스에 연결되지 않았습니다: {actor_name}")
    return errors


def validate_usecase_links(spec: dict) -> List[str]:
    usecase_ids = {str(item.get("id", "")) for item in spec.get("usecases", []) if isinstance(item, dict)}
    errors = []
    for process in spec.get("processes", []) if isinstance(spec.get("processes"), list) else []:
        if not isinstance(process, dict):
            continue
        usecase_id = str(process.get("usecase_id", ""))
        if usecase_id and usecase_id not in usecase_ids:
            errors.append(f"프로세스의 usecase_id가 usecases에 존재하지 않습니다: {process.get('id', '')} / {usecase_id}")
    return errors


def validate_process_policy_links(spec: dict, allow_incomplete: bool = False) -> List[str]:
    policy_groups = spec.get("policy_groups", [])
    policy_names = {str(item.get("name", "")) for item in policy_groups if isinstance(item, dict)}
    policy_name_by_id = {
        str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
        for item in policy_groups
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    if allow_incomplete and not policy_names:
        return []
    errors = []
    for process in spec.get("processes", []) if isinstance(spec.get("processes"), list) else []:
        if not isinstance(process, dict):
            continue
        related = process.get("related_policies", [])
        if not isinstance(related, list):
            errors.append(f"프로세스 related_policies는 배열이어야 합니다: {process.get('id', '')}")
            continue
        for policy_ref in related:
            policy_id, policy_name = split_policy_reference(policy_ref)
            if policy_id:
                expected_name = policy_name_by_id.get(policy_id, "")
                if not expected_name:
                    errors.append(f"프로세스의 관련 정책 ID가 policy_groups에 존재하지 않습니다: {process.get('id', '')} / {policy_id}")
                elif policy_name and policy_name != expected_name:
                    errors.append(f"프로세스의 관련 정책명이 정책 ID와 일치하지 않습니다: {process.get('id', '')} / {policy_ref}")
            elif str(policy_ref) not in policy_names:
                errors.append(f"프로세스의 관련 정책명이 policy_groups에 존재하지 않습니다: {process.get('id', '')} / {policy_ref}")
    return errors


def validate_policy_detail_links(spec: dict, allow_incomplete: bool = False) -> List[str]:
    policy_ids = {str(item.get("id", "")) for item in spec.get("policy_groups", []) if isinstance(item, dict)}
    if allow_incomplete and not spec.get("policy_details"):
        return []
    errors = []
    for detail in policy_detail_items(spec):
        if not isinstance(detail, dict):
            continue
        forbidden_process_fields = [key for key in ("process_id", "process_ids", "applicable_processes") if key in detail]
        if forbidden_process_fields:
            errors.append(f"정책 상세에는 프로세스 직접 매핑 필드를 작성하지 않습니다: {detail.get('id', '')} / {', '.join(forbidden_process_fields)}")
        policy_id = str(detail.get("policy_id", ""))
        if policy_id not in policy_ids:
            errors.append(f"정책 상세의 정책 ID가 policy_groups에 존재하지 않습니다: {detail.get('id', '')} / {policy_id}")
    errors.extend(validate_policy_group_items_match_details(spec, allow_incomplete=allow_incomplete))
    return errors


def validate_policy_group_items_match_details(spec: dict, allow_incomplete: bool = False) -> List[str]:
    groups = list_items(spec, "policy_groups")
    details = policy_detail_items(spec)
    if allow_incomplete and (not groups or not details):
        return []

    details_by_policy: dict[str, list[str]] = {}
    for detail in details:
        policy_id = str(detail.get("policy_id", "")).strip()
        name = str(detail.get("name", "")).strip()
        if policy_id and name:
            details_by_policy.setdefault(policy_id, []).append(name)

    errors: List[str] = []
    for group in groups:
        policy_id = str(group.get("id", "")).strip()
        detail_names = details_by_policy.get(policy_id, [])
        if not policy_id or not detail_names:
            continue
        raw_items = group.get("items")
        if not isinstance(raw_items, list):
            errors.append(f"정책 목록 items가 정책 상세명과 연결되지 않았습니다: {policy_id}")
            continue
        item_names = [policy_group_item_name(item) for item in raw_items if policy_group_item_name(item)]
        if not item_names:
            errors.append(f"정책 목록 items가 비어 있습니다: {policy_id}")
            continue
        missing_details = [name for name in detail_names if name not in item_names]
        unknown_items = [name for name in item_names if name not in detail_names]
        if missing_details:
            errors.append(
                f"정책 목록 items에 정책 상세명이 누락되었습니다: {policy_id} / {', '.join(missing_details[:6])}"
            )
        if unknown_items:
            errors.append(
                f"정책 목록 items가 정책 상세명과 일치하지 않습니다: {policy_id} / {', '.join(unknown_items[:6])}"
            )
    return errors


def policy_group_item_name(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("name", "")).strip()
    return str(item).strip()


def validate_policy_detail_content(spec: dict, allow_incomplete: bool = False) -> List[str]:
    details = spec.get("policy_details", [])
    if allow_incomplete and not details:
        return []
    if not isinstance(details, list):
        return ["policy_details는 배열이어야 합니다."]
    errors: List[str] = []
    for detail in policy_detail_items(spec):
        if not isinstance(detail, dict):
            continue
        detail_id = str(detail.get("id", "")).strip()
        if not str(detail.get("name", "")).strip():
            errors.append(f"정책 상세명이 비어 있습니다: {detail_id}")
        if is_empty_or_tbd(detail.get("content", "")):
            errors.append(f"정책 상세 내용이 비어 있습니다: {detail_id}")
    return errors


def is_empty_or_tbd(value: object) -> bool:
    text = str(value or "").strip()
    return not text or text.upper() == "TBD"


def validate_overview(spec: dict, allow_incomplete: bool = False) -> List[str]:
    overview = spec.get("overview", {})
    if not isinstance(overview, dict):
        return ["overview는 객체여야 합니다."]
    errors = []
    for key in ("scope", "principles"):
        if key not in overview:
            errors.append(f"overview.{key}가 없습니다.")
        elif not isinstance(overview[key], list) or (not allow_incomplete and not overview[key]):
            errors.append(f"overview.{key}는 비어 있지 않은 배열이어야 합니다.")
    return errors
