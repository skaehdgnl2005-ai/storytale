"""S12 — 의도 분석 모듈 테스트.

단위 테스트 (LLM 모킹) + @pytest.mark.integration (실제 API 1회 호출).
"""

import os
from unittest.mock import AsyncMock

import pytest

from storytale.interpreter.intent_analyzer import (
    IntentAnalysisError,
    IntentAnalyzer,
    RejectedIntentError,
)
from storytale.interpreter.llm_client import LLMClient

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------

ARC_TEMPLATES = [
    {
        "arc_id": "gentle_resolution",
        "description": "부드러운 문제 해결형",
        "target_ages": ["3-4", "5-6"],
        "stages": [],
        "rules": [],
    },
    {
        "arc_id": "courage_building",
        "description": "용기 축적형",
        "target_ages": ["3-4", "5-6", "7-8"],
        "stages": [],
        "rules": [],
    },
    {
        "arc_id": "relationship_repair",
        "description": "관계 회복형",
        "target_ages": ["5-6", "7-8"],
        "stages": [],
        "rules": [],
    },
    {
        "arc_id": "new_experience",
        "description": "새 경험 수용형",
        "target_ages": ["3-4", "5-6"],
        "stages": [],
        "rules": [],
    },
    {
        "arc_id": "joy_of_discovery",
        "description": "발견의 기쁨형",
        "target_ages": ["3-4", "5-6", "7-8"],
        "stages": [],
        "rules": [],
    },
    {
        "arc_id": "celebration_joy",
        "description": "기념일 축하형",
        "target_ages": ["3-4", "5-6", "7-8"],
        "stages": [],
        "rules": [],
    },
]


@pytest.fixture
def llm_client() -> LLMClient:
    return LLMClient(api_key="test-key")


@pytest.fixture
def analyzer(llm_client: LLMClient) -> IntentAnalyzer:
    return IntentAnalyzer(llm_client=llm_client, arc_templates=ARC_TEMPLATES)


def _mock_llm(analyzer: IntentAnalyzer, response: dict) -> AsyncMock:
    """LLMClient.complete_json 을 response dict 로 패치."""
    mock = AsyncMock(return_value=response)
    analyzer._client.complete_json = mock  # type: ignore[attr-defined]
    return mock


# ---------------------------------------------------------------------------
# 1. Case 1 — 가치 교육: 정직
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case1_value_teaching_honesty(analyzer: IntentAnalyzer) -> None:
    """거짓말 금지 → intent_category=value_teaching, core_theme에 '정직' 포함."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "value_teaching",
            "core_theme": "정직의 가치",
            "trigger_situation": "거짓말 상황",
            "child_current_behavior": "거짓말을 하는 상황",
            "parent_desired_outcome": "거짓말하면 안 된다는 것을 무섭지 않게 이해하길",
            "emotional_keywords": ["부끄러움", "불안", "용기"],
            "recommended_arc_id": "courage_building",
        },
    )

    result = await analyzer.analyze(
        parent_text="거짓말하면 안 된다는 걸 무섭지 않게 알려주고 싶어요",
        purpose_category="value_teaching",
        child_age=5,
    )

    assert result.intent_category == "value_teaching"
    assert "정직" in result.core_theme
    assert result.recommended_arc_id == "courage_building"
    assert len(result.emotional_keywords) >= 1


# ---------------------------------------------------------------------------
# 2. Case 2 — 관심사: 공룡
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case2_interest_story_dinosaur(analyzer: IntentAnalyzer) -> None:
    """공룡 관심사 → intent_category=interest_story, core_theme에 '공룡' 포함."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "interest_story",
            "core_theme": "공룡 모험",
            "trigger_situation": "공룡을 좋아하는 아이의 일상",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "아이가 좋아하는 공룡 세계를 탐험하는 책",
            "emotional_keywords": ["호기심", "설렘", "즐거움"],
            "recommended_arc_id": "joy_of_discovery",
        },
    )

    result = await analyzer.analyze(
        parent_text="공룡을 너무 좋아해요, 특히 트리케라톱스요",
        purpose_category="interest_story",
        child_age=4,
    )

    assert result.intent_category == "interest_story"
    assert "공룡" in result.core_theme
    assert result.recommended_arc_id == "joy_of_discovery"


# ---------------------------------------------------------------------------
# 3. Case 3 — 문제 해결: 동생
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case3_problem_solving_sibling(analyzer: IntentAnalyzer) -> None:
    """동생 갈등 → intent_category=problem_solving, emotional_keywords에 '질투' 포함."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "problem_solving",
            "core_theme": "동생과의 관계",
            "trigger_situation": "동생이 태어난 후 관심이 분산된 상황",
            "child_current_behavior": "동생을 자꾸 밀침",
            "parent_desired_outcome": "동생을 소중한 존재로 받아들이길",
            "emotional_keywords": ["질투", "불안", "외로움"],
            "recommended_arc_id": "gentle_resolution",
        },
    )

    result = await analyzer.analyze(
        parent_text="동생이 태어났는데 자꾸 동생을 밀쳐요. 엄마를 빼앗긴다고 생각하는 것 같아요.",  # noqa: E501
        purpose_category="problem_solving",
        child_age=4,
    )

    assert result.intent_category == "problem_solving"
    assert "질투" in result.emotional_keywords
    assert result.recommended_arc_id == "gentle_resolution"


# ---------------------------------------------------------------------------
# 4. Case 4 — 기념일: 생일
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case4_celebration_birthday(analyzer: IntentAnalyzer) -> None:
    """생일 → intent_category=celebration, core_theme에 '생일' 포함."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "celebration",
            "core_theme": "생일 축하",
            "trigger_situation": "다음 주 생일",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "특별한 생일 책으로 아이에게 사랑을 전하길",
            "emotional_keywords": ["기대", "설렘", "감사"],
            "recommended_arc_id": "celebration_joy",
        },
    )

    result = await analyzer.analyze(
        parent_text="다음 주가 생일인데 특별한 책을 만들어주고 싶어요",
        purpose_category="celebration",
        child_age=6,
    )

    assert result.intent_category == "celebration"
    assert "생일" in result.core_theme
    assert result.recommended_arc_id == "celebration_joy"


# ---------------------------------------------------------------------------
# 5. Case 5 — 모호한 입력
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case5_ambiguous_input(analyzer: IntentAnalyzer) -> None:
    """모호한 입력 → child_current_behavior='명시되지 않음'."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "value_teaching",
            "core_theme": "좋은 마음 키우기",
            "trigger_situation": "일상적인 상황",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "선하고 바른 아이로 자라길",
            "emotional_keywords": ["따뜻함", "바람"],
            "recommended_arc_id": "gentle_resolution",
        },
    )

    result = await analyzer.analyze(
        parent_text="좋은 아이가 됐으면 좋겠어요",
        purpose_category="value_teaching",
        child_age=5,
    )

    assert result.child_current_behavior == "명시되지 않음"


# ---------------------------------------------------------------------------
# 6. 부적절한 요청 거부
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejected_intent_raises_error(analyzer: IntentAnalyzer) -> None:
    """LLM이 rejected=true 반환 시 RejectedIntentError 발생."""
    _mock_llm(
        analyzer,
        {"rejected": True, "reason": "폭력적 내용 포함"},
    )

    with pytest.raises(RejectedIntentError) as exc_info:
        await analyzer.analyze(
            parent_text="아이가 폭력을 써서 원하는 걸 얻는 법을 알려주세요",
            purpose_category="value_teaching",
            child_age=5,
        )

    assert "폭력" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. 잘못된 arc_id 반환 시 IntentAnalysisError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_arc_id_raises_error(analyzer: IntentAnalyzer) -> None:
    """LLM이 존재하지 않는 arc_id 반환 시 IntentAnalysisError 발생."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "value_teaching",
            "core_theme": "정직",
            "trigger_situation": "거짓말 상황",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "정직한 아이",
            "emotional_keywords": ["부끄러움"],
            "recommended_arc_id": "nonexistent_arc",  # 존재하지 않음
        },
    )

    with pytest.raises(IntentAnalysisError) as exc_info:
        await analyzer.analyze(
            parent_text="거짓말하면 안 된다는 걸 알려주고 싶어요",
            purpose_category="value_teaching",
            child_age=5,
        )

    assert "arc_id" in str(exc_info.value).lower() or "nonexistent_arc" in str(
        exc_info.value
    )


# ---------------------------------------------------------------------------
# 8. 잘못된 intent_category 반환 시 IntentAnalysisError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_intent_category_raises_error(analyzer: IntentAnalyzer) -> None:
    """LLM이 알 수 없는 intent_category 반환 시 IntentAnalysisError 발생."""
    _mock_llm(
        analyzer,
        {
            "intent_category": "unknown_category",
            "core_theme": "정직",
            "trigger_situation": "상황",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "목표",
            "emotional_keywords": ["감정"],
            "recommended_arc_id": "gentle_resolution",
        },
    )

    with pytest.raises(IntentAnalysisError):
        await analyzer.analyze(
            parent_text="거짓말하면 안 된다는 걸 알려주고 싶어요",
            purpose_category="value_teaching",
            child_age=5,
        )


# ---------------------------------------------------------------------------
# 9. LLM 호출 시 프롬프트에 입력값 포함 여부 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_parent_text(analyzer: IntentAnalyzer) -> None:
    """LLM 호출 시 user prompt에 parent_text가 포함되어야 한다."""
    mock = _mock_llm(
        analyzer,
        {
            "intent_category": "value_teaching",
            "core_theme": "정직의 가치",
            "trigger_situation": "거짓말 상황",
            "child_current_behavior": "명시되지 않음",
            "parent_desired_outcome": "정직한 아이",
            "emotional_keywords": ["부끄러움"],
            "recommended_arc_id": "courage_building",
        },
    )

    parent_text = "거짓말하면 안 된다는 걸 알려주고 싶어요"
    await analyzer.analyze(
        parent_text=parent_text,
        purpose_category="value_teaching",
        child_age=5,
    )

    # complete_json 이 호출되었고, user 인자에 parent_text 가 포함됨
    assert mock.called
    _system, user = mock.call_args[0]
    assert parent_text in user


# ---------------------------------------------------------------------------
# 10. load_from_json 클래스 메서드
# ---------------------------------------------------------------------------


def test_load_arc_templates_from_json() -> None:
    """load_arc_templates_from_json()이 실제 JSON 파일을 읽는다."""
    templates = IntentAnalyzer.load_arc_templates_from_json()
    assert len(templates) >= 6  # emotional-arcs.json에 6개 정의
    arc_ids = {t["arc_id"] for t in templates}
    assert "gentle_resolution" in arc_ids
    assert "celebration_joy" in arc_ids


# ---------------------------------------------------------------------------
# 11. @pytest.mark.integration — 실제 API 호출
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_real_llm_call() -> None:
    """실제 Claude API 호출 1회. CLAUDE_API_KEY 필요."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 환경변수 미설정")

    client = LLMClient(api_key=api_key)
    templates = IntentAnalyzer.load_arc_templates_from_json()
    analyzer = IntentAnalyzer(llm_client=client, arc_templates=templates)

    result = await analyzer.analyze(
        parent_text="동생이 태어났는데 자꾸 동생을 밀쳐요.",
        purpose_category="problem_solving",
        child_age=4,
    )

    assert result.intent_category in {
        "value_teaching",
        "interest_story",
        "problem_solving",
        "celebration",
    }
    assert result.recommended_arc_id in {t["arc_id"] for t in templates}
    assert len(result.emotional_keywords) >= 1
