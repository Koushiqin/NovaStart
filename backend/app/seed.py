from datetime import datetime, time, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import SHANGHAI_TZ, Clock
from app.models import ActionLog, DayTask, Letter, Reflection, Session, User

# 按外键依赖倒序清表
_CLEAR_ORDER = [ActionLog, Letter, Reflection, Session, DayTask, User]

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


async def reset_seed(session: AsyncSession) -> list[User]:
    """清库并插入演示数据：3 个固定演示账号。

    小明 = 连续 6 天历史；小美 = 1 条历史；小刚 = 空（用于演示全新账号）。
    幂等：先全量 delete 再插入，重复调用结果计数一致。
    日期按「服务端当天 - n 天」动态生成，保证任何一天演示都是近 6 天。
    信件预置属 P6，本计划不写入信件。
    """
    for model in _CLEAR_ORDER:
        await session.execute(delete(model))

    today = Clock().today()
    xiaoming = User(name="小明")
    xiaomei = User(name="小美")
    xiaogang = User(name="小刚")
    session.add_all([xiaoming, xiaomei, xiaogang])
    await session.flush()  # 拿到自增 id

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
        "小美的历史回顾：从一个小目标开始。",
    )

    await session.commit()
    return [xiaoming, xiaomei, xiaogang]
