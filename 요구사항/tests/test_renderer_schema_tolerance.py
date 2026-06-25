from src.renderer import render_policy_html


def test_renderer_accepts_common_manual_schema_aliases():
    spec = {
        "meta": {
            "topic": "데이터 트래킹 체계",
            "topic_display": "데이터 트래킹 체계",
            "document_id": "POL-TRK",
            "document_type": "간소화 버전",
            "status": "작성중",
            "version": "v0.1",
            "author": "Codex Manual Authoring",
            "date": "2026-05-09",
            "authoring_basis": "PM-07 관련 상세 요구사항명과 상세 요구사항 설명을 기준으로 재구성했다.",
        },
        "history": [
            {
                "version": "v0.1",
                "description": "초안 작성",
                "date": "2026-05-09",
                "author": "Codex",
            }
        ],
        "overview": {
            "scope": "데이터 수집부터 검증, 저장, 활용, 품질 보정까지 포함한다.",
            "principles": [
                "고객 동의와 사용 목적을 기준으로 수집 범위를 제한한다.",
                {
                    "title": "추적 가능성",
                    "detail": "이벤트 발생부터 리포트 활용까지 이력을 남긴다.",
                },
            ],
        },
        "terms": [
            {
                "id": "TM-TRK-001",
                "term": "이벤트",
                "definition": "고객 또는 시스템 행동이 데이터로 기록되는 최소 단위다.",
            }
        ],
    }

    html = render_policy_html(spec, "<html><head></head><body></body></html>", stage_key="02_terms")

    assert "PM-07 관련 상세 요구사항명" in html
    assert "P<br/>M<br/>-<br/>0<br/>7" not in html
    assert "초안 작성" in html
    assert "데이터 수집부터 검증" in html
    assert "고객 동의와 사용 목적" in html
    assert "추적 가능성" in html
    assert "이벤트 발생부터 리포트 활용" in html
    assert "고객 또는 시스템 행동" in html
