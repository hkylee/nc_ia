# 스킬: read-module

소스 파일을 읽어 모듈의 화면·흐름·레거시 ID를 파악하고, 구조화된 맥락 문서를 만든다.

---

## 인풋

| 파일 | 경로 | 용도 |
|------|------|------|
| NC_IA_NOVA.tsv | `create-ia/output/NC_IA_NOVA.tsv` | 크로스모듈 참조 (from 링크·depth1 기준). 생성 결과물이라 output에 위치 |
| T4S_기능내역서.tsv | `create-ia/input/ia/T4S_기능내역서.tsv` | 레거시 채널(TW/TM/TU/TD) 화면 목록 및 ID |
| {ref-policy}_policy_spec.json | `create-ia/input/policy/` | 정책 프로세스·그룹·비즈니스 규칙. 파일명은 context-module.tsv의 `ref-policy` 컬럼 값 사용 |
| T4S_요구사항정의서.tsv | `create-ia/input/prd/T4S_요구사항정의서.tsv` | PRD. 단일 파일로 모듈 코드로 필터링해 참조 (없으면 스킵) |
| context-module.tsv | `.claude/contexts/context-module.tsv` | 모듈 메타 (`module`, `etc`, `ref-policy` 컬럼) |

### T4S_기능내역서.tsv 컬럼 구조

| 컬럼 | 용도 |
|------|------|
| `module` | 서브모듈 코드 (DSP-PRDD, MY-MBR, ORD-JOIN 등) — screen_id_new의 2~3번째 세그먼트 결합 |
| `channel` | 채널 (TW, TM, TU, TD) |
| `screen_id_new` | 레거시 화면 고유 ID |
| `screen_name` | 화면명 |
| `기능명` | 화면 내 개별 기능 |
| `기능 세부 설명` | `[조건]/[입력]/[출력]/[예외]` 형식 상세 설명 |
| `기능그룹_1Depth` ~ `기능그룹_7Depth` | 화면 **내부** UI 컴포넌트 계층 — `description` 작성 및 기능 목록 파악에 활용 |

> **TU 채널 주의:** TU QA 행은 `기능그룹_1~3Depth`가 QA 메타데이터(점수·카테고리)로 채워지고, 실제 기능그룹은 `기능그룹_4Depth`부터 시작한다. description 재료로 쓸 때는 TU 행의 `기능그룹_1~3Depth`를 무시하고 `4Depth`부터 참조.

### 인풋 파일 식별 규칙
1. `context-module.tsv`에서 해당 `module_id` 행의 `ref-policy` 컬럼 값 추출
   - 값이 있으면: `create-ia/input/policy/{ref-policy}_policy_spec.json` 로드
   - 값이 없으면: `⚠️ policy 없음 — 스킵` 메모 후 T4S 기반으로만 진행
2. `create-ia/input/prd/T4S_요구사항정의서.tsv` 에서 `상위 요구사항 ID` 컬럼이 `{module_id}`를 포함하는 행 필터링
   - 예: `MBR` → `13MBR-H01-001` 형식의 행. 파일 없으면 스킵
3. `create-ia/input/ia/T4S_기능내역서.tsv` 에서 `module` 컬럼이 `-{module_id}`로 끝나는 행 필터링
   - 예: `MBR` → `MY-MBR`, `PRDD` → `DSP-PRDD`, `CARD` → `ORD-CARD`

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
- **depth 구조**: 정책서 프로세스 흐름 기반으로 depth1~3 구성. depth1은 해당 모듈의 앱 내 루트 네비게이션명 (예: `마이`, `홈`, `고객센터`)으로 정책서 context에서 판단.
- **from 링크**: 크로스모듈 진입만 (예: 마이에서 로그인 진입). depth 내 이동은 기재 안 함.
- **공유 페이지 후보**: 본인인증 CP처럼 여러 UC가 공유할 화면을 미리 식별.

---

## 오류 처리

- policy 파일 없음 → `⚠️ {파일명} 없음 — 스킵` 메모 후 나머지로 계속
- T4S에 해당 모듈 화면 없음 → `레거시 screen_id: (없음)` 으로 표기
- 파일 인코딩 오류 → 오류 메시지와 함께 중단 후 사용자에게 보고
