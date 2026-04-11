"""SafetyRails CRUD API 및 시드 함수.

S9: 안전 규칙 모델 + API
"""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.db.models import SafetyRails

router = APIRouter(prefix="/guardrails/safety-rails", tags=["guardrails"])

# 시드 JSON 경로 (프로젝트 루트 기준)
_SEED_PATH = (
    Path(__file__).resolve().parents[6]
    / "docs"
    / "guardrail-seeds"
    / "safety-rails.json"
)

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Pydantic 스키마
# ---------------------------------------------------------------------------


class PatternBlockItem(BaseModel):
    pattern: str
    intent: str


class ContentFilterSchema(BaseModel):
    description: str
    exact_block: list[str]
    pattern_block: list[PatternBlockItem]
    allowlist: list[str]


class IllustrationSafetySchema(BaseModel):
    description: str
    negative_prompts: list[str]


class SafetyRailsCreate(BaseModel):
    prohibitions: list[str]
    required_elements: list[str]
    content_filter: ContentFilterSchema
    illustration_safety: IllustrationSafetySchema


class SafetyRailsResponse(BaseModel):
    id: int
    prohibitions: list[str]
    required_elements: list[str]
    content_filter: ContentFilterSchema
    illustration_safety: IllustrationSafetySchema

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _to_response(rails: SafetyRails) -> SafetyRailsResponse:
    return SafetyRailsResponse(
        id=rails.id,
        prohibitions=rails.prohibitions,
        required_elements=rails.required_elements,
        content_filter=ContentFilterSchema(**rails.content_filter),
        illustration_safety=IllustrationSafetySchema(**rails.illustration_safety),
    )


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SafetyRailsResponse])
async def list_safety_rails(db: DbDep) -> list[SafetyRailsResponse]:
    """안전 규칙 전체 목록 조회."""
    result = await db.execute(select(SafetyRails))
    records = result.scalars().all()
    return [_to_response(r) for r in records]


@router.get("/{rails_id}", response_model=SafetyRailsResponse)
async def get_safety_rails(db: DbDep, rails_id: int) -> SafetyRailsResponse:
    """ID로 단일 안전 규칙 조회."""
    record = await db.get(SafetyRails, rails_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Safety rails not found")
    return _to_response(record)


@router.post("", response_model=SafetyRailsResponse, status_code=201)
async def create_safety_rails(
    db: DbDep,
    payload: SafetyRailsCreate,
) -> SafetyRailsResponse:
    """안전 규칙 생성."""
    record = SafetyRails(
        prohibitions=payload.prohibitions,
        required_elements=payload.required_elements,
        content_filter=payload.content_filter.model_dump(),
        illustration_safety=payload.illustration_safety.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _to_response(record)


@router.delete("/{rails_id}", status_code=204)
async def delete_safety_rails(db: DbDep, rails_id: int) -> None:
    """안전 규칙 삭제."""
    record = await db.get(SafetyRails, rails_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Safety rails not found")
    await db.delete(record)
    await db.commit()


# ---------------------------------------------------------------------------
# 시드 함수
# ---------------------------------------------------------------------------


async def seed_safety_rails(db: AsyncSession) -> None:
    """safety-rails.json의 안전 규칙을 DB에 삽입한다.

    이미 데이터가 존재하면 건너뛴다 (중복 삽입 방지).
    """
    result = await db.execute(select(SafetyRails))
    if result.scalars().first() is not None:
        return

    with _SEED_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    record = SafetyRails(
        prohibitions=data["prohibitions"],
        required_elements=data["required_elements"],
        content_filter=data["content_filter"],
        illustration_safety=data["illustration_safety"],
    )
    db.add(record)
