"""Shared policy-detail style anchor rules.

The old-project PDFs are useful as a writing style signal, not as policy facts.
Keep this module small so writers, inspectors, revision agents, and mock mode can
share the same judgment axes without copying legacy project values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


STYLE_ANCHOR_REFERENCE_PATH = Path(
    "input/references/스타일앵커_예전프로젝트_정책상세화패턴_20260510.md"
)

STYLE_RELEVANT_STAGES = {
    "state",
    "process",
    "process_detail",
    "functions",
    "function_detail",
    "policies",
    "terms_refinement",
    "final_check",
    "full",
}

POLICY_DETAIL_STYLE_AXES: tuple[str, ...] = (
    "유형별 적용 기준",
    "가능/불가/제한 조건",
    "채널/주체/권한 기준",
    "업무 시점과 상태 기준",
    "사용/인증/혜택 소진 여부",
    "자동 판정과 수동 조정 경계",
    "외부·제휴·BSS 회신 기준",
    "고객 고지와 이력 저장 기준",
)

POLICY_DETAIL_STYLE_DO_NOT_COPY: tuple[str, ...] = (
    "예전 프로젝트의 상품명, 채널명, 조직명, 화면명, O/X 표기",
    "예전 프로젝트의 실제 숫자·기간·금액·제한값",
    "현재 요구사항·첨부자료·TK와 연결되지 않는 업무 범위",
)

POLICY_DETAIL_STYLE_MOCK_AXES: tuple[tuple[str, str, str], ...] = (
    (
        "유형별 적용 기준",
        "업무 유형은 신규, 변경, 취소, 복구, 운영 보정처럼 처리 결과가 달라지는 경우에만 구분한다. 같은 결과로 닫히는 유형은 하나의 기준으로 통합한다.",
        "유형",
    ),
    (
        "채널별 처리 기준",
        "앱·웹에서 고객이 직접 완료 가능한 업무는 셀프 처리 경로를 우선한다. 상담 또는 운영 처리는 권한 불명확, 고객 피해 가능성, 연계 실패가 확인된 경우로 제한한다.",
        "채널",
    ),
    (
        "주체별 권한 기준",
        "고객, 법정대리인, 대리인, 운영자는 본인확인, 대리 권한, 승인 책임이 확인된 범위에서만 처리할 수 있다. 권한이 없으면 제한 사유와 대체 경로를 안내한다.",
        "권한",
    ),
    (
        "사용·소진 여부 기준",
        "혜택, 쿠폰, 포인트, 권한, 인증 결과는 미사용, 사용 중, 사용 완료, 만료, 회수 필요 상태로 구분한다. 이미 소진된 항목은 재사용을 제한하고 이력을 남긴다.",
        "사용",
    ),
    (
        "자동·수동 조정 기준",
        "정책값과 증적 이력으로 자동 판정 가능한 업무는 자동 처리한다. 고객 피해 가능성, 원장 불일치, 연계 결과 충돌이 있으면 운영 확인 후 수동 조정한다.",
        "조정",
    ),
)


def policy_style_anchor_context(stage_key: str = "") -> dict:
    """Return a compact, serializable style anchor context."""
    normalized = normalize_stage_key(stage_key)
    if normalized and normalized not in STYLE_RELEVANT_STAGES:
        return {}
    return {
        "source": str(STYLE_ANCHOR_REFERENCE_PATH),
        "usage": "작성 스타일 참고용. 현재 요구사항, 첨부자료, TK, 샘플/템플릿보다 우선하지 않는다.",
        "axes": list(POLICY_DETAIL_STYLE_AXES),
        "do_not_copy": list(POLICY_DETAIL_STYLE_DO_NOT_COPY),
    }


def policy_style_anchor_for_prompt(stage_key: str = "") -> str:
    """Prompt block shared by writers, inspectors, and revision agents."""
    context = policy_style_anchor_context(stage_key)
    if not context:
        return ""
    axes = "\n".join(f"- {axis}" for axis in POLICY_DETAIL_STYLE_AXES)
    forbidden = "\n".join(f"- {item}" for item in POLICY_DETAIL_STYLE_DO_NOT_COPY)
    return (
        "정책 상세화 스타일 앵커:\n"
        "- 예전 프로젝트 문서는 정책을 상세화하는 방식만 참고한다. 정책 사실·수치·상품명은 복사하지 않는다.\n"
        "- 현재 요구사항, 첨부자료, TK, 샘플/템플릿, AGENTS.md와 연결되는 판단축만 사용한다.\n"
        "- 정책 항목은 설명문이 아니라 기능 동작을 통제하는 판단 기준이어야 한다.\n"
        "참고 판단축:\n"
        f"{axes}\n"
        "복사 금지:\n"
        f"{forbidden}"
    )


def policy_style_anchor_questions(stage_key: str = "") -> list[str]:
    normalized = normalize_stage_key(stage_key)
    if normalized and normalized not in {"process", "functions", "policies", "final_check"}:
        return []
    return [
        "이번 주제에서 유형별 적용 기준이 필요한 업무와 통합해도 되는 업무는 무엇인가?",
        "가능/불가/제한 조건, 권한, 상태, 시점, 사용 여부 중 어떤 축이 정책 항목으로 분리되어야 하는가?",
        "자동 판정으로 처리할 수 있는 기준과 운영 확인 또는 수동 조정으로 보내야 하는 기준은 무엇인가?",
        "BSS·외부·제휴 회신 결과, 고객 고지, 이력 저장 기준 중 누락되면 개발/QA가 막히는 항목은 무엇인가?",
    ]


def policy_style_anchor_inspection_rule(stage_key: str = "") -> str:
    if not policy_style_anchor_context(stage_key):
        return ""
    return (
        "정책 상세화 스타일 앵커 검수 기준: 정책 항목이 유형, 가능/불가, 권한, 상태/시점, 사용 여부, "
        "자동/수동 조정, BSS·외부 회신, 고지·이력 중 현재 주제에 필요한 판단축을 실제 기준으로 담았는지 본다. "
        "단, 예전 프로젝트 값이나 현재 근거 없는 범위를 요구하지 않는다."
    )


def normalize_stage_key(stage_key: str = "") -> str:
    key = str(stage_key or "").strip().lower()
    aliases: Mapping[str, str] = {
        "06_state": "state",
        "07_process": "process",
        "08_functions": "functions",
        "09_policies": "policies",
        "10_final_check": "final_check",
        "09_terms_refinement": "terms_refinement",
    }
    return aliases.get(key, key)
