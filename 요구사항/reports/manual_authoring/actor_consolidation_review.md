# Manual Authoring Actor Consolidation Review

## 기준
- 액터는 독립 책임 주체 기준으로만 유지한다.
- 세부 운영 역할, 엔진, 저장소, 알림, BSS 세부 시스템은 액터로 과분화하지 않고 기능·정책 책임으로 내린다.
- 기본 책임 단위는 고객, 운영자, 상담사, 채널 업무 시스템, 도메인/BSS 연계 시스템을 우선 사용한다.

## 정리 결과
| 문서 | 액터 수 변경 | 검증 |
|---|---:|---|
| PM-01 가이드라인/공통/품질/적응형 | 6 → 5 | validate_policy_spec / validate_stage_critical 통과 |
| PM-02 전시/관리 기능 | 6 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-03 상품 목록 | 6 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-04 외부 BP 서비스 관리 체계 | 6 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-05 AI 검색 | 7 → 5 | validate_policy_spec / validate_stage_critical 통과 |
| PM-06 추천 | 6 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-07 데이터 트래킹 체계 | 7 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-08 이벤트/미션 프로그램 | 7 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-09 외부 쿠폰 | 8 → 5 | validate_policy_spec / validate_stage_critical 통과 |
| PM-10 멤버십 혜택/T 플러스포인트 | 8 → 4 | validate_policy_spec / validate_stage_critical 통과 |
| PM-11 상품상세/담기 | 10 → 5 | validate_policy_spec / validate_stage_critical 통과 |

## 추가 관찰
- PM-04, PM-09, PM-10, PM-11은 요구사항 Trace 자동 매칭도 현재 0건 검토필요 상태다.
- PM-01, PM-02, PM-03, PM-05, PM-06, PM-07, PM-08은 액터 정리와 별개로 요구사항 Trace 자동 매칭이 약한 항목이 남아 있다.
- 해당 보완은 본문 품질과 요구사항 추적성 이슈이므로, 다음 별도 라운드에서 상세 요구사항명/설명 기준으로 보강하는 것이 안전하다.

## 다음 작성 기준 반영
- 신규 수동 작성 시 세부 운영자/세부 시스템을 먼저 액터로 만들지 않는다.
- 세부 주체 차이는 유즈케이스 설명, 기능 설명, 정책 항목의 책임 기준으로 표현한다.
- 시스템 액터명에는 `고객` 단어를 넣지 않는다. 검증기가 사람 액터로 오인할 수 있다.

## 2차 전반 반영 점검
- 1차 조정은 액터 목록, 유즈케이스 actor, 유즈케이스 다이어그램 중심이었다.
- 2차 조정에서 PM-02~PM-11의 프로세스, 기능, 정책 본문에 남은 세부 액터 표현까지 통합 표현으로 정리했다.
- `BSS`처럼 정책 판단 기준으로 필요한 시스템 개념은 유지하되, 세부 시스템이 액터처럼 보이는 표현은 도메인 연계 시스템 또는 채널 업무 시스템으로 통합했다.
- PM-02~PM-11 모두 잔여 세부 액터 표현 0건, validate_policy_spec / validate_stage_critical 통과 상태다.
- PM-01은 `BSS/연계 시스템`이 이미 통합 시스템 액터로 쓰이고 있어 유지했다.
