"""R4: 상황 태그 자동 생성 파이프라인 테스트.

TDD — 구현 전에 작성. LLM 호출은 모킹.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from storytale.recommendation.tag_generator import TagGenerator


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    return client


@pytest.fixture
def tag_generator(mock_llm_client):
    return TagGenerator(llm_client=mock_llm_client)


@pytest.mark.asyncio
async def test_generate_tags_returns_valid_tags(tag_generator, mock_llm_client):
    """줄거리 입력 시 유효한 태그 리스트 반환."""
    mock_llm_client.complete_json.return_value = {
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "동생이 태어나 질투를 느끼는 상황",
                "emotional_keywords": ["질투", "불안", "외로움"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.85,
            },
            {
                "tag_category": "value_teaching",
                "situation_description": "가족의 소중함을 알려주고 싶을 때",
                "emotional_keywords": ["사랑", "감사"],
                "recommended_arc_id": "celebration_joy",
                "confidence_score": 0.70,
            },
        ]
    }

    tags = await tag_generator.generate_tags(
        title="피터의 의자",
        author="에즈라 잭 키츠",
        synopsis="피터는 새로 태어난 동생 때문에 자기 물건이 분홍색으로 칠해지는 것이 속상합니다.",
    )

    assert len(tags) == 2
    assert tags[0]["tag_category"] == "problem_solving"
    assert tags[0]["emotional_keywords"] == ["질투", "불안", "외로움"]
    assert tags[0]["recommended_arc_id"] == "gentle_resolution"
    assert tags[0]["confidence_score"] == 0.85
    assert tags[1]["tag_category"] == "value_teaching"


@pytest.mark.asyncio
async def test_generate_tags_empty_synopsis(tag_generator, mock_llm_client):
    """줄거리 없이 제목만으로도 태그 생성 시도."""
    mock_llm_client.complete_json.return_value = {
        "tags": [
            {
                "tag_category": "interest_story",
                "situation_description": "하늘을 나는 상상을 좋아하는 아이",
                "emotional_keywords": ["호기심", "상상력"],
                "recommended_arc_id": "joy_of_discovery",
                "confidence_score": 0.60,
            }
        ]
    }

    tags = await tag_generator.generate_tags(
        title="구름빵",
        author="백희나",
        synopsis=None,
    )

    assert len(tags) == 1
    assert tags[0]["confidence_score"] == 0.60


@pytest.mark.asyncio
async def test_generate_tags_validates_category(tag_generator, mock_llm_client):
    """유효하지 않은 tag_category는 필터링."""
    mock_llm_client.complete_json.return_value = {
        "tags": [
            {
                "tag_category": "invalid_category",
                "situation_description": "테스트",
                "emotional_keywords": ["test"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.90,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "유효한 태그",
                "emotional_keywords": ["불안"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.80,
            },
        ]
    }

    tags = await tag_generator.generate_tags(
        title="테스트 책",
        author="작가",
        synopsis="테스트 줄거리",
    )

    assert len(tags) == 1
    assert tags[0]["tag_category"] == "problem_solving"


@pytest.mark.asyncio
async def test_generate_tags_filters_low_confidence(
    tag_generator, mock_llm_client
):
    """confidence_score 0.5 미만 태그는 필터링."""
    mock_llm_client.complete_json.return_value = {
        "tags": [
            {
                "tag_category": "celebration",
                "situation_description": "낮은 신뢰도",
                "emotional_keywords": ["기쁨"],
                "recommended_arc_id": "celebration_joy",
                "confidence_score": 0.30,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "높은 신뢰도",
                "emotional_keywords": ["불안"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.85,
            },
        ]
    }

    tags = await tag_generator.generate_tags(
        title="테스트 책",
        author="작가",
        synopsis="테스트 줄거리",
    )

    assert len(tags) == 1
    assert tags[0]["confidence_score"] == 0.85


@pytest.mark.asyncio
async def test_generate_tags_calls_llm_with_book_info(
    tag_generator, mock_llm_client
):
    """LLM에 책 정보가 제대로 전달되는지 확인."""
    mock_llm_client.complete_json.return_value = {"tags": []}

    await tag_generator.generate_tags(
        title="피터의 의자",
        author="에즈라 잭 키츠",
        synopsis="동생이 태어나서 질투하는 이야기",
    )

    mock_llm_client.complete_json.assert_called_once()
    call_args = mock_llm_client.complete_json.call_args
    system_prompt = call_args[1].get("system") or call_args[0][0]
    user_message = call_args[1].get("user_message") or call_args[0][1]

    assert "피터의 의자" in user_message
    assert "에즈라 잭 키츠" in user_message
