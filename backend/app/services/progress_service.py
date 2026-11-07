from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models.session import Session
from app.models.star import Star
from app.models.streak import Streak
from app.services.settle_service import SETTLEABLE_STATUSES

# 归属日 = 会话开始时刻的 Asia/Shanghai 自然日（禁止裸 cast(started_at, Date)）
ATTRIBUTION_DAY = cast(func.timezone("Asia/Shanghai", Session.started_at), Date)

# 亮级阈值（当天有效累计秒）：<5 分钟 → 0（不建行）；<15 分钟 Lv1；<25 分钟 Lv2；其余 Lv3
LEVEL_1_SECONDS = 300
LEVEL_2_SECONDS = 900
LEVEL_3_SECONDS = 1500

WALL_DAYS = 30


def level_for_seconds(seconds: int) -> int:
    if seconds < LEVEL_1_SECONDS:
        return 0
    if seconds < LEVEL_2_SECONDS:
        return 1
    if seconds < LEVEL_3_SECONDS:
        return 2
    return 3


async def _valid_seconds(db: AsyncSession, user_id: int, day: date) -> int:
    """当天归属日的有效累计秒数：discarded 与进行中场次一律排除。"""
    total = await db.scalar(
        select(func.sum(Session.duration_sec)).where(
            Session.user_id == user_id,
            Session.status.in_(SETTLEABLE_STATUSES),
            Session.ended_at.is_not(None),
            ATTRIBUTION_DAY == day,
        )
    )
    return int(total or 0)


async def recompute_day(db: AsyncSession, user_id: int, day: date) -> Star | None:
    """从有效会话重算某归属日的星星（幂等，只 flush 不 commit）。

    有效秒数 <5 分钟且无既有行时不建行（返回 None）；亮级只升不降。
    """
    seconds = await _valid_seconds(db, user_id, day)
    level = level_for_seconds(seconds)
    star = await db.scalar(select(Star).where(Star.user_id == user_id, Star.date == day))

    if star is None:
        if level == 0:
            return None
        star = Star(user_id=user_id, date=day, minutes=seconds // 60, level=level)
        try:
            # 并发首次建行：唯一约束冲突时回滚本 savepoint，转更新既有行
            async with db.begin_nested():
                db.add(star)
                await db.flush()
            return star
        except IntegrityError:
            star = await db.scalar(select(Star).where(Star.user_id == user_id, Star.date == day))
            if star is None:
                raise RuntimeError("stars 行在唯一键冲突后消失")

    star.minutes = seconds // 60
    star.level = max(star.level, level)

    await db.flush()
    return star


async def mark_day_completed(db: AsyncSession, user_id: int, day: date) -> Streak:
    """标记某归属日完成并维护连续天数（幂等，只 flush 不 commit）。"""
    streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))
    existed = streak is not None
    if streak is None:
        streak = Streak(user_id=user_id, current=0, longest=0, was_reset=False)
        try:
            # 并发首次建行：主键冲突时回滚本 savepoint，转更新既有行
            async with db.begin_nested():
                db.add(streak)
                await db.flush()
        except IntegrityError:
            streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))
            if streak is None:
                raise RuntimeError("streaks 行在唯一键冲突后消失")
            # 回退说明该行由并发事务创建：账号此前已完成过某天
            existed = True

    if streak.last_completed_date == day:
        # 同一自然日只 +1：重复触发不改任何值
        await db.flush()
        return streak

    if streak.last_completed_date == day - timedelta(days=1):
        streak.current += 1
        streak.longest = max(streak.longest, streak.current)
        streak.was_reset = False
    else:
        streak.current = 1
        # 行曾存在（之前完成过）才算断签重开；全新账号首次完成为 False
        streak.was_reset = existed
        streak.longest = max(streak.longest, 1)

    streak.last_completed_date = day
    await db.flush()
    return streak


async def streak_view(
    db: AsyncSession, user_id: int, today: date
) -> tuple[int, int, bool] | None:
    """读侧连续天数快照：断签归零只体现在返回值，不写库。无记录返回 None。"""
    streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))
    if streak is None:
        return None
    if streak.last_completed_date not in (today, today - timedelta(days=1)):
        return 0, streak.longest, streak.was_reset
    return streak.current, streak.longest, streak.was_reset


async def attribution_days(db: AsyncSession, user_id: int) -> list[date]:
    """该账号所有有效场次的归属日（升序、去重），供种子按日期回放写入路径。"""
    rows = await db.scalars(
        select(ATTRIBUTION_DAY)
        .where(
            Session.user_id == user_id,
            Session.status.in_(SETTLEABLE_STATUSES),
            Session.ended_at.is_not(None),
        )
        .distinct()
    )
    return sorted(rows.all())


@dataclass(frozen=True)
class WallCell:
    date: date
    state: str
    level: int | None


@dataclass(frozen=True)
class ProgressSnapshot:
    today_minutes: int
    today_level: int
    streak_current: int
    streak_longest: int
    streak_was_reset: bool
    wall: list[WallCell]


async def progress_snapshot(
    db: AsyncSession, user_id: int, clock: Clock
) -> ProgressSnapshot:
    """首页进度快照：今天数值、连续天数、最近 30 天星星墙（只读，不写库）。"""
    today = clock.today()
    window_start = today - timedelta(days=WALL_DAYS - 1)
    stars = {
        star.date: star
        for star in (
            await db.scalars(
                select(Star).where(Star.user_id == user_id, Star.date >= window_start)
            )
        ).all()
    }
    first_star = await db.scalar(select(func.min(Star.date)).where(Star.user_id == user_id))

    wall: list[WallCell] = []
    for offset in range(WALL_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        star = stars.get(day)
        if star is not None:
            wall.append(WallCell(date=day, state="lit", level=star.level))
        elif day == today:
            wall.append(WallCell(date=day, state="dim", level=None))
        elif first_star is None or day < first_star:
            wall.append(WallCell(date=day, state="empty", level=None))
        else:
            wall.append(WallCell(date=day, state="broken", level=None))

    view = await streak_view(db, user_id, today)
    current, longest, was_reset = view if view is not None else (0, 0, False)
    today_star = stars.get(today)

    return ProgressSnapshot(
        today_minutes=today_star.minutes if today_star else 0,
        today_level=today_star.level if today_star else 0,
        streak_current=current,
        streak_longest=longest,
        streak_was_reset=was_reset,
        wall=wall,
    )
