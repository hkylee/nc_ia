import unittest

from src.chapter_agents import build_function_detail_rows
from src.renderer import render_policy_html
from src.validator import validate_policy_spec, validate_stage_critical


def full_spec():
    return {
        "meta": {
            "topic": "회원 가입/탈퇴",
            "topic_slug": "회원가입탈퇴",
            "business_code": "MBR",
            "module_id": "PM-27",
            "document_id": "POL-MBR",
            "document_type": "Full 버전",
            "status": "작성중",
            "version": "v0.1",
            "author": "tester",
            "date": "2026-05-02",
            "template_type": "full",
            "authoring_basis": "Full 상세 테스트 fixture 기준으로 작성했다.",
        },
        "history": [{"version": "v0.1", "change": "초안", "date": "2026-05-02", "author": "tester"}],
        "overview": {"scope": ["회원 가입/탈퇴 업무"], "principles": [{"name": "고객 완결", "description": "고객이 업무를 끝낼 수 있게 한다."}]},
        "terms": [{"id": "TM-MBR-001", "name": "회원 상태", "description": "회원 업무 가능 여부를 판단하는 상태 값이다."}],
        "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "회원 업무를 요청하고 결과를 확인하는 주체"}],
        "usecases": [{"id": "US-MBR-CS-001", "actor": "고객", "name": "회원 가입", "description": "고객이 가입을 완료한다.", "process_target": "Y"}],
        "states": [{"id": "ST-MBR-001", "name": "가입 진행 중", "description": "가입 처리가 진행되는 상태", "next_action": "조건을 확인한다."}],
        "state_transitions": [{"usecase_ids": ["US-MBR-CS-001"], "current_state": "가입 진행 중", "event": "회원 가입", "next_state": "가입 진행 중", "criteria": "가입 조건 확인이 완료되면 상태를 유지하고 다음 절차로 이동한다."}],
        "processes": [
            {
                "id": "PR-MBR-CS-001-01",
                "usecase_id": "US-MBR-CS-001",
                "name": "가입 조건 확인",
                "description": "고객 상태와 가입 가능 조건을 확인한다.",
                "related_functions": ["FN-MBR-JOIN-001 가입 조건 확인"],
                "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
            }
        ],
        "process_details": [
            {
                "process_id": "PR-MBR-CS-001-01",
                "entry_condition": "고객이 회원 가입을 시작하고 기본 식별 정보가 확인된 경우 진입한다.",
                "exit_condition": "가입 가능 여부가 허용, 제한, 보류 중 하나로 확정되면 종료한다.",
                "previous_processes": ["업무 진입 조건 충족"],
                "next_processes": ["결과 안내 또는 후속 업무 연결"],
                "related_functions": ["FN-MBR-JOIN-001 가입 조건 확인"],
                "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
            }
        ],
        "functions": [
            {
                "id": "FN-MBR-JOIN-001",
                "process_id": "PR-MBR-CS-001-01",
                "process_ids": ["PR-MBR-CS-001-01"],
                "name": "가입 조건 확인",
                "description": "회원 상태와 가입 제한 여부를 조회해 가입 가능 결과를 만든다.",
                "details": ["회원 상태 조회", "가입 제한 확인", "결과 생성"],
            }
        ],
        "function_details": [
            {
                "function_id": "FN-MBR-JOIN-001",
                "input_information": ["회원 상태 조회 결과", "가입 제한 기준"],
                "processing_logic": [
                    "(상태) 가입 조건 확인 요청 → (액션) 회원 상태와 가입 제한 기준 조회 → (결과) 가입 가능 여부 반환",
                    "(상태) 제한 조건 존재 → (액션) 제한 사유와 선행 조치 확인 → (결과) 가입 진행 제한",
                    "(상태) 가입 가능 상태 → (액션) 다음 가입 단계 허용 → (결과) 가입 입력 단계 진입",
                ],
                "sub_functions": ["회원 상태 조회", "가입 제한 확인", "결과 생성"],
                "output_information": ["가입 가능 여부", "제한 사유"],
                "failure_exception_cases": ["BSS 응답 지연 시 보류로 반환한다."],
                "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
            }
        ],
        "policy_groups": [
            {
                "id": "PG-MBR-JOIN-001",
                "name": "가입 가능 여부 정책",
                "description": "가입 허용과 제한 기준을 정의한다.",
                "items": ["가입 제한"],
            }
        ],
        "policy_details": [{"id": "PI-MBR-JOIN-001-01", "policy_id": "PG-MBR-JOIN-001", "name": "가입 제한", "content": "제한 상태 고객은 가입을 허용하지 않고 제한 사유를 안내한다."}],
        "final_check": ["프로세스 상세과 기능 상세이 모두 작성되었는지 확인한다."],
    }


class FullDetailAgentOutputTest(unittest.TestCase):
    def test_full_renderer_uses_agent_written_process_and_function_details(self):
        html = render_policy_html(full_spec(), "<style></style>", "full", "full")

        self.assertIn("고객이 회원 가입을 시작하고 기본 식별 정보가 확인된 경우 진입한다.", html)
        self.assertIn("회원 상태 조회 결과", html)
        self.assertIn("실패/예외 케이스", html)

    def test_full_validator_requires_process_and_function_details(self):
        spec = full_spec()
        spec["process_details"] = []

        result = validate_stage_critical(spec, "MBR", "09_process_detail")

        self.assertFalse(result.ok)
        self.assertTrue(any("프로세스 상세" in error for error in result.errors))

    def test_full_policy_spec_accepts_completed_details(self):
        result = validate_policy_spec(full_spec(), "MBR")

        self.assertTrue(result.ok, result.errors)

    def test_full_function_processing_logic_requires_state_action_result(self):
        spec = full_spec()
        spec["function_details"][0]["processing_logic"] = [
            "(정상) 회원 상태를 확인해 가입 가능 여부를 판정한다.",
            "(분기) 제한 조건이 있으면 제한 사유를 반환한다.",
            "(예외) BSS 응답 지연 시 보류로 반환한다.",
        ]

        result = validate_policy_spec(spec, "MBR")

        self.assertFalse(result.ok)
        self.assertTrue(any("상태) ... → (액션) ... → (결과)" in error for error in result.errors))

    def test_policy_group_items_must_match_policy_detail_names(self):
        spec = full_spec()
        spec["policy_groups"][0]["items"] = ["가입 기준"]

        result = validate_policy_spec(spec, "MBR")

        self.assertFalse(result.ok)
        self.assertTrue(any("정책 목록 items" in error for error in result.errors))

    def test_full_process_detail_requires_function_id_and_name_reference(self):
        spec = full_spec()
        spec["process_details"][0]["related_functions"] = ["가입 조건 확인"]

        result = validate_policy_spec(spec, "MBR")

        self.assertFalse(result.ok)
        self.assertTrue(any("관련 기능은 ID와 명칭" in error for error in result.errors))

    def test_full_function_detail_requires_policy_id_and_name_reference(self):
        spec = full_spec()
        spec["function_details"][0]["related_policies"] = ["PG-MBR-JOIN-001 잘못된 정책명"]

        result = validate_policy_spec(spec, "MBR")

        self.assertFalse(result.ok)
        self.assertTrue(any("관련 정책 명칭이 ID와 일치" in error for error in result.errors))

    def test_renderer_reuses_function_under_multiple_processes(self):
        spec = full_spec()
        spec["processes"].append(
            {
                "id": "PR-MBR-CS-001-02",
                "usecase_id": "US-MBR-CS-001",
                "name": "가입 결과 안내",
                "description": "가입 결과를 고객에게 안내한다.",
                "related_functions": [],
                "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
            }
        )
        spec["functions"][0]["process_ids"] = ["PR-MBR-CS-001-01", "PR-MBR-CS-001-02"]

        html = render_policy_html(spec, "<style></style>", "simple", "08_functions")

        self.assertIn("1) 가입 조건 확인 (PR-MBR-CS-001-01)", html)
        self.assertIn("2) 가입 결과 안내 (PR-MBR-CS-001-02)", html)
        self.assertEqual(2, html.count('<td class="mono">FN-MBR-JOIN-001</td>'))

    def test_full_function_detail_fallback_varies_outputs_and_exceptions(self):
        spec = full_spec()
        spec["processes"].extend(
            [
                {
                    "id": "PR-MBR-CS-001-02",
                    "usecase_id": "US-MBR-CS-001",
                    "name": "가입 가능 여부 확정",
                    "description": "가입 가능 여부를 확정한다.",
                    "related_functions": ["FN-MBR-JOIN-002 가입 가능 여부 확정"],
                    "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
                },
                {
                    "id": "PR-MBR-CS-001-03",
                    "usecase_id": "US-MBR-CS-001",
                    "name": "가입 결과 안내",
                    "description": "가입 결과를 안내한다.",
                    "related_functions": ["FN-MBR-JOIN-003 가입 결과 안내"],
                    "related_policies": ["PG-MBR-JOIN-001 가입 가능 여부 정책"],
                },
            ]
        )
        spec["functions"].extend(
            [
                {
                    "id": "FN-MBR-JOIN-002",
                    "process_id": "PR-MBR-CS-001-02",
                    "process_ids": ["PR-MBR-CS-001-02"],
                    "name": "가입 가능 여부 확정",
                    "description": "가입 가능 여부를 확정한다.",
                    "details": ["조건 판정", "상태 반영", "결과 저장"],
                },
                {
                    "id": "FN-MBR-JOIN-003",
                    "process_id": "PR-MBR-CS-001-03",
                    "process_ids": ["PR-MBR-CS-001-03"],
                    "name": "가입 결과 안내",
                    "description": "가입 결과를 안내한다.",
                    "details": ["안내 구성", "고지 발송", "이력 저장"],
                },
            ]
        )

        rows = build_function_detail_rows(spec)

        outputs = {tuple(row["output_information"]) for row in rows}
        exceptions = {tuple(row["failure_exception_cases"]) for row in rows}
        self.assertEqual(len(rows), len(outputs))
        self.assertEqual(len(rows), len(exceptions))


if __name__ == "__main__":
    unittest.main()
