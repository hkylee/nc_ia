import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.web_app import pi_check_export_from_payload, pi_check_from_payload


class PICheckUploadTest(unittest.TestCase):
    def test_pi_check_compares_optional_as_is_with_required_to_be(self):
        as_is = "<h1>AI 검색</h1><p>기존 검색과 FAQ를 각각 운영한다.</p>"
        to_be = """
        <h1>AI 검색 To-Be</h1>
        <p>중복 입력과 중복 인증을 제거하고 셀프 처리로 자동화한다.</p>
        <p>실패, 오류, 중단, 취소, 중복 요청, 권한 없음, 데이터 없음 상황은 재시도와 상담 전환 기준을 둔다.</p>
        <p>BSS와 FO 책임 경계를 정하고 기준 정보는 단일 원천 마스터로 관리한다.</p>
        <p>KPI는 완료율, 처리 시간, 오류율로 본다. QA 검증과 운영 검증을 수행한다.</p>
        """

        report = pi_check_from_payload(
            {
                "asIs": {
                    "name": "as_is.html",
                    "contentBase64": base64.b64encode(as_is.encode("utf-8")).decode("ascii"),
                },
                "toBe": {
                    "name": "to_be.html",
                    "contentBase64": base64.b64encode(to_be.encode("utf-8")).decode("ascii"),
                },
            }
        )

        self.assertEqual(report["fileName"], "to_be.html")
        self.assertTrue(report["asIs"])
        self.assertTrue(report["toBe"])
        self.assertTrue(report["comparison"]["enabled"])
        self.assertEqual(report["comparison"]["toBeScore"], report["score"])
        self.assertGreaterEqual(report["comparison"]["deltaScore"], 0)
        self.assertIn("gatekeeper", report)
        self.assertIn("piReadiness", report)
        self.assertIn("inspectionMethod", report["checks"][0])
        self.assertTrue(report["actionItems"])

    def test_pi_check_requires_to_be_when_as_is_payload_is_present(self):
        with self.assertRaisesRegex(ValueError, "To-Be"):
            pi_check_from_payload({"asIs": {"name": "as_is.html", "content": "<p>기존</p>"}})

    def test_pi_check_export_writes_html_report(self):
        report = pi_check_from_payload({"toBe": {"name": "to_be.html", "content": "<p>KPI 완료율 처리 시간 오류율 QA 검증 BSS 책임 경계 단일 원천</p>"}})

        with tempfile.TemporaryDirectory() as tmpdir, patch("src.web_app.OUTPUT_ROOT", Path(tmpdir)):
            artifact = pi_check_export_from_payload({"report": report})
            export_path = Path(tmpdir) / artifact["path"]
            self.assertEqual(artifact["name"], "to_be_pi_check_report.html")
            self.assertTrue(export_path.exists())
            export_html = export_path.read_text(encoding="utf-8")
            self.assertIn("검수 영역과 세부 방식", export_html)
            self.assertIn("과제정의서 포괄성", export_html)


if __name__ == "__main__":
    unittest.main()
