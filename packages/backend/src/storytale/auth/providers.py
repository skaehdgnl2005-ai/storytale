"""소셜 로그인 프로바이더 클라이언트.

Google, Kakao, Apple OAuth 토큰 교환 및 사용자 정보 조회.
보안: 사용자 입력(auth_code/id_token)은 외부 API로만 전달.
"""

import os

import httpx
import jwt

from storytale.auth.schemas import SocialUserInfo

# ---------------------------------------------------------------------------
# 에러
# ---------------------------------------------------------------------------


class SocialAuthError(Exception):
    """소셜 인증 실패."""


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleProvider:
    """Google ID 토큰 검증.

    모바일 앱이 Google Sign-In으로 받은 ID 토큰을 검증하고
    사용자 이메일을 추출.
    """

    def __init__(self, client_id: str | None = None) -> None:
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID", "")

    async def get_user_info(self, auth_code: str) -> SocialUserInfo:
        """ID 토큰을 Google에 검증 요청 → 사용자 정보 반환."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    GOOGLE_TOKENINFO_URL,
                    params={"id_token": auth_code},
                )
                if resp.status_code != 200:
                    raise SocialAuthError(f"Google 토큰 검증 실패: {resp.status_code}")

                data = resp.json()
        except SocialAuthError:
            raise
        except Exception as e:
            raise SocialAuthError(f"Google 인증 오류: {e}") from e

        if not data.get("email_verified", False):
            raise SocialAuthError("이메일 미인증 계정입니다")

        if data.get("aud") != self.client_id:
            raise SocialAuthError(
                f"audience 불일치: 기대값={self.client_id}, 실제={data.get('aud')}"
            )

        return SocialUserInfo(
            email=data["email"],
            provider="google",
        )


# ---------------------------------------------------------------------------
# Kakao
# ---------------------------------------------------------------------------

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoProvider:
    """Kakao auth_code → 액세스 토큰 교환 → 사용자 정보 조회."""

    def __init__(
        self,
        client_id: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        self.client_id = client_id or os.getenv("KAKAO_CLIENT_ID", "")
        self.redirect_uri = redirect_uri or os.getenv("KAKAO_REDIRECT_URI", "")

    async def get_user_info(self, auth_code: str) -> SocialUserInfo:
        """auth_code → 토큰 교환 → 사용자 정보."""
        access_token = await self._exchange_token(auth_code)
        return await self._fetch_user_info(access_token)

    async def _exchange_token(self, auth_code: str) -> str:
        """auth_code를 Kakao 액세스 토큰으로 교환."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    KAKAO_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.client_id,
                        "redirect_uri": self.redirect_uri,
                        "code": auth_code,
                    },
                )
                if resp.status_code != 200:
                    raise SocialAuthError(f"Kakao 토큰 교환 실패: {resp.status_code}")
                return resp.json()["access_token"]
        except SocialAuthError:
            raise
        except Exception as e:
            raise SocialAuthError(f"Kakao 토큰 교환 오류: {e}") from e

    async def _fetch_user_info(self, access_token: str) -> SocialUserInfo:
        """Kakao 액세스 토큰으로 사용자 정보 조회."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    KAKAO_USER_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code != 200:
                    raise SocialAuthError(
                        f"Kakao 사용자 정보 조회 실패: {resp.status_code}"
                    )

                data = resp.json()
        except SocialAuthError:
            raise
        except Exception as e:
            raise SocialAuthError(f"Kakao 사용자 정보 오류: {e}") from e

        account = data.get("kakao_account", {})
        email = account.get("email")
        if not email:
            raise SocialAuthError("Kakao 계정에 이메일이 없습니다")

        return SocialUserInfo(email=email, provider="kakao")


# ---------------------------------------------------------------------------
# Apple
# ---------------------------------------------------------------------------

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


class AppleProvider:
    """Apple ID 토큰 검증.

    모바일 앱이 Sign in with Apple로 받은 ID 토큰을 검증.
    Apple 공개키로 JWT 서명을 확인.
    """

    def __init__(self, client_id: str | None = None) -> None:
        self.client_id = client_id or os.getenv("APPLE_CLIENT_ID", "")

    async def get_user_info(self, auth_code: str) -> SocialUserInfo:
        """ID 토큰 검증 → 사용자 정보."""
        try:
            payload = await self._verify_apple_token(auth_code)
        except SocialAuthError:
            raise
        except Exception as e:
            raise SocialAuthError(f"Apple 인증 오류: {e}") from e

        if payload.get("aud") != self.client_id:
            raise SocialAuthError(
                f"audience 불일치: 기대값={self.client_id}, 실제={payload.get('aud')}"
            )

        email = payload.get("email")
        if not email:
            raise SocialAuthError("Apple 계정에 이메일이 없습니다")

        return SocialUserInfo(email=email, provider="apple")

    async def _verify_apple_token(self, id_token: str) -> dict:
        """Apple 공개키로 ID 토큰 검증."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(APPLE_KEYS_URL)
                if resp.status_code != 200:
                    raise SocialAuthError("Apple 공개키 조회 실패")
                apple_keys = resp.json()

            # JWT 헤더에서 kid 추출
            header = jwt.get_unverified_header(id_token)
            kid = header.get("kid")

            # 매칭되는 공개키 찾기
            matching_key = None
            for key in apple_keys.get("keys", []):
                if key["kid"] == kid:
                    matching_key = key
                    break

            if matching_key is None:
                raise SocialAuthError("매칭되는 Apple 공개키가 없습니다")

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)

            return jwt.decode(
                id_token,
                public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer="https://appleid.apple.com",
            )
        except jwt.InvalidTokenError as e:
            raise SocialAuthError(f"Apple 토큰 검증 실패: {e}") from e


# ---------------------------------------------------------------------------
# 팩토리
# ---------------------------------------------------------------------------


def get_provider(
    provider_name: str,
) -> GoogleProvider | KakaoProvider | AppleProvider:
    """프로바이더 이름으로 클라이언트 인스턴스 반환."""
    providers = {
        "google": GoogleProvider,
        "kakao": KakaoProvider,
        "apple": AppleProvider,
    }
    cls = providers.get(provider_name)
    if cls is None:
        raise SocialAuthError(f"지원하지 않는 프로바이더: {provider_name}")
    return cls()
