import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.web_app import (
    apply_analysis_alignment_llm_review,
    apply_channel_pi_status_llm_review,
    pi_check_from_payload,
)


class FakeHybridClient:
    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "summary": "trace 근거는 유지하되 보완 우선순위를 명확히 잡아야 합니다.",
            "confidence": "high",
            "actionItems": [
                {
                    "priority": "P2",
                    "title": "보완 위치 구체화",
                    "target": "정책 판단 근거",
                    "evidence": "규칙 기반 결과에서 보완 후보가 확인됩니다.",
                    "suggestion": "기존 점수는 유지하고 보완 액션만 추가합니다.",
                }
            ],
        }


class HybridAgentRoutingTest(unittest.TestCase):
    def test_pi_check_uses_hybrid_review_without_leaking_internal_text(self):
        fake_client = FakeHybridClient()
        with patch("src.web_app.optional_hybrid_llm_client_from_payload", return_value=(fake_client, "")):
            report = pi_check_from_payload(
                {
                    "writerMode": "llm",
                    "toBe": {
                        "name": "to_be.html",
                        "content": (
                            "<p>KPI 완료율 처리 시간 오류율 QA 검증 BSS 책임 경계 단일 원천 "
                            "고객 셀프 처리 예외 복구 상담 전환 운영 검증</p>"
                        ),
                    },
                }
            )

        self.assertEqual(report["evaluationMode"], "hybrid")
        self.assertEqual(report["llmReview"]["confidence"], "high")
        self.assertTrue(any(item.get("type") == "llm_pi_review" for item in report["actionItems"]))
        self.assertNotIn("_analysisTextPreview", json.dumps(report, ensure_ascii=False))
        self.assertTrue(fake_client.calls)

    def test_analysis_alignment_hybrid_review_appends_trace_actions(self):
        fake_client = FakeHybridClient()
        report = apply_analysis_alignment_llm_review(
            {
                "summary": "규칙 기반 정렬 Check 완료",
                "score": 82,
                "actionItems": [],
                "analysisToPolicy": [],
                "policyToAnalysis": [],
            },
            llm_client=fake_client,
        )

        self.assertEqual(report["evaluationMode"], "hybrid")
        self.assertTrue(any(item.get("type") == "llm_alignment_review" for item in report["actionItems"]))
        self.assertIn("LLM 보조판정", report["summary"])

    def test_channel_pi_status_hybrid_review_appends_priority_actions(self):
        fake_client = FakeHybridClient()
        report = apply_channel_pi_status_llm_review(
            {
                "summary": "trace 기반 채널 PI 진단 완료",
                "score": 78,
                "priorityActions": [],
                "dimensions": [],
                "sourceCoverage": [],
            },
            llm_client=fake_client,
        )

        self.assertEqual(report["evaluationMode"], "hybrid")
        self.assertTrue(any(item.get("type") == "llm_channel_pi_review" for item in report["priorityActions"]))
        self.assertIn("LLM 보조판정", report["summary"])


if __name__ == "__main__":
    unittest.main()
