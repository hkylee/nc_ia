from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/ensure_manual_authoring_assets.py"
SPEC = importlib.util.spec_from_file_location("ensure_manual_authoring_assets", SCRIPT_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_ensure_manual_authoring_assets_generates_missing_bpmn(tmp_path: Path):
    spec_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual_spec.json"
    html_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual.html"
    queue_path = tmp_path / "reports/manual_authoring/manual_authoring_queue.json"
    spec_path.parent.mkdir(parents=True)
    queue_path.parent.mkdir(parents=True)
    html_path.write_text("<html><body>테스트</body></html>", encoding="utf-8")
    spec_path.write_text(
        json.dumps(
            {
                "meta": {"topic": "테스트", "business_code": "TST"},
                "usecases": [{"id": "US-TST-001", "name": "테스트 업무"}],
                "processes": [
                    {
                        "id": "PR-TST-001",
                        "usecase_id": "US-TST-001",
                        "name": "테스트 처리",
                        "description": "테스트를 처리한다.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "module_id": "PM-01",
                        "topic": "테스트",
                        "html_path": str(html_path.relative_to(tmp_path)),
                        "spec_path": str(spec_path.relative_to(tmp_path)),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = module.ensure_manual_authoring_assets(queue_path)

    assert result.ok
    assert len(result.generated_bpmn) == 1
    assert len(result.generated_bpmn_viewers) == 1
    assert result.generated_bpmn[0].exists()
    assert result.generated_bpmn_viewers[0].exists()
    updated = json.loads(queue_path.read_text(encoding="utf-8"))
    bpmn_path = tmp_path / updated["items"][0]["bpmn_path"]
    bpmn_viewer_path = tmp_path / updated["items"][0]["bpmn_viewer_path"]
    assert bpmn_path.exists()
    assert bpmn_viewer_path.exists()
    assert updated["items"][0]["bpmn"] == updated["items"][0]["bpmn_path"]
    assert "bpmn.io bpmn-js viewer" in bpmn_viewer_path.read_text(encoding="utf-8")


def test_ensure_manual_authoring_assets_check_mode_reports_missing_bpmn(tmp_path: Path):
    spec_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual_spec.json"
    html_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual.html"
    queue_path = tmp_path / "reports/manual_authoring/manual_authoring_queue.json"
    spec_path.parent.mkdir(parents=True)
    queue_path.parent.mkdir(parents=True)
    html_path.write_text("<html><body>테스트</body></html>", encoding="utf-8")
    spec_path.write_text(json.dumps({"meta": {"business_code": "TST"}}, ensure_ascii=False), encoding="utf-8")
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "module_id": "PM-01",
                        "topic": "테스트",
                        "html_path": str(html_path.relative_to(tmp_path)),
                        "spec_path": str(spec_path.relative_to(tmp_path)),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = module.ensure_manual_authoring_assets(queue_path, repair=False)

    assert not result.ok
    assert not result.generated_bpmn
    assert not result.generated_bpmn_viewers
    assert any("bpmn" in item for item in result.missing)


def test_ensure_manual_authoring_assets_rejects_history_version_tags(tmp_path: Path):
    spec_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual_spec.json"
    html_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual.html"
    bpmn_path = tmp_path / "output/manual_authoring_PM-01/NC_테스트_정책서_간소화_v0.1_manual_전체업무흐름도.bpmn"
    queue_path = tmp_path / "reports/manual_authoring/manual_authoring_queue.json"
    spec_path.parent.mkdir(parents=True)
    queue_path.parent.mkdir(parents=True)
    html_path.write_text("<html><body>테스트</body></html>", encoding="utf-8")
    bpmn_path.write_text('<?xml version="1.0" encoding="UTF-8"?><definitions />', encoding="utf-8")
    spec_path.write_text(
        json.dumps(
            {
                "meta": {"business_code": "TST"},
                "history": [{"version": "v0.1-pm01-quality", "changes": "작업 태그가 버전에 섞인 오류"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    queue_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "module_id": "PM-01",
                        "topic": "테스트",
                        "html_path": str(html_path.relative_to(tmp_path)),
                        "spec_path": str(spec_path.relative_to(tmp_path)),
                        "bpmn_path": str(bpmn_path.relative_to(tmp_path)),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = module.ensure_manual_authoring_assets(queue_path, repair=False)

    assert not result.ok
    assert result.history_version_errors
    assert "v0.1-pm01-quality" in result.history_version_errors[0]
