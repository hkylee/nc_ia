import unittest
from tempfile import TemporaryDirectory

from src.topic_knowledge_builder import (
    build_auxiliary_web_signals,
    build_tk_core_orientations,
    build_tk_process_function_guidance,
    build_topic_contract,
    build_topic_knowledge_pack,
    build_candidate_inventory,
    compact_topic_knowledge_for_prompt,
    load_topic_direction_milestones,
    split_references_by_authority,
    source_fingerprint,
    topic_direction_milestone_for,
    update_topic_direction_display_milestone,
    update_topic_direction_milestone,
)


class FakeRequirement:
    depth4 = "통합 쿠폰/이용권함"
    detail_name = "쿠폰 사용 확인"
    detail_description = "고객은 쿠폰 유효기간과 사용 가능 조건을 확인해야 한다."
    requirement_id = "REQ-001"
    source_number = "1"
    requirement_type = "필수"
    required = "Y"


class FakeReference:
    def __init__(self, source_name, category, signals=(), evidence=(), source_text=""):
        self.source_name = source_name
        self.category = category
        self.signals = signals
        self.evidence = evidence
        self.summary = " ".join(signals)
        self.source_text = source_text


class TopicKnowledgeBuilderTest(unittest.TestCase):
    def test_public_web_knowledge_is_auxiliary(self):
        attached = FakeReference("쿠폰 VoC 분석.pdf", "voc", ("쿠폰 사용 불편",), ("쿠폰 사용 조건 확인 필요",))
        web = FakeReference(
            "채널 방향성_T우주_sktuniverse_공개웹_구독정책_통합지식_20260503.md",
            "strategy",
            ("이용권 유효기간",),
            ("공개웹 보조 지식",),
        )

        primary, auxiliary = split_references_by_authority([attached, web])

        self.assertEqual([attached], primary)
        self.assertEqual([web], auxiliary)
        self.assertEqual("1순위 근거와 상충하면 사용하지 않는다.", build_auxiliary_web_signals(auxiliary)["usage_rule"])

    def test_candidate_inventory_includes_policy_values(self):
        inventory = build_candidate_inventory("통합 쿠폰/이용권함", [FakeRequirement()], [])

        self.assertIn("고객", inventory["actor_candidates"])
        self.assertTrue(any("쿠폰" in item for item in inventory["function_candidates"]))
        self.assertTrue(any("쿠폰" in item for item in inventory["policy_item_candidates"]))

    def test_pack_declares_candidates_as_non_binding(self):
        pack = build_topic_knowledge_pack(
            "통합 쿠폰/이용권함",
            requirements_dir="/tmp/not-existing-requirements",
            references_dir="/tmp/not-existing-references",
        )

        self.assertTrue(pack["candidate_usage_policy"]["use_as_candidate_only"])
        self.assertIn("출발점", pack["candidate_usage_policy"]["rule"])
        self.assertTrue(pack["candidate_usage_policy"]["rejection_conditions"])
        self.assertEqual(
            [
                "1순위 근거: 첨부자료 / 사내자료 / 요구사항 / 채널 방향성·TK 과제정의 PDF",
                "1순위 보강 근거: 현황 분석 종합 장표 / VoC 종합 장표",
                "2순위 보조 근거: SKT 공식 서비스 안내 / 약관 / 고객지원 페이지",
                "3순위 컴플라이언스 근거: 법령 / 규제기관 / 개인정보보호위 / 방통위 자료",
                "4순위 참고 근거: 경쟁사 / 벤치마킹 / 공개웹 자료",
            ],
            pack["source_authority_rule"]["priority"],
        )
        self.assertIn("analysis_synthesis_role", pack["source_authority_rule"])
        self.assertIn("topic_contract", pack)
        self.assertIn("상세 요구사항", pack["topic_contract"]["requirement_basis"])
        self.assertTrue(pack["topic_contract"]["must_not_cover"])
        self.assertIn("tk_core_orientations", pack)
        self.assertIn("topic_direction_milestone", pack)

    def test_topic_contract_uses_detail_requirements_and_boundaries(self):
        contract = build_topic_contract("통합 쿠폰/이용권함", [FakeRequirement()], [])

        self.assertIn("쿠폰 사용 확인", contract["topic_definition"])
        self.assertTrue(any("상세 요구사항명 기준: 쿠폰 사용 확인" == item for item in contract["must_cover"]))
        self.assertIn("요구사항 문구를 그대로 복사하지 않고", " ".join(contract["must_not_cover"]))
        self.assertIn("통합 쿠폰/이용권함", contract["boundary_rule"])

    def test_compact_prompt_includes_topic_contract(self):
        pack = build_topic_knowledge_pack(
            "통합 쿠폰/이용권함",
            requirements_dir="/tmp/not-existing-requirements",
            references_dir="/tmp/not-existing-references",
        )
        compact = compact_topic_knowledge_for_prompt(pack, max_chars=1200)

        self.assertIn("topic_contract", compact)
        self.assertIn("topic_definition", compact["topic_contract"])
        self.assertIn("tk_core_orientations", compact)
        self.assertIn("topic_direction_milestone", compact)

    def test_topic_direction_milestones_are_parsed_by_exact_topic(self):
        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/directions.md"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "# 지향점\n\n"
                    "## 1. 상품 목록\n"
                    "- 상품 목록은 고객 탐색 허브로 정의한다.\n"
                    "- 필터와 정렬은 비교 기준을 명확히 한다.\n\n"
                    "## 2. AI 검색\n"
                    "- AI 검색은 의도 기반 탐색으로 정의한다.\n"
                )

            milestones = load_topic_direction_milestones(path)

        self.assertEqual(2, len(milestones["상품 목록"]))
        self.assertEqual(["AI 검색은 의도 기반 탐색으로 정의한다."], topic_direction_milestone_for("AI 검색", milestones))
        self.assertEqual([], topic_direction_milestone_for("추천", milestones))

    def test_topic_direction_milestone_update_replaces_only_target_section(self):
        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/directions.md"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "# 지향점\n\n"
                    "## 1. 상품 목록\n"
                    "- 기존 상품 목록 지향점\n\n"
                    "## 2. AI 검색\n"
                    "- AI 검색은 의도 기반 탐색으로 정의한다.\n"
                )

            updated = update_topic_direction_milestone("상품 목록", ["새 상품 목록 지향점", "필터 기준을 명확히 한다."], path)
            milestones = load_topic_direction_milestones(path)

        self.assertEqual(["새 상품 목록 지향점", "필터 기준을 명확히 한다."], updated)
        self.assertEqual(updated, milestones["상품 목록"])
        self.assertEqual(["AI 검색은 의도 기반 탐색으로 정의한다."], milestones["AI 검색"])

    def test_topic_direction_display_update_preserves_internal_agent_lines(self):
        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/directions.md"
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "# 지향점\n\n"
                    "## 1. AI 검색\n"
                    "- AI 검색은 기존 지향점이다.\n"
                    "- 검색 결과는 실행 가능한 후속 행동으로 연결한다.\n"
                    "- 개발/QA가 AI 검색 업무의 조건과 예외를 테스트 케이스로 전환할 수 있게 한다.\n"
                )

            updated = update_topic_direction_display_milestone(
                "AI 검색",
                ["AI 검색은 새 고객 목적 지향점이다.", "검색 실패 시 복구 경로를 명확히 한다."],
                path,
            )
            milestones = load_topic_direction_milestones(path)

        self.assertEqual(
            [
                "AI 검색은 새 고객 목적 지향점이다.",
                "검색 실패 시 복구 경로를 명확히 한다.",
                "개발/QA가 AI 검색 업무의 조건과 예외를 테스트 케이스로 전환할 수 있게 한다.",
            ],
            updated,
        )
        self.assertEqual(updated, milestones["AI 검색"])

    def test_tk_core_orientation_is_extracted_as_first_class_direction(self):
        tk = FakeReference(
            "TK_CH_상품_할인_AI가 의사결정을 도와주는 상품_할인 체계.pdf",
            "strategy",
            ("AI·개인화는 정확성과 실행 가능성을 우선",),
            (),
            "지향점 및 기대 효과 핵심 지향점 To Do 기대 효과 KPI "
            "1 상품 정보는 AI가 이해하고 고객에게 설명할 수 있는 구조화된 상품 지식자산이 된다 "
            "상품명과 조건을 공통 스키마 기준으로 표준화한다.",
        )

        rows = build_tk_core_orientations("상품 목록", [tk])

        self.assertEqual(1, len(rows))
        self.assertIn("TK_CH_상품", rows[0]["source_name"])
        self.assertTrue(rows[0]["core_points"])
        self.assertIn("핵심 지향점", rows[0]["evidence_excerpt"])
        self.assertIn("mapping_rule", rows[0])
        self.assertTrue(rows[0]["matched_keywords"])

    def test_tk_core_orientation_filters_points_by_topic_context(self):
        tk = FakeReference(
            "TK_CH_상품_할인_AI가 의사결정을 도와주는 상품_할인 체계.pdf",
            "strategy",
            (),
            (),
            "지향점 및 기대 효과 핵심 지향점 "
            "1 상품 정보는 AI가 이해하고 고객에게 설명할 수 있는 구조화된 상품 지식자산이 된다 "
            "2 청구 수납 업무는 납부 실패와 재처리 기준을 중심으로 표준화한다",
        )

        rows = build_tk_core_orientations("상품 목록", [tk])

        self.assertEqual(1, len(rows))
        self.assertTrue(any("상품 정보" in item for item in rows[0]["core_points"]))
        self.assertFalse(any("청구 수납" in item for item in rows[0]["core_points"]))

    def test_tk_process_function_guidance_uses_major_process_rows(self):
        tk = FakeReference(
            "TK_CH_AI_검색_추천_통합_AI_Agent_탐색_체계.pdf",
            "strategy",
            (),
            (),
            "주요 프로세스 및 기능 번호 프로세스 명 주요 기능 "
            "1 AI Agent 진입 및 요청 입력 홈 MY 공통 Agent 진입점 제공 텍스트 음성 입력 제공 "
            "2 사용자 의도 분석 및 Task 분해 발화 의도 분류 후속 질문 생성 "
            "3 추천 후보 정렬 개인화 추천 점수 산정 제외 조건 반영",
        )

        rows = build_tk_process_function_guidance("AI 검색", [tk])

        self.assertTrue(rows)
        self.assertIn("process_name", rows[0])
        self.assertTrue(rows[0]["major_functions"])
        self.assertIn("주요 프로세스", rows[0]["usage_rule"])
        self.assertIn("여러 정책 주제", rows[0]["mapping_rule"])

    def test_tk_process_function_guidance_filters_rows_by_topic(self):
        tk = FakeReference(
            "TK_CH_AI_검색_추천_통합_AI_Agent_탐색_체계.pdf",
            "strategy",
            (),
            (),
            "주요 프로세스 및 기능 번호 프로세스 명 주요 기능 "
            "1 AI 검색 질의 실행 검색어 의도 분석 검색 결과 구성 "
            "2 청구 납부 실패 처리 미납 요금 조회 수납 결과 반영",
        )

        rows = build_tk_process_function_guidance("AI 검색", [tk])
        text = " ".join(
            [row.get("process_name", "") for row in rows]
            + [function for row in rows for function in row.get("major_functions", [])]
        )

        self.assertIn("검색", text)
        self.assertNotIn("청구", text)

    def test_source_fingerprint_changes_when_detail_description_changes(self):
        class ChangedRequirement(FakeRequirement):
            detail_description = "고객은 쿠폰 유효기간, 사용 가능 조건, 사용 제한 사유를 확인해야 한다."

        self.assertNotEqual(
            source_fingerprint([FakeRequirement()], []),
            source_fingerprint([ChangedRequirement()], []),
        )


if __name__ == "__main__":
    unittest.main()
