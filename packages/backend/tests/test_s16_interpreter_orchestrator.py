"""S16 — 인터프리터 통합 E2E 테스트.

인터프리터 오케스트레이션: 의도분석 → 장면설계 → 미리보기 → 수정 → 확정.
모든 LLM 호출을 모킹한 단위 테스트 + 실제 API E2E 통합 테스트.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from storytale.interpreter.intent_analyzer import IntentAnalysis, IntentAnalyzer
from storytale.interpreter.interpreter_orchestrator import (
    ArcNotFoundError,
    InterpreterOrchestrator,
    MaxRevisionsError,
    resolve_age_group,
)
from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.plan_reviser import PlanReviser
from storytale.interpreter.preview_generator import (
    PreviewGenerator,
    StoryPreview,
)
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlan,
    ScenePlanner,
    StyleNotes,
)

# ---------------------------------------------------------------------------
# 공통 픽스처 데이터
# ---------------------------------------------------------------------------

SAMPLE_ARC_TEMPLATES = [
    {
        "arc_id": "gentle_resolution",
        "description": "부드러운 문제 해결형",
        "target_ages": ["3-4", "5-6"],
        "stages": [
            {"phase": "공감", "ratio": 0.2, "purpose": "감정 반영"},
            {"phase": "전환점", "ratio": 0.15, "purpose": "시선 전환"},
            {"phase": "시도", "ratio": 0.25, "purpose": "행동 변화"},
            {"phase": "재시도", "ratio": 0.2, "purpose": "성장"},
            {"phase": "수용", "ratio": 0.2, "purpose": "감정 수용"},
        ],
        "rules": ["문제가 한 번에 해결되면 안 됨"],
    },
    {
        "arc_id": "courage_building",
        "description": "용기 축적형",
        "target_ages": ["3-4", "5-6", "7-8"],
        "stages": [],
        "rules": [],
    },
]

SAMPLE_AGE_STYLE_GUIDES = [
    {
        "age_group": "3-4",
        "sentence_rules": {},
        "emotional_expression": {},
        "page_guidelines": {
            "sentences_per_page": {"min": 2, "max": 3},
            "max_characters_per_page": 50,
            "total_pages": {"min": 8, "max": 12},
        },
    },
    {
        "age_group": "5-6",
        "sentence_rules": {},
        "emotional_expression": {},
        "page_guidelines": {
            "sentences_per_page": {"min": 3, "max": 4},
            "max_characters_per_page": 70,
            "total_pages": {"min": 10, "max": 14},
        },
    },
    {
        "age_group": "7-8",
        "sentence_rules": {},
        "emotional_expression": {},
        "page_guidelines": {
            "sentences_per_page": {"min": 3, "max": 5},
            "max_characters_per_page": 90,
            "total_pages": {"min": 12, "max": 16},
        },
    },
]

SAMPLE_SAFETY_RAILS = {
    "prohibitions": ["폭력적 해결 방식"],
    "required_elements": ["comfort_object 등장"],
    "content_filter": {
        "description": "테스트용 필터",
        "exact_block": [],
        "pattern_block": [
            {"pattern": "죽이고|죽이는|죽이자|죽여", "intent": "살해 표현"},
            {"pattern": "죽어|죽겠어|죽을래", "intent": "죽음 표현"},
        ],
        "allowlist": [],
    },
}

SAMPLE_INTENT = IntentAnalysis(
    intent_category="problem_solving",
    core_theme="패배 수용",
    trigger_situation="게임에서 지는 상황",
    child_current_behavior="지면 많이 움",
    parent_desired_outcome="지고도 괜찮다고 느끼길",
    emotional_keywords=["좌절", "분노", "울음"],
    recommended_arc_id="gentle_resolution",
)

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
            scene_id="attempt",
            emotion="설렘",
            purpose="행동 변화",
            description="서준이와 함께 다시 도전해봅니다.",
            child_elements=["friend_name과 함께 도전", "comfort_object가 용기를 줌"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 응원하는",
        avoid=["승패를 강조하는 표현", "무조건 이겨야 한다는 메시지"],
        repetition_motif="넘어져도 괜찮아",
    ),
)

SAMPLE_PREVIEW = StoryPreview(
    title="하은이의 용기 대모험",
    summary="게임에서 졌을 때 속상했던 하은이가 용기를 내는 이야기예요.",
    scene_highlights=[
        "😢 속상한 하은이",
        "🐰 넘어져도 일어나는 토끼",
        "💪 함께 도전하는 하은이",
    ],
    page_count=3,
    style="watercolor",
)

REVISED_SCENE_PLAN = ScenePlan(
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
            description="서준이가 넘어졌다가 다시 일어나는 모습을 봅니다.",
            child_elements=["friend_name이 직접 등장"],
        ),
        PlannedScene(
            scene_id="attempt",
            emotion="설렘",
            purpose="행동 변화",
            description="서준이와 함께 다시 도전해봅니다.",
            child_elements=["friend_name과 함께 도전", "comfort_object가 용기를 줌"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 응원하는",
        avoid=["승패를 강조하는 표현", "무조건 이겨야 한다는 메시지"],
        repetition_motif="넘어져도 괜찮아",
    ),
)


# ---------------------------------------------------------------------------
# resolve_age_group 테스트
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "age,expected",
    [
        (2, "3-4"),
        (3, "3-4"),
        (4, "3-4"),
        (5, "5-6"),
        (6, "5-6"),
        (7, "7-8"),
        (8, "7-8"),
        (9, "7-8"),
    ],
)
def test_resolve_age_group(age: int, expected: str) -> None:
    """나이 → AgeGroup 매핑이 올바르다."""
    assert resolve_age_group(age) == expected


# ---------------------------------------------------------------------------
# 모킹 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_analyzer() -> IntentAnalyzer:
    analyzer = MagicMock(spec=IntentAnalyzer)
    analyzer.analyze = AsyncMock(return_value=SAMPLE_INTENT)
    return analyzer


@pytest.fixture()
def mock_planner() -> ScenePlanner:
    planner = MagicMock(spec=ScenePlanner)
    planner.generate = AsyncMock(return_value=SAMPLE_SCENE_PLAN)
    return planner


@pytest.fixture()
def mock_reviser() -> PlanReviser:
    reviser = MagicMock(spec=PlanReviser)
    reviser.revise = AsyncMock(return_value=REVISED_SCENE_PLAN)
    return reviser


@pytest.fixture()
def mock_preview_gen() -> PreviewGenerator:
    gen = MagicMock(spec=PreviewGenerator)
    gen.generate = AsyncMock(return_value=SAMPLE_PREVIEW)
    return gen


@pytest.fixture()
def orchestrator(
    mock_analyzer: IntentAnalyzer,
    mock_planner: ScenePlanner,
    mock_reviser: PlanReviser,
    mock_preview_gen: PreviewGenerator,
) -> InterpreterOrchestrator:
    return InterpreterOrchestrator(
        intent_analyzer=mock_analyzer,
        scene_planner=mock_planner,
        plan_reviser=mock_reviser,
        preview_generator=mock_preview_gen,
        arc_templates=SAMPLE_ARC_TEMPLATES,
        age_style_guides=SAMPLE_AGE_STYLE_GUIDES,
        safety_rails=SAMPLE_SAFETY_RAILS,
    )


# ---------------------------------------------------------------------------
# interpret_and_plan 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interpret_and_plan_returns_scene_plan(
    orchestrator: InterpreterOrchestrator,
    mock_analyzer: IntentAnalyzer,
    mock_planner: ScenePlanner,
) -> None:
    """의도분석 → 장면설계 전체 흐름이 ScenePlan을 반환한다."""
    result = await orchestrator.interpret_and_plan(
        parent_text="게임에서 지면 많이 울어요",
        purpose_category="problem_solving",
        child_age=4,
    )

    assert isinstance(result, ScenePlan)
    assert result.title == "하은이의 용기 대모험"
    mock_analyzer.analyze.assert_called_once_with(
        "게임에서 지면 많이 울어요", "problem_solving", 4
    )
    mock_planner.generate.assert_called_once()


@pytest.mark.asyncio
async def test_interpret_and_plan_resolves_age_group(
    orchestrator: InterpreterOrchestrator,
    mock_planner: ScenePlanner,
) -> None:
    """child_age=5 → age_group '5-6' 스타일 가이드가 ScenePlanner에 전달된다."""
    await orchestrator.interpret_and_plan(
        parent_text="공룡을 좋아해요",
        purpose_category="interest_story",
        child_age=5,
    )

    call_args = mock_planner.generate.call_args
    age_style = call_args.kwargs["age_style"]
    assert age_style["age_group"] == "5-6"


@pytest.mark.asyncio
async def test_interpret_and_plan_selects_matching_arc(
    orchestrator: InterpreterOrchestrator,
    mock_planner: ScenePlanner,
) -> None:
    """recommended_arc_id로 올바른 arc_template을 찾아 전달한다."""
    await orchestrator.interpret_and_plan(
        parent_text="게임에서 지면 많이 울어요",
        purpose_category="problem_solving",
        child_age=4,
    )

    call_args = mock_planner.generate.call_args
    arc_template = call_args.kwargs["arc_template"]
    assert arc_template["arc_id"] == "gentle_resolution"


@pytest.mark.asyncio
async def test_interpret_and_plan_passes_safety_rails(
    orchestrator: InterpreterOrchestrator,
    mock_planner: ScenePlanner,
) -> None:
    """safety_rails가 ScenePlanner에 전달된다."""
    await orchestrator.interpret_and_plan(
        parent_text="용기를 갖고 싶어요",
        purpose_category="value_teaching",
        child_age=4,
    )

    call_args = mock_planner.generate.call_args
    safety = call_args.kwargs["safety_rails"]
    assert safety == SAMPLE_SAFETY_RAILS


@pytest.mark.asyncio
async def test_interpret_and_plan_arc_not_found(
    orchestrator: InterpreterOrchestrator,
    mock_analyzer: IntentAnalyzer,
) -> None:
    """존재하지 않는 arc_id → ArcNotFoundError 발생."""
    bad_intent = IntentAnalysis(
        intent_category="problem_solving",
        core_theme="테스트",
        trigger_situation="테스트",
        child_current_behavior="테스트",
        parent_desired_outcome="테스트",
        emotional_keywords=["테스트"],
        recommended_arc_id="nonexistent_arc",
    )
    mock_analyzer.analyze = AsyncMock(return_value=bad_intent)

    with pytest.raises(ArcNotFoundError):
        await orchestrator.interpret_and_plan(
            parent_text="테스트", purpose_category="problem_solving", child_age=4
        )


# ---------------------------------------------------------------------------
# get_preview 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_preview_returns_story_preview(
    orchestrator: InterpreterOrchestrator,
    mock_preview_gen: PreviewGenerator,
) -> None:
    """ScenePlan → StoryPreview 반환."""
    result = await orchestrator.get_preview(
        SAMPLE_SCENE_PLAN, style="watercolor", child_name="하은이"
    )

    assert isinstance(result, StoryPreview)
    mock_preview_gen.generate.assert_called_once_with(
        SAMPLE_SCENE_PLAN, "watercolor", child_name="하은이"
    )


# ---------------------------------------------------------------------------
# revise_plan 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_plan_returns_revised_plan(
    orchestrator: InterpreterOrchestrator,
) -> None:
    """수정 요청 → 수정된 ScenePlan 반환."""
    result = await orchestrator.revise_plan(
        SAMPLE_SCENE_PLAN, "토끼 대신 서준이가 나왔으면 좋겠어요"
    )

    assert isinstance(result, ScenePlan)


@pytest.mark.asyncio
async def test_revise_plan_passes_safety_rails(
    orchestrator: InterpreterOrchestrator,
    mock_reviser: PlanReviser,
) -> None:
    """PlanReviser에 safety_rails가 전달된다."""
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정해주세요")

    call_args = mock_reviser.revise.call_args
    safety = call_args.kwargs["safety_rails"]
    assert "prohibitions" in safety


@pytest.mark.asyncio
async def test_revise_plan_max_3_times(
    orchestrator: InterpreterOrchestrator,
) -> None:
    """최대 3회 수정 후 4번째는 MaxRevisionsError 발생."""
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정1")
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정2")
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정3")

    with pytest.raises(MaxRevisionsError):
        await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정4")


@pytest.mark.asyncio
async def test_revision_counter_resets_on_new_plan(
    orchestrator: InterpreterOrchestrator,
) -> None:
    """새로운 interpret_and_plan 호출 후 수정 카운터가 리셋된다."""
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정1")
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정2")
    await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정3")

    # 새 플랜 생성 → 카운터 리셋
    await orchestrator.interpret_and_plan(
        parent_text="새 이야기",
        purpose_category="interest_story",
        child_age=4,
    )

    # 다시 수정 가능해야 함
    result = await orchestrator.revise_plan(SAMPLE_SCENE_PLAN, "수정A")
    assert isinstance(result, ScenePlan)


# ---------------------------------------------------------------------------
# 전체 E2E 플로우 테스트 (모킹)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_e2e_flow(
    orchestrator: InterpreterOrchestrator,
) -> None:
    """전체 흐름: 의도분석 → 장면설계 → 미리보기 → 수정 → 재미리보기."""
    # Step 1: 의도분석 + 장면설계
    plan = await orchestrator.interpret_and_plan(
        parent_text="게임에서 지면 많이 울어요",
        purpose_category="problem_solving",
        child_age=4,
    )
    assert isinstance(plan, ScenePlan)

    # Step 2: 미리보기
    preview = await orchestrator.get_preview(
        plan, style="watercolor", child_name="하은이"
    )
    assert isinstance(preview, StoryPreview)

    # Step 3: 수정
    revised = await orchestrator.revise_plan(plan, "토끼 대신 서준이가 나왔으면")
    assert isinstance(revised, ScenePlan)

    # Step 4: 수정 후 재미리보기
    preview2 = await orchestrator.get_preview(
        revised, style="watercolor", child_name="하은이"
    )
    assert isinstance(preview2, StoryPreview)


# ---------------------------------------------------------------------------
# 통합 테스트 — 실제 Claude API E2E
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_interpreter_e2e_integration() -> None:
    """실제 Claude API로 전체 인터프리터 플로우 (CLAUDE_API_KEY 필요)."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY not set")

    llm_client = LLMClient(api_key=api_key)
    arc_templates = IntentAnalyzer.load_arc_templates_from_json()

    import json
    import pathlib

    project_root = pathlib.Path(__file__).parent.parent.parent.parent
    guides_path = project_root / "docs" / "guardrail-seeds" / "age-style-guides.json"
    safety_path = project_root / "docs" / "guardrail-seeds" / "safety-rails.json"

    with guides_path.open(encoding="utf-8") as f:
        age_style_guides = json.load(f)
    with safety_path.open(encoding="utf-8") as f:
        safety_rails = json.load(f)

    analyzer = IntentAnalyzer(llm_client=llm_client, arc_templates=arc_templates)
    planner = ScenePlanner(llm_client=llm_client)
    reviser = PlanReviser(llm_client=llm_client)
    preview_gen = PreviewGenerator(llm_client=llm_client)

    orch = InterpreterOrchestrator(
        intent_analyzer=analyzer,
        scene_planner=planner,
        plan_reviser=reviser,
        preview_generator=preview_gen,
        arc_templates=arc_templates,
        age_style_guides=age_style_guides,
        safety_rails=safety_rails,
    )

    # 전체 플로우
    plan = await orch.interpret_and_plan(
        parent_text="게임에서 지면 많이 울어요",
        purpose_category="problem_solving",
        child_age=4,
    )
    assert isinstance(plan, ScenePlan)
    assert len(plan.scenes) >= 8

    preview = await orch.get_preview(plan, style="watercolor", child_name="하은이")
    assert isinstance(preview, StoryPreview)
    assert len(preview.summary) > 0
