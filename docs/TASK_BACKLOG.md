# 태스크 백로그

상태: `[대기]` `[진행중]` `[완료]` `[차단]`

> **의존성 표기 규칙**: S1(모노레포 초기화)은 모든 태스크의 암묵적 전제조건이며, 개별 태스크의 "의존성"은 모듈 간 코드 의존성만 표기합니다.

---

## Phase 1: 기반 (S1~S6)

### S1 — 모노레포 초기화 & 개발환경 [완료]
- **산출물**: 폴더 구조, pyproject.toml, package.json, Docker Compose, .env.example
- **의존성**: 없음
- **검증**: `pip install -e .` 성공, `npm install` 성공, `docker-compose up` 성공

### S2 — 공유 타입 정의 [완료]
- **산출물**: `packages/shared/src/types/` (contracts를 TypeScript 타입으로)
- **의존성**: S1
- **검증**: `npx tsc --noEmit` 통과

### S3 — DB 스키마 & 마이그레이션 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md` (데이터 모델 섹션)
- **산출물**: SQLAlchemy 모델, Alembic 마이그레이션, 초기 스키마
- **의존성**: S1
- **검증**: `alembic upgrade head` 성공, 테이블 생성 확인

### S4 — FastAPI 앱 뼈대 [완료]
- **산출물**: 라우터 구조, 미들웨어(CORS, 에러핸들링), 헬스체크, DB 세션 관리
- **의존성**: S3
- **검증**: `pytest` 기본 통과, `GET /health` 200 OK

### S5 — React Native 앱 뼈대 [완료]
- **산출물**: Expo 프로젝트, 네비게이션(React Navigation), 테마/색상 시스템
- **의존성**: S1
- **검증**: iOS 시뮬레이터에서 앱 실행

### S6 — GitHub Actions CI [완료]
- **산출물**: `.github/workflows/test.yml` (백엔드 pytest + 프론트 tsc)
- **의존성**: S4, S5
- **검증**: PR 생성 시 자동 테스트 실행

---

## Phase 2: 가드레일 시스템 (S7~S10)

### S7 — 감정 흐름 템플릿 모델 + CRUD API [완료]
- **시작 시 필수 읽기**: `docs/guardrail-seeds/emotional-arcs.json`
- **산출물**: `EmotionalArcTemplate` 모델, API 엔드포인트, 시드 데이터 6개 삽입
- **의존성**: S4
- **검증**: CRUD 테스트 통과, 시드 데이터 조회 확인

### S8 — 연령별 문체 규칙 모델 + API [완료]
- **시작 시 필수 읽기**: `docs/guardrail-seeds/age-style-guides.json`
- **산출물**: `AgeStyleGuide` 모델, API 엔드포인트, 3개 연령대 시드
- **의존성**: S4
- **검증**: API 테스트 통과

### S9 — 안전 규칙 모델 + API [완료]
- **시작 시 필수 읽기**: `docs/guardrail-seeds/safety-rails.json`
- **산출물**: `SafetyRails` 모델, API 엔드포인트, 시드 데이터
- **의존성**: S4
- **검증**: API 테스트 통과

### S10 — 가드레일 통합 조회 API [완료]
- **산출물**: `GET /guardrails?age_group=3-4` → 아크 목록 + 문체 + 안전규칙 묶음
- **의존성**: S7, S8, S9
- **검증**: 통합 조회 테스트, 연령대별 올바른 데이터 반환

**🔍 품질 게이트 G1**: Phase 2 완료 후 가드레일 데이터 리뷰 세션.

---

## Phase 3: AI 인터프리터 (S11~S16) ⭐ 핵심

### S11 — LLM 클라이언트 래퍼 [완료]
- **산출물**: `LLMClient` (Claude API 호출, 재시도 3회, 타임아웃 60초, JSON 파싱, 호출별 로깅 포함)
- **의존성**: 없음 (외부 라이브러리만)
- **검증**: 모킹 테스트 + 실제 호출 1회 (`@pytest.mark.integration`)
- **로깅**: 요청/응답/소요시간/토큰수를 구조화 로그로 기록
- **[2026-04-08 확장]** Gemini fallback 추가:
  - `GeminiProvider` (`gemini_provider.py`): `complete()` 동일 인터페이스, 자체 재시도 3회
  - `LLMClient(fallback_provider=...)`: Claude 서버 장애(4회 소진) 시 Gemini로 자동 전환
  - `create_llm_client()` 팩토리: `GEMINI_API_KEY` 유무로 fallback 자동 설정
  - S19 이후 `LLMClient()` 직접 생성 대신 `create_llm_client()` 사용 권장
  - 의존성 추가: `google-genai>=1.0,<2`

### S12 — 의도 분석 모듈 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md`, `docs/prompts/intent-analyzer-v1.md`, `docs/guardrail-seeds/emotional-arcs.json`
- **산출물**: `IntentAnalyzer`, 프롬프트 `docs/prompts/intent-analyzer-v1.md`
- **의존성**: S11, S10
- **검증**: 5가지 입력 텍스트 → 올바른 category + arc 매칭
- **주의**: 이 세션은 프롬프트 엔지니어링에 집중. 코드보다 프롬프트가 중요.
- **테스트 케이스**:
  1. 가치 교육: "거짓말하면 안 된다는 걸 알려주고 싶어요"
  2. 관심사: "공룡을 너무 좋아해요, 특히 트리케라톱스"
  3. 문제 해결: "동생이 태어났는데 자꾸 밀쳐요"
  4. 기념일: "다음 주가 생일인데 특별한 책을 만들어주고 싶어요"
  5. 모호한 입력: "좋은 아이가 됐으면 좋겠어요"

### S13 — 장면 설계 모듈 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md`, `docs/prompts/scene-planner-v1.md`, `docs/guardrail-seeds/emotional-arcs.json`, `docs/guardrail-seeds/age-style-guides.json`, `docs/guardrail-seeds/safety-rails.json`
- **산출물**: `ScenePlanner`, 프롬프트 `docs/prompts/scene-planner-v1.md`
- **의존성**: S11, S10
- **검증**: 의도분석 결과 → scene_plan JSON 스키마 검증 + 가드레일 준수 확인
- **주의**: 안전 규칙 위반 여부를 자동 검증하는 validator 함수도 함께 구현.

### S14 — 설계 수정 모듈 [완료]
- **시작 시 필수 읽기**: `docs/prompts/scene-planner-v1.md`, `docs/guardrail-seeds/safety-rails.json`
- **산출물**: `PlanReviser`
- **의존성**: S13
- **검증**: "토끼 친구 대신 서준이가 나왔으면" → 해당 장면만 변경, 나머지 유지

### S15 — 부모 미리보기 생성 [완료]
- **시작 시 필수 읽기**: `docs/prompts/preview-generator-v1.md`
- **산출물**: `PreviewGenerator`
- **의존성**: S13
- **검증**: scene_plan → 이모지 + 한줄 요약 + 전체 요약 생성

### S16 — 인터프리터 통합 E2E [완료]
- **산출물**: 인터프리터 오케스트레이션, 전체 플로우 테스트
- **의존성**: S12~S15
- **검증**: 텍스트 입력 → 의도분석 → 장면설계 → 미리보기 → 수정 → 확정

**🔍 품질 게이트 G2**: 실제 5개 시나리오로 인터프리터 품질 수동 검증.

---

## Phase 4: 스토리 생성 (S17~S20)

### S17 — 장면별 텍스트 생성 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md`, `docs/prompts/story-personalizer-v1.md`, `docs/guardrail-seeds/age-style-guides.json`
- **산출물**: `StoryPersonalizer`, 프롬프트 `docs/prompts/story-personalizer-v1.md`
- **의존성**: S11
- **검증**: PlannedScene + ChildProfile → PersonalizedScene (텍스트 + 일러스트 프롬프트)

### S18 — 스토리 오케스트레이터 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md`
- **산출물**: `StoryOrchestrator` (인터프리터 + 텍스트 생성 연결)
- **의존성**: S16, S17
- **검증**: 1편 완성 E2E (텍스트만, 일러스트 제외)

### S19 — 스토리 생성 API [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md` (비동기 작업 처리 + 비용 추정 섹션)
- **산출물**: `POST /stories/generate` (비동기, 202 + jobId), SSE 엔드포인트
- **의존성**: S18
- **검증**: API 호출 → 백그라운드 생성 → SSE로 진행률 수신

### S20 — 스토리 저장/조회 API [완료]
- **산출물**: Story + StoryPage DB 저장, `GET /stories/{id}`, `GET /stories` (목록)
- **의존성**: S19
- **검증**: 생성 완료 → DB 저장 → 조회 확인

**🔍 품질 게이트 G3**: 3개 스토리 전문 생성, 텍스트 품질 수동 검증.

---

## Phase 4.5: 동화책 추천 (R1~R8) — Phase 5와 병렬

### R1 — 추천 계약 + 공유 타입 정의 [완료]
- **산출물**: `docs/contracts/book-recommendation.ts`, `packages/shared/src/types/book-recommendation.ts`
- **의존성**: S2
- **검증**: `npx tsc --noEmit` 통과

### R2 — Book DB 모델 + 마이그레이션 [완료]
- **산출물**: Book, SituationTag, BookRecommendation 모델 (models.py)
- **의존성**: R1
- **검증**: 모델 CRUD 테스트 11개 통과

### R3 — 외부 도서 API 클라이언트 [완료]
- **산출물**: AladinClient, NlcyClient (알라딘/국립도서관 API)
- **의존성**: 없음
- **검증**: 모킹 테스트 8개 통과

### R4 — 상황 태그 자동 생성 파이프라인 [완료]
- **산출물**: TagGenerator, `docs/prompts/tag-generator-v1.md`
- **의존성**: R2, S11
- **검증**: 모킹 테스트 5개 통과

### R5 — BookRecommender 서비스 [완료]
- **산출물**: BookRecommender (매칭 알고리즘 + LLM 가이드 생성)
- **의존성**: R2, R4, S12
- **검증**: 5개 시나리오 테스트 통과

### R6 — 추천 가이드 LLM 프롬프트 [완료]
- **산출물**: `docs/prompts/book-recommender-v1.md`
- **의존성**: R5

### R7 — 추천 API 엔드포인트 [완료]
- **산출물**: POST/GET /api/v1/recommendations
- **의존성**: R5
- **검증**: API 테스트 3개 통과

### R8 — 초기 도서 시드 데이터 [완료]
- **산출물**: `scripts/seed_books.py` (한국 아동 동화 25권 + 상황 태그)
- **의존성**: R3, R4
- **검증**: 스크립트 실행 → 25권 적재 성공

**🔍 품질 게이트 G3.5**: 10개 시나리오로 추천 품질 수동 검증 (TODO).

---

## Phase 5: 일러스트 파이프라인 (S21~S26)

### S21 — Replicate API 클라이언트 [완료]
- **산출물**: `ReplicateClient` (호출, 재시도, 폴링, 타임아웃)
- **의존성**: 없음
- **검증**: 모킹 + 실제 Flux.1 호출 1회

### S22a — PuLID 얼굴 앵커 생성 서비스 [완료]
- **시작 시 필수 읽기**: `docs/contracts/illustration-pipeline.ts` (CharacterSheetService Phase 1)
- **산출물**: `FaceAnchorService` — 아이 사진 → `bytedance/flux-pulid` API로 얼굴 특징 추출 → 스타일 무관 얼굴 앵커 이미지 생성
- **의존성**: S21
- **검증**: 테스트 사진 → 얼굴 앵커 이미지 생성, PuLID id_weight 파라미터 실험 (0.7~1.0)
- **주의**: 사진은 처리 후 즉시 삭제 (보안 규칙). 얼굴 앵커는 1회만 생성하면 모든 스타일에서 재사용.

### S22b — 멀티뷰 캐릭터 시트 + Identity Prompt Block [완료]
- **시작 시 필수 읽기**: `docs/contracts/illustration-pipeline.ts`, `docs/guardrail-seeds/art-direction.json`
- **산출물**: `CharacterSheetService` — 얼굴 앵커 + 스타일 → 정면/3\/4/측면 멀티뷰 이미지 생성 + Claude로 Identity Prompt Block 텍스트 추출
- **의존성**: S22a, S11
- **검증**:
  - 3뷰(정면/3\/4/측면) 이미지 생성 확인
  - Identity Prompt Block이 캐릭터 시트 이미지와 일치하는지 수동 검증
  - 같은 아이 + 같은 스타일이면 기존 시트 재사용 로직 작동 확인

### S23 — 장면 일러스트 생성 서비스 [완료]
- **시작 시 필수 읽기**: `docs/contracts/illustration-pipeline.ts`, `docs/guardrail-seeds/art-direction.json`, `docs/prompts/story-personalizer-v1.md`
- **산출물**: `SceneIllustrationService` — 일러스트 프롬프트(Identity Block 포함) + PuLID 얼굴 앵커 + 캐릭터 시트 → 장면 이미지 생성
- **의존성**: S21, S22b
- **검증**: 프롬프트 → 캐릭터 동일성 있는 이미지 생성
- **주의**: 아트 디렉션의 composition_rules, emotion_to_visual 반영 필수. sceneEmotion에 따른 색감 조절 테스트

### S24 — CLIP+DINOv2 하이브리드 일관성 검증 + 인페인팅 폴백 [완료]
- **시작 시 필수 읽기**: `docs/contracts/illustration-pipeline.ts` (ConsistencyValidator, InpaintingService)
- **산출물**:
  - `ConsistencyValidator` — CLIP(0.4) + DINOv2(0.6) 가중 합산 compositeScore, threshold 0.80
  - `InpaintingService` — compositeScore 미달 시 캐릭터 영역만 인페인팅 보정
- **의존성**: S22b, S23
- **검증**:
  - 일관된 이미지 compositeScore ≥ 0.80 통과 확인
  - 불일치 이미지 failureReason 정확 분류 (face_drift vs style_mismatch vs proportion_error)
  - 재생성 2회 실패 → 인페인팅 폴백 트리거 확인
  - 인페인팅 후 finalScore 다시 검증

### S25 — S3 이미지 관리 [완료]
- **산출물**: `ImageStorageService` (업로드, URL 생성, 삭제)
- **의존성**: 없음
- **검증**: 업로드 → URL 접근 가능 → 삭제 확인

### S26 — 일러스트 오케스트레이터 [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md` (4층 파이프라인 흐름), `docs/contracts/illustration-pipeline.ts`
- **산출물**: `IllustrationOrchestrator` — 전체 플로우:
  1. 캐릭터 시트 준비 (S22a → S22b)
  2. 장면별 일러스트 생성 (S23)
  3. CLIP+DINOv2 검증 (S24)
  4. 실패 시: 재생성(2회) → 인페인팅 폴백(1회)
- **의존성**: S22a, S22b, S23, S24, S25
- **검증**: 12장면 E2E 생성 — 전 장면 compositeScore ≥ 0.80 확인

**🔍 품질 게이트 G4**: 5개 스토리 일러스트, 캐릭터 동일성 수동 확인 + compositeScore 리포트 리뷰.

---

## Phase 6: 프론트엔드 (S27~S34)

### S27 — 인증 (소셜 로그인) [완료]
- **시작 시 필수 읽기**: `docs/ARCHITECTURE.md`, `docs/contracts/user-service.ts`
- **산출물**: 카카오/구글/애플 소셜 로그인, JWT 발급, 법정대리인 동의 플로우
- **의존성**: S4, S5

### S28 — 아이 프로필 등록 UI [완료]
- **산출물**: 프로필 입력 폼, 사진 업로드, API 연동
- **의존성**: S27
- **검증**: 백엔드 28 테스트 통과, `npx tsc --noEmit` 통과

### S29 — 목적 선택 화면 [완료]
- **산출물**: 4가지 목적 카드 UI (`PurposeSelectScreen` + `data/purposes.ts`)
- **의존성**: S5
- **검증**: `npx tsc --noEmit` 통과 + 컴파일 타임 type assertion(PURPOSE_CARDS 길이=4, IntentCategory 1:1 매핑)

### S30a — 백엔드 plan 엔드포인트 [완료]
- **산출물**: `POST /api/v1/stories/plan` — parent_text + purpose_category + child_id → ScenePlan + StoryPreview
- **의존성**: S18 (StoryOrchestrator), S27 (인증), S28 (ChildProfile API)
- **검증**: pytest 13개 통과 (happy path, 인증, 소유자, 입력 검증, RejectedIntent, 일반 예외)
- **배경**: S19가 노출한 `/stories/generate`는 이미 확정된 ScenePlan을 받는 Phase D 전용. 그 앞 단계(parent_text → ScenePlan)를 만드는 라우터가 누락되어 있어 S30(서술형 입력 UI)이 호출할 곳이 없었음. S30a가 그 빈자리를 채운다.

### S30b — 서술형 입력 UI [완료]
- **산출물**: `DescriptiveInputScreen` (목적별 prompt/예시), 글자수 카운터, `POST /stories/plan` 연동, REJECTED_INTENT/401/404/422 에러 매핑, 첫 프로필 자동 선택
- **추가 산출물**: `packages/mobile/src/api/stories.ts` (`createStoryPlan` + 와이어 타입), `apiFetch` 에러 파서 개선(`{error:{code,message}}` 래핑 형식 + REJECTED_INTENT inner code 추출)
- **의존성**: S29, S30a
- **검증**: `npx tsc --noEmit` 통과 + S30a 백엔드 회귀 13/13 통과 + 컴파일 타임 어서션(`Record<PurposeId, PurposeGuide>` 4종 강제, `purpose_category: PurposeId` 1:1 매핑)

### S31a — 백엔드 plan/revise 엔드포인트 [완료]
- **산출물**: `POST /api/v1/stories/plan/revise` — `current_plan` + `feedback` + `revision_count` + `child_id` → 수정된 ScenePlan + StoryPreview + 갱신된 revision_count
- **의존성**: S18 (StoryOrchestrator.revise_plan), S27 (인증), S28 (ChildProfile API)
- **배경**: `InterpreterOrchestrator.revise_plan()`은 구현되어 있으나 라우터에 노출되어 있지 않음. S30b 흐름의 다음 화면(S31 미리보기/수정)이 호출할 엔드포인트가 없어 S30a와 동일한 분할 패턴으로 선결.
- **revise_count 추적 결정**: **클라이언트 카운터 + 서버 검증** 방식. 요청에 `revision_count`(이미 적용된 횟수, 0-based)를 포함시켜 라우터가 `< MAX_REVISIONS(3)` 검증. `InterpreterOrchestrator._revision_count`는 매 요청마다 새 인스턴스가 생성되므로 사실상 무력화돼 있어 라우터 레벨로 끌어올림. (서버 잡 상태 도입은 MVP 범위 초과로 보류 — Phase 7에서 Redis 기반 세션 도입 시 재검토.)
- **검증**: pytest 15/15 통과 (happy 3 + 인증 1 + 소유자 3 + revision_count 한도 2 + 입력 검증 5 + 에러 처리 1)

### S31 — 미리보기 & 수정 UI [완료]
- **산출물**: `PreviewScreen` (요약 카드 + 장면 하이라이트 + 수정 입력 + 수정 카운터 + 확정 버튼), `revisePlan()` API 클라이언트, `MAX_REVISIONS_EXCEEDED` 에러 매핑
- **추가 산출물**: `packages/mobile/src/api/stories.ts` 확장 (`revisePlan` + `PlanRevisionRequest/Response` + `MAX_REVISIONS` + `MAX_REVISIONS_EXCEEDED_CODE` 상수)
- **의존성**: S30b, S31a
- **검증**: `npx tsc --noEmit` 통과 + 백엔드 S30a/S31a 회귀 28/28 통과
- **S32 임시 처리**: "이 이야기로 만들기" CTA 는 현재 Alert 으로 확정 상태 안내 + Home 복귀. S32(생성 중 로딩 UX) 에서 `navigation.navigate("Generation", {...})` 로 교체 예정(`// TODO(S32)` 주석 명시).

### S32 — 생성 중 로딩 UX [완료]
- **산출물**: `GenerationScreen` (진행률 바 + 장면 카드 `LayoutAnimation.spring` 등장 + 상태별 CTA), `generateStory()`/`getJobStatus()` API 클라이언트, 폴링 루프(`JOB_POLL_INTERVAL_MS = 1500ms`), 뒤로가기 차단
- **추가 산출물**: `packages/mobile/src/api/stories.ts` 확장 (`JOB_POLL_INTERVAL_MS`, `JobStatusValue`, `ChildInput`, `GenerateStoryRequest/Response`, `GeneratedScene`, `JobStatusResponse`)
- **의존성**: S31
- **SSE vs 폴링 결정**: **폴링 채택**. React Native 기본 fetch 는 SSE 파서 없음 + Expo managed 에서 `react-native-sse` 도입은 네이티브 빌드 필요로 MVP 범위 초과. 백엔드 `GET /stories/jobs/{id}` 폴링만으로 충분하며 1.5초 간격은 장면 생성 체감 시간과 근접. SSE 는 S35/E2E 이후 성능 측정 재검토.
- **검증**: `npx tsc --noEmit` 통과 + 백엔드 회귀 `test_s30a_plan_endpoint.py` + `test_s31a_plan_revise_endpoint.py` + `test_s19_story_api.py` 39/39 통과 + `ruff check` 통과
- **S33 임시 처리**: 완료 시 "그림책 열어보기" CTA 는 현재 Alert + Home 복귀. S33(그림책 뷰어) 에서 `navigation.navigate("Viewer", { storyId })` 로 교체 예정(`// TODO(S33)` 주석 명시). 단, `story_id` 를 state 로 승격해야 하는 후속 수정 필요(SESSION_LOG 기록).

**🔍 품질 게이트 G4.5**: S31 완료 후 핵심 사용자 플로우(프로필→서술입력→미리보기) 수동 검증.

### S33 — 그림책 뷰어 [완료]
- **산출물**: `ViewerScreen` (가로 FlatList + pagingEnabled 스와이프, 일러스트 4:3 + 텍스트 카드 레이아웃, 페이지 인디케이터, 로딩/에러/성공 상태 분기), `getStory()` API 클라이언트 + `StoryDetailResponse`/`StoryPageDetail` 와이어 타입, `Viewer` 라우트 등록, GenerationScreen `storyId` state 승격 + `handleOpenBook` Alert → `navigation.reset([Home, Viewer])` 교체 (S32 후속 이슈 해소)
- **의존성**: S5, S20 (GET /stories/{id}), S32 (Generation → Viewer 진입)
- **검증**: `npx tsc --noEmit` 통과 + 백엔드 회귀 `test_s19_story_api.py` + `test_s20_story_storage.py` + `test_s30a_plan_endpoint.py` + `test_s31a_plan_revise_endpoint.py` **49/49 통과**
- **페이지 넘기기 결정**: 가로 FlatList + pagingEnabled 스와이프 채택(버튼 없음). 책 넘기기 메타포 + 문학적 경험 + `getItemLayout`/`windowSize: 3` 성능 튜닝. 스크린리더 접근성 보조 버튼은 post-S35b 실기기 검증 후 재결정.
- **S26 가드**: `illustration_url === null` 일 때 `🎨` + "그림은 곧 도착해요" placeholder UI. 일러스트 파이프라인 연결 전에도 텍스트 뷰어로 동작.

### S34 — 내 서재 [완료]
- **산출물**: `LibraryScreen` (loading/error/empty/list 4상태 분기 + pull-to-refresh + 카드 long-press 삭제 Alert), `Library` 라우트 등록, HomeScreen "내 서재" 진입 버튼, ViewerScreen `headerRight` 삭제 CTA, mobile `listStories()`/`deleteStory()` API 클라이언트 + `StoryListItem`/`StoryListResponse` 와이어 타입 + `STORIES_PAGE_SIZE` 상수
- **추가 산출물(백엔드)**: `DELETE /api/v1/stories/{story_id}` 라우트 (S34 신규) — JWT 인증 + 소유자 검증(404 통일) + ORM cascade 로 StoryPage 동시 삭제. `tests/test_s34_story_delete_endpoint.py` 10개 테스트 (happy 5 + 인증 1 + 소유자 4)
- **의존성**: S33, S20 (GET /stories, GET /stories/{id})
- **검증**: 백엔드 `pytest tests/test_s34_story_delete_endpoint.py` 10/10 통과 + 라우터 회귀 (s19+s20+s30a+s31a+s34) **59/59 통과** + `ruff check`/`ruff format` 통과 + `npx tsc --noEmit` 통과
- **삭제 후 네비게이션**: ViewerScreen 의 삭제 CTA 는 진입 경로(Generation→reset 또는 Library→push) 양쪽 모두 `navigation.goBack()` 으로 자연 복귀(전자: Home, 후자: Library 카드 사라진 상태). LibraryScreen 의 long-press 삭제는 삭제된 카드만 로컬 state 에서 제거하여 화면 유지.

---

## Phase 7: 통합/운영 (S35~S38)

### S35a — 백엔드 통합 E2E [완료]
- **산출물**: 텍스트 파이프라인(S18) + 일러스트 파이프라인(S26) + DB 저장(S20) 통합 E2E 테스트 (`tests/test_s35a_text_illustration_e2e.py`, 7 케이스)
- **추가 산출물(라우터 통합 지점)**: `get_illustration_context_provider` 의존성 + `IllustrationContextProvider` 타입 + `IllustrationContextDep` Annotated + `_run_generation` 의 일러스트 루프 + `_save_story_to_db` 시그니처 확장(`story_id`/`illustrations`)
- **의존성**: S20, S26
- **검증**: `pytest tests/test_s35a_text_illustration_e2e.py` 7/7 통과 + 라우터 회귀(s19+s20+s26+s30a+s31a+s34+s35a) **79/79 통과** + `ruff check`/`ruff format` 통과
- **프로덕션 연결 보류**: `get_illustration_context_provider` 는 기본 `None` 반환 → 텍스트-only. 실제 `CharacterSheetService` 조립 + `photo_hash` 캐시 조회 + `IllustrationOrchestrator` 조립은 프로덕션 플로우 연결 시점에 추가(CLIP/DINOv2 모델 래퍼가 여전히 미구현이라 실기기 품질 검증 이후 결정).

### S35b — 프론트-백 통합 E2E [대기]
- **산출물**: 프로필등록 → 서술입력 → 미리보기 → 생성 → 열람 전체 플로우
- **의존성**: S35a, S27~S34

### S36 — 가드레일 관리 어드민 [대기]
- **산출물**: 감정아크/문체/안전규칙 CRUD 웹 UI
- **의존성**: S10

### S37 — 의도 분석 대시보드 [대기]
- **산출물**: 주제별 요청 빈도, 인기 키워드, 실패율 모니터링
- **의존성**: S20

### S38 — 배포 [대기]
- **산출물**: Railway 배포, Expo EAS 빌드, GitHub Actions deploy.yml
- **의존성**: S35b

**🔍 품질 게이트 G5**: 전체 플로우 수동 테스트 (시뮬레이터 + 실기기).
