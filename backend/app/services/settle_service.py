from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session


async def advance(db: AsyncSession, session_id: int, to_step: int) -> int | None:
    """推进结算步骤。带条件更新天然幂等：重复或回退请求不会命中任何行。

    返回最新 settle_step；session 不存在返回 None。
    """
    await db.execute(
        update(Session)
        .where(
            Session.id == session_id,
            Session.status == "completed",
            Session.settle_step < to_step,
        )
        .values(settle_step=to_step)
    )
    await db.commit()
    session = await db.get(Session, session_id)
    return session.settle_step if session else None
