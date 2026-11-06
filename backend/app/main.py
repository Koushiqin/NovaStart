from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.db import engine, get_session
from app.seed import reset_seed

app = FastAPI(title="NovaStart")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """探活接口：区分「进程活着」与「DB 可连」，server_time 是前端校准时钟的唯一来源。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "up"
    except Exception:
        db_status = "down"
    return {"status": "ok", "server_time": Clock().now().isoformat(), "db": db_status}


@app.post("/dev/reset-seed")
async def dev_reset_seed(session: AsyncSession = Depends(get_session)) -> dict:
    """演示用：重置种子数据。Demo 项目无生产环境，固定挂载。"""
    users = await reset_seed(session)
    return {"ok": True, "users": [{"id": u.id, "name": u.name} for u in users]}


if __name__ == "__main__":
    # 本地开发启动入口（start-api.bat 走这里）。
    # 不能用裸 uvicorn CLI：它先建 Proactor 事件循环再 import 本模块，
    # psycopg 异步在 Windows 下将直接报错；经此入口可让 db.py 顶部的
    # Selector 事件循环策略在 loop 创建前生效（--reload 子进程经 spawn
    # 重导入本模块时也会执行到）。
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
