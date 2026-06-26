# /create-ia

NOVA IA TSV를 모듈별로 생성하는 메인 커맨드.
`read-module → (확인) → draft-screens → build-tsv` 순으로 실행한다.

---

## 실행 절차

### Step 0: 모듈 선택
`.claude/contexts/context-module.tsv`를 읽어 아래 형식으로 출력한다.

```
┌──────────────────────────────────────────────────┐
│  사용 가능한 모듈 (group: AI&Marketing)            │
│  [1]  UXP  — 가이드라인                           │
│  [2]  APP  — 공통                                 │
│  ...                                              │
│  (group: Shop)                                    │
│  [13] PRDD — 상품 상세                            │
│  ...                                              │
│                                                   │
│  번호 또는 모듈 코드 입력                           │
│  (복수: 1,2 또는 UXP,APP / 전체: all):            │
└──────────────────────────────────────────────────┘
```

사용자 입력을 파싱해 대상 `module_id` 목록을 결정한다.

### Step 1: read-module (각 모듈)
선택된 모듈 각각에 대해 `/read-module` 스킬을 실행한다.
→ `.claude/skills/read-module/SKILL.md` 지시에 따름
→ 아웃풋: `create-ia/output/context_{module_id}.md`

### Step 2: 중간 확인
각 모듈의 `context_{module_id}.md`에서 UC 목록·화면 목록을 요약해 사용자에게 표시한다.

```
📋 {MODULE_ID} 맥락 요약
   UC {N}개: {UC명 목록}
   화면 {M}개 | 공유 페이지 후보 {K}개

계속 진행할까요? (Y/N)
```

N 입력 시 해당 모듈 건너뜀.

### Step 3: draft-screens (확인된 모듈)
확인이 완료된 모듈에 `/draft-screens` 스킬을 실행한다.
→ `.claude/skills/draft-screens/SKILL.md` 지시에 따름
→ 아웃풋: `create-ia/output/draft_{module_id}.json`

### Step 4: build-tsv
`/build-tsv` 스킬을 실행한다.
→ `.claude/skills/build-tsv/SKILL.md` 지시에 따름
→ 아웃풋: `create-ia/output/NC_IA_{MODULE_ID}.tsv`

### Step 5: 최종 리포트
```
✅ 완료
   생성 파일: create-ia/output/NC_IA_{MODULE_ID}.tsv
   총 {N}행 | UC {UC수}개 | 고유 화면 {화면수}개 | 공유 페이지 {K}개
```

