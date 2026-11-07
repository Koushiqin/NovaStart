from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.llm import TaskSplitter, get_splitter
from app.services import user_service


async def get_current_user_id(
    x_user_id: int = Header(alias="X-User-Id"),
    db: AsyncSession = Depends(get_session),
) -> int:
    """当前用户单点解析：请求头必填，账号必须存在。

    缺失 / 非整数由 FastAPI 请求头校验直接返回 422；账号不存在统一 404，
    在业务逻辑执行前拦截，避免落库半截数据。
    """
    if not await user_service.user_exists(db, x_user_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": f"账号 {x_user_id} 不存在"},
        )
    return x_user_id


def get_task_splitter() -> TaskSplitter:
    """任务拆分器依赖：按配置选择实现；测试可覆盖为计数或抛异常实现。"""
    return get_splitter(settings)
