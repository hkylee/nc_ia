"""Small OpenAI Responses API client for policy chapter generation.

The project intentionally keeps this dependency-free. If OPENAI_API_KEY is not
configured, callers can continue with the deterministic local writer.
"""

from __future__ import annotations

import json
import html
import os
import random
import re
import hashlib
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from policy_style_anchor import POLICY_DETAIL_STYLE_MOCK_AXES
    from runtime_paths import LOGS_ROOT, PROJECT_ROOT
except ImportError:  # pragma: no cover - package import fallback.
    from .policy_style_anchor import POLICY_DETAIL_STYLE_MOCK_AXES
    from .runtime_paths import LOGS_ROOT, PROJECT_ROOT

DEFAULT_MODEL = "gpt-5.2"
MOCK_MODEL = "mock-policy-agent"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TIMEOUT: int | None = 1200
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_SECONDS = 3.0
DEFAULT_RETRY_MAX_SECONDS = 60.0
DEFAULT_RETRY_AFTER_MAX_SECONDS = 180.0
DEFAULT_RETRY_JITTER_RATIO = 0.15
DEFAULT_PREFLIGHT_TIMEOUT = 60
DEFAULT_PREFLIGHT_MAX_RETRIES = 2
DEFAULT_PREFLIGHT_CACHE_TTL_SECONDS = 600
DEFAULT_MAX_OUTPUT_TOKEN_RETRIES = 3
LLM_LOG_PATH = LOGS_ROOT / "llm_calls.jsonl"
SUPPORTED_REASONING_EFFORTS = {"", "none", "minimal", "low", "medium", "high", "xhigh"}
TRANSIENT_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
PREFLIGHT_CACHE_LOCK = threading.Lock()
PREFLIGHT_CACHE: dict[str, dict[str, Any]] = {}


class LLMError(ValueError):
    """Raised when a configured LLM request cannot complete."""


@dataclass(frozen=True)
class LLMClient:
    writer_mode: str
    model: str
    reasoning_effort: str
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: int | None = DEFAULT_TIMEOUT
    max_output_tokens: int | None = None
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_seconds: float = DEFAULT_RETRY_BASE_SECONDS
    retry_max_seconds: float = DEFAULT_RETRY_MAX_SECONDS
    max_output_token_retries: int = DEFAULT_MAX_OUTPUT_TOKEN_RETRIES

    def with_overrides(
        self,
        *,
        writer_mode: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
    ) -> "LLMClient":
        next_writer_mode = self.writer_mode if writer_mode is None else writer_mode
        next_reasoning = self.reasoning_effort if reasoning_effort is None else reasoning_effort.strip().casefold()
        if next_writer_mode not in {"auto", "llm", "local", "mock"}:
            raise LLMError("writer_mode는 auto, llm, local, mock 중 하나여야 합니다.")
        if next_reasoning not in SUPPORTED_REASONING_EFFORTS:
            raise LLMError("reasoning_effort는 none, minimal, low, medium, high, xhigh 중 하나여야 합니다.")
        return replace(
            self,
            writer_mode=next_writer_mode,
            model=(model or self.model).strip(),
            reasoning_effort=next_reasoning,
            max_output_tokens=max_output_tokens or self.max_output_tokens,
        )

    @classmethod
    def from_context(cls, ctx: object) -> "LLMClient":
        load_env_files()
        writer_mode = str(getattr(ctx, "writer_mode", "auto") or "auto").strip().casefold()
        if mock_llm_enabled() and not bool(getattr(ctx, "disable_mock_env", False)):
            writer_mode = "mock"
        if writer_mode not in {"auto", "llm", "local", "mock"}:
            writer_mode = "auto"

        model = str(getattr(ctx, "llm_model", "") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()
        if writer_mode == "mock":
            model = str(os.getenv("NC_MOCK_LLM_MODEL") or MOCK_MODEL).strip()
        reasoning_effort = str(
            getattr(ctx, "reasoning_effort", "") or os.getenv("OPENAI_REASONING_EFFORT") or ""
        ).strip().casefold()
        if writer_mode == "mock" and not reasoning_effort:
            reasoning_effort = "none"
        if reasoning_effort not in SUPPORTED_REASONING_EFFORTS:
            raise LLMError(
                "OPENAI_REASONING_EFFORT는 none, minimal, low, medium, high, xhigh 중 하나여야 합니다."
            )
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        timeout = parse_timeout(os.getenv("OPENAI_TIMEOUT"), DEFAULT_TIMEOUT)
        max_output_tokens = parse_optional_int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS"))
        max_retries = max(0, parse_int(os.getenv("OPENAI_MAX_RETRIES"), DEFAULT_MAX_RETRIES))
        max_output_token_retries = max(
            0,
            parse_int(os.getenv("OPENAI_MAX_OUTPUT_TOKEN_RETRIES"), DEFAULT_MAX_OUTPUT_TOKEN_RETRIES),
        )
        retry_base_seconds = max(0.1, parse_float(os.getenv("OPENAI_RETRY_BASE_SECONDS"), DEFAULT_RETRY_BASE_SECONDS))
        retry_max_seconds = max(
            retry_base_seconds,
            parse_float(os.getenv("OPENAI_RETRY_MAX_SECONDS"), DEFAULT_RETRY_MAX_SECONDS),
        )

        if writer_mode == "llm" and not api_key:
            raise LLMError("LLM 작성 모드에는 OPENAI_API_KEY가 필요합니다.")

        return cls(
            writer_mode=writer_mode,
            model=model,
            reasoning_effort=reasoning_effort,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
            max_retries=max_retries,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
            max_output_token_retries=max_output_token_retries,
        )

    @property
    def enabled(self) -> bool:
        if self.writer_mode == "mock":
            return True
        return self.writer_mode in {"auto", "llm"} and bool(self.api_key)

    @property
    def forced(self) -> bool:
        return self.writer_mode == "llm"

    def generate_json(
        self,
        *,
        schema_name: str,
        schema: Mapping[str, Any],
        instructions: str,
        input_messages: Sequence[Mapping[str, str]],
        max_output_tokens: int | None = None,
        omit_max_output_tokens: bool = True,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: Any | None = None,
        include: Sequence[str] | None = None,
        _output_retry_count: int = 0,
    ) -> dict:
        if not self.enabled:
            raise LLMError("LLM 클라이언트가 비활성화되어 있습니다.")

        effective_max_output_tokens = None if omit_max_output_tokens else (max_output_tokens or self.max_output_tokens)
        if self.writer_mode == "mock":
            start_time = time.monotonic()
            request_size = request_token_context_size(instructions, input_messages, schema)
            parsed = mock_generate_json(
                schema_name=schema_name,
                schema=schema,
                instructions=instructions,
                input_messages=input_messages,
            )
            write_llm_log(
                {
                    "event": "request_success",
                    "mock": True,
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "response_status": "mock_completed",
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                    **request_size,
                }
            )
            return parsed
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": list(input_messages),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if effective_max_output_tokens is not None:
            payload["max_output_tokens"] = effective_max_output_tokens
        if tools:
            payload["tools"] = [dict(tool) for tool in tools]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if include:
            payload["include"] = list(include)
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        start_time = time.monotonic()
        request_size = request_token_context_size(instructions, input_messages, schema)
        write_llm_log(
            {
                "event": "request_start",
                "schema_name": schema_name,
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
                "base_url": self.base_url,
                "max_output_tokens": effective_max_output_tokens,
                "tools": tool_names(tools or ()),
                "tool_choice": tool_choice,
                **request_size,
            }
        )
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        body = ""
        for attempt in range(1, self.max_retries + 2):
            try:
                request = urllib.request.Request(
                    f"{self.base_url}/responses",
                    data=request_body,
                    headers=self.headers(),
                    method="POST",
                )
                urlopen_kwargs = {} if self.timeout is None else {"timeout": self.timeout}
                with urllib.request.urlopen(request, **urlopen_kwargs) as response:
                    body = response.read().decode("utf-8")
                break
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                message = f"OpenAI API 오류 {exc.code}: {summarize_error(error_body)}"
                if should_retry_http(exc.code, attempt, self.max_retries):
                    server_retry_after = parse_retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
                    retry_delay = self.retry_delay_seconds(attempt, server_retry_after)
                    self.log_retry(
                        schema_name=schema_name,
                        request_size=request_size,
                        start_time=start_time,
                        attempt=attempt,
                        error=message,
                        status_code=exc.code,
                        retry_after_seconds=retry_delay,
                        server_retry_after_seconds=server_retry_after,
                    )
                    time.sleep(retry_delay)
                    continue
                write_llm_log(
                    {
                        "event": "request_error",
                        "schema_name": schema_name,
                        "model": self.model,
                        "reasoning_effort": self.reasoning_effort,
                        "duration_ms": elapsed_ms(start_time),
                        "attempt": attempt,
                        "max_attempts": self.max_retries + 1,
                        "error": message,
                        **request_size,
                    }
                )
                raise LLMError(message) from exc
            except urllib.error.URLError as exc:
                message = f"OpenAI API 연결 실패: {exc.reason}"
                if should_retry_transport(attempt, self.max_retries):
                    retry_delay = self.retry_delay_seconds(attempt)
                    self.log_retry(
                        schema_name=schema_name,
                        request_size=request_size,
                        start_time=start_time,
                        attempt=attempt,
                        error=message,
                        retry_after_seconds=retry_delay,
                    )
                    time.sleep(retry_delay)
                    continue
                write_llm_log(
                    {
                        "event": "request_error",
                        "schema_name": schema_name,
                        "model": self.model,
                        "reasoning_effort": self.reasoning_effort,
                        "duration_ms": elapsed_ms(start_time),
                        "attempt": attempt,
                        "max_attempts": self.max_retries + 1,
                        "error": message,
                        **request_size,
                    }
                )
                raise LLMError(message) from exc
            except (TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, ssl.SSLError) as exc:
                timeout_label = "없음" if self.timeout is None else f"{self.timeout}초"
                if isinstance(exc, (TimeoutError, socket.timeout)):
                    message = f"OpenAI API 응답 대기 시간이 초과되었습니다. 현재 OPENAI_TIMEOUT={timeout_label}입니다."
                else:
                    message = f"OpenAI API 연결이 중간에 끊겼습니다: {exc}"
                if should_retry_transport(attempt, self.max_retries):
                    retry_delay = self.retry_delay_seconds(attempt)
                    self.log_retry(
                        schema_name=schema_name,
                        request_size=request_size,
                        start_time=start_time,
                        attempt=attempt,
                        error=message,
                        retry_after_seconds=retry_delay,
                    )
                    time.sleep(retry_delay)
                    continue
                write_llm_log(
                    {
                        "event": "request_error",
                        "schema_name": schema_name,
                        "model": self.model,
                        "reasoning_effort": self.reasoning_effort,
                        "duration_ms": elapsed_ms(start_time),
                        "attempt": attempt,
                        "max_attempts": self.max_retries + 1,
                        "error": message,
                        **request_size,
                    }
                )
                raise LLMError(message) from exc

        try:
            response_data = json.loads(body)
        except json.JSONDecodeError as exc:
            message = "OpenAI API 응답을 JSON으로 해석하지 못했습니다."
            write_llm_log(
                {
                    "event": "request_error",
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "error": message,
                    **request_size,
                }
            )
            raise LLMError(message) from exc

        if (
            effective_max_output_tokens is not None
            and response_data.get("status") == "incomplete"
            and response_incomplete_reason(response_data) == "max_output_tokens"
        ):
            larger_max_output_tokens = next_output_token_cap(effective_max_output_tokens, self.max_output_tokens)
            if (
                larger_max_output_tokens > effective_max_output_tokens
                and _output_retry_count < self.max_output_token_retries
            ):
                write_llm_log(
                    {
                        "event": "request_retry",
                        "schema_name": schema_name,
                        "model": self.model,
                        "reasoning_effort": self.reasoning_effort,
                        "duration_ms": elapsed_ms(start_time),
                        "retry_reason": "max_output_tokens",
                        "max_output_tokens": effective_max_output_tokens,
                        "next_max_output_tokens": larger_max_output_tokens,
                        "response_status": response_data.get("status", ""),
                        "usage": usage_summary(response_data),
                        **request_size,
                    }
                )
                return self.generate_json(
                    schema_name=schema_name,
                    schema=schema,
                    instructions=instructions,
                    input_messages=input_messages,
                    max_output_tokens=larger_max_output_tokens,
                    omit_max_output_tokens=omit_max_output_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                    include=include,
                    _output_retry_count=_output_retry_count + 1,
                )

        if response_data.get("status") == "incomplete":
            partial_text = extract_response_text(response_data)
            if partial_text:
                try:
                    partial_parsed = json.loads(partial_text)
                except json.JSONDecodeError:
                    partial_parsed = None
                if isinstance(partial_parsed, dict):
                    write_llm_log(
                        {
                            "event": "request_success_partial",
                            "schema_name": schema_name,
                            "model": self.model,
                            "reasoning_effort": self.reasoning_effort,
                            "duration_ms": elapsed_ms(start_time),
                            "response_status": response_data.get("status", ""),
                            "usage": usage_summary(response_data),
                            **request_size,
                        }
                    )
                    return partial_parsed

        if response_data.get("status") in {"failed", "incomplete"}:
            message = summarize_error(json.dumps(response_data, ensure_ascii=False))
            write_llm_log(
                {
                    "event": "request_error",
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "error": message,
                    "response_status": response_data.get("status", ""),
                    "usage": usage_summary(response_data),
                    **request_size,
                }
            )
            raise LLMError(message)

        text = extract_response_text(response_data)
        if not text:
            message = "OpenAI API 응답에 JSON 텍스트가 없습니다."
            write_llm_log(
                {
                    "event": "request_error",
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "error": message,
                    "usage": usage_summary(response_data),
                    **request_size,
                }
            )
            raise LLMError(message)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            message = "LLM 응답이 유효한 JSON이 아닙니다."
            write_llm_log(
                {
                    "event": "request_error",
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "error": message,
                    "usage": usage_summary(response_data),
                    **request_size,
                }
            )
            raise LLMError(message) from exc
        if not isinstance(parsed, dict):
            message = "LLM 응답은 JSON 객체여야 합니다."
            write_llm_log(
                {
                    "event": "request_error",
                    "schema_name": schema_name,
                    "model": self.model,
                    "reasoning_effort": self.reasoning_effort,
                    "duration_ms": elapsed_ms(start_time),
                    "error": message,
                    "usage": usage_summary(response_data),
                    **request_size,
                }
            )
            raise LLMError(message)
        write_llm_log(
            {
                "event": "request_success",
                "schema_name": schema_name,
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
                "duration_ms": elapsed_ms(start_time),
                "response_status": response_data.get("status", ""),
                "usage": usage_summary(response_data),
                **request_size,
            }
        )
        return parsed

    def headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        organization = os.getenv("OPENAI_ORG_ID", "").strip()
        project = os.getenv("OPENAI_PROJECT", "").strip()
        if organization:
            headers["OpenAI-Organization"] = organization
        if project:
            headers["OpenAI-Project"] = project
        return headers

    def preflight_check(self) -> dict:
        """Run a tiny real LLM call before a long generation job starts."""
        if self.writer_mode == "mock":
            return {"ok": True, "message": "Mock LLM 모드입니다."}
        timeout = parse_timeout(os.getenv("OPENAI_PREFLIGHT_TIMEOUT"), DEFAULT_PREFLIGHT_TIMEOUT)
        max_retries = max(0, parse_int(os.getenv("OPENAI_PREFLIGHT_MAX_RETRIES"), DEFAULT_PREFLIGHT_MAX_RETRIES))
        reasoning_effort = os.getenv("OPENAI_PREFLIGHT_REASONING_EFFORT", "low").strip().casefold()
        if reasoning_effort not in SUPPORTED_REASONING_EFFORTS:
            reasoning_effort = "low"
        cache_ttl = max(
            0,
            parse_int(os.getenv("OPENAI_PREFLIGHT_CACHE_TTL_SECONDS"), DEFAULT_PREFLIGHT_CACHE_TTL_SECONDS),
        )
        cache_key = preflight_cache_key(self, reasoning_effort, timeout, max_retries)
        cached = load_preflight_cache(cache_key, cache_ttl)
        if cached:
            return cached
        check_client = replace(
            self,
            timeout=timeout,
            max_retries=max_retries,
            reasoning_effort=reasoning_effort,
        )
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ok": {"type": "boolean"},
                "message": {"type": "string", "maxLength": 60},
            },
            "required": ["ok", "message"],
        }
        try:
            result = check_client.generate_json(
                schema_name="codex_connectivity_check",
                schema=schema,
                instructions="Return a small JSON object only. Set ok to true when this request can be processed.",
                input_messages=[{"role": "user", "content": "LLM connectivity preflight for NC Policy Agent."}],
                omit_max_output_tokens=True,
            )
        except LLMError as exc:
            raise LLMError(f"LLM 사전 연결 점검 실패: {exc}") from exc
        if result.get("ok"):
            save_preflight_cache(cache_key, result)
        return result

    def retry_delay_seconds(self, attempt: int, retry_after_seconds: float | None = None) -> float:
        delay = self.retry_base_seconds * (2 ** max(0, attempt - 1))
        delay = min(self.retry_max_seconds, delay)
        if retry_after_seconds is not None and retry_after_seconds > 0:
            max_retry_after = max(
                self.retry_max_seconds,
                parse_float(os.getenv("OPENAI_RETRY_AFTER_MAX_SECONDS"), DEFAULT_RETRY_AFTER_MAX_SECONDS),
            )
            delay = max(delay, min(retry_after_seconds, max_retry_after))
        jitter_ratio = max(0.0, parse_float(os.getenv("OPENAI_RETRY_JITTER_RATIO"), DEFAULT_RETRY_JITTER_RATIO))
        if jitter_ratio:
            jitter = delay * min(jitter_ratio, 0.5)
            delay = random.uniform(max(0.1, delay - jitter), delay + jitter)
        return round(delay, 2)

    def log_retry(
        self,
        *,
        schema_name: str,
        request_size: Mapping[str, Any],
        start_time: float,
        attempt: int,
        error: str,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        server_retry_after_seconds: float | None = None,
    ) -> None:
        retry_after = retry_after_seconds if retry_after_seconds is not None else self.retry_delay_seconds(attempt)
        write_llm_log(
            {
                "event": "request_retry",
                "schema_name": schema_name,
                "model": self.model,
                "reasoning_effort": self.reasoning_effort,
                "duration_ms": elapsed_ms(start_time),
                "attempt": attempt,
                "max_attempts": self.max_retries + 1,
                "retry_after_seconds": retry_after,
                "server_retry_after_seconds": server_retry_after_seconds,
                "status_code": status_code,
                "error": error,
                **request_size,
            }
        )


def preflight_cache_key(
    client: LLMClient,
    reasoning_effort: str,
    timeout: int | None,
    max_retries: int,
) -> str:
    key_material = {
        "writer_mode": client.writer_mode,
        "model": client.model,
        "base_url": client.base_url,
        "reasoning_effort": reasoning_effort,
        "timeout": timeout,
        "max_retries": max_retries,
        "api_key_hash": hashlib.sha256(client.api_key.encode("utf-8")).hexdigest()[:16] if client.api_key else "",
    }
    raw = json.dumps(key_material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_preflight_cache(cache_key: str, ttl_seconds: int) -> dict | None:
    if not cache_key or ttl_seconds <= 0:
        return None
    now = time.time()
    with PREFLIGHT_CACHE_LOCK:
        cached = PREFLIGHT_CACHE.get(cache_key)
        if not isinstance(cached, dict):
            return None
        created_at = float(cached.get("created_at") or 0)
        if created_at <= 0 or now - created_at > ttl_seconds:
            PREFLIGHT_CACHE.pop(cache_key, None)
            return None
        result = cached.get("result")
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    payload = dict(result)
    payload["cache_hit"] = True
    payload["cached_age_seconds"] = int(now - created_at)
    return payload


def save_preflight_cache(cache_key: str, result: Mapping[str, Any]) -> None:
    if not cache_key or not result.get("ok"):
        return
    payload = dict(result)
    payload["cache_hit"] = False
    with PREFLIGHT_CACHE_LOCK:
        PREFLIGHT_CACHE[cache_key] = {
            "created_at": time.time(),
            "result": payload,
        }


def load_env_files() -> None:
    for path in unique_paths(Path.cwd() / ".env", PROJECT_ROOT / ".env"):
        if path.exists() and path.is_file():
            load_env_file(path)


def unique_paths(*paths: Path) -> list[Path]:
    seen = set()
    result = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(path)
    return result


def load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except ValueError:
        return default


def parse_optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value else default
    except ValueError:
        return default


def parse_timeout(value: str | None, default: int | None) -> int | None:
    if value is None:
        return default
    normalized = value.strip().casefold()
    if not normalized:
        return default
    if normalized in {"none", "no", "off", "false", "0", "-1", "무제한", "없음"}:
        return None
    try:
        parsed = int(normalized)
    except ValueError:
        return default
    return None if parsed <= 0 else parsed


def parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(text)
        if retry_at.tzinfo is None:
            retry_at = retry_at.astimezone()
        return max(0.0, (retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
    except (TypeError, ValueError, OSError):
        return None


def llm_preflight_enabled() -> bool:
    value = os.getenv("OPENAI_PREFLIGHT_ENABLED", "1").strip().casefold()
    return value not in {"0", "false", "no", "off", "skip", "비활성", "끄기"}


def mock_llm_enabled() -> bool:
    """Return True when the workflow should use a no-cost mock LLM."""
    values = (
        os.getenv("NC_MOCK_LLM", ""),
        os.getenv("NC_LLM_PROVIDER", ""),
        os.getenv("OPENAI_MOCK_LLM", ""),
    )
    return any(str(value).strip().casefold() in {"1", "true", "yes", "y", "on", "mock"} for value in values)


def mock_generate_json(
    *,
    schema_name: str,
    schema: Mapping[str, Any],
    instructions: str,
    input_messages: Sequence[Mapping[str, str]],
) -> dict:
    """Generate deterministic schema-valid JSON without network calls.

    This mode is intentionally for workflow/UI tests. It keeps the same LLM
    orchestration path, but returns the local draft embedded in prompts or a
    pass-style inspector response.
    """
    del instructions
    text = "\n\n".join(str(message.get("content", "")) for message in input_messages)
    candidate: dict[str, Any] | None = None

    if schema_name in {"policy_inspection", "policy_json_inspection"}:
        candidate = {
            "status": "warn",
            "summary": "Mock Inspector 직접 호출은 문서 문맥이 부족합니다. 실제 LLM 미사용 검수는 policy_inspector의 strict local 규칙으로 수행됩니다.",
            "findings": [],
        }
    elif schema_name == "topic_learning":
        candidate = mock_topic_learning_payload(text)
    elif schema_name == "blueprint_architect_contract":
        candidate = extract_base_contract_payload(text)
    elif schema_name == "dev_qa_review":
        candidate = mock_dev_qa_review_payload(text)
    elif schema_name == "dev_qa_action_check":
        candidate = mock_dev_qa_action_check_payload(text)
    elif schema_name == "live_feedback":
        candidate = {
            "message": "현재 단계 흐름을 확인하며 문서 작성을 이어가고 있습니다.",
            "tone": "info",
        }
    elif schema_name.startswith("state_chapter"):
        candidate = mock_state_chapter_payload(text)
    elif schema_name.startswith("functions_chapter"):
        candidate = mock_functions_chapter_payload(text)
    elif schema_name.startswith("policies_chapter"):
        candidate = mock_policies_chapter_payload(text)
    elif schema_name.endswith("_chapter_patch"):
        candidate = mock_chapter_patch_payload(schema_name, text, schema)
    elif schema_name == "final_revision_patch":
        candidate = mock_final_revision_patch_payload(text)
    elif schema_name in {"revision_intent", "revision_refinement"}:
        candidate = mock_revision_intent_payload(text)
    else:
        candidate = (
            extract_labeled_json(
                text,
                labels=(
                    "로컬 초안 JSON:",
                    "현재 챕터 JSON:",
                    "상태 seed JSON(그대로 복사하지 말고 현재 주제와 유즈케이스에 맞게 재작성):",
                    "상태 seed JSON:",
                ),
            )
            or extract_schema_like_json(text, schema)
        )

    return coerce_mock_payload_to_schema(mock_naturalize_payload(candidate or {}), schema)


def mock_dev_qa_review_payload(text: str) -> dict[str, Any]:
    meta = mock_prompt_json_value(text, "문서 메타:")
    signals_payload = mock_prompt_json_value(text, "문서 구조 신호:")
    document_text = mock_prompt_section(text, "정책서 본문 텍스트:")
    signals = signals_payload if isinstance(signals_payload, Mapping) else {}
    normalized_doc = mock_normalized_search_text(document_text)

    def count_signal(key: str) -> int:
        value = signals.get(key)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    ambiguous_count = count_signal("tbd_or_ambiguous_count")
    counts = {
        "actor": count_signal("actor_count"),
        "usecase": count_signal("usecase_count"),
        "state": count_signal("state_count"),
        "process": count_signal("process_count"),
        "function": count_signal("function_count"),
        "policy_group": count_signal("policy_group_count"),
        "policy_item": count_signal("policy_item_count"),
        "history": count_signal("history_count_hint"),
    }
    has_bss_trace = any(keyword in normalized_doc for keyword in ("bss", "연계", "원장", "회신", "이력", "상태 반영", "저장"))
    has_exception_flow = any(keyword in normalized_doc for keyword in ("예외", "실패", "보류", "제한", "복구", "재시도", "만료"))
    has_qa_terms = any(keyword in normalized_doc for keyword in ("qa", "테스트", "검수", "기대 결과", "경계", "회귀"))
    has_policy_specificity = counts["policy_item"] > 0 and ambiguous_count == 0
    has_structure_chain = all(counts[key] > 0 for key in ("usecase", "process", "function", "policy_group"))

    development_findings: list[dict[str, str]] = []
    qa_findings: list[dict[str, str]] = []
    coverage_checks: list[dict[str, str]] = [
        mock_dev_qa_coverage(
            "구조 연결성",
            has_structure_chain,
            "유즈케이스, 프로세스, 기능, 정책 ID가 함께 확인됩니다.",
            "유즈케이스, 프로세스, 기능, 정책 ID 중 일부가 부족해 연결 검수가 제한됩니다.",
        ),
        mock_dev_qa_coverage(
            "BSS·연계 추적성",
            has_bss_trace,
            "BSS/연계 판정, 상태 반영 또는 이력 저장 신호가 확인됩니다.",
            "BSS/연계 판정, 상태 반영, 이력 저장, 결과 회신 중 확인 가능한 기준이 부족합니다.",
        ),
        mock_dev_qa_coverage(
            "정책 구체성",
            has_policy_specificity,
            "정책 항목 ID가 있고 TBD·모호 표현 신호가 낮습니다.",
            "정책 항목 수가 부족하거나 TBD·모호 표현 신호가 남아 있습니다.",
        ),
        mock_dev_qa_coverage(
            "QA 시나리오 도출성",
            has_exception_flow and has_qa_terms,
            "예외/실패/제한 흐름과 QA·테스트 기준 신호가 함께 확인됩니다.",
            "예외/실패/제한 흐름 또는 QA 테스트 기준 신호가 부족합니다.",
        ),
    ]

    if counts["process"] == 0 or counts["function"] == 0:
        development_findings.append(
            mock_dev_qa_finding(
                perspective="development",
                title="프로세스-기능 연결 기준 보강 필요",
                target_location="4. 프로세스 정의 > 프로세스 목록",
                desired_change="프로세스별 관련 기능과 관련 정책을 확인할 수 있도록 ID 연결 기준을 보강한다.",
                detail="Mock 모드의 문서 구조 신호에서 프로세스 또는 기능 ID가 부족하게 감지되어 상세 설계 연결성이 낮습니다.",
                recommendation="프로세스 목록에 관련 기능 ID와 정책 ID를 연결하고, 기능 목록의 process_ids와 양방향으로 맞춰 주세요.",
                priority="P2",
                severity="major",
            )
        )
    if not has_bss_trace:
        development_findings.append(
            mock_dev_qa_finding(
                perspective="development",
                title="BSS·연계 처리 기준 보강 필요",
                target_location="4. 프로세스 정의 > 전체 업무 흐름도",
                desired_change="BSS 또는 연계 시스템의 판정, 상태 반영, 이력 저장, 결과 회신 기준을 업무 흐름 안에 추가한다.",
                detail="Mock 모드의 본문 신호에서 BSS/연계/이력 기준이 충분히 확인되지 않았습니다.",
                recommendation="채널 처리와 BSS/연계 처리의 책임 경계를 프로세스, 기능, 정책 중 최소 한 곳에 명시해 주세요.",
                priority="P2",
                severity="major",
            )
        )
    if not has_policy_specificity:
        development_findings.append(
            mock_dev_qa_finding(
                perspective="development",
                title="정책 상세 판단값 보강 필요",
                target_location="6. 정책 정의 > 정책 상세",
                desired_change="정책 항목별 허용 조건, 제한 조건, 예외 기준, 고객 고지, 이력 저장 기준을 판단값으로 분리한다.",
                detail="Mock 모드의 구조 신호에서 정책 항목 부족 또는 모호 표현이 감지되어 구현 기준으로 쓰기 어렵습니다.",
                recommendation="TBD 또는 일반 표현을 결정 주체·기한·판단 기준이 있는 정책 항목으로 정리해 주세요.",
                priority="P2",
                severity="major" if ambiguous_count else "minor",
            )
        )
    if not has_exception_flow:
        qa_findings.append(
            mock_dev_qa_finding(
                perspective="qa",
                title="예외·실패·제한 흐름 보강 필요",
                target_location="3. 유즈케이스 정의 > 상태 전이표",
                desired_change="정상 흐름 외 실패, 보류, 제한, 복구 가능/불가 흐름을 상태 전이 또는 정책 기준으로 추가한다.",
                detail="Mock 모드의 본문 신호에서 QA가 예외 테스트 케이스로 전환할 수 있는 흐름 기준이 부족합니다.",
                recommendation="상태 전이표와 정책 상세에 실패 사유, 고객 안내, 재시도 또는 복구 기준을 연결해 주세요.",
                priority="P2",
                severity="major",
            )
        )
    if not has_qa_terms:
        qa_findings.append(
            mock_dev_qa_finding(
                perspective="qa",
                title="QA 테스트 기준 보강 필요",
                target_location="최종 점검 기준 > 개발/QA 검수 기준",
                desired_change="QA가 정상, 예외, 제한, 회귀 테스트를 도출할 수 있도록 테스트 전제와 기대 결과 확인 기준을 추가한다.",
                detail="Mock 모드의 본문 신호에서 QA, 테스트, 검수, 기대 결과와 같은 확인 기준이 부족하게 감지되었습니다.",
                recommendation="최종 점검 기준 또는 정책 상세에 테스트 전제, 경계 조건, 기대 결과를 확인할 수 있는 문장을 보강해 주세요.",
                priority="P3",
                severity="minor",
            )
        )

    findings_count = len(development_findings) + len(qa_findings)
    score = max(45, min(96, 92 - findings_count * 9 - min(ambiguous_count, 6) * 2))
    if score >= 88 and not findings_count:
        verdict = "충분"
    elif score < 70 or any(item["priority"] == "P1" for item in development_findings + qa_findings):
        verdict = "위험"
    else:
        verdict = "보완 필요"
    topic = str(meta.get("topic") if isinstance(meta, Mapping) else "").strip() or "선택 정책서"
    summary = (
        f"Mock LLM 모드에서 '{topic}' 문서의 구조 신호와 본문 키워드를 기준으로 개발/QA 준비도를 점검했습니다. "
        f"보완 후보 {findings_count}건, 점수 {score}점입니다."
    )
    recommended_actions = [
        item["recommendation"] for item in (development_findings + qa_findings)[:3]
    ] or ["현재 mock 신호 기준으로 추가 보완 후보가 없습니다. 실제 의미 검수는 LLM 사용 모드에서 다시 확인하세요."]
    evidence_gaps = []
    if not document_text.strip():
        evidence_gaps.append("정책서 본문 텍스트가 비어 있어 mock 검수 근거가 부족합니다.")
    if ambiguous_count:
        evidence_gaps.append(f"TBD 또는 모호 표현 신호 {ambiguous_count}건이 감지되었습니다.")
    return {
        "agent": "Development QA Review Agent",
        "score": score,
        "verdict": verdict,
        "summary": summary,
        "development_findings": development_findings,
        "qa_findings": qa_findings,
        "coverage_checks": coverage_checks,
        "recommended_actions": recommended_actions,
        "evidence_gaps": evidence_gaps,
    }


def mock_dev_qa_coverage(item: str, passed: bool, pass_detail: str, fail_detail: str) -> dict[str, str]:
    return {
        "item": item,
        "status": "pass" if passed else "warn",
        "detail": pass_detail if passed else fail_detail,
    }


def mock_dev_qa_finding(
    *,
    perspective: str,
    title: str,
    target_location: str,
    desired_change: str,
    detail: str,
    recommendation: str,
    priority: str,
    severity: str,
    action_type: str = "add",
    current_content: str = "",
) -> dict[str, str]:
    return {
        "perspective": perspective,
        "priority": priority,
        "action_type": action_type,
        "severity": severity,
        "title": title,
        "target_location": target_location,
        "current_content": current_content,
        "desired_change": desired_change,
        "detail": detail,
        "recommendation": recommendation,
    }


def mock_dev_qa_action_check_payload(text: str) -> dict[str, Any]:
    payload = mock_prompt_json_value(text, "확인할 보완 요청 항목:") or extract_first_json_object(text) or {}
    candidate_items = payload.get("items") if isinstance(payload, Mapping) else None
    document_text = mock_prompt_section(text, "현재 정책서 본문 텍스트:")
    items = []
    if isinstance(candidate_items, list):
        items = [
            mock_dev_qa_action_check_item(item, document_text)
            for item in candidate_items
            if isinstance(item, Mapping) and str(item.get("item_key") or "").strip()
        ]
    resolved_count = sum(1 for item in items if item["status"] == "resolved")
    partial_count = sum(1 for item in items if item["status"] == "partial")
    open_count = sum(1 for item in items if item["status"] == "open")
    return {
        "summary": (
            "Mock LLM 모드에서 문서 텍스트의 명시적 근거만 기준으로 보완 여부를 확인했습니다. "
            f"조치 완료 {resolved_count}건, 부분 반영 {partial_count}건, 미조치 {open_count}건입니다."
        ),
        "items": items,
    }


def mock_dev_qa_action_check_item(item: Mapping[str, Any], document_text: str) -> dict[str, str]:
    item_key = str(item.get("item_key") or "").strip()
    action_type = str(item.get("action_type") or "").strip().casefold()
    title = mock_compact_text(item.get("title") or "보완 요청", max_chars=80)
    current_content = str(item.get("current_content") or "").strip()
    desired_change = str(item.get("desired_change") or "").strip()
    recommendation = str(item.get("recommendation") or "").strip()
    user_note = str(item.get("user_note") or item.get("note") or "").strip()
    normalized_document = mock_normalized_search_text(document_text)
    desired_source = " ".join(part for part in (desired_change, user_note, recommendation) if part)

    if action_type == "delete":
        if current_content and not mock_text_contains(normalized_document, current_content):
            return {
                "item_key": item_key,
                "status": "resolved",
                "evidence": f"Mock 확인: 삭제 대상 '{mock_compact_text(current_content, max_chars=60)}'이 현재 문서 텍스트에서 확인되지 않습니다.",
                "note": "삭제 요청은 대상 문구 부재만 확인했습니다. 문맥상 대체 문구가 필요한지는 사람이 검토하세요.",
            }
        return {
            "item_key": item_key,
            "status": "open",
            "evidence": "Mock 확인: 삭제 대상 문구가 아직 문서에 남아 있거나 삭제 대상을 특정할 수 없습니다.",
            "note": f"'{title}' 삭제 요청은 실제 수정 후 다시 확인하세요.",
        }

    exact_desired = bool(desired_change and mock_text_contains(normalized_document, desired_change))
    desired_phrases = mock_action_check_phrases(desired_source)
    matched_phrases = [phrase for phrase in desired_phrases if mock_text_contains(normalized_document, phrase)]
    current_still_present = bool(current_content and mock_text_contains(normalized_document, current_content))

    if exact_desired:
        return {
            "item_key": item_key,
            "status": "resolved",
            "evidence": f"Mock 확인: 요청한 변경 문구 '{mock_compact_text(desired_change, max_chars=70)}'가 현재 문서에 그대로 확인됩니다.",
            "note": "정확 문구 기준으로만 조치 완료 처리했습니다. 위치 적합성은 필요 시 실제 LLM 모드에서 확인하세요.",
        }
    if matched_phrases:
        status = "partial"
        evidence = (
            "Mock 확인: 요청 문구 일부가 현재 문서에 확인됩니다. "
            f"확인된 단서: {', '.join(mock_compact_text(phrase, max_chars=36) for phrase in matched_phrases[:4])}"
        )
        if current_still_present and action_type == "change":
            evidence += " 기존 문구도 함께 남아 있어 완전 반영으로 보지 않았습니다."
        return {
            "item_key": item_key,
            "status": status,
            "evidence": evidence,
            "note": f"'{title}' 항목은 부분 반영 가능성이 있으므로 위치와 구체성을 확인하세요.",
        }
    return {
        "item_key": item_key,
        "status": "open",
        "evidence": "Mock 확인: 요청한 변경/추가 내용의 명시적 문구가 현재 문서에서 확인되지 않습니다.",
        "note": f"'{title}' 항목은 mock 모드에서 조치 완료로 처리하지 않았습니다.",
    }


def mock_action_check_phrases(value: str) -> list[str]:
    text = mock_normalized_search_text(value)
    if not text:
        return []
    quoted = re.findall(r"[\"'“”‘’`]([^\"'“”‘’`]{4,80})[\"'“”‘’`]", str(value or ""))
    chunks = re.split(r"[\n\r.;:!?/|·•,()\[\]{}]+|\s(?:및|또는|그리고|하거나|하도록|한다|합니다)\s", text)
    candidates = [*quoted, *chunks]
    return mock_unique_texts(
        [
            candidate
            for candidate in candidates
            if len(mock_normalized_search_text(candidate)) >= 8
            and not mock_action_check_stop_phrase(candidate)
        ],
        limit=8,
    )


def mock_action_check_stop_phrase(value: str) -> bool:
    normalized = mock_normalized_search_text(value)
    return normalized in {
        "추가한다",
        "변경한다",
        "보강한다",
        "정의한다",
        "확인한다",
        "기준을 추가한다",
        "기준을 보강한다",
    }


def mock_text_contains(normalized_document: str, needle: str) -> bool:
    normalized_needle = mock_normalized_search_text(needle)
    return bool(normalized_needle and normalized_needle in normalized_document)


def mock_normalized_search_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def mock_revision_intent_payload(text: str) -> dict[str, Any]:
    instruction = mock_prompt_section(text, "사용자 수정 요청:", "선택 영역 정보:").strip()
    selection_text = mock_prompt_section(text, "- 선택 텍스트:", "- 선택 블록 텍스트:").strip()
    block_html = mock_prompt_section(
        text,
        "- 선택 블록 HTML, target_replacement_html 작성 시 우선 교체 대상:",
        "선택 영역을 우선 수정하되",
    ).strip()
    replacement = mock_selected_text_replacement(instruction, selection_text)
    target_replacement_html = ""
    replacements: list[dict[str, str]] = []
    if replacement is not None and selection_text:
        if block_html:
            target_replacement_html = mock_replace_text_in_html_fragment(block_html, selection_text, replacement)
        replacements.append({"find": selection_text, "replace": replacement})

    if replacement is None:
        summary = "Mock 수정 Agent가 사용자 수정 요청을 보완 항목으로 정리했습니다."
        history_change = "사용자 수정 요청을 보완 항목으로 반영"
        append_items = [f"사용자 수정 요청: {instruction}"] if instruction else []
    elif replacement:
        summary = f"선택 영역 '{mock_compact_text(selection_text, max_chars=40)}'을 '{mock_compact_text(replacement, max_chars=40)}'로 변경합니다."
        history_change = f"선택 영역 문구를 '{mock_compact_text(replacement, max_chars=60)}'로 변경"
        append_items = []
    else:
        summary = f"선택 영역 '{mock_compact_text(selection_text, max_chars=40)}'을 삭제합니다."
        history_change = "선택 영역 문구 삭제"
        append_items = []

    return {
        "summary": summary,
        "history_change": history_change,
        "target_sections": mock_revision_target_sections(text),
        "replacements": replacements,
        "append_title": "수정 요청 반영 필요 사항",
        "append_items": append_items,
        "target_replacement_html": target_replacement_html,
    }


def mock_prompt_section(text: str, start_label: str, end_label: str = "") -> str:
    start = text.find(start_label)
    if start < 0:
        return ""
    start += len(start_label)
    end = text.find(end_label, start) if end_label else -1
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def mock_revision_target_sections(text: str) -> list[str]:
    match = re.search(r'"selected_sections"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))[:8]


def mock_replace_text_in_html_fragment(fragment: str, selected_text: str, replacement: str) -> str:
    escaped_replacement = html.escape(replacement)
    for candidate in (html.escape(selected_text), html.escape(selected_text, quote=False), selected_text):
        if candidate and candidate in fragment:
            return fragment.replace(candidate, escaped_replacement, 1)
    return fragment


def mock_selected_text_replacement(instruction: str, selected_text: str) -> str | None:
    request = mock_normalize_instruction_text(instruction)
    selected = mock_normalize_instruction_text(selected_text)
    if not request or not selected:
        return None
    if "띄어쓰기" in request and any(keyword in request for keyword in ("없", "제거", "삭제", "붙여")):
        return re.sub(r"\s+", "", selected)

    deletion_keywords = ("삭제", "제거", "지워", "없애", "빼줘", "빼 주세요", "빼주세요")
    replacement_markers = ("으로", "로 변경", "로 수정", "로 바꿔", "로 교체", "로 고쳐")
    if any(keyword in request for keyword in deletion_keywords) and not any(marker in request for marker in replacement_markers):
        return ""

    patterns = [
        r"[\"'“”‘’`]([^\"'“”‘’`\n]{1,160})[\"'“”‘’`]\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)",
        r"(?:을|를)\s*([^\n]{1,160}?)\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)",
        r"([^\n]{1,160}?)\s*(?:으로|로)\s*(?:변경|수정|바꿔|바꾸|교체|고쳐)",
    ]
    for pattern in patterns:
        match = re.search(pattern, request)
        if match:
            return mock_clean_replacement_candidate(match.group(1))
    return None


def mock_clean_replacement_candidate(value: str) -> str:
    candidate = mock_normalize_instruction_text(value)
    candidate = candidate.strip(" \t\r\n.,:;\"'“”‘’`()[]{}")
    for delimiter in ("을 ", "를 "):
        if delimiter in candidate:
            candidate = candidate.rsplit(delimiter, 1)[-1].strip()
    candidate = re.sub(r"^(?:이걸|이것을|이 문구를|이 문구|선택 영역을|선택 영역|선택한 영역을|선택한 문구를|문구를|텍스트를)\s*", "", candidate)
    return candidate.strip(" \t\r\n.,:;\"'“”‘’`()[]{}")


def mock_normalize_instruction_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def mock_topic_learning_payload(text: str) -> dict[str, Any]:
    """Build a richer deterministic topic-learning result from embedded packs.

    Mock mode should not pretend to reason with a model, but it should still
    exercise the same knowledge plumbing as LLM mode. This keeps no-cost tests
    useful by reflecting requirement details, topic knowledge packs, and chapter
    guidance instead of returning a generic placeholder.
    """

    topic = mock_topic_from_prompt(text)
    knowledge = mock_prompt_json_value(text, "사전 주제 Knowledge Pack:")
    requirements_payload = mock_prompt_json_value(text, "요구사항 요약:")
    topic_axes_payload = mock_prompt_json_value(text, "주제 의미 축:")
    knowledge_map = knowledge if isinstance(knowledge, Mapping) else {}
    if topic == "선택 주제":
        topic = str(knowledge_map.get("topic") or "").strip() or topic
    req_items = mock_requirement_items(requirements_payload)
    authoritative = knowledge_map.get("authoritative_signals") if isinstance(knowledge_map.get("authoritative_signals"), Mapping) else {}
    auxiliary = knowledge_map.get("auxiliary_web_signals") if isinstance(knowledge_map.get("auxiliary_web_signals"), Mapping) else {}
    candidate_inventory = (
        knowledge_map.get("candidate_inventory") if isinstance(knowledge_map.get("candidate_inventory"), Mapping) else {}
    )
    chapter_guidance = (
        knowledge_map.get("chapter_guidance") if isinstance(knowledge_map.get("chapter_guidance"), Mapping) else {}
    )
    topic_axes = knowledge_map.get("topic_axes") if isinstance(knowledge_map.get("topic_axes"), Mapping) else {}
    if not topic_axes and isinstance(topic_axes_payload, Mapping):
        topic_axes = topic_axes_payload

    direct_scope = mock_unique_texts(
        [
            *mock_values_from_mapping(authoritative, ("direct_scope", "scope_boundary", "requirement_summary")),
            *mock_values_from_mapping(topic_axes, ("customer_jobs", "business_scope", "policy_axes")),
            *(mock_requirement_scope(item) for item in req_items),
            f"{topic} 고객 과업과 처리 기준",
        ],
        limit=8,
    )
    customer_tasks = mock_unique_texts(
        [
            *mock_values_from_mapping(candidate_inventory, ("usecase_candidates", "customer_tasks")),
            *mock_values_from_mapping(topic_axes, ("customer_jobs", "user_jobs")),
            *(mock_requirement_task(item, topic) for item in req_items),
            f"{topic} 업무를 시작하고 완료한다.",
        ],
        limit=10,
    )
    requirement_implications = mock_unique_texts(
        [
            *(mock_requirement_implication(item) for item in req_items),
            "요구사항은 유즈케이스, 프로세스, 기능, 정책 중 하나 이상에 연결한다.",
        ],
        limit=10,
    )
    reference_implications = mock_unique_texts(
        [
            *mock_values_from_mapping(
                authoritative,
                ("reference_implications", "style_anchors", "template_signals", "attached_reference_signals"),
            ),
            *mock_values_from_mapping(auxiliary, ("official_service_signals", "compliance_signals", "benchmark_signals")),
            "참고자료의 전략 방향과 샘플의 간결한 표 구조를 유지한다.",
        ],
        limit=8,
    )
    bss_implications = mock_unique_texts(
        [
            *mock_values_from_mapping(candidate_inventory, ("bss_touchpoints", "process_patterns", "function_candidates")),
            *(mock_requirement_bss_implication(item) for item in req_items),
            "BSS 판단, 상태 반영, 이력 저장, 연계 결과 회신을 업무 기준으로 포함한다.",
        ],
        limit=8,
    )
    policy_risks = mock_unique_texts(
        [
            *mock_values_from_mapping(candidate_inventory, ("policy_item_candidates", "policy_candidates")),
            *(mock_requirement_policy_risk(item) for item in req_items),
            "정책이 기능 설명으로 흐르지 않도록 판단값과 제한 기준을 분리한다.",
        ],
        limit=10,
    )
    chapter_focus = mock_chapter_focus_from_guidance(chapter_guidance)

    topic_summary_parts = [
        direct_scope[0] if direct_scope else f"{topic} 고객 과업",
        customer_tasks[0] if customer_tasks else "",
        policy_risks[0] if policy_risks else "",
    ]
    topic_summary = " / ".join(part for part in topic_summary_parts if part)
    topic_understanding = mock_compact_text(
        f"{topic} 정책서는 {topic_summary}{korean_object_particle(topic_summary)} 중심으로 "
        "고객 과업, 처리 흐름, BSS 반영, 정책 판단값을 연결해야 한다.",
        max_chars=220,
    )
    return {
        "topic_understanding": topic_understanding,
        "scope_boundary": {
            "direct_scope": direct_scope,
            "related_but_not_core": ["상세 화면 설계", "API 필드 설계", "DB 컬럼 설계"],
            "excluded_or_later": ["운영 배치 상세", "물리 테이블 설계", "오류 코드 전체 목록"],
        },
        "customer_tasks": customer_tasks,
        "requirement_implications": requirement_implications,
        "reference_implications": reference_implications,
        "bss_implications": bss_implications,
        "policy_risks": policy_risks,
        "chapter_focus": chapter_focus,
    }


def mock_topic_from_prompt(text: str) -> str:
    match = re.search(r"정책서\s*주제\s*:\s*([^\n\r]+)", text)
    if match:
        topic = match.group(1).strip()
        if topic:
            return topic
    return extract_json_text_value(text, "topic") or "선택 주제"


def mock_requirement_items(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        for key in ("requirements", "items", "requirement_summary", "selected_requirements"):
            items = value.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, Mapping)]
    return []


def mock_requirement_scope(item: Mapping[str, Any]) -> str:
    name = mock_requirement_name(item)
    depth = str(item.get("depth4") or item.get("module") or item.get("category") or "").strip()
    if depth and name:
        return mock_compact_text(f"{depth}: {name}", max_chars=90)
    return mock_compact_text(name, max_chars=90)


def mock_requirement_name(item: Mapping[str, Any]) -> str:
    for key in ("detail_name", "상세 요구사항명", "name", "title", "requirement_name"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def mock_requirement_description(item: Mapping[str, Any]) -> str:
    for key in ("detail_description", "상세 요구사항 설명", "description", "summary", "requirement_description"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def mock_requirement_task(item: Mapping[str, Any], topic: str) -> str:
    name = mock_requirement_name(item)
    if not name:
        return ""
    task = re.sub(r"\s*(기능|요구|정책|관리|제공|지원)\s*$", "", name).strip()
    if not task:
        task = name
    if any(keyword in task for keyword in ("조회", "확인", "검색", "신청", "변경", "해지", "취소", "등록", "관리")):
        return mock_compact_text(f"{task} 업무를 시작해 결과를 확인한다.", max_chars=90)
    return mock_compact_text(f"{topic}에서 {task} 기준을 확인하고 처리한다.", max_chars=90)


def mock_requirement_implication(item: Mapping[str, Any]) -> str:
    name = mock_requirement_name(item)
    description = mock_requirement_description(item)
    if not name and not description:
        return ""
    axis = mock_requirement_axis(f"{name} {description}")
    source = name or description
    return mock_compact_text(f"{source} 요구는 {axis} 기준을 프로세스·기능·정책에 연결한다.", max_chars=120)


def mock_requirement_bss_implication(item: Mapping[str, Any]) -> str:
    text = f"{mock_requirement_name(item)} {mock_requirement_description(item)}"
    if not any(keyword in text for keyword in ("BSS", "연계", "원장", "상태", "이력", "결제", "인증", "동의", "검증", "승인")):
        return ""
    axis = mock_requirement_axis(text)
    return mock_compact_text(f"{axis} 관련 BSS·연계 판정 결과와 이력 저장 기준을 함께 정의한다.", max_chars=110)


def mock_requirement_policy_risk(item: Mapping[str, Any]) -> str:
    text = f"{mock_requirement_name(item)} {mock_requirement_description(item)}"
    if not text.strip():
        return ""
    axis = mock_requirement_axis(text)
    return mock_compact_text(f"{axis} 기준이 모호하면 정책 항목이 일반 설명으로 흐르므로 허용·제한·예외·고지 값을 분리한다.", max_chars=130)


def mock_requirement_axis(text: str) -> str:
    value = str(text or "")
    rules = (
        (("인증", "본인", "권한", "대리", "법정대리", "동의"), "인증·권한"),
        (("결제", "청구", "수납", "환불", "금액", "할인", "포인트", "쿠폰"), "금전 영향"),
        (("상태", "전이", "완료", "실패", "보류", "취소", "만료"), "상태 전이"),
        (("알림", "고지", "안내", "메시지"), "고객 고지"),
        (("이력", "로그", "보관", "파기", "저장", "증적"), "이력·보관"),
        (("운영", "관리", "승인", "검수", "보정"), "운영 관리"),
        (("검색", "추천", "AI", "질의", "결과"), "탐색·추천"),
        (("상품", "요금제", "혜택", "가입", "변경", "해지"), "상품·가입"),
    )
    for keywords, axis in rules:
        if any(keyword in value for keyword in keywords):
            return axis
    return "업무 조건"


def mock_chapter_focus_from_guidance(value: Any) -> dict[str, str]:
    defaults = {
        "overview": "고객 과업 기준의 범위와 원칙을 짧게 정리한다.",
        "terms": "정책 판단에 쓰이는 용어만 정의한다.",
        "actors": "독립 책임 주체만 액터로 둔다.",
        "usecases": "사람 액터가 완결해야 하는 업무 단위를 정의한다.",
        "usecase_diagram": "액터와 유즈케이스 관계를 샘플 양식의 정적 도식으로 표현한다.",
        "state": "유즈케이스 흐름에서 발생한 업무 사건을 전이 이벤트로 삼아 상태를 정의한다.",
        "process": "유즈케이스를 완성하는 사람 관점 절차를 정의한다.",
        "functions": "프로세스 수행에 필요한 처리 단위와 세부 구성을 정의한다.",
        "policies": "프로세스와 기능에 필요한 정책 그룹, 항목, 값을 정의한다.",
        "final_check": "연결성, 구체성, 근거 누락을 최종 확인한다.",
    }
    if not isinstance(value, Mapping):
        return defaults
    result = dict(defaults)
    for key in result:
        guidance = value.get(key)
        flattened = mock_flatten_texts(guidance)
        if flattened:
            result[key] = mock_compact_text(" ".join(flattened[:3]), max_chars=160)
    return result


def mock_values_from_mapping(value: Any, keys: Sequence[str]) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    result: list[str] = []
    for key in keys:
        result.extend(mock_flatten_texts(value.get(key)))
    return result


def mock_flatten_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Mapping):
        result: list[str] = []
        for item in value.values():
            result.extend(mock_flatten_texts(item))
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result: list[str] = []
        for item in value:
            result.extend(mock_flatten_texts(item))
        return result
    text = str(value).strip()
    return [text] if text else []


def mock_unique_texts(values: Sequence[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = mock_compact_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def mock_compact_text(value: object, *, max_chars: int = 120) -> str:
    text = mock_naturalize_text(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -:·\t\r\n")
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 1].rstrip(" ,.;:/")
    return f"{trimmed}…"


def mock_naturalize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: mock_naturalize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mock_naturalize_payload(item) for item in value]
    if isinstance(value, str):
        return mock_naturalize_text(value)
    return value


def mock_naturalize_text(text: str) -> str:
    value = str(text or "")
    replacements = {
        "회원 가입탈퇴은": "회원 가입·탈퇴는",
        "회원 가입탈퇴을": "회원 가입·탈퇴를",
        "회원 가입탈퇴의": "회원 가입·탈퇴의",
        "회원 가입탈퇴": "회원 가입·탈퇴",
        "회원가입탈퇴은": "회원가입/탈퇴는",
        "회원가입탈퇴을": "회원가입/탈퇴를",
        "회원가입탈퇴의": "회원가입/탈퇴의",
        "회원가입탈퇴": "회원가입/탈퇴",
        "가입탈퇴은": "가입·탈퇴는",
        "가입탈퇴을": "가입·탈퇴를",
        "가입탈퇴의": "가입·탈퇴의",
        "가입탈퇴": "가입·탈퇴",
        "분류을": "분류를",
        "조회은": "조회는",
        "확인은": "확인은",
        "기준 기준": "기준",
        "조건 조건": "조건",
        "정보 정보": "정보",
        "검증 검증": "검증",
        "조회 조회": "조회",
        "판정 판정": "판정",
        "구성 구성": "구성",
        "결과 결과": "결과",
        "처리 처리": "처리",
        "구성 결과": "구성",
        "저장 결과": "저장",
        "표시 결과": "표시",
        "안내 구성 결과": "안내 구성",
        "검토 요청 구성 결과": "검토 요청 구성",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\s*처리\s*기능\s+\d+(?=\s|$)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def korean_has_final_consonant(text: object) -> bool:
    for char in reversed(str(text or "").strip()):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if char.isalnum():
            return True
    return False


def korean_topic_particle(text: object) -> str:
    return "은" if korean_has_final_consonant(text) else "는"


def korean_object_particle(text: object) -> str:
    return "을" if korean_has_final_consonant(text) else "를"


def mock_function_description(name: str, detail_set: Sequence[str]) -> str:
    name = mock_naturalize_text(str(name or "기능").strip())
    details = [mock_naturalize_text(str(item).strip()) for item in detail_set if str(item).strip()]
    if not details:
        return f"{name}{korean_topic_particle(name)} 관련 프로세스의 입력, 판정, 결과 안내를 처리한다."
    if len(details) == 1:
        return f"{name}{korean_topic_particle(name)} {details[0]}{korean_object_particle(details[0])} 처리한다."
    if len(details) == 2:
        return f"{name}{korean_topic_particle(name)} {details[0]}와 {details[1]}{korean_object_particle(details[1])} 처리한다."
    head = ", ".join(details[:-1])
    tail = details[-1]
    return f"{name}{korean_topic_particle(name)} {head}, {tail}{korean_object_particle(tail)} 순서대로 처리한다."


def mock_state_chapter_payload(text: str) -> dict[str, Any] | None:
    usecases = mock_extract_state_usecases(text)
    if not usecases:
        return None
    business_code = mock_business_code_from_usecases(usecases)
    state_names = [
        ("업무 시작 전", "고객 또는 운영자가 업무를 시작하기 전 상태이다.", "요청 접수 여부를 확인한다."),
        ("요청 접수", "업무 요청이 접수되어 기본 정보를 확인하는 상태이다.", "처리 가능 여부를 판정한다."),
        ("판정 중", "채널과 연계 시스템이 업무 조건을 판정하는 상태이다.", "허용, 제한, 보류, 실패로 분기한다."),
        ("처리 가능", "필수 조건을 충족해 후속 처리를 진행할 수 있는 상태이다.", "처리 요청과 결과 반영을 진행한다."),
        ("처리 제한", "권한, 조건, 범위 문제로 처리를 제한하는 상태이다.", "제한 사유를 안내하고 후속 방법을 제시한다."),
        ("처리 보류", "추가 확인이나 운영 검토가 필요해 처리를 멈춘 상태이다.", "보완 또는 운영 확인 후 재판정한다."),
        ("처리 실패", "연계 실패나 조건 불일치로 요청을 완료하지 못한 상태이다.", "실패 사유와 재시도 가능 여부를 안내한다."),
        ("처리 완료", "업무 처리 결과가 확정되어 고객에게 안내된 상태이다.", "결과 확인과 이력 저장을 완료한다."),
    ]
    states = [
        {
            "id": f"ST-{business_code}-{index:03d}",
            "name": name,
            "description": description,
            "next_action": next_action,
        }
        for index, (name, description, next_action) in enumerate(state_names, start=1)
    ]
    route = [
        ("업무 시작 전", "요청 접수", "요청 접수 완료", "업무 시작 기준을 충족하면 요청을 접수한다."),
        ("요청 접수", "판정 중", "기본 정보 확인 완료", "접수 정보와 고객 조건을 기준으로 판정을 시작한다."),
        ("판정 중", "처리 가능", "처리 조건 충족", "필수 조건을 충족하면 후속 처리를 허용한다."),
        ("판정 중", "처리 제한", "제한 사유 확인", "권한, 범위, 조건 중 하나라도 불충족하면 제한한다."),
        ("판정 중", "처리 보류", "추가 확인 필요", "추가 확인 또는 운영 검토가 필요하면 보류한다."),
        ("판정 중", "처리 실패", "처리 실패 확정", "연계 실패나 필수 검증 실패 시 실패로 닫는다."),
        ("처리 가능", "처리 완료", "처리 결과 확정", "처리 결과가 확정되면 완료로 닫는다."),
    ]
    transitions: list[dict[str, Any]] = []
    for index, usecase in enumerate(usecases):
        current_state, next_state, event, criteria = route[index % len(route)]
        transitions.append(
            {
                "usecase_ids": [str(usecase.get("id", "")).strip()],
                "current_state": current_state,
                "event": event,
                "next_state": next_state,
                "criteria": criteria,
            }
        )
    return {"states": states, "state_transitions": transitions}


def mock_functions_chapter_payload(text: str) -> dict[str, Any] | None:
    payload = extract_labeled_json(text, labels=("로컬 초안 JSON:", "현재 챕터 JSON:"))
    if not isinstance(payload, Mapping):
        return None
    functions = payload.get("functions")
    if not isinstance(functions, list):
        return None
    process_ids = unique_nonempty_strings(
        process_id
        for function in functions
        if isinstance(function, Mapping)
        for process_id in mock_function_process_ids(function)
    )
    detail_sets = [
        ("대상 조건 구성", "권한 상태 검증", "결과 안내 구성"),
        ("입력값 정규화", "필수 조건 확인", "처리 결과 저장"),
        ("조회 범위 산정", "연계 응답 확인", "후속 안내 구성"),
        ("요청 정보 구성", "중복 처리 확인", "이력 저장"),
        ("상태값 조회", "가능 여부 판정", "알림 대상 구성"),
        ("인증 상태 확인", "동의 여부 확인", "처리 가능 표시"),
        ("운영 기준 조회", "예외 사유 분류", "검토 요청 구성"),
        ("결과값 조합", "고객 표시 구성", "재시도 안내 구성"),
    ]
    result: list[dict[str, Any]] = []
    existing_names: set[str] = set()
    for index, function in enumerate(functions):
        if not isinstance(function, Mapping):
            continue
        current_ids = mock_function_process_ids(function)
        linked_ids = current_ids
        if process_ids and index % 6 == 0:
            linked_ids = process_ids[index : index + 6] or current_ids
        if not linked_ids:
            linked_ids = process_ids[:1]
        detail_set = mock_select_detail_set(
            str(function.get("id") or function.get("name") or index),
            detail_sets,
            index,
        )
        row = dict(function)
        row["process_id"] = str(linked_ids[0]) if linked_ids else str(function.get("process_id", "")).strip()
        row["process_ids"] = linked_ids
        refined_name = mock_refine_function_name(str(row.get("name", "")), index)
        collision_index = 0
        while refined_name in existing_names:
            refined_name = mock_function_name_collision_variant(refined_name, collision_index)
            collision_index += 1
        existing_names.add(refined_name)
        row["name"] = refined_name
        row["details"] = list(detail_set)
        row["description"] = mock_function_description(row["name"], detail_set)
        result.append(row)
    return {"functions": result}


def mock_policies_chapter_payload(text: str) -> dict[str, Any] | None:
    payload = extract_labeled_json(text, labels=("로컬 초안 JSON:", "현재 챕터 JSON:"))
    if not isinstance(payload, Mapping):
        return None
    result: dict[str, Any] = {}
    groups = payload.get("policy_groups")
    details = payload.get("policy_details")
    if isinstance(groups, list):
        result["policy_groups"] = [
            mock_repair_policy_group(item, index) for index, item in enumerate(groups) if isinstance(item, Mapping)
        ]
    if isinstance(details, list):
        result["policy_details"] = [
            mock_repair_policy_detail(item, index) for index, item in enumerate(details) if isinstance(item, Mapping)
        ]
    return result or None


def mock_chapter_patch_payload(schema_name: str, text: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic but meaningful patches for no-cost repair loops."""

    del schema_name
    target = extract_labeled_json(text, labels=("패치 대상 JSON:",)) or {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    payload: dict[str, Any] = {}
    if "overview" in properties and isinstance(target.get("overview"), Mapping):
        payload["overview"] = mock_repair_overview(target.get("overview"), text)
    if "terms" in properties and isinstance(target.get("terms"), list):
        payload["terms"] = [mock_repair_term(item, index) for index, item in enumerate(target.get("terms") or []) if isinstance(item, Mapping)]
    if "actors" in properties and isinstance(target.get("actors"), list):
        payload["actors"] = [
            mock_repair_described_item(item, "액터", index) for index, item in enumerate(target.get("actors") or []) if isinstance(item, Mapping)
        ]
    if "usecases" in properties and isinstance(target.get("usecases"), list):
        payload["usecases"] = [
            mock_repair_usecase(item, index) for index, item in enumerate(target.get("usecases") or []) if isinstance(item, Mapping)
        ]
    if "states" in properties and isinstance(target.get("states"), list):
        payload["states"] = [
            mock_repair_state(item, index) for index, item in enumerate(target.get("states") or []) if isinstance(item, Mapping)
        ]
    if "state_transitions" in properties and isinstance(target.get("state_transitions"), list):
        payload["state_transitions"] = [
            mock_repair_transition(item, index)
            for index, item in enumerate(target.get("state_transitions") or [])
            if isinstance(item, Mapping)
        ]
    if "processes" in properties and isinstance(target.get("processes"), list):
        payload["processes"] = [
            mock_repair_process(item, index) for index, item in enumerate(target.get("processes") or []) if isinstance(item, Mapping)
        ]
    if "functions" in properties and isinstance(target.get("functions"), list):
        payload["functions"] = [
            mock_repair_function(item, index) for index, item in enumerate(target.get("functions") or []) if isinstance(item, Mapping)
        ]
    if "function_details" in properties and isinstance(target.get("function_details"), list):
        payload["function_details"] = [
            mock_repair_function_detail(item, index)
            for index, item in enumerate(target.get("function_details") or [])
            if isinstance(item, Mapping)
        ]
    if "policy_groups" in properties and isinstance(target.get("policy_groups"), list):
        payload["policy_groups"] = [
            mock_repair_policy_group(item, index)
            for index, item in enumerate(target.get("policy_groups") or [])
            if isinstance(item, Mapping)
        ]
    if "policy_details" in properties and isinstance(target.get("policy_details"), list):
        payload["policy_details"] = [
            mock_repair_policy_detail(item, index)
            for index, item in enumerate(target.get("policy_details") or [])
            if isinstance(item, Mapping)
        ]
    return payload


def mock_repair_overview(value: Any, feedback_text: str = "") -> dict[str, Any]:
    overview = dict(value) if isinstance(value, Mapping) else {}
    scope = [str(item).strip() for item in overview.get("scope", []) if str(item).strip()] if isinstance(overview.get("scope"), list) else []
    feedback_lower = feedback_text.casefold()
    asks_scope_revision = any(keyword in feedback_lower for keyword in ("범위", "제외", "scope"))
    if asks_scope_revision and not any("제외" in str(item) for item in scope):
        exclusion = "제외 범위: 화면 UI 상세, API 필드, DB 컬럼, 운영 배치 설계는 후속 산출물에서 다룬다."
        if len(scope) < 6:
            scope.append(exclusion)
        elif scope:
            scope[-1] = exclusion

    principles = normalize_mock_overview_principles(overview.get("principles", []))
    asks_principle_revision = any(keyword in feedback_lower for keyword in ("설계 원칙", "설계원칙", "원칙", "principle"))
    if asks_principle_revision or len(principles) < 4:
        supplemental = [
            {
                "name": "고객 결과 고지",
                "description": "고객이 처리 가능 여부, 제한 사유, 보류 또는 완료 결과를 이해할 수 있도록 고지 기준을 정책에 연결한다.",
            },
            {
                "name": "처리 이력 추적",
                "description": "BSS 또는 연계 시스템의 판정, 상태 반영, 결과 회신이 필요한 지점은 프로세스와 정책 항목에 남긴다.",
            },
        ]
        existing_names = {str(item.get("name", "")).strip() for item in principles if isinstance(item, Mapping)}
        for item in supplemental:
            if item["name"] in existing_names:
                continue
            if len(principles) < 6:
                principles.append(dict(item))
                existing_names.add(item["name"])
            elif principles:
                principles[-1] = dict(item)
                existing_names.add(item["name"])
                break

    overview["scope"] = scope[:6]
    overview["principles"] = principles[:6]
    return overview


def normalize_mock_overview_principles(value: Any) -> list[dict[str, str]]:
    principles: list[dict[str, str]] = []
    if not isinstance(value, list):
        return principles
    for index, item in enumerate(value, start=1):
        if isinstance(item, Mapping):
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            if ":" in text:
                name, description = [part.strip() for part in text.split(":", 1)]
            else:
                name = f"설계 원칙 {index}"
                description = text
        if not name:
            name = f"설계 원칙 {index}"
        if not description:
            description = "고객 과업 완료, 처리 가능 여부 판단, 결과 고지, 이력 저장 기준을 후속 장과 연결한다."
        principles.append({"name": name[:28], "description": description[:110]})
    return principles


def mock_repair_term(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"용어 {index + 1}").strip()
    row["description"] = (
        f"{name}는 업무 가능 여부, 제한 사유, 예외 처리, 고객 고지 또는 이력 저장 기준을 판단할 때 사용하는 정책 용어이다."
    )
    return row


def mock_repair_described_item(item: Mapping[str, Any], label: str, index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"{label} {index + 1}").strip()
    row["description"] = f"{name}는 요청 시작, 조건 판정, 결과 고지, 이력 저장 중 독립 책임을 갖는 {label}이다."
    return row


def mock_repair_usecase(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"유즈케이스 {index + 1}").strip()
    row["description"] = f"{name} 업무를 시작해 처리 가능 여부를 확인하고, 제한·보류·완료 결과를 고객 또는 운영자에게 확정한다."
    if not str(row.get("process_target", "")).strip():
        row["process_target"] = "Y"
    return row


def mock_repair_state(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"상태 {index + 1}").strip()
    row["description"] = f"{name} 상태에서는 허용 기능, 제한 사유, 고객 고지, 후속 처리 가능 여부를 구분한다."
    row["next_action"] = f"{name} 상태의 처리 결과를 기준으로 다음 전이, 복구, 이력 저장 여부를 결정한다."
    return row


def mock_repair_transition(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    row["event"] = str(row.get("event") or f"유즈케이스 처리 결과 확정 {index + 1}").strip()
    row["criteria"] = "유즈케이스 처리 결과가 허용, 제한, 보류, 실패 중 하나로 확정되면 다음 상태와 고객 고지, 이력 저장 여부를 함께 결정한다."
    return row


def mock_repair_process(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"프로세스 {index + 1}").strip()
    original = str(row.get("description") or "").strip()
    stage_focus = mock_process_stage_focus(name, original, index)
    if original and not re.fullmatch(r"(처리한다|확인한다|진행한다)[.。]?", original):
        row["description"] = f"{original} 이 단계에서는 {stage_focus}을 기준으로 허용, 제한, 보류, 완료 여부를 구분한다."
    else:
        row["description"] = f"{name} 단계에서는 {stage_focus}을 기준으로 허용, 제한, 보류, 완료 여부를 구분한다."
    return row


def mock_process_stage_focus(name: str, description: str, index: int) -> str:
    text = f"{name} {description}"
    rules = (
        (("진입", "목적", "접근"), "업무 목적과 접근 권한"),
        (("조회", "정보", "기준"), "조회 범위와 기준 정보"),
        (("권한", "상태", "조건", "가능", "검증"), "고객 상태와 처리 가능 조건"),
        (("입력", "인증", "동의"), "입력값 완전성과 인증·동의 결과"),
        (("영향", "비용", "혜택", "고지"), "고객 영향도와 사전 고지"),
        (("요청", "접수", "중복"), "요청 접수 가능성과 중복 여부"),
        (("결과", "반영", "완료", "실패"), "처리 결과와 후속 상태"),
        (("후속", "취소", "재시도", "상담"), "후속 처리 가능성과 상담 전환 기준"),
        (("운영", "예외", "승인", "보정"), "운영 확인 대상과 예외 승인 기준"),
        (("품질", "모니터링", "개선"), "품질 지표와 개선 과제 기준"),
    )
    for keywords, focus in rules:
        if any(keyword in text for keyword in keywords):
            return focus
    fallback = (
        "요청 대상과 처리 조건",
        "판정 결과와 고객 안내",
        "연계 결과와 이력 저장",
        "예외 사유와 복구 가능성",
    )
    return fallback[index % len(fallback)]


def mock_repair_function(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = mock_refine_function_name(str(row.get("name") or row.get("id") or f"기능 {index + 1}").strip(), index)
    row["name"] = name
    row["description"] = mock_naturalize_text(
        f"{name}{korean_topic_particle(name)} 관련 프로세스의 입력 조건을 확인하고 BSS 상태 반영, 고객 고지, 처리 이력 저장 결과를 만든다."
    )
    detail_sets = (
        ("요청 대상 및 권한 조건 확인", "허용·제한·보류 결과 판정", "고객 고지 및 처리 이력 저장"),
        ("현재 상태와 동의 조건 확인", "BSS 반영 필요 여부 산정", "실패 사유와 재시도 안내 구성"),
        ("업무 범위와 제한 조건 조회", "예외 허용 여부 판정", "결과 상태와 후속 처리 저장"),
        ("입력 정보 완전성 확인", "외부 연계 응답 검증", "완료·실패 결과 알림 구성"),
        ("고객 유형과 처리 가능 시간 확인", "중복 요청 및 만료 여부 판정", "상담 전환 또는 복구 안내 저장"),
    )
    row["details"] = list(mock_select_detail_set(str(row.get("id") or name), detail_sets, index))
    return row


def mock_select_detail_set(seed: str, detail_sets: Sequence[Sequence[str]], index: int) -> Sequence[str]:
    if not detail_sets:
        return ()
    digest = hashlib.sha1(str(seed or index).encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16)
    return detail_sets[(offset + index) % len(detail_sets)]


def mock_repair_function_detail(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    function_id = str(row.get("function_id") or row.get("id") or f"FN-MOCK-{index + 1:03d}")
    row.setdefault("function_id", function_id)
    detail_seed = str(row.get("function_id") or row.get("name") or index)
    axis = mock_select_detail_set(
        detail_seed,
        (
            ("요청 대상", "현재 상태", "권한·동의 여부"),
            ("조회 조건", "연계 응답", "기준일시"),
            ("처리 요청", "중복 여부", "실패 이력"),
            ("운영 기준", "예외 사유", "고객 영향도"),
        ),
        index,
    )
    output_axis = mock_select_detail_set(
        detail_seed,
        (
            ("처리 가능 여부", "제한 사유", "고객 안내 기준"),
            ("산정 결과", "후속 상태", "이력 저장 대상"),
            ("연계 회신 결과", "재시도 가능 여부", "상담 전환 기준"),
            ("확정 결과", "예외 분류", "운영 보정 필요 여부"),
        ),
        index + 1,
    )
    exception_axis = mock_select_detail_set(
        detail_seed,
        (
            ("권한 불충족", "상태 조건 불일치", "제한 사유 고지"),
            ("BSS 반영 실패", "응답 지연", "재시도 기준 초과"),
            ("중복 요청", "만료 조건 충족", "이력 저장 실패"),
            ("외부 연계 불일치", "부분 성공", "운영 검토 필요"),
        ),
        index + 2,
    )
    row["input_information"] = list(axis)
    row["processing_logic"] = [
        f"(상태) {axis[0]} 확인 필요 → (액션) 처리 대상과 기준 정보를 확인 → (결과) 처리 대상 확정",
        f"(상태) {axis[1]} 기준 확인 완료 → (액션) 허용·제한·보류 여부를 판정 → (결과) 후속 상태 결정",
        f"(상태) {axis[2]} 반영 필요 → (액션) 후속 고지와 이력 저장 대상을 결정 → (결과) 고객 안내·이력 저장 기준 생성",
    ]
    row["sub_functions"] = list(
        mock_select_detail_set(
            detail_seed,
            (
                ("조건 검증", "결과 산정", "고지 구성", "이력 저장"),
                ("대상 조회", "연계 확인", "예외 분류", "후속 안내"),
                ("입력 정합성 확인", "상태 반영", "결과 저장", "재시도 안내"),
            ),
            index + 3,
        )
    )
    row["output_information"] = list(output_axis)
    row["failure_exception_cases"] = list(exception_axis)
    return row


def mock_repair_policy_group(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    name = str(row.get("name") or row.get("id") or f"정책 {index + 1}").strip()
    row["description"] = f"{name}은 허용 기준, 제한 기준, 예외 기준, 고객 고지, 이력 저장 기준을 묶어 관리한다."
    return row


MOCK_POLICY_DETAIL_AXES: tuple[tuple[str, str, str], ...] = (
    (
        "요청 주체 허용 기준",
        "허용 대상은 업무 책임과 권한이 확인된 고객·운영자·연계 시스템으로 한정한다. 권한이 없으면 요청을 제한하고 사유를 고지한다.",
        "허용",
    ),
    (
        "상태 제한 기준",
        "제한 조건은 제한·보류·만료 상태이거나 필수 조건이 누락된 경우이다. 제한 시 다음 가능 시점과 상담 전환 여부를 안내한다.",
        "제한",
    ),
    (
        "인증 유효 기준",
        "인증 유효 시간은 10분이며 만료되면 재인증을 요구한다.",
        "인증",
    ),
    (
        "동의 확인 기준",
        "필수 약관과 개인정보 처리 동의가 완료되어야 업무를 허용한다. 선택 동의 미완료는 핵심 업무를 제한하지 않고 고지만 남긴다.",
        "동의",
    ),
    (
        "횟수 제한 기준",
        "요청 실패가 동일 업무 기준 5회를 초과하면 당일 재시도를 제한한다. 제한 시 운영 확인 이력을 저장한다.",
        "횟수",
    ),
    (
        "만료 처리 기준",
        "고객 응답 없이 7일을 초과한 요청은 만료 처리한다. 만료 시 요청 상태를 종료하고 고객에게 만료 사유와 재요청 방법을 안내한다.",
        "만료",
    ),
    (
        "상태 전환 기준",
        "판정 결과가 허용·제한·보류·실패 중 하나로 확정되면 상태를 전환한다. 다음 상태와 후속 가능 여부를 함께 저장한다.",
        "상태",
    ),
    (
        "BSS 반영 기준",
        "BSS 반영은 결과 확정 후 원장 또는 업무 상태 변경이 필요한 경우에만 요청한다. 반영 실패 시 실패 상태와 재시도 가능 여부를 저장한다.",
        "BSS",
    ),
    (
        "외부 연계 기준",
        "외부 연계는 인증기관·결제기관·제휴 시스템 응답이 필요한 경우 수행한다. 응답 지연 시 보류 상태로 두고 재시도 기준을 남긴다.",
        "연계",
    ),
    (
        "고객 고지 기준",
        "결과가 완료·제한·보류·실패로 바뀌는 모든 경우 고객 고지를 제공한다. 고지에는 결과, 제한 사유, 다음 조치, 문의 경로를 포함한다.",
        "고지",
    ),
    (
        "이력 저장 기준",
        "요청 시각, 판정 결과, 제한 사유, 처리 주체, 연계 결과를 이력으로 저장한다. 재처리는 이 이력을 기준으로 추적한다.",
        "이력",
    ),
    (
        "예외 복구 기준",
        "네트워크 실패나 연계 지연처럼 고객 귀책이 아닌 사유가 확인되면 예외 복구를 허용한다. 복구 결과와 보정 사유를 이력으로 남긴다.",
        "예외",
    ),
    (
        "운영 확인 기준",
        "자동 판정만으로 고객 영향도를 확정하기 어려운 경우 운영 확인을 요청한다. 확인 중에는 보류 상태를 유지하고 임의 완료 처리를 금지한다.",
        "운영",
    ),
    (
        "결과 회신 기준",
        "처리 결과가 확정되면 고객 채널과 연계 시스템에 동일 상태로 회신한다. 회신 실패 시 재전송 대상과 실패 이력을 저장한다.",
        "회신",
    ),
    (
        "우선순위 적용 기준",
        "우선순위는 고객 피해 가능성, 금전 영향, 상태 변경 여부 순으로 판단한다. 충돌 시 제한 기준을 먼저 적용하고 예외 사유를 기록한다.",
        "우선순위",
    ),
    (
        "판정 충돌 처리 기준",
        "채널 결과와 BSS·연계 결과가 다르면 판정 충돌로 본다. 이때는 보류 상태로 전환하고 기준 출처와 재확인 이력을 저장한다.",
        "충돌",
    ),
    (
        "재요청 허용 기준",
        "이전 요청이 실패·만료·고객 취소로 종료된 경우에만 재요청을 허용한다. 진행 중 요청이 있으면 중복 요청으로 제한한다.",
        "재요청",
    ),
    (
        "부분 성공 처리 기준",
        "일부 연계만 완료되고 핵심 상태 반영이 끝나지 않은 경우는 부분 성공으로 본다. 전체 완료로 보지 않고 보류 상태와 남은 처리 대상을 저장한다.",
        "부분성공",
    ),
    (
        "고객 취소 가능 기준",
        "BSS 반영 전이고 고객 영향 고지 확인 전인 요청은 고객 취소를 허용한다. 반영 후 취소는 후속 변경·복구 프로세스로 연결한다.",
        "취소",
    ),
    (
        "운영 보정 승인 기준",
        "고객 피해 가능성과 증적 이력이 함께 확인된 경우에만 운영 보정을 허용한다. 보정 전후 값과 승인 주체를 변경 이력으로 저장한다.",
        "보정",
    ),
    (
        "품질 모니터링 기준",
        "실패·보류·상담 전환이 같은 조건에서 3회 이상 반복되면 품질 모니터링 대상으로 등록한다. 반복 원인은 개선 과제로 관리한다.",
        "품질",
    ),
    (
        "데이터 정합성 기준",
        "고객 상태, 요청 상태, 연계 결과가 같은 처리 결과를 가리키는지 확인한다. 불일치 시 완료 처리를 보류한다.",
        "정합성",
    ),
    (
        "데이터 보관 기간 기준",
        "보관 기간은 법정 보관 사유, 고객 분쟁 대응, 처리 이력 추적 필요성을 기준으로 정한다. 기간 만료 시 파기 대상으로 전환하고 파기 이력을 저장한다.",
        "보관",
    ),
) + POLICY_DETAIL_STYLE_MOCK_AXES

MOCK_POLICY_DETAIL_AXIS_INDEX = {
    axis_name: index for index, (axis_name, _, _) in enumerate(MOCK_POLICY_DETAIL_AXES)
}


def mock_policy_detail_axis_index(axis_name: str, fallback: int) -> int:
    return MOCK_POLICY_DETAIL_AXIS_INDEX.get(axis_name, fallback)


MOCK_POLICY_DETAIL_NAME_VARIANTS = (
    "요청 접수",
    "조건 판정",
    "결과 확정",
    "예외 처리",
    "후속 안내",
    "이력 관리",
    "연계 확인",
    "운영 검토",
    "충돌 확인",
    "품질 확인",
    "취소 판단",
)
MOCK_POLICY_DETAIL_CONTEXT_VARIANTS = (
    "기본",
    "예외",
    "복구",
    "운영",
    "고지",
    "이력",
    "연계",
    "제한",
    "품질",
)
MOCK_POLICY_DETAIL_PHASE_VARIANTS = (
    "요청 접수 시",
    "조건 판정 시",
    "결과 확정 시",
    "예외 처리 시",
    "후속 안내 시",
    "이력 저장 시",
    "연계 확인 시",
    "운영 검토 시",
    "품질 확인 시",
)

MOCK_GENERIC_POLICY_DETAIL_NAMES = {
    "적용 기준",
    "예외 기준",
    "이력 기준",
    "기본 적용 기준",
    "정책 항목",
    "기준",
    "결과 구분",
    "결과 유형",
    "고객 안내 항목",
    "알림 채널",
    "반영 기준",
    "실패 안내",
    "이력 저장",
    "보관 기간",
    "관리 대상",
    "승인 조건",
    "모니터링 주기",
    "상담 전환 대상",
    "재시도 허용 횟수",
    "장애 안내 항목",
    "예외 이력 저장 항목",
    "민감정보 제한",
    "마스킹 기준",
    "열람 통제",
    "파기 이력 저장 항목",
    "허용 목록",
    "제한 조건",
    "고지 항목",
}

MOCK_POLICY_ID_SCOPE_LABELS = {
    "ACC": "접근·권한",
    "INF": "정보 노출",
    "CST": "고객 상태",
    "VAL": "가능 여부",
    "AUT": "인증·동의",
    "INP": "입력값",
    "IMP": "영향도 고지",
    "REQ": "요청 접수",
    "DUP": "중복 요청",
    "BSS": "BSS 연계",
    "STAT": "상태 전환",
    "RSLT": "처리 결과·이력",
    "NEXT": "후속 업무",
    "ERR": "예외·상담",
    "NTC": "알림·고지",
    "PRV": "개인정보·로그",
    "OPR": "운영 관리",
    "QUL": "품질 관리",
    "REQMAP": "요구사항 반영",
    "DATA": "데이터 보관",
}


def mock_policy_detail_axis(name: str, policy_id: str, index: int) -> tuple[str, str, str]:
    text = f"{mock_clean_policy_detail_name(name)} {policy_id}"
    keyword_axes = (
        (("유형별", "신규", "변경 유형", "업무 유형"), mock_policy_detail_axis_index("유형별 적용 기준", 0)),
        (("채널별", "셀프", "앱", "웹", "상담 경로"), mock_policy_detail_axis_index("채널별 처리 기준", 0)),
        (("주체별", "대리", "법정대리인", "권한"), mock_policy_detail_axis_index("주체별 권한 기준", 0)),
        (("사용 여부", "미사용", "사용 완료", "소진", "혜택 사용"), mock_policy_detail_axis_index("사용·소진 여부 기준", 0)),
        (("자동 판정", "수동 조정", "자동·수동"), mock_policy_detail_axis_index("자동·수동 조정 기준", 0)),
        (("보관 기간", "보존 기간", "보관기한", "보관 기한"), 22),
        (("우선순위", "우선", "선순위"), 14),
        (("충돌", "불일치", "정합"), 15),
        (("재요청", "중복", "반복"), 16),
        (("부분", "일부", "부분 성공"), 17),
        (("취소", "철회"), 18),
        (("보정", "수동", "승인"), 19),
        (("품질", "모니터링", "완료율", "실패율", "상담 전환율"), 20),
        (("데이터", "동기화", "정합성"), 21),
        (("동의", "약관", "개인정보"), 3),
        (("횟수", "회수", "재시도"), 4),
        (("만료", "기한", "기간"), 5),
        (("상태", "전환", "변경"), 6),
        (("BSS", "원장", "반영"), 7),
        (("외부", "연계", "승인", "기관", "제휴"), 8),
        (("고지", "안내", "알림", "통지"), 9),
        (("이력", "로그", "저장", "보관", "기록"), 10),
        (("예외", "복구", "보정"), 11),
        (("운영", "검토", "확인"), 12),
        (("회신", "결과", "응답"), 13),
        (("제한", "차단", "불가", "보류"), 1),
        (("허용", "대상", "가능"), 0),
        (("인증번호", "인증", "본인", "재인증", "유효시간", "유효 시간"), 2),
    )
    for keywords, axis_index in keyword_axes:
        if any(keyword in text for keyword in keywords):
            return MOCK_POLICY_DETAIL_AXES[axis_index]
    digest = hashlib.sha1(f"{text}:{index}".encode("utf-8")).hexdigest()
    return MOCK_POLICY_DETAIL_AXES[(int(digest[:8], 16) + index) % len(MOCK_POLICY_DETAIL_AXES)]


def mock_refine_policy_detail_name(name: str, policy_id: str, index: int, axis_name: str = "", suffix: str = "") -> str:
    if not axis_name or not suffix:
        axis_name, _, suffix = mock_policy_detail_axis(name, policy_id, index)
    cleaned = mock_clean_policy_detail_name(name)
    variant = MOCK_POLICY_DETAIL_NAME_VARIANTS[index % len(MOCK_POLICY_DETAIL_NAME_VARIANTS)]
    generic = not cleaned or cleaned in MOCK_GENERIC_POLICY_DETAIL_NAMES or re.fullmatch(r"\d+번\s*기준", cleaned)
    if generic:
        scoped_name = mock_scoped_policy_detail_name(cleaned, policy_id)
        if scoped_name:
            return scoped_name
        return f"{axis_name} - {variant}"
    staged_name = mock_staged_policy_detail_name(cleaned, index)
    if staged_name:
        scoped_name = mock_scoped_policy_detail_name(staged_name, policy_id)
        return scoped_name or staged_name
    if any(keyword in cleaned for keyword in ("적용 기준", "예외 기준", "이력 기준", "기본 적용 기준")):
        return f"{suffix} {cleaned}"
    return cleaned


def mock_clean_policy_detail_name(name: object) -> str:
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip()
    for variant in MOCK_POLICY_DETAIL_NAME_VARIANTS:
        cleaned = re.sub(rf"\s*-\s*{re.escape(variant)}\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s*기준\s+기준$", " 기준", cleaned).strip()
    return cleaned


def mock_policy_scope_label(policy_id: str) -> str:
    match = re.match(r"PG-[^-]+-([A-Z]+)-", str(policy_id or "").strip())
    if not match:
        return ""
    return MOCK_POLICY_ID_SCOPE_LABELS.get(match.group(1), "")


def mock_scoped_policy_detail_name(cleaned: str, policy_id: str) -> str:
    cleaned = str(cleaned or "").strip()
    if not cleaned or cleaned in {"적용 기준", "예외 기준", "이력 기준", "기본 적용 기준", "정책 항목", "기준"}:
        return ""
    scope = mock_policy_scope_label(policy_id)
    if not scope:
        return ""
    scope_tokens = [token for token in re.split(r"[·/\s]+", scope) if len(token) > 1]
    if any(token in cleaned for token in scope_tokens):
        return cleaned
    return f"{scope} {cleaned}"


def mock_staged_policy_detail_name(cleaned: str, index: int) -> str:
    cleaned = str(cleaned or "").strip()
    variant = MOCK_POLICY_DETAIL_NAME_VARIANTS[index % len(MOCK_POLICY_DETAIL_NAME_VARIANTS)]
    if cleaned.endswith("상태·제한 기준"):
        base = cleaned[: -len("상태·제한 기준")].strip()
        return f"{base} {variant} 제한 기준".strip()
    if cleaned.endswith("예외 기준") and len(cleaned) <= 16:
        base = cleaned[: -len("예외 기준")].strip()
        return f"{base} {variant} 예외 기준".strip()
    if cleaned in {"조회·탐색 기준", "운영 기준", "업무 조건 기준", "가입·신청 기준", "고지·안내 기준"}:
        base = cleaned[: -len("기준")].strip()
        return f"{base} {variant} 기준".strip()
    return ""


def mock_repair_policy_detail(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    row = dict(item)
    policy_id = str(row.get("policy_id") or "").strip()
    name = str(row.get("name") or row.get("id") or f"정책 항목 {index + 1}").strip()
    original_content = str(row.get("content") or "").strip()
    axis_name, content_template, suffix = mock_policy_detail_axis(name, policy_id, index)
    refined_name = mock_refine_policy_detail_name(name, policy_id, index, axis_name, suffix)
    row["name"] = mock_naturalize_text(refined_name)
    setting_content = mock_setting_policy_detail_content(refined_name, original_content, policy_id)
    if setting_content:
        row["content"] = mock_naturalize_text(setting_content)
        return row
    polished_content = mock_polish_preserved_policy_content(refined_name, policy_id, original_content)
    if polished_content != original_content:
        row["content"] = mock_naturalize_text(polished_content)
    elif mock_policy_content_needs_rewrite(original_content):
        row["content"] = mock_naturalize_text(mock_policy_detail_content(refined_name, content_template, index))
    else:
        row["content"] = mock_naturalize_text(original_content)
    return row


def mock_setting_policy_detail_content(name: str, content: str, policy_id: str = "") -> str:
    name_text = str(name or "")
    content_text = re.sub(r"\s+", " ", str(content or "")).strip()
    settings_scope_keywords = (
        "다국어",
        "언어",
        "쉬운모드",
        "접근성",
        "개인화",
        "추천",
        "홈",
        "퀵액션",
        "초기화",
        "삭제",
        "리셋",
        "로그아웃",
        "세션",
        "잠금",
        "보안",
        "알림",
        "수신",
        "환경설정",
        "설정",
    )
    is_settings_scope = "-LWI-" in str(policy_id or "") or any(
        keyword in name_text for keyword in settings_scope_keywords
    )
    if not is_settings_scope:
        return ""
    setting_keywords = (
        "다국어",
        "언어",
        "쉬운모드",
        "접근성",
        "개인화",
        "추천",
        "홈",
        "퀵액션",
        "동의",
        "권한",
        "초기화",
        "삭제",
        "리셋",
        "로그아웃",
        "세션",
        "잠금",
        "보안",
        "알림",
        "수신",
        "환경설정",
    )
    if not any(keyword in name_text for keyword in setting_keywords):
        return ""
    generic_markers = (
        "업무별 기준",
        "판정 결과가 허용·제한·보류·실패",
        "허용 대상은 업무 책임",
        "제한 조건은 제한·보류·만료",
        "요청 시각, 판정 결과",
        "네트워크 실패나 연계 지연",
    )
    should_replace = not content_text or mock_policy_content_needs_rewrite(content_text) or any(
        marker in content_text for marker in generic_markers
    )
    if not should_replace:
        return ""
    if any(keyword in name_text for keyword in ("다국어", "언어", "쉬운모드", "접근성")):
        return (
            f"{name_text}은 언어, 쉬운모드, 홈 우선 영역, 추천 노출 같은 개인화 항목을 고객이 직접 조정할 수 있게 한다. "
            "변경값은 고객 단위로 저장하고 기본값 복원 또는 기기 변경 시 적용 기준을 함께 안내한다."
        )
    if any(keyword in name_text for keyword in ("초기화", "삭제", "리셋")):
        return (
            f"{name_text}은 초기화 대상, 삭제 범위, 복구 가능 여부, 재학습 시작 시점을 처리 전에 고지한다. "
            "초기화가 완료되면 이전 개인화 결과 사용을 중단하고 처리 일시와 요청 주체를 이력으로 저장한다."
        )
    if any(keyword in name_text for keyword in ("로그아웃", "세션", "잠금", "보안")):
        return (
            f"{name_text}은 세션 유지 시간, 자동 로그아웃 조건, 재인증 필요 업무, 민감정보 보호 수준을 설정 기준으로 관리한다. "
            "변경 즉시 적용 여부와 예외 업무를 안내하고 변경 이력을 저장한다."
        )
    if any(keyword in name_text for keyword in ("동의", "권한")):
        return (
            f"{name_text}은 개인화·AI·민감 기능의 사용 여부를 필수·선택 동의, 권한 범위, 철회 가능 여부로 구분한다. "
            "고객이 동의를 변경하면 적용 범위와 제한되는 기능을 즉시 안내하고 변경 이력을 저장한다."
        )
    if any(keyword in name_text for keyword in ("알림", "수신", "환경설정")):
        return (
            f"{name_text}은 알림 유형, 수신 채널, 표시 방식, 필수 알림 예외를 고객이 구분해 선택할 수 있게 한다. "
            "필수 고지성 알림은 수신 거부 대상에서 제외하고 선택 알림은 변경 즉시 수신 기준에 반영한다."
        )
    if any(keyword in name_text for keyword in ("개인화", "추천", "홈", "퀵액션")):
        return (
            f"{name_text}은 홈 우선 영역, 추천 노출, 퀵액션, 기본 진입 경로를 고객 맥락에 맞게 조정하는 기준이다. "
            "고객이 변경한 값은 즉시 반영하되 기본값 복원과 적용 제외 조건을 함께 안내한다."
        )
    return ""


def mock_polish_preserved_policy_content(refined_name: str, policy_id: str, content: str) -> str:
    """Keep good local policy text, but remove vague mock-era placeholders."""

    name = str(refined_name or "")
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return text
    if "업무별 권한 기준" in text or "기준을 충족한 경우" in text or "조건을 충족한 경우" in text:
        if any(keyword in name for keyword in ("권한", "접근", "대리", "법정대리인", "제한 대상")):
            return (
                "대리 처리, 법정대리인, 법인, 미성년, 제한 고객은 본인확인, 대리 권한, "
                "법정대리인 동의, 고객 상태가 모두 확인된 경우에만 진행한다."
            )
    if any(keyword in name for keyword in ("보관 기간", "보존 기간", "보관기한", "보관 기한")):
        if "내부 기준" in text or len(text) < 38:
            return (
                "보관 기간은 법정 보관 사유, 고객 분쟁 대응, 처리 이력 추적 필요성을 기준으로 정한다. "
                "기간 만료 시 파기 대상으로 전환하고 파기 이력을 저장한다."
            )
    if any(keyword in name for keyword in ("인증번호 유효시간", "인증 유효 시간", "유효시간")):
        if len(text) < 30:
            return "인증 유효 시간은 10분이며 만료되면 재인증을 요구하고 실패 이력을 저장한다."
    return text


def mock_policy_content_needs_rewrite(content: str) -> bool:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if len(text) < 24:
        return True
    weak_markers = (
        "업무별 권한 기준",
        "업무별 기준",
        "내부 기준",
        "시스템 기준",
        "관련 정책",
        "필요 시",
        "별도 기준",
        "추후 협의",
        "검토 필요",
        "…",
        "...",
        "정책에 따라 처리",
        "시스템에서 처리",
        "고객 상태, 인증 결과, 동의 여부, 연계 시스템 응답",
        "고객 영향도를 기준으로 재시도, 상담 전환, 운영 확인",
    )
    if any(marker in text for marker in weak_markers):
        return True
    if re.search(
        r"^(요청 접수|조건 판정|결과 확정|예외 처리|후속 안내|이력 저장|연계 확인|운영 검토|품질 확인)\s*시\s*[^.]{2,80}기준은\s*",
        text,
    ):
        return True
    if re.search(
        r"^(접수 허용 기준|제한 안내 기준|이력 저장 기준|재검증 기준|상담 전환 기준|결과 회신 기준|운영 확인 기준|고객 고지 기준)\s*:\s*[^.]{2,100}기준은\s*",
        text,
    ):
        return True
    if re.search(r"기준은\s*(허용 대상은|제한 조건은|BSS 반영은|판정 결과가|처리 결과가)", text):
        return True
    decision_markers = (
        "허용",
        "제한",
        "필수",
        "선택",
        "상태",
        "인증",
        "동의",
        "고지",
        "안내",
        "이력",
        "저장",
        "보관",
        "만료",
        "취소",
        "보류",
        "실패",
        "재시도",
        "상담",
        "BSS",
        "연계",
        "원장",
        "우선순위",
    )
    return not (any(marker in text for marker in decision_markers) or re.search(r"\d+\s*(회|분|시간|일|개월|년|%)", text))


def mock_policy_detail_content(refined_name: str, content_template: str, index: int) -> str:
    content = content_template.format(name=refined_name)
    context_label = mock_policy_detail_context_label(refined_name)
    if not context_label:
        if mock_auth_valid_time_is_direct(refined_name, content):
            return content
        return mock_contextualize_policy_content(
            refined_name,
            content,
            phase=MOCK_POLICY_DETAIL_PHASE_VARIANTS[index % len(MOCK_POLICY_DETAIL_PHASE_VARIANTS)],
        )
    return mock_contextualize_policy_content(
        context_label,
        content,
        suffix="단계",
        qualifier=MOCK_POLICY_DETAIL_CONTEXT_VARIANTS[index % len(MOCK_POLICY_DETAIL_CONTEXT_VARIANTS)],
    )


def mock_contextualize_policy_content(
    subject: str,
    content: str,
    *,
    suffix: str = "기준",
    qualifier: str = "",
    phase: str = "",
) -> str:
    subject = str(subject or "").strip()
    if not subject:
        return content
    if " - " in subject:
        subject = subject.split(" - ", 1)[0].strip()
    subject = mock_clean_policy_detail_name(subject)
    subject_core = re.sub(r"\s*기준$", "", subject).strip() or subject
    subject_label = subject if subject.endswith(suffix) else f"{subject_core} {suffix}"
    subject_particle = korean_topic_particle(subject)
    core_particle = korean_topic_particle(subject_core)
    sentence_subject = subject_core if subject_label.endswith("기준") else subject_label
    sentence_particle = korean_topic_particle(sentence_subject)
    # Mock documents should exercise the repair loop, but they still need to
    # read like policy text. Avoid mechanical "조건 판정 시 A 기준은 B는"
    # scaffolding and start from the actual judgment value whenever possible.
    if content.startswith("인증 유효 시간은"):
        return mock_naturalize_text(content)
    replacements = (
        ("허용 대상은", f"{subject_core}{core_particle}"),
        ("제한 조건은", f"{subject_core}의 제한 조건은"),
        ("필수 약관과", f"{subject_label}에서는 필수 약관과"),
        ("요청 실패가", f"{subject_label}에서 요청 실패가"),
        ("고객 응답 없이", f"{subject_label}에서 고객 응답 없이"),
        ("판정 결과가", f"{sentence_subject}{sentence_particle} 판정 결과가"),
        (
            "BSS 반영은",
            "BSS 반영은" if any(token in subject_core for token in ("BSS", "원장", "반영")) else f"{subject_core}의 BSS 반영은",
        ),
        (
            "외부 연계는",
            "외부 연계는" if any(token in subject_core for token in ("외부", "연계", "제휴")) else f"{subject_core}의 외부 연계는",
        ),
        ("결과가", f"{subject_core}의 결과가"),
        ("요청 시각,", f"{subject_label}에서는 요청 시각,"),
        ("네트워크 실패나", f"{subject_label}에서 네트워크 실패나"),
        ("자동 판정만으로", f"{subject_label}은 자동 판정만으로"),
        ("처리 결과가", f"{sentence_subject}{sentence_particle} 처리 결과가"),
        (
            "우선순위는",
            "우선순위는" if "우선순위" in subject_core else f"{subject_core}의 우선순위는",
        ),
        ("채널 결과와", f"{subject_label}은 채널 결과와"),
        ("이전 요청이", f"{subject_label}에서 이전 요청이"),
        ("일부 연계만", f"{subject_label}에서 일부 연계만"),
        (
            "BSS 반영 전이고",
            "BSS 반영 전이고" if any(token in subject_core for token in ("BSS", "반영")) else f"{subject_label}은 BSS 반영 전이고",
        ),
        ("고객 피해 가능성과", f"{subject_label}에서 고객 피해 가능성과"),
        ("실패·보류·상담 전환이", f"{subject_label}에서 실패·보류·상담 전환이"),
        ("고객 상태,", f"{subject_label}에서는 고객 상태,"),
    )
    for old, new in replacements:
        if content.startswith(old):
            return mock_naturalize_text(new + content[len(old) :])
    return mock_naturalize_text(f"{subject_label}에서는 {content}")


def mock_auth_valid_time_is_direct(refined_name: str, content: str) -> bool:
    name = str(refined_name or "")
    return content.startswith("인증 유효 시간은") and any(keyword in name for keyword in ("인증번호", "유효시간", "유효 시간"))


def mock_policy_detail_context_label(refined_name: str) -> str:
    if " - " not in refined_name:
        return ""
    label = refined_name.rsplit(" - ", 1)[-1].strip()
    return label if label in MOCK_POLICY_DETAIL_NAME_VARIANTS else ""


def mock_final_revision_patch_payload(text: str) -> dict[str, Any]:
    spec_pack = extract_labeled_json(text, labels=("현재 정책서 JSON 요약:",)) or {}
    feedback_pack = extract_labeled_json(text, labels=("Final Inspector 보완 요청:",)) or {}
    feedback_text = json.dumps(feedback_pack, ensure_ascii=False) + "\n" + text
    updates: list[dict[str, Any]] = []
    functions = spec_pack.get("functions", []) if isinstance(spec_pack.get("functions"), list) else []
    needs_function_name = "기능명 반복" in feedback_text or "functions[*].name" in feedback_text
    needs_function_details = (
        "기능 세부 구성 반복" in feedback_text
        or "세부 기능 구성 반복" in feedback_text
        or "functions[*].details" in feedback_text
    )
    repeated_detail_signatures = mock_repeated_function_detail_signatures(functions)
    for index, item in enumerate(functions):
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        current_name = str(item.get("name") or "").strip()
        repaired_name = mock_refine_function_name(current_name, index)
        if (needs_function_name or mock_label_has_adjacent_duplicate(current_name)) and repaired_name and repaired_name != current_name:
            updates.append(
                {
                    "collection": "functions",
                    "id": item_id,
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "field": "name",
                    "value": repaired_name,
                    "values": [],
                    "reason": "Mock strict final finding의 기능명 반복 보완",
                }
            )
        current_details = tuple(str(value).strip() for value in item.get("details", []) if str(value).strip()) if isinstance(item.get("details"), list) else ()
        if needs_function_details and current_details in repeated_detail_signatures:
            repaired_details = mock_revision_function_detail_values(item, index)
            updates.append(
                {
                    "collection": "functions",
                    "id": item_id,
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "field": "details",
                    "value": "",
                    "values": repaired_details,
                    "reason": "Mock strict final finding의 기능 세부 구성 반복 보완",
                }
            )
        if len(updates) >= 18:
            break
    if not updates:
        for item in functions:
            if not isinstance(item, Mapping):
                continue
            item_id = str(item.get("id") or "").strip()
            if item_id:
                updates.append(
                    {
                        "collection": "functions",
                        "id": item_id,
                        "match_current_state": "",
                        "match_event": "",
                        "match_next_state": "",
                        "field": "description",
                        "value": mock_repair_function(item, len(updates)).get("description", ""),
                        "values": [],
                        "reason": "Mock strict final finding의 기능 밀도 보완",
                    }
                )
            if len(updates) >= 18:
                break
    for item in spec_pack.get("policy_details", []) if isinstance(spec_pack.get("policy_details"), list) else []:
        if len(updates) >= 18:
            break
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("id") or "").strip()
        original_content = str(item.get("content") or "").strip()
        repaired_content = mock_repair_policy_detail(item, len(updates)).get("content", "")
        if item_id and repaired_content != original_content:
            updates.append(
                {
                    "collection": "policy_details",
                    "id": item_id,
                    "match_current_state": "",
                    "match_event": "",
                    "match_next_state": "",
                    "field": "content",
                    "value": repaired_content,
                    "values": [],
                    "reason": "Mock strict final finding의 정책 구체성 보완",
                }
            )
    return {"updates": updates[:18], "notes": ["Mock LLM 미사용 모드에서 strict final finding을 deterministic patch로 보완했습니다."]}


def mock_repeated_function_detail_signatures(functions: object) -> set[tuple[str, ...]]:
    if not isinstance(functions, list):
        return set()
    counts: dict[tuple[str, ...], int] = {}
    for item in functions:
        if not isinstance(item, Mapping) or not isinstance(item.get("details"), list):
            continue
        signature = tuple(str(value).strip() for value in item.get("details", []) if str(value).strip())
        if not signature:
            continue
        counts[signature] = counts.get(signature, 0) + 1
    threshold = max(5, int(len(functions) * 0.30)) if functions else 5
    return {signature for signature, count in counts.items() if count >= threshold}


def mock_label_has_adjacent_duplicate(value: object) -> bool:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", str(value or ""))
    return any(left == right and left for left, right in zip(tokens, tokens[1:]))


def mock_revision_function_detail_values(item: Mapping[str, Any], index: int) -> list[str]:
    name = mock_refine_function_name(str(item.get("name") or item.get("id") or f"기능 {index + 1}"), index)
    text = f"{name} {item.get('description', '')}"
    patterns: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (("진입", "접근", "대상"), ("업무 대상 조회", "접근 권한 검증", "진입 결과 저장")),
        (("조회", "정보", "목록", "상세"), ("조회 대상 식별", "조회 조건 검증", "표시 결과 구성")),
        (("권한", "상태", "조건", "가능", "검증"), ("고객 상태 확인", "처리 조건 검증", "제한 사유 고지")),
        (("입력", "인증", "동의"), ("입력값 정합성 확인", "인증·동의 결과 검증", "요청 정보 구성")),
        (("영향", "비용", "혜택", "할인", "요금"), ("고객 영향도 산정", "적용 기준 검증", "사전 고지 구성")),
        (("요청", "접수", "중복"), ("요청 정보 구성", "중복 요청 판정", "접수 이력 저장")),
        (("결과", "반영", "완료", "실패"), ("처리 결과 판정", "후속 상태 반영", "완료·실패 안내")),
        (("후속", "취소", "재시도", "복구"), ("후속 가능 여부 판정", "복구 조건 확인", "상담 전환 안내")),
        (("운영", "예외", "승인", "보정"), ("운영 기준 조회", "예외 사유 분류", "검토 이력 저장")),
        (("연계", "BSS", "응답"), ("연계 요청 구성", "응답 결과 검증", "불일치 이력 저장")),
    )
    for keywords, details in patterns:
        if any(keyword in text for keyword in keywords):
            return mock_contextualize_revision_function_details(name, details)
    fallbacks = (
        ("요청 대상 조회", "처리 조건 검증", "결과 이력 저장"),
        ("기준 정보 조회", "허용 여부 판정", "고객 안내 구성"),
        ("상태 정보 확인", "예외 사유 분류", "후속 처리 연결"),
        ("연계 결과 확인", "보류 여부 판정", "재시도 안내 저장"),
    )
    return mock_contextualize_revision_function_details(name, fallbacks[index % len(fallbacks)])


def mock_contextualize_revision_function_details(name: str, details: Sequence[str]) -> list[str]:
    contextualized = [mock_naturalize_text(value) for value in details if str(value).strip()]
    if not contextualized:
        return []
    base = mock_collapse_repeated_label_tokens(name)
    base = re.sub(r"\s+\d+\s*$", "", base).strip()
    base = re.sub(r"\s*(처리 기준 확인|기준 검증|정보 구성|구성|확인|검증|조회|처리|기능)\s*$", "", base).strip()
    base = base[:18]
    if base and base not in contextualized[0]:
        action = "조회"
        if "검증" in contextualized[0]:
            action = "검증"
        elif "판정" in contextualized[0]:
            action = "판정"
        elif "저장" in contextualized[0]:
            action = "저장"
        contextualized[0] = mock_naturalize_text(f"{base} {action}")[:36]
    return contextualized


def mock_refine_function_name(name: str, index: int) -> str:
    """Keep no-cost mock output useful for structural regression tests."""

    capability_names = (
        "대상 조건 조회",
        "가능 여부 검증",
        "요청 정보 구성",
        "처리 결과 저장",
        "고객 안내 구성",
        "연계 응답 확인",
        "이력 정보 저장",
        "운영 예외 분류",
    )
    cleaned = re.sub(r"\s*처리\s*기능\s*\d+\s*$", "", str(name or "")).strip()
    cleaned = re.sub(r"\s*(처리\s*)?기능\s*\d+\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s*(처리\s*)?기능\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s*처리\s*$", "", cleaned).strip()
    cleaned = mock_naturalize_text(cleaned)
    cleaned = mock_collapse_repeated_label_tokens(cleaned)
    collision_match = re.search(r"\s+(\d+)$", cleaned)
    if collision_match:
        collision_index = max(0, int(collision_match.group(1)) - 2)
        cleaned = cleaned[: collision_match.start()].strip()
        if cleaned:
            return mock_function_name_collision_variant(cleaned, collision_index)
    if not cleaned or re.fullmatch(r"\d+번", cleaned):
        return capability_names[index % len(capability_names)]
    if cleaned.endswith(("조회", "검증", "판정", "산정", "저장", "안내", "구성", "확인", "분류", "연동", "관리")):
        return cleaned
    if any(keyword in cleaned for keyword in ("인증", "동의", "권한", "조건", "가능")):
        return f"{cleaned} 기준 검증"
    if any(keyword in cleaned for keyword in ("결과", "완료", "안내")):
        return f"{cleaned} 구성"
    if any(keyword in cleaned for keyword in ("이력", "로그", "저장")):
        return f"{cleaned} 저장"
    if any(keyword in cleaned for keyword in ("연계", "BSS", "응답")):
        return f"{cleaned} 확인"
    return mock_collapse_repeated_label_tokens(f"{cleaned} 정보 구성")


def mock_function_name_collision_variant(base_name: str, index: int) -> str:
    base = mock_collapse_repeated_label_tokens(mock_naturalize_text(base_name))
    stem = re.sub(
        r"\s*(처리 기준 확인|기준 검증|조건 검증|정보 구성|조건 확인|결과 구성|이력 저장|고지 구성|연계 확인|예외 판정|구성|확인|검증|조회|처리|기능)\s*$",
        "",
        base,
    ).strip()
    stem = stem or base or "업무"
    suffixes = (
        "조건 검증",
        "결과 구성",
        "이력 저장",
        "고지 구성",
        "연계 확인",
        "예외 판정",
    )
    suffix = suffixes[index % len(suffixes)]
    if stem.endswith("조건") and suffix.startswith("조건 "):
        suffix = suffix.removeprefix("조건 ").strip()
    return mock_collapse_repeated_label_tokens(f"{stem} {suffix}")


def mock_collapse_repeated_label_tokens(value: str) -> str:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+|[^0-9A-Za-z가-힣]+", str(value or ""))
    result: list[str] = []
    previous_word = ""
    for token in tokens:
        if re.fullmatch(r"[0-9A-Za-z가-힣]+", token):
            if token == previous_word:
                continue
            previous_word = token
        elif token.strip():
            previous_word = ""
        result.append(token)
    return re.sub(r"\s+", " ", "".join(result)).strip()


def mock_function_process_ids(function: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    process_id = str(function.get("process_id", "")).strip()
    if process_id:
        values.append(process_id)
    process_ids = function.get("process_ids")
    if isinstance(process_ids, list):
        values.extend(str(value).strip() for value in process_ids if str(value).strip())
    return unique_nonempty_strings(values)


def mock_extract_state_usecases(text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for label in ("승인된 유즈케이스 계약:", "유즈케이스 기반 상태 lifecycle 계약:", "이전 장 요약:"):
        payload = extract_labeled_json(text, labels=(label,))
        if not isinstance(payload, Mapping):
            continue
        raw_items: Any = None
        if isinstance(payload.get("allowed_transition_usecase_ids"), list):
            raw_items = payload.get("allowed_transition_usecase_ids")
        elif isinstance(payload.get("usecase_lifecycles"), list):
            raw_items = payload.get("usecase_lifecycles")
        elif isinstance(payload.get("usecases"), list):
            raw_items = payload.get("usecases")
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if not isinstance(item, Mapping):
                continue
            usecase_id = str(item.get("id") or item.get("usecase_id") or "").strip()
            name = str(item.get("name") or item.get("usecase_name") or "").strip()
            actor = str(item.get("actor") or "").strip()
            if usecase_id and name:
                candidates.append({"id": usecase_id, "name": name, "actor": actor})
        if candidates:
            break
    return dedupe_mock_usecases(candidates)


def dedupe_mock_usecases(usecases: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for usecase in usecases:
        usecase_id = str(usecase.get("id", "")).strip()
        if not usecase_id or usecase_id in seen:
            continue
        seen.add(usecase_id)
        result.append(
            {
                "id": usecase_id,
                "name": str(usecase.get("name", "")).strip(),
                "actor": str(usecase.get("actor", "")).strip(),
            }
        )
    return result


def mock_business_code_from_usecases(usecases: Sequence[Mapping[str, str]]) -> str:
    for usecase in usecases:
        parts = str(usecase.get("id", "")).strip().split("-")
        if len(parts) >= 3 and parts[1]:
            return parts[1]
    return "MCK"


def unique_nonempty_strings(values: Sequence[str] | Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def extract_base_contract_payload(text: str) -> dict[str, Any] | None:
    payload = extract_first_json_object(text)
    if not isinstance(payload, Mapping):
        return None
    contract = payload.get("base_contract")
    return dict(contract) if isinstance(contract, Mapping) else None


def extract_schema_like_json(text: str, schema: Mapping[str, Any]) -> dict[str, Any] | None:
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    if not properties:
        return extract_first_json_object(text)
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and any(key in candidate for key in properties):
            return candidate
    return None


def extract_labeled_json(text: str, *, labels: Sequence[str]) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for label in labels:
        index = text.find(label)
        if index < 0:
            continue
        tail = text[index + len(label) :]
        object_start = tail.find("{")
        if object_start < 0:
            continue
        try:
            candidate, _ = decoder.raw_decode(tail[object_start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return None


def mock_prompt_json_value(text: str, label: str) -> Any | None:
    decoder = json.JSONDecoder()
    index = text.find(label)
    if index < 0:
        return None
    tail = text[index + len(label) :]
    for start, char in enumerate(tail):
        if char not in "[{":
            continue
        try:
            candidate, _ = decoder.raw_decode(tail[start:])
        except json.JSONDecodeError:
            continue
        return candidate
    return None


def extract_first_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            return candidate
    return None


def extract_json_text_value(text: str, key: str) -> str:
    payload = extract_first_json_object(text)
    if isinstance(payload, Mapping):
        value = payload.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def coerce_mock_payload_to_schema(payload: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    value = coerce_mock_value(payload, schema, key_hint="")
    return value if isinstance(value, dict) else {}


def coerce_mock_value(value: Any, schema: Mapping[str, Any], *, key_hint: str) -> Any:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0] if schema_type else "string")
    if "enum" in schema and value in schema.get("enum", []):
        return value
    if "enum" in schema:
        enum_values = schema.get("enum") or []
        return enum_values[0] if enum_values else value
    if schema_type == "object" or "properties" in schema:
        source = value if isinstance(value, Mapping) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
        required = schema.get("required") if isinstance(schema.get("required"), list) else list(properties.keys())
        result: dict[str, Any] = {}
        for prop, prop_schema in properties.items():
            if prop in source:
                result[prop] = coerce_mock_value(source[prop], prop_schema, key_hint=prop)
            elif prop in required:
                result[prop] = mock_default_value(prop_schema, prop)
        return result
    if schema_type == "array":
        item_schema = schema.get("items") if isinstance(schema.get("items"), Mapping) else {}
        items = value if isinstance(value, list) else []
        return [coerce_mock_value(item, item_schema, key_hint=key_hint) for item in items]
    if schema_type == "boolean":
        return bool(value) if isinstance(value, bool) else True
    if schema_type == "integer":
        return value if isinstance(value, int) and not isinstance(value, bool) else 1
    if schema_type == "number":
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 1
    if schema_type == "null":
        return None
    if isinstance(value, str):
        return mock_naturalize_text(value)
    return mock_default_scalar(key_hint)


def mock_default_value(schema: Mapping[str, Any], key_hint: str) -> Any:
    if "enum" in schema:
        enum_values = schema.get("enum") or []
        return enum_values[0] if enum_values else ""
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), schema_type[0] if schema_type else "string")
    if schema_type == "object" or "properties" in schema:
        return coerce_mock_value({}, schema, key_hint=key_hint)
    if schema_type == "array":
        return []
    if schema_type == "boolean":
        return False
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0
    if schema_type == "null":
        return None
    return mock_default_scalar(key_hint)


def mock_default_scalar(key_hint: str) -> str:
    normalized = key_hint.casefold()
    if "status" in normalized:
        return "pass"
    if "summary" in normalized:
        return "Mock LLM 응답입니다."
    if "title" in normalized:
        return "Mock 응답"
    if "message" in normalized:
        return "Mock LLM 모드입니다."
    return ""


def should_retry_http(status_code: int, attempt: int, max_retries: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES and attempt <= max_retries


def should_retry_transport(attempt: int, max_retries: int) -> bool:
    return attempt <= max_retries


def response_incomplete_reason(response_data: Mapping[str, Any]) -> str:
    details = response_data.get("incomplete_details")
    if not isinstance(details, Mapping):
        return ""
    return str(details.get("reason", "") or "")


def next_output_token_cap(current: int, configured_max: int | None) -> int:
    if configured_max is None:
        return current
    if current >= configured_max:
        return current
    return min(configured_max, max(current * 2, current + 2000))


def extract_response_text(response_data: Mapping[str, Any]) -> str:
    direct = response_data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    for item in response_data.get("output", []) if isinstance(response_data.get("output"), list) else []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks).strip()


def request_token_context_size(
    instructions: str,
    input_messages: Sequence[Mapping[str, str]],
    schema: Mapping[str, Any],
) -> dict:
    input_chars = sum(len(str(message.get("content", ""))) for message in input_messages)
    return {
        "instructions_chars": len(instructions),
        "input_chars": input_chars,
        "schema_chars": len(json.dumps(schema, ensure_ascii=False)),
        "input_message_count": len(input_messages),
    }


def usage_summary(response_data: Mapping[str, Any]) -> dict:
    usage = response_data.get("usage")
    if not isinstance(usage, dict):
        return {}
    keys = (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_input_tokens",
        "reasoning_tokens",
    )
    summary = {key: usage.get(key) for key in keys if usage.get(key) is not None}
    for nested_key in ("input_tokens_details", "output_tokens_details"):
        nested = usage.get(nested_key)
        if isinstance(nested, dict):
            summary[nested_key] = nested
    return summary


def tool_names(tools: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(tool.get("type", "")) for tool in tools if isinstance(tool, Mapping)]


def summarize_error(value: str) -> str:
    try:
        data = json.loads(value)
        message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else ""
        if message:
            return str(message)
    except json.JSONDecodeError:
        pass
    return value[:500]


def elapsed_ms(start_time: float) -> int:
    return int((time.monotonic() - start_time) * 1000)


def write_llm_log(payload: Mapping[str, Any]) -> None:
    try:
        LLM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **dict(payload),
        }
        with LLM_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return
