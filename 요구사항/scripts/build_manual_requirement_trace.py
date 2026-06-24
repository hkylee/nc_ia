#!/usr/bin/env python3
"""Build a lightweight requirement trace report for manual authoring outputs.

The report is intentionally separate from the policy HTML so the document does
not become a requirements dump, while reviewers can still verify that detailed
requirement names/descriptions were considered.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.policy_requirements import RequirementItem, load_scoped_requirements_for_topic


STOPWORDS = {
    "고객",
    "서비스",
    "정책",
    "기준",
    "관리",
    "처리",
    "확인",
    "제공",
    "조회",
    "정보",
    "업무",
    "기능",
    "화면",
    "채널",
    "상세",
    "목록",
    "운영",
    "설정",
    "사용",
    "지원",
    "연계",
    "결과",
    "데이터",
}


@dataclass(frozen=True)
class TraceElement:
    element_type: str
    identifier: str
    name: str
    text: str


@dataclass(frozen=True)
class TraceMatch:
    element: TraceElement
    score: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Build manual authoring requirement trace report.")
    parser.add_argument("--topic", required=True, help="Policy topic label used by the requirements workbook.")
    parser.add_argument("--spec", required=True, type=Path, help="Policy spec JSON path.")
    parser.add_argument("--output", required=True, type=Path, help="Markdown trace report path.")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    requirements = load_scoped_requirements_for_topic(args.topic)
    elements = build_trace_elements(spec)
    markdown = render_trace_report(args.topic, requirements, elements, args.spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.output} ({len(requirements)} requirements, {len(elements)} trace elements)")
    return 0


def build_trace_elements(spec: dict) -> list[TraceElement]:
    elements: list[TraceElement] = []
    sections = [
        ("usecase", spec.get("usecases", [])),
        ("state", spec.get("state_codes", [])),
        ("state", spec.get("states", [])),
        ("transition", spec.get("state_transitions", [])),
        ("process", spec.get("processes", [])),
        ("function", spec.get("functions", [])),
        ("policy", spec.get("policy_groups", [])),
        ("policy_item", spec.get("policy_details", [])),
        ("trace", spec.get("trace_matrix", [])),
    ]
    for element_type, items in sections:
        for item in items or []:
            if not isinstance(item, dict):
                continue
            identifier = first_value(item, "id", "requirement_id", "item_id", "policy_id", "state_id", "transition_id", "source")
            name = first_value(item, "name", "detail_name", "item_name", "title", "event", "source")
            if not identifier and not name:
                continue
            text = " ".join(flatten_text(item))
            elements.append(
                TraceElement(
                    element_type=element_type,
                    identifier=identifier or name,
                    name=name or identifier,
                    text=text,
                )
            )
    return elements


def render_trace_report(
    topic: str,
    requirements: Sequence[RequirementItem],
    elements: Sequence[TraceElement],
    spec_path: Path,
) -> str:
    rows: list[str] = []
    mapped = 0
    review = 0
    for requirement in requirements:
        matches = match_requirement(requirement, elements)
        if matches:
            mapped += 1
            confidence = confidence_label(matches[0].score)
            match_text = "<br/>".join(
                f"{match.element.element_type}:{match.element.identifier} {match.element.name}".strip()
                for match in matches[:5]
            )
        else:
            review += 1
            confidence = "검토필요"
            match_text = "자동 매칭 없음"
        rows.append(
            "| "
            + " | ".join(
                [
                    md_escape(requirement.source_number),
                    md_escape(requirement.depth4),
                    md_escape(requirement.detail_name),
                    md_escape(summary(requirement.detail_description)),
                    md_escape(confidence),
                    md_escape(match_text),
                ]
            )
            + " |"
        )

    header = [
        f"# {topic} 상세 요구사항 Trace Report",
        "",
        "정책서 본문에는 요구사항 원문을 과도하게 싣지 않고, 본 리포트에서 상세 요구사항명/상세 요구사항 설명 기준의 1차 추적성을 확인한다.",
        "",
        f"- Spec: `{spec_path}`",
        f"- 상세 요구사항 수: {len(requirements)}",
        f"- 자동 매칭: {mapped}",
        f"- 수동 검토 필요: {review}",
        "",
        "> 자동 매칭은 상세 요구사항명/설명과 산출물의 유즈케이스, 상태, 프로세스, 기능, 정책, 정책 항목 텍스트를 비교한 1차 점검이다. 최종 커버리지 판정은 작성자 검토로 확정한다.",
        "",
        "| 번호 | Depth4 | 상세 요구사항명 | 상세 요구사항 설명 요약 | 매칭 신뢰도 | 관련 산출물 후보 |",
        "|---|---|---|---|---|---|",
    ]
    return "\n".join(header + rows) + "\n"


def match_requirement(requirement: RequirementItem, elements: Sequence[TraceElement]) -> list[TraceMatch]:
    query = f"{requirement.detail_name} {requirement.detail_description}"
    tokens = important_tokens(query)
    exact_name = normalize(requirement.detail_name)
    matches: list[TraceMatch] = []
    for element in elements:
        element_name = normalize(element.name)
        element_text = normalize(element.text)
        score = 0
        if exact_name and exact_name in element_text:
            score += 8
        for token in tokens:
            if token in element_name:
                score += 3
            elif token in element_text:
                score += 3 if element.element_type == "trace" else 1
        threshold = 3 if element.element_type == "trace" else max(3, min(6, len(tokens)))
        if score >= threshold:
            matches.append(TraceMatch(element, score))
    return sorted(matches, key=lambda item: (-item.score, item.element.element_type, item.element.identifier))[:5]


def important_tokens(text: str) -> list[str]:
    tokens = []
    seen: set[str] = set()
    for token in re.findall(r"[가-힣A-Za-z0-9]+", normalize(text)):
        if len(token) < 2 or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens[:12]


def confidence_label(score: int) -> str:
    if score >= 10:
        return "높음"
    if score >= 6:
        return "중간"
    return "낮음"


def first_value(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def flatten_text(value: object) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        parts: list[str] = []
        for child in value.values():
            parts.extend(flatten_text(child))
        return parts
    if isinstance(value, list):
        parts = []
        for child in value:
            parts.extend(flatten_text(child))
        return parts
    return [str(value)]


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def summary(text: str, limit: int = 90) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"


def md_escape(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br/>").strip()


if __name__ == "__main__":
    raise SystemExit(main())
