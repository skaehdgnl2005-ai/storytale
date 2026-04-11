# storytale.api

## 목적
FastAPI의 REST API 라우터, 엔드포인트 정의 및 의존성 주입(Dependency)을 담당하는 모듈.

## 주요 구성요소
- `router.py`: 최상위 `APIRouter`를 관리하여 `app.py`에 마운트(prefix=`/api/v1`)
- `dependencies.py`: API 엔드포인트에서 공통으로 사용할 `get_db` 등 의존성 함수를 정의

## 사용 예시
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from storytale.api.dependencies import get_db

router = APIRouter()

@router.get("/items")
async def read_items(db: AsyncSession = Depends(get_db)):
    pass
```

## 테스트
```bash
pytest packages/backend/tests/test_s4_fastapi_app.py
```
