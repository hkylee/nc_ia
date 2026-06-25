# Mock 34 Regression Comparison - mock_34_regen_20260508_114357

- current: `/Users/kiwoo/NC/output/mock_34_regen_20260508_114357`
- previous: `/Users/kiwoo/NC/output/mock_34_regen_20260507_223403`
- topics: 34

## Aggregate
- mock_token_hits: current avg 0, min 0, max 0 / previous avg 58.41
- odd_total: current avg 0.09, min 0, max 2 / previous avg 9.47
- odd_visible: current avg 0, min 0, max 0 / previous avg 7.59
- function_name_dups: current avg 0, min 0, max 0 / previous avg 0
- policy_detail_name_dups: current avg 0.44, min 0, max 5 / previous avg 1.94
- generic_policy_group_desc: current avg 20.06, min 0, max 22 / previous avg 22
- direction_lines: current avg 2, min 2, max 2 / previous avg 0
- terms: current avg 28.65, min 27, max 30 / previous avg 28.65
- actors: current avg 6, min 6, max 6 / previous avg 6
- usecases: current avg 8, min 8, max 8 / previous avg 8
- y_usecases: current avg 4, min 4, max 4 / previous avg 4
- processes: current avg 15.47, min 15, max 16 / previous avg 15.47
- functions: current avg 30.94, min 30, max 32 / previous avg 30.94
- policy_groups: current avg 22, min 22, max 22 / previous avg 22
- policy_details: current avg 113.03, min 97, max 117 / previous avg 113.03
- avg_policy_len: current avg 58.76, min 55.6, max 61.4 / previous avg 58.61
- bad_phrase_hits_visible: current avg 0.24, min 0, max 8 / previous avg 0.26
- request_map_policy_details: current avg 24.03, min 8, max 28 / previous avg 24.03
- html_chars: current avg 146903.06, min 140669, max 153231 / previous avg 147798.94
- tables: current avg 41.94, min 41, max 43 / previous avg 41.94
- rows: current avg 235.32, min 222, max 244 / previous avg 234.94

## Largest Remaining Issues
### odd_total
- 선물주문: odd_total=2
- 카트장바구니: odd_total=1
- AI검색: odd_total=0
- 가이드라인공통품질적응형: odd_total=0
- 결제: odd_total=0
- 고객센터_FAQ공지이용안내: odd_total=0
- 고객센터_매장안내: odd_total=0
- 고객센터_통합허브: odd_total=0
### policy_detail_name_dups
- 데이터트래킹체계: policy_detail_name_dups=5
- 상품목록: policy_detail_name_dups=5
- 상품서비스혜택이용공유: policy_detail_name_dups=5
- AI검색: policy_detail_name_dups=0
- 가이드라인공통품질적응형: policy_detail_name_dups=0
- 결제: policy_detail_name_dups=0
- 고객센터_FAQ공지이용안내: policy_detail_name_dups=0
- 고객센터_매장안내: policy_detail_name_dups=0
### bad_phrase_hits_visible
- 주문상태사후관리: bad_phrase_hits_visible=8
- AI검색: bad_phrase_hits_visible=0
- 가이드라인공통품질적응형: bad_phrase_hits_visible=0
- 결제: bad_phrase_hits_visible=0
- 고객센터_FAQ공지이용안내: bad_phrase_hits_visible=0
- 고객센터_매장안내: bad_phrase_hits_visible=0
- 고객센터_통합허브: bad_phrase_hits_visible=0
- 나의가입정보: bad_phrase_hits_visible=0

## Sample HTML Stats
- NC_AI검색_정책서_간소화_v1.5.html: chars=66545, tables=23, rows=209
- NC_정책서_Full_v1.0_확정본.html: chars=218103, tables=106, rows=824
- NC_정책서_간소화_v1.0_확정본.html: chars=184965, tables=55, rows=297