from sqlalchemy import create_engine

from storytale.db.base import Base

# try to import before implementation
from storytale.db.models import (
    AgeStyleGuide,
    ChildProfile,
    EmotionalArcTemplate,
    SafetyRails,
    Story,
    StoryPage,
    User,
)


def test_db_models_exist():
    assert hasattr(User, "email")
    assert hasattr(ChildProfile, "name")
    assert hasattr(EmotionalArcTemplate, "stages")
    assert hasattr(AgeStyleGuide, "sentence_rules")
    assert hasattr(SafetyRails, "prohibitions")
    assert hasattr(Story, "status")
    assert hasattr(StoryPage, "text")


def test_db_schema_generation():
    sqlite_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=sqlite_engine)

    tables = Base.metadata.tables.keys()
    assert "users" in tables
    assert "child_profiles" in tables
    assert "emotional_arc_templates" in tables
    assert "age_style_guides" in tables
    assert "safety_rails" in tables
    assert "stories" in tables
    assert "story_pages" in tables
