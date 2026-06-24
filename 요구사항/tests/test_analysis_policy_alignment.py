import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.analysis_policy_alignment import build_analysis_policy_alignment_report


class AnalysisPolicyAlignmentTest(unittest.TestCase):
    def test_alignment_report_checks_both_directions(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "reference_evidence.db"
            self._write_reference_db(db_path)

            spec = {
                "meta": {"topic": "상품 상세/담기", "topic_display": "상품 상세/담기"},
                "overview": {
                    "scope": [
                        "고객이 상품을 탐색하고 비교한 뒤 장바구니에 담기까지 셀프 처리할 수 있도록 범위를 정의한다."
                    ],
                    "principles": [
                        {
                            "name": "목적 기반 탐색",
                            "description": "검색, 비교, 추천, 담기 흐름을 고객 과업 기준으로 연결한다.",
                        }
                    ],
                },
                "usecases": [
                    {
                        "id": "US-001",
                        "actor": "고객",
                        "name": "상품 비교 후 담기",
                        "description": "고객이 상품 조건을 비교하고 추천 근거를 확인한 뒤 장바구니에 담는다.",
                    }
                ],
                "processes": [
                    {
                        "id": "PR-001",
                        "name": "탐색 조건 확인 및 비교",
                        "description": "고객 목적, 상태, 최근 행동을 기준으로 상품 탐색 조건과 비교 기준을 구성한다.",
                    }
                ],
                "functions": [
                    {
                        "id": "FN-001",
                        "name": "추천 비교 정보 구성",
                        "description": "상품 추천 근거, 가격, 혜택, 제한 조건을 함께 구성한다.",
                    }
                ],
                "policy_groups": [
                    {
                        "id": "PG-001",
                        "name": "추천 및 비교 정책",
                        "description": "AI 추천, 상품 비교, 담기 가능 여부 기준을 관리한다.",
                        "items": [{"id": "PI-001", "name": "추천 근거 표시"}],
                    }
                ],
                "policy_details": [
                    {
                        "id": "PI-001",
                        "policy_id": "PG-001",
                        "name": "추천 근거 표시",
                        "content": "AI 추천은 고객 목적, 혜택, 가격, 가입 가능 조건과 제한 사유를 함께 표시한다.",
                    },
                    {
                        "id": "PI-999",
                        "policy_id": "PG-999",
                        "name": "우주선 정비 기준",
                        "content": "우주선 엔진 정비와 발사대 점검 기준을 관리한다.",
                    },
                ],
            }

            report = build_analysis_policy_alignment_report(
                spec=spec,
                policy_file_name="NC_상품상세담기_정책서_간소화_v0.10.html",
                evidence_db_path=db_path,
            )

        self.assertEqual(report["agent"], "분석-정책 정렬 Check")
        self.assertGreater(report["analysisCoverageRate"], 0)
        self.assertGreater(report["policyGroundingRate"], 0)
        self.assertTrue(report["analysisToPolicy"])
        self.assertTrue(report["policyToAnalysis"])
        self.assertTrue(any(item["status"] in {"covered", "partial"} for item in report["analysisToPolicy"]))
        self.assertTrue(any(item["id"] == "PI-999" for item in report["policyToAnalysis"]))
        self.assertTrue(report["actionItems"])

    def _write_reference_db(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                create table documents (
                  document_id text primary key,
                  source_name text,
                  category text
                );
                create table evidence_items (
                  evidence_id text primary key,
                  chunk_id text,
                  document_id text,
                  evidence_type text,
                  summary text,
                  signals text,
                  related_topics text,
                  related_chapters text,
                  confidence real,
                  evidence_text text
                );
                """
            )
            conn.execute(
                "insert into documents(document_id, source_name, category) values (?, ?, ?)",
                ("DOC-1", "benchmarking.html", "analysis_synthesis"),
            )
            conn.execute(
                """
                insert into evidence_items(
                  evidence_id, chunk_id, document_id, evidence_type, summary,
                  signals, related_topics, related_chapters, confidence, evidence_text
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "EV-1",
                    "CH-1",
                    "DOC-1",
                    "analysis_synthesis",
                    "고객 목적 기반 탐색과 상품 비교, AI 추천 근거 표시가 통합채널의 핵심 설계 축이다.",
                    json.dumps(["고객 목적 기반 진입", "AI 추천 근거", "상품 비교"], ensure_ascii=False),
                    json.dumps(["상품 상세/담기", "추천"], ensure_ascii=False),
                    json.dumps(["overview", "process", "functions", "policies"], ensure_ascii=False),
                    0.9,
                    "검색, 비교, 추천, 담기 흐름을 하나의 고객 과업으로 연결해야 한다.",
                ),
            )


if __name__ == "__main__":
    unittest.main()
