"""초기 도서 + 상황 태그 시드 데이터 적재 스크립트 (R8).

사용법:
    cd packages/backend
    python scripts/seed_books.py

잘 알려진 한국 아동 동화책 30권과 수동 생성 상황 태그를 DB에 적재한다.
SQLite(테스트) 또는 PostgreSQL(운영) 모두 지원.
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# 프로젝트 경로 설정
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src")
)

from storytale.db.base import Base  # noqa: E402
from storytale.db.models import Book, SituationTag  # noqa: E402

# ---------------------------------------------------------------------------
# 시드 데이터: 한국 아동 동화책 30권 + 상황 태그
# ---------------------------------------------------------------------------

SEED_BOOKS = [
    {
        "isbn": "9788901260716",
        "title": "구름빵",
        "author": "백희나",
        "publisher": "한솔수북",
        "synopsis": "비 오는 날 아침, 고양이 남매가 나뭇가지에 걸린 구름을 주워와 엄마와 빵을 만들어 먹으면 하늘을 날 수 있게 되는 이야기.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "interest_story",
                "situation_description": "하늘을 나는 상상을 좋아하는 아이",
                "emotional_keywords": ["호기심", "상상력", "모험", "즐거움"],
                "recommended_arc_id": "joy_of_discovery",
                "confidence_score": 0.90,
            },
            {
                "tag_category": "value_teaching",
                "situation_description": "가족과 함께하는 따뜻한 시간의 소중함",
                "emotional_keywords": ["사랑", "따뜻함", "감사"],
                "recommended_arc_id": "celebration_joy",
                "confidence_score": 0.75,
            },
        ],
    },
    {
        "isbn": "9788943311384",
        "title": "알사탕",
        "author": "백희나",
        "publisher": "책읽는곰",
        "synopsis": "동동이가 알사탕을 먹으면 다른 사람의 마음 속 이야기가 들린다. 무뚝뚝한 아빠의 진심도 들리게 된다.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "아빠와 대화가 어려운 아이",
                "emotional_keywords": ["서운함", "이해", "사랑", "따뜻함"],
                "recommended_arc_id": "relationship_repair",
                "confidence_score": 0.85,
            },
        ],
    },
    {
        "isbn": "9788901219240",
        "title": "이슬이의 첫 심부름",
        "author": "쓰쓰이 요리코",
        "publisher": "한림출판사",
        "synopsis": "다섯 살 이슬이가 혼자서 처음으로 우유를 사러 가는 용기 있는 이야기.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "혼자서 무언가를 해보는 것이 두려운 아이",
                "emotional_keywords": ["두려움", "용기", "자신감", "뿌듯함"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.92,
            },
        ],
    },
    {
        "isbn": "9788901046556",
        "title": "강아지똥",
        "author": "권정생",
        "publisher": "길벗어린이",
        "synopsis": "아무도 거들떠보지 않는 강아지똥이 민들레꽃을 피우는 거름이 되는 이야기.",
        "target_age_min": 5,
        "target_age_max": 8,
        "tags": [
            {
                "tag_category": "value_teaching",
                "situation_description": "자존감이 낮아 자기 자신을 하찮게 여기는 아이",
                "emotional_keywords": ["외로움", "슬픔", "희망", "보람"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.88,
            },
        ],
    },
    {
        "isbn": "9788949112008",
        "title": "무지개 물고기",
        "author": "마르쿠스 피스터",
        "publisher": "시공주니어",
        "synopsis": "가장 예쁜 비늘을 가진 무지개 물고기가 나눔을 통해 진정한 친구를 얻는 이야기.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "value_teaching",
                "situation_description": "친구와 나누는 것을 어려워하는 아이",
                "emotional_keywords": ["외로움", "고민", "나눔", "기쁨", "갈등", "이해"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.90,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "친구가 없어서 외로운 아이",
                "emotional_keywords": ["외로움", "서운함", "기쁨"],
                "recommended_arc_id": "relationship_repair",
                "confidence_score": 0.82,
            },
        ],
    },
    {
        "isbn": "9788943307837",
        "title": "괜찮아",
        "author": "최숙희",
        "publisher": "웅진주니어",
        "synopsis": "서툴고 느려도 괜찮다는 따뜻한 위로의 메시지를 전하는 그림책.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "실수를 두려워하거나 자신감이 부족한 아이",
                "emotional_keywords": ["불안", "두려움", "위로", "안심"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.92,
            },
            {
                "tag_category": "value_teaching",
                "situation_description": "있는 그대로의 자신을 받아들이는 법을 알려주고 싶을 때",
                "emotional_keywords": ["자신감", "위축", "위로", "자존감"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.85,
            },
        ],
    },
    {
        "isbn": "9788901064895",
        "title": "나는 나의 주인",
        "author": "채인선",
        "publisher": "토토북",
        "synopsis": "아이가 자기 몸과 마음의 주인이라는 자존감 메시지.",
        "target_age_min": 5,
        "target_age_max": 8,
        "tags": [
            {
                "tag_category": "value_teaching",
                "situation_description": "자기 결정을 스스로 내리는 연습이 필요한 아이",
                "emotional_keywords": ["자신감", "독립심", "용기"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.80,
            },
        ],
    },
    {
        "isbn": "9788901107608",
        "title": "피터의 의자",
        "author": "에즈라 잭 키츠",
        "publisher": "비룡소",
        "synopsis": "동생이 태어나 자기 물건이 분홍색으로 칠해지자 삐진 피터가 결국 형이 되는 마음을 갖게 되는 이야기.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "동생이 태어나 질투를 느끼는 아이",
                "emotional_keywords": ["질투", "불안", "외로움", "수용", "서운함", "분노"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.93,
            },
        ],
    },
    {
        "isbn": "9788943309404",
        "title": "나는 형이니까",
        "author": "후쿠다 이와오",
        "publisher": "웅진주니어",
        "synopsis": "동생이 생기면서 혼자만의 시간을 빼앗긴 형이 결국 형의 기쁨을 발견하는 이야기.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "동생이 생기면서 관심을 덜 받는다고 느끼는 아이",
                "emotional_keywords": ["질투", "서운함", "책임감", "사랑", "외로움", "불안"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.90,
            },
        ],
    },
    {
        "isbn": "9788949120881",
        "title": "까만 밤에 무슨 일이 일어났을까?",
        "author": "브루노 무나리",
        "publisher": "시공주니어",
        "synopsis": "어둠 속에서 다양한 동물과 자연을 만나며 밤이 무섭지 않다는 것을 알게 되는 이야기.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "어둠이나 밤을 무서워하는 아이",
                "emotional_keywords": ["두려움", "호기심", "안심", "발견", "공포", "불안", "용기"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.87,
            },
        ],
    },
    {
        "isbn": "9788936438562",
        "title": "솔이의 추석 이야기",
        "author": "이억배",
        "publisher": "길벗어린이",
        "synopsis": "추석에 시골 할머니 댁을 방문하며 한국 전통 명절을 경험하는 이야기.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "celebration",
                "situation_description": "명절이나 특별한 날을 이해하고 즐기고 싶은 아이",
                "emotional_keywords": ["기대", "설렘", "감사", "즐거움"],
                "recommended_arc_id": "celebration_joy",
                "confidence_score": 0.88,
            },
        ],
    },
    {
        "isbn": "9788901053745",
        "title": "수박 수영장",
        "author": "안녕달",
        "publisher": "창비",
        "synopsis": "커다란 수박 안에서 수영장처럼 노는 상상력 풍부한 여름 이야기.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "interest_story",
                "situation_description": "여름이나 물놀이를 좋아하는 아이",
                "emotional_keywords": ["즐거움", "상상력", "신남", "시원함"],
                "recommended_arc_id": "joy_of_discovery",
                "confidence_score": 0.82,
            },
        ],
    },
    {
        "isbn": "9788901084321",
        "title": "거미와 파리",
        "author": "메리 하울리트",
        "publisher": "보림",
        "synopsis": "거미의 달콤한 유혹에 넘어가지 않는 지혜에 대한 이야기.",
        "target_age_min": 5,
        "target_age_max": 8,
        "tags": [
            {
                "tag_category": "value_teaching",
                "situation_description": "낯선 사람의 유혹이나 위험한 상황을 판단해야 하는 아이",
                "emotional_keywords": ["호기심", "경계심", "지혜", "안전"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.78,
            },
        ],
    },
    {
        "isbn": "9788949100524",
        "title": "사과가 쿵!",
        "author": "다다 히로시",
        "publisher": "보림",
        "synopsis": "사과 하나를 둘러싼 동물 친구들의 즐거운 반복 이야기.",
        "target_age_min": 3,
        "target_age_max": 4,
        "tags": [
            {
                "tag_category": "interest_story",
                "situation_description": "동물을 좋아하는 어린 아이",
                "emotional_keywords": ["즐거움", "호기심", "반복의 재미"],
                "recommended_arc_id": "joy_of_discovery",
                "confidence_score": 0.80,
            },
        ],
    },
    {
        "isbn": "9788943310011",
        "title": "엄마가 화났다",
        "author": "유타 바우어",
        "publisher": "책읽는곰",
        "synopsis": "엄마의 큰 소리에 놀란 펭귄 아이의 몸이 조각나는 이야기. 엄마가 사과하고 다시 꿰매주는 화해의 과정.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "부모의 화에 놀라고 위축되는 아이",
                "emotional_keywords": ["두려움", "슬픔", "안심", "화해"],
                "recommended_arc_id": "relationship_repair",
                "confidence_score": 0.90,
            },
        ],
    },
    {
        "isbn": "9788901099835",
        "title": "당근 유치원",
        "author": "안녕달",
        "publisher": "창비",
        "synopsis": "유치원에 처음 가는 토끼의 두근두근 첫 날 이야기.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "유치원이나 어린이집에 처음 가는 아이",
                "emotional_keywords": ["불안", "두려움", "설렘", "적응"],
                "recommended_arc_id": "new_experience",
                "confidence_score": 0.92,
            },
            {
                "tag_category": "celebration",
                "situation_description": "새 학기를 시작하는 아이",
                "emotional_keywords": ["설렘", "기대", "두근거림"],
                "recommended_arc_id": "new_experience",
                "confidence_score": 0.75,
            },
        ],
    },
    {
        "isbn": "9788953598836",
        "title": "팥죽 할멈과 호랑이",
        "author": "한국 전래동화",
        "publisher": "비룡소",
        "synopsis": "호랑이에게 잡아먹히려는 할머니를 밤톨, 송곳, 맷돌 등이 함께 도와 물리치는 전래동화.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "value_teaching",
                "situation_description": "힘을 합치면 어려운 문제도 해결할 수 있다는 것을 알려주고 싶을 때",
                "emotional_keywords": ["두려움", "협력", "용기", "통쾌함"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.85,
            },
        ],
    },
    {
        "isbn": "9788949131122",
        "title": "치과 의사 드소토 선생님",
        "author": "윌리엄 스타이그",
        "publisher": "비룡소",
        "synopsis": "치과에 간 여우를 지혜롭게 물리치는 생쥐 치과의사 이야기.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "치과나 병원에 가는 것을 무서워하는 아이",
                "emotional_keywords": ["두려움", "용기", "지혜", "안심"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.82,
            },
        ],
    },
    {
        "isbn": "9788901155552",
        "title": "이 닦기 싫어!",
        "author": "최민오",
        "publisher": "아이세움",
        "synopsis": "이 닦기를 싫어하는 아이가 충치 세균과의 모험을 통해 양치의 중요성을 깨닫는 이야기.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "이 닦기를 거부하는 아이",
                "emotional_keywords": ["거부", "호기심", "깨달음", "습관", "짜증", "싫음", "적응"],
                "recommended_arc_id": "new_experience",
                "confidence_score": 0.85,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "싫어하던 것을 자연스럽게 받아들이게 되는 과정",
                "emotional_keywords": ["싫음", "거부", "불편함", "저항감", "깨달음", "안심"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.80,
            },
        ],
    },
    {
        "isbn": "9788901171456",
        "title": "공룡이 쿵쿵쿵",
        "author": "다카이 요시카즈",
        "publisher": "보림",
        "synopsis": "다양한 공룡이 의성어와 함께 등장하는 즐거운 공룡 그림책.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "interest_story",
                "situation_description": "공룡을 좋아하는 아이",
                "emotional_keywords": ["호기심", "흥분", "모험", "즐거움"],
                "recommended_arc_id": "joy_of_discovery",
                "confidence_score": 0.90,
            },
        ],
    },
    {
        "isbn": "9788943312206",
        "title": "잘 자, 작은 곰아",
        "author": "마르틴 바델",
        "publisher": "시공주니어",
        "synopsis": "잠이 오지 않는 작은 곰에게 큰 곰이 다정하게 함께하는 잠자리 이야기.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "잠을 잘 안 자거나 어두운 곳을 무서워하는 아이",
                "emotional_keywords": ["두려움", "안심", "따뜻함", "포근함", "공포", "불안"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.88,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "어둠을 무서워하지만 용기를 내서 극복하는 과정",
                "emotional_keywords": ["두려움", "안심", "포근함", "용기"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.82,
            },
        ],
    },
    {
        "isbn": "9788901188123",
        "title": "심심한 늑대",
        "author": "박정섭",
        "publisher": "사계절",
        "synopsis": "심심한 늑대가 친구를 찾아 나서면서 벌어지는 유쾌한 이야기.",
        "target_age_min": 4,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "친구 사귀기를 어려워하는 아이",
                "emotional_keywords": ["외로움", "용기", "즐거움", "우정", "서운함", "불안", "소외"],
                "recommended_arc_id": "relationship_repair",
                "confidence_score": 0.82,
            },
            {
                "tag_category": "problem_solving",
                "situation_description": "수줍어서 먼저 다가가지 못하는 아이가 용기를 내는 이야기",
                "emotional_keywords": ["수줍음", "외로움", "용기", "두려움", "우정"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.78,
            },
        ],
    },
    {
        "isbn": "9788901195001",
        "title": "생일 축하해!",
        "author": "에릭 칼",
        "publisher": "더큰",
        "synopsis": "생일을 맞은 아이를 위한 따뜻한 축하와 사랑의 메시지.",
        "target_age_min": 3,
        "target_age_max": 6,
        "tags": [
            {
                "tag_category": "celebration",
                "situation_description": "생일을 맞은 아이에게 특별한 이야기를 해주고 싶을 때",
                "emotional_keywords": ["기쁨", "설렘", "사랑", "감사"],
                "recommended_arc_id": "celebration_joy",
                "confidence_score": 0.92,
            },
        ],
    },
    {
        "isbn": "9788901201009",
        "title": "으악, 도깨비다!",
        "author": "손정원",
        "publisher": "비룡소",
        "synopsis": "무서운 줄만 알았던 도깨비가 사실은 착하고 귀여운 존재라는 것을 알게 되는 이야기.",
        "target_age_min": 4,
        "target_age_max": 7,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "낯선 것이나 무서운 것에 대한 두려움이 큰 아이",
                "emotional_keywords": ["두려움", "호기심", "용기", "안심"],
                "recommended_arc_id": "courage_building",
                "confidence_score": 0.85,
            },
        ],
    },
    {
        "isbn": "9788901210123",
        "title": "싫어 싫어",
        "author": "최숙희",
        "publisher": "웅진주니어",
        "synopsis": "뭐든 싫다고 말하는 아이가 자기 감정을 표현하는 법을 배우는 이야기.",
        "target_age_min": 3,
        "target_age_max": 5,
        "tags": [
            {
                "tag_category": "problem_solving",
                "situation_description": "반항기나 거부 행동이 심한 아이",
                "emotional_keywords": ["분노", "좌절", "자기표현", "이해", "거부", "반항", "짜증", "답답함"],
                "recommended_arc_id": "gentle_resolution",
                "confidence_score": 0.87,
            },
        ],
    },
]


async def seed(database_url: str | None = None) -> None:
    """DB에 시드 데이터 적재."""
    url = database_url or os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///storytale_seed.db"
    )
    engine = create_async_engine(url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        inserted = 0
        skipped = 0

        for book_data in SEED_BOOKS:
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
            try:
                await session.flush()
            except Exception:
                await session.rollback()
                skipped += 1
                print(f"  SKIP (이미 존재): {book_data['title']}")
                continue

            for tag_data in tags_data:
                tag = SituationTag(
                    book_id=book.id,
                    tag_category=tag_data["tag_category"],
                    situation_description=tag_data[
                        "situation_description"
                    ],
                    emotional_keywords=tag_data["emotional_keywords"],
                    recommended_arc_id=tag_data.get(
                        "recommended_arc_id"
                    ),
                    confidence_score=tag_data["confidence_score"],
                    source="ai_generated",
                )
                session.add(tag)

            inserted += 1
            print(f"  OK: {book_data['title']} (+{len(tags_data)} tags)")

        await session.commit()
        print(f"\n완료: {inserted}권 적재, {skipped}권 스킵")


if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(seed(db_url))
