from datetime import date, datetime, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import get_clock
from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models.day_task import DayTask
from app.models.session import Session
from app.models.user import User

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 独立测试库（novastart_test），不碰开发库数据
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


class FixedClock:
    """可控时钟：经 get_clock 依赖注入，测试禁止 sleep 墙钟。"""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)

    def set_now(self, now: datetime) -> None:
        self._now = now


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
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def fixed_clock(client):
    clock = FixedClock(datetime.now(SHANGHAI_TZ).replace(microsecond=0))
    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


_uid = count(1)


async def _make_user(db_session: AsyncSession) -> int:
    user = User(name="测试用户", username=f"测试用户_{next(_uid)}")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


async def _header(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def _make_task(client: AsyncClient, user_id: int, text: str = "读完第三章并做习题") -> int:
    created = await client.post(
        "/api/tasks",
        json={"raw_text": text},
        headers=await _header(user_id),
    )
    assert created.status_code == 201
    task_id = created.json()["task"]["id"]
    analyzed = await client.post(
        f"/api/tasks/{task_id}/analyze", headers=await _header(user_id)
    )
    assert analyzed.status_code == 200
    return task_id


async def _start(client: AsyncClient, user_id: int, task_id: int) -> dict:
    resp = await client.post(
        "/api/sessions", json={"task_id": task_id}, headers=await _header(user_id)
    )
    assert resp.status_code == 200
    return resp.json()


async def _row(db_session: AsyncSession, session_id: int) -> Session:
    await db_session.rollback()
    row = await db_session.get(Session, session_id)
    assert row is not None
    return row


async def test_duplicate_start_reuses_active(client, db_session) -> None:
    """两次点开始返回同一会话，库中进行中会话仅一条。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)

    first = await _start(client, user_id, task_id)
    second = await _start(client, user_id, task_id)

    assert first["session_id"] == second["session_id"]
    assert first["started_at"] == second["started_at"]

    rows = (
        await db_session.scalars(
            select(Session).where(
                Session.user_id == user_id,
                Session.status.in_(["active", "completed"]),
                Session.ended_at.is_(None),
            )
        )
    ).all()
    assert len(rows) == 1


async def test_start_reuses_completed_without_end(client, db_session, fixed_clock) -> None:
    """5 分钟里程碑后会话仍是进行中（completed 但未结束），再次开始必须复用。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)

    first = await _start(client, user_id, task_id)
    fixed_clock.advance(301)

    current = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert current.json()["session"]["status"] == "completed"
    assert current.json()["session"]["ended_at"] is None

    second = await _start(client, user_id, task_id)
    assert second["session_id"] == first["session_id"]


async def test_create_session_after_ended_creates_new(client, db_session, fixed_clock) -> None:
    """有效结束（ended_at 已写）后再开始，必须新建会话而不是复用。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)

    first = await _start(client, user_id, task_id)
    fixed_clock.advance(300)
    ended = await client.post(
        f"/api/sessions/{first['session_id']}/end", headers=await _header(user_id)
    )
    assert ended.json()["result"] == "settled"

    second = await _start(client, user_id, task_id)

    assert second["session_id"] != first["session_id"]
    row = await _row(db_session, first["session_id"])
    assert row.status == "completed"
    assert row.ended_at is not None


async def test_lazy_min_marks_completed_without_ending(client, db_session, fixed_clock) -> None:
    """299 秒仍 active；300 秒置 completed，但仍未结束（ended_at / duration_sec 为 NULL）。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)

    fixed_clock.advance(299)
    at_299 = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert at_299.json()["session"]["status"] == "active"

    fixed_clock.advance(1)
    at_300 = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert at_300.json()["session"]["status"] == "completed"
    assert at_300.json()["session"]["ended_at"] is None

    row = await _row(db_session, started["session_id"])
    assert row.status == "completed"
    assert row.ended_at is None
    assert row.duration_sec is None


async def test_end_before_min_discarded(client, db_session, fixed_clock) -> None:
    """299 秒结束 → discarded，返回还差 1 秒。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(299)

    resp = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "discarded"
    assert data["duration_sec"] is None
    assert data["short_by_sec"] == 1
    assert data["server_time"]


async def test_discarded_writes_no_duration(client, db_session, fixed_clock) -> None:
    """无效场次时长与结束时间都不落库。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(200)

    await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    row = await _row(db_session, started["session_id"])
    assert row.status == "discarded"
    assert row.ended_at is None
    assert row.duration_sec is None


async def test_discard_unlocks_task_for_retry(client, db_session, fixed_clock) -> None:
    """无效结束完全丢弃：不再锁定当天任务，可重开一场（否则首页进入专注会空转）。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    first = await _start(client, user_id, task_id)
    fixed_clock.advance(59)

    ended = await client.post(
        f"/api/sessions/{first['session_id']}/end", headers=await _header(user_id)
    )
    assert ended.json()["result"] == "discarded"

    today = await client.get("/api/tasks/today", headers=await _header(user_id))
    assert today.json()["task"]["locked"] is False

    second = await _start(client, user_id, task_id)
    assert second["session_id"] != first["session_id"]


async def test_end_at_min_settled(client, db_session, fixed_clock) -> None:
    """300 秒结束 → 有效，duration_sec=300。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(300)

    resp = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    data = resp.json()
    assert data["result"] == "settled"
    assert data["duration_sec"] == 300
    assert data["short_by_sec"] is None

    row = await _row(db_session, started["session_id"])
    assert row.status == "completed"
    assert row.duration_sec == 300
    assert row.ended_at == row.started_at + timedelta(seconds=300)


async def test_end_over_max_capped(client, db_session, fixed_clock) -> None:
    """超过 180 分钟结束，时长封顶 10800 秒。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(10801)

    resp = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    data = resp.json()
    assert data["result"] == "settled"
    assert data["duration_sec"] == 10800

    row = await _row(db_session, started["session_id"])
    assert row.duration_sec == 10800
    assert row.ended_at == row.started_at + timedelta(seconds=10800)


async def test_lazy_180_marks_and_fills_duration(client, db_session, fixed_clock) -> None:
    """已达成 5 分钟的会话继续到 180 分钟后，懒标记补写 ended_at 与 duration_sec。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)

    fixed_clock.advance(301)
    await client.get("/api/sessions/current", headers=await _header(user_id))

    fixed_clock.advance(10800)  # 累计 11101 秒
    resp = await client.get("/api/sessions/current", headers=await _header(user_id))

    data = resp.json()["session"]
    assert data["status"] == "completed"
    assert data["ended_at"] is not None

    row = await _row(db_session, started["session_id"])
    assert row.duration_sec == 10800
    assert row.ended_at == row.started_at + timedelta(seconds=10800)


async def test_repeat_end_idempotent(client, db_session, fixed_clock) -> None:
    """重复结束返回相同结果，库内时长不变。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(300)

    first = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )
    fixed_clock.advance(120)
    second = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    assert first.json()["result"] == second.json()["result"] == "settled"
    assert first.json()["duration_sec"] == second.json()["duration_sec"] == 300

    row = await _row(db_session, started["session_id"])
    assert row.duration_sec == 300


async def test_repeat_end_discarded_idempotent(client, db_session, fixed_clock) -> None:
    """无效场次重复结束仍是 discarded，时长始终为 NULL。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)
    fixed_clock.advance(299)

    first = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )
    fixed_clock.advance(60)
    second = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    assert first.json()["result"] == second.json()["result"] == "discarded"
    assert second.json()["duration_sec"] is None
    assert second.json()["short_by_sec"] == 0

    row = await _row(db_session, started["session_id"])
    assert row.status == "discarded"
    assert row.duration_sec is None


async def test_end_other_users_session_404(client, db_session, fixed_clock) -> None:
    """跨账号结束他人会话 → 404，且不改变对方会话状态。"""
    owner_id = await _make_user(db_session)
    other_id = await _make_user(db_session)
    task_id = await _make_task(client, owner_id)
    started = await _start(client, owner_id, task_id)
    fixed_clock.advance(300)

    resp = await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(other_id)
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SESSION_NOT_FOUND"

    row = await _row(db_session, started["session_id"])
    assert row.status == "active"
    assert row.ended_at is None
    assert row.duration_sec is None


async def test_current_exposes_ended_at_and_task_starter(client, db_session, fixed_clock) -> None:
    """专注页所需的任务文案与结束信号从 current 响应直接可得。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)

    current = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert current.json()["session"]["task_starter_step"]
    assert current.json()["session"]["ended_at"] is None

    fixed_clock.advance(300)
    await client.post(
        f"/api/sessions/{started['session_id']}/end", headers=await _header(user_id)
    )

    ended = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert ended.json()["session"]["ended_at"] is not None
    assert ended.json()["session"]["status"] == "completed"


async def test_thresholds_come_from_settings(client, db_session, fixed_clock, monkeypatch) -> None:
    """演示加速只改 settings，不改代码。"""
    monkeypatch.setattr(settings, "session_min_seconds", 60)
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)

    short = await _start(client, user_id, task_id)
    fixed_clock.advance(59)
    discarded = await client.post(
        f"/api/sessions/{short['session_id']}/end", headers=await _header(user_id)
    )
    assert discarded.json()["result"] == "discarded"
    assert discarded.json()["short_by_sec"] == 1

    valid = await _start(client, user_id, task_id)
    fixed_clock.advance(60)
    settled = await client.post(
        f"/api/sessions/{valid['session_id']}/end", headers=await _header(user_id)
    )
    assert settled.json()["result"] == "settled"
    assert settled.json()["duration_sec"] == 60


async def test_current_exposes_session_max_seconds(client, db_session, monkeypatch) -> None:
    """current 暴露最长时长，前端才能在封顶时刻立即补懒标记（不必等 15s 轮询）。"""
    monkeypatch.setattr(settings, "session_max_seconds", 120)
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    await _start(client, user_id, task_id)

    current = await client.get("/api/sessions/current", headers=await _header(user_id))
    assert current.json()["session_max_seconds"] == 120


async def test_lazy_uses_started_at_across_midnight(
    client, db_session, fixed_clock
) -> None:
    """跨零点只标记完成，不改写 started_at（归属日仍由开始日派生）。"""
    fixed_clock.set_now(datetime(2026, 11, 6, 23, 58, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    started = await _start(client, user_id, task_id)

    fixed_clock.advance(300)

    resp = await client.get("/api/sessions/current", headers=await _header(user_id))
    data = resp.json()["session"]
    assert data["status"] == "completed"
    assert data["started_at"] == started["started_at"]
    assert data["started_at"].startswith("2026-11-06")


async def test_task_starter_step_from_task_owner(client, db_session, fixed_clock) -> None:
    """current 返回的任务文案与任务表当前采用版一致。"""
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    await _start(client, user_id, task_id)

    expected = await db_session.scalar(
        select(DayTask.starter_step).where(DayTask.id == task_id)
    )
    resp = await client.get("/api/sessions/current", headers=await _header(user_id))

    assert resp.json()["session"]["task_starter_step"] == expected
