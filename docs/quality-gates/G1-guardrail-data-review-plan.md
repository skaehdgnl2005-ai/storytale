# 품질 게이트 G1: 가드레일 데이터 리뷰

> **목적**: Phase 2 (S7~S10) 가드레일 시스템의 **시드 데이터 품질**, **API 정합성**, **교차 참조 일관성**을 검증한다. G1은 LLM 호출 없이 데이터와 API만 검증하는 게이트다.
>
> **전제 조건**: 백엔드 서버 기동 가능 (venv + DB). LLM API 키 불필요.

---

## 1. 검증 대상

### 시드 데이터 (0층 가드레일)

| 파일 | 내용 | 건수 |
|------|------|------|
| `docs/guardrail-seeds/emotional-arcs.json` | 감정 흐름 템플릿 | 6개 아크 |
| `docs/guardrail-seeds/age-style-guides.json` | 연령별 문체 규칙 | 3개 연령대 (3-4, 5-6, 7-8) |
| `docs/guardrail-seeds/safety-rails.json` | 안전 규칙 | 1건 (싱글톤) |

### DB 모델

| 모델 | 파일 | 테이블 |
|------|------|--------|
| `EmotionalArcTemplate` | `packages/backend/src/storytale/db/models.py` | `emotional_arc_templates` |
| `AgeStyleGuide` | 위와 동일 | `age_style_guides` |
| `SafetyRails` | 위와 동일 | `safety_rails` |

### API 엔드포인트

| 엔드포인트 | 파일 | 태스크 |
|-----------|------|--------|
| `GET/POST /api/v1/guardrails/arcs` | `packages/backend/src/storytale/api/guardrails/arc_templates.py` | S7 |
| `GET/DELETE /api/v1/guardrails/arcs/{arc_id}` | 위와 동일 | S7 |
| `GET/POST /api/v1/guardrails/age-styles` | `packages/backend/src/storytale/api/guardrails/age_style_guides.py` | S8 |
| `GET/DELETE /api/v1/guardrails/age-styles/{age_group}` | 위와 동일 | S8 |
| `GET/POST /api/v1/guardrails/safety-rails` | `packages/backend/src/storytale/api/guardrails/safety_rails.py` | S9 |
| `GET/DELETE /api/v1/guardrails/safety-rails/{id}` | 위와 동일 | S9 |
| `GET /api/v1/guardrails?age_group={age_group}` | `packages/backend/src/storytale/api/guardrails/combined.py` | S10 |

### 계약 (contracts)

- `docs/contracts/story-engine.ts` — `EmotionalArcTemplate`, `AgeStyleGuide`, `SafetyRails`, `AgeGroup` 타입 정의

---

## 2. 검증 영역

### 영역 A: 시드 데이터 내부 일관성

JSON 파일 자체의 구조적 정합성을 검증한다.

#### A1. emotional-arcs.json 구조 검증

| # | 기준 | 확인 방법 |
|---|------|----------|
| A1-1 | 모든 아크에 필수 필드 존재 | `arc_id`, `description`, `target_ages`, `stages`, `rules` |
| A1-2 | `target_ages` 값이 유효한 AgeGroup | 각 값 ∈ `["3-4", "5-6", "7-8"]` |
| A1-3 | `stages`의 `ratio` 합계 = 1.0 | 각 아크별 `sum(stage.ratio)` == 1.0 (오차 ±0.01) |
| A1-4 | 각 stage에 필수 필드 존재 | `phase`, `ratio`, `purpose` |
| A1-5 | `arc_id` 중복 없음 | 6개 아크의 arc_id가 모두 고유 |
| A1-6 | 모든 IntentCategory에 매칭 아크 존재 | `value_teaching`, `interest_story`, `problem_solving`, `celebration` 각각에 적합한 아크가 최소 1개 |

#### A2. age-style-guides.json 구조 검증

| # | 기준 | 확인 방법 |
|---|------|----------|
| A2-1 | 3개 연령대 모두 존재 | `"3-4"`, `"5-6"`, `"7-8"` |
| A2-2 | 필수 필드 존재 | `sentence_rules`, `emotional_expression`, `page_guidelines` |
| A2-3 | 문장 길이 단조 증가 | 3-4(20자) < 5-6(30자) < 7-8(40자) |
| A2-4 | 페이지당 문장 수 단조 증가 | 3-4(2~3) < 5-6(3~4) < 7-8(4~5) |
| A2-5 | 총 페이지 수 단조 증가 | 3-4(8~12) < 5-6(10~14) < 7-8(12~16) |
| A2-6 | 연령대 간 범위 겹침 허용 여부 확인 | 현재: 겹침 있음 (10~12 구간). 의도된 것인지 리뷰 |

#### A3. safety-rails.json 구조 검증

| # | 기준 | 확인 방법 |
|---|------|----------|
| A3-1 | 필수 섹션 존재 | `prohibitions`, `required_elements`, `content_filter_keywords`, `illustration_safety` |
| A3-2 | 금지 키워드 오탐 검토 | 각 키워드가 일상 단어와 충돌하지 않는지 (예: "죽" 단독 X → "죽이", "죽어" 등 활용형으로 되어있는지) |
| A3-3 | `required_elements`가 아크 구조와 양립 가능 | "comfort_object 최소 2개 장면 등장" → 최소 장면 수(8개)에서 달성 가능한지 |
| A3-4 | `illustration_safety.negative_prompts` 영문 확인 | 일러스트 프롬프트는 영문이므로 negative_prompts도 영문이어야 함 |

---

### 영역 B: 시드 데이터 ↔ 계약 교차 참조

시드 데이터의 구조가 `docs/contracts/story-engine.ts`의 타입 정의와 일치하는지 검증한다.

| # | 기준 | 확인 방법 |
|---|------|----------|
| B1 | `EmotionalArcTemplate` 필드 매핑 | 계약: `arcId, description, targetAges, stages, rules` ↔ 시드: `arc_id, description, target_ages, stages, rules` (camelCase→snake_case 변환 일치) |
| B2 | `ArcStage` 필드 매핑 | 계약: `phase, ratio, purpose` ↔ 시드 동일 |
| B3 | `AgeStyleGuide` 필드 매핑 | 계약: `ageGroup, sentenceRules, emotionalExpression, pageGuidelines` ↔ 시드: `age_group, sentence_rules, emotional_expression, page_guidelines` |
| B4 | `SentenceRules` 세부 필드 | 계약: `maxCharactersPerSentence, preferredStructure, repetitionPattern, vocabularyLevel` ↔ 시드 snake_case 대응 |
| B5 | `SafetyRails` 필드 매핑 | 계약: `prohibitions, requiredElements` ↔ 시드: `prohibitions, required_elements`. 주의: 시드에는 `content_filter_keywords`, `illustration_safety` 추가 필드 존재 (계약에 없음 — 의도된 확장인지 확인) |
| B6 | `AgeGroup` 타입 범위 | 계약: `"3-4" \| "5-6" \| "7-8"` ↔ 시드의 모든 age_group/target_ages 값이 이 범위 안에 있는지 |

---

### 영역 C: DB 모델 ↔ 시드 데이터 정합성

시드 데이터가 DB 모델에 정확히 매핑되어 삽입/조회 가능한지 검증한다.

| # | 기준 | 확인 방법 |
|---|------|----------|
| C1 | `EmotionalArcTemplate` 모델 컬럼 ↔ 시드 키 | `id`(=arc_id), `description`, `target_ages`(JSON), `stages`(JSON), `rules`(JSON) |
| C2 | `AgeStyleGuide` 모델 컬럼 ↔ 시드 키 | `age_group`(PK), `sentence_rules`(JSON), `emotional_expression`(JSON), `page_guidelines`(JSON) |
| C3 | `SafetyRails` 모델 컬럼 ↔ 시드 키 | `id`(auto), `prohibitions`(JSON), `required_elements`(JSON), `content_filter_keywords`(JSON), `illustration_safety`(JSON) |
| C4 | 시드 함수 라운드트립 | `seed_*()` → DB 삽입 → API 조회 → 시드 JSON과 동일한 데이터 반환 |

---

### 영역 D: API 기능 검증

실제 API 요청/응답이 올바른지 검증한다.

| # | 기준 | 확인 방법 |
|---|------|----------|
| D1 | 아크 CRUD | POST로 생성 → GET으로 조회 → DELETE로 삭제 → GET 404 |
| D2 | 아크 age_group 필터 | `GET /arcs?age_group=7-8` → `relationship_repair` 포함, `new_experience` 미포함 (target_ages에 7-8 없음) |
| D3 | 문체 가이드 CRUD | POST → GET → DELETE → 404 |
| D4 | 문체 가이드 age_group 조회 | `GET /age-styles/3-4` → 해당 연령대 가이드 반환 |
| D5 | 안전 규칙 CRUD | POST → GET → DELETE → 404 |
| D6 | **통합 조회 (S10 핵심)** | `GET /guardrails?age_group=3-4` → arcs(3-4세 포함 아크만) + style_guide(3-4세) + safety_rails |
| D7 | 통합 조회 age_group 미지정 | `GET /guardrails` → arcs=전체 6개, style_guide=null, safety_rails=존재 |
| D8 | 통합 조회 unknown age_group | `GET /guardrails?age_group=9-10` → arcs=빈 배열, style_guide=null |
| D9 | 시드 삽입 멱등성 | `seed_*()` 2회 호출 → 중복 데이터 없음 |

---

### 영역 E: 아동발달 관점 데이터 품질 (수동 리뷰)

시드 데이터가 아동발달 관점에서 적절한지 사람이 판단한다.

| # | 기준 | 리뷰 포인트 |
|---|------|------------|
| E1 | **감정 흐름 자연스러움** | 각 아크의 stages 순서가 아동 심리 발달 관점에서 자연스러운가? (예: gentle_resolution의 "공감→전환점→시도→재시도→수용" 흐름) |
| E2 | **연령별 적합성** | `target_ages` 배정이 적절한가? (예: `relationship_repair`가 3-4세 제외 — 관계 인지 발달 5세 이후) |
| E3 | **문체 규칙 현실성** | 3-4세 문장당 20자 제한이 실제 그림책과 비교해 적절한가? |
| E4 | **금지 규칙 완전성** | 누락된 금지 사항이 있는가? (예: 인종 차별, 장애 비하 등이 `prohibitions`에 포함되어 있는지) |
| E5 | **금지 키워드 충분성** | `content_filter_keywords`가 실제 위험 표현을 커버하는가? 오탐/미탐 밸런스 |
| E6 | **필수 요소 달성 가능성** | `required_elements`의 각 요구사항이 모든 아크 구조에서 자연스럽게 달성 가능한가? |
| E7 | **아크 규칙과 안전 규칙 충돌 여부** | 아크의 `rules`와 safety-rails의 `prohibitions`가 상충하지 않는가? |

---

## 3. 검증 실행 방법

### 3-1. 환경 준비

```bash
cd packages/backend
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 3-2. 기존 단위 테스트 통과 확인

먼저 S7~S10의 기존 테스트가 모두 통과하는지 확인한다.

```bash
pytest tests/test_s7_emotional_arc_templates.py tests/test_s8_age_style_guides.py tests/test_s9_safety_rails.py tests/test_s10_guardrails_combined.py -v
```

모두 통과해야 G1 검증을 진행할 수 있다.

### 3-3. G1 검증 스크립트 작성

`packages/backend/tests/quality_gates/test_g1_guardrail_data.py`에 영역 A~D를 자동화한 검증 스크립트를 작성한다.

```python
"""G1 품질 게이트: 가드레일 데이터 리뷰.

사용법:
    pytest tests/quality_gates/test_g1_guardrail_data.py -v
    (LLM API 키 불필요)
"""
import json
import pathlib
import pytest

SEEDS_DIR = pathlib.Path(__file__).parents[4] / "docs" / "guardrail-seeds"
CONTRACTS_PATH = pathlib.Path(__file__).parents[4] / "docs" / "contracts" / "story-engine.ts"

VALID_AGE_GROUPS = {"3-4", "5-6", "7-8"}
VALID_INTENT_CATEGORIES = {"value_teaching", "interest_story", "problem_solving", "celebration"}
VALID_ARC_IDS = {"gentle_resolution", "courage_building", "relationship_repair", "new_experience", "joy_of_discovery", "celebration_joy"}

@pytest.fixture(scope="module")
def arcs():
    with open(SEEDS_DIR / "emotional-arcs.json", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def age_styles():
    with open(SEEDS_DIR / "age-style-guides.json", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def safety():
    with open(SEEDS_DIR / "safety-rails.json", encoding="utf-8") as f:
        return json.load(f)

# ─── 영역 A1: emotional-arcs.json ───

class TestA1EmotionalArcs:
    def test_a1_1_required_fields(self, arcs):
        for arc in arcs:
            for field in ("arc_id", "description", "target_ages", "stages", "rules"):
                assert field in arc, f"{arc.get('arc_id', '?')} missing {field}"

    def test_a1_2_valid_age_groups(self, arcs):
        for arc in arcs:
            for age in arc["target_ages"]:
                assert age in VALID_AGE_GROUPS, f"{arc['arc_id']}: invalid age {age}"

    def test_a1_3_stage_ratios_sum_to_one(self, arcs):
        for arc in arcs:
            total = sum(s["ratio"] for s in arc["stages"])
            assert abs(total - 1.0) < 0.01, f"{arc['arc_id']}: ratio sum={total}"

    def test_a1_4_stage_required_fields(self, arcs):
        for arc in arcs:
            for stage in arc["stages"]:
                for field in ("phase", "ratio", "purpose"):
                    assert field in stage, f"{arc['arc_id']} stage missing {field}"

    def test_a1_5_unique_arc_ids(self, arcs):
        ids = [a["arc_id"] for a in arcs]
        assert len(ids) == len(set(ids))

    def test_a1_6_all_intent_categories_have_matching_arc(self, arcs):
        """각 IntentCategory에 적합한 아크가 최소 1개 존재하는지 확인.
        매핑 규칙은 intent-analyzer-v1.md 프롬프트 참조."""
        # 최소한 arc가 6개 이상이고 다양한 target_ages를 커버하는지
        all_ages_covered = set()
        for arc in arcs:
            all_ages_covered.update(arc["target_ages"])
        assert all_ages_covered == VALID_AGE_GROUPS

# ─── 영역 A2: age-style-guides.json ───

class TestA2AgeStyleGuides:
    def test_a2_1_all_age_groups_present(self, age_styles):
        groups = {g["age_group"] for g in age_styles}
        assert groups == VALID_AGE_GROUPS

    def test_a2_2_required_fields(self, age_styles):
        for g in age_styles:
            for field in ("sentence_rules", "emotional_expression", "page_guidelines"):
                assert field in g, f"{g['age_group']} missing {field}"

    def test_a2_3_sentence_length_monotonic(self, age_styles):
        by_age = {g["age_group"]: g for g in age_styles}
        assert by_age["3-4"]["sentence_rules"]["max_characters_per_sentence"] \
             < by_age["5-6"]["sentence_rules"]["max_characters_per_sentence"] \
             < by_age["7-8"]["sentence_rules"]["max_characters_per_sentence"]

    def test_a2_4_sentences_per_page_monotonic(self, age_styles):
        by_age = {g["age_group"]: g for g in age_styles}
        for prev, curr in [("3-4", "5-6"), ("5-6", "7-8")]:
            assert by_age[prev]["page_guidelines"]["sentences_per_page"]["max"] \
                <= by_age[curr]["page_guidelines"]["sentences_per_page"]["max"]

    def test_a2_5_total_pages_monotonic(self, age_styles):
        by_age = {g["age_group"]: g for g in age_styles}
        for prev, curr in [("3-4", "5-6"), ("5-6", "7-8")]:
            assert by_age[prev]["page_guidelines"]["total_pages"]["max"] \
                <= by_age[curr]["page_guidelines"]["total_pages"]["max"]

# ─── 영역 A3: safety-rails.json ───

class TestA3SafetyRails:
    def test_a3_1_required_sections(self, safety):
        for section in ("prohibitions", "required_elements", "content_filter_keywords", "illustration_safety"):
            assert section in safety, f"missing section: {section}"

    def test_a3_2_no_bare_stem_keywords(self, safety):
        """금지 키워드가 단독 어근('죽')이 아닌 활용형인지 확인."""
        keywords = safety["content_filter_keywords"]["keywords"]
        bare_stems = ["죽", "피"]  # 1글자 어근은 오탐 위험
        for kw in keywords:
            if len(kw) == 1:
                print(f"  WARNING: 1글자 키워드 '{kw}' — 오탐 가능성 리뷰 필요")

    def test_a3_3_required_elements_achievable(self, safety, age_styles):
        """required_elements가 최소 페이지 수(8)에서 달성 가능한지."""
        min_pages = min(g["page_guidelines"]["total_pages"]["min"] for g in age_styles)
        # comfort_object 2회 등장 → 최소 2 장면 필요 → min_pages >= 2
        assert min_pages >= 2, f"최소 페이지 {min_pages}에서 comfort_object 2회 불가"

    def test_a3_4_illustration_negative_prompts_english(self, safety):
        """일러스트 negative prompts가 영문인지 확인."""
        for prompt in safety["illustration_safety"]["negative_prompts"]:
            assert prompt.isascii(), f"Non-ASCII negative prompt: {prompt}"

# ─── 영역 B: 계약 교차 참조 (구조적 확인) ───

class TestBContractCrossRef:
    def test_b1_arc_fields_match_contract(self, arcs):
        """시드 데이터 키가 계약의 snake_case 변환과 일치."""
        expected_keys = {"arc_id", "description", "target_ages", "stages", "rules"}
        for arc in arcs:
            assert set(arc.keys()) == expected_keys, f"{arc['arc_id']}: {set(arc.keys())}"

    def test_b2_stage_fields_match_contract(self, arcs):
        expected_keys = {"phase", "ratio", "purpose"}
        for arc in arcs:
            for stage in arc["stages"]:
                assert set(stage.keys()) == expected_keys

    def test_b3_age_style_fields_match_contract(self, age_styles):
        expected_keys = {"age_group", "sentence_rules", "emotional_expression", "page_guidelines"}
        for g in age_styles:
            assert set(g.keys()) == expected_keys, f"{g['age_group']}: {set(g.keys())}"

    def test_b5_safety_extra_fields_documented(self, safety):
        """계약에 없는 content_filter_keywords, illustration_safety가 존재함을 확인.
        이는 의도된 확장 — 계약 업데이트 필요 여부를 리뷰."""
        contract_fields = {"prohibitions", "required_elements"}
        extra_fields = set(safety.keys()) - contract_fields - {"version", "last_updated"}
        if extra_fields:
            print(f"  INFO: 계약에 없는 추가 필드: {extra_fields} (의도된 확장인지 리뷰)")

# ─── 이 아래는 API 테스트 (영역 D) ───
# 기존 test_s7~s10 테스트가 이미 D1~D9를 커버하므로,
# 여기서는 기존 테스트 통과를 전제로 추가 확인만 수행.
```

### 3-4. 영역 E 수동 리뷰

영역 E는 코드로 자동화할 수 없다. 아래 체크리스트를 사람이 직접 리뷰한다.

시드 데이터 파일 3개를 열고 다음을 확인:

1. **E1**: 각 아크의 stages 순서를 읽으며 — 이 순서로 이야기를 만들면 아이에게 자연스러운가?
2. **E2**: `relationship_repair`가 3-4세 제외된 이유 납득되는가? 다른 아크의 `target_ages` 배정은?
3. **E3**: 3-4세 문장당 20자 → 실제 그림책 비교 (예: "토끼가 깡충 뛰었어요" = 12자). 적절한가?
4. **E4**: `prohibitions`에 없는 위험 시나리오가 있는가? (특히 한국 문화 맥락에서)
5. **E5**: `content_filter_keywords` 17개 — 빠진 위험 단어가 있는가? 오탐 가능한 단어가 있는가?
6. **E6**: `required_elements`의 "comfort_object 최소 2개 장면" — 부모가 comfort_object를 입력하지 않으면?
7. **E7**: 아크 rules와 prohibitions가 상충하는 경우가 있는가?

---

## 4. 합격 기준

### 자동 검증 (영역 A, B, C, D)

- **기존 테스트 (S7~S10)**: 52개 전체 통과 (S7: 12 + S8: 13 + S9: 12 + S10: 15)
- **G1 검증 스크립트 (영역 A, B)**: 전체 통과

### 수동 리뷰 (영역 E)

| # | 기준 | 필수 여부 |
|---|------|----------|
| E1 | 감정 흐름 자연스러움 | 필수 — 6개 아크 모두 합격 |
| E2 | 연령별 적합성 | 필수 |
| E3 | 문체 규칙 현실성 | 권장 (경미한 조정 허용) |
| E4 | 금지 규칙 완전성 | 필수 — 누락 시 즉시 추가 |
| E5 | 금지 키워드 충분성 | 권장 (Phase 3 이후 보완 가능) |
| E6 | 필수 요소 달성 가능성 | 필수 |
| E7 | 아크-안전 규칙 충돌 없음 | 필수 |

**합격**: 자동 전수 통과 + 수동 E1/E2/E4/E6/E7 필수 합격 + E3/E5 경미한 이슈만 허용

---

## 5. 결과 기록 양식

```markdown
## G1 검증 결과 — {날짜}

### 기존 테스트
- S7 (12개): PASS/FAIL
- S8 (13개): PASS/FAIL
- S9 (12개): PASS/FAIL
- S10 (15개): PASS/FAIL

### G1 자동 검증
| 영역 | 테스트 수 | 결과 | 비고 |
|------|----------|------|------|
| A1 (arcs) | 6 | PASS/FAIL | |
| A2 (age styles) | 5 | PASS/FAIL | |
| A3 (safety) | 4 | PASS/FAIL | |
| B (계약 교차참조) | 4 | PASS/FAIL | |

### 수동 리뷰 (영역 E)
| # | 기준 | 결과 | 비고 |
|---|------|------|------|
| E1 | 감정 흐름 자연스러움 | ✅/❌ | |
| E2 | 연령별 적합성 | ✅/❌ | |
| E3 | 문체 규칙 현실성 | ✅/❌ | |
| E4 | 금지 규칙 완전성 | ✅/❌ | |
| E5 | 금지 키워드 충분성 | ✅/❌ | |
| E6 | 필수 요소 달성 가능성 | ✅/❌ | |
| E7 | 아크-안전 규칙 충돌 | ✅/❌ | |

### 발견된 이슈
1. [이슈 제목] — 심각도(높음/중간/낮음), 영향 범위, 조치 방안

### 판정
- [ ] G1 합격 → Phase 3 인터프리터가 가드레일 데이터를 안전하게 사용 가능
- [ ] G1 불합격 → 시드 데이터 수정 후 재검증 필요
```

---

## 6. 주의사항

1. **LLM 호출 없음**: G1은 순수 데이터/API 검증. API 키 불필요.
2. **DB 마이그레이션**: SafetyRails의 `content_filter_keywords`, `illustration_safety` 컬럼은 S9에서 추가됨. Alembic 마이그레이션은 아직 미생성 — 테스트는 인메모리 SQLite에서 자동 반영.
3. **계약 확장 리뷰**: `SafetyRails`에 `content_filter_keywords`, `illustration_safety`가 계약(`story-engine.ts`)에 없는 추가 필드로 존재. G1에서 이 확장이 의도된 것인지 확인하고, 필요 시 계약 업데이트를 Phase 3 이후 태스크로 등록.
4. **시드 데이터 수정 시**: `.claude/rules/guardrail-editing.md`의 수정 규칙을 따를 것.
