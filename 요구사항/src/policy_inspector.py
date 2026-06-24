"""Inspector for NC policy document structure, guide compliance, and sample parity."""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from analysis_methods import method_guard_for_inspector
    from chain_matrix import build_chain_matrix, summarize_chain_matrix_for_stage
    from document_density import density_profile_from_spec, process_minimum_for_usecase
    from evidence_map import compact_topic_evidence_map_for_stage
    from pi_agent import pi_context_for_stage
    from policy_insight_rules import insight_applicability_for_prompt, insight_applicability_summary
    from policy_graph import graph_context_for_spec
    from policy_style_anchor import policy_style_anchor_context, policy_style_anchor_inspection_rule
    from runtime_paths import INSPECTIONS_ROOT, PROJECT_ROOT
    from topic_knowledge_builder import load_topic_knowledge_pack
except ImportError:  # pragma: no cover - package import fallback.
    from .analysis_methods import method_guard_for_inspector
    from .chain_matrix import build_chain_matrix, summarize_chain_matrix_for_stage
    from .document_density import density_profile_from_spec, process_minimum_for_usecase
    from .evidence_map import compact_topic_evidence_map_for_stage
    from .pi_agent import pi_context_for_stage
    from .policy_insight_rules import insight_applicability_for_prompt, insight_applicability_summary
    from .policy_graph import graph_context_for_spec
    from .policy_style_anchor import policy_style_anchor_context, policy_style_anchor_inspection_rule
    from .runtime_paths import INSPECTIONS_ROOT, PROJECT_ROOT
    from .topic_knowledge_builder import load_topic_knowledge_pack


REPORTS_DIR = INSPECTIONS_ROOT
DEFAULT_INSPECTOR_LLM_TASK_MAX_ATTEMPTS = 4
DEFAULT_INSPECTOR_LLM_RETRY_BASE_SECONDS = 10.0
DEFAULT_INSPECTOR_LLM_RETRY_MAX_SECONDS = 180.0
DEFAULT_INSPECTOR_MIN_SCORE = 85
FUNCTION_PROCESSING_LOGIC_PATTERN = re.compile(
    r"^\s*\(상태\)\s*.+?\s*→\s*\(액션\)\s*.+?\s*→\s*\(결과\)\s*.+"
)


@dataclass(frozen=True)
class InspectionFinding:
    severity: str
    category: str
    title: str
    detail: str
    recommendation: str
    finding_id: str = ""
    tier: str = ""
    is_quality_gate: bool = False
    is_metric_observation: bool = False
    target_path: str = ""
    fix_owner: str = "current_chapter"
    upstream_chapter: str = ""
    root_cause: str = ""
    required_change: str = ""
    patch_hint: str = ""
    acceptance_check: str = ""
    keep_constraints: str = ""
    do_not_change: str = ""


@dataclass(frozen=True)
class InspectionReport:
    status: str
    score: int
    scope: str
    checked_at: str
    summary: str
    findings: Sequence[InspectionFinding]
    metrics: dict

    def to_dict(self) -> dict:
        data = asdict(self)
        data["findings"] = [asdict(finding) for finding in self.findings]
        return data


SECTION_REQUIREMENTS = {
    "01_overview": ("1. 개요", "가. 범위", "나. 설계 원칙"),
    "02_terms": ("1. 개요", "2. 주요 용어"),
    "03_actors": ("3. 유즈케이스 정의", "가. 액터"),
    "04_usecases": ("3. 유즈케이스 정의", "나. 유즈케이스"),
    "05_usecase_diagram": ("3. 유즈케이스 정의", "다. 유즈케이스 다이어그램"),
    "06_state": ("3. 유즈케이스 정의", "라. 상태 전이표"),
    "07_process": ("4. 프로세스 정의", "가. 프로세스 목록", "나. 전체 업무 흐름도"),
    "08_functions": ("5. 기능 정의", "가. 기능 목록"),
    "09_policies": ("6. 정책 정의", "가. 정책 목록", "나. 정책 상세"),
    "10_final_check": ("최종 점검 기준",),
    "01_cover": ("통합채널 정책서",),
    "02_history": ("0. 문서 히스토리",),
    "03_overview": ("1. 개요", "가. 범위", "나. 설계 원칙"),
    "04_terms": ("2. 주요 용어",),
    "05_usecases": ("3. 유즈케이스 정의", "가. 액터", "나. 유즈케이스", "다. 유즈케이스 다이어그램", "라. 상태 전이표"),
    "06_process": ("4. 프로세스 정의", "가. 프로세스 목록", "나. 전체 업무 흐름도"),
    "07_functions": ("5. 기능 정의", "가. 기능 목록"),
    "08_policies": ("6. 정책 정의", "가. 정책 목록", "나. 정책 상세"),
    "09_final": ("최종 점검 기준",),
    "full": (
        "0. 문서 히스토리",
        "1. 개요",
        "2. 주요 용어",
        "3. 유즈케이스 정의",
        "4. 프로세스 정의",
        "5. 기능 정의",
        "6. 정책 정의",
        "최종 점검 기준",
    ),
}


FORBIDDEN_POLICY_PHRASES = (
    "검토 필요",
    "추후 협의",
    "시스템에서 처리",
    "가능하도록 한다",
    "정책에 따라 처리한다",
    "관련 부서 확인 필요",
    "정의 필요",
    "처리 예정",
    "협의 필요",
)

UI_OVERDETAIL_TERMS = (
    "디자인 컴포넌트",
    "API 필드",
    "DB 컬럼",
    "오류 코드 전체",
)

UI_CONTEXT_DETAIL_TERMS = (
    "팝업",
    "토스트",
    "배너",
    "버튼",
)

PROCESS_KEYWORDS = (
    "시작",
    "조회",
    "확인",
    "검증",
    "판정",
    "입력",
    "선택",
    "산정",
    "동의",
    "요청",
    "처리",
    "반영",
    "안내",
    "저장",
    "연동",
    "관리",
    "등록",
    "수정",
    "모니터링",
    "판단",
    "복원",
)
BODY_ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:TM|ACT|US|ST|PR|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")


def inspect_policy_document(
    document: str,
    template_html: str = "",
    sample_htmls: Sequence[str] = (),
    template_type: str = "simple",
    scope: str = "full",
    topic: str = "",
    brief: str = "",
    inspection_mode: str = "chapter-final",
    density_profile: Mapping[str, object] | None = None,
    llm_client: object | None = None,
    llm_required: bool = False,
    llm_retry_callback: object | None = None,
) -> InspectionReport:
    body = strip_style(document)
    text = visible_text(body)
    findings: List[InspectionFinding] = []
    metrics = collect_metrics(body, text, sample_htmls, topic)
    if isinstance(density_profile, Mapping):
        metrics["density_profile"] = dict(density_profile)
    metrics["inspection_profile"] = final_inspection_profile(inspection_mode, scope)

    findings.extend(check_template_structure(document, template_html))
    findings.extend(check_required_sections(text, scope, template_type))
    findings.extend(check_guide_compliance(body, text, template_type))
    findings.extend(check_template_guide_rules(body, text, template_type, scope))
    findings.extend(check_chapter_consistency(body, scope))
    findings.extend(check_connection_integrity(body, scope))
    findings.extend(check_sample_parity(metrics, template_type, scope, topic, density_profile=density_profile))
    findings.extend(check_topic_specificity(text, topic, scope))
    findings.extend(check_internal_code_leakage(body, text, topic, scope))
    findings.extend(check_topic_required_axes(text, topic, scope))
    findings.extend(check_user_brief_alignment(text, brief, scope))
    findings.extend(
        run_llm_inspector(
            document,
            body,
            text,
            findings,
            metrics,
            template_type,
            scope,
            topic,
            brief,
            inspection_mode,
            llm_client,
            llm_required,
            llm_retry_callback,
        )
    )

    score_details = calculate_score_details(findings)
    metrics["score_breakdown"] = score_details
    score = int(score_details["score"])
    status = "fail" if any(f.severity == "error" for f in findings) else "warn" if findings else "pass"
    summary = make_summary(status, score, findings, metrics)
    return InspectionReport(
        status=status,
        score=score,
        scope=scope,
        checked_at=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        findings=findings,
        metrics=metrics,
    )


def inspect_policy_json_spec(
    spec: Mapping[str, object],
    *,
    template_type: str = "simple",
    scope: str = "full",
    chapter_key: str = "",
    topic: str = "",
    brief: str = "",
    llm_client: object | None = None,
    llm_required: bool = False,
    llm_retry_callback: object | None = None,
) -> InspectionReport:
    """Inspect policy content from JSON. HTML rendering is checked separately at finalization."""
    metrics = collect_json_metrics(spec, scope)
    metrics["local_precheck"] = local_precheck_metrics(json_local_precheck(spec, scope))
    findings = check_json_stage_rules(spec, scope)
    findings.extend(
        run_llm_json_inspector(
            spec=spec,
            deterministic_findings=findings,
            metrics=metrics,
            template_type=template_type,
            scope=scope,
            chapter_key=chapter_key,
            topic=topic,
            brief=brief,
            llm_client=llm_client,
            llm_required=llm_required,
            llm_retry_callback=llm_retry_callback,
        )
    )
    score_details = calculate_score_details(findings)
    metrics["score_breakdown"] = score_details
    score = int(score_details["score"])
    status = "fail" if any(f.severity == "error" for f in findings) else "warn" if findings else "pass"
    summary = make_summary(status, score, findings, metrics)
    return InspectionReport(
        status=status,
        score=score,
        scope=scope,
        checked_at=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        findings=findings,
        metrics=metrics,
    )


def merge_inspection_reports(
    primary: InspectionReport,
    secondary: InspectionReport,
    *,
    source_key: str = "secondary_inspector",
) -> InspectionReport:
    """Merge deterministic JSON findings into another report.

    Final inspection is usually HTML-oriented, but some quality risks are only
    visible in the structured spec after later chapters update earlier links.
    Merging keeps the user-facing report single while preserving where the
    extra findings came from.
    """

    findings = [*list(primary.findings or []), *list(secondary.findings or [])]
    metrics = dict(primary.metrics or {})
    metrics[source_key] = {
        "status": secondary.status,
        "score": secondary.score,
        "summary": secondary.summary,
        "finding_count": len(secondary.findings or []),
        "metrics": secondary.metrics,
    }
    score_details = calculate_score_details(findings)
    metrics["score_breakdown"] = score_details
    score = int(score_details["score"])
    status = "fail" if any(f.severity == "error" for f in findings) else "warn" if findings else "pass"
    summary = make_summary(status, score, findings, metrics)
    return InspectionReport(
        status=status,
        score=score,
        scope=primary.scope,
        checked_at=primary.checked_at,
        summary=summary,
        findings=findings,
        metrics=metrics,
    )


def save_inspection_report(report: InspectionReport, target_name: str, suffix: str = "") -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", target_name)
    suffix_part = f"_{suffix}" if suffix else ""
    path = REPORTS_DIR / f"{safe_name}{suffix_part}_inspection.json"
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_sample_htmls(template_type: str) -> List[str]:
    samples_dir = PROJECT_ROOT / "input" / "samples"
    if not samples_dir.exists():
        return []
    htmls: List[str] = []
    for path in sorted(samples_dir.glob("*.html")):
        normalized_name = unicodedata.normalize("NFC", path.name)
        if template_type == "full" and "full" not in normalized_name.casefold():
            continue
        if template_type != "full" and "간소화" not in normalized_name:
            continue
        try:
            htmls.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return htmls


def repair_policy_document(document: str, report: InspectionReport) -> str:
    repaired = document
    repaired = re.sub(r"\{[^}]+\}", "", repaired)
    repaired = repaired.replace("TBD", "미정 항목은 결정 주체, 결정 필요 사유, 결정 기한과 함께 관리한다.")
    repaired = repaired.replace("<h3>가.<br/>", "<h3>가. ")
    repaired = repaired.replace("<h3>나.<br/>", "<h3>나. ")
    repaired = repaired.replace("<h3>다.<br/>", "<h3>다. ")
    repaired = repaired.replace("<h3>라.<br/>", "<h3>라. ")
    return repaired


def check_template_structure(document: str, template_html: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if "<style>" not in document or ".page" not in document:
        findings.append(error("양식", "템플릿 스타일 누락", "문서에 템플릿 CSS 또는 .page 레이아웃이 없습니다.", "템플릿의 <style> 영역을 유지해야 합니다."))
    if '<div class="page">' not in document:
        findings.append(error("양식", "페이지 컨테이너 누락", "문서 본문이 .page 컨테이너 안에 작성되지 않았습니다.", "기존 HTML 구조의 .page 컨테이너를 유지해야 합니다."))
    if template_html and ".page" in template_html and ".page" not in document:
        findings.append(error("양식", "템플릿 구조 불일치", "기준 템플릿의 핵심 스타일이 결과 문서에 반영되지 않았습니다.", "템플릿 CSS와 기본 구조를 보존하세요."))
    return findings


def check_required_sections(text: str, scope: str, template_type: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    required = list(required_sections_for_scope(scope))
    for label in required:
        if label not in text:
            findings.append(error("구조", "필수 장 누락", f"'{label}' 장 또는 절이 없습니다.", "AGENTS.md의 장별 작성 순서를 유지하세요."))
    if scope in {"07_functions", "08_policies", "09_final", "full"} and template_type == "full":
        for label in ("나. 프로세스 상세", "나. 기능 상세"):
            if label not in text:
                findings.append(error("구조", "Full 상세 장 누락", f"Full 버전에 필요한 '{label}' 장이 없습니다.", "Full 버전은 프로세스 상세와 기능 상세를 포함해야 합니다."))
    return findings


def required_sections_for_scope(scope: str) -> Iterable[str]:
    cumulative_sections = [
        ("cover", ("통합채널 정책서", "0. 문서 히스토리")),
        ("overview", ("1. 개요", "가. 범위", "나. 설계 원칙")),
        ("terms", ("2. 주요 용어",)),
        ("actors", ("3. 유즈케이스 정의", "가. 액터")),
        ("usecases", ("나. 유즈케이스",)),
        ("usecase_diagram", ("다. 유즈케이스 다이어그램",)),
        ("state", ("라. 상태 전이표",)),
        ("process", ("4. 프로세스 정의", "가. 프로세스 목록", "전체 업무 흐름도")),
        ("functions", ("5. 기능 정의", "가. 기능 목록")),
        ("policies", ("6. 정책 정의", "가. 정책 목록", "나. 정책 상세")),
        ("final_check", ("최종 점검 기준",)),
    ]
    rank = scope_rank(scope)
    if rank:
        required: List[str] = []
        for index, (_, labels) in enumerate(cumulative_sections, 1):
            if index > rank + 1:
                break
            required.extend(labels)
        return dedupe(required)
    if scope == "full":
        return SECTION_REQUIREMENTS["full"]
    ordered = list(SECTION_REQUIREMENTS)
    collected: List[str] = []
    for key in ordered:
        if key == "full":
            continue
        collected.extend(SECTION_REQUIREMENTS[key])
        if key == scope:
            break
    return collected


def scope_rank(scope: str) -> int:
    ranks = {
        "01_overview": 1,
        "02_terms": 2,
        "03_actors": 3,
        "04_usecases": 4,
        "05_usecase_diagram": 5,
        "06_state": 6,
        "07_process": 7,
        "08_functions": 8,
        "09_policies": 9,
        "09_process_detail": 9,
        "09_function_detail": 9,
        "process_detail": 9,
        "function_detail": 9,
        "10_final_check": 10,
        "03_overview": 1,
        "04_terms": 2,
        "05_usecases": 6,
        "06_process": 7,
        "07_functions": 8,
        "08_policies": 9,
        "09_final": 10,
    }
    return ranks.get(scope, 10 if scope == "full" else 0)


def check_guide_compliance(body: str, text: str, template_type: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    body_without_code = strip_code_like_blocks(strip_style(body))
    if re.search(r"\{[^}]+\}", body_without_code):
        findings.append(error("가이드", "미치환 placeholder 존재", "결과 문서 본문에 템플릿 placeholder가 남아 있습니다.", "모든 placeholder를 실제 정책서 내용으로 치환하세요."))
    if "작성 가이드" in text or ("템플릿" in text and "정책서" not in text):
        findings.append(warn("가이드", "작성 가이드 문구 잔존", "최종 정책서에 작성 가이드성 문구가 남아 있을 수 있습니다.", "최종 산출물에는 작성 가이드가 아니라 정책 내용만 남기세요."))
    forbidden_text = text.replace("운영 검토 필요", "운영 확인 필요")
    for phrase in FORBIDDEN_POLICY_PHRASES:
        if phrase in forbidden_text:
            findings.append(error("가이드", "금지 표현 사용", f"정책 상세에 부적합한 표현 '{phrase}'가 있습니다.", "결정 주체, 기준값, 제한 조건, 후속 처리 기준을 명확히 쓰세요."))
    if has_sentence_break_issue(body):
        findings.append(warn("양식", "문장 줄바꿈 점검 필요", "마침표 뒤 <br/> 줄바꿈이 누락된 문장이 있을 수 있습니다.", "문장 마침표 뒤에는 <br/>를 적용하세요."))
    if has_customer_state_as_actor(body):
        findings.append(warn("가이드", "고객 상태 액터 분리 위험", "로그인/비로그인 고객은 액터가 아니라 상태·권한 조건으로 관리해야 합니다.", "액터는 독립 책임 주체만 작성하세요."))
    return findings


def check_template_guide_rules(body: str, text: str, template_type: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    findings.extend(check_scope_guide(body, text, scope))
    findings.extend(check_actor_usecase_guide(body, scope))
    findings.extend(check_state_guide(body, scope))
    findings.extend(check_diagram_guide(body, scope))
    findings.extend(check_process_guide(body, scope))
    findings.extend(check_function_guide(body, scope))
    findings.extend(check_policy_guide(body, text, scope))
    findings.extend(check_final_gate_guide(text, scope, template_type))
    findings.extend(check_excluded_detail_guide(text, scope))
    findings.extend(check_concision_guide(body, scope))
    return findings


def check_scope_guide(body: str, text: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "overview"):
        return []
    findings: List[InspectionFinding] = []
    overview = extract_text_section(text, "1. 개요", "2. 주요 용어")
    target = overview or text
    requirements = {
        "대상 업무": ("정책서", "업무", "정의"),
        "대상 채널": ("앱", "웹"),
        "대상 고객": ("고객",),
        "포함 범위": ("포함",),
        "제외 범위": ("제외",),
        "후속 상세화 영역": ("후속", "상세화", "화면 설계", "기능 상세"),
    }
    missing = [
        label
        for label, keywords in requirements.items()
        if not any(keyword in target for keyword in keywords)
    ]
    if missing:
        findings.append(
            warn(
                "템플릿 가이드",
                "개요 범위 6요소 부족",
                f"범위 장에서 템플릿이 요구하는 요소가 약합니다: {', '.join(missing)}",
                "범위에는 대상 업무, 대상 채널, 대상 고객, 포함 범위, 제외 범위, 후속 산출물 상세화 영역을 모두 드러내세요.",
            )
        )
    principle_count = len(re.findall(r'<p\s+class=["\'][^"\']*\bprinciple-text\b', body))
    if principle_count and not 4 <= principle_count <= 6:
        findings.append(
            warn(
                "템플릿 가이드",
                "설계 원칙 수량 부적정",
                f"설계 원칙이 {principle_count}개입니다.",
                "템플릿 기준에 따라 설계 원칙은 4~6개로 제한하세요.",
            )
        )
    return findings


def check_concision_guide(body: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    body_without_code = strip_code_like_blocks(body)
    if "&lt;br" in body_without_code.casefold():
        findings.append(
            warn(
                "양식",
                "줄바꿈 태그 문자 노출",
                "본문에 <br/>이 실제 줄바꿈 태그가 아니라 문자로 노출된 부분이 있습니다.",
                "JSON 원문에는 <br/>를 넣지 말고 렌더링 단계에서 줄바꿈을 적용하세요.",
            )
        )

    rank = scope_rank(scope)
    cells = table_cell_texts(body)
    if not cells:
        return findings

    max_cell = max(len(cell) for cell in cells)
    avg_cell = sum(len(cell) for cell in cells) / len(cells)
    if rank <= 4 and max_cell > 180:
        findings.append(
            warn(
                "문체",
                "초기 장 표 설명 장황",
                f"표 셀 최대 길이가 {max_cell}자로 샘플 간소화본 대비 깁니다.",
                "개요·용어·액터·유즈케이스는 한 문장 설명만 남기고 세부 기준은 후속 장으로 이동하세요.",
            )
        )
    elif 5 <= rank <= 8 and (max_cell > 220 or avg_cell > 80):
        findings.append(
            warn(
                "문체",
                "표 설명 밀도 과다",
                f"표 셀 평균 {avg_cell:.1f}자, 최대 {max_cell}자로 설명이 길어질 위험이 있습니다.",
                "긴 설명 대신 행을 분리하고 관련 정책명으로 판단 기준을 연결하세요.",
            )
        )

    policy_contents = policy_item_content_texts(body)
    if rank >= 9 and policy_contents:
        max_policy = max(len(item) for item in policy_contents)
        if max_policy > 180:
            findings.append(
                warn(
                    "문체",
                    "정책 항목 다중 기준 포함",
                    f"정책 상세 content 최대 길이가 {max_policy}자입니다.",
                    "정책 상세 한 항목에는 하나의 기준만 담고, 기준값·예외·고지·이력은 별도 항목으로 분리하세요.",
                )
            )
    return findings


def check_actor_usecase_guide(body: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "usecases"):
        return []
    findings: List[InspectionFinding] = []
    actor_rows = table_rows_with_prefix(body, "ACT-")
    actor_names = {row["texts"][1] for row in actor_rows if len(row["texts"]) >= 2}
    usecase_actor_names = {
        row["texts"][1]
        for row in table_rows_with_prefix(body, "US-")
        if len(row["texts"]) >= 2
    }
    missing_actors = sorted(actor_names - usecase_actor_names)
    if missing_actors:
        findings.append(
            error(
                "챕터 정합성",
                "액터별 유즈케이스 누락",
                "액터 목록에 정의되었지만 유즈케이스에서 한 번도 사용되지 않은 액터가 있습니다: "
                + ", ".join(missing_actors[:8]),
                "3.가 액터에 정의한 모든 독립 책임 주체는 3.나 유즈케이스에서 최소 1개 이상의 주/보조 유즈케이스로 연결하세요.",
            )
        )
    usecase_rows = table_rows_with_prefix(body, "US-")
    y_rows = [row for row in usecase_rows if len(row["texts"]) >= 5 and row["texts"][4].strip().upper() == "Y"]
    step_like_names = [
        row["texts"][2]
        for row in y_rows
        if len(row["texts"]) >= 3 and is_step_like_usecase_name(row["texts"][2])
    ]
    if step_like_names:
        findings.append(
            error(
                "템플릿 가이드",
                "절차형 유즈케이스 분리",
                "process_target=Y 유즈케이스에 절차 단계가 포함되어 있습니다: " + ", ".join(step_like_names[:8]),
                "약관 동의, 본인인증, 입력, 조건 확인, 결과 안내 같은 단계는 상위 업무 목적 유즈케이스의 프로세스로 내려 작성하세요.",
                target_path="current_chapter.usecases[*].name",
                root_cause="process_target=Y usecase was written at process-step granularity",
                required_change="절차 단계명 유즈케이스를 고객·운영자가 완료하려는 상위 업무 목적명으로 병합·확대한다.",
                patch_hint="약관 동의, 인증, 입력, 조건 확인, 결과 안내는 유즈케이스가 아니라 해당 유즈케이스의 프로세스·상태·정책으로 내린다.",
                acceptance_check="process_target=Y 유즈케이스명에 약관 동의, 인증, 정보 입력, 조건 확인, 결과 확인 같은 절차 단계 표현이 남지 않아야 한다.",
            )
        )
    if len(y_rows) > 8 or (len(y_rows) > 6 and step_like_names):
        findings.append(
            warn(
                "템플릿 가이드",
                "유즈케이스 과분해",
                f"프로세스 정의 대상 Y 유즈케이스가 {len(y_rows)}개로 많고 절차 단계가 유즈케이스로 분리됐을 수 있습니다: "
                + ", ".join(step_like_names[:6]),
                "대상 확인, 조건 확인, 인증 복귀, 사유 확인, 완료 확인은 상위 사람 액터 유즈케이스의 프로세스·상태·정책으로 내려 작성하세요.",
            )
        )
    for row in usecase_rows:
        cells = row["texts"]
        if len(cells) < 5:
            continue
        usecase_id, actor, target = cells[0], cells[1], cells[4].strip().upper()
        if is_human_actor(actor) and target != "Y":
            findings.append(
                error(
                    "템플릿 가이드",
                    "사람 액터 유즈케이스 Y 누락",
                    f"{usecase_id}의 액터 '{actor}'는 사람이 수행하는 주체인데 프로세스 정의 대상이 {target or '비어 있음'}입니다.",
                    "고객, 운영자, 법정대리인, 대리인 유즈케이스는 원칙적으로 프로세스 정의 대상 Y로 작성하세요.",
                )
            )
        if is_system_actor(actor) and target != "N":
            findings.append(
                warn(
                    "템플릿 가이드",
                    "시스템 액터 유즈케이스 N 점검",
                    f"{usecase_id}의 액터 '{actor}'는 시스템/기관 성격인데 프로세스 정의 대상이 {target or '비어 있음'}입니다.",
                    "BSS, 인증기관, 연계 시스템의 조회·검증·저장 유즈케이스는 원칙적으로 N으로 두고 고객 프로세스 안의 기능·정책으로 반영하세요.",
                )
            )
    return findings


def transition_state_cells(cells: Sequence[str]) -> Optional[Tuple[str, str]]:
    """Return current/next state cells for both 4-column and 5-column transition tables."""
    normalized = [str(cell).strip() for cell in cells]
    if not normalized or "현재 상태" in normalized or "다음 상태" in normalized:
        return None
    if len(normalized) >= 5:
        current_state = normalized[1]
        next_state = normalized[3]
    elif len(normalized) >= 4:
        current_state = normalized[0]
        next_state = normalized[2]
    else:
        return None
    if not current_state or not next_state:
        return None
    return current_state, next_state


def check_state_guide(body: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "state"):
        return []
    findings: List[InspectionFinding] = []
    state_rows = table_rows_with_prefix(body, "ST-")
    state_names = {row["texts"][1] for row in state_rows if len(row["texts"]) >= 2}
    state_text = " ".join(state_names)
    if state_names and not any(keyword in state_text for keyword in ("실패", "제한", "보류", "운영", "예외")):
        findings.append(
            warn(
                "템플릿 가이드",
                "예외·제한 상태 부족",
                "상태 코드 목록에 실패, 제한, 보류, 운영 확인 같은 예외 상태가 약합니다.",
                "상태는 정상 흐름뿐 아니라 실패, 제한, 보류, 운영 확인 필요 상태를 함께 정의하세요.",
            )
        )

    transition_html = extract_html_between(body, "2) 상태 전이 기준", "3) 상태 전이 다이어그램")
    for row in table_rows(transition_html):
        cells = row["texts"]
        state_pair = transition_state_cells(cells)
        if not state_pair:
            continue
        current_state, next_state = state_pair
        if state_names and (current_state not in state_names or next_state not in state_names):
            findings.append(
                error(
                    "템플릿 가이드",
                    "상태 전이명 불일치",
                    f"상태 전이표의 '{current_state} → {next_state}' 중 상태 코드 목록에 없는 상태명이 있습니다.",
                    "상태 전이표의 현재 상태와 다음 상태는 상태 코드 목록의 상태명과 정확히 일치해야 합니다.",
                )
            )
    transition_text = visible_text(transition_html)
    if transition_text and not any(keyword in transition_text for keyword in ("실패", "예외", "재시도", "상담", "보류", "제한")):
        findings.append(
            warn(
                "템플릿 가이드",
                "상태 전이 예외 기준 부족",
                "상태 전이 기준에 실패, 예외, 재시도, 상담 전환 같은 후속 기준이 약합니다.",
                "전이 조건에는 실패 시 상태, 재시도 가능 여부, 고객 안내, 이력 저장, 상담 전환 기준을 필요한 만큼 포함하세요.",
            )
        )
    return findings


def check_diagram_guide(body: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if stage_reached(scope, "usecase_diagram"):
        diagram = extract_html_between_markers(
            body,
            ("<h3>다. 유즈케이스 다이어그램", "<h3>다.<br/>유즈케이스 다이어그램"),
            ("<h3>라. 상태 전이표", "<h3>라.<br/>상태 전이표", "<h2>4. 프로세스 정의"),
        )
        diagram_text = visible_text(diagram)
        if diagram and not diagram_has_usecase_relationships(diagram, diagram_text):
            findings.append(warn("템플릿 가이드", "유즈케이스 관계 표현 부족", "유즈케이스 다이어그램에서 액터와 유즈케이스 관계를 확인하기 어렵습니다.", "템플릿의 diagram-wrap 영역에 액터, 유즈케이스, association/include 관계가 드러나도록 표현하세요."))
    if stage_reached(scope, "state"):
        diagram = extract_html_between_markers(
            body,
            ("<h4>3) 상태 전이 다이어그램",),
            ("<h2>4. 프로세스 정의",),
        )
        if diagram and "ST-" not in diagram and not diagram_has_visual_flow(diagram):
            findings.append(warn("템플릿 가이드", "상태 다이어그램 코드 표기 부족", "상태 전이 다이어그램에 상태 코드가 함께 표기되지 않았습니다.", "상태 코드를 노드로, 전이 이벤트를 화살표로 표현하세요."))
    if stage_reached(scope, "process"):
        diagram = extract_html_between_markers(
            body,
            ("<h3>나. 전체 업무 흐름도", "<h3>나.<br/>전체 업무 흐름도", "<h3>다. 전체 업무 흐름도", "<h3>다.<br/>전체 업무 흐름도"),
            ("<h2>5. 기능 정의",),
        )
        if diagram and not diagram_has_process_flow(diagram):
            findings.append(warn("템플릿 가이드", "업무 흐름도 프로세스 흐름 약함", "전체 업무 흐름도에서 프로세스 흐름을 확인하기 어렵습니다.", "시작, 판단, 처리, 결과, 예외 흐름이 드러나도록 diagram-wrap 영역을 보완하세요."))
        if diagram and diagram_has_wrapped_process_flow(diagram):
            findings.append(
                warn(
                    "템플릿 가이드",
                    "업무 흐름도 접힘 배치",
                    "전체 업무 흐름도에서 프로세스가 다음 줄로 접히며 되돌아가는 선처럼 보일 수 있습니다.",
                    "유즈케이스별 프로세스는 Start에서 End까지 좌→우 단일 흐름으로 배치하고, 프로세스가 많으면 도식 폭을 넓혀 가로 스크롤로 표현하세요.",
                )
            )
        diagram_text = visible_text(diagram)
        if diagram_text and not any(keyword in diagram_text for keyword in ("실패", "예외", "제한", "분기", "보류", "Gateway")):
            findings.append(warn("템플릿 가이드", "업무 흐름도 예외 흐름 부족", "전체 업무 흐름도에서 정상 흐름과 예외·분기 흐름의 구분이 약합니다.", "정책 분기, 실패·예외 처리 흐름을 업무 흐름도에 함께 표현하세요."))
    return findings


def extract_html_between_markers(document: str, start_markers: Sequence[str], end_markers: Sequence[str]) -> str:
    starts = [
        (index, marker)
        for marker in start_markers
        for index in [document.find(marker)]
        if index >= 0
    ]
    if not starts:
        return ""
    start_index, marker = min(starts, key=lambda item: item[0])
    search_from = start_index + len(marker)
    ends = [
        index
        for marker in end_markers
        for index in [document.find(marker, search_from)]
        if index >= 0
    ]
    end_index = min(ends) if ends else len(document)
    return document[start_index:end_index]


def diagram_has_visual_flow(diagram_html: str) -> bool:
    return bool(re.search(r"<svg\b|<pre\b[^>]*class=[\"'][^\"']*mermaid|-->|→|⇒|->", diagram_html, flags=re.IGNORECASE))


def diagram_has_usecase_relationships(diagram_html: str, diagram_text: str) -> bool:
    if "uml-usecase-diagram" in diagram_html or "UML 2.0 Use Case Diagram" in diagram_html:
        return True
    if diagram_has_visual_flow(diagram_html):
        return True
    return bool(
        diagram_text
        and any(keyword in diagram_text for keyword in ("US-", "UC-", "유즈케이스", "액터", "include", "association", "→", "->"))
    )


def diagram_has_process_flow(diagram_html: str) -> bool:
    if "bpmn-process-diagram" in diagram_html or "BPMN 2.0 Process Diagram" in diagram_html:
        return True
    if diagram_has_visual_flow(diagram_html):
        return True
    diagram_text = visible_text(diagram_html)
    return bool(diagram_text and any(keyword in diagram_text for keyword in ("PR-", "프로세스", "시작", "판단", "처리", "완료", "흐름")))


def diagram_has_wrapped_process_flow(diagram_html: str) -> bool:
    if "bpmn-process-diagram" not in diagram_html:
        return False
    return bool(re.search(r"<path\b[^>]*class=[\"'][^\"']*\bflow\b", diagram_html, flags=re.IGNORECASE))


def check_process_guide(body: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "process"):
        return []
    findings: List[InspectionFinding] = []
    related_function_counts: List[int] = []
    function_names = table_names_by_prefix(body, "FN-")
    policy_names = table_names_by_prefix(body, "PG-")
    for row in table_rows_with_prefix(body, "PR-"):
        cells = row["texts"]
        html_cells = row["htmls"]
        if len(cells) < 5:
            continue
        process_id, name, description, related_functions, related_policies = cells[:5]
        if stage_reached(scope, "functions") and not related_functions.strip():
            findings.append(error("템플릿 가이드", "프로세스 관련 기능 누락", f"{process_id} '{name}'에 관련 기능이 없습니다.", "모든 프로세스는 실제 구현 또는 시스템 처리가 필요한 관련 기능 ID와 기능명을 가져야 합니다."))
        if stage_reached(scope, "functions") and related_functions.strip():
            related_function_counts.append(count_line_items(html_cells[3]) if len(html_cells) >= 4 else 1)
        if stage_reached(scope, "policies") and not related_policies.strip():
            findings.append(error("템플릿 가이드", "프로세스 관련 정책 누락", f"{process_id} '{name}'에 관련 정책이 없습니다.", "조건, 제한, 안내 기준이 있는 프로세스는 정책 목록의 정책 ID와 정책명을 연결해야 합니다."))
        if (
            stage_reached(scope, "functions")
            and related_functions.strip()
            and "FN-" not in related_functions
            and not cell_items_match_known_names(html_cells[3] if len(html_cells) >= 4 else related_functions, function_names)
        ):
            findings.append(warn("템플릿 가이드", "관련 기능 ID 누락", f"{process_id}의 관련 기능에 기능 ID가 없습니다.", "프로세스 목록의 관련 기능은 기능 정의의 기능 ID와 기능명을 함께 작성하세요."))
        if (
            stage_reached(scope, "policies")
            and related_policies.strip()
            and "PG-" not in related_policies
            and not cell_items_match_known_names(html_cells[4] if len(html_cells) >= 5 else related_policies, policy_names)
        ):
            findings.append(warn("템플릿 가이드", "관련 정책 ID 누락", f"{process_id}의 관련 정책에 정책 ID가 없습니다.", "프로세스 목록의 관련 정책은 정책 목록의 정책 ID와 정책명을 함께 작성하세요."))
        if description and not any(keyword in description for keyword in PROCESS_KEYWORDS):
            findings.append(warn("템플릿 가이드", "프로세스 설명 처리 기준 약함", f"{process_id} 설명이 고객 경험 순서나 처리 기준을 충분히 드러내지 못할 수 있습니다.", "프로세스 설명에는 조회, 검증, 조건 판단, 입력, 인증·동의, 처리 요청, 결과 안내 중 필요한 처리 목적을 명확히 쓰세요."))
    if len(related_function_counts) >= 8:
        single_count = sum(1 for count in related_function_counts if count == 1)
        if single_count == len(related_function_counts):
            findings.append(error("템플릿 가이드", "프로세스-기능 1:1 고착", "모든 프로세스가 관련 기능을 1개씩만 갖고 있어 기능 입자도가 프로세스와 동일해졌습니다.", "샘플처럼 복합 프로세스에는 조회·검증·저장·알림·연동·이력 기능을 복수로 연결하고, 공통 기능은 여러 프로세스에서 재사용하세요."))
        elif single_count >= int(len(related_function_counts) * 0.85):
            findings.append(warn("템플릿 가이드", "프로세스별 기능 과소 연결", f"{len(related_function_counts)}개 프로세스 중 {single_count}개가 관련 기능 1개만 갖습니다.", "단순 프로세스는 기능 1개도 가능하지만, 문서 전체가 1:1 구조로 굳지 않도록 복합 프로세스의 기능 분해와 공통 기능 재사용을 보완하세요."))
    return findings


def table_names_by_prefix(document: str, prefix: str) -> set[str]:
    names = set()
    for row in table_rows_with_prefix(document, prefix):
        cells = row["texts"]
        if len(cells) >= 2 and cells[1]:
            names.add(cells[1])
    return names


def cell_items_match_known_names(cell_html: str, known_names: set[str]) -> bool:
    if not known_names:
        return False
    items = split_cell_items(cell_html)
    return bool(items) and all(item in known_names or text_can_be_segmented_by_known_names(item, known_names) for item in items)


def text_can_be_segmented_by_known_names(text: str, known_names: set[str]) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return False
    names = sorted({re.sub(r"\s+", " ", name).strip() for name in known_names if name}, key=len, reverse=True)
    remaining = normalized
    matched = 0
    while remaining:
        remaining = remaining.strip(" ,;/·")
        candidate = next(
            (
                name
                for name in names
                if remaining == name or remaining.startswith(name + " ")
            ),
            "",
        )
        if not candidate:
            return False
        matched += 1
        remaining = remaining[len(candidate) :].strip()
    return matched > 0


def check_function_guide(body: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "functions"):
        return []
    findings: List[InspectionFinding] = []
    function_rows = dedupe_rows_by_first_cell(table_rows_with_prefix(body, "FN-"))
    detail_signatures: List[tuple[str, ...]] = []
    generic_name_count = 0
    sentence_like_detail_count = 0
    sentence_like_examples: List[str] = []
    for row in function_rows:
        cells = row["texts"]
        html_cells = row["htmls"]
        if len(cells) < 4:
            continue
        function_id, name, description = cells[:3]
        if name.endswith(" 기능"):
            generic_name_count += 1
        detail_items = [re.sub(r"\s+", " ", item).strip() for item in split_cell_items(html_cells[3])] if len(html_cells) >= 4 else []
        if detail_items:
            detail_signatures.append(tuple(detail_items))
            for detail_item in detail_items:
                if function_detail_item_is_sentence_like(detail_item):
                    sentence_like_detail_count += 1
                    if len(sentence_like_examples) < 3:
                        sentence_like_examples.append(detail_item)
        detail_count = count_line_items(html_cells[3]) if len(html_cells) >= 4 else 0
        if detail_count < 2:
            findings.append(error("템플릿 가이드", "기능 세부 구성 부족", f"{function_id} '{name}'의 세부 기능 구성이 2개 미만입니다.", "세부 기능 구성은 조회, 검증, 입력, 저장, 알림, 연동, 결과 확인 등 2~5개 하위 처리로 작성하세요."))
        if detail_count > 6:
            findings.append(warn("템플릿 가이드", "기능 세부 구성 과다", f"{function_id} '{name}'의 세부 기능 구성이 과도하게 많습니다.", "기능이 너무 크면 구현 범위가 불명확하므로 업무 완결 단위로 분리하세요."))
        if description and not any(keyword in description for keyword in ("처리", "결과", "생성", "제공", "확인", "안내", "저장", "반영", "조회", "검증", "판정", "분류", "산정", "연결", "관리", "전환", "수집", "유지", "갱신", "제한", "마스킹", "비교", "추적", "발급", "종료", "구성", "등록")):
            findings.append(warn("템플릿 가이드", "기능 설명 결과 기준 약함", f"{function_id} 설명이 '무엇을 처리해 어떤 결과를 만드는지'를 충분히 드러내지 못할 수 있습니다.", "기능 설명은 화면 위치가 아니라 처리 결과 중심으로 작성하세요."))
    if len(function_rows) >= 10 and detail_signatures:
        repeated_count = max(detail_signatures.count(signature) for signature in set(detail_signatures))
        if repeated_count >= max(5, int(len(function_rows) * 0.30)):
            findings.append(
                warn(
                    "템플릿 가이드",
                    "기능 세부 구성 반복",
                    f"동일한 세부 기능 구성이 {repeated_count}개 기능에서 반복됩니다.",
                    "기능은 프로세스명을 복사하지 말고 조회, 검증, 산정, 저장, 연동, 모니터링 등 실제 처리 역량 단위로 분리하세요.",
                    target_path="current_chapter.functions[*].details",
                    root_cause="여러 기능이 동일한 세부 기능 구성을 공유해 기능별 처리 책임 차이가 드러나지 않습니다.",
                    required_change="반복되는 functions[*].details를 기능별 조회, 검증, 산정, 저장, 알림, 연동, 이력 처리 단위로 분리합니다.",
                    patch_hint="각 기능의 process_ids와 description을 기준으로 details 2~5개를 서로 다른 하위 처리명으로 재작성합니다.",
                    acceptance_check="동일 details 조합이 전체 기능의 30% 이상 반복되지 않아야 합니다.",
                    keep_constraints="기능 ID, process_id, process_ids 연결은 유지합니다.",
                    do_not_change="지적되지 않은 프로세스와 정책 연결은 변경하지 않습니다.",
                )
            )
    if sentence_like_detail_count:
        findings.append(
            warn(
                "템플릿 가이드",
                "기능 세부 구성 문장형 작성",
                f"세부 기능 구성 {sentence_like_detail_count}개가 샘플과 달리 문장형 설명으로 작성되어 있습니다. 예: {', '.join(sentence_like_examples)}",
                "세부 기능 구성은 '통합 검색창 제공', '입력값 정규화', '권한 상태 검증'처럼 짧은 하위 처리명으로 바꾸세요.",
            )
        )
    if len(function_rows) >= 10 and generic_name_count >= int(len(function_rows) * 0.70):
        findings.append(
            warn(
                "템플릿 가이드",
                "기능명 일반화",
                f"기능명 {generic_name_count}건이 '~ 기능' 형태로 끝나 기능의 처리 목적이 약합니다.",
                "기능명은 고객 상태 조회, 권한 기준 검증, 처리 이력 저장처럼 처리 단위와 결과를 드러내세요.",
                target_path="current_chapter.functions[*].name",
                root_cause="기능명이 '~ 기능'으로 일반화되어 처리 책임과 산출 결과를 구분하기 어렵습니다.",
                required_change="일반화된 functions[*].name을 조회, 검증, 산정, 저장, 안내, 연동 등 처리 결과가 드러나는 이름으로 변경합니다.",
                patch_hint="'대상 조건 조회', '가능 여부 검증', '처리 이력 저장'처럼 명사형 처리 단위로 바꿉니다.",
                acceptance_check="전체 기능 중 '~ 기능'으로 끝나는 이름이 70% 미만이어야 합니다.",
                keep_constraints="기능 ID와 연결된 process_ids는 유지합니다.",
                do_not_change="기능 개수와 정책 연결은 이름 수정에 필요한 범위를 넘겨 변경하지 않습니다.",
            )
        )
    return findings


def dedupe_rows_by_first_cell(rows: Sequence[Mapping[str, object]]) -> List[dict]:
    """Renderer can repeat reused functions under multiple process groups."""

    seen: set[str] = set()
    result: List[dict] = []
    for row in rows:
        texts = row.get("texts") if isinstance(row, Mapping) else None
        if not isinstance(texts, list) or not texts:
            continue
        key = str(texts[0]).strip()
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    return result


def function_detail_item_is_sentence_like(value: object) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return False
    return bool(
        text.endswith(".")
        or re.search(r"(한다|된다|받는다|만든다|남긴다|불러온다|표시한다|제공한다|반환한다)\.?$", text)
    )


def json_function_process_ids(function: Mapping[str, object]) -> List[str]:
    values: List[str] = []
    process_id = str(function.get("process_id", "")).strip()
    if process_id:
        values.append(process_id)
    raw = function.get("process_ids")
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw if str(item).strip())
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def check_function_granularity_by_json(
    processes: Sequence[Mapping[str, object]],
    functions: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    process_ids = [str(process.get("id", "")).strip() for process in processes if str(process.get("id", "")).strip()]
    if len(process_ids) < 8:
        return []
    counts = {process_id: 0 for process_id in process_ids}
    reused_function_ids: List[str] = []
    for function in functions:
        linked_process_ids = [process_id for process_id in json_function_process_ids(function) if process_id in counts]
        if len(linked_process_ids) > 1:
            reused_function_ids.append(str(function.get("id", "")).strip())
        for process_id in linked_process_ids:
            counts[process_id] += 1
    covered_counts = [count for count in counts.values() if count > 0]
    findings: List[InspectionFinding] = []
    single_count = sum(1 for count in covered_counts if count == 1)
    if len(covered_counts) == len(process_ids) and single_count == len(process_ids):
        findings.append(
            error(
                "JSON 정합성",
                "프로세스-기능 1:1 고착",
                "모든 프로세스가 기능 1개씩만 연결되어 유즈케이스 → 프로세스 → 기능 계층이 분리되지 않았습니다.",
                "샘플처럼 복합 프로세스에는 복수 기능을 연결하고, 공통 조회·인증·동의·이력·알림 기능은 동일 기능 ID를 여러 process_ids에 재사용하세요.",
            )
        )
    elif len(covered_counts) == len(process_ids) and single_count >= int(len(process_ids) * 0.85) and not reused_function_ids:
        findings.append(
            warn(
                "JSON 정합성",
                "프로세스별 기능 과소 연결",
                f"{len(process_ids)}개 프로세스 중 {single_count}개가 기능 1개만 갖고, 재사용 기능이 없습니다.",
                "기능은 프로세스명 복사가 아니라 처리 역량 단위입니다. 복합 프로세스의 기능 분해와 공통 기능 재사용을 보완하세요.",
            )
        )
    detail_signatures = [
        tuple(str(item).strip() for item in function.get("details", []) if str(item).strip())
        for function in functions
        if isinstance(function.get("details"), list)
        and any(str(item).strip() for item in function.get("details", []))
    ]
    if len(functions) >= 10 and detail_signatures:
        repeated_count = max(detail_signatures.count(signature) for signature in set(detail_signatures))
        if repeated_count >= max(5, int(len(functions) * 0.30)):
            findings.append(
                warn(
                    "JSON 정합성",
                    "기능 세부 구성 반복",
                    f"동일한 details 조합이 {repeated_count}개 기능에서 반복됩니다.",
                    "기능별 details는 프로세스명을 복사하지 말고 조회, 검증, 산정, 저장, 알림, 연동, 이력 같은 처리 역량 단위로 분리하세요.",
                    target_path="current_chapter.functions[*].details",
                    root_cause="JSON functions.details가 여러 기능에서 동일하게 반복되어 기능 입자도 차이가 사라졌습니다.",
                    required_change="반복되는 details를 각 기능의 처리 책임에 맞는 2~5개 하위 처리명으로 변경합니다.",
                    patch_hint="'대상 조건 조회', '권한 상태 검증', '처리 결과 저장'처럼 짧은 명사형 처리 단위로 구성합니다.",
                    acceptance_check="동일 details 조합이 전체 기능의 30% 이상 반복되지 않아야 합니다.",
                    keep_constraints="functions[*].id, process_id, process_ids는 유지합니다.",
                    do_not_change="프로세스와 정책 목록은 지적 없이 재작성하지 않습니다.",
                )
            )
    generic_names = [
        str(function.get("id", "")).strip() or str(index)
        for index, function in enumerate(functions)
        if str(function.get("name", "")).strip().endswith(" 기능")
    ]
    if len(functions) >= 10 and len(generic_names) >= int(len(functions) * 0.70):
        findings.append(
            warn(
                "JSON 정합성",
                "기능명 일반화",
                f"기능명 {len(generic_names)}건이 '~ 기능' 형태로 끝납니다: " + ", ".join(generic_names[:8]),
                "기능명은 처리 단위와 결과가 드러나는 명사형으로 작성하세요.",
                target_path="current_chapter.functions[*].name",
                root_cause="functions.name이 일반 표현으로 끝나 개발자가 기능 책임을 구분하기 어렵습니다.",
                required_change="'~ 기능'으로 끝나는 기능명을 조회, 검증, 산정, 저장, 안내, 연동, 이력 처리 결과가 드러나는 이름으로 변경합니다.",
                patch_hint="'고객 상태 조회', '권한 기준 검증', '처리 이력 저장'처럼 작성합니다.",
                acceptance_check="전체 기능 중 '~ 기능'으로 끝나는 이름이 70% 미만이어야 합니다.",
                keep_constraints="functions[*].id와 process_ids는 유지합니다.",
                do_not_change="기능명을 바꾸기 위해 프로세스/정책 구조를 재작성하지 않습니다.",
            )
        )
    return findings


def check_policy_guide(body: str, text: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "policies"):
        return []
    findings: List[InspectionFinding] = []
    if "TBD" in text:
        tbd_nearby = nearby_text(text, "TBD", 220)
        if not all(keyword in tbd_nearby for keyword in ("결정 주체", "결정 필요 사유", "결정 기한")):
            findings.append(error("템플릿 가이드", "TBD 보완 정보 누락", "TBD가 있으나 결정 주체, 결정 필요 사유, 결정 기한이 함께 작성되지 않았습니다.", "미정 항목은 TBD만 남기지 말고 결정 주체, 결정 필요 사유, 결정 기한을 함께 쓰세요."))
    policy_contents = re.findall(r'<div class="policy-item-content">(.*?)</div>', body, flags=re.DOTALL | re.IGNORECASE)
    weak_count = 0
    for content_html in policy_contents:
        content = visible_text(content_html)
        if not content or any(phrase in content for phrase in ("정책에 따라 처리", "가능하도록 한다", "추후 협의", "검토 필요")):
            weak_count += 1
    if weak_count:
        findings.append(
            warn(
                "템플릿 가이드",
                "정책 상세 판단 기준 약함",
                f"정책 상세 {weak_count}건이 비어 있거나 금지 표현 중심으로 작성되어 판단 기준으로 쓰기 어렵습니다.",
                "샘플처럼 짧은 정책값은 허용하되, 모호한 표현 대신 인증 수단, 가능 횟수, 유효시간, 제한 기간, 채널, 저장 항목 같은 실제 기능 동작값을 선언하세요.",
            )
        )
    policy_titles = [
        visible_text(html_unescape(title_html))
        for title_html in re.findall(r'<div class="policy-item-title"[^>]*>(.*?)</div>', body, flags=re.DOTALL | re.IGNORECASE)
    ]
    generic_title_count = sum(1 for title in policy_titles if any(keyword in title for keyword in ("적용 기준", "예외 기준", "이력 기준", "기본 적용 기준")))
    if len(policy_titles) >= 20 and generic_title_count / max(1, len(policy_titles)) >= 0.65:
        findings.append(
            error(
                "정책 구체성",
                "정책 상세 제목 반복",
                "정책 상세 제목이 '적용 기준/예외 기준/이력 기준' 중심으로 반복되어 주제별 판단 항목이 드러나지 않습니다.",
                "정책 항목명은 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 허용 입력 방식, 금칙어 유형, 신뢰도 판정 기준처럼 실제 동작값 단위로 작성하세요.",
            )
        )
    boilerplate_count = sum(
        1
        for content in policy_item_content_texts(body)
        if "고객 상태, 인증 결과, 동의 여부, 연계 시스템 응답" in content
        or "고객 영향도를 기준으로 재시도, 상담 전환, 운영 확인" in content
    )
    if boilerplate_count >= 5:
        findings.append(
            error(
                "정책 구체성",
                "정책 상세 템플릿 반복",
                f"정책 상세 {boilerplate_count}건이 공통 템플릿 문구로 반복되어 실제 판단값과 제한 기준이 약합니다.",
                "공통 문구를 반복하지 말고 정책 그룹별 허용 목록, 횟수, 시간, 제한 기간, 예외 불가 조건, 고지·이력 기준을 구체화하세요.",
            )
        )
    if "개인정보" not in text or not any(keyword in text for keyword in ("로그", "이력", "보관", "파기")):
        findings.append(warn("템플릿 가이드", "개인정보·로그 기준 부족", "정책 정의에 개인정보, 로그, 이력, 보관·파기 기준이 약합니다.", "정책 상세에는 개인정보·민감정보 보호와 처리 이력 저장 기준을 포함하세요."))
    if "BSS" not in text:
        findings.append(warn("템플릿 가이드", "BSS 판단 기준 부족", "정책서 본문에서 BSS 검증·판정·상태 변경·결과 회신 기준이 약합니다.", "채널 문서라도 BSS가 수행하는 검증, 판정, 상태 변경, 데이터 처리, 연계 결과 회신을 포함하세요."))
    return findings


def check_final_gate_guide(text: str, scope: str, template_type: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "final_check"):
        return []
    target = extract_text_section(text, "최종 점검 기준", "")
    if not target:
        return []
    findings: List[InspectionFinding] = []
    expected = {
        "범위 정합성": ("범위", "제외"),
        "고객 완결성": ("고객", "완료"),
        "연결성": ("유즈케이스", "프로세스", "기능", "정책"),
        "정책 구체성": ("정책", "기준"),
        "개인정보·로그 보호": ("개인정보", "로그", "이력", "보관"),
        "운영 관리": ("운영", "품질", "모니터링"),
        "요구사항 반영": ("요구사항",),
    }
    missing = [label for label, keywords in expected.items() if not any(keyword in target for keyword in keywords)]
    if missing:
        findings.append(
            warn(
                "템플릿 가이드",
                "최종 점검 기준 부족",
                f"최종 점검 기준에서 약한 항목: {', '.join(missing)}",
                "최종 점검 기준에는 범위, 고객 완결성, 연결성, 정책 구체성, 개인정보·로그, 운영 관리, 요구사항 반영 여부를 포함하세요.",
            )
        )
    if template_type == "full" and not all(keyword in target for keyword in ("프로세스 상세", "기능 상세")):
        findings.append(warn("템플릿 가이드", "Full 상세 점검 기준 부족", "Full 버전 최종 점검 기준에 프로세스 상세성과 기능 상세성 점검이 약합니다.", "Full 버전은 프로세스 상세와 기능 상세의 진입/종료 조건, 입력/출력, 실패·예외 케이스를 점검하세요."))
    return findings


def check_excluded_detail_guide(text: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if scope not in {"07_process", "08_functions", "09_policies", "10_final_check", "full"}:
        return findings
    used_terms = [term for term in UI_OVERDETAIL_TERMS if has_unexcluded_detail_term(text, term)]
    used_terms.extend(term for term in UI_CONTEXT_DETAIL_TERMS if has_ui_detail_design_context(text, term))
    if used_terms:
        findings.append(
            warn(
                "템플릿 가이드",
                "상세 설계/UI 표현 과다 위험",
                f"정책서 본문에 상세 설계 또는 UI 중심 표현이 포함되어 있습니다: {', '.join(used_terms)}",
                "화면 UI 상세, 버튼, 팝업, API 필드, DB 컬럼, 오류 코드 전체 목록은 제외하고 정책 판단 기준만 남기세요.",
            )
        )
    return findings


def check_chapter_consistency(body: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    actor_rows = table_rows_with_prefix(body, "ACT-")
    usecase_rows = table_rows_with_prefix(body, "US-")
    state_rows = table_rows_with_prefix(body, "ST-")
    process_rows = extract_process_rows(body)
    function_rows = [row for row in table_rows_with_prefix(body, "FN-") if len(row["texts"]) >= 4]
    policy_rows = table_rows_with_prefix(body, "PG-")

    actor_names = {row["texts"][1] for row in actor_rows if len(row["texts"]) >= 2}
    usecase_ids = {row["texts"][0] for row in usecase_rows if row["texts"]}
    state_names = {row["texts"][1] for row in state_rows if len(row["texts"]) >= 2}
    function_names = {row["texts"][1] for row in function_rows if len(row["texts"]) >= 2}
    function_names_by_id = {
        row["texts"][0]: row["texts"][1]
        for row in function_rows
        if len(row["texts"]) >= 2
    }
    policy_names = {row["texts"][1] for row in policy_rows if len(row["texts"]) >= 2}
    policy_ids = {row["texts"][0] for row in policy_rows if row["texts"]}
    policy_name_by_id = {
        row["texts"][0]: row["texts"][1]
        for row in policy_rows
        if len(row["texts"]) >= 2
    }

    if stage_reached(scope, "usecases"):
        for row in usecase_rows:
            cells = row["texts"]
            if len(cells) < 2:
                continue
            usecase_id, actor = cells[0], cells[1]
            if actor_names and actor not in actor_names:
                findings.append(
                    error(
                        "챕터 정합성",
                        "유즈케이스 액터 불일치",
                        f"{usecase_id}가 참조하는 액터 '{actor}'가 액터 목록에 없습니다.",
                        "유즈케이스의 액터명은 3.가 액터 목록의 액터명과 정확히 일치해야 합니다.",
                    )
                )

    if stage_reached(scope, "process"):
        y_usecases = {
            row["texts"][0]: {
                "name": row["texts"][2] if len(row["texts"]) >= 3 else row["texts"][0],
                "actor": row["texts"][1] if len(row["texts"]) >= 2 else "",
            }
            for row in usecase_rows
            if len(row["texts"]) >= 5 and row["texts"][4].strip().upper() == "Y"
        }
        process_usecase_ids = {row.get("usecase_id", "") for row in process_rows}
        missing_processes = [f"{usecase_id} {row['name']}" for usecase_id, row in y_usecases.items() if usecase_id not in process_usecase_ids]
        if missing_processes:
            findings.append(
                error(
                    "챕터 정합성",
                    "Y 유즈케이스 프로세스 누락",
                    "프로세스 정의 대상 Y인 유즈케이스에 연결된 프로세스가 없습니다: " + ", ".join(missing_processes[:8]),
                    "사람 액터 Y 유즈케이스는 4. 프로세스 정의에서 실제 책임·판단·처리·결과 경계가 드러나도록 프로세스로 분해하세요.",
                )
            )
        process_count_by_usecase: dict[str, int] = {}
        coarse_process_names: List[str] = []
        for process in process_rows:
            usecase_id = str(process.get("usecase_id", "")).strip()
            process_count_by_usecase[usecase_id] = process_count_by_usecase.get(usecase_id, 0) + 1
            process_name = str(process.get("name", "")).strip()
            usecase_name = y_usecases.get(usecase_id, {}).get("name", "")
            if process_name and usecase_name and process_name in {f"{usecase_name} 처리", usecase_name}:
                coarse_process_names.append(f"{process.get('id', '')} {process_name}")
        single_process_usecases = [
            f"{usecase_id} {row['name']}({process_count_by_usecase.get(usecase_id, 0)}개)"
            for usecase_id, row in y_usecases.items()
            if is_human_actor(row.get("actor", ""))
            and process_count_by_usecase.get(usecase_id, 0) == 1
        ]
        if single_process_usecases:
            findings.append(
                error(
                    "챕터 정합성",
                    "Y 유즈케이스 단일 프로세스 축소",
                    "사람 액터 Y 유즈케이스가 단일 프로세스로 축소되어 업무 전환점이 보이지 않습니다: " + ", ".join(single_process_usecases[:8]),
                    "개수를 맞추기 위해 늘리지 말고, 시작·판단·처리·결과 중 실제 책임이나 상태가 달라지는 전환점만 분리하세요.",
                )
            )
        if coarse_process_names:
            findings.append(
                warn(
                    "템플릿 가이드",
                    "프로세스명 포괄 표현",
                    "프로세스명이 유즈케이스명과 같거나 '{유즈케이스명} 처리' 수준으로 포괄적입니다: " + ", ".join(coarse_process_names[:8]),
                    "프로세스명은 약관 동의, 정보 입력, 조건 검증, 결과 안내처럼 세부 절차 역할이 드러나게 작성하세요.",
                )
            )

    if stage_reached(scope, "functions"):
        missing_process_function_links = [
            process.get("id", "")
            for process in process_rows
            if not process.get("related_functions")
        ]
        if missing_process_function_links:
            findings.append(
                error(
                    "챕터 정합성",
                    "프로세스 관련 기능 누락",
                    "기능 작성 후에도 관련 기능이 연결되지 않은 프로세스가 있습니다: "
                    + ", ".join(missing_process_function_links[:8]),
                    "Functions Agent 작성 결과의 process_id를 기준으로 프로세스 related_functions를 실제 기능 ID와 기능명으로 업데이트하세요.",
                )
            )
        missing_function_refs = [
            f"{process.get('id', '')}:{function_ref}"
            for process in process_rows
            for function_ref in process.get("related_functions", [])
            if not function_reference_matches(function_ref, function_names, function_names_by_id)
        ]
        if missing_function_refs:
            findings.append(
                warn(
                    "챕터 정합성",
                    "프로세스 관련 기능 참조 불일치",
                    "프로세스 관련 기능이 기능 목록의 ID·기능명과 일치하지 않습니다: "
                    + ", ".join(missing_function_refs[:8]),
                    "프로세스의 related_functions는 5. 기능 정의의 기능 ID와 기능명을 함께 작성해야 합니다.",
                )
            )

    if stage_reached(scope, "state"):
        transition_html = extract_html_between(body, "2) 상태 전이 기준", "3) 상태 전이 다이어그램")
        for row in table_rows(transition_html):
            cells = row["texts"]
            state_pair = transition_state_cells(cells)
            if not state_pair:
                continue
            current_state, next_state = state_pair
            if state_names and current_state not in state_names:
                findings.append(
                    error(
                        "챕터 정합성",
                        "현재 상태 참조 불일치",
                        f"상태 전이표의 현재 상태 '{current_state}'가 상태 코드 목록에 없습니다.",
                        "상태 전이표는 3.라.1 상태 코드의 상태명을 그대로 사용해야 합니다.",
                    )
                )
            if state_names and next_state not in state_names:
                findings.append(
                    error(
                        "챕터 정합성",
                        "다음 상태 참조 불일치",
                        f"상태 전이표의 다음 상태 '{next_state}'가 상태 코드 목록에 없습니다.",
                        "상태 전이표는 3.라.1 상태 코드의 상태명을 그대로 사용해야 합니다.",
                    )
                )

    if stage_reached(scope, "process"):
        for process in process_rows:
            if usecase_ids and process["usecase_id"] not in usecase_ids:
                findings.append(
                    error(
                        "챕터 정합성",
                        "프로세스 유즈케이스 참조 불일치",
                        f"{process['id']}가 속한 유즈케이스 '{process['usecase_id']}'가 유즈케이스 목록에 없습니다.",
                        "프로세스 목록의 유즈케이스 그룹은 3.나 유즈케이스 ID와 일치해야 합니다.",
                    )
                )

    if stage_reached(scope, "functions"):
        related_functions = {
            item
            for process in process_rows
            for item in process.get("related_functions", [])
        }
        missing_functions = sorted(
            item
            for item in related_functions
            if not function_reference_matches(item, function_names, function_names_by_id)
        )
        if missing_functions:
            findings.append(
                error(
                    "챕터 정합성",
                    "프로세스 관련 기능 참조 불일치",
                    f"프로세스가 참조하지만 기능 목록의 ID·기능명과 맞지 않는 관련 기능이 있습니다: {', '.join(missing_functions[:5])}",
                    "4. 프로세스 정의의 관련 기능은 5. 기능 정의의 기능 ID와 기능명을 함께 작성해야 합니다.",
                )
            )
        process_ids = {process["id"] for process in process_rows if process.get("id")}
        function_detail_process_ids = set(re.findall(r"<h4\b[^>]*>.*?\((PR-[^)]+)\)</h4>", body, flags=re.DOTALL))
        missing_process_refs = sorted(function_detail_process_ids - process_ids)
        if function_detail_process_ids and missing_process_refs:
            findings.append(
                error(
                    "챕터 정합성",
                    "기능 상세 프로세스 참조 불일치",
                    f"기능 상세가 참조하는 프로세스 ID가 프로세스 목록에 없습니다: {', '.join(missing_process_refs[:5])}",
                    "기능 상세의 프로세스 ID는 4. 프로세스 정의의 프로세스 ID와 일치해야 합니다.",
                )
            )

    if stage_reached(scope, "policies"):
        missing_process_policy_links = [
            process.get("id", "")
            for process in process_rows
            if not process.get("related_policies")
        ]
        if missing_process_policy_links:
            findings.append(
                error(
                    "챕터 정합성",
                    "프로세스 관련 정책 누락",
                    "정책 작성 후에도 관련 정책이 연결되지 않은 프로세스가 있습니다: "
                    + ", ".join(missing_process_policy_links[:8]),
                    "Policies Agent 작성 결과의 정책 목록(policy_groups)을 기준으로 프로세스 related_policies를 정책 ID와 정책명으로 업데이트하세요.",
                )
            )
        missing_policies = []
        for process in process_rows:
            for policy_ref in process.get("related_policies", []):
                policy_id, policy_name = split_policy_reference(policy_ref)
                if policy_id:
                    expected_name = policy_name_by_id.get(policy_id, "")
                    if not expected_name:
                        missing_policies.append(f"{process.get('id', '')}:{policy_id}")
                    elif not policy_name:
                        missing_policies.append(f"{process.get('id', '')}:{policy_ref}")
                    elif policy_name != expected_name:
                        missing_policies.append(f"{process.get('id', '')}:{policy_ref}")
                elif policy_ref not in policy_names:
                    missing_policies.append(f"{process.get('id', '')}:{policy_ref}")
        if missing_policies:
            findings.append(
                error(
                    "챕터 정합성",
                    "프로세스 관련 정책 참조 불일치",
                    f"프로세스가 참조하지만 정책 목록과 일치하지 않는 정책 참조가 있습니다: {', '.join(missing_policies[:5])}",
                    "4. 프로세스 정의의 관련 정책은 6. 정책 정의의 정책 ID와 정책명을 함께 사용해야 합니다.",
                )
            )
        detail_policy_ids = set(re.findall(r"<h4\b[^>]*>.*?\((PG-[^)]+)\)</h4>\s*<div class=\"policy-group\">", body, flags=re.DOTALL))
        missing_detail_groups = sorted(policy_ids - detail_policy_ids)
        if missing_detail_groups:
            findings.append(
                error(
                    "챕터 정합성",
                    "정책 그룹 상세 누락",
                    f"정책 목록에는 있으나 정책 상세 장에 없는 정책 그룹이 있습니다: {', '.join(missing_detail_groups[:5])}",
                    "모든 정책 그룹은 6.나 정책 상세에 하나 이상의 정책 항목을 가져야 합니다.",
                )
            )
    return findings


def check_connection_integrity(body: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    policy_names = set(re.findall(r"<td>([^<]+ 정책)</td><td>[^<]*", body))
    process_policy_cells = re.findall(r"<td>([^<]*(?:정책|정책<br/>)[^<]*)</td>", body)
    if scope in {"06_process", "07_process", "07_functions", "08_functions", "08_policies", "09_policies", "09_final", "10_final_check", "full"}:
        if body.count("PR-") < 8:
            findings.append(metric_warn("밀도 관찰", "프로세스 밀도 낮음", "프로세스 ID가 적어 업무 흐름이 단순화됐을 수 있습니다.", "개수를 맞추기보다 Y 유즈케이스별 시작, 판단, 요청, 결과, 예외 흐름이 필요한 만큼 분리됐는지 확인하세요."))
    if scope in {"08_policies", "09_policies", "09_final", "10_final_check", "full"}:
        if not process_policy_cells:
            findings.append(error("연결성", "프로세스-정책 연결 누락", "프로세스 목록에 관련 정책이 연결되어 있지 않습니다.", "모든 프로세스에 정책 목록의 정책 ID와 정책명을 작성하세요."))
    if scope in {"08_policies", "09_policies", "09_final", "10_final_check", "full"}:
        if body.count("PG-") < 8:
            findings.append(metric_warn("밀도 관찰", "정책 그룹 밀도 낮음", "정책 그룹 수가 적어 판단축이 넓게 묶였을 수 있습니다.", "개수를 맞추기보다 권한, 노출, 검증, 인증, 고지, 결과, 예외, 운영, 개인정보, 품질 기준이 필요한 판단축으로 분리됐는지 확인하세요."))
        if body.count("policy-item-title") < 30:
            findings.append(metric_warn("밀도 관찰", "정책 상세 밀도 낮음", "정책 상세 항목 수가 적어 실제 판단값이 빠졌을 가능성이 있습니다.", "개수를 맞추기보다 각 정책 항목이 조건, 제한, 횟수, 시간, 상태, 예외, 고지, 이력 중 필요한 판단 기준을 담았는지 확인하세요."))
    if scope in {"05_usecases", "06_state", "06_process", "07_process", "07_functions", "08_functions", "08_policies", "09_policies", "09_final", "10_final_check", "full"} and body.count("ST-") < 8:
        findings.append(metric_warn("밀도 관찰", "상태 밀도 낮음", "상태 코드가 적어 예외나 제한 흐름이 누락됐을 수 있습니다.", "개수를 맞추기보다 고객 노출, 기능 허용, 정책 판단, 후속 처리를 바꾸는 상태가 빠졌는지 확인하세요."))
    return findings


def check_sample_parity(
    metrics: dict,
    template_type: str,
    scope: str,
    topic: str = "",
    density_profile: Mapping[str, object] | None = None,
) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if scope not in {"08_policies", "09_policies", "09_final", "10_final_check", "full"}:
        return findings
    strict_sample = bool(metrics.get("sample_topic_match_count"))
    if metrics["body_bytes"] < 30000:
        findings.append(warn("샘플 유사도", "본문 분량 부족", "샘플 정책서 수준에 비해 본문 분량이 적습니다.", "장별 표와 정책 상세를 더 구체화하세요."))
    if metrics["sample_min_body_bytes"] and metrics["body_bytes"] < metrics["sample_min_body_bytes"] * 0.18:
        findings.append(warn("샘플 유사도", "샘플 대비 분량 부족", "가장 작은 샘플 정책서와 비교해 본문 밀도가 낮습니다.", "유즈케이스, 프로세스, 기능, 정책 상세의 조건과 예외를 더 보강하세요."))
    if strict_sample:
        ratio_checks = (
            ("text_chars", "sample_max_text_chars", 0.50, "샘플 대비 텍스트 밀도 부족", "본문 텍스트 분량이 샘플의 절반 미만입니다."),
            ("usecase_distinct_count", "sample_max_usecase_distinct_count", 0.45, "샘플 대비 유즈케이스 부족", "유즈케이스 수가 샘플 수준에 비해 부족합니다."),
            ("process_distinct_count", "sample_max_process_distinct_count", 0.60, "샘플 대비 프로세스 부족", "프로세스 수가 샘플 수준에 비해 부족합니다."),
            ("function_distinct_count", "sample_max_function_distinct_count", 0.55, "샘플 대비 기능 부족", "기능 수가 샘플 수준에 비해 부족합니다."),
            ("policy_group_distinct_count", "sample_max_policy_group_distinct_count", 0.60, "샘플 대비 정책 그룹 부족", "정책 그룹 수가 샘플 수준에 비해 부족합니다."),
            ("policy_item_count", "sample_max_policy_item_count", 0.60, "샘플 대비 정책 상세 부족", "정책 상세 항목 수가 샘플 수준에 비해 부족합니다."),
        )
        for key, sample_key, threshold, title, detail in ratio_checks:
            sample_value = int(metrics.get(sample_key) or 0)
            current_value = int(metrics.get(key) or 0)
            if not sample_value:
                continue
            sample_required = sample_value * threshold
            if current_value < sample_required:
                findings.append(
                    metric_warn(
                        "샘플 유사도",
                        title,
                        f"{detail} 현재 {current_value}건, 주제 일치 샘플 기준 {sample_value}건입니다.",
                        "샘플 개수를 맞추기보다 샘플의 판단축, 표 밀도, 예외 기준 표현 수준과 비교해 실제 누락된 업무 질문이 있는지 확인하세요.",
                    )
                )
    if metrics["table_count"] < 8:
        findings.append(metric_warn("샘플 유사도", "표 구조 밀도 낮음", "샘플 정책서에 비해 표 기반 구조가 적습니다.", "표 개수를 맞추기보다 용어, 액터, 유즈케이스, 상태, 프로세스, 기능, 정책 목록 중 표로 검증해야 할 구조가 빠졌는지 확인하세요."))
    if metrics["policy_item_count"] < 30:
        findings.append(metric_warn("샘플 유사도", "정책 상세 밀도 낮음", "샘플 정책서와 비교해 정책 상세 항목이 적습니다.", "정책 상세 수를 맞추기보다 필요한 정책 질문이 판단값, 조건, 예외, 이력 기준으로 답변됐는지 확인하세요."))
    if template_type == "full" and metrics["table_count"] < 10:
        findings.append(warn("샘플 유사도", "Full 상세 밀도 부족", "Full 버전은 간소화보다 상세 표가 더 필요합니다.", "프로세스 상세와 기능 상세 표를 포함하세요."))
    return findings


def check_topic_specificity(text: str, topic: str, scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if not topic or scope not in {
        "01_overview",
        "02_terms",
        "03_actors",
        "04_usecases",
        "05_usecase_diagram",
        "06_state",
        "07_process",
        "08_functions",
        "09_policies",
        "10_final_check",
        "03_overview",
        "04_terms",
        "05_usecases",
        "06_process",
        "07_functions",
        "08_policies",
        "09_final",
        "full",
    }:
        return findings

    axes = topic_axis_specs(topic)
    if not axes:
        return findings
    compact_text = normalize_for_keyword_match(text)
    missing = [axis["label"] for axis in axes if not topic_axis_present(compact_text, axis)]
    if len(axes) >= 2:
        if missing and not stage_reached(scope, "process"):
            findings.append(
                warn(
                    "내용",
                    "주제 축 반영 부족",
                    f"복합 주제 '{topic}'의 의미 축 중 현재 범위에서 약한 축이 있습니다: {', '.join(missing)}",
                    "주제명을 반복하기보다 각 의미 축이 범위, 용어, 액터, 유즈케이스의 판단 기준으로 드러나도록 보완하세요.",
                )
            )
        return findings

    if missing:
        findings.append(
            warn(
                "내용",
                "주제 특화 부족",
                f"본문에서 주제 '{topic}'의 핵심 표현이 확인되지 않습니다.",
                "공통 문장만 쓰지 말고 주제의 고객 과업, 시스템 판정, 예외 기준이 현재 장에 드러나도록 보완하세요.",
            )
        )
    return findings


def check_internal_code_leakage(body: str, text: str, topic: str, scope: str) -> List[InspectionFinding]:
    if not stage_reached(scope, "overview"):
        return []
    findings: List[InspectionFinding] = []
    codes = infer_business_codes(body)
    if not codes:
        return findings
    target = extract_text_section(text, "1. 개요", "2. 주요 용어") or text
    for code in codes:
        if len(code) < 3:
            continue
        if topic_allows_business_code(topic, code):
            continue
        cleaned = remove_identifier_references(target, code)
        if not re.search(rf"(?<![A-Z0-9-]){re.escape(code)}(?![A-Z0-9-])", cleaned):
            continue
        snippet = nearby_text(cleaned, code, 80)
        replacement_hint = f"'{display_topic_for_inspection(topic)}'" if topic else "실제 정책서 주제명"
        findings.append(
            warn(
                "내부 코드",
                "내부 업무코드 본문 노출",
                f"업무코드 '{code}'가 ID가 아닌 본문 문장에 노출되어 있습니다: {snippet}",
                f"업무코드는 POL/ACT/US 같은 ID에만 사용하고, 본문에서는 {replacement_hint}처럼 고객과 검토자가 이해할 수 있는 업무명으로 바꾸세요.",
            )
        )
    return findings


def infer_business_codes(body: str) -> List[str]:
    codes = re.findall(r"\b(?:ACT|US|ST|PR|FN|PG|PI)-([A-Z0-9]+)-", body)
    codes.extend(re.findall(r"\bPOL-([A-Z0-9]+)\b", body))
    return dedupe(code for code in codes if code)


def topic_allows_business_code(topic: str, code: str) -> bool:
    """Allow customer-facing acronyms when they are part of the actual topic name."""

    code = str(code or "").strip().upper()
    if not topic or not code:
        return False
    tokens = re.findall(r"[A-Z0-9]+|[가-힣]+", unicodedata.normalize("NFC", str(topic)).upper())
    return code in tokens


def display_topic_for_inspection(topic: str) -> str:
    text = unicodedata.normalize("NFC", str(topic or "")).replace("_", " ").replace("/", "·")
    return re.sub(r"\s+", " ", text).strip()


def remove_identifier_references(text: str, code: str) -> str:
    cleaned = re.sub(rf"\b(?:POL|ACT|US|ST|PR|FN|PG|PI)-{re.escape(code)}[A-Z0-9-]*\b", " ", text)
    cleaned = re.sub(rf"\b문서\s*ID\s*{re.escape(code)}\b", " ", cleaned)
    cleaned = re.sub(rf"\b업무코드\s*{re.escape(code)}\b", " ", cleaned)
    return cleaned


def check_topic_required_axes(text: str, topic: str, scope: str) -> List[InspectionFinding]:
    if not topic or not stage_reached(scope, "process"):
        return []
    topic_axes = topic_required_axes(topic)
    if len(topic_axes) < 2:
        return []
    target_text = topic_axis_stage_text(text, scope)
    compact_text = normalize_for_keyword_match(target_text)
    missing = []
    for axis in topic_axes:
        if not topic_axis_present(compact_text, axis):
            missing.append(str(axis["label"]))
    if not missing:
        return []
    severity = error if stage_reached(scope, "policies") and len(missing) >= 2 else warn
    return [
        severity(
            "주제 특화",
            "주제별 필수 판단축 부족",
            f"{topic} 정책서의 현재 챕터에서 복합 주제 축 반영이 약합니다: {', '.join(missing)}",
            "복합 주제의 각 축이 프로세스, 기능, 정책 중 최소 하나 이상의 판단 지점으로 이어지도록 현재 챕터를 보완하세요.",
        )
    ]


def check_user_brief_alignment(text: str, brief: str, scope: str) -> List[InspectionFinding]:
    brief = str(brief or "").strip()
    if not brief or scope_rank(scope) < 3:
        return []
    keywords = user_brief_keywords(brief)
    if not keywords:
        return []
    content_text = re.sub(r"0\.\s*문서\s*히스토리.*?1\.\s*개요", "1. 개요", text, flags=re.DOTALL)
    compact_text = normalize_for_keyword_match(content_text)
    matched = [keyword for keyword in keywords if normalize_for_keyword_match(keyword) in compact_text]
    required = max(1, min(3, len(keywords) // 3 or 1))
    if len(matched) >= required:
        return []
    return [
        warn(
            "사용자 요청",
            "작성 요청 메모 반영 약함",
            "사용자가 입력한 작성 요청 메모의 핵심 표현이 현재 문서에 충분히 드러나지 않습니다.",
            "요구사항과 참고자료를 해치지 않는 범위에서 작성 요청 메모의 초점이 관련 챕터에 반영됐는지 확인하세요.",
        )
    ]


def user_brief_keywords(brief: str) -> List[str]:
    stopwords = {
        "정책서",
        "작성",
        "요청",
        "내용",
        "관련",
        "기준",
        "반영",
        "해주세요",
        "해줘",
        "있게",
        "대한",
        "대해",
        "그리고",
        "또는",
        "으로",
        "에서",
        "하는",
        "해야",
    }
    words = re.findall(r"[0-9A-Za-z가-힣]{2,}", brief)
    keywords: List[str] = []
    for word in words:
        normalized = word.strip()
        if not normalized or normalized in stopwords:
            continue
        if len(normalize_for_keyword_match(normalized)) < 2:
            continue
        if normalized not in keywords:
            keywords.append(normalized)
    return keywords[:8]


def normalize_for_keyword_match(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", str(value or "")).casefold())


def topic_required_axes(topic: str) -> List[dict]:
    return topic_axis_specs(topic)


def topic_axis_specs(topic: str) -> List[dict]:
    """Extract reusable topic axes without hardcoding a specific policy domain."""
    raw = display_topic_for_inspection(topic)
    if not raw:
        return []
    split_pattern = r"\s*(?:/|·|,|，|\+|&|\b및\b|\band\b)\s*"
    raw_parts = [part.strip() for part in re.split(split_pattern, raw) if part.strip()]
    parts = raw_parts if len(raw_parts) > 1 else [raw]
    axes: List[dict] = []
    for part in parts:
        label = re.sub(r"\s+", " ", part).strip()
        terms = topic_axis_terms(label)
        if not terms:
            continue
        compact = normalize_for_keyword_match(label)
        axes.append(
            {
                "label": label,
                "compact": compact,
                "terms": [normalize_for_keyword_match(term) for term in terms],
            }
        )
    return dedupe_topic_axes(axes)


def topic_axis_terms(label: str) -> List[str]:
    stopwords = {"nc", "통합채널", "정책서", "정책", "간소화", "full", "버전"}
    tokens = [
        token
        for token in re.split(r"[\s_/.·+&,，()\[\]{}<>:;|]+", str(label or ""))
        if token and normalize_for_keyword_match(token) not in stopwords
    ]
    if not tokens:
        return []
    return tokens


def dedupe_topic_axes(axes: Sequence[Mapping[str, object]]) -> List[dict]:
    result: List[dict] = []
    seen = set()
    for axis in axes:
        label = str(axis.get("label", "")).strip()
        compact = str(axis.get("compact", "")).strip()
        if not label or not compact or compact in seen:
            continue
        seen.add(compact)
        result.append(dict(axis))
    return result


def topic_axis_present(compact_text: str, axis: Mapping[str, object]) -> bool:
    compact = str(axis.get("compact", "")).strip()
    if compact and compact in compact_text:
        return True
    terms = [
        str(term).strip()
        for term in axis.get("terms", [])
        if str(term).strip()
    ]
    if not terms:
        return False
    if len(terms) == 1:
        return terms[0] in compact_text
    return all(term in compact_text for term in terms)


def topic_axis_stage_text(text: str, scope: str) -> str:
    rank = scope_rank(scope)
    if rank == 7:
        return extract_text_section(text, "4. 프로세스 정의", "5. 기능 정의") or text
    if rank == 8:
        return extract_text_section(text, "5. 기능 정의", "6. 정책 정의") or text
    if rank == 9:
        return extract_text_section(text, "6. 정책 정의", "최종 점검 기준") or text
    if rank >= 10:
        return text
    return focused_text_for_scope(text, scope)


def run_llm_inspector(
    document: str,
    body: str,
    text: str,
    deterministic_findings: Sequence[InspectionFinding],
    metrics: dict,
    template_type: str,
    scope: str,
    topic: str,
    brief: str,
    inspection_mode: str,
    llm_client: object | None,
    llm_required: bool,
    llm_retry_callback: object | None = None,
) -> List[InspectionFinding]:
    metrics["llm_inspector"] = {
        "used": False,
        "required": llm_required,
        "model": getattr(llm_client, "model", "") if llm_client else "",
        "reasoning_effort": getattr(llm_client, "reasoning_effort", "") if llm_client else "",
        "task_max_attempts": inspector_llm_task_max_attempts(),
        "inspection_mode": normalized_inspection_mode_for_inspector(inspection_mode),
        "profile": final_inspection_profile(inspection_mode, scope),
    }
    if llm_client is None or not getattr(llm_client, "enabled", False):
        if llm_required:
            raise ValueError("LLM inspector가 필요하지만 OPENAI_API_KEY 또는 LLM 설정이 활성화되어 있지 않습니다.")
        return []
    if is_mock_inspector_client(llm_client):
        findings = strict_mock_document_findings(body, text, metrics, scope)
        metrics["llm_inspector"] = {
            "used": True,
            "required": llm_required,
            "model": getattr(llm_client, "model", ""),
            "reasoning_effort": "none",
            "status": "strict_mock",
            "summary": "LLM 미사용 모드에서 pass 응답 대신 로컬 strict 규칙으로 검수했습니다.",
            "prompt_chars": 0,
            "task_attempts": 1,
            "task_retry_events": [],
            "strict_findings": len(findings),
        }
        return findings

    prompt = llm_inspection_prompt(
        body=body,
        text=text,
        deterministic_findings=deterministic_findings,
        metrics=metrics,
        template_type=template_type,
        scope=scope,
        topic=topic,
        brief=brief,
        inspection_mode=inspection_mode,
    )
    metrics["llm_inspector"]["prompt_chars"] = len(prompt)
    payload = None
    retry_events: List[dict] = []
    max_attempts = inspector_llm_task_max_attempts()
    for task_attempt in range(1, max_attempts + 1):
        try:
            metrics["llm_inspector"]["task_attempt"] = task_attempt
            payload = llm_client.generate_json(
                schema_name="policy_inspection",
                schema=llm_inspection_schema(),
                instructions=llm_inspection_instructions(topic, template_type, scope, brief, inspection_mode),
                input_messages=[{"role": "user", "content": prompt}],
                omit_max_output_tokens=True,
            )
            break
        except Exception as exc:
            recoverable = is_recoverable_llm_generation_error(exc)
            event = {
                "attempt": task_attempt,
                "max_attempts": max_attempts,
                "recoverable": recoverable,
                "error": str(exc)[:500],
            }
            retry_events.append(event)
            metrics["llm_inspector"].update(
                {
                    "status": "retry_wait" if recoverable and task_attempt < max_attempts else "failed_after_retries",
                    "task_attempt": task_attempt,
                    "task_retry_events": retry_events,
                    "error": str(exc)[:500],
                }
            )
            if not llm_required:
                metrics["llm_inspector"]["status"] = "fallback_after_error"
                return []
            if recoverable and task_attempt >= max_attempts:
                metrics["llm_inspector"]["status"] = "fallback_after_retries"
                return [llm_inspector_unavailable_finding(exc, max_attempts, input_mode="html")]
            if not recoverable or task_attempt >= max_attempts:
                raise
            delay = inspector_llm_retry_delay_seconds(task_attempt)
            event["retry_after_seconds"] = delay
            notify_llm_retry(llm_retry_callback, event)
            time.sleep(delay)
    if payload is None:
        raise ValueError("LLM inspector가 응답을 반환하지 못했습니다.")
    metrics["llm_inspector"] = {
        "used": True,
        "required": llm_required,
        "model": getattr(llm_client, "model", ""),
        "reasoning_effort": getattr(llm_client, "reasoning_effort", ""),
        "status": payload.get("status", ""),
        "summary": payload.get("summary", ""),
        "prompt_chars": len(prompt),
        "task_attempts": int(metrics.get("llm_inspector", {}).get("task_attempt", 1)) if isinstance(metrics.get("llm_inspector"), dict) else 1,
        "task_retry_events": retry_events,
    }
    findings = llm_findings(payload)
    filtered_findings = filter_llm_findings_for_scope(findings, scope)
    metrics["llm_inspector"]["filtered_findings"] = len(findings) - len(filtered_findings)
    if len(findings) != len(filtered_findings):
        metrics["llm_inspector"]["filter_reason"] = "현재 작성 범위 밖의 후속 장 보완 권고는 gate 감점에서 제외합니다."
    return filtered_findings


def run_llm_json_inspector(
    *,
    spec: Mapping[str, object],
    deterministic_findings: Sequence[InspectionFinding],
    metrics: dict,
    template_type: str,
    scope: str,
    chapter_key: str,
    topic: str,
    brief: str,
    llm_client: object | None,
    llm_required: bool,
    llm_retry_callback: object | None = None,
) -> List[InspectionFinding]:
    metrics["llm_inspector"] = {
        "used": False,
        "required": llm_required,
        "input_mode": "json",
        "model": getattr(llm_client, "model", "") if llm_client else "",
        "reasoning_effort": getattr(llm_client, "reasoning_effort", "") if llm_client else "",
        "task_max_attempts": inspector_llm_task_max_attempts(),
        "stage_inspector_profile": stage_inspector_profile(scope, chapter_key),
    }
    if llm_client is None or not getattr(llm_client, "enabled", False):
        if llm_required:
            raise ValueError("LLM inspector가 필요하지만 OPENAI_API_KEY 또는 LLM 설정이 활성화되어 있지 않습니다.")
        return []
    if is_mock_inspector_client(llm_client):
        findings = strict_mock_json_findings(spec, scope, chapter_key, metrics)
        metrics["llm_inspector"] = {
            "used": True,
            "required": llm_required,
            "input_mode": "json",
            "model": getattr(llm_client, "model", ""),
            "reasoning_effort": "none",
            "status": "strict_mock",
            "summary": "LLM 미사용 모드에서 pass 응답 대신 로컬 strict 규칙으로 검수했습니다.",
            "prompt_chars": 0,
            "task_attempts": 1,
            "task_retry_events": [],
            "stage_inspector_profile": stage_inspector_profile(scope, chapter_key),
            "strict_findings": len(findings),
        }
        return findings

    prompt = llm_json_inspection_prompt(
        spec=spec,
        deterministic_findings=deterministic_findings,
        metrics=metrics,
        template_type=template_type,
        scope=scope,
        chapter_key=chapter_key,
        topic=topic,
        brief=brief,
    )
    metrics["llm_inspector"]["prompt_chars"] = len(prompt)
    payload = None
    retry_events: List[dict] = []
    max_attempts = inspector_llm_task_max_attempts()
    for task_attempt in range(1, max_attempts + 1):
        try:
            metrics["llm_inspector"]["task_attempt"] = task_attempt
            payload = llm_client.generate_json(
                schema_name="policy_json_inspection",
                schema=llm_inspection_schema(),
                instructions=llm_json_inspection_instructions(topic, template_type, scope, brief),
                input_messages=[{"role": "user", "content": prompt}],
                omit_max_output_tokens=True,
            )
            break
        except Exception as exc:
            recoverable = is_recoverable_llm_generation_error(exc)
            event = {
                "attempt": task_attempt,
                "max_attempts": max_attempts,
                "recoverable": recoverable,
                "error": str(exc)[:500],
            }
            retry_events.append(event)
            metrics["llm_inspector"].update(
                {
                    "status": "retry_wait" if recoverable and task_attempt < max_attempts else "failed_after_retries",
                    "task_attempt": task_attempt,
                    "task_retry_events": retry_events,
                    "error": str(exc)[:500],
                }
            )
            if not llm_required:
                metrics["llm_inspector"]["status"] = "fallback_after_error"
                return []
            if recoverable and task_attempt >= max_attempts:
                metrics["llm_inspector"]["status"] = "fallback_after_retries"
                return [llm_inspector_unavailable_finding(exc, max_attempts, input_mode="json")]
            if not recoverable or task_attempt >= max_attempts:
                raise
            delay = inspector_llm_retry_delay_seconds(task_attempt)
            event["retry_after_seconds"] = delay
            notify_llm_retry(llm_retry_callback, event)
            time.sleep(delay)
    if payload is None:
        raise ValueError("LLM JSON inspector가 응답을 반환하지 못했습니다.")
    metrics["llm_inspector"] = {
        "used": True,
        "required": llm_required,
        "input_mode": "json",
        "model": getattr(llm_client, "model", ""),
        "reasoning_effort": getattr(llm_client, "reasoning_effort", ""),
        "status": payload.get("status", ""),
        "summary": payload.get("summary", ""),
        "prompt_chars": len(prompt),
        "task_attempts": int(metrics.get("llm_inspector", {}).get("task_attempt", 1)) if isinstance(metrics.get("llm_inspector"), dict) else 1,
        "task_retry_events": retry_events,
        "stage_inspector_profile": stage_inspector_profile(scope, chapter_key),
    }
    findings = llm_findings(payload)
    filtered_findings = filter_llm_findings_for_scope(findings, scope)
    metrics["llm_inspector"]["filtered_findings"] = len(findings) - len(filtered_findings)
    if len(findings) != len(filtered_findings):
        metrics["llm_inspector"]["filter_reason"] = "현재 작성 범위 밖의 후속 장 보완 권고는 gate 감점에서 제외합니다."
    return filtered_findings


def is_recoverable_llm_generation_error(exc: Exception) -> bool:
    message = str(exc)
    return any(
        marker in message
        for marker in (
            "max_output_tokens",
            '"status": "incomplete"',
            "response_status",
            "incomplete_details",
            "OpenAI API 오류 408",
            "OpenAI API 오류 409",
            "OpenAI API 오류 425",
            "OpenAI API 오류 429",
            "OpenAI API 오류 500",
            "OpenAI API 오류 502",
            "OpenAI API 오류 503",
            "OpenAI API 오류 504",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "rate_limit",
            "OpenAI API 연결 실패",
            "OpenAI API 응답 대기 시간이 초과",
            "OpenAI API 응답을 JSON으로 해석하지 못했습니다",
            "LLM 응답이 유효한 JSON이 아닙니다",
            "OpenAI API 응답에 JSON 텍스트가 없습니다",
        )
    )


def llm_inspector_unavailable_finding(exc: Exception, max_attempts: int, *, input_mode: str) -> InspectionFinding:
    return InspectionFinding(
        "warn",
        "LLM Inspector",
        "LLM Inspector 일시 실패",
        (
            f"LLM Inspector가 {max_attempts}회 재시도 후에도 응답하지 않아 "
            f"{input_mode.upper()} 로컬 검수 결과를 기준으로 작업을 계속 진행했습니다."
        ),
        "네트워크 또는 API 상태가 안정화된 뒤 개발/QA 검수나 최종 검수를 다시 실행해 LLM 관점의 품질 점검을 보완하세요.",
        tier="P2",
        is_metric_observation=True,
        target_path="meta.llm_inspector",
        fix_owner="current_chapter",
        root_cause=str(exc)[:500],
        required_change="LLM Inspector 재검수 필요",
        patch_hint="본문을 임의 수정하지 말고, 재검수 또는 개발/QA 검수 기능으로 LLM 관점의 누락 여부를 확인한다.",
        acceptance_check="개발/QA 검수 또는 Final Inspector가 정상 응답하고 남은 P1/P2 항목이 정리된다.",
    )


def is_mock_inspector_client(llm_client: object | None) -> bool:
    return str(getattr(llm_client, "writer_mode", "") or "").strip().casefold() == "mock"


def strict_mock_finding(
    title: str,
    detail: str,
    required_change: str,
    *,
    target_path: str,
    tier: str = "P2",
    root_cause: str = "",
    patch_hint: str = "",
    acceptance_check: str = "",
    recommendation: str = "",
    is_quality_gate: bool = False,
    category: str = "Mock strict",
    keep_constraints: str = "",
    do_not_change: str = "",
) -> InspectionFinding:
    """Create actionable local findings for no-cost mock inspection.

    Mock mode still needs to drive real repair loops. Populate the same
    fields expected from LLM Inspector so Chapter Writers can patch narrowly.
    """

    return InspectionFinding(
        "warn",
        category,
        title,
        detail,
        recommendation or required_change,
        tier=tier,
        is_quality_gate=is_quality_gate,
        target_path=target_path,
        fix_owner="current_chapter",
        root_cause=root_cause or detail,
        required_change=required_change,
        patch_hint=patch_hint or required_change,
        acceptance_check=acceptance_check or "동일 원인의 strict mock finding이 재발하지 않아야 합니다.",
        keep_constraints=keep_constraints or "기존 ID와 승인된 상위 장의 연결 구조는 유지합니다.",
        do_not_change=do_not_change or "지적 범위를 넘어 장 전체를 재작성하거나 주제별 하드코딩 정책을 추가하지 않습니다.",
    )


def strict_mock_json_findings(
    spec: Mapping[str, object],
    scope: str,
    chapter_key: str,
    metrics: Mapping[str, object],
) -> List[InspectionFinding]:
    """Return deterministic quality findings for LLM-off inspection."""

    del metrics
    findings: List[InspectionFinding] = []
    stage_key = inspector_stage_key(scope, chapter_key)
    is_final_scope = scope in {"full", "final"}
    actors = json_rows(spec, "actors")
    usecases = json_rows(spec, "usecases")
    states = json_rows(spec, "states")
    transitions = json_rows(spec, "state_transitions")
    processes = json_rows(spec, "processes")
    functions = json_rows(spec, "functions")
    policy_details = json_rows(spec, "policy_details")

    if is_final_scope or stage_key == "overview":
        findings.extend(strict_mock_overview_findings(spec))
    if is_final_scope or stage_key in {"terms", "terms_refinement"}:
        findings.extend(strict_mock_terms_findings(spec))
    if is_final_scope or stage_key == "state":
        findings.extend(strict_mock_state_findings(states, transitions))
    if is_final_scope or stage_key in {"process", "policies", "final_check"}:
        findings.extend(strict_mock_process_findings(processes))
    if is_final_scope or stage_key in {"functions", "policies", "final_check"}:
        findings.extend(strict_mock_function_findings(functions))
    if is_final_scope or stage_key == "policies":
        policy_groups = json_rows(spec, "policy_groups")
        findings.extend(strict_mock_policy_findings(policy_groups, policy_details))
    if is_final_scope or stage_key == "final_check":
        findings.extend(strict_mock_final_check_findings(spec))

    if stage_key == "usecases" and usecases and not any(is_human_actor(str(row.get("actor", ""))) for row in usecases):
        findings.append(
            strict_mock_finding(
                "사람 액터 유즈케이스 부족",
                "유즈케이스가 모두 시스템 중심으로 보입니다.",
                "사람 액터가 시작하고 완료해야 하는 고객/운영자 업무 유즈케이스를 최소 1개 이상 추가합니다.",
                target_path="current_chapter.usecases",
                tier="P2",
                root_cause="시스템 처리 유즈케이스만 남아 고객/운영자가 완료해야 하는 업무 단위가 드러나지 않습니다.",
                patch_hint="고객 또는 운영자가 목적을 시작하고 완료 상태에 도달하는 상위 업무 단위만 추가하고, 인증·조회·저장 같은 절차는 프로세스로 내립니다.",
                acceptance_check="usecases에 사람 액터가 수행하는 process_target=Y 유즈케이스가 1개 이상 있어야 합니다.",
            )
        )
    if stage_key == "actors" and actors and len(actors) < 2:
        findings.append(
            strict_mock_finding(
                "액터 책임 경계 부족",
                "액터가 1개 이하라서 고객 업무와 처리 책임의 분리가 약할 수 있습니다.",
                "고객과 처리/판정 책임 주체가 필요한지 확인하고 필요한 액터를 보강합니다.",
                target_path="current_chapter.actors",
                tier="P3",
                root_cause="정책서가 고객 과업과 시스템/운영 판정 책임을 구분할 근거가 부족합니다.",
                patch_hint="독립 책임 주체만 추가합니다. 로그인/비로그인/정상/제한 고객은 액터가 아니라 상태·권한 조건으로 둡니다.",
                acceptance_check="actors에 고객과 주요 처리/판정 책임 주체가 분리되어 있어야 합니다.",
            )
        )
    return findings


def strict_mock_overview_findings(spec: Mapping[str, object]) -> List[InspectionFinding]:
    overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
    scope_items = (
        [str(item).strip() for item in overview.get("scope", []) if str(item).strip()]
        if isinstance(overview.get("scope"), list)
        else []
    )
    principles = overview.get("principles", []) if isinstance(overview.get("principles"), list) else []
    findings: List[InspectionFinding] = []
    if scope_items and not any("제외" in item for item in scope_items):
        findings.append(
            strict_mock_finding(
                "개요 제외 범위 약함",
                "범위 설명에 제외 범위가 명시적으로 보이지 않습니다.",
                "작성 대상이 아닌 UI/API/DB/운영 상세 영역을 제외 범위로 분리합니다.",
                target_path="current_chapter.overview.scope",
                tier="P3",
                root_cause="포함 범위만 있고 제외 범위가 없어 후속 장에서 화면·API·DB 상세로 범위가 확장될 위험이 있습니다.",
                patch_hint="scope 배열에 '제외 범위' 문장을 1개 추가하되, 정책 판단에 직접 영향을 주는 기준은 제외하지 않습니다.",
                acceptance_check="overview.scope 안에서 제외 범위를 명시적으로 확인할 수 있어야 합니다.",
            )
        )
    if principles and not (4 <= len(principles) <= 6):
        findings.append(
            strict_mock_finding(
                "설계 원칙 개수 점검",
                f"설계 원칙이 {len(principles)}개입니다.",
                "원칙은 4~6개 수준으로 유지하고 기능·정책 판단에 연결되는 항목만 남깁니다.",
                target_path="current_chapter.overview.principles",
                tier="P3",
                root_cause="설계 원칙이 너무 적거나 많으면 후속 Agent가 적용해야 할 판단축이 흔들립니다.",
                patch_hint="중복 원칙은 병합하고, 정책·기능 판단으로 이어지지 않는 구호성 원칙은 제거합니다.",
                acceptance_check="overview.principles 개수가 4~6개이고 각 원칙이 기능 또는 정책 판단 기준으로 연결되어야 합니다.",
            )
        )
    return findings


def strict_mock_terms_findings(spec: Mapping[str, object]) -> List[InspectionFinding]:
    terms = json_rows(spec, "terms")
    if len(terms) < 5:
        return [
            strict_mock_finding(
                "주요 용어 부족",
                f"주요 용어가 {len(terms)}개입니다.",
                "상태, 권한, 인증, 동의, 정책 판단값에 쓰이는 용어를 보강합니다.",
                target_path="current_chapter.terms",
                tier="P3",
                root_cause="정책·상태·권한 판단에 쓰이는 용어가 부족해 뒤 장의 해석 기준이 약해집니다.",
                patch_hint="일반 명사가 아니라 상태, 고객 유형, 인증·권한, 동의, 데이터 보관, 외부기관, 정책 판단값 용어를 추가합니다.",
                acceptance_check="terms가 5개 이상이고 추가 용어가 정책 판단 기준에 쓰이는 용어여야 합니다.",
            )
        ]
    generic = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(terms)
        if strict_generic_text(row.get("description", ""), allow_policy_markers=True)
    ]
    if len(generic) >= max(4, int(len(terms) * 0.35)):
        return [
            strict_mock_finding(
                "용어 설명 판단 기준 부족",
                f"용어 설명 {len(generic)}건이 업무상 판단 기준보다 일반 설명에 가깝습니다.",
                "각 용어 설명에 상태/권한/조건/정책 판단에서 어떻게 쓰이는지를 포함합니다.",
                target_path="current_chapter.terms[*].description",
                tier="P3",
                root_cause="용어 설명이 사전적 정의에 머물러 프로세스·정책에서 같은 뜻으로 재사용하기 어렵습니다.",
                patch_hint="용어별 description에 '어떤 상태/권한/조건/정책 판단에 사용되는지'를 한 문장으로 추가합니다.",
                acceptance_check="일반 설명으로 보이는 terms.description 비율이 35% 미만이어야 합니다.",
            )
        ]
    return []


def strict_mock_state_findings(
    states: Sequence[Mapping[str, object]],
    transitions: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    generic_states = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(states)
        if strict_generic_text(row.get("description", ""))
    ]
    if len(states) >= 5 and len(generic_states) >= max(3, int(len(states) * 0.45)):
        findings.append(
            strict_mock_finding(
                "상태 설명 일반화",
                f"상태 설명 {len(generic_states)}건이 고객 노출, 기능 허용, 후속 처리 기준을 충분히 드러내지 않습니다.",
                "상태별로 업무 가능 여부, 후속 처리, 제한/복구 기준을 짧게 보강합니다.",
                target_path="current_chapter.states[*].description",
                tier="P2",
                root_cause="상태 설명이 단순 처리 단계처럼 작성되어 기능 허용, 정책 판단, 후속 처리 기준으로 사용하기 어렵습니다.",
                patch_hint="각 states.description에 고객에게 노출되는 의미, 허용/제한되는 기능, 다음 처리 기준 중 1개 이상을 포함합니다.",
                acceptance_check="일반화된 states.description 비율이 45% 미만이어야 합니다.",
            )
        )
    generic_criteria = [
        str(index)
        for index, row in enumerate(transitions)
        if strict_generic_text(row.get("criteria", ""))
    ]
    if len(transitions) >= 5 and len(generic_criteria) >= max(3, int(len(transitions) * 0.45)):
        findings.append(
            strict_mock_finding(
                "상태 전이 조건 일반화",
                f"상태 전이 기준 {len(generic_criteria)}건이 '기준 충족' 수준의 일반 조건으로 보입니다.",
                "전이 기준에 판정 주체, 조건, 실패/보류/제한 분기를 구분할 수 있는 문장을 보강합니다.",
                target_path="current_chapter.state_transitions[*].criteria",
                tier="P2",
                root_cause="전이 기준이 일반 조건으로만 쓰여 실제 어떤 사건과 판정으로 상태가 바뀌는지 알기 어렵습니다.",
                patch_hint="criteria에 BSS/채널/고객/운영자 중 판정 주체와 성공·실패·보류·제한 조건을 구분해 씁니다.",
                acceptance_check="일반화된 state_transitions.criteria 비율이 45% 미만이어야 합니다.",
            )
        )
    generic_events = [
        str(index)
        for index, row in enumerate(transitions)
        if strict_state_event_is_generic(row.get("event", ""))
    ]
    if len(transitions) >= 5 and len(generic_events) >= max(3, int(len(transitions) * 0.35)):
        findings.append(
            strict_mock_finding(
                "상태 전이 이벤트 일반화",
                f"상태 전이 이벤트 {len(generic_events)}건이 조건 충족, 처리 성공 같은 일반 사건으로 보입니다.",
                "event를 연결된 유즈케이스 흐름에서 실제 상태를 바꾸는 업무 사건명으로 바꿉니다.",
                target_path="current_chapter.state_transitions[*].event",
                tier="P2",
                root_cause="event가 추상 판정 결과로만 쓰여 usecase_ids와 상태 전이의 업무 추적성이 약합니다.",
                patch_hint="'고객 최종 요청 접수', 'BSS 반영 성공 회신', '인증 실패 횟수 초과', '운영 보정 완료'처럼 상태를 바꾸는 업무 사건으로 작성합니다.",
                acceptance_check="일반화된 state_transitions.event 비율이 35% 미만이어야 합니다.",
            )
        )
    return findings


def strict_mock_process_findings(processes: Sequence[Mapping[str, object]]) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if not processes:
        return findings
    policy_signatures = [
        tuple(sorted(str(item).strip() for item in row.get("related_policies", []) if str(item).strip()))
        for row in processes
        if isinstance(row.get("related_policies"), list)
    ]
    non_empty_policy_signatures = [signature for signature in policy_signatures if signature]
    if len(non_empty_policy_signatures) >= 5:
        repeated = max(
            non_empty_policy_signatures.count(signature)
            for signature in set(non_empty_policy_signatures)
        )
        if repeated >= max(4, int(len(policy_signatures) * 0.60)):
            findings.append(
                strict_mock_finding(
                    "프로세스 정책 연결 반복",
                    f"동일한 관련 정책 묶음이 {repeated}개 프로세스에서 반복됩니다.",
                    "프로세스별 판단 지점에 맞는 정책 그룹만 연결하고, 공통 정책은 필요한 프로세스에만 남깁니다.",
                    target_path="current_chapter.processes[*].related_policies",
                    tier="P2",
                    root_cause="프로세스마다 같은 정책 묶음이 반복되어 프로세스별 정책 판단 지점이 구분되지 않습니다.",
                    patch_hint="각 프로세스의 입력·판정·처리·결과 전환에 직접 필요한 정책만 남기고, 나머지 공통 정책은 실제 적용 프로세스에만 연결합니다.",
                    acceptance_check="동일한 related_policies 묶음이 전체 프로세스의 60% 이상 반복되지 않아야 합니다.",
                )
            )
    generic_descriptions = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(processes)
        if strict_generic_text(row.get("description", ""))
    ]
    if len(processes) >= 5 and len(generic_descriptions) >= max(3, int(len(processes) * 0.45)):
        findings.append(
            strict_mock_finding(
                "프로세스 설명 일반화",
                f"프로세스 설명 {len(generic_descriptions)}건이 실제 업무 전환점보다 일반 처리 문장에 가깝습니다.",
                "각 프로세스가 어떤 입력·판정·처리·결과 전환을 만드는지 구분해 작성합니다.",
                target_path="current_chapter.processes[*].description",
                tier="P2",
                root_cause="프로세스가 고객/운영자 업무 전환점이 아니라 일반 처리 문장으로만 작성됐습니다.",
                patch_hint="description에 시작 조건, 주요 판정, 처리 결과, 예외/제한 시 다음 행동 중 2개 이상을 반영합니다.",
                acceptance_check="일반화된 processes.description 비율이 45% 미만이어야 합니다.",
            )
        )
    refs_without_policy_id = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(processes)
        if isinstance(row.get("related_policies"), list)
        and any(str(policy).strip() and not str(policy).strip().startswith("PG-") for policy in row.get("related_policies", []))
    ]
    if refs_without_policy_id:
        findings.append(
            strict_mock_finding(
                "프로세스 관련 정책 ID 부족",
                f"관련 정책에 정책 ID 없이 명칭만 쓰인 프로세스가 있습니다: {', '.join(refs_without_policy_id[:8])}",
                "processes.related_policies를 정책 ID와 정책명 조합으로 정리합니다.",
                target_path="current_chapter.processes[*].related_policies",
                tier="P2",
                root_cause="프로세스와 정책 목록의 추적성이 약해 최종 문서에서 정책명 불일치가 발생할 수 있습니다.",
                patch_hint="'PG-XXX-YYY 정책명' 형식으로 policy_groups.id와 name을 함께 참조합니다.",
                acceptance_check="processes.related_policies의 모든 값이 정책 ID 또는 승인된 정책 참조 형식을 포함해야 합니다.",
            )
        )
    return findings


def strict_mock_function_findings(functions: Sequence[Mapping[str, object]]) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    stutter_names = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(functions)
        if strict_label_has_adjacent_duplicate(str(row.get("name", "")))
    ]
    if stutter_names:
        findings.append(
            strict_mock_finding(
                "기능명 반복 토큰",
                "기능명에 같은 의미 토큰이 반복된 항목이 있습니다: " + ", ".join(stutter_names[:8]),
                "기능명에서 '정보 정보', '기준 기준'처럼 반복되는 단어를 제거하고 처리 책임이 드러나는 이름으로 정리합니다.",
                target_path="current_chapter.functions[*].name",
                tier="P3",
                root_cause="Mock 보정 과정에서 요구사항 키워드와 기능 접미사가 겹치며 어색한 기능명이 생성됐습니다.",
                patch_hint="'상품 정보 정보 구성'은 '상품 정보 구성'으로, '운영 기준 기준 관리'는 '운영 기준 관리'처럼 줄입니다.",
                acceptance_check="functions.name에 인접한 동일 토큰 반복이 없어야 합니다.",
            )
        )
    descriptions = [compact_space(row.get("description", "")) for row in functions if str(row.get("description", "")).strip()]
    if len(descriptions) >= 4:
        repeated = max(descriptions.count(description) for description in set(descriptions))
        if repeated >= max(4, int(len(descriptions) * 0.50)):
            findings.append(
                strict_mock_finding(
                    "기능 설명 반복",
                    f"동일한 기능 설명이 {repeated}개 기능에서 반복됩니다.",
                    "기능별 설명을 조회, 검증, 산정, 저장, 알림, 연동 등 실제 처리 책임과 결과가 드러나게 구분합니다.",
                    target_path="current_chapter.functions[*].description",
                    tier="P2",
                    root_cause="여러 기능이 같은 설명을 공유해 개발자가 기능별 책임과 결과를 구분하기 어렵습니다.",
                    patch_hint="각 functions.description을 '무엇을 처리해 어떤 결과를 만든다' 형태로 바꾸고, 조회/검증/저장/알림/연동 책임을 구분합니다.",
                    acceptance_check="동일한 functions.description이 전체 기능의 50% 이상 반복되지 않아야 합니다.",
                )
            )
    generic_details = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(functions)
        if isinstance(row.get("details"), list)
        and any(strict_mock_function_detail_is_generic(item) for item in row.get("details", []))
    ]
    if len(functions) >= 5 and len(generic_details) >= max(3, int(len(functions) * 0.45)):
        findings.append(
            strict_mock_finding(
                "세부 기능 구성 일반화",
                f"세부 기능 구성 {len(generic_details)}개 기능에서 일반 처리 표현이 반복됩니다.",
                "세부 기능 구성은 정책값이나 프로세스 단계가 아니라 짧은 하위 처리명으로 구체화합니다.",
                target_path="current_chapter.functions[*].details",
                tier="P2",
                root_cause="details가 조회/검증/저장 같은 너무 넓은 단어 또는 일반 처리 표현으로 반복됩니다.",
                patch_hint="'고객 상태 조회', '권한 조건 검증', '처리 결과 저장', '제한 사유 안내'처럼 기능별 2~5개 하위 처리명으로 바꿉니다.",
                acceptance_check="일반화된 functions.details 보유 기능 비율이 45% 미만이어야 합니다.",
            )
        )
    weak_result_functions = [
        str(row.get("id", "")).strip() or str(index)
        for index, row in enumerate(functions)
        if not function_description_has_result(row.get("description", ""))
    ]
    if len(functions) >= 5 and len(weak_result_functions) >= max(3, int(len(functions) * 0.40)):
        findings.append(
            strict_mock_finding(
                "기능 설명 결과 기준 부족",
                f"기능 설명 {len(weak_result_functions)}건에서 처리 결과가 약합니다.",
                "기능 설명에 처리 입력 또는 판단 대상과 산출 결과를 함께 드러냅니다.",
                target_path="current_chapter.functions[*].description",
                tier="P2",
                root_cause="기능 설명이 수행 동작만 말하고 어떤 결과를 생성하는지 부족합니다.",
                patch_hint="'고객 상태를 조회해 처리 가능 상태를 판정한다', '처리 결과를 저장하고 고객 안내 항목을 생성한다'처럼 결과 명사를 포함합니다.",
                acceptance_check="처리 결과가 약한 functions.description 비율이 40% 미만이어야 합니다.",
            )
        )
    return findings


def strict_mock_policy_findings(
    policy_groups: Sequence[Mapping[str, object]],
    policy_details: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if not policy_details:
        return findings
    vague_ids: List[str] = []
    short_ids: List[str] = []
    mechanical_name_ids: List[str] = []
    mechanical_content_ids: List[str] = []
    for index, detail in enumerate(policy_details):
        detail_id = str(detail.get("id", "")).strip() or str(index)
        name = str(detail.get("name", "") or "").strip()
        content = str(detail.get("content", "") or "").strip()
        if len(content) < 24:
            short_ids.append(detail_id)
        if strict_policy_content_is_vague(content):
            vague_ids.append(detail_id)
        if strict_policy_detail_name_has_mechanical_suffix(name):
            mechanical_name_ids.append(detail_id)
        if strict_policy_content_has_mechanical_prefix(content):
            mechanical_content_ids.append(detail_id)
    if short_ids:
        findings.append(
            strict_mock_finding(
                "정책 항목 내용 과소",
                f"정책 항목 내용이 짧은 항목이 있습니다: {', '.join(short_ids[:8])}",
                "정책 항목에는 허용/제한/조건/예외/고지/이력/상태/BSS 기준 중 하나 이상을 문장으로 남깁니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                root_cause="정책 항목 내용이 짧아 개발/QA가 판단 기준이나 테스트 조건으로 변환하기 어렵습니다.",
                patch_hint="짧은 content에 적용 대상, 허용/제한 조건, 예외 또는 이력 저장 기준을 한 문장으로 보강합니다.",
                acceptance_check="policy_details.content가 24자 미만인 항목이 없어야 합니다.",
            )
        )
    if vague_ids:
        findings.append(
            strict_mock_finding(
                "정책 항목 판단값 부족",
                f"정책 항목 {len(vague_ids)}건이 일반 기준 표현으로 보입니다: {', '.join(vague_ids[:8])}",
                "업무별/내부 기준 같은 표현만 두지 말고 실제 허용 조건, 제한 조건, 예외, 고지, 이력, 상태 반영 기준을 선언합니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                is_quality_gate=True,
                root_cause="정책 항목이 '업무별 기준', '내부 기준', '필요 시' 같은 빈 판단 표현에 머물렀습니다.",
                patch_hint="각 content에 조건, 횟수/시간/상태, 예외, 고지, 이력, BSS 반영 중 현재 주제에 필요한 판단값을 명시합니다.",
                acceptance_check="일반 기준 표현이 남은 policy_details.content가 없어야 합니다.",
            )
        )
    if mechanical_name_ids:
        findings.append(
            strict_mock_finding(
                "정책 항목명 단계 suffix 반복",
                f"정책 항목명 {len(mechanical_name_ids)}건에 '- 요청 접수/조건 판정/결과 확정' 같은 작성 단계 suffix가 남아 있습니다: {', '.join(mechanical_name_ids[:8])}",
                "정책 항목명은 판단 대상만 남기고 작성 단계명은 본문에서 필요한 경우에만 자연스럽게 표현합니다.",
                target_path="current_chapter.policy_details[*].name",
                tier="P2",
                is_quality_gate=True,
                root_cause="Mock writer가 정책 항목 의미와 작성 단계 변형값을 한 제목에 결합해 기계적인 항목명을 만들었습니다.",
                patch_hint="'인증번호 유효시간 - 결과 확정'은 '인증번호 유효시간'처럼 줄이고, content는 실제 판단값으로 시작합니다.",
                acceptance_check="policy_details.name에 '- 결과 확정', '- 조건 판정' 같은 단계 suffix가 남지 않아야 합니다.",
            )
        )
    if mechanical_content_ids:
        findings.append(
            strict_mock_finding(
                "정책 항목 기계적 접두어",
                f"정책 항목 본문 {len(mechanical_content_ids)}건이 '조건 판정 시 ... 기준은 ...' 형태로 작성됐습니다: {', '.join(mechanical_content_ids[:8])}",
                "본문은 제목을 다시 풀어쓰지 말고 실제 판단값, 조건, 제한, 예외, 고지, 이력 기준을 바로 선언합니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                is_quality_gate=True,
                root_cause="Mock writer가 정책 항목명과 작성 단계명을 본문 앞에 반복 주입해 문장이 정책값보다 템플릿처럼 보입니다.",
                patch_hint="'조건 판정 시 상태 사용 기준은 판정 결과가...'가 아니라 '상태 사용 기준은 판정 결과가...' 또는 '판정 결과가...'처럼 자연스럽게 고칩니다.",
                acceptance_check="policy_details.content에 '요청 접수 시/조건 판정 시/결과 확정 시 ... 기준은' 패턴이 반복되지 않아야 합니다.",
            )
        )
    missing_decision_ids = [
        str(detail.get("id", "")).strip() or str(index)
        for index, detail in enumerate(policy_details)
        if not policy_content_has_decision_axis(detail.get("content", ""))
    ]
    if len(policy_details) >= 8 and len(missing_decision_ids) >= max(4, int(len(policy_details) * 0.25)):
        findings.append(
            strict_mock_finding(
                "정책 항목 판단축 부족",
                f"정책 항목 {len(missing_decision_ids)}건에 허용·제한·조건·예외·고지·이력·상태·BSS 중 뚜렷한 판단축이 약합니다.",
                "정책 항목마다 실제 판단축을 1개 이상 명시합니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                is_quality_gate=True,
                root_cause="정책 내용이 설명문처럼 작성되어 실제 기준값 또는 판정 조건으로 읽히지 않습니다.",
                patch_hint="각 항목에 '허용한다/제한한다/필수다/저장한다/전환한다/회신한다'처럼 판정 결과가 드러나는 동사를 포함합니다.",
                acceptance_check="판단축이 약한 policy_details.content 비율이 25% 미만이어야 합니다.",
            )
        )
    findings.extend(strict_mock_policy_structure_findings(policy_groups, policy_details))
    return findings


def strict_mock_policy_structure_findings(
    policy_groups: Sequence[Mapping[str, object]],
    policy_details: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    if not policy_groups or not policy_details:
        return findings

    detail_counts: dict[str, int] = {}
    for detail in policy_details:
        policy_id = str(detail.get("policy_id", "")).strip()
        if policy_id:
            detail_counts[policy_id] = detail_counts.get(policy_id, 0) + 1
    one_to_one_groups = [
        str(group.get("id", "")).strip()
        for group in policy_groups
        if str(group.get("id", "")).strip()
        and detail_counts.get(str(group.get("id", "")).strip(), 0) == 1
    ]
    if len(policy_groups) >= 6 and len(one_to_one_groups) >= max(4, int(len(policy_groups) * 0.60)):
        findings.append(
            strict_mock_finding(
                "정책 그룹-항목 1:1 축소",
                f"정책 그룹 {len(one_to_one_groups)}개가 정책 항목 1개로만 구성되어 판단 기준이 넓게 뭉쳤을 수 있습니다.",
                "각 정책 그룹에서 서로 다른 판단 기준은 별도 policy_details 항목으로 분리합니다.",
                target_path="current_chapter.policy_details",
                tier="P2",
                root_cause="정책 그룹이 하나의 설명성 항목으로만 닫혀 조건, 제한, 예외, 고지, 이력 기준을 분리하지 못했습니다.",
                patch_hint="정책 그룹별로 허용 기준, 제한 기준, 예외 기준, 고지/이력 기준이 실제로 다르면 각각 별도 정책 항목으로 나눕니다.",
                acceptance_check="정책 그룹 60% 이상이 policy_details 1개만 갖는 구조가 아니어야 합니다.",
            )
        )

    prefixes: dict[str, int] = {}
    for detail in policy_details:
        prefix = strict_policy_sentence_prefix(detail.get("content", ""))
        if prefix:
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
    repeated_prefixes = [prefix for prefix, count in prefixes.items() if count >= max(5, int(len(policy_details) * 0.18))]
    if repeated_prefixes:
        findings.append(
            strict_mock_finding(
                "정책 항목 문장 패턴 반복",
                "정책 항목 여러 건이 같은 문장 패턴으로 시작합니다: " + ", ".join(repeated_prefixes[:4]),
                "반복 문장 패턴을 줄이고 정책 항목별 판단 대상과 결과를 다르게 씁니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                is_quality_gate=True,
                root_cause="정책 항목이 템플릿 문장으로 반복되어 항목별 실제 판단 차이가 흐려졌습니다.",
                patch_hint="같은 prefix를 공유하는 항목은 적용 대상, 조건, 제한 결과, 예외, 이력 기준 중 무엇이 다른지 content 앞부분부터 다르게 작성합니다.",
                acceptance_check="동일 정책 문장 prefix가 policy_details의 18% 이상 또는 5건 이상 반복되지 않아야 합니다.",
            )
        )
    perspective_pattern_ids = [
        str(detail.get("id", "")).strip() or str(index)
        for index, detail in enumerate(policy_details)
        if strict_policy_perspective_pattern(detail.get("content", ""))
    ]
    if len(policy_details) >= 8 and len(perspective_pattern_ids) >= max(4, int(len(policy_details) * 0.20)):
        findings.append(
            strict_mock_finding(
                "정책 항목 관점 문장 반복",
                f"정책 항목 {len(perspective_pattern_ids)}건이 '{{항목}} 기준의 {{관점}} 관점에서' 형태의 반복 문장으로 작성됐습니다.",
                "정책 항목명은 제목에 두고, 본문은 실제 기준값·조건·제한·예외·고지·이력 기준을 바로 선언합니다.",
                target_path="current_chapter.policy_details[*].content",
                tier="P2",
                is_quality_gate=True,
                root_cause="Mock writer가 정책 항목 제목을 본문 앞에 반복 주입하면서 문서가 정책값보다 템플릿 문장처럼 보입니다.",
                patch_hint="'인증번호 유효시간 기준의 기본 관점에서 인증 유효 시간은...'이 아니라 '인증 유효 시간은 10분이며...'처럼 판단 기준을 직접 씁니다.",
                acceptance_check="정책 본문에서 '기준의 ... 관점' 패턴이 정책 상세의 20% 이상 반복되지 않아야 합니다.",
            )
        )
    return findings


def strict_label_has_adjacent_duplicate(value: str) -> bool:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", str(value or ""))
    return any(left == right and left for left, right in zip(tokens, tokens[1:]))


def strict_policy_perspective_pattern(value: object) -> bool:
    text = compact_space(value)
    return bool(re.search(r"기준의\s*[가-힣A-Za-z0-9·/ ]{1,12}\s*관점에서", text))


def strict_policy_detail_name_has_mechanical_suffix(value: object) -> bool:
    text = compact_space(value)
    return bool(
        re.search(
            r"\s-\s(요청 접수|조건 판정|결과 확정|예외 처리|후속 안내|이력 관리|연계 확인|운영 검토|충돌 확인|품질 확인|취소 판단)$",
            text,
        )
    )


def strict_policy_content_has_mechanical_prefix(value: object) -> bool:
    text = compact_space(value)
    return bool(
        re.search(
            r"^(요청 접수|조건 판정|결과 확정|예외 처리|후속 안내|이력 저장|연계 확인|운영 검토|품질 확인)\s*시\s*[^.]{2,80}기준은\s*",
            text,
        )
    ) or bool(
        re.search(
            r"^(접수 허용 기준|제한 안내 기준|이력 저장 기준|재검증 기준|상담 전환 기준|결과 회신 기준|운영 확인 기준|고객 고지 기준)\s*:\s*[^.]{2,100}기준은\s*",
            text,
        )
    ) or bool(re.search(r"기준은\s*(허용 대상은|제한 조건은|BSS 반영은|판정 결과가|처리 결과가)", text))


def strict_mock_final_check_findings(spec: Mapping[str, object]) -> List[InspectionFinding]:
    final_check = spec.get("final_check", []) if isinstance(spec.get("final_check"), list) else []
    required_terms = ("유즈케이스", "프로세스", "기능", "정책", "상태")
    text = " ".join(str(item) for item in final_check)
    missing = [term for term in required_terms if term not in text]
    if missing:
        return [
            strict_mock_finding(
                "최종 점검 연결 항목 부족",
                "최종 점검 기준에 핵심 연결 축이 일부 보이지 않습니다: " + ", ".join(missing),
                "최종 점검 기준에 유즈케이스, 상태, 프로세스, 기능, 정책 연결성을 확인하는 항목을 포함합니다.",
                target_path="current_chapter.final_check",
                tier="P2",
                root_cause="최종 점검 기준이 문서 전체 연결성을 확인하기에 부족합니다.",
                patch_hint="final_check 항목에 누락된 연결 축을 별도 점검 항목으로 추가합니다.",
                acceptance_check="final_check 텍스트에 유즈케이스, 상태, 프로세스, 기능, 정책 연결성이 모두 포함되어야 합니다.",
            )
        ]
    return []


def strict_mock_document_findings(
    body: str,
    text: str,
    metrics: Mapping[str, object],
    scope: str,
) -> List[InspectionFinding]:
    del body
    findings: List[InspectionFinding] = []
    if scope_rank(scope) >= 10 or scope in {"full", "final"}:
        policy_count = int(metrics.get("policy_item_count", 0) or 0)
        process_count = int(metrics.get("process_count", 0) or 0)
        function_count = int(metrics.get("function_count", 0) or 0)
        if process_count >= 10 and function_count and function_count < max(3, int(process_count * 0.25)):
            findings.append(
                strict_mock_finding(
                    "최종 기능 밀도 낮음",
                    f"프로세스 {process_count}개 대비 기능 {function_count}개로 기능 분해가 약할 수 있습니다.",
                    "기능은 프로세스 수행 역량 단위로 묶되, 업무 흐름을 구현 가능한 수준으로 분해합니다.",
                    target_path="document.functions",
                    tier="P2",
                    root_cause="최종 문서에서 프로세스 대비 기능 수가 낮아 업무 절차가 구현 단위로 충분히 분해되지 않았을 수 있습니다.",
                    patch_hint="기능 장에서 조회·검증·산정·저장·알림·연동·이력 같은 처리 역량을 확인하고 누락된 기능을 보강합니다.",
                    acceptance_check="최종 문서의 기능 수가 프로세스 수 대비 현저히 낮지 않아야 하며, 복합 프로세스에는 복수 기능이 연결되어야 합니다.",
                )
            )
        if policy_count and count_strict_policy_vague_phrases(text) >= max(4, int(policy_count * 0.08)):
            findings.append(
                strict_mock_finding(
                    "최종 정책 표현 일반화",
                    "최종 문서에 업무별 기준, 내부 기준, 필요 시 같은 일반 정책 표현이 다수 남아 있습니다.",
                    "정책 항목을 실제 허용/제한/예외/고지/이력/상태 반영 기준으로 보강합니다.",
                    target_path="document.policy_details",
                    tier="P2",
                    is_quality_gate=True,
                    root_cause="최종 정책 상세에 빈 판단 표현이 남아 개발/QA가 구체 기준으로 사용하기 어렵습니다.",
                    patch_hint="정책 장에서 일반 표현이 포함된 policy_details.content를 찾아 조건, 제한, 예외, 고지, 이력, 상태/BSS 반영 기준으로 교체합니다.",
                    acceptance_check="최종 문서에서 업무별 기준, 내부 기준, 필요 시, 별도 기준 같은 표현이 반복되지 않아야 합니다.",
                )
            )
    return findings


def strict_state_event_is_generic(value: object) -> bool:
    text = compact_space(value)
    if not text or len(text) < 5:
        return True
    generic_events = (
        "조건 충족",
        "조건 확인",
        "정책 제한",
        "처리 성공",
        "처리 실패",
        "처리 완료",
        "자동 처리 불가",
        "대상 정보 확인 완료",
        "고객이 업무에 진입",
        "운영자 확인 필요",
    )
    if text in generic_events:
        return True
    if re.fullmatch(r"(처리|검증|조회|확인|요청|결과)\s*(성공|실패|완료|필요|가능|불가)?", text):
        return True
    return False


def function_description_has_result(value: object) -> bool:
    text = compact_space(value)
    if not text:
        return False
    result_markers = (
        "판정",
        "결정",
        "분류",
        "생성",
        "구성",
        "저장",
        "반영",
        "전환",
        "회신",
        "안내",
        "연결",
        "제공",
        "산정",
        "확정",
    )
    return any(marker in text for marker in result_markers)


def strict_mock_function_detail_is_generic(value: object) -> bool:
    text = compact_space(value)
    if not text:
        return True
    concrete_actions = (
        "조회",
        "검증",
        "확인",
        "판정",
        "산정",
        "저장",
        "안내",
        "고지",
        "알림",
        "구성",
        "연동",
        "분류",
        "반영",
        "복구",
    )
    concrete_objects = (
        "고객",
        "상태",
        "권한",
        "조건",
        "요청",
        "결과",
        "이력",
        "제한",
        "예외",
        "동의",
        "인증",
        "BSS",
        "연계",
        "사유",
    )
    if any(action in text for action in concrete_actions) and any(obj in text for obj in concrete_objects):
        return False
    vague_labels = {
        "처리",
        "관리",
        "제공",
        "구성",
        "확인",
        "기준",
        "업무",
        "정보",
        "결과",
    }
    return text in vague_labels or len(text) < 4


def policy_content_has_decision_axis(value: object) -> bool:
    text = compact_space(value)
    if not text:
        return False
    if re.search(r"\d+\s*(회|분|시간|일|원|개월|년|%)", text):
        return True
    markers = (
        "허용",
        "제한",
        "금지",
        "필수",
        "예외",
        "고지",
        "알림",
        "이력",
        "저장",
        "보관",
        "파기",
        "상태",
        "전환",
        "BSS",
        "회신",
        "반영",
        "인증",
        "동의",
        "만료",
        "취소",
        "보류",
        "실패",
        "복구",
        "재시도",
        "상담",
        "우선순위",
        "기준일",
    )
    return any(marker in text for marker in markers)


def strict_policy_sentence_prefix(value: object) -> str:
    text = compact_space(value)
    if not text:
        return ""
    text = re.sub(r"^(접수 허용 기준|제한 안내 기준|이력 저장 기준|재검증 기준|상담 전환 기준|결과 회신 기준|운영 확인 기준|고객 고지 기준)\s*:\s*", "", text)
    text = re.sub(r"\d+\s*(회|분|시간|일|원|개월|년|%)", "{값}", text)
    chunks = re.split(r"[.,;。]|<br\s*/?>", text, maxsplit=1)
    prefix = compact_space(chunks[0])[:34]
    if len(prefix) < 12:
        return ""
    return prefix


def strict_generic_text(value: object, *, allow_policy_markers: bool = False) -> bool:
    text = compact_space(value)
    if not text or len(text) < 12:
        return True
    generic_markers = (
        "기준을 충족",
        "조건을 확인",
        "처리한다",
        "관리한다",
        "제공한다",
        "구성한다",
        "필요한 기준",
        "업무 요청",
        "업무 시작",
        "업무별",
        "관련 기준",
        "내부 기준",
        "시스템 기준",
    )
    concrete_markers = (
        "허용",
        "제한",
        "금지",
        "필수",
        "예외",
        "고지",
        "알림",
        "이력",
        "저장",
        "상태",
        "BSS",
        "본인확인",
        "로그인",
        "동의",
        "만료",
        "취소",
        "보류",
        "실패",
        "복구",
    )
    if re.search(r"\d+\s*(회|분|시간|일|원|개월|년|%)", text):
        return False
    if allow_policy_markers and any(marker in text for marker in concrete_markers):
        return False
    return any(marker in text for marker in generic_markers) and not any(marker in text for marker in concrete_markers)


def strict_policy_content_is_vague(value: object) -> bool:
    text = compact_space(value)
    if not text:
        return True
    vague_markers = (
        "업무별 권한 기준",
        "업무별 기준",
        "내부 기준",
        "시스템 기준",
        "관련 정책",
        "필요 시",
        "별도 기준",
        "기준을 함께 적용",
        "함께 적용한다",
        "고객 영향, 예외, 고지, 이력 저장 기준",
        "기준을 충족한 경우",
        "조건을 충족한 경우",
        "적절히",
    )
    if not any(marker in text for marker in vague_markers):
        return False
    concrete_markers = (
        "허용",
        "제한",
        "금지",
        "필수",
        "예외",
        "고지",
        "알림",
        "이력",
        "저장",
        "상태",
        "BSS",
        "본인확인",
        "로그인",
        "동의",
        "만료",
        "취소",
        "보류",
        "실패",
        "복구",
    )
    if re.search(r"\d+\s*(회|분|시간|일|원|개월|년|%)", text):
        return False
    return sum(1 for marker in concrete_markers if marker in text) < 2


def count_strict_policy_vague_phrases(text: str) -> int:
    return sum(
        text.count(marker)
        for marker in (
            "업무별 기준",
            "업무별 권한 기준",
            "내부 기준",
            "시스템 기준에 따라",
            "시스템 기준으로 처리",
            "시스템 기준을 적용",
            "관련 정책에 따라",
            "필요 시",
            "별도 기준",
        )
    )


def inspector_llm_task_max_attempts() -> int:
    value = os.getenv("OPENAI_INSPECTOR_TASK_MAX_ATTEMPTS", "").strip()
    try:
        return max(1, int(value)) if value else DEFAULT_INSPECTOR_LLM_TASK_MAX_ATTEMPTS
    except ValueError:
        return DEFAULT_INSPECTOR_LLM_TASK_MAX_ATTEMPTS


def inspector_llm_retry_delay_seconds(attempt: int) -> float:
    base = parse_float_env("OPENAI_INSPECTOR_RETRY_BASE_SECONDS", DEFAULT_INSPECTOR_LLM_RETRY_BASE_SECONDS)
    max_delay = max(base, parse_float_env("OPENAI_INSPECTOR_RETRY_MAX_SECONDS", DEFAULT_INSPECTOR_LLM_RETRY_MAX_SECONDS))
    return min(max_delay, base * (2 ** max(0, attempt - 1)))


def parse_float_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    try:
        return max(0.0, float(value)) if value else default
    except ValueError:
        return default


def notify_llm_retry(callback: object | None, event: Mapping[str, object]) -> None:
    if callable(callback):
        try:
            callback(dict(event))
        except Exception:
            return


def llm_inspection_instructions(
    topic: str,
    template_type: str,
    scope: str,
    brief: str = "",
    inspection_mode: str = "chapter-final",
) -> str:
    stage_profile = stage_inspector_profile(scope)
    return "\n".join(
        [
            "너는 통합채널 정책서 inspector다.",
            "문서를 처음부터 현재 작성 범위까지 누적 검수하고, 챕터 간 정합성과 샘플 수준을 확인한다.",
            final_inspection_role_instruction(inspection_mode, scope),
            inspection_scope_guard_instruction(inspection_mode, scope),
            stage_inspector_profile_instruction(stage_profile),
            insight_applicability_for_prompt(),
            policy_style_anchor_inspection_rule(scope),
            "검수 결과는 오류 또는 경고 findings로만 표현한다. 문제가 없으면 findings는 빈 배열로 둔다.",
            "현재 작성 범위에서 고칠 수 있는 문제를 우선 findings로 작성한다.",
            "PI Agent 관점은 독립 보조 검수로 사용한다. As-Is 복사, 중복 단계, 현업 받아쓰기, AI 끼워넣기, 예외 각주화, KPI 부재를 확인하되 정책서 템플릿을 PI 산출물 양식으로 바꾸라고 요구하지 않는다.",
            "전문 방법론은 액터·유즈케이스·상태·프로세스·정책의 의미 품질을 검수하는 기준으로만 쓴다. 템플릿·샘플에 없는 장이나 상세 양식을 추가하라고 요구하지 않는다.",
            "finding에는 fix_owner를 반드시 지정한다. 현재 장이 이전 장을 잘못 이어받은 문제는 current_chapter, 이전 장 자체의 누락·오류가 원인이면 upstream_chapter, 여러 장이 함께 어긋나면 cross_chapter, 후속 장에서 채울 문제는 defer_to_later다.",
            "Authoring Blueprint는 검증된 작성 가설이지 절대 정답이 아니다. support_context의 blueprint_quality_gate에 risk_flag가 있으면 해당 위험이 실제 산출물에 반영됐는지 확인하고, Blueprint 자체 오류가 명확하면 fix_owner를 cross_chapter로 둔다.",
            "upstream_chapter를 지정할 때는 upstream_chapter 필드에 overview, terms, actors, usecases, state, process, functions, policies 중 하나를 넣는다.",
            "이전 장은 기본적으로 통과된 기준선이다. 단, 현재 장에서 정상적으로 이어받을 수 없을 정도로 이전 장의 정의 자체가 부족하거나 잘못된 경우에만 upstream_chapter로 분류한다.",
            "이전 장과 이번 장이 맞지 않지만 이번 장의 명칭·설명·연결값으로 해결 가능하면 fix_owner는 current_chapter로 둔다.",
            "아직 작성 순서가 오지 않은 미래 장의 누락은 findings로 감점하지 말고 summary에만 언급한다.",
            "개요와 액터 범위에서는 샘플 전체 문서와 분량을 비교해 확장을 요구하지 않는다. 샘플처럼 간결한지와 책임 경계가 선명한지를 본다.",
            "주요 용어 장에는 상태, 권한 조건, 고객 유형, 인증, 동의, 보관 같은 판단 용어가 들어가는 것이 정상이다.",
            "용어 설명에 '상태', '조건', '판정'이 있다는 이유만으로 지적하지 말고, 상태 코드 목록과 실제로 충돌하거나 같은 개념을 다른 이름으로 중복 정의할 때만 지적한다.",
            "액터 장에서는 고객 상태, 자격, 가입 전/후, 정상/제한 같은 차이를 별도 액터로 나누지 않는 것이 원칙이다.",
            "고객 액터가 여러 고객 행위를 포괄하는 것은 정상이며, 자격 차이와 가능/불가 조건은 상태·유즈케이스·정책에서 다룬다.",
            "간소화본에서는 시스템 액터도 BSS, 인증기관, 연계 시스템처럼 책임 단위로 단순화할 수 있다. 실제 판정 책임이 충돌할 때만 지적한다.",
            "액터-유즈케이스, 상태-상태전이, 유즈케이스-프로세스, 프로세스-기능, 프로세스-정책, 정책 목록-정책 상세의 연결을 중점 점검한다.",
            "계층 원칙은 유즈케이스=상위 업무 목표, 프로세스=유즈케이스 완료 절차, 기능=프로세스를 수행하는 처리 역량, 세부 기능 구성=기능의 하위 처리명, 정책=기능 동작값·판단값이다.",
            "04_usecases에서는 유즈케이스가 약관 동의, 본인인증, 정보 입력, 조건 확인, 결과 안내 같은 절차 단계로 쪼개졌으면 finding으로 둔다. 유즈케이스는 고객·운영자 등 사람 액터가 완료하려는 상위 업무 목적이어야 한다.",
            "04_usecases에서는 조회, 검증, 산정, 저장, 알림, 연동처럼 처리 역량에 가까운 행위가 독립 유즈케이스로 올라오면 후속 기능으로 내려야 한다고 지적한다. 단, 작성 주제의 핵심 업무가 인증·연동 권한 확정이라면 고객·운영자가 완료해야 하는 상위 업무 목적으로 볼 수 있고, 이 경우 본인확인·인증번호·인증 결과 확인 같은 하위 절차만 분리 지적한다.",
            "04_usecases에서는 process_target=Y 기준을 고객으로만 보지 말고, 고객·운영자·법정대리인·대리인·관리자처럼 사람이 수행하는 액터 전체로 본다.",
            "06_state에서는 상태 전이 usecase_ids가 승인된 유즈케이스 ID인지 확인하고, event는 해당 유즈케이스 흐름에서 상태를 바꾸는 업무 사건인지 확인한다. event가 유즈케이스명과 다르다는 이유만으로 지적하지 않는다.",
            "09_policies에서는 정책 그룹이 프로세스와 기능의 필요 통제 지점에서 도출됐는지 본다. 정책은 프로세스/기능에 필요한 정책 정의 → 세부 정책 항목 정의 → 항목별 값 정의 순서가 드러나야 한다.",
            "정책 상세는 일반 원칙이 아니라 기능 동작에 필요한 값인지 본다. 인증 수단, 가능 횟수, 유효시간, 제한 기간, 노출 채널, 판정 기준 식별자, 수행 시스템, 고지 항목, 저장 항목처럼 샘플형 정책값이 있는지 확인한다.",
            "출력 한도와 무관하게 문서가 장황해졌는지 본다. 같은 의미 반복, 배경 설명, 근거 없는 일반론, 이전 장 재설명은 문체 또는 샘플 수준 문제로 지적한다.",
            "사용자 작성 요청 메모가 있으면 요구사항·참고자료·AGENTS.md와 충돌하지 않는 범위에서 반영됐는지 확인한다.",
            "화면 UI 상세, API 필드, DB 컬럼, 오류 코드 전체 목록이 본문에 과도하게 들어가면 지적한다.",
            "POL/ACT/US/ST/PR/FN/PG/PI 같은 ID와 업무코드는 ID 컬럼에서만 허용한다. 본문 문장에서 업무명처럼 노출되면 현재 범위에서 지적한다.",
            "각 finding은 Writer가 바로 patch할 수 있어야 한다. target_path에는 가능한 한 current_chapter.<field>[index].<column> 형태의 정확한 수정 위치를 쓴다.",
            "각 finding에는 root_cause, required_change, patch_hint, acceptance_check, keep_constraints, do_not_change를 반드시 채운다.",
            "target_path, root_cause, required_change, patch_hint, acceptance_check 중 하나라도 구체적으로 채울 수 없으면 finding으로 만들지 말고 summary 또는 open issue 성격의 관찰로만 남긴다.",
            "finding은 반드시 '어디에 있는 어떤 내용을 어떻게 바꿀지', '어디에 어떤 내용을 추가할지', '어디에 있는 어떤 내용을 삭제할지' 중 하나로 읽혀야 한다.",
            "root_cause에는 왜 문제인지와 어떤 선행 기준과 충돌하는지 쓴다. required_change에는 반드시 바꿔야 하는 JSON 필드와 값의 방향을 쓴다.",
            "patch_hint에는 대체 문장, 추가해야 할 조건, 삭제해야 할 표현 중 하나 이상을 쓴다. acceptance_check에는 다음 Inspector가 통과로 볼 수 있는 관찰 가능한 조건을 쓴다.",
            "keep_constraints에는 유지해야 할 기존 ID·명칭·간결성·선행 장 기준을 쓰고, do_not_change에는 이번 patch에서 건드리면 안 되는 장/항목을 쓴다.",
            "detail에는 문제 위치 또는 근거 문구를 쓰고, recommendation에는 수정 대상과 대체 표현 또는 보완 기준을 구체적으로 요약한다.",
            "기본 원칙은 현재 장에서 수정 가능한 finding을 우선 작성하는 것이다. 단, 현재 장 Agent가 정상적으로 보완할 수 없고 이전 장의 승인 계약 자체에 누락·오류가 명확한 경우에는 fix_owner=upstream_chapter 또는 cross_chapter로 작성한다. recommendation에는 이전 장에서 추가/수정할 최소 항목과 현재 장 재정렬 기준을 함께 적는다.",
            "06_state에서는 용어·액터·유즈케이스를 직접 수정하라고 기본적으로 요구하지 않는다. 단, 승인된 유즈케이스로는 상태 장이 성립하지 않을 정도로 이전 장 누락·오류가 명확하면 upstream_chapter를 지정하고, 상태 장 안에서 임의로 새 유즈케이스를 만들지 않는다.",
            "06_state에서는 상태 설명의 원인 범위와 전이 criteria의 원인 범위가 같은지 확인한다. 설명에 있는 원인이 전이로 도달하지 않거나 전이 조건이 설명보다 넓으면 현재 장 수정 finding으로 둔다.",
            "06_state에서는 이전 유즈케이스에 없는 임시저장·재개·운영 처리·고객별 결과 확정 책임을 상태가 새로 가정하지 않는지 확인한다.",
            "06_state에서는 같은 현재 상태에서 제한·실패·보류·완료 분기가 동시에 가능하면 우선순위 또는 배타 조건이 criteria에 있는지 확인한다.",
            "06_state에서는 모든 사건 조합의 전이 행을 요구하지 않는다. 같은 후속 조치로 처리 가능한 예외는 상태 설명이나 criteria를 좁히는 보완을 우선 권고한다.",
            "06_state에서 누락 전이는 고객 주 흐름이 막히거나 states.next_action이 명시한 경로가 전이표에 없을 때만 P1/P2 finding으로 둔다. 단순 조합 누락은 open issue 성격으로 summary에 남긴다.",
            "06_state finding의 recommendation은 '수정대상: ... / 수정방식: ... / 유지조건: ... / 검증조건: ...' 형식으로 작성한다.",
            "07_process에서는 개요·용어·액터·유즈케이스·상태 장 자체를 고치라는 finding을 기본적으로 만들지 않는다. 단, 승인된 유즈케이스나 상태 기준으로는 프로세스 장이 성립하지 않을 정도로 이전 장 누락·오류가 명확하면 upstream_chapter를 지정하고, 프로세스 장에서 임의로 새 기준을 만들지 않는다.",
            "07_process에서는 사람 액터 Y 유즈케이스가 1개 프로세스로만 끝나면 구조 점검 신호로 본다. 이때 무조건 프로세스를 추가하라고 하지 말고, 유즈케이스가 절차 단계처럼 너무 작으면 upstream_chapter로 상위 업무 유즈케이스에 병합·확대하도록 제안하고, 유즈케이스가 적절한 상위 업무라면 현재 장에서 시작·입력/선택·인증/동의·검증/판정·요청/반영·결과 안내 중 실제 책임 경계로 프로세스를 분해하도록 제안한다.",
            "07_process에서는 프로세스가 조회·검증·저장·알림 같은 기능명 나열로 작성되면 current_chapter finding으로 둔다. 프로세스는 고객/운영자가 경험하는 업무 전환점이어야 한다.",
            "07_process에서는 작성 순서상 관련 기능과 관련 정책이 아직 비어 있는 것이 정상이다. related_functions, related_policies 공란은 08_functions와 09_policies 이후에만 문제로 본다.",
            "08_functions에서는 기능이 프로세스명을 그대로 복사하거나 모든 프로세스에 기능 1개만 붙는 구조를 품질 결함으로 본다. 공통 기능은 동일 기능 ID를 여러 process_ids에 재사용하고, details는 짧은 하위 처리명이어야 한다.",
            "function_detail에서는 sub_functions가 프로세스 단계명이나 정책 항목명이 아니라 기능 하위 처리 구성인지 확인한다.",
            "findings 개수에 하드 제한을 두지 않는다. 현재 챕터에서 고쳐야 하는 실질 문제가 여러 개면 모두 작성하되, 같은 원인의 반복 지적은 하나의 finding으로 묶는다.",
            "summary는 3문장 이내로 작성한다. detail과 recommendation은 짧게 쓰되, 별도 구조화 필드에는 patch에 필요한 구체 내용을 생략하지 않는다.",
            "recommendation에는 가능하면 '유지할 것'도 함께 적는다. 예: 샘플 간소화본 수준의 짧은 문장은 유지하고 범위 문장 1개만 보완한다.",
            "추상 표현만 있는 finding은 만들지 않는다. '구체화 필요'라고만 쓰지 말고 어떤 문장/표현/연결을 어떻게 바꿀지 적는다.",
            f"주제: {topic or '-'}",
            f"템플릿 유형: {template_type}",
            f"검수 범위: {scope}",
            f"Inspector 실행 모드: {normalized_inspection_mode_for_inspector(inspection_mode)}",
            f"사용자 작성 요청 메모: {brief.strip() if str(brief or '').strip() else '-'}",
            "반드시 요청된 JSON 스키마에 맞는 JSON만 작성한다.",
        ]
    )


def llm_inspection_prompt(
    body: str,
    text: str,
    deterministic_findings: Sequence[InspectionFinding],
    metrics: dict,
    template_type: str,
    scope: str,
    topic: str,
    brief: str = "",
    inspection_mode: str = "chapter-final",
) -> str:
    context = llm_inspection_context(body, text, scope, deterministic_findings)
    inspection_pack = {
        "metrics": compact_inspection_metrics(metrics),
        "rule_findings": [asdict(finding) for finding in deterministic_findings],
        "outline": context["summary"].get("headings", []),
        "connections": context["summary"].get("connections", {}),
        "section_excerpts": context["section_excerpts"],
        "final_inspector_profile": final_inspection_profile(inspection_mode, scope),
        "stage_inspector_profile": stage_inspector_profile(scope),
        "insight_applicability": insight_applicability_summary(),
    }
    if context["focused_html"]:
        inspection_pack["table_structure_excerpt"] = context["focused_html"]
    parts = [
        f"정책서 주제: {topic or '-'}",
        f"템플릿 유형: {template_type}",
        f"검수 범위: {scope}",
        f"Inspector 실행 모드: {normalized_inspection_mode_for_inspector(inspection_mode)}",
        f"사용자 작성 요청 메모: {brief.strip() if str(brief or '').strip() else '-'}",
        "압축 검수 팩(JSON):\n" + json.dumps(inspection_pack, ensure_ascii=False, indent=2),
    ]
    parts.extend(
        [
            "검수 요청:\n압축 검수 팩은 문서 처음부터 현재 범위까지의 핵심 구조, 연결성, 발췌를 담고 있다. 규칙 기반 검수에서 놓칠 수 있는 챕터 간 정합성, 정책 구체성, 샘플 수준 부족, 누락 위험을 찾아줘.",
            final_inspection_prompt_rule(inspection_mode, scope),
            "이전 장 처리 기준:\n현재 범위 이전 장은 통과된 기준선으로 본다. 보완 recommendation은 원칙적으로 이번 장에서 바꿀 문장, 행, 연결값, 다이어그램 요소로 작성한다. 단, 이번 장이 정상적으로 이어받을 수 없을 정도로 이전 장의 승인 계약 자체가 누락·오류인 경우에는 fix_owner=upstream_chapter 또는 cross_chapter로 분류하고, 이전 장에서 고칠 최소 항목과 현재 장 재정렬 기준을 함께 작성한다.",
            "피드백 품질 기준:\nfinding은 '위치/문제/수정 방향/유지 조건'이 드러나야 한다. recommendation에는 Writer가 그대로 반영할 수 있는 문장 수준의 수정 방향을 포함해줘.",
            "피드백 수량 기준:\nfindings 개수에 하드 제한을 두지 않는다. Writer가 고쳐야 하는 실질 문제는 충분히 모두 작성하고, 같은 원인의 문제만 하나로 묶어라. Writer가 현재 챕터를 다시 쓸 때 바로 반영할 수 없는 장황한 분석은 summary로도 쓰지 마라.",
            "주의:\n현재 범위 이후의 장이 아직 없는 것은 정상이다. 예를 들어 01_overview에서는 액터, 유즈케이스, 상태, 프로세스, 기능, 정책 상세가 아직 없어도 findings로 감점하지 마라.",
            "주의:\n02_terms에서는 상태성 용어 자체를 문제로 보지 마라. 샘플 정책서도 상태, 고객 유형, 인증, 약관, 데이터 보관 용어를 용어 장에서 먼저 정의한다. 다만 후속 상태 전이와 충돌할 만큼 정의가 모호하면 그때만 지적한다.",
            "주의:\n03_actors에서는 가입 고객, 탈퇴 고객, 정상 고객, 제한 고객처럼 상태나 자격 차이를 별도 액터로 분리하라고 요구하지 마라. 고객은 하나의 액터로 두고 차이는 유즈케이스·상태·정책에서 다루는 것이 샘플 기준에 맞다.",
            "주의:\n04_usecases에서는 고객만 Y로 보는 기준을 쓰지 마라. 사람 액터는 Y, 시스템/기관 액터는 N이라는 기준으로 검수한다.",
            "주의:\n01_overview와 03_actors에서는 분량 확대를 권고하지 마라. 샘플 간소화본처럼 짧게 유지하고, 장황한 설명은 오히려 문제로 본다.",
            "주의:\n06_state에서는 이전 장의 용어·유즈케이스를 직접 고치라는 finding을 기본적으로 만들지 말고, 상태 코드/상태 전이 기준 안에서 해결 가능한 보완을 우선 제시한다. 단, 승인된 유즈케이스로 상태 전이가 성립하지 않는 명확한 upstream 결함은 upstream_chapter로 분류한다.",
            "주의:\n07_process에서는 이전 장 자체를 고치라는 finding을 기본적으로 만들지 말고, 프로세스 목록·프로세스 설명·BPMN 흐름 안에서 해결 가능한 보완을 우선 제시한다. 관련 기능/관련 정책 공란은 후속 장에서 채워지므로 감점하지 않는다. 단, 승인된 유즈케이스·상태 기준으로 프로세스가 성립하지 않는 명확한 upstream 결함은 upstream_chapter로 분류한다.",
            "주의:\n07_process에서는 Y 유즈케이스의 프로세스가 1개뿐이면 정상 통과로 보지 말고 입자도 오류 가능성을 점검한다. 해결 방향은 두 가지다. 1) 유즈케이스가 '결과 확인', '조건 확인', '인증 수행'처럼 절차 단계이면 상위 유즈케이스로 병합·확대하도록 upstream_chapter finding을 낸다. 2) 유즈케이스가 업무 목표라면 현재 장에서 의미 있는 판단·처리·결과·예외 경계로 프로세스를 분해하도록 finding을 낸다. 단, 개수 맞추기용 유사 프로세스 추가는 금지한다.",
            "주의:\n09_policies에서는 정책 항목을 추상 원칙으로 넓히지 말고, 연결된 프로세스와 기능이 실제 동작하기 위해 필요한 값·조건·횟수·시간·채널·저장 항목으로 고치도록 제안한다.",
        ]
    )
    return "\n\n".join(parts)


def normalized_inspection_mode_for_inspector(inspection_mode: str) -> str:
    value = str(inspection_mode or "chapter-final").strip().casefold().replace("_", "-")
    if value in {"final-only", "final"}:
        return "final-only"
    if value in {"none", "off", "skip"}:
        return "none"
    return "chapter-final"


def final_inspection_profile(inspection_mode: str, scope: str) -> dict:
    mode = normalized_inspection_mode_for_inspector(inspection_mode)
    is_final_scope = str(scope or "").strip() in {"full", "final", "10_final_check", "09_final"}
    if not is_final_scope:
        return {
            "mode": mode,
            "role": "stage_inspector",
            "focus": "현재 작성 범위의 JSON/HTML 정합성과 다음 장 인계 가능성",
            "gate_policy": "현재 장 기준",
        }
    if mode == "final-only":
        return {
            "mode": mode,
            "role": "comprehensive_final_inspector",
            "focus": (
                "장별 Inspector를 생략했으므로 개요, 용어, 액터, 유즈케이스, 상태, "
                "프로세스, 기능, 정책, 최종 점검을 모두 종합 검수"
            ),
            "chapter_assumption": "이전 장이 검수 통과됐다고 가정하지 않음",
            "finding_policy": "장별 품질 문제도 담당 Agent가 보완할 수 있도록 모두 finding으로 분배",
            "gate_policy": "score 기준, error 0건, quality gate blocker 0건",
        }
    if mode == "none":
        return {
            "mode": mode,
            "role": "disabled",
            "focus": "Inspector 비활성화",
            "gate_policy": "JSON Critical Gate만 적용",
        }
    return {
        "mode": mode,
        "role": "integration_final_inspector",
        "focus": (
            "장별 Inspector를 통과한 결과를 전제로, 전체 연결성, 후반 장 작성으로 인한 충돌, "
            "최종 HTML 렌더링, 샘플 수준, 제출 가능성을 통합 검수"
        ),
        "chapter_assumption": "각 장의 기본 품질은 이미 장별 Gate에서 1차 검수됐다고 봄",
        "finding_policy": "중복 세부 지적보다 cross-chapter 단절, 최종 산출물 리스크, 렌더링 문제를 우선 finding으로 작성",
        "gate_policy": "score 기준과 error 0건",
    }


def stage_inspector_profile(scope: str, chapter_key: str = "") -> dict:
    stage_key = inspector_stage_key(scope, chapter_key)
    profiles = {
        "overview": {
            "role": "Overview Inspector",
            "focus": "고객 과업 기준의 범위, 제외 범위, 설계 원칙, 후속 장 기준선",
            "must_verify": [
                "대상 업무·대상 고객·포함/제외 범위가 내부 시스템 기준이 아니라 고객 과업 기준인지",
                "설계 원칙이 4~6개 수준이며 기능·정책 판단에 연결 가능한지",
                "후속 액터·유즈케이스가 벗어나면 안 되는 경계가 드러나는지",
            ],
            "do_not_flag": [
                "후속 장에 아직 액터·유즈케이스·정책 상세가 없다는 이유",
                "샘플 간소화본 수준의 짧은 개요 분량",
            ],
            "pass_condition": "범위와 설계 원칙이 뒤 장의 작성 기준선으로 충분히 쓰일 수 있음",
        },
        "terms": {
            "role": "Terms Inspector",
            "focus": "상태·권한·인증·동의·보관·정책 판단값 용어의 해석 기준",
            "must_verify": [
                "일반 명사가 아니라 정책 판단이나 상태/권한 조건에 쓰이는 용어인지",
                "유사 용어 차이와 업무상 판단 기준이 설명에 포함됐는지",
                "후속 상태·정책에서 같은 개념을 다른 이름으로 중복 정의하지 않도록 기준이 되는지",
            ],
            "do_not_flag": [
                "상태성 용어가 용어 장에 먼저 정의되어 있다는 이유",
                "후속 상태 코드 목록이 아직 완성되지 않은 단계의 자연스러운 후보 용어",
            ],
            "pass_condition": "후속 장에서 용어 해석 충돌을 줄이는 판단 기준 역할을 함",
        },
        "actors": {
            "role": "Actor Inspector",
            "focus": "독립 책임 주체와 고객 상태/자격 조건의 분리",
            "must_verify": [
                "고객, 운영자, 법정대리인, 대리인, 핵심 시스템/기관 등 책임 주체만 액터인지",
                "로그인/비로그인/정상/제한/VIP 같은 상태·자격 차이가 액터로 분리되지 않았는지",
                "시스템 액터가 과도하게 쪼개지지 않고 책임 단위로 묶였는지",
            ],
            "do_not_flag": [
                "고객 액터 하나가 여러 고객 상태를 포괄하는 구조",
                "간소화본에서 BSS·연계 시스템을 통합 액터로 둔 구조",
            ],
            "pass_condition": "유즈케이스를 시작하거나 결과 책임을 만드는 주체 경계가 명확함",
        },
        "usecases": {
            "role": "Usecase Inspector",
            "focus": "액터가 완결해야 하는 상위 업무 목표와 프로세스 정의 대상 판단",
            "must_verify": [
                "유즈케이스가 약관 동의·인증·입력 같은 절차 단계가 아니라 고객/운영자의 상위 업무 목표인지",
                "사람 액터 유즈케이스는 process_target=Y, 시스템/기관 보조 처리는 원칙적으로 N인지",
                "후속 프로세스로 분해 가능한 완료 상태와 목적이 설명에 드러나는지",
            ],
            "do_not_flag": [
                "고객만 Y로 보지 말고 운영자·법정대리인·대리인 등 사람 액터 전체를 Y 후보로 보는 구조",
                "시스템 검증·조회가 보조 유즈케이스로 N 처리된 구조",
            ],
            "pass_condition": "유즈케이스가 후속 프로세스의 부모 업무 단위로 안정적으로 작동함",
        },
        "usecase_diagram": {
            "role": "Usecase Diagram Inspector",
            "focus": "액터-유즈케이스 관계의 시각적 정합성과 include 남용 방지",
            "must_verify": [
                "고객/운영자 중심 유즈케이스 관계가 한눈에 보이는지",
                "include 관계가 공통 처리에만 쓰이고 UI 단계나 버튼 클릭을 표현하지 않는지",
                "다이어그램이 actors/usecases 목록의 명칭과 충돌하지 않는지",
            ],
            "do_not_flag": [
                "HTML에서 텍스트 도식으로 표현한 간소화 다이어그램",
                "후속 프로세스 상세가 아직 없는 단계",
            ],
            "pass_condition": "액터와 유즈케이스 연결이 목록과 일치하고 UI 절차로 흐르지 않음",
        },
        "state": {
            "role": "State Inspector",
            "focus": "액터-유즈케이스 기반 상태 도출과 업무 사건형 전이 이벤트",
            "must_verify": [
                "상태 후보가 용어가 아니라 액터-유즈케이스 관계와 업무 가능 여부에서 도출됐는지",
                "전이 이벤트가 연결된 유즈케이스 흐름에서 발생한 업무 사건이며, 추적성은 usecase_ids로 보존되는지",
                "현재 상태/다음 상태가 상태 목록에 있고 예외·제한·보류 분기의 우선순위 또는 배타 조건이 있는지",
            ],
            "do_not_flag": [
                "상태 장에서 이전 용어/유즈케이스를 임의로 새로 만들지 않고 현재 장 안에서 정렬하는 구조",
                "시간 경과나 실패 사유가 event가 아니라 criteria에 배치된 구조",
            ],
            "pass_condition": "상태 코드와 전이표가 후속 프로세스의 조건 분기 기준으로 바로 쓰일 수 있음",
        },
        "process": {
            "role": "Process Inspector",
            "focus": "사람 액터 Y 유즈케이스를 완료하는 업무 절차 분해",
            "must_verify": [
                "유즈케이스 1개가 프로세스 1개로만 끝나지 않고 시작·입력/선택·인증/동의·검증·요청/반영·결과 안내 등으로 분해됐는지",
                "프로세스가 기능명 나열이 아니라 고객/운영자가 경험하는 업무 전환점인지",
                "상태 전이와 예외/제한 흐름을 프로세스 조건으로 이어받았는지",
            ],
            "do_not_flag": [
                "작성 순서상 related_functions, related_policies가 비어 있는 상태",
                "시스템 내부 조회·저장·판정을 별도 프로세스로 과도하게 분리하지 않은 구조",
            ],
            "pass_condition": "후속 기능 장이 각 프로세스를 수행 역량으로 분해할 수 있는 절차 수준임",
        },
        "functions": {
            "role": "Function Inspector",
            "focus": "프로세스를 수행하는 처리 역량과 세부 기능 구성의 입자도",
            "must_verify": [
                "기능이 프로세스명을 그대로 복사하지 않고 조회·검증·산정·저장·알림·연동 같은 처리 역량으로 묶였는지",
                "모든 프로세스에 기능 1개씩만 붙는 1:1 구조가 아닌지",
                "세부 기능 구성이 정책 항목이나 프로세스 단계명이 아니라 기능의 짧은 하위 처리명인지",
            ],
            "do_not_flag": [
                "공통 기능 ID가 여러 process_ids에 재사용된 구조",
                "정책값을 기능 설명에 길게 쓰지 않고 정책 장으로 넘긴 구조",
            ],
            "pass_condition": "프로세스 수행에 필요한 기능과 하위 처리가 정책값 없이도 이해됨",
        },
        "process_detail": {
            "role": "Process Detail Inspector",
            "focus": "Full 버전 프로세스 상세의 절차·예외·연결 보강",
            "must_verify": [
                "프로세스 상세가 기존 프로세스 ID를 유지하며 단계, 조건, 예외, 후속 처리를 보강하는지",
                "기능·정책과 연결되는 판단 지점이 드러나는지",
                "화면 UI 상세나 API/DB 필드로 과도하게 내려가지 않는지",
            ],
            "do_not_flag": [
                "간소화본 프로세스 목록과 일부 설명이 중복되는 구조",
                "세부 설계 수준의 필드/화면 정의를 제외한 구조",
            ],
            "pass_condition": "상세 설계자가 절차와 예외 흐름을 이해할 수 있는 수준으로 보강됨",
        },
        "function_detail": {
            "role": "Function Detail Inspector",
            "focus": "Full 버전 기능 상세와 세부 기능 구성의 구현 가능성",
            "must_verify": [
                "기능 상세가 기능 ID를 유지하며 하위 처리, 입력 판단, 결과 산출, 예외 처리를 보강하는지",
                "세부 기능 구성이 기능의 하위 처리이지 정책 항목/프로세스 단계의 복사본이 아닌지",
                "관련 정책과 기능 설명의 책임이 섞이지 않는지",
            ],
            "do_not_flag": [
                "API 필드·DB 컬럼을 의도적으로 제외한 구조",
                "정책값 자체를 정책 장에 남겨둔 구조",
            ],
            "pass_condition": "개발자가 기능의 처리 책임과 정책 참조 지점을 구분할 수 있음",
        },
        "policies": {
            "role": "Policy Inspector",
            "focus": "프로세스/기능 동작에 필요한 정책 그룹, 정책 항목, 항목별 값",
            "must_verify": [
                "정책 그룹이 프로세스와 기능의 통제 지점에서 도출됐는지",
                "정책 상세가 인증 수단, 가능 횟수, 유효시간, 제한 조건, 노출 채널, 저장 항목 같은 실제 값/조건을 갖는지",
                "정책 목록의 정책 항목과 정책 상세가 1:N으로 추적 가능한지",
            ],
            "do_not_flag": [
                "정책이 일반 보안/운영 원칙으로 확장되지 않고 해당 주제의 기능 동작값으로 제한된 구조",
                "정책 상세가 process에 직접 매핑되지 않고 policy_group 기준으로 관리되는 구조",
            ],
            "pass_condition": "상세 설계/개발/QA가 정책 항목별 값을 기준으로 구현·테스트할 수 있음",
        },
        "terms_refinement": {
            "role": "Terms Refinement Inspector",
            "focus": "정책 작성 후 용어 일관성, 중복 용어, 상태/정책명 충돌 정리",
            "must_verify": [
                "정책과 기능에서 쓰인 핵심 용어가 주요 용어와 충돌하지 않는지",
                "같은 개념이 여러 이름으로 남아 있지 않은지",
                "용어 보완이 기존 ID와 연결성을 깨지 않는지",
            ],
            "do_not_flag": [
                "정책 장에서만 쓰이는 세부 정책값을 모두 용어로 끌어올리지 않은 구조",
            ],
            "pass_condition": "문서 전체 용어가 같은 의미로 유지됨",
        },
        "final_check": {
            "role": "Final Check Chapter Inspector",
            "focus": "최종 점검 기준이 주제별 제출 Gate로 작동하는지",
            "must_verify": [
                "범위 정합성, 고객 완결성, BSS/연계 포함성, 상태 전이, 프로세스-기능-정책 연결성, 정책 구체성이 점검 항목에 포함됐는지",
                "주제와 무관한 일반 체크리스트로만 흐르지 않는지",
                "미해결 이슈와 요구사항 반영 확인 기준이 제출 전 판단에 쓰일 수 있는지",
            ],
            "do_not_flag": [
                "사용자가 요청하지 않은 별도 점검 결과 장을 추가하지 않은 구조",
            ],
            "pass_condition": "최종 제출 전 사람이 확인할 수 있는 주제 맞춤 Gate로 충분함",
        },
    }
    return profiles.get(
        stage_key,
        {
            "role": "Stage Inspector",
            "focus": "현재 작성 범위의 구조, 연결성, 정책 구체성",
            "must_verify": ["현재 장 산출물이 이전 승인 기준과 충돌하지 않는지", "후속 장으로 넘길 기준이 충분한지"],
            "do_not_flag": ["아직 작성 순서가 오지 않은 미래 장의 누락"],
            "pass_condition": "현재 장이 다음 작성 단계의 기준선으로 사용할 수 있음",
        },
    )


def stage_inspector_profile_instruction(profile: Mapping[str, object]) -> str:
    return (
        "[Stage Inspector 전문 프로파일]\n"
        "아래 프로파일은 현재 장의 전문 검수 역할이다. finding은 이 프로파일의 focus, must_verify, "
        "do_not_flag, pass_condition을 기준으로 판단한다.\n"
        + json.dumps(profile, ensure_ascii=False)
    )


def final_inspection_role_instruction(inspection_mode: str, scope: str) -> str:
    profile = final_inspection_profile(inspection_mode, scope)
    role = profile.get("role", "")
    if role == "comprehensive_final_inspector":
        return (
            "Final Inspector 역할: 이번 실행은 최종 검수만 모드다. 장별 Inspector가 생략됐으므로 "
            "각 장이 이미 통과됐다고 가정하지 말고, 장별 품질 문제와 챕터 간 정합성 문제를 모두 찾는다. "
            "finding은 반드시 담당 장 Agent가 보완할 수 있도록 target_path와 fix_owner를 구체화한다."
        )
    if role == "integration_final_inspector":
        return (
            "Final Inspector 역할: 이번 실행은 장별 검수 후 최종 통합 검수 모드다. "
            "장별 Gate에서 이미 본 고립된 세부 문체 문제를 반복하기보다, 전체 연결성, 후속 장 작성으로 생긴 충돌, "
            "최종 HTML 렌더링, 샘플 수준, 제출 가능성을 우선 검수한다."
        )
    return "Inspector 역할: 현재 작성 범위의 구조와 연결성을 검수한다."


def inspection_scope_guard_instruction(inspection_mode: str, scope: str) -> str:
    profile = final_inspection_profile(inspection_mode, scope)
    role = profile.get("role", "")
    base = (
        "검수 범위 제한: 현재 작성 범위, Authoring Blueprint가 정의한 범위, 첨부 요구사항, 사용자 작성 요청 메모 안에서만 finding을 생성한다. "
        "범위 밖 일반 보안 정책, 범위 밖 일반 운영 모니터링, 주제와 무관한 UX 일반론, 첨부 근거 없는 공개웹 추정 요구사항은 finding으로 만들지 않는다. "
        "다만 첨부 요구사항, 사용자 피드백, AGENTS.md, 샘플/템플릿 기준에 명시된 보안·운영·고지·이력 항목은 범위 안 finding으로 본다. "
        "범위가 애매한 항목은 감점 finding으로 단정하지 말고 summary에서 관찰 메모로만 언급한다."
    )
    if role == "comprehensive_final_inspector":
        return base + " 최종 검수만 모드에서는 모든 장을 볼 수 있지만, 그래도 정책서가 정의해야 할 업무 구조·판단값·연결성 범위를 넘는 일반론은 차단한다."
    if role == "integration_final_inspector":
        return base + " 장별 검수 후 최종 모드에서는 장별 세부 표현보다 후속 장 작성으로 생긴 cross-chapter 단절과 제출 리스크만 finding으로 둔다."
    return base + " 장별 검수에서는 미래 장에서 작성할 내용 부족을 현재 장 finding으로 만들지 않는다."


def final_inspection_prompt_rule(inspection_mode: str, scope: str) -> str:
    profile = final_inspection_profile(inspection_mode, scope)
    role = profile.get("role", "")
    if role == "comprehensive_final_inspector":
        return (
            "모드별 검수 지침:\n"
            "- final-only 모드이므로 장별 Inspector가 잡았어야 할 문제도 최종에서 발견해야 한다.\n"
            "- 개요/용어/액터/유즈케이스/상태/프로세스/기능/정책/최종점검 각각의 품질 문제를 필요한 만큼 finding으로 작성한다.\n"
            "- 단순 스타일보다 구조 정합성, 정책 구체성, 요구사항/근거 반영, 상태-프로세스-기능-정책 연결을 우선한다.\n"
            "- finding은 담당 Agent로 되돌아가므로 recommendation에 수정 대상 장과 최소 수정 방향을 명확히 쓴다."
        )
    if role == "integration_final_inspector":
        return (
            "모드별 검수 지침:\n"
            "- chapter-final 모드이므로 장별 품질은 이미 1차 검수됐다고 보고, 최종 통합 리스크에 집중한다.\n"
            "- 유즈케이스→상태→프로세스→기능→정책 chain 단절, 정책 상세와 프로세스 연결 불일치, 최종 HTML 렌더링 문제를 우선 찾는다.\n"
            "- 장별 Inspector가 이미 처리했을 법한 고립된 표현 문제는 전체 제출 리스크가 있을 때만 finding으로 둔다.\n"
            "- 후반 장 작성 후 앞 장과 충돌한 경우에는 cross_chapter 또는 upstream_chapter를 명확히 지정한다."
        )
    return "모드별 검수 지침:\n- 현재 범위의 실질 문제를 finding으로 작성한다."


def llm_json_inspection_instructions(topic: str, template_type: str, scope: str, brief: str = "") -> str:
    base = llm_inspection_instructions(topic, template_type, scope, brief)
    profile = stage_inspector_profile(scope)
    return base + "\n" + "\n".join(
        [
            "이번 검수 입력은 HTML이 아니라 정책서 JSON이다.",
            "JSON Stage Inspector도 Stage Inspector 전문 프로파일을 따른다. HTML 표현이 아니라 current_chapter JSON 필드가 프로파일의 pass_condition을 만족하는지 본다.",
            "JSON Stage Inspector 전문 프로파일:\n" + json.dumps(profile, ensure_ascii=False),
            "렌더링, CSS, 표 깨짐, <br/> 같은 HTML 형식 문제는 장별 findings로 만들지 않는다. HTML 형식은 최종 HTML Inspector가 별도로 검수한다.",
            "JSON 필드의 ID, 참조 관계, 이번 장 내용의 완결성, 정책 동작값의 구체성만 검수한다.",
            "검수 범위는 현재 장 JSON, approved_contract, support_context.must_cover, support_context.architecture_contract, 첨부 요구사항/사용자 메모로 한정한다. 범위 밖 일반론은 finding으로 만들지 않는다.",
            "support_context.topic_evidence_map에는 참고자료 DB에서 선별한 현재 장 근거 카드가 있다. 이 근거와 어긋난 일반론, 누락된 판단축, 근거 없는 확정 표현을 의미 검수 대상으로 본다.",
            "support_context.policy_detail_style_anchor는 예전 프로젝트 문서에서 추출한 정책 상세화 방식이다. 정책 사실이 아니라 유형·가능/불가·권한·시점·상태·사용 여부·자동/수동 조정·고지·이력 같은 판단축 누락을 확인하는 데만 사용한다.",
            "support_context.pi_agent_context는 PI Playbook 기반 독립 검수 관점이다. As-Is 복사, 중복 단계, 현업 받아쓰기, AI 끼워넣기, 예외 각주화, KPI 부재를 현재 장 범위 안에서만 확인하고, 정책서 템플릿을 PI 산출물 양식으로 바꾸라고 요구하지 않는다.",
            "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다. 하위 순위 근거가 상위 근거와 상충하면 하위 근거를 인정하지 말고 보완 finding으로 지적한다.",
            "support_context.prelearned_knowledge의 후보는 정답이 아니라 참고 후보이다. 후보가 현재 장의 요구사항, 첨부 참고자료, 승인된 유즈케이스·프로세스·기능·정책 연결 없이 그대로 들어오면 일반론 또는 범위 확장 finding으로 지적한다.",
            "반대로 prelearned_knowledge의 후보가 현재 주제 요구사항, 첨부 근거, 또는 승인된 계층 연결과 맞고 첨부 문서와 상충하지 않으면 공개웹/사전학습 출처라는 이유만으로 오류 처리하지 않는다.",
            "prelearned_knowledge.candidate_validation의 allowed_when과 reject_when을 기준으로 정상 후보 채택과 후보 오남용을 구분한다.",
            "support_context.analysis_method_guard는 전문 분석 기준의 적용 한계다. 방법론상 더 정교한 양식이 있더라도 NC 템플릿/샘플의 표 구조와 간결성을 벗어나게 지적하지 않는다.",
            "state 장 검수에서는 모든 사건 조합의 전이 행을 요구하지 않는다. 고객 주 흐름이 막히거나 next_action이 약속한 경로가 없을 때만 finding으로 만들고, 같은 후속 조치로 처리 가능한 예외는 description/criteria 축소를 우선 권고한다.",
            "finding은 tier, is_quality_gate, target_path, fix_owner, upstream_chapter를 반드시 채운다. P1은 참조 무결성·필수 슬롯·Gate 위반, P2는 정합성·구체성 부족, P3는 표현·문체 문제다.",
            "patch-only 보완을 전제로 finding을 작성한다. root_cause, required_change, patch_hint, acceptance_check, keep_constraints, do_not_change를 비우지 않는다.",
            "target_path가 비어 있으면 Writer가 전체 장을 다시 쓸 위험이 있다. 배열 항목은 current_chapter.processes[2].description처럼 index와 필드를 포함해 최대한 정확히 지정한다.",
            "target_path, root_cause, required_change, patch_hint, acceptance_check를 모두 구체적으로 쓸 수 없는 문제는 JSON finding으로 만들지 않는다. 불명확한 일반론 finding은 Writer 보완 품질을 떨어뜨린다.",
            "각 JSON finding은 '변경', '추가', '삭제' 중 어느 조치인지 recommendation 또는 required_change에서 명확히 구분되어야 한다.",
            "required_change는 '무엇을 추가/삭제/변경'인지, patch_hint는 '어떤 표현이나 조건으로 바꿀지', acceptance_check는 '어떤 기준이면 해결로 볼지'를 각각 다르게 쓴다.",
            "fix_owner 판단 기준: 현재 장 설명이나 연결값만 고치면 해결되는 문제는 current_chapter다. 이전 장에 필요한 액터·유즈케이스·상태·용어가 없어 현재 장이 억지로 새 기준을 만든 경우만 upstream_chapter다.",
            "upstream_chapter가 아니면 upstream_chapter는 빈 문자열로 둔다.",
        ]
    )


def llm_json_inspection_prompt(
    *,
    spec: Mapping[str, object],
    deterministic_findings: Sequence[InspectionFinding],
    metrics: dict,
    template_type: str,
    scope: str,
    topic: str,
    brief: str = "",
    chapter_key: str = "",
) -> str:
    local_precheck = json_local_precheck(spec, scope)
    metrics["local_precheck"] = local_precheck_metrics(local_precheck)
    is_stage_scope = 0 < scope_rank(scope) < 10
    approved_contract = json_approved_contract(spec, scope)
    current_chapter = json_current_chapter_pack(spec, scope, chapter_key=chapter_key)
    support_context = json_inspector_support_context(spec, scope, chapter_key)
    if is_stage_scope:
        approved_contract = compact_stage_inspector_value(
            approved_contract,
            max_string=90,
            max_list=24,
            max_dict_keys=10,
        )
        support_context = compact_stage_inspector_value(
            support_context,
            max_string=140,
            max_list=6,
            max_dict_keys=12,
        )
    else:
        support_context = compact_stage_inspector_value(
            support_context,
            max_string=180,
            max_list=12,
            max_dict_keys=14,
        )
    inspection_pack = {
        "metrics": compact_json_metrics(metrics),
        "local_precheck": compact_local_precheck_for_llm(local_precheck, scope),
        "rule_findings": compact_findings_for_llm(
            deterministic_findings,
            limit=50 if scope_rank(scope) >= 10 else 35,
        ),
        "approved_contract": approved_contract,
        "current_chapter": current_chapter,
        "support_context": support_context,
        "stage_inspector_profile": stage_inspector_profile(scope, chapter_key),
    }
    parts = [
        f"정책서 주제: {topic or '-'}",
        f"템플릿 유형: {template_type}",
        f"검수 범위: {scope}",
        f"사용자 작성 요청 메모: {brief.strip() if str(brief or '').strip() else '-'}",
        "JSON 검수 팩:\n" + json.dumps(inspection_pack, ensure_ascii=False, indent=2),
        (
            "검수 요청:\n"
            "HTML이 아니라 JSON 내용만 기준으로 검수한다. 이전 장은 approved_contract로 통과된 기준선이며, "
            "이번 장 JSON이 그 기준선을 정확히 이어받았는지 확인한다. "
            "stage_inspector_profile은 현재 장 전용 전문 검수 기준이므로, generic 검사보다 우선 적용한다. "
            "단, Blueprint Quality Gate가 지적한 위험은 그대로 믿지 말고 현재 JSON에 실제 결함으로 남았는지 확인한다. "
            "support_context.topic_evidence_map의 장별 근거 카드와 판단축을 기준으로, 원천 근거가 있는데도 빠진 내용과 근거 없이 일반화된 내용을 구분한다. "
            "하위 순위 근거와 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF가 충돌하는 경우에는 1순위 근거 기준으로 수정하도록 finding을 낸다. "
            "사전 Knowledge Pack 후보가 현재 주제의 요구사항·첨부 참고자료·계층 연결 없이 복사된 경우에는 삭제 또는 현재 장에 맞는 축소 수정을 요구한다. "
            "단, 사전 Knowledge Pack 후보가 현재 주제 요구사항·첨부 근거·승인된 계층 연결 중 하나 이상과 맞고 첨부 문서와 상충하지 않으면, 지식 기반 작성 자체를 오류로 보지 않는다. "
            "ID 형식, 참조 무결성, 단순 누락은 local_precheck와 rule_findings에 이미 계산되어 있으므로 반복 나열하지 말고, "
            "의미 정합성, 정책 동작값의 구체성, 책임 경계, 누락 가능성이 높은 판단 기준을 중심으로 검수한다."
        ),
        (
            "계층 검수 기준:\n"
            "유즈케이스는 상위 업무 목표, 프로세스는 그 목표를 완료하는 업무 절차, 기능은 프로세스를 수행하는 처리 역량, "
            "세부 기능 구성은 기능 아래의 짧은 하위 처리명, 정책은 기능 동작에 필요한 값·조건·허용 범위다. "
            "이번 장이 이 계층을 건너뛰거나 같은 입자를 다른 장에서 반복하면 finding으로 둔다."
        ),
        (
            "04_usecases 추가 기준:\n"
            "현재 범위가 유즈케이스 장이면 유즈케이스가 뒤에서 여러 프로세스로 분해 가능한 업무 목표인지 확인한다. "
            "약관 동의, 본인인증, 정보 입력, 조회, 검증, 저장, 알림처럼 절차나 기능에 가까운 행위가 독립 유즈케이스로 올라오면 current_chapter finding으로 둔다. "
            "다만 작성 주제의 핵심 업무가 인증·연동 권한 확정이면 '인증' 단어만으로 절차형 유즈케이스라고 판단하지 말고, 본인확인·인증번호 입력·인증 결과 확인처럼 하위 절차로 쪼개진 경우만 지적한다."
        ),
        (
            "03_actors 추가 기준:\n"
            "채널 업무 시스템은 요청 전달, 결과 표시, 상태·이력 기록을 담당하는 대상 채널 내부 처리 액터로 정의될 수 있다. "
            "따라서 채널 업무 시스템이 있다는 사실만 finding으로 두지 말고, BSS/인증기관/연계 시스템이 맡아야 할 최종 자격·가능 여부·원장 반영 판정을 채널 업무 시스템이 단독 수행하는 경우에만 책임 경계 finding으로 둔다."
        ),
        (
            "07_process 추가 기준:\n"
            "현재 범위가 프로세스 장이면 process_target=Y 유즈케이스가 충분한 업무 절차로 분해됐는지 확인한다. "
            "프로세스가 기능명 나열처럼 작성됐거나 유즈케이스 1개가 프로세스 1개로만 끝나면 current_chapter finding으로 둔다."
        ),
        (
            "08_functions 추가 기준:\n"
            "현재 범위가 기능 장이면 기능이 프로세스명을 복사하지 않고 조회·검증·산정·저장·알림·연동 같은 처리 역량으로 묶였는지 확인한다. "
            "details는 짧은 하위 처리명이어야 하며, 모든 프로세스가 기능 1개씩만 갖는 1:1 구조는 품질 결함으로 둔다."
        ),
        (
            "09_policies 추가 기준:\n"
            "현재 범위가 정책 장이면 정책 그룹이 프로세스와 기능의 필요 통제 지점에서 도출됐는지 확인한다. "
            "정책 상세는 정책을 구성하는 세부 항목과 각 항목별 값·조건·횟수·시간·채널·저장 항목을 선언해야 한다. "
            "정책 상세가 기능 설명, 처리 절차, 추상 원칙으로 작성됐으면 current_chapter finding으로 둔다."
        ),
        (
            "10_final_check 추가 기준:\n"
            "현재 범위가 최종 점검이면 유즈케이스 → 프로세스 → 기능 → 세부 기능 구성 → 정책값의 계층 정합성, "
            "프로세스-기능 입자도, 기능-정책 연결성을 제출 전 점검 항목으로 포함했는지 확인한다."
        ),
        (
            "06_state 추가 기준:\n"
            "현재 범위가 상태 장이면 states.description의 원인 범위, state_transitions.criteria의 도달 조건, "
            "같은 현재 상태에서 갈라지는 예외 분기의 우선순위, 판정 주체가 이전 장의 액터·유즈케이스 책임과 맞는지 중점 점검한다. "
            "상태 장 recommendation은 '수정대상 / 수정방식 / 유지조건 / 검증조건'을 포함해 Writer가 한 번에 보완할 수 있게 작성한다."
        ),
        (
            "피드백 기준:\n"
            "finding은 원칙적으로 이번 장에서 수정 가능한 항목을 작성한다. 단, 이번 장에서 정상적으로 보완할 수 없고 이전 장의 승인 계약 자체가 누락·오류인 경우에는 fix_owner=upstream_chapter 또는 cross_chapter로 작성한다. recommendation은 이번 장 또는 지정한 upstream 장의 ID, 명칭, 설명, 연결 필드, "
            "정책 항목 중 무엇을 어떻게 바꿀지 구체적으로 쓴다. upstream finding도 현재 장에서 재정렬해야 할 기준을 함께 적는다. "
            "Writer가 전체 장을 다시 쓰지 않도록 target_path, required_change, patch_hint, acceptance_check, keep_constraints, do_not_change를 구체적으로 채운다."
        ),
        (
            "제외 기준:\n"
            "CSS, HTML 구조, 줄바꿈, 표 렌더링 문제는 지적하지 않는다. 아직 작성 전인 후속 장 누락도 감점하지 않는다."
        ),
    ]
    return "\n\n".join(parts)


def compact_stage_inspector_value(
    value: object,
    *,
    max_string: int,
    max_list: int,
    max_dict_keys: int,
    depth: int = 0,
) -> object:
    """Keep Stage Inspector LLM input focused on the current chapter contract.

    Full/final inspection still receives the broader pack. For chapter gates we
    only need enough prior context to check continuity, otherwise the inspector
    spends tokens rereading unrelated evidence and tends to over-find.
    """
    if depth > 4:
        return limit_text(str(value), max_string)
    if isinstance(value, str):
        return limit_text(value, max_string)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        result: dict = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_dict_keys:
                result["_truncated_keys"] = max(0, len(value) - max_dict_keys)
                break
            result[str(key)] = compact_stage_inspector_value(
                item,
                max_string=max_string,
                max_list=max_list,
                max_dict_keys=max_dict_keys,
                depth=depth + 1,
            )
        return result
    if isinstance(value, list):
        compacted = [
            compact_stage_inspector_value(
                item,
                max_string=max_string,
                max_list=max_list,
                max_dict_keys=max_dict_keys,
                depth=depth + 1,
            )
            for item in value[:max_list]
        ]
        if len(value) > max_list:
            compacted.append({"_truncated_items": len(value) - max_list})
        return compacted
    return limit_text(str(value), max_string)


def llm_inspection_context(
    body: str,
    text: str,
    scope: str,
    deterministic_findings: Sequence[InspectionFinding] = (),
) -> dict:
    has_findings = bool(deterministic_findings)
    html_limit = inspection_html_limit(scope)
    if not has_findings:
        rank = scope_rank(scope)
        html_limit = min(html_limit, 1200 if rank >= 9 else 0)
    else:
        html_limit = min(html_limit, 1800)
    return {
        "summary": {
            "headings": heading_outline(body),
            "connections": connection_summary(body, scope),
        },
        "section_excerpts": section_excerpts_for_scope(text, scope),
        "focused_html": limit_text(focused_html_for_scope(body, scope), html_limit) if html_limit else "",
    }


def compact_inspection_metrics(metrics: Mapping[str, object]) -> dict:
    keys = (
        "body_bytes",
        "text_chars",
        "h2_count",
        "h3_count",
        "table_count",
        "policy_group_count",
        "policy_item_count",
        "state_count",
        "process_count",
        "function_count",
        "business_codes",
        "sample_topic_match_count",
        "sample_reference_mode",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def heading_outline(body: str) -> List[dict]:
    headings = []
    for match in re.finditer(r"<h([234])\b[^>]*>(.*?)</h\1>", body, flags=re.DOTALL | re.IGNORECASE):
        headings.append(
            {
                "level": int(match.group(1)),
                "text": limit_text(visible_text(match.group(2)), 100),
            }
        )
    return headings[:80]


def connection_summary(body: str, scope: str = "full") -> dict:
    rank = scope_rank(scope)
    process_rows = extract_process_rows(body)
    summary = {
        "actors": compact_rows(table_rows_with_prefix(body, "ACT-"), 12),
        "usecases": compact_rows(table_rows_with_prefix(body, "US-"), 24),
        "states": compact_rows(table_rows_with_prefix(body, "ST-"), 16),
    }
    if rank >= 7:
        summary["processes"] = [
            {
                "id": item.get("id", ""),
                "usecase_id": item.get("usecase_id", ""),
                "name": item.get("name", ""),
                "related_functions": item.get("related_functions", [])[:5],
                "related_policies": item.get("related_policies", [])[:5],
            }
            for item in process_rows[:35]
        ]
    if rank >= 8:
        summary["functions"] = compact_rows_by_first_cell(table_rows_with_prefix(body, "FN-"), 35)
    if rank >= 9:
        summary["policy_groups"] = compact_rows_by_first_cell(table_rows_with_prefix(body, "PG-"), 30)
        summary["policy_item_ids"] = dedupe(re.findall(r"PI-[A-Z0-9]+(?:-[A-Z0-9]+)+", body))[:60]
    return summary


def compact_rows(rows: Sequence[dict], limit: int, cell_limit: int = 90) -> List[List[str]]:
    result: List[List[str]] = []
    for row in rows[:limit]:
        result.append([limit_text(cell, cell_limit) for cell in row.get("texts", [])[:6]])
    return result


def compact_rows_by_first_cell(rows: Sequence[dict], limit: int, cell_limit: int = 90) -> List[List[str]]:
    """Compact table rows while hiding renderer grouping duplicates from the LLM inspector."""
    unique_rows: List[dict] = []
    seen: set[str] = set()
    for row in rows:
        cells = row.get("texts", [])
        first_cell = str(cells[0] if cells else "").strip()
        if first_cell and first_cell in seen:
            continue
        if first_cell:
            seen.add(first_cell)
        unique_rows.append(row)
    return compact_rows(unique_rows, limit, cell_limit)


def section_excerpts_for_scope(text: str, scope: str) -> List[dict]:
    """Return chapter-level excerpts so the LLM inspector can avoid full HTML input."""
    rank = scope_rank(scope)
    candidates = [
        ("overview", 1, "1. 개요", "2. 주요 용어", 1400),
        ("terms", 2, "2. 주요 용어", "3. 유즈케이스 정의", 900),
        ("usecases", 4, "3. 유즈케이스 정의", "4. 프로세스 정의", 1800),
        ("process", 7, "4. 프로세스 정의", "5. 기능 정의", 1800),
        ("functions", 8, "5. 기능 정의", "6. 정책 정의", 1600),
        ("policies", 9, "6. 정책 정의", "최종 점검 기준", 2200),
        ("final_check", 10, "최종 점검 기준", "", 900),
    ]
    excerpts: List[dict] = []
    for section, required_rank, start, end, limit in candidates:
        if rank < required_rank:
            continue
        content = extract_text_section(text, start, end)
        if content:
            excerpts.append({"section": section, "excerpt": limit_text(content, limit)})
    if not excerpts:
        excerpts.append({"section": "document", "excerpt": limit_text(text, 2500)})
    return excerpts


def focused_text_for_scope(text: str, scope: str) -> str:
    rank = scope_rank(scope)
    if rank <= 1:
        return extract_text_section(text, "1. 개요", "2. 주요 용어") or text[:12000]
    if rank <= 2:
        return extract_text_section(text, "1. 개요", "3. 유즈케이스 정의") or text[:14000]
    if rank <= 6:
        return extract_text_section(text, "1. 개요", "4. 프로세스 정의") or text[:18000]
    if rank == 7:
        return extract_text_section(text, "1. 개요", "5. 기능 정의") or text[:22000]
    if rank == 8:
        return extract_text_section(text, "1. 개요", "6. 정책 정의") or text[:24000]
    return text


def focused_html_for_scope(body: str, scope: str) -> str:
    rank = scope_rank(scope)
    if rank <= 1:
        return extract_html_between(body, "1. 개요", "2. 주요 용어") or body[:10000]
    if rank <= 2:
        return extract_html_between(body, "1. 개요", "3. 유즈케이스 정의") or body[:12000]
    if rank <= 6:
        return extract_html_between(body, "3. 유즈케이스 정의", "4. 프로세스 정의") or body[:16000]
    if rank == 7:
        return extract_html_between(body, "4. 프로세스 정의", "5. 기능 정의") or body[:18000]
    if rank == 8:
        return extract_html_between(body, "5. 기능 정의", "6. 정책 정의") or body[:18000]
    if rank == 9:
        return extract_html_between(body, "6. 정책 정의", "최종 점검 기준") or body[-22000:]
    return body


def inspection_text_limit(scope: str) -> int:
    rank = scope_rank(scope)
    if rank <= 2:
        return 3500
    if rank <= 6:
        return 5500
    if rank <= 8:
        return 7000
    return 9000


def inspection_html_limit(scope: str) -> int:
    rank = scope_rank(scope)
    if rank <= 2:
        return 2500
    if rank <= 6:
        return 4200
    if rank <= 8:
        return 5200
    return 7000


def llm_inspection_schema() -> dict:
    return json_object_schema(
        {
            "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
            "summary": {"type": "string"},
            "findings": json_array_schema(
                json_object_schema(
                    {
                        "finding_id": {"type": "string"},
                        "tier": {"type": "string", "enum": ["P1", "P2", "P3"]},
                        "severity": {"type": "string", "enum": ["error", "warn"]},
                        "category": {"type": "string"},
                        "is_quality_gate": {"type": "boolean"},
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "target_path": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "required_change": {"type": "string"},
                        "patch_hint": {"type": "string"},
                        "acceptance_check": {"type": "string"},
                        "keep_constraints": {"type": "string"},
                        "do_not_change": {"type": "string"},
                        "fix_owner": {
                            "type": "string",
                            "enum": ["current_chapter", "upstream_chapter", "cross_chapter", "defer_to_later"],
                        },
                        "upstream_chapter": {"type": "string"},
                    }
                )
            ),
        }
    )


def llm_findings(payload: Mapping[str, Any]) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    raw_findings = payload.get("findings", [])
    if not isinstance(raw_findings, list):
        return findings
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "warn")).strip()
        if severity not in {"error", "warn"}:
            severity = "warn"
        findings.append(
            InspectionFinding(
                severity=severity,
                category=str(item.get("category", "LLM 검수")).strip() or "LLM 검수",
                title=str(item.get("title", "LLM inspector 발견사항")).strip() or "LLM inspector 발견사항",
                detail=str(item.get("detail", "")).strip(),
                recommendation=str(item.get("recommendation", "")).strip(),
                finding_id=str(item.get("finding_id", "")).strip(),
                tier=str(item.get("tier", "")).strip(),
                is_quality_gate=bool(item.get("is_quality_gate", False)),
                target_path=str(item.get("target_path", "")).strip(),
                fix_owner=normalize_fix_owner(item.get("fix_owner")),
                upstream_chapter=str(item.get("upstream_chapter", "")).strip(),
                root_cause=str(item.get("root_cause", "")).strip(),
                required_change=str(item.get("required_change", "")).strip(),
                patch_hint=str(item.get("patch_hint", "")).strip(),
                acceptance_check=str(item.get("acceptance_check", "")).strip(),
                keep_constraints=str(item.get("keep_constraints", "")).strip(),
                do_not_change=str(item.get("do_not_change", "")).strip(),
            )
        )
    return findings


def normalize_fix_owner(value: object) -> str:
    owner = str(value or "").strip()
    return owner if owner in {"current_chapter", "upstream_chapter", "cross_chapter", "defer_to_later"} else "current_chapter"


GENERIC_FINDING_PHRASES = (
    "구체화 필요",
    "보완 필요",
    "검토 필요",
    "명확히 작성",
    "정합성 확보",
    "개선 필요",
    "추가 필요",
)


def finding_actionability_issues(finding: InspectionFinding) -> List[str]:
    """Return missing pieces that would make a Writer patch ambiguous."""

    issues: List[str] = []
    owner = normalize_fix_owner(getattr(finding, "fix_owner", "current_chapter"))
    target_path = str(getattr(finding, "target_path", "") or "").strip()
    upstream_chapter = str(getattr(finding, "upstream_chapter", "") or "").strip()

    if owner in {"current_chapter", "cross_chapter"} and not target_path:
        issues.append("target_path 누락")
    if owner == "upstream_chapter" and not upstream_chapter:
        issues.append("upstream_chapter 누락")

    required_fields = (
        ("root_cause", "원인"),
        ("required_change", "필수 변경"),
        ("patch_hint", "패치 힌트"),
        ("acceptance_check", "통과 기준"),
    )
    for field_name, label in required_fields:
        if not str(getattr(finding, field_name, "") or "").strip():
            issues.append(f"{label} 누락")

    recommendation = str(getattr(finding, "recommendation", "") or "").strip()
    required_change = str(getattr(finding, "required_change", "") or "").strip()
    patch_hint = str(getattr(finding, "patch_hint", "") or "").strip()
    if recommendation in GENERIC_FINDING_PHRASES and not required_change and not patch_hint:
        issues.append("일반론 recommendation")
    if recommendation and len(recommendation) < 12 and not required_change:
        issues.append("수정 방향 과소 명시")
    return issues


def filter_llm_findings_for_scope(findings: Sequence[InspectionFinding], scope: str) -> List[InspectionFinding]:
    rank = scope_rank(scope)
    if rank <= 0:
        return list(findings)
    if rank in {7, 8}:
        result: List[InspectionFinding] = []
        for finding in findings:
            combined = " ".join((finding.category, finding.title, finding.detail, finding.recommendation))
            if rank == 7 and any(marker in combined for marker in ("related_functions", "관련 기능", "function_count")):
                continue
            if rank < 9 and any(marker in combined for marker in ("related_policies", "관련 정책", "policy_group_count", "policy_item_count")):
                continue
            if is_previous_chapter_only_finding(finding, rank):
                continue
            result.append(finding)
        return result
    if rank >= 9:
        return list(findings)

    current_terms = {
        1: ("개요", "범위", "설계 원칙", "후속 상세화", "주제", "형식", "가이드", "업무코드", "내부 코드", "문체"),
        2: ("용어", "약어", "정의", "주요 용어", "형식", "가이드"),
        3: ("액터", "책임", "주체", "형식", "가이드"),
        4: ("유즈케이스", "액터", "프로세스 정의 대상", "형식", "가이드"),
        5: ("다이어그램", "UML", "include", "association", "관계", "형식", "가이드"),
        6: ("상태", "상태전이", "전이", "형식", "가이드"),
    }.get(rank, ())
    future_only_markers = (
        "아직 없음",
        "아직 검증",
        "검증할 수 없습니다",
        "후속 장",
        "후속 상세",
        "process_count",
        "function_count",
        "policy_group_count",
        "policy_item_count",
        "0건",
    )
    result: List[InspectionFinding] = []
    for finding in findings:
        combined = " ".join((finding.category, finding.title, finding.detail, finding.recommendation))
        heading = " ".join((finding.category, finding.title))
        if rank <= 3 and "샘플" in heading and any(marker in combined for marker in ("분량", "body_bytes", "밀도")):
            continue
        if rank == 1 and not any(
            allowed in finding.category for allowed in ("템플릿 가이드", "내용", "형식", "양식", "개요", "범위", "문체", "내부 코드")
        ):
            continue
        if rank < 7 and any(marker in combined for marker in ("process_count", "프로세스 연결", "어느 프로세스", "프로세스에 묶")):
            continue
        if any(marker in combined for marker in future_only_markers) and not any(term in heading for term in current_terms):
            continue
        if is_previous_chapter_only_finding(finding, rank):
            continue
        if any(term in heading for term in current_terms):
            result.append(finding)
    return result


def is_previous_chapter_only_finding(finding: InspectionFinding, rank: int) -> bool:
    """Exclude LLM feedback that blocks a stage but cannot be fixed by that stage's writer."""
    if getattr(finding, "fix_owner", "current_chapter") in {"upstream_chapter", "cross_chapter"}:
        return False
    combined = " ".join((finding.category, finding.title, finding.detail, finding.recommendation))
    heading = " ".join((finding.category, finding.title))
    recommendation = finding.recommendation
    if rank == 6:
        if any(marker in recommendation for marker in ("용어를", "용어·", "유즈케이스를", "액터를")) and not any(
            marker in recommendation for marker in ("상태", "전이", "ST-")
        ):
            return True
    if rank == 7:
        current_markers = ("프로세스 설명", "프로세스 목록", "업무 흐름도", "BPMN", "PR-")
        prior_heading_markers = ("개요", "주요 용어", "용어", "액터", "유즈케이스", "상태명")
        prior_edit_markers = ("개요", "용어", "액터", "유즈케이스", "상태명", "도입문", "머리문장")
        if any(marker in heading for marker in prior_heading_markers) and not any(marker in combined for marker in current_markers):
            return True
        if any(marker in recommendation for marker in prior_edit_markers) and not any(marker in recommendation for marker in current_markers):
            return True
    if rank == 8:
        current_markers = ("기능", "FN-", "세부 기능", "related_functions", "관련 기능")
        prior_heading_markers = ("개요", "주요 용어", "용어", "액터", "유즈케이스", "상태")
        if any(marker in heading for marker in prior_heading_markers) and not any(marker in combined for marker in current_markers):
            return True
    return False


def json_object_schema(properties: Mapping[str, object]) -> dict:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


def json_array_schema(items: Mapping[str, object]) -> dict:
    return {"type": "array", "items": dict(items)}


def limit_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...TRUNCATED..."


def collect_json_metrics(spec: Mapping[str, object], scope: str) -> dict:
    return {
        "input_mode": "json",
        "scope": scope,
        "term_count": len(json_rows(spec, "terms")),
        "actor_count": len(json_rows(spec, "actors")),
        "usecase_count": len(json_rows(spec, "usecases")),
        "state_count": len(json_rows(spec, "states")),
        "transition_count": len(json_rows(spec, "state_transitions")),
        "process_count": len(json_rows(spec, "processes")),
        "function_count": len(json_rows(spec, "functions")),
        "process_detail_count": len(json_rows(spec, "process_details")),
        "function_detail_count": len(json_rows(spec, "function_details")),
        "policy_group_count": len(json_rows(spec, "policy_groups")),
        "policy_detail_count": len(json_rows(spec, "policy_details")),
        "final_check_count": len(spec.get("final_check", []) if isinstance(spec.get("final_check"), list) else []),
    }


def compact_json_metrics(metrics: Mapping[str, object]) -> dict:
    return {
        key: metrics.get(key)
        for key in (
            "input_mode",
            "scope",
            "term_count",
            "actor_count",
            "usecase_count",
            "state_count",
            "transition_count",
            "process_count",
            "function_count",
            "process_detail_count",
            "function_detail_count",
            "policy_group_count",
            "policy_detail_count",
            "final_check_count",
        )
        if key in metrics
    }


def check_json_stage_rules(spec: Mapping[str, object], scope: str) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    actors = json_rows(spec, "actors")
    usecases = json_rows(spec, "usecases")
    states = json_rows(spec, "states")
    transitions = json_rows(spec, "state_transitions")
    processes = json_rows(spec, "processes")
    process_details = json_rows(spec, "process_details")
    functions = json_rows(spec, "functions")
    function_details = json_rows(spec, "function_details")
    policy_groups = json_rows(spec, "policy_groups")
    policy_details = json_rows(spec, "policy_details")

    actor_names = {str(row.get("name", "")).strip() for row in actors if str(row.get("name", "")).strip()}
    usecase_ids = {str(row.get("id", "")).strip() for row in usecases if str(row.get("id", "")).strip()}
    state_names = {str(row.get("name", "")).strip() for row in states if str(row.get("name", "")).strip()}
    process_ids = {str(row.get("id", "")).strip() for row in processes if str(row.get("id", "")).strip()}
    process_names_by_id = {
        str(row.get("id", "")).strip(): str(row.get("name", "")).strip()
        for row in processes
        if str(row.get("id", "")).strip()
    }
    function_names_by_id = {
        str(row.get("id", "")).strip(): str(row.get("name", "")).strip()
        for row in functions
        if str(row.get("id", "")).strip()
    }
    policy_ids = {str(row.get("id", "")).strip() for row in policy_groups if str(row.get("id", "")).strip()}
    policy_names_by_id = {
        str(row.get("id", "")).strip(): str(row.get("name", "")).strip()
        for row in policy_groups
        if str(row.get("id", "")).strip()
    }
    full_template = str(spec.get("meta", {}).get("template_type", "") if isinstance(spec.get("meta"), Mapping) else "").strip().casefold() == "full"

    if stage_reached(scope, "usecases") and actor_names:
        missing_actor_refs = [
            f"{row.get('id', '')}:{row.get('actor', '')}"
            for row in usecases
            if str(row.get("actor", "")).strip() not in actor_names
        ]
        if missing_actor_refs:
            findings.append(error("JSON 정합성", "유즈케이스 액터 참조 불일치", "액터 목록에 없는 actor를 참조합니다: " + ", ".join(missing_actor_refs[:6]), "이번 장의 usecases.actor 값을 actor 목록의 name과 정확히 일치시키세요."))

    if stage_reached(scope, "state") and state_names:
        invalid_transitions = [
            f"{row.get('current_state', '')}->{row.get('next_state', '')}"
            for row in transitions
            if str(row.get("current_state", "")).strip() not in state_names
            or str(row.get("next_state", "")).strip() not in state_names
        ]
        if invalid_transitions:
            findings.append(error("JSON 정합성", "상태 전이 참조 불일치", "상태 목록에 없는 상태명을 전이에서 사용합니다: " + ", ".join(invalid_transitions[:6]), "이번 장의 state_transitions.current_state와 next_state를 states.name 중 하나로 맞추세요."))
        findings.extend(check_state_json_quality(states, transitions))
        findings.extend(check_state_transition_usecase_coverage(usecases, transitions))

    if stage_reached(scope, "usecases"):
        step_like_y = [
            f"{row.get('id', '')} {row.get('name', '')}"
            for row in usecases
            if str(row.get("process_target", "")).strip().upper() == "Y"
            and is_step_like_usecase_name(str(row.get("name", "")))
        ]
        if step_like_y:
            findings.append(
                error(
                    "JSON 정합성",
                    "절차형 Y 유즈케이스",
                    "절차 단계가 process_target=Y 유즈케이스로 작성되었습니다: " + ", ".join(step_like_y[:8]),
                    "해당 항목은 상위 업무 목적 유즈케이스로 묶고, 세부 행위는 프로세스 장으로 내리세요.",
                    target_path="current_chapter.usecases[*].name",
                    root_cause="process_target=Y usecase was written at process-step granularity",
                    required_change="절차 단계명 유즈케이스를 고객·운영자가 완료하려는 상위 업무 목적명으로 병합·확대한다.",
                    patch_hint="약관 동의, 인증, 입력, 조건 확인, 결과 안내는 유즈케이스가 아니라 해당 유즈케이스의 프로세스·상태·정책으로 내린다.",
                    acceptance_check="process_target=Y 유즈케이스명에 약관 동의, 인증, 정보 입력, 조건 확인, 결과 확인 같은 절차 단계 표현이 남지 않아야 한다.",
                )
            )
        human_target_missing = [
            f"{row.get('id', '')}:{row.get('actor', '')}"
            for row in usecases
            if is_human_actor(str(row.get("actor", "")))
            and str(row.get("process_target", "")).strip().upper() != "Y"
        ]
        if human_target_missing:
            findings.append(error("JSON 정합성", "사람 액터 process_target 오분류", "사람 액터 유즈케이스가 process_target=Y가 아닙니다: " + ", ".join(human_target_missing[:8]), "고객뿐 아니라 운영자, 법정대리인, 대리인, 관리자처럼 사람이 수행하는 액터는 원칙적으로 process_target=Y로 작성하세요."))

    if stage_reached(scope, "process"):
        y_usecases = {
            str(row.get("id", "")).strip(): row
            for row in usecases
            if str(row.get("process_target", "")).strip().upper() == "Y"
        }
        process_usecase_ids = {str(row.get("usecase_id", "")).strip() for row in processes}
        missing_processes = sorted(set(y_usecases) - process_usecase_ids)
        if missing_processes:
            findings.append(error("JSON 정합성", "Y 유즈케이스 프로세스 누락", "프로세스 정의 대상 유즈케이스에 연결된 프로세스가 없습니다: " + ", ".join(missing_processes[:8]), "이번 장의 processes에 누락된 usecase_id별 프로세스를 추가하세요."))
        invalid_process_refs = [
            f"{row.get('id', '')}:{row.get('usecase_id', '')}"
            for row in processes
            if str(row.get("usecase_id", "")).strip() not in usecase_ids
        ]
        if invalid_process_refs:
            findings.append(error("JSON 정합성", "프로세스 유즈케이스 참조 불일치", "유즈케이스 목록에 없는 usecase_id를 사용합니다: " + ", ".join(invalid_process_refs[:6]), "이번 장의 processes.usecase_id를 usecases.id 중 하나로 맞추세요."))
        count_by_usecase: dict[str, int] = {}
        coarse_names: List[str] = []
        for process in processes:
            usecase_id = str(process.get("usecase_id", "")).strip()
            count_by_usecase[usecase_id] = count_by_usecase.get(usecase_id, 0) + 1
            usecase_name = str(y_usecases.get(usecase_id, {}).get("name", "")).strip()
            process_name = str(process.get("name", "")).strip()
            if usecase_name and process_name in {usecase_name, f"{usecase_name} 처리"}:
                coarse_names.append(f"{process.get('id', '')} {process_name}")
        density_profile = density_profile_from_spec(spec)
        single_process_usecases = [
            f"{usecase_id} {row.get('name', '')}({count_by_usecase.get(usecase_id, 0)}개)"
            for usecase_id, row in y_usecases.items()
            if is_human_actor(str(row.get("actor", "")))
            and count_by_usecase.get(usecase_id, 0) == 1
        ]
        if single_process_usecases:
            findings.append(error("JSON 정합성", "Y 유즈케이스 단일 프로세스 축소", "사람 액터 Y 유즈케이스가 단일 프로세스로 축소되어 업무 전환점이 보이지 않습니다: " + ", ".join(single_process_usecases[:8]), "개수를 맞추기 위해 늘리지 말고, 실제로 다른 시작·판단·처리·결과 경계를 갖는 전환점만 분해하세요."))
        overconcentrated_usecases = [
            f"{usecase_id} {row.get('name', '')}({count_by_usecase.get(usecase_id, 0)}개)"
            for usecase_id, row in y_usecases.items()
            if is_human_actor(str(row.get("actor", "")))
            and count_by_usecase.get(usecase_id, 0) > 7
        ]
        if overconcentrated_usecases:
            findings.append(error("JSON 정합성", "Y 유즈케이스 프로세스 과집중", "사람 액터 Y 유즈케이스 하나에 프로세스가 과도하게 몰려 업무 목표가 넓어졌을 수 있습니다: " + ", ".join(overconcentrated_usecases[:8]), "절차 단계로 잘게 쪼개지는 것은 피하되, 고객·운영자의 목표가 실제로 달라지는 지점은 별도 유즈케이스로 분리하고 프로세스를 재배분하세요."))
        if coarse_names:
            findings.append(warn("JSON 정합성", "프로세스명 포괄 표현", "프로세스명이 유즈케이스명과 같거나 처리로만 끝납니다: " + ", ".join(coarse_names[:8]), "프로세스명은 해당 유즈케이스를 구성하는 세부 절차명으로 변경하세요."))
        findings.extend(check_process_state_name_drift(processes, state_names))
        findings.extend(check_process_responsibility_boundaries(processes, actors))

    if stage_reached(scope, "functions") and process_ids:
        invalid_function_refs = [
            f"{row.get('id', '')}:{process_id}"
            for row in functions
            for process_id in json_function_process_ids(row)
            if process_id not in process_ids
        ]
        if invalid_function_refs:
            findings.append(error("JSON 정합성", "기능 프로세스 참조 불일치", "프로세스 목록에 없는 process_id를 사용합니다: " + ", ".join(invalid_function_refs[:6]), "이번 장의 functions.process_id를 processes.id 중 하나로 맞추세요."))
        functions_without_process = [
            str(row.get("id", "")).strip()
            for row in functions
            if not json_function_process_ids(row)
        ]
        if functions_without_process:
            findings.append(error("JSON 정합성", "기능 프로세스 연결 누락", "process_id/process_ids가 없는 기능이 있습니다: " + ", ".join(functions_without_process[:6]), "모든 기능은 대표 process_id와 연결 대상 process_ids를 가져야 합니다."))
        findings.extend(check_function_granularity_by_json(processes, functions))

    if full_template and scope in {"09_process_detail", "process_detail", "09_function_detail", "function_detail", "full"}:
        process_detail_ids = {str(row.get("process_id", "")).strip() for row in process_details if str(row.get("process_id", "")).strip()}
        missing_process_details = sorted(process_ids - process_detail_ids)
        if missing_process_details:
            findings.append(error("JSON 정합성", "Full 프로세스 상세 누락", "프로세스 상세가 없는 프로세스가 있습니다: " + ", ".join(missing_process_details[:8]), "Process Detail Agent는 모든 processes.id에 대해 process_details.process_id를 작성해야 합니다."))
        for row in process_details:
            process_id = str(row.get("process_id", "")).strip()
            if process_id and process_id not in process_ids:
                findings.append(error("JSON 정합성", "프로세스 상세 참조 불일치", f"process_details.process_id가 프로세스 목록에 없습니다: {process_id}", "process_details.process_id는 processes.id 중 하나여야 합니다."))
            for field in ("entry_condition", "exit_condition"):
                if not str(row.get(field, "")).strip():
                    findings.append(error("JSON 정합성", "프로세스 상세 조건 누락", f"{process_id}의 {field}가 비어 있습니다.", "진입 조건과 종료 조건을 각각 한 문장으로 작성하세요."))
            if compact_space(row.get("entry_condition", "")) == compact_space(row.get("exit_condition", "")):
                findings.append(error("JSON 정합성", "프로세스 상세 조건 동일", f"{process_id}의 진입 조건과 종료 조건이 동일합니다.", "진입 조건은 시작 기준, 종료 조건은 완료·제한·실패·보류 등 결과 확정 기준으로 분리하세요."))
            for field, label in (("previous_processes", "선행 프로세스"), ("next_processes", "후행 프로세스")):
                for message in check_process_flow_refs(row.get(field, []), process_ids, process_names_by_id, label, process_id):
                    findings.append(error("JSON 정합성", "프로세스 상세 흐름 참조 불일치", message, "선행·후행 프로세스는 프로세스 ID와 명칭 또는 프로세스 목록의 실제 명칭으로 작성하세요."))
            for message in check_named_refs(row.get("related_functions", []), function_names_by_id, split_function_reference, "관련 기능", process_id):
                findings.append(error("JSON 정합성", "프로세스 상세 기능 참조 불일치", message, "관련 기능은 기능 목록의 기능 ID와 기능명을 함께 작성하세요."))
            for message in check_named_refs(row.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", process_id):
                findings.append(error("JSON 정합성", "프로세스 상세 정책 참조 불일치", message, "관련 정책은 정책 목록의 정책 ID와 정책명을 함께 작성하세요."))

    if full_template and scope in {"09_function_detail", "function_detail", "full"}:
        function_ids = {str(row.get("id", "")).strip() for row in functions if str(row.get("id", "")).strip()}
        function_detail_ids = {str(row.get("function_id", "")).strip() for row in function_details if str(row.get("function_id", "")).strip()}
        missing_function_details = sorted(function_ids - function_detail_ids)
        if missing_function_details:
            findings.append(error("JSON 정합성", "Full 기능 상세 누락", "기능 상세가 없는 기능이 있습니다: " + ", ".join(missing_function_details[:8]), "Function Detail Agent는 모든 functions.id에 대해 function_details.function_id를 작성해야 합니다."))
        for row in function_details:
            function_id = str(row.get("function_id", "")).strip()
            if function_id and function_id not in function_ids:
                findings.append(error("JSON 정합성", "기능 상세 참조 불일치", f"function_details.function_id가 기능 목록에 없습니다: {function_id}", "function_details.function_id는 functions.id 중 하나여야 합니다."))
            for field in ("input_information", "processing_logic", "sub_functions", "output_information", "failure_exception_cases", "related_policies"):
                values = row.get(field)
                if not isinstance(values, list) or not any(str(item).strip() for item in values):
                    findings.append(error("JSON 정합성", "기능 상세 슬롯 누락", f"{function_id}의 {field}가 비어 있습니다.", "입력, 처리, 출력, 실패·예외, 관련 정책을 기능별로 작성하세요."))
            processing_logic = row.get("processing_logic", [])
            if isinstance(processing_logic, list):
                logic_lines = [str(item).strip() for item in processing_logic if str(item).strip()]
                if logic_lines and len(logic_lines) < 3:
                    findings.append(error("JSON 정합성", "기능 상세 처리 로직 부족", f"{function_id}의 처리 로직이 정상·분기·예외 흐름을 구분하기에 부족합니다.", "처리 로직은 최소 3개 이상 작성하고 각 줄을 '(상태) ... → (액션) ... → (결과) ...' 형식으로 쓰세요."))
                invalid_logic = [
                    line
                    for line in logic_lines
                    if not FUNCTION_PROCESSING_LOGIC_PATTERN.search(" ".join(line.split()))
                ]
                if invalid_logic:
                    findings.append(error("JSON 정합성", "기능 상세 처리 로직 형식 불일치", f"{function_id}의 처리 로직이 샘플의 상태-액션-결과 형식과 다릅니다: {invalid_logic[0]}", "처리 로직은 '(상태) ... → (액션) ... → (결과) ...' 형식으로 작성하세요."))
            for message in check_named_refs(row.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", function_id):
                findings.append(error("JSON 정합성", "기능 상세 정책 참조 불일치", message, "기능 상세의 관련 정책은 정책 목록의 정책 ID와 정책명을 함께 작성하세요."))

    if stage_reached(scope, "policies") and policy_ids:
        invalid_policy_refs = [
            f"{row.get('id', '')}:{row.get('policy_id', '')}"
            for row in policy_details
            if str(row.get("policy_id", "")).strip() not in policy_ids
        ]
        if invalid_policy_refs:
            findings.append(error("JSON 정합성", "정책 상세 정책 ID 불일치", "정책 목록에 없는 policy_id를 사용합니다: " + ", ".join(invalid_policy_refs[:6]), "이번 장의 policy_details.policy_id를 policy_groups.id 중 하나로 맞추세요."))
        empty_policy_groups = [
            str(row.get("id", "")).strip()
            for row in policy_groups
            if str(row.get("id", "")).strip() and not any(str(detail.get("policy_id", "")).strip() == str(row.get("id", "")).strip() for detail in policy_details)
        ]
        if empty_policy_groups:
            findings.append(error("JSON 정합성", "정책 그룹 상세 누락", "정책 상세가 없는 정책 그룹이 있습니다: " + ", ".join(empty_policy_groups[:8]), "이번 장의 policy_details에 각 정책 그룹별 판단 기준을 최소 1개 이상 작성하세요."))
        findings.extend(check_policy_detail_declaration_rules(policy_details))

    return findings


def check_process_state_name_drift(processes: Sequence[Mapping[str, object]], state_names: set[str]) -> List[InspectionFinding]:
    if not state_names:
        return []
    drift: List[str] = []
    state_like_pattern = re.compile(r"([가-힣A-Za-z0-9·/ ]{2,24}(?:완료|보류|실패|제한|필요))\s*(?:로|상태)")
    for index, process in enumerate(processes):
        description = str(process.get("description", "") or "")
        process_id = str(process.get("id", "") or f"processes[{index}]").strip()
        for match in state_like_pattern.finditer(description):
            candidate = re.sub(r"\s+", " ", match.group(1)).strip()
            if state_drift_candidate_is_known_phrase(candidate, state_names):
                continue
            if candidate and candidate not in state_names:
                drift.append(f"current_chapter.processes[{index}].description:{process_id}:{candidate}")
    if not drift:
        return []
    return [
        InspectionFinding(
            "warn",
            "JSON 정합성",
            "프로세스 설명의 비승인 상태명 의심",
            "프로세스 설명에 상태명처럼 보이나 상태 목록에 없는 표현이 있습니다: " + ", ".join(drift[:6]),
            "현재 장의 프로세스 설명에서 해당 표현을 승인된 states.name으로 바꾸거나, 상태명이 아닌 중립 처리 설명으로 고치세요.",
            tier="P2",
            target_path=",".join(item.split(":")[0] for item in drift[:6]),
            fix_owner="current_chapter",
        )
    ]


def state_drift_candidate_is_known_phrase(candidate: str, state_names: set[str]) -> bool:
    """Avoid flagging a sentence fragment that merely lists approved states.

    The drift detector intentionally looks for Korean phrases ending with
    상태-like suffixes, but process descriptions often say things like
    "인증 실패 시 인증·동의 필요 또는 인증 실패로 종료한다." In that case
    the greedy regex sees the whole fragment as one candidate even though the
    actual state mentions are approved.
    """

    if candidate in state_names:
        return True
    if not any(name in candidate for name in state_names):
        return False
    remainder = candidate
    for name in sorted(state_names, key=len, reverse=True):
        remainder = remainder.replace(name, " ")
    remainder = re.sub(r"(또는|및|시|이면|하면|경우|없거나|있거나|,|/|·|\s)+", " ", remainder).strip()
    return not re.search(r"(완료|보류|실패|제한|필요)$", remainder)


def check_process_responsibility_boundaries(
    processes: Sequence[Mapping[str, object]],
    actors: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    ai_actor_names = [
        str(actor.get("name", "")).strip()
        for actor in actors
        if isinstance(actor, Mapping) and any(marker in str(actor.get("name", "")) for marker in ("AI", "엔진", "모델"))
    ]
    if not ai_actor_names:
        return []
    final_decision_markers = ("최종", "확정", "결정", "분기", "전환", "상담 연결", "노출 경로", "대체 경로")
    channel_owner_markers = ("채널 업무 시스템", "채널", "BSS", "연계 시스템", "운영자")
    risky: List[str] = []
    for index, process in enumerate(processes):
        description = str(process.get("description", "") or "")
        if not any(actor_name and actor_name in description for actor_name in ai_actor_names):
            continue
        if not any(marker in description for marker in final_decision_markers):
            continue
        if any(marker in description for marker in channel_owner_markers):
            continue
        risky.append(f"current_chapter.processes[{index}].description:{process.get('id', '')}")
    if not risky:
        return []
    return [
        InspectionFinding(
            "warn",
            "책임경계",
            "AI 시스템 최종 분기 책임 과다",
            "AI/엔진 계열 액터가 고객 노출 경로 또는 업무 분기를 최종 확정하는 것처럼 읽히는 프로세스 설명이 있습니다: " + ", ".join(risky[:6]),
            "AI/엔진은 의도 해석, 후보 생성, 분류·추천으로 한정하고 결과 유형 확정, 고객 노출 경로, 업무 분기는 채널 업무 시스템 또는 BSS/연계 시스템 책임으로 분리하세요.",
            tier="P2",
            target_path=",".join(item.split(":")[0] for item in risky[:6]),
            fix_owner="current_chapter",
        )
    ]


def check_state_json_quality(states: Sequence[Mapping[str, object]], transitions: Sequence[Mapping[str, object]]) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    leaked_targets: List[str] = []
    transient_states = transient_state_overmodeling_targets(states)
    if transient_states:
        findings.append(
            InspectionFinding(
                "warn",
                "정합성",
                "처리 단계의 상태 승격",
                "상태 코드 목록에 인증·세션·BSS 내부 처리 같은 순간적인 처리 단계가 상태로 승격된 것으로 보입니다: "
                + ", ".join(transient_states[:8]),
                "샘플처럼 오래 남는 고객/업무 상태만 states에 남기고, 인증 실패·세션 만료·BSS 판정 중·동의 누락 같은 세부 사유는 state_transitions.criteria, 프로세스, 정책 항목으로 내리세요.",
                tier="P2",
                target_path="states",
                fix_owner="current_chapter",
            )
        )
    for index, state in enumerate(states, start=1):
        state_id = str(state.get("id", "")).strip() or f"states[{index}]"
        for field in ("name", "description", "next_action"):
            if BODY_ID_PATTERN.search(str(state.get(field, "") or "")):
                leaked_targets.append(f"{state_id}.{field}")
    for index, transition in enumerate(transitions, start=1):
        label = f"{transition.get('current_state', '')}->{transition.get('next_state', '')}" or f"state_transitions[{index}]"
        for field in ("event", "criteria"):
            if BODY_ID_PATTERN.search(str(transition.get(field, "") or "")):
                leaked_targets.append(f"{label}.{field}")
    if leaked_targets:
        findings.append(
            InspectionFinding(
                "warn",
                "문체",
                "상태 본문 ID 노출",
                "상태명, 설명, 후속 처리, 이벤트, 기준 문장에 내부 ID가 노출되었습니다: " + ", ".join(leaked_targets[:8]),
                "ID는 id 컬럼과 연결 필드에만 유지하고 본문 문장은 업무명으로 바꾸세요.",
                tier="P3",
                target_path="states/state_transitions",
            )
        )

    missing_usecase = [
        f"{transition.get('current_state', '')}->{transition.get('next_state', '')}"
        for transition in transitions
        if isinstance(transition, Mapping) and not transition_usecase_ids_value(transition)
    ]
    if missing_usecase:
        findings.append(
            InspectionFinding(
                "error",
                "정합성",
                "상태 전이 유즈케이스 연결 누락",
                "상태 전이는 상태 변경을 발생시키는 유즈케이스에 연결되어야 합니다: " + ", ".join(missing_usecase[:8]),
                "각 state_transitions 항목에 상태 변경을 발생시키는 액터 유즈케이스 ID 목록을 usecase_ids로 채우세요. BSS·인증기관·연계 시스템 결과가 직접 상태를 바꾸면 해당 시스템 액터 유즈케이스도 사용할 수 있습니다. 같은 전이가 여러 유즈케이스에 공통이면 행을 복제하지 말고 usecase_ids에 여러 ID를 넣으세요.",
                tier="P1",
                target_path="state_transitions",
                fix_owner="current_chapter",
            )
        )

    mixed_decision_result = [
        f"{transition.get('current_state', '')}->{transition.get('next_state', '')}"
        for transition in transitions
        if isinstance(transition, Mapping) and state_transition_mixes_decision_with_terminal_result(transition)
    ]
    if mixed_decision_result:
        findings.append(
            InspectionFinding(
                "warn",
                "정합성",
                "가능 여부와 확정 결과 혼용",
                "상태 전이 기준에서 가능 여부 판정과 완료·취소·종료 같은 확정 결과가 한 행에 섞여 있습니다: "
                + ", ".join(mixed_decision_result[:8]),
                "가능 여부는 판정 중/제한/보류 상태로 닫고, 완료·취소·종료는 확정·반영 조건이 충족된 별도 전이 기준으로 분리하세요.",
                tier="P2",
                target_path="state_transitions",
                fix_owner="current_chapter",
            )
        )

    grouped: dict[str, List[Mapping[str, object]]] = {}
    for transition in transitions:
        current = str(transition.get("current_state", "")).strip()
        if current:
            grouped.setdefault(current, []).append(transition)
    priority_keywords = ("우선", "먼저", "순위", "배타", "하나라도", "모두", "없고", "있는 경우", "없는 경우")
    exception_keywords = ("실패", "제한", "보류", "불일치", "오류", "중단", "만료", "취소", "누락", "충돌", "예외")
    ambiguous = []
    for current, rows in grouped.items():
        if len(rows) < 4:
            continue
        joined = " ".join(str(row.get("event", "")) + " " + str(row.get("criteria", "")) for row in rows)
        exception_count = sum(
            1
            for row in rows
            if any(keyword in f"{row.get('event', '')} {row.get('criteria', '')}" for keyword in exception_keywords)
        )
        if exception_count >= 2 and not any(keyword in joined for keyword in priority_keywords):
            ambiguous.append(current)
    if ambiguous:
        findings.append(
            InspectionFinding(
                "warn",
                "정합성",
                "분기 우선순위 부족",
                "같은 현재값에서 예외 분기가 여러 개 발생하지만 우선 적용 기준이 부족합니다: " + ", ".join(ambiguous[:6]),
                "해당 현재값의 criteria에 실패, 제한, 보류, 완료가 동시에 성립할 때의 우선순위 또는 배타 조건을 짧게 추가하세요.",
                tier="P2",
                target_path="state_transitions",
            )
        )
    return findings


TRANSIENT_STATE_MARKERS = (
    "로그인 세션",
    "세션 만료",
    "인증·동의",
    "인증 동의",
    "인증 실패",
    "동의 누락",
    "BSS 상태 변경",
    "BSS 처리",
    "판정 중",
    "처리 중",
)


def transient_state_overmodeling_targets(states: Sequence[Mapping[str, object]]) -> List[str]:
    targets: List[str] = []
    for state in states:
        if not isinstance(state, Mapping):
            continue
        name = str(state.get("name", "")).strip()
        text = " ".join(
            str(state.get(field, "")).strip()
            for field in ("name", "description", "next_action")
            if str(state.get(field, "")).strip()
        )
        if any(marker in text for marker in TRANSIENT_STATE_MARKERS):
            targets.append(name or str(state.get("id", "")).strip())
    return targets if len(targets) >= 2 else []


STATE_TERMINAL_RESULT_KEYWORDS = ("완료", "취소", "종료", "확정", "반영 완료", "탈퇴완료", "수락 완료")
STATE_TERMINAL_CONFIRMATION_KEYWORDS = (
    "확정",
    "완료",
    "성공",
    "승인",
    "최종",
    "상태 변경",
    "반영",
    "종료",
    "전환",
    "처리 결과",
)


def state_transition_mixes_decision_with_terminal_result(transition: Mapping[str, object]) -> bool:
    next_state = str(transition.get("next_state", "")).strip()
    if not any(keyword in next_state for keyword in STATE_TERMINAL_RESULT_KEYWORDS):
        return False
    text = f"{transition.get('event', '')} {transition.get('criteria', '')}"
    if "가능" not in text:
        return False
    return not any(keyword in text for keyword in STATE_TERMINAL_CONFIRMATION_KEYWORDS)


def check_state_transition_usecase_coverage(
    usecases: Sequence[Mapping[str, object]],
    transitions: Sequence[Mapping[str, object]],
) -> List[InspectionFinding]:
    required_usecases = []
    for usecase in usecases:
        usecase_id = str(usecase.get("id", "")).strip()
        if not usecase_id:
            continue
        name = str(usecase.get("name", "")).strip()
        description = str(usecase.get("description", "")).strip()
        if usecase_requires_state_transition(usecase):
            required_usecases.append((usecase_id, name))
    if not required_usecases:
        return []
    covered = set()
    for transition in transitions:
        if isinstance(transition, Mapping):
            covered.update(transition_usecase_ids_value(transition))
    missing = [f"{usecase_id} {name}" for usecase_id, name in required_usecases if usecase_id not in covered]
    if not missing:
        return []
    return [
        InspectionFinding(
            "warn",
            "정합성",
            "상태 전이 유즈케이스 범위 부족",
            "상태 변경 또는 후속 처리 판단이 필요한 유즈케이스가 state_transitions.usecase_ids에 없습니다: "
            + ", ".join(missing[:8]),
            "모든 유즈케이스를 기계적으로 전이 행으로 늘리지 말고, 해당 유즈케이스가 실제로 바꾸는 상태가 있으면 전이에 연결하고 같은 전이면 usecase_ids에 함께 묶으세요.",
            tier="P2",
            target_path="state_transitions",
            fix_owner="current_chapter",
        )
    ]


STATE_TRANSITION_REQUIRED_MARKERS = (
    "가입",
    "탈퇴",
    "해지",
    "변경",
    "취소",
    "만료",
    "승인",
    "완료",
    "제한",
    "보류",
    "실패",
    "복구",
    "전환",
    "상태",
    "원장",
    "반영",
    "정지",
    "휴면",
    "해제",
    "수락",
    "거절",
    "주문",
    "결제",
    "환불",
)


def usecase_requires_state_transition(usecase: Mapping[str, object]) -> bool:
    text = " ".join(
        str(usecase.get(key, "")).strip()
        for key in ("name", "description")
        if str(usecase.get(key, "")).strip()
    )
    return any(marker in text for marker in STATE_TRANSITION_REQUIRED_MARKERS)


def check_policy_detail_declaration_rules(policy_details: Sequence[Mapping[str, object]]) -> List[InspectionFinding]:
    findings: List[InspectionFinding] = []
    forbidden_process_ids: List[str] = []
    empty_content_ids: List[str] = []
    fixed_slot_ids: List[str] = []
    for detail in policy_details:
        detail_id = str(detail.get("id", "")).strip()
        if any(key in detail for key in ("process_id", "process_ids", "applicable_processes")):
            forbidden_process_ids.append(detail_id)
        if not str(detail.get("name", "")).strip() or not str(detail.get("content", "")).strip():
            empty_content_ids.append(detail_id)
        if any(key in detail for key in ("condition", "decision_rule", "thresholds", "exception_handling", "customer_notice", "audit_log", "owner", "source_evidence_ids", "tbd_reasons")):
            fixed_slot_ids.append(detail_id)
    if forbidden_process_ids:
        findings.append(error("JSON 정합성", "정책 상세 프로세스 직접 매핑 금지", "정책 상세에 프로세스 직접 매핑 필드가 있습니다: " + ", ".join(forbidden_process_ids[:8]), "policy_details에서는 process_id, process_ids, applicable_processes를 제거하고 policy_id로만 정책 그룹에 연결하세요."))
    if empty_content_ids:
        findings.append(error("정책 구체성", "정책 상세 선언 누락", "정책 상세명 또는 정책 내용이 비어 있습니다: " + ", ".join(empty_content_ids[:8]), "샘플처럼 정책 항목명과 정책 내용을 한 쌍으로 작성하세요."))
    if fixed_slot_ids:
        findings.append(warn("정책 스타일", "정책 상세 고정 슬롯 사용", "정책 상세에 발동 조건·판단 기준·기준값 등 고정 슬롯 필드가 남아 있습니다: " + ", ".join(fixed_slot_ids[:8]), "정책 상세는 id, policy_id, name, content 중심으로 두고, 필요한 동작값과 조건은 정책 항목을 나누어 content에 선언하세요."))
    return findings


def transition_usecase_ids_value(transition: Mapping[str, object]) -> List[str]:
    values = transition.get("usecase_ids")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    legacy = str(transition.get("usecase_id", "")).strip()
    return [legacy] if legacy else []


def compact_findings_for_llm(findings: Sequence[InspectionFinding], limit: int = 60) -> dict:
    """Keep local rule findings in the report, but send a compact version to the LLM."""
    compact = [
        {
            "severity": finding.severity,
            "tier": finding.tier,
            "category": finding.category,
            "title": limit_text(finding.title, 80),
            "detail": limit_text(finding.detail, 220),
            "recommendation": limit_text(finding.recommendation, 220),
            "target_path": limit_text(finding.target_path, 120),
            "root_cause": limit_text(finding.root_cause, 180),
            "required_change": limit_text(finding.required_change, 180),
            "patch_hint": limit_text(finding.patch_hint, 180),
            "acceptance_check": limit_text(finding.acceptance_check, 160),
            "is_quality_gate": finding.is_quality_gate,
        }
        for finding in findings[:limit]
    ]
    return {
        "items": compact,
        "total_count": len(findings),
        "omitted_count": max(0, len(findings) - len(compact)),
        "note": "전체 deterministic finding은 리포트에 유지된다. LLM에는 중복 검수 방지를 위해 압축본만 전달한다.",
    }


def json_local_precheck(spec: Mapping[str, object], scope: str) -> dict:
    """Deterministic checks and link matrix that do not require LLM reasoning."""
    stage_key = inspector_stage_key(scope)
    matrix = build_chain_matrix(spec)
    summary = summarize_chain_matrix_for_stage(matrix, stage_key)
    missing_links = [
        local_issue(str(item.get("type", "")), item.get("id", ""), str(item.get("reason", "")))
        for item in summary.get("missing_links", [])
        if isinstance(item, Mapping)
    ]
    issues = [
        item
        for item in missing_links
        if str(item.get("kind", "")).endswith(("_unknown_actor", "_unknown_usecase", "_unknown_process", "_unknown_group"))
        or "_unknown_" in str(item.get("kind", ""))
    ]
    missing_policy_detail_groups = [
        {
            "policy_id": str(item.get("id", "")).strip(),
            "policy_name": "",
            "reason": str(item.get("reason", "정책 상세가 없음")).strip() or "정책 상세가 없음",
        }
        for item in matrix.get("missing_links", [])
        if isinstance(item, Mapping) and item.get("type") == "policy_group_without_detail"
    ]

    return {
        "purpose": "로컬 코드로 계산한 참조 무결성/연결성 결과다. LLM은 이 결과를 반복 계산하지 말고 의미 품질 판단에 집중한다.",
        "issues": issues[:80],
        "issue_total_count": len(issues),
        "missing_links": missing_links[:80],
        "missing_link_total_count": len(missing_links),
        "chain_matrix": summary.get("rows", []),
        "chain_matrix_stats": summary.get("stats", {}),
        # Local precheck runs inside inspector prompts, so keep graph context
        # intentionally narrow. Full requirement/evidence graph injection belongs
        # to Context Pack assembly where stage-specific relevance can be scored.
        "policy_graph_context": graph_context_for_spec(spec, stage=stage_key, requirements=[], limit=8),
        "orphan_ids": summary.get("orphan_ids", {}),
        "missing_policy_detail_groups": missing_policy_detail_groups if stage_reached(scope, "policies") else [],
    }


def compact_local_precheck_for_llm(precheck: Mapping[str, object], scope: str) -> dict:
    """Send enough local structure to the LLM without rereading every row."""
    final_scope = scope_rank(scope) >= 10 or str(scope or "").strip() == "full"
    issue_limit = 40 if final_scope else 24
    link_limit = 40 if final_scope else 24
    matrix_limit = 48 if final_scope else 24
    graph_limit = 8 if final_scope else 6
    issues = precheck.get("issues", []) if isinstance(precheck.get("issues"), list) else []
    missing_links = precheck.get("missing_links", []) if isinstance(precheck.get("missing_links"), list) else []
    chain_matrix = precheck.get("chain_matrix", []) if isinstance(precheck.get("chain_matrix"), list) else []
    policy_graph_context = precheck.get("policy_graph_context", {}) if isinstance(precheck.get("policy_graph_context"), Mapping) else {}
    missing_policy_detail_groups = (
        precheck.get("missing_policy_detail_groups", [])
        if isinstance(precheck.get("missing_policy_detail_groups"), list)
        else []
    )
    return {
        "purpose": precheck.get("purpose", ""),
        "issue_total_count": precheck.get("issue_total_count", len(issues)),
        "missing_link_total_count": precheck.get("missing_link_total_count", len(missing_links)),
        "issues": compact_stage_inspector_value(
            issues[:issue_limit],
            max_string=140,
            max_list=issue_limit,
            max_dict_keys=8,
        ),
        "missing_links": compact_stage_inspector_value(
            missing_links[:link_limit],
            max_string=140,
            max_list=link_limit,
            max_dict_keys=8,
        ),
        "chain_matrix": compact_stage_inspector_value(
            chain_matrix[:matrix_limit],
            max_string=110,
            max_list=matrix_limit,
            max_dict_keys=10,
        ),
        "chain_matrix_stats": precheck.get("chain_matrix_stats", {}),
        "policy_graph_context": compact_stage_inspector_value(
            policy_graph_context,
            max_string=140,
            max_list=graph_limit,
            max_dict_keys=12,
        ),
        "orphan_ids": compact_stage_inspector_value(
            precheck.get("orphan_ids", {}),
            max_string=70,
            max_list=12,
            max_dict_keys=10,
        ),
        "missing_policy_detail_groups": compact_stage_inspector_value(
            missing_policy_detail_groups[: 20 if final_scope else 12],
            max_string=120,
            max_list=20 if final_scope else 12,
            max_dict_keys=6,
        ),
    }


def local_precheck_metrics(precheck: Mapping[str, object]) -> dict:
    return {
        "issue_count": int(precheck.get("issue_total_count", len(precheck.get("issues", []) if isinstance(precheck.get("issues"), list) else [])) or 0),
        "missing_link_count": int(precheck.get("missing_link_total_count", len(precheck.get("missing_links", []) if isinstance(precheck.get("missing_links"), list) else [])) or 0),
        "matrix_rows": len(precheck.get("chain_matrix", []) if isinstance(precheck.get("chain_matrix"), list) else []),
        "missing_policy_detail_groups": len(
            precheck.get("missing_policy_detail_groups", [])
            if isinstance(precheck.get("missing_policy_detail_groups"), list)
            else []
        ),
    }


def local_issue(kind: str, target: object, reason: str) -> dict:
    return {
        "kind": kind,
        "target": limit_text(str(target or ""), 100),
        "reason": limit_text(reason, 160),
    }


def split_reference_id(value: object, prefix: str) -> str:
    text = str(value or "").strip()
    match = re.match(rf"^({re.escape(prefix)}-[A-Z0-9]+(?:-[A-Z0-9]+)+)", text)
    return match.group(1) if match else ""


def unique_nonempty(items: Iterable[object]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def json_approved_contract(spec: Mapping[str, object], scope: str) -> dict:
    rank = scope_rank(scope)
    contract: dict = {
        "rule": "이전 장은 통과된 기준선이다. 이번 장은 아래 핵심 ID/명칭/참조값을 바꾸지 않고 이어받아야 한다.",
        "topic": spec.get("meta", {}).get("topic", "") if isinstance(spec.get("meta"), Mapping) else "",
    }
    if rank >= 2:
        overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
        contract["overview"] = {
            "scope": compact_json_strings(overview.get("scope", []), 60, 5),
            "principles": compact_json_rows(overview.get("principles", []), ("name",), 38, 6),
        }
    if rank >= 3:
        contract["terms"] = compact_json_rows(spec.get("terms", []), ("id", "name"), 42, 18)
    if rank >= 4:
        contract["actors"] = compact_json_rows(spec.get("actors", []), ("id", "name"), 42, 14)
    if rank >= 6:
        contract["usecases"] = compact_json_rows(spec.get("usecases", []), ("id", "actor", "name", "process_target"), 48, 46)
    if rank >= 7:
        contract["states"] = compact_json_rows(spec.get("states", []), ("id", "name"), 42, 28)
    if rank >= 8:
        contract["processes"] = compact_json_rows(spec.get("processes", []), ("id", "usecase_id", "name"), 48, 60)
    if rank >= 9:
        contract["functions"] = compact_json_rows(spec.get("functions", []), ("id", "process_id", "process_ids", "name"), 48, 70)
        contract["policy_groups"] = compact_json_rows(spec.get("policy_groups", []), ("id", "name"), 48, 60)
    return contract


def json_current_chapter_pack(spec: Mapping[str, object], scope: str, chapter_key: str = "") -> dict:
    if chapter_key == "process_detail":
        return {
            "processes": compact_json_rows(
                spec.get("processes", []),
                ("id", "usecase_id", "name", "description", "related_functions", "related_policies"),
                90,
                120,
            ),
            "process_details": compact_json_rows(
                spec.get("process_details", []),
                ("process_id", "entry_condition", "exit_condition", "previous_processes", "next_processes", "related_functions", "related_policies"),
                95,
                160,
            ),
        }
    if chapter_key == "function_detail":
        return {
            "functions": compact_json_rows(spec.get("functions", []), ("id", "process_id", "process_ids", "name", "description", "details"), 90, 140),
            "function_details": compact_json_rows(
                spec.get("function_details", []),
                ("function_id", "input_information", "processing_logic", "sub_functions", "output_information", "failure_exception_cases", "related_policies"),
                90,
                180,
            ),
        }
    if chapter_key == "terms_refinement":
        return {
            "terms": compact_json_rows(spec.get("terms", []), ("id", "name", "description"), 120, 70),
            "policy_terms_basis": compact_json_rows(spec.get("policy_details", []), ("id", "name", "content"), 110, 80),
        }
    rank = scope_rank(scope)
    if rank == 1:
        return {"overview": spec.get("overview", {})}
    if rank == 2:
        return {"terms": compact_json_rows(spec.get("terms", []), ("id", "name", "description"), 120, 50)}
    if rank == 3:
        return {"actors": compact_json_rows(spec.get("actors", []), ("id", "name", "description"), 120, 30)}
    if rank == 4:
        return {"usecases": compact_json_rows(spec.get("usecases", []), ("id", "actor", "name", "description", "process_target"), 110, 90)}
    if rank == 5:
        diagram = spec.get("meta", {}).get("usecase_diagram", {}) if isinstance(spec.get("meta"), Mapping) else {}
        return {"usecase_diagram": diagram}
    if rank == 6:
        return {
            "states": compact_json_rows(spec.get("states", []), ("id", "name", "description", "next_action"), 100, 45),
            "state_transitions": compact_json_rows(spec.get("state_transitions", []), ("usecase_ids", "current_state", "event", "next_state", "criteria"), 100, 70),
        }
    if rank == 7:
        return {"processes": compact_json_rows(spec.get("processes", []), ("id", "usecase_id", "name", "description"), 110, 100)}
    if rank == 8:
        return {"functions": compact_json_rows(spec.get("functions", []), ("id", "process_id", "process_ids", "name", "description", "details"), 90, 120)}
    if rank == 9:
        return {
            "policy_groups": compact_json_rows(spec.get("policy_groups", []), ("id", "name", "description"), 100, 90),
            "policy_details": compact_json_rows(
                spec.get("policy_details", []),
                ("id", "policy_id", "name", "content"),
                90,
                220,
            ),
        }
    return {"final_check": compact_json_strings(spec.get("final_check", []), 120, 40)}


def json_inspector_support_context(spec: Mapping[str, object], scope: str, chapter_key: str = "") -> dict:
    stage_key = inspector_stage_key(scope, chapter_key)
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = str(meta.get("topic", "") or spec.get("topic", "") or "")
    blueprint = meta.get("authoring_blueprint", {}) if isinstance(meta.get("authoring_blueprint"), Mapping) else {}
    requirement_cards = blueprint.get("requirement_cards", []) if isinstance(blueprint.get("requirement_cards"), list) else []
    chapter_blueprint = selected_chapter_blueprint(blueprint, stage_key)
    target_ids = {
        str(item).strip()
        for item in chapter_blueprint.get("target_requirement_ids", [])
        if str(item).strip()
    }
    requirement_digest = [
        {
            "id": card.get("id", ""),
            "title": limit_text(str(card.get("title", "")), 90),
            "summary": limit_text(str(card.get("summary", "")), 160),
        }
        for card in requirement_cards
        if isinstance(card, Mapping) and (not target_ids or str(card.get("id", "")).strip() in target_ids)
    ][:12]
    support = {
        "stage": stage_key,
        "requirement_digest": requirement_digest,
        "topic_evidence_map": compact_topic_evidence_map_for_stage(
            meta.get("topic_evidence_map", {}) if isinstance(meta.get("topic_evidence_map", {}), Mapping) else {},
            stage_key,
            max_cards=5,
        ),
        "prelearned_knowledge": inspector_prelearned_knowledge_context(topic, stage_key),
        "policy_detail_style_anchor": policy_style_anchor_context(stage_key),
        "pi_agent_context": pi_context_for_stage(stage_key),
        "analysis_method_guard": method_guard_for_inspector(),
        "must_cover": chapter_blueprint.get("must_cover", [])[:8] if isinstance(chapter_blueprint.get("must_cover", []), list) else [],
        "analysis_focus": chapter_blueprint.get("analysis_focus", {}) if isinstance(chapter_blueprint.get("analysis_focus", {}), Mapping) else {},
        "architecture_contract": inspector_architecture_context(blueprint, stage_key),
        "blueprint_quality_gate": relevant_blueprint_quality(meta.get("blueprint_quality_gate", {}), stage_key),
        "context_quality": relevant_context_quality(meta.get("context_pack_runs", []), stage_key),
        "open_inspector_issues": relevant_open_issues(meta.get("open_inspector_issues", []), stage_key),
        "evidence_gaps": relevant_evidence_gaps(spec.get("evidence_gaps", []), stage_key),
        "risk_flags": relevant_open_issues(meta.get("risk_flags", []), stage_key),
    }
    if stage_key == "policies":
        support["policy_derivation_rule"] = (
            "정책은 프로세스와 기능에 필요한 정책을 먼저 정의하고, 정책별 세부 항목을 나눈 뒤, "
            "각 항목별 값·조건·횟수·시간·채널·저장 항목을 선언해야 한다."
        )
    return support


def relevant_context_quality(items: object, stage_key: str) -> dict:
    if not isinstance(items, list):
        return {}
    compact_stage = inspector_stage_key(stage_key)
    stage_aliases = {stage_key, compact_stage}
    candidates = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        chapter = str(item.get("chapter", "") or "")
        if stage_key == "final_check" or chapter in stage_aliases or stage_key.endswith(chapter):
            candidates.append(item)
    if not candidates:
        return {}
    latest = candidates[-1]
    return {
        "chapter": latest.get("chapter", ""),
        "score": latest.get("context_quality_score"),
        "status": latest.get("context_quality_status", ""),
        "required_kind_coverage": latest.get("required_kind_coverage"),
        "evidence_gap_count": latest.get("evidence_gap_count", 0),
        "evidence_source_mix": latest.get("evidence_source_mix", {}),
    }


def inspector_prelearned_knowledge_context(topic: str, stage_key: str) -> dict:
    pack = load_topic_knowledge_pack(topic)
    if not pack:
        return {}
    inventory = pack.get("candidate_inventory", {}) if isinstance(pack.get("candidate_inventory", {}), Mapping) else {}
    guidance = pack.get("chapter_guidance", {}) if isinstance(pack.get("chapter_guidance", {}), Mapping) else {}
    return {
        "version": pack.get("version", ""),
        "topic": pack.get("topic", ""),
        "source_authority_rule": pack.get("source_authority_rule", {}),
        "candidate_usage_policy": pack.get("candidate_usage_policy", {}),
        "source_profile": compact_source_profile_for_inspector(pack.get("source_profile", {})),
        "topic_axes": compact_topic_axes_for_inspector(pack.get("topic_axes", {})),
        "chapter_guidance": compact_stage_guidance_for_inspector(guidance, stage_key),
        "candidate_inventory": stage_candidate_inventory_for_inspector(inventory, stage_key),
        "candidate_validation": {
            "allowed_when": [
                "현재 주제 요구사항 또는 첨부 참고자료와 직접 연결된다.",
                "승인된 액터-유즈케이스-프로세스-기능-정책 계층 중 하나와 연결된다.",
                "첨부 문서의 범위, 템플릿/샘플의 작성 밀도, AGENTS.md 기준과 상충하지 않는다.",
                "후보가 기능 동작값이나 판단값을 구체화하는 데 쓰였고 문서 범위를 넓히지 않는다.",
            ],
            "reject_when": [
                "공개웹 또는 사전학습 후보에만 있고 현재 주제의 첨부 근거·계층 연결이 없다.",
                "현재 주제 밖 인접 업무를 정책서 범위로 끌어온다.",
                "첨부 요구사항, 템플릿, 샘플, AGENTS.md와 상충한다.",
                "후속 상세설계, API, DB, 화면 UI 상세로 내려가는 내용을 정책서 본문에 확정값처럼 쓴다.",
            ],
            "inspector_rule": "지식 기반 후보 채택 자체는 finding이 아니다. 위 reject_when에 해당하거나 allowed_when을 설명할 연결이 없을 때만 보완 finding으로 작성한다.",
        },
    }


def compact_source_profile_for_inspector(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    return {
        "requirements_count": value.get("requirements_count", 0),
        "primary_reference_count": value.get("primary_reference_count", 0),
        "auxiliary_web_reference_count": value.get("auxiliary_web_reference_count", 0),
        "source_mix": value.get("source_mix", {}),
    }


def compact_topic_axes_for_inspector(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    return {
        "customer_task_axes": list(value.get("customer_task_axes", []) or [])[:8] if isinstance(value.get("customer_task_axes", []), list) else [],
        "decision_axes": list(value.get("decision_axes", []) or [])[:8] if isinstance(value.get("decision_axes", []), list) else [],
        "channel_axes": list(value.get("channel_axes", []) or [])[:8] if isinstance(value.get("channel_axes", []), list) else [],
    }


def compact_stage_guidance_for_inspector(guidance: object, stage_key: str) -> dict:
    if not isinstance(guidance, Mapping):
        return {}
    candidate_keys = [stage_key]
    if stage_key == "final_check":
        candidate_keys.extend(["overview", "usecases", "process", "functions", "policies"])
    for key in candidate_keys:
        item = guidance.get(key)
        if isinstance(item, Mapping):
            return {
                "stage": key,
                "focus": list(item.get("focus", []) or [])[:6] if isinstance(item.get("focus", []), list) else [],
                "avoid": list(item.get("avoid", []) or [])[:6] if isinstance(item.get("avoid", []), list) else [],
            }
    return {}


def stage_candidate_inventory_for_inspector(inventory: object, stage_key: str) -> dict:
    if not isinstance(inventory, Mapping):
        return {}
    keys_by_stage = {
        "actors": ("actor_candidates",),
        "usecases": ("actor_candidates", "usecase_candidates"),
        "usecase_diagram": ("actor_candidates", "usecase_candidates"),
        "state": ("usecase_candidates", "state_candidates", "process_patterns"),
        "process": ("usecase_candidates", "state_candidates", "process_patterns"),
        "functions": ("process_patterns", "function_candidates"),
        "function_detail": ("process_patterns", "function_candidates"),
        "policies": ("process_patterns", "function_candidates", "policy_item_candidates"),
        "final_check": ("usecase_candidates", "process_patterns", "function_candidates", "policy_item_candidates"),
    }
    selected_keys = keys_by_stage.get(stage_key, ("actor_candidates", "usecase_candidates", "state_candidates", "process_patterns", "function_candidates", "policy_item_candidates"))
    return {
        key: list(inventory.get(key, []) or [])[:10]
        for key in selected_keys
        if isinstance(inventory.get(key, []), list)
    }


def inspector_stage_key(scope: str, chapter_key: str = "") -> str:
    key = str(chapter_key or "").strip()
    if key:
        return key
    return {
        "01_overview": "overview",
        "02_terms": "terms",
        "03_actors": "actors",
        "04_usecases": "usecases",
        "05_usecase_diagram": "usecase_diagram",
        "06_state": "state",
        "07_process": "process",
        "08_functions": "functions",
        "09_policies": "policies",
        "09_process_detail": "process_detail",
        "09_function_detail": "function_detail",
        "10_final_check": "final_check",
    }.get(str(scope or "").strip(), str(scope or "").strip())


def selected_chapter_blueprint(blueprint: Mapping[str, object], stage_key: str) -> dict:
    chapters = blueprint.get("chapter_blueprints", []) if isinstance(blueprint.get("chapter_blueprints"), list) else []
    for item in chapters:
        if isinstance(item, Mapping) and item.get("stage") == stage_key:
            return dict(item)
    if stage_key == "terms_refinement":
        for item in chapters:
            if isinstance(item, Mapping) and item.get("stage") in {"terms", "policies"}:
                return dict(item)
    return {}


def inspector_architecture_context(blueprint: Mapping[str, object], stage_key: str) -> dict:
    contract = blueprint.get("architecture_contract", {}) if isinstance(blueprint.get("architecture_contract", {}), Mapping) else {}
    if not contract:
        return {}
    stage_contracts = [
        {
            "stage": item.get("stage", ""),
            "layer": item.get("layer", ""),
            "write_as": limit_text(str(item.get("write_as", "")), 80),
            "granularity": limit_text(str(item.get("granularity", "")), 180),
            "do_not_write_as": list(item.get("do_not_write_as", []) or [])[:5] if isinstance(item.get("do_not_write_as"), list) else [],
            "acceptance_checks": list(item.get("acceptance_checks", []) or [])[:5] if isinstance(item.get("acceptance_checks"), list) else [],
        }
        for item in contract.get("stage_contracts", [])
        if isinstance(item, Mapping) and item.get("stage") in {stage_key, "final_check"}
    ]
    return {
        "summary": limit_text(str(contract.get("summary", "")), 180),
        "architecture_evidence_pack": inspector_architecture_evidence_pack(contract.get("architecture_evidence_pack", {}), stage_key),
        "stage_contracts": stage_contracts[:3],
        "hierarchy_skeleton": inspector_skeleton_for_stage(contract.get("hierarchy_skeleton", {}), stage_key),
        "core_design_map": inspector_core_design_map_for_stage(contract.get("core_design_map", {}), stage_key),
    }


def inspector_skeleton_for_stage(skeleton: object, stage_key: str) -> dict:
    if not isinstance(skeleton, Mapping):
        return {}
    result: dict[str, object] = {}
    if stage_key in {"usecases", "state", "process"}:
        result["usecase_groups"] = compact_inspector_skeleton_rows(skeleton.get("usecase_groups", []), ("actor", "goal", "process_target", "process_pattern", "evidence_ids"), 8)
    if stage_key in {"state", "process", "functions", "policies"}:
        result["process_patterns"] = compact_inspector_skeleton_rows(skeleton.get("process_patterns", []), ("usecase_type", "steps", "state_touchpoints", "evidence_ids"), 6)
    if stage_key in {"functions", "function_detail", "policies"}:
        result["function_capabilities"] = compact_inspector_skeleton_rows(skeleton.get("function_capabilities", []), ("name", "capability_type", "detail_granularity", "reuse_rule", "evidence_ids"), 8)
    if stage_key in {"policies", "final_check"}:
        result["policy_taxonomy"] = compact_inspector_skeleton_rows(skeleton.get("policy_taxonomy", []), ("policy_group", "derived_from", "policy_items", "value_examples", "evidence_ids"), 8)
    return result


def inspector_core_design_map_for_stage(core_design_map: object, stage_key: str) -> dict:
    if not isinstance(core_design_map, Mapping):
        return {}
    rows = compact_inspector_skeleton_rows(
        core_design_map.get("design_rows", []),
        (
            "requirement_id",
            "title",
            "actors",
            "usecase",
            "state_candidates",
            "process",
            "functions",
            "policy_candidates",
            "policy_item_axes",
        ),
        10 if stage_key in {"final_check", "policies", "functions", "process", "state", "usecases"} else 5,
    )
    fallback = core_design_map.get("fallback_axes", {}) if isinstance(core_design_map.get("fallback_axes", {}), Mapping) else {}
    return {
        "purpose": limit_text(str(core_design_map.get("purpose", "")), 180),
        "design_rows": rows,
        "fallback_axes": {
            "customer_jobs": [limit_text(str(value), 90) for value in fallback.get("customer_jobs", [])[:5]]
            if isinstance(fallback.get("customer_jobs", []), list)
            else [],
            "policy_questions": [limit_text(str(value), 90) for value in fallback.get("policy_questions", [])[:5]]
            if isinstance(fallback.get("policy_questions", []), list)
            else [],
            "bss_touchpoints": [limit_text(str(value), 90) for value in fallback.get("bss_touchpoints", [])[:5]]
            if isinstance(fallback.get("bss_touchpoints", []), list)
            else [],
        },
    }


def inspector_architecture_evidence_pack(pack: object, stage_key: str) -> dict:
    if not isinstance(pack, Mapping):
        return {}
    stage_card_ids = pack.get("stage_card_ids", {})
    ids = stage_card_ids.get(stage_key, []) if isinstance(stage_card_ids, Mapping) else []
    ids_set = {str(item) for item in ids if str(item).strip()}
    cards = []
    for item in pack.get("cards", []):
        if not isinstance(item, Mapping):
            continue
        stages = item.get("stages", []) if isinstance(item.get("stages", []), list) else []
        if str(item.get("id", "")) not in ids_set and stage_key not in stages:
            continue
        cards.append(
            {
                "id": item.get("id", ""),
                "kind": item.get("kind", ""),
                "title": limit_text(str(item.get("title", "")), 90),
                "summary": limit_text(str(item.get("summary", "")), 160),
                "evidence": [limit_text(str(value), 140) for value in item.get("evidence", [])[:2]] if isinstance(item.get("evidence", []), list) else [],
            }
        )
        if len(cards) >= 6:
            break
    return {"stage_card_ids": list(ids_set)[:8], "cards": cards}


def compact_inspector_skeleton_rows(rows: object, fields: Sequence[str], limit: int) -> List[dict]:
    if not isinstance(rows, list):
        return []
    result: List[dict] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item: dict[str, object] = {}
        for field in fields:
            value = row.get(field)
            if isinstance(value, list):
                item[field] = [limit_text(str(part), 70) for part in value if str(part).strip()][:6]
            elif value is not None:
                item[field] = limit_text(str(value), 120)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def relevant_open_issues(items: object, stage_key: str) -> List[dict]:
    if not isinstance(items, list):
        return []
    selected: List[dict] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        text = json.dumps(item, ensure_ascii=False, default=str)
        if item.get("chapter") == stage_key or stage_key in text:
            selected.append(compact_issue(item))
    return selected[:8]


def relevant_evidence_gaps(items: object, stage_key: str) -> List[dict]:
    if not isinstance(items, list):
        return []
    selected: List[dict] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if item.get("stage") in {stage_key, "blueprint"}:
            selected.append(compact_issue(item))
    return selected[:10]


def relevant_blueprint_quality(quality_gate: object, stage_key: str) -> dict:
    if not isinstance(quality_gate, Mapping):
        return {}
    findings = []
    raw_findings = quality_gate.get("findings", [])
    if not isinstance(raw_findings, list):
        raw_findings = []
    for item in raw_findings:
        if not isinstance(item, Mapping):
            continue
        if item.get("stage") not in {stage_key, "blueprint"}:
            continue
        findings.append(
            {
                "issue_id": item.get("issue_id", ""),
                "severity": item.get("severity", ""),
                "category": item.get("category", ""),
                "title": limit_text(str(item.get("title", "")), 80),
                "detail": limit_text(str(item.get("detail", "")), 140),
                "recommendation": limit_text(str(item.get("recommendation", "")), 160),
                "target_path": item.get("target_path", ""),
            }
        )
    return {
        "status": quality_gate.get("status", ""),
        "passed": quality_gate.get("passed", False),
        "score": quality_gate.get("score", 0),
        "threshold": quality_gate.get("threshold", 0),
        "findings": findings[:8],
    }


def compact_issue(item: Mapping[str, object]) -> dict:
    compact = {}
    for key in ("chapter", "stage", "agent", "score", "threshold", "risk_flag", "risk_tier", "missing_kind", "reason", "handoff"):
        if key in item:
            compact[key] = limit_text(str(item.get(key, "")), 160)
    feedback = item.get("feedback", [])
    if isinstance(feedback, list) and feedback:
        compact["feedback"] = [
            {
                "tier": sub.get("priority_tier", ""),
                "fix_owner": sub.get("fix_owner", ""),
                "upstream_chapter": sub.get("upstream_chapter", ""),
                "category": limit_text(str(sub.get("category", "")), 60),
                "title": limit_text(str(sub.get("title", "")), 80),
                "detail": limit_text(str(sub.get("detail", "")), 140),
            }
            for sub in feedback
            if isinstance(sub, Mapping)
        ][:4]
    return compact


def json_connection_summary(spec: Mapping[str, object], scope: str) -> dict:
    usecases = json_rows(spec, "usecases")
    processes = json_rows(spec, "processes")
    functions = json_rows(spec, "functions")
    policy_groups = json_rows(spec, "policy_groups")
    policy_details = json_rows(spec, "policy_details")
    return {
        "actor_names": [row.get("name", "") for row in json_rows(spec, "actors")[:20]],
        "usecase_ids": [row.get("id", "") for row in usecases[:100]],
        "process_usecase_ids": [row.get("usecase_id", "") for row in processes[:100]],
        "function_process_ids": [row.get("process_id", "") for row in functions[:120]],
        "policy_ids": [row.get("id", "") for row in policy_groups[:90]],
        "policy_detail_policy_ids": [row.get("policy_id", "") for row in policy_details[:160]],
        "scope": scope,
    }


def json_rows(spec: Mapping[str, object], key: str) -> List[dict]:
    value = spec.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def compact_json_rows(items: object, keys: Sequence[str], cell_limit: int, limit: int) -> List[dict]:
    if not isinstance(items, list):
        return []
    result: List[dict] = []
    for item in items[:limit]:
        if not isinstance(item, Mapping):
            continue
        row = {}
        for key in keys:
            value = item.get(key, "")
            if isinstance(value, list):
                row[key] = compact_json_strings(value, cell_limit, 8)
            else:
                row[key] = limit_text(str(value), cell_limit)
        result.append(row)
    return result


def compact_json_strings(items: object, cell_limit: int, limit: int) -> List[str]:
    if not isinstance(items, list):
        return []
    return [limit_text(str(item), cell_limit) for item in items[:limit] if str(item).strip()]


def collect_metrics(body: str, text: str, sample_htmls: Sequence[str], topic: str = "") -> dict:
    sample_bytes = [len(strip_style(sample).encode("utf-8")) for sample in sample_htmls]
    sample_metrics = [sample_metric_counts(sample) for sample in sample_htmls]
    matched_samples = [sample for sample in sample_htmls if sample_matches_topic(sample, topic)]
    matched_sample_bytes = [len(strip_style(sample).encode("utf-8")) for sample in matched_samples]
    matched_sample_metrics = [sample_metric_counts(sample) for sample in matched_samples]
    selected_bytes = matched_sample_bytes or sample_bytes
    selected_metrics = matched_sample_metrics or sample_metrics
    return {
        "body_bytes": len(body.encode("utf-8")),
        "text_chars": len(text),
        "h2_count": len(re.findall(r"<h2\b", body)),
        "h3_count": len(re.findall(r"<h3\b", body)),
        "table_count": len(re.findall(r"<table\b", body)),
        "policy_group_count": body.count("PG-"),
        "policy_item_count": body.count("policy-item-title"),
        "state_count": body.count("ST-"),
        "process_count": body.count("PR-"),
        "function_count": body.count("FN-"),
        "business_codes": infer_business_codes(body),
        "usecase_distinct_count": count_distinct_ids(body, "US-"),
        "process_distinct_count": count_distinct_ids(body, "PR-"),
        "function_distinct_count": count_distinct_ids(body, "FN-"),
        "policy_group_distinct_count": count_distinct_ids(body, "PG-"),
        "sample_topic_match_count": len(matched_samples),
        "sample_reference_mode": "topic_matched" if matched_samples else "structural_reference",
        "sample_min_body_bytes": min(selected_bytes) if selected_bytes else 0,
        "sample_max_body_bytes": max(selected_bytes) if selected_bytes else 0,
        "sample_max_text_chars": max_metric(selected_metrics, "text_chars"),
        "sample_max_usecase_distinct_count": max_metric(selected_metrics, "usecase_distinct_count"),
        "sample_max_process_distinct_count": max_metric(selected_metrics, "process_distinct_count"),
        "sample_max_function_distinct_count": max_metric(selected_metrics, "function_distinct_count"),
        "sample_max_policy_group_distinct_count": max_metric(selected_metrics, "policy_group_distinct_count"),
        "sample_max_policy_item_count": max_metric(selected_metrics, "policy_item_count"),
    }


def sample_metric_counts(document: str) -> dict:
    body = strip_style(document)
    return {
        "text_chars": len(visible_text(body)),
        "usecase_distinct_count": count_distinct_ids(body, "US-"),
        "process_distinct_count": count_distinct_ids(body, "PR-"),
        "function_distinct_count": count_distinct_ids(body, "FN-"),
        "policy_group_distinct_count": count_distinct_ids(body, "PG-"),
        "policy_item_count": body.count("policy-item-title"),
    }


def count_distinct_ids(document: str, prefix: str) -> int:
    return len(set(re.findall(rf"{re.escape(prefix)}[A-Z0-9]+-[A-Z0-9-]+", document)))


def max_metric(metrics: Sequence[dict], key: str) -> int:
    return max((int(item.get(key) or 0) for item in metrics), default=0)


def sample_matches_topic(document: str, topic: str) -> bool:
    compact_topic = re.sub(r"\s+|/|·", "", unicodedata.normalize("NFC", topic or "")).casefold()
    if not compact_topic:
        return False
    compact_anchor = re.sub(r"\s+|/|·", "", unicodedata.normalize("NFC", sample_topic_anchor_text(document))).casefold()
    if compact_topic in compact_anchor:
        return True
    return False


def sample_topic_anchor_text(document: str) -> str:
    """Return only title/header metadata for topic matching.

    A short topic such as "추천" can appear in unrelated sample bodies. Treating
    that as a topic-matched sample makes the Inspector compare a simple policy
    against the wrong document density. Topic match therefore uses title-like
    anchors only; body content remains a structural/style reference.
    """
    body = strip_style(document)
    chunks: List[str] = []
    for pattern in (r"<title[^>]*>(.*?)</title>", r"<h1[^>]*>(.*?)</h1>"):
        for match in re.findall(pattern, body, flags=re.IGNORECASE | re.DOTALL):
            chunks.append(visible_text(match))
    visible = visible_text(body)
    if "정책서 ID" in visible:
        chunks.append(visible.split("정책서 ID", 1)[0][:500])
    return " ".join(chunk for chunk in chunks if chunk)


def calculate_score(findings: Sequence[InspectionFinding]) -> int:
    return int(calculate_score_details(findings)["score"])


def calculate_score_details(findings: Sequence[InspectionFinding]) -> dict:
    items = []
    total_penalty = 0
    gate_blockers = []
    seen_keys = set()
    for finding in findings:
        base_penalty = finding_penalty(finding)
        duplicate_key = (
            str(finding.severity or "").lower(),
            normalize_for_keyword_match(finding.category),
            normalize_for_keyword_match(finding.title),
        )
        is_duplicate = duplicate_key in seen_keys
        seen_keys.add(duplicate_key)
        penalty = 0 if is_duplicate else base_penalty
        total_penalty += penalty
        item = {
            "severity": finding.severity,
            "tier": finding_tier(finding),
            "category": finding.category,
            "title": finding.title,
            "penalty": penalty,
            "base_penalty": base_penalty,
            "duplicate": is_duplicate,
            "quality_gate": is_quality_gate_finding(finding),
        }
        items.append(item)
        if item["quality_gate"] and not is_duplicate:
            gate_blockers.append(item)
    return {
        "score": max(0, 100 - total_penalty),
        "total_penalty": total_penalty,
        "gate_blocker_count": len(gate_blockers),
        "gate_blockers": gate_blockers,
        "items": items,
    }


def finding_penalty(finding: InspectionFinding) -> int:
    severity = str(finding.severity or "").lower()
    text = f"{finding.category} {finding.title} {finding.detail}"
    if severity == "error":
        if is_quality_gate_finding(finding):
            return 24
        if any(keyword in text for keyword in ("템플릿 가이드", "가이드", "상태", "정책", "샘플")):
            return 18
        return 15
    if severity == "warn":
        if is_metric_observation(finding):
            return 2
        if is_quality_gate_finding(finding):
            return 11
        if any(keyword in text for keyword in ("샘플", "템플릿 가이드", "개인정보", "상태 전이", "정책 상세", "정책 구체성", "프로세스-기능", "프로세스-정책")):
            return 7
        if any(keyword in text for keyword in ("문체", "양식", "줄바꿈", "상세 설계", "UI")):
            return 3
        return 5
    return 0


def is_quality_gate_finding(finding: InspectionFinding) -> bool:
    if is_metric_observation(finding):
        return False
    if bool(getattr(finding, "is_quality_gate", False)):
        return True
    text = f"{finding.category} {finding.title} {finding.detail}"
    gate_keywords = (
        "주제 특화",
        "주제 축",
        "챕터 정합성",
        "연결성",
        "정책 구체성",
        "요구사항",
        "BSS",
        "프로세스 관련",
        "정책 그룹",
        "정책 상세",
        "상태 전이",
        "액터별 유즈케이스",
        "프로세스-기능",
        "프로세스-정책",
        "정책 판단",
        "판단 기준",
        "내부 업무코드",
        "업무코드 본문",
        "내부 코드",
    )
    return any(keyword in text for keyword in gate_keywords)


def is_metric_observation(finding: InspectionFinding) -> bool:
    return bool(getattr(finding, "is_metric_observation", False))


def finding_tier(finding: InspectionFinding) -> str:
    explicit = str(getattr(finding, "tier", "") or "").strip().upper()
    if explicit in {"P1", "P2", "P3"}:
        return explicit
    text = f"{finding.category} {finding.title} {finding.detail} {finding.recommendation}"
    if str(finding.severity or "").lower() == "error" or is_quality_gate_finding(finding):
        return "P1"
    if any(
        keyword in text
        for keyword in (
            "정합성",
            "구체성",
            "책임",
            "BSS",
            "요구사항",
            "근거",
            "연결",
            "상태",
            "프로세스",
            "기능",
            "정책",
            "액터",
            "유즈케이스",
        )
    ):
        return "P2"
    return "P3"


def make_summary(status: str, score: int, findings: Sequence[InspectionFinding], metrics: dict) -> str:
    if status == "pass":
        return f"검수 통과. 점수 {score}점이며 양식, 가이드, 샘플 수준 기준을 충족합니다."
    error_count = sum(1 for finding in findings if finding.severity == "error")
    warn_count = sum(1 for finding in findings if finding.severity == "warn")
    return f"검수 결과 {status}. 점수 {score}점, 오류 {error_count}건, 경고 {warn_count}건입니다."


def error(category: str, title: str, detail: str, recommendation: str, **kwargs: object) -> InspectionFinding:
    tier = str(kwargs.pop("tier", "P1") or "P1")
    is_quality_gate = bool(kwargs.pop("is_quality_gate", True))
    return InspectionFinding("error", category, title, detail, recommendation, tier=tier, is_quality_gate=is_quality_gate, **kwargs)


def warn(category: str, title: str, detail: str, recommendation: str, **kwargs: object) -> InspectionFinding:
    return InspectionFinding("warn", category, title, detail, recommendation, **kwargs)


def metric_warn(category: str, title: str, detail: str, recommendation: str, **kwargs: object) -> InspectionFinding:
    kwargs.setdefault("tier", "P3")
    kwargs.setdefault("is_metric_observation", True)
    return warn(category, title, detail, recommendation, **kwargs)


def strip_style(document: str) -> str:
    document = re.sub(r"<style\b.*?</style>", "", document, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<script\b.*?</script>", "", document, flags=re.DOTALL | re.IGNORECASE)


def strip_tags(document: str) -> str:
    return re.sub(r"<[^>]+>", " ", document)


def visible_text(document: str) -> str:
    text = strip_tags(document)
    text = html_unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stage_reached(scope: str, stage: str) -> bool:
    order = {
        "overview": 1,
        "terms": 2,
        "actors": 3,
        "usecases": 4,
        "usecase_diagram": 5,
        "state": 6,
        "process": 7,
        "functions": 8,
        "policies": 9,
        "final_check": 10,
    }
    scope_rank = {
        "01_overview": 1,
        "02_terms": 2,
        "03_actors": 3,
        "04_usecases": 4,
        "05_usecase_diagram": 5,
        "06_state": 6,
        "07_process": 7,
        "08_functions": 8,
        "09_policies": 9,
        "09_process_detail": 9,
        "09_function_detail": 9,
        "process_detail": 9,
        "function_detail": 9,
        "10_final_check": 10,
        "03_overview": 1,
        "04_terms": 2,
        "05_usecases": 6,
        "06_process": 7,
        "07_functions": 8,
        "08_policies": 9,
        "09_final": 10,
        "09_terms_refinement": 9,
        "terms_refinement": 9,
        "full": 10,
    }
    return scope_rank.get(scope, 10) >= order[stage]


def extract_text_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    end_index = text.find(end, start_index + len(start)) if end else -1
    if end_index < 0:
        return text[start_index:]
    return text[start_index:end_index]


def extract_html_between(document: str, start: str, end: str) -> str:
    start_index = document.find(start)
    if start_index < 0:
        return ""
    end_index = document.find(end, start_index + len(start)) if end else -1
    if end_index < 0:
        return document[start_index:]
    return document[start_index:end_index]


def table_rows_with_prefix(document: str, prefix: str) -> List[dict]:
    return [row for row in table_rows(document) if row["texts"] and row["texts"][0].startswith(prefix)]


def extract_process_rows(document: str) -> List[dict]:
    process_section = extract_html_between(document, "4. 프로세스 정의", "5. 기능 정의")
    rows: List[dict] = []
    for match in re.finditer(
        r"<h4\b[^>]*>.*?\((US-[^)]+)\)</h4>\s*(<table\b.*?</table>)",
        process_section,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        usecase_id = match.group(1)
        table_html = match.group(2)
        for row in table_rows(table_html):
            cells = row["texts"]
            htmls = row["htmls"]
            if len(cells) < 5 or not cells[0].startswith("PR-"):
                continue
            rows.append(
                {
                    "id": cells[0],
                    "usecase_id": usecase_id,
                    "name": cells[1],
                    "related_functions": split_cell_items(htmls[3]),
                    "related_policies": split_cell_items(htmls[4]),
                }
            )
    return rows


def table_rows(document: str) -> List[dict]:
    rows = []
    for row_html in re.findall(r"<tr\b.*?</tr>", document, flags=re.DOTALL | re.IGNORECASE):
        htmls = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.DOTALL | re.IGNORECASE)
        if not htmls:
            continue
        rows.append(
            {
                "htmls": htmls,
                "texts": [visible_text(cell) for cell in htmls],
            }
        )
    return rows


def table_cell_texts(document: str) -> List[str]:
    texts = []
    for cell_html in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", document, flags=re.DOTALL | re.IGNORECASE):
        text = visible_text(html_unescape(cell_html))
        if text:
            texts.append(text)
    return texts


def policy_item_content_texts(document: str) -> List[str]:
    texts = []
    for item_html in re.findall(
        r'<div class="policy-item-content"[^>]*>(.*?)</div>',
        document,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        text = visible_text(html_unescape(item_html))
        if text:
            texts.append(text)
    return texts


def count_line_items(cell_html: str) -> int:
    text = visible_text(cell_html)
    if not text:
        return 0
    split_count = len([item for item in re.split(r"<br\s*/?>|/", cell_html) if visible_text(item)])
    return max(1, split_count)


def split_cell_items(cell_html: str) -> List[str]:
    normalized = re.sub(r"<br\s*/?>", "\n", cell_html, flags=re.IGNORECASE)
    text = html_unescape(strip_tags(normalized))
    return dedupe(item.strip() for item in re.split(r"\n|,", text) if item.strip())


def split_policy_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(PG-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def is_human_actor(actor: str) -> bool:
    return any(keyword in actor for keyword in ("고객", "운영자", "법정대리인", "대리인", "관리자")) and not is_system_actor(actor)


def is_system_actor(actor: str) -> bool:
    return any(
        keyword in actor
        for keyword in (
            "BSS",
            "시스템",
            "기관",
            "연계",
            "채널 업무",
            "채널 서비스",
            "인증기관",
            "결제기관",
            "배송사",
            "제휴사",
            "엔진",
            "AI",
            "외부",
        )
    )


def is_step_like_usecase_name(name: str) -> bool:
    text = str(name or "")
    compact = re.sub(r"\s+", "", text)
    step_keywords = (
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
        "본인확인",
        "복귀",
        "사유 확인",
        "차단 사유",
        "제한 사유",
        "완료",
        "결과 확인",
        "결과 안내",
        "후속 조치",
    )
    auth_step_keywords = (
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
    if any(keyword in text for keyword in step_keywords):
        return True
    return any(keyword in compact for keyword in auth_step_keywords) or compact == "인증"


def minimum_process_count_for_usecase_name(actor: str, name: str, density_profile: object | None = None) -> int:
    return process_minimum_for_usecase(actor, name, density_profile)


def split_function_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(FN-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def function_reference_matches(value: object, function_names: set[str], function_names_by_id: Mapping[str, str]) -> bool:
    function_id, function_name = split_function_reference(value)
    if function_id:
        expected_name = function_names_by_id.get(function_id)
        return bool(expected_name and function_name == expected_name)
    return str(value or "").strip() in function_names


def compact_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def check_named_refs(
    values: object,
    names_by_id: Mapping[str, str],
    splitter,
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"{owner_id}의 {label}은 배열이어야 합니다."]
    known_names = {name for name in names_by_id.values() if name}
    messages: List[str] = []
    for value in values:
        text = compact_space(value)
        if not text:
            continue
        ref_id, ref_name = splitter(text)
        if not ref_id:
            if text in known_names:
                messages.append(f"{owner_id}의 {label}은 ID와 명칭을 함께 작성해야 합니다: {text}")
            else:
                messages.append(f"{owner_id}의 {label}이 목록에 없습니다: {text}")
            continue
        expected_name = names_by_id.get(ref_id)
        if not expected_name:
            messages.append(f"{owner_id}의 {label} ID가 목록에 없습니다: {ref_id}")
        elif not ref_name:
            messages.append(f"{owner_id}의 {label}은 ID와 명칭을 함께 작성해야 합니다: {text}")
        elif compact_space(ref_name) != compact_space(expected_name):
            messages.append(f"{owner_id}의 {label} 명칭이 ID와 일치하지 않습니다: {text}")
    return messages


def check_process_flow_refs(
    values: object,
    process_ids: set[str],
    process_names_by_id: Mapping[str, str],
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"{owner_id}의 {label}은 배열이어야 합니다."]
    known_names = {name for name in process_names_by_id.values() if name}
    allowed_texts = {"-", "없음", "업무 진입 조건 충족", "결과 안내 또는 후속 업무 연결"}
    messages: List[str] = []
    for value in values:
        text = compact_space(value)
        if not text or text in allowed_texts:
            continue
        match = re.match(r"^(PR-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
        if match:
            process_id = match.group(1).strip()
            process_name = compact_space(match.group(2))
            expected_name = compact_space(process_names_by_id.get(process_id, ""))
            if process_id not in process_ids:
                messages.append(f"{owner_id}의 {label} ID가 프로세스 목록에 없습니다: {process_id}")
            elif process_id == owner_id:
                messages.append(f"{owner_id}의 {label}이 자기 자신을 참조합니다.")
            elif process_name and process_name != expected_name:
                messages.append(f"{owner_id}의 {label} 명칭이 프로세스 ID와 일치하지 않습니다: {text}")
            continue
        if text not in known_names:
            messages.append(f"{owner_id}의 {label}이 프로세스 목록에 없습니다: {text}")
    return messages


def has_unexcluded_detail_term(text: str, term: str) -> bool:
    start = 0
    while True:
        index = text.find(term, start)
        if index < 0:
            return False
        nearby = text[max(0, index - 80) : index + len(term) + 80]
        if not any(keyword in nearby for keyword in ("제외", "다루지", "작성하지", "쓰지 않는다", "상세화")):
            return True
        start = index + len(term)


def has_ui_detail_design_context(text: str, term: str) -> bool:
    start = 0
    while True:
        index = text.find(term, start)
        if index < 0:
            return False
        nearby = text[max(0, index - 100) : index + len(term) + 100]
        if any(keyword in nearby for keyword in ("제외", "다루지", "작성하지", "쓰지 않는다", "상세화")):
            start = index + len(term)
            continue
        if any(keyword in nearby for keyword in ("정책", "기준", "요구사항", "고지", "안내", "노출 조건", "운영", "관리")):
            start = index + len(term)
            continue
        if any(
            keyword in nearby
            for keyword in (
                "픽셀",
                "px",
                "색상",
                "좌표",
                "위치값",
                "여백",
                "폰트",
                "CSS",
                "컴포넌트",
                "클릭",
                "화면 상세",
                "UI 상세",
                "UI 설계",
            )
        ):
            return True
        start = index + len(term)


def has_sentence_break_issue(document: str) -> bool:
    cleaned = strip_code_like_blocks(document)
    for token in re.split(r"(<[^>]+>)", cleaned):
        if not token or token.startswith("<"):
            continue
        normalized = re.sub(r"\s+", " ", html_unescape(token)).strip()
        if not normalized:
            continue
        normalized = re.sub(r"(^|\s)[가-힣]\.\s+(?=\S)", r"\1", normalized)
        if re.search(r"(?<!\d)[.!?][ \t]+(?=[가-힣A-Za-z0-9])", normalized):
            return True
    return False


def strip_code_like_blocks(document: str) -> str:
    cleaned = re.sub(r"<style\b.*?</style>", "", document, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<script\b.*?</script>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<pre\b.*?</pre>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)


def has_customer_state_as_actor(body: str) -> bool:
    actor_names = {"로그인 고객", "비로그인 고객", "정상 고객", "제한 고객", "휴면 고객"}
    actor_table_match = re.search(r"<h3>가\. 액터</h3>.*?</table>", body, flags=re.DOTALL)
    target = actor_table_match.group(0) if actor_table_match else body
    cells = re.findall(r"<td[^>]*>\s*([^<]+?)\s*</td>", target)
    return any(cell.strip() in actor_names for cell in cells)


def html_unescape(value: str) -> str:
    return (
        value.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
    )


def nearby_text(text: str, pattern: str, width: int) -> str:
    index = text.find(pattern)
    if index < 0:
        return ""
    return text[max(0, index - width) : index + width]
