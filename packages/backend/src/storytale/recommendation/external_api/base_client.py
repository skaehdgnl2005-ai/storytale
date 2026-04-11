"""외부 도서 API 공통 베이스 클라이언트.

재시도 3회, 지수 백오프, 타임아웃, 구조화 로깅.
LLMClient와 동일 패턴.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
TIMEOUT_SECONDS = 15.0
INITIAL_BACKOFF = 1.0


class BookMetadataResult(BaseModel):
    """정규화된 도서 메타데이터. 모든 외부 API가 이 형식으로 반환."""

    isbn: str
    title: str
    author: str
    publisher: str
    cover_image_url: str | None = None
    synopsis: str | None = None
    target_age_min: int = 3
    target_age_max: int = 8
    source: str = "manual"
    raw_data: dict[str, Any] | None = None


class ExternalApiError(Exception):
    """외부 도서 API 호출 실패."""

    def __init__(
        self,
        message: str,
        *,
        source: str = "unknown",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.retryable = retryable


class BaseBookClient(ABC):
    """외부 도서 API 베이스 클라이언트."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self._api_key = api_key
        self._base_url = base_url

    async def _request(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """HTTP GET 요청 + 재시도 로직."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            start = time.monotonic()
            try:
                async with httpx.AsyncClient(
                    timeout=TIMEOUT_SECONDS
                ) as client:
                    resp = await client.get(
                        self._base_url, params=params
                    )
                    elapsed = time.monotonic() - start

                    logger.info(
                        "external_api_call",
                        extra={
                            "source": self.source_name,
                            "status": resp.status_code,
                            "elapsed_ms": round(elapsed * 1000),
                            "attempt": attempt,
                        },
                    )

                    resp.raise_for_status()
                    return resp.json()

            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    wait = INITIAL_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "external_api_retry",
                        extra={
                            "source": self.source_name,
                            "attempt": attempt,
                            "wait_s": wait,
                            "error": str(exc),
                        },
                    )
                    await asyncio.sleep(wait)

        raise ExternalApiError(
            f"{self.source_name} API 호출 실패: {last_error}",
            source=self.source_name,
            retryable=True,
        )

    @property
    @abstractmethod
    def source_name(self) -> str:
        """API 소스 이름 (로깅용)."""

    @abstractmethod
    async def search_books(
        self, query: str, limit: int = 10
    ) -> list[BookMetadataResult]:
        """도서 검색."""

    @abstractmethod
    async def get_book_by_isbn(
        self, isbn: str
    ) -> BookMetadataResult | None:
        """ISBN으로 단건 조회."""
