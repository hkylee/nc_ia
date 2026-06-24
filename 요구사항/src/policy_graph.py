"""Derived SQLite graph layer for policy document quality signals.

The graph is a read-only index rebuilt from existing truth sources:
requirements DB rows, reference evidence chunks, and policy spec JSON.
Generation must stay fail-soft so authoring can continue without this index.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from chain_matrix import build_chain_matrix
    from policy_requirements import RequirementItem, load_scoped_requirements_for_topic
    from runtime_paths import POLICY_GRAPH_DB_PATH, REFERENCE_DB_PATH
except ImportError:  # pragma: no cover - package import fallback.
    from .chain_matrix import build_chain_matrix
    from .policy_requirements import RequirementItem, load_scoped_requirements_for_topic
    from .runtime_paths import POLICY_GRAPH_DB_PATH, REFERENCE_DB_PATH


NODE_TYPES = {
    "DocumentVersion",
    "Requirement",
    "EvidenceChunk",
    "Actor",
    "Usecase",
    "State",
    "StateTransition",
    "Process",
    "Function",
    "PolicyGroup",
    "PolicyItem",
    "InspectionFinding",
    "HealthCheckItem",
}

EDGE_TYPES = {
    "COVERS",
    "DERIVED_FROM",
    "EVIDENCED_BY",
    "MAPS_TO",
    "USES_STATE",
    "IMPLEMENTS",
    "CONSTRAINS",
    "FAILS_GATE",
    "PATCHED_BY",
}

SPEC_NODE_KEYS = {
    "actors": "Actor",
    "usecases": "Usecase",
    "states": "State",
    "state_transitions": "StateTransition",
    "processes": "Process",
    "functions": "Function",
    "policy_groups": "PolicyGroup",
    "policy_details": "PolicyItem",
}

STAGE_NODE_TYPES = {
    "overview": ("Requirement", "EvidenceChunk"),
    "terms": ("Requirement", "EvidenceChunk"),
    "actors": ("Actor", "Requirement"),
    "usecases": ("Usecase", "Actor", "Requirement"),
    "usecase_diagram": ("Usecase", "Actor"),
    "state": ("State", "StateTransition", "Usecase", "Requirement"),
    "process": ("Usecase", "Process", "Function", "PolicyGroup", "Requirement", "EvidenceChunk"),
    "process_detail": ("Usecase", "Process", "Function", "PolicyGroup", "Requirement"),
    "functions": ("Process", "Function", "PolicyGroup", "Requirement", "EvidenceChunk"),
    "function_detail": ("Process", "Function", "PolicyGroup", "PolicyItem", "Requirement"),
    "policies": ("Process", "Function", "PolicyGroup", "PolicyItem", "Requirement", "EvidenceChunk"),
    "terms_refinement": ("State", "Process", "Function", "PolicyGroup", "PolicyItem"),
    "final_check": tuple(sorted(NODE_TYPES - {"EvidenceChunk"})),
}


@dataclass(frozen=True)
class GraphBuildResult:
    db_path: Path
    document_id: str
    topic: str
    node_count: int
    edge_count: int
    coverage_gap_count: int
    chain_gap_count: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": str(self.db_path),
            "document_id": self.document_id,
            "topic": self.topic,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "coverage_gap_count": self.coverage_gap_count,
            "chain_gap_count": self.chain_gap_count,
            "error": self.error,
        }


def ensure_policy_graph_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            topic TEXT,
            document_id TEXT,
            source_id TEXT,
            title TEXT,
            summary TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_edges (
            edge_id TEXT PRIMARY KEY,
            edge_type TEXT NOT NULL,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            topic TEXT,
            document_id TEXT,
            weight REAL NOT NULL DEFAULT 1,
            payload_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_type_topic ON graph_nodes(node_type, topic)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_source ON graph_nodes(source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_type_topic ON graph_edges(edge_type, topic)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_node_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_node_id)")


def build_policy_graph(
    spec: Mapping[str, Any],
    *,
    topic: str = "",
    requirements: Sequence[RequirementItem | Mapping[str, Any] | object] | None = None,
    graph_db_path: Path | str = POLICY_GRAPH_DB_PATH,
    reference_db_path: Path | str = REFERENCE_DB_PATH,
    replace_document: bool = True,
) -> GraphBuildResult:
    """Rebuild graph rows for one policy spec.

    This function deliberately raises on unexpected errors so tests and manual
    rebuild commands can detect failures. Runtime callers should use
    ``try_build_policy_graph``.
    """

    graph_path = Path(graph_db_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = topic or str(meta.get("topic_display") or meta.get("topic") or spec.get("topic") or "").strip()
    document_id = document_node_source_id(spec, topic)
    now = datetime.now().isoformat(timespec="seconds")

    if requirements is None:
        requirements = list(load_scoped_requirements_for_topic(topic)) if topic else []
    else:
        requirements = list(requirements)

    with sqlite3.connect(graph_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_policy_graph_schema(conn)
        conn.execute("PRAGMA foreign_keys = OFF")
        if replace_document:
            conn.execute("DELETE FROM graph_edges WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM graph_nodes WHERE document_id = ?", (document_id,))
        conn.execute(
            "INSERT OR REPLACE INTO graph_metadata(key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO graph_metadata(key, value) VALUES (?, ?)",
            ("last_built_at", now),
        )

        add_node(
            conn,
            node_id=document_node_id(document_id),
            node_type="DocumentVersion",
            topic=topic,
            document_id=document_id,
            source_id=document_id,
            title=str(meta.get("topic_display") or meta.get("topic") or topic or document_id),
            summary=f"{meta.get('document_type', '')} {meta.get('version', '')}".strip(),
            payload={
                "meta": compact_payload(meta),
                "topic": topic,
                "built_at": now,
            },
        )

        requirement_nodes = add_requirement_nodes(conn, requirements, topic=topic, document_id=document_id)
        spec_nodes = add_spec_nodes(conn, spec, topic=topic, document_id=document_id)
        evidence_nodes = add_evidence_chunk_nodes(
            conn,
            topic=topic,
            document_id=document_id,
            reference_db_path=Path(reference_db_path),
            limit=80,
        )

        doc_id = document_node_id(document_id)
        requirement_node_ids = unique([node_id for node_ids in requirement_nodes.values() for node_id in node_ids])
        for node_id in [*requirement_node_ids, *spec_nodes.values(), *evidence_nodes]:
            add_edge(conn, "COVERS", doc_id, node_id, topic=topic, document_id=document_id)

        add_spec_hierarchy_edges(conn, spec, spec_nodes, topic=topic, document_id=document_id)
        add_trace_edges(conn, spec, requirement_nodes, spec_nodes, topic=topic, document_id=document_id)
        add_requirement_inference_edges(conn, requirements, spec, requirement_nodes, spec_nodes, topic=topic, document_id=document_id)
        add_evidence_edges(conn, spec_nodes, evidence_nodes, topic=topic, document_id=document_id)

        conn.commit()
        node_count = int(conn.execute("SELECT COUNT(*) FROM graph_nodes WHERE document_id = ?", (document_id,)).fetchone()[0])
        edge_count = int(conn.execute("SELECT COUNT(*) FROM graph_edges WHERE document_id = ?", (document_id,)).fetchone()[0])
        coverage_gap_count = len(requirement_coverage_gaps(conn, topic=topic, document_id=document_id, limit=10000))
        chain_gap_count = len(chain_consistency_gaps(conn, topic=topic, document_id=document_id, limit=10000))

    return GraphBuildResult(
        db_path=graph_path,
        document_id=document_id,
        topic=topic,
        node_count=node_count,
        edge_count=edge_count,
        coverage_gap_count=coverage_gap_count,
        chain_gap_count=chain_gap_count,
    )


def try_build_policy_graph(
    spec: Mapping[str, Any],
    *,
    topic: str = "",
    requirements: Sequence[RequirementItem | Mapping[str, Any] | object] | None = None,
    graph_db_path: Path | str = POLICY_GRAPH_DB_PATH,
    reference_db_path: Path | str = REFERENCE_DB_PATH,
    replace_document: bool = True,
) -> GraphBuildResult:
    try:
        return build_policy_graph(
            spec,
            topic=topic,
            requirements=requirements,
            graph_db_path=graph_db_path,
            reference_db_path=reference_db_path,
            replace_document=replace_document,
        )
    except Exception as exc:  # pragma: no cover - fail-soft runtime guard.
        meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
        resolved_topic = topic or str(meta.get("topic_display") or meta.get("topic") or spec.get("topic") or "").strip()
        document_id = document_node_source_id(spec, resolved_topic)
        return GraphBuildResult(
            db_path=Path(graph_db_path),
            document_id=document_id,
            topic=resolved_topic,
            node_count=0,
            edge_count=0,
            coverage_gap_count=0,
            chain_gap_count=0,
            error=str(exc),
        )


def query_policy_graph_context(
    *,
    topic: str,
    stage: str = "final_check",
    document_id: str = "",
    graph_db_path: Path | str = POLICY_GRAPH_DB_PATH,
    limit: int = 24,
) -> dict[str, Any]:
    """Return compact graph signals for Context Pack, Inspector, or Health Check."""

    db_path = Path(graph_db_path)
    if not db_path.exists():
        return {"available": False, "reason": "policy_graph.db not found", "stage": stage}
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            ensure_policy_graph_schema(conn)
            resolved_document_id = document_id or latest_document_id(conn, topic)
            if not resolved_document_id:
                return {"available": False, "reason": "no graph document for topic", "stage": stage, "topic": topic}
            coverage = requirement_coverage_gaps(conn, topic=topic, document_id=resolved_document_id, limit=limit)
            chain = chain_consistency_gaps(conn, topic=topic, document_id=resolved_document_id, limit=limit)
            nodes = stage_relevant_nodes(conn, topic=topic, document_id=resolved_document_id, stage=stage, limit=limit)
            paths = graph_paths_for_stage(conn, topic=topic, document_id=resolved_document_id, stage=stage, limit=limit)
            return {
                "available": True,
                "stage": stage,
                "topic": topic,
                "document_id": resolved_document_id,
                "node_counts": graph_node_type_counts(conn, document_id=resolved_document_id),
                "coverage_gaps": coverage,
                "coverage_gap_count": graph_count_requirements_without_mapping(conn, topic=topic, document_id=resolved_document_id),
                "chain_gaps": chain,
                "chain_gap_count": graph_count_chain_gaps(conn, topic=topic, document_id=resolved_document_id),
                "stage_nodes": nodes,
                "paths": paths,
                "token_efficiency_hint": "Writer/Inspector에는 전체 근거 대신 이 연결 경로와 누락 후보를 우선 주입한다.",
            }
    except Exception as exc:  # pragma: no cover - defensive query fallback.
        return {"available": False, "reason": str(exc), "stage": stage, "topic": topic}


def graph_context_for_spec(
    spec: Mapping[str, Any],
    *,
    stage: str,
    topic: str = "",
    graph_db_path: Path | str = POLICY_GRAPH_DB_PATH,
    requirements: Sequence[RequirementItem | Mapping[str, Any] | object] | None = None,
    limit: int = 24,
) -> dict[str, Any]:
    """Build a temporary/up-to-date graph for the spec and return stage context.

    Runtime use is fail-soft. If the graph cannot be built, callers receive a
    compact unavailable reason instead of an exception.
    """

    result = try_build_policy_graph(spec, topic=topic, requirements=requirements, graph_db_path=graph_db_path)
    if result.error:
        return {"available": False, "reason": result.error, "stage": stage, "topic": result.topic}
    return query_policy_graph_context(
        topic=result.topic,
        stage=stage,
        document_id=result.document_id,
        graph_db_path=graph_db_path,
        limit=limit,
    )


def add_requirement_nodes(
    conn: sqlite3.Connection,
    requirements: Sequence[RequirementItem | Mapping[str, Any] | object],
    *,
    topic: str,
    document_id: str,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for index, item in enumerate(requirements, start=1):
        source_id = requirement_source_id(item, index)
        node_id = graph_node_id("Requirement", f"{document_id}:{source_id}")
        title = first_present(item, "detail_name", "parent_name", "requirement_id", "source_number") or source_id
        summary = " ".join(
            text
            for text in (
                first_present(item, "parent_description"),
                first_present(item, "detail_description"),
            )
            if text
        ) or title
        payload = object_to_dict(item)
        add_node(
            conn,
            node_id=node_id,
            node_type="Requirement",
            topic=topic,
            document_id=document_id,
            source_id=source_id,
            title=title,
            summary=summary,
            payload=payload,
        )
        for alias in requirement_aliases(item, index):
            add_requirement_alias(result, alias, node_id)
        add_requirement_alias(result, source_id, node_id)
    return result


def add_requirement_alias(result: dict[str, list[str]], alias: Any, node_id: str) -> None:
    key = normalize_key(alias)
    if not key:
        return
    bucket = result.setdefault(key, [])
    if node_id not in bucket:
        bucket.append(node_id)


def add_spec_nodes(conn: sqlite3.Connection, spec: Mapping[str, Any], *, topic: str, document_id: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for list_key, node_type in SPEC_NODE_KEYS.items():
        for index, row in enumerate(list_rows(spec, list_key), start=1):
            source_id = spec_row_source_id(row, list_key, index)
            node_id = graph_node_id(node_type, f"{document_id}:{source_id}")
            title = str(row.get("name") or row.get("title") or row.get("event") or source_id).strip()
            summary = row_summary(row, node_type)
            add_node(
                conn,
                node_id=node_id,
                node_type=node_type,
                topic=topic,
                document_id=document_id,
                source_id=source_id,
                title=title,
                summary=summary,
                payload=compact_payload(row),
            )
            result[normalize_key(source_id)] = node_id
            if row.get("id"):
                result[normalize_key(row.get("id"))] = node_id
    return result


def add_evidence_chunk_nodes(
    conn: sqlite3.Connection,
    *,
    topic: str,
    document_id: str,
    reference_db_path: Path,
    limit: int,
) -> list[str]:
    if not reference_db_path.exists():
        return []
    try:
        with sqlite3.connect(reference_db_path) as ref_conn:
            ref_conn.row_factory = sqlite3.Row
            tables = {
                row[0]
                for row in ref_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if "chunks" not in tables:
                return []
            columns = {
                row[1]
                for row in ref_conn.execute("PRAGMA table_info(chunks)").fetchall()
            }
            select_cols = [
                "id" if "id" in columns else "rowid",
                "source_name" if "source_name" in columns else "'' AS source_name",
                "title" if "title" in columns else "'' AS title",
                "text AS text" if "text" in columns else ("chunk_text AS text" if "chunk_text" in columns else "'' AS text"),
                "category" if "category" in columns else "'' AS category",
            ]
            topic_filter = ""
            params: list[Any] = []
            if topic and any(col in columns for col in ("title", "text", "chunk_text", "source_name")):
                searchable = " || ' ' || ".join(
                    col for col in ("source_name", "title", "text", "chunk_text") if col in columns
                )
                topic_filter = f"WHERE ({searchable}) LIKE ?"
                params.append(f"%{topic}%")
            rows = ref_conn.execute(
                f"SELECT {', '.join(select_cols)} FROM chunks {topic_filter} LIMIT ?",
                [*params, limit],
            ).fetchall()
    except Exception:
        return []

    result: list[str] = []
    for row in rows:
        source_id = f"REFCHUNK-{row[0]}"
        node_id = graph_node_id("EvidenceChunk", f"{document_id}:{source_id}")
        text = str(row["text"] if "text" in row.keys() else "").strip()
        title = str(row["title"] or row["source_name"] or source_id).strip()
        add_node(
            conn,
            node_id=node_id,
            node_type="EvidenceChunk",
            topic=topic,
            document_id=document_id,
            source_id=source_id,
            title=title,
            summary=limit_text(text or title, 360),
            payload={
                "source_name": row["source_name"] if "source_name" in row.keys() else "",
                "category": row["category"] if "category" in row.keys() else "",
            },
        )
        result.append(node_id)
    return result


def add_spec_hierarchy_edges(
    conn: sqlite3.Connection,
    spec: Mapping[str, Any],
    spec_nodes: Mapping[str, str],
    *,
    topic: str,
    document_id: str,
) -> None:
    for usecase in list_rows(spec, "usecases"):
        usecase_node = lookup_spec_node(spec_nodes, usecase)
        actor_ref = first_value(usecase, "actor_id", "primary_actor_id", "actor")
        actor_node = lookup_node_by_ref(spec_nodes, actor_ref)
        if actor_node and usecase_node:
            add_edge(conn, "IMPLEMENTS", actor_node, usecase_node, topic=topic, document_id=document_id)

    matrix = build_chain_matrix(spec)
    for row in matrix.get("rows", []) if isinstance(matrix.get("rows"), list) else []:
        if not isinstance(row, Mapping):
            continue
        usecase_node = lookup_node_by_ref(spec_nodes, row.get("usecase_id"))
        process_node = lookup_node_by_ref(spec_nodes, row.get("process_id"))
        if usecase_node and process_node:
            add_edge(conn, "IMPLEMENTS", usecase_node, process_node, topic=topic, document_id=document_id)
        for function_id in row.get("function_ids", []) if isinstance(row.get("function_ids"), list) else []:
            function_node = lookup_node_by_ref(spec_nodes, function_id)
            if process_node and function_node:
                add_edge(conn, "IMPLEMENTS", process_node, function_node, topic=topic, document_id=document_id)
        for policy_id in row.get("policy_group_ids", []) if isinstance(row.get("policy_group_ids"), list) else []:
            policy_node = lookup_node_by_ref(spec_nodes, policy_id)
            if process_node and policy_node:
                add_edge(conn, "CONSTRAINS", process_node, policy_node, topic=topic, document_id=document_id)
        for state_id in row.get("state_ids", []) if isinstance(row.get("state_ids"), list) else []:
            state_node = lookup_node_by_ref(spec_nodes, state_id)
            if process_node and state_node:
                add_edge(conn, "USES_STATE", process_node, state_node, topic=topic, document_id=document_id)

    for detail in list_rows(spec, "policy_details"):
        detail_node = lookup_spec_node(spec_nodes, detail)
        policy_id = first_value(detail, "policy_id", "policyId", "policy_group_id", "policyGroupId")
        policy_node = lookup_node_by_ref(spec_nodes, policy_id)
        if policy_node and detail_node:
            add_edge(conn, "CONSTRAINS", policy_node, detail_node, topic=topic, document_id=document_id)

    states_by_name = {normalize_key(row.get("name")): row for row in list_rows(spec, "states")}
    for index, transition in enumerate(list_rows(spec, "state_transitions"), start=1):
        transition_node = lookup_spec_node(spec_nodes, transition, fallback_key=f"state_transitions:{index}")
        for ref in (
            first_value(transition, "current_state_id", "from_state_id", "fromStateId"),
            first_value(transition, "next_state_id", "to_state_id", "toStateId"),
        ):
            state_node = lookup_node_by_ref(spec_nodes, ref)
            if transition_node and state_node:
                add_edge(conn, "USES_STATE", transition_node, state_node, topic=topic, document_id=document_id)
        for name in (
            first_value(transition, "current_state", "from_state", "fromState"),
            first_value(transition, "next_state", "to_state", "toState"),
        ):
            state_row = states_by_name.get(normalize_key(name))
            state_node = lookup_spec_node(spec_nodes, state_row) if state_row else None
            if transition_node and state_node:
                add_edge(conn, "USES_STATE", transition_node, state_node, topic=topic, document_id=document_id)
        for usecase_id in list_values(transition.get("usecase_ids")):
            usecase_node = lookup_node_by_ref(spec_nodes, usecase_id)
            if usecase_node and transition_node:
                add_edge(conn, "MAPS_TO", usecase_node, transition_node, topic=topic, document_id=document_id)


def add_trace_edges(
    conn: sqlite3.Connection,
    spec: Mapping[str, Any],
    requirement_nodes: Mapping[str, Sequence[str]],
    spec_nodes: Mapping[str, str],
    *,
    topic: str,
    document_id: str,
) -> None:
    for row in spec.get("trace_matrix", []) if isinstance(spec.get("trace_matrix"), list) else []:
        if not isinstance(row, Mapping):
            continue
        target_nodes = trace_target_nodes(row, spec_nodes)
        if not target_nodes:
            continue
        for requirement_ref in trace_requirement_refs(row):
            for req_node in lookup_requirement_nodes(requirement_nodes, requirement_ref):
                for target_node in target_nodes:
                    add_edge(conn, "MAPS_TO", req_node, target_node, topic=topic, document_id=document_id)
                    add_edge(conn, "DERIVED_FROM", target_node, req_node, topic=topic, document_id=document_id)


def add_requirement_inference_edges(
    conn: sqlite3.Connection,
    requirements: Sequence[RequirementItem | Mapping[str, Any] | object],
    spec: Mapping[str, Any],
    requirement_nodes: Mapping[str, Sequence[str]],
    spec_nodes: Mapping[str, str],
    *,
    topic: str,
    document_id: str,
) -> None:
    candidates = [
        row
        for key in ("usecases", "processes", "functions", "policy_groups", "policy_details")
        for row in list_rows(spec, key)
    ]
    candidate_texts = [(row, normalized_text(row)) for row in candidates]
    for index, requirement in enumerate(requirements, start=1):
        req_node = first_lookup_requirement_node(requirement_nodes, requirement_source_id(requirement, index))
        if not req_node:
            continue
        aliases = {normalize_key(alias) for alias in requirement_aliases(requirement, index)}
        matched = False
        for row, text in candidate_texts:
            if aliases and any(alias and alias in text for alias in aliases):
                target_node = lookup_spec_node(spec_nodes, row)
                if target_node:
                    add_edge(conn, "MAPS_TO", req_node, target_node, topic=topic, document_id=document_id)
                    add_edge(conn, "DERIVED_FROM", target_node, req_node, topic=topic, document_id=document_id)
                    matched = True
        if matched:
            continue
        tokens = requirement_tokens(requirement)
        if not tokens:
            continue
        ranked: list[tuple[int, Mapping[str, Any]]] = []
        for row, text in candidate_texts:
            hits = sum(1 for token in tokens if token in text)
            if hits:
                ranked.append((hits, row))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        for hits, row in ranked[:2]:
            if hits < max(2, min(4, len(tokens) // 3)):
                continue
            target_node = lookup_spec_node(spec_nodes, row)
            if target_node:
                add_edge(
                    conn,
                    "MAPS_TO",
                    req_node,
                    target_node,
                    topic=topic,
                    document_id=document_id,
                    payload={"match": "token_overlap", "hits": hits},
                )
                add_edge(conn, "DERIVED_FROM", target_node, req_node, topic=topic, document_id=document_id)


def add_evidence_edges(
    conn: sqlite3.Connection,
    spec_nodes: Mapping[str, str],
    evidence_nodes: Sequence[str],
    *,
    topic: str,
    document_id: str,
) -> None:
    if not evidence_nodes:
        return
    # Keep this intentionally sparse: evidence chunks ground the document as a
    # whole until a later semantic linker can create precise chunk-to-node edges.
    for node_id in list(set(spec_nodes.values()))[:80]:
        for evidence_node in evidence_nodes[:3]:
            add_edge(conn, "EVIDENCED_BY", node_id, evidence_node, topic=topic, document_id=document_id, weight=0.3)


def requirement_coverage_gaps(
    conn: sqlite3.Connection,
    *,
    topic: str,
    document_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT n.node_id, n.source_id, n.title, n.summary
        FROM graph_nodes n
        WHERE n.document_id = ?
          AND n.node_type = 'Requirement'
          AND NOT EXISTS (
            SELECT 1
            FROM graph_edges e
            JOIN graph_nodes t ON t.node_id = e.target_node_id
            WHERE e.source_node_id = n.node_id
              AND e.edge_type = 'MAPS_TO'
              AND t.node_type IN ('Usecase', 'State', 'StateTransition', 'Process', 'Function', 'PolicyGroup', 'PolicyItem')
          )
        ORDER BY n.source_id
        LIMIT ?
        """,
        (document_id, limit),
    ).fetchall()
    return [
        {
            "type": "requirement_without_policy_chain",
            "requirement_id": row["source_id"],
            "title": row["title"],
            "summary": limit_text(row["summary"] or "", 160),
            "recommendation": "요구사항을 유즈케이스, 프로세스, 기능, 정책, 정책 항목 중 하나 이상에 연결하세요.",
        }
        for row in rows
    ]


def chain_consistency_gaps(
    conn: sqlite3.Connection,
    *,
    topic: str,
    document_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    queries = [
        (
            "usecase_without_process",
            "Usecase",
            "IMPLEMENTS",
            "Process",
            "유즈케이스를 완료하는 프로세스를 연결하세요.",
        ),
        (
            "process_without_function",
            "Process",
            "IMPLEMENTS",
            "Function",
            "프로세스 수행에 필요한 기능을 연결하세요.",
        ),
        (
            "process_without_policy",
            "Process",
            "CONSTRAINS",
            "PolicyGroup",
            "프로세스의 판단 기준이 되는 정책 그룹을 연결하세요.",
        ),
        (
            "policy_without_item",
            "PolicyGroup",
            "CONSTRAINS",
            "PolicyItem",
            "정책 그룹 아래에 실행 가능한 정책 항목을 작성하세요.",
        ),
    ]
    gaps: list[dict[str, Any]] = []
    for gap_type, source_type, edge_type, target_type, recommendation in queries:
        rows = conn.execute(
            """
            SELECT n.node_id, n.source_id, n.title, n.summary, n.payload_json
            FROM graph_nodes n
            WHERE n.document_id = ?
              AND n.node_type = ?
              AND NOT EXISTS (
                SELECT 1
                FROM graph_edges e
                JOIN graph_nodes t ON t.node_id = e.target_node_id
                WHERE e.source_node_id = n.node_id
                  AND e.edge_type = ?
                  AND t.node_type = ?
              )
            ORDER BY n.source_id
            LIMIT ?
            """,
            (document_id, source_type, edge_type, target_type, max(1, limit - len(gaps))),
        ).fetchall()
        for row in rows:
            if source_type == "Usecase":
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                except json.JSONDecodeError:
                    payload = {}
                if str(payload.get("process_target", "")).strip().upper() == "N":
                    continue
            gaps.append(
                {
                    "type": gap_type,
                    "node_type": source_type,
                    "source_id": row["source_id"],
                    "title": row["title"],
                    "summary": limit_text(row["summary"] or "", 140),
                    "recommendation": recommendation,
                }
            )
            if len(gaps) >= limit:
                return gaps
    return gaps


def graph_count_requirements_without_mapping(conn: sqlite3.Connection, *, topic: str, document_id: str) -> int:
    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM graph_nodes n
            WHERE n.document_id = ?
              AND n.node_type = 'Requirement'
              AND NOT EXISTS (
                SELECT 1
                FROM graph_edges e
                JOIN graph_nodes t ON t.node_id = e.target_node_id
                WHERE e.source_node_id = n.node_id
                  AND e.edge_type = 'MAPS_TO'
                  AND t.node_type IN ('Usecase', 'State', 'StateTransition', 'Process', 'Function', 'PolicyGroup', 'PolicyItem')
              )
            """,
            (document_id,),
        ).fetchone()[0]
    )


def graph_count_chain_gaps(conn: sqlite3.Connection, *, topic: str, document_id: str) -> int:
    return len(chain_consistency_gaps(conn, topic=topic, document_id=document_id, limit=100000))


def graph_node_type_counts(conn: sqlite3.Connection, *, document_id: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT node_type, COUNT(*) AS count
        FROM graph_nodes
        WHERE document_id = ?
        GROUP BY node_type
        """,
        (document_id,),
    ).fetchall()
    return {str(row["node_type"]): int(row["count"]) for row in rows}


def stage_relevant_nodes(
    conn: sqlite3.Connection,
    *,
    topic: str,
    document_id: str,
    stage: str,
    limit: int,
) -> list[dict[str, Any]]:
    node_types = STAGE_NODE_TYPES.get(stage, STAGE_NODE_TYPES.get(strip_stage_number(stage), ("Requirement",)))
    placeholders = ",".join("?" for _ in node_types)
    rows = conn.execute(
        f"""
        SELECT node_type, source_id, title, summary
        FROM graph_nodes
        WHERE document_id = ?
          AND node_type IN ({placeholders})
        ORDER BY node_type, source_id
        LIMIT ?
        """,
        (document_id, *node_types, limit),
    ).fetchall()
    return [
        {
            "type": row["node_type"],
            "id": row["source_id"],
            "title": row["title"],
            "summary": limit_text(row["summary"] or "", 140),
        }
        for row in rows
    ]


def graph_paths_for_stage(
    conn: sqlite3.Connection,
    *,
    topic: str,
    document_id: str,
    stage: str,
    limit: int,
) -> list[dict[str, Any]]:
    if strip_stage_number(stage) not in {"process", "functions", "policies", "final_check", "process_detail", "function_detail"}:
        return []
    rows = conn.execute(
        """
        SELECT
            u.source_id AS usecase_id,
            u.title AS usecase_title,
            p.source_id AS process_id,
            p.title AS process_title,
            f.source_id AS function_id,
            f.title AS function_title,
            pg.source_id AS policy_id,
            pg.title AS policy_title
        FROM graph_nodes u
        LEFT JOIN graph_edges up ON up.source_node_id = u.node_id AND up.edge_type = 'IMPLEMENTS'
        LEFT JOIN graph_nodes p ON p.node_id = up.target_node_id AND p.node_type = 'Process'
        LEFT JOIN graph_edges pf ON pf.source_node_id = p.node_id AND pf.edge_type = 'IMPLEMENTS'
        LEFT JOIN graph_nodes f ON f.node_id = pf.target_node_id AND f.node_type = 'Function'
        LEFT JOIN graph_edges pp ON pp.source_node_id = p.node_id AND pp.edge_type = 'CONSTRAINS'
        LEFT JOIN graph_nodes pg ON pg.node_id = pp.target_node_id AND pg.node_type = 'PolicyGroup'
        WHERE u.document_id = ?
          AND u.node_type = 'Usecase'
        ORDER BY u.source_id, p.source_id, f.source_id, pg.source_id
        LIMIT ?
        """,
        (document_id, limit),
    ).fetchall()
    return [
        {
            "usecase": compact_id_title(row["usecase_id"], row["usecase_title"]),
            "process": compact_id_title(row["process_id"], row["process_title"]),
            "function": compact_id_title(row["function_id"], row["function_title"]),
            "policy": compact_id_title(row["policy_id"], row["policy_title"]),
        }
        for row in rows
        if row["usecase_id"]
    ]


def latest_document_id(conn: sqlite3.Connection, topic: str) -> str:
    row = conn.execute(
        """
        SELECT document_id
        FROM graph_nodes
        WHERE node_type = 'DocumentVersion'
          AND (? = '' OR topic = ?)
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (topic, topic),
    ).fetchone()
    return str(row[0]) if row else ""


def add_node(
    conn: sqlite3.Connection,
    *,
    node_id: str,
    node_type: str,
    topic: str,
    document_id: str,
    source_id: str,
    title: str,
    summary: str,
    payload: Mapping[str, Any],
) -> None:
    if node_type not in NODE_TYPES:
        raise ValueError(f"Unsupported graph node type: {node_type}")
    conn.execute(
        """
        INSERT OR REPLACE INTO graph_nodes
            (node_id, node_type, topic, document_id, source_id, title, summary, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id,
            node_type,
            topic,
            document_id,
            source_id,
            title,
            limit_text(summary, 1000),
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
        ),
    )


def add_edge(
    conn: sqlite3.Connection,
    edge_type: str,
    source_node_id: str,
    target_node_id: str,
    *,
    topic: str,
    document_id: str,
    weight: float = 1,
    payload: Mapping[str, Any] | None = None,
) -> None:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unsupported graph edge type: {edge_type}")
    if not source_node_id or not target_node_id or source_node_id == target_node_id:
        return
    edge_id = stable_id(edge_type, source_node_id, target_node_id, document_id)
    conn.execute(
        """
        INSERT OR REPLACE INTO graph_edges
            (edge_id, edge_type, source_node_id, target_node_id, topic, document_id, weight, payload_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            edge_id,
            edge_type,
            source_node_id,
            target_node_id,
            topic,
            document_id,
            float(weight),
            json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, default=str),
        ),
    )


def document_node_source_id(spec: Mapping[str, Any], topic: str) -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    document_id = str(meta.get("document_id") or "").strip()
    version = str(meta.get("version") or "").strip()
    topic_key = normalize_key(topic or meta.get("topic") or "policy")
    if document_id:
        return f"{document_id}:{topic_key}:{version or 'draft'}"
    return f"POL-{topic_key}:{version or stable_id(compact_payload(meta))[:10]}"


def document_node_id(document_id: str) -> str:
    return graph_node_id("DocumentVersion", document_id)


def graph_node_id(node_type: str, source_id: str) -> str:
    return f"{node_type}:{stable_id(source_id)[:24]}"


def stable_id(*parts: Any) -> str:
    raw = "|".join(json.dumps(part, ensure_ascii=False, sort_keys=True, default=str) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def list_rows(spec: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    value = spec.get(key, [])
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def spec_row_source_id(row: Mapping[str, Any], list_key: str, index: int) -> str:
    if row.get("id"):
        return str(row.get("id")).strip()
    if list_key == "state_transitions":
        current = first_value(row, "current_state", "current_state_id", "from_state", "from_state_id")
        event = first_value(row, "event", "transition_event")
        next_state = first_value(row, "next_state", "next_state_id", "to_state", "to_state_id")
        return f"STT-{stable_id(current, event, next_state)[:10]}"
    if row.get("policy_id") and row.get("name"):
        return f"{row.get('policy_id')}:{row.get('name')}"
    return f"{list_key}:{index}"


def lookup_spec_node(spec_nodes: Mapping[str, str], row: Mapping[str, Any] | None, fallback_key: str = "") -> str:
    if not row:
        return ""
    for key in ("id", "policy_id", "process_id", "function_id"):
        if row.get(key):
            node = lookup_node_by_ref(spec_nodes, row.get(key))
            if node:
                return node
    if row.get("name"):
        node = lookup_node_by_ref(spec_nodes, row.get("name"))
        if node:
            return node
    return lookup_node_by_ref(spec_nodes, fallback_key)


def lookup_node_by_ref(nodes: Mapping[str, str], value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            found = lookup_node_by_ref(nodes, item)
            if found:
                return found
        return ""
    key = normalize_key(value)
    if not key:
        return ""
    if key in nodes:
        return nodes[key]
    for known, node_id in nodes.items():
        if key and key in known:
            return node_id
    return ""


def lookup_requirement_node(nodes: Mapping[str, Sequence[str]], value: Any) -> str:
    return first_lookup_requirement_node(nodes, value)


def first_lookup_requirement_node(nodes: Mapping[str, Sequence[str]], value: Any) -> str:
    found = lookup_requirement_nodes(nodes, value)
    return found[0] if found else ""


def lookup_requirement_nodes(nodes: Mapping[str, Sequence[str]], value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    key = normalize_key(str(value or "").removeprefix("REQ-"))
    if key in nodes:
        return list(nodes[key])
    req_key = normalize_key(value)
    if req_key in nodes:
        return list(nodes[req_key])
    id_match = re.match(r"^((?:REQ-)?[0-9A-Za-z][0-9A-Za-z_-]*(?:-\d{2,4})?)\b", raw)
    if id_match:
        id_key = normalize_key(id_match.group(1))
        if id_key in nodes:
            return list(nodes[id_key])
    return []


def trace_target_node(row: Mapping[str, Any], spec_nodes: Mapping[str, str]) -> str:
    nodes = trace_target_nodes(row, spec_nodes)
    return nodes[0] if nodes else ""


def trace_target_nodes(row: Mapping[str, Any], spec_nodes: Mapping[str, str]) -> list[str]:
    result: list[str] = []
    for value in trace_target_refs(row):
        found = lookup_node_by_ref(spec_nodes, value)
        if found:
            result.append(found)
    return unique(result)


def trace_target_refs(row: Mapping[str, Any]) -> list[Any]:
    refs: list[Any] = [row.get("item_id"), row.get("target_id"), row.get("id")]
    refs.extend(list_values(row.get("mapped_to")))
    for key in (
        "mapped_usecases",
        "mapped_states",
        "mapped_state_transitions",
        "mapped_processes",
        "mapped_functions",
        "mapped_policies",
        "mapped_policy_items",
    ):
        refs.extend(list_values(row.get(key)))
    return [ref for ref in refs if str(ref or "").strip()]


def trace_requirement_refs(row: Mapping[str, Any]) -> list[Any]:
    refs: list[Any] = []
    for key in ("evidence_ids", "requirement_ids", "requirements", "sample_detail_requirements"):
        refs.extend(list_values(row.get(key)))
    for key in ("requirement_id", "requirement_no", "detail_id", "source_number", "source", "requirement_group"):
        value = row.get(key)
        if str(value or "").strip():
            refs.append(value)
    return unique([str(ref) for ref in refs if str(ref or "").strip()])


def requirement_source_id(item: RequirementItem | Mapping[str, Any] | object, index: int) -> str:
    for key in ("detail_id", "requirement_id", "source_number"):
        value = first_present(item, key)
        if value:
            return str(value)
    return f"REQ-{index:03d}"


def requirement_aliases(item: RequirementItem | Mapping[str, Any] | object, index: int) -> list[str]:
    return [
        first_present(item, "detail_id"),
        first_present(item, "requirement_id"),
        first_present(item, "source_number"),
        first_present(item, "detail_name"),
        first_present(item, "parent_name"),
        f"REQ-{first_present(item, 'detail_id')}",
        f"REQ-{first_present(item, 'requirement_id')}",
        f"REQ-{first_present(item, 'source_number')}",
        requirement_source_id(item, index),
    ]


def requirement_tokens(item: RequirementItem | Mapping[str, Any] | object) -> list[str]:
    text = normalized_text(
        {
            "detail_name": first_present(item, "detail_name"),
            "detail_description": first_present(item, "detail_description"),
            "parent_name": first_present(item, "parent_name"),
            "parent_description": first_present(item, "parent_description"),
        }
    )
    tokens = [
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", text)
        if token not in {"고객", "업무", "기준", "정책", "처리", "관리", "확인", "제공", "정의", "통합"}
    ]
    return unique(tokens)[:18]


def first_present(item: RequirementItem | Mapping[str, Any] | object, *keys: str) -> str:
    for key in keys:
        if isinstance(item, Mapping):
            value = item.get(key, "")
        else:
            value = getattr(item, key, "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def first_value(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            value = next((item for item in value if str(item).strip()), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,;/\s]+", text) if item.strip()]


def row_summary(row: Mapping[str, Any], node_type: str) -> str:
    keys = {
        "Actor": ("responsibility", "description", "type"),
        "Usecase": ("description", "goal", "actor", "process_target"),
        "State": ("description", "next_action"),
        "StateTransition": ("event", "criteria", "current_state", "next_state"),
        "Process": ("description", "related_functions", "related_policies"),
        "Function": ("description", "details", "process_id", "process_ids"),
        "PolicyGroup": ("description", "items"),
        "PolicyItem": ("content", "description", "policy_id"),
    }.get(node_type, ("description", "content"))
    values: list[str] = []
    for key in keys:
        value = row.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value[:8])
        if value:
            values.append(str(value))
    return " ".join(values)[:1000]


def normalized_text(payload: Any) -> str:
    return normalize_key(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def normalize_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()


def compact_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def object_to_dict(item: RequirementItem | Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return compact_payload(item)
    return {
        key: value
        for key in dir(item)
        if not key.startswith("_")
        and not callable(value := getattr(item, key, None))
        and value not in (None, "", [], {})
    }


def unique(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def compact_id_title(source_id: Any, title: Any) -> str:
    source = str(source_id or "").strip()
    text = str(title or "").strip()
    if source and text:
        return f"{source} {limit_text(text, 48)}"
    return source or limit_text(text, 48)


def strip_stage_number(stage: str) -> str:
    return re.sub(r"^\d+[_-]", "", str(stage or "").strip())


def limit_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"
