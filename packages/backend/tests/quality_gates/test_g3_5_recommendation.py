"""G3.5 품질 게이트: 동화책 추천 품질 검증.

IntentAnalyzer → BookRecommender → LLM 가이드 생성 전체 흐름 검증.

실행:
    # 단위 테스트 (모킹, DB 매칭 로직 검증)
    cd packages/backend
    pytest tests/quality_gates/test_g3_5_recommendation.py -v -k "not integration"

    # 통합 테스트 (실제 LLM + 시드 DB)
    pytest tests/quality_gates/test_g3_5_recommendation.py -v -m integration -s

검증 기준:
    G3.5-1: IntentAnalysis 스키마 유효성
    G3.5-2: 매칭 정확도 (기대 도서 포함 + match_score > 0.3)
    G3.5-3: 가이드 품질 — why_this_book
    G3.5-4: 가이드 품질 — reading_questions (열린 질문)
    G3.5-5: 가이드 품질 — conversation_guide
    G3.5-6: 전환 유도 구조
    G3.5-7: 안전성
"""

import asyncio
import copy
import json
import os
import pathlib
import re
import sys
from typing import Any
from unittest.mock import AsyncMock

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from storytale.db.base import Base
from storytale.db.models import Book, SituationTag
from storytale.interpreter.intent_analyzer import IntentAnalysis, IntentAnalyzer
from storytale.interpreter.llm_client import LLMClient, create_llm_client
from storytale.interpreter.safety_checker import SafetyChecker
from storytale.recommendation.book_recommender import BookRecommender

# ---------------------------------------------------------------------------
# 경로 / 상수
# ---------------------------------------------------------------------------

SEEDS_DIR = pathlib.Path(__file__).parents[4] / "docs" / "guardrail-seeds"

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


# ---------------------------------------------------------------------------
# 시나리오 10개 (G3.5 문서 기준)
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "S1_동생질투",
        "purpose_category": "problem_solving",
        "parent_text": "동생이 태어났는데 자꾸 밀쳐요",
        "child_age": 5,
        "expected_titles": ["피터의 의자", "나는 형이니까"],
        "trigger_keywords": ["동생"],
    },
    {
        "id": 2,
        "name": "S2_유치원거부",
        "purpose_category": "problem_solving",
        "parent_text": "유치원 가기 싫다고 울어요",
        "child_age": 4,
        "expected_titles": ["당근 유치원"],
        "trigger_keywords": ["유치원"],
    },
    {
        "id": 3,
        "name": "S3_어둠공포",
        "purpose_category": "problem_solving",
        "parent_text": "어둠을 무서워해서 혼자 못 자요",
        "child_age": 4,
        "expected_titles": ["잘 자, 작은 곰아", "까만 밤에"],
        "trigger_keywords": ["어둠", "무서워", "잠"],
    },
    {
        "id": 4,
        "name": "S4_반항기",
        "purpose_category": "problem_solving",
        "parent_text": "자꾸 싫다고만 해요, 반항이 심해요",
        "child_age": 3,
        "expected_titles": ["싫어 싫어"],
        "trigger_keywords": ["싫", "반항", "거부", "안 ", "표현"],
    },
    {
        "id": 5,
        "name": "S5_공룡관심사",
        "purpose_category": "interest_story",
        "parent_text": "공룡을 너무 좋아해요, 특히 트리케라톱스",
        "child_age": 4,
        "expected_titles": ["공룡이 쿵쿵쿵"],
        "trigger_keywords": ["공룡", "트리케라톱스"],
    },
    {
        "id": 6,
        "name": "S6_나눔교육",
        "purpose_category": "value_teaching",
        "parent_text": "친구한테 장난감 안 빌려주려고 해요",
        "child_age": 5,
        "expected_titles": ["무지개 물고기"],
        "trigger_keywords": ["장난감", "빌려주", "나눔", "친구"],
    },
    {
        "id": 7,
        "name": "S7_자신감부족",
        "purpose_category": "value_teaching",
        "parent_text": "실수하면 크게 울어요, 자신감이 없어요",
        "child_age": 4,
        "expected_titles": ["괜찮아"],
        "trigger_keywords": ["실수", "자신감", "울", "위축", "서툴", "틀", "괜찮"],
    },
    {
        "id": 8,
        "name": "S8_생일축하",
        "purpose_category": "celebration",
        "parent_text": "다음 주 생일인데 특별한 걸 해주고 싶어요",
        "child_age": 5,
        "expected_titles": ["생일 축하해!"],
        "trigger_keywords": ["생일", "특별"],
    },
    {
        "id": 9,
        "name": "S9_친구사귀기",
        "purpose_category": "problem_solving",
        "parent_text": "친구를 사귀기 어려워해요",
        "child_age": 5,
        "expected_titles": ["심심한 늑대", "무지개 물고기"],
        "trigger_keywords": ["친구"],
    },
    {
        "id": 10,
        "name": "S10_이닦기거부",
        "purpose_category": "problem_solving",
        "parent_text": "이 안 닦으려고 해요",
        "child_age": 3,
        "expected_titles": ["이 닦기 싫어!"],
        "trigger_keywords": ["이", "닦"],
    },
]

# 단위 테스트용 미리 정의된 의도 분석 (시나리오별)
PRESET_INTENTS: dict[int, dict[str, Any]] = {
    1: {
        "intent_category": "problem_solving",
        "core_theme": "동생 질투",
        "trigger_situation": "동생이 태어났는데 자꾸 밀쳐요",
        "child_current_behavior": "동생을 밀치는 행동",
        "parent_desired_outcome": "동생과 사이좋게 지내길 바람",
        "emotional_keywords": ["질투", "불안", "외로움"],
        "recommended_arc_id": "gentle_resolution",
    },
    2: {
        "intent_category": "problem_solving",
        "core_theme": "유치원 거부",
        "trigger_situation": "유치원 가기 싫다고 울어요",
        "child_current_behavior": "유치원 등원 거부",
        "parent_desired_outcome": "유치원에 즐겁게 가길 바람",
        "emotional_keywords": ["불안", "두려움", "적응"],
        "recommended_arc_id": "new_experience",
    },
    3: {
        "intent_category": "problem_solving",
        "core_theme": "어둠 공포",
        "trigger_situation": "어둠을 무서워해서 혼자 못 자요",
        "child_current_behavior": "혼자 잠자기를 거부",
        "parent_desired_outcome": "어둠에 대한 두려움 극복",
        "emotional_keywords": ["두려움", "안심", "포근함"],
        "recommended_arc_id": "courage_building",
    },
    4: {
        "intent_category": "problem_solving",
        "core_theme": "반항기",
        "trigger_situation": "자꾸 싫다고만 해요, 반항이 심해요",
        "child_current_behavior": "모든 것에 거부 반응",
        "parent_desired_outcome": "감정 표현을 건강하게 배우길",
        "emotional_keywords": ["분노", "좌절", "자기표현"],
        "recommended_arc_id": "gentle_resolution",
    },
    5: {
        "intent_category": "interest_story",
        "core_theme": "공룡 탐험",
        "trigger_situation": "공룡을 너무 좋아해요, 특히 트리케라톱스",
        "child_current_behavior": "명시되지 않음",
        "parent_desired_outcome": "공룡 관심사를 살린 이야기",
        "emotional_keywords": ["호기심", "흥분", "모험"],
        "recommended_arc_id": "joy_of_discovery",
    },
    6: {
        "intent_category": "value_teaching",
        "core_theme": "나눔 학습",
        "trigger_situation": "친구한테 장난감 안 빌려주려고 해요",
        "child_current_behavior": "장난감 나눔 거부",
        "parent_desired_outcome": "나누는 기쁨을 알길 바람",
        "emotional_keywords": ["외로움", "고민", "나눔"],
        "recommended_arc_id": "gentle_resolution",
    },
    7: {
        # 시드 데이터에 "괜찮아"의 value_teaching 태그 추가됨.
        # "자신감이 없어요"는 가치 교육과 문제 해결 모두 해당 가능.
        "intent_category": "value_teaching",
        "core_theme": "자존감 형성",
        "trigger_situation": "실수하면 크게 울어요, 자신감이 없어요",
        "child_current_behavior": "실수에 과민 반응",
        "parent_desired_outcome": "실수해도 괜찮다는 것을 배우길",
        "emotional_keywords": ["불안", "두려움", "위로"],
        "recommended_arc_id": "gentle_resolution",
    },
    8: {
        "intent_category": "celebration",
        "core_theme": "생일 축하",
        "trigger_situation": "다음 주 생일인데 특별한 걸 해주고 싶어요",
        "child_current_behavior": "명시되지 않음",
        "parent_desired_outcome": "특별한 생일 경험",
        "emotional_keywords": ["기쁨", "설렘", "사랑"],
        "recommended_arc_id": "celebration_joy",
    },
    9: {
        "intent_category": "problem_solving",
        "core_theme": "친구 사귀기",
        "trigger_situation": "친구를 사귀기 어려워해요",
        "child_current_behavior": "또래 관계 형성 어려움",
        "parent_desired_outcome": "친구를 사귀는 용기를 갖길",
        "emotional_keywords": ["외로움", "용기", "우정"],
        "recommended_arc_id": "relationship_repair",
    },
    10: {
        "intent_category": "problem_solving",
        "core_theme": "이닦기 거부",
        "trigger_situation": "이 안 닦으려고 해요",
        "child_current_behavior": "양치질 거부",
        "parent_desired_outcome": "양치 습관 형성",
        "emotional_keywords": ["거부", "호기심", "습관"],
        "recommended_arc_id": "new_experience",
    },
}


# ---------------------------------------------------------------------------
# 환경 / 헬퍼
# ---------------------------------------------------------------------------


def _load_env() -> None:
    env_path = pathlib.Path(__file__).parents[4] / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ.setdefault(key, val.strip("\"'"))


def _load_seed_books() -> list[dict[str, Any]]:
    """seed_books.py의 SEED_BOOKS 데이터를 로드. pop 변형 방지를 위해 deepcopy."""
    scripts_dir = str(pathlib.Path(__file__).parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from seed_books import SEED_BOOKS
    return copy.deepcopy(SEED_BOOKS)


# ---------------------------------------------------------------------------
# 모듈 레벨 DB 세팅 (conftest.py 패턴 따름)
# ---------------------------------------------------------------------------

_g35_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_G35SessionFactory = async_sessionmaker(_g35_engine, expire_on_commit=False)


async def _seed_db() -> None:
    async with _g35_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _G35SessionFactory() as session:
        for book_data in _load_seed_books():
            tags_data = book_data.pop("tags", [])
            book = Book(
                isbn=book_data["isbn"],
                title=book_data["title"],
                author=book_data["author"],
                publisher=book_data["publisher"],
                synopsis=book_data.get("synopsis"),
                target_age_min=book_data["target_age_min"],
                target_age_max=book_data["target_age_max"],
                source="manual",
            )
            session.add(book)
            await session.flush()
            for tag_data in tags_data:
                tag = SituationTag(
                    book_id=book.id,
                    tag_category=tag_data["tag_category"],
                    situation_description=tag_data["situation_description"],
                    emotional_keywords=tag_data["emotional_keywords"],
                    recommended_arc_id=tag_data.get("recommended_arc_id"),
                    confidence_score=tag_data["confidence_score"],
                    source="ai_generated",
                )
                session.add(tag)
        await session.commit()


asyncio.run(_seed_db())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeds() -> dict[str, Any]:
    """guardrail-seeds JSON 데이터."""
    with open(SEEDS_DIR / "emotional-arcs.json", encoding="utf-8") as f:
        arcs = json.load(f)
    with open(SEEDS_DIR / "safety-rails.json", encoding="utf-8") as f:
        safety = json.load(f)
    return {"arcs": arcs, "safety": safety}


@pytest.fixture(scope="module")
def safety_checker(seeds) -> SafetyChecker:
    return SafetyChecker(content_filter=seeds["safety"]["content_filter"])


@pytest.fixture(scope="module")
def db_session_factory():
    """시드 데이터가 적재된 인메모리 SQLite 세션 팩토리."""
    return _G35SessionFactory


@pytest.fixture(scope="module")
def llm_client(seeds):
    """실제 Claude API 클라이언트. 통합 테스트용."""
    _load_env()
    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("CLAUDE_API_KEY 또는 ANTHROPIC_API_KEY 환경변수 필요")
    return create_llm_client(claude_api_key=api_key)


@pytest.fixture(scope="module")
def intent_analyzer(llm_client, seeds):
    """실제 LLM 기반 IntentAnalyzer."""
    return IntentAnalyzer(llm_client=llm_client, arc_templates=seeds["arcs"])


@pytest.fixture
def mock_llm():
    """단위 테스트용 모킹된 LLM 클라이언트."""
    mock = AsyncMock(spec=LLMClient)
    # 가이드 생성: 빈 가이드 반환 (매칭 로직 검증에 집중)
    mock.complete_json.return_value = {"guides": []}
    return mock


# ===========================================================================
# 단위 테스트: DB 매칭 로직 (모킹된 LLM)
# ===========================================================================


class TestG35UnitMatching:
    """G3.5-2 단위 검증: 프리셋 의도 → DB 매칭 정확도."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    async def test_matching_contains_expected_book(
        self, scenario, mock_llm, db_session_factory
    ):
        """기대 도서가 추천 결과에 1개 이상 포함되어야 한다."""
        intent = PRESET_INTENTS[scenario["id"]]

        async with db_session_factory() as session:
            recommender = BookRecommender(
                llm_client=mock_llm, db_session=session
            )
            result = await recommender.recommend(
                intent=intent,
                child_age=scenario["child_age"],
                limit=3,
            )

        rec_titles = [r["book"]["title"] for r in result["recommendations"]]
        matched = any(
            any(exp in title for title in rec_titles)
            for exp in scenario["expected_titles"]
        )
        assert matched, (
            f"기대 도서 {scenario['expected_titles']} 중 "
            f"하나도 추천되지 않음. 실제: {rec_titles}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    async def test_no_age_out_of_range(
        self, scenario, mock_llm, db_session_factory
    ):
        """추천된 도서의 연령 범위가 아이 나이와 ±1세 이내여야 한다."""
        intent = PRESET_INTENTS[scenario["id"]]

        async with db_session_factory() as session:
            recommender = BookRecommender(
                llm_client=mock_llm, db_session=session
            )
            result = await recommender.recommend(
                intent=intent,
                child_age=scenario["child_age"],
                limit=3,
            )

        for r in result["recommendations"]:
            book = r["book"]
            age = scenario["child_age"]
            # _age_fit_score는 2세+ 차이면 0.0 → 필터됨
            assert book["target_age_min"] - 1 <= age <= book["target_age_max"] + 1, (
                f"{book['title']} 연령 범위 {book['target_age_min']}-"
                f"{book['target_age_max']}에 아이 나이 {age} 부적합"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    async def test_conversion_structure(
        self, scenario, mock_llm, db_session_factory
    ):
        """G3.5-6: 전환 유도 구조 필드가 올바르게 설정되어야 한다."""
        intent = PRESET_INTENTS[scenario["id"]]

        async with db_session_factory() as session:
            recommender = BookRecommender(
                llm_client=mock_llm, db_session=session
            )
            result = await recommender.recommend(
                intent=intent,
                child_age=scenario["child_age"],
                limit=3,
            )

        assert result["has_custom_story_option"] is True, "G3.5-6: has_custom_story_option 누락"
        assert result["custom_story_prompt"], "G3.5-6: custom_story_prompt 비어있음"
        assert result["intent_analysis"], "G3.5-6: intent_analysis 누락"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    async def test_match_score_above_threshold(
        self, scenario, mock_llm, db_session_factory
    ):
        """G3.5-2: match_score 검증.

        단위 테스트는 프리셋 의도 사용으로 키워드 겹침이 낮을 수 있어
        완화된 임계값(0.2) 적용. 통합 테스트에서 0.3 기준 적용.
        """
        intent = PRESET_INTENTS[scenario["id"]]

        async with db_session_factory() as session:
            recommender = BookRecommender(
                llm_client=mock_llm, db_session=session
            )
            result = await recommender.recommend(
                intent=intent,
                child_age=scenario["child_age"],
                limit=3,
            )

        for r in result["recommendations"]:
            assert r["match_score"] > 0.2, (
                f"{r['book']['title']} match_score={r['match_score']} < 0.2"
            )


# ===========================================================================
# 통합 테스트: 실제 LLM + 시드 DB (G3.5-1 ~ G3.5-7)
# ===========================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
)
async def test_g3_5_full_scenario(
    scenario: dict[str, Any],
    intent_analyzer: IntentAnalyzer,
    llm_client: LLMClient,
    db_session_factory,
    safety_checker: SafetyChecker,
):
    """G3.5 전체 파이프라인 검증 (실제 LLM).

    각 시나리오에 대해 G3.5-1 ~ G3.5-7을 검증한다.
    """
    sep = "=" * 60
    print(f"\n{sep}\n[{scenario['name']}] 시작\n{sep}")
    print(f"  parent_text: {scenario['parent_text']}")
    print(f"  child_age: {scenario['child_age']}")

    # ------------------------------------------------------------------
    # Step 1: IntentAnalysis (실제 LLM)
    # ------------------------------------------------------------------
    intent: IntentAnalysis = await intent_analyzer.analyze(
        parent_text=scenario["parent_text"],
        purpose_category=scenario["purpose_category"],
        child_age=scenario["child_age"],
    )
    intent_dict = intent.model_dump()

    print(f"\n--- IntentAnalysis ---")
    print(json.dumps(intent_dict, ensure_ascii=False, indent=2))

    # G3.5-1: IntentAnalysis 스키마 유효성
    assert isinstance(intent, IntentAnalysis), "G3.5-1: IntentAnalysis 인스턴스 아님"
    assert intent.intent_category in VALID_CATEGORIES, (
        f"G3.5-1: intent_category '{intent.intent_category}' 유효하지 않음"
    )
    assert intent.recommended_arc_id in VALID_ARC_IDS, (
        f"G3.5-1: arc_id '{intent.recommended_arc_id}' 유효하지 않음"
    )
    assert 3 <= len(intent.emotional_keywords) <= 5, (
        f"G3.5-1: emotional_keywords {len(intent.emotional_keywords)}개 (3~5개 필요)"
    )
    print("[G3.5-1 PASS] IntentAnalysis 스키마 유효 ✓")

    # ------------------------------------------------------------------
    # Step 2: BookRecommender (실제 LLM + 시드 DB)
    # ------------------------------------------------------------------
    async with db_session_factory() as session:
        recommender = BookRecommender(
            llm_client=llm_client, db_session=session
        )
        result = await recommender.recommend(
            intent=intent_dict,
            child_age=scenario["child_age"],
            limit=3,
        )

    recommendations = result["recommendations"]
    rec_titles = [r["book"]["title"] for r in recommendations]

    print(f"\n--- 추천 결과 ({len(recommendations)}권) ---")
    for r in recommendations:
        print(f"  {r['book']['title']} (score={r['match_score']})")

    # G3.5-2: 매칭 정확도
    assert len(recommendations) > 0, "G3.5-2: 추천 결과가 비어있음"
    matched = any(
        any(exp in title for title in rec_titles)
        for exp in scenario["expected_titles"]
    )
    assert matched, (
        f"G3.5-2: 기대 도서 {scenario['expected_titles']} 중 "
        f"하나도 추천되지 않음. 실제: {rec_titles}"
    )
    for r in recommendations:
        assert r["match_score"] > 0.3, (
            f"G3.5-2: {r['book']['title']} match_score={r['match_score']} < 0.3"
        )
        book = r["book"]
        age = scenario["child_age"]
        assert book["target_age_min"] - 1 <= age <= book["target_age_max"] + 1, (
            f"G3.5-2: {book['title']} 연령 범위 벗어남"
        )
    print(f"[G3.5-2 PASS] 매칭 정확도 ✓ — {rec_titles}")

    # G3.5-3 ~ G3.5-5: 가이드 품질
    for r in recommendations:
        why = r.get("why_this_book", "")
        questions = r.get("reading_questions", [])
        guide = r.get("conversation_guide", [])

        # G3.5-3: why_this_book (2~3문장, trigger 키워드 포함, 판단 표현 없음)
        assert why, f"G3.5-3: why_this_book 비어있음 — {r['book']['title']}"
        sentences = [s.strip() for s in re.split(r"[.!?。]", why) if s.strip()]
        assert len(sentences) >= 2, (
            f"G3.5-3: why_this_book 2문장 미만 — '{why[:60]}...'"
        )
        has_trigger_kw = any(kw in why for kw in scenario["trigger_keywords"])
        assert has_trigger_kw, (
            f"G3.5-3: why_this_book에 trigger 키워드 없음. "
            f"기대: {scenario['trigger_keywords']}"
        )
        for forbidden in ["비교", "다른 아이", "착한 아이", "나쁜 아이"]:
            assert forbidden not in why, (
                f"G3.5-3: 판단/비교 표현 '{forbidden}' 발견"
            )

        # G3.5-4: reading_questions (3~5개, 열린 질문)
        assert 3 <= len(questions) <= 5, (
            f"G3.5-4: reading_questions {len(questions)}개 "
            f"(3~5개 필요) — {r['book']['title']}"
        )
        for q in questions:
            assert not _CLOSED_QUESTION_RE.search(q), (
                f"G3.5-4: 닫힌 질문 발견 — '{q}'"
            )

        # G3.5-5: conversation_guide (3~4개)
        assert 3 <= len(guide) <= 4, (
            f"G3.5-5: conversation_guide {len(guide)}개 "
            f"(3~4개 필요) — {r['book']['title']}"
        )

    print("[G3.5-3~5 PASS] 가이드 품질 ✓")

    # G3.5-6: 전환 유도 구조
    assert result["has_custom_story_option"] is True, "G3.5-6: has_custom_story_option 누락"
    assert result["custom_story_prompt"], "G3.5-6: custom_story_prompt 비어있음"
    assert result["intent_analysis"], "G3.5-6: intent_analysis 필드 누락"
    print("[G3.5-6 PASS] 전환 유도 구조 ✓")

    # G3.5-7: 안전성
    safety_violations: list[str] = []
    for r in recommendations:
        for field_name in ("why_this_book", "reading_questions", "conversation_guide"):
            content = r.get(field_name, "")
            if isinstance(content, list):
                content = " ".join(content)
            check = safety_checker.check_text(content)
            if check.blocked:
                safety_violations.append(
                    f"  {r['book']['title']}/{field_name}: "
                    f"금지어 '{check.matched_keyword}'"
                )
    assert not safety_violations, (
        f"G3.5-7: 안전성 위반 {len(safety_violations)}건:\n"
        + "\n".join(safety_violations)
    )
    print("[G3.5-7 PASS] 안전성 ✓")

    print(f"\n{sep}\n[{scenario['name']}] 완료 — ALL PASS\n{sep}")
