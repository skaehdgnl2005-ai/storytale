"""S27 — 인증 API 엔드포인트 테스트.

POST /auth/login, POST /auth/refresh, POST /auth/logout, POST /auth/consent.
get_current_user 의존성 검증.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from conftest import TestingSessionLocal
from storytale.app import app
from storytale.auth.schemas import SocialUserInfo
from storytale.auth.service import AuthService

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

BASE_URL = "http://test/api/v1"
TEST_JWT_SECRET = "test-secret-key-must-be-at-least-32-chars-long!!"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def auth_service(db_session) -> AuthService:
    return AuthService(
        db=db_session,
        jwt_secret=TEST_JWT_SECRET,
    )


@pytest_asyncio.fixture
async def logged_in_tokens(client):
    """로그인된 사용자의 토큰."""
    user_info = SocialUserInfo(
        email=f"api-test-{uuid.uuid4().hex[:8]}@example.com",
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
    return resp.json()


# ===========================================================================
# 로그인 API
# ===========================================================================


class TestLoginEndpoint:
    """POST /auth/login 테스트."""

    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, client):
        user_info = SocialUserInfo(email="login-test@example.com", provider="google")
        with patch(
            "storytale.api.auth_router.AuthService._get_social_user_info",
            new_callable=AsyncMock,
            return_value=user_info,
        ):
            resp = await client.post(
                "/auth/login",
                json={"provider": "google", "auth_code": "auth-code-123"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_invalid_provider(self, client):
        resp = await client.post(
            "/auth/login",
            json={"provider": "facebook", "auth_code": "code"},
        )
        assert resp.status_code == 422  # Pydantic 검증 실패

    @pytest.mark.asyncio
    async def test_login_missing_auth_code(self, client):
        resp = await client.post(
            "/auth/login",
            json={"provider": "google"},
        )
        assert resp.status_code == 422


# ===========================================================================
# 토큰 갱신 API
# ===========================================================================


class TestRefreshEndpoint:
    """POST /auth/refresh 테스트."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, client, logged_in_tokens):
        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": logged_in_tokens["refresh_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] != logged_in_tokens["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token(self, client):
        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert resp.status_code == 401


# ===========================================================================
# 로그아웃 API
# ===========================================================================


class TestLogoutEndpoint:
    """POST /auth/logout 테스트."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client, logged_in_tokens):
        resp = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {logged_in_tokens['access_token']}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_logout_without_token(self, client):
        resp = await client.post("/auth/logout")
        assert resp.status_code == 401


# ===========================================================================
# 동의 API
# ===========================================================================


class TestConsentEndpoint:
    """POST /auth/consent 테스트."""

    @pytest.mark.asyncio
    async def test_record_consent(self, client, logged_in_tokens):
        resp = await client.post(
            "/auth/consent",
            headers={"Authorization": f"Bearer {logged_in_tokens['access_token']}"},
            json={"agreed": True},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_consent_without_auth(self, client):
        resp = await client.post(
            "/auth/consent",
            json={"agreed": True},
        )
        assert resp.status_code == 401


# ===========================================================================
# get_current_user 의존성
# ===========================================================================


class TestGetCurrentUser:
    """보호된 엔드포인트 접근 시 get_current_user 동작 검증."""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self, client, logged_in_tokens):
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {logged_in_tokens['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "email" in data

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401
