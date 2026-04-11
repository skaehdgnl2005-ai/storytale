"""PuLID 얼굴 앵커 생성 서비스.

아이 사진 → bytedance/flux-pulid API → 스타일 무관 얼굴 앵커 이미지 생성.
얼굴 앵커는 1회만 생성하면 모든 스타일에서 재사용 가능.

보안:
- EXIF 메타데이터 자동 제거 후 처리.
- 사진 원본은 처리 후 메모리에서 즉시 폐기.
"""

import base64
import hashlib
import io
import logging
from typing import Any

from pydantic import BaseModel

from storytale.illustration.replicate_client import (
    ReplicateClient,
    ReplicateClientError,
)

logger = logging.getLogger(__name__)

PULID_MODEL = "bytedance/flux-pulid"
DEFAULT_ID_WEIGHT = 0.8
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5MB

# PuLID 얼굴 앵커 생성 프롬프트: 중립 배경, 깔끔한 조명, 스타일 무관
FACE_ANCHOR_PROMPT_TEMPLATE = (
    "a clean portrait photo of a {gender_word} child, "
    "approximately {age} years old, "
    "neutral white background, soft studio lighting, "
    "front-facing, natural expression, no accessories, "
    "high quality, photorealistic"
)

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG"

# JPEG APP1 마커 (EXIF)
_JPEG_APP1_MARKER = b"\xff\xe1"


class FaceAnchorResult(BaseModel):
    """얼굴 앵커 생성 결과."""

    face_anchor_url: str
    photo_hash: str


class FaceAnchorError(Exception):
    """얼굴 앵커 생성 실패."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class FaceAnchorService:
    """PuLID 기반 얼굴 앵커 생성 서비스.

    Args:
        replicate_client: Replicate API 클라이언트.
        id_weight: PuLID 얼굴 동일성 가중치 (0.0~1.0). 기본 0.8.
    """

    def __init__(
        self,
        replicate_client: ReplicateClient,
        id_weight: float = DEFAULT_ID_WEIGHT,
    ) -> None:
        self._client = replicate_client
        self._id_weight = id_weight

    async def create_face_anchor(
        self,
        child_photo: bytes,
        gender: str,
        age_approx: int,
    ) -> FaceAnchorResult:
        """아이 사진 → PuLID 얼굴 앵커 이미지 생성.

        Args:
            child_photo: 아이 사진 바이트 (JPEG 또는 PNG).
            gender: "male" 또는 "female".
            age_approx: 대략적인 나이.

        Returns:
            face_anchor_url을 포함하는 딕셔너리.

        Raises:
            FaceAnchorError: 사진 검증 실패, API 호출 실패 등.
        """
        self._validate_photo(child_photo)

        photo_hash = hashlib.sha256(child_photo).hexdigest()
        cleaned_photo = _strip_exif(child_photo)
        data_uri = _to_data_uri(cleaned_photo)

        prompt = FACE_ANCHOR_PROMPT_TEMPLATE.format(
            gender_word="boy" if gender == "male" else "girl",
            age=age_approx,
        )

        input_params: dict[str, Any] = {
            "prompt": prompt,
            "main_face_image": data_uri,
            "id_weight": self._id_weight,
            "num_steps": 20,
            "guidance": 4.0,
            "width": 512,
            "height": 512,
        }

        try:
            result = await self._client.run(PULID_MODEL, input_params)
        except ReplicateClientError as exc:
            logger.error(
                "face_anchor_generation_failed error=%s",
                exc,
            )
            raise FaceAnchorError(
                code="GENERATION_FAILED",
                message=f"얼굴 앵커 생성 실패: {exc}",
            ) from exc

        if not result.output:
            raise FaceAnchorError(
                code="EMPTY_OUTPUT",
                message="PuLID 모델이 빈 출력을 반환했습니다.",
            )

        face_anchor_url = result.output[0]

        logger.info(
            "face_anchor_created prediction_id=%s url=%s",
            result.prediction_id,
            face_anchor_url,
        )

        return FaceAnchorResult(
            face_anchor_url=face_anchor_url,
            photo_hash=photo_hash,
        )

    @staticmethod
    def _validate_photo(photo: bytes) -> None:
        """사진 포맷/크기 검증."""
        if len(photo) > MAX_PHOTO_SIZE:
            raise FaceAnchorError(
                code="PHOTO_TOO_LARGE",
                message=f"사진 크기가 {MAX_PHOTO_SIZE // (1024 * 1024)}MB 초과.",
            )

        if not (photo.startswith(_JPEG_MAGIC) or photo.startswith(_PNG_MAGIC)):
            raise FaceAnchorError(
                code="INVALID_FORMAT",
                message="JPEG 또는 PNG 포맷만 허용됩니다.",
            )


def _strip_png_metadata(photo: bytes) -> bytes:
    """PNG 메타데이터(tEXt, zTXt, iTXt, eXIf) 제거. Pillow로 픽셀만 재저장."""
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(photo))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except (UnidentifiedImageError, OSError):
        logger.warning("png_metadata_strip_failed — returning original")
        return photo


def _strip_exif(photo: bytes) -> bytes:
    """JPEG EXIF / PNG 메타데이터 제거."""
    if photo.startswith(_PNG_MAGIC):
        return _strip_png_metadata(photo)

    if not photo.startswith(_JPEG_MAGIC):
        return photo

    # JPEG 구조: SOI(FFD8) + 세그먼트들 + SOS + 이미지 데이터 + EOI(FFD9)
    # APP1(FFE1) 세그먼트만 제거하면 EXIF 삭제
    result = io.BytesIO()
    result.write(photo[:2])  # SOI

    pos = 2
    while pos < len(photo) - 1:
        if photo[pos] != 0xFF:
            # 이미지 데이터 영역 — 나머지 전부 복사
            result.write(photo[pos:])
            break

        marker = photo[pos : pos + 2]

        if marker == b"\xff\xd9":
            # EOI
            result.write(marker)
            break

        if marker in (b"\xff\xda",):
            # SOS — 이후 전부 이미지 데이터
            result.write(photo[pos:])
            break

        # 세그먼트 길이 읽기
        if pos + 3 >= len(photo):
            result.write(photo[pos:])
            break

        seg_len = int.from_bytes(photo[pos + 2 : pos + 4], "big")

        if marker == _JPEG_APP1_MARKER:
            # EXIF 세그먼트 — 건너뛰기
            pos += 2 + seg_len
            continue

        # 다른 세그먼트는 유지
        result.write(photo[pos : pos + 2 + seg_len])
        pos += 2 + seg_len

    return result.getvalue()


def _to_data_uri(photo: bytes) -> str:
    """사진 바이트 → base64 data URI 변환."""
    mime = "image/png" if photo.startswith(_PNG_MAGIC) else "image/jpeg"

    encoded = base64.b64encode(photo).decode("ascii")
    return f"data:{mime};base64,{encoded}"
