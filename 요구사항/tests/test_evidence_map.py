import unittest

from src.context_assembler import assemble_context_pack, update_traceability
from src.evidence_map import build_topic_evidence_map, compact_topic_evidence_map_for_stage
from src.evidence_store import EvidenceItem, EvidenceStore, evidence_authority_score, evidence_source_authority, evidence_source_authority_tier
from src.policy_inspector import json_inspector_support_context


class EvidenceMapTest(unittest.TestCase):
    def test_topic_evidence_map_selects_stage_specific_cards(self):
        spec = sample_spec()
        evidence_map = build_topic_evidence_map(
            topic="나의 가입 정보",
            spec=spec,
            evidence_store=sample_store(),
            learning=sample_learning(),
            stages=("process", "policies"),
            per_stage_limit=6,
        )

        process_map = evidence_map["stages"]["process"]
        policies_map = evidence_map["stages"]["policies"]

        self.assertIn("REQ-001", process_map["evidence_ids"])
        self.assertIn("requirement", process_map["source_mix"])
        self.assertTrue(process_map["flow_signals"])
        self.assertTrue(policies_map["decision_axes"])

    def test_context_pack_and_inspector_receive_topic_evidence_map(self):
        spec = sample_spec()
        spec["processes"] = [{"id": "PR-INFO-001", "name": "가입 정보 확인", "description": "고객이 가입 정보를 확인한다."}]
        topic_map = build_topic_evidence_map(
            topic="나의 가입 정보",
            spec=spec,
            evidence_store=sample_store(),
            learning=sample_learning(),
            stages=("process",),
            per_stage_limit=6,
        )
        spec["meta"]["topic_evidence_map"] = topic_map

        context_pack = assemble_context_pack(
            agent_key="process",
            spec=spec,
            evidence_store=sample_store(),
            topic="나의 가입 정보",
            learning=sample_learning(),
            limit=6,
        )
        update_traceability(spec, "process", context_pack)
        support_context = json_inspector_support_context(spec, "07_process", "process")

        self.assertTrue(context_pack["topic_evidence_map"]["evidence_cards"])
        self.assertIn("REQ-001", context_pack["topic_evidence_map"]["evidence_ids"])
        self.assertIn("REQ-001", context_pack["essential_evidence_ids"])
        self.assertTrue(context_pack["selection_strategy"])
        self.assertIn("context_quality", context_pack)
        self.assertTrue(context_pack["policy_questions"])
        self.assertTrue(context_pack["required_outputs"])
        self.assertTrue(context_pack["must_decide"])
        self.assertGreaterEqual(context_pack["context_quality"]["score"], 70)
        self.assertEqual("Evidence Store", context_pack["knowledge_mode"]["rag"]["source"])
        self.assertIn("Authoring Blueprint", context_pack["knowledge_mode"]["cag"]["source"])
        self.assertEqual("process", support_context["topic_evidence_map"]["stage"])
        self.assertTrue(spec["meta"]["context_pack_runs"][0]["evidence_source_mix"])
        self.assertIn("context_quality_score", spec["meta"]["context_pack_runs"][0])
        self.assertGreater(spec["meta"]["context_pack_runs"][0]["policy_question_count"], 0)
        self.assertEqual("process", support_context["context_quality"]["chapter"])
        self.assertGreaterEqual(support_context["context_quality"]["score"], 70)

    def test_context_quality_flags_missing_required_evidence(self):
        spec = sample_spec()
        store = EvidenceStore(
            [
                EvidenceItem(
                    id="REF-WEB-ONLY",
                    kind="strategy",
                    source="공개웹 보조 지식",
                    title="공개웹 보조 지식",
                    summary="첨부 근거 없이 보조 지식만 있다.",
                    signals=("나의 가입 정보",),
                    evidence=("보조 참고",),
                    tags=("web",),
                    score=90,
                )
            ]
        )

        context_pack = assemble_context_pack(
            agent_key="process",
            spec=spec,
            evidence_store=store,
            topic="나의 가입 정보",
            learning=sample_learning(),
            limit=3,
        )

        self.assertEqual("risk", context_pack["context_quality"]["status"])
        self.assertIn("requirement", context_pack["context_quality"]["missing_required_kinds"])

    def test_context_pack_preserves_required_non_requirement_kinds(self):
        many_requirements = [
            EvidenceItem(
                id=f"REQ-EXTRA-{index:03d}",
                kind="requirement",
                source="요구사항 통합 list",
                title=f"추가 요구사항 {index}",
                summary="가입 정보 확인 요구사항이다.",
                signals=("나의 가입 정보", "요구사항"),
                evidence=("추가 요구사항",),
                tags=("requirement",),
                score=100 - index,
            )
            for index in range(1, 16)
        ]
        store = EvidenceStore([*many_requirements, *sample_store().items])

        context_pack = assemble_context_pack(
            agent_key="overview",
            spec=sample_spec(),
            evidence_store=store,
            topic="나의 가입 정보",
            learning=sample_learning(),
            limit=6,
        )
        selected_kinds = {item["kind"] for item in context_pack["selected_evidence"]}

        self.assertIn("guideline", selected_kinds)
        self.assertIn("sample", selected_kinds)

    def test_topic_evidence_map_preserves_required_non_requirement_kinds(self):
        many_requirements = [
            EvidenceItem(
                id=f"REQ-EXTRA-{index:03d}",
                kind="requirement",
                source="요구사항 통합 list",
                title=f"추가 요구사항 {index}",
                summary="가입 정보 확인 요구사항이다.",
                signals=("나의 가입 정보", "요구사항"),
                evidence=("추가 요구사항",),
                tags=("requirement",),
                score=100 - index,
            )
            for index in range(1, 16)
        ]
        store = EvidenceStore([*many_requirements, *sample_store().items])

        evidence_map = build_topic_evidence_map(
            topic="나의 가입 정보",
            spec=sample_spec(),
            evidence_store=store,
            learning=sample_learning(),
            stages=("overview",),
            per_stage_limit=6,
        )
        selected_kinds = set(evidence_map["stages"]["overview"]["source_mix"])

        self.assertIn("guideline", selected_kinds)
        self.assertIn("sample", selected_kinds)
        self.assertNotIn("sample", [gap["missing_kind"] for gap in evidence_map["stages"]["overview"]["evidence_gaps"]])

    def test_compact_stage_map_stays_small(self):
        evidence_map = build_topic_evidence_map(
            topic="나의 가입 정보",
            spec=sample_spec(),
            evidence_store=sample_store(),
            learning=sample_learning(),
            stages=("process",),
            per_stage_limit=8,
        )

        compact = compact_topic_evidence_map_for_stage(evidence_map, "process", max_cards=2)

        self.assertEqual(2, len(compact["evidence_cards"]))
        self.assertIn("selection_strategy", compact)
        self.assertNotIn("stages", compact)

    def test_global_channel_strategy_reaches_core_stage_context(self):
        store = sample_store()
        evidence_map = build_topic_evidence_map(
            topic="나의 가입 정보",
            spec=sample_spec(),
            evidence_store=store,
            learning=sample_learning(),
            stages=("terms",),
            per_stage_limit=6,
        )

        terms_map = evidence_map["stages"]["terms"]
        context_pack = assemble_context_pack(
            agent_key="terms",
            spec=sample_spec(),
            evidence_store=store,
            topic="나의 가입 정보",
            learning=sample_learning(),
            limit=6,
        )

        self.assertTrue(terms_map["channel_integration_context"])
        self.assertTrue(context_pack["channel_integration_context"])
        self.assertIn("REF-STR-CHANNEL", terms_map["evidence_ids"])
        self.assertIn("REF-STR-CHANNEL", context_pack["selected_evidence_ids"])

    def test_source_authority_separates_official_compliance_and_benchmark_tiers(self):
        official = EvidenceItem(
            id="REF-WEB-001",
            kind="strategy",
            source="채널 방향성_T우주_sktuniverse_공개웹_구독정책_통합지식",
            title="공개웹 학습 지식",
            summary="T우주 공개웹에서 학습한 구독 정책 후보",
            signals=("구독",),
            evidence=("정기결제 기준을 보조로 참고한다.",),
            tags=("strategy", "md"),
            score=100,
        )
        compliance = EvidenceItem(
            id="REF-LAW-001",
            kind="general",
            source="개인정보보호위원회 개인정보 보호법 안내",
            title="컴플라이언스 근거",
            summary="개인정보 수집 동의와 보관 제한 기준",
            signals=("개인정보", "동의", "보관"),
            evidence=("개인정보 보호 기준",),
            tags=("compliance",),
            score=80,
        )
        benchmark = EvidenceItem(
            id="REF-BM-001",
            kind="benchmark",
            source="경쟁사 벤치마킹 결과",
            title="벤치마킹 근거",
            summary="타사 서비스 비교",
            signals=("비교",),
            evidence=("참고 후보",),
            tags=("benchmark",),
            score=80,
        )
        channel_direction = EvidenceItem(
            id="REF-CHANNEL-DIRECTION-001",
            kind="strategy",
            source="채널 방향성.pdf",
            title="채널 방향성",
            summary="NC 채널 전략과 고객 과업 기준",
            signals=("전략",),
            evidence=("채널 방향성 기준",),
            tags=("strategy", "pdf"),
            score=80,
        )
        tk_definition = EvidenceItem(
            id="REF-TK-001",
            kind="strategy",
            source="TK_ CH_주문_고객 주문경험 혁신 프로세스 재설계.pdf",
            title="TK 과제정의",
            summary="주문 경험 재설계 기준",
            signals=("과제정의",),
            evidence=("TK 기준",),
            tags=("strategy", "pdf"),
            score=80,
        )
        sample = EvidenceItem(
            id="SAMPLE-001",
            kind="sample",
            source="샘플 정책서",
            title="샘플 구조",
            summary="샘플의 작성 밀도와 표 구성을 우선한다.",
            signals=("샘플",),
            evidence=("샘플 기준",),
            tags=("sample",),
            score=60,
        )

        self.assertEqual("authority:skt_official_auxiliary", evidence_source_authority(official))
        self.assertEqual(2, evidence_source_authority_tier(official))
        self.assertEqual("authority:compliance_reference", evidence_source_authority(compliance))
        self.assertEqual(3, evidence_source_authority_tier(compliance))
        self.assertEqual("authority:public_benchmark_reference", evidence_source_authority(benchmark))
        self.assertEqual(4, evidence_source_authority_tier(benchmark))
        self.assertEqual("authority:requirement_level_reference", evidence_source_authority(channel_direction))
        self.assertEqual("authority:requirement_level_reference", evidence_source_authority(tk_definition))
        self.assertEqual(1, evidence_source_authority_tier(channel_direction))
        self.assertEqual(100, evidence_authority_score(channel_direction))
        self.assertEqual("authority:attached_sample", evidence_source_authority(sample))
        self.assertEqual(evidence_authority_score(channel_direction), evidence_authority_score(tk_definition))
        self.assertGreater(evidence_authority_score(sample), evidence_authority_score(official))
        self.assertGreater(evidence_authority_score(official), evidence_authority_score(compliance))
        self.assertGreater(evidence_authority_score(compliance), evidence_authority_score(benchmark))

    def test_stage_selection_dedupes_repeated_reference_chunks(self):
        store = EvidenceStore(
            [
                *sample_store().items,
                EvidenceItem(
                    id="REF-IA-DUP-001",
                    kind="ia",
                    source="IA 분석 상세",
                    title="가입 정보 상세 흐름",
                    summary="가입 정보 IA는 회선 선택, 상태 확인, 상세 확인, 상담 전환 흐름으로 구성된다.",
                    signals=("IA", "프로세스", "상담 전환"),
                    evidence=("회선 선택 후 상세 정보로 진입한다.",),
                    tags=("ia", "source_chunk"),
                    score=95,
                ),
                EvidenceItem(
                    id="REF-IA-DUP-002",
                    kind="ia",
                    source="IA 분석 상세",
                    title="가입 정보 상세 흐름",
                    summary="가입 정보 IA는 회선 선택, 상태 확인, 상세 확인, 상담 전환 흐름으로 구성된다.",
                    signals=("IA", "프로세스", "상담 전환"),
                    evidence=("회선 선택 후 상세 정보로 진입한다.",),
                    tags=("ia", "source_chunk"),
                    score=94,
                ),
            ]
        )

        selected = store.select(
            stage="process",
            topic="나의 가입 정보",
            query_terms=("가입 정보", "프로세스", "IA", "상담 전환"),
            required_kinds=("requirement", "voc", "ia", "strategy", "guideline"),
            limit=8,
        )
        selected_ids = [item.id for item in selected]

        self.assertLessEqual(
            len([item_id for item_id in selected_ids if item_id.startswith("REF-IA-DUP")]),
            1,
        )
        self.assertIn("REQ-001", selected_ids)


def sample_store():
    return EvidenceStore(
        [
            EvidenceItem(
                id="REQ-001",
                kind="requirement",
                source="요구사항 통합 list",
                title="가입 정보 조회",
                summary="고객은 가입 회선, 약정, 요금제, 이용 상태를 한 흐름에서 확인해야 한다.",
                signals=("나의 가입 정보", "조회", "고객 확인"),
                evidence=("고객이 가입 정보를 확인한다.",),
                tags=("나의 가입 정보", "필수"),
                score=90,
            ),
            EvidenceItem(
                id="REF-VOC-001",
                kind="voc",
                source="고객 VoC",
                title="가입 정보 확인 불편",
                summary="고객은 가입 정보가 여러 메뉴에 흩어져 확인이 어렵고, 제한 사유 안내를 기대한다.",
                signals=("불편", "제한 사유", "고객 기대"),
                evidence=("가입 정보 확인 경로가 복잡하다.",),
                tags=("voc",),
                score=80,
            ),
            EvidenceItem(
                id="REF-IA-001",
                kind="ia",
                source="IA 분석",
                title="가입 정보 흐름",
                summary="가입 정보 IA는 회선 선택, 상태 확인, 상세 확인, 상담 전환 흐름으로 구성된다.",
                signals=("IA", "프로세스", "상담 전환"),
                evidence=("회선 선택 후 상세 정보로 진입한다.",),
                tags=("ia",),
                score=75,
            ),
            EvidenceItem(
                id="REF-STR-001",
                kind="strategy",
                source="채널 전략",
                title="셀프 처리 확대",
                summary="NC 채널은 고객 셀프 확인을 우선하고 BSS 판정, 제한 조건, 이력 저장 기준을 명확히 해야 한다.",
                signals=("BSS 판정", "제한 조건", "이력 저장"),
                evidence=("고객 셀프 처리 확대.",),
                tags=("strategy",),
                score=70,
            ),
            EvidenceItem(
                id="REF-STR-CHANNEL",
                kind="strategy",
                source="채널 방향성_공개웹_T월드_T멤버십_T다이렉트샵_T우주_통합지식",
                title="통합채널 공개웹 지식",
                summary="T월드는 회선·요금·납부·BSS 판정, T멤버십은 등급·혜택·쿠폰, T다이렉트샵은 구매·가입·배송·개통, T우주는 구독·정기결제·제휴 책임 기준으로 구분한다.",
                signals=("채널별 책임 경계", "상태·정책 판단축", "본문 범위 확장 금지"),
                evidence=("통합채널 공개웹 지식은 현재 주제의 판단축을 선명하게 하는 공통 맥락이다.",),
                tags=("strategy", "source_chunk"),
                score=20,
            ),
            EvidenceItem(
                id="GUIDE-AGENTS",
                kind="guideline",
                source="AGENTS.md",
                title="작성 기준",
                summary="유즈케이스, 프로세스, 기능, 정책 연결성을 유지한다.",
                signals=("정합성", "정책 구체성"),
                evidence=("연결성을 검수한다.",),
                tags=("guideline",),
                score=95,
            ),
            EvidenceItem(
                id="SAMPLE-BASELINE",
                kind="sample",
                source="input/samples",
                title="샘플 기준",
                summary="샘플처럼 간결한 표 구조와 명확한 정책 항목으로 작성한다.",
                signals=("샘플", "간결"),
                evidence=("정책 항목을 분리한다.",),
                tags=("sample",),
                score=90,
            ),
        ]
    )


def sample_spec():
    return {
        "meta": {
            "topic": "나의 가입 정보",
            "authoring_blueprint": {
                "chapter_blueprints": [
                    {"stage": "process", "target_requirement_ids": ["REQ-001"]},
                    {"stage": "policies", "target_requirement_ids": ["REQ-001"]},
                ],
                "requirement_cards": [
                    {"id": "REQ-001", "title": "가입 정보 조회", "summary": "고객이 가입 정보를 확인한다."}
                ],
            },
        },
        "actors": [{"id": "ACT-INFO-001", "name": "고객", "type": "human"}],
        "usecases": [{"id": "US-INFO-001", "name": "가입 정보 확인", "actor": "고객", "process_target": "Y"}],
        "states": [{"id": "ST-INFO-001", "name": "조회 가능", "description": "상세 조회가 가능한 상태."}],
        "processes": [],
        "functions": [],
        "policy_groups": [],
        "policy_details": [],
        "trace_matrix": [],
        "evidence_gaps": [],
    }


def sample_learning():
    return {
        "customer_tasks": ["가입 정보를 확인한다."],
        "policy_risks": ["권한 없는 회선 정보 노출을 제한한다."],
        "bss_implications": ["BSS 권한 판정과 상태 회신을 반영한다."],
        "decision_axes": ["조회 허용 조건과 제한 사유 고지 기준을 정의한다."],
    }


if __name__ == "__main__":
    unittest.main()
