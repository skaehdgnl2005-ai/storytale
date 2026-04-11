"""S11 — LLM 클라이언트 래퍼 테스트.

단위 테스트 (모킹) + @pytest.mark.integration (실제 API 1회 호출).
"""

import json
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from storytale.interpreter.llm_client import (
    LLMClient,
    LLMClientError,
)

# ---------------------------------------------------------------------------
# 헬퍼: mock response 생성
# ---------------------------------------------------------------------------


def _make_response(
    text: str, input_tokens: int = 10, output_tokens: int = 20
) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


# ---------------------------------------------------------------------------
# 1. complete() — 기본 성공 케이스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_returns_text_on_success():
    client = LLMClient(api_key="test")
    expected = "안녕하세요!"
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response(expected)
        result = await client.complete("system", "user message")

    assert result == expected


@pytest.mark.asyncio
async def test_complete_passes_correct_params():
    client = LLMClient(api_key="test", model="claude-test-model")
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response("ok")
        await client.complete("sys", "usr", temperature=0.5, max_tokens=512)

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "claude-test-model"
    assert call_kwargs["system"] == "sys"
    assert call_kwargs["messages"] == [{"role": "user", "content": "usr"}]
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["max_tokens"] == 512


# ---------------------------------------------------------------------------
# 2. 재시도 로직 (최대 3회)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    """첫 번째 타임아웃 → 두 번째 성공 → 결과 반환."""
    client = LLMClient(api_key="test")
    success_resp = _make_response("성공")
    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = [
            anthropic.APITimeoutError(request=MagicMock()),
            success_resp,
        ]
        result = await client.complete("sys", "usr")

    assert result == "성공"
    assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_retries_on_server_error_then_succeeds():
    """500 에러 → 성공."""
    client = LLMClient(api_key="test")
    server_err = anthropic.InternalServerError(
        message="server error",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )
    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = [server_err, _make_response("회복")]
        result = await client.complete("sys", "usr")

    assert result == "회복"


@pytest.mark.asyncio
async def test_raises_max_retries_exceeded_after_three_failures():
    """3번 모두 타임아웃 → MaxRetriesExceeded."""
    client = LLMClient(api_key="test")
    with (
        patch.object(
            client._client.messages, "create", new_callable=AsyncMock
        ) as mock_create,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_create.side_effect = anthropic.APITimeoutError(request=MagicMock())
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete("sys", "usr")

    assert exc_info.value.code == "MAX_RETRIES_EXCEEDED"
    assert mock_create.call_count == 4  # 최초 1 + 재시도 3


@pytest.mark.asyncio
async def test_does_not_retry_on_auth_error():
    """인증 오류는 재시도하지 않는다."""
    client = LLMClient(api_key="invalid")
    auth_err = anthropic.AuthenticationError(
        message="auth error",
        response=MagicMock(status_code=401, headers={}),
        body=None,
    )
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = auth_err
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete("sys", "usr")

    assert mock_create.call_count == 1
    assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# 3. complete_json() — JSON 파싱
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_json_parses_valid_json():
    client = LLMClient(api_key="test")
    payload = {"category": "value_teaching", "score": 0.9}
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response(json.dumps(payload))
        result = await client.complete_json("sys", "usr")

    assert result == payload


@pytest.mark.asyncio
async def test_complete_json_extracts_from_markdown_block():
    """```json ... ``` 마크다운 블록에서 JSON 추출."""
    client = LLMClient(api_key="test")
    payload = {"key": "value"}
    raw = f"```json\n{json.dumps(payload)}\n```"
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response(raw)
        result = await client.complete_json("sys", "usr")

    assert result == payload


@pytest.mark.asyncio
async def test_complete_json_raises_parse_error_on_invalid_json():
    client = LLMClient(api_key="test")
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response("이것은 JSON이 아닙니다.")
        with pytest.raises(LLMClientError) as exc_info:
            await client.complete_json("sys", "usr")

    assert exc_info.value.code == "LLM_PARSE_ERROR"
    assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# 4. 구조화 로그
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logs_request_and_response(caplog):
    """요청/응답/소요시간/토큰수가 로그에 기록된다."""
    client = LLMClient(api_key="test")
    with patch.object(
        client._client.messages, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = _make_response(
            "응답", input_tokens=15, output_tokens=30
        )
        with caplog.at_level(logging.INFO, logger="storytale.interpreter.llm_client"):
            await client.complete("시스템", "유저")

    log_text = caplog.text
    assert "input_tokens" in log_text
    assert "output_tokens" in log_text


# ---------------------------------------------------------------------------
# 5. 통합 테스트 (실제 API 호출 1회)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_complete():
    """실제 Claude API 호출. CLAUDE_API_KEY 환경변수 필요."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 환경변수 없음 — 통합 테스트 건너뜀")

    client = LLMClient(api_key=api_key)
    result = await client.complete(
        system="당신은 간결하게 답변하는 어시스턴트입니다.",
        user="'안녕'을 한국어로 말하세요. 한 단어로만.",
        max_tokens=10,
    )
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api_complete_json():
    """실제 Claude API JSON 호출. CLAUDE_API_KEY 환경변수 필요."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 환경변수 없음 — 통합 테스트 건너뜀")

    client = LLMClient(api_key=api_key)
    result = await client.complete_json(
        system="JSON으로만 응답하세요.",
        user='{"status": "ok"} 를 그대로 JSON으로 반환하세요.',
        max_tokens=50,
    )
    assert isinstance(result, dict)
    assert "status" in result
