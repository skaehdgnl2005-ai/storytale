"""S13 — 장면 설계 모듈 테스트.

단위 테스트 (LLM 모킹) + @pytest.mark.integration (실제 API 1회 호출).
"""

import os
from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.intent_analyzer import IntentAnalysis
from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlanError,
    ScenePlanner,
    ScenePlanSafetyError,
    StyleNotes,
    validate_scene_plan,
)

# ---------------------------------------------------------------------------
# 공통 픽스처 데이터
# ---------------------------------------------------------------------------

SAMPLE_INTENT = IntentAnalysis(
    intent_category="problem_solving",
    core_theme="동생과의 관계",
    trigger_situation="동생이 태어난 후 관심이 분산된 상황",
    child_current_behavior="동생을 자꾸 밀침",
    parent_desired_outcome="동생을 소중한 존재로 받아들이길",
    emotional_keywords=["질투", "불안", "외로움"],
    recommended_arc_id="gentle_resolution",
)

ARC_TEMPLATE = {
    "arc_id": "gentle_resolution",
    "description": "부드러운 문제 해결형",
    "target_ages": ["3-4", "5-6"],
    "stages": [
        {"phase": "공감", "ratio": 0.2, "purpose": "현재 감정 반영"},
        {"phase": "전환점", "ratio": 0.15, "purpose": "시선 전환"},
        {"phase": "시도", "ratio": 0.25, "purpose": "행동 변화"},
        {"phase": "재시도", "ratio": 0.2, "purpose": "성장"},
        {"phase": "수용", "ratio": 0.2, "purpose": "감정 수용"},
    ],
    "rules": ["문제가 한 번에 해결되면 안 됨"],
}

AGE_STYLE = {
    "age_group": "3-4",
    "sentence_rules": {
        "max_characters_per_sentence": 20,
        "preferred_structure": "단문",
        "repetition_pattern": "AAB",
        "vocabulary_level": "일상 단어 500개",
    },
    "emotional_expression": {
        "method": "행동과 감각으로 표현",
        "good_examples": ["배가 꼬르륵 소리가 났어요."],
        "bad_examples": ["슬픈 마음이 들었어요."],
    },
    "page_guidelines": {
        "sentences_per_page": {"min": 2, "max": 3},
        "max_characters_per_page": 50,
        "total_pages": {"min": 8, "max": 12},
    },
}

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


def _make_valid_scene_plan_response(
    scene_count: int = 10,
    *,
    comfort_count: int = 2,
) -> dict:
    """유효한 ScenePlan LLM 응답 dict를 생성."""
    scenes = []
    for i in range(scene_count):
        child_elements: list[str] = []
        if i < comfort_count:
            child_elements.append(f"comfort_object가 장면 {i}에 등장")
        scenes.append(
            {
                "scene_id": "opening"
                if i == 0
                else ("closing" if i == scene_count - 1 else f"scene_{i}"),
                "emotion": "공감" if i == 0 else "기대",
                "purpose": f"장면 {i}의 목적",
                "description": f"하은이가 장면 {i}에서 겪는 일입니다.",
                "child_elements": child_elements,
            }
        )
    return {
        "title": "하은이의 특별한 하루",
        "scenes": scenes,
        "style_notes": {
            "tone": "훈계하지 않고 경험으로 보여주기",
            "avoid": ["직접적 교훈 문장", "어른이 가르치는 장면"],
            "repetition_motif": None,
        },
    }


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_client() -> LLMClient:
    return LLMClient(api_key="test-key")


@pytest.fixture
def planner(llm_client: LLMClient) -> ScenePlanner:
    return ScenePlanner(llm_client=llm_client)


def _mock_llm(planner: ScenePlanner, response: dict) -> AsyncMock:
    """LLMClient.complete_json 을 response dict 로 패치."""
    mock = AsyncMock(return_value=response)
    planner._client.complete_json = mock  # type: ignore[attr-defined]
    return mock


# ---------------------------------------------------------------------------
# 1. 정상 경로: ScenePlan 반환 + 스키마 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_valid_scene_plan(planner: ScenePlanner) -> None:
    """generate()가 ScenePlan 모델을 반환하고 필수 필드가 채워진다."""
    _mock_llm(planner, _make_valid_scene_plan_response(10))

    plan = await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    assert plan.title
    assert len(plan.scenes) == 10
    assert isinstance(plan.scenes[0], PlannedScene)
    assert isinstance(plan.style_notes, StyleNotes)
    assert plan.style_notes.tone


# ---------------------------------------------------------------------------
# 2. 첫 장면 scene_id == "opening"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_scene_is_opening(planner: ScenePlanner) -> None:
    """첫 번째 장면의 scene_id가 'opening'이어야 한다."""
    _mock_llm(planner, _make_valid_scene_plan_response(10))

    plan = await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    assert plan.scenes[0].scene_id == "opening"


# ---------------------------------------------------------------------------
# 3. 장면 수가 page_guidelines 범위 내
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scene_count_within_range(planner: ScenePlanner) -> None:
    """generate()가 age_style의 total_pages 범위를 준수한다 (8~12)."""
    _mock_llm(planner, _make_valid_scene_plan_response(10))

    plan = await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    min_p = AGE_STYLE["page_guidelines"]["total_pages"]["min"]
    max_p = AGE_STYLE["page_guidelines"]["total_pages"]["max"]
    assert min_p <= len(plan.scenes) <= max_p


# ---------------------------------------------------------------------------
# 4. comfort_object가 child_elements에 2회 이상 등장
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_comfort_object_appears_twice(planner: ScenePlanner) -> None:
    """child_elements 전체에서 'comfort_object' 언급이 2회 이상이어야 한다."""
    _mock_llm(planner, _make_valid_scene_plan_response(10, comfort_count=2))

    plan = await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    count = sum(
        1
        for scene in plan.scenes
        for elem in scene.child_elements
        if "comfort_object" in elem
    )
    assert count >= 2


# ---------------------------------------------------------------------------
# 5. style_notes.avoid 가 비어있지 않음
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_style_notes_avoid_not_empty(planner: ScenePlanner) -> None:
    """style_notes.avoid 리스트에 최소 1개 항목이 있어야 한다."""
    _mock_llm(planner, _make_valid_scene_plan_response(10))

    plan = await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    assert len(plan.style_notes.avoid) >= 1


# ---------------------------------------------------------------------------
# 6. validate_scene_plan: scenes 비어있으면 ScenePlanError
# ---------------------------------------------------------------------------


def test_validate_empty_scenes_raises_error() -> None:
    """scenes가 비어있으면 ScenePlanError 발생."""
    empty_plan_data = {
        "title": "빈 책",
        "scenes": [],
        "style_notes": {
            "tone": "따뜻하게",
            "avoid": ["교훈"],
            "repetition_motif": None,
        },
    }
    plan = _build_scene_plan(empty_plan_data)

    with pytest.raises(ScenePlanError, match="비어"):
        validate_scene_plan(plan, AGE_STYLE, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 7. validate_scene_plan: 장면 수 최소 미달
# ---------------------------------------------------------------------------


def test_validate_scene_count_too_few_raises_error() -> None:
    """장면 수가 total_pages.min 미만이면 ScenePlanError 발생."""
    response = _make_valid_scene_plan_response(3)  # min=8 미달
    plan = _build_scene_plan(response)

    with pytest.raises(ScenePlanError, match="최소"):
        validate_scene_plan(plan, AGE_STYLE, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 8. validate_scene_plan: 장면 수 최대 초과
# ---------------------------------------------------------------------------


def test_validate_scene_count_too_many_raises_error() -> None:
    """장면 수가 total_pages.max 초과이면 ScenePlanError 발생."""
    response = _make_valid_scene_plan_response(20)  # max=12 초과
    plan = _build_scene_plan(response)

    with pytest.raises(ScenePlanError, match="최대"):
        validate_scene_plan(plan, AGE_STYLE, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 9. validate_scene_plan: comfort_object 2회 미만
# ---------------------------------------------------------------------------


def test_validate_comfort_object_insufficient_raises_error() -> None:
    """comfort_object가 child_elements에 1회 이하면 ScenePlanError 발생."""
    response = _make_valid_scene_plan_response(10, comfort_count=1)
    plan = _build_scene_plan(response)

    with pytest.raises(ScenePlanError, match="comfort_object"):
        validate_scene_plan(plan, AGE_STYLE, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 10. validate_scene_plan: 금지 키워드 포함 시 ScenePlanSafetyError
# ---------------------------------------------------------------------------


def test_validate_prohibited_keyword_raises_safety_error() -> None:
    """description에 content_filter 금지 키워드가 포함되면 ScenePlanSafetyError 발생."""
    response = _make_valid_scene_plan_response(10)
    # 금지 키워드("바보")를 첫 장면 description에 삽입
    response["scenes"][0]["description"] = "하은이가 바보라고 말했어요."
    plan = _build_scene_plan(response)

    with pytest.raises(ScenePlanSafetyError, match="바보"):
        validate_scene_plan(plan, AGE_STYLE, SAFETY_RAILS)


# ---------------------------------------------------------------------------
# 11. LLM 호출 시 user 프롬프트에 intent 데이터 포함 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_intent_data(planner: ScenePlanner) -> None:
    """LLM 호출 시 user prompt에 core_theme과 장면 수 범위가 포함되어야 한다."""
    mock = _mock_llm(planner, _make_valid_scene_plan_response(10))

    await planner.generate(SAMPLE_INTENT, ARC_TEMPLATE, AGE_STYLE, SAFETY_RAILS)

    assert mock.called
    _system, user = mock.call_args[0]
    assert SAMPLE_INTENT.core_theme in user
    # page_guidelines.total_pages.min/max 값이 명시적으로 포함되어야 함
    assert "8" in user
    assert "12" in user


# ---------------------------------------------------------------------------
# 12. @pytest.mark.integration — 실제 API 호출
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_real_llm_call() -> None:
    """실제 Claude API 호출 1회. CLAUDE_API_KEY 필요."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 환경변수 미설정")

    from storytale.interpreter.intent_analyzer import IntentAnalyzer

    client = LLMClient(api_key=api_key)
    arc_templates = IntentAnalyzer.load_arc_templates_from_json()
    arc = next(t for t in arc_templates if t["arc_id"] == "gentle_resolution")

    planner = ScenePlanner(llm_client=client)
    plan = await planner.generate(SAMPLE_INTENT, arc, AGE_STYLE, SAFETY_RAILS)

    assert plan.title
    min_p = AGE_STYLE["page_guidelines"]["total_pages"]["min"]
    max_p = AGE_STYLE["page_guidelines"]["total_pages"]["max"]
    assert min_p <= len(plan.scenes) <= max_p
    assert plan.style_notes.avoid


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _build_scene_plan(data: dict):  # type: ignore[return]
    """dict → ScenePlan 변환 헬퍼 (validator 테스트용)."""
    from storytale.interpreter.scene_planner import ScenePlan

    scenes = [
        PlannedScene(
            scene_id=s["scene_id"],
            emotion=s["emotion"],
            purpose=s["purpose"],
            description=s["description"],
            child_elements=s.get("child_elements", []),
        )
        for s in data.get("scenes", [])
    ]
    style = StyleNotes(
        tone=data["style_notes"]["tone"],
        avoid=data["style_notes"].get("avoid", []),
        repetition_motif=data["style_notes"].get("repetition_motif"),
    )
    return ScenePlan(title=data["title"], scenes=scenes, style_notes=style)
