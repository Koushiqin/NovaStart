"""F6 投递 / 未处理信箱 / 历史信箱 / 发出记录（Spec 006 验收条件 1–17）。"""

import asyncio
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import get_clock
from app.db import Base, get_session
from app.main import app
from app.models.action_log import ActionLog
from app.models.day_task import DayTask
from app.models.letter import Letter
from app.models.reflection import Reflection
from app.models.session import Session
from app.models.user import User
from app.services import letter_service

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
    """独立引擎 + 会话工厂；并发用例另开连接，所有用例共用同一测试库重建。"""
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
    clock = FixedClock(datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ))
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


async def _seed_session(
    db: AsyncSession,
    user_id: int,
    *,
    started_at: datetime | None = None,
    status: str = "completed",
    ended: bool = True,
    duration: int | None = 300,
    raw_text: str = "读完第三章并做习题",
) -> tuple[int, int]:
    """直接落库任务 + 会话，返回 (session_id, task_id)；投递测试不走 API 建会话。"""
    started_at = started_at or datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ)
    task = DayTask(
        user_id=user_id,
        date=started_at.astimezone(SHANGHAI_TZ).date(),
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
        ended_at=started_at + timedelta(seconds=duration) if ended and duration else None,
        duration_sec=duration if ended else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session.id, task.id


async def _seed_reflection(
    db: AsyncSession, user_id: int, session_id: int, content: str, day: date
) -> None:
    db.add(Reflection(user_id=user_id, session_id=session_id, content=content, date=day))
    await db.commit()


def _default_expiry(clock: FixedClock) -> datetime:
    return datetime.combine(clock.today() + timedelta(days=1), time.min, tzinfo=SHANGHAI_TZ)


async def _insert_letter(
    db: AsyncSession,
    recipient_id: int,
    *,
    sender_id: int | None = None,
    session_id: int | None = None,
    content: str = "一封信",
    status: str = "delivered",
    handled: bool = False,
    favorited: bool = False,
    created_at: datetime | None = None,
    expired_at: datetime | None = None,
    focused_delivery: bool = False,
) -> int:
    letter = Letter(
        user_id=recipient_id,
        sender_id=sender_id,
        session_id=session_id,
        content=content,
        status=status,
        handled=handled,
        favorited=favorited,
        focused_delivery=focused_delivery,
        created_at=created_at or datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ),
        expired_at=expired_at or datetime(2026, 11, 8, 0, 0, tzinfo=SHANGHAI_TZ),
    )
    db.add(letter)
    await db.commit()
    await db.refresh(letter)
    return letter.id


async def _inbox(client: AsyncClient, user_id: int) -> list[dict]:
    resp = await client.get("/api/letters/inbox", headers=_hdr(user_id))
    assert resp.status_code == 200
    return resp.json()["letters"]


async def _outbox(client: AsyncClient, user_id: int) -> list[dict]:
    resp = await client.get("/api/letters/outbox", headers=_hdr(user_id))
    assert resp.status_code == 200
    return resp.json()["letters"]


async def _history(client: AsyncClient, user_id: int) -> list[dict]:
    resp = await client.get("/api/letters/history", headers=_hdr(user_id))
    assert resp.status_code == 200
    return resp.json()["letters"]


async def _send(
    client: AsyncClient, sender_id: int, session_id: int, recipient_name: str
) -> object:
    return await client.post(
        "/api/letters",
        json={"session_id": session_id, "recipient_name": recipient_name},
        headers=_hdr(sender_id),
    )


async def test_send_delivered_with_reflection_content(
    client, db_session, fixed_clock
):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id)
    await _seed_reflection(db_session, sender.id, sid, "今天很专注", date(2026, 11, 7))

    resp = await _send(client, sender.id, sid, "小美")

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "delivered"
    assert data["letter_id"] is not None
    inbox = await _inbox(client, recipient.id)
    assert len(inbox) == 1
    assert inbox[0]["content"] == "今天很专注"
    assert inbox[0]["sender_name"] == "小明"
    assert inbox[0]["status"] == "delivered"
    assert inbox[0]["focused_delivery"] is False


async def test_send_falls_back_to_task_text(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id, raw_text="读完第三章并做习题")

    resp = await _send(client, sender.id, sid, "小美")

    assert resp.json()["result"] == "delivered"
    inbox = await _inbox(client, recipient.id)
    assert inbox[0]["content"] == "读完第三章并做习题"


async def test_send_recipient_by_id_and_name(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid1, _ = await _seed_session(db_session, sender.id)
    sid2, _ = await _seed_session(
        db_session, sender.id, started_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ)
    )

    by_name = await _send(client, sender.id, sid1, " 小美 ")
    by_id = await _send(client, sender.id, sid2, str(recipient.id))

    assert by_name.json()["result"] == "delivered"
    assert by_id.json()["result"] == "delivered"
    assert len(await _inbox(client, recipient.id)) == 2


async def test_send_unknown_recipient_no_consume(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    sender_id = sender.id
    recipient = await _make_user(db_session, "小美")
    recipient_id = recipient.id
    sid, _ = await _seed_session(db_session, sender_id)

    unknown = await _send(client, sender_id, sid, "查无此人")

    assert unknown.status_code == 200
    assert unknown.json()["result"] == "rejected_unknown"
    assert unknown.json()["letter_id"] is None
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(Letter)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ActionLog)) == 0

    retry = await _send(client, sender_id, sid, "小美")
    assert retry.json()["result"] == "delivered"
    assert len(await _inbox(client, recipient_id)) == 1


async def test_send_full_rejected_then_resend_succeeds(
    client, db_session, fixed_clock
):
    sender = await _make_user(db_session, "小明")
    sender_id = sender.id
    full = await _make_user(db_session, "小美")
    other = await _make_user(db_session, "小刚")
    full_id, other_id = full.id, other.id
    for i in range(3):
        await _insert_letter(db_session, full_id, content=f"旧信 {i}")
    sid, _ = await _seed_session(db_session, sender_id)

    rejected = await _send(client, sender_id, sid, "小美")

    assert rejected.status_code == 200
    data = rejected.json()
    assert data["result"] == "rejected_full"
    assert data["letter_id"] is not None
    assert len(await _inbox(client, full_id)) == 3
    outbox = await _outbox(client, sender_id)
    assert len(outbox) == 1
    assert outbox[0]["status"] == "undelivered"
    assert outbox[0]["recipient_name"] == "小美"
    # 拒收不占 deliver 幂等键 → 改寄成功
    await db_session.rollback()
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(ActionLog)
            .where(ActionLog.session_id == sid, ActionLog.action_type == "deliver")
        )
        == 0
    )

    retry = await _send(client, sender_id, sid, "小刚")

    assert retry.json()["result"] == "delivered"
    assert len(await _inbox(client, other_id)) == 1


async def test_send_already_sent_idempotent(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    sender_id = sender.id
    first = await _make_user(db_session, "小美")
    second = await _make_user(db_session, "小刚")
    first_id, second_id = first.id, second.id
    sid, _ = await _seed_session(db_session, sender_id)

    assert (await _send(client, sender_id, sid, "小美")).json()["result"] == "delivered"
    again = await _send(client, sender_id, sid, "小刚")

    assert again.status_code == 200
    assert again.json()["result"] == "already_sent"
    assert again.json()["letter_id"] is None
    await db_session.rollback()
    assert (
        await db_session.scalar(
            select(func.count()).select_from(Letter).where(Letter.sender_id == sender_id)
        )
        == 1
    )
    assert len(await _inbox(client, first_id)) == 1
    assert await _inbox(client, second_id) == []


@pytest.mark.parametrize("case", ["missing", "other", "discarded", "unended"])
async def test_send_requires_valid_session(client, db_session, fixed_clock, case):
    sender = await _make_user(db_session, "小明")
    await _make_user(db_session, "小美")
    sid = 999999
    if case == "other":
        owner = await _make_user(db_session, "小刚")
        sid, _ = await _seed_session(db_session, owner.id)
    elif case == "discarded":
        sid, _ = await _seed_session(db_session, sender.id, status="discarded", ended=False, duration=None)
    elif case == "unended":
        sid, _ = await _seed_session(db_session, sender.id, status="active", ended=False, duration=None)

    resp = await _send(client, sender.id, sid, "小美")

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "SESSION_NOT_VALID"
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(Letter)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ActionLog)) == 0


async def test_concurrent_send_only_one_succeeds(db_env, fixed_clock):
    async with db_env() as setup:
        sender_a = await _make_user(setup, "小明")
        sender_b = await _make_user(setup, "小刚")
        recipient = await _make_user(setup, "小美")
        sid_a, _ = await _seed_session(setup, sender_a.id)
        sid_b, _ = await _seed_session(
            setup, sender_b.id, started_at=datetime(2026, 11, 7, 9, 30, tzinfo=SHANGHAI_TZ)
        )
        for i in range(2):
            await _insert_letter(setup, recipient.id, content=f"旧信 {i}")

    async with db_env() as s1, db_env() as s2:
        results = await asyncio.gather(
            letter_service.send(s1, sender_a.id, sid_a, "小美", fixed_clock),
            letter_service.send(s2, sender_b.id, sid_b, "小美", fixed_clock),
        )

    assert {r for r, _ in results} == {"delivered", "rejected_full"}
    async with db_env() as check:
        unhandled = await check.scalar(
            select(func.count())
            .select_from(Letter)
            .where(
                Letter.user_id == recipient.id,
                Letter.status == "delivered",
                Letter.handled == False,  # noqa: E712
            )
        )
        assert unhandled == 3


async def test_focused_delivery_tag(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    focused = await _make_user(db_session, "小美")
    idle = await _make_user(db_session, "小刚")
    await _seed_session(
        db_session, focused.id, status="active", ended=False, duration=None
    )
    sid1, _ = await _seed_session(db_session, sender.id)
    sid2, _ = await _seed_session(
        db_session, sender.id, started_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ)
    )

    assert (await _send(client, sender.id, sid1, "小美")).json()["result"] == "delivered"
    assert (await _send(client, sender.id, sid2, "小刚")).json()["result"] == "delivered"

    focused_letter = (await _inbox(client, focused.id))[0]
    idle_letter = (await _inbox(client, idle.id))[0]
    assert focused_letter["focused_delivery"] is True
    assert idle_letter["focused_delivery"] is False


async def test_dismiss_idempotent_and_not_in_history(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    letter_id = await _insert_letter(db_session, recipient.id)

    first = await client.post(f"/api/letters/{letter_id}/dismiss", headers=_hdr(recipient.id))
    second = await client.post(f"/api/letters/{letter_id}/dismiss", headers=_hdr(recipient.id))

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["letter"]["handled"] is True
    assert second.json()["letter"]["handled"] is True
    assert await _inbox(client, recipient.id) == []
    assert await _history(client, recipient.id) == []
    await db_session.rollback()
    row = await db_session.get(Letter, letter_id)
    assert row.handled is True and row.favorited is False


async def test_dismiss_expired_409(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    letter_id = await _insert_letter(
        db_session,
        recipient.id,
        expired_at=datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ),
    )

    resp = await client.post(f"/api/letters/{letter_id}/dismiss", headers=_hdr(recipient.id))

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LETTER_EXPIRED"
    await db_session.rollback()
    row = await db_session.get(Letter, letter_id)
    assert row.handled is False and row.favorited is False


async def test_favorite_expired_409(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    letter_id = await _insert_letter(
        db_session,
        recipient.id,
        expired_at=datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ),
    )

    resp = await client.post(f"/api/letters/{letter_id}/favorite", headers=_hdr(recipient.id))

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LETTER_EXPIRED"
    await db_session.rollback()
    assert (await db_session.get(Letter, letter_id)).favorited is False


async def test_favorite_idempotent_and_undelivered_404(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    recipient_id = recipient.id
    sender = await _make_user(db_session, "小明")
    sid, _ = await _seed_session(db_session, sender.id)
    letter_id = await _insert_letter(db_session, recipient_id, sender_id=sender.id, session_id=sid)
    undelivered_id = await _insert_letter(
        db_session,
        recipient_id,
        sender_id=sender.id,
        session_id=sid,
        status="undelivered",
        handled=True,
    )

    first = await client.post(f"/api/letters/{letter_id}/favorite", headers=_hdr(recipient_id))
    second = await client.post(f"/api/letters/{letter_id}/favorite", headers=_hdr(recipient_id))

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["letter"]["favorited"] is True
    assert second.json()["letter"]["favorited"] is True
    await db_session.rollback()
    fav_logs = await db_session.scalar(
        select(func.count())
        .select_from(ActionLog)
        .where(ActionLog.session_id == sid, ActionLog.action_type == f"favorite:{letter_id}")
    )
    assert fav_logs == 1

    missing = await client.post(
        f"/api/letters/{undelivered_id}/favorite", headers=_hdr(recipient_id)
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "LETTER_NOT_FOUND"


async def test_inbox_only_delivered_unexpired(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    keep = await _insert_letter(db_session, recipient.id, content="应显示")
    await _insert_letter(db_session, recipient.id, content="已处理", handled=True)
    await _insert_letter(
        db_session,
        recipient.id,
        content="已过期",
        expired_at=datetime(2026, 11, 7, 11, 0, tzinfo=SHANGHAI_TZ),
    )
    await _insert_letter(
        db_session,
        recipient.id,
        content="未送达",
        status="undelivered",
        handled=True,
    )

    inbox = await _inbox(client, recipient.id)

    assert [l["id"] for l in inbox] == [keep]
    assert len(inbox) <= 3


async def test_history_only_favorited_and_lazy_cleanup_100(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    recipient_id = recipient.id
    base = datetime(2026, 1, 1, 0, 0, tzinfo=SHANGHAI_TZ)
    for i in range(101):
        await _insert_letter(
            db_session,
            recipient_id,
            content=f"收藏 {i}",
            handled=True,
            favorited=True,
            created_at=base + timedelta(minutes=i),
            expired_at=base + timedelta(minutes=i),
        )
    await _insert_letter(db_session, recipient_id, content="已放弃", handled=True, favorited=False)

    letters = await _history(client, recipient_id)

    assert len(letters) == 100
    assert "已放弃" not in {l["content"] for l in letters}
    assert "收藏 0" not in {l["content"] for l in letters}
    await db_session.rollback()
    favorited_total = await db_session.scalar(
        select(func.count())
        .select_from(Letter)
        .where(Letter.user_id == recipient_id, Letter.favorited == True)  # noqa: E712
    )
    assert favorited_total == 100


async def test_outbox_lists_delivered_and_undelivered(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    delivered_to = await _make_user(db_session, "小美")
    full = await _make_user(db_session, "小刚")
    await _insert_letter(
        db_session,
        delivered_to.id,
        sender_id=sender.id,
        content="顺利寄出",
        created_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
    )
    await _insert_letter(
        db_session,
        full.id,
        sender_id=sender.id,
        content="被拒收",
        status="undelivered",
        handled=True,
        created_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ),
    )

    letters = await _outbox(client, sender.id)

    assert [l["status"] for l in letters] == ["undelivered", "delivered"]
    assert [l["recipient_name"] for l in letters] == ["小刚", "小美"]
    assert [l["content"] for l in letters] == ["被拒收", "顺利寄出"]


async def test_delete_favorited_letter(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    letter_id = await _insert_letter(
        db_session, recipient.id, content="可删除", handled=True, favorited=True
    )
    unlisted = await _insert_letter(db_session, recipient.id, content="未收藏")

    first = await client.delete(f"/api/letters/{letter_id}", headers=_hdr(recipient.id))
    second = await client.delete(f"/api/letters/{letter_id}", headers=_hdr(recipient.id))
    not_favorited = await client.delete(
        f"/api/letters/{unlisted}", headers=_hdr(recipient.id)
    )

    assert first.status_code == 204
    assert second.status_code == 404
    assert second.json()["detail"]["code"] == "LETTER_NOT_FOUND"
    assert not_favorited.status_code == 404
    assert await _history(client, recipient.id) == []


async def test_summary_received_during_session(client, db_session, fixed_clock):
    receiver = await _make_user(db_session, "小美")
    sender = await _make_user(db_session, "小明")
    sid, _ = await _seed_session(
        db_session,
        receiver.id,
        started_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ),
        duration=300,
    )
    inside = datetime(2026, 11, 7, 9, 2, tzinfo=SHANGHAI_TZ)
    for i in range(2):
        await _insert_letter(
            db_session,
            receiver.id,
            sender_id=sender.id,
            content=f"专注时 {i}",
            created_at=inside + timedelta(seconds=i),
        )
    await _insert_letter(
        db_session,
        receiver.id,
        sender_id=sender.id,
        content="窗口外",
        created_at=datetime(2026, 11, 7, 10, 0, tzinfo=SHANGHAI_TZ),
    )
    await _insert_letter(
        db_session,
        receiver.id,
        sender_id=sender.id,
        content="未送达",
        status="undelivered",
        handled=True,
        created_at=inside,
    )

    resp = await client.get(f"/api/sessions/{sid}/summary", headers=_hdr(receiver.id))

    assert resp.status_code == 200
    assert resp.json()["received_during_session"] == 2


async def test_unhandled_expiry_crosses_midnight(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id, started_at=datetime(2026, 11, 7, 23, 59, tzinfo=SHANGHAI_TZ))
    fixed_clock.set_now(datetime(2026, 11, 7, 23, 59, tzinfo=SHANGHAI_TZ))

    sent = await _send(client, sender.id, sid, "小美")
    assert sent.json()["result"] == "delivered"
    letters = await _inbox(client, recipient.id)
    assert len(letters) == 1
    assert letters[0]["expired_at"] == "2026-11-08T00:00:00+08:00"

    fixed_clock.set_now(datetime(2026, 11, 8, 0, 0, tzinfo=SHANGHAI_TZ))
    assert await _inbox(client, recipient.id) == []

    letter_id = letters[0]["id"]
    favorite = await client.post(
        f"/api/letters/{letter_id}/favorite", headers=_hdr(recipient.id)
    )
    dismiss = await client.post(
        f"/api/letters/{letter_id}/dismiss", headers=_hdr(recipient.id)
    )
    assert favorite.status_code == 409
    assert favorite.json()["detail"]["code"] == "LETTER_EXPIRED"
    assert dismiss.status_code == 409
    assert dismiss.json()["detail"]["code"] == "LETTER_EXPIRED"


async def test_expired_unhandled_letters_do_not_block_capacity(
    client, db_session, fixed_clock
):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id)
    for i in range(3):
        await _insert_letter(
            db_session,
            recipient.id,
            content=f"过期信 {i}",
            # == fixed_clock.now()，已过期
            expired_at=datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ),
        )

    resp = await _send(client, sender.id, sid, "小美")

    assert resp.status_code == 200
    assert resp.json()["result"] == "delivered"


async def test_concurrent_deliver_same_session_idempotent(db_env, fixed_clock):
    async with db_env() as setup:
        sender = await _make_user(setup, "小明")
        await _make_user(setup, "小美")
        sid, _ = await _seed_session(setup, sender.id)

    async with db_env() as s1, db_env() as s2:
        results = await asyncio.gather(
            letter_service.send(s1, sender.id, sid, "小美", fixed_clock),
            letter_service.send(s2, sender.id, sid, "小美", fixed_clock),
        )

    assert sorted(r for r, _ in results) == ["already_sent", "delivered"]
    async with db_env() as check:
        assert (
            await check.scalar(
                select(func.count()).select_from(Letter).where(Letter.session_id == sid)
            )
            == 1
        )


async def test_retry_deliver_with_overlong_content_returns_already_sent(
    client, db_session, fixed_clock
):
    sender = await _make_user(db_session, "小明")
    await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id, raw_text="长" * 201)
    db_session.add(ActionLog(session_id=sid, action_type="deliver"))
    await db_session.commit()

    resp = await _send(client, sender.id, sid, "小美")

    assert resp.status_code == 200
    assert resp.json()["result"] == "already_sent"


async def test_favorite_handled_letter_409(client, db_session, fixed_clock):
    recipient = await _make_user(db_session, "小美")
    letter_id = await _insert_letter(db_session, recipient.id, handled=True)

    resp = await client.post(
        f"/api/letters/{letter_id}/favorite", headers=_hdr(recipient.id)
    )

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LETTER_ALREADY_HANDLED"
    await db_session.rollback()
    assert (await db_session.get(Letter, letter_id)).favorited is False


async def test_duplicate_recipient_name_picks_smallest_id(
    client, db_session, fixed_clock
):
    sender = await _make_user(db_session, "小明")
    sender_id = sender.id
    # 先插大 id、后插小 id：seq scan 的物理行序与 id 序相反，
    # 未加 ORDER BY 时当前实现会返回大 id 那位。
    db_session.add(User(id=900001, name="小美"))
    await db_session.commit()
    db_session.add(User(id=900000, name="小美"))
    await db_session.commit()
    sid, _ = await _seed_session(db_session, sender_id)

    resp = await _send(client, sender_id, sid, "小美")

    assert resp.status_code == 200
    assert resp.json()["result"] == "delivered"
    await db_session.rollback()
    letter = await db_session.scalar(select(Letter).where(Letter.session_id == sid))
    assert letter.user_id == 900000


async def test_concurrent_retry_near_capacity_still_already_sent(
    db_env, fixed_clock
):
    """收件人已有 2 封有效未处理信时，同场并发重试不得走到拒收分支。"""
    async with db_env() as setup:
        sender = await _make_user(setup, "小明")
        recipient = await _make_user(setup, "小美")
        sid, _ = await _seed_session(setup, sender.id)
        for i in range(2):
            await _insert_letter(setup, recipient.id, content=f"旧信 {i}")

    async with db_env() as s1, db_env() as s2:
        results = await asyncio.gather(
            letter_service.send(s1, sender.id, sid, "小美", fixed_clock),
            letter_service.send(s2, sender.id, sid, "小美", fixed_clock),
        )

    assert sorted(r for r, _ in results) == ["already_sent", "delivered"]
    async with db_env() as check:
        letters = list(
            (await check.scalars(select(Letter).where(Letter.session_id == sid))).all()
        )
        assert len(letters) == 1
        assert letters[0].status == "delivered"
        assert (
            await check.scalar(
                select(func.count())
                .select_from(Letter)
                .where(Letter.status == "undelivered")
            )
            == 0
        )

