"""F10 随机回顾接口（Spec 007 验收条件 1–8）。"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import get_clock
from app.db import Base, get_session
from app.main import app
from app.models.day_task import DayTask
from app.models.reflection import Reflection
from app.models.session import Session
from app.models.user import User
from app.seed import reset_seed

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


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


@pytest.fixture
async def db_env():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncSession:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def db_session(db_env):
    async with db_env() as session:
        yield session


@pytest.fixture
async def client(db_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def fixed_clock(client):
    clock = FixedClock(datetime(2026, 11, 8, 12, 0, tzinfo=SHANGHAI_TZ))
    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


def _hdr(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def _make_user(db: AsyncSession, name: str) -> User:
    user = User(name=name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _seed_history(
    db: AsyncSession,
    user_id: int,
    started_at: datetime,
    *,
    status: str = "completed",
    ended: bool = True,
    raw_text: str = "读完第三章并做习题",
    reflection: str | None = None,
) -> int:
    """直接落库任务 + 会话（+ 可选感想），返回 session_id；回顾测试不走 API 建会话。"""
    local = started_at.astimezone(SHANGHAI_TZ)
    task = DayTask(
        user_id=user_id,
        date=local.date(),
        raw_text=raw_text,
        starter_step="先读第三章 20 分钟",
        steps=["先读第三章 20 分钟"],
    )
    db.add(task)
    await db.flush()
    session = Session(
        user_id=user_id,
        task_id=task.id,
        started_at=started_at,
        status=status,
        ended_at=started_at + timedelta(minutes=5) if ended else None,
        duration_sec=300 if ended else None,
    )
    db.add(session)
    await db.flush()
    if reflection is not None:
        db.add(
            Reflection(
                user_id=user_id,
                session_id=session.id,
                content=reflection,
                date=local.date(),
            )
        )
    await db.commit()
    await db.refresh(session)
    return session.id


async def _random(client: AsyncClient, user_id: int, exclude_session_id: int):
    return await client.get(
        "/api/review/random",
        params={"exclude_session_id": exclude_session_id},
        headers=_hdr(user_id),
    )


async def test_random_returns_item_shape(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")
    sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        raw_text="读完第三章",
        reflection="今天很有收获",
    )

    res = await _random(client, user.id, 0)

    assert res.status_code == 200
    body = res.json()
    item = body["item"]
    assert item["session_id"] == sid
    assert item["date"] == "2026-11-07"
    assert item["task_text"] == "读完第三章"
    assert item["reflection"] == "今天很有收获"
    assert body["server_time"] == fixed_clock.now().isoformat()


async def test_excludes_today_and_self(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")
    today_sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 8, 9, 0, tzinfo=SHANGHAI_TZ),
        raw_text="今天的任务",
        reflection="今天的感想",
    )
    past_sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        raw_text="昨天的任务",
        reflection="昨天的感想",
    )

    res = await _random(client, user.id, today_sid)

    assert res.status_code == 200
    item = res.json()["item"]
    assert item["session_id"] == past_sid
    assert item["date"] == "2026-11-07"


async def test_excludes_self_when_only_candidate(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")
    past_sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        reflection="只有这一条",
    )

    res = await _random(client, user.id, past_sid)
    assert res.status_code == 200
    assert res.json()["item"] is None

    res = await _random(client, user.id, 0)
    assert res.json()["item"]["session_id"] == past_sid


async def test_today_other_session_excluded(client, db_session, fixed_clock):
    """当天非本场场次一律不入选；07:00 上海 = 前一日 UTC，同时钉住归属日时区口径。"""
    user = await _make_user(db_session, "甲")
    await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 8, 7, 0, tzinfo=SHANGHAI_TZ),
        reflection="今天另一场的感想",
    )

    res = await _random(client, user.id, 0)

    assert res.status_code == 200
    assert res.json()["item"] is None


async def test_empty_pool_returns_null(client, db_session, fixed_clock):
    user = await _make_user(db_session, "刚")
    today_sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 8, 9, 0, tzinfo=SHANGHAI_TZ),
    )

    res = await _random(client, user.id, today_sid)

    assert res.status_code == 200
    assert res.json()["item"] is None


async def test_reflection_nullable(client, db_session, fixed_clock):
    without_user = await _make_user(db_session, "甲")
    await _seed_history(
        db_session,
        without_user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
    )
    res = await _random(client, without_user.id, 0)
    assert res.json()["item"]["reflection"] is None

    with_user = await _make_user(db_session, "乙")
    await _seed_history(
        db_session,
        with_user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        reflection="有感想",
    )
    res = await _random(client, with_user.id, 0)
    assert res.json()["item"]["reflection"] == "有感想"


async def test_discarded_excluded(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")
    await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        status="discarded",
        reflection="被放弃的场次",
    )

    res = await _random(client, user.id, 0)

    assert res.status_code == 200
    assert res.json()["item"] is None


async def test_ongoing_completed_excluded(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")
    await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        status="completed",
        ended=False,
    )

    res = await _random(client, user.id, 0)

    assert res.status_code == 200
    assert res.json()["item"] is None


async def test_cross_midnight_attribution(client, db_session, fixed_clock):
    fixed_clock.set_now(datetime(2026, 11, 8, 0, 10, tzinfo=SHANGHAI_TZ))
    user = await _make_user(db_session, "甲")
    # 昨天 23:58 开始、今天 00:03 结束：归属昨天，今天可被抽到
    sid = await _seed_history(
        db_session,
        user.id,
        datetime(2026, 11, 7, 23, 58, tzinfo=SHANGHAI_TZ),
        reflection="跨零点的感想",
    )

    res = await _random(client, user.id, 0)
    item = res.json()["item"]
    assert item["session_id"] == sid
    assert item["date"] == "2026-11-07"

    res = await _random(client, user.id, sid)
    assert res.json()["item"] is None


async def test_missing_exclude_session_id_422(client, db_session, fixed_clock):
    user = await _make_user(db_session, "甲")

    res = await client.get("/api/review/random", headers=_hdr(user.id))

    assert res.status_code == 422


async def test_unknown_user_404(client, db_session, fixed_clock):
    res = await _random(client, 9999, 0)

    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_seed_history_is_eligible(client, db_session, fixed_clock):
    users = await reset_seed(db_session, fixed_clock)
    xiaoming = users[0]
    expected_dates = {
        (fixed_clock.today() - timedelta(days=n)).isoformat() for n in range(1, 7)
    }

    res = await _random(client, xiaoming.id, 0)

    assert res.status_code == 200
    item = res.json()["item"]
    assert item is not None
    assert item["date"] in expected_dates
    assert item["task_text"]
    assert item["reflection"]
