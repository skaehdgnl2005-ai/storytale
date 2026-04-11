"""S3 이미지 관리 서비스.

ImageStorageService: S3 업로드, public URL 반환, presigned URL 생성, 삭제.
boto3를 asyncio.to_thread로 감싸 비동기 인터페이스 제공.
"""

import asyncio
import logging
import os

import boto3

logger = logging.getLogger(__name__)

_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class ImageStorageError(Exception):
    """이미지 저장 서비스 에러."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ImageStorageService:
    """S3 이미지 저장 서비스.

    Args:
        bucket: S3 버킷 이름. None이면 AWS_S3_BUCKET 환경변수 참조.
        region: AWS 리전. None이면 AWS_REGION 환경변수 참조.
    """

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        self._bucket = bucket or os.getenv("AWS_S3_BUCKET", "")
        self._region = region or os.getenv("AWS_REGION", "ap-northeast-2")
        self._client = boto3.client("s3", region_name=self._region)

    async def upload(self, image_buffer: bytes, key: str) -> str:
        """이미지를 S3에 업로드하고 public URL 반환.

        Args:
            image_buffer: 이미지 바이너리 데이터.
            key: S3 키. 예: "stories/{storyId}/scenes/{sceneId}.png"

        Returns:
            S3 public URL.

        Raises:
            ImageStorageError: 빈 버퍼이거나 S3 업로드 실패.
        """
        if not image_buffer:
            raise ImageStorageError(
                code="EMPTY_BUFFER",
                message="빈 이미지 데이터는 업로드할 수 없습니다",
            )

        content_type = self._detect_content_type(key)

        try:
            await self._put_object(image_buffer, key, content_type)
        except ImageStorageError:
            raise
        except Exception as exc:
            raise ImageStorageError(
                code="UPLOAD_FAILED",
                message=f"업로드 실패: {exc}",
            ) from exc

        url = self._build_url(key)
        logger.info("image_upload key=%s size=%d url=%s", key, len(image_buffer), url)
        return url

    async def delete(self, key: str) -> None:
        """S3에서 이미지 삭제.

        Args:
            key: 삭제할 S3 키.

        Raises:
            ImageStorageError: S3 삭제 실패.
        """
        try:
            await self._delete_object(key)
        except ImageStorageError:
            raise
        except Exception as exc:
            raise ImageStorageError(
                code="DELETE_FAILED",
                message=f"삭제 실패: {exc}",
            ) from exc

        logger.info("image_delete key=%s", key)

    async def generate_presigned_url(
        self, key: str, *, expires_in_seconds: int = 3600
    ) -> str:
        """S3 presigned URL 생성.

        Args:
            key: S3 키.
            expires_in_seconds: URL 만료 시간(초). 기본 3600초(1시간).

        Returns:
            presigned URL.

        Raises:
            ImageStorageError: URL 생성 실패.
        """
        try:
            return await self._generate_presigned(key, expires_in_seconds)
        except ImageStorageError:
            raise
        except Exception as exc:
            raise ImageStorageError(
                code="PRESIGNED_FAILED",
                message=f"presigned URL 생성 실패: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # 내부 메서드 (boto3 동기 호출을 to_thread로 래핑)
    # ------------------------------------------------------------------

    async def _put_object(self, data: bytes, key: str, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def _delete_object(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=key,
        )

    async def _generate_presigned(self, key: str, expires_in: int) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def _detect_content_type(self, key: str) -> str:
        """키 확장자에서 MIME 타입 추론."""
        dot_idx = key.rfind(".")
        if dot_idx == -1:
            return "application/octet-stream"
        ext = key[dot_idx:].lower()
        return _EXTENSION_TO_CONTENT_TYPE.get(ext, "application/octet-stream")

    def _build_url(self, key: str) -> str:
        """S3 public URL 조합."""
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
