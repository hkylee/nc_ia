import unittest
from types import SimpleNamespace

from src.chapter_agents import (
    OverviewAgent,
    manual_review_feedback,
    manual_revision_requested,
    request_manual_stage_review,
    revision_patch_target,
)


def review_stage():
    return SimpleNamespace(
        key="01",
        name="overview",
        agent=SimpleNamespace(display_name="Overview Agent"),
    )


class ManualReviewModeTest(unittest.TestCase):
    def test_manual_review_callback_can_request_revision(self):
        captured = {}

        def callback(payload):
            captured.update(payload)
            return {"action": "revise", "instruction": "제외 범위와 BSS 이력 저장 기준을 보강한다."}

        decision = request_manual_stage_review(
            SimpleNamespace(review_mode="manual", manual_review_callback=callback),
            review_stage(),
            1,
            {"score": 91, "threshold": 85, "passed": True, "artifact": {"name": "stage.html"}},
        )

        self.assertEqual("overview", captured["stage_name"])
        self.assertTrue(manual_revision_requested(decision))
        feedback = manual_review_feedback(decision)
        self.assertEqual("사용자 보완 요청", feedback[0]["title"])
        self.assertIn("BSS 이력 저장", feedback[0]["recommendation"])

    def test_manual_review_without_callback_continues(self):
        decision = request_manual_stage_review(
            SimpleNamespace(review_mode="manual", manual_review_callback=None),
            review_stage(),
            1,
            {"passed": True},
        )

        self.assertEqual({"action": "continue"}, decision)

    def test_manual_overview_principle_feedback_targets_overview(self):
        feedback = manual_review_feedback({"action": "revise", "instruction": "설계원칙을 더 구체적으로 보완해줘."})
        current = {
            "overview": {
                "scope": ["기존 범위"],
                "principles": [{"name": "기존 원칙", "description": "기존 설명"}],
            }
        }

        target = revision_patch_target(OverviewAgent(), current, feedback)

        self.assertIn("overview", target)
        self.assertEqual("기존 원칙", target["overview"]["principles"][0]["name"])


if __name__ == "__main__":
    unittest.main()
