# 스킬: build-tsv

화면 초안 JSON(`draft_{id}.json`)을 읽어 행을 정렬하고, 최종 IA TSV 파일을 생성한다.

---

## 트리거

- `/create-ia` 내부 호출 (Step 3, draft-screens 완료 후)
- `/build-tsv {module_id}` — 단독 재실행

---

## 인풋

| 파일 | 경로 | 용도 |
|------|------|------|
| draft_{module_id}.json | `create-ia/output/draft_{module_id}.json` | 화면 초안 (타입·ID·컬럼값) |
| ia-writing-rules.md | `.claude/rules/ia-writing-rules.md` | 행 정렬·flow_type 규칙 |
| ia-column-spec.md | `.claude/rules/ia-column-spec.md` | TSV 헤더·컬럼 순서 |
| context-ia-example.tsv | `.claude/contexts/context-ia-example.tsv` | **TSV 출력 포맷 레퍼런스** — 실제 값·탭 구분자·빈칸 처리 확인용 |
| T4S_IA.tsv | `create-ia/input/ia/T4S_IA.tsv` | 레거시 IA 전체. `screen_id_new`(col 15) + `fadeout 권고 대상`(col 41) 컬럼으로 fadeout 판정 |
| T4S_IA_fadeout.tsv | `create-ia/input/ia/T4S_IA_fadeout.tsv` | fadeout 검토 목록. `기능`(col 2, 화면명) + `우선순위`(col 7, P1~P9) 컬럼 활용 |

---

## 아웃풋

파일: `create-ia/output/NC_IA_{MODULE_ID}.tsv`

### TSV 헤더 (고정 컬럼 순서)

```
domain\tuc_code\tuc_name\tpage_id\tdepth1\tdepth2\tdepth3\tdepth4\tdepth5\tdev_type\tdescription\tfrom\tflow_type\towner_page\towner_uc\tlegacy_screen_id\t출처서비스\t통합여부\t비고
```

> depth 컬럼은 필요한 만큼 사용한다. 화면 계층이 3단계를 넘으면 depth4, depth5까지 확장. 사용하지 않는 depth는 빈칸. depth3에 언더스코어(`_`) 등으로 계층을 이어붙이지 말 것.

---

## 비고 컬럼 — fadeout 검토대상 표기

각 행의 `legacy_screen_id`에 포함된 ID를 `T4S_IA.tsv`의 `screen_id_new`(col 15)와 대조하고,
화면 이름(마지막 depth 값)을 `T4S_IA_fadeout.tsv`의 `기능`(col 2)과 비교해 아래 규칙으로 `비고`를 채운다.

| 조건 | 비고 값 |
|------|---------|
| `T4S_IA_fadeout.tsv`에 화면명 매칭 (기능 컬럼) | `fadeout 검토대상 ({우선순위})` 예: `fadeout 검토대상 (P1)` |
| `T4S_IA.tsv`의 `fadeout 권고 대상` = "강력 권고" | `fadeout 검토대상 (강력 권고)` |
| `T4S_IA.tsv`의 `fadeout 권고 대상` = "검토 포함" | `fadeout 검토대상` |
| 두 소스 모두 매칭 | `T4S_IA_fadeout.tsv` 우선순위 표기 사용 |
| 해당 없음 | (빈칸) |

**매칭 기준:**
1. `legacy_screen_id` ↔ `screen_id_new` 정확 일치 (`;`로 구분된 각 ID를 개별 비교)
2. 화면명(마지막 depth) ↔ `기능` 컬럼 — 공백·괄호 제거 후 포함 여부 비교 (fuzzy)

---

## 행 정렬 규칙 (순서대로 적용)

1. **depth 계층 순**: depth1 → depth2 → depth3 순서로 부모 행이 자식 행보다 먼저
2. **UC 내 flow_type 순**: `기본(빈칸)` → `케이스 1` → `케이스 2` → … → `예외 1` → `예외 2` → …
3. **shared_pages 삽입 위치**:
   - 마스터 행(owner_uc 기준 위치)에 `owner_page=✅`, `owner_uc=✅` 기재
   - 각 ref_uc 위치에 동일 page_id로 레퍼런스 행 삽입 (`owner_page`, `owner_uc` 빈칸)
4. **부모 행 보장**: depth2가 있으면 해당 depth1만 있는 부모 행이 반드시 먼저 등장

---

## from 필드 처리 규칙

- **depth 이동(부모→자식)**: 기재 안 함
- **크로스모듈 진입**: 기재 (예: `마이`, `홈`)
- **형제 간 전환(같은 depth2 내 A→B)**: 기재 (예: `본인인증`)
- **복귀 흐름**: 기재 (예: `가입 완료`, `비밀번호 재설정`)
- 여러 출발 화면: `;`로 구분

---

## 상태 업데이트

완료 후 아래 두 파일 갱신:

**`create-ia/state.json`** 업데이트:
```json
{
  "MBR": {
    "status": "done",
    "row_count": 21,
    "last_run": "YYYY-MM-DD HH:MM"
  }
}
```

**`create-ia/log.md`** 한 줄 추가:
```
- YYYY-MM-DD HH:MM | build-tsv | MBR | 21행 생성 → create-ia/output/NC_IA_MBR.tsv
```

---

## 완료 리포트 (사용자에게 출력)

```
✅ NC_IA_{MODULE_ID}.tsv 생성 완료
   - 총 {N}행 ({UC 수}개 UC, {화면 수}개 고유 화면)
   - 공유 페이지: {shared page 수}개
   - 위치: create-ia/output/NC_IA_{MODULE_ID}.tsv
```

---

## 오류 처리

- draft 파일 없음 → "draft-screens를 먼저 실행하세요" 안내 후 중단
- 부모 행 누락 감지 → 자동 삽입 후 `⚠️ 부모 행 자동 추가: {화면명}` 경고
- from 값 dangling → `⚠️ from 불일치: '{값}' — 존재하지 않는 화면명` 경고 (TSV는 생성 완료)
- page_id owner_page/owner_uc ✅ 복수 → 첫 번째만 유지, 나머지 제거 후 경고
