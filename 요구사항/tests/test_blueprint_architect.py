import unittest
import json
from types import SimpleNamespace

from src.authoring_blueprint import stage_blueprint_for_prompt
from src.blueprint_architect import build_architecture_contract, compact_blueprint
from src.blueprint_quality import validate_blueprint_quality
from src.orchestrator import resume_authoring_blueprint


class BlueprintArchitectTest(unittest.TestCase):
    def test_architect_builds_execution_and_policy_chains(self):
        blueprint = sample_blueprint()
        contract = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )

        chain_names = {item["name"] for item in contract["hierarchy_chains"]}
        stages = {item["stage"] for item in contract["stage_contracts"]}

        self.assertIn("execution_chain", chain_names)
        self.assertIn("policy_chain", chain_names)
        self.assertIn("usecases", stages)
        self.assertIn("process", stages)
        self.assertIn("functions", stages)
        self.assertIn("policies", stages)
        self.assertTrue(contract["hierarchy_skeleton"]["usecase_groups"])
        self.assertTrue(contract["hierarchy_skeleton"]["function_capabilities"])
        self.assertTrue(contract["hierarchy_skeleton"]["policy_taxonomy"])

    def test_architect_uses_evidence_pack_for_skeleton_grounding(self):
        blueprint = sample_blueprint()
        contract = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
            evidence_store=FakeEvidenceStore(),
        )

        evidence_pack = contract["architecture_evidence_pack"]
        self.assertTrue(evidence_pack["cards"])
        self.assertTrue(evidence_pack["stage_card_ids"]["usecases"])
        self.assertTrue(contract["hierarchy_skeleton"]["usecase_groups"][0]["evidence_ids"])

    def test_stage_prompt_receives_architecture_contract(self):
        blueprint = sample_blueprint()
        blueprint["architecture_contract"] = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )

        prompt_pack = stage_blueprint_for_prompt(blueprint, "functions")

        architecture = prompt_pack["architecture_contract"]
        self.assertEqual("Blueprint Architect Agent", architecture["agent"])
        self.assertTrue(architecture["stage_contracts"])
        self.assertEqual("functions", architecture["stage_contracts"][0]["stage"])
        self.assertIn("function_capabilities", architecture["hierarchy_skeleton"])
        self.assertNotIn("policy_taxonomy", architecture["hierarchy_skeleton"])

    def test_stage_prompt_receives_first_draft_quality_plan(self):
        blueprint = sample_blueprint()
        blueprint["architecture_contract"] = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )

        prompt_pack = stage_blueprint_for_prompt(blueprint, "process")

        plan = prompt_pack["architecture_contract"]["first_draft_quality_plan"]
        self.assertTrue(plan["stage_checks"])
        self.assertEqual("process", plan["stage_checks"][0]["stage"])
        self.assertIn("유즈케이스", plan["stage_checks"][0]["must_produce"])
        self.assertTrue(plan["handoff_checks"])

    def test_resume_rejects_legacy_blueprint_without_first_draft_plan(self):
        blueprint = sample_blueprint()
        contract = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )
        contract.pop("first_draft_quality_plan", None)
        blueprint["architecture_contract"] = contract

        resumed = resume_authoring_blueprint({"meta": {"authoring_blueprint": blueprint}})

        self.assertIsNone(resumed)

    def test_policy_stage_prompt_receives_policy_taxonomy_skeleton(self):
        blueprint = sample_blueprint()
        blueprint["architecture_contract"] = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )

        prompt_pack = stage_blueprint_for_prompt(blueprint, "policies")

        skeleton = prompt_pack["architecture_contract"]["hierarchy_skeleton"]
        self.assertIn("function_capabilities", skeleton)
        self.assertIn("policy_taxonomy", skeleton)

    def test_architect_passes_requirement_derived_candidates_to_writers(self):
        blueprint = sample_blueprint()
        blueprint["requirement_hierarchy_plan"] = [
            {
                "requirement_id": "REQ-001",
                "title": "통합 알림 조회",
                "actor_candidates": ["고객", "BSS/연계 시스템"],
                "usecase_candidate": "통합 알림 조회",
                "process_candidate": "통합 알림 검증·연계 처리 흐름",
                "function_capabilities": ["대상 정보 조회", "결과 안내 및 고지"],
                "policy_decision_axes": ["채널·고지 기준", "이력 저장 기준"],
                "target_stages": ["usecases", "process", "functions", "policies"],
            }
        ]
        blueprint["architecture_contract"] = build_architecture_contract(
            ctx=SimpleNamespace(topic="통합 알림", template_type="simple"),
            authoring_blueprint=blueprint,
            learning=sample_learning(),
        )

        prompt_pack = stage_blueprint_for_prompt(blueprint, "policies")

        skeleton = prompt_pack["architecture_contract"]["hierarchy_skeleton"]
        core_design = prompt_pack["architecture_contract"]["core_design_map"]
        self.assertIn("requirement_derived_candidates", skeleton)
        self.assertEqual("REQ-001", skeleton["requirement_derived_candidates"][0]["requirement_id"])
        self.assertEqual("approved_baseline", core_design["approval_status"])
        self.assertTrue(core_design["required_handoff"]["policies"])
        self.assertEqual("REQ-001", core_design["design_rows"][0]["requirement_id"])
        self.assertIn("정책", core_design["design_rows"][0]["policy_candidates"][0])

    def test_blueprint_quality_flags_missing_architecture_as_warning_only(self):
        report = validate_blueprint_quality(sample_blueprint(), sample_learning())

        self.assertTrue(report["passed"])
        self.assertEqual(0, report["gate_blocker_count"])
        self.assertTrue(any(item["issue_id"] == "BP-ARCH-missing" for item in report["findings"]))

    def test_compact_blueprint_keeps_architect_prompt_bounded(self):
        blueprint = sample_blueprint()
        long_text = "회원 가입과 회원 탈퇴 요구사항을 업무 구조로 재구성한다. " * 120
        blueprint["analysis_signals"] = {
            "customer_tasks": [long_text for _ in range(80)],
            "policy_decision_points": [long_text for _ in range(80)],
            "bss_touchpoints": [long_text for _ in range(80)],
        }
        blueprint["coverage_matrix"] = [
            {
                "requirement_id": f"REQ-{index:03d}",
                "title": long_text,
                "target_stages": ["overview", "usecases", "process", "functions", "policies"],
                "evidence_ids": [f"EV-{index:03d}"],
            }
            for index in range(80)
        ]
        blueprint["requirement_hierarchy_plan"] = [
            {
                "requirement_id": f"REQ-{index:03d}",
                "title": long_text,
                "actor_candidates": [long_text],
                "usecase_candidate": long_text,
                "process_candidate": long_text,
                "function_capabilities": [long_text],
                "policy_decision_axes": [long_text],
                "target_stages": ["usecases", "process", "functions", "policies"],
            }
            for index in range(80)
        ]
        blueprint["chapter_blueprints"] = [
            {
                "stage": f"stage-{index}",
                "focus": long_text,
                "must_cover": [long_text for _ in range(20)],
                "target_requirement_ids": [f"REQ-{inner:03d}" for inner in range(40)],
                "evidence_ids": [f"EV-{inner:03d}" for inner in range(40)],
                "requirement_hierarchy_plan": blueprint["requirement_hierarchy_plan"],
                "analysis_focus": {"customer_tasks": [long_text for _ in range(40)]},
            }
            for index in range(30)
        ]

        payload = json.dumps(compact_blueprint(blueprint), ensure_ascii=False)

        self.assertLess(len(payload), 30000)
        self.assertIn("document_strategy", compact_blueprint(blueprint))
        self.assertIn("analysis_signals", compact_blueprint(blueprint))
        self.assertIn("chapter_blueprints", compact_blueprint(blueprint))


def sample_learning():
    return {
        "customer_tasks": ["고객이 알림을 확인한다."],
        "requirement_implications": ["통합 알림 조회와 처리 기준을 정책서에 반영한다."],
        "bss_implications": ["BSS 알림 대상 여부를 판정한다."],
        "policy_risks": ["알림 노출 채널과 보관 기간을 정책으로 분리한다."],
        "scope_boundary": {"direct_scope": ["통합 알림 조회와 처리"], "excluded_or_later": ["알림 발송 배치 상세"]},
        "chapter_focus": {
            "overview": "범위 고정",
            "usecases": "상위 업무 목적",
            "process": "유즈케이스별 절차",
            "functions": "처리 역량",
            "policies": "동작값",
        },
    }


def sample_blueprint():
    stages = ["overview", "usecases", "state", "process", "functions", "policies", "process_detail", "function_detail"]
    return {
        "meta": {"topic": "통합 알림", "requirements_count": 1, "references_count": 1},
        "source_profile": {"reference_categories": ["voc", "ia", "strategy"]},
        "analysis_signals": {
            "customer_tasks": ["통합 알림을 확인한다."],
            "bss_touchpoints": ["알림 대상 여부를 판정한다."],
            "policy_decision_points": ["알림 노출 채널을 판단한다."],
        },
        "reference_cards": [{"id": "REF-001", "category": "voc"}],
        "coverage_matrix": [
            {"requirement_id": "REQ-001", "target_stages": ["overview", "usecases", "process", "functions", "policies"]}
        ],
        "chapter_blueprints": [
            {
                "stage": stage,
                "focus": f"{stage} focus",
                "must_cover": ["필수 기준"],
                "target_requirement_ids": ["REQ-001"] if stage != "state" else [],
                "evidence_ids": ["REQ-001"],
                "analysis_focus": {"customer_tasks": ["통합 알림을 확인한다."]},
            }
            for stage in stages
        ],
        "evidence_gaps": [],
    }


class FakeEvidenceStore:
    def select(self, *, stage, topic, query_terms=(), required_kinds=(), limit=8):
        return [FakeEvidenceItem(f"REF-{stage.upper()}-001", stage)]


class FakeEvidenceItem:
    def __init__(self, item_id, stage):
        self.id = item_id
        self.stage = stage

    def to_prompt_dict(self, max_chars=300):
        return {
            "id": self.id,
            "kind": "requirement",
            "source": "fake",
            "title": f"{self.stage} 근거",
            "summary": f"{self.stage} 작성 근거",
            "signals": [self.stage],
            "evidence": [f"{self.stage} evidence"],
            "tags": [self.stage],
        }


if __name__ == "__main__":
    unittest.main()
