from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.config import settings
from app.db import get_session
from app.llm import TaskSplitter, get_splitter
from app.services import auth_service


async def get_current_user_id(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> int:
    """当前用户单点解析：从 Authorization: Bearer <token> 解析登录会话。

    缺失 / 格式错误 → 401；token 无效或过期 → 401。
    不再信任客户端传入的 user_id，user_id 一律由服务端 sessions 表解析。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "未登录或登录已过期"},
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "未登录或登录已过期"},
        )
    user_id = await auth_service.get_session_user_id(db, token, clock)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "未登录或登录已过期"},
        )
    return user_id


def get_task_splitter() -> TaskSplitter:
    """任务拆分器依赖：按配置选择实现；测试可覆盖为计数或抛异常实现。"""
    return get_splitter(settings)
