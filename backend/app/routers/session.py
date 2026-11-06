from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.db import get_session
from app.schemas.session import CurrentSession, SessionCreate, SessionCreated, SessionInfo
from app.services import session_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreated)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_session)
) -> SessionCreated:
    """开始专注：写入 active 会话。"""
    clock = Clock()
    session = await session_service.create_session(db, body.user_id, body.task_id, clock)
    return SessionCreated(
        session_id=session.id,
        started_at=session.started_at.isoformat(),
        server_time=clock.now().isoformat(),
    )


@router.get("/current", response_model=CurrentSession)
async def current_session(
    user_id: int, db: AsyncSession = Depends(get_session)
) -> CurrentSession:
    """查询当前会话，顺带做懒计算完成标记（5min 完成 / 180min 封顶）。"""
    clock = Clock()
    session, elapsed = await session_service.get_current_session(db, user_id, clock)
    info = (
        SessionInfo(
            id=session.id,
            started_at=session.started_at.isoformat(),
            elapsed_sec=elapsed,
            status=session.status,
        )
        if session
        else None
    )
    return CurrentSession(session=info, server_time=clock.now().isoformat())
