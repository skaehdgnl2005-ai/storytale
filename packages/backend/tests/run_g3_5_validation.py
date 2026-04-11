"""G3.5 품질 게이트 — 생성 결과 검증 스크립트.

run_g3_5_generation.py가 생성한 g3_5_results.json을 로드하여
G3.5-1 ~ G3.5-7 기준으로 검증하고 리포트를 출력한다.

실행:
    cd packages/backend
    python tests/run_g3_5_validation.py
"""

import json
import os
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 프로젝트 경로
_BACKEND_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, _BACKEND_SRC)

from storytale.interpreter.safety_checker import SafetyChecker  # noqa: E402

# ---------------------------------------------------------------------------
# 경로 / 상수
# ---------------------------------------------------------------------------

_PROJECT_ROOT = pathlib.Path(__file__).parents[3]
_SEEDS_DIR = _PROJECT_ROOT / "docs" / "guardrail-seeds"
_RESULTS_PATH = pathlib.Path(__file__).parent / "g3_5_results.json"

VALID_CATEGORIES = frozenset(
    {"value_teaching", "interest_story", "problem_solving", "celebration"}
)
VALID_ARC_IDS = frozenset(
    {
        "gentle_resolution",
        "courage_building",
        "relationship_repair",
        "new_experience",
        "joy_of_discovery",
        "celebration_joy",
    }
)

# 닫힌 질문 패턴
_CLOSED_QUESTION_RE = re.compile(r"(맞지\?|그렇지\?|알지\?|아니야\?|하지\?)")

# 시나리오별 기대 도서 + trigger 키워드
EXPECTED = {
    "1": {"titles": ["피터의 의자", "나는 형이니까"], "keywords": ["동생"]},
    "2": {"titles": ["당근 유치원"], "keywords": ["유치원"]},
    "3": {"titles": ["잘 자, 작은 곰아", "까만 밤에"], "keywords": ["어둠", "무서워", "잠"]},
    "4": {"titles": ["싫어 싫어"], "keywords": ["싫", "반항"]},
    "5": {"titles": ["공룡이 쿵쿵쿵"], "keywords": ["공룡", "트리케라톱스"]},
    "6": {"titles": ["무지개 물고기"], "keywords": ["장난감", "빌려주", "나눔", "친구"]},
    "7": {"titles": ["괜찮아"], "keywords": ["실수", "자신감", "울"]},
    "8": {"titles": ["생일 축하해!"], "keywords": ["생일", "특별"]},
    "9": {"titles": ["심심한 늑대", "무지개 물고기"], "keywords": ["친구"]},
    "10": {"titles": ["이 닦기 싫어!"], "keywords": ["이", "닦"]},
}


# ---------------------------------------------------------------------------
# 검증 함수
# ---------------------------------------------------------------------------


def validate_g35_1(intent: dict) -> list[str]:
    """G3.5-1: IntentAnalysis 스키마 유효성."""
    errors = []
    if intent.get("intent_category") not in VALID_CATEGORIES:
        errors.append(f"intent_category '{intent.get('intent_category')}' 유효하지 않음")
    if intent.get("recommended_arc_id") not in VALID_ARC_IDS:
        errors.append(f"arc_id '{intent.get('recommended_arc_id')}' 유효하지 않음")
    kw_count = len(intent.get("emotional_keywords", []))
    if not (3 <= kw_count <= 5):
        errors.append(f"emotional_keywords {kw_count}개 (3~5개 필요)")
    return errors


def validate_g35_2(recs: list[dict], sid: str, child_age: int) -> list[str]:
    """G3.5-2: 매칭 정확도."""
    errors = []
    if not recs:
        errors.append("추천 결과가 비어있음")
        return errors

    rec_titles = [r["book"]["title"] for r in recs]
    expected_titles = EXPECTED.get(sid, {}).get("titles", [])

    matched = any(
        any(exp in title for title in rec_titles)
        for exp in expected_titles
    )
    if not matched:
        errors.append(f"기대 도서 {expected_titles} 중 하나도 없음. 실제: {rec_titles}")

    for r in recs:
        if r["match_score"] <= 0.3:
            errors.append(f"{r['book']['title']} match_score={r['match_score']} <= 0.3")
        book = r["book"]
        if not (book["target_age_min"] - 1 <= child_age <= book["target_age_max"] + 1):
            errors.append(f"{book['title']} 연령 범위 벗어남")
    return errors


def validate_g35_3(recs: list[dict], sid: str) -> list[str]:
    """G3.5-3: why_this_book 품질."""
    errors = []
    keywords = EXPECTED.get(sid, {}).get("keywords", [])

    for r in recs:
        why = r.get("why_this_book", "")
        title = r["book"]["title"]
        if not why:
            errors.append(f"{title}: why_this_book 비어있음")
            continue
        sentences = [s.strip() for s in re.split(r"[.!?。]", why) if s.strip()]
        if len(sentences) < 2:
            errors.append(f"{title}: why_this_book 2문장 미만")
        if not any(kw in why for kw in keywords):
            errors.append(f"{title}: trigger 키워드 {keywords} 미포함")
        for forbidden in ["비교", "다른 아이", "착한 아이", "나쁜 아이"]:
            if forbidden in why:
                errors.append(f"{title}: 판단 표현 '{forbidden}'")
    return errors


def validate_g35_4(recs: list[dict]) -> list[str]:
    """G3.5-4: reading_questions 품질."""
    errors = []
    for r in recs:
        questions = r.get("reading_questions", [])
        title = r["book"]["title"]
        if not (3 <= len(questions) <= 5):
            errors.append(f"{title}: reading_questions {len(questions)}개 (3~5개 필요)")
        for q in questions:
            if _CLOSED_QUESTION_RE.search(q):
                errors.append(f"{title}: 닫힌 질문 '{q[:30]}...'")
    return errors


def validate_g35_5(recs: list[dict]) -> list[str]:
    """G3.5-5: conversation_guide 품질."""
    errors = []
    for r in recs:
        guide = r.get("conversation_guide", [])
        title = r["book"]["title"]
        if not (3 <= len(guide) <= 4):
            errors.append(f"{title}: conversation_guide {len(guide)}개 (3~4개 필요)")
    return errors


def validate_g35_6(result: dict) -> list[str]:
    """G3.5-6: 전환 유도 구조."""
    errors = []
    if result.get("has_custom_story_option") is not True:
        errors.append("has_custom_story_option != true")
    if not result.get("custom_story_prompt"):
        errors.append("custom_story_prompt 비어있음")
    if not result.get("intent_analysis"):
        errors.append("intent_analysis 필드 누락")
    return errors


def validate_g35_7(recs: list[dict], checker: SafetyChecker) -> list[str]:
    """G3.5-7: 안전성."""
    errors = []
    for r in recs:
        for field_name in ("why_this_book", "reading_questions", "conversation_guide"):
            content = r.get(field_name, "")
            if isinstance(content, list):
                content = " ".join(content)
            check = checker.check_text(content)
            if check.blocked:
                errors.append(
                    f"{r['book']['title']}/{field_name}: "
                    f"금지어 '{check.matched_keyword}'"
                )
    return errors


# ---------------------------------------------------------------------------
# 메인 검증 실행
# ---------------------------------------------------------------------------


# 시나리오별 child_age (results에 없을 수 있으므로 하드코딩)
_CHILD_AGES = {
    "1": 5, "2": 4, "3": 4, "4": 3, "5": 4,
    "6": 5, "7": 4, "8": 5, "9": 5, "10": 3,
}


def main() -> None:
    if not _RESULTS_PATH.exists():
        print(f"ERROR: {_RESULTS_PATH} 파일이 없습니다.")
        print("먼저 run_g3_5_generation.py를 실행하세요.")
        sys.exit(1)

    with open(_RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    with open(_SEEDS_DIR / "safety-rails.json", encoding="utf-8") as f:
        safety_rails = json.load(f)
    checker = SafetyChecker(content_filter=safety_rails["content_filter"])

    scenarios = results.get("scenarios", {})
    total_scenarios = 0
    passed_scenarios = 0
    gate_results: dict[str, dict] = {}

    print(f"\n{'='*60}")
    print("G3.5 품질 게이트 검증 리포트")
    print(f"{'='*60}")

    for sid in sorted(scenarios.keys(), key=int):
        data = scenarios[sid]
        total_scenarios += 1

        print(f"\n--- 시나리오 {sid} ---")

        if data.get("status") != "ok":
            print(f"  SKIP: 생성 실패 — {data.get('error', 'unknown')}")
            gate_results[sid] = {"status": "SKIP", "errors": ["생성 실패"]}
            continue

        intent = data.get("intent_analysis", {})
        rec_result = data.get("recommendation", {})
        recs = rec_result.get("recommendations", [])
        child_age = _CHILD_AGES.get(sid, 4)

        all_errors: dict[str, list[str]] = {}
        all_errors["G3.5-1"] = validate_g35_1(intent)
        all_errors["G3.5-2"] = validate_g35_2(recs, sid, child_age)
        all_errors["G3.5-3"] = validate_g35_3(recs, sid)
        all_errors["G3.5-4"] = validate_g35_4(recs)
        all_errors["G3.5-5"] = validate_g35_5(recs)
        all_errors["G3.5-6"] = validate_g35_6(rec_result)
        all_errors["G3.5-7"] = validate_g35_7(recs, checker)

        scenario_pass = True
        for gate_id, errors in all_errors.items():
            status = "PASS" if not errors else "FAIL"
            icon = "✓" if not errors else "✗"
            print(f"  [{gate_id}] {status} {icon}")
            if errors:
                scenario_pass = False
                for e in errors:
                    print(f"         {e}")

        if scenario_pass:
            passed_scenarios += 1
            gate_results[sid] = {"status": "PASS", "errors": []}
        else:
            flat_errors = []
            for errors in all_errors.values():
                flat_errors.extend(errors)
            gate_results[sid] = {"status": "FAIL", "errors": flat_errors}

    # 판정
    print(f"\n{'='*60}")
    print("판정 결과")
    print(f"{'='*60}")
    print(f"  통과: {passed_scenarios}/{total_scenarios}")

    if passed_scenarios >= 8:
        verdict = "PASS"
        print(f"\n  G3.5 품질 게이트: PASS ✓")
        print(f"  10개 중 {passed_scenarios}개 통과 (기준: 8개 이상)")
    elif passed_scenarios >= 6:
        verdict = "CONDITIONAL"
        print(f"\n  G3.5 품질 게이트: CONDITIONAL ⚠")
        print(f"  10개 중 {passed_scenarios}개 통과 (기준: 6~7개)")
        print("  실패 시나리오 분석 후 프롬프트 조정 필요")
    else:
        verdict = "FAIL"
        print(f"\n  G3.5 품질 게이트: FAIL ✗")
        print(f"  10개 중 {passed_scenarios}개 통과 (기준: 5개 이하)")
        print("  BookRecommender 로직 또는 시드 데이터 재검토 필요")

    # 실패 시나리오 요약
    failed_ids = [sid for sid, r in gate_results.items() if r["status"] == "FAIL"]
    if failed_ids:
        print(f"\n  실패 시나리오: {', '.join(f'S{s}' for s in failed_ids)}")
        for sid in failed_ids:
            print(f"    S{sid}: {'; '.join(gate_results[sid]['errors'][:3])}")

    print(f"\n{'='*60}")
    return verdict


if __name__ == "__main__":
    verdict = main()
    sys.exit(0 if verdict == "PASS" else 1)
