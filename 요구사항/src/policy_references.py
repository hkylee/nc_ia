"""Reference material reader for NC policy document generation."""

from __future__ import annotations

import re
import hashlib
import html as html_lib
import json
import math
import os
import sqlite3
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
from xml.etree import ElementTree as ET

try:
    from runtime_paths import INPUT_ROOT, LOGS_ROOT, PROJECT_ROOT, REFERENCE_DB_PATH
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import INPUT_ROOT, LOGS_ROOT, PROJECT_ROOT, REFERENCE_DB_PATH

DEFAULT_REFERENCES_DIR = INPUT_ROOT / "references"
DEFAULT_REQUIREMENTS_DIR = INPUT_ROOT / "requirements"
DEFAULT_TEMPLATES_DIR = INPUT_ROOT / "templates"
DEFAULT_SAMPLES_DIR = INPUT_ROOT / "samples"
DEFAULT_REFERENCE_DB_PATH = REFERENCE_DB_PATH
REFERENCE_DB_SCHEMA_VERSION = 10
REFERENCE_CHUNK_TARGET_CHARS = 1100
REFERENCE_MAX_CHUNKS_PER_DOCUMENT = 220
REFERENCE_QUERY_CHUNKS_PER_DOCUMENT = 14
REFERENCE_VECTOR_DEFAULT_MODEL = "text-embedding-3-small"
REFERENCE_VECTOR_LOG_PATH = LOGS_ROOT / "reference_vector.jsonl"
REFERENCE_VECTOR_MIN_SIMILARITY = 0.68
REFERENCE_VECTOR_ANCHOR_MIN_SCORE = 4
REFERENCE_VECTOR_UNANCHORED_MAX_BOOST = 6
COMPOUND_TOPIC_SUFFIXES = (
    "주문",
    "조회",
    "설정",
    "관리",
    "변경",
    "처리",
    "상세",
    "목록",
    "정보",
    "혜택",
    "결제",
    "납부",
    "환불",
    "취소",
    "교환",
    "반품",
    "인증",
    "검색",
    "가입",
    "탈퇴",
)
GENERIC_REFERENCE_KEYWORDS = {
    "통합",
    "셀프",
    "목적",
    "고객",
    "불편",
    "복잡",
    "인증",
    "bss",
    "채널",
    "정책",
    "상태",
    "처리",
    "연계",
    "이력",
    "고지",
}
NON_REFERENCE_SOURCE_CATEGORIES = {"requirement", "template", "sample"}
ANALYSIS_SYNTHESIS_CATEGORY = "analysis_synthesis"
ANALYSIS_SYNTHESIS_HTML_NAMES = {
    "benchmarking.html",
    "customer-research.html",
    "employee-interview.html",
    "function-inventory-biz.html",
    "function-inventory-direct.html",
    "function-inventory-integrated.html",
    "function-inventory-membership.html",
    "function-inventory-tworld.html",
    "function-inventory-universe.html",
    "ia-analysis.html",
    "screen-flow.html",
    "service-policy.html",
    "voc-summary.html",
}
PDF_CHROME_LINE_PATTERNS = (
    re.compile(r"TDE Insights\s*서비스\s*제공\s*알림"),
    re.compile(r"페이지/\s*…/\s*\d+"),
    re.compile(r"^작성자\s*:.*마지막\s*업데이트"),
    re.compile(r"^문서번호\s*/\s*명\s*$"),
    re.compile(r"^변경\s*이력\s*$"),
    re.compile(r"^버전\s+변경일자\s+변경\s*내용"),
    re.compile(r"^Draft\s+\d{4}\."),
    re.compile(r"^\d{2,4}\.\s*\d{1,2}\.\s*\d{1,2}\..*Conﬂuence"),
    re.compile(r"^https?://con[ﬂfl]uence", re.IGNORECASE),
    re.compile(r"^[\uf000-\uf8ff\s]+$"),
)
PDF_LOW_SIGNAL_MARKERS = (
    "레이블 없음",
    "끌어다 놓기",
    "파일 찾아보기",
    "https://conﬂuence",
    "https://confluence",
)
PDF_NOISE_MARKERS = (
    "TDE Insights",
    "SUPER CH",
    "Confluence",
    "Conﬂuence",
    "To Be 과제정의",
    "마지막 업데이트",
    "문서번호 / 명",
    "변경 이력",
)
REQUIREMENT_LEVEL_REFERENCE_MARKERS = (
    "채널방향성pdf",
    "tkch",
)
REQUIREMENT_LEVEL_REFERENCE_SCORE_BOOST = 90
TK_CORE_ORIENTATION_SCORE_BOOST = 45


@dataclass(frozen=True)
class ReferenceInsight:
    source_name: str
    source_type: str
    category: str
    summary: str
    signals: Tuple[str, ...]
    evidence: Tuple[str, ...]
    score: int
    text_chars: int
    read_scope: str
    source_text: str = ""


def load_reference_insights_for_topic(
    topic: str,
    references_dir: Path | str = DEFAULT_REFERENCES_DIR,
    limit: int | None = None,
    *,
    database_path: Path | str | None = None,
) -> List[ReferenceInsight]:
    root = Path(references_dir)
    if not root.exists():
        return []

    keywords = topic_keywords(topic)
    if reference_database_enabled():
        try:
            insights = load_reference_insights_from_database(
                topic=topic,
                references_dir=root,
                keywords=keywords,
                limit=limit,
                database_path=Path(database_path) if database_path else DEFAULT_REFERENCE_DB_PATH,
            )
            if insights:
                return insights
        except Exception:
            # Keep generation resilient: if DB indexing fails, fall back to direct reads.
            pass

    insights: List[ReferenceInsight] = []
    for path in iter_reference_files(root):
        text = extract_reference_text(path, keywords)
        score = score_reference(path.name, text, keywords)

        category = categorize_reference(path.name, text)
        signals = tuple(extract_focus_signals(path.name, text, keywords, category))
        evidence = tuple(extract_evidence_snippets(path.name, text, keywords, category))
        summary = summarize_reference(category, signals)
        insights.append(
            ReferenceInsight(
                source_name=normalize(path.name),
                source_type=path.suffix.lower().lstrip("."),
                category=category,
                summary=summary,
                signals=signals,
                evidence=evidence,
                score=score,
                text_chars=len(text),
                read_scope="full_document",
                source_text=retain_source_text(text),
            )
        )

    insights.sort(key=lambda item: (item.score, category_priority(item.category), item.source_name), reverse=True)
    return insights[:limit] if limit is not None else insights


def reference_database_enabled() -> bool:
    return str(os.environ.get("NC_REFERENCE_DB_ENABLED", "1")) not in {"0", "false", "False", "no", "NO"}


def load_reference_insights_from_database(
    *,
    topic: str,
    references_dir: Path,
    keywords: Sequence[str],
    limit: int | None,
    database_path: Path,
) -> List[ReferenceInsight]:
    if should_index_project_source_database(references_dir, database_path):
        ensure_project_source_database(PROJECT_ROOT, database_path)
    else:
        ensure_reference_database(references_dir, database_path)
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        documents = conn.execute(
            """
            SELECT document_id, source_name, source_type, category, text_chars, page_count, content_hash
            FROM documents
            WHERE category NOT IN ('requirement', 'template', 'sample')
            ORDER BY source_name
            """
        ).fetchall()
        chunks_by_document: dict[str, List[sqlite3.Row]] = {}
        document_ids = [str(document["document_id"]) for document in documents]
        for document_id_batch in batched(document_ids, 200):
            if not document_id_batch:
                continue
            placeholders = ",".join("?" for _ in document_id_batch)
            for chunk in conn.execute(
                f"""
                SELECT chunk_id, document_id, page_start, page_end, section_title, text, tags, base_score
                FROM chunks
                WHERE document_id IN ({placeholders})
                ORDER BY document_id, page_start, chunk_index
                """,
                tuple(document_id_batch),
            ):
                chunks_by_document.setdefault(str(chunk["document_id"]), []).append(chunk)
        vector_scores, vector_mode = reference_vector_scores(conn, topic, keywords, chunks_by_document)

    insights: List[ReferenceInsight] = []
    for document in documents:
        document_id = str(document["document_id"])
        chunks = chunks_by_document.get(document_id, [])
        if not chunks:
            continue
        ranked_chunks = rank_database_chunks(
            chunks=chunks,
            source_name=str(document["source_name"]),
            keywords=keywords,
            category=str(document["category"]),
            vector_scores=vector_scores,
        )
        selected_chunks = [chunk for _, chunk in ranked_chunks[:REFERENCE_QUERY_CHUNKS_PER_DOCUMENT]]
        selected_text = "\n".join(chunk_text_with_page(chunk) for chunk in selected_chunks)
        category = str(document["category"] or categorize_reference(str(document["source_name"]), selected_text))
        signals = tuple(extract_focus_signals(str(document["source_name"]), selected_text, keywords, category))
        evidence = tuple(database_evidence_snippets(str(document["source_name"]), selected_chunks, keywords, category))
        top_chunk_score = ranked_chunks[0][0] if ranked_chunks else 0
        document_score = score_reference(str(document["source_name"]), selected_text, keywords) + top_chunk_score + category_priority(category)
        insights.append(
            ReferenceInsight(
                source_name=normalize(str(document["source_name"])),
                source_type=str(document["source_type"] or ""),
                category=category,
                summary=summarize_reference(category, signals),
                signals=signals,
                evidence=evidence,
                score=document_score,
                text_chars=int(document["text_chars"] or 0),
                read_scope=f"{vector_mode}_chunked_full_document:{len(selected_chunks)}/{len(chunks)}",
                source_text=retain_source_text(selected_text),
            )
        )

    insights.sort(key=lambda item: (item.score, category_priority(item.category), item.source_name), reverse=True)
    return insights[:limit] if limit is not None else insights


def ensure_reference_database(references_dir: Path, database_path: Path = DEFAULT_REFERENCE_DB_PATH) -> Path:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        initialize_reference_database(conn)
        if reference_index_version(conn) != str(REFERENCE_DB_SCHEMA_VERSION):
            reset_reference_index(conn)
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("index_version", str(REFERENCE_DB_SCHEMA_VERSION)),
            )
        existing = {
            str(row["source_path"]): row
            for row in conn.execute(
                "SELECT document_id, source_path, category, mtime_ns, file_size, content_hash FROM documents"
            )
        }
        current_paths = {str(path.resolve()) for path in iter_reference_files(references_dir)}
        managed_roots = [references_dir]
        for stale_path, row in list(existing.items()):
            if stale_path not in current_paths and path_is_under_any(stale_path, managed_roots):
                delete_indexed_document(conn, str(row["document_id"]))
        for path in iter_reference_files(references_dir):
            index_reference_file_if_needed(conn, path, existing.get(str(path.resolve())))
    return database_path


def ensure_project_source_database(
    project_root: Path = PROJECT_ROOT,
    database_path: Path = DEFAULT_REFERENCE_DB_PATH,
) -> Path:
    """Index every source family needed for authoring quality checks.

    Reference retrieval still filters to reference material only. Keeping
    requirements, templates, and samples in the same DB gives us a single
    auditable source inventory without duplicating those files into prompts.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        initialize_reference_database(conn)
        if reference_index_version(conn) != str(REFERENCE_DB_SCHEMA_VERSION):
            reset_reference_index(conn)
            conn.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
                ("index_version", str(REFERENCE_DB_SCHEMA_VERSION)),
            )
        existing = {
            str(row["source_path"]): row
            for row in conn.execute(
                "SELECT document_id, source_path, category, mtime_ns, file_size, content_hash FROM documents"
            )
        }
        source_specs = list(iter_project_source_file_specs(project_root))
        current_paths = {str(path.resolve()) for path, _ in source_specs}
        managed_roots = project_source_roots(project_root)
        for stale_path, row in list(existing.items()):
            if stale_path not in current_paths and path_is_under_any(stale_path, managed_roots):
                delete_indexed_document(conn, str(row["document_id"]))
        for path, category in source_specs:
            index_reference_file_if_needed(
                conn,
                path,
                existing.get(str(path.resolve())),
                category_override=category,
            )
    return database_path


def should_index_project_source_database(references_dir: Path, database_path: Path) -> bool:
    return same_path(references_dir, DEFAULT_REFERENCES_DIR) and same_path(database_path, DEFAULT_REFERENCE_DB_PATH)


def iter_project_source_file_specs(project_root: Path = PROJECT_ROOT) -> Iterable[tuple[Path, str | None]]:
    for root, category in project_source_groups(project_root):
        if category == "requirement":
            current_requirement = find_current_requirements_workbook(root)
            if current_requirement:
                yield current_requirement, category
            else:
                for path in iter_reference_files(root):
                    yield path, category
            continue
        if category == ANALYSIS_SYNTHESIS_CATEGORY:
            for path in iter_analysis_synthesis_files(root):
                yield path, category
            continue
        for path in iter_reference_files(root):
            yield path, category


def project_source_groups(project_root: Path = PROJECT_ROOT) -> tuple[tuple[Path, str | None], ...]:
    input_root = project_root / "input"
    return (
        (input_root / "references", None),
        (input_root / "PI guide", "guideline"),
        (input_root / "requirements", "requirement"),
        (input_root / "templates", "template"),
        (input_root / "samples", "sample"),
        (project_root / "output" / "reference_html", ANALYSIS_SYNTHESIS_CATEGORY),
    )


def project_source_roots(project_root: Path = PROJECT_ROOT) -> List[Path]:
    return [root for root, _ in project_source_groups(project_root)]


def iter_analysis_synthesis_files(root: Path) -> Iterable[Path]:
    """Yield completed status-analysis HTML pages that should become evidence.

    ``output/reference_html`` also contains TK task explainers, visual style
    variants, and placeholders. Those are UI deliverables, not reusable policy
    authoring knowledge, so this selector keeps only the completed 현황 분석
    pages that summarize benchmark, research, interview, IA, and VoC findings.
    """
    for path in iter_reference_files(root):
        if not is_analysis_synthesis_file(path):
            continue
        if is_analysis_synthesis_placeholder(path):
            continue
        yield path


def is_analysis_synthesis_file(path: Path) -> bool:
    name = path.name
    if path.suffix.lower() != ".html":
        return False
    return name in ANALYSIS_SYNTHESIS_HTML_NAMES or name.startswith("voc-")


def is_analysis_synthesis_placeholder(path: Path) -> bool:
    text = extract_html_text(path)
    if "작성 예정입니다" not in text:
        return False
    return len(text) < 1200 or contains_any(text, ("화면 흐름", "기능 내역", "서비스 정책"))


def find_current_requirements_workbook(requirements_dir: Path) -> Path | None:
    """Return only the authoritative requirements workbook for source audit.

    Historical requirement workbooks stay in ``input/requirements`` for
    traceability, but they must not remain selectable evidence after the final
    requirements file is converted into the dedicated requirements DB.
    """
    try:
        from policy_requirements import find_requirements_workbook
    except ImportError:  # pragma: no cover - package import fallback.
        from .policy_requirements import find_requirements_workbook

    return find_requirements_workbook(requirements_dir)


def same_path(left: Path, right: Path) -> bool:
    return safe_resolve(left) == safe_resolve(right)


def path_is_under_any(path: str | Path, roots: Sequence[Path]) -> bool:
    resolved_path = safe_resolve(Path(path))
    for root in roots:
        resolved_root = safe_resolve(root)
        if resolved_path == resolved_root or resolved_root in resolved_path.parents:
            return True
    return False


def safe_resolve(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def initialize_reference_database(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL UNIQUE,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            category TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            text_chars INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            indexed_at TEXT NOT NULL,
            read_scope TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            page_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            text_chars INTEGER NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            section_title TEXT NOT NULL,
            text TEXT NOT NULL,
            text_chars INTEGER NOT NULL,
            keywords TEXT NOT NULL,
            tags TEXT NOT NULL,
            base_score INTEGER NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_items (
            evidence_id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            signals TEXT NOT NULL,
            related_topics TEXT NOT NULL,
            related_chapters TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            evidence_text TEXT NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id),
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_hash TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            embedding_json TEXT NOT NULL,
            embedded_at TEXT NOT NULL,
            FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id),
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON chunks(tags)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_document ON evidence_items(document_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(embedding_model)")
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
        ("schema_version", str(REFERENCE_DB_SCHEMA_VERSION)),
    )
    conn.execute(
        "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
        ("index_version", "0"),
    )


def reference_index_version(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM metadata WHERE key = ?", ("index_version",)).fetchone()
    return str(row["value"] if isinstance(row, sqlite3.Row) else row[0]) if row else "0"


def reset_reference_index(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM chunk_embeddings")
    conn.execute("DELETE FROM evidence_items")
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM pages")
    conn.execute("DELETE FROM documents")


def index_reference_file_if_needed(
    conn: sqlite3.Connection,
    path: Path,
    existing_row,
    *,
    category_override: str | None = None,
) -> None:
    stat = path.stat()
    source_path = str(path.resolve())
    existing_category_matches = (
        not category_override
        or (
            existing_row is not None
            and str(existing_row["category"] or "") == str(category_override)
        )
    )
    if (
        existing_row
        and existing_category_matches
        and int(existing_row["mtime_ns"]) == int(stat.st_mtime_ns)
        and int(existing_row["file_size"]) == int(stat.st_size)
    ):
        return

    content_hash = file_sha256(path)
    if existing_row and existing_category_matches and str(existing_row["content_hash"]) == content_hash:
        conn.execute(
            "UPDATE documents SET mtime_ns = ?, file_size = ?, indexed_at = ? WHERE document_id = ?",
            (int(stat.st_mtime_ns), int(stat.st_size), now_iso(), str(existing_row["document_id"])),
        )
        return

    document_id = stable_document_id(path)
    delete_indexed_document(conn, document_id)
    page_texts = extract_reference_pages(path)
    full_text = clean_text("\n".join(text for _, text in page_texts))
    if not page_texts:
        page_texts = [(1, "")]
    category = category_override or categorize_reference(path.name, full_text)
    source_type = path.suffix.lower().lstrip(".")
    conn.execute(
        """
        INSERT OR REPLACE INTO documents(
            document_id, source_path, source_name, source_type, category, file_size, mtime_ns,
            content_hash, text_chars, page_count, indexed_at, read_scope
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            source_path,
            normalize(path.name),
            source_type,
            category,
            int(stat.st_size),
            int(stat.st_mtime_ns),
            content_hash,
            len(full_text),
            len(page_texts),
            now_iso(),
            "database_page_chunk_full_document",
        ),
    )
    for page_number, page_text in page_texts:
        page_id = f"{document_id}-P{page_number:04d}"
        conn.execute(
            "INSERT OR REPLACE INTO pages(page_id, document_id, page_number, text, text_chars) VALUES (?, ?, ?, ?, ?)",
            (page_id, document_id, page_number, page_text, len(page_text)),
        )
    chunks = chunk_reference_pages(page_texts)
    for chunk_index, chunk in enumerate(chunks[:REFERENCE_MAX_CHUNKS_PER_DOCUMENT], 1):
        chunk_id = f"{document_id}-C{chunk_index:04d}"
        tags = infer_reference_tags(path.name, chunk["text"], category, source_type)
        tags.extend(reference_chunk_quality_tags(chunk["text"]))
        tags = unique_nonempty(tags)
        keywords = extract_chunk_keywords(chunk["text"], path.name)
        base_score = (
            keyword_text_score(f"{path.name}\n{chunk['text']}", keywords)
            + category_priority(category)
            + requirement_level_reference_score_boost(path.name)
            - reference_chunk_quality_penalty(chunk["text"])
        )
        base_score = max(1, base_score)
        conn.execute(
            """
            INSERT OR REPLACE INTO chunks(
                chunk_id, document_id, chunk_index, page_start, page_end, section_title, text,
                text_chars, keywords, tags, base_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk_id,
                document_id,
                chunk_index,
                int(chunk["page_start"]),
                int(chunk["page_end"]),
                chunk["section_title"],
                chunk["text"],
                len(chunk["text"]),
                json.dumps(keywords, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                int(base_score),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_items(
                evidence_id, chunk_id, document_id, evidence_type, summary, signals,
                related_topics, related_chapters, confidence, evidence_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"EVD-{document_id.removeprefix('DOC-')}-{chunk_index:04d}",
                chunk_id,
                document_id,
                category,
                limit_text(chunk["text"], 360),
                json.dumps(extract_focus_signals(path.name, chunk["text"], keywords, category), ensure_ascii=False),
                json.dumps(keywords[:12], ensure_ascii=False),
                json.dumps(infer_related_chapters(chunk["text"], category), ensure_ascii=False),
                int(min(100, max(1, base_score))),
                limit_text(chunk["text"], 900),
            ),
        )


def delete_indexed_document(conn: sqlite3.Connection, document_id: str) -> None:
    conn.execute("DELETE FROM chunk_embeddings WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM evidence_items WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM pages WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))


def extract_reference_pages(path: Path) -> List[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_pages(path)
    text = extract_reference_text(path, ())
    return [(1, text)] if text else []


def extract_pdf_pages(path: Path) -> List[tuple[int, str]]:
    reader_class = import_pdf_reader()
    if not reader_class:
        return []
    try:
        reader = reader_class(str(path))
    except Exception:
        return []
    pages: List[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = clean_pdf_page_text(path, index, text)
        if not cleaned:
            cleaned = clean_pdf_page_text(path, index, extract_pdf_page_text_with_ocr(path, index))
        pages.append((index, cleaned))
    return pages


def clean_pdf_page_text(path: Path, page_number: int, text: str) -> str:
    """Remove extraction chrome while keeping real document content.

    Confluence-exported PDFs include repeated page chrome such as breadcrumbs,
    author metadata, footer URLs, and icon glyphs. Those strings are useful for
    provenance but noisy as policy evidence, so we remove only high-confidence
    line-level chrome and keep the body untouched.
    """
    if not text:
        return ""
    kept: List[str] = []
    for raw_line in str(text).splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if is_pdf_chrome_line(line):
            continue
        kept.append(line)
    return clean_text("\n".join(kept))


def is_pdf_chrome_line(line: str) -> bool:
    cleaned = clean_text(line)
    if not cleaned:
        return True
    return any(pattern.search(cleaned) for pattern in PDF_CHROME_LINE_PATTERNS)


def is_pdf_low_signal_page(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return True
    marker_hits = sum(1 for marker in PDF_LOW_SIGNAL_MARKERS if marker in cleaned)
    # Keep short pages when they contain actual policy words; otherwise mark
    # upload/footer residue as low-signal so retrieval can rank it lower.
    if len(cleaned) < 180 and marker_hits >= 1:
        return True
    if len(cleaned) < 320 and marker_hits >= 2 and not contains_any(
        cleaned,
        ("고객", "정책", "프로세스", "기능", "상태", "요구", "과제", "경험", "처리"),
    ):
        return True
    return False


def extract_pdf_page_text_with_ocr(path: Path, page_number: int) -> str:
    """Best-effort OCR fallback for image-only PDF pages.

    The project must run without heavyweight OCR dependencies, so this function
    is intentionally optional. If pypdfium2/PyMuPDF + pytesseract are installed
    in the runtime, empty pages can still be indexed; otherwise we safely keep
    the page as non-text.
    """
    if str(os.environ.get("NC_REFERENCE_OCR_ENABLED", "1")).strip().casefold() in {"0", "false", "no"}:
        return ""
    try:
        text = extract_pdf_page_text_with_pypdfium_ocr(path, page_number)
        if text:
            return text
        return extract_pdf_page_text_with_fitz_ocr(path, page_number)
    except Exception:
        return ""


def extract_pdf_page_text_with_pypdfium_ocr(path: Path, page_number: int) -> str:
    try:
        import pypdfium2 as pdfium  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        return ""
    try:
        pdf = pdfium.PdfDocument(str(path))
        page = pdf[page_number - 1]
        image = page.render(scale=2).to_pil()
        return clean_text(pytesseract.image_to_string(image, lang=ocr_languages()))
    except Exception:
        return ""


def extract_pdf_page_text_with_fitz_ocr(path: Path, page_number: int) -> str:
    try:
        import fitz  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception:
        return ""
    try:
        document = fitz.open(str(path))
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        return clean_text(pytesseract.image_to_string(image, lang=ocr_languages()))
    except Exception:
        return ""


def ocr_languages() -> str:
    return os.environ.get("NC_REFERENCE_OCR_LANG", "kor+eng").strip() or "kor+eng"


def chunk_reference_pages(page_texts: Sequence[tuple[int, str]], target_chars: int = REFERENCE_CHUNK_TARGET_CHARS) -> List[dict]:
    chunks: List[dict] = []
    current: List[str] = []
    current_size = 0
    page_start = 1
    page_end = 1
    for page_number, page_text in page_texts:
        for raw_fragment in split_reference_fragments(page_text, min_chars=30):
            for fragment in split_long_reference_fragment(raw_fragment, target_chars):
                if not fragment:
                    continue
                if current and current_size + len(fragment) > target_chars:
                    text = clean_text(" ".join(current))
                    chunks.append(
                        {
                            "page_start": page_start,
                            "page_end": page_end,
                            "section_title": infer_section_title(text),
                            "text": text,
                        }
                    )
                    current = []
                    current_size = 0
                    page_start = page_number
                if not current:
                    page_start = page_number
                current.append(fragment)
                current_size += len(fragment) + 1
                page_end = page_number
    if current:
        text = clean_text(" ".join(current))
        chunks.append(
            {
                "page_start": page_start,
                "page_end": page_end,
                "section_title": infer_section_title(text),
                "text": text,
            }
        )
    return [chunk for chunk in chunks if len(chunk["text"]) >= 80]


def split_long_reference_fragment(fragment: str, target_chars: int) -> List[str]:
    cleaned = clean_text(fragment)
    if len(cleaned) <= target_chars:
        return [cleaned]
    parts: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + target_chars)
        if end < len(cleaned):
            boundary = max(cleaned.rfind(" ", start, end), cleaned.rfind(",", start, end), cleaned.rfind(";", start, end))
            if boundary > start + int(target_chars * 0.55):
                end = boundary
        parts.append(cleaned[start:end].strip(" ,;"))
        start = end
    return [part for part in parts if len(part) >= 40]


def infer_section_title(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    sentence = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+", cleaned)[0]
    return limit_text(sentence, 80)


def infer_reference_tags(name: str, text: str, category: str, source_type: str) -> List[str]:
    tags = [category, source_type]
    chapter_rules = {
        "overview": ("범위", "채널", "전략", "고객", "목표"),
        "usecases": ("고객", "과업", "사용", "신청", "조회", "변경", "해지"),
        "state": ("상태", "완료", "실패", "제한", "보류", "취소"),
        "process": ("프로세스", "흐름", "단계", "상담", "셀프", "인증"),
        "functions": ("기능", "조회", "검증", "저장", "알림", "연계"),
        "policies": ("정책", "기준", "허용", "제한", "예외", "고지", "이력"),
    }
    source = f"{name}\n{text}"
    for tag, keywords in chapter_rules.items():
        if contains_any(source, keywords):
            tags.append(tag)
    return unique_nonempty(tags)


def reference_chunk_quality_tags(text: str) -> List[str]:
    cleaned = clean_text(text)
    tags: List[str] = []
    if not cleaned:
        return ["quality:empty"]
    if len(cleaned) < 250:
        tags.append("quality:short")
    if is_pdf_low_signal_page(cleaned):
        tags.append("quality:low_signal")
    if pdf_noise_marker_count(cleaned) >= 3:
        tags.append("noise:pdf_chrome")
    if contains_any(cleaned, PDF_LOW_SIGNAL_MARKERS):
        tags.append("noise:footer_or_upload")
    return tags


def reference_chunk_quality_penalty(text: str) -> int:
    cleaned = clean_text(text)
    if not cleaned:
        return 80
    penalty = 0
    if len(cleaned) < 160:
        penalty += 24
    elif len(cleaned) < 250:
        penalty += 12
    if is_pdf_low_signal_page(cleaned):
        penalty += 45
    noise_hits = pdf_noise_marker_count(cleaned)
    if noise_hits >= 5:
        penalty += 18
    elif noise_hits >= 3:
        penalty += 10
    if contains_any(cleaned, PDF_LOW_SIGNAL_MARKERS):
        penalty += 16
    return penalty


def pdf_noise_marker_count(text: str) -> int:
    return sum(str(text or "").count(marker) for marker in PDF_NOISE_MARKERS)


def infer_related_chapters(text: str, category: str) -> List[str]:
    tags = infer_reference_tags("", text, category, "")
    return [tag for tag in tags if tag in {"overview", "usecases", "state", "process", "functions", "policies"}] or ["overview"]


def extract_chunk_keywords(text: str, name: str, limit: int = 20) -> List[str]:
    candidates = re.findall(r"[A-Za-z0-9가-힣]{2,}", f"{name} {text}")
    stopwords = {"고객", "정책", "기준", "내용", "경우", "대한", "관련", "처리", "확인", "분석", "결과"}
    counts: dict[str, int] = {}
    for candidate in candidates:
        cleaned = clean_text(candidate)
        if cleaned in stopwords or len(cleaned) < 2:
            continue
        counts[cleaned] = counts.get(cleaned, 0) + 1
    ranked = sorted(counts.items(), key=lambda pair: (pair[1], len(pair[0]), pair[0]), reverse=True)
    return [keyword for keyword, _ in ranked[:limit]]


def rank_database_chunks(
    *,
    chunks: Sequence[sqlite3.Row],
    source_name: str,
    keywords: Sequence[str],
    category: str,
    vector_scores: Mapping[str, int] | None = None,
) -> List[tuple[int, sqlite3.Row]]:
    ranked: List[tuple[int, sqlite3.Row]] = []
    vector_scores = vector_scores or {}
    for chunk in chunks:
        text = str(chunk["text"] or "")
        score = int(chunk["base_score"] or 0)
        score += keyword_text_score(f"{source_name}\n{text}", keywords)
        score += category_priority(category)
        score += int(vector_scores.get(str(chunk["chunk_id"]), 0) or 0)
        if is_global_reference(source_name):
            score += 8
        if is_tk_reference_source(source_name) and has_core_orientation_marker(text):
            score += TK_CORE_ORIENTATION_SCORE_BOOST
        ranked.append((score, chunk))
    ranked.sort(key=lambda pair: (-pair[0], int(pair[1]["page_start"]), str(pair[1]["chunk_id"])))
    return ranked


def is_tk_reference_source(source_name: object) -> bool:
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", str(source_name or "").casefold())
    return normalized.startswith("tkch") or "tkch" in normalized


def has_core_orientation_marker(text: object) -> bool:
    value = str(text or "")
    return bool(re.search(r"(?:상위\s*)?핵심\s*지향(?:점)?|지향점\s*및\s*기대\s*효과", value))


def reference_vector_scores(
    conn: sqlite3.Connection,
    topic: str,
    keywords: Sequence[str],
    chunks_by_document: Mapping[str, Sequence[sqlite3.Row]],
) -> tuple[dict[str, int], str]:
    if not reference_vector_enabled():
        return {}, "database"
    candidates: List[sqlite3.Row] = []
    for chunks in chunks_by_document.values():
        preliminary = rank_database_chunks(
            chunks=chunks,
            source_name="",
            keywords=keywords,
            category="reference",
            vector_scores={},
        )
        candidates.extend(chunk for _, chunk in preliminary[:reference_vector_candidates_per_document()])
    candidates = dedupe_chunks(candidates)
    if not candidates:
        return {}, "database"
    try:
        model = reference_embedding_model()
        query_vector = request_openai_embeddings([reference_query_text(topic, keywords)], model)[0]
        ensure_chunk_embeddings(conn, candidates, model)
        chunk_vectors = load_chunk_embeddings(conn, [str(chunk["chunk_id"]) for chunk in candidates], model)
        candidate_by_id = {str(chunk["chunk_id"]): chunk for chunk in candidates}
        scores: dict[str, int] = {}
        guard_stats = {"full": 0, "partial": 0, "capped": 0, "filtered": 0}
        for chunk_id, vector in chunk_vectors.items():
            chunk = candidate_by_id.get(chunk_id)
            if chunk is None or not vector:
                continue
            similarity = cosine_similarity(query_vector, vector)
            anchor_score = reference_vector_anchor_score(chunk, topic, keywords)
            boost, guard = guarded_vector_boost(similarity, anchor_score)
            guard_stats[guard] = guard_stats.get(guard, 0) + 1
            if boost > 0:
                scores[chunk_id] = boost
        write_reference_vector_log(
            {
                "event": "vector_scores",
                "topic": topic,
                "model": model,
                "candidate_chunks": len(candidates),
                "scored_chunks": len(scores),
                "guard_stats": guard_stats,
                "min_similarity": reference_vector_min_similarity(),
                "anchor_min_score": reference_vector_anchor_min_score(),
            }
        )
        return scores, "database_hybrid_vector_guarded"
    except Exception as exc:
        write_reference_vector_log(
            {
                "event": "vector_fallback",
                "topic": topic,
                "error": str(exc)[:300],
            }
        )
        return {}, "database"


def reference_vector_enabled() -> bool:
    value = os.getenv("NC_REFERENCE_VECTOR_ENABLED", "0").strip().casefold()
    if value not in {"1", "true", "yes", "y"}:
        return False
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def reference_embedding_model() -> str:
    return os.getenv("OPENAI_EMBEDDING_MODEL", REFERENCE_VECTOR_DEFAULT_MODEL).strip() or REFERENCE_VECTOR_DEFAULT_MODEL


def reference_vector_candidates_per_document() -> int:
    return parse_positive_int_env("NC_REFERENCE_VECTOR_CANDIDATES_PER_DOCUMENT", 32)


def reference_vector_weight() -> int:
    return parse_positive_int_env("NC_REFERENCE_VECTOR_WEIGHT", 70)


def reference_vector_min_similarity() -> float:
    return parse_float_env("NC_REFERENCE_VECTOR_MIN_SIMILARITY", REFERENCE_VECTOR_MIN_SIMILARITY)


def reference_vector_anchor_min_score() -> int:
    return parse_positive_int_env("NC_REFERENCE_VECTOR_ANCHOR_MIN_SCORE", REFERENCE_VECTOR_ANCHOR_MIN_SCORE)


def reference_vector_unanchored_max_boost() -> int:
    return parse_positive_int_env("NC_REFERENCE_VECTOR_UNANCHORED_MAX_BOOST", REFERENCE_VECTOR_UNANCHORED_MAX_BOOST)


def reference_embedding_batch_size() -> int:
    return parse_positive_int_env("NC_REFERENCE_EMBEDDING_BATCH_SIZE", 48)


def reference_embedding_max_chars() -> int:
    return parse_positive_int_env("NC_REFERENCE_EMBEDDING_MAX_CHARS", 1800)


def reference_vector_anchor_score(chunk: sqlite3.Row, topic: str, keywords: Sequence[str]) -> int:
    """Measure lexical/topic anchoring before allowing vector similarity to help."""
    text = " ".join(
        str(value or "")
        for value in (
            topic,
            chunk["section_title"],
            chunk["tags"],
            chunk["text"],
        )
    )
    return keyword_text_score(text, [topic, *keywords])


def guarded_vector_boost(similarity: float, anchor_score: int) -> tuple[int, str]:
    if similarity < reference_vector_min_similarity():
        return 0, "filtered"
    raw_boost = int(max(0.0, similarity) * reference_vector_weight())
    if anchor_score >= reference_vector_anchor_min_score():
        return raw_boost, "full"
    if anchor_score > 0:
        return min(raw_boost, max(reference_vector_unanchored_max_boost(), reference_vector_weight() // 3)), "partial"
    return min(raw_boost, reference_vector_unanchored_max_boost()), "capped"


def ensure_chunk_embeddings(conn: sqlite3.Connection, chunks: Sequence[sqlite3.Row], model: str) -> None:
    missing: List[tuple[sqlite3.Row, str, str]] = []
    hashes = {str(chunk["chunk_id"]): chunk_embedding_hash(chunk) for chunk in chunks}
    for chunk_id_batch in batched(list(hashes), 200):
        placeholders = ",".join("?" for _ in chunk_id_batch)
        rows = conn.execute(
            f"""
            SELECT chunk_id, embedding_hash
            FROM chunk_embeddings
            WHERE embedding_model = ? AND chunk_id IN ({placeholders})
            """,
            (model, *chunk_id_batch),
        ).fetchall()
        current = {str(row["chunk_id"]): str(row["embedding_hash"]) for row in rows}
        for chunk in chunks:
            chunk_id = str(chunk["chunk_id"])
            if chunk_id in chunk_id_batch and current.get(chunk_id) != hashes[chunk_id]:
                missing.append((chunk, hashes[chunk_id], chunk_embedding_text(chunk)))
    if not missing:
        return
    for batch in batched(missing, reference_embedding_batch_size()):
        embeddings = request_openai_embeddings([text for _, _, text in batch], model)
        for (chunk, embedding_hash, _), embedding in zip(batch, embeddings):
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_embeddings(
                    chunk_id, document_id, embedding_model, embedding_hash, dimensions, embedding_json, embedded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(chunk["chunk_id"]),
                    str(chunk["document_id"]),
                    model,
                    embedding_hash,
                    len(embedding),
                    json.dumps(embedding, separators=(",", ":")),
                    now_iso(),
                ),
            )


def load_chunk_embeddings(conn: sqlite3.Connection, chunk_ids: Sequence[str], model: str) -> dict[str, List[float]]:
    vectors: dict[str, List[float]] = {}
    for chunk_id_batch in batched(list(chunk_ids), 200):
        if not chunk_id_batch:
            continue
        placeholders = ",".join("?" for _ in chunk_id_batch)
        rows = conn.execute(
            f"""
            SELECT chunk_id, embedding_json
            FROM chunk_embeddings
            WHERE embedding_model = ? AND chunk_id IN ({placeholders})
            """,
            (model, *chunk_id_batch),
        ).fetchall()
        for row in rows:
            try:
                vector = json.loads(str(row["embedding_json"]))
            except json.JSONDecodeError:
                continue
            if isinstance(vector, list):
                vectors[str(row["chunk_id"])] = [float(value) for value in vector]
    return vectors


def request_openai_embeddings(texts: Sequence[str], model: str) -> List[List[float]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없어 reference embedding을 생성할 수 없습니다.")
    endpoint = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/") + "/embeddings"
    payload = json.dumps({"model": model, "input": list(texts)}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    max_retries = parse_positive_int_env("NC_REFERENCE_EMBEDDING_MAX_RETRIES", 3)
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            embeddings = [
                [float(value) for value in item.get("embedding", [])]
                for item in sorted(data.get("data", []), key=lambda item: int(item.get("index", 0)))
            ]
            if len(embeddings) != len(texts):
                raise RuntimeError("embedding 응답 개수가 요청 개수와 다릅니다.")
            return embeddings
        except urllib.error.HTTPError as exc:
            if exc.code not in {408, 409, 429, 500, 502, 503, 504} or attempt >= max_retries:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"embedding API 오류 {exc.code}: {body[:300]}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, ConnectionAbortedError) as exc:
            if attempt >= max_retries:
                raise RuntimeError(f"embedding API 연결 실패: {exc}") from exc
        time.sleep(min(30.0, 2.0 * (2 ** (attempt - 1))))
    raise RuntimeError("embedding API 호출에 실패했습니다.")


def reference_query_text(topic: str, keywords: Sequence[str]) -> str:
    return clean_text(" ".join([topic, *keywords, "고객 과업 프로세스 기능 정책 상태 예외 BSS 연계 이력 고지"]))


def chunk_embedding_text(chunk: sqlite3.Row) -> str:
    return limit_text(
        clean_text(
            " ".join(
                str(value or "")
                for value in (
                    chunk["section_title"],
                    chunk["tags"],
                    chunk["text"],
                )
            )
        ),
        reference_embedding_max_chars(),
    )


def chunk_embedding_hash(chunk: sqlite3.Row) -> str:
    text = chunk_embedding_text(chunk)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def dedupe_chunks(chunks: Sequence[sqlite3.Row]) -> List[sqlite3.Row]:
    result: List[sqlite3.Row] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        result.append(chunk)
    return result


def batched(values: Sequence, batch_size: int) -> Iterable[Sequence]:
    batch_size = max(1, batch_size)
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def parse_positive_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    try:
        return max(1, int(value)) if value else default
    except ValueError:
        return default


def parse_float_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    try:
        return float(value) if value else default
    except ValueError:
        return default


def write_reference_vector_log(payload: Mapping[str, object]) -> None:
    try:
        REFERENCE_VECTOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REFERENCE_VECTOR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": now_iso(), **dict(payload)}, ensure_ascii=False) + "\n")
    except OSError:
        return


def keyword_text_score(text: str, keywords: Sequence[str]) -> int:
    haystack = text.casefold()
    score = 0
    for keyword in keywords:
        key = str(keyword or "").casefold()
        if not key:
            continue
        occurrences = haystack.count(key)
        if occurrences:
            if key in GENERIC_REFERENCE_KEYWORDS:
                score += min(2, occurrences)
            else:
                score += min(24, occurrences * (8 if len(key) >= 3 else 4))
    return score


def chunk_text_with_page(chunk: sqlite3.Row) -> str:
    page_start = int(chunk["page_start"] or 0)
    page_end = int(chunk["page_end"] or page_start)
    page_label = f"p.{page_start}" if page_start == page_end else f"p.{page_start}-{page_end}"
    return f"[{page_label}] {chunk['text']}"


def database_evidence_snippets(
    source_name: str,
    chunks: Sequence[sqlite3.Row],
    keywords: Sequence[str],
    category: str,
    limit: int = 8,
) -> List[str]:
    snippets: List[str] = []
    for chunk in chunks:
        for fragment in split_reference_fragments(str(chunk["text"] or ""), min_chars=40):
            if contains_any(fragment, keywords[:12]) or contains_any(fragment, ("불편", "제한", "예외", "인증", "BSS", "고지", "이력", "정책")):
                snippets.append(limit_text(f"{source_name} {chunk_text_page_suffix(chunk)}: {fragment}", 280))
                break
        if len(snippets) >= limit:
            break
    if not snippets and chunks:
        snippets.append(limit_text(f"{source_name} {chunk_text_page_suffix(chunks[0])}: {chunks[0]['text']}", 280))
    return unique_nonempty(snippets)[:limit]


def chunk_text_page_suffix(chunk: sqlite3.Row) -> str:
    page_start = int(chunk["page_start"] or 0)
    page_end = int(chunk["page_end"] or page_start)
    return f"p.{page_start}" if page_start == page_end else f"p.{page_start}-{page_end}"


def stable_document_id(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"DOC-{digest}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def iter_reference_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.glob("*")):
        if path.name.startswith(".") or path.name.startswith("~$") or not path.is_file():
            continue
        if path.suffix.lower() in {".pdf", ".xlsx", ".xlsm", ".docx", ".txt", ".md", ".html"}:
            yield path


def extract_reference_text(path: Path, keywords: Sequence[str]) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix in {".xlsx", ".xlsm"}:
        return extract_xlsx_text(path, keywords)
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".html":
        return extract_html_text(path)
    try:
        return clean_text(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return ""


def extract_html_text(path: Path) -> str:
    try:
        return html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return ""


def extract_docx_text(path: Path) -> str:
    """Extract paragraph/table text from a DOCX file without external runtime dependencies."""
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        return ""

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines: List[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = "".join(texts).strip()
        if line:
            lines.append(line)
    return clean_text("\n".join(lines))


def html_to_text(raw_html: str) -> str:
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw_html)
    raw = re.sub(r"(?is)<!--(.*?)-->", r" \1 ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|tr|table|section|article|h[1-6]|text|svg)>", "\n", raw)
    raw = re.sub(r"(?i)<(td|th)[^>]*>", " | ", raw)
    text = re.sub(r"(?is)<[^>]+>", " ", raw)
    return clean_text(html_lib.unescape(text))


def extract_pdf_text(path: Path, max_pages: int | None = None, max_chars: int | None = None) -> str:
    reader_class = import_pdf_reader()
    if not reader_class:
        return ""

    try:
        reader = reader_class(str(path))
    except Exception:
        return ""

    chunks: List[str] = []
    pages = list(reader.pages)
    if max_pages is not None:
        pages = pages[:max_pages]
    for index, page in enumerate(pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = clean_pdf_page_text(path, index, text) if path.suffix.lower() == ".pdf" else clean_text(text)
        if cleaned:
            chunks.append(cleaned)
        if max_chars is not None and sum(len(chunk) for chunk in chunks) >= max_chars:
            break
    extracted = clean_text("\n".join(chunks))
    return extracted[:max_chars] if max_chars is not None else extracted


def import_pdf_reader():
    try:
        from pypdf import PdfReader

        return PdfReader
    except Exception:
        for bundled_path in bundled_python_package_paths():
            if bundled_path.exists() and str(bundled_path) not in sys.path:
                sys.path.append(str(bundled_path))
        try:
            from pypdf import PdfReader

            return PdfReader
        except Exception:
            return None


def bundled_python_package_paths() -> List[Path]:
    root = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python"
    paths = [root]
    paths.extend(sorted(root.glob("lib/python*/site-packages")) if root.exists() else [])
    return paths


def extract_xlsx_text(path: Path, keywords: Sequence[str], max_chars: int | None = None) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = read_shared_strings(archive)
            sheet_paths = resolve_sheet_paths(archive)
            chunks: List[str] = []
            for sheet_name, sheet_path in sheet_paths.items():
                sheet_text = read_xlsx_sheet_text(archive, sheet_path, shared_strings, keywords)
                if sheet_text:
                    chunks.append(f"{sheet_name}\n{sheet_text}")
                if max_chars is not None and sum(len(chunk) for chunk in chunks) >= max_chars:
                    break
            extracted = clean_text("\n".join(chunks))
            return extracted[:max_chars] if max_chars is not None else extracted
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        return ""


def read_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [clean_text("".join(text.text or "" for text in item.findall(".//{*}t"))) for item in root.findall("{*}si")]


def resolve_sheet_paths(archive: zipfile.ZipFile) -> Dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib.get("Id"): rel.attrib.get("Target", "")
        for rel in rels.findall("{*}Relationship")
    }
    sheet_paths: Dict[str, str] = {}
    for sheet in workbook.findall(".//{*}sheet"):
        name = clean_text(sheet.attrib.get("name", ""))
        relationship_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_targets.get(relationship_id, "")
        if not name or not target:
            continue
        target = target.lstrip("/")
        sheet_paths[name] = target if target.startswith("xl/") else f"xl/{target}"
    return sheet_paths


def read_xlsx_sheet_text(
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: Sequence[str],
    keywords: Sequence[str],
    max_rows: int | None = None,
) -> str:
    if sheet_path not in archive.namelist():
        return ""
    root = ET.fromstring(archive.read(sheet_path))
    rows: List[str] = []
    for row_index, row in enumerate(root.findall(".//{*}sheetData/{*}row"), start=1):
        values = [read_cell(cell, shared_strings) for cell in row.findall("{*}c")]
        line = clean_text(" ".join(value for value in values if value))
        if not line:
            continue
        rows.append(line)
        if max_rows is not None and row_index >= max_rows:
            break
    return "\n".join(rows)


def read_cell(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return clean_text("".join(text.text or "" for text in cell.findall(".//{*}t")))

    value_node = cell.find("{*}v")
    if value_node is None or value_node.text is None:
        return ""
    raw_value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return ""
    return clean_text(raw_value)


def topic_keywords(topic: str) -> List[str]:
    normalized_topic = clean_text(topic)
    compact = re.sub(r"\s+", "", normalized_topic)
    parts = [part for part in re.split(r"[\s/·,]+", normalized_topic) if len(part) >= 2]
    keywords = [normalized_topic, compact, *parts]
    keywords.extend(" ".join(parts[index : index + 2]) for index in range(max(0, len(parts) - 1)))
    keywords.extend(compound_topic_keywords(compact, parts))
    keywords.extend(
        (
            "통합",
            "셀프",
            "목적",
            "고객",
            "불편",
            "복잡",
            "인증",
            "BSS",
            "채널",
            "정책",
            "상태",
            "처리",
            "연계",
            "이력",
            "고지",
        )
    )
    return unique_keywords(keywords)


def compound_topic_keywords(compact_topic: str, parts: Sequence[str]) -> List[str]:
    """Add generic Korean compound-topic variants for evidence retrieval.

    This is intentionally not domain-specific. It helps topics written as one
    word, such as "선물주문", match references that use "선물" or "선물 주문".
    """
    compact = clean_text(compact_topic)
    if not compact or len(parts) > 1:
        return []
    keywords: List[str] = []
    for suffix in COMPOUND_TOPIC_SUFFIXES:
        if not compact.endswith(suffix):
            continue
        prefix = compact[: -len(suffix)].strip()
        if len(prefix) < 2:
            continue
        keywords.extend((prefix, suffix, f"{prefix} {suffix}"))
    return keywords


def unique_keywords(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = clean_text(value)
        key = cleaned.casefold()
        if len(cleaned) < 2 or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def score_reference(name: str, text: str, keywords: Sequence[str]) -> int:
    source = f"{normalize(name)}\n{text[:20000]}"
    score = 0
    normalized_name = normalize(name).casefold()
    source_folded = source.casefold()
    for keyword in keywords:
        key = str(keyword or "").casefold()
        if not key or key not in source_folded:
            continue
        if key in GENERIC_REFERENCE_KEYWORDS:
            score += 1
        else:
            score += 12 if key in normalized_name else 4
    if is_global_reference(name):
        score += 8
    if "VoC" in name or "고객" in name:
        score += 2
    score += requirement_level_reference_score_boost(name)
    return score


def is_requirement_level_reference(name: str) -> bool:
    key = normalized_reference_source_key(name)
    return any(marker in key for marker in REQUIREMENT_LEVEL_REFERENCE_MARKERS)


def requirement_level_reference_score_boost(name: str) -> int:
    return REQUIREMENT_LEVEL_REFERENCE_SCORE_BOOST if is_requirement_level_reference(name) else 0


def normalized_reference_source_key(value: object) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", unicodedata.normalize("NFKC", str(value or "")).casefold())


def is_global_reference(name: str) -> bool:
    normalized = normalize(name)
    return any(keyword in normalized for keyword in ("채널 방향성", "T4s 분석", "고객 조사", "고객조사", "벤치마킹", "IA_최종", "IA_최종 정리본", "benchmarking.html", "customer-research.html", "employee-interview.html", "ia-analysis.html", "voc-summary.html"))


def categorize_reference(name: str, text: str) -> str:
    normalized_name = normalize(name)
    if normalized_name in ANALYSIS_SYNTHESIS_HTML_NAMES or normalized_name.startswith("voc-"):
        return ANALYSIS_SYNTHESIS_CATEGORY
    if contains_any(normalized_name, ("1순위", "첨부자료", "사내자료", "요구사항", "작성체크포인트", "작성 체크포인트", "PI_Playbook", "PI Playbook", "PI_산출물", "프로세스 혁신")):
        return "guideline"
    if contains_any(normalized_name, ("개인정보보호위원회", "개인정보보호위", "방송통신위원회", "방통위", "규제기관", "법령", "법률", "약관법")):
        return "compliance"
    if contains_any(normalized_name, ("tworld.co.kr", "shop.tworld", "sktuniverse.co.kr", "고객지원", "공식 서비스", "서비스 안내", "이용약관")):
        return "official"
    if contains_any(normalized_name, ("고객 VoC 분석", "VoC 분석", "고객 VOC 분석")):
        return "voc"
    if contains_any(normalized_name, ("벤치마킹", "경쟁사", "타사")):
        return "benchmark"
    if contains_any(normalized_name, ("채널 AI", "AI 경험", "Agentic", "챗봇", "개인화", "추천")):
        return "ai"
    if contains_any(normalized_name, ("고객 조사", "고객조사", "인사이트", "리서치")):
        return "research"
    if contains_any(normalized_name, ("채널 방향성", "T4s 분석", "T4S 분석", "전략", "통합")):
        return "strategy"
    if contains_any(normalized_name, ("IA_최종", "IA 최종", "IA_", "인포메이션", "메뉴 구조")):
        return "ia"

    source = f"{normalized_name}\n{text[:2000]}"
    if contains_any(source, ("1순위", "첨부자료", "사내자료", "요구사항", "작성체크포인트", "작성 체크포인트", "Process Innovation Playbook", "PI Playbook", "프로세스 혁신", "As-Is", "To-Be 재설계", "Zero-base")):
        return "guideline"
    if contains_any(source, ("개인정보보호위원회", "개인정보보호위", "방송통신위원회", "방통위", "규제기관", "법령", "법률", "개인정보 보호법", "전기통신사업법")):
        return "compliance"
    if contains_any(source, ("tworld.co.kr", "shop.tworld", "sktuniverse.co.kr", "고객지원", "공식 서비스", "서비스 안내", "이용약관")):
        return "official"
    if contains_any(source, ("VoC", "불만", "문의", "고객 VoC")):
        return "voc"
    if contains_any(source, ("벤치마킹", "경쟁사", "타사")):
        return "benchmark"
    if contains_any(source, ("AI", "Agentic", "챗봇", "개인화", "추천")):
        return "ai"
    if contains_any(source, ("고객 조사", "고객조사", "인사이트", "리서치")):
        return "research"
    if contains_any(source, ("채널 방향성", "T4s", "전략", "통합")):
        return "strategy"
    if contains_any(source, ("IA", "메뉴", "depth", "인포메이션", "구조")):
        return "ia"
    return "general"


def extract_focus_signals(name: str, text: str, keywords: Sequence[str], category: str) -> List[str]:
    source = f"{normalize(name)}\n{text}"
    signals = []
    concept_rules = [
        (("목적", "길찾기", "노드", "컨시어지", "분기"), "고객 목적 기반 진입과 길찾기 복잡도 완화"),
        (("셀프", "Self", "온라인", "상담", "오프"), "상담 의존을 줄이는 셀프 처리 완결성"),
        (("BSS", "연계", "오케스트레이션", "원장", "응답"), "채널과 BSS·연계 시스템의 판단 흐름 통합"),
        (("인증", "전환", "마찰", "작은", "불편"), "인증·전환 단계의 마찰 최소화"),
        (("정확", "신뢰", "AI", "할루시네이션", "실행"), "AI·개인화는 정확성과 실행 가능성을 우선"),
        (("개인화", "Right time", "Right offer", "추천"), "개인화는 고객 동의와 맥락에 맞는 시점·제안으로 제한"),
        (("복잡", "어렵", "헤맬", "불편", "오인"), "고객이 헷갈리는 조건과 제한 사유를 사전에 명확화"),
        (("메뉴", "IA", "depth", "탐색", "구조"), "IA와 탐색 경로의 일관성 유지"),
        (("비교", "가격", "혜택", "상세", "선택"), "상품·혜택 비교 기준과 선택 전 영향도 고지"),
        (("장애", "실패", "오류", "재시도", "대체"), "실패·장애 시 재시도와 대체 경로 안내"),
    ]
    for required_terms, signal in concept_rules:
        if contains_any(source, required_terms) and signal not in signals:
            signals.append(signal)

    if category == "voc" and "고객 불편을 정책 예외와 안내 기준으로 환원" not in signals:
        signals.append("고객 불편을 정책 예외와 안내 기준으로 환원")
    if category == "benchmark" and "외부 서비스 수준을 기준으로 비교·선택 경험 보강" not in signals:
        signals.append("외부 서비스 수준을 기준으로 비교·선택 경험 보강")
    if category == ANALYSIS_SYNTHESIS_CATEGORY and "현황 분석 종합 인사이트를 정책 판단축으로 환원" not in signals:
        signals.append("현황 분석 종합 인사이트를 정책 판단축으로 환원")

    if any(keyword.casefold() in source.casefold() for keyword in keywords[:6]):
        topic_signal = "해당 정책 주제와 직접 연결되는 참고 문맥 확인"
        if topic_signal not in signals:
            signals.append(topic_signal)

    return signals[:4]


def extract_evidence_snippets(
    name: str,
    text: str,
    keywords: Sequence[str],
    category: str,
    limit: int = 6,
    max_chars: int = 260,
) -> List[str]:
    source_name = normalize(name)
    snippets: List[str] = []
    priority_terms = unique_keywords(
        list(keywords[:10])
        + [
            "불편",
            "복잡",
            "상담",
            "셀프",
            "BSS",
            "인증",
            "오류",
            "실패",
            "정확",
            "개인화",
            "IA",
            "메뉴",
        ]
    )
    if category == "voc":
        priority_terms.extend(["문의", "불만", "고객"])
    if category == "strategy":
        priority_terms.extend(["전략", "통합", "채널"])
    if category == ANALYSIS_SYNTHESIS_CATEGORY:
        priority_terms.extend(["전략", "전환", "Pain Point", "문제", "기회", "정책서", "요구사항", "통합채널", "반영"])

    for fragment in split_reference_fragments(text):
        if not fragment:
            continue
        if contains_any(fragment, priority_terms):
            snippets.append(limit_text(f"{source_name}: {fragment}", max_chars))
        if len(snippets) >= limit:
            break

    if not snippets and text:
        snippets.append(limit_text(f"{source_name}: {text}", max_chars))
    return unique_nonempty(snippets)[:limit]


def split_reference_fragments(text: str, min_chars: int = 40) -> Iterable[str]:
    for fragment in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|[\n\r]+", text):
        cleaned = clean_text(fragment)
        if len(cleaned) >= min_chars:
            yield cleaned


def summarize_reference(category: str, signals: Sequence[str]) -> str:
    if signals:
        return ", ".join(signals[:3])
    summaries = {
        "strategy": "채널 통합 방향과 목적 기반 경험 원칙을 정책 기준으로 반영한다.",
        "research": "고객 조사에서 드러난 이해도, 신뢰, 불편 요인을 안내와 예외 기준으로 반영한다.",
        "voc": "VoC에서 반복되는 고객 불편을 검증, 고지, 상담 전환 기준으로 반영한다.",
        "ia": "IA 구조와 탐색 흐름을 고객 과업 중심 프로세스와 기능 범위에 반영한다.",
        "benchmark": "벤치마킹 자료의 비교·선택·처리 기대 수준을 고객 경험 기준으로 반영한다.",
        "ai": "AI와 개인화 적용 시 정확성, 신뢰도, 실행 가능성, 폴백 기준을 반영한다.",
        "official": "SKT 공식 서비스 안내, 약관, 고객지원 페이지의 고객 고지와 서비스 기준을 보조 근거로 반영한다.",
        "compliance": "법령과 규제기관 자료에서 확인되는 준수 필요성과 금지선을 개인정보·고지·동의·보관 기준에 반영한다.",
        "guideline": "첨부자료, 사내자료, 요구사항, 템플릿, 샘플을 정책서 구조와 작성 기준으로 해석한다.",
        "requirement": "요구사항 통합 list의 업무 범위와 필수 반영 기준을 정책 구조로 재구성한다.",
        "template": "정책서 템플릿의 장 구성, 표 구조, 작성 가이드를 렌더링 기준으로 사용한다.",
        "sample": "샘플 정책서의 작성 밀도, 문체, 표 구성, 정책 상세 수준을 품질 기준으로 사용한다.",
        ANALYSIS_SYNTHESIS_CATEGORY: "현황 분석 장표에서 정리한 전략, 고객 불편, IA, VoC, 벤치마킹 인사이트를 정책 판단축으로 반영한다.",
        "general": "참고자료의 업무 맥락을 정책 판단 기준으로 재구성한다.",
    }
    return summaries.get(category, summaries["general"])


def category_priority(category: str) -> int:
    return {
        "strategy": 7,
        "research": 6,
        "voc": 5,
        "ia": 4,
        "benchmark": 3,
        "ai": 2,
        "official": 5,
        "compliance": 4,
        "guideline": 6,
        "requirement": 7,
        "template": 6,
        "sample": 6,
        ANALYSIS_SYNTHESIS_CATEGORY: 6,
        "general": 1,
    }.get(category, 0)


def contains_any(text: str, keywords: Sequence[str]) -> bool:
    normalized = text.casefold()
    return any(keyword.casefold() in normalized for keyword in keywords if keyword)


def clean_text(value: object) -> str:
    text = normalize(str(value if value is not None else ""))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def limit_text(value: object, max_chars: int) -> str:
    text = clean_text(value)
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def retain_source_text(value: object, max_chars: int = 120000) -> str:
    """Keep enough source text for downstream chunk-level evidence selection."""
    text = clean_text(value)
    return text if len(text) <= max_chars else text[:max_chars].rstrip()


def unique_nonempty(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = clean_text(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value)
