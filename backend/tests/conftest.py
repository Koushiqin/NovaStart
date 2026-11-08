"""测试全局 fixture。

为兼容既有测试用例（通过 X-User-Id 头部传递身份），在测试环境下把
`get_current_user_id` 覆盖为「读 X-User-Id 并校验账号存在」，行为与改造前一致。
新鉴权逻辑（Bearer token）由 test_auth.py 单独覆盖。
"""

import pytest
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user_id
from app.main import app
from app.services import user_service


@pytest.fixture(autouse=True)
def _auth_header_override():
    async def _override(
        x_user_id: int = Header(alias="X-User-Id"),
        db: AsyncSession = Depends(get_session),
    ) -> int:
        if not await user_service.user_exists(db, x_user_id):
            raise HTTPException(
                status_code=404,
                detail={"code": "USER_NOT_FOUND", "message": f"账号 {x_user_id} 不存在"},
            )
        return x_user_id

    app.dependency_overrides[get_current_user_id] = _override
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
