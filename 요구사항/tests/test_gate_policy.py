import unittest
from types import SimpleNamespace

from src.gate_policy import inspect_gate_decision
from src.policy_inspector import InspectionFinding


class GatePolicyTest(unittest.TestCase):
    def test_state_semantic_warning_blocks_hard_gate(self):
        report = SimpleNamespace(
            score=90,
            findings=[
                InspectionFinding(
                    "warn",
                    "정합성",
                    "분기 우선순위 부족",
                    "같은 현재값에서 예외 분기가 여러 개 발생합니다.",
                    "전이 기준의 우선순위를 추가하세요.",
                    tier="P2",
                )
            ],
            metrics={"score_breakdown": {"gate_blocker_count": 0}},
        )

        decision = inspect_gate_decision(report, "state", 85)

        self.assertFalse(decision["passed"])
        self.assertEqual(1, decision["gate_blocker_count"])


if __name__ == "__main__":
    unittest.main()
