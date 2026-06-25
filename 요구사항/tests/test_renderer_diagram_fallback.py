from src.renderer import build_state_mermaid, build_state_static_diagram, render_policy_html


def minimal_diagram_spec():
    return {
        "meta": {
            "topic": "회원 가입탈퇴",
            "document_type": "간소화 버전",
            "version": "v0.1",
            "business_code": "MBR",
            "usecase_diagram": {"lines": ["[고객] → (가입 정보 확인)"]},
        },
        "history": [{"version": "v0.1", "change": "초안"}],
        "overview": {"scope": [], "principles": []},
        "terms": [],
        "actors": [{"id": "ACT-MBR-001", "name": "고객", "description": "고객"}],
        "usecases": [
            {
                "id": "US-MBR-001",
                "actor": "고객",
                "name": "가입 정보 확인",
                "description": "가입 정보를 확인한다.",
                "process_target": "Y",
            }
        ],
        "states": [{"id": "ST-MBR-001", "name": "가입 전"}],
        "state_transitions": [
            {
                "usecase_ids": ["US-MBR-001"],
                "current_state": "가입 전",
                "event": "가입 신청",
                "next_state": "가입 완료",
                "criteria": "인증 완료 시 전이한다.",
            }
        ],
        "processes": [
            {
                "id": "PR-MBR-001",
                "usecase_id": "US-MBR-001",
                "name": "가입 정보 확인",
                "related_functions": ["FN-MBR-001"],
                "related_policies": ["PG-MBR-001"],
            }
        ],
        "functions": [],
        "policy_groups": [],
        "policy_details": [],
        "final_check": [],
    }


def test_diagrams_render_as_sample_style_static_visuals():
    html = render_policy_html(minimal_diagram_spec(), "", stage_key="07")

    assert ".diagram-wrap.mermaid-diagram { display: none; }" in html
    assert ".diagram-wrap.mermaid-diagram.mermaid-rendered { display: block; }" in html
    assert "markRenderedMermaidBlocks" in html
    assert ".meta th { width: 180px !important; }" in html
    assert '<div class="diagram-wrap uml-usecase-diagram">' in html
    assert '<svg aria-label="회원 가입탈퇴 유즈케이스 다이어그램"' in html
    assert '<text class="actor-text"' in html
    assert "US-MBR-001" in html
    assert "가입 정보 확인" in html
    assert "가입 전" in html
    assert "가입 신청" in html
    assert "가입 완료" in html
    assert "관련 유즈케이스" not in html
    assert '<th style="width: 150px;">현재 상태</th><th style="width: 180px;">전이 이벤트</th><th style="width: 150px;">다음 상태</th><th>처리 기준 및 후속 처리</th>' in html
    assert '<div class="diagram-wrap state-transition-diagram">' in html
    assert '<svg aria-label="상태 전이 다이어그램"' in html
    assert '<div class="diagram-wrap mermaid-diagram state-transition-mermaid">' not in html
    assert '<polygon class="gateway"' not in html
    assert "flow-label" in html
    assert "flow-label-bg" in html
    assert "실선은 대표 흐름" in html
    assert "branch-row" not in html
    assert 'data-bpmn-viewer="true"' in html
    assert 'type="application/json">{"xml":' in html
    assert "BPMN XML 다운로드" in html
    assert '<div class="diagram-wrap bpmn-process-diagram">' in html
    assert '<svg aria-label="전체 업무 흐름도 BPMN"' in html
    assert "PR-MBR-001" in html
    assert "조건 판정" not in html
    assert 'x1="285" x2="244"' not in html
    assert 'x1="293" x2="284"' not in html


def test_policy_detail_continuation_lines_keep_bullet_prefix():
    spec = minimal_diagram_spec()
    spec["policy_groups"] = [
        {"id": "PG-MBR-001", "name": "개인정보 보정 정책", "description": "보정 기준을 정의한다."}
    ]
    spec["policy_details"] = [
        {
            "id": "PI-MBR-001-01",
            "policy_id": "PG-MBR-001",
            "name": "최소 수집",
            "content": "요청 접수 시 최소 수집 기준에서 고객 피해 가능성과 중복 이력이 함께 확인된 경우에만 운영 보정을 허용한다. 보정 전후 값과 승인 주체를 변경 이력으로 저장한다.",
        }
    ]

    html = render_policy_html(spec, "", stage_key="09")

    assert "• 최소 수집" in html
    assert '<span class="policy-item-line">- 요청 접수 시 최소 수집 기준' in html
    assert '<span class="policy-item-line">- 보정 전후 값과 승인 주체를 변경 이력으로 저장한다.</span>' in html


def test_process_diagram_keeps_long_usecase_flow_left_to_right():
    spec = minimal_diagram_spec()
    for process_count in range(5, 9):
        spec["processes"] = [
            {
                "id": f"PR-MBR-{index:03d}",
                "usecase_id": "US-MBR-001",
                "name": f"가입 단계 {index}",
                "description": f"가입 단계 {index}을 처리한다.",
                "related_functions": ["FN-MBR-001"],
                "related_policies": ["PG-MBR-001"],
            }
            for index in range(1, process_count + 1)
        ]

        html = render_policy_html(spec, "", stage_key="07")

        assert '<div class="diagram-wrap bpmn-process-diagram">' in html
        assert f"PR-MBR-{process_count:03d}" in html
        assert '<path class="flow"' not in html
        process_diagram = html.split('<div class="diagram-wrap bpmn-process-diagram">', 1)[1].split("</div>", 1)[0]
        assert 'viewBox="0 0 1120 ' not in process_diagram


def test_grouped_policy_details_render_as_policy_items():
    spec = minimal_diagram_spec()
    spec["policy_groups"] = [
        {"id": "PG-MBR-001", "name": "개인정보 보정 정책", "description": "보정 기준을 정의한다."}
    ]
    spec["processes"][0]["related_policies"] = ["PG-MBR-001 개인정보 보정 정책"]
    spec["policy_details"] = [
        {
            "policy_id": "PG-MBR-001",
            "policy_name": "개인정보 보정 정책",
            "items": [
                {
                    "id": "PI-MBR-001-01",
                    "name": "최소 수집",
                    "content": "요청 접수 시 최소 수집 기준에서 고객 피해 가능성과 중복 이력이 함께 확인된 경우에만 운영 보정을 허용한다.",
                }
            ],
        }
    ]

    html = render_policy_html(spec, "", stage_key="09")

    assert "• 최소 수집" in html
    assert "PI-MBR-001-01" in html
    assert "요청 접수 시 최소 수집 기준" in html
    assert '<div class="policy-item-title">•  <span class="mono">()</span></div>' not in html


def test_final_check_dict_items_render_as_title_and_criteria():
    spec = minimal_diagram_spec()
    spec["final_check"] = [
        {
            "item": "범위 정합성",
            "criteria": "정책서가 다루는 업무 범위와 제외 범위가 구분되어야 한다. 다른 정책서와의 경계가 드러나야 한다.",
        }
    ]

    html = render_policy_html(spec, "", stage_key="10")

    assert "{'item'" not in html
    assert '<div class="guide-section-title">1. 범위 정합성</div>' in html
    assert "정책서가 다루는 업무 범위와 제외 범위가 구분되어야 한다.<br/>" in html
    assert "다른 정책서와의 경계가 드러나야 한다.<br/>" in html


def test_state_diagram_resolves_transition_state_ids_to_defined_names():
    spec = minimal_diagram_spec()
    spec["states"] = [
        {"id": "ST-MBR-001", "name": "가입 전"},
        {"id": "ST-MBR-002", "name": "인증 중"},
        {"id": "ST-MBR-003", "name": "가입 완료"},
        {"id": "ST-MBR-004", "name": "보완 필요"},
    ]
    spec["state_transitions"] = [
        {
            "current_state": "ST-MBR-001",
            "event": "가입 신청",
            "next_state": "ST-MBR-002",
            "criteria": "가입 신청을 접수하면 인증 중으로 전이한다.",
        },
        {
            "current_state": "ST-MBR-002",
            "event": "인증 완료",
            "next_state": "ST-MBR-003",
            "criteria": "본인 인증이 완료되면 가입 완료로 전이한다.",
        },
        {
            "current_state": "ST-MBR-002",
            "event": "인증 실패",
            "next_state": "ST-MBR-004",
            "criteria": "인증에 실패하면 보완 필요 상태로 전이한다.",
        },
    ]

    static_svg = build_state_static_diagram(spec)
    mermaid = build_state_mermaid(spec)

    assert static_svg.count('<rect class="state') == 4
    assert static_svg.count('class="flow"') >= 2
    assert static_svg.count('class="flow-dash"') >= 1
    assert "가입 전" in static_svg
    assert "인증 중" in static_svg
    assert "가입 완료" in static_svg
    assert "보완 필요" in static_svg
    assert 'ST-MBR-001</text>' in static_svg
    assert 'ST-MBR-002</text>' in static_svg
    assert 'ST-MBR-003</text>' in static_svg
    assert 'state "가입 전 ST-MBR-001" as S01' in mermaid
    assert "S01 --> S02" in mermaid
    assert "S02 --> S03" in mermaid

    html = render_policy_html(spec, "", stage_key="06")
    transition_table = html.split('<h4>2) 상태 전이 기준</h4>', 1)[1].split('<h4>3) 상태 전이 다이어그램</h4>', 1)[0]

    assert "가입 전<br/>" in transition_table
    assert "ST-MBR-001" in transition_table
    assert "<td>ST-MBR-001</td>" not in transition_table
