import unittest

from src.chain_matrix import build_chain_matrix, summarize_chain_matrix_for_stage


class ChainMatrixTest(unittest.TestCase):
    def test_detects_missing_links_and_reference_errors(self):
        spec = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객"}],
            "usecases": [
                {"id": "US-MBR-001", "name": "가입 신청", "actor": "고객", "process_target": "Y"},
                {"id": "US-MBR-002", "name": "가입 검증", "actor": "없는 액터", "process_target": "N"},
            ],
            "states": [{"id": "ST-MBR-001", "name": "신청 중"}],
            "state_transitions": [
                {"id": "TR-MBR-001", "current_state": "신청 중", "next_state": "없는 상태"}
            ],
            "processes": [
                {
                    "id": "PR-MBR-001",
                    "name": "가입 접수",
                    "usecase_id": "US-MBR-999",
                    "related_functions": ["FN-MBR-999 미존재 기능"],
                    "related_policies": ["PG-MBR-999 미존재 정책"],
                }
            ],
            "functions": [{"id": "FN-MBR-001", "name": "가입 저장", "process_id": "PR-MBR-999"}],
            "policy_groups": [{"id": "PG-MBR-001", "name": "가입 제한 정책"}],
            "policy_details": [{"id": "PI-MBR-001", "policy_id": "PG-MBR-999", "content": "제한 기준"}],
        }

        matrix = build_chain_matrix(spec)
        types = {item["type"] for item in matrix["missing_links"]}

        self.assertIn("usecase_without_process", types)
        self.assertIn("usecase_unknown_actor", types)
        self.assertIn("process_unknown_usecase", types)
        self.assertIn("process_unknown_function_ref", types)
        self.assertIn("process_unknown_policy_group_ref", types)
        self.assertIn("function_unknown_process", types)
        self.assertIn("policy_detail_unknown_group", types)
        self.assertIn("state_transition_unknown_to", types)

    def test_stage_summary_filters_to_relevant_findings(self):
        spec = {
            "actors": [{"id": "ACT-INFO-001", "name": "고객"}],
            "usecases": [{"id": "US-INFO-001", "name": "정보 조회", "actor": "고객", "process_target": "Y"}],
            "processes": [{"id": "PR-INFO-001", "name": "정보 조회 처리", "usecase_id": "US-INFO-001"}],
            "functions": [],
            "policy_groups": [],
            "policy_details": [],
        }

        matrix = build_chain_matrix(spec)
        function_summary = summarize_chain_matrix_for_stage(matrix, "functions")
        policy_summary = summarize_chain_matrix_for_stage(matrix, "policies")

        self.assertEqual(["process_without_function"], [item["type"] for item in function_summary["missing_links"]])
        self.assertIn("process_without_policy_group", [item["type"] for item in policy_summary["missing_links"]])

    def test_multi_process_function_links_are_counted_for_each_process(self):
        spec = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객"}],
            "usecases": [{"id": "US-MBR-001", "name": "가입", "actor": "고객", "process_target": "Y"}],
            "processes": [
                {"id": "PR-MBR-001", "name": "본인인증", "usecase_id": "US-MBR-001"},
                {"id": "PR-MBR-002", "name": "탈퇴 인증", "usecase_id": "US-MBR-001"},
            ],
            "functions": [
                {
                    "id": "FN-MBR-COM-001",
                    "name": "본인인증 처리",
                    "process_id": "PR-MBR-001",
                    "process_ids": ["PR-MBR-001", "PR-MBR-002"],
                }
            ],
            "policy_groups": [],
            "policy_details": [],
        }

        matrix = build_chain_matrix(spec)
        rows = {row["process_id"]: row for row in matrix["rows"]}

        self.assertEqual(["FN-MBR-COM-001"], rows["PR-MBR-001"]["function_ids"])
        self.assertEqual(["FN-MBR-COM-001"], rows["PR-MBR-002"]["function_ids"])


if __name__ == "__main__":
    unittest.main()
