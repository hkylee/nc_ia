import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src import web_app


def test_describe_policy_file_backfills_json_download_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(web_app, "OUTPUT_ROOT", tmp_path)

    policy_path = tmp_path / "NC_AI검색_정책서_간소화_v0.1.html"
    policy_path.write_text("<html><body>AI 검색 정책서</body></html>", encoding="utf-8")
    (tmp_path / "AI검색_policy_spec.json").write_text(
        json.dumps(
            {
                "meta": {"topic": "AI 검색"},
                "overview": {"scope": ["AI 검색 범위"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    described = web_app.describe_policy_file(policy_path)

    assert described["json"]["name"] == "NC_AI검색_정책서_간소화_v0.1_spec.json"
    assert described["json"]["url"] == "/output/NC_AI%EA%B2%80%EC%83%89_%EC%A0%95%EC%B1%85%EC%84%9C_%EA%B0%84%EC%86%8C%ED%99%94_v0.1_spec.json"
    version_spec = tmp_path / described["json"]["name"]
    assert version_spec.exists()
    payload = json.loads(version_spec.read_text(encoding="utf-8"))
    assert payload["meta"]["version"] == "v0.1"
    assert payload["meta"]["version_spec_reason"] == "json_download_backfill"
