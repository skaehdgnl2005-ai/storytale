"""S21 — Replicate API 클라이언트 테스트.

ReplicateClient: 호출, 재시도, 폴링, 타임아웃.
httpx 기반 직접 호출, 기존 base_client.py 패턴 따름.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from storytale.illustration.replicate_client import (
    MAX_RETRIES,
    POLL_INTERVAL,
    POLL_TIMEOUT,
    ReplicateClient,
    ReplicateClientError,
)

# ---------------------------------------------------------------------------
# 헬퍼: httpx.Response 팩토리
# ---------------------------------------------------------------------------


def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    """테스트용 httpx.Response 생성."""
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "https://api.replicate.com/"),
    )


# ---------------------------------------------------------------------------
# 1. 생성 + 폴링 → 성공
# ---------------------------------------------------------------------------


class TestRunPrediction:
    """run() 메서드: 예측 생성 → 폴링 → 결과 반환."""

    @pytest.mark.asyncio
    async def test_run_succeeds_after_polling(self) -> None:
        """생성 후 processing → succeeded 폴링 시나리오."""
        create_resp = _json_response(
            {
                "id": "pred_abc123",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/pred_abc123"},
            },
            status_code=201,
        )

        poll_processing = _json_response(
            {
                "id": "pred_abc123",
                "status": "processing",
            }
        )

        poll_succeeded = _json_response(
            {
                "id": "pred_abc123",
                "status": "succeeded",
                "output": ["https://replicate.delivery/result.png"],
            }
        )

        client = ReplicateClient(api_key="test-key")

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp
            mock_get.side_effect = [poll_processing, poll_succeeded]

            result = await client.run(
                model="stability-ai/flux",
                input_params={"prompt": "a cat"},
            )

        assert result.prediction_id == "pred_abc123"
        assert result.output == ["https://replicate.delivery/result.png"]
        assert result.status == "succeeded"
        assert mock_post.call_count == 1
        assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_run_immediate_success(self) -> None:
        """생성 응답에서 바로 succeeded인 경우 (동기 모델)."""
        create_resp = _json_response(
            {
                "id": "pred_instant",
                "status": "succeeded",
                "output": ["https://replicate.delivery/instant.png"],
            },
            status_code=201,
        )

        client = ReplicateClient(api_key="test-key")

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp

            result = await client.run(
                model="some/model",
                input_params={"prompt": "test"},
            )

        assert result.status == "succeeded"
        assert result.output == ["https://replicate.delivery/instant.png"]
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 2. 실패 시나리오
# ---------------------------------------------------------------------------


class TestFailureScenarios:
    """예측 실패, 취소, 타임아웃 시나리오."""

    @pytest.mark.asyncio
    async def test_prediction_failed_raises_error(self) -> None:
        """Replicate 예측이 failed 상태로 끝나면 에러."""
        create_resp = _json_response(
            {
                "id": "pred_fail",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/pred_fail"},
            },
            status_code=201,
        )

        poll_failed = _json_response(
            {
                "id": "pred_fail",
                "status": "failed",
                "error": "NSFW content detected",
            }
        )

        client = ReplicateClient(api_key="test-key")

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp
            mock_get.return_value = poll_failed

            with pytest.raises(ReplicateClientError) as exc_info:
                await client.run(model="some/model", input_params={})

        assert exc_info.value.code == "PREDICTION_FAILED"
        assert "NSFW" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_prediction_canceled_raises_error(self) -> None:
        """예측이 canceled 상태면 에러."""
        create_resp = _json_response(
            {
                "id": "pred_cancel",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/pred_cancel"},
            },
            status_code=201,
        )

        poll_canceled = _json_response(
            {
                "id": "pred_cancel",
                "status": "canceled",
            }
        )

        client = ReplicateClient(api_key="test-key")

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp
            mock_get.return_value = poll_canceled

            with pytest.raises(ReplicateClientError) as exc_info:
                await client.run(model="some/model", input_params={})

        assert exc_info.value.code == "PREDICTION_CANCELED"

    @pytest.mark.asyncio
    async def test_polling_http_error_raises(self) -> None:
        """폴링 중 HTTP 에러(5xx) → raise_for_status로 에러 전파."""
        create_resp = _json_response(
            {
                "id": "pred_poll_err",
                "status": "starting",
                "urls": {
                    "get": "https://api.replicate.com/v1/predictions/pred_poll_err"
                },
            },
            status_code=201,
        )

        poll_error_resp = _json_response(
            {"detail": "internal server error"}, status_code=500
        )

        client = ReplicateClient(api_key="test-key", poll_timeout=5.0)

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp
            mock_get.return_value = poll_error_resp

            with pytest.raises(httpx.HTTPStatusError):
                await client.run(model="some/model", input_params={})

        # 에러가 즉시 발생하므로 무한 폴링하지 않음
        assert mock_get.call_count == 1

    @pytest.mark.asyncio
    async def test_polling_timeout(self) -> None:
        """폴링 타임아웃 시 에러."""
        create_resp = _json_response(
            {
                "id": "pred_slow",
                "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/pred_slow"},
            },
            status_code=201,
        )

        poll_processing = _json_response(
            {
                "id": "pred_slow",
                "status": "processing",
            }
        )

        client = ReplicateClient(
            api_key="test-key",
            poll_timeout=0.1,
            poll_interval=0.05,
        )

        with (
            patch.object(client, "_post", new_callable=AsyncMock) as mock_post,
            patch.object(client, "_get", new_callable=AsyncMock) as mock_get,
        ):
            mock_post.return_value = create_resp
            mock_get.return_value = poll_processing

            with pytest.raises(ReplicateClientError) as exc_info:
                await client.run(model="some/model", input_params={})

        assert exc_info.value.code == "POLL_TIMEOUT"
        assert exc_info.value.retryable is False


# ---------------------------------------------------------------------------
# 3. 재시도 로직
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """HTTP 에러 시 재시도."""

    @pytest.mark.asyncio
    async def test_create_retries_on_server_error(self) -> None:
        """생성 요청에서 5xx 에러 시 재시도 후 성공."""
        error_resp = _json_response({"detail": "server error"}, status_code=500)
        success_resp = _json_response(
            {
                "id": "pred_retry",
                "status": "succeeded",
                "output": ["https://replicate.delivery/ok.png"],
            },
            status_code=201,
        )

        client = ReplicateClient(api_key="test-key")

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.HTTPStatusError(
                    "Server Error",
                    request=httpx.Request("POST", "https://api.replicate.com/"),
                    response=error_resp,
                ),
                success_resp,
            ]

            result = await client.run(model="some/model", input_params={})

        assert result.status == "succeeded"
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_create_retries_on_rate_limit(self) -> None:
        """429 Rate Limit 시 재시도."""
        rate_limit_resp = _json_response({"detail": "rate limited"}, status_code=429)
        success_resp = _json_response(
            {
                "id": "pred_rl",
                "status": "succeeded",
                "output": ["ok.png"],
            },
            status_code=201,
        )

        client = ReplicateClient(api_key="test-key")

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                httpx.HTTPStatusError(
                    "Rate Limited",
                    request=httpx.Request("POST", "https://api.replicate.com/"),
                    response=rate_limit_resp,
                ),
                success_resp,
            ]

            result = await client.run(model="some/model", input_params={})

        assert result.status == "succeeded"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self) -> None:
        """MAX_RETRIES 초과 시 에러."""
        error_resp = _json_response({"detail": "server error"}, status_code=500)

        client = ReplicateClient(api_key="test-key")

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "https://api.replicate.com/"),
                response=error_resp,
            )

            with pytest.raises(ReplicateClientError) as exc_info:
                await client.run(model="some/model", input_params={})

        assert exc_info.value.code == "MAX_RETRIES_EXCEEDED"
        assert exc_info.value.retryable is False
        assert mock_post.call_count == MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_auth_error_no_retry(self) -> None:
        """401 인증 에러는 재시도하지 않음."""
        auth_error_resp = _json_response({"detail": "unauthorized"}, status_code=401)

        client = ReplicateClient(api_key="bad-key")

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Unauthorized",
                request=httpx.Request("POST", "https://api.replicate.com/"),
                response=auth_error_resp,
            )

            with pytest.raises(ReplicateClientError) as exc_info:
                await client.run(model="some/model", input_params={})

        assert exc_info.value.code == "AUTH_ERROR"
        assert mock_post.call_count == 1


# ---------------------------------------------------------------------------
# 4. 설정 검증
# ---------------------------------------------------------------------------


class TestClientConfiguration:
    """클라이언트 설정 및 초기화."""

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """REPLICATE_API_TOKEN 환경변수에서 키 로드."""
        monkeypatch.setenv("REPLICATE_API_TOKEN", "env-token-123")
        client = ReplicateClient()
        assert client._api_key == "env-token-123"

    def test_api_key_explicit(self) -> None:
        """명시적 키가 환경변수보다 우선."""
        client = ReplicateClient(api_key="explicit-key")
        assert client._api_key == "explicit-key"

    def test_default_constants(self) -> None:
        """기본 상수값 확인."""
        assert MAX_RETRIES == 3
        assert POLL_TIMEOUT == 300.0
        assert POLL_INTERVAL == 2.0

    def test_custom_timeouts(self) -> None:
        """커스텀 타임아웃/폴링 설정."""
        client = ReplicateClient(
            api_key="test",
            poll_timeout=600.0,
            poll_interval=5.0,
            request_timeout=30.0,
        )
        assert client._poll_timeout == 600.0
        assert client._poll_interval == 5.0
        assert client._request_timeout == 30.0


# ---------------------------------------------------------------------------
# 5. cancel 기능
# ---------------------------------------------------------------------------


class TestCancelPrediction:
    """예측 취소 기능."""

    @pytest.mark.asyncio
    async def test_cancel_prediction(self) -> None:
        """진행 중인 예측 취소."""
        cancel_resp = _json_response(
            {
                "id": "pred_to_cancel",
                "status": "canceled",
            }
        )

        client = ReplicateClient(api_key="test-key")

        with patch.object(client, "_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = cancel_resp

            await client.cancel("pred_to_cancel")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "pred_to_cancel" in call_args[0][0]
        assert "cancel" in call_args[0][0]
