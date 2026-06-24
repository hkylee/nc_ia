import os
from unittest.mock import patch

from src.llm_client import LLMClient, PREFLIGHT_CACHE, PREFLIGHT_CACHE_LOCK


def clear_preflight_cache():
    with PREFLIGHT_CACHE_LOCK:
        PREFLIGHT_CACHE.clear()


def test_preflight_reuses_recent_success_without_second_llm_call():
    clear_preflight_cache()
    client = LLMClient(
        writer_mode="llm",
        model="gpt-5.5",
        reasoning_effort="medium",
        api_key="test-key",
    )

    with patch.dict(os.environ, {"OPENAI_PREFLIGHT_CACHE_TTL_SECONDS": "600"}, clear=False), patch.object(
        LLMClient,
        "generate_json",
        return_value={"ok": True, "message": "ready"},
    ) as generate:
        first = client.preflight_check()
        second = client.preflight_check()

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["cache_hit"] is True
    assert generate.call_count == 1
    clear_preflight_cache()
