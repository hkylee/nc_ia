"""Development and QA readiness review agent for rendered policy documents."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping


def dev_qa_review_schema() -> dict:
    finding_schema = {
        "type": "object",
        "properties": {
            "perspective": {"type": "string", "enum": ["development", "qa"]},
            "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
            "action_type": {"type": "string", "enum": ["change", "add", "delete"]},
            "severity": {"type": "string", "enum": ["critical", "major", "minor", "info"]},
            "title": {"type": "string"},
            "target_location": {"type": "string"},
            "current_content": {"type": "string"},
            "desired_change": {"type": "string"},
            "detail": {"type": "string"},
            "recommendation": {"type": "string"},
        },
        "required": [
            "perspective",
            "priority",
            "action_type",
            "severity",
            "title",
            "target_location",
            "current_content",
            "desired_change",
            "detail",
            "recommendation",
        ],
        "additionalProperties": False,
    }
    coverage_schema = {
        "type": "object",
        "properties": {
            "item": {"type": "string"},
            "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
            "detail": {"type": "string"},
        },
        "required": ["item", "status", "detail"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "agent": {"type": "string"},
            "score": {"type": "integer"},
            "verdict": {"type": "string", "enum": ["충분", "보완 필요", "위험"]},
            "summary": {"type": "string"},
            "development_findings": {"type": "array", "items": finding_schema},
            "qa_findings": {"type": "array", "items": finding_schema},
            "coverage_checks": {"type": "array", "items": coverage_schema},
            "recommended_actions": {"type": "array", "items": {"type": "string"}},
            "evidence_gaps": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "agent",
            "score",
            "verdict",
            "summary",
            "development_findings",
            "qa_findings",
            "coverage_checks",
            "recommended_actions",
            "evidence_gaps",
        ],
        "additionalProperties": False,
    }


def dev_qa_action_check_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_key": {"type": "string"},
                        "status": {"type": "string", "enum": ["resolved", "partial", "open"]},
                        "evidence": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["item_key", "status", "evidence", "note"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "items"],
        "additionalProperties": False,
    }


def dev_qa_review_instructions(topic: str, template_type: str) -> str:
    version_label = "Full 버전" if template_type == "full" else "간소화 버전"
    return f"""
당신은 NC 정책서를 개발/QA 관점에서 검수하는 Development QA Review Agent다.
검수 대상은 "{topic}" 정책서이며 문서 유형은 {version_label}이다.

목표:
- 개발자가 상세 설계와 구현 범위를 이해할 수 있는지 판단한다.
- QA가 정상/예외/제한/회귀 테스트 시나리오를 도출할 수 있는지 판단한다.
- HTML 외형이 아니라 업무 구조, 상태, 프로세스, 기능, 정책 기준의 충분성을 평가한다.

검수 범위:
- NC 정책서는 상세 설계/QA가 참고할 업무 기준 문서다. 시스템 보안 설계서, API 명세서, DB 설계서, 운영 절차서, 법무 검토서가 아니다.
- 보완 요청은 반드시 문서 안의 특정 장, 표, ID, 정책 항목과 직접 연결되어야 한다.
- 문서 범위를 벗어난 일반 보안·인프라·개발 방법론 요구는 finding으로 만들지 않는다.
- 보안·개인정보 관련 지적은 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 권한 판정, 노출 제한, 고객 고지, 이력 저장 기준, 보관 기준처럼 정책서가 결정해야 하는 판단값에 한정한다.
- 암호화 방식, 키 관리, 취약점 점검, 침투 테스트, OWASP, 방화벽, WAF, 네트워크 보안, API 파라미터, DB 컬럼, 로그 수집 구현처럼 상세 설계/운영/보안 산출물에서 다룰 내용은 제외한다.
- 단, 해당 내용이 현재 문서의 정책 항목에 이미 등장했는데 판단값이 불명확한 경우에는 "정책 항목을 구체화"하는 finding으로만 작성한다.

검수 기준:
- 액터 → 유즈케이스 → 상태 → 프로세스 → 기능 → 정책 연결이 끊기지 않아야 한다.
- 사람 액터 유즈케이스는 프로세스로 충분히 분해되어야 한다.
- 상태 전이 이벤트는 상태를 바꾸는 업무 사건이어야 하고, 현재/다음 상태가 상태 목록과 맞으며 추적성은 usecase_ids로 확인되어야 한다.
- 프로세스는 기능과 정책을 참조할 수 있어야 하고, 기능은 세부 기능 구성을 가져야 한다.
- 정책은 기능 설명이 아니라 실제 동작 기준값, 허용/제한 조건, 예외 기준, 고지/이력 기준을 포함해야 한다.
- BSS/연계 시스템의 판정, 상태 반영, 이력 저장, 결과 회신이 누락되면 개발/QA 리스크로 본다.
- QA 관점에서는 테스트 전제, 경계값, 실패/보류/제한 케이스, 회귀 영향이 도출 가능한지 본다.

응답 기준:
- 점수는 0~100점으로 산정한다.
- 개발/QA가 바로 쓸 수 없을 정도의 누락은 critical 또는 major로 표시한다.
- 일반론을 금지한다. "보안을 강화한다", "모니터링이 필요하다", "개인정보 보호를 검토한다"처럼 어느 위치에 무엇을 바꿀지 알 수 없는 항목은 작성하지 않는다.
- 문서에 근거가 없는 내용을 새로 만들어 단정하지 말고 evidence_gaps에 남긴다.
- evidence_gaps는 정책서 본문 안에서 판단값의 근거가 부족한 경우만 쓴다.
- 요구사항 파일, references 폴더, LLM 입력 본문, TRUNCATED 같은 검수 시스템 입력 한계는 문서 보완 항목이나 evidence_gaps로 쓰지 않는다.
- development_findings는 개발 관점, qa_findings는 QA 관점만 담는다.
- 각 finding은 반드시 아래 3가지 유형 중 하나여야 한다.
  1. change: 어디에 있는 어떤 내용을 어떻게 바꿀지.
  2. add: 어디에 어떤 내용을 추가할지.
  3. delete: 어디에 있는 어떤 내용을 삭제할지.
- target_location은 "4. 프로세스 정의 > 프로세스 목록 > PR-XXX-001"처럼 문서 내 위치를 구체적으로 쓴다.
- target_location이 "문서 본문", "전체 문서"처럼 넓으면 안 된다. 문서에서 실제 수정할 장/표/ID/항목명을 지정한다.
- current_content는 change/delete일 때 문서에 있는 현재 내용을 짧게 쓰고, add일 때는 빈 문자열로 둔다.
- desired_change는 실제로 바꿀 문장, 추가할 내용, 삭제 기준을 정책서 문체로 구체적으로 쓴다.
- priority는 P1/P2/P3 중 하나로 쓴다. P1은 개발/QA 진행을 막는 결함, P2는 보완해야 품질이 안정되는 결함, P3는 표현·명확성 개선이다.
- detail은 왜 개발 또는 QA 관점에서 문제가 되는지 설명한다.
- recommendation은 수정 Agent에게 줄 수 있는 실행 지시문으로 쓴다.
- recommended_actions는 finding을 반복하지 말고 우선 처리 순서 요약만 쓴다.
- coverage_checks는 단순 개수 충족으로 pass 처리하지 말고, 개발/QA가 실제로 쓸 수 있는 의미 품질을 기준으로 판단한다.
- 결과는 반드시 지정된 JSON 스키마만 반환한다.
""".strip()


def dev_qa_action_check_instructions(topic: str) -> str:
    return f"""
당신은 NC 정책서 보완 요청 항목이 실제 문서에 반영됐는지 확인하는 Development QA Action Check Agent다.
검수 대상은 "{topic}" 정책서다.

역할:
- 사용자가 선택했던 보완 요청 항목별로 현재 문서에 반영됐는지 판단한다.
- 새 보완 항목을 만들지 않는다.
- 각 항목은 resolved, partial, open 중 하나로만 판정한다.

판정 기준:
- resolved: 요청한 변경/추가/삭제가 문서의 적절한 위치에 반영되어 개발 또는 QA 관점의 문제가 해소됐다.
- partial: 일부는 반영됐지만 위치, 내용, 구체성, 연결성 중 하나가 부족하다.
- open: 요청한 보완이 문서에 확인되지 않거나 반대로 문서 정합성을 해친다.

응답 기준:
- item_key는 입력 item_key를 그대로 반환한다.
- evidence는 문서에서 확인한 근거 또는 미반영 사유를 짧게 쓴다.
- note는 사람이 다음에 확인할 포인트를 쓴다.
- 결과는 반드시 지정된 JSON 스키마만 반환한다.
""".strip()


def dev_qa_review_prompt(
    *,
    file_name: str,
    topic: str,
    template_type: str,
    document_text: str,
    signals: Mapping[str, Any],
) -> str:
    return "\n\n".join(
        [
            "아래 정책서가 개발/QA 관점에서 충분한지 검수해 주세요.",
            "중요: 문서 안에서 실제 수정할 수 있는 정책서 범위의 항목만 finding으로 작성하세요. 일반 보안·인프라·API·DB·운영 절차 요구는 제외하세요.",
            "중요: 입력 텍스트가 일부 축약되어 있거나 외부 요구사항/참고자료 원문이 함께 제공되지 않은 것은 정책서 결함으로 보고하지 마세요.",
            "문서 메타:",
            json.dumps(
                {
                    "file_name": file_name,
                    "topic": topic,
                    "template_type": template_type,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "문서 구조 신호:",
            json.dumps(signals, ensure_ascii=False, indent=2),
            "정책서 본문 텍스트:",
            document_text,
        ]
    )


def dev_qa_action_check_prompt(*, file_name: str, items: List[Mapping[str, Any]], document_text: str) -> str:
    return "\n\n".join(
        [
            "아래 보완 요청 항목들이 현재 정책서에 반영됐는지 확인해 주세요.",
            "문서 파일:",
            file_name,
            "확인할 보완 요청 항목:",
            json.dumps({"items": items}, ensure_ascii=False, indent=2),
            "현재 정책서 본문 텍스트:",
            document_text,
        ]
    )


def extract_dev_qa_signals(document: str) -> Dict[str, Any]:
    text = strip_html(document)
    signals = {
        "history_count_hint": count_heading_near_rows(document, "문서 히스토리"),
        "actor_count": count_unique_ids(document, ["ACT"]),
        "usecase_count": count_unique_ids(document, ["US"]),
        "state_count": count_unique_ids(document, ["ST"]),
        "process_count": count_unique_ids(document, ["PR", "PRC"]),
        "function_count": count_unique_ids(document, ["FN"]),
        "policy_group_count": count_unique_ids(document, ["PG"]),
        "policy_item_count": count_unique_ids(document, ["PI"]),
        "tbd_or_ambiguous_count": count_ambiguous_markers(text),
        "has_mermaid": "mermaid" in document.casefold(),
        "text_length": len(text),
    }
    signals["health_hints"] = {
        "usecase_per_actor": safe_ratio(signals["usecase_count"], signals["actor_count"]),
        "process_per_usecase": safe_ratio(signals["process_count"], signals["usecase_count"]),
        "function_per_process": safe_ratio(signals["function_count"], signals["process_count"]),
        "policy_per_process": safe_ratio(signals["policy_group_count"], signals["process_count"]),
        "policy_item_per_policy": safe_ratio(signals["policy_item_count"], signals["policy_group_count"]),
    }
    return signals


def normalize_dev_qa_review(report: Mapping[str, Any]) -> Dict[str, Any]:
    score = int_or_zero(report.get("score"))
    score = max(0, min(100, score))
    normalized = {
        "agent": str(report.get("agent") or "Development QA Review Agent"),
        "score": score,
        "verdict": normalize_verdict(report.get("verdict"), score),
        "summary": str(report.get("summary") or "개발/QA 관점 검수를 완료했습니다.").strip(),
        "development_findings": normalize_findings(report.get("development_findings"), default_perspective="development"),
        "qa_findings": normalize_findings(report.get("qa_findings"), default_perspective="qa"),
        "coverage_checks": normalize_coverage(report.get("coverage_checks")),
        "recommended_actions": normalize_strings(report.get("recommended_actions")),
        "evidence_gaps": normalize_evidence_gaps(report.get("evidence_gaps")),
    }
    if not normalized["coverage_checks"]:
        normalized["coverage_checks"] = default_coverage_checks()
    return normalized


def normalize_dev_qa_action_check(report: Mapping[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, str]] = []
    for item in report.get("items", []) if isinstance(report.get("items"), list) else []:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "open").strip().casefold()
        if status not in {"resolved", "partial", "open"}:
            status = "open"
        items.append(
            {
                "item_key": str(item.get("item_key") or "").strip(),
                "status": status,
                "evidence": str(item.get("evidence") or "").strip(),
                "note": str(item.get("note") or "").strip(),
            }
        )
    return {
        "summary": str(report.get("summary") or "보완 여부 확인을 완료했습니다.").strip(),
        "items": [item for item in items if item["item_key"]],
    }


def save_dev_qa_review_report(report: Mapping[str, Any], *, reports_dir: Path, file_name: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{file_name}_dev_qa_review.json"
    payload = dict(report)
    payload["created_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def normalize_findings(value: Any, *, default_perspective: str) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    findings: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity") or "info").strip().casefold()
        if severity not in {"critical", "major", "minor", "info"}:
            severity = "info"
        perspective = str(item.get("perspective") or "").strip().casefold()
        if perspective not in {"development", "qa"}:
            perspective = default_perspective
        priority = str(item.get("priority") or "").strip().upper()
        if priority not in {"P1", "P2", "P3"}:
            priority = priority_from_severity(severity)
        action_type = str(item.get("action_type") or "").strip().casefold()
        if action_type not in {"change", "add", "delete"}:
            action_type = "change"
        normalized = {
            "perspective": perspective,
            "priority": priority,
            "action_type": action_type,
            "severity": severity,
            "title": str(item.get("title") or "검토 항목").strip(),
            "target_location": str(item.get("target_location") or "문서 본문").strip(),
            "current_content": str(item.get("current_content") or "").strip(),
            "desired_change": str(item.get("desired_change") or item.get("recommendation") or "").strip(),
            "detail": str(item.get("detail") or "").strip(),
            "recommendation": str(item.get("recommendation") or "").strip(),
        }
        if is_out_of_scope_dev_qa_finding(normalized):
            continue
        findings.append(normalized)
    return findings


def is_out_of_scope_dev_qa_finding(item: Mapping[str, str]) -> bool:
    text = " ".join(str(item.get(key, "")) for key in ("title", "target_location", "current_content", "desired_change", "detail", "recommendation"))
    target = str(item.get("target_location", "")).strip()
    normalized_text = text.casefold()
    broad_target = target in {"문서 본문", "전체 문서", "문서 전체", "전반", "전체"} or "문서 전반" in target
    has_specific_anchor = bool(re.search(r"\b(?:ACT|US|ST|PR|PRC|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+\b", text, flags=re.IGNORECASE))
    has_section_anchor = any(marker in target for marker in ("개요", "용어", "액터", "유즈케이스", "상태", "프로세스", "기능", "정책", "점검"))
    if broad_target and not has_specific_anchor and not has_section_anchor:
        return True

    out_of_scope_security_terms = (
        "암호화",
        "키 관리",
        "키관리",
        "owasp",
        "침투 테스트",
        "취약점",
        "방화벽",
        "waf",
        "tls",
        "ssl",
        "네트워크 보안",
        "보안 패치",
        "시큐어 코딩",
        "api 보안",
        "db 보안",
        "인프라 보안",
    )
    policy_scope_security_terms = (
        "인증",
        "본인확인",
        "권한",
        "동의",
        "노출 제한",
        "고지",
        "이력",
        "보관",
        "상태",
        "정책 항목",
        "허용",
        "제한",
        "예외",
        "기준값",
        "유효시간",
        "가능 횟수",
    )
    mentions_out_of_scope_security = any(term in normalized_text for term in out_of_scope_security_terms)
    mentions_policy_scope = any(term in normalized_text for term in policy_scope_security_terms)
    if mentions_out_of_scope_security and not mentions_policy_scope:
        return True

    generic_only_patterns = (
        "보안을 강화",
        "개인정보 보호를 강화",
        "모니터링을 강화",
        "관리 체계를 수립",
        "운영 절차를 수립",
        "보안 정책을 수립",
    )
    if broad_target and any(pattern in normalized_text for pattern in generic_only_patterns):
        return True
    return False


def priority_from_severity(severity: str) -> str:
    if severity in {"critical", "major"}:
        return "P1"
    if severity == "minor":
        return "P2"
    return "P3"


def normalize_coverage(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    checks: List[Dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "warn").strip().casefold()
        if status not in {"pass", "warn", "fail"}:
            status = "warn"
        checks.append(
            {
                "item": str(item.get("item") or "점검 항목").strip(),
                "status": status,
                "detail": str(item.get("detail") or "").strip(),
            }
        )
    return checks


def default_coverage_checks() -> List[Dict[str, str]]:
    return [
        {"item": "구조 연결성", "status": "warn", "detail": "LLM 응답에 세부 점검 결과가 없어 추가 확인이 필요합니다."},
        {"item": "정책 구체성", "status": "warn", "detail": "정책값과 예외 기준의 충분성을 사람이 확인해야 합니다."},
    ]


def normalize_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_evidence_gaps(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    gaps: List[str] = []
    for item in value:
        text = str(item).strip()
        if not text or is_meta_review_limitation(text):
            continue
        gaps.append(text)
    return gaps


def is_meta_review_limitation(text: str) -> bool:
    normalized = text.casefold()
    meta_patterns = (
        "truncated",
        "입력 본문",
        "본문이 잘려",
        "제공 본문",
        "원문이 제공",
        "요구사항 통합 list",
        "requirements",
        "references 폴더",
        "참고자료 원문",
        "검수 입력",
    )
    return any(pattern in normalized for pattern in meta_patterns)


def normalize_verdict(value: Any, score: int) -> str:
    text = str(value or "").strip()
    if text in {"충분", "보완 필요", "위험"}:
        return text
    if score >= 90:
        return "충분"
    if score >= 70:
        return "보완 필요"
    return "위험"


def int_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def strip_html(document: str) -> str:
    text = re.sub(r"<style\b.*?</style>", " ", document, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def count_unique_ids(document: str, prefixes: List[str]) -> int:
    values: set[str] = set()
    for prefix in prefixes:
        escaped = re.escape(prefix)
        pattern = re.compile(rf"(?:^|[^A-Z0-9])({escaped}-[A-Z0-9]+-[A-Z0-9-]+)", re.IGNORECASE)
        for match in pattern.finditer(document):
            values.add(match.group(1).upper().strip())
    return len(values)


def count_ambiguous_markers(text: str) -> int:
    markers = ("TBD", "추후 협의", "검토 필요", "정책에 따라", "가능하도록 한다", "관련 부서 확인")
    lowered = text.casefold()
    return sum(lowered.count(marker.casefold()) for marker in markers)


def count_heading_near_rows(document: str, heading: str) -> int:
    index = document.find(heading)
    if index < 0:
        return 0
    window = document[index : index + 6000]
    return len(re.findall(r"<tr\b", window, flags=re.IGNORECASE))


def safe_ratio(numerator: Any, denominator: Any) -> float:
    top = int_or_zero(numerator)
    bottom = int_or_zero(denominator)
    if top <= 0 or bottom <= 0:
        return 0.0
    return round(top / bottom, 2)
