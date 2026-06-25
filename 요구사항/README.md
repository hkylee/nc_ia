# NOVA 정책서 작성 자동화

HTML 템플릿을 기준으로 NOVA 정책서 HTML을 생성하는 Python CLI 및 로컬 웹 도구입니다.
템플릿의 CSS와 문서 폭은 유지하되, 본문은 AGENTS.md 작성 기준에 따라 개요, 주요 용어, 액터, 유즈케이스, 상태 전이, 프로세스, 기능, 정책 상세까지 실제 내용으로 작성합니다.

## 폴더 구조

```text
.
├── input/
│   ├── references/      # 참고 자료
│   ├── requirements/    # 요구사항 파일
│   ├── samples/         # 기존 정책서 샘플
│   └── templates/       # HTML 템플릿
├── output/
│   └── steps/           # 단계별 HTML 스냅샷
├── prompts/             # 향후 프롬프트 템플릿
├── src/
│   ├── __init__.py
│   ├── chapter_agents.py # 10개 장별 전문 작성 agent와 순차 작성 흐름
│   ├── llm_client.py   # OpenAI Responses API 기반 LLM 작성 클라이언트
│   ├── llm_routing.py  # agent별 모델/추론 강도 라우팅
│   ├── orchestrator.py # 주제 학습, 장별 agent 실행, 검수 loop 제어
│   ├── policy_agent.py  # CLI 진입점
│   ├── policy_inspector.py # 정책서 양식·가이드·샘플 수준 검수기
│   ├── policy_references.py # 참고자료 PDF/엑셀 분석 로더
│   ├── policy_requirements.py # 요구사항 엑셀 4depth 매칭 로더
│   ├── renderer.py      # 검증된 JSON 스펙을 HTML로 렌더링
│   ├── schema.py        # 정책서 JSON 스펙 생성기
│   ├── validator.py     # 정책서 JSON 연결성 검증기
│   ├── policy_writer.py # 이전 HTML 작성기
│   └── web_app.py       # 로컬 웹사이트 서버
├── web/                 # 웹 화면 파일
└── tests/               # 향후 테스트
```

## 새 작업자 로컬 개발 셋업

다른 작업자가 GitHub 저장소를 받은 뒤에는 아래 순서로 환경을 준비합니다.

```bash
git clone https://github.com/kiwookimu/ncstudio.git
cd ncstudio

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.example .env
```

처음 확인할 문서는 아래 순서를 권장합니다.

- `AGENTS.md`: Codex가 가장 먼저 참고해야 하는 정책서 작성/검수/보완 작업 지침입니다.
- `README.md`: 로컬 실행, LLM 설정, 테스트, 배포 기준을 확인하는 운영 안내입니다.
- `.env.example`: 로컬과 Render에 필요한 환경변수 예시입니다.
- `requirements-dev.txt`: `pytest`, `ruff` 등 개발·검증용 추가 패키지 목록입니다.

LLM 없이 흐름만 확인하려면 `.env`에서 `NC_MOCK_LLM=1`로 설정하거나 CLI에서 `--writer-mode mock`을 사용합니다.
실제 LLM 작성은 `.env`에 `OPENAI_API_KEY`를 설정한 뒤 `--writer-mode llm`으로 실행합니다.

로컬 웹 서버는 아래 명령으로 실행합니다.

```bash
python3 src/web_app.py
```

변경 후 기본 검증은 아래 명령을 기준으로 수행합니다.

```bash
python3 -m pytest -q
python3 -m py_compile src/web_app.py
node --check web/app.js
```

`node --check`는 Node.js가 설치된 환경에서만 실행합니다.
운영 배포 시에는 `.env`를 GitHub에 올리지 않고, Render Environment Variables에 필요한 값을 직접 등록합니다.

## 대용량 파생 DB 재생성

`reports/evidence/policy_graph.db`는 정책서 spec, 요구사항 DB, 참고자료 DB를 기반으로 만든 파생 그래프 인덱스입니다.
원천 데이터가 아니라 재생성 가능한 런타임 캐시이며, 현재 크기가 GitHub 단일 파일 제한인 100MB를 넘을 수 있으므로 저장소에는 포함하지 않습니다.

앱이 부팅될 때 `policy_graph.db`가 없으면 자동으로 다시 생성합니다.
그래프 입력은 문서 작업실에서 보이는 정책서 중 주제·템플릿별 최신 버전 spec으로 제한합니다.
Render persistent disk에 예전 버전 또는 고아 spec 파일이 남아 있어도 그래프 DB가 불필요하게 커지지 않도록 하기 위한 기준입니다.
이미 DB가 있는 경우에는 최신 spec 변경·삭제분만 증분 갱신하고, 요구사항 DB나 참고자료 DB가 바뀌었거나 증분 갱신 중 오류가 나면 안전하게 전체 재생성으로 전환합니다.
전체/증분 갱신 후에는 SQLite `VACUUM`을 실행해 삭제된 그래프 행의 디스크 공간을 반환합니다.
기본값은 웹 서버 시작을 막지 않도록 백그라운드 생성이며, 생성 상태와 증분/전체 모드는 `/api/health`의 `policyGraph` 항목에서 확인할 수 있습니다.

```bash
curl http://127.0.0.1:8000/api/health
```

수동으로 즉시 재생성하려면 아래 명령을 실행합니다.

```bash
python3 scripts/repair_requirement_sources.py output --rebuild-graph
```

Render에서는 persistent disk 기준으로 아래 경로에 생성됩니다.

```text
/var/data/ncstudio/reports/evidence/policy_graph.db
```

관련 환경변수는 아래와 같습니다.

```text
NC_POLICY_GRAPH_BOOTSTRAP_ENABLED=1   # 부팅 시 자동 생성 사용
NC_POLICY_GRAPH_BOOTSTRAP_ASYNC=1     # 백그라운드 생성
NC_POLICY_GRAPH_BOOTSTRAP_FORCE=0     # 매번 강제 재생성 여부
NC_POLICY_GRAPH_INCREMENTAL_ENABLED=1 # 정책서 spec 변경분 증분 갱신 사용
NC_POLICY_GRAPH_DB_PATH=...           # 필요 시 생성 위치 override
```

`policy_graph.db`가 아직 생성 중이거나 없는 상태에서도 사이트 조회와 문서 작업은 동작합니다.
다만 Health Check와 Inspector의 그래프 기반 보조 신호는 생성 완료 전까지 제한될 수 있습니다.

`reports/evidence/feature_inventory.db`는 `input/references/SKT_T4S_기능내역서_정리.xlsx`를 정제해 만든 기능내역서 인덱스입니다.
원본 엑셀은 유지하고, SQLite에는 채널, 화면, 기능명, 기능 세부 설명, 조건, 입력, 출력, IA Depth, 신뢰도, 중복 여부, 정제 이슈를 분리해 저장합니다.
중복으로 판정된 행은 삭제하지 않고 `is_duplicate=1`로 표시하며, 중복 제거 기준 조회는 `feature_unique_rows` 뷰를 사용합니다.
DB 크기가 커질 수 있으므로 GitHub 100MB 제한에 걸리면 DB 파일은 제외하고 원본 엑셀과 아래 재생성 스크립트를 기준으로 복구합니다.

수동으로 기능내역서 DB를 다시 만들려면 아래 명령을 실행합니다.

```bash
python3 scripts/build_feature_inventory_db.py --force
```

요구사항, 참고자료, 기능내역서, Topic Knowledge를 한 번에 갱신하려면 아래 명령을 사용합니다.

```bash
python3 scripts/refresh_source_knowledge.py
```

## 실행

```bash
python3 src/policy_agent.py create --topic "상품 상세" --template input/templates/template.html
```

현재 `input/templates/`에는 아래 2개 HTML 템플릿이 있습니다.

```text
NC_정책서_Full_템플릿_최종본.html
NC_정책서_간소화_템플릿_최종본.html
```

`input/templates/template.html` 파일이 없거나 `input/templates` 폴더를 넘기면 Full 버전과 간소화 버전 중 무엇으로 작성할지 먼저 물어봅니다.
자동 실행처럼 물어보면 안 되는 상황에서는 `--template-type`을 지정합니다.

```bash
python3 src/policy_agent.py create --topic "상품 상세" --template input/templates
python3 src/policy_agent.py create --topic "상품 상세" --template simple
python3 src/policy_agent.py create --topic "상품 상세" --template full
python3 src/policy_agent.py create --topic "상품 상세" --template input/templates --template-type simple
python3 src/policy_agent.py create --topic "상품 상세" --template input/templates --template-type full
python3 src/policy_agent.py create --topic "상품 상세" --template simple --requirements-dir input/requirements
python3 src/policy_agent.py create --topic "상품 상세" --template simple --references-dir input/references
python3 src/policy_agent.py create --topic "상품 상세" --template simple --writer-mode llm --model gpt-5.2 --reasoning-effort xhigh
```

최종 산출물 예시는 아래와 같습니다.

```text
output/상품상세_policy_spec.json
output/상품상세_authoring_blueprint.json
output/NC_상품상세_정책서_간소화_v0.10.html
output/NC_상품상세_정책서_간소화_v0.10_전체업무흐름도.bpmn
output/NC_상품상세_정책서_간소화_v0.10_전체업무흐름도_viewer.html
output/NC_상품상세_정책서_Full_v0.10.html
```

같은 주제로 다시 실행하면 `v0.11`, `v0.12`처럼 버전이 자동 증가하고, `v0.19` 다음은 `v0.20`으로 이어집니다.
BPMN 산출물은 BPMN 2.0 XML로 저장하고, 같은 위치에 `bpmn-js` 기반 bpmn.io viewer HTML을 함께 생성합니다.
정책서 HTML 안에는 인라인 bpmn.io viewer와 정적 SVG 폴백이 포함되어, 네트워크가 막힌 환경에서도 업무 흐름을 확인할 수 있습니다.

생성되는 정책서는 템플릿 placeholder를 단순 치환하지 않고, 먼저 정책서 내용을 JSON 스펙으로 작성한 뒤 검증을 통과한 스펙만 HTML로 렌더링합니다.
작성 시작 전에는 요구사항과 참고자료를 확인해 주제 학습 요약과 Authoring Blueprint를 만들고, 템플릿과 샘플 HTML의 구성 수준을 분석해 장별 agent 지침으로 사용합니다.
이때 원천 자료는 Evidence Store로 표준화되고, 각 장별 agent 실행 직전 Context Assembler가 해당 장에 필요한 요구사항, VoC, IA, 전략, 샘플, 작성 기준 근거만 선별해 Context Pack으로 전달합니다.
현황 분석에서 완성한 벤치마킹, 고객 조사, 임직원 인터뷰, IA 분석, VoC 종합/상세 HTML 장표도 `analysis_synthesis` 근거로 색인되어 정책서 작성과 Inspector 검토의 보강 지식으로 사용됩니다.
단, `작성 예정입니다` 상태의 placeholder와 TK 과제정의 설명형 HTML은 지식화 대상에서 제외하고, 분석 장표가 요구사항·TK 원천과 충돌하면 원천을 우선합니다.
Authoring Blueprint에는 요구사항 카드, 분석 신호, 장별 작성 기준, 요구사항 coverage matrix, Evidence Gap이 저장됩니다.
각 agent는 담당 장 작성 시 Blueprint의 `target_requirement_ids`, `analysis_focus`, `evidence_summaries`를 우선 반영하며, 근거 없는 일반론으로 범위를 확장하지 않도록 지시받습니다.
최종 JSON에는 내부 검증용 `trace_matrix`, `evidence_gaps`, `meta.authoring_blueprint`, `meta.context_pack_runs`가 저장되어 어떤 산출물이 어떤 요구사항·근거 묶음에서 작성되었는지 추적할 수 있습니다.
LLM 작성 모드에서는 이 주제 학습 단계도 LLM이 수행하며, 분석 결과는 JSON의 `meta.topic_learning.llm_learning`에 저장됩니다.

정책서는 하나의 writer가 한 번에 작성하지 않고 아래 10개 전문 agent가 순서대로 이어서 작성합니다.
이 실행 순서는 `src/orchestrator.py`가 제어하며, `src/chapter_agents.py`는 각 장별 agent의 작성 책임만 담당합니다.

```text
01 overview
02 terms
03 actors
04 usecases
05 usecase_diagram
06 state
07 process
08 functions
09 policies
10 final_check
```

각 agent는 현재까지 작성된 JSON 스펙을 먼저 리뷰한 뒤 자신이 담당한 장만 보완합니다.
agent가 장 작성을 마치면 부분 JSON 검증과 JSON Critical Gate를 먼저 실행합니다.
Critical Gate는 액터-유즈케이스, 유즈케이스-프로세스, 프로세스-기능, 프로세스-정책, 상태-상태전이 같은 구조 오류를 HTML/LLM inspector 전에 빠르게 차단합니다.
Critical Gate를 통과한 경우에만 HTML 렌더링과 inspector 검수를 실행합니다.
inspector는 항상 문서 처음부터 현재 작성된 챕터까지 누적 범위를 점검합니다.
inspector 점수가 기준에 미달하거나 오류가 있으면 보완점을 같은 agent에게 다시 보내고, 해당 agent가 같은 챕터를 재작성합니다.
기준 점수 이상에 도달한 결과만 다음 agent가 이어받습니다.
전체 장이 끝난 뒤에는 최종 JSON 검증과 전체 문서 inspector 검수를 한 번 더 실행합니다.

JSON의 `meta.chapter_agents`에는 장별 agent 지침이 저장되고, `meta.chapter_agent_runs`에는 실제 순차 작성 이력이 저장됩니다.
`meta.topic_learning`에는 작성 전 확인한 요구사항과 참고자료 기반의 주제 학습 요약이 저장됩니다.

LLM 작성 엔진을 사용하려면 OpenAI API 키를 환경변수 또는 `.env` 파일에 설정합니다.

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.4"
export OPENAI_REASONING_EFFORT="high"
```

작성 엔진은 아래 4가지 모드를 지원합니다.

```text
auto  - OPENAI_API_KEY가 있으면 LLM을 사용하고, 없으면 로컬 작성기를 사용
llm   - 반드시 LLM을 사용. API 키가 없거나 호출에 실패하면 생성 중단
local - LLM 없이 로컬 작성기만 사용
mock  - API 호출 없이 LLM 작성 경로를 테스트. 웹 테스트는 NC_MOCK_LLM=1로 전환
```

LLM 작성 시 각 chapter agent는 OpenAI Responses API의 Structured Outputs 방식으로 담당 장 JSON만 생성합니다.
API 키가 있어 LLM 호출을 실제로 시작한 뒤 일시 오류, 출력 한도, JSON 형식 오류, 연결성 검증 오류가 발생하면 로컬 작성기로 대체하지 않고 LLM 재시도를 수행합니다.
재시도해도 해결되지 않거나 API 키, 모델 권한, 과금, 지원하지 않는 모델/추론 강도처럼 재시도로 해결할 수 없는 오류는 오류를 반환합니다.
`auto` 모드는 API 키가 아예 없을 때만 로컬 작성기를 사용합니다.
`mock` 모드는 오케스트레이터, 체크포인트, 렌더링, 웹 진행 팝업을 검증하기 위한 테스트 모드이며 실제 문서 품질 검증에는 사용하지 않습니다.
웹사이트는 항상 `llm` 모드로 실행하므로 API 키, 모델, 네트워크 연결에 문제가 있으면 로컬 작성기로 조용히 대체하지 않고 생성 오류를 반환합니다.
모델 ID는 계정에서 사용 가능한 값을 입력해야 하며, `gpt-5.5`처럼 특정 모델을 쓰려면 해당 모델이 OpenAI 계정의 `/v1/models` 목록에 있어야 합니다.
추론 품질과 비용의 균형을 맞추기 위해 역할별 LLM 라우팅을 적용합니다.
기본 모델은 서버의 `.env`에 지정된 `OPENAI_MODEL`을 사용하되, overview·terms·actors·final_check는 낮은 추론 강도, usecases·state·process·functions·policies는 중간 추론 강도, final inspector는 높은 추론 강도로 실행합니다.
PI Agent는 프로세스 혁신성, As-Is/To-Be 차이, 안티패턴을 판단하는 고난도 평가 역할이므로 기본 라우팅을 `gpt-5.5` / `xhigh`로 둡니다.
단, `mock` 모드에서는 PI Agent도 API를 호출하지 않고 `mock-policy-agent` / `none` 경로로 동작합니다.
process·functions·policies처럼 출력량이 큰 장은 하나의 큰 JSON으로 요청하지 않고 ID 묶음 단위로 분할 작성합니다.
이 방식은 선행 장의 ID와 명칭을 유지하면서 각 묶음을 작성한 뒤 다시 병합하므로, 장간 연결성을 유지하면서 출력 한도 재시도와 추론 토큰 낭비를 줄입니다.
기본 출력 한도는 `OPENAI_MAX_OUTPUT_TOKENS=32000`으로 운영하며, process·functions는 장별 최대 22000, policies는 장별 최대 26000까지 사용할 수 있습니다.
분할 작성 중 특정 구간의 LLM 호출이 실패하면 해당 구간을 로컬 초안으로 대체하지 않고, 보정 지시를 추가해 LLM으로 다시 작성합니다.
유즈케이스 다이어그램은 JSON 기반 Mermaid 렌더링으로 생성하므로 기본적으로 LLM을 사용하지 않습니다.
inspector는 규칙 기반 검수를 먼저 실행하고, process·functions·policies 또는 기준 미달 장에 대해서만 LLM inspector를 추가 실행합니다.
보완 루프가 발생하면 해당 agent는 자동으로 한 단계 높은 추론 강도로 escalation됩니다.
LLM 출력이 `max_output_tokens`에 걸리면 같은 요청의 한도 증설 재시도는 기본 3회 수행하고, 장별 작성 단계도 기본 5회까지 보정 재시도합니다.
웹사이트는 작성 엔진과 모델을 선택하지 않고 항상 서버의 `.env` 설정과 역할별 라우팅 규칙을 사용합니다.
웹 화면 상단에는 서버가 읽은 LLM 모델과 reasoning 설정이 표시됩니다.
정책서 생성 시 로컬 요구사항과 `input/references` 분석을 기준으로 Context Pack을 구성합니다.

JSON 스펙은 아래 구조를 사용합니다.

```json
{
  "meta": {},
  "history": [],
  "overview": {
    "scope": [],
    "principles": []
  },
  "terms": [],
  "actors": [],
  "usecases": [],
  "states": [],
  "state_transitions": [],
  "processes": [],
  "functions": [],
  "policy_groups": [],
  "policy_details": [],
  "final_check": []
}
```

검증기는 ID 형식과 연결성을 확인합니다.
예를 들어 `ACT-{업무코드}-001`, `US-{업무코드}-...`, `PR-{업무코드}-...`, `FN-{업무코드}-...`, `PG-{업무코드}-...`, `PI-{업무코드}-...` 형식을 검사하고, 유즈케이스 actor, 프로세스 관련 정책명, 정책 상세의 정책 ID가 실제 정의 목록에 존재하는지 확인합니다.

검증을 통과한 정책서는 아래 내용을 장별로 렌더링합니다.

작성 전에 `input/requirements/`의 엑셀 파일에서 `요구사항 통합 list` 시트를 읽고, `Depth 4`가 정책서 주제와 일치하는 요구사항을 확인합니다.
`편집 현황*`이 `삭제`인 항목은 제외하고, 관련 요구사항은 원문을 정책서에 나열하거나 추적표로 넣지 않습니다.
대신 고객 과업, 검증 조건, 운영 기준, 예외 처리 기준을 분석해 프로세스, 기능, 정책 판단 기준에 자연스럽게 반영합니다.

또한 작성 전에 `input/references/`의 PDF와 엑셀 참고자료를 읽고, 정책서 주제와 관련된 채널 전략, 고객 조사, VoC, IA, 벤치마킹, AI 관점을 분석합니다.
참고자료 원문을 그대로 복사하지 않고, 목적 기반 진입, 셀프 처리, 고객 불편 제거, IA 경로 정합성, 비교·선택 기준, AI 신뢰도 같은 정책 판단 기준으로 재구성합니다.
참고자료 분석을 생략해야 할 때는 `--no-references`를 사용할 수 있습니다.

- 문서 히스토리
- 개요와 설계 원칙
- 주요 용어
- 액터와 유즈케이스
- 유즈케이스 다이어그램과 상태 전이표
- 프로세스 목록과 전체 업무 흐름도
- 기능 목록
- 정책 목록과 정책 상세
- 최종 점검 기준

Full 버전은 간소화 버전에 더해 프로세스 상세와 기능 상세를 포함합니다.

생성 과정에서는 각 장 작성 후 inspector가 양식, 가이드 준수, 장별 연결성, 샘플 수준을 검수하고 리포트를 `reports/inspections/`에 저장합니다.
기본 통과 기준은 90점이며, 각 챕터별 작성-검수-보완 loop는 최대 3회 수행합니다.
기준은 `--inspector-min-score`, `--inspector-max-loops` 옵션으로 조정할 수 있습니다.
전체 장을 모두 작성한 뒤에도 최종 inspector를 한 번 더 실행합니다.
inspector는 템플릿 문서의 작성 가이드를 기준으로 범위 6요소, 설계 원칙 수량, 액터·유즈케이스 Y/N 기준, 상태 전이명 정합성, 다이어그램 ID 표기, 프로세스 관련 기능·정책, 기능 세부 구성, 정책 상세의 실제 판단 기준, TBD 보완 정보, 개인정보·로그·운영·요구사항 점검 항목을 확인합니다.
또한 액터-유즈케이스, 상태-상태전이, 유즈케이스-프로세스, 프로세스-기능, 프로세스-정책, 정책 목록-정책 상세 간 참조가 실제 문서 안에서 일치하는지 검증합니다.
LLM 작성 모드에서는 규칙 기반 inspector가 문서 처음부터 현재 범위까지 누적 검수하고, 품질 리스크가 큰 장 또는 기준 미달 장에 대해서 LLM inspector가 추가 검수합니다.
LLM inspector 사용 여부와 모델 정보는 각 inspection 리포트의 `metrics.llm_inspector`에 저장됩니다.

생성된 문서는 별도로 검수할 수도 있습니다.

```bash
python3 src/policy_agent.py inspect --file output/NC_상품상세_정책서_간소화_v0.10.html --template simple --scope full
```

## 웹사이트 실행

정책서 작성을 요청하고 생성 결과를 미리보기로 확인하는 로컬 웹사이트를 실행할 수 있습니다.

```bash
python3 src/web_app.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

웹사이트에서 할 수 있는 일:

- 정책서 주제 입력
- Full 버전 또는 간소화 버전 선택
- 작성 요청 메모 입력
- 정책서 HTML 생성
- `output/` 폴더의 생성 결과 목록 확인
- 생성된 정책서 미리보기 및 새 창 열기
- 생성된 정책서 inspector 검수 결과 확인
- 생성된 정책서 삭제

## Render 배포

현재 프로젝트는 정적 HTML만 올리는 구조가 아니라 Python 서버와 `/api` 엔드포인트를 함께 사용합니다.
그래서 GitHub Pages보다 Render 같은 웹 서비스 배포가 더 적합합니다.

이 저장소에는 Render용 설정 파일이 포함되어 있습니다.

- [render.yaml](/Users/kiwoo/NC/render.yaml)
- [requirements.txt](/Users/kiwoo/NC/requirements.txt)

### 배포 순서

1. Render에서 `New +` → `Web Service`를 선택합니다.
2. GitHub 저장소 `kiwookimu/ncstudio`를 연결합니다.
3. 루트의 `render.yaml`을 그대로 사용합니다.
4. 배포 후 Render 환경변수에 OpenAI 설정을 입력합니다.

### 필수 환경변수

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4
OPENAI_REASONING_EFFORT=medium
OPENAI_MODEL_TOPIC_LEARNING=gpt-5.5
OPENAI_MODEL_BLUEPRINT_ARCHITECT=gpt-5.5
OPENAI_MODEL_PI_AGENT=gpt-5.5
OPENAI_REASONING_EFFORT_PI_AGENT=xhigh
```

필수는 `OPENAI_API_KEY`이고, 나머지는 기본값을 유지해도 됩니다.
PI Agent 관련 환경변수를 생략하면 코드 기본값으로 `gpt-5.5` / `xhigh`를 사용합니다.

### 사용량/비용 집계

웰컴 페이지의 Agent별 행은 서비스 내부 로그(`reports/logs/llm_calls.jsonl`) 기준으로 집계합니다.
OpenAI의 조직 Usage API는 내부 Agent명을 알 수 없기 때문에 Agent별 행에는 사용하지 않습니다.

상단 `총 호출`, `총 토큰`, `총 비용`은 기본적으로 기존 `OPENAI_API_KEY`로 OpenAI 조직 Usage/Costs API를 조회합니다.
이 키에는 조직 Usage/Costs 조회 권한(`api.usage.read`)이 필요합니다.
기존 키로 Usage API 권한이 부족하면 화면에 `OpenAI 집계 권한 없음`으로 표시하고 로컬 로그 추정치를 보여줍니다.
별도 조회 키가 필요한 운영 환경에서만 `OPENAI_USAGE_API_KEY`로 덮어쓸 수 있습니다.
설정하지 않으면 화면에 `로컬 로그 기준 · OpenAI 집계 미설정`으로 표시되고, 로컬 로그 추정치를 보여줍니다.

```text
OPENAI_API_KEY=...
OPENAI_USAGE_DASHBOARD_ENABLED=1
OPENAI_USAGE_LOOKBACK_DAYS=30
```

우리 서비스 외 호출이 섞이지 않게 하려면 가능한 경우 아래 필터도 함께 설정합니다.

```text
OPENAI_USAGE_PROJECT_IDS=...
OPENAI_USAGE_API_KEY_IDS=...
```

### 저장 경로

Render는 재시작이나 재배포 때 임시 파일 시스템이 초기화될 수 있으므로, 산출물과 리포트는 영구 디스크 경로로 분리하는 편이 안전합니다.
기본 Render 설정은 아래 경로를 사용합니다.

```text
NC_OUTPUT_DIR=/var/data/ncstudio/output
NC_REPORTS_DIR=/var/data/ncstudio/reports
NC_SITE_SETTINGS_PATH=/var/data/ncstudio/reports/site_settings.json
NC_USER_DB_PATH=/var/data/ncstudio/reports/auth/users.sqlite3
NC_REFERENCE_DB_PATH=/var/data/ncstudio/reports/evidence/reference_evidence.db
NC_FEATURE_INVENTORY_DB_PATH=/var/data/ncstudio/reports/evidence/feature_inventory.db
NC_TOPIC_KNOWLEDGE_DIR=/var/data/ncstudio/reports/evidence/topic_knowledge
```

로컬에서는 이 값을 비워두면 기존처럼 저장소 안의 `output/`, `reports/`를 그대로 사용합니다.

웰컴 페이지의 `LLM 사용 여부`는 코드 배포물이 아니라 서버 런타임 설정입니다.
Render에서는 `NC_SITE_SETTINGS_PATH=/var/data/ncstudio/reports/site_settings.json`에 저장하므로 Git push, 재배포, 서비스 재시작으로 덮어쓰지 않습니다.
관리자가 화면에서 켜거나 끈 값이 전체 사용자에게 공통 적용되며, 이 파일은 Git에 올리지 않습니다.

### 회원 계정 DB 보관 기준

회원가입 정보는 코드 배포물과 분리된 런타임 데이터입니다.
Render에서는 `NC_USER_DB_PATH=/var/data/ncstudio/reports/auth/users.sqlite3`처럼 영구 디스크 아래 SQLite DB로 저장합니다.
이 파일은 Git에 올리지 않으며, 로컬의 `reports/auth/` 데이터도 `.gitignore`에 의해 배포 대상에서 제외됩니다.

기존 `reports/auth/users.json` 계정 파일이 있으면 새 SQLite DB가 비어 있을 때 자동으로 1회 가져옵니다.
따라서 코드 재배포, Git push, 로컬 파일 배포는 서버의 가입자 DB를 덮어쓰지 않습니다.
단, Render 디스크를 직접 삭제하거나 `NC_USER_DB_PATH`를 임시 파일 시스템 경로로 바꾸면 계정 정보가 유실될 수 있습니다.

### 주의 사항

- `.env`는 GitHub에 올리지 않고 Render 환경변수로만 관리합니다.
- `NC_SESSION_SECRET`은 운영 환경변수로 고정해 두어야 재배포 후에도 로그인 세션 서명이 안정적으로 유지됩니다.
- OCR 품질을 높이려면 Render 런타임에 `tesseract` 시스템 패키지가 추가로 필요할 수 있습니다.
- `input/requirements`, `input/references`, `input/templates`, `input/samples`는 현재 저장소에 커밋된 파일을 그대로 사용합니다.
