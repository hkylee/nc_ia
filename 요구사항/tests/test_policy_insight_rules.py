from types import SimpleNamespace

from src.chapter_agents import build_system_instructions
from src.policy_insight_rules import insight_applicability_for_prompt, insight_applicability_summary
from src.policy_inspector import llm_inspection_instructions


def test_insight_applicability_prompt_separates_topic_specific_rules():
    prompt = insight_applicability_for_prompt()

    assert "[COMMON]" in prompt
    assert "[TOPIC]" in prompt
    assert "[PATTERN]" in prompt
    assert "[DO_NOT_GENERALIZE]" in prompt
    assert "PM-XX 섹션은 기본적으로 [TOPIC]" in prompt
    assert "근거 없이 일반화" in prompt


def test_insight_applicability_summary_is_serializable_contract():
    summary = insight_applicability_summary()

    assert summary["default_rule"].startswith("PM-XX")
    assert any(item["id"] == "COMMON" for item in summary["levels"])
    assert any(item["id"] == "DO_NOT_GENERALIZE" for item in summary["levels"])


def test_writer_system_prompt_keeps_insight_generalization_guard():
    runtime = SimpleNamespace(ctx=SimpleNamespace(business_code="TST"), authoring_blueprint={})

    prompt = build_system_instructions(runtime)

    assert "수동 작성 인사이트 적용 기준" in prompt
    assert "주제별 인사이트를 근거 없이 일반화" in prompt


def test_inspector_prompt_keeps_insight_generalization_guard():
    prompt = llm_inspection_instructions("simple", "07_process", "chapter-final", "상품 목록", "")

    assert "수동 작성 인사이트 적용 기준" in prompt
    assert "현재 주제의 상세 요구사항명/설명" in prompt
