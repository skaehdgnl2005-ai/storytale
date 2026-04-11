"""S9: SafetyRails CRUD API 테스트.

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

SAFETY_PAYLOAD = {
    "prohibitions": [
        "공포, 위협, 벌을 동기부여 수단으로 사용하는 장면",
        "어른이 아이를 직접 혼내거나 야단치는 장면",
    ],
    "required_elements": [
        "아이의 감정을 판단 없이 있는 그대로 수용하는 장면이 최소 1회",
        "아이가 스스로 선택하거나 행동하는 순간이 최소 1회",
    ],
    "content_filter": {
        "description": "생성된 텍스트에서 검출 시 재생성을 트리거하는 키워드",
        "exact_block": ["바보", "혼내"],
        "pattern_block": [
            {"pattern": "죽이고|죽이는|죽여", "intent": "살해 표현"},
        ],
        "allowlist": ["반죽이"],
    },
    "illustration_safety": {
        "description": "일러스트 생성 프롬프트에서 금지되는 요소",
        "negative_prompts": ["scary", "horror", "violent"],
    },
}


# ---------------------------------------------------------------------------
# CRUD 테스트
# ---------------------------------------------------------------------------


def test_list_safety_rails_empty():
    """초기에는 빈 목록을 반환해야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_safety_rails():
    """안전 규칙을 생성하면 201과 함께 생성된 데이터를 반환해야 한다."""
    response = client.post("/api/v1/guardrails/safety-rails", json=SAFETY_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "prohibitions" in data
    assert "required_elements" in data
    assert "content_filter" in data
    assert "illustration_safety" in data
    assert len(data["prohibitions"]) == 2
    assert len(data["required_elements"]) == 2


def test_get_safety_rails_by_id():
    """생성한 ID로 단일 안전 규칙을 조회할 수 있어야 한다."""
    # 먼저 목록으로 ID 확인
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    first_id = data[0]["id"]

    response = client.get(f"/api/v1/guardrails/safety-rails/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


def test_get_safety_rails_not_found():
    """존재하지 않는 ID 조회 시 404를 반환해야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails/99999")
    assert response.status_code == 404


def test_list_safety_rails_after_create():
    """생성 후 목록 조회 시 해당 규칙이 포함되어야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_delete_safety_rails():
    """안전 규칙을 삭제하면 204를 반환하고, 이후 조회 시 404가 되어야 한다."""
    # 먼저 목록에서 ID 가져오기
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    target_id = data[0]["id"]

    response = client.delete(f"/api/v1/guardrails/safety-rails/{target_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/guardrails/safety-rails/{target_id}")
    assert response.status_code == 404


def test_delete_safety_rails_not_found():
    """존재하지 않는 ID 삭제 시 404를 반환해야 한다."""
    response = client.delete("/api/v1/guardrails/safety-rails/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 시드 데이터 테스트
# ---------------------------------------------------------------------------


def test_seed_inserts_safety_rails():
    """시드 함수 실행 후 안전 규칙 1건이 DB에 삽입되어야 한다."""
    from storytale.api.guardrails.safety_rails import seed_safety_rails

    async def _run():
        async with TestingSessionLocal() as session:
            await seed_safety_rails(session)
            await session.commit()

    asyncio.run(_run())

    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_seed_prohibitions_non_empty():
    """시드 데이터의 prohibitions 목록이 비어있지 않아야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert len(data[0]["prohibitions"]) > 0


def test_seed_required_elements_non_empty():
    """시드 데이터의 required_elements 목록이 비어있지 않아야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert len(data[0]["required_elements"]) > 0


def test_seed_content_filter_structure():
    """시드 데이터의 content_filter가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    cf = data[0]["content_filter"]
    assert "description" in cf
    assert "exact_block" in cf
    assert "pattern_block" in cf
    assert "allowlist" in cf
    assert isinstance(cf["exact_block"], list)
    assert len(cf["exact_block"]) > 0


def test_seed_illustration_safety_structure():
    """시드 데이터의 illustration_safety가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/safety-rails")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    illus = data[0]["illustration_safety"]
    assert "description" in illus
    assert "negative_prompts" in illus
    assert isinstance(illus["negative_prompts"], list)
    assert len(illus["negative_prompts"]) > 0
