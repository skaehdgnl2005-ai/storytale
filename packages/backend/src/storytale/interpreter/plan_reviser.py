"""설계 수정 모듈 (2층 부모 확인 루프).

부모 피드백을 반영해 ScenePlan의 특정 장면만 수정한다.
수정 결과는 안전 규칙 준수를 재검증한다.
"""

import json
import logging
from typing import Any

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import (
    PlannedScene,
    ScenePlan,
    ScenePlanSafetyError,
    StyleNotes,
    validate_scene_plan,
)

logger = logging.getLogger(__name__)

# 프롬프트 버전 (docs/prompts/plan-reviser-v1.md)
_PROMPT_VERSION = "plan-reviser-v1"

# 권장 LLM 파라미터
_TEMPERATURE = 0.3
_MAX_TOKENS = 8192
_MAX_SAFETY_RETRIES = 2  # 안전 필터 차단 시 재생성 최대 횟수


# ---------------------------------------------------------------------------
# 예외 클래스
# ---------------------------------------------------------------------------


class PlanReviserError(Exception):
    """설계 수정 실패 (스키마 오류 등)."""


# ---------------------------------------------------------------------------
# 프롬프트 템플릿
# docs/prompts/plan-reviser-v1.md 에서 관리
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
당신은 아동 그림책 스토리 수정 전문가입니다.
현재 장면 설계와 부모의 수정 요청을 받아, 필요한 장면만 최소한으로 수정합니다.

## 수정 원칙
1. 부모 피드백과 직접 관련된 장면만 수정하세요.
2. 관련 없는 장면은 JSON 내용을 그대로 유지하세요.
3. 수정 후에도 전체 장면 흐름의 일관성을 유지하세요.
4. 안전 규칙을 반드시 준수하세요.

## 안전 규칙 (절대 위반 금지)
{safety_prohibitions}

## 출력 형식
반드시 아래 JSON만 출력하세요. 다른 텍스트를 포함하지 마세요.
{{
  "title": "...",
  "scenes": [
    {{
      "scene_id": "...",
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
## 현재 장면 설계
{current_plan_json}

## 부모 수정 요청
{parent_feedback}

위 수정 요청을 반영하여 장면 설계를 수정하세요.
수정이 불필요한 장면은 그대로 유지하세요.\
"""


# ---------------------------------------------------------------------------
# PlanReviser
# ---------------------------------------------------------------------------


class PlanReviser:
    """부모 피드백 → ScenePlan 수정기.

    Args:
        llm_client: LLMClient 인스턴스.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def revise(
        self,
        current_plan: ScenePlan,
        parent_feedback: str,
        safety_rails: dict[str, Any],
        age_style: dict[str, Any] | None = None,
    ) -> ScenePlan:
        """부모 피드백을 반영해 ScenePlan을 수정한다.

        Args:
            current_plan: 현재 확정 전 ScenePlan.
            parent_feedback: 부모의 수정 요청 텍스트.
            safety_rails: 안전 규칙 dict (safety-rails.json 구조).
            age_style: 연령별 문체 규칙 dict. 제공 시 장면 수 범위 검증도 실행.

        Returns:
            수정된 ScenePlan 인스턴스.

        Raises:
            ScenePlanSafetyError: 수정 후 안전 규칙 위반.
            ScenePlanError: age_style 제공 시 장면 수 범위 오류 등.
            LLMClientError: LLM 호출 자체 실패.
            PlanReviserError: 응답 파싱 실패.
        """
        prohibitions = safety_rails.get("prohibitions", [])
        system = _SYSTEM_PROMPT_TEMPLATE.format(
            safety_prohibitions="\n".join(f"- {p}" for p in prohibitions),
        )

        user = _USER_PROMPT_TEMPLATE.format(
            current_plan_json=json.dumps(
                current_plan.model_dump(), ensure_ascii=False, indent=2
            ),
            parent_feedback=parent_feedback,
        )

        logger.info(
            "plan_revise prompt_version=%s scene_count=%d",
            _PROMPT_VERSION,
            len(current_plan.scenes),
        )

        # 안전 필터 차단 시 최대 _MAX_SAFETY_RETRIES 회 재생성
        last_safety_error: ScenePlanSafetyError | None = None
        for attempt in range(_MAX_SAFETY_RETRIES + 1):
            if attempt > 0:
                logger.warning(
                    "plan_revise safety_retry attempt=%d/%d reason=%s",
                    attempt,
                    _MAX_SAFETY_RETRIES,
                    last_safety_error,
                )

            raw: dict[str, Any] = await self._client.complete_json(
                system,
                user,
                temperature=_TEMPERATURE,
                max_tokens=_MAX_TOKENS,
            )

            revised = self._parse_response(raw)

            try:
                if age_style is not None:
                    validate_scene_plan(revised, age_style, safety_rails)
                else:
                    _validate_safety_only(revised, safety_rails)
                return revised
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
            raise PlanReviserError(
                f"scenes 필드가 리스트가 아닙니다: {type(scenes_raw)}"
            )

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


# ---------------------------------------------------------------------------
# 안전 키워드 전용 검증 (age_style 없을 때)
# ---------------------------------------------------------------------------


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
