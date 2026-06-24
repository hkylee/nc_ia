import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.channel_pi_status import (
    analysis_item_score,
    analysis_item_status,
    build_channel_pi_status_report,
    evaluate_trace_bridge,
    extract_requirement_ids,
    latest_policy_spec_records,
    policy_trace_stats,
    trace_supported_alignment_score,
)


class ChannelPiStatusTest(unittest.TestCase):
    def test_channel_pi_status_uses_latest_specs_and_alignment_agent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "output"
            output_root.mkdir()
            evidence_db = root / "reference_evidence.db"
            requirements_db = root / "requirements.db"
            self._write_reference_db(evidence_db)
            self._write_requirements_db(requirements_db)

            self._write_spec(output_root / "NC_AI검색_정책서_간소화_v0.10_spec.json", "AI 검색", "v0.10", keyword="검색")
            self._write_spec(output_root / "NC_AI검색_정책서_간소화_v0.11_spec.json", "AI 검색", "v0.11", keyword="추천")
            self._write_spec(output_root / "NC_추천_정책서_간소화_v0.10_spec.json", "추천", "v0.10", keyword="추천")

            records = latest_policy_spec_records(output_root)
            report = build_channel_pi_status_report(
                output_root=output_root,
                evidence_db_path=evidence_db,
                requirements_db_path=requirements_db,
            )

        self.assertEqual(len(records), 2)
        self.assertEqual(report["alignmentAgent"], "분석-정책 정렬 진단")
        self.assertEqual(report["topicCount"], 2)
        self.assertGreaterEqual(report["score"], 0)
        self.assertTrue(report["dimensions"])
        self.assertEqual(len(report["dimensions"]), 6)
        self.assertTrue(report["sourceCoverage"])
        self.assertTrue(any(item["id"] == "analysis-requirement" for item in report["dimensions"]))
        self.assertTrue(any(item["id"] == "requirement-policy" for item in report["dimensions"]))
        self.assertTrue(any(item["id"] == "bridge-continuity" for item in report["dimensions"]))
        self.assertTrue(any(item["id"] == "analysis-item-coverage" for item in report["dimensions"]))
        self.assertTrue(any(item["id"] == "cross-validation" for item in report["dimensions"]))
        self.assertTrue(any(item["id"] == "requirement-trace" for item in report["dimensions"]))
        excluded_dimension_ids = {
            "alignment-agent",
            "analysis-policy",
            "policy-grounding",
            "policy-specificity",
            "analysis-readiness",
        }
        self.assertFalse(excluded_dimension_ids.intersection(item["id"] for item in report["dimensions"]))
        self.assertTrue(any(row["topic"] == "AI 검색" and row["version"] == "v0.11" for row in report["topicRows"]))
        self.assertTrue(all("analysisRequirementCoverageRate" in row for row in report["topicRows"]))
        self.assertTrue(all("requirementPolicyTraceRate" in row for row in report["topicRows"]))
        self.assertTrue(all("traceContinuityRate" in row for row in report["topicRows"]))
        self.assertEqual(report["analysisItemCoverageSummary"]["total"], 1)
        self.assertEqual(len(report["analysisItemCoverage"]), 1)
        self.assertTrue(report["analysisItemCoverage"][0]["policyMatches"])
        self.assertTrue(report["analysisItemCoverage"][0]["requirementMatches"])
        self.assertIn("trustedCoverageRate", report["crossValidation"])
        self.assertIn("findings", report["crossValidation"])
        self.assertEqual(report["requirements"]["detailCount"], 2)

    def test_trace_stats_separates_group_trace_from_detail_id_trace(self):
        spec = {
            "meta": {"requirements_count": 10},
            "functions": [{"id": "FN-001"}],
            "trace_matrix": [
                {
                    "requirement_group": "그룹 단위 요구",
                    "detail_requirement_count": 10,
                    "sample_detail_requirements": ["요구 A", "요구 B"],
                    "mapped_to": ["FN-001"],
                    "coverage": "반영",
                }
            ],
        }

        stats = policy_trace_stats(spec)

        self.assertEqual(stats["coverageRate"], 100)
        self.assertEqual(stats["directRequirementIdCount"], 0)
        self.assertEqual(stats["groupedRequirementTraceRowCount"], 1)
        self.assertLess(stats["traceSchemaCompletenessRate"], 70)
        self.assertIn(stats["traceConfidenceLabel"], {"낮음", "추정"})

    def test_trace_stats_counts_direct_detail_ids_as_high_confidence(self):
        spec = {
            "meta": {"requirements_count": 2},
            "functions": [{"id": "FN-001"}],
            "policy_details": [{"id": "PI-001"}],
            "trace_matrix": [
                {"detail_id": "REQ-1", "mapped_to": ["FN-001"], "coverage": "반영"},
                {"detail_id": "REQ-2", "mapped_to": ["PI-001"], "coverage": "반영"},
            ],
        }

        stats = policy_trace_stats(spec)

        self.assertEqual(stats["directRequirementIdCount"], 2)
        self.assertEqual(stats["directRequirementTraceRate"], 100)
        self.assertEqual(stats["traceConfidenceLabel"], "높음")

    def test_trace_supported_alignment_uses_structured_trace_as_second_opinion(self):
        score = trace_supported_alignment_score(
            raw_score=55,
            alignment_report={"analysisCoverageRate": 55, "policyGroundingRate": 54},
            trace_stats={"directRequirementTraceRate": 100, "traceConfidenceScore": 91},
            trace_bridge={
                "analysisRequirementCoverageRate": 75,
                "requirementPolicyTraceRate": 97,
                "traceContinuityRate": 82,
            },
        )

        self.assertGreaterEqual(score, 80)
        self.assertEqual(analysis_item_status(0.02, 0.14, True), "covered")
        self.assertGreaterEqual(analysis_item_score("covered", 0.02, 0.14, True), 82)

    def test_trace_bridge_rewards_explicit_analysis_evidence_ids(self):
        spec = {
            "meta": {"requirements_count": 1},
            "functions": [{"id": "FN-001"}],
            "trace_matrix": [
                {
                    "detail_id": "REQ-1",
                    "detail_name": "설정 경로",
                    "mapped_to": ["FN-001"],
                    "analysis_evidence_ids": ["EV-1"],
                    "coverage": "반영",
                }
            ],
        }
        trace_stats = policy_trace_stats(spec)
        bridge = evaluate_trace_bridge(
            spec,
            [{"detailId": "REQ-1", "detailName": "설정 경로", "policyMappingStatus": "FN-001"}],
            [
                {
                    "id": "EV-1",
                    "sourceName": "analysis.html",
                    "sourceGroup": "고객 조사",
                    "summary": "고객은 설정 경로를 쉽게 찾아야 한다.",
                    "tokens": {"고객": 1, "설정": 1, "경로": 1},
                }
            ],
            trace_stats,
        )

        self.assertEqual(bridge["traceContinuityRate"], 100)
        self.assertFalse(bridge["items"])

    def test_requirement_id_extractor_keeps_spaced_excel_ids(self):
        self.assertEqual(extract_requirement_ids("khmi 00-001"), ["khmi 00-001"])
        self.assertEqual(extract_requirement_ids("MBS_01-001"), ["MBS_01-001"])
        self.assertEqual(extract_requirement_ids("PM-23-UNMAPPED-001"), ["PM-23-UNMAPPED-001"])

    def _write_spec(self, path: Path, topic: str, version: str, *, keyword: str) -> None:
        slug = topic.replace(" ", "")
        spec = {
            "meta": {
                "topic": slug,
                "topic_display": topic,
                "version": version,
                "requirements_count": 2,
            },
            "overview": {
                "scope": [f"고객이 {keyword} 목적을 기준으로 정보를 확인하고 실행까지 연결한다."],
                "principles": [{"name": "목적 기반 경험", "description": f"{keyword} 맥락을 고객 과업 기준으로 정렬한다."}],
            },
            "usecases": [
                {"id": f"US-{slug}-001", "actor": "고객", "name": f"{keyword} 기반 의사결정", "description": "고객이 근거를 확인하고 실행한다."}
            ],
            "processes": [
                {"id": f"PR-{slug}-001", "name": f"{keyword} 조건 확인", "description": "고객 조건과 실행 가능 여부를 확인한다."}
            ],
            "functions": [
                {"id": f"FN-{slug}-001", "name": f"{keyword} 근거 구성", "description": "분석 근거와 실행 경로를 함께 구성한다."}
            ],
            "policy_groups": [
                {"id": f"PG-{slug}-001", "name": f"{keyword} 판단 정책", "description": "고객 조건과 근거 표시 기준을 관리한다.", "items": [{"id": f"PI-{slug}-001", "name": "근거 표시"}]}
            ],
            "policy_details": [
                {"id": f"PI-{slug}-001", "policy_id": f"PG-{slug}-001", "name": "근거 표시", "content": f"{keyword} 결과에는 고객 조건, 제한 사유, 실행 경로를 함께 표시한다."}
            ],
            "trace_matrix": [
                {
                    "requirement_group": f"{keyword} 요구",
                    "detail_requirement_count": 2,
                    "mapped_to": [f"US-{slug}-001", f"FN-{slug}-001", f"PI-{slug}-001"],
                    "coverage": "반영",
                }
            ],
        }
        path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

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
                ("DOC-1", "analysis.html", "analysis_synthesis"),
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
                    "검색과 추천은 고객 목적, 실행 경로, 제한 사유를 함께 설명해야 한다.",
                    json.dumps(["검색", "추천", "실행 경로"], ensure_ascii=False),
                    json.dumps(["AI 검색", "추천"], ensure_ascii=False),
                    json.dumps(["overview", "process", "functions", "policies"], ensure_ascii=False),
                    0.9,
                    "고객은 탐색과 추천 결과에서 근거를 확인한 뒤 실행으로 이어져야 한다.",
                ),
            )

    def _write_requirements_db(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.executescript(
                """
                create table requirement_rows (
                  detail_id text,
                  normalized_depth4 text,
                  detail_name text,
                  detail_description text,
                  parent_name text,
                  parent_description text,
                  policy_mapping_status text
                );
                """
            )
            conn.executemany(
                """
                insert into requirement_rows(
                  detail_id, normalized_depth4, detail_name, detail_description,
                  parent_name, parent_description, policy_mapping_status
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("REQ-1", "AI 검색", "검색 실행 경로", "고객이 검색 결과에서 실행 경로와 제한 사유를 확인한다.", "검색 요구", "검색 목적 기반 의사결정", "AI 검색 정책서 반영"),
                    ("REQ-2", "추천", "추천 근거 표시", "고객이 추천 결과의 근거와 실행 가능 여부를 확인한다.", "추천 요구", "추천 목적 기반 의사결정", "추천 정책서 반영"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
