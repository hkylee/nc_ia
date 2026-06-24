from src.policy_agent import make_business_code, make_module_id


def test_cart_topics_use_stable_business_code():
    assert make_business_code("카트/장바구니") == "CRT"
    assert make_business_code("장바구니") == "CRT"


def test_discount_simulation_topics_use_stable_business_code():
    assert make_business_code("할인/시뮬레이션") == "SIM"
    assert make_business_code("시뮬레이션") == "SIM"


def test_order_contract_topics_use_stable_business_code():
    assert make_business_code("주문/계약/가입") == "ORD"
    assert make_business_code("주문") == "ORD"
    assert make_module_id("주문/계약/가입") == "PM-14"


def test_all_34_policy_topics_have_module_id():
    from src.topic_knowledge_builder import POLICY_TOPICS

    module_ids = [make_module_id(topic) for topic in POLICY_TOPICS]

    assert len(module_ids) == 34
    assert all(module_ids)
    assert module_ids[0] == "PM-01"
    assert module_ids[-1] == "PM-34"


def test_gift_order_topics_use_stable_business_code():
    assert make_business_code("선물주문") == "GFT"
    assert make_business_code("선물 주문") == "GFT"


def test_product_change_topics_use_change_business_code():
    assert make_business_code("상품변경") == "CHG"
    assert make_business_code("상품 변경") == "CHG"


def test_payment_topics_use_stable_business_code():
    assert make_business_code("결제") == "PAY"
    assert make_business_code("결제 관리") == "PAY"


def test_order_aftercare_topics_use_order_business_code():
    assert make_business_code("주문 상태/사후 관리") == "ORD"
    assert make_business_code("주문상태사후관리") == "ORD"


def test_termination_refund_cancel_topics_use_stable_business_code():
    assert make_business_code("해지/환불/취소") == "TRM"
    assert make_business_code("해지환불취소") == "TRM"
