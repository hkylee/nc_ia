"""Independent Process Innovation Agent knowledge and checks.

The PI Agent is intentionally separate from Inspector/Health Check. It provides
one consistent PI lens that writers, reviewers, and manual Codex authoring can
reuse without changing the policy document template.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import tempfile
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence
import xml.etree.ElementTree as ET

try:
    from policy_references import extract_reference_text
    from runtime_paths import EVIDENCE_ROOT, INPUT_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .policy_references import extract_reference_text
    from .runtime_paths import EVIDENCE_ROOT, INPUT_ROOT


PI_GUIDE_ROOT = INPUT_ROOT / "PI guide"
PI_AGENT_KNOWLEDGE_PATH = EVIDENCE_ROOT / "pi_agent_knowledge.json"

PI_STAGES = [
    {
        "id": "PI-STAGE-01",
        "name": "As-Is 진단",
        "goal": "현행 프로세스를 정량·정성·구조 관점에서 확인하고 실제 병목과 원인을 고정한다.",
        "outputs": ["Baseline", "Pain Point Map", "BPMN 2.0 As-Is"],
        "guard": "현업 설명을 그대로 받아쓰지 말고 실제 거래 데이터와 고객/운영 로그로 검증한다.",
    },
    {
        "id": "PI-STAGE-02",
        "name": "To-Be 재설계",
        "goal": "First Principles로 필요한 단계만 남기고 보수·표준·혁신 시나리오를 비교한다.",
        "outputs": ["To-Be 후보", "AI/HITL 후보", "단계·분기·액터·시스템 호출 비교"],
        "guard": "단계 수가 줄지 않으면 PI가 아니다. 유지되는 모든 단계는 존재 이유를 설명해야 한다.",
    },
    {
        "id": "PI-STAGE-03",
        "name": "Gap 분석과 우선순위",
        "goal": "단계 수, 처리 시간, 시스템 영향, 현업 영향, 규제·정책 영향으로 실행 우선순위를 정한다.",
        "outputs": ["Quick Win/전략/점진/재검토 매트릭스", "영향도 분석"],
        "guard": "효과가 큰 개선과 실현 가능한 개선을 분리해 후속 실행 리스크를 낮춘다.",
    },
    {
        "id": "PI-STAGE-04",
        "name": "검증",
        "goal": "Walkthrough, Data Replay, Pilot으로 To-Be 흐름이 실제 업무에서 작동하는지 검증한다.",
        "outputs": ["사용자 검증 결과", "예외 시나리오 검증", "KPI 달성 가능성"],
        "guard": "핵심 사용자 동의, 예외 시나리오 처리, KPI 목표 달성 가능성을 함께 확인한다.",
    },
    {
        "id": "PI-STAGE-05",
        "name": "이행과 지속 개선",
        "goal": "KPI Dashboard, 변화관리, SLA/실패 시나리오를 운영 체계로 전환한다.",
        "outputs": ["KPI Dashboard", "Change Plan", "SLA/Failure Scenario", "3/6/12개월 회고"],
        "guard": "정책은 산출물 작성이 아니라 운영 개선 루프까지 연결되어야 완성된다.",
    },
]

PI_PRINCIPLES = [
    {"id": "PI-PR-01", "name": "Don’t pave the cow path", "rule": "기존 절차를 전산화하지 말고 왜 필요한지부터 다시 판단한다."},
    {"id": "PI-PR-02", "name": "Why부터 5단계까지", "rule": "각 단계는 5-Why 수준으로 존재 이유와 제거 가능성을 검토한다."},
    {"id": "PI-PR-03", "name": "Single Source of Truth", "rule": "동일 판단값과 기준 정보는 하나의 원천 기준으로 관리한다."},
    {"id": "PI-PR-04", "name": "단계 수 줄이기", "rule": "기본 목표는 단계 수 30% 이상 축소이며, 미축소 시 사유를 남긴다."},
    {"id": "PI-PR-05", "name": "정량+정성 근거", "rule": "데이터와 인터뷰를 함께 사용해 병목·불편·실패 원인을 확인한다."},
    {"id": "PI-PR-06", "name": "예외는 본문에", "rule": "실패·중단·취소·지연·권한 없음 같은 예외를 본문 흐름과 정책에 포함한다."},
    {"id": "PI-PR-07", "name": "측정 가능한 KPI", "rule": "KPI는 이름, 산식, 주기, Baseline, Target, Owner를 포함한다."},
]

PI_OUTPUT_SECTIONS = [
    "Process ID & classification",
    "As-Is model + baseline",
    "Pain point & root cause",
    "To-Be model + design rationale",
    "Business rules",
    "KPI definition",
    "Change impact analysis",
]

def pi_flow_item(
    rubric_id: str,
    question: str,
    markers: Sequence[str],
    *,
    target_location: str,
    suggestion: str,
    required_hits: int = 2,
    legacy_id: str = "",
) -> Dict[str, Any]:
    return {
        "id": f"PI-FLOW-{rubric_id}",
        "rubric_id": rubric_id,
        "question": question,
        "markers": tuple(markers),
        "target_location": target_location,
        "suggestion": suggestion,
        "required_hits": required_hits,
        "legacy_id": legacy_id,
    }


def pi_flow_section(order: int, name: str, items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {"id": f"PI-FLOW-S{order:02d}", "order": order, "name": name, "max_score": 10, "items": list(items)}


PI_FLOW_RUBRIC_SECTIONS = [
    pi_flow_section(
        1,
        "과제정의서 포괄성",
        [
            pi_flow_item("1-1", "과제정의서의 업무 목표·범위가 To-be Flow에 반영되어 있는가", ("과제", "목표", "범위", "To-Be", "Flow"), target_location="개요/범위/전체 업무 흐름도", suggestion="업무 목표와 범위가 To-Be Flow의 시작·종료·대상 업무에 연결되도록 보강한다.", legacy_id="PI-CHECK-03"),
            pi_flow_item("1-2", "과제정의서의 대상 업무·포함 범위가 To-be Flow에 누락 없이 반영되었는가", ("대상 업무", "포함 범위", "제외 범위", "업무 흐름", "누락"), target_location="개요/프로세스 목록", suggestion="대상 업무와 포함 범위를 프로세스 목록과 흐름도에 빠짐없이 매핑한다."),
            pi_flow_item("1-3", "과제정의서의 제약사항 및 전제조건이 Flow 설계에 고려되었는가", ("제약", "전제", "조건", "법", "보안", "정합성"), target_location="개요/정책 상세/상태 전이표", suggestion="제약사항과 전제조건을 상태·정책 판단 기준으로 명시한다."),
            pi_flow_item("1-4", "과제정의서 대비 추가·변경된 항목이 명확히 식별되어 있는가", ("추가", "변경", "차이", "Gap", "변경 이력"), target_location="문서 히스토리/Gap 설명/프로세스", suggestion="기존 과제 정의와 달라진 업무·흐름·정책을 변경 항목으로 식별한다."),
            pi_flow_item("1-5", "과제정의서에 명시된 이해관계자·액터가 Flow에 반영되어 있는가", ("이해관계자", "액터", "고객", "운영자", "시스템", "책임"), target_location="액터/유즈케이스/프로세스", suggestion="이해관계자와 액터의 책임이 유즈케이스와 프로세스에 연결되도록 보강한다."),
        ],
    ),
    pi_flow_section(
        2,
        "요구사항 명세 포괄성",
        [
            pi_flow_item("2-1", "기능 요구사항이 To-be Flow 각 단계에 빠짐없이 매핑되어 있는가", ("요구사항", "기능", "단계", "매핑", "trace"), target_location="요구사항 Trace/프로세스/기능 정의", suggestion="요구사항 ID별로 프로세스 단계와 기능 연결을 남긴다."),
            pi_flow_item("2-2", "In/Out 데이터 요건이 Flow의 입출력 설계에 반영되어 있는가", ("입력", "출력", "데이터", "조회", "저장", "결과"), target_location="기능 정의/정책 상세", suggestion="각 단계의 입력·출력 데이터와 결과 반영 기준을 기능 또는 정책으로 명시한다.", legacy_id="PI-CHECK-08"),
            pi_flow_item("2-3", "AI 요건이 Flow 내 적절한 처리 단계에 포함되어 있는가", ("AI", "추천", "분류", "자동", "모델", "처리 단계"), target_location="프로세스/기능 정의", suggestion="AI 요건을 별도 장식이 아니라 실제 처리 단계와 기능으로 연결한다.", legacy_id="PI-CHECK-05"),
            pi_flow_item("2-4", "비기능 요구사항(성능·보안·가용성 등)이 Flow 설계에 고려되었는가", ("성능", "보안", "가용성", "권한", "인증", "SLA"), target_location="정책 상세/최종 점검 기준", suggestion="성능·보안·가용성 요구를 고객 상태, 권한, 실패 대응 기준에 반영한다."),
            pi_flow_item("2-5", "요구사항 명세 대비 미반영 항목이 있다면 그 사유가 명확한가", ("미반영", "제외", "사유", "요구사항", "범위 밖"), target_location="요구사항 Trace/문서 히스토리", suggestion="미반영 또는 제외 요구사항은 사유와 후속 처리 기준을 남긴다."),
        ],
    ),
    pi_flow_section(
        3,
        "KPI 연계 설계",
        [
            pi_flow_item("3-1", "과제별 부여된 KPI 목표값이 Flow 설계에 명확히 반영되었는가", ("KPI", "목표", "지표", "완료율", "처리 시간", "오류율"), target_location="최종 점검 기준/운영 KPI 정책", suggestion="과제 KPI를 Flow 단계와 정책 판단 기준에 연결한다.", legacy_id="PI-CHECK-06"),
            pi_flow_item("3-2", "KPI 개선을 직접 유발하는 Flow 변경 포인트가 식별되어 있는가", ("KPI", "개선", "변경 포인트", "축소", "자동화", "셀프"), target_location="To-Be 흐름/프로세스", suggestion="KPI 개선을 만드는 단계 제거·통합·자동화 포인트를 명시한다.", legacy_id="PI-CHECK-01"),
            pi_flow_item("3-3", "KPI가 매출·비용 등 P&L 항목과 연결되는 경로로 추적 가능한가 (KPI-to-P&L 추적성)", ("매출", "비용", "P&L", "손익", "절감", "생산성"), target_location="성과 측정/운영 KPI 정책", suggestion="KPI가 비용 절감, 매출, 생산성, 고객경험 중 어떤 가치로 이어지는지 추적 경로를 보강한다."),
            pi_flow_item("3-4", "To-be Flow 설계로 예상되는 KPI 개선 효과가 정량적으로 추정되어 있는가", ("%", "건", "분", "시간", "감소", "증가", "Baseline", "Target"), target_location="성과 측정/Gap 분석", suggestion="개선 효과를 정성 표현이 아니라 기준값·목표값·예상 변화량으로 제시한다."),
            pi_flow_item("3-5", "KPI 달성을 위한 전제 조건, 측정 시점, 측정 주체가 정의되어 있는가", ("전제 조건", "측정", "시점", "주기", "Owner", "책임자"), target_location="운영 KPI 정책/최종 점검 기준", suggestion="KPI별 측정 시점, 주기, 책임자, 전제 조건을 함께 정의한다."),
        ],
    ),
    pi_flow_section(
        4,
        "KPI 달성 혁신성",
        [
            pi_flow_item("4-1", "단순 기능 이관이 아닌 업무 재설계(Re-design) 수준의 혁신이 포함되어 있는가", ("재설계", "Re-design", "혁신", "통합", "제거", "자동화"), target_location="프로세스 정의/To-Be 흐름", suggestion="기존 기능 이관을 넘어 제거·통합·자동화된 업무 재설계 지점을 명확히 한다.", legacy_id="PI-CHECK-01"),
            pi_flow_item("4-2", "KPI 목표값 달성에 충분한 수준의 업무 개선이 이루어졌는가", ("목표", "개선", "충분", "KPI", "효과", "달성"), target_location="성과 측정/프로세스", suggestion="KPI 목표 달성에 필요한 개선 강도와 범위를 설명한다."),
            pi_flow_item("4-3", "현재(As-is) 대비 명확한 혁신 Gap이 Flow에 구현되어 있는가", ("As-Is", "To-Be", "Gap", "현재", "대비", "차이"), target_location="As-Is/To-Be 비교/프로세스", suggestion="As-Is 대비 달라진 단계, 액터, 시스템 호출, 예외 처리 차이를 명시한다."),
            pi_flow_item("4-4", "혁신의 범위·깊이가 KPI 달성 목표에 비례하는가", ("범위", "깊이", "KPI", "목표", "우선순위", "영향도"), target_location="Gap 분석/우선순위", suggestion="혁신 범위와 KPI 영향도를 비교해 과소·과대 설계를 조정한다."),
            pi_flow_item("4-5", "타 과제 KPI 달성에도 긍정적 영향을 주는 시너지 설계가 있는가", ("타 과제", "시너지", "연계", "공통", "재사용", "확장"), target_location="영향도 분석/정책 상세", suggestion="공통 데이터, 공통 기능, 공통 정책이 다른 과제 KPI에 주는 영향을 남긴다."),
        ],
    ),
    pi_flow_section(
        5,
        "MNO Biz Value Driver 기여도",
        [
            pi_flow_item("5-1", "MNO 핵심 Value Driver(매출·비용·고객경험·생산성 등)와의 연관성이 명확한가", ("매출", "비용", "고객경험", "생산성", "Value Driver", "가치"), target_location="개요/성과 측정", suggestion="Flow 변화가 매출, 비용, 고객경험, 생산성 중 어떤 가치 동인에 기여하는지 명시한다."),
            pi_flow_item("5-2", "To-be Flow 변화가 특정 Value Driver를 어떻게 개선하는지 설명되어 있는가", ("To-Be", "변화", "개선", "가치", "기여", "효과"), target_location="To-Be 흐름/성과 측정", suggestion="각 Flow 변경이 어떤 Value Driver를 어떻게 개선하는지 설명한다."),
            pi_flow_item("5-3", "Value Driver 기여 효과의 규모(Impact)가 추정 가능한가", ("Impact", "영향도", "규모", "추정", "건", "%", "비용"), target_location="Gap 분석/성과 측정", suggestion="Value Driver별 예상 효과 규모를 정량 또는 등급으로 추정한다."),
            pi_flow_item("5-4", "단기·중기·장기 가치 실현 시점이 고려되어 있는가", ("단기", "중기", "장기", "시점", "로드맵", "Phase"), target_location="이행 계획/우선순위", suggestion="가치 실현 시점을 단계별 또는 우선순위별로 구분한다."),
            pi_flow_item("5-5", "복수 Value Driver에 기여하는 복합 효과가 고려되어 있는가", ("복수", "복합", "시너지", "매출", "비용", "고객경험"), target_location="성과 측정/영향도 분석", suggestion="여러 Value Driver에 동시에 영향을 주는 복합 효과를 정리한다."),
        ],
    ),
    pi_flow_section(
        6,
        "To-be Flow 완성도",
        [
            pi_flow_item("6-1", "Flow의 시작 조건과 종료 조건이 명확히 정의되어 있는가", ("시작 조건", "종료 조건", "완료", "개시", "결과"), target_location="프로세스 정의/상태 전이표", suggestion="Flow의 시작 조건, 종료 상태, 완료 결과를 명확히 정의한다.", legacy_id="PI-CHECK-02"),
            pi_flow_item("6-2", "각 단계별 액터(고객·직원·시스템)와 책임이 명확히 정의되어 있는가", ("액터", "고객", "운영자", "시스템", "책임", "단계"), target_location="액터/프로세스 정의", suggestion="단계별 수행 주체와 책임을 고객·운영자·시스템 기준으로 분리한다.", legacy_id="PI-CHECK-07"),
            pi_flow_item("6-3", "주요 분기 조건 및 예외 경로가 Flow에 포함되어 있는가", ("분기", "예외", "실패", "오류", "재시도", "복구"), target_location="상태 전이표/프로세스 예외 흐름", suggestion="분기 조건, 실패, 재시도, 복구, 상담 전환 경로를 본문 흐름에 포함한다.", legacy_id="PI-CHECK-04"),
            pi_flow_item("6-4", "시스템·채널 간 연계 포인트와 데이터 흐름이 명확한가", ("시스템", "채널", "연계", "데이터 흐름", "BSS", "결과 회신"), target_location="프로세스/기능 정의/BSS 연계 정책", suggestion="채널, BSS, 외부 시스템 간 연계 포인트와 데이터 흐름을 명시한다.", legacy_id="PI-CHECK-07"),
            pi_flow_item("6-5", "Flow 전체가 완결된 업무 단위로 구성되어 있는가", ("완결", "업무 단위", "종료", "결과", "후속"), target_location="유즈케이스/프로세스 정의", suggestion="고객 또는 운영자가 인식하는 완료 결과까지 하나의 업무 단위로 구성한다."),
        ],
    ),
    pi_flow_section(
        7,
        "혁신 실현 가능성",
        [
            pi_flow_item("7-1", "제안된 혁신이 현재 기술 수준에서 구현 가능한가", ("구현 가능", "기술", "가능", "시스템", "제약", "검토"), target_location="기능 정의/영향도 분석", suggestion="혁신 기능의 구현 가능성과 기술 제약을 명시한다."),
            pi_flow_item("7-2", "혁신 실현에 필요한 선행 조건(인프라·데이터·조직 등)이 식별되어 있는가", ("선행 조건", "인프라", "데이터", "조직", "권한", "준비"), target_location="이행 계획/정책 상세", suggestion="필요한 인프라, 데이터, 조직, 권한 선행 조건을 정리한다."),
            pi_flow_item("7-3", "구현 복잡도 대비 KPI 기여 효과가 합리적으로 균형 잡혀 있는가", ("복잡도", "KPI", "효과", "우선순위", "균형", "난이도"), target_location="Gap 분석/우선순위", suggestion="구현 난이도와 KPI 효과를 비교해 우선순위를 보정한다."),
            pi_flow_item("7-4", "혁신 실현 리스크 및 대응 방안이 고려되어 있는가", ("리스크", "대응", "장애", "실패", "Fallback", "완화"), target_location="상태 전이표/정책 상세", suggestion="실현 리스크와 장애·실패 대응 방안을 함께 남긴다."),
            pi_flow_item("7-5", "단계적 실현 계획(Phase) 또는 우선순위가 고려되어 있는가", ("Phase", "단계적", "우선순위", "로드맵", "1차", "2차"), target_location="이행 계획/문서 히스토리", suggestion="단계적 실현 계획과 후속 보완 우선순위를 구분한다."),
        ],
    ),
    pi_flow_section(
        8,
        "디지털·자동화 혁신",
        [
            pi_flow_item("8-1", "수작업·대면 처리를 디지털 셀프서비스로 전환하는 설계가 있는가", ("수작업", "대면", "셀프", "디지털", "앱", "웹"), target_location="To-Be 흐름/기능 정의", suggestion="수작업·대면 처리 감소와 셀프서비스 전환 범위를 명시한다.", legacy_id="PI-CHECK-01"),
            pi_flow_item("8-2", "반복 업무의 자동화 또는 배치 처리 설계가 포함되어 있는가", ("반복", "자동화", "배치", "스케줄", "일괄", "자동"), target_location="기능 정의/운영 정책", suggestion="반복 업무를 자동화하거나 배치 처리하는 기준을 정의한다."),
            pi_flow_item("8-3", "채널 통합을 통해 고객 접점이 단순화되는 설계인가", ("채널 통합", "접점", "단순화", "통합채널", "연속", "핸드오프"), target_location="개요/프로세스/채널 정책", suggestion="채널별 분절을 줄이고 통합채널에서 이어지는 고객 접점을 정의한다."),
            pi_flow_item("8-4", "업무 처리 속도·정확도 향상을 위한 시스템 자동화가 포함되어 있는가", ("처리 속도", "정확도", "자동화", "검증", "산정", "처리 시간"), target_location="기능 정의/성과 측정", suggestion="속도와 정확도를 높이는 자동 검증·산정·처리 기능을 연결한다."),
            pi_flow_item("8-5", "디지털 전환으로 인한 운영 비용 절감이 설계에 반영되어 있는가", ("운영 비용", "비용 절감", "효율", "생산성", "상담 감소"), target_location="성과 측정/운영 정책", suggestion="운영 비용 절감 효과와 측정 방식을 KPI로 연결한다."),
        ],
    ),
    pi_flow_section(
        9,
        "AI/데이터 혁신 활용",
        [
            pi_flow_item("9-1", "AI 요건이 단순 기능 추가가 아닌 업무 혁신의 핵심 요소로 설계되어 있는가", ("AI", "업무 혁신", "의사결정", "추천", "자동", "핵심"), target_location="프로세스/기능 정의", suggestion="AI를 기능명 언급이 아니라 업무 판단·추천·자동화의 핵심 단계로 설계한다.", legacy_id="PI-CHECK-05"),
            pi_flow_item("9-2", "AI 활용으로 의사결정 속도나 정확도가 개선되는 Flow인가", ("AI", "의사결정", "속도", "정확도", "추천", "판정"), target_location="To-Be 흐름/성과 측정", suggestion="AI가 의사결정 속도 또는 정확도에 미치는 개선 효과를 명시한다."),
            pi_flow_item("9-3", "AI 활용을 위한 데이터 입력·출력 설계가 명확한가", ("AI", "데이터", "입력", "출력", "학습", "피드백"), target_location="기능 정의/데이터 정책", suggestion="AI 입력 데이터, 출력 결과, 학습·피드백 기준을 정의한다."),
            pi_flow_item("9-4", "AI 결과의 신뢰도 관리 및 예외 처리 방안이 Flow에 포함되어 있는가", ("AI", "신뢰도", "예외", "HITL", "Fallback", "운영자 확인"), target_location="정책 상세/운영 전환 기준", suggestion="AI 신뢰도, HITL, Fallback, 운영자 확인 기준을 함께 정의한다.", legacy_id="PI-CHECK-05"),
            pi_flow_item("9-5", "AI 도입으로 기대되는 KPI 개선 효과가 Flow 수준에서 추적 가능한가", ("AI", "KPI", "개선", "추적", "효과", "측정"), target_location="성과 측정/AI 기능 정의", suggestion="AI 도입 효과를 KPI와 Flow 단계 단위로 추적 가능하게 만든다."),
        ],
    ),
    pi_flow_section(
        10,
        "CX 혁신 기여도",
        [
            pi_flow_item("10-1", "고객 관점에서 As-is 대비 처리 절차가 단순화되었는가", ("고객", "As-Is", "단순화", "절차", "축소", "셀프"), target_location="고객 여정/To-Be 흐름", suggestion="고객 관점의 절차 단순화와 단계 축소를 명확히 보여준다.", legacy_id="PI-CHECK-01"),
            pi_flow_item("10-2", "고객이 처리 상태·결과를 실시간으로 인지할 수 있는 설계인가", ("상태", "결과", "실시간", "안내", "알림", "진행"), target_location="상태 전이표/고지 정책", suggestion="처리 상태, 결과, 실패 사유를 고객이 인지할 수 있는 고지 기준으로 보강한다."),
            pi_flow_item("10-3", "고객의 실패·오류 경험을 줄이는 방향으로 Flow가 개선되었는가", ("실패", "오류", "재시도", "복구", "고객", "개선"), target_location="예외 흐름/정책 상세", suggestion="고객 실패·오류 경험을 줄이는 복구, 재시도, 대체 행동 기준을 정의한다.", legacy_id="PI-CHECK-04"),
            pi_flow_item("10-4", "고객 처리 완료 시간(TAT)이 단축되는 설계인가", ("TAT", "완료 시간", "처리 시간", "단축", "즉시", "시간"), target_location="성과 측정/프로세스", suggestion="고객 처리 완료 시간 단축 효과와 측정 기준을 명시한다."),
            pi_flow_item("10-5", "고객이 앱/웹에서 직접 완료할 수 있는 업무 범위가 확대되었는가", ("앱", "웹", "직접 완료", "셀프", "업무 범위", "완결"), target_location="개요/기능 정의/프로세스", suggestion="앱/웹 셀프 완결 업무 범위와 제외되는 업무를 구분한다."),
        ],
    ),
]


def build_pi_checklist() -> List[Dict[str, Any]]:
    checklist: List[Dict[str, Any]] = []
    for section in PI_FLOW_RUBRIC_SECTIONS:
        for item in section["items"]:
            item_id = str(item["id"])
            checklist.append(
                {
                    "id": item_id,
                    "rubric_id": item.get("rubric_id", ""),
                    "section_id": section["id"],
                    "section_order": section["order"],
                    "section_name": section["name"],
                    "question": item["question"],
                    "focus": section["name"],
                    "detail": f"{section['name']} 관점에서 {item['question']}",
                    "pass_criteria": item["question"],
                    "legacy_id": item.get("legacy_id", ""),
                    "required_hits": item.get("required_hits", 2),
                }
            )
    return checklist


PI_CHECKLIST = build_pi_checklist()

PI_ANTI_PATTERNS = [
    {
        "id": "PI-ANTI-01",
        "name": "As-Is 복사",
        "rule": "기존 흐름을 거의 그대로 옮기고 단순 명칭만 바꾸는 방식",
        "risk": "통합채널 전환 후에도 단계 수, 상담 의존, 운영 수작업이 줄지 않는다.",
    },
    {
        "id": "PI-ANTI-02",
        "name": "현업 받아쓰기",
        "rule": "근거 검증 없이 요청 문구와 현재 운영 방식을 정책으로 확정하는 방식",
        "risk": "요구사항 문구는 남지만 정책 판단 기준과 예외 기준이 비어 개발·QA가 다시 해석해야 한다.",
    },
    {
        "id": "PI-ANTI-03",
        "name": "AI 끼워넣기",
        "rule": "입력·출력·신뢰도·HITL·Fallback 없이 AI만 언급하는 방식",
        "risk": "AI 적용 범위가 불명확해 자동화 리스크와 상담 전환 기준이 통제되지 않는다.",
    },
    {
        "id": "PI-ANTI-04",
        "name": "예외 각주화",
        "rule": "예외와 실패를 본문 흐름이 아니라 별첨·후속 검토로 밀어내는 방식",
        "risk": "실패·중단·권한 없음·데이터 없음 상황에서 고객과 운영자가 다음 행동을 알 수 없다.",
    },
    {
        "id": "PI-ANTI-05",
        "name": "KPI 부재",
        "rule": "개선 효과를 측정할 수 있는 지표와 운영 주기가 없는 방식",
        "risk": "개선 여부를 판단할 수 없어 운영 품질과 비용 절감 효과를 사후에 검증하기 어렵다.",
    },
]

PI_GATEKEEPER_DIMENSIONS = [
    {
        "id": "PI-GK-01",
        "name": "체크 기준 완전성",
        "description": "PI Check 결과가 10개 섹션·50개 검증 항목을 모두 포함하고 각 항목의 상태를 명확히 산정했는지 확인한다.",
    },
    {
        "id": "PI-GK-02",
        "name": "근거 설명성",
        "description": "각 체크 항목에 왜 PASS/PARTIAL/FAIL인지 판단할 수 있는 근거 문장이 있는지 확인한다.",
    },
    {
        "id": "PI-GK-03",
        "name": "보완 실행성",
        "description": "PARTIAL/FAIL 항목과 안티패턴이 실행 가능한 보완 항목으로 이어지는지 확인한다.",
    },
    {
        "id": "PI-GK-04",
        "name": "안티패턴 정합성",
        "description": "감지된 안티패턴 수와 사유가 결과 요약 및 보완 항목과 일치하는지 확인한다.",
    },
    {
        "id": "PI-GK-05",
        "name": "비교 결과 정합성",
        "description": "As-Is/To-Be 비교가 있는 경우 점수 차이, 개선/후퇴 항목, 안티패턴 증감이 일관적인지 확인한다.",
    },
]

def build_pi_check_target_locations() -> Dict[str, str]:
    targets: Dict[str, str] = {}
    for section in PI_FLOW_RUBRIC_SECTIONS:
        for item in section["items"]:
            targets[str(item["id"])] = str(item.get("target_location", "To-Be Flow/정책서 본문"))
    return targets


def build_pi_check_method_guide() -> Dict[str, Dict[str, Any]]:
    guide: Dict[str, Dict[str, Any]] = {}
    for section in PI_FLOW_RUBRIC_SECTIONS:
        section_name = str(section["name"])
        for item in section["items"]:
            markers = tuple(str(marker) for marker in item.get("markers", ()) if marker)
            item_id = str(item["id"])
            guide[item_id] = {
                "inspection_item": f"{item.get('rubric_id')} {item.get('question')}",
                "method": (
                    f"{section_name} 관점에서 업로드 문서의 산출물 위치, 판단 근거, 정량/정성 신호를 확인한다. "
                    f"주요 확인 신호: {', '.join(markers[:8])}."
                ),
                "markers": markers,
                "required_hits": item.get("required_hits", 2),
                "suggestion": item.get("suggestion", ""),
            }
    return guide


PI_CHECK_TARGET_LOCATIONS = build_pi_check_target_locations()

PI_CORE_CHECK_IDS = {
    "PI-FLOW-1-2",
    "PI-FLOW-2-1",
    "PI-FLOW-3-2",
    "PI-FLOW-4-1",
    "PI-FLOW-5-1",
    "PI-FLOW-7-1",
    "PI-FLOW-9-1",
}

PI_INSPECTION_METHODS = [
    {
        "id": "PI-METHOD-01",
        "name": "문서 정규화 기반 검수",
        "description": "HTML, PPTX, DOCX, PDF, BPMN, Markdown, Text, JSON을 공통 분석 텍스트로 변환한 뒤 동일한 PI 기준으로 평가한다.",
    },
    {
        "id": "PI-METHOD-02",
        "name": "신호 기반 PASS/PARTIAL/FAIL 판정",
        "description": "각 검수 항목별 필수 신호와 부분 신호를 분리해 PASS, PARTIAL, FAIL을 산정한다.",
    },
    {
        "id": "PI-METHOD-03",
        "name": "안티패턴 병행 탐지",
        "description": "As-Is 복사, 현업 받아쓰기, AI 끼워넣기, 예외 각주화, KPI 부재를 별도 규칙으로 감지한다.",
    },
    {
        "id": "PI-METHOD-04",
        "name": "As-Is/To-Be 비교 검수",
        "description": "As-Is 문서가 있으면 체크 항목별 상태 변화, 점수 차이, 안티패턴 증감을 함께 비교한다.",
    },
    {
        "id": "PI-METHOD-05",
        "name": "GateKeeper 재검수",
        "description": "PI Check 결과 자체가 검수 항목, 판단 근거, 보완 실행 항목, 비교 정합성을 갖췄는지 다시 판정한다.",
    },
]

PI_CHECK_METHOD_GUIDE = build_pi_check_method_guide()


def pi_checklist_with_methods() -> List[Dict[str, Any]]:
    checklist: List[Dict[str, Any]] = []
    for item in PI_CHECKLIST:
        item_id = str(item.get("id", ""))
        guide = PI_CHECK_METHOD_GUIDE.get(item_id, {})
        checklist.append(
            {
                **item,
                "inspection_item": guide.get("inspection_item", item.get("focus", "")),
                "inspection_method": guide.get("method", ""),
                "target_location": PI_CHECK_TARGET_LOCATIONS.get(item_id, ""),
            }
        )
    return checklist

PI_STAGE_CONTEXT = {
    "overview": {
        "focus": ["이 정책서가 제거하려는 현행 병목", "고객 과업 완료 관점의 To-Be 방향", "포함/제외 범위와 책임 경계"],
        "questions": ["기존 절차를 왜 그대로 유지하면 안 되는가?", "어떤 중복·수작업·상담 의존을 줄이는가?"],
    },
    "usecases": {
        "focus": ["고객이 완료하려는 상위 업무 목적", "운영자·시스템 보조 처리와 고객 과업 분리", "불필요하게 쪼갠 절차성 유즈케이스 제거"],
        "questions": ["이 유즈케이스는 고객/운영자의 완료 목적 단위인가?", "단순 조회·저장·검증을 독립 유즈케이스로 올리지 않았는가?"],
    },
    "state": {
        "focus": ["정상·실패·대기·제한·복구 상태", "교착 없는 종료 조건", "고객 표시 상태와 내부 처리 상태의 구분"],
        "questions": ["실패·보류 상태에서도 다음 행동이 정해져 있는가?", "상태가 정책 판단이나 기능 허용을 실제로 바꾸는가?"],
    },
    "process": {
        "focus": ["단계 수 축소", "중복 입력·인증·확인 제거", "예외를 본문 흐름에 포함", "AI/자동화와 HITL 경계"],
        "questions": ["이 단계를 제거하면 어떤 위험이 생기는가?", "같은 판단을 두 번 하지 않는가?", "예외가 별첨으로 밀려나지 않았는가?"],
    },
    "functions": {
        "focus": ["프로세스를 수행하는 처리 역량", "단일 기준 정보", "자동화 가능 처리와 수동 조정 경계", "데이터 입출력"],
        "questions": ["이 기능은 어떤 프로세스 단계를 줄이거나 안정화하는가?", "판단값의 원천 데이터가 하나로 관리되는가?"],
    },
    "policies": {
        "focus": ["업무 규칙", "가능/불가/제한 조건", "예외·고지·이력", "KPI와 운영 모니터링 기준"],
        "questions": ["사람이 매번 판단하지 않게 할 기준값이 있는가?", "제한·복구·Fallback 조건이 실제 실행 가능하게 적혔는가?"],
    },
    "final_check": {
        "focus": ["10개 섹션·50개 PI 체크리스트", "5개 안티패턴", "요구사항-프로세스-기능-정책 연결", "운영 KPI"],
        "questions": ["As-Is 복사나 현업 받아쓰기가 남아 있지 않은가?", "개선 효과를 측정할 수 있는가?"],
    },
}


def build_pi_agent_knowledge(source_root: Path = PI_GUIDE_ROOT) -> Dict[str, Any]:
    """Build a structured PI knowledge pack from the PI guide folder."""
    source_files = source_file_snapshots(source_root)
    return {
        "agent": "PI Agent",
        "version": "1.0",
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        "source_files": source_files,
        "role": "정책서 작성 전후에 프로세스 혁신 관점의 병목 제거, To-Be 재설계, KPI, 예외 본문화를 독립적으로 점검한다.",
        "scope_boundary": [
            "PI Agent는 정책서 템플릿과 샘플 구조를 바꾸지 않는다.",
            "PI Guide는 작성 품질과 프로세스 혁신 관점의 보조 근거이며, 요구사항·첨부자료와 충돌하면 요구사항·첨부자료를 우선한다.",
            "PI 산출물 양식을 정책서 본문에 그대로 강제하지 않고, 정책서 장 구조 안에서 핵심 판단축만 반영한다.",
        ],
        "stages": PI_STAGES,
        "principles": PI_PRINCIPLES,
        "output_sections": PI_OUTPUT_SECTIONS,
        "checklist": pi_checklist_with_methods(),
        "inspection_methods": PI_INSPECTION_METHODS,
        "gatekeeper_dimensions": PI_GATEKEEPER_DIMENSIONS,
        "anti_patterns": PI_ANTI_PATTERNS,
        "stage_context": PI_STAGE_CONTEXT,
        "writer_contract": [
            "각 프로세스 단계는 고객 가치, 법·정책 준수, 보안, 운영 효율, 데이터 정합성 중 하나로 존재 이유를 설명할 수 있어야 한다.",
            "중복 입력, 중복 인증, 반복 확인, 상담 의존, 운영자 수작업은 줄이거나 줄이지 못하는 사유를 정책으로 남긴다.",
            "예외·실패·지연·권한 없음·데이터 없음은 각주나 후속 과제가 아니라 상태·프로세스·정책 본문에 포함한다.",
            "AI/자동화는 입력, 출력, 신뢰도, HITL, 대체 경로가 함께 정의될 때만 정책 판단축으로 사용한다.",
        ],
        "inspector_contract": [
            "As-Is 복사, 현업 받아쓰기, AI 끼워넣기, 예외 각주화, KPI 부재를 발견하면 PI finding으로 기록한다.",
            "단순히 'PI 관점 부족'이라고 쓰지 말고 어느 프로세스·기능·정책에 어떤 기준을 추가/변경해야 하는지 지정한다.",
            "정책서 범위를 벗어난 별도 PI 산출물 작성을 요구하지 않는다.",
        ],
    }


def source_file_snapshots(source_root: Path = PI_GUIDE_ROOT) -> List[Dict[str, Any]]:
    if not source_root.exists():
        return []
    snapshots: List[Dict[str, Any]] = []
    for path in sorted(source_root.iterdir()):
        if path.name.startswith(".") or path.name.startswith("~$") or not path.is_file():
            continue
        if path.suffix.lower() not in {".docx", ".xlsx", ".xlsm", ".pdf", ".md", ".txt", ".html"}:
            continue
        text = extract_reference_text(path, ())
        snapshots.append(
            {
                "name": path.name,
                "path": str(path),
                "suffix": path.suffix.lower(),
                "size": path.stat().st_size,
                "extracted_chars": len(text),
                "preview": compact_text(text, 360),
            }
        )
    return snapshots


def save_pi_agent_knowledge(path: Path = PI_AGENT_KNOWLEDGE_PATH, source_root: Path = PI_GUIDE_ROOT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_pi_agent_knowledge(source_root)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_pi_agent_knowledge(path: Path = PI_AGENT_KNOWLEDGE_PATH) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return build_pi_agent_knowledge()


def pi_context_for_stage(stage: str) -> Dict[str, Any]:
    """Return compact PI guidance for one authoring or inspection stage."""
    normalized_stage = normalize_stage(stage)
    knowledge = load_pi_agent_knowledge()
    stage_context = knowledge.get("stage_context", {}) if isinstance(knowledge.get("stage_context"), Mapping) else {}
    context = stage_context.get(normalized_stage) or stage_context.get("final_check") or {}
    return {
        "agent": "PI Agent",
        "stage": normalized_stage,
        "role": knowledge.get("role", ""),
        "scope_boundary": knowledge.get("scope_boundary", [])[:3],
        "focus": context.get("focus", []) if isinstance(context, Mapping) else [],
        "questions": context.get("questions", []) if isinstance(context, Mapping) else [],
        "principles": [
            {"id": item.get("id"), "name": item.get("name"), "rule": item.get("rule")}
            for item in knowledge.get("principles", [])[:7]
            if isinstance(item, Mapping)
        ],
        "anti_patterns": [
            {"id": item.get("id"), "name": item.get("name")}
            for item in knowledge.get("anti_patterns", [])[:5]
            if isinstance(item, Mapping)
        ],
    }


def evaluate_pi_document_quality(document: str, *, topic: str = "") -> Dict[str, Any]:
    """Run deterministic PI checks over a policy HTML/spec text.

    This is a lightweight signal, not a replacement for Inspector or Health Check.
    """
    text = compact_text(strip_markup(str(document or "")), 120000)
    normalized = re.sub(r"\s+", " ", text)
    checks = [evaluate_pi_flow_check(item, normalized) for item in PI_CHECKLIST]
    legacy_checks = evaluate_legacy_pi_checks(normalized)
    anti_patterns = detect_pi_anti_patterns(normalized)
    yes_count = sum(1 for item in checks if item["status"] == "yes")
    partial_count = sum(1 for item in checks if item["status"] == "partial")
    return {
        "agent": "PI Agent",
        "topic": topic,
        "yes_count": yes_count,
        "partial_count": partial_count,
        "no_count": len(checks) - yes_count - partial_count,
        "anti_pattern_count": len(anti_patterns),
        "checks": checks,
        "legacy_checks": legacy_checks,
        "anti_patterns": anti_patterns,
        "recommendations": pi_recommendations(checks, anti_patterns),
    }


def evaluate_pi_flow_check(item: Mapping[str, Any], text: str) -> Dict[str, Any]:
    item_id = str(item.get("id", ""))
    guide = PI_CHECK_METHOD_GUIDE.get(item_id, {})
    markers = tuple(str(marker) for marker in guide.get("markers", ()) if marker)
    required_hits = max(1, int(guide.get("required_hits") or item.get("required_hits") or 2))
    hits = marker_hit_count(text, markers)
    passed = hits >= required_hits
    partial = hits > 0

    if item_id.startswith("PI-FLOW-3-"):
        kpi_count = count_kpi_terms(text)
        numeric = has_quantitative_signal(text)
        passed = kpi_count >= 3 and hits >= 2 and (numeric or item_id in {"PI-FLOW-3-1", "PI-FLOW-3-2"})
        partial = kpi_count >= 1 or hits > 0
    elif item_id in {"PI-FLOW-6-3", "PI-FLOW-10-3"}:
        failures = count_failure_axes(text)
        passed = failures >= 5
        partial = failures >= 3 or hits > 0
    elif item_id in {"PI-FLOW-9-1", "PI-FLOW-9-2", "PI-FLOW-9-3", "PI-FLOW-9-4", "PI-FLOW-9-5"}:
        if "AI" not in text and "자동화" not in text:
            passed = False
            partial = False
        elif item_id == "PI-FLOW-9-4":
            passed = has_ai_hitl_boundary(text)
            partial = has_any(text, ("AI", "신뢰도", "HITL", "Fallback", "운영자", "예외"))
        else:
            passed = hits >= required_hits
            partial = hits > 0
    elif item_id in {"PI-FLOW-4-1", "PI-FLOW-8-1", "PI-FLOW-10-1"}:
        passed = has_stage_reduction_signal(text) or hits >= required_hits
        partial = has_any(text, ("단계", "프로세스", "간소", "통합", "셀프", "자동화")) or hits > 0

    suggestion = str(guide.get("suggestion") or item.get("suggestion") or "검수 항목의 판단 근거와 보완 기준을 문서 본문에 명시한다.")
    return pi_check(item_id, passed, partial, suggestion, text=text)


def evaluate_legacy_pi_checks(text: str) -> List[Dict[str, str]]:
    legacy_items = [
        ("PI-CHECK-01", has_stage_reduction_signal(text), has_any(text, ("단계", "프로세스", "간소", "통합")), "단계 축소 또는 미축소 사유"),
        ("PI-CHECK-02", has_any(text, ("근거", "사유", "목적", "판단 기준", "왜")), has_any(text, ("프로세스", "단계", "정책")), "단계별 존재 이유"),
        ("PI-CHECK-03", has_pain_point_evidence(text), has_any(text, ("불편", "병목", "실패", "이탈", "지연")), "Pain Point 근거"),
        ("PI-CHECK-04", count_failure_axes(text) >= 5, count_failure_axes(text) >= 3, "예외·실패 본문화"),
        ("PI-CHECK-05", has_ai_hitl_boundary(text), ("AI" not in text and "자동화" not in text) or has_any(text, ("운영자", "상담", "수동", "대체")), "AI/자동화와 HITL 경계"),
        ("PI-CHECK-06", count_kpi_terms(text) >= 3, count_kpi_terms(text) >= 1, "KPI 측정 가능성"),
        ("PI-CHECK-07", has_any(text, ("BSS", "FO", "외부 시스템", "연계 시스템", "책임 경계", "영향")), has_any(text, ("시스템", "연계", "프로세스")), "영향 시스템과 책임 경계"),
        ("PI-CHECK-08", has_any(text, ("Single Source", "SSOT", "단일 원천", "기준 정보", "마스터", "원장")), has_any(text, ("중복", "기준", "원천", "마스터")), "Single Source of Truth"),
        ("PI-CHECK-09", has_any(text, ("Walkthrough", "Pilot", "Data Replay", "사용자 검증", "운영 검증", "QA", "검수")), has_any(text, ("검증", "테스트", "점검")), "검증 가능성"),
    ]
    return [
        {"id": item_id, "status": "yes" if passed else "partial" if partial else "no", "name": name}
        for item_id, passed, partial, name in legacy_items
    ]


def marker_hit_count(text: str, markers: Sequence[str]) -> int:
    normalized = str(text or "")
    return sum(1 for marker in unique_texts(markers) if marker and marker in normalized)


def has_quantitative_signal(text: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|건|회|분|초|시간|일|원|명|개월|점)", str(text or "")))


def normalize_pi_check_document(document: str | bytes, *, file_name: str = "") -> Dict[str, Any]:
    """Convert an uploaded document into a stable JSON shape before PI checks.

    The uploaded original is never persisted. This derived JSON is only used as
    an analysis view so PI checks can reason over headings, tables, and text
    consistently instead of scanning raw HTML markup.
    """
    suffix = Path(str(file_name or "")).suffix.lower()
    if isinstance(document, (bytes, bytearray)):
        raw_bytes = bytes(document)
        if suffix in {".docx", ".pptx", ".pdf"}:
            text = extract_binary_upload_text(raw_bytes, suffix)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return {
                "kind": suffix.lstrip("."),
                "file_name": file_name,
                "headings": [],
                "paragraphs": lines,
                "tables": [],
                "text": compact_text("\n".join(lines), 120000),
                "metrics": {
                    "source_bytes": len(raw_bytes),
                    "text_chars": len(text),
                    "heading_count": 0,
                    "paragraph_count": len(lines),
                    "table_count": 0,
                },
            }
        raw = decode_upload_text(raw_bytes)
    else:
        raw = str(document or "")
    if suffix == ".json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw_text": raw}
        text = compact_text(flatten_json_text(payload), 120000)
        return {
            "kind": "json",
            "file_name": file_name,
            "headings": [],
            "paragraphs": [],
            "tables": [],
            "text": text,
            "metrics": {
                "source_chars": len(raw),
                "text_chars": len(text),
                "heading_count": 0,
                "table_count": 0,
            },
        }
    if suffix == ".bpmn" or raw.lstrip().startswith("<?xml"):
        extracted = extract_xml_text_with_attributes(raw)
        lines = [line.strip() for line in extracted.splitlines() if line.strip()]
        return {
            "kind": "bpmn" if suffix == ".bpmn" else "xml",
            "file_name": file_name,
            "headings": [],
            "paragraphs": lines,
            "tables": [],
            "text": compact_text("\n".join(lines), 120000),
            "metrics": {
                "source_chars": len(raw),
                "text_chars": len(extracted),
                "heading_count": 0,
                "paragraph_count": len(lines),
                "table_count": 0,
            },
        }
    if suffix in {".html", ".htm"} or "<html" in raw.casefold() or "<table" in raw.casefold():
        parser = PIHtmlStructureParser()
        parser.feed(raw)
        normalized = parser.to_payload(file_name=file_name)
        normalized["text"] = compact_text(normalized.get("text", ""), 120000)
        normalized["metrics"]["source_chars"] = len(raw)
        normalized["metrics"]["text_chars"] = len(normalized["text"])
        return normalized
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    headings = [line.lstrip("# ").strip() for line in lines if line.startswith("#")]
    text = compact_text("\n".join(lines), 120000)
    return {
        "kind": "text",
        "file_name": file_name,
        "headings": headings,
        "paragraphs": lines,
        "tables": [],
        "text": text,
        "metrics": {
            "source_chars": len(raw),
            "text_chars": len(text),
            "heading_count": len(headings),
            "table_count": 0,
        },
    }


def decode_upload_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def extract_binary_upload_text(raw_bytes: bytes, suffix: str) -> str:
    if suffix == ".pptx":
        return extract_pptx_text(raw_bytes)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(raw_bytes)
        temp_path = Path(handle.name)
    try:
        return extract_reference_text(temp_path, ())
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def extract_pptx_text(raw_bytes: bytes) -> str:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile:
        return ""
    lines: List[str] = []
    xml_names = [
        name
        for name in archive.namelist()
        if (name.startswith("ppt/slides/slide") or name.startswith("ppt/notesSlides/notesSlide")) and name.endswith(".xml")
    ]
    for name in sorted(xml_names, key=natural_sort_key):
        try:
            root = ET.fromstring(archive.read(name))
        except (KeyError, ET.ParseError):
            continue
        slide_lines = [node.text.strip() for node in root.iter() if node.tag.endswith("}t") and node.text and node.text.strip()]
        if slide_lines:
            lines.append(f"[{Path(name).stem}]")
            lines.extend(slide_lines)
    return "\n".join(lines)


def natural_sort_key(value: str) -> List[object]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def extract_xml_text_with_attributes(raw_xml: str) -> str:
    try:
        root = ET.fromstring(raw_xml.encode("utf-8"))
    except ET.ParseError:
        return strip_markup(raw_xml)
    lines: List[str] = []
    for node in root.iter():
        tag = node.tag.split("}", 1)[-1] if "}" in node.tag else node.tag
        attrs = []
        for key in ("id", "name", "sourceRef", "targetRef", "bpmnElement"):
            value = node.attrib.get(key)
            if value:
                attrs.append(f"{key}={value}")
        text = (node.text or "").strip()
        if attrs or text:
            lines.append(" ".join([tag, *attrs, text]).strip())
    return "\n".join(lines)


def pi_check_analysis_text(normalized_document: Mapping[str, Any]) -> str:
    """Create compact analysis text from normalized PI document JSON."""
    headings = normalized_document.get("headings", [])
    paragraphs = normalized_document.get("paragraphs", [])
    tables = normalized_document.get("tables", [])
    lines: List[str] = []
    if headings:
        lines.append("[HEADINGS]")
        lines.extend(str(item) for item in headings[:80])
    if paragraphs:
        lines.append("[PARAGRAPHS]")
        lines.extend(str(item) for item in paragraphs[:500])
    if tables:
        lines.append("[TABLES]")
        for table_index, table in enumerate(tables[:30], start=1):
            rows = table.get("rows", []) if isinstance(table, Mapping) else []
            lines.append(f"TABLE {table_index}")
            for row in rows[:80]:
                if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
                    lines.append(" | ".join(str(cell) for cell in row[:12]))
    if not lines:
        lines.append(str(normalized_document.get("text", "")))
    return compact_text("\n".join(lines), 120000)


class PIHtmlStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture_stack: List[Dict[str, Any]] = []
        self.headings: List[str] = []
        self.paragraphs: List[str] = []
        self.tables: List[Dict[str, Any]] = []
        self.current_table: List[List[str]] | None = None
        self.current_row: List[str] | None = None

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized == "table":
            self.current_table = []
        if normalized == "tr":
            self.current_row = []
        if normalized in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "th", "td"}:
            self.capture_stack.append({"tag": normalized, "parts": []})

    def handle_data(self, data: str) -> None:
        if not data or not self.capture_stack:
            return
        for capture in self.capture_stack:
            capture["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "th", "td"}:
            capture = self.pop_capture(normalized)
            if capture:
                text = compact_text(" ".join(capture.get("parts", [])), 1200)
                if text:
                    if normalized.startswith("h"):
                        self.headings.append(text)
                    elif normalized in {"p", "li"}:
                        self.paragraphs.append(text)
                    elif normalized in {"th", "td"} and self.current_row is not None:
                        self.current_row.append(text)
        if normalized == "tr" and self.current_table is not None and self.current_row:
            self.current_table.append(self.current_row)
            self.current_row = None
        if normalized == "table" and self.current_table is not None:
            self.tables.append({"rows": self.current_table[:120]})
            self.current_table = None

    def pop_capture(self, tag: str) -> Dict[str, Any] | None:
        for index in range(len(self.capture_stack) - 1, -1, -1):
            if self.capture_stack[index].get("tag") == tag:
                return self.capture_stack.pop(index)
        return None

    def to_payload(self, *, file_name: str = "") -> Dict[str, Any]:
        table_texts = []
        for table in self.tables[:30]:
            rows = table.get("rows", [])
            table_texts.extend(" | ".join(row[:12]) for row in rows[:80])
        text = "\n".join([*self.headings, *self.paragraphs, *table_texts])
        return {
            "kind": "html",
            "file_name": file_name,
            "headings": self.headings[:120],
            "paragraphs": self.paragraphs[:800],
            "tables": self.tables[:40],
            "text": text,
            "metrics": {
                "heading_count": len(self.headings),
                "paragraph_count": len(self.paragraphs),
                "table_count": len(self.tables),
            },
        }


def flatten_json_text(value: Any) -> str:
    parts: List[str] = []

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                walk(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
            return
        if node is None:
            return
        text = str(node).strip()
        if text:
            parts.append(f"{path}: {text}" if path else text)

    walk(value)
    return "\n".join(parts)


def detect_pi_anti_patterns(text: str) -> List[Dict[str, str]]:
    detected: List[Dict[str, str]] = []
    if text.count("기존") >= 4 and not has_any(text, ("제거", "축소", "간소", "자동화", "통합 기준")):
        detected.append({"id": "PI-ANTI-01", "name": "As-Is 복사", "reason": "기존 흐름 언급은 많지만 제거·축소·통합 기준이 약합니다."})
    if has_any(text, ("현업 요청", "현업 기준", "관련 부서 확인")) and not has_any(text, ("근거", "데이터", "요구사항", "VOC")):
        detected.append({"id": "PI-ANTI-02", "name": "현업 받아쓰기", "reason": "현업 기준을 검증 근거 없이 확정하는 표현이 있습니다."})
    if "AI" in text and not has_any(text, ("신뢰도", "HITL", "운영자 확인", "Fallback", "대체 경로", "상담 전환")):
        detected.append({"id": "PI-ANTI-03", "name": "AI 끼워넣기", "reason": "AI 언급은 있으나 신뢰도·HITL·Fallback 경계가 약합니다."})
    if has_any(text, ("예외는 별도", "별첨", "후속 검토")) and has_any(text, ("실패", "예외", "오류", "복구")):
        detected.append({"id": "PI-ANTI-04", "name": "예외 각주화", "reason": "예외/실패 처리가 본문 정책이 아니라 후속 검토로 밀려 있습니다."})
    if count_kpi_terms(text) == 0:
        detected.append({"id": "PI-ANTI-05", "name": "KPI 부재", "reason": "개선 효과를 측정할 KPI 표현이 확인되지 않습니다."})
    return detected


def pi_recommendations(checks: Sequence[Mapping[str, str]], anti_patterns: Sequence[Mapping[str, str]]) -> List[str]:
    recommendations = [
        str(item.get("suggestion", ""))
        for item in checks
        if str(item.get("status", "")).lower() != "yes" and item.get("suggestion")
    ]
    recommendations.extend(str(item.get("reason", "")) for item in anti_patterns if item.get("reason"))
    return [item for item in unique_texts(recommendations)[:8] if item]


def pi_check(item_id: str, passed: bool, partial: bool, suggestion: str, *, text: str = "") -> Dict[str, Any]:
    checklist_item = next((item for item in PI_CHECKLIST if item["id"] == item_id), {"question": item_id})
    guide = PI_CHECK_METHOD_GUIDE.get(item_id, {})
    status = "yes" if passed else "partial" if partial else "no"
    evidence = pi_evidence_for_check(text, item_id)
    return {
        "id": item_id,
        "rubricId": checklist_item.get("rubric_id", ""),
        "sectionId": checklist_item.get("section_id", ""),
        "sectionOrder": checklist_item.get("section_order", ""),
        "sectionName": checklist_item.get("section_name", ""),
        "question": checklist_item.get("question", item_id),
        "status": status,
        "focus": checklist_item.get("focus", ""),
        "detail": checklist_item.get("detail", ""),
        "passCriteria": checklist_item.get("pass_criteria", ""),
        "inspectionItem": guide.get("inspection_item", checklist_item.get("focus", "")),
        "inspectionMethod": guide.get("method", ""),
        "targetLocation": PI_CHECK_TARGET_LOCATIONS.get(item_id, ""),
        "statusReason": pi_status_reason(status, item_id, bool(evidence)),
        "evidence": evidence,
        "suggestion": suggestion,
    }


def pi_status_reason(status: str, item_id: str, has_evidence: bool) -> str:
    guide = PI_CHECK_METHOD_GUIDE.get(item_id, {})
    item_name = str(guide.get("inspection_item", item_id))
    if status == "yes":
        return f"{item_name} 검수 기준을 충족하는 신호가 확인되었습니다."
    if status == "partial":
        return f"{item_name} 관련 일부 신호는 있으나 PASS 기준 전체를 충족하려면 판단 기준과 근거를 더 명확히 해야 합니다."
    if has_evidence:
        return f"{item_name} 관련 표현은 있으나 PASS 기준으로 인정할 만큼 충분한 근거가 확인되지 않습니다."
    return f"{item_name} 검수 기준을 뒷받침하는 문장이나 수치가 확인되지 않습니다."


def pi_evidence_for_check(text: str, item_id: str) -> List[str]:
    markers = PI_CHECK_METHOD_GUIDE.get(item_id, {}).get("markers", ())
    return evidence_snippets(text, markers, limit=3)


def evidence_snippets(text: str, markers: Sequence[str], *, limit: int = 3) -> List[str]:
    normalized = str(text or "")
    snippets: List[str] = []
    for marker in markers:
        if not marker:
            continue
        index = normalized.find(marker)
        if index < 0:
            continue
        start = max(0, index - 42)
        end = min(len(normalized), index + len(marker) + 58)
        snippet = normalized[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(normalized):
            snippet = snippet + "..."
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets


def enrich_pi_check_report(report: Mapping[str, Any], *, comparison: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    enriched = dict(report)
    if comparison is not None:
        enriched["comparison"] = dict(comparison)
    action_items = build_pi_action_items(enriched, comparison=comparison)
    gatekeeper = evaluate_pi_gatekeeper(enriched, action_items=action_items, comparison=comparison)
    readiness = evaluate_pi_readiness(enriched, comparison=comparison)
    blockers = build_pi_blockers(enriched, gatekeeper=gatekeeper, readiness=readiness, comparison=comparison)
    enriched["actionItems"] = action_items
    enriched["actionItemCount"] = len(action_items)
    enriched["gatekeeper"] = gatekeeper
    enriched["qualityGatePassed"] = bool(gatekeeper.get("passed"))
    enriched["piReadiness"] = readiness
    enriched["piReadinessGatePassed"] = bool(readiness.get("passed"))
    enriched["blockers"] = blockers
    enriched["resultBlocked"] = bool(blockers)
    return enriched


def build_pi_action_items(report: Mapping[str, Any], *, comparison: Mapping[str, Any] | None = None) -> List[Dict[str, Any]]:
    action_items: List[Dict[str, Any]] = []
    for check in report.get("checks", []) if isinstance(report.get("checks", []), list) else []:
        if not isinstance(check, Mapping):
            continue
        status = str(check.get("status", "")).lower()
        if status == "yes":
            continue
        item_id = str(check.get("id", ""))
        priority = "P1" if status == "no" and item_id in PI_CORE_CHECK_IDS else "P2" if status == "no" else "P3"
        evidence_values = check.get("evidence", [])
        if isinstance(evidence_values, str):
            evidence_values = [evidence_values]
        if not isinstance(evidence_values, Sequence):
            evidence_values = []
        action_items.append(
            {
                "itemId": item_id,
                "type": "pi_check",
                "priority": priority,
                "title": f"{check.get('inspectionItem') or check.get('focus') or item_id} 보완",
                "targetLocation": check.get("targetLocation") or PI_CHECK_TARGET_LOCATIONS.get(item_id, "정책서 본문"),
                "inspectionMethod": check.get("inspectionMethod", ""),
                "evidence": "; ".join(str(item) for item in evidence_values if item) or check.get("statusReason", ""),
                "suggestion": check.get("suggestion", ""),
                "status": status,
            }
        )
    for pattern in report.get("antiPatterns", []) if isinstance(report.get("antiPatterns", []), list) else []:
        if not isinstance(pattern, Mapping):
            continue
        pattern_id = str(pattern.get("id", ""))
        priority = "P1" if pattern_id in {"PI-ANTI-04", "PI-ANTI-05"} else "P2"
        action_items.append(
            {
                "itemId": pattern_id,
                "type": "anti_pattern",
                "priority": priority,
                "title": f"{pattern.get('name') or pattern_id} 제거",
                "targetLocation": "프로세스/상태/기능/정책 상세",
                "inspectionMethod": "PI 안티패턴 탐지 결과를 본문 보완 항목으로 전환한다.",
                "evidence": pattern.get("reason", ""),
                "suggestion": pi_anti_pattern_suggestion(pattern_id),
                "status": "fail",
            }
        )
    if comparison and isinstance(comparison.get("regressedItems"), list):
        for item in comparison.get("regressedItems", [])[:6]:
            if not isinstance(item, Mapping):
                continue
            item_id = str(item.get("id", ""))
            action_items.append(
                {
                    "itemId": f"COMPARE-{item_id}",
                    "type": "comparison_regression",
                    "priority": "P1" if item_id in PI_CORE_CHECK_IDS else "P2",
                    "title": f"{item_id} As-Is 대비 후퇴 보완",
                    "targetLocation": PI_CHECK_TARGET_LOCATIONS.get(item_id, "To-Be 문서"),
                    "inspectionMethod": "As-Is/To-Be 체크 상태를 비교해 To-Be에서 낮아진 항목을 보완 대상으로 지정한다.",
                    "evidence": f"{item.get('from', '-')} → {item.get('to', '-')}",
                    "suggestion": item.get("suggestion", ""),
                    "status": "regressed",
                }
            )
    return sorted(action_items, key=lambda item: {"P1": 0, "P2": 1, "P3": 2}.get(str(item.get("priority", "P3")), 3))[:18]


def pi_anti_pattern_suggestion(pattern_id: str) -> str:
    suggestions = {
        "PI-ANTI-01": "기존 흐름 중 제거·통합·자동화할 단계와 유지 사유를 To-Be 프로세스에 명시한다.",
        "PI-ANTI-02": "현업 요청 문구를 요구사항·VOC·운영 데이터 근거와 연결하고 정책 판단 기준으로 재작성한다.",
        "PI-ANTI-03": "AI 입력, 출력, 신뢰도, HITL, Fallback, 상담 전환 기준을 함께 정의한다.",
        "PI-ANTI-04": "예외·실패·복구·재시도·고지 기준을 별첨이 아니라 상태 전이와 정책 상세에 포함한다.",
        "PI-ANTI-05": "KPI 이름, 산식, 측정 주기, 기준값, 목표, Owner를 최소 3개 이상 정의한다.",
    }
    return suggestions.get(pattern_id, "안티패턴 사유를 본문 보완 항목으로 전환한다.")


def evaluate_pi_gatekeeper(
    report: Mapping[str, Any],
    *,
    action_items: Sequence[Mapping[str, Any]] | None = None,
    comparison: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    checks = report.get("checks", []) if isinstance(report.get("checks", []), list) else []
    anti_patterns = report.get("antiPatterns", []) if isinstance(report.get("antiPatterns", []), list) else []
    action_items = list(action_items or [])
    dimensions = [
        pi_gatekeeper_dimension(
            "PI-GK-01",
            "pass"
            if len(checks) == len(PI_CHECKLIST)
            and all(str(item.get("status", "")).lower() in {"yes", "partial", "no"} for item in checks if isinstance(item, Mapping))
            else "fail",
            f"{len(checks)}개 체크 항목을 평가했습니다.",
        ),
        pi_gatekeeper_dimension(
            "PI-GK-02",
            "pass"
            if sum(1 for item in checks if isinstance(item, Mapping) and item.get("inspectionMethod") and item.get("statusReason")) >= 8
            else "warn"
            if sum(1 for item in checks if isinstance(item, Mapping) and item.get("statusReason")) >= 6
            else "fail",
            "항목별 검수 방식과 판정 사유를 확인했습니다.",
        ),
        pi_gatekeeper_dimension(
            "PI-GK-03",
            "pass"
            if action_items or int(report.get("noCount") or 0) == 0 and int(report.get("partialCount") or 0) == 0
            else "fail",
            f"보완 실행 항목 {len(action_items)}건을 생성했습니다.",
        ),
        pi_gatekeeper_dimension(
            "PI-GK-04",
            "pass"
            if int(report.get("antiPatternCount") or 0) == len(anti_patterns)
            and all(isinstance(item, Mapping) and item.get("reason") for item in anti_patterns)
            else "warn",
            f"안티패턴 {len(anti_patterns)}건을 결과와 대조했습니다.",
        ),
        pi_gatekeeper_dimension(
            "PI-GK-05",
            pi_comparison_gate_status(comparison),
            pi_comparison_gate_detail(comparison),
        ),
    ]
    points = sum({"pass": 2, "warn": 1, "fail": 0}.get(str(item.get("status")), 0) for item in dimensions)
    grade = "A" if points >= 9 else "B" if points >= 7 else "C" if points >= 5 else "F"
    return {
        "agent": "PI Check GateKeeper",
        "version": "1.0",
        "grade": grade,
        "score": points,
        "maxScore": len(dimensions) * 2,
        "passed": grade in {"A", "B"},
        "summary": f"PI Check 결과 검수는 {grade} 등급입니다.",
        "dimensions": dimensions,
    }


def pi_gatekeeper_dimension(item_id: str, status: str, detail: str) -> Dict[str, Any]:
    metadata = next((item for item in PI_GATEKEEPER_DIMENSIONS if item["id"] == item_id), {"name": item_id, "description": ""})
    return {
        "id": item_id,
        "name": metadata.get("name", item_id),
        "description": metadata.get("description", ""),
        "status": status,
        "detail": detail,
    }


def pi_comparison_gate_status(comparison: Mapping[str, Any] | None) -> str:
    if not comparison:
        return "pass"
    try:
        expected_delta = int(comparison.get("toBeScore") or 0) - int(comparison.get("asIsScore") or 0)
        actual_delta = int(comparison.get("deltaScore") or 0)
    except (TypeError, ValueError):
        return "fail"
    if expected_delta != actual_delta:
        return "fail"
    if int(comparison.get("regressedCount") or 0) >= 3:
        return "warn"
    return "pass"


def pi_comparison_gate_detail(comparison: Mapping[str, Any] | None) -> str:
    if not comparison:
        return "As-Is 비교 문서가 없어 To-Be 단독 점검으로 처리했습니다."
    return (
        f"As-Is {comparison.get('asIsScore', '-')}점, To-Be {comparison.get('toBeScore', '-')}점, "
        f"점수 차이 {comparison.get('deltaScore', '-')}점을 확인했습니다."
    )


def evaluate_pi_readiness(report: Mapping[str, Any], *, comparison: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    score = int(report.get("score") or 0)
    no_count = int(report.get("noCount") or 0)
    anti_count = int(report.get("antiPatternCount") or 0)
    checks = report.get("checks", []) if isinstance(report.get("checks", []), list) else []
    core_failures = [
        str(item.get("id"))
        for item in checks
        if isinstance(item, Mapping) and str(item.get("id")) in PI_CORE_CHECK_IDS and str(item.get("status", "")).lower() == "no"
    ]
    comparison_delta = int(comparison.get("deltaScore") or 0) if comparison else None
    regressed_count = int(comparison.get("regressedCount") or 0) if comparison else 0
    reasons: List[str] = []
    if score < 65:
        reasons.append("PI 점수가 65점 미만입니다.")
    if no_count >= 4:
        reasons.append("FAIL 항목이 4건 이상입니다.")
    if anti_count >= 3:
        reasons.append("안티패턴이 3건 이상입니다.")
    if core_failures:
        reasons.append(f"핵심 PI 항목 실패: {', '.join(core_failures)}")
    if comparison_delta is not None and comparison_delta < 0:
        reasons.append("To-Be 점수가 As-Is보다 낮습니다.")
    if regressed_count >= 3:
        reasons.append("As-Is 대비 후퇴 항목이 3건 이상입니다.")
    status = "fail" if reasons else "pass" if score >= 80 and no_count == 0 and anti_count <= 1 else "warn"
    return {
        "status": status,
        "passed": status != "fail",
        "score": score,
        "summary": "PI 제출 가능 기준을 통과했습니다." if status == "pass" else "PI 보완 후 재검토가 필요합니다." if status == "warn" else "PI 제출 Gate를 통과하지 못했습니다.",
        "reasons": reasons,
        "coreFailures": core_failures,
    }


def build_pi_blockers(
    report: Mapping[str, Any],
    *,
    gatekeeper: Mapping[str, Any],
    readiness: Mapping[str, Any],
    comparison: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    blockers: List[Dict[str, Any]] = []
    if not gatekeeper.get("passed"):
        blockers.append(
            {
                "id": "PI-GATEKEEPER",
                "type": "pi_check_quality",
                "severity": "P1",
                "message": str(gatekeeper.get("summary", "PI Check 결과 품질 Gate를 통과하지 못했습니다.")),
            }
        )
    if readiness.get("status") == "fail":
        blockers.append(
            {
                "id": "PI-READINESS",
                "type": "pi_readiness",
                "severity": "P1",
                "message": str(readiness.get("summary", "PI 제출 Gate를 통과하지 못했습니다.")),
            }
        )
    if comparison and int(comparison.get("deltaScore") or 0) < 0:
        blockers.append(
            {
                "id": "PI-COMPARISON-REGRESSION",
                "type": "pi_comparison",
                "severity": "P1",
                "message": "To-Be가 As-Is보다 낮은 PI 점수로 평가되었습니다.",
            }
        )
    return blockers


def normalize_stage(stage: str) -> str:
    value = str(stage or "").strip().lower()
    aliases = {
        "07_process": "process",
        "08_functions": "functions",
        "09_policies": "policies",
        "10_final_check": "final_check",
        "09_final": "final_check",
        "full": "final_check",
        "final": "final_check",
    }
    return aliases.get(value, value or "final_check")


def strip_markup(value: str) -> str:
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def has_any(text: str, markers: Sequence[str]) -> bool:
    return any(marker and marker in text for marker in markers)


def has_stage_reduction_signal(text: str) -> bool:
    return has_any(text, ("단계 수", "단계 축소", "중복 제거", "중복 입력", "중복 인증", "간소화", "셀프 처리", "자동화", "일괄 처리"))


def has_pain_point_evidence(text: str) -> bool:
    return has_any(text, ("Pain Point", "병목", "불편", "실패", "이탈", "지연")) and bool(re.search(r"\d+(?:\.\d+)?\s*(?:건|회|분|초|시간|일|%|퍼센트)", text))


def count_failure_axes(text: str) -> int:
    markers = ("실패", "오류", "중단", "취소", "철회", "미완료", "중복", "지연", "권한 없음", "데이터 없음", "복구", "재시도", "상담 전환")
    return sum(1 for marker in markers if marker in text)


def has_ai_hitl_boundary(text: str) -> bool:
    if "AI" not in text and "자동화" not in text:
        return True
    return has_any(text, ("입력", "출력")) and has_any(text, ("신뢰도", "HITL", "운영자 확인", "수동", "Fallback", "대체 경로", "상담 전환"))


def count_kpi_terms(text: str) -> int:
    markers = ("KPI", "성공률", "완료율", "전환율", "처리 시간", "오류율", "재시도율", "상담 전환율", "이탈률", "품질", "리드타임")
    return sum(1 for marker in markers if marker in text)


def unique_texts(values: Sequence[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or inspect PI Agent knowledge.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("refresh", help="Refresh reports/evidence/pi_agent_knowledge.json")
    subparsers.add_parser("show", help="Print compact PI Agent knowledge")
    args = parser.parse_args(argv)

    if args.command == "refresh":
        path = save_pi_agent_knowledge()
        print(path)
        return 0
    if args.command == "show":
        print(json.dumps(load_pi_agent_knowledge(), ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover - manual utility.
    raise SystemExit(main())
