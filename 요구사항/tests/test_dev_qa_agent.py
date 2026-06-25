import unittest

from dev_qa_agent import normalize_dev_qa_review


class DevQaAgentNormalizationTest(unittest.TestCase):
    def test_filters_meta_evidence_gaps(self):
        report = normalize_dev_qa_review(
            {
                "agent": "Development QA Review Agent",
                "score": 80,
                "verdict": "보완 필요",
                "summary": "검수 완료",
                "development_findings": [],
                "qa_findings": [],
                "coverage_checks": [],
                "recommended_actions": [],
                "evidence_gaps": [
                    "제공된 정책서 본문이 ...TRUNCATED...로 종료되어 확인할 수 없다.",
                    "요구사항 통합 list 원문이 제공되지 않았다.",
                    "발송량 제한 상한의 결정 근거가 정책 항목에 없다.",
                ],
            }
        )
        self.assertEqual(report["evidence_gaps"], ["발송량 제한 상한의 결정 근거가 정책 항목에 없다."])

    def test_filters_broad_out_of_scope_security_finding(self):
        report = normalize_dev_qa_review(
            {
                "agent": "Development QA Review Agent",
                "score": 80,
                "verdict": "보완 필요",
                "summary": "검수 완료",
                "development_findings": [
                    {
                        "perspective": "development",
                        "priority": "P2",
                        "action_type": "add",
                        "severity": "major",
                        "title": "OWASP 취약점 점검 기준 추가",
                        "target_location": "전체 문서",
                        "current_content": "",
                        "desired_change": "OWASP 취약점 점검 기준을 추가한다.",
                        "detail": "보안 강화를 위해 필요하다.",
                        "recommendation": "보안 정책을 수립한다.",
                    },
                    {
                        "perspective": "development",
                        "priority": "P2",
                        "action_type": "add",
                        "severity": "major",
                        "title": "인증번호 유효시간 기준 추가",
                        "target_location": "6. 정책 정의 > PG-ABC-AUTH-001",
                        "current_content": "",
                        "desired_change": "인증번호 유효시간은 3분으로 한다.",
                        "detail": "정책 판단값이 필요하다.",
                        "recommendation": "정책 항목을 추가한다.",
                    },
                ],
                "qa_findings": [],
                "coverage_checks": [],
                "recommended_actions": [],
                "evidence_gaps": [],
            }
        )
        self.assertEqual(len(report["development_findings"]), 1)
        self.assertEqual(report["development_findings"][0]["title"], "인증번호 유효시간 기준 추가")


if __name__ == "__main__":
    unittest.main()
