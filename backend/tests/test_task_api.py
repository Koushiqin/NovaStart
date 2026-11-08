"""F1+F2 今日任务接口测试：草稿 → 分析 → 编辑，覆盖 Spec 002 第 3 节验收条件。"""

from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clock import Clock
from app.db import Base, get_session
from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter
from app.main import app
from app.models.day_task import DayTask
from app.models.session import Session
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


async def _make_user(db_session: AsyncSession, name: str = "测试用户") -> int:
    user = User(name=name, username=name)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


def _header(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


class CountingSplitter:
    """记录真实 split 调用次数，用于验证「同标题只调一次」。"""

    def __init__(self, inner: TaskSplitter) -> None:
        self._inner = inner
        self.calls = 0

    async def split(self, task_text: str, date: str) -> SplitResult:
        self.calls += 1
        return await self._inner.split(task_text, date)


class ExplodingSplitter:
    """模拟模型不可用：任何调用都抛异常，用于验证降级不阻塞。"""

    async def split(self, task_text: str, date: str) -> SplitResult:
        raise RuntimeError("模型不可用")


def _use_splitter(splitter: TaskSplitter) -> None:
    """覆盖拆分器依赖（延迟 import，保证实现前测试仍以断言失败而非导入错误呈现）。"""
    from app.deps import get_task_splitter

    app.dependency_overrides[get_task_splitter] = lambda: splitter


async def _create(client: AsyncClient, user_id: int, text: str = "读完第三章并做习题") -> dict:
    resp = await client.post("/api/tasks", json={"raw_text": text}, headers=_header(user_id))
    assert resp.status_code == 201, resp.text
    return resp.json()["task"]


async def _analyze(client: AsyncClient, user_id: int, task_id: int):
    return await client.post(f"/api/tasks/{task_id}/analyze", headers=_header(user_id))


async def test_create_draft_then_get_today(client: AsyncClient, db_session: AsyncSession) -> None:
    """首次输入只建草稿：不调 splitter、无 starter/steps。"""
    user_id = await _make_user(db_session)

    task = await _create(client, user_id, "背 20 个单词")

    assert task["raw_text"] == "背 20 个单词"
    assert task["starter_step"] == ""
    assert task["steps"] == []
    assert task["origin_starter_step"] is None
    assert task["origin_steps"] is None
    assert task["analyzed"] is False
    assert task["split_stale"] is False
    assert task["locked"] is False
    assert task["source"] is None

    resp = await client.get("/api/tasks/today", headers=_header(user_id))
    data = resp.json()
    assert data["task"]["id"] == task["id"]
    assert data["task"]["analyzed"] is False
    assert data["carry_over"] is None
    assert data["server_time"]


async def test_create_duplicate_returns_existing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """同一自然日重复建任务返回既有任务，不新建也不改文本。"""
    user_id = await _make_user(db_session)
    first = await _create(client, user_id, "背单词")

    resp = await client.post(
        "/api/tasks", json={"raw_text": "换一个标题"}, headers=_header(user_id)
    )

    assert resp.status_code == 200
    assert resp.json()["task"]["id"] == first["id"]
    assert resp.json()["task"]["raw_text"] == "背单词"
    rows = (await db_session.scalars(select(DayTask))).all()
    assert len(rows) == 1


async def test_create_new_task_after_previous_locked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """当天任务已开始后，再建任务会新增一条同日任务，并成为 /tasks/today 的最新任务。"""
    user_id = await _make_user(db_session)
    clock = Clock()
    first = await _create(client, user_id, "背单词")

    db_session.add(
        Session(user_id=user_id, task_id=first["id"], started_at=clock.now(), status="completed")
    )
    await db_session.commit()

    second = await _create(client, user_id, "读一章书")

    assert second["id"] != first["id"]
    assert second["raw_text"] == "读一章书"
    assert second["locked"] is False

    rows = (await db_session.scalars(select(DayTask))).all()
    assert len(rows) == 2

    today = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]
    assert today["id"] == second["id"]

    # 新任务可独立分析，不受旧任务锁定影响
    resp = await _analyze(client, user_id, second["id"])
    assert resp.status_code == 200, resp.text


async def test_empty_and_over_200_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """空 / 纯空白 / 超 200 字一律 422，且不落库。"""
    user_id = await _make_user(db_session)

    for text in ("", "   ", "字" * 201):
        resp = await client.post("/api/tasks", json={"raw_text": text}, headers=_header(user_id))
        assert resp.status_code == 422, (text[:10], resp.text)

    rows = (await db_session.scalars(select(DayTask))).all()
    assert rows == []


async def test_analyze_stores_both_versions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """分析后原始版与采用版一致，来源与日期落库。"""
    user_id = await _make_user(db_session)
    task = await _create(client, user_id)

    resp = await _analyze(client, user_id, task["id"])

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] in {"mock", "llm", "fallback"}
    assert data["starter_step"]
    assert 1 <= len(data["steps"]) <= 3
    assert data["server_time"]

    today = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]
    assert today["analyzed"] is True
    assert today["origin_starter_step"] == today["starter_step"]
    assert today["origin_steps"] == today["steps"]
    assert today["split_stale"] is False
    assert today["source"] == data["source"]

    row = await db_session.scalar(select(DayTask).where(DayTask.id == task["id"]))
    assert row is not None and row.analyzed_text == row.raw_text


async def test_analyze_fallback_on_splitter_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """模型抛异常 → 200 + 模板拆分 + source=fallback，流程不阻塞。"""
    user_id = await _make_user(db_session)
    _use_splitter(ExplodingSplitter())
    task = await _create(client, user_id)

    resp = await _analyze(client, user_id, task["id"])

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "fallback"
    assert data["starter_step"]
    assert 0 <= len(data["steps"]) <= 3

    today = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]
    assert today["source"] == "fallback"
    assert today["analyzed"] is True


async def test_analyze_cache_reuse(client: AsyncClient, db_session: AsyncSession) -> None:
    """同一标题连点分析：splitter 只被调用一次，结果复用。"""
    user_id = await _make_user(db_session)
    counting = CountingSplitter(MockSplitter())
    _use_splitter(counting)
    task = await _create(client, user_id, "背 20 个单词")

    first = await _analyze(client, user_id, task["id"])
    second = await _analyze(client, user_id, task["id"])

    assert first.status_code == 200 and second.status_code == 200
    assert counting.calls == 1
    assert first.json()["starter_step"] == second.json()["starter_step"]
    assert first.json()["steps"] == second.json()["steps"]


async def test_patch_edits_adopted_only(client: AsyncClient, db_session: AsyncSession) -> None:
    """手动编辑只改采用版，模型原始版保持不变，刷新后仍在。"""
    user_id = await _make_user(db_session)
    task = await _create(client, user_id)
    await _analyze(client, user_id, task["id"])
    before = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]

    resp = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"starter_step": "先读摘要", "steps": ["圈出重点", "只看第一段"]},
        headers=_header(user_id),
    )

    assert resp.status_code == 200, resp.text
    edited = resp.json()["task"]
    assert edited["starter_step"] == "先读摘要"
    assert edited["steps"] == ["圈出重点", "只看第一段"]
    assert edited["origin_starter_step"] == before["origin_starter_step"]
    assert edited["origin_steps"] == before["origin_steps"]
    assert edited["analyzed"] is True

    today = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]
    assert today["starter_step"] == "先读摘要"
    assert today["steps"] == ["圈出重点", "只看第一段"]


async def test_patch_title_keeps_split_sets_stale(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """分析后改标题：保留旧拆分、不重新调模型，响应标记可重新分析。"""
    user_id = await _make_user(db_session)
    counting = CountingSplitter(MockSplitter())
    _use_splitter(counting)
    task = await _create(client, user_id, "背 20 个单词")
    analyzed = (await _analyze(client, user_id, task["id"])).json()

    resp = await client.patch(
        f"/api/tasks/{task['id']}", json={"raw_text": "背 30 个单词"}, headers=_header(user_id)
    )

    assert resp.status_code == 200, resp.text
    edited = resp.json()["task"]
    assert edited["raw_text"] == "背 30 个单词"
    assert edited["starter_step"] == analyzed["starter_step"]
    assert edited["steps"] == analyzed["steps"]
    assert edited["analyzed"] is True
    assert edited["split_stale"] is True
    assert counting.calls == 1  # 改标题不自动重新分析

    today = (await client.get("/api/tasks/today", headers=_header(user_id))).json()["task"]
    assert today["split_stale"] is True


async def test_patch_and_analyze_locked_after_session_start(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """计时开始后编辑 / 重新分析一律 409，防止学着学着换任务。"""
    user_id = await _make_user(db_session)
    task = await _create(client, user_id)
    await _analyze(client, user_id, task["id"])
    session = await client.post(
        "/api/sessions", json={"task_id": task["id"]}, headers=_header(user_id)
    )
    assert session.status_code == 200

    resp = await client.patch(
        f"/api/tasks/{task['id']}", json={"starter_step": "改一下"}, headers=_header(user_id)
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "TASK_LOCKED"

    resp = await _analyze(client, user_id, task["id"])
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "TASK_LOCKED"


async def test_carry_over_yesterday_unfinished(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """昨天有任务且无完成会话 → carry_over；一旦有完成会话就不再提示。"""
    user_id = await _make_user(db_session)
    clock = Clock()
    yesterday = clock.today() - timedelta(days=1)
    task = DayTask(
        user_id=user_id,
        date=yesterday,
        raw_text="昨天没走完的任务",
        starter_step="打开资料",
        steps=[],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    data = (await client.get("/api/tasks/today", headers=_header(user_id))).json()
    assert data["task"] is None
    assert data["carry_over"]["raw_text"] == "昨天没走完的任务"
    assert data["carry_over"]["date"] == yesterday.isoformat()

    db_session.add(
        Session(user_id=user_id, task_id=task.id, started_at=clock.now(), status="completed")
    )
    await db_session.commit()

    data = (await client.get("/api/tasks/today", headers=_header(user_id))).json()
    assert data["carry_over"] is None


async def test_task_not_owned_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """任务归属校验：其他账号不能编辑或分析本账号任务。"""
    user_a = await _make_user(db_session, "账号甲")
    user_b = await _make_user(db_session, "账号乙")
    task = await _create(client, user_a)

    patch = await client.patch(
        f"/api/tasks/{task['id']}", json={"starter_step": "偷改"}, headers=_header(user_b)
    )
    assert patch.status_code == 404
    assert patch.json()["detail"]["code"] == "TASK_NOT_FOUND"

    analyze = await _analyze(client, user_b, task["id"])
    assert analyze.status_code == 404
    assert analyze.json()["detail"]["code"] == "TASK_NOT_FOUND"
