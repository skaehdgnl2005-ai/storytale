"""인증 API 라우터.

계약: docs/contracts/user-service.ts (AuthService)
엔드포인트: POST /auth/login, POST /auth/refresh, POST /auth/logout,
           POST /auth/consent, GET /auth/me
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.dependencies import get_db
from storytale.auth.schemas import (
    AuthTokens,
    ConsentRequest,
    SocialLoginRequest,
    TokenRefreshRequest,
)
from storytale.auth.service import AuthService, create_blacklist

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "change-me-in-production")

# 모듈 수준 싱글턴 — 서버 수명주기 동안 하나의 블랙리스트 인스턴스 공유
_blacklist = create_blacklist()


def _get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:  # noqa: B008
    return AuthService(db=db, jwt_secret=JWT_SECRET, blacklist=_blacklist)


AuthServiceDep = Annotated[AuthService, Depends(_get_auth_service)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]


async def get_current_user_id(
    credentials: CredentialsDep,
    auth_service: AuthServiceDep,
) -> str:
    """보호된 엔드포인트용 의존성 — 현재 사용자 ID 반환."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    try:
        payload = auth_service.decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다")
        return payload["sub"]
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None


CurrentUserDep = Annotated[str, Depends(get_current_user_id)]


# ---------------------------------------------------------------------------
# 로그인
# ---------------------------------------------------------------------------


@router.post("/login", response_model=AuthTokens)
async def login(
    body: SocialLoginRequest,
    auth_service: AuthServiceDep,
) -> AuthTokens:
    """소셜 로그인 → JWT 토큰 발급."""
    try:
        return await auth_service.social_login(
            provider=body.provider, auth_code=body.auth_code
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------------------------------------------------------------------------
# 토큰 갱신
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=AuthTokens)
async def refresh(
    body: TokenRefreshRequest,
    auth_service: AuthServiceDep,
) -> AuthTokens:
    """리프레시 토큰으로 새 토큰 쌍 발급."""
    try:
        return await auth_service.refresh_token(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None


# ---------------------------------------------------------------------------
# 로그아웃
# ---------------------------------------------------------------------------


@router.post("/logout")
async def logout(
    credentials: CredentialsDep,
    auth_service: AuthServiceDep,
) -> dict:
    """로그아웃 (리프레시 토큰 무효화)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    try:
        auth_service.decode_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None

    return {"message": "로그아웃 되었습니다"}


# ---------------------------------------------------------------------------
# 법정대리인 동의
# ---------------------------------------------------------------------------


@router.post("/consent")
async def record_consent(
    body: ConsentRequest,
    user_id: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> dict:
    """법정대리인(부모) 동의 기록."""
    if not body.agreed:
        raise HTTPException(status_code=400, detail="동의가 필요합니다")
    await auth_service.record_consent(user_id=user_id)
    return {"message": "동의가 기록되었습니다"}


# ---------------------------------------------------------------------------
# 내 정보
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_me(
    user_id: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> dict:
    """현재 로그인한 사용자 정보."""
    user = await auth_service.get_user(user_id=user_id)
    return {
        "user_id": str(user.id),
        "email": user.email,
        "provider": user.provider,
        "consent_given": user.consent_given_at is not None,
    }
