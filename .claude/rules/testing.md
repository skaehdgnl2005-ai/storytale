# 테스트 전략

## TDD 워크플로우 (필수)
1. 테스트 파일 먼저 작성.
2. `pytest` 실행 → 실패 확인. 실패하지 않으면 테스트가 잘못된 것.
3. 최소한의 구현으로 테스트 통과.
4. 리팩터링.
5. 다음 테스트 케이스로 반복.

## 테스트 구조
- 파일 위치: `packages/backend/tests/` (백엔드 미러 구조).
- 네이밍: `test_{모듈명}.py` → `test_{함수명}` 또는 `test_{시나리오}`.
- 픽스처: `conftest.py`에 공유 픽스처. DB 세션, 테스트 클라이언트 등.

## 테스트 종류별 비중
- 단위 테스트: 70%. 외부 의존성 모킹.
- 통합 테스트: 25%. DB, Redis 포함. 테스트용 Docker 컨테이너 사용.
- E2E 테스트: 5%. 전체 플로우. 백엔드: pytest + httpx AsyncClient. 모바일: S5에서 도구 결정.

## LLM 호출 테스트
- 단위 테스트: 반드시 모킹. 실제 API 호출 금지.
- 통합 테스트: 실제 호출 1~2회 허용. `@pytest.mark.integration` 마킹.
- 모킹 시: 실제 API 응답 형식과 동일한 fixture JSON 사용.

## 일러스트 파이프라인 테스트
- Replicate 호출: 모킹 기본. 실제 호출은 `@pytest.mark.external`.
- CLIP 검증: 로컬 모델로 테스트. 테스트용 이미지 `tests/fixtures/`에 배치.

## 커버리지
- 최소 목표: 80%.
- contracts에 정의된 모든 public 인터페이스는 반드시 테스트.
