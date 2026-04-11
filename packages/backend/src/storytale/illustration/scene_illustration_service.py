"""장면 일러스트 생성 서비스.

일러스트 프롬프트(Identity Block 포함) + PuLID 얼굴 앵커 + art-direction 규칙
→ 캐릭터 동일성이 유지된 장면 이미지 생성.

art-direction.json의 emotion_to_visual, composition_rules, style modifiers,
absolute_prohibitions를 반영하여 최종 프롬프트를 구성한다.
"""

import logging
from typing import Any

from pydantic import BaseModel

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.replicate_client import (
    ReplicateClient,
    ReplicateClientError,
)

logger = logging.getLogger(__name__)

PULID_MODEL = "bytedance/flux-pulid"
DEFAULT_ID_WEIGHT = 0.85
SCENE_WIDTH = 768
SCENE_HEIGHT = 768


class SceneIllustration(BaseModel):
    """생성된 장면 일러스트."""

    scene_id: str
    image_url: str
    generation_attempts: int
    used_inpainting: bool
    width: int
    height: int


class SceneIllustrationError(Exception):
    """장면 일러스트 생성 실패."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SceneIllustrationService:
    """장면 일러스트 생성 서비스.

    Args:
        replicate_client: PuLID 이미지 생성용.
        art_direction: art-direction.json 전체 데이터.
        id_weight: PuLID 얼굴 동일성 가중치. 기본 0.85.
    """

    def __init__(
        self,
        replicate_client: ReplicateClient,
        art_direction: dict[str, Any],
        id_weight: float = DEFAULT_ID_WEIGHT,
    ) -> None:
        self._replicate = replicate_client
        self._art_direction = art_direction
        self._id_weight = id_weight

    async def generate_illustration(
        self,
        scene_id: str,
        illustration_prompt: str,
        character: CharacterSheet,
        style: str,
        scene_emotion: str,
        id_weight: float | None = None,
    ) -> SceneIllustration:
        """장면 일러스트 생성.

        Args:
            scene_id: 장면 식별자.
            illustration_prompt: 영문 프롬프트 (Identity Block이 이미 포함된 상태).
            character: 캐릭터 시트 (faceAnchorUrl 등).
            style: 일러스트 스타일 (watercolor, pastel_crayon, clean_digital).
            scene_emotion: 장면 감정 (emotion_to_visual 참조).

        Returns:
            SceneIllustration.

        Raises:
            SceneIllustrationError: 스타일 미지원, 생성 실패, 빈 출력.
        """
        style_defs = self._art_direction.get("style_definitions", {})
        if style not in style_defs:
            raise SceneIllustrationError(
                code="INVALID_STYLE",
                message=f"지원하지 않는 스타일: {style}",
            )

        enhanced_prompt = self._build_prompt(illustration_prompt, style, scene_emotion)
        negative_prompt = self._build_negative_prompt(style)

        effective_id_weight = id_weight if id_weight is not None else self._id_weight

        input_params: dict[str, Any] = {
            "prompt": enhanced_prompt,
            "negative_prompt": negative_prompt,
            "main_face_image": character.face_anchor_url,
            "id_weight": effective_id_weight,
            "num_steps": 20,
            "guidance": 4.0,
            "width": SCENE_WIDTH,
            "height": SCENE_HEIGHT,
        }

        try:
            result = await self._replicate.run(PULID_MODEL, input_params)
        except ReplicateClientError as exc:
            logger.error(
                "scene_illustration_failed scene_id=%s error=%s",
                scene_id,
                exc,
            )
            raise SceneIllustrationError(
                code="GENERATION_FAILED",
                message=f"장면 일러스트 생성 실패: {exc}",
            ) from exc

        if not result.output:
            raise SceneIllustrationError(
                code="EMPTY_OUTPUT",
                message=f"장면 {scene_id}: PuLID 모델이 빈 출력을 반환.",
            )

        image_url = result.output[0]

        logger.info(
            "scene_illustration_generated scene_id=%s image_url=%s",
            scene_id,
            image_url,
        )

        return SceneIllustration(
            scene_id=scene_id,
            image_url=image_url,
            generation_attempts=1,
            used_inpainting=False,
            width=SCENE_WIDTH,
            height=SCENE_HEIGHT,
        )

    # ------------------------------------------------------------------
    # 프롬프트 빌더
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        base_prompt: str,
        style: str,
        scene_emotion: str,
    ) -> str:
        """프롬프트 5단계 순서로 합성.

        base(Identity+Action+Env) → Emotion → Composition → Style.
        """
        parts: list[str] = [base_prompt]

        # 3. Emotion Block — 감정별 시각 조절 (palette_shift, lighting)
        emotion_visuals = self._art_direction.get("emotion_to_visual", {})
        emotion_config = emotion_visuals.get(scene_emotion, {})
        if palette := emotion_config.get("palette_shift"):
            parts.append(palette)
        if lighting := emotion_config.get("lighting"):
            parts.append(lighting)

        # 4. Composition Block — 구도 규칙
        parts.extend(self._build_composition_tokens())

        # 5. Style Block — positive modifiers + 아동 일러스트 기본
        style_defs = self._art_direction.get("style_definitions", {})
        style_def = style_defs.get(style, {})
        positive_mods = style_def.get("positive_modifiers", [])
        if positive_mods:
            parts.append(", ".join(positive_mods))
        parts.append("child's eye level perspective, children's book illustration")

        return ", ".join(parts)

    def _build_composition_tokens(self) -> list[str]:
        """composition_rules → 영어 프롬프트 토큰."""
        rules = self._art_direction.get("composition_rules", {})
        tokens: list[str] = []

        if rules.get("character_focus"):
            tokens.append("character fills 40-60% of frame")
        max_props = rules.get("max_props_per_scene")
        if max_props:
            tokens.append(f"maximum {max_props} props, simple environment")
        if rules.get("framing"):
            tokens.append("centered or rule-of-thirds framing")

        return tokens

    def _build_negative_prompt(self, style: str) -> str:
        """스타일 네거티브 + absolute_prohibitions 합산."""
        negatives: list[str] = []

        # 스타일 네거티브 모디파이어
        style_defs = self._art_direction.get("style_definitions", {})
        style_def = style_defs.get(style, {})
        negatives.extend(style_def.get("negative_modifiers", []))

        # 절대 금지 항목
        prohibitions = self._art_direction.get("absolute_prohibitions", [])
        negatives.extend(prohibitions)

        return ", ".join(negatives)
