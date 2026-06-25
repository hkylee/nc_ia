"""Policy document Health Check evaluator.

The Health Check is a post-authoring quality scorecard. It intentionally stays
separate from the generation Inspector so users can run it from the document
workspace without changing the authoring pipeline.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

try:
    from runtime_paths import INPUT_ROOT, INSPECTIONS_ROOT
    from pi_agent import evaluate_pi_document_quality
    from policy_graph import query_policy_graph_context
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import INPUT_ROOT, INSPECTIONS_ROOT
    from .pi_agent import evaluate_pi_document_quality
    from .policy_graph import query_policy_graph_context


DEFAULT_RUBRIC_PATH = INPUT_ROOT / "rubrics" / "policy_health_check_rubric.json"
REPORTS_DIR = INSPECTIONS_ROOT
ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:ACT|US|ST|PR|PRC|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
POLICY_DECISION_PATTERN = re.compile(
    r"(\d+|TBD|최대|최소|이상|이하|초과|미만|허용|제한|필수|선택|횟수|회|분|시간|일|개월|만료|보관|저장|고지|예외|우선순위|동의|인증|상태|대상|조건|기한|재시도|불가|가능)"
)
WEAK_POLICY_MARKERS = (
    "시스템 기준에 따름",
    "시스템 기준에 따라",
    "정책에 따라 처리",
    "관련 정책에 따라",
    "필요 시",
    "검토 필요",
    "추후 협의",
    "관련 부서 확인",
)
HEALTH_GATEKEEPER_DIMENSIONS = (
    {
        "id": "GK-1",
        "name": "evidence_specificity",
        "label": "근거 구체성",
        "description": "항목별 판단 근거가 점수와 문서 위치를 설명할 만큼 구체적인가",
    },
    {
        "id": "GK-2",
        "name": "gap_completeness",
        "label": "Gap 완결성",
        "description": "미통과 항목과 필수 Gate 실패가 보완 항목으로 빠짐없이 이어지는가",
    },
    {
        "id": "GK-3",
        "name": "rubric_adherence",
        "label": "루브릭 준수",
        "description": "루브릭의 섹션, 항목, 필수 Gate 구조를 그대로 평가했는가",
    },
    {
        "id": "GK-4",
        "name": "rationale_quality",
        "label": "판단 사유 품질",
        "description": "요약, 주요 Gap, 보완 제안이 검토자가 바로 실행할 수 있는 수준인가",
    },
    {
        "id": "GK-5",
        "name": "internal_consistency",
        "label": "내부 일관성",
        "description": "섹션 점수, 총점, Gate 판정, 종합 판정이 서로 모순되지 않는가",
    },
)

HEALTH_CHECK_TEMPLATE_PROFILES = {
    "simple": {
        "id": "simple",
        "label": "간소화 버전",
        "focus": "간소화 산출물 범위 안에서 개요, 업무 구조, 상태, 프로세스·기능·정책 연결, 요구사항 추적성을 엄격하게 검증합니다.",
        "requiredScope": "개요, 용어, 액터, 유즈케이스, 상태 전이, 프로세스 목록, 기능 목록, 정책 목록·상세, 요구사항 추적",
    },
    "full": {
        "id": "full",
        "label": "Full 버전",
        "focus": "간소화 골격 검증에 더해 프로세스 상세와 기능 상세가 상세 설계 입력 수준인지 검증합니다.",
        "requiredScope": "간소화 범위 전체, 프로세스 상세, 기능 상세, 입력·처리·출력, 실패·예외, 상태-액션-결과 로직",
    },
}


def normalize_health_template_type(template_type: str) -> str:
    value = str(template_type or "").strip().casefold()
    if value in {"full", "full version", "full버전"}:
        return "full"
    return "simple"


def health_check_template_profile(template_type: str) -> Dict[str, str]:
    key = normalize_health_template_type(template_type)
    return dict(HEALTH_CHECK_TEMPLATE_PROFILES[key])


def evaluate_health_check(
    *,
    document: str,
    file_name: str,
    topic: str,
    template_type: str,
    llm_client: object | None = None,
    rubric_path: Path = DEFAULT_RUBRIC_PATH,
    recheck_item_ids: Optional[List[str]] = None,
    previous_report: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    template_key = normalize_health_template_type(template_type)
    profile = health_check_template_profile(template_key)
    rubric = load_health_check_rubric(rubric_path)
    signals = extract_health_signals(document, topic=topic, template_type=template_key)
    signals["policy_graph_context"] = query_policy_graph_context(topic=topic, stage="final_check", limit=30)
    sections = score_sections(rubric, signals)
    evaluation_mode = "code"
    llm_error = ""

    if llm_client is not None and getattr(llm_client, "enabled", False) and getattr(llm_client, "writer_mode", "") != "mock":
        try:
            llm_report = run_llm_health_check(
                llm_client=llm_client,
                rubric=rubric,
                document_text=signals["text_preview"],
                signals=signals,
                topic=topic,
                template_type=template_key,
            )
            sections = merge_llm_scores(sections, llm_report)
            evaluation_mode = "hybrid"
        except Exception as exc:  # pragma: no cover - defensive LLM fallback.
            llm_error = str(exc)

    recheck_ids = normalize_recheck_item_ids(recheck_item_ids)
    if recheck_ids and previous_report:
        sections = merge_selective_recheck_sections(previous_report, sections, recheck_ids)
        evaluation_mode = f"{evaluation_mode}-selective"

    raw_score = sum(int(section["score"]) for section in sections)
    item_scores = {
        item["id"]: int(item["score"])
        for section in sections
        for item in section.get("items", [])
        if isinstance(item, Mapping)
    }
    gates = evaluate_mandatory_gates(rubric, item_scores, signals)
    gate_passed = all(gate["passed"] for gate in gates)
    total_score = apply_gate_score_cap(raw_score, gates)
    judgement = judgement_for_score(rubric, total_score)
    if not gate_passed and judgement in {"우수", "양호"}:
        judgement = "보완 필요"
    low_sections = sorted(sections, key=lambda section: int(section["score"]))[:3]
    action_items = build_health_action_items(sections, gates, signals)
    remediation_plan = build_health_remediation_plan(
        sections=sections,
        gates=gates,
        action_items=action_items,
        previous_report=previous_report,
        recheck_item_ids=recheck_ids,
    )
    summary = build_summary(total_score, judgement, gate_passed, low_sections, evaluation_mode, llm_error, profile)
    report = {
        "agent": "Policy Health Check",
        "rubricId": rubric.get("rubric_id", "policy_health_check"),
        "rubricVersion": rubric.get("version", "1.0"),
        "fileName": file_name,
        "topic": topic,
        "templateType": template_key,
        "templateProfile": profile,
        "evaluationMode": evaluation_mode,
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "score": total_score,
        "rawScore": raw_score,
        "maxScore": int(rubric.get("max_score", 100)),
        "judgement": judgement,
        "mandatoryGatePassed": gate_passed,
        "summary": summary,
        "sections": sections,
        "mandatoryGates": gates,
        "actionItems": action_items,
        "remediationPlan": remediation_plan,
        "signals": compact_signals(signals),
        "llmError": llm_error,
    }
    if recheck_ids:
        report["recheckScope"] = {
            "mode": "failed-items",
            "itemIds": recheck_ids,
            "reusedItemCount": max(0, len(health_check_items(previous_report or {})) - len(recheck_ids)),
        }
    gatekeeper = evaluate_health_gatekeeper(report, rubric=rubric, signals=signals)
    report["gatekeeper"] = gatekeeper
    report["qualityGatePassed"] = bool(gatekeeper.get("passed"))
    apply_health_result_blockers(report)
    report["summary"] = append_gatekeeper_summary(summary, gatekeeper)
    return report


def load_health_check_rubric(path: Path = DEFAULT_RUBRIC_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_health_check_report(report: Mapping[str, Any], *, reports_dir: Path = REPORTS_DIR, file_name: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{file_name}_health_check.json"
    payload = dict(report)
    payload["created_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def extract_health_signals(document: str, *, topic: str = "", template_type: str = "simple") -> Dict[str, Any]:
    template_key = normalize_health_template_type(template_type)
    text = visible_text(document)
    normalized = re.sub(r"\s+", " ", text)
    pi_agent_result = evaluate_pi_document_quality(document, topic=topic)
    state_transition_rows = extract_table_rows_by_headers(document, ("현재 상태", "전이 이벤트", "다음 상태"))
    process_rows = extract_table_rows_by_headers(document, ("프로세스 ID", "관련 기능", "관련 정책"))
    requirement_rows = extract_table_rows_by_headers(document, ("요구사항",))
    policy_item_blocks = extract_policy_item_blocks(document)
    complete_process_rows = [
        row for row in process_rows
        if contains_id_prefix(" ".join(row), "PR") and contains_id_prefix(" ".join(row), "FN") and contains_id_prefix(" ".join(row), "PG")
    ]
    process_with_function_rows = [row for row in process_rows if contains_id_prefix(" ".join(row), "FN")]
    process_with_policy_rows = [row for row in process_rows if contains_id_prefix(" ".join(row), "PG")]
    linked_transition_rows = [
        row for row in state_transition_rows
        if len(row) >= 4 and row[0].strip() and row[1].strip() and row[2].strip() and row[3].strip()
    ]
    quality_policy_items = [
        block for block in policy_item_blocks
        if is_quality_policy_item(block)
    ]
    policy_item_text = " ".join(policy_item_blocks)
    requirements_mapping_count = count_requirements_mapping_rows(requirement_rows)
    if not requirements_mapping_count and has_requirements_trace_statement(normalized):
        requirements_mapping_count = 1
    full_detail_signals = extract_full_detail_signals(document, normalized)
    id_counts = {
        "actors": count_unique_ids(document, "ACT"),
        "usecases": count_unique_ids(document, "US"),
        "states": count_unique_ids(document, "ST"),
        "processes": count_unique_ids(document, "PR"),
        "functions": count_unique_ids(document, "FN"),
        "policies": count_unique_ids(document, "PG"),
        "policy_items": count_unique_ids(document, "PI"),
    }
    id_examples = {
        "actors": unique_ids(document, "ACT")[:3],
        "usecases": unique_ids(document, "US")[:3],
        "states": unique_ids(document, "ST")[:3],
        "processes": unique_ids(document, "PR")[:3],
        "functions": unique_ids(document, "FN")[:3],
        "policies": unique_ids(document, "PG")[:3],
        "policy_items": unique_ids(document, "PI")[:3],
    }
    return {
        "template_type": template_key,
        "template_profile": health_check_template_profile(template_key),
        "text": normalized,
        "text_preview": normalized[:55000],
        "topic": topic,
        "id_counts": id_counts,
        "id_examples": id_examples,
        "state_transition_count": len(state_transition_rows) or count_occurrences(document, ("전이 이벤트", "현재 상태", "다음 상태")),
        "state_transition_linked_event_count": len(linked_transition_rows),
        "process_row_count": len(process_rows),
        "process_complete_mapping_count": len(complete_process_rows),
        "process_function_mapping_count": len(process_with_function_rows),
        "process_policy_mapping_count": len(process_with_policy_rows),
        "requirements_mapping_row_count": requirements_mapping_count,
        **full_detail_signals,
        "policy_item_block_count": len(policy_item_blocks),
        "policy_item_quality_count": len(quality_policy_items),
        "truncated_marker_count": policy_item_text.count("…") + policy_item_text.count("..."),
        "weak_policy_count": sum(policy_item_text.count(marker) for marker in WEAK_POLICY_MARKERS),
        "decision_marker_count": len(POLICY_DECISION_PATTERN.findall(normalized)),
        "id_reference_count": len(ID_PATTERN.findall(document)),
        "has_scope": has_any(normalized, ("가. 범위", "대상 업무", "포함 범위", "제외 범위")),
        "has_exclusion": has_any(normalized, ("제외 범위", "제외한다", "후속 산출물", "상세 설계서")),
        "has_boundary": has_any(normalized, ("정책서 간 경계", "다른 정책서", "타 정책서", "경계")),
        "has_policy_questions": has_any(normalized, ("핵심 정책 질문", "누가", "언제", "몇 번", "어떤 조건", "실패하면")),
        "has_channel_integration": has_any(normalized, ("통합채널", "채널 통합", "앱/웹", "앱·웹", "FO", "BSS")),
        "has_customer_precheck": has_any(normalized, ("처리 가능 여부", "사전", "가능 여부", "조건 확인", "영향도")),
        "has_customer_result": has_any(normalized, ("처리 결과", "결과 확인", "영향", "완료 안내", "결과 회신")),
        "has_self_service": has_any(normalized, ("셀프", "직접 완료", "앱/웹", "앱·웹", "상담 전환")),
        "has_failure_guidance": has_any(normalized, ("실패 사유", "다음 행동", "재시도", "복구", "고객 안내")),
        "has_plain_language": has_any(normalized, ("고객", "안내", "고지", "이해", "용어")),
        "pi_agent": pi_agent_result,
        "has_pi": has_any(normalized, ("중복", "자동화", "일괄", "수작업", "운영자", "효율", "PI"))
        or int(pi_agent_result.get("yes_count", 0)) >= 2,
        "has_process_flow": has_any(normalized, ("시작", "확인", "요청", "반영", "완료", "프로세스")),
        "has_status_distinction": has_any(normalized, ("완료", "실패", "대기", "제한", "보류", "만료")),
        "has_customer_system_status": has_any(normalized, ("고객 표시 상태", "시스템 내부 상태", "내부 상태", "표시 상태")),
        "has_policy_allow_restrict": has_any(normalized, ("허용", "제한", "불가", "가능", "예외")),
        "has_customer_type": has_any(normalized, ("고객 유형", "가입 상태", "권한", "미성년", "법정대리인", "대리인")),
        "has_timing": has_any(normalized, ("시점", "전", "후", "만료", "기한", "유효 시간")),
        "has_fail_cases": has_any(normalized, ("인증 실패", "조회 실패", "결제 실패", "연동 실패", "처리 실패"))
        or has_topic_scoped_failure_case(normalized),
        "has_topic_scoped_failure": has_topic_scoped_failure_case(normalized),
        "has_retry": has_any(normalized, ("재시도", "횟수", "최대", "중복 요청", "멱등")),
        "has_recovery": has_any(normalized, ("복구", "취소", "철회", "재처리", "보정")),
        "has_bss": has_any(normalized, ("BSS", "원장", "상태 변경", "상태 반영", "이력 저장", "결과 회신")),
        "has_external": has_any(normalized, ("외부 시스템", "연계 시스템", "인증기관", "PG", "제휴", "배송사", "분석", "딥링크", "캐시")),
        "has_integration_risk": has_any(normalized, ("장애", "통합 리스크", "영향 확대", "연동 실패", "복잡도")),
        "has_data_input": has_any(normalized, ("입력 데이터", "입력값", "필수", "선택", "출처", "생성 주체")),
        "has_data_processing": has_any(normalized, ("검증", "변환", "처리 기준", "산정", "판정")),
        "has_data_output": has_any(normalized, ("출력 데이터", "생성", "변경", "삭제", "결과")),
        "has_data_retention": has_any(normalized, ("저장", "이력", "보관", "마스킹", "조회")),
        "has_requirements_trace": has_any(normalized, ("요구사항", "매핑", "추적", "신규 도출")),
        "has_dev_qa": has_any(normalized, ("개발", "QA", "테스트", "기대 결과", "검수")),
    }


def score_sections(rubric: Mapping[str, Any], signals: Mapping[str, Any]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    for section in rubric.get("sections", []):
        if not isinstance(section, Mapping):
            continue
        items = [score_item(item, signals) for item in section.get("items", []) if isinstance(item, Mapping)]
        sections.append(
            {
                "id": section.get("id", ""),
                "order": section.get("order", 0),
                "name": section.get("name", ""),
                "score": sum(item["score"] for item in items),
                "maxScore": int(section.get("max_score", 10)),
                "judgement": section_judgement(sum(item["score"] for item in items)),
                "majorGap": first_gap(items),
                "items": items,
            }
        )
    return sections


def score_item(item: Mapping[str, Any], signals: Mapping[str, Any]) -> Dict[str, Any]:
    item_id = str(item.get("id", "")).strip()
    score, evidence, suggestion = local_item_score(item_id, signals)
    return {
        "id": item_id,
        "question": str(item.get("question", "")).strip(),
        "score": score,
        "maxScore": int(item.get("max_score", 2)),
        "evidence": evidence,
        "suggestion": suggestion,
        "relatedLocation": related_location(item_id, signals),
    }


def local_item_score(item_id: str, signals: Mapping[str, Any]) -> tuple[int, str, str]:
    counts = signals.get("id_counts", {}) if isinstance(signals.get("id_counts"), Mapping) else {}
    actor_count = int(counts.get("actors", 0))
    usecase_count = int(counts.get("usecases", 0))
    process_count = int(counts.get("processes", 0))
    function_count = int(counts.get("functions", 0))
    policy_count = int(counts.get("policies", 0))
    policy_item_count = int(counts.get("policy_items", 0))
    transition_count = int(signals.get("state_transition_count", 0))
    linked_transition_count = int(signals.get("state_transition_linked_event_count", 0))
    process_row_count = int(signals.get("process_row_count", 0))
    process_complete_mapping_count = int(signals.get("process_complete_mapping_count", 0))
    process_function_mapping_count = int(signals.get("process_function_mapping_count", 0))
    process_policy_mapping_count = int(signals.get("process_policy_mapping_count", 0))
    requirements_mapping_row_count = int(signals.get("requirements_mapping_row_count", 0))
    policy_item_block_count = int(signals.get("policy_item_block_count", 0))
    policy_item_quality_count = int(signals.get("policy_item_quality_count", 0))
    truncated_count = int(signals.get("truncated_marker_count", 0))
    decision_count = int(signals.get("decision_marker_count", 0))
    weak_count = int(signals.get("weak_policy_count", 0))
    graph = signals.get("policy_graph_context", {}) if isinstance(signals.get("policy_graph_context"), Mapping) else {}
    graph_available = bool(graph.get("available"))
    graph_counts = graph.get("node_counts", {}) if isinstance(graph.get("node_counts"), Mapping) else {}
    graph_requirement_count = int(graph_counts.get("Requirement", 0) or 0)
    graph_coverage_gap_count = int(graph.get("coverage_gap_count", 0) or 0)
    graph_chain_gap_count = int(graph.get("chain_gap_count", 0) or 0)
    graph_trace_ok = graph_available and graph_requirement_count > 0 and graph_coverage_gap_count == 0
    graph_chain_ok = graph_available and graph_chain_gap_count == 0
    pi_agent = signals.get("pi_agent", {}) if isinstance(signals.get("pi_agent"), Mapping) else {}
    pi_check_status = pi_agent_check_status(pi_agent)
    pi_step_reduction = pi_check_status.get("PI-CHECK-01") in {"yes", "partial"} or pi_check_status.get("PI-CHECK-02") == "yes"
    pi_exceptions = pi_check_status.get("PI-CHECK-04") in {"yes", "partial"}
    pi_ssot = pi_check_status.get("PI-CHECK-08") in {"yes", "partial"}
    process_mapping_ratio = ratio(process_complete_mapping_count, process_row_count)
    process_function_ratio = ratio(process_function_mapping_count, process_row_count)
    process_policy_ratio = ratio(process_policy_mapping_count, process_row_count)
    transition_link_ratio = ratio(linked_transition_count, transition_count)
    policy_item_quality_ratio = ratio(policy_item_quality_count, policy_item_block_count or policy_item_count)
    expected_transition_rows = max(3, min(6, max(0, int(counts.get("states", 0)) - 1)))
    template_type = normalize_health_template_type(str(signals.get("template_type", "simple")))
    is_full = template_type == "full"
    full_process_detail_ok = bool(signals.get("has_full_process_detail_scope")) and process_count > 0
    full_function_detail_ok = (
        bool(signals.get("has_full_function_detail_scope"))
        and int(signals.get("full_state_action_result_count", 0) or 0) >= max(2, min(4, function_count or 2))
        and function_count > 0
    )
    full_exception_detail_ok = bool(signals.get("has_full_normal_branch_exception")) and full_function_detail_ok
    full_io_contract_ok = bool(signals.get("has_full_io_contract")) and full_function_detail_ok
    process_flow_strong = process_count >= max(2, usecase_count // 2) and signals["has_process_flow"]
    process_flow_full_strong = process_flow_strong and full_process_detail_ok
    process_to_usecase_strong = (
        (process_count > 0 and usecase_count > 0 and process_mapping_ratio >= 0.8 and graph_chain_gap_count == 0)
        if graph_available
        else (process_count > 0 and usecase_count > 0 and process_mapping_ratio >= 0.8)
    )
    process_to_usecase_full_strong = process_to_usecase_strong and full_process_detail_ok
    function_to_process_strong = (
        (function_count > 0 and process_count > 0 and process_function_ratio >= 0.8 and graph_chain_ok)
        if graph_available
        else (function_count > 0 and process_count > 0 and process_function_ratio >= 0.8)
    )
    function_to_process_full_strong = function_to_process_strong and full_function_detail_ok
    full_detail_evidence = "Full 전용 프로세스 상세와 기능 상세의 입력·처리·출력·예외 기준이 확인됩니다."
    full_detail_suggestion = "Full 버전에서는 프로세스 상세의 진입/종료/선행·후행 조건과 기능 상세의 입력·상태-액션-결과·출력·실패·예외를 보강하세요."

    checks = {
        "1-1": (signals["has_scope"], topic_present(signals), "범위 문단과 주제명이 확인됩니다.", "개요의 범위에 대상 업무, 고객, 채널을 명시하세요."),
        "1-2": (signals["has_scope"] and signals["has_exclusion"], signals["has_exclusion"], "포함/제외 또는 후속 산출물 경계가 확인됩니다.", "포함 범위와 제외 범위를 분리해 작성하세요."),
        "1-3": (signals["has_boundary"], signals["has_exclusion"], "정책서 간 경계 표현이 확인됩니다.", "다른 정책서와 겹치는 범위와 넘기지 않을 범위를 적으세요."),
        "1-4": (signals["has_policy_questions"], decision_count >= 12, "정책 질문 또는 판단 기준 표현이 확인됩니다.", "누가, 언제, 몇 번, 어떤 조건, 실패 시 기준을 질문 형태로 도출하세요."),
        "1-5": (signals["has_channel_integration"], signals["has_bss"], "채널 통합/BSS 관점이 확인됩니다.", "기존 기능 이관이 아니라 통합채널 기준의 처리 기준을 명시하세요."),
        "2-1": (signals["has_customer_precheck"], signals["has_policy_allow_restrict"], "처리 가능 여부 사전 확인 기준이 확인됩니다.", "고객이 신청 전 가능 여부를 알 수 있는 조건을 추가하세요."),
        "2-2": (signals["has_customer_result"], signals["has_status_distinction"], "처리 결과와 영향 확인 기준이 확인됩니다.", "처리 결과, 영향, 고객 안내 기준을 보강하세요."),
        "2-3": (signals["has_self_service"], signals["has_channel_integration"], "앱/웹 셀프 처리 관점이 확인됩니다.", "상담 의존이 아닌 고객 직접 완료 기준을 명시하세요."),
        "2-4": (signals["has_failure_guidance"], signals["has_fail_cases"], "실패 사유와 다음 행동 안내가 확인됩니다.", "실패 사유, 재시도, 복구, 상담 전환 기준을 추가하세요."),
        "2-5": (signals["has_plain_language"], usecase_count > 0, "고객 안내와 용어 정리 관점이 확인됩니다.", "고객이 이해할 수 있는 상태/용어/안내 기준을 보강하세요."),
        "3-1": (process_flow_full_strong if is_full else process_flow_strong, process_count > 0 and (not is_full or signals["has_process_flow"]), full_detail_evidence if is_full else "프로세스가 업무 흐름 단위로 구성됩니다.", full_detail_suggestion if is_full else "유즈케이스를 완료하는 최소 프로세스 흐름을 보강하세요."),
        "3-2": (signals["has_channel_integration"] and signals["has_bss"], signals["has_channel_integration"], "채널과 시스템 흐름 연결이 확인됩니다.", "FO-BSS-외부 시스템 간 단절 지점을 줄이는 흐름을 작성하세요."),
        "3-3": (signals["has_pi"] and ("중복" in signals["text"] or pi_step_reduction or pi_ssot), signals["has_pi"], "중복/수작업 축소 또는 PI 단계 축소 관점이 확인됩니다.", "중복 입력, 중복 인증, 반복 안내 제거 기준과 유지 사유를 추가하세요."),
        "3-4": (signals["has_self_service"] and signals["has_pi"], signals["has_self_service"], "셀프 처리 또는 자동화 전환 관점이 확인됩니다.", "운영자 예외 처리와 상담 의존을 줄이는 기준을 보강하세요."),
        "3-5": (has_any(signals["text"], ("예약", "일괄", "자동 처리")) or pi_exceptions, signals["has_pi"], "예약/일괄/자동 처리 또는 예외 본문화 관점이 확인됩니다.", "반복 업무의 자동 처리, 일괄 처리, 예외 본문화 가능성을 검토하세요."),
        "4-1": (actor_count >= 2 and usecase_count >= 2, actor_count > 0, "액터와 유즈케이스 ID가 확인됩니다.", "실제 책임 주체 기준으로 액터를 정의하세요."),
        "4-2": (usecase_count >= 3 and signals["has_process_flow"], usecase_count > 0, "유즈케이스가 업무 단위로 정의됩니다.", "고객의 시작 목적과 완료 상태가 드러나는 유즈케이스를 보강하세요."),
        "4-3": (process_to_usecase_full_strong if is_full else process_to_usecase_strong, process_count > 0 and usecase_count > 0, "프로세스 목록과 Full 프로세스 상세의 연결이 확인됩니다." if is_full else "프로세스 행에서 관련 기능·정책 ID 연결이 확인됩니다.", "Full 버전에서는 프로세스 상세에 각 프로세스가 유즈케이스를 완성하는 절차인지와 진입/종료/선행·후행/관련 기능·정책을 연결하세요." if is_full else "프로세스가 어떤 유즈케이스를 완성하고 어떤 기능·정책으로 이어지는지 ID 기준으로 연결하세요."),
        "4-4": (function_to_process_full_strong if is_full else function_to_process_strong, function_count > 0, "기능 목록과 Full 기능 상세의 처리 책임이 확인됩니다." if is_full else "프로세스별 관련 기능 ID 연결이 확인됩니다.", "Full 버전에서는 각 기능에 입력 정보, 상태-액션-결과 처리, 출력 정보, 실패·예외, 관련 정책을 상세로 연결하세요." if is_full else "프로세스 수행에 필요한 기능을 처리 역량 기준으로 정의하고 관련 기능 ID를 연결하세요."),
        "4-5": ((policy_count > 0 and policy_item_quality_ratio >= 0.7 and process_policy_ratio >= 0.8 and graph_chain_ok) if graph_available else (policy_count > 0 and policy_item_quality_ratio >= 0.7 and process_policy_ratio >= 0.8), policy_count > 0 and policy_item_count >= policy_count, "정책 항목과 프로세스별 관련 정책 ID 연결이 확인됩니다.", "각 프로세스/기능에 연결되는 정책 ID와 실행 가능한 정책 항목을 보강하세요."),
        "5-1": (counts.get("states", 0) > 0, signals["has_status_distinction"], "상태 코드 또는 상태 표현이 확인됩니다.", "업무 상태 목록을 추가하세요."),
        "5-2": (transition_count >= expected_transition_rows and transition_link_ratio >= 0.5, transition_count >= 3, "상태 전이 행과 전이 이벤트의 유즈케이스/프로세스 연결이 확인됩니다.", "상태 전이 이벤트 컬럼에 관련 유즈케이스 또는 프로세스 ID를 연결하세요."),
        "5-3": (signals["has_status_distinction"], counts.get("states", 0) > 0, "완료/실패/대기/제한 상태 표현이 확인됩니다.", "완료, 실패, 대기, 제한 상태를 구분하세요."),
        "5-4": (signals["has_customer_system_status"], signals["has_status_distinction"], "고객 표시 상태와 내부 상태 구분이 확인됩니다.", "고객 표시 상태와 시스템 내부 상태의 차이를 명시하세요."),
        "5-5": (signals["has_customer_result"] and signals["has_failure_guidance"], signals["has_customer_result"], "상태별 고객 안내/후속 행동이 확인됩니다.", "상태별 안내와 다음 행동 기준을 보강하세요."),
        "6-1": (policy_item_count > 0 and policy_item_quality_ratio >= 0.75, policy_item_count > 0 and decision_count > 0, "정책 항목별 판단 기준 표현이 확인됩니다.", "각 정책 항목에 값, 조건, 횟수, 시간, 상태 중 하나 이상을 구체적으로 넣으세요."),
        "6-2": (signals["has_policy_allow_restrict"], policy_count > 0, "허용/제한 기준이 확인됩니다.", "허용 기준과 제한 기준을 함께 정의하세요."),
        "6-3": (signals["has_customer_type"], policy_count > 0, "고객 유형/권한별 기준이 확인됩니다.", "고객 유형, 권한, 가입 상태별 적용 기준을 보강하세요."),
        "6-4": (signals["has_timing"], policy_count > 0, "시점/기한 기준이 확인됩니다.", "업무 전/중/후, 만료, 기한 기준을 추가하세요."),
        "6-5": (weak_count == 0 and truncated_count == 0 and policy_item_count > 0, weak_count <= 2 and truncated_count <= 2, "빈 정책 표현과 생략 표시가 적거나 없습니다.", "시스템 기준에 따름 같은 빈 정책 표현이나 말줄임표로 끊긴 정책을 실제 판단값으로 바꾸세요."),
        "7-1": (signals["has_fail_cases"] and (not is_full or full_exception_detail_ok), signals["has_failure_guidance"], "Full 기능 상세에서 정상·분기·예외와 실패 케이스가 확인됩니다." if is_full else "주제 범위에 맞는 실패 케이스 표현이 확인됩니다.", "Full 버전에서는 기능 상세의 실패·예외 케이스에 처리 기준, 안내, 중단/재시도 결과를 함께 작성하세요." if is_full else "인증/조회/결제/연동 또는 주제 고유 실패 케이스를 명시하세요."),
        "7-2": (signals["has_retry"], signals["has_fail_cases"], "재시도/횟수 기준이 확인됩니다.", "재시도 가능 여부와 횟수 기준을 추가하세요."),
        "7-3": (signals["has_failure_guidance"], signals["has_fail_cases"], "실패 시 고객 안내 기준이 확인됩니다.", "실패 시 고객 안내 문구와 다음 행동 기준을 보강하세요."),
        "7-4": (signals["has_recovery"] and (not is_full or full_exception_detail_ok), signals["has_fail_cases"], "Full 기능 상세의 예외 처리 결과에 복구/취소/재처리 기준이 확인됩니다." if is_full else "복구/취소/재처리 기준이 확인됩니다.", "Full 버전에서는 예외 상태별 액션과 결과에 복구, 취소, 철회, 재처리 조건을 연결하세요." if is_full else "복구, 취소, 철회, 재처리 조건을 추가하세요."),
        "7-5": (has_any(signals["text"], ("중복 요청", "멱등", "중복 처리")), signals["has_retry"], "중복 요청/멱등성 기준이 확인됩니다.", "중복 요청과 멱등 처리 기준을 보강하세요."),
        "8-1": (signals["has_bss"], policy_count > 0, "BSS 판단/저장/상태 변경 기준이 확인됩니다.", "BSS가 판정, 저장, 상태 변경, 결과 회신해야 하는 항목을 명시하세요."),
        "8-2": (signals["has_bss"] and has_any(signals["text"], ("FO", "책임 경계", "외부 시스템")), signals["has_bss"], "FO/BSS/외부 시스템 책임 표현이 확인됩니다.", "FO, BSS, 외부 시스템 간 책임 경계를 추가하세요."),
        "8-3": (
            (signals["has_external"] or signals["has_bss"]) and signals["has_fail_cases"],
            signals["has_external"] or signals["has_bss"],
            "외부/BSS/분석 연계 실패 처리 관점이 확인됩니다.",
            "외부 시스템, BSS, 분석, 캐시, 딥링크 등 주제 범위의 연계 실패 처리 기준을 보강하세요.",
        ),
        "8-4": (has_any(signals["text"], ("원장", "상태 반영", "이력 저장", "결과 회신")), signals["has_bss"], "원장/상태/이력/회신 기준이 확인됩니다.", "원장 반영, 상태 반영, 이력 저장, 결과 회신 기준을 명시하세요."),
        "8-5": (signals["has_integration_risk"], signals["has_external"] or signals["has_bss"], "통합 리스크 또는 장애 영향 관점이 확인됩니다.", "통합 장애 영향과 채널 간 영향 리스크를 보강하세요."),
        "9-1": (signals["has_data_input"] and (not is_full or full_io_contract_ok), function_count > 0, "Full 기능 상세에서 입력 정보 기준이 확인됩니다." if is_full else "입력 데이터 기준이 확인됩니다.", "Full 버전에서는 기능 상세의 입력 정보에 고객 입력값, 시스템 조회값, 외부 연계 결과, 필수/선택 여부를 작성하세요." if is_full else "업무 수행에 필요한 입력 데이터와 필수/선택 여부를 명시하세요."),
        "9-2": (signals["has_data_input"] and has_any(signals["text"], ("출처", "생성 주체", "필수", "선택")) and (not is_full or full_io_contract_ok), signals["has_data_input"], "Full 기능 상세에서 입력 데이터 출처/주체/필수 여부가 확인됩니다." if is_full else "입력 데이터 출처/주체/필수 여부가 확인됩니다.", "Full 버전에서는 입력 정보에 데이터 출처, 생성 주체, 필수/선택 기준을 명확히 연결하세요." if is_full else "입력 데이터의 출처, 생성 주체, 필수/선택 기준을 보강하세요."),
        "9-3": (signals["has_data_processing"] and (not is_full or full_function_detail_ok), function_count > 0, "Full 기능 상세에서 상태-액션-결과 처리 기준이 확인됩니다." if is_full else "데이터 검증/처리 기준이 확인됩니다.", "Full 버전에서는 처리 로직을 '(상태) ... → (액션) ... → (결과) ...' 형식으로 정상·분기·예외까지 작성하세요." if is_full else "검증, 변환, 산정, 판정 기준을 추가하세요."),
        "9-4": (signals["has_data_output"] and (not is_full or full_io_contract_ok), function_count > 0, "Full 기능 상세에서 출력 정보와 처리 결과 기준이 확인됩니다." if is_full else "출력 데이터/결과 기준이 확인됩니다.", "Full 버전에서는 처리 결과로 생성·변경·삭제되는 데이터와 고객/시스템 회신 결과를 기능 상세의 출력 정보에 작성하세요." if is_full else "처리 결과로 생성, 변경, 삭제되는 데이터를 명시하세요."),
        "9-5": (signals["has_data_retention"], policy_count > 0, "저장/이력/보관/마스킹 기준이 확인됩니다.", "저장, 이력, 조회, 마스킹, 보관 기준을 보강하세요."),
        "10-1": (requirements_mapping_row_count > 0 or graph_trace_ok, graph_available or signals["has_requirements_trace"], "요구사항 매핑 행 또는 Policy Graph 요구사항 연결이 확인됩니다.", "기준 요구사항을 프로세스, 기능, 정책 중 하나 이상에 매핑한 표 또는 추적 근거를 추가하세요."),
        "10-2": ((requirements_mapping_row_count > 0 or graph_trace_ok) and signals["has_process_flow"], signals["has_requirements_trace"] or graph_available, "요구사항을 업무 흐름/정책 기준으로 재구성한 추적 근거가 확인됩니다.", "요구사항 문구를 그대로 두지 말고 업무 흐름과 판단 기준으로 재구성한 근거를 남기세요."),
        "10-3": (has_any(signals["text"], ("신규 도출", "추가 도출", "누락", "알림", "이력")), signals["has_requirements_trace"], "신규 도출 항목 표현이 확인됩니다.", "요구사항에서 빠진 예외, 상태, 알림, 이력 필요성을 기록하세요."),
        "10-4": (signals["has_dev_qa"] and function_count > 0 and (not is_full or (full_process_detail_ok and full_function_detail_ok)), function_count > 0, "Full 상세 설계로 전환할 프로세스·기능 상세 구조가 확인됩니다." if is_full else "개발자가 기능 설계로 전환할 ID 구조가 확인됩니다.", "Full 버전에서는 개발자가 설계 항목으로 옮길 수 있도록 프로세스 상세와 기능 상세의 ID, 입력, 처리, 출력, 정책 연결을 보강하세요." if is_full else "개발자가 설계 항목으로 전환할 기능/정책 연결을 보강하세요."),
        "10-5": (signals["has_dev_qa"] and signals["has_status_distinction"] and (not is_full or full_exception_detail_ok), signals["has_dev_qa"], "Full 기능 상세의 정상·분기·예외 결과에서 QA 조건을 도출할 수 있습니다." if is_full else "QA 테스트 조건/기대 결과 관점이 확인됩니다.", "Full 버전에서는 QA가 테스트 조건과 기대 결과를 만들 수 있게 정상, 분기, 예외, 재시도, 중단 결과를 상태-액션-결과로 남기세요." if is_full else "QA가 테스트 조건과 기대 결과를 도출할 수 있게 경계값과 예외 결과를 명시하세요."),
    }
    strong, partial, evidence, suggestion = checks.get(
        item_id,
        (False, False, "자동 평가 기준이 없습니다.", "루브릭 평가 기준을 보강하세요."),
    )
    score = 2 if strong else 1 if partial else 0
    if score == 0:
        evidence = "문서에서 해당 기준을 충분히 확인하지 못했습니다."
    elif score == 1:
        evidence = evidence + " 다만 구체성 또는 연결 근거가 더 필요합니다."
    return score, evidence, suggestion


def evaluate_mandatory_gates(
    rubric: Mapping[str, Any],
    item_scores: Mapping[str, int],
    signals: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    for gate in rubric.get("mandatory_gates", []):
        if not isinstance(gate, Mapping):
            continue
        item_ref = str(gate.get("item_ref", "")).strip()
        score = int(item_scores.get(item_ref, 0))
        passed = score >= 2
        if gate.get("id") == "G5":
            passed = (
                passed
                and int(signals.get("weak_policy_count", 0)) == 0
                and int(signals.get("truncated_marker_count", 0)) == 0
            )
        gates.append(
            {
                "id": str(gate.get("id", "")).strip(),
                "itemRef": item_ref,
                "description": str(gate.get("description", "")).strip(),
                "passed": passed,
                "reason": "통과" if passed else "관련 체크 항목이 2점 기준을 충족하지 못했습니다.",
                "suggestion": "관련 장의 연결성과 판단 기준을 보강하세요." if not passed else "",
            }
        )
    return gates


def apply_gate_score_cap(score: int, gates: List[Mapping[str, Any]]) -> int:
    failed_count = sum(1 for gate in gates if not gate.get("passed"))
    if failed_count >= 3:
        return min(score, 69)
    if failed_count >= 1:
        return min(score, 79)
    return score


def run_llm_health_check(
    *,
    llm_client: object,
    rubric: Mapping[str, Any],
    document_text: str,
    signals: Mapping[str, Any],
    topic: str,
    template_type: str,
) -> Dict[str, Any]:
    return llm_client.generate_json(
        schema_name="policy_health_check",
        schema=health_check_llm_schema(),
        instructions=health_check_llm_instructions(),
        input_messages=[
            {
                "role": "user",
                "content": "\n\n".join(
                    [
                        "아래 정책서를 Health Check 루브릭 기준으로 평가해 주세요.",
                        json.dumps(
                            {
                                "topic": topic,
                                "template_type": template_type,
                                "rubric": rubric,
                                "signals": compact_signals(signals),
                            },
                            ensure_ascii=False,
                        ),
                        "정책서 본문:",
                        document_text,
                    ]
                ),
            }
        ],
    )


def health_check_llm_schema() -> Dict[str, Any]:
    item_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "score": {"type": "integer"},
            "evidence": {"type": "string"},
            "suggestion": {"type": "string"},
        },
        "required": ["id", "score", "evidence", "suggestion"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "items": {"type": "array", "items": item_schema},
        },
        "required": ["summary", "items"],
        "additionalProperties": False,
    }


def health_check_llm_instructions() -> str:
    return """
당신은 NC 정책서의 설계 품질을 Health Check 루브릭으로 평가하는 Quality Evaluator다.
점수는 각 항목 0, 1, 2점만 사용한다.
0점은 문서에서 확인 불가, 1점은 일부 확인되나 개발/QA 기준으로 부족, 2점은 충분히 확인되는 경우다.
간소화 버전은 간소화 산출물에 존재하는 장과 범위 안에서 엄격하게 평가하고, 프로세스 상세·기능 상세처럼 간소화 범위 밖의 장을 요구하지 않는다.
Full 버전은 간소화 구조 검증에 더해 프로세스 상세와 기능 상세의 진입 조건, 종료 조건, 입력, 상태-액션-결과 처리, 출력, 실패·예외, 관련 정책 연결을 평가한다.
문서 범위를 벗어난 일반 보안·운영·개발 방법론 요구를 만들지 않는다.
판단 근거는 문서 안의 장, 표, ID, 정책 항목에 연결해서 짧게 쓴다.
보완 제안은 사용자가 수정할 수 있는 정책서 문체의 실행 지시로 작성한다.
결과는 지정된 JSON 스키마만 반환한다.
""".strip()


def merge_llm_scores(sections: List[Dict[str, Any]], llm_report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    llm_items = {
        str(item.get("id", "")).strip(): item
        for item in llm_report.get("items", [])
        if isinstance(item, Mapping)
    }
    merged: List[Dict[str, Any]] = []
    for section in sections:
        next_items = []
        for item in section.get("items", []):
            override = llm_items.get(item.get("id", ""))
            if override:
                item = {
                    **item,
                    "score": max(0, min(2, int(override.get("score", item.get("score", 0)) or 0))),
                    "evidence": str(override.get("evidence") or item.get("evidence") or ""),
                    "suggestion": str(override.get("suggestion") or item.get("suggestion") or ""),
                    "source": "llm",
                }
            next_items.append(item)
        score = sum(int(item["score"]) for item in next_items)
        merged.append({**section, "items": next_items, "score": score, "judgement": section_judgement(score), "majorGap": first_gap(next_items)})
    return merged


def normalize_recheck_item_ids(item_ids: Optional[List[str]]) -> List[str]:
    if not item_ids:
        return []
    normalized: List[str] = []
    for item_id in item_ids:
        value = str(item_id or "").strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized[:50]


def merge_selective_recheck_sections(
    previous_report: Mapping[str, Any],
    current_sections: List[Dict[str, Any]],
    recheck_item_ids: List[str],
) -> List[Dict[str, Any]]:
    """Reuse previous item results except for selected failed items.

    The local signal extraction still runs once, but optional LLM scoring and UI
    review can focus on the selected item IDs. This keeps the report comparable
    while avoiding a full semantic re-review for every already-passed item.
    """

    recheck_set = set(recheck_item_ids)
    previous_items = {
        str(item.get("id", "") or ""): dict(item)
        for item in health_check_items(previous_report)
        if item.get("id")
    }
    merged_sections: List[Dict[str, Any]] = []
    for section in current_sections:
        next_items: List[Dict[str, Any]] = []
        for item in section.get("items", []):
            item_id = str(item.get("id", "") or "")
            if item_id and item_id not in recheck_set and item_id in previous_items:
                previous_item = dict(previous_items[item_id])
                previous_item["source"] = str(previous_item.get("source", "previous"))
                previous_item["recheckStatus"] = "reused"
                next_items.append(previous_item)
            else:
                refreshed_item = dict(item)
                refreshed_item["recheckStatus"] = "rechecked" if item_id in recheck_set else "new"
                next_items.append(refreshed_item)
        score = sum(int(item.get("score", 0) or 0) for item in next_items)
        merged_sections.append(
            {
                **section,
                "items": next_items,
                "score": score,
                "judgement": section_judgement(score),
                "majorGap": first_gap(next_items),
            }
        )
    return merged_sections


def build_health_action_items(
    sections: List[Mapping[str, Any]],
    gates: List[Mapping[str, Any]],
    signals: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    failed_gates = {str(gate.get("itemRef", "")): gate for gate in gates if not gate.get("passed")}
    for section in sections:
        for item in section.get("items", []):
            if not isinstance(item, Mapping):
                continue
            score = int(item.get("score", 0))
            if score >= 2:
                continue
            item_id = str(item.get("id", ""))
            items.append(
                {
                    "itemId": item_id,
                    "section": section.get("name", ""),
                    "priority": "P1" if item_id in failed_gates else "P2" if score == 0 else "P3",
                    "title": item.get("question", ""),
                    "targetLocation": item.get("relatedLocation", ""),
                    "evidence": item.get("evidence", ""),
                    "suggestion": item.get("suggestion", ""),
                    "score": score,
                }
            )
    items.extend(graph_action_items(signals or {}))
    return sorted(items, key=lambda item: {"P1": 0, "P2": 1, "P3": 2}.get(item["priority"], 3))[:20]


def build_health_remediation_plan(
    *,
    sections: List[Mapping[str, Any]],
    gates: List[Mapping[str, Any]],
    action_items: List[Mapping[str, Any]],
    previous_report: Mapping[str, Any] | None = None,
    recheck_item_ids: Optional[List[str]] = None,
    artifact_drift: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Create a user-facing remediation strategy from the scorecard.

    Health Check scoring should stay deterministic, but the UI needs a clearer
    explanation of what to fix now, what remains as partial risk, and whether a
    recheck surfaced new or repeated issues. This plan is intentionally derived
    from the already-scored items instead of changing the scoring itself.
    """

    failed_gate_refs = {str(gate.get("itemRef", "") or "") for gate in gates if isinstance(gate, Mapping) and not gate.get("passed")}
    previous_items = {
        str(item.get("id", "") or ""): item
        for item in health_check_items(previous_report or {})
        if isinstance(item, Mapping) and item.get("id")
    }
    has_previous = bool(previous_items)
    immediate: List[Dict[str, Any]] = []
    potential: List[Dict[str, Any]] = []
    newly_detected: List[Dict[str, Any]] = []
    repeated: List[Dict[str, Any]] = []
    improved: List[Dict[str, Any]] = []
    regressed: List[Dict[str, Any]] = []

    for section in sections:
        if not isinstance(section, Mapping):
            continue
        for item in section.get("items", []):
            if not isinstance(item, Mapping):
                continue
            score = int(item.get("score", 0) or 0)
            max_score = health_item_max_score(item)
            item_id = str(item.get("id", "") or "")
            if score >= max_score:
                if has_previous and item_id in previous_items:
                    previous_item = previous_items[item_id]
                    previous_score = int(previous_item.get("score", 0) or 0)
                    previous_max = health_item_max_score(previous_item)
                    if previous_score < previous_max:
                        improved.append(
                            health_plan_item_from_section(
                                section=section,
                                item=item,
                                priority="P3",
                                history_status="resolved",
                                previous_score=previous_score,
                                current_score=score,
                            )
                        )
                continue

            priority = "P1" if item_id in failed_gate_refs else "P2" if score <= 0 else "P3"
            history_status = health_history_status(item, previous_items if has_previous else {})
            plan_item = health_plan_item_from_section(
                section=section,
                item=item,
                priority=priority,
                history_status=history_status,
                previous_score=int(previous_items[item_id].get("score", 0) or 0) if item_id in previous_items else None,
                current_score=score,
            )
            if priority in {"P1", "P2"}:
                immediate.append(plan_item)
            else:
                potential.append(plan_item)
            if has_previous:
                if history_status in {"new", "regressed"}:
                    newly_detected.append(plan_item)
                elif history_status == "repeated":
                    repeated.append(plan_item)
                if history_status == "regressed":
                    regressed.append(plan_item)

    graph_items = [health_plan_item_from_action(item, "graph") for item in action_items if is_graph_action_item(item)]
    immediate.extend(graph_items)
    artifact_items = health_artifact_plan_items(artifact_drift, action_items)
    immediate = unique_plan_items(immediate)
    potential = unique_plan_items(potential)
    artifact_items = unique_plan_items(artifact_items)
    newly_detected = unique_plan_items(newly_detected)
    repeated = unique_plan_items(repeated)
    improved = unique_plan_items(improved)
    regressed = unique_plan_items(regressed)

    summary = (
        f"즉시 보완 {len(immediate)}건, 잠재 보완 {len(potential)}건, "
        f"산출물 동기화 {len(artifact_items)}건을 분리했습니다."
    )
    if has_previous:
        summary += f" 재점검 기준 신규 {len(newly_detected)}건, 반복 {len(repeated)}건, 개선 {len(improved)}건입니다."
    return {
        "version": "1.0",
        "summary": summary,
        "guidance": "본문 보완은 즉시 보완 항목부터 처리하고, 산출물 동기화 이슈는 HTML/spec/BPMN/Trace 재생성 또는 저장 동기화 문제로 별도 확인하세요.",
        "immediate": immediate[:16],
        "potential": potential[:18],
        "artifactSync": artifact_items[:12],
        "newlyDetected": newly_detected[:12],
        "repeated": repeated[:12],
        "improved": improved[:12],
        "regressed": regressed[:12],
        "recheck": {
            "hasPrevious": has_previous,
            "selectedItemIds": normalize_recheck_item_ids(recheck_item_ids),
            "newCount": len(newly_detected),
            "repeatedCount": len(repeated),
            "improvedCount": len(improved),
            "regressedCount": len(regressed),
        },
    }


def health_item_max_score(item: Mapping[str, Any]) -> int:
    try:
        return max(1, int(item.get("maxScore", item.get("max_score", 2)) or 2))
    except (TypeError, ValueError):
        return 2


def health_history_status(item: Mapping[str, Any], previous_items: Mapping[str, Mapping[str, Any]]) -> str:
    item_id = str(item.get("id", "") or "")
    if not previous_items:
        return "initial"
    previous_item = previous_items.get(item_id)
    if not previous_item:
        return "new"
    score = int(item.get("score", 0) or 0)
    max_score = health_item_max_score(item)
    previous_score = int(previous_item.get("score", 0) or 0)
    previous_max = health_item_max_score(previous_item)
    if previous_score >= previous_max and score < max_score:
        return "regressed"
    if previous_score < previous_max and score < max_score:
        return "repeated"
    if previous_score < previous_max and score >= max_score:
        return "resolved"
    return "stable"


def health_plan_item_from_section(
    *,
    section: Mapping[str, Any],
    item: Mapping[str, Any],
    priority: str,
    history_status: str,
    previous_score: int | None = None,
    current_score: int | None = None,
) -> Dict[str, Any]:
    return {
        "itemId": str(item.get("id", "") or ""),
        "section": str(section.get("name", "") or ""),
        "sectionId": str(section.get("id", "") or ""),
        "priority": priority,
        "title": str(item.get("question", "") or item.get("title", "") or "보완 항목"),
        "targetLocation": str(item.get("relatedLocation", "") or "문서 본문"),
        "evidence": str(item.get("evidence", "") or ""),
        "suggestion": str(item.get("suggestion", "") or ""),
        "score": int(item.get("score", 0) or 0),
        "maxScore": health_item_max_score(item),
        "historyStatus": history_status,
        "recheckStatus": str(item.get("recheckStatus", "") or ""),
        "previousScore": previous_score,
        "currentScore": current_score if current_score is not None else int(item.get("score", 0) or 0),
    }


def health_plan_item_from_action(item: Mapping[str, Any], history_status: str) -> Dict[str, Any]:
    return {
        "itemId": str(item.get("itemId", "") or ""),
        "section": str(item.get("section", "") or ""),
        "sectionId": "",
        "priority": str(item.get("priority", "P2") or "P2"),
        "title": str(item.get("title", "") or "보완 항목"),
        "targetLocation": str(item.get("targetLocation", "") or "문서 본문"),
        "evidence": str(item.get("evidence", "") or ""),
        "suggestion": str(item.get("suggestion", "") or ""),
        "score": int(item.get("score", 0) or 0),
        "maxScore": 2,
        "historyStatus": history_status,
        "recheckStatus": str(item.get("recheckStatus", "") or ""),
        "previousScore": None,
        "currentScore": int(item.get("score", 0) or 0),
    }


def is_graph_action_item(item: Mapping[str, Any]) -> bool:
    item_id = str(item.get("itemId", "") or "")
    return item_id.startswith("GRAPH-")


def health_artifact_plan_items(
    artifact_drift: Mapping[str, Any] | None,
    action_items: List[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    artifact_items = [
        health_plan_item_from_action(item, "artifact")
        for item in action_items
        if str(item.get("section", "") or "") == "산출물 동기화" or str(item.get("itemId", "") or "").startswith("ARTIFACT")
    ]
    drift = artifact_drift or {}
    if isinstance(drift, Mapping) and drift.get("status") not in {None, "", "pass", "skipped"}:
        issues = drift.get("issues", []) if isinstance(drift.get("issues", []), list) else []
        if not issues and drift.get("summary"):
            artifact_items.append(
                {
                    "itemId": "ARTIFACT-DRIFT",
                    "section": "산출물 동기화",
                    "sectionId": "artifact",
                    "priority": "P1" if drift.get("status") == "fail" else "P2",
                    "title": str(drift.get("summary", "산출물 동기화 확인 필요")),
                    "targetLocation": "HTML/spec/BPMN/Trace",
                    "evidence": str(drift.get("summary", "")),
                    "suggestion": "본문 보완 전에 HTML, spec, BPMN, Trace 산출물이 같은 버전 기준으로 재생성되었는지 확인하세요.",
                    "score": 0 if drift.get("status") == "fail" else 1,
                    "maxScore": 2,
                    "historyStatus": "artifact",
                    "recheckStatus": "",
                    "previousScore": None,
                    "currentScore": 0 if drift.get("status") == "fail" else 1,
                }
            )
    return artifact_items


def unique_plan_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        key = str(item.get("itemId") or item.get("title") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def graph_action_items(signals: Mapping[str, Any]) -> List[Dict[str, Any]]:
    graph = signals.get("policy_graph_context", {}) if isinstance(signals.get("policy_graph_context"), Mapping) else {}
    if not graph.get("available"):
        return []
    items: List[Dict[str, Any]] = []
    for gap in graph.get("coverage_gaps", []) if isinstance(graph.get("coverage_gaps"), list) else []:
        if not isinstance(gap, Mapping):
            continue
        requirement_id = str(gap.get("requirement_id", "") or "").strip()
        title = str(gap.get("title", "") or "요구사항 연결 누락").strip()
        items.append(
            {
                "itemId": f"GRAPH-COVERAGE-{requirement_id}",
                "section": "요구사항·개발·QA 추적성",
                "priority": "P1",
                "title": f"{requirement_id} 요구사항 연결 누락",
                "targetLocation": "요구사항 매핑 / 프로세스·기능·정책 연결",
                "evidence": f"{requirement_id} {title} 요구사항이 유즈케이스·프로세스·기능·정책·정책항목 중 하나에도 연결되지 않았습니다.",
                "suggestion": str(gap.get("recommendation", "") or "요구사항을 실제 문서 계층 중 하나 이상에 연결하세요."),
                "score": 0,
            }
        )
    for gap in graph.get("chain_gaps", []) if isinstance(graph.get("chain_gaps"), list) else []:
        if not isinstance(gap, Mapping):
            continue
        source_id = str(gap.get("source_id", "") or "").strip()
        title = str(gap.get("title", "") or "계층 연결 누락").strip()
        items.append(
            {
                "itemId": f"GRAPH-CHAIN-{source_id}-{gap.get('type', '')}",
                "section": "업무 구조 정합성",
                "priority": "P1" if gap.get("type") in {"usecase_without_process", "process_without_function"} else "P2",
                "title": f"{source_id} 계층 연결 누락",
                "targetLocation": "유즈케이스-프로세스-기능-정책 연결",
                "evidence": f"{source_id} {title}: {gap.get('type', '')}",
                "suggestion": str(gap.get("recommendation", "") or "상위/하위 계층 연결을 보강하세요."),
                "score": 0,
            }
        )
    return items


def evaluate_health_gatekeeper(
    report: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    signals: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Review whether the Health Check result is itself trustworthy.

    This is a deterministic GateKeeper inspired by the agentic review loop used
    in external SBF validation material. It does not change the document score;
    it tells the user whether the scorecard has enough evidence, gap coverage,
    rubric fidelity, rationale quality, and internal consistency to be relied on.
    """

    dimensions: List[Dict[str, Any]] = []
    for spec in HEALTH_GATEKEEPER_DIMENSIONS:
        score, status, evidence, suggestion = health_gatekeeper_dimension_score(
            str(spec["name"]),
            report=report,
            rubric=rubric,
            signals=signals or {},
        )
        dimensions.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "label": spec["label"],
                "description": spec["description"],
                "score": score,
                "maxScore": 20,
                "status": status,
                "evidence": evidence,
                "suggestion": suggestion,
            }
        )

    total_score = sum(int(item["score"]) for item in dimensions)
    grade = health_gatekeeper_grade(total_score)
    critical_fail = any(
        item["status"] == "fail" and item["name"] in {"rubric_adherence", "internal_consistency"}
        for item in dimensions
    )
    passed = grade in {"A", "B"} and not critical_fail
    findings = [
        {
            "dimension": item["name"],
            "label": item["label"],
            "status": item["status"],
            "evidence": item["evidence"],
            "suggestion": item["suggestion"],
        }
        for item in dimensions
        if item["status"] != "pass"
    ]
    summary = (
        f"GateKeeper {grade}등급({total_score}/100)입니다. "
        f"{'Health Check 산출물 품질을 신뢰할 수 있습니다.' if passed else 'Health Check 산출물 품질 보완이 필요합니다.'}"
    )
    return {
        "agent": "Health Check GateKeeper",
        "version": "1.0",
        "grade": grade,
        "score": total_score,
        "maxScore": 100,
        "passed": passed,
        "summary": summary,
        "dimensions": dimensions,
        "findings": findings,
    }


def health_gatekeeper_dimension_score(
    name: str,
    *,
    report: Mapping[str, Any],
    rubric: Mapping[str, Any],
    signals: Mapping[str, Any],
) -> tuple[int, str, str, str]:
    if name == "evidence_specificity":
        return score_gatekeeper_evidence_specificity(report)
    if name == "gap_completeness":
        return score_gatekeeper_gap_completeness(report)
    if name == "rubric_adherence":
        return score_gatekeeper_rubric_adherence(report, rubric)
    if name == "rationale_quality":
        return score_gatekeeper_rationale_quality(report)
    if name == "internal_consistency":
        return score_gatekeeper_internal_consistency(report, rubric)
    return 0, "fail", "알 수 없는 GateKeeper 차원입니다.", "GateKeeper 평가 차원 정의를 확인하세요."


def score_gatekeeper_evidence_specificity(report: Mapping[str, Any]) -> tuple[int, str, str, str]:
    items = health_check_items(report)
    if not items:
        return 0, "fail", "평가 항목이 없습니다.", "Health Check 섹션별 평가 항목을 생성하세요."
    concrete_count = sum(1 for item in items if has_specific_health_evidence(item))
    ratio_value = ratio(concrete_count, len(items))
    if ratio_value >= 0.9:
        return 20, "pass", f"{concrete_count}/{len(items)}개 항목에 판단 근거와 보완 위치가 있습니다.", ""
    if ratio_value >= 0.7:
        return 14, "partial", f"{concrete_count}/{len(items)}개 항목만 충분한 판단 근거를 갖습니다.", "근거가 짧은 항목에는 문서 위치, 확인 신호, 보완 대상을 함께 남기세요."
    if ratio_value >= 0.45:
        return 7, "partial", f"{concrete_count}/{len(items)}개 항목에서만 근거를 확인했습니다.", "항목별 evidence/suggestion/relatedLocation을 보강하세요."
    return 0, "fail", f"{concrete_count}/{len(items)}개 항목만 근거가 있습니다.", "Health Check 항목별 판단 근거를 생성하도록 평가 로직을 보완하세요."


def score_gatekeeper_gap_completeness(report: Mapping[str, Any]) -> tuple[int, str, str, str]:
    failed_items = [
        item for item in health_check_items(report)
        if int(item.get("score", 0) or 0) < int(item.get("maxScore", item.get("max_score", 2)) or 2)
    ]
    actions = report.get("actionItems", []) if isinstance(report.get("actionItems", []), list) else []
    action_ids = {str(item.get("itemId", "") or "") for item in actions if isinstance(item, Mapping)}
    failed_ids = {str(item.get("id", "") or "") for item in failed_items if item.get("id")}
    expected_action_count = min(len(failed_ids), 20)
    covered_count = min(len(failed_ids & action_ids), expected_action_count)
    failed_gates = [gate for gate in report.get("mandatoryGates", []) if isinstance(gate, Mapping) and not gate.get("passed")]
    p1_ids = {
        str(item.get("itemId", "") or "")
        for item in actions
        if isinstance(item, Mapping) and str(item.get("priority", "")) == "P1"
    }
    failed_gate_refs = {str(gate.get("itemRef", "") or "") for gate in failed_gates}
    failed_gate_covered = failed_gate_refs.issubset(p1_ids)
    if not failed_items and not failed_gates:
        return 20, "pass", "미통과 항목과 필수 Gate 실패가 없습니다.", ""
    coverage = ratio(covered_count, expected_action_count or 1)
    if coverage >= 0.9 and failed_gate_covered:
        return 20, "pass", f"미통과 항목 상위 {covered_count}/{expected_action_count}건과 필수 Gate 실패가 보완 항목으로 연결됩니다.", ""
    if coverage >= 0.6 and failed_gate_covered:
        return 14, "partial", f"미통과 항목 상위 {covered_count}/{expected_action_count}건이 보완 항목으로 연결됩니다.", "낮은 점수 항목이 actionItems에서 누락되지 않게 보완하세요."
    return 7 if failed_gate_covered else 0, "partial" if failed_gate_covered else "fail", (
        f"미통과 항목 상위 {covered_count}/{expected_action_count}건만 보완 항목에 연결됩니다."
    ), "필수 Gate 실패는 P1, 0점 항목은 P2 이상으로 actionItems에 연결하세요."


def score_gatekeeper_rubric_adherence(report: Mapping[str, Any], rubric: Mapping[str, Any]) -> tuple[int, str, str, str]:
    sections = report.get("sections", []) if isinstance(report.get("sections", []), list) else []
    rubric_sections = [section for section in rubric.get("sections", []) if isinstance(section, Mapping)]
    expected_item_ids = {
        str(item.get("id", "") or "")
        for section in rubric_sections
        for item in section.get("items", [])
        if isinstance(item, Mapping)
    }
    actual_item_ids = {str(item.get("id", "") or "") for item in health_check_items(report)}
    score_bounds_ok = all(
        0 <= int(item.get("score", 0) or 0) <= int(item.get("maxScore", item.get("max_score", 2)) or 2)
        for item in health_check_items(report)
    )
    gate_count_ok = len(report.get("mandatoryGates", []) or []) == len(rubric.get("mandatory_gates", []) or [])
    section_count_ok = len(sections) == len(rubric_sections)
    item_ids_ok = expected_item_ids == actual_item_ids
    if section_count_ok and item_ids_ok and gate_count_ok and score_bounds_ok:
        return 20, "pass", "루브릭 섹션, 항목, 필수 Gate, 점수 범위를 모두 준수합니다.", ""
    partial_count = sum(1 for flag in (section_count_ok, item_ids_ok, gate_count_ok, score_bounds_ok) if flag)
    if partial_count >= 3:
        return 14, "partial", "루브릭 구조 대부분을 준수하지만 일부 불일치가 있습니다.", "섹션 수, 항목 ID, 필수 Gate 수를 루브릭과 다시 맞추세요."
    return 0, "fail", "루브릭 구조와 Health Check 결과 구조가 맞지 않습니다.", "Health Check 결과 생성 시 루브릭 섹션과 항목을 누락 없이 순회하세요."


def score_gatekeeper_rationale_quality(report: Mapping[str, Any]) -> tuple[int, str, str, str]:
    summary = str(report.get("summary", "") or "")
    actions = report.get("actionItems", []) if isinstance(report.get("actionItems", []), list) else []
    low_sections = [
        section for section in report.get("sections", [])
        if isinstance(section, Mapping) and int(section.get("score", 0) or 0) < int(section.get("maxScore", section.get("max_score", 10)) or 10)
    ]
    summary_ok = all(marker in summary for marker in ("Health Check", "점", "판정"))
    action_quality_count = sum(1 for item in actions if has_action_item_rationale(item))
    action_quality_ok = not actions or ratio(action_quality_count, len(actions)) >= 0.85
    section_gap_ok = not low_sections or any(str(section.get("majorGap", "") or "").strip() for section in low_sections)
    if summary_ok and action_quality_ok and section_gap_ok:
        return 20, "pass", "요약, 주요 Gap, 보완 제안이 실행 가능한 수준입니다.", ""
    if summary_ok and (action_quality_ok or section_gap_ok):
        return 14, "partial", "요약은 충분하지만 일부 Gap 또는 보완 제안의 실행성이 약합니다.", "보완 항목에는 위치, 근거, 수정 방향을 함께 작성하세요."
    return 7, "partial", "Health Check 요약 또는 보완 사유가 짧습니다.", "검토자가 바로 수정할 수 있게 주요 Gap과 보완 제안을 구체화하세요."


def score_gatekeeper_internal_consistency(report: Mapping[str, Any], rubric: Mapping[str, Any]) -> tuple[int, str, str, str]:
    sections = report.get("sections", []) if isinstance(report.get("sections", []), list) else []
    gates = report.get("mandatoryGates", []) if isinstance(report.get("mandatoryGates", []), list) else []
    section_sum = sum(int(section.get("score", 0) or 0) for section in sections if isinstance(section, Mapping))
    raw_score = int(report.get("rawScore", 0) or 0)
    total_score = int(report.get("score", 0) or 0)
    expected_score = apply_gate_score_cap(raw_score, gates)
    gate_passed = all(gate.get("passed") for gate in gates if isinstance(gate, Mapping))
    expected_judgement = judgement_for_score(rubric, total_score)
    if not gate_passed and expected_judgement in {"우수", "양호"}:
        expected_judgement = "보완 필요"
    checks = {
        "raw_score": raw_score == section_sum,
        "score_cap": total_score == expected_score,
        "gate_flag": bool(report.get("mandatoryGatePassed")) == gate_passed,
        "judgement": str(report.get("judgement", "")) == expected_judgement,
    }
    if all(checks.values()):
        return 20, "pass", "섹션 합계, Gate cap, 필수 Gate 여부, 판정이 서로 일치합니다.", ""
    failed = ", ".join(key for key, ok in checks.items() if not ok)
    if sum(1 for ok in checks.values() if ok) >= 3:
        return 14, "partial", f"대부분 일치하지만 {failed} 항목에 불일치가 있습니다.", "총점, rawScore, Gate 통과 여부, 판정 산식을 다시 동기화하세요."
    return 0, "fail", f"Health Check 내부 값 불일치가 큽니다: {failed}", "점수 산식과 Gate 판정 산식을 우선 보정하세요."


def health_check_items(report: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return [
        item
        for section in report.get("sections", [])
        if isinstance(section, Mapping)
        for item in section.get("items", [])
        if isinstance(item, Mapping)
    ]


def has_specific_health_evidence(item: Mapping[str, Any]) -> bool:
    evidence = str(item.get("evidence", "") or "").strip()
    suggestion = str(item.get("suggestion", "") or "").strip()
    location = str(item.get("relatedLocation", "") or "").strip()
    if not suggestion or len(suggestion) < 10:
        return False
    if not location:
        return False
    if "자동 평가 기준이 없습니다" in evidence:
        return False
    if int(item.get("score", 0) or 0) <= 0:
        return bool(evidence or suggestion)
    return len(evidence) >= 10


def has_action_item_rationale(item: Mapping[str, Any]) -> bool:
    if not isinstance(item, Mapping):
        return False
    return all(
        str(item.get(key, "") or "").strip()
        for key in ("title", "targetLocation", "suggestion")
    )


def health_gatekeeper_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 60:
        return "C"
    return "F"


def append_gatekeeper_summary(summary: str, gatekeeper: Mapping[str, Any]) -> str:
    grade = str(gatekeeper.get("grade", "") or "")
    passed = bool(gatekeeper.get("passed"))
    if not grade:
        return summary
    gatekeeper_text = f" GateKeeper {grade}등급으로 평가 품질 {'통과' if passed else '보완 필요'}입니다."
    return f"{summary}{gatekeeper_text}"


def apply_health_result_blockers(report: Dict[str, Any]) -> None:
    gatekeeper = report.get("gatekeeper", {}) if isinstance(report.get("gatekeeper"), Mapping) else {}
    blockers: List[Dict[str, str]] = []
    grade = str(gatekeeper.get("grade", "") or "")
    if grade in {"C", "F"} or gatekeeper.get("passed") is False:
        blockers.append(
            {
                "id": "GK-CF",
                "type": "gatekeeper",
                "severity": "P1",
                "message": f"Health Check GateKeeper가 {grade or '-'}등급입니다. 평가 결과를 운영 판단에 사용하기 전에 평가 품질 보완이 필요합니다.",
            }
        )
    report["resultBlocked"] = bool(blockers)
    report["blockers"] = blockers


def build_summary(
    score: int,
    judgement: str,
    gate_passed: bool,
    low_sections: List[Mapping[str, Any]],
    evaluation_mode: str,
    llm_error: str,
    profile: Mapping[str, Any] | None = None,
) -> str:
    names = ", ".join(str(section.get("name", "")) for section in low_sections if section.get("name"))
    gate_text = "필수 게이트를 통과했습니다" if gate_passed else "필수 게이트 보완이 필요합니다"
    mode_text = "LLM+코드 기반" if evaluation_mode == "hybrid" else "코드 기반"
    profile_label = str((profile or {}).get("label", "") or "").strip()
    profile_text = f" {profile_label} 검증 범위로 평가했습니다." if profile_label else ""
    suffix = f" LLM 정성 평가 오류로 코드 평가만 사용했습니다: {llm_error}" if llm_error else ""
    return f"{mode_text} Health Check 결과 {score}점, 판정은 {judgement}입니다. {gate_text}.{profile_text} 주요 보완 영역은 {names or '없음'}입니다.{suffix}"


def judgement_for_score(rubric: Mapping[str, Any], score: int) -> str:
    for item in sorted(rubric.get("judgement", []), key=lambda row: int(row.get("min_score", 0)), reverse=True):
        if score >= int(item.get("min_score", 0)):
            return str(item.get("label", "재작성 필요"))
    return "재작성 필요"


def section_judgement(score: int) -> str:
    if score >= 9:
        return "우수"
    if score >= 8:
        return "양호"
    if score >= 7:
        return "보완 필요"
    if score >= 6:
        return "재검토 필요"
    return "재작성 필요"


def first_gap(items: List[Mapping[str, Any]]) -> str:
    for item in items:
        if int(item.get("score", 0)) < 2:
            return str(item.get("suggestion", "")).strip()
    return ""


def compact_signals(signals: Mapping[str, Any]) -> Dict[str, Any]:
    graph = signals.get("policy_graph_context", {}) if isinstance(signals.get("policy_graph_context"), Mapping) else {}
    pi_agent = signals.get("pi_agent", {}) if isinstance(signals.get("pi_agent"), Mapping) else {}
    return {
        "template_type": signals.get("template_type", "simple"),
        "template_profile": signals.get("template_profile", {}),
        "id_counts": signals.get("id_counts", {}),
        "id_examples": signals.get("id_examples", {}),
        "state_transition_count": signals.get("state_transition_count", 0),
        "weak_policy_count": signals.get("weak_policy_count", 0),
        "truncated_marker_count": signals.get("truncated_marker_count", 0),
        "decision_marker_count": signals.get("decision_marker_count", 0),
        "id_reference_count": signals.get("id_reference_count", 0),
        "requirements_mapping_row_count": signals.get("requirements_mapping_row_count", 0),
        "full_process_detail_marker_count": signals.get("full_process_detail_marker_count", 0),
        "full_function_detail_marker_count": signals.get("full_function_detail_marker_count", 0),
        "full_state_action_result_count": signals.get("full_state_action_result_count", 0),
        "has_full_process_detail_scope": signals.get("has_full_process_detail_scope", False),
        "has_full_function_detail_scope": signals.get("has_full_function_detail_scope", False),
        "has_full_normal_branch_exception": signals.get("has_full_normal_branch_exception", False),
        "has_full_io_contract": signals.get("has_full_io_contract", False),
        "state_transition_linked_event_count": signals.get("state_transition_linked_event_count", 0),
        "process_complete_mapping_count": signals.get("process_complete_mapping_count", 0),
        "policy_item_quality_count": signals.get("policy_item_quality_count", 0),
        "pi_agent": {
            "yes_count": pi_agent.get("yes_count", 0),
            "partial_count": pi_agent.get("partial_count", 0),
            "anti_pattern_count": pi_agent.get("anti_pattern_count", 0),
            "recommendations": pi_agent.get("recommendations", [])[:5] if isinstance(pi_agent.get("recommendations", []), list) else [],
        },
        "policy_graph": {
            "available": graph.get("available", False),
            "coverage_gap_count": graph.get("coverage_gap_count", 0),
            "chain_gap_count": graph.get("chain_gap_count", 0),
            "node_counts": graph.get("node_counts", {}),
        },
    }


def pi_agent_check_status(pi_agent: Mapping[str, Any]) -> Dict[str, str]:
    checks = pi_agent.get("checks", []) if isinstance(pi_agent.get("checks", []), list) else []
    result: Dict[str, str] = {}
    for item in checks:
        if not isinstance(item, Mapping):
            continue
        result[str(item.get("id", ""))] = str(item.get("status", ""))
    legacy_checks = pi_agent.get("legacy_checks", pi_agent.get("legacyChecks", []))
    if isinstance(legacy_checks, list):
        for item in legacy_checks:
            if not isinstance(item, Mapping):
                continue
            result[str(item.get("id", ""))] = str(item.get("status", ""))
    return result


def visible_text(document: str) -> str:
    cleaned = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", document, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</(p|div|section|article|tr|li|h[1-6])>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return html.unescape(re.sub(r"[ \t\r\f\v]+", " ", cleaned)).strip()


def count_unique_ids(document: str, prefix: str) -> int:
    pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(prefix)}-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
    return len(set(pattern.findall(document)))


def unique_ids(document: str, prefix: str) -> List[str]:
    pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(prefix)}-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
    seen: List[str] = []
    for match in pattern.findall(document):
        if match not in seen:
            seen.append(match)
    return seen


def extract_table_rows_by_headers(document: str, required_headers: tuple[str, ...]) -> List[List[str]]:
    rows: List[List[str]] = []
    for table in re.findall(r"<table\b[^>]*>.*?</table>", document, flags=re.IGNORECASE | re.DOTALL):
        header_text = " ".join(
            visible_text(row_html)
            for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", table, flags=re.IGNORECASE | re.DOTALL)
            if re.search(r"<th\b", row_html, flags=re.IGNORECASE)
        )
        if not all(header in header_text for header in required_headers):
            continue
        for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", table, flags=re.IGNORECASE | re.DOTALL):
            if re.search(r"<th\b", row_html, flags=re.IGNORECASE):
                continue
            cells = [
                visible_text(cell)
                for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
            ]
            if cells:
                rows.append(cells)
    return rows


def extract_policy_item_blocks(document: str) -> List[str]:
    blocks = [
        visible_text(block)
        for block in re.findall(r"<div\b[^>]*class=[\"'][^\"']*policy-item[^\"']*[\"'][^>]*>.*?</div>\s*</div>", document, flags=re.IGNORECASE | re.DOTALL)
    ]
    if blocks:
        return [block for block in blocks if "PI-" in block]
    blocks = [
        visible_text(block)
        for block in re.findall(r"<li\b[^>]*>.*?PI-.*?</li>", document, flags=re.IGNORECASE | re.DOTALL)
    ]
    if blocks:
        return blocks
    text = visible_text(document)
    ids = list(re.finditer(r"PI-[A-Z0-9]+-[A-Z0-9-]+", text))
    fallback: List[str] = []
    for index, match in enumerate(ids):
        start = max(0, match.start() - 80)
        end = ids[index + 1].start() if index + 1 < len(ids) else min(len(text), match.end() + 260)
        fallback.append(text[start:end].strip())
    return fallback


def is_quality_policy_item(block: str) -> bool:
    normalized = re.sub(r"\s+", " ", block).strip()
    if len(normalized) < 34:
        return False
    if "…" in normalized or "..." in normalized:
        return False
    if any(marker in normalized for marker in WEAK_POLICY_MARKERS):
        return False
    return bool(POLICY_DECISION_PATTERN.search(normalized))


def contains_id_prefix(text: str, prefix: str) -> bool:
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(prefix)}-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])", text))


def count_requirements_mapping_rows(rows: List[List[str]]) -> int:
    count = 0
    for row in rows:
        row_text = " ".join(row)
        if not has_any(row_text, ("요구사항", "상세 요구사항", "REQ", "Depth4", "4depth")):
            continue
        if any(contains_id_prefix(row_text, prefix) for prefix in ("US", "PR", "FN", "PG", "PI", "ST")):
            count += 1
    return count


def has_requirements_trace_statement(text: str) -> bool:
    """Accept a compact trace summary when the full mapping is stored externally."""

    if not has_any(text, ("요구사항", "상세 요구사항")):
        return False
    if not has_any(text, ("매핑", "추적", "반영", "재구성")):
        return False
    return bool(re.search(r"(요구사항|상세 요구사항)[^.\n]{0,80}\d+\s*건", text))


def has_topic_scoped_failure_case(text: str) -> bool:
    """Recognize failure handling that is specific to the document's domain.

    Some policy areas do not involve authentication or payment at all. In those
    cases the Health Check should reward concrete, topic-scoped failures such as
    publish reflection failure, BSS/analytics timeout, cache invalidation failure,
    deep-link failure, or duplicate/idempotent request handling.
    """

    return has_any(
        text,
        (
            "응답 지연",
            "회신 실패",
            "반영 실패",
            "동기화 실패",
            "게시 반영 실패",
            "채널별 게시 반영 실패",
            "BSS 반영 실패",
            "BSS 원장 반영 실패",
            "BSS·분석 응답",
            "분석 응답",
            "분석 연계 실패",
            "캐시 무효화 실패",
            "딥링크 실패",
            "외부 호출 실패",
            "폴백",
            "대체 노출",
            "대체 경로",
            "중복 게시 요청",
            "중복 요청",
            "멱등",
        ),
    )


def extract_full_detail_signals(document: str, normalized_text: str) -> Dict[str, Any]:
    """Extract signals that should only be required for Full-version checks."""

    process_detail_markers = (
        "프로세스 상세",
        "진입 조건",
        "종료 조건",
        "선행",
        "후행",
        "관련 기능",
        "관련 정책",
    )
    function_detail_markers = (
        "기능 상세",
        "입력 정보",
        "처리 로직",
        "처리 (상태-액션-결과)",
        "상태-액션-결과",
        "출력 정보",
        "실패·예외",
        "세부 기능 구성",
        "관련 정책",
    )
    full_logic_pattern = re.compile(
        r"\(상태\)[^→]{2,240}→\s*\(액션\)[^→]{2,420}→\s*\(결과\)[^<\n]{2,420}",
        flags=re.IGNORECASE,
    )
    full_logic_count = len(full_logic_pattern.findall(document)) or len(full_logic_pattern.findall(normalized_text))
    return {
        "full_process_detail_marker_count": count_occurrences(normalized_text, process_detail_markers),
        "full_function_detail_marker_count": count_occurrences(normalized_text, function_detail_markers),
        "full_state_action_result_count": full_logic_count,
        "has_full_process_detail_scope": all(marker in normalized_text for marker in ("프로세스 상세", "진입 조건", "종료 조건"))
        and has_any(normalized_text, ("선행", "후행"))
        and has_any(normalized_text, ("관련 기능", "관련 정책")),
        "has_full_function_detail_scope": all(marker in normalized_text for marker in ("기능 상세", "입력 정보", "출력 정보"))
        and has_any(normalized_text, ("처리 (상태-액션-결과)", "상태-액션-결과", "처리 로직"))
        and has_any(normalized_text, ("실패·예외", "실패", "예외")),
        "has_full_normal_branch_exception": all(marker in normalized_text for marker in ("정상", "분기", "예외")),
        "has_full_io_contract": all(marker in normalized_text for marker in ("입력 정보", "출력 정보")) and has_any(
            normalized_text,
            ("고객 입력값", "시스템 조회값", "외부 연계 결과", "필수", "선택", "생성", "변경", "삭제"),
        ),
    }


def ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def count_occurrences(text: str, markers: tuple[str, ...]) -> int:
    return sum(text.count(marker) for marker in markers)


def has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def topic_present(signals: Mapping[str, Any]) -> bool:
    topic = str(signals.get("topic", "")).strip()
    return bool(topic and topic in str(signals.get("text", "")))


def related_location(item_id: str, signals: Mapping[str, Any] | None = None) -> str:
    prefix = item_id.split("-", 1)[0]
    signals = signals or {}
    examples = signals.get("id_examples", {}) if isinstance(signals.get("id_examples"), Mapping) else {}
    counts = signals.get("id_counts", {}) if isinstance(signals.get("id_counts"), Mapping) else {}

    def with_examples(base: str, keys: tuple[str, ...]) -> str:
        ids: List[str] = []
        total = 0
        for key in keys:
            key_examples = examples.get(key, []) if isinstance(examples.get(key, []), list) else []
            ids.extend(str(item) for item in key_examples if item)
            total += int(counts.get(key, 0) or 0)
        ids = ids[:3]
        if ids:
            suffix = ", ".join(ids)
            if total > len(ids):
                suffix = f"{suffix} 외 {total - len(ids)}건"
            return f"{base} ({suffix})"
        return base

    base = {
        "1": "1. 개요 > 가. 범위 / 나. 설계 원칙",
        "2": "1. 개요 / 3~6장 고객 흐름·정책 기준",
        "3": "4. 프로세스 정의",
        "4": "3~6장 업무 구조 연결",
        "5": "3. 유즈케이스 정의 > 라. 상태 전이표",
        "6": "6. 정책 정의",
        "7": "상태 전이표 / 정책 상세",
        "8": "프로세스 / 기능 / 정책 상세",
        "9": "기능 정의 / 정책 상세",
        "10": "최종 점검 기준 / 요구사항 매핑",
    }.get(prefix, "문서 본문")
    if prefix == "4":
        return with_examples(base, ("usecases", "processes", "functions", "policies"))
    if prefix == "5":
        return with_examples(base, ("states", "usecases"))
    if prefix in {"6", "7"}:
        return with_examples(base, ("policies", "policy_items"))
    if prefix == "8":
        return with_examples(base, ("processes", "functions", "policies"))
    if prefix == "9":
        return with_examples(base, ("functions", "policy_items"))
    if prefix == "10":
        return with_examples(base, ("usecases", "processes", "functions", "policies", "policy_items"))
    return base
