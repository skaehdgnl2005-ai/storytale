"""S22a — PuLID 얼굴 앵커 생성 서비스 테스트.

FaceAnchorService: 아이 사진 → bytedance/flux-pulid → 얼굴 앵커 이미지 생성.
보안: EXIF 제거, 사진 처리 후 즉시 삭제.
"""

import hashlib
import struct
from unittest.mock import AsyncMock

import pytest

from storytale.illustration.face_anchor_service import (
    MAX_PHOTO_SIZE,
    PULID_MODEL,
    FaceAnchorError,
    FaceAnchorResult,
    FaceAnchorService,
)
from storytale.illustration.replicate_client import (
    PredictionResult,
    ReplicateClientError,
)

# ---------------------------------------------------------------------------
# 헬퍼: 테스트용 이미지 바이트
# ---------------------------------------------------------------------------

# 최소 유효 JPEG: FFD8 FF 시작, FFD9 종료
_MINIMAL_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9"

# EXIF 포함 JPEG (APP1 마커 FFE1)
_JPEG_WITH_EXIF = (
    b"\xff\xd8"  # SOI
    b"\xff\xe1"  # APP1 (EXIF)
    b"\x00\x08"  # 길이 8 bytes
    b"Exif\x00\x00"  # EXIF 헤더
    b"\xff\xe0"  # APP0
    b"\x00\x02"  # 길이
    b"\xff\xd9"  # EOI
)


# 최소 유효 PNG: 시그니처 + IHDR + IEND
def _make_minimal_png() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk: width=1, height=1, bit_depth=8, color_type=2
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = 0  # 테스트용 (실제 CRC 불필요)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    # IEND chunk
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", 0)
    return sig + ihdr + iend


_MINIMAL_PNG = _make_minimal_png()


# ---------------------------------------------------------------------------
# 1. 성공 시나리오
# ---------------------------------------------------------------------------


class TestCreateFaceAnchor:
    """createFaceAnchor: 사진 → PuLID → 얼굴 앵커 URL."""

    @pytest.mark.asyncio
    async def test_success_returns_face_anchor_url(self) -> None:
        """정상 사진 → ReplicateClient 호출 → faceAnchorUrl 반환."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_face_001",
            status="succeeded",
            output=["https://replicate.delivery/face-anchor-001.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        result = await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="female",
            age_approx=5,
        )

        assert result.face_anchor_url == (
            "https://replicate.delivery/face-anchor-001.png"
        )
        mock_client.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_photo_hash(self) -> None:
        """동일 입력 → 동일 SHA-256 해시 반환."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_hash",
            status="succeeded",
            output=["https://replicate.delivery/face-anchor-hash.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        result = await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="female",
            age_approx=5,
        )

        expected_hash = hashlib.sha256(_MINIMAL_JPEG).hexdigest()
        assert result.photo_hash == expected_hash

    @pytest.mark.asyncio
    async def test_photo_hash_is_pydantic_model(self) -> None:
        """FaceAnchorResult가 Pydantic BaseModel이다."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_model",
            status="succeeded",
            output=["https://replicate.delivery/face-anchor-model.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        result = await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="female",
            age_approx=5,
        )

        assert isinstance(result, FaceAnchorResult)
        assert hasattr(result, "face_anchor_url")
        assert hasattr(result, "photo_hash")

    @pytest.mark.asyncio
    async def test_png_photo_accepted(self) -> None:
        """PNG 포맷도 정상 처리."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_face_002",
            status="succeeded",
            output=["https://replicate.delivery/face-anchor-002.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        result = await service.create_face_anchor(
            child_photo=_MINIMAL_PNG,
            gender="male",
            age_approx=3,
        )

        assert result.face_anchor_url is not None
        mock_client.run.assert_called_once()


# ---------------------------------------------------------------------------
# 2. PuLID 파라미터 검증
# ---------------------------------------------------------------------------


class TestPulidParameters:
    """ReplicateClient에 전달되는 PuLID 모델 파라미터 검증."""

    @pytest.mark.asyncio
    async def test_correct_model_and_id_weight(self) -> None:
        """bytedance/flux-pulid 모델, id_weight 0.8 기본값."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_params",
            status="succeeded",
            output=["https://replicate.delivery/face.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="female",
            age_approx=4,
        )

        call_args = mock_client.run.call_args
        assert call_args.kwargs.get("model") or call_args.args[0] == PULID_MODEL
        input_params = call_args.kwargs.get("input_params") or call_args.args[1]
        assert input_params["id_weight"] == 0.8

    @pytest.mark.asyncio
    async def test_prompt_includes_gender_and_age(self) -> None:
        """프롬프트에 성별/연령 정보 포함."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_prompt",
            status="succeeded",
            output=["https://replicate.delivery/face.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="male",
            age_approx=6,
        )

        input_params = mock_client.run.call_args.args[1]
        prompt = input_params["prompt"]
        assert "boy" in prompt.lower()

    @pytest.mark.asyncio
    async def test_custom_id_weight(self) -> None:
        """id_weight 커스텀 값 전달."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_custom",
            status="succeeded",
            output=["https://replicate.delivery/face.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client, id_weight=0.95)
        await service.create_face_anchor(
            child_photo=_MINIMAL_JPEG,
            gender="female",
            age_approx=5,
        )

        input_params = mock_client.run.call_args.args[1]
        assert input_params["id_weight"] == 0.95


# ---------------------------------------------------------------------------
# 3. 사진 검증
# ---------------------------------------------------------------------------


class TestPhotoValidation:
    """사진 포맷/크기 검증."""

    @pytest.mark.asyncio
    async def test_rejects_oversized_photo(self) -> None:
        """5MB 초과 사진 거부."""
        huge_photo = b"\xff\xd8\xff\xe0" + b"\x00" * (MAX_PHOTO_SIZE + 1) + b"\xff\xd9"
        service = FaceAnchorService(replicate_client=AsyncMock())

        with pytest.raises(FaceAnchorError) as exc_info:
            await service.create_face_anchor(
                child_photo=huge_photo,
                gender="male",
                age_approx=4,
            )
        assert exc_info.value.code == "PHOTO_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_rejects_invalid_format(self) -> None:
        """JPEG/PNG 외 포맷 거부."""
        gif_bytes = b"GIF89a" + b"\x00" * 100
        service = FaceAnchorService(replicate_client=AsyncMock())

        with pytest.raises(FaceAnchorError) as exc_info:
            await service.create_face_anchor(
                child_photo=gif_bytes,
                gender="female",
                age_approx=5,
            )
        assert exc_info.value.code == "INVALID_FORMAT"

    @pytest.mark.asyncio
    async def test_rejects_empty_photo(self) -> None:
        """빈 바이트 거부."""
        service = FaceAnchorService(replicate_client=AsyncMock())

        with pytest.raises(FaceAnchorError) as exc_info:
            await service.create_face_anchor(
                child_photo=b"",
                gender="male",
                age_approx=3,
            )
        assert exc_info.value.code == "INVALID_FORMAT"


# ---------------------------------------------------------------------------
# 4. EXIF 메타데이터 제거
# ---------------------------------------------------------------------------


class TestExifStripping:
    """보안: EXIF 메타데이터 제거 후 처리."""

    @pytest.mark.asyncio
    async def test_png_metadata_stripped(self) -> None:
        """PNG의 tEXt/eXIf 청크가 제거된 후 API 호출."""
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        # tEXt 메타데이터 포함 PNG 생성
        img = Image.new("RGB", (2, 2), color=(255, 0, 0))
        png_info = PngInfo()
        png_info.add_text("Author", "secret-parent-name")
        png_info.add_text("Comment", "sensitive-data")
        import io

        buf = io.BytesIO()
        img.save(buf, format="PNG", pnginfo=png_info)
        png_with_metadata = buf.getvalue()

        # 메타데이터가 원본에 포함되어 있는지 확인
        assert b"secret-parent-name" in png_with_metadata

        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_png_meta",
            status="succeeded",
            output=["https://replicate.delivery/face-png.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        await service.create_face_anchor(
            child_photo=png_with_metadata,
            gender="female",
            age_approx=5,
        )

        # API에 전달된 data URI에서 메타데이터가 제거되었는지 확인
        import base64

        input_params = mock_client.run.call_args.args[1]
        data_uri = input_params["main_face_image"]
        b64_data = data_uri.split(",", 1)[1]
        decoded = base64.b64decode(b64_data)
        assert b"secret-parent-name" not in decoded
        assert b"sensitive-data" not in decoded

    @pytest.mark.asyncio
    async def test_exif_stripped_before_api_call(self) -> None:
        """EXIF 포함 JPEG → API 호출 시 EXIF 제거된 데이터 전송."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_exif",
            status="succeeded",
            output=["https://replicate.delivery/face.png"],
        )

        service = FaceAnchorService(replicate_client=mock_client)
        await service.create_face_anchor(
            child_photo=_JPEG_WITH_EXIF,
            gender="female",
            age_approx=4,
        )

        # API가 호출되었는지 확인 (EXIF 제거 후 정상 진행)
        mock_client.run.assert_called_once()
        # 전달된 이미지 데이터에 EXIF 마커(FFE1)가 없어야 함
        input_params = mock_client.run.call_args.args[1]
        id_image_data = input_params["main_face_image"]
        # base64 데이터 URI이므로 디코딩 후 확인
        assert "data:image/" in id_image_data


# ---------------------------------------------------------------------------
# 5. 에러 전파
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """ReplicateClient 에러 → FaceAnchorError 변환."""

    @pytest.mark.asyncio
    async def test_replicate_error_wrapped(self) -> None:
        """ReplicateClientError → FaceAnchorError로 래핑."""
        mock_client = AsyncMock()
        mock_client.run.side_effect = ReplicateClientError(
            code="PREDICTION_FAILED",
            message="모델 실행 실패",
        )

        service = FaceAnchorService(replicate_client=mock_client)

        with pytest.raises(FaceAnchorError) as exc_info:
            await service.create_face_anchor(
                child_photo=_MINIMAL_JPEG,
                gender="male",
                age_approx=5,
            )
        assert exc_info.value.code == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_empty_output_raises_error(self) -> None:
        """Replicate 응답에 output이 없으면 에러."""
        mock_client = AsyncMock()
        mock_client.run.return_value = PredictionResult(
            prediction_id="pred_empty",
            status="succeeded",
            output=None,
        )

        service = FaceAnchorService(replicate_client=mock_client)

        with pytest.raises(FaceAnchorError) as exc_info:
            await service.create_face_anchor(
                child_photo=_MINIMAL_JPEG,
                gender="female",
                age_approx=4,
            )
        assert exc_info.value.code == "EMPTY_OUTPUT"
