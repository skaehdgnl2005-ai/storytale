"""인터프리터 오케스트레이터 (S16).

의도분석 → 장면설계 → 미리보기 → 수정(최대 3회) → 확정 전체 플로우를 조율한다.
contracts/story-engine.ts StoryInterpreter + PreviewGenerator 통합.
"""

import logging
from typing import Any

from storytale.interpreter.intent_analyzer import IntentAnalyzer
from storytale.interpreter.plan_reviser import PlanReviser
from storytale.interpreter.preview_generator import (
    IllustrationStyle,
    PreviewGenerator,
    StoryPreview,
)
from storytale.interpreter.scene_planner import ScenePlan, ScenePlanner

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3


# ---------------------------------------------------------------------------
# 예외 클래스
# ---------------------------------------------------------------------------


class ArcNotFoundError(Exception):
    """recommended_arc_id에 해당하는 감정 흐름 템플릿을 찾을 수 없을 때."""


class MaxRevisionsError(Exception):
    """최대 수정 횟수(3회)를 초과했을 때."""


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------


def resolve_age_group(age: int) -> str:
    """나이 → AgeGroup 매핑.

    contracts/story-engine.ts resolveAgeGroup 대응.
    3세 미만 → "3-4", 3-4세 → "3-4", 5-6세 → "5-6",
    7-8세 → "7-8", 9세 이상 → "7-8".
    """
    if age <= 4:
        return "3-4"
    if age <= 6:
        return "5-6"
    return "7-8"


# ---------------------------------------------------------------------------
# InterpreterOrchestrator
# ---------------------------------------------------------------------------


class InterpreterOrchestrator:
    """인터프리터 전체 플로우 오케스트레이터.

    Args:
        intent_analyzer: S12 IntentAnalyzer 인스턴스.
        scene_planner: S13 ScenePlanner 인스턴스.
        plan_reviser: S14 PlanReviser 인스턴스.
        preview_generator: S15 PreviewGenerator 인스턴스.
        arc_templates: 감정 흐름 템플릿 목록 (emotional-arcs.json 구조).
        age_style_guides: 연령별 문체 규칙 목록 (age-style-guides.json 구조).
        safety_rails: 안전 규칙 dict (safety-rails.json 구조).
    """

    def __init__(
        self,
        intent_analyzer: IntentAnalyzer,
        scene_planner: ScenePlanner,
        plan_reviser: PlanReviser,
        preview_generator: PreviewGenerator,
        arc_templates: list[dict[str, Any]],
        age_style_guides: list[dict[str, Any]],
        safety_rails: dict[str, Any],
    ) -> None:
        self._analyzer = intent_analyzer
        self._planner = scene_planner
        self._reviser = plan_reviser
        self._preview_gen = preview_generator
        self._arc_templates = {t["arc_id"]: t for t in arc_templates}
        self._age_styles = {g["age_group"]: g for g in age_style_guides}
        self._safety_rails = safety_rails
        self._revision_count = 0

    async def interpret_and_plan(
        self,
        parent_text: str,
        purpose_category: str,
        child_age: int,
    ) -> ScenePlan:
        """부모 텍스트 → 의도분석 → 장면설계.

        Returns:
            검증된 ScenePlan.

        Raises:
            ArcNotFoundError: arc_id 매칭 실패.
            RejectedIntentError: 부적절한 요청.
            ScenePlanError / ScenePlanSafetyError: 장면 설계 검증 실패.
        """
        self._revision_count = 0

        age_group = resolve_age_group(child_age)
        age_style = self._age_styles[age_group]

        logger.info(
            "interpret_and_plan purpose=%s age=%d age_group=%s",
            purpose_category,
            child_age,
            age_group,
        )

        intent = await self._analyzer.analyze(parent_text, purpose_category, child_age)

        arc_id = intent.recommended_arc_id
        arc_template = self._arc_templates.get(arc_id)
        if arc_template is None:
            raise ArcNotFoundError(
                f"arc_id '{arc_id}'에 해당하는 템플릿이 없습니다. "
                f"사용 가능: {sorted(self._arc_templates.keys())}"
            )

        plan = await self._planner.generate(
            intent=intent,
            arc_template=arc_template,
            age_style=age_style,
            safety_rails=self._safety_rails,
        )

        logger.info(
            "interpret_and_plan done title=%s scenes=%d",
            plan.title,
            len(plan.scenes),
        )
        return plan

    async def get_preview(
        self,
        scene_plan: ScenePlan,
        style: IllustrationStyle,
        child_name: str | None = None,
    ) -> StoryPreview:
        """ScenePlan → StoryPreview (부모 미리보기)."""
        return await self._preview_gen.generate(
            scene_plan, style, child_name=child_name
        )

    async def revise_plan(
        self,
        current_plan: ScenePlan,
        parent_feedback: str,
    ) -> ScenePlan:
        """부모 피드백 → ScenePlan 수정. 최대 3회.

        Raises:
            MaxRevisionsError: 수정 횟수 초과.
        """
        if self._revision_count >= MAX_REVISIONS:
            raise MaxRevisionsError(
                f"최대 수정 횟수({MAX_REVISIONS}회)를 초과했습니다."
            )

        self._revision_count += 1

        logger.info(
            "revise_plan revision=%d/%d",
            self._revision_count,
            MAX_REVISIONS,
        )

        return await self._reviser.revise(
            current_plan=current_plan,
            parent_feedback=parent_feedback,
            safety_rails=self._safety_rails,
        )
