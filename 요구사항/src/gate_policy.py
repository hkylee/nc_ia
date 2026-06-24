"""Shared quality gate policy for chapter inspector decisions."""

from __future__ import annotations

import os
from typing import Mapping


DEFAULT_HARD_GATE_MIN_SCORE = 90
DEFAULT_SOFT_GATE_MIN_SCORE = 85
DEFAULT_HARD_GATE_EXTRA_RETRIES = 0

HARD_GATE_CHAPTERS = {"usecases", "state", "process", "process_detail", "function_detail", "policies"}
SOFT_GATE_CHAPTERS = {"overview", "terms", "actors", "functions"}
LOG_ONLY_CHAPTERS = {"usecase_diagram", "terms_refinement", "final_check"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def hard_gate_min_score() -> int:
    return max(0, min(100, env_int("HARD_GATE_MIN_SCORE", DEFAULT_HARD_GATE_MIN_SCORE)))


def soft_gate_min_score(fallback: int = DEFAULT_SOFT_GATE_MIN_SCORE) -> int:
    default = max(DEFAULT_SOFT_GATE_MIN_SCORE, int(fallback or DEFAULT_SOFT_GATE_MIN_SCORE))
    return max(0, min(100, env_int("SOFT_GATE_MIN_SCORE", default)))


def hard_gate_extra_retries() -> int:
    return max(0, env_int("HARD_GATE_EXTRA_RETRIES", DEFAULT_HARD_GATE_EXTRA_RETRIES))


def gate_tier(chapter_key: str) -> str:
    key = str(chapter_key or "").strip()
    if key in HARD_GATE_CHAPTERS:
        return "hard"
    if key in LOG_ONLY_CHAPTERS:
        return "log-only"
    return "soft"


def gate_required_score(chapter_key: str, fallback_min_score: int) -> int:
    tier = gate_tier(chapter_key)
    if tier == "hard":
        return hard_gate_min_score()
    if tier == "log-only":
        return 0
    return soft_gate_min_score(fallback_min_score)


def stage_max_loops(chapter_key: str, base_max_loops: int) -> int:
    base = max(1, int(base_max_loops or 1))
    if gate_tier(chapter_key) == "hard":
        return base + hard_gate_extra_retries()
    return base


def gate_rule_summary(fallback_min_score: int, base_max_loops: int) -> dict:
    return {
        "tiers": {
            "hard": {
                "chapters": sorted(HARD_GATE_CHAPTERS),
                "min_score": hard_gate_min_score(),
                "requires": "score >= min_score, gate_blocker_count = 0, error_count = 0",
                "extra_retries": hard_gate_extra_retries(),
            },
            "soft": {
                "chapters": sorted(SOFT_GATE_CHAPTERS),
                "min_score": soft_gate_min_score(fallback_min_score),
                "requires": "score >= min_score, error_count = 0",
            },
            "log-only": {
                "chapters": sorted(LOG_ONLY_CHAPTERS),
                "min_score": 0,
                "requires": "records open issues but does not block next chapter",
            },
        },
        "base_max_loops": max(1, int(base_max_loops or 1)),
    }


def inspect_gate_decision(report: object, chapter_key: str, fallback_min_score: int) -> dict:
    tier = gate_tier(chapter_key)
    threshold = gate_required_score(chapter_key, fallback_min_score)
    findings = list(getattr(report, "findings", []) or [])
    error_count = sum(1 for finding in findings if getattr(finding, "severity", "") == "error")
    metrics = getattr(report, "metrics", {}) or {}
    score_breakdown = metrics.get("score_breakdown", {}) if isinstance(metrics, Mapping) else {}
    gate_blocker_count = int(score_breakdown.get("gate_blocker_count", 0) or 0)
    gate_blocker_count += semantic_gate_blocker_count(findings, chapter_key)
    score = int(getattr(report, "score", 0) or 0)

    if tier == "log-only":
        passed = True
    elif tier == "hard":
        passed = score >= threshold and gate_blocker_count == 0 and error_count == 0
    else:
        passed = score >= threshold and error_count == 0

    return {
        "tier": tier,
        "threshold": threshold,
        "score": score,
        "error_count": error_count,
        "gate_blocker_count": gate_blocker_count,
        "passed": passed,
    }


def semantic_gate_blocker_count(findings: list[object], chapter_key: str) -> int:
    """Promote high-risk semantic warnings to blockers for hard-gate chapters."""
    key = str(chapter_key or "").strip()
    blockers = 0
    for finding in findings:
        severity = str(getattr(finding, "severity", "") or "")
        category = str(getattr(finding, "category", "") or "")
        title = str(getattr(finding, "title", "") or "")
        detail = str(getattr(finding, "detail", "") or "")
        recommendation = str(getattr(finding, "recommendation", "") or "")
        combined = " ".join((category, title, detail, recommendation))
        if severity == "error":
            continue
        if key == "state" and any(marker in combined for marker in ("분기 우선순위", "상태 전이", "전이 기준", "도달 조건")):
            blockers += 1
            continue
        if key == "process" and any(marker in combined for marker in ("승인된 상태명", "비승인 상태명", "책임경계", "최종 경로 분기")):
            blockers += 1
            continue
        if key == "process_detail" and any(marker in combined for marker in ("진입 조건", "종료 조건", "선행", "후행", "관련 기능", "관련 정책")):
            blockers += 1
            continue
        if key == "function_detail" and any(marker in combined for marker in ("입력", "처리 로직", "출력", "실패", "예외", "관련 정책")):
            blockers += 1
            continue
        if key == "policies" and any(marker in combined for marker in ("판단 기준", "기준값", "허용 조건", "제한 조건")):
            blockers += 1
    return blockers
