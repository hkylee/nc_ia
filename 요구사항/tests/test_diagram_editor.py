import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.web_app as web_app


class DiagramEditorTests(unittest.TestCase):
    def test_diagram_edit_creates_version_and_bpmn_sidecars(self):
        source_name = "NC_상품상세담기_정책서_Full_v0.11.html"
        source_html = Path("output") / source_name
        source_spec = Path("output") / f"{source_html.stem}_spec.json"

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            lock_dir = output_root / ".locks"
            output_root.mkdir()
            shutil.copy2(source_html, output_root / source_html.name)
            shutil.copy2(source_spec, output_root / source_spec.name)

            with patch.object(web_app, "OUTPUT_ROOT", output_root), patch.object(web_app, "LOCK_DIR", lock_dir):
                diagram = web_app.policy_diagram_data_from_name(source_name)
                self.assertGreater(len(diagram["usecases"]), 0)

                edited_usecases = json.loads(json.dumps(diagram["usecases"], ensure_ascii=False))
                edited_usecases[0]["name"] = "상품 가치 탐색과 이해 수정"

                result = web_app.save_policy_diagram_edit_from_payload(
                    {
                        "name": source_name,
                        "author": "Diagram Test",
                        "saveMode": "new_version",
                        "baseHash": web_app.document_content_hash((output_root / source_name).read_text(encoding="utf-8")),
                        "diagram": {
                            "actors": diagram["actors"],
                            "usecases": edited_usecases,
                            "states": diagram["states"],
                            "stateTransitions": diagram["stateTransitions"],
                            "processes": diagram["processes"],
                        },
                    }
                )

                self.assertEqual(result.name, "NC_상품상세담기_정책서_Full_v0.12.html")
                self.assertTrue(result.exists())
                self.assertTrue((output_root / f"{result.stem}_spec.json").exists())
                self.assertTrue((output_root / f"{result.stem}_전체업무흐름도.bpmn").exists())
                self.assertTrue((output_root / f"{result.stem}_전체업무흐름도_viewer.html").exists())

                updated_spec = json.loads((output_root / f"{result.stem}_spec.json").read_text(encoding="utf-8"))
                self.assertEqual(updated_spec["usecases"][0]["name"], "상품 가치 탐색과 이해 수정")
                self.assertIn("bpmn-viewer", result.read_text(encoding="utf-8"))

    def test_diagram_edit_rejects_unknown_usecase_actor(self):
        source_name = "NC_상품상세담기_정책서_Full_v0.11.html"
        source_html = Path("output") / source_name
        source_spec = Path("output") / f"{source_html.stem}_spec.json"

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            lock_dir = output_root / ".locks"
            output_root.mkdir()
            shutil.copy2(source_html, output_root / source_html.name)
            shutil.copy2(source_spec, output_root / source_spec.name)

            with patch.object(web_app, "OUTPUT_ROOT", output_root), patch.object(web_app, "LOCK_DIR", lock_dir):
                diagram = web_app.policy_diagram_data_from_name(source_name)
                edited_usecases = json.loads(json.dumps(diagram["usecases"], ensure_ascii=False))
                edited_usecases[0]["actor"] = "없는 액터"

                with self.assertRaisesRegex(ValueError, "액터 목록"):
                    web_app.save_policy_diagram_edit_from_payload(
                        {
                            "name": source_name,
                            "author": "Diagram Test",
                            "saveMode": "new_version",
                            "diagram": {
                                "actors": diagram["actors"],
                                "usecases": edited_usecases,
                                "states": diagram["states"],
                                "stateTransitions": diagram["stateTransitions"],
                                "processes": diagram["processes"],
                            },
                        }
                    )


if __name__ == "__main__":
    unittest.main()
