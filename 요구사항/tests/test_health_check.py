import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from health_check_evaluator import (
    build_health_remediation_plan,
    evaluate_health_check,
    evaluate_health_gatekeeper,
    load_health_check_rubric,
)
import web_app


class HealthCheckEvaluatorTest(unittest.TestCase):
    def test_rubric_has_expected_sections_and_gates(self):
        rubric = load_health_check_rubric()

        self.assertEqual(rubric["rubric_id"], "policy_health_check")
        self.assertEqual(len(rubric["sections"]), 10)
        self.assertEqual(sum(len(section["items"]) for section in rubric["sections"]), 50)
        self.assertEqual(len(rubric["mandatory_gates"]), 7)

    def test_evaluator_returns_scorecard_without_llm(self):
        document = """
        <html><body>
          <h2>가. 범위</h2>
          <p>회원 가입/탈퇴 업무의 대상 업무, 포함 범위, 제외 범위, 정책서 간 경계를 정의한다.</p>
          <p>통합채널, 앱/웹, FO, BSS가 고객 처리 가능 여부와 처리 결과를 확인한다.</p>
          <h2>나. 설계 원칙</h2>
          <p>중복 입력과 수작업을 줄이고 셀프 처리와 자동 처리를 우선한다.</p>
          <table>
            <tr><th>액터 ID</th><th>액터명</th></tr>
            <tr><td>ACT-MBR-CUS-001</td><td>고객</td></tr>
            <tr><td>ACT-MBR-BSS-001</td><td>BSS</td></tr>
          </table>
          <table>
            <tr><th>유즈케이스 ID</th><th>유즈케이스명</th></tr>
            <tr><td>US-MBR-JOIN-001</td><td>회원 가입 신청</td></tr>
            <tr><td>US-MBR-LEAVE-001</td><td>회원 탈퇴 요청</td></tr>
            <tr><td>US-MBR-RECOVER-001</td><td>실패 후 재시도</td></tr>
          </table>
          <table>
            <tr><th>상태 코드</th><th>상태명</th></tr>
            <tr><td>ST-MBR-REQ-001</td><td>신청 중</td></tr>
            <tr><td>ST-MBR-DONE-001</td><td>처리 완료</td></tr>
            <tr><td>ST-MBR-FAIL-001</td><td>처리 실패</td></tr>
          </table>
          <table>
            <tr><th>현재 상태</th><th>전이 이벤트</th><th>다음 상태</th></tr>
            <tr><td>ST-MBR-REQ-001</td><td>US-MBR-JOIN-001</td><td>ST-MBR-DONE-001</td></tr>
          </table>
          <table>
            <tr><th>프로세스 ID</th><th>프로세스명</th><th>관련 기능</th><th>관련 정책</th></tr>
            <tr><td>PR-MBR-JOIN-001</td><td>가입 조건 확인</td><td>FN-MBR-AUTH-001</td><td>PG-MBR-AUTH-001</td></tr>
            <tr><td>PR-MBR-LEAVE-001</td><td>탈퇴 영향 확인</td><td>FN-MBR-LEAVE-001</td><td>PG-MBR-LEAVE-001</td></tr>
          </table>
          <table>
            <tr><th>기능 ID</th><th>기능명</th><th>세부 기능 구성</th></tr>
            <tr><td>FN-MBR-AUTH-001</td><td>본인 인증 처리</td><td>인증 요청, 검증, 이력 저장</td></tr>
            <tr><td>FN-MBR-LEAVE-001</td><td>탈퇴 처리</td><td>영향 산정, 상태 반영, 결과 회신</td></tr>
          </table>
          <table>
            <tr><th>정책 ID</th><th>정책명</th><th>정책 항목</th></tr>
            <tr><td>PG-MBR-AUTH-001</td><td>인증 정책</td><td>PI-MBR-AUTH-001-01</td></tr>
            <tr><td>PG-MBR-LEAVE-001</td><td>탈퇴 정책</td><td>PI-MBR-LEAVE-001-01</td></tr>
          </table>
          <ul>
            <li>인증 유효 시간 (PI-MBR-AUTH-001-01)<br/>- 인증번호 유효 시간은 10분이며 만료되면 재인증을 요구한다.</li>
            <li>탈퇴 재처리 (PI-MBR-LEAVE-001-01)<br/>- BSS 원장 반영 실패 시 상태는 처리 실패로 저장하고 최대 3회 재시도한다.</li>
          </ul>
          <p>인증 실패, 조회 실패, 결제 실패, 외부 시스템 연동 실패 시 고객에게 실패 사유와 다음 행동을 안내한다.</p>
          <p>입력 데이터의 필수 여부, 출처, 검증, 변환, 출력 데이터, 저장, 이력, 보관, 마스킹 기준을 관리한다.</p>
          <p>요구사항 매핑, 신규 도출, 개발, QA 테스트 조건과 기대 결과를 추적한다.</p>
        </body></html>
        """

        report = evaluate_health_check(
            document=document,
            file_name="NC_회원가입탈퇴_정책서_간소화_v0.1.html",
            topic="회원가입탈퇴",
            template_type="simple",
        )

        self.assertEqual(report["evaluationMode"], "code")
        self.assertGreaterEqual(report["score"], 0)
        self.assertLessEqual(report["score"], 100)
        self.assertEqual(len(report["sections"]), 10)
        self.assertEqual(len(report["mandatoryGates"]), 7)
        self.assertIn(report["judgement"], {"우수", "양호", "보완 필요", "재검토 필요", "재작성 필요"})
        self.assertIn("gatekeeper", report)
        self.assertEqual(len(report["gatekeeper"]["dimensions"]), 5)
        self.assertEqual(report["qualityGatePassed"], report["gatekeeper"]["passed"])
        self.assertIn(report["gatekeeper"]["grade"], {"A", "B", "C", "F"})
        self.assertIn("GateKeeper", report["summary"])
        self.assertIn("remediationPlan", report)
        self.assertIn("immediate", report["remediationPlan"])

    def test_remediation_plan_splits_priority_history_and_artifact_sync(self):
        previous_report = {
            "sections": [
                {
                    "id": "scope",
                    "name": "범위",
                    "items": [
                        {"id": "1-1", "score": 2, "maxScore": 2, "question": "범위 충분"},
                        {"id": "2-1", "score": 0, "maxScore": 2, "question": "정책값 부족"},
                    ],
                }
            ]
        }
        sections = [
            {
                "id": "scope",
                "name": "범위",
                "score": 3,
                "items": [
                    {
                        "id": "1-1",
                        "score": 1,
                        "maxScore": 2,
                        "question": "범위 충분",
                        "suggestion": "범위 기준을 보강한다.",
                        "relatedLocation": "1. 개요",
                    },
                    {
                        "id": "2-1",
                        "score": 0,
                        "maxScore": 2,
                        "question": "정책값 부족",
                        "suggestion": "정책값을 확정한다.",
                        "relatedLocation": "6. 정책 정의",
                    },
                    {
                        "id": "3-1",
                        "score": 2,
                        "maxScore": 2,
                        "question": "개선 완료",
                        "suggestion": "",
                        "relatedLocation": "3. 유즈케이스",
                    },
                ],
            }
        ]
        plan = build_health_remediation_plan(
            sections=sections,
            gates=[{"id": "G1", "itemRef": "2-1", "passed": False}],
            action_items=[
                {
                    "itemId": "ARTIFACT-DRIFT",
                    "section": "산출물 동기화",
                    "priority": "P1",
                    "title": "spec 불일치",
                    "targetLocation": "HTML/spec",
                    "suggestion": "spec을 재생성한다.",
                    "score": 0,
                }
            ],
            previous_report=previous_report,
            recheck_item_ids=["1-1", "2-1"],
            artifact_drift={"status": "fail", "summary": "산출물 동기화 차단 항목이 있습니다.", "issues": []},
        )

        self.assertEqual(1, len(plan["immediate"]))
        self.assertEqual("2-1", plan["immediate"][0]["itemId"])
        self.assertEqual("repeated", plan["immediate"][0]["historyStatus"])
        self.assertEqual(1, len(plan["potential"]))
        self.assertEqual("regressed", plan["potential"][0]["historyStatus"])
        self.assertEqual(1, plan["recheck"]["newCount"])
        self.assertEqual(1, plan["recheck"]["repeatedCount"])
        self.assertGreaterEqual(len(plan["artifactSync"]), 1)
        self.assertIn("즉시 보완", plan["summary"])

    def test_template_profile_keeps_simple_strict_without_full_only_scope(self):
        document = """
        <html><body>
          <h2>가. 범위</h2>
          <p>프로파일테스트 대상 업무, 포함 범위, 제외 범위, 정책서 간 경계를 정의한다.</p>
          <p>통합채널, 앱/웹, FO, BSS가 고객 처리 가능 여부와 처리 결과를 확인한다.</p>
          <p>중복 입력과 수작업을 줄이고 셀프 처리와 자동 처리를 우선한다.</p>
          <table><tr><th>액터 ID</th></tr><tr><td>ACT-PRF-CUS-001</td></tr><tr><td>ACT-PRF-BSS-001</td></tr></table>
          <table><tr><th>유즈케이스 ID</th></tr><tr><td>US-PRF-001</td></tr><tr><td>US-PRF-002</td></tr><tr><td>US-PRF-003</td></tr></table>
          <table><tr><th>프로세스 ID</th><th>프로세스명</th><th>관련 기능</th><th>관련 정책</th></tr>
            <tr><td>PR-PRF-001</td><td>조건 확인</td><td>FN-PRF-001</td><td>PG-PRF-001</td></tr>
            <tr><td>PR-PRF-002</td><td>결과 반영</td><td>FN-PRF-002</td><td>PG-PRF-001</td></tr>
          </table>
          <table><tr><th>기능 ID</th><th>기능명</th><th>세부 기능 구성</th></tr>
            <tr><td>FN-PRF-001</td><td>조건 검증</td><td>입력 데이터 확인, BSS 검증, 결과 회신</td></tr>
            <tr><td>FN-PRF-002</td><td>결과 저장</td><td>출력 데이터 생성, 이력 저장, 고객 안내</td></tr>
          </table>
          <table><tr><th>정책 ID</th><th>정책 항목</th></tr><tr><td>PG-PRF-001</td><td>PI-PRF-001-01</td></tr></table>
          <div class="policy-item"><div class="policy-item-title">처리 허용 기준 <span>PI-PRF-001-01</span></div><div class="policy-item-content">- 고객 상태가 정상이고 인증이 완료된 경우에만 허용한다.</div></div>
          <p>요구사항 3건을 프로세스, 기능, 정책으로 매핑하고 개발, QA 테스트 조건과 기대 결과를 관리한다.</p>
        </body></html>
        """

        simple_report = evaluate_health_check(
            document=document,
            file_name="NC_프로파일테스트_정책서_간소화_v0.10.html",
            topic="프로파일테스트",
            template_type="simple",
        )
        full_report = evaluate_health_check(
            document=document,
            file_name="NC_프로파일테스트_정책서_Full_v0.10.html",
            topic="프로파일테스트",
            template_type="full",
        )
        simple_items = {item["id"]: item for section in simple_report["sections"] for item in section["items"]}
        full_items = {item["id"]: item for section in full_report["sections"] for item in section["items"]}

        self.assertEqual("간소화 버전", simple_report["templateProfile"]["label"])
        self.assertEqual("Full 버전", full_report["templateProfile"]["label"])
        self.assertEqual(2, simple_items["4-3"]["score"])
        self.assertLess(full_items["4-3"]["score"], 2)
        self.assertIn("프로세스 상세", full_items["4-3"]["suggestion"])

    def test_full_template_scores_full_detail_scope(self):
        document = """
        <html><body>
          <h2>가. 범위</h2>
          <p>Full프로파일 대상 업무, 포함 범위, 제외 범위, 정책서 간 경계를 정의한다.</p>
          <p>통합채널, 앱/웹, FO, BSS가 고객 처리 가능 여부와 처리 결과를 확인한다.</p>
          <p>중복 입력과 수작업을 줄이고 셀프 처리와 자동 처리를 우선한다.</p>
          <table><tr><th>액터 ID</th></tr><tr><td>ACT-FUL-CUS-001</td></tr><tr><td>ACT-FUL-BSS-001</td></tr></table>
          <table><tr><th>유즈케이스 ID</th></tr><tr><td>US-FUL-001</td></tr><tr><td>US-FUL-002</td></tr><tr><td>US-FUL-003</td></tr></table>
          <table><tr><th>상태 코드</th></tr><tr><td>ST-FUL-REQ-001</td></tr><tr><td>ST-FUL-DONE-001</td></tr><tr><td>ST-FUL-FAIL-001</td></tr></table>
          <table><tr><th>현재 상태</th><th>전이 이벤트</th><th>다음 상태</th></tr><tr><td>신청 중</td><td>US-FUL-001</td><td>처리 완료</td></tr><tr><td>신청 중</td><td>US-FUL-002</td><td>처리 실패</td></tr><tr><td>처리 실패</td><td>US-FUL-003</td><td>처리 완료</td></tr></table>
          <table><tr><th>프로세스 ID</th><th>프로세스명</th><th>관련 기능</th><th>관련 정책</th></tr>
            <tr><td>PR-FUL-001</td><td>조건 확인</td><td>FN-FUL-001</td><td>PG-FUL-001</td></tr>
            <tr><td>PR-FUL-002</td><td>결과 반영</td><td>FN-FUL-002</td><td>PG-FUL-001</td></tr>
          </table>
          <h3>나. 프로세스 상세</h3>
          <table><tr><th>프로세스 ID</th><th>진입 조건</th><th>종료 조건</th><th>선행</th><th>후행</th><th>관련 기능</th><th>관련 정책</th></tr>
            <tr><td>PR-FUL-001</td><td>고객 상태 확인 가능</td><td>검증 결과 확정</td><td>US-FUL-001</td><td>PR-FUL-002</td><td>FN-FUL-001</td><td>PG-FUL-001</td></tr>
          </table>
          <table><tr><th>기능 ID</th><th>기능명</th><th>세부 기능 구성</th></tr>
            <tr><td>FN-FUL-001</td><td>조건 검증</td><td>입력 데이터 확인, BSS 검증, 결과 회신</td></tr>
            <tr><td>FN-FUL-002</td><td>결과 저장</td><td>출력 데이터 생성, 이력 저장, 고객 안내</td></tr>
          </table>
          <h3>나. 기능 상세</h3>
          <table><tr><th>기능 ID</th><th>입력 정보</th><th>처리 (상태-액션-결과)</th><th>출력 정보</th><th>실패·예외</th><th>관련 정책</th></tr>
            <tr><td>FN-FUL-001</td><td>고객 입력값, 시스템 조회값, 외부 연계 결과, 필수/선택 값</td><td>(상태) 정상 → (액션) 입력 데이터 검증과 BSS 조회를 수행한다 → (결과) 처리 가능 결과를 생성한다<br/>(상태) 예외 → (액션) 연계 실패 사유를 저장한다 → (결과) 재시도 안내를 제공한다</td><td>출력 데이터와 처리 결과</td><td>실패·예외, 중복 요청, 재시도 기준</td><td>PG-FUL-001</td></tr>
          </table>
          <table><tr><th>정책 ID</th><th>정책 항목</th></tr><tr><td>PG-FUL-001</td><td>PI-FUL-001-01</td></tr></table>
          <div class="policy-item"><div class="policy-item-title">처리 허용 기준 <span>PI-FUL-001-01</span></div><div class="policy-item-content">- 고객 상태가 정상이고 인증이 완료된 경우에만 허용한다. 실패 시 최대 3회 재시도하고 결과와 이력은 5년 보관한다.</div></div>
          <p>요구사항 3건을 프로세스, 기능, 정책으로 매핑하고 신규 도출, 개발, QA 테스트 조건과 기대 결과를 관리한다.</p>
        </body></html>
        """

        report = evaluate_health_check(
            document=document,
            file_name="NC_Full프로파일_정책서_Full_v0.10.html",
            topic="Full프로파일",
            template_type="full",
        )
        items = {item["id"]: item for section in report["sections"] for item in section["items"]}

        self.assertEqual(2, items["4-3"]["score"])
        self.assertEqual(2, items["4-4"]["score"])
        self.assertEqual(2, items["9-3"]["score"])
        self.assertGreaterEqual(report["signals"]["full_state_action_result_count"], 2)

    def test_health_gatekeeper_flags_internal_inconsistency(self):
        report = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <p>통합채널, BSS, 요구사항, 개발, QA 테스트 기준을 정의한다.</p>
            </body></html>
            """,
            file_name="inconsistent.html",
            topic="불일치",
            template_type="simple",
        )
        report["rawScore"] = 0
        report["score"] = 100
        report["mandatoryGatePassed"] = True
        report["judgement"] = "우수"

        gatekeeper = evaluate_health_gatekeeper(report, rubric=load_health_check_rubric())
        internal = next(item for item in gatekeeper["dimensions"] if item["name"] == "internal_consistency")

        self.assertEqual(internal["status"], "fail")
        self.assertFalse(gatekeeper["passed"])

    def test_selective_recheck_reuses_previous_non_selected_items(self):
        previous = evaluate_health_check(
            document="<html><body><h2>가. 범위</h2><p>통합채널 BSS 요구사항 개발 QA 테스트 기준을 정의한다.</p></body></html>",
            file_name="selective.html",
            topic="선택재점검",
            template_type="simple",
        )

        refreshed = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <p>선택재점검 대상 업무, 포함 범위, 제외 범위, 정책서 간 경계를 정의한다.</p>
              <p>통합채널, 앱/웹, FO, BSS가 고객 처리 가능 여부와 처리 결과를 확인한다.</p>
            </body></html>
            """,
            file_name="selective.html",
            topic="선택재점검",
            template_type="simple",
            previous_report=previous,
            recheck_item_ids=["1-1"],
        )

        items = {item["id"]: item for section in refreshed["sections"] for item in section["items"]}
        self.assertEqual(refreshed["recheckScope"]["mode"], "failed-items")
        self.assertEqual(items["1-1"]["recheckStatus"], "rechecked")
        self.assertEqual(items["1-2"]["recheckStatus"], "reused")

    def test_weak_policy_phrase_reduces_specificity_gate(self):
        report = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <table><tr><th>정책 ID</th><th>정책명</th></tr><tr><td>PG-ABC-001</td><td>정책</td></tr></table>
              <ul><li>정책 항목 (PI-ABC-001-01)<br/>- 시스템 기준에 따라 처리한다.</li></ul>
            </body></html>
            """,
            file_name="weak.html",
            topic="약한 정책",
            template_type="simple",
        )

        gate_g5 = next(gate for gate in report["mandatoryGates"] if gate["id"] == "G5")
        self.assertFalse(gate_g5["passed"])
        self.assertIn(report["judgement"], {"보완 필요", "재검토 필요", "재작성 필요"})

    def test_missing_requirement_mapping_caps_health_score(self):
        report = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <p>요구사항을 업무 흐름과 정책 기준으로 재구성한다.</p>
              <p>통합채널, 앱/웹, FO, BSS 책임 경계와 고객 처리 가능 여부를 정의한다.</p>
              <table><tr><th>액터 ID</th></tr><tr><td>ACT-ABC-CUS-001</td></tr><tr><td>ACT-ABC-BSS-001</td></tr></table>
              <table><tr><th>유즈케이스 ID</th></tr><tr><td>US-ABC-001</td></tr><tr><td>US-ABC-002</td></tr><tr><td>US-ABC-003</td></tr></table>
              <table><tr><th>현재 상태</th><th>전이 이벤트</th><th>다음 상태</th></tr><tr><td>대기</td><td>US-ABC-001</td><td>완료</td></tr><tr><td>대기</td><td>US-ABC-002</td><td>실패</td></tr><tr><td>실패</td><td>US-ABC-003</td><td>완료</td></tr></table>
              <table><tr><th>프로세스 ID</th><th>관련 기능</th><th>관련 정책</th></tr><tr><td>PR-ABC-001</td><td>FN-ABC-001</td><td>PG-ABC-001</td></tr></table>
              <table><tr><th>정책 ID</th><th>정책 항목</th></tr><tr><td>PG-ABC-001</td><td>PI-ABC-001-01</td></tr></table>
              <div class="policy-item"><div class="policy-item-title">기준 <span>PI-ABC-001-01</span></div><div class="policy-item-content">- 허용 조건은 고객 상태가 정상이고 인증이 완료된 경우로 제한한다.</div></div>
              <p>인증 실패, 조회 실패, 결제 실패, 외부 시스템 연동 실패 시 최대 3회 재시도하고 실패 사유와 복구 방법을 안내한다.</p>
              <p>입력 데이터 출처, 생성 주체, 필수·선택 여부, 검증, 변환, 출력 데이터, 저장, 이력, 보관, 마스킹 기준을 관리한다.</p>
              <p>신규 도출, 개발, QA 테스트 조건과 기대 결과를 관리한다.</p>
            </body></html>
            """,
            file_name="missing_req_map.html",
            topic="요구사항 매핑 없음",
            template_type="simple",
        )

        gate_g7 = next(gate for gate in report["mandatoryGates"] if gate["id"] == "G7")
        self.assertFalse(gate_g7["passed"])
        self.assertLessEqual(report["score"], 79)
        self.assertGreaterEqual(report["rawScore"], report["score"])

    def test_truncated_policy_item_fails_specificity_gate(self):
        report = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <table><tr><th>정책 ID</th><th>정책명</th></tr><tr><td>PG-ABC-001</td><td>정책</td></tr></table>
              <div class="policy-item"><div class="policy-item-title">기준 <span>PI-ABC-001-01</span></div><div class="policy-item-content">- 고객 고지 기준은 고지 대상, 고지 시점, 필수 안내 항목을…</div></div>
            </body></html>
            """,
            file_name="truncated.html",
            topic="말줄임 정책",
            template_type="simple",
        )

        gate_g5 = next(gate for gate in report["mandatoryGates"] if gate["id"] == "G5")
        self.assertFalse(gate_g5["passed"])
        self.assertLessEqual(report["score"], 79)

    def test_topic_scoped_failure_cases_count_for_display_management(self):
        report = evaluate_health_check(
            document="""
            <html><body>
              <h2>가. 범위</h2>
              <p>전시/관리 기능은 통합채널, 앱/웹, FO, BSS, 분석 연계 시스템이 고객별 노출 가능 여부와 게시 반영 결과를 확인하는 기준을 정의한다.</p>
              <p>포함 범위와 제외 범위, 정책서 간 경계를 정의하고 고객 표시 상태와 시스템 내부 상태를 구분한다.</p>
              <table><tr><th>액터 ID</th><th>액터명</th></tr><tr><td>ACT-DSP-001</td><td>고객</td></tr><tr><td>ACT-DSP-002</td><td>BSS/분석 연계 시스템</td></tr></table>
              <table><tr><th>유즈케이스 ID</th><th>유즈케이스명</th></tr><tr><td>US-DSP-CUS-001</td><td>개인화 전시 확인</td></tr><tr><td>US-DSP-OPR-001</td><td>전시 기준 운영</td></tr><tr><td>US-DSP-BSS-001</td><td>BSS·분석 조건 판정</td></tr></table>
              <table><tr><th>상태 코드</th><th>상태명</th></tr><tr><td>ST-DSP-001</td><td>게시 대기</td></tr><tr><td>ST-DSP-002</td><td>게시 완료</td></tr><tr><td>ST-DSP-003</td><td>게시 반영 실패</td></tr></table>
              <table><tr><th>현재 상태</th><th>전이 이벤트</th><th>다음 상태</th><th>처리 기준 및 후속 처리</th></tr><tr><td>게시 대기</td><td>US-DSP-OPR-001, US-DSP-BSS-001</td><td>게시 완료</td><td>BSS·분석 응답이 3초 안에 회신되고 채널별 게시 반영 결과가 성공이면 완료한다.</td></tr><tr><td>게시 대기</td><td>US-DSP-BSS-001</td><td>게시 반영 실패</td><td>BSS·분석 응답 지연, 딥링크 실패, 캐시 무효화 실패, 채널별 게시 반영 실패가 있으면 실패 사유와 대체 노출 경로를 안내한다.</td></tr></table>
              <table><tr><th>프로세스 ID</th><th>프로세스명</th><th>관련 기능</th><th>관련 정책</th></tr><tr><td>PR-DSP-001</td><td>전시 조건 확인</td><td>FN-DSP-001</td><td>PG-DSP-001</td></tr></table>
              <table><tr><th>기능 ID</th><th>기능명</th><th>세부 기능 구성</th></tr><tr><td>FN-DSP-001</td><td>전시 조건 판정</td><td>조건 조회, 분석 응답 확인, 결과 회신, 이력 저장</td></tr></table>
              <table><tr><th>정책 ID</th><th>정책명</th><th>정책 항목</th></tr><tr><td>PG-DSP-001</td><td>게시 반영 정책</td><td>PI-DSP-001-01</td></tr></table>
              <div class="policy-item"><div class="policy-item-title">BSS·분석 연계 실패 폴백 <span>PI-DSP-001-01</span></div><div class="policy-item-content">- BSS·분석 응답이 3초 안에 회신되지 않으면 고객별 전시를 확정하지 않고 공통 기본 전시를 제공한다.<br/>- 중복 게시 요청은 5분 안에는 최초 요청 결과를 재사용하고 실패 이력과 결과 회신을 저장한다.</div></div>
              <p>요구사항 149건을 프로세스, 기능, 정책으로 매핑하고 신규 도출, 개발, QA 테스트 조건과 기대 결과를 추적한다.</p>
            </body></html>
            """,
            file_name="display.html",
            topic="전시/관리 기능",
            template_type="simple",
        )

        items = {item["id"]: item for section in report["sections"] for item in section["items"]}
        self.assertEqual(2, items["7-1"]["score"])
        self.assertEqual(2, items["8-3"]["score"])

    def test_web_health_check_falls_back_when_llm_preflight_fails(self):
        class FailingClient:
            enabled = True
            writer_mode = "llm"

            def preflight_check(self):
                raise RuntimeError("preflight unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "NC_테스트_정책서_간소화_v0.1.html"
            policy_path.write_text(
                "<html><body><h2>가. 범위</h2><p>통합채널 BSS 요구사항 개발 QA 테스트 기준을 정의한다.</p></body></html>",
                encoding="utf-8",
            )
            with (
                patch.object(web_app, "policy_file_path", return_value=policy_path),
                patch.object(web_app, "parse_policy_filename", return_value={"topic": "테스트", "template_label": "간소화", "version": "v0.1"}),
                patch.object(web_app, "llm_client_from_web_payload", return_value=FailingClient()),
                patch.object(web_app, "llm_preflight_enabled", return_value=True),
                patch.object(web_app, "save_health_check_report", return_value=Path(tmp) / "health.json"),
            ):
                report = web_app.health_check_from_payload(
                    {
                        "name": policy_path.name,
                        "writerMode": "llm",
                        "healthCheckUseLlm": True,
                        "llmAccessToken": web_app.LLM_ACCESS_TOKEN_VALUE,
                        "clientSessionId": "test-session",
                    }
                )

        self.assertEqual(report["evaluationMode"], "code")
        self.assertIn("preflight unavailable", report["llmError"])
        self.assertEqual(report["clientSessionId"], "test-session")

    def test_web_health_check_is_code_based_by_default_even_when_global_llm_is_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "NC_테스트_정책서_간소화_v0.1.html"
            policy_path.write_text(
                "<html><body><h2>가. 범위</h2><p>통합채널 BSS 요구사항 개발 QA 테스트 기준을 정의한다.</p></body></html>",
                encoding="utf-8",
            )
            with (
                patch.object(web_app, "policy_file_path", return_value=policy_path),
                patch.object(web_app, "parse_policy_filename", return_value={"topic": "테스트", "template_label": "간소화", "version": "v0.1"}),
                patch.object(web_app, "save_health_check_report", return_value=Path(tmp) / "health.json"),
            ):
                report = web_app.health_check_from_payload(
                    {
                        "name": policy_path.name,
                        "writerMode": "llm",
                        "clientSessionId": "test-session",
                    }
                )

        self.assertEqual(report["evaluationMode"], "code")
        self.assertEqual(report.get("llmError", ""), "")
        self.assertEqual(report["clientSessionId"], "test-session")

    def test_web_health_check_supports_interrupted_draft_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            checkpoints_dir = output_root / "checkpoints"
            steps_dir = output_root / "steps"
            checkpoints_dir.mkdir()
            steps_dir.mkdir()
            preview_path = steps_dir / "NC_중단문서_정책서_간소화_v0.1_01_overview.html"
            preview_path.write_text(
                "<html><body><h2>가. 범위</h2><p>통합채널 BSS 요구사항 개발 QA 테스트 기준을 정의한다.</p></body></html>",
                encoding="utf-8",
            )
            checkpoint_path = checkpoints_dir / "NC_중단문서_정책서_간소화_v0.1_latest_checkpoint.json"
            checkpoint_path.write_text(
                json.dumps(
                    {
                        "checkpoint": {
                            "topic": "중단문서",
                            "topic_slug": "중단문서",
                            "template_type": "simple",
                            "version": "v0.1",
                            "stage_key": "01",
                            "stage_name": "overview",
                            "stage_label": "개요",
                        },
                        "spec": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (
                patch.object(web_app, "OUTPUT_ROOT", output_root),
                patch.object(web_app, "save_health_check_report", return_value=output_root / "health.json"),
            ):
                report = web_app.health_check_from_payload(
                    {
                        "draftResumeFrom": "checkpoints/NC_중단문서_정책서_간소화_v0.1_latest_checkpoint.json",
                        "writerMode": "mock",
                        "clientSessionId": "draft-session",
                    }
                )

        self.assertEqual(report["fileName"], preview_path.name)
        self.assertEqual(report["topic"], "중단문서")
        self.assertEqual(report["templateType"], "simple")
        self.assertEqual(report["evaluationMode"], "code")
        self.assertEqual(report["clientSessionId"], "draft-session")

    def test_web_health_check_export_creates_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            reports_root = Path(tmp) / "reports"
            output_root.mkdir()
            reports_root.mkdir()
            policy_path = output_root / "NC_테스트_정책서_간소화_v0.1.html"
            policy_path.write_text(
                "<html><body><h2>가. 범위</h2><p>통합채널 BSS 요구사항 개발 QA 테스트 기준을 정의한다.</p></body></html>",
                encoding="utf-8",
            )
            with (
                patch.object(web_app, "OUTPUT_ROOT", output_root),
                patch.object(web_app, "REPORTS_DIR", reports_root),
                patch.object(web_app, "RUNTIME_REPORTS_ROOT", reports_root),
            ):
                report = web_app.health_check_from_payload({"name": policy_path.name, "writerMode": "mock"})
                artifact = web_app.health_check_export_from_payload({"name": policy_path.name, "report": report})
                exported = output_root / artifact["path"]
                self.assertTrue(exported.exists())
                self.assertIn("Policy Health Check Export", exported.read_text(encoding="utf-8"))

    def test_completed_checkpoint_is_restored_not_shown_as_interrupted_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            checkpoints_dir = output_root / "checkpoints"
            checkpoints_dir.mkdir()
            template_path = output_root / "template.html"
            template_path.write_text("<html></html>", encoding="utf-8")
            checkpoint_path = checkpoints_dir / "NC_완료문서_정책서_간소화_v0.1_latest_checkpoint.json"
            checkpoint_path.write_text(
                json.dumps(
                    {
                        "checkpoint": {
                            "topic": "완료문서",
                            "topic_slug": "완료문서",
                            "template_type": "simple",
                            "version": "v0.1",
                            "stage_key": "10",
                            "stage_name": "final_check",
                            "stage_label": "Final Check Agent",
                            "passed": True,
                        },
                        "spec": {"meta": {"title": "완료문서"}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (
                patch.object(web_app, "OUTPUT_ROOT", output_root),
                patch.object(web_app, "choose_template", return_value=template_path),
                patch.object(web_app, "render_policy_html", return_value="<html><body>완료</body></html>"),
            ):
                items = web_app.list_policy_files()
                drafts = web_app.list_resumable_drafts()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "NC_완료문서_정책서_간소화_v0.1.html")
        self.assertEqual(drafts, [])


if __name__ == "__main__":
    unittest.main()
