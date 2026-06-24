import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src.chapter_agents import chapter_stages
from src.orchestrator import checkpoint_spec, resume_repair_start_index
from src.schema import ensure_policy_spec_base_keys
from src.validator import validate_policy_spec


def legacy_simple_spec():
    return {
        "meta": {
            "business_code": "SUB",
            "template_type": "simple",
            "usecase_diagram": {"lines": ["[고객] → (가입 정보 확인)"]},
        },
        "history": [{"version": "v0.1", "change": "legacy checkpoint"}],
        "overview": {"scope": ["범위"], "principles": [{"name": "원칙", "description": "설명"}]},
        "terms": [{"id": "TM-SUB-001", "name": "용어", "description": "판단 기준"}],
        "actors": [{"id": "ACT-SUB-001", "name": "고객", "responsibility": "요청"}],
        "usecases": [
            {
                "id": "US-SUB-001",
                "name": "가입 정보 확인",
                "actor": "고객",
                "description": "고객이 가입 정보를 확인한다.",
                "process_target": "Y",
            }
        ],
        "states": [
            {
                "id": "ST-SUB-001",
                "name": "조회 가능",
                "description": "조회 가능한 상태",
                "next_action": "가입 정보 조회 결과를 확인한다.",
            }
        ],
        "state_transitions": [
            {
                "usecase_ids": ["US-SUB-001"],
                "current_state": "조회 가능",
                "event": "가입 정보 확인",
                "next_state": "조회 가능",
                "criteria": "조회 요청 시 유지한다.",
            }
        ],
        "processes": [
            {
                "id": "PR-SUB-001",
                "usecase_id": "US-SUB-001",
                "name": "가입 정보 조회",
                "description": "고객 권한과 조회 조건을 확인한다.",
                "related_functions": ["FN-SUB-001 가입 정보 조회"],
                "related_policies": ["PG-SUB-001 조회 기준"],
            },
            {
                "id": "PR-SUB-002",
                "usecase_id": "US-SUB-001",
                "name": "조회 결과 제공",
                "description": "조회 가능 여부와 결과를 고객에게 제공하고 이력을 저장한다.",
                "related_functions": ["FN-SUB-001 가입 정보 조회"],
                "related_policies": ["PG-SUB-001 조회 기준"],
            }
        ],
        "functions": [
            {
                "id": "FN-SUB-001",
                "name": "가입 정보 조회",
                "process_id": "PR-SUB-001",
                "process_ids": ["PR-SUB-001", "PR-SUB-002"],
                "description": "가입 정보를 조회한다.",
                "details": ["권한 확인", "결과 제공"],
            }
        ],
        "policy_groups": [
            {"id": "PG-SUB-001", "name": "조회 기준", "description": "조회 허용 기준", "items": ["권한 기준"]}
        ],
        "policy_details": [
            {
                "id": "PI-SUB-001",
                "policy_id": "PG-SUB-001",
                "name": "권한 기준",
                "content": "본인확인 완료 고객에게만 조회를 허용하고 조회 이력을 저장한다.",
            }
        ],
        "final_check": [{"category": "정합성", "item": "연결 확인", "criteria": "프로세스와 정책이 연결되어야 한다."}],
    }


class PolicySpecMigrationTest(unittest.TestCase):
    def test_base_key_migration_adds_full_only_arrays_without_content(self):
        spec = legacy_simple_spec()
        self.assertNotIn("process_details", spec)
        self.assertNotIn("function_details", spec)

        migrated = ensure_policy_spec_base_keys(spec)

        self.assertEqual([], migrated["process_details"])
        self.assertEqual([], migrated["function_details"])
        self.assertTrue(validate_policy_spec(migrated, "SUB").ok)

    def test_resume_checkpoint_migrates_legacy_spec_shape(self):
        legacy = legacy_simple_spec()
        original = copy.deepcopy(legacy)

        migrated = checkpoint_spec({"checkpoint": {"stage_key": "08"}, "spec": legacy})

        self.assertIsNot(migrated, legacy)
        self.assertEqual(original, legacy)
        self.assertIn("process_details", migrated)
        self.assertIn("function_details", migrated)

    def test_resume_repair_restarts_from_first_invalid_completed_stage(self):
        spec = ensure_policy_spec_base_keys(legacy_simple_spec())
        spec["states"][0]["next_action"] = "US-SUB-001 기준으로 조회를 허용한다."
        spec["state_transitions"][0].pop("usecase_ids", None)
        stages = chapter_stages("simple")
        requested_start = 8

        repair_start = resume_repair_start_index(stages, spec, "SUB", requested_start)

        self.assertEqual("06", stages[repair_start].key)

    def test_resume_repair_keeps_current_start_when_completed_stages_are_valid(self):
        spec = ensure_policy_spec_base_keys(legacy_simple_spec())
        stages = chapter_stages("simple")
        requested_start = 8

        repair_start = resume_repair_start_index(stages, spec, "SUB", requested_start)

        self.assertEqual(requested_start, repair_start)

    def test_grouped_policy_details_are_validated_as_policy_items(self):
        spec = ensure_policy_spec_base_keys(legacy_simple_spec())
        spec["policy_groups"][0]["items"] = [{"id": "PI-SUB-001", "name": "권한 기준"}]
        spec["policy_details"] = [
            {
                "policy_id": "PG-SUB-001",
                "policy_name": "조회 기준",
                "items": [
                    {
                        "id": "PI-SUB-001",
                        "name": "권한 기준",
                        "content": "본인확인 완료 고객에게만 조회를 허용하고 조회 이력을 저장한다.",
                    }
                ],
            }
        ]

        result = validate_policy_spec(spec, "SUB")

        self.assertTrue(result.ok, result.errors)


if __name__ == "__main__":
    unittest.main()
