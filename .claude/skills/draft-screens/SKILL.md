# 스킬: draft-screens

맥락 문서(`context_{id}.md`)를 읽어 각 화면의 dev_type을 분류하고, page_id·UC code를 채번한 구조화 초안(JSON)을 만든다.

---

## 트리거

- `/create-ia` 내부 호출 (Step 2, read-module 완료 후)
- `/draft-screens {module_id}` — 단독 재실행

---

## 인풋

| 파일 | 경로 | 용도 |
|------|------|------|
| context_{module_id}.md | `create-ia/output/context_{module_id}.md` | 화면·UC 목록, depth 구조 |
| ia-column-spec.md | `.claude/rules/ia-column-spec.md` | page_id·UC code 채번 규칙 |
| ia-dev-type.md | `.claude/rules/ia-dev-type.md` | dev_type 분류 기준·판단 흐름·예시 |
| ia-writing-rules.md | `.claude/rules/ia-writing-rules.md` | flow_type·shared page 규칙 |
| context-ia-example.tsv | `.claude/contexts/context-ia-example.tsv` | 컬럼 구조·값 형식 레퍼런스 |

---

## 아웃풋

파일: `create-ia/output/draft_{module_id}.json`

### 출력 스키마 (고정 — 반드시 준수)

```json
{
  "module_id": "MBR",
  "generated_at": "YYYY-MM-DD",
  "screens": [
    {
      "page_id": "NOVA-MBR-PG-001-0",
      "dev_type": "PG",
      "uc_code": "US-MBR-LGN-001",
      "uc_name": "로그인",
      "depth1": "로그인",
      "depth2": "",
      "depth3": "",
      "description": "회원 모듈 진입(미로그인 시)",
      "from": "마이; 가입 완료",
      "flow_type": "",
      "owner_page": "✅",
      "owner_uc": "✅",
      "legacy_screen_id": "TW-MY-MBR-MOPC-049-PG-001; TM-MY-SET-MO-01-PG-001",
      "출처서비스": "TW, TM",
      "통합여부": "●"
    }
  ],
  "shared_pages": [
    {
      "page_id": "NOVA-MBR-CP-001-0",
      "dev_type": "CP",
      "screen_name": "본인인증",
      "owner_uc": "US-MBR-JON-001",
      "ref_ucs": ["US-MBR-FND-001", "US-MBR-DMT-001", "US-MBR-WDR-001"]
    }
  ]
}
```

### page_id 채번 규칙

- `NOVA-{MODULE_ID}-{DEV_TYPE}-{SEQ}-0` 형식
- `{SEQ}`는 **같은 도메인+개발타입 내**에서 001부터 순서대로
- shared_pages의 공유 CP/BS는 owner UC 위치에서 001 채번 후 ref_ucs에서 동일 ID 참조
- 변형이 없으면 항상 `-0` 고정

### UC code 채번 규칙

- `US-{MODULE_ID}-{CAT}-{SEQ}` 형식
- `{CAT}`는 3자리 대문자, 프로세스 분류 (예: LGN=로그인, JON=가입, FND=찾기, WDR=탈퇴)
- `context_{id}.md`의 UC 목록 기준, 정책서 프로세스 ID에서 카테고리 추출

### shared_pages 식별 기준

- 같은 화면(본인인증 CP, 배송지 BS 등)이 2개 이상 UC에서 반복되면 공유 페이지로 추출
- `owner_uc`: 해당 UC 중 가장 먼저 나오는(depth 순서) UC
- `ref_ucs`: 나머지 참조 UC 목록

---

## 오류 처리

- context 파일 없음 → "read-module을 먼저 실행하세요" 안내 후 중단
- UC 목록이 비어있음 → 경고 후 사용자 확인 요청
- page_id 중복 발생 → 자동 증번 후 `⚠️ 중복 조정: {원래값} → {새값}` 로그
