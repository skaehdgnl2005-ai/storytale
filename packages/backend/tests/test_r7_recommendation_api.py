"""R7: 추천 API 엔드포인트 테스트.

TDD — 구현 전에 작성.
httpx AsyncClient로 API 호출 테스트.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from storytale.api.dependencies import get_db
from storytale.app import app
from storytale.db.base import Base
from storytale.db.models import Book, ChildProfile, SituationTag, User


@pytest_asyncio.fixture(autouse=True)
async def _setup_test_db():
    """테스트 DB 설정."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 시드 데이터
    async with session_factory() as session:
        book = Book(
            isbn="9788901001",
            title="피터의 의자",
            author="에즈라 잭 키츠",
            publisher="비룡소",
            synopsis="동생 때문에 자기 물건이 분홍색으로 칠해지는 피터",
            target_age_min=4,
            target_age_max=7,
            source="manual",
        )
        session.add(book)
        await session.commit()
        await session.refresh(book)

        tag = SituationTag(
            book_id=book.id,
            tag_category="problem_solving",
            situation_description="동생이 태어나 질투를 느끼는 상황",
            emotional_keywords=["질투", "불안", "외로움"],
            recommended_arc_id="gentle_resolution",
            confidence_score=0.90,
            source="ai_generated",
        )
        session.add(tag)
        await session.commit()

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def mock_llm_guide():
    """LLM 가이드 생성 모킹."""
    return {
        "guides": [
            {
                "book_id": "placeholder",
                "why_this_book": "이 책은 동생이 생긴 아이의 마음을 잘 담았어요.",
                "reading_questions": ["피터는 어떤 기분이었을까?"],
                "conversation_guide": ["우리 아이도 비슷한 기분 느낀 적 있어?"],
            }
        ]
    }


@pytest.mark.asyncio
async def test_post_recommendations(mock_llm_guide):
    """POST /api/v1/recommendations 정상 호출."""
    mock_intent = MagicMock()
    mock_intent.model_dump.return_value = {
        "intent_category": "problem_solving",
        "core_theme": "형제 갈등",
        "trigger_situation": "동생이 태어났는데 자꾸 밀쳐요",
        "child_current_behavior": "밀침",
        "parent_desired_outcome": "사이좋게",
        "emotional_keywords": ["질투", "불안"],
        "recommended_arc_id": "gentle_resolution",
    }

    with (
        patch(
            "storytale.api.recommendations.router.create_llm_client"
        ) as mock_factory,
        patch(
            "storytale.api.recommendations.router.IntentAnalyzer"
        ) as mock_analyzer_cls,
        patch(
            "storytale.api.recommendations.router._load_arc_templates",
            return_value=[],
        ),
    ):
        mock_client = AsyncMock()
        mock_client.complete_json.return_value = mock_llm_guide
        mock_factory.return_value = mock_client

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = mock_intent
        mock_analyzer_cls.return_value = mock_analyzer

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/recommendations",
                json={
                    "parent_text": "동생이 태어났는데 자꾸 밀쳐요",
                    "child_age": 5,
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert "intent_analysis" in data
    assert "recommendations" in data
    assert data["has_custom_story_option"] is True
    assert "custom_story_prompt" in data


@pytest.mark.asyncio
async def test_post_recommendations_validation_error():
    """필수 필드 누락 시 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/recommendations",
            json={"parent_text": "테스트"},
            # child_age 누락
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_recommendations_empty_text():
    """빈 텍스트 입력 시 422 (Pydantic min_length=1)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/recommendations",
            json={"parent_text": "", "child_age": 5},
        )

    assert resp.status_code == 422
