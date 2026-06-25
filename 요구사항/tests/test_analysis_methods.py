import unittest
from types import SimpleNamespace

from src.analysis_methods import method_guard_for_inspector, method_knowledge_for_agent, method_knowledge_for_learning
from src.chapter_agents import (
    ActorsAgent,
    AgentRuntime,
    PoliciesAgent,
    build_chapter_prompt,
    build_learning_prompt,
    build_system_instructions,
    policy_derivation_matrix_for_prompt,
)
from src.evidence_store import EvidenceStore


class AnalysisMethodsTest(unittest.TestCase):
    def test_method_knowledge_keeps_template_sample_as_top_guard(self):
        knowledge = method_knowledge_for_agent("usecases")

        priorities = knowledge["template_sample_guard"]["priority"]
        self.assertIn("템플릿/샘플", priorities[0])
        self.assertIn("Primary actor goal", knowledge["method_focus"])
        self.assertTrue(any("절차 단계" in rule for rule in knowledge["rules"]))
        self.assertIn("usecase_vs_process", knowledge["artifact_boundaries"])

    def test_system_instruction_blocks_method_from_changing_template(self):
        runtime = sample_runtime()

        instructions = build_system_instructions(runtime)

        self.assertIn("전문 분석 방법론", instructions)
        self.assertIn("템플릿/샘플", instructions)
        self.assertIn("바꾸는 근거로 쓰지 않는다", instructions)

    def test_chapter_prompt_includes_method_knowledge(self):
        runtime = sample_runtime()
        spec = sample_spec()
        agent = ActorsAgent()
        local_payload = {"actors": []}

        prompt = build_chapter_prompt(agent, spec, local_payload, runtime)

        self.assertIn("전문 분석 방법론 적용 기준", prompt)
        self.assertIn("UML Actor responsibility", prompt)
        self.assertIn("템플릿/샘플", prompt)

    def test_inspector_guard_keeps_method_subordinate_to_sample(self):
        guard = method_guard_for_inspector()

        self.assertIn("템플릿·샘플", guard["rule"])
        self.assertIn("actors", guard["stage_method_focus"])
        self.assertIn("transition_vs_criteria", guard["artifact_boundaries"])

    def test_learning_prompt_contains_document_wide_method_pack(self):
        runtime = sample_runtime()
        learning_pack = method_knowledge_for_learning()

        prompt = build_learning_prompt(runtime.ctx, {"topic": "상품 상세"}, {"common_rules": []})

        self.assertIn("전문 분석 방법론 팩", prompt)
        self.assertIn("상태 전이", prompt)
        self.assertIn("기능", prompt)
        self.assertIn("정책", prompt)
        self.assertIn("artifact_boundaries", learning_pack["document_method"])

    def test_policy_method_defines_operational_values_not_generic_principles(self):
        knowledge = method_knowledge_for_agent("policies")

        self.assertIn("Operational policy values", knowledge["method_focus"])
        joined_rules = " ".join(knowledge["rules"])
        self.assertIn("인증 수단", joined_rules)
        self.assertIn("인증번호 유효시간", joined_rules)
        self.assertIn("저장 항목", joined_rules)
        self.assertIn("추상 원칙", joined_rules)

    def test_policy_agent_instruction_uses_sample_value_style(self):
        instruction = PoliciesAgent().instruction({})
        runtime = sample_runtime()
        system_instruction = build_system_instructions(runtime)

        self.assertIn("기능이 실제로 동작", instruction)
        self.assertIn("프로세스와 기능", instruction)
        self.assertIn("인증 가능 횟수", instruction)
        self.assertIn("유효시간", system_instruction)

    def test_policy_derivation_matrix_starts_from_process_and_function_needs(self):
        spec = sample_spec()
        spec["processes"] = [
            {"id": "PR-PRD-001", "usecase_id": "US-PRD-001", "name": "본인인증", "description": "고객 본인 여부를 확인한다."}
        ]
        spec["functions"] = [
            {
                "id": "FN-PRD-001",
                "process_id": "PR-PRD-001",
                "name": "인증번호 검증",
                "description": "인증번호를 검증하고 실패 횟수를 관리한다.",
                "details": ["인증 수단 확인", "인증번호 유효시간 확인", "인증 실패 횟수 관리"],
            }
        ]

        matrix = policy_derivation_matrix_for_prompt(spec)

        self.assertEqual(matrix[0]["process_id"], "PR-PRD-001")
        axes = " ".join(item["policy_axis"] for item in matrix[0]["required_policy_axes"])
        candidates = " ".join(" ".join(item["item_candidates"]) for item in matrix[0]["required_policy_axes"])
        self.assertIn("인증·동의", axes)
        self.assertIn("인증 가능 횟수", candidates)
        self.assertIn("인증번호 유효시간", candidates)


def sample_runtime():
    ctx = SimpleNamespace(topic="상품 상세", business_code="PRD", template_type="simple")
    return AgentRuntime(
        ctx=ctx,
        target_spec=sample_spec(),
        learning={},
        guideline={"common_rules": []},
        evidence_store=EvidenceStore([]),
        authoring_blueprint={},
        llm_client=SimpleNamespace(model="gpt-5.4", reasoning_effort="medium"),
    )


def sample_spec():
    return {
        "meta": {"topic": "상품 상세", "business_code": "PRD"},
        "overview": {"scope": [], "principles": []},
        "terms": [],
        "actors": [],
        "usecases": [],
        "states": [],
        "state_transitions": [],
        "processes": [],
        "functions": [],
        "policy_groups": [],
        "policy_details": [],
        "trace_matrix": [],
        "evidence_gaps": [],
    }


if __name__ == "__main__":
    unittest.main()
