"""S27 — 소셜 프로바이더 클라이언트 테스트.

Google/Kakao/Apple OAuth 토큰 교환 및 사용자 정보 조회.
외부 API 호출은 모두 모킹.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from storytale.auth.providers import (
    AppleProvider,
    GoogleProvider,
    KakaoProvider,
    SocialAuthError,
)
from storytale.auth.schemas import SocialUserInfo


def _make_response(status_code: int, json_data: dict) -> MagicMock:
    """httpx.Response 모킹 (json()은 동기 메서드)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


# ===========================================================================
# Google
# ===========================================================================


class TestGoogleProvider:
    """Google ID 토큰 검증 → 사용자 정보."""

    @pytest.mark.asyncio
    async def test_valid_id_token_returns_user_info(self):
        provider = GoogleProvider(client_id="test-client-id")
        mock_resp = _make_response(
            200,
            {
                "email": "user@gmail.com",
                "email_verified": True,
                "aud": "test-client-id",
            },
        )

        with patch(
            "storytale.auth.providers.httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=mock_resp,
        ):
            info = await provider.get_user_info(auth_code="google-id-token")

        assert isinstance(info, SocialUserInfo)
        assert info.email == "user@gmail.com"
        assert info.provider == "google"

    @pytest.mark.asyncio
    async def test_unverified_email_raises(self):
        provider = GoogleProvider(client_id="test-client-id")
        mock_resp = _make_response(
            200,
            {
                "email": "user@gmail.com",
                "email_verified": False,
                "aud": "test-client-id",
            },
        )

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(SocialAuthError, match="이메일 미인증"),
        ):
            await provider.get_user_info(auth_code="google-id-token")

    @pytest.mark.asyncio
    async def test_wrong_audience_raises(self):
        provider = GoogleProvider(client_id="test-client-id")
        mock_resp = _make_response(
            200,
            {
                "email": "user@gmail.com",
                "email_verified": True,
                "aud": "wrong-client-id",
            },
        )

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(SocialAuthError, match="audience"),
        ):
            await provider.get_user_info(auth_code="google-id-token")

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        provider = GoogleProvider(client_id="test-client-id")
        mock_resp = _make_response(400, {})

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(SocialAuthError),
        ):
            await provider.get_user_info(auth_code="invalid-token")


# ===========================================================================
# Kakao
# ===========================================================================


class TestKakaoProvider:
    """Kakao auth_code → 액세스 토큰 → 사용자 정보."""

    @pytest.mark.asyncio
    async def test_valid_auth_code_returns_user_info(self):
        provider = KakaoProvider(
            client_id="kakao-app-key",
            redirect_uri="https://app.storytale.kr/auth/kakao/callback",
        )

        token_resp = _make_response(
            200, {"access_token": "kakao-access-token", "token_type": "bearer"}
        )
        user_resp = _make_response(
            200,
            {
                "kakao_account": {
                    "email": "user@kakao.com",
                    "is_email_verified": True,
                }
            },
        )

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.post",
                new_callable=AsyncMock,
                return_value=token_resp,
            ),
            patch(
                "storytale.auth.providers.httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=user_resp,
            ),
        ):
            info = await provider.get_user_info(auth_code="kakao-auth-code")

        assert info.email == "user@kakao.com"
        assert info.provider == "kakao"

    @pytest.mark.asyncio
    async def test_token_exchange_failure_raises(self):
        provider = KakaoProvider(
            client_id="kakao-app-key",
            redirect_uri="https://app.storytale.kr/auth/kakao/callback",
        )

        mock_resp = _make_response(400, {"error": "invalid_grant"})

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.post",
                new_callable=AsyncMock,
                return_value=mock_resp,
            ),
            pytest.raises(SocialAuthError, match="토큰 교환"),
        ):
            await provider.get_user_info(auth_code="bad-code")

    @pytest.mark.asyncio
    async def test_no_email_raises(self):
        provider = KakaoProvider(
            client_id="kakao-app-key",
            redirect_uri="https://app.storytale.kr/auth/kakao/callback",
        )

        token_resp = _make_response(200, {"access_token": "kakao-access-token"})
        user_resp = _make_response(200, {"kakao_account": {}})

        with (
            patch(
                "storytale.auth.providers.httpx.AsyncClient.post",
                new_callable=AsyncMock,
                return_value=token_resp,
            ),
            patch(
                "storytale.auth.providers.httpx.AsyncClient.get",
                new_callable=AsyncMock,
                return_value=user_resp,
            ),
            pytest.raises(SocialAuthError, match="이메일"),
        ):
            await provider.get_user_info(auth_code="code")


# ===========================================================================
# Apple
# ===========================================================================


class TestAppleProvider:
    """Apple ID 토큰 검증 → 사용자 정보."""

    @pytest.mark.asyncio
    async def test_valid_id_token_returns_user_info(self):
        provider = AppleProvider(client_id="com.storytale.app")

        decoded_payload = {
            "email": "user@icloud.com",
            "email_verified": True,
            "aud": "com.storytale.app",
            "iss": "https://appleid.apple.com",
        }

        with patch.object(
            provider,
            "_verify_apple_token",
            new_callable=AsyncMock,
            return_value=decoded_payload,
        ):
            info = await provider.get_user_info(auth_code="apple-id-token")

        assert info.email == "user@icloud.com"
        assert info.provider == "apple"

    @pytest.mark.asyncio
    async def test_wrong_audience_raises(self):
        provider = AppleProvider(client_id="com.storytale.app")

        decoded_payload = {
            "email": "user@icloud.com",
            "email_verified": True,
            "aud": "com.other.app",
            "iss": "https://appleid.apple.com",
        }

        with (
            patch.object(
                provider,
                "_verify_apple_token",
                new_callable=AsyncMock,
                return_value=decoded_payload,
            ),
            pytest.raises(SocialAuthError, match="audience"),
        ):
            await provider.get_user_info(auth_code="apple-token")

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        provider = AppleProvider(client_id="com.storytale.app")

        with (
            patch.object(
                provider,
                "_verify_apple_token",
                new_callable=AsyncMock,
                side_effect=Exception("Invalid token"),
            ),
            pytest.raises(SocialAuthError),
        ):
            await provider.get_user_info(auth_code="bad-token")
