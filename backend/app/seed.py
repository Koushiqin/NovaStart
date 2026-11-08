from datetime import datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import SHANGHAI_TZ, Clock
from app.models import (
    ActionLog,
    AuthSession,
    DayTask,
    Letter,
    Reflection,
    Session,
    Star,
    Streak,
    User,
)
from app.services import progress_service

# 按外键依赖倒序清表；users 单独处理：三个固定演示账号保留原 id，
# 因为前端把 userId 持久化在 localStorage，id 漂移会让刷新后的选中账号失效。
_CLEAR_ORDER = [ActionLog, AuthSession, Letter, Reflection, Session, Star, Streak, DayTask]

# 三个固定演示账号（name, username）
_DEMO_ACCOUNTS = (
    ("小明", "xiaoming"),
    ("小美", "xiaomei"),
    ("小刚", "xiaogang"),
)

# 小美昨日感想：既写入反思，也作为预置信件的正文
_XIAOMEI_REFLECTION = "小美的历史回顾：从一个小目标开始。"

# 小明 6 天历史用到的任务主题
_DEMO_TOPICS = [
    "阅读《深入理解计算机系统》第三章",
    "整理本周英语单词 50 个",
    "看完线性代数第 4 讲视频",
    "写周报初稿",
    "复习操作系统进程调度一节",
    "整理本周读书笔记",
]


async def _add_day_history(
    db: AsyncSession, user: User, day, raw_text: str, reflection_text: str
) -> None:
    """写入某账号某天的一条完整历史：任务 + 5 分钟完成的专注 + 反思。"""
    task = DayTask(
        user_id=user.id,
        date=day,
        raw_text=raw_text,
        starter_step="打开资料，只看第 1 段",
        steps=[f"{raw_text}：第 {i} 步" for i in range(1, 4)],
    )
    db.add(task)
    await db.flush()

    started_at = datetime.combine(day, time(20, 0), tzinfo=SHANGHAI_TZ)
    focus = Session(
        user_id=user.id,
        task_id=task.id,
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=5),
        duration_sec=300,
        status="completed",
    )
    db.add(focus)
    await db.flush()

    db.add(
        Reflection(
            user_id=user.id,
            session_id=focus.id,
            content=reflection_text,
            date=day,
        )
    )


async def reset_seed(session: AsyncSession, clock: Clock) -> list[User]:
    """清库并插入演示数据：3 个固定演示账号。

    小明 = 连续 6 天历史；小美 = 1 条历史；小刚 = 空（用于演示全新账号）。
    幂等：清空业务数据后按名字复用既有演示账号（id 不漂移），缺失才新建；
    重复调用结果计数一致。日期按「服务端当天 - n 天」动态生成，保证任何一天演示都是近 6 天。
    小明未处理信箱预置小美 2 封（P6 验收 18），不走投递机会，直接落库。
    """
    for model in _CLEAR_ORDER:
        await session.execute(delete(model))

    # 非演示账号一律删除；已有演示账号复用（重复 reset 不改变 id）
    demo_names = [name for name, _ in _DEMO_ACCOUNTS]
    await session.execute(delete(User).where(User.name.not_in(demo_names)))
    existing = {u.name: u for u in (await session.execute(select(User))).scalars()}
    users: list[User] = []
    for name, username in _DEMO_ACCOUNTS:
        user = existing.get(name)
        if user is None:
            user = User(name=name, username=username)
            session.add(user)
        else:
            # 已存在账号补齐 username（历史数据迁移场景）
            if user.username != username:
                user.username = username
        users.append(user)
    await session.flush()  # 新建账号拿到自增 id

    today = clock.today()
    xiaoming, xiaomei, xiaogang = users

    for n in range(1, 7):
        day = today - timedelta(days=n)
        await _add_day_history(
            session,
            xiaoming,
            day,
            _DEMO_TOPICS[n - 1],
            f"第 {n} 天回顾：5 分钟启动比想象中容易。",
        )

    await _add_day_history(
        session,
        xiaomei,
        today - timedelta(days=1),
        "整理英语单词 20 个",
        _XIAOMEI_REFLECTION,
    )

    # 小明未处理信箱预置小美 2 封（正文取小美昨日感想），不走投递机会
    expires_at = datetime.combine(today + timedelta(days=1), time.min, tzinfo=SHANGHAI_TZ)
    created_at = clock.now() - timedelta(hours=1)
    for _ in range(2):
        session.add(
            Letter(
                user_id=xiaoming.id,
                sender_id=xiaomei.id,
                session_id=None,
                content=_XIAOMEI_REFLECTION,
                status="delivered",
                focused_delivery=False,
                favorited=False,
                handled=False,
                expired_at=expires_at,
                created_at=created_at,
            )
        )

    # 星星与连续天数走与线上相同的 recompute 写入路径（逐日升序），不手写 star/streak 行
    await session.flush()
    for user in users:
        for day in await progress_service.attribution_days(session, user.id):
            await progress_service.recompute_day(session, user.id, day)
            await progress_service.mark_day_completed(session, user.id, day)

    await session.commit()
    return [xiaoming, xiaomei, xiaogang]
