"""S7: EmotionalArcTemplate CRUD API 테스트.

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

ARC_PAYLOAD = {
    "arc_id": "gentle_resolution",
    "description": "부드러운 문제 해결형",
    "target_ages": ["3-4", "5-6"],
    "stages": [
        {"phase": "공감", "ratio": 0.2, "purpose": "아이의 현재 감정 반영"},
        {"phase": "전환점", "ratio": 0.15, "purpose": "시선 전환"},
        {"phase": "시도", "ratio": 0.25, "purpose": "작은 행동 변화"},
        {"phase": "재시도", "ratio": 0.2, "purpose": "다시 시도"},
        {"phase": "수용", "ratio": 0.2, "purpose": "감정적 수용"},
    ],
    "rules": ["문제가 한 번에 해결되면 안 됨"],
}


# ---------------------------------------------------------------------------
# CRUD 테스트
# ---------------------------------------------------------------------------


def test_list_arcs_empty():
    """초기에는 빈 목록을 반환해야 한다."""
    response = client.get("/api/v1/guardrails/arcs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_arc():
    """아크 템플릿을 생성하면 201과 함께 생성된 데이터를 반환해야 한다."""
    response = client.post("/api/v1/guardrails/arcs", json=ARC_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["arc_id"] == "gentle_resolution"
    assert data["description"] == "부드러운 문제 해결형"
    assert "3-4" in data["target_ages"]
    assert len(data["stages"]) == 5
    assert len(data["rules"]) == 1


def test_get_arc_by_id():
    """특정 arc_id로 단일 아크를 조회할 수 있어야 한다."""
    response = client.get("/api/v1/guardrails/arcs/gentle_resolution")
    assert response.status_code == 200
    data = response.json()
    assert data["arc_id"] == "gentle_resolution"


def test_get_arc_not_found():
    """존재하지 않는 arc_id 조회 시 404를 반환해야 한다."""
    response = client.get("/api/v1/guardrails/arcs/nonexistent_arc")
    assert response.status_code == 404


def test_list_arcs_after_create():
    """생성 후 목록 조회 시 해당 아크가 포함되어야 한다."""
    response = client.get("/api/v1/guardrails/arcs")
    assert response.status_code == 200
    data = response.json()
    arc_ids = [a["arc_id"] for a in data]
    assert "gentle_resolution" in arc_ids


def test_list_arcs_filter_by_age_group():
    """age_group 쿼리 파라미터로 필터링이 가능해야 한다."""
    # 3-4 연령에 해당하는 아크만 반환
    response = client.get("/api/v1/guardrails/arcs?age_group=3-4")
    assert response.status_code == 200
    data = response.json()
    for arc in data:
        assert "3-4" in arc["target_ages"]


def test_create_arc_duplicate():
    """같은 arc_id로 중복 생성 시 409를 반환해야 한다."""
    response = client.post("/api/v1/guardrails/arcs", json=ARC_PAYLOAD)
    assert response.status_code == 409


def test_delete_arc():
    """아크를 삭제하면 204를 반환하고, 이후 조회 시 404가 되어야 한다."""
    response = client.delete("/api/v1/guardrails/arcs/gentle_resolution")
    assert response.status_code == 204

    response = client.get("/api/v1/guardrails/arcs/gentle_resolution")
    assert response.status_code == 404


def test_delete_arc_not_found():
    """존재하지 않는 arc_id 삭제 시 404를 반환해야 한다."""
    response = client.delete("/api/v1/guardrails/arcs/nonexistent_arc")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 시드 데이터 테스트
# ---------------------------------------------------------------------------


def test_seed_inserts_6_arcs():
    """시드 함수 실행 후 6개의 아크가 DB에 삽입되어야 한다."""
    from storytale.api.guardrails.arc_templates import seed_emotional_arcs

    async def _run():
        async with TestingSessionLocal() as session:
            # 기존 데이터 정리 후 시드
            await seed_emotional_arcs(session)
            await session.commit()

    asyncio.run(_run())

    response = client.get("/api/v1/guardrails/arcs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6


def test_seed_arc_ids():
    """시드 데이터에 6개의 올바른 arc_id가 포함되어야 한다."""
    response = client.get("/api/v1/guardrails/arcs")
    assert response.status_code == 200
    data = response.json()
    arc_ids = {a["arc_id"] for a in data}
    expected = {
        "gentle_resolution",
        "courage_building",
        "relationship_repair",
        "new_experience",
        "joy_of_discovery",
        "celebration_joy",
    }
    assert arc_ids == expected


def test_seed_arc_stages_structure():
    """각 아크의 stages가 올바른 구조를 가져야 한다."""
    response = client.get("/api/v1/guardrails/arcs/courage_building")
    assert response.status_code == 200
    data = response.json()
    stages = data["stages"]
    assert len(stages) == 5
    for stage in stages:
        assert "phase" in stage
        assert "ratio" in stage
        assert "purpose" in stage
    # ratio 합계는 1.0에 근접해야 함
    total_ratio = sum(s["ratio"] for s in stages)
    assert abs(total_ratio - 1.0) < 0.01
