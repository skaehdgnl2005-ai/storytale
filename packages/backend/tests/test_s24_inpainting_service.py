"""S24 — 인페인팅 폴백 서비스 테스트.

InpaintingService:
- compositeScore 미달 시 캐릭터 영역만 인페인팅 보정
- 보정 후 ConsistencyValidator로 재검증
- failureReason별 다른 인페인팅 전략
"""

from unittest.mock import AsyncMock

import pytest

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.consistency_validator import ConsistencyScore
from storytale.illustration.inpainting_service import (
    InpaintingResult,
    InpaintingService,
    InpaintingServiceError,
)

# ------------------------------------------------------------------
# 공통 픽스처
# ------------------------------------------------------------------


def _make_character_sheet(**overrides) -> CharacterSheet:
    defaults = {
        "character_id": "char-001",
        "reference_images": {
            "front": "https://example.com/front.png",
            "three_quarter": "https://example.com/3q.png",
            "side": "https://example.com/side.png",
        },
        "face_anchor_url": "https://example.com/anchor.png",
        "identity_prompt_block": "a young girl with round face",
        "style": "watercolor_warm",
        "created_at": "2026-04-09T00:00:00+00:00",
        "gender": "female",
        "age_approx": 5,
    }
    defaults.update(overrides)
    return CharacterSheet(**defaults)


@pytest.fixture()
def character_sheet() -> CharacterSheet:
    return _make_character_sheet()


@pytest.fixture()
def mock_replicate():
    client = AsyncMock()
    return client


@pytest.fixture()
def mock_validator():
    validator = AsyncMock()
    return validator


@pytest.fixture()
def service(mock_replicate, mock_validator):
    return InpaintingService(
        replicate_client=mock_replicate,
        consistency_validator=mock_validator,
    )


# ==================================================================
# 카테고리 1: 인페인팅 성공 → 재검증 통과
# ==================================================================


class TestInpaintingSuccess:
    """인페인팅 후 재검증 통과 케이스."""

    @pytest.mark.asyncio()
    async def test_face_drift_correction_succeeds(
        self, service, mock_replicate, mock_validator, character_sheet
    ):
        """face_drift → 인페인팅 → 재검증 통과."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-001",
            status="succeeded",
            output=["https://example.com/corrected.png"],
        )
        mock_validator.validate.return_value = ConsistencyScore(
            clip_score=0.88,
            dino_score=0.85,
            composite_score=0.862,
            passed=True,
            failure_reason=None,
        )

        result = await service.correct_character_region(
            scene_image_url="https://example.com/scene.png",
            character_sheet=character_sheet,
            failure_reason="face_drift",
        )

        assert isinstance(result, InpaintingResult)
        assert result.corrected_image_url == "https://example.com/corrected.png"
        assert result.final_score.passed is True
        assert result.final_score.composite_score == pytest.approx(0.862)

    @pytest.mark.asyncio()
    async def test_style_mismatch_correction_succeeds(
        self, service, mock_replicate, mock_validator, character_sheet
    ):
        """style_mismatch → 인페인팅 → 재검증 통과."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-002",
            status="succeeded",
            output=["https://example.com/style_fixed.png"],
        )
        mock_validator.validate.return_value = ConsistencyScore(
            clip_score=0.83,
            dino_score=0.90,
            composite_score=0.872,
            passed=True,
            failure_reason=None,
        )

        result = await service.correct_character_region(
            scene_image_url="https://example.com/scene.png",
            character_sheet=character_sheet,
            failure_reason="style_mismatch",
        )

        assert result.corrected_image_url == "https://example.com/style_fixed.png"
        assert result.final_score.passed is True


# ==================================================================
# 카테고리 2: failureReason별 프롬프트 전략
# ==================================================================


class TestFailureReasonStrategy:
    """failureReason에 따라 다른 인페인팅 전략 적용."""

    @pytest.mark.asyncio()
    async def test_face_drift_uses_higher_id_weight(
        self, service, mock_replicate, mock_validator, character_sheet
    ):
        """face_drift → PuLID id_weight 상향."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-003",
            status="succeeded",
            output=["https://example.com/fixed.png"],
        )
        mock_validator.validate.return_value = ConsistencyScore(
            clip_score=0.85,
            dino_score=0.85,
            composite_score=0.85,
            passed=True,
            failure_reason=None,
        )

        await service.correct_character_region(
            scene_image_url="https://example.com/scene.png",
            character_sheet=character_sheet,
            failure_reason="face_drift",
        )

        call_args = mock_replicate.run.call_args
        input_params = call_args[0][1]
        assert input_params["id_weight"] >= 0.90

    @pytest.mark.asyncio()
    async def test_style_mismatch_includes_style_in_prompt(
        self, service, mock_replicate, mock_validator, character_sheet
    ):
        """style_mismatch → 프롬프트에 스타일 키워드 강화."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-004",
            status="succeeded",
            output=["https://example.com/fixed.png"],
        )
        mock_validator.validate.return_value = ConsistencyScore(
            clip_score=0.85,
            dino_score=0.85,
            composite_score=0.85,
            passed=True,
            failure_reason=None,
        )

        await service.correct_character_region(
            scene_image_url="https://example.com/scene.png",
            character_sheet=character_sheet,
            failure_reason="style_mismatch",
        )

        call_args = mock_replicate.run.call_args
        input_params = call_args[0][1]
        assert character_sheet.style in input_params["prompt"]


# ==================================================================
# 카테고리 3: 인페인팅 후 재검증 실패
# ==================================================================


class TestInpaintingStillFails:
    """인페인팅 후에도 재검증 미통과."""

    @pytest.mark.asyncio()
    async def test_inpainting_done_but_still_fails(
        self, service, mock_replicate, mock_validator, character_sheet
    ):
        """인페인팅 성공 → 재검증 실패 → 결과에 passed=False 반영."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-005",
            status="succeeded",
            output=["https://example.com/still_bad.png"],
        )
        mock_validator.validate.return_value = ConsistencyScore(
            clip_score=0.70,
            dino_score=0.65,
            composite_score=0.67,
            passed=False,
            failure_reason="face_drift",
        )

        result = await service.correct_character_region(
            scene_image_url="https://example.com/scene.png",
            character_sheet=character_sheet,
            failure_reason="face_drift",
        )

        assert result.corrected_image_url == "https://example.com/still_bad.png"
        assert result.final_score.passed is False


# ==================================================================
# 카테고리 4: 에러 처리
# ==================================================================


class TestInpaintingErrors:
    """인페인팅 과정 에러."""

    @pytest.mark.asyncio()
    async def test_replicate_failure_raises(
        self, service, mock_replicate, character_sheet
    ):
        """Replicate API 실패 → InpaintingServiceError."""
        from storytale.illustration.replicate_client import ReplicateClientError

        mock_replicate.run.side_effect = ReplicateClientError(
            code="API_ERROR", message="Replicate down"
        )

        with pytest.raises(InpaintingServiceError, match="인페인팅"):
            await service.correct_character_region(
                scene_image_url="https://example.com/scene.png",
                character_sheet=character_sheet,
                failure_reason="face_drift",
            )

    @pytest.mark.asyncio()
    async def test_empty_output_raises(self, service, mock_replicate, character_sheet):
        """Replicate 빈 출력 → InpaintingServiceError."""
        from storytale.illustration.replicate_client import PredictionResult

        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred-006",
            status="succeeded",
            output=None,
        )

        with pytest.raises(InpaintingServiceError, match="빈 출력"):
            await service.correct_character_region(
                scene_image_url="https://example.com/scene.png",
                character_sheet=character_sheet,
                failure_reason="proportion_error",
            )
