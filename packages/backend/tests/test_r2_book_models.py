"""R2: Book, SituationTag, BookRecommendation 모델 테스트.

TDD — 모델 구현 전에 작성.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from storytale.db.base import Base
from storytale.db.models import (
    Book,
    BookRecommendation,
    ChildProfile,
    SituationTag,
    User,
)


def test_book_model_exists():
    assert hasattr(Book, "isbn")
    assert hasattr(Book, "title")
    assert hasattr(Book, "author")
    assert hasattr(Book, "publisher")
    assert hasattr(Book, "cover_image_url")
    assert hasattr(Book, "synopsis")
    assert hasattr(Book, "target_age_min")
    assert hasattr(Book, "target_age_max")
    assert hasattr(Book, "source")
    assert hasattr(Book, "metadata_json")
    assert hasattr(Book, "created_at")
    assert hasattr(Book, "updated_at")


def test_situation_tag_model_exists():
    assert hasattr(SituationTag, "book_id")
    assert hasattr(SituationTag, "tag_category")
    assert hasattr(SituationTag, "situation_description")
    assert hasattr(SituationTag, "emotional_keywords")
    assert hasattr(SituationTag, "recommended_arc_id")
    assert hasattr(SituationTag, "confidence_score")
    assert hasattr(SituationTag, "source")
    assert hasattr(SituationTag, "created_at")


def test_book_recommendation_model_exists():
    assert hasattr(BookRecommendation, "user_id")
    assert hasattr(BookRecommendation, "child_id")
    assert hasattr(BookRecommendation, "parent_text")
    assert hasattr(BookRecommendation, "intent_analysis")
    assert hasattr(BookRecommendation, "recommended_books")
    assert hasattr(BookRecommendation, "guides")
    assert hasattr(BookRecommendation, "created_at")


def test_schema_includes_new_tables():
    sqlite_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=sqlite_engine)

    tables = Base.metadata.tables.keys()
    assert "books" in tables
    assert "situation_tags" in tables
    assert "book_recommendations" in tables


def test_book_table_has_isbn_column():
    table = Book.__table__
    isbn_col = table.c.isbn
    assert isbn_col.unique is True
    assert isbn_col.nullable is False


def test_situation_tag_has_book_fk():
    table = SituationTag.__table__
    book_id_col = table.c.book_id
    fk_names = [fk.target_fullname for fk in book_id_col.foreign_keys]
    assert "books.id" in fk_names


def test_book_recommendation_has_user_and_child_fk():
    table = BookRecommendation.__table__
    user_fk = [fk.target_fullname for fk in table.c.user_id.foreign_keys]
    child_fk = [fk.target_fullname for fk in table.c.child_id.foreign_keys]
    assert "users.id" in user_fk
    assert "child_profiles.id" in child_fk


def test_book_relationship_to_tags():
    """Book 모델이 tags relationship을 가지는지 확인."""
    assert hasattr(Book, "tags")


@pytest.mark.asyncio
async def test_book_crud():
    """Book CRUD 기본 동작 확인."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        book = Book(
            isbn="9788901260716",
            title="구름빵",
            author="백희나",
            publisher="한솔수북",
            target_age_min=3,
            target_age_max=6,
            source="manual",
        )
        session.add(book)
        await session.commit()
        await session.refresh(book)

        assert book.id is not None
        assert book.isbn == "9788901260716"
        assert book.title == "구름빵"
        assert book.created_at is not None


@pytest.mark.asyncio
async def test_situation_tag_crud():
    """SituationTag CRUD 기본 동작 확인."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        book = Book(
            isbn="9788901260716",
            title="구름빵",
            author="백희나",
            publisher="한솔수북",
            target_age_min=3,
            target_age_max=6,
            source="manual",
        )
        session.add(book)
        await session.commit()
        await session.refresh(book)

        tag = SituationTag(
            book_id=book.id,
            tag_category="interest_story",
            situation_description="하늘을 날고 싶은 상상력이 풍부한 아이",
            emotional_keywords=["호기심", "상상력", "모험"],
            recommended_arc_id="joy_of_discovery",
            confidence_score=0.85,
            source="ai_generated",
        )
        session.add(tag)
        await session.commit()
        await session.refresh(tag)

        assert tag.id is not None
        assert tag.book_id == book.id
        assert tag.emotional_keywords == ["호기심", "상상력", "모험"]
        assert tag.confidence_score == 0.85


@pytest.mark.asyncio
async def test_book_recommendation_crud():
    """BookRecommendation CRUD 기본 동작 확인."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(email="test@example.com", provider="google")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        child = ChildProfile(
            user_id=user.id, name="서준", age=5, gender="male"
        )
        session.add(child)
        await session.commit()
        await session.refresh(child)

        rec = BookRecommendation(
            user_id=user.id,
            child_id=child.id,
            parent_text="동생이 태어났는데 자꾸 밀쳐요",
            intent_analysis={
                "intent_category": "problem_solving",
                "core_theme": "형제 갈등",
                "emotional_keywords": ["질투", "불안"],
            },
            recommended_books=[
                {"book_id": str(uuid.uuid4()), "rank": 1, "match_score": 0.92}
            ],
            guides=[
                {
                    "book_id": str(uuid.uuid4()),
                    "why_this_book": "동생과의 관계를 따뜻하게 다루는 이야기예요.",
                    "reading_questions": ["주인공은 동생이 생기고 어떤 기분이었을까?"],
                    "conversation_guide": ["우리 서준이도 동생이 생겼을 때 어떤 기분이었어?"],
                }
            ],
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)

        assert rec.id is not None
        assert rec.parent_text == "동생이 태어났는데 자꾸 밀쳐요"
        assert rec.intent_analysis["intent_category"] == "problem_solving"
