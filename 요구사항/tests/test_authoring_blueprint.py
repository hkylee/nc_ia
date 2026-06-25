import unittest
import json
from types import SimpleNamespace

from src.authoring_blueprint import build_authoring_blueprint, stage_blueprint_for_prompt


class AuthoringBlueprintRequirementHierarchyTest(unittest.TestCase):
    def test_requirement_is_interpreted_into_hierarchy_candidates(self):
        requirement = SimpleNamespace(
            requirement_id="REQ-PLAN-001",
            source_number="1",
            depth3="요금제",
            depth4="요금제 변경",
            detail_name="요금제 변경 신청",
            detail_description="고객이 요금제 변경 가능 여부를 확인하고 BSS 검증 후 변경 신청 결과를 안내받는다.",
            parent_name="요금제 변경",
            parent_description="고객의 변경 요청을 처리하고 변경 이력을 저장한다.",
            requirement_type="필수",
            priority="P1",
            required="Y",
        )
        ctx = SimpleNamespace(
            topic="요금제 변경",
            business_code="PLAN",
            template_type="simple",
            requirements=[requirement],
            references=[],
        )

        blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=FakeEvidenceStore(),
            learning={},
            guideline={},
        )

        card = blueprint["requirement_cards"][0]
        self.assertNotIn("priority", card)
        self.assertIn("BSS 검증", card["source_excerpt"])
        self.assertIn("변경 신청 결과", card["source_excerpt"])

        strategy = blueprint["document_strategy"]
        self.assertIn("요금제 변경", strategy["topic_definition"])
        self.assertIn("누가 할 수 있는가?", strategy["core_policy_questions"])
        self.assertIn("액터", strategy["must_include"])
        self.assertIn("근거 없는 인터넷 일반론", strategy["must_not"])

        plan = blueprint["requirement_hierarchy_plan"]
        self.assertEqual(1, len(plan))
        row = plan[0]
        self.assertIn("고객", row["actor_candidates"])
        self.assertIn("BSS/연계 시스템", row["actor_candidates"])
        self.assertIn("요금제 변경 신청", row["usecase_candidate"])
        self.assertIn("검증·연계", row["process_candidate"])
        self.assertIn("자격 및 조건 검증", row["function_capabilities"])
        self.assertIn("처리 요청 및 결과 반영", row["function_capabilities"])
        self.assertIn("적용 대상·허용·제한 조건", row["policy_decision_axes"])

        process_pack = stage_blueprint_for_prompt(blueprint, "process")
        stage_plan = process_pack["stage_blueprint"]["requirement_hierarchy_plan"]
        self.assertEqual("REQ-PLAN-001", stage_plan[0]["requirement_id"])
        self.assertIn("BSS 검증", stage_plan[0]["source_excerpt"])
        self.assertIn("상세 요구사항명과 상세 요구사항 설명", blueprint["rule"])
        self.assertIn("요구사항 ID는 추적", blueprint["rule"])
        self.assertIn("요구사항은 본문에 그대로 복사하지 않는다", process_pack["requirement_hierarchy_rule"])
        self.assertIn("요구사항 ID와 우선순위는 추적용", process_pack["requirement_hierarchy_rule"])
        self.assertIn("density_profile", process_pack)
        self.assertIn("selected_requirement_cards", process_pack["stage_blueprint"])
        self.assertNotIn("priority_requirement_cards", process_pack["stage_blueprint"])

    def test_tk_process_function_guidance_flows_into_process_and_function_blueprints(self):
        requirement = SimpleNamespace(
            requirement_id="REQ-AI-001",
            source_number="1",
            depth3="AI",
            depth4="AI 검색",
            detail_name="AI 검색 질의 처리",
            detail_description="고객 질의를 해석하고 실행 가능한 검색 결과와 후속 행동을 안내한다.",
            parent_name="AI 검색",
            parent_description="AI 기반 탐색 업무를 정의한다.",
            requirement_type="필수",
            priority="P1",
            required="Y",
        )
        ctx = SimpleNamespace(
            topic="AI 검색",
            business_code="AIS",
            template_type="simple",
            requirements=[requirement],
            references=[],
        )
        learning = {
            "prelearned_knowledge": {
                "tk_process_function_guidance": [
                    {
                        "process_name": "AI Agent 진입 및 요청 입력",
                        "major_functions": ["공통 Agent 진입점 제공", "텍스트·음성 입력 제공"],
                    }
                ]
            }
        }

        blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=FakeEvidenceStore(),
            learning=learning,
            guideline={},
        )

        process_pack = stage_blueprint_for_prompt(blueprint, "process")
        function_pack = stage_blueprint_for_prompt(blueprint, "functions")

        self.assertIn("tk_process_function_guidance", blueprint["document_strategy"])
        self.assertIn("AI Agent 진입", " ".join(process_pack["stage_blueprint"]["analysis_focus"]["tk_process_function_guidance"]))
        self.assertIn("텍스트", " ".join(function_pack["stage_blueprint"]["analysis_focus"]["tk_process_function_guidance"]))

    def test_requirement_strategy_overrides_generic_learning_scope(self):
        requirement = SimpleNamespace(
            requirement_id="REQ-MBR-001",
            source_number="41",
            depth3="회원",
            depth4="회원 가입/탈퇴",
            detail_name="회원탈퇴 단계형 처리",
            detail_description="고객이 회원탈퇴 조건을 확인하고 인증 후 탈퇴 요청 결과를 안내받는다.",
            parent_name="회원 가입/탈퇴",
            parent_description="회원 가입과 탈퇴 요청을 처리한다.",
            requirement_type="필수",
            priority="P1",
            required="Y",
        )
        ctx = SimpleNamespace(
            topic="회원가입 · 회원탈퇴",
            business_code="MBR",
            template_type="simple",
            requirements=[requirement],
            references=[],
        )

        blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=FakeEvidenceStore(),
            learning={"scope_boundary": {"direct_scope": ["선택 주제 고객 과업과 처리 기준"]}},
            guideline={},
        )

        topic_definition = blueprint["document_strategy"]["topic_definition"]
        self.assertIn("회원가입 · 회원탈퇴", topic_definition)
        self.assertIn("회원탈퇴 단계형 처리", topic_definition)
        self.assertNotIn("선택 주제", topic_definition)

    def test_requirement_priority_is_not_used_as_blueprint_signal(self):
        base_kwargs = dict(
            requirement_id="REQ-AUTH-001",
            source_number="12",
            depth3="인증",
            depth4="인증 번호 검증",
            detail_name="인증 번호 검증 제한",
            detail_description="고객이 인증 번호를 입력하면 유효시간, 입력 가능 횟수, 실패 후 재시도 가능 여부를 확인한다.",
            parent_name="본인 인증",
            parent_description="본인 인증 수단과 실패 복구 기준을 정의한다.",
            requirement_type="필수",
            required="Y",
        )
        ctx_a = SimpleNamespace(
            topic="인증",
            business_code="AUTH",
            template_type="simple",
            requirements=[SimpleNamespace(**base_kwargs, priority="P1")],
            references=[],
        )
        ctx_b = SimpleNamespace(
            topic="인증",
            business_code="AUTH",
            template_type="simple",
            requirements=[SimpleNamespace(**base_kwargs, priority="P3")],
            references=[],
        )

        blueprint_a = build_authoring_blueprint(ctx=ctx_a, evidence_store=FakeEvidenceStore(), learning={}, guideline={})
        blueprint_b = build_authoring_blueprint(ctx=ctx_b, evidence_store=FakeEvidenceStore(), learning={}, guideline={})

        self.assertEqual(blueprint_a["meta"]["source_fingerprint"], blueprint_b["meta"]["source_fingerprint"])
        self.assertNotIn("priority", json.dumps(blueprint_a["requirement_cards"], ensure_ascii=False))
        self.assertNotIn("priority", json.dumps(blueprint_a["coverage_matrix"], ensure_ascii=False))

    def test_requirement_level_pdf_reference_is_authoritative_in_blueprint(self):
        ctx = SimpleNamespace(
            topic="주문/계약/가입",
            business_code="ORD",
            template_type="simple",
            requirements=[],
            references=[
                SimpleNamespace(
                    source_name="TK_ CH_주문_고객 주문경험 혁신 프로세스 재설계.pdf",
                    source_type="pdf",
                    category="guideline",
                    summary="주문 경험 재설계 과제정의",
                    signals=("주문 신청", "계약 가입", "BSS 반영"),
                    evidence=("고객 주문경험 혁신 프로세스 재설계",),
                    score=420,
                    text_chars=12000,
                    read_scope="full_document",
                )
            ],
        )

        blueprint = build_authoring_blueprint(ctx=ctx, evidence_store=FakeEvidenceStore(), learning={}, guideline={})
        card = blueprint["reference_cards"][0]

        self.assertEqual("authority:requirement_level_reference", card["source_authority"])
        self.assertEqual(1, card["authority_tier"])
        self.assertEqual(100, card["authority_score"])
        self.assertIn("요구사항급", card["source_precedence"])

    def test_large_stage_keeps_full_requirement_targets_and_spreads_detail_cards(self):
        requirements = [
            SimpleNamespace(
                requirement_id=f"REQ-ORD-{index:03d}",
                source_number=str(index),
                depth3="주문",
                depth4="주문/계약/가입",
                detail_name=f"주문 상세 요구 {index:03d}",
                detail_description=f"고객이 주문 조건 {index:03d}을 확인하고 처리 결과와 이력 기준을 안내받는다.",
                parent_name="주문/계약/가입",
                parent_description="주문 신청과 계약 가입 처리를 정의한다.",
                requirement_type="필수",
                priority="P1",
                required="Y",
            )
            for index in range(1, 91)
        ]
        ctx = SimpleNamespace(
            topic="주문/계약/가입",
            business_code="ORD",
            template_type="simple",
            requirements=requirements,
            references=[],
        )

        blueprint = build_authoring_blueprint(
            ctx=ctx,
            evidence_store=FakeEvidenceStore(),
            learning={},
            guideline={},
        )
        process_pack = stage_blueprint_for_prompt(blueprint, "process")
        stage_blueprint = process_pack["stage_blueprint"]

        self.assertEqual(90, stage_blueprint["target_requirement_count"])
        self.assertEqual(90, len(stage_blueprint["target_requirement_ids"]))
        selected_titles = [item["title"] for item in stage_blueprint["selected_requirement_cards"]]
        self.assertIn("주문 상세 요구 001", selected_titles)
        self.assertIn("주문 상세 요구 090", selected_titles)
        self.assertTrue(any("주문 상세 요구 04" in title for title in selected_titles))


class FakeEvidenceStore:
    def summary(self):
        return {"items": 0}

    def select(self, *, stage, topic, query_terms=(), required_kinds=(), limit=8):
        return []


if __name__ == "__main__":
    unittest.main()
