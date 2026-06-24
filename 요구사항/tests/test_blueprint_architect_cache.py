import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.blueprint_architect import build_architecture_contract, enhance_architecture_contract_with_llm


class CountingClient:
    enabled = True
    forced = True
    model = "gpt-5.5"
    reasoning_effort = "high"

    def __init__(self):
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        return {"summary": "LLM이 계층 기준을 보강했습니다."}


def test_blueprint_architect_llm_result_is_cached_by_signature():
    ctx = SimpleNamespace(topic="통합 알림", topic_slug="통합알림", business_code="NOVA", template_type="simple")
    blueprint = sample_blueprint()
    learning = sample_learning()
    contract = build_architecture_contract(ctx=ctx, authoring_blueprint=blueprint, learning=learning)
    client = CountingClient()

    with tempfile.TemporaryDirectory() as temp_dir, patch(
        "src.blueprint_architect.BLUEPRINT_CACHE_DIR",
        Path(temp_dir),
    ):
        first = enhance_architecture_contract_with_llm(
            ctx=ctx,
            authoring_blueprint=blueprint,
            learning=learning,
            contract=contract,
            llm_client=client,
        )
        second = enhance_architecture_contract_with_llm(
            ctx=ctx,
            authoring_blueprint=blueprint,
            learning=learning,
            contract=contract,
            llm_client=client,
        )

    assert client.calls == 1
    assert first["llm_cache_hit"] is False
    assert second["llm_cache_hit"] is True
    assert second["summary"] == "LLM이 계층 기준을 보강했습니다."


def sample_learning():
    return {
        "customer_tasks": ["고객이 알림을 확인한다."],
        "bss_implications": ["BSS 알림 대상 여부를 판정한다."],
        "policy_risks": ["알림 노출 채널을 정책으로 분리한다."],
        "chapter_focus": {"process": "유즈케이스별 절차", "policies": "동작값"},
    }


def sample_blueprint():
    return {
        "meta": {
            "topic": "통합 알림",
            "source_fingerprint": "sample-fp",
            "requirements_count": 1,
            "references_count": 1,
        },
        "analysis_signals": {
            "customer_tasks": ["통합 알림을 확인한다."],
            "bss_touchpoints": ["알림 대상 여부를 판정한다."],
            "policy_decision_points": ["알림 노출 채널을 판단한다."],
        },
        "coverage_matrix": [
            {"requirement_id": "REQ-001", "target_stages": ["overview", "usecases", "process", "functions", "policies"]}
        ],
        "chapter_blueprints": [
            {
                "stage": stage,
                "focus": f"{stage} focus",
                "must_cover": ["필수 기준"],
                "target_requirement_ids": ["REQ-001"],
                "evidence_ids": ["REQ-001"],
                "analysis_focus": {"customer_tasks": ["통합 알림을 확인한다."]},
            }
            for stage in ("overview", "usecases", "state", "process", "functions", "policies")
        ],
        "evidence_gaps": [],
    }
