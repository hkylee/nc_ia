# Token Saving PR 1 Summary

## 반영 범위

- S1 동시 실행 lock을 추가했다.
  - 웹 생성 작업 시작 시 `output/.locks/{topic_slug}_{template_type}.lock`을 생성한다.
  - 30분 이내 동일 주제/템플릿 생성 작업이 실행 중이면 409 Conflict로 새 작업을 차단한다.
  - 작업 완료, 실패, 중단 시 lock 상태를 `completed`, `failed`, `aborted`로 갱신한다.

- S1 중단/재개 안전성을 조정했다.
  - 생성 중 중단 시 HTML, 단계 산출물, 품질 리포트는 정리한다.
  - 재개 가능한 checkpoint는 삭제하지 않는다.
  - 중단 이벤트에 최신 checkpoint 정보를 함께 남긴다.

- S5 Chain Matrix를 로컬 deterministic 모듈로 분리했다.
  - `src/chain_matrix.py`를 추가했다.
  - actor -> usecase -> process -> function -> policy_group 연결을 코드로 분석한다.
  - ID/참조 무결성, 누락 링크, orphan ID를 LLM 없이 계산한다.
  - `policy_inspector.py`는 해당 결과를 받아 LLM Inspector에 압축 전달한다.

- S6 Inspector pass cache를 정밀화했다.
  - cache version을 `inspector-pass-v4-contract-matrix`로 올렸다.
  - cache key에 현재 장 payload hash, 이전 장 contract hash, chain matrix hash, gate tier, min score를 포함했다.
  - 동일 JSON이라도 이전 장 계약이나 연결성 결과가 달라지면 재검수한다.
  - cache hit/miss 통계를 `spec.meta.inspector_cache_stats`에 기록한다.
  - 통과 장 상태를 `spec.meta.chapter_state`에 기록한다.

- S4 Patch payload 흐름을 안전하게 강화했다.
  - patch mode에서 patch target에 포함되지 않은 필드는 병합하지 않는다.
  - feedback이 8건 초과이거나 `structure/구조` category면 좁은 patch 대신 scoped full revision으로 전환한다.
  - patch prompt에 전체 장 JSON 재작성 금지, 지적 항목 외 수정 금지 규칙을 명시했다.

## 보류 범위

- JSON Patch 표준 스키마(`operation`, `target_path`, `value`) 전면 도입은 보류했다.
  - 현재 코드가 장별 배열 patch schema를 이미 사용하고 있어, 한 번에 JSON Patch로 바꾸면 Writer/merge/validator 영향 범위가 크다.
  - 이번 PR은 품질 영향이 없는 낭비 제거가 목적이므로 기존 patch 구조를 유지하며 안전 장치만 추가했다.

- Inspector 부분 재검수는 완전 구현하지 않았다.
  - 현재는 입력 fingerprint 기반 pass cache로 중복 재검수를 줄인다.
  - finding 단위 부분 재검수는 patch finding 상태 저장 구조를 더 정교하게 만든 뒤 별도 PR로 진행하는 편이 안전하다.

- 전체 LLM 회귀 및 토큰 측정은 수행하지 않았다.
  - API 비용이 발생하는 작업이라 이번 변경에서는 로컬 단위 테스트와 컴파일 검증만 수행했다.
  - 다음 검증 시 샘플 주제 1건으로 before/after token usage를 비교하면 된다.

## 검증

- `python3 -m py_compile src/chain_matrix.py src/policy_inspector.py src/orchestrator.py src/web_app.py src/chapter_agents.py tests/test_chain_matrix.py tests/test_patch_revision.py`
- `python3 -m unittest discover -s tests`

## 기대 효과

- 같은 작업 중복 실행과 중단 후 처음부터 재생성되는 낭비가 줄어든다.
- Inspector가 HTML/전체 JSON 대신 로컬 연결성 요약을 활용해 의미 검수에 집중할 수 있다.
- 이미 통과한 동일 장을 더 안전하게 캐시 재사용한다.
- 보완 루프에서 전체 장 재작성으로 빠지는 빈도를 줄인다.
