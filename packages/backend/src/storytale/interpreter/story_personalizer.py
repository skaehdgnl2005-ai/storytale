"""장면별 텍스트 생성 모듈 (3층 개인화 생성).

PlannedScene + ChildProfile → PersonalizedScene (그림책 텍스트 + 일러스트 프롬프트).
프롬프트: docs/prompts/story-personalizer-v1.md
"""

import logging
from typing import Any

from pydantic import BaseModel

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import PlannedScene, StyleNotes

logger = logging.getLogger(__name__)

# 프롬프트 버전 (docs/prompts/story-personalizer-v1.md)
_PROMPT_VERSION = "story-personalizer-v1"

# 권장 LLM 파라미터 (프롬프트 spec 기준)
_TEMPERATURE = 0.7
_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# 도메인 모델 (contracts/story-engine.ts 대응)
# ---------------------------------------------------------------------------


class ChildProfile(BaseModel):
    """아이 프로필. contracts ChildProfile 대응."""

    child_id: str
    name: str
    age: int
    gender: str  # "male" | "female"
    comfort_object: str | None = None
    friend_name: str | None = None
    favorite_animal: str | None = None
    character_sheet_url: str | None = None


class PersonalizedScene(BaseModel):
    """개인화된 장면 결과. contracts PersonalizedScene 대응."""

    scene_id: str
    page_number: int
    text: str
    illustration_prompt: str


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class StoryPersonalizerError(Exception):
    """장면 텍스트 생성 실패 (필수 필드 누락, 스키마 불일치 등)."""


# ---------------------------------------------------------------------------
# emotion_to_visual 매핑 (art-direction.json에서 발췌)
# ---------------------------------------------------------------------------

_EMOTION_TO_VISUAL: dict[str, dict[str, str]] = {
    "joy": {
        "palette_shift": "warm golden highlights, soft yellow-orange accents",
        "lighting": "bright warm sunlight, gentle lens flare",
        "whitespace": "적당한 여백. 활기차되 복잡하지 않게.",
        "background_hint": "꽃, 나비, 반짝이는 빛 입자 등 긍정적 요소 1~2개",
    },
    "sadness": {
        "palette_shift": "blue-gray undertones, muted cool pastels",
        "lighting": "soft diffused light, slightly dim, overcast feel",
        "whitespace": "많은 여백. 고립감이나 쓸쓸함을 공간으로 표현.",
        "background_hint": "비 오는 창가, 빈 벤치 등 고요한 요소. 어둡지는 않게.",
    },
    "fear": {
        "palette_shift": "muted cool tones, desaturated. NOT dark or scary",
        "lighting": "soft ambient light, gentle shadows only",
        "whitespace": "캐릭터 주변 넓은 여백으로 불안감 표현.",
        "background_hint": "살짝 흐릿한 배경. 위협적 요소 없이 낯설음만 표현.",
    },
    "anger": {
        "palette_shift": "warm reds softened to coral-pink",
        "lighting": "warm but slightly intense",
        "whitespace": "보통 수준. 에너지가 느껴지되 혼란스럽지 않게.",
        "background_hint": "바람에 날리는 나뭇잎 등 동적 요소.",
    },
    "courage": {
        "palette_shift": "warm amber and gold tones, subtle glow",
        "lighting": "golden hour lighting, warm directional light from front",
        "whitespace": "중간. 캐릭터 앞에 열린 공간을 두어 '나아감'을 암시.",
        "background_hint": "길, 문, 언덕 등 '앞으로 나아가는' 상징적 요소",
    },
    "comfort": {
        "palette_shift": "soft warm cream and peach tones",
        "lighting": "warm indoor lighting, cozy lamplight feel",
        "whitespace": "적은 여백. 포근하고 아늑한 감싸는 느낌.",
        "background_hint": "이불, 쿠션, 위안 물건 등 안정감을 주는 소품",
    },
}


# ---------------------------------------------------------------------------
# 시스템 프롬프트 템플릿
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
당신은 아동 그림책 작가입니다.
장면 설계서를 받아, 아이의 개인 정보를 자연스럽게 엮어 실제 그림책 텍스트를 작성합니다.

## 역할
- 주어진 장면의 description을 기반으로 그림책 텍스트를 완성합니다.
- 설계서에 없는 새로운 사건이나 캐릭터를 추가하지 마세요.
- child_elements에 명시된 개인화 요소를 반드시 포함하세요.

## 문체 규칙 (연령: {age_group})
- 한 문장 최대 {max_characters_per_sentence}자.
- 문장 구조: {preferred_structure}.
- 반복 패턴: {repetition_pattern}.
- 어휘: {vocabulary_level} 수준. 어려운 단어 금지.
- 감정 표현: {emotional_expression_method}.
  좋은 예: {good_examples}
  나쁜 예: {bad_examples}
- 한 페이지에 {sentences_per_page_min}~{sentences_per_page_max}문장 \
(최대 {max_characters_per_page}자).

## 스타일 노트
- 어조: {tone}
- 피할 것: {avoid}
- 반복 모티프: {repetition_motif}

## 일러스트 프롬프트 작성 규칙
- 영문으로 작성. 50~100단어.
- **프롬프트 구조 (반드시 아래 순서를 따를 것)**:
  1. **Identity Block**: 캐릭터 시트에서 자동 주입됨. 절대 수정하지 말 것.
  2. **Action Block**: "[주체]가 [행동]하는 장면" 서술.
  3. **Emotion Block**: 장면 감정에 맞는 색감/조명/분위기.
  4. **Environment Block**: 배경, 소품. 소품 최대 3개, 여백 30~50%.
  5. **Style Block**: illustration style, children's book illustration.
- 아이 캐릭터: "{gender_pronoun}" 로 지칭. 이름 사용 금지 (개인정보 보호).
- 배경은 단순하게. 주인공의 감정이 중심이 되도록 여백의 미를 살린다.
- 아이 눈높이(로우 앵글) 구도. 위에서 내려다보는 시점 금지.

## 출력 형식
반드시 아래 JSON만 출력하세요.
{{
  "scene_id": "...",
  "page_number": ...,
  "text": "그림책에 나올 실제 한국어 텍스트. 줄바꿈은 \\n으로.",
  "illustration_prompt": "English prompt for illustration generation..."
}}\
"""


# ---------------------------------------------------------------------------
# 유저 프롬프트 템플릿
# ---------------------------------------------------------------------------

_USER_PROMPT_TEMPLATE = """\
## 아이 정보
- 이름: {child_name}
- 나이: {child_age}세
- 성별: {child_gender_kr}
- 위안 물건: {comfort_object}
- 친구: {friend_name}
- 좋아하는 동물: {favorite_animal}

## Identity Prompt Block (일러스트 프롬프트에 그대로 삽입)
{identity_prompt_block}

## 아트 디렉션 — 감정별 시각 가이드
{emotion_visual_guide}

## 현재 장면 ({scene_index}/{total_scenes})
- 장면 ID: {scene_id}
- 감정: {emotion}
- 목적: {purpose}
- 장면 설명: {description}
- 개인화 요소: {child_elements}

## 이전 장면 요약
{previous_summary}

이 장면의 그림책 텍스트와 일러스트 프롬프트를 생성하세요.\
"""


# ---------------------------------------------------------------------------
# StoryPersonalizer
# ---------------------------------------------------------------------------


class StoryPersonalizer:
    """PlannedScene + ChildProfile → PersonalizedScene 변환기.

    Args:
        llm_client: LLMClient 인스턴스.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def generate_scene(
        self,
        scene: PlannedScene,
        child: ChildProfile,
        previous_summary: str,
        age_style: dict[str, Any],
        style_notes: StyleNotes,
        scene_index: int,
        total_scenes: int,
        identity_prompt_block: str | None = None,
    ) -> PersonalizedScene:
        """장면 하나에 대한 개인화 텍스트 + 일러스트 프롬프트를 생성한다.

        Args:
            scene: S13에서 생성된 PlannedScene.
            child: 아이 프로필.
            previous_summary: 이전 장면 요약 (첫 장면이면 "없음").
            age_style: 연령별 문체 규칙 dict.
            style_notes: 스토리 스타일 노트.
            scene_index: 현재 장면 번호 (1부터).
            total_scenes: 전체 장면 수.
            identity_prompt_block: 캐릭터 시트 기반 외형 묘사 (S22 이후 제공).

        Returns:
            PersonalizedScene 인스턴스.

        Raises:
            StoryPersonalizerError: 응답 파싱 실패 또는 필수 필드 누락.
            LLMClientError: LLM 호출 자체 실패.
        """
        system = self._build_system_prompt(child, age_style, style_notes)
        user = self._build_user_prompt(
            scene=scene,
            child=child,
            previous_summary=previous_summary,
            scene_index=scene_index,
            total_scenes=total_scenes,
            identity_prompt_block=identity_prompt_block,
        )

        logger.info(
            "story_personalizer prompt_version=%s scene_id=%s child_id=%s",
            _PROMPT_VERSION,
            scene.scene_id,
            child.child_id,
        )

        raw: dict[str, Any] = await self._client.complete_json(
            system,
            user,
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )

        return self._parse_response(raw)

    # ------------------------------------------------------------------
    # 프롬프트 빌더
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        child: ChildProfile,
        age_style: dict[str, Any],
        style_notes: StyleNotes,
    ) -> str:
        sentence_rules = age_style.get("sentence_rules", {})
        emotional_expr = age_style.get("emotional_expression", {})
        page_guide = age_style.get("page_guidelines", {})
        sentences_per_page = page_guide.get("sentences_per_page", {})

        gender_pronoun = "a young boy" if child.gender == "male" else "a young girl"

        return _SYSTEM_PROMPT_TEMPLATE.format(
            age_group=age_style.get("age_group", "3-4"),
            max_characters_per_sentence=sentence_rules.get(
                "max_characters_per_sentence", 20
            ),
            preferred_structure=sentence_rules.get("preferred_structure", "단문"),
            repetition_pattern=sentence_rules.get("repetition_pattern", "AAB"),
            vocabulary_level=sentence_rules.get(
                "vocabulary_level", "일상 단어 500개 이내"
            ),
            emotional_expression_method=emotional_expr.get("method", ""),
            good_examples=", ".join(emotional_expr.get("good_examples", [])),
            bad_examples=", ".join(emotional_expr.get("bad_examples", [])),
            sentences_per_page_min=sentences_per_page.get("min", 2),
            sentences_per_page_max=sentences_per_page.get("max", 3),
            max_characters_per_page=page_guide.get("max_characters_per_page", 50),
            tone=style_notes.tone,
            avoid=", ".join(style_notes.avoid),
            repetition_motif=style_notes.repetition_motif or "없음",
            gender_pronoun=gender_pronoun,
        )

    def _build_user_prompt(
        self,
        scene: PlannedScene,
        child: ChildProfile,
        previous_summary: str,
        scene_index: int,
        total_scenes: int,
        identity_prompt_block: str | None,
    ) -> str:
        gender_kr = "남자" if child.gender == "male" else "여자"

        # Identity Prompt Block 처리
        if identity_prompt_block:
            identity_text = identity_prompt_block
        else:
            identity_text = (
                "(Identity Prompt Block 미제공 — 캐릭터 시트 생성 전입니다. "
                "일러스트 프롬프트에 기본 외형 묘사를 포함하세요.)"
            )

        # 감정별 시각 가이드 조립
        emotion_visual_guide = self._build_emotion_visual_guide(scene.emotion)

        return _USER_PROMPT_TEMPLATE.format(
            child_name=child.name,
            child_age=child.age,
            child_gender_kr=gender_kr,
            comfort_object=child.comfort_object or "없음",
            friend_name=child.friend_name or "없음",
            favorite_animal=child.favorite_animal or "없음",
            identity_prompt_block=identity_text,
            emotion_visual_guide=emotion_visual_guide,
            scene_index=scene_index,
            total_scenes=total_scenes,
            scene_id=scene.scene_id,
            emotion=scene.emotion,
            purpose=scene.purpose,
            description=scene.description,
            child_elements=", ".join(scene.child_elements),
            previous_summary=previous_summary,
        )

    def _build_emotion_visual_guide(self, emotion: str) -> str:
        """현재 장면 감정에 해당하는 시각 가이드를 텍스트로 조립."""
        visual = _EMOTION_TO_VISUAL.get(emotion)
        if not visual:
            return (
                f"(감정 '{emotion}'에 대한 사전 정의된 시각 가이드가 "
                "없습니다. 장면 감정에 맞게 자유롭게 묘사하세요.)"
            )

        lines = [f"감정: {emotion}"]
        for key, value in visual.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 응답 파싱
    # ------------------------------------------------------------------

    def _parse_response(self, raw: dict[str, Any]) -> PersonalizedScene:
        """LLM 응답 dict → PersonalizedScene 변환.

        Raises:
            StoryPersonalizerError: 필수 필드 누락 시.
        """
        scene_id = raw.get("scene_id")
        page_number = raw.get("page_number")
        text = raw.get("text")
        illustration_prompt = raw.get("illustration_prompt")

        missing = []
        if not scene_id:
            missing.append("scene_id")
        if page_number is None:
            missing.append("page_number")
        if not text:
            missing.append("text")
        if not illustration_prompt:
            missing.append("illustration_prompt")

        if missing:
            raise StoryPersonalizerError(
                f"LLM 응답에 필수 필드가 누락되었습니다: {', '.join(missing)}"
            )

        return PersonalizedScene(
            scene_id=scene_id,
            page_number=page_number,
            text=text,
            illustration_prompt=illustration_prompt,
        )
