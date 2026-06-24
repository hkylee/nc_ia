import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.chapter_agents import (
    diversify_mock_repeated_function_details,
    ensure_function_process_coverage,
    ensure_mock_function_density_coverage,
)
from src.llm_client import (
    LLMClient,
    mock_final_revision_patch_payload,
    mock_function_description,
    mock_generate_json,
    mock_naturalize_text,
    mock_refine_function_name,
    mock_repair_overview,
    mock_repair_policy_detail,
    mock_repair_process,
)
from src.dev_qa_agent import dev_qa_action_check_schema, dev_qa_review_schema
from src.policy_inspector import (
    InspectionFinding,
    InspectionReport,
    count_strict_policy_vague_phrases,
    finding_actionability_issues,
    inspect_policy_json_spec,
    merge_inspection_reports,
)
from src.validator import validate_policy_specificity


class MockLLMClientTest(unittest.TestCase):
    def test_env_mock_mode_overrides_llm_without_api_key(self):
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="llm", llm_model="", reasoning_effort=""))

        self.assertEqual("mock", client.writer_mode)
        self.assertTrue(client.enabled)
        self.assertEqual("mock-policy-agent", client.model)

    def test_explicit_llm_can_disable_global_mock_env(self):
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": "test-key"}, clear=False):
            client = LLMClient.from_context(
                SimpleNamespace(writer_mode="llm", llm_model="gpt-5.5", reasoning_effort="", disable_mock_env=True)
            )

        self.assertEqual("llm", client.writer_mode)
        self.assertEqual("gpt-5.5", client.model)

    def test_mock_inspector_direct_call_returns_context_warning(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {"type": "string", "enum": ["pass", "warn", "fail"]},
                "summary": {"type": "string"},
                "findings": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["status", "summary", "findings"],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            payload = client.generate_json(
                schema_name="policy_json_inspection",
                schema=schema,
                instructions="inspect",
                input_messages=[{"role": "user", "content": "검수해줘"}],
            )

        self.assertEqual("warn", payload["status"])
        self.assertEqual([], payload["findings"])

    def test_mock_chapter_uses_local_draft_from_prompt(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "terms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                        "required": ["id", "name"],
                    },
                }
            },
            "required": ["terms"],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            payload = client.generate_json(
                schema_name="terms_chapter",
                schema=schema,
                instructions="write",
                input_messages=[
                    {
                        "role": "user",
                        "content": '로컬 초안 JSON:\n{"terms":[{"id":"TM-001","name":"상태"}]}',
                    }
                ],
            )

        self.assertEqual([{"id": "TM-001", "name": "상태"}], payload["terms"])

    def test_mock_revision_intent_uses_selected_text_instead_of_context_summary(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "history_change": {"type": "string"},
                "target_sections": {"type": "array", "items": {"type": "string"}},
                "replacements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "find": {"type": "string"},
                            "replace": {"type": "string"},
                        },
                        "required": ["find", "replace"],
                    },
                },
                "append_title": {"type": "string"},
                "append_items": {"type": "array", "items": {"type": "string"}},
                "target_replacement_html": {"type": "string"},
            },
            "required": [
                "summary",
                "history_change",
                "target_sections",
                "replacements",
                "append_title",
                "append_items",
                "target_replacement_html",
            ],
        }
        prompt = """
사용자 수정 요청:
간소화버전 으로 변경해줘

선택 영역 정보:
- 선택 위치: 표지
- 선택 텍스트:
간소화 버전
- 선택 블록 텍스트:
문서 구분 간소화 버전
- 선택 블록 HTML, target_replacement_html 작성 시 우선 교체 대상:
<tr><th>문서 구분</th><td>간소화 버전</td></tr>
선택 영역을 우선 수정하되, 연결성 유지를 위해 필요한 관련 장 보완은 replacements로 최소 범위만 작성한다.

정책서 구조 및 선택 장 요약:
{
  "selected_sections": ["overview"],
  "target_selection": {"text": "간소화 버전"},
  "outline": []
}
"""

        payload = mock_generate_json(
            schema_name="revision_intent",
            schema=schema,
            instructions="revise",
            input_messages=[{"role": "user", "content": prompt}],
        )

        self.assertNotEqual("Mock LLM 응답입니다.", payload["summary"])
        self.assertEqual([{"find": "간소화 버전", "replace": "간소화버전"}], payload["replacements"])
        self.assertIn("<td>간소화버전</td>", payload["target_replacement_html"])

    def test_mock_dev_qa_action_check_does_not_auto_resolve_without_document_evidence(self):
        prompt = """
아래 보완 요청 항목들이 현재 정책서에 반영됐는지 확인해 주세요.

문서 파일:
NC_추천_정책서_간소화_v0.3.html

확인할 보완 요청 항목:
{
  "items": [
    {
      "item_key": "qa-001",
      "action_type": "add",
      "title": "예외 흐름 보강",
      "target_location": "3. 유즈케이스 정의 > 상태 전이표",
      "current_content": "",
      "desired_change": "추천 실패 시 고객에게 재시도 가능 여부와 대체 탐색 경로를 고지한다.",
      "recommendation": "상태 전이표에 추천 실패와 대체 탐색 경로를 추가한다."
    }
  ]
}

현재 정책서 본문 텍스트:
추천 정책서는 고객에게 추천 상품을 보여준다.
"""

        payload = mock_generate_json(
            schema_name="dev_qa_action_check",
            schema=dev_qa_action_check_schema(),
            instructions="check",
            input_messages=[{"role": "user", "content": prompt}],
        )

        self.assertEqual("open", payload["items"][0]["status"])
        self.assertIn("명시적 문구", payload["items"][0]["evidence"])

    def test_mock_dev_qa_action_check_resolves_only_when_exact_desired_text_exists(self):
        prompt = """
확인할 보완 요청 항목:
{
  "items": [
    {
      "item_key": "qa-002",
      "action_type": "add",
      "title": "예외 흐름 보강",
      "target_location": "3. 유즈케이스 정의 > 상태 전이표",
      "current_content": "",
      "desired_change": "추천 실패 시 고객에게 재시도 가능 여부와 대체 탐색 경로를 고지한다.",
      "recommendation": "상태 전이표에 추천 실패와 대체 탐색 경로를 추가한다."
    }
  ]
}

현재 정책서 본문 텍스트:
상태 전이표에는 추천 실패 시 고객에게 재시도 가능 여부와 대체 탐색 경로를 고지한다.
"""

        payload = mock_generate_json(
            schema_name="dev_qa_action_check",
            schema=dev_qa_action_check_schema(),
            instructions="check",
            input_messages=[{"role": "user", "content": prompt}],
        )

        self.assertEqual("resolved", payload["items"][0]["status"])
        self.assertIn("그대로 확인", payload["items"][0]["evidence"])

    def test_mock_dev_qa_review_uses_document_signals_instead_of_canned_findings(self):
        prompt = """
문서 메타:
{
  "file_name": "NC_테스트_정책서_간소화_v0.1.html",
  "topic": "테스트",
  "template_type": "simple"
}

문서 구조 신호:
{
  "history_count_hint": 0,
  "actor_count": 1,
  "usecase_count": 2,
  "state_count": 0,
  "process_count": 0,
  "function_count": 0,
  "policy_group_count": 1,
  "policy_item_count": 0,
  "tbd_or_ambiguous_count": 2,
  "has_mermaid": false,
  "text_length": 1200
}

정책서 본문 텍스트:
고객은 추천을 확인한다. 정책은 TBD로 정한다.
"""

        payload = mock_generate_json(
            schema_name="dev_qa_review",
            schema=dev_qa_review_schema(),
            instructions="review",
            input_messages=[{"role": "user", "content": prompt}],
        )

        titles = [item["title"] for item in payload["development_findings"] + payload["qa_findings"]]
        self.assertIn("프로세스-기능 연결 기준 보강 필요", titles)
        self.assertIn("예외·실패·제한 흐름 보강 필요", titles)
        self.assertNotIn("Mock 개발 관점 점검", titles)
        self.assertLess(payload["score"], 82)
        self.assertIn("구조 신호", payload["summary"])

    def test_mock_topic_learning_uses_knowledge_pack_and_requirement_details(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "topic_understanding": {"type": "string"},
                "scope_boundary": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "direct_scope": {"type": "array", "items": {"type": "string"}},
                        "related_but_not_core": {"type": "array", "items": {"type": "string"}},
                        "excluded_or_later": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["direct_scope", "related_but_not_core", "excluded_or_later"],
                },
                "customer_tasks": {"type": "array", "items": {"type": "string"}},
                "requirement_implications": {"type": "array", "items": {"type": "string"}},
                "reference_implications": {"type": "array", "items": {"type": "string"}},
                "bss_implications": {"type": "array", "items": {"type": "string"}},
                "policy_risks": {"type": "array", "items": {"type": "string"}},
                "chapter_focus": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "overview": {"type": "string"},
                        "terms": {"type": "string"},
                        "actors": {"type": "string"},
                        "usecases": {"type": "string"},
                        "usecase_diagram": {"type": "string"},
                        "state": {"type": "string"},
                        "process": {"type": "string"},
                        "functions": {"type": "string"},
                        "policies": {"type": "string"},
                        "final_check": {"type": "string"},
                    },
                    "required": [
                        "overview",
                        "terms",
                        "actors",
                        "usecases",
                        "usecase_diagram",
                        "state",
                        "process",
                        "functions",
                        "policies",
                        "final_check",
                    ],
                },
            },
            "required": [
                "topic_understanding",
                "scope_boundary",
                "customer_tasks",
                "requirement_implications",
                "reference_implications",
                "bss_implications",
                "policy_risks",
                "chapter_focus",
            ],
        }
        knowledge = {
            "authoritative_signals": {
                "direct_scope": ["회원 가입과 탈퇴 요청의 접수, 인증, 결과 고지"],
            },
            "topic_axes": {
                "customer_jobs": ["고객은 가입 가능 여부와 탈퇴 후 복구 가능 여부를 확인한다."],
            },
            "candidate_inventory": {
                "usecase_candidates": ["회원 가입 신청", "회원 탈퇴 요청"],
                "policy_item_candidates": ["인증번호 유효시간", "탈퇴 유예 기간"],
                "bss_touchpoints": ["BSS 가입 상태 변경", "탈퇴 이력 저장"],
            },
            "chapter_guidance": {
                "policies": ["인증, 유예 기간, 이력 저장 기준을 정책 항목으로 분리한다."],
            },
        }
        requirements = [
            {
                "detail_name": "인증번호 유효시간",
                "detail_description": "인증번호는 10분 동안만 유효하고 만료 시 재인증을 요구한다.",
                "depth4": "회원 인증",
            },
            {
                "detail_name": "탈퇴 처리 상태 반영",
                "detail_description": "탈퇴 완료 후 BSS 회원 상태를 변경하고 이력을 저장한다.",
                "depth4": "회원 탈퇴",
            },
        ]
        payload = mock_generate_json(
            schema_name="topic_learning",
            schema=schema,
            instructions="learn",
            input_messages=[
                {
                    "role": "user",
                    "content": (
                        '{"topic":"회원 가입/탈퇴"}\n'
                        "사전 주제 Knowledge Pack:\n"
                        + json.dumps(knowledge, ensure_ascii=False)
                        + "\n요구사항 요약:\n"
                        + json.dumps(requirements, ensure_ascii=False)
                    ),
                }
            ],
        )

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("인증번호 유효시간", serialized)
        self.assertIn("BSS 가입 상태 변경", serialized)
        self.assertIn("회원 가입 신청", serialized)
        self.assertIn("인증, 유예 기간, 이력 저장 기준", payload["chapter_focus"]["policies"])

    def test_mock_state_covers_all_usecases(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "states": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "next_action": {"type": "string"},
                        },
                        "required": ["id", "name", "description", "next_action"],
                    },
                },
                "state_transitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "usecase_ids": {"type": "array", "items": {"type": "string"}},
                            "current_state": {"type": "string"},
                            "event": {"type": "string"},
                            "next_state": {"type": "string"},
                            "criteria": {"type": "string"},
                        },
                        "required": ["usecase_ids", "current_state", "event", "next_state", "criteria"],
                    },
                },
            },
            "required": ["states", "state_transitions"],
        }
        usecase_contract = {
            "allowed_transition_usecase_ids": [
                {"id": "US-MCK-CS-001", "name": "고객 요청 접수", "actor": "고객"},
                {"id": "US-MCK-BSS-001", "name": "업무 조건 판정", "actor": "BSS"},
            ]
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            payload = client.generate_json(
                schema_name="state_chapter",
                schema=schema,
                instructions="write",
                input_messages=[
                    {
                        "role": "user",
                        "content": "승인된 유즈케이스 계약:\n" + json.dumps(usecase_contract, ensure_ascii=False),
                    }
                ],
            )

        covered = {
            value
            for transition in payload["state_transitions"]
            for value in transition["usecase_ids"]
        }
        self.assertEqual({"US-MCK-CS-001", "US-MCK-BSS-001"}, covered)
        self.assertEqual("요청 접수 완료", payload["state_transitions"][0]["event"])
        self.assertNotEqual("고객 요청 접수", payload["state_transitions"][0]["event"])

    def test_mock_functions_varies_details_and_reuses_processes(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "functions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "process_id": {"type": "string"},
                            "process_ids": {"type": "array", "items": {"type": "string"}},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "details": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id", "process_id", "process_ids", "name", "description", "details"],
                    },
                }
            },
            "required": ["functions"],
        }
        local_payload = {
            "functions": [
                {
                    "id": f"FN-MCK-{index:03d}",
                    "process_id": f"PR-MCK-{index:03d}",
                    "process_ids": [f"PR-MCK-{index:03d}"],
                    "name": f"{index}번 처리 기능",
                    "description": "처리한다.",
                    "details": ["조회", "검증", "저장", "결과 안내"],
                }
                for index in range(1, 9)
            ]
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            payload = client.generate_json(
                schema_name="functions_chapter",
                schema=schema,
                instructions="write",
                input_messages=[
                    {
                        "role": "user",
                        "content": "로컬 초안 JSON:\n" + json.dumps(local_payload, ensure_ascii=False),
                    }
                ],
            )

        signatures = {tuple(function["details"]) for function in payload["functions"]}
        reused = [function for function in payload["functions"] if len(function["process_ids"]) > 1]
        names = [function["name"] for function in payload["functions"]]
        self.assertGreater(len(signatures), 1)
        self.assertTrue(reused)
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(any(function["name"].endswith(" 기능") for function in payload["functions"]))

    def test_mock_policy_writer_varies_policy_detail_patterns(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "policy_groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["id", "name", "description"],
                    },
                },
                "policy_details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "policy_id": {"type": "string"},
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["id", "policy_id", "name", "content"],
                    },
                },
            },
            "required": ["policy_groups", "policy_details"],
        }
        local_payload = {
            "policy_groups": [
                {"id": "PG-MCK-ACC-001", "name": "접근 정책", "description": "정책을 관리한다."},
                {"id": "PG-MCK-VAL-001", "name": "검증 정책", "description": "정책을 관리한다."},
            ],
            "policy_details": [
                {
                    "id": f"PI-MCK-{index:03d}",
                    "policy_id": "PG-MCK-ACC-001" if index <= 16 else "PG-MCK-VAL-001",
                    "name": "적용 기준",
                    "content": "업무별 기준에 따라 처리한다.",
                }
                for index in range(1, 33)
            ],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            payload = client.generate_json(
                schema_name="policies_chapter",
                schema=schema,
                instructions="write",
                input_messages=[
                    {
                        "role": "user",
                        "content": "로컬 초안 JSON:\n" + json.dumps(local_payload, ensure_ascii=False),
                    }
                ],
            )

        prefixes = {detail["content"][:32] for detail in payload["policy_details"]}
        names = {detail["name"] for detail in payload["policy_details"]}
        self.assertGreaterEqual(len(prefixes), 14)
        self.assertGreater(len(names), 14)
        self.assertFalse(validate_policy_specificity(payload))

    def test_mock_policy_detail_preserves_meaningful_name_without_suffix(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-AUT-001-03",
                "policy_id": "PG-MBR-AUT-001",
                "name": "인증번호 유효시간 - 결과 확정",
                "content": "업무별 기준에 따라 처리한다.",
            },
            2,
        )

        self.assertEqual("인증번호 유효시간", detail["name"])
        self.assertEqual("인증 유효 시간은 10분이며 만료되면 재인증을 요구하고 실패 이력을 저장한다.", detail["content"])

    def test_mock_text_naturalizer_fixes_common_korean_artifacts(self):
        self.assertEqual("회원 가입·탈퇴는 내부 기준으로 구성한다.", mock_naturalize_text("회원 가입탈퇴은 내부 기준으로 구성한다."))
        self.assertEqual("회원 가입·탈퇴를 완료한다.", mock_naturalize_text("회원 가입탈퇴을 완료한다."))
        self.assertEqual("예외 사유 분류를 수행한다.", mock_naturalize_text("예외 사유 분류을 수행한다."))
        self.assertEqual("후속 업무 선택 정보 구성", mock_refine_function_name("후속 업무 선택 처리 기능 2", 0))
        self.assertEqual(
            "가입·신청 조건 정보 구성은 대상 조건 구성, 권한 상태 검증, 결과 안내 구성을 순서대로 처리한다.",
            mock_function_description("가입·신청 조건 정보 구성", ("대상 조건 구성", "권한 상태 검증", "결과 안내 구성")),
        )

    def test_mock_function_name_collision_uses_semantic_suffix(self):
        self.assertEqual("조회·탐색 조건 검증", mock_refine_function_name("조회·탐색 정보 구성 2", 0))
        self.assertEqual("조회·탐색 결과 구성", mock_refine_function_name("조회·탐색 정보 구성 3", 0))

    def test_mock_overview_repair_never_blanks_principles(self):
        repaired = mock_repair_overview(
            {
                "scope": ["기존 범위"] * 6,
                "principles": [
                    {"name": "기존 원칙", "description": "기존 설명"},
                    "고객 안내 기준: 처리 결과를 고객에게 안내한다.",
                ],
            },
            "설계원칙을 보완해줘",
        )

        self.assertTrue(repaired["principles"])
        self.assertTrue(all(item["name"] and item["description"] for item in repaired["principles"]))
        self.assertLessEqual(len(repaired["scope"]), 6)

    def test_mock_policy_detail_content_reads_like_sentence(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-ACC-001-01",
                "policy_id": "PG-MBR-ACC-001",
                "name": "접근 허용 범위 - 요청 접수",
                "content": "업무별 기준에 따라 처리한다.",
            },
            0,
        )

        self.assertEqual("접근 허용 범위", detail["name"])
        self.assertTrue(detail["content"].startswith("접근 허용 범위는 "))
        self.assertNotIn(" - ", detail["content"])
        self.assertNotIn("요청 접수 시", detail["content"])

    def test_mock_policy_detail_avoids_mechanical_prefix(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MCK-BSS-001-01",
                "policy_id": "PG-MCK-BSS-001",
                "name": "반영 기준",
                "content": "업무별 기준에 따라 처리한다.",
            },
            3,
        )

        self.assertEqual("BSS 연계 반영 기준", detail["name"])
        self.assertTrue(detail["content"].startswith("BSS 반영은 "))
        self.assertNotIn("예외 처리 시", detail["content"])
        self.assertNotIn("기준은 BSS 반영은", detail["content"])

    def test_mock_policy_detail_does_not_repeat_standard_subject_before_result(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-VAL-001-04",
                "policy_id": "PG-MBR-VAL-001",
                "name": "재검증 기준",
                "content": "업무별 기준에 따라 처리한다.",
            },
            5,
        )

        self.assertEqual("재검증 기준", detail["name"])
        self.assertNotIn("기준은 처리 결과가", detail["content"])
        self.assertNotIn("조건 판정 시", detail["content"])

    def test_mock_policy_detail_preserves_specific_existing_content(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-AUT-001-02",
                "policy_id": "PG-MBR-AUT-001",
                "name": "인증 가능 횟수",
                "content": "동일 업무 세션 기준 최대 5회까지 허용한다.",
            },
            1,
        )

        self.assertEqual("인증 가능 횟수", detail["name"])
        self.assertEqual("동일 업무 세션 기준 최대 5회까지 허용한다.", detail["content"])

    def test_mock_policy_detail_rewrites_vague_authority_condition(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-ACC-001-02",
                "policy_id": "PG-MBR-ACC-001",
                "name": "권한 제한 대상",
                "content": "대리 처리, 법정대리인, 법인, 미성년, 제한 고객은 업무별 권한 기준을 충족한 경우에만 진행한다.",
            },
            1,
        )

        self.assertEqual("권한 제한 대상", detail["name"])
        self.assertIn("본인확인", detail["content"])
        self.assertIn("법정대리인 동의", detail["content"])
        self.assertNotIn("업무별 권한 기준", detail["content"])

    def test_mock_policy_detail_uses_retention_content_for_storage_period(self):
        detail = mock_repair_policy_detail(
            {
                "id": "PI-MBR-DATA-001-03",
                "policy_id": "PG-MBR-DATA-001",
                "name": "보관 기간",
                "content": "보관 기간은 법령, 내부 기준, 감사 필요성, 고객 분쟁 가능성을 기준으로 적용한다.",
            },
            2,
        )

        self.assertEqual("보관 기간", detail["name"])
        self.assertIn("법정 보관 사유", detail["content"])
        self.assertIn("파기 이력", detail["content"])
        self.assertNotIn("내부 기준", detail["content"])

    def test_mock_policy_detail_scopes_generic_name_with_policy_group(self):
        result_detail = mock_repair_policy_detail(
            {
                "id": "PI-MCK-RSLT-001-01",
                "policy_id": "PG-MCK-RSLT-001",
                "name": "결과 구분",
                "content": "업무별 기준에 따라 처리한다.",
            },
            0,
        )
        notice_detail = mock_repair_policy_detail(
            {
                "id": "PI-MCK-NTC-001-01",
                "policy_id": "PG-MCK-NTC-001",
                "name": "결과 구분",
                "content": "업무별 기준에 따라 처리한다.",
            },
            1,
        )

        self.assertEqual("결과 구분", result_detail["name"])
        self.assertEqual("알림·고지 결과 구분", notice_detail["name"])

    def test_mock_policy_detail_varies_repeated_meaningful_names(self):
        details = [
            mock_repair_policy_detail(
                {
                    "id": f"PI-MCK-RQCOV-{index:03d}",
                    "policy_id": "PG-MCK-RQCOV-001",
                    "name": "조회·탐색 상태·제한 기준",
                    "content": "업무별 기준에 따라 처리한다.",
                },
                index,
            )
            for index in range(12)
        ]

        spec = {
            "meta": {"template_type": "simple"},
            "policy_groups": [
                {"id": "PG-MCK-RQCOV-001", "name": "조회·탐색 정책", "description": "조회 기준을 정의한다."}
            ],
            "policy_details": details,
        }

        self.assertFalse(validate_policy_specificity(spec))
        self.assertGreater(len({detail["name"] for detail in details}), 6)
        self.assertTrue(any("요청 접수 제한 기준" in detail["name"] for detail in details))

    def test_mock_policy_inspector_flags_mechanical_policy_text(self):
        spec = {
            "meta": {"template_type": "simple"},
            "policy_groups": [
                {"id": "PG-MCK-STAT-001", "name": "상태 정책", "description": "상태 기준을 정의한다."}
            ],
            "policy_details": [
                {
                    "id": "PI-MCK-STAT-001-01",
                    "policy_id": "PG-MCK-STAT-001",
                    "name": "상태 사용 기준 - 결과 확정",
                    "content": "결과 확정 시 상태 사용 기준은 판정 결과가 허용·제한·보류·실패 중 하나로 확정되면 상태를 전환한다.",
                }
            ]
            * 8,
        }
        client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))

        report = inspect_policy_json_spec(spec, llm_client=client, chapter_key="policies")
        titles = {finding.title for finding in report.findings}

        self.assertIn("정책 항목명 단계 suffix 반복", titles)
        self.assertIn("정책 항목 기계적 접두어", titles)

    def test_mock_process_repair_preserves_process_specific_focus(self):
        rows = [
            mock_repair_process(
                {
                    "id": "PR-MCK-001",
                    "name": "기준 정보 조회",
                    "description": "채널은 대상 정보와 기준 정보를 조회한다.",
                },
                0,
            ),
            mock_repair_process(
                {
                    "id": "PR-MCK-002",
                    "name": "처리 요청 접수",
                    "description": "고객 최종 확인 후 처리 요청을 접수하고 중복 요청을 제한한다.",
                },
                1,
            ),
        ]

        self.assertIn("조회 범위와 기준 정보", rows[0]["description"])
        self.assertIn("요청 접수 가능성과 중복 여부", rows[1]["description"])
        self.assertNotEqual(rows[0]["description"], rows[1]["description"])

    def test_mock_function_density_adds_complementary_process_functions(self):
        spec = {
            "meta": {"business_code": "MCK"},
            "processes": [
                {"id": f"PR-MCK-CS-001-0{index}", "name": f"{index}번 프로세스"}
                for index in range(1, 4)
            ],
            "functions": [
                {
                    "id": f"FN-MCK-AUTO-00{index}",
                    "process_id": f"PR-MCK-CS-001-0{index}",
                    "process_ids": [f"PR-MCK-CS-001-0{index}"],
                    "name": f"{index}번 처리",
                    "description": "조회, 검증, 저장 처리를 제공한다.",
                    "details": ["조회", "검증", "저장"],
                }
                for index in range(1, 4)
            ],
        }

        ensure_mock_function_density_coverage(spec)

        self.assertEqual(6, len(spec["functions"]))
        counts = {
            process["id"]: sum(process["id"] in function.get("process_ids", []) for function in spec["functions"])
            for process in spec["processes"]
        }
        self.assertEqual({"PR-MCK-CS-001-01": 2, "PR-MCK-CS-001-02": 2, "PR-MCK-CS-001-03": 2}, counts)

    def test_mock_json_inspector_uses_strict_local_findings(self):
        spec = {
            "meta": {"template_type": "simple"},
            "processes": [
                {"id": f"PR-MCK-{index:03d}", "usecase_id": "US-MCK-001", "name": f"{index}번 프로세스"}
                for index in range(1, 5)
            ],
            "functions": [
                {
                    "id": f"FN-MCK-{index:03d}",
                    "process_id": f"PR-MCK-{index:03d}",
                    "process_ids": [f"PR-MCK-{index:03d}"],
                    "name": f"{index}번 처리",
                    "description": "프로세스 수행에 필요한 조건 확인, 처리, 결과 구성을 제공한다.",
                    "details": ["조회", "검증", "저장"],
                }
                for index in range(1, 5)
            ],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            report = inspect_policy_json_spec(
                spec,
                template_type="simple",
                scope="functions",
                chapter_key="functions",
                topic="Mock Strict",
                llm_client=client,
                llm_required=True,
            )

        self.assertEqual("strict_mock", report.metrics["llm_inspector"]["status"])
        self.assertLess(report.score, 100)
        self.assertTrue(any(finding.title == "기능 설명 반복" for finding in report.findings))
        strict_findings = [
            finding
            for finding in report.findings
            if finding.category == "Mock strict"
        ]
        self.assertTrue(strict_findings)
        self.assertFalse(finding_actionability_issues(strict_findings[0]))

    def test_mock_policy_inspector_flags_vague_policy_items(self):
        spec = {
            "meta": {"template_type": "simple"},
            "policy_groups": [
                {"id": "PG-MCK-ACC-001", "name": "접근 정책", "description": "접근 기준을 정의한다."},
                {"id": "PG-MCK-VAL-001", "name": "검증 정책", "description": "검증 기준을 정의한다."},
            ],
            "policy_details": [
                {
                    "id": f"PI-MCK-ACC-{index:02d}",
                    "policy_id": "PG-MCK-ACC-001" if index <= 4 else "PG-MCK-VAL-001",
                    "name": f"{index}번 기준",
                    "content": "업무별 기준에 따라 처리한다.",
                }
                for index in range(1, 9)
            ],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            report = inspect_policy_json_spec(
                spec,
                template_type="simple",
                scope="policies",
                chapter_key="policies",
                topic="Mock Strict",
                llm_client=client,
                llm_required=True,
            )

        self.assertEqual("strict_mock", report.metrics["llm_inspector"]["status"])
        self.assertLess(report.score, 85)
        self.assertTrue(any(finding.title == "정책 항목 판단값 부족" for finding in report.findings))
        self.assertTrue(any(finding.is_quality_gate for finding in report.findings))

    def test_mock_policies_stage_rechecks_cross_chapter_quality(self):
        spec = {
            "meta": {"template_type": "simple"},
            "processes": [
                {
                    "id": f"PR-MCK-{index:03d}",
                    "usecase_id": "US-MCK-001",
                    "name": f"{index}번 프로세스",
                    "description": "고객 요청을 확인하고 처리 결과를 안내한다.",
                    "related_policies": ["PG-MCK-ACC-001 접근 정책", "PG-MCK-VAL-001 검증 정책"],
                }
                for index in range(1, 7)
            ],
            "functions": [
                {
                    "id": "FN-MCK-001",
                    "process_id": "PR-MCK-001",
                    "process_ids": ["PR-MCK-001"],
                    "name": "상품 정보 정보 구성",
                    "description": "상품 정보를 구성하고 고객 표시 결과를 만든다.",
                    "details": ["상품 정보 구성", "고객 표시 구성"],
                }
            ],
            "policy_groups": [
                {"id": "PG-MCK-ACC-001", "name": "접근 정책", "description": "접근 기준을 정의한다."},
                {"id": "PG-MCK-VAL-001", "name": "검증 정책", "description": "검증 기준을 정의한다."},
            ],
            "policy_details": [
                {
                    "id": f"PI-MCK-ACC-{index:02d}",
                    "policy_id": "PG-MCK-ACC-001" if index <= 4 else "PG-MCK-VAL-001",
                    "name": f"{index}번 기준",
                    "content": "인증번호 유효시간 기준의 기본 관점에서 인증 유효 시간은 10분이며 만료되면 재인증을 요구한다.",
                }
                for index in range(1, 9)
            ],
        }
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": ""}, clear=False):
            client = LLMClient.from_context(SimpleNamespace(writer_mode="mock", llm_model="", reasoning_effort=""))
            report = inspect_policy_json_spec(
                spec,
                template_type="simple",
                scope="policies",
                chapter_key="policies",
                topic="Mock Strict",
                llm_client=client,
                llm_required=True,
            )

        titles = {finding.title for finding in report.findings}
        self.assertLess(report.score, 100)
        self.assertIn("프로세스 정책 연결 반복", titles)
        self.assertIn("정책 항목 관점 문장 반복", titles)
        self.assertIn("기능명 반복 토큰", titles)

    def test_final_report_merge_keeps_json_strict_findings(self):
        primary = InspectionReport(
            status="pass",
            score=100,
            scope="full",
            checked_at="2026-05-06T00:00:00",
            summary="ok",
            findings=[],
            metrics={},
        )
        secondary = InspectionReport(
            status="warn",
            score=89,
            scope="full",
            checked_at="2026-05-06T00:00:01",
            summary="json warn",
            findings=[
                InspectionFinding(
                    "warn",
                    "Mock strict",
                    "정책 항목 관점 문장 반복",
                    "반복 문장입니다.",
                    "직접 기준 문장으로 수정하세요.",
                    is_quality_gate=True,
                )
            ],
            metrics={},
        )

        merged = merge_inspection_reports(primary, secondary, source_key="json_final_inspector")

        self.assertEqual("warn", merged.status)
        self.assertLess(merged.score, 100)
        self.assertEqual(1, len(merged.findings))
        self.assertIn("json_final_inspector", merged.metrics)

    def test_mock_final_revision_updates_function_details_and_names(self):
        prompt = (
            "Final Inspector 보완 요청:\n"
            + json.dumps(
                {
                    "by_chapter": {
                        "functions": [
                            {"title": "기능 세부 구성 반복", "target_path": "current_chapter.functions[*].details"},
                            {"title": "기능명 반복 토큰", "target_path": "current_chapter.functions[*].name"},
                        ]
                    }
                },
                ensure_ascii=False,
            )
            + "\n\n현재 정책서 JSON 요약:\n"
            + json.dumps(
                {
                    "functions": [
                        {
                            "id": f"FN-MCK-{index:03d}",
                            "name": "조회·탐색 정보 정보 구성",
                            "description": "프로세스 수행에 필요한 조회, 검증, 저장 처리를 제공한다.",
                            "details": ["조회", "검증", "저장", "결과 안내"],
                        }
                        for index in range(1, 13)
                    ]
                },
                ensure_ascii=False,
            )
        )

        payload = mock_final_revision_patch_payload(prompt)
        name_updates = [item for item in payload["updates"] if item.get("field") == "name"]
        detail_updates = [item for item in payload["updates"] if item.get("field") == "details"]

        self.assertTrue(name_updates)
        self.assertTrue(detail_updates)
        self.assertTrue(all("정보 정보" not in item.get("value", "") for item in name_updates))
        self.assertTrue(all(item.get("values") != ["조회", "검증", "저장", "결과 안내"] for item in detail_updates))

    def test_mock_final_revision_preserves_strong_policy_detail_content(self):
        strong_content = (
            "가입·변경 업무 다국어 제공은 언어, 쉬운모드, 홈 우선 영역, 추천 노출 같은 개인화 항목을 "
            "고객이 직접 조정할 수 있게 한다. 변경값은 고객 단위로 저장하고 기본값 복원 또는 기기 변경 시 "
            "적용 기준을 함께 안내한다."
        )
        prompt = (
            "Final Inspector 보완 요청:\n"
            + json.dumps({"by_chapter": {"policies": [{"title": "정책 구체성 보완"}]}}, ensure_ascii=False)
            + "\n\n현재 정책서 JSON 요약:\n"
            + json.dumps(
                {
                    "policy_details": [
                        {
                            "id": "PI-LWI-RQCOV-001",
                            "policy_id": "PG-LWI-REQMAP-001",
                            "name": "가입·변경 업무 다국어 제공",
                            "content": strong_content,
                        },
                        {
                            "id": "PI-LWI-RQCOV-002",
                            "policy_id": "PG-LWI-REQMAP-001",
                            "name": "조건 판정",
                            "content": "업무별 기준에 따라 처리한다.",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        payload = mock_final_revision_patch_payload(prompt)
        content_updates = [item for item in payload["updates"] if item.get("collection") == "policy_details"]

        self.assertFalse(any(item.get("id") == "PI-LWI-RQCOV-001" for item in content_updates))
        self.assertTrue(any(item.get("id") == "PI-LWI-RQCOV-002" for item in content_updates))

    def test_mock_repair_policy_detail_uses_settings_specific_content(self):
        item = {
            "id": "PI-LWI-RQCOV-001",
            "policy_id": "PG-LWI-REQMAP-001",
            "name": "가입·변경 업무 다국어 제공",
            "content": (
                "가입·변경 업무 다국어 제공은 판정 결과가 허용·제한·보류·실패 중 하나로 확정되면 "
                "상태를 전환한다. 다음 상태와 후속 가능 여부를 함께 저장한다."
            ),
        }

        repaired = mock_repair_policy_detail(item, 0)

        self.assertIn("언어, 쉬운모드, 홈 우선 영역, 추천 노출", repaired["content"])
        self.assertNotIn("판정 결과가 허용·제한·보류·실패", repaired["content"])

    def test_mock_repair_policy_detail_uses_settings_security_content(self):
        item = {
            "id": "PI-LWI-RQCOV-002",
            "policy_id": "PG-LWI-REQMAP-001",
            "name": "자동 로그아웃/세션 정책 설정",
            "content": "업무별 기준에 따라 처리한다.",
        }

        repaired = mock_repair_policy_detail(item, 1)

        self.assertIn("세션 유지 시간", repaired["content"])
        self.assertIn("자동 로그아웃 조건", repaired["content"])

    def test_fallback_function_process_coverage_uses_specific_details(self):
        spec = {
            "meta": {"business_code": "MCK"},
            "processes": [
                {"id": f"PR-MCK-{index:03d}", "name": f"업무 진입 및 대상 확인 {index}"}
                for index in range(1, 12)
            ],
            "functions": [],
        }

        ensure_function_process_coverage(spec)
        signatures = [tuple(row.get("details", [])) for row in spec["functions"]]

        self.assertEqual(11, len(spec["functions"]))
        self.assertFalse(any(signature == ("조회", "검증", "저장", "결과 안내") for signature in signatures))
        self.assertLess(max(signatures.count(signature) for signature in set(signatures)), 11)

    def test_mock_repeated_function_details_are_diversified(self):
        spec = {
            "meta": {"business_code": "TST"},
            "processes": [
                {"id": f"PR-TST-CS-001-{index:02d}", "name": f"고객 요청 {index} 처리"}
                for index in range(1, 8)
            ],
            "functions": [
                {
                    "id": f"FN-TST-MOCK-{index:03d}",
                    "process_id": f"PR-TST-CS-001-{index:02d}",
                    "name": f"고객 요청 {index} 조건 판정",
                    "description": "반복 세부 기능 구성",
                    "details": ["상태값 조회", "가능 여부 판정", "알림 대상 구성"],
                }
                for index in range(1, 8)
            ],
        }

        diversify_mock_repeated_function_details(spec, threshold=6)
        signatures = [tuple(function["details"]) for function in spec["functions"]]

        self.assertGreater(len(set(signatures)), 1)
        self.assertTrue(all("반복 세부 기능 구성" not in function["description"] for function in spec["functions"]))

    def test_mock_density_function_ids_do_not_expose_mock_marker(self):
        spec = {
            "meta": {"business_code": "TST"},
            "processes": [
                {"id": f"PR-TST-CS-001-{index:02d}", "name": f"고객 요청 {index} 처리"}
                for index in range(1, 4)
            ],
            "functions": [],
        }

        ensure_mock_function_density_coverage(spec)

        self.assertTrue(spec["functions"])
        self.assertFalse(any("MOCK" in function["id"] for function in spec["functions"]))

    def test_mock_final_vague_phrase_count_does_not_flag_system_reference_context(self):
        text = "BSS 또는 연계 시스템 기준 정보는 입력 정보로 사용한다. 관련 정책 목록은 별도 표에서 참조한다."

        self.assertEqual(0, count_strict_policy_vague_phrases(text))


if __name__ == "__main__":
    unittest.main()
