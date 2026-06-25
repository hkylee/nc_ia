# 산출물 활용 가이드 — 상품 상세/담기 (v0.11)

이 폴더는 NC 정책서 HTML을 AI 에이전트 친화 포맷으로 자동 변환한 결과입니다.
LLM 호출 없는 결정적 변환이므로, 같은 입력은 항상 같은 산출물을 생성합니다.

**통계**: 액터 5 · 유즈케이스 16 · 상태 18 · 상태 전이 22 · 프로세스 40 · 기능 36 · 정책 그룹 21 · 정책 항목 107 · 용어 14

---

## 산출물 구성

| 파일 | 용도 | 권장 활용 시점 |
|---|---|---|
| `00_INDEX.md` | 진입 가이드 · ID hierarchy 트리 · 다이어그램 3종 mermaid | **가장 먼저** — 전체 그림과 라우팅 |
| `usecase_<UC>.md` × N | UC 1개당 1파일. Process > Function > Policy Group > Policy Item 4단 구조 | AI 목업 input, 화면/컴포넌트 단위 설계 |
| `entities.yaml` | 모든 엔티티 + 양방향 cross_refs + hierarchy (영문 키, 평탄 구조) | 머신 처리, 스크립트 자동화 |
| `mapping.csv` | UC × PR × FN × PG × PI 평탄 N:N 매트릭스 | Excel pivot, 영향도 분석 |
| `warnings.md` | 자동 검증 결과 + 다이어그램 추출 주의사항 | 신뢰도 평가 |
| `diagrams/*.svg` | UC / State / BPMN 원본 SVG fallback | 다이어그램 시각 검토 |

---

## 활용 시나리오

### 1. AI 코드/목업 생성 input
Claude Code · Cursor · Copilot 등에 `usecase_<UC>.md` 를 컨텍스트로 넣으면 그 UC의 모든 Process / Function / Policy를 한 파일에서 grep · Read 가능합니다.

### 2. ID 추적
폴더 전체 grep으로 ID 1개를 추적:
```bash
grep -r "PR-MBR-CS-001-01" .
```

### 3. Excel pivot
`mapping.csv`를 Excel/Sheets로 import 후 pivot table로 UC ↔ PR ↔ FN ↔ PG ↔ PI의 N:N 영향도 분석.

### 4. 스크립트 자동화
`entities.yaml`을 Python yaml로 로드해 cross_refs 활용한 자동 검증·문서 생성.

---

## ID 체계

```
UC (Use Case)        US-{domain}-{area}-{nnn}
 └ PR (Process)      PR-{domain}-{area}-{nnn}-{nn}
    └ FN (Function)  FN-{domain}-{category}-{nnn}
       └ PG (Policy Group)   PG-{domain}-{topic}-{nnn}
          └ PI (Policy Item) POL-{domain}-{topic}-{nnn}-{nn}
```

- `entities.yaml#hierarchy` — UC → PR → FN 트리
- `entities.yaml#cross_refs` — 양방향 매핑 (function_to_processes, process_to_functions, process_to_policy_groups, policy_group_to_items, usecase_to_processes)

---

## 알려진 변환 특성 (사전 안내)

원본 HTML의 작성 방식상 다음 특성을 알고 활용하면 됩니다:

- **PR ↔ FN 매핑은 광역(union)으로 surface**: 원본 HTML의 "5장 가. 기능 목록" 표와 "4장 다. 프로세스 상세" 셀 두 곳에 PR-FN 매핑이 있고 두 곳이 다를 수 있습니다. 변환기는 데이터 보존을 위해 두 source를 union 처리합니다. **좁은 매핑만 필요하면** 원본 HTML "5장 가. 기능 목록"의 PR-단위 표를 참조하세요.

- **상태 전이의 UC 매핑이 부재할 수 있음**: 원본 상태 전이표에 UC ID 컬럼이 없으면 `entities.yaml#transitions[].usecase_id`가 빈 값으로 남습니다. UC 단위 추적이 필요하면 `entities.yaml#transitions[]` 전체를 보고 매핑하세요.

- **UC 다이어그램 보강 노드**: SVG 좌표 휴리스틱이 못 잡은 UC는 entities 기반으로 mermaid 본문에 보강됩니다. 정확한 actor↔UC 관계는 `warnings.md`의 `entities_based_supplement` 노트와 `diagrams/uc_*.svg` 원본을 함께 확인.

- **BPMN 누락 task**: 원본 BPMN에 그려져 있지 않으나 `entities.processes`에 정의된 PR은 `warnings.md`의 `bpmn_task_missing_from_mermaid` 노트에 명시됩니다. mapping.csv · entities.yaml로 보완.

- **PolicyItem 본문 "- " prefix · "세부 기능 구성" 공백 join**: 원본 HTML 텍스트가 거의 그대로 들어옵니다 (의미 손실 없음, 가독성만 cosmetic).

- **LLM 호출 없음**: 100% stdlib 기반 결정적 변환. 같은 HTML 입력은 항상 같은 산출물을 생성합니다.

---

## 빠른 시작

```bash
# UC 1개 컨텍스트로 AI 에이전트에게 전달
cat usecase_US-MBR-CS-001.md

# ID 전체 추적
grep -rn "FN-MBR-COM-001" .

# entities.yaml 스크립트 처리
python -c "
import yaml
d = yaml.safe_load(open('entities.yaml'))
for fn in d['functions']:
    print(fn['id'], fn['name'], fn['related_policy_group_ids'])
"

# mapping.csv 처리
python -c "
import csv
rows = list(csv.DictReader(open('mapping.csv')))
print(f'{len(rows)} mapping rows')
"
```

---

## 피드백

활용 중 발견한 문제·개선 제안은 변환기 담당자에게 전달해주세요.
