"""S11-Gemini — GeminiProvider 단위 테스트.

TDD 1단계: 구현 전 테스트 먼저 작성.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.genai import errors as gemini_errors

from storytale.interpreter.llm_client import LLMClientError

# ---------------------------------------------------------------------------
# 헬퍼: mock 응답 생성
# ---------------------------------------------------------------------------


def _make_response(
    text: str,
    prompt_tokens: int = 10,
    candidate_tokens: int = 20,
) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = MagicMock(
        prompt_token_count=prompt_tokens,
        candidates_token_count=candidate_tokens,
    )
    return resp


def _server_error(code: int = 500) -> gemini_errors.ServerError:
    return gemini_errors.ServerError(code, {"error": "Server Error"})


def _client_error(code: int = 401) -> gemini_errors.ClientError:
    return gemini_errors.ClientError(code, {"error": "Client Error"})


# ---------------------------------------------------------------------------
# 1. complete() — 기본 성공 케이스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_returns_text_on_success():
    """정상 응답 시 텍스트 반환."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")
    expected = "안녕하세요!"

    with patch.object(
        provider._client.aio.models, "generate_content", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = _make_response(expected)
        result = await provider.complete("system prompt", "user message")

    assert result == expected


@pytest.mark.asyncio
async def test_complete_passes_correct_params():
    """system_instruction, temperature, max_output_tokens 가 올바르게 전달된다."""
    from google.genai import types

    from storytale.interpreter.gemini_provider import (
        DEFAULT_GEMINI_MODEL,
        GeminiProvider,
    )

    provider = GeminiProvider(api_key="test")

    with patch.object(
        provider._client.aio.models, "generate_content", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = _make_response("ok")
        await provider.complete("시스템", "유저", temperature=0.3, max_tokens=512)

    call_kwargs = mock_gen.call_args.kwargs
    assert call_kwargs["model"] == DEFAULT_GEMINI_MODEL
    assert call_kwargs["contents"] == "유저"
    config: types.GenerateContentConfig = call_kwargs["config"]
    assert config.system_instruction == "시스템"
    assert config.temperature == 0.3
    assert config.max_output_tokens == 512


# ---------------------------------------------------------------------------
# 2. 재시도 로직
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_server_error_then_succeeds():
    """500 에러 1회 → 재시도 성공."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with (
        patch.object(
            provider._client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = [_server_error(500), _make_response("회복")]
        result = await provider.complete("sys", "usr")

    assert result == "회복"
    assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_retries_on_rate_limit_then_succeeds():
    """429 에러 1회 → 재시도 성공."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with (
        patch.object(
            provider._client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = [_client_error(429), _make_response("성공")]
        result = await provider.complete("sys", "usr")

    assert result == "성공"
    assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_retries_on_httpx_timeout_then_succeeds():
    """httpx 타임아웃 1회 → 재시도 성공."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with (
        patch.object(
            provider._client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = [
            httpx.TimeoutException("timeout"),
            _make_response("성공"),
        ]
        result = await provider.complete("sys", "usr")

    assert result == "성공"
    assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_raises_max_retries_exceeded_after_all_failures():
    """서버 에러 4회 연속 → LLMClientError(MAX_RETRIES_EXCEEDED)."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with (
        patch.object(
            provider._client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = _server_error(500)
        with pytest.raises(LLMClientError) as exc_info:
            await provider.complete("sys", "usr")

    assert exc_info.value.code == "MAX_RETRIES_EXCEEDED"
    assert mock_gen.call_count == 4  # 초기 1 + 재시도 3


# ---------------------------------------------------------------------------
# 3. 재시도 안 하는 케이스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_does_not_retry_on_auth_error():
    """401 인증 에러 → 즉시 실패, 재시도 없음."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with patch.object(
        provider._client.aio.models, "generate_content", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.side_effect = _client_error(401)
        with pytest.raises(LLMClientError) as exc_info:
            await provider.complete("sys", "usr")

    assert mock_gen.call_count == 1
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_does_not_retry_on_bad_request():
    """400 요청 에러 → 즉시 실패, 재시도 없음."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with patch.object(
        provider._client.aio.models, "generate_content", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.side_effect = _client_error(400)
        with pytest.raises(LLMClientError):
            await provider.complete("sys", "usr")

    assert mock_gen.call_count == 1


# ---------------------------------------------------------------------------
# 4. 구조화 로그
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logs_request_and_response(caplog):
    """요청/응답/소요시간/토큰수가 로그에 기록된다."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with patch.object(
        provider._client.aio.models, "generate_content", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = _make_response(
            "응답",
            prompt_tokens=15,
            candidate_tokens=30,
        )
        with caplog.at_level(
            logging.INFO, logger="storytale.interpreter.gemini_provider"
        ):
            await provider.complete("시스템", "유저")

    assert "prompt_tokens" in caplog.text or "input_tokens" in caplog.text
    assert "output_tokens" in caplog.text or "candidate_tokens" in caplog.text


@pytest.mark.asyncio
async def test_logs_retry_warning_on_server_error(caplog):
    """서버 에러 시 warning 로그가 남는다."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test")

    with (
        patch.object(
            provider._client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_gen,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_gen.side_effect = [_server_error(500), _make_response("ok")]
        with caplog.at_level(
            logging.WARNING, logger="storytale.interpreter.gemini_provider"
        ):
            await provider.complete("sys", "usr")

    assert "retry" in caplog.text.lower() or "gemini_retry" in caplog.text


# ---------------------------------------------------------------------------
# 5. 기본 모델명
# ---------------------------------------------------------------------------


def test_default_model():
    """기본 모델명이 gemini-3.1-pro 이다."""
    from storytale.interpreter.gemini_provider import (
        DEFAULT_GEMINI_MODEL,
        GeminiProvider,
    )

    provider = GeminiProvider(api_key="test")
    assert provider.model == DEFAULT_GEMINI_MODEL
    assert "gemini" in DEFAULT_GEMINI_MODEL.lower()


def test_custom_model():
    """커스텀 모델명 지정 가능."""
    from storytale.interpreter.gemini_provider import GeminiProvider

    provider = GeminiProvider(api_key="test", model="gemini-custom")
    assert provider.model == "gemini-custom"
