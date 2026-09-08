# StoryTale 앱 흐름도

> 개인화 아동 그림책 생성 앱의 전체 화면 구성, 사용자 여정, API 흐름, 아키텍처 매핑을 정리한 문서.

---

## 1. 전체 화면 구성 (12개 스크린)

| # | 화면 | 파일 | 역할 |
|---|------|------|------|
| 1 | Login | `screens/LoginScreen.tsx` | 이메일 로그인/회원가입 |
| 2 | Home | `screens/HomeScreen.tsx` | 대시보드 (3개 CTA) |
| 3 | ProfileForm | `screens/ProfileFormScreen.tsx` | 아이 프로필 등록 |
| 4 | PurposeSelect | `screens/PurposeSelectScreen.tsx` | 목적 선택 (4종) |
| 5 | DescriptiveInput | `screens/DescriptiveInputScreen.tsx` | 부모 자유 서술 입력 |
| 6 | Preview | `screens/PreviewScreen.tsx` | 설계 미리보기 + 수정 (최대 3회) |
| 7 | Generation | `screens/GenerationScreen.tsx` | 생성 중 로딩 UX |
| 8 | Viewer | `screens/ViewerScreen.tsx` | 완성 그림책 뷰어 |
| 9 | Library | `screens/LibraryScreen.tsx` | 내 서재 (스토리 갤러리) |
| 10 | RecommendPurpose | `screens/RecommendPurposeScreen.tsx` | 추천 - 목적 선택 |
| 11 | RecommendInput | `screens/RecommendInputScreen.tsx` | 추천 - 상황 서술 |
| 12 | RecommendResult | `screens/RecommendResultScreen.tsx` | 추천 결과 + 맞춤동화 CTA |

> 모든 경로 기준: `packages/mobile/src/`

---

## 2. 사용자 여정 — 전체 흐름도

```
                            앱 시작
                              |
                       토큰 확인 (bootstrap)
                         /           \
                    없음/만료        유효
                      |               |
                 +---------+          |
                 |  Login  |          |
                 | (로그인) |----------+
                 +---------+          |
                                      v
                               +----------+
                      +------->|   Home   |<--------------+
                      |        | (대시보드) |               |
                      |        +----+-----+               |
                      |             |                      |
                      |     프로필 없음?                    |
                      |      Yes |      No                 |
                      |          v       |                 |
                      |   +------------+ |                 |
                      |   |ProfileForm | |                 |
                      |   |(프로필 등록)|-+                 |
                      |   +------------+                   |
                      |                                    |
                      |   +----------+-----------+         |
                      |   |          |           |         |
                      |   v          v           v         |
                      | [추천]    [맞춤동화]   [내서재]     |
                      | 플로우A   플로우B     플로우C      |
                      |   |          |           |         |
                      +---+----------+-----------+---------+
```

---

## 3. 플로우 A — 추천 플로우 (기존 책 추천 → 맞춤 동화 연결)

```
Home
 |  "이야기의 힘을 빌려보세요"
 v
+---------------------+
| RecommendPurpose    |   목적 선택 (4종 카드)
| "어떤 이야기가       |   - 가치 교육
|  필요한가요?"        |   - 관심사
|                     |   - 문제 해결
|                     |   - 기념일
+---------+-----------+
          v
+---------------------+
| RecommendInput      |   상황 자유 서술
| "어떤 상황인지       |   (1~500자)
|  알려주세요"         |
+---------+-----------+
          |  POST /recommendations
          v
+---------------------+
| RecommendResult     |
|                     |   - 감정 키워드 뱃지
|                     |   - 추천 도서 3권
|                     |     (표지, 작가, 연령, 추천 이유)
|                     |   - 독서 가이드 (질문 + 대화법)
|                     |
|                     |   CTA: "맞춤 동화 만들기"
+---------+-----------+            |
          |                        | (PurposeSelect 건너뜀)
          |                        v
          |                 +----------+
          |                 | Preview  | <-- 플로우 B 합류
          |                 +----------+
          v
       (종료/홈)
```

---

## 4. 플로우 B — 맞춤 동화 만들기 (핵심 창작 흐름)

```
Home
 |  "맞춤 동화 만들기"
 v
+---------------------+
| PurposeSelect       |   목적 선택 (4종 카드)
|                     |   - 가치 교육 (value_teaching)
|                     |   - 관심사 (interest_story)
|                     |   - 문제 해결 (problem_solving)
|                     |   - 기념일 (celebration)
+---------+-----------+
          v
+---------------------+
| DescriptiveInput    |   부모 자유 서술 (1~500자)
| "어떤 이야기를       |   예: "요즘 동생 때문에 힘들어해요"
|  담아볼까요?"        |
+---------+-----------+
          |  POST /stories/plan
          v
+---------------------+
|     Preview         |   AI 생성 설계 미리보기
|                     |   - 제목 + 줄거리 요약
|                     |   - 장면별 하이라이트 (이모지 + 한줄)
|                     |   - 예상 페이지 수
|   +---------------+ |   - 스타일 (수채화/파스텔 등)
|   | 수정 요청      |<--- POST /stories/plan/revise
|   | (최대 3회)     | |       (최대 3회 반복)
|   +---------------+ |
|                     |
|   [확정하기] --------+
+---------+-----------+
          |  POST /stories/generate -> 202 + jobId
          v
+---------------------+
|   Generation        |   생성 중 UX
|                     |   - "이야기가 자라고 있어요"
|                     |   - 1.5초 간격 폴링
|   +-------------+   |     GET /stories/jobs/{jobId}
|   | Scene 1  OK |   |   - 완료 장면 실시간 표시
|   | Scene 2  OK |   |   - 전체 완료 시 자동 전환
|   | Scene 3  .. |   |
|   +-------------+   |
+---------+-----------+
          v
+---------------------+
|     Viewer          |   완성 그림책 뷰어
|                     |   - 가로 스와이프 페이지
|   +-------------+   |   - 일러스트 (4:3) + 텍스트 카드
|   |   [그림]    |   |   - 페이지 인디케이터
|   |  텍스트...  |   |   - 뒤로 -> Library 또는 Home
|   |     1/8     |   |
|   +-------------+   |
+---------------------+
```

---

## 5. 플로우 C — 내 서재

```
Home
 |  "내 서재"
 v
+---------------------+
|    Library          |   스토리 갤러리
|                     |   - 카드형 목록 (최신순)
|   +--------+        |   - 당겨서 새로고침
|   | 책 1   | 탭 -------> Viewer (해당 스토리)
|   | 책 2   | 길게누름 --> 삭제 확인
|   | 책 3   |        |
|   +--------+        |
+---------------------+
```

---

## 6. 4층 아키텍처 × 화면 매핑

```
  부모 입력                    AI 처리                   화면
                        +---------------------+
 PurposeSelect -------->| 0층: 가드레일        |
 DescriptiveInput ----->|  - 감정흐름 템플릿    |
                        |  - 연령별 문체        |
                        |  - 안전 규칙         |
                        +----------+----------+
                                   v
                        +---------------------+
                        | 1층: AI 인터프리터    |
                        |  - 의도 분석         |-------> Preview
                        |  - 장면 설계         |
                        |  - 미리보기 생성      |
                        +----------+----------+
                                   v
                        +---------------------+
 Preview (수정 요청) -->| 2층: 부모 확인 루프   |-------> Preview
                        |  (최대 3회 수정)     |       (수정/확정)
                        +----------+----------+
                                   v (확정)
                        +---------------------+
                        | 3층: 개인화 생성      |-------> Generation
                        |  - 장면별 텍스트 생성  |      (진행률 폴링)
                        |  - 일러스트 프롬프트   |
                        +----------+----------+
                                   v
                        +---------------------+
                        | 4층: AI 일러스트      |-------> Viewer
                        |  - PuLID 얼굴 앵커   |       (완성본 열람)
                        |  - 캐릭터 시트 생성   |
                        |  - Flux.1 장면 생성  |
                        |  - CLIP+DINO 검증   |
                        +---------------------+
```

---

## 7. API 호출 흐름 요약

| 화면 전환 | API 호출 | 메서드 | 응답 |
|-----------|----------|--------|------|
| Login -> Home | `/auth/login/email` | POST | JWT 토큰 |
| Home (마운트) | `/profiles` | GET | 프로필 목록 |
| ProfileForm -> Home | `/profiles` | POST | 생성된 프로필 |
| DescriptiveInput -> Preview | `/stories/plan` | POST | ScenePlan + Preview |
| Preview (수정) | `/stories/plan/revise` | POST | 수정된 Plan (최대 3회) |
| Preview (확정) -> Generation | `/stories/generate` | POST | 202 + jobId |
| Generation (폴링) | `/stories/jobs/{jobId}` | GET | 진행률 + 완료 장면 |
| Viewer (열기) | `/stories/{id}` | GET | 전체 스토리 + 페이지 |
| Library (목록) | `/stories` | GET | 스토리 목록 |
| Library (삭제) | `/stories/{id}` | DELETE | 삭제 확인 |
| RecommendInput -> Result | `/recommendations` | POST | 추천 3권 + 가이드 |

---

## 8. 네비게이션 라우트 파라미터

| 라우트 | 파라미터 | 설명 |
|--------|----------|------|
| `Login` | 없음 | |
| `Home` | 없음 | |
| `ProfileForm` | 없음 | |
| `PurposeSelect` | 없음 | |
| `DescriptiveInput` | `{ purpose: PurposeId }` | 선택한 목적 |
| `Preview` | `{ plan, preview, childId, childName }` | AI 생성 설계 |
| `Generation` | `{ plan, childId, childName, style }` | 확정된 설계 |
| `Viewer` | `{ storyId }` | 완성 스토리 ID |
| `Library` | 없음 | |
| `RecommendPurpose` | 없음 | |
| `RecommendInput` | `{ purpose: PurposeId }` | 선택한 목적 |
| `RecommendResult` | `{ result, childId, childName }` | 추천 결과 |

---

## 9. 에러 흐름

| 상황 | 코드 | 처리 |
|------|------|------|
| 토큰 만료/무효 | 401 | `forceLogoutToLogin()` -> Login 화면 리셋 |
| 부적절한 부모 입력 | 400 (`REJECTED_INTENT_CODE`) | "이 이야기는 함께 만들기 어려워요" 알림 |
| 수정 횟수 초과 | 400 (`MAX_REVISIONS_EXCEEDED_CODE`) | "수정은 최대 3회까지 가능해요" 알림 |
| 생성 실패 | 500 | Generation 화면 내 재시도/홈 복귀 CTA |

---

## 10. 디자인 토큰 (현재 적용)

| 토큰 | 값 | 용도 |
|------|-----|------|
| Primary | `#FFA94D` | 주요 버튼, 강조색 |
| Primary Light | `#FFF3E6` | 배경 하이라이트 |
| Secondary | `#A07DE8` | 보조 강조 (라벤더) |
| Tertiary | `#6DD4B8` | 성공/긍정 (민트) |
| Background | `#FDF9F5` | 전체 배경 (따뜻한 오프화이트) |
| Text | `#2E2720` | 본문 텍스트 (다크 브라운) |
| Text Secondary | `#7A7067` | 보조 텍스트 |
| Border | `#E8E2DB` | 테두리, 구분선 |
| Shadow | `#3E3225` | 그림자 (따뜻한 브라운 톤) |
| Border Radius | `14px` (버튼), `20px` (카드) | |
| Min Touch Target | `44x44` ~ `52x52` | |
| UI 폰트 | Pretendard | 가독성 |
| 스토리 폰트 | Cafe24Ssurround | 동화책 느낌 |
