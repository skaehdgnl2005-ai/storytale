"""S35a — 백엔드 통합 E2E 테스트.

텍스트 파이프라인(S18 StoryOrchestrator) + 일러스트 파이프라인(S26
IllustrationOrchestrator) + DB 저장(S20)을 하나의 플로우로 검증한다.

검증 범위:
    POST /api/v1/stories/generate
      → 텍스트 장면 생성(StoryOrchestrator)
      → 일러스트 장면 생성(IllustrationOrchestrator)
      → Story + StoryPage(text + illustration_url + consistency_score) DB 저장
      → GET /api/v1/stories/{id} 로 전체 결과 조회

전략:
    - 두 파이프라인 모두 AsyncMock 으로 주입(단위/통합 경계).
      실제 LLM/Replicate 호출은 별도 `@pytest.mark.integration` 범위.
    - S22a(얼굴 앵커)/S22b(캐릭터 시트) 파이프라인은 S35a 범위 밖.
      테스트가 사전 구성된 CharacterSheet 를 주입한다.
    - `get_illustration_context_provider` 신규 의존성으로
      라우터가 텍스트-only 모드와 텍스트+일러스트 모드를 구분한다.
"""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from conftest import TestingSessionLocal
from storytale.api.auth_router import get_current_user_id
from storytale.api.stories.router import (
    get_illustration_context_provider,
    get_session_factory,
    get_story_orchestrator,
    job_manager,
)
from storytale.app import app
from storytale.db.models import Story as StoryModel
from storytale.db.models import StoryPage as StoryPageModel
from storytale.illustration.character_sheet_service import (
    CharacterReferenceImages,
    CharacterSheet,
)
from storytale.illustration.consistency_validator import ConsistencyScore
from storytale.illustration.illustration_orchestrator import (
    IllustrationOrchestratorError,
    OrchestratedIllustration,
)
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes
from storytale.interpreter.story_personalizer import PersonalizedScene

# ---------------------------------------------------------------------------
# 픽스처 데이터
# ---------------------------------------------------------------------------

TEST_USER_ID = str(uuid.uuid4())
TEST_CHILD_ID = str(uuid.uuid4())

SAMPLE_SCENE_PLAN = ScenePlan(
    title="하은이의 용기 대모험",
    scenes=[
        PlannedScene(
            scene_id="opening",
            emotion="속상함",
            purpose="현재 감정 공감",
            description="하은이가 게임에서 지고 속상해합니다.",
            child_elements=["comfort_object가 곁에 있음"],
        ),
        PlannedScene(
            scene_id="turning_point",
            emotion="호기심",
            purpose="시선 전환",
            description="토끼가 넘어졌다가 다시 일어나는 모습을 봅니다.",
            child_elements=["favorite_animal이 비유로 등장"],
        ),
        PlannedScene(
            scene_id="resolution",
            emotion="용기",
            purpose="감정 전환",
            description="하은이도 다시 도전합니다.",
            child_elements=["comfort_object 응원"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 응원하는",
        avoid=["승패를 강조하는 표현"],
        repetition_motif="넘어져도 괜찮아",
    ),
)

PERSONALIZED_SCENES = [
    PersonalizedScene(
        scene_id="opening",
        page_number=1,
        text="하은이가 블록 쌓기 게임에서 졌어요.",
        illustration_prompt=(
            "A young girl looking sad after losing a block game, warm lighting"
        ),
    ),
    PersonalizedScene(
        scene_id="turning_point",
        page_number=2,
        text="그때, 토끼 한 마리가 풀밭에서 넘어졌어요.",
        illustration_prompt="A rabbit stumbling then rising in a sunlit meadow",
    ),
    PersonalizedScene(
        scene_id="resolution",
        page_number=3,
        text="하은이도 용기를 내어 다시 도전했어요.",
        illustration_prompt="The girl bravely trying again with a warm smile",
    ),
]


def _make_fake_character_sheet() -> CharacterSheet:
    """E2E 테스트에서 주입하는 캐릭터 시트 픽스처.

    S22a/S22b 파이프라인(사진 업로드 → 얼굴 앵커 → 멀티뷰 시트)은 S35a
    범위 밖이므로 사전 구성된 CharacterSheet 를 테스트가 직접 주입한다.
    """
    return CharacterSheet(
        character_id="char-test-001",
        reference_images=CharacterReferenceImages(
            front="https://fixtures.example/char/front.png",
            three_quarter="https://fixtures.example/char/three_quarter.png",
            side="https://fixtures.example/char/side.png",
        ),
        face_anchor_url="https://fixtures.example/char/anchor.png",
        identity_prompt_block=(
            "a young girl with round face, short black hair, rosy cheeks"
        ),
        style="watercolor",
        created_at="2026-04-11T00:00:00+00:00",
        gender="female",
        age_approx=4,
    )


def _make_passing_score(composite: float = 0.86) -> ConsistencyScore:
    return ConsistencyScore(
        clip_score=0.85,
        dino_score=0.88,
        composite_score=composite,
        passed=True,
        failure_reason=None,
    )


VALID_REQUEST_BODY: dict[str, Any] = {
    "confirmed_plan": SAMPLE_SCENE_PLAN.model_dump(),
    "child": {
        "child_id": TEST_CHILD_ID,
        "name": "하은",
        "age": 4,
        "gender": "female",
        "comfort_object": "토니(곰 인형)",
        "friend_name": "서준",
        "favorite_animal": "토끼",
    },
    "style": "watercolor",
}


# ---------------------------------------------------------------------------
# 픽스처: 텍스트 오케스트레이터 모킹 (S18 패턴)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_story_orchestrator() -> AsyncMock:
    """StoryOrchestrator 를 모킹 — PersonalizedScene 을 순차 yield."""
    orch = AsyncMock()

    async def fake_generate_story(confirmed_plan, child, style):
        for scene in PERSONALIZED_SCENES:
            await asyncio.sleep(0)
            yield scene

    orch.generate_story = fake_generate_story
    return orch


# ---------------------------------------------------------------------------
# 픽스처: 일러스트 오케스트레이터 모킹 (S26 패턴)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_illustration_orchestrator() -> AsyncMock:
    """IllustrationOrchestrator 를 모킹 — OrchestratedIllustration 순차 yield.

    테스트가 전달한 scenes 를 그대로 순회하며 각 scene_id 에 대해
    S3 스타일 URL 과 passing score 를 부여한 결과를 반환한다.
    """
    orch = AsyncMock()

    async def fake_generate_all_illustrations(
        story_id: str,
        scenes: list[PersonalizedScene],
        character: CharacterSheet,
        style: str,
        scene_emotions: dict[str, str] | None = None,
    ):
        for scene in scenes:
            await asyncio.sleep(0)
            yield OrchestratedIllustration(
                scene_id=scene.scene_id,
                image_url=(
                    "https://s3.fixtures.example/stories/"
                    f"{story_id}/scenes/{scene.scene_id}.png"
                ),
                consistency_score=_make_passing_score(),
                generation_attempts=1,
                used_inpainting=False,
                width=768,
                height=768,
            )

    orch.generate_all_illustrations = fake_generate_all_illustrations
    # generate_all_illustrations 에 전달된 인자 추적용 스파이
    orch._spy_calls = []
    return orch


# ---------------------------------------------------------------------------
# 픽스처: 테스트 전후 스토리 테이블 정리
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _clean_stories_table():
    async with TestingSessionLocal() as session:
        await session.execute(delete(StoryPageModel))
        await session.execute(delete(StoryModel))
        await session.commit()
    yield
    async with TestingSessionLocal() as session:
        await session.execute(delete(StoryPageModel))
        await session.execute(delete(StoryModel))
        await session.commit()


# ---------------------------------------------------------------------------
# 픽스처: 클라이언트 (텍스트 + 일러스트 통합 모드)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client_with_illustration(
    mock_story_orchestrator: AsyncMock,
    mock_illustration_orchestrator: AsyncMock,
):
    """텍스트 + 일러스트 파이프라인 통합 모드 httpx AsyncClient.

    - get_story_orchestrator → 텍스트 mock
    - get_illustration_context_provider → (일러스트 mock, 픽스처 CharacterSheet)
    - get_session_factory → 테스트 DB
    - get_current_user_id → 고정 UUID (인증 우회)
    """
    character_sheet = _make_fake_character_sheet()

    async def fake_context_provider(
        child, style: str
    ) -> tuple[AsyncMock, CharacterSheet]:
        return mock_illustration_orchestrator, character_sheet

    app.dependency_overrides[get_story_orchestrator] = lambda: mock_story_orchestrator
    app.dependency_overrides[get_illustration_context_provider] = lambda: (
        fake_context_provider
    )
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    job_manager.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_story_orchestrator, None)
    app.dependency_overrides.pop(get_illustration_context_provider, None)
    app.dependency_overrides.pop(get_session_factory, None)
    app.dependency_overrides.pop(get_current_user_id, None)
    job_manager.clear()


# ---------------------------------------------------------------------------
# 픽스처: 클라이언트 (텍스트-only 모드 = S20 하위 호환)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client_text_only(mock_story_orchestrator: AsyncMock):
    """일러스트 파이프라인을 주입하지 않은 기존 텍스트-only 모드.

    S35a 가 S19/S20 기존 동작에 회귀를 일으키지 않는지 같은 파일에서 검증.
    """
    app.dependency_overrides[get_story_orchestrator] = lambda: mock_story_orchestrator
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    # get_illustration_context_provider 는 override 하지 않음 → None 반환 → 텍스트-only
    job_manager.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_story_orchestrator, None)
    app.dependency_overrides.pop(get_session_factory, None)
    app.dependency_overrides.pop(get_current_user_id, None)
    job_manager.clear()


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


async def _generate_and_wait(client: AsyncClient) -> str:
    """스토리 생성 → 완료 대기 → story_id 반환."""
    resp = await client.post("/api/v1/stories/generate", json=VALID_REQUEST_BODY)
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]

    final_data: dict[str, Any] | None = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        resp = await client.get(f"/api/v1/stories/jobs/{job_id}")
        final_data = resp.json()
        if final_data["status"] in ("completed", "failed"):
            break

    assert final_data is not None
    assert final_data["status"] == "completed", (
        f"Job did not complete: status={final_data['status']} "
        f"error={final_data.get('error')}"
    )
    story_id = final_data["story_id"]
    assert story_id, "story_id should be set on completion"
    return story_id


# ===========================================================================
# 1. 해피 패스: 텍스트 + 일러스트 통합 E2E
# ===========================================================================


class TestTextIllustrationE2E:
    @pytest.mark.asyncio()
    async def test_full_pipeline_saves_text_and_illustrations(
        self, client_with_illustration: AsyncClient
    ) -> None:
        """POST /generate → 텍스트+일러스트 생성 → DB 에 양쪽 모두 저장."""
        story_id = await _generate_and_wait(client_with_illustration)

        # DB 검증: 모든 페이지가 text + illustration_url + consistency_score
        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryPageModel)
                .where(StoryPageModel.story_id == uuid.UUID(story_id))
                .order_by(StoryPageModel.page_number)
            )
            pages = result.scalars().all()

        assert len(pages) == 3
        for page in pages:
            assert page.text, "text must be non-empty"
            assert page.illustration_url is not None, (
                f"page {page.scene_id} illustration_url missing"
            )
            assert "s3.fixtures.example" in page.illustration_url
            assert page.consistency_score is not None
            assert page.consistency_score >= 0.80

        # page → scene_id 매핑 확인 (순서 포함)
        assert [p.scene_id for p in pages] == [
            "opening",
            "turning_point",
            "resolution",
        ]

    @pytest.mark.asyncio()
    async def test_get_story_returns_illustration_urls(
        self, client_with_illustration: AsyncClient
    ) -> None:
        """GET /stories/{id} 응답의 pages 가 illustration_url 을 포함한다."""
        story_id = await _generate_and_wait(client_with_illustration)

        resp = await client_with_illustration.get(f"/api/v1/stories/{story_id}")
        assert resp.status_code == 200
        story = resp.json()

        assert story["page_count"] == 3
        assert len(story["pages"]) == 3
        for page in story["pages"]:
            assert page["illustration_url"] is not None
            assert page["illustration_url"].startswith("https://")

    @pytest.mark.asyncio()
    async def test_illustration_story_id_matches_db_story_id(
        self,
        client_with_illustration: AsyncClient,
        mock_illustration_orchestrator: AsyncMock,
    ) -> None:
        """일러스트 파이프라인이 받은 story_id 가 DB 에 저장된 story.id 와 일치한다.

        → S3 키 `stories/{story_id}/scenes/{scene_id}.png` 가
           DB 의 스토리와 대응되어 후속 조회/삭제 시 일치한다.
        """
        # generate_all_illustrations 호출 시 story_id 를 캡처
        captured: dict[str, str] = {}
        real_fn = mock_illustration_orchestrator.generate_all_illustrations

        async def capturing(story_id, scenes, character, style, scene_emotions=None):
            captured["story_id"] = story_id
            async for item in real_fn(
                story_id=story_id,
                scenes=scenes,
                character=character,
                style=style,
                scene_emotions=scene_emotions,
            ):
                yield item

        mock_illustration_orchestrator.generate_all_illustrations = capturing

        db_story_id = await _generate_and_wait(client_with_illustration)

        assert captured.get("story_id") == db_story_id

    @pytest.mark.asyncio()
    async def test_scene_emotions_forwarded_from_plan(
        self,
        client_with_illustration: AsyncClient,
        mock_illustration_orchestrator: AsyncMock,
    ) -> None:
        """ScenePlan 의 emotion 이 일러스트 오케스트레이터에 scene_emotions 로 전달."""
        captured: dict[str, Any] = {}
        real_fn = mock_illustration_orchestrator.generate_all_illustrations

        async def capturing(story_id, scenes, character, style, scene_emotions=None):
            captured["scene_emotions"] = scene_emotions
            async for item in real_fn(
                story_id=story_id,
                scenes=scenes,
                character=character,
                style=style,
                scene_emotions=scene_emotions,
            ):
                yield item

        mock_illustration_orchestrator.generate_all_illustrations = capturing

        await _generate_and_wait(client_with_illustration)

        emotions = captured.get("scene_emotions")
        assert emotions is not None
        assert emotions["opening"] == "속상함"
        assert emotions["turning_point"] == "호기심"
        assert emotions["resolution"] == "용기"


# ===========================================================================
# 2. 일러스트 파이프라인 실패 → 그레이스풀 폴백
# ===========================================================================


class TestIllustrationFailureGraceful:
    @pytest.mark.asyncio()
    async def test_illustration_error_marks_job_failed_but_text_preserved(
        self,
        client_with_illustration: AsyncClient,
        mock_illustration_orchestrator: AsyncMock,
    ) -> None:
        """일러스트 파이프라인 에러 → job 은 failed, 단 장면 텍스트는 이미 수집됨.

        일러스트 에러는 전체 스토리를 중단시키지만, 장면 텍스트는 생성 중
        이미 yield 되어 job.scenes 에 누적돼 있어야 한다(부분 결과 보존).
        """

        async def failing_all(story_id, scenes, character, style, scene_emotions=None):
            yield OrchestratedIllustration(
                scene_id="opening",
                image_url="https://s3.fixtures.example/partial.png",
                consistency_score=_make_passing_score(),
                generation_attempts=1,
                used_inpainting=False,
                width=768,
                height=768,
            )
            raise IllustrationOrchestratorError(
                code="SCENE_GENERATION_FAILED",
                message="fake illustration failure",
            )

        mock_illustration_orchestrator.generate_all_illustrations = failing_all

        resp = await client_with_illustration.post(
            "/api/v1/stories/generate", json=VALID_REQUEST_BODY
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        data: dict[str, Any] | None = None
        for _ in range(40):
            await asyncio.sleep(0.1)
            resp = await client_with_illustration.get(f"/api/v1/stories/jobs/{job_id}")
            data = resp.json()
            if data["status"] in ("completed", "failed"):
                break

        assert data is not None
        assert data["status"] == "failed"
        assert data["error"] is not None
        # 텍스트는 모두 수집된 상태 (일러스트 단계 진입 전)
        assert len(data["scenes"]) == 3


# ===========================================================================
# 3. 텍스트-only 하위 호환 (S19/S20 회귀 방지)
# ===========================================================================


class TestTextOnlyBackwardsCompat:
    @pytest.mark.asyncio()
    async def test_text_only_mode_still_saves_story(
        self, client_text_only: AsyncClient
    ) -> None:
        """illustration provider 가 None 이면 텍스트만 생성하고 DB 에 저장."""
        story_id = await _generate_and_wait(client_text_only)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryPageModel)
                .where(StoryPageModel.story_id == uuid.UUID(story_id))
                .order_by(StoryPageModel.page_number)
            )
            pages = result.scalars().all()

        assert len(pages) == 3
        for page in pages:
            assert page.text
            assert page.illustration_url is None
            assert page.consistency_score is None

    @pytest.mark.asyncio()
    async def test_text_only_get_story_has_null_illustration_urls(
        self, client_text_only: AsyncClient
    ) -> None:
        """텍스트-only 모드의 GET /stories/{id} 응답은 illustration_url 이 null."""
        story_id = await _generate_and_wait(client_text_only)

        resp = await client_text_only.get(f"/api/v1/stories/{story_id}")
        assert resp.status_code == 200
        for page in resp.json()["pages"]:
            assert page["illustration_url"] is None
