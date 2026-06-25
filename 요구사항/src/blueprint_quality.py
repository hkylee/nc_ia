"""Quality gate for the authoring blueprint.

The blueprint is useful only when it is treated as a verified writing
hypothesis, not as an unquestioned source of truth. This module checks that the
learning output, requirements, evidence, and stage-level writing contracts are
strong enough before chapter writers start.
"""

from __future__ import annotations

import os
import re
from typing import List, Mapping, Sequence


DEFAULT_BLUEPRINT_GATE_MIN_SCORE = 85
CORE_STAGES = (
    "overview",
    "usecases",
    "state",
    "process",
    "functions",
    "policies",
    "process_detail",
    "function_detail",
)
HARD_STAGES = ("usecases", "state", "process", "policies", "process_detail", "function_detail")
REQUIRED_LEARNING_FIELDS = (
    "customer_tasks",
    "requirement_implications",
    "bss_implications",
    "policy_risks",
    "chapter_focus",
)


def validate_blueprint_quality(
    blueprint: Mapping[str, object],
    learning: Mapping[str, object],
    *,
    threshold: int | None = None,
) -> dict:
    """Return a deterministic quality report for the authoring blueprint."""
    min_score = threshold if threshold is not None else blueprint_gate_min_score()
    findings: List[dict] = []
    findings.extend(source_findings(blueprint))
    findings.extend(learning_findings(learning))
    findings.extend(architecture_findings(blueprint))
    findings.extend(stage_findings(blueprint))
    findings.extend(topic_axis_findings(blueprint, learning))

    error_count = sum(1 for item in findings if item.get("severity") == "error")
    warn_count = sum(1 for item in findings if item.get("severity") == "warn")
    gate_blocker_count = sum(1 for item in findings if item.get("is_quality_gate"))
    score = max(0, 100 - error_count * 14 - warn_count * 4)
    passed = score >= min_score and error_count == 0 and gate_blocker_count == 0
    status = "passed" if passed else "risk_flag"
    return {
        "version": "blueprint-quality-v1",
        "status": status,
        "passed": passed,
        "score": score,
        "threshold": min_score,
        "error_count": error_count,
        "warn_count": warn_count,
        "gate_blocker_count": gate_blocker_count,
        "summary": blueprint_quality_summary(status, findings),
        "findings": findings,
        "stage_risk_map": stage_risk_map(findings),
        "rule": (
            "Authoring Blueprint는 확정 정답이 아니라 검증된 작성 가설이다. "
            "risk_flag가 있으면 장별 Writer와 Inspector는 해당 stage의 finding을 우선 확인한다."
        ),
    }


def blueprint_gate_min_score() -> int:
    value = os.getenv("BLUEPRINT_GATE_MIN_SCORE", "").strip()
    try:
        return int(value) if value else DEFAULT_BLUEPRINT_GATE_MIN_SCORE
    except ValueError:
        return DEFAULT_BLUEPRINT_GATE_MIN_SCORE


def source_findings(blueprint: Mapping[str, object]) -> List[dict]:
    findings: List[dict] = []
    meta = mapping_value(blueprint, "meta")
    source_profile = mapping_value(blueprint, "source_profile")
    requirement_count = safe_int(meta.get("requirements_count"))
    reference_count = safe_int(meta.get("references_count"))
    categories = set(str(value) for value in list_value(source_profile, "reference_categories"))
    coverage_matrix = list_value(blueprint, "coverage_matrix")
    reference_cards = list_value(blueprint, "reference_cards")
    evidence_gaps = [item for item in list_value(blueprint, "evidence_gaps") if isinstance(item, Mapping)]
    has_requirement_gap = any(str(item.get("kind", "")) == "requirements" for item in evidence_gaps)

    if requirement_count <= 0 and has_requirement_gap:
        findings.append(
            finding(
                "BP-SOURCE-000",
                "warn",
                "traceability",
                "직접 요구사항 매칭 없음",
                "요구사항 통합 list에서 현재 주제와 직접 연결된 요구사항을 찾지 못했습니다. 이 상태로 작성하면 요구사항을 정책 질문으로 해석하지 못하고 일반론으로 흐를 수 있습니다.",
                "주제명·4depth 매칭을 먼저 점검하고, 정말 요구사항이 없는 주제라면 Evidence Gap을 명시한 상태로 Writer가 요구사항을 임의로 만들지 않게 하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.requirement_cards",
                gate=True,
            )
        )
    if requirement_count > 0 and not coverage_matrix:
        findings.append(
            finding(
                "BP-SOURCE-001",
                "error",
                "traceability",
                "요구사항 Coverage Matrix 누락",
                "요구사항은 있으나 Blueprint에 coverage_matrix가 없어 장별 반영 기준을 만들 수 없습니다.",
                "요구사항별 target_stages를 포함한 coverage_matrix를 생성해야 합니다.",
                stage="blueprint",
                target_path="authoring_blueprint.coverage_matrix",
                gate=True,
            )
        )
    if reference_count > 0 and not reference_cards:
        findings.append(
            finding(
                "BP-SOURCE-002",
                "error",
                "traceability",
                "참고자료 카드 누락",
                "참고자료는 있으나 Blueprint에 reference_cards가 없어 근거 기반 작성 방향을 검증할 수 없습니다.",
                "DB에서 선별한 참고자료 요약과 evidence id를 Blueprint에 포함해야 합니다.",
                stage="blueprint",
                target_path="authoring_blueprint.reference_cards",
                gate=True,
            )
        )
    if reference_count > 0 and not categories.intersection({"voc", "research"}):
        findings.append(
            finding(
                "BP-SOURCE-003",
                "warn",
                "evidence",
                "고객 근거 약함",
                "VoC 또는 고객 조사 근거가 약하면 고객 과업과 Pain Point가 일반화될 수 있습니다.",
                "usecases와 process 작성 시 고객 행동·불편 근거를 Context Pack에서 우선 보강하세요.",
                stage="usecases",
                target_path="authoring_blueprint.source_profile.reference_categories",
            )
        )
    if reference_count > 0 and "ia" not in categories:
        findings.append(
            finding(
                "BP-SOURCE-004",
                "warn",
                "evidence",
                "IA/Flow 근거 약함",
                "IA 또는 Flow 근거가 약하면 프로세스와 기능이 추상적으로 작성될 수 있습니다.",
                "process와 functions 작성 시 선택된 Context Pack에 flow 근거가 있는지 확인하세요.",
                stage="process",
                target_path="authoring_blueprint.source_profile.reference_categories",
            )
        )
    return findings


def architecture_findings(blueprint: Mapping[str, object]) -> List[dict]:
    findings: List[dict] = []
    contract = mapping_value(blueprint, "architecture_contract")
    if not contract:
        findings.append(
            finding(
                "BP-ARCH-missing",
                "warn",
                "structure",
                "Blueprint Architect 계약 누락",
                "작성 전 액터-유즈케이스-프로세스-기능-정책 계층 계약이 없어 장별 Agent가 서로 다른 입자도로 작성할 수 있습니다.",
                "Blueprint Architect Agent가 hierarchy_chains와 stage_contracts를 생성하도록 연결하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract",
            )
        )
        return findings

    stage_contracts = [item for item in list_value(contract, "stage_contracts") if isinstance(item, Mapping)]
    stages = {str(item.get("stage", "")) for item in stage_contracts}
    required = {"actors", "usecases", "state", "process", "functions", "policies", "final_check"}
    missing = sorted(required - stages)
    if missing:
        findings.append(
            finding(
                "BP-ARCH-stage-contracts",
                "warn",
                "structure",
                "계층 Stage Contract 일부 누락",
                f"Blueprint Architect 계약에 필요한 stage_contract가 일부 없습니다: {', '.join(missing)}",
                "누락 stage의 layer, granularity, acceptance_checks를 추가하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract.stage_contracts",
            )
        )
    first_draft_plan = mapping_value(contract, "first_draft_quality_plan")
    stage_checks = [item for item in list_value(first_draft_plan, "stage_checks") if isinstance(item, Mapping)]
    first_draft_stages = {str(item.get("stage", "")) for item in stage_checks}
    missing_first_draft = sorted(required - first_draft_stages)
    if not first_draft_plan or missing_first_draft:
        findings.append(
            finding(
                "BP-ARCH-first-draft-plan",
                "warn",
                "structure",
                "초안 품질 계획 누락",
                "Writer가 Inspector 기준을 출력 전 자체 점검할 first_draft_quality_plan이 부족합니다."
                + (f" 누락 stage: {', '.join(missing_first_draft)}" if missing_first_draft else ""),
                "각 핵심 장별 before_write, must_produce, self_check, reject_if 기준을 포함하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract.first_draft_quality_plan",
            )
        )
    chains = [item for item in list_value(contract, "hierarchy_chains") if isinstance(item, Mapping)]
    chain_names = {str(item.get("name", "")) for item in chains}
    if "execution_chain" not in chain_names or "policy_chain" not in chain_names:
        findings.append(
            finding(
                "BP-ARCH-chains",
                "warn",
                "structure",
                "핵심 계층 Chain 누락",
                "execution_chain 또는 policy_chain이 없어 본문 작성 전 계위 기준이 약합니다.",
                "액터→유즈케이스→프로세스→기능→세부 기능 구성, 프로세스→정책→정책 항목 chain을 모두 포함하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract.hierarchy_chains",
            )
        )
    evidence_pack = mapping_value(contract, "architecture_evidence_pack")
    if not evidence_pack and (list_value(blueprint, "reference_cards") or list_value(blueprint, "coverage_matrix")):
        findings.append(
            finding(
                "BP-ARCH-evidence-pack",
                "warn",
                "traceability",
                "Architecture Evidence Pack 누락",
                "Blueprint Architect가 참고자료/요구사항 근거 카드를 직접 받지 못하면 skeleton이 학습 요약에만 의존할 수 있습니다.",
                "Evidence Store에서 usecases, state, process, functions, policies별 근거 카드를 선별해 architecture_evidence_pack에 포함하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract.architecture_evidence_pack",
            )
        )
    skeleton = mapping_value(contract, "hierarchy_skeleton")
    if not skeleton:
        findings.append(
            finding(
                "BP-ARCH-skeleton-missing",
                "warn",
                "structure",
                "계층 Skeleton 누락",
                "Blueprint Architect 계약에 실제 작성 전 후보 구조가 없어 Writer가 원칙만 보고 장별 내용을 추정할 수 있습니다.",
                "actor_candidates, usecase_groups, process_patterns, function_capabilities, policy_taxonomy를 포함한 hierarchy_skeleton을 생성하세요.",
                stage="blueprint",
                target_path="authoring_blueprint.architecture_contract.hierarchy_skeleton",
            )
        )
    else:
        required_sections = {
            "actor_candidates": "액터 후보",
            "usecase_groups": "유즈케이스 그룹",
            "process_patterns": "프로세스 분해 패턴",
            "function_capabilities": "기능 후보",
            "policy_taxonomy": "정책 분류",
        }
        missing_sections = [
            label
            for key, label in required_sections.items()
            if not list_value(skeleton, key)
        ]
        if missing_sections:
            findings.append(
                finding(
                    "BP-ARCH-skeleton-sections",
                    "warn",
                    "structure",
                    "계층 Skeleton 일부 비어 있음",
                    f"작성 전 skeleton에서 일부 영역이 비어 있습니다: {', '.join(missing_sections)}",
                    "비어 있는 영역을 최소 후보 구조로 채워 장별 Writer가 같은 계위 기준을 보게 하세요.",
                    stage="blueprint",
                    target_path="authoring_blueprint.architecture_contract.hierarchy_skeleton",
                )
            )
        process_boundary_keywords = ("시작", "접수", "판단", "검증", "조건", "분기", "요청", "반영", "결과", "안내", "완료", "예외", "실패", "제한", "보류")
        for group in list_value(skeleton, "usecase_groups"):
            pattern_text = " ".join(str(item) for item in list_value(group, "process_pattern")) if isinstance(group, Mapping) else ""
            if isinstance(group, Mapping) and not any(keyword in pattern_text for keyword in process_boundary_keywords):
                findings.append(
                    finding(
                        "BP-ARCH-usecase-process-pattern",
                        "warn",
                        "specificity",
                        "유즈케이스 분해 패턴 약함",
                        "usecase_groups의 process_pattern에 업무 전환점이 보이지 않으면 유즈케이스가 포괄 프로세스로 축약될 위험이 있습니다.",
                        "각 상위 유즈케이스 후보에 시작, 판단, 처리 요청, 결과 안내, 예외 등 실제 책임 경계가 드러나는 process_pattern을 둡니다. 개수 맞추기가 아니라 책임 경계 분리를 기준으로 합니다.",
                        stage="usecases",
                        target_path="authoring_blueprint.architecture_contract.hierarchy_skeleton.usecase_groups",
                    )
                )
                break
        evidence_missing_sections: List[str] = []
        for section in ("usecase_groups", "process_patterns", "function_capabilities", "policy_taxonomy"):
            rows = [row for row in list_value(skeleton, section) if isinstance(row, Mapping)]
            if rows and not any(list_value(row, "evidence_ids") for row in rows):
                evidence_missing_sections.append(section)
        if evidence_missing_sections:
            findings.append(
                finding(
                    "BP-ARCH-skeleton-evidence",
                    "warn",
                    "traceability",
                    "계층 Skeleton 근거 ID 약함",
                    f"일부 skeleton 영역에 evidence_ids가 없습니다: {', '.join(evidence_missing_sections)}",
                    "각 skeleton 후보에는 관련 요구사항 또는 참고자료 evidence_id를 연결해 Writer와 Inspector가 근거를 추적하게 하세요.",
                    stage="blueprint",
                    target_path="authoring_blueprint.architecture_contract.hierarchy_skeleton",
                )
            )
        for capability in list_value(skeleton, "function_capabilities"):
            if isinstance(capability, Mapping) and len(list_value(capability, "detail_granularity")) < 2:
                findings.append(
                    finding(
                        "BP-ARCH-function-detail-granularity",
                        "warn",
                        "specificity",
                        "기능 세부 구성 기준 약함",
                        "function_capabilities의 detail_granularity가 약하면 기능 상세가 문장형 설명으로 흐를 수 있습니다.",
                        "각 기능 후보에는 조회 조건 구성, 권한 상태 검증, 결과 안내 구성처럼 2개 이상의 짧은 하위 처리명을 둡니다.",
                        stage="functions",
                        target_path="authoring_blueprint.architecture_contract.hierarchy_skeleton.function_capabilities",
                    )
                )
                break
    return findings


def learning_findings(learning: Mapping[str, object]) -> List[dict]:
    findings: List[dict] = []
    scope_boundary = mapping_value(learning, "scope_boundary")
    if not list_value(scope_boundary, "direct_scope"):
        findings.append(
            finding(
                "BP-LEARN-001",
                "error",
                "scope",
                "직접 범위 누락",
                "학습 결과에 direct_scope가 없어 장별 Agent가 현재 정책서의 직접 작성 범위를 고정하기 어렵습니다.",
                "학습 단계에서 직접 범위, 관련 범위, 제외/후속 범위를 분리해야 합니다.",
                stage="overview",
                target_path="learning.scope_boundary.direct_scope",
                gate=True,
            )
        )
    if not list_value(scope_boundary, "excluded_or_later"):
        findings.append(
            finding(
                "BP-LEARN-002",
                "warn",
                "scope",
                "제외/후속 범위 약함",
                "제외 범위가 약하면 인접 업무가 용어·유즈케이스·정책으로 과확장될 수 있습니다.",
                "overview와 usecases 작성 시 인접 업무를 본문 범위로 확장하지 않도록 제외 기준을 명시하세요.",
                stage="overview",
                target_path="learning.scope_boundary.excluded_or_later",
            )
        )
    for field in REQUIRED_LEARNING_FIELDS:
        value = learning.get(field)
        has_value = bool(value) if not isinstance(value, list) else bool([item for item in value if str(item).strip()])
        if field == "chapter_focus" and isinstance(value, Mapping):
            has_value = any(str(item).strip() for item in value.values())
        if not has_value:
            stage = field_stage(field)
            findings.append(
                finding(
                    f"BP-LEARN-{field.upper()}",
                    "warn" if field not in {"bss_implications", "policy_risks"} else "error",
                    "specificity",
                    f"{field} 학습 결과 약함",
                    f"학습 결과의 {field}가 비어 있어 후속 장이 일반론으로 작성될 위험이 있습니다.",
                    "해당 장 작성 시 Context Pack의 근거를 우선 반영하고, 근거가 부족하면 Evidence Gap으로 남기세요.",
                    stage=stage,
                    target_path=f"learning.{field}",
                    gate=field in {"bss_implications", "policy_risks"},
                )
            )
    return findings


def stage_findings(blueprint: Mapping[str, object]) -> List[dict]:
    findings: List[dict] = []
    chapters = [item for item in list_value(blueprint, "chapter_blueprints") if isinstance(item, Mapping)]
    by_stage = {str(item.get("stage", "")): item for item in chapters}
    coverage_matrix = list_value(blueprint, "coverage_matrix")
    coverage_by_stage: dict[str, int] = {}
    for row in coverage_matrix:
        if not isinstance(row, Mapping):
            continue
        for stage in list_value(row, "target_stages"):
            coverage_by_stage[str(stage)] = coverage_by_stage.get(str(stage), 0) + 1

    for stage in CORE_STAGES:
        chapter = by_stage.get(stage)
        if not chapter:
            findings.append(
                finding(
                    f"BP-STAGE-{stage}-missing",
                    "error",
                    "structure",
                    f"{stage} Blueprint 누락",
                    f"{stage} 장의 작성 기준이 없어 Agent가 공통 방향 없이 작성할 수 있습니다.",
                    f"{stage} stage_blueprint를 생성하고 focus, must_cover, evidence_ids를 포함해야 합니다.",
                    stage=stage,
                    target_path=f"authoring_blueprint.chapter_blueprints[{stage}]",
                    gate=True,
                )
            )
            continue
        if not list_value(chapter, "must_cover"):
            findings.append(
                finding(
                    f"BP-STAGE-{stage}-must-cover",
                    "error",
                    "structure",
                    f"{stage} must_cover 누락",
                    f"{stage} 장의 필수 작성 기준이 비어 있습니다.",
                    "샘플/AGENTS.md 기준의 필수 포함 항목을 must_cover로 채우세요.",
                    stage=stage,
                    target_path=f"authoring_blueprint.chapter_blueprints[{stage}].must_cover",
                    gate=True,
                )
            )
        if not list_value(chapter, "evidence_ids"):
            severity = "error" if stage in HARD_STAGES else "warn"
            findings.append(
                finding(
                    f"BP-STAGE-{stage}-evidence",
                    severity,
                    "traceability",
                    f"{stage} 근거 ID 약함",
                    f"{stage} 장의 evidence_ids가 없어 장별 작성이 요구사항·참고자료와 분리될 수 있습니다.",
                    "작성 직전 Context Pack에서 해당 stage의 요구사항/참고자료 근거를 다시 선별하세요.",
                    stage=stage,
                    target_path=f"authoring_blueprint.chapter_blueprints[{stage}].evidence_ids",
                    gate=severity == "error",
                )
            )
        if coverage_by_stage.get(stage, 0) and not list_value(chapter, "target_requirement_ids"):
            findings.append(
                finding(
                    f"BP-STAGE-{stage}-requirements",
                    "error",
                    "traceability",
                    f"{stage} 대상 요구사항 누락",
                    f"coverage_matrix에는 {stage} 반영 대상 요구사항이 있으나 stage_blueprint에는 target_requirement_ids가 없습니다.",
                    "coverage_matrix 기준으로 target_requirement_ids를 stage_blueprint에 반영하세요.",
                    stage=stage,
                    target_path=f"authoring_blueprint.chapter_blueprints[{stage}].target_requirement_ids",
                    gate=True,
                )
            )
        analysis_focus = mapping_value(chapter, "analysis_focus")
        if stage in HARD_STAGES and not any(list_value(analysis_focus, key) for key in analysis_focus):
            findings.append(
                finding(
                    f"BP-STAGE-{stage}-analysis",
                    "warn",
                    "specificity",
                    f"{stage} 분석 초점 약함",
                    f"{stage} 장의 analysis_focus가 약해 구조는 맞지만 일반적인 설명으로 흐를 수 있습니다.",
                    "고객 과업, BSS 판단, 예외, 정책 판단축 중 이 장에 필요한 항목을 보강하세요.",
                    stage=stage,
                    target_path=f"authoring_blueprint.chapter_blueprints[{stage}].analysis_focus",
                )
            )
    return findings


def topic_axis_findings(blueprint: Mapping[str, object], learning: Mapping[str, object]) -> List[dict]:
    topic = str(mapping_value(blueprint, "meta").get("topic", "") or learning.get("topic", "")).strip()
    axes = topic_axes(topic)
    if len(axes) < 2:
        return []
    payload = normalize_for_match(f"{learning} {blueprint.get('analysis_signals', {})}")
    missing = [axis for axis in axes if not topic_axis_present(payload, axis)]
    if not missing:
        return []
    return [
        finding(
            "BP-TOPIC-001",
            "warn",
            "scope",
            "주제 의미 축 일부 약함",
            f"복합 주제의 일부 의미 축이 학습/Blueprint에 약하게 반영됐습니다: {', '.join(missing)}",
            "각 장 작성 시 누락된 의미 축이 범위, 유즈케이스, 프로세스, 정책 판단 기준에 필요한지 확인하세요.",
            stage="overview",
            target_path="learning.topic_understanding",
        )
    ]


def topic_axes(topic: str) -> List[str]:
    raw = re.sub(r"\s+", " ", str(topic or "")).strip()
    if not raw:
        return []
    parts = [part.strip() for part in re.split(r"\s*(?:/|·|,|，|\+|&|\b및\b|\band\b)\s*", raw) if part.strip()]
    return [part for part in parts if normalize_for_match(part) not in {"nc", "통합채널", "정책서", "정책"}]


def topic_axis_present(payload: str, axis: str) -> bool:
    normalized = normalize_for_match(axis)
    if normalized and normalized in payload:
        return True
    tokens = [normalize_for_match(token) for token in re.split(r"\s+", axis) if token.strip()]
    return bool(tokens) and all(token in payload for token in tokens)


def stage_risk_map(findings: Sequence[Mapping[str, object]]) -> dict:
    result: dict[str, dict] = {}
    for item in findings:
        stage = str(item.get("stage", "") or "blueprint")
        bucket = result.setdefault(stage, {"error": 0, "warn": 0, "finding_ids": []})
        severity = str(item.get("severity", "warn"))
        bucket[severity] = int(bucket.get(severity, 0) or 0) + 1
        bucket["finding_ids"].append(item.get("issue_id", ""))
    return result


def blueprint_quality_summary(status: str, findings: Sequence[Mapping[str, object]]) -> str:
    if not findings:
        return "Blueprint가 요구사항, 참고자료, 장별 작성 기준을 갖추고 있어 본문 작성을 시작할 수 있습니다."
    errors = sum(1 for item in findings if item.get("severity") == "error")
    warnings = sum(1 for item in findings if item.get("severity") == "warn")
    return f"Blueprint 품질 상태는 {status}입니다. 오류 {errors}건, 경고 {warnings}건을 이후 작성/검수에 전달합니다."


def finding(
    issue_id: str,
    severity: str,
    category: str,
    title: str,
    detail: str,
    recommendation: str,
    *,
    stage: str,
    target_path: str,
    gate: bool = False,
) -> dict:
    return {
        "issue_id": issue_id,
        "severity": severity,
        "priority_tier": "P1" if severity == "error" or gate else "P2",
        "category": category,
        "stage": stage,
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
        "target_path": target_path,
        "is_quality_gate": bool(gate),
        "fix_owner": "blueprint",
        "acceptance_check": "해당 stage 작성 전에 근거, 범위, 필수 포함 기준이 명시되어야 합니다.",
    }


def field_stage(field: str) -> str:
    return {
        "customer_tasks": "usecases",
        "requirement_implications": "overview",
        "bss_implications": "process",
        "policy_risks": "policies",
        "chapter_focus": "blueprint",
    }.get(field, "blueprint")


def mapping_value(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key) if isinstance(mapping, Mapping) else None
    return value if isinstance(value, Mapping) else {}


def list_value(mapping: Mapping[str, object], key: str) -> list:
    value = mapping.get(key) if isinstance(mapping, Mapping) else None
    return value if isinstance(value, list) else []


def safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize_for_match(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()
