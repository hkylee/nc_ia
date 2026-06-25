from src.policy_agent import normalize_sentence_breaks


def test_normalize_sentence_breaks_does_not_modify_svg_text():
    document = (
        '<p>문장 하나다. 다음 문장이다.</p>'
        '<svg role="img"><text>완료 기준을 저장한다.</text></svg>'
    )

    normalized = normalize_sentence_breaks(document)

    assert '<p>문장 하나다.<br/>다음 문장이다.<br/></p>' in normalized
    assert '<text>완료 기준을 저장한다.</text>' in normalized
    assert '<text>완료 기준을 저장한다.<br/></text>' not in normalized
