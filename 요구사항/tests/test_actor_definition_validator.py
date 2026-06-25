from src.validator import validate_stage_critical


def base_actor_spec(actors):
    return {
        "meta": {"business_code": "TST"},
        "history": [],
        "overview": {"scope": [], "principles": []},
        "terms": [],
        "actors": actors,
        "usecases": [],
        "states": [],
        "state_transitions": [],
        "processes": [],
        "process_details": [],
        "functions": [],
        "function_details": [],
        "policy_groups": [],
        "policy_details": [],
        "final_check": [],
    }


def test_validator_rejects_customer_condition_as_actor():
    result = validate_stage_critical(
        base_actor_spec([{"id": "ACT-TST-001", "name": "비로그인 고객", "description": "비로그인 상태 고객"}]),
        business_code="TST",
        scope="actors",
    )

    assert not result.ok
    assert any("고객 상태" in error or "권한 조건" in error for error in result.errors)


def test_validator_rejects_detailed_operator_and_system_actors():
    result = validate_stage_critical(
        base_actor_spec(
            [
                {"id": "ACT-TST-001", "name": "고객", "description": "고객"},
                {"id": "ACT-TST-002", "name": "상품 운영자", "description": "상품 운영"},
                {"id": "ACT-TST-003", "name": "AI 검색 엔진", "description": "검색 후보 생성"},
            ]
        ),
        business_code="TST",
        scope="actors",
    )

    assert not result.ok
    assert any("상품 운영자" in error for error in result.errors)
    assert any("AI 검색 엔진" in error for error in result.errors)


def test_validator_rejects_composite_human_actor_name():
    result = validate_stage_critical(
        base_actor_spec(
            [
                {"id": "ACT-TST-001", "name": "고객", "description": "고객"},
                {"id": "ACT-TST-002", "name": "법정대리인/대리인", "description": "대리 권한을 확인한다."},
            ]
        ),
        business_code="TST",
        scope="actors",
    )

    assert not result.ok
    assert any("복합 액터" in error or "묶은 복합" in error for error in result.errors)


def test_validator_allows_consolidated_actor_set():
    result = validate_stage_critical(
        base_actor_spec(
            [
                {"id": "ACT-TST-001", "name": "고객", "description": "업무를 요청하고 결과를 확인한다."},
                {"id": "ACT-TST-002", "name": "운영자", "description": "기준과 예외를 관리한다."},
                {"id": "ACT-TST-003", "name": "상담사", "description": "상담 전환 문맥을 이어받아 응대한다."},
                {"id": "ACT-TST-004", "name": "채널 업무 시스템", "description": "요청 전달과 상태·이력 반영을 담당한다."},
                {"id": "ACT-TST-005", "name": "상품·BSS 연계 시스템", "description": "상품 기준과 고객 조건 판정을 회신한다."},
            ]
        ),
        business_code="TST",
        scope="actors",
    )

    assert result.ok
