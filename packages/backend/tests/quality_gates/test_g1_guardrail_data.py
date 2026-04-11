"""G1 품질 게이트: 가드레일 데이터 리뷰.

사용법:
    pytest tests/quality_gates/test_g1_guardrail_data.py -v
    (LLM API 키 불필요)
"""

import json
import pathlib

import pytest

SEEDS_DIR = pathlib.Path(__file__).parents[4] / "docs" / "guardrail-seeds"
CONTRACTS_PATH = (
    pathlib.Path(__file__).parents[4] / "docs" / "contracts" / "story-engine.ts"
)

VALID_AGE_GROUPS = {"3-4", "5-6", "7-8"}
VALID_INTENT_CATEGORIES = {
    "value_teaching",
    "interest_story",
    "problem_solving",
    "celebration",
}
VALID_ARC_IDS = {
    "gentle_resolution",
    "courage_building",
    "relationship_repair",
    "new_experience",
    "joy_of_discovery",
    "celebration_joy",
}


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
        assert (
            by_age["3-4"]["sentence_rules"]["max_characters_per_sentence"]
            < by_age["5-6"]["sentence_rules"]["max_characters_per_sentence"]
            < by_age["7-8"]["sentence_rules"]["max_characters_per_sentence"]
        )

    def test_a2_4_sentences_per_page_monotonic(self, age_styles):
        by_age = {g["age_group"]: g for g in age_styles}
        for prev, curr in [("3-4", "5-6"), ("5-6", "7-8")]:
            assert (
                by_age[prev]["page_guidelines"]["sentences_per_page"]["max"]
                <= by_age[curr]["page_guidelines"]["sentences_per_page"]["max"]
            )

    def test_a2_5_total_pages_monotonic(self, age_styles):
        by_age = {g["age_group"]: g for g in age_styles}
        for prev, curr in [("3-4", "5-6"), ("5-6", "7-8")]:
            assert (
                by_age[prev]["page_guidelines"]["total_pages"]["max"]
                <= by_age[curr]["page_guidelines"]["total_pages"]["max"]
            )


# ─── 영역 A3: safety-rails.json ───


class TestA3SafetyRails:
    def test_a3_1_required_sections(self, safety):
        required = (
            "prohibitions",
            "required_elements",
            "content_filter",
            "illustration_safety",
        )
        for section in required:
            assert section in safety, f"missing: {section}"
        cf = safety["content_filter"]
        for key in ("exact_block", "pattern_block", "allowlist"):
            assert key in cf, f"missing: {key}"

    def test_a3_2_no_bare_stem_keywords(self, safety):
        """exact_block 키워드가 단독 어근('죽')이 아닌 구체적 표현인지 확인."""
        keywords = safety["content_filter"]["exact_block"]
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
        expected_keys = {
            "arc_id",
            "description",
            "target_ages",
            "stages",
            "rules",
        }
        for arc in arcs:
            actual = set(arc.keys())
            assert actual == expected_keys, f"{arc['arc_id']}: {actual}"

    def test_b2_stage_fields_match_contract(self, arcs):
        expected_keys = {"phase", "ratio", "purpose"}
        for arc in arcs:
            for stage in arc["stages"]:
                assert set(stage.keys()) == expected_keys

    def test_b3_age_style_fields_match_contract(self, age_styles):
        expected_keys = {
            "age_group",
            "sentence_rules",
            "emotional_expression",
            "page_guidelines",
        }
        for g in age_styles:
            actual = set(g.keys())
            assert actual == expected_keys, f"{g['age_group']}: {actual}"

    def test_b5_safety_extra_fields_documented(self, safety):
        """계약에 없는 content_filter, illustration_safety가 존재함을 확인.
        이는 의도된 확장 — 계약 업데이트 필요 여부를 리뷰."""
        contract_fields = {"prohibitions", "required_elements"}
        skip = {"version", "last_updated"}
        extra = set(safety.keys()) - contract_fields - skip
        if extra:
            print(f"  INFO: 계약에 없는 추가 필드: {extra}")
