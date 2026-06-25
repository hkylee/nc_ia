"""Compact analysis-method knowledge for NC policy agents.

These rules are intentionally short. They improve modeling judgment while
keeping the generated document inside the uploaded template and sample style.
"""

from __future__ import annotations

from typing import Mapping


METHOD_SOURCES = (
    {
        "id": "UML-USECASE",
        "name": "OMG UML 2.5.1 UseCase/Actor",
        "use": "Actor, UseCase, and association judgment.",
        "url": "https://www.omg.org/spec/UML/2.5.1/About-UML",
    },
    {
        "id": "UML-STATE",
        "name": "OMG UML 2.5.1 State Machine",
        "use": "State, transition, event, guard/criteria, and lifecycle judgment.",
        "url": "https://www.omg.org/spec/UML/2.5.1/About-UML",
    },
    {
        "id": "UML-ACTIVITY",
        "name": "OMG UML 2.5.1 Activity/Action",
        "use": "Action, control flow, input/output, and functional responsibility judgment.",
        "url": "https://www.omg.org/spec/UML/2.5.1/About-UML",
    },
    {
        "id": "USECASE-FOUNDATION",
        "name": "Jacobson/Cockburn Use-Case Foundation",
        "use": "Primary actor, goal, and flow-of-events judgment.",
        "url": "https://www.ivarjacobson.com/publications/use-case-foundation",
    },
    {
        "id": "BPMN-2.0.2",
        "name": "OMG BPMN 2.0.2",
        "use": "Process, activity, event, gateway, and exception-flow judgment.",
        "url": "https://www.omg.org/spec/BPMN/2.0.2",
    },
    {
        "id": "BRG-RULES",
        "name": "Business Rules Group",
        "use": "Declarative, atomic, constraint-oriented policy judgment.",
        "url": "https://www.businessrulesgroup.org/first_paper.htm",
    },
    {
        "id": "IIBA-BA-STANDARD",
        "name": "IIBA Business Analysis Standard",
        "use": "Traceability, verification, validation, and change impact judgment.",
        "url": "https://www.iiba.org/standards-and-resources/babok/",
    },
    {
        "id": "IEEE-29148",
        "name": "ISO/IEC/IEEE 29148 Requirements Engineering",
        "use": "Good requirement quality, functional requirement, verification, and specification completeness judgment.",
        "url": "https://standards.ieee.org/ieee/29148/6937/",
    },
)


COMMON_METHOD_GUARD = {
    "priority": [
        "1. 템플릿/샘플의 장 구성, 표 구조, 필드명, 문장 밀도를 최우선으로 유지한다.",
        "2. AGENTS.md, 요구사항, 참고자료, Evidence Map의 범위와 근거를 벗어나지 않는다.",
        "3. 전문 방법론은 액터·유즈케이스·상태·프로세스·기능·정책을 분류하는 내부 판단 기준으로만 쓴다.",
    ],
    "do_not": [
        "템플릿에 없는 fully-dressed use case, BPMN/DMN 전문 양식, 별도 분석 보고서 장을 추가하지 않는다.",
        "정책서 본문에 방법론 출처나 이론 설명을 쓰지 않는다.",
        "샘플보다 장황한 배경 설명, 시나리오 서술, 모델링 강의 문장을 만들지 않는다.",
    ],
    "style": "결과는 NC 정책서 샘플처럼 짧은 표 셀, 명확한 판단 기준, 정책 항목 중심으로 작성한다.",
}


ARTIFACT_BOUNDARY_RULES = {
    "actor_vs_condition": [
        "액터는 행위와 책임을 갖는 역할이고, 로그인/비로그인/정상/제한/미성년 같은 차이는 조건·상태·정책이다.",
        "상품 운영자, 전시 운영자, 쿠폰 운영자, 마케팅 운영자 같은 내부 세부 역할은 기본적으로 운영자로 통합하고 역할 차이는 유즈케이스 설명·기능·정책에 둔다.",
        "AI 검색 엔진, 추천 엔진, 상품 마스터, 알림센터 같은 세부 시스템은 채널 업무 시스템 또는 도메인/BSS 연계 시스템으로 통합하고 세부 책임은 기능·정책으로 내려 쓴다.",
        "시스템명은 액터가 아니라 결과를 생성하거나 판정·회신 책임이 있을 때만 액터가 된다.",
    ],
    "usecase_vs_process": [
        "유즈케이스는 액터가 달성하려는 목표이고, 프로세스는 그 목표를 완성하는 절차 흐름이다.",
        "약관 동의, 인증, 입력, 검증, 결과 안내는 대개 유즈케이스가 아니라 프로세스 단계다.",
    ],
    "state_vs_term_process": [
        "상태는 후속 처리와 허용 여부가 달라지는 업무 조건이고, 용어는 그 상태와 판단값을 해석하기 위한 정의다.",
        "상태명은 액터-유즈케이스 lifecycle에서 도출하고, 프로세스명이나 화면 상태를 상태명으로 승격하지 않는다.",
    ],
    "transition_vs_criteria": [
        "전이 이벤트는 승인된 유즈케이스 흐름에서 발생한 상태 변화 업무 사건이며, 추적성은 usecase_ids로 남기고 세부 판정 조건은 criteria에 둔다.",
        "현재 상태, 이벤트, 기준, 다음 상태가 한 행에서 읽혀야 하며, 결과 상태끼리 무의미하게 직접 이동하지 않는다.",
    ],
    "process_vs_function": [
        "프로세스는 사람 또는 업무 관점의 활동 순서이고, 기능은 그 활동을 가능하게 하는 처리 역량이다.",
        "내부 조회·저장·연동·알림은 기능으로 두고, 고객/운영자 흐름의 전환점만 프로세스로 둔다.",
    ],
    "function_vs_policy": [
        "기능은 처리 결과를 만들고, 정책은 그 기능이 어떤 값·조건·범위로 동작할지 제어한다.",
        "기능 설명에 인증 수단, 가능 횟수, 유효시간, 노출 채널, 제한 기간 같은 정책값을 길게 쓰지 않고 정책 상세로 분리한다.",
        "정책은 프로세스와 기능을 먼저 읽고, 기능 동작에 필요한 통제 지점에서 도출한다.",
    ],
    "policy_rule_quality": [
        "정책 항목은 기능 동작에 필요한 하나의 설정값·조건값·제어값이어야 하며, 하나의 항목에 여러 기준을 섞지 않는다.",
        "정책은 샘플처럼 항목명과 값/조건을 선언하고, 절차·구현·화면 문구·추상 원칙을 정책처럼 포장하지 않는다.",
        "좋은 정책 항목은 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 재요청 간격, 노출 채널, 제한 기간, 판정 기준 식별자, 저장 항목처럼 상세 설계자가 바로 쓸 수 있는 값이다.",
    ],
    "traceability_quality": [
        "요구사항은 유즈케이스, 상태, 프로세스, 기능, 정책 중 하나 이상으로 이어져야 한다.",
        "하위 장은 상위 장의 ID, 명칭, 책임 경계를 이어받고, 누락이나 충돌은 Evidence Gap 또는 Inspector finding으로 남긴다.",
    ],
}


DOCUMENT_AUTHORING_METHOD = {
    "purpose": "정책서를 상세 설계자가 사용할 수 있는 업무 구조, 상태 기준, 처리 흐름, 기능 범위, 정책 판단 기준으로 작성한다.",
    "artifact_sequence": [
        "개요에서 범위와 제외 범위를 고정한다.",
        "용어에서 판단값과 상태·권한·고지·이력 용어를 표준화한다.",
        "액터에서 책임 주체를 정한다.",
        "유즈케이스에서 사람 액터의 상위 목표와 시스템 보조 처리를 분리한다.",
        "상태에서 유즈케이스 lifecycle에 따른 허용·제한·보류·완료·예외 조건을 정의한다.",
        "프로세스에서 Y 유즈케이스를 시작, 판단, 처리, 예외, 종료 흐름으로 분해한다.",
        "기능에서 프로세스를 수행하는 조회·검증·산정·저장·알림·연동 역량을 정의한다.",
        "정책에서 기능과 프로세스가 따라야 할 동작값, 허용 목록, 횟수, 시간, 채널, 제한 조건, 예외, 고지, 이력 기준을 선언한다.",
        "최종 점검에서 요구사항과 유즈케이스→상태→프로세스→기능→정책 연결을 검증한다.",
    ],
    "artifact_boundaries": ARTIFACT_BOUNDARY_RULES,
    "template_guard": COMMON_METHOD_GUARD,
}


METHOD_KNOWLEDGE_BY_STAGE = {
    "overview": {
        "method_focus": "Scope modeling",
        "rules": [
            "범위는 시스템 기준이 아니라 고객 과업, 업무 경계, 제외 범위, 후속 상세화 영역으로 고정한다.",
            "포함/제외 범위는 후속 유즈케이스·프로세스·정책에서 검증 가능한 표현이어야 한다.",
            "비전이나 방향성은 원칙으로만 쓰고, 실제 판단값은 정책 장으로 보낸다.",
        ],
    },
    "terms": {
        "method_focus": "Business vocabulary",
        "rules": [
            "용어는 비즈니스에서 특별한 의미를 갖는 단어만 정의한다.",
            "상태, 권한, 동의, 제한, 예외, 이력처럼 후속 판단 기준에 쓰이는 용어를 우선한다.",
            "일반 명사나 UI 표현은 제외하고, 유사 용어 간 차이가 드러나게 쓴다.",
            "용어는 상태·정책 판단값의 의미를 고정하지만 상태 후보를 대신 생성하지 않는다.",
        ],
    },
    "terms_refinement": {
        "method_focus": "Vocabulary consistency",
        "rules": [
            "기능·정책 작성 후 실제로 쓰인 판단 용어를 기준으로 용어장을 보정한다.",
            "동일 개념이 여러 명칭으로 쓰였으면 샘플에 맞는 짧은 표준명으로 통일한다.",
            "정책 항목 수준의 긴 조건문은 용어로 끌어올리지 않는다.",
        ],
    },
    "actors": {
        "method_focus": "UML Actor responsibility",
        "rules": [
            "액터는 시스템과 상호작용하는 역할이며, 독립 목표나 책임을 가진 주체만 둔다.",
            "고객 상태, 자격, 권한 차이는 액터가 아니라 상태·조건·정책으로 다룬다.",
            "내부 세부 운영 역할은 별도 액터가 아니라 운영자 책임 안에서 유즈케이스·기능·정책으로 분해한다.",
            "세부 엔진·저장소·알림·업무 시스템은 독립 액터보다 통합 시스템 액터로 묶고, 판정·회신·이력 책임만 남긴다.",
            "시스템 액터는 판정, 검증, 회신, 기록처럼 결과를 만드는 책임이 있을 때만 분리한다.",
            "한 주체가 빠졌을 때 유즈케이스가 성립하지 않거나 정책 기준이 달라지면 액터 후보로 본다.",
        ],
    },
    "usecases": {
        "method_focus": "Primary actor goal",
        "rules": [
            "유즈케이스는 특정 액터가 달성하려는 목표이며, 약관 동의·인증·입력 같은 절차 단계가 아니다.",
            "하나의 유즈케이스는 여러 성공/예외 흐름을 모으는 상위 업무 목적이어야 한다.",
            "사람 액터의 목표 달성 업무는 process_target=Y, 시스템 보조 처리 유즈케이스는 원칙적으로 N이다.",
            "UI 클릭, 화면 이동, 내부 저장은 유즈케이스가 아니라 프로세스 또는 기능으로 내려 보낸다.",
            "한 Y 유즈케이스에 프로세스가 8개 이상 필요하다면 유즈케이스가 너무 넓은지 확인하고, 고객·운영자의 목표가 실제로 달라지는 경우에는 유즈케이스를 분리한다.",
        ],
    },
    "usecase_diagram": {
        "method_focus": "UML use case association",
        "rules": [
            "다이어그램은 액터와 유즈케이스 관계를 보여주는 용도이며 프로세스 순서를 표현하지 않는다.",
            "include는 여러 유즈케이스가 반복해서 쓰는 공통 처리일 때만 사용한다.",
            "시스템 경계 밖 액터와 경계 안 유즈케이스가 구분되어야 한다.",
        ],
    },
    "state": {
        "method_focus": "State-transition modeling",
        "rules": [
            "상태는 업무 가능 여부, 제한, 보류, 완료, 예외처럼 후속 처리가 달라지는 조건이다.",
            "상태 후보는 용어장이 아니라 액터-유즈케이스 목표의 시작, 판정, 완료, 예외 lifecycle에서 도출한다.",
            "전이 이벤트는 승인된 유즈케이스 흐름에서 발생한 상태 변화 업무 사건이어야 하며, 추적성은 usecase_ids로 남기고 세부 판정 조건은 criteria에 둔다.",
            "현재 상태와 다음 상태는 상태 목록의 표준명과 정확히 일치해야 한다.",
            "상태 설명은 '무엇이 가능한/제한되는 상태인지'를 쓰고, 전이 기준은 '어떤 유즈케이스와 조건이면 이동하는지'를 쓴다.",
            "같은 현재 상태에서 여러 전이가 가능하면 우선순위, 배타 조건, 보류/실패/완료의 출구 기준을 criteria에 명시한다.",
        ],
    },
    "process": {
        "method_focus": "BPMN process decomposition",
        "rules": [
            "프로세스는 유즈케이스 목표를 달성하기 위한 활동 흐름이다.",
            "각 Y 유즈케이스는 시작, 업무 태스크, 판단 분기, 예외/제한 경로, 종료가 보이도록 복수 절차로 분해한다.",
            "BPMN 관점에서 태스크는 일을 수행하고, 게이트웨이는 분기를 만들며, 이벤트는 흐름 시작·중간 반응·종료를 만든다.",
            "내부 시스템 저장/조회는 별도 프로세스가 아니라 기능으로 내려 보낸다.",
        ],
    },
    "process_detail": {
        "method_focus": "BPMN handoff details",
        "rules": [
            "진입 조건은 어떤 상태나 선행 결과에서 프로세스가 시작되는지 표현한다.",
            "종료 조건은 어떤 결과, 상태, 예외, 후속 연결이 확정되어야 끝나는지 표현한다.",
            "선행·후행 관계는 같은 유즈케이스 흐름의 실제 순서를 우선한다.",
        ],
    },
    "functions": {
        "method_focus": "Functional decomposition",
        "rules": [
            "기능은 화면 단위가 아니라 프로세스를 수행하게 하는 처리 역량이다.",
            "기능명은 조회, 검증, 산정, 저장, 알림, 연동, 결과 구성처럼 처리 결과가 드러나야 한다.",
            "정책 판단값은 기능 설명에 길게 쓰지 말고 정책 상세로 분리한다.",
            "기능은 입력을 받아 처리하고 산출물을 만드는 단위여야 하며, 설명에는 처리 결과가 드러나야 한다.",
            "프로세스별로 필요한 기능을 빠뜨리지 않되 동일 세부 기능 묶음을 여러 기능에 복사하지 않는다.",
        ],
    },
    "function_detail": {
        "method_focus": "Functional responsibility detail",
        "rules": [
            "입력, 처리, 출력, 실패·예외는 구현자가 책임 경계를 이해할 정도로만 쓴다.",
            "처리 로직은 상태 확인, 액션, 결과 구분이 드러나야 한다.",
            "API 필드, DB 컬럼, 화면 상세는 쓰지 않는다.",
            "입력 정보와 출력 정보는 서로 연결되어야 하며, 처리 로직은 입력을 어떤 판단/변환/저장으로 출력화하는지 보여야 한다.",
            "실패·예외 케이스에는 재시도, 중단, 제한, 상담 전환, 이력 저장 중 필요한 후속 처리가 있어야 한다.",
        ],
    },
    "policies": {
        "method_focus": "Operational policy values and control rules",
        "rules": [
            "정책은 일반 원칙이 아니라 기능이 실제로 동작하기 위해 필요한 값, 조건, 허용 범위, 제한 기준, 채널, 횟수, 시간, 저장 항목을 정하는 기준이다.",
            "작성 순서는 1) 프로세스와 기능에 필요한 정책을 정의, 2) 그 정책을 구성하는 세부 항목을 정의, 3) 각 항목별 값을 정의하는 흐름을 따른다.",
            "정책 상세 한 항목은 샘플처럼 '정책 항목명 - 정책값/조건' 한 쌍으로 작성한다.",
            "정책 항목 후보는 인증 수단, 인증 가능 횟수, 인증번호 유효시간, 재요청 간격, 노출 채널, 제한 기간, 판정 기준 식별자, 수행 시스템, 저장 항목, 실패 처리처럼 기능 동작값으로 도출한다.",
            "추상 원칙, 기능 처리 절차, 운영 화면 설명, API/DB 구현 설명은 정책 상세로 쓰지 않는다.",
        ],
    },
    "final_check": {
        "method_focus": "Traceability, verification, validation",
        "rules": [
            "요구사항에서 유즈케이스, 상태, 프로세스, 기능, 정책으로 이어지는 전후 추적성을 확인한다.",
            "산출물이 내부적으로 일관되고 상세 설계자가 사용할 수 있을 만큼 충분한지 확인한다.",
            "정책이 고객 가치와 업무 목표를 지원하는지 확인한다.",
        ],
    },
}


STAGE_BOUNDARY_KEYS = {
    "overview": ("traceability_quality",),
    "terms": ("state_vs_term_process", "policy_rule_quality"),
    "terms_refinement": ("state_vs_term_process", "policy_rule_quality", "traceability_quality"),
    "actors": ("actor_vs_condition",),
    "usecases": ("actor_vs_condition", "usecase_vs_process"),
    "usecase_diagram": ("actor_vs_condition", "usecase_vs_process"),
    "state": ("state_vs_term_process", "transition_vs_criteria", "traceability_quality"),
    "process": ("usecase_vs_process", "process_vs_function", "transition_vs_criteria"),
    "process_detail": ("usecase_vs_process", "process_vs_function"),
    "functions": ("process_vs_function", "function_vs_policy"),
    "function_detail": ("process_vs_function", "function_vs_policy", "traceability_quality"),
    "policies": ("function_vs_policy", "policy_rule_quality", "traceability_quality"),
    "final_check": ("traceability_quality", "actor_vs_condition", "usecase_vs_process", "state_vs_term_process", "process_vs_function", "function_vs_policy", "policy_rule_quality"),
}


def method_knowledge_for_agent(chapter_key: str) -> dict:
    """Return compact method knowledge for a chapter prompt."""
    stage = METHOD_KNOWLEDGE_BY_STAGE.get(chapter_key, METHOD_KNOWLEDGE_BY_STAGE["overview"])
    return {
        "template_sample_guard": COMMON_METHOD_GUARD,
        "method_focus": stage["method_focus"],
        "rules": stage["rules"],
        "artifact_boundaries": stage_artifact_boundaries(chapter_key),
        "source_basis": [
            {"id": item["id"], "use": item["use"]}
            for item in METHOD_SOURCES
            if method_source_applies(chapter_key, item["id"])
        ],
    }


def method_source_applies(chapter_key: str, source_id: str) -> bool:
    stage_sources = {
        "overview": {"IIBA-BA-STANDARD"},
        "terms": {"BRG-RULES", "IIBA-BA-STANDARD"},
        "terms_refinement": {"BRG-RULES", "IIBA-BA-STANDARD"},
        "actors": {"UML-USECASE", "USECASE-FOUNDATION"},
        "usecases": {"UML-USECASE", "USECASE-FOUNDATION", "IIBA-BA-STANDARD"},
        "usecase_diagram": {"UML-USECASE"},
        "state": {"UML-STATE", "UML-USECASE", "IIBA-BA-STANDARD"},
        "process": {"BPMN-2.0.2", "USECASE-FOUNDATION"},
        "process_detail": {"BPMN-2.0.2"},
        "functions": {"BPMN-2.0.2", "UML-ACTIVITY", "IEEE-29148", "IIBA-BA-STANDARD"},
        "function_detail": {"BPMN-2.0.2", "UML-ACTIVITY", "IEEE-29148", "IIBA-BA-STANDARD"},
        "policies": {"BRG-RULES", "IIBA-BA-STANDARD", "IEEE-29148"},
        "final_check": {"IIBA-BA-STANDARD", "BRG-RULES", "IEEE-29148"},
    }
    return source_id in stage_sources.get(chapter_key, {"IIBA-BA-STANDARD"})


def stage_artifact_boundaries(chapter_key: str) -> dict:
    return {
        key: ARTIFACT_BOUNDARY_RULES[key]
        for key in STAGE_BOUNDARY_KEYS.get(chapter_key, ())
        if key in ARTIFACT_BOUNDARY_RULES
    }


def method_knowledge_for_learning() -> dict:
    """Return the cross-document method pack for topic learning."""
    return {
        "template_sample_guard": COMMON_METHOD_GUARD,
        "document_method": {
            "purpose": DOCUMENT_AUTHORING_METHOD["purpose"],
            "artifact_sequence": DOCUMENT_AUTHORING_METHOD["artifact_sequence"],
            "artifact_boundaries": DOCUMENT_AUTHORING_METHOD["artifact_boundaries"],
        },
        "stage_focus": {
            key: {
                "method_focus": value["method_focus"],
                "rules": value["rules"][:4],
            }
            for key, value in METHOD_KNOWLEDGE_BY_STAGE.items()
        },
        "source_basis": [
            {"id": item["id"], "use": item["use"]}
            for item in METHOD_SOURCES
        ],
    }


def method_guard_for_inspector() -> dict:
    return {
        "rule": "전문 방법론은 품질 검수 기준으로 쓰되, 템플릿·샘플 구조와 AGENTS.md 기준을 벗어나게 요구하지 않는다.",
        "template_sample_guard": COMMON_METHOD_GUARD,
        "stage_method_focus": {
            key: value["method_focus"]
            for key, value in METHOD_KNOWLEDGE_BY_STAGE.items()
        },
        "artifact_boundaries": ARTIFACT_BOUNDARY_RULES,
    }
