"""LLM 클라이언트 래퍼.

Claude API 호출 공통 레이어:
- 재시도 3회 (지수 백오프)
- 타임아웃 60초 (scene_plan 등 복잡한 JSON 생성 대응)
- JSON 파싱 (마크다운 블록 포함)
- 구조화 로그 (요청/응답/소요시간/토큰수)
- fallback_provider: Claude 서버 장애 시 Gemini 등 대체 프로바이더로 자동 전환
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any

import anthropic

if TYPE_CHECKING:
    from storytale.interpreter.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
TIMEOUT_SECONDS = 60.0  # scene_plan 등 복잡한 JSON 생성은 30초로 부족
DEFAULT_MODEL = "claude-sonnet-4-6"

# 재시도 대상 예외 (일시적 오류만)
_RETRYABLE_EXCEPTIONS = (
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
)


class LLMClientError(Exception):
    """LLM 호출 실패. contracts/story-engine.ts StoryEngineError 대응."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        server_failure: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        # server_failure=True: 서버 장애로 재시도가 모두 소진된 경우 (fallback 대상)
        # server_failure=False: 인증 오류·클라이언트 오류 등 (fallback 불필요)
        self.server_failure = server_failure


class LLMClient:
    """Claude API 호출 래퍼.

    Args:
        api_key: API 키. None이면 CLAUDE_API_KEY → ANTHROPIC_API_KEY 순 환경변수 참조.
        model: 사용할 Claude 모델 ID.
        fallback_provider: Claude 서버 장애 시 위임할 대체 프로바이더
            (예: GeminiProvider).
            None이면 fallback 없이 기존 동작 유지.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        fallback_provider: "GeminiProvider | None" = None,
    ) -> None:
        # .env.example은 CLAUDE_API_KEY 사용 → SDK 기본값(ANTHROPIC_API_KEY) 전에 확인
        resolved_key = api_key or os.getenv("CLAUDE_API_KEY")
        self._client = anthropic.AsyncAnthropic(
            api_key=resolved_key,
            timeout=TIMEOUT_SECONDS,
        )
        self.model = model
        self._fallback = fallback_provider

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
        try:
            return await self._complete_primary(
                system, user, temperature=temperature, max_tokens=max_tokens
            )
        except LLMClientError as exc:
            if exc.server_failure and self._fallback is not None:
                logger.warning(
                    "llm_fallback primary=%s reason=%s — Gemini fallback 시도",
                    self.model,
                    exc,
                )
                return await self._fallback.complete(
                    system, user, temperature=temperature, max_tokens=max_tokens
                )
            raise

    async def _complete_primary(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Claude API 재시도 루프."""
        last_exc: Exception | None = None

        _overloaded = False
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                # 529 과부하 시 더 긴 백오프 (10, 20, 40, 80, 160s)
                if _overloaded:
                    delay = 10.0 * (2.0 ** (attempt - 1))
                else:
                    delay = 2.0 ** (attempt - 1)  # 1s, 2s, 4s
                await asyncio.sleep(delay)

            try:
                started_at = time.monotonic()
                response = await self._client.messages.create(
                    model=self.model,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed = time.monotonic() - started_at
                text = response.content[0].text

                logger.info(
                    "llm_complete model=%s attempt=%d elapsed=%.3fs "
                    "input_tokens=%d output_tokens=%d",
                    self.model,
                    attempt + 1,
                    elapsed,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                )
                return text

            except _RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                logger.warning(
                    "llm_retry attempt=%d/%d error=%s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    str(exc),
                )
                continue

            except anthropic.APIStatusError as exc:
                if exc.status_code == 529:
                    # 529 Overloaded — 일시적 과부하, 재시도 대상
                    _overloaded = True
                    last_exc = exc
                    logger.warning(
                        "llm_retry attempt=%d/%d error=overloaded_529",
                        attempt + 1,
                        MAX_RETRIES + 1,
                    )
                    continue
                # 4xx 클라이언트 오류 — 재시도해도 의미 없음, fallback도 의미 없음
                code = (
                    "LLM_TIMEOUT" if exc.status_code == 408 else "MAX_RETRIES_EXCEEDED"
                )
                raise LLMClientError(
                    code=code, message=str(exc), retryable=False
                ) from exc

        raise LLMClientError(
            code="MAX_RETRIES_EXCEEDED",
            message=f"LLM 호출 {MAX_RETRIES + 1}회 모두 실패: {last_exc}",
            retryable=False,
            server_failure=True,  # 서버 장애로 재시도 소진 → fallback 대상
        ) from last_exc

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """JSON 응답 완성 요청.

        마크다운 코드 블록(```json ... ```)에서도 JSON을 추출한다.

        Returns:
            파싱된 JSON dict.

        Raises:
            LLMClientError(code="LLM_PARSE_ERROR"): JSON 파싱 실패 시.
        """
        raw = await self.complete(
            system, user, temperature=temperature, max_tokens=max_tokens
        )
        return _parse_json(raw)


# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
# 마크다운 블록 없이 날 JSON 객체만 반환하는 경우 대응
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    """텍스트에서 JSON을 추출해 파싱한다.

    시도 순서:
    1. ```json ... ``` 마크다운 블록 추출
    2. { ... } 객체 직접 추출 (닫는 ``` 누락 등 대응)
    3. 전체 텍스트 그대로 파싱
    """
    candidates: list[str] = []

    # 1. 마크다운 블록
    match = _JSON_BLOCK_RE.search(text)
    if match:
        extracted = match.group(1).strip()
        if extracted:
            candidates.append(extracted)

    # 2. { ... } 객체 직접 추출 (LLM이 닫는 ``` 를 빠뜨린 경우)
    obj_match = _JSON_OBJECT_RE.search(text)
    if obj_match:
        candidates.append(obj_match.group(0))

    # 3. 전체 텍스트
    candidates.append(text.strip())

    last_exc: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if not isinstance(result, dict):
                raise LLMClientError(
                    code="LLM_PARSE_ERROR",
                    message=f"JSON 최상위가 dict가 아님: {type(result).__name__}",
                    retryable=False,
                )
            return result
        except json.JSONDecodeError as exc:
            last_exc = exc
            continue

    raise LLMClientError(
        code="LLM_PARSE_ERROR",
        message=f"JSON 파싱 실패: {last_exc}. 원문: {text[:200]}",
        retryable=False,
    ) from last_exc


# ---------------------------------------------------------------------------
# 팩토리
# ---------------------------------------------------------------------------


def create_llm_client(
    claude_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> LLMClient:
    """환경 설정에 따라 LLMClient를 생성한다.

    GEMINI_API_KEY (또는 gemini_api_key 인자)가 있으면 GeminiProvider를
    fallback으로 연결한다. 없으면 Claude 단독 모드.

    Args:
        claude_api_key: Claude API 키. None이면 CLAUDE_API_KEY 환경변수 참조.
        gemini_api_key: Gemini API 키. None이면 GEMINI_API_KEY 환경변수 참조.

    Returns:
        fallback이 설정된 LLMClient 인스턴스.
    """
    fallback = None
    resolved_gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if resolved_gemini_key:
        from storytale.interpreter.gemini_provider import (
            GeminiProvider,
        )

        fallback = GeminiProvider(api_key=resolved_gemini_key)
    return LLMClient(api_key=claude_api_key, fallback_provider=fallback)
