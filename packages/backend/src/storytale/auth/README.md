# auth 모듈

소셜 로그인, JWT 토큰 발급/검증, 법정대리인 동의를 담당하는 인증 모듈.

## 주요 클래스/함수

| 클래스/함수 | 파일 | 역할 |
|-------------|------|------|
| `AuthService` | `service.py` | JWT 생성/검증, 소셜 로그인 플로우, 토큰 갱신, 로그아웃, 동의 기록 |
| `TokenBlacklist` | `service.py` | 토큰 블랙리스트 프로토콜 |
| `RedisBlacklist` | `service.py` | Redis 기반 블랙리스트 (프로덕션) |
| `InMemoryBlacklist` | `service.py` | 인메모리 블랙리스트 (테스트/개발) |
| `create_blacklist()` | `service.py` | `REDIS_URL` 유무로 구현체 자동 선택 |
| `GoogleProvider` | `providers.py` | Google ID 토큰 검증 |
| `KakaoProvider` | `providers.py` | Kakao auth_code 교환 + 사용자 조회 |
| `AppleProvider` | `providers.py` | Apple ID 토큰 JWKS 검증 |
| `AuthTokens` | `schemas.py` | 응답 스키마 (access_token, refresh_token, expires_in) |
| `SocialLoginRequest` | `schemas.py` | 로그인 요청 (provider, auth_code) |

## 사용 예시

```python
from storytale.auth.service import AuthService

# 서비스 생성
auth = AuthService(db=session, jwt_secret="your-secret-key")

# 소셜 로그인 (프로바이더 호출은 _get_social_user_info 오버라이드 필요)
tokens = await auth.social_login(provider="google", auth_code="...")

# 토큰 검증
payload = auth.decode_token(tokens.access_token)
user_id = payload["sub"]

# 토큰 갱신
new_tokens = await auth.refresh_token(tokens.refresh_token)

# 법정대리인 동의
await auth.record_consent(user_id=user_id)
```

## API 엔드포인트

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | `/api/v1/auth/login` | 소셜 로그인 | 불필요 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 | 불필요 |
| POST | `/api/v1/auth/logout` | 로그아웃 | Bearer |
| POST | `/api/v1/auth/consent` | 법정대리인 동의 | Bearer |
| GET | `/api/v1/auth/me` | 내 정보 | Bearer |

## 테스트

```bash
pytest tests/test_s27_auth_service.py tests/test_s27_auth_api.py tests/test_s27_social_providers.py -v
```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `JWT_SECRET_KEY` | `change-me-in-production` | JWT 서명 비밀키 (32자 이상 권장) |
| `REDIS_URL` | (미설정 시 인메모리) | Redis 연결 URL. 설정 시 블랙리스트를 Redis에 저장 |
| `GOOGLE_CLIENT_ID` | | Google OAuth 클라이언트 ID |
| `KAKAO_CLIENT_ID` | | Kakao 앱 REST API 키 |
| `KAKAO_REDIRECT_URI` | | Kakao 리다이렉트 URI |
| `APPLE_CLIENT_ID` | | Apple 번들 ID (예: `com.storytale.app`) |

## 다른 라우터에서 인증 사용

```python
from storytale.api.auth_router import CurrentUserDep

@router.get("/protected")
async def protected_endpoint(user_id: CurrentUserDep) -> dict:
    return {"user_id": user_id}
```
