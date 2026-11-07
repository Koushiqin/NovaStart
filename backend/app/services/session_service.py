from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models.day_task import DayTask
from app.models.session import Session

# 最小专注时长：达到即视为完成（演示节奏，5 分钟）
SESSION_MIN_MINUTES = 5
# 硬上限：超过后补写 ended_at，避免忘记结束导致会话永远挂着
SESSION_MAX_MINUTES = 180


class TaskNotFound(Exception):
    """任务不存在或不属于当前账号。"""


async def create_session(
    db: AsyncSession, user_id: int, task_id: int, clock: Clock
) -> Session:
    """开启一个专注会话（status=active）；只能挂到当前账号自己的任务上。"""
    owned_task = await db.scalar(
        select(DayTask.id).where(DayTask.id == task_id, DayTask.user_id == user_id)
    )
    if owned_task is None:
        raise TaskNotFound

    session = Session(user_id=user_id, task_id=task_id, started_at=clock.now(), status="active")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_current_session(
    db: AsyncSession, user_id: int, clock: Clock
) -> tuple[Session | None, int]:
    """取用户当前会话（active 或待结算的 completed），并做懒计算完成标记。

    懒计算规则：active 且已进行 >= 5min → 置 completed；>= 180min → 置 completed
    并补写 ended_at（按 started_at + 180min 封顶）。返回 (session, elapsed_sec)。
    """
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.status.in_(["active", "completed"]))
        .order_by(Session.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None, 0

    now = clock.now()
    elapsed = max(0, int((now - session.started_at).total_seconds()))

    if session.status == "active":
        if elapsed >= SESSION_MAX_MINUTES * 60:
            session.status = "completed"
            session.ended_at = session.started_at + timedelta(minutes=SESSION_MAX_MINUTES)
            await db.commit()
        elif elapsed >= SESSION_MIN_MINUTES * 60:
            session.status = "completed"
            await db.commit()

    return session, elapsed
