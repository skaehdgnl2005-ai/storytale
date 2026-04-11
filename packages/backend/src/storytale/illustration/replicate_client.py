"""Replicate API 클라이언트.

Flux.1, PuLID 등 이미지 생성 모델 호출 공통 레이어:
- 예측 생성 (POST /v1/predictions)
- 폴링 (GET /v1/predictions/{id})
- 재시도 3회 (지수 백오프, 5xx/429만)
- 폴링 타임아웃 (기본 300초)
- 구조화 로깅
"""

import asyncio
import logging
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
POLL_TIMEOUT = 300.0
POLL_INTERVAL = 2.0
REQUEST_TIMEOUT = 30.0
BASE_URL = "https://api.replicate.com/v1"

_TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PredictionResult(BaseModel):
    """Replicate 예측 결과."""

    prediction_id: str
    status: str
    output: list[str] | None = None
    error: str | None = None


class ReplicateClientError(Exception):
    """Replicate API 호출 실패."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ReplicateClient:
    """Replicate API 클라이언트.

    Args:
        api_key: API 토큰. None이면 REPLICATE_API_TOKEN 환경변수 참조.
        poll_timeout: 폴링 최대 대기 시간(초). 기본 300초.
        poll_interval: 폴링 간격(초). 기본 2초.
        request_timeout: 개별 HTTP 요청 타임아웃(초). 기본 30초.
    """

    def __init__(
        self,
        api_key: str | None = None,
        poll_timeout: float = POLL_TIMEOUT,
        poll_interval: float = POLL_INTERVAL,
        request_timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.getenv("REPLICATE_API_TOKEN", "")
        self._poll_timeout = poll_timeout
        self._poll_interval = poll_interval
        self._request_timeout = request_timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, url: str, json_data: dict[str, Any]) -> httpx.Response:
        """POST 요청."""
        async with httpx.AsyncClient(timeout=self._request_timeout) as http:
            return await http.post(url, json=json_data, headers=self._headers())

    async def _get(self, url: str) -> httpx.Response:
        """GET 요청."""
        async with httpx.AsyncClient(timeout=self._request_timeout) as http:
            return await http.get(url, headers=self._headers())

    async def run(
        self,
        model: str,
        input_params: dict[str, Any],
        *,
        version: str | None = None,
    ) -> PredictionResult:
        """예측 생성 + 폴링으로 결과 반환.

        Args:
            model: 모델 식별자 (예: "stability-ai/flux").
            input_params: 모델 입력 파라미터.
            version: 모델 버전 해시. None이면 model 필드로 최신 버전 사용.

        Returns:
            PredictionResult: 예측 결과.

        Raises:
            ReplicateClientError: 생성 실패, 폴링 타임아웃, 예측 실패 등.
        """
        create_data = self._build_create_payload(model, input_params, version)
        resp_data = await self._create_with_retry(create_data)

        prediction_id = resp_data["id"]
        status = resp_data.get("status", "starting")

        if status in _TERMINAL_STATUSES:
            return self._to_result(resp_data)

        poll_url = resp_data.get("urls", {}).get(
            "get", f"{BASE_URL}/predictions/{prediction_id}"
        )
        return await self._poll_until_complete(prediction_id, poll_url)

    async def cancel(self, prediction_id: str) -> None:
        """진행 중인 예측 취소."""
        url = f"{BASE_URL}/predictions/{prediction_id}/cancel"
        await self._post(url, {})
        logger.info("replicate_cancel prediction_id=%s", prediction_id)

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _build_create_payload(
        self,
        model: str,
        input_params: dict[str, Any],
        version: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"input": input_params}
        if version:
            payload["version"] = version
        else:
            payload["model"] = model
        return payload

    async def _create_with_retry(self, create_data: dict[str, Any]) -> dict[str, Any]:
        """예측 생성 요청 + 재시도."""
        url = f"{BASE_URL}/predictions"
        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                delay = 2.0 ** (attempt - 1)
                await asyncio.sleep(delay)

            try:
                started_at = time.monotonic()
                resp = await self._post(url, create_data)
                elapsed = time.monotonic() - started_at

                resp.raise_for_status()
                data = resp.json()

                logger.info(
                    "replicate_create prediction_id=%s status=%s "
                    "attempt=%d elapsed=%.3fs",
                    data.get("id"),
                    data.get("status"),
                    attempt + 1,
                    elapsed,
                )
                return data

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 401:
                    raise ReplicateClientError(
                        code="AUTH_ERROR",
                        message=f"Replicate 인증 실패: {exc}",
                        retryable=False,
                    ) from exc

                if status_code not in _RETRYABLE_STATUS_CODES:
                    raise ReplicateClientError(
                        code="API_ERROR",
                        message=f"Replicate API 에러 ({status_code}): {exc}",
                        retryable=False,
                    ) from exc

                last_exc = exc
                logger.warning(
                    "replicate_retry attempt=%d/%d status=%d",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    status_code,
                )

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "replicate_retry attempt=%d/%d error=timeout",
                    attempt + 1,
                    MAX_RETRIES + 1,
                )

        raise ReplicateClientError(
            code="MAX_RETRIES_EXCEEDED",
            message=f"Replicate API 호출 {MAX_RETRIES + 1}회 모두 실패: {last_exc}",
            retryable=False,
        )

    async def _poll_until_complete(
        self, prediction_id: str, poll_url: str
    ) -> PredictionResult:
        """폴링으로 예측 완료 대기."""
        deadline = time.monotonic() + self._poll_timeout

        while time.monotonic() < deadline:
            resp = await self._get(poll_url)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "unknown")

            logger.debug(
                "replicate_poll prediction_id=%s status=%s",
                prediction_id,
                status,
            )

            if status in _TERMINAL_STATUSES:
                return self._to_result(data)

            await asyncio.sleep(self._poll_interval)

        raise ReplicateClientError(
            code="POLL_TIMEOUT",
            message=(
                f"예측 {prediction_id} 폴링 타임아웃 ({self._poll_timeout}초 초과)"
            ),
            retryable=False,
        )

    @staticmethod
    def _to_result(data: dict[str, Any]) -> PredictionResult:
        """API 응답 → PredictionResult 변환."""
        status = data["status"]
        error_msg = data.get("error")

        if status == "failed":
            raise ReplicateClientError(
                code="PREDICTION_FAILED",
                message=f"예측 실패: {error_msg or 'unknown'}",
                retryable=False,
            )

        if status == "canceled":
            raise ReplicateClientError(
                code="PREDICTION_CANCELED",
                message=f"예측 취소됨: {data['id']}",
                retryable=False,
            )

        output = data.get("output")
        if isinstance(output, str):
            output = [output]

        return PredictionResult(
            prediction_id=data["id"],
            status=status,
            output=output,
            error=error_msg,
        )
