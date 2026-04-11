"""의도 분석 모듈 (1층 AI 인터프리터, Step 1).

부모의 서술형 텍스트를 분석하여 구조화된 IntentAnalysis를 반환한다.
"""

import json
import logging
import os
import pathlib
from typing import Any

from pydantic import BaseModel

from storytale.interpreter.llm_client import LLMClient

logger = logging.getLogger(__name__)

# contracts/story-engine.ts IntentCategory
_VALID_CATEGORIES = frozenset(
    {"value_teaching", "interest_story", "problem_solving", "celebration"}
)

_ARC_TEMPLATES_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
    / "docs"
    / "guardrail-seeds"
    / "emotional-arcs.json"
)

# 프롬프트 파일 위치 (로깅/디버그 용도)
_PROMPT_VERSION = "intent-analyzer-v1"

# 권장 LLM 파라미터 (docs/prompts/intent-analyzer-v1.md 기준)
_TEMPERATURE = 0.3
_MAX_TOKENS = 1024


class IntentAnalysis(BaseModel):
    """분석된 부모 의도. contracts/story-engine.ts IntentAnalysis 대응."""

    intent_category: str
    core_theme: str
    trigger_situation: str
    child_current_behavior: str
    parent_desired_outcome: str
    emotional_keywords: list[str]
    recommended_arc_id: str


class RejectedIntentError(Exception):
    """LLM이 부적절한 요청으로 판단하여 거부한 경우."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class IntentAnalysisError(Exception):
    """의도 분석 실패 (잘못된 arc_id, 잘못된 category 등)."""


# ---------------------------------------------------------------------------
# 시스템 프롬프트 / 유저 프롬프트 템플릿
# docs/prompts/intent-analyzer-v1.md 에서 관리
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
당신은 아동발달 전문가이자 동화책 기획자입니다.
부모가 보내는 짧은 텍스트를 분석하여, 동화책의 설계 방향을 구조화합니다.

## 입력
- 부모가 선택한 목적 카테고리
  (value_teaching / interest_story / problem_solving / celebration)
- 부모가 작성한 서술형 텍스트 (1~2문장)
- 아이의 나이

## 당신의 임무
부모의 텍스트에서 다음을 추출하세요:
1. core_theme: 이 동화책의 핵심 주제 (명사형, 4~8글자)
2. trigger_situation: 아이가 겪는 구체적 상황
3. child_current_behavior: 아이의 현재 행동/상태
4. parent_desired_outcome: 부모가 바라는 변화
5. emotional_keywords: 이 상황에서 아이가 느낄 감정 키워드 (3~5개)
6. recommended_arc_id: 아래 감정 흐름 템플릿 중 가장 적합한 것의 ID

## 사용 가능한 감정 흐름 템플릿
{arc_templates}

## 규칙
- 부모가 명시하지 않은 내용을 과도하게 추론하지 마세요.
- child_current_behavior가 텍스트에 없으면 "명시되지 않음"으로.
- recommended_arc_id는 반드시 위 템플릿 목록에 있는 ID여야 합니다.
- 부적절한 요청(폭력, 혐오 등)이면 전체 응답을 {{"rejected": true, "reason": "..."}} 로.

## 출력 형식
반드시 아래 JSON만 출력하세요. 다른 텍스트를 포함하지 마세요.
{{
  "intent_category": "...",
  "core_theme": "...",
  "trigger_situation": "...",
  "child_current_behavior": "...",
  "parent_desired_outcome": "...",
  "emotional_keywords": ["...", "...", "..."],
  "recommended_arc_id": "..."
}}\
"""

_USER_PROMPT_TEMPLATE = """\
목적: {purpose_category}
아이 나이: {child_age}세
부모 입력: "{parent_text}"\
"""


class IntentAnalyzer:
    """부모 텍스트 → IntentAnalysis 변환기.

    Args:
        llm_client: LLMClient 인스턴스.
        arc_templates: 감정 흐름 템플릿 목록 (emotional-arcs.json 구조).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        arc_templates: list[dict[str, Any]],
    ) -> None:
        self._client = llm_client
        self._arc_templates = arc_templates
        self._valid_arc_ids = frozenset(t["arc_id"] for t in arc_templates)

    async def analyze(
        self,
        parent_text: str,
        purpose_category: str,
        child_age: int,
    ) -> IntentAnalysis:
        """부모 텍스트를 분석하여 IntentAnalysis 반환.

        Args:
            parent_text: 부모가 작성한 서술형 텍스트.
            purpose_category: IntentCategory 값.
            child_age: 아이 나이 (정수).

        Returns:
            IntentAnalysis 인스턴스.

        Raises:
            RejectedIntentError: 부적절한 요청이라 LLM이 거부한 경우.
            IntentAnalysisError: arc_id/category 검증 실패 등.
            LLMClientError: LLM 호출 자체 실패.
        """
        system = self._build_system_prompt()
        user = _USER_PROMPT_TEMPLATE.format(
            purpose_category=purpose_category,
            child_age=child_age,
            parent_text=parent_text,
        )

        logger.info(
            "intent_analyze prompt_version=%s purpose=%s age=%d",
            _PROMPT_VERSION,
            purpose_category,
            child_age,
        )

        raw: dict[str, Any] = await self._client.complete_json(
            system,
            user,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )

        return self._validate_and_build(raw)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """arc_templates 를 삽입한 시스템 프롬프트 생성."""
        # arc_id + description 만 요약하여 토큰 절약
        arc_summary = [
            {"arc_id": t["arc_id"], "description": t["description"]}
            for t in self._arc_templates
        ]
        return _SYSTEM_PROMPT_TEMPLATE.format(
            arc_templates=json.dumps(arc_summary, ensure_ascii=False, indent=2)
        )

    def _validate_and_build(self, raw: dict[str, Any]) -> IntentAnalysis:
        """LLM 응답을 검증하고 IntentAnalysis 인스턴스로 변환."""
        # 거부 응답 확인
        if raw.get("rejected"):
            reason = raw.get("reason", "부적절한 요청")
            raise RejectedIntentError(reason)

        # intent_category 검증
        category = raw.get("intent_category", "")
        if category not in _VALID_CATEGORIES:
            raise IntentAnalysisError(
                f"알 수 없는 intent_category: '{category}'. "
                f"허용값: {sorted(_VALID_CATEGORIES)}"
            )

        # recommended_arc_id 검증
        arc_id = raw.get("recommended_arc_id", "")
        if arc_id not in self._valid_arc_ids:
            raise IntentAnalysisError(
                f"알 수 없는 arc_id: '{arc_id}'. 허용값: {sorted(self._valid_arc_ids)}"
            )

        return IntentAnalysis(
            intent_category=category,
            core_theme=raw.get("core_theme", ""),
            trigger_situation=raw.get("trigger_situation", ""),
            child_current_behavior=raw.get("child_current_behavior", "명시되지 않음"),
            parent_desired_outcome=raw.get("parent_desired_outcome", ""),
            emotional_keywords=raw.get("emotional_keywords", []),
            recommended_arc_id=arc_id,
        )

    # ------------------------------------------------------------------
    # 클래스 메서드
    # ------------------------------------------------------------------

    @classmethod
    def load_arc_templates_from_json(
        cls,
        path: str | os.PathLike[str] | None = None,
    ) -> list[dict[str, Any]]:
        """emotional-arcs.json 에서 템플릿 목록을 로드한다.

        Args:
            path: JSON 파일 경로. None이면 프로젝트 기본 경로 사용.

        Returns:
            arc 템플릿 dict 목록.
        """
        target = pathlib.Path(path) if path else _ARC_TEMPLATES_PATH
        with target.open(encoding="utf-8") as f:
            return json.load(f)
