from src.policy_requirements import (
    DEFAULT_REQUIREMENTS_DIR,
    DEFAULT_REQUIREMENTS_DB_PATH,
    RequirementItem,
    clean_text,
    effective_detail_name,
    ensure_requirements_database,
    find_column,
    find_policy_module_mapping_workbook,
    find_requirements_workbook,
    load_policy_module_mapping,
    load_scoped_requirements_for_topic,
    matches_policy_topic,
    matches_policy_topic_strict,
    requirement_sort_key,
    requirements_workbook_rank_key,
    strict_depth4_labels_for_topic,
    topic_match_axes,
)
from src.chapter_agents import requirement_prompt_items


def test_topic_match_axes_normalizes_compound_member_topic():
    assert topic_match_axes("회원 가입/탈퇴") == ["회원가입", "탈퇴"]
    assert topic_match_axes("회원가입 · 회원탈퇴") == ["회원가입", "회원탈퇴"]


def test_matches_member_signup_withdrawal_topic_variants():
    assert matches_policy_topic("회원 가입/탈퇴", "회원가입 · 회원탈퇴")
    assert matches_policy_topic("회원 가입/탈퇴/로그인/인증", "회원가입 · 회원탈퇴")


def test_does_not_match_unrelated_signup_scope_on_single_axis_only():
    assert not matches_policy_topic("상품 가입/탈퇴", "회원가입 · 회원탈퇴")


def test_strict_topic_matching_blocks_adjacent_product_scope():
    assert matches_policy_topic("상품·서비스 혜택 이용/공유", "상품 상세")
    assert matches_policy_topic_strict("상품 상세", "상품 상세")
    assert not matches_policy_topic_strict("상품·서비스 혜택 이용/공유", "상품 상세")


def test_strict_topic_matching_allows_registered_compound_aliases():
    assert set(strict_depth4_labels_for_topic("가이드라인/ 공통/ 품질/ 적응형")) == {
        "가이드라인/ 공통/ 품질/ 적응형",
        "가이드라인",
        "공통",
        "품질/적응형",
    }
    assert matches_policy_topic_strict("공통", "가이드라인/ 공통/ 품질/ 적응형")
    assert matches_policy_topic_strict("회원 가입/탈퇴", "회원가입 · 회원탈퇴")


def test_requirements_workbook_selection_ignores_mapping_workbook():
    workbook = find_requirements_workbook(DEFAULT_REQUIREMENTS_DIR)

    assert workbook is not None
    assert workbook.name == "20260509_요구사항 최종.xlsx"
    assert "맵핑표" not in workbook.name


def test_requirements_workbook_selection_prefers_dated_final_file():
    older = DEFAULT_REQUIREMENTS_DIR / "20260426_NC 요구사항 목록 정의서.xlsx"
    latest = DEFAULT_REQUIREMENTS_DIR / "20260509_요구사항 최종.xlsx"

    assert requirements_workbook_rank_key(latest) > requirements_workbook_rank_key(older)


def test_requirements_database_indexes_current_workbook():
    db_path = ensure_requirements_database(DEFAULT_REQUIREMENTS_DIR)

    assert db_path == DEFAULT_REQUIREMENTS_DB_PATH
    assert db_path.exists()


def test_requirement_column_matching_prefers_exact_header():
    headers = ["요구사항id상위요구사항목록시트", "상위요구사항", "요구사항설명"]

    assert find_column(headers, "상위요구사항") == 1


def test_excel_error_values_do_not_pollute_requirement_text():
    assert clean_text("#REF!") == ""
    assert clean_text("#N/A") == ""


def test_requirements_database_fills_blank_detail_names_from_description():
    db_path = ensure_requirements_database(DEFAULT_REQUIREMENTS_DIR)

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        blank_count = conn.execute(
            "SELECT COUNT(*) FROM requirement_rows WHERE COALESCE(detail_name, '') = ''"
        ).fetchone()[0]
        generated_name = conn.execute(
            "SELECT detail_name FROM requirement_rows WHERE detail_id = 'ORD-H07-003'"
        ).fetchone()[0]
        parent_name = conn.execute(
            "SELECT parent_name FROM requirement_rows WHERE requirement_id = '13UXP-H02' LIMIT 1"
        ).fetchone()[0]

    assert blank_count == 0
    assert generated_name
    assert generated_name != "ORD-H07-003"
    assert parent_name == "레이블·문구 표준화"


def test_effective_detail_name_keeps_source_description_but_derives_label():
    assert effective_detail_name(
        "",
        "고객이 계약/서비스단위변경를 채널에서 직접 변경할 수 있어야 한다. 변경 후 적용 시점과 결과를 바로 확인할 수 있어야 한다.",
        parent_name="주문/계약/가입",
        requirement_id="ORD-H07",
    ).startswith("계약/서비스단위변경")


def test_policy_module_mapping_covers_new_34_topics():
    mapping_workbook = find_policy_module_mapping_workbook(DEFAULT_REQUIREMENTS_DIR)
    mapping = load_policy_module_mapping(DEFAULT_REQUIREMENTS_DIR)

    assert mapping_workbook is not None
    assert mapping_workbook.name == "정책서 모듈 맵핑표.xlsx"
    assert len(mapping) == 34
    assert mapping["이벤트/미션 프로그램"] == ["이벤트/미션 프로그램"]
    assert mapping["멤버십 혜택/T 플러스포인트"] == ["멤버십 혜택/T 플러스포인트"]
    assert mapping["결제"] == ["결제"]


def test_scoped_requirements_use_34_module_mapping():
    payment_items = load_scoped_requirements_for_topic("결제")
    event_items = load_scoped_requirements_for_topic("이벤트/미션 프로그램")

    assert len(payment_items) == 104
    assert {item.depth4 for item in payment_items} == {"결제"}
    assert all(item.detail_id and item.detail_name and item.detail_description for item in payment_items)
    assert len(event_items) == 66
    assert {item.depth4 for item in event_items} == {"이벤트/미션 프로그램"}


def test_scoped_requirements_use_depth4_when_policy_module_column_is_absent():
    items = load_scoped_requirements_for_topic("주문 상태/사후 관리")

    assert len(items) == 111
    assert {item.policy_module for item in items if item.policy_module} == set()
    assert {item.depth4 for item in items} == {"주문 상태/사후 관리"}


def test_requirement_sort_key_ignores_unverified_priority():
    base = dict(
        source_number="10",
        depth3="상품",
        depth4="상품 목록",
        requirement_id="REQ-LOW",
        parent_name="상품 목록",
        parent_description="",
        detail_name="목록 카드 표준",
        detail_description="목록 카드 표시 기준을 정의한다.",
        requirement_type="필수",
        required="Y",
        source="",
        owner_team="",
        owner="",
        edit_status="",
        review_status="",
    )
    p1 = RequirementItem(**base, priority="P1")
    p3 = RequirementItem(**base, priority="P3")

    assert requirement_sort_key(p1) == requirement_sort_key(p3)


def test_requirement_prompt_items_uses_detail_fields_without_priority_bias():
    items = [
        RequirementItem(
            source_number=str(index),
            depth3="주문",
            depth4="주문/계약/가입",
            requirement_id=f"REQ-{index:03d}",
            detail_id=f"REQ-{index:03d}-{index:03d}",
            parent_name="주문/계약/가입",
            parent_description="주문 업무 기준을 정의한다.",
            detail_name=f"상세 요구 {index:03d}",
            detail_description=f"고객이 상세 조건 {index:03d}을 확인하고 처리 결과를 안내받는다.",
            requirement_type="필수",
            priority="P1",
            required="Y",
            source="",
            owner_team="",
            owner="",
            edit_status="",
            review_status="",
        )
        for index in range(1, 11)
    ]

    prompt_items = requirement_prompt_items(items, limit=4)
    names = [item["detail_name"] for item in prompt_items]

    assert "priority" not in prompt_items[0]
    assert prompt_items[0]["detail_id"].startswith("REQ-")
    assert "상세 요구 001" in names
    assert "상세 요구 010" in names
    assert any(name in names for name in {"상세 요구 004", "상세 요구 005", "상세 요구 006", "상세 요구 007"})
