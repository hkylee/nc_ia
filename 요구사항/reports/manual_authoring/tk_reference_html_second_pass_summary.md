# TK Reference HTML 2차 보강 작업 기록

## 일시

2026-05-16

## 대상

- `output/reference_html/tk-task-01.html`부터 `output/reference_html/tk-task-12.html`까지 12개 설명형 HTML.

## 반영 내용

- 각 TK 문서에 `통합채널 연결 관점` 섹션을 추가했다.
- 각 과제를 개별 과제가 아니라 12개 과제 간 데이터, 상태, 인증, 동의, 알림, 고객지원 맥락이 연결되는 구조로 보강했다.
- 9번 `정책서 작성 시 남겨야 할 판단 기준`에 통합 관점 정책 항목을 추가했다.
- 10번 `정책서로 전환할 때의 핵심 질문`에 주제 간 연결을 검토하기 위한 결정 질문을 추가했다.
- 새 확정 수치나 근거 없는 사실은 추가하지 않고, 기존 TK 내용과 보유 지식의 해석 범위 안에서 보강했다.

## 공통 보강 축

- 여정 ID와 공통 상태 모델.
- 회원·인증·동의·알림의 기반 정책.
- 주문·결제·청구·사후관리 상태 연결.
- AI 추천·전시·상품 지식·고객지원의 피드백 루프.
- 가족·다회선·대리 처리 권한과 인증 기준.
- 상담·매장 전환 시 고객 입력과 처리 맥락 전달.

## 검증

- `python3 scripts/build_tk_task_queue.py`
- `python3 -m py_compile scripts/build_tk_task_queue.py`
- `python3 -m py_compile src/web_app.py`
- `node --check web/app.js`
- `git diff --check`
- 12개 HTML 모두에서 `통합채널 연결 관점` 섹션 포함 여부 확인.
- 이전에 제거한 보조 표현이 12개 HTML에 재등장하지 않았는지 확인.

## 배포

- 사용자가 별도로 요청하지 않아 Render 배포는 수행하지 않았다.
