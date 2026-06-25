"""Document density planning for policy authoring.

The generator should not produce every policy document at the same structural
density. This module computes a small, deterministic density contract from the
available requirements, references, and template type. The contract is used as
an authoring target, not as topic-specific content.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


SIGNAL_KEYWORDS = {
    "state": ("상태", "전이", "진행", "완료", "보류", "제한", "만료", "실패", "취소", "해지", "탈퇴"),
    "exception": ("예외", "오류", "장애", "실패", "불가", "제한", "재시도", "복구", "상담"),
    "bss": ("BSS", "원장", "청구", "회선", "가입", "약정", "요금", "판정"),
    "external": ("연계", "외부", "제휴", "콜백", "승인", "배송", "결제", "PG"),
    "auth": ("인증", "본인확인", "동의", "권한", "명의", "법정대리인", "대리인"),
    "notice": ("알림", "고지", "안내", "공지", "결과 회신"),
    "history": ("이력", "로그", "저장", "보관", "파기", "증적", "감사"),
    "policy_value": ("횟수", "시간", "기간", "금액", "한도", "우선순위", "허용", "제한 조건"),
    "operation": ("운영", "관리", "승인", "검수", "품질", "모니터링", "보정"),
    "privacy": ("개인정보", "민감정보", "마스킹", "동의 철회"),
}


@dataclass(frozen=True)
class DensityProfile:
    level: str
    score: int
    template_type: str
    requirement_count: int
    reference_count: int
    signal_counts: dict[str, int]
    structural_requirement_limit: int
    requirement_policy_limit: int
    max_usecases_total: int
    max_usecases_y: int
    max_states: int
    max_state_transitions: int
    process_min_bonus: int
    recommended_processes_per_y_usecase: str
    policy_detail_target_range: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_density_profile(
    ctx: object | None = None,
    *,
    requirement_items: Sequence[object] | None = None,
    requirements: Sequence[object] | None = None,
    references: Sequence[object] | None = None,
    template_type: str | None = None,
) -> DensityProfile:
    requirements = list(requirements if requirements is not None else getattr(ctx, "requirements", ()) or ())
    references = list(references if references is not None else getattr(ctx, "references", ()) or ())
    items = list(requirement_items or requirements)
    template = (template_type or getattr(ctx, "template_type", "") or "simple").strip().lower()

    signal_counts = count_density_signals(items)
    score = requirement_score(len(requirements))
    score += reference_score(len(references))
    score += min(6, sum(1 for value in signal_counts.values() if value > 0))
    if signal_counts.get("operation", 0) >= 3:
        score += 1
    if template == "full":
        score += 2

    level = density_level(score)
    return profile_for_level(
        level,
        score=score,
        template_type=template,
        requirement_count=len(requirements),
        reference_count=len(references),
        signal_counts=signal_counts,
    )


def density_profile_from_mapping(value: object) -> DensityProfile | None:
    if not isinstance(value, Mapping):
        return None
    required = {
        "level",
        "score",
        "template_type",
        "requirement_count",
        "reference_count",
        "signal_counts",
        "structural_requirement_limit",
        "requirement_policy_limit",
        "max_usecases_total",
        "max_usecases_y",
        "max_states",
        "max_state_transitions",
        "process_min_bonus",
        "recommended_processes_per_y_usecase",
        "policy_detail_target_range",
    }
    if not required.issubset(set(value.keys())):
        return None
    try:
        return DensityProfile(
            level=str(value.get("level", "standard")),
            score=int(value.get("score", 0) or 0),
            template_type=str(value.get("template_type", "simple") or "simple"),
            requirement_count=int(value.get("requirement_count", 0) or 0),
            reference_count=int(value.get("reference_count", 0) or 0),
            signal_counts=dict(value.get("signal_counts", {}) or {}),
            structural_requirement_limit=int(value.get("structural_requirement_limit", 2) or 2),
            requirement_policy_limit=int(value.get("requirement_policy_limit", 17) or 17),
            max_usecases_total=int(value.get("max_usecases_total", 11) or 11),
            max_usecases_y=int(value.get("max_usecases_y", 6) or 6),
            max_states=int(value.get("max_states", 12) or 12),
            max_state_transitions=int(value.get("max_state_transitions", 28) or 28),
            process_min_bonus=int(value.get("process_min_bonus", 0) or 0),
            recommended_processes_per_y_usecase=str(value.get("recommended_processes_per_y_usecase", "복수 전환점")),
            policy_detail_target_range=str(value.get("policy_detail_target_range", "80~110")),
        )
    except (TypeError, ValueError):
        return None


def density_profile_from_spec(spec: object) -> DensityProfile | None:
    if not isinstance(spec, Mapping):
        return None
    profile = density_profile_from_mapping(spec.get("density_profile"))
    if profile:
        return profile
    meta = spec.get("meta", {})
    if isinstance(meta, Mapping):
        return density_profile_from_mapping(meta.get("density_profile"))
    return None


def density_prompt_contract(profile: DensityProfile | None) -> dict:
    if profile is None:
        return {}
    return {
        "level": profile.level,
        "rule": "문서 밀도는 주제 복잡도에 맞춘 참고 목표다. 개수를 맞추기 위해 억지로 항목을 늘리지 말고, 단일 포괄 항목으로 업무 흐름이 뭉개지는 경우에만 분해한다.",
        "structural_requirement_limit": profile.structural_requirement_limit,
        "requirement_policy_limit": profile.requirement_policy_limit,
        "max_usecases_total": profile.max_usecases_total,
        "max_usecases_y": profile.max_usecases_y,
        "max_states": profile.max_states,
        "max_state_transitions": profile.max_state_transitions,
        "process_min_bonus": profile.process_min_bonus,
        "recommended_processes_per_y_usecase": profile.recommended_processes_per_y_usecase,
        "process_rule": "권장 범위는 검토 관점이다. Y 유즈케이스가 1개 프로세스로만 끝나면 유즈케이스가 절차 단계처럼 너무 작은지, 또는 프로세스가 시작·판단·처리·결과를 한 행에 섞었는지 점검한다. 모든 유즈케이스에 동일 개수를 강제하지 말고 의미 있는 전환점으로만 나눈다.",
        "policy_detail_target_range": profile.policy_detail_target_range,
    }


def process_minimum_for_usecase(actor: object, name: object, profile: DensityProfile | None = None) -> int:
    actor_text = str(actor or "")
    name_text = str(name or "")
    if "운영" in actor_text or "관리자" in actor_text:
        base = 2
    elif any(keyword in name_text for keyword in ("정보", "조회", "확인")):
        base = 2
    elif any(keyword in name_text for keyword in ("변경", "취소", "해지", "탈퇴", "후속", "재시도", "상담")):
        base = 2
    else:
        base = 2
    bonus = max(0, min(1, int(getattr(profile, "process_min_bonus", 0) or 0))) if profile else 0
    return min(3, base + bonus)


def count_density_signals(items: Sequence[object]) -> dict[str, int]:
    text = "\n".join(item_text(item) for item in items)
    return {
        signal: sum(1 for keyword in keywords if keyword in text)
        for signal, keywords in SIGNAL_KEYWORDS.items()
    }


def item_text(item: object) -> str:
    if isinstance(item, Mapping):
        values = [
            item.get("title", ""),
            item.get("short_title", ""),
            item.get("description", ""),
            item.get("detail_name", ""),
            item.get("detail_description", ""),
            item.get("requirement_type", ""),
            item.get("policy_group", ""),
        ]
    else:
        values = [
            getattr(item, "detail_name", ""),
            getattr(item, "detail_description", ""),
            getattr(item, "requirement_type", ""),
            getattr(item, "parent_name", ""),
            getattr(item, "parent_description", ""),
        ]
    return re.sub(r"\s+", " ", " ".join(str(value or "") for value in values)).strip()


def requirement_score(count: int) -> int:
    if count >= 150:
        return 6
    if count >= 90:
        return 5
    if count >= 50:
        return 4
    if count >= 20:
        return 3
    if count > 0:
        return 1
    return 0


def reference_score(count: int) -> int:
    if count >= 50:
        return 3
    if count >= 20:
        return 2
    if count > 0:
        return 1
    return 0


def density_level(score: int) -> str:
    if score >= 14:
        return "complex"
    if score >= 10:
        return "high"
    if score >= 5:
        return "standard"
    return "low"


def profile_for_level(
    level: str,
    *,
    score: int,
    template_type: str,
    requirement_count: int,
    reference_count: int,
    signal_counts: dict[str, int],
) -> DensityProfile:
    full = template_type == "full"
    table = {
        "low": {
            "structural": 1,
            "policy": 10,
            "usecases": (9, 5),
            "states": (10, 24),
            "bonus": 0,
            "process_range": "복수 전환점",
            "policy_range": "70~95",
        },
        "standard": {
            "structural": 2,
            "policy": 17,
            "usecases": (11, 6),
            "states": (12, 28),
            "bonus": 0,
            "process_range": "복수 전환점",
            "policy_range": "85~110",
        },
        "high": {
            "structural": 3,
            "policy": 22,
            "usecases": (13, 7),
            "states": (14, 34),
            "bonus": 1,
            "process_range": "복수 전환점+예외 분기",
            "policy_range": "95~125",
        },
        "complex": {
            "structural": 4,
            "policy": 28,
            "usecases": (15, 8),
            "states": (16, 40),
            "bonus": 1,
            "process_range": "복수 전환점+예외/운영 분기",
            "policy_range": "105~140",
        },
    }
    selected = table.get(level, table["standard"])
    usecase_total, usecase_y = selected["usecases"]
    states, transitions = selected["states"]
    if full:
        usecase_total += 2
        usecase_y += 1
        states += 6
        transitions += 12
    return DensityProfile(
        level=level,
        score=score,
        template_type=template_type or "simple",
        requirement_count=requirement_count,
        reference_count=reference_count,
        signal_counts=signal_counts,
        structural_requirement_limit=selected["structural"] + (1 if full and selected["structural"] < 5 else 0),
        requirement_policy_limit=selected["policy"] + (6 if full else 0),
        max_usecases_total=usecase_total,
        max_usecases_y=usecase_y,
        max_states=states,
        max_state_transitions=transitions,
        process_min_bonus=selected["bonus"],
        recommended_processes_per_y_usecase=selected["process_range"],
        policy_detail_target_range=selected["policy_range"],
    )
