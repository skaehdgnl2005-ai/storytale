"""S10: 가드레일 통합 조회 API 테스트.

TDD 방식으로 먼저 작성. 구현 전 실패 확인 필요.

GET /api/v1/guardrails?age_group=3-4 → 아크 목록 + 문체 + 안전규칙 묶음

주의: 이 테스트는 알파벳 순서상 test_s7/s8/s9 보다 먼저 실행된다.
따라서 시드 JSON에 있는 arc_id/age_group 과 겹치지 않는
테스트 전용 고유 ID를 사용하며, module-scoped fixture 로 정리한다.
"""

import pytest
from fastapi.testclient import TestClient

# 공유 DB 설정은 conftest.py에서 담당
from conftest import TestingSessionLocal  # noqa: F401
from storytale.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# 테스트 전용 상수 (시드 데이터/S7·S8 페이로드와 겹치지 않는 고유 ID)
# ---------------------------------------------------------------------------

_AGE_A = "s10-test-age-a"
_AGE_B = "s10-test-age-b"

_ARC_1 = "s10_test_arc_alpha"
_ARC_2 = "s10_test_arc_beta"
_ARC_3 = "s10_test_arc_gamma"

_ARC_TEMPLATE = {
    "arc_id": "",  # 각 테스트에서 덮어씀
    "description": "S10 테스트용 아크",
    "target_ages": [],
    "stages": [
        {"phase": "발단", "ratio": 0.2, "purpose": "도입"},
        {"phase": "전개", "ratio": 0.3, "purpose": "갈등"},
        {"phase": "절정", "ratio": 0.2, "purpose": "위기"},
        {"phase": "결말", "ratio": 0.2, "purpose": "해결"},
        {"phase": "마무리", "ratio": 0.1, "purpose": "귀환"},
    ],
    "rules": ["S10 테스트 전용 규칙"],
}

_STYLE_TEMPLATE = {
    "age_group": "",  # 각 테스트에서 덮어씀
    "sentence_rules": {
        "max_characters_per_sentence": 20,
        "preferred_structure": "단문",
        "repetition_pattern": "AAB",
        "vocabulary_level": "기초",
    },
    "emotional_expression": {
        "method": "행동으로 표현",
        "good_examples": ["손을 꼭 쥐었어요."],
        "bad_examples": ["불안했어요."],
    },
    "page_guidelines": {
        "sentences_per_page": {"min": 2, "max": 3},
        "max_characters_per_page": 50,
        "total_pages": {"min": 8, "max": 12},
    },
}

_SAFETY_PAYLOAD = {
    "prohibitions": ["S10 테스트용 금지 사항"],
    "required_elements": ["S10 테스트용 필수 요소"],
    "content_filter": {
        "description": "S10 테스트용 필터",
        "exact_block": ["테스트키워드"],
        "pattern_block": [],
        "allowlist": [],
    },
    "illustration_safety": {
        "description": "S10 테스트용 일러스트 안전",
        "negative_prompts": ["test_negative"],
    },
}


# ---------------------------------------------------------------------------
# 모듈-scoped 픽스처: 테스트 데이터 생성 → yield → 정리
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def s10_test_data():
    """S10 테스트 전용 데이터를 생성하고 테스트 완료 후 정리한다."""
    # --- 생성 ---
    # 아크: _ARC_1, _ARC_2 → _AGE_A, _ARC_3 → _AGE_B
    arc_a = {**_ARC_TEMPLATE, "arc_id": _ARC_1, "target_ages": [_AGE_A]}
    arc_b = {**_ARC_TEMPLATE, "arc_id": _ARC_2, "target_ages": [_AGE_A, _AGE_B]}
    arc_c = {**_ARC_TEMPLATE, "arc_id": _ARC_3, "target_ages": [_AGE_B]}

    for payload in (arc_a, arc_b, arc_c):
        resp = client.post("/api/v1/guardrails/arcs", json=payload)
        assert resp.status_code == 201, f"arc 생성 실패: {resp.text}"

    # 문체 가이드: _AGE_A 전용
    style_a = {**_STYLE_TEMPLATE, "age_group": _AGE_A}
    resp = client.post("/api/v1/guardrails/age-styles", json=style_a)
    assert resp.status_code == 201, f"age_style 생성 실패: {resp.text}"

    # 안전 규칙 (중복 허용 엔드포인트이므로 생성만 하고 ID 추적)
    resp = client.post("/api/v1/guardrails/safety-rails", json=_SAFETY_PAYLOAD)
    assert resp.status_code == 201, f"safety_rails 생성 실패: {resp.text}"
    safety_id = resp.json()["id"]

    yield

    # --- 정리 (S7·S8·S9 테스트가 깨끗한 상태에서 실행될 수 있도록) ---
    for arc_id in (_ARC_1, _ARC_2, _ARC_3):
        client.delete(f"/api/v1/guardrails/arcs/{arc_id}")
    client.delete(f"/api/v1/guardrails/age-styles/{_AGE_A}")
    client.delete(f"/api/v1/guardrails/safety-rails/{safety_id}")


# ---------------------------------------------------------------------------
# 응답 구조 검증
# ---------------------------------------------------------------------------


def test_combined_response_structure_with_age_group():
    """age_group 제공 시 응답에 필수 필드가 모두 있어야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    data = response.json()
    assert "age_group" in data
    assert "arcs" in data
    assert "style_guide" in data
    assert "safety_rails" in data


def test_combined_response_structure_without_age_group():
    """age_group 없을 때도 응답에 필수 필드가 있어야 한다."""
    response = client.get("/api/v1/guardrails")
    assert response.status_code == 200
    data = response.json()
    assert "age_group" in data
    assert "arcs" in data
    assert "style_guide" in data
    assert "safety_rails" in data


# ---------------------------------------------------------------------------
# age_group 없을 때
# ---------------------------------------------------------------------------


def test_combined_without_age_group_returns_arcs():
    """age_group 없이 조회하면 테스트 아크 3개가 포함되어야 한다."""
    response = client.get("/api/v1/guardrails")
    assert response.status_code == 200
    data = response.json()
    arc_ids = {a["arc_id"] for a in data["arcs"]}
    assert _ARC_1 in arc_ids
    assert _ARC_2 in arc_ids
    assert _ARC_3 in arc_ids


def test_combined_without_age_group_style_guide_is_null():
    """age_group 없으면 style_guide는 null이어야 한다."""
    response = client.get("/api/v1/guardrails")
    assert response.status_code == 200
    assert response.json()["style_guide"] is None


def test_combined_without_age_group_age_group_is_null():
    """age_group 없으면 응답의 age_group도 null이어야 한다."""
    response = client.get("/api/v1/guardrails")
    assert response.status_code == 200
    assert response.json()["age_group"] is None


# ---------------------------------------------------------------------------
# age_group 필터링
# ---------------------------------------------------------------------------


def test_combined_with_age_group_returns_filtered_arcs():
    """age_group=_AGE_A 조회 시 _AGE_A 에 속하는 아크만 반환되어야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    data = response.json()
    assert data["age_group"] == _AGE_A
    arc_ids = {a["arc_id"] for a in data["arcs"]}
    # _ARC_1, _ARC_2 는 _AGE_A 포함; _ARC_3 는 _AGE_B 만 포함
    assert _ARC_1 in arc_ids
    assert _ARC_2 in arc_ids
    assert _ARC_3 not in arc_ids


def test_combined_arcs_match_age_group():
    """반환된 아크는 모두 해당 age_group을 target_ages에 포함해야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    for arc in response.json()["arcs"]:
        assert _AGE_A in arc["target_ages"], (
            f"Arc {arc['arc_id']} does not target '{_AGE_A}'"
        )


def test_combined_style_guide_matches_age_group():
    """반환된 style_guide의 age_group이 쿼리 파라미터와 일치해야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    data = response.json()
    assert data["style_guide"] is not None
    assert data["style_guide"]["age_group"] == _AGE_A


def test_combined_style_guide_has_required_fields():
    """style_guide에 필수 필드 3개가 모두 있어야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    sg = response.json()["style_guide"]
    assert "sentence_rules" in sg
    assert "emotional_expression" in sg
    assert "page_guidelines" in sg


def test_combined_age_group_with_no_style_guide():
    """스타일 가이드 없는 age_group이면 style_guide는 null이어야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_B}")
    assert response.status_code == 200
    data = response.json()
    # _AGE_B 아크는 있지만 스타일 가이드는 없음
    arc_ids = {a["arc_id"] for a in data["arcs"]}
    assert _ARC_2 in arc_ids  # _ARC_2 는 _AGE_B 포함
    assert _ARC_3 in arc_ids  # _ARC_3 는 _AGE_B 전용
    assert data["style_guide"] is None


# ---------------------------------------------------------------------------
# 알 수 없는 age_group
# ---------------------------------------------------------------------------


def test_combined_unknown_age_group_returns_empty_arcs():
    """존재하지 않는 age_group이면 arcs는 빈 목록이어야 한다."""
    response = client.get("/api/v1/guardrails?age_group=nonexistent-99")
    assert response.status_code == 200
    data = response.json()
    # 테스트 아크 중 "nonexistent-99" 를 target 하는 것은 없음
    test_arc_ids = {_ARC_1, _ARC_2, _ARC_3}
    returned_ids = {a["arc_id"] for a in data["arcs"]}
    assert test_arc_ids.isdisjoint(returned_ids)


def test_combined_unknown_age_group_style_guide_is_null():
    """존재하지 않는 age_group이면 style_guide는 null이어야 한다."""
    response = client.get("/api/v1/guardrails?age_group=nonexistent-99")
    assert response.status_code == 200
    assert response.json()["style_guide"] is None


def test_combined_unknown_age_group_still_returns_safety_rails():
    """존재하지 않는 age_group이더라도 안전 규칙은 반환되어야 한다."""
    response = client.get("/api/v1/guardrails?age_group=nonexistent-99")
    assert response.status_code == 200
    assert response.json()["safety_rails"] is not None


# ---------------------------------------------------------------------------
# 안전 규칙 구조 검증
# ---------------------------------------------------------------------------


def test_combined_safety_rails_structure():
    """safety_rails에 필수 필드가 모두 있어야 한다."""
    response = client.get(f"/api/v1/guardrails?age_group={_AGE_A}")
    assert response.status_code == 200
    sr = response.json()["safety_rails"]
    assert sr is not None
    assert "id" in sr
    assert "prohibitions" in sr
    assert "required_elements" in sr
    assert "content_filter" in sr
    assert "illustration_safety" in sr
    assert len(sr["prohibitions"]) > 0
    assert len(sr["required_elements"]) > 0


def test_combined_safety_rails_present_without_age_group():
    """age_group 없이 조회해도 안전 규칙이 반환되어야 한다."""
    response = client.get("/api/v1/guardrails")
    assert response.status_code == 200
    assert response.json()["safety_rails"] is not None
