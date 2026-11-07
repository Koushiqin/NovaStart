from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.config import settings
from app.db import get_session
from app.deps import get_current_user_id
from app.llm import get_splitter
from app.models.day_task import DayTask
from app.schemas.task import TaskCreate, TaskCreated

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreated)
async def create_task(
    body: TaskCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> TaskCreated:
    """创建当天任务：调 splitter 拆步后落库，返回拆分结果与服务器时间。"""
    clock = Clock()
    split = await get_splitter(settings).split(body.raw_text, clock.today().isoformat())

    task = DayTask(
        user_id=user_id,
        date=clock.today(),
        raw_text=body.raw_text,
        starter_step=split.starter_step,
        steps=split.steps,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return TaskCreated(
        task_id=task.id,
        starter_step=split.starter_step,
        steps=split.steps,
        source=split.source,
        server_time=clock.now().isoformat(),
    )
