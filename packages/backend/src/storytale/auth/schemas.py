"""인증 관련 Pydantic 스키마."""

from typing import Literal

from pydantic import BaseModel


class SocialLoginRequest(BaseModel):
    """소셜 로그인 요청."""

    provider: Literal["google", "kakao", "apple"]
    auth_code: str


class TokenRefreshRequest(BaseModel):
    """토큰 갱신 요청."""

    refresh_token: str


class AuthTokens(BaseModel):
    """인증 토큰 응답."""

    access_token: str
    refresh_token: str
    expires_in: int  # 초 단위


class SocialUserInfo(BaseModel):
    """소셜 프로바이더에서 받은 사용자 정보."""

    email: str
    provider: str


class ConsentRequest(BaseModel):
    """법정대리인 동의 요청."""

    agreed: bool
