"""S14 — 설계 수정 모듈 테스트.

단위 테스트 (LLM 모킹) + @pytest.mark.integration (실제 API 1회 호출).
"""

import os
from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.plan_reviser import PlanReviser
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlan,
    ScenePlanSafetyError,
    StyleNotes,
)

# ---------------------------------------------------------------------------
# 공통 픽스처 데이터
# ---------------------------------------------------------------------------

SAFETY_RAILS = {
    "prohibitions": ["공포, 위협, 벌을 동기부여 수단으로 사용하는 장면"],
    "required_elements": [
        "아이의 감정을 판단 없이 있는 그대로 수용하는 장면이 최소 1회",
        "위안 물건(comfort_object) 또는 안전 대상이 최소 2개 장면에 등장",
    ],
    "content_filter": {
        "description": "금지 키워드",
        "exact_block": ["바보", "혼내", "남자답"],
        "pattern_block": [
            {"pattern": "죽이고|죽이는|죽이자|죽여", "intent": "살해 표현"},
        ],
        "allowlist": ["반죽이", "반죽을"],
    },
    "illustration_safety": {
        "description": "일러스트 금지 요소",
        "negative_prompts": ["scary", "horror"],
    },
}

AGE_STYLE = {
    "age_group": "3-4",
    "sentence_rules": {
        "max_characters_per_sentence": 20,
        "preferred_structure": "단문",
    },
    "page_guidelines": {
        "sentences_per_page": {"min": 2, "max": 3},
        "total_pages": {"min": 8, "max": 12},
    },
}

_FEEDBACK = "토끼 친구 대신 서준이가 나왔으면"


def _make_sample_plan(
    *,
    comfort_count: int = 2,
    scene_count: int = 10,
) -> ScenePlan:
    """테스트용 ScenePlan 생성 헬퍼."""
    scenes = []
    for i in range(scene_count):
        child_elements: list[str] = []
        if i < comfort_count:
            child_elements.append(f"comfort_object가 장면 {i}에 등장")
        is_rabbit_scene = i == 2
        scenes.append(
            PlannedScene(
                scene_id="opening"
                if i == 0
                else ("closing" if i == scene_count - 1 else f"scene_{i}"),
                emotion="공감" if i == 0 else "기대",
                purpose=f"장면 {i}의 목적",
                description=(
                    f"하은이가 토끼 친구와 장면 {i}에서 놀고 있습니다."
                    if is_rabbit_scene
                    else f"하은이가 장면 {i}에서 겪는 일입니다."
                ),
                child_elements=child_elements,
            )
        )
    return ScenePlan(
        title="하은이의 특별한 하루",
        scenes=scenes,
        style_notes=StyleNotes(
            tone="훈계하지 않고 경험으로 보여주기",
            avoid=["직접적 교훈 문장", "어른이 가르치는 장면"],
            repetition_motif=None,
        ),
    )


def _make_revised_response(
    original: ScenePlan,
    changed_scene_idx: int = 2,
    new_description: str = "하은이가 서준이와 장면 2에서 놀고 있습니다.",
) -> dict:
    """하나의 장면만 바꾼 LLM 응답 dict 생성."""
    scenes_raw = []
    for i, scene in enumerate(original.scenes):
        desc = new_description if i == changed_scene_idx else scene.description
        scenes_raw.append(
            {
                "scene_id": scene.scene_id,
                "emotion": scene.emotion,
                "purpose": scene.purpose,
                "description": desc,
                "child_elements": scene.child_elements,
            }
        )
    return {
        "title": original.title,
        "scenes": scenes_raw,
        "style_notes": {
            "tone": original.style_notes.tone,
            "avoid": original.style_notes.avoid,
            "repetition_motif": original.style_notes.repetition_motif,
        },
    }


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_client() -> LLMClient:
    return LLMClient(api_key="test-key")


@pytest.fixture
def reviser(llm_client: LLMClient) -> PlanReviser:
    return PlanReviser(llm_client=llm_client)


def _mock_llm(reviser: PlanReviser, response: dict) -> AsyncMock:
    mock = AsyncMock(return_value=response)
    reviser._client.complete_json = mock  # type: ignore[attr-defined]
    return mock


# ---------------------------------------------------------------------------
# 1. 정상 경로: ScenePlan 반환
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_returns_scene_plan(reviser: PlanReviser) -> None:
    """revise()가 ScenePlan 인스턴스를 반환한다."""
    original = _make_sample_plan()
    _mock_llm(reviser, _make_revised_response(original))

    result = await reviser.revise(original, _FEEDBACK, SAFETY_RAILS)

    assert isinstance(result, ScenePlan)
    assert result.title
    assert len(result.scenes) > 0


# ---------------------------------------------------------------------------
# 2. 수정 요청된 장면이 변경됨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_changes_target_scene(reviser: PlanReviser) -> None:
    """수정 요청된 장면의 description이 변경된다."""
    original = _make_sample_plan()
    new_desc = "하은이가 서준이와 장면 2에서 놀고 있습니다."
    _mock_llm(
        reviser,
        _make_revised_response(original, changed_scene_idx=2, new_description=new_desc),
    )

    result = await reviser.revise(original, _FEEDBACK, SAFETY_RAILS)

    assert result.scenes[2].description == new_desc
    assert "서준이" in result.scenes[2].description


# ---------------------------------------------------------------------------
# 3. 수정 요청과 무관한 장면은 그대로 유지
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_preserves_unchanged_scenes(reviser: PlanReviser) -> None:
    """수정과 무관한 장면의 description은 원본과 동일하게 유지된다."""
    original = _make_sample_plan()
    _mock_llm(reviser, _make_revised_response(original, changed_scene_idx=2))

    result = await reviser.revise(original, _FEEDBACK, SAFETY_RAILS)

    # scene_2 제외 나머지 장면 description 동일
    for i, (orig_scene, rev_scene) in enumerate(
        zip(original.scenes, result.scenes, strict=True)
    ):
        if i != 2:
            assert rev_scene.description == orig_scene.description, (
                f"장면 {i}이 변경되지 않아야 하는데 변경됨"
            )


# ---------------------------------------------------------------------------
# 4. 수정 후 안전 규칙 위반 시 ScenePlanSafetyError 발생
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_raises_safety_error_on_forbidden_keyword(
    reviser: PlanReviser,
) -> None:
    """수정된 plan에 금지 키워드가 포함되면 ScenePlanSafetyError가 발생한다."""
    original = _make_sample_plan()
    bad_response = _make_revised_response(
        original,
        changed_scene_idx=2,
        new_description="하은이가 바보라고 말했어요.",  # 금지 키워드
    )
    _mock_llm(reviser, bad_response)

    with pytest.raises(ScenePlanSafetyError, match="바보"):
        await reviser.revise(original, _FEEDBACK, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 5. LLM 호출 시 현재 plan과 부모 피드백이 포함됨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_prompt_contains_plan_and_feedback(reviser: PlanReviser) -> None:
    """LLM 호출 시 user prompt에 현재 plan과 부모 피드백이 포함되어야 한다."""
    original = _make_sample_plan()
    mock = _mock_llm(reviser, _make_revised_response(original))
    feedback = "토끼 친구 대신 서준이가 나왔으면"

    await reviser.revise(original, feedback, SAFETY_RAILS)

    assert mock.called
    _system, user = mock.call_args[0]
    assert feedback in user
    assert original.title in user


# ---------------------------------------------------------------------------
# 6. system prompt에 금지 규칙이 포함됨
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_system_prompt_contains_prohibitions(
    reviser: PlanReviser,
) -> None:
    """system prompt에 safety_rails의 prohibitions가 포함되어야 한다."""
    original = _make_sample_plan()
    mock = _mock_llm(reviser, _make_revised_response(original))

    await reviser.revise(original, "분위기를 바꿔주세요", SAFETY_RAILS)

    system, _user = mock.call_args[0]
    assert "공포" in system  # prohibitions 중 첫 번째 항목의 일부


# ---------------------------------------------------------------------------
# 7. age_style 제공 시 전체 validate_scene_plan 실행
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_with_age_style_validates_scene_count(
    reviser: PlanReviser,
) -> None:
    """age_style을 제공하면 장면 수 범위 검증도 실행된다."""
    from storytale.interpreter.scene_planner import ScenePlanError

    original = _make_sample_plan(scene_count=10)

    # 응답에서 scenes를 3개만 반환 → min=8 미달
    bad_response = _make_revised_response(original)
    bad_response["scenes"] = bad_response["scenes"][:3]  # 3개만 남김
    _mock_llm(reviser, bad_response)

    with pytest.raises(ScenePlanError, match="최소"):
        await reviser.revise(
            original, "더 짧게 해주세요", SAFETY_RAILS, age_style=AGE_STYLE
        )


# ---------------------------------------------------------------------------
# 8. 장면 수 유지 (수정은 내용만, 개수는 원본 유지가 기본)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_preserves_scene_count(reviser: PlanReviser) -> None:
    """수정 후 장면 수가 원본과 동일하다."""
    original = _make_sample_plan(scene_count=10)
    _mock_llm(reviser, _make_revised_response(original))

    result = await reviser.revise(original, _FEEDBACK, SAFETY_RAILS)

    assert len(result.scenes) == len(original.scenes)


# ---------------------------------------------------------------------------
# 9. @pytest.mark.integration — 실제 API 호출
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_real_llm_call() -> None:
    """실제 Claude API 호출 1회. CLAUDE_API_KEY 필요."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 환경변수 미설정")

    client = LLMClient(api_key=api_key)
    reviser = PlanReviser(llm_client=client)
    original = _make_sample_plan(scene_count=10)

    result = await reviser.revise(
        original,
        "토끼 친구 대신 서준이라는 이름의 친구가 나왔으면 좋겠어요",
        SAFETY_RAILS,
    )

    assert isinstance(result, ScenePlan)
    assert len(result.scenes) > 0
    # 수정 요청 반영 확인 (일부 장면에 서준이 등장)
    all_descriptions = " ".join(s.description for s in result.scenes)
    assert "서준" in all_descriptions
