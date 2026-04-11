"""인증 관련 Pydantic 스키마."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------------------------------------------------------------------------
# S27b 상수
# ---------------------------------------------------------------------------

MIN_PASSWORD_LENGTH = 8  # 문자 단위 (Python len)
MAX_PASSWORD_BYTES = 72  # bcrypt null-terminated 입력 제한


# ---------------------------------------------------------------------------
# 기존 소셜 로그인 스키마 (S27)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# S27b 이메일+비밀번호 스키마
# ---------------------------------------------------------------------------


class EmailRegisterRequest(BaseModel):
    """이메일+비밀번호 회원가입 요청.

    - `email`: EmailStr 로 RFC 5322 검증 + 도메인 자동 정규화.
      pre-validator 로 strip() 하여 모바일 복붙 UX 대응.
    - `password`: 최소 8자 (문자 단위) + 최대 72바이트 (UTF-8, bcrypt 한도).
    """

    email: EmailStr
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def _strip_email(cls, v: str) -> str:
        # mode="before" 가 핵심 — EmailStr 타입 검증이 실행되기 전에 strip 수행.
        return v.strip() if isinstance(v, str) else v

    @field_validator("password")
    @classmethod
    def _password_bytes_within_bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 encoded"
            )
        return v


class EmailLoginRequest(BaseModel):
    """이메일+비밀번호 로그인 요청.

    `password` 에 min_length/max_bytes 검증 없음. 이유:
    1. 비번 정책 변경 시 과거 사용자 로그인 회귀 방지
    2. 긴 비번은 bcrypt 가 72바이트로 silent truncate 하므로 자연스럽게 401
    """

    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _strip_email(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v
