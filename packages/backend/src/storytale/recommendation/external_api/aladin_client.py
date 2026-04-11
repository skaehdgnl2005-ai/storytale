"""알라딘 Open API 클라이언트.

https://docs.aladin.co.kr/
아동 도서 검색 + ISBN 조회.
"""

import os
import re

from .base_client import BaseBookClient, BookMetadataResult

_ALADIN_API_URL = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
_ALADIN_LOOKUP_URL = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"


def _clean_author(raw: str) -> str:
    """'백희나 (지은이)' → '백희나'"""
    return re.sub(r"\s*\(.*?\)", "", raw).strip()


class AladinClient(BaseBookClient):
    """알라딘 Open API 클라이언트."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("ALADIN_TTB_KEY", "")
        super().__init__(api_key=key, base_url=_ALADIN_API_URL)

    @property
    def source_name(self) -> str:
        return "aladin"

    def _parse_item(self, item: dict) -> BookMetadataResult:
        return BookMetadataResult(
            isbn=item.get("isbn13", item.get("isbn", "")),
            title=item.get("title", ""),
            author=_clean_author(item.get("author", "")),
            publisher=item.get("publisher", ""),
            cover_image_url=item.get("cover") or None,
            synopsis=item.get("description") or None,
            source="aladin",
            raw_data=item,
        )

    async def search_books(
        self, query: str, limit: int = 10
    ) -> list[BookMetadataResult]:
        params = {
            "ttbkey": self._api_key,
            "Query": query,
            "QueryType": "Keyword",
            "MaxResults": limit,
            "SearchTarget": "Book",
            "CategoryId": 13789,  # 유아/어린이
            "output": "js",
            "Version": "20131101",
        }
        data = await self._request(params)
        items = data.get("item", [])
        return [self._parse_item(item) for item in items]

    async def get_book_by_isbn(
        self, isbn: str
    ) -> BookMetadataResult | None:
        self._base_url = _ALADIN_LOOKUP_URL
        try:
            params = {
                "ttbkey": self._api_key,
                "itemIdType": "ISBN13",
                "ItemId": isbn,
                "output": "js",
                "Version": "20131101",
            }
            data = await self._request(params)
            items = data.get("item", [])
            if not items:
                return None
            return self._parse_item(items[0])
        finally:
            self._base_url = _ALADIN_API_URL
