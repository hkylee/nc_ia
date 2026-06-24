import unittest

from src.policy_agent import inspection_feedback
from src.policy_inspector import (
    InspectionFinding,
    finding_actionability_issues,
    llm_findings,
    llm_json_inspection_instructions,
    llm_json_inspection_prompt,
    llm_inspection_instructions,
    stage_inspector_profile,
)


class InspectorFeedbackDetailTest(unittest.TestCase):
    def test_llm_findings_preserve_patch_guidance_fields(self):
        findings = llm_findings(
            {
                "findings": [
                    {
                        "finding_id": "F-001",
                        "tier": "P2",
                        "severity": "warn",
                        "category": "정합성",
                        "is_quality_gate": True,
                        "title": "프로세스 책임 경계 모호",
                        "detail": "AI 엔진이 최종 분기를 확정하는 것처럼 보인다.",
                        "recommendation": "프로세스 설명의 최종 분기 주체를 채널 업무 시스템으로 바꾼다.",
                        "target_path": "current_chapter.processes[2].description",
                        "fix_owner": "current_chapter",
                        "upstream_chapter": "",
                        "root_cause": "AI 후보 생성과 채널 노출 결정 책임이 한 문장에 섞였다.",
                        "required_change": "description에서 최종 확정 주체를 채널 업무 시스템으로 수정한다.",
                        "patch_hint": "AI 엔진은 후보 생성, 채널 업무 시스템은 노출 경로 확정으로 분리한다.",
                        "acceptance_check": "AI가 최종 확정한다는 표현이 없어야 한다.",
                        "keep_constraints": "프로세스 ID와 usecase_id는 유지한다.",
                        "do_not_change": "actors와 usecases는 수정하지 않는다.",
                    }
                ]
            }
        )

        self.assertEqual("current_chapter.processes[2].description", findings[0].target_path)
        self.assertIn("채널 업무 시스템", findings[0].required_change)
        self.assertIn("actors", findings[0].do_not_change)

    def test_inspection_feedback_passes_detailed_patch_guidance_to_writer(self):
        finding = InspectionFinding(
            "warn",
            "정합성",
            "프로세스 책임 경계 모호",
            "AI 엔진이 최종 분기를 확정하는 것처럼 보인다.",
            "프로세스 설명의 최종 분기 주체를 채널 업무 시스템으로 바꾼다.",
            tier="P2",
            target_path="current_chapter.processes[2].description",
            root_cause="AI 후보 생성과 채널 노출 결정 책임이 한 문장에 섞였다.",
            required_change="description에서 최종 확정 주체를 채널 업무 시스템으로 수정한다.",
            patch_hint="AI 엔진은 후보 생성, 채널 업무 시스템은 노출 경로 확정으로 분리한다.",
            acceptance_check="AI가 최종 확정한다는 표현이 없어야 한다.",
            keep_constraints="프로세스 ID와 usecase_id는 유지한다.",
            do_not_change="actors와 usecases는 수정하지 않는다.",
        )
        report = type("Report", (), {"findings": [finding], "score": 82, "scope": "07_process"})()

        feedback = inspection_feedback(report, 90, attempt=1, chapter_key="process")

        self.assertEqual("current_chapter.processes[2].description", feedback[0]["target_path"])
        self.assertIn("필수수정", feedback[0]["recommendation"])
        self.assertEqual("AI가 최종 확정한다는 표현이 없어야 한다.", feedback[0]["acceptance_check"])
        self.assertEqual("actors와 usecases는 수정하지 않는다.", feedback[0]["do_not_change"])

    def test_json_inspector_prompt_allows_explicit_upstream_backtrack_exception(self):
        instructions = llm_json_inspection_instructions("AI 검색", "간소화", "07_process")
        prompt = llm_json_inspection_prompt(
            spec={},
            deterministic_findings=[],
            metrics={},
            template_type="간소화",
            scope="07_process",
            topic="AI 검색",
            chapter_key="process",
        )

        self.assertIn("현재 장에서 수정 가능한 finding을 우선", instructions)
        self.assertIn("fix_owner=upstream_chapter 또는 cross_chapter", instructions)
        self.assertIn("이전 장의 승인 계약 자체가 누락·오류", prompt)
        self.assertIn("upstream finding도 현재 장에서 재정렬해야 할 기준", prompt)

    def test_stage_inspector_profile_is_chapter_specific(self):
        state_profile = stage_inspector_profile("06_state")
        policy_profile = stage_inspector_profile("09_policies")

        self.assertEqual("State Inspector", state_profile["role"])
        self.assertEqual("Policy Inspector", policy_profile["role"])
        self.assertIn("전이 이벤트", " ".join(state_profile["must_verify"]))
        self.assertIn("정책 상세", " ".join(policy_profile["must_verify"]))

    def test_llm_instructions_include_stage_inspector_profile(self):
        instructions = llm_inspection_instructions("AI 검색", "간소화", "08_functions")

        self.assertIn("Stage Inspector 전문 프로파일", instructions)
        self.assertIn("Function Inspector", instructions)
        self.assertIn("프로세스명을 그대로 복사", instructions)

    def test_actionability_gate_accepts_precise_finding(self):
        finding = InspectionFinding(
            "warn",
            "정합성",
            "프로세스 책임 경계 모호",
            "AI 엔진이 최종 분기를 확정하는 것처럼 보인다.",
            "프로세스 설명의 최종 분기 주체를 채널 업무 시스템으로 바꾼다.",
            target_path="current_chapter.processes[2].description",
            root_cause="AI 후보 생성과 채널 노출 결정 책임이 한 문장에 섞였다.",
            required_change="description에서 최종 확정 주체를 채널 업무 시스템으로 수정한다.",
            patch_hint="AI 엔진은 후보 생성, 채널 업무 시스템은 노출 경로 확정으로 분리한다.",
            acceptance_check="AI가 최종 확정한다는 표현이 없어야 한다.",
        )

        self.assertEqual([], finding_actionability_issues(finding))

    def test_actionability_gate_marks_vague_finding_for_writer_guard(self):
        finding = InspectionFinding(
            "warn",
            "정책",
            "정책 구체성 부족",
            "정책이 추상적이다.",
            "구체화 필요",
            tier="P2",
        )
        report = type("Report", (), {"findings": [finding], "score": 70, "scope": "09_policies"})()

        feedback = inspection_feedback(report, 90, attempt=1, chapter_key="policies")

        self.assertIn("target_path 누락", finding_actionability_issues(finding))
        self.assertEqual("needs_clarification", feedback[0]["feedback_quality"])
        self.assertEqual("scoped_full_revision", feedback[0]["remediation_mode"])
        self.assertIn("지정된 보완 모드의 범위 안에서만", feedback[0]["recommendation"])
        self.assertIn("원인 누락", feedback[0]["actionability_issues"])

    def test_inspection_feedback_routes_near_miss_to_patch(self):
        finding = InspectionFinding(
            "warn",
            "정합성",
            "정책 항목 연결 부족",
            "정책 항목 1건의 설명이 기능 동작값으로 읽히지 않는다.",
            "해당 정책 항목 설명만 동작값 기준으로 수정한다.",
            tier="P2",
            target_path="current_chapter.policy_details[0].content",
            root_cause="정책 항목이 일반 설명으로 작성되어 개발 판단값이 없다.",
            required_change="content에 허용 횟수, 제한 조건, 고지 기준 중 필요한 값을 명시한다.",
            patch_hint="현재 항목만 고객 고지 기준과 제한 조건 중심으로 바꾼다.",
            acceptance_check="해당 정책 항목이 기능 동작값으로 읽혀야 한다.",
        )
        report = type("Report", (), {"findings": [finding], "score": 82, "scope": "09_policies"})()

        feedback = inspection_feedback(report, 85, attempt=1, chapter_key="policies")

        self.assertEqual("patch", feedback[0]["remediation_mode"])
        self.assertIn("patch-only", feedback[0]["revision_policy"])

    def test_structure_blocker_uses_scoped_revision_even_with_high_score(self):
        finding = InspectionFinding(
            "warn",
            "structure",
            "프로세스 계층 구조 결함",
            "프로세스가 기능명 나열로 작성되어 유즈케이스 완료 절차로 읽히지 않는다.",
            "프로세스 섹션을 업무 절차 기준으로 재정렬한다.",
            tier="P1",
            target_path="current_chapter.processes",
            root_cause="프로세스와 기능 계층이 섞였다.",
            required_change="processes 배열의 설명과 순서를 유즈케이스 완료 절차로 재구성한다.",
            patch_hint="시작, 조건 판단, 요청 접수, 처리 반영, 결과 안내 순서로 묶는다.",
            acceptance_check="프로세스명이 기능 처리명처럼 보이지 않아야 한다.",
        )
        report = type("Report", (), {"findings": [finding], "score": 88, "scope": "07_process"})()

        feedback = inspection_feedback(report, 85, attempt=1, chapter_key="process")

        self.assertEqual("scoped_section_revision", feedback[0]["remediation_mode"])

    def test_inspector_instructions_require_patch_actionability(self):
        instructions = llm_json_inspection_instructions("AI 검색", "간소화", "09_policies")

        self.assertIn("target_path, root_cause, required_change, patch_hint, acceptance_check", instructions)
        self.assertIn("변경", instructions)
        self.assertIn("추가", instructions)
        self.assertIn("삭제", instructions)


if __name__ == "__main__":
    unittest.main()
