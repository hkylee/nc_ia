import json
from pathlib import Path

from web_app import (
    reference_seed_manifest_path,
    sync_policy_seed_once,
    sync_seed_directory,
)


def test_reference_html_seed_preserves_runtime_edit(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_file = source / "reference_html" / "ia-analysis.html"
    target_file = target / "reference_html" / "ia-analysis.html"
    source_file.parent.mkdir(parents=True)
    target_file.parent.mkdir(parents=True)
    source_file.write_text("<html><body>repo seed</body></html>", encoding="utf-8")
    target_file.write_text("<html><body>user edit</body></html>", encoding="utf-8")

    sync_seed_directory(source, target)

    assert target_file.read_text(encoding="utf-8") == "<html><body>user edit</body></html>"
    manifest = json.loads(reference_seed_manifest_path(target).read_text(encoding="utf-8"))
    assert manifest["files"]["reference_html/ia-analysis.html"]["status"] == "preserved_runtime_edit"


def test_reference_html_seed_updates_unmodified_prior_seed(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_file = source / "reference_html" / "ia-analysis.html"
    target_file = target / "reference_html" / "ia-analysis.html"
    source_file.parent.mkdir(parents=True)
    target_file.parent.mkdir(parents=True)
    source_file.write_text("<html><body>repo seed v1</body></html>", encoding="utf-8")
    target_file.write_text("<html><body>repo seed v1</body></html>", encoding="utf-8")

    sync_seed_directory(source, target)
    source_file.write_text("<html><body>repo seed v2</body></html>", encoding="utf-8")
    sync_seed_directory(source, target)

    assert target_file.read_text(encoding="utf-8") == "<html><body>repo seed v2</body></html>"


def test_policy_seed_once_does_not_overwrite_existing_runtime_policy(tmp_path: Path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    existing_policy = target / "NC_테스트_정책서_간소화_v0.10.html"
    missing_policy = target / "NC_테스트_정책서_간소화_v0.11.html"
    (source / existing_policy.name).write_text("<html><body>repo policy</body></html>", encoding="utf-8")
    (source / missing_policy.name).write_text("<html><body>new repo policy</body></html>", encoding="utf-8")
    existing_policy.write_text("<html><body>runtime edit</body></html>", encoding="utf-8")

    sync_policy_seed_once(source, target)

    assert existing_policy.read_text(encoding="utf-8") == "<html><body>runtime edit</body></html>"
    assert missing_policy.read_text(encoding="utf-8") == "<html><body>new repo policy</body></html>"
