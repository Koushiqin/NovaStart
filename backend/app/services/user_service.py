from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def list_users(db: AsyncSession) -> list[User]:
    """演示账号列表，按 id 升序。"""
    return list(await db.scalars(select(User).order_by(User.id)))


async def user_exists(db: AsyncSession, user_id: int) -> bool:
    """账号是否存在（请求头身份校验用）。"""
    return await db.scalar(select(User.id).where(User.id == user_id)) is not None
