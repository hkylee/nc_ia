import json
import shutil
import unittest
from pathlib import Path

from src import web_app


class UserEventLoggingTest(unittest.TestCase):
    def setUp(self):
        self.original_path = web_app.USER_EVENT_LOG_PATH
        self.root = web_app.PROJECT_ROOT / ".tmp_user_event_logging_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.log_path = self.root / "reports" / "logs" / "user_events.jsonl"
        web_app.USER_EVENT_LOG_PATH = self.log_path

    def tearDown(self):
        web_app.USER_EVENT_LOG_PATH = self.original_path
        if self.root.exists():
            shutil.rmtree(self.root)

    def read_events(self):
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]

    def test_user_event_log_redacts_sensitive_payload_but_keeps_useful_summary(self):
        web_app.write_user_event(
            "revision_requested",
            {
                "name": "NC_상품목록_정책서_간소화_v0.3.html",
                "instructionPreview": "정책 항목에 재고 부족 예외를 추가해줘.",
                "llmAccessToken": "secret-token",
                "html": "<html>large</html>",
                "htmlChars": 18,
            },
            session_id="browser-session-1",
        )

        event = self.read_events()[0]

        self.assertEqual("revision_requested", event["event"])
        self.assertEqual("server", event["source"])
        self.assertEqual(16, len(event["session"]))
        self.assertEqual("NC_상품목록_정책서_간소화_v0.3.html", event["details"]["name"])
        self.assertIn("재고 부족", event["details"]["instructionPreview"])
        self.assertEqual(18, event["details"]["htmlChars"])
        self.assertNotIn("secret-token", json.dumps(event, ensure_ascii=False))
        self.assertNotIn("<html>large</html>", json.dumps(event, ensure_ascii=False))

    def test_policy_request_event_payload_keeps_options_and_brief_length(self):
        payload = {
            "topic": "상품 목록",
            "templateType": "simple",
            "reviewMode": "manual",
            "inspectionMode": "final-only",
            "writerMode": "mock",
            "brief": "테스트 요구사항",
        }

        summary = web_app.event_payload_for_policy_request(payload, job={"id": "job-1"}, status="accepted")

        self.assertEqual("job-1", summary["jobId"])
        self.assertEqual("상품 목록", summary["topic"])
        self.assertEqual("manual", summary["reviewMode"])
        self.assertEqual("final-only", summary["inspectionMode"])
        self.assertEqual("mock", summary["writerMode"])
        self.assertEqual(len("테스트 요구사항"), summary["briefChars"])

    def test_service_usage_summary_groups_events_errors_and_revision_requests(self):
        web_app.write_user_event("policy_selected", {"selectedName": "상품 목록"}, session_id="browser-session-1", source="client")
        web_app.write_user_event(
            "revision_requested",
            {"name": "상품 목록", "instructionPreview": "재고 예외를 추가해줘."},
            session_id="browser-session-1",
        )
        web_app.write_user_event("ui_error", {"message": "업로드 실패"}, session_id="browser-session-2", source="client")

        summary = web_app.summarize_service_user_events(self.log_path)

        self.assertEqual(3, summary["summary"]["recentEvents"])
        self.assertEqual(1, summary["summary"]["recentErrors"])
        self.assertEqual(1, summary["summary"]["revisionRequests"])
        self.assertEqual("상품 목록", summary["topTargets"][0]["name"])
        self.assertEqual("ui_error", summary["recentErrors"][0]["event"])


if __name__ == "__main__":
    unittest.main()
