# 안전 필터 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 단순 부분문자열 매칭을 2-Tier(패턴+LLM) 안전 필터로 교체하여 금지어 오탐을 해결하고, Gemini 빈 응답 재시도를 추가한다.

**Architecture:** `safety-rails.json`의 `content_filter_keywords`를 `content_filter`(exact_block / pattern_block / allowlist)로 재구조화. 새 모듈 `safety_checker.py`에 Tier 1(패턴) + Tier 2(LLM 문맥 판단) 로직을 집중시키고, `scene_planner.py`와 `plan_reviser.py`의 중복 검증 코드를 이 모듈에 위임. `gemini_provider.py`의 빈 응답을 재시도 가능 에러로 분류.

**Tech Stack:** Python 3.12, re (정규식), Pydantic v2, pytest, AsyncMock

**Spec:** `docs/superpowers/specs/2026-04-09-safety-filter-redesign.md`

---

## File Structure

| 파일 | 역할 | 변경 |
|------|------|------|
| `docs/guardrail-seeds/safety-rails.json` | 안전 규칙 시드 데이터 | 수정: `content_filter_keywords` → `content_filter` |
| `packages/backend/src/storytale/interpreter/safety_checker.py` | 2-Tier 안전 필터 전담 | **신규** |
| `packages/backend/tests/test_safety_checker.py` | safety_checker 단위 테스트 | **신규** |
| `packages/backend/src/storytale/interpreter/scene_planner.py` | 장면 설계 + 검증 | 수정: 키워드 검증 → SafetyChecker 위임 |
| `packages/backend/src/storytale/interpreter/plan_reviser.py` | 설계 수정 + 검증 | 수정: 키워드 검증 → SafetyChecker 위임 |
| `packages/backend/tests/test_s13_scene_planner.py` | 장면 설계 테스트 | 수정: SAFETY_RAILS fixture 스키마 업데이트 |
| `packages/backend/tests/test_s14_plan_reviser.py` | 설계 수정 테스트 | 수정: SAFETY_RAILS fixture 스키마 업데이트 |
| `packages/backend/src/storytale/interpreter/gemini_provider.py` | Gemini fallback | 수정: 빈 응답 재시도 |
| `packages/backend/tests/test_gemini_empty_retry.py` | Gemini 빈 응답 재시도 테스트 | **신규** |
| `packages/backend/src/storytale/api/guardrails/safety_rails.py` | API Pydantic 스키마 | 수정: 새 스키마 대응 |
| `packages/backend/tests/test_s9_safety_rails.py` | API 테스트 | 수정: 페이로드 스키마 업데이트 |

---

### Task 1: safety-rails.json 스키마 변경

**Files:**
- Modify: `docs/guardrail-seeds/safety-rails.json`

- [ ] **Step 1: `content_filter_keywords`를 `content_filter`로 재구조화**

`safety-rails.json`의 `content_filter_keywords` 섹션을 다음으로 교체:

```json
"content_filter": {
    "description": "생성된 텍스트의 안전 검증 규칙. Tier 1(패턴) → Tier 2(LLM 문맥 판단) 순서로 적용.",
    "exact_block": [
      "바보", "멍청", "못생긴", "뚱뚱",
      "벌 줄", "혼내", "혼날",
      "엄마가 슬퍼", "아빠가 화나",
      "남자답", "여자답",
      "착한 아이", "나쁜 아이"
    ],
    "pattern_block": [
      {"pattern": "죽이고|죽이는|죽이자|죽이다|죽여", "intent": "살해 표현"},
      {"pattern": "죽어|죽겠어|죽을래|죽고\\s*싶", "intent": "죽음 표현"},
      {"pattern": "피가|피를|피투성이|피범벅|코피|피났|피 나", "intent": "유혈 표현"},
      {"pattern": "칼로|칼을|칼이|칼날|칼에", "intent": "흉기 표현"}
    ],
    "allowlist": [
      "반죽이", "반죽을", "반죽", "미역죽", "팥죽", "호박죽",
      "피아노", "피자", "피부", "피리", "피곤", "피우",
      "칼국수", "뮤지칼"
    ]
  }
```

기존 `content_filter_keywords` 키를 완전히 제거하고 `content_filter` 키로 교체한다.

- [ ] **Step 2: JSON 유효성 검증**

Run: `python -c "import json; json.load(open('docs/guardrail-seeds/safety-rails.json', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add docs/guardrail-seeds/safety-rails.json
git commit -m "refactor: safety-rails.json content_filter 3종 분류 스키마로 변경

exact_block / pattern_block / allowlist 구조로 재설계.
G2 시나리오4 '반죽이' 오탐 해결을 위한 기반.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: safety_checker.py 테스트 작성 (TDD — 테스트 먼저)

**Files:**
- Create: `packages/backend/tests/test_safety_checker.py`

- [ ] **Step 1: Tier 1 테스트 작성**

```python
"""safety_checker 단위 테스트."""

import pytest

from storytale.interpreter.safety_checker import (
    SafetyChecker,
    SafetyMatch,
    SafetyCheckResult,
)


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
        "반죽이", "반죽을", "반죽",
        "미역죽", "팥죽", "호박죽",
        "피아노", "피자", "피부", "피곤",
        "칼국수", "뮤지칼",
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd packages/backend && python -m pytest tests/test_safety_checker.py -v 2>&1 | head -30`
Expected: FAIL — `ModuleNotFoundError: No module named 'storytale.interpreter.safety_checker'`

- [ ] **Step 3: Commit**

```bash
git add packages/backend/tests/test_safety_checker.py
git commit -m "test: safety_checker TDD 테스트 작성 (실패 상태)

Tier 1 exact_block, pattern_block, allowlist 검증.
오탐 방지(반죽이, 피아노, 칼국수) 테스트 포함.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: safety_checker.py 구현

**Files:**
- Create: `packages/backend/src/storytale/interpreter/safety_checker.py`

- [ ] **Step 1: SafetyChecker 구현**

```python
"""2-Tier 안전 필터.

Tier 1: allowlist → exact_block → pattern_block (정규식) 순서로 텍스트 검증.
Tier 2: pattern_block 매칭 시 LLM 문맥 판단 (선택적, 향후 확장).

scene_planner.py, plan_reviser.py의 중복 키워드 검증을 이 모듈로 통합.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from storytale.interpreter.scene_planner import ScenePlan, ScenePlanSafetyError


@dataclass
class SafetyCheckResult:
    """안전 검증 결과."""

    blocked: bool = False
    tier: int | None = None
    matched_keyword: str = ""
    matched_intent: str = ""


class SafetyChecker:
    """2-Tier 안전 필터.

    Args:
        content_filter: safety-rails.json의 content_filter dict.
    """

    def __init__(self, content_filter: dict[str, Any]) -> None:
        self._exact_block: list[str] = content_filter.get("exact_block", [])
        self._pattern_block: list[dict[str, str]] = content_filter.get(
            "pattern_block", []
        )
        self._allowlist: list[str] = content_filter.get("allowlist", [])
        # 정규식 사전 컴파일
        self._compiled_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(p["pattern"]), p["intent"]) for p in self._pattern_block
        ]

    def check_text(self, text: str) -> SafetyCheckResult:
        """텍스트를 Tier 1 기준으로 검증한다.

        Returns:
            SafetyCheckResult. blocked=True면 위반.
        """
        if not text:
            return SafetyCheckResult()

        # Step 1: allowlist에 해당하는 부분을 플레이스홀더로 치환
        cleaned = text
        for allowed in sorted(self._allowlist, key=len, reverse=True):
            cleaned = cleaned.replace(allowed, "\x00" * len(allowed))

        # Step 2: exact_block 검사 (치환된 텍스트에서)
        for keyword in self._exact_block:
            if keyword in cleaned:
                return SafetyCheckResult(
                    blocked=True,
                    tier=1,
                    matched_keyword=keyword,
                    matched_intent=f"exact_block: {keyword}",
                )

        # Step 3: pattern_block 정규식 검사 (치환된 텍스트에서)
        for pattern, intent in self._compiled_patterns:
            if pattern.search(cleaned):
                return SafetyCheckResult(
                    blocked=True,
                    tier=1,
                    matched_keyword=pattern.pattern,
                    matched_intent=intent,
                )

        return SafetyCheckResult()

    def validate_plan(self, plan: ScenePlan) -> None:
        """ScenePlan 전체 장면의 description을 검증한다.

        Raises:
            ScenePlanSafetyError: 위반 장면이 있을 때.
        """
        for scene in plan.scenes:
            result = self.check_text(scene.description)
            if result.blocked:
                raise ScenePlanSafetyError(
                    f"장면 '{scene.scene_id}'의 description에 "
                    f"금지 표현이 포함되어 있습니다: {result.matched_keyword} "
                    f"({result.matched_intent})"
                )
```

- [ ] **Step 2: 테스트 실행 → 통과 확인**

Run: `cd packages/backend && python -m pytest tests/test_safety_checker.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 3: Commit**

```bash
git add packages/backend/src/storytale/interpreter/safety_checker.py
git commit -m "feat: SafetyChecker 2-Tier 안전 필터 구현

allowlist → exact_block → pattern_block 순서 검증.
'반죽이', '피아노', '칼국수' 등 오탐 방지.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: scene_planner.py에 SafetyChecker 통합

**Files:**
- Modify: `packages/backend/src/storytale/interpreter/scene_planner.py:131-141`
- Modify: `packages/backend/tests/test_s13_scene_planner.py:70-84`

- [ ] **Step 1: scene_planner.py의 validate_scene_plan 키워드 검증을 SafetyChecker로 교체**

`scene_planner.py`의 `validate_scene_plan()` 함수에서 금지 키워드 검증 부분(L131-141)을 교체:

```python
# 기존 코드 (삭제):
#     filter_keywords: list[str] = safety_rails.get("content_filter_keywords", {}).get(
#         "keywords", []
#     )
#     for scene in plan.scenes:
#         for keyword in filter_keywords:
#             if keyword in scene.description:
#                 raise ScenePlanSafetyError(...)

# 새 코드:
    content_filter = safety_rails.get("content_filter", {})
    if content_filter:
        from storytale.interpreter.safety_checker import SafetyChecker
        checker = SafetyChecker(content_filter=content_filter)
        checker.validate_plan(plan)
```

파일 상단에 import를 추가하지 않고 함수 내 지연 import를 사용한다 (순환 의존 방지: safety_checker가 scene_planner의 ScenePlan을 import하므로).

- [ ] **Step 2: test_s13_scene_planner.py의 SAFETY_RAILS fixture를 새 스키마로 업데이트**

```python
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
```

test_validate_prohibited_keyword_raises_safety_error 테스트는 "바보"를 사용하므로 exact_block에 있어서 그대로 동작한다.

- [ ] **Step 3: 테스트 실행 → 통과 확인**

Run: `cd packages/backend && python -m pytest tests/test_s13_scene_planner.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: Commit**

```bash
git add packages/backend/src/storytale/interpreter/scene_planner.py packages/backend/tests/test_s13_scene_planner.py
git commit -m "refactor: scene_planner 키워드 검증을 SafetyChecker로 위임

validate_scene_plan()의 중복 부분문자열 매칭 제거.
테스트 fixture를 content_filter 새 스키마로 업데이트.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: plan_reviser.py에 SafetyChecker 통합

**Files:**
- Modify: `packages/backend/src/storytale/interpreter/plan_reviser.py:222-237`
- Modify: `packages/backend/tests/test_s14_plan_reviser.py:24-38`

- [ ] **Step 1: plan_reviser.py의 _validate_safety_only를 SafetyChecker로 교체**

`plan_reviser.py` 하단의 `_validate_safety_only()` 함수를 교체:

```python
def _validate_safety_only(
    plan: ScenePlan,
    safety_rails: dict[str, Any],
) -> None:
    """content_filter만 검증한다."""
    content_filter = safety_rails.get("content_filter", {})
    if content_filter:
        from storytale.interpreter.safety_checker import SafetyChecker
        checker = SafetyChecker(content_filter=content_filter)
        checker.validate_plan(plan)
```

- [ ] **Step 2: test_s14_plan_reviser.py의 SAFETY_RAILS fixture를 새 스키마로 업데이트**

```python
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
```

- [ ] **Step 3: 테스트 실행 → 통과 확인**

Run: `cd packages/backend && python -m pytest tests/test_s14_plan_reviser.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 4: Commit**

```bash
git add packages/backend/src/storytale/interpreter/plan_reviser.py packages/backend/tests/test_s14_plan_reviser.py
git commit -m "refactor: plan_reviser 키워드 검증을 SafetyChecker로 위임

_validate_safety_only()의 중복 부분문자열 매칭 제거.
테스트 fixture를 content_filter 새 스키마로 업데이트.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: API Pydantic 스키마 및 시드 테스트 업데이트

**Files:**
- Modify: `packages/backend/src/storytale/api/guardrails/safety_rails.py:36-39`
- Modify: `packages/backend/tests/test_s9_safety_rails.py:22-39`
- Modify: `packages/backend/tests/test_s10_guardrails_combined.py:66-78`

- [ ] **Step 1: safety_rails.py의 Pydantic 스키마 업데이트**

`ContentFilterKeywordsSchema`를 `ContentFilterSchema`로 변경:

```python
class PatternBlockItem(BaseModel):
    pattern: str
    intent: str


class ContentFilterSchema(BaseModel):
    description: str
    exact_block: list[str]
    pattern_block: list[PatternBlockItem]
    allowlist: list[str]
```

`SafetyRailsCreate`와 `SafetyRailsResponse`에서 필드명과 타입 교체:

```python
class SafetyRailsCreate(BaseModel):
    prohibitions: list[str]
    required_elements: list[str]
    content_filter: ContentFilterSchema
    illustration_safety: IllustrationSafetySchema


class SafetyRailsResponse(BaseModel):
    id: int
    prohibitions: list[str]
    required_elements: list[str]
    content_filter: ContentFilterSchema
    illustration_safety: IllustrationSafetySchema

    model_config = {"from_attributes": True}
```

`_to_response` 헬퍼도 업데이트:

```python
def _to_response(rails: SafetyRails) -> SafetyRailsResponse:
    return SafetyRailsResponse(
        id=rails.id,
        prohibitions=rails.prohibitions,
        required_elements=rails.required_elements,
        content_filter=ContentFilterSchema(**rails.content_filter),
        illustration_safety=IllustrationSafetySchema(**rails.illustration_safety),
    )
```

`create_safety_rails` 엔드포인트도 업데이트:

```python
record = SafetyRails(
    prohibitions=payload.prohibitions,
    required_elements=payload.required_elements,
    content_filter=payload.content_filter.model_dump(),
    illustration_safety=payload.illustration_safety.model_dump(),
)
```

- [ ] **Step 2: DB 모델의 JSON 컬럼명 확인 및 업데이트**

`packages/backend/src/storytale/db/models.py`에서 `SafetyRails` 모델의 `content_filter_keywords` 컬럼명을 `content_filter`로 변경이 필요할 수 있다. 실제 컬럼명을 확인하고 필요시 업데이트한다.

주의: DB 마이그레이션이 필요할 수 있다. SQLite 개발 DB면 간단히 컬럼명 변경, PostgreSQL이면 Alembic 마이그레이션 작성.

- [ ] **Step 3: test_s9_safety_rails.py의 SAFETY_PAYLOAD 업데이트**

```python
SAFETY_PAYLOAD = {
    "prohibitions": [
        "공포, 위협, 벌을 동기부여 수단으로 사용하는 장면",
        "어른이 아이를 직접 혼내거나 야단치는 장면",
    ],
    "required_elements": [
        "아이의 감정을 판단 없이 있는 그대로 수용하는 장면이 최소 1회",
        "아이가 스스로 선택하거나 행동하는 순간이 최소 1회",
    ],
    "content_filter": {
        "description": "생성된 텍스트에서 검출 시 재생성을 트리거하는 키워드",
        "exact_block": ["바보", "혼내"],
        "pattern_block": [
            {"pattern": "죽이고|죽이는|죽여", "intent": "살해 표현"},
        ],
        "allowlist": ["반죽이"],
    },
    "illustration_safety": {
        "description": "일러스트 생성 프롬프트에서 금지되는 요소",
        "negative_prompts": ["scary", "horror", "violent"],
    },
}
```

`test_seed_content_filter_keywords_structure` 테스트를 `test_seed_content_filter_structure`로 이름 변경하고 검증 필드 업데이트:

```python
def test_seed_content_filter_structure():
    """시드 데이터의 content_filter가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    cf = data[0]["content_filter"]
    assert "description" in cf
    assert "exact_block" in cf
    assert "pattern_block" in cf
    assert "allowlist" in cf
    assert isinstance(cf["exact_block"], list)
    assert len(cf["exact_block"]) > 0
```

- [ ] **Step 4: test_s10_guardrails_combined.py의 _SAFETY_PAYLOAD 업데이트**

```python
_SAFETY_PAYLOAD = {
    "prohibitions": ["S10 테스트용 금지 사항"],
    "required_elements": ["S10 테스트용 필수 요소"],
    "content_filter": {
        "description": "S10 테스트용 필터",
        "exact_block": ["테스트키워드"],
        "pattern_block": [],
        "allowlist": [],
    },
    "illustration_safety": {
        "description": "S10 테스트용 일러스트 안전",
        "negative_prompts": ["test_negative"],
    },
}
```

- [ ] **Step 5: seed_safety_rails 함수에서 content_filter 키 사용하도록 업데이트**

`safety_rails.py`의 `seed_safety_rails()` 함수:

```python
record = SafetyRails(
    prohibitions=data["prohibitions"],
    required_elements=data["required_elements"],
    content_filter=data["content_filter"],
    illustration_safety=data["illustration_safety"],
)
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `cd packages/backend && python -m pytest tests/test_s9_safety_rails.py tests/test_s10_guardrails_combined.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 7: Commit**

```bash
git add packages/backend/src/storytale/api/guardrails/safety_rails.py packages/backend/src/storytale/db/models.py packages/backend/tests/test_s9_safety_rails.py packages/backend/tests/test_s10_guardrails_combined.py
git commit -m "refactor: API 스키마를 content_filter 구조로 업데이트

ContentFilterSchema(exact_block/pattern_block/allowlist) 적용.
시드 함수, CRUD API, 테스트 fixture 모두 업데이트.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Gemini 빈 응답 재시도

**Files:**
- Modify: `packages/backend/src/storytale/interpreter/gemini_provider.py:126-132`
- Create: `packages/backend/tests/test_gemini_empty_retry.py`

- [ ] **Step 1: 테스트 작성**

```python
"""Gemini 빈 응답 재시도 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from storytale.interpreter.gemini_provider import GeminiProvider
from storytale.interpreter.llm_client import LLMClientError


@pytest.fixture
def provider() -> GeminiProvider:
    return GeminiProvider(api_key="test-key")


@pytest.mark.asyncio
async def test_empty_response_retries_once(provider: GeminiProvider) -> None:
    """빈 응답(text=None) 시 1회 재시도한다."""
    response_empty = MagicMock()
    response_empty.text = None
    response_empty.usage_metadata = None

    response_ok = MagicMock()
    response_ok.text = '{"result": "ok"}'
    response_ok.usage_metadata = None

    mock_generate = AsyncMock(side_effect=[response_empty, response_ok])
    provider._client.aio.models.generate_content = mock_generate

    result = await provider.complete("system", "user")
    assert result == '{"result": "ok"}'
    assert mock_generate.call_count == 2


@pytest.mark.asyncio
async def test_empty_response_twice_raises_error(provider: GeminiProvider) -> None:
    """빈 응답이 재시도 후에도 반복되면 LLMClientError를 발생시킨다."""
    response_empty = MagicMock()
    response_empty.text = None
    response_empty.usage_metadata = None

    mock_generate = AsyncMock(return_value=response_empty)
    provider._client.aio.models.generate_content = mock_generate

    with pytest.raises(LLMClientError, match="빈 응답"):
        await provider.complete("system", "user")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd packages/backend && python -m pytest tests/test_gemini_empty_retry.py -v 2>&1 | tail -20`
Expected: FAIL — 현재 코드는 빈 응답 시 즉시 `LLMClientError`를 발생시키므로 재시도하지 않음

- [ ] **Step 3: gemini_provider.py 빈 응답 재시도 구현**

`gemini_provider.py`의 `complete()` 메서드에서 `text is None` 부분(L127-132)을 변경:

```python
                text = response.text
                if text is None:
                    if attempt < MAX_RETRIES:
                        logger.warning(
                            "gemini_empty_response attempt=%d/%d — 재시도",
                            attempt + 1,
                            MAX_RETRIES + 1,
                        )
                        last_exc = LLMClientError(
                            code="LLM_EMPTY_RESPONSE",
                            message="Gemini가 빈 응답을 반환했습니다 (안전 필터 차단 가능성).",
                            retryable=True,
                        )
                        continue
                    raise LLMClientError(
                        code="LLM_EMPTY_RESPONSE",
                        message="Gemini가 빈 응답을 반환했습니다 (안전 필터 차단 가능성).",
                        retryable=False,
                    )
                return text
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd packages/backend && python -m pytest tests/test_gemini_empty_retry.py -v`
Expected: 모든 테스트 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/backend/src/storytale/interpreter/gemini_provider.py packages/backend/tests/test_gemini_empty_retry.py
git commit -m "fix: Gemini 빈 응답 시 1회 재시도 후 실패

G2 이슈2/3 대응. response.text=None일 때 즉시 에러 대신
기존 재시도 루프 내에서 continue하여 1회 더 시도.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: 나머지 테스트 영향 확인 및 전체 테스트 통과

**Files:**
- Modify (필요시): `packages/backend/tests/test_s16_interpreter_orchestrator.py`
- Modify (필요시): `packages/backend/tests/quality_gates/test_g1_guardrail_data.py`

- [ ] **Step 1: 전체 단위 테스트 실행**

Run: `cd packages/backend && python -m pytest tests/ -v --ignore=tests/quality_gates -k "not integration" 2>&1 | tail -40`
Expected: 모든 테스트 PASS

- [ ] **Step 2: 실패한 테스트가 있다면 SAFETY_RAILS fixture 스키마를 content_filter 구조로 업데이트**

다른 테스트 파일에서도 `content_filter_keywords` 키를 사용하는 곳이 있으면 `content_filter` 구조로 교체한다. 특히:
- `test_s16_interpreter_orchestrator.py`에 `SAFETY_RAILS` dict가 있다면 업데이트
- `test_g1_guardrail_data.py`에 `content_filter_keywords` 검증이 있다면 업데이트

- [ ] **Step 3: 전체 테스트 재실행 및 통과 확인**

Run: `cd packages/backend && python -m pytest tests/ -v --ignore=tests/quality_gates -k "not integration"`
Expected: 모든 테스트 PASS

- [ ] **Step 4: ruff 린트/포맷 확인**

Run: `cd packages/backend && ruff check src tests && ruff format --check src tests`
Expected: 에러 없음

- [ ] **Step 5: Commit (변경이 있을 경우)**

```bash
git add -u packages/backend/
git commit -m "fix: 나머지 테스트의 SAFETY_RAILS fixture를 새 스키마로 업데이트

content_filter_keywords → content_filter 전환 완료.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: guardrail-editing.md 규칙 업데이트

**Files:**
- Modify: `.claude/rules/guardrail-editing.md`

- [ ] **Step 1: safety-rails.json 특별 규칙 업데이트**

기존:
```
3. **safety-rails.json 특별 규칙**:
   - 금지어는 활용형 기반 (예: "죽" 단독 X → "죽이", "죽어", "죽겠" 등 O).
   - 새 금지어 추가 시 오탐 검토 ("죽" → "미역죽" 오탐 가능).
```

변경:
```
3. **safety-rails.json 특별 규칙**:
   - `content_filter`는 3종 구조: `exact_block`(문맥 무관 차단), `pattern_block`(정규식 패턴), `allowlist`(오탐 예외).
   - 새 금지어 추가 시 분류 기준: 오탐 위험이 없으면 `exact_block`, 활용형 구분이 필요하면 `pattern_block`, 알려진 오탐은 `allowlist`에 추가.
   - `pattern_block` 패턴 추가 시 `allowlist`와 교차 테스트 필수. `pytest tests/test_safety_checker.py -v`로 검증.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/guardrail-editing.md
git commit -m "docs: guardrail-editing 규칙을 content_filter 3종 구조에 맞게 업데이트

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
