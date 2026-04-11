"""Gemini LLM 프로바이더.

LLMClient fallback용 Google Gemini API 래퍼:
- 재시도 3회 (지수 백오프) — LLMClient와 동일 패턴
- 동일한 LLMClientError 에러 계약
- 구조화 로그 (요청/응답/소요시간/토큰수)
"""

import asyncio
import logging
import os
import time

import httpx
from google import genai
from google.genai import errors as gemini_errors
from google.genai import types

from storytale.interpreter.llm_client import LLMClientError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
TIMEOUT_SECONDS = 60.0
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"

# 재시도 대상 예외
# - ServerError: 5xx 서버 에러
# - ClientError(429): Rate Limit
# - httpx 네트워크/타임아웃 에러
_RETRYABLE_GEMINI_EXCEPTIONS = (
    gemini_errors.ServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


def _is_retryable(exc: Exception) -> bool:
    """재시도 가능한 에러인지 판단한다."""
    if isinstance(exc, gemini_errors.ClientError):
        return exc.code == 429  # Rate Limit만 재시도
    return isinstance(exc, _RETRYABLE_GEMINI_EXCEPTIONS)


class GeminiProvider:
    """Google Gemini API 호출 래퍼.

    LLMClient fallback용으로 동일한 complete() 인터페이스를 제공한다.

    Args:
        api_key: Gemini API 키. None이면 GEMINI_API_KEY 환경변수 참조.
        model: 사용할 Gemini 모델 ID.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_GEMINI_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client = genai.Client(
            api_key=resolved_key,
            http_options=types.HttpOptions(timeout=int(TIMEOUT_SECONDS * 1000)),
        )
        self.model = model

    async def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """텍스트 완성 요청.

        Args:
            system: 시스템 프롬프트.
            user: 유저 메시지.
            temperature: 생성 온도.
            max_tokens: 최대 출력 토큰.

        Returns:
            생성된 텍스트.

        Raises:
            LLMClientError: 타임아웃, 인증 오류, 최대 재시도 초과 등.
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                delay = 2.0 ** (attempt - 1)  # 1s, 2s, 4s
                await asyncio.sleep(delay)

            try:
                started_at = time.monotonic()
                response = await self._client.aio.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=config,
                )
                elapsed = time.monotonic() - started_at

                prompt_tokens = 0
                output_tokens = 0
                if response.usage_metadata:
                    prompt_tokens = response.usage_metadata.prompt_token_count or 0
                    output_tokens = response.usage_metadata.candidates_token_count or 0

                logger.info(
                    "gemini_complete model=%s attempt=%d elapsed=%.3fs "
                    "prompt_tokens=%d output_tokens=%d",
                    self.model,
                    attempt + 1,
                    elapsed,
                    prompt_tokens,
                    output_tokens,
                )
                text = response.text
                if text is None:
                    _msg = "Gemini가 빈 응답을 반환했습니다 (안전 필터 차단 가능성)."
                    if attempt < MAX_RETRIES:
                        logger.warning(
                            "gemini_empty_response attempt=%d/%d — 재시도",
                            attempt + 1,
                            MAX_RETRIES + 1,
                        )
                        last_exc = LLMClientError(
                            code="LLM_EMPTY_RESPONSE",
                            message=_msg,
                            retryable=True,
                        )
                        continue
                    raise LLMClientError(
                        code="LLM_EMPTY_RESPONSE",
                        message=_msg,
                        retryable=False,
                    )
                return text

            except Exception as exc:
                if not _is_retryable(exc):
                    # 4xx 클라이언트 에러 등 — 즉시 실패
                    raise LLMClientError(
                        code="MAX_RETRIES_EXCEEDED",
                        message=str(exc),
                        retryable=False,
                    ) from exc

                last_exc = exc
                logger.warning(
                    "gemini_retry attempt=%d/%d error=%s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    str(exc),
                )
                continue

        raise LLMClientError(
            code="MAX_RETRIES_EXCEEDED",
            message=f"Gemini 호출 {MAX_RETRIES + 1}회 모두 실패: {last_exc}",
            retryable=False,
        ) from last_exc
