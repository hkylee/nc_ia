import json
import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


class FullFromSimpleTest(unittest.TestCase):
    def setUp(self):
        self.original_output_root = web_app.OUTPUT_ROOT
        self.original_reports_dir = web_app.REPORTS_DIR
        self.original_lock_dir = web_app.LOCK_DIR
        self.root = web_app.PROJECT_ROOT / ".tmp_full_from_simple_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.output_root = self.root / "output"
        self.reports_dir = self.root / "reports"
        web_app.OUTPUT_ROOT = self.output_root
        web_app.REPORTS_DIR = self.reports_dir
        web_app.LOCK_DIR = self.output_root / ".locks"
        for child in ("checkpoints", "status", ".locks"):
            (self.output_root / child).mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        web_app.OUTPUT_ROOT = self.original_output_root
        web_app.REPORTS_DIR = self.original_reports_dir
        web_app.LOCK_DIR = self.original_lock_dir
        if self.root.exists():
            shutil.rmtree(self.root)

    def write_simple_policy(self, *, completed=True):
        name = "NC_AI검색_정책서_간소화_v0.12.html"
        (self.output_root / name).write_text("<html></html>", encoding="utf-8")
        spec = {
            "meta": {
                "topic": "AI검색",
                "topic_slug": "AI검색",
                "template_type": "simple",
                "version": "v0.12",
                "chapter_state": {"process_detail": {"status": "old"}},
            },
            "history": [{"version": "v0.12", "change": "간소화 작성 완료"}],
            "overview": {"scope": ["AI 검색 범위"], "principles": ["검색 원칙"]},
            "process_details": [{"process_id": "OLD"}],
            "function_details": [{"function_id": "OLD"}],
        }
        checkpoint = {
            "checkpoint": {"stage_key": "10", "template_type": "simple", "version": "v0.12"},
            "spec": spec,
        }
        checkpoint_path = self.output_root / "checkpoints/NC_AI검색_정책서_간소화_v0.12_latest_checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
        if completed:
            web_app.update_policy_lifecycle_from_payload({"name": name, "status": "completed", "author": "Tester"})
        return name

    def test_prepare_full_from_simple_builds_full_resume_checkpoint(self):
        name = self.write_simple_policy()

        checkpoint_path, payload = web_app.prepare_full_from_simple_payload(
            {
                "name": name,
                "topic": "AI검색",
                "reviewMode": "manual",
                "inspectionMode": "final-only",
                "writerMode": "mock",
                "author": "Tester",
            }
        )

        self.assertEqual("full", payload["templateType"])
        self.assertEqual("manual", payload["reviewMode"])
        self.assertEqual("final-only", payload["inspectionMode"])
        self.assertEqual("mock", payload["writerMode"])
        self.assertTrue(payload["fullFromSimple"])
        self.assertEqual(name, payload["sourceSimpleName"])
        self.assertTrue(checkpoint_path.exists())

        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        spec = checkpoint["spec"]
        self.assertEqual("full", spec["meta"]["template_type"])
        self.assertEqual("v0.10", spec["meta"]["version"])
        self.assertEqual(name, spec["meta"]["source_simple_document"]["name"])
        self.assertEqual([], spec["process_details"])
        self.assertEqual([], spec["function_details"])
        self.assertNotIn("process_detail", spec["meta"]["chapter_state"])
        self.assertEqual("09", checkpoint["checkpoint"]["stage_key"])
        latest_path = self.output_root / "checkpoints/NC_AI검색_정책서_Full_v0.10_latest_checkpoint.json"
        self.assertTrue(latest_path.exists())

    def test_prepare_full_from_simple_requires_completed_simple_policy(self):
        name = self.write_simple_policy(completed=False)

        with self.assertRaises(ValueError):
            web_app.prepare_full_from_simple_payload({"name": name, "topic": "AI검색", "writerMode": "mock"})

    def test_prepare_full_from_simple_increments_existing_full_version(self):
        name = self.write_simple_policy()
        (self.output_root / "NC_AI검색_정책서_Full_v0.10.html").write_text("<html></html>", encoding="utf-8")

        checkpoint_path, payload = web_app.prepare_full_from_simple_payload(
            {"name": name, "topic": "AI검색", "writerMode": "mock"}
        )
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

        self.assertEqual("v0.11", checkpoint["spec"]["meta"]["version"])
        self.assertIn("Full_v0.11", payload["resumeFrom"])


if __name__ == "__main__":
    unittest.main()
