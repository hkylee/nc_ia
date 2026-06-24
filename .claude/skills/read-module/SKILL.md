# 스킬: read-module

소스 파일을 읽어 모듈의 화면·흐름·레거시 ID를 파악하고, 구조화된 맥락 문서를 만든다.

---

## 트리거

- `/create-ia` 내부 호출 (Step 1)
- `/read-module {module_id}` — 단독 재실행

---

## 인풋

| 파일 | 경로 | 용도 |
|------|------|------|
| NC_IA_NOVA.tsv | `create-ia/output/NC_IA_NOVA.tsv` | 크로스모듈 참조 (from 링크·depth1 기준). 생성 결과물이라 output에 위치 |
| T4S_기능내역서.csv | `create-ia/input/ia/T4S_기능내역서.csv` | 레거시 채널(TW/TM/TU/TD) 화면 목록 및 ID |
| {module_id}_policy_spec.json | `create-ia/input/policy/` | 정책 프로세스·그룹·비즈니스 규칙 |
| {module_id}_prd.md | `create-ia/input/prd/` | PRD 있으면 참조 (없으면 스킵) |
| context-module.tsv | `.claude/contexts/context-module.tsv` | 모듈 메타 (ref-policy, ref-ia, depth1) |

### 인풋 파일 식별 규칙
1. `context-module.tsv`에서 해당 `module_id` 행의 `ref-policy` 컬럼 값으로 policy 파일명 목록 추출
2. `create-ia/input/policy/` 에서 해당 파일들 로드 (존재하지 않는 파일은 경고 후 스킵)
3. T4S 기능내역서에서 해당 모듈 관련 레거시 화면만 필터 (screen_id에 모듈 코드 포함된 행)

---

## 아웃풋

파일: `create-ia/output/context_{module_id}.md`

### 출력 포맷 (고정 — 이 구조를 반드시 준수)

```markdown
# {MODULE_ID} 모듈 맥락

> 생성일: {YYYY-MM-DD} | 인풋: {사용한 policy 파일명들}

## UC 목록
| uc_code | uc_name | 설명 |
|---------|---------|------|
| US-{MOD}-{CAT}-001 | {UC명} | {1-2문장 요약} |

## 화면 목록
| 화면명 | 진입 경로 | dev_type 예상 | 레거시 screen_id | 채널 |
|--------|----------|--------------|-----------------|------|
| {화면명} | {depth 경로} | PG/BS/CP/... | TW-...; TM-... | TW, TM |

## depth 구조
- depth1: {모듈 루트명}
  - depth2: {섹션명}
    - depth3: {세부 화면명}
  - depth2: {섹션명}
    - ...

## from 링크 (크로스모듈·비depth 진입)
- {화면명} ← {출처 화면 이름} ({출처 모듈})

## 공유 페이지 후보
- {화면명}: UC {A}, {B}, {C} 공유 예정 (공통 CP/BS)
```

### 작성 지침

- **UC 목록**: policy_spec.json의 processes 또는 policies 기반. 너무 세분화하지 말고 사용자 시나리오 단위로 묶는다.
- **화면 목록**: UC별 주요 화면만 (helper 팝업 등 소규모 UI는 description으로 대신).
- **depth 구조**: `context-module.tsv`의 `depth1` 값이 루트. 정책서 프로세스 흐름 기반으로 depth2~3 구성.
- **from 링크**: 크로스모듈 진입만 (예: 마이에서 로그인 진입). depth 내 이동은 기재 안 함.
- **공유 페이지 후보**: 본인인증 CP처럼 여러 UC가 공유할 화면을 미리 식별.

---

## 오류 처리

- policy 파일 없음 → `⚠️ {파일명} 없음 — 스킵` 메모 후 나머지로 계속
- T4S에 해당 모듈 화면 없음 → `레거시 screen_id: (없음)` 으로 표기
- 파일 인코딩 오류 → 오류 메시지와 함께 중단 후 사용자에게 보고
