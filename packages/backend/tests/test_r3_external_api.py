"""R3: 외부 도서 API 클라이언트 테스트.

TDD — 구현 전에 작성. 모든 HTTP 호출은 모킹.
"""

from unittest.mock import AsyncMock, patch

import pytest

from storytale.recommendation.external_api.aladin_client import AladinClient
from storytale.recommendation.external_api.base_client import (
    BookMetadataResult,
    ExternalApiError,
)
from storytale.recommendation.external_api.nlcy_client import NlcyClient


# ============================================================
# BookMetadataResult 기본 검증
# ============================================================


def test_book_metadata_result_fields():
    result = BookMetadataResult(
        isbn="9788901260716",
        title="구름빵",
        author="백희나",
        publisher="한솔수북",
        target_age_min=3,
        target_age_max=6,
        cover_image_url="https://example.com/cover.jpg",
        synopsis="하늘에서 구름 반죽을 주워 빵을 구우면...",
    )
    assert result.isbn == "9788901260716"
    assert result.title == "구름빵"
    assert result.target_age_min == 3


# ============================================================
# AladinClient 테스트
# ============================================================


@pytest.mark.asyncio
async def test_aladin_search_books_success():
    """알라딘 API 정상 응답 시 BookMetadataResult 리스트 반환."""
    mock_response = {
        "item": [
            {
                "isbn13": "9788901260716",
                "title": "구름빵",
                "author": "백희나 (지은이)",
                "publisher": "한솔수북",
                "cover": "https://example.com/cover.jpg",
                "description": "하늘에서 구름 반죽을 주워...",
                "customerReviewRank": 9,
            },
            {
                "isbn13": "9788943311384",
                "title": "알사탕",
                "author": "백희나 (지은이)",
                "publisher": "책읽는곰",
                "cover": "https://example.com/cover2.jpg",
                "description": "알사탕을 먹으면 마음의 소리가...",
                "customerReviewRank": 10,
            },
        ]
    }

    client = AladinClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await client.search_books("백희나", limit=5)

    assert len(results) == 2
    assert results[0].isbn == "9788901260716"
    assert results[0].title == "구름빵"
    assert results[0].author == "백희나"
    assert results[1].isbn == "9788943311384"


@pytest.mark.asyncio
async def test_aladin_search_books_empty():
    """알라딘 API 결과가 없을 때 빈 리스트 반환."""
    mock_response = {"item": []}

    client = AladinClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await client.search_books("존재하지않는책", limit=5)

    assert results == []


@pytest.mark.asyncio
async def test_aladin_get_book_by_isbn():
    """ISBN으로 단건 조회."""
    mock_response = {
        "item": [
            {
                "isbn13": "9788901260716",
                "title": "구름빵",
                "author": "백희나 (지은이)",
                "publisher": "한솔수북",
                "cover": "https://example.com/cover.jpg",
                "description": "하늘에서 구름 반죽을 주워...",
                "customerReviewRank": 9,
            }
        ]
    }

    client = AladinClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_book_by_isbn("9788901260716")

    assert result is not None
    assert result.isbn == "9788901260716"


@pytest.mark.asyncio
async def test_aladin_get_book_by_isbn_not_found():
    """ISBN 조회 결과 없을 때 None 반환."""
    mock_response = {"item": []}

    client = AladinClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_book_by_isbn("0000000000000")

    assert result is None


# ============================================================
# NlcyClient 테스트
# ============================================================


@pytest.mark.asyncio
async def test_nlcy_search_books_success():
    """국립도서관 API 정상 응답 시 BookMetadataResult 리스트 반환."""
    mock_response = {
        "docs": [
            {
                "EA_ISBN": "9788901260716",
                "TITLE": "구름빵",
                "AUTHOR": "백희나 글·그림",
                "PUBLISHER": "한솔수북",
                "TITLE_URL": "https://example.com/cover.jpg",
                "BOOK_INTRODUCTION": "하늘에서 구름 반죽을 주워...",
            }
        ]
    }

    client = NlcyClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        results = await client.search_books("구름빵", limit=5)

    assert len(results) == 1
    assert results[0].isbn == "9788901260716"
    assert results[0].title == "구름빵"
    assert results[0].source == "nlcy"


@pytest.mark.asyncio
async def test_nlcy_get_book_by_isbn():
    """국립도서관 ISBN 조회."""
    mock_response = {
        "docs": [
            {
                "EA_ISBN": "9788901260716",
                "TITLE": "구름빵",
                "AUTHOR": "백희나 글·그림",
                "PUBLISHER": "한솔수북",
                "TITLE_URL": "",
                "BOOK_INTRODUCTION": "",
            }
        ]
    }

    client = NlcyClient(api_key="test-key")
    with patch.object(
        client, "_request", new_callable=AsyncMock, return_value=mock_response
    ):
        result = await client.get_book_by_isbn("9788901260716")

    assert result is not None
    assert result.title == "구름빵"


# ============================================================
# 에러 처리 테스트
# ============================================================


@pytest.mark.asyncio
async def test_aladin_request_error_raises():
    """HTTP 오류 시 ExternalApiError 발생."""
    client = AladinClient(api_key="test-key")
    with patch.object(
        client,
        "_request",
        new_callable=AsyncMock,
        side_effect=ExternalApiError("API 호출 실패", source="aladin"),
    ):
        with pytest.raises(ExternalApiError, match="API 호출 실패"):
            await client.search_books("test")
