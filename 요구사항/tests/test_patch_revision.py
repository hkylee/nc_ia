import unittest
from types import SimpleNamespace

from src.chapter_agents import (
    compact_patch_target_for_prompt,
    merge_patch_payload,
    requires_scoped_full_revision,
    revision_patch_target,
    should_use_patch_revision,
)


class PatchRevisionTest(unittest.TestCase):
    def test_patch_payload_ignores_fields_outside_patch_target(self):
        agent = SimpleNamespace(output_fields=("actors", "usecases"))
        current = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객"}],
            "usecases": [{"id": "US-MBR-001", "name": "가입 신청"}],
        }
        patch = {
            "actors": [{"id": "ACT-MBR-001", "name": "고객 수정"}],
            "usecases": [{"id": "US-MBR-001", "name": "수정되면 안 됨"}],
        }
        target = {"actors": [{"id": "ACT-MBR-001", "name": "고객"}]}

        merged = merge_patch_payload(agent, current, patch, patch_target=target)

        self.assertEqual("고객 수정", merged["actors"][0]["name"])
        self.assertEqual("가입 신청", merged["usecases"][0]["name"])

    def test_revision_patch_target_uses_inspector_target_path_index(self):
        agent = SimpleNamespace(output_fields=("processes",), chapter_key="process")
        current = {
            "processes": [
                {"id": "PR-AIS-001", "name": "첫 번째"},
                {"id": "PR-AIS-002", "name": "두 번째"},
                {"id": "PR-AIS-003", "name": "세 번째"},
            ]
        }
        feedback = [
            {
                "target_path": "current_chapter.processes[2].description",
                "detail": "세 번째 프로세스 설명 보완",
            }
        ]

        target = revision_patch_target(agent, current, feedback)

        self.assertEqual(["PR-AIS-003"], [item["id"] for item in target["processes"]])

    def test_full_revision_is_blocked_above_low_score_threshold(self):
        agent = SimpleNamespace(output_fields=("processes",), chapter_key="process")
        spec = {"processes": [{"id": "PR-AIS-001", "name": "프로세스"}]}
        feedback = [
            {
                "category": "구조",
                "detail": "프로세스 구조 전반 보완",
                "inspector_score": 82,
            }
        ]

        self.assertFalse(requires_scoped_full_revision(agent, feedback))
        self.assertTrue(should_use_patch_revision(agent, spec, feedback))

    def test_patch_revision_is_blocked_without_current_payload(self):
        agent = SimpleNamespace(output_fields=("processes",), chapter_key="process")
        feedback = [
            {
                "category": "구조",
                "detail": "프로세스 구조 전반 보완",
                "inspector_score": 82,
            }
        ]

        self.assertFalse(should_use_patch_revision(agent, {}, feedback))

    def test_full_revision_is_allowed_only_for_low_score_structural_failure(self):
        agent = SimpleNamespace(output_fields=("processes",), chapter_key="process")
        feedback = [
            {
                "category": "구조",
                "detail": "프로세스 구조 전반 보완",
                "inspector_score": 50,
            }
        ]

        self.assertTrue(requires_scoped_full_revision(agent, feedback))
        self.assertFalse(should_use_patch_revision(agent, {}, feedback))

    def test_process_target_path_prefers_patch_even_with_broad_mode(self):
        agent = SimpleNamespace(output_fields=("processes",), chapter_key="process")
        spec = {
            "processes": [
                {"id": "PR-AIS-001", "name": "첫 번째"},
                {"id": "PR-AIS-002", "name": "두 번째"},
            ]
        }
        feedback = [
            {
                "remediation_mode": "blueprint_realign_revision",
                "target_path": "current_chapter.processes[1].description",
                "detail": "PR-AIS-002 설명 보완",
                "inspector_score": 51,
            }
        ]

        self.assertTrue(should_use_patch_revision(agent, spec, feedback))

    def test_functions_target_path_prefers_patch_even_with_full_mode(self):
        agent = SimpleNamespace(output_fields=("functions",), chapter_key="functions")
        spec = {
            "functions": [
                {"id": "FN-AIS-001", "name": "첫 번째"},
                {"id": "FN-AIS-002", "name": "두 번째"},
            ]
        }
        feedback = [
            {
                "remediation_mode": "scoped_full_revision",
                "target_path": "current_chapter.functions[0].details",
                "detail": "FN-AIS-001 세부 기능 구성 보완",
                "inspector_score": 60,
            }
        ]

        self.assertTrue(should_use_patch_revision(agent, spec, feedback))

    def test_object_payload_can_be_patched_without_rewriting_chapter(self):
        agent = SimpleNamespace(output_fields=("overview",), chapter_key="overview")
        current = {
            "overview": {
                "scope": ["기존 범위"],
                "principles": [{"name": "기존 원칙", "description": "기존 설명"}],
            }
        }
        patch = {"overview": {"scope": ["수정 범위"]}}
        target = {"overview": current["overview"]}

        merged = merge_patch_payload(agent, current, patch, patch_target=target)

        self.assertEqual(["수정 범위"], merged["overview"]["scope"])
        self.assertEqual(current["overview"]["principles"], merged["overview"]["principles"])

    def test_overview_patch_target_keeps_principles_as_objects(self):
        target = {
            "overview": {
                "scope": ["기존 범위"],
                "principles": [{"name": "기존 원칙", "description": "기존 설명"}],
            }
        }

        compact = compact_patch_target_for_prompt(target)

        self.assertEqual("기존 원칙", compact["overview"]["principles"][0]["name"])
        self.assertEqual("기존 설명", compact["overview"]["principles"][0]["description"])


if __name__ == "__main__":
    unittest.main()
