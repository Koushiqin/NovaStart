from datetime import timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, SHANGHAI_TZ
from app.config import settings
from app.models.day_task import DayTask
from app.models.letter import Letter
from app.models.session import Session
from app.models.star import Star
from app.services import progress_service
from app.services.settle_service import SETTLEABLE_STATUSES

# 进行中会话：5 分钟里程碑会把 active 置为 completed，但计时仍在继续（ended_at 为空）
ONGOING_STATUSES = ("active", "completed")


class TaskNotFound(Exception):
    """任务不存在或不属于当前账号。"""


async def create_session(
    db: AsyncSession, user_id: int, task_id: int, clock: Clock
) -> Session:
    """开启一个专注会话（status=active）；只能挂到当前账号自己的任务上。

    已有进行中会话（active / completed 且未写 ended_at）时直接复用，避免重复点开始
    产生多条并行会话。
    """
    owned_task = await db.scalar(
        select(DayTask.id).where(DayTask.id == task_id, DayTask.user_id == user_id)
    )
    if owned_task is None:
        raise TaskNotFound

    ongoing = await db.scalar(
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.status.in_(ONGOING_STATUSES),
            Session.ended_at.is_(None),
        )
        .order_by(Session.started_at.desc(), Session.id.desc())
        .limit(1)
    )
    if ongoing is not None:
        return ongoing

    session = Session(user_id=user_id, task_id=task_id, started_at=clock.now(), status="active")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_current_session(
    db: AsyncSession, user_id: int, clock: Clock
) -> tuple[Session | None, int, str | None]:
    """取用户当前会话并做懒计算，返回 (session, elapsed_sec, task_starter_step)。

    懒计算规则（全部服务端按 started_at 求差，不使用客户端定时器）：
    - 达到最短时长 → status=completed，但不写 ended_at / duration_sec（计时继续）；
    - 达到最长时长 → status=completed，补写 ended_at = started_at + max 与 duration_sec。
    第二分支对「已达到 5 分钟但未结束」的 completed 会话同样生效，保证 180 自动结束。
    """
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.status.in_(["active", "completed"]))
        .order_by(Session.started_at.desc(), Session.id.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None, 0, None

    now = clock.now()
    elapsed = max(0, int((now - session.started_at).total_seconds()))
    day = session.started_at.astimezone(SHANGHAI_TZ).date()

    if session.ended_at is None and elapsed >= settings.session_max_seconds:
        session.status = "completed"
        session.ended_at = session.started_at + timedelta(seconds=settings.session_max_seconds)
        session.duration_sec = settings.session_max_seconds
        await progress_service.mark_day_completed(db, user_id, day)
        await progress_service.recompute_day(db, user_id, day)
        await db.commit()
    elif session.status == "active" and elapsed >= settings.session_min_seconds:
        session.status = "completed"
        # 满 5 分钟先记连续天数；星星等有效结束/封顶后按有效时长补算（同一事务）
        await progress_service.mark_day_completed(db, user_id, day)
        await progress_service.recompute_day(db, user_id, day)
        await db.commit()

    starter_step = await db.scalar(
        select(DayTask.starter_step).where(DayTask.id == session.task_id)
    )
    return session, elapsed, starter_step


async def end_session(
    db: AsyncSession, session_id: int, user_id: int, clock: Clock
) -> tuple[str, int | None] | None:
    """结束会话并判定有效性，返回 (result, value) 或 None（不存在/非本人）。

    - result="settled"：value = duration_sec；
    - result="discarded"：value = short_by_sec（还差多少秒达到最短时长）。
    重复调用幂等：已结束会话不再二次改写。
    """
    session = await db.scalar(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    if session is None:
        return None

    now = clock.now()
    elapsed = max(0, int((now - session.started_at).total_seconds()))
    min_seconds = settings.session_min_seconds

    if session.status == "discarded":
        # 无列存原始差额，重复调用按当前时刻重算（仅信息性提示）
        return "discarded", max(0, min_seconds - elapsed)

    if session.status == "settled" or session.ended_at is not None:
        return "settled", session.duration_sec

    if elapsed < min_seconds:
        # 无效场次完全丢弃：时长与结束时间都不写库，保留行只为幂等
        session.status = "discarded"
        session.ended_at = None
        session.duration_sec = None
        await db.commit()
        return "discarded", min_seconds - elapsed

    duration = min(elapsed, settings.session_max_seconds)
    session.status = "completed"
    session.duration_sec = duration
    session.ended_at = session.started_at + timedelta(seconds=duration)
    day = session.started_at.astimezone(SHANGHAI_TZ).date()
    await progress_service.mark_day_completed(db, user_id, day)
    await progress_service.recompute_day(db, user_id, day)
    await db.commit()
    return "settled", duration


async def get_settlement_summary(
    db: AsyncSession, session_id: int, user_id: int, clock: Clock
) -> tuple[Session, DayTask, int, int | None, tuple[int, int, bool] | None, int] | None:
    """结算页数据源：本场有效会话、任务文案、归属日累计时长、本场星星与连续天数。

    可访问条件：本人、已结束（ended_at 非空）、status ∈ {completed, settled}；
    其余情况返回 None（router 统一映射 404，不区分原因）。
    归属日按 started_at 的 Asia/Shanghai 日期，禁止裸 cast(started_at, Date)。
    star_level = 归属日 stars 等级（该日无星为 None）；
    streak = 当前账号读侧快照（无任何完成记录为 None）；
    received = 本场时间窗 [started_at, ended_at] 内本人收到的已投递信数。
    """
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(SETTLEABLE_STATUSES),
        )
    )
    if session is None:
        return None

    task = await db.scalar(select(DayTask).where(DayTask.id == session.task_id))
    if task is None:
        return None

    attribution_day = session.started_at.astimezone(SHANGHAI_TZ).date()
    today_total = await db.scalar(
        select(func.sum(Session.duration_sec)).where(
            Session.user_id == user_id,
            Session.status.in_(SETTLEABLE_STATUSES),
            Session.ended_at.is_not(None),
            cast(func.timezone("Asia/Shanghai", Session.started_at), Date) == attribution_day,
        )
    )
    star = await db.scalar(
        select(Star).where(Star.user_id == user_id, Star.date == attribution_day)
    )
    streak = await progress_service.streak_view(db, user_id, clock.today())
    received = await db.scalar(
        select(func.count())
        .select_from(Letter)
        .where(
            Letter.user_id == user_id,
            Letter.status == "delivered",
            Letter.created_at >= session.started_at,
            Letter.created_at <= session.ended_at,
        )
    )
    return (
        session,
        task,
        int(today_total or 0),
        star.level if star else None,
        streak,
        int(received or 0),
    )
