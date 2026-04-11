"""S28 — 아이 프로필 CRUD API + 사진 업로드 테스트.

계약: docs/contracts/user-service.ts (ChildProfileService)
엔드포인트: POST /profiles, GET /profiles, GET /profiles/{id},
           PUT /profiles/{id}, DELETE /profiles/{id},
           POST /profiles/{id}/photo
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image

from storytale.app import app
from storytale.auth.schemas import SocialUserInfo

BASE_URL = "http://test/api/v1"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_header(client):
    """로그인된 사용자의 Authorization 헤더."""
    user_info = SocialUserInfo(
        email=f"profile-test-{uuid.uuid4().hex[:8]}@example.com",
        provider="google",
    )
    with patch(
        "storytale.api.auth_router.AuthService._get_social_user_info",
        new_callable=AsyncMock,
        return_value=user_info,
    ):
        resp = await client.post(
            "/auth/login",
            json={"provider": "google", "auth_code": "test-code"},
        )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def other_auth_header(client):
    """다른 사용자의 Authorization 헤더 (소유자 검증 테스트용)."""
    user_info = SocialUserInfo(
        email=f"other-{uuid.uuid4().hex[:8]}@example.com",
        provider="google",
    )
    with patch(
        "storytale.api.auth_router.AuthService._get_social_user_info",
        new_callable=AsyncMock,
        return_value=user_info,
    ):
        resp = await client.post(
            "/auth/login",
            json={"provider": "google", "auth_code": "test-code"},
        )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


VALID_PROFILE = {
    "name": "서준이",
    "age": 4,
    "gender": "male",
    "comfort_object": "토니 곰인형",
    "friend_name": "민준이",
    "favorite_animal": "토끼",
}


# ===========================================================================
# POST /profiles — 프로필 생성
# ===========================================================================


class TestCreateProfile:
    """POST /profiles 테스트."""

    @pytest.mark.asyncio
    async def test_create_profile_success(self, client, auth_header):
        resp = await client.post("/profiles", json=VALID_PROFILE, headers=auth_header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "서준이"
        assert data["age"] == 4
        assert data["gender"] == "male"
        assert data["comfort_object"] == "토니 곰인형"
        assert data["friend_name"] == "민준이"
        assert data["favorite_animal"] == "토끼"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_profile_minimal(self, client, auth_header):
        """필수 필드만으로 생성."""
        resp = await client.post(
            "/profiles",
            json={"name": "하은이", "age": 3, "gender": "female"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "하은이"
        assert data["comfort_object"] is None

    @pytest.mark.asyncio
    async def test_create_profile_without_auth(self, client):
        resp = await client.post("/profiles", json=VALID_PROFILE)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_profile_invalid_gender(self, client, auth_header):
        resp = await client.post(
            "/profiles",
            json={"name": "서준이", "age": 4, "gender": "unknown"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_profile_age_too_low(self, client, auth_header):
        resp = await client.post(
            "/profiles",
            json={"name": "서준이", "age": 0, "gender": "male"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_profile_age_too_high(self, client, auth_header):
        resp = await client.post(
            "/profiles",
            json={"name": "서준이", "age": 14, "gender": "male"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_profile_name_too_long(self, client, auth_header):
        resp = await client.post(
            "/profiles",
            json={"name": "가" * 51, "age": 4, "gender": "male"},
            headers=auth_header,
        )
        assert resp.status_code == 422


# ===========================================================================
# GET /profiles — 프로필 목록
# ===========================================================================


class TestListProfiles:
    """GET /profiles 테스트."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client, auth_header):
        resp = await client.get("/profiles", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_after_create(self, client, auth_header):
        await client.post(
            "/profiles",
            json={"name": "아이1", "age": 3, "gender": "female"},
            headers=auth_header,
        )
        await client.post(
            "/profiles",
            json={"name": "아이2", "age": 5, "gender": "male"},
            headers=auth_header,
        )
        resp = await client.get("/profiles", headers=auth_header)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_list_only_own_profiles(self, client, auth_header, other_auth_header):
        """다른 사용자의 프로필은 보이지 않아야 한다."""
        await client.post(
            "/profiles",
            json={"name": "내아이", "age": 4, "gender": "male"},
            headers=auth_header,
        )
        await client.post(
            "/profiles",
            json={"name": "남의아이", "age": 5, "gender": "female"},
            headers=other_auth_header,
        )
        resp = await client.get("/profiles", headers=auth_header)
        names = [p["name"] for p in resp.json()]
        assert "내아이" in names
        assert "남의아이" not in names

    @pytest.mark.asyncio
    async def test_list_without_auth(self, client):
        resp = await client.get("/profiles")
        assert resp.status_code == 401


# ===========================================================================
# GET /profiles/{id} — 프로필 조회
# ===========================================================================


class TestGetProfile:
    """GET /profiles/{id} 테스트."""

    @pytest.mark.asyncio
    async def test_get_profile(self, client, auth_header):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.get(f"/profiles/{child_id}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["name"] == "서준이"

    @pytest.mark.asyncio
    async def test_get_nonexistent_profile(self, client, auth_header):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/profiles/{fake_id}", headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_profile(
        self, client, auth_header, other_auth_header
    ):
        """다른 사용자의 프로필에 접근하면 404."""
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.get(f"/profiles/{child_id}", headers=other_auth_header)
        assert resp.status_code == 404


# ===========================================================================
# PUT /profiles/{id} — 프로필 수정
# ===========================================================================


class TestUpdateProfile:
    """PUT /profiles/{id} 테스트."""

    @pytest.mark.asyncio
    async def test_update_profile(self, client, auth_header):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.put(
            f"/profiles/{child_id}",
            json={"name": "서준", "comfort_object": "새 곰인형"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "서준"
        assert data["comfort_object"] == "새 곰인형"
        # 변경하지 않은 필드는 유지
        assert data["age"] == 4
        assert data["favorite_animal"] == "토끼"

    @pytest.mark.asyncio
    async def test_update_gender_rejected(self, client, auth_header):
        """gender는 캐릭터 시트와 연동되므로 변경 불가 (계약 명시)."""
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.put(
            f"/profiles/{child_id}",
            json={"gender": "female"},
            headers=auth_header,
        )
        # gender 필드가 스키마에 없으므로 무시됨 — 원래 값 유지
        assert resp.status_code == 200
        assert resp.json()["gender"] == "male"

    @pytest.mark.asyncio
    async def test_update_nonexistent_profile(self, client, auth_header):
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/profiles/{fake_id}",
            json={"name": "새이름"},
            headers=auth_header,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_profile(
        self, client, auth_header, other_auth_header
    ):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.put(
            f"/profiles/{child_id}",
            json={"name": "해킹"},
            headers=other_auth_header,
        )
        assert resp.status_code == 404


# ===========================================================================
# DELETE /profiles/{id} — 프로필 삭제
# ===========================================================================


class TestDeleteProfile:
    """DELETE /profiles/{id} 테스트."""

    @pytest.mark.asyncio
    async def test_delete_profile(self, client, auth_header):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.delete(f"/profiles/{child_id}", headers=auth_header)
        assert resp.status_code == 204

        # 삭제 후 조회 시 404
        get_resp = await client.get(f"/profiles/{child_id}", headers=auth_header)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, client, auth_header):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(f"/profiles/{fake_id}", headers=auth_header)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_profile(
        self, client, auth_header, other_auth_header
    ):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.delete(f"/profiles/{child_id}", headers=other_auth_header)
        assert resp.status_code == 404


# ===========================================================================
# POST /profiles/{id}/photo — 사진 업로드
# ===========================================================================


def _make_jpeg(width: int = 100, height: int = 100) -> bytes:
    """테스트용 JPEG 이미지 생성."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png(width: int = 100, height: int = 100) -> bytes:
    """테스트용 PNG 이미지 생성."""
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_with_exif() -> bytes:
    """EXIF 메타데이터가 포함된 JPEG 생성 (Pillow 내장 방식)."""
    import struct

    img = Image.new("RGB", (100, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg_data = buf.getvalue()
    # 최소 EXIF APP1 마커 삽입 (Exif\x00\x00 + TIFF 헤더)
    tiff_header = b"MM" + struct.pack(">H", 42) + struct.pack(">I", 8)
    # IFD with 1 entry: Make = "TestCamera"
    value = b"TestCamera\x00"
    ifd = struct.pack(">H", 1)  # 1 entry
    ifd += struct.pack(">HHI", 0x010F, 2, len(value))  # Make tag, ASCII
    ifd += struct.pack(">I", 8 + 2 + 12 + 4)  # offset to value
    ifd += struct.pack(">I", 0)  # next IFD
    exif_body = b"Exif\x00\x00" + tiff_header + ifd + value
    app1 = b"\xff\xe1" + struct.pack(">H", len(exif_body) + 2) + exif_body
    # SOI 뒤에 삽입
    result = jpeg_data[:2] + app1 + jpeg_data[2:]
    return result


class TestPhotoUpload:
    """POST /profiles/{id}/photo 테스트."""

    @pytest.mark.asyncio
    async def test_upload_jpeg(self, client, auth_header):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        photo = _make_jpeg()
        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("child.jpg", photo, "image/jpeg")},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["photo_hash"] is not None
        assert len(data["photo_hash"]) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_upload_png(self, client, auth_header):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        photo = _make_png()
        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("child.png", photo, "image/png")},
            headers=auth_header,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_strips_exif(self, client, auth_header):
        """EXIF 메타데이터가 제거되는지 확인."""
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        photo = _make_jpeg_with_exif()
        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("child.jpg", photo, "image/jpeg")},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["exif_stripped"] is True

    @pytest.mark.asyncio
    async def test_upload_invalid_format(self, client, auth_header):
        """JPEG/PNG 외 형식은 거부."""
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("child.gif", b"GIF89a...", "image/gif")},
            headers=auth_header,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_too_large(self, client, auth_header):
        """5MB 초과 파일은 거부."""
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        big_photo = b"\x00" * (5 * 1024 * 1024 + 1)
        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("big.jpg", big_photo, "image/jpeg")},
            headers=auth_header,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_without_auth(self, client):
        fake_id = str(uuid.uuid4())
        photo = _make_jpeg()
        resp = await client.post(
            f"/profiles/{fake_id}/photo",
            files={"photo": ("child.jpg", photo, "image/jpeg")},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_other_users_profile(
        self, client, auth_header, other_auth_header
    ):
        create_resp = await client.post(
            "/profiles", json=VALID_PROFILE, headers=auth_header
        )
        child_id = create_resp.json()["id"]

        photo = _make_jpeg()
        resp = await client.post(
            f"/profiles/{child_id}/photo",
            files={"photo": ("child.jpg", photo, "image/jpeg")},
            headers=other_auth_header,
        )
        assert resp.status_code == 404
