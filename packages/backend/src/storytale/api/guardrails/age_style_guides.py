"""AgeStyleGuide CRUD API 및 시드 함수.

S8: 연령별 문체 규칙 모델 + API
"""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.db.models import AgeStyleGuide

router = APIRouter(prefix="/guardrails/age-styles", tags=["guardrails"])

# 시드 JSON 경로 (프로젝트 루트 기준)
_SEED_PATH = (
    Path(__file__).resolve().parents[6]
    / "docs"
    / "guardrail-seeds"
    / "age-style-guides.json"
)

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Pydantic 스키마
# ---------------------------------------------------------------------------


class SentenceRulesSchema(BaseModel):
    max_characters_per_sentence: int
    preferred_structure: str
    repetition_pattern: str
    vocabulary_level: str


class EmotionalExpressionSchema(BaseModel):
    method: str
    good_examples: list[str]
    bad_examples: list[str]


class PageRangeSchema(BaseModel):
    min: int
    max: int


class PageGuidelinesSchema(BaseModel):
    sentences_per_page: PageRangeSchema
    max_characters_per_page: int
    total_pages: PageRangeSchema


class AgeStyleGuideCreate(BaseModel):
    age_group: str
    sentence_rules: SentenceRulesSchema
    emotional_expression: EmotionalExpressionSchema
    page_guidelines: PageGuidelinesSchema


class AgeStyleGuideResponse(BaseModel):
    age_group: str
    sentence_rules: SentenceRulesSchema
    emotional_expression: EmotionalExpressionSchema
    page_guidelines: PageGuidelinesSchema

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _to_response(guide: AgeStyleGuide) -> AgeStyleGuideResponse:
    return AgeStyleGuideResponse(
        age_group=guide.age_group,
        sentence_rules=SentenceRulesSchema(**guide.sentence_rules),
        emotional_expression=EmotionalExpressionSchema(**guide.emotional_expression),
        page_guidelines=PageGuidelinesSchema(**guide.page_guidelines),
    )


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AgeStyleGuideResponse])
async def list_age_styles(db: DbDep) -> list[AgeStyleGuideResponse]:
    """연령별 문체 가이드 전체 목록 조회."""
    result = await db.execute(select(AgeStyleGuide))
    guides = result.scalars().all()
    return [_to_response(g) for g in guides]


@router.get("/{age_group}", response_model=AgeStyleGuideResponse)
async def get_age_style(db: DbDep, age_group: str) -> AgeStyleGuideResponse:
    """특정 age_group의 문체 가이드 조회."""
    guide = await db.get(AgeStyleGuide, age_group)
    if guide is None:
        raise HTTPException(status_code=404, detail="Age style guide not found")
    return _to_response(guide)


@router.post("", response_model=AgeStyleGuideResponse, status_code=201)
async def create_age_style(
    db: DbDep,
    payload: AgeStyleGuideCreate,
) -> AgeStyleGuideResponse:
    """연령별 문체 가이드 생성."""
    existing = await db.get(AgeStyleGuide, payload.age_group)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Age style guide already exists")

    guide = AgeStyleGuide(
        age_group=payload.age_group,
        sentence_rules=payload.sentence_rules.model_dump(),
        emotional_expression=payload.emotional_expression.model_dump(),
        page_guidelines=payload.page_guidelines.model_dump(),
    )
    db.add(guide)
    await db.commit()
    await db.refresh(guide)
    return _to_response(guide)


@router.delete("/{age_group}", status_code=204)
async def delete_age_style(db: DbDep, age_group: str) -> None:
    """연령별 문체 가이드 삭제."""
    guide = await db.get(AgeStyleGuide, age_group)
    if guide is None:
        raise HTTPException(status_code=404, detail="Age style guide not found")
    await db.delete(guide)
    await db.commit()


# ---------------------------------------------------------------------------
# 시드 함수
# ---------------------------------------------------------------------------


async def seed_age_style_guides(db: AsyncSession) -> None:
    """age-style-guides.json의 3개 연령대 가이드를 DB에 삽입한다.

    이미 존재하는 항목은 건너뛴다.
    """
    with _SEED_PATH.open(encoding="utf-8") as f:
        guides_data = json.load(f)

    for item in guides_data:
        existing = await db.get(AgeStyleGuide, item["age_group"])
        if existing is not None:
            continue
        guide = AgeStyleGuide(
            age_group=item["age_group"],
            sentence_rules=item["sentence_rules"],
            emotional_expression=item["emotional_expression"],
            page_guidelines=item["page_guidelines"],
        )
        db.add(guide)
