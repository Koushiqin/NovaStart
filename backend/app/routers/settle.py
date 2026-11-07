from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.db import get_session
from app.deps import get_current_user_id
from app.schemas.settle import SettleAdvance, SettleState
from app.services import settle_service

router = APIRouter(prefix="/api/settle", tags=["settle"])


@router.post("/{session_id}/advance", response_model=SettleState)
async def advance(
    session_id: int,
    body: SettleAdvance,
    _user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> SettleState:
    """推进结算步骤（1..4），带条件更新天然幂等，只进不退。"""
    step = await settle_service.advance(db, session_id, body.to_step)
    if step is None:
        raise HTTPException(status_code=404, detail="session not found")
    return SettleState(
        session_id=session_id,
        settle_step=step,
        server_time=Clock().now().isoformat(),
    )
