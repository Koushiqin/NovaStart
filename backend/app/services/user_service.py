from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def list_users(db: AsyncSession) -> list[User]:
    """演示账号列表，按 id 升序。"""
    return list(await db.scalars(select(User).order_by(User.id)))


async def user_exists(db: AsyncSession, user_id: int) -> bool:
    """账号是否存在（请求头身份校验用）。"""
    return await db.scalar(select(User.id).where(User.id == user_id)) is not None


async def find_by_name_or_id(db: AsyncSession, raw: str) -> User | None:
    """信件收件人解析：去空白后全数字按 id，否则按 name 精确匹配（A8）。"""
    value = raw.strip()
    if not value:
        return None
    if value.isdigit():
        return await db.scalar(select(User).where(User.id == int(value)))
    return await db.scalar(select(User).where(User.name == value))


async def get_names(db: AsyncSession, user_ids: Iterable[int | None]) -> dict[int, str]:
    """批量取账号名，供 sender_name / recipient_name 拼装；空集合不查库。"""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.name).where(User.id.in_(ids)))
    return dict(rows.all())
