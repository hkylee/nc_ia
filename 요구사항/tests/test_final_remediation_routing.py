import unittest
from pathlib import Path

from src.policy_agent import (
    PolicyContext,
    apply_final_revision_patch,
    build_final_remediation_runtime,
    final_finding_chapter,
    final_revision_spec_pack,
    final_remediation_feedback_by_chapter,
    prioritize_final_remediation_feedback,
    split_final_remediation_for_revision,
)
from src.policy_inspector import InspectionFinding


class FinalRemediationRoutingTest(unittest.TestCase):
    def test_final_finding_routes_policy_privacy_to_policies_agent(self):
        finding = InspectionFinding(
            "warn",
            "개인정보·이력 정책",
            "인증·처리 이력의 저장·보관·파기 기준이 약함",
            "정책 상세에 개인정보 기준이 부족하다.",
            "정책 상세에 보관 기간과 파기 기준을 추가한다.",
        )

        self.assertEqual("policies", final_finding_chapter(finding))

    def test_final_finding_routes_state_transition_to_state_agent(self):
        finding = InspectionFinding(
            "error",
            "상태 정합성",
            "상태 전이표가 상태명이 아닌 유즈케이스명을 현재·다음 상태로 사용함",
            "상태 전이 기준에 문제가 있다.",
            "상태 전이표를 상태명 기준으로 수정한다.",
        )

        self.assertEqual("state", final_finding_chapter(finding))

    def test_final_finding_routes_procedural_y_usecase_to_usecases_agent(self):
        finding = InspectionFinding(
            "error",
            "템플릿 가이드",
            "절차형 유즈케이스 분리",
            "process_target=Y 유즈케이스에 절차 단계가 포함되어 있습니다: 회원가입 · 회원탈퇴 요청 및 결과 확인",
            "해당 항목은 상위 업무 목적 유즈케이스로 묶고, 세부 행위는 프로세스 장으로 내리세요.",
        )

        self.assertEqual("usecases", final_finding_chapter(finding))

    def test_final_feedback_is_grouped_by_chapter_agent(self):
        report = type(
            "Report",
            (),
            {
                "score": 72,
                "scope": "full",
                "findings": [
                    InspectionFinding("error", "상태 정합성", "상태 전이 오류", "상태 오류", "상태 수정"),
                    InspectionFinding("warn", "최종 점검", "최종 점검 기준 부족", "점검 기준 부족", "최종 점검 보완"),
                ],
            },
        )()

        grouped = final_remediation_feedback_by_chapter(report, 85, 1)

        self.assertIn("state", grouped)
        self.assertIn("final_check", grouped)
        self.assertTrue(grouped["state"][0]["recommendation"])

    def test_final_remediation_prioritizes_upstream_usecase_before_downstream_chapters(self):
        grouped = prioritize_final_remediation_feedback(
            {
                "usecases": [{"priority_tier": "P1", "title": "절차형 Y 유즈케이스"}],
                "process": [{"priority_tier": "P1", "title": "프로세스 연결 보완"}],
                "policies": [{"priority_tier": "P1", "title": "정책 연결 보완"}],
            }
        )

        self.assertEqual(["usecases"], list(grouped))

    def test_final_revision_split_keeps_root_p1_for_chapter_agent(self):
        revision, chapter = split_final_remediation_for_revision(
            {
                "usecases": [{"priority_tier": "P1", "title": "절차형 Y 유즈케이스"}],
                "policies": [{"priority_tier": "P2", "title": "정책 항목 보강"}],
            }
        )

        self.assertEqual({}, revision)
        self.assertEqual(["usecases"], list(chapter))

    def test_final_revision_split_routes_non_structural_policy_feedback_to_revision_agent(self):
        revision, chapter = split_final_remediation_for_revision(
            {
                "policies": [
                    {
                        "priority_tier": "P2",
                        "remediation_mode": "patch",
                        "title": "정책 항목 판단축 보강",
                        "target_path": "policy_details[PI-MBR-001-01].content",
                    }
                ]
            }
        )

        self.assertIn("policies", revision)
        self.assertEqual({}, chapter)

    def test_final_revision_split_routes_broad_p2_policy_feedback_to_revision_agent(self):
        revision, chapter = split_final_remediation_for_revision(
            {
                "policies": [
                    {
                        "priority_tier": "P2",
                        "remediation_mode": "scoped_full_revision",
                        "title": "정책 상세 판단축 보강",
                        "detail": "정책 항목이 일반론이라 허용·제한·이력 기준을 보강해야 한다.",
                    }
                ]
            }
        )

        self.assertIn("policies", revision)
        self.assertEqual({}, chapter)

    def test_final_revision_split_keeps_missing_policy_rows_for_chapter_agent(self):
        revision, chapter = split_final_remediation_for_revision(
            {
                "policies": [
                    {
                        "priority_tier": "P1",
                        "remediation_mode": "scoped_full_revision",
                        "title": "정책 그룹 누락",
                        "detail": "필수 정책 그룹 추가와 정책 상세 추가가 필요하다.",
                    }
                ]
            }
        )

        self.assertEqual({}, revision)
        self.assertIn("policies", chapter)

    def test_final_revision_split_routes_broad_revision_to_chapter_agent(self):
        revision, chapter = split_final_remediation_for_revision(
            {
                "functions": [
                    {
                        "priority_tier": "P1",
                        "remediation_mode": "scoped_full_revision",
                        "title": "기능 계층 구조 재정렬",
                    }
                ]
            }
        )

        self.assertEqual({}, revision)
        self.assertIn("functions", chapter)

    def test_apply_final_revision_patch_updates_existing_policy_detail_only(self):
        spec = {
            "policy_details": [
                {
                    "id": "PI-MBR-001-01",
                    "policy_id": "PG-MBR-001",
                    "name": "이력 저장 기준",
                    "content": "이력을 저장한다.",
                }
            ]
        }
        payload = {
            "updates": [
                {
                    "collection": "policy_details",
                    "id": "PI-MBR-001-01",
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "name": "",
                    "description": "",
                    "content": "회원 가입·탈퇴 요청, BSS 판정 결과, 고객 고지 결과를 요청일시와 처리 주체 기준으로 저장한다.",
                    "actor": "",
                    "process_target": "",
                    "next_action": "",
                    "criteria": "",
                    "event": "",
                    "current_state": "",
                    "next_state": "",
                    "policy_id": "",
                    "usecase_id": "",
                    "process_id": "",
                    "usecase_ids": [],
                    "related_functions": [],
                    "related_policies": [],
                    "process_ids": [],
                    "details": [],
                    "items": [],
                    "reason": "정책 항목이 일반 설명이라 판단축을 보강한다.",
                },
                {
                    "collection": "policy_details",
                    "id": "PI-MBR-999-99",
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "name": "새 항목",
                    "description": "",
                    "content": "새 항목을 만들면 안 된다.",
                    "actor": "",
                    "process_target": "",
                    "next_action": "",
                    "criteria": "",
                    "event": "",
                    "current_state": "",
                    "next_state": "",
                    "policy_id": "",
                    "usecase_id": "",
                    "process_id": "",
                    "usecase_ids": [],
                    "related_functions": [],
                    "related_policies": [],
                    "process_ids": [],
                    "details": [],
                    "items": [],
                    "reason": "존재하지 않는 ID는 무시한다.",
                },
            ],
            "notes": [],
        }

        applied = apply_final_revision_patch(spec, payload)

        self.assertEqual(1, len(applied))
        self.assertIn("BSS 판정 결과", spec["policy_details"][0]["content"])
        self.assertEqual(1, len(spec["policy_details"]))

    def test_apply_final_revision_patch_updates_state_transition_by_match(self):
        spec = {
            "state_transitions": [
                {
                    "usecase_ids": ["US-MBR-001"],
                    "current_state": "미가입",
                    "event": "회원 가입 완료",
                    "next_state": "정상",
                    "criteria": "가입하면 정상으로 전환한다.",
                }
            ]
        }
        payload = {
            "updates": [
                {
                    "collection": "state_transitions",
                    "id": "",
                    "match_current_state": "미가입",
                    "match_event": "회원 가입 완료",
                    "match_next_state": "정상",
                    "name": "",
                    "description": "",
                    "content": "",
                    "actor": "",
                    "process_target": "",
                    "next_action": "",
                    "criteria": "본인 인증, 필수 동의, BSS 가입 가능 판정이 모두 완료되면 정상으로 전환한다.",
                    "event": "",
                    "current_state": "",
                    "next_state": "",
                    "policy_id": "",
                    "usecase_id": "",
                    "process_id": "",
                    "usecase_ids": [],
                    "related_functions": [],
                    "related_policies": [],
                    "process_ids": [],
                    "details": [],
                    "items": [],
                    "reason": "전이 조건을 구체화한다.",
                }
            ],
            "notes": [],
        }

        applied = apply_final_revision_patch(spec, payload)

        self.assertEqual(1, len(applied))
        self.assertIn("BSS 가입 가능 판정", spec["state_transitions"][0]["criteria"])

    def test_apply_final_revision_patch_accepts_compact_field_value_update(self):
        spec = {
            "policy_details": [
                {
                    "id": "PI-MBR-001-01",
                    "policy_id": "PG-MBR-001",
                    "name": "이력 저장 기준",
                    "content": "이력을 저장한다.",
                }
            ]
        }
        payload = {
            "updates": [
                {
                    "collection": "policy_details",
                    "id": "PI-MBR-001-01",
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "field": "content",
                    "value": "회원 가입·탈퇴 요청, BSS 판정 결과, 고객 고지 결과를 요청일시와 처리 주체 기준으로 저장한다.",
                    "values": [],
                    "reason": "정책 항목의 이력 판단 기준을 보강한다.",
                }
            ],
            "notes": [],
        }

        applied = apply_final_revision_patch(spec, payload)

        self.assertEqual(1, len(applied))
        self.assertEqual(["content"], applied[0]["fields"])
        self.assertIn("BSS 판정 결과", spec["policy_details"][0]["content"])

    def test_apply_final_revision_patch_accepts_compact_list_update(self):
        spec = {
            "functions": [
                {
                    "id": "FN-MBR-001",
                    "process_id": "PR-MBR-001",
                    "name": "가입 요청 처리",
                    "description": "가입 요청을 처리한다.",
                    "details": ["가입 요청 접수"],
                }
            ]
        }
        payload = {
            "updates": [
                {
                    "collection": "functions",
                    "id": "FN-MBR-001",
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "field": "details",
                    "value": "",
                    "values": ["가입 요청 접수", "본인 인증 결과 확인", "BSS 가입 가능 판정 결과 반영"],
                    "reason": "세부 기능 구성을 업무 처리 단위로 보강한다.",
                }
            ],
            "notes": [],
        }

        applied = apply_final_revision_patch(spec, payload)

        self.assertEqual(1, len(applied))
        self.assertEqual(["details"], applied[0]["fields"])
        self.assertIn("BSS 가입 가능 판정 결과 반영", spec["functions"][0]["details"])

    def test_final_revision_spec_pack_prioritizes_feedback_text_match(self):
        policy_details = [
            {
                "id": f"PI-XOG-{index:03d}",
                "policy_id": "PG-XOG-001",
                "name": f"일반 정책 항목 {index}",
                "content": "일반 판단 기준을 정의한다.",
            }
            for index in range(90)
        ]
        policy_details[-1]["name"] = "미연결 정책 항목 정리 기준"
        spec = {"meta": {"topic": "테스트"}, "policy_details": policy_details}

        pack = final_revision_spec_pack(
            spec,
            [
                {
                    "chapter": "policies",
                    "title": "미연결 정책 항목 정리 기준 보강",
                    "detail": "미연결 정책 항목 정리 기준이 약하다.",
                }
            ],
        )

        self.assertTrue(any(item["id"] == "PI-XOG-089" for item in pack["policy_details"]))

    def test_final_remediation_runtime_reuses_existing_authoring_blueprint(self):
        blueprint = {
            "document_strategy": {"topic_definition": "회원 가입과 탈퇴 업무 기준을 정의한다."},
            "chapter_blueprints": [{"stage": "overview", "writing_goal": "범위와 원칙 정의"}],
        }
        ctx = PolicyContext(
            topic="회원 가입, 탈퇴",
            topic_html="회원 가입, 탈퇴",
            topic_slug="회원_가입_탈퇴",
            module_id="PM-27",
            business_code="MBR",
            version="v0.1",
            version_number="0.1",
            today="2026-05-05",
            status="초안",
            author="tester",
            brief="",
            brief_html="",
            template_path=Path("template.html"),
            template_type="simple",
            output_dir=Path("output"),
            requirements=(),
            references=(),
        )

        runtime = build_final_remediation_runtime(
            ctx,
            "<html></html>",
            [],
            {"meta": {"authoring_blueprint": blueprint, "topic_learning": {"summary": "학습"}}},
        )

        self.assertEqual(blueprint, runtime.authoring_blueprint)


if __name__ == "__main__":
    unittest.main()
