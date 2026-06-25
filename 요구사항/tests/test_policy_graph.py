import tempfile
import unittest
from pathlib import Path

from src.policy_graph import (
    build_policy_graph,
    document_node_source_id,
    graph_context_for_spec,
    query_policy_graph_context,
)


class FakeRequirement:
    def __init__(self, detail_id, detail_name, detail_description=""):
        self.source_number = detail_id
        self.depth3 = "테스트"
        self.depth4 = "테스트 정책서"
        self.requirement_id = detail_id.rsplit("-", 1)[0]
        self.detail_id = detail_id
        self.parent_name = detail_name
        self.parent_description = ""
        self.detail_name = detail_name
        self.detail_description = detail_description
        self.requirement_type = "기능"
        self.priority = ""
        self.required = "Y"


def complete_spec():
    return {
        "meta": {
            "topic": "테스트 정책서",
            "topic_display": "테스트 정책서",
            "document_id": "POL-TST",
            "version": "v0.1",
            "template_type": "simple",
        },
        "actors": [{"id": "ACT-TST-CUS-001", "name": "고객", "responsibility": "업무를 시작한다."}],
        "usecases": [
            {
                "id": "US-TST-CUS-001",
                "actor_id": "ACT-TST-CUS-001",
                "actor": "고객",
                "name": "테스트 업무 완료",
                "description": "고객이 테스트 업무를 완료한다.",
                "process_target": "Y",
            }
        ],
        "states": [
            {"id": "ST-TST-001", "name": "접수 전"},
            {"id": "ST-TST-002", "name": "완료"},
        ],
        "state_transitions": [
            {
                "usecase_ids": ["US-TST-CUS-001"],
                "current_state": "접수 전",
                "event": "US-TST-CUS-001",
                "next_state": "완료",
                "criteria": "처리 결과가 성공이면 완료한다.",
            }
        ],
        "processes": [
            {
                "id": "PR-TST-001",
                "usecase_id": "US-TST-CUS-001",
                "name": "조건 확인 및 처리 요청",
                "description": "조건을 확인하고 처리 요청을 접수한다.",
                "related_functions": ["FN-TST-001"],
                "related_policies": ["PG-TST-001"],
            }
        ],
        "functions": [
            {
                "id": "FN-TST-001",
                "process_id": "PR-TST-001",
                "name": "조건 검증 처리",
                "description": "조건을 검증하고 결과를 회신한다.",
                "details": ["조건 조회", "결과 저장"],
            }
        ],
        "policy_groups": [
            {
                "id": "PG-TST-001",
                "name": "처리 허용 정책",
                "description": "처리 가능 조건과 제한 기준을 정의한다.",
            }
        ],
        "policy_details": [
            {
                "id": "PI-TST-001-01",
                "policy_id": "PG-TST-001",
                "name": "허용 조건",
                "content": "고객 상태가 정상이고 인증이 완료된 경우에만 처리한다.",
            }
        ],
        "trace_matrix": [
            {
                "item_type": "usecase",
                "item_id": "US-TST-CUS-001",
                "item_name": "테스트 업무 완료",
                "links": {},
                "evidence_ids": ["REQ-REQ-TST-001-01"],
            }
        ],
    }


class PolicyGraphTest(unittest.TestCase):
    def test_builds_graph_nodes_and_edges_from_policy_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "policy_graph.db"
            result = build_policy_graph(
                complete_spec(),
                requirements=[
                    FakeRequirement("REQ-TST-001-01", "테스트 처리", "고객이 테스트 업무를 처리한다."),
                ],
                graph_db_path=db_path,
            )

            self.assertEqual("", result.error)
            self.assertGreaterEqual(result.node_count, 10)
            self.assertGreaterEqual(result.edge_count, 10)
            context = query_policy_graph_context(topic="테스트 정책서", stage="process", graph_db_path=db_path)
            self.assertTrue(context["available"])
            self.assertEqual(0, context["coverage_gap_count"])
            self.assertEqual(0, context["chain_gap_count"])
            self.assertTrue(context["paths"])

    def test_requirement_coverage_gap_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "policy_graph.db"
            build_policy_graph(
                complete_spec(),
                requirements=[
                    FakeRequirement("REQ-TST-001-01", "테스트 처리", "고객이 테스트 업무를 처리한다."),
                    FakeRequirement("REQ-TST-999-01", "누락 요구사항", "문서 어디에도 연결되지 않은 요구사항이다."),
                ],
                graph_db_path=db_path,
            )

            context = query_policy_graph_context(topic="테스트 정책서", stage="final_check", graph_db_path=db_path)

            self.assertEqual(1, context["coverage_gap_count"])
            self.assertEqual("REQ-TST-999-01", context["coverage_gaps"][0]["requirement_id"])

    def test_trace_matrix_supports_mapped_columns(self):
        spec = complete_spec()
        spec["trace_matrix"] = [
            {
                "requirement_id": "REQ-TST-001-01",
                "mapped_processes": ["PR-TST-001"],
                "mapped_functions": ["FN-TST-001"],
                "mapped_policies": ["PG-TST-001"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "policy_graph.db"
            build_policy_graph(
                spec,
                requirements=[
                    FakeRequirement("REQ-TST-001-01", "테스트 처리", "고객이 테스트 업무를 처리한다."),
                ],
                graph_db_path=db_path,
            )

            context = query_policy_graph_context(topic="테스트 정책서", stage="final_check", graph_db_path=db_path)

            self.assertEqual(0, context["coverage_gap_count"])

    def test_trace_matrix_supports_group_source_and_mapped_to_columns(self):
        spec = complete_spec()
        spec["trace_matrix"] = [
            {
                "source": "REQ-TST-001 테스트 요구 묶음",
                "mapped_to": "PG-TST-001",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "policy_graph.db"
            build_policy_graph(
                spec,
                requirements=[
                    FakeRequirement("REQ-TST-001-01", "테스트 처리 A", "고객이 테스트 업무를 처리한다."),
                    FakeRequirement("REQ-TST-001-02", "테스트 처리 B", "고객이 테스트 업무를 확인한다."),
                ],
                graph_db_path=db_path,
            )

            context = query_policy_graph_context(topic="테스트 정책서", stage="final_check", graph_db_path=db_path)

            self.assertEqual(0, context["coverage_gap_count"])

    def test_document_graph_id_includes_topic_to_prevent_cross_topic_collision(self):
        spec_a = complete_spec()
        spec_b = complete_spec()
        spec_a["meta"]["topic"] = "회원가입탈퇴"
        spec_a["meta"]["topic_display"] = "회원 가입·탈퇴"
        spec_a["meta"]["document_id"] = "POL-MBR"
        spec_b["meta"]["topic"] = "회원정보조회변경"
        spec_b["meta"]["topic_display"] = "회원정보 조회·변경"
        spec_b["meta"]["document_id"] = "POL-MBR"

        self.assertNotEqual(
            document_node_source_id(spec_a, "회원 가입·탈퇴"),
            document_node_source_id(spec_b, "회원정보 조회·변경"),
        )

    def test_chain_gap_is_reported_without_breaking_context_query(self):
        spec = complete_spec()
        spec["processes"][0]["related_functions"] = []
        spec["functions"] = []
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "policy_graph.db"
            context = graph_context_for_spec(
                spec,
                stage="process",
                topic="테스트 정책서",
                requirements=[FakeRequirement("REQ-TST-001-01", "테스트 처리")],
                graph_db_path=db_path,
            )

            self.assertTrue(context["available"])
            self.assertGreaterEqual(context["chain_gap_count"], 1)
            self.assertTrue(any(gap["type"] == "process_without_function" for gap in context["chain_gaps"]))


if __name__ == "__main__":
    unittest.main()
