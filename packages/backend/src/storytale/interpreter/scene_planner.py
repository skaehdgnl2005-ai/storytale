"""장면 설계 모듈 (1층 AI 인터프리터, Step 2).

IntentAnalysis + EmotionalArcTemplate + AgeStyleGuide + SafetyRails →
ScenePlan (장면 목록 + 스타일 노트).
"""

import json
import logging
from typing import Any

from pydantic import BaseModel

from storytale.interpreter.intent_analyzer import IntentAnalysis
from storytale.interpreter.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 프롬프트 버전 (docs/prompts/scene-planner-v1.md)
_PROMPT_VERSION = "scene-planner-v1"

# 권장 LLM 파라미터 (docs/prompts/scene-planner-v1.md 기준)
_TEMPERATURE = 0.3

_MAX_TOKENS_BY_AGE: dict[str, int] = {
    "3-4": 8192,
    "5-6": 8192,
    "7-8": 8192,
}
_MAX_TOKENS_DEFAULT = 4096
_MAX_SAFETY_RETRIES = 2  # 안전 필터 차단 시 재생성 최대 횟수


# ---------------------------------------------------------------------------
# 도메인 모델 (contracts/story-engine.ts 대응, Python snake_case)
# ---------------------------------------------------------------------------


class StyleNotes(BaseModel):
    """스토리 전체 스타일 가이드. contracts StyleNotes 대응."""

    tone: str
    avoid: list[str]
    repetition_motif: str | None = None


class PlannedScene(BaseModel):
    """개별 장면 설계. contracts PlannedScene 대응."""

    scene_id: str
    emotion: str
    purpose: str
    description: str
    child_elements: list[str]


class ScenePlan(BaseModel):
    """확정된 장면 설계 전체. contracts ScenePlan 대응."""

    title: str
    scenes: list[PlannedScene]
    style_notes: StyleNotes


# ---------------------------------------------------------------------------
# 예외 클래스
# ---------------------------------------------------------------------------


class ScenePlanError(Exception):
    """장면 설계 검증 실패 (스키마 오류, 범위 오류 등)."""


class ScenePlanSafetyError(Exception):
    """안전 규칙 위반 (금지 키워드 포함 등)."""


# ---------------------------------------------------------------------------
# 검증 함수 (독립 호출 가능)
# ---------------------------------------------------------------------------


def validate_scene_plan(
    plan: ScenePlan,
    age_style: dict[str, Any],
    safety_rails: dict[str, Any],
) -> None:
    """ScenePlan이 가드레일을 준수하는지 검증한다.

    Args:
        plan: 검증할 ScenePlan.
        age_style: 연령별 문체 규칙 dict (age-style-guides.json 구조).
        safety_rails: 안전 규칙 dict (safety-rails.json 구조).

    Raises:
        ScenePlanError: scenes 비어있음, 장면 수 범위 오류, comfort_object 부족,
            style_notes.avoid 비어있음.
        ScenePlanSafetyError: content_filter 위반.
    """
    # 1. scenes 비어있음 검증
    if not plan.scenes:
        raise ScenePlanError("scenes 배열이 비어있습니다.")

    # 2. 장면 수 범위 검증
    page_guidelines = age_style.get("page_guidelines", {})
    total_pages = page_guidelines.get("total_pages", {})
    min_pages: int = total_pages.get("min", 1)
    max_pages: int = total_pages.get("max", 9999)

    if len(plan.scenes) < min_pages:
        raise ScenePlanError(
            f"장면 수 {len(plan.scenes)}개가 최소 {min_pages}개 미만입니다."
        )
    if len(plan.scenes) > max_pages:
        raise ScenePlanError(
            f"장면 수 {len(plan.scenes)}개가 최대 {max_pages}개를 초과합니다."
        )

    # 3. comfort_object가 child_elements에 2회 이상 등장
    comfort_count = sum(
        1
        for scene in plan.scenes
        for elem in scene.child_elements
        if "comfort_object" in elem
    )
    if comfort_count < 2:
        raise ScenePlanError(
            f"comfort_object가 child_elements에 {comfort_count}회만 등장합니다. "
            "최소 2회 필요합니다."
        )

    # 4. 금지 키워드 검증 (SafetyChecker 위임)
    content_filter = safety_rails.get("content_filter", {})
    if content_filter:
        from storytale.interpreter.safety_checker import SafetyChecker

        checker = SafetyChecker(content_filter=content_filter)
        checker.validate_plan(plan)

    # 5. style_notes.avoid 비어있음 검증
    if not plan.style_notes.avoid:
        raise ScenePlanError("style_notes.avoid가 비어있습니다.")


# ---------------------------------------------------------------------------
# 시스템 프롬프트 / 유저 프롬프트 템플릿
# docs/prompts/scene-planner-v1.md 에서 관리
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
당신은 아동 그림책 스토리 설계자입니다.
의도 분석 결과와 감정 흐름 템플릿을 받아, 구체적인 장면 계획을 설계합니다.

## 입력
- 의도 분석 결과 (JSON)
- 선택된 감정 흐름 템플릿 (JSON)
- 연령별 문체 규칙 (JSON)
- 안전 규칙 (JSON)

## 당신의 임무
감정 흐름 템플릿의 각 stage를 구체적인 장면으로 변환하세요.
하나의 stage가 1~2개 장면이 될 수 있습니다.
총 장면 수는 연령별 문체 규칙의 total_pages 범위 안이어야 합니다.

## 장면 설계 규칙
1. 각 장면에는 명확한 감정(emotion)과 목적(purpose)이 있어야 합니다.
2. description은 이 장면에서 "무슨 일이 일어나는지"를 2~3문장으로 서술.
3. child_elements에는 개인화 요소가 어떻게 등장하는지 명시:
   - "comfort_object가 용기를 주는 역할"
   - "friend_name과 함께 문제를 해결"
   - "favorite_animal이 비유/상상 속에 등장"
4. 첫 장면(opening)은 반드시 아이의 현재 감정을 공감하는 것으로 시작.
5. 마지막 장면(closing)은 열린 결말 또는 긍정적 기대로.
6. comfort_object는 반드시 최소 2개 장면의 child_elements에 등장해야 합니다.

## 스타일 노트 생성 규칙
- tone: 이 이야기 전체의 어조. "훈계"가 아닌 "경험"으로.
- avoid: 이 주제에서 특히 피해야 할 표현/장면 (최소 2개).
- repetition_motif: 스토리 전체에서 반복되는 문구 패턴 (없으면 null).

## 출력 형식
반드시 아래 JSON만 출력하세요. 다른 텍스트를 포함하지 마세요.
{{
  "title": "동화책 제목 (아이 친화적, 5~15글자)",
  "scenes": [
    {{
      "scene_id": "opening",
      "emotion": "...",
      "purpose": "...",
      "description": "...",
      "child_elements": ["...", "..."]
    }}
  ],
  "style_notes": {{
    "tone": "...",
    "avoid": ["...", "..."],
    "repetition_motif": null
  }}
}}\
"""

_USER_PROMPT_TEMPLATE = """\
[필수] scenes 배열 장면 수: {min_scenes}~{max_scenes}개 (반드시 준수)

## 의도 분석 결과
{intent_json}

## 감정 흐름 템플릿
{arc_json}

## 연령별 문체 규칙
{age_style_json}

## 안전 규칙 (절대 위반 금지)
{safety_rails_json}

위 정보를 바탕으로 장면 계획을 설계하세요.\
"""


# ---------------------------------------------------------------------------
# ScenePlanner
# ---------------------------------------------------------------------------


class ScenePlanner:
    """IntentAnalysis + 가드레일 → ScenePlan 변환기.

    Args:
        llm_client: LLMClient 인스턴스.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def generate(
        self,
        intent: IntentAnalysis,
        arc_template: dict[str, Any],
        age_style: dict[str, Any],
        safety_rails: dict[str, Any],
    ) -> ScenePlan:
        """장면 설계를 생성하고 검증하여 반환한다.

        Args:
            intent: S12 IntentAnalyzer가 반환한 IntentAnalysis.
            arc_template: 선택된 감정 흐름 템플릿 dict.
            age_style: 연령별 문체 규칙 dict.
            safety_rails: 안전 규칙 dict.

        Returns:
            검증된 ScenePlan 인스턴스.

        Raises:
            ScenePlanError: 장면 설계 검증 실패.
            ScenePlanSafetyError: 안전 규칙 위반.
            LLMClientError: LLM 호출 자체 실패.
        """
        age_group: str = age_style.get("age_group", "5-6")
        max_tokens = _MAX_TOKENS_BY_AGE.get(age_group, _MAX_TOKENS_DEFAULT)

        total_pages = age_style.get("page_guidelines", {}).get("total_pages", {})
        min_scenes: int = total_pages.get("min", 8)
        max_scenes: int = total_pages.get("max", 16)

        user = _USER_PROMPT_TEMPLATE.format(
            min_scenes=min_scenes,
            max_scenes=max_scenes,
            intent_json=json.dumps(intent.model_dump(), ensure_ascii=False, indent=2),
            arc_json=json.dumps(arc_template, ensure_ascii=False, indent=2),
            age_style_json=json.dumps(age_style, ensure_ascii=False, indent=2),
            safety_rails_json=json.dumps(
                {
                    "prohibitions": safety_rails.get("prohibitions", []),
                    "required_elements": safety_rails.get("required_elements", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )

        logger.info(
            "scene_plan prompt_version=%s arc=%s age_group=%s max_tokens=%d",
            _PROMPT_VERSION,
            arc_template.get("arc_id", "unknown"),
            age_group,
            max_tokens,
        )

        # 안전 필터 차단 시 최대 _MAX_SAFETY_RETRIES 회 재생성
        last_safety_error: ScenePlanSafetyError | None = None
        for attempt in range(_MAX_SAFETY_RETRIES + 1):
            if attempt > 0:
                logger.warning(
                    "scene_plan safety_retry attempt=%d/%d reason=%s",
                    attempt,
                    _MAX_SAFETY_RETRIES,
                    last_safety_error,
                )

            raw: dict[str, Any] = await self._client.complete_json(
                _SYSTEM_PROMPT,
                user,
                temperature=_TEMPERATURE,
                max_tokens=max_tokens,
            )

            plan = self._parse_response(raw)
            try:
                validate_scene_plan(plan, age_style, safety_rails)
                return plan
            except ScenePlanSafetyError as exc:
                last_safety_error = exc
                continue

        raise last_safety_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _parse_response(self, raw: dict[str, Any]) -> ScenePlan:
        """LLM 응답 dict → ScenePlan 변환."""
        scenes_raw = raw.get("scenes", [])
        if not isinstance(scenes_raw, list):
            raise ScenePlanError(f"scenes 필드가 리스트가 아닙니다: {type(scenes_raw)}")

        scenes = [
            PlannedScene(
                scene_id=s.get("scene_id", ""),
                emotion=s.get("emotion", ""),
                purpose=s.get("purpose", ""),
                description=s.get("description", ""),
                child_elements=s.get("child_elements", []),
            )
            for s in scenes_raw
        ]

        style_raw = raw.get("style_notes", {})
        style_notes = StyleNotes(
            tone=style_raw.get("tone", ""),
            avoid=style_raw.get("avoid", []),
            repetition_motif=style_raw.get("repetition_motif"),
        )

        return ScenePlan(
            title=raw.get("title", ""),
            scenes=scenes,
            style_notes=style_notes,
        )
