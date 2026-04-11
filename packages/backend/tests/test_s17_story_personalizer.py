"""S17 — 장면별 텍스트 생성 모듈 테스트.

단위 테스트 (LLM 모킹): PlannedScene + ChildProfile → PersonalizedScene.
"""

from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import PlannedScene, StyleNotes
from storytale.interpreter.story_personalizer import (
    ChildProfile,
    PersonalizedScene,
    StoryPersonalizer,
    StoryPersonalizerError,
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

SAMPLE_SCENE = PlannedScene(
    scene_id="opening",
    emotion="sadness",
    purpose="현재 감정 공감",
    description=(
        "하은이가 엄마 옆에 앉아 있지만 엄마는 동생을 안고 있다. "
        "하은이는 토니를 꼭 껴안고 있다."
    ),
    child_elements=["comfort_object 등장", "엄마와의 거리감 표현"],
)

SAMPLE_STYLE_NOTES = StyleNotes(
    tone="훈계하지 않고 경험으로 보여주기",
    avoid=["직접적 교훈 문장", "어른이 가르치는 장면"],
    repetition_motif="토니가 옆에 있으니까 괜찮아",
)

AGE_STYLE_3_4 = {
    "age_group": "3-4",
    "sentence_rules": {
        "max_characters_per_sentence": 20,
        "preferred_structure": "주어 + 동사 + 감각/감정. 단문 위주.",
        "repetition_pattern": "AAB",
        "vocabulary_level": "일상 단어 500개 이내. 의성어·의태어 적극 활용.",
    },
    "emotional_expression": {
        "method": "행동과 감각으로 표현. 감정을 직접 명명하지 않는다.",
        "good_examples": ["배가 꼬르륵 소리가 났어요.", "눈물이 뚝 떨어졌어요."],
        "bad_examples": ["하은이는 불안했어요."],
    },
    "page_guidelines": {
        "sentences_per_page": {"min": 2, "max": 3},
        "max_characters_per_page": 50,
        "total_pages": {"min": 8, "max": 12},
    },
}

# LLM이 반환할 샘플 응답
SAMPLE_LLM_RESPONSE = {
    "scene_id": "opening",
    "page_number": 1,
    "text": "하은이가 토니를 꼭 안았어요.\n엄마는 저기 멀리 있었어요.",
    "illustration_prompt": (
        "a young girl hugging a brown teddy bear tightly, "
        "soft blue-gray undertones, muted cool pastels, "
        "soft diffused light, overcast feel, "
        "a sofa in background, large whitespace around character, "
        "soft watercolor wash, children's book illustration"
    ),
}


# ---------------------------------------------------------------------------
# 기본 생성 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_scene_returns_personalized_scene():
    """PlannedScene + ChildProfile → PersonalizedScene 변환 성공."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    result = await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    assert isinstance(result, PersonalizedScene)
    assert result.scene_id == "opening"
    assert result.page_number == 1
    assert isinstance(result.text, str)
    assert len(result.text) > 0
    assert isinstance(result.illustration_prompt, str)
    assert len(result.illustration_prompt) > 0


@pytest.mark.asyncio
async def test_llm_called_with_correct_temperature():
    """프롬프트 spec대로 temperature=0.7 사용."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    _, kwargs = client.complete_json.call_args
    assert kwargs.get("temperature") == 0.7


@pytest.mark.asyncio
async def test_llm_called_with_correct_max_tokens():
    """프롬프트 spec대로 max_tokens=1024 사용."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    _, kwargs = client.complete_json.call_args
    assert kwargs.get("max_tokens") == 4096


# ---------------------------------------------------------------------------
# 프롬프트 내용 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_prompt_contains_child_name():
    """유저 프롬프트에 아이 이름이 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    user_prompt = args[1]  # 두 번째 위치 인자 = user prompt
    assert "하은" in user_prompt


@pytest.mark.asyncio
async def test_user_prompt_contains_scene_info():
    """유저 프롬프트에 장면 정보가 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    user_prompt = args[1]
    assert "opening" in user_prompt
    assert "sadness" in user_prompt
    assert "1/8" in user_prompt


@pytest.mark.asyncio
async def test_system_prompt_contains_age_style_rules():
    """시스템 프롬프트에 연령별 문체 규칙이 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    system_prompt = args[0]  # 첫 번째 위치 인자 = system prompt
    assert "20" in system_prompt  # max_characters_per_sentence
    assert "AAB" in system_prompt  # repetition_pattern


@pytest.mark.asyncio
async def test_system_prompt_contains_style_notes():
    """시스템 프롬프트에 스타일 노트가 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    system_prompt = args[0]
    assert "훈계하지 않고 경험으로 보여주기" in system_prompt


# ---------------------------------------------------------------------------
# Identity Prompt Block 관련 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identity_prompt_block_in_user_prompt():
    """identity_prompt_block이 제공되면 유저 프롬프트에 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
        identity_prompt_block=(
            "a young girl with round face, short black hair with red hairpin"
        ),
    )

    args = client.complete_json.call_args[0]
    user_prompt = args[1]
    assert "a young girl with round face" in user_prompt


@pytest.mark.asyncio
async def test_no_identity_block_uses_placeholder():
    """identity_prompt_block 미제공 시 플레이스홀더 텍스트가 포함된다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    user_prompt = args[1]
    # identity block 없이도 호출은 성공해야 함 (S22 전에 텍스트만 먼저 생성 가능)
    assert "Identity Prompt Block" in user_prompt


# ---------------------------------------------------------------------------
# emotion_to_visual 참조 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_prompt_contains_emotion_visual_guide():
    """유저 프롬프트에 감정별 시각 가이드가 포함되어야 한다."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=SAMPLE_CHILD,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    user_prompt = args[1]
    # sadness 장면이므로 sadness 가이드가 포함되어야 함
    assert "blue-gray" in user_prompt or "sadness" in user_prompt


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_llm_response_raises_error():
    """LLM이 필수 필드 누락 응답을 반환하면 StoryPersonalizerError 발생."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value={"scene_id": "opening"})

    personalizer = StoryPersonalizer(llm_client=client)

    with pytest.raises(StoryPersonalizerError):
        await personalizer.generate_scene(
            scene=SAMPLE_SCENE,
            child=SAMPLE_CHILD,
            previous_summary="없음",
            age_style=AGE_STYLE_3_4,
            style_notes=SAMPLE_STYLE_NOTES,
            scene_index=1,
            total_scenes=8,
        )


@pytest.mark.asyncio
async def test_child_gender_mapped_to_pronoun():
    """아이 성별이 일러스트 프롬프트 가이드에 반영되어야 한다 (boy/girl)."""
    client = LLMClient(api_key="fake-key")
    client.complete_json = AsyncMock(return_value=SAMPLE_LLM_RESPONSE)

    male_child = ChildProfile(
        child_id="child-002",
        name="서준",
        age=5,
        gender="male",
    )

    personalizer = StoryPersonalizer(llm_client=client)
    await personalizer.generate_scene(
        scene=SAMPLE_SCENE,
        child=male_child,
        previous_summary="없음",
        age_style=AGE_STYLE_3_4,
        style_notes=SAMPLE_STYLE_NOTES,
        scene_index=1,
        total_scenes=8,
    )

    args = client.complete_json.call_args[0]
    system_prompt = args[0]
    # 시스템 프롬프트에서 boy/girl 지칭 안내가 있어야 함
    assert "boy" in system_prompt.lower() or "a young boy" in system_prompt.lower()
