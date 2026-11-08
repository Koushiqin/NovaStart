from datetime import date, datetime, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import get_clock
from app.db import Base, get_session
from app.main import app
from app.models.day_task import DayTask
from app.models.reflection import Reflection
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


def _header(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def _seed_session(
    db_session: AsyncSession,
    user_id: int,
    *,
    started_at: datetime | None = None,
    status: str = "completed",
    ended: bool = True,
    duration: int | None = 300,
    settle_step: int = 0,
    raw_text: str = "读完第三章并做习题",
    starter_step: str = "先读第三章 20 分钟",
) -> int:
    """直接落库一条任务 + 会话，结算测试不走 API 建会话。"""
    started_at = started_at or datetime.now(SHANGHAI_TZ)
    task = DayTask(
        user_id=user_id,
        date=started_at.astimezone(SHANGHAI_TZ).date(),
        raw_text=raw_text,
        starter_step=starter_step,
        steps=[starter_step],
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
        settle_step=settle_step,
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


async def _reflection_count(db_session: AsyncSession, session_id: int) -> int:
    await db_session.rollback()
    return await db_session.scalar(
        select(func.count()).select_from(Reflection).where(Reflection.session_id == session_id)
    )


async def _summary(client: AsyncClient, session_id: int, user_id: int) -> tuple[int, dict]:
    resp = await client.get(
        f"/api/sessions/{session_id}/summary", headers=_header(user_id)
    )
    return resp.status_code, resp.json()


async def _reflect(client: AsyncClient, session_id: int, user_id: int, content: str) -> object:
    return await client.post(
        f"/api/sessions/{session_id}/reflection",
        json={"content": content},
        headers=_header(user_id),
    )


async def test_summary_fields(client, db_session, fixed_clock):
    fixed_clock.set_now(datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    sid = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ)
    )

    status_code, data = await _summary(client, sid, user_id)

    assert status_code == 200
    assert data["attribution_date"] == "2026-11-07"
    assert data["duration_sec"] == 300
    assert data["today_total_sec"] == 300
    assert data["task_text"] == "读完第三章并做习题"
    assert data["starter_text"] == "先读第三章 20 分钟"
    assert data["settle_step"] == 0
    assert data["status"] == "completed"
    assert data["received_during_session"] == 0
    assert data["star_level"] is None
    assert data["streak"] is None
    assert data["server_time"]


async def test_summary_today_total_valid_only(client, db_session, fixed_clock):
    """当天另有一场 discarded 与一场有效场次：只累计有效且已结束的。"""
    fixed_clock.set_now(datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    main = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ)
    )
    await _seed_session(
        db_session,
        user_id,
        started_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ),
        duration=120,
    )
    await _seed_session(
        db_session,
        user_id,
        started_at=datetime(2026, 11, 7, 11, 0, tzinfo=SHANGHAI_TZ),
        status="discarded",
        ended=False,
        duration=None,
    )

    status_code, data = await _summary(client, main, user_id)

    assert status_code == 200
    assert data["today_total_sec"] == 420


async def test_summary_excludes_ongoing_completed(client, db_session, fixed_clock):
    """当天另一场仅达 5 分钟里程碑但未结束（ended_at=NULL）→ 不计入。"""
    fixed_clock.set_now(datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    main = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ)
    )
    await _seed_session(
        db_session,
        user_id,
        started_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ),
        status="completed",
        ended=False,
        duration=None,
    )

    status_code, data = await _summary(client, main, user_id)

    assert status_code == 200
    assert data["today_total_sec"] == 300


@pytest.mark.parametrize(
    "started_at",
    [
        datetime(2026, 11, 7, 23, 30, tzinfo=SHANGHAI_TZ),
        datetime(2026, 11, 7, 0, 30, tzinfo=SHANGHAI_TZ),
    ],
    ids=["23:30", "00:30"],
)
async def test_summary_attribution_day_across_midnight(
    client, db_session, fixed_clock, started_at
):
    """归属日按 started_at 的 Asia/Shanghai 日期：前一日场次不串入当天累计。"""
    fixed_clock.set_now(started_at)
    user_id = await _make_user(db_session)
    main = await _seed_session(db_session, user_id, started_at=started_at)
    await _seed_session(
        db_session,
        user_id,
        started_at=datetime(2026, 11, 6, 23, 30, tzinfo=SHANGHAI_TZ),
        duration=600,
    )

    status_code, data = await _summary(client, main, user_id)

    assert status_code == 200
    assert data["today_total_sec"] == 300


async def test_summary_attribution_date_across_midnight(client, db_session, fixed_clock):
    """凌晨结算昨日开始的场次：日期标签取归属日，不取 clock.today()。"""
    fixed_clock.set_now(datetime(2026, 11, 7, 0, 10, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    sid = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 6, 23, 50, tzinfo=SHANGHAI_TZ)
    )

    status_code, data = await _summary(client, sid, user_id)

    assert status_code == 200
    assert data["attribution_date"] == "2026-11-06"
    assert data["today_total_sec"] == 300


async def test_summary_discarded_session_404(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id, status="discarded", ended=False, duration=None)

    status_code, data = await _summary(client, sid, user_id)

    assert status_code == 404
    assert data["detail"]["code"] == "SESSION_NOT_FOUND"


async def test_summary_other_user_404(client, db_session, fixed_clock):
    owner_id = await _make_user(db_session)
    other_id = await _make_user(db_session)
    sid = await _seed_session(db_session, owner_id)

    status_code, data = await _summary(client, sid, other_id)

    assert status_code == 404
    assert data["detail"]["code"] == "SESSION_NOT_FOUND"


async def test_summary_unended_or_missing_404(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    ongoing = await _seed_session(
        db_session, user_id, status="completed", ended=False, duration=None
    )

    for session_id in (ongoing, 999999):
        status_code, data = await _summary(client, session_id, user_id)
        assert status_code == 404
        assert data["detail"]["code"] == "SESSION_NOT_FOUND"


async def test_reflection_save_advances_step(client, db_session, fixed_clock):
    """跨零点写感想：date 记会话归属日，settle_step 推进到 1。"""
    fixed_clock.set_now(datetime(2026, 11, 7, 0, 10, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    sid = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 6, 23, 50, tzinfo=SHANGHAI_TZ)
    )

    resp = await _reflect(client, sid, user_id, "  今天很专注  ")

    assert resp.status_code == 201
    data = resp.json()
    assert data["reflection"]["content"] == "今天很专注"
    assert data["settle_step"] == 1
    assert data["server_time"]

    reflection = await db_session.scalar(
        select(Reflection).where(Reflection.session_id == sid)
    )
    assert reflection.content == "今天很专注"
    assert reflection.date == date(2026, 11, 6)
    assert (await _session_row(db_session, sid)).settle_step == 1


async def test_reflection_blank_skips(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id)

    resp = await _reflect(client, sid, user_id, "   ")

    assert resp.status_code == 201
    data = resp.json()
    assert data["reflection"] is None
    assert data["settle_step"] == 1
    assert await _reflection_count(db_session, sid) == 0
    assert (await _session_row(db_session, sid)).settle_step == 1


async def test_reflection_repeat_409(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id)

    first = await _reflect(client, sid, user_id, "第一条感想")
    second = await _reflect(client, sid, user_id, "第二条感想")

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "REFLECTION_LOCKED"
    assert await _reflection_count(db_session, sid) == 1
    assert (await _session_row(db_session, sid)).settle_step == 1


async def test_reflection_after_skip_409(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id)

    skipped = await _reflect(client, sid, user_id, "")
    retried = await _reflect(client, sid, user_id, "跳过后想补写")

    assert skipped.status_code == 201
    assert skipped.json()["reflection"] is None
    assert retried.status_code == 409
    assert retried.json()["detail"]["code"] == "REFLECTION_LOCKED"
    assert await _reflection_count(db_session, sid) == 0
    assert (await _session_row(db_session, sid)).settle_step == 1


async def test_reflection_over_200_422(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id)

    resp = await _reflect(client, sid, user_id, "a" * 201)

    assert resp.status_code == 422
    assert await _reflection_count(db_session, sid) == 0
    assert (await _session_row(db_session, sid)).settle_step == 0


async def test_reflection_discarded_404(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id, status="discarded", ended=False, duration=None)

    resp = await _reflect(client, sid, user_id, "无效场次的感想")

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SESSION_NOT_FOUND"
    assert await _reflection_count(db_session, sid) == 0
    assert (await _session_row(db_session, sid)).settle_step == 0


async def test_advance_step4_marks_settled(client, db_session, fixed_clock):
    """连续推进 1→4：第④步完成置 settled，再重复推进保持 4。"""
    user_id = await _make_user(db_session)
    sid = await _seed_session(db_session, user_id)

    for step in (1, 2, 3, 4):
        resp = await client.post(
            f"/api/settle/{sid}/advance",
            json={"to_step": step},
            headers=_header(user_id),
        )
        assert resp.status_code == 200
        assert resp.json()["settle_step"] == step

    row = await _session_row(db_session, sid)
    assert row.status == "settled"
    assert row.settle_step == 4

    repeat = await client.post(
        f"/api/settle/{sid}/advance", json={"to_step": 4}, headers=_header(user_id)
    )
    assert repeat.json()["settle_step"] == 4
