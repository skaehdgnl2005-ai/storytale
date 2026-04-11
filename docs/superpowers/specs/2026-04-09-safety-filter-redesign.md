# 안전 필터 재설계 — 2-Tier 키워드 검증

> 작성일: 2026-04-09  
> 트리거: G2 검증 이슈1 (금지어 오탐), 이슈2·3 (Gemini fallback 빈 응답)  
> 범위: `safety-rails.json` 스키마 + 키워드 검증 로직 + Gemini fallback 강화

---

## 1. 문제 요약

### 1-1. 단순 부분문자열 매칭의 한계

현재 `scene_planner.py:136`과 `plan_reviser.py:232`에서 동일한 방식:

```python
if keyword in scene.description:  # 부분문자열 매칭
```

한국어는 교착어로, 형태소가 결합하면서 무관한 단어 안에 금지어가 포함됨:
- `반죽이` ⊃ `죽이` → 케이크 만들기 장면 차단 (G2 시나리오4)
- `피아노` ⊃ `피` → 음악 장면 차단 가능
- `칼국수` ⊃ `칼` → 요리 장면 차단 가능

### 1-2. LLM 2차 판단 미구현

`safety-rails.json`의 note에 "키워드 검출 후 LLM으로 2차 판단 권장"이 명시되어 있으나 구현되지 않음.

### 1-3. 검증 로직 중복

`scene_planner.py`의 `validate_scene_plan()`과 `plan_reviser.py`의 `_validate_safety_only()`에 동일한 키워드 매칭 코드가 중복.

### 1-4. Gemini fallback 빈 응답

Claude 타임아웃 시 Gemini fallback에서 `response.text = None` 반환 시 적절한 재시도/복구 없이 `LLMClientError` 발생.

---

## 2. 설계

### 2-1. safety-rails.json 스키마 변경

기존 `content_filter_keywords`의 flat keyword 리스트를 3종 분류로 재구조화:

```json
{
  "content_filter": {
    "description": "생성된 텍스트의 안전 검증 규칙. Tier 1(패턴) → Tier 2(LLM 문맥 판단) 순서로 적용.",
    "exact_block": [
      "바보", "멍청", "못생긴", "뚱뚱",
      "벌 줄", "혼내", "혼날",
      "엄마가 슬퍼", "아빠가 화나",
      "남자답", "여자답",
      "착한 아이", "나쁜 아이"
    ],
    "pattern_block": [
      {"pattern": "죽이고|죽이는|죽이자|죽이다|죽여", "intent": "살해 표현"},
      {"pattern": "죽어|죽겠어|죽을래|죽고\\s*싶", "intent": "죽음 표현"},
      {"pattern": "피가|피를|피투성이|피범벅|코피|피났|피 나", "intent": "유혈 표현"},
      {"pattern": "칼로|칼을|칼이|칼날|칼에", "intent": "흉기 표현"}
    ],
    "allowlist": [
      "반죽이", "반죽을", "반죽", "미역죽", "팥죽", "호박죽", "죽을 끓", "죽을 만들",
      "피아노", "피자", "피부", "피리", "피곤", "피우", "행복피우",
      "칼국수", "뮤지칼"
    ]
  }
}
```

**분류 기준:**
- `exact_block`: 문맥 무관하게 항상 차단. 오탐 위험이 낮은 다어절 표현.
- `pattern_block`: 정규식 패턴. 의도된 활용형만 매칭. `intent` 필드는 Tier 2 LLM 판단 시 컨텍스트로 전달.
- `allowlist`: 알려진 오탐. Tier 1 매칭 전 먼저 확인하여 즉시 통과.

### 2-2. 검증 로직 통합 — safety_checker.py

새 모듈 `packages/backend/src/storytale/interpreter/safety_checker.py`:

```
SafetyChecker
├── check_text(text) → SafetyCheckResult
│   ├── Step 1: allowlist 스캔 → 허용 단어를 플레이스홀더로 치환
│   ├── Step 2: exact_block 매칭 → 즉시 위반
│   └── Step 3: pattern_block 정규식 매칭 → 매칭 시 Tier 2로
├── check_context(text, matches) → bool  [Tier 2]
│   └── LLM에 문장 + 매칭된 패턴의 intent를 전달하여 실제 위반 여부 판단
└── validate_plan(plan, safety_rails) → None | raise SafetyError
    └── 모든 scene.description에 check_text 적용
```

**Tier 2 LLM 호출 설계:**
- 호출 조건: `pattern_block` 매칭 시에만 (exact_block은 Tier 2 없이 즉시 차단)
- 프롬프트: 짧은 yes/no 판단. temperature=0, max_tokens=50
- fallback: LLM 호출 실패 시 안전 우선(차단)

### 2-3. scene_planner.py / plan_reviser.py 변경

두 파일의 중복 검증 로직을 `SafetyChecker.validate_plan()` 호출로 교체:

```python
# Before (scene_planner.py:132-141, plan_reviser.py:226-237)
for scene in plan.scenes:
    for keyword in filter_keywords:
        if keyword in scene.description:
            raise ScenePlanSafetyError(...)

# After
checker = SafetyChecker(safety_rails, llm_client)
await checker.validate_plan(plan)  # 내부에서 Tier 1 → Tier 2 처리
```

`validate_scene_plan()` 함수는 기존 시그니처를 유지하되, 내부 키워드 검증 부분만 `SafetyChecker`에 위임.

### 2-4. Gemini fallback 빈 응답 처리

`gemini_provider.py`에서 `response.text = None` 시:
1. 빈 응답을 재시도 가능 에러로 분류 (현재: 즉시 `LLMClientError`)
2. 최대 1회 재시도 (safety_harm_category 체크 로그 추가)
3. 재시도 실패 시 기존과 동일하게 `LLMClientError` 발생

---

## 3. 영향 범위

| 파일 | 변경 유형 |
|------|-----------|
| `docs/guardrail-seeds/safety-rails.json` | 스키마 변경 (content_filter_keywords → content_filter) |
| `packages/backend/src/storytale/interpreter/safety_checker.py` | **신규** |
| `packages/backend/src/storytale/interpreter/scene_planner.py` | 키워드 검증 → SafetyChecker 위임 |
| `packages/backend/src/storytale/interpreter/plan_reviser.py` | 키워드 검증 → SafetyChecker 위임 |
| `packages/backend/src/storytale/interpreter/gemini_provider.py` | 빈 응답 재시도 |
| `packages/backend/src/storytale/api/guardrails/safety_rails.py` | Pydantic 스키마 업데이트 |
| `packages/backend/tests/test_safety_checker.py` | **신규** |
| `packages/backend/tests/test_s13_scene_planner.py` | 기존 안전 검증 테스트 조정 |
| `packages/backend/tests/test_s14_plan_reviser.py` | 기존 안전 검증 테스트 조정 |

---

## 4. 기각한 대안

| 대안 | 기각 이유 |
|------|-----------|
| 형태소 분석기(Mecab/konlpy) 도입 | C 라이브러리 의존성, 배포 복잡도 증가. 프로젝트 규모에 비해 과도. |
| 키워드 활용형만 교체 (패턴 없이) | `피`, `칼` 같은 1글자는 활용형으로 커버 불가. 새로운 오탐 계속 발생. |
| LLM 2차 판단만 (Tier 1 없이) | 매 장면마다 LLM 호출은 비용·지연 과다. |

---

## 5. 성공 기준

1. G2 시나리오4 재검증 통과: "케이크 반죽이 뭉쳐졌어요" 류 표현이 오탐 없이 통과
2. 기존 안전 차단 유지: "죽이고 싶어", "피가 났어" 등은 여전히 차단
3. 기존 테스트 전체 통과 (스키마 변경에 맞춰 조정 후)
4. Gemini 빈 응답 시 1회 재시도 후 실패하면 기존과 동일하게 에러 발생
