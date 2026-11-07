"""F1+F2 今日任务业务规则：当天唯一、草稿 → 分析双版本、计时后锁定、昨日提示。

事务边界在本模块内闭合；router 只做解析与转发。
"""

from datetime import date, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter
from app.models.day_task import DayTask
from app.models.session import Session
from app.schemas.task import CarryOver, TaskState

# starter 最多 60 字，超出视为模型输出不合规，走模板降级
MAX_STARTER_CHARS = 60
# 后续步骤最多 3 条（brainstorming F2）
MAX_STEPS = 3
# 视为「昨天已走完」的会话状态；active / discarded 都算没走完
_DONE_STATUSES = ("completed", "settled")


class TaskNotFound(Exception):
    """任务不存在或不属于当前账号。"""


class TaskLocked(Exception):
    """任务已有会话，文案已锁定。"""


def _task_state(task: DayTask, *, locked: bool) -> TaskState:
    """把 ORM 行转换为响应状态；analyzed / split_stale 由 analyzed_text 派生。"""
    analyzed = task.analyzed_text is not None
    return TaskState(
        id=task.id,
        raw_text=task.raw_text,
        starter_step=task.starter_step,
        steps=list(task.steps or []),
        origin_starter_step=task.origin_starter_step,
        origin_steps=None if task.origin_steps is None else list(task.origin_steps),
        analyzed=analyzed,
        split_stale=analyzed and task.analyzed_text != task.raw_text,
        locked=locked,
        source=task.split_source,
    )


async def _get_task(db: AsyncSession, user_id: int, day: date) -> DayTask | None:
    return await db.scalar(
        select(DayTask).where(DayTask.user_id == user_id, DayTask.date == day)
    )


async def _get_owned_task(db: AsyncSession, user_id: int, task_id: int) -> DayTask:
    task = await db.scalar(
        select(DayTask).where(DayTask.id == task_id, DayTask.user_id == user_id)
    )
    if task is None:
        raise TaskNotFound
    return task


async def _has_any_session(db: AsyncSession, task_id: int) -> bool:
    """存在该任务的有效会话即锁定（active / completed / settled）；discarded 完全丢弃不锁定。"""
    return bool(
        await db.scalar(
            select(exists().where(Session.task_id == task_id, Session.status != "discarded"))
        )
    )


async def _has_done_session(db: AsyncSession, task_id: int) -> bool:
    return bool(
        await db.scalar(
            select(exists().where(Session.task_id == task_id, Session.status.in_(_DONE_STATUSES)))
        )
    )


async def get_today(
    db: AsyncSession, user_id: int, clock: Clock
) -> tuple[TaskState | None, CarryOver | None]:
    """首页唯一数据源：今日任务 + （今日无任务时）昨日未完任务提示。"""
    today = clock.today()
    task = await _get_task(db, user_id, today)
    if task is not None:
        return _task_state(task, locked=await _has_any_session(db, task.id)), None

    previous = await _get_task(db, user_id, today - timedelta(days=1))
    if previous is None or await _has_done_session(db, previous.id):
        return None, None
    return None, CarryOver(raw_text=previous.raw_text, date=previous.date)


async def create_draft(
    db: AsyncSession, user_id: int, raw_text: str, clock: Clock
) -> tuple[TaskState, bool]:
    """当天首次输入建草稿；同日重复请求返回既有任务（created=False）。"""
    existing = await _get_task(db, user_id, clock.today())
    if existing is not None:
        return (
            _task_state(existing, locked=await _has_any_session(db, existing.id)),
            False,
        )

    task = DayTask(
        user_id=user_id,
        date=clock.today(),
        raw_text=raw_text,
        starter_step="",
        steps=[],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_state(task, locked=False), True


def _normalize_split(result: SplitResult) -> SplitResult | None:
    """二次校验：starter 非空且 ≤60 字、steps 每项非空并截断到 3 条；不合规返回 None。"""
    starter = result.starter_step.strip()
    steps = [step.strip() for step in result.steps][:MAX_STEPS]
    if not starter or len(starter) > MAX_STARTER_CHARS or not all(steps):
        return None
    return SplitResult(starter_step=starter, steps=steps, source=result.source)


async def _fallback_split(task_text: str, day: date) -> SplitResult:
    mock = await MockSplitter().split(task_text, day.isoformat())
    return SplitResult(
        starter_step=mock.starter_step.strip(),
        steps=[step.strip() for step in mock.steps][:MAX_STEPS],
        source="fallback",
    )


async def analyze(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    splitter: TaskSplitter,
    clock: Clock,
) -> SplitResult:
    """分析任务：同标题复用已存采用版，否则调 splitter 并双版本落库。"""
    task = await _get_owned_task(db, user_id, task_id)
    if await _has_any_session(db, task_id):
        raise TaskLocked

    # 同标题重复点「分析」：复用已存采用版，不调模型、不覆盖学生编辑
    if task.analyzed_text is not None and task.analyzed_text == task.raw_text:
        return SplitResult(
            starter_step=task.starter_step,
            steps=list(task.steps or []),
            source=task.split_source or "fallback",
        )

    try:
        normalized = _normalize_split(
            await splitter.split(task.raw_text, task.date.isoformat())
        )
    except Exception:
        normalized = None

    result = normalized or await _fallback_split(task.raw_text, task.date)

    task.origin_starter_step = task.starter_step = result.starter_step
    task.origin_steps = task.steps = list(result.steps)
    task.split_source = result.source
    task.analyzed_text = task.raw_text
    await db.commit()
    await db.refresh(task)
    return result


async def update_task(
    db: AsyncSession,
    user_id: int,
    task_id: int,
    *,
    raw_text: str | None = None,
    starter_step: str | None = None,
    steps: list[str] | None = None,
) -> TaskState:
    """只改当前采用版；origin / analyzed_text 不动，改标题不触发重新分析。"""
    task = await _get_owned_task(db, user_id, task_id)
    if await _has_any_session(db, task_id):
        raise TaskLocked

    if raw_text is not None:
        task.raw_text = raw_text
    if starter_step is not None:
        task.starter_step = starter_step
    if steps is not None:
        task.steps = steps

    await db.commit()
    await db.refresh(task)
    return _task_state(task, locked=False)
