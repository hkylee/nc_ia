import unittest

from src.policy_inspector import compact_local_precheck_for_llm, llm_json_inspection_prompt


class StageInspectorCompactionTest(unittest.TestCase):
    def test_stage_json_inspector_pack_truncates_support_context(self):
        spec = {
            "meta": {
                "topic": "AI 검색",
                "authoring_blueprint": {
                    "requirement_cards": [
                        {"id": f"REQ-{index}", "title": "요구사항" * 20, "summary": "상세 설명" * 80}
                        for index in range(20)
                    ],
                },
            },
            "usecases": [
                {
                    "id": f"US-AIS-{index:03d}",
                    "actor": "고객",
                    "name": "검색 업무",
                    "description": "검색 과업 설명" * 50,
                    "process_target": "Y",
                }
                for index in range(40)
            ],
            "processes": [
                {
                    "id": f"PR-AIS-{index:03d}",
                    "usecase_id": "US-AIS-001",
                    "name": "검색 처리",
                    "description": "프로세스 설명" * 50,
                }
                for index in range(40)
            ],
        }

        prompt = llm_json_inspection_prompt(
            spec=spec,
            deterministic_findings=[],
            metrics={},
            template_type="simple",
            scope="07_process",
            chapter_key="process",
            topic="AI 검색",
        )

        self.assertIn("_truncated_items", prompt)
        self.assertIn('"current_chapter"', prompt)
        self.assertLess(len(prompt), 60000)

    def test_final_json_inspector_compacts_local_precheck_for_llm(self):
        precheck = {
            "purpose": "테스트",
            "issues": [{"kind": "issue", "target": f"X-{index}", "reason": "사유" * 20} for index in range(80)],
            "issue_total_count": 80,
            "missing_links": [{"kind": "link", "target": f"Y-{index}", "reason": "누락" * 20} for index in range(90)],
            "missing_link_total_count": 90,
            "chain_matrix": [{"id": f"ROW-{index}", "description": "설명" * 30} for index in range(100)],
            "chain_matrix_stats": {"rows": 100},
            "policy_graph_context": {"paths": [{"id": f"P-{index}", "label": "경로" * 20} for index in range(30)]},
            "orphan_ids": {"functions": [f"FN-{index}" for index in range(30)]},
            "missing_policy_detail_groups": [{"policy_id": f"PG-{index}", "reason": "상세 없음"} for index in range(40)],
        }

        compact = compact_local_precheck_for_llm(precheck, "full")

        self.assertEqual(80, compact["issue_total_count"])
        self.assertEqual(90, compact["missing_link_total_count"])
        self.assertLessEqual(len(compact["issues"]), 40)
        self.assertLessEqual(len(compact["missing_links"]), 40)
        self.assertLessEqual(len(compact["chain_matrix"]), 48)
        self.assertIn("_truncated_items", str(compact["policy_graph_context"]))


if __name__ == "__main__":
    unittest.main()
