"""Rules for applying manual authoring insights safely.

Manual insights often start from one policy topic.  This module keeps writers,
inspectors, and blueprint agents from promoting topic-specific observations into
global rules unless the current requirements and topic context justify it.
"""

from __future__ import annotations


INSIGHT_APPLICABILITY_LEVELS: tuple[tuple[str, str], ...] = (
    (
        "COMMON",
        "모든 정책서에 적용 가능한 계위, 연결, 품질, 렌더링, 추적성 규칙이다. AGENTS.md, Validator, Inspector, Mock 규칙으로 승격할 수 있다.",
    ),
    (
        "TOPIC",
        "특정 PM/주제에서 발견한 업무 경계 또는 판단축이다. 현재 주제, 요구사항, TK, 첨부자료가 같은 맥락일 때만 적용한다.",
    ),
    (
        "PATTERN",
        "다른 주제에도 유사하게 참고할 수 있는 작성 패턴이다. 그대로 복사하지 말고 현재 주제의 요구사항 언어로 재구성한다.",
    ),
    (
        "DO_NOT_GENERALIZE",
        "특정 주제 경계, 수치, 업무 이관 판단처럼 다른 정책서에 강제하면 오염되는 내용이다. 공통 prompt, mock 템플릿, validator로 승격하지 않는다.",
    ),
)


def insight_applicability_for_prompt() -> str:
    """Return a compact prompt block shared by LLM agents."""
    levels = "\n".join(f"- [{key}] {description}" for key, description in INSIGHT_APPLICABILITY_LEVELS)
    return (
        "수동 작성 인사이트 적용 기준:\n"
        f"{levels}\n"
        "- reports/manual_authoring/manual_authoring_agent_insights.md의 PM-XX 섹션은 기본적으로 [TOPIC]이다.\n"
        "- 상태 전이 criteria 필수, 복합 액터명 금지, 순수 ID 연결, 요구사항 원문 복사 금지처럼 주제와 무관한 구조 문제만 [COMMON]으로 본다.\n"
        "- 특정 주제에서 나온 업무 경계, 예: 환불 산정 범위, 선물 발신/수신 구조, 청구·수납 상태 분리 등은 현재 주제 근거가 맞을 때만 적용한다.\n"
        "- 인사이트를 적용할 때는 현재 주제의 상세 요구사항명/설명, TK, 첨부자료, 승인된 Blueprint와 충돌하지 않는지 먼저 확인한다.\n"
        "- 주제별 인사이트를 근거 없이 일반화해 액터, 유즈케이스, 상태, 프로세스, 기능, 정책을 추가하지 않는다."
    )


def insight_applicability_summary() -> dict:
    """Serializable form for context packs or tests."""
    return {
        "levels": [{"id": key, "description": description} for key, description in INSIGHT_APPLICABILITY_LEVELS],
        "default_rule": "PM-XX 섹션은 기본적으로 TOPIC이며, 공통 구조 결함만 COMMON으로 승격한다.",
        "generalization_guard": "현재 주제 요구사항, TK, 첨부자료, Blueprint와 연결되지 않으면 주제별 인사이트를 적용하지 않는다.",
    }
