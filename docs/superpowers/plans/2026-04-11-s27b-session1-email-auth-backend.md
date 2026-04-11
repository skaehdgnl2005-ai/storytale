# S27b 세션 1 — 이메일+비밀번호 로그인 (백엔드) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 소셜 로그인 백엔드(S27)에 이메일+비밀번호 회원가입/로그인을 추가하여 세션 2(모바일 LoginScreen) 가 의존할 API 를 완성한다.

**Architecture:** `User.password_hash` 컬럼을 추가(nullable, 하위 호환). `auth/service.py` 에 bcrypt 해싱 + constant-time login (`@functools.cache` dummy hash) + `register_with_email`/`login_with_email` 메서드를 추가. 새 `auth/schemas.py` 스키마(`EmailRegisterRequest`/`EmailLoginRequest`) 는 Pydantic `EmailStr` + `strip()` pre-validator + 72바이트 UTF-8 검증. `auth_router.py` 에 `POST /auth/register/email` 과 `POST /auth/login/email` 을 추가하되 기존 엔드포인트는 건드리지 않음. `_issue_tokens` 재사용으로 refresh token 파이프라인은 신규 코드 0줄.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 + `pydantic[email]`, bcrypt>=4.1, PyJWT, pytest, pytest-asyncio, httpx AsyncClient, aiosqlite

**Spec:** [docs/superpowers/specs/2026-04-11-s27b-session1-email-auth-backend-design.md](../specs/2026-04-11-s27b-session1-email-auth-backend-design.md)

**핸드오프:** [docs/S27b-handoff.md](../../S27b-handoff.md)

---

## File Structure

| 파일 | 역할 | 변경 유형 |
|---|---|---|
| `packages/backend/pyproject.toml` | Python 의존성 매니페스트 | 수정: `bcrypt` 추가, `pydantic` → `pydantic[email]` |
| `packages/backend/src/storytale/db/models.py` | SQLAlchemy ORM 모델 | 수정: `User.password_hash` 컬럼 추가 |
| `packages/backend/alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py` | DB 스키마 migration | **신규** (수동 작성) |
| `packages/backend/src/storytale/auth/schemas.py` | 인증 Pydantic 스키마 | 수정: `EmailRegisterRequest`/`EmailLoginRequest` 추가 |
| `packages/backend/src/storytale/auth/service.py` | AuthService (JWT, 소셜, 블랙리스트) | 수정: `EmailAlreadyExistsError` + 헬퍼 + `register_with_email`/`login_with_email` + `_find_or_create_user` 리팩터링 |
| `packages/backend/src/storytale/api/auth_router.py` | FastAPI 라우터 | 수정: `POST /auth/register/email`, `POST /auth/login/email` 추가 (기존 엔드포인트 건드리지 않음) |
| `packages/backend/tests/test_s27b_email_auth.py` | S27b TDD 테스트 스위트 | **신규** (약 15 케이스) |

**변경 파일 수**: 6 (테스트 파일은 카운트 별도 — CLAUDE.md 관례)

**건드리지 않는 파일** (중요):
- `packages/backend/tests/test_s27_auth_api.py` — 회귀만 확인, 수정 금지
- `packages/backend/tests/conftest.py` — 신규 컬럼은 `Base.metadata.create_all` 로 자동 반영
- `packages/backend/src/storytale/auth/service.py` 의 `create_access_token`/`create_refresh_token`/`_issue_tokens`/`refresh_token`/`logout` 메서드 — 재사용만 (본문 수정 금지)
- `packages/backend/src/storytale/api/auth_router.py` 의 `login`/`refresh`/`logout`/`record_consent`/`get_me` 엔드포인트 — 본문 수정 금지 (기존 버그는 S27b 범위 밖)

---

## 사전 체크 — 환경 확인

- [ ] **Step 0.1: venv 활성화 확인**

Windows PowerShell:
```powershell
cd packages/backend
.venv\Scripts\activate
```

Bash (Git Bash on Windows):
```bash
cd packages/backend
source .venv/Scripts/activate
```

기대: 프롬프트에 `(.venv)` 표시

- [ ] **Step 0.2: 현재 테스트 베이스라인 확인**

```bash
pytest tests/test_s27_auth_api.py -v
```

기대: 전 케이스 통과. 회귀 베이스라인 기록.

- [ ] **Step 0.3: BCRYPT_ROUNDS 환경변수 설정 (테스트용)**

테스트 속도를 위해 dev 라운드 4 로 고정:

Bash:
```bash
export BCRYPT_ROUNDS=4
```

PowerShell:
```powershell
$env:BCRYPT_ROUNDS = "4"
```

기대: 이후 모든 pytest 명령이 이 환경에서 실행됨. 대략 bcrypt 1회당 ~10ms.

---

### Task 1: 의존성 추가 — `bcrypt` + `pydantic[email]`

**Files:**
- Modify: `packages/backend/pyproject.toml`

- [ ] **Step 1.1: pyproject.toml 수정**

`packages/backend/pyproject.toml` 의 `dependencies` 블록을 찾아 다음과 같이 변경:

변경 전:
```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "sqlalchemy>=2.0,<3",
    "alembic>=1.14,<2",
    "asyncpg>=0.30,<1",
    "pydantic>=2.0,<3",
    "pydantic-settings>=2.0,<3",
    "httpx>=0.28,<1",
    "redis>=5.0,<6",
    "python-dotenv>=1.0,<2",
    "PyJWT>=2.8,<3",
    ...
]
```

변경 후 — `pydantic` 을 `pydantic[email]` 로 전환하고 `bcrypt` 추가:
```toml
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "sqlalchemy>=2.0,<3",
    "alembic>=1.14,<2",
    "asyncpg>=0.30,<1",
    "pydantic[email]>=2.0,<3",
    "pydantic-settings>=2.0,<3",
    "httpx>=0.28,<1",
    "redis>=5.0,<6",
    "python-dotenv>=1.0,<2",
    "PyJWT>=2.8,<3",
    "bcrypt>=4.1,<5",
    ...
]
```

(`PyYAML`, `anthropic`, `google-genai`, `boto3`, `Pillow` 는 건드리지 않음. 순서만 유지.)

- [ ] **Step 1.2: 의존성 설치**

```bash
pip install -e .
```

기대 출력에 다음 패키지들이 설치됨을 확인:
```
Successfully installed bcrypt-4.x.x email-validator-2.x.x dnspython-... idna-...
```

- [ ] **Step 1.3: import smoke test**

```bash
python -c "import bcrypt; import email_validator; from pydantic import EmailStr; print('OK')"
```

기대 출력:
```
OK
```

에러가 나면: `pip install bcrypt email-validator` 개별 설치 후 재시도.

- [ ] **Step 1.4: 커밋**

```bash
cd ../..
git add packages/backend/pyproject.toml
git commit -m "chore(S27b): bcrypt + pydantic[email] 의존성 추가

이메일+비밀번호 로그인(S27b)에 필요한 bcrypt 해싱과 Pydantic EmailStr
검증을 위해 의존성 추가.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `User.password_hash` 컬럼 추가

**Files:**
- Modify: `packages/backend/src/storytale/db/models.py:25-36`

- [ ] **Step 2.1: models.py 의 `User` 클래스 수정**

`packages/backend/src/storytale/db/models.py` 에서 `User` 클래스를 찾아 `password_hash` 컬럼을 `consent_given_at` 아래에 추가:

변경 전 (models.py:25-36):
```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    consent_given_at = Column(DateTime(timezone=True), nullable=True)

    profiles = relationship("ChildProfile", back_populates="user")
    stories = relationship("Story", back_populates="user")
    book_recommendations = relationship("BookRecommendation", back_populates="user")
```

변경 후:
```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    consent_given_at = Column(DateTime(timezone=True), nullable=True)
    # S27b: 이메일+비번 로그인용 bcrypt 해시. 소셜 유저는 null 유지.
    password_hash = Column(String, nullable=True)

    profiles = relationship("ChildProfile", back_populates="user")
    stories = relationship("Story", back_populates="user")
    book_recommendations = relationship("BookRecommendation", back_populates="user")
```

- [ ] **Step 2.2: ORM 로드 smoke test**

```bash
cd packages/backend
python -c "from storytale.db.models import User; print([c.name for c in User.__table__.columns])"
```

기대 출력 (순서는 다를 수 있음):
```
['id', 'email', 'provider', 'created_at', 'consent_given_at', 'password_hash']
```

`password_hash` 가 포함되어 있어야 함.

- [ ] **Step 2.3: 회귀 테스트 (conftest 자동 create_all 이 새 컬럼을 반영하는지)**

```bash
pytest tests/test_s27_auth_api.py -v
```

기대: 전 케이스 통과 (새 컬럼이 nullable 이라 기존 테스트 영향 없음).

- [ ] **Step 2.4: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/db/models.py
git commit -m "feat(S27b): User 모델에 password_hash 컬럼 추가

이메일+비번 로그인 유저의 bcrypt 해시를 저장할 컬럼. 소셜 유저는 nullable
유지로 하위 호환. conftest.py 의 Base.metadata.create_all 이 자동 반영하므로
테스트 DB 변경은 불필요.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: alembic migration — `password_hash` 추가

**Files:**
- Create: `packages/backend/alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py`

**주의**: 핸드오프 경고에 따라 `alembic revision --autogenerate` 는 **사용하지 않음**. 기존 migration 이 Postgres `JSONB` 를 사용해 SQLite 로 autogenerate 시 모든 테이블 diff 를 잡기 때문에 수동 작성. 기존 `a1b2c3d4e5f6_add_consent_given_at_to_users.py` 를 템플릿으로 사용.

- [ ] **Step 3.1: 기존 migration 체인 확인**

```bash
ls packages/backend/alembic/versions/
```

기대 출력:
```
76c2febda894_initial_schema.py
a1b2c3d4e5f6_add_consent_given_at_to_users.py
__pycache__
```

새 migration 의 `down_revision` 은 `a1b2c3d4e5f6` 이어야 함.

- [ ] **Step 3.2: 신규 migration 파일 생성**

파일 `packages/backend/alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py` 를 다음 내용으로 생성:

```python
"""Add password_hash to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """S27b: 이메일+비번 로그인용 password_hash 컬럼 추가.

    소셜 유저는 null 유지 (하위 호환).
    """
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """password_hash 컬럼 제거."""
    op.drop_column("users", "password_hash")
```

- [ ] **Step 3.3: migration 구문 검증**

```bash
cd packages/backend
python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
cfg = Config('alembic.ini')
script = ScriptDirectory.from_config(cfg)
heads = script.get_heads()
print('heads:', heads)
for rev in script.walk_revisions():
    print(rev.revision, '<-', rev.down_revision)
"
```

기대 출력 (head 는 새 migration 이어야 함):
```
heads: ('b2c3d4e5f6a7',)
b2c3d4e5f6a7 <- a1b2c3d4e5f6
a1b2c3d4e5f6 <- 76c2febda894
76c2febda894 <- None
```

- [ ] **Step 3.4: 커밋**

```bash
cd ../..
git add packages/backend/alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py
git commit -m "feat(S27b): add password_hash alembic migration

수동 작성. autogenerate 는 기존 JSONB 테이블 diff 를 전부 잡으므로 사용
안 함. down_revision 은 a1b2c3d4e5f6 (consent_given_at). 프로덕션 배포 전
(S38) 에 alembic upgrade head 로 적용 예정.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: RED — 테스트 스위트 전체 작성

**Files:**
- Create: `packages/backend/tests/test_s27b_email_auth.py`

- [ ] **Step 4.1: 테스트 파일 생성**

파일 `packages/backend/tests/test_s27b_email_auth.py` 를 다음 내용으로 생성:

```python
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
        mixed_case = original.replace("example.com", "Example.COM").upper()[:5] + original[5:]
        # 간단히 대소문자 섞기: 원본이 lowercase 이므로 일부를 대문자로
        resp = await client.post(
            "/auth/register/email",
            json={"email": original.upper(), "password": "testpass123"},
        )
        assert resp.status_code == 200

        # DB 에는 소문자로 저장되어야 함
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
        # 한글 25자 = UTF-8 75바이트 (3바이트 × 25). bcrypt 72바이트 한도 초과
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
    async def test_login_with_wrong_password_returns_401(
        self, client, registered_user
    ):
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
```

- [ ] **Step 4.2: 테스트 파일 실행 — RED 확인**

```bash
cd packages/backend
pytest tests/test_s27b_email_auth.py -v
```

기대: **전 케이스 실패**. 대표적 에러는 다음 중 하나:
- `404 Not Found` — 엔드포인트 아직 없음
- `ModuleNotFoundError` / `ImportError` — 스키마/예외 아직 없음

주의: 일부 케이스는 엔드포인트가 없어서 FastAPI 가 `405 Method Not Allowed` 나 `404` 를 반환할 수 있음. 이는 의도된 RED.

**RED 가 아닌 경우** (즉 어떤 테스트가 우연히 통과하는 경우) 는 테스트가 틀렸다는 신호 → 코드 리뷰 후 수정.

- [ ] **Step 4.3: 커밋 (실패 테스트)**

```bash
cd ../..
git add packages/backend/tests/test_s27b_email_auth.py
git commit -m "test(S27b): 이메일 인증 엔드포인트 테스트 스위트 (RED)

register(8) + login(7) + /auth/me 회귀(1) 총 16 케이스. 엔드포인트 미구현
상태에서 404/ImportError 로 전부 실패 확인. 후속 커밋으로 GREEN 진입.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: GREEN — Pydantic 스키마

**Files:**
- Modify: `packages/backend/src/storytale/auth/schemas.py`

- [ ] **Step 5.1: schemas.py 에 신규 스키마 추가**

`packages/backend/src/storytale/auth/schemas.py` 파일을 다음 내용으로 **완전히 교체**:

```python
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
```

- [ ] **Step 5.2: 스키마 단독 import 검증**

```bash
cd packages/backend
python -c "
from storytale.auth.schemas import EmailRegisterRequest, EmailLoginRequest, MAX_PASSWORD_BYTES
print('MAX_PASSWORD_BYTES:', MAX_PASSWORD_BYTES)

# 정상 케이스
req = EmailRegisterRequest(email='  Foo@Example.COM  ', password='testpass123')
print('email after validation:', req.email)

# strip + EmailStr 도메인 소문자화 확인
assert '@example.com' in req.email.lower(), f'got {req.email}'

# 에러 케이스: 짧은 비번
try:
    EmailRegisterRequest(email='a@b.com', password='short')
    print('ERROR: should have raised')
except Exception as e:
    print('short password rejected:', type(e).__name__)

# 에러 케이스: 72바이트 초과
try:
    EmailRegisterRequest(email='a@b.com', password='가' * 25)
    print('ERROR: should have raised')
except Exception as e:
    print('overlong password rejected:', type(e).__name__)
"
```

기대 출력:
```
MAX_PASSWORD_BYTES: 72
email after validation: Foo@example.com
short password rejected: ValidationError
overlong password rejected: ValidationError
```

주의: `Foo@example.com` 으로 로컬파트 `Foo` 는 보존, 도메인만 소문자화 — 이는 EmailStr 의 기본 동작. 서비스 계층에서 `email.lower()` 로 추가 정규화 예정.

- [ ] **Step 5.3: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/auth/schemas.py
git commit -m "feat(S27b): EmailRegisterRequest/EmailLoginRequest Pydantic 스키마

- EmailStr 로 RFC 5322 검증 (pydantic[email] extras)
- @field_validator(mode='before') + strip() 으로 모바일 복붙 UX
- Register 비번 검증: min_length 8 + max UTF-8 72바이트
- Login 비번 검증 없음 (정책 변경 회귀 방지 + bcrypt truncate 위임)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: GREEN — service.py 헬퍼 + 예외 + 리팩터링

**Files:**
- Modify: `packages/backend/src/storytale/auth/service.py`

이 Task 는 코드량이 많아서 세부 단계로 분할합니다. `register_with_email`/`login_with_email` 은 Task 7 에서 추가합니다.

- [ ] **Step 6.1: import 섹션 확장**

`packages/backend/src/storytale/auth/service.py` 의 import 블록(1-18 라인)을 찾아 다음 import 를 추가:

변경 전:
```python
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
```

변경 후:
```python
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
```

변경 포인트 3개:
1. `import functools` 추가
2. `import bcrypt` 추가
3. `from sqlalchemy.exc import IntegrityError` 추가

- [ ] **Step 6.2: 상수 블록에 S27b 상수 추가**

기존 상수 블록(`JWT_ALGORITHM = "HS256"` 등) 아래에 추가:

변경 전:
```python
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_EXPIRE_MINUTES = 1440  # 24시간
DEFAULT_REFRESH_EXPIRE_DAYS = 7
BLACKLIST_KEY_PREFIX = "token_blacklist:"
```

변경 후:
```python
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_EXPIRE_MINUTES = 1440  # 24시간
DEFAULT_REFRESH_EXPIRE_DAYS = 7
BLACKLIST_KEY_PREFIX = "token_blacklist:"

# S27b 비밀번호 해싱
DEFAULT_BCRYPT_ROUNDS = 12  # prod 기본값. dev 는 BCRYPT_ROUNDS=4 env 로 오버라이드
MAX_PASSWORD_BYTES = 72  # bcrypt null-terminated 입력 제한 (schemas.py 와 동일 값)
EMAIL_PROVIDER = "email"  # User.provider 값. 소셜 판정은 password_hash IS NULL 로 함
```

- [ ] **Step 6.3: `EmailAlreadyExistsError` 예외 클래스 추가**

`TokenBlacklist(Protocol):` 선언 **위** (블랙리스트 섹션 시작 주석 위) 에 추가:

찾을 위치:
```python
# ---------------------------------------------------------------------------
# 토큰 블랙리스트 프로토콜
# ---------------------------------------------------------------------------


class TokenBlacklist(Protocol):
```

변경 후 — 섹션 주석 위에 새 섹션 삽입:
```python
# ---------------------------------------------------------------------------
# S27b 예외
# ---------------------------------------------------------------------------


class EmailAlreadyExistsError(Exception):
    """이메일이 이미 존재하는 경우. 라우터에서 409 로 변환."""


# ---------------------------------------------------------------------------
# 토큰 블랙리스트 프로토콜
# ---------------------------------------------------------------------------


class TokenBlacklist(Protocol):
```

- [ ] **Step 6.4: 비밀번호 해싱 헬퍼 함수 추가**

`create_blacklist()` 함수 **아래**, `class AuthService:` **위** 에 헬퍼 함수 블록 추가.

찾을 위치 (service.py 의 `create_blacklist` 함수 끝 — 약 85-86 라인):
```python
def create_blacklist() -> TokenBlacklist:
    """환경에 따라 블랙리스트 구현체 선택."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        logger.info("Redis 블랙리스트 사용: %s", redis_url)
        return RedisBlacklist(redis_url)
    logger.warning("REDIS_URL 미설정 — 인메모리 블랙리스트 사용 (개발 전용)")
    return InMemoryBlacklist()


class AuthService:
```

변경 후 — 헬퍼 섹션 삽입:
```python
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
```

- [ ] **Step 6.5: `_find_user_by_email` 헬퍼 추가 + `_find_or_create_user` 리팩터링**

`AuthService` 클래스 내부의 `_find_or_create_user` 메서드를 찾아서 수정.

찾을 위치 (service.py:194-210 근처):
```python
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
```

변경 후 — `_find_user_by_email` 헬퍼 추가 + 기존 메서드 리팩터링:
```python
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
```

- [ ] **Step 6.6: 리팩터링 회귀 확인**

```bash
cd packages/backend
pytest tests/test_s27_auth_api.py -v
```

기대: **전 케이스 통과**. `_find_or_create_user` 의 외부 동작은 변경 없음 (단순히 헬퍼 추출).

- [ ] **Step 6.7: import 체인 smoke test**

```bash
python -c "
from storytale.auth.service import (
    AuthService,
    EmailAlreadyExistsError,
    _hash_password,
    _verify_password,
    _get_dummy_hash,
)
print('imports OK')
h = _hash_password('testpass123')
print('hash prefix:', h[:7])
assert _verify_password('testpass123', h)
assert not _verify_password('wrongpass', h)
print('verify OK')
d = _get_dummy_hash()
print('dummy prefix:', d[:7])
"
```

기대 출력:
```
imports OK
hash prefix: $2b$04$    (또는 $2b$12$ if BCRYPT_ROUNDS 미설정)
verify OK
dummy prefix: $2b$04$    (동일)
```

- [ ] **Step 6.8: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/auth/service.py
git commit -m "feat(S27b): auth/service 헬퍼 — 해싱 + 예외 + _find_user_by_email

- EmailAlreadyExistsError 예외 클래스 (모듈 수준, RejectedIntentError 선례)
- _hash_password / _verify_password (bcrypt, BCRYPT_ROUNDS 매 호출 os.getenv)
- _get_dummy_hash (@functools.cache, constant-time login + DoS 방어)
- _find_user_by_email 신규 헬퍼
- _find_or_create_user 는 _find_user_by_email 재사용으로 리팩터링 (동작 동일)

register_with_email / login_with_email 메서드는 다음 커밋에서 추가.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: GREEN — `register_with_email` 메서드

**Files:**
- Modify: `packages/backend/src/storytale/auth/service.py`

- [ ] **Step 7.1: `register_with_email` 메서드 추가**

`AuthService` 클래스 내부의 `_issue_tokens` 메서드 **위** 에 추가.

찾을 위치 (service.py:212 근처):
```python
    def _issue_tokens(self, user_id: str) -> AuthTokens:
        """액세스 + 리프레시 토큰 쌍 발급."""
        return AuthTokens(
            access_token=self.create_access_token(user_id=user_id),
            refresh_token=self.create_refresh_token(user_id=user_id),
            expires_in=self.access_token_expire_minutes * 60,
        )
```

변경 후 — `register_with_email` 메서드를 위에 삽입:
```python
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

    def _issue_tokens(self, user_id: str) -> AuthTokens:
        """액세스 + 리프레시 토큰 쌍 발급."""
        return AuthTokens(
            access_token=self.create_access_token(user_id=user_id),
            refresh_token=self.create_refresh_token(user_id=user_id),
            expires_in=self.access_token_expire_minutes * 60,
        )
```

- [ ] **Step 7.2: smoke test — 메서드 직접 호출**

```bash
cd packages/backend
python -c "
import asyncio
from conftest import TestingSessionLocal
from storytale.auth.service import AuthService, EmailAlreadyExistsError

async def run():
    async with TestingSessionLocal() as db:
        svc = AuthService(db=db, jwt_secret='test-secret-32-chars-long-enough!!')
        tokens = await svc.register_with_email('smoke@example.com', 'testpass123')
        print('access_token prefix:', tokens.access_token[:20])
        assert tokens.refresh_token
        assert tokens.expires_in > 0

        # 중복 가입 → 예외
        try:
            await svc.register_with_email('smoke@example.com', 'other123')
            print('ERROR: should have raised')
        except EmailAlreadyExistsError:
            print('duplicate rejected OK')

asyncio.run(run())
"
```

기대 출력:
```
access_token prefix: eyJ...
duplicate rejected OK
```

주의: `conftest` 를 직접 import 하므로 `pythonpath` 가 `tests` 를 포함해야 함. `pyproject.toml` 의 `[tool.pytest.ini_options]::pythonpath = ["tests"]` 가 이를 보장.

만약 `ModuleNotFoundError: No module named 'conftest'` 가 나면:
```bash
python -c "
import sys; sys.path.insert(0, 'tests')
... (위 스크립트 그대로)
"
```

- [ ] **Step 7.3: register 테스트 부분 실행 (GREEN 확인)**

```bash
pytest tests/test_s27b_email_auth.py::TestRegisterEmail -v
```

기대: 8개 케이스 **통과** (엔드포인트가 아직 없어도 RED 인 것은 Task 9 에서 해결 — 여기선 서비스 계층만).

주의: 테스트는 HTTP 경유 (`client.post("/auth/register/email", ...)`) 라 실제로는 엔드포인트가 필요함. 이 단계에서는 전부 여전히 404 로 실패할 것. Task 9 (라우터) 를 끝낸 후 다시 확인.

- [ ] **Step 7.4: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/auth/service.py
git commit -m "feat(S27b): AuthService.register_with_email — 이메일 회원가입

- email.lower() 로 로컬파트까지 정규화 (EmailStr 은 도메인만 처리)
- 선확인 → INSERT → IntegrityError 시 rollback 후 재확인 (race condition
  교과서 패턴). 다른 원인의 IntegrityError 는 500 으로 전파.
- _issue_tokens 재사용으로 refresh token 신규 코드 0줄
- User.provider = 'email' (EMAIL_PROVIDER 상수), password_hash = bcrypt

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: GREEN — `login_with_email` 메서드

**Files:**
- Modify: `packages/backend/src/storytale/auth/service.py`

- [ ] **Step 8.1: `login_with_email` 메서드 추가**

`register_with_email` 메서드 **아래**, `_issue_tokens` **위** 에 삽입:

```python
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
```

- [ ] **Step 8.2: smoke test — 로그인 분기 확인**

```bash
cd packages/backend
python -c "
import asyncio
from conftest import TestingSessionLocal
from storytale.auth.service import AuthService

async def run():
    async with TestingSessionLocal() as db:
        svc = AuthService(db=db, jwt_secret='test-secret-32-chars-long-enough!!')

        # 가입
        await svc.register_with_email('login-smoke@example.com', 'correctpass123')

        # 정상 로그인
        tokens = await svc.login_with_email('login-smoke@example.com', 'correctpass123')
        print('login OK, token prefix:', tokens.access_token[:20])

        # 대소문자 차이 → 성공
        tokens = await svc.login_with_email('LOGIN-smoke@example.COM', 'correctpass123')
        print('case-insensitive login OK')

        # 비번 틀림 → ValueError
        try:
            await svc.login_with_email('login-smoke@example.com', 'wrong')
            print('ERROR')
        except ValueError as e:
            print('wrong password:', e)

        # 존재 안 하는 이메일 → ValueError
        try:
            await svc.login_with_email('nobody@example.com', 'anything')
            print('ERROR')
        except ValueError as e:
            print('unknown email:', e)

asyncio.run(run())
"
```

기대 출력:
```
login OK, token prefix: eyJ...
case-insensitive login OK
wrong password: 이메일 또는 비밀번호가 올바르지 않아요
unknown email: 이메일 또는 비밀번호가 올바르지 않아요
```

두 에러 메시지가 **완전히 동일** 해야 함.

- [ ] **Step 8.3: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/auth/service.py
git commit -m "feat(S27b): AuthService.login_with_email — constant-time 로그인

3가지 실패 케이스(이메일 없음 / 비번 틀림 / 소셜 전용 유저) 동일 타이밍
+ 동일 에러 메시지로 이메일 enumeration 방지. @functools.cache dummy hash
로 매 요청 bcrypt.hashpw 호출 없이 ~250ms 타이밍 균일.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: GREEN — 라우터 엔드포인트 2개

**Files:**
- Modify: `packages/backend/src/storytale/api/auth_router.py`

- [ ] **Step 9.1: import 확장**

`packages/backend/src/storytale/api/auth_router.py` 의 import 블록 (1-22 라인)을 찾아 수정:

변경 전:
```python
from storytale.auth.schemas import (
    AuthTokens,
    ConsentRequest,
    SocialLoginRequest,
    TokenRefreshRequest,
)
from storytale.auth.service import AuthService, create_blacklist
```

변경 후 — `EmailRegisterRequest`/`EmailLoginRequest` + `EmailAlreadyExistsError` 추가:
```python
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
```

- [ ] **Step 9.2: `/auth/register/email` 엔드포인트 추가**

기존 `login` 엔드포인트 (auth_router.py:66-77) **아래** 에 새 섹션 추가.

찾을 위치:
```python
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
```

변경 후 — `login` 과 `# 토큰 갱신` 섹션 사이에 새 섹션 삽입:
```python
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
```

- [ ] **Step 9.3: 전체 S27b 테스트 실행 — GREEN 확인**

```bash
cd packages/backend
pytest tests/test_s27b_email_auth.py -v
```

기대: **전 16 케이스 통과**.

실패가 있을 경우 진단 가이드:
- **404 Not Found**: 라우터 등록이 안 됨 → `app.py` 에서 auth_router 가 include 되어 있는지 확인. (S27 에서 이미 등록돼 있어야 정상)
- **`test_register_duplicate_email_returns_409` 실패 (응답이 500)**: IntegrityError 가 EmailAlreadyExistsError 로 변환되지 않고 있음 → Task 7 의 try/except 블록 재확인
- **`test_login_with_unknown_email_returns_401` 실패 (에러 메시지가 다름)**: `login_with_email` 의 ValueError 메시지가 "이메일 또는 비밀번호가 올바르지 않아요" 인지 확인
- **`test_register_normalizes_email_case` 실패 (DB 에서 소문자 이메일 찾지 못함)**: `register_with_email` 에서 `normalized_email = email.lower()` 호출 확인
- **`test_register_strips_whitespace` 실패**: schemas.py 의 `_strip_email` validator 에서 `mode="before"` 누락

- [ ] **Step 9.4: 커밋**

```bash
cd ../..
git add packages/backend/src/storytale/api/auth_router.py
git commit -m "feat(S27b): POST /auth/register/email + /auth/login/email 라우터

- EmailAlreadyExistsError → 409 + {message, code} envelope
  (stories/router.py:677 REJECTED_INTENT 패턴과 일관된 필드 순서)
- login ValueError → 401 + string detail (/auth/refresh 패턴)
- 기존 /auth/login (social) 의 except Exception → 500 버그는 의도적으로
  복제하지 않음 (세션 1 범위 밖, SESSION_LOG 기록 예정)
- 기존 login/refresh/logout/consent/me 엔드포인트 건드리지 않음

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 회귀 스위트 + 린트 + 포맷

- [ ] **Step 10.1: 회귀 스위트 전체 실행**

```bash
cd packages/backend
pytest tests/test_s27b_email_auth.py tests/test_s27_auth_api.py tests/test_s35b_frontend_contract_e2e.py tests/test_s30a_plan_endpoint.py tests/test_s31a_plan_revise_endpoint.py tests/test_s34_story_delete_endpoint.py tests/test_s35a_text_illustration_e2e.py -v
```

기대: **전 스위트 통과**. 실패가 1건이라도 있으면 중단하고 원인 분석 후 수정.

- [ ] **Step 10.2: ruff check**

```bash
ruff check src tests
```

기대 출력:
```
All checks passed!
```

lint 위반이 있으면 `ruff check --fix src tests` 로 자동 수정 시도. 수동 수정 후 재실행.

- [ ] **Step 10.3: ruff format**

```bash
ruff format src tests
```

기대: **0 files reformatted** 또는 재포맷된 파일 목록.

재포맷이 발생했다면 `git diff` 로 변경 확인 후 Task 10.4 에서 함께 커밋.

- [ ] **Step 10.4: 린트/포맷 결과 커밋 (변경이 있을 때만)**

```bash
cd ../..
git status --short packages/backend/
```

변경이 있으면:
```bash
git add packages/backend/
git commit -m "style(S27b): ruff format 적용

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

변경 없으면 건너뛰고 Task 11 로 진행.

---

### Task 11: `dev_token.py` smoke test

**목적**: 새 `password_hash` 컬럼 추가가 기존 `scripts/dev_token.py` 동작을 깨지 않는지 확인. dev_token.py 는 `password_hash=None` 으로 User 를 생성하므로 nullable 컬럼에 영향 없어야 함.

- [ ] **Step 11.1: 기존 test.db 삭제 (깨끗한 상태 시작)**

**주의**: test.db 는 dev 용 SQLite 파일. 프로덕션 DB 가 아님. 삭제해도 안전.

```bash
cd packages/backend
rm -f test.db
```

- [ ] **Step 11.2: dev_token.py 실행**

```bash
python scripts/dev_token.py
```

기대 출력 (정확한 토큰 값은 매번 다름):
```
[Created] dev user: <uuid> <dev@storytale.local>

======================================================================
ACCESS TOKEN (24h expiry)
======================================================================
eyJ...
======================================================================

Temporarily replace line 9 of packages/mobile/src/api/client.ts:

   [before] let accessToken: string | null = null;
   [after ] let accessToken: string | null = "eyJ...";
...
```

실패 조건:
- **sqlalchemy.exc.OperationalError: no such column: users.password_hash** — `Base.metadata.create_all` 이 신규 컬럼을 반영 못 함 → models.py 수정 확인, test.db 다시 삭제 후 재실행
- **AttributeError: type object 'User' has no attribute 'password_hash'** — Task 2 가 제대로 커밋되지 않음 → `git log packages/backend/src/storytale/db/models.py` 확인

- [ ] **Step 11.3: 재실행 시 기존 유저 재사용 확인**

```bash
python scripts/dev_token.py
```

기대: `[Found existing] dev user: ...` (같은 uuid). password_hash 가 null 이어도 조회 성공.

- [ ] **Step 11.4: test.db 를 git 에서 제외 (이미 staging 돼 있으면 unstage)**

```bash
cd ../..
git status --short packages/backend/test.db
```

만약 `M` 표시가 되어 있으면:
```bash
git restore --staged packages/backend/test.db 2>/dev/null || true
```

(test.db 는 최초 커밋에 이미 들어가 있어서 M 표시가 날 수 있음. S27b 작업과 무관한 수정이므로 커밋하지 않음.)

---

### Task 12: SESSION_LOG 엔트리 작성

**Files:**
- Modify: `docs/SESSION_LOG.md` (파일 최상단에 새 엔트리 추가)

- [ ] **Step 12.1: 현재 SESSION_LOG 상단 확인**

```bash
head -5 docs/SESSION_LOG.md
```

기대: 기존 `## S35b — ...` 엔트리가 line 7 부근에 있음. 새 S27b 엔트리는 그 **위** (line 5 의 `---` 다음) 에 삽입.

- [ ] **Step 12.2: SESSION_LOG 에 새 엔트리 추가**

`docs/SESSION_LOG.md` 파일을 열어 line 5 의 `---` **아래** 에 다음 블록을 삽입. 기존 S35b 엔트리는 건드리지 않음.

```markdown
## S27b 세션 1 — 이메일+비밀번호 로그인 백엔드 (2026-04-11)

### 완료된 것
- **이메일 회원가입/로그인 백엔드 전체** — `POST /auth/register/email` + `POST /auth/login/email` 추가. 기존 JWT 파이프라인(`_issue_tokens`) 재사용으로 refresh token 발급 신규 코드 0줄. 기존 소셜 로그인 엔드포인트(`/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/consent`, `/auth/me`) 는 건드리지 않음.
- **`User.password_hash` 컬럼 추가** — `Column(String, nullable=True)`, 소셜 유저는 NULL 유지로 하위 호환. alembic migration `b2c3d4e5f6a7_add_password_hash_to_users.py` 수동 작성 (autogenerate 는 기존 JSONB diff 를 잡아서 사용 안 함).
- **의존성 추가** — `bcrypt>=4.1,<5` (해싱) + `pydantic[email]>=2.0,<3` (EmailStr 검증, `email-validator` 자동 pull).
- **Constant-time login** — `@functools.cache` 로 lazy init 된 `_get_dummy_hash()` 를 써서 3가지 실패 케이스(이메일 없음 / 비번 틀림 / 소셜 전용 유저)가 동일한 타이밍(~250ms prod) + 동일한 에러 메시지를 반환. 이메일 enumeration 방지 + DoS 방어.
- **Race condition 방어** — `register_with_email` 의 `IntegrityError` catch → rollback → `_find_user_by_email` 재확인 패턴. 다른 원인(NOT NULL/FK/Check)의 IntegrityError 는 500 으로 전파하여 디버깅 단서 보존.
- **이메일 정규화** — `@field_validator("email", mode="before")` + `strip()` pre-validator (모바일 복붙 UX) + 서비스 계층에서 `email.lower()` (EmailStr 의 도메인만 자동 정규화하는 부분을 로컬파트까지 확장).
- **테스트 스위트** — `test_s27b_email_auth.py` 16 케이스 (TestRegisterEmail 8 + TestLoginEmail 7 + TestMeEndpointWithEmailUser 1).

### TDD 워크플로우
1. **RED** — `tests/test_s27b_email_auth.py` 16 케이스 작성 → `pytest` → 전 케이스 404/ImportError 로 실패.
2. **GREEN 1** — `pyproject.toml` 의존성 추가 + `pip install -e .`
3. **GREEN 2** — `models.py::User.password_hash` + alembic migration.
4. **GREEN 3** — `schemas.py` 에 `EmailRegisterRequest`/`EmailLoginRequest` 추가 (EmailStr + strip + min_length 8 + max 72바이트).
5. **GREEN 4** — `service.py` 에 `EmailAlreadyExistsError` + `_hash_password`/`_verify_password`/`_get_dummy_hash`/`_find_user_by_email` 헬퍼 + `_find_or_create_user` 리팩터링.
6. **GREEN 5** — `service.py::register_with_email` (IntegrityError race 방어).
7. **GREEN 6** — `service.py::login_with_email` (constant-time 패턴).
8. **GREEN 7** — `auth_router.py` 에 두 엔드포인트 + 409/401 에러 envelope.
9. **회귀** — `test_s27_auth_api.py`, `test_s35b_frontend_contract_e2e.py`, `test_s30a_plan_endpoint.py`, `test_s31a_plan_revise_endpoint.py`, `test_s34_story_delete_endpoint.py`, `test_s35a_text_illustration_e2e.py` 전체 통과 확인.
10. **린트** — `ruff check src tests` + `ruff format src tests` 통과.
11. **`dev_token.py` smoke** — 새 컬럼 추가 후에도 정상 동작 확인 (`password_hash=None` 유지).

### 구현 요약
- **주요 클래스/함수/파일**:
  - `packages/backend/src/storytale/db/models.py::User.password_hash` — `Column(String, nullable=True)` 컬럼 추가
  - `packages/backend/alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py` — 수동 작성 migration (down_revision: `a1b2c3d4e5f6`)
  - `packages/backend/src/storytale/auth/schemas.py::EmailRegisterRequest` — EmailStr + `_strip_email` pre-validator + `_password_bytes_within_bcrypt_limit` field_validator
  - `packages/backend/src/storytale/auth/schemas.py::EmailLoginRequest` — EmailStr + `_strip_email` pre-validator (비번 길이 검증 없음 — 정책 변경 회귀 방지)
  - `packages/backend/src/storytale/auth/schemas.py::MIN_PASSWORD_LENGTH` = 8, `MAX_PASSWORD_BYTES` = 72
  - `packages/backend/src/storytale/auth/service.py::EmailAlreadyExistsError` — 모듈 수준 예외 클래스 (RejectedIntentError 선례)
  - `packages/backend/src/storytale/auth/service.py::_hash_password` — `os.getenv("BCRYPT_ROUNDS", "12")` 매 호출 조회 (테스트 monkeypatch 호환)
  - `packages/backend/src/storytale/auth/service.py::_verify_password` — `bcrypt.checkpw`
  - `packages/backend/src/storytale/auth/service.py::_get_dummy_hash` — `@functools.cache` lazy init
  - `packages/backend/src/storytale/auth/service.py::_find_user_by_email` — 신규 헬퍼
  - `packages/backend/src/storytale/auth/service.py::_find_or_create_user` — `_find_user_by_email` 재사용으로 리팩터링 (외부 동작 동일)
  - `packages/backend/src/storytale/auth/service.py::AuthService.register_with_email(email, password)` — 선확인 + INSERT + race condition 방어
  - `packages/backend/src/storytale/auth/service.py::AuthService.login_with_email(email, password)` — constant-time 패턴
  - `packages/backend/src/storytale/api/auth_router.py::register_email` — POST /auth/register/email → `EmailAlreadyExistsError → 409 + {message, code}`
  - `packages/backend/src/storytale/api/auth_router.py::login_email` — POST /auth/login/email → `ValueError → 401`
  - `packages/backend/tests/test_s27b_email_auth.py` — 16 케이스 TDD 스위트
- **계약 대비 변경점**:
  - `contracts/user-service.ts::AuthService` 는 이메일+비번 로그인을 명시하지 않음. S27b 는 S27 의 JWT 파이프라인 재사용 조건에서 새 엔드포인트 2개를 추가 — 계약 확장 성격.
  - `/auth/login/email` 실패 시 3가지 케이스(이메일 없음 / 비번 틀림 / 소셜 전용 유저) 가 동일한 401 + 동일 메시지 반환 — 보안 원칙(이메일 enumeration 방지) 우선. 핸드오프 원문은 "소셜 계정으로 가입된 이메일입니다" 힌트를 제안했으나 구현에서 기각.
  - inner code envelope 필드 순서 `{"message": ..., "code": ...}` 로 `stories/router.py:677` 의 `REJECTED_INTENT` 패턴과 일관. `.claude/rules/api-conventions.md` 는 `{detail, code}` 로 명시하지만 실제 구현은 FastAPI HTTPException 제약으로 nested 되어 있음 (드리프트).
- **환경변수**:
  - `BCRYPT_ROUNDS`: 기본값 `12` (prod). dev/test 는 `4` 로 설정하여 테스트 속도 확보. `.env.example` 반영 필요 (TODO).
- **의존 모듈 사용**:
  - `AuthService.create_access_token` / `create_refresh_token` / `_issue_tokens` (S27) — register/login 양쪽에서 재사용. 신규 토큰 로직 0줄.
  - `AuthService.decode_token` / `refresh_token` (S27) — 이메일 유저의 refresh token 도 `sub` + `type="refresh"` 만 보므로 변경 없이 동작.
  - `EmailStr` / `pydantic[email]` — RFC 5322 + IDN 검증, 도메인 자동 소문자화, 로컬파트 원본 보존.
  - `bcrypt.hashpw` / `gensalt(rounds=N)` / `checkpw` (신규) — 72바이트 초과 입력은 silent truncate.

### 다음 세션에 알려줄 것
- **세션 2 (모바일) 진입 조건 모두 충족** — 세션 1 완료 판정 체크리스트 (설계 스펙 §7) 전부 통과. 다음은 `docs/S27b-handoff.md` 의 "세션 2 시작 시 Claude 에게 전달할 프롬프트" 를 사용하여 새 세션으로 진입.
- **API 경로 확정** — `POST /api/v1/auth/register/email`, `POST /api/v1/auth/login/email`. 모바일 `src/api/client.ts` 의 `loginWithEmail`/`registerWithEmail` 함수는 이 경로와 request body `{email, password}` 를 그대로 사용.
- **에러 응답 형식** — 409 에는 inner code `EMAIL_ALREADY_EXISTS`. 401 에는 inner code 없음(string detail 만). 모바일 `parseErrorBody` 가 이미 이 형식을 파싱하므로 추가 작업 불필요. 분기 코드:
  ```typescript
  if (err.status === 409 && err.code === "EMAIL_ALREADY_EXISTS") { ... }
  if (err.status === 401) { ... }
  ```

### 발견된 이슈 / 이월 사항

- 🚨 **(보안 높음) `/auth/logout` 은 현재 완전한 no-op** — `auth_router.py:102-115` 가 `auth_service.logout()` 을 호출하지 않고 토큰 디코드만 수행. 추가로 router(access token) ↔ service(refresh token) 계층 간 토큰 타입 가정 불일치. 블랙리스트에 아무것도 추가되지 않아 refresh token 이 여전히 유효 → 로그아웃 후에도 `/auth/refresh` 로 새 access token 발급 가능. 수정은 설계 재검토 필요 (router 가 refresh_token 을 body 로 받을지, access token 의 jti 를 블랙리스트 키로 쓸지). **권장: S27d 신규 태스크로 분리**. 세션 2 모바일 작업에는 능동 로그아웃 UI 가 원래 계획에 없으므로 영향 없음.

- **(중간) `/auth/login` (social) 의 `except Exception → 500` 버그** — `auth_router.py:66-77`. `SocialAuthError`/`ValueError` 모두 500 으로 변환되어 클라이언트는 401 을 받아야 할 상황에도 500 수신. `/auth/refresh` 는 같은 상황에서 `except ValueError → 401` 로 올바르게 처리함. S27b 는 새 엔드포인트에서 `/auth/refresh` 패턴을 따랐고 기존 `/auth/login` 은 의도적으로 건드리지 않음. S27d 에서 함께 수정 권장.

- **(낮음) `api-conventions.md` ↔ 실제 구현 드리프트** — `.claude/rules/api-conventions.md` 는 `{detail: "메시지", code: "ERROR_CODE"}` 로 명시하지만 실제 구현은 FastAPI `HTTPException` 제약으로 `{detail: {message, code}}` nested 구조. 별도 문서 동기화 태스크 필요.

- **(낮음) 기존 social 유저 이메일 case 정규화 미적용** — `_find_or_create_user` 는 소셜 프로바이더 반환값을 그대로 비교. Apple 등 일부 프로바이더가 원본 case 로 반환할 수 있어서 배포 시점에 `UPDATE users SET email = LOWER(email)` 필요. **S38 배포 전 체크리스트**: `scripts/s38_pre_deploy_normalize_emails.py` 작성 (dry-run + 충돌 감지 + 수동 해소 경로).

- **(낮음) DB 레벨 case-insensitive unique index 부재** — 현재 서비스 계층 `email.lower()` 로 방어. admin 스크립트나 ORM bypass 는 뚫림. 궁극적 방어는 Postgres `CREATE UNIQUE INDEX ... ON users (LOWER(email))` 또는 `citext`. S27c 또는 별도 hardening.

- **(미래) 비밀번호 변경 시 refresh token 일괄 무효화 메커니즘 필요** — 현재 `_blacklist` 는 개별 토큰 키 기반. user-wide 무효화는 `User.token_version` 필드 + JWT payload 에 version 포함, 또는 user-wide Redis 블랙리스트 키 패턴, 또는 refresh token 개별 관리 테이블 중 선택 필요. 비번 변경 기능 도입 시 결정.

- **(기록) `provider` 컬럼 의미** — "최초 가입 경로" 로 고정된 historical marker. 시나리오 (b) email 유저가 `/auth/login` (social) 재접속 시 `_find_or_create_user` 가 기존 유저 반환 + provider 갱신 없음 → 이 값은 로직 분기에 **사용 금지**. 소셜/로컬 분기는 `password_hash IS NULL` 로 판단.

- **(기록) 암묵적 계정 연결** — `_find_or_create_user` 는 이메일만으로 조회. email 유저가 같은 이메일로 소셜 로그인 시 기존 로컬 계정에 JWT 발급됨. OIDC "이메일 소유권 증명" 합의 기반의 의도된 동작. UX 개선 필요 시 S27c.

- **(기술 부채) `.env.example` 에 `BCRYPT_ROUNDS` 반영 필요** — dev=4, prod=12 설정 문서화. S38 배포 전 체크리스트.
```

- [ ] **Step 12.3: SESSION_LOG 커밋**

```bash
git add docs/SESSION_LOG.md
git commit -m "docs(S27b): SESSION_LOG 세션 1 엔트리 + 발견된 이슈 3건

S27b 세션 1 (백엔드) 완료 기록. 구현 요약, TDD 워크플로우, 계약 변경점,
발견된 이슈 (특히 /auth/logout no-op 버그 - S27d 제안, /auth/login 의
except Exception → 500 버그).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: S27b-handoff.md 갱신 (세션 1 완료 표시)

**Files:**
- Modify: `docs/S27b-handoff.md`

핸드오프 파일은 원래 S27b 세션 1/2 완료 후 **삭제 권장** 이지만, 세션 2 가 아직 남아 있으므로 세션 1 완료 상태만 표시.

- [ ] **Step 13.1: 세션 1 완료 마커 추가**

`docs/S27b-handoff.md` 파일 최상단의 TL;DR 섹션을 찾아서 다음 한 줄을 `## TL;DR` 섹션 **내부** 맨 앞에 추가:

변경 전:
```markdown
## TL;DR

S27 (인증) 은 백엔드 소셜 로그인까지만 완료되었고, ...
```

변경 후:
```markdown
## TL;DR

> **2026-04-11 업데이트**: 세션 1 (백엔드) 완료. 세션 2 (모바일) 만 남음. SESSION_LOG S27b 엔트리 참조.

S27 (인증) 은 백엔드 소셜 로그인까지만 완료되었고, ...
```

- [ ] **Step 13.2: 커밋**

```bash
git add docs/S27b-handoff.md
git commit -m "docs(S27b): 핸드오프에 세션 1 완료 마커 추가

세션 2 (모바일) 진입 시 혼동 방지용. 세션 2 완료 후 파일 전체 삭제 예정.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: 최종 완료 판정

- [ ] **Step 14.1: 완료 판정 체크리스트 확인**

설계 스펙 §7 의 완료 판정을 순차 실행:

```bash
cd packages/backend

# 1. S27b 테스트 전 케이스 통과
pytest tests/test_s27b_email_auth.py -v
# 기대: 16 passed

# 2. 회귀 스위트 0건
pytest tests/test_s27_auth_api.py tests/test_s35b_frontend_contract_e2e.py -v
# 기대: 전 케이스 통과

# 3. 확장 회귀 스위트
pytest tests/test_s30a_plan_endpoint.py tests/test_s31a_plan_revise_endpoint.py tests/test_s34_story_delete_endpoint.py tests/test_s35a_text_illustration_e2e.py -v
# 기대: 전 케이스 통과

# 4. Lint
ruff check src tests
# 기대: All checks passed!

# 5. Format 변경 없음
ruff format --check src tests
# 기대: N files already formatted

# 6. Migration 수동 편집 확인
cat alembic/versions/b2c3d4e5f6a7_add_password_hash_to_users.py | grep -E "op\.(add_column|drop_column)"
# 기대: add_column 1줄, drop_column 1줄

# 7. dev_token smoke
python scripts/dev_token.py
# 기대: 성공적으로 토큰 발급
```

모두 통과 후:

- [ ] **Step 14.2: 최종 git log 확인**

```bash
cd ../..
git log --oneline -15
```

기대: 세션 1 커밋들이 순서대로 쌓여 있음.
```
<hash> docs(S27b): 핸드오프에 세션 1 완료 마커 추가
<hash> docs(S27b): SESSION_LOG 세션 1 엔트리 + 발견된 이슈 3건
<hash> feat(S27b): POST /auth/register/email + /auth/login/email 라우터
<hash> feat(S27b): AuthService.login_with_email — constant-time 로그인
<hash> feat(S27b): AuthService.register_with_email — 이메일 회원가입
<hash> feat(S27b): auth/service 헬퍼 — 해싱 + 예외 + _find_user_by_email
<hash> feat(S27b): EmailRegisterRequest/EmailLoginRequest Pydantic 스키마
<hash> test(S27b): 이메일 인증 엔드포인트 테스트 스위트 (RED)
<hash> feat(S27b): add password_hash alembic migration
<hash> feat(S27b): User 모델에 password_hash 컬럼 추가
<hash> chore(S27b): bcrypt + pydantic[email] 의존성 추가
<hash> docs(S27b): 세션 1 백엔드 설계 스펙 — 이메일+비밀번호 로그인
...
```

- [ ] **Step 14.3: 세션 1 완료 선언**

세션 1 완료. 다음 세션 (세션 2 모바일) 시작 시에는:
1. `docs/S27b-handoff.md` + `docs/SESSION_LOG.md` 의 S27b 세션 1 엔트리 로드
2. 핸드오프의 "세션 2 시작 시 Claude 에게 전달할 프롬프트" 사용
3. 세션 2 TDD 로드맵 (핸드오프 §"세션 2 TDD 로드맵") 진행

---

## 자체 리뷰 (skill 요구)

### 1. 스펙 커버리지

스펙 §3 포함 항목 → 플랜 Task 매핑:

| 스펙 항목 | 플랜 위치 |
|---|---|
| `pyproject.toml` 의존성 추가 | Task 1 |
| `User.password_hash` 컬럼 | Task 2 |
| alembic migration | Task 3 |
| `EmailRegisterRequest`/`EmailLoginRequest` | Task 5 |
| `EmailAlreadyExistsError` | Task 6 (Step 6.3) |
| `_hash_password` / `_verify_password` | Task 6 (Step 6.4) |
| `_get_dummy_hash` (`@functools.cache`) | Task 6 (Step 6.4) |
| `_find_user_by_email` + `_find_or_create_user` 리팩터링 | Task 6 (Step 6.5) |
| `register_with_email` (IntegrityError race 방어) | Task 7 |
| `login_with_email` (constant-time) | Task 8 |
| `POST /auth/register/email` + `POST /auth/login/email` 라우터 | Task 9 |
| 테스트 스위트 15-16 케이스 | Task 4 (RED) + Task 9 Step 9.3 (GREEN 확인) |

스펙 §5 테스트 계획 15 케이스 → 플랜의 16 케이스 (플랜이 `test_login_normalizes_email_case` 를 추가로 포함 — 스펙 §5 의 테이블에도 이미 있음).

스펙 §6 alembic migration 수동 편집 → 플랜 Task 3.

스펙 §7 완료 판정 → 플랜 Task 14.1.

**갭 없음.** ✅

### 2. Placeholder 스캔

플랜 내에서 다음 패턴 검색 (수동):
- TBD / TODO / FIXME / "implement later": ❌ 없음 (존재 위치는 모두 기존 코드의 TODO 주석 설명)
- "Add appropriate error handling": ❌ 없음
- "similar to Task N": ❌ 없음 (각 Task 는 완전한 코드 포함)
- 코드 없는 코드 변경 스텝: ❌ 없음

**통과.** ✅

### 3. 타입/시그니처 일관성

- `_hash_password(plain: str) -> str` — Task 6 (Step 6.4), Task 7 에서 사용 일치 ✅
- `_verify_password(plain: str, hashed: str) -> bool` — Task 6, Task 8 일치 ✅
- `_get_dummy_hash() -> str` — Task 6, Task 8 일치 ✅
- `_find_user_by_email(self, email: str) -> User | None` — Task 6 (Step 6.5), Task 7, Task 8 일치 ✅
- `register_with_email(self, email: str, password: str) -> AuthTokens` — Task 7, router Task 9 일치 ✅
- `login_with_email(self, email: str, password: str) -> AuthTokens` — Task 8, router Task 9 일치 ✅
- `EmailAlreadyExistsError` — Task 6 (Step 6.3), Task 7 (raise), Task 9 (catch) 일치 ✅
- `EMAIL_PROVIDER = "email"` — Task 6 (Step 6.2), Task 7 (사용) 일치 ✅
- `MAX_PASSWORD_BYTES = 72` — schemas.py (Task 5) + service.py (Task 6 Step 6.2) 동일 값 ✅
- `EmailRegisterRequest` / `EmailLoginRequest` — Task 5 정의, Task 9 import 일치 ✅

**통과.** ✅
