# 가드레일 시드 데이터 수정 규칙

`docs/guardrail-seeds/` 내의 모든 JSON 파일에 적용.

## 수정 시 검증 체크리스트
1. **JSON 유효성**: 파싱 에러 없는지 확인.
2. **교차 참조 일관성**:
   - `emotional-arcs.json`의 `target_ages` ↔ `age-style-guides.json`의 `age_group` 일치.
   - 모든 `IntentCategory` (contracts 정의)에 매칭 아크가 최소 1개 존재.
3. **safety-rails.json 특별 규칙**:
   - `content_filter`는 3종 구조: `exact_block`(문맥 무관 차단), `pattern_block`(정규식 패턴), `allowlist`(오탐 예외).
   - 새 금지어 추가 시 분류 기준: 오탐 위험이 없으면 `exact_block`, 활용형 구분이 필요하면 `pattern_block`, 알려진 오탐은 `allowlist`에 추가.
   - `pattern_block` 패턴 추가 시 `allowlist`와 교차 테스트 필수. `pytest tests/test_safety_checker.py -v`로 검증.
4. **age-style-guides.json 특별 규칙**:
   - `text_per_page`는 숫자 기반 구조화 형식.
   - 연령대 간 문장 길이·복잡도가 단조 증가하는지 확인.

## 수정 후 필수 작업
- 관련 프롬프트(`docs/prompts/`)에서 해당 데이터 참조 부분 확인.
- contracts 타입 스키마와 여전히 일치하는지 확인.

> **TODO(Post-S1)**: 프로젝트 초기화 후 이 검증을 자동 hook으로 전환할 것.
