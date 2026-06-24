import json

from src.eval_harness import run_eval_harness


def test_eval_harness_compares_scenario_expectations_without_llm(tmp_path):
    scenarios = tmp_path / "reports" / "eval" / "scenarios"
    output_root = tmp_path / "output"
    reports_root = tmp_path / "reports"
    checkpoints = output_root / "checkpoints"
    inspections = reports_root / "inspections"
    scenarios.mkdir(parents=True)
    checkpoints.mkdir(parents=True)
    inspections.mkdir(parents=True)

    (scenarios / "sample.json").write_text(
        json.dumps(
            {
                "id": "sample-policy",
                "topic": "테스트",
                "expectations": {
                    "min_counts": {"policy_details": 2, "functions": 1},
                    "max_validation_errors": 0,
                    "max_critical_errors": 0,
                    "min_latest_inspection_score": 85,
                    "min_context_quality_score": 80,
                    "max_context_gap_runs": 0,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (checkpoints / "NC_테스트_정책서_간소화_v0.1_latest_checkpoint.json").write_text(
        json.dumps(
            {
                "checkpoint": {"topic": "테스트", "stage_key": "finalize"},
                "spec": {
                    "meta": {
                        "topic": "테스트",
                        "business_code": "TST",
                        "usecase_diagram": {"lines": ["[고객] -> (업무 확인)"]},
                        "context_pack_runs": [
                            {
                                "chapter": "process",
                                "context_quality_score": 88,
                                "context_quality_status": "good",
                                "required_kind_coverage": 1.0,
                                "evidence_gap_count": 0,
                                "evidence_ids": ["REQ-001"],
                            }
                        ],
                    },
                    "history": [],
                    "overview": {"scope": [], "principles": []},
                    "terms": [],
                    "actors": [{"id": "ACT-TST-001", "name": "고객"}],
                    "usecases": [{"id": "US-TST-001", "name": "업무 확인", "actor": "고객", "process_target": "Y"}],
                        "states": [
                            {"id": "ST-TST-001", "name": "시작 전", "description": "업무 시작 전 상태이다.", "next_action": "업무 확인을 시작한다."},
                            {"id": "ST-TST-002", "name": "완료", "description": "업무가 완료된 상태이다.", "next_action": "결과를 확인한다."},
                        ],
                    "state_transitions": [
                        {
                            "usecase_ids": ["US-TST-001"],
                            "current_state": "시작 전",
                            "event": "업무 확인",
                            "next_state": "완료",
                            "criteria": "고객이 확인 요청을 완료하면 완료 상태로 전환한다.",
                        }
                    ],
                        "processes": [
                            {
                                "id": "PR-TST-001",
                                "name": "업무 확인 처리",
                                "usecase_id": "US-TST-001",
                                "related_functions": ["FN-TST-001 확인 기능"],
                                "related_policies": ["PG-TST-001 확인 정책"],
                            },
                            {
                                "id": "PR-TST-002",
                                "name": "확인 결과 제공",
                                "usecase_id": "US-TST-001",
                                "related_functions": ["FN-TST-001 확인 기능"],
                                "related_policies": ["PG-TST-001 확인 정책"],
                            }
                        ],
                        "functions": [
                            {
                                "id": "FN-TST-001",
                                "name": "확인 기능",
                                "process_ids": ["PR-TST-001", "PR-TST-002"],
                            "details": ["대상 조회", "결과 저장"],
                        }
                    ],
                    "policy_groups": [
                        {
                            "id": "PG-TST-001",
                            "name": "확인 정책",
                            "description": "확인 기준",
                            "items": ["확인 허용 기준", "이력 저장 기준"],
                        }
                    ],
                    "policy_details": [
                        {"id": "PI-TST-001", "policy_id": "PG-TST-001", "name": "확인 허용 기준", "content": "고객 본인 인증이 완료된 경우에만 확인을 허용한다."},
                        {"id": "PI-TST-002", "policy_id": "PG-TST-001", "name": "이력 저장 기준", "content": "확인 완료 이력은 30일 이상 저장한다."},
                    ],
                    "final_check": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (inspections / "NC_테스트_정책서_간소화_v0.1.html_final_inspection.json").write_text(
        json.dumps({"status": "pass", "score": 91, "scope": "final", "findings": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    report = run_eval_harness(scenarios_root=scenarios, output_root=output_root, reports_root=reports_root)

    assert report["summary"]["scenarioCount"] == 1
    assert report["summary"]["passed"] == 1
    assert report["results"][0]["status"] == "pass"


def test_eval_harness_reports_missing_scenarios(tmp_path):
    report = run_eval_harness(
        scenarios_root=tmp_path / "reports" / "eval" / "scenarios",
        output_root=tmp_path / "output",
        reports_root=tmp_path / "reports",
    )

    assert report["summary"]["scenarioCount"] == 0
    assert report["recommendations"]
