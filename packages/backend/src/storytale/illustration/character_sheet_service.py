"""멀티뷰 캐릭터 시트 + Identity Prompt Block 서비스.

얼굴 앵커(S22a) + 스타일 → PuLID 기반 정면/3/4/측면 멀티뷰 이미지 생성.
캐릭터 시트를 LLM(Claude)에 분석시켜 Identity Prompt Block 텍스트 추출.
같은 아이(photo_hash) + 같은 스타일이면 기존 시트 재사용.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from storytale.illustration.replicate_client import (
    ReplicateClient,
    ReplicateClientError,
)

logger = logging.getLogger(__name__)

PULID_MODEL = "bytedance/flux-pulid"
DEFAULT_ID_WEIGHT = 0.85

# 뷰별 프롬프트 지시어
_VIEW_DIRECTIVES: dict[str, str] = {
    "front": "front-facing portrait, looking directly at camera",
    "three_quarter": (
        "three-quarter angle portrait, slightly turned to the right, natural pose"
    ),
    "side": "side profile portrait, facing right",
}

_IDENTITY_BLOCK_SYSTEM_PROMPT = """\
You are a character description specialist for children's book illustrations.
Given a character's attributes, generate a concise English appearance \
description that will be used as an identity anchor across all illustrations.

Rules:
- Output ONLY the description text, no labels or formatting.
- Include: face shape, hair (color, length, style), eyes, \
distinguishing features, clothing.
- Keep under 50 words.
- Use natural, descriptive language suitable for image generation prompts.
- Do NOT include background, action, or emotion descriptions.
"""


class CharacterReferenceImages(BaseModel):
    """멀티뷰 참조 이미지 (계약: CharacterReferenceImages)."""

    model_config = ConfigDict(populate_by_name=True)

    front: str
    three_quarter: str | None = Field(default=None, alias="threeQuarter")
    side: str | None = None


class CharacterSheet(BaseModel):
    """멀티뷰 캐릭터 시트."""

    model_config = ConfigDict(populate_by_name=True)

    character_id: str = Field(alias="characterId", default="")
    reference_images: CharacterReferenceImages = Field(
        alias="referenceImages",
    )
    face_anchor_url: str = Field(alias="faceAnchorUrl", default="")
    identity_prompt_block: str = Field(alias="identityPromptBlock", default="")
    style: str
    created_at: str = Field(alias="createdAt", default="")
    gender: str
    age_approx: int = Field(alias="ageApprox", default=0)


class CharacterSheetError(Exception):
    """캐릭터 시트 생성 실패."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CharacterSheetService:
    """멀티뷰 캐릭터 시트 생성 + Identity Prompt Block 추출.

    Args:
        replicate_client: PuLID 이미지 생성용.
        llm_client: Identity Prompt Block 생성용.
        style_definitions: art-direction.json의 style_definitions.
        id_weight: PuLID 얼굴 동일성 가중치. 기본 0.85.
    """

    def __init__(
        self,
        replicate_client: ReplicateClient,
        llm_client: Any,
        style_definitions: dict[str, Any],
        id_weight: float = DEFAULT_ID_WEIGHT,
    ) -> None:
        self._replicate = replicate_client
        self._llm = llm_client
        self._styles = style_definitions
        self._id_weight = id_weight
        self._cache: dict[tuple[str, str], CharacterSheet] = {}

    async def create_character_sheet(
        self,
        face_anchor_url: str,
        style: str,
        gender: str,
        age_approx: int,
    ) -> CharacterSheet:
        """얼굴 앵커 + 스타일 → 3뷰 참조 이미지 생성.

        Returns:
            identity_prompt_block이 빈 CharacterSheet.
            generate_identity_prompt_block()으로 후속 채워야 함.
        """
        if style not in self._styles:
            raise CharacterSheetError(
                code="INVALID_STYLE",
                message=f"지원하지 않는 스타일: {style}",
            )

        style_def = self._styles[style]
        gender_word = "boy" if gender == "male" else "girl"

        view_urls: dict[str, str] = {}
        for view_name, view_directive in _VIEW_DIRECTIVES.items():
            url = await self._generate_view(
                face_anchor_url=face_anchor_url,
                view_directive=view_directive,
                gender_word=gender_word,
                age_approx=age_approx,
                style_def=style_def,
                style_name=style,
            )
            view_urls[view_name] = url

        ref_images = CharacterReferenceImages(
            front=view_urls["front"],
            three_quarter=view_urls.get("three_quarter"),
            side=view_urls.get("side"),
        )

        sheet = CharacterSheet(
            character_id=uuid.uuid4().hex,
            reference_images=ref_images,
            face_anchor_url=face_anchor_url,
            identity_prompt_block="",
            style=style,
            created_at=datetime.now(UTC).isoformat(),
            gender=gender,
            age_approx=age_approx,
        )

        logger.info(
            "character_sheet_created id=%s style=%s views=%d",
            sheet.character_id,
            style,
            len(view_urls),
        )

        return sheet

    async def generate_identity_prompt_block(
        self,
        character_sheet: CharacterSheet,
    ) -> str:
        """캐릭터 속성 기반 Identity Prompt Block 텍스트 생성."""
        gender_word = "boy" if character_sheet.gender == "male" else "girl"
        user_prompt = (
            f"Character: a {character_sheet.age_approx}-year-old "
            f"{gender_word}.\n"
            f"Illustration style: {character_sheet.style}.\n"
            f"Generate a concise English appearance description "
            f"for this child character in a children's book."
        )

        try:
            result = await self._llm.complete(
                system=_IDENTITY_BLOCK_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.4,
                max_tokens=200,
            )
        except Exception as exc:
            logger.error(
                "identity_block_failed character_id=%s error=%s",
                character_sheet.character_id,
                exc,
            )
            raise CharacterSheetError(
                code="IDENTITY_BLOCK_FAILED",
                message=f"Identity Prompt Block 생성 실패: {exc}",
            ) from exc

        logger.info(
            "identity_block_generated character_id=%s length=%d",
            character_sheet.character_id,
            len(result),
        )

        return result.strip()

    async def get_existing_sheet(
        self,
        photo_hash: str,
        style: str,
    ) -> CharacterSheet | None:
        """캐시에서 기존 시트 조회."""
        return self._cache.get((photo_hash, style))

    def cache_sheet(
        self,
        photo_hash: str,
        sheet: CharacterSheet,
    ) -> None:
        """시트를 캐시에 저장."""
        self._cache[(photo_hash, sheet.style)] = sheet

    # ------------------------------------------------------------------
    # 내부
    # ------------------------------------------------------------------

    async def _generate_view(
        self,
        face_anchor_url: str,
        view_directive: str,
        gender_word: str,
        age_approx: int,
        style_def: dict[str, Any],
        style_name: str,
    ) -> str:
        """단일 뷰 이미지 생성."""
        positive = ", ".join(style_def.get("positive_modifiers", []))
        prompt = (
            f"{view_directive}, "
            f"a {age_approx}-year-old {gender_word}, "
            f"{positive}, "
            f"children's book illustration, {style_name} style"
        )

        input_params: dict[str, Any] = {
            "prompt": prompt,
            "main_face_image": face_anchor_url,
            "id_weight": self._id_weight,
            "num_steps": 20,
            "guidance": 4.0,
            "width": 512,
            "height": 512,
        }

        try:
            result = await self._replicate.run(PULID_MODEL, input_params)
        except ReplicateClientError as exc:
            raise CharacterSheetError(
                code="VIEW_GENERATION_FAILED",
                message=f"뷰 이미지 생성 실패: {exc}",
            ) from exc

        if not result.output:
            raise CharacterSheetError(
                code="VIEW_GENERATION_FAILED",
                message="PuLID 모델이 빈 출력을 반환.",
            )

        return result.output[0]
