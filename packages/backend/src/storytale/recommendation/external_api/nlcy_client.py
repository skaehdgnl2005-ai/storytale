"""국립어린이청소년도서관 API 클라이언트.

https://nl.go.kr/NL/contents/N31101030800.do
아동 도서 메타데이터 조회.
"""

import os
import re

from .base_client import BaseBookClient, BookMetadataResult

_NLCY_API_URL = "https://nl.go.kr/NL/search/openApi/search.do"


def _clean_author(raw: str) -> str:
    """'백희나 글·그림' → '백희나'"""
    return re.sub(r"\s*(글|그림|옮김|지음|엮음)[·,\s]*(글|그림|옮김)?", "", raw).strip()


class NlcyClient(BaseBookClient):
    """국립어린이청소년도서관 API 클라이언트."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("NLCY_API_KEY", "")
        super().__init__(api_key=key, base_url=_NLCY_API_URL)

    @property
    def source_name(self) -> str:
        return "nlcy"

    def _parse_doc(self, doc: dict) -> BookMetadataResult:
        return BookMetadataResult(
            isbn=doc.get("EA_ISBN", ""),
            title=doc.get("TITLE", ""),
            author=_clean_author(doc.get("AUTHOR", "")),
            publisher=doc.get("PUBLISHER", ""),
            cover_image_url=doc.get("TITLE_URL") or None,
            synopsis=doc.get("BOOK_INTRODUCTION") or None,
            source="nlcy",
            raw_data=doc,
        )

    async def search_books(
        self, query: str, limit: int = 10
    ) -> list[BookMetadataResult]:
        params = {
            "key": self._api_key,
            "kwd": query,
            "detailSearch": "true",
            "category": "도서",
            "pageNum": 1,
            "pageSize": limit,
            "srchTarget": "total",
            "outputStyle": "json",
        }
        data = await self._request(params)
        docs = data.get("docs", [])
        return [self._parse_doc(doc) for doc in docs]

    async def get_book_by_isbn(
        self, isbn: str
    ) -> BookMetadataResult | None:
        params = {
            "key": self._api_key,
            "kwd": isbn,
            "detailSearch": "true",
            "isbnOp": "isbn",
            "isbn": isbn,
            "pageSize": 1,
            "outputStyle": "json",
        }
        data = await self._request(params)
        docs = data.get("docs", [])
        if not docs:
            return None
        return self._parse_doc(docs[0])
