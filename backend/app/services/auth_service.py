import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models.auth_session import AuthSession
from app.models.user import User

SESSION_TTL = timedelta(days=3)


class UsernameTakenError(Exception):
    """注册时 username 已被占用（含并发场景下唯一约束冲突）。"""


def _generate_token() -> str:
    """64 位十六进制随机 token。"""
    return secrets.token_hex(32)


async def _create_session(db: AsyncSession, user_id: int, clock: Clock) -> str:
    token = _generate_token()
    db.add(
        AuthSession(
            token=token,
            user_id=user_id,
            expires_at=clock.now() + SESSION_TTL,
        )
    )
    return token


async def login(db: AsyncSession, username: str, clock: Clock) -> tuple[User, str] | None:
    """按 username 登录。命中则新建 session 返回 (user, token)，未命中返回 None。"""
    user = await db.scalar(select(User).where(User.username == username))
    if user is None:
        return None
    token = await _create_session(db, user.id, clock)
    await db.commit()
    return user, token


async def register(
    db: AsyncSession, username: str, name: str, clock: Clock
) -> tuple[User, str]:
    """注册新账号：原子写入 user + session。

    并发同一 username 时，唯一约束触发 IntegrityError，统一抛 UsernameTakenError。
    name 为空时回退用 username 作为显示名。
    """
    display_name = name.strip() or username
    user = User(name=display_name, username=username)
    db.add(user)
    try:
        await db.flush()  # 触发唯一约束检查
    except IntegrityError:
        await db.rollback()
        raise UsernameTakenError
    token = await _create_session(db, user.id, clock)
    await db.commit()
    return user, token


async def logout(db: AsyncSession, token: str) -> None:
    """登出：删除 session 行（token 立即失效）。"""
    await db.execute(delete(AuthSession).where(AuthSession.token == token))
    await db.commit()


async def get_session_user_id(
    db: AsyncSession, token: str, clock: Clock
) -> int | None:
    """校验 token 并返回 user_id；缺失或过期返回 None。"""
    session = await db.get(AuthSession, token)
    if session is None:
        return None
    if session.expires_at <= clock.now():
        # 过期 session 清理掉，避免表无限增长
        await db.execute(delete(AuthSession).where(AuthSession.token == token))
        await db.commit()
        return None
    return session.user_id
