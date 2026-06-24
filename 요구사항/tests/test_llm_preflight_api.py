from unittest.mock import patch

from src import web_app


class DummyPreflightClient:
    def __init__(self, result):
        self.result = result

    def preflight_check(self):
        return self.result


def test_run_llm_preflight_check_uses_real_llm_client_preflight():
    with patch.object(
        web_app.LLMClient,
        "from_context",
        return_value=DummyPreflightClient({"ok": True, "message": "ready"}),
    ) as factory:
        result = web_app.run_llm_preflight_check()

    assert result == {"ok": True, "message": "ready"}
    factory.assert_called_once()


def test_run_llm_preflight_check_normalizes_non_dict_result():
    with patch.object(web_app.LLMClient, "from_context", return_value=DummyPreflightClient("ready")):
        result = web_app.run_llm_preflight_check()

    assert result == {"ok": True, "message": "ready"}
