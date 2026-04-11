"""EmotionalArcTemplate CRUD API 및 시드 함수.

S7: 감정 흐름 템플릿 모델 + CRUD API
"""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException  # Depends used in DbDep
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.db.models import EmotionalArcTemplate

router = APIRouter(prefix="/guardrails/arcs", tags=["guardrails"])

# 시드 JSON 경로 (프로젝트 루트 기준)
_SEED_PATH = (
    Path(__file__).resolve().parents[6]
    / "docs"
    / "guardrail-seeds"
    / "emotional-arcs.json"
)

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Pydantic 스키마
# ---------------------------------------------------------------------------


class ArcStageSchema(BaseModel):
    phase: str
    ratio: float
    purpose: str


class EmotionalArcTemplateCreate(BaseModel):
    arc_id: str
    description: str
    target_ages: list[str]
    stages: list[ArcStageSchema]
    rules: list[str]


class EmotionalArcTemplateResponse(BaseModel):
    arc_id: str
    description: str
    target_ages: list[str]
    stages: list[ArcStageSchema]
    rules: list[str]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _to_response(template: EmotionalArcTemplate) -> EmotionalArcTemplateResponse:
    return EmotionalArcTemplateResponse(
        arc_id=template.id,
        description=template.description,
        target_ages=template.target_ages,
        stages=template.stages,
        rules=template.rules,
    )


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.get("", response_model=list[EmotionalArcTemplateResponse])
async def list_arcs(
    db: DbDep,
    age_group: str | None = None,
) -> list[EmotionalArcTemplateResponse]:
    """감정 흐름 템플릿 목록 조회. age_group 필터 선택적."""
    result = await db.execute(select(EmotionalArcTemplate))
    templates = result.scalars().all()

    if age_group:
        # JSON 배열 필터: Python 레벨에서 처리 (SQLite 호환성)
        templates = [t for t in templates if age_group in t.target_ages]

    return [_to_response(t) for t in templates]


@router.get("/{arc_id}", response_model=EmotionalArcTemplateResponse)
async def get_arc(
    db: DbDep,
    arc_id: str,
) -> EmotionalArcTemplateResponse:
    """특정 arc_id의 감정 흐름 템플릿 조회."""
    template = await db.get(EmotionalArcTemplate, arc_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Arc template not found")
    return _to_response(template)


@router.post("", response_model=EmotionalArcTemplateResponse, status_code=201)
async def create_arc(
    db: DbDep,
    payload: EmotionalArcTemplateCreate,
) -> EmotionalArcTemplateResponse:
    """감정 흐름 템플릿 생성."""
    existing = await db.get(EmotionalArcTemplate, payload.arc_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Arc template already exists")

    template = EmotionalArcTemplate(
        id=payload.arc_id,
        description=payload.description,
        target_ages=payload.target_ages,
        stages=[s.model_dump() for s in payload.stages],
        rules=payload.rules,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.delete("/{arc_id}", status_code=204)
async def delete_arc(
    db: DbDep,
    arc_id: str,
) -> None:
    """감정 흐름 템플릿 삭제."""
    template = await db.get(EmotionalArcTemplate, arc_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Arc template not found")
    await db.delete(template)
    await db.commit()


# ---------------------------------------------------------------------------
# 시드 함수
# ---------------------------------------------------------------------------


async def seed_emotional_arcs(db: AsyncSession) -> None:
    """emotional-arcs.json의 6개 아크를 DB에 삽입한다. 이미 존재하면 건너뛴다."""
    with _SEED_PATH.open(encoding="utf-8") as f:
        arcs_data = json.load(f)

    for arc in arcs_data:
        existing = await db.get(EmotionalArcTemplate, arc["arc_id"])
        if existing is not None:
            continue
        template = EmotionalArcTemplate(
            id=arc["arc_id"],
            description=arc["description"],
            target_ages=arc["target_ages"],
            stages=arc["stages"],
            rules=arc["rules"],
        )
        db.add(template)
