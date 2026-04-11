"""S30a — POST /api/v1/stories/plan 엔드포인트 테스트.

부모 서술형 텍스트 + 목적 + child_id → ScenePlan + StoryPreview 반환.
StoryOrchestrator의 interpret_and_plan + get_preview 단계(Phase A+B)를 노출한다.

설계:
- S19의 /stories/generate(Phase D)는 이미 확정된 plan을 받음.
- 그 앞 단계(parent_text → ScenePlan)가 라우터에 노출되어 있지 않아
  S30(모바일 서술형 입력 UI)이 호출할 곳이 없었음. S30a가 그 빈자리를 채운다.

테스트 전략:
- 인증/소유자 검증은 실제 로그인 + 실제 ChildProfile 생성으로 통합 검증 (S28 패턴).
- StoryOrchestrator는 모킹 (S19 패턴) — LLM 호출 없이 빠르게 동작.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from storytale.api.stories.router import get_story_orchestrator
from storytale.app import app
from storytale.auth.schemas import SocialUserInfo
from storytale.interpreter.intent_analyzer import RejectedIntentError
from storytale.interpreter.preview_generator import StoryPreview
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes

BASE_URL = "http://test/api/v1"

# ---------------------------------------------------------------------------
# 픽스처 데이터
# ---------------------------------------------------------------------------

SAMPLE_SCENE_PLAN = ScenePlan(
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
            description="엄마의 변하지 않은 사랑을 느낍니다.",
            child_elements=["엄마와 단둘이 보내는 시간"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 다독이는",
        avoid=["혼내는 어조", "비교하는 표현"],
        repetition_motif="너는 여전히 소중해",
    ),
)

SAMPLE_STORY_PREVIEW = StoryPreview(
    title="서준이의 마음 다독이기",
    summary=(
        "동생이 생긴 후 마음이 복잡한 서준이가 엄마의 사랑을 다시 확인하는 이야기예요."
    ),
    scene_highlights=[
        "🥺 동생이 생긴 후 속상한 서준이",
        "🤗 엄마와 단둘이 보내는 시간",
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
    """StoryOrchestrator를 모킹. interpret_and_plan + get_preview만 사용."""
    orch = AsyncMock()
    orch.interpret_and_plan = AsyncMock(return_value=SAMPLE_SCENE_PLAN)
    orch.get_preview = AsyncMock(return_value=SAMPLE_STORY_PREVIEW)
    return orch


@pytest_asyncio.fixture()
async def client(mock_orchestrator):
    """AsyncClient + StoryOrchestrator dependency override."""
    app.dependency_overrides[get_story_orchestrator] = lambda: mock_orchestrator
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac
    app.dependency_overrides.pop(get_story_orchestrator, None)


async def _login(client: AsyncClient, email_prefix: str = "plan-test") -> str:
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
    token = await _login(client, "plan-owner")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def other_auth_header(client):
    """다른 사용자의 Authorization 헤더 (소유자 검증용)."""
    token = await _login(client, "plan-other")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def child_id(client, auth_header):
    """auth_header 사용자가 소유한 ChildProfile 생성 → child_id 반환."""
    resp = await client.post("/profiles", json=VALID_PROFILE, headers=auth_header)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _valid_body(child_id: str) -> dict:
    return {
        "parent_text": (
            "동생이 태어난 후로 자꾸 동생을 밀쳐요. 마음을 다독여주고 싶어요."
        ),
        "purpose_category": "problem_solving",
        "child_id": child_id,
    }


# ===========================================================================
# Happy path
# ===========================================================================


class TestPlanEndpointHappyPath:
    @pytest.mark.asyncio
    async def test_returns_200_with_plan_and_preview(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """정상 요청 → 200 + plan + preview 반환."""
        resp = await client.post(
            "/stories/plan", json=_valid_body(child_id), headers=auth_header
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "plan" in data
        assert "preview" in data

        plan = data["plan"]
        assert plan["title"] == "서준이의 마음 다독이기"
        assert len(plan["scenes"]) == 2
        assert plan["scenes"][0]["scene_id"] == "opening"
        assert "style_notes" in plan

        preview = data["preview"]
        assert preview["title"] == "서준이의 마음 다독이기"
        assert preview["page_count"] == 2
        assert len(preview["scene_highlights"]) == 2
        assert preview["style"] == "watercolor"

    @pytest.mark.asyncio
    async def test_orchestrator_called_with_correct_args(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """interpret_and_plan이 parent_text + purpose + child로 호출되어야 한다."""
        await client.post(
            "/stories/plan", json=_valid_body(child_id), headers=auth_header
        )

        assert mock_orchestrator.interpret_and_plan.await_count == 1
        call = mock_orchestrator.interpret_and_plan.await_args
        assert call.kwargs["parent_text"].startswith("동생이 태어난")
        assert call.kwargs["purpose_category"] == "problem_solving"
        # child는 ChildProfile 모델로 전달되어야 함 (interpret_and_plan 시그니처 준수)
        child_arg = call.kwargs["child"]
        assert child_arg.name == "서준"
        assert child_arg.age == 5

        # get_preview는 plan + style 인자로 호출
        assert mock_orchestrator.get_preview.await_count == 1
        preview_call = mock_orchestrator.get_preview.await_args
        assert preview_call.kwargs["plan"] is SAMPLE_SCENE_PLAN
        assert preview_call.kwargs["style"] == "watercolor"


# ===========================================================================
# 인증
# ===========================================================================


class TestPlanEndpointAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(
        self, client: AsyncClient, child_id: str
    ) -> None:
        """Authorization 헤더 없음 → 401."""
        resp = await client.post("/stories/plan", json=_valid_body(child_id))
        assert resp.status_code == 401


# ===========================================================================
# 소유자 검증
# ===========================================================================


class TestPlanEndpointOwnership:
    @pytest.mark.asyncio
    async def test_unknown_child_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """존재하지 않는 child_id → 404."""
        body = _valid_body(str(uuid.uuid4()))
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_uuid_child_returns_404(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """UUID 형식이 아닌 child_id → 404 (S20 패턴 일치)."""
        body = _valid_body("not-a-uuid")
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
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
        resp = await client.post("/stories/plan", json=body, headers=other_auth_header)
        assert resp.status_code == 404


# ===========================================================================
# 입력 검증
# ===========================================================================


class TestPlanEndpointValidation:
    @pytest.mark.asyncio
    async def test_invalid_purpose_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """purpose_category가 4종 IntentCategory 외 → 422."""
        body = {**_valid_body(child_id), "purpose_category": "random_topic"}
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_parent_text_too_long_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """parent_text 500자 초과 → 422 (security.md: 부모 입력 최대 500자)."""
        body = {**_valid_body(child_id), "parent_text": "가" * 501}
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_parent_text_empty_returns_422(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """parent_text 빈 문자열 → 422."""
        body = {**_valid_body(child_id), "parent_text": ""}
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_parent_text_500_chars_ok(
        self, client: AsyncClient, auth_header: dict, child_id: str
    ) -> None:
        """parent_text 정확히 500자 → 통과."""
        body = {**_valid_body(child_id), "parent_text": "가" * 500}
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_child_id_returns_422(
        self, client: AsyncClient, auth_header: dict
    ) -> None:
        """child_id 필드 누락 → 422."""
        body = {
            "parent_text": "이야기를 만들어주세요",
            "purpose_category": "value_teaching",
        }
        resp = await client.post("/stories/plan", json=body, headers=auth_header)
        assert resp.status_code == 422


# ===========================================================================
# 오케스트레이터 에러 처리
# ===========================================================================


class TestPlanEndpointOrchestratorErrors:
    @pytest.mark.asyncio
    async def test_rejected_intent_returns_400(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """LLM이 부적절한 요청으로 거부 → 400 + REJECTED_INTENT 코드."""
        mock_orchestrator.interpret_and_plan.side_effect = RejectedIntentError(
            "폭력적인 요청은 동화책으로 만들 수 없어요."
        )

        resp = await client.post(
            "/stories/plan", json=_valid_body(child_id), headers=auth_header
        )

        assert resp.status_code == 400
        body = resp.json()
        # storytale.app 글로벌 핸들러가 HTTPException.detail을 message로 매핑하므로
        # detail에 dict를 넘기면 그 dict가 error.message 자리에 들어온다.
        # 클라이언트는 error.message.code === "REJECTED_INTENT" 로 구분.
        assert body["error"]["code"] == 400
        message = body["error"]["message"]
        assert isinstance(message, dict)
        assert message["code"] == "REJECTED_INTENT"
        assert "폭력적인" in message["message"]

    @pytest.mark.asyncio
    async def test_orchestrator_exception_returns_500(
        self,
        client: AsyncClient,
        auth_header: dict,
        child_id: str,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """일반 예외 → 500."""
        mock_orchestrator.interpret_and_plan.side_effect = RuntimeError(
            "LLM upstream error"
        )

        resp = await client.post(
            "/stories/plan", json=_valid_body(child_id), headers=auth_header
        )

        assert resp.status_code == 500
