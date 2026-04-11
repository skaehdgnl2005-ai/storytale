"""Gemini 빈 응답 재시도 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from storytale.interpreter.gemini_provider import GeminiProvider
from storytale.interpreter.llm_client import LLMClientError


@pytest.fixture
def provider() -> GeminiProvider:
    with patch("storytale.interpreter.gemini_provider.genai.Client"):
        return GeminiProvider(api_key="test-key")


@pytest.mark.asyncio
async def test_empty_response_retries_once(provider: GeminiProvider) -> None:
    """빈 응답(text=None) 시 1회 재시도한다."""
    response_empty = MagicMock()
    response_empty.text = None
    response_empty.usage_metadata = None

    response_ok = MagicMock()
    response_ok.text = '{"result": "ok"}'
    response_ok.usage_metadata = None

    mock_generate = AsyncMock(side_effect=[response_empty, response_ok])
    provider._client.aio.models.generate_content = mock_generate

    result = await provider.complete("system", "user")
    assert result == '{"result": "ok"}'
    assert mock_generate.call_count == 2


@pytest.mark.asyncio
async def test_empty_response_twice_raises_error(provider: GeminiProvider) -> None:
    """빈 응답이 재시도 후에도 반복되면 LLMClientError를 발생시킨다."""
    response_empty = MagicMock()
    response_empty.text = None
    response_empty.usage_metadata = None

    mock_generate = AsyncMock(return_value=response_empty)
    provider._client.aio.models.generate_content = mock_generate

    with pytest.raises(LLMClientError, match="빈 응답"):
        await provider.complete("system", "user")
