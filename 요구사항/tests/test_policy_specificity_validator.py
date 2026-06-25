from src.validator import policy_detail_has_decision_criteria, policy_detail_quality_dimensions, validate_policy_specificity


def test_policy_specificity_flags_details_without_decision_criteria():
    spec = {
        "policy_details": [
            {
                "id": f"PI-TST-{index:03d}",
                "policy_id": "PG-TST-001",
                "name": f"업무 처리 기준 {index}",
                "content": "업무를 원활하게 처리한다.",
            }
            for index in range(1, 9)
        ]
    }

    errors = validate_policy_specificity(spec)

    assert any("실제 판단 기준" in error for error in errors)


def test_policy_specificity_accepts_operational_values_and_conditions():
    spec = {
        "policy_details": [
            {
                "id": "PI-TST-001",
                "policy_id": "PG-TST-001",
                "name": "인증 시도 제한 기준",
                "content": "인증 번호 입력은 최대 5회까지 허용하고, 초과 시 10분 동안 재시도를 제한한다.",
            },
            {
                "id": "PI-TST-002",
                "policy_id": "PG-TST-001",
                "name": "이력 저장 기준",
                "content": "처리 완료 이력은 고객 고지 후 30일 이상 저장한다.",
            },
        ]
    }

    assert validate_policy_specificity(spec) == []
    assert policy_detail_has_decision_criteria(spec["policy_details"][0])
    assert "count_limit" in policy_detail_quality_dimensions(spec["policy_details"][0])
    assert "history_rule" in policy_detail_quality_dimensions(spec["policy_details"][1])


def test_policy_specificity_rejects_condition_like_generic_sentence():
    detail = {
        "id": "PI-TST-001",
        "policy_id": "PG-TST-001",
        "name": "상태별 처리 기준",
        "content": "고객 상태에 따라 적절히 처리한다.",
    }

    assert not policy_detail_has_decision_criteria(detail)


def test_policy_specificity_flags_repeated_low_density_patterns():
    spec = {
        "policy_details": [
            {
                "id": f"PI-TST-{index:03d}",
                "policy_id": "PG-TST-001",
                "name": f"고지 저장 기준 {index}",
                "content": "고객에게 처리 결과를 안내하고 이력을 저장한다.",
            }
            for index in range(1, 17)
        ]
    }

    errors = validate_policy_specificity(spec)

    assert any("같은 패턴으로 반복" in error for error in errors)
