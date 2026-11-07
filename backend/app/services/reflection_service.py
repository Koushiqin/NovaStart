from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, SHANGHAI_TZ
from app.models.reflection import Reflection
from app.models.session import Session
from app.services import settle_service


class SessionNotFound(Exception):
    """会话不存在、非本人、discarded 或未结束。"""


class ReflectionLocked(Exception):
    """感想已提交或已跳过：只允许第①步写一次。"""


async def save(
    db: AsyncSession, session_id: int, user_id: int, content: str, clock: Clock
) -> Reflection | None:
    """写入感想并推进 settle_step 0→1；空白内容 = 跳过（不落库）。

    - 可写条件与结算页一致：本人、已结束、status ∈ {completed, settled}；
    - settle_step >= 1 或已有记录 → ReflectionLocked，感想只读（A19）；
    - 写入与 advance 同一 commit：先 add 再 advance，不新增第二写入路径；
    - `date` 取会话 started_at 的 Asia/Shanghai 日期（跨零点仍记开始日）；
      `clock` 保留为服务签名统一的时间入口，归属日不取写入时间。
    """
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(settle_service.SETTLEABLE_STATUSES),
        )
    )
    if session is None:
        raise SessionNotFound

    existing = await db.scalar(
        select(Reflection.id).where(Reflection.session_id == session_id)
    )
    if session.settle_step >= 1 or existing is not None:
        raise ReflectionLocked

    text = content.strip()
    reflection = None
    if text:
        reflection = Reflection(
            user_id=user_id,
            session_id=session_id,
            content=text,
            date=session.started_at.astimezone(SHANGHAI_TZ).date(),
        )
        db.add(reflection)

    step = await settle_service.advance(db, session_id, 1, user_id)
    if step is None:
        await db.rollback()
        raise SessionNotFound
    return reflection
