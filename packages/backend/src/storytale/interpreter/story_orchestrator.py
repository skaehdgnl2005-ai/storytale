"""스토리 오케스트레이터 (S18).

InterpreterOrchestrator(S16) + StoryPersonalizer(S17)를 연결하여
전체 스토리 생성 파이프라인을 조율한다.

contracts/story-engine.ts StoryOrchestrator 대응.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from storytale.interpreter.interpreter_orchestrator import (
    InterpreterOrchestrator,
    resolve_age_group,
)
from storytale.interpreter.preview_generator import StoryPreview
from storytale.interpreter.scene_planner import ScenePlan
from storytale.interpreter.story_personalizer import (
    ChildProfile,
    PersonalizedScene,
    StoryPersonalizer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class StoryOrchestratorError(Exception):
    """스토리 생성 중 발생한 오류."""


# ---------------------------------------------------------------------------
# StoryOrchestrator
# ---------------------------------------------------------------------------


class StoryOrchestrator:
    """인터프리터 + 텍스트 생성 전체 파이프라인 오케스트레이터.

    Args:
        interpreter: S16 InterpreterOrchestrator 인스턴스.
        personalizer: S17 StoryPersonalizer 인스턴스.
        age_style_guides: 연령별 문체 규칙 목록 (age-style-guides.json 구조).
    """

    def __init__(
        self,
        interpreter: InterpreterOrchestrator,
        personalizer: StoryPersonalizer,
        age_style_guides: list[dict[str, Any]],
    ) -> None:
        self._interpreter = interpreter
        self._personalizer = personalizer
        self._age_styles = {g["age_group"]: g for g in age_style_guides}

    # ------------------------------------------------------------------
    # Phase A: 해석 & 설계
    # ------------------------------------------------------------------

    async def interpret_and_plan(
        self,
        parent_text: str,
        purpose_category: str,
        child: ChildProfile,
    ) -> ScenePlan:
        """부모 텍스트 → 의도분석 → 장면설계.

        InterpreterOrchestrator에 위임. child.age를 전달.
        """
        return await self._interpreter.interpret_and_plan(
            parent_text=parent_text,
            purpose_category=purpose_category,
            child_age=child.age,
        )

    # ------------------------------------------------------------------
    # Phase B: 미리보기
    # ------------------------------------------------------------------

    async def get_preview(
        self,
        plan: ScenePlan,
        style: str,
        child_name: str | None = None,
    ) -> StoryPreview:
        """ScenePlan + style → StoryPreview (부모 미리보기)."""
        return await self._interpreter.get_preview(
            scene_plan=plan,
            style=style,
            child_name=child_name,
        )

    # ------------------------------------------------------------------
    # Phase C: 수정
    # ------------------------------------------------------------------

    async def revise_plan(
        self,
        plan: ScenePlan,
        feedback: str,
    ) -> ScenePlan:
        """부모 피드백 → ScenePlan 수정.

        MaxRevisionsError는 InterpreterOrchestrator에서 발생.
        """
        return await self._interpreter.revise_plan(
            current_plan=plan,
            parent_feedback=feedback,
        )

    # ------------------------------------------------------------------
    # Phase D: 생성 (확정 후)
    # ------------------------------------------------------------------

    async def generate_story(
        self,
        confirmed_plan: ScenePlan,
        child: ChildProfile,
        style: str,
    ) -> AsyncGenerator[PersonalizedScene, None]:
        """확정된 ScenePlan의 장면별 텍스트를 순차 생성한다.

        각 장면 완료 시 PersonalizedScene을 yield한다.

        Args:
            confirmed_plan: 부모가 확정한 ScenePlan.
            child: 아이 프로필.
            style: 일러스트 스타일 (현재 텍스트 생성에는 미사용, 향후 확장용).

        Yields:
            PersonalizedScene: 장면별 개인화 결과.

        Raises:
            StoryOrchestratorError: 장면 생성 실패 시.
        """
        age_group = resolve_age_group(child.age)
        age_style = self._age_styles[age_group]
        total_scenes = len(confirmed_plan.scenes)
        previous_summary = "없음"

        logger.info(
            "generate_story title=%s scenes=%d child_id=%s age_group=%s",
            confirmed_plan.title,
            total_scenes,
            child.child_id,
            age_group,
        )

        for idx, scene in enumerate(confirmed_plan.scenes, start=1):
            try:
                personalized = await self._personalizer.generate_scene(
                    scene=scene,
                    child=child,
                    previous_summary=previous_summary,
                    age_style=age_style,
                    style_notes=confirmed_plan.style_notes,
                    scene_index=idx,
                    total_scenes=total_scenes,
                    identity_prompt_block=None,
                )
            except Exception as exc:
                raise StoryOrchestratorError(
                    f"장면 '{scene.scene_id}' 생성 실패: {exc}"
                ) from exc

            logger.info(
                "scene_generated scene_id=%s page=%d (%d/%d)",
                personalized.scene_id,
                personalized.page_number,
                idx,
                total_scenes,
            )

            previous_summary = personalized.text
            yield personalized
