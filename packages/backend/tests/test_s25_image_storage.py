"""S25 — S3 이미지 관리 서비스 테스트.

ImageStorageService: 업로드, URL 생성, 삭제.
boto3 호출은 모킹. 단위 테스트.
"""

from unittest.mock import AsyncMock, patch

import pytest

from storytale.illustration.image_storage_service import (
    ImageStorageError,
    ImageStorageService,
)

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

BUCKET = "storytale-images"
REGION = "ap-northeast-2"


@pytest.fixture
def service() -> ImageStorageService:
    return ImageStorageService(bucket=BUCKET, region=REGION)


# ---------------------------------------------------------------------------
# 1. upload — 이미지 업로드 → public URL 반환
# ---------------------------------------------------------------------------


class TestUpload:
    """upload(): S3에 이미지 업로드 후 URL 반환."""

    @pytest.mark.asyncio
    async def test_upload_returns_public_url(
        self, service: ImageStorageService
    ) -> None:
        """정상 업로드 시 올바른 S3 URL 반환."""
        image_data = b"\x89PNG\r\n\x1a\nfake-image-data"
        key = "stories/story-001/scenes/scene-01.png"

        with patch.object(service, "_put_object", new_callable=AsyncMock) as mock_put:
            url = await service.upload(image_data, key)

        mock_put.assert_called_once_with(image_data, key, "image/png")
        expected = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{key}"
        assert url == expected

    @pytest.mark.asyncio
    async def test_upload_jpeg_content_type(self, service: ImageStorageService) -> None:
        """JPEG 키에 대해 올바른 content-type 설정."""
        image_data = b"\xff\xd8\xff\xe0fake-jpeg"
        key = "characters/char-001/front.jpg"

        with patch.object(service, "_put_object", new_callable=AsyncMock) as mock_put:
            url = await service.upload(image_data, key)

        mock_put.assert_called_once_with(image_data, key, "image/jpeg")
        assert "char-001/front.jpg" in url

    @pytest.mark.asyncio
    async def test_upload_empty_buffer_raises(
        self, service: ImageStorageService
    ) -> None:
        """빈 버퍼 업로드 시 에러."""
        with pytest.raises(ImageStorageError, match="빈 이미지"):
            await service.upload(b"", "some/key.png")

    @pytest.mark.asyncio
    async def test_upload_s3_error_raises(self, service: ImageStorageService) -> None:
        """S3 호출 실패 시 ImageStorageError."""
        with (
            patch.object(
                service,
                "_put_object",
                new_callable=AsyncMock,
                side_effect=Exception("S3 down"),
            ),
            pytest.raises(ImageStorageError, match="업로드 실패"),
        ):
            await service.upload(b"data", "key.png")


# ---------------------------------------------------------------------------
# 2. delete — S3 오브젝트 삭제
# ---------------------------------------------------------------------------


class TestDelete:
    """delete(): S3에서 키 삭제."""

    @pytest.mark.asyncio
    async def test_delete_calls_s3(self, service: ImageStorageService) -> None:
        """정상 삭제 호출."""
        key = "stories/story-001/scenes/scene-01.png"

        with patch.object(
            service, "_delete_object", new_callable=AsyncMock
        ) as mock_del:
            await service.delete(key)

        mock_del.assert_called_once_with(key)

    @pytest.mark.asyncio
    async def test_delete_s3_error_raises(self, service: ImageStorageService) -> None:
        """S3 삭제 실패 시 ImageStorageError."""
        with (
            patch.object(
                service,
                "_delete_object",
                new_callable=AsyncMock,
                side_effect=Exception("err"),
            ),
            pytest.raises(ImageStorageError, match="삭제 실패"),
        ):
            await service.delete("key.png")


# ---------------------------------------------------------------------------
# 3. generatePresignedUrl — 서명된 URL 생성
# ---------------------------------------------------------------------------


class TestGeneratePresignedUrl:
    """generate_presigned_url(): S3 presigned URL 반환."""

    @pytest.mark.asyncio
    async def test_presigned_url_returned(self, service: ImageStorageService) -> None:
        """정상적인 presigned URL 반환."""
        expected = (
            "https://storytale-images.s3.amazonaws.com/key.png?X-Amz-Signature=abc"
        )

        with patch.object(
            service,
            "_generate_presigned",
            new_callable=AsyncMock,
            return_value=expected,
        ) as mock_gen:
            url = await service.generate_presigned_url(
                "key.png", expires_in_seconds=3600
            )

        mock_gen.assert_called_once_with("key.png", 3600)
        assert url == expected

    @pytest.mark.asyncio
    async def test_presigned_url_custom_expiry(
        self, service: ImageStorageService
    ) -> None:
        """커스텀 만료 시간 전달."""
        with patch.object(
            service,
            "_generate_presigned",
            new_callable=AsyncMock,
            return_value="url",
        ) as mock_gen:
            await service.generate_presigned_url("k.png", expires_in_seconds=7200)

        mock_gen.assert_called_once_with("k.png", 7200)

    @pytest.mark.asyncio
    async def test_presigned_url_error_raises(
        self, service: ImageStorageService
    ) -> None:
        """presigned URL 생성 실패 시 ImageStorageError."""
        with (
            patch.object(
                service,
                "_generate_presigned",
                new_callable=AsyncMock,
                side_effect=Exception("err"),
            ),
            pytest.raises(ImageStorageError, match="presigned URL 생성 실패"),
        ):
            await service.generate_presigned_url("key.png", expires_in_seconds=600)


# ---------------------------------------------------------------------------
# 4. content-type 추론
# ---------------------------------------------------------------------------


class TestContentTypeDetection:
    """_detect_content_type(): 키 확장자 기반 MIME 타입 추론."""

    def test_png(self, service: ImageStorageService) -> None:
        assert service._detect_content_type("img.png") == "image/png"

    def test_jpg(self, service: ImageStorageService) -> None:
        assert service._detect_content_type("img.jpg") == "image/jpeg"

    def test_jpeg(self, service: ImageStorageService) -> None:
        assert service._detect_content_type("img.jpeg") == "image/jpeg"

    def test_webp(self, service: ImageStorageService) -> None:
        assert service._detect_content_type("img.webp") == "image/webp"

    def test_unknown_defaults_to_octet_stream(
        self, service: ImageStorageService
    ) -> None:
        ct = service._detect_content_type("file.bin")
        assert ct == "application/octet-stream"


# ---------------------------------------------------------------------------
# 5. URL 빌드
# ---------------------------------------------------------------------------


class TestBuildUrl:
    """_build_url(): S3 public URL 조합."""

    def test_url_format(self, service: ImageStorageService) -> None:
        url = service._build_url("stories/s1/scene.png")
        expected = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/stories/s1/scene.png"
        assert url == expected
