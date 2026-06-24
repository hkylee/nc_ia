import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import web_app
from src.topic_knowledge_builder import TOPIC_KNOWLEDGE_VERSION, topic_knowledge_path


class TopicDirectionUpdateTest(unittest.TestCase):
    def test_cached_direction_updates_without_full_rebuild(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_root = Path(tmpdir)
            topic = "AI 검색"
            path = topic_knowledge_path(topic, knowledge_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "version": TOPIC_KNOWLEDGE_VERSION,
                        "topic": topic,
                        "topic_direction_milestone": ["기존 지침"],
                        "topic_direction_strategy": ["기존 지침"],
                        "topic_direction_agent_guidance": ["기존 지침"],
                        "topic_contract": {"topic_definition": "AI 검색 정책서"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(web_app, "DEFAULT_TOPIC_KNOWLEDGE_DIR", knowledge_root):
                updated = web_app.update_cached_topic_direction(
                    topic,
                    [
                        "AI 검색은 고객 의도 기반 실행 진입점으로 정의한다.",
                        "개발/QA가 AI 검색 조건을 테스트 케이스로 전환할 수 있게 한다.",
                    ],
                )

            self.assertTrue(updated)
            pack = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                pack["topic_direction_strategy"],
                ["AI 검색은 고객 의도 기반 실행 진입점으로 정의한다."],
            )
            self.assertIn("개발/QA", pack["topic_direction_agent_guidance"][1])
            self.assertTrue(pack["knowledge_refresh_pending"])

    def test_topic_scope_reads_runtime_knowledge_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_root = Path(tmpdir) / "runtime_topic_knowledge"
            output_root = Path(tmpdir) / "output"
            topic = "AI 검색"
            path = topic_knowledge_path(topic, knowledge_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "version": TOPIC_KNOWLEDGE_VERSION,
                        "topic": topic,
                        "topic_direction_milestone": ["런타임 저장 지침"],
                        "topic_direction_strategy": ["런타임 저장 지침"],
                        "topic_direction_agent_guidance": ["런타임 저장 지침"],
                        "topic_contract": {
                            "topic_definition": "AI 검색 정책서",
                            "direct_scope": ["AI 검색"],
                            "writing_goal": ["기본 작성 목표"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(web_app, "DEFAULT_TOPIC_KNOWLEDGE_DIR", knowledge_root), patch.object(web_app, "OUTPUT_ROOT", output_root):
                definitions = web_app.build_runtime_topic_scope_definitions()
                definition = web_app.runtime_topic_scope_definition(topic)

            self.assertIn(topic, definitions)
            self.assertIsNotNone(definition)
            self.assertEqual(["런타임 저장 지침"], definition["topicDirectionDisplay"])
            self.assertIn("런타임 저장 지침", definition["brief"])


if __name__ == "__main__":
    unittest.main()
