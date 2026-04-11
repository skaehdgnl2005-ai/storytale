"""S8: AgeStyleGuide CRUD API 테스트.

TDD 방식으로 먼저 작성. 구현 전 실패 확인 필요.
"""

import asyncio

from fastapi.testclient import TestClient

# 공유 DB 설정은 conftest.py에서 담당 (테스트 모듈 간 충돌 방지)
from conftest import TestingSessionLocal
from storytale.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

STYLE_PAYLOAD_3_4 = {
    "age_group": "3-4",
    "sentence_rules": {
        "max_characters_per_sentence": 20,
        "preferred_structure": "주어 + 동사 + 감각/감정. 단문 위주.",
        "repetition_pattern": "AAB",
        "vocabulary_level": "일상 단어 500개 이내.",
    },
    "emotional_expression": {
        "method": "행동과 감각으로 표현.",
        "good_examples": ["배가 꼬르륵 소리가 났어요."],
        "bad_examples": ["하은이는 불안했어요."],
    },
    "page_guidelines": {
        "sentences_per_page": {"min": 2, "max": 3},
        "max_characters_per_page": 50,
        "total_pages": {"min": 8, "max": 12},
    },
}


# ---------------------------------------------------------------------------
# CRUD 테스트
# ---------------------------------------------------------------------------


def test_list_age_styles_empty():
    """초기에는 빈 목록을 반환해야 한다."""
    response = client.get("/api/v1/guardrails/age-styles")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_age_style():
    """연령별 문체 가이드를 생성하면 201과 함께 생성된 데이터를 반환해야 한다."""
    response = client.post("/api/v1/guardrails/age-styles", json=STYLE_PAYLOAD_3_4)
    assert response.status_code == 201
    data = response.json()
    assert data["age_group"] == "3-4"
    assert "sentence_rules" in data
    assert "emotional_expression" in data
    assert "page_guidelines" in data
    assert data["sentence_rules"]["max_characters_per_sentence"] == 20


def test_get_age_style_by_age_group():
    """특정 age_group으로 단일 가이드를 조회할 수 있어야 한다."""
    response = client.get("/api/v1/guardrails/age-styles/3-4")
    assert response.status_code == 200
    data = response.json()
    assert data["age_group"] == "3-4"


def test_get_age_style_not_found():
    """존재하지 않는 age_group 조회 시 404를 반환해야 한다."""
    response = client.get("/api/v1/guardrails/age-styles/99-99")
    assert response.status_code == 404


def test_list_age_styles_after_create():
    """생성 후 목록 조회 시 해당 가이드가 포함되어야 한다."""
    response = client.get("/api/v1/guardrails/age-styles")
    assert response.status_code == 200
    data = response.json()
    age_groups = [s["age_group"] for s in data]
    assert "3-4" in age_groups


def test_create_age_style_duplicate():
    """같은 age_group으로 중복 생성 시 409를 반환해야 한다."""
    response = client.post("/api/v1/guardrails/age-styles", json=STYLE_PAYLOAD_3_4)
    assert response.status_code == 409


def test_delete_age_style():
    """가이드를 삭제하면 204를 반환하고, 이후 조회 시 404가 되어야 한다."""
    response = client.delete("/api/v1/guardrails/age-styles/3-4")
    assert response.status_code == 204

    response = client.get("/api/v1/guardrails/age-styles/3-4")
    assert response.status_code == 404


def test_delete_age_style_not_found():
    """존재하지 않는 age_group 삭제 시 404를 반환해야 한다."""
    response = client.delete("/api/v1/guardrails/age-styles/99-99")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 시드 데이터 테스트
# ---------------------------------------------------------------------------


def test_seed_inserts_3_age_styles():
    """시드 함수 실행 후 3개의 연령대 가이드가 DB에 삽입되어야 한다."""
    from storytale.api.guardrails.age_style_guides import seed_age_style_guides

    async def _run():
        async with TestingSessionLocal() as session:
            await seed_age_style_guides(session)
            await session.commit()

    asyncio.run(_run())

    response = client.get("/api/v1/guardrails/age-styles")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_seed_age_group_ids():
    """시드 데이터에 3개의 올바른 age_group이 포함되어야 한다."""
    response = client.get("/api/v1/guardrails/age-styles")
    assert response.status_code == 200
    data = response.json()
    age_groups = {s["age_group"] for s in data}
    assert age_groups == {"3-4", "5-6", "7-8"}


def test_seed_sentence_rules_structure():
    """각 가이드의 sentence_rules가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/age-styles/5-6")
    assert response.status_code == 200
    data = response.json()
    rules = data["sentence_rules"]
    assert "max_characters_per_sentence" in rules
    assert "preferred_structure" in rules
    assert "repetition_pattern" in rules
    assert "vocabulary_level" in rules


def test_seed_page_guidelines_structure():
    """각 가이드의 page_guidelines가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/age-styles/7-8")
    assert response.status_code == 200
    data = response.json()
    guidelines = data["page_guidelines"]
    assert "sentences_per_page" in guidelines
    assert "max_characters_per_page" in guidelines
    assert "total_pages" in guidelines
    spp = guidelines["sentences_per_page"]
    assert spp["min"] <= spp["max"]


def test_seed_emotional_expression_examples():
    """각 가이드의 emotional_expression에 good/bad 예시가 있어야 한다."""
    response = client.get("/api/v1/guardrails/age-styles/3-4")
    assert response.status_code == 200
    data = response.json()
    expr = data["emotional_expression"]
    assert "method" in expr
    assert "good_examples" in expr
    assert "bad_examples" in expr
    assert len(expr["good_examples"]) > 0
    assert len(expr["bad_examples"]) > 0
