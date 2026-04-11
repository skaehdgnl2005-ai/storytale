"""S27b — 이메일+비밀번호 인증 API 테스트.

POST /auth/register/email, POST /auth/login/email.
기존 /auth/me 가 이메일 유저에게도 동작하는지 회귀.

설계 문서: docs/superpowers/specs/2026-04-11-s27b-session1-email-auth-backend-design.md
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from conftest import TestingSessionLocal
from storytale.app import app
from storytale.db.models import User

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

BASE_URL = "http://test/api/v1"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


def _unique_email(prefix: str = "s27b") -> str:
    """각 테스트마다 유니크한 이메일 반환 (DB 오염 격리)."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


# ===========================================================================
# POST /auth/register/email
# ===========================================================================


class TestRegisterEmail:
    """회원가입 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_register_returns_tokens(self, client):
        email = _unique_email()
        resp = await client.post(
            "/auth/register/email",
            json={"email": email, "password": "testpass123"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_register_creates_user_with_email_provider(self, client):
        email = _unique_email()
        resp = await client.post(
            "/auth/register/email",
            json={"email": email, "password": "testpass123"},
        )
        assert resp.status_code == 200

        # DB 직접 확인
        async with TestingSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.provider == "email"
            assert user.password_hash is not None
            assert user.password_hash.startswith("$2b$")  # bcrypt format
            # 원본 비번은 저장되지 않음
            assert "testpass123" not in user.password_hash

    @pytest.mark.asyncio
    async def test_register_normalizes_email_case(self, client):
        original = _unique_email("case")
        # 대문자로 입력 → DB 에는 소문자로 저장되어야 함
        resp = await client.post(
            "/auth/register/email",
            json={"email": original.upper(), "password": "testpass123"},
        )
        assert resp.status_code == 200

        async with TestingSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.email == original.lower())
            )
            user = result.scalar_one_or_none()
            assert user is not None, "이메일이 소문자로 정규화되어 저장되지 않음"

    @pytest.mark.asyncio
    async def test_register_strips_whitespace(self, client):
        email = _unique_email()
        resp = await client.post(
            "/auth/register/email",
            json={"email": f"  {email}  ", "password": "testpass123"},
        )
        assert resp.status_code == 200

        async with TestingSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            assert user is not None, "앞뒤 공백이 strip 되지 않음"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client):
        email = _unique_email()
        # 첫 가입
        resp1 = await client.post(
            "/auth/register/email",
            json={"email": email, "password": "testpass123"},
        )
        assert resp1.status_code == 200

        # 두 번째 가입 → 409 + inner code
        resp2 = await client.post(
            "/auth/register/email",
            json={"email": email, "password": "otherpass456"},
        )
        assert resp2.status_code == 409, resp2.text
        body = resp2.json()
        # 에러 envelope: {error: {code: 409, message: {message: ..., code: ...}}}
        assert "error" in body
        assert body["error"]["code"] == 409
        inner = body["error"]["message"]
        assert isinstance(inner, dict), f"expected inner dict, got {type(inner)}"
        assert inner["code"] == "EMAIL_ALREADY_EXISTS"
        assert "이미 가입된 이메일" in inner["message"]

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client):
        resp = await client.post(
            "/auth/register/email",
            json={"email": "not-an-email", "password": "testpass123"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(self, client):
        resp = await client.post(
            "/auth/register/email",
            json={"email": _unique_email(), "password": "short"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_overlong_password_returns_422(self, client):
        # 한글 25자 = UTF-8 75바이트 (3바이트 * 25). bcrypt 72바이트 한도 초과
        long_password = "가" * 25
        assert len(long_password.encode("utf-8")) == 75
        resp = await client.post(
            "/auth/register/email",
            json={"email": _unique_email(), "password": long_password},
        )
        assert resp.status_code == 422


# ===========================================================================
# POST /auth/login/email
# ===========================================================================


class TestLoginEmail:
    """로그인 엔드포인트 테스트."""

    @pytest_asyncio.fixture
    async def registered_user(self, client):
        """사전 가입된 유저 픽스처."""
        email = _unique_email("login")
        password = "correctpass123"
        resp = await client.post(
            "/auth/register/email",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200
        return {"email": email, "password": password, "tokens": resp.json()}

    @pytest.mark.asyncio
    async def test_login_with_correct_password_returns_tokens(
        self, client, registered_user
    ):
        resp = await client.post(
            "/auth/login/email",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_returns_401(self, client, registered_user):
        resp = await client.post(
            "/auth/login/email",
            json={
                "email": registered_user["email"],
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_unknown_email_returns_401(self, client):
        resp = await client.post(
            "/auth/login/email",
            json={
                "email": _unique_email("unknown"),
                "password": "anypassword",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_social_only_user_returns_401(self, client):
        # DB 에 직접 소셜 전용 유저 삽입 (password_hash=None)
        social_email = _unique_email("social")
        async with TestingSessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=social_email,
                provider="google",
                password_hash=None,
            )
            session.add(user)
            await session.commit()

        resp = await client.post(
            "/auth/login/email",
            json={"email": social_email, "password": "anypassword"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_overlong_password_returns_401(
        self, client, registered_user
    ):
        # 긴 비번은 bcrypt 가 자동 truncate 후 비교 → 틀린 해시 → 401
        long_password = "가" * 30
        resp = await client.post(
            "/auth/login/email",
            json={
                "email": registered_user["email"],
                "password": long_password,
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_normalizes_email_case(self, client, registered_user):
        # 대문자로 입력해도 정상 로그인
        resp = await client.post(
            "/auth/login/email",
            json={
                "email": registered_user["email"].upper(),
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200


# ===========================================================================
# 기존 /auth/me 회귀
# ===========================================================================


class TestMeEndpointWithEmailUser:
    """이메일 유저가 기존 /auth/me 엔드포인트로 자기 정보 조회."""

    @pytest.mark.asyncio
    async def test_me_returns_email_user_info(self, client):
        email = _unique_email("me")
        reg_resp = await client.post(
            "/auth/register/email",
            json={"email": email, "password": "testpass123"},
        )
        assert reg_resp.status_code == 200
        access_token = reg_resp.json()["access_token"]

        me_resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == email
        assert data["provider"] == "email"
        assert data["consent_given"] is False
        assert "user_id" in data
