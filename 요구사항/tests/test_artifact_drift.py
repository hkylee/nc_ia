import json
from pathlib import Path

from src.artifact_drift import evaluate_policy_artifact_drift
from src import web_app


def test_artifact_drift_passes_synced_outputs(tmp_path: Path):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    html_path = output / "NC_테스트_정책서_간소화_v0.1.html"
    html_path.write_text(
        """
        <html><body>
        ACT-TST-CUS-001 US-TST-001 ST-TST-001 PR-TST-001 FN-TST-001 PG-TST-001 PI-TST-001-01
        </body></html>
        """,
        encoding="utf-8",
    )
    spec = {
        "meta": {"topic": "테스트", "topic_slug": "테스트", "version": "v0.1", "requirements_count": 1},
        "actors": [{"id": "ACT-TST-CUS-001"}],
        "usecases": [{"id": "US-TST-001"}],
        "states": [{"id": "ST-TST-001"}],
        "processes": [{"id": "PR-TST-001"}],
        "functions": [{"id": "FN-TST-001"}],
        "policy_groups": [{"id": "PG-TST-001"}],
        "policy_details": [{"id": "PI-TST-001-01", "policy_id": "PG-TST-001"}],
        "trace_matrix": [{"requirement_id": "REQ-1", "process_ids": ["PR-TST-001"]}],
    }
    (output / "NC_테스트_정책서_간소화_v0.1_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (output / "테스트_policy_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (output / "NC_테스트_정책서_간소화_v0.1_전체업무흐름도.bpmn").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:task id="Task_PR-TST-001" name="PR-TST-001 테스트"/></bpmn:definitions>',
        encoding="utf-8",
    )

    report = evaluate_policy_artifact_drift(html_path, output_root=output, reports_root=reports)

    assert report["status"] == "pass"
    assert report["passed"] is True


def test_artifact_drift_flags_missing_bpmn_and_trace(tmp_path: Path):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    html_path = output / "NC_테스트_정책서_간소화_v0.1.html"
    html_path.write_text("<html><body>ACT-TST-CUS-001 US-TST-001</body></html>", encoding="utf-8")
    spec = {
        "meta": {"topic": "테스트", "topic_slug": "테스트", "version": "v0.1", "requirements_count": 2},
        "actors": [{"id": "ACT-TST-CUS-001"}],
        "usecases": [{"id": "US-TST-001"}],
        "processes": [{"id": "PR-TST-001"}],
    }
    (output / "NC_테스트_정책서_간소화_v0.1_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    report = evaluate_policy_artifact_drift(html_path, output_root=output, reports_root=reports)
    issue_ids = {item["id"] for item in report["issues"]}

    assert report["status"] == "fail"
    assert "DRIFT-BPMN-MISSING" in issue_ids
    assert "DRIFT-TRACE-MISSING" in issue_ids


def test_artifact_drift_skips_topic_spec_latest_warning_for_old_versions(tmp_path: Path):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    old_html = output / "NC_테스트_정책서_간소화_v0.10.html"
    latest_html = output / "NC_테스트_정책서_간소화_v0.11.html"
    old_html.write_text("<html><body>PR-TST-001</body></html>", encoding="utf-8")
    latest_html.write_text("<html><body>PR-TST-001</body></html>", encoding="utf-8")
    spec = {
        "meta": {"topic": "테스트", "topic_slug": "테스트", "version": "v0.10", "requirements_count": 0},
        "processes": [{"id": "PR-TST-001"}],
    }
    latest_spec = {**spec, "meta": {**spec["meta"], "version": "v0.11"}}
    (output / "NC_테스트_정책서_간소화_v0.10_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (output / "테스트_policy_spec.json").write_text(json.dumps(latest_spec, ensure_ascii=False), encoding="utf-8")
    (output / "NC_테스트_정책서_간소화_v0.10_전체업무흐름도.bpmn").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:task id="Task_PR-TST-001" name="PR-TST-001 테스트"/></bpmn:definitions>',
        encoding="utf-8",
    )

    report = evaluate_policy_artifact_drift(old_html, output_root=output, reports_root=reports)
    issue_ids = {item["id"] for item in report["issues"]}

    assert "DRIFT-TOPIC-SPEC-LATEST" not in issue_ids


def test_artifact_drift_skips_topic_spec_latest_warning_for_other_template(tmp_path: Path):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    full_html = output / "NC_테스트_정책서_Full_v0.11.html"
    full_html.write_text("<html><body>PR-TST-001</body></html>", encoding="utf-8")
    full_spec = {
        "meta": {"topic": "테스트", "topic_slug": "테스트", "version": "v0.11", "template_type": "full", "requirements_count": 0},
        "processes": [{"id": "PR-TST-001"}],
    }
    simple_topic_spec = {
        "meta": {"topic": "테스트", "topic_slug": "테스트", "version": "v0.19", "template_type": "simple", "requirements_count": 0},
        "processes": [{"id": "PR-TST-001"}],
    }
    (output / "NC_테스트_정책서_Full_v0.11_spec.json").write_text(json.dumps(full_spec, ensure_ascii=False), encoding="utf-8")
    (output / "테스트_policy_spec.json").write_text(json.dumps(simple_topic_spec, ensure_ascii=False), encoding="utf-8")
    (output / "NC_테스트_정책서_Full_v0.11_전체업무흐름도.bpmn").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:task id="Task_PR-TST-001" name="PR-TST-001 테스트"/></bpmn:definitions>',
        encoding="utf-8",
    )

    report = evaluate_policy_artifact_drift(full_html, output_root=output, reports_root=reports)
    issue_ids = {item["id"] for item in report["issues"]}

    assert "DRIFT-TOPIC-SPEC-LATEST" not in issue_ids


def test_artifact_sync_repair_regenerates_sidecar_outputs(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", output)
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", reports)
    monkeypatch.setattr(web_app, "LOCK_DIR", output / ".locks")

    source_spec_path = web_app.PROJECT_ROOT / "output" / "상품목록_policy_spec.json"
    spec = json.loads(source_spec_path.read_text(encoding="utf-8"))
    html_name = "NC_상품목록_정책서_간소화_v0.10.html"
    html_path = output / html_name
    html_path.write_text("<html><body>stale artifact</body></html>", encoding="utf-8")
    (output / "NC_상품목록_정책서_간소화_v0.10_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False),
        encoding="utf-8",
    )

    result = web_app.repair_policy_artifact_sync_from_payload({"name": html_name, "author": "Tester"})
    issue_ids = {item["id"] for item in result["after"]["issues"]}

    assert result["after"]["status"] != "fail"
    assert "DRIFT-HTML-SPEC-ID" not in issue_ids
    assert "DRIFT-BPMN-MISSING" not in issue_ids
    assert (output / "NC_상품목록_정책서_간소화_v0.10_전체업무흐름도.bpmn").exists()
    assert (output / "NC_상품목록_정책서_간소화_v0.10_전체업무흐름도_viewer.html").exists()
    assert 'data-bpmn-viewer="true"' in html_path.read_text(encoding="utf-8")


def test_artifact_drift_treats_runtime_html_as_source_of_truth(tmp_path: Path):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    html_path = output / "NC_테스트_정책서_간소화_v0.10.html"
    html_path.write_text("<html><body>사용자 직접 편집 본문</body></html>", encoding="utf-8")
    spec = {
        "meta": {
            "topic": "테스트",
            "topic_slug": "테스트",
            "version": "v0.10",
            "requirements_count": 0,
            "html_runtime_source": True,
            "version_spec_reason": "manual_edit_new_version",
        },
        "actors": [{"id": "ACT-TST-CUS-001"}],
        "usecases": [{"id": "US-TST-001"}],
        "processes": [{"id": "PR-TST-001"}],
    }
    (output / "NC_테스트_정책서_간소화_v0.10_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (output / "NC_테스트_정책서_간소화_v0.10_전체업무흐름도.bpmn").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:task id="Task_PR-TST-001" name="PR-TST-001 테스트"/></bpmn:definitions>',
        encoding="utf-8",
    )

    report = evaluate_policy_artifact_drift(html_path, output_root=output, reports_root=reports)
    issue_ids = {item["id"] for item in report["issues"]}

    assert report["htmlRuntimeSource"] is True
    assert report["status"] == "warn"
    assert "DRIFT-HTML-RUNTIME-SOURCE" in issue_ids
    assert "DRIFT-HTML-SPEC-ID" not in issue_ids


def test_artifact_sync_repair_preserves_runtime_html_source(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", output)
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", reports)
    monkeypatch.setattr(web_app, "LOCK_DIR", output / ".locks")

    html_name = "NC_테스트_정책서_간소화_v0.10.html"
    html_path = output / html_name
    html_path.write_text("<html><body><p>사용자가 직접 저장한 본문</p></body></html>", encoding="utf-8")
    spec = {
        "meta": {
            "topic": "테스트",
            "topic_slug": "테스트",
            "version": "v0.10",
            "requirements_count": 0,
            "html_runtime_source": True,
            "version_spec_reason": "html_upload",
        },
        "processes": [{"id": "PR-TST-001", "name": "테스트 프로세스"}],
    }
    (output / "NC_테스트_정책서_간소화_v0.10_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    result = web_app.repair_policy_artifact_sync_from_payload({"name": html_name, "author": "Tester"})
    repaired_types = {item["type"] for item in result["repaired"]}

    assert result["htmlRuntimeSource"] is True
    assert "html_preserved" in repaired_types
    assert "html" not in repaired_types
    assert "사용자가 직접 저장한 본문" in html_path.read_text(encoding="utf-8")
    assert (output / "NC_테스트_정책서_간소화_v0.10_전체업무흐름도.bpmn").exists()


def test_html_spec_sync_marks_runtime_html_as_synced(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    reports = tmp_path / "reports"
    output.mkdir()
    reports.mkdir()
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", output)
    monkeypatch.setattr(web_app, "RUNTIME_REPORTS_ROOT", reports)
    monkeypatch.setattr(web_app, "REPORTS_DIR", reports)
    monkeypatch.setattr(web_app, "LOCK_DIR", output / ".locks")

    html_name = "NC_테스트_정책서_간소화_v0.10.html"
    html_path = output / html_name
    html_path.write_text(
        "<html><body><h2>1. 개요</h2><p>사용자가 직접 저장한 본문</p></body></html>",
        encoding="utf-8",
    )
    spec = {
        "meta": {
            "topic": "테스트",
            "topic_slug": "테스트",
            "version": "v0.10",
            "requirements_count": 0,
            "html_runtime_source": True,
            "spec_sync_needed": True,
            "version_spec_reason": "manual_edit_new_version",
        },
        "processes": [{"id": "PR-TST-001", "name": "테스트 프로세스"}],
    }
    (output / "NC_테스트_정책서_간소화_v0.10_spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    result = web_app.sync_policy_spec_from_runtime_html(html_path, author="Tester")
    updated = json.loads((output / "NC_테스트_정책서_간소화_v0.10_spec.json").read_text(encoding="utf-8"))
    report = evaluate_policy_artifact_drift(html_path, output_root=output, reports_root=reports)
    issue_ids = {item["id"] for item in report["issues"]}

    assert result["status"] == "synced"
    assert updated["meta"]["spec_sync_needed"] is False
    assert updated["meta"]["html_spec_sync_status"] == "synced"
    assert updated["meta"]["html_spec_sync_content_hash"] == web_app.document_content_hash(html_path.read_text(encoding="utf-8"))
    assert updated["html_runtime_snapshot"]["html_text_chars"] > 0
    assert report["htmlSpecSyncNeeded"] is False
    assert "DRIFT-HTML-RUNTIME-SOURCE" not in issue_ids


def test_latest_policy_for_topic_ignores_bpmn_viewer_html(tmp_path: Path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    policy_path = output / "NC_상품목록_정책서_간소화_v0.10.html"
    legacy_same_sequence_path = output / "NC_상품목록_정책서_간소화_v0.2.html"
    newer_policy_path = output / "NC_상품목록_정책서_간소화_v0.11.html"
    viewer_path = output / "NC_상품목록_정책서_간소화_v0.10_전체업무흐름도_viewer.html"
    policy_path.write_text("<html><body>policy</body></html>", encoding="utf-8")
    legacy_same_sequence_path.write_text("<html><body>legacy policy</body></html>", encoding="utf-8")
    newer_policy_path.write_text("<html><body>newer policy</body></html>", encoding="utf-8")
    viewer_path.write_text("<html><body>viewer</body></html>", encoding="utf-8")
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", output)

    assert web_app.latest_policy_for_topic("상품목록", "simple") == newer_policy_path
