from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.models.session import Session
from app.models.user import User

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

# 独立测试库（novastart_test），不碰开发库数据；模型含 JSONB/timestamptz，SQLite 无法兼容
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


@pytest.fixture
async def db_session():
    """每个用例独立引擎（pytest-asyncio 每用例新事件循环），并重建空表。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncSession:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as session:
        yield session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _make_user(db_session: AsyncSession) -> int:
    user = User(name="测试用户")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


async def _make_task(client: AsyncClient, user_id: int, text: str = "读完第三章并做习题") -> int:
    created = await client.post(
        "/api/tasks",
        json={"raw_text": text},
        headers={"X-User-Id": str(user_id)},
    )
    assert created.status_code == 201
    task_id = created.json()["task"]["id"]
    analyzed = await client.post(
        f"/api/tasks/{task_id}/analyze", headers={"X-User-Id": str(user_id)}
    )
    assert analyzed.status_code == 200
    return task_id


async def test_create_task_returns_mock_split_result(client, db_session):
    user_id = await _make_user(db_session)

    created = await client.post(
        "/api/tasks",
        json={"raw_text": "读完第三章并做习题"},
        headers={"X-User-Id": str(user_id)},
    )
    assert created.status_code == 201

    resp = await client.post(
        f"/api/tasks/{created.json()['task']['id']}/analyze",
        headers={"X-User-Id": str(user_id)},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "mock"
    assert data["starter_step"]
    assert 1 <= len(data["steps"]) <= 3
    assert data["server_time"]


async def test_create_session_then_current_reports_elapsed(client, db_session):
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)

    resp = await client.post(
        "/api/sessions",
        json={"task_id": task_id},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    assert resp.json()["server_time"]

    resp = await client.get("/api/sessions/current", headers={"X-User-Id": str(user_id)})
    data = resp.json()
    assert data["session"]["id"] == session_id
    assert data["session"]["status"] == "active"
    assert data["session"]["elapsed_sec"] >= 0
    assert data["server_time"]


async def test_current_marks_completed_after_five_minutes(client, db_session):
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    resp = await client.post(
        "/api/sessions",
        json={"task_id": task_id},
        headers={"X-User-Id": str(user_id)},
    )
    session_id = resp.json()["session_id"]

    # 直接把 started_at 改到 6 分钟前，模拟已超过最小专注时长
    six_min_ago = datetime.now(SHANGHAI_TZ) - timedelta(minutes=6)
    await db_session.execute(
        update(Session).where(Session.id == session_id).values(started_at=six_min_ago)
    )
    await db_session.commit()

    resp = await client.get("/api/sessions/current", headers={"X-User-Id": str(user_id)})
    assert resp.json()["session"]["status"] == "completed"  # 懒计算生效
