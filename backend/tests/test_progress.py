import asyncio
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import get_clock
from app.db import Base, get_session
from app.main import app
from app.models.day_task import DayTask
from app.models.session import Session
from app.models.star import Star
from app.models.streak import Streak
from app.models.user import User
from app.services import progress_service

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 独立测试库（novastart_test），不碰开发库数据
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"

# 固定「今天」，所有断言按注入时钟推导，禁止 sleep 与真实墙钟
TODAY = date(2026, 11, 7)


class FixedClock:
    """可控时钟：经 get_clock 依赖注入，测试禁止 sleep 墙钟。"""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def set_now(self, now: datetime) -> None:
        self._now = now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


@pytest.fixture
async def db_session():
    """每个用例独立引擎（pytest-asyncio 每用例新事件循环），并重建空表。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncSession:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as session:
        yield session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def db_env():
    """独立引擎 + 会话工厂；并发用例各开连接验证首次建行幂等。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def fixed_clock(client):
    clock = FixedClock(datetime.combine(TODAY, time(12, 0), tzinfo=SHANGHAI_TZ))
    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=SHANGHAI_TZ)


async def _make_user(db_session: AsyncSession, name: str = "测试用户") -> int:
    user = User(name=name)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


async def _seed_session(
    db_session: AsyncSession,
    user_id: int,
    started_at: datetime,
    *,
    duration: int | None = 300,
    status: str = "completed",
    ended: bool = True,
) -> int:
    """直接落库一条任务 + 会话（不走 API），用于精确控制归属日与时长。"""
    day = started_at.astimezone(SHANGHAI_TZ).date()
    task = DayTask(
        user_id=user_id,
        date=day,
        raw_text="读完第三章并做习题",
        starter_step="先读第三章 20 分钟",
        steps=["先读第三章 20 分钟"],
    )
    db_session.add(task)
    await db_session.flush()
    session = Session(
        user_id=user_id,
        task_id=task.id,
        started_at=started_at,
        status=status,
        ended_at=started_at + timedelta(seconds=duration) if ended and duration else None,
        duration_sec=duration if ended else None,
    )
    db_session.add(session)
    await db_session.commit()
    return session.id


def _header(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def _star_row(db_session: AsyncSession, user_id: int, day: date) -> Star | None:
    await db_session.rollback()
    # 已过期实例留在 identity map 里会触发同步懒加载（MissingGreenlet），先清空再取新行
    db_session.expunge_all()
    return await db_session.scalar(
        select(Star).where(Star.user_id == user_id, Star.date == day)
    )


async def _streak_row(db_session: AsyncSession, user_id: int) -> Streak | None:
    await db_session.rollback()
    db_session.expunge_all()
    return await db_session.scalar(select(Streak).where(Streak.user_id == user_id))


async def _progress(client: AsyncClient, user_id: int) -> tuple[int, dict]:
    resp = await client.get("/api/progress/summary", headers=_header(user_id))
    return resp.status_code, resp.json()


async def _make_task(client: AsyncClient, user_id: int) -> int:
    created = await client.post(
        "/api/tasks",
        json={"raw_text": "读完第三章并做习题"},
        headers=_header(user_id),
    )
    assert created.status_code == 201
    task_id = created.json()["task"]["id"]
    analyzed = await client.post(f"/api/tasks/{task_id}/analyze", headers=_header(user_id))
    assert analyzed.status_code == 200
    return task_id


@pytest.mark.parametrize(
    "minutes,level", [(5, 1), (14, 1), (15, 2), (24, 2), (25, 3), (40, 3)]
)
async def test_star_levels(db_session, minutes, level):
    """验收 1：有效时长边界 5/14/15/24/25/40 分钟 → 亮度 1/1/2/2/3/3。"""
    user_id = await _make_user(db_session)
    await _seed_session(db_session, user_id, _at(TODAY, 9), duration=minutes * 60)

    star = await progress_service.recompute_day(db_session, user_id, TODAY)
    await db_session.commit()

    assert star is not None
    assert star.level == level
    assert star.minutes == minutes


async def test_two_sessions_accumulate_one_increment(db_session):
    """验收 2：5+12 分钟累计到同一行 17 分钟 Lv2，连续天数只 +1 一次。"""
    user_id = await _make_user(db_session)
    await _seed_session(db_session, user_id, _at(TODAY, 9), duration=300)
    await _seed_session(db_session, user_id, _at(TODAY, 10), duration=720)

    await progress_service.mark_day_completed(db_session, user_id, TODAY)
    await progress_service.recompute_day(db_session, user_id, TODAY)
    await db_session.commit()

    star = await _star_row(db_session, user_id, TODAY)
    assert star.minutes == 17
    assert star.level == 2
    streak = await _streak_row(db_session, user_id)
    assert streak.current == 1

    # 第二场结束时再触发一次（幂等）：星级累计、连续天数不再 +1
    await progress_service.mark_day_completed(db_session, user_id, TODAY)
    await progress_service.recompute_day(db_session, user_id, TODAY)
    await db_session.commit()
    assert (await _streak_row(db_session, user_id)).current == 1


async def test_cross_midnight_attributed_to_start_day(db_session):
    """验收 3：23:58 开始、00:03 满 5 分钟 → 星星与连续天数记在开始日。"""
    user_id = await _make_user(db_session)
    yesterday = TODAY - timedelta(days=1)
    await _seed_session(db_session, user_id, _at(yesterday, 23, 58), duration=300)

    star = await progress_service.recompute_day(db_session, user_id, yesterday)
    await progress_service.mark_day_completed(db_session, user_id, yesterday)
    await db_session.commit()

    assert star is not None
    assert star.date == yesterday
    assert (await _streak_row(db_session, user_id)).last_completed_date == yesterday
    # 次日归属日无有效场次 → 不建星
    assert await progress_service.recompute_day(db_session, user_id, TODAY) is None


async def test_break_resets_keeps_longest(db_session):
    """验收 4：断档重开 → current=1、was_reset=True、longest 不回退。"""
    user_id = await _make_user(db_session)
    for offset in (3, 2):
        await progress_service.mark_day_completed(db_session, user_id, TODAY - timedelta(days=offset))
        await db_session.commit()

    await progress_service.mark_day_completed(db_session, user_id, TODAY)
    await db_session.commit()

    streak = await _streak_row(db_session, user_id)
    assert streak.current == 1
    assert streak.was_reset is True
    assert streak.longest == 2
    assert streak.last_completed_date == TODAY


async def test_read_side_zero_does_not_write(client, db_session, fixed_clock):
    """验收 5：last 早于昨天 → 响应 current=0，库中 current 不被改写。"""
    user_id = await _make_user(db_session)
    for offset in (5, 4, 3):
        await progress_service.mark_day_completed(db_session, user_id, TODAY - timedelta(days=offset))
    await db_session.commit()

    status_code, data = await _progress(client, user_id)

    assert status_code == 200
    assert data["streak"]["current"] == 0
    assert data["streak"]["longest"] == 3
    stored = await _streak_row(db_session, user_id)
    assert stored.current == 3


async def test_discarded_contributes_nothing(db_session):
    """验收 6：仅 discarded 场次 → 无 stars 行、无 streak 变化。"""
    user_id = await _make_user(db_session)
    await _seed_session(
        db_session, user_id, _at(TODAY, 9), duration=None, status="discarded", ended=False
    )

    assert await progress_service.recompute_day(db_session, user_id, TODAY) is None
    await db_session.commit()

    assert await _star_row(db_session, user_id, TODAY) is None
    assert await _streak_row(db_session, user_id) is None


async def test_end_without_milestone_marks_streak(client, db_session, fixed_clock):
    """验收 7：从未轮询命中 5 分钟里程碑，直接有效结束 → 星星点亮、连续 +1（幂等）。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await client.post(
        "/api/sessions", json={"task_id": task_id}, headers=_header(user_id)
    )
    session_id = started.json()["session_id"]

    fixed_clock.advance(360)
    ended = await client.post(f"/api/sessions/{session_id}/end", headers=_header(user_id))
    assert ended.json()["result"] == "settled"

    star = await _star_row(db_session, user_id, TODAY)
    assert star.level == 1
    assert star.minutes == 6
    streak = await _streak_row(db_session, user_id)
    assert streak.current == 1

    fixed_clock.advance(60)
    await client.post(f"/api/sessions/{session_id}/end", headers=_header(user_id))
    assert (await _streak_row(db_session, user_id)).current == 1


async def test_level_only_increases(db_session):
    """验收 8：已有 Lv2 的日期再次 recompute 得到更小亮级时仍保持 Lv2。"""
    user_id = await _make_user(db_session)
    long_id = await _seed_session(db_session, user_id, _at(TODAY, 9), duration=1200)

    await progress_service.recompute_day(db_session, user_id, TODAY)
    await db_session.commit()
    assert (await _star_row(db_session, user_id, TODAY)).level == 2

    # 去掉 20 分钟那场，只剩 5 分钟：重算得 Lv1，但已有行保持 Lv2
    await db_session.execute(delete(Session).where(Session.id == long_id))
    await db_session.commit()
    await _seed_session(db_session, user_id, _at(TODAY, 10), duration=300)
    await progress_service.recompute_day(db_session, user_id, TODAY)
    await db_session.commit()

    star = await _star_row(db_session, user_id, TODAY)
    assert star.level == 2
    assert star.minutes == 5


async def test_progress_summary_contract(client, db_session, fixed_clock):
    """验收 9：字段齐全，wall 30 项、升序、最后一项为今天。"""
    user_id = await _make_user(db_session)
    await _seed_session(db_session, user_id, _at(TODAY, 9), duration=300)
    await progress_service.recompute_day(db_session, user_id, TODAY)
    await progress_service.mark_day_completed(db_session, user_id, TODAY)
    await db_session.commit()

    status_code, data = await _progress(client, user_id)

    assert status_code == 200
    assert data["today"] == {"minutes": 5, "level": 1}
    assert data["streak"] == {"current": 1, "longest": 1, "was_reset": False}
    wall = data["wall"]
    assert len(wall) == 30
    assert wall[0]["date"] == (TODAY - timedelta(days=29)).isoformat()
    assert wall[-1]["date"] == TODAY.isoformat()
    assert all(w["date"] == (TODAY - timedelta(days=29 - i)).isoformat() for i, w in enumerate(wall))
    assert data["server_time"]


async def test_summary_wall_states(client, db_session, fixed_clock):
    """验收 10：lit / dim / broken / empty 四态；全新账号只有今天 dim。"""
    user_id = await _make_user(db_session)
    first_day = TODAY - timedelta(days=3)
    await _seed_session(db_session, user_id, _at(first_day, 9), duration=300)
    await _seed_session(db_session, user_id, _at(TODAY - timedelta(days=1), 9), duration=300)
    await progress_service.recompute_day(db_session, user_id, first_day)
    await progress_service.recompute_day(db_session, user_id, TODAY - timedelta(days=1))
    await db_session.commit()

    _, data = await _progress(client, user_id)
    states = {w["date"]: w for w in data["wall"]}

    assert states[first_day.isoformat()]["state"] == "lit"
    assert states[first_day.isoformat()]["level"] == 1
    assert states[(TODAY - timedelta(days=2)).isoformat()]["state"] == "broken"
    assert states[(TODAY - timedelta(days=1)).isoformat()]["state"] == "lit"
    assert states[TODAY.isoformat()]["state"] == "dim"
    assert states[TODAY.isoformat()]["level"] is None
    assert states[(TODAY - timedelta(days=4)).isoformat()]["state"] == "empty"

    fresh_id = await _make_user(db_session, "全新账号")
    _, fresh = await _progress(client, fresh_id)
    assert [w["state"] for w in fresh["wall"]] == ["empty"] * 29 + ["dim"]


async def test_settle_summary_filled(client, db_session, fixed_clock):
    """验收 11：P4 summary 的 star_level / streak 与 progress 同源。"""
    user_id = await _make_user(db_session)
    session_id = await _seed_session(db_session, user_id, _at(TODAY, 9), duration=300)
    await progress_service.recompute_day(db_session, user_id, TODAY)
    await progress_service.mark_day_completed(db_session, user_id, TODAY)
    await db_session.commit()

    resp = await client.get(
        f"/api/sessions/{session_id}/summary", headers=_header(user_id)
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["star_level"] == 1
    assert data["streak"] == {"current": 1, "longest": 1, "was_reset": False}


async def test_concurrent_recompute_day_keeps_single_row(db_env):
    """并发首次建星行：不抛 IntegrityError，库中最终只有一行。"""
    async with db_env() as setup:
        user_id = await _make_user(setup)
        await _seed_session(setup, user_id, _at(TODAY, 9), duration=300)

    async def recompute_once() -> None:
        async with db_env() as db:
            await progress_service.recompute_day(db, user_id, TODAY)
            await db.commit()

    await asyncio.gather(recompute_once(), recompute_once())

    async with db_env() as check:
        rows = await check.scalar(
            select(func.count())
            .select_from(Star)
            .where(Star.user_id == user_id, Star.date == TODAY)
        )
    assert rows == 1
