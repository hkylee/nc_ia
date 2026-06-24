import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.policy_agent import final_inspection_gate_passed, record_unresolved_final_inspector_issues
from src.policy_inspector import (
    InspectionFinding,
    final_inspection_profile,
    inspect_policy_json_spec,
    llm_inspection_instructions,
    llm_inspection_prompt,
)
from llm_client import LLMError


class RecoverableFailingInspectorClient:
    writer_mode = "llm"
    model = "test-model"
    reasoning_effort = "high"
    enabled = True

    def __init__(self):
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        raise LLMError("OpenAI API 연결 실패")


class FinalInspectorModesTest(unittest.TestCase):
    def test_chapter_final_instruction_focuses_on_integration(self):
        instructions = llm_inspection_instructions(
            "통합 알림",
            "simple",
            "full",
            inspection_mode="chapter-final",
        )

        self.assertIn("장별 검수 후 최종 통합 검수 모드", instructions)
        self.assertIn("전체 연결성", instructions)

    def test_final_only_instruction_replaces_chapter_inspection(self):
        instructions = llm_inspection_instructions(
            "통합 알림",
            "simple",
            "full",
            inspection_mode="final-only",
        )

        self.assertIn("최종 검수만 모드", instructions)
        self.assertIn("각 장이 이미 통과됐다고 가정하지 말고", instructions)

    def test_final_prompt_contains_mode_profile(self):
        prompt = llm_inspection_prompt(
            body="<h2>1. 개요</h2>",
            text="1. 개요",
            deterministic_findings=[],
            metrics={},
            template_type="simple",
            scope="full",
            topic="통합 알림",
            inspection_mode="final-only",
        )

        self.assertIn("comprehensive_final_inspector", prompt)
        self.assertIn("장별 Inspector가 잡았어야 할 문제", prompt)

    def test_final_only_gate_blocks_quality_gate_warning(self):
        report = SimpleNamespace(
            score=90,
            findings=[InspectionFinding("warn", "정책 구체성", "정책값 부족", "정책값이 약하다.", "값을 보완한다.")],
            metrics={"score_breakdown": {"gate_blocker_count": 1}},
        )
        ctx = SimpleNamespace(inspection_mode="final-only", inspector_min_score=85)

        self.assertFalse(final_inspection_gate_passed(report, ctx))

    def test_chapter_final_gate_allows_non_error_warning_above_score(self):
        report = SimpleNamespace(
            score=90,
            findings=[InspectionFinding("warn", "정책 구체성", "정책값 부족", "정책값이 약하다.", "값을 보완한다.")],
            metrics={"score_breakdown": {"gate_blocker_count": 1}},
        )
        ctx = SimpleNamespace(inspection_mode="chapter-final", inspector_min_score=85)

        self.assertTrue(final_inspection_gate_passed(report, ctx))

    def test_profile_names_are_distinct(self):
        self.assertEqual(
            "integration_final_inspector",
            final_inspection_profile("chapter-final", "full")["role"],
        )
        self.assertEqual(
            "comprehensive_final_inspector",
            final_inspection_profile("final-only", "full")["role"],
        )

    def test_required_llm_json_inspector_falls_back_after_recoverable_failures(self):
        client = RecoverableFailingInspectorClient()
        spec = {
            "meta": {"template_type": "simple"},
            "actors": [{"id": "ACT-MBR-001", "name": "고객"}],
            "usecases": [],
            "states": [],
            "state_transitions": [],
            "processes": [],
            "functions": [],
            "policy_groups": [],
            "policy_details": [],
        }

        with patch.dict(
            "os.environ",
            {
                "OPENAI_INSPECTOR_TASK_MAX_ATTEMPTS": "2",
                "OPENAI_INSPECTOR_RETRY_BASE_SECONDS": "0",
                "OPENAI_INSPECTOR_RETRY_MAX_SECONDS": "0",
            },
            clear=False,
        ):
            report = inspect_policy_json_spec(
                spec,
                template_type="simple",
                scope="03_actors",
                chapter_key="actors",
                topic="회원가입탈퇴",
                llm_client=client,
                llm_required=True,
            )

        self.assertEqual(2, client.calls)
        self.assertTrue(any(finding.category == "LLM Inspector" for finding in report.findings))
        self.assertEqual("fallback_after_retries", report.metrics["llm_inspector"]["status"])

    def test_unresolved_final_findings_are_recorded_as_open_issues(self):
        spec = {"meta": {}}
        report = SimpleNamespace(
            score=72,
            summary="최종 검수 미통과",
            findings=[
                InspectionFinding("error", "정책 구체성", "정책값 부족", "정책값이 약하다.", "값을 보완한다.")
            ],
        )
        ctx = SimpleNamespace(inspector_min_score=85, inspector_max_loops=3)

        record_unresolved_final_inspector_issues(spec, report, ctx, repair_attempt=3)

        self.assertEqual(1, len(spec["meta"]["open_inspector_issues"]))
        self.assertEqual("final_inspector_needs_review", spec["meta"]["open_inspector_issues"][0]["handoff"])
        self.assertTrue(spec["meta"]["risk_flags"])


if __name__ == "__main__":
    unittest.main()
