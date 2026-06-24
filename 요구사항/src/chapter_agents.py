"""Chapter-specialized policy writer agents.

Each chapter agent writes one part of the policy spec, records what it reviewed,
and leaves the next agent a structured JSON spec to continue from.
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, MutableMapping, Optional, Sequence

try:
    from analysis_methods import method_knowledge_for_agent, method_knowledge_for_learning
    from authoring_blueprint import stage_blueprint_for_prompt
    from context_assembler import assemble_context_pack, update_traceability
    from document_density import density_profile_from_spec, density_prompt_contract, process_minimum_for_usecase
    from evidence_store import EvidenceStore, evidence_authority_tier_for_authority, evidence_source_authority_for_values
    from llm_client import LLMClient, LLMError
    from llm_routing import client_for_chapter, client_for_topic_learning, route_metadata
    from policy_insight_rules import insight_applicability_for_prompt
    from policy_style_anchor import policy_style_anchor_for_prompt
    from schema import (
        build_base_meta,
        build_history,
    )
    from topic_knowledge_builder import compact_topic_knowledge_for_prompt, load_topic_knowledge_pack
except ImportError:  # pragma: no cover - package import fallback.
    from .analysis_methods import method_knowledge_for_agent, method_knowledge_for_learning
    from .authoring_blueprint import stage_blueprint_for_prompt
    from .context_assembler import assemble_context_pack, update_traceability
    from .document_density import density_profile_from_spec, density_prompt_contract, process_minimum_for_usecase
    from .evidence_store import EvidenceStore, evidence_authority_tier_for_authority, evidence_source_authority_for_values
    from .llm_client import LLMClient, LLMError
    from .llm_routing import client_for_chapter, client_for_topic_learning, route_metadata
    from .policy_insight_rules import insight_applicability_for_prompt
    from .policy_style_anchor import policy_style_anchor_for_prompt
    from .schema import (
        build_base_meta,
        build_history,
    )
    from .topic_knowledge_builder import compact_topic_knowledge_for_prompt, load_topic_knowledge_pack


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEARNING_CACHE_DIR = PROJECT_ROOT / "reports" / "cache"
CHUNKED_LLM_CHAPTERS = {"process", "functions", "policies", "process_detail", "function_detail"}
DEFAULT_LLM_TASK_MAX_ATTEMPTS = 5
DEFAULT_LLM_PATCH_TASK_MAX_ATTEMPTS = 2
DEFAULT_LLM_TASK_RETRY_BASE_SECONDS = 2.0
TOPIC_LEARNING_PROMPT_VERSION = "topic-scope-boundary-v7-requirement-level-pdf"
MAX_PROCESSES_PER_Y_USECASE = 7
BODY_ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:TM|ACT|US|ST|PR|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?:[은는이가을를의와과로])?(?![A-Z0-9-])")
FUNCTION_PROCESSING_LOGIC_PATTERN = re.compile(
    r"^\s*\(상태\)\s*.+?\s*→\s*\(액션\)\s*.+?\s*→\s*\(결과\)\s*.+"
)
INCOMPLETE_SENTENCE_TAILS = (
    "후상",
    "후",
    "다음",
    "통해",
    "위해",
    "및",
    "또는",
    "으로",
    "로",
)
SYSTEM_RESPONSIBILITY_MARKERS = (
    "판정",
    "검증",
    "조회",
    "회신",
    "저장",
    "반영",
    "인증",
    "연계",
    "이력",
    "결과",
    "알림",
    "분류",
    "생성",
)


@dataclass(frozen=True)
class ChapterStage:
    key: str
    name: str
    scope: str
    agent: "ChapterAgent"


@dataclass(frozen=True)
class AgentRuntime:
    ctx: object
    target_spec: dict
    learning: dict
    guideline: dict
    evidence_store: EvidenceStore
    authoring_blueprint: dict
    llm_client: LLMClient


def routing_feedback_for_agent(
    agent: "ChapterAgent",
    spec: Mapping[str, object],
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> List[Mapping[str, object]]:
    """Build routing-only signals without polluting the writer feedback prompt."""
    signals: List[Mapping[str, object]] = [dict(item) for item in feedback or [] if isinstance(item, Mapping)]
    signals.extend(blueprint_quality_routing_signals(agent.chapter_key, spec, runtime))
    signals.extend(open_issue_routing_signals(agent.chapter_key, spec))
    signals.extend(evidence_complexity_routing_signals(agent.chapter_key, spec))
    return dedupe_routing_signals(signals)


def blueprint_quality_routing_signals(chapter_key: str, spec: Mapping[str, object], runtime: AgentRuntime) -> List[dict]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    quality_gate = meta.get("blueprint_quality_gate", {}) if isinstance(meta, Mapping) else {}
    if not isinstance(quality_gate, Mapping):
        quality_gate = {}
    if not quality_gate and isinstance(runtime.authoring_blueprint, Mapping):
        runtime_quality_gate = runtime.authoring_blueprint.get("quality_gate", {})
        quality_gate = runtime_quality_gate if isinstance(runtime_quality_gate, Mapping) else {}
    if not isinstance(quality_gate, Mapping) or not quality_gate:
        return []

    stage_key = routing_stage_key(chapter_key)
    stage_risk_map = quality_gate.get("stage_risk_map", {})
    stage_risk = stage_risk_map.get(stage_key, {}) if isinstance(stage_risk_map, Mapping) else {}
    blueprint_risk = stage_risk_map.get("blueprint", {}) if isinstance(stage_risk_map, Mapping) else {}
    relevant_findings = [
        item
        for item in quality_gate.get("findings", [])
        if isinstance(item, Mapping) and str(item.get("stage", "") or "") in {stage_key, "blueprint"}
    ]
    if not relevant_findings and not stage_risk and not blueprint_risk:
        return []

    score = safe_int_for_routing(quality_gate.get("score"))
    threshold = safe_int_for_routing(quality_gate.get("threshold"))
    passed = routing_truthy(quality_gate.get("passed"))
    should_signal = not passed or (threshold and score < threshold) or bool(stage_risk)
    if not should_signal:
        return []

    return [
        {
            "dynamic_escalation": True,
            "severity": "routing",
            "tier": "P2",
            "category": "blueprint_quality",
            "title": "Blueprint 품질 리스크 반영",
            "detail": (
                f"{stage_key} 장 작성 전에 Blueprint 품질 리스크를 더 깊게 해석합니다. "
                f"score={score}, threshold={threshold}, finding={len(relevant_findings)}"
            ),
            "target_path": "meta.blueprint_quality_gate",
            "risk_flag": True,
        }
    ]


def open_issue_routing_signals(chapter_key: str, spec: Mapping[str, object]) -> List[dict]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    issues = meta.get("open_inspector_issues", []) if isinstance(meta, Mapping) else []
    if not isinstance(issues, list):
        return []
    stage_key = routing_stage_key(chapter_key)
    signals: List[dict] = []
    for issue in issues[-12:]:
        if not isinstance(issue, Mapping) or not routing_truthy(issue.get("risk_flag", False)):
            continue
        issue_chapter = routing_stage_key(str(issue.get("chapter", "") or issue.get("stage", "")))
        feedback_items = issue.get("feedback", [])
        related_by_feedback = False
        if isinstance(feedback_items, list):
            related_by_feedback = any(
                isinstance(item, Mapping)
                and routing_stage_key(str(item.get("fix_owner", "") or item.get("upstream_chapter", ""))) == stage_key
                for item in feedback_items
            )
        if issue_chapter not in {stage_key, "final", "blueprint"} and not related_by_feedback:
            continue
        signals.append(
            {
                "dynamic_escalation": True,
                "severity": "routing",
                "tier": str(issue.get("risk_tier", "") or "P2"),
                "category": "open_inspector_issue",
                "title": "이전 검수 리스크 반영",
                "detail": limit_text_for_policy(issue.get("summary", "") or issue.get("reason", ""), 180),
                "target_path": "meta.open_inspector_issues",
                "risk_flag": True,
            }
        )
    return signals[:3]


def evidence_complexity_routing_signals(chapter_key: str, spec: Mapping[str, object]) -> List[dict]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    topic_map = meta.get("topic_evidence_map", {}) if isinstance(meta, Mapping) else {}
    stats = topic_map.get("stats", {}) if isinstance(topic_map, Mapping) and isinstance(topic_map.get("stats", {}), Mapping) else {}
    evidence_count = safe_int_for_routing(stats.get("evidence_id_count"))
    source_count = safe_int_for_routing(stats.get("source_count"))
    evidence_threshold = routing_env_int("NC_ROUTING_COMPLEX_EVIDENCE_THRESHOLD", 40)
    source_threshold = routing_env_int("NC_ROUTING_COMPLEX_SOURCE_THRESHOLD", 12)
    if evidence_count < evidence_threshold and source_count < source_threshold:
        return []
    return [
        {
            "dynamic_escalation": True,
            "severity": "routing",
            "tier": "P2",
            "category": "evidence_complexity",
            "title": "참고 근거 복잡도 높음",
            "detail": f"{chapter_key} 작성 시 근거 {evidence_count}건, 출처 {source_count}개를 계층 기준에 맞춰 선별합니다.",
            "target_path": "meta.topic_evidence_map.stats",
        }
    ]


def dedupe_routing_signals(signals: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in signals:
        key = (
            str(item.get("category", "")),
            str(item.get("target_path", "")),
            str(item.get("title", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def routing_stage_key(value: str) -> str:
    key = str(value or "").strip().casefold().replace("-", "_")
    aliases = {
        "policy": "policies",
        "policy_groups": "policies",
        "policy_details": "policies",
        "states": "state",
        "state_transitions": "state",
        "term": "terms",
        "terms_refinement": "terms_refinement",
        "finalize": "final",
    }
    return aliases.get(key, key)


def safe_int_for_routing(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def routing_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def routing_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on", "risk_flag"}


class ChapterAgent:
    chapter_key = ""
    display_name = ""
    output_fields: Sequence[str] = ()

    def instruction(self, guideline: dict) -> str:
        return "템플릿 구조와 샘플 작성 밀도를 기준으로 현재 챕터를 작성한다."

    def write(
        self,
        spec: dict,
        runtime: AgentRuntime,
        attempt: int = 1,
        feedback: Sequence[Mapping[str, object]] | None = None,
    ) -> dict:
        reviewed_fields = populated_fields(spec)
        next_spec = copy.deepcopy(spec)
        llm_status = "local"
        llm_error = ""
        has_feedback = bool(feedback)
        routing_feedback = routing_feedback_for_agent(self, spec, runtime, feedback)
        chapter_llm_client = client_for_chapter(
            runtime.llm_client,
            self.chapter_key,
            attempt=attempt,
            feedback=routing_feedback,
        )
        if chapter_llm_client.enabled:
            retry_feedback = list(feedback or [])
            retry_events: List[dict] = []
            max_attempts = chapter_llm_task_max_attempts(self, spec, retry_feedback)
            for llm_attempt in range(1, max_attempts + 1):
                try:
                    payload = self.write_with_llm(spec, runtime, retry_feedback, chapter_llm_client)
                    ensure_full_chapter_payload_shape(self, payload)
                    candidate_spec = copy.deepcopy(spec)
                    self.apply_payload(candidate_spec, payload)
                    self.validate_payload(candidate_spec, runtime, payload)
                    normalize_agent_output(candidate_spec, self, runtime)
                    record_payload_generation_meta(candidate_spec, self, payload, attempt)
                    record_llm_retry_meta(candidate_spec, self, attempt, retry_events)
                    next_spec = candidate_spec
                    if chapter_llm_client.writer_mode == "mock":
                        llm_status = "mock_revision" if has_feedback or llm_attempt > 1 else "mock"
                    else:
                        llm_status = "llm_revision" if has_feedback or llm_attempt > 1 else "llm"
                    break
                except Exception as exc:
                    if not should_retry_llm_task_error(exc):
                        raise
                    if llm_attempt >= max_attempts:
                        llm_error = str(exc)
                        next_spec = writer_failure_fallback_spec(self, spec, runtime, feedback)
                        record_writer_failure_fallback(next_spec, self, exc, llm_attempt, max_attempts, feedback)
                        if chapter_llm_client.writer_mode == "mock":
                            llm_status = "mock_fallback_local"
                        else:
                            llm_status = "llm_fallback_local"
                        break
                    retry_events.append(
                        {
                            "llm_attempt": llm_attempt,
                            "reason": str(exc)[:300],
                        }
                    )
                    retry_feedback = list(retry_feedback) + [llm_retry_feedback(exc, llm_attempt)]
                    time.sleep(llm_retry_delay_seconds(llm_attempt))
        else:
            self.apply(next_spec, runtime)
            normalize_agent_output(next_spec, self, runtime)
            if chapter_llm_client.writer_mode == "auto":
                llm_status = "local_no_api_key"
            elif has_feedback:
                llm_status = "local_revision"
        record_context_pack(next_spec, self, runtime)
        record_agent_run(
            next_spec,
            self,
            runtime,
            reviewed_fields,
            llm_status,
            llm_error,
            attempt,
            feedback,
            routing_feedback=routing_feedback,
            llm_client=chapter_llm_client,
        )
        return next_spec

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        raise NotImplementedError

    def write_with_llm(
        self,
        spec: dict,
        runtime: AgentRuntime,
        feedback: Sequence[Mapping[str, object]] | None = None,
        llm_client: LLMClient | None = None,
    ) -> dict:
        llm_client = llm_client or runtime.llm_client
        if should_use_patch_revision(self, spec, feedback):
            return self.write_patch_revision_with_llm(spec, runtime, feedback or (), llm_client)
        local_spec = copy.deepcopy(spec)
        self.apply(local_spec, runtime)
        local_payload = self.extract_payload(local_spec)
        schema = chapter_output_schema(self)
        if should_chunk_chapter(self, local_payload):
            return self.write_with_llm_chunks(
                spec,
                runtime,
                feedback=feedback,
                llm_client=llm_client,
                local_payload=local_payload,
                schema=schema,
            )
        messages = [
            {
                "role": "user",
                "content": build_chapter_prompt(self, spec, local_payload, runtime, feedback),
            }
        ]
        payload = llm_client.generate_json(
            schema_name=f"{self.chapter_key}_chapter",
            schema=schema,
            instructions=build_system_instructions(runtime, self),
            input_messages=messages,
        )
        return payload

    def write_patch_revision_with_llm(
        self,
        spec: dict,
        runtime: AgentRuntime,
        feedback: Sequence[Mapping[str, object]],
        llm_client: LLMClient,
    ) -> dict:
        current_payload = self.extract_payload(spec)
        patch_target = revision_patch_target(self, current_payload, feedback)
        if not patch_target:
            patch_target = default_revision_patch_target(self, current_payload)
        if not patch_target:
            return dict(current_payload)
        patch_payload = llm_client.generate_json(
            schema_name=f"{self.chapter_key}_chapter_patch",
            schema=chapter_patch_schema(self),
            instructions=build_system_instructions(runtime),
            input_messages=[
                {
                    "role": "user",
                    "content": build_patch_revision_prompt(self, spec, patch_target, runtime, feedback),
                }
            ],
        )
        ensure_patch_payload_within_target(self, patch_payload, patch_target, feedback)
        merged = merge_patch_payload(self, current_payload, patch_payload, patch_target=patch_target)
        ensure_patch_feedback_targets_changed(self, current_payload, merged, feedback)
        merged["__llm_patch_revision"] = {
            "enabled": True,
            "mode": "patch",
            "chapter": self.chapter_key,
            "target_items": patch_target_summary(patch_target),
        }
        return merged

    def write_with_llm_chunks(
        self,
        spec: dict,
        runtime: AgentRuntime,
        *,
        feedback: Sequence[Mapping[str, object]] | None,
        llm_client: LLMClient,
        local_payload: Mapping[str, object],
        schema: Mapping[str, object],
    ) -> dict:
        chunks = chunk_payload_for_agent(self, local_payload)
        if len(chunks) <= 1:
            return llm_client.generate_json(
                schema_name=f"{self.chapter_key}_chapter",
                schema=schema,
                instructions=build_system_instructions(runtime, self),
                input_messages=[
                    {
                        "role": "user",
                        "content": build_chapter_prompt(self, spec, local_payload, runtime, feedback),
                    }
                ],
            )

        merged_chunks: List[Mapping[str, object]] = []
        chunk_fallbacks: List[dict] = []
        for index, chunk_payload in enumerate(chunks, start=1):
            chunk_feedback = list(feedback or [])
            for chunk_attempt in range(1, llm_task_max_attempts() + 1):
                try:
                    prompt = build_chunked_chapter_prompt(
                        self,
                        spec,
                        chunk_payload,
                        runtime,
                        chunk_feedback,
                        chunk_index=index,
                        total_chunks=len(chunks),
                    )
                    chunk_result = llm_client.generate_json(
                        schema_name=f"{self.chapter_key}_chapter_chunk",
                        schema=schema,
                        instructions=build_system_instructions(runtime, self),
                        input_messages=[{"role": "user", "content": prompt}],
                    )
                    if not isinstance(chunk_result, Mapping):
                        raise LLMError("분할 Writer 응답이 JSON 객체가 아닙니다.")
                    merged_chunks.append(filter_chunk_result(self, chunk_payload, chunk_result))
                    break
                except Exception as exc:
                    if not should_retry_llm_task_error(exc):
                        raise
                    if chunk_attempt >= llm_task_max_attempts():
                        merged_chunks.append(filter_chunk_result(self, chunk_payload, chunk_payload))
                        chunk_fallbacks.append(
                            {
                                "chunk_index": index,
                                "total_chunks": len(chunks),
                                "llm_attempt": chunk_attempt,
                                "max_attempts": llm_task_max_attempts(),
                                "reason": str(exc)[:500],
                            }
                        )
                        break
                    chunk_feedback = list(chunk_feedback) + [llm_retry_feedback(exc, chunk_attempt, chunk=index)]
                    time.sleep(llm_retry_delay_seconds(chunk_attempt))

        payload = merge_chunk_results(self, merged_chunks)
        payload["__llm_chunking"] = {
            "enabled": True,
            "chapter": self.chapter_key,
            "chunks": len(chunks),
            "fallback_chunks": chunk_fallbacks,
            "strategy": "large_chapter_split_by_local_ids_compact_context",
        }
        return payload

    def extract_payload(self, spec: dict) -> dict:
        payload = {}
        for field in self.output_fields:
            if field == "meta.usecase_diagram":
                payload["usecase_diagram"] = copy.deepcopy(spec.get("meta", {}).get("usecase_diagram", {}))
            else:
                payload[field] = copy.deepcopy(spec.get(field))
        return payload

    def apply_payload(self, spec: dict, payload: Mapping[str, object]) -> None:
        for field in self.output_fields:
            if field == "meta.usecase_diagram":
                spec.setdefault("meta", {})["usecase_diagram"] = copy.deepcopy(payload.get("usecase_diagram", {}))
            else:
                spec[field] = copy.deepcopy(payload.get(field, []))

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        return


def writer_failure_fallback_spec(
    agent: ChapterAgent,
    spec: dict,
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> dict:
    """Keep generation moving when all retryable writer attempts fail validation."""
    if feedback and getattr(getattr(runtime, "llm_client", None), "writer_mode", "") == "mock":
        target_seed = copy.deepcopy(spec)
        agent.apply(target_seed, runtime)
        normalize_agent_output(target_seed, agent, runtime)
        try:
            agent.validate_payload(target_seed, runtime, agent.extract_payload(target_seed))
            return target_seed
        except Exception:
            pass

    fallback_spec = copy.deepcopy(spec)
    if not feedback:
        agent.apply(fallback_spec, runtime)
    normalize_agent_output(fallback_spec, agent, runtime)
    return fallback_spec


def ensure_full_chapter_payload_shape(agent: ChapterAgent, payload: Mapping[str, object]) -> None:
    if not isinstance(payload, Mapping):
        raise LLMError("챕터 Writer 응답이 JSON 객체가 아닙니다.")
    for field in agent.output_fields:
        key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        value = payload.get(key)
        if key in {"overview", "usecase_diagram"}:
            if not isinstance(value, Mapping):
                raise LLMError(f"챕터 Writer 응답의 {key} 필드는 JSON 객체여야 합니다.")
        elif not isinstance(value, list):
            raise LLMError(f"챕터 Writer 응답의 {key} 필드는 배열이어야 합니다.")


def record_writer_failure_fallback(
    spec: dict,
    agent: ChapterAgent,
    exc: Exception,
    llm_attempt: int,
    max_attempts: int,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> None:
    spec.setdefault("meta", {}).setdefault("writer_fallback_events", []).append(
        {
            "chapter": agent.chapter_key,
            "agent": agent.display_name,
            "llm_attempt": llm_attempt,
            "max_attempts": max_attempts,
            "mode": "preserve_current_payload" if feedback else "local_seed_payload",
            "reason": str(exc)[:500],
        }
    )


class OverviewAgent(ChapterAgent):
    chapter_key = "overview"
    display_name = "Overview Agent"
    output_fields = ("overview",)

    def instruction(self, guideline: dict) -> str:
        return (
            "범위는 대상 업무, 대상 채널, 대상 고객, 포함 범위, 제외 범위, 후속 상세화 영역을 각각 한두 문장으로만 작성하고, "
            "설계 원칙은 4~6개로 제한해 판단축만 제시한다. "
            "주제명과 주제 고유 처리 기준이 범위·원칙에 직접 드러나야 하며, 로그인·상담·주문·결제 등 인접 업무는 포함 여부를 명확히 좁혀 쓴다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["overview"] = copy.deepcopy(runtime.target_spec["overview"])


class TermsAgent(ChapterAgent):
    chapter_key = "terms"
    display_name = "Terms Agent"
    output_fields = ("terms",)

    def instruction(self, guideline: dict) -> str:
        return (
            "용어는 일반 명사가 아니라 이후 상태, 프로세스, 기능, 정책 판단에 직접 쓰이는 기준 용어만 한 문장으로 정의한다. "
            "주제가 여러 의미 축으로 나뉘면 각 축의 판단 용어와 경계 용어를 균형 있게 포함하고, 인접 업무의 계약·주문·혜택·일반 로그인 용어는 현재 주제 판단에 직접 쓰일 때만 둔다. "
            "Blueprint Architect의 작성 전략과 근거 Context에서 반복적으로 등장하는 단위 계층, 대상/자격, 제한 사유, lifecycle 상태, 운영 주기, 재진입/이어하기, 만료/기한, 보상·정산, 이력·감사, 약관·동의 축은 현재 주제 판단에 쓰이면 용어로 먼저 표준화한다. "
            "인증 수단, 로그인 세션, 인증 세션, 재인증, 재진입은 서로 다른 판단축이면 한 용어에 섞지 말고 경계를 분리한다. "
            "가입 동의와 탈퇴 최종 확인·영향 고지는 같은 '약관 동의' 용어로 묶지 말고, 동의/확인/고지의 업무 책임을 구분한다. "
            "탈퇴 차단 사유, 탈퇴 보류, 탈퇴 후 보관 정보는 각각 요청 전 제한, 요청 후 확정 전 대기, 완료 후 보관 기준으로 분리한다. "
            "정책값의 숫자나 허용 범위는 정책 장으로 넘기되, 그 값을 담을 판단축 명칭은 용어 장에서 누락하지 않는다. "
            "상태명으로 이어질 가능성이 큰 제한·불가·보류·완료 용어는 후속 상태명과 같은 표준 명칭을 쓰고, 용어 정의 안에 후속 정책 우선순위나 재사용 판정을 미리 섞지 않는다. "
            "개요에서 쓰는 약어와 판정 표현은 용어 장에서 풀어 쓰거나 개요에서 쉬운 업무명으로 바꿀 수 있게 정렬한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["terms"] = copy.deepcopy(runtime.target_spec["terms"])

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        terms = payload.get("terms", [])
        if not isinstance(terms, list) or not terms:
            raise LLMError("주요 용어 terms가 비어 있습니다.")
        for item in terms:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            joined = f"{name} {description}"
            if "약관 동의" in name and "탈퇴" in description and any(marker in description for marker in ("최종 확인", "영향 고지", "영향 안내")):
                raise LLMError("가입 동의와 탈퇴 최종 확인/영향 고지가 하나의 약관 동의 용어로 섞여 있습니다.")
            if "인증" in name and "로그인 세션" in description and "인증 세션" in description:
                raise LLMError("인증 용어가 로그인 세션과 인증 세션의 판단축을 동시에 포함합니다.")
            if "재인증" in name and "재진입" in description:
                raise LLMError("재인증 용어에 재진입/이어하기 기준이 섞여 있습니다.")
            if "탈퇴 차단" in joined and any(marker in description for marker in ("보류", "보관")):
                raise LLMError("탈퇴 차단 사유 용어에 보류 또는 보관 기준이 섞여 있습니다.")
            if "탈퇴 보류" in joined and any(marker in description for marker in ("차단", "보관")):
                raise LLMError("탈퇴 보류 용어에 차단 또는 보관 기준이 섞여 있습니다.")


class TermsRefinementAgent(ChapterAgent):
    chapter_key = "terms_refinement"
    display_name = "Terms Review Agent"
    output_fields = ("terms",)

    def instruction(self, guideline: dict) -> str:
        return (
            "기능과 정책까지 작성된 전체 문서를 다시 검토해 상태, 권한, 인증, 동의, 제한, 예외, 고지, 이력, BSS 연계처럼 "
            "프로세스·기능·정책 판단에 실제로 쓰인 용어를 주요 용어에 보강한다. 기존 핵심 용어는 유지하고 일반 명사는 추가하지 않는다. "
            "같은 개념이 용어·상태·프로세스에서 다른 이름으로 갈라졌으면 하나의 표준 명칭으로 통일한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["terms"] = refined_terms_from_document(spec, runtime)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        terms = payload.get("terms", [])
        if not isinstance(terms, list) or not terms:
            raise LLMError("용어 재정비 결과 terms가 비어 있습니다.")
        existing_names = {str(item.get("name", "")).strip() for item in spec.get("terms", []) if isinstance(item, dict)}
        new_names = {str(item.get("name", "")).strip() for item in terms if isinstance(item, dict)}
        dropped = sorted(name for name in existing_names if name and name not in new_names)
        if existing_names and len(dropped) > max(2, int(len(existing_names) * 0.35)):
            raise LLMError(f"기존 핵심 용어가 과도하게 삭제되었습니다: {', '.join(dropped[:5])}")
        state_names = [
            str(item.get("name", "")).strip()
            for item in spec.get("states", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]
        if state_names and not any(name in new_names for name in state_names):
            raise LLMError("상태 전이와 정책 판단에 쓰이는 상태 용어가 주요 용어에 반영되지 않았습니다.")


class ActorsAgent(ChapterAgent):
    chapter_key = "actors"
    display_name = "Actors Agent"
    output_fields = ("actors",)

    def instruction(self, guideline: dict) -> str:
        return (
            "액터는 독립 책임 주체와 핵심 책임만 한 문장으로 정의한다. "
            "액터는 보통 고객, 운영자, 상담사, 법정대리인, 대리인, 채널 업무 시스템, 도메인/BSS 연계 시스템처럼 책임 단위로 둔다. "
            "법정대리인/대리인, 발신 고객/수신 고객처럼 여러 사람 주체를 '/'나 '및'으로 묶은 복합 액터명은 쓰지 않는다. 책임이 같으면 하나의 책임명으로 통합하고, 책임이 다르면 별도 액터로 분리한다. "
            "시스템 액터도 BSS/멤버십 연계 시스템, 제휴처/외부 사용처처럼 여러 책임을 '/'로 묶지 말고, 멤버십 연계 시스템이나 외부 사용처처럼 하나의 책임명으로 쓴다. "
            "로그인 고객, 비로그인 고객, 정상 고객, 제한 고객, VIP 고객처럼 고객 상태·등급·권한 차이는 액터가 아니라 상태·조건·정책으로 내려 작성한다. "
            "상품 운영자, 전시 운영자, 쿠폰 운영자, 마케팅 운영자처럼 내부 세부 역할을 액터로 나누지 말고 기본적으로 운영자로 통합한다. "
            "AI 검색 엔진, 추천 엔진, 상품 마스터, 알림센터, 장바구니 시스템 같은 세부 시스템도 독립 액터보다 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합한다. "
            "고객은 요청·입력·확인·동의 주체로, 시스템·기관은 판정·처리·회신 주체로 써서 같은 책임이 중복 수행되는 것처럼 보이지 않게 한다. "
            "채널 업무 시스템은 독립 액터로 둘 수 있지만 대상 채널 자체를 외부 주체처럼 쓰지 않는다. "
            "채널 업무 시스템은 요청 전달, 결과 반영, 화면 분기, 상태·이력 저장을 담당하고 최종 자격·가능 여부 판정은 BSS 또는 해당 연계 주체가 담당하도록 분리한다. "
            "자격·가능 여부·원장 반영 최종 판정은 BSS/인증기관/연계 시스템으로 귀속하고, 채널 업무 시스템은 흐름 제어·요청 전달·결과 표시·상태/이력 기록으로 한정한다. "
            "외부 연계 시스템은 BSS·인증기관이 아닌 보조 조회값, 알림, 동의 확인, 처리 콜백만 담당하도록 제외 책임을 함께 쓴다. "
            "운영자는 기준 관리·예외 처리·사후 확인 주체로 쓰고, 고객 정상 흐름의 개별 승인자처럼 보이지 않게 한다. "
            "트리거·허용 행위·금지 행위·이력 기준은 유즈케이스와 정책 장으로 넘긴다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["actors"] = copy.deepcopy(runtime.target_spec["actors"])

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        actors = payload.get("actors", [])
        if not isinstance(actors, list) or not actors:
            raise LLMError("액터 목록 actors가 비어 있습니다.")
        status_actor_markers = (
            "로그인 고객",
            "비로그인 고객",
            "정상 고객",
            "제한 고객",
            "휴면 고객",
            "미성년 고객",
            "VIP 고객",
            "일반 고객",
        )
        final_decision_markers = ("최종 판정", "자격 판정", "가능 여부 판정", "원장 반영 판정", "승인", "거절", "확정한다")
        delegation_markers = ("BSS", "인증기관", "연계", "회신", "결과를 받아", "판정 결과", "원장")
        if len([item for item in actors if isinstance(item, dict) and str(item.get("name", "")).strip()]) > 8:
            raise LLMError("액터가 8개를 초과해 과분화되었습니다. 책임 단위로 통합한 뒤 유즈케이스/프로세스에서 차이를 표현하세요.")
        for item in actors:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            violation = actor_granularity_violation_reason(name)
            if violation:
                raise LLMError(f"액터 정의가 과분화되었습니다: {name} / {violation}")
            if any(marker == name for marker in status_actor_markers):
                raise LLMError(f"'{name}'은 액터가 아니라 고객 상태/권한 조건입니다.")
            if "채널 업무 시스템" in name:
                has_final_decision = any(marker in description for marker in final_decision_markers)
                has_delegation = any(marker in description for marker in delegation_markers)
                if has_final_decision and not has_delegation:
                    raise LLMError("채널 업무 시스템이 BSS/연계 판정 위임 없이 최종 판정 주체로 작성되었습니다.")


class UsecasesAgent(ChapterAgent):
    chapter_key = "usecases"
    display_name = "Usecases Agent"
    output_fields = ("usecases",)

    def instruction(self, guideline: dict) -> str:
        return (
            "유즈케이스는 고객이 인식하는 완료 목적 단위로 묶고, 설명은 시작 목적과 완료 상태만 짧게 작성한다. "
            "계층 기준은 유즈케이스 → 프로세스 → 기능 → 세부 기능 구성 순서이며, 유즈케이스는 뒤에서 시작·판단·처리·결과 같은 의미 있는 전환점으로 분해 가능한 상위 업무 목표여야 한다. "
            "대상 확인, 조건 확인, 유형 선택, 인증 복귀, 사유 확인, 완료 확인처럼 절차 단계에 가까운 행위는 별도 유즈케이스로 쪼개지 말고 상위 고객 유즈케이스의 프로세스·상태·정책으로 내려 보낸다. "
            "유즈케이스는 고객이 완료하려는 상위 업무 목적 수준이고, 약관 동의·본인인증·정보 입력·결과 안내처럼 반복 절차에 가까운 행위는 프로세스 단계다. "
            "조회, 검증, 산정, 저장, 알림, 연동처럼 처리 역량에 가까운 행위는 유즈케이스가 아니라 후속 기능으로 내려 보낸다. "
            "프로세스 정의 대상은 고객만이 아니라 고객, 운영자, 법정대리인, 대리인, 관리자처럼 사람이 수행하는 액터이면 원칙적으로 Y다. "
            "간소화본 기준으로 process_target=Y 유즈케이스는 보통 고객 3~4개, 운영자 1~2개 수준으로 유지한다. "
            "본인확인·인증번호·재인증처럼 여러 흐름에 걸친 공통 인증 절차와 세션, 알림, 이력은 중복 유즈케이스로 늘리지 말고 보조 유즈케이스 1개로 경계를 고정한다. "
            "단, 작성 주제의 핵심 업무가 인증·연동 권한 확정처럼 고객이 완료해야 하는 상위 업무 목적을 다루는 경우에는 이를 유즈케이스로 허용하고, 본인확인·인증번호 입력·인증 결과 확인 같은 하위 절차만 프로세스로 내린다. "
            "시스템 액터의 검증·조회·회신 유즈케이스는 process_target=N으로 두고, 고객 흐름에 꼭 필요한 공통 통제는 고객 또는 운영자 유즈케이스의 프로세스 안에서 처리한다. "
            "시스템 액터 유즈케이스명은 '[액터명] 지원 처리'처럼 포괄적으로 쓰지 말고, 판정·검증·회신·상태 반영·이력 저장 중 해당 액터가 실제 맡는 책임을 이름에 쓴다. "
            "사람 액터 유즈케이스 설명에는 실제 판정 주체가 필요한 경우 '채널이 BSS/연계 판정 결과를 받아 안내한다'처럼 책임 연결을 짧게 남긴다. "
            "복합 주제는 각 의미 축의 시작 조건과 완료 상태가 유즈케이스명 또는 설명에서 구분되게 작성한다. "
            "모든 유즈케이스 설명은 완결된 문장으로 끝내며, '후', '다음', '통해', '위해'처럼 뒤 문장이 필요한 표현으로 끊지 않는다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["usecases"] = copy.deepcopy(runtime.target_spec["usecases"])

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        actors = {item.get("name") for item in spec.get("actors", []) if isinstance(item, dict)}
        usecases = payload.get("usecases", []) if isinstance(payload.get("usecases"), list) else []
        for usecase in usecases:
            if isinstance(usecase, dict) and usecase.get("actor") not in actors:
                raise LLMError(f"유즈케이스 actor가 액터 목록에 없습니다: {usecase.get('actor')}")
        max_total, max_y = usecase_count_limits(runtime)
        y_usecases = [
            usecase
            for usecase in usecases
            if isinstance(usecase, dict) and str(usecase.get("process_target", "")).strip().upper() == "Y"
        ]
        if len(usecases) > max_total:
            raise LLMError(
                f"유즈케이스가 {len(usecases)}개로 너무 세분화되었습니다. "
                f"{max_total}개 이하로 묶고 절차 단계는 프로세스·상태·정책으로 내려 작성하세요."
            )
        if len(y_usecases) > max_y:
            step_like = [
                str(usecase.get("name", ""))
                for usecase in y_usecases
                if is_step_like_usecase_name(str(usecase.get("name", "")))
            ]
            hint = f" 단계형 유즈케이스 후보: {', '.join(step_like[:6])}" if step_like else ""
            raise LLMError(
                f"프로세스 정의 대상 Y 유즈케이스가 {len(y_usecases)}개로 많습니다. "
                f"{max_y}개 이하의 고객 완결 업무 단위로 묶으세요.{hint}"
            )
        step_like_y = [
            str(usecase.get("name", ""))
            for usecase in y_usecases
            if is_step_like_usecase_name(str(usecase.get("name", "")))
        ]
        if step_like_y:
            raise LLMError(
                "절차 단계가 process_target=Y 유즈케이스로 작성되었습니다. "
                f"다음 항목은 상위 업무 목적 유즈케이스의 프로세스로 내려 작성하세요: {', '.join(step_like_y[:6])}"
            )
        for usecase in y_usecases:
            actor_name = str(usecase.get("actor", "")).strip()
            if is_system_actor_name(actor_name):
                raise LLMError(
                    f"시스템/기관 액터 '{actor_name}'의 유즈케이스는 process_target=N이어야 합니다. 공통 통제는 고객/운영자 프로세스 안에서 처리하세요: {usecase.get('id')}"
                )
        for usecase in usecases:
            if not isinstance(usecase, dict):
                continue
            actor_name = str(usecase.get("actor", "")).strip()
            process_target = str(usecase.get("process_target", "")).strip().upper()
            usecase_name = str(usecase.get("name", "")).strip()
            description = str(usecase.get("description", "")).strip()
            if looks_incomplete_policy_sentence(description):
                raise LLMError(
                    f"유즈케이스 설명이 중간에 끊겼거나 완결 문장이 아닙니다: {usecase.get('id')} / {description}"
                )
            if is_generic_system_usecase(usecase, actor_name):
                raise LLMError(
                    f"시스템 액터 유즈케이스가 포괄명으로 작성되었습니다. 실제 책임이 드러나게 다시 작성하세요: {usecase.get('id')} / {usecase_name}"
                )
            if is_system_actor_name(actor_name) and not has_system_responsibility_marker(f"{usecase_name} {description}"):
                raise LLMError(
                    f"시스템 액터 유즈케이스에 판정·검증·회신·반영 등 실제 책임이 부족합니다: {usecase.get('id')} / {usecase_name}"
                )
            if is_human_actor_name(actor_name) and process_target != "Y":
                raise LLMError(
                    f"사람 액터 '{actor_name}'의 유즈케이스는 process_target=Y여야 합니다: {usecase.get('id')}"
                )


class UsecaseDiagramAgent(ChapterAgent):
    chapter_key = "usecase_diagram"
    display_name = "Usecase Diagram Agent"
    output_fields = ("meta.usecase_diagram",)

    def instruction(self, guideline: dict) -> str:
        return "유즈케이스 다이어그램은 UML 2.0 Use Case Diagram 기준으로 액터, 시스템 경계, 유즈케이스, association 관계가 성립하도록 작성한다."

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        lines = []
        for usecase in spec.get("usecases", []):
            if usecase.get("process_target") == "Y":
                lines.append(f"[{usecase.get('actor', '')}] → ({usecase.get('name', '')})")
        supporting = [
            f"[{usecase.get('actor', '')}] → 지원: {usecase.get('name', '')}"
            for usecase in spec.get("usecases", [])
            if usecase.get("process_target") != "Y"
        ]
        spec.setdefault("meta", {})["usecase_diagram"] = {"lines": lines + supporting}

    def write_with_llm(
        self,
        spec: dict,
        runtime: AgentRuntime,
        feedback: Sequence[Mapping[str, object]] | None = None,
        llm_client: LLMClient | None = None,
    ) -> dict:
        llm_client = llm_client or runtime.llm_client
        if llm_client.writer_mode == "mock":
            local_spec = copy.deepcopy(spec)
            self.apply(local_spec, runtime)
            return self.extract_payload(local_spec)
        return super().write_with_llm(spec, runtime, feedback, llm_client)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        diagram = payload.get("usecase_diagram", {})
        lines = diagram.get("lines", []) if isinstance(diagram, dict) else []
        if not isinstance(lines, list) or not lines:
            raise LLMError("유즈케이스 다이어그램 lines가 비어 있습니다.")


class StateAgent(ChapterAgent):
    chapter_key = "state"
    display_name = "State Agent"
    output_fields = ("states", "state_transitions")

    def instruction(self, guideline: dict) -> str:
        return (
            "상태는 기능 허용과 후속 처리를 바꾸는 값만 작성하고, 상태 정의와 전이 기준은 각각 한 문장으로 작성한다. "
            "상태는 액터와 유즈케이스 관계에서 도출하되, 고객·운영자가 오래 구분해야 하는 업무 상태만 남긴다. "
            "상태 전이 event는 유즈케이스명이 아니라 해당 유즈케이스 흐름에서 실제 상태를 바꾸는 업무 사건으로 쓴다. "
            "유즈케이스 추적성은 event가 아니라 usecase_ids로 보존한다. "
            "프로세스 단계명, 기능명, 세부 기능 구성명, 화면 안내명은 상태명이나 전이 이벤트로 승격하지 않는다. "
            "로그인 세션, 인증 실패, BSS 처리 중, 판정 중처럼 순간적인 처리 단계는 독립 상태로 만들지 말고 전이 criteria, 프로세스, 정책으로 내린다. "
            "같은 의미의 상태명은 하나로 통일하고, 복합 주제에서 완료 결과나 제한 사유가 다르면 구분 기준을 이름 또는 후속 처리에 명시한다. "
            "전이표에는 고객 중단, 인증/연계 실패, 제한, 운영 확인처럼 정상 흐름 밖의 종료 기준도 상태 목록의 실제 명칭으로 연결한다. "
            "각 상태는 선행 유즈케이스나 후속 프로세스에서 참조 가능한 이름을 사용하고, 처리 보류·운영 확인 상태는 후속 처리 주체가 범위 안에 있는지 함께 확인한다. "
            "상태 설명과 전이 기준의 원인 범위는 반드시 일치시킨다. 예를 들어 상태 설명에 권한 부족과 연결 범위 제외를 함께 쓰면 전이표에서도 두 원인이 모두 도달해야 한다. "
            "이전 장에 없는 임시저장, 재개, 운영 처리, 고객별 결과 확정 책임을 새로 가정하지 않는다. 필요한 후속 처리 주체가 없으면 상태를 만들지 말고 제한 사유 안내 또는 후속 확인 안내로 좁힌다. "
            "동일 현재 상태에서 제한·실패·보류·완료 전이가 여러 개로 갈라지면 criteria에 우선순위 또는 배타 조건을 짧게 명시한다. "
            "특히 같은 current_state가 state_transitions에 2회 이상 등장하면 각 행의 criteria에는 '우선순위:' 또는 '배타 조건:' 표현으로 먼저 적용할 조건과 마지막 완료 조건을 명시한다. "
            "간소화본은 개수를 채우는 문서가 아니다. 샘플처럼 미가입, 정상, 휴면, 탈퇴유예, 제한, 완료, 보류처럼 후속 처리 기준이 다른 핵심 상태만 남긴다. "
            "운영 확인·보류처럼 공통 상태를 쓰는 경우에는 진입 원인별 후속 처리 우선순위와 출구 조건을 criteria에 명확히 둔다. "
            "가능 여부, 권한, 제한, 원장 반영처럼 시스템 판정이 필요한 상태는 고객이 판단하는 것처럼 쓰지 말고 BSS·채널 업무 시스템·연계 시스템 중 실제 판정 주체를 적는다. "
            "모든 상태 전이는 usecase_ids로 상태 변경을 발생시키는 승인된 유즈케이스에 연결한다. "
            "usecase_ids는 사람 액터와 시스템 액터를 포함한 모든 액터 유즈케이스를 사용할 수 있지만, 상태를 실제로 바꾸지 않는 유즈케이스를 억지로 포함하지 않는다. "
            "같은 현재 상태·이벤트·다음 상태·기준이 여러 유즈케이스에서 공통으로 발생하면 전이 행을 복제하지 말고 usecase_ids에 여러 ID를 담는다. "
            "조회·판정형 업무는 준비/판정 중 상태에서 결과 상태로 분기하고, 다시 조회나 재판정은 결과 상태끼리 직접 이동하지 말고 판정 중 상태로 되돌린다. "
            "고객이 이미 확인한 결과 상태라도 원천 업무 완료·취소·조건 변경·만료 같은 비동기 변경이 들어오면 시스템/BSS 유즈케이스로 판정 허브에 재진입하거나 완료·무효 상태로 닫는 전이를 둔다. "
            "ID는 id 필드에만 쓰고 description, next_action, event, criteria 문장에는 업무명만 쓴다. "
            "Inspector가 용어·유즈케이스와의 충돌을 지적하면 이전 장을 새로 쓰려 하지 말고, 상태명·상태 설명·전이 기준 안에서 표준명과 원인 범위를 맞춘다."
        )

    def write_with_llm(
        self,
        spec: dict,
        runtime: AgentRuntime,
        feedback: Sequence[Mapping[str, object]] | None = None,
        llm_client: LLMClient | None = None,
    ) -> dict:
        llm_client = llm_client or runtime.llm_client
        current_payload = self.extract_payload(spec)
        has_current_state = bool(current_payload.get("states")) and bool(current_payload.get("state_transitions"))
        if has_current_state and should_use_patch_revision(self, spec, feedback):
            return self.write_patch_revision_with_llm(spec, runtime, feedback or (), llm_client)

        local_spec = copy.deepcopy(spec)
        if has_current_state:
            local_payload = current_payload
        else:
            self.apply(local_spec, runtime)
            local_payload = self.extract_payload(local_spec)
        return llm_client.generate_json(
            schema_name=f"{self.chapter_key}_chapter",
            schema=chapter_output_schema(self),
            instructions=build_system_instructions(runtime, self),
            input_messages=[
                {
                    "role": "user",
                    "content": build_state_focused_prompt(self, spec, local_payload, runtime, feedback),
                }
            ],
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["states"] = copy.deepcopy(runtime.target_spec["states"])
        spec["state_transitions"] = copy.deepcopy(runtime.target_spec["state_transitions"])
        default_usecase_id = default_state_transition_usecase_id(spec)
        if default_usecase_id:
            for transition in spec.get("state_transitions", []):
                if isinstance(transition, dict) and not transition_usecase_ids_value(transition):
                    transition["usecase_ids"] = [default_usecase_id]

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        canonicalize_state_transition_events(spec, payload)
        states = payload.get("states", []) if isinstance(payload.get("states"), list) else []
        transitions = payload.get("state_transitions", []) if isinstance(payload.get("state_transitions"), list) else []
        if not states:
            raise LLMError("상태 코드 목록이 비어 있습니다. 현재 주제의 업무 가능 여부와 후속 처리 기준 상태를 작성하세요.")
        if not transitions:
            raise LLMError("상태 전이표가 비어 있습니다. 각 전이를 관련 usecase_ids에 연결해 작성하세요.")
        max_states, max_transitions = state_count_limits(runtime)
        if len(states) > max_states:
            record_normalization_warning(
                spec,
                self,
                "states",
                "state_count_soft_limit",
                (
                    f"상태가 {len(states)}개로 권장 상한 {max_states}개를 넘었습니다. "
                    "Inspector 단계에서 실제 업무 경계가 아닌 상태만 통합 대상으로 판단합니다."
                ),
            )
        hard_max_transitions = max_transitions + state_transition_overflow_tolerance(runtime)
        if len(transitions) > hard_max_transitions:
            record_normalization_warning(
                spec,
                self,
                "state_transitions",
                "state_transition_count_soft_limit",
                (
                    f"상태 전이가 {len(transitions)}개로 권장 상한 {max_transitions}개를 넘었습니다. "
                    "Inspector 단계에서 같은 후속 처리로 닫히는 사유 분기만 통합 대상으로 판단합니다."
                ),
            )
        for state in states:
            if not isinstance(state, dict):
                continue
            description = str(state.get("description", "")).strip()
            next_action = str(state.get("next_action", "")).strip()
            if looks_incomplete_policy_sentence(description) or looks_incomplete_policy_sentence(next_action):
                record_normalization_warning(
                    spec,
                    self,
                    "states",
                    "state_sentence_needs_review",
                    f"상태 설명 또는 후속 처리가 완결 문장인지 재검토가 필요합니다: {state.get('id')} / {state.get('name')}",
                )
        state_names = {
            str(item.get("name", "")).strip()
            for item in spec.get("states", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }
        state_usecase_lifecycle_errors = state_usecase_lifecycle_errors_for_payload(spec, transitions)
        if state_usecase_lifecycle_errors:
            record_normalization_warning(
                spec,
                self,
                "state_transitions",
                "state_usecase_lifecycle_coverage",
                "유즈케이스 기반 상태 전이 범위 보완이 필요할 수 있습니다.",
                examples=state_usecase_lifecycle_errors,
            )
        state_term_contract_errors = state_term_contract_errors_for_payload(spec, runtime)
        if state_term_contract_errors:
            record_normalization_warning(
                spec,
                self,
                "states",
                "state_term_contract_mismatch",
                "상태 후보 용어와 상태명 정합성 보완이 필요할 수 있습니다.",
                examples=state_term_contract_errors,
            )
        usecases = [item for item in spec.get("usecases", []) if isinstance(item, dict)]
        usecase_ids = {str(item.get("id", "")).strip() for item in usecases if str(item.get("id", "")).strip()}
        transitions = payload.get("state_transitions", [])
        for transition in transitions if isinstance(transitions, list) else []:
            if not isinstance(transition, dict):
                continue
            transition_usecase_ids = transition_usecase_ids_value(transition)
            if not transition_usecase_ids:
                raise LLMError("상태 전이표의 모든 항목에는 상태 변경을 발생시키는 usecase_ids가 필요합니다.")
            invalid = [value for value in transition_usecase_ids if value not in usecase_ids]
            if invalid:
                raise LLMError(f"상태 전이 usecase_ids가 유즈케이스 목록에 없습니다: {', '.join(invalid[:6])}")
            if not str(transition.get("event", "")).strip():
                raise LLMError("상태 전이 event가 비어 있습니다. 상태를 바꾸는 업무 사건을 작성하세요.")
            current_state = str(transition.get("current_state", "")).strip()
            next_state = str(transition.get("next_state", "")).strip()
            if current_state not in state_names or next_state not in state_names:
                raise LLMError("상태 전이표에 상태 목록에 없는 상태명이 있습니다.")
            if transition_mixes_possibility_with_terminal_result(transition):
                record_normalization_warning(
                    spec,
                    self,
                    "state_transitions",
                    "state_transition_decision_result_mixed",
                    (
                        "상태 전이가 가능 여부 판정과 최종 확정 결과를 혼용할 수 있습니다. "
                        "Inspector 단계에서 판정 허브 또는 완료 확정 조건 보완 여부를 판단합니다."
                    ),
                    examples=[f"{current_state}->{next_state}"],
                )
        ambiguous = ambiguous_state_branch_sources(transitions)
        if ambiguous:
            record_normalization_warning(
                spec,
                self,
                "state_transitions",
                "state_transition_branch_priority",
                "같은 현재 상태에서 예외 분기가 여러 개 발생하지만 우선순위 또는 배타 조건이 부족할 수 있습니다.",
                examples=ambiguous,
            )


class ProcessAgent(ChapterAgent):
    chapter_key = "process"
    display_name = "Process Agent"
    output_fields = ("processes",)

    def instruction(self, guideline: dict) -> str:
        return (
            "프로세스는 유즈케이스별 업무 흐름만 작성한다. 관련 기능과 관련 정책은 예측해서 쓰지 않고, "
            "후속 Functions Agent와 Policies Agent 작성 결과를 기준으로 나중에 연결한다. "
            "계층 기준상 프로세스는 상위 유즈케이스를 완료하기 위한 순차 절차이고, 기능처럼 조회·검증·저장 같은 처리 역량만 나열하면 안 된다. "
            "프로세스는 유즈케이스를 완성하는 세부 절차이므로 process_target=Y 유즈케이스를 단일 포괄 프로세스로 끝내지 않는다. 단일 프로세스로만 표현된다면 유즈케이스가 절차 단계처럼 너무 작은지, 아니면 프로세스가 시작·판단·처리·결과를 한 행에 섞었는지 먼저 판단한다. "
            "반대로 한 Y 유즈케이스에 프로세스가 8개 이상 필요하다면 유즈케이스가 너무 넓은지 먼저 점검하고, 고객·운영자의 목표가 달라지는 지점은 별도 유즈케이스로 분리한다. "
            "고객 유즈케이스는 진입/대상 확인, 조건 검증, 입력·인증·동의, 영향도 확인, 처리 요청, 결과 안내 중 실제로 다른 판단이나 후속 상태를 만드는 전환점만 분리한다. "
            "운영자·대리인 등 사람 액터 유즈케이스도 기준 확인, 등록/검토, 승인/반영, 이력/품질 확인 중 실제 책임 경계가 다른 절차만 분리한다. "
            "개수를 맞추기 위해 비슷한 프로세스를 늘리지 말고, 하나의 프로세스 설명 안에 시작·판단·처리·결과가 모두 섞이면 그때만 나눈다. "
            "process_target=Y 유즈케이스는 빠짐없이 프로세스로 이어지고, 설명에는 시작점, 핵심 판단, 예외 또는 완료 기준이 드러나야 한다. "
            "프로세스 설명의 결과 표현은 가능한 한 상태 장의 실제 상태명으로 맞추고, 상태 진입·이탈이 필요한 경우 한 문장 안에 드러낸다. "
            "작성 전 유즈케이스별 skeleton을 내부적으로 먼저 세우고, 각 절차가 승인된 상태명·책임 주체·예외 종료 중 무엇과 연결되는지 확인한 뒤 상세 설명을 작성한다. "
            "상태 장에 없는 완료/보류/제한/실패 표현을 새 상태명처럼 만들지 말고, 필요한 경우 기존 상태명 또는 중립 처리 표현으로 쓴다. "
            "고객 행동과 채널/BSS/인증기관 내부 통제를 같은 프로세스 책임으로 겹쳐 쓰지 않는다. "
            "BPMN 2.0 Process Diagram으로 전환될 수 있도록 시작, 태스크, 조건 판단, 예외/제한, 종료 흐름은 드러나야 한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["processes"] = []
        ensure_process_usecase_coverage(spec, runtime)
        ensure_target_requirement_process_coverage(spec, runtime)
        clear_deferred_process_links(spec)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        usecase_ids = {item.get("id") for item in spec.get("usecases", []) if isinstance(item, dict)}
        processes = payload.get("processes", [])
        for process in processes if isinstance(processes, list) else []:
            if not isinstance(process, dict):
                continue
            if process.get("usecase_id") not in usecase_ids:
                raise LLMError(f"프로세스 usecase_id가 유즈케이스 목록에 없습니다: {process.get('usecase_id')}")
        y_usecases = [
            item
            for item in spec.get("usecases", [])
            if isinstance(item, dict) and str(item.get("process_target", "")).strip().upper() == "Y"
        ]
        process_count_by_usecase: dict[str, int] = {}
        for process in processes if isinstance(processes, list) else []:
            if not isinstance(process, dict):
                continue
            usecase_id = str(process.get("usecase_id", "")).strip()
            process_count_by_usecase[usecase_id] = process_count_by_usecase.get(usecase_id, 0) + 1
        density_profile = density_profile_for_runtime(runtime)
        thin_usecases = [
            f"{usecase.get('id', '')}({usecase.get('name', '')}:{process_count_by_usecase.get(str(usecase.get('id', '')).strip(), 0)}개)"
            for usecase in y_usecases
            if (
                process_count_by_usecase.get(str(usecase.get("id", "")).strip(), 0)
                < minimum_process_count_for_usecase(usecase, density_profile)
            )
        ]
        if thin_usecases:
            raise LLMError(
                "프로세스가 유즈케이스를 완성하는 세부 절차로 충분히 분해되지 않았습니다. "
                "사람 액터 Y 유즈케이스가 1개 프로세스로만 끝나면 유즈케이스가 너무 작은 절차 단계인지 먼저 점검하고, 상위 업무 목표가 맞다면 실제로 다른 판단·처리·결과 경계를 갖는 전환점으로만 분해하세요: "
                + ", ".join(thin_usecases[:8])
            )
        overwide_usecases = [
            f"{usecase.get('id', '')}({usecase.get('name', '')}:{process_count_by_usecase.get(str(usecase.get('id', '')).strip(), 0)}개)"
            for usecase in y_usecases
            if process_count_by_usecase.get(str(usecase.get("id", "")).strip(), 0) > MAX_PROCESSES_PER_Y_USECASE
        ]
        if overwide_usecases:
            raise LLMError(
                "프로세스가 특정 Y 유즈케이스에 과도하게 집중되었습니다. "
                "절차 단계로 쪼개지는 것은 피하되, 고객·운영자의 목표가 실제로 달라지는 지점은 별도 유즈케이스로 분리한 뒤 프로세스를 다시 배분하세요: "
                + ", ".join(overwide_usecases[:8])
            )


class FunctionsAgent(ChapterAgent):
    chapter_key = "functions"
    display_name = "Functions Agent"
    output_fields = ("functions",)

    def instruction(self, guideline: dict) -> str:
        return (
            "기능은 화면 단위나 프로세스 1:1 복사가 아니라 조회, 검증, 산정, 저장, 연동, 모니터링 같은 처리 역량 단위로 묶는다. "
            "각 기능은 대표 process_id와 연결 대상 process_ids를 유지하고, 작성 후 프로세스 목록의 관련 기능은 기능 ID와 기능명으로 자동 업데이트된다. "
            "앞 단계 프로세스의 시작·판단·예외·완료 흐름을 수행할 수 있도록 기능 누락을 막되, 같은 세부 기능 묶음을 반복 복제하지 않는다. "
            "프로세스별 기능이 모두 1개씩만 붙는 구조는 피하고, 검증·판정·저장·알림·연동·이력처럼 서로 다른 처리 책임은 필요한 프로세스에 복수 기능으로 연결한다. "
            "본인인증, 약관 동의, 이력 저장, 알림 발송, 상태 조회처럼 여러 프로세스에서 재사용되는 기능은 하나의 기능 ID를 여러 process_ids에 연결한다. "
            "판정 기능은 진행 가능 여부와 최소 결과값 확정으로, 안내 기능은 이미 확정된 결과의 고객 고지와 후속 조치 변환으로 책임을 분리한다. "
            "외부 인증 호출·결과 수신과 세션 유효성·재인증 기준·상태 저장을 한 기능에 섞어 쓰지 않는다. "
            "세부 기능 구성(details)은 샘플처럼 '통합 검색창 제공', '입력값 정규화' 같은 짧은 하위 처리명으로만 작성하고, "
            "'...한다'로 끝나는 설명문이나 정책 판단 기준을 넣지 않는다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["functions"] = []
        ensure_target_requirement_function_coverage(spec, runtime)
        ensure_function_process_coverage(spec)
        if getattr(getattr(runtime, "llm_client", None), "writer_mode", "") == "mock":
            ensure_mock_function_density_coverage(spec)
        deduplicate_function_names(spec)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        process_ids = {item.get("id") for item in spec.get("processes", []) if isinstance(item, dict)}
        functions = payload.get("functions", [])
        detail_signatures = []
        for function in functions if isinstance(functions, list) else []:
            if not isinstance(function, dict):
                continue
            linked_process_ids = function_linked_process_ids(function)
            if not linked_process_ids:
                raise LLMError(f"기능 process_id/process_ids가 비어 있습니다: {function.get('id')}")
            for process_id in linked_process_ids:
                if process_id not in process_ids:
                    raise LLMError(f"기능 process_id가 프로세스 목록에 없습니다: {function.get('id')} / {process_id}")
            details = tuple(str(item).strip() for item in function.get("details", []) if str(item).strip())
            if details:
                detail_signatures.append(details)
        if len(functions) >= 10 and detail_signatures:
            repeated = max(detail_signatures.count(signature) for signature in set(detail_signatures))
            if repeated >= max(5, int(len(functions) * 0.30)):
                raise LLMError("동일한 기능 세부 구성이 과도하게 반복되었습니다.")
        sentence_like: List[str] = []
        if isinstance(functions, list):
            for function in functions:
                if not isinstance(function, dict):
                    continue
                sentence_like.extend(
                    str(detail).strip()
                    for detail in function.get("details", [])
                    if function_detail_label_is_sentence_like(detail)
                )
        if sentence_like and len(sentence_like) >= max(4, int(max(1, len(functions)) * 0.4)):
            raise LLMError(
                "기능 세부 구성은 문장형 설명이 아니라 샘플처럼 짧은 하위 처리명으로 작성해야 합니다. "
                "예: '조회 조건 구성', '권한 상태 검증', '결과 안내 구성'."
            )
        granularity_error = function_granularity_error(spec.get("processes", []), functions)
        if granularity_error:
            raise LLMError(granularity_error)


class ProcessDetailAgent(ChapterAgent):
    chapter_key = "process_detail"
    display_name = "Process Detail Agent"
    output_fields = ("process_details",)

    def instruction(self, guideline: dict) -> str:
        return (
            "Full 버전 전용으로 프로세스 목록의 각 프로세스가 어떤 고객/시스템 상태에서 시작되고 어떤 결과가 확정되면 끝나는지 작성한다. "
            "프로세스 상세는 이미 확정된 유즈케이스-프로세스 계층을 설명하는 장이며, 기능 상세나 정책값을 새로 작성하는 장이 아니다. "
            "프로세스 ID는 그대로 유지하고, 진입 조건, 종료 조건, 선행 프로세스, 후행 프로세스, 관련 기능, 관련 정책을 프로세스별로 채운다. "
            "진입 조건은 고객 상태, 시스템 상태, 선행 처리 결과 중 실제 시작 기준을 한 문장으로 쓴다. "
            "종료 조건은 완료, 제한, 실패, 보류, 후속 연결 중 무엇이 확정되어야 종료되는지 한 문장으로 쓴다. "
            "선행·후행 프로세스는 같은 유즈케이스의 실제 프로세스 ID와 명칭을 우선 사용한다. "
            "관련 기능과 관련 정책은 이미 작성된 기능 목록과 정책 목록의 ID·명칭을 그대로 참조하고 새 기능·정책을 만들지 않는다. "
            "샘플 Full 문서처럼 짧고 명확하게 쓰되, 단순히 프로세스명을 반복하는 일반 문장이나 모든 행에 같은 조건을 복사하지 않는다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["process_details"] = build_process_detail_rows(spec)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        process_ids = {str(item.get("id", "")).strip() for item in spec.get("processes", []) if isinstance(item, dict)}
        process_names_by_id = {
            str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
            for item in spec.get("processes", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        function_names_by_id = {
            str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
            for item in spec.get("functions", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        policy_names_by_id = {
            str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
            for item in spec.get("policy_groups", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        rows = payload.get("process_details", [])
        if not isinstance(rows, list):
            raise LLMError("process_details는 배열이어야 합니다.")
        detail_ids = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            process_id = str(row.get("process_id", "")).strip()
            if process_id not in process_ids:
                raise LLMError(f"프로세스 상세 process_id가 프로세스 목록에 없습니다: {process_id}")
            detail_ids.add(process_id)
            for field in ("entry_condition", "exit_condition"):
                if not str(row.get(field, "")).strip():
                    raise LLMError(f"프로세스 상세 {field}가 비어 있습니다: {process_id}")
            if normalize_space(row.get("entry_condition", "")) == normalize_space(row.get("exit_condition", "")):
                raise LLMError(f"프로세스 상세 진입 조건과 종료 조건이 동일합니다: {process_id}")
            for field in ("previous_processes", "next_processes", "related_functions", "related_policies"):
                if not isinstance(row.get(field), list) or not any(str(item).strip() for item in row.get(field, [])):
                    raise LLMError(f"프로세스 상세 {field}는 비어 있지 않은 배열이어야 합니다: {process_id}")
            for error in validate_process_flow_references(row.get("previous_processes", []), process_ids, process_names_by_id, "선행 프로세스", process_id):
                raise LLMError(error)
            for error in validate_process_flow_references(row.get("next_processes", []), process_ids, process_names_by_id, "후행 프로세스", process_id):
                raise LLMError(error)
            for error in validate_named_references(row.get("related_functions", []), function_names_by_id, split_function_reference, "관련 기능", process_id):
                raise LLMError(error)
            for error in validate_named_references(row.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", process_id):
                raise LLMError(error)
        missing = sorted(process_ids - detail_ids)
        if missing:
            raise LLMError("프로세스 상세가 누락된 프로세스가 있습니다: " + ", ".join(missing[:8]))


class FunctionDetailAgent(ChapterAgent):
    chapter_key = "function_detail"
    display_name = "Function Detail Agent"
    output_fields = ("function_details",)

    def instruction(self, guideline: dict) -> str:
        return (
            "Full 버전 전용으로 기능 목록의 각 기능을 상세 설계 입력으로 확장한다. "
            "기능 상세는 기능 아래의 세부 처리 구성만 확장하며, 새로운 유즈케이스나 프로세스를 만들거나 프로세스 순서를 다시 정의하지 않는다. "
            "기능 ID와 process_id/process_ids는 변경하지 않고, 입력 정보, 처리 로직, 세부 기능 구성, 출력 정보, 실패·예외 케이스, 관련 정책을 작성한다. "
            "입력 정보는 고객 입력값, 시스템 조회값, 외부 연계 결과, 채널·세션·기준일시 중 실제 처리에 필요한 값만 쓴다. "
            "처리 로직은 샘플처럼 각 줄을 반드시 '(상태) ... → (액션) ... → (결과) ...' 구조로 쓰고 정상, 분기, 예외를 구분한다. "
            "'(정상)', '(분기)', '(예외)'만 붙인 설명문은 처리 로직으로 쓰지 않는다. "
            "출력 정보는 화면 표시값, 저장 결과, 연계 회신, 고객 안내 중 기능이 만드는 결과를 쓴다. "
            "실패·예외 케이스에는 고객 안내, 재시도, 중단, 상담 전환, 이력 저장 기준을 함께 남긴다. "
            "정책값은 기능 상세에 직접 풀어쓰지 말고 관련 정책 ID·정책명으로 연결한다. "
            "API 필드, DB 컬럼, 화면 상세는 제외하고 구현자가 처리 책임과 예외 기준을 이해할 수 있는 수준으로만 작성한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["function_details"] = build_function_detail_rows(spec)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        function_ids = {str(item.get("id", "")).strip() for item in spec.get("functions", []) if isinstance(item, dict)}
        policy_names_by_id = {
            str(item.get("id", "")).strip(): str(item.get("name", "")).strip()
            for item in spec.get("policy_groups", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        rows = payload.get("function_details", [])
        if not isinstance(rows, list):
            raise LLMError("function_details는 배열이어야 합니다.")
        detail_ids = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            function_id = str(row.get("function_id", "")).strip()
            if function_id not in function_ids:
                raise LLMError(f"기능 상세 function_id가 기능 목록에 없습니다: {function_id}")
            detail_ids.add(function_id)
            for field in (
                "input_information",
                "processing_logic",
                "sub_functions",
                "output_information",
                "failure_exception_cases",
                "related_policies",
            ):
                if not isinstance(row.get(field), list) or not any(str(item).strip() for item in row.get(field, [])):
                    raise LLMError(f"기능 상세 {field}가 비어 있습니다: {function_id}")
            processing_logic = [str(item).strip() for item in row.get("processing_logic", []) if str(item).strip()]
            if len(processing_logic) < 3:
                raise LLMError(f"기능 상세 processing_logic은 정상·분기·예외를 구분하도록 최소 3개 이상 작성해야 합니다: {function_id}")
            for logic in processing_logic:
                if not function_processing_logic_is_state_action_result(logic):
                    raise LLMError(
                        "기능 상세 processing_logic은 샘플처럼 "
                        f"'(상태) ... → (액션) ... → (결과) ...' 형식이어야 합니다: {function_id}"
                    )
            for error in validate_named_references(row.get("related_policies", []), policy_names_by_id, split_policy_reference, "관련 정책", function_id):
                raise LLMError(error)
        missing = sorted(function_ids - detail_ids)
        if missing:
            raise LLMError("기능 상세가 누락된 기능이 있습니다: " + ", ".join(missing[:8]))


class PoliciesAgent(ChapterAgent):
    chapter_key = "policies"
    display_name = "Policies Agent"
    output_fields = ("policy_groups", "policy_details")

    def instruction(self, guideline: dict) -> str:
        return (
            "정책은 일반 원칙이 아니라 기능이 실제로 동작하기 위해 필요한 값·조건·허용 범위·제한 기준이다. "
            "먼저 프로세스와 기능을 기준으로 필요한 정책을 정의하고, 다음으로 정책을 구성하는 세부 항목을 정의한 뒤, 마지막으로 각 항목별 값을 작성한다. "
            "정책은 유즈케이스·프로세스·기능 계층을 다시 쪼개는 장이 아니라, 기능 수행 중 결정해야 하는 값과 제한 기준을 선언하는 장이다. "
            "샘플처럼 정책 그룹 아래 정책 항목을 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 노출 채널, 제한 기간, 저장 항목 같은 실제 동작값 단위로 선언한다. "
            "정책 상세는 정책 그룹(policy_id)에만 연결하고, 프로세스 목록의 관련 정책은 정책 목록의 정책 ID와 정책명 기준으로 자동 업데이트된다. "
            "정책 상세는 고정 슬롯을 나열하지 말고 정책 항목명과 정책 내용만으로 적용값, 제한값, 예외값, 고지·이력 기준을 짧게 선언한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["policy_groups"] = copy.deepcopy(runtime.target_spec["policy_groups"])
        spec["policy_details"] = copy.deepcopy(runtime.target_spec["policy_details"])
        strip_policy_detail_process_ids(spec)
        normalize_policy_details(spec)

    def validate_payload(self, spec: dict, runtime: AgentRuntime, payload: Mapping[str, object]) -> None:
        policy_groups = payload.get("policy_groups", [])
        policy_details = payload.get("policy_details", [])
        policy_ids = {item.get("id") for item in policy_groups if isinstance(item, dict)}
        for detail in policy_details if isinstance(policy_details, list) else []:
            if not isinstance(detail, dict):
                continue
            if detail.get("policy_id") not in policy_ids:
                raise LLMError(f"정책 상세 policy_id가 정책 그룹에 없습니다: {detail.get('policy_id')}")
            if any(key in detail for key in ("process_id", "process_ids", "applicable_processes")):
                raise LLMError(f"정책 상세에는 프로세스 직접 매핑 필드를 작성하지 않습니다: {detail.get('id')}")


class FinalCheckAgent(ChapterAgent):
    chapter_key = "final_check"
    display_name = "Final Check Agent"
    output_fields = ("final_check",)

    def instruction(self, guideline: dict) -> str:
        return (
            "최종 점검은 제출 전 확인할 항목명을 짧게 나열하고, 점검 설명은 한 문장으로 작성한다. "
            "유즈케이스 → 프로세스 → 기능 → 세부 기능 구성 → 정책값으로 이어지는 계층이 끊기거나 서로 같은 입자로 반복되지 않는지 확인 항목에 포함한다. "
            "HTML, spec, BPMN, 요구사항 Trace가 같은 버전과 ID 기준으로 동기화되는지도 포함한다."
        )

    def apply(self, spec: dict, runtime: AgentRuntime) -> None:
        spec["final_check"] = copy.deepcopy(runtime.target_spec["final_check"])


def build_policy_spec_with_chapter_agents(
    ctx,
    template_html: str,
    sample_htmls: Sequence[str],
    after_stage=None,
) -> dict:
    """Backward-compatible wrapper around the dedicated orchestrator."""
    try:
        from orchestrator import orchestrate_policy_generation
    except ImportError:  # pragma: no cover - package import fallback.
        from .orchestrator import orchestrate_policy_generation

    return orchestrate_policy_generation(ctx, template_html, sample_htmls, after_stage=after_stage)


def emit_progress(ctx, event: str, **payload: object) -> None:
    callback = getattr(ctx, "progress_callback", None)
    if not callable(callback):
        return
    callback(event, payload)


def request_manual_stage_review(ctx, stage: ChapterStage, attempt: int, gate_result: Mapping[str, object]) -> Mapping[str, object]:
    if getattr(ctx, "review_mode", "auto") != "manual":
        return {"action": "continue"}
    callback = getattr(ctx, "manual_review_callback", None)
    if not callable(callback):
        return {"action": "continue"}
    decision = callback(
        {
            "stage_key": stage.key,
            "stage_name": stage.name,
            "stage_label": stage.agent.display_name,
            "attempt": attempt,
            "score": gate_result.get("score"),
            "threshold": gate_result.get("threshold"),
            "passed": gate_result.get("passed", True),
            "artifact": gate_result.get("artifact"),
            "preview": gate_result.get("preview"),
            "message": (
                f"{stage.agent.display_name} 결과 HTML을 확인한 뒤 다음 단계 진행 또는 보완 요청을 선택해 주세요."
            ),
        }
    )
    return decision if isinstance(decision, Mapping) else {"action": "continue"}


def manual_revision_requested(decision: Mapping[str, object]) -> bool:
    return str(decision.get("action", "")).strip().casefold() == "revise"


def manual_review_feedback(decision: Mapping[str, object]) -> List[Mapping[str, object]]:
    instruction = str(decision.get("instruction", "")).strip()
    if not instruction:
        instruction = "사용자 검수 결과에 따라 현재 챕터를 더 구체적으로 보완한다."
    return [
        {
            "severity": "manual",
            "category": "사용자 검수",
            "title": "사용자 보완 요청",
            "detail": instruction,
            "recommendation": instruction,
        }
    ]


def initialize_spec(ctx, learning: dict, guideline: dict) -> dict:
    meta = build_base_meta(ctx)
    meta["topic_learning"] = learning
    meta["chapter_agent_guideline"] = guideline
    meta["chapter_agents"] = [
        {
            "chapter": stage.agent.chapter_key,
            "agent": stage.agent.display_name,
            "instruction": stage.agent.instruction(guideline),
        }
        for stage in chapter_stages(getattr(ctx, "template_type", ""))
    ]
    return {
        "meta": meta,
        "history": build_history(ctx, "챕터별 전문 agent가 주제 학습 후 순차 작성한다."),
        "overview": {"scope": [], "principles": []},
        "terms": [],
        "actors": [],
        "usecases": [],
        "states": [],
        "state_transitions": [],
        "processes": [],
        "process_details": [],
        "functions": [],
        "function_details": [],
        "policy_groups": [],
        "policy_details": [],
        "final_check": [],
        "trace_matrix": [],
        "evidence_gaps": [],
    }


CONTEXT_PACK_CACHE_VERSION = "context-pack-v8-requirement-level-pdf"
CONTEXT_PACK_CACHE: dict[str, dict] = {}


def record_context_pack(spec: dict, agent: ChapterAgent, runtime: AgentRuntime) -> None:
    context_pack = context_pack_for_agent(
        agent.chapter_key,
        spec,
        runtime,
        limit=14,
    )
    update_traceability(spec, agent.chapter_key, context_pack)


def context_pack_for_agent(agent_key: str, spec: Mapping[str, object], runtime: AgentRuntime, *, limit: int) -> dict:
    key = context_pack_cache_key(agent_key, spec, runtime, limit)
    cached = CONTEXT_PACK_CACHE.get(key)
    if cached is None:
        cached = assemble_context_pack(
            agent_key=agent_key,
            spec=spec,
            evidence_store=runtime.evidence_store,
            topic=runtime.ctx.topic,
            learning=runtime.learning,
            limit=limit,
        )
        if len(CONTEXT_PACK_CACHE) > 80:
            CONTEXT_PACK_CACHE.clear()
        CONTEXT_PACK_CACHE[key] = copy.deepcopy(cached)
    return copy.deepcopy(cached)


def context_pack_cache_key(agent_key: str, spec: Mapping[str, object], runtime: AgentRuntime, limit: int) -> str:
    payload = {
        "cache_version": CONTEXT_PACK_CACHE_VERSION,
        "agent_key": agent_key,
        "topic": getattr(runtime.ctx, "topic", ""),
        "business_code": getattr(runtime.ctx, "business_code", ""),
        "limit": limit,
        "evidence_store": runtime.evidence_store.summary() if getattr(runtime, "evidence_store", None) else {},
        "content_fingerprint": spec_context_fingerprint_for_cache(agent_key, spec, runtime.learning),
        "counts": {
            key: len(spec.get(key, [])) if isinstance(spec.get(key), list) else 0
            for key in (
                "terms",
                "actors",
                "usecases",
                "states",
                "state_transitions",
                "processes",
                "process_details",
                "functions",
                "function_details",
                "policy_groups",
                "policy_details",
            )
        },
        "ids": {
            key: [
                str(item.get("id") or item.get("process_id") or item.get("function_id") or "").strip()
                for item in spec.get(key, [])[:120]
                if isinstance(item, Mapping)
                and str(item.get("id") or item.get("process_id") or item.get("function_id") or "").strip()
            ]
            for key in (
                "actors",
                "usecases",
                "states",
                "processes",
                "process_details",
                "functions",
                "function_details",
                "policy_groups",
                "policy_details",
            )
            if isinstance(spec.get(key), list)
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def spec_context_fingerprint_for_cache(
    agent_key: str,
    spec: Mapping[str, object],
    learning: Mapping[str, object],
) -> str:
    """Make context-pack caching sensitive to meaning changes, not only IDs."""
    payload = {
        "agent_key": agent_key,
        "overview": cache_value(spec.get("overview", {})),
        "sections": {
            key: cache_value(spec.get(key, []))
            for key in (
                "terms",
                "actors",
                "usecases",
                "states",
                "state_transitions",
                "processes",
                "process_details",
                "functions",
                "function_details",
                "policy_groups",
                "policy_details",
                "final_check",
            )
        },
        "usecase_diagram": cache_value(spec.get("meta", {}).get("usecase_diagram", {}) if isinstance(spec.get("meta"), Mapping) else {}),
        "learning": {
            key: cache_value(learning.get(key, []))
            for key in ("customer_tasks", "policy_risks", "bss_implications", "decision_axes")
            if isinstance(learning, Mapping)
        },
    }
    return stable_cache_hash(payload)


def cache_value(value: object):
    if isinstance(value, Mapping):
        return {
            str(key): cache_value(inner)
            for key, inner in value.items()
            if str(key) in {
                "id",
                "code",
                "name",
                "description",
                "actor",
                "usecase_id",
                "process_id",
                "function_id",
                "policy_id",
                "process_target",
                "current_state",
                "next_state",
                "event",
                "criteria",
                "content",
                "details",
                "entry_condition",
                "exit_condition",
                "previous_processes",
                "next_processes",
                "input_information",
                "processing_logic",
                "sub_functions",
                "output_information",
                "failure_exception_cases",
                "scope",
                "principles",
                "lines",
                "related_functions",
                "related_policies",
                "next_action",
            }
        }
    if isinstance(value, list):
        return [cache_value(item) for item in value[:160]]
    if isinstance(value, tuple):
        return [cache_value(item) for item in value[:160]]
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def stable_cache_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def chapter_stages(template_type: str | None = None) -> List[ChapterStage]:
    stages = [
        ChapterStage("01", "overview", "01_overview", OverviewAgent()),
        ChapterStage("02", "terms", "02_terms", TermsAgent()),
        ChapterStage("03", "actors", "03_actors", ActorsAgent()),
        ChapterStage("04", "usecases", "04_usecases", UsecasesAgent()),
        ChapterStage("05", "usecase_diagram", "05_usecase_diagram", UsecaseDiagramAgent()),
        ChapterStage("06", "state", "06_state", StateAgent()),
        ChapterStage("07", "process", "07_process", ProcessAgent()),
        ChapterStage("08", "functions", "08_functions", FunctionsAgent()),
        ChapterStage("09", "policies", "09_policies", PoliciesAgent()),
    ]
    if str(template_type or "").strip().casefold() == "full":
        stages.extend(
            [
                ChapterStage("09_process_detail", "process_detail", "09_process_detail", ProcessDetailAgent()),
                ChapterStage("09_function_detail", "function_detail", "09_function_detail", FunctionDetailAgent()),
            ]
        )
    stages.extend(
        [
            ChapterStage("09_terms_refinement", "terms_refinement", "09_terms_refinement", TermsRefinementAgent()),
            ChapterStage("10", "final_check", "10_final_check", FinalCheckAgent()),
        ]
    )
    return stages


def build_process_detail_rows(spec: Mapping[str, object]) -> List[dict]:
    processes = [item for item in spec.get("processes", []) if isinstance(item, Mapping)]
    grouped: dict[str, List[Mapping[str, object]]] = {}
    for process in processes:
        grouped.setdefault(str(process.get("usecase_id", "")).strip(), []).append(process)
    rows: List[dict] = []
    for group in grouped.values():
        for index, process in enumerate(group):
            process_id = str(process.get("id", "")).strip()
            process_name = str(process.get("name", "")).strip()
            previous_process = group[index - 1] if index > 0 else None
            next_process = group[index + 1] if index + 1 < len(group) else None
            rows.append(
                {
                    "process_id": process_id,
                    "entry_condition": default_process_entry_condition(process, previous_process),
                    "exit_condition": default_process_exit_condition(process, next_process),
                    "previous_processes": [process_ref(previous_process)] if previous_process else ["업무 진입 조건 충족"],
                    "next_processes": [process_ref(next_process)] if next_process else ["결과 안내 또는 후속 업무 연결"],
                    "related_functions": unique_nonempty(process.get("related_functions", [])),
                    "related_policies": unique_nonempty(process.get("related_policies", [])),
                }
            )
            if process_name and not rows[-1]["entry_condition"]:
                rows[-1]["entry_condition"] = f"{process_name} 수행에 필요한 선행 확인이 완료된 경우 진입한다."
    return rows


def default_process_entry_condition(process: Mapping[str, object], previous_process: Mapping[str, object] | None) -> str:
    name = str(process.get("name", "")).strip()
    if previous_process:
        return f"{previous_process.get('name', '')} 결과가 확인되어 {name} 처리가 필요한 경우 진입한다."
    return f"고객 또는 운영자가 {name} 업무를 시작할 수 있는 기본 조건을 충족한 경우 진입한다."


def default_process_exit_condition(process: Mapping[str, object], next_process: Mapping[str, object] | None) -> str:
    name = str(process.get("name", "")).strip()
    if next_process:
        return f"{name}의 판단 결과가 확정되어 {next_process.get('name', '')}로 넘길 수 있으면 종료한다."
    return f"{name} 결과가 완료, 제한, 실패, 보류 중 하나로 확정되고 안내 또는 이력이 남으면 종료한다."


def process_ref(process: Mapping[str, object] | None) -> str:
    if not isinstance(process, Mapping):
        return ""
    return " ".join(
        item
        for item in (
            str(process.get("id", "")).strip(),
            str(process.get("name", "")).strip(),
        )
        if item
    )


def build_function_detail_rows(spec: Mapping[str, object]) -> List[dict]:
    processes_by_id = {
        str(process.get("id", "")).strip(): process
        for process in spec.get("processes", [])
        if isinstance(process, Mapping) and str(process.get("id", "")).strip()
    }
    rows: List[dict] = []
    for function in spec.get("functions", []):
        if not isinstance(function, Mapping):
            continue
        function_id = str(function.get("id", "")).strip()
        function_name = str(function.get("name", "")).strip()
        linked_process_ids = function_linked_process_ids(function)
        linked_processes = [
            processes_by_id[process_id]
            for process_id in linked_process_ids
            if process_id in processes_by_id
        ]
        process = linked_processes[0] if linked_processes else {}
        related_policies = unique_nonempty(
            policy_ref
            for linked_process in linked_processes
            for policy_ref in (
                linked_process.get("related_policies", [])
                if isinstance(linked_process.get("related_policies", []), list)
                else []
            )
        )
        rows.append(
            {
                "function_id": function_id,
                "input_information": default_function_inputs(function, process),
                "processing_logic": default_function_processing_logic(function, process),
                "sub_functions": unique_nonempty(function.get("details", []))[:6] or [function_name],
                "output_information": default_function_outputs(function, process),
                "failure_exception_cases": default_function_exceptions(function, process),
                "related_policies": related_policies or ["정책 목록 작성 결과 기준으로 연결"],
            }
        )
    return rows


def default_function_inputs(function: Mapping[str, object], process: Mapping[str, object]) -> List[str]:
    process_name = str(process.get("name", "")).strip()
    return unique_nonempty(
        [
            "고객 또는 운영자 요청 정보",
            f"{process_name} 수행에 필요한 상태·권한 정보" if process_name else "업무 수행에 필요한 상태·권한 정보",
            "BSS 또는 연계 시스템 기준 정보",
        ]
    )


def default_function_processing_logic(function: Mapping[str, object], process: Mapping[str, object]) -> List[str]:
    name = str(function.get("name", "")).strip()
    process_name = str(process.get("name", "")).strip()
    process_label = process_name or "관련 프로세스"
    function_label = name or "기능"
    return unique_nonempty(
        [
            f"(상태) {process_label} 진입 → (액션) {function_label} 처리 대상을 확인 → (결과) 처리 대상 확정",
            f"(상태) 기준 정보 확인 완료 → (액션) 허용·제한·보류 여부 판정 → (결과) 후속 처리 상태 결정",
            "(상태) 연계 실패 또는 예외 발생 → (액션) 실패 사유 분류와 재시도 가능 여부 확인 → (결과) 고객 안내·상담 전환·이력 저장 대상 생성",
        ]
    )


def function_processing_logic_is_state_action_result(value: object) -> bool:
    return bool(FUNCTION_PROCESSING_LOGIC_PATTERN.search(" ".join(str(value or "").split())))


def default_function_outputs(function: Mapping[str, object], process: Mapping[str, object]) -> List[str]:
    name = str(function.get("name", "")).strip() or str(function.get("id", "")).strip() or "기능"
    process_name = str(process.get("name", "")).strip()
    process_label = f"{process_name} 기준" if process_name else "관련 프로세스 기준"
    return unique_nonempty(
        [
            f"{name}의 처리 가능 여부와 {process_label} 판정 결과",
            f"{name} 완료 후 고객 안내 또는 후속 처리 메시지 기준",
            f"{name} 수행 결과의 이력 저장 대상과 연계 회신 결과",
        ]
    )


def default_function_exceptions(function: Mapping[str, object], process: Mapping[str, object]) -> List[str]:
    name = str(function.get("name", "")).strip() or str(function.get("id", "")).strip() or "기능"
    process_name = str(process.get("name", "")).strip()
    process_label = process_name or "관련 프로세스"
    return unique_nonempty(
        [
            f"{name} 중 권한 또는 상태 조건이 {process_label} 기준과 맞지 않으면 제한 결과로 반환한다.",
            f"{name}에 필요한 BSS·연계 응답이 지연되면 보류 또는 재시도 기준으로 전환한다.",
            f"{name} 반복 실패 또는 고객 피해 가능성이 있으면 상담 전환 대상으로 분류하고 이력을 저장한다.",
        ]
    )


def ensure_process_detail_coverage(spec: dict) -> None:
    existing = {
        str(detail.get("process_id", "")).strip(): detail
        for detail in spec.get("process_details", [])
        if isinstance(detail, dict) and str(detail.get("process_id", "")).strip()
    }
    for fallback in build_process_detail_rows(spec):
        process_id = str(fallback.get("process_id", "")).strip()
        if not process_id:
            continue
        existing.setdefault(process_id, fallback)
    spec["process_details"] = [copy.deepcopy(existing[str(process.get("id", "")).strip()]) for process in spec.get("processes", []) if isinstance(process, dict) and str(process.get("id", "")).strip() in existing]


def ensure_function_detail_coverage(spec: dict) -> None:
    existing = {
        str(detail.get("function_id", "")).strip(): detail
        for detail in spec.get("function_details", [])
        if isinstance(detail, dict) and str(detail.get("function_id", "")).strip()
    }
    for fallback in build_function_detail_rows(spec):
        function_id = str(fallback.get("function_id", "")).strip()
        if not function_id:
            continue
        existing.setdefault(function_id, fallback)
    spec["function_details"] = [copy.deepcopy(existing[str(function.get("id", "")).strip()]) for function in spec.get("functions", []) if isinstance(function, dict) and str(function.get("id", "")).strip() in existing]


def record_agent_run(
    spec: dict,
    agent: ChapterAgent,
    runtime: AgentRuntime,
    reviewed_fields: Sequence[str],
    llm_status: str,
    llm_error: str = "",
    attempt: int = 1,
    inspector_feedback: Sequence[Mapping[str, object]] | None = None,
    routing_feedback: Sequence[Mapping[str, object]] | None = None,
    llm_client: LLMClient | None = None,
) -> None:
    used_client = llm_client or runtime.llm_client
    routing_feedback = list(routing_feedback or inspector_feedback or [])
    spec.setdefault("meta", {}).setdefault("chapter_agent_runs", []).append(
        {
            "chapter": agent.chapter_key,
            "agent": agent.display_name,
            "attempt": attempt,
            "reviewed_fields": list(reviewed_fields),
            "completed_fields": list(agent.output_fields),
            "current_fields_after_run": populated_fields(spec),
            "instruction": agent.instruction(runtime.guideline),
            "topic_learning_used": True,
            "writer": llm_status,
            "model": used_client.model if llm_status.startswith("llm") else "",
            "reasoning_effort": used_client.reasoning_effort if llm_status.startswith("llm") else "",
            "llm_route": route_metadata(runtime.llm_client, agent.chapter_key, attempt=attempt, feedback=routing_feedback),
            "fallback_reason": llm_error[:500],
            "inspector_feedback": list(inspector_feedback or []),
            "routing_signal_count": len(routing_feedback),
        }
    )


def normalize_agent_output(spec: dict, agent: ChapterAgent, runtime: Optional[AgentRuntime] = None) -> None:
    """Keep each chapter close to the concise sample-document style."""
    normalize_common_agent_fields(spec, agent)
    if agent.chapter_key == "overview":
        overview = spec.get("overview", {})
        if isinstance(overview, dict):
            overview["scope"] = [limit_text_for_policy(item, 150) for item in overview.get("scope", [])]
            for principle in overview.get("principles", []):
                if not isinstance(principle, dict):
                    continue
                principle["name"] = limit_text_for_policy(principle.get("name", ""), 28)
                principle["description"] = limit_text_for_policy(principle.get("description", ""), 110)
        return

    if agent.chapter_key == "actors":
        for actor in spec.get("actors", []):
            if not isinstance(actor, dict):
                continue
            actor["description"] = compact_actor_description(actor.get("description", ""))
        return

    if agent.chapter_key in {"terms", "terms_refinement"}:
        for term in spec.get("terms", []):
            if isinstance(term, dict):
                term["description"] = limit_text_for_policy(term.get("description", ""), 120)
        return

    if agent.chapter_key == "usecases":
        for usecase in spec.get("usecases", []):
            if isinstance(usecase, dict):
                usecase["description"] = limit_text_for_policy(usecase.get("description", ""), 110)
        ensure_usecase_actor_coverage(spec)
        return

    if agent.chapter_key == "usecase_diagram":
        diagram = spec.setdefault("meta", {}).get("usecase_diagram", {})
        if isinstance(diagram, dict):
            diagram["lines"] = [limit_text_for_policy(line, 140) for line in diagram.get("lines", [])]
            ensure_diagram_usecase_coverage(spec, diagram)
        return

    if agent.chapter_key == "state":
        for state in spec.get("states", []):
            if not isinstance(state, dict):
                continue
            state["description"] = limit_text_for_policy(strip_body_ids(state.get("description", "")), 95)
            state["next_action"] = limit_text_for_policy(strip_body_ids(state.get("next_action", "")), 95)
        for transition in spec.get("state_transitions", []):
            if not isinstance(transition, dict):
                continue
            transition["event"] = limit_text_for_policy(strip_body_ids(transition.get("event", "")), 80)
            transition["criteria"] = limit_text_for_policy(strip_body_ids(transition.get("criteria", "")), 120)
        return

    if agent.chapter_key == "process":
        for process in spec.get("processes", []):
            if not isinstance(process, dict):
                continue
            process["description"] = limit_text_for_policy(process.get("description", ""), 110)
            process["related_functions"] = []
            process["related_policies"] = []
        ensure_process_usecase_coverage(spec, runtime)
        ensure_target_requirement_process_coverage(spec, runtime)
        clear_deferred_process_links(spec)
        return

    if agent.chapter_key == "functions":
        for function in spec.get("functions", []):
            if not isinstance(function, dict):
                continue
            linked_process_ids = function_linked_process_ids(function)
            if not linked_process_ids:
                linked_process_ids = [str(function.get("process_id", "")).strip()] if str(function.get("process_id", "")).strip() else []
            function["process_ids"] = linked_process_ids
            if linked_process_ids and not str(function.get("process_id", "")).strip():
                function["process_id"] = linked_process_ids[0]
            function["description"] = limit_text_for_policy(function.get("description", ""), 110)
            function["details"] = normalize_function_detail_labels(function.get("details", []), max_items=5)
        ensure_target_requirement_function_coverage(spec, runtime)
        ensure_function_process_coverage(spec)
        if getattr(getattr(runtime, "llm_client", None), "writer_mode", "") == "mock":
            ensure_mock_function_density_coverage(spec)
            diversify_mock_repeated_function_details(spec)
        deduplicate_function_names(spec)
        reconcile_process_function_links(spec)
        return

    if agent.chapter_key == "process_detail":
        for detail in spec.get("process_details", []):
            if not isinstance(detail, dict):
                continue
            detail["entry_condition"] = limit_text_for_policy(detail.get("entry_condition", ""), 130)
            detail["exit_condition"] = limit_text_for_policy(detail.get("exit_condition", ""), 130)
            detail["previous_processes"] = limit_list_items(detail.get("previous_processes", []), 80, max_items=4)
            detail["next_processes"] = limit_list_items(detail.get("next_processes", []), 80, max_items=4)
            detail["related_functions"] = limit_list_items(detail.get("related_functions", []), 90, max_items=8)
            detail["related_policies"] = limit_list_items(detail.get("related_policies", []), 110, max_items=8)
        ensure_process_detail_coverage(spec)
        return

    if agent.chapter_key == "function_detail":
        for detail in spec.get("function_details", []):
            if not isinstance(detail, dict):
                continue
            detail["input_information"] = limit_list_items(detail.get("input_information", []), 100, max_items=6)
            detail["processing_logic"] = limit_list_items(detail.get("processing_logic", []), 130, max_items=6)
            detail["sub_functions"] = limit_list_items(detail.get("sub_functions", []), 80, max_items=6)
            detail["output_information"] = limit_list_items(detail.get("output_information", []), 100, max_items=6)
            detail["failure_exception_cases"] = limit_list_items(detail.get("failure_exception_cases", []), 120, max_items=6)
            detail["related_policies"] = limit_list_items(detail.get("related_policies", []), 110, max_items=8)
        ensure_function_detail_coverage(spec)
        return

    if agent.chapter_key == "policies":
        for group in spec.get("policy_groups", []):
            if isinstance(group, dict):
                group["description"] = limit_text_for_policy(group.get("description", ""), 120)
        strip_policy_detail_process_ids(spec)
        for detail in spec.get("policy_details", []):
            if not isinstance(detail, dict):
                continue
            detail["name"] = limit_text_for_policy(detail.get("name", ""), 60)
            detail["content"] = compact_policy_detail_content(detail.get("content", ""))
        normalize_policy_details(spec)
        ensure_policy_process_coverage(spec)
        reconcile_process_policy_links(spec)
        return

    if agent.chapter_key == "final_check":
        spec["final_check"] = limit_list_items(spec.get("final_check", []), 120)
        return


def normalize_common_agent_fields(spec: dict, agent: ChapterAgent) -> None:
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        values = spec.get(schema_key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            for key, value in list(item.items()):
                if isinstance(value, str):
                    item[key] = re.sub(r"\s+", " ", value).strip()
                elif isinstance(value, list) and all(not isinstance(entry, (dict, list)) for entry in value):
                    normalized = unique_nonempty(value)
                    if len([entry for entry in value if str(entry).strip()]) > len(normalized):
                        record_normalization_warning(
                            spec,
                            agent,
                            schema_key,
                            "duplicate_list_values_removed",
                            f"{schema_key}.{key} 목록에서 중복·공백 값을 정리했습니다.",
                            examples=normalized[:5],
                        )
                    item[key] = normalized
        id_key = ID_FIELD_BY_LIST.get(schema_key)
        if id_key:
            deduped, dropped_keys = dedupe_dicts_by_key_with_dropped(values, id_key)
            if dropped_keys:
                record_normalization_warning(
                    spec,
                    agent,
                    schema_key,
                    "duplicate_id_rows_removed",
                    f"{schema_key}에서 같은 {id_key}를 가진 행 {len(dropped_keys)}건을 정리했습니다. 중복 ID가 서로 다른 의미를 담았다면 재검수가 필요합니다.",
                    examples=dropped_keys[:8],
                )
            spec[schema_key] = deduped
    strip_policy_detail_process_ids(spec)


def dedupe_dicts_by_key(values: Sequence[object], key: str) -> List[dict]:
    return dedupe_dicts_by_key_with_dropped(values, key)[0]


def dedupe_dicts_by_key_with_dropped(values: Sequence[object], key: str) -> tuple[List[dict], List[str]]:
    result: List[dict] = []
    seen: set[str] = set()
    dropped: List[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        item_key = str(item.get(key, "")).strip()
        if item_key and item_key in seen:
            dropped.append(item_key)
            continue
        if item_key:
            seen.add(item_key)
        result.append(item)
    return result, dropped


def record_normalization_warning(
    spec: dict,
    agent: ChapterAgent,
    field: str,
    reason: str,
    detail: str,
    *,
    examples: Sequence[object] | None = None,
) -> None:
    warnings = spec.setdefault("meta", {}).setdefault("normalization_warnings", [])
    if not isinstance(warnings, list):
        spec.setdefault("meta", {})["normalization_warnings"] = []
        warnings = spec["meta"]["normalization_warnings"]
    entry = {
        "chapter": agent.chapter_key,
        "agent": agent.display_name,
        "field": field,
        "reason": reason,
        "detail": detail,
        "examples": [str(item) for item in list(examples or [])[:8] if str(item).strip()],
    }
    signature = stable_cache_hash(entry)
    existing = {
        str(item.get("signature", ""))
        for item in warnings
        if isinstance(item, Mapping)
    }
    if signature in existing:
        return
    entry["signature"] = signature
    warnings.append(entry)
    if len(warnings) > 80:
        del warnings[:-80]


def compact_actor_description(value: object) -> str:
    text = clean_policy_text(value)
    if not text:
        return ""
    labeled = extract_labeled_segment(text, ("유형", "책임", "역할"))
    if labeled:
        text = labeled
    return limit_text_for_policy(text, 105)


def refined_terms_from_document(spec: dict, runtime: AgentRuntime) -> List[dict]:
    terms = [copy.deepcopy(item) for item in spec.get("terms", []) if isinstance(item, dict)]
    existing_names = {str(item.get("name", "")).strip() for item in terms if str(item.get("name", "")).strip()}
    existing_ids = {str(item.get("id", "")).strip() for item in terms if str(item.get("id", "")).strip()}
    code = business_code_from_spec(spec)

    def add_term(name: str, description: str) -> None:
        clean_name = limit_text_for_policy(name, 40)
        if not clean_name or clean_name in existing_names:
            return
        term_id = next_generated_id(existing_ids, f"TM-{code}")
        existing_ids.add(term_id)
        existing_names.add(clean_name)
        terms.append(
            {
                "id": term_id,
                "name": clean_name,
                "description": limit_text_for_policy(description, 120),
            }
        )

    for state in spec.get("states", [])[:8]:
        if not isinstance(state, dict):
            continue
        state_name = str(state.get("name", "")).strip()
        state_desc = str(state.get("description", "")).strip()
        if state_name:
            add_term(
                state_name,
                state_desc or f"{state_name}은 업무 가능 여부와 후속 처리 기준을 판단하는 상태 값이다.",
            )

    document_text = "\n".join(spec_text_fragments(spec))
    policy_term_rules = [
        ("본인 인증", ("인증", "본인확인"), "고객 또는 대리인의 처리 권한을 확인하기 위해 요구되는 인증 기준이다."),
        ("동의", ("동의", "약관"), "업무 처리 전 고객에게 고지하고 수락 여부를 확인해야 하는 의사 표시 기준이다."),
        ("처리 제한", ("제한", "불가", "차단"), "고객 상태, 상품 조건, 연계 결과에 따라 업무 진행을 막거나 보류하는 기준이다."),
        ("예외 처리", ("예외", "실패", "오류"), "정상 흐름을 완료할 수 없을 때 재시도, 대체 경로, 상담 전환을 판단하는 기준이다."),
        ("고객 고지", ("고지", "안내", "알림"), "처리 결과, 제한 사유, 고객 영향도를 고객에게 명확히 알리는 기준이다."),
        ("이력 저장", ("이력", "로그", "저장"), "처리 요청, 판단 결과, 변경 내용을 추적 가능하게 남기는 관리 기준이다."),
        ("BSS 연계", ("BSS", "원장", "연계"), "채널 요청에 대해 BSS가 검증, 판정, 상태 반영, 결과 회신을 수행하는 처리 기준이다."),
        ("운영 검토", ("운영 검토", "운영 확인", "운영자"), "자동 처리로 확정하기 어려운 건을 운영자가 확인하거나 보정하는 기준이다."),
    ]
    for name, keywords, description in policy_term_rules:
        if any(keyword in document_text for keyword in keywords):
            add_term(name, description)

    return terms


def spec_text_fragments(value: object) -> List[str]:
    fragments: List[str] = []
    if isinstance(value, Mapping):
        for nested in value.values():
            fragments.extend(spec_text_fragments(nested))
    elif isinstance(value, list):
        for nested in value:
            fragments.extend(spec_text_fragments(nested))
    elif isinstance(value, str):
        text = clean_policy_text(value)
        if text:
            fragments.append(text)
    return fragments


def compact_policy_detail_content(value: object) -> str:
    text = clean_policy_text(value)
    text = re.sub(r"^(기준|내용|정책|처리)\s*:\s*", "", text)
    return limit_text_for_policy(text, 220)


def limit_list_items(values: object, max_chars: int, max_items: int | None = None) -> List[str]:
    if not isinstance(values, list):
        return []
    selected = values[:max_items] if max_items is not None else values
    return [limit_text_for_policy(item, max_chars) for item in selected if clean_policy_text(item)]


def ensure_usecase_actor_coverage(spec: dict) -> None:
    actors = [actor for actor in spec.get("actors", []) if isinstance(actor, dict)]
    usecases = spec.setdefault("usecases", [])
    used = {
        str(usecase.get("actor", "")).strip()
        for usecase in usecases
        if isinstance(usecase, dict) and str(usecase.get("actor", "")).strip()
    }
    existing_ids = {str(usecase.get("id", "")) for usecase in usecases if isinstance(usecase, dict)}
    code = business_code_from_spec(spec)
    for actor in actors:
        actor_name = str(actor.get("name", "")).strip()
        actor_id = str(actor.get("id", "")).strip()
        if not actor_name or actor_name in used or actor_id in used:
            continue
        usecase_id = next_generated_id(existing_ids, f"US-{code}-ACT")
        existing_ids.add(usecase_id)
        process_target = "N" if is_system_actor_name(actor_name) else "Y"
        usecase_name, usecase_description = default_usecase_for_actor(
            actor_name,
            str(spec.get("meta", {}).get("topic", "")).strip(),
        )
        usecases.append(
            {
                "id": usecase_id,
                "actor": actor_name,
                "name": limit_text_for_policy(usecase_name, 60),
                "description": limit_text_for_policy(usecase_description, 110),
                "process_target": process_target,
            }
        )


def ensure_diagram_usecase_coverage(spec: dict, diagram: dict) -> None:
    lines = diagram.setdefault("lines", [])
    joined = "\n".join(str(line) for line in lines)
    for usecase in spec.get("usecases", []):
        if not isinstance(usecase, dict):
            continue
        name = str(usecase.get("name", "")).strip()
        actor = str(usecase.get("actor", "")).strip()
        if not name or name in joined:
            continue
        lines.append(limit_text_for_policy(f"[{actor}] → ({name})", 140))


def ensure_process_usecase_coverage(spec: dict, runtime: Optional[AgentRuntime]) -> None:
    processes = spec.setdefault("processes", [])
    existing_ids = {str(process.get("id", "")) for process in processes if isinstance(process, dict)}
    code = business_code_from_spec(spec)
    density_profile = density_profile_for_runtime(runtime)
    for usecase in spec.get("usecases", []):
        if not isinstance(usecase, dict) or usecase.get("process_target") != "Y":
            continue
        usecase_id = str(usecase.get("id", "")).strip()
        if not usecase_id:
            continue
        current_count = sum(
            1
            for process in processes
            if isinstance(process, dict) and str(process.get("usecase_id", "")).strip() == usecase_id
        )
        minimum_count = minimum_process_count_for_usecase(usecase, density_profile)
        if current_count >= minimum_count:
            continue
        suffix = usecase_id.replace(f"US-{code}-", "").replace("US-", "")
        templates = process_templates_for_usecase(usecase)
        for index in range(current_count, minimum_count):
            template = templates[min(index, len(templates) - 1)]
            process_id = next_process_step_id(existing_ids, f"PR-{code}-{suffix}")
            existing_ids.add(process_id)
            processes.append(
                {
                    "id": process_id,
                    "usecase_id": usecase_id,
                    "name": limit_text_for_policy(template["name"], 60),
                    "description": limit_text_for_policy(template["description"], 110),
                    "related_functions": [],
                    "related_policies": [],
                }
            )


def ensure_target_requirement_process_coverage(spec: dict, runtime: Optional[AgentRuntime]) -> None:
    if runtime is None or not isinstance(getattr(runtime, "target_spec", None), Mapping):
        return
    target_processes = runtime.target_spec.get("processes", [])
    if not isinstance(target_processes, list):
        return
    processes = spec.setdefault("processes", [])
    existing_ids = {str(process.get("id", "")).strip() for process in processes if isinstance(process, dict)}
    usecase_ids = {str(usecase.get("id", "")).strip() for usecase in spec.get("usecases", []) if isinstance(usecase, dict)}
    for process in target_processes:
        if not isinstance(process, Mapping):
            continue
        process_id = str(process.get("id", "")).strip()
        usecase_id = str(process.get("usecase_id", "")).strip()
        if "-RQCOV-" not in process_id or not process_id or process_id in existing_ids or usecase_id not in usecase_ids:
            continue
        copied = copy.deepcopy(dict(process))
        copied["related_functions"] = []
        copied["related_policies"] = []
        processes.append(copied)
        existing_ids.add(process_id)


def clear_deferred_process_links(spec: dict) -> None:
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        process["related_functions"] = []
        process["related_policies"] = []


def ensure_function_process_coverage(spec: dict) -> None:
    functions = spec.setdefault("functions", [])
    existing_names = {str(function.get("name", "")).strip() for function in functions if isinstance(function, dict)}
    existing_ids = {str(function.get("id", "")) for function in functions if isinstance(function, dict)}
    code = business_code_from_spec(spec)
    function_process_ids = {
        process_id
        for function in functions
        if isinstance(function, dict)
        for process_id in function_linked_process_ids(function)
    }
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("id", "")).strip()
        if process_id and process_id not in function_process_ids:
            process_name = str(process.get("name") or "프로세스").strip()
            function_name = unique_function_name(
                existing_names,
                fallback_function_name_for_process(process_name, len(functions)),
            )
            function_id = next_generated_id(existing_ids, f"FN-{code}-AUTO")
            existing_ids.add(function_id)
            existing_names.add(function_name)
            function_process_ids.add(process_id)
            details = fallback_function_details_for_process(process_name, function_name, len(functions))
            functions.append(
                {
                    "id": function_id,
                    "process_id": process_id,
                    "process_ids": [process_id],
                    "name": function_name,
                    "description": fallback_function_description_for_process(process_name, function_name, details),
                    "details": details,
                }
            )
        for function_ref in process.get("related_functions", []) if isinstance(process.get("related_functions"), list) else []:
            _, function_name = split_function_reference(function_ref)
            function_name = function_name or str(function_ref).strip()
            if not process_id or not function_name or function_name in existing_names:
                continue
            function_id = next_generated_id(existing_ids, f"FN-{code}-AUTO")
            process_name = str(process.get("name") or "프로세스").strip()
            function_name = fallback_function_name_for_process(function_name, len(functions))
            if function_name in existing_names:
                function_name = unique_function_name(existing_names, function_name)
            existing_ids.add(function_id)
            existing_names.add(function_name)
            details = fallback_function_details_for_process(process_name, function_name, len(functions))
            functions.append(
                {
                    "id": function_id,
                    "process_id": process_id,
                    "process_ids": [process_id],
                    "name": function_name,
                    "description": fallback_function_description_for_process(process_name, function_name, details),
                    "details": details,
                }
            )


def collapse_repeated_label_tokens(value: object) -> str:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+|[^0-9A-Za-z가-힣]+", str(value or ""))
    result: List[str] = []
    previous_word = ""
    for token in tokens:
        if re.fullmatch(r"[0-9A-Za-z가-힣]+", token):
            if token == previous_word:
                continue
            previous_word = token
        elif token.strip():
            previous_word = ""
        result.append(token)
    return re.sub(r"\s+", " ", "".join(result)).strip()


def fallback_function_name_for_process(process_name: object, index: int) -> str:
    text = collapse_repeated_label_tokens(process_name)
    text = re.sub(r"\s*(처리\s*)?기능\s*\d*\s*$", "", text).strip()
    text = re.sub(r"\s*처리\s*$", "", text).strip()
    text = re.sub(r"\s*프로세스\s*$", "", text).strip()
    if not text:
        defaults = ("대상 조건 확인", "처리 가능 여부 판정", "결과 고지 구성", "이력 저장 관리")
        return defaults[index % len(defaults)]
    if text.endswith(("조회", "검증", "판정", "산정", "저장", "안내", "구성", "확인", "분류", "연동", "관리", "등록")):
        return limit_text_for_policy(text, 70)
    if any(keyword in text for keyword in ("권한", "상태", "조건", "가능", "인증", "동의")):
        return limit_text_for_policy(f"{text} 기준 검증", 70)
    if any(keyword in text for keyword in ("결과", "완료", "안내", "고지")):
        return limit_text_for_policy(f"{text} 구성", 70)
    if any(keyword in text for keyword in ("이력", "로그", "저장")):
        return limit_text_for_policy(f"{text} 저장", 70)
    if any(keyword in text for keyword in ("연계", "BSS", "응답")):
        return limit_text_for_policy(f"{text} 확인", 70)
    return limit_text_for_policy(f"{text} 처리 기준 확인", 70)


def fallback_function_details_for_process(process_name: object, function_name: object, index: int) -> List[str]:
    text = f"{process_name} {function_name}"
    patterns: Sequence[tuple[Sequence[str], Sequence[str]]] = (
        (("진입", "접근", "대상"), ("업무 대상 조회", "접근 권한 검증", "진입 결과 저장")),
        (("조회", "정보", "목록", "상세"), ("조회 대상 식별", "조회 조건 검증", "표시 결과 구성")),
        (("권한", "상태", "조건", "가능", "검증"), ("고객 상태 확인", "처리 조건 검증", "제한 사유 고지")),
        (("입력", "인증", "동의"), ("입력값 정합성 확인", "인증·동의 결과 검증", "요청 정보 구성")),
        (("영향", "비용", "혜택", "할인", "요금"), ("고객 영향도 산정", "적용 기준 검증", "사전 고지 구성")),
        (("요청", "접수", "중복"), ("요청 정보 구성", "중복 요청 판정", "접수 이력 저장")),
        (("결과", "반영", "완료", "실패"), ("처리 결과 판정", "후속 상태 반영", "완료·실패 안내")),
        (("후속", "취소", "재시도", "복구"), ("후속 가능 여부 판정", "복구 조건 확인", "상담 전환 안내")),
        (("운영", "예외", "승인", "보정"), ("운영 기준 조회", "예외 사유 분류", "검토 이력 저장")),
        (("연계", "BSS", "응답"), ("연계 요청 구성", "응답 결과 검증", "불일치 이력 저장")),
    )
    for keywords, details in patterns:
        if any(keyword in text for keyword in keywords):
            return contextualize_fallback_function_details(process_name, function_name, details)
    fallbacks = (
        ("요청 대상 조회", "처리 조건 검증", "결과 이력 저장"),
        ("기준 정보 조회", "허용 여부 판정", "고객 안내 구성"),
        ("상태 정보 확인", "예외 사유 분류", "후속 처리 연결"),
        ("연계 결과 확인", "보류 여부 판정", "재시도 안내 저장"),
    )
    return contextualize_fallback_function_details(process_name, function_name, fallbacks[index % len(fallbacks)])


def contextualize_fallback_function_details(
    process_name: object,
    function_name: object,
    details: Sequence[str],
) -> List[str]:
    contextualized = [str(item).strip() for item in details if str(item).strip()]
    if not contextualized:
        return []
    base = collapse_repeated_label_tokens(function_name or process_name)
    base = re.sub(r"\s+\d+\s*$", "", base).strip()
    base = re.sub(r"\s*(처리 기준 확인|기준 검증|정보 구성|구성|확인|검증|조회|처리|기능)\s*$", "", base).strip()
    base = limit_text_for_policy(base, 18)
    if base and base not in contextualized[0]:
        action = "조회"
        if "검증" in contextualized[0]:
            action = "검증"
        elif "판정" in contextualized[0]:
            action = "판정"
        elif "저장" in contextualized[0]:
            action = "저장"
        contextualized[0] = limit_text_for_policy(f"{base} {action}", 36)
    return contextualized


def korean_has_final_consonant(text: object) -> bool:
    for char in reversed(str(text or "").strip()):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if char.isalnum():
            return True
    return False


def korean_topic_particle(text: object) -> str:
    return "은" if korean_has_final_consonant(text) else "는"


def fallback_function_description_for_process(process_name: object, function_name: object, details: Sequence[str]) -> str:
    detail_text = ", ".join(str(item).strip() for item in details[:3] if str(item).strip())
    if not detail_text:
        detail_text = "대상 조회, 조건 검증, 결과 저장"
    return limit_text_for_policy(
        f"{function_name}{korean_topic_particle(function_name)} {process_name} 단계에서 {detail_text}을 순서대로 수행해 처리 가능 여부와 후속 안내 기준을 만든다.",
        110,
    )


MOCK_FUNCTION_DENSITY_TEMPLATES = (
    (
        "조건·제한 판정",
        "{process_name}의 고객 상태, 권한, 제한 조건을 확인해 허용·보류·제한 결과를 산정한다.",
        ("고객 상태 확인", "권한 조건 검증", "제한 사유 산정", "판정 결과 저장"),
    ),
    (
        "결과·이력 구성",
        "{process_name}의 처리 결과, 실패 사유, 후속 가능 여부를 구성하고 감사 가능한 이력을 남긴다.",
        ("처리 결과 구성", "실패 사유 정리", "후속 가능 여부 산정", "처리 이력 저장"),
    ),
    (
        "고지·후속 경로 구성",
        "{process_name}의 완료·제한·보류 결과를 고객에게 안내하고 다음 행동 경로를 제공한다.",
        ("고지 대상 판정", "안내 내용 구성", "후속 경로 연결", "고지 이력 저장"),
    ),
    (
        "연계 결과 확인",
        "{process_name}에 필요한 BSS 또는 연계 시스템 응답을 확인하고 불일치 시 보류·재시도 기준을 만든다.",
        ("연계 응답 확인", "불일치 여부 판정", "재시도 기준 산정", "보류 이력 저장"),
    ),
)


def ensure_mock_function_density_coverage(spec: dict) -> None:
    """Improve no-cost mock drafts by avoiding one-process/one-function thinness."""

    functions = spec.setdefault("functions", [])
    processes = [process for process in spec.get("processes", []) if isinstance(process, dict)]
    if not processes:
        return
    existing_ids = {str(function.get("id", "")).strip() for function in functions if isinstance(function, dict)}
    existing_names = {str(function.get("name", "")).strip() for function in functions if isinstance(function, dict)}
    function_process_counts: dict[str, int] = {}
    for function in functions:
        if not isinstance(function, dict):
            continue
        for process_id in function_linked_process_ids(function):
            function_process_counts[process_id] = function_process_counts.get(process_id, 0) + 1
    code = business_code_from_spec(spec)
    for index, process in enumerate(processes):
        process_id = str(process.get("id", "")).strip()
        if not process_id or function_process_counts.get(process_id, 0) >= 2:
            continue
        template_name, description_template, details = MOCK_FUNCTION_DENSITY_TEMPLATES[
            index % len(MOCK_FUNCTION_DENSITY_TEMPLATES)
        ]
        process_name = str(process.get("name") or "프로세스").strip()
        function_name = unique_function_name(
            existing_names,
            density_function_name_for_process(process_name, template_name),
        )
        function_id = next_generated_id(existing_ids, f"FN-{code}-AUX")
        existing_ids.add(function_id)
        existing_names.add(function_name)
        function_process_counts[process_id] = function_process_counts.get(process_id, 0) + 1
        functions.append(
            {
                "id": function_id,
                "process_id": process_id,
                "process_ids": [process_id],
                "name": function_name,
                "description": limit_text_for_policy(description_template.format(process_name=process_name), 110),
                "details": contextualize_fallback_function_details(process_name, function_name, details),
            }
        )


def diversify_mock_repeated_function_details(spec: dict, threshold: int = 6) -> None:
    """Mock 전용: 같은 세부 기능 구성이 과도하게 반복되면 프로세스 맥락으로 다시 잡는다."""

    functions = [function for function in spec.get("functions", []) if isinstance(function, dict)]
    if not functions:
        return
    processes_by_id = {
        str(process.get("id", "")).strip(): process
        for process in spec.get("processes", [])
        if isinstance(process, dict)
    }
    signature_rows: dict[tuple[str, ...], List[dict]] = {}
    for function in functions:
        signature = tuple(str(item).strip() for item in function.get("details", []) if str(item).strip())
        if signature:
            signature_rows.setdefault(signature, []).append(function)
    for rows in signature_rows.values():
        if len(rows) < threshold:
            continue
        for index, function in enumerate(rows):
            process_id = str(function.get("process_id", "") or "").strip()
            process = processes_by_id.get(process_id, {})
            process_name = str(process.get("name") or function.get("name") or "프로세스").strip()
            function_name = str(function.get("name") or process_name).strip()
            details = fallback_function_details_for_process(process_name, function_name, index)
            function["details"] = details
            function["description"] = fallback_function_description_for_process(process_name, function_name, details)


def ensure_target_requirement_function_coverage(spec: dict, runtime: Optional[AgentRuntime]) -> None:
    if runtime is None or not isinstance(getattr(runtime, "target_spec", None), Mapping):
        return
    target_functions = runtime.target_spec.get("functions", [])
    if not isinstance(target_functions, list):
        return
    functions = spec.setdefault("functions", [])
    existing_ids = {str(function.get("id", "")).strip() for function in functions if isinstance(function, dict)}
    process_ids = {str(process.get("id", "")).strip() for process in spec.get("processes", []) if isinstance(process, dict)}
    for index, function in enumerate(target_functions):
        if not isinstance(function, Mapping):
            continue
        function_id = str(function.get("id", "")).strip()
        linked_process_ids = function_linked_process_ids(function)
        if "-RQCOV-" not in function_id or not function_id or function_id in existing_ids:
            continue
        if not linked_process_ids or not any(process_id in process_ids for process_id in linked_process_ids):
            continue
        copied = copy.deepcopy(dict(function))
        copied["process_ids"] = [process_id for process_id in linked_process_ids if process_id in process_ids]
        copied["process_id"] = copied["process_ids"][0]
        copied["name"] = fallback_function_name_for_process(copied.get("name") or copied.get("id"), index)
        if copied["name"] in {str(item.get("name", "")).strip() for item in functions if isinstance(item, dict)}:
            copied["name"] = unique_function_name(
                {str(item.get("name", "")).strip() for item in functions if isinstance(item, dict)},
                copied["name"],
            )
        if not isinstance(copied.get("details"), list) or any(
            str(item).strip() in {"조회", "검증", "저장", "결과 안내", "정보", "기준", "확인"}
            for item in copied.get("details", [])
        ):
            copied["details"] = fallback_function_details_for_process(
                copied.get("name"), copied.get("name"), len(functions)
            )
        copied["description"] = fallback_function_description_for_process(
            copied.get("name"), copied.get("name"), copied.get("details") or []
        )
        functions.append(copied)
        existing_ids.add(function_id)


def reconcile_process_function_links(spec: dict) -> None:
    refs_by_process: dict[str, List[str]] = {}
    for function in spec.get("functions", []):
        if not isinstance(function, dict):
            continue
        function_ref = format_function_reference(function)
        for process_id in function_linked_process_ids(function):
            if process_id and function_ref:
                refs_by_process.setdefault(process_id, []).append(function_ref)
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("id", "")).strip()
        process["related_functions"] = limit_list_items(unique_nonempty(refs_by_process.get(process_id, [])), 120, max_items=8)


def deduplicate_function_names(spec: dict) -> None:
    existing_names: set[str] = set()
    for function in spec.get("functions", []):
        if not isinstance(function, dict):
            continue
        name = str(function.get("name", "")).strip()
        if not name:
            continue
        if name in existing_names:
            name = unique_function_name(existing_names, name)
            function["name"] = name
        existing_names.add(name)


def format_function_reference(function: Mapping[str, object]) -> str:
    function_id = str(function.get("id", "")).strip()
    function_name = str(function.get("name", "")).strip()
    return " ".join(item for item in (function_id, function_name) if item).strip()


def function_linked_process_ids(function: Mapping[str, object]) -> List[str]:
    values: List[str] = []
    process_id = str(function.get("process_id", "")).strip()
    if process_id:
        values.append(process_id)
    for key in ("process_ids", "related_process_ids"):
        raw = function.get(key)
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    return unique_nonempty(values)


def function_granularity_error(processes: object, functions: object) -> str:
    if not isinstance(processes, list) or not isinstance(functions, list):
        return ""
    process_ids = [str(process.get("id", "")).strip() for process in processes if isinstance(process, dict) and str(process.get("id", "")).strip()]
    if len(process_ids) < 8:
        return ""
    counts = {process_id: 0 for process_id in process_ids}
    reused_function_count = 0
    for function in functions:
        if not isinstance(function, Mapping):
            continue
        linked_process_ids = [process_id for process_id in function_linked_process_ids(function) if process_id in counts]
        if len(linked_process_ids) > 1:
            reused_function_count += 1
        for process_id in linked_process_ids:
            counts[process_id] += 1
    covered_counts = [count for count in counts.values() if count > 0]
    if len(covered_counts) != len(process_ids):
        return ""
    single_count = sum(1 for count in covered_counts if count == 1)
    if single_count == len(process_ids):
        return (
            "프로세스별 기능이 모두 1개씩만 연결되어 기능 입자도가 프로세스와 1:1로 고착되었습니다. "
            "샘플처럼 복합 프로세스에는 조회·검증·저장·알림·연동·이력 등 복수 기능을 연결하고, "
            "공통 기능은 하나의 기능 ID를 여러 process_ids에 재사용하세요."
        )
    if single_count >= int(len(process_ids) * 0.85) and reused_function_count == 0:
        return (
            "대부분의 프로세스가 기능 1개만 갖고 공통 기능 재사용도 없습니다. "
            "프로세스-기능 관계를 재검토해 복합 프로세스의 기능 분해와 공통 기능 재사용을 반영하세요."
        )
    return ""


def split_function_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(FN-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def validate_named_references(
    values: object,
    names_by_id: Mapping[str, str],
    splitter,
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"{owner_id}의 {label}은 배열이어야 합니다."]
    known_names = {name for name in names_by_id.values() if name}
    errors: List[str] = []
    for value in values:
        text = normalize_space(value)
        if not text:
            continue
        ref_id, ref_name = splitter(text)
        if not ref_id:
            if text in known_names:
                errors.append(f"{owner_id}의 {label}은 ID와 명칭을 함께 작성해야 합니다: {text}")
            else:
                errors.append(f"{owner_id}의 {label}이 목록에 없습니다: {text}")
            continue
        expected_name = names_by_id.get(ref_id)
        if not expected_name:
            errors.append(f"{owner_id}의 {label} ID가 목록에 없습니다: {ref_id}")
        elif not ref_name:
            errors.append(f"{owner_id}의 {label}은 ID와 명칭을 함께 작성해야 합니다: {text}")
        elif normalize_space(ref_name) != normalize_space(expected_name):
            errors.append(f"{owner_id}의 {label} 명칭이 ID와 일치하지 않습니다: {text}")
    return errors


def validate_process_flow_references(
    values: object,
    process_ids: set[str],
    process_names_by_id: Mapping[str, str],
    label: str,
    owner_id: str,
) -> List[str]:
    if not isinstance(values, list):
        return [f"{owner_id}의 {label}은 배열이어야 합니다."]
    errors: List[str] = []
    known_names = {name for name in process_names_by_id.values() if name}
    allowed_texts = {"-", "없음", "업무 진입 조건 충족", "결과 안내 또는 후속 업무 연결"}
    for value in values:
        text = normalize_space(value)
        if not text or text in allowed_texts:
            continue
        match = re.match(r"^(PR-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
        if match:
            process_id = match.group(1).strip()
            process_name = normalize_space(match.group(2))
            expected_name = process_names_by_id.get(process_id, "")
            if process_id not in process_ids:
                errors.append(f"{owner_id}의 {label} ID가 프로세스 목록에 없습니다: {process_id}")
            elif process_id == owner_id:
                errors.append(f"{owner_id}의 {label}이 자기 자신을 참조합니다.")
            elif process_name and normalize_space(expected_name) != process_name:
                errors.append(f"{owner_id}의 {label} 명칭이 프로세스 ID와 일치하지 않습니다: {text}")
            continue
        if text not in known_names:
            errors.append(f"{owner_id}의 {label}이 프로세스 목록에 없습니다: {text}")
    return errors


def ensure_policy_process_coverage(spec: dict) -> None:
    groups = spec.setdefault("policy_groups", [])
    details = spec.setdefault("policy_details", [])
    group_names = {str(group.get("name", "")).strip(): str(group.get("id", "")).strip() for group in groups if isinstance(group, dict)}
    group_ids = {str(group.get("id", "")) for group in groups if isinstance(group, dict)}
    detail_ids = {str(detail.get("id", "")) for detail in details if isinstance(detail, dict)}
    detail_policy_ids = {str(detail.get("policy_id", "")) for detail in details if isinstance(detail, dict)}
    code = business_code_from_spec(spec)
    strip_policy_detail_process_ids(spec)
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        for policy_ref in process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []:
            _, policy_name = split_policy_reference(policy_ref)
            policy_name = policy_name or str(policy_ref).strip()
            if not policy_name or policy_name in group_names:
                continue
            policy_id = next_generated_id(group_ids, f"PG-{code}-AUTO")
            group_ids.add(policy_id)
            group_names[policy_name] = policy_id
            groups.append({"id": policy_id, "name": policy_name, "description": f"{policy_name}의 판단 기준을 정의한다."})
    for policy_name, policy_id in list(group_names.items()):
        if not policy_id or policy_id in detail_policy_ids:
            continue
        detail_id = next_generated_id(detail_ids, f"PI-{code}-AUTO")
        detail_ids.add(detail_id)
        detail_policy_ids.add(policy_id)
        details.append(
            {
                "id": detail_id,
                "policy_id": policy_id,
                "name": "기본 적용 기준",
                "content": compact_policy_detail_content(f"{policy_name}은 고객 영향, 예외, 고지, 이력 저장 기준을 함께 적용한다."),
            }
        )
    normalize_policy_details(spec)


def strip_policy_detail_process_ids(spec: dict) -> None:
    for detail in spec.get("policy_details", []):
        if isinstance(detail, dict):
            detail.pop("process_id", None)
            detail.pop("process_ids", None)
            detail.pop("applicable_processes", None)


POLICY_DETAIL_SLOT_FIELDS = (
    "condition",
    "decision_rule",
    "thresholds",
    "exception_handling",
    "customer_notice",
    "audit_log",
    "owner",
    "source_evidence_ids",
    "tbd_reasons",
)


def normalize_policy_details(spec: dict) -> None:
    for detail in spec.get("policy_details", []):
        if not isinstance(detail, dict):
            continue
        detail["name"] = limit_text_for_policy(detail.get("name", ""), 60)
        content = compact_policy_detail_content(detail.get("content", ""))
        detail["content"] = content or default_policy_logic(detail)
        for field in POLICY_DETAIL_SLOT_FIELDS:
            detail.pop(field, None)
    sync_policy_group_items_from_details(spec)


def default_policy_logic(detail: Mapping[str, object]) -> str:
    content = str(detail.get("content", "")).strip()
    return content or "업무별 허용 목록, 제한 조건, 적용 채널, 이력 저장 항목 중 필요한 값을 정책 항목으로 확정한다."


def sync_policy_group_items_from_details(spec: dict) -> None:
    details_by_policy: dict[str, list[str]] = {}
    for detail in spec.get("policy_details", []):
        if not isinstance(detail, dict):
            continue
        policy_id = str(detail.get("policy_id", "")).strip()
        name = str(detail.get("name", "")).strip()
        if policy_id and name:
            details_by_policy.setdefault(policy_id, []).append(name)
    for group in spec.get("policy_groups", []):
        if not isinstance(group, dict):
            continue
        policy_id = str(group.get("id", "")).strip()
        if policy_id in details_by_policy:
            group["items"] = details_by_policy[policy_id]


def reconcile_process_policy_links(spec: dict) -> None:
    strip_policy_detail_process_ids(spec)
    groups = [group for group in spec.get("policy_groups", []) if isinstance(group, dict)]
    group_by_name = {
        str(group.get("name", "")).strip(): group
        for group in groups
        if str(group.get("name", "")).strip()
    }
    group_by_id = {
        str(group.get("id", "")).strip(): group
        for group in groups
        if str(group.get("id", "")).strip()
    }
    functions_by_process = functions_grouped_by_process(spec)
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        process_id = str(process.get("id", "")).strip()
        existing_refs = []
        for policy_ref in process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []:
            policy_id, policy_name = split_policy_reference(policy_ref)
            group = group_by_id.get(policy_id) or group_by_name.get(policy_name)
            if group:
                existing_refs.append(format_policy_reference(group))
        recommended = policy_names_for_process(
            process,
            groups,
            functions_by_process.get(process_id, []),
            max_items=4,
        )
        recommended_refs = [
            format_policy_reference(group_by_name[name])
            for name in recommended
            if name in group_by_name
        ]
        # Policy links are derived after the policy chapter is complete. Prefer
        # the current policy catalogue over stale placeholder links produced in
        # earlier chapters.
        process["related_policies"] = limit_list_items(
            unique_nonempty(recommended_refs or existing_refs),
            120,
            max_items=4,
        )
    attach_unlinked_policy_groups_to_processes(spec, groups, functions_by_process)


def attach_unlinked_policy_groups_to_processes(
    spec: dict,
    groups: Sequence[dict],
    functions_by_process: Mapping[str, Sequence[dict]],
) -> None:
    """Avoid renderer-level '미연결 정책' buckets by assigning each policy once.

    The sample documents show policy groups under process-oriented sections
    rather than as a catch-all orphan table. This keeps the catalogue intact
    while adding the lightest plausible process link for groups that the first
    pass did not select.
    """

    if not groups:
        return
    group_by_id = {str(group.get("id", "")).strip(): group for group in groups if str(group.get("id", "")).strip()}
    linked_ids: set[str] = set()
    for process in spec.get("processes", []):
        if not isinstance(process, dict):
            continue
        for policy_ref in process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []:
            policy_id, _ = split_policy_reference(policy_ref)
            if policy_id:
                linked_ids.add(policy_id)
    orphan_groups = [group for policy_id, group in group_by_id.items() if policy_id not in linked_ids]
    if not orphan_groups:
        return
    processes = [process for process in spec.get("processes", []) if isinstance(process, dict)]
    if not processes:
        return
    for group in orphan_groups:
        process = best_process_for_policy_group(group, processes, functions_by_process)
        refs = process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []
        process["related_policies"] = limit_list_items(
            unique_nonempty([*refs, format_policy_reference(group)]),
            120,
            max_items=5,
        )


def best_process_for_policy_group(
    group: Mapping[str, object],
    processes: Sequence[dict],
    functions_by_process: Mapping[str, Sequence[dict]],
) -> dict:
    ranked: List[tuple[int, int, str, dict]] = []
    group_name = str(group.get("name", "")).strip()
    for process in processes:
        process_id = str(process.get("id", "")).strip()
        refs = process.get("related_policies", []) if isinstance(process.get("related_policies"), list) else []
        function_text = " ".join(
            " ".join(
                [
                    str(function.get("name", "")),
                    str(function.get("description", "")),
                    " ".join(str(item) for item in function.get("details", []) if str(item).strip())
                    if isinstance(function.get("details", []), list)
                    else "",
                ]
            )
            for function in functions_by_process.get(process_id, [])
            if isinstance(function, Mapping)
        )
        process_text = " ".join([str(process.get("name", "")), str(process.get("description", "")), function_text])
        score = policy_group_match_score(process_text, policy_group_axes(group_name), group)
        ranked.append((score, len(refs), process_id, process))
    available = [item for item in ranked if item[1] < 5]
    candidates = available or ranked
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][3]


def policy_group_axes(group_name: str) -> tuple[str, ...]:
    text = str(group_name or "")
    axes: list[str] = []
    rules = (
        (("접근", "권한"), ("진입", "접근", "권한", "로그인", "자격")),
        (("정보", "노출"), ("조회", "정보", "노출", "구성")),
        (("상태", "전환"), ("상태", "변경", "반영", "완료")),
        (("인증", "동의"), ("인증", "동의", "본인")),
        (("입력", "검증"), ("입력", "검증", "확인")),
        (("영향", "고지"), ("영향", "고지", "안내", "혜택", "비용")),
        (("요청", "접수"), ("요청", "접수", "처리")),
        (("중복",), ("중복", "재요청", "반복")),
        (("BSS", "연계"), ("BSS", "연계", "원장", "회신")),
        (("후속",), ("후속", "다음", "연결")),
        (("예외", "상담", "오류", "장애"), ("예외", "상담", "실패", "보류", "오류", "장애")),
        (("알림", "고지"), ("알림", "고지", "안내", "통지")),
        (("개인정보", "로그", "데이터", "보관", "파기"), ("개인정보", "로그", "데이터", "보관", "파기", "이력")),
        (("운영", "품질", "변경"), ("운영", "품질", "변경", "관리", "모니터링")),
        (("요구사항",), ("요구사항", "반영", "누락", "추적")),
    )
    for keywords, values in rules:
        if any(keyword in text for keyword in keywords):
            axes.extend(values)
    return tuple(unique_nonempty(axes))


def format_policy_reference(group: Mapping[str, object]) -> str:
    policy_id = str(group.get("id", "")).strip()
    policy_name = str(group.get("name", "")).strip()
    return " ".join(item for item in (policy_id, policy_name) if item).strip()


def split_policy_reference(value: object) -> tuple[str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(PG-[A-Z0-9]+-[A-Z0-9-]+)(?:\s*[-:|]\s*|\s+)?(.*)$", text)
    if not match:
        return "", text
    return match.group(1).strip(), match.group(2).strip()


def functions_grouped_by_process(spec: dict) -> dict[str, List[dict]]:
    grouped: dict[str, List[dict]] = {}
    for function in spec.get("functions", []):
        if not isinstance(function, dict):
            continue
        for process_id in function_linked_process_ids(function):
            grouped.setdefault(process_id, []).append(function)
    return grouped


def policy_names_for_process(process: Mapping[str, object], groups: Sequence[dict], functions: Sequence[dict], max_items: int = 3) -> List[str]:
    available_groups = [group for group in groups if isinstance(group, dict) and str(group.get("name", "")).strip()]
    if not available_groups:
        return []
    function_text = " ".join(
        " ".join(
            [
                str(function.get("name", "")),
                str(function.get("description", "")),
                " ".join(str(item) for item in function.get("details", []) if str(item).strip())
                if isinstance(function.get("details", []), list)
                else "",
            ]
        )
        for function in functions
        if isinstance(function, dict)
    )
    process_text = " ".join([str(process.get("name", "")), str(process.get("description", ""))])
    # Function descriptions can be intentionally broad because one function may
    # support multiple process variants. Use the process itself as the primary
    # policy-mapping signal, then fall back to function text only if needed.
    text = process_text
    desired_axes: List[str] = []
    keyword_rules = [
        (("진입", "접근", "권한", "로그인", "자격"), ("접근·권한",)),
        (("조회", "정보", "노출", "구성", "기준일", "목적"), ("정보 노출", "상태 조회")),
        (("상태", "조건", "가능", "검증", "판정", "제한"), ("가능 여부 검증", "상태 조회", "상태 전환")),
        (("인증", "동의", "본인"), ("인증·동의", "수신 동의")),
        (("입력", "선택", "값"), ("입력", "검증")),
        (("영향", "비용", "혜택", "약정", "청구", "할인"), ("영향도 고지", "고지")),
        (("요청", "접수", "처리"), ("처리 요청", "중복", "상태 전환")),
        (("결과", "완료", "반영", "저장", "이력"), ("처리 결과", "이력 저장", "상태 전환")),
        (("예외", "실패", "상담", "보류", "장애", "오류"), ("예외·상담", "연계 실패", "오류")),
        (("BSS", "연계", "회신", "원장"), ("BSS", "연계 판정", "업무 판정")),
        (("알림", "고지", "안내"), ("알림 노출", "알림 정보", "유형·고지")),
        (("운영", "관리", "모니터링", "품질", "보정"), ("운영", "품질", "변경 이력")),
        (("개인정보", "로그", "보호", "민감", "마스킹"), ("개인정보", "로그 보호", "이력 보관")),
    ]
    for keywords, axes in keyword_rules:
        if any(keyword in text for keyword in keywords):
            desired_axes.extend(axes)
    desired_axes.extend(["처리 결과", "이력"])
    scored = sorted(
        (
            (policy_group_match_score(text, desired_axes, group), str(group.get("name", "")).strip())
            for group in available_groups
        ),
        key=lambda item: (-item[0], item[1]),
    )
    selected = [name for score, name in scored if score > 0][:max_items]
    if function_text:
        fallback_scored = sorted(
            (
                (policy_group_match_score(function_text, (), group), str(group.get("name", "")).strip())
                for group in available_groups
            ),
            key=lambda item: (-item[0], item[1]),
        )
        fallback_selected = [name for score, name in fallback_scored if score > 0]
        if selected:
            # Keep the process-specific mapping primary, but do not drop a
            # shared function's core policy axis when the process itself only
            # produced a sparse mapping.
            if len(selected) < 2:
                return unique_nonempty(selected + fallback_selected)[:max_items]
            return selected
        if fallback_selected:
            return fallback_selected[:max_items]
    if selected:
        return selected
    return [str(available_groups[0].get("name", "")).strip()]


POLICY_MATCH_STOPWORDS = {
    "정책",
    "기준",
    "관리",
    "처리",
    "통합",
    "고객",
    "업무",
    "시스템",
    "채널",
    "대상",
}


def policy_group_match_score(process_text: str, desired_axes: Sequence[str], group: Mapping[str, object]) -> int:
    group_text = " ".join([str(group.get("name", "")), str(group.get("description", ""))])
    group_tokens = policy_match_tokens(group_text)
    process_tokens = policy_match_tokens(process_text)
    score = 0
    for axis in desired_axes:
        axis_tokens = policy_match_tokens(axis)
        if not axis_tokens:
            continue
        overlap = axis_tokens & group_tokens
        if axis_normalized(axis) and axis_normalized(axis) in axis_normalized(group_text):
            score += 40
        score += len(overlap) * 12
    score += len(process_tokens & group_tokens) * 3
    if any(keyword in process_text for keyword in ("예외", "실패", "상담", "보류", "장애", "오류")):
        if any(keyword in group_text for keyword in ("예외", "실패", "상담", "장애", "오류")):
            score += 20
    elif any(keyword in group_text for keyword in ("예외", "상담", "장애", "오류")):
        score -= 18
    return score


def policy_match_tokens(text: object) -> set[str]:
    raw = str(text or "")
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", raw)
    return {token for token in tokens if token not in POLICY_MATCH_STOPWORDS}


def axis_normalized(text: object) -> str:
    return re.sub(r"[\s·/()_-]+", "", str(text or "").replace("정책", ""))


def unique_function_name(existing_names: set[str], base_name: str) -> str:
    if base_name not in existing_names:
        return base_name
    index = 0
    while True:
        candidate = mock_function_name_collision_variant(base_name, index)
        if candidate not in existing_names:
            return candidate
        index += 1


def mock_function_name_collision_variant(base_name: str, index: int) -> str:
    base = collapse_repeated_label_tokens(base_name)
    stem = re.sub(
        r"\s*(처리 기준 확인|기준 검증|조건 검증|정보 구성|조건 확인|결과 구성|이력 저장|고지 구성|연계 확인|예외 판정|구성|확인|검증|조회|처리|기능)\s*$",
        "",
        base,
    ).strip()
    stem = stem or base or "업무"
    suffixes = (
        "조건 검증",
        "결과 구성",
        "이력 저장",
        "고지 구성",
        "연계 확인",
        "예외 판정",
    )
    suffix = suffixes[index % len(suffixes)]
    if stem.endswith("조건") and suffix.startswith("조건 "):
        suffix = suffix.removeprefix("조건 ").strip()
    return limit_text_for_policy(f"{stem} {suffix}", 70)


def density_function_name_for_process(process_name: object, template_name: str) -> str:
    stem = collapse_repeated_label_tokens(process_name)
    stem = re.sub(
        r"\s*(처리 기준 확인|기준 검증|조건 검증|정보 구성|조건 확인|결과 확인|연계 결과 확인|구성|확인|검증|조회|판정|처리|기능)\s*$",
        "",
        stem,
    ).strip()
    stem = stem or str(process_name or "업무").strip() or "업무"
    return limit_text_for_policy(f"{stem} {template_name}", 70)


def default_policy_names(spec: dict, runtime: Optional[AgentRuntime]) -> List[str]:
    if runtime is not None:
        names = [
            str(group.get("name", "")).strip()
            for group in runtime.target_spec.get("policy_groups", [])
            if isinstance(group, dict) and str(group.get("name", "")).strip()
        ]
        if names:
            return names
    return [
        str(group.get("name", "")).strip()
        for group in spec.get("policy_groups", [])
        if isinstance(group, dict) and str(group.get("name", "")).strip()
    ]


def policy_derivation_matrix_for_prompt(spec: Mapping[str, object], max_rows: int = 36) -> List[dict]:
    """Compact process/function to policy need matrix for the Policies Agent."""
    functions_by_process = functions_grouped_by_process(dict(spec))
    function_details_by_id = {
        str(detail.get("function_id", "")).strip(): detail
        for detail in spec.get("function_details", [])
        if isinstance(detail, Mapping) and str(detail.get("function_id", "")).strip()
    }
    rows: List[dict] = []
    for process in spec.get("processes", []):
        if not isinstance(process, Mapping):
            continue
        process_id = str(process.get("id", "")).strip()
        process_functions = functions_by_process.get(process_id, [])
        function_summaries: List[str] = []
        combined_parts = [str(process.get("name", "")), str(process.get("description", ""))]
        for function in process_functions[:6]:
            if not isinstance(function, Mapping):
                continue
            function_id = str(function.get("id", "")).strip()
            function_name = str(function.get("name", "")).strip()
            details = function_details_by_id.get(function_id, {})
            text_parts = [
                function_name,
                str(function.get("description", "")),
                " ".join(str(item) for item in function.get("details", []) if str(item).strip())
                if isinstance(function.get("details", []), list)
                else "",
                " ".join(str(item) for item in details.get("processing_logic", []) if str(item).strip())
                if isinstance(details.get("processing_logic", []), list)
                else "",
                " ".join(str(item) for item in details.get("failure_exception_cases", []) if str(item).strip())
                if isinstance(details.get("failure_exception_cases", []), list)
                else "",
            ]
            combined_parts.extend(text_parts)
            function_summaries.append(limit_text_for_policy(" ".join(item for item in (function_id, function_name) if item), 70))
        required = derive_policy_needs_from_text(" ".join(combined_parts))
        if not required:
            required = [{"policy_axis": "처리 결과·이력", "item_candidates": ["결과 유형", "고객 안내 항목", "이력 저장 항목"]}]
        rows.append(
            {
                "process_id": process_id,
                "process_name": limit_text_for_policy(process.get("name", ""), 60),
                "functions": function_summaries[:5],
                "required_policy_axes": required[:4],
            }
        )
        if len(rows) >= max_rows:
            break
    return rows


def derive_policy_needs_from_text(text: str) -> List[dict]:
    rules = [
        (("인증", "본인", "PASS", "인증번호", "동의"), "인증·동의", ["인증 수단", "인증 가능 횟수", "인증번호 유효시간", "동의 저장 항목", "인증 실패 처리"]),
        (("조회", "노출", "표시", "안내", "정보", "기준일"), "대상 정보 노출", ["노출 대상", "노출 제한 대상", "기준일 표시", "노출 채널", "비노출 대상"]),
        (("상태", "가능", "검증", "판정", "제한", "자격"), "가능 여부 검증", ["검증 필수 항목", "가능 판정 조건", "제한 사유", "재검증 기준", "판정 수행 시스템"]),
        (("입력", "선택", "값", "폼", "필수"), "입력값 검증", ["필수 입력 항목", "입력 허용 범위", "오류 안내 항목", "민감정보 제한"]),
        (("요금", "혜택", "약정", "할인", "비용", "쿠폰", "포인트", "영향"), "영향도 고지", ["고지 필수 항목", "고지 시점", "예상값 기준", "고객 확인 조건"]),
        (("요청", "접수", "처리", "중복", "재요청"), "처리 요청 접수", ["접수 조건", "요청 상태값", "중복 판단 기준", "재요청 허용 조건"]),
        (("완료", "결과", "반영", "저장", "이력", "알림"), "처리 결과·이력", ["결과 유형", "고객 안내 항목", "이력 저장 항목", "알림 채널"]),
        (("실패", "오류", "장애", "예외", "보류", "상담"), "예외·상담 전환", ["상담 전환 대상", "재시도 허용 횟수", "장애 안내 항목", "예외 이력 저장 항목"]),
        (("BSS", "연계", "회신", "원장"), "BSS 연계 판정", ["조회 대상", "판정 우선순위", "결과 반영 조건", "실패 처리 방식"]),
        (("개인정보", "민감", "로그", "마스킹", "보관", "파기"), "개인정보·로그 보호", ["민감정보 제한", "마스킹 기준", "보관 기간", "열람 통제", "파기 이력 저장 항목"]),
        (("운영", "관리", "품질", "모니터링", "변경", "승인"), "운영 관리", ["관리 대상", "승인 조건", "변경 이력 저장 항목", "모니터링 주기"]),
    ]
    result: List[dict] = []
    for keywords, policy_axis, item_candidates in rules:
        if any(keyword in text for keyword in keywords):
            result.append({"policy_axis": policy_axis, "item_candidates": item_candidates})
    return result


def is_system_actor_name(name: str) -> bool:
    if any(keyword in name for keyword in ("고객", "운영자", "법정대리인", "대리인", "관리자", "상담사")):
        return False
    return any(
        keyword in name
        for keyword in (
            "BSS",
            "시스템",
            "기관",
            "연계",
            "엔진",
            "채널 업무",
            "채널 서비스",
            "제휴사",
            "배송사",
            "결제기관",
            "외부",
        )
    )


def is_human_actor_name(name: str) -> bool:
    return any(keyword in name for keyword in ("고객", "운영자", "법정대리인", "대리인", "관리자", "상담사")) and not is_system_actor_name(name)


CUSTOMER_CONDITION_ACTOR_PATTERNS = (
    re.compile(r"(로그인|비로그인|정상|제한|휴면|미성년|성인|VIP|우수|일반|신규|기존|개인|법인)\s*고객"),
    re.compile(r"고객\s*(상태|등급|유형|세그먼트)"),
)
DETAILED_OPERATOR_PREFIXES = (
    "전시",
    "상품",
    "콘텐츠",
    "쿠폰",
    "멤버십",
    "마케팅",
    "이벤트",
    "미션",
    "보상",
    "검색",
    "추천",
    "데이터",
    "태깅",
    "알림",
    "배포",
    "승인",
    "검수승인",
    "정산",
    "카테고리",
    "혜택",
)
ALLOWED_OPERATOR_ACTOR_NAMES = {"운영자", "제휴처 운영자"}
ALLOWED_HUMAN_ACTOR_NAMES = {
    "고객",
    "운영자",
    "상담사",
    "법정대리인",
    "대리인",
    "관리자",
    "품질 검수자",
    "제휴처 운영자",
}
DETAILED_SYSTEM_ACTOR_MARKERS = (
    "AI 검색 엔진",
    "추천 엔진",
    "AI 추천 엔진",
    "상품 마스터",
    "지식 베이스",
    "알림센터",
    "장바구니 시스템",
    "검색 시스템",
    "추천 시스템",
    "상품정보 시스템",
    "혜택 시스템",
    "주문 시스템",
    "재고 시스템",
    "결제 시스템",
    "상담 시스템",
    "데이터 플랫폼",
)
GENERAL_SYSTEM_ACTOR_NAMES = {
    "BSS",
    "인증기관",
    "연계 시스템",
    "채널 업무 시스템",
    "BSS/연계 시스템",
}
COMPOSITE_HUMAN_ACTOR_SEPARATOR_PATTERN = re.compile(
    r"(고객|운영자|상담사|관리자|법정대리인|대리인)\s*(?:/|·|,|및)\s*"
    r"(고객|운영자|상담사|관리자|법정대리인|대리인)"
)


def actor_granularity_violation_reason(name: str) -> str:
    text = normalize_space(name)
    if not text:
        return ""
    if is_composite_human_actor_name(text):
        return "여러 사람 책임 주체를 '/'·'및' 등으로 묶은 복합 액터는 금지합니다. 책임이 같으면 하나의 책임명으로 통합하고, 다르면 별도 액터로 분리하세요."
    for pattern in CUSTOMER_CONDITION_ACTOR_PATTERNS:
        if pattern.search(text):
            return "로그인 여부, 고객 상태, 등급, 세그먼트는 액터가 아니라 상태·권한 조건·정책 상세로 관리해야 합니다."
    if is_detailed_internal_operator_actor(text):
        return "세부 내부 운영 역할은 기본적으로 '운영자'로 통합하고, 역할 차이는 유즈케이스 설명·기능·정책 항목으로 내려 작성해야 합니다."
    if is_detailed_system_actor(text):
        return "세부 엔진·저장소·업무 시스템은 독립 액터보다 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합하는 것이 안전합니다."
    return ""


def is_composite_human_actor_name(name: str) -> bool:
    text = normalize_space(name)
    if not text:
        return False
    return bool(COMPOSITE_HUMAN_ACTOR_SEPARATOR_PATTERN.search(text))


def is_detailed_internal_operator_actor(name: str) -> bool:
    text = normalize_space(name)
    if not text or text in ALLOWED_OPERATOR_ACTOR_NAMES:
        return False
    if "운영자" not in text and "관리자" not in text:
        return False
    if text in ALLOWED_HUMAN_ACTOR_NAMES:
        return False
    if "제휴처" in text:
        return False
    return any(prefix in text for prefix in DETAILED_OPERATOR_PREFIXES)


def is_detailed_system_actor(name: str) -> bool:
    text = normalize_space(name)
    if not text or text in GENERAL_SYSTEM_ACTOR_NAMES:
        return False
    if "·BSS 연계 시스템" in text or "/BSS 연계 시스템" in text:
        return False
    if text.endswith("연계 시스템") and "BSS" in text:
        return False
    return any(marker in text for marker in DETAILED_SYSTEM_ACTOR_MARKERS)


def density_profile_for_runtime(runtime: Optional[AgentRuntime]) -> object | None:
    if runtime is None:
        return None
    target_spec = getattr(runtime, "target_spec", None)
    profile = density_profile_from_spec(target_spec) if isinstance(target_spec, Mapping) else None
    if profile:
        return profile
    return density_profile_from_spec(getattr(runtime, "spec", None))


def usecase_count_limits(runtime: Optional[AgentRuntime]) -> tuple[int, int]:
    profile = density_profile_for_runtime(runtime)
    template_type = str(getattr(getattr(runtime, "ctx", None), "template_type", "") or "").strip().lower()
    default_total = profile.max_usecases_total if profile else 13 if template_type == "full" else 11
    default_y = profile.max_usecases_y if profile else 8 if template_type == "full" else 6
    total = parse_positive_int_env("NC_USECASE_MAX_TOTAL", default_total)
    y_count = parse_positive_int_env("NC_USECASE_MAX_Y", default_y)
    return total, y_count


def state_count_limits(runtime: Optional[AgentRuntime]) -> tuple[int, int]:
    profile = density_profile_for_runtime(runtime)
    template_type = str(getattr(getattr(runtime, "ctx", None), "template_type", "") or "").strip().lower()
    default_states = profile.max_states if profile else 20 if template_type == "full" else 12
    default_transitions = profile.max_state_transitions if profile else 45 if template_type == "full" else 28
    states = parse_positive_int_env("NC_STATE_MAX_COUNT", default_states)
    transitions = parse_positive_int_env("NC_STATE_TRANSITION_MAX_COUNT", default_transitions)
    return states, transitions


def state_transition_overflow_tolerance(runtime: Optional[AgentRuntime]) -> int:
    template_type = str(getattr(getattr(runtime, "ctx", None), "template_type", "") or "").strip().lower()
    default_tolerance = 4 if template_type != "full" else 6
    return parse_positive_int_env("NC_STATE_TRANSITION_OVERFLOW_TOLERANCE", default_tolerance)


def default_state_transition_usecase_id(spec: Mapping[str, object]) -> str:
    usecases = spec.get("usecases", [])
    if not isinstance(usecases, list):
        return ""
    for usecase in usecases:
        if not isinstance(usecase, Mapping):
            continue
        usecase_id = str(usecase.get("id", "")).strip()
        if usecase_id and str(usecase.get("process_target", "")).strip().upper() == "Y":
            return usecase_id
    for usecase in usecases:
        if isinstance(usecase, Mapping) and str(usecase.get("id", "")).strip():
            return str(usecase.get("id", "")).strip()
    return ""


def transition_usecase_ids_value(transition: Mapping[str, object]) -> List[str]:
    values = transition.get("usecase_ids")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    legacy = str(transition.get("usecase_id", "")).strip()
    return [legacy] if legacy else []


STATE_TERM_NAME_KEYWORDS = (
    "진입 전",
    "처리 중",
    "판정 중",
    "분석 중",
    "생성 중",
    "진행 중",
    "대기",
    "접수",
    "완료",
    "성공",
    "실패",
    "제한",
    "보류",
    "필요",
    "만료",
    "취소",
    "종료",
    "확정",
    "유예",
    "정상",
    "휴면",
    "탈퇴",
    "가입제한",
    "재가입제한",
    "수락",
    "거절",
    "열람",
    "전달",
    "운영 검토",
    "운영 확인",
    "반영 완료",
    "상담 전환",
    "무결과",
    "저신뢰",
)
STATE_TERM_DESCRIPTION_SIGNALS = (
    "인 상태",
    "된 상태",
    "하는 상태",
    "상태로",
    "상태를",
    "상태가",
    "상태에서",
    "표시 상태",
    "고객 표시 상태",
    "업무 가능 여부",
)
STATE_TERM_EXCLUDED_SUFFIXES = (
    "상태",
    "흐름",
    "기준",
    "정보",
    "이력",
    "정책",
    "처리",
    "유형",
    "대상",
    "방식",
    "조건",
    "목록",
    "회원",
    "고객",
    "자격",
    "권한",
    "여부",
)
TERMINAL_STATE_KEYWORDS = ("완료", "취소", "종료", "확정", "반영 완료", "탈퇴완료", "수락 완료")
TERMINAL_CONFIRMATION_KEYWORDS = (
    "확정",
    "완료",
    "성공",
    "승인",
    "최종",
    "상태 변경",
    "반영",
    "종료",
    "전환",
    "처리 결과",
)


def state_term_candidates(spec: Mapping[str, object], *, limit: int = 24) -> List[dict]:
    candidates: List[dict] = []
    seen: set[str] = set()
    for term in spec.get("terms", []):
        if not isinstance(term, Mapping):
            continue
        name = clean_policy_text(term.get("name", ""))
        description = clean_policy_text(term.get("description", ""))
        if not is_state_value_term(name, description) or name in seen:
            continue
        seen.add(name)
        candidates.append(
            {
                "name": name,
                "description": limit_text_for_policy(description, 140),
                "rule": "상태로 채택하면 states.name에 이 이름을 그대로 사용한다.",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def is_state_value_term(name: str, description: str) -> bool:
    if not name or len(name) > 24:
        return False
    if name.endswith(STATE_TERM_EXCLUDED_SUFFIXES):
        return False
    text = f"{name} {description}"
    has_state_signal = any(signal in description for signal in STATE_TERM_DESCRIPTION_SIGNALS)
    has_name_signal = any(keyword in name for keyword in STATE_TERM_NAME_KEYWORDS)
    if not has_state_signal and not has_name_signal:
        return False
    if len(name) <= 1:
        return False
    return True


def state_term_contract_errors_for_payload(spec: Mapping[str, object], runtime: Optional[AgentRuntime]) -> List[str]:
    max_states, _ = state_count_limits(runtime)
    candidates = state_term_candidates(spec, limit=max_states + 4)
    state_names = [
        clean_policy_text(state.get("name", ""))
        for state in spec.get("states", [])
        if isinstance(state, Mapping) and clean_policy_text(state.get("name", ""))
    ]
    errors: List[str] = []
    conflicts = state_term_name_variant_conflicts(candidates, state_names)
    if conflicts:
        errors.append("상태 후보 용어를 변형하지 말아야 합니다: " + ", ".join(conflicts[:6]))
    return errors


def state_usecase_lifecycle_errors_for_payload(
    spec: Mapping[str, object],
    transitions: object | None = None,
) -> List[str]:
    actor_usecases = {
        str(usecase.get("id", "")).strip(): str(usecase.get("name", "")).strip()
        for usecase in spec.get("usecases", [])
        if isinstance(usecase, Mapping)
        and str(usecase.get("id", "")).strip()
        and usecase_requires_state_transition(usecase)
    }
    if not actor_usecases:
        return []
    covered: set[str] = set()
    transition_rows = transitions if transitions is not None else spec.get("state_transitions", [])
    for transition_row in transition_rows if isinstance(transition_rows, list) else []:
        if not isinstance(transition_row, Mapping):
            continue
        covered.update(transition_usecase_ids_value(transition_row))
    missing = sorted(usecase_id for usecase_id in actor_usecases if usecase_id not in covered)
    if not missing:
        return []
    return [
        "액터 유즈케이스가 상태 전이 usecase_ids에 없습니다: "
        + ", ".join(f"{usecase_id} {actor_usecases[usecase_id]}" for usecase_id in missing[:6])
    ]


def state_term_name_variant_conflicts(candidates: Sequence[Mapping[str, object]], state_names: Sequence[str]) -> List[str]:
    conflicts: List[str] = []
    state_name_set = set(state_names)
    for candidate in candidates:
        name = str(candidate.get("name", "")).strip()
        if not name or name in state_name_set:
            continue
        for state_name in state_names:
            if not state_name or state_name == name:
                continue
            if name in state_name or state_name in name:
                conflicts.append(f"{name} -> {state_name}")
                break
    return conflicts


def transition_mixes_possibility_with_terminal_result(transition: Mapping[str, object]) -> bool:
    next_state = str(transition.get("next_state", "")).strip()
    if not any(keyword in next_state for keyword in TERMINAL_STATE_KEYWORDS):
        return False
    text = f"{transition.get('event', '')} {transition.get('criteria', '')}"
    if "가능" not in text:
        return False
    return not any(keyword in text for keyword in TERMINAL_CONFIRMATION_KEYWORDS)


def transition_event_matches_linked_usecases(
    transition: Mapping[str, object],
    usecases: Sequence[Mapping[str, object]],
) -> bool:
    """Legacy compatibility check.

    State transition traceability is now carried by usecase_ids. The event
    itself should be a concrete business trigger, so this check only ensures
    the linked usecases exist and the event is not empty.
    """
    linked_ids = set(transition_usecase_ids_value(transition))
    if not linked_ids:
        return False
    linked_count = sum(
        1
        for usecase in usecases
        if str(usecase.get("id", "")).strip() in linked_ids
    )
    return linked_count > 0 and bool(str(transition.get("event", "")).strip())


STATE_TRANSITION_REQUIRED_MARKERS = (
    "가입",
    "탈퇴",
    "해지",
    "변경",
    "취소",
    "만료",
    "승인",
    "완료",
    "제한",
    "보류",
    "실패",
    "복구",
    "전환",
    "상태",
    "원장",
    "반영",
    "정지",
    "휴면",
    "해제",
    "수락",
    "거절",
    "주문",
    "결제",
    "환불",
)


def usecase_requires_state_transition(usecase: Mapping[str, object]) -> bool:
    """Return True when a usecase likely changes durable business/customer state."""
    text = " ".join(
        str(usecase.get(key, "")).strip()
        for key in ("name", "description")
        if str(usecase.get(key, "")).strip()
    )
    return any(marker in text for marker in STATE_TRANSITION_REQUIRED_MARKERS)


def canonicalize_state_transition_events(spec: MutableMapping[str, object], payload: Mapping[str, object]) -> None:
    """Normalize transition event text without replacing business triggers with usecase names."""
    usecases = [item for item in spec.get("usecases", []) if isinstance(item, Mapping)]
    names_by_id = {
        str(usecase.get("id", "")).strip(): str(usecase.get("name", "")).strip()
        for usecase in usecases
        if str(usecase.get("id", "")).strip() and str(usecase.get("name", "")).strip()
    }
    payload_transitions = payload.get("state_transitions", [])
    if not isinstance(payload_transitions, list):
        return
    spec_transitions = spec.get("state_transitions", [])
    if not isinstance(spec_transitions, list):
        spec_transitions = []

    for index, transition in enumerate(payload_transitions):
        if not isinstance(transition, dict):
            continue
        linked_names = [
            names_by_id[value]
            for value in transition_usecase_ids_value(transition)
            if value in names_by_id
        ]
        original_event = str(transition.get("event", "")).strip()
        if original_event:
            transition["event"] = original_event
            continue
        fallback_event = " / ".join(unique_nonempty(linked_names))
        if fallback_event:
            transition["event"] = fallback_event
            if index < len(spec_transitions) and isinstance(spec_transitions[index], dict):
                spec_transitions[index]["event"] = fallback_event


def event_is_usecase_name(event: str, linked_names: Sequence[str]) -> bool:
    normalized_event = normalize_event_usecase_name(event)
    allowed = {normalize_event_usecase_name(name) for name in linked_names if normalize_event_usecase_name(name)}
    if not normalized_event or not allowed:
        return False
    if normalized_event in allowed:
        return True
    parts = [
        normalize_event_usecase_name(part)
        for part in re.split(r"\s*(?:/|,|·|\|| 및 | 와 | 과 )\s*", event)
        if normalize_event_usecase_name(part)
    ]
    return bool(parts) and all(part in allowed for part in parts)


def normalize_event_usecase_name(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def parse_positive_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return max(1, int(value))
    except ValueError:
        return default


def is_step_like_usecase_name(name: str) -> bool:
    text = str(name or "")
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return False
    if re.search(r"요청\s*및\s*결과\s*확인\s*$", text):
        return True
    if is_composite_business_usecase_name(text):
        return False
    exact_step_names = {
        "대상확인",
        "조건확인",
        "가능여부확인",
        "유형선택",
        "정보입력",
        "요청정보입력",
        "처리요청",
        "요청접수",
        "약관동의",
        "최종확인",
        "본인확인",
        "본인인증",
        "인증",
        "복귀",
        "사유확인",
        "차단사유확인",
        "제한사유확인",
        "완료",
        "완료확인",
        "처리완료",
        "결과확인",
        "결과안내",
        "후속조치",
    }
    if compact in exact_step_names:
        return True
    step_keywords = (
        "대상 확인",
        "조건 확인",
        "가능 여부",
        "유형 선택",
        "정보 입력",
        "요청 정보",
        "처리 요청",
        "요청 접수",
        "약관 동의",
        "최종 확인",
        "본인확인",
        "복귀",
        "사유 확인",
        "차단 사유",
        "제한 사유",
        "결과 확인",
        "결과 안내",
        "후속 조치",
    )
    auth_step_keywords = (
        "본인인증",
        "본인확인",
        "추가인증",
        "재인증",
        "명의인증",
        "회선인증",
        "카드인증",
        "계좌인증",
        "인증번호",
        "인증결과",
        "인증상태",
        "인증복귀",
        "인증완료",
        "인증수행",
    )
    if any(keyword in text for keyword in step_keywords):
        return True
    return any(keyword in compact for keyword in auth_step_keywords) or compact == "인증"


def is_composite_business_usecase_name(name: str) -> bool:
    text = str(name or "").strip()
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 20:
        return False
    if not re.search(r"(?:\s및\s|/|·|,)", text):
        return False
    business_markers = (
        "가입",
        "탈퇴",
        "신청",
        "변경",
        "해지",
        "취소",
        "주문",
        "주문서",
        "계약",
        "결제",
        "환불",
        "배송",
        "반품",
        "교환",
        "상품",
        "서비스",
        "BP",
        "목록",
        "상세",
        "검색",
        "추천",
        "혜택",
        "쿠폰",
        "포인트",
        "이벤트",
        "미션",
        "참여",
        "멤버십",
        "알림",
        "상담",
        "고객센터",
        "매장",
        "인증",
        "연동",
        "공유",
        "관리",
        "등록",
        "검수",
        "승인",
        "데이터",
        "트래킹",
        "청구",
        "수납",
        "약관",
        "동의",
        "개인정보",
        "고객",
        "경험",
        "회원정보",
        "주소록",
    )
    decision_markers = (
        "대상",
        "조건",
        "가능",
        "기준",
        "유형",
        "상태",
        "결과",
        "예외",
        "제한",
        "권한",
        "안내",
        "점검",
        "지원",
        "조회",
        "제공",
        "적용",
        "표준",
        "사전",
        "진입",
        "종료",
        "검증",
        "판정",
        "분기",
        "흐름",
        "처리",
        "이력",
        "고지",
        "회신",
        "확정",
    )
    business_score = sum(1 for marker in business_markers if marker in compact)
    decision_score = sum(1 for marker in decision_markers if marker in compact)
    return business_score >= 1 and decision_score >= 1 and (business_score + decision_score) >= 3


def looks_incomplete_policy_sentence(value: object) -> bool:
    text = clean_policy_text(value).rstrip(".。.!?")
    if not text:
        return True
    return any(text.endswith(tail) for tail in INCOMPLETE_SENTENCE_TAILS)


def has_system_responsibility_marker(value: object) -> bool:
    text = clean_policy_text(value)
    return any(marker in text for marker in SYSTEM_RESPONSIBILITY_MARKERS)


def is_generic_system_usecase(usecase: Mapping[str, object], actor_name: str) -> bool:
    if not is_system_actor_name(actor_name):
        return False
    name = clean_policy_text(usecase.get("name", ""))
    description = clean_policy_text(usecase.get("description", ""))
    generic_names = {
        "지원 처리",
        "업무 지원",
        f"{actor_name} 지원 처리",
        f"{actor_name} 업무 지원",
    }
    generic_description_markers = (
        "업무에 필요한 책임을 수행하고 결과를 제공",
        "필요한 책임을 수행하고 결과를 제공",
    )
    return name in generic_names or any(marker in description for marker in generic_description_markers)


def default_usecase_for_actor(actor_name: str, topic: str) -> tuple[str, str]:
    topic_label = topic or "해당"
    actor_subject = korean_subject(actor_name)
    if "BSS" in actor_name:
        return (
            "BSS 판정 및 결과 회신",
            "BSS가 업무 가능 여부와 원장 반영 필요성을 판정하고 처리 결과를 채널에 회신하는 보조 유즈케이스",
        )
    if "인증" in actor_name or "기관" in actor_name:
        return (
            "인증 결과 제공",
            "인증기관이 본인 확인 또는 권한 검증 결과를 생성해 채널과 BSS 판정에 필요한 근거를 제공하는 보조 유즈케이스",
        )
    if "AI" in actor_name or "엔진" in actor_name:
        return (
            "후보 생성 및 분류 결과 제공",
            "AI 또는 엔진이 요청 의도를 분류하고 후보 결과를 생성해 채널 업무 시스템의 최종 안내를 지원하는 보조 유즈케이스",
        )
    if "연계" in actor_name or "외부" in actor_name or "제휴" in actor_name:
        return (
            "외부 기준 정보 및 결과 회신",
            "연계 시스템이 외부 기준 정보, 승인·처리 결과, 콜백을 제공하고 채널 업무 시스템의 상태 반영을 지원하는 보조 유즈케이스",
        )
    if "채널 업무" in actor_name or "시스템" in actor_name:
        return (
            "채널 요청 접수 및 상태·이력 반영",
            "채널 업무 시스템이 고객 입력, 세션, 요청 전달, 결과 상태, 처리 이력을 관리하고 최종 판정은 BSS 또는 연계 결과를 따른다.",
        )
    if is_system_actor_name(actor_name):
        return (
            "처리 결과 회신",
            "시스템 액터가 검증·조회·처리 결과를 생성해 채널 업무 흐름의 후속 판단을 지원하는 보조 유즈케이스",
        )
    if "운영" in actor_name or "관리자" in actor_name:
        return (
            "운영 기준 관리 및 예외 확인",
            f"{actor_subject} {topic_label} 업무의 운영 기준을 관리하고 자동 처리 예외를 확인해 후속 조치를 완료하는 유즈케이스",
        )
    if "약관" in topic_label:
        return (
            "고객 동의·권리 관리",
            f"{actor_subject} 필수·선택 동의 상태, 약관 변경 영향, 철회·재동의 가능 여부를 확인하고 필요한 후속 업무를 완료하는 유즈케이스",
        )
    return (
        f"{topic_label} 업무 수행",
        f"{actor_subject} {topic_label} 업무의 대상, 가능 조건, 처리 영향, 완료 상태를 확인해 고객 과업을 완료하는 유즈케이스",
    )


def korean_subject(value: object) -> str:
    text = clean_policy_text(value)
    if not text:
        return ""
    return f"{text}{korean_subject_particle(text)}"


def korean_subject_particle(value: object) -> str:
    text = clean_policy_text(value)
    if not text:
        return "가"
    char = text[-1]
    code = ord(char)
    if 0xAC00 <= code <= 0xD7A3:
        return "이" if (code - 0xAC00) % 28 else "가"
    return "가"


def ambiguous_state_branch_sources(transitions: object) -> List[str]:
    if not isinstance(transitions, list):
        return []
    grouped: dict[str, List[Mapping[str, object]]] = {}
    for transition in transitions:
        if not isinstance(transition, Mapping):
            continue
        current = str(transition.get("current_state", "")).strip()
        if current:
            grouped.setdefault(current, []).append(transition)
    priority_keywords = ("우선", "먼저", "순위", "배타", "하나라도", "모두", "없고", "있는 경우", "없는 경우", "그 외")
    exception_keywords = ("실패", "제한", "보류", "불일치", "오류", "중단", "만료", "취소", "누락", "충돌", "예외")
    ambiguous: List[str] = []
    for current, rows in grouped.items():
        if len(rows) < 4:
            continue
        joined = " ".join(str(row.get("event", "")) + " " + str(row.get("criteria", "")) for row in rows)
        exception_count = sum(
            1
            for row in rows
            if any(keyword in f"{row.get('event', '')} {row.get('criteria', '')}" for keyword in exception_keywords)
        )
        if exception_count >= 2 and not any(keyword in joined for keyword in priority_keywords):
            ambiguous.append(current)
    return ambiguous


def minimum_process_count_for_usecase(usecase: Mapping[str, object], density_profile: object | None = None) -> int:
    return process_minimum_for_usecase(usecase.get("actor", ""), usecase.get("name", ""), density_profile)


def process_templates_for_usecase(usecase: Mapping[str, object]) -> List[dict]:
    actor = str(usecase.get("actor", "")).strip()
    usecase_name = str(usecase.get("name", "")).strip() or "업무"
    if "운영" in actor or "관리자" in actor:
        return [
            {
                "name": "운영 기준 확인",
                "description": f"운영자가 {usecase_name}에 필요한 기준 정보와 적용 범위를 확인한다.",
            },
            {
                "name": "기준·예외 등록",
                "description": f"운영자가 {usecase_name} 기준값, 예외 조건, 적용 기간을 등록하거나 보정한다.",
            },
            {
                "name": "승인·배포 및 이력 관리",
                "description": f"{usecase_name} 변경 내용을 승인 상태로 배포하고 변경 이력과 품질 지표를 저장한다.",
            },
        ]
    is_notification_usecase = usecase_name.startswith("통합 알림") or (
        "알림" in usecase_name and any(keyword in usecase_name for keyword in ("수신", "알림함", "후속", "발송", "권한", "복구"))
    )
    is_customer_center_hub_usecase = "고객센터" in usecase_name or (
        any(keyword in usecase_name for keyword in ("셀프 해결", "상담", "문의", "후속 관리"))
        and any(keyword in usecase_name for keyword in ("허브", "접수", "전환", "고객센터"))
    )
    is_customer_center_store_usecase = any(
        keyword in usecase_name for keyword in ("매장", "대리점", "지점", "방문", "예약")
    ) and not any(keyword in usecase_name for keyword in ("FAQ", "공지", "이용안내", "통합허브"))
    is_customer_center_faq_notice_usecase = any(
        keyword in usecase_name for keyword in ("FAQ", "공지", "이용안내", "가이드", "도움 콘텐츠")
    ) and "통합허브" not in usecase_name
    if is_customer_center_store_usecase:
        if any(keyword in usecase_name for keyword in ("예외", "대체", "제한", "후속")):
            return [
                {
                    "name": "매장 이용 제한 사유 확인",
                    "description": "고객이 휴무, 폐점, 예약 불가, 처리 불가 업무, 위치 정보 미동의 등 매장 이용 제한 사유를 확인한다.",
                },
                {
                    "name": "대체 매장·온라인 경로 안내",
                    "description": "채널이 고객 위치, 처리 가능 업무, 운영시간을 기준으로 대체 매장, 온라인 처리, 상담 연결 중 가능한 경로를 제시한다.",
                },
                {
                    "name": "정보 불일치·장애 신고 접수",
                    "description": "매장 정보, 운영시간, 위치, 처리 가능 업무가 실제와 다르면 신고 또는 상담 접수 경로를 안내한다.",
                },
                {
                    "name": "후속 안내 및 이력 저장",
                    "description": "선택한 대체 경로, 제한 사유, 재조회 가능 여부, 상담 전환 여부를 고객 이력으로 저장한다.",
                },
            ]
        if any(keyword in usecase_name for keyword in ("예약", "방문 준비", "준비")):
            return [
                {
                    "name": "방문 업무와 예약 가능 여부 확인",
                    "description": "고객이 처리하려는 업무가 해당 매장에서 가능한지, 예약 또는 대기 접수가 가능한지 확인한다.",
                },
                {
                    "name": "방문 시간·대기 조건 선택",
                    "description": "고객이 운영시간, 휴무일, 혼잡도, 예약 가능 시간, 예상 대기 기준을 확인하고 방문 시점을 선택한다.",
                },
                {
                    "name": "본인확인·구비서류 사전 안내",
                    "description": "방문 업무에 필요한 본인확인, 법정대리인·대리 권한, 구비서류, 처리 제한 조건을 사전에 안내한다.",
                },
                {
                    "name": "예약 결과 및 변경·취소 기준 안내",
                    "description": "예약 또는 방문 준비 결과와 변경·취소 가능 시간, 미방문 영향, 대체 경로를 안내하고 이력을 저장한다.",
                },
            ]
        return [
            {
                "name": "방문 목적 및 위치 기준 선택",
                "description": "고객이 방문 목적, 현재 위치 사용 여부, 단골 매장, 지역·지하철·매장명 검색 기준을 선택한다.",
            },
            {
                "name": "매장 검색·속성 필터 적용",
                "description": "채널이 거리순, 지역, 매장 속성, 바로픽업, 주차, 외국어, 기기 체험존 등 필터를 적용해 후보 매장을 조회·정렬한다.",
            },
            {
                "name": "운영시간·처리 가능 업무 확인",
                "description": "고객이 후보 매장의 영업시간, 휴무일, 연락처, 제공 서비스, 처리 가능 업무, 예약 가능 여부를 확인한다.",
            },
            {
                "name": "방문 경로 및 필요 준비물 확인",
                "description": "고객이 방문 경로, 구비서류, 대리 권한, 온라인 대체 가능 여부, 상담 연결 필요 여부를 확인한다.",
            },
        ]
    if is_customer_center_faq_notice_usecase:
        if "공지·변경" in usecase_name or usecase_name.startswith("공지"):
            return [
                {
                    "name": "공지 유형 및 영향 범위 확인",
                    "description": "고객이 일반 안내, 중요 변경, 긴급 공지, 장애·점검 공지 중 어떤 유형인지 확인하고 본인 회선·지역·상품 영향 여부를 판단한다.",
                },
                {
                    "name": "변경 핵심 및 적용 시점 확인",
                    "description": "공지의 변경 전후 핵심 차이, 적용일, 고객 행동 필요 여부, 예상 복구 시점 또는 상세 원문 경로를 확인한다.",
                },
                {
                    "name": "대체 행동 및 문의 경로 선택",
                    "description": "공지 영향이 있으면 재시도, 나중에 처리, 대체 채널, 문의·상담 연결 중 가능한 후속 행동을 선택한다.",
                },
                {
                    "name": "공지 확인 이력 및 후속 안내 저장",
                    "description": "확인한 공지, 영향 판단 결과, 후속 이동, 미해결 또는 문의 전환 여부를 이력으로 저장한다.",
                },
            ]
        if "후속" in usecase_name or "해결" in usecase_name:
            return [
                {
                    "name": "해결 가이드 상세 확인",
                    "description": "고객이 선택한 FAQ 또는 이용안내의 단계별 해결 가이드, 적용 대상, 준비 정보, 최신 기준일을 확인한다.",
                },
                {
                    "name": "관련 업무 바로가기 실행",
                    "description": "가이드 확인 후 조회, 설정, 신청, 변경, 셀프 처리 화면 중 현재 문제를 해결할 수 있는 화면으로 이동한다.",
                },
                {
                    "name": "해결 성공 여부 확인",
                    "description": "고객이 안내 수행 후 문제가 해결되었는지 확인하고 미해결 사유를 검색 실패, 정보 부족, 권한 제한, 시스템 오류로 분류한다.",
                },
                {
                    "name": "미해결 문의·상담 연결",
                    "description": "문제가 해결되지 않으면 콘텐츠명, 검색어, 선택 경로, 실패 사유를 유지해 문의 템플릿 또는 상담 경로로 연결한다.",
                },
            ]
        return [
            {
                "name": "도움 콘텐츠 목적 선택",
                "description": "고객이 FAQ, 이용안내, 가이드, 공지 중 현재 문제 해결 목적에 맞는 콘텐츠 유형과 카테고리를 선택한다.",
            },
            {
                "name": "FAQ·가이드 검색 및 추천",
                "description": "채널이 검색어, 문제 유형, 최근 급증 이슈, 고객 맥락을 기준으로 FAQ와 이용안내를 추천한다.",
            },
            {
                "name": "콘텐츠 최신성 및 해결 가능 여부 확인",
                "description": "고객이 콘텐츠의 최종 업데이트 기준일, 적용 대상, 셀프 해결 가능 여부, 상담 필요 여부를 확인한다.",
            },
            {
                "name": "다음 행동 또는 대체 탐색 선택",
                "description": "고객이 관련 화면 이동, 추가 FAQ 확인, 매장찾기, 문의·상담 연결 등 다음 행동을 선택한다.",
            },
        ]
    if is_customer_center_hub_usecase:
        if "문의" in usecase_name or "접수" in usecase_name:
            return [
                {
                    "name": "문의 유형 및 채널 선택",
                    "description": "고객이 문의 목적, 긴급도, 선호 채널, 첨부 필요 여부를 기준으로 상담 또는 1:1 문의 경로를 선택한다.",
                },
                {
                    "name": "필수 입력·첨부 정보 구성",
                    "description": "채널이 문의 유형별 필수 정보, 첨부 허용 기준, 개인정보 마스킹, 제출 가능 조건을 확인하고 누락·허용 불가 항목은 보완 요청 또는 접수 제한 기준으로 분류한다.",
                },
                {
                    "name": "인증·개인정보 동의 확인",
                    "description": "상담 또는 문의 처리에 필요한 본인확인, 대리 권한, 개인정보 제공 동의 여부를 확인한다.",
                },
                {
                    "name": "문의 접수 및 상태 생성",
                    "description": "문의 요청을 접수하고 접수, 확인, 조치 중, 답변 완료, 추가 정보 요청 상태를 생성한다.",
                },
                {
                    "name": "상담 연결 또는 대기 안내",
                    "description": "운영시간, 예상 대기, 상담 가능 범위, 대체 채널을 안내하고 상담 문맥과 접수 이력을 저장한다.",
                },
            ]
        if "후속" in usecase_name or "전환" in usecase_name:
            return [
                {
                    "name": "직전 과업·상담 문맥 확인",
                    "description": "고객의 직전 셀프 해결 시도, 오류·실패 사유, 문의 이력, 상담 이력을 확인한다.",
                },
                {
                    "name": "셀프 해결 실패 사유 분류",
                    "description": "셀프 해결 실패가 권한, 정보 부족, 시스템 오류, 처리 제한, 상담 필요 중 어디에 해당하는지 분류한다.",
                },
                {
                    "name": "상담 이관 정보 구성",
                    "description": "고객 KEY, 문제 유형, 입력 정보, 실패 사유, 준비 정보를 상담원 또는 콜센터로 전달할 문맥으로 구성한다.",
                },
                {
                    "name": "추가 정보 요청·응답 처리",
                    "description": "상담 또는 문의 처리에 추가 정보가 필요하면 요청 사유, 제출 기한, 미제출 영향을 안내한다.",
                },
                {
                    "name": "처리 결과 및 온라인 재유입 안내",
                    "description": "답변, 처리 완료, 보류, 상담 종료 후 고객이 앱·웹에서 이어서 할 수 있는 후속 행동을 안내한다.",
                },
            ]
        return [
            {
                "name": "문제 유형 및 현재 상태 확인",
                "description": "고객이 해결하려는 문제 유형과 현재 업무 상태를 선택하고 고객센터 허브가 처리 맥락을 확인한다.",
            },
            {
                "name": "셀프 해결 가능 범위 판정",
                "description": "채널이 고객 상태, 업무 조건, 준비 정보, 처리 가능 범위를 기준으로 셀프 해결 가능 여부를 판정한다.",
            },
            {
                "name": "Self 해결 카드 및 준비 정보 제시",
                "description": "셀프 해결이 가능하면 해결 카드, 필요 정보, 처리 전 영향, 예상 결과를 먼저 제시한다.",
            },
            {
                "name": "해결 실패 시 대체 경로 안내",
                "description": "셀프 해결이 실패하거나 제한되면 불가 사유와 재시도, 문의, 상담, 매장 등 대체 경로를 안내한다.",
            },
            {
                "name": "후속 상담·문의 연결",
                "description": "상담 또는 문의가 필요하면 직전 해결 시도와 실패 사유를 문맥으로 유지해 다음 채널에 전달한다.",
            },
        ]
    if is_notification_usecase:
        if "수신" in usecase_name or "설정" in usecase_name:
            return [
                {
                    "name": "수신 유형 및 채널 선택",
                    "description": "고객이 거래성, 보안, 혜택, 마케팅, 공지 알림 중 수신할 유형과 채널을 선택한다.",
                },
                {
                    "name": "필수·선택 알림 구분",
                    "description": "채널이 수신 거부 가능한 선택 알림과 반드시 제공해야 하는 필수·거래성 알림을 구분한다.",
                },
                {
                    "name": "OS 권한 및 연락처 확인",
                    "description": "푸시 권한, 대표 연락처, 개별 수신 연락처, 언어 설정을 확인하고 필요한 설정 이동 경로를 안내한다.",
                },
                {
                    "name": "조용한 시간·빈도 기준 적용",
                    "description": "고객 설정, 조용한 시간, 다시알림, 빈도 제한 기준을 적용해 수신 피로를 줄인다.",
                },
                {
                    "name": "수신 설정 반영 및 이력 저장",
                    "description": "변경 전후 수신 설정, 적용 시점, 예외 알림, 실패 사유를 이력으로 저장한다.",
                },
            ]
        if "후속" in usecase_name or "복구" in usecase_name:
            return [
                {
                    "name": "알림 유효성 및 처리 상태 확인",
                    "description": "알림이 아직 유효한지, 관련 업무가 이미 처리되었는지, 후속 행동이 필요한지 확인한다.",
                },
                {
                    "name": "중복·만료·무효 알림 정리",
                    "description": "동일 사건의 중복 알림, 만료된 알림, 처리 완료 알림을 병합하거나 무효 상태로 전환한다.",
                },
                {
                    "name": "발송 실패·수신 제한 복구",
                    "description": "권한 거부, 연락처 오류, 채널 장애, 고객 설정 제한에 따른 실패를 분류하고 재시도 가능 여부와 대체 안내 경로를 판정한다.",
                },
                {
                    "name": "상담 전환 및 문맥 전달",
                    "description": "셀프 처리가 어려우면 알림 유형, 발생 시점, 대상 업무 정보를 유지해 상담 또는 문의로 연결한다.",
                },
                {
                    "name": "후속 결과 및 이력 안내",
                    "description": "처리 완료, 실패, 보류, 상담 전환 결과와 다음 행동을 안내하고 이력을 저장한다.",
                },
            ]
        return [
            {
                "name": "알림함 진입 및 유형 확인",
                "description": "고객이 통합 알림함에서 주문, 결제, 혜택, 상담, 보안, 공지 등 확인할 알림 유형을 선택한다.",
            },
            {
                "name": "행동 필요 여부 및 우선순위 분류",
                "description": "채널이 납부 필요, 인증 필요, 만료 임박, 답변 확인처럼 후속 행동이 필요한 알림을 우선 분류한다.",
            },
            {
                "name": "알림 상세 및 컨텍스트 확인",
                "description": "고객이 알림 상세에서 발생 사유, 대상 서비스, 처리 기한, 후속 화면 이동에 필요한 컨텍스트를 확인한다.",
            },
            {
                "name": "후속 업무 진입 또는 보관",
                "description": "고객이 바로가기, 다시알림, 중요 표시, 삭제, 상담 전환 중 필요한 다음 행동을 선택한다.",
            },
        ]
    if "약관" in usecase_name or "동의" in usecase_name or "철회" in usecase_name:
        if "변경" in usecase_name or "철회" in usecase_name:
            return [
                {
                    "name": "변경·철회 대상 선택",
                    "description": f"고객이 {usecase_name} 대상 약관 또는 동의 목적을 선택한다.",
                },
                {
                    "name": "철회 가능 여부 판정",
                    "description": "채널이 필수·선택 구분, 서비스 영향, 재동의 필요 여부를 판정한다.",
                },
                {
                    "name": "변경·철회 요청 접수",
                    "description": "고객 확인 후 변경·철회 요청을 접수하고 적용 결과를 구분한다.",
                },
                {
                    "name": "동의 이력 및 고지 저장",
                    "description": "변경 전후 동의 상태, 약관 버전, 고지 확인 이력을 저장한다.",
                },
            ]
        if "권리" in usecase_name:
            return [
                {
                    "name": "약관 원문·요약 열람",
                    "description": "고객이 약관 원문, 요약, 적용 서비스와 채널 범위를 조회한다.",
                },
                {
                    "name": "개인정보 제공·위탁 고지 확인",
                    "description": "채널이 제3자 제공, 처리 위탁, 쿠키, 위치정보 고지 범위를 구분해 안내한다.",
                },
                {
                    "name": "거부권 및 미동의 영향 확인",
                    "description": "고객이 선택 동의 거부권과 미동의 시 제한되는 기능 범위를 확인한다.",
                },
                {
                    "name": "약관 버전·시행일 확인",
                    "description": "현재 적용 약관 버전, 시행일, 개정 이력, 재동의 필요 여부를 확인한다.",
                },
            ]
        if "필수" in usecase_name or "선택" in usecase_name:
            return [
                {
                    "name": "업무 유형별 동의 항목 확인",
                    "description": "고객이 주문, 가입, 위치, 마케팅, 개인화 등 업무 유형별 필요한 동의 항목을 확인한다.",
                },
                {
                    "name": "필수·선택 동의 구분",
                    "description": "채널이 필수 약관과 선택 동의를 구분하고 선택 동의는 목적별·서비스별로 분리한다.",
                },
                {
                    "name": "미동의 제한 범위 판정",
                    "description": "필수 동의 미완료 시 제한되는 단계와 선택 동의 거부 후에도 유지되는 기본 경험을 판정한다.",
                },
                {
                    "name": "동의 처리 및 증적 저장",
                    "description": "고객 확인 후 동의 처리 결과, 약관 버전, 고지 확인, 처리 시각을 증적으로 저장한다.",
                },
            ]
        return [
            {
                "name": "약관·권리 범위 확인",
                "description": f"고객이 {usecase_name}에 필요한 약관 유형과 권리 행사 범위를 확인한다.",
            },
            {
                "name": "필수·선택 동의 구분",
                "description": "채널이 필수 약관, 선택 동의, 개인정보 제공·위탁 고지 범위를 구분한다.",
            },
            {
                "name": "동의 상태 및 버전 확인",
                "description": "현재 동의 상태, 약관 버전, 재동의 필요 여부를 확인한다.",
            },
            {
                "name": "동의 결과 고지 및 이력 저장",
                "description": "동의 처리 결과와 고객 고지 확인 여부를 안내하고 증적을 저장한다.",
            },
        ]
    if "설정" in usecase_name:
        if "개인화" in usecase_name or "알림" in usecase_name:
            return [
                {
                    "name": "설정 목적 선택",
                    "description": "고객이 개인화, AI 도움, 알림 수신·표시 중 변경하려는 설정 목적을 선택한다.",
                },
                {
                    "name": "적용 범위 확인",
                    "description": "채널이 동의 상태, 표시 채널, 데이터 활용 범위, 기본값 적용 여부를 확인한다.",
                },
                {
                    "name": "설정값 변경 접수",
                    "description": "고객이 선택한 설정값을 접수하고 중복·충돌 조건을 검증한다.",
                },
                {
                    "name": "설정 결과 반영",
                    "description": "변경 결과를 개인화 노출, 알림 수신, 표시 방식에 반영한다.",
                },
                {
                    "name": "변경 이력 안내",
                    "description": "변경 일시, 적용 범위, 되돌리기 가능 여부를 안내하고 이력을 저장한다.",
                },
            ]
        if "초기화" in usecase_name or "삭제" in usecase_name:
            return [
                {
                    "name": "초기화 대상 선택",
                    "description": "고객이 개인화 기록, AI 대화 기록, 추천 기록 중 초기화 또는 삭제 대상을 선택한다.",
                },
                {
                    "name": "영향 범위 고지",
                    "description": "채널이 초기화 후 복구 가능 여부, 추천 품질 영향, 보관 예외 기준을 안내한다.",
                },
                {
                    "name": "초기화·삭제 요청 접수",
                    "description": "고객 최종 확인 후 초기화 또는 삭제 요청을 접수하고 중복 요청을 제한한다.",
                },
                {
                    "name": "처리 결과 및 이력 안내",
                    "description": "처리 완료, 보류, 실패 결과와 후속 행동을 안내하고 이력을 저장한다.",
                },
            ]
        return [
            {
                "name": "설정 진입 및 상태 확인",
                "description": "고객이 현재 설정 상태, 권한 상태, 기본값 적용 범위를 확인한다.",
            },
            {
                "name": "권한·보안 조건 판정",
                "description": "채널이 시스템 권한, 세션, 보안 기준, 접근성 설정 가능 여부를 판정한다.",
            },
            {
                "name": "설정 경로 및 대체 안내",
                "description": "고객에게 직접 변경 가능 항목, OS 설정 이동, 제한 사유와 대체 경로를 안내한다.",
            },
            {
                "name": "설정 상태 이력 저장",
                "description": "설정 상태 조회와 변경 진입 이력을 저장하고 후속 설정 화면과 연결한다.",
            },
        ]
    if "회원정보" in usecase_name:
        if "통합 조회" in usecase_name or "조회" in usecase_name or "이해" in usecase_name:
            return [
                {
                    "name": "조회 대상 및 목적 확인",
                    "description": "고객이 프로필, 연락처, 주소, 계좌, 관계 정보 중 조회할 대상을 선택한다.",
                },
                {
                    "name": "권한·마스킹 범위 판정",
                    "description": "채널이 인증 상태, 고객 유형, 대리 권한에 따라 노출 가능 범위와 마스킹 수준을 판정한다.",
                },
                {
                    "name": "대표값·출처 정보 구성",
                    "description": "대표값, 보조값, 미검증값, 출처 우선순위와 기준 시점을 고객이 이해할 수 있게 구성한다.",
                },
                {
                    "name": "정정·변경 경로 안내",
                    "description": "불일치나 변경 필요 항목이 있으면 가능한 수정 경로와 제한 사유를 안내한다.",
                },
            ]
        if "정정" in usecase_name or "복구" in usecase_name:
            return [
                {
                    "name": "문제 유형 및 정정 대상 확인",
                    "description": "고객이 불일치, 미검증, 변경 실패, 처리 중단 중 정정 또는 복구할 대상을 선택한다.",
                },
                {
                    "name": "셀프 복구 가능 여부 판정",
                    "description": "채널이 이전 처리 이력, 인증 상태, 제한 사유를 기준으로 셀프 복구 가능 여부를 판정한다.",
                },
                {
                    "name": "보완·상담 전환 처리",
                    "description": "보완 제출, 재인증, 상담 전환 중 필요한 후속 경로를 안내하고 문맥 정보를 유지한다.",
                },
                {
                    "name": "정정 결과 및 이력 안내",
                    "description": "정정 또는 복구 결과, 반영 시점, 남은 후속 조치를 안내하고 처리 이력을 저장한다.",
                },
            ]
        return [
            {
                "name": "변경 대상 및 적용 범위 선택",
                "description": "고객이 연락처, 이메일, 주소, 환불계좌, 관계 정보 중 변경할 항목과 적용 범위를 선택한다.",
            },
            {
                "name": "재인증·증빙 기준 확인",
                "description": "채널이 변경 항목의 민감도, 권한, 증빙 필요 여부, 세션 영향 기준을 확인한다.",
            },
            {
                "name": "변경 요청 접수",
                "description": "고객 확인 후 변경 요청을 접수하고 중복 요청과 진행 중 요청을 제한한다.",
            },
            {
                "name": "BSS 반영 및 영향 고지",
                "description": "BSS 또는 연계 시스템 반영 결과와 로그인, 알림, 배송, 환불, 계약 영향 범위를 안내한다.",
            },
            {
                "name": "변경 이력 저장",
                "description": "변경 전후 값, 적용 대상, 인증 결과, 처리 일시, 실패 사유를 이력으로 저장한다.",
            },
        ]
    if any(keyword in usecase_name for keyword in ("정보", "조회", "확인")):
        return [
            {
                "name": "업무 진입 및 대상 확인",
                "description": f"고객이 {usecase_name} 대상과 확인 목적을 선택한다.",
            },
            {
                "name": "기준 정보 조회",
                "description": f"채널이 {usecase_name}에 필요한 기준 정보와 고객별 적용 정보를 조회한다.",
            },
            {
                "name": "권한·상태 확인",
                "description": f"권한, 고객 상태, 제한 조건을 확인해 제공 가능한 정보 범위를 판정한다.",
            },
            {
                "name": "정보 제공 및 후속 경로 안내",
                "description": f"고객에게 확인 결과, 제한 사유, 후속 업무 경로를 안내하고 조회 이력을 저장한다.",
            },
        ]
    if any(keyword in usecase_name for keyword in ("변경", "취소", "해지", "탈퇴", "후속", "재시도", "상담")):
        return [
            {
                "name": "후속 업무 선택",
                "description": f"고객이 {usecase_name} 대상과 후속 처리 목적을 선택한다.",
            },
            {
                "name": "후속 처리 가능 여부 확인",
                "description": f"이전 처리 결과, 고객 상태, 제한 조건을 기준으로 {usecase_name} 가능 여부를 판정한다.",
            },
            {
                "name": "후속 요청 접수 및 상태 반영",
                "description": f"고객 확인 후 {usecase_name} 요청을 접수하고 처리 상태를 반영한다.",
            },
            {
                "name": "후속 결과 안내 및 이력 저장",
                "description": f"{usecase_name} 결과와 다음 행동을 안내하고 요청, 검증, 고지 이력을 저장한다.",
            },
        ]
    return [
        {
            "name": "업무 진입 및 목적 확인",
            "description": f"고객이 {usecase_name} 업무에 진입하고 처리 목적과 대상을 확인한다.",
        },
        {
            "name": "처리 조건 검증",
            "description": f"채널이 고객 상태, 권한, 제한 조건, 연계 결과를 기준으로 {usecase_name} 가능 여부를 확인한다.",
        },
        {
            "name": "입력·인증·동의 처리",
            "description": f"고객이 {usecase_name}에 필요한 정보를 입력하고 인증·동의 결과를 확정한다.",
        },
        {
            "name": "영향도 확인 및 최종 확인",
            "description": f"비용, 혜택, 상태 변경 영향을 고지하고 고객 최종 확인을 수집한다.",
        },
        {
            "name": "처리 요청 접수 및 결과 안내",
            "description": f"{usecase_name} 요청을 접수해 처리 결과를 반영하고 완료, 실패, 보류, 제한 결과를 안내한다.",
        },
    ]


def next_process_step_id(existing_ids: set, prefix: str) -> str:
    index = 1
    while True:
        value = f"{prefix}-{index:02d}"
        if value not in existing_ids:
            return value
        index += 1


def business_code_from_spec(spec: dict) -> str:
    return str(spec.get("meta", {}).get("business_code", "GEN")).strip() or "GEN"


def next_generated_id(existing_ids: set, prefix: str) -> str:
    index = 1
    while True:
        value = f"{prefix}-{index:03d}"
        if value not in existing_ids:
            return value
        index += 1


def extract_labeled_segment(text: str, labels: Sequence[str]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:\s*(.+?)(?=\s+[가-힣A-Za-z·/ ]{{1,16}}\s*:|$)", text)
        if match:
            return match.group(1).strip()
    return ""


def limit_text_for_policy(value: object, max_chars: int) -> str:
    text = clean_policy_text(value)
    if len(text) <= max_chars:
        return text
    chunks = split_policy_sentences(text)
    selected: List[str] = []
    current = ""
    for chunk in chunks:
        candidate = f"{current} {chunk}".strip() if current else chunk
        if len(candidate) > max_chars:
            break
        selected.append(chunk)
        current = candidate
    if selected:
        return " ".join(selected)
    # 정책서 본문은 표시용 요약이 아니라 설계 기준 산출물이므로 문장을 중간에 자르지 않는다.
    # 긴 값은 렌더러의 줄바꿈/표 레이아웃에 맡기고, 말줄임으로 정책 기준을 잃지 않게 한다.
    return text


def split_policy_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?。])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def clean_policy_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"</?br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_body_ids(value: object) -> str:
    text = clean_policy_text(value)
    text = BODY_ID_PATTERN.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,/·-")


FUNCTION_DETAIL_ACTIONS = (
    "조회",
    "확인",
    "검증",
    "판정",
    "구분",
    "구성",
    "저장",
    "반영",
    "제공",
    "포함",
    "생성",
    "분류",
    "산정",
    "연동",
    "안내",
    "전달",
    "관리",
    "등록",
    "처리",
    "비교",
    "유지",
    "갱신",
    "제한",
    "차단",
    "탐지",
    "호출",
    "회신",
    "동기화",
    "마스킹",
    "접수",
    "수신",
    "발송",
    "노출",
    "표시",
    "전환",
    "반환",
)


def normalize_function_detail_labels(values: object, max_items: int = 5) -> List[str]:
    if not isinstance(values, list):
        return []
    result: List[str] = []
    seen = set()
    for value in values[:max_items]:
        label = normalize_function_detail_label(value)
        if not label or label in seen:
            continue
        seen.add(label)
        result.append(limit_text_for_policy(label, 45))
    return result


def normalize_function_detail_label(value: object) -> str:
    text = strip_body_ids(value)
    text = text.strip(" .。")
    text = re.sub(r"\s*(?:,|，)\s*", "·", text)
    text = re.sub(r"\s+", " ", text)
    action_pattern = "|".join(FUNCTION_DETAIL_ACTIONS)
    replacements = (
        (rf"(.+?)(?:을|를)\s+분리해\s+({action_pattern})한다$", r"\1 분리 \2"),
        (rf"(.+?)(?:을|를)\s+구분해\s+({action_pattern})한다$", r"\1 구분 \2"),
        (rf"(.+?)(?:을|를)\s+함께\s+({action_pattern})한다$", r"\1 함께 \2"),
        (rf"(.+?)(?:을|를)\s+({action_pattern})한다$", r"\1 \2"),
        (rf"(.+?)(?:으로|로)\s+({action_pattern})한다$", r"\1 \2"),
        (rf"(.+?)(?:에|와|과)\s+({action_pattern})한다$", r"\1 \2"),
        (r"(.+?)(?:을|를)\s+만든다$", r"\1 생성"),
        (r"(.+?)(?:을|를)\s+남긴다$", r"\1 저장"),
        (r"(.+?)(?:을|를)\s+불러온다$", r"\1 조회"),
        (r"(.+?)(?:을|를)\s+구분한다$", r"\1 구분"),
        (r"(.+?)(?:으로|로)\s+표시한다$", r"\1 표시"),
        (r"(.+?)(?:을|를)\s+표시한다$", r"\1 표시"),
    )
    for pattern, replacement in replacements:
        updated = re.sub(pattern, replacement, text)
        if updated != text:
            text = updated
            break
    text = re.sub(r"(?:한다|된다|받는다|이어진다|포함한다)$", "", text)
    text = re.sub(r"(기준|정보|결과|값|조건|항목)(?:을|를)\s+", r"\1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,/·-")


def function_detail_label_is_sentence_like(value: object) -> bool:
    text = clean_policy_text(value).strip()
    if not text:
        return False
    return bool(
        re.search(r"(한다|된다|받는다|만든다|남긴다|불러온다|표시한다|제공한다|반환한다)\.?$", text)
        or text.endswith(".")
    )


def chapter_output_schema(agent: ChapterAgent) -> dict:
    properties = {}
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        properties[schema_key] = field_schema(schema_key)
    return object_schema(properties)


def field_schema(field: str) -> dict:
    schemas = {
        "overview": object_schema(
            {
                "scope": {"type": "array", "items": {"type": "string", "maxLength": 150}, "minItems": 6, "maxItems": 6},
                "principles": {
                    "type": "array",
                    "items": object_schema(
                        {
                            "name": {"type": "string", "maxLength": 28},
                            "description": {"type": "string", "maxLength": 110},
                        }
                    ),
                    "minItems": 4,
                    "maxItems": 6,
                },
            }
        ),
        "terms": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 120},
                }
            )
        ),
        "actors": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 110},
                }
            )
        ),
        "usecases": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "actor": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 110},
                    "process_target": {"type": "string", "enum": ["Y", "N"]},
                }
            )
        ),
        "usecase_diagram": object_schema({"lines": array_schema({"type": "string", "maxLength": 140})}),
        "states": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 95},
                    "next_action": {"type": "string", "maxLength": 95},
                }
            ),
            min_items=1,
        ),
        "state_transitions": array_schema(
            object_schema(
                {
                    "usecase_ids": array_schema({"type": "string"}),
                    "current_state": {"type": "string"},
                    "event": {"type": "string", "maxLength": 80},
                    "next_state": {"type": "string"},
                    "criteria": {"type": "string", "maxLength": 120},
                }
            ),
            min_items=1,
        ),
        "processes": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "usecase_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 110},
                    "related_functions": array_schema({"type": "string", "maxLength": 70}),
                    "related_policies": array_schema({"type": "string", "maxLength": 120}),
                }
            )
        ),
        "functions": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "process_id": {"type": "string"},
                    "process_ids": array_schema({"type": "string"}),
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 110},
                    "details": array_schema({"type": "string", "maxLength": 45}),
                }
            )
        ),
        "process_details": array_schema(
            object_schema(
                {
                    "process_id": {"type": "string"},
                    "entry_condition": {"type": "string", "maxLength": 130},
                    "exit_condition": {"type": "string", "maxLength": 130},
                    "previous_processes": array_schema({"type": "string", "maxLength": 80}),
                    "next_processes": array_schema({"type": "string", "maxLength": 80}),
                    "related_functions": array_schema({"type": "string", "maxLength": 90}),
                    "related_policies": array_schema({"type": "string", "maxLength": 110}),
                }
            )
        ),
        "function_details": array_schema(
            object_schema(
                {
                    "function_id": {"type": "string"},
                    "input_information": array_schema({"type": "string", "maxLength": 100}),
                    "processing_logic": array_schema({"type": "string", "maxLength": 130}),
                    "sub_functions": array_schema({"type": "string", "maxLength": 80}),
                    "output_information": array_schema({"type": "string", "maxLength": 100}),
                    "failure_exception_cases": array_schema({"type": "string", "maxLength": 120}),
                    "related_policies": array_schema({"type": "string", "maxLength": 110}),
                }
            )
        ),
        "policy_groups": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string", "maxLength": 120},
                }
            )
        ),
        "policy_details": array_schema(
            object_schema(
                {
                    "id": {"type": "string"},
                    "policy_id": {"type": "string"},
                    "name": {"type": "string", "maxLength": 60},
                    "content": {"type": "string", "maxLength": 220},
                }
            )
        ),
        "final_check": array_schema({"type": "string", "maxLength": 120}),
    }
    return schemas[field]


def object_schema(properties: Mapping[str, object]) -> dict:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


def array_schema(items: Mapping[str, object], *, min_items: int | None = None) -> dict:
    schema = {"type": "array", "items": dict(items)}
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def build_system_instructions(runtime: AgentRuntime, agent: ChapterAgent | None = None) -> str:
    instructions = [
            "너는 통합채널 정책서 작성 전문 agent다.",
            "반드시 요청된 JSON 스키마에 맞는 JSON만 작성한다.",
            "정책서는 업체가 상세 설계를 수행할 수 있도록 업무 구조, 처리 흐름, 기능 범위, 정책 판단 기준을 정의한다.",
            "요구사항과 참고자료는 원문을 복사하지 말고 고객 과업, 검증 조건, 예외, 운영 기준, BSS 연계 기준으로 재구성한다.",
            "전문 분석 방법론은 액터·유즈케이스·상태·프로세스·기능·정책을 판단하기 위한 내부 기준이다. 템플릿/샘플의 장 구성, 표 구조, 필드명, 간결성을 바꾸는 근거로 쓰지 않는다.",
            "사전 주제 Knowledge Pack의 후보는 정답이 아니라 참고 후보 목록이다. 현재 주제의 첨부 요구사항, 첨부 참고자료, 현재 유즈케이스·프로세스·기능 연결로 검증된 항목만 채택한다.",
            "TK 문서의 주요 프로세스 및 기능은 유즈케이스·프로세스·기능 후보를 정렬하는 근거로 쓰되, 현재 주제·상세 요구사항과 직접 맞는 항목만 채택한다.",
            "Knowledge Pack 후보를 그대로 복사하지 않는다. 채택하지 않은 후보를 억지로 문서에 넣지 않고, 필요하면 제외 또는 Evidence Gap으로 둔다.",
            insight_applicability_for_prompt(),
            "샘플 간소화본처럼 문장은 짧고 단정하게 쓴다. 한 셀에는 하나의 핵심 판단만 담고 분석 메모를 길게 풀어쓰지 않는다.",
            "출력 가능한 공간이 남아 있어도 분량을 채우기 위해 배경 설명, 일반론, 동일 의미 반복, 자기 평가 문장을 추가하지 않는다.",
            "각 문장은 근거가 있는 업무 주체, 판단 조건, 처리 결과 중 하나 이상을 드러낼 때만 남긴다.",
            "이미 선행 장에서 정의한 내용은 다시 설명하지 말고 ID, 명칭, 관련 기능명, 관련 정책명으로 짧게 참조한다.",
            "확정 정책값이 없는 경우 장황한 추정 대신 결정이 필요한 기준축과 현재 근거에서 판단 가능한 범위만 쓴다.",
            "JSON 값에는 <br/>, HTML 태그, 마크다운, 줄바꿈 지시문을 넣지 않는다. 줄바꿈은 HTML 렌더러가 처리한다.",
            "상세한 트리거, 허용 행위, 금지 행위, 이력 저장 기준은 가능한 한 프로세스·기능·정책 장에 배치하고 개요·액터에는 요약만 둔다.",
            "화면 UI 상세, API 필드, DB 컬럼, 오류 코드 전체 목록, 운영자 화면 상세, 배치 설계는 작성하지 않는다.",
            "액터는 독립 책임 주체만 작성하고 로그인/비로그인/정상/제한 고객은 액터로 분리하지 않는다.",
            "유즈케이스는 상위 업무 목적 단위로 작성하고, 본인인증·약관 동의·정보 입력·조건 확인·결과 안내는 프로세스 단계로 작성한다.",
            "프로세스 정의 대상은 고객만이 아니라 고객, 운영자, 법정대리인, 대리인, 관리자 등 사람 액터 전체를 기준으로 Y를 부여한다.",
            "정책 상세는 샘플처럼 정책 항목명과 정책 내용으로 선언한다. 인증 수단, 가능 횟수, 유효시간, 적용 기간, 허용 목록, 제한 조건, 노출 채널, 고지 항목, 저장 항목처럼 기능 동작에 필요한 값을 항목으로 나누되 고정 슬롯을 반복하지 않는다.",
            "Authoring Blueprint의 요구사항, 분석 신호, evidence_ids를 우선 반영한다. 근거 없는 일반론으로 범위를 확장하지 않는다.",
            "단, Authoring Blueprint는 확정 정답이 아니라 검증된 작성 가설이다. Blueprint Quality Gate의 stage_findings가 있으면 해당 위험을 먼저 해소하고, 근거가 약한 부분은 확정값처럼 쓰지 않는다.",
            "사용자 작성 요청 메모가 있으면 요구사항·참고자료·AGENTS.md 원칙을 해치지 않는 범위에서 작성 초점과 보완 우선순위로 반드시 반영한다.",
            "근거가 부족한 정책값은 확정값처럼 만들지 말고, 현재 근거에서 도출 가능한 판단 기준만 작성한다.",
            "금지 표현: 검토 필요, 추후 협의, 시스템에서 처리, 가능하도록 한다, 정책에 따라 처리한다, 관련 부서 확인 필요.",
            f"업무코드는 {runtime.ctx.business_code}이며 모든 ID는 이 업무코드와 기존 ID 체계를 유지한다.",
            "업무코드는 ID 생성 전용 값이다. 본문, 학습 요약, 범위, 원칙 문장에서는 업무코드를 서비스명이나 업무명처럼 쓰지 않는다.",
    ]
    blueprint_contract = approved_blueprint_system_contract(runtime, agent)
    if blueprint_contract:
        insert_at = 3
        instructions[insert_at:insert_at] = [blueprint_contract]
    return "\n".join(instructions)


def approved_blueprint_system_contract(runtime: AgentRuntime, agent: ChapterAgent | None) -> str:
    if agent is None:
        return ""
    stage_blueprint = stage_blueprint_for_prompt(runtime.authoring_blueprint, agent.chapter_key)
    if not isinstance(stage_blueprint, Mapping) or not stage_blueprint:
        return ""
    compact_contract = {
        "chapter": agent.chapter_key,
        "rule": "이 Approved Blueprint Contract는 현재 장의 계층, 입자도, 근거 우선순위, 작성 금지 기준이다. Writer는 이 계약을 우선 준수한다.",
        "stage_blueprint": stage_blueprint,
        "conflict_policy": "첨부 요구사항·템플릿·샘플·AGENTS.md와 충돌하면 첨부 자료를 우선하고 Blueprint 후보는 축소 또는 제외한다.",
        "scope_policy": "현재 장 범위 밖의 보안·운영·UX 일반론은 새 항목으로 확장하지 않는다.",
    }
    return "[Approved Blueprint Contract - 현재 장 필수 준수]\n" + prompt_json(compact_contract, 2400)


def writer_self_check_for_prompt(agent: ChapterAgent, stage_blueprint: Mapping[str, object]) -> dict:
    contract = stage_blueprint.get("architecture_contract", {}) if isinstance(stage_blueprint, Mapping) else {}
    first_draft_plan = contract.get("first_draft_quality_plan", {}) if isinstance(contract, Mapping) else {}
    return {
        "rule": "아래 기준은 JSON 출력 전 내부 점검용이다. self_check 결과를 JSON 필드로 출력하지 않는다.",
        "return_rule": "하나라도 실패하면 JSON을 반환하기 전에 담당 장 안에서 직접 보완한 뒤 최종 JSON만 반환한다.",
        "chapter": agent.chapter_key,
        "first_draft_quality_plan": first_draft_plan,
        "chapter_specific_checks": chapter_first_draft_quality_checks(agent.chapter_key),
        "stage_contracts": contract.get("stage_contracts", [])[:2] if isinstance(contract, Mapping) else [],
        "quality_gates": contract.get("quality_gates", [])[:3] if isinstance(contract, Mapping) else [],
            "must_fix_before_return": [
                "담당 챕터의 ID와 명칭이 이전 장 기준과 맞는지 확인한다.",
                "담당 챕터가 상위 계층을 다시 쓰거나 하위 계층을 앞당겨 쓰지 않았는지 확인한다.",
                "Knowledge Pack 후보를 채택했다면 요구사항, 첨부 참고자료, 현재 프로세스/기능/정책 연결 중 하나로 설명 가능한지 확인한다.",
                "연결 근거가 약한 Knowledge Pack 후보는 출력에서 제거한다.",
                "샘플의 표 셀 밀도처럼 짧고 판단 가능한 문장인지 확인한다.",
                "근거 없는 일반론, 반복 문장, 기능/정책/프로세스 계층 혼용이 있으면 반환 전 제거한다.",
        ],
    }


TK_PROCESS_FUNCTION_GUIDANCE_STAGES = {"usecases", "process", "functions", "process_detail", "function_detail"}


def tk_process_function_application_for_prompt(agent: ChapterAgent, runtime: AgentRuntime) -> dict:
    if agent.chapter_key not in TK_PROCESS_FUNCTION_GUIDANCE_STAGES:
        return {}
    prelearned = runtime.learning.get("prelearned_knowledge", {}) if isinstance(runtime.learning, Mapping) else {}
    rows = prelearned.get("tk_process_function_guidance", []) if isinstance(prelearned, Mapping) else []
    if not isinstance(rows, list) or not rows:
        return {}
    compact_rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        process_name = str(row.get("process_name", "") or "").strip()
        major_functions = [
            str(item or "").strip()
            for item in (row.get("major_functions", []) if isinstance(row.get("major_functions", []), list) else [])
            if str(item or "").strip()
        ][:5]
        if not process_name and not major_functions:
            continue
        compact_rows.append(
            {
                "process_name": process_name[:90],
                "major_functions": [item[:90] for item in major_functions],
                "source_name": str(row.get("source_name", "") or "")[:120],
                "matched_keywords": row.get("matched_keywords", [])[:6] if isinstance(row.get("matched_keywords", []), list) else [],
            }
        )
        if len(compact_rows) >= 8:
            break
    if not compact_rows:
        return {}
    stage_rules = {
        "usecases": "TK 프로세스명은 유즈케이스 후보가 아니라 업무 목표를 찾는 단서다. 절차 단계는 상위 고객/운영자 목표로 묶고 process_target=Y/N 기준을 다시 판단한다.",
        "process": "현재 주제와 맞는 TK 프로세스 행은 프로세스 후보로 검토한다. 단, 상세 요구사항명/설명과 연결되지 않는 행은 제외한다.",
        "functions": "TK 주요 기능은 기능·세부 기능 구성 후보로 전환한다. 기능명은 업무 처리 역량으로 재작성하고 TK 문구를 그대로 복사하지 않는다.",
        "process_detail": "TK 행의 순서와 기능 단서를 참고해 프로세스 상세 흐름을 보강하되, 시스템 내부 처리는 기능·정책으로 내린다.",
        "function_detail": "TK 주요 기능을 세부 기능 구성 후보로 참고하되 화면 UI, API, DB 상세로 내려가지 않는다.",
    }
    return {
        "rule": "TK의 '주요 프로세스 및 기능'은 지향점이 아니라 유즈케이스·프로세스·기능 설계 후보 근거다.",
        "one_to_many_guard": "TK 하나가 여러 정책 주제를 포괄할 수 있으므로 현재 주제·상세 요구사항과 맞는 행만 사용한다.",
        "fallback": "현재 주제와 직접 맞는 TK 행이 없으면 요구사항 상세명/상세설명, 샘플, Approved Blueprint를 우선한다.",
        "stage_rule": stage_rules.get(agent.chapter_key, ""),
        "guidance_rows": compact_rows,
    }


def chapter_first_draft_quality_checks(chapter_key: str) -> List[str]:
    checks = {
        "overview": [
            "범위는 고객 과업 기준으로 쓰고, 내부 시스템/조직 기준만으로 정의하지 않는다.",
            "설계 원칙은 4~6개이며 후속 기능·정책 판단으로 연결 가능한 문장이다.",
        ],
        "terms": [
            "일반 명사가 아니라 상태, 권한, 인증, 동의, 정책 판단값에 쓰이는 용어만 남긴다.",
            "설명에는 업무상 판단 기준과 유사 용어 차이가 드러난다.",
        ],
        "actors": [
            "로그인/비로그인/정상/제한 고객처럼 고객 상태를 액터로 분리하지 않는다.",
            "액터는 유즈케이스 시작, 검증·승인, 결과 생성 책임이 있는 독립 주체다.",
        ],
        "usecases": [
            "유즈케이스는 절차 단계가 아니라 고객·운영자가 완료하려는 상위 업무 목표다.",
            "사람 액터 유즈케이스는 process_target=Y, 시스템 보조 처리는 원칙적으로 N이다.",
        ],
        "usecase_diagram": [
            "액터와 유즈케이스 관계만 표현하고 화면 이동·버튼·팝업을 넣지 않는다.",
            "include는 반복 공통 처리에만 사용한다.",
        ],
        "state": [
            "전이 이벤트는 승인된 유즈케이스 흐름에서 발생한 상태 변화 업무 사건이다. 유즈케이스 추적성은 usecase_ids로 확인한다.",
            "현재 상태와 다음 상태는 상태 목록에 존재하고, 예외·제한·보류 분기 기준이 배타적이다.",
        ],
        "process": [
            "프로세스는 기능명 나열이 아니라 유즈케이스 완료 절차다.",
            "사람 액터 Y 유즈케이스가 1개 프로세스로만 끝나면 유즈케이스 입자도 또는 프로세스 경계를 점검하고, 상위 업무 목표가 맞을 때만 시작·판단·요청·반영·안내 단위로 분해한다.",
        ],
        "process_detail": [
            "프로세스 상세는 선행/후행 프로세스, 관련 기능, 관련 정책과 이어져야 한다.",
            "내부 API/DB 구현이 아니라 업무 판단과 처리 기준을 설명한다.",
        ],
        "functions": [
            "기능은 프로세스명을 복사하지 않고 조회·검증·산정·저장·알림·연동 같은 처리 역량으로 묶는다.",
            "세부 기능 구성은 짧은 하위 처리명이며 기능마다 충분히 구체적이다.",
        ],
        "function_detail": [
            "입력/처리/출력/예외/관련 정책이 개발·QA가 이해 가능한 수준으로 이어진다.",
            "세부 기능 구성은 프로세스 단계명이나 정책 항목명이 아니라 기능 하위 처리다.",
        ],
        "policies": [
            "정책은 기능 동작에 필요한 값·조건·허용 범위·예외·고지·이력 기준이다.",
            "정책 상세는 정책 그룹 → 정책 항목 → 항목별 값 순서로 읽힌다.",
        ],
    }
    return checks.get(chapter_key, [
        "담당 장의 상위/하위 계층과 ID 연결을 확인한다.",
        "근거 없는 일반론과 중복 설명을 제거한다.",
    ])


def revision_request_for_mode(agent: ChapterAgent, mode: str) -> str:
    common = (
        "이전 장은 이미 통과된 기준선이다. 이전 장의 용어·액터·유즈케이스·상태·ID를 바꾸려 하지 말고, 이번 담당 챕터를 그 기준에 맞춘다.\n"
        "반환 전에 각 feedback의 acceptance_check를 스스로 대조하고, 같은 원인의 finding이 재발하지 않도록 실제 JSON 값의 명칭·설명·연결값을 고친다.\n"
        "새 ID, 새 용어, 새 액터, 새 정책 축은 feedback에서 명시했거나 연결성 누락을 해결하는 경우에만 추가한다.\n"
        "Authoring Blueprint의 요구사항·분석 신호·근거와 맞지 않는 일반 문장은 제거하고, 누락된 근거 기반 판단축을 보완한다.\n"
        "문장을 길게 늘리지 말고, 현재 챕터에 필요한 핵심만 남긴다.\n"
        "JSON 문자열 안에 <br/> 또는 HTML 태그를 절대 넣지 마라.\n"
        "기존 ID, actor명, usecase_id, 기능 process_id, 정책 상세 policy_id의 연결성은 깨지지 않아야 한다.\n"
        "담당 챕터 외 필드는 반환하지 마라."
    )
    mode_rules = {
        "patch": (
            "보완 방식: patch 수준 최소 수정.\n"
            "Inspector가 지적한 ID, 항목명, 문구, 연결만 직접 수정하고 지적되지 않은 항목은 가능한 유지한다.\n"
            "피드백이 이전 장과의 불일치를 말하더라도 수정 범위는 담당 챕터 안으로 한정한다."
        ),
        "scoped_section_revision": (
            "보완 방식: scoped section revision.\n"
            "초안 품질이 통과 기준에 근접하지 않아 patch만으로는 부족할 수 있다.\n"
            "finding이 가리키는 섹션, 표, 행 그룹과 같은 원인의 인접 항목은 다시 정렬한다.\n"
            "단, 담당 장 전체를 새 주제로 다시 쓰거나 이전 장의 기준을 임의로 바꾸지 않는다."
        ),
        "scoped_full_revision": (
            "보완 방식: scoped full revision.\n"
            "담당 장 전체의 계층, 입자도, 연결성, 샘플 수준을 다시 맞춘다.\n"
            "로컬 초안의 좋은 ID와 연결은 가능한 유지하되, 구조가 낮은 품질의 원인이면 담당 장 안에서 재배치·재서술한다."
        ),
        "blueprint_realign_revision": (
            "보완 방식: Blueprint realign revision.\n"
            "먼저 Approved Blueprint와 이전 장 계약을 다시 읽고, 담당 장이 따라야 할 계층과 입자도를 재확인한다.\n"
            "초안에 근거 없는 지식 후보, 일반론, 계층 혼용이 있으면 제거하고 담당 장을 다시 구성한다."
        ),
    }
    return "작성 요청:\n" + mode_rules.get(mode, mode_rules["patch"]) + "\n" + common


def build_chapter_prompt(
    agent: ChapterAgent,
    current_spec: dict,
    local_payload: dict,
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]] | None = None,
    *,
    chunk_mode: bool = False,
) -> str:
    budget = chapter_prompt_budget(agent, bool(feedback))
    if chunk_mode:
        budget = chunk_prompt_budget(agent, budget)
    feedback_block = "Inspector/사용자 보완 요청:\n없음"
    focused_feedback: Sequence[Mapping[str, object]] | None = None
    learning_limit = budget["learning"]
    summary_limit = budget["summary"]
    payload_limit = min(chapter_payload_limit(agent), budget["payload"])
    payload_label = "로컬 초안 JSON"
    payload_for_prompt = compact_payload_for_prompt(agent, local_payload)
    state_repair_block = state_repair_contract_block(agent, agent.extract_payload(current_spec), ())
    state_authoring_block = state_authoring_contract_block(agent, current_spec, local_payload)
    process_contract_block = process_upstream_contract_block(agent, current_spec)
    stage_blueprint = stage_blueprint_for_prompt(runtime.authoring_blueprint, agent.chapter_key)
    tk_process_function_block = tk_process_function_application_for_prompt(agent, runtime)
    style_anchor_block = policy_style_anchor_for_prompt(agent.chapter_key)
    request = (
        "작성 요청:\n로컬 초안을 기반으로 담당 챕터 JSON을 샘플 정책서의 구성 방식에 맞게 보강해줘.\n"
            "Authoring Blueprint의 target_requirement_ids, analysis_focus, evidence_summaries를 우선 반영하고 일반론으로 새 항목을 만들지 마라.\n"
            "주제가 여러 의미 축으로 나뉘는 경우 현재 챕터에서 각 축이 최소 1회 이상 업무 판단 기준으로 드러나야 한다.\n"
            "참고자료에 있더라도 현재 주제 범위 밖의 인접 업무는 용어, 액터, 유즈케이스, 정책으로 확장하지 말고 필요 시 제외/후속 범위에만 남긴다.\n"
            "필요한 기준은 독립 판단 단위로만 분리하고, 같은 의미의 기준을 표현만 바꿔 반복하지 마라.\n"
        "샘플 간소화본의 밀도에 맞춰 짧은 문장과 간결한 표 셀을 사용하고, 장황한 배경 설명·일반론·분량 채우기 문장은 쓰지 마라.\n"
        "정책서가 완결됐다고 판단되면 더 쓰지 말고 반환한다.\n"
        "JSON 문자열 안에 <br/> 또는 HTML 태그를 절대 넣지 마라.\n"
        "단, 기존 ID, actor명, usecase_id, 기능 process_id, 정책 상세 policy_id의 연결성은 깨지지 않아야 한다.\n"
        "담당 챕터 외 필드는 반환하지 마라."
    )
    if feedback:
        remediation_mode = feedback_remediation_mode(feedback)
        focused_feedback = compact_feedback_for_prompt(
            feedback,
            agent=agent,
            current_payload=agent.extract_payload(current_spec),
        )
        feedback_block = "Inspector/사용자 보완 요청:\n" + prompt_json(
            list(focused_feedback),
            feedback_prompt_limit(focused_feedback, budget["feedback"]),
        )
        learning_limit = min(learning_limit, 2500)
        summary_limit = min(summary_limit, 5000)
        payload_limit = min(payload_limit, 14000)
        payload_label = "현재 챕터 JSON"
        payload_for_prompt = compact_payload_for_prompt(agent, agent.extract_payload(current_spec))
        state_repair_block = state_repair_contract_block(agent, agent.extract_payload(current_spec), focused_feedback)
        state_authoring_block = state_authoring_contract_block(agent, current_spec, local_payload)
        process_contract_block = process_upstream_contract_block(agent, current_spec)
        request = revision_request_for_mode(agent, remediation_mode)
    if agent.chapter_key == "terms_refinement":
        request = (
            "작성 요청:\n기능과 정책까지 작성된 현재 정책서 전체를 기준으로 주요 용어 목록을 한 번 더 업데이트해줘.\n"
            "기존 핵심 용어와 ID는 가능한 유지하고, 상태·프로세스·기능·정책 상세에서 실제 판단 기준으로 쓰인 용어가 누락된 경우에만 추가한다.\n"
            "추가 대상은 상태, 인증·권한, 동의, 제한, 예외, 고객 고지, 이력 저장, BSS 연계, 운영 검토처럼 후속 설계 해석 차이를 줄이는 용어다.\n"
            "일반 명사, 화면 표현, 정책 상세 한 항목에만 쓰이는 긴 예외 설명은 용어로 만들지 마라.\n"
            "용어 설명은 업무상 판단 기준이 드러나는 한 문장으로 작성하고 120자 이내로 유지한다.\n"
            "JSON 문자열 안에 <br/> 또는 HTML 태그를 절대 넣지 마라.\n"
            "담당 챕터 외 필드는 반환하지 마라."
        )
    sections = [
            f"담당 agent: {agent.display_name}",
            f"담당 챕터: {agent.chapter_key}",
            f"작성 지침: {agent.instruction(runtime.guideline)}",
            style_anchor_block,
            "전문 분석 방법론 적용 기준:\n" + prompt_json(method_knowledge_for_agent(agent.chapter_key), 1800),
            "최근 Inspector 실패 패턴 예방:\n" + "\n".join(f"- {rule}" for rule in inspector_failure_prevention_rules(agent)),
            "간결성 기준:\n" + "\n".join(f"- {rule}" for rule in chapter_concision_rules(agent)),
            "공통 지침:\n" + "\n".join(f"- {rule}" for rule in runtime.guideline.get("common_rules", [])),
            "주제 학습 요약:\n" + prompt_json(runtime.learning, learning_limit),
            "사용자 작성 요청 메모:\n" + user_brief_for_prompt(runtime.ctx),
            "작성 기준서(Authoring Blueprint):\n"
            + prompt_json(stage_blueprint, budget["blueprint"]),
            "초안 품질 자체 점검 기준(출력하지 말고 내부적으로만 확인):\n"
            + prompt_json(writer_self_check_for_prompt(agent, stage_blueprint), 1800),
            "현재까지 작성된 정책서 요약:\n" + prompt_json(summarize_spec_for_prompt(current_spec), summary_limit),
            "챕터 인계 정합성 컨텍스트:\n"
            + prompt_json(alignment_context_for_prompt(agent, current_spec, runtime), budget["alignment"]),
            "Agent별 근거 Context Pack:\n"
            + prompt_json(
                context_pack_for_agent(
                    agent.chapter_key,
                    current_spec,
                    runtime,
                    limit=budget["context_items"],
                ),
                budget["context"],
            ),
            f"{payload_label}:\n" + prompt_json(payload_for_prompt, payload_limit),
            state_authoring_block,
            feedback_block,
            state_repair_block,
            process_contract_block,
            feedback_resolution_block(focused_feedback or feedback),
            request,
    ]
    if tk_process_function_block:
        sections.insert(
            4,
            "TK 주요 프로세스·기능 적용 기준:\n" + prompt_json(tk_process_function_block, 1800),
        )
    return "\n\n".join(section for section in sections if section)


def build_state_focused_prompt(
    agent: ChapterAgent,
    current_spec: dict,
    local_payload: Mapping[str, object],
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]] | None = None,
) -> str:
    focused_feedback = compact_feedback_for_prompt(
        feedback,
        agent=agent,
        current_payload=agent.extract_payload(current_spec),
    )
    feedback_block = "Inspector/자동 재시도 보완 요청:\n없음"
    if focused_feedback:
        feedback_block = "Inspector/자동 재시도 보완 요청:\n" + prompt_json_unlimited(list(focused_feedback))
    max_states, max_transitions = state_count_limits(runtime)
    state_payload = state_seed_payload_for_prompt(local_payload, current_spec)
    stage_blueprint = stage_blueprint_for_prompt(runtime.authoring_blueprint, "state")
    return "\n\n".join(
        [
            f"담당 agent: {agent.display_name}",
            "상태 장 전용 작성 모드: 이전 장 전체를 다시 해석하지 말고, 승인된 유즈케이스와 상태 seed를 기준으로 상태 장만 작성한다.",
            f"작성 지침: {agent.instruction(runtime.guideline)}",
            policy_style_anchor_for_prompt("state"),
            "전문 분석 방법론 적용 기준:\n" + prompt_json(method_knowledge_for_agent(agent.chapter_key), 1800),
            "템플릿·샘플 기반 상태 작성 규칙:\n" + prompt_json_unlimited(state_template_sample_rules_for_prompt()),
            "상태 전이 설계 패턴:\n" + prompt_json_unlimited(state_transition_design_pattern()),
            "유즈케이스 기반 상태 lifecycle 계약:\n"
            + prompt_json_unlimited(state_usecase_lifecycle_contract_for_prompt(current_spec)),
            "상태 장 필수 계약:\n"
            + prompt_json_unlimited(
                {
                    "must_not_be_empty": "states와 state_transitions는 절대 빈 배열로 반환하지 않는다.",
                    "state_count": f"간소화본은 업무 경계가 다른 핵심 상태만 작성한다. {max_states}개는 상한 안전장치이며, 개수를 채우려고 상태를 늘리지 않는다.",
                    "transition_count": f"전이는 정상·제한·보류·실패·운영 확인의 대표 경로만 작성한다. {max_transitions}개는 상한 안전장치이며, 모든 사건 조합을 행으로 복제하지 않는다.",
                    "primary_source": "상태 후보의 1차 출처는 용어가 아니라 상태를 실제로 바꾸는 유즈케이스의 시작·판정·완료·예외 lifecycle이다.",
                    "usecase_link": "상태를 변경하는 주체는 유즈케이스다. 모든 전이는 state_transitions.usecase_ids에 액터 유즈케이스 ID를 1개 이상 넣는다.",
                    "event_rule": "state_transitions.event에는 연결된 유즈케이스 흐름에서 상태를 실제로 바꾸는 업무 사건을 쓴다. 예: 회원 가입 완료, 기존 정상 회원 식별, 유예 기간 만료, 상태 조회 실패. 유즈케이스명은 usecase_ids로만 추적한다.",
                    "dedupe": "같은 전이가 여러 유즈케이스에 공통이면 전이 행을 복제하지 말고 usecase_ids 배열에 여러 ID를 넣는다.",
                    "state_name_integrity": "current_state와 next_state는 states.name을 글자 단위로 동일하게 사용한다.",
                    "state_term_integrity": "용어 장은 상태명 사전이다. 선택한 상태가 용어 후보와 같은 의미이면 같은 이름을 쓰고, 예: '열람'을 '열람 완료'로 바꾸지 않는다.",
                    "decision_vs_result": "가능 여부 판정과 최종 확정 결과를 분리한다. '가능' 판정만으로 완료·취소·종료 상태로 보내지 말고 확정·완료·반영 조건을 criteria에 둔다.",
                    "overfit_guard": "Inspector가 누락 전이를 지적해도 항상 행을 추가하지 않는다. 같은 후속 조치로 처리 가능한 경우에는 상태 설명 또는 criteria를 좁혀 모순을 없앤다.",
                    "scope_limit": "시스템 판정·연계 결과가 상태 변경을 직접 발생시키면 해당 시스템 액터 유즈케이스를 usecase_ids에 연결하고, event에는 상태 변화 사건을 쓰며 상세 조건은 criteria에 쓴다.",
                    "style": "상태 설명과 후속 처리는 각각 한 문장으로 쓰고 ID를 본문 문장에 넣지 않는다.",
                }
            ),
            "용어 기반 상태명 보조 계약:\n" + prompt_json_unlimited(state_term_contract_for_prompt(current_spec)),
            "승인된 유즈케이스 계약:\n" + prompt_json_unlimited(state_usecase_contract_for_prompt(current_spec)),
            "이전 장 요약:\n" + prompt_json(state_focused_spec_summary(current_spec), 5200),
            "주제 학습 요약:\n" + prompt_json(runtime.learning, 1400),
            "작성 기준서(상태 장 관련 Blueprint):\n"
            + prompt_json(stage_blueprint, 2600),
            "초안 품질 자체 점검 기준(출력하지 말고 내부적으로만 확인):\n"
            + prompt_json(writer_self_check_for_prompt(agent, stage_blueprint), 1600),
            "상태 장 근거 Context Pack:\n"
            + prompt_json(context_pack_for_agent("state", current_spec, runtime, limit=4), 1800),
            "상태 seed JSON(그대로 복사하지 말고 현재 주제와 유즈케이스에 맞게 재작성):\n"
            + prompt_json_unlimited(state_payload),
            "사용자 작성 요청 메모:\n" + user_brief_for_prompt(runtime.ctx),
            feedback_block,
            feedback_resolution_block(focused_feedback or feedback),
            "작성 요청:\n"
            "states와 state_transitions만 반환한다. "
            "상태는 고객 또는 운영자가 인식하는 업무 가능 여부와 후속 처리 기준으로만 정의한다. "
            "유즈케이스가 상태를 바꾸는 구조가 드러나도록 모든 전이에 usecase_ids를 채우고, event에는 샘플처럼 상태 변화 업무 사건을 쓴다. "
            "BSS·인증기관·연계 시스템의 판정이 상태 변경을 직접 발생시키면 해당 시스템 액터 유즈케이스는 usecase_ids에 연결하고, 판정 조건과 후속 기준은 criteria에 적는다. "
            "상태 후보는 먼저 상태 변경이 있는 유즈케이스 lifecycle에서 도출하고, 용어 후보는 선택한 상태명의 표준명으로만 사용한다. "
            "고객 행위가 판정 중 상태로 들어가면 허용·불허·보류·실패 출구를 함께 닫아야 한다. "
            "Seed보다 좋아지는 방향으로 통합·보완하되 빈 배열, UI 상태, 화면 로딩, 버튼 활성화, 결과 상태끼리 직접 이동하는 전이는 만들지 않는다. "
            "JSON 문자열 안에 <br/>, HTML, 마크다운을 넣지 않는다.",
        ]
    )


def state_seed_payload_for_prompt(
    local_payload: Mapping[str, object],
    current_spec: Mapping[str, object],
) -> dict:
    transitions = copy.deepcopy(local_payload.get("state_transitions", []))
    usecase_ids = [
        str(usecase.get("id", "")).strip()
        for usecase in current_spec.get("usecases", [])
        if isinstance(usecase, Mapping)
        and str(usecase.get("id", "")).strip()
    ]
    first_usecase_id = usecase_ids[0] if usecase_ids else ""
    if isinstance(transitions, list) and first_usecase_id:
        for transition in transitions:
            if isinstance(transition, dict) and not transition_usecase_ids_value(transition):
                transition["usecase_ids"] = [first_usecase_id]
    return {
        "states": compact_dicts(
            local_payload.get("states", []),
            ("id", "name", "description", "next_action"),
            120,
            14,
        ),
        "state_transitions": compact_dicts(
            transitions,
            ("usecase_ids", "current_state", "event", "next_state", "criteria"),
            130,
            30,
        ),
    }


def state_template_sample_rules_for_prompt() -> dict:
    return {
        "template_rules": [
            "상태는 고객 노출, 기능 허용, 정책 판단, 후속 처리의 기준이 되는 값만 둔다.",
            "상태 전이는 현재 상태, 전이 이벤트, 다음 상태, 처리 기준 및 후속 처리 순서로 닫힌다.",
            "화면 로딩, 버튼 활성화, 단순 안내 노출, 임시 UI 상태는 상태 코드로 만들지 않는다.",
            "전이 조건이 정책 판단을 포함하면 이후 정책 장에서 정책 항목으로 이어질 수 있게 기준값·제한·예외를 남긴다.",
        ],
        "sample_patterns": [
            "상태명은 정상, 보류, 완료, 제한, 만료, 재처리 필요처럼 업무 lifecycle을 나타내는 용어로 고정하고 전이표에서 같은 이름만 사용한다.",
            "처리 허브 상태는 요청 접수, 조건 분석 중, 결과 생성 중처럼 후속 분기의 기준이 되는 상태로 두고, 결과 제공, 실패, 저신뢰, 상담 전환, 종료처럼 처리 결과별로 분기한다.",
            "샘플은 '가능 여부 판정'과 '완료/취소/종료 확정'을 한 전이에 섞지 않는다. 가능 여부는 판정 기준이고 완료·취소·종료는 확정 결과다.",
            "운영 검토 또는 운영 확인 상태는 실제 유입 전이의 원인 범위를 모두 포괄하도록 정의한다.",
        ],
        "writer_guardrails": [
            "앞 장의 용어가 상태값이면 states.name을 임의로 바꾸지 않는다.",
            "모든 액터 유즈케이스가 상태 변경의 기준이 될 수 있지만, 실제 상태 변화가 없는 유즈케이스는 전이표에 억지로 넣지 않는다.",
            "전이 이벤트 칸에는 연결된 유즈케이스 흐름에서 발생한 업무 사건을 쓰고, 추적할 유즈케이스 ID는 usecase_ids에 둔다.",
            "같은 판정 허브에서 허용, 제한, 보류, 실패 분기가 있으면 우선순위나 배타 조건을 criteria에 짧게 둔다.",
        ],
    }


def state_usecase_lifecycle_contract_for_prompt(spec: Mapping[str, object]) -> dict:
    contracts: List[dict] = []
    for usecase in spec.get("usecases", []):
        if not isinstance(usecase, Mapping):
            continue
        usecase_id = str(usecase.get("id", "")).strip()
        if not usecase_id:
            continue
        usecase_text = " ".join(
            str(usecase.get(key, "")).strip()
            for key in ("actor", "name", "description")
            if str(usecase.get(key, "")).strip()
        )
        contracts.append(
            {
                "usecase_id": usecase_id,
                "actor": limit_text_for_policy(usecase.get("actor", ""), 60),
                "usecase_name": limit_text_for_policy(usecase.get("name", ""), 80),
                "process_target": str(usecase.get("process_target", "")).strip().upper(),
                "lifecycle_questions": state_lifecycle_questions_for_usecase(usecase_text),
                "required_transition": "이 유즈케이스가 고객/업무 상태를 실제로 바꾸면 state_transitions.usecase_ids에 포함한다. 상태 변화가 없으면 프로세스·기능·정책 기준으로 넘긴다.",
                "event_name_rule": "이 유즈케이스가 만든 전이의 event 값은 유즈케이스명이 아니라 상태를 바꾸는 업무 사건이어야 한다.",
            }
        )
    return {
        "primary_rule": "상태 후보는 모든 액터 유즈케이스를 검토하되, 실제 고객/업무 상태를 바꾸는 시작, 판정, 완료, 예외, 운영 확인 lifecycle에서만 도출한다.",
        "usecase_lifecycles": contracts,
        "merge_rule": "여러 유즈케이스가 같은 상태를 공유하면 상태 행은 하나로 두고, 전이 usecase_ids 배열에 여러 유즈케이스 ID를 넣는다.",
        "term_rule": "용어 장은 상태명 표준화를 위한 보조 사전이다. 유즈케이스 lifecycle에 필요하지 않은 용어를 상태로 만들지 않는다.",
    }


def state_lifecycle_questions_for_usecase(usecase_text: str) -> List[str]:
    questions = [
        "이 유즈케이스가 시작되기 전 또는 진입 직후 고객/운영자가 구분해야 하는 상태는 무엇인가?",
        "이 유즈케이스 수행 중 BSS·인증기관·연계 시스템 판정이 모이는 판정/처리 중 상태가 필요한가?",
        "정상 완료 시 고객에게 노출되거나 후속 프로세스를 허용하는 완료 상태는 무엇인가?",
        "제한, 실패, 보류, 만료, 취소, 운영 확인처럼 정상 완료 외에 닫아야 하는 상태가 무엇인가?",
    ]
    if any(keyword in usecase_text for keyword in ("운영자", "관리자", "관리", "모니터링", "검토", "승인", "보정")):
        questions.append("운영자 처리 결과가 운영 확인 필요 또는 운영 반영 완료 상태로 닫히는가?")
    if any(keyword in usecase_text for keyword in ("확인", "조회", "검색", "열람")):
        questions.append("조회·확인 결과는 결과 제공, 무결과, 제한, 후속 연결 중 어떤 상태로 분기하는가?")
    if any(keyword in usecase_text for keyword in ("신청", "주문", "가입", "변경", "해지", "취소", "수락", "거절", "결제", "납부", "등록")):
        questions.append("요청 접수 이후 허용, 불허, 보류, 실패, 완료 출구가 모두 닫히는가?")
    return unique_nonempty(questions)


def state_term_contract_for_prompt(spec: Mapping[str, object]) -> dict:
    candidates = state_term_candidates(spec, limit=24)
    return {
        "state_name_vocabulary_from_terms": candidates,
        "rules": [
            "이 목록은 상태 후보의 출처가 아니라 상태명 표준화 사전이다.",
            "유즈케이스 lifecycle에서 필요한 상태가 이 목록의 용어와 같은 의미이면 states.name에 정확히 같은 이름을 사용한다.",
            "이 목록에 있어도 유즈케이스 수행 전후 상태가 아니면 상태 코드로 만들지 않는다.",
            "후보명을 더 길게 바꾸거나 완료/중/상태 같은 접미어를 붙여 유사 상태명으로 만들지 않는다.",
        ],
    }


def state_usecase_contract_for_prompt(spec: Mapping[str, object]) -> dict:
    actor_usecases: List[dict] = []
    for usecase in spec.get("usecases", []):
        if not isinstance(usecase, Mapping):
            continue
        row = {
            "id": str(usecase.get("id", "")).strip(),
            "actor": limit_text_for_policy(usecase.get("actor", ""), 60),
            "name": limit_text_for_policy(usecase.get("name", ""), 80),
            "description": limit_text_for_policy(usecase.get("description", ""), 140),
            "process_target": str(usecase.get("process_target", "")).strip().upper(),
        }
        if not row["id"]:
            continue
        actor_usecases.append(row)
    return {
        "allowed_transition_usecase_ids": actor_usecases,
        "rule": "state_transitions.usecase_ids에는 모든 액터 유즈케이스 ID를 사용할 수 있지만, 실제 상태 변화가 있는 전이에만 연결한다. event는 연결된 유즈케이스 흐름에서 발생한 상태 변화 사건이고, 세부 판정 조건과 시간 기준은 criteria에 작성한다.",
    }


def state_focused_spec_summary(spec: Mapping[str, object]) -> dict:
    overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
    return {
        "overview": {
            "scope": compact_strings(overview.get("scope", []), 140, 8),
            "principles": compact_strings(overview.get("principles", []), 140, 8),
        },
        "terms": compact_dicts(spec.get("terms", []), ("id", "name", "description"), 110, 24),
        "actors": compact_dicts(spec.get("actors", []), ("id", "name", "responsibility"), 120, 18),
        "usecases": compact_dicts(
            spec.get("usecases", []),
            ("id", "actor", "name", "description", "process_target"),
            130,
            40,
        ),
    }


def feedback_resolution_block(feedback: Sequence[Mapping[str, object]] | None) -> str:
    if not feedback:
        return "보완 완료 기준:\n없음"
    items: List[dict] = []
    for index, item in enumerate(feedback, start=1):
        if not isinstance(item, Mapping):
            continue
        issue_id = str(item.get("issue_id") or f"FB-{index:02d}")
        title = limit_text_for_policy(item.get("title", ""), 70)
        recommendation = limit_text_for_policy(item.get("recommendation") or item.get("required_fix", ""), 180)
        acceptance = limit_text_for_policy(item.get("acceptance_check", ""), 180)
        detail = limit_text_for_policy(item.get("detail") or item.get("problem", ""), 180)
        items.append(
            {
                "issue_id": issue_id,
                "priority_tier": limit_text_for_policy(item.get("priority_tier", ""), 8),
                "batch_label": limit_text_for_policy(item.get("batch_label", ""), 80),
                "failure_type": limit_text_for_policy(item.get("failure_type", ""), 32),
                "must_change": "해당 finding이 다시 나오지 않도록 JSON 값 자체를 수정한다.",
                "target": title,
                "problem": detail,
                "required_fix": recommendation,
                "acceptance_check": acceptance or "동일 원인의 Inspector finding이 반복되지 않아야 한다.",
            }
        )
    if not items:
        return "보완 완료 기준:\n없음"
    return (
        "보완 완료 기준:\n"
        "아래 항목은 설명만 추가하지 말고 담당 챕터 JSON의 ID, 명칭, 설명, 연결값 중 하나 이상을 실제로 바꿔 해결해야 한다.\n"
        + prompt_json_unlimited(items)
    )


def state_repair_contract_block(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]] | None,
) -> str:
    if agent.chapter_key != "state":
        return ""
    if not feedback:
        return (
            "상태 전이 설계 패턴:\n"
            + prompt_json_unlimited(state_transition_design_pattern())
        )
    return (
        "상태 전이 보완 구조화 지시:\n"
        + prompt_json_unlimited(state_repair_contract(current_payload, feedback))
    )


def state_authoring_contract_block(
    agent: ChapterAgent,
    current_spec: Mapping[str, object],
    local_payload: Mapping[str, object],
) -> str:
    if agent.chapter_key != "state":
        return ""
    usecases = [
        {
            "id": usecase.get("id", ""),
            "actor": usecase.get("actor", ""),
            "name": usecase.get("name", ""),
            "process_target": str(usecase.get("process_target", "")).strip().upper(),
        }
        for usecase in current_spec.get("usecases", [])
        if isinstance(usecase, Mapping)
        and str(usecase.get("id", "")).strip()
    ]
    state_seed = compact_dicts(
        local_payload.get("states", []),
        ("id", "name", "description", "next_action"),
        100,
        14,
    )
    transition_seed = compact_dicts(
        local_payload.get("state_transitions", []),
        ("usecase_ids", "current_state", "event", "next_state", "criteria"),
        110,
        30,
    )
    return (
        "상태 장 작성 계약:\n"
        + prompt_json_unlimited(
            {
                "non_empty_required": "states와 state_transitions는 절대 빈 배열로 반환하지 않는다.",
                "usecase_rule": "모든 state_transitions.usecase_ids는 상태 변경을 발생시키는 액터 유즈케이스 ID 목록이다. 시스템 판정 결과로 상태가 바뀌면 해당 시스템 액터 유즈케이스도 사용할 수 있다.",
                "event_rule": "모든 state_transitions.event는 연결된 usecase_ids의 유즈케이스 흐름에서 발생한 상태 변화 사건이어야 한다. 유즈케이스명은 usecase_ids로만 추적한다.",
                "dedupe_rule": "같은 현재 상태·이벤트·다음 상태·criteria가 여러 유즈케이스에서 공통으로 발생하면 행을 복제하지 말고 usecase_ids에 여러 ID를 넣는다.",
                "branch_priority_rule": "같은 current_state가 2회 이상 등장하면 해당 전이들의 criteria에 '우선순위:' 또는 '배타 조건:'을 명시한다. 실패·제한·보류 조건을 먼저 쓰고, 그 외 정상 완료 조건을 마지막에 둔다.",
                "allowed_usecase_ids": usecases,
                "size_rule": "간소화본은 상태 개수를 맞추지 않는다. 샘플처럼 후속 처리 기준이 다른 핵심 상태와 대표 전이만 작성한다.",
                "coverage_rule": "allowed_usecase_ids 전체를 기계적으로 포함하지 않는다. 실제 고객/업무 상태를 바꾸는 유즈케이스만 state_transitions.usecase_ids에 포함한다.",
                "state_seed_to_rework": state_seed,
                "transition_seed_to_rework": transition_seed,
                "must_return": [
                    "states: id/name/description/next_action 필수. 업무 경계가 없는 임시 처리 상태는 제외.",
                    "state_transitions: usecase_ids/current_state/event/next_state/criteria 필수. event는 업무 사건, usecase_ids는 추적성.",
                    "current_state와 next_state는 states.name 중 하나를 정확히 사용한다.",
                    "각 전이는 연결된 유즈케이스의 완료·판정·조회·저장·회신 흐름에서 발생하는 상태 변경이어야 한다.",
                ],
            }
        )
    )


def process_upstream_contract_block(agent: ChapterAgent, current_spec: Mapping[str, object]) -> str:
    if agent.chapter_key != "process":
        return ""
    states = current_spec.get("states", [])
    usecases = current_spec.get("usecases", [])
    actors = current_spec.get("actors", [])
    approved_states = [
        {"id": state.get("id", ""), "name": state.get("name", "")}
        for state in states
        if isinstance(state, Mapping) and str(state.get("name", "")).strip()
    ]
    y_usecases = [
        {
            "id": usecase.get("id", ""),
            "name": usecase.get("name", ""),
            "actor": usecase.get("actor", ""),
            "process_target": usecase.get("process_target", ""),
        }
        for usecase in usecases
        if isinstance(usecase, Mapping) and str(usecase.get("process_target", "")).strip().upper() == "Y"
    ]
    actor_names = [
        actor.get("name", "")
        for actor in actors
        if isinstance(actor, Mapping) and str(actor.get("name", "")).strip()
    ]
    return (
        "프로세스 승인 계약:\n"
        + prompt_json_unlimited(
            {
                "rule": "Process Agent는 이전 장의 승인된 액터·유즈케이스·상태를 기준선으로 사용한다.",
                "approved_actor_names": actor_names[:20],
                "process_target_y_usecases": y_usecases[:80],
                "approved_states": approved_states[:80],
                "process_rules": [
                    "프로세스 설명에 상태명처럼 보이는 완료/보류/제한/실패 표현을 쓸 때는 approved_states.name 중 하나와 같은 명칭을 사용한다.",
                    "새 상태가 정말 필요하면 프로세스에서 임의로 만들지 말고 Inspector가 upstream_chapter=state로 분류할 수 있게 기존 상태명 안에서 문제를 드러낸다.",
                    "AI 시스템은 의도 해석, 응답 후보 생성, 분류·추천을 담당한다. 고객 노출 경로 확정과 업무 분기 확정은 채널 업무 시스템 또는 BSS/연계 시스템 책임으로 분리한다.",
                    "BSS/연계 시스템은 자격, 상태, 제한 조건, 원장 반영, 결과 회신의 판정 주체로 작성한다.",
                    "process_target=Y 유즈케이스는 고객/운영자가 완료하려는 업무의 실제 책임·판단·처리·결과 경계가 드러나도록 프로세스로 분해한다.",
                ],
            }
        )
    )


def state_transition_design_pattern() -> dict:
    return {
        "pattern": "핵심 판정 경계 중심 상태 모델",
        "rules": [
            "상태는 화면 단계가 아니라 고객 가능 여부, BSS/연계 판정, 후속 조치가 달라지는 경계만 분리한다.",
            "회원가입·탈퇴 샘플처럼 미가입, 정상, 휴면, 탈퇴유예, 탈퇴완료, 재가입제한, 가입제한, 상태확인불가 같은 오래 남는 업무 상태를 우선한다.",
            "전이 이벤트는 유즈케이스명이 아니라 상태를 바꾸는 업무 사건이다. 예: 회원 가입 완료, 기존 정상 회원 식별, 유예 기간 만료, 상태 조회 실패.",
            "로그인 세션, 인증 실패, 동의 누락, BSS 처리 중, 판정 중처럼 순간적인 처리 단계는 상태가 아니라 criteria, 프로세스, 정책 항목으로 내린다.",
            "모든 예외를 별도 상태로 만들지 말고, 후속 처리나 고객 가능 여부가 같으면 criteria와 정책 항목으로 내린다.",
            "조회 준비, 처리 중, 통합 조회 중처럼 조건을 모으는 판정 허브 상태에서 대표 결과 상태로 분기한다.",
            "조회 완료, 권한 제한, 조회 보류, 연계 실패, 정합성 예외 같은 결과 상태끼리는 직접 이동하지 않는다.",
            "결과 상태에서 다시 조회하거나 재판정할 때는 판정 허브 상태로 되돌린 뒤 같은 우선순위 체계로 다시 분기한다.",
            "고객 노출 결과 상태가 원천 업무 변경, BSS 회신, 외부 연계 콜백으로 바뀔 수 있으면 시스템 유즈케이스 이벤트로 판정 허브 재진입 전이를 둔다.",
            "각 결과 상태 description의 원인은 적어도 하나의 inbound transition criteria로 도달 가능해야 한다.",
            "여러 결과 분기가 같은 현재 상태에서 출발하면 criteria에 먼저 적용할 예외와 마지막 완료 조건을 함께 드러낸다.",
            "전이표는 모든 사건 조합을 exhaustive하게 쓰는 표가 아니다. 정상, 제한, 보류, 실패, 운영 확인처럼 후속 처리가 달라지는 대표 경로만 쓴다.",
        ],
        "anti_patterns": [
            "완료 상태에서 제한/실패/보류 상태로 직접 이동",
            "상태 설명에는 원인이 있는데 해당 상태로 들어오는 전이 기준이 없음",
            "고객이 이미 본 결과 상태가 원천 업무 변경을 받아도 갱신 전이가 없어 다음 조회에만 의존함",
            "다시 조회 전이가 예외 재판정을 우회하고 바로 완료로 이동",
            "운영자 유즈케이스 없이 운영자가 고객별 BSS 판정을 확정하는 상태",
            "개수를 채우려고 실패, 보류, 제한 사유를 각각 별도 상태로 과분해하는 상태",
            "같은 후속 조치로 돌아가는 예외를 전이 행으로 모두 복제하는 전이표",
            "유즈케이스명을 event에 반복해 상태 변화 사건이 보이지 않는 전이표",
            "인증·세션·BSS 내부 처리 단계를 상태 코드 목록으로 승격하는 구조",
        ],
    }


def state_repair_contract(
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> dict:
    feedback_text = feedback_text_blob(feedback)
    affected_names = names_mentioned_in_feedback(current_payload, feedback_text)
    states = current_payload.get("states", [])
    transitions = current_payload.get("state_transitions", [])
    affected_states = [
        copy.deepcopy(state)
        for state in states
        if isinstance(state, Mapping) and str(state.get("name", "")).strip() in affected_names
    ]
    affected_transitions = affected_state_transitions(transitions, affected_names)
    if not affected_transitions and any(keyword in feedback_text for keyword in ("전이", "criteria", "도달", "재조회", "다시 조회", "우선순위")):
        affected_transitions = state_transition_sample_for_repair(transitions)
    return {
        "repair_mode": "상태 장 내부 정합성 보완",
        "affected_state_names": sorted(affected_names),
        "affected_states": compact_dicts(affected_states, ("id", "name", "description", "next_action"), 120, 12),
        "affected_transitions": compact_dicts(
            affected_transitions,
            ("usecase_ids", "current_state", "event", "next_state", "criteria"),
            120,
            24,
        ),
        "required_actions": state_repair_actions(feedback_text),
        "acceptance_checks": [
            "모든 state_transitions.usecase_ids는 상태 변경을 발생시키는 액터 유즈케이스 ID 목록이다.",
            "모든 state_transitions.event는 샘플처럼 상태를 바꾸는 업무 사건이고, 유즈케이스 추적성은 usecase_ids에 있다.",
            "모든 states.name은 state_transitions.current_state 또는 next_state에서 정확히 같은 명칭으로만 참조된다.",
            "각 결과 상태 description의 원인은 inbound transition criteria 중 하나 이상으로 도달 가능하다.",
            "description을 고치면 inbound/outbound transition criteria도 함께 맞춘다.",
            "누락 전이를 지적받아도 항상 행을 늘리지 않는다. 같은 후속 조치로 처리 가능한 경우 description 또는 criteria를 좁혀 모순을 제거한다.",
            "다시 조회·재판정은 결과 상태에서 다른 결과 상태로 직접 이동하지 않고 판정 허브 상태로 돌아간다.",
            "동일 현재 상태의 예외/제한/완료 분기에는 우선순위 또는 배타 조건이 있다.",
            "본문에는 US-, TM-, ACT-, ST- 같은 내부 ID가 없다.",
        ],
        "design_pattern": state_transition_design_pattern(),
    }


def state_transition_sample_for_repair(values: object) -> List[dict]:
    if not isinstance(values, list):
        return []
    rows = [copy.deepcopy(item) for item in values if isinstance(item, dict)]
    exception_keywords = ("실패", "제한", "보류", "예외", "불일치", "누락", "중단", "만료", "취소")
    selected = [
        row
        for row in rows
        if any(keyword in f"{row.get('event', '')} {row.get('next_state', '')} {row.get('criteria', '')}" for keyword in exception_keywords)
    ]
    if len(selected) < 8:
        selected.extend(row for row in rows if row not in selected)
    return selected[:24]


def state_repair_actions(feedback_text: str) -> List[dict]:
    actions: List[dict] = []
    if any(keyword in feedback_text for keyword in ("도달", "누락", "없습니다", "비어")):
        actions.append(
            {
                "type": "missing_or_unreachable_transition",
                "instruction": "상태를 삭제하기보다 먼저 해당 상태 description의 원인을 만족하는 inbound transition을 추가하거나 기존 description/criteria를 좁게 보완한다. 전이 행 추가는 고객 주 흐름 또는 명시된 next_action이 실제로 막힐 때만 선택한다.",
            }
        )
    if any(keyword in feedback_text for keyword in ("원인 범위", "description", "criteria", "넓", "좁", "서로 다름")):
        actions.append(
            {
                "type": "description_criteria_alignment",
                "instruction": "상태 description과 해당 상태로 들어오는 전이 criteria를 한 쌍으로 수정한다. 둘 중 하나만 바꾸지 않는다.",
            }
        )
    if any(keyword in feedback_text for keyword in ("재조회", "다시 조회", "self-loop", "동일 상태")):
        actions.append(
            {
                "type": "requery_routing",
                "instruction": "결과 상태의 다시 조회는 완료/제한/실패 같은 다른 결과 상태로 직접 보내지 말고 판정 허브 상태로 되돌려 같은 우선순위로 재판정한다.",
            }
        )
    if any(keyword in feedback_text for keyword in ("동기화", "원천", "조건 변경", "만료", "비동기", "다시 열지", "재판정")):
        actions.append(
            {
                "type": "async_source_sync",
                "instruction": "고객 노출 결과 상태가 원천 업무 완료·취소·조건 변경·만료를 받을 수 있으면 시스템/BSS 유즈케이스 이벤트로 판정 허브 재진입 또는 완료·무효 확정 전이를 추가한다.",
            }
        )
    if any(keyword in feedback_text for keyword in ("우선", "순위", "동시", "분기", "배타")):
        actions.append(
            {
                "type": "branch_priority",
                "instruction": "같은 current_state에서 여러 결과로 갈라지는 criteria에 먼저 적용할 예외와 마지막 완료 조건을 명시한다.",
            }
        )
    if any(keyword in feedback_text for keyword in ("운영", "책임", "BSS", "판정")):
        actions.append(
            {
                "type": "responsibility_boundary",
                "instruction": "운영자는 기준 보정과 예외 관리까지만 쓰고 고객별 BSS 판정 결과 확정 책임은 BSS/채널 판정 흐름으로 둔다.",
            }
        )
    if not actions:
        actions.append(
            {
                "type": "state_consistency_general",
                "instruction": "Inspector finding의 대상 상태명과 전이 기준을 찾아 상태 설명, next_action, inbound/outbound transition을 함께 정합화한다.",
            }
        )
    return actions


PATCH_REVISION_CHAPTERS = {
    "overview",
    "terms",
    "terms_refinement",
    "actors",
    "usecases",
    "usecase_diagram",
    "state",
    "process",
    "process_detail",
    "functions",
    "function_detail",
    "policies",
    "final_check",
}
DEFAULT_SCOPED_FULL_REVISION_MAX_SCORE = 71
BROAD_REMEDIATION_MODES = {
    "scoped_section_revision",
    "scoped_full_revision",
    "blueprint_realign_revision",
}
ID_FIELD_BY_LIST = {
    "terms": "id",
    "actors": "id",
    "usecases": "id",
    "states": "id",
    "processes": "id",
    "process_details": "process_id",
    "functions": "id",
    "function_details": "function_id",
    "policy_groups": "id",
    "policy_details": "id",
}
ID_PATTERN = re.compile(r"(?<![A-Z0-9])(?:TM|ACT|US|ST|PR|FN|PG|PI)-[A-Z0-9]+-[A-Z0-9-]+(?![A-Z0-9-])")
PATCH_ADDITION_KEYWORDS = (
    "추가",
    "누락",
    "없음",
    "신규",
    "생성",
    "보강",
    "add",
    "missing",
    "new",
    "create",
)


def should_use_patch_revision(
    agent: ChapterAgent,
    spec: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]] | None,
) -> bool:
    if agent.chapter_key not in PATCH_REVISION_CHAPTERS or not feedback:
        return False
    if not has_patchable_current_payload(agent, spec):
        return False
    if prefers_targeted_process_function_patch(agent, spec, feedback):
        return True
    if feedback_remediation_mode(feedback) in BROAD_REMEDIATION_MODES:
        return False
    if requires_scoped_full_revision(agent, feedback):
        return False
    return True


def prefers_targeted_process_function_patch(
    agent: ChapterAgent,
    spec: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> bool:
    """Avoid chunk rewrites when Inspector feedback identifies exact rows.

    Process, functions, and policies are the most expensive chunked chapters.
    When feedback contains concrete target_path values or IDs that map to the
    current payload, patching those rows is safer and cheaper than regenerating
    the whole chapter chunk.
    """
    if agent.chapter_key not in {"process", "functions", "policies"}:
        return False
    current_payload = current_patchable_payload(agent, spec)
    explicit_target = explicit_revision_patch_target(agent, current_payload, feedback)
    if not explicit_target:
        return False
    targeted_rows = sum(len(value) for value in explicit_target.values() if isinstance(value, list))
    total_rows = sum(len(value) for value in current_payload.values() if isinstance(value, list))
    if targeted_rows <= 0:
        return False
    if total_rows <= 0:
        return True
    return targeted_rows <= max(3, min(12, total_rows))


def has_patchable_current_payload(agent: ChapterAgent, spec: Mapping[str, object]) -> bool:
    current_payload = current_patchable_payload(agent, spec)
    for value in current_payload.values():
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, list) and value:
            return True
    return False


def current_patchable_payload(agent: ChapterAgent, spec: Mapping[str, object]) -> dict:
    if hasattr(agent, "extract_payload"):
        return agent.extract_payload(dict(spec))
    current_payload = {}
    for field in getattr(agent, "output_fields", ()):
        if field == "meta.usecase_diagram":
            current_payload["usecase_diagram"] = copy.deepcopy(spec.get("meta", {}).get("usecase_diagram", {}))
        else:
            current_payload[field] = copy.deepcopy(spec.get(field))
    return current_payload


def requires_scoped_full_revision(agent: ChapterAgent, feedback: Sequence[Mapping[str, object]]) -> bool:
    """Use full chapter revision only for very low-score structural failures."""
    if feedback_remediation_mode(feedback) in BROAD_REMEDIATION_MODES:
        return agent.chapter_key in PATCH_REVISION_CHAPTERS
    if not scoped_full_revision_allowed(feedback):
        return False
    categories = {
        str(item.get("category", "")).strip().casefold()
        for item in feedback
        if isinstance(item, Mapping)
    }
    text = feedback_text_blob(feedback)
    has_id_specific_target = bool(ID_PATTERN.search(text))
    failure_types = {
        str(item.get("failure_type", "")).strip()
        for item in feedback
        if isinstance(item, Mapping)
    }
    broad_keywords = ("전반", "전체", "구조", "균형", "일반론", "장황", "잘게", "과도", "누락 가능", "샘플 수준")
    structural_types = {"content_quality", "sample_concision", "state_consistency"}
    has_structural_signal = (
        len(feedback) > 8
        or "structure" in categories
        or "구조" in categories
        or bool(failure_types & structural_types)
        or any(keyword in text for keyword in broad_keywords)
    )
    if not has_structural_signal:
        return False
    if has_id_specific_target and len(feedback) <= 3 and not any(keyword in text for keyword in ("전반", "전체", "구조", "샘플 수준")):
        return False
    return agent.chapter_key in PATCH_REVISION_CHAPTERS


def scoped_full_revision_allowed(feedback: Sequence[Mapping[str, object]]) -> bool:
    score = feedback_inspector_score(feedback)
    return score is not None and score <= scoped_full_revision_max_score()


def feedback_remediation_mode(feedback: Sequence[Mapping[str, object]] | None) -> str:
    priority = {
        "blueprint_realign_revision": 4,
        "scoped_full_revision": 3,
        "scoped_section_revision": 2,
        "patch": 1,
    }
    selected = "patch"
    for item in feedback or []:
        if not isinstance(item, Mapping):
            continue
        mode = str(item.get("remediation_mode", "") or "").strip()
        if priority.get(mode, 0) > priority.get(selected, 0):
            selected = mode
    return selected


def scoped_full_revision_max_score() -> int:
    raw = os.getenv("SCOPED_FULL_REVISION_MAX_SCORE", "").strip()
    try:
        return max(0, min(100, int(raw))) if raw else DEFAULT_SCOPED_FULL_REVISION_MAX_SCORE
    except ValueError:
        return DEFAULT_SCOPED_FULL_REVISION_MAX_SCORE


def feedback_inspector_score(feedback: Sequence[Mapping[str, object]]) -> Optional[int]:
    scores: List[int] = []
    for item in feedback or []:
        if not isinstance(item, Mapping):
            continue
        for key in ("inspector_score", "score"):
            value = item.get(key)
            if value in (None, ""):
                continue
            try:
                scores.append(int(value))
            except (TypeError, ValueError):
                continue
    return min(scores) if scores else None


def revision_patch_target(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> dict:
    feedback_text = feedback_text_blob(feedback)
    affected_ids = set(ID_PATTERN.findall(feedback_text))
    affected_names = names_mentioned_in_feedback(current_payload, feedback_text)
    target: dict = target_items_from_feedback_paths(agent, current_payload, feedback)
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        values = current_payload.get(schema_key, [])
        if isinstance(values, Mapping):
            if schema_key in feedback_target_schema_keys(agent, feedback_text):
                target[schema_key] = copy.deepcopy(dict(values))
            continue
        if not isinstance(values, list):
            continue
        if schema_key == "state_transitions":
            target[schema_key] = affected_state_transitions(values, affected_names)
            continue
        selected = [
            copy.deepcopy(item)
            for item in values
            if isinstance(item, dict) and item_matches_revision_target(schema_key, item, affected_ids, affected_names)
        ]
        target[schema_key] = merge_target_items(target.get(schema_key, []), selected)
    if agent.chapter_key == "policies":
        target = expand_policy_patch_target(target, current_payload)
    if agent.chapter_key == "state" and target.get("states"):
        names = {str(item.get("name", "")).strip() for item in target["states"] if isinstance(item, dict)}
        transitions = affected_state_transitions(current_payload.get("state_transitions", []), names | affected_names)
        if transitions:
            target["state_transitions"] = transitions
    if not any(isinstance(value, list) and value for value in target.values()):
        target = fallback_revision_patch_target(agent, current_payload, feedback_text)
    return {
        key: value
        for key, value in target.items()
        if (isinstance(value, list) and value) or (isinstance(value, Mapping) and value)
    }


def explicit_revision_patch_target(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> dict:
    """Return only targets explicitly identified by path, ID, or row name."""
    feedback_text = feedback_text_blob(feedback)
    affected_ids = set(ID_PATTERN.findall(feedback_text))
    affected_names = names_mentioned_in_feedback(current_payload, feedback_text)
    target: dict = target_items_from_feedback_paths(agent, current_payload, feedback)
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        values = current_payload.get(schema_key, [])
        if not isinstance(values, list):
            continue
        selected = [
            copy.deepcopy(item)
            for item in values
            if isinstance(item, dict) and item_matches_revision_target(schema_key, item, affected_ids, affected_names)
        ]
        target[schema_key] = merge_target_items(target.get(schema_key, []), selected)
    return {
        key: value
        for key, value in target.items()
        if isinstance(value, list) and value
    }


def target_items_from_feedback_paths(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> dict:
    """Select exact JSON rows from Inspector target_path values like processes[2]."""
    allowed_fields = {"usecase_diagram" if field == "meta.usecase_diagram" else field for field in agent.output_fields}
    target: dict = {}
    for item in feedback or []:
        if not isinstance(item, Mapping):
            continue
        for field, index in target_indexes_from_path(str(item.get("target_path", ""))):
            if field not in allowed_fields:
                continue
            values = current_payload.get(field, [])
            if not isinstance(values, list) or index < 0 or index >= len(values):
                continue
            row = values[index]
            if isinstance(row, dict):
                target[field] = merge_target_items(target.get(field, []), [copy.deepcopy(row)])
    return target


def target_indexes_from_path(path: str) -> List[tuple[str, int]]:
    result: List[tuple[str, int]] = []
    for match in re.finditer(r"(?:current_chapter\.)?([A-Za-z_]+)\[(\d+)\]", str(path or "")):
        try:
            result.append((match.group(1), int(match.group(2))))
        except ValueError:
            continue
    return result


def target_field_refs_from_path(path: str) -> List[dict]:
    refs: List[dict] = []
    for match in re.finditer(r"(?:current_chapter\.)?([A-Za-z_]+)\[(\d+)\](?:\.([A-Za-z_]+))?", str(path or "")):
        try:
            refs.append(
                {
                    "field": match.group(1),
                    "index": int(match.group(2)),
                    "property": match.group(3) or "",
                }
            )
        except ValueError:
            continue
    return refs


def merge_target_items(existing: object, additions: Sequence[object]) -> List[dict]:
    result = [copy.deepcopy(item) for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
    seen_ids = {patch_item_identity(item) for item in result if patch_item_identity(item)}
    seen_serialized = {json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) for item in result}
    for item in additions:
        if not isinstance(item, dict):
            continue
        item_id = patch_item_identity(item)
        serialized = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if item_id and item_id in seen_ids:
            continue
        if not item_id and serialized in seen_serialized:
            continue
        if item_id:
            seen_ids.add(item_id)
        seen_serialized.add(serialized)
        result.append(copy.deepcopy(item))
    return result


def patch_item_identity(item: Mapping[str, object]) -> str:
    return str(item.get("id") or item.get("process_id") or item.get("function_id") or "").strip()


def fallback_revision_patch_target(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    feedback_text: str,
) -> dict:
    """When Inspector gives a rule-level finding without IDs, still patch narrowly by chapter field."""
    target_fields = feedback_target_schema_keys(agent, feedback_text)
    if not target_fields:
        return {}
    target: dict = {}
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        if schema_key not in target_fields:
            continue
        values = current_payload.get(schema_key, [])
        if isinstance(values, Mapping) and values:
            target[schema_key] = copy.deepcopy(dict(values))
            continue
        if not isinstance(values, list) or not values:
            continue
        target[schema_key] = copy.deepcopy(values[: fallback_patch_item_limit(agent, schema_key)])
    return target


def default_revision_patch_target(agent: ChapterAgent, current_payload: Mapping[str, object]) -> dict:
    """Keep revisions in delta mode even when Inspector feedback has no explicit ID."""
    target: dict = {}
    preferred_fields = {
        "terms": ("terms",),
        "terms_refinement": ("terms",),
        "overview": ("overview",),
        "actors": ("actors",),
        "usecases": ("usecases",),
        "usecase_diagram": ("usecase_diagram",),
        "state": ("states", "state_transitions"),
        "process": ("processes",),
        "process_detail": ("process_details",),
        "functions": ("functions",),
        "function_detail": ("function_details",),
        "policies": ("policy_groups", "policy_details"),
        "final_check": ("final_check",),
    }.get(agent.chapter_key, ())
    for schema_key in preferred_fields:
        values = current_payload.get(schema_key, [])
        if isinstance(values, Mapping) and values:
            target[schema_key] = copy.deepcopy(dict(values))
            continue
        if not isinstance(values, list) or not values:
            continue
        target[schema_key] = copy.deepcopy(values[: default_patch_item_limit(agent, schema_key)])
    return target


def default_patch_item_limit(agent: ChapterAgent, schema_key: str) -> int:
    limits = {
        "terms": 10,
        "actors": 8,
        "usecases": 12,
        "states": 10,
        "state_transitions": 14,
        "processes": 10,
        "process_details": 10,
        "functions": 12,
        "function_details": 12,
        "policy_groups": 8,
        "policy_details": 16,
        "final_check": 12,
    }
    if agent.chapter_key in {"functions", "function_detail", "policies"}:
        return min(limits.get(schema_key, 10), 10)
    return limits.get(schema_key, 10)


def feedback_target_schema_keys(agent: ChapterAgent, feedback_text: str) -> set[str]:
    text = feedback_text.casefold()
    candidates: set[str] = set()
    keyword_map = (
        ("overview", ("개요", "범위", "설계 원칙", "설계원칙", "원칙", "scope", "principle")),
        ("terms", ("용어", "term")),
        ("actors", ("액터", "actor", "주체", "책임")),
        ("usecases", ("유즈케이스", "usecase", "use case")),
        ("states", ("상태", "state")),
        ("state_transitions", ("전이", "transition")),
        ("processes", ("프로세스", "process", "흐름")),
        ("process_details", ("프로세스 상세", "진입 조건", "종료 조건", "선행 프로세스", "후행 프로세스")),
        ("functions", ("기능", "function")),
        ("function_details", ("기능 상세", "입력 정보", "처리 로직", "출력 정보", "실패", "예외")),
        ("policy_groups", ("정책 그룹", "정책 목록", "policy group")),
        ("policy_details", ("정책 상세", "정책 기준", "policy detail", "판단값", "허용", "제한", "예외", "고지", "이력")),
    )
    for schema_key, keywords in keyword_map:
        if any(keyword.casefold() in text for keyword in keywords):
            candidates.add(schema_key)
    if any(keyword in text for keyword in ("샘플", "밀도", "분량", "구체성", "일반론", "주제 특화", "연결성")):
        candidates.update("usecase_diagram" if field == "meta.usecase_diagram" else field for field in agent.output_fields)
    allowed = {"usecase_diagram" if field == "meta.usecase_diagram" else field for field in agent.output_fields}
    return candidates & allowed


def fallback_patch_item_limit(agent: ChapterAgent, schema_key: str) -> int:
    limits = {
        "terms": 12,
        "actors": 8,
        "usecases": 12,
        "states": 12,
        "state_transitions": 18,
        "processes": 12,
        "process_details": 12,
        "functions": 14,
        "function_details": 14,
        "policy_groups": 10,
        "policy_details": 18,
    }
    return limits.get(schema_key, 12)


def feedback_text_blob(feedback: Sequence[Mapping[str, object]]) -> str:
    parts: List[str] = []
    for item in feedback:
        if not isinstance(item, Mapping):
            continue
        for key in (
            "issue_id",
            "category",
            "title",
            "detail",
            "problem",
            "recommendation",
            "required_fix",
            "acceptance_check",
        ):
            value = item.get(key)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def names_mentioned_in_feedback(current_payload: Mapping[str, object], feedback_text: str) -> set[str]:
    names: set[str] = set()
    for values in current_payload.values():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, Mapping):
                continue
            for key in ("name", "actor", "current_state", "next_state"):
                name = str(item.get(key, "")).strip()
                if name and name in feedback_text:
                    names.add(name)
    return names


def item_matches_revision_target(
    field: str,
    item: Mapping[str, object],
    affected_ids: set[str],
    affected_names: set[str],
) -> bool:
    item_id = patch_item_identity(item)
    if item_id and item_id in affected_ids:
        return True
    linked_keys = {
        "processes": ("usecase_id",),
        "process_details": ("process_id",),
        "functions": ("process_id",),
        "function_details": ("function_id",),
        "policy_details": ("policy_id",),
    }.get(field, ())
    if any(str(item.get(key, "")).strip() in affected_ids for key in linked_keys):
        return True
    name = str(item.get("name", "")).strip()
    if name and name in affected_names:
        return True
    if field == "usecases" and str(item.get("actor", "")).strip() in affected_names:
        return True
    return False


def affected_state_transitions(values: object, affected_names: set[str]) -> List[dict]:
    if not isinstance(values, list) or not affected_names:
        return []
    selected: List[dict] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        current_state = str(item.get("current_state", "")).strip()
        next_state = str(item.get("next_state", "")).strip()
        if current_state in affected_names or next_state in affected_names:
            selected.append(copy.deepcopy(item))
    return selected


def expand_policy_patch_target(target: dict, current_payload: Mapping[str, object]) -> dict:
    groups = target.get("policy_groups", []) if isinstance(target.get("policy_groups"), list) else []
    details = target.get("policy_details", []) if isinstance(target.get("policy_details"), list) else []
    group_ids = {str(group.get("id", "")).strip() for group in groups if isinstance(group, Mapping)}
    if group_ids:
        existing_detail_ids = {str(detail.get("id", "")).strip() for detail in details if isinstance(detail, Mapping)}
        for detail in current_payload.get("policy_details", []) if isinstance(current_payload.get("policy_details", []), list) else []:
            if not isinstance(detail, dict):
                continue
            detail_id = str(detail.get("id", "")).strip()
            if detail_id not in existing_detail_ids and str(detail.get("policy_id", "")).strip() in group_ids:
                details.append(copy.deepcopy(detail))
    if details:
        target["policy_details"] = details
    return target


def build_patch_revision_prompt(
    agent: ChapterAgent,
    current_spec: dict,
    patch_target: Mapping[str, object],
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]],
) -> str:
    budget = chapter_prompt_budget(agent, True)
    current_payload = agent.extract_payload(current_spec)
    focused_feedback = compact_feedback_for_prompt(
        feedback,
        agent=agent,
        current_payload=current_payload,
    )
    context_pack = context_pack_for_agent(
        agent.chapter_key,
        current_spec,
        runtime,
        limit=min(2, budget["context_items"]),
    )
    style_anchor_block = policy_style_anchor_for_prompt(agent.chapter_key)
    parts = [
        f"담당 agent: {agent.display_name}",
        f"담당 챕터: {agent.chapter_key}",
        "작업 방식: Inspector 보완 패치",
        f"작성 지침: {agent.instruction(runtime.guideline)}",
        style_anchor_block,
        "전문 분석 방법론 적용 기준:\n" + prompt_json(method_knowledge_for_agent(agent.chapter_key), 1200),
        "[Patch Mode 규칙]\n"
        "- 아래 패치 대상 JSON에 포함된 항목만 수정한다.\n"
        "- Inspector가 지적하지 않은 항목은 수정하지 않는다.\n"
        "- finding이 누락/추가를 명시한 경우에만 새 항목을 추가한다.\n"
        "- 패치 대상 밖의 ID나 새로운 ID를 임의로 반환하면 검증에서 실패한다.\n"
        "- 패치 대상에 없는 기존 항목은 반환하지 않는다.\n"
        "- 반환 JSON의 각 배열은 수정·추가할 항목만 담고, 수정할 항목이 없으면 빈 배열로 둔다.\n"
        "- 단, ID가 없는 문자열 배열은 패치 대상 범위 안의 값을 전체 배열로 반환한다.\n"
        "- 전체 장 JSON을 다시 작성하지 않는다.\n"
        "- ID와 연결 필드는 기존 값을 유지하되, Inspector가 지적한 충돌을 해결하는 경우에만 바꾼다.",
        "주제 학습 핵심:\n" + prompt_json(runtime.learning, 700),
        "작성 기준서 핵심:\n" + prompt_json(stage_blueprint_for_prompt(runtime.authoring_blueprint, agent.chapter_key), 1400),
        "패치 정합성 핵심:\n"
        + prompt_json(focused_alignment_context_for_patch(agent, current_spec, runtime, patch_target, focused_feedback), 1800),
        "근거 Context Pack 핵심:\n" + prompt_json(context_pack, 1200),
        "패치 대상 JSON:\n" + prompt_json(compact_patch_target_for_prompt(patch_target), patch_target_prompt_limit(agent)),
        "필수 패치 대상 필드:\n" + prompt_json(patch_target_field_contract(current_payload, focused_feedback), 2200),
        terms_patch_addition_rules(agent, current_payload, focused_feedback),
        "Inspector/사용자 보완 요청:\n" + prompt_json(list(focused_feedback), feedback_prompt_limit(focused_feedback, 2200)),
        "패치 수행 계획:\n" + prompt_json(patch_resolution_plan(focused_feedback, patch_target), 1800),
        process_upstream_contract_block(agent, current_spec),
        feedback_resolution_block(focused_feedback),
        "반환 요청:\n"
        "패치 대상 항목 중 실제로 고친 항목만 JSON 스키마에 맞춰 반환한다. "
        "패치 대상 밖 항목을 정리하고 싶어도 이번 반환에는 포함하지 않는다. "
        "문제 설명을 덧붙이지 말고, JSON 문자열 안에는 <br/>·HTML·마크다운을 쓰지 않는다.",
    ]
    if agent.chapter_key == "state":
        parts.insert(
            5,
            "상태 보완 원칙:\n"
            "- 상태 설명을 고치면 해당 상태로 들어오거나 나가는 전이 criteria도 함께 맞춘다.\n"
            "- 전이 criteria를 고치면 대상 상태의 description, next_action과 원인 범위가 충돌하지 않는지 함께 확인한다.\n"
            "- 이전 유즈케이스에 없는 임시저장·재개·운영 확정 업무를 새로 만들지 않는다.\n"
            "- 결과 상태에서 다시 조회·재판정할 때는 다른 결과 상태로 직접 보내지 말고 판정 허브 상태로 되돌린다.\n"
            "- 본문 문장에는 US-, TM-, ACT-, ST- 같은 내부 ID를 쓰지 않는다.",
        )
        parts.insert(
            6,
            state_repair_contract_block(agent, current_payload, focused_feedback),
        )
    return "\n\n".join(parts)


def terms_patch_addition_rules(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    focused_feedback: Sequence[Mapping[str, object]],
) -> str:
    if agent.chapter_key not in {"terms", "terms_refinement"}:
        return ""
    text = feedback_text_blob(focused_feedback)
    if not any(keyword.casefold() in text.casefold() for keyword in PATCH_ADDITION_KEYWORDS):
        return ""
    existing_terms = [item for item in current_payload.get("terms", []) if isinstance(item, Mapping)]
    ids = [str(item.get("id", "")).strip() for item in existing_terms]
    next_hint = next_sequential_id_hint(ids, "TM")
    return (
        "용어 추가 패치 규칙:\n"
        f"- Inspector가 누락 용어 추가를 요구했으므로 필요한 최소 용어를 terms 배열에 추가해도 된다. 다음 ID 힌트: {next_hint}.\n"
        "- 새 용어는 feedback의 required_change, patch_hint, acceptance_check에 직접 언급된 판단축만 추가한다.\n"
        "- 정책값 숫자, 허용 횟수, 기간 수치 자체는 추가하지 말고 그 값을 담을 판단축 명칭만 용어로 만든다.\n"
        "- 기존 용어 설명 보완과 신규 용어 추가를 함께 요구받은 경우 둘 다 반환한다. 빈 배열로 넘기면 같은 finding이 반복된다."
    )


def next_sequential_id_hint(ids: Sequence[str], prefix: str) -> str:
    max_number = 0
    sample = ""
    pattern = re.compile(rf"^({re.escape(prefix)}-[A-Z0-9]+-)(\d+)$")
    for item_id in ids:
        match = pattern.match(str(item_id or "").strip())
        if not match:
            continue
        sample = match.group(1)
        try:
            max_number = max(max_number, int(match.group(2)))
        except ValueError:
            continue
    if not sample:
        return f"{prefix}-{{업무코드}}-001"
    return f"{sample}{max_number + 1:03d}"


def compact_feedback_for_prompt(
    feedback: Sequence[Mapping[str, object]] | None,
    *,
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    max_items: Optional[int] = None,
) -> List[dict]:
    if not feedback:
        return []
    prioritized = sorted(
        [item for item in feedback if isinstance(item, Mapping)],
        key=feedback_priority,
        reverse=True,
    )
    compact: List[dict] = []
    selected = prioritized if max_items is None else prioritized[:max_items]
    for index, item in enumerate(selected, start=1):
        text = feedback_item_text(item)
        compact.append(
            {
                "issue_id": str(item.get("issue_id") or f"FB-{index:02d}"),
                "priority_tier": limit_text_for_policy(item.get("priority_tier", ""), 8),
                "batch_label": limit_text_for_policy(item.get("batch_label", ""), 80),
                "severity": limit_text_for_policy(item.get("severity", ""), 16),
                "failure_type": limit_text_for_policy(item.get("failure_type", ""), 32),
                "repair_scope": limit_text_for_policy(item.get("repair_scope", ""), 48),
                "fix_owner": limit_text_for_policy(item.get("fix_owner", "current_chapter"), 32),
                "upstream_chapter": limit_text_for_policy(item.get("upstream_chapter", ""), 32),
                "target_path": limit_text_for_policy(item.get("target_path", ""), 120),
                "inspector_score": item.get("inspector_score", ""),
                "inspector_threshold": item.get("inspector_threshold", ""),
                "remediation_mode": limit_text_for_policy(item.get("remediation_mode", "patch"), 40),
                "revision_policy": limit_text_for_policy(item.get("revision_policy", ""), 100),
                "category": limit_text_for_policy(item.get("category", ""), 36),
                "title": limit_text_for_policy(item.get("title", ""), 64),
                "feedback_quality": limit_text_for_policy(item.get("feedback_quality", ""), 32),
                "actionability_issues": limit_text_for_policy(item.get("actionability_issues", ""), 120),
                "affected_ids": sorted(ID_PATTERN.findall(text))[:8],
                "affected_names": sorted(names_mentioned_in_feedback(current_payload, text))[:8],
                "target_fields": sorted(feedback_target_schema_keys(agent, text)),
                "patch_rule": "target_path와 패치 대상 JSON에 포함된 항목만 최소 수정한다.",
                "problem": limit_text_for_policy(item.get("detail", ""), 220),
                "root_cause": limit_text_for_policy(item.get("root_cause", ""), 240),
                "required_change": limit_text_for_policy(item.get("required_change", ""), 320),
                "patch_hint": limit_text_for_policy(item.get("patch_hint", ""), 320),
                "keep_constraints": limit_text_for_policy(item.get("keep_constraints", ""), 140),
                "do_not_change": limit_text_for_policy(item.get("do_not_change", ""), 140),
                "required_fix": limit_text_for_policy(item.get("recommendation", ""), 260),
                "acceptance_check": limit_text_for_policy(
                    item.get("acceptance_check", "")
                    or "동일 원인의 finding이 다음 Inspector 결과에 반복되지 않아야 합니다.",
                    140,
                ),
            }
        )
    return compact


def patch_target_field_contract(
    current_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> List[dict]:
    contract: List[dict] = []
    for index, item in enumerate(feedback or [], start=1):
        if not isinstance(item, Mapping):
            continue
        refs = target_field_refs_from_path(str(item.get("target_path", "")))
        if not refs:
            continue
        fields: List[dict] = []
        for ref in refs:
            field = str(ref.get("field", ""))
            prop = str(ref.get("property", ""))
            row = payload_row_at(current_payload, field, int(ref.get("index", -1)))
            if not row:
                continue
            fields.append(
                {
                    "path": f"{field}[{ref.get('index')}]" + (f".{prop}" if prop else ""),
                    "row_identity": patch_item_identity(row) or state_transition_identity(row),
                    "current_value": limit_text_for_policy(row.get(prop, "") if prop else row, 180),
                    "must_change": bool(prop),
                }
            )
        if not fields:
            continue
        contract.append(
            {
                "issue_id": str(item.get("issue_id") or f"FB-{index:02d}"),
                "title": limit_text_for_policy(item.get("title", ""), 80),
                "required_change": limit_text_for_policy(item.get("required_change", "") or item.get("recommendation", ""), 320),
                "patch_hint": limit_text_for_policy(item.get("patch_hint", ""), 320),
                "fields": fields,
                "rule": "must_change=true인 필드는 패치 결과에서 기존값과 달라져야 한다. 그대로 두면 재시도된다.",
            }
        )
    return contract


def patch_resolution_plan(
    feedback: Sequence[Mapping[str, object]],
    patch_target: Mapping[str, object],
) -> List[dict]:
    target_fields = sorted(str(key) for key, value in patch_target.items() if value)
    target_ids = sorted(
        {
            str(row.get("id", "")).strip()
            for value in patch_target.values()
            if isinstance(value, list)
            for row in value
            if isinstance(row, Mapping) and str(row.get("id", "")).strip()
        }
    )
    plan: List[dict] = []
    for index, item in enumerate(feedback, start=1):
        if not isinstance(item, Mapping):
            continue
        affected_ids = sorted(str(value) for value in item.get("affected_ids", []) if isinstance(value, str))
        plan.append(
            {
                "issue_id": str(item.get("issue_id") or f"FB-{index:02d}"),
                "target_path": str(item.get("target_path", "")),
                "allowed_fields": target_fields,
                "allowed_ids": affected_ids or target_ids[:12],
                "remediation_mode": limit_text_for_policy(item.get("remediation_mode", "patch"), 40),
                "root_cause": limit_text_for_policy(item.get("root_cause", ""), 160),
                "feedback_quality": limit_text_for_policy(item.get("feedback_quality", ""), 32),
                "actionability_issues": limit_text_for_policy(item.get("actionability_issues", ""), 120),
                "required_fix": limit_text_for_policy(item.get("required_fix", "") or item.get("recommendation", ""), 180),
                "patch_hint": limit_text_for_policy(item.get("patch_hint", ""), 180),
                "acceptance_check": limit_text_for_policy(item.get("acceptance_check", ""), 160),
                "keep_constraints": limit_text_for_policy(item.get("keep_constraints", ""), 140),
                "do_not_change": limit_text_for_policy(item.get("do_not_change", ""), 140)
                or "패치 대상 밖의 항목, Inspector가 지적하지 않은 ID, 이전 장 승인 기준",
            }
        )
    return plan


def feedback_priority(item: Mapping[str, object]) -> tuple[int, int, int, int]:
    text = feedback_item_text(item)
    severity = str(item.get("severity", "")).casefold()
    must = str(item.get("must_resolve", "")).casefold()
    tier = str(item.get("priority_tier", "")).upper()
    return (
        {"P1": 3, "P2": 2, "P3": 1}.get(tier, 0),
        2 if severity == "error" else 1,
        1 if must in {"y", "true", "1"} else 0,
        1 if any(keyword in text for keyword in ("연결", "정책", "상태", "프로세스", "기능", "액터", "유즈케이스", "구체", "샘플")) else 0,
    )


def feedback_item_text(item: Mapping[str, object]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in (
            "issue_id",
            "priority_tier",
            "batch_label",
            "severity",
            "failure_type",
            "repair_scope",
            "fix_owner",
            "upstream_chapter",
            "inspector_score",
            "inspector_threshold",
            "remediation_mode",
            "revision_policy",
            "category",
            "feedback_quality",
            "actionability_issues",
            "target_path",
            "title",
            "detail",
            "root_cause",
            "required_change",
            "patch_hint",
            "keep_constraints",
            "do_not_change",
            "problem",
            "recommendation",
            "required_fix",
            "acceptance_check",
        )
        if item.get(key)
    )


def focused_alignment_context_for_patch(
    agent: ChapterAgent,
    spec: dict,
    runtime: AgentRuntime,
    patch_target: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> dict:
    full = alignment_context_for_prompt(agent, spec, runtime)
    affected_ids = {
        affected_id
        for item in feedback
        if isinstance(item, Mapping)
        for affected_id in item.get("affected_ids", [])
        if isinstance(affected_id, str)
    }
    target_ids = {
        patch_item_identity(row)
        for values in patch_target.values()
        if isinstance(values, list)
        for row in values
        if isinstance(row, Mapping) and patch_item_identity(row)
    }
    focus_ids = affected_ids | target_ids
    focused: dict = {
        "rule": full.get("rule", ""),
        "topic_axes": full.get("topic_axes", []),
        "open_inspector_issues": full.get("open_inspector_issues", [])[:2],
    }
    for key in ("actors", "usecases", "states", "processes", "process_details", "functions", "function_details", "policy_groups"):
        values = full.get(key)
        if isinstance(values, list):
            filtered = filter_compact_rows_by_ids(values, focus_ids)
            focused[key] = filtered if filtered else values[:12]
    if "policy_name_candidates" in full:
        focused["policy_name_candidates"] = full.get("policy_name_candidates", [])[:20]
    for key in ("actor_coverage_rule", "process_rule", "refinement_rule"):
        if key in full:
            focused[key] = full[key]
    return {key: value for key, value in focused.items() if value}


def filter_compact_rows_by_ids(values: Sequence[object], focus_ids: set[str]) -> List[dict]:
    if not focus_ids:
        return []
    result: List[dict] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        haystack = " ".join(str(item) for item in value.values())
        if any(focus_id and focus_id in haystack for focus_id in focus_ids):
            result.append(value)
    return result[:20]


def compact_patch_target_for_prompt(patch_target: Mapping[str, object]) -> dict:
    compact: dict = {}
    for field, values in patch_target.items():
        if field == "overview" and isinstance(values, Mapping):
            compact[field] = {
                "scope": compact_strings(values.get("scope", []), 120, 6),
                "principles": compact_dicts(values.get("principles", []), ("name", "description"), 120, 6),
            }
            continue
        if isinstance(values, Mapping):
            compact[field] = compact_dict(values, tuple(patch_field_keys(field)), 120, 40)
            continue
        if not isinstance(values, list):
            continue
        compact[field] = compact_dicts(values, tuple(patch_field_keys(field)), 120, 40)
    return compact


def patch_field_keys(field: str) -> Sequence[str]:
    return {
        "overview": ("scope", "principles"),
        "terms": ("id", "name", "description"),
        "actors": ("id", "name", "description"),
        "usecases": ("id", "actor", "name", "description", "process_target"),
        "usecase_diagram": ("lines",),
        "states": ("id", "name", "description", "next_action"),
        "state_transitions": ("usecase_ids", "current_state", "event", "next_state", "criteria"),
        "processes": ("id", "usecase_id", "name", "description", "related_functions", "related_policies"),
        "process_details": ("process_id", "entry_condition", "exit_condition", "previous_processes", "next_processes", "related_functions", "related_policies"),
        "functions": ("id", "process_id", "process_ids", "name", "description", "details"),
        "function_details": ("function_id", "input_information", "processing_logic", "sub_functions", "output_information", "failure_exception_cases", "related_policies"),
        "policy_groups": ("id", "name", "description"),
        "policy_details": (
            "id",
            "policy_id",
            "name",
            "content",
        ),
    }.get(field, ("id", "name", "description"))


def patch_target_prompt_limit(agent: ChapterAgent) -> int:
    return {
        "overview": 3000,
        "terms": 2200,
        "terms_refinement": 2600,
        "actors": 2200,
        "usecases": 3800,
        "usecase_diagram": 2400,
        "state": 4200,
        "process": 4200,
        "process_detail": 4600,
        "functions": 4400,
        "function_detail": 5000,
        "policies": 5600,
        "final_check": 2600,
    }.get(agent.chapter_key, 3600)


def chapter_patch_schema(agent: ChapterAgent) -> dict:
    properties = {}
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        properties[schema_key] = field_schema(schema_key)
    return object_schema(properties)


def merge_patch_payload(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    patch_payload: Mapping[str, object],
    *,
    patch_target: Mapping[str, object] | None = None,
) -> dict:
    merged = copy.deepcopy(dict(current_payload))
    allowed_fields = set(patch_target.keys()) if isinstance(patch_target, Mapping) else set()
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        if allowed_fields and schema_key not in allowed_fields:
            continue
        patch_values = patch_payload.get(schema_key, [])
        current_values = merged.get(schema_key, [])
        if isinstance(current_values, Mapping) and isinstance(patch_values, Mapping) and patch_values:
            merged[schema_key] = {**copy.deepcopy(dict(current_values)), **copy.deepcopy(dict(patch_values))}
            continue
        if not isinstance(patch_values, list) or not patch_values:
            continue
        if schema_key == "state_transitions":
            merged[schema_key] = merge_state_transition_patch(current_values, patch_values)
            continue
        id_key = ID_FIELD_BY_LIST.get(schema_key)
        if id_key:
            merged[schema_key] = merge_id_list_patch(current_values, patch_values, id_key)
        else:
            merged[schema_key] = copy.deepcopy(patch_values)
    return merged


def ensure_patch_payload_within_target(
    agent: ChapterAgent,
    patch_payload: Mapping[str, object],
    patch_target: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> None:
    """Reject patch responses that drift into full-chapter rewrites.

    The patch schema still exposes all chapter fields so the model can return
    empty arrays for untouched fields. Non-empty fields and item identities must
    stay inside the selected patch target unless the finding explicitly asks for
    missing/new rows.
    """
    if not isinstance(patch_payload, Mapping):
        raise LLMError("패치 응답이 JSON 객체가 아닙니다.")
    allowed_fields = {str(key) for key, value in patch_target.items() if value}
    unexpected_fields: List[str] = []
    out_of_scope_items: List[str] = []
    oversized_additions: List[str] = []
    for field in agent.output_fields:
        schema_key = "usecase_diagram" if field == "meta.usecase_diagram" else field
        patch_values = patch_payload.get(schema_key)
        if patch_values in (None, "", [], {}):
            continue
        if schema_key not in allowed_fields:
            unexpected_fields.append(schema_key)
            continue
        target_values = patch_target.get(schema_key)
        if isinstance(target_values, Mapping):
            continue
        if not isinstance(patch_values, list) or not isinstance(target_values, list):
            continue
        allowed_identities = patch_target_identities(schema_key, target_values)
        patch_identities = [identity for identity in (patch_payload_identity(schema_key, item) for item in patch_values) if identity]
        additions = [identity for identity in patch_identities if identity not in allowed_identities]
        if not additions:
            continue
        if not patch_feedback_allows_addition(feedback, schema_key):
            out_of_scope_items.extend(f"{schema_key}:{identity}" for identity in additions[:8])
            continue
        limit = patch_add_item_limit(agent, schema_key)
        if len(additions) > limit:
            oversized_additions.append(f"{schema_key}:{len(additions)}>{limit}")
    if unexpected_fields or out_of_scope_items or oversized_additions:
        details = []
        if unexpected_fields:
            details.append("대상 밖 필드=" + ", ".join(sorted(set(unexpected_fields))[:8]))
        if out_of_scope_items:
            details.append("대상 밖 항목=" + ", ".join(out_of_scope_items[:8]))
        if oversized_additions:
            details.append("추가 과다=" + ", ".join(oversized_additions[:8]))
        raise LLMError(
            "Patch Mode에서는 Inspector가 지정한 대상만 수정해야 합니다. "
            "패치 대상 밖 항목을 반환하지 말고, 필요한 경우 finding이 지정한 누락 항목만 소량 추가하세요. "
            + " / ".join(details)
        )


def patch_target_identities(schema_key: str, values: Sequence[object]) -> set[str]:
    return {
        identity
        for identity in (patch_payload_identity(schema_key, item) for item in values)
        if identity
    }


def patch_payload_identity(schema_key: str, item: object) -> str:
    if not isinstance(item, Mapping):
        return ""
    if schema_key == "state_transitions":
        return state_transition_identity(item)
    id_key = ID_FIELD_BY_LIST.get(schema_key)
    if id_key:
        return str(item.get(id_key, "")).strip()
    return patch_item_identity(item)


def patch_feedback_allows_addition(feedback: Sequence[Mapping[str, object]], schema_key: str) -> bool:
    field_keywords = {
        "state_transitions": ("전이", "transition", "도달", "분기"),
        "policy_details": ("정책 상세", "정책 항목", "판단값", "허용", "제한", "policy detail"),
        "policy_groups": ("정책 그룹", "정책 목록", "policy group"),
        "processes": ("프로세스", "process"),
        "functions": ("기능", "function"),
        "terms": ("용어", "term"),
        "actors": ("액터", "actor"),
        "usecases": ("유즈케이스", "usecase", "use case"),
    }.get(schema_key, ())
    for item in feedback or []:
        if not isinstance(item, Mapping):
            continue
        text = feedback_item_text(item)
        text_lower = text.casefold()
        if not any(keyword.casefold() in text_lower for keyword in PATCH_ADDITION_KEYWORDS):
            continue
        if field_keywords and not any(keyword.casefold() in text_lower for keyword in field_keywords):
            continue
        return True
    return False


def patch_add_item_limit(agent: ChapterAgent, schema_key: str) -> int:
    limits = {
        "state_transitions": 6,
        "policy_details": 6,
        "policy_groups": 3,
        "processes": 4,
        "functions": 4,
        "function_details": 4,
        "process_details": 4,
        "terms": 4,
        "actors": 2,
        "usecases": 3,
    }
    if agent.chapter_key in {"overview", "final_check"}:
        return 4
    return limits.get(schema_key, 3)


def ensure_patch_feedback_targets_changed(
    agent: ChapterAgent,
    current_payload: Mapping[str, object],
    merged_payload: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]],
) -> None:
    allowed_fields = {"usecase_diagram" if field == "meta.usecase_diagram" else field for field in agent.output_fields}
    unchanged: List[str] = []
    for index, item in enumerate(feedback or [], start=1):
        if not isinstance(item, Mapping):
            continue
        refs = feedback_target_field_refs(item, allowed_fields)
        if not refs:
            continue
        changed = False
        for ref in refs:
            field = str(ref.get("field", ""))
            prop = str(ref.get("property", ""))
            idx = int(ref.get("index", -1))
            before = payload_row_value_at(current_payload, field, idx, prop)
            after = payload_row_value_at(merged_payload, field, idx, prop)
            if before != after:
                changed = True
                break
        if not changed and feedback_allows_related_field_change(agent, item):
            changed = any(
                payload_field_changed(current_payload, merged_payload, field)
                for field in feedback_target_schema_keys(agent, feedback_item_text(item))
                if field in allowed_fields
            )
        if not changed:
            unchanged.append(str(item.get("issue_id") or item.get("title") or f"feedback-{index}"))
    if unchanged:
        raise LLMError(
            "Inspector가 지정한 패치 대상 필드가 변경되지 않았습니다. "
            "target_path의 current_value를 실제로 바꾸어 동일 finding이 반복되지 않게 하세요: "
            + ", ".join(unchanged[:8])
        )


def feedback_target_field_refs(item: Mapping[str, object], allowed_fields: set[str]) -> List[dict]:
    """Collect exact patch refs from all Inspector guidance, not only target_path.

    Inspectors often describe a coupled fix such as "state description 또는
    transition criteria 중 하나를 맞춘다". A patch is valid when it changes one
    of those explicitly mentioned fields, even if target_path names only the
    representative field.
    """
    refs: List[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for key in (
        "target_path",
        "detail",
        "required_change",
        "patch_hint",
        "recommendation",
        "acceptance_check",
    ):
        for ref in target_field_refs_from_path(str(item.get(key, ""))):
            field = str(ref.get("field", ""))
            prop = str(ref.get("property", ""))
            if field not in allowed_fields or not prop:
                continue
            marker = (field, int(ref.get("index", -1)), prop)
            if marker in seen:
                continue
            seen.add(marker)
            refs.append(ref)
    return refs


def feedback_allows_related_field_change(agent: ChapterAgent, item: Mapping[str, object]) -> bool:
    if agent.chapter_key != "state":
        return False
    text = feedback_item_text(item)
    has_alternative = any(keyword in text for keyword in ("또는", "중 하나", "추가 전이", "outbound", "전이 목록", "state_transitions"))
    has_transition_scope = "state_transitions" in feedback_target_schema_keys(agent, text) or "전이" in text
    return has_alternative and has_transition_scope


def payload_field_changed(
    current_payload: Mapping[str, object],
    merged_payload: Mapping[str, object],
    field: str,
) -> bool:
    before = canonical_json_value(current_payload.get(field))
    after = canonical_json_value(merged_payload.get(field))
    return before != after


def canonical_json_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def payload_row_at(payload: Mapping[str, object], field: str, index: int) -> Mapping[str, object]:
    values = payload.get(field, [])
    if not isinstance(values, list) or index < 0 or index >= len(values):
        return {}
    row = values[index]
    return row if isinstance(row, Mapping) else {}


def payload_row_value_at(payload: Mapping[str, object], field: str, index: int, prop: str) -> str:
    row = payload_row_at(payload, field, index)
    if not row:
        return ""
    return clean_policy_text(row.get(prop, ""))


def state_transition_identity(item: Mapping[str, object]) -> str:
    key = state_transition_key(item)
    return " -> ".join(value for value in key if value)


def merge_id_list_patch(current_values: object, patch_values: Sequence[object], id_key: str) -> List[dict]:
    current = [copy.deepcopy(item) for item in current_values if isinstance(item, dict)] if isinstance(current_values, list) else []
    by_id = {str(item.get(id_key, "")).strip(): index for index, item in enumerate(current) if str(item.get(id_key, "")).strip()}
    for patch_item in patch_values:
        if not isinstance(patch_item, dict):
            continue
        item_id = str(patch_item.get(id_key, "")).strip()
        if item_id and item_id in by_id:
            updated = copy.deepcopy(current[by_id[item_id]])
            updated.update(copy.deepcopy(patch_item))
            current[by_id[item_id]] = updated
        elif item_id:
            current.append(copy.deepcopy(patch_item))
    return current


def merge_state_transition_patch(current_values: object, patch_values: Sequence[object]) -> List[dict]:
    current = [copy.deepcopy(item) for item in current_values if isinstance(item, dict)] if isinstance(current_values, list) else []
    by_key = {state_transition_key(item): index for index, item in enumerate(current)}
    for patch_item in patch_values:
        if not isinstance(patch_item, dict):
            continue
        key = state_transition_key(patch_item)
        if key in by_key:
            updated = copy.deepcopy(current[by_key[key]])
            updated.update(copy.deepcopy(patch_item))
            current[by_key[key]] = updated
        else:
            current.append(copy.deepcopy(patch_item))
    return current


def state_transition_key(item: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(item.get("current_state", "")).strip(),
        str(item.get("event", "")).strip(),
        str(item.get("next_state", "")).strip(),
    )


def patch_target_summary(patch_target: Mapping[str, object]) -> dict:
    return {
        key: len(value)
        for key, value in patch_target.items()
        if isinstance(value, list)
    }


def should_chunk_chapter(agent: ChapterAgent, local_payload: Mapping[str, object]) -> bool:
    if agent.chapter_key not in CHUNKED_LLM_CHAPTERS:
        return False
    chunks = chunk_payload_for_agent(agent, local_payload)
    return len(chunks) > 1


def chunk_payload_for_agent(agent: ChapterAgent, local_payload: Mapping[str, object]) -> List[dict]:
    if agent.chapter_key not in CHUNKED_LLM_CHAPTERS:
        return [dict(local_payload)]
    if not should_split_by_estimated_workload(agent, local_payload):
        return [dict(local_payload)]
    if agent.chapter_key == "process":
        chunks = chunk_items_by_group(local_payload.get("processes", []), ("usecase_id",), chunk_workload_limit(agent))
        return [{"processes": chunk} for chunk in chunks] or [dict(local_payload)]
    if agent.chapter_key == "process_detail":
        chunks = chunk_items_by_group(local_payload.get("process_details", []), ("usecase_id", "process_id"), chunk_workload_limit(agent))
        return [{"process_details": chunk} for chunk in chunks] or [dict(local_payload)]
    if agent.chapter_key == "functions":
        chunks = chunk_items_by_group(local_payload.get("functions", []), ("process_id", "process_ids"), chunk_workload_limit(agent))
        return [{"functions": chunk} for chunk in chunks] or [dict(local_payload)]
    if agent.chapter_key == "function_detail":
        chunks = chunk_items_by_group(local_payload.get("function_details", []), ("function_id", "process_id"), chunk_workload_limit(agent))
        return [{"function_details": chunk} for chunk in chunks] or [dict(local_payload)]
    if agent.chapter_key == "policies":
        groups = [item for item in local_payload.get("policy_groups", []) if isinstance(item, dict)]
        details = [item for item in local_payload.get("policy_details", []) if isinstance(item, dict)]
        chunks: List[dict] = []
        for group_chunk in chunk_policy_groups(groups, details, chunk_workload_limit(agent)):
            group_ids = {str(group.get("id", "")).strip() for group in group_chunk if str(group.get("id", "")).strip()}
            detail_chunk = [
                detail
                for detail in details
                if str(detail.get("policy_id", "")).strip() in group_ids
            ]
            chunks.append({"policy_groups": group_chunk, "policy_details": detail_chunk})
        return chunks or [dict(local_payload)]
    return [dict(local_payload)]


def split_list(items: object, size: int) -> List[list]:
    if not isinstance(items, list):
        return []
    return [copy.deepcopy(items[index : index + size]) for index in range(0, len(items), size)]


def chunk_size(agent: ChapterAgent) -> int:
    sizes = {
        "process": 12,
        "process_detail": 8,
        "functions": 8,
        "function_detail": 8,
        "policies": 8,
    }
    return sizes.get(agent.chapter_key, 10)


def should_split_by_estimated_workload(agent: ChapterAgent, local_payload: Mapping[str, object]) -> bool:
    return estimated_chunk_workload(agent, local_payload) > chunk_workload_limit(agent)


def chunk_workload_limit(agent: ChapterAgent) -> float:
    limits = {
        "process": 18.0,
        "process_detail": 16.0,
        "functions": 18.0,
        "function_detail": 18.0,
        "policies": 24.0,
    }
    return limits.get(agent.chapter_key, 18.0)


def estimated_chunk_workload(agent: ChapterAgent, payload: Mapping[str, object]) -> float:
    if agent.chapter_key == "process":
        return sum(item_workload(item) for item in safe_dict_items(payload.get("processes", [])))
    if agent.chapter_key == "process_detail":
        return sum(item_workload(item) * 1.2 for item in safe_dict_items(payload.get("process_details", [])))
    if agent.chapter_key == "functions":
        return sum(item_workload(item) + list_workload(item.get("details")) * 0.35 for item in safe_dict_items(payload.get("functions", [])))
    if agent.chapter_key == "function_detail":
        return sum(item_workload(item) * 1.3 for item in safe_dict_items(payload.get("function_details", [])))
    if agent.chapter_key == "policies":
        groups = safe_dict_items(payload.get("policy_groups", []))
        details = safe_dict_items(payload.get("policy_details", []))
        return sum(item_workload(item) for item in groups) + sum(item_workload(item) * 1.4 for item in details)
    return item_workload(payload)


def safe_dict_items(value: object) -> List[dict]:
    if not isinstance(value, list):
        return []
    return [copy.deepcopy(item) for item in value if isinstance(item, dict)]


def list_workload(value: object) -> float:
    if not isinstance(value, list):
        return 0.0
    return float(len(value))


def item_workload(item: Mapping[str, object]) -> float:
    serialized = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
    list_bonus = sum(len(value) for value in item.values() if isinstance(value, list)) * 0.25
    return max(1.0, len(serialized) / 180.0) + list_bonus


def chunk_items_by_group(items: object, key_candidates: Sequence[str], limit: float) -> List[List[dict]]:
    groups = grouped_items(items, key_candidates)
    return pack_weighted_groups(groups, limit)


def grouped_items(items: object, key_candidates: Sequence[str]) -> List[List[dict]]:
    if not isinstance(items, list):
        return []
    groups: List[List[dict]] = []
    index_by_key: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = group_key_for_item(item, key_candidates)
        if not key:
            key = str(item.get("id") or item.get("process_id") or item.get("function_id") or len(groups))
        if key not in index_by_key:
            index_by_key[key] = len(groups)
            groups.append([])
        groups[index_by_key[key]].append(copy.deepcopy(item))
    return groups


def group_key_for_item(item: Mapping[str, object], key_candidates: Sequence[str]) -> str:
    for key in key_candidates:
        value = item.get(key)
        if isinstance(value, list):
            for entry in value:
                text = str(entry).strip()
                if text:
                    return text
        else:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def pack_weighted_groups(groups: Sequence[Sequence[Mapping[str, object]]], limit: float) -> List[List[dict]]:
    chunks: List[List[dict]] = []
    current: List[dict] = []
    current_weight = 0.0
    for group in groups:
        group_items = [copy.deepcopy(dict(item)) for item in group if isinstance(item, dict)]
        if not group_items:
            continue
        group_weight = sum(item_workload(item) for item in group_items)
        if group_weight > limit and len(group_items) > 1:
            if current:
                chunks.append(current)
                current = []
                current_weight = 0.0
            chunks.extend(split_oversized_items(group_items, limit))
            continue
        if current and current_weight + group_weight > limit:
            chunks.append(current)
            current = []
            current_weight = 0.0
        current.extend(group_items)
        current_weight += group_weight
    if current:
        chunks.append(current)
    return chunks


def split_oversized_items(items: Sequence[Mapping[str, object]], limit: float) -> List[List[dict]]:
    chunks: List[List[dict]] = []
    current: List[dict] = []
    current_weight = 0.0
    for item in items:
        item_dict = copy.deepcopy(dict(item))
        weight = item_workload(item_dict)
        if current and current_weight + weight > limit:
            chunks.append(current)
            current = []
            current_weight = 0.0
        current.append(item_dict)
        current_weight += weight
    if current:
        chunks.append(current)
    return chunks


def chunk_policy_groups(groups: Sequence[Mapping[str, object]], details: Sequence[Mapping[str, object]], limit: float) -> List[List[dict]]:
    details_by_policy: dict[str, List[Mapping[str, object]]] = {}
    for detail in details:
        policy_id = str(detail.get("policy_id", "")).strip()
        details_by_policy.setdefault(policy_id, []).append(detail)
    grouped = [[copy.deepcopy(dict(group))] for group in groups if isinstance(group, Mapping)]
    chunks: List[List[dict]] = []
    current: List[dict] = []
    current_weight = 0.0
    for group_items in grouped:
        group = group_items[0]
        policy_id = str(group.get("id", "")).strip()
        group_weight = item_workload(group) + sum(item_workload(detail) * 1.4 for detail in details_by_policy.get(policy_id, []))
        if current and current_weight + group_weight > limit:
            chunks.append(current)
            current = []
            current_weight = 0.0
        current.append(copy.deepcopy(group))
        current_weight += group_weight
    if current:
        chunks.append(current)
    return chunks


def build_chunked_chapter_prompt(
    agent: ChapterAgent,
    current_spec: dict,
    chunk_payload: Mapping[str, object],
    runtime: AgentRuntime,
    feedback: Sequence[Mapping[str, object]] | None,
    *,
    chunk_index: int,
    total_chunks: int,
) -> str:
    base_prompt = build_chapter_prompt(agent, current_spec, dict(chunk_payload), runtime, feedback, chunk_mode=True)
    constraints = [
        f"분할 작성 모드: 현재 {chunk_index}/{total_chunks} 구간만 작성한다.",
        "반환 JSON에는 로컬 초안 JSON에 포함된 ID만 포함한다.",
        "로컬 초안 JSON의 모든 ID는 누락 없이 반환한다.",
        "담당 구간 밖의 항목을 새로 만들거나 다른 구간 항목을 반복하지 않는다.",
        "현재 구간 안에서도 선행 장의 actor, usecase_id, 기능 process_id, 정책 상세 policy_id, policy name 연결은 유지한다.",
    ]
    if agent.chapter_key == "process":
        constraints.append("각 프로세스는 해당 usecase_id를 유지하고, related_functions와 related_policies는 빈 배열로 둔다. 기능/정책 연결은 후속 장 작성 후 자동 보정한다.")
        constraints.append("같은 usecase_id 안의 프로세스는 상위 유즈케이스를 완료하는 순차 절차로 서로 다른 역할을 가져야 하며, 한 유즈케이스를 1개 프로세스로 축약하지 않는다.")
    if agent.chapter_key == "functions":
        constraints.append("각 기능은 로컬 초안의 process_id를 유지하고, 프로세스 수행에 필요한 조회·검증·산정·저장·알림·연동 역량만 간결히 작성한다.")
        constraints.append("process_ids에는 이 기능을 사용하는 모든 프로세스 ID를 넣고, 대표 process_id도 process_ids에 포함한다.")
        constraints.append("복합 프로세스에는 기능을 2개 이상 연결하고, 공통 조회·인증·동의·이력·알림 기능은 여러 process_ids에 재사용한다.")
        constraints.append("모든 프로세스가 기능 1개씩만 갖는 1:1 구조는 샘플 수준에 맞지 않으므로 금지한다.")
        constraints.append("details는 샘플의 세부 기능 구성 칸처럼 짧은 하위 처리명만 쓴다. 예: '조회 조건 구성', '권한 상태 검증', '결과 안내 구성'.")
        constraints.append("details에는 마침표가 있는 문장, '~한다' 설명문, 정책값·예외 기준 문장을 쓰지 않는다.")
    if agent.chapter_key == "process_detail":
        constraints.append("각 프로세스 상세는 로컬 초안의 process_id를 유지하고, 현재 구간의 프로세스 상세만 작성한다.")
        constraints.append("프로세스 상세에서 기능 상세나 정책값을 새로 만들지 말고, 진입·종료·선행·후행·참조 연결만 보강한다.")
        constraints.append("관련 기능과 관련 정책은 이미 작성된 ID·명칭을 그대로 사용하고 새 기능·정책을 만들지 않는다.")
        constraints.append("진입 조건은 시작 가능한 고객/시스템 상태나 선행 처리 결과, 종료 조건은 확정된 결과 상태 또는 후속 연결 기준으로 쓴다.")
        constraints.append("모든 프로세스에 같은 진입·종료 문장을 반복하지 말고 현재 프로세스의 판단 지점에 맞게 다르게 쓴다.")
    if agent.chapter_key == "function_detail":
        constraints.append("각 기능 상세는 로컬 초안의 function_id를 유지하고, 현재 구간의 기능 상세만 작성한다.")
        constraints.append("기능 상세는 기능 아래의 세부 처리 책임만 확장하고, 유즈케이스·프로세스 순서나 정책값을 새로 정의하지 않는다.")
        constraints.append("입력/처리/출력/실패·예외는 기능별로 다르게 작성하되 API 필드나 DB 컬럼은 쓰지 않는다.")
        constraints.append("처리 로직은 '(상태) ... → (액션) ... → (결과) ...' 형태로 정상, 분기, 예외 중 필요한 흐름을 작성한다.")
        constraints.append("정책값은 기능 상세에 풀어쓰지 말고 관련 정책 ID·명칭으로만 연결한다.")
    if agent.chapter_key == "policies":
        constraints.append("policy_groups는 로컬 초안의 정책 ID를 유지하고, policy_details는 해당 policy_id에 연결된 판단 기준만 작성하며 process_id는 작성하지 않는다.")
        constraints.append("policy_details는 샘플처럼 id, policy_id, name, content만 작성한다. 발동 조건, 판단 기준, 기준값, 고객 고지, 감사 로그 같은 고정 슬롯을 별도 필드로 만들지 않는다.")
        constraints.append("정책 작성은 프로세스/기능별 필요 정책 도출 → 세부 정책 항목 도출 → 항목별 값 정의 순서로 수행한다.")
        constraints.append("정책 상세 name/content는 인증 수단, 가능 횟수, 유효시간, 제한 기간, 채널, 저장 항목처럼 기능 동작에 필요한 실제 값 또는 조건 중심으로 작성한다.")
    return base_prompt + "\n\n" + "분할 작성 제약:\n" + "\n".join(f"- {item}" for item in constraints)


def filter_chunk_result(agent: ChapterAgent, local_payload: Mapping[str, object], result: Mapping[str, object]) -> dict:
    if agent.chapter_key == "process":
        local_items = [item for item in local_payload.get("processes", []) if isinstance(item, dict)]
        return {"processes": complete_filtered_items(local_items, result.get("processes", []), "id")}
    if agent.chapter_key == "functions":
        local_items = [item for item in local_payload.get("functions", []) if isinstance(item, dict)]
        return {"functions": complete_filtered_items(local_items, result.get("functions", []), "id")}
    if agent.chapter_key == "process_detail":
        local_items = [item for item in local_payload.get("process_details", []) if isinstance(item, dict)]
        return {"process_details": complete_filtered_items(local_items, result.get("process_details", []), "process_id")}
    if agent.chapter_key == "function_detail":
        local_items = [item for item in local_payload.get("function_details", []) if isinstance(item, dict)]
        return {"function_details": complete_filtered_items(local_items, result.get("function_details", []), "function_id")}
    if agent.chapter_key == "policies":
        local_groups = [item for item in local_payload.get("policy_groups", []) if isinstance(item, dict)]
        local_details = [item for item in local_payload.get("policy_details", []) if isinstance(item, dict)]
        return {
            "policy_groups": complete_filtered_items(local_groups, result.get("policy_groups", []), "id"),
            "policy_details": complete_filtered_items(local_details, result.get("policy_details", []), "id"),
        }
    return dict(result)


def complete_filtered_items(local_items: Sequence[Mapping[str, object]], result_items: object, id_key: str) -> List[dict]:
    allowed_ids = {str(item.get(id_key, "")).strip() for item in local_items if str(item.get(id_key, "")).strip()}
    by_id: dict[str, dict] = {}
    if isinstance(result_items, list):
        for item in result_items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get(id_key, "")).strip()
            if item_id in allowed_ids:
                by_id[item_id] = copy.deepcopy(item)
    completed: List[dict] = []
    for local_item in local_items:
        item_id = str(local_item.get(id_key, "")).strip()
        if item_id in by_id:
            merged = copy.deepcopy(dict(local_item))
            merged.update(by_id[item_id])
            completed.append(merged)
        else:
            completed.append(copy.deepcopy(dict(local_item)))
    return completed


def merge_chunk_results(agent: ChapterAgent, chunks: Sequence[Mapping[str, object]]) -> dict:
    if agent.chapter_key == "process":
        return {"processes": merge_list_field(chunks, "processes")}
    if agent.chapter_key == "functions":
        return {"functions": merge_list_field(chunks, "functions")}
    if agent.chapter_key == "process_detail":
        return {"process_details": merge_list_field(chunks, "process_details")}
    if agent.chapter_key == "function_detail":
        return {"function_details": merge_list_field(chunks, "function_details")}
    if agent.chapter_key == "policies":
        return {
            "policy_groups": merge_list_field(chunks, "policy_groups"),
            "policy_details": merge_list_field(chunks, "policy_details"),
        }
    return {}


def merge_list_field(chunks: Sequence[Mapping[str, object]], field: str) -> List[dict]:
    merged: List[dict] = []
    for chunk in chunks:
        values = chunk.get(field, [])
        if not isinstance(values, list):
            continue
        merged.extend(copy.deepcopy([item for item in values if isinstance(item, dict)]))
    return merged


def record_payload_generation_meta(spec: dict, agent: ChapterAgent, payload: Mapping[str, object], attempt: int) -> None:
    chunking = payload.get("__llm_chunking")
    if isinstance(chunking, dict):
        spec.setdefault("meta", {}).setdefault("llm_chunking_runs", []).append(
            {
                "chapter": agent.chapter_key,
                "attempt": attempt,
                **chunking,
            }
        )
    patch_revision = payload.get("__llm_patch_revision")
    if isinstance(patch_revision, dict):
        spec.setdefault("meta", {}).setdefault("llm_patch_revision_runs", []).append(
            {
                "chapter": agent.chapter_key,
                "attempt": attempt,
                **patch_revision,
            }
        )


def record_llm_retry_meta(spec: dict, agent: ChapterAgent, attempt: int, retry_events: Sequence[Mapping[str, object]]) -> None:
    if not retry_events:
        return
    spec.setdefault("meta", {}).setdefault("llm_retry_runs", []).append(
        {
            "chapter": agent.chapter_key,
            "agent": agent.display_name,
            "orchestrator_attempt": attempt,
            "retries": list(retry_events),
        }
    )


def llm_task_max_attempts() -> int:
    value = os.getenv("OPENAI_LLM_TASK_MAX_ATTEMPTS", "").strip()
    try:
        return max(1, int(value)) if value else DEFAULT_LLM_TASK_MAX_ATTEMPTS
    except ValueError:
        return DEFAULT_LLM_TASK_MAX_ATTEMPTS


def patch_llm_task_max_attempts() -> int:
    value = os.getenv("OPENAI_LLM_PATCH_MAX_ATTEMPTS", "").strip()
    try:
        return max(1, int(value)) if value else DEFAULT_LLM_PATCH_TASK_MAX_ATTEMPTS
    except ValueError:
        return DEFAULT_LLM_PATCH_TASK_MAX_ATTEMPTS


def chapter_llm_task_max_attempts(
    agent: ChapterAgent,
    spec: Mapping[str, object],
    feedback: Sequence[Mapping[str, object]] | None,
) -> int:
    """Keep expensive patch retries bounded; API-level retries are handled by the LLM client."""
    max_attempts = llm_task_max_attempts()
    if should_use_patch_revision(agent, spec, feedback):
        return min(max_attempts, patch_llm_task_max_attempts())
    return max_attempts


def llm_retry_delay_seconds(attempt: int) -> float:
    value = os.getenv("OPENAI_LLM_TASK_RETRY_BASE_SECONDS", "").strip()
    try:
        base = max(0.0, float(value)) if value else DEFAULT_LLM_TASK_RETRY_BASE_SECONDS
    except ValueError:
        base = DEFAULT_LLM_TASK_RETRY_BASE_SECONDS
    return min(30.0, base * (2 ** max(0, attempt - 1)))


def should_retry_llm_task_error(exc: Exception) -> bool:
    if not isinstance(exc, LLMError):
        return False
    message = str(exc).casefold()
    fatal_markers = (
        "401",
        "403",
        "invalid_api_key",
        "incorrect api key",
        "api key",
        "model_not_found",
        "does not exist",
        "unsupported value",
        "not supported",
        "permission",
        "billing",
        "quota",
    )
    return not any(marker in message for marker in fatal_markers)


def llm_retry_feedback(exc: Exception, attempt: int, *, chunk: int | None = None) -> Mapping[str, str]:
    target = f"chunk {chunk}" if chunk is not None else "chapter"
    message = str(exc)
    if "상태 코드 목록이 비어" in message or "상태 전이표가 비어" in message:
        recommendation = (
            "상태 장 전용 seed를 유지하되 현재 주제에 맞게 재작성하고, states와 state_transitions를 절대 빈 배열로 반환하지 마세요. "
            "모든 state_transitions에는 상태 변경을 발생시키는 액터 유즈케이스 ID를 usecase_ids로 채우세요."
        )
    elif "상태 전이 이벤트" in message or "유즈케이스명" in message:
        recommendation = (
            "state_transitions.event에는 usecase_ids로 연결한 유즈케이스 흐름에서 상태를 바꾸는 업무 사건을 쓰세요. "
            "예: 회원 가입 완료, 유예 기간 만료, 상태 조회 실패. 세부 판정 조건과 후속 처리는 criteria에 옮겨 쓰세요."
        )
    elif "max_output_tokens" in message or "incomplete" in message:
        recommendation = "출력 한도에 걸리지 않도록 항목을 짧게 쓰고, 설명을 한 문장으로 제한하며 기존 ID의 필수 필드만 반환하세요."
    elif "JSON" in message or "json" in message:
        recommendation = "반드시 JSON schema에 맞는 JSON 객체만 반환하고, 마크다운·HTML·설명 문장을 JSON 밖에 쓰지 마세요."
    else:
        recommendation = "이전 실패 원인을 반영해 같은 ID와 연결성을 유지한 채 더 간결하고 검증 가능한 JSON으로 다시 작성하세요."
    return {
        "severity": "retry",
        "category": "LLM 자동 재시도",
        "title": f"{target} LLM 재시도 {attempt}",
        "detail": message[:500],
        "recommendation": recommendation,
    }


def chapter_prompt_budget(agent: ChapterAgent, has_feedback: bool = False) -> dict:
    """Keep the useful context, but stop sending every summary twice."""
    budgets = {
        "overview": dict(learning=1400, blueprint=3200, summary=900, alignment=1200, context=2200, context_items=6, payload=7000, feedback=2600),
        "terms": dict(learning=1300, blueprint=3400, summary=1000, alignment=1400, context=2300, context_items=6, payload=9000, feedback=2600),
        "actors": dict(learning=1300, blueprint=3200, summary=1000, alignment=1400, context=2200, context_items=6, payload=7000, feedback=2600),
        "usecases": dict(learning=1800, blueprint=4400, summary=2200, alignment=3000, context=3000, context_items=8, payload=18000, feedback=3600),
        "usecase_diagram": dict(learning=900, blueprint=2400, summary=1400, alignment=2600, context=1600, context_items=5, payload=4000, feedback=2200),
        "state": dict(learning=1800, blueprint=4500, summary=2400, alignment=3200, context=3100, context_items=8, payload=20000, feedback=3600),
        "process": dict(learning=1700, blueprint=4600, summary=1500, alignment=2400, context=2500, context_items=7, payload=20000, feedback=3600),
        "process_detail": dict(learning=1400, blueprint=3800, summary=1600, alignment=2600, context=2300, context_items=6, payload=24000, feedback=3600),
        "functions": dict(learning=1600, blueprint=4300, summary=1500, alignment=2400, context=2400, context_items=7, payload=20000, feedback=3600),
        "function_detail": dict(learning=1400, blueprint=3800, summary=1600, alignment=2600, context=2300, context_items=6, payload=26000, feedback=3600),
        "policies": dict(learning=1800, blueprint=4800, summary=1600, alignment=2600, context=2600, context_items=7, payload=24000, feedback=4000),
        "terms_refinement": dict(learning=1400, blueprint=3600, summary=1800, alignment=2600, context=2200, context_items=6, payload=12000, feedback=3200),
        "final_check": dict(learning=1200, blueprint=3200, summary=1800, alignment=2400, context=1800, context_items=5, payload=5000, feedback=2800),
    }
    budget = dict(budgets.get(agent.chapter_key, budgets["usecases"]))
    if has_feedback:
        budget["blueprint"] = min(budget["blueprint"], 2600)
        budget["learning"] = min(budget["learning"], 1000)
        budget["summary"] = min(budget["summary"], 1400)
        budget["alignment"] = min(budget["alignment"], 2400)
        budget["context"] = min(budget["context"], 1800)
        budget["context_items"] = min(budget["context_items"], 4)
    return budget


def chunk_prompt_budget(agent: ChapterAgent, budget: Mapping[str, int]) -> dict:
    """Reduce repeated context for chunked LLM calls while preserving local IDs."""
    compact = dict(budget)
    compact["learning"] = min(int(compact.get("learning", 0)), 700)
    compact["blueprint"] = min(int(compact.get("blueprint", 0)), 2200 if agent.chapter_key == "policies" else 1800)
    compact["summary"] = min(int(compact.get("summary", 0)), 900)
    compact["alignment"] = min(int(compact.get("alignment", 0)), 1400)
    compact["context"] = min(int(compact.get("context", 0)), 900)
    compact["context_items"] = min(int(compact.get("context_items", 0)), 3)
    compact["payload"] = min(int(compact.get("payload", 0)), 12000)
    compact["feedback"] = min(int(compact.get("feedback", 0)), 1800)
    return compact


def compact_payload_for_prompt(agent: ChapterAgent, payload: Mapping[str, object]) -> Mapping[str, object]:
    key = agent.chapter_key
    if key == "process":
        return {
            "processes": compact_dicts(
                payload.get("processes", []),
                ("id", "usecase_id", "name", "description"),
                70,
                120,
            )
        }
    if key == "functions":
        return {
            "functions": compact_dicts(
                payload.get("functions", []),
                ("id", "process_id", "name"),
                70,
                140,
            )
        }
    if key == "process_detail":
        return {
            "process_details": compact_dicts(
                payload.get("process_details", []),
                ("process_id", "entry_condition", "exit_condition", "previous_processes", "next_processes", "related_functions", "related_policies"),
                80,
                140,
            )
        }
    if key == "function_detail":
        return {
            "function_details": compact_dicts(
                payload.get("function_details", []),
                ("function_id", "input_information", "processing_logic", "sub_functions", "output_information", "failure_exception_cases", "related_policies"),
                80,
                160,
            )
        }
    if key == "policies":
        return {
            "policy_groups": compact_dicts(
                payload.get("policy_groups", []),
                ("id", "name", "description"),
                80,
                80,
            ),
            "policy_details": compact_dicts(
                payload.get("policy_details", []),
                ("id", "policy_id", "name", "content"),
                80,
                160,
            ),
        }
    return payload


def chapter_concision_rules(agent: ChapterAgent) -> List[str]:
    common = [
        "샘플 간소화본처럼 짧은 명사형 항목과 한 문장 설명을 우선한다.",
        "한 설명에는 하나의 책임, 판단 조건, 처리 결과만 담는다.",
        "후속 장에서 상세화할 내용은 현재 장에 길게 선반영하지 않는다.",
        "정책 판단 기준은 긴 문단이 아니라 검증 가능한 행 또는 정책 항목으로 분리한다.",
        "복합 주제는 각 의미 축을 항목으로 분리하되 같은 의미를 표현만 바꿔 반복하지 않는다.",
        "요구사항이나 근거에서 직접 나오지 않은 배경 설명, 시장 일반론, 시스템 일반론은 쓰지 않는다.",
        "이미 이전 장에서 정의한 내용은 다시 풀어쓰지 말고 기존 ID와 명칭으로 참조한다.",
    ]
    if agent.chapter_key == "overview":
        return common + [
            "scope는 대상 업무, 대상 채널, 대상 고객, 포함 범위, 제외 범위, 후속 상세화 영역만 다룬다.",
            "범위 문장은 고객 과업과 포함/제외 판단만 남기고 배경 설명은 쓰지 않는다.",
            "설계 원칙은 후속 기능·정책 판단에 실제로 연결되는 기준만 남긴다.",
        ]
    if agent.chapter_key == "actors":
        return common + [
            "액터 설명은 '무엇을 책임지는 주체'인지 한 문장으로만 작성한다.",
            "하위 역할, 권한 매트릭스, 금지 행위, 감사 기준은 정책 장으로 넘긴다.",
            "고객 상태나 자격 차이는 액터 설명에 나열하지 말고 상태·정책 조건으로 넘긴다.",
        ]
    if agent.chapter_key in {"terms", "terms_refinement"}:
        return common + [
            "용어 설명은 업무상 판단 기준만 한 문장으로 작성한다.",
            "예시와 상세 예외는 정책 상세로 넘긴다.",
            "본문에서 판단 기준으로 쓰이지 않는 일반 명사는 추가하지 않는다.",
        ]
    if agent.chapter_key == "usecases":
        return common + [
            "유즈케이스 설명은 시작 목적과 완료 상태만 작성한다.",
            "유즈케이스는 뒤에서 여러 프로세스로 분해될 수 있는 상위 업무 목표여야 한다.",
            "예외와 세부 단계는 프로세스 장으로 넘긴다.",
            "인증, 선택, 확인 같은 절차 단계는 독립 유즈케이스로 만들지 않는다.",
            "조회, 검증, 산정, 저장, 알림, 연동 같은 처리 역량은 기능 장으로 넘긴다.",
            "프로세스 정의 대상은 고객만이 아니라 사람 액터 전체를 기준으로 판단한다.",
            "뒤에서 특정 Y 유즈케이스에 프로세스가 8개 이상 필요해 보이면 유즈케이스가 너무 넓은 것이므로 고객·운영자 목표 기준으로 미리 나눈다.",
        ]
    if agent.chapter_key == "usecase_diagram":
        return common + [
            "UML 2.0 Use Case Diagram 기준으로 액터는 시스템 경계 밖에, 유즈케이스는 시스템 경계 안에 둔다.",
            "액터와 유즈케이스 관계는 association으로만 연결하고 UI 단계는 넣지 않는다.",
            "화면 이동, 버튼, 팝업, 내부 처리 단계는 넣지 않는다.",
        ]
    if agent.chapter_key == "state":
        return common + [
            "상태 정의는 업무 가능 여부 또는 후속 처리 변화만 설명한다.",
            "상태는 액터와 유즈케이스 관계에서 도출하고, 전이 이벤트는 상태를 실제로 바꾸는 업무 사건으로 쓴다.",
            "전이 기준은 관련 유즈케이스, 현재 상태, 이벤트, 다음 상태, 처리 기준을 한 행으로 끝낸다.",
            "상태 변경은 유즈케이스 흐름에서 발생시키며, state_transitions.usecase_ids는 실제 상태 변화가 있는 액터 유즈케이스 ID를 연결한다.",
            "프로세스 단계명, 기능명, 세부 기능 구성명은 상태명이나 전이 이벤트로 쓰지 않는다.",
            "단순 화면 상태나 안내 상태는 쓰지 않고 업무 상태만 남긴다.",
            "후속 처리와 고객 가능 여부가 같으면 예외 사유를 별도 상태로 늘리지 말고 criteria 또는 정책 항목으로 내린다.",
            "전이표는 대표 경로만 쓴다. 모든 인증 실패, 외부 회신, 고객 취소 조합을 행으로 복제하지 않는다.",
            "상태 설명의 원인 범위와 전이 기준의 원인 범위를 다르게 쓰지 않는다.",
            "여러 예외 전이가 같은 현재 상태에서 출발하면 우선순위 또는 배타 조건을 한 문장 안에 남긴다.",
        ]
    if agent.chapter_key == "process":
        return common + [
            "프로세스 설명은 고객/운영자가 무엇을 처리하는지 한 문장으로 작성한다.",
            "프로세스는 유즈케이스를 완료하는 업무 절차이고, 기능처럼 조회·검증·저장 같은 처리 역량만 나열하지 않는다.",
            "상위 유즈케이스를 포괄 프로세스 1개로 축약하지 말고, 실제 판단·처리·결과 경계가 다르면 세부 절차로 분해한다.",
            "반대로 한 Y 유즈케이스에 프로세스가 8개 이상 몰리면 유즈케이스가 너무 넓은지 확인하고, 고객·운영자 목표가 실제로 달라지는 지점은 유즈케이스로 분리한다.",
            "입력, 확인, 인증·동의, 검증, 처리, 결과 안내는 분해 후보이지 고정 슬롯이 아니다. 개수 맞추기를 위해 유사 프로세스를 늘리지 않는다.",
            "관련 기능과 관련 정책은 후속 장에서 실제 산출물 기준으로 연결하므로 프로세스 단계에서는 예측해 쓰지 않는다.",
            "상세 예외와 조건값은 설명 칸에 길게 쓰지 말고 판단 지점만 남긴다.",
            "내부 시스템 처리 세부는 기능으로 넘기고 프로세스에는 업무 흐름의 전환점만 남긴다.",
        ]
    if agent.chapter_key == "functions":
        return common + [
            "기능 설명은 무엇을 처리해 어떤 결과를 만드는지 한 문장으로 작성한다.",
            "기능은 프로세스의 하위 처리 역량이고, 세부 기능 구성은 기능을 구현 검토 가능한 더 작은 처리명으로 나눈 것이다.",
            "단순 프로세스는 기능 1개도 가능하지만, 문서 전체가 프로세스 1개당 기능 1개로만 구성되면 안 된다.",
            "조회, 검증, 저장, 알림, 이력, 외부 연동처럼 여러 프로세스에서 반복되는 기능은 동일 기능 ID를 여러 process_ids에 연결해 재사용한다.",
            "세부 기능 구성은 조회, 검증, 산정, 저장, 알림, 연동 같은 짧은 처리명으로 쓴다.",
            "세부 기능 구성은 '통합 검색창 제공', '입력값 정규화'처럼 명사형 하위 처리 단위로 쓰고, '...한다.' 형태의 설명문으로 쓰지 않는다.",
            "정책값과 예외 기준은 기능 설명에 길게 쓰지 말고 정책 상세로 넘긴다.",
        ]
    if agent.chapter_key == "process_detail":
        return common + [
            "프로세스 상세는 각 프로세스의 진입 조건과 종료 조건을 한 문장씩만 작성한다.",
            "프로세스 상세는 이미 확정된 프로세스의 조건과 연결을 보강하고, 기능 상세나 정책값을 새로 만들지 않는다.",
            "선행·후행 프로세스는 실제 프로세스 ID와 프로세스명 중심으로 연결한다.",
            "관련 기능과 관련 정책은 이미 확정된 기능·정책 ID와 명칭만 짧게 참조한다.",
            "단순히 프로세스명을 반복하는 일반 조건 문장을 쓰지 않는다.",
        ]
    if agent.chapter_key == "function_detail":
        return common + [
            "기능 상세는 입력, 처리, 출력, 실패·예외를 구현 책임 기준으로 나누되 각 항목은 짧게 쓴다.",
            "기능 상세의 세부 기능 구성은 기능 아래 처리명이며, 프로세스 단계명이나 정책 항목명으로 쓰지 않는다.",
            "처리 로직 각 줄은 반드시 '(상태) ... → (액션) ... → (결과) ...' 형식으로 작성한다.",
            "'(정상)', '(분기)', '(예외)'만 붙인 설명문은 처리 로직으로 인정하지 않는다.",
            "API 필드, DB 컬럼, 화면 문구는 쓰지 않는다.",
            "정책값은 기능 상세에 풀어쓰지 말고 관련 정책 ID와 정책명으로 연결한다.",
        ]
    if agent.chapter_key == "policies":
        return common + [
            "정책 그룹은 프로세스와 기능이 실제로 필요로 하는 통제 지점을 기준으로 정의한다.",
            "정책은 기능 수행에 필요한 판단값·허용값·제한값을 선언하고, 유즈케이스·프로세스·기능 계층을 다시 작성하지 않는다.",
            "각 정책 그룹은 먼저 세부 항목 후보를 나누고, policy_details에서 항목별 값을 선언한다.",
            "정책 그룹 설명은 판단 영역만 설명하고 세부 기준값은 policy_details로 쪼갠다.",
            "policy_details는 policy_id로만 정책 그룹에 연결하고 process_id는 작성하지 않는다.",
            "정책 상세 한 항목에는 하나의 기능 동작값, 허용 목록, 횟수, 시간, 제한 조건, 예외, 고지, 저장 기준 중 하나만 담는다.",
            "정책 상세는 샘플처럼 정책 항목명과 정책 내용으로 선언하고, 발동 조건·판단 기준·기준값 같은 고정 라벨을 반복하지 않는다.",
            "정책 상세 content에는 실제 값 또는 적용 조건만 쓰고 배경 설명, 추상 원칙, 구현 방식은 쓰지 않는다.",
        ]
    if agent.chapter_key == "final_check":
        return common + [
            "최종 점검은 항목명 중심의 체크리스트로 작성한다.",
            "유즈케이스 → 프로세스 → 기능 → 세부 기능 구성 → 정책값 계층의 입자도와 연결성을 점검 항목으로 둔다.",
            "HTML, 버전 spec, BPMN, 요구사항 Trace가 같은 버전·같은 ID 체계를 가리키는지 산출물 동기화 점검 항목을 둔다.",
            "점검 문장은 확인 기준과 통과 조건만 남긴다.",
        ]
    return common


def inspector_failure_prevention_rules(agent: ChapterAgent) -> List[str]:
    """Generalized rules learned from recent inspector feedback loops."""
    common = [
        "주제명만 바꾸는 공통 문장으로 쓰지 말고, 현재 주제의 고유 판단축이 최소 하나 이상 드러나게 한다.",
        "ID는 ID 필드와 표의 ID 컬럼에서 관리하고, 제목·설명 문장에는 업무명만 쓴다.",
        "이전 장에서 정한 표준 명칭을 바꾸지 않는다. 같은 개념은 용어, 상태, 유즈케이스, 프로세스에서 같은 이름을 쓴다.",
        "운영자 화면 상세는 제외하되, 셀프 처리 기준 관리·예외 판단·감사 책임은 필요한 경우 내부 책임으로만 좁혀 쓴다.",
        "자동 Inspector/Health Check 점수가 좋아도 직접 Inspector 관점으로 범위, 계위, 연결, 정책 구체성을 다시 확인한다.",
    ]
    key = agent.chapter_key
    if key == "overview":
        return common + [
            "인접 업무를 포함하는 표현은 '직후 연계', '결과 안내', '후속 연결'처럼 범위를 좁히고 제외 범위에 일반 업무를 분리한다.",
        ]
    if key in {"terms", "terms_refinement"}:
        return common + [
            "용어는 개념 정의까지만 쓰고 우선순위, 재사용 가능 여부, 노출 순서 같은 정책 규칙은 후속 정책 장으로 보낸다.",
            "제한, 불가, 실패, 완료, 보류처럼 상태가 될 수 있는 용어는 상태명과 충돌하지 않게 표준명을 먼저 고른다.",
            "약어는 독자가 초반에 이해할 수 있도록 풀어 쓰거나 주요 용어에 포함한다.",
        ]
    if key == "actors":
        return common + [
            "채널 업무 시스템은 흐름 제어와 결과 반영 주체이고, BSS는 최종 업무 판정 주체이며, 인증기관은 인증 결과 제공 주체로 분리한다.",
            "외부 연계 시스템에는 BSS·인증기관의 판정 책임을 넣지 말고 보조 조회·알림·동의·콜백 책임만 남긴다.",
        ]
    if key == "usecases":
        return common + [
            "사람 액터 유즈케이스는 process_target=Y, 시스템/기관 액터 유즈케이스는 process_target=N으로 둔다.",
            "시스템 액터 유즈케이스는 보조 처리로 두고 process_target=N을 사용한다.",
            "고객·운영자 등 사람이 보는 완료 목적은 사람 액터 유즈케이스에, 세션 복원·상태 저장·연계 결과 수신은 보조 유즈케이스 설명에만 둔다.",
            "사람 액터 유즈케이스가 판정 결과를 다루면 판정 주체와 안내 주체를 짧게 구분한다.",
            "유즈케이스가 프로세스나 기능 수준으로 잘게 쪼개지면 후속 장 전체가 1:1 구조가 되므로 상위 업무 목표로 묶는다.",
        ]
    if key == "usecase_diagram":
        return common + [
            "보조 유즈케이스는 독립 업무처럼 보이지 않게 주 유즈케이스와 include/지원 관계 또는 관계 설명으로 연결한다.",
            "채널 내부 공통 통제는 시스템 경계 내부 공통 처리로 표현하고 외부 액터처럼 보이지 않게 한다.",
        ]
    if key == "state":
        return common + [
            "상태 정의의 원인 범위와 상태 전이의 원인 범위를 일치시킨다.",
            "전이 이벤트는 연결된 유즈케이스 흐름의 상태 변화 업무 사건이어야 하며, 기능명이나 내부 처리 단계명은 criteria로 내려 쓴다.",
            "고객 취소, 인증 만료, 연계 실패, 처리 보류, 운영 확인은 서로 다른 후속 처리가 필요하면 구분 기준을 남긴다.",
            "운영 확인 상태를 쓰면 처리 주체가 유즈케이스나 후속 프로세스에 있는지 확인한다.",
            "이전 유즈케이스에 없는 임시저장·재개·운영 확정 같은 새 업무를 상태 장에서 만들지 않는다.",
            "운영자는 기준 보정·예외 접수 책임만 갖고, 고객별 BSS 판정 결과 확정 책임을 상태 전이에 부여하지 않는다.",
            "process_target=N인 시스템/BSS/외부 연계 유즈케이스라도 고객 노출 상태, 가입·사용 가능 여부, 제한 사유, 오류·복구 경로, BSS 반영 결과를 바꾸면 state_transitions.usecase_ids에 포함한다.",
            "description, next_action, event, criteria에는 US-, TM-, ACT-, ST- 같은 내부 ID를 쓰지 않는다.",
        ]
    if key == "process":
        return common + [
            "프로세스 제목에는 유즈케이스 ID를 붙이지 않는다.",
            "프로세스는 기능명을 길게 바꾼 항목이 아니라 유즈케이스 완료를 향한 업무 전환점이어야 한다.",
            "프로세스 설명 끝은 가능한 한 상태 장의 실제 상태명 또는 상태 분기 기준으로 닫는다.",
            "고객 경험 프로세스와 채널/BSS/인증기관 내부 통제 프로세스의 책임을 같은 문장에 섞지 않는다.",
            "정의된 기능과 정책이 프로세스에서 미참조로 남지 않게 related_functions와 related_policies를 순수 ID로 연결한다.",
            "기능 process_ids와 프로세스 related_functions가 양방향으로 맞는지 직접 점검한다.",
        ]
    if key == "functions":
        return common + [
            "같은 세부 기능 묶음을 여러 기능에 복사하지 말고 기능별 산출 결과를 다르게 정의한다.",
            "판정, 안내, 세션 통제, 외부 연계 호출은 서로 다른 책임이면 별도 기능으로 나눈다.",
            "상세 요구사항의 처리 경로, 계산 기준, 외부 회신, 복구 가능성이 서로 다르면 같은 기능 안에서도 세부 기능 구성으로 분리해 추적 가능하게 남긴다.",
            "기능 제목에는 프로세스 ID를 붙이지 않고 기능 ID는 기능 목록의 ID 컬럼에서 관리한다.",
            "AI/분석/보조 판단 기능도 실제 프로세스의 related_functions에 연결하고, 기능의 process_ids에서 역참조한다.",
            "정책을 실행하는 기능이면 function.related_policies에도 정책 ID를 남겨 프로세스 related_policies와 추적 가능하게 한다.",
        ]
    if key == "process_detail":
        return common + [
            "진입 조건과 종료 조건이 모두 같은 문장으로 반복되면 안 된다.",
            "관련 기능·정책은 기능 목록과 정책 목록의 ID·명칭을 그대로 사용한다.",
            "선행/후행 관계는 같은 유즈케이스 흐름 안의 실제 프로세스 순서를 우선한다.",
        ]
    if key == "function_detail":
        return common + [
            "입력/출력/예외 항목을 모든 기능에 같은 문구로 복사하지 않는다.",
            "처리 로직은 기능명 반복이 아니라 조회, 검증, 산정, 저장, 회신 중 실제 처리 책임을 드러낸다.",
            "sub_functions는 기능의 하위 처리 구성이고, 프로세스 순서나 정책 항목을 대신 쓰지 않는다.",
            "관련 정책은 프로세스의 관련 정책 또는 정책 목록의 ID·명칭과 맞춰 쓴다.",
        ]
    if key == "policies":
        return common + [
            "정책 그룹 요약에는 정책 목적과 판단 기준만 쓰고 요구사항명이나 적용 대상 나열을 섞지 않는다.",
            "정책은 프로세스나 기능 설명을 반복하지 않고 기능 동작을 통제하는 값·조건·허용 범위를 선언한다.",
            "정책 상세는 하나의 판단 기준만 담고, 같은 이름의 '적용 기준/예외 기준/이력 기준' 템플릿을 반복하지 않는다.",
            "여러 상세 요구사항이 같은 상위 정책으로 묶이더라도 고객 경로, 처리 시점, 계산 기준, 외부 회신, 복구 가능성이 달라지면 별도 정책 항목으로 분리한다.",
            "예상 금액, 위약금, 결합 영향처럼 QA 계산 케이스가 달라지는 항목은 하나의 영향도 고지 정책으로 뭉개지 않는다.",
            "정책 상세가 추상 설명으로 흐르면 안 된다. 인증 수단, 가능 횟수, 유효시간, 제한 기간, 채널, 저장 항목, 실패 처리처럼 실제 기능 동작값으로 바꾼다.",
            "범위·경계, 빈 화면·오류 폴백, 필터·정렬 같은 공통 정책도 전달 맥락, 고객 후속 행동, 적용 채널, 기준 버전, 이력 저장 중 필요한 판단축을 포함한다.",
        ]
    return common


def alignment_context_for_prompt(agent: ChapterAgent, spec: dict, runtime: AgentRuntime) -> dict:
    """Pass compact predecessor outputs so chapter agents do not lose alignment."""
    return approved_contract_for_prompt(agent, spec, runtime)


SLIM_APPROVED_CONTRACT_STAGES = {
    "process",
    "process_detail",
    "functions",
    "function_detail",
    "policies",
    "terms_refinement",
    "final_check",
}


def contract_actor_rows(spec: Mapping[str, object], max_rows: int) -> List[dict]:
    rows: List[dict] = []
    actors = spec.get("actors", []) if isinstance(spec.get("actors", []), list) else []
    for actor in actors[:max_rows]:
        if not isinstance(actor, Mapping):
            continue
        name = str(actor.get("name", "")).strip()
        actor_type = "사람" if is_human_actor_name(name) else "시스템" if is_system_actor_name(name) else "기타"
        row = {
            "id": limit_text_for_policy(actor.get("id", ""), 36),
            "name": limit_text_for_policy(name, 42),
            "type": actor_type,
        }
        responsibility = limit_text_for_policy(actor.get("description", ""), 58)
        if responsibility:
            row["responsibility"] = responsibility
        rows.append(row)
    return rows


def contract_usecase_rows(spec: Mapping[str, object], max_rows: int, *, include_goal: bool = True) -> List[dict]:
    rows: List[dict] = []
    usecases = spec.get("usecases", []) if isinstance(spec.get("usecases", []), list) else []
    for usecase in usecases[:max_rows]:
        if not isinstance(usecase, Mapping):
            continue
        row = {
            "id": limit_text_for_policy(usecase.get("id", ""), 40),
            "actor": limit_text_for_policy(usecase.get("actor", ""), 36),
            "name": limit_text_for_policy(usecase.get("name", ""), 52),
            "process_target": limit_text_for_policy(usecase.get("process_target", ""), 4),
        }
        goal = limit_text_for_policy(usecase.get("description", ""), 62)
        if include_goal and goal:
            row["goal"] = goal
        rows.append(row)
    return rows


def contract_state_rows(spec: Mapping[str, object], max_rows: int, *, include_next: bool = True) -> List[dict]:
    rows: List[dict] = []
    states = spec.get("states", []) if isinstance(spec.get("states", []), list) else []
    for state in states[:max_rows]:
        if not isinstance(state, Mapping):
            continue
        row = {
            "id": limit_text_for_policy(state.get("id", ""), 36),
            "name": limit_text_for_policy(state.get("name", ""), 42),
        }
        meaning = limit_text_for_policy(state.get("description", ""), 58)
        if meaning:
            row["meaning"] = meaning
        next_action = limit_text_for_policy(state.get("next_action", ""), 58)
        if include_next and next_action:
            row["next"] = next_action
        rows.append(row)
    return rows


def contract_process_rows(
    spec: Mapping[str, object],
    max_rows: int,
    *,
    include_intent: bool = True,
    include_links: bool = False,
) -> List[dict]:
    rows: List[dict] = []
    processes = spec.get("processes", []) if isinstance(spec.get("processes", []), list) else []
    for process in processes[:max_rows]:
        if not isinstance(process, Mapping):
            continue
        row = {
            "id": limit_text_for_policy(process.get("id", ""), 38),
            "usecase_id": limit_text_for_policy(process.get("usecase_id", ""), 38),
            "name": limit_text_for_policy(process.get("name", ""), 54),
        }
        intent = limit_text_for_policy(process.get("description", ""), 62)
        if include_intent and intent:
            row["intent"] = intent
        if include_links:
            row["related_functions"] = compact_strings(process.get("related_functions", []), 52, 4)
            row["related_policies"] = compact_strings(process.get("related_policies", []), 52, 4)
        rows.append(row)
    return rows


def contract_function_rows(spec: Mapping[str, object], max_rows: int, *, include_result: bool = False) -> List[dict]:
    rows: List[dict] = []
    functions = spec.get("functions", []) if isinstance(spec.get("functions", []), list) else []
    for function in functions[:max_rows]:
        if not isinstance(function, Mapping):
            continue
        linked_process_ids = function_linked_process_ids(function)
        row = {
            "id": limit_text_for_policy(function.get("id", ""), 38),
            "process_id": limit_text_for_policy(function.get("process_id", ""), 38),
            "process_ids": compact_strings(linked_process_ids, 38, 6),
            "name": limit_text_for_policy(function.get("name", ""), 54),
        }
        result = limit_text_for_policy(function.get("description", ""), 62)
        if include_result and result:
            row["result"] = result
        rows.append(row)
    return rows


def approved_contract_for_prompt(agent: ChapterAgent, spec: dict, runtime: AgentRuntime) -> dict:
    """Approved predecessor contract: compact, stage-specific, and stable."""
    key = agent.chapter_key
    slim = key in SLIM_APPROVED_CONTRACT_STAGES
    topic_axes = topic_axes_for_prompt(runtime.ctx.topic)
    context: dict = {
        "rule": "이전 장은 통과된 기준선이다. 현재 챕터는 아래 contract의 ID/명칭/책임/상태를 바꾸지 말고 이어받는다.",
        "topic_axes": topic_axes,
    }
    density_profile = density_profile_for_runtime(runtime)
    density_contract = density_prompt_contract(density_profile)
    if density_contract:
        context["density_contract"] = density_contract
    open_issues = open_inspector_issues_for_prompt(spec)
    if open_issues:
        context["open_inspector_issues"] = open_issues
        context["open_issue_rule"] = (
            "이전 장에서 최대 보완 후 남은 Inspector 이슈다. 현재 챕터에서 직접 해결할 수 있는 연결성, 명칭, 책임 경계, "
            "프로세스-기능-정책 누락은 반드시 보정하고, 직접 수정할 수 없는 내용은 새 모순을 만들지 않도록 같은 명칭을 유지한다."
        )
    if len(topic_axes) >= 2:
        context["topic_axis_rule"] = "정책서 주제가 여러 의미 축으로 나뉘므로 담당 챕터에서 각 축을 빠뜨리지 말고, 축별 고객 행위·시스템 판정·예외 기준을 필요한 수준으로 분리한다."
    if key in {"terms", "actors", "usecases", "usecase_diagram", "state", "process", "process_detail", "functions", "function_detail", "policies", "terms_refinement", "final_check"}:
        context["overview_contract"] = overview_contract(spec)
    if key in {"actors", "usecases", "usecase_diagram", "state"}:
        context["term_contract"] = compact_dicts(spec.get("terms", []), ("id", "name"), 60, 24)
    elif key in SLIM_APPROVED_CONTRACT_STAGES:
        term_limit = 24 if key in {"terms_refinement", "final_check"} else 12
        context["term_index"] = compact_dicts(spec.get("terms", []), ("id", "name"), 46, term_limit)
    if key in {"usecases", "usecase_diagram", "state", "process", "process_detail", "functions", "function_detail", "policies", "terms_refinement", "final_check"}:
        context["actor_contract"] = contract_actor_rows(spec, 12 if slim else 16)
        context["actor_rule"] = "유즈케이스 actor 값은 actor_contract의 name과 정확히 일치한다."
    if key in {"usecase_diagram", "state", "process", "process_detail", "functions", "function_detail", "policies", "terms_refinement", "final_check"}:
        usecase_limits = {
            "process": 46,
            "process_detail": 50,
            "functions": 42,
            "function_detail": 42,
            "policies": 36,
            "terms_refinement": 48,
            "final_check": 54,
        }
        context["usecase_contract"] = contract_usecase_rows(
            spec,
            usecase_limits.get(key, 70),
            include_goal=key in SLIM_APPROVED_CONTRACT_STAGES,
        )
    if key in {"process", "process_detail", "functions", "function_detail", "policies", "terms_refinement", "final_check"}:
        context["state_contract"] = contract_state_rows(spec, 26 if slim else 32, include_next=True)
    if key == "state":
        context["state_basis"] = {
            "usecases": compact_dicts(spec.get("usecases", []), ("id", "actor", "name", "process_target"), 70, 50),
            "term_names": [item.get("name", "") for item in compact_dicts(spec.get("terms", []), ("name",), 50, 24)],
            "design_pattern": state_transition_design_pattern(),
        }
    if key == "process":
        context["process_basis"] = {
            "y_usecases": process_target_usecases(spec),
            "state_names": [item.get("name", "") for item in compact_dicts(spec.get("states", []), ("name",), 50, 32)],
            "rule": "사람 액터 Y 유즈케이스는 실제 판단·처리·결과·예외 경계가 드러나야 한다. 1개 프로세스로만 끝나면 정상 통과가 아니라 유즈케이스 입자도 또는 프로세스 분해를 재점검한다. 반대로 8개 이상 프로세스가 한 Y 유즈케이스에 몰리면 유즈케이스가 너무 넓은지 확인하고 고객·운영자 목표가 달라지는 지점은 유즈케이스로 분리한다. density_target은 개수 강제가 아니라 분해가 필요한 경계 힌트다. 결과 표현은 state_names 중 하나 또는 명확한 상태 분기 기준으로 닫는다.",
            "sample_ratio": "좋은 샘플 정책서는 상위 업무 유즈케이스를 단일 포괄 프로세스로 축소하지 않지만, 개수 맞추기를 위해 유사 프로세스를 늘리지도 않는다.",
        }
        if density_contract:
            context["process_basis"]["density_target"] = density_contract.get("recommended_processes_per_y_usecase", "")
    if key in {"process_detail", "functions", "function_detail", "policies", "terms_refinement", "final_check"}:
        process_limits = {
            "process_detail": 72,
            "functions": 64,
            "function_detail": 64,
            "policies": 58,
            "terms_refinement": 64,
            "final_check": 72,
        }
        context["process_contract"] = contract_process_rows(
            spec,
            process_limits.get(key, 72),
            include_intent=True,
            include_links=key in {"process_detail", "function_detail", "terms_refinement", "final_check"},
        )
    if key in {"process_detail", "function_detail", "policies", "terms_refinement", "final_check"}:
        function_limits = {
            "process_detail": 70,
            "function_detail": 72,
            "policies": 68,
            "terms_refinement": 72,
            "final_check": 82,
        }
        context["function_contract"] = contract_function_rows(
            spec,
            function_limits.get(key, 72),
            include_result=key in {"policies", "function_detail", "terms_refinement", "final_check"},
        )
    if key in {"process", "process_detail", "function_detail", "policies", "terms_refinement", "final_check"}:
        policy_source = spec.get("policy_groups", []) or runtime.target_spec.get("policy_groups", [])
        context["policy_name_candidates"] = compact_dicts(policy_source, ("id", "name"), 70, 40)
    if key == "policies":
        context["policy_derivation_rule"] = (
            "정책은 프로세스와 기능의 필요 통제 지점에서 도출한다. "
            "순서: 1) 프로세스/기능별 필요 정책 그룹 정의, 2) 정책 그룹별 세부 정책 항목 정의, 3) 항목별 값·조건·횟수·시간·채널·저장 항목 정의."
        )
        context["process_function_policy_needs"] = policy_derivation_matrix_for_prompt(spec)
    if key in {"process_detail", "function_detail", "terms_refinement", "final_check"}:
        context["process_detail_contract"] = compact_dicts(
            spec.get("process_details", []),
            ("process_id", "entry_condition", "exit_condition", "related_functions", "related_policies"),
            65,
            60 if slim else 90,
        )
    if key in {"function_detail", "terms_refinement", "final_check"}:
        context["function_detail_contract"] = compact_dicts(
            spec.get("function_details", []),
            ("function_id", "processing_logic", "output_information", "related_policies"),
            65,
            60 if slim else 90,
        )
    if key in {"terms_refinement", "final_check"}:
        context["policy_contract"] = {
            "groups": compact_dicts(spec.get("policy_groups", []), ("id", "name"), 58, 70),
            "details": compact_dicts(spec.get("policy_details", []), ("id", "policy_id", "name"), 58, 90),
        }
    if key == "terms_refinement":
        context["refinement_rule"] = "기능·정책 장에서 실제로 사용된 판단 용어가 terms에 없으면 추가하고, 일반 명사나 정책 상세 수준의 예외 설명은 추가하지 않는다."
    return context


def overview_contract(spec: Mapping[str, object]) -> dict:
    overview = spec.get("overview", {}) if isinstance(spec.get("overview"), Mapping) else {}
    return {
        "scope": compact_strings(overview.get("scope", []), 95, 6),
        "principles": compact_dicts(overview.get("principles", []), ("name",), 45, 6),
    }


def process_target_usecases(spec: Mapping[str, object]) -> List[dict]:
    rows = []
    for item in spec.get("usecases", []) if isinstance(spec.get("usecases"), list) else []:
        if not isinstance(item, dict):
            continue
        if str(item.get("process_target", "")).strip().upper() != "Y":
            continue
        rows.append(
            {
                "id": limit_text_for_policy(item.get("id", ""), 40),
                "actor": limit_text_for_policy(item.get("actor", ""), 40),
                "name": limit_text_for_policy(item.get("name", ""), 70),
            }
        )
    return rows[:70]


def topic_axes_for_prompt(topic: str) -> List[dict]:
    raw = str(topic or "").strip()
    if not raw:
        return []
    parts = [part.strip() for part in re.split(r"\s*(?:/|·|,|，|\+|&|\b및\b|\band\b)\s*", raw) if part.strip()]
    if len(parts) <= 1:
        parts = [raw]
    axes: List[dict] = []
    seen = set()
    for part in parts:
        tokens = [token for token in re.split(r"[\s()\[\]{}<>:;|]+", part) if token]
        compact = re.sub(r"\s+", "", part).casefold()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        axes.append(
            {
                "label": re.sub(r"\s+", " ", part).strip(),
                "required_terms": tokens,
            }
        )
    return axes


def compact_dicts(items: object, keys: Sequence[str], cell_limit: int, limit: int) -> List[dict]:
    result: List[dict] = []
    if not isinstance(items, list):
        return result
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        row = {}
        for key in keys:
            value = item.get(key, "")
            if isinstance(value, list):
                row[key] = compact_strings(value, cell_limit, 8)
            else:
                row[key] = limit_text_for_policy(value, cell_limit)
        result.append(row)
    return result


def compact_dict(item: object, keys: Sequence[str], cell_limit: int, limit: int) -> dict:
    if not isinstance(item, Mapping):
        return {}
    row = {}
    for key in keys[:limit]:
        value = item.get(key, "")
        if isinstance(value, list):
            row[key] = compact_strings(value, cell_limit, 12)
        elif isinstance(value, Mapping):
            row[key] = compact_dict(value, tuple(value.keys()), cell_limit, 12)
        else:
            row[key] = limit_text_for_policy(value, cell_limit)
    return row


def compact_strings(items: object, cell_limit: int, limit: int) -> List[str]:
    if not isinstance(items, list):
        return []
    return [limit_text_for_policy(item, cell_limit) for item in items[:limit] if clean_policy_text(item)]


def chapter_payload_limit(agent: ChapterAgent) -> int:
    limits = {
        "overview": 12000,
        "terms": 16000,
        "actors": 12000,
        "usecases": 24000,
        "usecase_diagram": 10000,
        "state": 28000,
        "process": 36000,
        "process_detail": 36000,
        "functions": 36000,
        "function_detail": 40000,
        "policies": 52000,
        "terms_refinement": 22000,
        "final_check": 12000,
    }
    return limits.get(agent.chapter_key, 24000)


def summarize_spec_for_prompt(spec: dict) -> dict:
    return {
        "meta": {
            "topic": spec.get("meta", {}).get("topic", ""),
            "business_code": spec.get("meta", {}).get("business_code", ""),
            "template_type": spec.get("meta", {}).get("template_type", ""),
        },
        "populated_fields": populated_fields(spec),
        "counts": {
            key: len(spec.get(key, [])) if isinstance(spec.get(key), list) else 0
            for key in (
                "terms",
                "actors",
                "usecases",
                "states",
                "state_transitions",
                "processes",
                "process_details",
                "functions",
                "function_details",
                "policy_groups",
                "policy_details",
                "final_check",
            )
        },
        "actors": [item.get("name") for item in spec.get("actors", []) if isinstance(item, dict)],
        "usecases": [
            {"id": item.get("id"), "actor": item.get("actor"), "name": item.get("name")}
            for item in spec.get("usecases", [])
            if isinstance(item, dict)
        ],
        "states": [item.get("name") for item in spec.get("states", []) if isinstance(item, dict)],
        "open_inspector_issues": open_inspector_issues_for_prompt(spec),
        "process_related_policies": unique_nonempty(
            policy
            for process in spec.get("processes", [])
            if isinstance(process, dict)
            for policy in process.get("related_policies", [])
        )[:80],
    }


def open_inspector_issues_for_prompt(spec: Mapping[str, object], limit: int = 8) -> List[dict]:
    meta = spec.get("meta", {}) if isinstance(spec.get("meta"), Mapping) else {}
    issues = meta.get("open_inspector_issues", []) if isinstance(meta, Mapping) else []
    if not isinstance(issues, list):
        return []
    compact: List[dict] = []
    for issue in issues[-limit:]:
        if not isinstance(issue, Mapping):
            continue
        feedback_items = issue.get("feedback", [])
        selected_feedback = []
        if isinstance(feedback_items, list):
            for item in feedback_items[:3]:
                if not isinstance(item, Mapping):
                    continue
                selected_feedback.append(
                    {
                        "title": limit_text_for_policy(item.get("title", ""), 70),
                        "category": limit_text_for_policy(item.get("category", ""), 40),
                        "recommendation": limit_text_for_policy(item.get("recommendation", ""), 150),
                    }
                )
        compact.append(
            {
                "chapter": issue.get("chapter", ""),
                "score": issue.get("score", ""),
                "feedback": selected_feedback,
            }
        )
    return compact


def prompt_json(value: object, limit: int) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...TRUNCATED..."


def prompt_json_unlimited(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def feedback_prompt_limit(feedback: Sequence[Mapping[str, object]] | None, minimum: int) -> int:
    text = prompt_json_unlimited(list(feedback or []))
    return max(minimum, len(text))


def populated_fields(spec: dict) -> List[str]:
    fields = []
    for field in (
        "overview",
        "terms",
        "actors",
        "usecases",
        "states",
        "state_transitions",
        "processes",
        "process_details",
        "functions",
        "function_details",
        "policy_groups",
        "policy_details",
        "final_check",
    ):
        value = spec.get(field)
        if isinstance(value, dict) and any(value.values()):
            fields.append(field)
        elif isinstance(value, list) and value:
            fields.append(field)
    if spec.get("meta", {}).get("usecase_diagram"):
        fields.append("usecase_diagram")
    return fields


def learn_topic(ctx) -> dict:
    requirements = getattr(ctx, "requirements", ()) or ()
    references = getattr(ctx, "references", ()) or ()
    prelearned_knowledge = load_topic_knowledge_pack(ctx.topic)
    requirement_terms = unique_nonempty(
        [
            getattr(item, "depth3", "")
            for item in requirements
        ]
        + [
            getattr(item, "depth4", "")
            for item in requirements
        ]
        + [
            getattr(item, "detail_name", "")
            for item in requirements[:20]
        ]
    )
    reference_categories = sorted({getattr(item, "category", "general") for item in references})
    reference_signals = unique_nonempty(
        signal
        for item in references
        for signal in (getattr(item, "signals", ()) or ())
    )
    return {
        "topic": ctx.topic,
        "business_code": ctx.business_code,
        "requirements_count": len(requirements),
        "references_count": len(references),
        "reference_sources": [getattr(item, "source_name", "") for item in references],
        "reference_read_scope": "full_document",
        "reference_total_text_chars": sum(int(getattr(item, "text_chars", 0) or 0) for item in references),
        "requirement_terms": requirement_terms[:20],
        "reference_categories": reference_categories,
        "reference_signals": reference_signals[:40],
        "prelearned_knowledge": compact_topic_knowledge_for_prompt(prelearned_knowledge, max_chars=7000),
        "learning_summary": build_learning_summary(ctx.topic, requirements, references),
    }


def enhance_learning_with_llm(ctx, base_learning: dict, guideline: dict, llm_client: LLMClient) -> dict:
    llm_client = client_for_topic_learning(llm_client)
    learning = copy.deepcopy(base_learning)
    learning["llm_learning"] = {
        "used": False,
        "model": llm_client.model,
        "reasoning_effort": llm_client.reasoning_effort,
    }
    if not llm_client.enabled:
        if llm_client.forced:
            raise LLMError("LLM 학습 단계에는 OPENAI_API_KEY가 필요합니다.")
        learning["llm_learning"]["reason"] = "LLM 비활성화 모드입니다."
        return learning

    cached_payload = load_topic_learning_cache(ctx, guideline, llm_client)
    if cached_payload:
        learning["llm_learning"] = {
            "used": True,
            "cache_hit": True,
            "model": llm_client.model,
            "reasoning_effort": llm_client.reasoning_effort,
            "analysis": cached_payload,
        }
        apply_topic_learning_payload(learning, cached_payload)
        return learning

    retry_feedback: List[Mapping[str, str]] = []
    for llm_attempt in range(1, llm_task_max_attempts() + 1):
        try:
            prompt = build_learning_prompt(ctx, learning, guideline)
            if retry_feedback:
                prompt = prompt + "\n\nLLM 자동 재시도 지시:\n" + prompt_json(retry_feedback, 3000)
            payload = llm_client.generate_json(
                schema_name="topic_learning",
                schema=topic_learning_schema(),
                instructions=build_learning_instructions(ctx),
                input_messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            break
        except Exception as exc:
            if not should_retry_llm_task_error(exc):
                raise
            if llm_attempt >= llm_task_max_attempts():
                learning["llm_learning"].update(
                    {
                        "used": False,
                        "fallback": True,
                        "model": llm_client.model,
                        "reasoning_effort": llm_client.reasoning_effort,
                        "reason": (
                            "Topic Learning LLM 보강이 반복 실패해 기본 근거 학습 결과로 계속 진행했습니다. "
                            f"{str(exc)[:240]}"
                        ),
                    }
                )
                return learning
            retry_feedback.append(llm_retry_feedback(exc, llm_attempt))
            time.sleep(llm_retry_delay_seconds(llm_attempt))

    save_topic_learning_cache(ctx, guideline, llm_client, payload)
    learning["llm_learning"] = {
        "used": True,
        "cache_hit": False,
        "model": llm_client.model,
        "reasoning_effort": llm_client.reasoning_effort,
        "analysis": payload,
    }
    apply_topic_learning_payload(learning, payload)
    return learning


def apply_topic_learning_payload(learning: dict, payload: Mapping[str, object]) -> None:
    learning["learning_summary"] = sanitize_business_code_text(
        payload.get("topic_understanding") or learning.get("learning_summary", ""),
        str(learning.get("business_code", "")),
        str(learning.get("topic", "")),
    )
    for key in (
        "scope_boundary",
        "customer_tasks",
        "requirement_implications",
        "reference_implications",
        "bss_implications",
        "policy_risks",
        "chapter_focus",
    ):
        learning[key] = payload.get(key, learning.get(key, [] if key != "chapter_focus" else {}))


def sanitize_business_code_text(value: object, business_code: str, topic: str) -> str:
    text = str(value or "")
    code = str(business_code or "").strip()
    topic_text = str(topic or "").strip()
    if not code or not topic_text:
        return text
    replacements = {
        f"{code}의 {topic_text}": topic_text,
        f"{code} {topic_text}": topic_text,
        f"{code}의": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s{2,}", " ", text).strip()


def load_topic_learning_cache(ctx, guideline: dict, llm_client: LLMClient) -> Optional[dict]:
    path = topic_learning_cache_path(ctx, guideline, llm_client)
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    signature = topic_learning_cache_signature(ctx, guideline, llm_client)
    cached_signature = cached.get("signature") if isinstance(cached, dict) else None
    if isinstance(cached_signature, dict) and cached_signature != signature:
        return None
    payload = cached.get("payload") if isinstance(cached, dict) else None
    if not isinstance(payload, dict) or not valid_topic_learning_payload(payload):
        return None
    return payload


def valid_topic_learning_payload(payload: Mapping[str, object]) -> bool:
    required_list_fields = (
        "customer_tasks",
        "requirement_implications",
        "reference_implications",
        "bss_implications",
        "policy_risks",
    )
    if not str(payload.get("topic_understanding", "") or "").strip():
        return False
    scope_boundary = payload.get("scope_boundary", {})
    if not isinstance(scope_boundary, Mapping):
        return False
    if not nonempty_list(scope_boundary.get("direct_scope")):
        return False
    for key in required_list_fields:
        if not nonempty_list(payload.get(key)):
            return False
    chapter_focus = payload.get("chapter_focus", {})
    return isinstance(chapter_focus, Mapping) and any(str(value).strip() for value in chapter_focus.values())


def nonempty_list(value: object) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def save_topic_learning_cache(ctx, guideline: dict, llm_client: LLMClient, payload: Mapping[str, object]) -> None:
    try:
        LEARNING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        topic_learning_cache_path(ctx, guideline, llm_client).write_text(
            json.dumps(
                {
                    "topic": getattr(ctx, "topic", ""),
                    "template_type": getattr(ctx, "template_type", ""),
                    "model": llm_client.model,
                    "reasoning_effort": llm_client.reasoning_effort,
                    "knowledge_mode": {
                        "type": "CAG",
                        "role": "반복 작성 기준으로 재사용되는 주제 학습 캐시",
                        "refresh_rule": "요구사항, 참고자료, 샘플 기준, 모델 또는 프롬프트 버전이 바뀌면 캐시 경로가 달라진다.",
                    },
                    "signature": topic_learning_cache_signature(ctx, guideline, llm_client),
                    "payload": dict(payload),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def topic_learning_cache_path(ctx, guideline: dict, llm_client: LLMClient) -> Path:
    digest = hashlib.sha256(
        json.dumps(topic_learning_cache_signature(ctx, guideline, llm_client), ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    safe_topic = re.sub(r"[^0-9A-Za-z가-힣_-]+", "", str(getattr(ctx, "topic_slug", "") or getattr(ctx, "topic", ""))) or "topic"
    return LEARNING_CACHE_DIR / f"topic_learning_{safe_topic}_{digest}.json"


def topic_learning_cache_signature(ctx, guideline: dict, llm_client: LLMClient) -> dict:
    requirements = getattr(ctx, "requirements", ()) or ()
    references = getattr(ctx, "references", ()) or ()
    prelearned_knowledge = load_topic_knowledge_pack(getattr(ctx, "topic", ""))
    return {
        "prompt_version": TOPIC_LEARNING_PROMPT_VERSION,
        "topic": getattr(ctx, "topic", ""),
        "business_code": getattr(ctx, "business_code", ""),
        "template_type": getattr(ctx, "template_type", ""),
        "model": llm_client.model,
        "reasoning_effort": llm_client.reasoning_effort,
        "requirements": [
            [
                getattr(item, "detail_id", ""),
                getattr(item, "requirement_id", ""),
                getattr(item, "depth4", ""),
                getattr(item, "detail_name", ""),
                getattr(item, "detail_description", ""),
                getattr(item, "requirement_type", ""),
                getattr(item, "required", ""),
            ]
            for item in requirements
        ],
        "references": [
            [
                getattr(item, "source_name", ""),
                getattr(item, "source_type", ""),
                getattr(item, "text_chars", 0),
                tuple(getattr(item, "signals", ()) or ())[:5],
            ]
            for item in references
        ],
        "prelearned_knowledge": {
            "version": prelearned_knowledge.get("version", ""),
            "source_fingerprint": prelearned_knowledge.get("source_fingerprint", ""),
        },
        "sample_baseline": guideline.get("sample_baseline", {}),
    }


def build_learning_instructions(ctx) -> str:
    return "\n".join(
        [
            "너는 통합채널 정책서 작성을 시작하기 전 주제를 학습하는 전문 analyst다.",
            "요구사항과 참고자료를 그대로 복사하지 말고, 고객 과업, BSS 판단, 예외, 기능 범위, 정책 기준으로 재구성한다.",
            "근거 우선순위는 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF, 2순위 SKT 공식 서비스 안내·약관·고객지원, 3순위 법령·규제기관·개인정보보호위·방통위, 4순위 경쟁사·벤치마킹·공개웹 자료다.",
            "하위 순위 근거가 상위 순위 근거와 상충하면 상위 근거를 우선하고, 상충되는 하위 근거는 학습 요약과 작성 기준에서 제거한다.",
            "2~4순위 근거는 1순위 근거에 없는 판단 후보를 보완하는 용도로만 사용하고, 첨부 문서의 범위·양식·정책 기준을 바꾸는 근거로 사용하지 않는다.",
            "사전 주제 Knowledge Pack은 후보 참고서다. 후보를 그대로 확정하지 말고, 현재 주제의 첨부 요구사항·첨부 참고자료·프로세스/기능 연결로 검증된 항목만 학습 요약에 남긴다.",
            "Knowledge Pack 후보 중 현재 주제 범위를 넓히거나 첨부 문서와 연결되지 않는 내용은 학습 결과에서 제거한다.",
            "T월드, T멤버십, T다이렉트샵, T우주 공개웹 통합 지식은 NC 채널 공통 맥락으로 사용한다.",
            "단, 공통 맥락은 현재 정책서 주제의 판단축을 선명하게 하기 위한 기준이며, 주제 밖 업무를 본문 범위로 확장하는 근거가 아니다.",
            "T월드는 회선·요금·납부·BSS 판정, T멤버십은 등급·혜택·쿠폰·바코드, T다이렉트샵은 구매·가입·배송·개통, T우주는 구독·정기결제·제휴 책임 기준으로 해석한다.",
            "전문 분석 방법론을 사용해 상태 정의, 상태 전이, 프로세스, 기능, 정책을 서로 다른 산출물로 구분한다.",
            "단, 방법론은 내부 판단 기준이다. 템플릿/샘플에 없는 장, 표, 필드, 장황한 모델링 설명을 만들지 않는다.",
            "참고자료에 인접 업무가 함께 있더라도 현재 정책서 주제의 직접 범위와 제외 범위를 먼저 고정한다.",
            "현재 주제의 고객 과업을 완료하는 데 직접 필요하지 않은 계약, 주문, 결제, 혜택, 로그인 일반론, 운영 내부 업무는 관련/제외 후보로 분리한다.",
            "scope_boundary.direct_scope에는 반드시 작성할 범위만, related_but_not_core에는 연결만 고려할 범위만, excluded_or_later에는 이번 정책서 본문으로 확장하지 않을 범위를 적는다.",
            "정책서 작성 agent들이 바로 사용할 수 있도록 챕터별 작성 초점과 누락 위험을 구체적으로 정리한다.",
            "사용자 작성 요청 메모가 있으면 학습 초점, 누락 위험, 챕터별 작성 관점에 반영한다.",
            "학습 요약은 이후 agent가 바로 쓸 판단축만 남기고, 자료 소개·배경 설명·중복 표현은 쓰지 않는다.",
            "상태는 유즈케이스 lifecycle에서, 프로세스는 유즈케이스 목표 달성 절차에서, 기능은 프로세스 수행 역량에서, 정책은 판단 기준에서 도출한다.",
            "근거가 충분한 내용과 Evidence Gap을 구분하고, 불확실한 내용을 확정 정책처럼 길게 추정하지 않는다.",
            f"정책서 주제는 {ctx.topic}이다.",
            f"업무코드 {ctx.business_code}는 ID 생성 전용이다. 본문과 학습 요약에서는 업무명처럼 사용하지 않는다.",
            "반드시 요청된 JSON 스키마에 맞는 JSON만 작성한다.",
        ]
    )


def is_recoverable_llm_generation_error(exc: Exception) -> bool:
    """Allow generation to continue when the model attempted work but hit output limits."""
    message = str(exc)
    recoverable_markers = (
        "max_output_tokens",
        '"status": "incomplete"',
        "response_status",
        "incomplete_details",
        "OpenAI API 오류 408",
        "OpenAI API 오류 409",
        "OpenAI API 오류 425",
        "OpenAI API 오류 429",
        "OpenAI API 오류 500",
        "OpenAI API 오류 502",
        "OpenAI API 오류 503",
        "OpenAI API 오류 504",
        "error code: 502",
        "error code: 503",
        "error code: 504",
        "rate_limit",
        "OpenAI API 연결 실패",
        "OpenAI API 응답 대기 시간이 초과",
        "LLM 응답이 유효한 JSON이 아닙니다",
        "OpenAI API 응답에 JSON 텍스트가 없습니다",
    )
    return any(marker in message for marker in recoverable_markers)


def build_learning_prompt(ctx, base_learning: dict, guideline: dict) -> str:
    topic_axes = topic_axes_for_prompt(getattr(ctx, "topic", ""))
    return "\n\n".join(
        [
            f"정책서 주제: {ctx.topic}",
            f"템플릿 유형: {ctx.template_type}",
            "주제 의미 축:\n" + prompt_json(topic_axes, 1200),
            "사용자 작성 요청 메모:\n" + user_brief_for_prompt(ctx),
            "기본 학습 요약:\n" + prompt_json(base_learning, 3500),
            "사전 주제 Knowledge Pack:\n" + prompt_json(base_learning.get("prelearned_knowledge", {}) or {}, 7000),
            "요구사항 요약:\n" + prompt_json(requirement_prompt_items(getattr(ctx, "requirements", ()) or (), limit=60), 12000),
            "참고자료 출처 프로필:\n" + prompt_json(reference_source_profile(getattr(ctx, "references", ()) or ()), 2500),
            "참고자료 핵심 근거 요약:\n" + prompt_json(reference_prompt_items(getattr(ctx, "references", ()) or (), limit=36), 14000),
            "템플릿/샘플 기준:\n" + prompt_json(guideline, 2500),
            "전문 분석 방법론 팩:\n" + prompt_json(method_knowledge_for_learning(), 7000),
            (
            "작성 요청:\n이 주제의 정책서를 작성하기 전에 반드시 반영해야 할 고객 과업, BSS 판단, 예외, 기능 범위, 정책 기준, 챕터별 작성 초점을 분석해줘.\n"
                "근거가 상충하면 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF를 우선하고, 충돌하는 2~4순위 보조/참고 근거는 학습 요약에서 삭제해라.\n"
                "사전 주제 Knowledge Pack이 있으면 작성 전략과 계층 후보의 출발점으로 사용하되, 후보를 그대로 확정하지 말고 첨부 문서 우선순위와 Evidence Gap을 그대로 지켜라.\n"
                "Knowledge Pack 후보 중 요구사항·첨부 참고자료·프로세스/기능/정책 연결로 검증되지 않는 항목은 채택하지 마라.\n"
                "먼저 현재 주제의 직접 범위와 제외/후속 범위를 구분하고, 참고자료의 인접 업무 신호는 현재 주제의 판단 기준에 직접 연결될 때만 포함해줘.\n"
                "T월드·T멤버십·T다이렉트샵·T우주 통합 지식은 채널별 책임과 상태·정책 축을 구분하는 데 사용하되, 현재 주제와 직접 관련 없는 채널 업무를 유즈케이스나 정책으로 확장하지 마라.\n"
                "주제 의미 축이 여러 개인 경우 각 축별로 필요한 판단 기준을 균형 있게 정리하되, 축 밖의 업무를 용어·유즈케이스·정책으로 확장하지 마라.\n"
                "상태 정의, 상태 전이, 프로세스, 기능, 정책은 전문 방법론 팩의 산출물 경계를 기준으로 구분하되, 산출 형식은 템플릿/샘플 기준을 유지해라."
            ),
        ]
    )


def user_brief_for_prompt(ctx) -> str:
    brief = str(getattr(ctx, "brief", "") or "").strip()
    if not brief:
        return "없음"
    return limit_prompt_text(brief, 1200)


def requirement_prompt_items(requirements: Sequence[object], limit: int = 50) -> List[dict]:
    return [
        {
            "detail_id": getattr(item, "detail_id", ""),
            "requirement_id": getattr(item, "requirement_id", ""),
            "depth3": limit_prompt_text(getattr(item, "depth3", ""), 80),
            "depth4": limit_prompt_text(getattr(item, "depth4", ""), 80),
            "detail_name": limit_prompt_text(getattr(item, "detail_name", ""), 160),
            "detail_description": limit_prompt_text(getattr(item, "detail_description", ""), 360),
            "requirement_type": limit_prompt_text(getattr(item, "requirement_type", ""), 80),
            "required": limit_prompt_text(getattr(item, "required", ""), 40),
        }
        for item in select_requirement_prompt_items(requirements, limit)
    ]


def select_requirement_prompt_items(requirements: Sequence[object], limit: int | None) -> List[object]:
    items = list(requirements)
    if limit is None or len(items) <= limit:
        return items
    if limit <= 0:
        return []

    selected: List[object] = []
    seen_ids: set[int] = set()

    def append(item: object) -> None:
        marker = id(item)
        if marker in seen_ids or len(selected) >= limit:
            return
        selected.append(item)
        seen_ids.add(marker)

    by_depth4: dict[str, List[object]] = {}
    for item in items:
        depth4 = str(getattr(item, "depth4", "") or "요구사항").strip()
        by_depth4.setdefault(depth4, []).append(item)
    for bucket in by_depth4.values():
        append(bucket[0])

    for item in select_evenly_for_prompt(items, limit):
        append(item)
    for item in items:
        append(item)
    return selected[:limit]


def select_evenly_for_prompt(values: Sequence[object], limit: int) -> List[object]:
    items = list(values)
    if limit <= 0 or len(items) <= limit:
        return items
    if limit == 1:
        return [items[0]]
    last_index = len(items) - 1
    indexes = sorted({round(index * last_index / (limit - 1)) for index in range(limit)})
    return [items[index] for index in indexes][:limit]


def reference_prompt_items(references: Sequence[object], limit: int | None = 20) -> List[dict]:
    selected_references = select_reference_prompt_items(references, limit)
    if limit is None:
        selected_references = list(references)
    if limit is not None:
        selected_references = selected_references[:limit]
    return [
        {
            "source_name": getattr(item, "source_name", ""),
            "source_type": getattr(item, "source_type", ""),
            "category": getattr(item, "category", ""),
            "source_authority": evidence_source_authority_for_values(
                getattr(item, "category", ""),
                getattr(item, "source_name", ""),
                " ".join(
                    [
                        str(getattr(item, "summary", "") or ""),
                        " ".join(str(value) for value in getattr(item, "signals", ()) or ()),
                    ]
                ),
            ),
            "authority_tier": evidence_authority_tier_for_authority(
                evidence_source_authority_for_values(
                    getattr(item, "category", ""),
                    getattr(item, "source_name", ""),
                    " ".join(
                        [
                            str(getattr(item, "summary", "") or ""),
                            " ".join(str(value) for value in getattr(item, "signals", ()) or ()),
                        ]
                    ),
                )
            ),
            "summary": limit_prompt_text(getattr(item, "summary", ""), 420),
            "signals": list(getattr(item, "signals", ()) or ())[:5],
            "evidence": reference_evidence_for_prompt(getattr(item, "evidence", ()) or (), limit=4, max_chars=220),
            "score": getattr(item, "score", 0),
            "text_chars": getattr(item, "text_chars", 0),
            "read_scope": getattr(item, "read_scope", "full_document"),
        }
        for item in selected_references
    ]


def select_reference_prompt_items(references: Sequence[object], limit: int | None) -> List[object]:
    items = list(references)
    if limit is None or len(items) <= limit:
        return sorted(items, key=reference_rank_key, reverse=True)
    best_by_category: dict[str, object] = {}
    for item in sorted(items, key=reference_rank_key, reverse=True):
        category = str(getattr(item, "category", "") or "reference")
        if category not in best_by_category:
            best_by_category[category] = item
    selected: List[object] = list(best_by_category.values())[:limit]
    seen_ids: set[int] = set()
    for item in selected:
        seen_ids.add(id(item))
    for item in sorted(items, key=reference_rank_key, reverse=True):
        if len(selected) >= limit:
            break
        if id(item) in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(id(item))
    return selected


def reference_rank_key(item: object) -> tuple[int, int, int, int]:
    return (
        reference_authority_rank(item),
        int(getattr(item, "score", 0) or 0),
        len(getattr(item, "signals", ()) or ()),
        int(getattr(item, "text_chars", 0) or 0),
    )


def reference_authority_rank(item: object) -> int:
    authority = evidence_source_authority_for_values(
        getattr(item, "category", ""),
        getattr(item, "source_name", ""),
        getattr(item, "summary", ""),
    )
    return {
        1: 5,
        2: 3,
        3: 2,
        4: 1,
    }.get(evidence_authority_tier_for_authority(authority), 1)


def reference_source_profile(references: Sequence[object]) -> dict:
    items = list(references)
    by_category: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_authority: dict[str, int] = {}
    by_authority_tier: dict[str, int] = {}
    total_chars = 0
    for item in items:
        category = str(getattr(item, "category", "") or "reference")
        source_type = str(getattr(item, "source_type", "") or "unknown")
        authority = evidence_source_authority_for_values(category, getattr(item, "source_name", ""), getattr(item, "summary", ""))
        authority_tier = evidence_authority_tier_for_authority(authority)
        by_category[category] = by_category.get(category, 0) + 1
        by_type[source_type] = by_type.get(source_type, 0) + 1
        by_authority[authority] = by_authority.get(authority, 0) + 1
        by_authority_tier[f"tier_{authority_tier}"] = by_authority_tier.get(f"tier_{authority_tier}", 0) + 1
        total_chars += int(getattr(item, "text_chars", 0) or 0)
    return {
        "total_sources_read": len(items),
        "total_text_chars_read": total_chars,
        "by_category": by_category,
        "by_source_type": by_type,
        "by_source_authority": by_authority,
        "by_authority_tier": by_authority_tier,
        "source_authority_rule": "근거가 상충하면 1순위 첨부자료·사내자료·요구사항·채널 방향성/TK 과제정의 PDF를 우선하고, 상충되는 2~4순위 보조/참고 근거는 사용하지 않는다.",
        "prompt_policy": "원천 자료는 전체 읽기 결과를 Evidence Store에 보관하고, LLM 학습에는 카테고리별 대표 근거와 고득점 근거만 전달한다.",
    }


def reference_evidence_for_prompt(evidence: Sequence[object], limit: int = 3, max_chars: int = 180) -> List[str]:
    items = []
    for value in list(evidence)[:limit]:
        text = str(value).strip()
        if not text:
            continue
        items.append(text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…")
    return items


def limit_prompt_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def topic_learning_schema() -> dict:
    return object_schema(
        {
            "topic_understanding": {"type": "string"},
            "scope_boundary": object_schema(
                {
                    "direct_scope": array_schema({"type": "string"}),
                    "related_but_not_core": array_schema({"type": "string"}),
                    "excluded_or_later": array_schema({"type": "string"}),
                }
            ),
            "customer_tasks": array_schema({"type": "string"}),
            "requirement_implications": array_schema({"type": "string"}),
            "reference_implications": array_schema({"type": "string"}),
            "bss_implications": array_schema({"type": "string"}),
            "policy_risks": array_schema({"type": "string"}),
            "chapter_focus": object_schema(
                {
                    "overview": {"type": "string"},
                    "terms": {"type": "string"},
                    "actors": {"type": "string"},
                    "usecases": {"type": "string"},
                    "usecase_diagram": {"type": "string"},
                    "state": {"type": "string"},
                    "process": {"type": "string"},
                    "functions": {"type": "string"},
                    "policies": {"type": "string"},
                    "final_check": {"type": "string"},
                }
            ),
        }
    )


def build_learning_summary(topic: str, requirements: Sequence[object], references: Sequence[object]) -> str:
    parts = [f"{topic} 주제 작성 전 요구사항 {len(requirements)}건과 참고자료 {len(references)}건을 확인한다."]
    if requirements:
        parts.append("요구사항은 원문 추적표로 복사하지 않고 고객 과업, 검증 조건, 예외, 운영 기준으로 재구성한다.")
    if references:
        total_chars = sum(int(getattr(item, "text_chars", 0) or 0) for item in references)
        parts.append(
            f"참고자료는 전체 문서 범위로 읽고 총 {total_chars:,}자 분량에서 채널 전략, 고객 불편, IA, 벤치마킹, AI·개인화 관점을 정책 판단 기준으로 재구성한다."
        )
    return " ".join(parts)


def build_agent_guideline(template_html: str, sample_htmls: Sequence[str]) -> dict:
    sample_metrics = [html_metrics(sample) for sample in sample_htmls]
    max_sample = max(sample_metrics, key=lambda item: item["body_bytes"], default={})
    return {
        "template": {
            "preserve_style": "<style" in template_html.casefold(),
            "preserve_page_container": ".page" in template_html,
        },
        "sample_baseline": max_sample,
        "common_rules": [
            "기존 템플릿 CSS와 .page 구조를 유지한다.",
            "JSON에는 <br/>를 직접 쓰지 않는다. HTML 줄바꿈은 렌더링 단계에서 문장 마침표 뒤에 적용한다.",
            "샘플처럼 표 기반으로 장별 판단 기준을 촘촘히 작성하되, 셀 하나는 짧게 쓰고 기준이 여러 개면 행이나 정책 항목을 분리한다.",
            "전문 분석 방법론은 액터·유즈케이스·상태·프로세스·기능·정책 판단에만 사용하고, 템플릿/샘플에 없는 장·표·필드는 추가하지 않는다.",
            "개요와 액터는 샘플 간소화본처럼 짧게 쓰고, 상세 판단 기준은 프로세스·기능·정책 장에 배치한다.",
            "유즈케이스, 상태, 프로세스, 기능, 정책 ID의 연결성을 유지한다.",
            "정책 상세는 모호한 설명이 아니라 실제 기능 동작값, 허용 목록, 횟수, 시간, 제한 조건, 채널, 예외, 이력 기준으로 작성한다.",
        ],
    }


def html_metrics(document: str) -> dict:
    body = re.sub(r"<style.*?</style>", "", document, flags=re.DOTALL | re.IGNORECASE)
    return {
        "body_bytes": len(body.encode("utf-8")),
        "table_count": len(re.findall(r"<table\b", body, flags=re.IGNORECASE)),
        "h4_count": len(re.findall(r"<h4\b", body, flags=re.IGNORECASE)),
        "policy_item_count": body.count("policy-item-title"),
        "text_chars": len(strip_tags(body)),
    }


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def unique_nonempty(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
