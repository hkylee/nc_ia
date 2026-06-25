import json
import tempfile
import unittest
from pathlib import Path

from src.topic_scope_definitions import build_topic_scope_definitions, format_scope_brief


class TopicScopeDefinitionsTest(unittest.TestCase):
    def test_builds_scope_definition_from_topic_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "상품목록.json").write_text(
                json.dumps(
                    {
                        "topic": "상품 목록",
                        "source_authority_rule": {
                            "priority": [
                                "1순위 근거: 첨부자료 / 사내자료 / 요구사항 / 채널 방향성·TK 과제정의 PDF"
                            ]
                        },
                        "topic_contract": {
                            "topic_definition": "상품 목록 정책서는 목록 탐색과 필터 기준을 정의한다.",
                            "writing_goal": ["개발/QA가 테스트 케이스로 전환할 수 있게 한다."],
                            "direct_scope": ["상품 목록", "카테고리 전시", "정렬/필터"],
                            "must_cover": ["상세 요구사항명 기준: 카테고리 전시"],
                            "must_not_cover": ["인접 정책서 업무를 핵심 범위로 확장하지 않는다."],
                            "focus_points": ["상세 요구사항명과 상세 설명을 먼저 본다."],
                            "core_policy_questions": ["누가 할 수 있는가."],
                            "boundary_rule": "상품 목록 직접 과업만 본문으로 작성한다.",
                        },
                        "topic_direction_milestone": [
                            "상품 목록은 단순 카탈로그가 아니라 고객이 비교와 선택을 시작하는 탐색 허브로 정의한다.",
                            "카테고리와 정렬 기준은 고객이 상품 차이를 빠르게 이해하도록 구성한다.",
                            "개발/QA가 상품 목록 업무의 허용 조건, 제한 조건, 예외 처리, 이력 기준을 테스트 케이스로 전환할 수 있게 한다.",
                        ],
                        "tk_core_orientations": [
                            {
                                "source_name": "TK_CH_상품_할인.pdf",
                                "topic_relevance": 100,
                                "core_points": ["상품 정보는 AI가 이해할 수 있는 구조화된 지식자산이 된다."],
                            },
                            {
                                "source_name": "TK_CH_전시_탐색.pdf",
                                "topic_relevance": 90,
                                "core_points": ["고객 탐색 흐름은 목적 기반으로 재구성한다."],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            definitions = build_topic_scope_definitions(root)

        self.assertIn("상품 목록", definitions)
        definition = definitions["상품 목록"]
        self.assertIn("목록 탐색", definition["definition"])
        self.assertEqual(definition["scope"], ["카테고리 전시", "정렬/필터"])
        self.assertEqual(definition["mustCover"], ["카테고리 전시"])
        self.assertEqual(
            definition["coreOrientations"],
            [
                "상품 정보는 AI가 이해할 수 있는 구조화된 지식자산이 된다.",
                "고객 탐색 흐름은 목적 기반으로 재구성한다.",
            ],
        )
        self.assertIn("[작성 지향점]", definition["brief"])
        self.assertIn("고객이 비교와 선택을 시작하는 탐색 허브", definition["brief"])
        self.assertIn("상품 차이를 빠르게 이해", definition["brief"])
        self.assertEqual(
            definition["topicDirectionDisplay"],
            [
                "상품 목록은 단순 카탈로그가 아니라 고객이 비교와 선택을 시작하는 탐색 허브로 정의한다.",
                "카테고리와 정렬 기준은 고객이 상품 차이를 빠르게 이해하도록 구성한다.",
            ],
        )
        self.assertEqual(
            definition["topicDirectionAgent"],
            [
                "상품 목록은 단순 카탈로그가 아니라 고객이 비교와 선택을 시작하는 탐색 허브로 정의한다.",
                "카테고리와 정렬 기준은 고객이 상품 차이를 빠르게 이해하도록 구성한다.",
                "개발/QA가 상품 목록 업무의 허용 조건, 제한 조건, 예외 처리, 이력 기준을 테스트 케이스로 전환할 수 있게 한다.",
            ],
        )
        self.assertNotIn("개발/QA", definition["brief"])
        self.assertNotIn("반드시 다룰 항목", definition["brief"])
        self.assertIn("conceptCard", definition)
        self.assertEqual([column["label"] for column in definition["conceptCard"]["columns"]], ["고객 과업", "업무 흐름", "처리 역량", "정책 기준"])

    def test_concept_card_uses_latest_policy_spec_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            output.mkdir()
            knowledge = root / "knowledge"
            knowledge.mkdir()
            (knowledge / "AI검색.json").write_text(
                json.dumps(
                    {
                        "topic": "AI 검색",
                        "topic_contract": {
                            "topic_definition": "AI 검색 정책서는 검색과 실행 연결 기준을 정의한다.",
                            "direct_scope": ["검색 진입"],
                            "must_cover": ["상세 요구사항명 기준: 검색 결과"],
                            "focus_points": ["실패 복구"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (output / "AI검색_policy_spec.json").write_text(
                json.dumps(
                    {
                        "meta": {"topic": "AI검색", "topic_display": "AI 검색", "version": "v0.2"},
                        "usecases": [{"id": "US-AIS-001", "name": "AI 검색으로 정보 탐색 완료", "description": "검색 결과를 확인한다."}],
                        "processes": [{"id": "PR-AIS-001", "name": "검색 질의 정규화", "description": "고객 질의를 정리한다."}],
                        "functions": [{"id": "FN-AIS-001", "name": "의도 해석", "description": "검색 의도를 판정한다."}],
                        "policy_groups": [{"id": "PG-AIS-001", "name": "검색 결과 신뢰 정책", "description": "출처와 신뢰도를 고지한다."}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            definitions = build_topic_scope_definitions(knowledge, output_dir=output)

        card = definitions["AI 검색"]["conceptCard"]
        self.assertEqual(card["columns"][0]["items"][0]["id"], "US-AIS-001")
        self.assertEqual(card["columns"][1]["items"][0]["name"], "검색 질의 정규화")
        self.assertEqual(card["columns"][2]["items"][0]["id"], "FN-AIS-001")
        self.assertEqual(card["columns"][3]["items"][0]["name"], "검색 결과 신뢰 정책")

    def test_formats_brief_with_scope_direction_and_boundary(self):
        brief = format_scope_brief(
            {
                "definition": "AI 검색 정책서는 검색 진입과 결과 품질 기준을 정의한다.",
                "scope": ["전역 검색", "검색어 입력"],
                "topicDirectionMilestone": [
                    "AI 검색은 고객 의도를 해석하고 실행 가능한 결과로 연결한다.",
                    "검색 실패와 낮은 신뢰 결과는 복구 경로와 근거 고지 기준으로 관리한다.",
                    "개발/QA가 AI 검색 업무의 허용 조건과 예외 처리를 테스트 케이스로 전환할 수 있게 한다.",
                ],
                "direction": ["검색 실패 복구 기준을 남긴다."],
                "mustCover": ["검색 입력 UI 표준"],
                "focusPoints": ["정책 질문을 먼저 정리한다."],
                "boundaryRule": "추천은 연계 결과로만 다룬다.",
                "mustNotCover": ["화면 UI 상세로 내려가지 않는다."],
            }
        )

        self.assertIn("[작성 지향점]", brief)
        self.assertIn("- AI 검색은 고객 의도를 해석하고 실행 가능한 결과로 연결한다.", brief)
        self.assertIn("- 검색 실패와 낮은 신뢰 결과는 복구 경로와 근거 고지 기준으로 관리한다.", brief)
        self.assertNotIn("개발/QA", brief)
        self.assertNotIn("경계 기준", brief)


if __name__ == "__main__":
    unittest.main()
