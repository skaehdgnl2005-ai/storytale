"""S34 — DELETE /api/v1/stories/{story_id} 엔드포인트 테스트.

내 서재(LibraryScreen)에서 사용자가 스토리를 삭제할 때 호출하는 엔드포인트.
S20이 노출한 GET /stories, GET /stories/{id} 와 같은 라우터에 추가된다.

설계:
- 인증/소유자 검증은 실제 로그인 + DB 직접 시드로 통합 검증 (S30a/S31a 패턴).
- Story 모델의 pages 관계는 `cascade="all, delete-orphan"` 으로 선언되어 있어
  ORM 레벨에서 자식 StoryPage 들이 함께 삭제된다 (models.py::Story.pages).
- 응답: 204 No Content (api-conventions.md DELETE 관례 + 본문 없음).
- 소유자 불일치/존재하지 않음/유효하지 않은 UUID 모두 404 로 동일 처리
  (S20 패턴: 정보 노출 방지).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from conftest import TestingSessionLocal
from storytale.app import app
from storytale.auth.schemas import SocialUserInfo
from storytale.db.models import Story as StoryModel
from storytale.db.models import StoryPage as StoryPageModel

BASE_URL = "http://test/api/v1"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _clean_stories_table():
    """각 테스트 전후 스토리 테이블 정리 (test_s20 패턴)."""
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
async def client():
    """의존성 오버라이드 없는 순수 AsyncClient (실제 인증 사용)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


async def _login(client: AsyncClient, email_prefix: str = "delete-test") -> str:
    """소셜 로그인 → JWT access token 반환 (test_s30a 패턴)."""
    user_info = SocialUserInfo(
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
        provider="google",
    )
    with patch(
        "storytale.api.auth_router.AuthService._get_social_user_info",
        new_callable=AsyncMock,
        return_value=user_info,
    ):
        resp = await client.post(
            "/auth/login",
            json={"provider": "google", "auth_code": "test-code"},
        )
    return resp.json()["access_token"]


async def _get_user_id(client: AsyncClient, header: dict) -> str:
    """JWT 로 GET /auth/me 호출 → user_id 반환."""
    resp = await client.get("/auth/me", headers=header)
    assert resp.status_code == 200, resp.text
    return resp.json()["user_id"]


@pytest_asyncio.fixture()
async def auth_header(client: AsyncClient):
    token = await _login(client, "delete-owner")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def other_auth_header(client: AsyncClient):
    token = await _login(client, "delete-other")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def child_id(client: AsyncClient, auth_header: dict) -> str:
    """auth_header 사용자가 소유한 ChildProfile 생성 → child_id 반환."""
    profile = {
        "name": "하은",
        "age": 4,
        "gender": "female",
        "comfort_object": "토니 곰인형",
        "friend_name": "민준",
        "favorite_animal": "토끼",
    }
    resp = await client.post("/profiles", json=profile, headers=auth_header)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _seed_story(
    user_id: str,
    child_id: str,
    title: str = "하은이의 용기 대모험",
    page_count: int = 3,
) -> str:
    """DB 에 Story + StoryPage 행을 직접 삽입 → story_id 반환.

    DELETE 테스트 본질에 집중하기 위해 generate 잡 플로우를 우회한다.
    """
    story_uuid = uuid.uuid4()
    async with TestingSessionLocal() as session:
        story = StoryModel(
            id=story_uuid,
            user_id=uuid.UUID(user_id),
            child_id=uuid.UUID(child_id),
            scene_plan={"title": title, "scenes": [], "style_notes": {}},
            status="completed",
            style="watercolor",
        )
        session.add(story)
        for page_number in range(1, page_count + 1):
            page = StoryPageModel(
                story_id=story_uuid,
                page_number=page_number,
                scene_id=f"scene_{page_number}",
                text=f"{page_number}번째 페이지 본문",
                illustration_prompt="watercolor illustration prompt",
            )
            session.add(page)
        await session.commit()

    return str(story_uuid)


# ===========================================================================
# Happy path
# ===========================================================================


class TestDeleteStoryHappyPath:
    @pytest.mark.asyncio
    async def test_delete_returns_204(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """본인 스토리 DELETE → 204 No Content."""
        user_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(user_id, child_id)

        resp = await client.delete(f"/stories/{story_id}", headers=auth_header)

        assert resp.status_code == 204
        # 204 는 본문 없음.
        assert resp.content == b""

    @pytest.mark.asyncio
    async def test_delete_removes_story_from_db(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """DELETE 후 Story 행이 DB 에서 사라진다."""
        user_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(user_id, child_id)

        await client.delete(f"/stories/{story_id}", headers=auth_header)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryModel).where(StoryModel.id == uuid.UUID(story_id))
            )
            assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_cascades_to_pages(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """DELETE 시 자식 StoryPage 들도 함께 삭제된다 (cascade)."""
        user_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(user_id, child_id, page_count=5)

        # 사전 확인: 페이지 5개 존재
        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryPageModel).where(
                    StoryPageModel.story_id == uuid.UUID(story_id)
                )
            )
            assert len(result.scalars().all()) == 5

        await client.delete(f"/stories/{story_id}", headers=auth_header)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryPageModel).where(
                    StoryPageModel.story_id == uuid.UUID(story_id)
                )
            )
            assert result.scalars().all() == []

    @pytest.mark.asyncio
    async def test_delete_then_get_returns_404(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """DELETE 후 같은 ID 로 GET 하면 404."""
        user_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(user_id, child_id)

        await client.delete(f"/stories/{story_id}", headers=auth_header)
        resp = await client.get(f"/stories/{story_id}", headers=auth_header)

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_does_not_affect_other_stories(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """한 스토리 DELETE 가 다른 스토리에는 영향이 없다."""
        user_id = await _get_user_id(client, auth_header)
        story_a = await _seed_story(user_id, child_id, title="첫 번째 책")
        story_b = await _seed_story(user_id, child_id, title="두 번째 책")

        resp = await client.delete(f"/stories/{story_a}", headers=auth_header)
        assert resp.status_code == 204

        # B 는 여전히 조회 가능
        resp = await client.get(f"/stories/{story_b}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["id"] == story_b


# ===========================================================================
# 인증
# ===========================================================================


class TestDeleteStoryAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        """Authorization 헤더 없음 → 401."""
        resp = await client.delete(f"/stories/{uuid.uuid4()}")
        assert resp.status_code == 401


# ===========================================================================
# 소유자 검증
# ===========================================================================


class TestDeleteStoryOwnership:
    @pytest.mark.asyncio
    async def test_unknown_story_id_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """존재하지 않는 story_id → 404."""
        resp = await client.delete(f"/stories/{uuid.uuid4()}", headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """UUID 형식이 아닌 story_id → 404 (S20 패턴)."""
        resp = await client.delete("/stories/not-a-uuid", headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_other_users_story_returns_404(
        self,
        client: AsyncClient,
        auth_header: dict,
        other_auth_header: dict,
        child_id: str,
    ) -> None:
        """다른 사용자의 스토리 DELETE → 404 (소유자 정보 노출 방지)."""
        owner_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(owner_id, child_id)

        # 다른 사용자가 삭제 시도
        resp = await client.delete(f"/stories/{story_id}", headers=other_auth_header)
        assert resp.status_code == 404

        # 원래 소유자에게는 여전히 존재
        resp = await client.get(f"/stories/{story_id}", headers=auth_header)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_other_user_cannot_delete_via_double_call(
        self,
        client: AsyncClient,
        auth_header: dict,
        other_auth_header: dict,
        child_id: str,
    ) -> None:
        """다른 사용자가 DELETE 를 두 번 호출해도 원본은 보존된다 (방어 검증)."""
        owner_id = await _get_user_id(client, auth_header)
        story_id = await _seed_story(owner_id, child_id)

        await client.delete(f"/stories/{story_id}", headers=other_auth_header)
        await client.delete(f"/stories/{story_id}", headers=other_auth_header)

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(StoryModel).where(StoryModel.id == uuid.UUID(story_id))
            )
            assert result.scalar_one_or_none() is not None
