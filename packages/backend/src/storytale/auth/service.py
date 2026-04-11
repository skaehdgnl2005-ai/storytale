"""인증 서비스 — JWT, 소셜 로그인, 법정대리인 동의.

계약: docs/contracts/user-service.ts (AuthService)
"""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.auth.schemas import AuthTokens, SocialUserInfo
from storytale.db.models import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_EXPIRE_MINUTES = 1440  # 24시간
DEFAULT_REFRESH_EXPIRE_DAYS = 7
BLACKLIST_KEY_PREFIX = "token_blacklist:"


# ---------------------------------------------------------------------------
# 토큰 블랙리스트 프로토콜
# ---------------------------------------------------------------------------


class TokenBlacklist(Protocol):
    """토큰 블랙리스트 인터페이스."""

    async def add(self, token: str, ttl_seconds: int) -> None: ...
    async def contains(self, token: str) -> bool: ...


class InMemoryBlacklist:
    """인메모리 블랙리스트 — 테스트용."""

    def __init__(self) -> None:
        self._tokens: set[str] = set()

    async def add(self, token: str, ttl_seconds: int) -> None:
        self._tokens.add(token)

    async def contains(self, token: str) -> bool:
        return token in self._tokens


class RedisBlacklist:
    """Redis 기반 블랙리스트 — 프로덕션용.

    토큰을 키로, TTL을 리프레시 토큰 만료 시간에 맞춰 설정.
    서버 재시작 후에도 블랙리스트 유지.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        import redis.asyncio as aioredis

        self._url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = aioredis.from_url(self._url, decode_responses=True)

    async def add(self, token: str, ttl_seconds: int) -> None:
        key = f"{BLACKLIST_KEY_PREFIX}{token}"
        await self._redis.setex(key, ttl_seconds, "1")

    async def contains(self, token: str) -> bool:
        key = f"{BLACKLIST_KEY_PREFIX}{token}"
        return await self._redis.exists(key) > 0


def create_blacklist() -> TokenBlacklist:
    """환경에 따라 블랙리스트 구현체 선택."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        logger.info("Redis 블랙리스트 사용: %s", redis_url)
        return RedisBlacklist(redis_url)
    logger.warning("REDIS_URL 미설정 — 인메모리 블랙리스트 사용 (개발 전용)")
    return InMemoryBlacklist()


class AuthService:
    """인증 서비스.

    - JWT 액세스/리프레시 토큰 생성 및 검증
    - 소셜 로그인 (Google/Kakao/Apple)
    - 토큰 갱신 및 로그아웃
    - 법정대리인 동의 기록
    """

    def __init__(
        self,
        db: AsyncSession,
        jwt_secret: str | None = None,
        access_token_expire_minutes: int = DEFAULT_ACCESS_EXPIRE_MINUTES,
        refresh_token_expire_days: int = DEFAULT_REFRESH_EXPIRE_DAYS,
        blacklist: TokenBlacklist | None = None,
    ) -> None:
        self.db = db
        self.jwt_secret = jwt_secret or os.getenv(
            "JWT_SECRET_KEY", "change-me-in-production"
        )
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self._blacklist = blacklist or InMemoryBlacklist()

    # =======================================================================
    # JWT 토큰
    # =======================================================================

    def create_access_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """액세스 토큰 생성."""
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": now + expires_delta,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """리프레시 토큰 생성."""
        if expires_delta is None:
            expires_delta = timedelta(days=self.refresh_token_expire_days)
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + expires_delta,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=JWT_ALGORITHM)

    def decode_token(self, token: str) -> dict:
        """토큰 디코딩 및 검증."""
        try:
            return jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError as e:
            raise ValueError("만료된 토큰입니다") from e
        except jwt.InvalidTokenError as e:
            raise ValueError("유효하지 않은 토큰입니다") from e

    # =======================================================================
    # 소셜 로그인
    # =======================================================================

    async def social_login(self, provider: str, auth_code: str) -> AuthTokens:
        """소셜 로그인 → 사용자 조회/생성 → JWT 발급."""
        user_info = await self._get_social_user_info(provider, auth_code)
        user = await self._find_or_create_user(user_info)
        return self._issue_tokens(str(user.id))

    async def _get_social_user_info(
        self, provider: str, auth_code: str
    ) -> SocialUserInfo:
        """소셜 프로바이더에서 사용자 정보 조회.

        프로바이더별 구현:
        - Google: ID 토큰 검증 (tokeninfo API)
        - Kakao: auth_code → 액세스 토큰 교환 → 사용자 정보 조회
        - Apple: ID 토큰 검증 (공개키 기반 JWT)
        """
        from storytale.auth.providers import SocialAuthError, get_provider

        try:
            social_provider = get_provider(provider)
            return await social_provider.get_user_info(auth_code=auth_code)
        except SocialAuthError as e:
            raise ValueError(str(e)) from e

    async def _find_or_create_user(self, user_info: SocialUserInfo) -> User:
        """이메일로 기존 사용자 조회, 없으면 생성."""
        stmt = select(User).where(User.email == user_info.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=user_info.email,
                provider=user_info.provider,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return user

    def _issue_tokens(self, user_id: str) -> AuthTokens:
        """액세스 + 리프레시 토큰 쌍 발급."""
        return AuthTokens(
            access_token=self.create_access_token(user_id=user_id),
            refresh_token=self.create_refresh_token(user_id=user_id),
            expires_in=self.access_token_expire_minutes * 60,
        )

    # =======================================================================
    # 토큰 갱신
    # =======================================================================

    async def refresh_token(self, refresh_token: str) -> AuthTokens:
        """리프레시 토큰으로 새 토큰 쌍 발급."""
        if await self._blacklist.contains(refresh_token):
            raise ValueError("무효화된 토큰입니다")

        payload = self.decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise ValueError("리프레시 토큰이 아닙니다")

        user_id = payload["sub"]
        return self._issue_tokens(user_id)

    # =======================================================================
    # 로그아웃
    # =======================================================================

    async def logout(self, refresh_token: str) -> None:
        """리프레시 토큰 무효화 (블랙리스트 등록)."""
        payload = self.decode_token(refresh_token)
        # TTL을 토큰 만료까지 남은 시간으로 설정 (만료 후 자동 삭제)
        exp = payload.get("exp", 0)
        now = int(datetime.now(UTC).timestamp())
        ttl = max(exp - now, 1)
        await self._blacklist.add(refresh_token, ttl_seconds=ttl)

    # =======================================================================
    # 법정대리인 동의
    # =======================================================================

    async def record_consent(self, user_id: str) -> None:
        """법정대리인(부모) 동의 기록."""
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(User).where(User.id == uid)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("사용자를 찾을 수 없습니다")

        user.consent_given_at = datetime.now(UTC)
        await self.db.commit()

    async def has_consent(self, user_id: str) -> bool:
        """동의 여부 확인."""
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(User).where(User.id == uid)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("사용자를 찾을 수 없습니다")

        return user.consent_given_at is not None

    async def get_user(self, user_id: str) -> User:
        """사용자 조회."""
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(User).where(User.id == uid)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("사용자를 찾을 수 없습니다")

        return user
