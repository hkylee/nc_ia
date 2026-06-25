from src.orchestrator import (
    build_repair_controller_event,
    feedback_fingerprints,
    record_density_profile,
    repair_controller_feedback_item,
    should_handoff_stagnant_stage,
)


class _Agent:
    def __init__(self, chapter_key: str):
        self.chapter_key = chapter_key
        self.display_name = f"{chapter_key.title()} Agent"


class _Stage:
    def __init__(self, chapter_key: str):
        self.agent = _Agent(chapter_key)
        self.key = chapter_key
        self.name = chapter_key


def test_hard_gate_stagnation_handoffs_before_extra_retry():
    assert should_handoff_stagnant_stage(_Stage("usecases"), attempt=3, max_loops=4, stagnant_attempts=2)


def test_log_only_stage_never_uses_stagnation_handoff():
    assert not should_handoff_stagnant_stage(
        _Stage("usecase_diagram"), attempt=3, max_loops=4, stagnant_attempts=2
    )


def test_stagnation_handoff_does_not_replace_max_loop_handoff():
    assert not should_handoff_stagnant_stage(_Stage("state"), attempt=4, max_loops=4, stagnant_attempts=3)


def test_feedback_fingerprint_detects_repeated_finding_with_reworded_detail():
    first = {
        "target_path": "usecases[UC-001].description",
        "category": "정합성",
        "title": "유즈케이스 목적 불명확",
        "detail": "목적이 약합니다.",
    }
    second = {
        "target_path": "usecases[UC-001].description",
        "category": "정합성",
        "title": "유즈케이스 목적 불명확",
        "detail": "목적과 완료 상태가 불분명합니다.",
    }

    assert feedback_fingerprints([first]) == feedback_fingerprints([second])


def test_repair_controller_emits_regression_feedback():
    stage = _Stage("usecases")
    event = build_repair_controller_event(
        stage=stage,
        attempt=2,
        current_score=72,
        best_score=80,
        stagnant_attempts=1,
        repeated_finding_count=0,
        feedback_count=2,
    )

    assert event is not None
    assert event["decision"] == "score_regression_discard_candidate"
    feedback = repair_controller_feedback_item(stage, event)
    assert feedback["priority_tier"] == "P1"
    assert feedback["failure_type"] == "score_regression_discard_candidate"


def test_repair_controller_ignores_first_attempt():
    stage = _Stage("state")

    assert (
        build_repair_controller_event(
            stage=stage,
            attempt=1,
            current_score=70,
            best_score=70,
            stagnant_attempts=0,
            repeated_finding_count=2,
            feedback_count=2,
        )
        is None
    )


def test_record_density_profile_keeps_runtime_density_visible_in_final_spec():
    spec = {"meta": {}}
    target_spec = {
        "density_profile": {
            "level": "complex",
            "structural_requirement_limit": 4,
            "requirement_policy_limit": 28,
        }
    }

    record_density_profile(spec, target_spec)

    assert spec["density_profile"]["level"] == "complex"
    assert spec["meta"]["density_profile"]["requirement_policy_limit"] == 28
