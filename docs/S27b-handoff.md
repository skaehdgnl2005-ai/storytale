# S27b — 이메일+비밀번호 로그인 핸드오프 브리프

**작성일**: 2026-04-11 (S35b 수동 스모크 중 S27 누락 발견 직후)
**목적**: 다음 세션에서 S27b 를 시작하는 Claude 가 컨텍스트를 빠르게 로드할 수 있도록.
**수명**: S27b 세션 1/2 완료 직후 **삭제 권장**. 이 파일 자체가 일회성 브리프.

---

## TL;DR

> **2026-04-11 업데이트**: 세션 1 (백엔드) 완료. 세션 2 (모바일) 만 남음. SESSION_LOG S27b 엔트리 참조.

S27 (인증) 은 백엔드 소셜 로그인까지만 완료되었고, **모바일에 로그인 UI / 토큰 부트스트랩 / setAccessToken 호출 경로가 전무**. 그래서 모바일 앱은 JWT 가 항상 null 인 채로 동작하고 모든 API 가 401 을 받는다. S27b 는 그 갭을 이메일+비밀번호 최소 로그인 화면으로 메운다. 소셜 OAuth 는 S27c (출시 직전) 로 분리.

## 배경 — 어떻게 갭이 드러났는가

1. **2026-04-11 S35b 작업 완료** — backend contract E2E 8 케이스 + 라우터 보안 균열(`/jobs/{job_id}` 폴링 인증 누락) 수정 + 74/74 회귀 통과.
2. **S35b 실기기 수동 스모크 시도** — 사용자가 폰 Expo Go 로 앱 열기 → Expo 번들러 에러(monorepo cwd 문제) → `cd packages/mobile && npx expo start --clear` 로 해결 → 앱 Home 화면 진입 → "뭘 테스트해야 할지 모르겠다" → Claude 가 화면 구조 탐색 중 **발견**:
   - `packages/mobile/src/api/client.ts::setAccessToken` 함수는 export 되어 있으나 **호출 경로가 단 하나도 없음** (grep 결과 0건)
   - 5개 화면(`DescriptiveInputScreen.tsx:173`, `GenerationScreen.tsx:114`, `PreviewScreen.tsx:104`, `LibraryScreen.tsx:111`, `ViewerScreen.tsx:78`) 에 `TODO(post-S27): 로그인 화면이 마련되면 navigation.replace("Login") 로 교체` 주석
   - 즉 S27 은 **백엔드만** 완료된 상태로 [완료] 마킹된 것이었음
3. **임시 해결책** — `packages/backend/scripts/dev_token.py` (S35b 작업 중 생성) 로 dev 유저 + JWT 생성 → `client.ts` 한 줄 하드코딩 → 수동 스모크 진행. S27b 완료 후 삭제 예정.
4. **리뷰어 경고 재검증** — 브레인스토밍 시 리뷰어가 "httpx contract E2E 는 상태 관리 꼬임을 못 잡는다"고 지적했는데, 실제로 이 갭은 "상태 관리 층의 누락" 이었음. contract E2E 가 아니라 **수동 스모크가 정확히 잡아냄**. 수동 스모크를 의무화한 판단이 결과적으로 정답.

## 범위 결정 (브레인스토밍 이전에 확정된 것)

**(최소 로그인 화면)** — 이메일+비밀번호 한 쌍만.

**왜 소셜 OAuth 가 아닌가** (2026-04-11 사용자 결정):
- 카카오/구글/애플 SDK 연동 + 개발자 앱 등록 + URL 스킴 + 리다이렉트 URL 구성은 **앱스토어 심사 직전** 에 필요한 요구사항
- 개발 중엔 이메일/비번 하나로 dev 테스트 + G4.5 수동 리뷰 + S38 내부 테스트까지 전부 충분
- 소셜 OAuth 전체 묶음은 별도 태스크 **S27c** 로 분리 (백로그 등재는 S27b 완료 후)

**세션 분할** (CLAUDE.md "파일 5개 이상 동시 수정 금지" 준수):

| 세션 | 범위 | 파일 수 |
|---|---|---|
| **세션 1** | 백엔드 전체 | 약 6 |
| **세션 2** | 모바일 전체 + 5개 화면 TODO 주석 정리 | 약 5 |

## 세션 1 진입 시 필수 읽기

1. **`docs/TASK_BACKLOG.md::S27b`** — 이 태스크의 전체 스펙 (산출물 파일 목록 포함)
2. **`docs/SESSION_LOG.md`** 최상단 S35b 엔트리 — 갭 발견 맥락 + `dev_token.py` 임시 해결책 + 실기기 스모크 결과
3. **`packages/backend/src/storytale/api/auth_router.py`** — 기존 소셜 로그인 라우터. JWT 파이프라인 재사용 지점: `AuthServiceDep`, `CurrentUserDep`, `get_current_user_id`
4. **`packages/backend/src/storytale/auth/service.py::AuthService`** — `create_access_token`/`create_refresh_token` 그대로 사용. 새로 추가할 메서드: `register_with_email(email, password, name)`, `login_with_email(email, password)`
5. **`packages/backend/src/storytale/auth/schemas.py`** — 기존 `SocialLoginRequest`, `AuthTokens` 패턴 참고하여 `EmailRegisterRequest`/`EmailLoginRequest` 추가
6. **`packages/backend/src/storytale/db/models.py::User`** — `password_hash: Column(String, nullable=True)` 추가. 소셜 유저는 null 유지(하위 호환)
7. **`packages/backend/tests/test_s27_auth_api.py`** — 기존 auth 테스트 패턴 (httpx AsyncClient + social login mock 우회 패턴). 새 테스트는 이 패턴 차용

## 설계 결정 먼저 필요한 것들 (브레인스토밍 아이템 — 세션 1 시작 직전)

1. **비밀번호 해싱 라이브러리 선택**
   - 옵션: `passlib[bcrypt]` / `bcrypt` 직접 / `argon2-cffi`
   - 기존 의존성에 이미 설치된 것 있는지 확인: `pyproject.toml` grep
   - 환경변수 `BCRYPT_ROUNDS` 로 dev(4) / prod(12) 분기

2. **이메일 중복 응답 형식**
   - 409 Conflict + mobile `parseErrorBody` 호환 envelope: `{error: {code: 409, message: {code: "EMAIL_ALREADY_EXISTS", message: "..."}}}`
   - 기존 `REJECTED_INTENT` inner code 패턴 재사용 (S30a 에서 도입된 패턴)

3. **비밀번호 정책**
   - MVP: 최소 8자만. 복잡도 규칙(대소문자/숫자/특수문자) 은 과투자.
   - 근거: 아이용 서비스라 부모가 쓰기 쉬워야 함 + 이메일 로그인은 어차피 개발 중 임시 수단

4. **이메일 형식 검증**
   - Pydantic `EmailStr` 사용 → `email-validator` 패키지 의존성 확인 필요
   - 대안: 정규식 직접. `EmailStr` 권장.

5. **기존 social 유저 하위 호환**
   - `password_hash` nullable
   - social 유저가 이메일 로그인으로 재접속 시도 → "소셜 계정으로 가입된 이메일입니다" 에러
   - 반대로 email 유저가 `/auth/login` (social) 시도 → 기존 경로가 `_find_or_create_user` 로 새 social 레코드 만들 수 있으므로 주의. 이메일 unique 제약이 있으므로 충돌 방지됨.

6. **API 경로 네이밍**
   - 옵션 A: `/auth/register/email` + `/auth/login/email` (명시적 중첩)
   - 옵션 B: `/auth/signup` + `/auth/signin` (관습적)
   - 옵션 C: `/auth/email/register` + `/auth/email/login` (prefix 그룹핑)
   - **추천**: 옵션 A. 기존 `/auth/login` (social) 과 일관성 + 향후 `/auth/login/google` 같은 확장 여지.

7. **refresh token 발급 여부**
   - 이메일 로그인도 refresh token 동일하게 발급 (`AuthService._issue_tokens` 재사용)
   - `/auth/refresh` 는 토큰 타입 무관하게 동작하므로 변경 없음

## 세션 1 TDD 로드맵

1. **RED**: `tests/test_s27b_email_auth.py` 작성 (예상 ~10 케이스)
   - happy path: `POST /auth/register/email` → 200 + tokens → `POST /auth/login/email` → 200 + tokens → `GET /auth/me` → 이메일 확인
   - 중복 이메일: `POST /auth/register/email` 같은 이메일 두 번 → 두 번째 409 + inner code
   - 잘못된 비번: `POST /auth/login/email` 잘못된 비번 → 401
   - 존재하지 않는 이메일: `POST /auth/login/email` → 401 (비번 잘못과 동일 응답, 이메일 존재 여부 노출 방지)
   - 비번 너무 짧음: 422
   - 잘못된 이메일 형식: 422
   - social 유저 이메일로 email 로그인 시도: 401 (social 계정임을 힌트로 주지 않음)

2. **GREEN 1**: `db/models.py::User.password_hash` 추가 + alembic migration 생성 (`alembic revision --autogenerate -m "add password_hash to users"`)
   - 주의: 기존 alembic migration 이 JSONB 로 SQLite 에서 깨지므로 **autogenerate 가 모든 테이블 diff 를 잡을 수 있음**. 새 migration 에는 `add_column` 하나만 남기도록 수동 편집.

3. **GREEN 2**: `auth/service.py` 확장 — `_hash_password`, `_verify_password`, `register_with_email`, `login_with_email`

4. **GREEN 3**: `auth/schemas.py` 에 request 모델 추가

5. **GREEN 4**: `auth_router.py` 에 두 엔드포인트 추가

6. **회귀**: 기존 `test_s27_auth_api.py` + `test_s35b_frontend_contract_e2e.py` + 전체 스토리 경로 테스트 통과 확인

## 세션 2 진입 조건 (세션 1 완료 판정)

- [ ] `pytest tests/test_s27b_email_auth.py` 전 케이스 통과
- [ ] `pytest tests/test_s27_auth_api.py tests/test_s35b_frontend_contract_e2e.py` 회귀 0건
- [ ] `ruff check` + `ruff format` 통과
- [ ] alembic migration 이 이미 존재하는 SQLite `test.db` 에 `add_column` 만 실행하고 에러 없이 끝남 (dev_token.py 가 여전히 동작하는지 smoke)
- [ ] SESSION_LOG 에 S27b 세션 1 엔트리 작성

## 세션 2 TDD 로드맵

- **RED (컴파일 타임)**: `AppNavigator.tsx` 에 `import { LoginScreen } from "../screens/LoginScreen"` 만 먼저 추가 → `npx tsc --noEmit` → `TS2307` 확인 (기존 S29~S34 패턴)
- **GREEN**:
  - `src/screens/LoginScreen.tsx` 신규 — 이메일/비번 입력 + 회원가입 ↔ 로그인 토글 + 에러 배너 + submit 후 토큰 저장 → 초기화면 네비게이션
  - `src/navigation/AppNavigator.tsx` — `Login` 라우트 추가 + `initialRouteName` 조건부
  - `src/api/client.ts` 확장 또는 신규 `src/storage/tokenStore.ts` — AsyncStorage wrapper (`saveToken`/`loadToken`/`clearToken`) + `loginWithEmail`/`registerWithEmail` API 함수
  - `App.tsx` 또는 신규 `src/auth/bootstrap.tsx` — 앱 시작 시 저장 토큰 로드 → `setAccessToken` → `GET /auth/me` 로 유효성 검증 → 유효하면 Home, 아니면 Login 으로 초기 라우트 결정
  - 5개 화면의 `TODO(post-S27)` 주석을 실제 `navigation.replace("Login")` 호출로 교체 (401 감지 시)
- **검증**: `npx tsc --noEmit` 통과 + 실기기 1회 스모크 (LoginScreen → 회원가입 → Home → ProfileForm 진입). **S35b 미완 스모크와 병합** 하여 9화면 전체 1회 탭까지.

## 의존성 추가 가능성

- `bcrypt` 또는 `passlib[bcrypt]` → `pyproject.toml` 에 추가 필요할 가능성
- `email-validator` (Pydantic `EmailStr` 용)
- 모바일: `@react-native-async-storage/async-storage` → `packages/mobile/package.json` 에 추가 필요할 가능성. Expo SDK 54 에 기본 포함 여부 확인 필요.

## dev_token.py 와의 상호작용

- 세션 1 에서 `User.password_hash` 컬럼이 추가된다. `dev_token.py` 는 이 컬럼을 null 로 두고 User 생성 → 여전히 동작해야 함.
- 세션 2 완료 후 `dev_token.py` 는 **삭제** 권장. 로그인 UI 가 생겼으므로 목적 완수.
- `packages/mobile/src/api/client.ts` 의 임시 토큰 하드코딩이 남아있지 않은지 `git diff` 로 확인 후 세션 2 종료.

---

## 세션 1 시작 시 Claude 에게 전달할 프롬프트 (복사 → 붙여넣기)

```
S27b 세션 1 (백엔드) 시작합니다.

먼저 docs/S27b-handoff.md 를 전부 읽어주세요. 거기에 배경 / 범위 / 설계 결정
아이템 / TDD 로드맵 / 세션 1 진입 조건이 모두 정리돼 있습니다.

읽은 후:
1. 핸드오프의 "설계 결정 먼저 필요한 것들" 7가지 아이템을 brainstorming skill
   로 하나씩 짚어가며 확정해주세요 (하나씩 질문하기).
2. 설계 확정 후 writing-plans skill 로 세션 1 구현 계획을 작성합니다.
3. 계획 승인 후 test-driven-development skill 로 TDD RED → GREEN 진행합니다.
4. CLAUDE.md "파일 5개 이상 동시 수정 금지" 를 지키기 위해 이번 세션은
   백엔드 범위만 (약 6파일). 모바일은 세션 2.

핸드오프에 적힌 "필수 읽기" 7개 문서를 먼저 로드한 뒤 브레인스토밍을
시작해주세요.
```

## 세션 2 시작 시 Claude 에게 전달할 프롬프트 (세션 1 완료 후 사용)

```
S27b 세션 2 (모바일) 시작합니다.

docs/S27b-handoff.md 와 docs/SESSION_LOG.md 의 S27b 세션 1 엔트리를 먼저
읽어주세요. 세션 1 에서 확정된 API 경로/요청-응답 형식을 정확히 따라야
합니다.

읽은 후:
1. S27b 핸드오프의 "세션 2 TDD 로드맵" 을 따라 진행합니다.
2. 5개 화면의 TODO(post-S27) 주석을 실제 navigation.replace("Login")
   호출로 교체합니다 (DescriptiveInput/Generation/Preview/Library/Viewer).
3. 세션 2 완료 후 packages/backend/scripts/dev_token.py 삭제 여부를
   최종 결정하고, packages/mobile/src/api/client.ts 에 임시 토큰
   하드코딩이 남아있지 않은지 git diff 로 확인해주세요.
4. 세션 2 완료 후 S35b 의 미완 실기기 수동 스모크를 이어서 진행합니다.
   9화면 탭 시나리오. 결과는 docs/SESSION_LOG.md 의 S35b 엔트리에 추가
   기록.
```
