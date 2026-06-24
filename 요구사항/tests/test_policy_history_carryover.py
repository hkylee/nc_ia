import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.policy_agent import load_previous_document_history, make_topic_slug, merge_continued_document_history


class PolicyHistoryCarryoverTest(unittest.TestCase):
    def test_rewrite_generation_carries_previous_document_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            topic_slug = make_topic_slug("AI 검색")
            previous = output_dir / f"NC_{topic_slug}_정책서_간소화_v0.11.html"
            previous.write_text(
                """
                <html><body>
                <h2>0. 문서 히스토리</h2>
                <table><tbody>
                <tr><td>v0.10</td><td>최초 작성</td><td>2026-05-01</td><td>Planner</td></tr>
                <tr><td>v0.11</td><td>검수 보완</td><td>2026-05-02</td><td>Planner</td></tr>
                </tbody></table>
                </body></html>
                """,
                encoding="utf-8",
            )
            older = output_dir / f"NC_{topic_slug}_정책서_간소화_v0.10.html"
            older.write_text("<html><body>older</body></html>", encoding="utf-8")

            previous_history = load_previous_document_history(output_dir, topic_slug, "simple", "v0.12")
            spec = {"history": [{"version": "v0.12", "change": "새 초안", "date": "2026-05-03", "author": "Agent"}]}
            ctx = SimpleNamespace(version="v0.12", today="2026-05-03", author="Agent", brief="신규 기준으로 재작성")

            changed = merge_continued_document_history(spec, ctx, previous_history)

            self.assertTrue(changed)
            self.assertEqual(["v0.10", "v0.11", "v0.12"], [item["version"] for item in spec["history"]])
            self.assertEqual("2026-05-03", spec["history"][-1]["date"])
            self.assertIn("v0.11 문서 기준으로 신규 재작성", spec["history"][-1]["change"])
            self.assertIn("작성 요청 메모", spec["history"][-1]["change"])


if __name__ == "__main__":
    unittest.main()
