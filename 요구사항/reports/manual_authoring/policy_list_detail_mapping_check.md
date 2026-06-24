# 정책 목록-상세 매핑 점검 리포트

- 점검 일시: 2026-05-09 Asia/Seoul
- 점검 대상: 수동 작성 큐 PM-01~PM-06
- 점검 기준: `policy_groups.items`의 각 항목이 동일 정책 ID의 `policy_details.name`에 1:1로 존재해야 함

| 문서 | 정책 그룹 | 정책 상세 | 결과 | 조치 |
|---|---:|---:|---|---|
| manual_authoring_PM-01_common_quality | 11 | 26 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |
| manual_authoring_PM-02_display_management | 15 | 43 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |
| manual_authoring_PM-03_product_list | 17 | 38 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |
| manual_authoring_PM-04_external_bp_service | 15 | 30 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |
| manual_authoring_PM-05_ai_search | 15 | 45 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |
| manual_authoring_PM-06_recommendation | 16 | 48 | 통과 | 정책 상세 제목 기준으로 목록 항목 정렬 완료 |

## 참고

- PM-01~PM-04는 이번 점검에서 정책 목록 항목을 정책 상세 제목 기준으로 보강했다.
- PM-05, PM-06은 점검 시점 기준 이미 목록-상세 매핑이 정합했다.
- 별도 레거시 초안 `manual_authoring_signup_withdrawal`은 목록-상세 매핑은 맞지만, 34개 작성 큐 대상이 아니며 중복 ID 등 구조 오류가 남아 별도 정리 대상이다.
