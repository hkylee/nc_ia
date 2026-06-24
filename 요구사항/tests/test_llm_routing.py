import os
import unittest
from unittest.mock import patch

from src.llm_client import LLMClient
from src.llm_routing import client_for_chapter, client_for_pi_agent, client_for_topic_learning, routing_plan


class LLMRoutingTest(unittest.TestCase):
    def base_client(self) -> LLMClient:
        return LLMClient(
            writer_mode="llm",
            model="gpt-5.4",
            reasoning_effort="high",
            api_key="test-key",
        )

    def test_topic_learning_uses_stronger_default_route(self):
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_topic_learning(self.base_client())

        self.assertEqual(routed.model, "gpt-5.5")
        self.assertEqual(routed.reasoning_effort, "high")

    def test_topic_learning_env_override_still_supported(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_MODEL_TOPIC_LEARNING": "gpt-5.5-custom",
                "OPENAI_REASONING_EFFORT_TOPIC_LEARNING": "xhigh",
            },
            clear=True,
        ):
            routed = client_for_topic_learning(self.base_client())

        self.assertEqual(routed.model, "gpt-5.5-custom")
        self.assertEqual(routed.reasoning_effort, "xhigh")

    def test_routing_plan_exposes_topic_learning_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            plan = routing_plan(self.base_client())

        self.assertEqual(plan["topic_learning"]["model"], "gpt-5.5")
        self.assertEqual(plan["topic_learning"]["reasoning_effort"], "high")

    def test_simple_chapter_uses_cost_balanced_model(self):
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_chapter(self.base_client(), "overview")

        self.assertEqual(routed.model, "gpt-5.4")
        self.assertEqual(routed.reasoning_effort, "medium")

    def test_simple_chapter_escalates_to_frontier_model_on_retry(self):
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_chapter(self.base_client(), "overview", attempt=2)

        self.assertEqual(routed.model, "gpt-5.5")
        self.assertEqual(routed.reasoning_effort, "high")

    def test_core_chapter_stays_on_frontier_model(self):
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_chapter(self.base_client(), "process")

        self.assertEqual(routed.model, "gpt-5.5")
        self.assertEqual(routed.reasoning_effort, "high")

    def test_live_feedback_keeps_mini_model(self):
        with patch.dict(os.environ, {}, clear=True):
            plan = routing_plan(self.base_client())

        self.assertEqual(plan["live_feedback"]["model"], "gpt-5.4-mini")
        self.assertEqual(plan["live_feedback"]["reasoning_effort"], "medium")

    def test_pi_agent_uses_frontier_extra_high_reasoning(self):
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_pi_agent(self.base_client())
            plan = routing_plan(self.base_client())

        self.assertEqual(routed.model, "gpt-5.5")
        self.assertEqual(routed.reasoning_effort, "xhigh")
        self.assertEqual(plan["pi_agent"]["model"], "gpt-5.5")
        self.assertEqual(plan["pi_agent"]["reasoning_effort"], "xhigh")

    def test_pi_agent_mock_mode_stays_mock_without_reasoning(self):
        mock_client = LLMClient(
            writer_mode="mock",
            model="mock-policy-agent",
            reasoning_effort="none",
            api_key="",
        )
        with patch.dict(os.environ, {}, clear=True):
            routed = client_for_pi_agent(mock_client)
            plan = routing_plan(mock_client)

        self.assertEqual(routed.writer_mode, "mock")
        self.assertEqual(routed.model, "mock-policy-agent")
        self.assertEqual(routed.reasoning_effort, "none")
        self.assertTrue(plan["pi_agent"]["mock"])
        self.assertEqual(plan["pi_agent"]["reasoning_effort"], "none")

    def test_final_only_inspector_uses_extra_high_reasoning(self):
        with patch.dict(os.environ, {}, clear=True):
            plan = routing_plan(self.base_client())

        self.assertEqual(plan["inspector_final_comprehensive"]["model"], "gpt-5.5")
        self.assertEqual(plan["inspector_final_comprehensive"]["reasoning_effort"], "xhigh")

    def test_safe_cost_reduction_routes_stay_balanced(self):
        with patch.dict(os.environ, {}, clear=True):
            plan = routing_plan(self.base_client())

        for route in ("usecase_diagram", "process_detail", "function_detail", "dev_qa_review"):
            self.assertEqual(plan[route]["model"], "gpt-5.4")
            self.assertEqual(plan[route]["reasoning_effort"], "medium")
            self.assertEqual(plan[route]["escalation_model"], "gpt-5.5")
            self.assertEqual(plan[route]["escalation_effort"], "high")


if __name__ == "__main__":
    unittest.main()
