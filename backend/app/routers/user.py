from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.schemas.user import UserOut, UsersResponse
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UsersResponse)
async def list_users(
    db: AsyncSession = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> UsersResponse:
    """演示账号列表（无需请求头），供前端账号切换使用。"""
    users = await user_service.list_users(db)
    return UsersResponse(
        users=[UserOut.model_validate(u) for u in users],
        server_time=clock.now().isoformat(),
    )
