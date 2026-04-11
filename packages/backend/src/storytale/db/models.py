import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


def utcnow():
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    consent_given_at = Column(DateTime(timezone=True), nullable=True)
    # S27b: 이메일+비번 로그인용 bcrypt 해시. 소셜 유저는 null 유지.
    password_hash = Column(String, nullable=True)

    profiles = relationship("ChildProfile", back_populates="user")
    stories = relationship("Story", back_populates="user")
    book_recommendations = relationship("BookRecommendation", back_populates="user")


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # 암호화 예정
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    comfort_object = Column(String, nullable=True)  # 암호화 예정
    friend_name = Column(String, nullable=True)  # 암호화 예정
    favorite_animal = Column(String, nullable=True)
    character_sheet_url = Column(String, nullable=True)
    photo_hash = Column(String, nullable=True)

    user = relationship("User", back_populates="profiles")
    stories = relationship("Story", back_populates="child")
    book_recommendations = relationship("BookRecommendation", back_populates="child")


class EmotionalArcTemplate(Base):
    __tablename__ = "emotional_arc_templates"

    id = Column(String, primary_key=True)
    description = Column(String, nullable=False)
    target_ages = Column(JSON, nullable=False)  # str[]
    stages = Column(JSON, nullable=False)  # ArcStage 배열
    rules = Column(JSON, nullable=False)  # str[]


class AgeStyleGuide(Base):
    __tablename__ = "age_style_guides"

    age_group = Column(String, primary_key=True)
    sentence_rules = Column(JSON, nullable=False)
    emotional_expression = Column(JSON, nullable=False)
    page_guidelines = Column(JSON, nullable=False)


class SafetyRails(Base):
    __tablename__ = "safety_rails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prohibitions = Column(JSON, nullable=False)  # str[]
    required_elements = Column(JSON, nullable=False)  # str[]
    content_filter = Column(JSON, nullable=False)  # {exact_block, ...}
    illustration_safety = Column(JSON, nullable=False)  # {description, neg_prompts}


class Story(Base):
    __tablename__ = "stories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_id = Column(
        UUID(as_uuid=True), ForeignKey("child_profiles.id"), nullable=False
    )
    intent_analysis = Column(JSON, nullable=True)
    scene_plan = Column(JSON, nullable=True)
    status = Column(String, nullable=False)
    style = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="stories")
    child = relationship("ChildProfile", back_populates="stories")
    pages = relationship(
        "StoryPage", back_populates="story", cascade="all, delete-orphan"
    )


class StoryPage(Base):
    __tablename__ = "story_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    scene_id = Column(String, nullable=False)
    text = Column(String, nullable=False)
    illustration_prompt = Column(String, nullable=False)
    illustration_url = Column(String, nullable=True)
    consistency_score = Column(Float, nullable=True)

    story = relationship("Story", back_populates="pages")


# ============================================================
# 동화책 추천 (Phase 4.5)
# ============================================================


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    isbn = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    publisher = Column(String, nullable=False)
    cover_image_url = Column(String, nullable=True)
    synopsis = Column(Text, nullable=True)
    target_age_min = Column(Integer, nullable=False)
    target_age_max = Column(Integer, nullable=False)
    source = Column(String, nullable=False)  # "nlcy" | "aladin" | "kyobo" | "manual"
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    tags = relationship(
        "SituationTag", back_populates="book", cascade="all, delete-orphan"
    )


class SituationTag(Base):
    __tablename__ = "situation_tags"
    __table_args__ = (
        Index("ix_situation_tags_category", "tag_category"),
        Index("ix_situation_tags_arc", "recommended_arc_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    tag_category = Column(String, nullable=False)  # IntentCategory 값
    situation_description = Column(Text, nullable=False)
    emotional_keywords = Column(JSON, nullable=False)  # str[]
    recommended_arc_id = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=False)
    source = Column(String, nullable=False)  # "ai_generated" | "user_feedback"
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    book = relationship("Book", back_populates="tags")


class BookRecommendation(Base):
    __tablename__ = "book_recommendations"
    __table_args__ = (
        Index("ix_book_rec_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_id = Column(
        UUID(as_uuid=True), ForeignKey("child_profiles.id"), nullable=False
    )
    parent_text = Column(Text, nullable=False)
    intent_analysis = Column(JSON, nullable=False)
    recommended_books = Column(JSON, nullable=False)  # [{book_id, rank, match_score}]
    guides = Column(JSON, nullable=False)  # [{book_id, why_this_book, ...}]
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="book_recommendations")
    child = relationship("ChildProfile", back_populates="book_recommendations")
