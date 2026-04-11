"""가드레일 통합 조회 API.

S10: GET /guardrails?age_group=3-4 → 아크 목록 + 문체 가이드 + 안전 규칙 묶음
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.api.guardrails.age_style_guides import (
    AgeStyleGuideResponse,
)
from storytale.api.guardrails.age_style_guides import (
    _to_response as _to_age_style_response,
)
from storytale.api.guardrails.arc_templates import (
    EmotionalArcTemplateResponse,
)
from storytale.api.guardrails.arc_templates import (
    _to_response as _to_arc_response,
)
from storytale.api.guardrails.safety_rails import (
    SafetyRailsResponse,
)
from storytale.api.guardrails.safety_rails import (
    _to_response as _to_safety_response,
)
from storytale.db.models import AgeStyleGuide, EmotionalArcTemplate, SafetyRails

router = APIRouter(prefix="/guardrails", tags=["guardrails"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


class GuardrailsBundleResponse(BaseModel):
    age_group: str | None
    arcs: list[EmotionalArcTemplateResponse]
    style_guide: AgeStyleGuideResponse | None
    safety_rails: SafetyRailsResponse | None


@router.get("", response_model=GuardrailsBundleResponse)
async def get_guardrails_bundle(
    db: DbDep,
    age_group: str | None = None,
) -> GuardrailsBundleResponse:
    """age_group으로 필터된 가드레일 번들 조회.

    - arcs: age_group 포함하는 감정 흐름 템플릿 목록 (없으면 전체)
    - style_guide: age_group에 해당하는 문체 가이드 (없으면 null)
    - safety_rails: 싱글톤 안전 규칙 (없으면 null)
    """
    # 1. 감정 흐름 아크 목록
    result = await db.execute(select(EmotionalArcTemplate))
    templates = result.scalars().all()
    if age_group:
        templates = [t for t in templates if age_group in t.target_ages]
    arcs = [_to_arc_response(t) for t in templates]

    # 2. 연령별 문체 가이드 (age_group 지정 시만 조회)
    style_guide: AgeStyleGuideResponse | None = None
    if age_group:
        guide = await db.get(AgeStyleGuide, age_group)
        if guide is not None:
            style_guide = _to_age_style_response(guide)

    # 3. 안전 규칙 (싱글톤 — 첫 번째 레코드)
    rails_result = await db.execute(select(SafetyRails))
    rails = rails_result.scalars().first()
    safety_rails = _to_safety_response(rails) if rails is not None else None

    return GuardrailsBundleResponse(
        age_group=age_group,
        arcs=arcs,
        style_guide=style_guide,
        safety_rails=safety_rails,
    )
