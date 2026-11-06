from datetime import datetime, time, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import SHANGHAI_TZ, Clock
from app.models import ActionLog, DayTask, Letter, Reflection, Session, User

# 按外键依赖倒序清表
_CLEAR_ORDER = [ActionLog, Letter, Reflection, Session, DayTask, User]

_DEMO_TOPICS = [
    "阅读《深入理解计算机系统》第三章",
    "整理本周英语单词 50 个",
    "看完线性代数第 4 讲视频",
    "写周报初稿",
    "复习操作系统进程调度一节",
]


async def reset_seed(session: AsyncSession) -> list[User]:
    """清库并插入演示数据：2 个用户 + A 用户近 5 天的任务/专注/反思样例。

    幂等：先全量 delete 再插入，重复调用结果计数一致。
    日期按「服务端当天 - n 天」动态生成，保证任何一天演示都是近 5 天。
    """
    for model in _CLEAR_ORDER:
        await session.execute(delete(model))

    today = Clock().today()
    user_a = User(name="演示用户A")
    user_b = User(name="演示用户B")
    session.add_all([user_a, user_b])
    await session.flush()  # 拿到自增 id

    for n in range(1, 6):
        day = today - timedelta(days=n)
        raw_text = _DEMO_TOPICS[n - 1]
        task = DayTask(
            user_id=user_a.id,
            date=day,
            raw_text=raw_text,
            starter_step="打开资料，只看第 1 段",
            steps=[f"{raw_text}：第 {i} 步" for i in range(1, 4)],
        )
        session.add(task)
        await session.flush()

        started_at = datetime.combine(day, time(20, 0), tzinfo=SHANGHAI_TZ)
        focus = Session(
            user_id=user_a.id,
            task_id=task.id,
            started_at=started_at,
            ended_at=started_at + timedelta(minutes=5),
            duration_sec=300,
            status="completed",
        )
        session.add(focus)
        await session.flush()

        session.add(
            Reflection(
                user_id=user_a.id,
                session_id=focus.id,
                content=f"第 {n} 天回顾：5 分钟启动比想象中容易。",
                date=day,
            )
        )

    await session.commit()
    return [user_a, user_b]
