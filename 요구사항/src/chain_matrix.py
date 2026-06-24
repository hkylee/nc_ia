"""Deterministic chain matrix for NC policy specs.

This module intentionally has no LLM dependency. It builds the structural
links that can be checked by code so inspectors can focus on semantic quality.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping, Sequence


ID_PREFIXES = ("ACT", "US", "ST", "PR", "FN", "PG", "PI")


def build_chain_matrix(spec: Mapping[str, object]) -> dict:
    """Analyze actor -> usecase -> process -> function -> policy links."""
    actors = rows(spec, "actors")
    usecases = rows(spec, "usecases")
    states = rows(spec, "states")
    transitions = rows(spec, "state_transitions")
    processes = rows(spec, "processes")
    functions = rows(spec, "functions")
    policy_groups = rows(spec, "policy_groups")
    policy_details = rows(spec, "policy_details")

    actors_by_id = index_by_id(actors)
    actors_by_name = {clean(row.get("name")): row for row in actors if clean(row.get("name"))}
    usecases_by_id = index_by_id(usecases)
    states_by_id = index_by_id(states)
    states_by_name = {clean(row.get("name")): row for row in states if clean(row.get("name"))}
    processes_by_id = index_by_id(processes)
    functions_by_id = index_by_id(functions)
    policies_by_id = index_by_id(policy_groups)

    functions_by_process: dict[str, list[dict]] = {}
    for function in functions:
        for process_id in function_process_ids(function):
            functions_by_process.setdefault(process_id, []).append(function)

    processes_by_usecase: dict[str, list[dict]] = {}
    for process in processes:
        usecase_id = first_value(process, "usecase_id", "usecaseId")
        if usecase_id:
            processes_by_usecase.setdefault(usecase_id, []).append(process)

    detail_count_by_policy: dict[str, int] = {}
    for detail in policy_details:
        policy_id = first_value(detail, "policy_id", "policyId", "policy_group_id", "policyGroupId")
        if policy_id:
            detail_count_by_policy[policy_id] = detail_count_by_policy.get(policy_id, 0) + 1

    rows_out: list[dict] = []
    missing_links: list[dict] = []

    for usecase in usecases:
        usecase_id = row_id(usecase)
        actor_ref = first_value(usecase, "actor_id", "primary_actor_id", "primaryActorId")
        actor_name = first_value(usecase, "actor", "primary_actor", "primaryActor")
        actor = actors_by_id.get(actor_ref) or actors_by_name.get(actor_name)
        if (actor_ref or actor_name) and not actor:
            missing_links.append(
                issue(
                    "usecase_unknown_actor",
                    usecase_id,
                    f"유즈케이스 액터 '{actor_ref or actor_name}'가 actors에 존재하지 않음",
                )
            )

        linked_processes = processes_by_usecase.get(usecase_id, [])
        if process_target(usecase) and not linked_processes:
            missing_links.append(issue("usecase_without_process", usecase_id, "process_target=Y이나 연결 프로세스가 없음"))

        if not linked_processes:
            rows_out.append(
                {
                    "actor_id": row_id(actor) if actor else actor_ref,
                    "actor_name": clean(actor.get("name")) if actor else actor_name,
                    "usecase_id": usecase_id,
                    "usecase_name": clean(usecase.get("name")),
                    "process_id": "",
                    "process_name": "",
                    "function_ids": [],
                    "policy_group_ids": [],
                    "state_ids": [],
                }
            )
            continue

        for process in linked_processes:
            rows_out.append(chain_row(actor, usecase, process, functions_by_process, states_by_id, states_by_name))

    for process in processes:
        process_id = row_id(process)
        usecase_id = first_value(process, "usecase_id", "usecaseId")
        if usecase_id and usecase_id not in usecases_by_id:
            missing_links.append(issue("process_unknown_usecase", process_id, f"usecase_id '{usecase_id}'가 usecases에 없음"))

        function_ids = process_function_ids(process, functions_by_process.get(process_id, []))
        policy_ids = process_policy_ids(process)
        if not function_ids:
            missing_links.append(issue("process_without_function", process_id, "프로세스에 연결된 기능 ID가 없음"))
        if not policy_ids:
            missing_links.append(issue("process_without_policy_group", process_id, "프로세스에 연결된 정책 그룹 ID가 없음"))
        for function_id in function_ids:
            if function_id not in functions_by_id:
                missing_links.append(
                    issue("process_unknown_function_ref", process_id, f"related_functions의 '{function_id}'가 functions에 없음")
                )
        for policy_id in policy_ids:
            if policy_id not in policies_by_id:
                missing_links.append(
                    issue("process_unknown_policy_group_ref", process_id, f"related_policies의 '{policy_id}'가 policy_groups에 없음")
                )

    for function in functions:
        linked_process_ids = function_process_ids(function)
        if not linked_process_ids:
            missing_links.append(issue("function_without_process", row_id(function), "기능에 연결된 process_id/process_ids가 없음"))
        for process_id in linked_process_ids:
            if process_id and process_id not in processes_by_id:
                missing_links.append(
                    issue("function_unknown_process", row_id(function), f"process_id '{process_id}'가 processes에 없음")
                )

    for detail in policy_details:
        policy_id = first_value(detail, "policy_id", "policyId", "policy_group_id", "policyGroupId")
        if policy_id and policy_id not in policies_by_id:
            missing_links.append(
                issue("policy_detail_unknown_group", row_id(detail), f"policy_id '{policy_id}'가 policy_groups에 없음")
            )

    for group in policy_groups:
        policy_id = row_id(group)
        if policy_id and detail_count_by_policy.get(policy_id, 0) == 0:
            missing_links.append(issue("policy_group_without_detail", policy_id, "정책 그룹에 정책 상세 항목이 없음"))

    transition_state_refs = set()
    for transition in transitions:
        current = first_value(transition, "current_state_id", "from_state_id", "fromStateId")
        next_state = first_value(transition, "next_state_id", "to_state_id", "toStateId")
        current_name = first_value(transition, "current_state", "from_state", "fromState")
        next_name = first_value(transition, "next_state", "to_state", "toState")
        current_id = current or row_id(states_by_name.get(current_name))
        next_id = next_state or row_id(states_by_name.get(next_name))
        if current_id:
            transition_state_refs.add(current_id)
        if next_id:
            transition_state_refs.add(next_id)
        if (current or current_name) and not current_id:
            missing_links.append(issue("state_transition_unknown_from", row_id(transition), f"현재 상태 '{current or current_name}'가 states에 없음"))
        if (next_state or next_name) and not next_id:
            missing_links.append(issue("state_transition_unknown_to", row_id(transition), f"다음 상태 '{next_state or next_name}'가 states에 없음"))

    actor_ids_used = {clean(row.get("actor_id")) for row in rows_out if clean(row.get("actor_id"))}
    process_function_refs = {
        function_id
        for process in processes
        for function_id in process_function_ids(process, functions_by_process.get(row_id(process), []))
    }
    process_policy_refs = {policy_id for process in processes for policy_id in process_policy_ids(process)}
    orphan_ids = {
        "actors": sorted([actor_id for actor_id in actors_by_id if actor_id not in actor_ids_used]),
        "states": sorted([state_id for state_id in states_by_id if state_id not in transition_state_refs]),
        "functions": sorted([function_id for function_id in functions_by_id if function_id not in process_function_refs]),
        "policy_groups": sorted([policy_id for policy_id in policies_by_id if policy_id not in process_policy_refs]),
    }

    return {
        "rows": rows_out,
        "missing_links": dedupe_issues(missing_links),
        "orphan_ids": orphan_ids,
        "stats": {
            "actor_count": len(actors),
            "usecase_count": len(usecases),
            "state_count": len(states),
            "state_transition_count": len(transitions),
            "process_count": len(processes),
            "function_count": len(functions),
            "policy_group_count": len(policy_groups),
            "policy_detail_count": len(policy_details),
            "missing_link_count": len(dedupe_issues(missing_links)),
            "matrix_row_count": len(rows_out),
        },
    }


def summarize_chain_matrix_for_stage(matrix: Mapping[str, object], stage_key: str, row_limit: int = 120) -> dict:
    """Return a compact stage-focused view for prompts/cache keys."""
    stage = normalize_stage_key(stage_key)
    rows_in = matrix.get("rows", []) if isinstance(matrix.get("rows"), list) else []
    missing_in = matrix.get("missing_links", []) if isinstance(matrix.get("missing_links"), list) else []
    relevant_types = relevant_missing_types(stage)
    missing = [
        dict(item)
        for item in missing_in
        if isinstance(item, Mapping) and (not relevant_types or str(item.get("type", "")) in relevant_types)
    ]
    return {
        "stage": stage,
        "stats": matrix.get("stats", {}) if isinstance(matrix.get("stats"), Mapping) else {},
        "rows": compact_rows(rows_in, stage)[:row_limit],
        "missing_links": missing[:80],
        "missing_link_total_count": len(missing),
        "orphan_ids": relevant_orphans(matrix.get("orphan_ids", {}), stage),
    }


def chain_matrix_fingerprint(spec: Mapping[str, object], stage_key: str = "") -> str:
    matrix = build_chain_matrix(spec)
    payload = summarize_chain_matrix_for_stage(matrix, stage_key) if stage_key else matrix
    return stable_hash(payload)


def stable_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rows(spec: Mapping[str, object], key: str) -> list[dict]:
    value = spec.get(key, [])
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def index_by_id(items: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    return {row_id(item): item for item in items if row_id(item)}


def chain_row(
    actor: Mapping[str, object] | None,
    usecase: Mapping[str, object],
    process: Mapping[str, object],
    functions_by_process: Mapping[str, Sequence[Mapping[str, object]]],
    states_by_id: Mapping[str, Mapping[str, object]],
    states_by_name: Mapping[str, Mapping[str, object]],
) -> dict:
    process_id = row_id(process)
    return {
        "actor_id": row_id(actor) if actor else "",
        "actor_name": clean(actor.get("name")) if actor else "",
        "usecase_id": row_id(usecase),
        "usecase_name": clean(usecase.get("name")),
        "process_id": process_id,
        "process_name": clean(process.get("name")),
        "function_ids": process_function_ids(process, functions_by_process.get(process_id, []))[:12],
        "policy_group_ids": process_policy_ids(process)[:12],
        "state_ids": process_state_ids(process, states_by_id, states_by_name)[:12],
    }


def process_function_ids(process: Mapping[str, object], linked_functions: Sequence[Mapping[str, object]]) -> list[str]:
    ids = [row_id(function) for function in linked_functions if row_id(function)]
    ids.extend(reference_ids(process.get("related_functions"), "FN"))
    ids.extend(reference_ids(process.get("related_function_ids"), "FN"))
    ids.extend(reference_ids(process.get("function_ids"), "FN"))
    return unique(ids)


def function_process_ids(function: Mapping[str, object]) -> list[str]:
    ids = []
    process_id = first_value(function, "process_id", "processId")
    if process_id:
        ids.append(process_id)
    raw = function.get("process_ids")
    if isinstance(raw, list):
        ids.extend(clean(item) for item in raw if clean(item))
    return unique(ids)


def process_policy_ids(process: Mapping[str, object]) -> list[str]:
    ids = reference_ids(process.get("related_policies"), "PG")
    ids.extend(reference_ids(process.get("related_policy_ids"), "PG"))
    ids.extend(reference_ids(process.get("policy_group_ids"), "PG"))
    return unique(ids)


def process_state_ids(
    process: Mapping[str, object],
    states_by_id: Mapping[str, Mapping[str, object]],
    states_by_name: Mapping[str, Mapping[str, object]],
) -> list[str]:
    ids = reference_ids(process.get("state_ids"), "ST")
    for key in ("start_state", "end_state", "from_state", "to_state"):
        value = first_value(process, key)
        if value in states_by_id:
            ids.append(value)
        elif value in states_by_name:
            ids.append(row_id(states_by_name[value]))
    return unique(ids)


def reference_ids(value: object, prefix: str) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = clean(item)
        if not text:
            continue
        matches = re.findall(rf"(?<![A-Z0-9])({re.escape(prefix)}-[A-Z0-9]+(?:-[A-Z0-9]+)+)(?![A-Z0-9-])", text)
        result.extend(matches)
    return result


def first_value(row: Mapping[str, object] | None, *keys: str) -> str:
    if not isinstance(row, Mapping):
        return ""
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def row_id(row: Mapping[str, object] | None) -> str:
    return first_value(row, "id", "policy_id", "policyId", "process_id", "processId")


def process_target(usecase: Mapping[str, object]) -> bool:
    return first_value(usecase, "process_target", "processTarget").upper() == "Y"


def clean(value: object) -> str:
    return str(value or "").strip()


def unique(items: Sequence[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = clean(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def issue(kind: str, target: object, reason: str) -> dict:
    return {"type": kind, "id": clean(target), "reason": reason}


def dedupe_issues(issues: Sequence[Mapping[str, object]]) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in issues:
        key = (clean(item.get("type")), clean(item.get("id")), clean(item.get("reason")))
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(item))
    return result


def normalize_stage_key(stage_key: str) -> str:
    stage = str(stage_key or "").strip().casefold()
    if stage in {"06_state", "state", "states"}:
        return "state"
    if stage in {"07_process", "process", "processes", "09_process_detail", "process_detail"}:
        return "process"
    if stage in {"08_functions", "functions", "09_function_detail", "function_detail"}:
        return "functions"
    if stage in {"09_policies", "policies"}:
        return "policies"
    if stage in {"04_usecases", "usecases"}:
        return "usecases"
    if stage in {"03_actors", "actors"}:
        return "actors"
    return stage


def relevant_missing_types(stage: str) -> set[str]:
    if stage == "actors":
        return {"usecase_unknown_actor"}
    if stage == "usecases":
        return {"usecase_unknown_actor", "usecase_without_process"}
    if stage == "state":
        return {"state_transition_unknown_from", "state_transition_unknown_to"}
    if stage == "process":
        return {"usecase_without_process", "process_unknown_usecase"}
    if stage == "functions":
        return {"process_without_function", "process_unknown_function_ref", "function_unknown_process"}
    if stage == "policies":
        return {
            "process_without_policy_group",
            "process_unknown_policy_group_ref",
            "policy_detail_unknown_group",
            "policy_group_without_detail",
        }
    return set()


def compact_rows(rows_in: Sequence[object], stage: str) -> list[dict]:
    keys_by_stage = {
        "actors": ("actor_id", "actor_name", "usecase_id", "usecase_name"),
        "usecases": ("actor_id", "actor_name", "usecase_id", "usecase_name"),
        "process": ("usecase_id", "usecase_name", "process_id", "process_name"),
        "functions": ("process_id", "process_name", "function_ids"),
        "policies": ("process_id", "process_name", "policy_group_ids"),
    }
    keys = keys_by_stage.get(stage, ("actor_id", "usecase_id", "process_id", "function_ids", "policy_group_ids"))
    result: list[dict] = []
    for row in rows_in:
        if not isinstance(row, Mapping):
            continue
        result.append({key: row.get(key) for key in keys if row.get(key) not in (None, "", [])})
    return result


def relevant_orphans(orphan_ids: object, stage: str) -> dict:
    if not isinstance(orphan_ids, Mapping):
        return {}
    keys_by_stage = {
        "actors": ("actors",),
        "state": ("states",),
        "functions": ("functions",),
        "policies": ("policy_groups",),
    }
    keys = keys_by_stage.get(stage, ())
    return {key: orphan_ids.get(key, []) for key in keys if orphan_ids.get(key)}
