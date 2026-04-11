"""IllustrationOrchestrator 테스트 (S26).

TDD RED: 오케스트레이터 전체 플로우 테스트.
- 장면별 일러스트 생성 → 일관성 검증 → 재생성/인페인팅 → S3 업로드
- AsyncGenerator로 장면별 yield
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from storytale.illustration.character_sheet_service import CharacterSheet
from storytale.illustration.consistency_validator import ConsistencyScore
from storytale.illustration.inpainting_service import InpaintingResult
from storytale.illustration.scene_illustration_service import SceneIllustration
from storytale.interpreter.story_personalizer import PersonalizedScene

# ---------------------------------------------------------------------------
# 헬퍼: 테스트 픽스처 팩토리
# ---------------------------------------------------------------------------


def _make_character_sheet(**overrides: object) -> CharacterSheet:
    defaults = {
        "character_id": "char-001",
        "reference_images": {"front": "https://s3/front.png"},
        "face_anchor_url": "https://s3/anchor.png",
        "identity_prompt_block": "a young girl with round face, short black hair",
        "style": "watercolor",
        "created_at": "2026-04-10T00:00:00",
        "gender": "female",
        "age_approx": 5,
    }
    defaults.update(overrides)
    return CharacterSheet(**defaults)


def _make_scene(scene_id: str = "scene_1", page: int = 1) -> PersonalizedScene:
    return PersonalizedScene(
        scene_id=scene_id,
        page_number=page,
        text="토끼가 숲에서 놀아요.",
        illustration_prompt="a little girl playing with a rabbit in the forest",
    )


def _passing_score(**overrides: object) -> ConsistencyScore:
    defaults = {
        "clip_score": 0.85,
        "dino_score": 0.88,
        "composite_score": 0.868,
        "passed": True,
        "failure_reason": None,
    }
    defaults.update(overrides)
    return ConsistencyScore(**defaults)


def _failing_score(reason: str = "face_drift", **overrides: object) -> ConsistencyScore:
    defaults = {
        "clip_score": 0.70,
        "dino_score": 0.60,
        "composite_score": 0.64,
        "passed": False,
        "failure_reason": reason,
    }
    defaults.update(overrides)
    return ConsistencyScore(**defaults)


def _scene_illustration(scene_id: str = "scene_1") -> SceneIllustration:
    return SceneIllustration(
        scene_id=scene_id,
        image_url="https://replicate/output.png",
        generation_attempts=1,
        used_inpainting=False,
        width=768,
        height=768,
    )


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def scene_service() -> AsyncMock:
    svc = AsyncMock()
    svc.generate_illustration = AsyncMock(
        return_value=_scene_illustration("scene_1"),
    )
    return svc


@pytest.fixture()
def validator() -> AsyncMock:
    v = AsyncMock()
    v.validate = AsyncMock(return_value=_passing_score())
    return v


@pytest.fixture()
def inpainting() -> AsyncMock:
    svc = AsyncMock()
    svc.correct_character_region = AsyncMock()
    return svc


@pytest.fixture()
def storage() -> AsyncMock:
    svc = AsyncMock()
    svc.upload = AsyncMock(return_value="https://s3/final.png")
    return svc


@pytest.fixture(autouse=True)
def _mock_httpx():
    """httpx.AsyncClient를 모킹 — Replicate URL에서 이미지 다운로드를 시뮬레이션."""
    mock_response = MagicMock()
    mock_response.content = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "storytale.illustration.illustration_orchestrator.httpx.AsyncClient",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.fixture()
def orchestrator(
    scene_service: AsyncMock,
    validator: AsyncMock,
    inpainting: AsyncMock,
    storage: AsyncMock,
):
    from storytale.illustration.illustration_orchestrator import (
        IllustrationOrchestrator,
    )

    return IllustrationOrchestrator(
        scene_illustration_service=scene_service,
        consistency_validator=validator,
        inpainting_service=inpainting,
        image_storage_service=storage,
    )


async def _collect(async_gen):
    """AsyncGenerator → list 변환 헬퍼."""
    results = []
    async for item in async_gen:
        results.append(item)
    return results


# ===================================================================
# 1. 해피 패스: 모든 장면이 첫 시도에 검증 통과
# ===================================================================


class TestHappyPath:
    @pytest.mark.asyncio()
    async def test_single_scene_passes_on_first_try(
        self, orchestrator, scene_service, validator, storage
    ):
        """단일 장면이 첫 시도에 통과하면 1개 결과를 yield한다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert len(results) == 1
        result = results[0]
        assert result.scene_id == "scene_1"
        assert result.consistency_score.passed is True
        assert result.generation_attempts == 1
        assert result.used_inpainting is False

    @pytest.mark.asyncio()
    async def test_multiple_scenes_yield_in_order(
        self, orchestrator, scene_service, validator, storage
    ):
        """여러 장면이 순서대로 yield된다."""
        character = _make_character_sheet()
        scenes = [_make_scene(f"scene_{i}", i) for i in range(1, 4)]

        scene_service.generate_illustration = AsyncMock(
            side_effect=[_scene_illustration(f"scene_{i}") for i in range(1, 4)]
        )

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert len(results) == 3
        assert [r.scene_id for r in results] == [
            "scene_1",
            "scene_2",
            "scene_3",
        ]

    @pytest.mark.asyncio()
    async def test_s3_upload_with_correct_key(
        self, orchestrator, scene_service, validator, storage
    ):
        """생성된 이미지가 올바른 S3 키로 업로드된다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        storage.upload.assert_called_once()
        call_args = storage.upload.call_args
        s3_key = call_args[1].get("key") or call_args[0][1]
        assert "story-001" in s3_key
        assert "scene_1" in s3_key

    @pytest.mark.asyncio()
    async def test_s3_upload_receives_bytes_not_url(
        self, orchestrator, scene_service, validator, storage
    ):
        """S3 업로드 시 이미지 URL이 아닌 다운로드된 bytes를 전달해야 한다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        storage.upload.assert_called_once()
        first_arg = storage.upload.call_args[0][0]
        assert isinstance(first_arg, bytes)

    @pytest.mark.asyncio()
    async def test_final_image_url_is_s3_url(
        self, orchestrator, scene_service, validator, storage
    ):
        """최종 결과의 image_url은 S3 URL이다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert results[0].image_url == "https://s3/final.png"


# ===================================================================
# 2. 재생성: 검증 실패 → 재시도 성공
# ===================================================================


class TestRetry:
    @pytest.mark.asyncio()
    async def test_retry_on_first_failure_succeeds(
        self, orchestrator, scene_service, validator, inpainting, storage
    ):
        """1차 검증 실패 → 2차 시도에서 통과."""
        validator.validate = AsyncMock(
            side_effect=[_failing_score("face_drift"), _passing_score()]
        )
        scene_service.generate_illustration = AsyncMock(
            side_effect=[
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
            ]
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert len(results) == 1
        assert results[0].generation_attempts == 2
        assert results[0].used_inpainting is False
        assert results[0].consistency_score.passed is True
        inpainting.correct_character_region.assert_not_called()

    @pytest.mark.asyncio()
    async def test_retry_with_id_weight_increase_on_second_failure(
        self, orchestrator, scene_service, validator, inpainting, storage
    ):
        """2차 연속 실패 → id_weight 상향 후 3차 재생성 → 통과."""
        validator.validate = AsyncMock(
            side_effect=[
                _failing_score("face_drift"),
                _failing_score("face_drift"),
                _passing_score(),
            ]
        )
        scene_service.generate_illustration = AsyncMock(
            side_effect=[
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
            ]
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert len(results) == 1
        assert results[0].generation_attempts == 3
        assert results[0].used_inpainting is False
        assert results[0].consistency_score.passed is True

        # attempt 1: id_weight=None (기본값), attempt 2+: id_weight=0.95 (부스트)
        calls = scene_service.generate_illustration.call_args_list
        assert calls[0][1].get("id_weight") is None
        assert calls[1][1].get("id_weight") == pytest.approx(0.95)
        assert calls[2][1].get("id_weight") == pytest.approx(0.95)


# ===================================================================
# 3. 인페인팅 폴백: 3회 재생성 모두 실패 → 인페인팅
# ===================================================================


class TestInpaintingFallback:
    @pytest.mark.asyncio()
    async def test_inpainting_triggered_after_three_generation_failures(
        self, orchestrator, scene_service, validator, inpainting, storage
    ):
        """3회 재생성 모두 실패 → 인페인팅 폴백 → 통과."""
        failing = _failing_score("face_drift")
        passing = _passing_score()

        validator.validate = AsyncMock(side_effect=[failing, failing, failing])
        scene_service.generate_illustration = AsyncMock(
            side_effect=[
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
            ]
        )
        inpainting.correct_character_region = AsyncMock(
            return_value=InpaintingResult(
                corrected_image_url="https://replicate/inpainted.png",
                final_score=passing,
            )
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        assert len(results) == 1
        assert results[0].used_inpainting is True
        assert results[0].consistency_score.passed is True
        inpainting.correct_character_region.assert_called_once()

    @pytest.mark.asyncio()
    async def test_inpainting_failure_yields_best_result(
        self, orchestrator, scene_service, validator, inpainting, storage
    ):
        """인페인팅도 실패하면 가장 나은 결과를 yield한다 (생성 중단 방지)."""
        failing = _failing_score("face_drift")
        inpaint_failing = _failing_score(
            "face_drift", composite_score=0.72, passed=False
        )

        validator.validate = AsyncMock(side_effect=[failing, failing, failing])
        scene_service.generate_illustration = AsyncMock(
            side_effect=[
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
                _scene_illustration("scene_1"),
            ]
        )
        inpainting.correct_character_region = AsyncMock(
            return_value=InpaintingResult(
                corrected_image_url="https://replicate/inpainted.png",
                final_score=inpaint_failing,
            )
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        results = await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            )
        )

        # 인페인팅도 실패해도 결과를 yield한다 (전체 책 생성을 중단하지 않음)
        assert len(results) == 1
        assert results[0].used_inpainting is True
        assert results[0].consistency_score.passed is False


# ===================================================================
# 4. scene_emotions 매핑
# ===================================================================


class TestSceneEmotions:
    @pytest.mark.asyncio()
    async def test_scene_emotion_passed_to_service(
        self, orchestrator, scene_service, validator, storage
    ):
        """scene_emotions 매핑이 SceneIllustrationService에 전달된다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
                scene_emotions={"scene_1": "joy"},
            )
        )

        call_kwargs = scene_service.generate_illustration.call_args[1]
        assert call_kwargs["scene_emotion"] == "joy"

    @pytest.mark.asyncio()
    async def test_missing_emotion_defaults_to_neutral(
        self, orchestrator, scene_service, validator, storage
    ):
        """scene_emotions에 없는 장면은 기본값 'neutral'로 전달된다."""
        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        await _collect(
            orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
                scene_emotions={},
            )
        )

        call_kwargs = scene_service.generate_illustration.call_args[1]
        assert call_kwargs["scene_emotion"] == "neutral"


# ===================================================================
# 5. 에러 처리
# ===================================================================


class TestErrorHandling:
    @pytest.mark.asyncio()
    async def test_scene_generation_error_propagates(
        self, orchestrator, scene_service, validator, storage
    ):
        """SceneIllustrationService 에러가 전파된다."""
        from storytale.illustration.scene_illustration_service import (
            SceneIllustrationError,
        )

        scene_service.generate_illustration = AsyncMock(
            side_effect=SceneIllustrationError(
                code="GENERATION_FAILED",
                message="Replicate API 호출 실패",
            )
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1")]

        from storytale.illustration.illustration_orchestrator import (
            IllustrationOrchestratorError,
        )

        with pytest.raises(IllustrationOrchestratorError) as exc_info:
            await _collect(
                orchestrator.generate_all_illustrations(
                    story_id="story-001",
                    scenes=scenes,
                    character=character,
                    style="watercolor",
                )
            )

        assert exc_info.value.code == "SCENE_GENERATION_FAILED"
        assert "scene_1" in str(exc_info.value)

    @pytest.mark.asyncio()
    async def test_partial_success_yields_completed_scenes(
        self, orchestrator, scene_service, validator, storage
    ):
        """첫 장면 성공 후 두 번째 장면 에러 → 첫 장면 결과는 yield됨."""
        from storytale.illustration.scene_illustration_service import (
            SceneIllustrationError,
        )

        scene_service.generate_illustration = AsyncMock(
            side_effect=[
                _scene_illustration("scene_1"),
                SceneIllustrationError(
                    code="GENERATION_FAILED",
                    message="fail",
                ),
            ]
        )

        character = _make_character_sheet()
        scenes = [_make_scene("scene_1", 1), _make_scene("scene_2", 2)]

        from storytale.illustration.illustration_orchestrator import (
            IllustrationOrchestratorError,
        )

        results = []
        with pytest.raises(IllustrationOrchestratorError):
            async for item in orchestrator.generate_all_illustrations(
                story_id="story-001",
                scenes=scenes,
                character=character,
                style="watercolor",
            ):
                results.append(item)

        # 첫 장면은 이미 yield됨
        assert len(results) == 1
        assert results[0].scene_id == "scene_1"
