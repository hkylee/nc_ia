import unittest

from src.policy_inspector import check_process_responsibility_boundaries


class ProcessInspectorRulesTest(unittest.TestCase):
    def test_ai_final_route_decision_requires_channel_or_bss_owner(self):
        findings = check_process_responsibility_boundaries(
            [{"id": "PR-SRCH-001", "description": "AI 검색 엔진이 최종 노출 경로를 결정한다."}],
            [{"id": "ACT-SRCH-003", "name": "AI 검색 엔진"}],
        )

        self.assertEqual(1, len(findings))
        self.assertEqual("AI 시스템 최종 분기 책임 과다", findings[0].title)
        self.assertEqual("current_chapter", findings[0].fix_owner)

    def test_ai_candidate_generation_with_channel_decision_is_allowed(self):
        findings = check_process_responsibility_boundaries(
            [{"id": "PR-SRCH-002", "description": "AI 검색 엔진은 후보를 생성하고 채널 업무 시스템이 노출 경로를 확정한다."}],
            [{"id": "ACT-SRCH-003", "name": "AI 검색 엔진"}],
        )

        self.assertEqual([], findings)


if __name__ == "__main__":
    unittest.main()
