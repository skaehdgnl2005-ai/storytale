"""safety_checker 단위 테스트."""

import pytest

from storytale.interpreter.safety_checker import SafetyChecker

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

CONTENT_FILTER = {
    "description": "테스트용 안전 필터",
    "exact_block": ["바보", "멍청", "벌 줄", "착한 아이"],
    "pattern_block": [
        {"pattern": "죽이고|죽이는|죽이자|죽여", "intent": "살해 표현"},
        {"pattern": "죽어|죽겠어|죽을래", "intent": "죽음 표현"},
        {"pattern": "피가|피를|피투성이|코피", "intent": "유혈 표현"},
        {"pattern": "칼로|칼을|칼이|칼날", "intent": "흉기 표현"},
    ],
    "allowlist": [
        "반죽이",
        "반죽을",
        "반죽",
        "미역죽",
        "팥죽",
        "호박죽",
        "피아노",
        "피자",
        "피부",
        "피곤",
        "칼국수",
        "뮤지칼",
    ],
}


@pytest.fixture
def checker() -> SafetyChecker:
    return SafetyChecker(content_filter=CONTENT_FILTER)


# ---------------------------------------------------------------------------
# Tier 1: exact_block
# ---------------------------------------------------------------------------


def test_exact_block_detects_forbidden_word(checker: SafetyChecker) -> None:
    """exact_block 키워드가 포함되면 즉시 위반으로 감지한다."""
    result = checker.check_text("하은이가 바보라고 말했어요.")
    assert result.blocked is True
    assert result.tier == 1
    assert result.matched_keyword == "바보"


def test_exact_block_detects_multi_word(checker: SafetyChecker) -> None:
    """다어절 exact_block(착한 아이)도 감지한다."""
    result = checker.check_text("넌 착한 아이가 되어야 해.")
    assert result.blocked is True
    assert result.matched_keyword == "착한 아이"


# ---------------------------------------------------------------------------
# Tier 1: allowlist (오탐 방지)
# ---------------------------------------------------------------------------


def test_allowlist_permits_banjuk(checker: SafetyChecker) -> None:
    """'반죽이'는 allowlist에 있으므로 통과한다."""
    result = checker.check_text("케이크 반죽이 뭉쳐졌어요.")
    assert result.blocked is False


def test_allowlist_permits_piano(checker: SafetyChecker) -> None:
    """'피아노'는 allowlist에 있으므로 통과한다."""
    result = checker.check_text("하은이가 피아노를 쳤어요.")
    assert result.blocked is False


def test_allowlist_permits_kalguksu(checker: SafetyChecker) -> None:
    """'칼국수'는 allowlist에 있으므로 통과한다."""
    result = checker.check_text("엄마가 칼국수를 만들었어요.")
    assert result.blocked is False


def test_allowlist_permits_miyeokjuk(checker: SafetyChecker) -> None:
    """'미역죽'은 allowlist에 있으므로 통과한다."""
    result = checker.check_text("미역죽을 끓여요.")
    assert result.blocked is False


# ---------------------------------------------------------------------------
# Tier 1: pattern_block
# ---------------------------------------------------------------------------


def test_pattern_block_detects_kill_expression(checker: SafetyChecker) -> None:
    """살해 활용형 '죽이고'를 감지한다."""
    result = checker.check_text("나쁜 용을 죽이고 싶어.")
    assert result.blocked is True
    assert result.tier == 1
    assert "살해" in result.matched_intent


def test_pattern_block_detects_blood(checker: SafetyChecker) -> None:
    """유혈 표현 '피가'를 감지한다."""
    result = checker.check_text("무릎에서 피가 났어요.")
    assert result.blocked is True
    assert "유혈" in result.matched_intent


def test_pattern_block_detects_knife(checker: SafetyChecker) -> None:
    """흉기 표현 '칼로'를 감지한다."""
    result = checker.check_text("칼로 위협했어요.")
    assert result.blocked is True
    assert "흉기" in result.matched_intent


# ---------------------------------------------------------------------------
# 안전한 텍스트 — 전부 통과
# ---------------------------------------------------------------------------


def test_safe_text_passes(checker: SafetyChecker) -> None:
    """안전한 텍스트는 blocked=False를 반환한다."""
    result = checker.check_text("하은이가 토끼 인형을 안고 잠들었어요.")
    assert result.blocked is False


def test_empty_text_passes(checker: SafetyChecker) -> None:
    """빈 텍스트도 통과한다."""
    result = checker.check_text("")
    assert result.blocked is False


# ---------------------------------------------------------------------------
# validate_plan: ScenePlan 전체 검증
# ---------------------------------------------------------------------------


def test_validate_plan_raises_on_blocked_scene(checker: SafetyChecker) -> None:
    """금지 키워드가 포함된 장면이 있으면 ScenePlanSafetyError를 발생시킨다."""
    from storytale.interpreter.scene_planner import (
        PlannedScene,
        ScenePlan,
        ScenePlanSafetyError,
        StyleNotes,
    )

    plan = ScenePlan(
        title="테스트 책",
        scenes=[
            PlannedScene(
                scene_id="opening",
                emotion="공감",
                purpose="도입",
                description="하은이가 바보라고 놀림 받았어요.",
                child_elements=[],
            ),
        ],
        style_notes=StyleNotes(tone="따뜻하게", avoid=["교훈"], repetition_motif=None),
    )

    with pytest.raises(ScenePlanSafetyError, match="바보"):
        checker.validate_plan(plan)


def test_validate_plan_passes_safe_scenes(checker: SafetyChecker) -> None:
    """모든 장면이 안전하면 예외 없이 통과한다."""
    from storytale.interpreter.scene_planner import (
        PlannedScene,
        ScenePlan,
        StyleNotes,
    )

    plan = ScenePlan(
        title="테스트 책",
        scenes=[
            PlannedScene(
                scene_id="opening",
                emotion="공감",
                purpose="도입",
                description="하은이가 케이크 반죽이 뭉쳐진 걸 봤어요.",
                child_elements=[],
            ),
        ],
        style_notes=StyleNotes(tone="따뜻하게", avoid=["교훈"], repetition_motif=None),
    )

    checker.validate_plan(plan)  # 예외 미발생
