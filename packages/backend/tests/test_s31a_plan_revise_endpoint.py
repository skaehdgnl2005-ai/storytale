"""S31a — POST /api/v1/stories/plan/revise 엔드포인트 테스트.

부모가 받은 ScenePlan + 수정 피드백 → 수정된 ScenePlan + 새 StoryPreview.
StoryOrchestrator.revise_plan + get_preview(Phase C → 재 Phase B) 단계를 노출한다.

설계:
- S30a가 plan(Phase A+B)을 노출했고, S31a는 그 다음 단계인 revise(Phase C)를 노출한다.
- revise 횟수 제한(MAX_REVISIONS=3)은 라우터 레벨에서 검증한다.
  `InterpreterOrchestrator._revision_count`는 매 요청마다 새 인스턴스가 생성되므로
  무력화돼 있어 사용하지 않는다(SESSION_LOG S31a 결정 메모 참조).
- 클라이언트가 `revision_count`(이미 적용된 횟수, 0-based)를 보낸다.
- 서버는 `revision_count < MAX_REVISIONS`를 검증하고, 통과 시 +1 한 값을 응답에 포함.

테스트 전략:
- 인증/소유자 검증은 실제 로그인 + 실제 ChildProfile 생성으로 통합 검증 (S28/S30a 패턴).
- StoryOrchestrator는 모킹 — LLM 호출 없이 빠르게 동작.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from storytale.api.stories.router import get_story_orchestrator
from storytale.app import app
from storytale.auth.schemas import SocialUserInfo
from storytale.interpreter.interpreter_orchestrator import MAX_REVISIONS
from storytale.interpreter.preview_generator import StoryPreview
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes

BASE_URL = "http://test/api/v1"

# ---------------------------------------------------------------------------
# 픽스처 데이터
# ---------------------------------------------------------------------------

ORIGINAL_SCENE_PLAN = ScenePlan(
    title="서준이의 마음 다독이기",
    scenes=[
        PlannedScene(
            scene_id="opening",
            emotion="속상함",
            purpose="현재 감정 공감",
            description="동생이 생긴 후 서준이가 속상해합니다.",
            child_elements=["comfort_object가 곁에 있음"],
        ),
        PlannedScene(
            scene_id="turning_point",
            emotion="안도",
            purpose="시선 전환",
            description="토끼 친구가 나타나 위로해줍니다.",
            child_elements=["favorite_animal 등장"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 다독이는",
        avoid=["혼내는 어조", "비교하는 표현"],
        repetition_motif="너는 여전히 소중해",
    ),
)

REVISED_SCENE_PLAN = ScenePlan(
    title="서준이의 마음 다독이기",
    scenes=[
        PlannedScene(
            scene_id="opening",
            emotion="속상함",
            purpose="현재 감정 공감",
            description="동생이 생긴 후 서준이가 속상해합니다.",
            child_elements=["comfort_object가 곁에 있음"],
        ),
        PlannedScene(
            scene_id="turning_point",
            emotion="안도",
            purpose="시선 전환",
            description="친구 민준이가 나타나 위로해줍니다.",
            child_elements=["friend_name 등장"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 다독이는",
        avoid=["혼내는 어조", "비교하는 표현"],
        repetition_motif="너는 여전히 소중해",
    ),
)

REVISED_STORY_PREVIEW = StoryPreview(
    title="서준이의 마음 다독이기",
    summary=(
        "동생이 생긴 후 마음이 복잡한 서준이가 "
        "친구 민준이의 위로로 마음을 다독이는 이야기예요."
    ),
    scene_highlights=[
        "🥺 동생이 생긴 후 속상한 서준이",
        "🤗 친구 민준이가 위로해주는 시간",
    ],
    page_count=2,
    style="watercolor",
)

VALID_PROFILE = {
    "name": "서준",
    "age": 5,
    "gender": "male",
    "comfort_object": "토니 곰인형",
    "friend_name": "민준",
    "favorite_animal": "토끼",
}


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_orchestrator():
    """StoryOrchestrator를 모킹. revise_plan + get_preview만 사용."""
    orch = AsyncMock()
    orch.revise_plan = AsyncMock(return_value=REVISED_SCENE_PLAN)
    orch.get_preview = AsyncMock(return_value=REVISED_STORY_PREVIEW)
    return orch


@pytest_asyncio.fixture()
async def client(mock_orchestrator):
    """AsyncClient + StoryOrchestrator dependency override."""
    app.dependency_overrides[get_story_orchestrator] = lambda: mock_orchestrator
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac
    app.dependency_overrides.pop(get_story_orchestrator, None)


async def _login(client: AsyncClient, email_prefix: str = "revise-test") -> str:
    """소셜 로그인 → JWT access token 반환."""
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


@pytest_asyncio.fixture()
async def auth_header(client):
    """로그인된 사용자의 Authorization 헤더."""
    token = await _login(client, "revise-owner")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def other_auth_header(client):
    """다른 사용자의 Authorization 헤더 (소유자 검증용)."""
    token = await _login(client, "revise-other")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def child_id(client, auth_header):
    """auth_header 사용자가 소유한 ChildProfile 생성 → child_id 반환."""
    resp = await client.post("/profiles", json=VALID_PROFILE, headers=auth_header)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _valid_body(child_id: str, revision_count: int = 0) -> dict:
    return {
        "current_plan": ORIGINAL_SCENE_PLAN.model_dump(),
        "feedback": "토끼 친구 대신 민준이가 나왔으면 좋겠어요.",
        "revision_count": revision_count,
        "child_id": child_id,
    }


# ===========================================================================
# Happy path
# ===========================================================================


class TestPlanReviseEndpointHappyPath:
    @pytest.mark.asyncio
    async def test_returns_200_with_revised_plan_and_preview(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """정상 요청 → 200 + 수정된 plan + 새 preview + revision_count=1."""
        resp = await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id, revision_count=0),
            headers=auth_header,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "plan" in data
        assert "preview" in data
        assert "revision_count" in data

        plan = data["plan"]
        # 수정된 turning_point 장면 확인
        assert plan["scenes"][1]["description"].startswith("친구 민준이")
        assert "friend_name 등장" in plan["scenes"][1]["child_elements"]

        preview = data["preview"]
        assert preview["page_count"] == 2
        assert "민준" in preview["summary"]
        assert preview["style"] == "watercolor"

        # 0회 → 1회 (이번 호출이 1번째 revise)
        assert data["revision_count"] == 1

    @pytest.mark.asyncio
    async def test_orchestrator_called_with_correct_args(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """revise_plan이 current_plan + feedback으로 호출되어야 한다."""
        await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id),
            headers=auth_header,
        )

        assert mock_orchestrator.revise_plan.await_count == 1
        call = mock_orchestrator.revise_plan.await_args
        # current_plan은 ScenePlan 모델로 전달되어야 함
        plan_arg = call.kwargs["plan"]
        assert plan_arg.title == "서준이의 마음 다독이기"
        assert len(plan_arg.scenes) == 2
        assert call.kwargs["feedback"].startswith("토끼 친구 대신")

        # get_preview는 revised plan + style + child_name으로 호출
        assert mock_orchestrator.get_preview.await_count == 1
        preview_call = mock_orchestrator.get_preview.await_args
        assert preview_call.kwargs["plan"] is REVISED_SCENE_PLAN
        assert preview_call.kwargs["style"] == "watercolor"
        assert preview_call.kwargs["child_name"] == "서준"

    @pytest.mark.asyncio
    async def test_revision_count_increments_at_each_step(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """클라이언트가 보낸 revision_count + 1을 응답에 반환."""
        # 1번째 revise: 0 → 1
        resp = await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id, revision_count=0),
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["revision_count"] == 1

        # 2번째 revise: 1 → 2
        resp = await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id, revision_count=1),
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["revision_count"] == 2

        # 3번째 revise: 2 → 3 (마지막 허용)
        resp = await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id, revision_count=2),
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["revision_count"] == 3


# ===========================================================================
# 인증
# ===========================================================================


class TestPlanReviseEndpointAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(
        self, client: AsyncClient, child_id: str
    ) -> None:
        """Authorization 헤더 없음 → 401."""
        resp = await client.post("/stories/plan/revise", json=_valid_body(child_id))
        assert resp.status_code == 401


# ===========================================================================
# 소유자 검증
# ===========================================================================


class TestPlanReviseEndpointOwnership:
    @pytest.mark.asyncio
    async def test_unknown_child_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """존재하지 않는 child_id → 404."""
        body = _valid_body(str(uuid.uuid4()))
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_uuid_child_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """UUID 형식이 아닌 child_id → 404 (S20/S30a 패턴 일치)."""
        body = _valid_body("not-a-uuid")
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_other_users_child_returns_404(
        self,
        client: AsyncClient,
        other_auth_header: dict,
        child_id: str,
    ) -> None:
        """다른 사용자가 만든 child_id → 404 (소유자 정보 노출 방지)."""
        body = _valid_body(child_id)
        resp = await client.post(
            "/stories/plan/revise", json=body, headers=other_auth_header
        )
        assert resp.status_code == 404


# ===========================================================================
# 수정 횟수 제한
# ===========================================================================


class TestPlanReviseEndpointMaxRevisions:
    @pytest.mark.asyncio
    async def test_revision_count_at_limit_returns_400(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """revision_count == MAX_REVISIONS(3) → 400 + MAX_REVISIONS_EXCEEDED."""
        body = _valid_body(child_id, revision_count=MAX_REVISIONS)
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)

        assert resp.status_code == 400
        body_json = resp.json()
        # 글로벌 핸들러가 detail을 error.message에 매핑
        message = body_json["error"]["message"]
        assert isinstance(message, dict)
        assert message["code"] == "MAX_REVISIONS_EXCEEDED"
        assert "3" in message["message"]  # 한도 안내 문구에 횟수 노출

        # orchestrator는 호출되지 않아야 함
        mock_orchestrator.revise_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_revision_count_above_limit_returns_400(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """revision_count > MAX_REVISIONS → 400."""
        body = _valid_body(child_id, revision_count=MAX_REVISIONS + 5)
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)

        assert resp.status_code == 400
        message = resp.json()["error"]["message"]
        assert message["code"] == "MAX_REVISIONS_EXCEEDED"
        mock_orchestrator.revise_plan.assert_not_called()


# ===========================================================================
# 입력 검증
# ===========================================================================


class TestPlanReviseEndpointValidation:
    @pytest.mark.asyncio
    async def test_feedback_too_long_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """feedback 500자 초과 → 422 (security.md: 부모 입력 최대 500자)."""
        body = _valid_body(child_id)
        body["feedback"] = "가" * 501
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_feedback_empty_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """feedback 빈 문자열 → 422."""
        body = _valid_body(child_id)
        body["feedback"] = ""
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_revision_count_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """revision_count 음수 → 422."""
        body = _valid_body(child_id, revision_count=-1)
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_current_plan_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """current_plan 누락 → 422."""
        body = _valid_body(child_id)
        body.pop("current_plan")
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_revision_count_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """revision_count 필드 누락 → 422 (명시 강제)."""
        body = _valid_body(child_id)
        body.pop("revision_count")
        resp = await client.post("/stories/plan/revise", json=body, headers=auth_header)
        assert resp.status_code == 422


# ===========================================================================
# 오케스트레이터 에러 처리
# ===========================================================================


class TestPlanReviseEndpointOrchestratorErrors:
    @pytest.mark.asyncio
    async def test_orchestrator_exception_returns_500(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """일반 예외 → 500 + 부드러운 한국어 메시지."""
        mock_orchestrator.revise_plan.side_effect = RuntimeError("LLM upstream error")

        resp = await client.post(
            "/stories/plan/revise",
            json=_valid_body(child_id),
            headers=auth_header,
        )

        assert resp.status_code == 500
