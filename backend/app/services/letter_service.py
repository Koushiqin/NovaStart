from datetime import datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import SHANGHAI_TZ, Clock
from app.models.action_log import ActionLog
from app.models.day_task import DayTask
from app.models.letter import Letter
from app.models.reflection import Reflection
from app.models.session import Session
from app.models.user import User
from app.services import user_service
from app.services.settle_service import SETTLEABLE_STATUSES

# 未处理信箱上限：达到后拒收（拒收不消耗投递机会）
INBOX_MAX_UNHANDLED = 3
# 历史信件上限：超出部分在读取时懒清理
HISTORY_LIMIT = 100
# 信件正文上限（与感想 / 任务内容一致）
CONTENT_MAX_LENGTH = 200
# 进行中会话：5 分钟里程碑会把 active 置为 completed，但计时仍在继续（ended_at 为空）
ONGOING_STATUSES = ("active", "completed")


class SessionNotValid(Exception):
    """会话不存在 / 非本人 / discarded / 未结束：不能投递。"""


class LetterExpired(Exception):
    """信件已过当日 24:00，不能再收藏或放弃。"""


class LetterAlreadyHandled(Exception):
    """信件已被放弃或已收藏为历史，不能再用收藏「复活」。"""


class ContentTooLong(Exception):
    """信件正文超过 200 字。"""


def _expiry(clock: Clock) -> datetime:
    """未收藏信的失效时刻 = 收到日次日 00:00（Asia/Shanghai）。"""
    return datetime.combine(clock.today() + timedelta(days=1), time.min, tzinfo=SHANGHAI_TZ)


async def _recipient_is_focused(db: AsyncSession, recipient_id: int) -> bool:
    """收件人此刻是否有进行中会话（专注时投递标签）。"""
    return (
        await db.scalar(
            select(Session.id)
            .where(
                Session.user_id == recipient_id,
                Session.status.in_(ONGOING_STATUSES),
                Session.ended_at.is_(None),
            )
            .limit(1)
        )
    ) is not None


async def _letter_content(db: AsyncSession, session: Session) -> str:
    """正文 = 本场感想去空白；无感想则本场任务当前采用版 raw_text。"""
    reflection = await db.scalar(
        select(Reflection.content).where(Reflection.session_id == session.id)
    )
    if reflection and reflection.strip():
        text = reflection.strip()
    else:
        raw = await db.scalar(select(DayTask.raw_text).where(DayTask.id == session.task_id))
        text = (raw or "").strip()
    if len(text) > CONTENT_MAX_LENGTH:
        raise ContentTooLong
    return text


async def send(
    db: AsyncSession, sender_id: int, session_id: int, recipient_name: str, clock: Clock
) -> tuple[str, int | None]:
    """投递一封信，返回 (四态结果, letter_id)。

    四态：delivered / rejected_full / rejected_unknown / already_sent。
    事务顺序（Spec 006 §6.3）：校验会话 → 解析收件人 → 查 deliver 幂等键 →
    行锁计数 → 满 3 拒收（只写 undelivered 记录，不占 deliver 键）→ 成功写键+信。
    """
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == sender_id,
            Session.ended_at.is_not(None),
            Session.status.in_(SETTLEABLE_STATUSES),
        )
    )
    if session is None:
        raise SessionNotValid

    recipient = await user_service.find_by_name_or_id(db, recipient_name)
    if recipient is None:
        return "rejected_unknown", None

    # 幂等键先于正文校验：已投递场次的重试直接返回 already_sent，
    # 不因历史原文超长而得到 422。
    already = await db.scalar(
        select(ActionLog.id).where(
            ActionLog.session_id == session_id, ActionLog.action_type == "deliver"
        )
    )
    if already is not None:
        return "already_sent", None

    text = await _letter_content(db, session)

    # 先锁收件人 users 行：FOR UPDATE 只锁已存在的 letters 行，锁不住并发插入的幻影行；
    # 锁顺序统一为 users 行 → letters 行，dismiss/favorite 不锁 users，无环。
    await db.scalar(select(User.id).where(User.id == recipient.id).with_for_update())

    # 拿锁后重查幂等键：并发重试的后来者在锁前可能读到无键，
    # 等锁期间对方已提交，此时应返回 already_sent 而非走到拒收分支。
    if (
        await db.scalar(
            select(ActionLog.id).where(
                ActionLog.session_id == session_id, ActionLog.action_type == "deliver"
            )
        )
        is not None
    ):
        return "already_sent", None

    # 行锁锁住收件人全部已投递且未处理、未过期的信，并发投递时串行化计数
    unhandled = (
        await db.execute(
            select(Letter.id)
            .where(
                Letter.user_id == recipient.id,
                Letter.status == "delivered",
                Letter.handled == False,  # noqa: E712
                Letter.expired_at > clock.now(),
            )
            .with_for_update()
        )
    ).all()

    if len(unhandled) >= INBOX_MAX_UNHANDLED:
        # 拒收只写发送方的 undelivered 记录；键不阻止后续 deliver（机会未消耗）
        try:
            async with db.begin_nested():
                db.add(
                    ActionLog(
                        session_id=session_id,
                        action_type=f"deliver_undelivered:{recipient.id}",
                    )
                )
                await db.flush()
        except IntegrityError:
            await db.rollback()
            return "rejected_full", await db.scalar(
                select(Letter.id)
                .where(
                    Letter.user_id == recipient.id,
                    Letter.session_id == session_id,
                    Letter.status == "undelivered",
                )
                .order_by(Letter.id.desc())
                .limit(1)
            )
        letter = Letter(
            user_id=recipient.id,
            sender_id=sender_id,
            session_id=session_id,
            content=text,
            status="undelivered",
            handled=True,
            expired_at=_expiry(clock),
        )
        db.add(letter)
        await db.commit()
        await db.refresh(letter)
        return "rejected_full", letter.id

    # 专注标签查询必须在 db.add 之前完成：autoflush 会提前把幂等键写库，
    # IntegrityError 需落在下面的 try/except 内才能返回 already_sent。
    focused_delivery = await _recipient_is_focused(db, recipient.id)
    letter = Letter(
        user_id=recipient.id,
        sender_id=sender_id,
        session_id=session_id,
        content=text,
        status="delivered",
        handled=False,
        focused_delivery=focused_delivery,
        expired_at=_expiry(clock),
    )
    db.add(ActionLog(session_id=session_id, action_type="deliver"))
    db.add(letter)
    try:
        await db.commit()
    except IntegrityError:
        # 并发双击：另一事务已占 deliver 键
        await db.rollback()
        return "already_sent", None
    await db.refresh(letter)
    return "delivered", letter.id


async def get_inbox(db: AsyncSession, user_id: int, clock: Clock) -> list[Letter]:
    """未处理未过期的已投递信件（懒失效：过期判断在查询条件里，不后台清扫）。"""
    result = await db.execute(
        select(Letter)
        .where(
            Letter.user_id == user_id,
            Letter.status == "delivered",
            Letter.handled == False,  # noqa: E712
            Letter.expired_at > clock.now(),
        )
        .order_by(Letter.created_at.desc())
        .limit(INBOX_MAX_UNHANDLED)
    )
    return list(result.scalars().all())


async def get_history(db: AsyncSession, user_id: int) -> list[Letter]:
    """历史信箱 = 本人已投递且已收藏；读取时懒清理超过 100 的最旧信件。"""
    result = await db.execute(
        select(Letter)
        .where(
            Letter.user_id == user_id,
            Letter.status == "delivered",
            Letter.favorited == True,  # noqa: E712
        )
        .order_by(Letter.created_at.desc())
    )
    letters = list(result.scalars().all())
    if len(letters) > HISTORY_LIMIT:
        stale_ids = [letter.id for letter in letters[HISTORY_LIMIT:]]
        await db.execute(delete(Letter).where(Letter.id.in_(stale_ids)))
        await db.commit()
        letters = letters[:HISTORY_LIMIT]
    return letters


async def get_outbox(db: AsyncSession, sender_id: int) -> list[Letter]:
    """发出记录：本人投出的已投递与未送达信件，按时间倒序。"""
    result = await db.execute(
        select(Letter)
        .where(
            Letter.sender_id == sender_id,
            Letter.status.in_(("delivered", "undelivered")),
        )
        .order_by(Letter.created_at.desc())
    )
    return list(result.scalars().all())


async def dismiss(
    db: AsyncSession, letter_id: int, user_id: int, clock: Clock
) -> Letter | None:
    """放弃一封未处理信：置 handled=True、不进历史；过期 409、重复幂等。"""
    letter = await db.scalar(
        select(Letter).where(
            Letter.id == letter_id,
            Letter.user_id == user_id,
            Letter.status == "delivered",
        )
    )
    if letter is None:
        return None
    if letter.expired_at <= clock.now():
        raise LetterExpired
    if letter.handled:
        return letter

    letter.handled = True
    letter.favorited = False
    await db.flush()  # 先把状态写进外层事务，savepoint 回滚只影响幂等键
    if letter.session_id is not None:
        try:
            async with db.begin_nested():
                db.add(
                    ActionLog(
                        session_id=letter.session_id,
                        action_type=f"dismiss:{letter.id}",
                    )
                )
                await db.flush()
        except IntegrityError:
            pass
    await db.commit()
    await db.refresh(letter)
    return letter


async def favorite(
    db: AsyncSession, letter_id: int, user_id: int, clock: Clock
) -> Letter | None:
    """收藏本人未处理信：置 favorited + handled，幂等且只写一条幂等键。"""
    letter = await db.scalar(
        select(Letter).where(
            Letter.id == letter_id,
            Letter.user_id == user_id,
            Letter.status == "delivered",
        )
    )
    if letter is None:
        return None
    if letter.expired_at <= clock.now():
        raise LetterExpired
    if letter.favorited:
        return letter
    if letter.handled:
        # 已放弃的信不能再收藏复活进历史（幂等重试走上面的 favorited 分支）
        raise LetterAlreadyHandled

    letter.favorited = True
    letter.handled = True
    await db.flush()  # 同 dismiss：状态在 savepoint 之外，冲突回滚不会丢状态
    if letter.session_id is not None:
        # action_type 带 letter_id，保证同一 session 的不同信件可各自收藏一次
        try:
            async with db.begin_nested():
                db.add(
                    ActionLog(
                        session_id=letter.session_id,
                        action_type=f"favorite:{letter.id}",
                    )
                )
                await db.flush()
        except IntegrityError:
            pass
    await db.commit()
    await db.refresh(letter)
    return letter


async def delete_favorited(db: AsyncSession, letter_id: int, user_id: int) -> bool:
    """删除本人历史信箱中的收藏信（物理删除）；不满足条件返回 False。"""
    letter = await db.scalar(
        select(Letter).where(
            Letter.id == letter_id,
            Letter.user_id == user_id,
            Letter.status == "delivered",
            Letter.favorited == True,  # noqa: E712
        )
    )
    if letter is None:
        return False
    await db.delete(letter)
    await db.commit()
    return True
