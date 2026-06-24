from types import SimpleNamespace

from src.policy_agent import apply_final_integration_pass


def test_final_integration_pass_normalizes_process_reference_labels():
    spec = {
        "meta": {"topic": "테스트"},
        "processes": [
            {
                "id": "PR-TST-001",
                "name": "처리 절차",
                "related_functions": ["FN-TST-001"],
                "related_policies": ["PG-TST-001"],
            }
        ],
            "functions": [{"id": "FN-TST-001", "name": "대상 검증 기능", "process_ids": ["PR-TST-001"]}],
        "policy_groups": [{"id": "PG-TST-001", "name": "검증 정책"}],
        "policy_details": [
            {
                "id": "PI-TST-001",
                "policy_id": "PG-TST-001",
                "name": "검증 허용 기준",
                "content": "본인 인증이 완료된 고객에게만 검증을 허용한다.",
            }
        ],
    }

    integrated = apply_final_integration_pass(spec, SimpleNamespace(topic="테스트"), "unit")

    assert integrated["processes"][0]["related_functions"] == ["FN-TST-001 대상 검증 기능"]
    assert integrated["processes"][0]["related_policies"] == ["PG-TST-001 검증 정책"]
    assert integrated["meta"]["final_integration_runs"][0]["status"] == "ok"


def test_final_integration_pass_records_weak_policy_dimensions_without_rewriting_content():
    spec = {
        "meta": {"topic": "테스트"},
        "processes": [],
        "functions": [],
        "policy_groups": [{"id": "PG-TST-001", "name": "업무 정책"}],
        "policy_details": [
            {
                "id": "PI-TST-001",
                "policy_id": "PG-TST-001",
                "name": "업무 처리 기준",
                "content": "업무를 원활하게 처리한다.",
            }
        ],
    }

    integrated = apply_final_integration_pass(spec, SimpleNamespace(topic="테스트"), "unit")

    run = integrated["meta"]["final_integration_runs"][0]
    assert run["status"] == "watch"
    assert run["weak_policy_detail_ids"] == ["PI-TST-001"]
    assert run["manual_patch_candidate_count"] == 1
    assert run["manual_patch_candidates"][0]["type"] == "weak_policy_detail_dimensions"
    assert run["manual_patch_candidates"][0]["safe_auto_fix"] is False
    assert integrated["policy_details"][0]["content"] == "업무를 원활하게 처리한다."


def test_final_integration_pass_records_link_gaps_without_guessing_new_links():
    spec = {
        "meta": {"topic": "테스트"},
        "processes": [
            {
                "id": "PR-TST-001",
                "name": "처리 절차",
                "related_functions": [],
                "related_policies": [],
            }
        ],
        "functions": [{"id": "FN-TST-001", "name": "대상 검증 기능", "process_id": "PR-TST-MISSING"}],
        "policy_groups": [{"id": "PG-TST-001", "name": "검증 정책"}],
        "policy_details": [
            {
                "id": "PI-TST-001",
                "policy_id": "PG-TST-MISSING",
                "name": "검증 허용 기준",
                "content": "본인 인증이 완료된 고객에게만 검증을 허용한다.",
            }
        ],
    }

    integrated = apply_final_integration_pass(spec, SimpleNamespace(topic="테스트"), "unit")

    run = integrated["meta"]["final_integration_runs"][0]
    candidate_types = {item["type"] for item in run["manual_patch_candidates"]}
    assert run["status"] == "watch"
    assert "process_missing_related_functions" in candidate_types
    assert "process_missing_related_policies" in candidate_types
    assert "function_unknown_process_id" in candidate_types
    assert "policy_detail_unknown_policy_group" in candidate_types
    assert integrated["processes"][0]["related_functions"] == []
    assert integrated["processes"][0]["related_policies"] == []
    assert integrated["functions"][0]["process_id"] == "PR-TST-MISSING"
    assert integrated["policy_details"][0]["policy_id"] == "PG-TST-MISSING"
