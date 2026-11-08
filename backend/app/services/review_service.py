import hashlib

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models.day_task import DayTask
from app.models.reflection import Reflection
from app.models.session import Session
from app.services.settle_service import SETTLEABLE_STATUSES

# 归属日口径：started_at 的 Asia/Shanghai 自然日（与 P3/P4/P5 一致）
_attribution_date = cast(func.timezone("Asia/Shanghai", Session.started_at), Date)


async def random_past(
    db: AsyncSession, user_id: int, exclude_session_id: int, clock: Clock
) -> tuple[Session, str, str, str | None] | None:
    """随机抽一条本人过去有效场次，返回 (会话, 归属日 ISO, 任务原文, 感想或 None)。

    候选池：本人、completed/settled、已结束（ended_at 非空）、归属日早于今天，
    并排除本场；随机一条，不保证不重复。池空返回 None。
    """
    stmt = (
        select(Session, DayTask.raw_text, Reflection.content, _attribution_date)
        .join(DayTask, DayTask.id == Session.task_id)
        .outerjoin(Reflection, Reflection.session_id == Session.id)
        .where(
            Session.user_id == user_id,
            Session.status.in_(SETTLEABLE_STATUSES),
            Session.ended_at.is_not(None),
            _attribution_date < clock.today(),
            Session.id != exclude_session_id,
        )
        .order_by(func.random())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None

    session, task_text, reflection, day = row
    return session, day.isoformat(), task_text, reflection


async def daily_past(
    db: AsyncSession, user_id: int, clock: Clock
) -> tuple[Session, str, str, str | None] | None:
    """按 (user_id, 当日归属日) 确定性选取一条过去有效场次。

    同一天对同一用户重复调用始终返回同一条；跨日可变。
    候选池：本人、completed/settled、已结束、归属日早于今天。
    选取方式：候选按 session.id 升序排列，idx = stable_hash(user_id, date) % count。
    池空返回 None。
    """
    stmt = (
        select(Session, DayTask.raw_text, Reflection.content, _attribution_date)
        .join(DayTask, DayTask.id == Session.task_id)
        .outerjoin(Reflection, Reflection.session_id == Session.id)
        .where(
            Session.user_id == user_id,
            Session.status.in_(SETTLEABLE_STATUSES),
            Session.ended_at.is_not(None),
            _attribution_date < clock.today(),
        )
        .order_by(Session.id.asc())
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    # 同日确定性：用 user_id + 当天日期做稳定哈希取模
    today_str = clock.today().isoformat()
    seed = f"{user_id}:{today_str}"
    idx = _stable_mod(seed, len(rows))
    session, task_text, reflection, day = rows[idx]
    return session, day.isoformat(), task_text, reflection


def _stable_mod(seed: str, modulus: int) -> int:
    """对字符串做稳定哈希并对 modulus 取模，结果在 [0, modulus)。"""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return value % modulus
