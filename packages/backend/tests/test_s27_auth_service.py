"""S27 — 인증 서비스 테스트.

TDD: JWT 토큰 생성/검증, 소셜 로그인, 토큰 갱신, 로그아웃.
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from conftest import TestingSessionLocal
from storytale.auth.schemas import AuthTokens, SocialUserInfo
from storytale.auth.service import AuthService

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret-key-must-be-at-least-32-chars-long!!"


# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def auth_service(db_session) -> AuthService:
    return AuthService(
        db=db_session,
        jwt_secret=TEST_JWT_SECRET,
        access_token_expire_minutes=1440,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def google_user_info() -> SocialUserInfo:
    return SocialUserInfo(email="parent@gmail.com", provider="google")


@pytest.fixture
def kakao_user_info() -> SocialUserInfo:
    return SocialUserInfo(email="parent@kakao.com", provider="kakao")


# ===========================================================================
# JWT 토큰 생성/검증
# ===========================================================================


class TestJWTTokens:
    """JWT 토큰 생성 및 검증."""

    @pytest.mark.asyncio
    async def test_create_access_token_returns_string(self, auth_service):
        user_id = str(uuid.uuid4())
        token = auth_service.create_access_token(user_id=user_id)
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_decode_access_token_contains_user_id(self, auth_service):
        user_id = str(uuid.uuid4())
        token = auth_service.create_access_token(user_id=user_id)
        payload = auth_service.decode_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    @pytest.mark.asyncio
    async def test_expired_token_raises_value_error(self, auth_service):
        user_id = str(uuid.uuid4())
        token = auth_service.create_access_token(
            user_id=user_id,
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(ValueError, match="만료"):
            auth_service.decode_token(token)

    @pytest.mark.asyncio
    async def test_invalid_token_raises_value_error(self, auth_service):
        with pytest.raises(ValueError, match="유효하지"):
            auth_service.decode_token("not-a-real-jwt-token")

    @pytest.mark.asyncio
    async def test_create_refresh_token_has_refresh_type(self, auth_service):
        user_id = str(uuid.uuid4())
        token = auth_service.create_refresh_token(user_id=user_id)
        payload = auth_service.decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == user_id

    @pytest.mark.asyncio
    async def test_access_and_refresh_tokens_differ(self, auth_service):
        user_id = str(uuid.uuid4())
        access = auth_service.create_access_token(user_id=user_id)
        refresh = auth_service.create_refresh_token(user_id=user_id)
        assert access != refresh


# ===========================================================================
# 소셜 로그인
# ===========================================================================


class TestSocialLogin:
    """소셜 로그인 플로우 (프로바이더 호출은 모킹)."""

    @pytest.mark.asyncio
    async def test_google_login_creates_new_user(self, auth_service, google_user_info):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            tokens = await auth_service.social_login(
                provider="google", auth_code="google-auth-code"
            )

        assert isinstance(tokens, AuthTokens)
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.expires_in == 1440 * 60  # 초 단위

    @pytest.mark.asyncio
    async def test_login_existing_user_returns_tokens(
        self, auth_service, google_user_info
    ):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            tokens1 = await auth_service.social_login(
                provider="google", auth_code="code1"
            )
            tokens2 = await auth_service.social_login(
                provider="google", auth_code="code2"
            )

        # 같은 사용자, 다른 토큰
        assert tokens1.access_token != tokens2.access_token

    @pytest.mark.asyncio
    async def test_kakao_login(self, auth_service, kakao_user_info):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=kakao_user_info,
        ):
            tokens = await auth_service.social_login(
                provider="kakao", auth_code="kakao-code"
            )

        assert tokens.access_token
        payload = auth_service.decode_token(tokens.access_token)
        assert payload["sub"]  # user_id가 존재

    @pytest.mark.asyncio
    async def test_login_returns_user_id_in_token(self, auth_service, google_user_info):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            tokens = await auth_service.social_login(
                provider="google", auth_code="code"
            )

        payload = auth_service.decode_token(tokens.access_token)
        assert payload["sub"]  # UUID 문자열
        assert payload["type"] == "access"


# ===========================================================================
# 토큰 갱신
# ===========================================================================


class TestTokenRefresh:
    """리프레시 토큰으로 새 토큰 발급."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, auth_service, google_user_info):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            original = await auth_service.social_login(
                provider="google", auth_code="code"
            )

        new_tokens = await auth_service.refresh_token(original.refresh_token)
        assert new_tokens.access_token
        assert new_tokens.access_token != original.access_token

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, auth_service):
        user_id = str(uuid.uuid4())
        access_token = auth_service.create_access_token(user_id=user_id)
        with pytest.raises(ValueError, match="리프레시"):
            await auth_service.refresh_token(access_token)

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_fails(self, auth_service):
        with pytest.raises(ValueError):
            await auth_service.refresh_token("invalid-token")


# ===========================================================================
# 로그아웃
# ===========================================================================


class TestLogout:
    """로그아웃 시 리프레시 토큰 무효화."""

    @pytest.mark.asyncio
    async def test_logout_invalidates_refresh_token(
        self, auth_service, google_user_info
    ):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            tokens = await auth_service.social_login(
                provider="google", auth_code="code"
            )

        await auth_service.logout(tokens.refresh_token)

        with pytest.raises(ValueError, match="무효화"):
            await auth_service.refresh_token(tokens.refresh_token)

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token_raises(self, auth_service):
        with pytest.raises(ValueError):
            await auth_service.logout("invalid-token")


# ===========================================================================
# 법정대리인 동의
# ===========================================================================


class TestParentalConsent:
    """법정대리인(부모) 동의 기록."""

    @pytest.mark.asyncio
    async def test_record_consent(self, auth_service, google_user_info):
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=google_user_info,
        ):
            tokens = await auth_service.social_login(
                provider="google", auth_code="code"
            )

        payload = auth_service.decode_token(tokens.access_token)
        user_id = payload["sub"]
        await auth_service.record_consent(user_id=user_id)

        user = await auth_service.get_user(user_id=user_id)
        assert user.consent_given_at is not None

    @pytest.mark.asyncio
    async def test_check_consent_status(self, auth_service):
        # 독립된 사용자 사용 (다른 테스트와 DB 상태 공유 방지)
        unique_info = SocialUserInfo(
            email="consent-check@example.com", provider="google"
        )
        with patch.object(
            auth_service,
            "_get_social_user_info",
            new_callable=AsyncMock,
            return_value=unique_info,
        ):
            tokens = await auth_service.social_login(
                provider="google", auth_code="code"
            )

        payload = auth_service.decode_token(tokens.access_token)
        user_id = payload["sub"]

        # 동의 전
        assert not await auth_service.has_consent(user_id=user_id)

        # 동의 후
        await auth_service.record_consent(user_id=user_id)
        assert await auth_service.has_consent(user_id=user_id)
