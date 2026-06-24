#!/usr/bin/env python3
"""Build a channel PI status dashboard with the analysis-policy alignment agent."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from analysis_policy_alignment import (
        build_analysis_policy_alignment_report,
        extract_policy_elements,
        first_non_empty,
        load_analysis_evidence,
        normalize_key,
        pair_score,
        tokenize,
        top_shared_terms,
        weighted_overlap,
    )
except ImportError:  # pragma: no cover - package import fallback.
    from .analysis_policy_alignment import (
        build_analysis_policy_alignment_report,
        extract_policy_elements,
        first_non_empty,
        load_analysis_evidence,
        normalize_key,
        pair_score,
        tokenize,
        top_shared_terms,
        weighted_overlap,
    )


CHANNEL_PI_STATUS_VERSION = "1.2"
CHANNEL_PI_STATUS_FILE = "channel_pi_status.json"
EXCLUDED_SOURCE_COVERAGE_GROUPS = {"VoC 분석 종합"}
MAX_REQUIREMENT_TRACE_ROWS = 260
MAX_TRACE_BRIDGE_ITEMS = 8
MAX_ANALYSIS_ITEM_MATCHES = 4
TRACE_MAPPED_FIELDS = (
    "mapped_to",
    "mapped_usecases",
    "mapped_usecase",
    "mapped_processes",
    "mapped_process",
    "mapped_functions",
    "mapped_function",
    "mapped_policies",
    "mapped_policy",
    "mapped_policy_groups",
    "mapped_policy_details",
    "mapped_states",
    "mapped_state",
    "links",
)
TRACE_SELF_ELEMENT_FIELDS = ("item_id", "artifact_id")
TRACE_REQUIREMENT_ID_FIELDS = (
    "detail_id",
    "detail_requirement_id",
    "detail_requirement_ids",
    "requirement_id",
    "requirement_ids",
    "source_number",
    "requirement_no",
)
TRACE_ANALYSIS_EVIDENCE_FIELDS = (
    "analysis_evidence_ids",
    "analysis_evidence_id",
    "source_evidence_ids",
    "source_evidence_id",
    "evidence_ids",
)
TRACE_ANALYSIS_SOURCE_GROUP_FIELDS = (
    "analysis_source_groups",
    "analysis_source_group",
    "source_groups",
    "source_group",
)
POLICY_SPEC_NAME_RE = re.compile(
    r"^NC_(?P<topic>.+?)_정책서_(?P<label>간소화|Full)_(?P<version>v\d+\.\d+)(?P<suffix>_보완본)?_spec\.json$"
)


def build_channel_pi_status_report(
    *,
    output_root: Path,
    evidence_db_path: Path,
    requirements_db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a deterministic channel PI status report from the latest policy specs."""

    policy_records = latest_policy_spec_records(output_root)
    if not policy_records:
        raise ValueError("점검할 정책서 spec 파일을 찾지 못했습니다.")

    evidence_summary = load_evidence_summary(evidence_db_path)
    requirements_summary = load_requirements_summary(requirements_db_path) if requirements_db_path else {}
    requirement_rows_by_topic = load_requirement_rows_by_topic(requirements_db_path) if requirements_db_path else {}
    analysis_evidence = load_analysis_evidence(evidence_db_path)

    topic_rows: List[Dict[str, Any]] = []
    global_policy_elements: List[Dict[str, Any]] = []
    source_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "covered": 0, "partial": 0, "missing": 0})
    alignment_errors: List[Dict[str, str]] = []

    for record in policy_records:
        try:
            spec = load_json(record["specPath"])
            global_policy_elements.extend(annotated_policy_elements(spec, record))
            alignment_report = build_analysis_policy_alignment_report(
                spec=spec,
                policy_file_name=record["policyFile"],
                evidence_db_path=evidence_db_path,
            )
            trace_stats = policy_trace_stats(spec)
            requirement_rows = requirement_rows_for_policy(requirement_rows_by_topic, spec, record)
            trace_bridge = evaluate_trace_bridge(spec, requirement_rows, analysis_evidence, trace_stats)
            density_stats = policy_density_stats(spec, trace_stats)
            row = build_topic_row(record, spec, alignment_report, trace_stats, density_stats, trace_bridge)
            topic_rows.append(row)
            for source in alignment_report.get("sourceCoverage", []):
                if not isinstance(source, Mapping):
                    continue
                group = str(source.get("sourceGroup") or "분석 출처")
                if group in EXCLUDED_SOURCE_COVERAGE_GROUPS:
                    continue
                source_totals[group]["total"] += safe_int(source.get("total"))
                source_totals[group]["covered"] += safe_int(source.get("covered"))
                source_totals[group]["partial"] += safe_int(source.get("partial"))
                source_totals[group]["missing"] += safe_int(source.get("missing"))
        except Exception as exc:  # pragma: no cover - defensive aggregation boundary.
            alignment_errors.append({"policyFile": record["policyFile"], "error": str(exc)})

    if not topic_rows:
        error_message = alignment_errors[0]["error"] if alignment_errors else "정렬 에이전트 실행 결과가 없습니다."
        raise ValueError(f"채널 PI 현황을 생성하지 못했습니다: {error_message}")

    analysis_item_coverage = build_analysis_item_coverage(
        analysis_evidence,
        global_policy_elements,
        requirement_rows_by_topic,
    )
    analysis_item_summary = analysis_item_coverage.get("summary", {})
    topic_rows.sort(key=lambda row: (safe_int(row.get("score")), -safe_int(row.get("actionItemCount")), str(row.get("topic") or "")))
    cross_validation = build_cross_validation_report(analysis_item_coverage.get("items", []), topic_rows)
    analysis_item_summary.update(
        {
            "trustedCovered": safe_int(cross_validation.get("trustedCovered")),
            "reviewNeeded": safe_int(cross_validation.get("reviewNeeded")),
            "trustedCoverageRate": safe_int(cross_validation.get("trustedCoverageRate")),
        }
    )
    dimensions = build_channel_dimensions(topic_rows, evidence_summary, analysis_item_summary, cross_validation)
    stage_flow = build_stage_flow(output_root, evidence_summary, requirements_summary, topic_rows)
    overall_score = weighted_average(
        [
            (dimension["score"], dimension["weight"])
            for dimension in dimensions
            if isinstance(dimension, Mapping)
        ]
    )
    judgement = channel_pi_judgement(overall_score)
    source_coverage = aggregate_source_coverage(source_totals)
    priority_actions = build_priority_actions(topic_rows, alignment_errors)

    return {
        "agent": "Channel PI Status",
        "alignmentAgent": "분석-정책 정렬 진단",
        "version": CHANNEL_PI_STATUS_VERSION,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "score": overall_score,
        "judgement": judgement,
        "summary": build_channel_summary(overall_score, topic_rows, dimensions),
        "topicCount": len(topic_rows),
        "policySpecCount": len(policy_records),
        "requirements": requirements_summary,
        "evidence": evidence_summary,
        "stageFlow": stage_flow,
        "dimensions": dimensions,
        "sourceCoverage": source_coverage,
        "analysisItemCoverageSummary": analysis_item_summary,
        "analysisItemCoverage": analysis_item_coverage.get("items", []),
        "crossValidation": cross_validation,
        "topicRows": topic_rows,
        "priorityActions": priority_actions,
        "errors": alignment_errors,
        "method": {
            "type": "deterministic",
            "description": "최신 정책서 spec마다 분석-정책 정렬 에이전트를 실행하고, 직접 문장 매칭과 상세 요구사항 trace를 함께 반영해 채널 PI 현황을 산정합니다.",
            "keptSeparateFrom": "PI Check",
        },
    }


def latest_policy_spec_records(output_root: Path) -> List[Dict[str, Any]]:
    latest_by_topic: Dict[str, Dict[str, Any]] = {}
    for path in sorted(output_root.glob("NC_*_정책서_*_spec.json")):
        match = POLICY_SPEC_NAME_RE.match(path.name)
        if not match:
            continue
        topic_slug = match.group("topic")
        label = match.group("label")
        version = match.group("version")
        suffix = match.group("suffix") or ""
        policy_file = f"NC_{topic_slug}_정책서_{label}_{version}{suffix}.html"
        record = {
            "topicSlug": topic_slug,
            "templateLabel": label,
            "version": version,
            "suffix": suffix,
            "policyFile": policy_file,
            "specFile": path.name,
            "specPath": path,
            "sortKey": policy_spec_sort_key(version, suffix, label),
        }
        previous = latest_by_topic.get(topic_slug)
        if previous is None or record["sortKey"] > previous["sortKey"]:
            latest_by_topic[topic_slug] = record
    return sorted(latest_by_topic.values(), key=lambda item: str(item["topicSlug"]))


def policy_spec_sort_key(version: str, suffix: str, label: str) -> Tuple[int, int, int, int]:
    parts = re.findall(r"\d+", str(version or ""))
    major = int(parts[0]) if parts else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    suffix_score = 1 if suffix else 0
    label_score = 1 if label == "Full" else 0
    return major, minor, suffix_score, label_score


def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return data


def build_topic_row(
    record: Mapping[str, Any],
    spec: Mapping[str, Any],
    alignment_report: Mapping[str, Any],
    trace_stats: Mapping[str, Any],
    density_stats: Mapping[str, Any],
    trace_bridge: Mapping[str, Any],
) -> Dict[str, Any]:
    raw_score = safe_int(alignment_report.get("score"))
    trace_supported_score = trace_supported_alignment_score(
        raw_score=raw_score,
        alignment_report=alignment_report,
        trace_stats=trace_stats,
        trace_bridge=trace_bridge,
    )
    score = max(raw_score, trace_supported_score)
    action_items = alignment_report.get("actionItems", [])
    stats = alignment_report.get("stats", {}) if isinstance(alignment_report.get("stats"), Mapping) else {}
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    return {
        "topic": str(meta.get("topic_display") or meta.get("topic") or record.get("topicSlug") or ""),
        "topicSlug": str(record.get("topicSlug") or ""),
        "policyFile": str(record.get("policyFile") or alignment_report.get("policyFile") or ""),
        "specFile": str(record.get("specFile") or ""),
        "version": str(meta.get("version") or record.get("version") or ""),
        "templateLabel": str(record.get("templateLabel") or meta.get("template_label") or ""),
        "score": score,
        "rawAlignmentScore": raw_score,
        "traceSupportedScore": trace_supported_score,
        "judgement": channel_pi_judgement(score),
        "status": topic_status(score),
        "analysisCoverageRate": safe_int(alignment_report.get("analysisCoverageRate")),
        "policyGroundingRate": safe_int(alignment_report.get("policyGroundingRate")),
        "analysisRequirementCoverageRate": safe_int(trace_bridge.get("analysisRequirementCoverageRate")),
        "requirementPolicyTraceRate": safe_int(trace_bridge.get("requirementPolicyTraceRate")),
        "traceContinuityRate": safe_int(trace_bridge.get("traceContinuityRate")),
        "dbRequirementMappingRate": safe_int(trace_bridge.get("dbRequirementMappingRate")),
        "analysisMissing": safe_int(stats.get("analysisMissing")),
        "policyUnsupported": safe_int(stats.get("policyUnsupported")),
        "requirementCount": safe_int(trace_stats.get("requirementCount")),
        "traceCoverageRate": safe_int(trace_stats.get("coverageRate")),
        "mappedIdResolveRate": safe_int(trace_stats.get("mappedIdResolveRate")),
        "unresolvedMappedIdCount": safe_int(trace_stats.get("unresolvedMappedIdCount")),
        "traceRowCount": safe_int(trace_stats.get("rowCount")),
        "mappedElementCount": safe_int(trace_stats.get("mappedElementCount")),
        "explicitRequirementTraceRowCount": safe_int(trace_stats.get("explicitRequirementTraceRowCount")),
        "traceSchemaCompletenessRate": safe_int(trace_stats.get("traceSchemaCompletenessRate")),
        "directRequirementTraceRate": safe_int(trace_stats.get("directRequirementTraceRate")),
        "uniqueRequirementTraceRate": safe_int(trace_stats.get("uniqueRequirementTraceRate")),
        "traceConfidenceScore": safe_int(trace_stats.get("traceConfidenceScore")),
        "traceConfidenceLabel": str(trace_stats.get("traceConfidenceLabel") or ""),
        "directRequirementIdCount": safe_int(trace_stats.get("directRequirementIdCount")),
        "evidenceRequirementIdCount": safe_int(trace_stats.get("evidenceRequirementIdCount")),
        "groupedRequirementTraceRowCount": safe_int(trace_stats.get("groupedRequirementTraceRowCount")),
        "coverageStatusCounts": trace_stats.get("coverageStatusCounts", {}) if isinstance(trace_stats.get("coverageStatusCounts"), Mapping) else {},
        "traceBridgeItems": trace_bridge.get("items", []) if isinstance(trace_bridge.get("items"), list) else [],
        "policyDensityScore": safe_int(density_stats.get("score")),
        "policyDetailCount": safe_int(density_stats.get("policyDetailCount")),
        "processCount": safe_int(density_stats.get("processCount")),
        "functionCount": safe_int(density_stats.get("functionCount")),
        "actionItemCount": len(action_items) if isinstance(action_items, list) else 0,
        "topAction": first_action_text(action_items),
        "traceAction": first_action_text(trace_bridge.get("actions")),
        "summary": str(alignment_report.get("summary") or ""),
    }


def trace_supported_alignment_score(
    *,
    raw_score: int,
    alignment_report: Mapping[str, Any],
    trace_stats: Mapping[str, Any],
    trace_bridge: Mapping[str, Any],
) -> int:
    """Blend direct text matching with trusted trace continuity.

    The alignment agent intentionally starts with direct analysis-policy text
    similarity. In this product, however, strong detail-requirement trace is a
    first-class proof path. When the trace is structured and resolves to real
    policy elements, use it as a second-opinion score instead of forcing the
    policy document to repeat analysis vocabulary.
    """

    direct_context = round(
        safe_int(alignment_report.get("analysisCoverageRate")) * 0.50
        + safe_int(alignment_report.get("policyGroundingRate")) * 0.50
    )
    trace_support = weighted_average(
        [
            (trace_bridge.get("analysisRequirementCoverageRate"), 0.25),
            (trace_bridge.get("requirementPolicyTraceRate"), 0.30),
            (trace_bridge.get("traceContinuityRate"), 0.25),
            (trace_stats.get("traceConfidenceScore"), 0.20),
        ]
    )
    direct_requirement_rate = safe_int(trace_stats.get("directRequirementTraceRate"))
    requirement_policy_rate = safe_int(trace_bridge.get("requirementPolicyTraceRate"))
    trace_confidence = safe_int(trace_stats.get("traceConfidenceScore"))

    if trace_confidence >= 85 and direct_requirement_rate >= 85 and requirement_policy_rate >= 85:
        blended = max(trace_support, round(direct_context * 0.15 + trace_support * 0.85))
    elif trace_support >= 70 and requirement_policy_rate >= 70:
        blended = round(direct_context * 0.40 + trace_support * 0.60)
    else:
        blended = round(direct_context * 0.70 + trace_support * 0.30)
    return max(0, min(95, max(raw_score, blended)))


def policy_trace_stats(spec: Mapping[str, Any]) -> Dict[str, Any]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    requirement_count = safe_int(meta.get("requirements_count"))
    trace_rows = spec.get("trace_matrix", [])
    rows = trace_rows if isinstance(trace_rows, list) else []
    weighted_total = 0.0
    weighted_covered = 0.0
    mapped_ids: set[str] = set()
    explicit_requirement_rows = 0
    grouped_requirement_rows = 0
    evidence_requirement_rows = 0
    direct_requirement_ids: set[str] = set()
    evidence_requirement_ids: set[str] = set()
    unknown_rows = 0
    covered_rows = 0
    partial_rows = 0
    missing_rows = 0
    element_ids = policy_element_id_set(spec)

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        normalized = normalize_trace_row(row)
        count = safe_int(normalized.get("detailRequirementCount"), default=0)
        if count <= 0:
            continue
        factor = float(normalized.get("coverageFactor") or 0.0)
        status = str(normalized.get("coverageStatus") or "unknown")
        if normalized.get("hasRequirementSignal"):
            explicit_requirement_rows += 1
        source = str(normalized.get("requirementIdSource") or "none")
        if source == "direct":
            direct_requirement_ids.update(str(item) for item in normalized.get("directRequirementIds", []) if str(item or "").strip())
        elif source == "evidence":
            evidence_requirement_rows += 1
            evidence_requirement_ids.update(str(item) for item in normalized.get("evidenceRequirementIds", []) if str(item or "").strip())
        elif source in {"group", "text"}:
            grouped_requirement_rows += 1
        if status == "covered":
            covered_rows += 1
        elif status == "partial":
            partial_rows += 1
        elif status == "missing":
            missing_rows += 1
        else:
            unknown_rows += 1
        weighted_total += count
        weighted_covered += count * factor
        mapped_ids.update(str(item) for item in normalized.get("mappedIds", []) if str(item or "").strip())

    denominator = max(requirement_count, int(weighted_total), 1)
    coverage_rate = round((weighted_covered / max(1, denominator)) * 100)
    resolved_ids = {item for item in mapped_ids if item in element_ids}
    unresolved_ids = sorted(mapped_ids - resolved_ids)
    mapped_resolve_rate = round((len(resolved_ids) / max(1, len(mapped_ids))) * 100) if mapped_ids else 0
    unique_requirement_ids = direct_requirement_ids | evidence_requirement_ids
    direct_requirement_rate = round((len(direct_requirement_ids) / max(1, denominator)) * 100)
    evidence_requirement_rate = round((len(evidence_requirement_ids) / max(1, denominator)) * 100)
    unique_requirement_rate = round((len(unique_requirement_ids) / max(1, denominator)) * 100)
    row_signal_rate = round((explicit_requirement_rows / max(1, len(rows))) * 100) if rows else 0
    schema_completeness_rate = round(
        min(100, direct_requirement_rate) * 0.7
        + min(100, evidence_requirement_rate) * 0.2
        + row_signal_rate * 0.1
    )
    if direct_requirement_rate == 0 and evidence_requirement_rate == 0 and grouped_requirement_rows:
        schema_completeness_rate = min(schema_completeness_rate, 45)
    elif direct_requirement_rate == 0 and evidence_requirement_rate > 0:
        schema_completeness_rate = min(schema_completeness_rate, 65)
    trace_confidence_score = round(
        schema_completeness_rate * 0.45
        + mapped_resolve_rate * 0.30
        + max(0, min(100, coverage_rate)) * 0.25
    )
    return {
        "requirementCount": denominator,
        "coverageRate": max(0, min(100, coverage_rate)),
        "rowCount": len(rows),
        "mappedElementCount": len(mapped_ids),
        "mappedIdResolveRate": max(0, min(100, mapped_resolve_rate)),
        "unresolvedMappedIdCount": len(unresolved_ids),
        "unresolvedMappedIds": unresolved_ids[:20],
        "explicitRequirementTraceRowCount": explicit_requirement_rows,
        "groupedRequirementTraceRowCount": grouped_requirement_rows,
        "evidenceRequirementTraceRowCount": evidence_requirement_rows,
        "directRequirementIdCount": len(direct_requirement_ids),
        "evidenceRequirementIdCount": len(evidence_requirement_ids),
        "uniqueRequirementTraceCount": len(unique_requirement_ids),
        "directRequirementTraceRate": max(0, min(100, direct_requirement_rate)),
        "evidenceRequirementTraceRate": max(0, min(100, evidence_requirement_rate)),
        "uniqueRequirementTraceRate": max(0, min(100, unique_requirement_rate)),
        "traceSchemaCompletenessRate": schema_completeness_rate,
        "traceConfidenceScore": max(0, min(100, trace_confidence_score)),
        "traceConfidenceLabel": trace_confidence_label(trace_confidence_score, direct_requirement_rate, unique_requirement_rate),
        "coverageStatusCounts": {
            "covered": covered_rows,
            "partial": partial_rows,
            "missing": missing_rows,
            "unknown": unknown_rows,
        },
    }


def policy_element_id_set(spec: Mapping[str, Any]) -> set[str]:
    ids: set[str] = {"OVERVIEW"}
    overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
    principles = overview.get("principles", [])
    if isinstance(principles, list):
        for index, _ in enumerate(principles, 1):
            ids.add(f"PRINCIPLE-{index:02d}")
    for key in ("usecases", "states", "processes", "functions", "policy_groups", "policy_details"):
        rows = spec.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("id") or "").strip():
                ids.add(str(row.get("id")).strip())
    for row in spec.get("policy_groups", []) if isinstance(spec.get("policy_groups"), list) else []:
        if not isinstance(row, Mapping):
            continue
        items = row.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, Mapping) and str(item.get("id") or "").strip():
                ids.add(str(item.get("id")).strip())
    return ids


def policy_density_stats(spec: Mapping[str, Any], trace_stats: Mapping[str, Any]) -> Dict[str, Any]:
    process_count = len(spec.get("processes", [])) if isinstance(spec.get("processes"), list) else 0
    function_count = len(spec.get("functions", [])) if isinstance(spec.get("functions"), list) else 0
    policy_group_count = len(spec.get("policy_groups", [])) if isinstance(spec.get("policy_groups"), list) else 0
    policy_detail_count = len(spec.get("policy_details", [])) if isinstance(spec.get("policy_details"), list) else 0
    requirement_count = safe_int(trace_stats.get("requirementCount"), default=1)
    detail_target = max(12, round(requirement_count * 0.55))
    score = round(
        min(1.0, process_count / 10) * 20
        + min(1.0, function_count / 10) * 20
        + min(1.0, policy_group_count / 8) * 15
        + min(1.0, policy_detail_count / detail_target) * 30
        + min(1.0, safe_int(trace_stats.get("coverageRate")) / 100) * 15
    )
    return {
        "score": max(0, min(100, score)),
        "processCount": process_count,
        "functionCount": function_count,
        "policyGroupCount": policy_group_count,
        "policyDetailCount": policy_detail_count,
    }


def load_evidence_summary(evidence_db_path: Path) -> Dict[str, Any]:
    if not evidence_db_path.exists():
        return {"dbPath": str(evidence_db_path), "documentCount": 0, "evidenceCount": 0, "analysisDocumentCount": 0, "analysisEvidenceCount": 0, "sourceGroups": []}
    with sqlite3.connect(evidence_db_path) as conn:
        conn.row_factory = sqlite3.Row
        document_count = safe_int(conn.execute("select count(*) from documents").fetchone()[0])
        evidence_count = safe_int(conn.execute("select count(*) from evidence_items").fetchone()[0])
        analysis_document_count = safe_int(conn.execute("select count(*) from documents where category = 'analysis_synthesis'").fetchone()[0])
        analysis_evidence_count = safe_int(
            conn.execute(
                """
                select count(*)
                from evidence_items e
                join documents d on d.document_id = e.document_id
                where d.category = 'analysis_synthesis'
                """
            ).fetchone()[0]
        )
        source_groups = []
        for row in conn.execute(
            """
            select d.source_name, count(e.evidence_id) as evidence_count
            from documents d
            left join evidence_items e on e.document_id = d.document_id
            where d.category = 'analysis_synthesis'
            group by d.source_name
            order by evidence_count desc, d.source_name
            """
        ):
            source_groups.append({"sourceName": str(row["source_name"] or ""), "evidenceCount": safe_int(row["evidence_count"])})
    return {
        "dbPath": str(evidence_db_path),
        "documentCount": document_count,
        "evidenceCount": evidence_count,
        "analysisDocumentCount": analysis_document_count,
        "analysisEvidenceCount": analysis_evidence_count,
        "sourceGroups": source_groups[:12],
    }


def load_requirements_summary(requirements_db_path: Optional[Path]) -> Dict[str, Any]:
    if not requirements_db_path or not requirements_db_path.exists():
        return {"dbPath": str(requirements_db_path or ""), "detailCount": 0, "topicCount": 0, "mappedCount": 0}
    with sqlite3.connect(requirements_db_path) as conn:
        detail_count = safe_int(
            conn.execute(
                "select count(*) from requirement_rows where coalesce(trim(detail_id), '') <> ''"
            ).fetchone()[0]
        )
        topic_count = safe_int(
            conn.execute(
                "select count(distinct normalized_depth4) from requirement_rows where coalesce(trim(normalized_depth4), '') <> ''"
            ).fetchone()[0]
        )
        mapped_count = safe_int(
            conn.execute(
                "select count(*) from requirement_rows where coalesce(trim(policy_mapping_status), '') <> ''"
            ).fetchone()[0]
        )
    return {
        "dbPath": str(requirements_db_path),
        "detailCount": detail_count,
        "topicCount": topic_count,
        "mappedCount": mapped_count,
    }


def load_requirement_rows_by_topic(requirements_db_path: Optional[Path]) -> Dict[str, List[Dict[str, Any]]]:
    if not requirements_db_path or not requirements_db_path.exists():
        return {}
    by_topic: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    with sqlite3.connect(requirements_db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = requirement_row_columns(conn)
        if "detail_id" not in columns:
            return {}
        select_columns = [
            optional_requirement_column(columns, "normalized_depth4"),
            optional_requirement_column(columns, "depth4"),
            optional_requirement_column(columns, "normalized_policy_module"),
            optional_requirement_column(columns, "policy_module"),
            "detail_id",
            optional_requirement_column(columns, "detail_name"),
            optional_requirement_column(columns, "detail_description"),
            optional_requirement_column(columns, "parent_name"),
            optional_requirement_column(columns, "parent_description"),
            optional_requirement_column(columns, "requirement_type"),
            optional_requirement_column(columns, "priority"),
            optional_requirement_column(columns, "source"),
            optional_requirement_column(columns, "policy_mapping_status"),
        ]
        order_column = "normalized_depth4" if "normalized_depth4" in columns else "detail_id"
        query = f"""
            select {", ".join(select_columns)}
            from requirement_rows
            where coalesce(trim(detail_id), '') <> ''
            order by {order_column}, detail_id
        """
        for row in conn.execute(query):
            item = {
                "topic": str(row["depth4"] or row["policy_module"] or ""),
                "normalizedTopic": str(row["normalized_depth4"] or row["normalized_policy_module"] or ""),
                "detailId": str(row["detail_id"] or ""),
                "detailName": str(row["detail_name"] or ""),
                "detailDescription": str(row["detail_description"] or ""),
                "parentName": str(row["parent_name"] or ""),
                "parentDescription": str(row["parent_description"] or ""),
                "requirementType": str(row["requirement_type"] or ""),
                "priority": str(row["priority"] or ""),
                "source": str(row["source"] or ""),
                "policyMappingStatus": str(row["policy_mapping_status"] or ""),
            }
            item["policyMappingIds"] = extract_policy_element_ids(str(row["policy_mapping_status"] or ""))
            keys = {
                normalize_key(row["normalized_depth4"]),
                normalize_key(row["depth4"]),
                normalize_key(row["normalized_policy_module"]),
                normalize_key(row["policy_module"]),
            }
            for key in keys:
                if key:
                    by_topic[key].append(item)
    return dict(by_topic)


def requirement_row_columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("pragma table_info(requirement_rows)")}


def optional_requirement_column(columns: set[str], name: str) -> str:
    return name if name in columns else f"'' as {name}"


def extract_policy_element_ids(value: Any) -> List[str]:
    text_parts: List[str] = []
    for item in flatten_trace_values(value):
        text_parts.append(str(item))
    text = " ".join(text_parts)
    if not text.strip():
        return []
    patterns = [
        r"\b(?:US|UC|PR|PC|FN|PG|PI|ST|TM|ACT|P|S)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?:->[A-Za-z0-9-]+)?\b",
        r"\b(?:MOD|INFO|OPS|AUTH|BILL|VOC|IA|DSP|ORD|MEM|FAQ|COM|MYI|LCM|PAY)_[0-9]{2}-[0-9]{3}\b",
        r"\b[0-9]{1,2}[A-Z]{2,5}-H[0-9]{2}-[0-9]{3}\b",
    ]
    ids: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = str(match).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                ids.append(cleaned)
    return ids


def extract_requirement_ids(value: Any) -> List[str]:
    text_parts: List[str] = []
    for item in flatten_trace_values(value):
        text_parts.append(str(item))
    text = " ".join(text_parts)
    if not text.strip():
        return []
    patterns = [
        r"\bREQ-[A-Za-z0-9가-힣_]+(?:[ -][A-Za-z0-9]+){0,4}\b",
        r"\b[A-Za-z]{2,8}\s+[0-9]{2}-[0-9]{3}\b",
        r"\b[A-Z]{2,8}_[0-9]{2}-[0-9]{3}\b",
        r"\bPM-[0-9]{2}-UNMAPPED-[0-9]{3}\b",
        r"\b[0-9]{1,2}[A-Z]{2,5}-H[0-9]{2}-[0-9]{3}\b",
        r"\b(?:MOD|INFO|OPS|AUTH|BILL|VOC|IA|DSP|ORD|MEM|FAQ|COM|MYI|LCM|PAY)_[0-9]{2}-[0-9]{3}\b",
        r"\b[A-Z]{2,8}-H[0-9]{2}-[0-9]{3}\b",
    ]
    ids: List[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            cleaned = str(match).strip()
            if not cleaned or cleaned.startswith(("REFCH-", "SAMPLE-")):
                continue
            if not cleaned.startswith("REQ-") and f"REQ-{cleaned}" in text:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                ids.append(cleaned)
    return ids


def flatten_trace_values(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: List[Any] = []
        for item in value:
            result.extend(flatten_trace_values(item))
        return result
    if isinstance(value, Mapping):
        result = []
        for item in value.values():
            result.extend(flatten_trace_values(item))
        return result
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]
        if parsed is value:
            return [stripped]
        return flatten_trace_values(parsed)
    return [value]


def collect_trace_ids(row: Mapping[str, Any], fields: Sequence[str]) -> List[str]:
    ids: List[str] = []
    seen: set[str] = set()
    for field in fields:
        for item in flatten_trace_values(row.get(field)):
            raw = str(item or "").strip()
            if not raw:
                continue
            extracted = extract_policy_element_ids(raw)
            candidates = extracted if field == "links" else extracted or split_trace_id_text(raw)
            for candidate in candidates:
                cleaned = str(candidate or "").strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    ids.append(cleaned)
    return ids


def collect_requirement_ids(row: Mapping[str, Any], fields: Sequence[str]) -> List[str]:
    ids: List[str] = []
    seen: set[str] = set()
    for field in fields:
        for item in flatten_trace_values(row.get(field)):
            raw = str(item or "").strip()
            if not raw:
                continue
            extracted = extract_requirement_ids(raw)
            candidates = extracted or ([] if field == "evidence_ids" else split_trace_id_text(raw))
            for candidate in candidates:
                cleaned = str(candidate or "").strip()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    ids.append(cleaned)
    return ids


def collect_analysis_evidence_ids(row: Mapping[str, Any], fields: Sequence[str]) -> List[str]:
    ids: List[str] = []
    seen: set[str] = set()
    for field in fields:
        for item in flatten_trace_values(row.get(field)):
            raw = str(item or "").strip()
            if not raw:
                continue
            for candidate in split_trace_id_text(raw):
                cleaned = str(candidate or "").strip()
                if cleaned and normalize_key(cleaned).startswith("ev") and cleaned not in seen:
                    seen.add(cleaned)
                    ids.append(cleaned)
    return ids


def collect_trace_text_values(row: Mapping[str, Any], fields: Sequence[str]) -> List[str]:
    values: List[str] = []
    seen: set[str] = set()
    for field in fields:
        for item in flatten_trace_values(row.get(field)):
            text = str(item or "").strip()
            if text and text not in seen:
                seen.add(text)
                values.append(text)
    return values


def split_trace_id_text(value: str) -> List[str]:
    text = str(value or "").strip()
    if not text or len(text) > 120:
        return []
    if text.isdigit():
        return []
    if re.search(r"[가-힣]", text):
        return []
    return [part.strip() for part in re.split(r"[\s,;|]+", text) if part.strip()]


def requirement_rows_for_policy(
    requirements_by_topic: Mapping[str, List[Dict[str, Any]]],
    spec: Mapping[str, Any],
    record: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    keys = [
        meta.get("topic_display"),
        meta.get("topic"),
        meta.get("topic_slug"),
        record.get("topicSlug"),
    ]
    seen_ids: set[str] = set()
    rows: List[Dict[str, Any]] = []
    for raw_key in keys:
        key = normalize_key(raw_key)
        if not key:
            continue
        for row in requirements_by_topic.get(key, []):
            row_id = str(row.get("detailId") or "")
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            rows.append(row)
    return rows


def evaluate_trace_bridge(
    spec: Mapping[str, Any],
    requirement_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    trace_stats: Mapping[str, Any],
) -> Dict[str, Any]:
    requirement_sample = list(requirement_rows[:MAX_REQUIREMENT_TRACE_ROWS])
    requirement_scores = [analysis_requirement_score(row, evidence_rows) for row in requirement_sample]
    analysis_requirement_rate = score_bucket_average(requirement_scores, covered=0.11, partial=0.055)

    mapped_db_total = len(requirement_rows)
    mapped_db_count = sum(1 for row in requirement_rows if str(row.get("policyMappingStatus") or "").strip())
    db_mapping_rate = round((mapped_db_count / max(1, mapped_db_total)) * 100) if mapped_db_total else 0

    trace_rows = spec.get("trace_matrix", [])
    rows = [row for row in trace_rows if isinstance(row, Mapping)] if isinstance(trace_rows, list) else []
    element_ids = policy_element_id_set(spec)
    evidence_by_id = {normalize_key(row.get("id")): row for row in evidence_rows if str(row.get("id") or "").strip()}
    bridge_items: List[Dict[str, Any]] = []
    weighted_total = 0
    weighted_score = 0.0

    for index, row in enumerate(rows, 1):
        normalized = normalize_trace_row(row)
        count = safe_int(normalized.get("detailRequirementCount"), default=0)
        if count <= 0:
            continue
        text = str(normalized.get("text") or "")
        tokens = tokenize(text)
        inferred_matches = top_evidence_for_tokens(tokens, evidence_rows)
        direct_matches = trace_direct_evidence_matches(normalized, evidence_by_id)
        evidence_matches = merge_evidence_matches(direct_matches, inferred_matches)
        top_score = evidence_matches[0]["score"] if evidence_matches else 0.0
        evidence_rate = score_to_percent(top_score, covered=0.11, partial=0.055)
        if direct_matches:
            evidence_rate = max(evidence_rate, 100)
        mapped_to = [str(item).strip() for item in normalized.get("mappedIds", []) if str(item or "").strip()]
        resolved = [item for item in mapped_to if item in element_ids]
        unresolved = [item for item in mapped_to if item not in element_ids]
        resolve_rate = round((len(resolved) / max(1, len(mapped_to))) * 100) if mapped_to else 0
        row_score = round(evidence_rate * 0.45 + resolve_rate * 0.55)
        source = str(normalized.get("requirementIdSource") or "none")
        if source == "evidence":
            row_score = round(row_score * 0.90)
        elif source in {"group", "text"}:
            row_score = round(row_score * 0.82)
        elif source == "none":
            row_score = round(row_score * 0.70)
        weighted_total += count
        weighted_score += row_score * count
        if row_score < 82 or unresolved:
            bridge_items.append(
                {
                    "index": index,
                    "requirementGroup": str(normalized.get("requirementGroup") or f"Trace {index}"),
                    "detailRequirementCount": count,
                    "analysisEvidenceRate": evidence_rate,
                    "mappedResolveRate": resolve_rate,
                    "score": row_score,
                    "requirementIdSource": source,
                    "unresolvedMappedIds": unresolved[:8],
                    "coverageStatus": normalized.get("coverageStatus"),
                    "matches": evidence_matches[:3],
                }
            )

    trace_continuity_rate = round(weighted_score / max(1, weighted_total)) if rows else 0
    requirement_policy_rate = weighted_average(
        [
            (trace_stats.get("coverageRate"), 0.35),
            (trace_stats.get("mappedIdResolveRate"), 0.35),
            (db_mapping_rate, 0.15 if mapped_db_total else 0.0),
            (trace_stats.get("traceSchemaCompletenessRate"), 0.15),
        ]
    )

    actions: List[Dict[str, Any]] = []
    if analysis_requirement_rate < 70:
        actions.append(
            {
                "priority": "P1",
                "title": "현황 분석→요구사항 근거 연결 보강",
                "target": "요구사항 trace 메타데이터",
                "suggestion": "요구사항별로 어떤 현황 분석 출처와 신호에서 도출됐는지 evidence_id 또는 sourceGroup을 trace에 남기면 진단 정확도가 올라갑니다.",
            }
        )
    if safe_int(trace_stats.get("mappedIdResolveRate")) < 95:
        actions.append(
            {
                "priority": "P1",
                "title": "요구사항→정책서 매핑 ID 정합성 보강",
                "target": "trace_matrix.mapped_to",
                "suggestion": "trace_matrix의 mapped_to 값이 실제 유즈케이스, 프로세스, 기능, 정책 ID와 일치하는지 보강합니다. 본문 수정 없이 trace ID만 정합화합니다.",
            }
        )
    if safe_int(trace_stats.get("traceSchemaCompletenessRate")) < 70:
        actions.append(
            {
                "priority": "P1",
                "title": "상세 요구사항 ID 단위 Trace 구조화",
                "target": "trace_matrix.requirement_id/detail_id",
                "suggestion": "그룹명 또는 evidence_id만으로 추정하지 않도록 최신 requirements.db의 detail_id와 실제 반영 요소 ID를 같은 trace row에 남깁니다.",
            }
        )
    if trace_continuity_rate < 70:
        actions.append(
            {
                "priority": "P2",
                "title": "현황 분석→요구사항→정책서 연결 축 보강",
                "target": "trace_matrix + evidence mapping",
                "suggestion": "요구사항 묶음별 분석 근거와 정책서 반영 ID가 한 줄에서 이어지도록 trace bridge를 보강합니다.",
            }
        )

    return {
        "analysisRequirementCoverageRate": analysis_requirement_rate,
        "requirementPolicyTraceRate": requirement_policy_rate,
        "traceContinuityRate": max(0, min(100, trace_continuity_rate)),
        "dbRequirementMappingRate": db_mapping_rate,
        "items": sorted(bridge_items, key=lambda item: (safe_int(item.get("score")), -safe_int(item.get("detailRequirementCount"))))[:MAX_TRACE_BRIDGE_ITEMS],
        "actions": actions,
    }


def trace_confidence_label(score: int, direct_requirement_rate: int, unique_requirement_rate: int) -> str:
    if direct_requirement_rate >= 85 and score >= 85:
        return "높음"
    if unique_requirement_rate >= 70 and score >= 70:
        return "보통"
    if score >= 60:
        return "추정"
    return "낮음"


def analysis_requirement_score(row: Mapping[str, Any], evidence_rows: Sequence[Mapping[str, Any]]) -> float:
    text = " ".join(
        [
            str(row.get("parentName") or ""),
            str(row.get("parentDescription") or ""),
            str(row.get("detailName") or ""),
            str(row.get("detailDescription") or ""),
            str(row.get("requirementType") or ""),
            str(row.get("source") or ""),
        ]
    )
    tokens = tokenize(text)
    matches = top_evidence_for_tokens(tokens, evidence_rows, limit=1)
    return matches[0]["score"] if matches else 0.0


def top_evidence_for_tokens(tokens: Any, evidence_rows: Sequence[Mapping[str, Any]], *, limit: int = 4) -> List[Dict[str, Any]]:
    if not tokens:
        return []
    matches: List[Dict[str, Any]] = []
    for evidence in evidence_rows:
        evidence_tokens = evidence.get("tokens")
        score = weighted_overlap(tokens, evidence_tokens) if evidence_tokens else 0.0
        if score <= 0:
            continue
        matches.append(
            {
                "id": evidence.get("id") or "",
                "sourceName": evidence.get("sourceName") or "",
                "sourceGroup": evidence.get("sourceGroup") or "현황 분석",
                "summary": evidence.get("summary") or "",
                "score": round(score, 3),
                "sharedTerms": top_shared_terms(tokens, evidence_tokens, limit=5) if evidence_tokens else [],
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:limit]


def trace_direct_evidence_matches(
    normalized_trace_row: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for evidence_id in normalized_trace_row.get("analysisEvidenceIds", []):
        evidence = evidence_by_id.get(normalize_key(evidence_id))
        if not evidence:
            continue
        matches.append(
            {
                "id": evidence.get("id") or "",
                "sourceName": evidence.get("sourceName") or "",
                "sourceGroup": evidence.get("sourceGroup") or "현황 분석",
                "summary": evidence.get("summary") or "",
                "score": 0.12,
                "sharedTerms": ["trace evidence"],
            }
        )
        if len(matches) >= limit:
            break
    return matches


def merge_evidence_matches(
    direct_matches: Sequence[Mapping[str, Any]],
    inferred_matches: Sequence[Mapping[str, Any]],
    *,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*direct_matches, *inferred_matches]:
        evidence_id = str(item.get("id") or "").strip()
        key = normalize_key(evidence_id) or json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
        if len(merged) >= limit:
            break
    return merged


def normalize_trace_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    mapped_ids = collect_trace_ids(row, TRACE_MAPPED_FIELDS)
    if not mapped_ids:
        mapped_ids = collect_trace_ids(row, TRACE_SELF_ELEMENT_FIELDS)
    explicit_requirement_ids = collect_requirement_ids(row, TRACE_REQUIREMENT_ID_FIELDS)
    evidence_requirement_ids = collect_requirement_ids(row, ("evidence_ids",))
    analysis_evidence_ids = collect_analysis_evidence_ids(row, TRACE_ANALYSIS_EVIDENCE_FIELDS)
    analysis_source_groups = collect_trace_text_values(row, TRACE_ANALYSIS_SOURCE_GROUP_FIELDS)
    requirement_ids = explicit_requirement_ids or evidence_requirement_ids
    samples = row.get("sample_detail_requirements", [])
    sample_text = " ".join(str(item) for item in samples if str(item or "").strip()) if isinstance(samples, list) else ""
    detail_count = safe_int(row.get("detail_requirement_count"), default=0)
    if detail_count <= 0 and explicit_requirement_ids:
        detail_count = len(explicit_requirement_ids)
    if detail_count <= 0 and evidence_requirement_ids:
        detail_count = 1
    if detail_count <= 0 and isinstance(samples, list) and samples:
        detail_count = len(samples)
    has_requirement_signal = bool(
        detail_count > 0
        or requirement_ids
        or str(row.get("requirement_name") or row.get("detail_name") or row.get("parent_name") or row.get("requirement_group") or "").strip()
    )
    if explicit_requirement_ids:
        requirement_id_source = "direct"
    elif evidence_requirement_ids:
        requirement_id_source = "evidence"
    elif detail_count > 0 or isinstance(samples, list) and samples:
        requirement_id_source = "group"
    elif str(row.get("requirement_name") or row.get("detail_name") or row.get("parent_name") or row.get("requirement_group") or "").strip():
        requirement_id_source = "text"
    else:
        requirement_id_source = "none"
    if detail_count <= 0 and has_requirement_signal:
        detail_count = 1
    coverage_status, coverage_factor = normalize_coverage_status(row.get("coverage"), mapped_ids)
    text = " ".join(
        str(part or "")
        for part in [
            row.get("requirement_group"),
            row.get("requirement_name"),
            row.get("detail_name"),
            row.get("parent_name"),
            row.get("source"),
            row.get("source_number"),
            row.get("rationale"),
            row.get("note"),
            row.get("summary"),
            " ".join(analysis_source_groups),
            sample_text,
        ]
        if str(part or "").strip()
    )
    return {
        "detailRequirementCount": detail_count,
        "hasRequirementSignal": has_requirement_signal,
        "requirementIds": requirement_ids,
        "directRequirementIds": explicit_requirement_ids,
        "evidenceRequirementIds": evidence_requirement_ids,
        "analysisEvidenceIds": analysis_evidence_ids,
        "analysisSourceGroups": analysis_source_groups,
        "requirementIdSource": requirement_id_source,
        "mappedIds": mapped_ids,
        "coverageStatus": coverage_status,
        "coverageFactor": coverage_factor,
        "requirementGroup": first_non_empty(row.get("requirement_group"), row.get("requirement_name"), row.get("detail_name"), row.get("source_number"), default=""),
        "text": text,
    }


def normalize_coverage_status(value: Any, mapped_ids: Sequence[str]) -> Tuple[str, float]:
    raw = str(value or "").strip()
    folded = raw.casefold()
    if not raw:
        return ("partial", 0.5) if mapped_ids else ("unknown", 0.0)
    if folded in {"y", "yes", "covered", "complete", "done", "true", "반영", "반영완료", "완료"} or "반영 완료" in raw:
        return "covered", 1.0
    if folded in {"n", "no", "missing", "false", "미반영"} or "미반영" in raw:
        return "missing", 0.0
    if folded in {"partial", "weak", "unknown", "review"} or "부분" in raw or "검토" in raw:
        return "partial", 0.5
    return ("partial", 0.5) if mapped_ids else ("unknown", 0.0)


def annotated_policy_elements(spec: Mapping[str, Any], record: Mapping[str, Any]) -> List[Dict[str, Any]]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = str(meta.get("topic_display") or meta.get("topic") or record.get("topicSlug") or "")
    elements: List[Dict[str, Any]] = []
    for element in extract_policy_elements(spec):
        enriched = dict(element)
        enriched.update(
            {
                "topic": topic,
                "topicSlug": str(record.get("topicSlug") or ""),
                "policyFile": str(record.get("policyFile") or ""),
                "version": str(meta.get("version") or record.get("version") or ""),
                "templateLabel": str(record.get("templateLabel") or meta.get("template_label") or ""),
            }
        )
        elements.append(enriched)
    return elements


def build_analysis_item_coverage(
    evidence_rows: Sequence[Mapping[str, Any]],
    policy_elements: Sequence[Mapping[str, Any]],
    requirements_by_topic: Mapping[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    requirement_index = build_requirement_match_index(requirements_by_topic)
    items: List[Dict[str, Any]] = []
    by_source: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "covered": 0, "partial": 0, "missing": 0})

    for evidence in evidence_rows:
        policy_matches = top_global_policy_matches(evidence, policy_elements)
        requirement_matches = top_global_requirement_matches(evidence, requirement_index)
        best_policy_score = float(policy_matches[0]["score"]) if policy_matches else 0.0
        best_requirement_score = float(requirement_matches[0]["score"]) if requirement_matches else 0.0
        requirement_trace_mapped = requirement_match_has_policy_trace(first_mapping(requirement_matches))
        status = analysis_item_status(best_policy_score, best_requirement_score, requirement_trace_mapped)
        source_group = str(evidence.get("sourceGroup") or "현황 분석")
        by_source[source_group]["total"] += 1
        by_source[source_group][status] += 1
        items.append(
            {
                "id": str(evidence.get("id") or ""),
                "sourceGroup": source_group,
                "sourceName": str(evidence.get("sourceName") or ""),
                "summary": str(evidence.get("summary") or ""),
                "signals": evidence.get("signals", []) if isinstance(evidence.get("signals"), list) else [],
                "relatedTopics": evidence.get("relatedTopics", []) if isinstance(evidence.get("relatedTopics"), list) else [],
                "status": status,
                "statusLabel": analysis_item_status_label(status),
                "coverageLabel": analysis_item_coverage_label(status, best_policy_score, best_requirement_score, requirement_trace_mapped),
                "score": analysis_item_score(status, best_policy_score, best_requirement_score, requirement_trace_mapped),
                "requirementTraceMapped": requirement_trace_mapped,
                "policyMatches": policy_matches,
                "requirementMatches": requirement_matches,
                "howHandled": analysis_item_handling_text(status, policy_matches, requirement_matches),
                "recommendation": analysis_item_recommendation(status, evidence, policy_matches, requirement_matches),
            }
        )

    status_order = {"missing": 0, "partial": 1, "covered": 2}
    items.sort(
        key=lambda item: (
            status_order.get(str(item.get("status")), 9),
            safe_int(item.get("score")),
            str(item.get("sourceGroup") or ""),
            str(item.get("summary") or ""),
        )
    )
    covered = sum(1 for item in items if item.get("status") == "covered")
    partial = sum(1 for item in items if item.get("status") == "partial")
    missing = sum(1 for item in items if item.get("status") == "missing")
    total = len(items)
    rate = round(((covered + partial * 0.5) / max(1, total)) * 100)
    source_rows = []
    for source_group, counts in by_source.items():
        source_total = safe_int(counts.get("total"))
        source_rate = round(((safe_int(counts.get("covered")) + safe_int(counts.get("partial")) * 0.5) / max(1, source_total)) * 100)
        source_rows.append(
            {
                "sourceGroup": source_group,
                "total": source_total,
                "covered": safe_int(counts.get("covered")),
                "partial": safe_int(counts.get("partial")),
                "missing": safe_int(counts.get("missing")),
                "coverageRate": source_rate,
            }
        )
    source_rows.sort(key=lambda item: (safe_int(item.get("coverageRate")), -safe_int(item.get("total")), str(item.get("sourceGroup") or "")))
    return {
        "summary": {
            "total": total,
            "covered": covered,
            "partial": partial,
            "missing": missing,
            "coverageRate": rate,
            "sourceCoverage": source_rows,
        },
        "items": items,
    }


def build_requirement_match_index(requirements_by_topic: Mapping[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, str]] = set()
    rows: List[Dict[str, Any]] = []
    for topic_key, topic_rows in requirements_by_topic.items():
        for row in topic_rows:
            detail_id = str(row.get("detailId") or "").strip()
            key = (detail_id, normalize_key(row.get("normalizedTopic") or row.get("topic") or topic_key))
            if not detail_id or key in seen:
                continue
            seen.add(key)
            text = " ".join(
                [
                    str(row.get("parentName") or ""),
                    str(row.get("parentDescription") or ""),
                    str(row.get("detailName") or ""),
                    str(row.get("detailDescription") or ""),
                    str(row.get("requirementType") or ""),
                    str(row.get("source") or ""),
                ]
            )
            tokens = tokenize(text)
            if not tokens:
                continue
            enriched = dict(row)
            enriched["topicKey"] = str(topic_key or "")
            enriched["tokens"] = tokens
            enriched["policyMappingIds"] = row.get("policyMappingIds", []) if isinstance(row.get("policyMappingIds"), list) else []
            rows.append(enriched)
    return rows


def top_global_policy_matches(evidence: Mapping[str, Any], policy_elements: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    evidence_tokens = evidence.get("tokens")
    if not evidence_tokens:
        return []
    related_topics = {normalize_key(topic) for topic in evidence.get("relatedTopics", []) if normalize_key(topic)}
    matches: List[Dict[str, Any]] = []
    for element in policy_elements:
        element_tokens = element.get("tokens")
        if not element_tokens:
            continue
        score = pair_score(evidence_tokens, element_tokens, evidence.get("relatedChapters", []), str(element.get("section") or ""))
        element_topic = normalize_key(element.get("topic") or element.get("topicSlug"))
        if related_topics:
            if element_topic in related_topics:
                score += 0.04
            elif score < 0.20:
                score *= 0.88
        if score <= 0:
            continue
        matches.append(
            {
                "topic": str(element.get("topic") or ""),
                "policyFile": str(element.get("policyFile") or ""),
                "version": str(element.get("version") or ""),
                "section": str(element.get("section") or ""),
                "sectionLabel": str(element.get("sectionLabel") or ""),
                "id": str(element.get("id") or ""),
                "title": str(element.get("title") or ""),
                "score": round(score, 3),
                "sharedTerms": top_shared_terms(evidence_tokens, element_tokens, limit=6),
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:MAX_ANALYSIS_ITEM_MATCHES]


def top_global_requirement_matches(evidence: Mapping[str, Any], requirement_index: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    evidence_tokens = evidence.get("tokens")
    if not evidence_tokens:
        return []
    related_topics = {normalize_key(topic) for topic in evidence.get("relatedTopics", []) if str(topic or "").strip()}
    matches: List[Dict[str, Any]] = []
    for row in requirement_index:
        row_tokens = row.get("tokens")
        if not row_tokens:
            continue
        score = weighted_overlap(evidence_tokens, row_tokens)
        row_topic = normalize_key(row.get("normalizedTopic") or row.get("topic") or row.get("topicKey"))
        if row_topic and row_topic in related_topics:
            score += 0.03
        if score <= 0:
            continue
        matches.append(
            {
                "detailId": str(row.get("detailId") or ""),
                "detailName": str(row.get("detailName") or ""),
                "topic": str(row.get("topic") or row.get("normalizedTopic") or ""),
                "requirementType": str(row.get("requirementType") or ""),
                "policyMappingStatus": str(row.get("policyMappingStatus") or ""),
                "policyMappingIds": row.get("policyMappingIds", []) if isinstance(row.get("policyMappingIds"), list) else [],
                "score": round(min(1.0, score), 3),
                "sharedTerms": top_shared_terms(evidence_tokens, row_tokens, limit=6),
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:MAX_ANALYSIS_ITEM_MATCHES]


def requirement_match_has_policy_trace(match: Mapping[str, Any]) -> bool:
    if not match:
        return False
    mapping_ids = match.get("policyMappingIds")
    if isinstance(mapping_ids, list) and any(str(item or "").strip() for item in mapping_ids):
        return True
    return bool(str(match.get("policyMappingStatus") or "").strip())


def analysis_item_status(policy_score: float, requirement_score: float, requirement_trace_mapped: bool = False) -> str:
    if policy_score >= 0.24:
        return "covered"
    if policy_score >= 0.18 and requirement_score >= 0.13:
        return "covered"
    if requirement_trace_mapped and requirement_score >= 0.13:
        return "covered"
    if policy_score >= 0.12 or requirement_score >= 0.11:
        return "partial"
    return "missing"


def analysis_item_score(status: str, policy_score: float, requirement_score: float, requirement_trace_mapped: bool = False) -> int:
    direct = min(100, round((policy_score / 0.24) * 100)) if policy_score else 0
    bridged = min(100, round(((policy_score / 0.18) * 0.65 + (requirement_score / 0.13) * 0.35) * 100)) if policy_score and requirement_score else 0
    requirement_cap = 88 if requirement_trace_mapped else 62
    requirement_only = min(requirement_cap, round((requirement_score / 0.13) * requirement_cap)) if requirement_score else 0
    raw = max(direct, bridged, requirement_only)
    if status == "covered":
        return max(82, min(100, raw))
    if status == "partial":
        return max(50, min(81, raw))
    return max(0, min(49, raw))


def analysis_item_status_label(status: str) -> str:
    return {"covered": "반영", "partial": "부분 반영", "missing": "미반영"}.get(status, status)


def analysis_item_coverage_label(
    status: str,
    policy_score: float,
    requirement_score: float,
    requirement_trace_mapped: bool = False,
) -> str:
    if status == "covered" and policy_score >= 0.24:
        return "정책서 직접 반영"
    if status == "covered" and requirement_trace_mapped and requirement_score >= 0.13:
        return "요구사항 Trace 경유 반영"
    if status == "covered":
        return "정책서 직접 반영"
    if status == "partial" and policy_score >= 0.12:
        return "정책서 후보 있음"
    if status == "partial" and requirement_score >= 0.11:
        return "요구사항 후보 있음"
    return "보강 필요"


def analysis_item_handling_text(
    status: str,
    policy_matches: Sequence[Mapping[str, Any]],
    requirement_matches: Sequence[Mapping[str, Any]],
) -> str:
    if policy_matches:
        top = policy_matches[0]
        return f"{top.get('topic', '정책서')} 정책서의 {top.get('sectionLabel', '요소')} · {top.get('title', '-')} 항목에서 가장 강하게 다룹니다."
    if requirement_matches:
        top = requirement_matches[0]
        return f"요구사항 {top.get('detailId', '-')} · {top.get('detailName', '-')} 후보는 있으나 정책서 반영 위치가 약합니다."
    if status == "missing":
        return "요구사항과 정책서에서 직접 연결 후보가 약하게 진단되었습니다."
    return "부분 연결 후보가 있으나 반영 위치를 더 명확히 남길 필요가 있습니다."


def analysis_item_recommendation(
    status: str,
    evidence: Mapping[str, Any],
    policy_matches: Sequence[Mapping[str, Any]],
    requirement_matches: Sequence[Mapping[str, Any]],
) -> str:
    if status == "covered":
        if policy_matches:
            top = policy_matches[0]
            return f"현재는 {top.get('topic', '정책서')}의 {top.get('id', '-')} 기준으로 추적할 수 있습니다."
        return "요구사항과 정책서 trace 연결을 유지하면 됩니다."
    signal = first_non_empty(evidence.get("signals"), evidence.get("summary"), default="해당 분석 신호")
    if requirement_matches and not policy_matches:
        return f"{signal}이 요구사항 후보에는 보이지만 정책서 반영 ID가 약합니다. trace_matrix에서 실제 반영된 프로세스·기능·정책 ID를 연결하세요."
    if policy_matches:
        top = policy_matches[0]
        return f"{signal}이 {top.get('topic', '정책서')} 후보와 일부 연결됩니다. 본문 수정이 아니라 evidence_id 또는 trace 근거를 보강해 반영 위치를 확정하세요."
    return f"{signal}을 어떤 요구사항과 정책서 항목에서 다룰지 trace 후보를 추가로 지정해야 합니다."


def build_cross_validation_report(
    analysis_items: Sequence[Mapping[str, Any]],
    topic_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    topic_lookup = {normalize_key(row.get("topic")): row for row in topic_rows if normalize_key(row.get("topic"))}
    findings: List[Dict[str, Any]] = []
    trusted_covered = 0
    topic_mismatch = 0
    low_policy_context = 0
    low_trace_confidence = 0
    weak_direct_match = 0

    for item in analysis_items:
        policy_match = first_mapping(item.get("policyMatches"))
        requirement_match = first_mapping(item.get("requirementMatches"))
        policy_topic_key = normalize_key(policy_match.get("topic"))
        requirement_topic_key = normalize_key(requirement_match.get("topic"))
        related_topic_keys = {normalize_key(topic) for topic in item.get("relatedTopics", []) if normalize_key(topic)}
        policy_score = float(policy_match.get("score") or 0.0)
        requirement_score = float(requirement_match.get("score") or 0.0)
        requirement_mapping_ids = {str(item_id) for item_id in requirement_match.get("policyMappingIds", []) if str(item_id or "").strip()} if isinstance(requirement_match.get("policyMappingIds"), list) else set()
        requirement_trace_mapped = requirement_match_has_policy_trace(requirement_match)
        trace_links_policy = bool(str(policy_match.get("id") or "") in requirement_mapping_ids)
        policy_row = topic_lookup.get(policy_topic_key, {})
        trace_supported = bool(
            requirement_trace_mapped
            or (
                policy_row
                and safe_int(policy_row.get("traceConfidenceScore")) >= 80
                and safe_int(policy_row.get("requirementPolicyTraceRate")) >= 80
                and safe_int(policy_row.get("traceContinuityRate")) >= 70
            )
        )
        topic_aligned = bool(
            policy_topic_key
            and (
                policy_topic_key == requirement_topic_key
                or policy_topic_key in related_topic_keys
                or requirement_topic_key in related_topic_keys
                or trace_links_policy
                or trace_supported
            )
        )
        has_topic_mismatch = bool(
            policy_topic_key
            and requirement_topic_key
            and policy_topic_key != requirement_topic_key
            and not topic_aligned
            and policy_score >= 0.18
            and requirement_score >= 0.13
        )
        policy_context_low = bool(
            policy_row
            and not trace_supported
            and (
                safe_int(policy_row.get("analysisCoverageRate")) < 65
                or safe_int(policy_row.get("policyGroundingRate")) < 65
            )
            and policy_score < 0.18
        )
        trace_confidence_low = bool(policy_row and safe_int(policy_row.get("traceConfidenceScore")) < 65 and not trace_links_policy and not requirement_trace_mapped)
        if has_topic_mismatch:
            topic_mismatch += 1
        if policy_context_low:
            low_policy_context += 1
        if trace_confidence_low:
            low_trace_confidence += 1
        if policy_score < 0.18 and not trace_supported:
            weak_direct_match += 1

        if item.get("status") == "covered" and not has_topic_mismatch and not policy_context_low and not trace_confidence_low:
            trusted_covered += 1
            continue

        finding = cross_validation_finding(
            item,
            policy_match,
            requirement_match,
            policy_row,
            has_topic_mismatch=has_topic_mismatch,
            policy_context_low=policy_context_low,
            trace_confidence_low=trace_confidence_low,
            policy_score=policy_score,
            requirement_score=requirement_score,
        )
        if finding:
            findings.append(finding)

    total = len(analysis_items)
    review_needed = max(0, total - trusted_covered)
    trusted_rate = round((trusted_covered / max(1, total)) * 100)
    findings.sort(key=lambda item: (0 if item.get("priority") == "P1" else 1, safe_int(item.get("score")), str(item.get("sourceGroup") or "")))
    return {
        "title": "현황 분석↔정책서 교차검증",
        "summary": cross_validation_summary_text(total, trusted_covered, review_needed, topic_mismatch, low_policy_context, low_trace_confidence),
        "trustedCovered": trusted_covered,
        "reviewNeeded": review_needed,
        "trustedCoverageRate": trusted_rate,
        "topicMismatchCount": topic_mismatch,
        "lowPolicyContextCount": low_policy_context,
        "lowTraceConfidenceCount": low_trace_confidence,
        "weakDirectMatchCount": weak_direct_match,
        "findingCount": len(findings),
        "findings": findings[:24],
    }


def cross_validation_finding(
    item: Mapping[str, Any],
    policy_match: Mapping[str, Any],
    requirement_match: Mapping[str, Any],
    policy_row: Mapping[str, Any],
    *,
    has_topic_mismatch: bool,
    policy_context_low: bool,
    trace_confidence_low: bool,
    policy_score: float,
    requirement_score: float,
) -> Dict[str, Any]:
    if item.get("status") == "partial":
        finding_type = "weak_match"
        priority = "P1" if policy_score < 0.15 else "P2"
        title = "부분 반영 항목 재확인"
        reason = "분석 항목이 정책서 후보에는 연결되지만 직접 반영 강도가 낮습니다."
        recommendation = "본문을 늘리기보다 해당 분석 근거가 어떤 요구사항과 정책서 ID로 이어지는지 trace를 확정하세요."
    elif has_topic_mismatch:
        finding_type = "topic_mismatch"
        priority = "P1" if policy_score < 0.24 else "P2"
        title = "요구사항 후보와 정책서 후보 주제 불일치"
        reason = "현황 분석에서 잡힌 요구사항 후보 주제와 정책서 반영 후보 주제가 다릅니다."
        recommendation = "상위 요구사항 후보가 맞는지, 아니면 정책서 매칭이 공통 용어 때문에 과대 연결된 것인지 확인하세요."
    elif policy_context_low:
        finding_type = "low_policy_context"
        priority = "P2"
        title = "정책서 기준 역방향 근거 약함"
        reason = "분석 항목은 해당 정책서에 붙었지만, 그 정책서 자체의 분석 반영률 또는 정책 근거율이 낮습니다."
        recommendation = "정책서 시작 관점에서도 같은 분석 근거가 핵심 정책 요소를 충분히 설명하는지 확인하세요."
    elif trace_confidence_low:
        finding_type = "low_trace_confidence"
        priority = "P2"
        title = "Trace 신뢰도 낮음"
        reason = "분석 항목과 정책서 후보는 연결되지만, 상세 요구사항 ID 단위 trace가 약해 반영 완료로 보기 어렵습니다."
        recommendation = "정책서 본문은 유지하고 trace_matrix에 detail_id와 실제 반영 요소 ID를 함께 남겨 양방향 추적 신뢰도를 높이세요."
    elif policy_score < 0.18:
        finding_type = "weak_direct_match"
        priority = "P2"
        title = "직접 매칭 점수 낮음"
        reason = "분석 항목과 정책서 후보의 직접 유사도가 낮아 보조 후보로만 보는 것이 안전합니다."
        recommendation = "이 항목은 반영 완료보다 검토 후보로 관리하세요."
    else:
        return {}

    return {
        "type": finding_type,
        "priority": priority,
        "title": title,
        "sourceGroup": str(item.get("sourceGroup") or ""),
        "sourceName": str(item.get("sourceName") or ""),
        "summary": str(item.get("summary") or ""),
        "analysisStatus": str(item.get("statusLabel") or item.get("status") or ""),
        "score": safe_int(item.get("score")),
        "policyTopic": str(policy_match.get("topic") or ""),
        "policyElement": " · ".join(
            part
            for part in [
                str(policy_match.get("sectionLabel") or ""),
                str(policy_match.get("id") or ""),
                str(policy_match.get("title") or ""),
            ]
            if part
        ),
        "policyScore": round(policy_score, 3),
        "policyAnalysisCoverageRate": safe_int(policy_row.get("analysisCoverageRate")) if policy_row else 0,
        "policyGroundingRate": safe_int(policy_row.get("policyGroundingRate")) if policy_row else 0,
        "policyTraceConfidenceScore": safe_int(policy_row.get("traceConfidenceScore")) if policy_row else 0,
        "policyTraceConfidenceLabel": str(policy_row.get("traceConfidenceLabel") or "") if policy_row else "",
        "requirementTopic": str(requirement_match.get("topic") or ""),
        "requirementElement": " · ".join(
            part
            for part in [
                str(requirement_match.get("detailId") or ""),
                str(requirement_match.get("detailName") or ""),
            ]
            if part
        ),
        "requirementScore": round(requirement_score, 3),
        "reason": reason,
        "recommendation": recommendation,
    }


def first_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        return value[0]
    return {}


def cross_validation_summary_text(
    total: int,
    trusted_covered: int,
    review_needed: int,
    topic_mismatch: int,
    low_policy_context: int,
    low_trace_confidence: int,
) -> str:
    if not total:
        return "교차검증할 현황 분석 항목이 없습니다."
    return (
        f"현황 분석 항목 {total}건 중 {trusted_covered}건은 양방향 기준으로도 비교적 안정적입니다. "
        f"{review_needed}건은 정책서 시작 관점에서 재확인이 필요하며, "
        f"그중 요구사항 후보와 정책서 후보 주제가 다른 항목은 {topic_mismatch}건, "
        f"매칭된 정책서 자체의 분석 근거율이 낮은 항목은 {low_policy_context}건, "
        f"상세 요구사항 ID trace 신뢰도가 낮은 항목은 {low_trace_confidence}건입니다."
    )


def score_to_percent(score: float, *, covered: float, partial: float) -> int:
    if score >= covered:
        return 100
    if score >= partial:
        return 50
    return 0


def score_bucket_average(scores: Sequence[float], *, covered: float, partial: float) -> int:
    if not scores:
        return 0
    values = [score_to_percent(score, covered=covered, partial=partial) for score in scores]
    return round(sum(values) / len(values))


def build_stage_flow(
    output_root: Path,
    evidence_summary: Mapping[str, Any],
    requirements_summary: Mapping[str, Any],
    topic_rows: List[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    task_count = len(list((output_root / "reference_html").glob("tk-task-*.html")))
    return [
        {
            "id": "analysis",
            "index": "01",
            "title": "현황 분석",
            "metric": f"{safe_int(evidence_summary.get('analysisEvidenceCount'))}건",
            "description": "벤치마킹, 고객 조사, 임직원 인터뷰, IA, VoC 분석을 정책 판단의 근거로 정리합니다.",
        },
        {
            "id": "task-definition",
            "index": "02",
            "title": "과제 정의",
            "metric": f"{task_count}개",
            "description": "분석 내용을 통합채널 관점의 전략 과제와 실행 방향으로 압축합니다.",
        },
        {
            "id": "requirements",
            "index": "03",
            "title": "요구사항",
            "metric": f"{safe_int(requirements_summary.get('detailCount'))}건",
            "description": "과제 방향을 상세 요구사항과 trace 기준으로 구조화합니다.",
        },
        {
            "id": "policy",
            "index": "04",
            "title": "정책서",
            "metric": f"{len(topic_rows)}개",
            "description": "요구사항과 분석 근거가 정책서의 유즈케이스, 프로세스, 기능, 정책에 반영되는지 점검합니다.",
        },
    ]


def build_channel_dimensions(
    topic_rows: List[Mapping[str, Any]],
    evidence_summary: Mapping[str, Any],
    analysis_item_summary: Optional[Mapping[str, Any]] = None,
    cross_validation: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    avg_analysis_requirement = average(row.get("analysisRequirementCoverageRate") for row in topic_rows)
    avg_requirement_policy = average(row.get("requirementPolicyTraceRate") for row in topic_rows)
    avg_trace_continuity = average(row.get("traceContinuityRate") for row in topic_rows)
    avg_trace = average(row.get("traceCoverageRate") for row in topic_rows)
    avg_trace_schema = average(row.get("traceSchemaCompletenessRate") for row in topic_rows)
    avg_trace_confidence = average(row.get("traceConfidenceScore") for row in topic_rows)
    trace_quality = round(avg_trace * 0.45 + avg_trace_schema * 0.30 + avg_trace_confidence * 0.25)
    item_coverage = safe_int((analysis_item_summary or {}).get("coverageRate"))
    trusted_coverage = safe_int((cross_validation or {}).get("trustedCoverageRate"))
    return [
        {
            "id": "analysis-requirement",
            "title": "현황 분석→요구사항 반영도",
            "score": avg_analysis_requirement,
            "weight": 0.18,
            "status": dimension_status(avg_analysis_requirement),
            "description": "현황 분석의 핵심 신호가 요구사항명과 요구사항 설명에 근거로 이어지는지 점검합니다.",
        },
        {
            "id": "requirement-policy",
            "title": "요구사항→정책서 Trace 정합성",
            "score": avg_requirement_policy,
            "weight": 0.18,
            "status": dimension_status(avg_requirement_policy),
            "description": "요구사항 trace가 실제 정책서의 유즈케이스, 프로세스, 기능, 정책 ID로 해소되는지 확인합니다.",
        },
        {
            "id": "bridge-continuity",
            "title": "현황 분석→요구사항→정책서 연결성",
            "score": avg_trace_continuity,
            "weight": 0.14,
            "status": dimension_status(avg_trace_continuity),
            "description": "요구사항 묶음이 분석 근거와 정책서 반영 ID를 한 흐름으로 연결하는지 보는 trace bridge 지표입니다.",
        },
        {
            "id": "analysis-item-coverage",
            "title": "현황 분석 항목별 정책 커버리지",
            "score": item_coverage,
            "weight": 0.08,
            "status": dimension_status(item_coverage),
            "description": "현황 분석 근거 1건마다 요구사항 후보와 정책서 반영 위치가 남아 있는지 점검합니다.",
        },
        {
            "id": "cross-validation",
            "title": "양방향 교차검증 안정성",
            "score": trusted_coverage,
            "weight": 0.02,
            "status": dimension_status(trusted_coverage),
            "description": "현황 분석 시작 관점과 정책서 시작 관점이 같은 반영 판단으로 수렴하는지 확인합니다.",
        },
        {
            "id": "requirement-trace",
            "title": "요구사항 Trace 밀도",
            "score": trace_quality,
            "weight": 0.04,
            "status": dimension_status(trace_quality),
            "description": "최신 요구사항이 trace_matrix에 상세 요구사항 ID와 반영 요소 ID로 구조화되어 남아 있는 정도입니다.",
        },
    ]


def evidence_readiness_score(evidence_summary: Mapping[str, Any]) -> int:
    analysis_docs = safe_int(evidence_summary.get("analysisDocumentCount"))
    analysis_items = safe_int(evidence_summary.get("analysisEvidenceCount"))
    source_groups = len(evidence_summary.get("sourceGroups", [])) if isinstance(evidence_summary.get("sourceGroups"), list) else 0
    score = round(min(1.0, analysis_items / 200) * 50 + min(1.0, analysis_docs / 25) * 35 + min(1.0, source_groups / 5) * 15)
    return max(0, min(100, score))


def aggregate_source_coverage(source_totals: Mapping[str, Mapping[str, int]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source_group, totals in source_totals.items():
        if source_group in EXCLUDED_SOURCE_COVERAGE_GROUPS:
            continue
        total = safe_int(totals.get("total"))
        covered = safe_int(totals.get("covered"))
        partial = safe_int(totals.get("partial"))
        missing = safe_int(totals.get("missing"))
        rate = round(((covered + partial * 0.5) / max(1, total)) * 100)
        rows.append(
            {
                "sourceGroup": source_group,
                "total": total,
                "covered": covered,
                "partial": partial,
                "missing": missing,
                "coverageRate": rate,
                "status": dimension_status(rate),
            }
        )
    return sorted(rows, key=lambda row: (safe_int(row["coverageRate"]), str(row["sourceGroup"])))


def build_priority_actions(topic_rows: List[Mapping[str, Any]], errors: Iterable[Mapping[str, str]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for error in errors:
        actions.append(
            {
                "priority": "P1",
                "topic": str(error.get("policyFile") or "정책서"),
                "title": "정렬 에이전트 실행 실패",
                "target": str(error.get("policyFile") or ""),
                "suggestion": str(error.get("error") or "해당 정책서 spec과 분석 근거 DB를 확인해야 합니다."),
            }
        )
    for row in topic_rows:
        if (
            safe_int(row.get("score")) >= 82
            and safe_int(row.get("traceCoverageRate")) >= 95
            and safe_int(row.get("traceContinuityRate")) >= 82
            and safe_int(row.get("requirementPolicyTraceRate")) >= 82
        ):
            continue
        priority = "P1" if min(safe_int(row.get("score")), safe_int(row.get("traceContinuityRate"))) < 65 else "P2"
        suggestion = str(row.get("traceAction") or row.get("topAction") or "")
        if not suggestion:
            suggestion = "본문은 유지하고 trace_matrix, evidence_id, mapped_to 정합성을 보강해 분석 근거와 요구사항, 정책서 반영 ID를 더 명확히 연결합니다."
        actions.append(
            {
                "priority": priority,
                "topic": str(row.get("topic") or ""),
                "title": "Trace 기반 정렬 진단 보강",
                "target": f"{row.get('topic', '')} · {row.get('policyFile', '')}",
                "suggestion": suggestion,
                "score": min(safe_int(row.get("score")), safe_int(row.get("traceContinuityRate"), default=100)),
            }
        )
    return sorted(actions, key=lambda item: (0 if item.get("priority") == "P1" else 1, safe_int(item.get("score"), default=100)))[:18]


def build_channel_summary(score: int, topic_rows: List[Mapping[str, Any]], dimensions: List[Mapping[str, Any]]) -> str:
    risk_count = sum(1 for row in topic_rows if safe_int(row.get("score")) < 65)
    warn_count = sum(1 for row in topic_rows if 65 <= safe_int(row.get("score")) < 82)
    weakest = min(dimensions, key=lambda item: safe_int(item.get("score"))) if dimensions else {}
    if risk_count:
        return f"{len(topic_rows)}개 정책서 중 {risk_count}개가 중점 보강 대상입니다. 가장 약한 축은 {weakest.get('title', '정렬')}입니다."
    if warn_count:
        return f"{len(topic_rows)}개 정책서 중 {warn_count}개는 분석 근거 또는 trace 보강이 필요합니다. {weakest.get('title', '정렬')} 축을 우선 확인하세요."
    return f"{len(topic_rows)}개 정책서가 전반적으로 분석 근거와 안정적으로 정렬되어 있습니다."


def save_channel_pi_status_report(report: Mapping[str, Any], *, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    target = reports_dir / CHANNEL_PI_STATUS_FILE
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_channel_pi_status_report(*, reports_dir: Path) -> Optional[Dict[str, Any]]:
    target = reports_dir / CHANNEL_PI_STATUS_FILE
    if not target.exists():
        return None
    data = json.loads(target.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def weighted_average(pairs: Iterable[Tuple[Any, float]]) -> int:
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        numeric = safe_int(value)
        w = float(weight or 0)
        numerator += numeric * w
        denominator += w
    return round(numerator / denominator) if denominator else 0


def average(values: Iterable[Any]) -> int:
    numeric = [safe_int(value) for value in values]
    return round(sum(numeric) / len(numeric)) if numeric else 0


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def channel_pi_judgement(score: int) -> str:
    if score >= 82:
        return "양호"
    if score >= 65:
        return "보강 필요"
    return "중점 보강"


def topic_status(score: int) -> str:
    if score >= 82:
        return "정렬 양호"
    if score >= 65:
        return "보강 필요"
    return "중점 보강"


def dimension_status(score: int) -> str:
    if score >= 82:
        return "success"
    if score >= 65:
        return "warn"
    return "danger"


def first_action_text(actions: Any) -> str:
    if not isinstance(actions, list) or not actions:
        return ""
    action = actions[0]
    if not isinstance(action, Mapping):
        return ""
    return str(action.get("suggestion") or action.get("title") or "")
