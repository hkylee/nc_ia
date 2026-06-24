import json
import shutil
import sqlite3
import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


def bootstrap_spec(topic: str, document_id: str, detail: str) -> dict:
    return {
        "meta": {
            "topic": topic,
            "topic_display": topic,
            "document_id": document_id,
            "version": "v0.10",
            "template_type": "simple",
        },
        "actors": [{"id": f"ACT-{document_id}-CUS", "name": "고객", "responsibility": "업무를 시작한다."}],
        "usecases": [
            {
                "id": f"US-{document_id}-001",
                "actor_id": f"ACT-{document_id}-CUS",
                "actor": "고객",
                "name": f"{topic} 확인",
                "description": f"고객이 {detail} 확인한다.",
                "process_target": "Y",
            }
        ],
        "states": [{"id": f"ST-{document_id}-001", "name": "확인 전"}, {"id": f"ST-{document_id}-002", "name": "완료"}],
        "processes": [
            {
                "id": f"PR-{document_id}-001",
                "usecase_id": f"US-{document_id}-001",
                "name": f"{topic} 처리",
                "description": f"{detail} 처리한다.",
                "related_functions": [f"FN-{document_id}-001"],
                "related_policies": [f"PG-{document_id}-001"],
            }
        ],
        "functions": [
            {
                "id": f"FN-{document_id}-001",
                "process_id": f"PR-{document_id}-001",
                "name": f"{topic} 기능",
                "description": f"{detail} 결과를 생성한다.",
                "details": ["기준 조회", "결과 저장"],
            }
        ],
        "policy_groups": [
            {
                "id": f"PG-{document_id}-001",
                "name": f"{topic} 정책",
                "description": f"{detail} 판단 기준을 정의한다.",
            }
        ],
        "policy_details": [
            {
                "id": f"PI-{document_id}-001-01",
                "policy_id": f"PG-{document_id}-001",
                "name": "처리 기준",
                "content": f"{detail} 조건이 충족된 경우에만 완료한다.",
            }
        ],
    }


class PolicyGraphBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.original_output_root = web_app.OUTPUT_ROOT
        self.original_graph_path = web_app.POLICY_GRAPH_DB_PATH
        self.original_requirements_path = web_app.REQUIREMENTS_DB_PATH
        self.original_reference_path = web_app.REFERENCE_DB_PATH
        self.original_incremental = web_app.POLICY_GRAPH_INCREMENTAL_ENABLED
        self.original_force = web_app.POLICY_GRAPH_BOOTSTRAP_FORCE

        self.root = web_app.PROJECT_ROOT / ".tmp_policy_graph_bootstrap_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.output_root = self.root / "output"
        self.checkpoint_root = self.output_root / "checkpoints"
        self.evidence_root = self.root / "reports" / "evidence"
        self.runtime_root = self.root / "runtime"
        self.checkpoint_root.mkdir(parents=True)
        self.evidence_root.mkdir(parents=True)
        self.runtime_root.mkdir(parents=True)

        web_app.OUTPUT_ROOT = self.output_root
        web_app.POLICY_GRAPH_DB_PATH = self.runtime_root / "policy_graph.db"
        web_app.REQUIREMENTS_DB_PATH = self.evidence_root / "requirements.db"
        web_app.REFERENCE_DB_PATH = self.evidence_root / "reference.db"
        web_app.POLICY_GRAPH_INCREMENTAL_ENABLED = True
        web_app.POLICY_GRAPH_BOOTSTRAP_FORCE = False

    def tearDown(self):
        web_app.OUTPUT_ROOT = self.original_output_root
        web_app.POLICY_GRAPH_DB_PATH = self.original_graph_path
        web_app.REQUIREMENTS_DB_PATH = self.original_requirements_path
        web_app.REFERENCE_DB_PATH = self.original_reference_path
        web_app.POLICY_GRAPH_INCREMENTAL_ENABLED = self.original_incremental
        web_app.POLICY_GRAPH_BOOTSTRAP_FORCE = self.original_force
        if self.root.exists():
            shutil.rmtree(self.root)

    def write_spec(self, filename: str, spec: dict) -> Path:
        path = self.checkpoint_root / filename
        path.write_text(json.dumps({"spec": spec}, ensure_ascii=False), encoding="utf-8")
        return path

    def write_policy_artifacts(self, topic: str, label: str, version: str, document_id: str) -> tuple[Path, Path]:
        html_path = self.output_root / f"NC_{topic}_정책서_{label}_{version}.html"
        spec_path = self.output_root / f"{html_path.stem}_spec.json"
        html_path.write_text("<html></html>", encoding="utf-8")
        spec_path.write_text(
            json.dumps({"spec": bootstrap_spec(topic, document_id, f"{version} 기준을")}, ensure_ascii=False),
            encoding="utf-8",
        )
        return html_path, spec_path

    def document_count(self) -> int:
        with sqlite3.connect(web_app.POLICY_GRAPH_DB_PATH) as conn:
            row = conn.execute("SELECT COUNT(DISTINCT document_id) FROM graph_nodes WHERE node_type = ?", ("DocumentVersion",)).fetchone()
        return int(row[0] or 0)

    def test_policy_graph_uses_latest_visible_policy_specs_only(self):
        _old_html, old_spec = self.write_policy_artifacts("정책 A", "간소화", "v0.10", "POL-A-OLD")
        _new_html, new_spec = self.write_policy_artifacts("정책 A", "간소화", "v0.11", "POL-A-NEW")
        _full_html, full_spec = self.write_policy_artifacts("정책 A", "Full", "v0.10", "POL-A-FULL")
        orphan_spec = self.output_root / "정책A_policy_spec.json"
        orphan_spec.write_text(json.dumps({"spec": bootstrap_spec("정책 A", "POL-A-ORPHAN", "고아 spec을")}, ensure_ascii=False), encoding="utf-8")

        spec_paths = web_app.policy_graph_spec_paths()

        self.assertIn(new_spec, spec_paths)
        self.assertIn(full_spec, spec_paths)
        self.assertNotIn(old_spec, spec_paths)
        self.assertNotIn(orphan_spec, spec_paths)

    def test_bootstrap_updates_changed_specs_incrementally_and_rebuilds_when_sources_change(self):
        spec_a = self.write_spec("policy_a_latest_checkpoint.json", bootstrap_spec("정책 A", "POL-A", "조건 A를"))
        spec_b = self.write_spec("policy_b_latest_checkpoint.json", bootstrap_spec("정책 B", "POL-B", "조건 B를"))
        spec_paths = [spec_a, spec_b]

        initial_plan = web_app.policy_graph_bootstrap_plan(spec_paths, web_app.POLICY_GRAPH_DB_PATH)
        self.assertEqual("full", initial_plan["action"])
        web_app.run_policy_graph_bootstrap_plan(spec_paths, initial_plan)
        self.assertEqual(2, self.document_count())
        self.assertEqual("ready", web_app.policy_graph_bootstrap_plan(spec_paths, web_app.POLICY_GRAPH_DB_PATH)["action"])

        time.sleep(0.02)
        spec_a.write_text(
            json.dumps({"spec": bootstrap_spec("정책 A", "POL-A", "변경된 조건 A를")}, ensure_ascii=False),
            encoding="utf-8",
        )
        incremental_plan = web_app.policy_graph_bootstrap_plan(spec_paths, web_app.POLICY_GRAPH_DB_PATH)
        self.assertEqual("incremental", incremental_plan["action"])
        self.assertEqual(1, incremental_plan["changedSpecFileCount"])
        web_app.run_policy_graph_bootstrap_plan(spec_paths, incremental_plan)
        self.assertEqual(2, self.document_count())

        spec_b.unlink()
        delete_plan = web_app.policy_graph_bootstrap_plan([spec_a], web_app.POLICY_GRAPH_DB_PATH)
        self.assertEqual("incremental", delete_plan["action"])
        self.assertEqual(1, delete_plan["deletedSpecFileCount"])
        web_app.run_policy_graph_bootstrap_plan([spec_a], delete_plan)
        self.assertEqual(1, self.document_count())

        web_app.REQUIREMENTS_DB_PATH.write_text("changed", encoding="utf-8")
        source_plan = web_app.policy_graph_bootstrap_plan([spec_a], web_app.POLICY_GRAPH_DB_PATH)
        self.assertEqual("full", source_plan["action"])
        self.assertEqual("source_changed", source_plan["reason"])


if __name__ == "__main__":
    unittest.main()
