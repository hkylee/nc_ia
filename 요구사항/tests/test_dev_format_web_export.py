import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import web_app


class DevFormatWebExportTest(unittest.TestCase):
    def test_full_policy_export_creates_artifacts_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            output_root.mkdir()
            source = PROJECT_ROOT / "input" / "samples" / "NC_상품상세담기_정책서_Full_v0.11.html"
            policy_path = output_root / source.name
            shutil.copyfile(source, policy_path)

            with patch.object(web_app, "OUTPUT_ROOT", output_root):
                export = web_app.dev_format_export_from_payload({"name": policy_path.name})

            export_dir = output_root / export["outputDir"]
            zip_path = output_root / export["zipArtifact"]["path"]
            self.assertEqual(export["templateType"], "full")
            self.assertTrue((export_dir / "00_INDEX.md").is_file())
            self.assertTrue((export_dir / "mapping.csv").is_file())
            self.assertTrue((export_dir / "entities.yaml").is_file())
            self.assertTrue(zip_path.is_file())
            self.assertEqual(export["zipArtifact"]["label"], "ZIP 파일")
            self.assertGreater(export["counts"]["usecaseFiles"], 0)
            self.assertGreater(export["counts"]["mappingRows"], 0)
            self.assertEqual(export["warnings"]["blockingCount"], 0)
            zip_tree = export["zipTree"]
            self.assertEqual(zip_tree["rootName"], zip_path.name)
            self.assertEqual(zip_tree["files"], ["00_INDEX.md", "README.md", "mapping.csv", "entities.yaml", "warnings.md"])
            self.assertEqual(zip_tree["groups"]["usecases"]["count"], export["counts"]["usecaseFiles"])
            self.assertEqual(zip_tree["groups"]["diagrams"]["files"], ["bpmn_1.svg", "state_1.svg", "uc_1.svg"])
            with zipfile.ZipFile(zip_path) as archive:
                archive_names = set(archive.namelist())
                self.assertIn("00_INDEX.md", archive_names)
                self.assertIn("mapping.csv", archive_names)
                for file_name in zip_tree["files"]:
                    self.assertIn(file_name, archive_names)
                for file_name in zip_tree["groups"]["diagrams"]["files"]:
                    self.assertIn(f"diagrams/{file_name}", archive_names)
                usecase_members = [
                    name
                    for name in archive_names
                    if name.startswith("usecase_") and name.endswith(".md")
                ]
                self.assertEqual(len(usecase_members), zip_tree["groups"]["usecases"]["count"])

    def test_simple_policy_export_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            output_root.mkdir()
            policy_path = output_root / "NC_테스트_정책서_간소화_v0.1.html"
            policy_path.write_text("<html><body><h1>테스트 정책서</h1></body></html>", encoding="utf-8")

            with patch.object(web_app, "OUTPUT_ROOT", output_root):
                with self.assertRaisesRegex(ValueError, "Full 버전 정책서"):
                    web_app.dev_format_export_from_payload({"name": policy_path.name})

    def test_invalid_policy_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            output_root.mkdir()
            with patch.object(web_app, "OUTPUT_ROOT", output_root):
                with self.assertRaisesRegex(ValueError, "정책서 파일명이 올바르지 않습니다"):
                    web_app.dev_format_export_from_payload({"name": "../NC_테스트_정책서_Full_v0.1.html"})

    def test_warning_summary_treats_unknown_prefix_as_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            warnings_path = Path(tmp) / "warnings.md"
            warnings_path.write_text(
                """
# warnings.md
## Broken cross-refs (참조된 ID가 정의되지 않음) (0건)
## Orphan entities (정의되었지만 어디서도 참조되지 않음) (0건)
## N:N 양방향 불일치 (0건)
## ID 형식 위반 (알려진 접두사 외) (0건)
## 누락 의심 정책 (0건)
## Silent failure 의심 (입력 신호 vs 산출물 비율) (0건)
## Unknown ID prefix (PREFIX_TO_TYPE 미등록) (1건)
## Diagrams (다이어그램 추출 검증) (0건)
""",
                encoding="utf-8",
            )

            summary = web_app.dev_format_warning_summary(warnings_path)

        self.assertEqual(summary["status"], "review")
        self.assertEqual(summary["blockingCount"], 0)
        self.assertEqual(summary["reviewCount"], 1)

    def test_warning_summary_keeps_diagram_notes_out_of_validation_warning_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            warnings_path = Path(tmp) / "warnings.md"
            warnings_path.write_text(
                """
# warnings.md
## Broken cross-refs (참조된 ID가 정의되지 않음) (0건)
## Orphan entities (정의되었지만 어디서도 참조되지 않음) (0건)
## N:N 양방향 불일치 (0건)
## ID 형식 위반 (알려진 접두사 외) (0건)
## 누락 의심 정책 (0건)
## Silent failure 의심 (입력 신호 vs 산출물 비율) (0건)
## Unknown ID prefix (PREFIX_TO_TYPE 미등록) (0건)
## Diagrams (다이어그램 추출 검증) (3건)

### Diagram 1 — uc (`다. 유즈케이스 다이어그램`)

- uc_diagram_low_confidence: 좌표 휴리스틱 추출 (정확도 보장 X). 의미 검증 필요.
- unmapped_uc_names: ['통합회원 시작과 가입 유형']
- entities_based_supplement: ['US-MBR-CUS-001'] (원본 SVG에 그려져 있지 않아 entities.usecases 기반으로 보완)
""",
                encoding="utf-8",
            )

            summary = web_app.dev_format_warning_summary(warnings_path)

        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["totalCount"], 0)
        self.assertEqual(summary["blockingCount"], 0)
        self.assertEqual(summary["reviewCount"], 0)
        self.assertEqual(summary["diagramNotes"]["totalCount"], 3)
        self.assertEqual(summary["diagramNotes"]["actionCount"], 2)
        self.assertEqual([item["key"] for item in summary["diagramNotes"]["items"]], ["unmapped_uc_names", "entities_based_supplement"])
        first_note, second_note = summary["diagramNotes"]["items"]
        self.assertEqual(first_note["label"], "유즈케이스 이름 매칭 확인")
        self.assertIn("자동 매칭하지 못했습니다", first_note["message"])
        self.assertIn("mapping.csv", first_note["action"])
        self.assertEqual(first_note["targets"], ["통합회원 시작과 가입 유형"])
        self.assertEqual(second_note["label"], "유즈케이스 다이어그램 보강")
        self.assertIn("관계선까지 안정적으로 읽지 못해", second_note["message"])
        self.assertIn("diagrams/uc_1.svg", second_note["action"])
        self.assertEqual(second_note["targets"], ["US-MBR-CUS-001"])

    def test_warning_summary_treats_silent_failure_as_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            warnings_path = Path(tmp) / "warnings.md"
            warnings_path.write_text(
                """
# warnings.md
## Broken cross-refs (참조된 ID가 정의되지 않음) (0건)
## Orphan entities (정의되었지만 어디서도 참조되지 않음) (0건)
## N:N 양방향 불일치 (0건)
## ID 형식 위반 (알려진 접두사 외) (0건)
## 누락 의심 정책 (0건)
## Silent failure 의심 (입력 신호 vs 산출물 비율) (2건)
## Unknown ID prefix (PREFIX_TO_TYPE 미등록) (0건)
## Diagrams (다이어그램 추출 검증) (0건)
""",
                encoding="utf-8",
            )

            summary = web_app.dev_format_warning_summary(warnings_path)

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["blockingCount"], 2)
        self.assertEqual(summary["reviewCount"], 0)


if __name__ == "__main__":
    unittest.main()
