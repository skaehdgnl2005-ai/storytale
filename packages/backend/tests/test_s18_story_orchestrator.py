"""S18 — 스토리 오케스트레이터 테스트.

StoryOrchestrator: InterpreterOrchestrator(S16) + StoryPersonalizer(S17) 연결.
전체 플로우: 의도분석 → 장면설계 → 미리보기 → 수정 → 확정 → 장면별 텍스트 생성.
모든 LLM 호출을 모킹한 단위 테스트.
"""

from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.interpreter_orchestrator import (
    InterpreterOrchestrator,
    MaxRevisionsError,
)
from storytale.interpreter.preview_generator import StoryPreview
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlan,
    StyleNotes,
)
from storytale.interpreter.story_orchestrator import (
    StoryOrchestrator,
    StoryOrchestratorError,
)
from storytale.interpreter.story_personalizer import (
    ChildProfile,
    PersonalizedScene,
    StoryPersonalizer,
)

# ---------------------------------------------------------------------------
# 공통 픽스처 데이터
# ---------------------------------------------------------------------------

SAMPLE_CHILD = ChildProfile(
    child_id="child-001",
    name="하은",
    age=4,
    gender="female",
    comfort_object="토니(곰 인형)",
    friend_name="서준",
    favorite_animal="토끼",
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

SAMPLE_AGE_STYLE_GUIDES = [
    {
        "age_group": "3-4",
        "sentence_rules": {
            "max_characters_per_sentence": 20,
            "preferred_structure": "단문",
            "repetition_pattern": "AAB",
            "vocabulary_level": "일상 단어 500개 이내",
        },
        "emotional_expression": {
            "method": "의성어·의태어 활용",
            "good_examples": ["두근두근", "살금살금"],
            "bad_examples": ["불안하다", "긴장된다"],
        },
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
        "page_guidelines": {},
    },
    {
        "age_group": "7-8",
        "sentence_rules": {},
        "emotional_expression": {},
        "page_guidelines": {},
    },
]

PERSONALIZED_SCENES = [
    PersonalizedScene(
        scene_id="opening",
        page_number=1,
        text="하은이가 블록 쌓기 게임에서 졌어요.\n토니를 꼭 안았어요.",
        illustration_prompt="A young girl hugging a teddy bear, looking sad...",
    ),
    PersonalizedScene(
        scene_id="turning_point",
        page_number=2,
        text="그때, 토끼 한 마리가 풀밭에서 넘어졌어요.\n하지만 다시 일어났어요!",
        illustration_prompt="A rabbit falling then getting up in a meadow...",
    ),
    PersonalizedScene(
        scene_id="attempt",
        page_number=3,
        text='하은이는 서준이와 함께 다시 해봤어요.\n"넘어져도 괜찮아!"',
        illustration_prompt="A young girl and a boy playing together, smiling...",
    ),
]

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
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 응원하는",
        avoid=["승패를 강조하는 표현"],
        repetition_motif="넘어져도 괜찮아",
    ),
)


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_interpreter() -> AsyncMock:
    interp = AsyncMock(spec=InterpreterOrchestrator)
    interp.interpret_and_plan.return_value = SAMPLE_SCENE_PLAN
    interp.get_preview.return_value = SAMPLE_PREVIEW
    interp.revise_plan.return_value = REVISED_SCENE_PLAN
    return interp


@pytest.fixture()
def mock_personalizer() -> AsyncMock:
    personalizer = AsyncMock(spec=StoryPersonalizer)
    personalizer.generate_scene.side_effect = PERSONALIZED_SCENES
    return personalizer


@pytest.fixture()
def orchestrator(
    mock_interpreter: AsyncMock,
    mock_personalizer: AsyncMock,
) -> StoryOrchestrator:
    return StoryOrchestrator(
        interpreter=mock_interpreter,
        personalizer=mock_personalizer,
        age_style_guides=SAMPLE_AGE_STYLE_GUIDES,
    )


# ---------------------------------------------------------------------------
# Phase A: interpret_and_plan 테스트
# ---------------------------------------------------------------------------


class TestInterpretAndPlan:
    @pytest.mark.asyncio()
    async def test_delegates_to_interpreter(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """부모 텍스트 → InterpreterOrchestrator.interpret_and_plan 위임."""
        result = await orchestrator.interpret_and_plan(
            parent_text="게임에서 지면 많이 울어요",
            purpose_category="problem_solving",
            child=SAMPLE_CHILD,
        )

        assert result == SAMPLE_SCENE_PLAN
        mock_interpreter.interpret_and_plan.assert_awaited_once_with(
            parent_text="게임에서 지면 많이 울어요",
            purpose_category="problem_solving",
            child_age=SAMPLE_CHILD.age,
        )

    @pytest.mark.asyncio()
    async def test_uses_child_age(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """child.age를 interpreter에 전달한다."""
        older_child = ChildProfile(
            child_id="child-002", name="민수", age=7, gender="male"
        )
        await orchestrator.interpret_and_plan(
            parent_text="용기를 알려주고 싶어요",
            purpose_category="value_teaching",
            child=older_child,
        )

        mock_interpreter.interpret_and_plan.assert_awaited_once_with(
            parent_text="용기를 알려주고 싶어요",
            purpose_category="value_teaching",
            child_age=7,
        )


# ---------------------------------------------------------------------------
# Phase B: get_preview 테스트
# ---------------------------------------------------------------------------


class TestGetPreview:
    @pytest.mark.asyncio()
    async def test_delegates_to_interpreter(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """ScenePlan + style → InterpreterOrchestrator.get_preview 위임."""
        result = await orchestrator.get_preview(
            plan=SAMPLE_SCENE_PLAN,
            style="watercolor",
            child_name="하은",
        )

        assert result == SAMPLE_PREVIEW
        mock_interpreter.get_preview.assert_awaited_once_with(
            scene_plan=SAMPLE_SCENE_PLAN,
            style="watercolor",
            child_name="하은",
        )

    @pytest.mark.asyncio()
    async def test_child_name_optional(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """child_name 없이 호출 가능."""
        await orchestrator.get_preview(
            plan=SAMPLE_SCENE_PLAN,
            style="pastel_crayon",
        )

        mock_interpreter.get_preview.assert_awaited_once_with(
            scene_plan=SAMPLE_SCENE_PLAN,
            style="pastel_crayon",
            child_name=None,
        )


# ---------------------------------------------------------------------------
# Phase C: revise_plan 테스트
# ---------------------------------------------------------------------------


class TestRevisePlan:
    @pytest.mark.asyncio()
    async def test_delegates_to_interpreter(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """피드백 → InterpreterOrchestrator.revise_plan 위임."""
        result = await orchestrator.revise_plan(
            plan=SAMPLE_SCENE_PLAN,
            feedback="토끼 대신 서준이가 나왔으면",
        )

        assert result == REVISED_SCENE_PLAN
        mock_interpreter.revise_plan.assert_awaited_once_with(
            current_plan=SAMPLE_SCENE_PLAN,
            parent_feedback="토끼 대신 서준이가 나왔으면",
        )

    @pytest.mark.asyncio()
    async def test_max_revisions_propagated(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
    ) -> None:
        """InterpreterOrchestrator의 MaxRevisionsError가 전파된다."""
        mock_interpreter.revise_plan.side_effect = MaxRevisionsError(
            "최대 수정 횟수 초과"
        )

        with pytest.raises(MaxRevisionsError):
            await orchestrator.revise_plan(
                plan=SAMPLE_SCENE_PLAN,
                feedback="다시 수정해주세요",
            )


# ---------------------------------------------------------------------------
# Phase D: generate_story 테스트
# ---------------------------------------------------------------------------


class TestGenerateStory:
    @pytest.mark.asyncio()
    async def test_generates_all_scenes(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """confirmedPlan의 모든 장면에 대해 PersonalizedScene을 생성한다."""
        results: list[PersonalizedScene] = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        assert len(results) == 3
        assert results[0].scene_id == "opening"
        assert results[1].scene_id == "turning_point"
        assert results[2].scene_id == "attempt"

    @pytest.mark.asyncio()
    async def test_calls_personalizer_sequentially(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """StoryPersonalizer.generate_scene을 장면별로 순차 호출한다."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        assert mock_personalizer.generate_scene.await_count == 3

    @pytest.mark.asyncio()
    async def test_passes_correct_age_style(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """child.age에 맞는 age_style을 personalizer에 전달한다."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        first_call = mock_personalizer.generate_scene.call_args_list[0]
        assert first_call.kwargs["age_style"]["age_group"] == "3-4"

    @pytest.mark.asyncio()
    async def test_passes_style_notes(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """confirmed_plan의 style_notes를 personalizer에 전달한다."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        first_call = mock_personalizer.generate_scene.call_args_list[0]
        assert first_call.kwargs["style_notes"] == SAMPLE_SCENE_PLAN.style_notes

    @pytest.mark.asyncio()
    async def test_previous_summary_chain(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """첫 장면은 '없음', 이후 장면은 이전 장면 텍스트를 previous_summary로 전달."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        calls = mock_personalizer.generate_scene.call_args_list

        # 첫 장면: "없음"
        assert calls[0].kwargs["previous_summary"] == "없음"
        # 두 번째 장면: 첫 장면의 텍스트
        assert calls[1].kwargs["previous_summary"] == PERSONALIZED_SCENES[0].text
        # 세 번째 장면: 두 번째 장면의 텍스트
        assert calls[2].kwargs["previous_summary"] == PERSONALIZED_SCENES[1].text

    @pytest.mark.asyncio()
    async def test_scene_index_and_total(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """scene_index(1부터)와 total_scenes를 올바르게 전달한다."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        calls = mock_personalizer.generate_scene.call_args_list

        assert calls[0].kwargs["scene_index"] == 1
        assert calls[0].kwargs["total_scenes"] == 3
        assert calls[1].kwargs["scene_index"] == 2
        assert calls[2].kwargs["scene_index"] == 3

    @pytest.mark.asyncio()
    async def test_identity_prompt_block_none(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """S22 전이므로 identity_prompt_block은 None."""
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=SAMPLE_SCENE_PLAN,
            child=SAMPLE_CHILD,
            style="watercolor",
        ):
            results.append(scene)

        for call in mock_personalizer.generate_scene.call_args_list:
            assert call.kwargs["identity_prompt_block"] is None

    @pytest.mark.asyncio()
    async def test_older_child_gets_correct_age_style(
        self,
        mock_interpreter: AsyncMock,
        mock_personalizer: AsyncMock,
    ) -> None:
        """7세 아이 → '7-8' age_style 사용."""
        older_child = ChildProfile(
            child_id="child-002", name="민수", age=7, gender="male"
        )
        # 장면 1개짜리 plan
        short_plan = ScenePlan(
            title="민수의 모험",
            scenes=[SAMPLE_SCENE_PLAN.scenes[0]],
            style_notes=SAMPLE_SCENE_PLAN.style_notes,
        )
        mock_personalizer.generate_scene.side_effect = [PERSONALIZED_SCENES[0]]

        orch = StoryOrchestrator(
            interpreter=mock_interpreter,
            personalizer=mock_personalizer,
            age_style_guides=SAMPLE_AGE_STYLE_GUIDES,
        )

        results = []
        async for scene in orch.generate_story(
            confirmed_plan=short_plan, child=older_child, style="watercolor"
        ):
            results.append(scene)

        first_call = mock_personalizer.generate_scene.call_args_list[0]
        assert first_call.kwargs["age_style"]["age_group"] == "7-8"

    @pytest.mark.asyncio()
    async def test_personalizer_error_propagated(
        self,
        orchestrator: StoryOrchestrator,
        mock_personalizer: AsyncMock,
    ) -> None:
        """StoryPersonalizer 에러가 StoryOrchestratorError로 래핑된다."""
        mock_personalizer.generate_scene.side_effect = Exception("LLM 호출 실패")

        with pytest.raises(StoryOrchestratorError, match="opening"):
            async for _ in orchestrator.generate_story(
                confirmed_plan=SAMPLE_SCENE_PLAN,
                child=SAMPLE_CHILD,
                style="watercolor",
            ):
                pass


# ---------------------------------------------------------------------------
# E2E 통합 시나리오 (모킹)
# ---------------------------------------------------------------------------


class TestE2EFlow:
    @pytest.mark.asyncio()
    async def test_full_flow_text_only(
        self,
        orchestrator: StoryOrchestrator,
        mock_interpreter: AsyncMock,
        mock_personalizer: AsyncMock,
    ) -> None:
        """전체 플로우: 의도분석 → 미리보기 → 수정 → 텍스트 생성."""
        # Phase A: interpret_and_plan
        plan = await orchestrator.interpret_and_plan(
            parent_text="게임에서 지면 많이 울어요",
            purpose_category="problem_solving",
            child=SAMPLE_CHILD,
        )
        assert plan.title == "하은이의 용기 대모험"

        # Phase B: get_preview
        preview = await orchestrator.get_preview(
            plan=plan, style="watercolor", child_name="하은"
        )
        assert preview.page_count == 3

        # Phase C: revise_plan
        revised = await orchestrator.revise_plan(
            plan=plan, feedback="토끼 대신 서준이가 나왔으면"
        )
        assert revised != plan

        # Phase D: generate_story (revised plan은 2 scenes)
        mock_personalizer.generate_scene.side_effect = PERSONALIZED_SCENES[:2]
        results = []
        async for scene in orchestrator.generate_story(
            confirmed_plan=revised, child=SAMPLE_CHILD, style="watercolor"
        ):
            results.append(scene)

        assert len(results) == 2
        assert all(isinstance(s, PersonalizedScene) for s in results)
