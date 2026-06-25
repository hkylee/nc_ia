# Quality Strengthening Changelog

## 2026-05-03

- Evidence Store에 `authority_score`를 추가해 첨부 요구사항, 템플릿, 샘플, AGENTS.md, 첨부 참고자료, 공개웹 보조 지식의 우선순위를 코드 레벨에서 구분했다.
- Context Pack과 Topic Evidence Map에 `authority_score`를 노출해 Writer와 Blueprint Architect가 근거 권위를 확인할 수 있게 했다.
- Evidence 선택 결과를 Writer에 전달하기 전에 권위 점수 기준으로 재정렬해 공개웹 지식이 첨부 자료를 앞지르지 않게 했다.
- Blueprint Architect에 `blueprint_phases`를 추가해 Stage A 계층 결정과 Stage B 장별 기준 변환을 명시했다.
- Chapter Writer system prompt에 장별 `Approved Blueprint Contract`를 고정 주입했다.
- Inspector prompt에 범위 제한 지침을 추가해 범위 밖 일반론 finding 생성을 억제했다.
- 전수 검수 후 patch 보완 호출의 Blueprint system 중복 주입을 제거했다.
- 전수 검수 후 장별 Writer prompt 경로에 `blueprint_phases`가 전달되도록 보완했다.
