"""일러스트 오케스트레이터 (S26).

전체 일러스트 생성 플로우:
1. 장면별 일러스트 생성 (SceneIllustrationService)
2. CLIP+DINOv2 하이브리드 검증 (ConsistencyValidator)
3. 실패 시: 재생성(2회) → 인페인팅 폴백(1회)
4. S3 업로드 (ImageStorageService)

AsyncGenerator로 장면별 yield → SSE 진행률 전달 가능.
"""

import logging
from collections.abc import AsyncGenerator

import httpx
from pydantic import BaseModel

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.consistency_validator import (
    ConsistencyScore,
    ConsistencyValidator,
)
from storytale.illustration.image_storage_service import ImageStorageService
from storytale.illustration.inpainting_service import InpaintingService
from storytale.illustration.scene_illustration_service import (
    DEFAULT_ID_WEIGHT,
    SceneIllustrationError,
    SceneIllustrationService,
)
from storytale.interpreter.story_personalizer import PersonalizedScene

logger = logging.getLogger(__name__)

MAX_GENERATION_ATTEMPTS = 3
ID_WEIGHT_BOOST = 0.1


class OrchestratedIllustration(BaseModel):
    """오케스트레이터가 yield하는 최종 결과. 일관성 점수 포함."""

    scene_id: str
    image_url: str
    consistency_score: ConsistencyScore
    generation_attempts: int
    used_inpainting: bool
    width: int
    height: int


class IllustrationOrchestratorError(Exception):
    """오케스트레이터 에러."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class IllustrationOrchestrator:
    """일러스트 전체 파이프라인 오케스트레이터.

    Args:
        scene_illustration_service: 장면 일러스트 생성 (S23).
        consistency_validator: CLIP+DINOv2 검증 (S24).
        inpainting_service: 인페인팅 폴백 (S24).
        image_storage_service: S3 업로드 (S25).
    """

    def __init__(
        self,
        scene_illustration_service: SceneIllustrationService,
        consistency_validator: ConsistencyValidator,
        inpainting_service: InpaintingService,
        image_storage_service: ImageStorageService,
    ) -> None:
        self._scene_service = scene_illustration_service
        self._validator = consistency_validator
        self._inpainting = inpainting_service
        self._storage = image_storage_service

    async def generate_all_illustrations(
        self,
        story_id: str,
        scenes: list[PersonalizedScene],
        character: CharacterSheet,
        style: str,
        scene_emotions: dict[str, str] | None = None,
    ) -> AsyncGenerator[OrchestratedIllustration, None]:
        """전체 장면 일러스트 생성.

        장면별로 생성 → 검증 → 재시도/인페인팅 → S3 업로드 후 yield.

        Args:
            story_id: 스토리 ID (S3 키 생성용).
            scenes: 개인화된 장면 목록.
            character: 캐릭터 시트.
            style: 일러스트 스타일.
            scene_emotions: scene_id → emotion 매핑. 없으면 "neutral" 사용.

        Yields:
            OrchestratedIllustration: 완성된 장면 일러스트.

        Raises:
            IllustrationOrchestratorError: 장면 생성 자체가 실패한 경우.
        """
        emotions = scene_emotions or {}

        for scene in scenes:
            result = await self._process_scene(
                story_id=story_id,
                scene=scene,
                character=character,
                style=style,
                emotion=emotions.get(scene.scene_id, "neutral"),
            )
            yield result

    async def _process_scene(
        self,
        story_id: str,
        scene: PersonalizedScene,
        character: CharacterSheet,
        style: str,
        emotion: str,
    ) -> OrchestratedIllustration:
        """단일 장면 처리: 생성 → 검증 → 재시도 → 인페인팅 → S3 업로드."""
        best_image_url: str | None = None
        best_score: ConsistencyScore | None = None
        attempts = 0

        for attempt in range(MAX_GENERATION_ATTEMPTS):
            attempts = attempt + 1

            # attempt 2+ → id_weight 부스트 (계약: "2차 실패 시 id_weight +0.1 상향")
            id_weight: float | None = None
            if attempt >= 1:
                id_weight = DEFAULT_ID_WEIGHT + ID_WEIGHT_BOOST

            try:
                illustration = await self._scene_service.generate_illustration(
                    scene_id=scene.scene_id,
                    illustration_prompt=scene.illustration_prompt,
                    character=character,
                    style=style,
                    scene_emotion=emotion,
                    id_weight=id_weight,
                )
            except SceneIllustrationError as exc:
                raise IllustrationOrchestratorError(
                    code="SCENE_GENERATION_FAILED",
                    message=(f"장면 {scene.scene_id} 일러스트 생성 실패: {exc}"),
                ) from exc

            score = await self._validator.validate(illustration.image_url, character)

            if score.passed:
                best_image_url = illustration.image_url
                best_score = score
                break

            # 현재까지 가장 나은 결과 기록
            if best_score is None or score.composite_score > best_score.composite_score:
                best_image_url = illustration.image_url
                best_score = score

            logger.warning(
                "consistency_failed scene=%s attempt=%d composite=%.3f reason=%s",
                scene.scene_id,
                attempts,
                score.composite_score,
                score.failure_reason,
            )

        used_inpainting = False

        # 3회 모두 실패 → 인페인팅 폴백
        if best_score is not None and not best_score.passed:
            logger.info(
                "inpainting_fallback scene=%s reason=%s",
                scene.scene_id,
                best_score.failure_reason,
            )

            failure_reason = best_score.failure_reason or "face_drift"

            inpaint_result = await self._inpainting.correct_character_region(
                scene_image_url=best_image_url,
                character_sheet=character,
                failure_reason=failure_reason,
            )

            best_image_url = inpaint_result.corrected_image_url
            best_score = inpaint_result.final_score
            used_inpainting = True

        # 이미지 다운로드 후 bytes로 S3 업로드
        s3_key = f"stories/{story_id}/scenes/{scene.scene_id}.png"
        async with httpx.AsyncClient() as http:
            resp = await http.get(best_image_url)
            resp.raise_for_status()
            image_bytes = resp.content
        s3_url = await self._storage.upload(image_bytes, s3_key)

        return OrchestratedIllustration(
            scene_id=scene.scene_id,
            image_url=s3_url,
            consistency_score=best_score,
            generation_attempts=attempts,
            used_inpainting=used_inpainting,
            width=768,
            height=768,
        )
