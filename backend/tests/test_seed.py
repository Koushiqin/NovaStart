from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import Clock
from app.db import Base
from app.models.day_task import DayTask
from app.seed import reset_seed

TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_reset_seed_uses_injected_today(db_session: AsyncSession):
    """种子数据必须按注入时钟的「今天」生成，而不是容器真实日期。"""
    offset = Clock(offset_seconds=-86400)

    users = await reset_seed(db_session, offset)

    days = (
        await db_session.scalars(select(DayTask.date).where(DayTask.user_id == users[0].id))
    ).all()
    assert max(days) == offset.today() - timedelta(days=1)
