"""S15 — 부모 미리보기 생성 모듈 테스트.

단위 테스트 (LLM 모킹) + @pytest.mark.integration (실제 API 1회 호출).
"""

import os
from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.preview_generator import (
    PreviewGenerator,
    StoryPreview,
)
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlan,
    StyleNotes,
)

# ---------------------------------------------------------------------------
# 공통 픽스처 데이터
# ---------------------------------------------------------------------------

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
        PlannedScene(
            scene_id="resolution",
            emotion="뿌듯함",
            purpose="감정 수용",
            description="지고도 웃을 수 있게 된 하은이.",
            child_elements=["comfort_object와 함께 웃음"],
        ),
        PlannedScene(
            scene_id="closing",
            emotion="평온",
            purpose="열린 결말",
            description="내일은 또 어떤 모험이 기다릴까요?",
            child_elements=["comfort_object와 함께 잠듦"],
        ),
    ],
    style_notes=StyleNotes(
        tone="따뜻하고 응원하는",
        avoid=["승패를 강조하는 표현", "무조건 이겨야 한다는 메시지"],
        repetition_motif="넘어져도 괜찮아",
    ),
)

VALID_LLM_RESPONSE = {
    "title": "하은이의 용기 대모험",
    "summary": (
        "게임에서 졌을 때 속상했던 하은이가, "
        "토끼 친구의 모습에서 용기를 발견하고 "
        "서준이와 함께 다시 도전하는 이야기예요. "
        "지고도 웃을 수 있다는 걸 알게 된 "
        "하은이의 성장 이야기예요."
    ),
    "scene_highlights": [
        "😢 게임에서 지고 속상한 하은이",
        "🐰 넘어져도 다시 일어나는 토끼",
        "💪 서준이와 함께 다시 도전!",
        "😊 지고도 웃을 수 있게 된 하은이",
        "🌙 내일은 또 어떤 모험이 기다릴까?",
    ],
    "style": "watercolor",
}


# ---------------------------------------------------------------------------
# 단위 테스트 — LLM 모킹
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_llm() -> LLMClient:
    client = LLMClient.__new__(LLMClient)
    client.complete_json = AsyncMock(return_value=VALID_LLM_RESPONSE)
    return client


@pytest.mark.asyncio
async def test_generate_preview_returns_story_preview(mock_llm: LLMClient) -> None:
    """정상 응답 → StoryPreview 객체 반환."""
    gen = PreviewGenerator(llm_client=mock_llm)
    result = await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    assert isinstance(result, StoryPreview)
    assert result.title == "하은이의 용기 대모험"
    assert len(result.scene_highlights) == 5
    assert result.page_count == 5
    assert result.style == "watercolor"


@pytest.mark.asyncio
async def test_generate_preview_summary_is_nonempty(mock_llm: LLMClient) -> None:
    """summary가 비어있지 않은 문자열이어야 한다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    result = await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    assert isinstance(result.summary, str)
    assert len(result.summary) > 0


@pytest.mark.asyncio
async def test_generate_preview_scene_highlights_have_emoji(
    mock_llm: LLMClient,
) -> None:
    """각 scene_highlight는 이모지로 시작해야 한다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    result = await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    for highlight in result.scene_highlights:
        # 이모지는 ord > 127인 문자로 시작
        assert ord(highlight[0]) > 127, f"이모지로 시작하지 않음: {highlight}"


@pytest.mark.asyncio
async def test_generate_preview_page_count_matches_scenes(
    mock_llm: LLMClient,
) -> None:
    """page_count는 scene_plan의 장면 수와 일치해야 한다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    result = await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    assert result.page_count == len(SAMPLE_SCENE_PLAN.scenes)


@pytest.mark.asyncio
async def test_generate_preview_passes_style_through(mock_llm: LLMClient) -> None:
    """style 파라미터가 그대로 전달된다."""
    gen = PreviewGenerator(llm_client=mock_llm)

    # pastel_crayon 스타일 테스트
    response_with_pastel = {**VALID_LLM_RESPONSE, "style": "pastel_crayon"}
    mock_llm.complete_json = AsyncMock(return_value=response_with_pastel)

    result = await gen.generate(SAMPLE_SCENE_PLAN, style="pastel_crayon")
    assert result.style == "pastel_crayon"


@pytest.mark.asyncio
async def test_generate_preview_calls_llm_with_correct_params(
    mock_llm: LLMClient,
) -> None:
    """LLM 호출 시 temperature=0.3, max_tokens=1024 사용."""
    gen = PreviewGenerator(llm_client=mock_llm)
    await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    mock_llm.complete_json.assert_called_once()
    call_kwargs = mock_llm.complete_json.call_args
    assert call_kwargs.kwargs["temperature"] == 0.3
    assert call_kwargs.kwargs["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_generate_preview_child_name_in_prompt(mock_llm: LLMClient) -> None:
    """child_name이 유저 프롬프트에 포함된다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor", child_name="하은이")

    call_args = mock_llm.complete_json.call_args
    user_prompt = call_args.args[1]  # 두 번째 positional arg
    assert "하은이" in user_prompt


@pytest.mark.asyncio
async def test_generate_preview_default_child_name(mock_llm: LLMClient) -> None:
    """child_name 미지정 시 '우리 아이'가 사용된다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    call_args = mock_llm.complete_json.call_args
    user_prompt = call_args.args[1]
    assert "우리 아이" in user_prompt


@pytest.mark.asyncio
async def test_generate_preview_scene_plan_json_in_prompt(
    mock_llm: LLMClient,
) -> None:
    """scene_plan JSON이 유저 프롬프트에 포함된다."""
    gen = PreviewGenerator(llm_client=mock_llm)
    await gen.generate(SAMPLE_SCENE_PLAN, style="watercolor")

    call_args = mock_llm.complete_json.call_args
    user_prompt = call_args.args[1]
    assert "하은이의 용기 대모험" in user_prompt
    assert "opening" in user_prompt


# ---------------------------------------------------------------------------
# 통합 테스트 — 실제 Claude API 호출
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_integration() -> None:
    """실제 Claude API로 미리보기 생성 (CLAUDE_API_KEY 필요)."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY not set")

    client = LLMClient(api_key=api_key)
    gen = PreviewGenerator(llm_client=client)

    result = await gen.generate(
        SAMPLE_SCENE_PLAN,
        style="watercolor",
        child_name="하은이",
    )

    assert isinstance(result, StoryPreview)
    assert len(result.summary) > 0
    assert len(result.scene_highlights) == len(SAMPLE_SCENE_PLAN.scenes)
    assert result.page_count == len(SAMPLE_SCENE_PLAN.scenes)
    assert result.style == "watercolor"
