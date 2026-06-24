import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from src.blueprint_architect import architecture_contract_schema
from src.chapter_agents import chapter_output_schema, chapter_patch_schema, chapter_stages, topic_learning_schema
from src.dev_qa_agent import dev_qa_action_check_schema, dev_qa_review_schema
from src.policy_inspector import llm_inspection_schema
from src.web_app import revision_schema


def collect_strict_schema_errors(schema, path="root"):
    errors = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and "properties" in schema:
            properties = set((schema.get("properties") or {}).keys())
            required = schema.get("required")
            if not isinstance(required, list):
                errors.append(f"{path}: required must include every property")
            else:
                missing = sorted(properties - set(required))
                if missing:
                    errors.append(f"{path}: missing required {missing}")
            if schema.get("additionalProperties") is not False:
                errors.append(f"{path}: additionalProperties must be false")
        for key, value in schema.items():
            errors.extend(collect_strict_schema_errors(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            errors.extend(collect_strict_schema_errors(value, f"{path}[{index}]"))
    return errors


class LLMStrictSchemaTest(unittest.TestCase):
    def test_all_llm_response_schemas_are_strict(self):
        schemas = {
            "blueprint_architect_contract": architecture_contract_schema(),
            "dev_qa_review": dev_qa_review_schema(),
            "dev_qa_action_check": dev_qa_action_check_schema(),
            "policy_inspection": llm_inspection_schema(),
            "policy_json_inspection": llm_inspection_schema(),
            "topic_learning": topic_learning_schema(),
            "revision_intent": revision_schema(),
            "revision_refinement": revision_schema(),
        }
        for template_type in ("simple", "full"):
            for stage in chapter_stages(template_type):
                key = f"{template_type}:{stage.agent.chapter_key}"
                schemas[f"{key}:chapter"] = chapter_output_schema(stage.agent)
                schemas[f"{key}:patch"] = chapter_patch_schema(stage.agent)

        errors = []
        for name, schema in schemas.items():
            errors.extend(f"{name} {error}" for error in collect_strict_schema_errors(schema))

        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
