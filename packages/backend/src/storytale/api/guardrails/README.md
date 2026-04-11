# guardrails API 모듈

가드레일 시드 데이터(감정 흐름 템플릿, 연령별 문체, 안전 규칙)를 관리하는 API.

## 주요 파일

| 파일 | 역할 |
|------|------|
| `arc_templates.py` | `EmotionalArcTemplate` CRUD 엔드포인트 + `seed_emotional_arcs()` |

## 엔드포인트 (`/api/v1/guardrails/arcs`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/guardrails/arcs` | 전체 목록. `?age_group=3-4` 필터 지원 |
| GET | `/guardrails/arcs/{arc_id}` | 단일 조회 |
| POST | `/guardrails/arcs` | 생성 (201) |
| DELETE | `/guardrails/arcs/{arc_id}` | 삭제 (204) |

## 사용 예시

```python
from storytale.api.guardrails.arc_templates import seed_emotional_arcs

# DB 초기 시드 삽입
async with AsyncSession(...) as session:
    await seed_emotional_arcs(session)
    await session.commit()
```

## 테스트 실행

```bash
cd packages/backend
source .venv/Scripts/activate
pytest tests/test_s7_emotional_arc_templates.py -v
```
