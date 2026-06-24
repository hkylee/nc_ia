#!/usr/bin/env python3
"""Evaluate whether analysis evidence and policy specs are mutually aligned."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ALIGNMENT_VERSION = "1.0"
MAX_RELEVANT_EVIDENCE = 48
MAX_POLICY_ELEMENTS = 220
MAX_DISPLAY_ITEMS = 18

STOPWORDS = {
    "한다",
    "해야",
    "있다",
    "있는",
    "없다",
    "없는",
    "기준",
    "정책",
    "정책서",
    "고객",
    "시스템",
    "통합",
    "통합채널",
    "처리",
    "확인",
    "관리",
    "제공",
    "수행",
    "관련",
    "상태",
    "업무",
    "기능",
    "흐름",
    "단계",
    "결과",
    "정보",
    "구성",
    "대상",
    "경우",
    "필요",
    "반영",
}

LENS_KEYWORDS = {
    "고객 문제·VoC": {"불편", "문의", "상담", "고객", "민원", "실패", "혼란", "pain", "voc", "해결"},
    "IA·탐색 구조": {"ia", "탐색", "메뉴", "검색", "노출", "전시", "구조", "경로", "진입", "화면"},
    "벤치마킹·전략": {"벤치마킹", "전략", "비교", "시장", "사례", "플랫폼", "미션", "혜택", "agent"},
    "운영·인터뷰": {"운영", "인터뷰", "담당", "조직", "검수", "승인", "관리자", "업무"},
    "데이터·시스템": {"데이터", "bss", "연계", "자동", "학습", "이력", "트래킹", "인증", "결제"},
}


def build_analysis_policy_alignment_report(
    *,
    spec: Mapping[str, Any],
    policy_file_name: str,
    evidence_db_path: Path,
) -> Dict[str, Any]:
    """Build a deterministic analysis-policy alignment report."""

    evidence_rows = load_analysis_evidence(evidence_db_path)
    policy_elements = extract_policy_elements(spec)
    topic = policy_topic(spec, policy_file_name)

    if not evidence_rows:
        raise ValueError("분석 근거 DB에서 현황 분석 근거를 찾지 못했습니다.")
    if not policy_elements:
        raise ValueError("정책서 spec에서 점검할 정책 요소를 찾지 못했습니다.")

    corpus_tokens = Counter()
    for element in policy_elements:
        corpus_tokens.update(element["tokens"])
    relevant_evidence = select_relevant_evidence(evidence_rows, corpus_tokens, topic)

    analysis_to_policy = evaluate_analysis_to_policy(relevant_evidence, policy_elements)
    policy_to_analysis = evaluate_policy_to_analysis(policy_elements, relevant_evidence)
    source_coverage = build_source_coverage(analysis_to_policy)

    analysis_total = len(analysis_to_policy)
    analysis_covered = sum(1 for item in analysis_to_policy if item["status"] == "covered")
    analysis_partial = sum(1 for item in analysis_to_policy if item["status"] == "partial")
    analysis_missing = sum(1 for item in analysis_to_policy if item["status"] == "missing")

    policy_total = len(policy_to_analysis)
    policy_grounded = sum(1 for item in policy_to_analysis if item["status"] == "grounded")
    policy_weak = sum(1 for item in policy_to_analysis if item["status"] == "weak")
    policy_unsupported = sum(1 for item in policy_to_analysis if item["status"] == "unsupported")

    analysis_rate = round(((analysis_covered + analysis_partial * 0.5) / max(1, analysis_total)) * 100)
    policy_rate = round(((policy_grounded + policy_weak * 0.5) / max(1, policy_total)) * 100)
    score = round(analysis_rate * 0.55 + policy_rate * 0.45)
    judgement = alignment_judgement(score, analysis_missing, policy_unsupported)

    display_analysis = sorted(
        analysis_to_policy,
        key=lambda item: ({"missing": 0, "partial": 1, "covered": 2}.get(item["status"], 9), -item["relevanceScore"]),
    )[:MAX_DISPLAY_ITEMS]
    display_policy = sorted(
        policy_to_analysis,
        key=lambda item: ({"unsupported": 0, "weak": 1, "grounded": 2}.get(item["status"], 9), item["score"]),
    )[:MAX_DISPLAY_ITEMS]

    return {
        "agent": "분석-정책 정렬 Check",
        "version": ALIGNMENT_VERSION,
        "policyFile": policy_file_name,
        "topic": topic,
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "score": score,
        "judgement": judgement,
        "summary": build_summary(score, analysis_rate, policy_rate, analysis_missing, policy_unsupported),
        "analysisCoverageRate": analysis_rate,
        "policyGroundingRate": policy_rate,
        "analysisEvidenceCount": analysis_total,
        "policyElementCount": policy_total,
        "stats": {
            "analysisCovered": analysis_covered,
            "analysisPartial": analysis_partial,
            "analysisMissing": analysis_missing,
            "policyGrounded": policy_grounded,
            "policyWeak": policy_weak,
            "policyUnsupported": policy_unsupported,
            "sourceCount": len(source_coverage),
        },
        "sourceCoverage": source_coverage,
        "analysisToPolicy": display_analysis,
        "policyToAnalysis": display_policy,
        "actionItems": build_action_items(display_analysis, display_policy),
        "method": {
            "type": "deterministic",
            "description": "현황 분석 근거 DB와 정책서 spec의 토큰·신호·장 연결을 비교해 양방향 추적성을 점검합니다.",
            "thresholds": {
                "analysisCovered": 0.18,
                "analysisPartial": 0.09,
                "policyGrounded": 0.16,
                "policyWeak": 0.08,
            },
        },
    }


def load_analysis_evidence(evidence_db_path: Path) -> List[Dict[str, Any]]:
    if not evidence_db_path.exists():
        raise ValueError(f"분석 근거 DB를 찾을 수 없습니다: {evidence_db_path}")

    query = """
        select
            e.evidence_id,
            e.evidence_type,
            e.summary,
            e.signals,
            e.related_topics,
            e.related_chapters,
            e.confidence,
            e.evidence_text,
            d.document_id,
            d.source_name,
            d.category
        from evidence_items e
        join documents d on d.document_id = e.document_id
        where d.category = 'analysis_synthesis'
        order by d.source_name, e.evidence_id
    """
    rows: List[Dict[str, Any]] = []
    with sqlite3.connect(evidence_db_path) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute(query):
            signals = parse_json_list(row["signals"])
            topics = parse_json_list(row["related_topics"])
            chapters = parse_json_list(row["related_chapters"])
            text = " ".join(
                [
                    str(row["summary"] or ""),
                    " ".join(signals),
                    " ".join(topics),
                    str(row["evidence_text"] or ""),
                ]
            )
            rows.append(
                {
                    "id": str(row["evidence_id"] or ""),
                    "documentId": str(row["document_id"] or ""),
                    "sourceName": str(row["source_name"] or ""),
                    "sourceGroup": source_group(str(row["source_name"] or "")),
                    "evidenceType": str(row["evidence_type"] or ""),
                    "summary": compact_text(row["summary"] or row["evidence_text"] or "", 220),
                    "signals": signals[:6],
                    "relatedTopics": topics[:8],
                    "relatedChapters": chapters[:8],
                    "confidence": optional_float(row["confidence"], 0.7),
                    "text": text,
                    "tokens": tokenize(text),
                    "lenses": detect_lenses(text),
                }
            )
    return rows


def extract_policy_elements(spec: Mapping[str, Any]) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = str(meta.get("topic_display") or meta.get("topic") or "").strip()

    overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
    for index, text in enumerate(as_text_list(overview.get("scope")), 1):
        add_policy_element(elements, "overview", "OVERVIEW", f"범위 {index}", text, topic=topic)
    for index, principle in enumerate(as_mapping_list(overview.get("principles")), 1):
        add_policy_element(
            elements,
            "overview",
            f"PRINCIPLE-{index:02d}",
            str(principle.get("name") or f"설계 원칙 {index}"),
            f"{principle.get('name', '')} {principle.get('description', '')}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("usecases")):
        add_policy_element(
            elements,
            "usecases",
            str(row.get("id") or ""),
            str(row.get("name") or "유즈케이스"),
            f"{row.get('actor', '')} {row.get('name', '')} {row.get('description', '')}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("states")):
        add_policy_element(
            elements,
            "state",
            str(row.get("id") or ""),
            str(row.get("name") or "상태"),
            f"{row.get('name', '')} {row.get('description', '')} {row.get('next_action', '')}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("state_transitions")):
        add_policy_element(
            elements,
            "state",
            f"{row.get('current_state', '')}->{row.get('next_state', '')}",
            str(row.get("event") or "상태 전이"),
            f"{row.get('current_state', '')} {row.get('event', '')} {row.get('next_state', '')} {row.get('criteria', '')}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("processes")):
        add_policy_element(
            elements,
            "process",
            str(row.get("id") or ""),
            str(row.get("name") or "프로세스"),
            f"{row.get('name', '')} {row.get('description', '')}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("functions")):
        add_policy_element(
            elements,
            "functions",
            str(row.get("id") or ""),
            str(row.get("name") or "기능"),
            f"{row.get('name', '')} {row.get('description', '')} {' '.join(as_text_list(row.get('details')))}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("policy_groups")):
        add_policy_element(
            elements,
            "policies",
            str(row.get("id") or ""),
            str(row.get("name") or "정책 그룹"),
            f"{row.get('name', '')} {row.get('description', '')} {' '.join(item_name for item_name in policy_item_names(row.get('items')))}",
            topic=topic,
        )

    for row in as_mapping_list(spec.get("policy_details")):
        add_policy_element(
            elements,
            "policies",
            str(row.get("id") or ""),
            str(row.get("name") or "정책 항목"),
            f"{row.get('name', '')} {row.get('content', '')}",
            topic=topic,
        )

    deduped: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for element in elements:
        key = (element["section"], element["id"], element["title"])
        if key in seen or not element["tokens"]:
            continue
        seen.add(key)
        deduped.append(element)
        if len(deduped) >= MAX_POLICY_ELEMENTS:
            break
    return deduped


def add_policy_element(
    elements: List[Dict[str, Any]],
    section: str,
    element_id: str,
    title: str,
    text: str,
    *,
    topic: str,
) -> None:
    clean_text = compact_text(text, 520)
    tokens = tokenize(f"{title} {clean_text}")
    if not clean_text or len(tokens) < 2:
        return
    elements.append(
        {
            "section": section,
            "sectionLabel": section_label(section),
            "id": element_id or "-",
            "title": title or section_label(section),
            "text": clean_text,
            "tokens": tokens,
            "lenses": detect_lenses(clean_text),
        }
    )


def select_relevant_evidence(
    evidence_rows: Sequence[Dict[str, Any]],
    policy_tokens: Counter,
    topic: str,
) -> List[Dict[str, Any]]:
    topic_tokens = tokenize(topic)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    generic_sources = {"벤치마킹", "고객 조사", "임직원 인터뷰", "IA 분석", "VoC 분석 종합"}

    for evidence in evidence_rows:
        score = weighted_overlap(evidence["tokens"], policy_tokens)
        if topic_tokens:
            score += overlap_ratio(evidence["tokens"], topic_tokens) * 0.18
        if evidence["sourceGroup"] in generic_sources:
            score += 0.04
        if evidence.get("relatedChapters"):
            score += 0.02
        scored.append((round(score, 5), evidence))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected: List[Dict[str, Any]] = []
    source_quota: Dict[str, int] = defaultdict(int)
    for score, evidence in scored:
        if len(selected) >= MAX_RELEVANT_EVIDENCE:
            break
        if score < 0.025 and len(selected) >= 16:
            continue
        group = evidence["sourceGroup"]
        if source_quota[group] >= 8 and group not in generic_sources:
            continue
        selected.append({**evidence, "relevanceScore": round(score, 3)})
        source_quota[group] += 1

    if len(selected) < 12:
        existing_ids = {item["id"] for item in selected}
        for score, evidence in scored:
            if evidence["id"] in existing_ids:
                continue
            selected.append({**evidence, "relevanceScore": round(score, 3)})
            if len(selected) >= 12:
                break
    return selected


def evaluate_analysis_to_policy(
    evidence_rows: Sequence[Dict[str, Any]],
    policy_elements: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for evidence in evidence_rows:
        matches = top_policy_matches(evidence, policy_elements)
        top_score = matches[0]["score"] if matches else 0.0
        status = "covered" if top_score >= 0.18 else "partial" if top_score >= 0.09 else "missing"
        result.append(
            {
                "id": evidence["id"],
                "sourceName": evidence["sourceName"],
                "sourceGroup": evidence["sourceGroup"],
                "summary": evidence["summary"],
                "signals": evidence["signals"],
                "lenses": evidence["lenses"],
                "relatedChapters": evidence["relatedChapters"],
                "status": status,
                "statusLabel": analysis_status_label(status),
                "score": round(top_score, 3),
                "relevanceScore": evidence.get("relevanceScore", 0),
                "matches": matches[:4],
                "rationale": analysis_rationale(status, matches),
            }
        )
    return result


def evaluate_policy_to_analysis(
    policy_elements: Sequence[Dict[str, Any]],
    evidence_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for element in policy_elements:
        matches = top_evidence_matches(element, evidence_rows)
        top_score = matches[0]["score"] if matches else 0.0
        status = "grounded" if top_score >= 0.16 else "weak" if top_score >= 0.08 else "unsupported"
        result.append(
            {
                "id": element["id"],
                "section": element["section"],
                "sectionLabel": element["sectionLabel"],
                "title": element["title"],
                "text": element["text"],
                "lenses": element["lenses"],
                "status": status,
                "statusLabel": policy_status_label(status),
                "score": round(top_score, 3),
                "matches": matches[:4],
                "rationale": policy_rationale(status, matches),
            }
        )
    return result


def top_policy_matches(evidence: Mapping[str, Any], policy_elements: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for element in policy_elements:
        score = pair_score(evidence["tokens"], element["tokens"], evidence.get("relatedChapters", []), element["section"])
        if score <= 0:
            continue
        shared = top_shared_terms(evidence["tokens"], element["tokens"])
        matches.append(
            {
                "id": element["id"],
                "section": element["section"],
                "sectionLabel": element["sectionLabel"],
                "title": element["title"],
                "score": round(score, 3),
                "sharedTerms": shared,
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:6]


def top_evidence_matches(element: Mapping[str, Any], evidence_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for evidence in evidence_rows:
        score = pair_score(evidence["tokens"], element["tokens"], evidence.get("relatedChapters", []), str(element.get("section", "")))
        if score <= 0:
            continue
        matches.append(
            {
                "id": evidence["id"],
                "sourceName": evidence["sourceName"],
                "sourceGroup": evidence["sourceGroup"],
                "summary": evidence["summary"],
                "score": round(score, 3),
                "sharedTerms": top_shared_terms(evidence["tokens"], element["tokens"]),
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:6]


def pair_score(
    evidence_tokens: Counter,
    element_tokens: Counter,
    related_chapters: Sequence[str],
    section: str,
) -> float:
    base = weighted_overlap(evidence_tokens, element_tokens)
    if not base:
        return 0.0
    chapter_boost = 0.0
    normalized_chapters = {normalize_key(chapter) for chapter in related_chapters}
    if normalize_key(section) in normalized_chapters:
        chapter_boost += 0.04
    elif section == "policies" and "policy" in normalized_chapters:
        chapter_boost += 0.04
    return min(1.0, base + chapter_boost)


def weighted_overlap(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    if not shared:
        return 0.0
    weighted = sum(min(left[token], right[token]) for token in shared)
    denominator = math.sqrt(sum(left.values()) * sum(right.values()))
    return weighted / denominator if denominator else 0.0


def overlap_ratio(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    return len(shared) / max(1, len(set(right)))


def top_shared_terms(left: Counter, right: Counter, *, limit: int = 8) -> List[str]:
    shared = set(left) & set(right)
    ranked = sorted(shared, key=lambda token: (min(left[token], right[token]), left[token] + right[token], len(token)), reverse=True)
    return ranked[:limit]


def build_source_coverage(items: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_source: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        by_source[str(item.get("sourceGroup") or "기타")].append(item)
    rows: List[Dict[str, Any]] = []
    for source, source_items in by_source.items():
        total = len(source_items)
        covered = sum(1 for item in source_items if item.get("status") == "covered")
        partial = sum(1 for item in source_items if item.get("status") == "partial")
        missing = sum(1 for item in source_items if item.get("status") == "missing")
        rows.append(
            {
                "sourceGroup": source,
                "total": total,
                "covered": covered,
                "partial": partial,
                "missing": missing,
                "coverageRate": round(((covered + partial * 0.5) / max(1, total)) * 100),
            }
        )
    rows.sort(key=lambda item: (item["coverageRate"], -item["total"]))
    return rows


def build_action_items(
    analysis_items: Sequence[Mapping[str, Any]],
    policy_items: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for item in analysis_items:
        if item.get("status") not in {"missing", "partial"}:
            continue
        signal = first_non_empty(item.get("signals"), item.get("summary"), default="분석 근거")
        actions.append(
            {
                "priority": "P1" if item.get("status") == "missing" else "P2",
                "type": "analysis_to_policy",
                "title": f"{item.get('sourceGroup', '분석')} 근거 반영 보강",
                "target": "개요, 프로세스, 기능, 정책 항목",
                "suggestion": f"{signal} 관점이 현재 정책서에서 어떤 유즈케이스·기능·정책 기준으로 반영되는지 명시하거나 trace 근거를 보강합니다.",
            }
        )
    for item in policy_items:
        if item.get("status") != "unsupported":
            continue
        actions.append(
            {
                "priority": "P2",
                "type": "policy_to_analysis",
                "title": f"{item.get('sectionLabel', '정책 요소')} 근거 연결 확인",
                "target": f"{item.get('id', '-')} · {item.get('title', '-')}",
                "suggestion": "정책 판단이 현황 분석 근거에서 나온 것인지 확인하고, 근거가 있다면 trace를 보강합니다. 근거가 없으면 정책 기준을 재검토합니다.",
            }
        )
    return actions[:16]


def build_summary(score: int, analysis_rate: int, policy_rate: int, missing: int, unsupported: int) -> str:
    if score >= 82 and missing == 0 and unsupported <= 3:
        return f"분석 근거 반영률 {analysis_rate}%, 정책 근거 연결률 {policy_rate}%로 양방향 정렬 상태가 안정적입니다."
    if score >= 65:
        return f"분석 근거 반영률 {analysis_rate}%, 정책 근거 연결률 {policy_rate}%입니다. 일부 근거와 정책 항목의 trace 보강이 필요합니다."
    return f"분석 근거 반영률 {analysis_rate}%, 정책 근거 연결률 {policy_rate}%로 주요 분석 근거 또는 정책 판단 근거의 연결 보강이 필요합니다."


def alignment_judgement(score: int, missing: int, unsupported: int) -> str:
    if score >= 82 and missing == 0 and unsupported <= 3:
        return "정렬 양호"
    if score >= 65:
        return "부분 보강 필요"
    return "중점 보강 필요"


def analysis_rationale(status: str, matches: Sequence[Mapping[str, Any]]) -> str:
    if not matches:
        return "정책서 요소와 직접 연결되는 핵심 용어가 충분히 발견되지 않았습니다."
    top = matches[0]
    if status == "covered":
        return f"{top.get('sectionLabel', '정책 요소')}의 {top.get('title', '-')} 항목과 핵심 신호가 연결됩니다."
    if status == "partial":
        return f"{top.get('sectionLabel', '정책 요소')}와 일부 용어가 겹치지만 판단 기준 또는 trace를 더 명확히 남길 필요가 있습니다."
    return "관련 후보는 있으나 반영 근거가 약합니다."


def policy_rationale(status: str, matches: Sequence[Mapping[str, Any]]) -> str:
    if not matches:
        return "정책 판단을 뒷받침하는 현황 분석 근거가 약하게 감지되었습니다."
    top = matches[0]
    if status == "grounded":
        return f"{top.get('sourceGroup', '분석 근거')}의 {top.get('sourceName', '-')} 근거와 연결됩니다."
    if status == "weak":
        return f"{top.get('sourceGroup', '분석 근거')} 근거와 일부 연결되지만 정책 판단 근거로는 trace 보강이 필요합니다."
    return "분석 근거와의 연결이 충분하지 않습니다."


def analysis_status_label(status: str) -> str:
    return {"covered": "반영", "partial": "부분 반영", "missing": "보강 필요"}.get(status, status)


def policy_status_label(status: str) -> str:
    return {"grounded": "근거 있음", "weak": "근거 약함", "unsupported": "근거 확인 필요"}.get(status, status)


def source_group(source_name: str) -> str:
    name = source_name.casefold()
    if name == "voc-summary.html":
        return "VoC 분석 종합"
    if name.startswith("voc-"):
        return "VoC 분석"
    if "benchmark" in name or "벤치" in source_name:
        return "벤치마킹"
    if "customer" in name or "고객" in source_name:
        return "고객 조사"
    if "employee" in name or "interview" in name or "인터뷰" in source_name:
        return "임직원 인터뷰"
    if "ia-" in name or "ia_" in name or "ia" == name.removesuffix(".html"):
        return "IA 분석"
    return "현황 분석"


def detect_lenses(text: str) -> List[str]:
    normalized = normalize_text(text)
    lenses: List[str] = []
    for lens, keywords in LENS_KEYWORDS.items():
        if any(normalize_text(keyword) in normalized for keyword in keywords):
            lenses.append(lens)
    return lenses[:3] or ["통합채널 설계"]


def policy_topic(spec: Mapping[str, Any], policy_file_name: str) -> str:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic = str(meta.get("topic_display") or meta.get("topic") or "").strip()
    if topic:
        return topic
    match = re.search(r"NC_(.+?)_정책서_", policy_file_name)
    return match.group(1) if match else policy_file_name


def parse_json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value).strip()] if str(value).strip() else []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [str(parsed).strip()] if str(parsed).strip() else []


def as_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def as_mapping_list(value: Any) -> List[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def policy_item_names(value: Any) -> List[str]:
    result: List[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            result.append(str(item.get("name") or item.get("id") or "").strip())
        else:
            result.append(str(item).strip())
    return [item for item in result if item]


def tokenize(value: str) -> Counter:
    normalized = normalize_text(value)
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", normalized)
    filtered = [token for token in tokens if token not in STOPWORDS and not token.isdigit()]
    return Counter(filtered)


def normalize_text(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\s·/_,:;()\[\]{}<>|+=\"'`~!?#$%^&*-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", str(value or "").casefold())


def compact_text(value: Any, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def optional_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def section_label(section: str) -> str:
    return {
        "overview": "개요",
        "usecases": "유즈케이스",
        "state": "상태",
        "process": "프로세스",
        "functions": "기능",
        "policies": "정책",
    }.get(section, section)


def first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                if str(item).strip():
                    return str(item).strip()
        elif str(value or "").strip():
            return str(value).strip()
    return default
