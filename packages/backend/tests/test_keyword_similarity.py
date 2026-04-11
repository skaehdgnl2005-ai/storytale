"""동의어 인식 키워드 유사도 테스트.

G3.5 품질 게이트 실패 원인: LLM emotional_keywords와 시드 데이터 keywords가
동일 감정을 다른 어휘로 표현 → Jaccard 0.0~0.29.
동의어 그룹을 사용하여 의미적으로 같은 키워드를 인식해야 한다.
"""

from storytale.recommendation.book_recommender import (
    _synonym_similarity,
)


class TestSynonymSimilarity:
    """동의어 인식 유사도 함수 단위 테스트."""

    def test_exact_match_returns_high_score(self):
        """완전히 같은 키워드면 1.0."""
        score = _synonym_similarity(
            ["두려움", "용기", "안심"],
            ["두려움", "용기", "안심"],
        )
        assert score == 1.0

    def test_empty_lists_return_zero(self):
        """둘 다 비어있으면 0.0."""
        assert _synonym_similarity([], []) == 0.0

    def test_one_empty_returns_zero(self):
        """한쪽만 비어있으면 0.0."""
        assert _synonym_similarity(["두려움"], []) == 0.0
        assert _synonym_similarity([], ["두려움"]) == 0.0

    def test_synonym_match_counts(self):
        """'거부감'과 '거부'는 동의어 그룹 → 매칭되어야 한다."""
        score = _synonym_similarity(
            ["거부감", "답답함"],
            ["거부", "좌절"],
        )
        # 거부감↔거부 매칭, 답답함↔좌절 매칭 → 높은 유사도
        assert score >= 0.7

    def test_fear_synonyms(self):
        """두려움/공포/무서움은 동의어 → 매칭."""
        score = _synonym_similarity(
            ["공포", "불안감"],
            ["두려움", "불안"],
        )
        assert score >= 0.7

    def test_sadness_synonyms(self):
        """슬픔/서운함/서러움은 동의어."""
        score = _synonym_similarity(
            ["서운함", "외로움"],
            ["슬픔", "고독"],
        )
        assert score >= 0.7

    def test_joy_synonyms(self):
        """기쁨/즐거움/행복/신남은 동의어."""
        score = _synonym_similarity(
            ["행복", "신남"],
            ["기쁨", "즐거움"],
        )
        assert score >= 0.7

    def test_no_overlap_returns_zero(self):
        """전혀 관련 없는 키워드는 0.0."""
        score = _synonym_similarity(
            ["호기심", "모험"],
            ["슬픔", "외로움"],
        )
        assert score == 0.0

    def test_partial_overlap(self):
        """일부만 겹칠 때 중간 점수."""
        score = _synonym_similarity(
            ["두려움", "호기심", "안심"],
            ["두려움", "슬픔", "안심"],
        )
        # 2/4 (union) 직접 매칭 → ~0.5 이상
        assert 0.4 <= score <= 0.8

    def test_anger_frustration_synonyms(self):
        """분노/화/짜증과 좌절/답답함 각각 동의어 그룹."""
        score = _synonym_similarity(
            ["분노", "좌절"],
            ["화", "답답함"],
        )
        assert score >= 0.7

    def test_real_scenario_s4_rejection(self):
        """S4 반항기 실패 케이스: LLM이 '거부감','답답함','반항심' 출력 가능
        vs 시드 '분노','좌절','자기표현','이해'."""
        score = _synonym_similarity(
            ["거부감", "답답함", "반항심"],
            ["분노", "좌절", "자기표현", "이해"],
        )
        # 거부감↔(분노 근접), 답답함↔좌절 → 최소 부분 매칭
        assert score >= 0.3

    def test_real_scenario_s7_confidence(self):
        """S7 자신감부족: LLM이 '위축','불안감','자존감' 출력 가능
        vs 시드 '불안','두려움','위로','안심'."""
        score = _synonym_similarity(
            ["위축", "불안감", "자존감"],
            ["불안", "두려움", "위로", "안심"],
        )
        # 불안감↔불안 매칭 → 최소 부분 매칭
        assert score >= 0.2
