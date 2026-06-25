# PM-34 고객센터_매장안내 Topic Learning & Core Design

## 1. 주제 정의

고객센터_매장안내는 위치 검색이 아니라 고객 목적에 맞는 방문 가능 매장과 대리점 서비스를 찾는 오프라인 연결 업무다.
고객은 매장 위치, 영업 상태, 처리 가능 업무, 예약 가능 여부, 단골 매장, 가입·개통 매장 정보를 기준으로 방문 또는 대체 경로를 선택해야 한다.

## 2. 요구사항 분석

- 상세 요구사항 수: 9건
- 요구사항 그룹: {"STORE-H01": 8, "12INT-H03": 1}
- 핵심 상세 요구사항: 매장 찾기 지도·리스트 검색, 대리점 마이크로사이트, 콘텐츠 관리, 전용 URL, 단골 대리점, 처리 가능 업무·예약 가능 여부, 주변·단골 기반 안내, 가입·개통 매장 정보, 공통 팝업 전환

## 3. Core Design

- 액터: 고객, 운영자, 대리점 운영자, BSS, 채널 업무 시스템, 연계 시스템
- 고객 유즈케이스: 방문 가능한 매장 탐색, 방문 준비·대체 경로, 내 매장 정보·단골 매장 관리
- 운영 유즈케이스: 대리점 사이트·콘텐츠 운영, 매장안내 기준·품질 관리
- 시스템 유즈케이스: BSS 조건 판정, 채널 정보 노출·이력 처리, 위치·지도·URL·예약 연계

## 4. 검증 계획

- Schema/JSON Gate
- Stage Critical Gate
- Requirement Trace 9/9
- Health Check
- Asset/Rendering Check
- Codex 직접 Inspector와 Health Check

## 5. 최종 검증 결과

- Schema/JSON Gate: 통과
- Stage Critical Gate: 통과
- Requirement Trace: 9/9 자동 매칭, 수동 검토 필요 0건
- Health Check: 100/100, 우수, 필수 Gate 통과
- Asset/Rendering Check: 통과
- Codex 직접 Inspector: 통과
- 직접 검수 메모: PM-34는 FAQ, 공지, 상담 접수 문서가 아니라 방문 가능한 매장 탐색, 예약 가능 여부, 대리점 사이트·URL, 단골 매장, 가입·개통 매장 확인, 공통 매장찾기 팝업 전환 기준을 정의하는 문서로 유지했다.
