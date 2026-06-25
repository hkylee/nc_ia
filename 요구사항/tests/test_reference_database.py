import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.policy_references import (
    categorize_reference,
    clean_pdf_page_text,
    ensure_reference_database,
    ensure_project_source_database,
    extract_xlsx_text,
    guarded_vector_boost,
    html_to_text,
    is_requirement_level_reference,
    load_reference_insights_for_topic,
    reference_chunk_quality_penalty,
    reference_chunk_quality_tags,
    reference_vector_unanchored_max_boost,
    topic_keywords,
)


class ReferenceDatabaseTest(unittest.TestCase):
    def test_current_requirements_xlsx_extracts_visible_text(self):
        requirements_path = Path("input/requirements/20260509_요구사항 최종.xlsx")
        text = extract_xlsx_text(requirements_path, [])

        self.assertIn("요구사항 통합 list", text)
        self.assertIn("상세 요구사항명", text)

    def test_indexes_documents_pages_chunks_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            references_dir = root / "references"
            references_dir.mkdir()
            (references_dir / "AI 검색 고객 VoC.txt").write_text(
                "AI 검색 고객은 검색 결과가 부정확할 때 상담 전환과 재검색 안내를 기대한다.\n"
                "BSS 연계 결과가 지연되면 보류 상태와 재시도 기준을 안내해야 한다.\n"
                "정책은 추천 근거, 제한 사유, 이력 저장 기준을 함께 정의해야 한다.",
                encoding="utf-8",
            )
            db_path = root / "reference_evidence.db"

            ensure_reference_database(references_dir, db_path)

            with sqlite3.connect(db_path) as conn:
                document_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
                page_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
                chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                evidence_count = conn.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0]
                embedding_table_count = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chunk_embeddings'"
                ).fetchone()[0]

            self.assertEqual(document_count, 1)
            self.assertGreaterEqual(page_count, 1)
            self.assertGreaterEqual(chunk_count, 1)
            self.assertGreaterEqual(evidence_count, 1)
            self.assertEqual(embedding_table_count, 1)

    def test_project_source_database_indexes_requirements_templates_and_samples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for folder in ("references", "requirements", "templates", "samples"):
                (root / "input" / folder).mkdir(parents=True, exist_ok=True)
            (root / "input" / "references" / "채널 방향성.txt").write_text(
                "통합채널은 고객 과업을 목적 기반으로 정리한다.",
                encoding="utf-8",
            )
            (root / "input" / "requirements" / "요구사항 목록.txt").write_text(
                "요구사항 통합 list 회원 가입 상태 전이 정책 기준",
                encoding="utf-8",
            )
            (root / "input" / "templates" / "간소화 템플릿.html").write_text(
                "<html><body><div class='guide-title'>작성 가이드</div><table><tr><td>정책 상세</td></tr></table></body></html>",
                encoding="utf-8",
            )
            (root / "input" / "samples" / "샘플 정책서.html").write_text(
                "<html><body><h1>샘플 정책서</h1><p>정책 항목은 실제 기준값으로 작성한다.</p></body></html>",
                encoding="utf-8",
            )
            db_path = root / "reference_evidence.db"

            ensure_project_source_database(root, db_path)

            with sqlite3.connect(db_path) as conn:
                counts = dict(
                    conn.execute("SELECT category, COUNT(*) FROM documents GROUP BY category").fetchall()
                )

            self.assertEqual(counts.get("strategy"), 1)
            self.assertEqual(counts.get("requirement"), 1)
            self.assertEqual(counts.get("template"), 1)
            self.assertEqual(counts.get("sample"), 1)

    def test_project_source_database_indexes_completed_analysis_synthesis_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for folder in ("references", "requirements", "templates", "samples"):
                (root / "input" / folder).mkdir(parents=True, exist_ok=True)
            analysis_dir = root / "output" / "reference_html"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "benchmarking.html").write_text(
                "<html><body><h1>벤치마킹 결과</h1><p>통합채널 정책서는 비교, 선택, 실행, 완료 흐름을 고객 과업 기준으로 재구성해야 한다. "
                "벤치마킹 분석은 정책 판단축, 예외 처리, 안내 기준으로 환원한다.</p></body></html>",
                encoding="utf-8",
            )
            (analysis_dir / "voc-auto-payment-apply.html").write_text(
                "<html><body><h1>자동 납부 VoC 분석</h1><p>고객은 자동 납부 신청과 변경 과정에서 적용 시점, 실패 복구, 결과 고지를 명확히 확인해야 한다. "
                "정책서는 상태, 알림, 이력 저장 기준을 함께 정의한다.</p></body></html>",
                encoding="utf-8",
            )
            (analysis_dir / "screen-flow.html").write_text(
                "<html><body><h1>화면 Flow</h1><p>작성 예정입니다.</p></body></html>",
                encoding="utf-8",
            )
            (analysis_dir / "tk-task-01.html").write_text(
                "<html><body><h1>TK 과제 정의</h1><p>과제 정의 설명형 HTML은 별도 지식화 대상이 아니다.</p></body></html>",
                encoding="utf-8",
            )
            db_path = root / "reference_evidence.db"

            ensure_project_source_database(root, db_path)

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT source_name, category FROM documents ORDER BY source_name"
                ).fetchall()

            self.assertEqual(
                rows,
                [
                    ("benchmarking.html", "analysis_synthesis"),
                    ("voc-auto-payment-apply.html", "analysis_synthesis"),
                ],
            )

    def test_reference_reindex_preserves_non_reference_source_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            references_dir = root / "input" / "references"
            templates_dir = root / "input" / "templates"
            references_dir.mkdir(parents=True)
            templates_dir.mkdir(parents=True)
            (references_dir / "채널 방향성.txt").write_text("채널 전략과 고객 과업", encoding="utf-8")
            template_path = templates_dir / "간소화 템플릿.html"
            template_path.write_text("<html><body>작성 가이드 정책 상세</body></html>", encoding="utf-8")
            db_path = root / "reference_evidence.db"

            ensure_project_source_database(root, db_path)
            ensure_reference_database(references_dir, db_path)

            with sqlite3.connect(db_path) as conn:
                template_count = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE category = 'template'"
                ).fetchone()[0]

            self.assertEqual(template_count, 1)

    def test_html_to_text_keeps_visible_guide_text_without_css(self):
        text = html_to_text(
            "<html><style>.guide{color:red}</style><body><div class='guide-title'>작성 가이드</div>"
            "<table><tr><th>정책 ID</th><td>PG-001</td></tr></table></body></html>"
        )

        self.assertIn("작성 가이드", text)
        self.assertIn("정책 ID", text)
        self.assertIn("PG-001", text)
        self.assertNotIn("color:red", text)

    def test_pdf_page_cleaner_removes_confluence_chrome_but_keeps_body(self):
        raw = "\n".join(
            [
                "📢 ( 신규 ) TDE Insights 서비스  제공  알림  →",
                " 페이지/ …/ 54000. To Be 과제정의",
                "작성자 : 홍길동  Next 플랫폼기획 2 팀, 마지막  업데이트 : 2026 04 27, • 9 분  읽기",
                "TK_ CH_AI 기반 탐색 추천 전시 및 데이터 트래킹 체계",
                "과제 목적 고객 맥락에 맞는 추천과 실행 제안을 제공한다.",
                "정책 기준 고객 행동 이력은 추천 사유와 함께 저장한다.",
                "\uf108\uf105",
                "26. 5. 7. 오후 9:26 TK_ CH_AI 기반 탐색 - SUPER CH - TDE 2.0 Conﬂuence",
                "https://conﬂuence.tde.sktelecom.com/spaces/SUPERCHPJT/pages/123 1/6",
            ]
        )

        text = clean_pdf_page_text(Path("sample.pdf"), 1, raw)

        self.assertIn("과제 목적", text)
        self.assertIn("정책 기준", text)
        self.assertNotIn("TDE Insights", text)
        self.assertNotIn("마지막 업데이트", text)
        self.assertNotIn("conﬂuence.tde", text)

    def test_reference_chunk_quality_penalizes_footer_or_upload_residue(self):
        noisy = "레이블 없음 https://conﬂuence.tde.sktelecom.com 파일 찾아보기"
        useful = "고객은 결제 실패 시 재시도 기준과 처리 보류 상태를 확인해야 한다. 정책은 이력 저장 기준을 포함한다."

        self.assertGreater(reference_chunk_quality_penalty(noisy), reference_chunk_quality_penalty(useful))
        self.assertIn("quality:low_signal", reference_chunk_quality_tags(noisy))
        self.assertNotIn("quality:low_signal", reference_chunk_quality_tags(useful))

    def test_loader_uses_database_chunked_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            references_dir = root / "references"
            references_dir.mkdir()
            (references_dir / "요금 안내 고객 조사.txt").write_text(
                "요금 안내 고객은 청구 금액, 할인 반영, 납부 예정 금액을 한 번에 확인하길 원한다.\n"
                "오류나 지연이 있으면 납부 보류 사유와 후속 문의 경로를 안내해야 한다.",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"NC_REFERENCE_VECTOR_ENABLED": "0"}, clear=False):
                insights = load_reference_insights_for_topic(
                    "요금 안내서",
                    references_dir,
                    database_path=root / "reference_evidence.db",
                )

            self.assertTrue(insights)
            self.assertIn("database_chunked_full_document", insights[0].read_scope)
            self.assertTrue(insights[0].source_text)

    def test_global_reference_categories_follow_source_name(self):
        self.assertEqual(categorize_reference("채널 방향성.pdf", "IA 메뉴 구조"), "strategy")
        self.assertEqual(categorize_reference("벤치마킹 결과.pdf", "IA 메뉴 구조"), "benchmark")
        self.assertEqual(categorize_reference("고객조사 결과.pdf", "문의 불편"), "research")
        self.assertEqual(categorize_reference("채널 AI 경험 검토_CX팀.pdf", "고객 문의"), "ai")
        self.assertEqual(categorize_reference("요금제 변경 - 고객 VoC 분석.pdf", "고객 문의"), "voc")
        self.assertEqual(categorize_reference("1순위_첨부자료사내자료요구사항_정책작성체크포인트.md", ""), "guideline")
        self.assertEqual(categorize_reference("2순위_SKT공식서비스약관고객지원_정책체크포인트.md", "tworld.co.kr"), "official")

    def test_channel_direction_and_tk_pdfs_are_requirement_level_references(self):
        self.assertTrue(is_requirement_level_reference("채널 방향성.pdf"))
        self.assertTrue(is_requirement_level_reference("TK_ CH_주문_고객 주문경험 혁신 프로세스 재설계.pdf"))
        self.assertFalse(is_requirement_level_reference("벤치마킹 결과.pdf"))

    def test_compound_topic_keywords_support_joined_korean_topics(self):
        keywords = topic_keywords("선물주문")

        self.assertIn("선물주문", keywords)
        self.assertIn("선물", keywords)
        self.assertIn("주문", keywords)
        self.assertIn("선물 주문", keywords)

    def test_compound_topic_keywords_improve_reference_selection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            references_dir = root / "references"
            references_dir.mkdir()
            (references_dir / "데이터 선물 고객 VoC.txt").write_text(
                "데이터 선물 고객은 선물 가능 대상과 수신 완료 여부를 명확히 확인하길 원한다.\n"
                "선물 실패 시 재시도, 취소, 고객 고지 기준을 정책으로 정의해야 한다.",
                encoding="utf-8",
            )

            insights = load_reference_insights_for_topic(
                "선물주문",
                references_dir,
                database_path=root / "reference_evidence.db",
            )

            self.assertTrue(insights)
            self.assertIn("선물", insights[0].source_text)

    def test_vector_enabled_loader_stores_embeddings_and_marks_hybrid_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            references_dir = root / "references"
            references_dir.mkdir()
            (references_dir / "요금 안내 고객 조사.txt").write_text(
                "고객은 청구 금액과 할인 반영, 납부 예정 금액을 한 번에 이해하길 원한다.\n"
                "납부 지연이나 보류 사유가 있으면 후속 문의 경로를 함께 안내해야 한다.",
                encoding="utf-8",
            )
            db_path = root / "reference_evidence.db"

            def fake_embeddings(texts, model):
                return [[1.0, 0.0] for _ in texts]

            with patch.dict(
                "os.environ",
                {
                    "NC_REFERENCE_VECTOR_ENABLED": "1",
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_EMBEDDING_MODEL": "test-embedding-model",
                },
                clear=False,
            ), patch("src.policy_references.request_openai_embeddings", side_effect=fake_embeddings):
                insights = load_reference_insights_for_topic("요금 안내서", references_dir, database_path=db_path)

            with sqlite3.connect(db_path) as conn:
                embedding_count = conn.execute("SELECT COUNT(*) FROM chunk_embeddings").fetchone()[0]

            self.assertTrue(insights)
            self.assertIn("database_hybrid_vector", insights[0].read_scope)
            self.assertGreaterEqual(embedding_count, 1)

    def test_vector_boost_is_capped_when_keyword_anchor_is_missing(self):
        with patch.dict(
            "os.environ",
            {
                "NC_REFERENCE_VECTOR_WEIGHT": "70",
                "NC_REFERENCE_VECTOR_UNANCHORED_MAX_BOOST": "6",
                "NC_REFERENCE_VECTOR_MIN_SIMILARITY": "0.68",
                "NC_REFERENCE_VECTOR_ANCHOR_MIN_SCORE": "4",
            },
            clear=False,
        ):
            boost, guard = guarded_vector_boost(0.99, 0)

        self.assertEqual("capped", guard)
        self.assertEqual(reference_vector_unanchored_max_boost(), boost)


if __name__ == "__main__":
    unittest.main()
