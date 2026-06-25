import json
import os
import shutil
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


class PolicyDeleteCleanupTest(unittest.TestCase):
    def setUp(self):
        self.original_output_root = web_app.OUTPUT_ROOT
        self.original_reports_dir = web_app.REPORTS_DIR
        self.original_lock_dir = web_app.LOCK_DIR
        self.original_policy_comments_dir = web_app.POLICY_COMMENTS_DIR
        self.root = web_app.PROJECT_ROOT / ".tmp_policy_delete_test"
        if self.root.exists():
            shutil.rmtree(self.root)
        self.output_root = self.root / "output"
        self.reports_dir = self.root / "reports"
        web_app.OUTPUT_ROOT = self.output_root
        web_app.REPORTS_DIR = self.reports_dir
        web_app.LOCK_DIR = self.output_root / ".locks"
        web_app.POLICY_COMMENTS_DIR = self.reports_dir / "comments"
        for child in ("steps", "checkpoints", "quality", ".locks"):
            (self.output_root / child).mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        web_app.OUTPUT_ROOT = self.original_output_root
        web_app.REPORTS_DIR = self.original_reports_dir
        web_app.LOCK_DIR = self.original_lock_dir
        web_app.POLICY_COMMENTS_DIR = self.original_policy_comments_dir
        if self.root.exists():
            shutil.rmtree(self.root)

    def write(self, relative_path: str, content: str = "x") -> Path:
        path = self.output_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def make_old(self, path: Path, *, hours: int = 48) -> Path:
        old = time.time() - hours * 3600
        os.utime(path, (old, old))
        return path

    def test_delete_policy_removes_related_checkpoints_and_auxiliary_files(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.1.html"
        self.write(policy_name, "<html></html>")
        self.write("status/NC_AI검색_정책서_간소화_v0.1_status.json", "{}")
        self.write("steps/NC_AI검색_정책서_간소화_v0.1_06_state.html")
        self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_01_overview_checkpoint.json", "{}")
        self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json", "{}")
        self.write("quality/NC_AI검색_정책서_간소화_v0.1_quality_report.json", "{}")
        self.write("AI검색_policy_spec.json", "{}")
        self.write("NC_AI검색_정책서_간소화_v0.1_spec.json", "{}")
        self.write("AI검색_authoring_blueprint.json", "{}")
        self.write("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도.bpmn", "<xml></xml>")
        self.write("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도_viewer.html", "<html></html>")
        comment_path = web_app.policy_comments_storage_path(policy_name)
        comment_path.parent.mkdir(parents=True, exist_ok=True)
        comment_path.write_text('{"policyName": "NC_AI검색_정책서_간소화_v0.1.html", "comments": []}', encoding="utf-8")
        report = self.reports_dir / "NC_AI검색_정책서_간소화_v0.1.html_web_inspection.json"
        report.write_text("{}", encoding="utf-8")
        lock = web_app.LOCK_DIR / f"{web_app.job_lock_key('AI검색', 'simple')}.lock"
        lock.write_text(json.dumps({"status": "canceled"}), encoding="utf-8")

        result = web_app.delete_policy_from_payload({"name": policy_name})

        self.assertEqual(policy_name, result["name"])
        self.assertFalse((self.output_root / policy_name).exists())
        self.assertFalse((self.output_root / "steps/NC_AI검색_정책서_간소화_v0.1_06_state.html").exists())
        self.assertFalse((self.output_root / "status/NC_AI검색_정책서_간소화_v0.1_status.json").exists())
        self.assertFalse((self.output_root / "checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json").exists())
        self.assertFalse((self.output_root / "quality/NC_AI검색_정책서_간소화_v0.1_quality_report.json").exists())
        self.assertFalse(report.exists())
        self.assertFalse((self.output_root / "AI검색_policy_spec.json").exists())
        self.assertFalse((self.output_root / "NC_AI검색_정책서_간소화_v0.1_spec.json").exists())
        self.assertFalse((self.output_root / "AI검색_authoring_blueprint.json").exists())
        self.assertFalse((self.output_root / "NC_AI검색_정책서_간소화_v0.1_전체업무흐름도.bpmn").exists())
        self.assertFalse((self.output_root / "NC_AI검색_정책서_간소화_v0.1_전체업무흐름도_viewer.html").exists())
        self.assertFalse(comment_path.exists())
        self.assertFalse(lock.exists())

    def test_policy_comments_are_shared_server_artifacts(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.10.html"
        next_policy_name = "NC_AI검색_정책서_간소화_v0.11.html"
        self.write(policy_name, "<html></html>")
        self.write(next_policy_name, "<html></html>")
        user = {"name": "작성자 A", "employeeId": "1111120"}

        added = web_app.update_policy_comments_from_payload(
            {
                "name": policy_name,
                "action": "add",
                "comment": {
                    "id": "comment-1",
                    "note": "함께 확인할 코멘트",
                    "headingPath": ["문서 전체"],
                    "targetKind": "문서",
                },
            },
            user,
        )

        self.assertEqual(1, len(added["comments"]))
        self.assertEqual("작성자 A", added["comments"][0]["author"])
        self.assertEqual("NC_AI검색_정책서_간소화_v0.10.html", added["comments"][0]["originalPolicyName"])
        self.assertEqual("v0.10", added["comments"][0]["createdOnVersion"])
        storage_path = web_app.policy_comments_storage_path(policy_name)
        next_storage_path = web_app.policy_comments_storage_path(next_policy_name)
        self.assertEqual(storage_path, next_storage_path)
        self.assertTrue(storage_path.exists())

        updated = web_app.update_policy_comments_from_payload(
            {"name": policy_name, "action": "status", "id": "comment-1", "status": "보류"},
            {"name": "작성자 B"},
        )
        self.assertEqual("보류", updated["comments"][0]["status"])

        replied = web_app.update_policy_comments_from_payload(
            {
                "name": policy_name,
                "action": "reply",
                "id": "comment-1",
                "reply": {"id": "reply-1", "note": "답글입니다."},
            },
            {"name": "작성자 C"},
        )
        self.assertEqual("작성자 C", replied["comments"][0]["replies"][0]["author"])

        loaded = web_app.load_policy_comments(policy_name)
        self.assertEqual("comment-1", loaded["comments"][0]["id"])
        self.assertEqual("reply-1", loaded["comments"][0]["replies"][0]["id"])
        loaded_next = web_app.load_policy_comments(next_policy_name)
        self.assertEqual("AI검색", loaded_next["topic"])
        self.assertEqual(next_policy_name, loaded_next["policyName"])
        self.assertEqual("comment-1", loaded_next["comments"][0]["id"])
        self.assertEqual("NC_AI검색_정책서_간소화_v0.10.html", loaded_next["comments"][0]["originalPolicyName"])
        self.assertEqual("v0.10", loaded_next["comments"][0]["createdOnVersion"])

    def test_delete_policy_keeps_topic_comments_when_other_version_remains(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.10.html"
        next_policy_name = "NC_AI검색_정책서_간소화_v0.11.html"
        self.write(policy_name, "<html></html>")
        self.write(next_policy_name, "<html></html>")
        web_app.update_policy_comments_from_payload(
            {
                "name": policy_name,
                "action": "add",
                "comment": {
                    "id": "comment-keep",
                    "note": "다음 버전에서도 유지",
                    "headingPath": ["문서 전체"],
                    "targetKind": "문서",
                },
            },
            {"name": "작성자 A"},
        )
        storage_path = web_app.policy_comments_storage_path(policy_name)

        web_app.delete_policy_from_payload({"name": policy_name})

        self.assertFalse((self.output_root / policy_name).exists())
        self.assertTrue((self.output_root / next_policy_name).exists())
        self.assertTrue(storage_path.exists())
        loaded_next = web_app.load_policy_comments(next_policy_name)
        self.assertEqual("comment-keep", loaded_next["comments"][0]["id"])
        self.assertEqual(policy_name, loaded_next["comments"][0]["originalPolicyName"])

    def test_legacy_policy_comment_file_migrates_to_topic_storage(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.10.html"
        next_policy_name = "NC_AI검색_정책서_간소화_v0.11.html"
        self.write(policy_name, "<html></html>")
        self.write(next_policy_name, "<html></html>")
        legacy_path = web_app.policy_comments_legacy_storage_path_for_name(policy_name)
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps(
                {
                    "policyName": policy_name,
                    "contentHash": "legacy-hash",
                    "comments": [
                        {
                            "id": "legacy-comment",
                            "note": "이전 저장 방식 코멘트",
                            "author": "작성자 A",
                            "headingPath": ["문서 전체"],
                            "targetKind": "문서",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        loaded = web_app.load_policy_comments(next_policy_name)

        self.assertFalse(legacy_path.exists())
        self.assertTrue(web_app.policy_comments_storage_path(next_policy_name).exists())
        self.assertEqual("legacy-comment", loaded["comments"][0]["id"])
        self.assertEqual(policy_name, loaded["comments"][0]["originalPolicyName"])
        self.assertEqual("v0.10", loaded["comments"][0]["createdOnVersion"])

    def test_delete_policy_keeps_auxiliary_files_when_other_version_remains(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.1.html"
        self.write(policy_name, "<html></html>")
        self.write("NC_AI검색_정책서_간소화_v0.2.html", "<html></html>")
        self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json", "{}")
        self.write("checkpoints/NC_AI검색_정책서_간소화_v0.2_latest_checkpoint.json", "{}")
        self.write("AI검색_policy_spec.json", "{}")
        self.write("NC_AI검색_정책서_간소화_v0.1_spec.json", '{"meta": {"version": "v0.1"}}')
        self.write("NC_AI검색_정책서_간소화_v0.2_spec.json", '{"meta": {"version": "v0.2"}}')
        self.write("AI검색_authoring_blueprint.json", "{}")

        web_app.delete_policy_from_payload({"name": policy_name})

        self.assertFalse((self.output_root / policy_name).exists())
        self.assertFalse((self.output_root / "checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json").exists())
        self.assertTrue((self.output_root / "NC_AI검색_정책서_간소화_v0.2.html").exists())
        self.assertTrue((self.output_root / "checkpoints/NC_AI검색_정책서_간소화_v0.2_latest_checkpoint.json").exists())
        self.assertTrue((self.output_root / "AI검색_policy_spec.json").exists())
        self.assertFalse((self.output_root / "NC_AI검색_정책서_간소화_v0.1_spec.json").exists())
        self.assertTrue((self.output_root / "NC_AI검색_정책서_간소화_v0.2_spec.json").exists())
        self.assertTrue((self.output_root / "AI검색_authoring_blueprint.json").exists())

    def test_describe_policy_file_includes_versioned_json_artifact(self):
        policy = self.write("NC_AI검색_정책서_간소화_v0.1.html", "<html></html>")
        self.write("NC_AI검색_정책서_간소화_v0.1_spec.json", '{"meta": {"version": "v0.1"}}')

        item = web_app.describe_policy_file(policy)

        self.assertEqual("NC_AI검색_정책서_간소화_v0.1_spec.json", item["json"]["name"])
        self.assertEqual("/output/NC_AI%EA%B2%80%EC%83%89_%EC%A0%95%EC%B1%85%EC%84%9C_%EA%B0%84%EC%86%8C%ED%99%94_v0.1_spec.json", item["json"]["url"])

    def test_describe_policy_file_omits_json_artifact_when_spec_is_missing(self):
        policy = self.write("NC_AI검색_정책서_간소화_v0.1.html", "<html></html>")

        item = web_app.describe_policy_file(policy)

        self.assertIsNone(item["json"])

    def test_list_policy_files_excludes_bpmn_viewer_artifacts(self):
        self.write("NC_AI검색_정책서_간소화_v0.1.html", "<html></html>")
        self.write("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도.bpmn", "<xml></xml>")
        self.write("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도_viewer.html", "<html></html>")

        items = web_app.list_policy_files()

        self.assertEqual(["NC_AI검색_정책서_간소화_v0.1.html"], [item["name"] for item in items])
        self.assertTrue(web_app.re_match_policy_filename("NC_AI검색_정책서_간소화_v0.1.html"))
        self.assertFalse(web_app.re_match_policy_filename("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도_viewer.html"))

    def test_intermediate_cleanup_keeps_final_outputs_and_final_reports(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.1.html"
        final_html = self.write(policy_name, "<html></html>")
        bpmn = self.write("NC_AI검색_정책서_간소화_v0.1_전체업무흐름도.bpmn", "<xml></xml>")
        spec = self.write("AI검색_policy_spec.json", "{}")
        blueprint = self.write("AI검색_authoring_blueprint.json", "{}")
        quality = self.write("quality/NC_AI검색_정책서_간소화_v0.1_quality_report.json", "{}")
        step = self.write("steps/NC_AI검색_정책서_간소화_v0.1_06_state.html", "<html></html>")
        checkpoint = self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json", "{}")
        diagnostic = self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_06_state_attempt1_failed_diagnostic.json", "{}")
        stage_report = self.reports_dir / f"{policy_name}_06_state_attempt1_inspection.json"
        final_report = self.reports_dir / f"{policy_name}_final_inspection.json"
        dev_qa_report = self.reports_dir / f"{policy_name}_dev_qa_review.json"
        stage_report.write_text("{}", encoding="utf-8")
        final_report.write_text("{}", encoding="utf-8")
        dev_qa_report.write_text("{}", encoding="utf-8")
        for path in (step, checkpoint, diagnostic, stage_report, final_report, dev_qa_report):
            self.make_old(path)

        result = web_app.cleanup_policy_intermediate_artifacts(policy_name, retention_hours=24)

        self.assertTrue(
            any(item.endswith("output/steps/NC_AI검색_정책서_간소화_v0.1_06_state.html") for item in result["deletedFiles"])
        )
        self.assertFalse(step.exists())
        self.assertFalse(checkpoint.exists())
        self.assertFalse(diagnostic.exists())
        self.assertFalse(stage_report.exists())
        self.assertTrue(final_html.exists())
        self.assertTrue(bpmn.exists())
        self.assertTrue(spec.exists())
        self.assertTrue(blueprint.exists())
        self.assertTrue(quality.exists())
        self.assertTrue(final_report.exists())
        self.assertTrue(dev_qa_report.exists())

    def test_intermediate_cleanup_respects_retention_window(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.1.html"
        self.write(policy_name, "<html></html>")
        step = self.write("steps/NC_AI검색_정책서_간소화_v0.1_06_state.html", "<html></html>")
        checkpoint = self.write("checkpoints/NC_AI검색_정책서_간소화_v0.1_latest_checkpoint.json", "{}")

        result = web_app.cleanup_policy_intermediate_artifacts(policy_name, retention_hours=24)

        self.assertEqual([], result["deletedFiles"])
        self.assertTrue(step.exists())
        self.assertTrue(checkpoint.exists())

    def test_runtime_batch_cleanup_removes_old_mock_dirs_only(self):
        old_mock = self.output_root / "mock_34_regen_20260507_211313"
        old_mock.mkdir(parents=True, exist_ok=True)
        (old_mock / "NC_AI검색_정책서_간소화_v0.1.html").write_text("<html></html>", encoding="utf-8")
        keep_dir = self.output_root / "state_transition_test"
        keep_dir.mkdir(parents=True, exist_ok=True)
        (keep_dir / "state.json").write_text("{}", encoding="utf-8")
        self.make_old(old_mock)
        self.make_old(keep_dir)

        result = web_app.cleanup_stale_runtime_batch_dirs(retention_hours=24)

        self.assertFalse(old_mock.exists())
        self.assertTrue(keep_dir.exists())
        self.assertEqual(1, len(result["deletedDirs"]))
        self.assertGreater(result["deletedBytes"], 0)

    def test_runtime_batch_cleanup_removes_only_safe_old_runtime_dirs(self):
        old_mock = self.output_root / "mock_eval_old"
        old_llm_test = self.output_root / "llm_graph_test_ai_search_20260512_082445"
        keep_reference = self.output_root / "reference_html"
        keep_status = self.output_root / "status"
        keep_state_test = self.output_root / "state_transition_test"
        for path in (old_mock, old_llm_test, keep_reference, keep_status, keep_state_test):
            path.mkdir(parents=True, exist_ok=True)
            (path / "artifact.html").write_text("<html></html>", encoding="utf-8")
            self.make_old(path)

        result = web_app.cleanup_stale_runtime_batch_dirs(retention_hours=24)

        self.assertFalse(old_mock.exists())
        self.assertFalse(old_llm_test.exists())
        self.assertTrue(keep_reference.exists())
        self.assertTrue(keep_status.exists())
        self.assertTrue(keep_state_test.exists())
        self.assertEqual(2, len(result["deletedDirs"]))
        self.assertGreater(result["deletedBytes"], 0)

    def test_runtime_batch_cleanup_respects_retention_window(self):
        recent_mock = self.output_root / "mock_34_regen_20260508_114357"
        recent_mock.mkdir(parents=True, exist_ok=True)
        (recent_mock / "NC_AI검색_정책서_간소화_v0.1.html").write_text("<html></html>", encoding="utf-8")

        result = web_app.cleanup_stale_runtime_batch_dirs(retention_hours=24)

        self.assertTrue(recent_mock.exists())
        self.assertEqual([], result["deletedDirs"])

    def test_policy_lifecycle_defaults_to_in_progress_and_can_be_completed(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        path = self.write(policy_name, "<html></html>")

        item = web_app.describe_policy_file(path)
        self.assertEqual("in_progress", item["lifecycle"]["status"])
        self.assertEqual("작성 중", item["documentStatus"])

        updated = web_app.update_policy_lifecycle_from_payload(
            {"name": policy_name, "status": "completed", "author": "Planner"}
        )
        status_path = self.output_root / "status/NC_나의가입정보_정책서_간소화_v0.4_status.json"
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual("completed", updated["lifecycle"]["status"])
        self.assertEqual("작성 완료", updated["documentStatus"])
        self.assertEqual("Planner", status_payload["updatedBy"])
        self.assertEqual("completed", status_payload["history"][-1]["to"])

    def test_completed_policy_blocks_edit_and_delete_until_canceled(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        self.write(policy_name, "<html></html>")
        web_app.update_policy_lifecycle_from_payload({"name": policy_name, "status": "completed"})

        with self.assertRaises(ValueError):
            web_app.delete_policy_from_payload({"name": policy_name})

        web_app.update_policy_lifecycle_from_payload({"name": policy_name, "status": "in_progress"})
        web_app.delete_policy_from_payload({"name": policy_name})
        self.assertFalse((self.output_root / policy_name).exists())

    def test_manual_edit_rejects_stale_base_hash(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        original = "<html><body><h2>0. 문서 히스토리</h2><table><tbody></tbody></table><p>이전 내용</p></body></html>"
        current = "<html><body><h2>0. 문서 히스토리</h2><table><tbody></tbody></table><p>다른 사용자 수정</p></body></html>"
        path = self.write(policy_name, original)
        base_hash = web_app.document_content_hash(original)
        path.write_text(current, encoding="utf-8")

        with self.assertRaises(ValueError):
            web_app.save_manual_edit_from_payload(
                {
                    "name": policy_name,
                    "html": "<html><body><p>내 수정</p></body></html>",
                    "saveMode": "overwrite",
                    "baseHash": base_hash,
                }
            )

        self.assertIn("다른 사용자 수정", path.read_text(encoding="utf-8"))

    def test_manual_edit_sanitizes_executable_html(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        original = "<html><body><h2>0. 문서 히스토리</h2><table><tbody></tbody></table><p>이전 내용</p></body></html>"
        path = self.write(policy_name, original)
        self.write("NC_나의가입정보_정책서_간소화_v0.4_spec.json", '{"meta": {"version": "v0.4"}}')

        web_app.save_manual_edit_from_payload(
            {
                "name": policy_name,
                "html": """
                <html><body>
                <h2>0. 문서 히스토리</h2><table><tbody></tbody></table>
                <p onclick="fetch('/api/policies')">수정 내용</p>
                <img src="x" onerror="alert(1)"/>
                <a href="javascript:alert(1)">위험 링크</a>
                <script>fetch('/api/admin/locks/cleanup')</script>
                <iframe src="/api/policies"></iframe>
                </body></html>
                """,
                "saveMode": "overwrite",
                "baseHash": web_app.document_content_hash(original),
            }
        )

        saved = path.read_text(encoding="utf-8")
        self.assertIn("수정 내용", saved)
        self.assertNotIn("<script", saved.casefold())
        self.assertNotIn("<iframe", saved.casefold())
        self.assertNotIn("onclick", saved.casefold())
        self.assertNotIn("onerror", saved.casefold())
        self.assertNotIn("javascript:", saved.casefold())

    def test_reference_html_edit_sanitizes_and_overwrites_reference_file(self):
        original = "<html><body><main><p>이전 분석</p></main></body></html>"
        path = self.write("reference_html/ia-analysis.html", original)
        base_hash = web_app.document_content_hash(original)

        result = web_app.save_reference_html_edit_from_payload(
            {
                "url": "/output/reference_html/ia-analysis.html",
                "html": """
                <!DOCTYPE html>
                <html><body>
                  <main>
                    <p onclick="fetch('/api/policies')">수정 분석</p>
                    <img src="x" onerror="alert(1)"/>
                    <a href="javascript:alert(1)">위험 링크</a>
                    <script>alert(1)</script>
                    <iframe src="/api/policies"></iframe>
                  </main>
                </body></html>
                """,
                "saveMode": "overwrite",
                "baseHash": base_hash,
            }
        )

        self.assertEqual(path, result)
        saved = path.read_text(encoding="utf-8")
        self.assertIn("수정 분석", saved)
        self.assertNotIn("이전 분석", saved)
        self.assertNotIn("<script", saved.casefold())
        self.assertNotIn("<iframe", saved.casefold())
        self.assertNotIn("onclick", saved.casefold())
        self.assertNotIn("onerror", saved.casefold())
        self.assertNotIn("javascript:", saved.casefold())

    def test_reference_html_edit_rejects_non_reference_path(self):
        self.write("NC_AI검색_정책서_간소화_v0.10.html", "<html><body><p>정책서</p></body></html>")

        with self.assertRaisesRegex(ValueError, "현황 분석 문서만"):
            web_app.save_reference_html_edit_from_payload(
                {
                    "url": "/output/NC_AI검색_정책서_간소화_v0.10.html",
                    "html": "<html><body><p>수정</p></body></html>",
                    "saveMode": "overwrite",
                }
            )

    def test_manual_edit_preserves_generated_diagram_runtime_scripts_only_from_source(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        original = """
        <html><head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script src="https://unpkg.com/bpmn-js/dist/bpmn-viewer.production.min.js"></script>
        <script>
        (function () {
          function renderBpmnViewers() { document.querySelectorAll("[data-bpmn-viewer]"); }
          function bindBpmnDownload() { document.querySelector("[data-bpmn-download]"); }
          window.mermaid.initialize({ startOnLoad: false });
        })();
        </script>
        </head><body>
        <h2>0. 문서 히스토리</h2><table><tbody></tbody></table>
        <div class="bpmn-viewer" data-bpmn-source-id="bpmn-process-xml" data-bpmn-viewer="true"></div>
        <script id="bpmn-process-xml" type="application/json">{"xml":"<bpmn/>"}</script>
        <p>이전 내용</p>
        </body></html>
        """
        path = self.write(policy_name, original)
        self.write("NC_나의가입정보_정책서_간소화_v0.4_spec.json", '{"meta": {"version": "v0.4"}}')

        web_app.save_manual_edit_from_payload(
            {
                "name": policy_name,
                "html": """
                <html><head>
                <script src="https://evil.example/x.js"></script>
                </head><body>
                <h2>0. 문서 히스토리</h2><table><tbody></tbody></table>
                <p>수정 내용</p>
                <script id="bpmn-process-xml" type="application/json">{"xml":"<tampered/>"}</script>
                <script>alert(1)</script>
                </body></html>
                """,
                "saveMode": "overwrite",
                "baseHash": web_app.document_content_hash(original),
            }
        )

        saved = path.read_text(encoding="utf-8")
        self.assertIn("mermaid.min.js", saved)
        self.assertIn("bpmn-viewer.production.min.js", saved)
        self.assertIn("renderBpmnViewers", saved)
        self.assertIn('"xml":"<bpmn/>"', saved)
        self.assertNotIn("evil.example", saved)
        self.assertNotIn("<tampered/>", saved)
        self.assertNotIn("alert(1)", saved)

    def test_manual_edit_preserves_document_bullets_and_font_size_styles(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        original = "<html><body><h2>0. 문서 히스토리</h2><table><tbody></tbody></table><p>이전 내용</p></body></html>"
        path = self.write(policy_name, original)
        self.write("NC_나의가입정보_정책서_간소화_v0.4_spec.json", '{"meta": {"version": "v0.4"}}')

        web_app.save_manual_edit_from_payload(
            {
                "name": policy_name,
                "html": """
                <html><body>
                <h2>0. 문서 히스토리</h2><table><tbody></tbody></table>
                <div class="policy-item-title">• 처리 기준</div>
                <div class="policy-item-content">
                  <span class="policy-item-line">- 첫 번째 기준<br/></span>
                  <span class="policy-item-line" style="font-size: 14px;">- 두 번째 기준<br/></span>
                </div>
                <p><span style="font-size: 15px;" data-nc-font-size="15">본문 크기 유지</span></p>
                <ul><li>목록 불릿 유지</li></ul>
                </body></html>
                """,
                "saveMode": "overwrite",
                "baseHash": web_app.document_content_hash(original),
            }
        )

        saved = path.read_text(encoding="utf-8")
        self.assertIn("• 처리 기준", saved)
        self.assertIn('class="policy-item-line"', saved)
        self.assertIn("font-size: 14px", saved)
        self.assertIn("font-size: 15px", saved)
        self.assertIn("<ul><li>목록 불릿 유지</li></ul>", saved)
        version_spec = json.loads((self.output_root / "NC_나의가입정보_정책서_간소화_v0.4_spec.json").read_text(encoding="utf-8"))
        self.assertEqual("v0.4", version_spec["meta"]["version"])
        self.assertEqual("manual_edit_overwrite", version_spec["meta"]["version_spec_reason"])

    def test_manual_edit_preserves_editor_indentation_styles(self):
        policy_name = "NC_추천_정책서_간소화_v0.4.html"
        original = "<html><body><h2>0. 문서 히스토리</h2><table><tbody></tbody></table><p>이전 내용</p></body></html>"
        path = self.write(policy_name, original)
        self.write("NC_추천_정책서_간소화_v0.4_spec.json", '{"meta": {"version": "v0.4"}}')

        web_app.save_manual_edit_from_payload(
            {
                "name": policy_name,
                "html": """
                <html><body>
                <h2>0. 문서 히스토리</h2><table><tbody></tbody></table>
                <p style="margin-left: 24px;" data-nc-indent="24">들여쓰기 문단</p>
                <div class="policy-item-content" style="margin-left: 48px;" data-nc-indent="48">정책 항목 들여쓰기</div>
                <table><tbody><tr><td style="padding-left: 24px;" data-nc-indent="24">표 셀 들여쓰기</td></tr></tbody></table>
                </body></html>
                """,
                "saveMode": "overwrite",
                "baseHash": web_app.document_content_hash(original),
            }
        )

        saved = path.read_text(encoding="utf-8")
        self.assertIn("margin-left: 24px", saved)
        self.assertIn("margin-left: 48px", saved)
        self.assertIn("padding-left: 24px", saved)
        self.assertIn('data-nc-indent="24"', saved)
        self.assertIn('data-nc-indent="48"', saved)

    def test_upload_policy_html_registers_uploaded_file_safely(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        self.write(base_name, "<html><body><p>서버 기준 문서</p></body></html>")
        self.write("NC_상품목록_정책서_간소화_v0.3_spec.json", '{"meta": {"version": "v0.3"}, "document_history": []}')

        result = web_app.upload_policy_html_from_payload(
            {
                "baseName": base_name,
                "name": "상품 상세 정책서_v0.2.html",
                "html": """
                <html><head><title>상품 상세 정책서 간소화 버전 v0.2</title></head><body>
                <div class="eyebrow">NOVA 통합채널 정책서 간소화 버전</div>
                <h1>상품 상세 정책서</h1>
                <table class="meta">
                  <tr><th>문서 구분</th><td>간소화 버전</td></tr>
                  <tr><th>버전</th><td class="mono">v0.2</td></tr>
                </table>
                <h2>0. 문서 히스토리</h2>
                <table><tbody></tbody></table>
                <p onclick="alert(1)">등록 내용</p>
                <script>alert(1)</script>
                </body></html>
                """,
            }
        )

        self.assertEqual("NC_상품목록_정책서_간소화_v0.13.html", result.name)
        saved = result.read_text(encoding="utf-8")
        self.assertIn("등록 내용", saved)
        self.assertIn("<title>상품목록 정책서 간소화 버전 v0.13</title>", saved)
        self.assertIn("<h1>상품목록 정책서</h1>", saved)
        self.assertIn('<td class="mono">v0.13</td>', saved)
        self.assertIn("HTML 파일 업로드로 서버 기준 새 버전을 등록했습니다.", saved)
        self.assertNotIn("<script", saved.casefold())
        self.assertNotIn("onclick", saved.casefold())
        item = web_app.describe_policy_file(result)
        self.assertEqual("상품목록", item["topic"])
        self.assertEqual("간소화", item["templateLabel"])
        version_spec = json.loads((self.output_root / "NC_상품목록_정책서_간소화_v0.13_spec.json").read_text(encoding="utf-8"))
        self.assertEqual("v0.13", version_spec["meta"]["version"])
        self.assertEqual("html_upload", version_spec["meta"]["version_spec_reason"])

    def test_upload_policy_html_uses_server_versions_not_uploaded_file_version(self):
        base_name = "NC_AI검색_정책서_간소화_v0.1.html"
        latest_name = "NC_AI검색_정책서_간소화_v0.3.html"
        self.write(base_name, "<html><body><p>기존</p></body></html>")
        self.write(latest_name, "<html><body><p>최신</p></body></html>")

        result = web_app.upload_policy_html_from_payload(
            {
                "baseName": base_name,
                "name": "NC_다른주제_정책서_간소화_v0.2.html",
                "html": "<html><body><p>업로드</p></body></html>",
            }
        )

        self.assertEqual("NC_AI검색_정책서_간소화_v0.13.html", result.name)
        self.assertIn("기존", (self.output_root / base_name).read_text(encoding="utf-8"))
        self.assertIn("최신", (self.output_root / latest_name).read_text(encoding="utf-8"))
        self.assertIn("업로드", result.read_text(encoding="utf-8"))

    def test_upload_policy_json_renders_html_spec_and_bpmn_artifacts(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        sample_spec = json.loads((PROJECT_ROOT / "output" / "상품목록_policy_spec.json").read_text(encoding="utf-8"))
        self.write(base_name, "<html><body><p>기준 문서</p></body></html>")

        result = web_app.upload_policy_json_from_payload(
            {
                "baseName": base_name,
                "name": "상품목록_policy_spec.json",
                "json": json.dumps({"spec": sample_spec}, ensure_ascii=False),
                "author": "Tester",
            }
        )

        self.assertEqual("NC_상품목록_정책서_간소화_v0.13.html", result.name)
        saved_html = result.read_text(encoding="utf-8")
        self.assertIn("<style>", saved_html)
        self.assertIn("BPMN XML 다운로드", saved_html)
        self.assertIn('data-bpmn-viewer="true"', saved_html)
        self.assertIn("<svg", saved_html)

        version_spec_path = self.output_root / "NC_상품목록_정책서_간소화_v0.13_spec.json"
        latest_spec_path = self.output_root / "상품목록_policy_spec.json"
        bpmn_path = self.output_root / "NC_상품목록_정책서_간소화_v0.13_전체업무흐름도.bpmn"
        bpmn_viewer_path = self.output_root / "NC_상품목록_정책서_간소화_v0.13_전체업무흐름도_viewer.html"
        self.assertTrue(version_spec_path.exists())
        self.assertTrue(latest_spec_path.exists())
        self.assertTrue(bpmn_path.exists())
        self.assertTrue(bpmn_viewer_path.exists())
        self.assertIn("<bpmn:definitions", bpmn_path.read_text(encoding="utf-8"))
        self.assertIn("bpmn.io bpmn-js viewer", bpmn_viewer_path.read_text(encoding="utf-8"))

        version_spec = json.loads(version_spec_path.read_text(encoding="utf-8"))
        latest_spec = json.loads(latest_spec_path.read_text(encoding="utf-8"))
        self.assertEqual("v0.13", version_spec["meta"]["version"])
        self.assertEqual("json_upload", version_spec["meta"]["version_spec_reason"])
        self.assertEqual("상품목록_policy_spec.json", version_spec["meta"]["version_spec_source"])
        self.assertEqual("simple", version_spec["meta"]["template_type"])
        self.assertEqual("상품목록", version_spec["meta"]["topic_slug"])
        self.assertEqual(version_spec["meta"]["version"], latest_spec["meta"]["version"])
        self.assertEqual("JSON 파일 업로드로 서버 템플릿, SVG, BPMN 뷰어를 재생성해 새 버전을 등록했습니다.", version_spec["history"][-1]["change"])

    def test_upload_policy_json_records_validation_warnings_without_blocking_render(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        sample_spec = json.loads((PROJECT_ROOT / "output" / "상품목록_policy_spec.json").read_text(encoding="utf-8"))
        sample_spec.setdefault("actors", []).append(
            {
                "id": "ACT-PCL-999",
                "name": "검증 경고 액터",
                "type": "system",
                "description": "렌더링은 가능하지만 유즈케이스 연결 검증 경고를 발생시키는 액터입니다.",
            }
        )
        self.write(base_name, "<html><body><p>기준 문서</p></body></html>")

        result = web_app.upload_policy_json_from_payload(
            {
                "baseName": base_name,
                "name": "상품목록_policy_spec.json",
                "json": json.dumps(sample_spec, ensure_ascii=False),
                "author": "Tester",
            }
        )

        self.assertEqual("NC_상품목록_정책서_간소화_v0.13.html", result.name)
        self.assertIn("<style>", result.read_text(encoding="utf-8"))
        version_spec = json.loads((self.output_root / "NC_상품목록_정책서_간소화_v0.13_spec.json").read_text(encoding="utf-8"))
        warnings = version_spec["meta"].get("json_upload_validation_warnings", [])
        self.assertGreater(len(warnings), 0)
        self.assertEqual(len(warnings), version_spec["meta"].get("json_upload_validation_warning_count"))
        self.assertTrue(any("액터" in warning for warning in warnings))

    def test_upload_policy_json_rejects_completed_policy(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        sample_spec = json.loads((PROJECT_ROOT / "output" / "상품목록_policy_spec.json").read_text(encoding="utf-8"))
        self.write(base_name, "<html><body><p>완료 문서</p></body></html>")
        web_app.update_policy_lifecycle_from_payload({"name": base_name, "status": "completed"})

        with self.assertRaisesRegex(ValueError, "작성 완료 상태"):
            web_app.upload_policy_json_from_payload(
                {
                    "baseName": base_name,
                    "name": "상품목록_policy_spec.json",
                    "json": json.dumps(sample_spec, ensure_ascii=False),
                }
            )

        self.assertFalse((self.output_root / "NC_상품목록_정책서_간소화_v0.4.html").exists())

    def test_upload_policy_json_rejects_template_mismatch(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        sample_spec = json.loads((PROJECT_ROOT / "output" / "상품목록_policy_spec.json").read_text(encoding="utf-8"))
        sample_spec["meta"]["template_type"] = "full"
        self.write(base_name, "<html><body><p>기준 문서</p></body></html>")

        with self.assertRaisesRegex(ValueError, "문서 유형"):
            web_app.upload_policy_json_from_payload(
                {
                    "baseName": base_name,
                    "name": "상품목록_policy_spec.json",
                    "json": json.dumps(sample_spec, ensure_ascii=False),
                }
            )

    def test_upload_policy_json_rejects_topic_mismatch(self):
        base_name = "NC_상품목록_정책서_간소화_v0.3.html"
        sample_spec = json.loads((PROJECT_ROOT / "output" / "상품목록_policy_spec.json").read_text(encoding="utf-8"))
        sample_spec["meta"]["topic"] = "AI검색"
        self.write(base_name, "<html><body><p>기준 문서</p></body></html>")

        with self.assertRaisesRegex(ValueError, "주제"):
            web_app.upload_policy_json_from_payload(
                {
                    "baseName": base_name,
                    "name": "상품목록_policy_spec.json",
                    "json": json.dumps(sample_spec, ensure_ascii=False),
                }
            )

    def test_upload_policy_html_rejects_completed_policy(self):
        base_name = "NC_AI검색_정책서_간소화_v0.1.html"
        self.write(base_name, "<html><body><p>완료 문서</p></body></html>")
        web_app.update_policy_lifecycle_from_payload({"name": base_name, "status": "completed"})

        with self.assertRaisesRegex(ValueError, "작성 완료 상태"):
            web_app.upload_policy_html_from_payload(
                {
                    "baseName": base_name,
                    "name": "외부 작성본.html",
                    "html": "<html><body><p>업로드</p></body></html>",
                }
            )

        self.assertFalse((self.output_root / "NC_AI검색_정책서_간소화_v0.2.html").exists())

    def test_policy_create_rejects_existing_topic_without_rewrite_flag(self):
        self.write("NC_AI검색_정책서_간소화_v0.1.html", "<html></html>")

        with self.assertRaisesRegex(ValueError, "이미 같은 주제로 생성된 정책서"):
            web_app.start_policy_job(
                {
                    "topic": "AI검색",
                    "templateType": "simple",
                    "reviewMode": "auto",
                    "inspectionMode": "none",
                    "writerMode": "mock",
                }
            )

    def test_policy_create_allows_existing_topic_when_rewrite_requested(self):
        self.write("NC_AI검색_정책서_간소화_v0.1.html", "<html></html>")

        with patch.object(web_app.threading.Thread, "start", lambda _thread: None):
            job = web_app.start_policy_job(
                {
                    "topic": "AI검색",
                    "templateType": "simple",
                    "reviewMode": "auto",
                    "inspectionMode": "none",
                    "writerMode": "mock",
                    "rewriteExisting": True,
                }
            )

        try:
            self.assertEqual("AI검색", job["topic"])
            self.assertTrue(job["rewriteExisting"])
            self.assertEqual("queued", job["status"])
        finally:
            with web_app.JOBS_LOCK:
                web_app.JOBS.pop(job["id"], None)

    def test_policy_create_rejects_completed_topic_even_when_rewrite_requested(self):
        policy_name = "NC_AI검색_정책서_간소화_v0.1.html"
        self.write(policy_name, "<html></html>")
        web_app.update_policy_lifecycle_from_payload({"name": policy_name, "status": "completed"})

        with self.assertRaisesRegex(ValueError, "작성 완료 상태"):
            web_app.start_policy_job(
                {
                    "topic": "AI검색",
                    "templateType": "simple",
                    "reviewMode": "auto",
                    "inspectionMode": "none",
                    "writerMode": "mock",
                    "rewriteExisting": True,
                }
            )

    def test_upload_policy_html_requires_server_base_policy(self):
        with self.assertRaisesRegex(ValueError, "기준 정책서"):
            web_app.upload_policy_html_from_payload(
                {
                    "name": "외부 작성본.html",
                    "html": "<html><body><p>업로드</p></body></html>",
                }
            )

    def test_revision_llm_mode_requires_access_token_before_lock(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        self.write(policy_name, "<html><body><p>수정 대상</p></body></html>")

        with self.assertRaisesRegex(ValueError, "LLM 사용 권한"):
            web_app.start_revision_job(
                {
                    "name": policy_name,
                    "instruction": "문장을 다듬어줘.",
                    "writerMode": "llm",
                }
            )

        self.assertFalse(any(web_app.LOCK_DIR.glob("doc_*.lock")))

    def test_delete_policy_respects_active_document_lock(self):
        policy_name = "NC_나의가입정보_정책서_간소화_v0.4.html"
        self.write(policy_name, "<html></html>")
        lock_key = web_app.document_lock_key(policy_name)
        lock_path = web_app.LOCK_DIR / f"{lock_key}.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "lock_key": lock_key,
                    "job_id": "active-edit",
                    "operation": "manual_edit",
                    "file_name": policy_name,
                    "status": "running",
                    "started_at_epoch": web_app.time.time(),
                    "updated_at_epoch": web_app.time.time(),
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(web_app.JobConflict):
            web_app.delete_policy_from_payload({"name": policy_name})

        self.assertTrue((self.output_root / policy_name).exists())

    def test_service_health_detects_and_cleans_only_stale_locks(self):
        active_key = web_app.document_lock_key("NC_활성_정책서_간소화_v0.1.html")
        stale_key = web_app.job_lock_key("만료작업", "simple")
        active_path = web_app.LOCK_DIR / f"{active_key}.lock"
        stale_path = web_app.LOCK_DIR / f"{stale_key}.lock"
        active_path.write_text(
            json.dumps(
                {
                    "lock_key": active_key,
                    "job_id": "active-doc",
                    "operation": "manual_edit",
                    "file_name": "NC_활성_정책서_간소화_v0.1.html",
                    "status": "running",
                    "started_at_epoch": web_app.time.time(),
                    "updated_at_epoch": web_app.time.time(),
                }
            ),
            encoding="utf-8",
        )
        stale_path.write_text(
            json.dumps(
                {
                    "lock_key": stale_key,
                    "job_id": "stale-job",
                    "topic": "만료작업",
                    "template_type": "simple",
                    "status": "running",
                    "started_at_epoch": web_app.time.time() - web_app.JOB_LOCK_TTL_SECONDS - 10,
                    "updated_at_epoch": web_app.time.time() - web_app.JOB_LOCK_TTL_SECONDS - 10,
                }
            ),
            encoding="utf-8",
        )

        dashboard = web_app.build_service_health_dashboard()
        self.assertEqual(1, dashboard["summary"]["activeLocks"])
        self.assertEqual(1, dashboard["summary"]["staleLocks"])

        result = web_app.cleanup_service_locks({})
        self.assertEqual([stale_path.name], [item["fileName"] for item in result["deleted"]])
        self.assertTrue(active_path.exists())
        self.assertFalse(stale_path.exists())

    def test_service_health_cleans_terminal_locks(self):
        lock_key = web_app.job_lock_key("완료작업", "simple")
        lock_path = web_app.LOCK_DIR / f"{lock_key}.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "lock_key": lock_key,
                    "job_id": "done-job",
                    "topic": "완료작업",
                    "template_type": "simple",
                    "status": "completed",
                    "started_at_epoch": web_app.time.time(),
                    "updated_at_epoch": web_app.time.time(),
                }
            ),
            encoding="utf-8",
        )

        result = web_app.cleanup_service_locks({})

        self.assertEqual([lock_path.name], [item["fileName"] for item in result["deleted"]])
        self.assertFalse(lock_path.exists())

    def test_service_health_reports_persistent_root_breakdown(self):
        persistent_root = self.root / "persistent"
        output_root = persistent_root / "output"
        reports_dir = persistent_root / "reports" / "inspections"
        extra_dir = persistent_root / "uploads"
        output_root.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        extra_dir.mkdir(parents=True, exist_ok=True)
        (output_root / "policy.html").write_text("output-bytes", encoding="utf-8")
        (reports_dir / "inspection.json").write_text("report-bytes", encoding="utf-8")
        (extra_dir / "raw.bin").write_bytes(b"x" * 25)

        with patch.object(web_app, "OUTPUT_ROOT", output_root), patch.object(web_app, "REPORTS_DIR", reports_dir), patch.dict(os.environ, {"NC_PERSISTENT_ROOT": str(persistent_root)}):
            dashboard = web_app.build_service_health_dashboard()

        disk = dashboard["disk"]
        self.assertEqual(str(persistent_root), disk["persistentRoot"])
        self.assertGreaterEqual(disk["persistentRootBytes"], disk["totalBytes"])
        self.assertGreater(disk["untrackedPersistentBytes"], 0)
        self.assertIn("uploads", [item["name"] for item in disk["persistentRootChildren"]])
        self.assertEqual(disk["persistentRootBytes"], dashboard["summary"]["diskUsageBytes"])

    def test_deleted_open_file_summary_detects_proc_fd_links(self):
        persistent_root = self.root / "persistent"
        proc_root = self.root / "proc"
        fd_dir = proc_root / "123" / "fd"
        fd_dir.mkdir(parents=True, exist_ok=True)
        (proc_root / "123" / "comm").write_text("python", encoding="utf-8")
        deleted_target = persistent_root / "output" / "old.log"
        deleted_target.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(f"{deleted_target} (deleted)", fd_dir / "7")
        os.symlink("/tmp/outside.log (deleted)", fd_dir / "8")

        summary = web_app.summarize_deleted_open_files(proc_root=proc_root, path_prefix=persistent_root)

        self.assertTrue(summary["supported"])
        self.assertEqual(1, len(summary["items"]))
        self.assertEqual("123", summary["items"][0]["pid"])
        self.assertEqual("7", summary["items"][0]["fd"])
        self.assertEqual("python", summary["items"][0]["process"])
        self.assertEqual(str(deleted_target), summary["items"][0]["path"])

    def test_runtime_cleanup_manifest_deletes_only_output_and_report_artifacts(self):
        output_file = self.output_root / "NC_이전주제_정책서_간소화_v0.1.html"
        output_file.write_text("<html></html>", encoding="utf-8")
        output_dir = self.output_root / "mock_eval_old"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "old.html").write_text("<html></html>", encoding="utf-8")
        repo_root = self.root / "repo"
        reports_root = repo_root / "reports"
        cache_file = reports_root / "cache" / "topic_learning_old.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("{}", encoding="utf-8")
        ignored_file = repo_root / "input" / "keep.txt"
        ignored_file.parent.mkdir(parents=True, exist_ok=True)
        ignored_file.write_text("keep", encoding="utf-8")
        manifest = reports_root / "module_34_cleanup_removed_files.json"
        manifest.write_text(
            json.dumps(
                {
                    "removed": [
                        "output/NC_이전주제_정책서_간소화_v0.1.html",
                        "reports/cache/topic_learning_old.json",
                        "input/keep.txt",
                        "../outside.txt",
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        refresh_manifest = reports_root / "runtime_seed_refresh_bpmn_io_cleanup_removed_files.json"
        refresh_manifest.write_text(
            json.dumps({"removed": ["output/mock_eval_old"]}, ensure_ascii=False),
            encoding="utf-8",
        )

        with patch.object(web_app, "PROJECT_ROOT", repo_root), patch.object(web_app, "REPORTS_DIR", reports_root / "inspections"):
            web_app.apply_runtime_cleanup_manifests()

        self.assertFalse(output_file.exists())
        self.assertFalse(output_dir.exists())
        self.assertFalse(cache_file.exists())
        self.assertTrue(ignored_file.exists())

    def test_agent_usage_dashboard_groups_schema_calls(self):
        log_path = self.root / "llm_calls.jsonl"
        log_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "timestamp": "2026-05-02T10:00:00",
                            "event": "request_success",
                            "schema_name": "process_chapter_chunk",
                            "model": "gpt-5.5",
                            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                        }
                    ),
                    json.dumps(
                        {
                            "timestamp": "2026-05-02T10:01:00",
                            "event": "request_success",
                            "schema_name": "policy_json_inspection",
                            "model": "gpt-5.4",
                            "usage": {
                                "input_tokens": 20,
                                "output_tokens": 8,
                                "total_tokens": 28,
                                "output_tokens_details": {"reasoning_tokens": 3},
                            },
                        }
                    ),
                ]
            ),
            encoding="utf-8",
        )

        dashboard = web_app.build_agent_usage_dashboard(log_path)
        rows = {row["agent"]: row for row in dashboard["items"]}

        self.assertEqual(2, dashboard["summary"]["calls"])
        self.assertEqual(43, dashboard["summary"]["totalTokens"])
        self.assertEqual(15, rows["Process Agent"]["totalTokens"])
        self.assertEqual(28, rows["Inspector Agent"]["totalTokens"])
        self.assertEqual(3, rows["Inspector Agent"]["reasoningTokens"])

    def test_agent_usage_dashboard_can_use_openai_usage_summary(self):
        log_path = self.root / "llm_calls.jsonl"
        log_path.write_text("", encoding="utf-8")

        usage_payload = {
            "data": [
                {
                    "results": [
                        {
                            "num_model_requests": 7,
                            "input_tokens": 1000,
                            "output_tokens": 400,
                            "input_cached_tokens": 200,
                        }
                    ]
                }
            ]
        }
        cost_payload = {
            "data": [
                {
                    "results": [
                        {"amount": {"value": 1.25, "currency": "usd"}},
                    ]
                }
            ]
        }

        with patch.dict(
            web_app.os.environ,
            {"OPENAI_USAGE_API_KEY": "test-admin-key", "OPENAI_USAGE_DASHBOARD_ENABLED": "1"},
            clear=False,
        ), patch.object(web_app, "fetch_openai_usage_pages", side_effect=[[usage_payload], [cost_payload]]):
            dashboard = web_app.build_agent_usage_dashboard(log_path)

        summary = dashboard["summary"]
        self.assertEqual("openai_api", summary["usageSource"])
        self.assertEqual(7, summary["calls"])
        self.assertEqual(1400, summary["totalTokens"])
        self.assertEqual(200, summary["cachedInputTokens"])
        self.assertEqual(1.25, summary["estimatedCostUsd"])

    def test_agent_usage_dashboard_uses_existing_openai_api_key_for_usage_summary(self):
        log_path = self.root / "llm_calls.jsonl"
        log_path.write_text("", encoding="utf-8")
        usage_payload = {"data": [{"results": [{"num_model_requests": 3, "input_tokens": 700, "output_tokens": 300}]}]}
        cost_payload = {"data": [{"results": [{"amount": {"value": 0.75, "currency": "usd"}}]}]}

        with patch.dict(
            web_app.os.environ,
            {
                "OPENAI_API_KEY": "test-existing-key",
                "OPENAI_USAGE_API_KEY": "",
                "OPENAI_ADMIN_API_KEY": "",
                "OPENAI_USAGE_DASHBOARD_ENABLED": "1",
            },
            clear=False,
        ), patch.object(web_app, "fetch_openai_usage_pages", side_effect=[[usage_payload], [cost_payload]]) as fetch_mock:
            dashboard = web_app.build_agent_usage_dashboard(log_path)

        self.assertEqual("openai_api", dashboard["summary"]["usageSource"])
        self.assertEqual(3, dashboard["summary"]["calls"])
        self.assertEqual(1000, dashboard["summary"]["totalTokens"])
        self.assertEqual(0.75, dashboard["summary"]["estimatedCostUsd"])
        self.assertEqual(2, fetch_mock.call_count)

    def test_agent_usage_dashboard_explains_missing_usage_scope(self):
        log_path = self.root / "llm_calls.jsonl"
        log_path.write_text("", encoding="utf-8")

        with patch.dict(
            web_app.os.environ,
            {
                "OPENAI_API_KEY": "test-existing-key",
                "OPENAI_USAGE_API_KEY": "",
                "OPENAI_ADMIN_API_KEY": "",
                "OPENAI_USAGE_DASHBOARD_ENABLED": "1",
            },
            clear=False,
        ), patch.object(
            web_app,
            "fetch_openai_usage_pages",
            side_effect=RuntimeError("OpenAI Usage API 403: Missing scopes: api.usage.read"),
        ):
            dashboard = web_app.build_agent_usage_dashboard(log_path)

        summary = dashboard["summary"]
        self.assertEqual("local_log", summary["usageSource"])
        self.assertEqual("permission_denied", summary["externalUsageStatus"])
        self.assertIn("api.usage.read", summary["externalUsageMessage"])
        self.assertIn("로컬 LLM 호출 로그", summary["costBasis"])

    def test_agent_usage_dashboard_marks_openai_usage_not_configured(self):
        log_path = self.root / "llm_calls.jsonl"
        log_path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-05-02T10:00:00",
                    "event": "request_success",
                    "schema_name": "overview_chapter",
                    "model": "gpt-5.4",
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                }
            ),
            encoding="utf-8",
        )

        with patch.dict(
            web_app.os.environ,
            {
                "OPENAI_USAGE_API_KEY": "",
                "OPENAI_ADMIN_API_KEY": "",
                "OPENAI_API_KEY": "",
                "OPENAI_USAGE_DASHBOARD_ENABLED": "1",
            },
            clear=False,
        ):
            dashboard = web_app.build_agent_usage_dashboard(log_path)

        summary = dashboard["summary"]
        self.assertEqual("local_log", summary["usageSource"])
        self.assertEqual("not_configured", summary["externalUsageStatus"])
        self.assertEqual(1, summary["calls"])
        self.assertEqual(15, summary["totalTokens"])


if __name__ == "__main__":
    unittest.main()
