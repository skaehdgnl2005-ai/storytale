"""S35b — 프론트-백 통합 E2E 테스트 (mobile API contract E2E).

S35a 가 백엔드 내부 파이프라인(StoryOrchestrator + IllustrationOrchestrator
+ DB 저장)의 통합을 검증했다면, S35b 는 **모바일 앱이 실제로 때리는**
HTTP 시퀀스를 그대로 재현하여 "프론트가 서버에 보내는 것 ↔ 서버가 프론트에게
돌려주는 것" 의 계약(contract)을 회귀 방어한다.

### 범위

- **in scope**: 모바일 `packages/mobile/src/api/{client,profiles,stories}.ts`
  가 호출하는 모든 URL/헤더/바디 시퀀스, 응답 JSON 의 snake_case 필드 세트,
  `ApiClientError` 가 파싱하는 에러 envelope(`{error: {code, message}}`)
  형식, JWT 만료/재로그인 경로, 소유자 검증 404 통일 정책.
- **out of scope**: 실기기 RN UI 자동화(Detox/Playwright) — 별도 태스크 I2.
  모바일 jest 복구 — 별도 태스크 I1. CLIP/DINOv2 실제 호출 — S24 범위 밖.
  동시 생성 제한(409) — security.md 규칙은 존재하나 미구현, SESSION_LOG
  "발견된 이슈" 에 이월.

### 전략

- 모든 LLM/Replicate 호출은 AsyncMock. S35a 패턴 재사용.
- 인증은 **실제 소셜 로그인**(AuthService `_get_social_user_info` 만 패치)으로
  JWT 를 발급받아 mobile `setAccessToken` 흐름과 동일하게 Authorization 헤더로
  전달. S30a/S31a/S34 가 사용한 `_login` 패턴을 그대로 가져온다.
- ChildProfile 은 실제 `POST /profiles` 로 생성 → 실제 child_id 로 후속 호출.
- 일러스트 오케스트레이터는 S35a 의 fake 제공자를 재사용(과도한 재실행 방지).

### 왜 이게 "contract E2E" 인가

mobile 측 와이어 타입은 `packages/mobile/src/api/stories.ts` 의 interface 들
(PlanStoryResponse, JobStatusResponse, StoryDetailResponse, StoryListResponse
등) 에 모두 snake_case 로 선언돼 있다. 본 테스트가 각 응답의 **키 세트를
정확히 그 interface 와 1:1 비교**하기 때문에, 백엔드가 필드를 하나라도
추가/제거/renaming 하면 반드시 여기서 실패한다. 즉 mobile 타입 정의와
백엔드 Pydantic 모델 사이의 "서로 모르고 있는 균열" 이 회귀로 즉시 잡힌다.
"""

import asyncio
import uuid
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from conftest import TestingSessionLocal
from storytale.api.auth_router import JWT_SECRET
from storytale.api.stories.router import (
    get_illustration_context_provider,
    get_session_factory,
    get_story_orchestrator,
    job_manager,
)
from storytale.app import app
from storytale.auth.schemas import SocialUserInfo
from storytale.auth.service import AuthService, create_blacklist
from storytale.db.models import Story as StoryModel
from storytale.db.models import StoryPage as StoryPageModel
from storytale.illustration.character_sheet_service import (
    CharacterReferenceImages,
    CharacterSheet,
)
from storytale.illustration.consistency_validator import ConsistencyScore
from storytale.illustration.illustration_orchestrator import OrchestratedIllustration
from storytale.interpreter.intent_analyzer import RejectedIntentError
from storytale.interpreter.preview_generator import StoryPreview
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes
from storytale.interpreter.story_personalizer import PersonalizedScene

BASE_URL = "http://test/api/v1"

# ---------------------------------------------------------------------------
# 픽스처 데이터 — S30a/S35a 와 일관된 구성
# ---------------------------------------------------------------------------

SAMPLE_SCENE_PLAN = ScenePlan(
    title="하은이의 마음 다독이기",
    scenes=[
        PlannedScene(
            scene_id="opening",
            emotion="속상함",
            purpose="현재 감정 공감",
            description="동생이 생긴 후 하은이가 속상해합니다.",
            child_elements=["comfort_object가 곁에 있음"],
        ),
        PlannedScene(
            scene_id="turning_point",
            emotion="안도",
            purpose="시선 전환",
            description="엄마의 사랑이 변하지 않았음을 느낍니다.",
            child_elements=["엄마와 단둘이 보내는 시간"],
        ),
        PlannedScene(
            scene_id="resolution",
            emotion="따뜻함",
            purpose="감정 전환",
            description="하은이가 동생에게도 마음을 열어봅니다.",
            child_elements=["comfort_object 응원"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 다독이는",
        avoid=["혼내는 어조", "비교하는 표현"],
        repetition_motif="너는 여전히 소중해",
    ),
)

SAMPLE_STORY_PREVIEW = StoryPreview(
    title="하은이의 마음 다독이기",
    summary=(
        "동생이 생긴 후 마음이 복잡한 하은이가 엄마의 사랑을 다시 확인하는 이야기예요."
    ),
    scene_highlights=[
        "🥺 동생이 생긴 후 속상한 하은이",
        "🤗 엄마와 단둘이 보내는 시간",
        "💛 다시 마음을 열어보는 하은이",
    ],
    page_count=3,
    style="watercolor",
)

REVISED_SCENE_PLAN = ScenePlan(
    title="하은이의 부드러운 마음 여행",
    scenes=SAMPLE_SCENE_PLAN.scenes,
    style_notes=StyleNotes(
        tone="아주 부드럽고 다독이는",
        avoid=["혼내는 어조", "비교하는 표현", "빠른 템포"],
        repetition_motif="너의 마음이 제일 소중해",
    ),
)

REVISED_STORY_PREVIEW = StoryPreview(
    title="하은이의 부드러운 마음 여행",
    summary="더 부드러운 톤으로 다시 쓰인 이야기예요.",
    scene_highlights=[
        "🥺 속상한 하은이",
        "🤗 엄마의 품",
        "💛 다시 열리는 마음",
    ],
    page_count=3,
    style="watercolor",
)

PERSONALIZED_SCENES = [
    PersonalizedScene(
        scene_id="opening",
        page_number=1,
        text="하은이는 동생이 생긴 게 조금 속상했어요.",
        illustration_prompt="A young girl sitting quietly, warm lighting",
    ),
    PersonalizedScene(
        scene_id="turning_point",
        page_number=2,
        text="엄마가 하은이를 꼭 안아주었어요.",
        illustration_prompt="A mother warmly hugging her daughter",
    ),
    PersonalizedScene(
        scene_id="resolution",
        page_number=3,
        text="하은이는 동생에게 작은 인사를 건넸어요.",
        illustration_prompt="The girl gently greeting her baby sibling",
    ),
]

VALID_PROFILE_BODY = {
    "name": "하은",
    "age": 4,
    "gender": "female",
    "comfort_object": "토니 곰인형",
    "friend_name": "서준",
    "favorite_animal": "토끼",
}

VALID_PLAN_BODY_TEMPLATE = {
    "parent_text": "동생이 태어난 후로 속상해해요. 마음을 다독여주고 싶어요.",
    "purpose_category": "problem_solving",
    # child_id 는 테스트에서 동적으로 주입
}


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------


def _make_fake_character_sheet() -> CharacterSheet:
    """S35a 와 동일한 픽스처 캐릭터 시트."""
    return CharacterSheet(
        character_id="char-test-s35b",
        reference_images=CharacterReferenceImages(
            front="https://fixtures.example/char/front.png",
            three_quarter="https://fixtures.example/char/three_quarter.png",
            side="https://fixtures.example/char/side.png",
        ),
        face_anchor_url="https://fixtures.example/char/anchor.png",
        identity_prompt_block="a young girl with round face, short black hair",
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


# ---------------------------------------------------------------------------
# 픽스처: 오케스트레이터 모킹
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_orchestrator() -> AsyncMock:
    """StoryOrchestrator 모킹 — plan/revise/generate 전 단계 지원.

    - interpret_and_plan: SAMPLE_SCENE_PLAN 반환
    - get_preview: SAMPLE_STORY_PREVIEW 반환
    - revise_plan: REVISED_SCENE_PLAN 반환 (revision_count 1 증가 의미)
    - generate_story: PERSONALIZED_SCENES 순차 yield
    """
    orch = AsyncMock()
    orch.interpret_and_plan = AsyncMock(return_value=SAMPLE_SCENE_PLAN)
    orch.get_preview = AsyncMock(
        side_effect=[SAMPLE_STORY_PREVIEW, REVISED_STORY_PREVIEW]
    )
    orch.revise_plan = AsyncMock(return_value=REVISED_SCENE_PLAN)

    async def fake_generate_story(confirmed_plan, child, style):
        for scene in PERSONALIZED_SCENES:
            await asyncio.sleep(0)
            yield scene

    orch.generate_story = fake_generate_story
    return orch


@pytest.fixture()
def mock_illustration_orchestrator() -> AsyncMock:
    """IllustrationOrchestrator 모킹 — S35a 패턴."""
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
    return orch


# ---------------------------------------------------------------------------
# 픽스처: 테스트 전후 스토리 테이블 정리 (S35a 패턴)
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
# 픽스처: 통합 클라이언트 (일러스트 주입 + 오케스트레이터 모킹)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(
    mock_orchestrator: AsyncMock,
    mock_illustration_orchestrator: AsyncMock,
):
    """모바일 전체 플로우용 httpx AsyncClient.

    - get_story_orchestrator → plan/revise/generate 전 단계 mock
    - get_illustration_context_provider → (일러스트 mock, 픽스처 CharacterSheet)
    - get_session_factory → 테스트 DB
    - 인증은 override 하지 않음 → 실제 AuthService + 실제 JWT 흐름 사용
    """
    character_sheet = _make_fake_character_sheet()

    async def fake_context_provider(
        child, style: str
    ) -> tuple[AsyncMock, CharacterSheet]:
        return mock_illustration_orchestrator, character_sheet

    app.dependency_overrides[get_story_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_illustration_context_provider] = lambda: (
        fake_context_provider
    )
    app.dependency_overrides[get_session_factory] = lambda: TestingSessionLocal
    job_manager.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=BASE_URL,
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_story_orchestrator, None)
    app.dependency_overrides.pop(get_illustration_context_provider, None)
    app.dependency_overrides.pop(get_session_factory, None)
    job_manager.clear()


# ---------------------------------------------------------------------------
# 헬퍼: 로그인 / 폴링 / 만료 토큰
# ---------------------------------------------------------------------------


async def _login(
    client: AsyncClient, email_prefix: str = "s35b-flow"
) -> dict[str, str]:
    """모바일 AuthBootstrap 과 동일한 경로로 로그인 → access_token 반환.

    POST /auth/login 은 mobile 의 첫 호출. `_get_social_user_info` 만 패치하여
    JWT 발급 경로(create_access_token + create_refresh_token) 는 실제 코드를
    그대로 태운다.
    """
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
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    return tokens


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _expired_access_token(user_id: str) -> str:
    """만료된 JWT access token 생성 — AuthService 를 DB 없이 직접 사용.

    real login 과 동일한 JWT_SECRET + 동일한 payload 구조(`type=access`, `sub=user_id`)
    이되 exp 만 과거로. mobile 이 "서버가 401 을 돌려줄 때 어떻게 반응해야 하는가"
    의 contract 를 테스트하기 위함.
    """
    svc = AuthService(
        db=None,  # type: ignore[arg-type]  # decode/encode 는 db 불필요
        jwt_secret=JWT_SECRET,
        blacklist=create_blacklist(),
    )
    return svc.create_access_token(user_id=user_id, expires_delta=timedelta(seconds=-1))


async def _poll_until_completed(
    client: AsyncClient,
    job_id: str,
    headers: dict[str, str],
    max_iterations: int = 60,
) -> dict[str, Any]:
    """잡이 completed 또는 failed 상태가 될 때까지 폴링 → 최종 snapshot 반환."""
    final: dict[str, Any] | None = None
    for _ in range(max_iterations):
        await asyncio.sleep(0.1)
        resp = await client.get(f"/stories/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        final = resp.json()
        if final["status"] in ("completed", "failed"):
            return final
    assert final is not None, "polling yielded no snapshots"
    return final


async def _create_profile(
    client: AsyncClient, headers: dict[str, str], body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """mobile createProfile() 과 동일한 경로로 프로필 생성."""
    resp = await client.post(
        "/profiles", json=body or VALID_PROFILE_BODY, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# 1. Happy path — 모바일 전체 플로우 E2E
# ===========================================================================


class TestFullMobileContractFlow:
    """모바일이 실제로 때리는 HTTP 시퀀스를 한 테스트에서 end-to-end 로 검증.

    각 단계 응답의 키 세트가 `packages/mobile/src/api/stories.ts` 의 TypeScript
    interface 와 1:1 매칭되는지 인라인으로 확인한다. 백엔드가 필드를 renaming
    /추가/제거하면 반드시 여기서 실패한다.
    """

    @pytest.mark.asyncio()
    async def test_full_sequence_login_to_delete(self, client: AsyncClient) -> None:
        """로그인 → 프로필 등록 → plan → revise → generate → 폴링
        → GET /stories/{id} → GET /stories → DELETE → GET(404) 까지 한 번에."""
        # --- 1. login (mobile AuthBootstrap) ---
        tokens = await _login(client, "full-flow")
        # mobile AuthTokens 와이어 형태
        assert set(tokens.keys()) >= {"access_token", "refresh_token"}
        headers = _auth_header(tokens["access_token"])

        # --- 2. create profile (mobile createProfile) ---
        profile = await _create_profile(client, headers)
        # mobile ChildProfile 와이어 형태
        assert set(profile.keys()) >= {
            "id",
            "name",
            "age",
            "gender",
            "comfort_object",
            "friend_name",
            "favorite_animal",
        }
        child_id = profile["id"]

        # --- 3. list profiles (mobile DescriptiveInputScreen 자동 선택) ---
        list_profiles_resp = await client.get("/profiles", headers=headers)
        assert list_profiles_resp.status_code == 200
        profiles_list = list_profiles_resp.json()
        assert isinstance(profiles_list, list)
        assert any(p["id"] == child_id for p in profiles_list)

        # --- 4. POST /stories/plan (mobile createStoryPlan) ---
        plan_body = {**VALID_PLAN_BODY_TEMPLATE, "child_id": child_id}
        plan_resp = await client.post("/stories/plan", json=plan_body, headers=headers)
        assert plan_resp.status_code == 200, plan_resp.text
        plan_data = plan_resp.json()
        # mobile PlanStoryResponse 와이어 형태
        assert set(plan_data.keys()) == {"plan", "preview"}
        plan_wire = plan_data["plan"]
        # mobile ScenePlan 와이어 형태
        assert set(plan_wire.keys()) == {"title", "scenes", "style_notes"}
        assert len(plan_wire["scenes"]) == 3
        # mobile PlannedScene 와이어 형태
        first_scene = plan_wire["scenes"][0]
        assert set(first_scene.keys()) == {
            "scene_id",
            "emotion",
            "purpose",
            "description",
            "child_elements",
        }
        preview_wire = plan_data["preview"]
        # mobile StoryPreview 와이어 형태
        assert set(preview_wire.keys()) == {
            "title",
            "summary",
            "scene_highlights",
            "page_count",
            "style",
        }

        # --- 5. POST /stories/plan/revise (mobile revisePlan) ---
        revise_body = {
            "current_plan": plan_wire,
            "feedback": "더 부드럽게 해주세요",
            "revision_count": 0,
            "child_id": child_id,
        }
        revise_resp = await client.post(
            "/stories/plan/revise", json=revise_body, headers=headers
        )
        assert revise_resp.status_code == 200, revise_resp.text
        revise_data = revise_resp.json()
        # mobile PlanRevisionResponse 와이어 형태
        assert set(revise_data.keys()) == {"plan", "preview", "revision_count"}
        # 서버가 카운트를 올려서 내려줌 (mobile 이 다음 요청에 그대로 echo)
        assert revise_data["revision_count"] == 1

        # --- 6. POST /stories/generate (mobile generateStory) ---
        generate_body = {
            "confirmed_plan": revise_data["plan"],
            "child": {
                "child_id": child_id,
                "name": profile["name"],
                "age": profile["age"],
                "gender": profile["gender"],
                "comfort_object": profile["comfort_object"],
                "friend_name": profile["friend_name"],
                "favorite_animal": profile["favorite_animal"],
            },
            "style": "watercolor",
        }
        gen_resp = await client.post(
            "/stories/generate", json=generate_body, headers=headers
        )
        assert gen_resp.status_code == 202, gen_resp.text
        gen_data = gen_resp.json()
        # mobile GenerateStoryResponse 와이어 형태
        assert set(gen_data.keys()) == {"job_id"}
        job_id = gen_data["job_id"]

        # --- 7. GET /stories/jobs/{job_id} 폴링 (mobile getJobStatus 루프) ---
        final_snapshot = await _poll_until_completed(client, job_id, headers)
        assert final_snapshot["status"] == "completed", final_snapshot
        # mobile JobStatusResponse 와이어 형태
        assert set(final_snapshot.keys()) == {
            "job_id",
            "status",
            "total_scenes",
            "completed_scenes",
            "scenes",
            "error",
            "story_id",
        }
        assert final_snapshot["story_id"] is not None
        assert final_snapshot["total_scenes"] == 3
        assert final_snapshot["completed_scenes"] == 3
        # mobile GeneratedScene 와이어 형태
        for scene in final_snapshot["scenes"]:
            assert set(scene.keys()) >= {
                "scene_id",
                "page_number",
                "text",
                "illustration_prompt",
            }
        story_id = final_snapshot["story_id"]

        # --- 8. GET /stories/{story_id} (mobile getStory → ViewerScreen) ---
        detail_resp = await client.get(f"/stories/{story_id}", headers=headers)
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        # mobile StoryDetailResponse 와이어 형태
        assert set(detail_data.keys()) == {
            "id",
            "title",
            "status",
            "style",
            "created_at",
            "page_count",
            "pages",
        }
        assert detail_data["page_count"] == 3
        assert len(detail_data["pages"]) == 3
        # mobile StoryPageDetail 와이어 형태
        for page in detail_data["pages"]:
            assert set(page.keys()) == {
                "id",
                "page_number",
                "scene_id",
                "text",
                "illustration_prompt",
                "illustration_url",
            }
            # S35a 통합 덕분에 일러스트 URL 이 채워진 상태
            assert page["illustration_url"] is not None
            assert page["illustration_url"].startswith("https://")

        # --- 9. GET /stories?limit=20&offset=0 (mobile listStories → LibraryScreen) ---
        list_resp = await client.get("/stories?limit=20&offset=0", headers=headers)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        # mobile StoryListResponse 와이어 형태
        assert set(list_data.keys()) == {"items", "total", "limit", "offset"}
        assert list_data["limit"] == 20
        assert list_data["offset"] == 0
        assert list_data["total"] >= 1
        assert any(item["id"] == story_id for item in list_data["items"])
        # mobile StoryListItem 와이어 형태
        for item in list_data["items"]:
            assert set(item.keys()) == {
                "id",
                "title",
                "status",
                "style",
                "created_at",
                "page_count",
            }

        # --- 10. DELETE /stories/{story_id} (mobile deleteStory) ---
        del_resp = await client.delete(f"/stories/{story_id}", headers=headers)
        assert del_resp.status_code == 204
        assert del_resp.content == b""

        # --- 11. GET 확인 — 삭제 후 404 ---
        after_delete_resp = await client.get(f"/stories/{story_id}", headers=headers)
        assert after_delete_resp.status_code == 404


# ===========================================================================
# 2. 에러 envelope 계약 — mobile ApiClientError parseErrorBody 와 일치
# ===========================================================================


class TestMobileErrorEnvelope:
    """mobile `client.ts::parseErrorBody` 가 `{error: {code, message}}` 래핑
    형식과 `REJECTED_INTENT` inner code 패턴을 기대한다. 백엔드가 이를
    돌려주지 않으면 모바일 에러 핸들링이 전부 무너진다.
    """

    @pytest.mark.asyncio()
    async def test_missing_auth_header_returns_wrapped_401(
        self, client: AsyncClient
    ) -> None:
        """Authorization 헤더 없음 → 401 + 래핑된 error envelope."""
        resp = await client.post(
            "/stories/plan",
            json={
                **VALID_PLAN_BODY_TEMPLATE,
                "child_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 401
        body = resp.json()
        # mobile parseErrorBody 가 기대하는 형태
        assert "error" in body, (
            f"401 에러 본문은 `error` 키 래핑되어야 mobile parseErrorBody 가 읽는다. "
            f"실제: {body}"
        )
        err_obj = body["error"]
        assert isinstance(err_obj, dict)
        assert "message" in err_obj

    @pytest.mark.asyncio()
    async def test_unknown_child_returns_wrapped_404(self, client: AsyncClient) -> None:
        """존재하지 않는 child_id → 404 + 래핑된 error envelope."""
        tokens = await _login(client, "err-envelope")
        headers = _auth_header(tokens["access_token"])

        resp = await client.post(
            "/stories/plan",
            json={
                **VALID_PLAN_BODY_TEMPLATE,
                "child_id": str(uuid.uuid4()),
            },
            headers=headers,
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "message" in body["error"]

    @pytest.mark.asyncio()
    async def test_rejected_intent_has_inner_code_for_mobile_switch(
        self,
        client: AsyncClient,
        mock_orchestrator: AsyncMock,
    ) -> None:
        """RejectedIntentError → mobile inner code 분기가 가능한 envelope.

        형식: `{error: {code, message: {code: 'REJECTED_INTENT', message: '...'}}}`.
        mobile `client.ts::parseErrorBody` 가 outer message 의 dict 내부에서
        `code === REJECTED_INTENT` 를 추출한다. 이 형태가 깨지면 mobile
        DescriptiveInputScreen 의 거부 배너가 일반 에러로 보여져 혼란을 준다.
        """
        # orchestrator 가 RejectedIntentError 를 던지도록 설정
        mock_orchestrator.interpret_and_plan = AsyncMock(
            side_effect=RejectedIntentError("부적절한 내용이 포함되어 있어요")
        )

        tokens = await _login(client, "reject-intent")
        headers = _auth_header(tokens["access_token"])
        profile = await _create_profile(client, headers)

        resp = await client.post(
            "/stories/plan",
            json={**VALID_PLAN_BODY_TEMPLATE, "child_id": profile["id"]},
            headers=headers,
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        # 바깥 래핑
        assert "error" in body
        outer_message = body["error"]["message"]
        # inner code 가 dict 로 내려와야 mobile parseErrorBody 가
        # innerCode = "REJECTED_INTENT" 를 추출할 수 있다.
        assert isinstance(outer_message, dict), (
            f"REJECTED_INTENT 는 inner dict 형태여야 한다. 실제: {outer_message!r}"
        )
        assert outer_message.get("code") == "REJECTED_INTENT"
        assert isinstance(outer_message.get("message"), str)


# ===========================================================================
# 3. JWT 만료 시나리오
# ===========================================================================


class TestExpiredJWTContract:
    """모바일이 JWT 만료 상태로 서버에 도달했을 때 401 + 래핑 envelope 로
    응답해야 한다. 그래야 `ApiClientError(status=401)` 로 분기해 재로그인
    유도가 동작한다(client.ts 전반의 401 처리 경로).
    """

    @pytest.mark.asyncio()
    async def test_expired_token_at_plan_returns_401(self, client: AsyncClient) -> None:
        """만료된 토큰으로 POST /stories/plan → 401."""
        expired = _expired_access_token(user_id=str(uuid.uuid4()))
        resp = await client.post(
            "/stories/plan",
            json={
                **VALID_PLAN_BODY_TEMPLATE,
                "child_id": str(uuid.uuid4()),
            },
            headers=_auth_header(expired),
        )
        assert resp.status_code == 401, resp.text
        body = resp.json()
        assert "error" in body

    @pytest.mark.asyncio()
    async def test_expired_token_at_polling_returns_401(
        self, client: AsyncClient
    ) -> None:
        """정상 로그인으로 잡을 시작한 후 폴링 단계에서 만료된 토큰으로 바꾸면 401.

        모바일 GenerationScreen 의 폴링 루프 중 토큰이 만료되는 실제 시나리오를
        contract 수준에서 재현.
        """
        tokens = await _login(client, "expired-poll")
        fresh_headers = _auth_header(tokens["access_token"])
        profile = await _create_profile(client, fresh_headers)

        generate_body = {
            "confirmed_plan": SAMPLE_SCENE_PLAN.model_dump(),
            "child": {
                "child_id": profile["id"],
                "name": profile["name"],
                "age": profile["age"],
                "gender": profile["gender"],
                "comfort_object": profile["comfort_object"],
                "friend_name": profile["friend_name"],
                "favorite_animal": profile["favorite_animal"],
            },
            "style": "watercolor",
        }
        gen_resp = await client.post(
            "/stories/generate", json=generate_body, headers=fresh_headers
        )
        assert gen_resp.status_code == 202
        job_id = gen_resp.json()["job_id"]

        # 이제 만료된 토큰으로 폴링
        expired = _expired_access_token(user_id=str(uuid.uuid4()))
        poll_resp = await client.get(
            f"/stories/jobs/{job_id}", headers=_auth_header(expired)
        )
        assert poll_resp.status_code == 401
        body = poll_resp.json()
        assert "error" in body


# ===========================================================================
# 4. 소유자 검증 — 남의 스토리/프로필은 404 로 통일
# ===========================================================================


class TestOwnershipContract:
    """다른 사용자의 리소스는 401 이 아닌 404 로 응답해야 한다(소유자 정보
    노출 방지). mobile ViewerScreen/LibraryScreen 은 404 를 "없는 스토리" 로
    처리하고 401 은 재로그인으로 분기하므로 이 구분이 깨지면 UX 가 뒤집힌다.
    """

    @pytest.mark.asyncio()
    async def test_other_users_story_returns_404(self, client: AsyncClient) -> None:
        """사용자 A가 생성한 스토리를 사용자 B가 조회 시도 → 404."""
        # 사용자 A: 로그인 → 프로필 → 스토리 생성
        tokens_a = await _login(client, "owner-a")
        headers_a = _auth_header(tokens_a["access_token"])
        profile_a = await _create_profile(client, headers_a)

        generate_body = {
            "confirmed_plan": SAMPLE_SCENE_PLAN.model_dump(),
            "child": {
                "child_id": profile_a["id"],
                "name": profile_a["name"],
                "age": profile_a["age"],
                "gender": profile_a["gender"],
                "comfort_object": profile_a["comfort_object"],
                "friend_name": profile_a["friend_name"],
                "favorite_animal": profile_a["favorite_animal"],
            },
            "style": "watercolor",
        }
        gen_resp = await client.post(
            "/stories/generate", json=generate_body, headers=headers_a
        )
        assert gen_resp.status_code == 202
        job_id = gen_resp.json()["job_id"]
        snapshot = await _poll_until_completed(client, job_id, headers_a)
        story_id = snapshot["story_id"]

        # 사용자 B: 다른 계정으로 로그인 → A의 스토리 조회 시도
        tokens_b = await _login(client, "owner-b")
        headers_b = _auth_header(tokens_b["access_token"])

        get_resp = await client.get(f"/stories/{story_id}", headers=headers_b)
        assert get_resp.status_code == 404
        body = get_resp.json()
        assert "error" in body

        # 삭제도 시도 → 동일하게 404 (권한 부재 노출 금지)
        del_resp = await client.delete(f"/stories/{story_id}", headers=headers_b)
        assert del_resp.status_code == 404

        # A 가 자신의 스토리를 여전히 볼 수 있음 (B의 404 시도가 원본을 건드리지 않음)
        verify_resp = await client.get(f"/stories/{story_id}", headers=headers_a)
        assert verify_resp.status_code == 200


# ===========================================================================
# 5. DELETE 의 멱등성 — mobile LibraryScreen/ViewerScreen 404 처리 가정
# ===========================================================================


class TestDeleteIdempotencyContract:
    """mobile LibraryScreen 의 long-press 삭제 + ViewerScreen 의 헤더 삭제 CTA
    는 모두 404 를 "이미 삭제된 것" 으로 동일 처리한다(session log S34 참조).
    서버가 두 번째 DELETE 를 404 로 돌려주지 않으면 이 가정이 깨진다.
    """

    @pytest.mark.asyncio()
    async def test_delete_twice_second_is_404(self, client: AsyncClient) -> None:
        """동일 스토리를 두 번 DELETE → 첫 번째 204, 두 번째 404."""
        tokens = await _login(client, "idempotent-delete")
        headers = _auth_header(tokens["access_token"])
        profile = await _create_profile(client, headers)

        generate_body = {
            "confirmed_plan": SAMPLE_SCENE_PLAN.model_dump(),
            "child": {
                "child_id": profile["id"],
                "name": profile["name"],
                "age": profile["age"],
                "gender": profile["gender"],
                "comfort_object": profile["comfort_object"],
                "friend_name": profile["friend_name"],
                "favorite_animal": profile["favorite_animal"],
            },
            "style": "watercolor",
        }
        gen_resp = await client.post(
            "/stories/generate", json=generate_body, headers=headers
        )
        assert gen_resp.status_code == 202
        snapshot = await _poll_until_completed(
            client, gen_resp.json()["job_id"], headers
        )
        story_id = snapshot["story_id"]

        first = await client.delete(f"/stories/{story_id}", headers=headers)
        assert first.status_code == 204

        second = await client.delete(f"/stories/{story_id}", headers=headers)
        assert second.status_code == 404
        body = second.json()
        assert "error" in body
