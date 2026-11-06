import asyncio
import sys
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# psycopg 3 异步模式不支持 Windows 默认的 ProactorEventLoop，须切到 Selector 循环
# 放在引擎创建之前生效；uvicorn / pytest-asyncio 均经事件循环策略建 loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，Alembic 的 target_metadata 指向它。"""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每个请求一个 AsyncSession。"""
    async with SessionLocal() as session:
        yield session
