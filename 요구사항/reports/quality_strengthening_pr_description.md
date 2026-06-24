# NC Policy Agent Quality Strengthening PR Description

## 적용 결과

### S4. Evidence 권위 점수 계층화: full 적용
- `EvidenceItem`에 `authority_score`를 추가했다.
- 점수 체계는 요구사항 100, 템플릿 95, 샘플 80, AGENTS.md 75, 첨부 참고자료 70, 공개웹 보조 지식 30으로 적용했다.
- Evidence 선택 후 Writer/Blueprint/Context Pack에 전달되는 순서를 권위 점수 기준으로 재정렬한다.
- 공개웹 근거는 폐기하지 않고 하단 보조 근거로 유지한다.

### S5. Blueprint를 Chapter Writer에 고정 주입: full에 가까운 partial 적용
- Chapter Writer system instructions 상단에 `Approved Blueprint Contract`를 주입한다.
- 장별로 필요한 Blueprint만 추출해 넣어 전체 Blueprint 반복 주입은 피했다.
- 보완/patch/chunk/state 전용 작성 경로에도 동일하게 주입되도록 연결했다.

### S6. Inspector 범위 제한 prompt: full 적용
- Stage Inspector, Final Inspector, JSON Inspector 공통으로 범위 제한 지침을 강화했다.
- 현재 장, Approved Contract, Authoring Blueprint, 첨부 요구사항, 사용자 메모 안에서만 finding을 생성하도록 했다.
- 범위 밖 일반 보안·운영·UX 요구사항은 finding이 아니라 summary 관찰 메모 수준으로만 다루도록 했다.

### M1. Blueprint 2단계화: partial 적용
- 별도 LLM 호출을 추가하는 full 2-call 구조는 보류했다.
- 현재 Blueprint Architect가 이미 계층 계약과 장별 계약을 함께 만들고 있어, 우선 `blueprint_phases`로 Stage A/B를 명시하는 방식으로 적용했다.
- Stage A는 계층·입자도·근거 우선순위 결정, Stage B는 장별 Writer 기준 변환으로 정의했다.

## 제안과 다르게 구현한 부분
- M1은 별도 LLM 호출을 추가하지 않았다. 토큰과 실패 지점이 늘고, 현재 구조의 `hierarchy_skeleton`, `stage_contracts`, `first_draft_quality_plan`이 이미 2층 구조와 유사하기 때문이다.
- S4는 cutoff를 적용하지 않았다. 공개웹 지식을 자동 폐기하면 참고 가능한 후보까지 사라질 수 있어, 정렬과 충돌 규칙으로 제어했다.

## 새로 발견한 리스크
- Evidence 점수 정렬이 강해져 공개웹의 신선한 보조 지식이 뒤로 밀릴 수 있다. 다만 첨부자료 우선 원칙에는 부합한다.
- Blueprint system 주입으로 Writer 호출당 입력 토큰이 소폭 증가할 수 있다. 장별 추출과 2400자 제한으로 증가 폭을 줄였다.
- Inspector 범위 제한이 과하면 일부 보안·운영 리스크가 summary로만 남을 수 있다. 첨부 요구사항 또는 사용자 메모에 있는 항목은 예외로 finding 허용했다.

## 검증 결과
- Python 컴파일 검증 통과:
  - `src/evidence_store.py`
  - `src/context_assembler.py`
  - `src/evidence_map.py`
  - `src/blueprint_architect.py`
  - `src/chapter_agents.py`
  - `src/policy_inspector.py`
  - `src/orchestrator.py`
  - `src/policy_agent.py`
- Evidence authority 단위 검증 통과:
  - 첨부 요구사항이 공개웹보다 상단에 배치된다.
  - 샘플과 첨부 참고자료가 공개웹보다 상단에 배치된다.
- Writer system prompt 검증 통과:
  - `Approved Blueprint Contract`가 장별 Writer system instructions에 포함된다.
- Inspector prompt 검증 통과:
  - JSON Inspector instructions에 `검수 범위 제한` 지침이 포함된다.
- 추가 전수 검수 후 보완:
  - Patch 보완 호출에는 `Approved Blueprint Contract` system 재주입을 제거했다. Patch prompt 자체에 장별 기준서 핵심이 이미 포함되어 있어 중복 토큰을 줄이기 위함이다.
  - `blueprint_phases`가 Blueprint Architect 내부에만 있고 장별 Writer prompt 경로에는 빠져 있던 문제를 보완했다. 이제 `stage_blueprint_for_prompt()`와 compact blueprint에도 Stage A/B 정보가 포함된다.

## 미실행 항목
- 샘플 주제 2~3건 전체 생성 회귀는 실행하지 않았다.
- 사유: 실제 LLM 비용과 시간이 큰 테스트라 이번 변경에서는 컴파일 및 단위 검증까지만 수행했다.
- 권장 후속: `LLM 사용` 1건, `LLM 미사용` 1건으로 Blueprint/finding 수와 공개웹 덮어쓰기 여부를 비교한다.
