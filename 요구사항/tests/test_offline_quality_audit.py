import json

from src.offline_quality_audit import (
    audit_context_pack_runs,
    audit_checkpoints,
    audit_inspections,
    audit_llm_logs,
    checkpoint_scope,
    run_offline_quality_audit,
)


def test_audit_inspections_routes_existing_report_without_llm(tmp_path):
    inspections = tmp_path / "inspections"
    inspections.mkdir()
    (inspections / "NC_테스트_정책서_간소화_v0.1.html_07_process_attempt1_inspection.json").write_text(
        json.dumps(
            {
                "status": "fail",
                "score": 62,
                "scope": "07_process",
                "findings": [
                    {
                        "severity": "warn",
                        "category": "structure",
                        "title": "프로세스 구조 전반 부족",
                        "detail": "프로세스가 기능명 나열로 작성됐다.",
                        "recommendation": "프로세스 섹션을 업무 절차로 재정렬한다.",
                        "target_path": "current_chapter.processes",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    audits = audit_inspections(inspections, min_score=85)

    assert len(audits) == 1
    assert audits[0].remediation_mode == "scoped_full_revision"
    assert audits[0].actionability_issue_count > 0


def test_audit_llm_logs_summarizes_tokens_and_errors(tmp_path):
    log_path = tmp_path / "llm_calls.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps({"event": "request_start", "schema_name": "process_chapter"}),
                json.dumps({"event": "request_success", "schema_name": "process_chapter", "usage": {"total_tokens": 120}}),
                json.dumps({"event": "request_error", "schema_name": "inspector", "error": "temporary network error"}),
            ]
        ),
        encoding="utf-8",
    )

    audit = audit_llm_logs(log_path)

    assert audit.rows == 3
    assert audit.requests == 1
    assert audit.successes == 1
    assert audit.errors == 1
    assert audit.total_tokens == 120
    assert audit.top_errors[0]["error"] == "temporary network error"


def test_run_offline_quality_audit_handles_empty_artifact_dirs(tmp_path):
    output_root = tmp_path / "output"
    reports_root = tmp_path / "reports"
    (output_root / "checkpoints").mkdir(parents=True)
    (reports_root / "inspections").mkdir(parents=True)
    (reports_root / "logs").mkdir(parents=True)

    report = run_offline_quality_audit(output_root=output_root, reports_root=reports_root)

    assert report["summary"]["checkpointCount"] == 0
    assert report["summary"]["inspectionReportCount"] == 0
    assert report["summary"]["contextPackRunCount"] == 0
    assert report["recommendations"]


def test_audit_context_pack_runs_summarizes_quality_scores(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "NC_테스트_정책서_간소화_v0.1_latest_checkpoint.json").write_text(
        json.dumps(
            {
                "checkpoint": {"topic": "테스트", "stage_key": "07_process"},
                "spec": {
                    "meta": {
                        "topic": "테스트",
                        "context_pack_runs": [
                            {
                                "chapter": "process",
                                "context_quality_score": 64,
                                "context_quality_status": "risk",
                                "required_kind_coverage": 0.6,
                                "evidence_gap_count": 2,
                                "evidence_ids": ["REQ-001"],
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    runs = audit_context_pack_runs(checkpoints)

    assert len(runs) == 1
    assert runs[0].chapter == "process"
    assert runs[0].score == 64
    assert runs[0].evidence_gap_count == 2


def test_audit_checkpoints_does_not_flag_future_stage_keys(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    (checkpoints / "NC_테스트_정책서_간소화_v0.1_latest_checkpoint.json").write_text(
        json.dumps(
            {
                "checkpoint": {"topic": "테스트", "stage_key": "08_functions", "stage_name": "functions", "passed": True},
                "spec": {
                    "meta": {"topic": "테스트", "business_code": "TST"},
                    "history": [],
                    "overview": {"scope": [], "principles": []},
                    "terms": [],
                    "actors": [],
                    "usecases": [],
                    "states": [],
                    "state_transitions": [],
                    "processes": [],
                    "functions": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    audits = audit_checkpoints(checkpoints)

    assert len(audits) == 1
    assert audits[0].validation_error_count == 0


def test_checkpoint_scope_prefers_specific_stage_names():
    assert checkpoint_scope({"stage_key": "09_process_detail", "stage_name": "process_detail"}) == "09_process_detail"
    assert checkpoint_scope({"stage_key": "09_function_detail", "stage_name": "function_detail"}) == "09_function_detail"
    assert checkpoint_scope({"stage_key": "09_terms_refinement", "stage_name": "terms_refinement"}) == "09_policies"
