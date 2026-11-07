from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session

_SETTLEABLE_STATUSES = ("completed", "settled")


async def advance(db: AsyncSession, session_id: int, to_step: int, user_id: int) -> int | None:
    """推进结算步骤。带条件更新天然幂等：重复或回退请求不会命中任何行。

    仅本人、已结束（ended_at 非空）的有效会话可推进；第 ④ 步同事务置 settled。
    返回最新 settle_step；不可推进或不属于该用户时返回 None。
    """
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(_SETTLEABLE_STATUSES),
        )
    )
    if session is None:
        return None

    values: dict[str, int | str] = {"settle_step": to_step}
    if to_step >= 4:
        values["status"] = "settled"
    await db.execute(
        update(Session)
        .where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(_SETTLEABLE_STATUSES),
            Session.settle_step < to_step,
        )
        .values(**values)
    )
    await db.commit()
    await db.refresh(session)
    return session.settle_step
