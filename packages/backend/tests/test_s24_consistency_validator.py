"""S24 — CLIP+DINOv2 하이브리드 일관성 검증 테스트.

ConsistencyValidator:
- CLIP(0.4) + DINOv2(0.6) 가중 합산 compositeScore
- threshold 0.80
- failureReason 분류: face_drift, style_mismatch, proportion_error
"""

from unittest.mock import AsyncMock

import pytest

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.consistency_validator import (
    ConsistencyScore,
    ConsistencyValidator,
    ConsistencyValidatorError,
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
def mock_clip_model():
    """CLIP 임베딩 추출 모킹."""
    model = AsyncMock()
    return model


@pytest.fixture()
def mock_dino_model():
    """DINOv2 임베딩 추출 모킹."""
    model = AsyncMock()
    return model


@pytest.fixture()
def validator(mock_clip_model, mock_dino_model):
    return ConsistencyValidator(
        clip_model=mock_clip_model,
        dino_model=mock_dino_model,
    )


# ==================================================================
# 카테고리 1: 검증 통과 케이스
# ==================================================================


class TestValidationPassed:
    """compositeScore >= 0.80 → passed=True, failureReason=None."""

    @pytest.mark.asyncio()
    async def test_high_scores_pass(self, validator, character_sheet):
        """CLIP=0.90, DINO=0.92 → composite=0.912 → 통과."""
        validator._clip_model.get_similarity.return_value = 0.90
        validator._dino_model.get_similarity.return_value = 0.92

        result = await validator.validate(
            "https://example.com/scene1.png", character_sheet
        )

        assert isinstance(result, ConsistencyScore)
        assert result.clip_score == pytest.approx(0.90)
        assert result.dino_score == pytest.approx(0.92)
        assert result.composite_score == pytest.approx(0.4 * 0.90 + 0.6 * 0.92)
        assert result.passed is True
        assert result.failure_reason is None

    @pytest.mark.asyncio()
    async def test_exactly_threshold_passes(self, validator, character_sheet):
        """compositeScore == 0.80 정확히 경계값 → 통과."""
        # 0.4 * clip + 0.6 * dino = 0.80
        # clip=0.80, dino=0.80 → 0.32 + 0.48 = 0.80
        validator._clip_model.get_similarity.return_value = 0.80
        validator._dino_model.get_similarity.return_value = 0.80

        result = await validator.validate(
            "https://example.com/scene2.png", character_sheet
        )

        assert result.composite_score == pytest.approx(0.80)
        assert result.passed is True
        assert result.failure_reason is None

    @pytest.mark.asyncio()
    async def test_uses_front_reference_image(self, validator, character_sheet):
        """캐릭터 시트 정면 이미지와 비교."""
        validator._clip_model.get_similarity.return_value = 0.85
        validator._dino_model.get_similarity.return_value = 0.88

        await validator.validate("https://example.com/scene3.png", character_sheet)

        # 정면 이미지가 참조로 사용되는지 확인
        validator._clip_model.get_similarity.assert_called_once()
        call_args = validator._clip_model.get_similarity.call_args
        assert call_args[0][1] == "https://example.com/front.png"

        validator._dino_model.get_similarity.assert_called_once()
        dino_args = validator._dino_model.get_similarity.call_args
        assert dino_args[0][1] == "https://example.com/front.png"


# ==================================================================
# 카테고리 2: 실패 분류 — face_drift (DINO low)
# ==================================================================


class TestFaceDrift:
    """DINOv2 점수가 낮으면 face_drift."""

    @pytest.mark.asyncio()
    async def test_low_dino_classified_as_face_drift(self, validator, character_sheet):
        """CLIP=0.85, DINO=0.60 → composite=0.70 → face_drift."""
        validator._clip_model.get_similarity.return_value = 0.85
        validator._dino_model.get_similarity.return_value = 0.60

        result = await validator.validate(
            "https://example.com/bad_face.png", character_sheet
        )

        assert result.passed is False
        assert result.failure_reason == "face_drift"
        assert result.composite_score == pytest.approx(0.4 * 0.85 + 0.6 * 0.60)


# ==================================================================
# 카테고리 3: 실패 분류 — style_mismatch (CLIP low)
# ==================================================================


class TestStyleMismatch:
    """CLIP 점수가 낮으면 style_mismatch."""

    @pytest.mark.asyncio()
    async def test_low_clip_classified_as_style_mismatch(
        self, validator, character_sheet
    ):
        """CLIP=0.55, DINO=0.85 → composite=0.73 → style_mismatch."""
        validator._clip_model.get_similarity.return_value = 0.55
        validator._dino_model.get_similarity.return_value = 0.85

        result = await validator.validate(
            "https://example.com/wrong_style.png", character_sheet
        )

        assert result.passed is False
        assert result.failure_reason == "style_mismatch"

    @pytest.mark.asyncio()
    async def test_both_low_but_clip_lower_is_style_mismatch(
        self, validator, character_sheet
    ):
        """CLIP=0.50, DINO=0.70 → 둘 다 낮지만 CLIP이 더 낮으면 style_mismatch."""
        validator._clip_model.get_similarity.return_value = 0.50
        validator._dino_model.get_similarity.return_value = 0.70

        result = await validator.validate(
            "https://example.com/both_bad.png", character_sheet
        )

        assert result.passed is False
        assert result.failure_reason == "style_mismatch"

    @pytest.mark.asyncio()
    async def test_equal_scores_above_low_threshold(self, validator, character_sheet):
        """CLIP=0.70, DINO=0.70 → 동점이면 style_mismatch (not face_drift)."""
        validator._clip_model.get_similarity.return_value = 0.70
        validator._dino_model.get_similarity.return_value = 0.70

        result = await validator.validate(
            "https://example.com/equal_scores.png", character_sheet
        )

        assert result.passed is False
        assert result.composite_score == pytest.approx(0.70)
        assert result.failure_reason == "style_mismatch"

    @pytest.mark.asyncio()
    async def test_only_clip_below_low_threshold(self, validator, character_sheet):
        """CLIP=0.60, DINO=0.70 → dino > clip이므로 style_mismatch."""
        validator._clip_model.get_similarity.return_value = 0.60
        validator._dino_model.get_similarity.return_value = 0.70

        result = await validator.validate(
            "https://example.com/clip_low.png", character_sheet
        )

        assert result.passed is False
        assert result.failure_reason == "style_mismatch"


# ==================================================================
# 카테고리 4: 실패 분류 — proportion_error (둘 다 낮음)
# ==================================================================


class TestProportionError:
    """CLIP과 DINO 둘 다 낮은 경우 proportion_error."""

    @pytest.mark.asyncio()
    async def test_both_very_low_classified_as_proportion_error(
        self, validator, character_sheet
    ):
        """CLIP=0.40, DINO=0.35 → 둘 다 매우 낮음 → proportion_error."""
        validator._clip_model.get_similarity.return_value = 0.40
        validator._dino_model.get_similarity.return_value = 0.35

        result = await validator.validate(
            "https://example.com/proportion_fail.png", character_sheet
        )

        assert result.passed is False
        assert result.failure_reason == "proportion_error"
        assert result.composite_score == pytest.approx(0.4 * 0.40 + 0.6 * 0.35)


# ==================================================================
# 카테고리 5: 에러 처리
# ==================================================================


class TestErrorHandling:
    """모델 호출 실패 시 에러 전파."""

    @pytest.mark.asyncio()
    async def test_clip_model_failure_raises(self, validator, character_sheet):
        """CLIP 모델 에러 → ConsistencyValidatorError."""
        validator._clip_model.get_similarity.side_effect = RuntimeError(
            "CLIP model failed"
        )
        validator._dino_model.get_similarity.return_value = 0.85

        with pytest.raises(ConsistencyValidatorError, match="CLIP"):
            await validator.validate("https://example.com/err.png", character_sheet)

    @pytest.mark.asyncio()
    async def test_dino_model_failure_raises(self, validator, character_sheet):
        """DINOv2 모델 에러 → ConsistencyValidatorError."""
        validator._clip_model.get_similarity.return_value = 0.85
        validator._dino_model.get_similarity.side_effect = RuntimeError(
            "DINOv2 model failed"
        )

        with pytest.raises(ConsistencyValidatorError, match="DINOv2"):
            await validator.validate("https://example.com/err2.png", character_sheet)

    @pytest.mark.asyncio()
    async def test_missing_front_reference_raises(self, validator):
        """정면 참조 이미지가 빈 문자열인 캐릭터 시트 → 에러."""
        sheet = _make_character_sheet(
            reference_images={"front": ""},
        )

        with pytest.raises(ConsistencyValidatorError, match="front"):
            await validator.validate("https://example.com/scene.png", sheet)
