"""S22b — 멀티뷰 캐릭터 시트 + Identity Prompt Block 테스트.

CharacterSheetService:
- 얼굴 앵커 + 스타일 → 정면/3/4/측면 멀티뷰 이미지 생성
- Claude로 Identity Prompt Block 텍스트 생성
- 같은 아이 + 같은 스타일이면 기존 시트 재사용
"""

from unittest.mock import AsyncMock

import pytest

from storytale.illustration.character_sheet_service import (
    CharacterSheet,
    CharacterSheetError,
    CharacterSheetService,
)
from storytale.illustration.replicate_client import (
    PredictionResult,
    ReplicateClientError,
)

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_FACE_ANCHOR_URL = "https://replicate.delivery/face-anchor-001.png"

_STYLE_DEFS = {
    "watercolor": {
        "positive_modifiers": ["soft watercolor wash", "warm pastel tones"],
        "negative_modifiers": ["sharp edges", "photorealistic"],
    },
    "pastel_crayon": {
        "positive_modifiers": ["crayon texture", "hand-drawn quality"],
        "negative_modifiers": ["smooth gradients", "photorealistic"],
    },
    "clean_digital": {
        "positive_modifiers": ["clean digital illustration", "flat design"],
        "negative_modifiers": ["photorealistic", "heavy textures"],
    },
}


def _make_replicate_result(idx: int) -> PredictionResult:
    return PredictionResult(
        prediction_id=f"pred_view_{idx}",
        status="succeeded",
        output=[f"https://replicate.delivery/view-{idx}.png"],
    )


def _make_mock_replicate() -> AsyncMock:
    """3회 연속 호출 → 3개 뷰 이미지 반환."""
    mock = AsyncMock()
    mock.run.side_effect = [
        _make_replicate_result(1),  # front
        _make_replicate_result(2),  # three_quarter
        _make_replicate_result(3),  # side
    ]
    return mock


def _make_mock_llm(response: str = "") -> AsyncMock:
    mock = AsyncMock()
    mock.complete.return_value = response or (
        "a young girl with round face, short black hair, "
        "big brown eyes, rosy cheeks, wearing a yellow sweater"
    )
    return mock


# ---------------------------------------------------------------------------
# 1. 멀티뷰 캐릭터 시트 생성
# ---------------------------------------------------------------------------


class TestCreateCharacterSheet:
    """create_character_sheet: 얼굴 앵커 + 스타일 → 3뷰 참조 이미지."""

    @pytest.mark.asyncio
    async def test_returns_three_view_urls(self) -> None:
        """정면/3/4/측면 3개 URL이 포함된 CharacterSheet 반환."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        sheet = await service.create_character_sheet(
            face_anchor_url=_FACE_ANCHOR_URL,
            style="watercolor",
            gender="female",
            age_approx=5,
        )

        assert sheet.reference_images.front.startswith("https://")
        assert sheet.reference_images.three_quarter.startswith("https://")
        assert sheet.reference_images.side.startswith("https://")

    @pytest.mark.asyncio
    async def test_replicate_called_three_times(self) -> None:
        """ReplicateClient.run이 3회 호출됨 (정면, 3/4, 측면)."""
        mock_replicate = _make_mock_replicate()
        service = CharacterSheetService(
            replicate_client=mock_replicate,
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        await service.create_character_sheet(
            face_anchor_url=_FACE_ANCHOR_URL,
            style="watercolor",
            gender="male",
            age_approx=4,
        )

        assert mock_replicate.run.call_count == 3

    @pytest.mark.asyncio
    async def test_sheet_has_correct_metadata(self) -> None:
        """CharacterSheet에 style, face_anchor_url, created_at 포함."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        sheet = await service.create_character_sheet(
            face_anchor_url=_FACE_ANCHOR_URL,
            style="pastel_crayon",
            gender="female",
            age_approx=6,
        )

        assert sheet.style == "pastel_crayon"
        assert sheet.face_anchor_url == _FACE_ANCHOR_URL
        assert sheet.created_at  # ISO datetime string
        assert sheet.character_id  # non-empty


# ---------------------------------------------------------------------------
# 2. 스타일 모디파이어 적용
# ---------------------------------------------------------------------------


class TestStyleModifiers:
    """생성 프롬프트에 art-direction 스타일 모디파이어 반영."""

    @pytest.mark.asyncio
    async def test_watercolor_modifiers_in_prompt(self) -> None:
        """watercolor 스타일 → positive_modifiers가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = CharacterSheetService(
            replicate_client=mock_replicate,
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        await service.create_character_sheet(
            face_anchor_url=_FACE_ANCHOR_URL,
            style="watercolor",
            gender="female",
            age_approx=5,
        )

        # 첫 번째 호출(정면)의 프롬프트 확인
        first_call_params = mock_replicate.run.call_args_list[0].args[1]
        prompt = first_call_params["prompt"]
        assert "watercolor" in prompt.lower()

    @pytest.mark.asyncio
    async def test_invalid_style_raises_error(self) -> None:
        """정의되지 않은 스타일 → CharacterSheetError."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        with pytest.raises(CharacterSheetError) as exc_info:
            await service.create_character_sheet(
                face_anchor_url=_FACE_ANCHOR_URL,
                style="pixel_art",
                gender="male",
                age_approx=4,
            )
        assert exc_info.value.code == "INVALID_STYLE"


# ---------------------------------------------------------------------------
# 3. Identity Prompt Block 생성
# ---------------------------------------------------------------------------


class TestGenerateIdentityPromptBlock:
    """generate_identity_prompt_block: LLM으로 캐릭터 외형 묘사 텍스트 생성."""

    @pytest.mark.asyncio
    async def test_returns_english_description(self) -> None:
        """LLMClient.complete 호출 → 영문 외형 묘사 반환."""
        expected = (
            "a young girl with round face, short black hair, "
            "big brown eyes, rosy cheeks, wearing a yellow sweater"
        )
        mock_llm = _make_mock_llm(expected)
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=mock_llm,
            style_definitions=_STYLE_DEFS,
        )

        sheet = CharacterSheet(
            character_id="char_001",
            reference_images={
                "front": "https://example.com/front.png",
                "three_quarter": "https://example.com/tq.png",
                "side": "https://example.com/side.png",
            },
            face_anchor_url=_FACE_ANCHOR_URL,
            identity_prompt_block="",
            style="watercolor",
            created_at="2026-04-09T12:00:00",
            gender="female",
            age_approx=5,
        )

        result = await service.generate_identity_prompt_block(sheet)

        assert result == expected
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_includes_character_attributes(self) -> None:
        """LLM 호출 시 성별/연령 정보가 프롬프트에 포함."""
        mock_llm = _make_mock_llm()
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=mock_llm,
            style_definitions=_STYLE_DEFS,
        )

        sheet = CharacterSheet(
            character_id="char_002",
            reference_images={"front": "https://example.com/f.png"},
            face_anchor_url=_FACE_ANCHOR_URL,
            identity_prompt_block="",
            style="pastel_crayon",
            created_at="2026-04-09T12:00:00",
            gender="male",
            age_approx=6,
        )

        await service.generate_identity_prompt_block(sheet)

        call_args = mock_llm.complete.call_args
        user_prompt = call_args.kwargs.get("user") or call_args.args[1]
        assert "boy" in user_prompt.lower() or "male" in user_prompt.lower()


# ---------------------------------------------------------------------------
# 4. 기존 시트 재사용
# ---------------------------------------------------------------------------


class TestGetExistingSheet:
    """get_existing_sheet: 캐시 기반 재사용."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cache(self) -> None:
        """캐시에 없으면 None 반환."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        result = await service.get_existing_sheet("hash_abc", "watercolor")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_sheet(self) -> None:
        """캐시에 저장 후 동일 키로 조회하면 반환."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        sheet = CharacterSheet(
            character_id="char_cached",
            reference_images={"front": "https://example.com/f.png"},
            face_anchor_url=_FACE_ANCHOR_URL,
            identity_prompt_block="a young boy",
            style="watercolor",
            created_at="2026-04-09T12:00:00",
            gender="male",
            age_approx=4,
        )

        service.cache_sheet("hash_xyz", sheet)
        result = await service.get_existing_sheet("hash_xyz", "watercolor")

        assert result is not None
        assert result.character_id == "char_cached"

    @pytest.mark.asyncio
    async def test_different_style_returns_none(self) -> None:
        """같은 해시라도 다른 스타일이면 None."""
        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        sheet = CharacterSheet(
            character_id="char_style",
            reference_images={"front": "https://example.com/f.png"},
            face_anchor_url=_FACE_ANCHOR_URL,
            identity_prompt_block="a young girl",
            style="watercolor",
            created_at="2026-04-09T12:00:00",
            gender="female",
            age_approx=5,
        )

        service.cache_sheet("hash_same", sheet)
        result = await service.get_existing_sheet("hash_same", "pastel_crayon")

        assert result is None


# ---------------------------------------------------------------------------
# 5. 에러 처리
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Replicate/LLM 에러 → CharacterSheetError 변환."""

    @pytest.mark.asyncio
    async def test_replicate_error_wrapped(self) -> None:
        """ReplicateClientError → CharacterSheetError."""
        mock_replicate = AsyncMock()
        mock_replicate.run.side_effect = ReplicateClientError(
            code="PREDICTION_FAILED",
            message="모델 실패",
        )

        service = CharacterSheetService(
            replicate_client=mock_replicate,
            llm_client=_make_mock_llm(),
            style_definitions=_STYLE_DEFS,
        )

        with pytest.raises(CharacterSheetError) as exc_info:
            await service.create_character_sheet(
                face_anchor_url=_FACE_ANCHOR_URL,
                style="watercolor",
                gender="female",
                age_approx=5,
            )
        assert exc_info.value.code == "VIEW_GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_llm_error_wrapped(self) -> None:
        """LLMClient 에러 → CharacterSheetError."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("LLM 호출 실패")

        service = CharacterSheetService(
            replicate_client=_make_mock_replicate(),
            llm_client=mock_llm,
            style_definitions=_STYLE_DEFS,
        )

        sheet = CharacterSheet(
            character_id="char_err",
            reference_images={"front": "https://example.com/f.png"},
            face_anchor_url=_FACE_ANCHOR_URL,
            identity_prompt_block="",
            style="watercolor",
            created_at="2026-04-09T12:00:00",
            gender="female",
            age_approx=5,
        )

        with pytest.raises(CharacterSheetError) as exc_info:
            await service.generate_identity_prompt_block(sheet)
        assert exc_info.value.code == "IDENTITY_BLOCK_FAILED"
