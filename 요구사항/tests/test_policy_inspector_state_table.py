import unittest

from src.policy_inspector import check_chapter_consistency, check_state_guide, transition_state_cells


STATE_HTML_WITH_USECASE_COLUMN = """
<h3>라. 상태 전이표</h3>
<h4>1) 상태 코드</h4>
<table>
<tbody>
<tr><td>ST-TIY-001</td><td>쿠폰 조회 중</td><td>조회 상태</td><td>후속 처리</td></tr>
<tr><td>ST-TIY-002</td><td>사용 가능</td><td>사용 가능 상태</td><td>후속 처리</td></tr>
</tbody>
</table>
<h4>2) 상태 전이 기준</h4>
<table>
<thead>
<tr><th>관련 유즈케이스</th><th>현재 상태</th><th>전이 이벤트</th><th>다음 상태</th><th>처리 기준 및 후속 처리</th></tr>
</thead>
<tbody>
<tr><td>외부 쿠폰 탐색 (US-TIY-CS-001)</td><td>쿠폰 조회 중</td><td>외부 쿠폰 탐색</td><td>사용 가능</td><td>조건 충족 시 사용 가능으로 전환하고 실패 시 제한 안내를 제공한다.</td></tr>
</tbody>
</table>
<h4>3) 상태 전이 다이어그램</h4>
"""


class PolicyInspectorStateTableTest(unittest.TestCase):
    def test_transition_state_cells_reads_five_column_table(self):
        cells = ["외부 쿠폰 탐색 (US-TIY-CS-001)", "쿠폰 조회 중", "외부 쿠폰 탐색", "사용 가능", "조건 충족"]

        self.assertEqual(("쿠폰 조회 중", "사용 가능"), transition_state_cells(cells))

    def test_transition_state_cells_reads_legacy_four_column_table(self):
        cells = ["쿠폰 조회 중", "외부 쿠폰 탐색", "사용 가능", "조건 충족"]

        self.assertEqual(("쿠폰 조회 중", "사용 가능"), transition_state_cells(cells))

    def test_state_guide_does_not_treat_usecase_column_as_current_state(self):
        findings = check_state_guide(STATE_HTML_WITH_USECASE_COLUMN, "06_state")

        self.assertNotIn("상태 전이명 불일치", {finding.title for finding in findings})

    def test_chapter_consistency_does_not_treat_usecase_column_as_state(self):
        findings = check_chapter_consistency(STATE_HTML_WITH_USECASE_COLUMN, "06_state")
        titles = {finding.title for finding in findings}

        self.assertNotIn("현재 상태 참조 불일치", titles)
        self.assertNotIn("다음 상태 참조 불일치", titles)


if __name__ == "__main__":
    unittest.main()
