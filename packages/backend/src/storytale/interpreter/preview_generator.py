"""부모 미리보기 생성 모듈 (1층 AI 인터프리터, Step 3).

ScenePlan → StoryPreview (제목 + 요약 + 이모지 장면 하이라이트).
부모에게 보여줄 미리보기를 LLM으로 생성한다.
"""

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import ScenePlan

logger = logging.getLogger(__name__)

# 프롬프트 버전 (docs/prompts/preview-generator-v1.md)
_PROMPT_VERSION = "preview-generator-v1"

# 권장 LLM 파라미터 (docs/prompts/preview-generator-v1.md 기준)
_TEMPERATURE = 0.3
_MAX_TOKENS = 1024

IllustrationStyle = Literal["watercolor", "pastel_crayon", "clean_digital"]


# ---------------------------------------------------------------------------
# 도메인 모델 (contracts/story-engine.ts StoryPreview 대응)
# ---------------------------------------------------------------------------


class StoryPreview(BaseModel):
    """부모에게 보여줄 미리보기. contracts StoryPreview 대응."""

    title: str
    summary: str
    scene_highlights: list[str]
    page_count: int
    style: IllustrationStyle


# ---------------------------------------------------------------------------
# 시스템 프롬프트 / 유저 프롬프트 템플릿
# docs/prompts/preview-generator-v1.md 에서 관리
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
당신은 동화책 기획 요약 전문가입니다.
장면 설계서(scene_plan)를 받아, 부모가 쉽게 이해할 수 있는 미리보기를 생성합니다.

## 규칙
1. summary: 2~3문장으로 전체 이야기를 요약. "~하는 이야기예요" 체.
2. scene_highlights: 각 장면을 이모지 + 한줄(15자 이내)로 요약.
   이모지는 장면의 감정/상황에 맞게 선택.
3. 부모 친화적 어조. 전문 용어 사용 금지.
4. 아이 이름이 있으면 사용. 없으면 "우리 아이".

## 출력 형식
{
  "title": "동화책 제목",
  "summary": "하은이가 ... 하는 이야기예요.",
  "scene_highlights": [
    "🎮 게임에서 지고 속상한 하은이",
    "🧸 토니를 멀리 던지는 하은이",
    "🐰 토끼가 넘어져도 웃는 모습",
    "💪 서준이와 다시 도전하는 하은이",
    "😊 지고도 웃을 수 있게 된 하은이"
  ],
  "style": "watercolor"
}\
"""

_USER_PROMPT_TEMPLATE = """\
## 장면 설계서
{scene_plan_json}

## 아이 이름
{child_name}

## 일러스트 스타일
{illustration_style}

부모에게 보여줄 미리보기를 생성하세요.\
"""


# ---------------------------------------------------------------------------
# PreviewGenerator
# ---------------------------------------------------------------------------


class PreviewGenerator:
    """ScenePlan → StoryPreview 변환기.

    Args:
        llm_client: LLMClient 인스턴스.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def generate(
        self,
        scene_plan: ScenePlan,
        style: IllustrationStyle,
        child_name: str | None = None,
    ) -> StoryPreview:
        """장면 설계서로부터 부모 미리보기를 생성한다.

        Args:
            scene_plan: S13 ScenePlanner가 반환한 ScenePlan.
            style: 일러스트 스타일.
            child_name: 아이 이름. None이면 "우리 아이" 사용.

        Returns:
            StoryPreview 인스턴스.

        Raises:
            LLMClientError: LLM 호출 실패.
        """
        resolved_name = child_name or "우리 아이"

        user = _USER_PROMPT_TEMPLATE.format(
            scene_plan_json=json.dumps(
                scene_plan.model_dump(), ensure_ascii=False, indent=2
            ),
            child_name=resolved_name,
            illustration_style=style,
        )

        logger.info(
            "preview_generate prompt_version=%s style=%s child_name=%s",
            _PROMPT_VERSION,
            style,
            "provided" if child_name else "default",
        )

        raw: dict[str, Any] = await self._client.complete_json(
            _SYSTEM_PROMPT,
            user,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )

        return self._parse_response(raw, scene_plan, style)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw: dict[str, Any],
        scene_plan: ScenePlan,
        style: IllustrationStyle,
    ) -> StoryPreview:
        """LLM 응답 dict → StoryPreview 변환.

        page_count와 style은 LLM 응답이 아닌 입력 데이터에서 결정한다.
        """
        return StoryPreview(
            title=raw.get("title", scene_plan.title),
            summary=raw.get("summary", ""),
            scene_highlights=raw.get("scene_highlights", []),
            page_count=len(scene_plan.scenes),
            style=style,
        )
