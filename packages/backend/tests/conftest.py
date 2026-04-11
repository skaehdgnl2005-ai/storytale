"""공유 테스트 DB 설정.

모든 테스트 파일이 동일한 인메모리 SQLite DB를 사용하도록 한다.
app.dependency_overrides[get_db]를 conftest.py에서 한 번만 설정해
테스트 모듈 간 충돌을 방지한다.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from storytale.api.dependencies import get_db
from storytale.app import app
from storytale.db.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def _create_tables() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(_create_tables())


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


# 단일 지점에서 오버라이드 설정.
# 각 테스트 파일이 각자 설정하면 마지막 임포트가 이깁니다.
app.dependency_overrides[get_db] = override_get_db
