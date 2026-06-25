import unittest

from src.authoring_blueprint import stage_blueprint_for_prompt
from src.blueprint_quality import validate_blueprint_quality


class BlueprintQualityTest(unittest.TestCase):
    def test_complete_blueprint_passes_quality_gate(self):
        blueprint = sample_blueprint()
        learning = sample_learning()

        report = validate_blueprint_quality(blueprint, learning)

        self.assertTrue(report["passed"])
        self.assertEqual("passed", report["status"])
        self.assertEqual(0, report["gate_blocker_count"])

    def test_missing_scope_and_hard_stage_evidence_flags_risk(self):
        blueprint = sample_blueprint()
        learning = sample_learning()
        learning["scope_boundary"]["direct_scope"] = []
        for chapter in blueprint["chapter_blueprints"]:
            if chapter["stage"] == "process":
                chapter["evidence_ids"] = []

        report = validate_blueprint_quality(blueprint, learning)

        self.assertFalse(report["passed"])
        self.assertEqual("risk_flag", report["status"])
        self.assertGreater(report["gate_blocker_count"], 0)
        stages = {item["stage"] for item in report["findings"]}
        self.assertIn("overview", stages)
        self.assertIn("process", stages)

    def test_stage_prompt_receives_relevant_blueprint_quality_findings(self):
        blueprint = sample_blueprint()
        learning = sample_learning()
        for chapter in blueprint["chapter_blueprints"]:
            if chapter["stage"] == "policies":
                chapter["evidence_ids"] = []
        blueprint["quality_gate"] = validate_blueprint_quality(blueprint, learning)

        prompt_pack = stage_blueprint_for_prompt(blueprint, "policies")

        findings = prompt_pack["blueprint_quality_gate"]["stage_findings"]
        self.assertTrue(findings)
        self.assertEqual("policies", findings[0]["stage"])

    def test_requirement_gap_blocks_blueprint_pass(self):
        blueprint = sample_blueprint()
        learning = sample_learning()
        blueprint["meta"]["requirements_count"] = 0
        blueprint["requirement_cards"] = []
        blueprint["coverage_matrix"] = []
        blueprint["evidence_gaps"] = [
            {"kind": "requirements", "title": "관련 요구사항 없음", "detail": "직접 매칭된 요구사항이 없습니다."}
        ]

        report = validate_blueprint_quality(blueprint, learning)

        self.assertFalse(report["passed"])
        self.assertEqual("risk_flag", report["status"])
        self.assertGreater(report["gate_blocker_count"], 0)
        self.assertIn("직접 요구사항 매칭 없음", [item["title"] for item in report["findings"]])


def sample_learning():
    return {
        "topic": "상품 상세",
        "scope_boundary": {
            "direct_scope": ["고객이 상품 상세 정보를 확인하고 가입 가능 여부를 판단한다."],
            "related_but_not_core": ["주문 처리"],
            "excluded_or_later": ["결제 승인 상세"],
        },
        "customer_tasks": ["상품 정보를 확인한다."],
        "requirement_implications": ["상품 정보와 가입 조건을 정책서에 반영한다."],
        "bss_implications": ["BSS 가입 가능 여부와 고객 상태를 판정한다."],
        "policy_risks": ["노출 가능 정보와 가입 제한 조건을 정책으로 분리한다."],
        "chapter_focus": {
            "overview": "범위를 고정한다.",
            "usecases": "상위 고객 과업으로 정의한다.",
            "process": "유즈케이스별 절차로 분해한다.",
            "policies": "판단 기준을 선언한다.",
        },
    }


def sample_blueprint():
    stages = ["overview", "usecases", "state", "process", "functions", "policies", "process_detail", "function_detail"]
    return {
        "meta": {
            "topic": "상품 상세",
            "requirements_count": 1,
            "references_count": 2,
        },
        "source_profile": {
            "reference_categories": ["voc", "research", "ia", "strategy"],
        },
        "analysis_signals": {
            "customer_tasks": ["상품 정보를 확인한다."],
            "bss_touchpoints": ["BSS 가입 가능 여부를 판정한다."],
            "policy_decision_points": ["가입 제한 조건을 판단한다."],
        },
        "reference_cards": [{"id": "REF-001", "category": "voc"}],
        "coverage_matrix": [
            {
                "requirement_id": "REQ-001",
                "target_stages": ["overview", "usecases", "process", "functions", "policies"],
            }
        ],
        "chapter_blueprints": [
            {
                "stage": stage,
                "focus": f"{stage} focus",
                "must_cover": ["필수 기준"],
                "target_requirement_ids": ["REQ-001"] if stage != "state" else [],
                "evidence_ids": [f"REQ-001", f"REF-{stage}"],
                "analysis_focus": {"customer_tasks": ["상품 정보를 확인한다."]},
            }
            for stage in stages
        ],
        "evidence_gaps": [],
    }


if __name__ == "__main__":
    unittest.main()
