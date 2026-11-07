from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.deps import get_current_user_id, get_task_splitter
from app.llm import TaskSplitter
from app.schemas.task import (
    AnalyzeResult,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TodayResponse,
)
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_TASK_NOT_FOUND = {"code": "TASK_NOT_FOUND", "message": "任务不存在"}
_TASK_LOCKED = {"code": "TASK_LOCKED", "message": "开始计时后不能再修改任务"}


@router.post("", response_model=TaskResponse)
async def create_task(
    body: TaskCreate,
    response: Response,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """建今日草稿：不调 splitter；同日重复请求返回既有任务。"""
    task, created = await task_service.create_draft(db, user_id, body.raw_text, clock)
    if created:
        response.status_code = 201
    return TaskResponse(task=task, server_time=clock.now().isoformat())


@router.get("/today", response_model=TodayResponse)
async def get_today(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> TodayResponse:
    """首页唯一数据源：今日任务 + 昨日未完任务提示。"""
    task, carry_over = await task_service.get_today(db, user_id, clock)
    return TodayResponse(task=task, carry_over=carry_over, server_time=clock.now().isoformat())


@router.post("/{task_id}/analyze", response_model=AnalyzeResult)
async def analyze_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
    splitter: TaskSplitter = Depends(get_task_splitter),
) -> AnalyzeResult:
    """点「分析」才调用 splitter，双版本落库；同标题复用已存结果。"""
    try:
        result = await task_service.analyze(db, user_id, task_id, splitter, clock)
    except task_service.TaskNotFound:
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
    except task_service.TaskLocked:
        raise HTTPException(status_code=409, detail=_TASK_LOCKED)
    return AnalyzeResult(
        starter_step=result.starter_step,
        steps=result.steps,
        source=result.source,
        server_time=clock.now().isoformat(),
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """只更新当前采用版；计时开始后锁定 409。"""
    fields = body.model_dump(exclude_unset=True)
    try:
        task = await task_service.update_task(
            db,
            user_id,
            task_id,
            raw_text=fields.get("raw_text"),
            starter_step=fields.get("starter_step"),
            steps=fields.get("steps"),
        )
    except task_service.TaskNotFound:
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
    except task_service.TaskLocked:
        raise HTTPException(status_code=409, detail=_TASK_LOCKED)
    return TaskResponse(task=task, server_time=clock.now().isoformat())
