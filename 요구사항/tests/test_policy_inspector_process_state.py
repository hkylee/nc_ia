from src.policy_inspector import check_process_state_name_drift


def test_process_state_drift_ignores_approved_state_list_fragments():
    findings = check_process_state_name_drift(
        [
            {
                "id": "PR-MBR-001",
                "description": "고객이 인증을 진행하고 인증 미완료는 인증·동의 필요, 인증기관 거절은 인증 실패로 종료한다.",
            }
        ],
        {"인증·동의 필요", "인증 실패", "처리 보류"},
    )

    assert findings == []


def test_process_state_drift_flags_unapproved_terminal_state_phrase():
    findings = check_process_state_name_drift(
        [
            {
                "id": "PR-MBR-001",
                "description": "고객 요청이 접수되면 별도 검토 필요 상태로 전환한다.",
            }
        ],
        {"인증·동의 필요", "인증 실패", "처리 보류"},
    )

    assert findings
    assert findings[0].title == "프로세스 설명의 비승인 상태명 의심"
