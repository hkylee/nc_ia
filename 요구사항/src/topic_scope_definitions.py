"""Topic scope and direction summaries for policy authoring UI.

The summaries are derived from Topic Knowledge Packs so the UI follows the
same requirement/PDF priority rules as Blueprint and Context Pack generation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from runtime_paths import TOPIC_KNOWLEDGE_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .runtime_paths import TOPIC_KNOWLEDGE_ROOT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOPIC_KNOWLEDGE_DIR = TOPIC_KNOWLEDGE_ROOT


def build_topic_scope_definitions(
    topic_knowledge_dir: Path = TOPIC_KNOWLEDGE_DIR,
    *,
    output_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Build UI-ready scope definitions from generated Topic Knowledge Packs."""

    definitions: dict[str, dict[str, Any]] = {}
    if not topic_knowledge_dir.exists():
        return definitions

    policy_specs = _load_latest_policy_specs(output_dir) if output_dir else {}

    for path in sorted(topic_knowledge_dir.glob("*.json")):
        if path.name in {"manifest.json", "validation_report.json"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        topic = str(data.get("topic") or "").strip()
        contract = data.get("topic_contract") if isinstance(data.get("topic_contract"), Mapping) else {}
        if not topic or not contract:
            continue

        definition = _definition_from_contract(topic, contract, data, policy_specs.get(_normalize_topic(topic)))
        definitions[topic] = definition

    return definitions


def topic_scope_definition(
    topic: str,
    topic_knowledge_dir: Path = TOPIC_KNOWLEDGE_DIR,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any] | None:
    definitions = build_topic_scope_definitions(topic_knowledge_dir, output_dir=output_dir)
    normalized = _normalize_topic(topic)
    for key, value in definitions.items():
        if _normalize_topic(key) == normalized:
            return value
    return None


def _definition_from_contract(
    topic: str,
    contract: Mapping[str, Any],
    data: Mapping[str, Any],
    policy_spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope_items = _compact_list(contract.get("direct_scope"), limit=10, skip_values={topic})
    must_cover = _compact_list(
        [_strip_prefix(item, "상세 요구사항명 기준:") for item in _as_list(contract.get("must_cover"))],
        limit=10,
    )
    must_not = _compact_list(contract.get("must_not_cover"), limit=5)
    focus_points = _compact_list(contract.get("focus_points"), limit=5)
    policy_questions = _compact_list(contract.get("core_policy_questions"), limit=8)
    writing_goals = _compact_list(contract.get("writing_goal"), limit=4)
    direction_milestone = _compact_list(data.get("topic_direction_milestone"), limit=8)
    display_milestone, agent_milestone = _split_direction_milestone(direction_milestone)
    agent_milestone = _merge_direction_lines(display_milestone, agent_milestone, limit=8)
    core_orientations = _core_orientations_from_pack(data)
    source_rule = data.get("source_authority_rule") if isinstance(data.get("source_authority_rule"), Mapping) else {}
    source_priority = _compact_list(source_rule.get("priority"), limit=4)

    definition: dict[str, Any] = {
        "topic": topic,
        "definition": str(contract.get("topic_definition") or "").strip(),
        "direction": writing_goals,
        "topicDirectionMilestone": direction_milestone,
        "topicDirectionDisplay": display_milestone,
        "topicDirectionAgent": agent_milestone,
        "coreOrientations": core_orientations,
        "scope": scope_items,
        "mustCover": must_cover,
        "mustNotCover": must_not,
        "focusPoints": focus_points,
        "policyQuestions": policy_questions,
        "boundaryRule": str(contract.get("boundary_rule") or "").strip(),
        "requirementBasis": str(contract.get("requirement_basis") or "").strip(),
        "sourcePriority": source_priority,
    }
    definition["brief"] = format_scope_brief(definition)
    definition["conceptCard"] = _build_concept_card(definition, policy_spec)
    return definition


def format_scope_brief(definition: Mapping[str, Any]) -> str:
    """Format a scope definition for the authoring request memo textarea."""

    lines = ["[작성 지향점]"]
    direction_milestone = _as_list(definition.get("topicDirectionDisplay")) or _display_direction_milestone(
        _as_list(definition.get("topicDirectionMilestone"))
    )
    for item in direction_milestone[:3]:
        lines.append(f"- {item}")
    if not direction_milestone:
        direction = _as_list(definition.get("direction"))
        for item in direction[:3]:
            lines.append(f"- {item}")
    if len(lines) == 1:
        lines.append(f"- {definition.get('definition') or '선택한 주제의 요구사항과 TK 지향점을 기준으로 작성한다.'}")
    return "\n".join(lines)


def _display_direction_milestone(lines: list[str]) -> list[str]:
    """Return service-facing direction text without internal agent guardrails.

    The source milestone may include additional authoring instructions for
    agents, such as QA conversion or policy-item coverage checks. Those are
    valuable context for generation, but they make the UI feel noisy. For the
    service, expose only purpose-oriented strategic milestones.
    """

    return _split_direction_milestone(lines)[0]


def _split_direction_milestone(lines: list[str]) -> tuple[list[str], list[str]]:
    display: list[str] = []
    agent: list[str] = []
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        if _is_agent_direction_line(text):
            agent.append(text)
        else:
            display.append(text)
    if not display and lines:
        display = [str(lines[0]).strip()]
        agent = [line for line in agent if _normalize_topic(line) != _normalize_topic(display[0])]
    return display[:3], agent[:5]


def _merge_direction_lines(*groups: list[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw in group:
            text = str(raw or "").strip()
            normalized = _normalize_topic(text)
            if not text or normalized in seen:
                continue
            seen.add(normalized)
            result.append(text)
            if len(result) >= limit:
                return result
    return result


def _is_agent_direction_line(value: object) -> bool:
    text = str(value or "")
    markers = (
        "개발/QA",
        "테스트 케이스",
        "Agent",
        "agent",
        "Context",
        "context",
        "컨텍스트",
        "내부 지침",
        "검수 기준",
    )
    return any(marker in text for marker in markers)


def _compact_list(value: Any, *, limit: int, skip_values: set[str] | None = None) -> list[str]:
    skip = {_normalize_topic(item) for item in (skip_values or set())}
    result: list[str] = []
    for raw in _as_list(value):
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = _normalize_topic(text)
        if normalized in skip or normalized in {_normalize_topic(item) for item in result}:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _core_orientations_from_pack(data: Mapping[str, Any], limit: int = 5, max_per_source: int = 2) -> list[str]:
    rows = data.get("tk_core_orientations", [])
    if not isinstance(rows, list):
        return []
    ranked_rows = sorted(
        (row for row in rows if isinstance(row, Mapping)),
        key=lambda row: int(row.get("topic_relevance", 0) or 0),
        reverse=True,
    )
    result: list[str] = []
    source_counts: dict[str, int] = {}
    for row in ranked_rows:
        if not isinstance(row, Mapping):
            continue
        source = str(row.get("source_name") or "").strip()
        for point in _as_list(row.get("core_points", [])):
            if source and source_counts.get(source, 0) >= max_per_source:
                continue
            normalized = _normalize_topic(point)
            if not normalized or normalized in {_normalize_topic(item) for item in result}:
                continue
            result.append(point)
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
            if len(result) >= limit:
                return result
    return result


def _as_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _strip_prefix(value: object, prefix: str) -> str:
    text = str(value or "").strip()
    return text.removeprefix(prefix).strip()


def _normalize_topic(value: object) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _build_concept_card(definition: Mapping[str, Any], policy_spec: Mapping[str, Any] | None) -> dict[str, Any]:
    display_lines = _as_list(definition.get("topicDirectionDisplay")) or _as_list(definition.get("direction"))
    goal = display_lines[0] if display_lines else str(definition.get("definition") or "").strip()

    usecases = _spec_items(policy_spec, "usecases", limit=4)
    processes = _spec_items(policy_spec, "processes", limit=4)
    functions = _spec_items(policy_spec, "functions", limit=4)
    policies = _spec_items(policy_spec, "policy_groups", limit=4) or _spec_items(policy_spec, "policies", limit=4)

    if not usecases:
        usecases = _fallback_items(_as_list(definition.get("mustCover")) or _as_list(definition.get("scope")), limit=4)
    if not processes:
        processes = _fallback_items(_as_list(definition.get("scope")) or _as_list(definition.get("focusPoints")), limit=4)
    if not functions:
        functions = _fallback_items(_as_list(definition.get("policyQuestions")) or _as_list(definition.get("focusPoints")), limit=4)
    if not policies:
        policies = _fallback_items(_as_list(definition.get("focusPoints")) or _as_list(definition.get("mustCover")), limit=4)

    return {
        "title": "주제 체계도",
        "goal": goal or "선택한 주제의 고객 과업, 업무 흐름, 기능, 정책 기준을 한눈에 정리합니다.",
        "columns": [
            {"id": "usecases", "label": "고객 과업", "items": usecases},
            {"id": "processes", "label": "업무 흐름", "items": processes},
            {"id": "functions", "label": "처리 역량", "items": functions},
            {"id": "policies", "label": "정책 기준", "items": policies},
        ],
    }


def _spec_items(policy_spec: Mapping[str, Any] | None, key: str, *, limit: int) -> list[dict[str, str]]:
    if not isinstance(policy_spec, Mapping):
        return []
    rows = policy_spec.get(key)
    if not isinstance(rows, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or row.get("title") or "").strip()
        identifier = str(row.get("id") or row.get("policy_id") or "").strip()
        description = str(row.get("description") or "").strip()
        if not name and not identifier:
            continue
        normalized = _normalize_topic(f"{identifier} {name}")
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append({"id": identifier, "name": name or identifier, "description": description})
        if len(result) >= limit:
            break
    return result


def _fallback_items(values: list[str], *, limit: int) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        normalized = _normalize_topic(text)
        if not text or normalized in seen:
            continue
        seen.add(normalized)
        result.append({"id": "", "name": text, "description": ""})
        if len(result) >= limit:
            break
    return result


def _load_latest_policy_specs(output_dir: Path | None) -> dict[str, Mapping[str, Any]]:
    if not output_dir or not output_dir.exists():
        return {}
    latest: dict[str, tuple[tuple[int, int], float, Mapping[str, Any]]] = {}
    for path in sorted(output_dir.glob("*.json")):
        if not (path.name.endswith("_policy_spec.json") or path.name.endswith("_spec.json")):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, Mapping):
            continue
        topic = _policy_spec_topic(data, path)
        normalized_topic = _normalize_topic(topic)
        if not normalized_topic:
            continue
        version = _policy_spec_version(data, path)
        try:
            modified_at = path.stat().st_mtime
        except OSError:
            modified_at = 0.0
        current = latest.get(normalized_topic)
        if current is None or (version, modified_at) > (current[0], current[1]):
            latest[normalized_topic] = (version, modified_at, data)
    return {topic: data for topic, (_version, _modified_at, data) in latest.items()}


def _policy_spec_topic(data: Mapping[str, Any], path: Path) -> str:
    meta = data.get("meta") if isinstance(data.get("meta"), Mapping) else {}
    for key in ("topic_display", "topic", "topic_slug"):
        value = str(meta.get(key) or data.get(key) or "").strip()
        if value:
            return value
    if path.name.endswith("_policy_spec.json"):
        return path.name.removesuffix("_policy_spec.json")
    match = re.match(r"NC_(.+?)_정책서_", path.name)
    if match:
        return match.group(1)
    return path.stem


def _policy_spec_version(data: Mapping[str, Any], path: Path) -> tuple[int, int]:
    meta = data.get("meta") if isinstance(data.get("meta"), Mapping) else {}
    raw = str(meta.get("version") or data.get("version") or path.name)
    match = re.search(r"v?(\d+)\.(\d+)", raw)
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))
