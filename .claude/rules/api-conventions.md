# API 설계 규칙

## URL 패턴
- REST 기본: `/{리소스 복수형}` → GET(목록), POST(생성).
- 단일 리소스: `/{리소스 복수형}/{id}` → GET, PUT, DELETE.
- 동작: `/{리소스}/{id}/{동사}` → POST. 예: `/stories/{id}/generate`.
- 버전: URL에 넣지 않음. 초기 단계에서 불필요.

## 요청/응답
- 요청 바디: Pydantic BaseModel로 검증. snake_case 필드.
- 응답: `{"data": ...}` 래핑 없이 직접 반환. FastAPI 기본 직렬화.
- 에러: `{"detail": "메시지", "code": "ERROR_CODE"}` 형식.
- 페이지네이션: `?limit=20&offset=0`. 응답에 `total` 포함.

## HTTP 상태 코드
- 200: 조회/수정 성공.
- 201: 생성 성공.
- 400: 입력 검증 실패.
- 401: 인증 필요.
- 404: 리소스 없음.
- 422: Pydantic 검증 에러 (FastAPI 기본).
- 500: 서버 에러 (LLM/외부 API 실패 포함).

## 비동기 작업 (스토리 생성, 일러스트 생성)
- 생성 요청: `POST /stories/generate` → 202 Accepted + `{jobId}`.
- 상태 조회: `GET /stories/jobs/{jobId}` → 진행률 + 완료된 장면 목록.
- 실시간: SSE(Server-Sent Events)로 장면 완료 시 푸시.
- 최종 결과: `GET /stories/{id}` → 완성된 스토리 + 일러스트 URL.

## 인증
- JWT Bearer 토큰. Authorization 헤더.
- 소셜 로그인 후 자체 JWT 발급.

## 동시성 제어
- 사용자당 동시 스토리 생성 1건 제한. Redis 기반 락.
- 진행 중인 생성 작업이 있으면 409 Conflict 반환.

## 파일 업로드
- 아이 사진: 최대 5MB, JPEG/PNG만 허용.
- EXIF 메타데이터 자동 제거 후 처리.
- multipart/form-data 사용.
