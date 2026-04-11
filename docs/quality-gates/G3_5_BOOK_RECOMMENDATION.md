# 품질 게이트 G3.5: 동화책 추천 품질 검증

## 목적

Phase 4.5(R1-R8)에서 구현된 동화책 추천 파이프라인의 E2E 품질을 검증한다.
- IntentAnalyzer → BookRecommender → LLM 가이드 생성 전체 흐름
- 추천 정확도, 독후 가이드 품질, 안전성

## 사전 조건

### 필수 읽기
- `docs/contracts/book-recommendation.ts` — 추천 계약
- `docs/prompts/book-recommender-v1.md` — 가이드 생성 프롬프트
- `docs/prompts/tag-generator-v1.md` — 태그 생성 프롬프트
- `docs/guardrail-seeds/emotional-arcs.json` — 감정 아크 6종
- `docs/guardrail-seeds/safety-rails.json` — 안전 규칙

### 필수 코드 이해
- `packages/backend/src/storytale/recommendation/book_recommender.py` — 핵심 서비스
- `packages/backend/src/storytale/interpreter/intent_analyzer.py` — 의도 분석 (공유)
- `packages/backend/src/storytale/recommendation/tag_generator.py` — 태그 생성

### 시드 데이터
- `packages/backend/scripts/seed_books.py` 실행으로 25권 + 상황 태그 적재 필요
- 실행: `cd packages/backend && python scripts/seed_books.py`

### 환경변수
- `CLAUDE_API_KEY` 또는 `ANTHROPIC_API_KEY` — IntentAnalyzer + 가이드 생성용
- `GEMINI_API_KEY` (선택) — fallback용

---

## 검증 시나리오 (10개)

### 시나리오 구성

| # | purpose_category | parent_text | child_age | 기대 매칭 |
|---|-----------------|-------------|-----------|----------|
| 1 | problem_solving | "동생이 태어났는데 자꾸 밀쳐요" | 5 | 피터의 의자, 나는 형이니까 |
| 2 | problem_solving | "유치원 가기 싫다고 울어요" | 4 | 당근 유치원 |
| 3 | problem_solving | "어둠을 무서워해서 혼자 못 자요" | 4 | 잘 자 작은 곰아, 까만 밤에... |
| 4 | problem_solving | "자꾸 싫다고만 해요, 반항이 심해요" | 3 | 싫어 싫어 |
| 5 | interest_story | "공룡을 너무 좋아해요, 특히 트리케라톱스" | 4 | 공룡이 쿵쿵쿵 |
| 6 | value_teaching | "친구한테 장난감 안 빌려주려고 해요" | 5 | 무지개 물고기 |
| 7 | value_teaching | "실수하면 크게 울어요, 자신감이 없어요" | 4 | 괜찮아 |
| 8 | celebration | "다음 주 생일인데 특별한 걸 해주고 싶어요" | 5 | 생일 축하해! |
| 9 | problem_solving | "친구를 사귀기 어려워해요" | 5 | 심심한 늑대, 무지개 물고기 |
| 10 | problem_solving | "이 안 닦으려고 해요" | 3 | 이 닦기 싫어! |

---

## 검증 기준 (G3.5-1 ~ G3.5-7)

### G3.5-1: IntentAnalysis 스키마 유효성
- `IntentAnalysis` Pydantic 모델로 파싱 가능
- `intent_category`가 4개 중 하나
- `recommended_arc_id`가 6개 아크 중 하나
- `emotional_keywords` 3~5개

### G3.5-2: 매칭 정확도
- 각 시나리오의 "기대 매칭" 도서가 추천 결과에 **1개 이상 포함**
- `match_score` > 0.3 (최소 기준)
- 연령 범위 벗어난 도서가 추천되지 않음

### G3.5-3: 가이드 품질 — why_this_book
- 2~3문장 이상
- `trigger_situation`의 핵심 키워드가 포함 (예: "동생", "유치원", "어둠")
- 판단/비교 표현 없음 (안전 규칙 준수)

### G3.5-4: 가이드 품질 — reading_questions
- 3~5개 질문
- 열린 질문 형태 ("~할까?", "~었을까?" 등)
- 닫힌 질문 없음 ("맞지?", "그렇지?" 등)

### G3.5-5: 가이드 품질 — conversation_guide
- 3~4개 대화 주제
- 책 내용과 아이의 실제 경험을 연결하는 구조
- 아이의 나이에 맞는 어휘 수준

### G3.5-6: 전환 유도 구조
- `has_custom_story_option` = true
- `custom_story_prompt` 존재하며 따뜻한 톤
- `intent_analysis` 필드 포함 (유료 전환 시 재분석 불필요)

### G3.5-7: 안전성
- 가이드 텍스트에 `safety-rails.json`의 금지어 없음
- 판단/비교/훈계 표현 없음
- 아이 이름이 가이드에 자연스럽게 사용되거나 사용되지 않음 (기계적 삽입 금지)

---

## 실행 방법

### 방법 1: pytest 통합 테스트 (권장)

```bash
cd packages/backend
pytest tests/quality_gates/test_g3_5_recommendation.py -v --run-integration
```

테스트 파일 위치: `packages/backend/tests/quality_gates/test_g3_5_recommendation.py`

### 방법 2: 수동 검증 스크립트

```bash
cd packages/backend
python tests/run_g3_5_generation.py    # 10개 시나리오 추천 생성 → g3_5_results.json
python tests/run_g3_5_validation.py    # 결과 검증 + 리포트 출력
```

---

## 판정 기준

| 등급 | 기준 |
|------|------|
| **PASS** | 10개 중 8개 이상 시나리오에서 G3.5-1~7 전부 통과 |
| **CONDITIONAL** | 10개 중 6~7개 통과. 실패 시나리오 분석 후 프롬프트 조정 |
| **FAIL** | 5개 이하 통과. BookRecommender 로직 또는 시드 데이터 재검토 필요 |

---

## 파일 구조

```
packages/backend/tests/
├── quality_gates/
│   └── test_g3_5_recommendation.py    # pytest 통합 테스트 (작성 필요)
├── run_g3_5_generation.py             # 생성 스크립트 (작성 필요)
├── run_g3_5_validation.py             # 검증 스크립트 (작성 필요)
└── g3_5_results.json                  # 결과 체크포인트 (자동 생성)
```

---

## 의존성 요약

```
IntentAnalyzer (S12, 기존)
    ↓
BookRecommender (R5)
    ├── DB 매칭: Book + SituationTag (R2)
    └── LLM 가이드: book-recommender-v1.md (R6)
    ↓
BookRecommendationResult (R1 계약)
```

## 주의사항

1. **LLM 호출 비용**: 시나리오당 IntentAnalyzer 1회 + 가이드 생성 1회 = ~$0.05. 10개 전체 ~$0.50.
2. **시드 데이터 의존**: `seed_books.py`로 25권이 적재되어 있어야 함. 적재 안 되면 매칭 결과가 빈 리스트.
3. **API 지연**: 각 시나리오 사이 3초 딜레이 권장 (rate limit 방지).
4. **결과 저장**: `g3_5_results.json`에 체크포인트 저장. 중간 실패 시 이어서 실행 가능.
