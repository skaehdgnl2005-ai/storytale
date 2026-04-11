# S27b 세션 1 — 이메일+비밀번호 로그인 (백엔드) 설계

> 작성일: 2026-04-11
> 트리거: S35b 실기기 수동 스모크 중 발견된 Critical 갭 — 모바일 `setAccessToken` 호출 경로 0건, S27 이 백엔드만 완료 마킹된 상태
> 범위: 백엔드 약 6 파일 — User 모델 컬럼 추가 + alembic migration + bcrypt 해싱 + `EmailRegisterRequest`/`EmailLoginRequest` 스키마 + `/auth/register/email`/`/auth/login/email` 엔드포인트 + TDD 테스트 스위트
> 핸드오프: [docs/S27b-handoff.md](../../S27b-handoff.md)
> 분할: 세션 1 (이 문서, 백엔드) / 세션 2 (모바일 — 별도 세션)

---

## 1. 배경

S35b (2026-04-11) 의 실기기 수동 스모크 중 Claude 가 다음을 발견:

- `packages/mobile/src/api/client.ts::setAccessToken` 함수는 export 되어 있으나 **호출 경로가 단 한 곳도 없음** (grep 결과 0건)
- 5개 화면에 `TODO(post-S27): 로그인 화면이 마련되면 navigation.replace("Login") 로 교체` 주석이 남아 있음
- S27 (인증) 은 **백엔드 소셜 로그인** 만 완료된 상태로 [완료] 마킹되었고, 모바일 UI / 토큰 부트스트랩 / setAccessToken 호출 경로가 전무했음

S27b 는 이 갭을 **이메일+비밀번호 최소 로그인** 으로 메운다. 소셜 OAuth (카카오/구글/애플 SDK + 앱스토어 심사 요구사항) 는 S27c 로 분리되어 출시 직전에 진행한다.

세션 1 은 **백엔드만** 다룬다 (파일 5개 이상 동시 수정 금지 원칙). 모바일은 세션 2.

---

## 2. 목적

세션 2 (모바일 LoginScreen + 토큰 부트스트랩) 진입 직전까지의 백엔드 인프라를 완성한다:

- `POST /auth/register/email` 엔드포인트 — 이메일/비번 회원가입 + JWT 발급
- `POST /auth/login/email` 엔드포인트 — 이메일/비번 로그인 + JWT 발급
- 기존 JWT 파이프라인(`AuthService.create_access_token` / `create_refresh_token` / `_issue_tokens`) 재사용
- 기존 `/auth/refresh`, `/auth/me`, `/auth/consent` 경로와 이메일 유저 간 완전 호환
- 기존 소셜 유저 (`provider` in `{google,kakao,apple}`) 와 하위 호환

---

## 3. 범위

### 포함 (세션 1)

- `packages/backend/pyproject.toml` — `bcrypt>=4.1,<5` 추가, `pydantic` → `pydantic[email]` extras 전환
- `packages/backend/src/storytale/db/models.py::User` — `password_hash = Column(String, nullable=True)` 추가
- `packages/backend/alembic/versions/{rev}_add_password_hash_to_users.py` — 신규 migration (수동 편집)
- `packages/backend/src/storytale/auth/schemas.py` — `EmailRegisterRequest`, `EmailLoginRequest` 추가
- `packages/backend/src/storytale/auth/service.py`:
  - `EmailAlreadyExistsError` 예외 클래스 (모듈 수준)
  - `_hash_password(plain) -> str` / `_verify_password(plain, hashed) -> bool` 헬퍼
  - `_get_dummy_hash() -> str` — `@functools.cache` lazy init (constant-time login 용)
  - `_find_user_by_email(email) -> User | None` — 신규 헬퍼
  - `_find_or_create_user` 리팩터링 — `_find_user_by_email` 재사용
  - `register_with_email(email, password) -> AuthTokens` — 회원가입 + IntegrityError catch
  - `login_with_email(email, password) -> AuthTokens` — constant-time login 패턴
- `packages/backend/src/storytale/api/auth_router.py`:
  - `@router.post("/register/email", response_model=AuthTokens)` 엔드포인트
  - `@router.post("/login/email", response_model=AuthTokens)` 엔드포인트
  - 기존 엔드포인트 건드리지 않음
- `packages/backend/tests/test_s27b_email_auth.py` — 신규 TDD 테스트 스위트 (약 15 케이스)

**파일 수**: 6 (테스트 파일은 CLAUDE.md "파일 5개 이상 동시 수정 금지" 카운트에서 관례적으로 별도)

### 제외 (세션 1 범위 밖)

- 모바일 LoginScreen, tokenStore, bootstrap, 5개 화면 401 감지 — **세션 2**
- `/auth/login` (social) 의 `except Exception → 500` 버그 — 🚨 기록만, 수정 안 함
- `/auth/logout` 의 no-op 버그 + router-service 계층 간 토큰 타입 가정 불일치 — 🚨 S27d 제안
- 기존 social 유저 이메일 데이터 case 백필 마이그레이션 — S38 배포 전 별도 스크립트
- DB 레벨 case-insensitive unique index — S27c 또는 별도 hardening
- 비밀번호 변경 시 refresh token 일괄 무효화 메커니즘 — 비번 변경 기능 도입 시
- `api-conventions.md` ↔ 실제 구현 드리프트 문서 동기화 — 별도 태스크
- 카카오/구글/애플 OAuth SDK 통합 — S27c
- 비밀번호 리셋 / 이메일 인증 링크 / 2FA — MVP 범위 초과

---

## 4. 설계 결정 (Q1~Q7)

### Q1. 비밀번호 해싱 라이브러리 — `bcrypt` 직접

**결정**: `bcrypt>=4.1,<5` 를 `pyproject.toml` 에 추가. `passlib` / `argon2-cffi` 미채택.

**근거**:
1. `passlib` 는 2020-10 이후 사실상 유지보수 중단 (bcrypt 4.x 호환성 경고)
2. `argon2-cffi` 는 메모리-hard 해서 더 안전하나 MVP 에 과투자 + 핸드오프가 이미 `BCRYPT_ROUNDS` 환경변수를 전제
3. MVP 에 multiple-algorithm 추상화 (passlib `CryptContext`) 는 YAGNI — 현재 알고리즘 1개

**구현**:

```python
# auth/service.py 모듈 수준
import bcrypt
import functools
import os

MAX_PASSWORD_BYTES = 72  # bcrypt null-terminated 입력 제한


def _hash_password(plain: str) -> str:
    # BCRYPT_ROUNDS 를 매 호출마다 읽어 테스트 monkeypatch 호환
    rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=rounds),
    ).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


@functools.cache
def _get_dummy_hash() -> str:
    """Constant-time login 용 dummy hash. 프로세스 lifetime 내 1회만 계산.

    공격자가 존재하지 않는 이메일로 로그인 스팸할 때 매 요청마다 bcrypt.hashpw 를
    실행하면 prod 라운드 12 기준 ~250ms × 요청 수로 CPU 가 포화된다. 캐시로 첫
    로그인 시점에 1회만 계산 후 프로세스 종료까지 고정.
    """
    return _hash_password("constant-time-login-dummy-value")
```

**BCRYPT_ROUNDS 정책**: dev=4 (~10ms), prod=12 (~250ms). 환경변수 미설정 시 기본값 12 (안전한 default).

**72바이트 제한**:
- **Register**: Pydantic `@field_validator("password")` 에서 `len(v.encode("utf-8")) > MAX_PASSWORD_BYTES` 검증 → 422
- **Login**: early check 없음. bcrypt 가 silent truncate 하므로 긴 비번은 어차피 기존 해시와 매칭 실패 → 401

---

### Q2. 이메일 중복 에러 응답 envelope

**결정**: `409 Conflict` + inner code `"EMAIL_ALREADY_EXISTS"` + 부모 톤 메시지.

**wire 형식**:
```json
{
  "error": {
    "code": 409,
    "message": {
      "message": "이미 가입된 이메일이에요 😊",
      "code": "EMAIL_ALREADY_EXISTS"
    }
  }
}
```

**필드 순서**: inner dict 는 `{"message": ..., "code": ...}` 순서로 stories/router.py:677 의 `REJECTED_INTENT` 패턴과 일치시켜 grep/검색 consistency 유지.

**모바일 영향**: `parseErrorBody` (client.ts:45-) 가 이미 이 형식을 파싱. 세션 2 에서 `ApiClientError.code === "EMAIL_ALREADY_EXISTS"` 로 분기만 하면 됨.

**이메일 enumeration 취약점 (register 에서 409 반환) 수용 근거**:
- 이메일 인프라 없음 (가입 확인 이메일 발송 불가)
- 아이 서비스 타겟이 스팸 enumeration 공격 대상이 아님
- 법정대리인 동의 단계(S27) 가 2차 확인 역할

---

### Q3. 비밀번호 정책

**결정표**:

| 규칙 | 값 | 구현 위치 |
|---|---|---|
| 최소 길이 | 8자 (문자 단위) | Pydantic `Field(min_length=8)` → 자동 422 |
| 최대 길이 | 72 바이트 (UTF-8) | `@field_validator` 수동 → 422 |
| 복잡도 | **없음** | — |
| 금지어 | **없음** | — |
| 공백 처리 | **변환 없음** (strip/trim 하지 않음) | — |

**근거**: NIST SP 800-63B 관례 (복잡도 규칙은 예측 가능한 패턴을 유도) + 구현 단순성 + MVP 범위.

**`register_with_email` 시그니처**: `(email, password)` 만. **`name` 파라미터 제거** (핸드오프의 `name` 언급은 추측).

- 현재 `User` 모델에 `name` 필드 없음
- `SocialUserInfo` 도 `email + provider` 만 보유 → 소셜/로컬 일관성 유지
- 부모 이름은 서비스 어디에서도 렌더링에 사용 안 됨 (개인화는 아이 이름)

**Login 실패 메시지 통일**: 다음 3가지 모두 **동일한 401** + `"이메일 또는 비밀번호가 올바르지 않아요"` (inner code 없음):
1. 존재하지 않는 이메일
2. 존재하지만 비번 틀림
3. 소셜 전용 유저 (`password_hash IS NULL`) 로 이메일 로그인 시도

---

### Q4. 이메일 형식 검증 — Pydantic `EmailStr`

**결정**: `pyproject.toml` 에 `pydantic[email]>=2.0,<3` 로 전환. `email-validator` 패키지가 자동 pull 됨.

**근거**:
1. 정규식 이메일 검증은 업계 악몽 (RFC 5322 정확 구현 = 6000+ 자 정규식)
2. `EmailStr` 은 RFC 5322/5321 + IDN + Punycode 자동 처리
3. `email-validator` 는 순수 Python + `idna` 만 의존 (~100KB)
4. 한글 도메인 (`홍길동@도메인.한국`) 자동 지원

**정규화 정책**:

```python
# EmailStr 은 도메인만 자동 정규화 (lowercase + Punycode). 로컬파트까지 통일하여
# "User@example.com" ≠ "user@example.com" 같은 중복 가입을 방지.
normalized_email = email.lower()
```

**Pre-validator (strip)**:

```python
class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def _strip_email(cls, v: str) -> str:
        # 모바일 복붙 시 앞뒤 공백 흡수. mode="before" 가 핵심 — EmailStr 검증
        # 전에 먼저 실행되어야 효과가 있음.
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
    email: EmailStr
    password: str  # login 은 길이 검증 없음 — 정책 변경 시 과거 사용자 로그인 회귀 방지

    @field_validator("email", mode="before")
    @classmethod
    def _strip_email(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v
```

**기존 social 경로 email 정규화**: 세션 1 범위 밖. `_find_or_create_user` 가 소셜 프로바이더 반환값을 그대로 비교하는 현재 동작 유지. SESSION_LOG "S38 배포 전 체크리스트" 로 기록.

---

### Q5. 교차 로그인 정책 & 하위 호환 (보안 엄격)

**시나리오별 응답**:

| # | 시나리오 | 백엔드 동작 | 응답 |
|---|---|---|---|
| a | social 전용 유저 (`password_hash=NULL`) 가 `/auth/login/email` 시도 | `_find_user_by_email` → user 찾음, password_hash 는 NULL → `_get_dummy_hash()` 로 대체 → verify false | **401** `"이메일 또는 비밀번호가 올바르지 않아요"` |
| b | email 유저 (`password_hash=bcrypt`) 가 `/auth/login` (social) 시도 | 기존 `_find_or_create_user` 가 이메일 매치로 기존 email 유저 반환 → JWT 발급 | **200** + tokens |
| c | social 유저가 `/auth/register/email` 재가입 | `_find_user_by_email` → user 존재 → `EmailAlreadyExistsError` | **409** + `EMAIL_ALREADY_EXISTS` |
| d | email 유저가 `/auth/register/email` 재가입 | 동일 | **409** + `EMAIL_ALREADY_EXISTS` |

**시나리오 (a) 의 constant-time 보장**:

```python
async def login_with_email(self, email: str, password: str) -> AuthTokens:
    normalized_email = email.lower()
    user = await self._find_user_by_email(normalized_email)
    stored_hash = (
        user.password_hash if (user and user.password_hash) else _get_dummy_hash()
    )
    is_valid = _verify_password(password, stored_hash)
    if not (user and user.password_hash and is_valid):
        raise ValueError("이메일 또는 비밀번호가 올바르지 않아요")
    return self._issue_tokens(str(user.id))
```

**타이밍 분석**:
- 존재 안 하는 이메일: `SELECT` (~5ms) + `bcrypt verify against dummy` (~250ms) = **~255ms**
- 비번 틀림: `SELECT` + `bcrypt verify against real hash` = **~255ms**
- 소셜 전용 유저: `SELECT` + `bcrypt verify against dummy` = **~255ms**
- **세 케이스 동일 타이밍** ✅

**시나리오 (b) OIDC 암묵적 연결 근거**:
- OAuth 제공자 = 이메일 소유권 증명 (OIDC 스펙 명시)
- 공격 벡터 분석: "공격자가 희생자 이메일로 email 가입 → 희생자가 Google 소셜 로그인" 시나리오에서 공격자는 희생자 Google 계정 비번/2FA 를 통과하지 못하므로 계정 탈취 불가
- 기존 S27 `_find_or_create_user` 동작을 바꾸면 회귀 위험

**소셜 판정 로직**: `user.password_hash IS NULL` (not `provider != "email"`).
- 미래 확장성: 소셜 유저가 비번을 추가 설정하는 기능 가능성 허용
- `provider` 필드는 **최초 가입 경로 historical marker** 이며 소셜/로컬 분기에 **사용 금지**

**`password_hash` 컬럼 정의**:

```python
password_hash = Column(String, nullable=True)
```

- 소셜 유저는 NULL 유지 (하위 호환)
- 길이 제한 없는 `String` — 미래 해시 알고리즘 전환 대응

**`_find_user_by_email` 헬퍼 + `_find_or_create_user` 리팩터링**:

```python
async def _find_user_by_email(self, email: str) -> User | None:
    """이메일로 사용자 조회. 없으면 None.

    호출자는 이 메서드를 호출하기 전에 email 을 정규화(소문자화) 해야 한다.
    """
    stmt = select(User).where(User.email == email)
    result = await self.db.execute(stmt)
    return result.scalar_one_or_none()


async def _find_or_create_user(self, user_info: SocialUserInfo) -> User:
    user = await self._find_user_by_email(user_info.email)  # 헬퍼 재사용
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

**`register_with_email` — race condition 해결 (옵션 1: rollback 후 재확인)**:

```python
async def register_with_email(self, email: str, password: str) -> AuthTokens:
    normalized_email = email.lower()
    existing = await self._find_user_by_email(normalized_email)
    if existing is not None:
        raise EmailAlreadyExistsError()
    try:
        user = User(
            id=uuid.uuid4(),
            email=normalized_email,
            provider="email",
            password_hash=_hash_password(password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
    except IntegrityError as e:
        await self.db.rollback()
        # 교과서적 race condition 해결: rollback 후 재확인으로 IntegrityError 의
        # 실제 원인이 "이메일 중복" 인지 검증. 다른 원인(NOT NULL/FK/Check)이면
        # 그대로 500 으로 전파하여 디버깅 단서 보존.
        existing = await self._find_user_by_email(normalized_email)
        if existing is not None:
            raise EmailAlreadyExistsError() from e
        raise
    return self._issue_tokens(str(user.id))
```

**`EmailAlreadyExistsError` 위치**: `auth/service.py` 모듈 수준. 선례: `interpreter/intent_analyzer.py:50::RejectedIntentError`.

```python
class EmailAlreadyExistsError(Exception):
    """이메일이 이미 존재하는 경우. 라우터에서 409 로 변환."""
```

---

### Q6. API 경로 네이밍 — 옵션 A

**결정**:
- `POST /auth/register/email` → 200 OK + `AuthTokens`
- `POST /auth/login/email` → 200 OK + `AuthTokens`

**근거**:
1. 기존 `/auth/login` (social) 과 **액션 하위 variant(채널)** 구조로 일관 + 확장 여지 (`/auth/login/google` 등)
2. 옵션 B (signup/signin) 기각: `/auth/login` 과 의미 중복 용어
3. 옵션 C (`/auth/email/register`) 기각: `/auth/email` 이 애매한 리소스로 오해 여지

**200 OK 선택 근거 (정정)**: auth 엔드포인트 family 는 REST '리소스 CRUD' 관점이 아니라 **'세션 수립' 관점** 에서 설계됨. 기존 `/auth/login` (200 OK) 과 일관. 업계 관례 (Auth0/Firebase/Supabase) 도 register/login 양쪽 200.

**에러 매핑**:

| 케이스 | 경로 | HTTP | inner code | 처리 위치 |
|---|---|---|---|---|
| 이메일 형식 오류 | register/login | 422 | (Pydantic 기본) | Pydantic EmailStr |
| 비번 `min_length < 8` | register | 422 | (Pydantic 기본) | Pydantic Field |
| 비번 72바이트 초과 | register | 422 | (custom ValueError) | `@field_validator` |
| 이메일 중복 | register | 409 | `EMAIL_ALREADY_EXISTS` | auth_router catch |
| 로그인 실패 (전부) | login | 401 | 없음 (string) | service ValueError catch |

**라우터 코드**:

```python
# auth_router.py 추가 (기존 엔드포인트 건드리지 않음)

@router.post("/register/email", response_model=AuthTokens)
async def register_email(
    body: EmailRegisterRequest,
    auth_service: AuthServiceDep,
) -> AuthTokens:
    try:
        return await auth_service.register_with_email(
            email=body.email,
            password=body.password,
        )
    except EmailAlreadyExistsError as exc:
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
    try:
        return await auth_service.login_with_email(
            email=body.email,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
```

**`/auth/refresh` 패턴 채택** (`except ValueError → 401`). 기존 `/auth/login` (social) 의 `except Exception → 500` 패턴은 **의도적으로 복제하지 않음** (Q7 섹션의 발견된 이슈 참조).

---

### Q7. refresh token 발급 여부 — 발급 유지 (신규 코드 0줄)

**결정**: Register/login 둘 다 `AuthService._issue_tokens` 를 그대로 호출하여 access + refresh 쌍 발급.

**정합성 검증** (코드 인용):
- `schemas.py:21-26` `AuthTokens.refresh_token: str` **필수 필드** — Optional 변경은 S27 회귀
- `service.py:212-218` `_issue_tokens` 가 access+refresh 쌍 발급 — register/login 이 이 메서드만 호출하면 자동 포함
- `service.py:224-235` `refresh_token` 메서드는 `sub` 와 `type="refresh"` 만 확인, 가입 경로 정보 0% 참조 — 이메일 유저의 refresh token 도 동일 처리

**만료 정책**: 기존 유지 (access 24h / refresh 7d). 이메일이라고 단축할 이유 없음.

**블랙리스트 연동**: 자동 (`_blacklist.contains` 기존 로직 그대로).

---

## 5. 테스트 계획 (TDD RED)

**파일**: `packages/backend/tests/test_s27b_email_auth.py`

**공유 픽스처** (기존 `test_s27_auth_api.py` 패턴 차용):
- `client`: `httpx AsyncClient(transport=ASGITransport(app=app))`
- `db_session`: `TestingSessionLocal()`

**테스트 케이스** (약 15개, RED → GREEN 순):

| # | 클래스 | 테스트 | 기대 |
|---|---|---|---|
| 1 | `TestRegisterEmail` | `test_register_returns_tokens` | 200 + `{access_token, refresh_token, expires_in}` |
| 2 | | `test_register_creates_user_with_email_provider` | DB 에 `provider="email"`, `password_hash` non-null |
| 3 | | `test_register_normalizes_email_case` | `"Foo@Example.COM"` 입력 → DB 저장 `"foo@example.com"` |
| 4 | | `test_register_strips_whitespace` | `" foo@example.com "` 입력 → 정상 처리 |
| 5 | | `test_register_duplicate_email_returns_409` | 같은 이메일 2번 → 두 번째 409 + inner `EMAIL_ALREADY_EXISTS` |
| 6 | | `test_register_invalid_email_returns_422` | `"not-an-email"` → 422 |
| 7 | | `test_register_short_password_returns_422` | `"short"` (5자) → 422 |
| 8 | | `test_register_overlong_password_returns_422` | 한글 25자 (75바이트) → 422 |
| 9 | `TestLoginEmail` | `test_login_with_correct_password_returns_tokens` | 200 + tokens |
| 10 | | `test_login_with_wrong_password_returns_401` | 401 |
| 11 | | `test_login_with_unknown_email_returns_401` | 401 (enum 방지) |
| 12 | | `test_login_with_social_only_user_returns_401` | 401 (password_hash IS NULL) |
| 13 | | `test_login_with_overlong_password_returns_401` | 긴 비번 → 401 (bcrypt truncate 회귀 보호) |
| 14 | | `test_login_normalizes_email_case` | 대소문자 다르게 입력해도 로그인 성공 |
| 15 | `TestMeEndpointWithEmailUser` | `test_me_returns_email_user_info` | 기존 `/auth/me` 가 email 유저에게도 동작 — `{user_id, email, provider: "email", consent_given: false}` |

**회귀 테스트**: 다음 스위트 전체 통과 필요
- `tests/test_s27_auth_api.py` — 기존 소셜 로그인/refresh/logout/consent/me
- `tests/test_s35b_frontend_contract_e2e.py` — 프론트-백 contract E2E 8 케이스
- `tests/test_s30a_plan_endpoint.py`, `test_s31a_plan_revise_endpoint.py`, `test_s34_story_delete_endpoint.py`, `test_s35a_text_illustration_e2e.py` — 인증 의존성을 쓰는 기존 테스트

**Constant-time login 타이밍 검증은 유닛 테스트 범위 밖** — 정확한 타이밍 측정은 noise 에 민감하여 flaky 테스트 유발. 대신 코드 리뷰 + 구조 검증으로 보장.

---

## 6. alembic Migration 주의사항

핸드오프 2번 항목에서 이미 경고된 사항:

> 기존 alembic migration 이 JSONB 로 SQLite 에서 깨지므로 **autogenerate 가 모든 테이블 diff 를 잡을 수 있음**. 새 migration 파일에 `add_column` 하나만 남기도록 **수동 편집** 필수.

**구현 단계 체크리스트**:
1. `alembic revision --autogenerate -m "add password_hash to users"` 실행
2. 생성된 파일 열어서 `upgrade()` 에 `op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))` 외 모든 라인 삭제
3. `downgrade()` 에 `op.drop_column("users", "password_hash")` 만 남기기
4. down_revision 체인 확인: `a1b2c3d4e5f6` (consent_given_at 추가) 를 가리켜야 함

**conftest.py 영향**: 없음. `conftest.py` 는 `Base.metadata.create_all` 로 SQLite 테이블 생성 — alembic migration 파일 자체는 테스트 런타임에 실행되지 않음. `User.password_hash` 컬럼 추가가 `Base.metadata` 에 자동 반영되므로 테스트 DB 에도 자동 포함.

**`dev_token.py` 호환성**: `dev_token.py` 는 `password_hash=None` 으로 User 생성 → `nullable=True` 이므로 여전히 동작. 세션 1 완료 후 `python scripts/dev_token.py` 로 smoke 확인 필요.

---

## 7. 완료 판정

- [ ] `pytest tests/test_s27b_email_auth.py` 전 케이스 통과 (약 15개)
- [ ] `pytest tests/test_s27_auth_api.py tests/test_s35b_frontend_contract_e2e.py` 회귀 0건
- [ ] `pytest tests/test_s30a_plan_endpoint.py tests/test_s31a_plan_revise_endpoint.py tests/test_s34_story_delete_endpoint.py tests/test_s35a_text_illustration_e2e.py` 회귀 0건
- [ ] `ruff check src tests` 통과
- [ ] `ruff format src tests` 통과 (변경사항 0 이어야 함)
- [ ] 수동 편집된 alembic migration 파일에 `add_column` 하나만 남음을 diff 로 확인
- [ ] `dev_token.py` smoke 통과 (`python scripts/dev_token.py` 가 새 컬럼 환경에서 여전히 토큰 발급)
- [ ] SESSION_LOG 에 S27b 세션 1 엔트리 작성 — "구현 요약" + "다음 세션에 알려줄 것" + "발견된 이슈"

---

## 8. 발견된 이슈 (세션 1 범위 밖)

### 🚨 `/auth/logout` no-op 버그 (보안 영향 대) — S27d 제안

**현상** (`auth_router.py:102-115`):

```python
try:
    auth_service.decode_token(credentials.credentials)   # ← 디코드만
except ValueError as e:
    raise HTTPException(status_code=401, detail=str(e)) from None
return {"message": "로그아웃 되었습니다"}   # ← 거짓말
```

- `auth_service.logout(...)` 호출이 **실제로 없음**
- 블랙리스트에 토큰이 추가되지 않음 → refresh token 이 여전히 유효 → 로그아웃 후에도 `/auth/refresh` 로 새 access token 발급 가능
- 응답 `"로그아웃 되었습니다"` 는 거짓 claim

**추가 발견 — 계약 불일치**:
- `AuthService.logout(refresh_token: str)` (service.py:241) 는 **refresh_token 을 인자로 받음**
- 하지만 router 는 `credentials.credentials` (= Bearer 헤더 = access token) 을 디코드함
- 두 계층의 **토큰 타입 가정이 불일치** → 수정은 설계 재검토 필요 (router 가 refresh_token 을 body 로 받을지, access token 의 jti 를 블랙리스트 키로 쓸지 결정 필요)

**왜 세션 1 범위 밖인가**:
- 파일 예산 (auth_router.py 수정 범위 확대)
- TDD granularity (logout 버그 수정은 별도 테스트 + 기존 `test_logout_success` 가 버그를 놓친 이유 분석 필요)
- 설계 재검토 필요 (위 계약 불일치)

**권장 조치**: **S27d** 제안 ID 로 별도 hardening 태스크. 세션 2 모바일 작업은 원래 계획에 능동 로그아웃 UI 가 없으므로 세션 2 진행에는 영향 없음.

### `/auth/login` (social) `except Exception → 500` 버그 (중간)

**현상** (`auth_router.py:66-77`):

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e)) from e
```

`SocialAuthError` / `ValueError` 모두 500 으로 변환. `/auth/refresh` 가 동일 상황에서 401 로 올바르게 처리하는 것과 비일관.

**왜 세션 1 범위 밖인가**:
- 기능은 동작 (에러 코드만 이상)
- 수정 시 `test_s27_auth_api.py` 의 기존 `test_login_invalid_provider` 등과 회귀 충돌 가능
- `/auth/logout` 버그와 묶어서 S27d 에서 함께 수정이 효율적

**S27b 에서 취하는 행동**: 신규 엔드포인트는 `/auth/refresh` 패턴 (`except ValueError → 401`) 을 따름. 기존 `/auth/login` 의 버그 패턴은 **의도적으로 복제하지 않음**.

### `api-conventions.md` 문서-구현 드리프트 (낮음)

`.claude/rules/api-conventions.md` 는 `{detail: "메시지", code: "ERROR_CODE"}` 로 명시하지만 실제 구현은 FastAPI HTTPException 제약 때문에 `{detail: {message, code}}` nested 구조. 별도 문서 동기화 태스크 필요.

### 기존 social 유저 이메일 case 정규화 (낮음)

소셜 프로바이더 (특히 Apple) 가 이메일을 원본 case 로 반환할 수 있음. 프로덕션 DB 배포 시점에 `UPDATE users SET email = LOWER(email)` 또는 동등한 스크립트 필요. unique 제약 충돌 시 수동 정리.

**S38 배포 전 체크리스트**: `scripts/s38_pre_deploy_normalize_emails.py` 작성 (dry-run + 충돌 감지 로그 + 수동 해소 경로 포함).

### 비밀번호 변경 시 refresh token 일괄 무효화 (미래)

현재 `_blacklist` 는 개별 토큰 키 기반이라 user-wide 무효화 지원 안 됨. 비번 변경 기능 도입 시 설계 후보:
- `User.token_version` 필드 + JWT payload 에 version 포함 (O(1) 검증, DB 조회 필요)
- user-wide Redis 블랙리스트 키 패턴 (`blacklist:user:{user_id}:issued_before_{ts}`)
- Refresh token 개별 관리 테이블 (User ↔ RefreshToken 1:N)

S27b 범위 완전 외. 비번 변경 기능 설계 시 결정.

### DB 레벨 case-insensitive unique index (낮음)

현재 서비스 계층에서 `email.lower()` 로 방어. admin 스크립트나 ORM bypass 쿼리는 뚫림. 궁극적 방어는 Postgres `CREATE UNIQUE INDEX ... ON users (LOWER(email))` 또는 `citext` 컬럼 변경. S27c 또는 별도 hardening 태스크.

---

## 9. 세션 2 예고 (참고용)

본 문서의 범위는 아니지만 세션 1 결정이 세션 2 에 직접 영향을 주므로 간단히 기록:

- `src/screens/LoginScreen.tsx` 신규 — 이메일/비번 입력 + 회원가입 ↔ 로그인 토글 + 에러 배너
- `src/api/client.ts` 확장 또는 `src/storage/tokenStore.ts` 신규 — AsyncStorage wrapper + `loginWithEmail`/`registerWithEmail`
- `src/navigation/AppNavigator.tsx` — Login 라우트 + 조건부 초기 라우트
- `src/auth/bootstrap.tsx` 또는 `App.tsx` — 앱 시작 시 토큰 로드 → `setAccessToken` → `GET /auth/me` 검증 → Home 또는 Login
- 5개 화면 `TODO(post-S27)` → `navigation.replace("Login")` 교체 (401 감지 시)
- `packages/backend/scripts/dev_token.py` 삭제 + `packages/mobile/src/api/client.ts` 임시 토큰 하드코딩 제거

**세션 2 에 능동 로그아웃 UI 는 포함되지 않음** (핸드오프 세션 2 TDD 로드맵 확인). S27d (`/auth/logout` 버그 수정) 이후 별도 UI 태스크에서 추가.

---

## 10. 참조

- 핸드오프: [docs/S27b-handoff.md](../../S27b-handoff.md)
- 핵심 소스:
  - `packages/backend/src/storytale/api/auth_router.py` — 기존 소셜 로그인 라우터
  - `packages/backend/src/storytale/auth/service.py::AuthService` — JWT 파이프라인
  - `packages/backend/src/storytale/auth/schemas.py` — 기존 `SocialLoginRequest`, `AuthTokens`
  - `packages/backend/src/storytale/db/models.py::User` — User 모델
  - `packages/backend/tests/test_s27_auth_api.py` — 기존 auth 테스트 패턴
- 관련 규칙:
  - `.claude/rules/testing.md` — TDD 필수
  - `.claude/rules/code-style.md` — Python 3.12+, Pydantic v2, async/await
  - `.claude/rules/security.md` — JWT 만료, 본인 리소스만 접근, 아동 데이터 보호
  - `.claude/rules/api-conventions.md` — REST 패턴 (문서-구현 드리프트 있음, 위 참조)
- 기존 inner code 패턴 선례: `packages/backend/src/storytale/api/stories/router.py:673-678` (REJECTED_INTENT)
- 기존 예외 클래스 선례: `packages/backend/src/storytale/interpreter/intent_analyzer.py:50` (RejectedIntentError)
