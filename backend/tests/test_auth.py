"""鉴权：注册 / 登录 / 登出 / 会话过期（Spec 009 验收条件 1–8）。

本文件测试真实 Bearer 鉴权路径，因此在 fixture 中移除 conftest 的
X-User-Id 兼容覆盖，让 get_current_user_id 走 sessions 表校验。
"""

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import Clock
from app.db import Base, get_session
from app.deps import get_current_user_id
from app.main import app
from app.models.auth_session import AuthSession
from app.models.user import User

TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/novastart_test"


class FixedClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now

    def today(self):
        return self._now.date()


@pytest.fixture
async def db_env():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    # 移除 conftest 的 X-User-Id 覆盖，使用真实 Bearer 鉴权
    app.dependency_overrides.pop(get_current_user_id, None)
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def db_session(db_env):
    async with db_env() as session:
        yield session


@pytest.fixture
async def client(db_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def fixed_clock(db_env):
    from datetime import datetime, timezone

    clock = FixedClock(datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc))
    from app.clock import get_clock

    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


async def test_register_creates_user_and_session(client, db_session, fixed_clock):
    resp = await client.post("/api/auth/register", json={"username": "alice"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["username"] == "alice"
    assert body["token"]
    # session 行存在且 3 天后过期
    sess = await db_session.scalar(select(AuthSession).where(AuthSession.token == body["token"]))
    assert sess is not None
    assert sess.expires_at == fixed_clock.now() + timedelta(days=3)
    user = await db_session.scalar(select(User).where(User.username == "alice"))
    assert user is not None


async def test_register_invalid_length_422(client):
    for username in ["", "a" * 16]:
        resp = await client.post("/api/auth/register", json={"username": username})
        assert resp.status_code == 422


async def test_register_duplicate_409(client):
    await client.post("/api/auth/register", json={"username": "bob"})
    resp = await client.post("/api/auth/register", json={"username": "bob"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "USERNAME_TAKEN"


async def test_login_success_returns_token(client, db_session, fixed_clock):
    await client.post("/api/auth/register", json={"username": "carol"})

    resp = await client.post("/api/auth/login", json={"username": "carol"})

    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "carol"
    assert resp.json()["token"]


async def test_login_unknown_404(client):
    resp = await client.post("/api/auth/login", json={"username": "ghost"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"


async def test_bearer_token_grants_access(client, db_session, fixed_clock):
    reg = await client.post("/api/auth/register", json={"username": "dave"})
    token = reg.json()["token"]

    # 带有效 token 访问受保护接口
    resp = await client.get(
        "/api/progress/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


async def test_missing_token_401(client):
    resp = await client.get("/api/progress/summary")
    assert resp.status_code == 401


async def test_expired_token_401(client, db_session, fixed_clock):
    reg = await client.post("/api/auth/register", json={"username": "erin"})
    token = reg.json()["token"]

    # 把时钟拨到 3 天零 1 秒后，session 过期
    fixed_clock._now = fixed_clock.now() + timedelta(days=3, seconds=1)

    resp = await client.get(
        "/api/progress/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401
    # 过期 session 被清理
    assert await db_session.scalar(select(AuthSession).where(AuthSession.token == token)) is None


async def test_logout_invalidates_token(client, db_session, fixed_clock):
    reg = await client.post("/api/auth/register", json={"username": "frank"})
    token = reg.json()["token"]

    resp = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    resp = await client.get(
        "/api/progress/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401


async def test_register_concurrent_same_username_one_succeeds(client, db_session, fixed_clock):
    """并发注册同一 username：唯一约束保证只有一个成功。"""
    import asyncio

    async def register():
        return await client.post("/api/auth/register", json={"username": "grace"})

    results = await asyncio.gather(register(), register(), return_exceptions=True)
    statuses = [r.status_code for r in results if not isinstance(r, Exception)]
    assert 201 in statuses
    assert 409 in statuses
    # 库里只有一个 grace
    count = await db_session.scalar(select(User).where(User.username == "grace"))
    assert count is not None
