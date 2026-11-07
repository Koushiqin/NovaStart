from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.models.day_task import DayTask
from app.models.user import User

# 独立测试库（novastart_test），不碰开发库数据；模型含 JSONB/timestamptz，SQLite 无法兼容
TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """每个用例独立引擎（pytest-asyncio 每用例新事件循环），并重建空表。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    async with session_factory() as session:
        yield session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _make_user(db_session: AsyncSession, name: str) -> int:
    user = User(name=name)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


def _header(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def test_missing_header_is_422_from_header_binding(client: AsyncClient) -> None:
    """缺 X-User-Id 必须是请求头校验失败（422 且 loc 指向 header），不能落到 500。"""
    resp = await client.post("/api/tasks", json={"raw_text": "背单词"})

    assert resp.status_code == 422
    locs = [tuple(item["loc"]) for item in resp.json()["detail"]]
    assert any(loc[0] == "header" and loc[1].lower() == "x-user-id" for loc in locs), locs

    resp = await client.get("/api/sessions/current")
    assert resp.status_code == 422


async def test_unknown_user_is_404_with_code(client: AsyncClient) -> None:
    resp = await client.post("/api/tasks", json={"raw_text": "x"}, headers=_header(9999))

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"
    assert resp.json()["detail"]["message"]


async def test_users_endpoint_returns_seed_accounts(client: AsyncClient) -> None:
    assert (await client.post("/dev/reset-seed")).status_code == 200

    resp = await client.get("/api/users")

    assert resp.status_code == 200
    data = resp.json()
    assert [u["name"] for u in data["users"]] == ["小明", "小美", "小刚"]
    assert data["server_time"]


async def test_reset_seed_keeps_demo_user_ids(client: AsyncClient) -> None:
    """重复 reset-seed 不得改变三个固定演示账号的 id。

    前端把 userId 持久化到 localStorage，若 reset 后 id 漂移，
    刷新页面时已选账号会匹配不到任何按钮（验收条件 4 失败）。
    """
    first = (await client.post("/dev/reset-seed")).json()["users"]
    assert [u["name"] for u in first] == ["小明", "小美", "小刚"]

    second = (await client.post("/dev/reset-seed")).json()["users"]
    assert [u["id"] for u in second] == [u["id"] for u in first]


async def test_task_owner_comes_from_header(client: AsyncClient, db_session: AsyncSession) -> None:
    """两个账号各建任务：落库的 user_id 来自请求头，查询各自只见自己的数据。"""
    user_a = await _make_user(db_session, "账号甲")
    user_b = await _make_user(db_session, "账号乙")

    resp_a = await client.post(
        "/api/tasks", json={"raw_text": "甲的任务"}, headers=_header(user_a)
    )
    resp_b = await client.post(
        "/api/tasks", json={"raw_text": "乙的任务"}, headers=_header(user_b)
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201

    rows = (await db_session.scalars(select(DayTask).order_by(DayTask.id))).all()
    assert [(r.user_id, r.raw_text) for r in rows] == [
        (user_a, "甲的任务"),
        (user_b, "乙的任务"),
    ]


async def test_current_session_not_visible_across_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_a = await _make_user(db_session, "账号甲")
    user_b = await _make_user(db_session, "账号乙")
    task = await client.post("/api/tasks", json={"raw_text": "甲的任务"}, headers=_header(user_a))
    session = await client.post(
        "/api/sessions", json={"task_id": task.json()["task"]["id"]}, headers=_header(user_a)
    )
    assert session.status_code == 200

    resp_b = await client.get("/api/sessions/current", headers=_header(user_b))
    assert resp_b.json()["session"] is None

    resp_a = await client.get("/api/sessions/current", headers=_header(user_a))
    assert resp_a.json()["session"]["status"] == "active"
