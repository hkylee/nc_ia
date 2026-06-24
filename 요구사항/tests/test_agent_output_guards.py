import os
import unittest
from types import SimpleNamespace

from src.chapter_agents import (
    AgentRuntime,
    ActorsAgent,
    FunctionsAgent,
    PoliciesAgent,
    ProcessAgent,
    StateAgent,
    TermsAgent,
    UsecasesAgent,
    approved_contract_for_prompt,
    build_function_detail_rows,
    chapter_output_schema,
    chunk_payload_for_agent,
    chunk_size,
    ensure_patch_feedback_targets_changed,
    ensure_patch_payload_within_target,
    ensure_usecase_actor_coverage,
    fallback_patch_item_limit,
    normalize_agent_output,
    patch_target_field_contract,
    policy_names_for_process,
    reconcile_process_policy_links,
    refined_terms_from_document,
    requires_scoped_full_revision,
    state_authoring_contract_block,
    state_term_candidates,
    state_usecase_lifecycle_contract_for_prompt,
    target_field_refs_from_path,
)
from llm_client import LLMError
from src.policy_inspector import check_diagram_guide, check_function_guide, check_json_stage_rules, check_process_guide, json_approved_contract
from src.validator import validate_stage_critical, validate_state_transition_integrity


def simple_runtime():
    return SimpleNamespace(ctx=SimpleNamespace(template_type="simple"))


def topic_runtime(topic="통합 알림"):
    return SimpleNamespace(ctx=SimpleNamespace(template_type="simple", topic=topic), target_spec={})


class FailingUsecaseLLMClient:
    writer_mode = "llm"
    model = "test-model"
    reasoning_effort = "medium"
    enabled = True

    def __init__(self):
        self.calls = 0

    def with_overrides(self, **kwargs):
        return self

    def generate_json(self, **kwargs):
        self.calls += 1
        return {
            "usecases": [
                {
                    "id": "US-PAI-BAD-001",
                    "actor": "고객",
                    "name": "본인인증",
                    "description": "고객이 본인인증을 수행한다.",
                    "process_target": "Y",
                }
            ]
        }


class EmptyEvidenceStore:
    items = []

    def select(self, **kwargs):
        return []

    def summary(self):
        return {}


class RetryAlwaysFailLLMClient:
    writer_mode = "llm"
    model = "test-model"
    reasoning_effort = "medium"
    enabled = True

    def __init__(self):
        self.calls = 0

    def with_overrides(self, **kwargs):
        return self

    def generate_json(self, **kwargs):
        self.calls += 1
        raise LLMError("temporary network timeout")


def state_spec(states):
    return {
        "usecases": [
            {
                "id": "US-GFT-001",
                "actor": "고객",
                "name": "선물 주문",
                "description": "고객이 선물 주문을 완료한다.",
                "process_target": "Y",
            }
        ],
        "states": states,
    }


class AgentOutputGuardsTest(unittest.TestCase):
    def test_terms_rejects_mixed_signup_and_withdrawal_consent_boundary(self):
        payload = {
            "terms": [
                {
                    "id": "TM-MBR-001",
                    "name": "약관 동의",
                    "description": "가입 약관 동의와 탈퇴 최종 확인 및 영향 고지를 함께 판단하는 기준이다.",
                }
            ]
        }

        with self.assertRaises(LLMError):
            TermsAgent().validate_payload({}, simple_runtime(), payload)

    def test_terms_rejects_mixed_withdrawal_block_hold_retention_boundary(self):
        payload = {
            "terms": [
                {
                    "id": "TM-MBR-002",
                    "name": "탈퇴 차단 사유",
                    "description": "탈퇴 요청 전 제한 사유와 탈퇴 보류 및 탈퇴 후 보관 기준을 함께 관리한다.",
                }
            ]
        }

        with self.assertRaises(LLMError):
            TermsAgent().validate_payload({}, simple_runtime(), payload)

    def test_terms_stage_gate_rejects_blank_term_id(self):
        spec = {
            "meta": {"business_code": "MBR"},
            "terms": [{"name": "회원 상태", "description": "회원 업무 가능 여부를 판단하는 상태 값이다."}],
        }

        result = validate_stage_critical(spec, "MBR", "02_terms")

        self.assertFalse(result.ok)
        self.assertIn("Critical Gate: 용어 ID가 비어 있습니다: terms[1]", result.errors)

    def test_terms_refinement_uses_standard_numeric_term_ids(self):
        spec = {
            "meta": {"business_code": "GFT"},
            "terms": [{"id": "TM-GFT-001", "name": "선물 상태", "description": "선물 업무 상태 값이다."}],
            "states": [{"id": "ST-GFT-001", "name": "수락 대기", "description": "수취인 응답을 기다리는 상태이다."}],
        }

        terms = refined_terms_from_document(spec, simple_runtime())

        self.assertTrue(any(term["id"] == "TM-GFT-002" for term in terms))
        self.assertFalse(any("-REF-" in term["id"] for term in terms))

    def test_actor_rejects_customer_status_as_actor(self):
        payload = {"actors": [{"id": "ACT-MBR-001", "name": "로그인 고객", "description": "로그인한 고객"}]}

        with self.assertRaises(LLMError):
            ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_actor_rejects_detailed_internal_operator_actor(self):
        payload = {"actors": [{"id": "ACT-PRD-002", "name": "상품 운영자", "description": "상품 기준을 관리한다."}]}

        with self.assertRaises(LLMError):
            ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_actor_rejects_detailed_system_actor(self):
        payload = {"actors": [{"id": "ACT-AIS-003", "name": "AI 검색 엔진", "description": "검색 후보를 생성한다."}]}

        with self.assertRaises(LLMError):
            ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_actor_allows_consolidated_operator_and_system_actors(self):
        payload = {
            "actors": [
                {"id": "ACT-PDD-001", "name": "고객", "description": "상품 업무를 요청하고 결과를 확인한다."},
                {"id": "ACT-PDD-002", "name": "운영자", "description": "상품 기준과 품질 지표를 관리한다."},
                {"id": "ACT-PDD-003", "name": "채널 업무 시스템", "description": "BSS 판정 결과를 받아 고객에게 안내하고 상태·이력을 반영한다."},
                {"id": "ACT-PDD-004", "name": "상품·BSS 연계 시스템", "description": "상품 기준 정보와 고객 조건 판정 결과를 회신한다."},
            ]
        }

        ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_actor_rejects_channel_system_as_sole_final_decision_owner(self):
        payload = {
            "actors": [
                {
                    "id": "ACT-MBR-002",
                    "name": "채널 업무 시스템",
                    "description": "회원가입 자격을 최종 판정하고 요청 가능 여부를 확정한다.",
                }
            ]
        }

        with self.assertRaises(LLMError):
            ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_actor_allows_channel_system_when_bss_decision_is_delegated(self):
        payload = {
            "actors": [
                {
                    "id": "ACT-MBR-002",
                    "name": "채널 업무 시스템",
                    "description": "BSS 판정 결과를 받아 고객에게 안내하고 상태·이력을 반영한다.",
                }
            ]
        }

        ActorsAgent().validate_payload({}, simple_runtime(), payload)

    def test_chunked_large_chapters_use_wider_chunks(self):
        self.assertEqual(8, chunk_size(FunctionsAgent()))
        self.assertEqual(8, chunk_size(PoliciesAgent()))

    def test_dynamic_chunking_keeps_small_function_payload_together(self):
        payload = {
            "functions": [
                {
                    "id": f"FN-MBR-{index:03d}",
                    "process_id": f"PR-MBR-{index:03d}",
                    "name": f"기능 {index}",
                    "description": "처리한다.",
                    "details": ["조회", "저장"],
                }
                for index in range(1, 10)
            ]
        }

        chunks = chunk_payload_for_agent(FunctionsAgent(), payload)

        self.assertEqual(1, len(chunks))
        self.assertEqual(9, len(chunks[0]["functions"]))

    def test_dynamic_chunking_groups_functions_by_process_when_large(self):
        payload = {
            "functions": [
                {
                    "id": f"FN-MBR-{index:03d}",
                    "process_id": "PR-MBR-001" if index <= 6 else "PR-MBR-002",
                    "name": f"회원 업무 기능 {index}",
                    "description": "고객 상태, 인증 결과, BSS 회신, 후속 고지 기준을 함께 확인하여 처리 결과를 구성한다.",
                    "details": ["상태 조회", "권한 검증", "BSS 결과 반영", "고객 고지", "이력 저장"],
                }
                for index in range(1, 13)
            ]
        }

        chunks = chunk_payload_for_agent(FunctionsAgent(), payload)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            process_ids = {item["process_id"] for item in chunk["functions"]}
            self.assertEqual(1, len(process_ids))

    def test_process_gate_rejects_mechanical_one_to_one_usecase_process_mapping(self):
        spec = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "고객"}],
            "usecases": [
                {
                    "id": f"US-MBR-CUS-{index:03d}",
                    "actor": "고객",
                    "name": f"고객 업무 {index}",
                    "description": "고객이 업무를 완료한다.",
                    "process_target": "Y",
                }
                for index in range(1, 5)
            ],
            "processes": [
                {
                    "id": f"PR-MBR-CUS-{index:03d}",
                    "usecase_id": f"US-MBR-CUS-{index:03d}",
                    "name": f"고객 업무 {index} 처리",
                    "description": "고객 업무를 처리한다.",
                }
                for index in range(1, 5)
            ],
        }

        result = validate_stage_critical(spec, "MBR", scope="process")

        self.assertFalse(result.ok)
        self.assertTrue(any("프로세스 1개씩" in error for error in result.errors))

    def test_usecase_gate_rejects_step_level_process_target(self):
        spec = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "고객"}],
            "usecases": [
                {
                    "id": "US-MBR-AUTH-001",
                    "actor": "고객",
                    "name": "본인확인",
                    "description": "고객이 본인확인을 수행한다.",
                    "process_target": "Y",
                }
            ],
        }

        result = validate_stage_critical(spec, "MBR", scope="usecases")

        self.assertFalse(result.ok)
        self.assertTrue(any("절차 단계" in error for error in result.errors))

    def test_process_gate_rejects_single_process_for_y_usecase(self):
        spec = {
            "meta": {"usecase_diagram": {"lines": ["[고객] → (회원 가입 완료)"]}},
            "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "고객"}],
            "usecases": [
                {
                    "id": "US-MBR-CUS-001",
                    "actor": "고객",
                    "name": "회원 가입 완료",
                    "description": "고객이 회원 가입을 완료한다.",
                    "process_target": "Y",
                }
            ],
            "processes": [
                {
                    "id": "PR-MBR-CUS-001",
                    "usecase_id": "US-MBR-CUS-001",
                    "name": "가입 처리",
                    "description": "회원 가입을 처리한다.",
                }
            ],
        }

        result = validate_stage_critical(spec, "MBR", scope="process")

        self.assertFalse(result.ok)
        self.assertTrue(any("프로세스 1개로만" in error for error in result.errors))

    def test_state_gate_requires_state_impact_system_usecase_linkage(self):
        spec = {
            "actors": [
                {"id": "ACT-DSP-001", "name": "고객", "description": "전시 정보를 확인한다."},
                {"id": "ACT-DSP-002", "name": "BSS/분석 연계 시스템", "description": "고객 조건과 분석 결과를 회신한다."},
            ],
            "usecases": [
                {
                    "id": "US-DSP-CUS-001",
                    "actor": "고객",
                    "name": "개인화 전시 확인",
                    "description": "고객이 개인화 전시 결과를 확인한다.",
                    "process_target": "Y",
                },
                {
                    "id": "US-DSP-BSS-001",
                    "actor": "BSS/분석 연계 시스템",
                    "name": "고객 상태·분석 조건 판정",
                    "description": "BSS와 분석 시스템이 고객 상태, 보유 조건, 노출 가능 여부를 회신한다.",
                    "process_target": "N",
                },
            ],
            "states": [
                {"id": "ST-DSP-001", "name": "노출 대기", "description": "노출 조건 확인 전 상태", "next_action": "고객 조건을 판정한다."},
                {"id": "ST-DSP-002", "name": "노출 가능", "description": "전시 가능한 상태", "next_action": "전시를 표시한다."},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["US-DSP-CUS-001"],
                    "current_state": "노출 대기",
                    "event": "개인화 전시 진입",
                    "next_state": "노출 가능",
                    "criteria": "고객 조건과 노출 가능 여부가 확인되면 전시 가능으로 전환한다.",
                }
            ],
        }

        result = validate_stage_critical(spec, "DSP", scope="state")

        self.assertFalse(result.ok)
        self.assertTrue(any("시스템/BSS 유즈케이스가 상태 전이에 연결되지 않았습니다" in error for error in result.errors))

    def test_process_gate_rejects_overconcentrated_y_usecase(self):
        spec = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "고객"}],
            "usecases": [
                {
                    "id": "US-MBR-CUS-001",
                    "actor": "고객",
                    "name": "회원 이용 여정 관리",
                    "description": "고객이 회원 이용 여정을 관리한다.",
                    "process_target": "Y",
                }
            ],
            "processes": [
                {
                    "id": f"PR-MBR-CUS-{index:03d}",
                    "usecase_id": "US-MBR-CUS-001",
                    "name": f"회원 이용 절차 {index}",
                    "description": "회원 이용 절차를 처리한다.",
                }
                for index in range(1, 9)
            ],
        }

        result = validate_stage_critical(spec, "MBR", scope="process")

        self.assertFalse(result.ok)
        self.assertTrue(any("프로세스가 과도하게 집중" in error for error in result.errors))

    def test_usecase_diagram_gate_requires_actor_association_line(self):
        spec = {
            "meta": {"usecase_diagram": {"lines": ["[고객] → (검색 맥락 기반 상담 응대)"]}},
            "actors": [{"id": "ACT-AIS-001", "name": "상담사", "description": "상담을 처리하는 주체"}],
            "usecases": [
                {
                    "id": "US-AIS-CS-001",
                    "actor": "상담사",
                    "name": "검색 맥락 기반 상담 응대",
                    "description": "상담사가 검색 맥락으로 상담을 완료한다.",
                    "process_target": "Y",
                }
            ],
        }

        result = validate_stage_critical(spec, "AIS", scope="usecase_diagram")

        self.assertFalse(result.ok)
        self.assertTrue(any("같은 관계선" in error for error in result.errors))

    def test_dynamic_policy_chunking_keeps_details_with_group(self):
        payload = {
            "policy_groups": [
                {
                    "id": f"PG-MBR-{index:03d}",
                    "name": f"정책 그룹 {index}",
                    "description": "회원 업무 판단 기준을 정의한다.",
                    "items": [f"항목 {index}"],
                }
                for index in range(1, 7)
            ],
            "policy_details": [
                {
                    "id": f"PI-MBR-{group:03d}-{detail:02d}",
                    "policy_id": f"PG-MBR-{group:03d}",
                    "name": f"정책 항목 {group}-{detail}",
                    "content": "고객 상태, 요청 시점, BSS 판정 결과, 이력 저장 기준을 함께 확인한다.",
                }
                for group in range(1, 7)
                for detail in range(1, 5)
            ],
        }

        chunks = chunk_payload_for_agent(PoliciesAgent(), payload)

        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            group_ids = {item["id"] for item in chunk["policy_groups"]}
            detail_policy_ids = {item["policy_id"] for item in chunk["policy_details"]}
            self.assertTrue(detail_policy_ids.issubset(group_ids))

    def test_chunked_writer_falls_back_per_chunk_instead_of_stopping(self):
        client = RetryAlwaysFailLLMClient()
        previous_attempts = os.environ.get("OPENAI_LLM_TASK_MAX_ATTEMPTS")
        previous_delay = os.environ.get("OPENAI_LLM_TASK_RETRY_BASE_SECONDS")
        os.environ["OPENAI_LLM_TASK_MAX_ATTEMPTS"] = "2"
        os.environ["OPENAI_LLM_TASK_RETRY_BASE_SECONDS"] = "0"
        functions = [
            {
                "id": f"FN-MBR-{index:03d}",
                "process_id": "PR-MBR-001" if index <= 6 else "PR-MBR-002",
                "process_ids": ["PR-MBR-001" if index <= 6 else "PR-MBR-002"],
                "name": f"회원 처리 기능 {index}",
                "description": "고객 상태, 인증 결과, BSS 회신, 후속 고지 기준을 함께 확인하여 처리 결과를 구성한다.",
                "details": [f"상태 조회 {index}", f"권한 검증 {index}", f"이력 저장 {index}"],
            }
            for index in range(1, 13)
        ]
        runtime = AgentRuntime(
            ctx=SimpleNamespace(template_type="simple", topic="회원가입탈퇴", business_code="MBR"),
            target_spec={"functions": functions},
            learning={},
            guideline={},
            evidence_store=EmptyEvidenceStore(),
            authoring_blueprint={},
            llm_client=client,
        )
        spec = {
            "meta": {"topic": "회원가입탈퇴"},
            "processes": [
                {"id": "PR-MBR-001", "name": "가입 처리"},
                {"id": "PR-MBR-002", "name": "탈퇴 처리"},
            ],
        }

        try:
            agent = FunctionsAgent()
            result = agent.write_with_llm_chunks(
                spec,
                runtime,
                feedback=None,
                llm_client=client,
                local_payload={"functions": functions},
                schema=chapter_output_schema(agent),
            )
        finally:
            if previous_attempts is None:
                os.environ.pop("OPENAI_LLM_TASK_MAX_ATTEMPTS", None)
            else:
                os.environ["OPENAI_LLM_TASK_MAX_ATTEMPTS"] = previous_attempts
            if previous_delay is None:
                os.environ.pop("OPENAI_LLM_TASK_RETRY_BASE_SECONDS", None)
            else:
                os.environ["OPENAI_LLM_TASK_RETRY_BASE_SECONDS"] = previous_delay

        self.assertEqual(12, len(result["functions"]))
        self.assertGreaterEqual(len(result["__llm_chunking"]["fallback_chunks"]), 1)
        self.assertEqual(4, client.calls)

    def test_usecase_rejects_truncated_description(self):
        spec = {"actors": [{"name": "고객"}]}
        payload = {
            "usecases": [
                {
                    "id": "US-GFT-001",
                    "actor": "고객",
                    "name": "선물 발송",
                    "description": "고객이 선물 발송 조건을 확인한 후",
                    "process_target": "Y",
                }
            ]
        }

        with self.assertRaises(LLMError):
            UsecasesAgent().validate_payload(spec, simple_runtime(), payload)

    def test_usecase_allows_auth_when_authentication_is_business_goal(self):
        spec = {"actors": [{"name": "고객"}]}
        payload = {
            "usecases": [
                {
                    "id": "US-PAI-001",
                    "actor": "고객",
                    "name": "상품 연동 인증",
                    "description": "고객이 상품 연동 인증을 요청하고 처리 결과를 확인해 상품 이용 조건을 확정한다.",
                    "process_target": "Y",
                }
            ]
        }

        UsecasesAgent().validate_payload(spec, simple_runtime(), payload)

    def test_usecase_allows_ai_named_human_operator(self):
        spec = {"actors": [{"name": "검색/AI 운영자"}]}
        payload = {
            "usecases": [
                {
                    "id": "US-AIS-OPR-001",
                    "actor": "검색/AI 운영자",
                    "name": "검색 기준·AI 품질 운영",
                    "description": "검색/AI 운영자가 검색 기준과 AI 품질 개선 업무를 완료한다.",
                    "process_target": "Y",
                }
            ]
        }

        UsecasesAgent().validate_payload(spec, simple_runtime(), payload)

    def test_usecase_rejects_authentication_step_as_business_goal(self):
        spec = {"actors": [{"name": "고객"}]}
        payload = {
            "usecases": [
                {
                    "id": "US-PAI-002",
                    "actor": "고객",
                    "name": "본인인증",
                    "description": "고객이 본인인증을 수행한다.",
                    "process_target": "Y",
                }
            ]
        }

        with self.assertRaises(LLMError):
            UsecasesAgent().validate_payload(spec, simple_runtime(), payload)

    def test_usecase_writer_falls_back_instead_of_stopping_after_retryable_validation_errors(self):
        client = FailingUsecaseLLMClient()
        previous_attempts = os.environ.get("OPENAI_LLM_TASK_MAX_ATTEMPTS")
        previous_delay = os.environ.get("OPENAI_LLM_TASK_RETRY_BASE_SECONDS")
        os.environ["OPENAI_LLM_TASK_MAX_ATTEMPTS"] = "2"
        os.environ["OPENAI_LLM_TASK_RETRY_BASE_SECONDS"] = "0"
        runtime = AgentRuntime(
            ctx=SimpleNamespace(template_type="simple", topic="상품 연동/인증", business_code="PAI"),
            target_spec={
                "usecases": [
                    {
                        "id": "US-PAI-001",
                        "actor": "고객",
                        "name": "상품 연동 인증",
                        "description": "고객이 상품 연동 인증을 요청하고 처리 결과를 확인해 상품 이용 조건을 확정한다.",
                        "process_target": "Y",
                    }
                ]
            },
            learning={},
            guideline={},
            evidence_store=EmptyEvidenceStore(),
            authoring_blueprint={},
            llm_client=client,
        )
        spec = {"meta": {"topic": "상품 연동/인증"}, "actors": [{"id": "ACT-PAI-001", "name": "고객"}]}

        try:
            result = UsecasesAgent().write(spec, runtime)
        finally:
            if previous_attempts is None:
                os.environ.pop("OPENAI_LLM_TASK_MAX_ATTEMPTS", None)
            else:
                os.environ["OPENAI_LLM_TASK_MAX_ATTEMPTS"] = previous_attempts
            if previous_delay is None:
                os.environ.pop("OPENAI_LLM_TASK_RETRY_BASE_SECONDS", None)
            else:
                os.environ["OPENAI_LLM_TASK_RETRY_BASE_SECONDS"] = previous_delay

        self.assertEqual("상품 연동 인증", result["usecases"][0]["name"])
        self.assertEqual(2, client.calls)
        self.assertEqual("usecases", result["meta"]["writer_fallback_events"][0]["chapter"])
        self.assertEqual("local_seed_payload", result["meta"]["writer_fallback_events"][0]["mode"])

    def test_inspector_does_not_flag_product_auth_goal_as_step_only(self):
        spec = {
            "actors": [{"id": "ACT-PAI-001", "name": "고객"}],
            "usecases": [
                {
                    "id": "US-PAI-001",
                    "actor": "고객",
                    "name": "상품 연동 인증",
                    "description": "고객이 상품 연동 인증을 요청하고 처리 결과를 확인해 상품 이용 조건을 확정한다.",
                    "process_target": "Y",
                }
            ],
        }

        titles = {finding.title for finding in check_json_stage_rules(spec, "04_usecases")}

        self.assertNotIn("절차형 Y 유즈케이스", titles)

    def test_inspector_flags_authentication_step_as_y_usecase(self):
        spec = {
            "actors": [{"id": "ACT-PAI-001", "name": "고객"}],
            "usecases": [
                {
                    "id": "US-PAI-002",
                    "actor": "고객",
                    "name": "본인인증",
                    "description": "고객이 본인인증을 수행한다.",
                    "process_target": "Y",
                }
            ],
        }

        titles = {finding.title for finding in check_json_stage_rules(spec, "04_usecases")}

        self.assertIn("절차형 Y 유즈케이스", titles)

    def test_usecase_rejects_generic_system_support_name(self):
        spec = {"actors": [{"name": "BSS"}]}
        payload = {
            "usecases": [
                {
                    "id": "US-GFT-002",
                    "actor": "BSS",
                    "name": "BSS 지원 처리",
                    "description": "BSS가 해당 업무에 필요한 책임을 수행하고 결과를 제공하는 유즈케이스",
                    "process_target": "N",
                }
            ]
        }

        with self.assertRaises(LLMError):
            UsecasesAgent().validate_payload(spec, simple_runtime(), payload)

    def test_auto_actor_coverage_uses_specific_system_responsibility(self):
        spec = {
            "meta": {"topic": "선물주문", "business_code": "GFT"},
            "actors": [{"id": "ACT-GFT-001", "name": "BSS"}],
            "usecases": [],
        }

        ensure_usecase_actor_coverage(spec)

        self.assertEqual("BSS 판정 및 결과 회신", spec["usecases"][0]["name"])
        self.assertIn("판정", spec["usecases"][0]["description"])

    def test_state_agent_keeps_semantic_review_for_inspector(self):
        transitions = [
            {
                "usecase_ids": ["UC-MEM-001"],
                "current_state": "가입 요청",
                "event": "회원 가입",
                "next_state": "가입 실패",
                "criteria": "인증 실패 시 고객에게 재시도를 안내한다.",
            },
            {
                "usecase_ids": ["UC-MEM-001"],
                "current_state": "가입 요청",
                "event": "회원 가입",
                "next_state": "가입 보류",
                "criteria": "필수 동의 누락 시 보류한다.",
            },
            {
                "usecase_ids": ["UC-MEM-001"],
                "current_state": "가입 요청",
                "event": "회원 가입",
                "next_state": "가입 제한",
                "criteria": "제한 고객이면 가입을 제한한다.",
            },
            {
                "usecase_ids": ["UC-MEM-001"],
                "current_state": "가입 요청",
                "event": "회원 가입",
                "next_state": "가입 완료",
                "criteria": "가입 가능이면 회원 자격을 부여한다.",
            },
        ]
        spec = {
            "meta": {"topic": "회원가입"},
            "usecases": [
                {
                    "id": "UC-MEM-001",
                    "actor": "고객",
                    "name": "회원 가입",
                    "description": "고객이 가입 조건을 확인하고 회원 가입을 완료한다.",
                    "process_target": "Y",
                }
            ],
            "states": [
                {"id": "ST-001", "name": "가입 요청", "description": "가입 처리를 요청한 상태다.", "next_action": "가입 조건을 판정한다."},
                {"id": "ST-002", "name": "가입 실패", "description": "가입 처리에 실패한 상태다.", "next_action": "실패 사유를 안내한다."},
                {"id": "ST-003", "name": "가입 보류", "description": "추가 확인이 필요한 상태다.", "next_action": "보류 사유를 안내한다."},
                {"id": "ST-004", "name": "가입 제한", "description": "가입이 제한된 상태다.", "next_action": "제한 사유를 안내한다."},
                {"id": "ST-005", "name": "가입 완료", "description": "회원 가입이 완료된 상태다.", "next_action": "가입 완료 결과를 안내한다."},
            ],
            "state_transitions": transitions,
        }

        StateAgent().validate_payload(spec, simple_runtime(), {"states": spec["states"], "state_transitions": transitions})

        reasons = {warning.get("reason") for warning in spec["meta"].get("normalization_warnings", [])}
        self.assertIn("state_transition_decision_result_mixed", reasons)
        self.assertIn("state_transition_branch_priority", reasons)

    def test_state_inspector_catches_coverage_and_decision_mixing(self):
        spec = {
            "usecases": [
                {"id": "UC-MEM-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"},
                {"id": "UC-MEM-002", "name": "회원 탈퇴", "actor": "고객", "process_target": "Y"},
            ],
            "states": [
                {"id": "ST-001", "name": "가입 요청", "description": "가입 처리를 요청한 상태다.", "next_action": "가입 조건을 판정한다."},
                {"id": "ST-002", "name": "가입 완료", "description": "회원 가입이 완료된 상태다.", "next_action": "가입 완료 결과를 안내한다."},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["UC-MEM-001"],
                    "current_state": "가입 요청",
                    "event": "가입 조건 판정",
                    "next_state": "가입 완료",
                    "criteria": "가입 가능이면 회원 자격을 부여한다.",
                }
            ],
        }

        titles = {finding.title for finding in check_json_stage_rules(spec, "06_state")}

        self.assertIn("상태 전이 유즈케이스 범위 부족", titles)
        self.assertIn("가능 여부와 확정 결과 혼용", titles)

    def test_function_details_are_normalized_to_sample_style(self):
        spec = {
            "meta": {"topic": "통합알림", "business_code": "ARZ"},
            "processes": [{"id": "PR-ARZ-001", "name": "알림 목록 조회"}],
            "functions": [
                {
                    "id": "FN-ARZ-001",
                    "process_id": "PR-ARZ-001",
                    "name": "통합 알림 목록 조회",
                    "description": "확정된 조건으로 통합 알림 목록을 조회한다.",
                    "details": [
                        "서비스, 유형, 상태 기준을 조회 조건으로 구성한다.",
                        "알림별 중요도, 유형, 상태 정보를 함께 조회한다.",
                        "목록 결과에 후속 처리 연결 판단용 기본 정보를 포함한다.",
                    ],
                }
            ],
        }

        normalize_agent_output(spec, FunctionsAgent(), topic_runtime("통합알림"))

        self.assertEqual(
            ["서비스·유형·상태 기준 조회 조건 구성", "알림별 중요도·유형·상태 정보 함께 조회", "목록 결과에 후속 처리 연결 판단용 기본 정보 포함"],
            spec["functions"][0]["details"],
        )
        self.assertNotIn("한다", " ".join(spec["functions"][0]["details"]))

    def test_inspector_flags_sentence_style_function_details(self):
        body = """
        <table><tbody><tr>
        <td class="mono">FN-ARZ-001</td>
        <td>통합 알림 목록 조회</td>
        <td>확정된 조건으로 통합 알림 목록을 조회한다.</td>
        <td>서비스, 유형, 상태 기준을 조회 조건으로 구성한다.<br/>목록 결과를 제공한다.</td>
        </tr></tbody></table>
        """

        findings = check_function_guide(body, "08_functions")

        self.assertTrue(any(finding.title == "기능 세부 구성 문장형 작성" for finding in findings))

    def test_validator_blocks_sentence_style_function_details(self):
        spec = {
            "meta": {"business_code": "ARZ"},
            "functions": [
                {
                    "id": "FN-ARZ-001",
                    "process_id": "PR-ARZ-001",
                    "name": "통합 알림 목록 조회",
                    "description": "확정된 조건으로 통합 알림 목록을 조회한다.",
                    "details": [
                        "서비스, 유형, 상태 기준을 조회 조건으로 구성한다.",
                        "알림별 중요도 조회",
                    ],
                }
            ],
            "processes": [
                {
                    "id": "PR-ARZ-001",
                    "name": "알림 목록 확인",
                    "related_functions": ["FN-ARZ-001 통합 알림 목록 조회"],
                }
            ],
        }

        result = validate_stage_critical(spec, "ARZ", "08_functions")

        self.assertFalse(result.ok)
        self.assertTrue(any("기능 세부 기능 구성은 설명문" in error for error in result.errors))

    def test_html_function_guide_dedupes_reused_function_rows(self):
        rows = "\n".join(
            """
            <tr>
            <td class="mono">FN-ARZ-001</td>
            <td>대상 조건 조회</td>
            <td>대상 조건을 조회해 결과를 제공한다.</td>
            <td>대상 조건 구성<br/>권한 상태 검증<br/>결과 안내 구성</td>
            </tr>
            """
            for _ in range(8)
        )
        body = f"<table><tbody>{rows}</tbody></table>"

        findings = check_function_guide(body, "08_functions")

        self.assertFalse(any(finding.title == "기능 세부 구성 반복" for finding in findings))

    def test_json_function_granularity_flags_generic_names_with_actionable_fields(self):
        spec = {
            "processes": [
                {"id": f"PR-ARZ-{index:03d}", "name": f"프로세스 {index}"}
                for index in range(1, 11)
            ],
            "functions": [
                {
                    "id": f"FN-ARZ-{index:03d}",
                    "process_id": f"PR-ARZ-{index:03d}",
                    "process_ids": [f"PR-ARZ-{index:03d}"],
                    "name": f"{index}번 처리 기능",
                    "description": "업무 처리 결과를 생성한다.",
                    "details": ["조회", "검증", "저장"],
                }
                for index in range(1, 11)
            ],
        }

        findings = check_json_stage_rules(spec, "08_functions")
        generic = next(finding for finding in findings if finding.title == "기능명 일반화")

        self.assertEqual("current_chapter.functions[*].name", generic.target_path)
        self.assertIn("조회", generic.required_change)
        self.assertIn("70%", generic.acceptance_check)

    def test_functions_agent_rejects_process_function_one_to_one_lock(self):
        processes = [
            {"id": f"PR-ARZ-{index:03d}", "name": f"프로세스 {index}"}
            for index in range(1, 9)
        ]
        payload = {
            "functions": [
                {
                    "id": f"FN-ARZ-{index:03d}",
                    "process_id": f"PR-ARZ-{index:03d}",
                    "process_ids": [f"PR-ARZ-{index:03d}"],
                    "name": f"기능 {index}",
                    "description": "업무 처리 결과를 생성한다.",
                    "details": ["대상 조회", "결과 저장"],
                }
                for index in range(1, 9)
            ]
        }

        with self.assertRaises(LLMError):
            FunctionsAgent().validate_payload({"processes": processes}, topic_runtime("통합알림"), payload)

    def test_multi_process_function_reuse_updates_process_links(self):
        spec = {
            "meta": {"topic": "통합알림", "business_code": "ARZ"},
            "processes": [
                {"id": "PR-ARZ-001", "name": "알림 상세 확인", "related_functions": []},
                {"id": "PR-ARZ-002", "name": "후속 처리 연결", "related_functions": []},
            ],
            "functions": [
                {
                    "id": "FN-ARZ-COM-001",
                    "process_id": "PR-ARZ-001",
                    "process_ids": ["PR-ARZ-001", "PR-ARZ-002"],
                    "name": "알림 상태 조회",
                    "description": "알림 상태와 업무 결과를 조회한다.",
                    "details": ["상태 조회", "업무 결과 확인"],
                }
            ],
        }

        normalize_agent_output(spec, FunctionsAgent(), topic_runtime("통합알림"))

        self.assertEqual(["FN-ARZ-COM-001 알림 상태 조회"], spec["processes"][0]["related_functions"])
        self.assertEqual(["FN-ARZ-COM-001 알림 상태 조회"], spec["processes"][1]["related_functions"])

    def test_multi_process_function_reuse_feeds_policy_reconciliation(self):
        spec = {
            "meta": {"topic": "통합알림", "business_code": "ARZ"},
            "processes": [
                {"id": "PR-ARZ-001", "name": "알림 진입", "description": "업무를 시작한다.", "related_policies": []},
                {"id": "PR-ARZ-002", "name": "후속 처리", "description": "업무를 이어간다.", "related_policies": []},
            ],
            "functions": [
                {
                    "id": "FN-ARZ-COM-001",
                    "process_id": "PR-ARZ-001",
                    "process_ids": ["PR-ARZ-001", "PR-ARZ-002"],
                    "name": "권한 상태 조회",
                    "description": "권한과 상태를 검증한다.",
                    "details": ["권한 확인", "상태 조회"],
                }
            ],
            "policy_groups": [
                {"id": "PG-ARZ-AUTH-001", "name": "접근·권한 정책", "description": "접근 권한 기준"},
                {"id": "PG-ARZ-RESULT-001", "name": "처리 결과 정책", "description": "처리 결과 기준"},
            ],
            "policy_details": [
                {"id": "PI-ARZ-AUTH-001", "policy_id": "PG-ARZ-AUTH-001", "name": "권한 기준", "content": "권한이 없으면 제한 안내한다."},
                {"id": "PI-ARZ-RESULT-001", "policy_id": "PG-ARZ-RESULT-001", "name": "결과 기준", "content": "처리 결과를 저장한다."},
            ],
        }

        reconcile_process_policy_links(spec)

        self.assertIn("PG-ARZ-AUTH-001 접근·권한 정책", spec["processes"][1]["related_policies"])

    def test_function_detail_rows_aggregate_policies_from_all_linked_processes(self):
        spec = {
            "processes": [
                {"id": "PR-ARZ-001", "name": "알림 진입", "related_policies": ["PG-ARZ-AUTH-001 접근·권한 정책"]},
                {"id": "PR-ARZ-002", "name": "후속 처리", "related_policies": ["PG-ARZ-RESULT-001 처리 결과 정책"]},
            ],
            "functions": [
                {
                    "id": "FN-ARZ-COM-001",
                    "process_id": "PR-ARZ-001",
                    "process_ids": ["PR-ARZ-001", "PR-ARZ-002"],
                    "name": "알림 상태 조회",
                    "description": "알림 상태와 업무 결과를 조회한다.",
                    "details": ["상태 조회", "업무 결과 확인"],
                }
            ],
        }

        rows = build_function_detail_rows(spec)

        self.assertEqual(
            ["PG-ARZ-AUTH-001 접근·권한 정책", "PG-ARZ-RESULT-001 처리 결과 정책"],
            rows[0]["related_policies"],
        )

    def test_inspector_flags_process_function_one_to_one_lock(self):
        spec = {
            "processes": [
                {"id": f"PR-ARZ-{index:03d}", "name": f"프로세스 {index}"}
                for index in range(1, 9)
            ],
            "functions": [
                {
                    "id": f"FN-ARZ-{index:03d}",
                    "process_id": f"PR-ARZ-{index:03d}",
                    "process_ids": [f"PR-ARZ-{index:03d}"],
                    "name": f"기능 {index}",
                    "details": ["대상 조회", "결과 저장"],
                }
                for index in range(1, 9)
            ],
        }

        findings = check_json_stage_rules(spec, "08_functions")

        self.assertTrue(any(finding.title == "프로세스-기능 1:1 고착" for finding in findings))

    def test_html_inspector_flags_process_function_one_to_one_lock(self):
        rows = "".join(
            f"<tr><td class='mono'>PR-ARZ-{index:03d}</td><td>프로세스 {index}</td><td>설명</td><td>FN-ARZ-{index:03d} 기능 {index}</td><td></td></tr>"
            for index in range(1, 9)
        )
        body = f"<table><tbody>{rows}</tbody></table>"

        findings = check_process_guide(body, "08_functions")

        self.assertTrue(any(finding.title == "프로세스-기능 1:1 고착" for finding in findings))

    def test_html_inspector_accepts_sample_style_name_only_references(self):
        body = """
        <section>
          <h2>4. 프로세스 정의</h2>
          <table><tbody>
            <tr><td class="mono">PR-AIS-001</td><td>검색 진입</td><td>고객이 검색을 시작한다.</td><td>검색 진입점 제공<br/>추천 질의 제공</td><td>검색 입력 정책<br/>재질의 정책</td></tr>
          </tbody></table>
          <h2>5. 기능 정의</h2>
          <table><tbody>
            <tr><td class="mono">FN-AIS-001</td><td>검색 진입점 제공</td><td>검색 진입점을 제공한다.</td><td>통합 검색창 제공<br/>검색 세션 생성</td></tr>
            <tr><td class="mono">FN-AIS-002</td><td>추천 질의 제공</td><td>추천 질의를 제공한다.</td><td>공통 추천 질의 제공<br/>상황 기반 추천 질의 제공</td></tr>
          </tbody></table>
          <h2>6. 정책 정의</h2>
          <table><tbody>
            <tr><td class="mono">PG-AIS-001</td><td>검색 입력 정책</td><td>입력 기준을 정의한다.</td><td>허용 입력 방식<br/>입력 제한 기준</td></tr>
            <tr><td class="mono">PG-AIS-002</td><td>재질의 정책</td><td>재질의 기준을 정의한다.</td><td>재질의 유도 기준<br/>보정 조건 제공 기준</td></tr>
          </tbody></table>
        </section>
        """

        titles = {finding.title for finding in check_process_guide(body, "09_policies")}

        self.assertNotIn("관련 기능 ID 누락", titles)
        self.assertNotIn("관련 정책 ID 누락", titles)

    def test_html_inspector_accepts_space_joined_sample_style_references(self):
        body = """
        <section>
          <h2>4. 프로세스 정의</h2>
          <table><tbody>
            <tr><td class="mono">PR-AIS-001</td><td>검색 진입</td><td>고객이 검색을 시작한다.</td><td>검색 진입점 제공 추천 질의 제공 최근 검색어 제공</td><td>검색 입력 정책 재질의 정책 검색 이력 정책</td></tr>
          </tbody></table>
          <h2>5. 기능 정의</h2>
          <table><tbody>
            <tr><td class="mono">FN-AIS-001</td><td>검색 진입점 제공</td><td>검색 진입점을 제공한다.</td><td>통합 검색창 제공<br/>검색 세션 생성</td></tr>
            <tr><td class="mono">FN-AIS-002</td><td>추천 질의 제공</td><td>추천 질의를 제공한다.</td><td>공통 추천 질의 제공<br/>상황 기반 추천 질의 제공</td></tr>
            <tr><td class="mono">FN-AIS-003</td><td>최근 검색어 제공</td><td>최근 검색어를 제공한다.</td><td>최근 질의 조회<br/>최근 질의 삭제</td></tr>
          </tbody></table>
          <h2>6. 정책 정의</h2>
          <table><tbody>
            <tr><td class="mono">PG-AIS-001</td><td>검색 입력 정책</td><td>입력 기준을 정의한다.</td><td>허용 입력 방식<br/>입력 제한 기준</td></tr>
            <tr><td class="mono">PG-AIS-002</td><td>재질의 정책</td><td>재질의 기준을 정의한다.</td><td>재질의 유도 기준<br/>보정 조건 제공 기준</td></tr>
            <tr><td class="mono">PG-AIS-003</td><td>검색 이력 정책</td><td>이력 기준을 정의한다.</td><td>이력 저장 기준<br/>삭제 기준</td></tr>
          </tbody></table>
        </section>
        """

        titles = {finding.title for finding in check_process_guide(body, "09_policies")}

        self.assertNotIn("관련 기능 ID 누락", titles)
        self.assertNotIn("관련 정책 ID 누락", titles)

    def test_diagram_inspector_accepts_svg_sample_style_diagrams(self):
        body = """
        <h3>다. 유즈케이스 다이어그램</h3>
        <div class="diagram-wrap"><svg><text>고객 → 검색 질의 입력</text></svg></div>
        <h3>라. 상태 전이표</h3>
        <h4>3) 상태 전이 다이어그램</h4>
        <div class="diagram-wrap"><svg><text>요청 접수 → 판정 중</text></svg></div>
        <h2>4. 프로세스 정의</h2>
        <h3>나. 전체 업무 흐름도</h3>
        <div class="diagram-wrap"><svg><text>시작 → 판단 → 처리 완료</text></svg></div>
        <h2>5. 기능 정의</h2>
        """

        titles = {finding.title for finding in check_diagram_guide(body, "10_final_check")}

        self.assertNotIn("UML 2.0 유즈케이스 표기 부족", titles)
        self.assertNotIn("유즈케이스 시스템 경계 표기 부족", titles)
        self.assertNotIn("상태 다이어그램 코드 표기 부족", titles)
        self.assertNotIn("BPMN 2.0 프로세스 표기 부족", titles)
        self.assertNotIn("업무 흐름도 프로세스 ID 누락", titles)

    def test_diagram_inspector_flags_wrapped_process_flow_layout(self):
        body = """
        <h2>4. 프로세스 정의</h2>
        <h3>나. 전체 업무 흐름도</h3>
        <div class="diagram-wrap bpmn-process-diagram">
          <svg>
            <text>Start → PR-AIS-001 → PR-AIS-002 → End</text>
            <path class="flow" d="M 1000 200 L 1000 300 L 300 300"></path>
          </svg>
        </div>
        <h2>5. 기능 정의</h2>
        """

        titles = {finding.title for finding in check_diagram_guide(body, "10_final_check")}

        self.assertIn("업무 흐름도 접힘 배치", titles)

    def test_state_rejects_oversized_simple_transition_set(self):
        states = [
            {"id": f"ST-GFT-{index:03d}", "name": f"상태 {index}", "description": "업무 판단 상태이다.", "next_action": "후속 기준을 확인한다."}
            for index in range(1, 14)
        ]
        payload = {"states": states, "state_transitions": []}
        spec = {"states": states}

        with self.assertRaises(LLMError):
            StateAgent().validate_payload(spec, simple_runtime(), payload)

    def test_state_allows_small_transition_overflow_to_avoid_retry_churn(self):
        states = [
            {"id": "ST-GFT-001", "name": "진입 전", "description": "업무 시작 전 상태이다.", "next_action": "업무를 시작한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
        ]
        payload = {
            "states": states,
            "state_transitions": [
                {
                    "usecase_ids": ["US-GFT-001"],
                    "current_state": "진입 전",
                    "event": "선물 주문",
                    "next_state": "처리 완료",
                    "criteria": f"{index}차 확인 기준이 충족되면 완료한다.",
                }
                for index in range(1, 30)
            ],
        }

        StateAgent().validate_payload(state_spec(states), simple_runtime(), payload)

    def test_state_rejects_empty_state_payload_before_inspector(self):
        payload = {"states": [], "state_transitions": []}

        with self.assertRaises(LLMError):
            StateAgent().validate_payload(state_spec([]), simple_runtime(), payload)

    def test_state_stage_gate_rejects_empty_state_description_and_next_action(self):
        spec = state_spec(
            [
                {"id": "ST-GFT-001", "name": "진입 전", "description": "", "next_action": ""},
                {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
            ]
        )
        spec["state_transitions"] = [
            {
                "usecase_ids": ["US-GFT-001"],
                "current_state": "진입 전",
                "event": "선물 주문",
                "next_state": "처리 완료",
                "criteria": "주문 조건이 충족되면 처리 완료로 전이한다.",
            }
        ]

        result = validate_stage_critical(spec, "GFT", scope="state")

        self.assertFalse(result.ok)
        self.assertIn("Critical Gate: 상태 description가 비어 있습니다: ST-GFT-001", result.errors)
        self.assertIn("Critical Gate: 상태 next_action가 비어 있습니다: ST-GFT-001", result.errors)

    def test_state_stage_gate_rejects_empty_state_name(self):
        spec = state_spec(
            [
                {"id": "ST-GFT-001", "name": "", "description": "업무 시작 전 상태이다.", "next_action": "업무를 시작한다."},
                {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
            ]
        )
        spec["state_transitions"] = [
            {
                "usecase_ids": ["US-GFT-001"],
                "current_state": "ST-GFT-001",
                "event": "선물 주문",
                "next_state": "처리 완료",
                "criteria": "주문 조건이 충족되면 처리 완료로 전이한다.",
            }
        ]

        result = validate_stage_critical(spec, "GFT", scope="state")

        self.assertFalse(result.ok)
        self.assertIn("Critical Gate: 상태 name가 비어 있습니다: ST-GFT-001", result.errors)

    def test_state_records_ambiguous_exception_branches_for_inspector(self):
        states = [
            {"id": "ST-GFT-001", "name": "운영 확인 필요", "description": "운영자가 후속 기준을 확인하는 상태이다.", "next_action": "처리 사유별 후속 조치를 결정한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
            {"id": "ST-GFT-003", "name": "처리 제한", "description": "업무 진행이 제한된 상태이다.", "next_action": "제한 사유를 안내한다."},
            {"id": "ST-GFT-004", "name": "처리 실패", "description": "업무 처리가 실패한 상태이다.", "next_action": "재시도 기준을 안내한다."},
            {"id": "ST-GFT-005", "name": "처리 보류", "description": "업무 처리가 보류된 상태이다.", "next_action": "운영 확인을 요청한다."},
        ]
        transitions = [
            {"usecase_ids": ["US-GFT-001"], "current_state": "운영 확인 필요", "event": "선물 주문", "next_state": "처리 완료", "criteria": "운영자가 승인한다."},
            {"usecase_ids": ["US-GFT-001"], "current_state": "운영 확인 필요", "event": "선물 주문", "next_state": "처리 제한", "criteria": "제한 사유가 확인된다."},
            {"usecase_ids": ["US-GFT-001"], "current_state": "운영 확인 필요", "event": "선물 주문", "next_state": "처리 실패", "criteria": "연계 오류가 발생한다."},
            {"usecase_ids": ["US-GFT-001"], "current_state": "운영 확인 필요", "event": "선물 주문", "next_state": "처리 보류", "criteria": "입력 정보가 누락된다."},
        ]
        payload = {"states": states, "state_transitions": transitions}
        spec = state_spec(states)

        StateAgent().validate_payload(spec, simple_runtime(), payload)

        reasons = {warning.get("reason") for warning in spec["meta"].get("normalization_warnings", [])}
        self.assertIn("state_transition_branch_priority", reasons)

    def test_state_requires_transition_usecase_id(self):
        states = [
            {"id": "ST-GFT-001", "name": "진입 전", "description": "업무 시작 전 상태이다.", "next_action": "업무를 시작한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
        ]
        payload = {
            "states": states,
            "state_transitions": [
                {"current_state": "진입 전", "event": "업무 시작", "next_state": "처리 완료", "criteria": "고객이 요청한다."}
            ],
        }

        with self.assertRaises(LLMError):
            StateAgent().validate_payload(state_spec(states), simple_runtime(), payload)

    def test_state_records_actor_usecase_lifecycle_coverage_for_inspector(self):
        states = [
            {"id": "ST-GFT-001", "name": "진입 전", "description": "업무 시작 전 상태이다.", "next_action": "업무를 시작한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
        ]
        spec = state_spec(states)
        spec["usecases"].append(
            {
                "id": "US-GFT-002",
                "actor": "운영자",
                "name": "선물 주문 취소",
                "description": "운영자가 예외 상황에서 선물 주문을 취소한다.",
                "process_target": "Y",
            }
        )
        payload = {
            "states": states,
            "state_transitions": [
                {"usecase_ids": ["US-GFT-001"], "current_state": "진입 전", "event": "선물 주문", "next_state": "처리 완료", "criteria": "고객이 요청을 완료한다."}
            ],
        }

        StateAgent().validate_payload(spec, simple_runtime(), payload)

        reasons = {warning.get("reason") for warning in spec["meta"].get("normalization_warnings", [])}
        self.assertIn("state_usecase_lifecycle_coverage", reasons)

        titles = {finding.title for finding in check_json_stage_rules({**spec, **payload}, "06_state")}
        self.assertIn("상태 전이 유즈케이스 범위 부족", titles)

    def test_state_records_renamed_state_term_candidate_for_inspector(self):
        states = [
            {"id": "ST-GFT-001", "name": "수락 대기", "description": "수취인 응답을 기다리는 상태이다.", "next_action": "수락 또는 거절을 기다린다."},
            {"id": "ST-GFT-002", "name": "열람 완료", "description": "수취인이 선물을 열람한 상태이다.", "next_action": "수락 또는 거절을 선택한다."},
        ]
        payload = {
            "states": states,
            "state_transitions": [
                {"usecase_ids": ["US-GFT-001"], "current_state": "수락 대기", "event": "선물 주문", "next_state": "열람 완료", "criteria": "수취인이 선물 내용을 확인한다."}
            ],
        }
        spec = state_spec(states)
        spec["terms"] = [
            {"id": "TM-GFT-001", "name": "열람", "description": "수취인이 선물 내용을 확인한 고객 표시 상태"}
        ]

        StateAgent().validate_payload(spec, simple_runtime(), payload)

        reasons = {warning.get("reason") for warning in spec["meta"].get("normalization_warnings", [])}
        self.assertIn("state_term_contract_mismatch", reasons)

    def test_state_records_possibility_as_terminal_result_for_inspector(self):
        states = [
            {"id": "ST-GFT-001", "name": "선물 가능 판정 중", "description": "BSS가 가능 여부를 판정하는 상태이다.", "next_action": "허용 또는 제한으로 분기한다."},
            {"id": "ST-GFT-002", "name": "취소", "description": "선물 주문이 취소된 상태이다.", "next_action": "취소 결과를 안내한다."},
        ]
        payload = {
            "states": states,
            "state_transitions": [
                {"usecase_ids": ["US-GFT-001"], "current_state": "선물 가능 판정 중", "event": "선물 주문", "next_state": "취소", "criteria": "BSS가 회수 가능 회신을 반환한다."}
            ],
        }

        spec = state_spec(states)

        StateAgent().validate_payload(spec, simple_runtime(), payload)

        reasons = {warning.get("reason") for warning in spec["meta"].get("normalization_warnings", [])}
        self.assertIn("state_transition_decision_result_mixed", reasons)

    def test_state_preserves_business_event_trigger(self):
        states = [
            {"id": "ST-GFT-001", "name": "진입 전", "description": "업무 시작 전 상태이다.", "next_action": "업무를 시작한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
        ]
        spec = state_spec(states)
        payload = {
            "states": states,
            "state_transitions": [
                {"usecase_ids": ["US-GFT-001"], "current_state": "진입 전", "event": "BSS 판정 완료", "next_state": "처리 완료", "criteria": "BSS 판정 결과가 허용이면 완료한다."}
            ],
        }
        spec["state_transitions"] = [dict(payload["state_transitions"][0])]

        StateAgent().validate_payload(spec, simple_runtime(), payload)

        self.assertEqual("BSS 판정 완료", payload["state_transitions"][0]["event"])
        self.assertEqual("BSS 판정 완료", spec["state_transitions"][0]["event"])
        self.assertEqual("BSS 판정 결과가 허용이면 완료한다.", payload["state_transitions"][0]["criteria"])

    def test_validator_allows_business_event_trigger_with_usecase_ids(self):
        spec = {
            "usecases": [
                {"id": "US-MBR-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"}
            ],
            "states": [
                {"id": "ST-MBR-001", "name": "미가입"},
                {"id": "ST-MBR-002", "name": "정상"},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["US-MBR-001"],
                    "current_state": "미가입",
                    "event": "회원 가입 완료",
                    "next_state": "정상",
                    "criteria": "회원 계정 생성과 CI/DI 매핑 저장이 완료되면 전환한다.",
                }
            ],
        }

        self.assertEqual([], validate_state_transition_integrity(spec))

    def test_validator_accepts_transition_state_ids(self):
        spec = {
            "usecases": [
                {"id": "US-MBR-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"}
            ],
            "states": [
                {"id": "ST-MBR-001", "name": "미가입"},
                {"id": "ST-MBR-002", "name": "정상"},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["US-MBR-001"],
                    "current_state": "ST-MBR-001",
                    "event": "회원 가입 완료",
                    "next_state": "ST-MBR-002",
                    "criteria": "회원 계정 생성과 CI/DI 매핑 저장이 완료되면 전환한다.",
                }
            ],
        }

        self.assertEqual([], validate_state_transition_integrity(spec))

    def test_validator_rejects_unknown_transition_state_reference(self):
        spec = {
            "usecases": [
                {"id": "US-MBR-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"}
            ],
            "states": [
                {"id": "ST-MBR-001", "name": "미가입"},
                {"id": "ST-MBR-002", "name": "정상"},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["US-MBR-001"],
                    "current_state": "ST-MBR-999",
                    "event": "회원 가입 완료",
                    "next_state": "정상",
                    "criteria": "회원 계정 생성과 CI/DI 매핑 저장이 완료되면 전환한다.",
                }
            ],
        }

        errors = validate_state_transition_integrity(spec)

        self.assertIn("Critical Gate: 현재 상태가 상태 목록의 ID/이름에 없습니다: ST-MBR-999", errors)

    def test_validator_rejects_empty_transition_event(self):
        spec = {
            "usecases": [
                {"id": "US-MBR-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"}
            ],
            "states": [
                {"id": "ST-MBR-001", "name": "미가입"},
                {"id": "ST-MBR-002", "name": "정상"},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["US-MBR-001"],
                    "current_state": "미가입",
                    "event": "",
                    "next_state": "정상",
                    "criteria": "회원 계정 생성과 CI/DI 매핑 저장이 완료되면 전환한다.",
                }
            ],
        }

        self.assertIn("Critical Gate: 상태 전이 이벤트가 비어 있습니다.", validate_state_transition_integrity(spec))

    def test_state_inspector_flags_transient_state_overmodeling(self):
        spec = {
            "usecases": [
                {"id": "UC-MEM-001", "name": "회원 가입", "actor": "고객", "process_target": "Y"},
            ],
            "states": [
                {"id": "ST-001", "name": "미가입", "description": "회원 가입 전 상태다.", "next_action": "가입을 시작한다."},
                {"id": "ST-002", "name": "로그인 세션", "description": "로그인 세션이 열린 처리 단계다.", "next_action": "세션을 확인한다."},
                {"id": "ST-003", "name": "인증 실패", "description": "본인 인증에 실패한 처리 단계다.", "next_action": "재시도를 안내한다."},
                {"id": "ST-004", "name": "BSS 처리 중", "description": "BSS가 가입 조건을 판정 중인 처리 단계다.", "next_action": "판정 결과를 기다린다."},
                {"id": "ST-005", "name": "정상", "description": "가입이 완료된 회원 상태다.", "next_action": "서비스 이용을 허용한다."},
            ],
            "state_transitions": [
                {
                    "usecase_ids": ["UC-MEM-001"],
                    "current_state": "미가입",
                    "event": "회원 가입 완료",
                    "next_state": "정상",
                    "criteria": "가입 조건 충족 후 회원 자격을 부여한다.",
                }
            ],
        }

        titles = {finding.title for finding in check_json_stage_rules(spec, "06_state")}

        self.assertIn("처리 단계의 상태 승격", titles)

    def test_state_candidate_terms_exclude_decision_conditions(self):
        spec = {
            "terms": [
                {"id": "TM-GFT-001", "name": "수락 자격", "description": "수취인이 해당 선물을 받을 수 있는지 판정하는 조건이다."},
                {"id": "TM-GFT-002", "name": "수락 대기", "description": "수취인이 아직 수락이나 거절을 완료하지 않은 상태다."},
            ]
        }

        self.assertEqual(["수락 대기"], [item["name"] for item in state_term_candidates(spec)])

    def test_state_lifecycle_contract_uses_all_actor_usecases_as_primary_source(self):
        spec = {
            "usecases": [
                {"id": "US-GFT-001", "actor": "고객", "name": "선물 수락", "description": "고객이 선물을 수락한다.", "process_target": "Y"},
                {"id": "US-GFT-002", "actor": "BSS", "name": "수락 자격 판정", "description": "BSS가 수락 자격을 판정한다.", "process_target": "N"},
            ]
        }

        contract = state_usecase_lifecycle_contract_for_prompt(spec)

        self.assertEqual(["US-GFT-001", "US-GFT-002"], [row["usecase_id"] for row in contract["usecase_lifecycles"]])
        self.assertIn("유즈케이스", contract["primary_rule"])

    def test_state_authoring_contract_lists_system_usecases_too(self):
        spec = {
            "usecases": [
                {"id": "US-GFT-001", "actor": "고객", "name": "선물 수락", "description": "고객이 선물을 수락한다.", "process_target": "Y"},
                {"id": "US-GFT-002", "actor": "BSS", "name": "수락 자격 판정", "description": "BSS가 수락 자격을 판정한다.", "process_target": "N"},
            ]
        }

        block = state_authoring_contract_block(StateAgent(), spec, {"states": [], "state_transitions": []})

        self.assertIn("US-GFT-001", block)
        self.assertIn("US-GFT-002", block)
        self.assertIn("기계적으로 포함하지 않는다", block)

    def test_state_allows_system_actor_usecase_as_transition_event(self):
        states = [
            {"id": "ST-GFT-001", "name": "판정 중", "description": "BSS가 판정하는 상태이다.", "next_action": "판정 결과로 분기한다."},
            {"id": "ST-GFT-002", "name": "처리 완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 안내한다."},
        ]
        spec = state_spec(states)
        spec["usecases"] = [
            {
                "id": "US-GFT-BSS-001",
                "actor": "BSS",
                "name": "선물 가능 여부 판정",
                "description": "BSS가 선물 가능 여부를 판정한다.",
                "process_target": "N",
            }
        ]
        payload = {
            "states": states,
            "state_transitions": [
                {"usecase_ids": ["US-GFT-BSS-001"], "current_state": "판정 중", "event": "선물 가능 여부 판정", "next_state": "처리 완료", "criteria": "BSS가 허용 결과를 회신하면 처리 완료로 전환한다."}
            ],
        }

        StateAgent().validate_payload(spec, simple_runtime(), payload)

    def test_patch_target_path_parses_property_refs(self):
        refs = target_field_refs_from_path(
            "current_chapter.states[1].description; current_chapter.state_transitions[2].criteria"
        )

        self.assertEqual(
            [
                {"field": "states", "index": 1, "property": "description"},
                {"field": "state_transitions", "index": 2, "property": "criteria"},
            ],
            refs,
        )

    def test_patch_contract_lists_current_values_for_target_fields(self):
        payload = {
            "states": [
                {"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명", "next_action": "기존 후속"}
            ]
        }
        feedback = [{"issue_id": "F-1", "target_path": "current_chapter.states[0].description", "required_change": "설명을 바꾼다."}]

        contract = patch_target_field_contract(payload, feedback)

        self.assertEqual("states[0].description", contract[0]["fields"][0]["path"])
        self.assertEqual("기존 설명", contract[0]["fields"][0]["current_value"])
        self.assertTrue(contract[0]["fields"][0]["must_change"])

    def test_patch_revision_rejects_noop_target_field(self):
        agent = StateAgent()
        current = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명"}],
            "state_transitions": [],
        }
        merged = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명"}],
            "state_transitions": [],
        }
        feedback = [{"issue_id": "F-1", "target_path": "current_chapter.states[0].description"}]

        with self.assertRaises(LLMError):
            ensure_patch_feedback_targets_changed(agent, current, merged, feedback)

    def test_patch_revision_allows_changed_target_field(self):
        agent = StateAgent()
        current = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명"}],
            "state_transitions": [],
        }
        merged = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "수정 설명"}],
            "state_transitions": [],
        }
        feedback = [{"issue_id": "F-1", "target_path": "current_chapter.states[0].description"}]

        ensure_patch_feedback_targets_changed(agent, current, merged, feedback)

    def test_patch_revision_accepts_related_state_transition_change(self):
        agent = StateAgent()
        current = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명"}],
            "state_transitions": [
                {
                    "usecase_ids": ["US-GFT-001"],
                    "current_state": "진입 전",
                    "event": "선물 주문",
                    "next_state": "판정 중",
                    "criteria": "기존 기준",
                }
            ],
        }
        merged = {
            "states": [{"id": "ST-GFT-001", "name": "판정 중", "description": "기존 설명"}],
            "state_transitions": [
                {
                    "usecase_ids": ["US-GFT-001"],
                    "current_state": "진입 전",
                    "event": "선물 주문",
                    "next_state": "판정 중",
                    "criteria": "원천 상태 변경이 들어오면 판정 중으로 재진입한다.",
                }
            ],
        }
        feedback = [
            {
                "issue_id": "F-1",
                "target_path": "current_chapter.states[0].description",
                "required_change": "상태 설명 또는 outbound transitions 중 하나를 조정한다.",
                "recommendation": "current_chapter.state_transitions[0].criteria를 원천 상태 변경 기준으로 보완할 수 있다.",
            }
        ]

        ensure_patch_feedback_targets_changed(agent, current, merged, feedback)

    def test_scoped_full_revision_uses_score_and_routing_mode(self):
        feedback = [
            {
                "category": "structure",
                "detail": "프로세스 구조 전반이 샘플 수준에 맞지 않습니다.",
                "inspector_score": 82,
            }
        ]

        self.assertFalse(requires_scoped_full_revision(ProcessAgent(), feedback))

        feedback[0]["inspector_score"] = 62

        self.assertTrue(requires_scoped_full_revision(ProcessAgent(), feedback))

        feedback[0]["inspector_score"] = 76
        feedback[0]["remediation_mode"] = "scoped_section_revision"

        self.assertTrue(requires_scoped_full_revision(ProcessAgent(), feedback))

    def test_fallback_patch_target_stays_small_for_broad_feedback(self):
        self.assertLessEqual(fallback_patch_item_limit(PoliciesAgent(), "policy_details"), 18)
        self.assertLessEqual(fallback_patch_item_limit(ProcessAgent(), "processes"), 12)

    def test_patch_payload_rejects_out_of_target_ids_without_add_finding(self):
        feedback = [
            {
                "issue_id": "F-1",
                "target_path": "current_chapter.processes[0].description",
                "required_change": "설명을 구체화한다.",
            }
        ]
        patch_target = {
            "processes": [
                {"id": "PR-GFT-001", "usecase_id": "US-GFT-001", "name": "기존 프로세스", "description": "기존 설명"}
            ]
        }
        patch_payload = {
            "processes": [
                {"id": "PR-GFT-999", "usecase_id": "US-GFT-001", "name": "새 프로세스", "description": "대상 밖 항목"}
            ]
        }

        with self.assertRaises(LLMError):
            ensure_patch_payload_within_target(ProcessAgent(), patch_payload, patch_target, feedback)

    def test_patch_payload_allows_small_additions_when_finding_requires_missing_item(self):
        feedback = [
            {
                "issue_id": "F-1",
                "target_path": "current_chapter.processes",
                "required_change": "누락된 프로세스를 추가한다.",
                "patch_hint": "프로세스 항목 추가",
            }
        ]
        patch_target = {
            "processes": [
                {"id": "PR-GFT-001", "usecase_id": "US-GFT-001", "name": "기존 프로세스", "description": "기존 설명"}
            ]
        }
        patch_payload = {
            "processes": [
                {"id": "PR-GFT-002", "usecase_id": "US-GFT-001", "name": "누락 프로세스", "description": "누락 보완"}
            ]
        }

        ensure_patch_payload_within_target(ProcessAgent(), patch_payload, patch_target, feedback)

    def test_policy_link_recommendation_uses_topic_specific_policy_names(self):
        process = {
            "name": "알림 목록 기준 확인",
            "description": "고객별 알림 이력과 표시 기준을 확인해 알림 표시 가능 대상을 구분한다.",
        }
        functions = [
            {
                "name": "통합 알림 목록 조회",
                "description": "확정된 조건으로 통합 알림 목록과 핵심 상태를 조회한다.",
                "details": ["알림별 중요도, 유형, 상태 정보를 함께 조회한다."],
            }
        ]
        groups = [
            {"id": "PG-ARZ-INF-001", "name": "알림 정보 노출 정책", "description": "알림함 노출 채널과 우선순위를 정한다."},
            {"id": "PG-ARZ-ERR-001", "name": "예외·상담 전환 정책", "description": "자동 처리 불가 상황의 상담 전환 기준을 정한다."},
        ]

        names = policy_names_for_process(process, groups, functions, max_items=2)

        self.assertIn("알림 정보 노출 정책", names)
        self.assertNotEqual(["예외·상담 전환 정책"], names)

    def test_process_approved_contract_is_slim_but_keeps_alignment_keys(self):
        spec = {
            "meta": {"topic": "통합 알림"},
            "overview": {
                "scope": ["고객이 통합 알림을 조회하고 알림별 후속 업무로 이동하는 범위를 정의한다."],
                "principles": [{"name": "고객 알림 완결성"}],
            },
            "terms": [{"id": f"TM-NTF-{index:03d}", "name": f"용어 {index}"} for index in range(1, 20)],
            "actors": [
                {
                    "id": "ACT-NTF-001",
                    "name": "고객",
                    "description": "고객은 알림 목록을 확인하고 필요한 업무를 이어서 수행하는 책임을 가진다. " * 3,
                }
            ],
            "usecases": [
                {
                    "id": "US-NTF-001",
                    "actor": "고객",
                    "name": "통합 알림 확인",
                    "description": "고객이 알림 목록과 알림별 처리 상태를 확인하고 필요한 후속 업무를 선택한다. " * 3,
                    "process_target": "Y",
                }
            ],
            "states": [
                {
                    "id": "ST-NTF-001",
                    "name": "확인 전",
                    "description": "고객이 아직 알림을 확인하지 않은 상태이다. " * 3,
                    "next_action": "고객이 알림을 확인하거나 만료 기준에 따라 숨김 처리한다. " * 3,
                }
            ],
        }

        contract = approved_contract_for_prompt(ProcessAgent(), spec, topic_runtime())

        self.assertIn("term_index", contract)
        self.assertNotIn("term_contract", contract)
        self.assertIn("actor_contract", contract)
        self.assertEqual("사람", contract["actor_contract"][0]["type"])
        self.assertIn("usecase_contract", contract)
        self.assertIn("goal", contract["usecase_contract"][0])
        self.assertLessEqual(len(contract["usecase_contract"][0]["goal"]), 62)
        self.assertIn("state_contract", contract)
        self.assertIn("next", contract["state_contract"][0])

    def test_policies_approved_contract_drops_long_previous_descriptions(self):
        spec = {
            "meta": {"topic": "통합 알림"},
            "overview": {"scope": [], "principles": []},
            "actors": [{"id": "ACT-NTF-001", "name": "고객", "description": "긴 설명" * 40}],
            "usecases": [{"id": "US-NTF-001", "actor": "고객", "name": "통합 알림 확인", "process_target": "Y"}],
            "states": [{"id": "ST-NTF-001", "name": "확인 전", "description": "긴 상태" * 40, "next_action": "확인한다."}],
            "processes": [
                {
                    "id": "PR-NTF-001",
                    "usecase_id": "US-NTF-001",
                    "name": "알림 목록 확인",
                    "description": "고객이 알림 목록을 확인하고 처리 기준을 선택한다. " * 5,
                }
            ],
            "functions": [
                {
                    "id": "FN-NTF-001",
                    "process_id": "PR-NTF-001",
                    "name": "알림 목록 조회",
                    "description": "알림 목록과 읽음 상태, 후속 업무 연결 정보를 산출한다. " * 5,
                }
            ],
        }

        contract = approved_contract_for_prompt(PoliciesAgent(), spec, topic_runtime())

        self.assertIn("process_contract", contract)
        self.assertIn("intent", contract["process_contract"][0])
        self.assertNotIn("description", contract["process_contract"][0])
        self.assertLessEqual(len(contract["process_contract"][0]["intent"]), 62)
        self.assertIn("function_contract", contract)
        self.assertIn("result", contract["function_contract"][0])
        self.assertLessEqual(len(contract["function_contract"][0]["result"]), 62)

    def test_inspector_approved_contract_uses_id_index_not_long_text(self):
        spec = {
            "meta": {"topic": "통합 알림"},
            "overview": {"scope": ["고객이 통합 알림을 확인한다."], "principles": [{"name": "간결한 알림"}]},
            "terms": [{"id": f"TM-NTF-{index:03d}", "name": f"용어 {index}"} for index in range(1, 40)],
            "actors": [{"id": "ACT-NTF-001", "name": "고객", "description": "긴 설명" * 50}],
            "usecases": [
                {"id": f"US-NTF-{index:03d}", "actor": "고객", "name": f"알림 확인 {index}", "process_target": "Y"}
                for index in range(1, 70)
            ],
            "states": [{"id": "ST-NTF-001", "name": "확인 전"}],
            "processes": [{"id": "PR-NTF-001", "usecase_id": "US-NTF-001", "name": "알림 확인"}],
            "functions": [{"id": "FN-NTF-001", "process_id": "PR-NTF-001", "name": "알림 조회"}],
        }

        contract = json_approved_contract(spec, "09_policies")

        self.assertLessEqual(len(contract["terms"]), 18)
        self.assertLessEqual(len(contract["usecases"]), 46)
        self.assertNotIn("description", contract["actors"][0])
        self.assertIn("policy_groups", contract)


if __name__ == "__main__":
    unittest.main()
