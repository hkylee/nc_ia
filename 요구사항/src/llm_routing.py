"""Role-based LLM routing for policy generation.

The default model stays user-controlled through OPENAI_MODEL. This module only
chooses the lightest safe reasoning effort for each role and escalates when a
chapter needs revision.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Sequence

try:
    from llm_client import LLMClient, MOCK_MODEL
except ImportError:  # pragma: no cover - package import fallback.
    from .llm_client import LLMClient, MOCK_MODEL


@dataclass(frozen=True)
class RouteProfile:
    route: str
    reasoning_effort: str
    escalation_effort: str
    llm_enabled: bool = True
    default_model: str = ""
    escalation_model: str = ""


ROUTE_PROFILES: dict[str, RouteProfile] = {
    "topic_learning": RouteProfile("topic_learning", "high", "high", default_model="gpt-5.5"),
    "blueprint_architect": RouteProfile("blueprint_architect", "high", "high", default_model="gpt-5.5"),
    "overview": RouteProfile("overview", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "terms": RouteProfile("terms", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "actors": RouteProfile("actors", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "usecases": RouteProfile("usecases", "high", "high", default_model="gpt-5.5"),
    "usecase_diagram": RouteProfile(
        "usecase_diagram", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"
    ),
    "state": RouteProfile("state", "high", "high", default_model="gpt-5.5"),
    "process": RouteProfile("process", "high", "high", default_model="gpt-5.5"),
    "process_detail": RouteProfile("process_detail", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "functions": RouteProfile("functions", "high", "high", default_model="gpt-5.5"),
    "function_detail": RouteProfile(
        "function_detail", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"
    ),
    "policies": RouteProfile("policies", "high", "high", default_model="gpt-5.5"),
    "terms_refinement": RouteProfile(
        "terms_refinement", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"
    ),
    "final_check": RouteProfile("final_check", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "inspector_stage": RouteProfile("inspector_stage", "high", "high", default_model="gpt-5.5"),
    "inspector_final": RouteProfile("inspector_final", "high", "high", default_model="gpt-5.5"),
    "inspector_final_comprehensive": RouteProfile(
        "inspector_final_comprehensive", "xhigh", "xhigh", default_model="gpt-5.5"
    ),
    "revision": RouteProfile("revision", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "dev_qa_review": RouteProfile("dev_qa_review", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "health_check": RouteProfile("health_check", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "pi_agent": RouteProfile("pi_agent", "xhigh", "xhigh", default_model="gpt-5.5"),
    "analysis_alignment": RouteProfile("analysis_alignment", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "channel_pi_status": RouteProfile("channel_pi_status", "medium", "high", default_model="gpt-5.4", escalation_model="gpt-5.5"),
    "live_feedback": RouteProfile("live_feedback", "medium", "medium", default_model="gpt-5.4-mini"),
}

def client_for_chapter(
    base_client: LLMClient,
    chapter_key: str,
    *,
    attempt: int = 1,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> LLMClient:
    return client_for_route(base_client, chapter_key, attempt=attempt, feedback=feedback)


def client_for_topic_learning(base_client: LLMClient) -> LLMClient:
    return client_for_route(base_client, "topic_learning")


def client_for_stage_inspector(
    base_client: LLMClient,
    *,
    final: bool = False,
    attempt: int = 1,
    inspection_mode: str = "",
) -> LLMClient:
    route = inspector_route_key(final=final, inspection_mode=inspection_mode)
    return client_for_route(base_client, route, attempt=attempt)


def client_for_revision(base_client: LLMClient, *, attempt: int = 1) -> LLMClient:
    return client_for_route(base_client, "revision", attempt=attempt)


def client_for_pi_agent(base_client: LLMClient) -> LLMClient:
    return client_for_route(base_client, "pi_agent")


def inspector_route_key(*, final: bool, inspection_mode: str = "") -> str:
    if not final:
        return "inspector_stage"
    normalized = str(inspection_mode or "").strip().casefold().replace("_", "-")
    if normalized in {"final-only", "final"}:
        return "inspector_final_comprehensive"
    return "inspector_final"


def client_for_route(
    base_client: LLMClient,
    route_key: str,
    *,
    attempt: int = 1,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> LLMClient:
    profile = ROUTE_PROFILES.get(route_key, RouteProfile(route_key, base_client.reasoning_effort, "high"))
    if base_client.writer_mode == "mock":
        return base_client.with_overrides(model=base_client.model or MOCK_MODEL, reasoning_effort="none")
    if not profile.llm_enabled and not route_llm_forced(route_key):
        return base_client.with_overrides(writer_mode="local", reasoning_effort="")

    route_env = env_suffix(route_key)
    model = os.getenv(f"OPENAI_MODEL_{route_env}") or profile.default_model or base_client.model
    effort = os.getenv(f"OPENAI_REASONING_EFFORT_{route_env}") or profile.reasoning_effort
    if should_escalate(attempt, feedback):
        model = os.getenv(f"OPENAI_MODEL_{route_env}_ESCALATED") or profile.escalation_model or model
        effort = os.getenv(f"OPENAI_REASONING_EFFORT_{route_env}_ESCALATED") or profile.escalation_effort
    return base_client.with_overrides(model=model, reasoning_effort=effort)


def route_metadata(client: LLMClient, route_key: str, *, attempt: int = 1, feedback: Sequence[Mapping[str, object]] | None = None) -> dict:
    routed = client_for_route(client, route_key, attempt=attempt, feedback=feedback)
    reasons = escalation_reasons(attempt, feedback)
    return {
        "route": route_key,
        "model": routed.model,
        "reasoning_effort": routed.reasoning_effort,
        "writer_mode": routed.writer_mode,
        "llm_enabled": routed.enabled,
        "max_output_tokens": None,
        "output_limit": "omitted",
        "escalated": bool(reasons),
        "escalation_reasons": reasons,
    }


def routing_plan(base_client: LLMClient) -> dict:
    if base_client.writer_mode == "mock":
        return {
            key: {
                "model": base_client.model or MOCK_MODEL,
                "reasoning_effort": "none",
                "escalation_effort": "none",
                "escalation_model": base_client.model or MOCK_MODEL,
                "llm_enabled": True,
                "writer_mode": "mock",
                "mock": True,
                "max_output_tokens": None,
                "output_limit": "omitted",
            }
            for key in ROUTE_PROFILES
        }
    return {
        key: {
            "model": (os.getenv(f"OPENAI_MODEL_{env_suffix(key)}") or profile.default_model or base_client.model),
            "reasoning_effort": (os.getenv(f"OPENAI_REASONING_EFFORT_{env_suffix(key)}") or profile.reasoning_effort),
            "escalation_effort": (
                os.getenv(f"OPENAI_REASONING_EFFORT_{env_suffix(key)}_ESCALATED") or profile.escalation_effort
            ),
            "escalation_model": (
                os.getenv(f"OPENAI_MODEL_{env_suffix(key)}_ESCALATED")
                or profile.escalation_model
                or os.getenv(f"OPENAI_MODEL_{env_suffix(key)}")
                or profile.default_model
                or base_client.model
            ),
            "llm_enabled": profile.llm_enabled,
            "max_output_tokens": None,
            "output_limit": "omitted",
        }
        for key, profile in ROUTE_PROFILES.items()
    }


def should_escalate(attempt: int, feedback: Sequence[Mapping[str, object]] | None) -> bool:
    return bool(escalation_reasons(attempt, feedback))


def escalation_reasons(attempt: int, feedback: Sequence[Mapping[str, object]] | None) -> list[str]:
    reasons: list[str] = []
    if attempt > 1:
        reasons.append("retry_attempt")
    for item in feedback or []:
        severity = str(item.get("severity", "")).strip().casefold()
        priority = str(item.get("priority_tier", "") or item.get("tier", "")).strip().upper()
        if severity in {"error", "critical"}:
            reasons.append("critical_feedback")
        if priority == "P1":
            reasons.append("p1_feedback")
        if str(item.get("priority", "")).strip().upper() == "P1":
            reasons.append("p1_feedback")
        if truthy(item.get("is_quality_gate")) or truthy(item.get("dynamic_escalation")):
            reasons.append("quality_gate_or_dynamic_signal")
        if int_like(item.get("gate_blocker_count")) > 0 or truthy(item.get("risk_flag")):
            reasons.append("gate_blocker_or_risk_flag")
        if str(item.get("must_resolve", "")).strip().upper() == "Y":
            reasons.append("must_resolve_feedback")
        if str(item.get("category", "")).strip() == "사용자 검수" or severity == "manual":
            reasons.append("manual_review_feedback")
    return sorted(set(reasons))


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def int_like(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def route_llm_forced(route_key: str) -> bool:
    value = os.getenv(f"OPENAI_USE_LLM_FOR_{env_suffix(route_key)}", "").strip().casefold()
    return value in {"1", "true", "yes", "y"}


def env_suffix(route_key: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in route_key.upper())
