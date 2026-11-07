from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import Clock
from app.db import Base, get_session
from app.main import app
from app.models.action_log import ActionLog
from app.models.day_task import DayTask
from app.models.letter import Letter
from app.models.session import Session
from app.models.user import User
from app.services import letter_service

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 独立测试库（novastart_test），不碰开发库数据；行锁/timestamptz 依赖真实 PG
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


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


async def _make_user(db_session: AsyncSession) -> int:
    user = User(name="测试用户")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


async def _make_session_row(
    db_session: AsyncSession, user_id: int, status: str = "active", *, ended: bool = False
) -> int:
    """直接落库一条会话（deliver/settle 测试不走 API 建会话）。"""
    task = DayTask(
        user_id=user_id,
        date=datetime.now(SHANGHAI_TZ).date(),
        raw_text="任务",
        starter_step="开始",
        steps=["开始"],
    )
    db_session.add(task)
    await db_session.flush()
    started_at = datetime.now(SHANGHAI_TZ)
    session = Session(
        user_id=user_id,
        task_id=task.id,
        started_at=started_at,
        status=status,
        ended_at=started_at + timedelta(minutes=5) if ended else None,
        duration_sec=300 if ended else None,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session.id


async def _session_row(db_session: AsyncSession, session_id: int) -> Session:
    await db_session.rollback()
    row = await db_session.get(Session, session_id)
    assert row is not None
    return row


async def test_inbox_caps_at_three_unhandled(client, db_session):
    user_id = await _make_user(db_session)
    for i in range(4):
        sid = await _make_session_row(db_session, user_id)
        await letter_service.deliver(db_session, user_id, sid, f"第 {i + 1} 封信", Clock())

    resp = await client.get("/api/letters/inbox", headers={"X-User-Id": str(user_id)})

    assert resp.status_code == 200
    assert len(resp.json()["letters"]) == 3  # 第 4 封被丢弃


async def test_deliver_same_session_only_once(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id)

    first = await letter_service.deliver(db_session, user_id, sid, "内容A", Clock())
    second = await letter_service.deliver(db_session, user_id, sid, "内容B", Clock())

    assert first is not None
    assert second is None  # ActionLog 唯一约束挡住重复投递
    count = await db_session.scalar(
        select(func.count()).select_from(Letter).where(Letter.session_id == sid)
    )
    assert count == 1


async def test_inbox_excludes_expired_letters(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id)
    letter = await letter_service.deliver(db_session, user_id, sid, "会过期的信", Clock())

    # 把 expired_at 改到昨天，模拟已过期
    await db_session.execute(
        update(Letter)
        .where(Letter.id == letter.id)
        .values(expired_at=datetime.now(SHANGHAI_TZ) - timedelta(days=1))
    )
    await db_session.commit()

    resp = await client.get("/api/letters/inbox", headers={"X-User-Id": str(user_id)})
    ids = [l["id"] for l in resp.json()["letters"]]
    assert letter.id not in ids


async def test_favorite_is_idempotent(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id)
    letter = await letter_service.deliver(db_session, user_id, sid, "可收藏的信", Clock())

    r1 = await client.post(
        f"/api/letters/{letter.id}/favorite", headers={"X-User-Id": str(user_id)}
    )
    r2 = await client.post(
        f"/api/letters/{letter.id}/favorite", headers={"X-User-Id": str(user_id)}
    )

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["letter"]["favorited"] is True
    assert r2.json()["letter"]["favorited"] is True  # 重复调用返回一致
    fav_logs = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.session_id == sid, ActionLog.action_type == f"favorite:{letter.id}")
    )
    assert fav_logs == 1  # 不写重复 ActionLog


async def test_settle_advance_idempotent_and_monotonic(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id, status="completed", ended=True)

    headers = {"X-User-Id": str(user_id)}
    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2}, headers=headers)
    assert r.json()["settle_step"] == 2
    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2}, headers=headers)
    assert r.json()["settle_step"] == 2  # 重复调用幂等
    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 3}, headers=headers)
    assert r.json()["settle_step"] == 3
    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2}, headers=headers)
    assert r.json()["settle_step"] == 3  # 回退请求不生效


async def test_advance_rejects_in_progress(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id, status="completed")  # ended_at=None

    resp = await client.post(
        f"/api/settle/{sid}/advance",
        json={"to_step": 2},
        headers={"X-User-Id": str(user_id)},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SESSION_NOT_FOUND"
    assert (await _session_row(db_session, sid)).settle_step == 0


async def test_advance_rejects_other_users_session(client, db_session):
    owner_id = await _make_user(db_session)
    other_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, owner_id, status="completed", ended=True)

    resp = await client.post(
        f"/api/settle/{sid}/advance",
        json={"to_step": 2},
        headers={"X-User-Id": str(other_id)},
    )

    assert resp.status_code == 404
    assert (await _session_row(db_session, sid)).settle_step == 0


async def test_advance_four_marks_settled_and_monotonic(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id, status="completed", ended=True)
    headers = {"X-User-Id": str(user_id)}

    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 4}, headers=headers)
    assert r.json()["settle_step"] == 4
    row = await _session_row(db_session, sid)
    assert row.status == "settled"

    r2 = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2}, headers=headers)
    assert r2.json()["settle_step"] == 4
    row = await _session_row(db_session, sid)
    assert row.status == "settled"
    assert row.settle_step == 4


async def test_history_lazy_cleanup_keeps_latest_100(client, db_session):
    user_id = await _make_user(db_session)
    base = datetime.now(SHANGHAI_TZ) - timedelta(days=200)
    for i in range(105):
        db_session.add(
            Letter(
                user_id=user_id,
                session_id=None,
                content=f"历史 {i}",
                handled=True,
                expired_at=base + timedelta(seconds=i),
                created_at=base + timedelta(seconds=i),
            )
        )
    await db_session.commit()

    resp = await client.get("/api/letters/history", headers={"X-User-Id": str(user_id)})

    assert resp.status_code == 200
    letters = resp.json()["letters"]
    assert len(letters) == 100
    total = await db_session.scalar(
        select(func.count()).select_from(Letter).where(Letter.user_id == user_id)
    )
    assert total == 100  # 库里也只留 100 条
    remaining = {l["content"] for l in letters}
    for i in range(5):
        assert f"历史 {i}" not in remaining  # 最旧 5 条已被删除


async def test_inbox_expiry_uses_injected_clock(db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id)

    now = Clock()
    await letter_service.deliver(db_session, user_id, sid, "今天的信", now)
    assert len(await letter_service.get_inbox(db_session, user_id, now)) == 1

    later = Clock(offset_seconds=86400)
    assert await letter_service.get_inbox(db_session, user_id, later) == []
