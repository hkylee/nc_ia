import unittest
from argparse import Namespace
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.policy_agent import normalized_inspection_mode
from src.web_app import LLM_ACCESS_TOKEN_VALUE, build_create_args_from_payload, llm_client_from_web_payload


class InspectionModeTest(unittest.TestCase):
    def test_no_inspect_forces_none_mode(self):
        mode = normalized_inspection_mode(Namespace(no_inspect=True, inspection_mode="chapter-final"))

        self.assertEqual("none", mode)

    def test_final_only_mode_is_preserved_from_web_payload(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
            }
        )

        self.assertEqual("final-only", args.inspection_mode)
        self.assertFalse(args.no_inspect)

    def test_web_payload_can_select_mock_writer_mode(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
                "writerMode": "mock",
            }
        )

        self.assertEqual("mock", args.writer_mode)

    def test_web_payload_can_select_llm_unused_label(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
                "writerMode": "미사용",
            }
        )

        self.assertEqual("mock", args.writer_mode)

    def test_web_payload_defaults_to_mock_writer_mode(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
            }
        )

        self.assertEqual("mock", args.writer_mode)

    def test_web_payload_can_select_llm_writer_mode(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
                "writerMode": "llm",
            }
        )

        self.assertEqual("llm", args.writer_mode)

    def test_web_payload_can_select_llm_used_label(self):
        args = build_create_args_from_payload(
            {
                "topic": "매장/대리점",
                "templateType": "simple",
                "reviewMode": "auto",
                "inspectionMode": "final-only",
                "writerMode": "사용",
            }
        )

        self.assertEqual("llm", args.writer_mode)

    def test_web_llm_payload_does_not_fall_back_to_global_mock_env(self):
        with patch.dict("os.environ", {"NC_MOCK_LLM": "1", "OPENAI_API_KEY": "test-key"}, clear=False):
            client = llm_client_from_web_payload(
                {
                    "writerMode": "llm",
                    "llmAccessToken": LLM_ACCESS_TOKEN_VALUE,
                }
            )

        self.assertEqual("llm", client.writer_mode)


if __name__ == "__main__":
    unittest.main()
