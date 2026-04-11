"""API Routers."""

from fastapi import APIRouter

from storytale.api.auth_router import router as auth_router
from storytale.api.guardrails.age_style_guides import router as age_style_guides_router
from storytale.api.guardrails.arc_templates import router as arc_templates_router
from storytale.api.guardrails.combined import router as guardrails_combined_router
from storytale.api.guardrails.safety_rails import router as safety_rails_router
from storytale.api.profiles.router import router as profiles_router
from storytale.api.recommendations.router import router as recommendations_router
from storytale.api.stories.router import router as stories_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(profiles_router)
# 통합 조회 먼저 등록 (구체적인 하위 경로보다 앞에 위치)
api_router.include_router(guardrails_combined_router)
api_router.include_router(arc_templates_router)
api_router.include_router(age_style_guides_router)
api_router.include_router(safety_rails_router)
api_router.include_router(stories_router)
api_router.include_router(recommendations_router)
