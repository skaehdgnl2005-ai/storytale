"""LLMClient fallback 동작 단위 테스트.

TDD 1단계: fallback 구현 전 테스트 먼저 작성.
fallback_provider를 Mock으로 주입하여 LLMClient의 위임 로직만 검증한다.
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from storytale.interpreter.llm_client import LLMClient, LLMClientError

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_claude_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=10, output_tokens=20)
    return resp


def _make_mock_fallback(return_text: str = "fallback 응답") -> AsyncMock:
    """GeminiProvider를 흉내 내는 mock fallback."""
    fallback = AsyncMock()
    fallback.complete = AsyncMock(return_value=return_text)
    return fallback


def _max_retries_error() -> LLMClientError:
    return LLMClientError(
        code="MAX_RETRIES_EXCEEDED",
        message="Claude 서버 장애",
        retryable=False,
    )


# ---------------------------------------------------------------------------
# 1. fallback 없음 — 기존 동작 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_fallback_primary_succeeds():
    """fallback=None, Claude 성공 → 정상 반환."""
    client = LLMClient(api_key="test")
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_claude_response("Claude 응답")
        result = await client.complete("sys", "usr")

    assert result == "Claude 응답"


@pytest.mark.asyncio
async def test_no_fallback_primary_fails_raises():
    """fallback=None, Claude 실패 → LLMClientError 그대로 raise."""
    client = LLMClient(api_key="test")
    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = anthropic.InternalServerError(
            message="500",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete("sys", "usr")

    assert exc_info.value.code == "MAX_RETRIES_EXCEEDED"


# ---------------------------------------------------------------------------
# 2. fallback 있음 — 위임 로직
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_not_called_when_primary_succeeds():
    """Claude 성공 시 fallback.complete()는 호출되지 않는다."""
    fallback = _make_mock_fallback()
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_claude_response("Claude 성공")
        result = await client.complete("sys", "usr")

    assert result == "Claude 성공"
    fallback.complete.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_called_on_max_retries():
    """Claude MAX_RETRIES_EXCEEDED → fallback.complete() 호출 → fallback 결과 반환."""
    fallback = _make_mock_fallback("Gemini 응답")
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = anthropic.InternalServerError(
            message="500",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        result = await client.complete("sys", "usr", temperature=0.5, max_tokens=512)

    assert result == "Gemini 응답"
    # fallback은 동일한 파라미터로 호출되어야 한다
    fallback.complete.assert_called_once_with(
        "sys", "usr", temperature=0.5, max_tokens=512
    )


@pytest.mark.asyncio
async def test_fallback_not_called_on_auth_error():
    """Claude 인증 에러(401) → fallback 호출 안 함, 즉시 raise."""
    fallback = _make_mock_fallback()
    client = LLMClient(api_key="invalid", fallback_provider=fallback)

    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = anthropic.AuthenticationError(
            message="auth error",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        with pytest.raises(LLMClientError):
            await client.complete("sys", "usr")

    fallback.complete.assert_not_called()


@pytest.mark.asyncio
async def test_both_providers_fail_raises_error():
    """Claude 실패 → Gemini도 실패 → LLMClientError raise."""
    fallback = AsyncMock()
    fallback.complete = AsyncMock(
        side_effect=LLMClientError(
            code="MAX_RETRIES_EXCEEDED",
            message="Gemini도 장애",
            retryable=False,
        )
    )
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = anthropic.InternalServerError(
            message="500",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete("sys", "usr")

    assert exc_info.value.code == "MAX_RETRIES_EXCEEDED"


# ---------------------------------------------------------------------------
# 3. 로깅
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_event_logged(caplog):
    """fallback 발동 시 warning 로그가 기록된다."""
    fallback = _make_mock_fallback("Gemini 응답")
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
        caplog.at_level(logging.WARNING, logger="storytale.interpreter.llm_client"),
    ):
        mock_create.side_effect = anthropic.InternalServerError(
            message="500",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        await client.complete("sys", "usr")

    assert "llm_fallback" in caplog.text


# ---------------------------------------------------------------------------
# 4. complete_json() — fallback 통과
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_json_through_fallback():
    """Claude 타임아웃 → Gemini가 JSON 반환 → 정상 파싱."""
    payload = {"category": "value_teaching", "score": 0.9}
    fallback = _make_mock_fallback(json.dumps(payload))
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = anthropic.InternalServerError(
            message="500",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
        result = await client.complete_json("sys", "usr")

    assert result == payload


@pytest.mark.asyncio
async def test_parse_error_does_not_trigger_fallback():
    """Claude가 응답했지만 JSON 파싱 실패 → fallback 호출 안 함."""
    fallback = _make_mock_fallback()
    client = LLMClient(api_key="test", fallback_provider=fallback)

    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_claude_response("이것은 JSON이 아닙니다")
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete_json("sys", "usr")

    assert exc_info.value.code == "LLM_PARSE_ERROR"
    fallback.complete.assert_not_called()


# ---------------------------------------------------------------------------
# 5. create_llm_client() 팩토리
# ---------------------------------------------------------------------------


def test_create_llm_client_without_gemini_key():
    """GEMINI_API_KEY 없으면 fallback=None."""
    from storytale.interpreter.llm_client import create_llm_client

    client = create_llm_client(claude_api_key="test-claude")
    assert client._fallback is None


def test_create_llm_client_with_gemini_key():
    """GEMINI_API_KEY 있으면 GeminiProvider가 fallback으로 설정된다."""
    from storytale.interpreter.gemini_provider import GeminiProvider
    from storytale.interpreter.llm_client import create_llm_client

    client = create_llm_client(
        claude_api_key="test-claude",
        gemini_api_key="test-gemini",
    )
    assert client._fallback is not None
    assert isinstance(client._fallback, GeminiProvider)


def test_create_llm_client_picks_gemini_key_from_env(monkeypatch):
    """환경변수 GEMINI_API_KEY로도 fallback이 활성화된다."""
    from storytale.interpreter.gemini_provider import GeminiProvider
    from storytale.interpreter.llm_client import create_llm_client

    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    client = create_llm_client(claude_api_key="test-claude")
    assert isinstance(client._fallback, GeminiProvider)
