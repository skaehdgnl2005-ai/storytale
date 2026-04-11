"""S20 — 스토리 저장/조회 API 테스트.

생성 완료 → Story + StoryPage DB 저장 → GET /stories/{id}, GET /stories 목록 조회.
"""

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from conftest import TestingSessionLocal
from storytale.api.auth_router import get_current_user_id
from storytale.api.stories.router import (
    get_session_factory,
    get_story_orchestrator,
    job_manager,
)
from storytale.app import app
from storytale.db.models import Story as StoryModel
from storytale.db.models import StoryPage as StoryPageModel
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
        illustration_prompt="A young girl looking sad after losing a game...",
    ),
    PersonalizedScene(
        scene_id="turning_point",
        page_number=2,
        text="그때, 토끼 한 마리가 풀밭에서 넘어졌어요.",
        illustration_prompt="A rabbit falling then getting up in a meadow...",
    ),
    PersonalizedScene(
        scene_id="resolution",
        page_number=3,
        text="하은이도 용기를 내어 다시 도전했어요.",
        illustration_prompt="The girl bravely trying again with a smile...",
    ),
]

VALID_REQUEST_BODY = {
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
    "user_id": TEST_USER_ID,
}


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_orchestrator():
    """StoryOrchestrator를 모킹."""
    orch = AsyncMock()

    async def fake_generate_story(confirmed_plan, child, style):
        for scene in PERSONALIZED_SCENES:
            await asyncio.sleep(0)
            yield scene

    orch.generate_story = fake_generate_story
    return orch


@pytest_asyncio.fixture(autouse=True)
async def _clean_stories_table():
    """각 테스트 전후 스토리 테이블 정리."""
    async with TestingSessionLocal() as session:
        await session.execute(delete(StoryPageModel))
        await session.execute(delete(StoryModel))
        await session.commit()
    yield
    async with TestingSessionLocal() as session:
        await session.execute(delete(StoryPageModel))
        await session.execute(delete(StoryModel))
        await session.commit()


@pytest_asyncio.fixture()
async def client(mock_orchestrator):
    """httpx AsyncClient with mocked dependencies + 인증 우회."""
    app.dependency_overrides[get_story_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
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


async def _generate_and_wait(client: AsyncClient) -> str:
    """스토리 생성 → 완료 대기 → story_id 반환."""
    resp = await client.post("/api/v1/stories/generate", json=VALID_REQUEST_BODY)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    for _ in range(20):
        await asyncio.sleep(0.1)
        resp = await client.get(f"/api/v1/stories/jobs/{job_id}")
        data = resp.json()
        if data["status"] == "completed":
            return data["story_id"]

    msg = f"Job {job_id} did not complete in time: {data['status']}"
    raise AssertionError(msg)


# ---------------------------------------------------------------------------
# 생성 → DB 저장 테스트
# ---------------------------------------------------------------------------


class TestStorySaving:
    @pytest.mark.asyncio()
    async def test_completed_job_has_story_id(self, client: AsyncClient) -> None:
        """완료된 잡은 story_id를 포함한다."""
        story_id = await _generate_and_wait(client)
        assert story_id is not None
        assert len(story_id) > 0

    @pytest.mark.asyncio()
    async def test_story_saved_to_db(self, client: AsyncClient) -> None:
        """생성 완료 후 Story 레코드가 DB에 존재한다."""
        story_id = await _generate_and_wait(client)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryModel).where(StoryModel.id == uuid.UUID(story_id))
            )
            story = result.scalar_one_or_none()
            assert story is not None
            assert story.status == "completed"
            assert story.style == "watercolor"

    @pytest.mark.asyncio()
    async def test_story_pages_saved_to_db(self, client: AsyncClient) -> None:
        """생성된 장면이 StoryPage로 저장된다."""
        story_id = await _generate_and_wait(client)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryPageModel)
                .where(StoryPageModel.story_id == uuid.UUID(story_id))
                .order_by(StoryPageModel.page_number)
            )
            pages = result.scalars().all()
            assert len(pages) == 3
            assert pages[0].scene_id == "opening"
            assert pages[0].text == "하은이가 블록 쌓기 게임에서 졌어요."
            assert pages[2].scene_id == "resolution"


# ---------------------------------------------------------------------------
# GET /stories/{story_id} 테스트
# ---------------------------------------------------------------------------


class TestGetStory:
    @pytest.mark.asyncio()
    async def test_get_story_returns_detail(self, client: AsyncClient) -> None:
        """스토리 상세 조회 → 200 + pages 포함."""
        story_id = await _generate_and_wait(client)

        resp = await client.get(f"/api/v1/stories/{story_id}")
        assert resp.status_code == 200

        story = resp.json()
        assert story["id"] == story_id
        assert story["title"] == "하은이의 용기 대모험"
        assert story["status"] == "completed"
        assert story["style"] == "watercolor"
        assert story["page_count"] == 3
        assert len(story["pages"]) == 3

    @pytest.mark.asyncio()
    async def test_get_story_pages_ordered(self, client: AsyncClient) -> None:
        """페이지가 page_number 순으로 정렬된다."""
        story_id = await _generate_and_wait(client)

        resp = await client.get(f"/api/v1/stories/{story_id}")
        pages = resp.json()["pages"]
        page_numbers = [p["page_number"] for p in pages]
        assert page_numbers == [1, 2, 3]
        assert pages[0]["scene_id"] == "opening"
        assert pages[2]["scene_id"] == "resolution"

    @pytest.mark.asyncio()
    async def test_get_story_not_found(self, client: AsyncClient) -> None:
        """존재하지 않는 story_id → 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/stories/{fake_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_get_story_invalid_id(self, client: AsyncClient) -> None:
        """유효하지 않은 UUID → 404."""
        resp = await client.get("/api/v1/stories/not-a-uuid")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /stories 목록 테스트
# ---------------------------------------------------------------------------


class TestListStories:
    @pytest.mark.asyncio()
    async def test_list_stories_empty(self, client: AsyncClient) -> None:
        """스토리가 없으면 빈 목록."""
        resp = await client.get("/api/v1/stories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio()
    async def test_list_stories_has_items(self, client: AsyncClient) -> None:
        """생성된 스토리가 목록에 포함된다."""
        await _generate_and_wait(client)

        resp = await client.get("/api/v1/stories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "하은이의 용기 대모험"
        assert data["items"][0]["page_count"] == 3

    @pytest.mark.asyncio()
    async def test_list_stories_pagination(self, client: AsyncClient) -> None:
        """limit/offset 페이지네이션."""
        await _generate_and_wait(client)
        await _generate_and_wait(client)

        resp = await client.get("/api/v1/stories?limit=1&offset=0")
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2
        assert data["limit"] == 1
        assert data["offset"] == 0
