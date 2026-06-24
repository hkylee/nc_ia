import unittest
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import src.web_app as web_app
from src.policy_inspector import InspectionFinding, InspectionReport
from src.llm_client import LLMClient
from src.web_app import (
    RevisionInspectorGateError,
    apply_revision_plan,
    client_for_revision_request,
    continue_pending_revision_save,
    constrain_revision_plan_scope,
    revision_delta_acceptable,
    revision_document_context,
    revision_instructions,
    revision_inspection_review_payload,
    revision_prompt,
    revision_schema,
    revision_save_mode_from_payload,
    revision_selection_from_payload,
)


class SelectedRevisionTest(unittest.TestCase):
    def test_selection_payload_is_normalized_for_revision_prompt(self):
        selection = revision_selection_from_payload(
            {
                "selection": {
                    "text": "인증 번호 유효시간 3분",
                    "html": "<td>인증 번호 유효시간 3분</td>",
                    "blockText": "인증 정책 인증 번호 유효시간 3분",
                    "blockHtml": "<tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr>",
                    "sectionTitle": "정책 상세",
                    "headingPath": ["6. 정책 정의", "나. 정책 상세"],
                }
            }
        )

        prompt = revision_prompt("<html><body><h2>6. 정책 정의</h2><table><tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr></table></body></html>", "유효시간을 5분으로 바꿔줘", selection)

        self.assertEqual("6. 정책 정의 > 나. 정책 상세", selection["heading_path"])
        self.assertIn("선택 영역 정보", prompt)
        self.assertIn("인증 번호 유효시간 3분", prompt)
        self.assertIn("선택 블록 HTML", prompt)

    def test_selection_revision_prompt_uses_selected_block_not_full_section(self):
        unrelated_rows = "\n".join(
            f"<tr><td>다른 정책 항목 {index}</td><td>{'무관한 설명' * 40}</td></tr>"
            for index in range(80)
        )
        old_html = f"""
<html><body>
<h2>6. 정책 정의</h2>
<h3>나. 정책 상세</h3>
<table><tbody>
<tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr>
{unrelated_rows}
</tbody></table>
</body></html>
"""
        selection = revision_selection_from_payload(
            {
                "selection": {
                    "text": "인증 번호 유효시간 3분",
                    "blockText": "인증 정책 인증 번호 유효시간 3분",
                    "blockHtml": "<tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr>",
                    "sectionTitle": "정책 상세",
                    "headingPath": ["6. 정책 정의", "나. 정책 상세"],
                }
            }
        )

        context = revision_document_context(old_html, "선택 문장을 5분으로 수정해줘", selection)
        prompt = revision_prompt(old_html, "선택 문장을 5분으로 수정해줘", selection)

        self.assertEqual(["policies"], context["summary"]["selected_sections"])
        self.assertIn("인증 번호 유효시간 3분", prompt)
        self.assertNotIn("다른 정책 항목 79", prompt)
        self.assertLess(len(prompt), 6000)

    def test_selection_revision_plan_is_limited_to_minimal_patch(self):
        plan = {
            "summary": "여러 항목 수정",
            "replacements": [{"find": f"기존 {index}", "replace": f"변경 {index}"} for index in range(8)],
            "append_items": [f"추가 {index}" for index in range(6)],
        }

        constrained = constrain_revision_plan_scope(plan, "선택 영역만 수정해줘", {"text": "선택"})

        self.assertEqual(3, len(constrained["replacements"]))
        self.assertEqual(2, len(constrained["append_items"]))
        self.assertIn("수정 범위 과다", constrained["summary"])

    def test_qa_revision_plan_can_keep_selected_action_items(self):
        plan = {
            "summary": "선택 항목 보완",
            "replacements": [{"find": f"기존 {index}", "replace": f"변경 {index}"} for index in range(12)],
            "append_items": [f"추가 {index}" for index in range(12)],
        }

        constrained = constrain_revision_plan_scope(plan, "개발/QA 검수 결과 중 사용자가 선택한 보완 요청만 반영해줘.", {})

        self.assertEqual(12, len(constrained["replacements"]))
        self.assertEqual(12, len(constrained["append_items"]))

    def test_revision_schema_limits_general_revision_output(self):
        schema = revision_schema("예외 처리 기준을 보완해줘", {})
        properties = schema["properties"]

        self.assertEqual(6, properties["replacements"]["maxItems"])
        self.assertEqual(6, properties["append_items"]["maxItems"])
        self.assertEqual(0, properties["target_replacement_html"]["maxLength"])
        self.assertLessEqual(properties["replacements"]["items"]["properties"]["replace"]["maxLength"], 800)

    def test_general_revision_prompt_uses_bounded_target_section_excerpt(self):
        long_policy_rows = "\n".join(
            f"<tr><td>정책 항목 {index}</td><td>{'예외 기준 설명 ' * 80}</td></tr>"
            for index in range(120)
        )
        old_html = f"""
<html><body>
<h2>1. 개요</h2><p>개요</p>
<h2>6. 정책 정의</h2><table><tbody>{long_policy_rows}</tbody></table>
</body></html>
"""

        context = revision_document_context(old_html, "예외 처리 기준을 보완해줘", {})
        prompt = revision_prompt(old_html, "예외 처리 기준을 보완해줘", {})

        self.assertEqual(["policies"], context["summary"]["selected_sections"])
        self.assertLessEqual(len(context["selected_text"]), 3520)
        self.assertLessEqual(len(context["selected_html"]), 8020)
        self.assertNotIn("정책 항목 119", prompt)

    def test_revision_schema_keeps_selected_revision_small_but_allows_target_html(self):
        schema = revision_schema("선택 영역을 수정해줘", {"text": "선택 문장"})
        properties = schema["properties"]

        self.assertEqual(3, properties["replacements"]["maxItems"])
        self.assertEqual(2, properties["append_items"]["maxItems"])
        self.assertGreater(properties["target_replacement_html"]["maxLength"], 1000)

    def test_revision_schema_allows_qa_selected_action_budget(self):
        schema = revision_schema("개발/QA 검수 결과 중 선택된 보완 항목만 반영해줘.", {})
        properties = schema["properties"]

        self.assertEqual(20, properties["replacements"]["maxItems"])
        self.assertEqual(20, properties["append_items"]["maxItems"])

    def test_revision_schema_allows_broader_quality_revision_budget(self):
        schema = revision_schema("전체 구조와 요구사항 누락 여부를 점검하고 보완해줘.", {})
        properties = schema["properties"]

        self.assertEqual(10, properties["replacements"]["maxItems"])
        self.assertEqual(10, properties["append_items"]["maxItems"])
        self.assertEqual(8, properties["target_sections"]["maxItems"])
        self.assertEqual(0, properties["target_replacement_html"]["maxLength"])

    def test_revision_instructions_include_output_budget(self):
        instructions = revision_instructions("추천", "simple", instruction="예외 처리 기준을 보완해줘", selection={})

        self.assertIn("replacements 최대 6개", instructions)
        self.assertIn("append_items 최대 6개", instructions)
        self.assertIn("target_replacement_html을 빈 문자열", instructions)
        self.assertIn("표 전체를 통째로 반환하지 않는다", instructions)

    def test_revision_request_uses_low_reasoning_for_first_scoped_pass(self):
        client = LLMClient(writer_mode="llm", model="gpt-5.4", reasoning_effort="medium", api_key="test-key")

        routed = client_for_revision_request(client, "예외 처리 기준을 보완해줘", {})

        self.assertEqual("low", routed.reasoning_effort)
        self.assertEqual("gpt-5.4", routed.model)

    def test_revision_request_keeps_medium_for_broad_quality_revision(self):
        client = LLMClient(writer_mode="llm", model="gpt-5.4", reasoning_effort="medium", api_key="test-key")

        routed = client_for_revision_request(client, "전체 구조와 요구사항 누락 여부를 점검하고 보완해줘.", {})

        self.assertEqual("medium", routed.reasoning_effort)

    def test_revision_request_keeps_qa_reasoning_budget(self):
        client = LLMClient(writer_mode="llm", model="gpt-5.4", reasoning_effort="medium", api_key="test-key")

        routed = client_for_revision_request(client, "개발/QA 검수 결과 중 선택된 보완 항목만 반영해줘.", {})

        self.assertEqual("medium", routed.reasoning_effort)

    def test_apply_revision_plan_prefers_selected_block_replacement(self):
        old_html = """
<html><body>
<h2>6. 정책 정의</h2>
<table><tbody><tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr></tbody></table>
</body></html>
"""
        selection = {
            "text": "인증 번호 유효시간 3분",
            "html": "<td>인증 번호 유효시간 3분</td>",
            "block_text": "인증 정책 인증 번호 유효시간 3분",
            "block_html": "<tr><td>인증 정책</td><td>인증 번호 유효시간 3분</td></tr>",
            "section_title": "정책 상세",
            "heading_path": "6. 정책 정의 > 나. 정책 상세",
        }
        plan = {
            "target_replacement_html": "<tr><td>인증 정책</td><td>인증 번호 유효시간 5분</td></tr>",
            "replacements": [],
        }

        revised, applied = apply_revision_plan(old_html, plan, "유효시간을 5분으로 바꿔줘", selection)

        self.assertEqual(1, applied)
        self.assertIn("인증 번호 유효시간 5분", revised)
        self.assertNotIn("인증 번호 유효시간 3분", revised)

    def test_apply_revision_plan_infers_simple_selected_text_change_when_plan_is_empty(self):
        old_html = """
<html><body>
<h1>추천 정책서</h1>
<table><tbody><tr><th>문서 구분</th><td>간소화 버전</td></tr></tbody></table>
</body></html>
"""
        selection = {
            "text": "간소화 버전",
            "html": "<td>간소화 버전</td>",
            "block_text": "문서 구분 간소화 버전",
            "block_html": "<tr><th>문서 구분</th><td>간소화 버전</td></tr>",
            "section_title": "표지",
            "heading_path": "표지",
        }
        plan = {
            "target_replacement_html": "",
            "replacements": [],
        }

        revised, applied = apply_revision_plan(old_html, plan, "간소화버전 으로 변경해줘", selection)

        self.assertEqual(1, applied)
        self.assertIn("<td>간소화버전</td>", revised)
        self.assertNotIn("간소화 버전", revised)

    def test_revision_delta_accepts_preexisting_inspector_failure(self):
        baseline = self.report(
            76,
            [
                self.finding(
                    "error",
                    "정책 구체성",
                    "정책 상세 선언 누락",
                    "기존 문서에 정책 상세 선언 누락이 있습니다.",
                )
            ],
        )
        revised = self.report(
            80,
            [
                self.finding(
                    "error",
                    "정책 구체성",
                    "정책 상세 선언 누락",
                    "수정 후에도 기존 정책 상세 선언 누락이 남아 있습니다.",
                )
            ],
        )

        self.assertTrue(revision_delta_acceptable(baseline, revised))

    def test_revision_delta_rejects_new_blocking_finding(self):
        baseline = self.report(86, [])
        revised = self.report(
            88,
            [
                self.finding(
                    "error",
                    "연결성",
                    "프로세스 관련 정책 누락",
                    "수정본에서 새 연결성 오류가 발생했습니다.",
                )
            ],
        )

        self.assertFalse(revision_delta_acceptable(baseline, revised))

    def test_revision_inspection_review_payload_contains_save_decision_context(self):
        baseline = self.report(82, [])
        revised = self.report(
            78,
            [
                self.finding(
                    "warning",
                    "정책 구체성",
                    "미정 항목 정리 필요",
                    "사용자 수정 요청 이후에도 결정 필요 항목이 남아 있습니다.",
                )
            ],
        )

        payload = revision_inspection_review_payload(
            old_path=Path("NC_상품상세담기_정책서_간소화_v0.3.html"),
            new_path=Path("NC_상품상세담기_정책서_간소화_v0.4.html"),
            baseline_report=baseline,
            revised_report=revised,
        )

        self.assertEqual("revision_inspection_gate", payload["review_type"])
        self.assertEqual("수정본 검수", payload["stage_label"])
        self.assertEqual(78, payload["score"])
        self.assertIn("저장 여부", payload["message"])
        self.assertTrue(any("기존 점수 82점" in item for item in payload["preview"]["items"]))

    def test_selected_revision_uses_current_version_save_mode_for_small_edits(self):
        selection = revision_selection_from_payload(
            {
                "selection": {
                    "text": "간소화 버전",
                    "blockText": "문서 구분 간소화 버전",
                    "sectionTitle": "표지",
                }
            }
        )

        save_mode = revision_save_mode_from_payload(
            {"saveMode": "current_version", "instruction": "선택 문구를 간소화버전으로 바꿔줘"},
            selection,
        )

        self.assertEqual("current_version", save_mode)

    def test_selected_revision_keeps_new_version_save_mode_for_broad_requests(self):
        selection = revision_selection_from_payload(
            {
                "selection": {
                    "text": "요구사항 반영",
                    "blockText": "요구사항 반영 여부",
                    "sectionTitle": "최종 점검",
                }
            }
        )

        broad_save_mode = revision_save_mode_from_payload(
            {"saveMode": "current_version", "instruction": "문서 전체 요구사항 반영 여부를 점검하고 보완해줘"},
            selection,
        )
        no_selection_save_mode = revision_save_mode_from_payload(
            {"saveMode": "current_version", "instruction": "선택 문구를 바꿔줘"},
            {},
        )

        self.assertEqual("new_version", broad_save_mode)
        self.assertEqual("new_version", no_selection_save_mode)

    def test_revision_inspection_review_payload_describes_current_version_save(self):
        baseline = self.report(82, [])
        revised = self.report(78, [])

        payload = revision_inspection_review_payload(
            old_path=Path("NC_상품상세담기_정책서_간소화_v0.12.html"),
            new_path=Path("NC_상품상세담기_정책서_간소화_v0.12.html"),
            baseline_report=baseline,
            revised_report=revised,
            save_mode="current_version",
        )

        self.assertTrue(any("현재 버전에 누적 반영" in item for item in payload["preview"]["items"]))

    def test_failed_revision_candidate_can_be_saved_after_user_continue(self):
        original_output_root = web_app.OUTPUT_ROOT
        original_candidate_dir = web_app.REVISION_CANDIDATE_DIR
        original_jobs = dict(web_app.JOBS)
        job_id = "job-revision-continue"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                output_root = root / "output"
                output_root.mkdir()
                candidate_dir = root / "reports" / "cache" / "revision_candidates"
                web_app.OUTPUT_ROOT = output_root
                web_app.REVISION_CANDIDATE_DIR = candidate_dir
                web_app.JOBS.clear()
                old_path = output_root / "NC_상품상세담기_정책서_간소화_v0.3.html"
                new_path = output_root / "NC_상품상세담기_정책서_간소화_v0.4.html"
                old_path.write_text(
                    """
<html><head><title>NC 상품상세담기 v0.3</title></head><body>
<h2>0. 문서 히스토리</h2><table><tbody>
<tr><td>v0.3</td><td>기존 작성</td><td>2026-05-12</td><td>Codex</td></tr>
</tbody></table>
<p>미정 항목이 남아 있다.</p>
</body></html>
""",
                    encoding="utf-8",
                )
                revised_html = old_path.read_text(encoding="utf-8").replace(
                    "미정 항목이 남아 있다.",
                    "결정 필요 항목은 결정 주체, 결정 사유, 결정 기한을 함께 기록한다.",
                )
                pending = web_app.persist_revision_candidate(
                    job_id,
                    RevisionInspectorGateError(
                        "수정본이 Inspector 기준을 통과하지 못했습니다. 점수 43점 / 기준 85점",
                        old_path=old_path,
                        new_path=new_path,
                        revised_html=revised_html,
                        author="Codex Test",
                        change_summary="미정 항목 정리 기준 보완",
                        score=43,
                        threshold=85,
                    ),
                )
                web_app.JOBS[job_id] = {
                    "id": job_id,
                    "kind": "revision",
                    "status": "error",
                    "topic": "상품상세담기",
                    "templateType": "simple",
                    "currentStageKey": "02",
                    "message": "검수 기준 미통과",
                    "activity": [],
                    "_startedMono": None,
                    "elapsedMs": 0,
                    "_pendingRevisionSave": pending,
                    "pendingRevisionSave": web_app.pending_revision_save_public(pending),
                    "stages": [
                        {"key": "01", "label": "수정 Agent", "status": "done"},
                        {"key": "02", "label": "수정본 검수", "status": "error"},
                        {"key": "03", "label": "문서 히스토리 업데이트", "status": "pending"},
                        {"key": "04", "label": "새 버전 저장", "status": "pending"},
                    ],
                }

                snapshot = continue_pending_revision_save(job_id)

                self.assertEqual("completed", snapshot["status"])
                self.assertNotIn("pendingRevisionSave", snapshot)
                self.assertTrue(new_path.exists())
                self.assertIn("결정 필요 항목은 결정 주체", new_path.read_text(encoding="utf-8"))
                self.assertIn("v0.4", new_path.read_text(encoding="utf-8"))
                self.assertFalse(Path(pending["candidatePath"]).exists())
        finally:
            web_app.OUTPUT_ROOT = original_output_root
            web_app.REVISION_CANDIDATE_DIR = original_candidate_dir
            web_app.JOBS.clear()
            web_app.JOBS.update(original_jobs)

    def report(self, score, findings):
        return InspectionReport(
            status="fail" if any(f.severity == "error" for f in findings) else "warn",
            score=score,
            scope="full",
            checked_at="2026-05-12T00:00:00",
            summary="test",
            findings=findings,
            metrics={},
        )

    def finding(self, severity, category, title, detail):
        return InspectionFinding(
            severity=severity,
            category=category,
            title=title,
            detail=detail,
            recommendation="보완",
        )


if __name__ == "__main__":
    unittest.main()
