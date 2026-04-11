"""G3.5 품질 게이트 — 10개 시나리오 추천 생성 스크립트.

실행:
    cd packages/backend
    python tests/run_g3_5_generation.py

결과: tests/g3_5_results.json 에 체크포인트 저장.
중간 실패 시 이어서 실행 가능 (이미 완료된 시나리오는 건너뜀).

환경변수:
    CLAUDE_API_KEY 또는 ANTHROPIC_API_KEY 필수.
"""

import asyncio
import copy
import json
import os
import pathlib
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 프로젝트 경로 설정
_BACKEND_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, _BACKEND_SRC)
sys.path.insert(0, _SCRIPTS_DIR)

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from seed_books import SEED_BOOKS  # noqa: E402
from storytale.db.base import Base  # noqa: E402
from storytale.db.models import Book, SituationTag  # noqa: E402
from storytale.interpreter.intent_analyzer import IntentAnalyzer  # noqa: E402
from storytale.interpreter.llm_client import create_llm_client  # noqa: E402
from storytale.recommendation.book_recommender import BookRecommender  # noqa: E402

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------

_PROJECT_ROOT = pathlib.Path(__file__).parents[3]
_SEEDS_DIR = _PROJECT_ROOT / "docs" / "guardrail-seeds"
_RESULTS_PATH = pathlib.Path(__file__).parent / "g3_5_results.json"

# ---------------------------------------------------------------------------
# 시나리오 10개 (G3.5 문서 기준)
# ---------------------------------------------------------------------------

SCENARIOS = [
    {"id": 1, "purpose_category": "problem_solving", "parent_text": "동생이 태어났는데 자꾸 밀쳐요", "child_age": 5},
    {"id": 2, "purpose_category": "problem_solving", "parent_text": "유치원 가기 싫다고 울어요", "child_age": 4},
    {"id": 3, "purpose_category": "problem_solving", "parent_text": "어둠을 무서워해서 혼자 못 자요", "child_age": 4},
    {"id": 4, "purpose_category": "problem_solving", "parent_text": "자꾸 싫다고만 해요, 반항이 심해요", "child_age": 3},
    {"id": 5, "purpose_category": "interest_story", "parent_text": "공룡을 너무 좋아해요, 특히 트리케라톱스", "child_age": 4},
    {"id": 6, "purpose_category": "value_teaching", "parent_text": "친구한테 장난감 안 빌려주려고 해요", "child_age": 5},
    {"id": 7, "purpose_category": "value_teaching", "parent_text": "실수하면 크게 울어요, 자신감이 없어요", "child_age": 4},
    {"id": 8, "purpose_category": "celebration", "parent_text": "다음 주 생일인데 특별한 걸 해주고 싶어요", "child_age": 5},
    {"id": 9, "purpose_category": "problem_solving", "parent_text": "친구를 사귀기 어려워해요", "child_age": 5},
    {"id": 10, "purpose_category": "problem_solving", "parent_text": "이 안 닦으려고 해요", "child_age": 3},
]

# API 호출 사이 딜레이 (초)
_API_DELAY = 3


# ---------------------------------------------------------------------------
# 환경
# ---------------------------------------------------------------------------


def _load_env() -> None:
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    os.environ.setdefault(key, val.strip("\"'"))


def _load_results() -> dict:
    """기존 체크포인트 로드."""
    if _RESULTS_PATH.exists():
        with open(_RESULTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"scenarios": {}, "metadata": {}}


def _save_results(results: dict) -> None:
    """결과 체크포인트 저장."""
    with open(_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# DB 세팅 + 시드
# ---------------------------------------------------------------------------


async def _setup_db():
    """인메모리 SQLite에 시드 데이터 적재."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        seed_data = copy.deepcopy(SEED_BOOKS)
        for book_data in seed_data:
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
    return session_factory


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------


async def run() -> None:
    _load_env()

    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: CLAUDE_API_KEY 또는 ANTHROPIC_API_KEY 환경변수 필요")
        sys.exit(1)

    # LLM + DB 세팅
    llm = create_llm_client(claude_api_key=api_key)

    with open(_SEEDS_DIR / "emotional-arcs.json", encoding="utf-8") as f:
        arcs = json.load(f)

    analyzer = IntentAnalyzer(llm_client=llm, arc_templates=arcs)
    session_factory = await _setup_db()

    # 기존 체크포인트 로드
    results = _load_results()

    total = len(SCENARIOS)
    passed = 0
    skipped = 0
    failed = 0

    for idx, scenario in enumerate(SCENARIOS, 1):
        sid = str(scenario["id"])

        # 이미 완료된 시나리오 건너뛰기
        if sid in results["scenarios"] and results["scenarios"][sid].get("status") == "ok":
            print(f"[{idx}/{total}] S{sid} — 이미 완료, 건너뜀")
            skipped += 1
            passed += 1
            continue

        print(f"\n{'='*50}")
        print(f"[{idx}/{total}] S{sid}: {scenario['parent_text']}")
        print(f"{'='*50}")

        try:
            # Step 1: IntentAnalysis
            intent = await analyzer.analyze(
                parent_text=scenario["parent_text"],
                purpose_category=scenario["purpose_category"],
                child_age=scenario["child_age"],
            )
            intent_dict = intent.model_dump()
            print(f"  intent_category: {intent.intent_category}")
            print(f"  arc_id: {intent.recommended_arc_id}")
            print(f"  keywords: {intent.emotional_keywords}")

            # Step 2: BookRecommender
            async with session_factory() as session:
                recommender = BookRecommender(llm_client=llm, db_session=session)
                rec_result = await recommender.recommend(
                    intent=intent_dict,
                    child_age=scenario["child_age"],
                    limit=3,
                )

            rec_titles = [r["book"]["title"] for r in rec_result["recommendations"]]
            print(f"  추천 도서: {rec_titles}")

            for r in rec_result["recommendations"]:
                print(f"    - {r['book']['title']} (score={r['match_score']})")
                if r.get("why_this_book"):
                    print(f"      why: {r['why_this_book'][:80]}...")
                if r.get("reading_questions"):
                    print(f"      questions: {len(r['reading_questions'])}개")
                if r.get("conversation_guide"):
                    print(f"      guide: {len(r['conversation_guide'])}개")

            results["scenarios"][sid] = {
                "status": "ok",
                "intent_analysis": intent_dict,
                "recommendation": rec_result,
            }
            passed += 1

        except Exception as exc:
            print(f"  ERROR: {exc}")
            results["scenarios"][sid] = {
                "status": "error",
                "error": str(exc),
            }
            failed += 1

        # 체크포인트 저장 + API 딜레이
        _save_results(results)
        if idx < total:
            time.sleep(_API_DELAY)

    # 메타데이터 업데이트
    results["metadata"] = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results_path": str(_RESULTS_PATH),
    }
    _save_results(results)

    print(f"\n{'='*50}")
    print(f"생성 완료: {passed}/{total} 성공, {failed} 실패, {skipped} 스킵")
    print(f"결과 저장: {_RESULTS_PATH}")
    print(f"{'='*50}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
