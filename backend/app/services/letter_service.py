from datetime import datetime, time, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import SHANGHAI_TZ, Clock
from app.models.action_log import ActionLog
from app.models.letter import Letter

# 未处理信箱上限：超过即丢弃新信，不投递
INBOX_MAX_UNHANDLED = 3
# 历史信件上限：超出部分在读取时懒清理
HISTORY_LIMIT = 100


async def deliver(
    db: AsyncSession, user_id: int, session_id: int, content: str, clock: Clock
) -> Letter | None:
    """投递一封信。同一 session 只投一次（ActionLog 唯一约束）；
    用户未处理信件 >= 3 封时丢弃不投。返回 Letter 或 None（未投递）。"""
    # 幂等门：先占 (session_id, "deliver") 这个幂等键，占不到说明已投过
    try:
        async with db.begin_nested():
            db.add(ActionLog(session_id=session_id, action_type="deliver"))
            await db.flush()
    except IntegrityError:
        return None

    # 行锁锁住该用户全部未处理信件，并发投递时串行化计数
    result = await db.execute(
        select(Letter)
        .where(Letter.user_id == user_id, Letter.handled == False)  # noqa: E712
        .with_for_update()
    )
    if len(result.scalars().all()) >= INBOX_MAX_UNHANDLED:
        await db.commit()  # ActionLog 已写，本 session 不再重投
        return None

    # expired_at = 当日 24:00（即次日 0 点，Asia/Shanghai）
    tomorrow = clock.today() + timedelta(days=1)
    letter = Letter(
        user_id=user_id,
        session_id=session_id,
        content=content,
        expired_at=datetime.combine(tomorrow, time.min, tzinfo=SHANGHAI_TZ),
    )
    db.add(letter)
    await db.commit()
    await db.refresh(letter)
    return letter


async def get_inbox(db: AsyncSession, user_id: int, clock: Clock) -> list[Letter]:
    """未处理且未过期的信件（懒失效：过期判断在查询条件里，不后台清扫）。"""
    result = await db.execute(
        select(Letter)
        .where(
            Letter.user_id == user_id,
            Letter.handled == False,  # noqa: E712
            Letter.expired_at > clock.now(),
        )
        .order_by(Letter.created_at.desc())
    )
    return list(result.scalars().all())


async def get_history(db: AsyncSession, user_id: int) -> list[Letter]:
    """历史（已处理/已收藏）信件。返回前懒清理：超过 100 条则删最旧的。"""
    result = await db.execute(
        select(Letter)
        .where(
            Letter.user_id == user_id,
            or_(Letter.handled == True, Letter.favorited == True),  # noqa: E712
        )
        .order_by(Letter.created_at.desc())
    )
    letters = list(result.scalars().all())
    if len(letters) > HISTORY_LIMIT:
        stale_ids = [l.id for l in letters[HISTORY_LIMIT:]]
        await db.execute(delete(Letter).where(Letter.id.in_(stale_ids)))
        await db.commit()
        letters = letters[:HISTORY_LIMIT]
    return letters


async def favorite(db: AsyncSession, letter_id: int) -> Letter | None:
    """收藏信件，幂等：已收藏直接返回原状态，不重复写 ActionLog。"""
    letter = await db.get(Letter, letter_id)
    if letter is None:
        return None
    if letter.favorited:
        return letter
    letter.favorited = True
    if letter.session_id is not None:
        # action_type 带 letter_id，保证同一 session 的不同信件可各自收藏一次
        db.add(ActionLog(session_id=letter.session_id, action_type=f"favorite:{letter.id}"))
    await db.commit()
    await db.refresh(letter)
    return letter
