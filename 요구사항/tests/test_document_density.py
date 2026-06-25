from types import SimpleNamespace

from src.chapter_agents import AgentRuntime, ensure_process_usecase_coverage
from src.document_density import build_density_profile, process_minimum_for_usecase


def requirement(index: int, text: str):
    return SimpleNamespace(
        detail_name=f"요구사항 {index:03d}",
        detail_description=text,
        requirement_type="필수",
    )


def context(requirements, references=(), template_type="simple"):
    return SimpleNamespace(
        template_type=template_type,
        requirements=list(requirements),
        references=list(references),
    )


def test_density_profile_raises_limits_for_complex_requirement_sets():
    requirements = [
        requirement(
            index,
            "고객 상태 전이, BSS 원장 반영, 인증, 예외, 알림, 이력 저장, 제한 조건을 함께 정의한다.",
        )
        for index in range(95)
    ]

    profile = build_density_profile(context(requirements))

    assert profile.level in {"high", "complex"}
    assert profile.structural_requirement_limit >= 3
    assert profile.requirement_policy_limit >= 22
    assert profile.max_usecases_y >= 7
    assert profile.max_states >= 14


def test_process_minimum_never_falls_back_to_one_process_per_y_usecase():
    low_profile = build_density_profile(context([requirement(1, "고객이 기본 정보를 확인한다.")]))
    high_profile = build_density_profile(
        context(
            [
                requirement(
                    index,
                    "고객 상태 전이, BSS 원장 반영, 인증, 예외, 알림, 이력 저장, 제한 조건을 함께 정의한다.",
                )
                for index in range(95)
            ]
        )
    )

    assert process_minimum_for_usecase("고객", "정보 확인", low_profile) >= 2
    assert process_minimum_for_usecase("운영자", "운영 기준 관리", low_profile) >= 2
    assert process_minimum_for_usecase("고객", "업무 처리", low_profile) >= 2
    assert process_minimum_for_usecase("고객", "업무 처리", high_profile) > process_minimum_for_usecase(
        "고객", "업무 처리", low_profile
    )


def test_process_coverage_generation_uses_dynamic_density_floor():
    high_profile = build_density_profile(
        context(
            [
                requirement(
                    index,
                    "고객 상태 전이, BSS 원장 반영, 인증, 예외, 알림, 이력 저장, 제한 조건을 함께 정의한다.",
                )
                for index in range(95)
            ]
        )
    )
    spec = {
        "meta": {"business_code": "DEN", "topic": "복합 업무"},
        "usecases": [
            {
                "id": "US-DEN-CS-001",
                "actor": "고객",
                "name": "복합 업무 처리",
                "description": "고객이 복합 업무를 완료한다.",
                "process_target": "Y",
            }
        ],
        "processes": [],
    }
    runtime = AgentRuntime(
        ctx=SimpleNamespace(),
        target_spec={"density_profile": high_profile.to_dict()},
        learning={},
        guideline={},
        evidence_store=None,
        authoring_blueprint={},
        llm_client=None,
    )

    ensure_process_usecase_coverage(spec, runtime)

    assert len(spec["processes"]) == process_minimum_for_usecase("고객", "복합 업무 처리", high_profile)
    assert 1 < len(spec["processes"]) <= 3
