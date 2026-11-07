from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import Clock
from app.db import Base
from app.models.day_task import DayTask
from app.models.letter import Letter
from app.models.star import Star
from app.models.streak import Streak
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


async def test_reset_seed_generates_stars_and_streak(db_session: AsyncSession):
    """验收 12：星星与连续天数由真实 recompute 路径产生（不手写行）。"""
    offset = Clock(offset_seconds=-86400)
    xiaoming, xiaomei, xiaogang = await reset_seed(db_session, offset)
    today = offset.today()

    stars = (
        await db_session.scalars(select(Star).where(Star.user_id == xiaoming.id))
    ).all()
    assert len(stars) == 6
    assert {star.date for star in stars} == {
        today - timedelta(days=n) for n in range(1, 7)
    }
    assert all(star.level == 1 and star.minutes == 5 for star in stars)

    streak = await db_session.scalar(
        select(Streak).where(Streak.user_id == xiaoming.id)
    )
    assert streak.current == 6
    assert streak.longest == 6
    assert streak.last_completed_date == today - timedelta(days=1)
    assert streak.was_reset is False

    xiaomei_stars = (
        await db_session.scalars(select(Star).where(Star.user_id == xiaomei.id))
    ).all()
    xiaomei_streak = await db_session.scalar(
        select(Streak).where(Streak.user_id == xiaomei.id)
    )
    assert len(xiaomei_stars) == 1
    assert xiaomei_streak.current == 1

    assert (
        await db_session.scalar(select(func.count()).select_from(Star).where(Star.user_id == xiaogang.id))
    ) == 0
    assert (
        await db_session.scalar(select(Streak).where(Streak.user_id == xiaogang.id))
    ) is None


async def test_reset_seed_prefills_mailbox(db_session: AsyncSession):
    """验收 18：小明未处理信箱 2 封（小美发来），小美发出记录 2 条已投递。"""
    offset = Clock(offset_seconds=-86400)

    xiaoming, xiaomei, _ = await reset_seed(db_session, offset)

    inbox = (
        await db_session.scalars(
            select(Letter).where(
                Letter.user_id == xiaoming.id,
                Letter.status == "delivered",
                Letter.handled == False,  # noqa: E712
            )
        )
    ).all()
    assert len(inbox) == 2
    assert {letter.sender_id for letter in inbox} == {xiaomei.id}
    assert {letter.content for letter in inbox} == {"小美的历史回顾：从一个小目标开始。"}
    assert all(letter.expired_at > offset.now() for letter in inbox)

    outbox = (
        await db_session.scalars(
            select(Letter).where(
                Letter.sender_id == xiaomei.id,
                Letter.status == "delivered",
            )
        )
    ).all()
    assert len(outbox) == 2
    assert {letter.user_id for letter in outbox} == {xiaoming.id}
