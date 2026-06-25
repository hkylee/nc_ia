# warnings.md — 자동 검증 리포트

총 4건의 경고가 검출되었습니다.

## Broken cross-refs (참조된 ID가 정의되지 않음) (0건)

_없음_

## Orphan entities (정의되었지만 어디서도 참조되지 않음) (0건)

_없음_

## N:N 양방향 불일치 (0건)

_없음_

## ID 형식 위반 (알려진 접두사 외) (0건)

_없음_

## 누락 의심 정책 (0건)

_없음_

## Silent failure 의심 (입력 신호 vs 산출물 비율) (0건)

_없음_

## Unknown ID prefix (PREFIX_TO_TYPE 미등록) (0건)

_없음_

## Diagrams (다이어그램 추출 검증) (4건)

### Diagram 1 — uc (`다. 유즈케이스 다이어그램`)

- uc_diagram_low_confidence: 좌표 휴리스틱 추출 (정확도 보장 X). 의미 검증 필요.
- unmapped_uc_names: ['회원 상태 변경 처리', '회원 상태 조회/검증']
- entities_based_supplement: ['US-MBR-BSS-001', 'US-MBR-BSS-002', 'US-MBR-BSS-003', 'US-MBR-BSS-005', 'US-MBR-BSS-006', 'US-MBR-BSS-007'] (원본 SVG에 그려져 있지 않아 entities.usecases 기반으로 보완. actor↔UC edge는 의미 추측을 피해 생략 — entities.yaml/SVG fallback 참조)

### Diagram 2 — state (`3) 상태 전이 다이어그램`)

- _경고 없음_

### Diagram 3 — bpmn (`나. 전체 업무 흐름도`)

- bpmn_task_missing_from_mermaid: ['PR-MBR-CS-002-02', 'PR-MBR-CS-004-03'] (entities.processes에는 정의됐으나 원본 BPMN SVG에 task 노드로 그려져 있지 않음 — mapping.csv / SVG fallback / entities.yaml 참조)

