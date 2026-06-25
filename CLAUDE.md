# IA 생성 워크스페이스

NOVA IA TSV 파일을 모듈별로 생성하는 워크스페이스.
정책서(policy) + T4S 기능내역서(ia) + PRD를 인풋으로 받아, `/create-ia` 커맨드 하나로 NC_IA_{MODULE}.tsv를 생성한다.

---

## 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/create-ia` | 모듈 선택 → read-module → draft-screens → build-tsv 순 실행 |
| `/read-module {id}` | 소스 읽기·맥락 파악만 재실행 |
| `/draft-screens {id}` | 화면 초안(타입 분류·ID 채번)만 재실행 |
| `/build-tsv {id}` | 행 정렬·TSV 완성만 재실행 |

---

## /create-ia 실행 흐름

```
1. .claude/contexts/context-module.tsv 읽기
   ┌──────────────────────────────────────────┐
   │  사용 가능한 모듈                         │
   │  [1] MBR  — 로그인/회원                  │
   │  [2] PRD  — 상품                         │
   │  [3] MY   — 마이                         │
   │  [4] ORD  — 주문/장바구니                │
   │  [5] SCH  — AI 검색                      │
   │  [6] DSP  — 홈/전시                      │
   │                                          │
   │  번호 또는 ID 입력                        │
   │  (복수: 1,2 또는 MBR,PRD / 전체: all):  │
   └──────────────────────────────────────────┘

2. [read-module] 선택 모듈별 맥락 파악
   → create-ia/output/context_{id}.md 생성

3. (중간 확인) UC 목록·화면 목록 리뷰
   → "계속 진행할까요? (Y/N)"

4. [draft-screens] 화면 초안 생성
   → create-ia/output/draft_{id}.json 생성

5. [build-tsv] TSV 완성
   → create-ia/output/NC_IA_{id}.tsv 생성
   → 행 수·공유페이지 수 리포트 출력
```

---

## 스킬 위치

| 스킬 | 경로 |
|------|------|
| read-module | `.claude/skills/read-module/SKILL.md` |
| draft-screens | `.claude/skills/draft-screens/SKILL.md` |
| build-tsv | `.claude/skills/build-tsv/SKILL.md` |

---

## 인풋 위치

| 유형 | 경로 | 내용 |
|------|------|------|
| IA 참조 | `create-ia/input/ia/` | T4S_기능내역서.csv (레거시 화면 원본) |
| 정책서 | `create-ia/input/policy/` | {module}_policy_spec.json |
| PRD | `create-ia/input/prd/` | {module}_prd.md (추후 채움) |

---

## 중간 산출물

| 파일 | 생성 스킬 | 용도 |
|------|----------|------|
| `create-ia/output/context_{id}.md` | read-module | UC·화면 목록, depth 구조, from 링크 |
| `create-ia/output/draft_{id}.json` | draft-screens | 스키마 고정 화면 초안 |

---

## 최종 아웃풋

`create-ia/output/NC_IA_{MODULE}.tsv`

---

## 작성 기준 문서

| 문서 | 경로 | 내용 |
|------|------|------|
| 멘탈 모델 | `.claude/rules/ia-mental-model.md` | depth vs from, 플로우맵 앵커, 검증 패스 |
| 컬럼 규격 | `.claude/rules/ia-column-spec.md` | 16개 컬럼, page_id·UC code 채번 |
| 작성 규칙 | `.claude/rules/ia-writing-rules.md` | 9개 규칙, flow_type 분류 |
| 예제 | `.claude/rules/ia-example.md` | MBR 풀세트 26행 워크드 예제 |
| dev_type | `.claude/rules/ia-dev-type.md` | 구현 유형 상세 가이드 |

---

## 모듈 레지스트리

`.claude/contexts/context-module.tsv` — 모듈 추가 시 이 파일에 행 추가
