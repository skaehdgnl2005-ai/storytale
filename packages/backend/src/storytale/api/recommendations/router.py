"""동화책 추천 API 라우터 (R7).

POST /recommendations → 상황 분석 + 도서 추천 + 독후 가이드.
GET  /recommendations → 추천 이력 목록.
GET  /recommendations/{id} → 추천 상세.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.db.models import BookRecommendation as BookRecModel
from storytale.interpreter.intent_analyzer import IntentAnalyzer
from storytale.interpreter.llm_client import create_llm_client
from storytale.recommendation.book_recommender import BookRecommender

DbDep = Annotated[AsyncSession, Depends(get_db)]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

MIN_CHILD_AGE = 1
MAX_CHILD_AGE = 12
MAX_PARENT_TEXT = 500

_SEEDS_DIR = (
    Path(__file__).resolve().parents[6] / "docs" / "guardrail-seeds"
)


@lru_cache(maxsize=1)
def _load_arc_templates() -> list[dict]:
    """감정 아크 템플릿 로드 (최초 1회)."""
    path = _SEEDS_DIR / "emotional-arcs.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 요청/응답 모델
# ---------------------------------------------------------------------------


class RecommendRequest(BaseModel):
    parent_text: str = Field(
        ..., min_length=1, max_length=MAX_PARENT_TEXT
    )
    child_age: int = Field(..., ge=MIN_CHILD_AGE, le=MAX_CHILD_AGE)
    purpose_category: str | None = None
    child_id: str | None = None
    user_id: str | None = None


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.post("")
async def create_recommendation(
    req: RecommendRequest,
    db: DbDep,
) -> dict[str, Any]:
    """상황 분석 → 도서 추천 + 독후 가이드."""
    if not req.parent_text.strip():
        raise HTTPException(status_code=400, detail="입력 텍스트가 비어있습니다.")

    llm = create_llm_client()

    # 1단계: 의도 분석 (기존 IntentAnalyzer 재사용)
    arc_templates = _load_arc_templates()
    analyzer = IntentAnalyzer(
        llm_client=llm, arc_templates=arc_templates
    )
    purpose = req.purpose_category or "problem_solving"
    intent = await analyzer.analyze(
        parent_text=req.parent_text,
        purpose_category=purpose,
        child_age=req.child_age,
    )

    # 2단계: 도서 추천 + 가이드 생성
    recommender = BookRecommender(
        llm_client=llm, db_session=db
    )
    result = await recommender.recommend(
        intent=intent.model_dump(),
        child_age=req.child_age,
        limit=3,
    )

    return result


@router.get("")
async def list_recommendations(
    db: DbDep,
    user_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """추천 이력 목록 (페이지네이션)."""
    query = select(BookRecModel)
    count_query = select(func.count()).select_from(BookRecModel)

    if user_id:
        query = query.where(BookRecModel.user_id == user_id)
        count_query = count_query.where(
            BookRecModel.user_id == user_id
        )

    query = query.order_by(
        BookRecModel.created_at.desc()
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return {
        "items": [
            {
                "id": str(r.id),
                "parent_text": r.parent_text,
                "recommended_books": r.recommended_books,
                "created_at": r.created_at.isoformat()
                if r.created_at
                else None,
            }
            for r in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    db: DbDep,
) -> dict[str, Any]:
    """추천 상세 조회."""
    result = await db.execute(
        select(BookRecModel).where(
            BookRecModel.id == recommendation_id
        )
    )
    rec = result.scalar_one_or_none()

    if not rec:
        raise HTTPException(status_code=404, detail="추천을 찾을 수 없습니다.")

    return {
        "id": str(rec.id),
        "parent_text": rec.parent_text,
        "intent_analysis": rec.intent_analysis,
        "recommended_books": rec.recommended_books,
        "guides": rec.guides,
        "created_at": rec.created_at.isoformat()
        if rec.created_at
        else None,
    }
