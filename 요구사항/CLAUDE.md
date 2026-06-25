# CLAUDE.md

이 프로젝트의 작성 기준·아키텍처·운영 원칙은 모두 `AGENTS.md`에 정의되어 있다. Claude Code도 동일한 컨텍스트를 사용한다.

@AGENTS.md

## Claude Code 환경 메모

- **Python 환경**: 가상환경은 `.venv/`. `source .venv/bin/activate` 후 진행.
- **의존성 설치**: `pip install -r requirements.txt -r requirements-dev.txt`
- **테스트 실행**: `pytest` (전체) / `pytest tests/test_<name>.py` (단건)
- **린트**: `ruff check .` / `ruff format .`
- **CLI 진입점**: `python src/policy_agent.py create --topic "<주제>" --template <경로>` (자세한 옵션은 README.md 참조)
- **로컬 웹**: `python src/web_app.py`
- **환경 변수**: `.env.example`을 `.env`로 복사한 뒤 `OPENAI_API_KEY` 설정 필요. `.env`는 git에 commit 금지.
- **Mock 모드**: API 비용 없이 흐름만 테스트하려면 `NC_MOCK_LLM=1`.

## AGENTS.md Section 17 적용 메모

- AGENTS.md Section 17은 "Codex 작업 방식"으로 명명되어 있으나, **그 안의 규칙(직접 검수, Health Check, 장별 작성 순서, 정책서 품질 게이트 등)은 Claude Code도 동일하게 따른다.** "Codex"를 "작성하는 Agent"로 읽는다.
- 17.1의 `python src/policy_agent.py ...` 명령 예시는 Claude Code도 그대로 Bash 도구로 실행한다.
- 17.4.0의 직접 Inspector / 직접 Health Check 강제 규칙은 Claude Code도 매 정책서마다 수행한다.

## Claude Code 작업 시 주의사항

- 본 저장소는 원작자가 Codex(`AGENTS.md`)로 작업한 프로젝트이며, 협업 중이다. AGENTS.md를 직접 수정하지 말고, Claude 특화 메모만 위 섹션에 추가한다.
- 정책서 산출물(`output/`, `reports/`)은 의도적으로 git에 추적된다 (`.gitignore` 주석 참조). 함부로 ignore에 추가하지 않는다.
- `.env`, `.env.*` (단, `.env.example` 제외)은 절대 commit 금지.
- `.claude/`는 개인 Claude Code 설정용이라 gitignore된다 (HANDOVER 등 개인 메모 commit 금지).
