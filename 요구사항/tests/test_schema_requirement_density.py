from types import SimpleNamespace

from src.schema import build_policy_spec


def test_requirements_are_converted_to_policy_item_candidates_not_copied():
    requirement = SimpleNamespace(
        detail_name="회원탈퇴 단계형 처리",
        detail_description="고객이 회원탈퇴 조건을 확인하고 인증 후 탈퇴 요청 결과를 안내받는다.",
    )
    ctx = SimpleNamespace(
        topic="회원가입 · 회원탈퇴",
        topic_slug="회원가입회원탈퇴",
        business_code="MBR",
        template_type="simple",
        status="draft",
        version="v0.1",
        author="test",
        today="2026-05-05",
        brief="",
        requirements=[requirement],
        references=[],
    )

    spec = build_policy_spec(ctx)

    requirement_details = [item for item in spec["policy_details"] if item["id"].startswith("PI-MBR-RQCOV-")]
    assert requirement_details
    assert requirement_details[0]["name"] != "회원탈퇴 단계형 처리"
    assert "해지·취소" in requirement_details[0]["name"]
    assert "회원탈퇴 단계형 처리" not in requirement_details[0]["name"]
    assert "고객이 회원탈퇴 조건을 확인하고 인증 후 탈퇴 요청 결과를 안내받는다." not in requirement_details[0]["content"]
    assert "회원탈퇴 단계형 처리" not in requirement_details[0]["content"]
    assert "인증 필요 여부" in requirement_details[0]["content"]
    assert "처리 가능 상태" in requirement_details[0]["content"]
    assert "제한 사유" in requirement_details[0]["content"]

    requirement_processes = [item for item in spec["processes"] if "-RQCOV-" in item["id"]]
    requirement_functions = [item for item in spec["functions"] if item["id"].startswith("FN-MBR-RQCOV-")]

    assert requirement_processes
    assert requirement_functions
    assert not [item for item in spec["usecases"] if item["id"].startswith("US-MBR-RQCOV-")]
    assert requirement_processes[0]["id"] == "PR-MBR-CS-003-RQCOV-001"
    assert requirement_processes[0]["usecase_id"] == "US-MBR-CS-003"
    assert requirement_functions[0]["process_id"] == "PR-MBR-CS-003-RQCOV-001"
    assert "회원탈퇴 단계형 처리" not in requirement_processes[0]["name"]
    assert "회원탈퇴 단계형 처리" not in requirement_functions[0]["name"]
    assert "고객이 회원탈퇴 조건을 확인하고 인증 후 탈퇴 요청 결과를 안내받는다." not in requirement_processes[0]["description"]
    assert "고객이 회원탈퇴 조건을 확인하고 인증 후 탈퇴 요청 결과를 안내받는다." not in requirement_functions[0]["description"]


def test_complex_requirements_expand_coverage_without_creating_requirement_usecases():
    requirements = [
        SimpleNamespace(
            detail_name=f"복합 요구사항 {index:03d}",
            detail_description="고객 상태 전이, BSS 원장 반영, 인증, 예외, 알림, 이력 저장, 제한 조건을 함께 정의한다.",
        )
        for index in range(95)
    ]
    ctx = SimpleNamespace(
        topic="복합 업무",
        topic_slug="복합업무",
        business_code="CMP",
        template_type="simple",
        status="draft",
        version="v0.1",
        author="test",
        today="2026-05-05",
        brief="",
        requirements=requirements,
        references=[],
    )

    spec = build_policy_spec(ctx)
    density = spec["density_profile"]

    assert density["level"] in {"high", "complex"}
    assert density["structural_requirement_limit"] >= 3
    assert density["requirement_policy_limit"] >= 22

    requirement_processes = [item for item in spec["processes"] if "-RQCOV-" in item["id"]]
    requirement_functions = [item for item in spec["functions"] if item["id"].startswith("FN-CMP-RQCOV-")]
    requirement_policy_details = [item for item in spec["policy_details"] if item["id"].startswith("PI-CMP-RQCOV-")]

    assert 1 <= len(requirement_processes) <= density["structural_requirement_limit"]
    assert len(requirement_functions) >= len(requirement_processes) * 2
    assert len(requirement_policy_details) == density["requirement_policy_limit"]
    assert not [item for item in spec["usecases"] if "-RQCOV-" in item["id"]]
    assert len({item["name"] for item in requirement_processes}) == len(requirement_processes)
