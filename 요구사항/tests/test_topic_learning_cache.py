import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.chapter_agents import enhance_learning_with_llm, load_topic_learning_cache, topic_learning_cache_path
from src.llm_client import LLMClient
from llm_client import LLMError


class RetryFailingLearningClient:
    writer_mode = "llm"
    model = "test-model"
    reasoning_effort = "high"
    enabled = True
    forced = True

    def __init__(self):
        self.calls = 0

    def with_overrides(self, **kwargs):
        return self

    def generate_json(self, **kwargs):
        self.calls += 1
        raise LLMError("temporary network timeout")


class TopicLearningCacheTest(unittest.TestCase):
    def test_invalid_legacy_cache_is_ignored(self):
        ctx = SimpleNamespace(
            topic="AI 검색",
            topic_slug="AI검색",
            business_code="AI",
            template_type="simple",
            requirements=(),
            references=(),
            brief="",
        )
        client = LLMClient(writer_mode="llm", model="gpt-5.5", reasoning_effort="high", api_key="test-key")
        with tempfile.TemporaryDirectory() as temp_dir, patch("src.chapter_agents.LEARNING_CACHE_DIR", Path(temp_dir)):
            path = topic_learning_cache_path(ctx, {}, client)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "topic": "AI 검색",
                        "model": "gpt-5.5",
                        "reasoning_effort": "high",
                        "payload": {
                            "topic_understanding": "AI 검색 정책서 작성 방향",
                            "customer_tasks": ["검색한다."],
                            "requirement_implications": ["검색 요구사항을 반영한다."],
                            "reference_implications": ["참고자료를 반영한다."],
                            "bss_implications": ["연계 판정을 반영한다."],
                            "policy_risks": ["노출 기준을 정책화한다."],
                            "chapter_focus": {"overview": "범위 고정"},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertIsNone(load_topic_learning_cache(ctx, {}, client))

    def test_valid_cache_is_loaded(self):
        ctx = SimpleNamespace(
            topic="AI 검색",
            topic_slug="AI검색",
            business_code="AI",
            template_type="simple",
            requirements=(),
            references=(),
            brief="",
        )
        client = LLMClient(writer_mode="llm", model="gpt-5.5", reasoning_effort="high", api_key="test-key")
        payload = {
            "topic_understanding": "AI 검색 정책서 작성 방향",
            "scope_boundary": {
                "direct_scope": ["AI 검색 결과 제공"],
                "related_but_not_core": ["추천"],
                "excluded_or_later": ["광고 운영"],
            },
            "customer_tasks": ["검색한다."],
            "requirement_implications": ["검색 요구사항을 반영한다."],
            "reference_implications": ["참고자료를 반영한다."],
            "bss_implications": ["연계 판정을 반영한다."],
            "policy_risks": ["노출 기준을 정책화한다."],
            "chapter_focus": {"overview": "범위 고정"},
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch("src.chapter_agents.LEARNING_CACHE_DIR", Path(temp_dir)):
            path = topic_learning_cache_path(ctx, {}, client)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"payload": payload}, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(payload, load_topic_learning_cache(ctx, {}, client))

    def test_topic_learning_falls_back_to_base_learning_after_retryable_failures(self):
        ctx = SimpleNamespace(
            topic="AI 검색",
            topic_slug="AI검색",
            business_code="AI",
            template_type="simple",
            requirements=(),
            references=(),
            brief="",
        )
        base_learning = {"summary": "기본 학습 결과"}
        client = RetryFailingLearningClient()
        with tempfile.TemporaryDirectory() as temp_dir, patch("src.chapter_agents.LEARNING_CACHE_DIR", Path(temp_dir)):
            with patch.dict(
                "os.environ",
                {"OPENAI_LLM_TASK_MAX_ATTEMPTS": "2", "OPENAI_LLM_TASK_RETRY_BASE_SECONDS": "0"},
                clear=False,
            ):
                learning = enhance_learning_with_llm(ctx, base_learning, {}, client)

        self.assertEqual("기본 학습 결과", learning["summary"])
        self.assertTrue(learning["llm_learning"]["fallback"])
        self.assertFalse(learning["llm_learning"]["used"])
        self.assertEqual(2, client.calls)


if __name__ == "__main__":
    unittest.main()
