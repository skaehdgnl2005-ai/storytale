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
    EmailLoginRequest,
    EmailRegisterRequest,
    SocialLoginRequest,
    TokenRefreshRequest,
)
from storytale.auth.service import (
    AuthService,
    EmailAlreadyExistsError,
    create_blacklist,
)

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
# S27b 이메일 회원가입 / 로그인
# ---------------------------------------------------------------------------


@router.post("/register/email", response_model=AuthTokens)
async def register_email(
    body: EmailRegisterRequest,
    auth_service: AuthServiceDep,
) -> AuthTokens:
    """이메일+비밀번호 회원가입 → JWT 발급.

    에러:
    - 422: Pydantic 검증 실패 (이메일 형식, 비번 길이/바이트)
    - 409: 이미 가입된 이메일 (inner code: EMAIL_ALREADY_EXISTS)
    """
    try:
        return await auth_service.register_with_email(
            email=body.email,
            password=body.password,
        )
    except EmailAlreadyExistsError as exc:
        # 기존 REJECTED_INTENT 패턴과 일관된 필드 순서: message → code
        raise HTTPException(
            status_code=409,
            detail={
                "message": "이미 가입된 이메일이에요 😊",
                "code": "EMAIL_ALREADY_EXISTS",
            },
        ) from exc


@router.post("/login/email", response_model=AuthTokens)
async def login_email(
    body: EmailLoginRequest,
    auth_service: AuthServiceDep,
) -> AuthTokens:
    """이메일+비밀번호 로그인 → JWT 발급 (constant-time).

    에러:
    - 422: Pydantic 검증 실패 (이메일 형식)
    - 401: 로그인 실패 (3가지 케이스 동일 응답: 이메일 없음 / 비번 틀림 /
           소셜 전용 유저). 이메일 존재 여부 노출 방지.
    """
    try:
        return await auth_service.login_with_email(
            email=body.email,
            password=body.password,
        )
    except ValueError as exc:
        # /auth/refresh 의 에러 핸들링 패턴을 따름. 기존 /auth/login 의
        # except Exception → 500 은 의도적으로 복제하지 않음 (SESSION_LOG
        # 의 "발견된 이슈" 참조).
        raise HTTPException(status_code=401, detail=str(exc)) from exc


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
