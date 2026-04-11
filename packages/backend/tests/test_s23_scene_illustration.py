"""S23 — 장면 일러스트 생성 서비스 테스트.

SceneIllustrationService:
- 일러스트 프롬프트(Identity Block 포함) + PuLID 얼굴 앵커 → 장면 이미지 생성
- art-direction의 emotion_to_visual로 감정별 색감/조명 조절
- composition_rules, style modifiers, absolute_prohibitions 반영
"""

from unittest.mock import AsyncMock

import pytest

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.replicate_client import (
    PredictionResult,
    ReplicateClientError,
)
from storytale.illustration.scene_illustration_service import (
    SceneIllustration,
    SceneIllustrationError,
    SceneIllustrationService,
)

# ---------------------------------------------------------------------------
# 픽스처 / 헬퍼
# ---------------------------------------------------------------------------

_FACE_ANCHOR_URL = "https://replicate.delivery/face-anchor-001.png"

_IDENTITY_BLOCK = (
    "a young girl with round face, short black hair with red hairpin, "
    "wearing yellow sweater with star pattern, rosy cheeks, big brown eyes"
)

_ART_DIRECTION = {
    "style_definitions": {
        "watercolor": {
            "positive_modifiers": [
                "soft watercolor wash",
                "warm pastel tones",
                "visible paper texture",
            ],
            "negative_modifiers": [
                "sharp edges",
                "photorealistic",
                "cell shading",
            ],
        },
        "pastel_crayon": {
            "positive_modifiers": ["crayon texture", "hand-drawn quality"],
            "negative_modifiers": ["smooth gradients", "photorealistic"],
        },
        "clean_digital": {
            "positive_modifiers": [
                "clean digital illustration",
                "flat design with subtle depth",
                "smooth color fills",
                "soft rounded shapes",
            ],
            "negative_modifiers": [
                "photorealistic",
                "heavy textures",
                "grunge",
                "sharp angular shapes",
            ],
        },
    },
    "composition_rules": {
        "character_focus": "주인공이 화면의 40~60%를 차지.",
        "perspective": "아이 눈높이(로우 앵글).",
        "max_props_per_scene": 3,
        "framing": "캐릭터를 프레임 중앙 또는 1/3 지점에 배치.",
    },
    "emotion_to_visual": {
        "joy": {
            "palette_shift": "warm golden highlights, soft yellow-orange accents",
            "lighting": "bright warm sunlight, gentle lens flare",
        },
        "sadness": {
            "palette_shift": "blue-gray undertones, muted cool pastels",
            "lighting": "soft diffused light, slightly dim, overcast feel",
        },
        "fear": {
            "palette_shift": "muted cool tones, desaturated",
            "lighting": "soft ambient light, gentle shadows only",
        },
        "anger": {
            "palette_shift": "warm reds softened to coral-pink",
            "lighting": "warm but slightly intense",
        },
        "courage": {
            "palette_shift": "warm amber and gold tones, subtle glow",
            "lighting": "golden hour lighting, warm directional light from front",
        },
        "comfort": {
            "palette_shift": "soft warm cream and peach tones",
            "lighting": "warm indoor lighting, cozy lamplight feel",
        },
    },
    "absolute_prohibitions": [
        "scary or threatening expressions",
        "sharp objects, weapons",
        "dark shadows, horror atmosphere",
        "photorealistic rendering",
        "adults towering over children",
        "child alone outside at night",
        "blood, wounds, physical pain",
        "complex chaotic backgrounds",
    ],
}


def _make_character_sheet() -> CharacterSheet:
    return CharacterSheet(
        character_id="char_001",
        reference_images={
            "front": "https://replicate.delivery/front.png",
            "three_quarter": "https://replicate.delivery/tq.png",
            "side": "https://replicate.delivery/side.png",
        },
        face_anchor_url=_FACE_ANCHOR_URL,
        identity_prompt_block=_IDENTITY_BLOCK,
        style="watercolor",
        created_at="2026-04-09T12:00:00",
        gender="female",
        age_approx=5,
    )


def _make_replicate_result() -> PredictionResult:
    return PredictionResult(
        prediction_id="pred_scene_001",
        status="succeeded",
        output=["https://replicate.delivery/scene-001.png"],
    )


def _make_mock_replicate() -> AsyncMock:
    mock = AsyncMock()
    mock.run.return_value = _make_replicate_result()
    return mock


def _make_illustration_prompt() -> str:
    return (
        f"{_IDENTITY_BLOCK}, "
        "hugging a brown teddy bear tightly, "
        "soft warm cream tones, cozy indoor lamplight, "
        "simple bedroom with one window, "
        "watercolor style, children's book illustration"
    )


# ---------------------------------------------------------------------------
# 1. 장면 일러스트 생성 성공
# ---------------------------------------------------------------------------


class TestGenerateIllustration:
    """generateIllustration: 프롬프트 + 캐릭터 → 장면 이미지."""

    @pytest.mark.asyncio
    async def test_returns_scene_illustration(self) -> None:
        """성공 시 SceneIllustration 반환 (image_url, scene_id 포함)."""
        service = SceneIllustrationService(
            replicate_client=_make_mock_replicate(),
            art_direction=_ART_DIRECTION,
        )

        result = await service.generate_illustration(
            scene_id="scene_001",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        assert isinstance(result, SceneIllustration)
        assert result.scene_id == "scene_001"
        assert result.image_url.startswith("https://")
        assert result.generation_attempts == 1
        assert result.used_inpainting is False
        assert result.width > 0
        assert result.height > 0

    @pytest.mark.asyncio
    async def test_replicate_called_with_face_anchor(self) -> None:
        """PuLID face_anchor_url이 Replicate 호출에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_002",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        call_args = mock_replicate.run.call_args
        input_params = call_args.args[1]
        assert input_params["main_face_image"] == _FACE_ANCHOR_URL

    @pytest.mark.asyncio
    async def test_replicate_called_once(self) -> None:
        """단일 장면 → Replicate 1회 호출."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_003",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        assert mock_replicate.run.call_count == 1


# ---------------------------------------------------------------------------
# 2. 감정별 시각 조절
# ---------------------------------------------------------------------------


class TestEmotionVisualAdjustment:
    """sceneEmotion에 따라 emotion_to_visual의 palette/lighting 반영."""

    @pytest.mark.asyncio
    async def test_joy_emotion_adds_warm_palette(self) -> None:
        """joy → warm golden highlights 등이 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_joy",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "warm golden highlights" in prompt.lower() or "golden" in prompt.lower()

    @pytest.mark.asyncio
    async def test_sadness_emotion_adds_cool_palette(self) -> None:
        """sadness → blue-gray undertones 등이 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_sad",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="sadness",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "blue-gray" in prompt.lower() or "muted" in prompt.lower()

    @pytest.mark.asyncio
    async def test_fear_emotion_adds_muted_tones(self) -> None:
        """fear → muted cool tones가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_fear",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="fear",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "muted" in prompt.lower()

    @pytest.mark.asyncio
    async def test_anger_emotion_adds_coral_tones(self) -> None:
        """anger → coral-pink가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_anger",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="anger",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "coral" in prompt.lower()

    @pytest.mark.asyncio
    async def test_comfort_emotion_adds_warm_cream(self) -> None:
        """comfort → warm cream and peach가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_comfort",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="comfort",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "peach" in prompt.lower() or "cream" in prompt.lower()

    @pytest.mark.asyncio
    async def test_unknown_emotion_no_crash(self) -> None:
        """emotion_to_visual에 없는 감정 → 에러 없이 기본 생성."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        result = await service.generate_illustration(
            scene_id="scene_unknown",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="surprise",
        )

        assert result.image_url.startswith("https://")


# ---------------------------------------------------------------------------
# 3. 스타일 모디파이어 + 네거티브 프롬프트
# ---------------------------------------------------------------------------


class TestStyleAndNegativePrompt:
    """스타일 positive/negative 모디파이어 + absolute_prohibitions 반영."""

    @pytest.mark.asyncio
    async def test_style_positive_modifiers_in_prompt(self) -> None:
        """watercolor positive modifiers가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_style",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "soft watercolor wash" in prompt.lower()

    @pytest.mark.asyncio
    async def test_clean_digital_style_modifiers(self) -> None:
        """clean_digital 스타일의 positive modifiers가 프롬프트에 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_digital",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="clean_digital",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "clean digital illustration" in prompt.lower()

    @pytest.mark.asyncio
    async def test_negative_prompt_includes_all_8_prohibitions(self) -> None:
        """negative_prompt에 8개 absolute_prohibitions 전부 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_all_neg",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        negative = mock_replicate.run.call_args.args[1]["negative_prompt"]
        for prohibition in _ART_DIRECTION["absolute_prohibitions"]:
            assert prohibition in negative, f"Missing prohibition: {prohibition}"

    @pytest.mark.asyncio
    async def test_negative_prompt_includes_prohibitions(self) -> None:
        """negative_prompt에 스타일 네거티브 + absolute_prohibitions 포함."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_neg",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        input_params = mock_replicate.run.call_args.args[1]
        negative = input_params.get("negative_prompt", "")
        # 스타일 네거티브
        assert "sharp edges" in negative.lower()
        # absolute_prohibitions
        assert "photorealistic" in negative.lower()


# ---------------------------------------------------------------------------
# 3b. 구도 규칙 (composition_rules) 프롬프트 반영
# ---------------------------------------------------------------------------


class TestCompositionRules:
    """composition_rules가 프롬프트에 영어 토큰으로 반영되는지 확인."""

    @pytest.mark.asyncio
    async def test_character_focus_in_prompt(self) -> None:
        """character_focus 40-60% → 프롬프트에 반영."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_comp",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "40" in prompt and "60" in prompt

    @pytest.mark.asyncio
    async def test_max_props_in_prompt(self) -> None:
        """max_props → 프롬프트에 반영."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_props",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        assert "3" in prompt and "prop" in prompt.lower()

    @pytest.mark.asyncio
    async def test_framing_in_prompt(self) -> None:
        """framing 규칙 → 프롬프트에 반영."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_frame",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"].lower()
        assert (
            "center" in prompt
            or "rule-of-thirds" in prompt
            or "rule of thirds" in prompt
        )


class TestPromptOrder:
    """프롬프트 5단계 순서: base(Identity+Action) → Emotion → Composition → Style."""

    @pytest.mark.asyncio
    async def test_emotion_before_style(self) -> None:
        """감정 토큰이 스타일 모디파이어보다 앞에 배치."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_order",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        prompt = mock_replicate.run.call_args.args[1]["prompt"]
        # "warm golden highlights" (emotion) < "soft watercolor wash" (style)
        emotion_idx = prompt.find("warm golden highlights")
        style_idx = prompt.find("soft watercolor wash")
        assert emotion_idx < style_idx, (
            f"Emotion ({emotion_idx}) should be before Style ({style_idx})"
        )


# ---------------------------------------------------------------------------
# 4. PuLID 파라미터
# ---------------------------------------------------------------------------


class TestPulidParameters:
    """PuLID id_weight, 이미지 크기 등 파라미터 검증."""

    @pytest.mark.asyncio
    async def test_default_id_weight(self) -> None:
        """기본 id_weight가 Replicate 호출에 전달."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_iw",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        input_params = mock_replicate.run.call_args.args[1]
        assert "id_weight" in input_params
        assert 0.7 <= input_params["id_weight"] <= 1.0

    @pytest.mark.asyncio
    async def test_custom_id_weight(self) -> None:
        """생성자에서 id_weight 커스텀 설정."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
            id_weight=0.9,
        )

        await service.generate_illustration(
            scene_id="scene_iw2",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        input_params = mock_replicate.run.call_args.args[1]
        assert input_params["id_weight"] == 0.9

    @pytest.mark.asyncio
    async def test_scene_image_larger_than_character_sheet(self) -> None:
        """장면 이미지는 캐릭터 시트(512)보다 큰 해상도."""
        mock_replicate = _make_mock_replicate()
        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        await service.generate_illustration(
            scene_id="scene_size",
            illustration_prompt=_make_illustration_prompt(),
            character=_make_character_sheet(),
            style="watercolor",
            scene_emotion="joy",
        )

        input_params = mock_replicate.run.call_args.args[1]
        assert input_params["width"] >= 768
        assert input_params["height"] >= 768


# ---------------------------------------------------------------------------
# 5. 에러 처리
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Replicate 에러 → SceneIllustrationError 변환."""

    @pytest.mark.asyncio
    async def test_replicate_error_wrapped(self) -> None:
        """ReplicateClientError → SceneIllustrationError."""
        mock_replicate = AsyncMock()
        mock_replicate.run.side_effect = ReplicateClientError(
            code="PREDICTION_FAILED",
            message="모델 실패",
        )

        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        with pytest.raises(SceneIllustrationError) as exc_info:
            await service.generate_illustration(
                scene_id="scene_err",
                illustration_prompt=_make_illustration_prompt(),
                character=_make_character_sheet(),
                style="watercolor",
                scene_emotion="joy",
            )
        assert exc_info.value.code == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_empty_output_raises_error(self) -> None:
        """Replicate가 빈 output 반환 → SceneIllustrationError."""
        mock_replicate = AsyncMock()
        mock_replicate.run.return_value = PredictionResult(
            prediction_id="pred_empty",
            status="succeeded",
            output=None,
        )

        service = SceneIllustrationService(
            replicate_client=mock_replicate,
            art_direction=_ART_DIRECTION,
        )

        with pytest.raises(SceneIllustrationError) as exc_info:
            await service.generate_illustration(
                scene_id="scene_empty",
                illustration_prompt=_make_illustration_prompt(),
                character=_make_character_sheet(),
                style="watercolor",
                scene_emotion="joy",
            )
        assert exc_info.value.code == "EMPTY_OUTPUT"

    @pytest.mark.asyncio
    async def test_invalid_style_raises_error(self) -> None:
        """art_direction에 없는 스타일 → SceneIllustrationError."""
        service = SceneIllustrationService(
            replicate_client=_make_mock_replicate(),
            art_direction=_ART_DIRECTION,
        )

        with pytest.raises(SceneIllustrationError) as exc_info:
            await service.generate_illustration(
                scene_id="scene_bad_style",
                illustration_prompt=_make_illustration_prompt(),
                character=_make_character_sheet(),
                style="pixel_art",
                scene_emotion="joy",
            )
        assert exc_info.value.code == "INVALID_STYLE"
