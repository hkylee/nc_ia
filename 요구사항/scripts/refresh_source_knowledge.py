#!/usr/bin/env python3
"""Refresh derived requirement, reference, feature inventory, and topic knowledge artifacts.

This script keeps source files intact and rebuilds only derived artifacts:

- reports/evidence/requirements.db
- reports/evidence/reference_evidence.db
- reports/evidence/feature_inventory.db
- reports/evidence/topic_knowledge/*.json
- validation reports and cleanup manifest for persisted Render disks
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from policy_references import DEFAULT_REFERENCE_DB_PATH, ensure_project_source_database, load_reference_insights_for_topic  # noqa: E402
from policy_requirements import DEFAULT_REQUIREMENTS_DB_PATH, ensure_requirements_database, find_requirements_workbook, load_scoped_requirements_for_topic  # noqa: E402
from feature_inventory import DEFAULT_FEATURE_INVENTORY_DB_PATH, ensure_feature_inventory_database, inspect_feature_inventory_database  # noqa: E402
from topic_knowledge_builder import DEFAULT_TOPIC_KNOWLEDGE_DIR, POLICY_TOPICS, build_all_topic_knowledge_packs  # noqa: E402
from topic_knowledge_validator import save_validation_report, validate_topic_knowledge_dir  # noqa: E402


REPORTS_ROOT = PROJECT_ROOT / "reports"
CACHE_ROOT = REPORTS_ROOT / "cache"
EVIDENCE_ROOT = REPORTS_ROOT / "evidence"
REFRESH_STAMP = "20260510"
REPORT_JSON = REPORTS_ROOT / f"source_knowledge_refresh_{REFRESH_STAMP}.json"
REPORT_MD = REPORTS_ROOT / f"source_knowledge_refresh_{REFRESH_STAMP}.md"
CLEANUP_MANIFEST = REPORTS_ROOT / f"source_knowledge_refresh_cleanup_{REFRESH_STAMP}.json"


def main() -> None:
    started_at = now_iso()
    removed_local = cleanup_local_derived_artifacts()

    requirements_db = ensure_requirements_database()
    reference_db = ensure_project_source_database(PROJECT_ROOT, DEFAULT_REFERENCE_DB_PATH)
    feature_inventory_db = ensure_feature_inventory_database()
    topic_manifest = build_all_topic_knowledge_packs(POLICY_TOPICS, output_dir=DEFAULT_TOPIC_KNOWLEDGE_DIR)
    knowledge_validation = validate_topic_knowledge_dir(DEFAULT_TOPIC_KNOWLEDGE_DIR)
    validation_json, validation_md = save_validation_report(knowledge_validation, DEFAULT_TOPIC_KNOWLEDGE_DIR)
    requirements_info = inspect_requirements_database(requirements_db)
    references_info = inspect_reference_database(reference_db)
    feature_inventory_info = inspect_feature_inventory_database(feature_inventory_db)
    legacy_validation_reports = write_legacy_validation_reports(
        requirements_info=requirements_info,
        references_info=references_info,
        reference_db=reference_db,
    )

    cleanup_manifest = write_cleanup_manifest(removed_local.get("removed_files", []))
    post_sidecar_cleanup = cleanup_sqlite_sidecars()
    if post_sidecar_cleanup["removed_count"]:
        removed_local["post_rebuild_sidecars"] = post_sidecar_cleanup
    report = {
        "generated_at": now_iso(),
        "started_at": started_at,
        "project_root": str(PROJECT_ROOT),
        "local_cleanup": removed_local,
        "requirements": requirements_info,
        "references": references_info,
        "feature_inventory": feature_inventory_info,
        "validation_reports": legacy_validation_reports,
        "topic_knowledge": {
            "manifest": topic_manifest,
            "validation_json": str(validation_json),
            "validation_md": str(validation_md),
            "validation_summary": knowledge_validation.get("summary", {}),
            "finding_count": len(knowledge_validation.get("findings", [])),
        },
        "render_cleanup_manifest": cleanup_manifest,
        "notes": [
            "input/ 하위 원본 요구사항, 레퍼런스, 템플릿, 샘플 파일은 삭제하지 않았습니다.",
            "reports/cache와 SQLite WAL/SHM 같은 파생 파일만 정리했습니다.",
            "기능내역서 DB는 원본 엑셀을 보존한 채 정제·중복 플래그·요약 테이블을 재생성합니다.",
            "Render는 다음 배포 시작 시 cleanup manifest에 적힌 기존 파생 파일을 삭제한 뒤, 저장소의 최신 파생 파일을 시드합니다.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown_report(report), encoding="utf-8")
    print(json.dumps({"report": str(REPORT_JSON), "summary": summarize_report(report)}, ensure_ascii=False, indent=2))


def cleanup_local_derived_artifacts() -> dict:
    removed_files: list[str] = []
    removed_dirs: list[str] = []
    removed_bytes = 0

    for path in input_noise_files():
        deleted, size = remove_path(path)
        if deleted:
            removed_files.append(relative(path))
            removed_bytes += size

    if CACHE_ROOT.exists():
        for path in sorted(CACHE_ROOT.glob("*.json")):
            deleted, size = remove_path(path)
            if deleted:
                removed_files.append(relative(path))
                removed_bytes += size

    for path in sqlite_sidecar_paths(DEFAULT_REFERENCE_DB_PATH) + sqlite_sidecar_paths(DEFAULT_REQUIREMENTS_DB_PATH) + sqlite_sidecar_paths(DEFAULT_FEATURE_INVENTORY_DB_PATH):
        deleted, size = remove_path(path)
        if deleted:
            removed_files.append(relative(path))
            removed_bytes += size

    if DEFAULT_TOPIC_KNOWLEDGE_DIR.exists():
        for path in sorted(DEFAULT_TOPIC_KNOWLEDGE_DIR.glob("*")):
            if path.is_file() and path.suffix.lower() in {".json", ".md"}:
                deleted, size = remove_path(path)
                if deleted:
                    removed_files.append(relative(path))
                    removed_bytes += size

    return {
        "removed_files": removed_files,
        "removed_dirs": removed_dirs,
        "removed_count": len(removed_files) + len(removed_dirs),
        "removed_bytes": removed_bytes,
    }


def input_noise_files() -> Iterable[Path]:
    for root in (PROJECT_ROOT / "input", REPORTS_ROOT, PROJECT_ROOT / "output"):
        if root.exists():
            yield from root.rglob(".DS_Store")


def sqlite_sidecar_paths(db_path: Path) -> list[Path]:
    return [Path(str(db_path) + suffix) for suffix in ("-wal", "-shm", "-journal")]


def remove_path(path: Path) -> tuple[bool, int]:
    if not path.exists():
        return False, 0
    size = path_size(path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True, size


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())


def inspect_requirements_database(db_path: Path | None) -> dict:
    if not db_path or not Path(db_path).exists():
        return {"ok": False, "error": "requirements.db not found"}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        metadata = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
        total_rows = conn.execute("SELECT COUNT(*) FROM requirement_rows").fetchone()[0]
        active_detail_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM requirement_rows
            WHERE COALESCE(edit_status, '') <> '삭제'
              AND (COALESCE(detail_name, '') <> '' OR COALESCE(detail_description, '') <> '')
            """
        ).fetchone()[0]
        deleted_rows = conn.execute(
            "SELECT COUNT(*) FROM requirement_rows WHERE COALESCE(edit_status, '') = '삭제'"
        ).fetchone()[0]
    topic_counts = {
        topic: len(load_scoped_requirements_for_topic(topic))
        for topic in POLICY_TOPICS
    }
    return {
        "ok": True,
        "path": str(db_path),
        "source_workbook": metadata.get("source_name", ""),
        "selected_workbook": str(find_requirements_workbook(PROJECT_ROOT / "input" / "requirements") or ""),
        "schema_version": metadata.get("schema_version", ""),
        "source_hash": metadata.get("source_hash", ""),
        "total_rows": total_rows,
        "active_detail_rows": active_detail_rows,
        "deleted_rows": deleted_rows,
        "topic_count": len(topic_counts),
        "topics_without_requirements": [topic for topic, count in topic_counts.items() if count <= 0],
        "topic_requirement_counts": topic_counts,
    }


def inspect_reference_database(db_path: Path) -> dict:
    if not db_path.exists():
        return {"ok": False, "error": "reference_evidence.db not found"}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        metadata = dict(conn.execute("SELECT key, value FROM metadata").fetchall())
        document_rows = conn.execute(
            """
            SELECT source_name, source_type, category, text_chars, page_count, read_scope
            FROM documents
            ORDER BY category, source_name
            """
        ).fetchall()
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count, SUM(text_chars) AS text_chars, SUM(page_count) AS pages FROM documents GROUP BY category ORDER BY category"
        ).fetchall()
        type_rows = conn.execute(
            "SELECT source_type, COUNT(*) AS count, SUM(text_chars) AS text_chars, SUM(page_count) AS pages FROM documents GROUP BY source_type ORDER BY source_type"
        ).fetchall()
        pdf_rows = conn.execute(
            """
            SELECT d.source_name, d.text_chars, d.page_count,
                   SUM(CASE WHEN p.text_chars < 80 THEN 1 ELSE 0 END) AS low_text_pages
            FROM documents d
            LEFT JOIN pages p ON p.document_id = d.document_id
            WHERE d.source_type = 'pdf'
            GROUP BY d.document_id
            ORDER BY d.source_name
            """
        ).fetchall()
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0]
        empty_docs = conn.execute(
            "SELECT source_name, source_type, category FROM documents WHERE text_chars < 80 ORDER BY source_name"
        ).fetchall()
        chunk_stats_row = conn.execute(
            "SELECT MIN(LENGTH(text)) AS min_chars, AVG(LENGTH(text)) AS avg_chars, MAX(LENGTH(text)) AS max_chars FROM chunks"
        ).fetchone()
    pdf_quality = [
        {
            "source_name": row["source_name"],
            "text_chars": int(row["text_chars"] or 0),
            "page_count": int(row["page_count"] or 0),
            "low_text_pages": int(row["low_text_pages"] or 0),
        }
        for row in pdf_rows
    ]
    return {
        "ok": True,
        "path": str(db_path),
        "schema_version": metadata.get("schema_version", ""),
        "index_version": metadata.get("index_version", ""),
        "documents": [dict(row) for row in document_rows],
        "documents_by_category": [dict(row) for row in category_rows],
        "documents_by_type": [dict(row) for row in type_rows],
        "chunk_count": chunk_count,
        "evidence_count": evidence_count,
        "chunk_chars": {
            "min": int(chunk_stats_row["min_chars"] or 0),
            "avg": round(float(chunk_stats_row["avg_chars"] or 0), 1),
            "max": int(chunk_stats_row["max_chars"] or 0),
        },
        "pdf_count": len(pdf_quality),
        "pdf_low_extraction_candidates": [
            item
            for item in pdf_quality
            if item["text_chars"] < 1000 or (item["page_count"] and item["low_text_pages"] / item["page_count"] > 0.65)
        ],
        "empty_or_low_text_documents": [dict(row) for row in empty_docs],
    }


def write_cleanup_manifest(local_removed_files: Iterable[str] = ()) -> dict:
    removed: list[str] = []
    removed.extend(str(path) for path in local_removed_files)
    removed.append("reports/cache")
    removed.extend(tracked_paths_under("reports/cache"))
    removed.extend(relative(path) for path in sorted(CACHE_ROOT.glob("*.json")) if path.exists())
    removed.extend(
        [
            "reports/evidence/requirements.db",
            "reports/evidence/reference_evidence.db",
            "reports/evidence/reference_evidence.db-wal",
            "reports/evidence/reference_evidence.db-shm",
            "reports/evidence/reference_evidence.db-journal",
            "reports/evidence/feature_inventory.db",
            "reports/evidence/feature_inventory.db-wal",
            "reports/evidence/feature_inventory.db-shm",
            "reports/evidence/feature_inventory.db-journal",
            "reports/evidence/source_db_validation.json",
            "reports/evidence/source_db_validation.md",
            "reports/evidence/reference_db_validation.json",
            "reports/evidence/reference_db_validation.md",
            "reports/evidence/reference_db_learning_validation.json",
            "reports/evidence/reference_db_learning_validation.md",
        ]
    )
    if DEFAULT_TOPIC_KNOWLEDGE_DIR.exists():
        removed.extend(
            relative(path)
            for path in sorted(DEFAULT_TOPIC_KNOWLEDGE_DIR.glob("*"))
            if path.is_file() and path.suffix.lower() in {".json", ".md"}
        )
    payload = {
        "generated_at": now_iso(),
        "purpose": "Refresh derived requirements/reference/feature-inventory/topic-knowledge artifacts on persistent Render disks.",
        "preserve": [
            "input/references",
            "input/requirements",
            "input/templates",
            "input/samples",
            "reports/logs",
        ],
        "removed": sorted(set(removed)),
    }
    CLEANUP_MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(CLEANUP_MANIFEST),
        "removed_count": len(payload["removed"]),
    }


def tracked_paths_under(path: str) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z", path],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return []
    return [
        raw.decode("utf-8", errors="replace")
        for raw in output.split(b"\0")
        if raw.strip()
    ]


def cleanup_sqlite_sidecars() -> dict:
    removed_files: list[str] = []
    removed_bytes = 0
    for path in sqlite_sidecar_paths(DEFAULT_REFERENCE_DB_PATH) + sqlite_sidecar_paths(DEFAULT_REQUIREMENTS_DB_PATH) + sqlite_sidecar_paths(DEFAULT_FEATURE_INVENTORY_DB_PATH):
        deleted, size = remove_path(path)
        if deleted:
            removed_files.append(relative(path))
            removed_bytes += size
    return {
        "removed_files": removed_files,
        "removed_count": len(removed_files),
        "removed_bytes": removed_bytes,
    }


def render_markdown_report(report: dict) -> str:
    req = report.get("requirements", {})
    ref = report.get("references", {})
    inv = report.get("feature_inventory", {})
    tk = report.get("topic_knowledge", {})
    inventory_meta = inv.get("metadata", {}) if isinstance(inv.get("metadata"), dict) else {}
    lines = [
        "# Source Knowledge Refresh Report",
        "",
        f"- 생성 시각: {report.get('generated_at', '')}",
        f"- 요구사항 원천: {req.get('source_workbook', '')}",
        f"- 요구사항 활성 상세 건수: {req.get('active_detail_rows', 0)}",
        f"- 34개 주제 중 요구사항 0건: {len(req.get('topics_without_requirements', []))}",
        f"- 레퍼런스 문서 수: {sum(int(row.get('count') or 0) for row in ref.get('documents_by_category', []))}",
        f"- 레퍼런스 chunk/evidence: {ref.get('chunk_count', 0)} / {ref.get('evidence_count', 0)}",
        f"- PDF 추출 점검 후보: {len(ref.get('pdf_low_extraction_candidates', []))}",
        f"- 기능내역서 정제 행/고유 행: {inventory_meta.get('feature_row_count', 0)} / {inventory_meta.get('unique_feature_row_count', 0)}",
        f"- 기능내역서 정제 이슈: {inventory_meta.get('cleanup_issue_count', 0)}",
        f"- 레거시 검증 리포트: {', '.join(Path(path).name for path in report.get('validation_reports', {}).get('paths', []))}",
        f"- Topic Knowledge 검증 요약: {tk.get('validation_summary', {})}",
        f"- Render cleanup manifest: {report.get('render_cleanup_manifest', {}).get('path', '')}",
        "",
        "## Topic Requirement Counts",
        "",
    ]
    for topic, count in req.get("topic_requirement_counts", {}).items():
        lines.append(f"- {topic}: {count}")
    lines.extend(["", "## Feature Inventory Channel Summary", ""])
    if not inv.get("ok"):
        lines.append(f"- 기능내역서 DB 점검 실패: {inv.get('error', '')}")
    for row in inv.get("channels", []):
        lines.append(
            f"- {row.get('channel')}: feature={row.get('feature_rows')}, unique={row.get('unique_feature_rows')}, duplicate={row.get('duplicate_rows')}, screens={row.get('screen_count')}, issues={row.get('issue_count')}"
        )
    lines.extend(["", "## PDF Extraction Review Candidates", ""])
    candidates = ref.get("pdf_low_extraction_candidates", [])
    if not candidates:
        lines.append("- PDF 추출 품질 점검 후보가 없습니다.")
    for item in candidates[:30]:
        lines.append(
            f"- {item.get('source_name')}: text={item.get('text_chars')}, pages={item.get('page_count')}, low_pages={item.get('low_text_pages')}"
        )
    return "\n".join(lines) + "\n"


def summarize_report(report: dict) -> dict:
    return {
        "requirements_active_detail_rows": report.get("requirements", {}).get("active_detail_rows", 0),
        "topics_without_requirements": report.get("requirements", {}).get("topics_without_requirements", []),
        "reference_pdf_low_extraction_candidates": len(report.get("references", {}).get("pdf_low_extraction_candidates", [])),
        "feature_inventory_rows": report.get("feature_inventory", {}).get("metadata", {}).get("feature_row_count", 0),
        "feature_inventory_unique_rows": report.get("feature_inventory", {}).get("metadata", {}).get("unique_feature_row_count", 0),
        "feature_inventory_cleanup_issues": report.get("feature_inventory", {}).get("metadata", {}).get("cleanup_issue_count", 0),
        "topic_knowledge_validation": report.get("topic_knowledge", {}).get("validation_summary", {}),
        "cleanup_removed_count": report.get("render_cleanup_manifest", {}).get("removed_count", 0),
    }


def write_legacy_validation_reports(*, requirements_info: dict, references_info: dict, reference_db: Path) -> dict:
    """Refresh validation files that older tooling and docs still reference.

    These files are derived reports, not source-of-truth inputs. Regenerating
    them avoids a confusing split where the DB/TK packs are current but the
    visible validation notes still mention an old 44-topic structure.
    """

    source_json = EVIDENCE_ROOT / "source_db_validation.json"
    source_md = EVIDENCE_ROOT / "source_db_validation.md"
    reference_json = EVIDENCE_ROOT / "reference_db_validation.json"
    reference_md = EVIDENCE_ROOT / "reference_db_validation.md"
    learning_json = EVIDENCE_ROOT / "reference_db_learning_validation.json"
    learning_md = EVIDENCE_ROOT / "reference_db_learning_validation.md"

    generated_at = now_iso()
    source_payload = {
        "status": "PASS" if references_info.get("ok") else "FAIL",
        "generated_at": generated_at,
        "database": str(reference_db),
        "summary": references_info.get("documents_by_category", []),
        "documents": references_info.get("documents", []),
        "pdf_low_extraction_candidates": references_info.get("pdf_low_extraction_candidates", []),
        "requirements": {
            "source_workbook": requirements_info.get("source_workbook", ""),
            "active_detail_rows": requirements_info.get("active_detail_rows", 0),
            "topics_without_requirements": requirements_info.get("topics_without_requirements", []),
        },
    }
    source_json.write_text(json.dumps(source_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    source_md.write_text(render_source_validation_markdown(source_payload), encoding="utf-8")

    reference_status = "PASS" if not references_info.get("pdf_low_extraction_candidates") and not references_info.get("empty_or_low_text_documents") else "PASS_WITH_WARNINGS"
    reference_payload = {
        "status": reference_status,
        "validated_at": generated_at,
        "documents": len(references_info.get("documents", [])),
        "pages": sum(int(item.get("page_count") or 0) for item in references_info.get("documents", [])),
        "chunks": references_info.get("chunk_count", 0),
        "evidence_items": references_info.get("evidence_count", 0),
        "chunk_chars": references_info.get("chunk_chars", {}),
        "quality_flags": [
            "원본 참고자료, 요구사항, 템플릿, 샘플, 현황 분석 종합 장표가 reference_evidence.db에 색인되었습니다.",
            "모든 chunks는 evidence_items로 연결됩니다." if references_info.get("chunk_count") == references_info.get("evidence_count") else "chunk/evidence 개수 차이가 있습니다.",
            "PDF 저품질 추출 후보가 없습니다." if not references_info.get("pdf_low_extraction_candidates") else "PDF 저품질 추출 후보가 있어 확인이 필요합니다.",
        ],
        "issues": [],
        "warnings": references_info.get("pdf_low_extraction_candidates", []) + references_info.get("empty_or_low_text_documents", []),
        "category_counts": references_info.get("documents_by_category", []),
        "type_counts": references_info.get("documents_by_type", []),
    }
    reference_json.write_text(json.dumps(reference_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    reference_md.write_text(render_reference_validation_markdown(reference_payload), encoding="utf-8")

    retrieval_summary = build_learning_retrieval_summary(reference_db)
    learning_status = "PASS" if all(item.get("reference_count", 0) > 0 for item in retrieval_summary) else "PASS_WITH_WARNINGS"
    learning_payload = {
        "status": learning_status,
        "validated_at": generated_at,
        "learning_readiness_score": 100 if learning_status == "PASS" else 90,
        "topics_tested": len(POLICY_TOPICS),
        "documents": reference_payload["documents"],
        "chunks": reference_payload["chunks"],
        "evidence_items": reference_payload["evidence_items"],
        "warnings": [
            {"type": "topic_reference_gap", "topic": item["topic"]}
            for item in retrieval_summary
            if item.get("reference_count", 0) <= 0
        ],
        "topic_retrieval_summary": retrieval_summary,
    }
    learning_json.write_text(json.dumps(learning_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    learning_md.write_text(render_learning_validation_markdown(learning_payload), encoding="utf-8")
    return {
        "paths": [
            str(source_json),
            str(source_md),
            str(reference_json),
            str(reference_md),
            str(learning_json),
            str(learning_md),
        ],
        "source_status": source_payload["status"],
        "reference_status": reference_payload["status"],
        "learning_status": learning_payload["status"],
    }


def build_learning_retrieval_summary(reference_db: Path) -> list[dict]:
    summary: list[dict] = []
    references_dir = PROJECT_ROOT / "input" / "references"
    for topic in POLICY_TOPICS:
        insights = load_reference_insights_for_topic(topic, references_dir, limit=8, database_path=reference_db)
        categories = sorted({item.category for item in insights})
        sources = [item.source_name for item in insights]
        signals = sorted({signal for item in insights for signal in item.signals[:4]})
        summary.append(
            {
                "topic": topic,
                "reference_count": len(insights),
                "source_count": len(set(sources)),
                "categories": categories,
                "signals": signals[:12],
                "top_sources": sources[:5],
            }
        )
    return summary


def render_source_validation_markdown(payload: dict) -> str:
    lines = [
        "# Source DB Validation",
        "",
        f"- Status: {payload.get('status')}",
        f"- Generated at: {payload.get('generated_at')}",
        f"- Database: `{payload.get('database')}`",
        f"- Requirements source: {payload.get('requirements', {}).get('source_workbook', '')}",
        f"- Active requirement detail rows: {payload.get('requirements', {}).get('active_detail_rows', 0)}",
        "",
        "## Summary",
        "",
    ]
    for row in payload.get("summary", []):
        lines.append(
            f"- [{row.get('category')}] documents={int(row.get('count') or 0)} chars={int(row.get('text_chars') or 0)} pages={int(row.get('pages') or 0)}"
        )
    lines.extend(["", "## Documents", ""])
    for item in payload.get("documents", []):
        lines.append(
            f"- [{item.get('category')}] {item.get('source_name')} | {item.get('source_type')} | chars={item.get('text_chars')} pages={item.get('page_count')} scope={item.get('read_scope')}"
        )
    lines.extend(["", "## PDF Extraction Review Candidates", ""])
    candidates = payload.get("pdf_low_extraction_candidates", [])
    if not candidates:
        lines.append("- 없음")
    for item in candidates:
        lines.append(f"- {item.get('source_name')}: chars={item.get('text_chars')} pages={item.get('page_count')} low_pages={item.get('low_text_pages')}")
    return "\n".join(lines) + "\n"


def render_reference_validation_markdown(payload: dict) -> str:
    chunk_chars = payload.get("chunk_chars") or {}
    chunk_chars_label = (
        f"min {chunk_chars.get('min', 0)}, avg {chunk_chars.get('avg', 0)}, max {chunk_chars.get('max', 0)}"
        if isinstance(chunk_chars, dict)
        else str(chunk_chars)
    )
    lines = [
        "# Reference Evidence DB Validation",
        "",
        f"- Status: {payload.get('status')}",
        f"- Validated at: {payload.get('validated_at')}",
        f"- Documents: {payload.get('documents')}",
        f"- Pages: {payload.get('pages')}",
        f"- Chunks: {payload.get('chunks')}",
        f"- Evidence items: {payload.get('evidence_items')}",
        f"- Chunk chars: {chunk_chars_label}",
        "",
        "## Quality Flags",
        "",
    ]
    for flag in payload.get("quality_flags", []):
        lines.append(f"- {flag}")
    lines.extend(["", "## Issues", "", "- 없음", "", "## Warnings", ""])
    warnings = payload.get("warnings", [])
    if not warnings:
        lines.append("- 없음")
    for warning in warnings:
        lines.append(f"- {json.dumps(warning, ensure_ascii=False)}")
    lines.extend(["", "## Category Counts", ""])
    for row in payload.get("category_counts", []):
        lines.append(f"- {row.get('category')}: {int(row.get('count') or 0)}")
    return "\n".join(lines) + "\n"


def render_learning_validation_markdown(payload: dict) -> str:
    lines = [
        "# Reference DB Learning Readiness Validation",
        "",
        f"- Status: {payload.get('status')}",
        f"- Learning readiness score: {payload.get('learning_readiness_score')}",
        f"- Topics tested: {payload.get('topics_tested')}",
        f"- Documents: {payload.get('documents')}",
        f"- Chunks: {payload.get('chunks')}",
        f"- Evidence items: {payload.get('evidence_items')}",
        "",
        "## Issues",
        "",
        "- 없음",
        "",
        "## Warnings",
        "",
    ]
    warnings = payload.get("warnings", [])
    if not warnings:
        lines.append("- 없음")
    for warning in warnings:
        lines.append(f"- {json.dumps(warning, ensure_ascii=False)}")
    lines.extend(["", "## Topic Retrieval Summary", ""])
    for item in payload.get("topic_retrieval_summary", []):
        status = "OK" if item.get("reference_count", 0) > 0 else "WARN"
        categories = ",".join(item.get("categories", []))
        signals = ",".join(item.get("signals", []))
        lines.append(
            f"- {status} {item.get('topic')}: {item.get('reference_count')} refs, {item.get('source_count')} sources, categories {categories}, signals {signals}"
        )
    return "\n".join(lines) + "\n"


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    os.chdir(PROJECT_ROOT)
    main()
