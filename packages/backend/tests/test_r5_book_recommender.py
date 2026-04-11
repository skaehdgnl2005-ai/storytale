"""R5: BookRecommender 서비스 테스트.

TDD — 구현 전에 작성.
IntentAnalysis → DB 매칭 → LLM 가이드 생성.
"""

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from storytale.db.base import Base
from storytale.db.models import Book, SituationTag
from storytale.recommendation.book_recommender import BookRecommender


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_session(db_session):
    """테스트용 책 + 태그 시드 데이터."""
    # 책 1: 동생 관련
    book1 = Book(
        isbn="9788901001",
        title="피터의 의자",
        author="에즈라 잭 키츠",
        publisher="비룡소",
        synopsis="동생 때문에 자기 물건이 분홍색으로 칠해지는 피터",
        target_age_min=4,
        target_age_max=7,
        source="manual",
    )
    # 책 2: 동생 관련 (다른 아크)
    book2 = Book(
        isbn="9788901002",
        title="나는 형이니까",
        author="후쿠다 이와오",
        publisher="웅진주니어",
        synopsis="형이 되는 것의 의미를 발견하는 이야기",
        target_age_min=3,
        target_age_max=6,
        source="manual",
    )
    # 책 3: 공룡 관련
    book3 = Book(
        isbn="9788901003",
        title="공룡이 쿵쿵쿵",
        author="다카이 요시카즈",
        publisher="보림",
        synopsis="다양한 공룡이 등장하는 즐거운 이야기",
        target_age_min=3,
        target_age_max=5,
        source="manual",
    )
    # 책 4: 연령 범위가 7-8
    book4 = Book(
        isbn="9788901004",
        title="나의 특별한 형",
        author="김영진",
        publisher="키즈엠",
        synopsis="장애가 있는 형을 이해하는 이야기",
        target_age_min=7,
        target_age_max=9,
        source="manual",
    )

    db_session.add_all([book1, book2, book3, book4])
    await db_session.commit()
    for b in [book1, book2, book3, book4]:
        await db_session.refresh(b)

    # 태그들
    tags = [
        SituationTag(
            book_id=book1.id,
            tag_category="problem_solving",
            situation_description="동생이 태어나 질투를 느끼는 상황",
            emotional_keywords=["질투", "불안", "외로움"],
            recommended_arc_id="gentle_resolution",
            confidence_score=0.90,
            source="ai_generated",
        ),
        SituationTag(
            book_id=book2.id,
            tag_category="problem_solving",
            situation_description="동생이 생기면서 변하는 가족 관계",
            emotional_keywords=["질투", "책임감", "사랑"],
            recommended_arc_id="gentle_resolution",
            confidence_score=0.85,
            source="ai_generated",
        ),
        SituationTag(
            book_id=book3.id,
            tag_category="interest_story",
            situation_description="공룡을 좋아하는 아이",
            emotional_keywords=["호기심", "흥분", "모험"],
            recommended_arc_id="joy_of_discovery",
            confidence_score=0.80,
            source="ai_generated",
        ),
        SituationTag(
            book_id=book4.id,
            tag_category="problem_solving",
            situation_description="형제의 장애를 이해하는 상황",
            emotional_keywords=["혼란", "이해", "사랑"],
            recommended_arc_id="relationship_repair",
            confidence_score=0.85,
            source="ai_generated",
        ),
    ]
    db_session.add_all(tags)
    await db_session.commit()

    return db_session


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete_json.return_value = {
        "guides": [
            {
                "book_id": "placeholder",
                "why_this_book": "이 책은 동생이 생긴 아이의 마음을 잘 담았어요.",
                "reading_questions": [
                    "피터는 어떤 기분이었을까?",
                    "의자를 왜 가져가고 싶었을까?",
                ],
                "conversation_guide": [
                    "우리 아이도 비슷한 기분 느낀 적 있어?",
                ],
            }
        ]
    }
    return llm


@pytest.mark.asyncio
async def test_recommend_exact_match(seeded_session, mock_llm):
    """동생 질투 상황 → 관련 책 2-3권 추천."""
    recommender = BookRecommender(
        llm_client=mock_llm, db_session=seeded_session
    )

    intent = {
        "intent_category": "problem_solving",
        "core_theme": "형제 갈등",
        "trigger_situation": "동생이 태어났는데 자꾸 밀쳐요",
        "child_current_behavior": "동생을 밀침",
        "parent_desired_outcome": "동생과 잘 지내기",
        "emotional_keywords": ["질투", "불안", "분노"],
        "recommended_arc_id": "gentle_resolution",
    }

    result = await recommender.recommend(intent=intent, child_age=5, limit=3)

    assert len(result["recommendations"]) >= 1
    assert len(result["recommendations"]) <= 3
    # 피터의 의자나 나는 형이니까가 포함되어야 함
    titles = [r["book"]["title"] for r in result["recommendations"]]
    assert any(
        t in titles for t in ["피터의 의자", "나는 형이니까"]
    )
    # 공룡 책은 나오면 안 됨
    assert "공룡이 쿵쿵쿵" not in titles


@pytest.mark.asyncio
async def test_recommend_age_filtering(seeded_session, mock_llm):
    """4세 아이 → 7세+ 전용 책은 제외."""
    recommender = BookRecommender(
        llm_client=mock_llm, db_session=seeded_session
    )

    intent = {
        "intent_category": "problem_solving",
        "core_theme": "형제 이해",
        "trigger_situation": "형제 간 갈등",
        "child_current_behavior": "자주 싸움",
        "parent_desired_outcome": "서로 이해",
        "emotional_keywords": ["혼란", "이해"],
        "recommended_arc_id": "relationship_repair",
    }

    result = await recommender.recommend(intent=intent, child_age=4, limit=3)

    titles = [r["book"]["title"] for r in result["recommendations"]]
    # 7-9세 전용 책은 4세에게 추천하지 않음
    assert "나의 특별한 형" not in titles


@pytest.mark.asyncio
async def test_recommend_includes_intent_analysis(seeded_session, mock_llm):
    """응답에 intent_analysis가 포함되어야 함 (유료 전환용)."""
    recommender = BookRecommender(
        llm_client=mock_llm, db_session=seeded_session
    )

    intent = {
        "intent_category": "interest_story",
        "core_theme": "공룡",
        "trigger_situation": "공룡을 너무 좋아함",
        "child_current_behavior": "공룡 이름 다 외움",
        "parent_desired_outcome": "관심사 기반 독서",
        "emotional_keywords": ["호기심", "흥분"],
        "recommended_arc_id": "joy_of_discovery",
    }

    result = await recommender.recommend(intent=intent, child_age=4, limit=3)

    assert result["intent_analysis"] == intent
    assert result["has_custom_story_option"] is True
    assert "만들어" in result["custom_story_prompt"]


@pytest.mark.asyncio
async def test_recommend_no_match_fallback(seeded_session, mock_llm):
    """매칭되는 책이 없어도 빈 리스트 + 전환 유도."""
    recommender = BookRecommender(
        llm_client=mock_llm, db_session=seeded_session
    )

    intent = {
        "intent_category": "celebration",
        "core_theme": "졸업",
        "trigger_situation": "유치원 졸업",
        "child_current_behavior": "설렘",
        "parent_desired_outcome": "졸업 기념",
        "emotional_keywords": ["기대", "설렘", "자랑스러움"],
        "recommended_arc_id": "celebration_joy",
    }

    result = await recommender.recommend(intent=intent, child_age=6, limit=3)

    assert result["has_custom_story_option"] is True
    # 매칭 없으면 빈 리스트여도 에러 아님
    assert isinstance(result["recommendations"], list)


@pytest.mark.asyncio
async def test_recommend_generates_guides(seeded_session, mock_llm):
    """추천 결과에 가이드 정보가 포함되어야 함."""
    recommender = BookRecommender(
        llm_client=mock_llm, db_session=seeded_session
    )

    intent = {
        "intent_category": "problem_solving",
        "core_theme": "형제 갈등",
        "trigger_situation": "동생 질투",
        "child_current_behavior": "밀침",
        "parent_desired_outcome": "사이좋게",
        "emotional_keywords": ["질투", "불안"],
        "recommended_arc_id": "gentle_resolution",
    }

    result = await recommender.recommend(intent=intent, child_age=5, limit=3)

    if result["recommendations"]:
        rec = result["recommendations"][0]
        assert "why_this_book" in rec
        assert "reading_questions" in rec
        assert "conversation_guide" in rec
