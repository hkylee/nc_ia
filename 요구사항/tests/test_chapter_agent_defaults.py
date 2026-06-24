from src.chapter_agents import default_usecase_for_actor, korean_subject


def test_default_usecase_for_actor_uses_natural_korean_subject_particle():
    assert korean_subject("고객") == "고객이"
    assert korean_subject("운영자") == "운영자가"

    _, customer_description = default_usecase_for_actor("고객", "회원가입 · 회원탈퇴")
    _, operator_description = default_usecase_for_actor("운영자", "회원가입 · 회원탈퇴")

    assert "고객이 회원가입 · 회원탈퇴 업무의 대상, 가능 조건, 처리 영향, 완료 상태를 확인" in customer_description
    assert "운영자가 회원가입 · 회원탈퇴 업무의 운영 기준" in operator_description
    assert "고객가" not in customer_description
    assert "운영자가가" not in operator_description


def test_default_usecase_for_actor_separates_external_and_channel_systems():
    external_name, external_description = default_usecase_for_actor("연계 시스템", "회원가입 · 회원탈퇴")
    channel_name, channel_description = default_usecase_for_actor("채널 업무 시스템", "회원가입 · 회원탈퇴")

    assert external_name == "외부 기준 정보 및 결과 회신"
    assert "외부 기준 정보" in external_description
    assert "콜백" in external_description
    assert channel_name == "채널 요청 접수 및 상태·이력 반영"
    assert "고객 입력" in channel_description
    assert "최종 판정은 BSS 또는 연계 결과" in channel_description
    assert external_name != channel_name
