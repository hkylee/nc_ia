"""Validate prebuilt topic knowledge packs for sufficiency and conflicts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Mapping

try:
    from topic_knowledge_builder import (
        DEFAULT_TOPIC_KNOWLEDGE_DIR,
        POLICY_TOPICS,
        TOPIC_KNOWLEDGE_VERSION,
        domain_candidate_triggers,
    )
except ImportError:  # pragma: no cover - package import fallback.
    from .topic_knowledge_builder import (
        DEFAULT_TOPIC_KNOWLEDGE_DIR,
        POLICY_TOPICS,
        TOPIC_KNOWLEDGE_VERSION,
        domain_candidate_triggers,
    )


def validate_topic_knowledge_dir(root: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> dict:
    findings = []
    topic_results = []
    expected = set(POLICY_TOPICS)
    existing_topics = set()
    for path in sorted(root.glob("*.json")):
        if path.name in {"manifest.json", "validation_report.json"}:
            continue
        data = read_json(path)
        if not looks_like_topic_pack(data):
            continue
        topic = str(data.get("topic", "") or path.stem)
        existing_topics.add(topic)
        result = validate_pack(data, path)
        topic_results.append(result)
        findings.extend(result["findings"])
    for missing in sorted(expected - existing_topics):
        findings.append(finding("P1", "missing_pack", missing, "사전 Knowledge Pack이 없습니다.", "prelearn을 다시 실행하세요."))
    version_mismatch_count = sum(1 for item in topic_results if item["version"] != TOPIC_KNOWLEDGE_VERSION)
    p1_count = sum(1 for item in findings if item["priority"] == "P1")
    p2_count = sum(1 for item in findings if item["priority"] == "P2")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "expected_topic_count": len(expected),
        "actual_topic_count": len(existing_topics),
        "version": TOPIC_KNOWLEDGE_VERSION,
        "version_mismatch_count": version_mismatch_count,
        "summary": {
            "status": "pass" if not p1_count and not p2_count else "review",
            "p1": p1_count,
            "p2": p2_count,
            "p3": sum(1 for item in findings if item["priority"] == "P3"),
            "topics_with_requirements": sum(1 for item in topic_results if item["requirements_count"] > 0),
            "topics_with_primary_references": sum(1 for item in topic_results if item["primary_reference_count"] > 0),
            "topics_with_auxiliary_web": sum(1 for item in topic_results if item["auxiliary_web_reference_count"] > 0),
        },
        "topic_results": topic_results,
        "findings": findings,
    }


def looks_like_topic_pack(data: Mapping[str, object]) -> bool:
    """Return true only for generated Topic Knowledge Pack JSON files."""
    return bool(
        data.get("topic")
        and data.get("version")
        and isinstance(data.get("source_profile"), Mapping)
        and isinstance(data.get("candidate_inventory"), Mapping)
        and isinstance(data.get("topic_evidence_map"), Mapping)
    )


def validate_pack(data: Mapping[str, object], path: Path) -> dict:
    topic = str(data.get("topic", "") or path.stem)
    findings = []
    profile = data.get("source_profile", {}) if isinstance(data.get("source_profile"), Mapping) else {}
    requirements_count = int(profile.get("requirements_count", 0) or 0)
    primary_reference_count = int(profile.get("primary_reference_count", 0) or 0)
    auxiliary_web_reference_count = int(profile.get("auxiliary_web_reference_count", 0) or 0)
    candidate_policy = data.get("candidate_usage_policy", {}) if isinstance(data.get("candidate_usage_policy"), Mapping) else {}
    topic_contract = data.get("topic_contract", {}) if isinstance(data.get("topic_contract"), Mapping) else {}
    source_rule = data.get("source_authority_rule", {}) if isinstance(data.get("source_authority_rule"), Mapping) else {}
    inventory = data.get("candidate_inventory", {}) if isinstance(data.get("candidate_inventory"), Mapping) else {}
    topic_map = data.get("topic_evidence_map", {}) if isinstance(data.get("topic_evidence_map"), Mapping) else {}
    stages = topic_map.get("stages", {}) if isinstance(topic_map.get("stages"), Mapping) else {}

    if data.get("version") != TOPIC_KNOWLEDGE_VERSION:
        findings.append(finding("P1", "version", topic, "Knowledge Pack 버전이 현재 코드와 다릅니다.", "prelearn을 다시 실행하세요."))
    if requirements_count <= 0:
        findings.append(finding("P1", "coverage", topic, "매칭된 요구사항이 없습니다.", "요구사항 depth4 매칭 또는 주제명을 확인하세요."))
    if primary_reference_count <= 0:
        findings.append(finding("P2", "coverage", topic, "첨부 참고자료 근거가 없습니다.", "공개웹이 아닌 첨부 근거를 보강하세요."))
    if not candidate_policy.get("use_as_candidate_only"):
        findings.append(finding("P1", "candidate_guard", topic, "후보 전용 정책이 없습니다.", "candidate_usage_policy.use_as_candidate_only를 true로 둬야 합니다."))
    if "상충" not in str(source_rule.get("conflict_policy", "")):
        findings.append(finding("P1", "source_authority", topic, "근거 우선순위 충돌 처리 규칙이 약합니다.", "conflict_policy에 상충 시 상위 근거 우선 규칙을 명시하세요."))
    if not topic_contract:
        findings.append(finding("P1", "topic_contract", topic, "주제별 작성 계약서가 없습니다.", "prelearn을 다시 실행해 topic_contract를 생성하세요."))
    else:
        required_contract_fields = ("topic_definition", "writing_goal", "direct_scope", "must_cover", "must_not_cover", "focus_points", "boundary_rule")
        missing_fields = [field for field in required_contract_fields if not topic_contract.get(field)]
        if missing_fields:
            findings.append(
                finding(
                    "P1",
                    "topic_contract",
                    topic,
                    f"주제별 작성 계약서 필드가 부족합니다: {', '.join(missing_fields)}.",
                    "topic_contract 생성 규칙과 요구사항 매핑을 확인하세요.",
                )
            )
        if "상세 요구사항" not in str(topic_contract.get("requirement_basis", "")):
            findings.append(
                finding(
                    "P2",
                    "topic_contract_basis",
                    topic,
                    "주제 계약서가 상세 요구사항명/설명 기준을 명시하지 않습니다.",
                    "requirement_basis에 상세 요구사항명과 상세 요구사항 설명 기준을 명시하세요.",
                )
            )
    for stage in ("overview", "terms", "actors", "usecases", "state", "process", "functions", "policies", "final_check"):
        stage_data = stages.get(stage, {}) if isinstance(stages.get(stage), Mapping) else {}
        if not stage_data.get("evidence_ids"):
            findings.append(finding("P2", "stage_evidence", topic, f"{stage} 장 근거 카드가 없습니다.", "Context Pack 근거 선별을 확인하세요."))
    if generic_candidate_leak(topic, inventory.get("policy_item_candidates", [])):
        findings.append(finding("P2", "generic_candidate", topic, "정책 후보가 주제 특화 없이 일반 기준에 치우쳐 있습니다.", "후보 생성 corpus를 주제 앵커 중심으로 좁히세요."))
    leaked = off_topic_candidate_markers(topic, inventory)
    if leaked:
        findings.append(
            finding(
                "P2",
                "off_topic_candidate",
                topic,
                f"현재 주제와 직접 관련 없는 후보 키워드가 섞였습니다: {', '.join(leaked)}.",
                "후보 확장은 주제명과 해당 주제 요구사항에서 직접 나온 키워드로만 제한하세요.",
            )
        )
    if primary_reference_count == 0 and auxiliary_web_reference_count > 0:
        findings.append(finding("P1", "web_overreach", topic, "공개웹 보조 지식만 있고 첨부 근거가 없습니다.", "확정 정책값을 쓰지 말고 첨부 근거를 먼저 보강하세요."))

    return {
        "topic": topic,
        "path": str(path),
        "version": str(data.get("version", "")),
        "requirements_count": requirements_count,
        "primary_reference_count": primary_reference_count,
        "auxiliary_web_reference_count": auxiliary_web_reference_count,
        "policy_candidate_count": len(inventory.get("policy_item_candidates", []) if isinstance(inventory.get("policy_item_candidates", []), list) else []),
        "function_candidate_count": len(inventory.get("function_candidates", []) if isinstance(inventory.get("function_candidates", []), list) else []),
        "finding_count": len(findings),
        "findings": findings,
    }


def generic_candidate_leak(topic: str, candidates: object) -> bool:
    if not isinstance(candidates, list) or not candidates:
        return True
    topic_key = "".join(ch for ch in topic if ch.isalnum())
    topic_parts = [part for part in topic.replace("·", "/").replace(" ", "/").split("/") if len(part) >= 2]
    first_candidates = " ".join(str(item) for item in candidates[:5])
    if topic_key and topic_key in "".join(ch for ch in first_candidates if ch.isalnum()):
        return False
    return not any(part in first_candidates for part in topic_parts)


def off_topic_candidate_markers(topic: str, inventory: Mapping[str, object]) -> List[str]:
    allowed = set(domain_candidate_triggers(topic))
    for marker in list(allowed):
        allowed.update(RELATED_MARKER_ALLOWLIST.get(marker, ()))
    topic_text = str(topic or "")
    for marker in OFF_TOPIC_MARKERS:
        if marker in topic_text:
            allowed.add(marker)
    candidate_text = " ".join(
        str(item)
        for key in ("function_candidates", "policy_item_candidates", "state_candidates", "process_patterns")
        for item in inventory.get(key, [])
        if isinstance(inventory.get(key, []), list)
    )
    leaked = []
    for marker in OFF_TOPIC_MARKERS:
        if marker in candidate_text and marker not in allowed:
            leaked.append(marker)
    return leaked


OFF_TOPIC_MARKERS = (
    "결제",
    "납부",
    "배송",
    "교환",
    "반품",
    "쿠폰",
    "이용권",
    "구독",
    "멤버십",
    "환불",
    "검색",
    "알림",
    "회원",
    "포인트",
    "혜택",
)

RELATED_MARKER_ALLOWLIST = {
    "멤버십": ("혜택",),
    "혜택": ("멤버십",),
    "쿠폰": ("이용권",),
    "이용권": ("쿠폰",),
}


def finding(priority: str, category: str, topic: str, message: str, recommendation: str) -> dict:
    return {
        "priority": priority,
        "category": category,
        "topic": topic,
        "message": message,
        "recommendation": recommendation,
    }


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_validation_report(report: Mapping[str, object], root: Path = DEFAULT_TOPIC_KNOWLEDGE_DIR) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "validation_report.json"
    md_path = root / "validation_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_markdown(report: Mapping[str, object]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# Topic Knowledge Validation Report",
        "",
        f"- 생성 시각: {report.get('generated_at', '')}",
        f"- 상태: {summary.get('status', '')}",
        f"- 주제 수: {report.get('actual_topic_count', 0)} / {report.get('expected_topic_count', 0)}",
        f"- P1/P2/P3: {summary.get('p1', 0)} / {summary.get('p2', 0)} / {summary.get('p3', 0)}",
        f"- 요구사항 연결 주제: {summary.get('topics_with_requirements', 0)}",
        f"- 첨부 참고자료 연결 주제: {summary.get('topics_with_primary_references', 0)}",
        f"- 공개웹 보조지식 연결 주제: {summary.get('topics_with_auxiliary_web', 0)}",
        "",
        "## Findings",
    ]
    findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
    if not findings:
        lines.append("- 발견된 P1/P2/P3 이슈가 없습니다.")
    for item in findings[:100]:
        if not isinstance(item, Mapping):
            continue
        lines.append(f"- [{item.get('priority')}] {item.get('topic')} / {item.get('category')}: {item.get('message')} {item.get('recommendation')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NC topic knowledge packs")
    parser.add_argument("--root", default=str(DEFAULT_TOPIC_KNOWLEDGE_DIR), help="Topic Knowledge Pack 폴더")
    args = parser.parse_args()
    root = Path(args.root)
    report = validate_topic_knowledge_dir(root)
    json_path, md_path = save_validation_report(report, root)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
