import json
import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


class RuntimeBpmnMigrationTest(unittest.TestCase):
    def setUp(self):
        self.original_output_root = web_app.OUTPUT_ROOT
        self.original_reports_dir = web_app.REPORTS_DIR
        self.root = web_app.PROJECT_ROOT / ".tmp_runtime_bpmn_migration_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.output_root = self.root / "output"
        self.reports_dir = self.root / "reports" / "inspections"
        self.output_root.mkdir(parents=True)
        self.reports_dir.mkdir(parents=True)
        web_app.OUTPUT_ROOT = self.output_root
        web_app.REPORTS_DIR = self.reports_dir

    def tearDown(self):
        web_app.OUTPUT_ROOT = self.original_output_root
        web_app.REPORTS_DIR = self.original_reports_dir
        if self.root.exists():
            shutil.rmtree(self.root)

    def test_runtime_migration_updates_render_only_policy_outputs(self):
        html_path = self.output_root / "NC_AI검색_정책서_간소화_v0.1.html"
        spec_path = self.output_root / "NC_AI검색_정책서_간소화_v0.1_spec.json"
        html_path.write_text("<html><body><h1>old static process</h1></body></html>", encoding="utf-8")
        spec_path.write_text(json.dumps(sample_spec(), ensure_ascii=False), encoding="utf-8")

        result = web_app.migrate_runtime_bpmn_io_artifacts()

        self.assertEqual(1, len(result["updated"]))
        html = html_path.read_text(encoding="utf-8")
        self.assertIn("bpmn-viewer.production.min.js", html)
        self.assertIn('data-bpmn-viewer="true"', html)
        self.assertTrue((self.output_root / "NC_AI검색_정책서_간소화_v0.1_전체업무흐름도.bpmn").exists())
        self.assertTrue((self.output_root / "NC_AI검색_정책서_간소화_v0.1_전체업무흐름도_viewer.html").exists())
        self.assertTrue((self.root / "reports" / "runtime_bpmn_io_migration_latest.json").exists())

    def test_runtime_migration_skips_when_spec_is_missing(self):
        html_path = self.output_root / "NC_AI검색_정책서_간소화_v0.1.html"
        html_path.write_text("<html><body>old</body></html>", encoding="utf-8")

        result = web_app.migrate_runtime_bpmn_io_artifacts()

        self.assertEqual([], result["updated"])
        self.assertEqual("spec_missing", result["skipped"][0]["reason"])


def sample_spec():
    return {
        "meta": {"topic": "AI검색", "version": "v0.1", "document_type": "간소화 버전"},
        "history": [],
        "overview": {"scope": "AI 검색 업무", "principles": ["고객 과업 중심으로 검색 결과를 제공한다."]},
        "terms": [{"id": "TM-001", "name": "검색", "description": "고객이 필요한 정보를 찾는 업무 기준이다."}],
        "actors": [{"id": "AC-001", "name": "고객", "description": "검색 업무를 시작하는 주체다."}],
        "usecases": [{"id": "UC-AI-001", "actor_id": "AC-001", "name": "AI 검색 이용", "description": "고객이 정보를 찾는다.", "process_target": "Y"}],
        "state_codes": [{"code": "ST-001", "name": "조회 가능", "description": "검색을 시작할 수 있는 상태다."}],
        "state_transitions": [],
        "processes": [{"id": "PR-AI-001", "usecase_id": "UC-AI-001", "name": "검색어 입력", "description": "고객이 검색어를 입력한다."}],
        "functions": [{"id": "FN-AI-001", "name": "검색 처리", "description": "검색 결과를 생성한다.", "details": ["검색어 분석"]}],
        "policies": [{"id": "PG-AI-001", "name": "검색 기준", "description": "검색 기준을 정의한다.", "items": [{"id": "PI-AI-001", "name": "검색어 기준"}]}],
        "policy_details": [{"id": "PI-AI-001", "policy_id": "PG-AI-001", "name": "검색어 기준", "content": "검색어는 고객 입력 기준으로 처리한다."}],
        "final_checks": [],
    }


if __name__ == "__main__":
    unittest.main()
