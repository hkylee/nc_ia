import tempfile
import unittest
import zipfile
from pathlib import Path

from src.pi_agent import (
    build_pi_agent_knowledge,
    evaluate_pi_document_quality,
    normalize_pi_check_document,
    pi_check_analysis_text,
    pi_checklist_with_methods,
    pi_context_for_stage,
)
from src.policy_references import extract_reference_text, project_source_groups


class PIAgentTest(unittest.TestCase):
    def test_pi_agent_knowledge_has_independent_contract(self):
        knowledge = build_pi_agent_knowledge()

        self.assertEqual(knowledge["agent"], "PI Agent")
        self.assertEqual(len(knowledge["principles"]), 7)
        self.assertEqual(len(knowledge["checklist"]), 50)
        self.assertEqual(len(knowledge["inspection_methods"]), 5)
        self.assertEqual(len(knowledge["gatekeeper_dimensions"]), 5)
        self.assertEqual(len(knowledge["anti_patterns"]), 5)
        self.assertTrue(any("템플릿" in rule for rule in knowledge["scope_boundary"]))
        self.assertTrue(all("inspection_method" in item for item in pi_checklist_with_methods()))
        self.assertTrue(any(item.get("section_name") == "KPI 연계 설계" for item in knowledge["checklist"]))

    def test_pi_context_is_stage_specific(self):
        context = pi_context_for_stage("process")

        self.assertEqual(context["agent"], "PI Agent")
        self.assertIn("process", context["stage"])
        self.assertTrue(any("중복" in item or "단계" in item for item in context["focus"]))
        self.assertTrue(context["anti_patterns"])

    def test_pi_evaluator_detects_quality_signals_and_antipatterns(self):
        document = """
        프로세스는 중복 입력과 중복 인증을 제거하고 앱/웹 셀프 처리로 자동화한다.
        실패, 오류, 중단, 취소, 중복 요청, 권한 없음, 데이터 없음 상황은 재시도와 상담 전환 기준을 둔다.
        BSS와 FO 책임 경계를 정하고 기준 정보는 단일 원천 마스터로 관리한다.
        KPI는 완료율, 처리 시간, 오류율로 본다. QA 검증과 운영 검증을 수행한다.
        AI 결과는 입력, 출력, 신뢰도, 운영자 확인, Fallback 기준을 함께 둔다.
        """

        result = evaluate_pi_document_quality(document, topic="AI 검색")

        self.assertGreaterEqual(result["yes_count"], 5)
        self.assertEqual(result["anti_pattern_count"], 0)
        self.assertIn("inspectionMethod", result["checks"][0])
        self.assertIn("statusReason", result["checks"][0])
        self.assertEqual(len(result["checks"]), 50)
        self.assertEqual(len(result["legacy_checks"]), 9)

    def test_pi_check_normalizes_html_before_analysis(self):
        document = """
        <html><body>
          <h1>AI 검색 정책서</h1>
          <p>중복 입력과 중복 인증을 제거하고 셀프 처리로 자동화한다.</p>
          <table>
            <tr><th>KPI</th><th>기준</th></tr>
            <tr><td>완료율</td><td>처리 시간과 오류율을 함께 본다.</td></tr>
          </table>
        </body></html>
        """

        normalized = normalize_pi_check_document(document, file_name="sample.html")
        analysis_text = pi_check_analysis_text(normalized)

        self.assertEqual(normalized["kind"], "html")
        self.assertEqual(normalized["metrics"]["heading_count"], 1)
        self.assertEqual(normalized["metrics"]["table_count"], 1)
        self.assertIn("AI 검색 정책서", analysis_text)
        self.assertIn("완료율", analysis_text)

    def test_pi_check_normalizes_pptx_and_bpmn_uploads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pptx = Path(tmpdir) / "sample.pptx"
            slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                   xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>중복 입력 제거</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
            </p:sld>
            """
            with zipfile.ZipFile(pptx, "w") as archive:
                archive.writestr("ppt/slides/slide1.xml", slide_xml)

            normalized_pptx = normalize_pi_check_document(pptx.read_bytes(), file_name="sample.pptx")
            bpmn = '<bpmn:task xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Task_1" name="상담 전환 기준 확인"/>'
            normalized_bpmn = normalize_pi_check_document(bpmn.encode("utf-8"), file_name="flow.bpmn")

        self.assertEqual(normalized_pptx["kind"], "pptx")
        self.assertIn("중복 입력 제거", pi_check_analysis_text(normalized_pptx))
        self.assertEqual(normalized_bpmn["kind"], "bpmn")
        self.assertIn("상담 전환 기준 확인", pi_check_analysis_text(normalized_bpmn))

    def test_project_sources_include_pi_guide_as_guideline(self):
        groups = [(root.name, category) for root, category in project_source_groups()]

        self.assertIn(("PI guide", "guideline"), groups)

    def test_docx_reference_text_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            docx = Path(tmpdir) / "sample.docx"
            document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>Process Innovation Playbook</w:t></w:r></w:p>
                <w:p><w:r><w:t>단계 수를 줄이고 예외를 본문에 포함한다.</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            text = extract_reference_text(docx, ())

        self.assertIn("Process Innovation Playbook", text)
        self.assertIn("예외를 본문", text)


if __name__ == "__main__":
    unittest.main()
