"""인증 서비스 — JWT, 소셜 로그인, 법정대리인 동의.

계약: docs/contracts/user-service.ts (AuthService)
"""

import functools
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

# S27b 비밀번호 해싱
DEFAULT_BCRYPT_ROUNDS = 12  # prod 기본값. dev 는 BCRYPT_ROUNDS=4 env 로 오버라이드
MAX_PASSWORD_BYTES = 72  # bcrypt null-terminated 입력 제한 (schemas.py 와 동일 값)
EMAIL_PROVIDER = "email"  # User.provider 값. 소셜 판정은 password_hash IS NULL 로 함


# ---------------------------------------------------------------------------
# S27b 예외
# ---------------------------------------------------------------------------


class EmailAlreadyExistsError(Exception):
    """이메일이 이미 존재하는 경우. 라우터에서 409 로 변환."""


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


# ---------------------------------------------------------------------------
# S27b 비밀번호 해싱
# ---------------------------------------------------------------------------


def _hash_password(plain: str) -> str:
    """bcrypt 해시 생성.

    BCRYPT_ROUNDS 환경변수를 **매 호출마다** 읽어 테스트의 monkeypatch.setenv
    호환성을 보장. 성능 영향: os.getenv ~100ns vs bcrypt ~10-250ms → 무시.
    """
    rounds = int(os.getenv("BCRYPT_ROUNDS", str(DEFAULT_BCRYPT_ROUNDS)))
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=rounds),
    ).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    """bcrypt 해시 비교. 72바이트 초과는 silent truncate (bcrypt 자동)."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


@functools.cache
def _get_dummy_hash() -> str:
    """Constant-time login 용 dummy hash. 프로세스 lifetime 내 1회만 계산.

    공격자가 존재하지 않는 이메일로 로그인 스팸할 때 매 요청마다 bcrypt.hashpw
    를 실행하면 prod 라운드 12 기준 ~250ms × 요청 수로 CPU 가 포화된다. 캐시로
    첫 로그인 시점에 1회만 계산 후 프로세스 종료까지 고정.

    BCRYPT_ROUNDS 런타임 변경 시 서버 재시작 필요(허용 가능한 제약).
    테스트 격리가 필요하면 `_get_dummy_hash.cache_clear()` 호출.
    """
    return _hash_password("constant-time-login-dummy-value")


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

    async def _find_user_by_email(self, email: str) -> User | None:
        """이메일로 사용자 조회. 없으면 None.

        호출자는 이 메서드 호출 전에 email 을 정규화(소문자화) 해야 한다.
        현재 소셜 경로는 정규화 없이 호출 — S38 배포 전 별도 스크립트로 백필.
        """
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _find_or_create_user(self, user_info: SocialUserInfo) -> User:
        """이메일로 기존 사용자 조회, 없으면 생성."""
        user = await self._find_user_by_email(user_info.email)
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

    # =======================================================================
    # S27b 이메일+비밀번호 로그인
    # =======================================================================

    async def register_with_email(self, email: str, password: str) -> AuthTokens:
        """이메일+비번 회원가입 → JWT 발급.

        Args:
            email: 사용자 이메일. 호출자는 이미 Pydantic EmailStr 로 검증된
                   값을 넘기지만, 이 메서드 내부에서 .lower() 로 추가 정규화.
            password: 평문 비번. Pydantic 에서 8자 이상 + 72바이트 이하 검증됨.

        Raises:
            EmailAlreadyExistsError: 같은 이메일로 이미 가입된 사용자 존재.

        Returns:
            AuthTokens: access + refresh 쌍.
        """
        # EmailStr 은 도메인만 자동 정규화. 로컬파트까지 통일하여
        # "User@example.com" ≠ "user@example.com" 같은 중복 가입을 방지.
        normalized_email = email.lower()

        # 선확인: 이미 존재하면 즉시 409
        existing = await self._find_user_by_email(normalized_email)
        if existing is not None:
            raise EmailAlreadyExistsError()

        # INSERT 시도
        try:
            user = User(
                id=uuid.uuid4(),
                email=normalized_email,
                provider=EMAIL_PROVIDER,
                password_hash=_hash_password(password),
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError as e:
            await self.db.rollback()
            # 교과서적 race condition 해결: rollback 후 재확인으로 IntegrityError
            # 의 실제 원인이 "이메일 중복" 인지 검증. 다른 원인(NOT NULL/FK/
            # Check) 이면 그대로 500 으로 전파하여 디버깅 단서 보존.
            existing = await self._find_user_by_email(normalized_email)
            if existing is not None:
                raise EmailAlreadyExistsError() from e
            raise

        return self._issue_tokens(str(user.id))

    async def login_with_email(self, email: str, password: str) -> AuthTokens:
        """이메일+비번 로그인 → JWT 발급 (constant-time).

        3가지 실패 케이스(이메일 없음 / 비번 틀림 / 소셜 전용 유저)가 동일한
        타이밍 + 동일한 에러 메시지를 반환하여 이메일 enumeration 방지.

        Raises:
            ValueError: 로그인 실패 (라우터에서 401 로 변환).

        Returns:
            AuthTokens: access + refresh 쌍.
        """
        normalized_email = email.lower()
        user = await self._find_user_by_email(normalized_email)

        # constant-time: user 가 없거나 password_hash 가 NULL 이면 dummy hash
        # 로 대체. bcrypt 타이밍이 모든 케이스에서 균일해짐.
        stored_hash = (
            user.password_hash
            if (user and user.password_hash)
            else _get_dummy_hash()
        )
        is_valid = _verify_password(password, stored_hash)

        if not (user and user.password_hash and is_valid):
            # 동일한 에러 메시지 + 동일한 타이밍 → 공격자에게 힌트 0
            raise ValueError("이메일 또는 비밀번호가 올바르지 않아요")

        return self._issue_tokens(str(user.id))

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
