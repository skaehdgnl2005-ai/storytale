"""CLIP+DINOv2 하이브리드 일관성 검증 서비스.

생성된 장면 일러스트와 캐릭터 시트 정면 이미지의 유사도를 검증한다.
- CLIP: 글로벌 의미론적 유사도 (스타일, 전체 분위기)
- DINOv2: 구조적 시각 유사도 (얼굴 구조, 비율, 세부 특징)
- compositeScore = 0.4 * clipScore + 0.6 * dinoScore
- threshold: 0.80
"""

import logging
from typing import Literal

from pydantic import BaseModel

from storytale.illustration.character_sheet_service import CharacterSheet

logger = logging.getLogger(__name__)

CLIP_WEIGHT = 0.4
DINO_WEIGHT = 0.6
COMPOSITE_THRESHOLD = 0.80

# failureReason 분류 임계값
# 둘 다 0.65 미만이면 proportion_error (전체적으로 캐릭터가 틀림)
_BOTH_LOW_THRESHOLD = 0.65

ConsistencyFailureReason = Literal["face_drift", "style_mismatch", "proportion_error"]


class ConsistencyScore(BaseModel):
    """일관성 검증 결과."""

    clip_score: float
    dino_score: float
    composite_score: float
    passed: bool
    failure_reason: ConsistencyFailureReason | None = None


class ConsistencyValidatorError(Exception):
    """일관성 검증 실패."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ConsistencyValidator:
    """CLIP+DINOv2 하이브리드 일관성 검증기.

    Args:
        clip_model: CLIP 임베딩 모델. get_similarity(image_url, ref_url) → float.
        dino_model: DINOv2 임베딩 모델. get_similarity(image_url, ref_url) → float.
        threshold: composite score 통과 기준. 기본 0.80.
    """

    def __init__(
        self,
        clip_model: object,
        dino_model: object,
        threshold: float = COMPOSITE_THRESHOLD,
    ) -> None:
        self._clip_model = clip_model
        self._dino_model = dino_model
        self._threshold = threshold

    async def validate(
        self,
        generated_image_url: str,
        character_sheet: CharacterSheet,
    ) -> ConsistencyScore:
        """생성 이미지와 캐릭터 시트 정면 이미지의 유사도 검증.

        Args:
            generated_image_url: 생성된 장면 이미지 URL.
            character_sheet: 캐릭터 시트 (정면 이미지가 참조 기준).

        Returns:
            ConsistencyScore: 검증 결과.

        Raises:
            ConsistencyValidatorError: 참조 이미지 없거나 모델 호출 실패.
        """
        front_url = character_sheet.reference_images.front
        if not front_url:
            raise ConsistencyValidatorError(
                code="MISSING_REFERENCE",
                message="캐릭터 시트에 front 참조 이미지가 없습니다.",
            )

        clip_score = await self._get_clip_score(generated_image_url, front_url)
        dino_score = await self._get_dino_score(generated_image_url, front_url)

        composite = CLIP_WEIGHT * clip_score + DINO_WEIGHT * dino_score
        passed = composite >= self._threshold
        failure_reason = (
            None if passed else self._classify_failure(clip_score, dino_score)
        )

        score = ConsistencyScore(
            clip_score=clip_score,
            dino_score=dino_score,
            composite_score=composite,
            passed=passed,
            failure_reason=failure_reason,
        )

        logger.info(
            "consistency_check image=%s composite=%.3f passed=%s reason=%s",
            generated_image_url,
            composite,
            passed,
            failure_reason,
        )

        return score

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------

    async def _get_clip_score(self, image_url: str, reference_url: str) -> float:
        """CLIP 유사도 조회."""
        try:
            return await self._clip_model.get_similarity(image_url, reference_url)
        except Exception as exc:
            raise ConsistencyValidatorError(
                code="CLIP_FAILED",
                message=f"CLIP 유사도 계산 실패: {exc}",
            ) from exc

    async def _get_dino_score(self, image_url: str, reference_url: str) -> float:
        """DINOv2 유사도 조회."""
        try:
            return await self._dino_model.get_similarity(image_url, reference_url)
        except Exception as exc:
            raise ConsistencyValidatorError(
                code="DINO_FAILED",
                message=f"DINOv2 유사도 계산 실패: {exc}",
            ) from exc

    @staticmethod
    def _classify_failure(
        clip_score: float, dino_score: float
    ) -> ConsistencyFailureReason:
        """실패 원인 분류.

        - 둘 다 매우 낮으면(< 0.65) → proportion_error
        - DINO가 CLIP보다 낮으면 → face_drift (얼굴 구조 불일치)
        - CLIP이 DINO보다 낮으면 → style_mismatch (화풍 불일치)
        """
        if clip_score < _BOTH_LOW_THRESHOLD and dino_score < _BOTH_LOW_THRESHOLD:
            return "proportion_error"
        if dino_score < clip_score:
            return "face_drift"
        return "style_mismatch"
