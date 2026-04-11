"""상황 태그 자동 생성 파이프라인.

동화책 줄거리/메타데이터 → LLM 분석 → SituationTag 구조 반환.
"""

import logging
from typing import Any

from storytale.interpreter.llm_client import LLMClient

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = frozenset(
    {"value_teaching", "interest_story", "problem_solving", "celebration"}
)

_VALID_ARC_IDS = frozenset(
    {
        "gentle_resolution",
        "courage_building",
        "relationship_repair",
        "new_experience",
        "joy_of_discovery",
        "celebration_joy",
    }
)

_MIN_CONFIDENCE = 0.5

_TEMPERATURE = 0.3
_MAX_TOKENS = 1024

_SYSTEM_PROMPT = """당신은 아동발달 전문가이자 독서 치료사입니다.
동화책의 정보를 분석하여, 이 책이 어떤 상황에 처한 아이에게 도움이 될 수 있는지
구조화된 태그를 생성합니다.

## 태그 카테고리 (정확히 4가지만 사용)
- value_teaching: 소중한 가치를 알려주고 싶을 때
- interest_story: 아이의 관심사와 연결되는 이야기
- problem_solving: 문제 상황을 지혜롭게 해결하고 싶을 때
- celebration: 특별한 날을 기념하고 싶을 때

## 감정 아크 ID (6가지)
- gentle_resolution: 부드러운 해결
- courage_building: 용기 키우기
- relationship_repair: 관계 회복
- new_experience: 새로운 경험
- joy_of_discovery: 발견의 즐거움
- celebration_joy: 함께하는 기쁨

## 규칙
1. 한 책에 1~3개의 태그를 생성합니다.
2. situation_description은 부모가 공감할 수 있는 구체적 상황 서술.
3. emotional_keywords는 아이가 느낄 감정 3~5개.
4. confidence_score: 줄거리 명확 → 0.8~1.0, 제목만 → 0.5~0.7.
5. recommended_arc_id: 가장 잘 맞는 감정 아크 선택.

반드시 아래 JSON 형식으로만 응답하세요."""

_OUTPUT_SCHEMA = """{
  "tags": [
    {
      "tag_category": "value_teaching|interest_story|...",
      "situation_description": "string",
      "emotional_keywords": ["string"],
      "recommended_arc_id": "string",
      "confidence_score": 0.0
    }
  ]
}"""


class TagGenerator:
    """동화책 메타데이터 → 상황 태그 생성."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def generate_tags(
        self,
        title: str,
        author: str,
        synopsis: str | None = None,
    ) -> list[dict[str, Any]]:
        """책 정보를 분석하여 상황 태그 리스트 반환."""
        synopsis_text = synopsis or "(줄거리 정보 없음)"
        user_message = (
            f"다음 동화책을 분석하여 상황 태그를 생성해주세요.\n\n"
            f"제목: {title}\n"
            f"저자: {author}\n"
            f"줄거리: {synopsis_text}"
        )

        result = await self._llm.complete_json(
            system=_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )

        raw_tags = result.get("tags", [])
        return self._validate_and_filter(raw_tags)

    def _validate_and_filter(
        self, raw_tags: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """유효하지 않은 태그 필터링."""
        valid = []
        for tag in raw_tags:
            if tag.get("tag_category") not in _VALID_CATEGORIES:
                logger.warning(
                    "invalid_tag_category",
                    extra={"category": tag.get("tag_category")},
                )
                continue

            score = tag.get("confidence_score", 0)
            if score < _MIN_CONFIDENCE:
                logger.info(
                    "low_confidence_tag_filtered",
                    extra={"score": score},
                )
                continue

            arc_id = tag.get("recommended_arc_id")
            if arc_id and arc_id not in _VALID_ARC_IDS:
                tag["recommended_arc_id"] = None

            valid.append(tag)
        return valid
