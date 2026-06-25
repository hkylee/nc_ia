from src.policy_inspector import (
    calculate_score_details,
    check_internal_code_leakage,
    check_sample_parity,
    check_topic_required_axes,
    sample_matches_topic,
    topic_axis_specs,
)


def test_short_topic_does_not_match_unrelated_sample_body_text():
    sample_html = """
    <html><head><title>회원가입 정책서</title></head>
    <body><h1>회원가입 · 회원탈퇴 정책서</h1><p>추천 조건은 다른 장의 예시로만 등장한다.</p></body></html>
    """

    assert not sample_matches_topic(sample_html, "추천")


def test_topic_matches_sample_title_anchor():
    sample_html = """
    <html><head><title>추천 정책서</title></head>
    <body><h1>추천 정책서</h1><p>고객 추천 업무를 정의한다.</p></body></html>
    """

    assert sample_matches_topic(sample_html, "추천")


def test_sample_parity_count_gaps_are_non_blocking_metric_observations():
    metrics = {
        "body_bytes": 140_000,
        "text_chars": 48_000,
        "table_count": 58,
        "policy_item_count": 117,
        "usecase_distinct_count": 8,
        "process_distinct_count": 31,
        "function_distinct_count": 27,
        "policy_group_distinct_count": 22,
        "sample_topic_match_count": 1,
        "sample_min_body_bytes": 235_000,
        "sample_max_text_chars": 62_000,
        "sample_max_usecase_distinct_count": 13,
        "sample_max_process_distinct_count": 22,
        "sample_max_function_distinct_count": 29,
        "sample_max_policy_group_distinct_count": 44,
        "sample_max_policy_item_count": 475,
    }
    findings = check_sample_parity(metrics, "simple", "full", "회원가입 · 회원탈퇴")
    count_findings = [
        finding
        for finding in findings
        if finding.title in {"샘플 대비 정책 그룹 부족", "샘플 대비 정책 상세 부족"}
    ]

    assert count_findings
    assert {finding.severity for finding in count_findings} == {"warn"}
    assert all(finding.is_metric_observation for finding in count_findings)
    score = calculate_score_details(count_findings)
    assert score["gate_blocker_count"] == 0


def test_topic_axis_specs_treat_underscore_as_display_separator():
    axes = topic_axis_specs("고객센터_FAQ/공지/이용안내")

    assert [axis["label"] for axis in axes] == ["고객센터 FAQ", "공지", "이용안내"]
    assert axes[0]["terms"] == ["고객센터", "faq"]


def test_customer_facing_topic_acronym_is_not_internal_code_leakage():
    body = """
    <h1>고객센터 FAQ·공지·이용안내 정책서</h1>
    <p>고객센터 FAQ·공지·이용안내 업무의 처리 기준을 정의한다.</p>
    <td>POL-FAQ</td><td>문서 ID FAQ</td>
    """
    text = "1. 개요 고객센터 FAQ·공지·이용안내 업무의 처리 기준을 정의한다. 2. 주요 용어"

    findings = check_internal_code_leakage(body, text, "고객센터_FAQ/공지/이용안내", "full")

    assert findings == []


def test_topic_required_axes_match_displayed_faq_topic():
    text = """
    4. 프로세스 정의 고객센터 FAQ 조회 기준을 확인한다.
    공지 노출 조건과 이용안내 연결 기준을 판정한다.
    5. 기능 정의 고객센터 FAQ·공지·이용안내 표시 결과를 구성한다.
    """

    findings = check_topic_required_axes(text, "고객센터_FAQ/공지/이용안내", "full")

    assert findings == []
