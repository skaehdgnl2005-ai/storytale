"""스토리 생성/저장/조회 API 라우터 (S19 + S20 + S30a).

POST /stories/plan → 부모 텍스트 + 목적 + child → ScenePlan + StoryPreview (S30a).
POST /stories/generate → 202 + jobId (BackgroundTasks로 비동기 생성).
GET  /stories/jobs/{job_id} → 진행률 + 완료된 장면 목록.
GET  /stories/jobs/{job_id}/stream → SSE 스트리밍.
GET  /stories → 스토리 목록 (페이지네이션).
GET  /stories/{story_id} → 스토리 상세 + 페이지.
"""

import asyncio
import json
import json as json_mod
import logging
import uuid
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from storytale.api.auth_router import CurrentUserDep
from storytale.api.dependencies import get_db
from storytale.db.models import ChildProfile as ChildProfileModel
from storytale.db.models import Story as StoryModel
from storytale.db.models import StoryPage as StoryPageModel
from storytale.interpreter.intent_analyzer import IntentAnalyzer, RejectedIntentError
from storytale.interpreter.llm_client import create_llm_client
from storytale.interpreter.plan_reviser import PlanReviser
from storytale.interpreter.preview_generator import PreviewGenerator, StoryPreview
from storytale.interpreter.scene_planner import ScenePlan, ScenePlanner
from storytale.interpreter.story_orchestrator import StoryOrchestrator
from storytale.interpreter.story_personalizer import ChildProfile, StoryPersonalizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stories", tags=["stories"])


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

MIN_CHILD_AGE = 1
MAX_CHILD_AGE = 12
VALID_STYLES = {"watercolor", "pastel_crayon", "clean_digital"}

# 가드레일 시드 데이터 경로
_SEEDS_DIR = Path(__file__).resolve().parents[6] / "docs" / "guardrail-seeds"


@lru_cache(maxsize=1)
def _load_guardrail_data() -> tuple[list[dict], list[dict], dict]:
    """가드레일 JSON 파일을 로드한다. 최초 1회만 로드."""
    with (_SEEDS_DIR / "emotional-arcs.json").open(encoding="utf-8") as f:
        arc_templates = json.load(f)
    with (_SEEDS_DIR / "age-style-guides.json").open(encoding="utf-8") as f:
        age_style_guides = json.load(f)
    with (_SEEDS_DIR / "safety-rails.json").open(encoding="utf-8") as f:
        safety_rails = json.load(f)
    return arc_templates, age_style_guides, safety_rails


# ---------------------------------------------------------------------------
# 요청/응답 모델
# ---------------------------------------------------------------------------


class ChildInput(BaseModel):
    """스토리 생성용 아이 정보."""

    child_id: str
    name: str
    age: int = Field(ge=MIN_CHILD_AGE, le=MAX_CHILD_AGE)
    gender: str
    comfort_object: str | None = None
    friend_name: str | None = None
    favorite_animal: str | None = None


class GenerateStoryRequest(BaseModel):
    """스토리 생성 요청. 부모가 확정한 ScenePlan + 아이 정보 + 스타일."""

    confirmed_plan: ScenePlan
    child: ChildInput
    style: str
    user_id: str | None = None  # JWT 인증 시 무시됨. 하위 호환용.

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        if v not in VALID_STYLES:
            msg = f"style은 {VALID_STYLES} 중 하나여야 합니다."
            raise ValueError(msg)
        return v


# S30a — 부모 서술형 입력으로부터 ScenePlan + StoryPreview를 만드는 엔드포인트
# (Phase A + B 노출). 모바일 서술형 입력 화면(S30b)이 호출한다.

# IntentCategory: contracts/story-engine.ts 와 1:1 매핑.
IntentCategory = Literal[
    "value_teaching",
    "interest_story",
    "problem_solving",
    "celebration",
]

# security.md: 부모 서술형 입력은 최대 500자.
PARENT_TEXT_MAX_LENGTH = 500

# S31에서 부모가 명시적으로 스타일을 고를 때까지 사용할 미리보기 기본값.
DEFAULT_PREVIEW_STYLE = "watercolor"


class PlanStoryRequest(BaseModel):
    """부모 서술형 입력 → ScenePlan 생성 요청."""

    parent_text: str = Field(
        min_length=1,
        max_length=PARENT_TEXT_MAX_LENGTH,
    )
    purpose_category: IntentCategory
    child_id: str


class PlanStoryResponse(BaseModel):
    """ScenePlan + 부모 미리보기 응답.

    S30(서술형 입력) 화면에서 받아 그대로 S31(미리보기/수정) 화면에 전달한다.
    style은 S31에서 부모가 확정하므로 여기서는 기본값(watercolor)이 사용된다.
    """

    plan: ScenePlan
    preview: StoryPreview


class GenerateStoryResponse(BaseModel):
    """생성 요청 응답."""

    job_id: str


class JobStatusResponse(BaseModel):
    """잡 상태 응답."""

    job_id: str
    status: str
    total_scenes: int
    completed_scenes: int
    scenes: list[dict[str, Any]]
    error: str | None = None
    story_id: str | None = None


# S20: 스토리 조회 응답 모델


class StoryPageResponse(BaseModel):
    """스토리 페이지 응답."""

    id: str
    page_number: int
    scene_id: str
    text: str
    illustration_prompt: str
    illustration_url: str | None = None


class StoryDetailResponse(BaseModel):
    """스토리 상세 응답."""

    id: str
    title: str
    status: str
    style: str
    created_at: str
    page_count: int
    pages: list[StoryPageResponse]


class StoryListItem(BaseModel):
    """스토리 목록 항목."""

    id: str
    title: str
    status: str
    style: str
    created_at: str
    page_count: int


class StoryListResponse(BaseModel):
    """스토리 목록 응답."""

    items: list[StoryListItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# 잡 매니저 (인메모리 MVP)
# ---------------------------------------------------------------------------


class JobStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class JobState:
    """단일 잡의 상태."""

    def __init__(self, job_id: str, total_scenes: int) -> None:
        self.job_id = job_id
        self.status = JobStatus.PENDING
        self.total_scenes = total_scenes
        self.completed_scenes = 0
        self.scenes: list[dict[str, Any]] = []
        self.error: str | None = None
        self.story_id: str | None = None
        self.event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def to_response(self) -> JobStatusResponse:
        return JobStatusResponse(
            job_id=self.job_id,
            status=self.status.value,
            total_scenes=self.total_scenes,
            completed_scenes=self.completed_scenes,
            scenes=self.scenes,
            error=self.error,
            story_id=self.story_id,
        )


class JobManager:
    """인메모리 잡 상태 관리. MVP용. 프로덕션은 Redis로 전환."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def create_job(self, total_scenes: int) -> JobState:
        job_id = str(uuid.uuid4())
        job = JobState(job_id=job_id, total_scenes=total_scenes)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    def clear(self) -> None:
        self._jobs.clear()


# 모듈 수준 싱글턴 (테스트에서 주입 가능)
job_manager = JobManager()


# ---------------------------------------------------------------------------
# 의존성
# ---------------------------------------------------------------------------


async def get_story_orchestrator() -> StoryOrchestrator:
    """StoryOrchestrator 의존성.

    create_llm_client()를 사용하여 Gemini fallback을 자동 연결하고,
    가드레일 시드 데이터를 로드하여 전체 파이프라인을 조립한다.
    테스트에서는 app.dependency_overrides로 오버라이드 가능.
    """
    arc_templates, age_style_guides, safety_rails = _load_guardrail_data()
    llm_client = create_llm_client()

    from storytale.interpreter.interpreter_orchestrator import (
        InterpreterOrchestrator,
    )

    interpreter = InterpreterOrchestrator(
        intent_analyzer=IntentAnalyzer(llm_client, arc_templates),
        scene_planner=ScenePlanner(llm_client),
        plan_reviser=PlanReviser(llm_client),
        preview_generator=PreviewGenerator(llm_client),
        arc_templates=arc_templates,
        age_style_guides=age_style_guides,
        safety_rails=safety_rails,
    )
    personalizer = StoryPersonalizer(llm_client)

    return StoryOrchestrator(
        interpreter=interpreter,
        personalizer=personalizer,
        age_style_guides=age_style_guides,
    )


async def get_session_factory() -> async_sessionmaker:
    """세션 팩토리 의존성. 백그라운드 태스크 DB 접근용. 테스트에서 오버라이드."""
    from storytale.db.session import AsyncSessionLocal

    return AsyncSessionLocal


OrchestratorDep = Annotated[StoryOrchestrator, Depends(get_story_orchestrator)]
SessionFactoryDep = Annotated[async_sessionmaker, Depends(get_session_factory)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# DB 저장 (S20)
# ---------------------------------------------------------------------------


async def _save_story_to_db(
    session_factory: async_sessionmaker,
    user_id: str,
    child_id: str,
    confirmed_plan: ScenePlan,
    style: str,
    scenes: list[dict[str, Any]],
) -> str:
    """생성 완료된 스토리를 Story + StoryPage DB에 저장한다."""
    story_id = uuid.uuid4()

    async with session_factory() as session:
        story = StoryModel(
            id=story_id,
            user_id=uuid.UUID(user_id),
            child_id=uuid.UUID(child_id),
            scene_plan=confirmed_plan.model_dump(),
            status="completed",
            style=style,
        )
        session.add(story)

        for scene_data in scenes:
            page = StoryPageModel(
                story_id=story_id,
                page_number=scene_data["page_number"],
                scene_id=scene_data["scene_id"],
                text=scene_data["text"],
                illustration_prompt=scene_data["illustration_prompt"],
            )
            session.add(page)

        await session.commit()

    return str(story_id)


# ---------------------------------------------------------------------------
# 백그라운드 생성 태스크
# ---------------------------------------------------------------------------


async def _run_generation(
    job: JobState,
    orchestrator: StoryOrchestrator,
    confirmed_plan: ScenePlan,
    child: ChildProfile,
    style: str,
    user_id: str | None = None,
    child_id: str | None = None,
    session_factory: async_sessionmaker | None = None,
) -> None:
    """백그라운드에서 장면별 텍스트를 생성하고 잡 상태를 갱신한다."""
    job.status = JobStatus.IN_PROGRESS

    try:
        async for scene in orchestrator.generate_story(
            confirmed_plan=confirmed_plan, child=child, style=style
        ):
            scene_data = scene.model_dump()
            job.scenes.append(scene_data)
            job.completed_scenes += 1

            # SSE 이벤트 발행
            await job.event_queue.put(
                {"event": "scene_complete", "scene_id": scene.scene_id, **scene_data}
            )

            logger.info(
                "job=%s scene_complete scene_id=%s (%d/%d)",
                job.job_id,
                scene.scene_id,
                job.completed_scenes,
                job.total_scenes,
            )

        # S20: DB 저장
        if user_id and child_id and session_factory:
            job.story_id = await _save_story_to_db(
                session_factory=session_factory,
                user_id=user_id,
                child_id=child_id,
                confirmed_plan=confirmed_plan,
                style=style,
                scenes=job.scenes,
            )

        job.status = JobStatus.COMPLETED
        await job.event_queue.put({"event": "complete"})

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        await job.event_queue.put({"event": "error", "message": str(exc)})
        logger.error("job=%s generation_failed: %s", job.job_id, exc)


# ---------------------------------------------------------------------------
# 헬퍼 (S30a)
# ---------------------------------------------------------------------------


async def _load_owned_child_profile(
    db: AsyncSession,
    user_id: str,
    child_id: str,
) -> ChildProfileModel:
    """child_id를 받아 본인 소유의 ChildProfile DB 행을 반환한다.

    소유자가 아니거나 존재하지 않으면 404를 던진다 (정보 노출 방지를 위해
    "존재하지 않음"과 "다른 사용자의 것"을 동일하게 처리).
    UUID 형식이 아닌 child_id도 404로 처리 (S20 패턴 일치).
    """
    try:
        child_uuid = uuid.UUID(child_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=404, detail="아이 프로필을 찾을 수 없어요"
        ) from None

    result = await db.execute(
        select(ChildProfileModel).where(ChildProfileModel.id == child_uuid)
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.user_id != user_uuid:
        raise HTTPException(status_code=404, detail="아이 프로필을 찾을 수 없어요")

    return profile


def _to_interpreter_child(profile: ChildProfileModel) -> ChildProfile:
    """DB ChildProfile → interpreter 도메인 ChildProfile 매핑."""
    return ChildProfile(
        child_id=str(profile.id),
        name=profile.name,
        age=profile.age,
        gender=profile.gender,
        comfort_object=profile.comfort_object,
        friend_name=profile.friend_name,
        favorite_animal=profile.favorite_animal,
    )


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.post("/plan", response_model=PlanStoryResponse)
async def plan_story(
    request: PlanStoryRequest,
    orchestrator: OrchestratorDep,
    db: DbDep,
    current_user_id: CurrentUserDep,
) -> PlanStoryResponse:
    """부모 서술형 텍스트 → ScenePlan + StoryPreview (S30a).

    S30(서술형 입력) 화면이 호출. 응답은 그대로 S31(미리보기/수정) 화면에 전달된다.
    style은 S31에서 부모가 확정하므로 미리보기에는 기본값(watercolor)이 사용된다.
    """
    profile = await _load_owned_child_profile(
        db=db, user_id=current_user_id, child_id=request.child_id
    )
    child = _to_interpreter_child(profile)

    try:
        plan = await orchestrator.interpret_and_plan(
            parent_text=request.parent_text,
            purpose_category=request.purpose_category,
            child=child,
        )
        preview = await orchestrator.get_preview(
            plan=plan,
            style=DEFAULT_PREVIEW_STYLE,
            child_name=child.name,
        )
    except RejectedIntentError as exc:
        # api-conventions.md: {"detail": "...", "code": "ERROR_CODE"}
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "code": "REJECTED_INTENT"},
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("plan_story_failed user_id=%s", current_user_id)
        raise HTTPException(
            status_code=500,
            detail="이야기 설계 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.",
        ) from exc

    logger.info(
        "plan_story_done user_id=%s child_id=%s purpose=%s scenes=%d",
        current_user_id,
        request.child_id,
        request.purpose_category,
        len(plan.scenes),
    )
    return PlanStoryResponse(plan=plan, preview=preview)


@router.post("/generate", status_code=202, response_model=GenerateStoryResponse)
async def generate_story(
    request: GenerateStoryRequest,
    background_tasks: BackgroundTasks,
    orchestrator: OrchestratorDep,
    session_factory: SessionFactoryDep,
    current_user_id: CurrentUserDep,
) -> GenerateStoryResponse:
    """스토리 생성을 시작한다. 202 + jobId 반환. JWT 인증 필수."""
    # ChildInput → ChildProfile 변환
    child = ChildProfile(
        child_id=request.child.child_id,
        name=request.child.name,
        age=request.child.age,
        gender=request.child.gender,
        comfort_object=request.child.comfort_object,
        friend_name=request.child.friend_name,
        favorite_animal=request.child.favorite_animal,
    )

    total_scenes = len(request.confirmed_plan.scenes)
    job = job_manager.create_job(total_scenes=total_scenes)

    # JWT에서 추출한 user_id 사용 (요청 바디의 user_id 무시)
    background_tasks.add_task(
        _run_generation,
        job=job,
        orchestrator=orchestrator,
        confirmed_plan=request.confirmed_plan,
        child=child,
        style=request.style,
        user_id=current_user_id,
        child_id=request.child.child_id,
        session_factory=session_factory,
    )

    logger.info("job_created job_id=%s total_scenes=%d", job.job_id, total_scenes)
    return GenerateStoryResponse(job_id=job.job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """잡 상태 및 진행률을 반환한다."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_response()


@router.get("/jobs/{job_id}/stream")
async def stream_job_events(job_id: str, request: Request) -> StreamingResponse:
    """SSE로 잡 이벤트를 스트리밍한다."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            # 클라이언트 연결 끊김 체크
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(job.event_queue.get(), timeout=30.0)
            except TimeoutError:
                # 킵얼라이브 코멘트
                yield ": keepalive\n\n"
                continue

            yield f"data: {json_mod.dumps(event, ensure_ascii=False)}\n\n"

            if event.get("event") in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# S20: 스토리 목록/상세 조회 엔드포인트


@router.get("", response_model=StoryListResponse)
async def list_stories(
    db: DbDep,
    current_user_id: CurrentUserDep,
    limit: int = 20,
    offset: int = 0,
) -> StoryListResponse:
    """본인의 스토리 목록을 페이지네이션으로 반환한다. JWT 인증 필수."""
    user_uuid = uuid.UUID(current_user_id)
    count_result = await db.execute(
        select(func.count())
        .select_from(StoryModel)
        .where(StoryModel.user_id == user_uuid)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(StoryModel)
        .options(selectinload(StoryModel.pages))
        .where(StoryModel.user_id == user_uuid)
        .order_by(StoryModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    stories = result.scalars().all()

    return StoryListResponse(
        items=[
            StoryListItem(
                id=str(s.id),
                title=s.scene_plan.get("title", "") if s.scene_plan else "",
                status=s.status,
                style=s.style,
                created_at=s.created_at.isoformat(),
                page_count=len(s.pages),
            )
            for s in stories
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story(
    story_id: str, db: DbDep, current_user_id: CurrentUserDep
) -> StoryDetailResponse:
    """스토리 상세 정보와 페이지를 반환한다. JWT 인증 필수 + 소유자 검증."""
    try:
        story_uuid = uuid.UUID(story_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Story not found") from None

    result = await db.execute(
        select(StoryModel)
        .options(selectinload(StoryModel.pages))
        .where(StoryModel.id == story_uuid)
    )
    story = result.scalar_one_or_none()
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")

    # 소유자 검증
    if str(story.user_id) != current_user_id:
        raise HTTPException(status_code=404, detail="Story not found")

    sorted_pages = sorted(story.pages, key=lambda p: p.page_number)

    return StoryDetailResponse(
        id=str(story.id),
        title=story.scene_plan.get("title", "") if story.scene_plan else "",
        status=story.status,
        style=story.style,
        created_at=story.created_at.isoformat(),
        page_count=len(sorted_pages),
        pages=[
            StoryPageResponse(
                id=str(p.id),
                page_number=p.page_number,
                scene_id=p.scene_id,
                text=p.text,
                illustration_prompt=p.illustration_prompt,
                illustration_url=p.illustration_url,
            )
            for p in sorted_pages
        ],
    )
