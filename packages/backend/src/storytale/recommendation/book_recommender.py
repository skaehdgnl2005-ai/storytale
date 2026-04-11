"""동화책 추천 서비스.

IntentAnalysis → DB 매칭 → LLM 가이드 생성 → 추천 결과 반환.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.db.models import Book, SituationTag
from storytale.interpreter.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 매칭 가중치
_W_KEYWORD = 0.55
_W_ARC = 0.15
_W_AGE = 0.20
_W_CONFIDENCE = 0.10

# LLM 파라미터
_TEMPERATURE = 0.5
_MAX_TOKENS = 4096

_GUIDE_SYSTEM_PROMPT = """당신은 경험 많은 어린이집 선생님 같은 친구입니다.
부모가 아이의 상황을 말하면, 추천된 동화책들에 대해
따뜻하고 실용적인 독서 가이드를 만들어줍니다.

## 톤
- 따뜻하고 신뢰감 있게. "당신이 아이를 가장 잘 알아요"의 톤.
- 판단하지 않기. 부모의 걱정을 있는 그대로 인정.

## 절대 금지 표현
- "착한 아이", "나쁜 아이", "다른 아이"처럼 아이를 비교·판단하는 표현 금지.
- "혼내", "벌", "야단", "못된" 등 훈육·처벌 관련 표현 금지.
- 부정적 표현을 쓰는 대신, 아이의 감정을 있는 그대로 인정하는 표현을 사용하세요.

## 규칙
1. why_this_book: 왜 지금 이 상황에 맞는지 2-3문장. **반드시 아이의 구체적 상황 키워드를 포함**하여 부모가 공감할 수 있게.
2. reading_questions: 읽어줄 때 열린 질문 3-5개. 답이 정해진 질문 금지.
3. conversation_guide: 책과 아이 경험을 연결하는 대화 주제 3-4개.

반드시 아래 JSON 형식으로만 응답하세요.
{
  "guides": [
    {
      "book_id": "string",
      "why_this_book": "string",
      "reading_questions": ["string"],
      "conversation_guide": ["string"]
    }
  ]
}"""

_CUSTOM_STORY_PROMPT = (
    "이 상황에 딱 맞는 이야기를 만들어줄 수 있어요"
)


_SYNONYM_GROUPS: list[set[str]] = [
    # 분노/거부 계열
    {
        "분노", "화", "짜증", "격분", "노여움", "거부감",
        "반항심", "반항", "거부", "거부반응", "싫음",
        "거부행동", "저항감", "저항",
    },
    # 좌절/답답 계열
    {"좌절", "답답함", "답답", "실망", "좌절감", "막막함"},
    # 두려움 계열
    {
        "두려움", "공포", "무서움", "겁", "위축", "놀람",
        "수줍음",
    },
    # 불안 계열
    {
        "불안", "불안감", "걱정", "긴장", "초조",
        "망설임", "낯섦", "불편함", "혼란",
    },
    # 슬픔 계열
    {"슬픔", "서운함", "서러움", "우울", "눈물", "그리움"},
    # 외로움 계열
    {"외로움", "고독", "쓸쓸함", "소외감", "소외"},
    # 기쁨 계열
    {
        "기쁨", "즐거움", "행복", "신남", "통쾌함",
        "유쾌", "보람",
    },
    # 안심/위로 계열
    {
        "안심", "안정", "편안함", "위로", "포근함",
        "따뜻함", "안도", "수용",
    },
    # 용기/자신감 계열
    {"용기", "자신감", "당당함", "자존감", "독립심"},
    # 호기심 계열
    {"호기심", "궁금함", "탐구심", "흥분", "관심"},
    # 사랑 계열
    {"사랑", "애정", "다정함", "감사", "사랑받음"},
    # 질투 계열
    {"질투", "시기", "부러움", "샘"},
    # 설렘 계열
    {"설렘", "기대", "두근거림", "두근두근", "특별함"},
    # 습관/적응 계열
    {"습관", "적응", "익숙함", "깨달음"},
    # 자기표현 계열
    {
        "자기표현", "표현", "소통", "이해",
        "자기주장",
    },
    # 우정 계열
    {"우정", "친구", "동료", "나눔"},
    # 고민/갈등 계열
    {"고민", "갈등", "걱정거리", "딜레마"},
]

_KEYWORD_TO_GROUP: dict[str, int] = {}
for _idx, _group in enumerate(_SYNONYM_GROUPS):
    for _word in _group:
        _KEYWORD_TO_GROUP[_word] = _idx


def _synonym_similarity(a: list[str], b: list[str]) -> float:
    """동의어 그룹을 고려한 키워드 유사도.

    각 키워드를 동의어 그룹 ID로 정규화한 뒤 Jaccard 유사도를 계산한다.
    동의어 그룹에 없는 키워드는 원본 문자열을 그대로 사용한다.
    """
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0

    def _normalize(keywords: list[str]) -> set[str | int]:
        result: set[str | int] = set()
        for kw in keywords:
            group_id = _KEYWORD_TO_GROUP.get(kw)
            if group_id is not None:
                result.add(group_id)
            else:
                result.add(kw)
        return result

    norm_a = _normalize(a)
    norm_b = _normalize(b)
    intersection = norm_a & norm_b
    union = norm_a | norm_b
    return len(intersection) / len(union)


def _jaccard_similarity(a: list[str], b: list[str]) -> float:
    """두 키워드 리스트의 Jaccard 유사도 (레거시, 참고용)."""
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _age_fit_score(
    child_age: int, age_min: int, age_max: int
) -> float:
    """연령 적합도. 범위 내이면 1.0, 1세 차이 0.5, 2세+ 0.0."""
    if age_min <= child_age <= age_max:
        return 1.0
    distance = min(abs(child_age - age_min), abs(child_age - age_max))
    if distance == 1:
        return 0.5
    return 0.0


class BookRecommender:
    """IntentAnalysis → 도서 추천 + 독후 가이드."""

    def __init__(
        self,
        llm_client: LLMClient,
        db_session: AsyncSession,
    ) -> None:
        self._llm = llm_client
        self._db = db_session

    async def recommend(
        self,
        intent: dict[str, Any],
        child_age: int,
        limit: int = 3,
    ) -> dict[str, Any]:
        """추천 결과 반환."""
        matches = await self._find_matching_books(
            intent, child_age, limit
        )

        guides: list[dict[str, Any]] = []
        if matches:
            guides = await self._generate_guides(
                matches, intent, child_age
            )

        recommendations = self._merge_matches_and_guides(
            matches, guides
        )

        return {
            "intent_analysis": intent,
            "recommendations": recommendations,
            "has_custom_story_option": True,
            "custom_story_prompt": _CUSTOM_STORY_PROMPT,
        }

    async def _find_matching_books(
        self,
        intent: dict[str, Any],
        child_age: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """DB에서 매칭되는 책 검색 + 점수 계산."""
        category = intent.get("intent_category", "")
        arc_id = intent.get("recommended_arc_id", "")
        keywords = intent.get("emotional_keywords", [])

        stmt = (
            select(SituationTag, Book)
            .join(Book, SituationTag.book_id == Book.id)
            .where(SituationTag.tag_category == category)
        )
        result = await self._db.execute(stmt)
        rows = result.all()

        scored: list[dict[str, Any]] = []
        for tag, book in rows:
            age_score = _age_fit_score(
                child_age, book.target_age_min, book.target_age_max
            )
            if age_score == 0.0:
                continue

            keyword_score = _synonym_similarity(
                keywords,
                tag.emotional_keywords or [],
            )
            arc_score = 1.0 if tag.recommended_arc_id == arc_id else 0.0
            conf_score = tag.confidence_score or 0.0

            total = (
                _W_KEYWORD * keyword_score
                + _W_ARC * arc_score
                + _W_AGE * age_score
                + _W_CONFIDENCE * conf_score
            )

            scored.append(
                {
                    "book": {
                        "id": str(book.id),
                        "isbn": book.isbn,
                        "title": book.title,
                        "author": book.author,
                        "publisher": book.publisher,
                        "cover_image_url": book.cover_image_url,
                        "synopsis": book.synopsis,
                        "target_age_min": book.target_age_min,
                        "target_age_max": book.target_age_max,
                    },
                    "match_score": round(total, 3),
                    "matched_tags": [
                        {
                            "tag_category": tag.tag_category,
                            "situation_description": (
                                tag.situation_description
                            ),
                            "emotional_keywords": (
                                tag.emotional_keywords
                            ),
                            "recommended_arc_id": (
                                tag.recommended_arc_id
                            ),
                        }
                    ],
                }
            )

        scored.sort(key=lambda x: x["match_score"], reverse=True)

        # 같은 책 중복 제거 (가장 높은 점수만)
        seen_isbns: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in scored:
            isbn = item["book"]["isbn"]
            if isbn not in seen_isbns:
                seen_isbns.add(isbn)
                unique.append(item)

        return unique[:limit]

    async def _generate_guides(
        self,
        matches: list[dict[str, Any]],
        intent: dict[str, Any],
        child_age: int,
    ) -> list[dict[str, Any]]:
        """LLM으로 각 책별 독서 가이드 생성."""
        books_text = ""
        for i, m in enumerate(matches, 1):
            book = m["book"]
            synopsis = book.get("synopsis") or "(줄거리 없음)"
            books_text += (
                f"{i}. 《{book['title']}》 - {book['author']}\n"
                f"   줄거리: {synopsis}\n"
                f"   book_id: {book['id']}\n\n"
            )

        trigger = intent.get(
            "trigger_situation", "구체적 상황 없음"
        )
        core_theme = intent.get("core_theme", "")
        user_message = (
            f"부모 고민의 핵심: {core_theme}\n"
            f"아이 상황: {trigger}\n"
            f"아이 나이: {child_age}세\n\n"
            f"추천된 책들:\n{books_text}\n"
            f"각 책에 대해 독서 가이드를 만들어주세요. "
            f"why_this_book에는 아이의 상황을 구체적으로 언급해주세요."
        )

        try:
            result = await self._llm.complete_json(
                system=_GUIDE_SYSTEM_PROMPT,
                user=user_message,
                temperature=_TEMPERATURE,
                max_tokens=_MAX_TOKENS,
            )
            return result.get("guides", [])
        except Exception:
            logger.exception("guide_generation_failed")
            return []

    def _merge_matches_and_guides(
        self,
        matches: list[dict[str, Any]],
        guides: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """매칭 결과와 가이드를 합침."""
        guide_map: dict[str, dict[str, Any]] = {}
        for g in guides:
            bid = g.get("book_id", "")
            guide_map[bid] = g

        merged = []
        for m in matches:
            book_id = m["book"]["id"]
            guide = guide_map.get(book_id, {})
            merged.append(
                {
                    **m,
                    "why_this_book": guide.get(
                        "why_this_book", ""
                    ),
                    "reading_questions": guide.get(
                        "reading_questions", []
                    ),
                    "conversation_guide": guide.get(
                        "conversation_guide", []
                    ),
                }
            )
        return merged
