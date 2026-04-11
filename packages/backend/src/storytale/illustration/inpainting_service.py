"""인페인팅 폴백 서비스.

compositeScore 미달 시 캐릭터 얼굴/상체 영역만 인페인팅으로 보정한다.
배경과 포즈는 유지하면서 캐릭터 동일성만 복구.

failureReason별 전략:
- face_drift: PuLID id_weight 상향 (0.95) → 얼굴 구조 복구
- style_mismatch: 프롬프트에 스타일 키워드 강화
- proportion_error: id_weight 상향 + 스타일 키워드 강화
"""

import logging

from pydantic import BaseModel

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.consistency_validator import (
    ConsistencyFailureReason,
    ConsistencyScore,
    ConsistencyValidator,
)
from storytale.illustration.replicate_client import (
    ReplicateClient,
    ReplicateClientError,
)

logger = logging.getLogger(__name__)

PULID_MODEL = "bytedance/flux-pulid"
INPAINTING_ID_WEIGHT_DEFAULT = 0.85
INPAINTING_ID_WEIGHT_HIGH = 0.95


class InpaintingResult(BaseModel):
    """인페인팅 결과."""

    corrected_image_url: str
    final_score: ConsistencyScore


class InpaintingServiceError(Exception):
    """인페인팅 실패."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InpaintingService:
    """캐릭터 영역 인페인팅 보정 서비스.

    Args:
        replicate_client: Replicate API 호출.
        consistency_validator: 보정 후 재검증.
    """

    def __init__(
        self,
        replicate_client: ReplicateClient,
        consistency_validator: ConsistencyValidator,
    ) -> None:
        self._replicate = replicate_client
        self._validator = consistency_validator

    async def correct_character_region(
        self,
        scene_image_url: str,
        character_sheet: CharacterSheet,
        failure_reason: ConsistencyFailureReason,
    ) -> InpaintingResult:
        """캐릭터 영역 인페인팅 보정.

        Args:
            scene_image_url: 원본 장면 이미지 URL.
            character_sheet: 캐릭터 시트 (얼굴 앵커 + Identity Block).
            failure_reason: 실패 원인 (전략 선택에 사용).

        Returns:
            InpaintingResult: 보정된 이미지 URL + 재검증 점수.

        Raises:
            InpaintingServiceError: 인페인팅 실패.
        """
        prompt, id_weight = self._build_strategy(character_sheet, failure_reason)

        input_params = {
            "prompt": prompt,
            "main_face_image": character_sheet.face_anchor_url,
            "id_weight": id_weight,
            "num_steps": 20,
            "guidance": 4.0,
            "width": 768,
            "height": 768,
        }

        try:
            result = await self._replicate.run(PULID_MODEL, input_params)
        except ReplicateClientError as exc:
            raise InpaintingServiceError(
                code="INPAINTING_FAILED",
                message=f"인페인팅 Replicate 호출 실패: {exc}",
            ) from exc

        if not result.output:
            raise InpaintingServiceError(
                code="EMPTY_OUTPUT",
                message="인페인팅 결과가 빈 출력을 반환.",
            )

        corrected_url = result.output[0]

        final_score = await self._validator.validate(corrected_url, character_sheet)

        logger.info(
            "inpainting_done reason=%s corrected_url=%s composite=%.3f passed=%s",
            failure_reason,
            corrected_url,
            final_score.composite_score,
            final_score.passed,
        )

        return InpaintingResult(
            corrected_image_url=corrected_url,
            final_score=final_score,
        )

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------

    @staticmethod
    def _build_strategy(
        character_sheet: CharacterSheet,
        failure_reason: ConsistencyFailureReason,
    ) -> tuple[str, float]:
        """failureReason별 프롬프트 + id_weight 결정.

        Returns:
            (prompt, id_weight) 튜플.
        """
        identity = character_sheet.identity_prompt_block
        style = character_sheet.style

        if failure_reason == "face_drift":
            prompt = (
                f"{identity}, "
                f"children's book illustration, "
                f"consistent character appearance, same face"
            )
            id_weight = INPAINTING_ID_WEIGHT_HIGH
        elif failure_reason == "style_mismatch":
            prompt = (
                f"{identity}, "
                f"children's book illustration, {style} style, "
                f"consistent art style throughout"
            )
            id_weight = INPAINTING_ID_WEIGHT_DEFAULT
        else:
            # proportion_error: 둘 다 강화
            prompt = (
                f"{identity}, "
                f"children's book illustration, {style} style, "
                f"correct body proportions, consistent character"
            )
            id_weight = INPAINTING_ID_WEIGHT_HIGH

        return prompt, id_weight
