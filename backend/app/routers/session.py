from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.config import settings
from app.db import get_session
from app.deps import get_current_user_id
from app.schemas.progress import StreakInfo
from app.schemas.session import (
    CurrentSession,
    ReflectionContent,
    ReflectionCreate,
    ReflectionSaved,
    SessionCreate,
    SessionCreated,
    SessionEnded,
    SessionInfo,
    SessionSummary,
)
from app.services import reflection_service, session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreated)
async def create_session(
    body: SessionCreate,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> SessionCreated:
    """开始专注：写入 active 会话；任务必须属于当前账号。"""
    try:
        session = await session_service.create_session(db, user_id, body.task_id, clock)
    except session_service.TaskNotFound:
        raise HTTPException(
            status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"}
        )
    return SessionCreated(
        session_id=session.id,
        started_at=session.started_at.isoformat(),
        server_time=clock.now().isoformat(),
    )


@router.post("/{session_id}/end", response_model=SessionEnded)
async def end_session(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> SessionEnded:
    """结束专注并判定有效性：唯一结束路径，规则在 service 内闭合。"""
    outcome = await session_service.end_session(db, session_id, user_id, clock)
    if outcome is None:
        raise HTTPException(
            status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "会话不存在"}
        )
    result, value = outcome
    if result == "settled":
        return SessionEnded(
            result="settled",
            duration_sec=value,
            short_by_sec=None,
            server_time=clock.now().isoformat(),
        )
    return SessionEnded(
        result="discarded",
        duration_sec=None,
        short_by_sec=value,
        server_time=clock.now().isoformat(),
    )


@router.get("/current", response_model=CurrentSession)
async def current_session(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> CurrentSession:
    """查询当前会话，顺带做懒计算完成标记（5min 完成 / 180min 封顶）。"""
    session, elapsed, starter_step = await session_service.get_current_session(db, user_id, clock)
    info = (
        SessionInfo(
            id=session.id,
            started_at=session.started_at.isoformat(),
            elapsed_sec=elapsed,
            status=session.status,
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            task_starter_step=starter_step,
        )
        if session
        else None
    )
    return CurrentSession(
        session=info,
        server_time=clock.now().isoformat(),
        session_max_seconds=settings.session_max_seconds,
    )


@router.get("/{session_id}/summary", response_model=SessionSummary)
async def session_summary(
    session_id: int,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> SessionSummary:
    """结算页数据源：本次时长、归属日累计、starter 原话复述与星星/连续天数。"""
    summary = await session_service.get_settlement_summary(db, session_id, user_id, clock)
    if summary is None:
        raise HTTPException(
            status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "会话不存在"}
        )
    session, task, today_total_sec, star_level, streak, received = summary
    return SessionSummary(
        duration_sec=session.duration_sec,
        today_total_sec=today_total_sec,
        task_text=task.raw_text,
        starter_text=task.starter_step,
        settle_step=session.settle_step,
        status=session.status,
        received_during_session=received,
        star_level=star_level,
        streak=StreakInfo(current=streak[0], longest=streak[1], was_reset=streak[2])
        if streak
        else None,
        server_time=clock.now().isoformat(),
    )


@router.post("/{session_id}/reflection", response_model=ReflectionSaved, status_code=201)
async def save_reflection(
    session_id: int,
    body: ReflectionCreate,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> ReflectionSaved:
    """第①步感想：一次性写入；空白 = 跳过不落库，二者都推进 settle_step 到 1。"""
    try:
        reflection = await reflection_service.save(
            db, session_id, user_id, body.content, clock
        )
    except reflection_service.SessionNotFound:
        raise HTTPException(
            status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "会话不存在"}
        )
    except reflection_service.ReflectionLocked:
        raise HTTPException(
            status_code=409,
            detail={"code": "REFLECTION_LOCKED", "message": "感想已提交或已跳过"},
        )
    return ReflectionSaved(
        reflection=ReflectionContent(content=reflection.content) if reflection else None,
        settle_step=1,
        server_time=clock.now().isoformat(),
    )
