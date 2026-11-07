# P1–P3 复审修复实施计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行；步骤用 `- [ ]` 追踪。每个任务先跑红测试再改代码，完成即 commit。

**Goal:** 修复 P1–P3 复审确认的 13 项问题中可执行的部分，使「有效结束 → 结算 → 再开一场」主链路无断点，并统一会话状态、归属日与时间偏移口径，为 P4 开工清障。

**Architecture:** 后端以 `settle_service.advance` 为唯一结算推进入口（校验归属与 `ended_at`，第④步同事务置 `settled`）；前端不再以持久化 `currentSessionId` 作判定依据，首页锁定态通过 `GET /sessions/current` 分流；时间偏移覆盖信件/种子/健康检查，归属日统一用 Asia/Shanghai 的 SQL 转换。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL 16；React 18 + zustand + axios；pytest（真实 PG `novastart_test`，Clock 注入，禁止 sleep）。

**Spec:** [P1–P3 复审修复清单](../../../.superpowers/sdd/2026-11-07-p1-p3-review-fix-list.md)；口径依据 [Spec 003](../../../docs/specs/003-f3-focus-session.md)，下游消费方见 [P4](../plans/2026-11-07-p4-f4-f5-settle-reflection.md)、[P5](../plans/2026-11-07-p5-f7-star-streak.md)、[P7](../plans/2026-11-07-p7-f10-random-review.md)、[P8](../plans/2026-11-07-p8-f8-records.md)。

## Global Constraints

- 不新增数据库迁移；本计划不改 ORM 模型（FIX-13 不落地）。
- 不新增依赖，不改启动方式，不改 CI，不放宽 `tests/test_architecture.py`。
- 后端时间判定只走 `app/clock.py` 的 `Clock`；前端只走 `useServerClock`，HTTP 只走 `api/client.ts`。
- 后端测试固定 `novastart_test`，连库命令一律沙箱外执行；时序测试注入 `Clock`，禁止 sleep。
- 前端无自动化测试框架：以 `npm run lint` + `npm run build` + 浏览器复验为准，并在对应 Spec 回填。
- 每个任务独立 commit；未跑过验证命令不得声明完成。

## Review Focus

1. 有效结束（`completed` 且 `ended_at` 已写）后点首页按钮 → 去 `/settle`，不再回 `/focus`；结算完成（`settled`）后 → 直接新建下一场（Task 3、Task 4）。
2. 对 `active` 或 `completed` 但 `ended_at IS NULL` 的会话推进结算 → 404，且库内 `settle_step` 不变（Task 2）。
3. 第④步推进后 `status="settled"`；再推进到更小步仍返回 4、状态不回退（Task 2）。
4. `-86400` 偏移下：种子「今天」、当日信件过期、`/health` 的 `server_time` 全部与注入的 `Clock` 一致（Task 6）。
5. LLM 返回 `steps` 为字符串或含非字符串项 → 抛错走 fallback，绝不拆成单字符（Task 9）。

---

### Task 1: 统一 `settled` / `completed` 口径（FIX-02）

**Files:**
- Modify: `docs/specs/003-f3-focus-session.md`（§6.1 命名说明、§6.4）
- Modify: `docs/superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md:64`
- Modify: `docs/superpowers/plans/2026-11-07-p5-f7-star-streak.md`（Global Constraints）
- Modify: `docs/superpowers/plans/2026-11-07-p7-f10-random-review.md`（Architecture）
- Modify: `docs/superpowers/plans/2026-11-07-p8-f8-records.md`（Architecture）

**Interfaces:**
- Consumes: Spec 003 §6.1/§6.4 现有措辞。
- Produces: 全项目统一口径——`completed` = 有效待结算；`settled` = 第④步完成；统计过滤一律 `status IN ('completed','settled') AND ended_at IS NOT NULL`。

- [ ] **Step 1:** 把 Spec 003 §6.1「命名说明」改为明确迁移规则：API 的 `result="settled"` 只表示「有效、可进结算页」；库内从 `completed` 到 `settled` 的唯一入口是 `settle_service.advance` 在 `to_step=4` 时同事务写 `status="settled"`。
- [ ] **Step 2:** 在 Spec 003 §6.4 表下补一行：「状态迁移：`completed` --(settle_step 达 4)--> `settled`；`advance` 是唯一迁移入口，重复调用保持 4」。
- [ ] **Step 3:** 把 P4 计划 L64 的 `status=="completed"` 改为 `status.in_(("completed", "settled"))`；并在 Task 2 Step 3 前补一句：第④步完成调用 `advance(db, session_id, 4, user_id)`，服务端同事务置 `settled`。
- [ ] **Step 4:** P5 Global Constraints、P7 Architecture、P8 Architecture 各补一句：「有效场次 = `status IN ('completed','settled') AND ended_at IS NOT NULL`；`discarded` 与进行中场次一律排除」。
- [ ] **Step 5: 验证** `Grep` 计划目录中的 `status=="completed"`，预期 0 条；`status.in_(("completed", "settled"))` 出现在 P4。
- [ ] **Step 6: Commit** `docs: unify completed and settled session semantics`

### Task 2: 结算推进校验归属与已结束，第④步置 `settled`（FIX-03）

**Files:**
- Modify: `backend/app/services/settle_service.py`
- Modify: `backend/app/routers/settle.py`
- Modify: `docs/superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md:64`（`advance(..., 1)` 补 `user_id` 参数）
- Test: `backend/tests/test_letter_settle.py`

**Interfaces:**
- Consumes: `Session` 模型、`get_current_user_id`。
- Produces: `settle_service.advance(db: AsyncSession, session_id: int, to_step: int, user_id: int) -> int | None`；仅 `user_id` 本人、`ended_at IS NOT NULL`、`status IN ('completed','settled')` 的会话可推进；`None` → 404 `{"code":"SESSION_NOT_FOUND","message":"会话不存在"}`；`to_step=4` 同事务置 `status="settled"`。

- [ ] **Step 1: 写失败测试**

先扩展 `backend/tests/test_letter_settle.py` 的 helper，并加三个用例：

```python
async def _make_session_row(
    db_session, user_id, status: str = "active", *, ended: bool = False
) -> int:
    started_at = datetime.now(SHANGHAI_TZ)
    session = Session(
        user_id=user_id, task_id=task.id, started_at=started_at, status=status,
        ended_at=started_at + timedelta(minutes=5) if ended else None,
        duration_sec=300 if ended else None,
    )
    ...

async def _session_row(db_session, session_id):
    await db_session.rollback()
    return await db_session.get(Session, session_id)

async def test_advance_rejects_in_progress(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id, status="completed")  # ended_at=None
    resp = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2},
                             headers={"X-User-Id": str(user_id)})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SESSION_NOT_FOUND"
    assert (await _session_row(db_session, sid)).settle_step == 0

async def test_advance_rejects_other_users_session(client, db_session):
    owner_id = await _make_user(db_session)
    other_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, owner_id, status="completed", ended=True)
    resp = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2},
                             headers={"X-User-Id": str(other_id)})
    assert resp.status_code == 404
    assert (await _session_row(db_session, sid)).settle_step == 0

async def test_advance_four_marks_settled_and_monotonic(client, db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id, status="completed", ended=True)
    headers = {"X-User-Id": str(user_id)}
    r = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 4}, headers=headers)
    assert r.json()["settle_step"] == 4
    row = await _session_row(db_session, sid)
    assert row.status == "settled"
    r2 = await client.post(f"/api/settle/{sid}/advance", json={"to_step": 2}, headers=headers)
    assert r2.json()["settle_step"] == 4
    row = await _session_row(db_session, sid)
    assert row.status == "settled" and row.settle_step == 4
```

同时把既有 `test_settle_advance_idempotent_and_monotonic` 的 `_make_session_row(..., status="completed")` 改为 `ended=True`（否则会被新规则 404）。

- [ ] **Step 2:** 跑三个新用例，预期 FAIL（当前 `advance` 无 `user_id` 参数、不校验 `ended_at`、不会置 `settled`）。
- [ ] **Step 3: 实现**

`settle_service.advance` 改为：

```python
_SETTLEABLE_STATUSES = ("completed", "settled")

async def advance(db, session_id, to_step, user_id) -> int | None:
    session = await db.scalar(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(_SETTLEABLE_STATUSES),
        )
    )
    if session is None:
        return None
    values = {"settle_step": to_step}
    if to_step >= 4:
        values["status"] = "settled"
    await db.execute(
        update(Session)
        .where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.ended_at.is_not(None),
            Session.status.in_(_SETTLEABLE_STATUSES),
            Session.settle_step < to_step,
        )
        .values(**values)
    )
    await db.commit()
    await db.refresh(session)
    return session.settle_step
```

router 把 `_user_id` 改名为 `user_id` 并传入；404 改结构化 detail。

- [ ] **Step 4:** 更新 P4 计划 L64 的 `settle_service.advance(..., 1)` 为 `settle_service.advance(db, session_id, 1, user_id)`。
- [ ] **Step 5: 验证** 跑 `test_letter_settle.py` 全绿 + `pytest backend -q` 全绿 + 架构棘轮。
- [ ] **Step 6: Commit** `fix(backend): settle advance ownership and ended-only guard`

### Task 3: 有效结束后可再开一场（FIX-01）

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx:116-136`
- Modify: `docs/superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md`（Task 3 Step 4）
- Test: `backend/tests/test_session_end.py`（回归）

**Interfaces:**
- Consumes: `GET /api/sessions/current`、`POST /api/sessions {task_id}`、`GET /api/tasks/today` 的 `locked`。
- Produces: 首页 `locked` 时点击按钮：当前会话 `ended_at IS NULL` → `/focus`；`ended_at` 已写 → `/settle`；无当前会话（已 `settled`）→ 新建会话后 `/focus`。

- [ ] **Step 1: 写回归测试**（当前后端已支持，预期直接 PASS，作为入口守卫）

```python
async def test_create_session_after_ended_creates_new(client, db_session, fixed_clock):
    user_id = await _make_user(db_session)
    task_id = await _make_task(client, user_id)
    first = await _start(client, user_id, task_id)
    fixed_clock.advance(300)
    await client.post(f"/api/sessions/{first['session_id']}/end", headers=await _header(user_id))
    second = await _start(client, user_id, task_id)
    assert second["session_id"] != first["session_id"]
```

- [ ] **Step 2:** 跑该用例；若 FAIL 先修 `session_service.create_session` 的复用条件，预期 PASS。
- [ ] **Step 3: 改 `HomePage.handleStart`**

`locked` 分支不再无条件 `navigate("/focus")`，改为：

先把 `const accountId = userId`、`setBusy("start")`、`setError(null)` 与 `try/catch/finally` 前置到 `locked` 分支之前，两个分支共用同一套落错与 `setBusy(null)`；分支内：

```tsx
const current = await apiClient.get<CurrentSessionResponse>("/sessions/current")
if (!stillCurrentAccount(accountId)) return
const ongoing = current.data.session
if (ongoing && ongoing.ended_at === null) { navigate("/focus"); return }
if (ongoing && ongoing.ended_at !== null) { navigate("/settle"); return }
const res = await apiClient.post<{ session_id: number }>("/sessions", { task_id: task.id })
if (!stillCurrentAccount(accountId)) return
setCurrentSessionId(res.data.session_id)
navigate("/focus")
```

本地定义 `interface CurrentSessionResponse { session: { id: number; ended_at: string | null } | null }`；按钮文案 `locked ? "继续" : "开始学习"`。

- [ ] **Step 4:** P4 计划 Task 3 Step 4 的完成页补「再学一场」按钮：`POST /api/sessions {task_id}` 成功后跳 `/focus`。
- [ ] **Step 5: 验证** `npm run lint`、`npm run build`；浏览器：有效结束 → 首页按钮落到 `/settle`，不会再「首页 ↔ /focus」循环。
- [ ] **Step 6: Commit** `fix(frontend): route locked task to settle or a new session`

### Task 4: `currentSessionId` 生命周期（FIX-04）

**Files:**
- Modify: `frontend/src/store/app.ts:28-32`
- Modify: `frontend/src/features/AccountSwitcher.tsx`
- Modify: `frontend/src/pages/FocusPage.tsx`（挂载、15s 轮询、封顶补发三处）
- Modify: `docs/superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md`（Task 3 Step 1）

**Interfaces:**
- Consumes: zustand `useAppStore`。
- Produces: 持久化只保留 `userId`；`currentSessionId` 仅作本次会话快捷入口，`/settle` 一律先 `GET /sessions/current` 取 id；切账号清空 `currentSessionId` 与 `settleStep`。

- [ ] **Step 1:** `store/app.ts` 的 `partialize` 改为 `({ userId }) => ({ userId })`，注释同步为「只持久化身份；当前会话每次由 `/sessions/current` 重新确认」。
- [ ] **Step 2:** `AccountSwitcher` 点击改为 `handleSwitch(id)`：先 `setCurrentSessionId(null)`、`setSettleStep(0)`，再 `setUserId(id)`。
- [ ] **Step 3:** `FocusPage` 增加 `const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId)`；挂载/轮询/封顶响应里：`current !== null` → `setCurrentSessionId(current.id)`；`current === null` → `setCurrentSessionId(null)` 后再返回。
- [ ] **Step 4:** P4 计划 Task 3 Step 1 改为「进入页面先 `GET /sessions/current` 取 session id（无会话回首页），再拉 summary」。
- [ ] **Step 5: 验证** `npm run lint`、`npm run build`；浏览器 DevTools 确认 `localStorage["novastart-user"]` 只含 `userId`；账号 A 开专注后切到 B，刷新不残留 A 的会话 id。
- [ ] **Step 6: Commit** `fix(frontend): make currentSessionId session-scoped`

### Task 5: 归属日时区口径（FIX-08）

**Files:**
- Modify: `docs/specs/003-f3-focus-session.md`（§6.4）
- Modify: `docs/superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md:64`
- Modify: `docs/superpowers/plans/2026-11-07-p5-f7-star-streak.md`、`...p7...`、`...p8...`

**Interfaces:**
- Consumes: 无（统计查询尚未实现）。
- Produces: 全项目归属日 SQL 写法统一为 `cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`；P4 必须新增 `test_summary_attribution_day_across_midnight`。

- [ ] **Step 1:** Spec 003 §6.4 补一句：归属日一律用上述表达式（等价 `started_at AT TIME ZONE 'Asia/Shanghai'`），禁止裸 `cast(started_at, Date)`——PostgreSQL 容器默认 UTC，会让 0–8 点场次落到前一天。
- [ ] **Step 2:** 把 P4 计划 L64 的 `cast(started_at, Date)` 替换为 `cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`；并写入 `test_summary_attribution_day_across_midnight`（23:30 与 00:30 两个边界）。
- [ ] **Step 3:** P5/P7/P8 计划中各补一句「归属日分组/候选过滤使用同一 `func.timezone` 表达式」。
- [ ] **Step 4: 验证** `Grep` 计划目录 `cast(started_at, Date)` 预期 0 条；`func.timezone("Asia/Shanghai"` 出现在 P4/P5/P7/P8。
- [ ] **Step 5: Commit** `docs: pin attribution day to Asia/Shanghai in SQL`

### Task 6: 时间偏移覆盖信件、seed、健康检查（FIX-05）

**Files:**
- Modify: `backend/app/services/letter_service.py:17-67`
- Modify: `backend/app/routers/letter.py:13-24`
- Modify: `backend/app/seed.py:63-107`
- Modify: `backend/app/main.py:32-48`
- Test: `backend/tests/test_letter_settle.py`、`backend/tests/test_clock.py`、新建 `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `Clock`、`get_clock`。
- Produces: `letter_service.deliver(db, user_id, session_id, content, clock)`、`letter_service.get_inbox(db, user_id, clock)`、`seed.reset_seed(session, clock)`；`GET /health` 经 `Depends(get_clock)` 取时间。`get_history` 无时间判定，不新增参数。

- [ ] **Step 1: 写失败测试**

```python
# test_letter_settle.py
async def test_inbox_expiry_uses_injected_clock(db_session):
    user_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, user_id)
    now = Clock()
    await letter_service.deliver(db_session, user_id, sid, "今天的信", now)
    assert len(await letter_service.get_inbox(db_session, user_id, now)) == 1
    assert await letter_service.get_inbox(db_session, user_id, Clock(offset_seconds=86400)) == []

# test_clock.py
async def test_health_uses_injected_clock():
    fixed = Clock(offset_seconds=3600)
    app.dependency_overrides[get_clock] = lambda: fixed
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/health")
    finally:
        app.dependency_overrides.pop(get_clock, None)
    assert abs((datetime.fromisoformat(resp.json()["server_time"]) - fixed.now()).total_seconds()) < 2

# test_seed.py（新建）：只建 engine/session，不挂 app 依赖覆盖
@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()

async def test_reset_seed_uses_injected_today(db_session):
    offset = Clock(offset_seconds=-86400)
    users = await reset_seed(db_session, offset)
    days = (await db_session.scalars(
        select(DayTask.date).where(DayTask.user_id == users[0].id)
    )).all()
    assert max(days) == offset.today() - timedelta(days=1)
```

- [ ] **Step 2:** `test_clock.py` 补 import：`datetime`、`httpx.AsyncClient`/`ASGITransport`、`app.main.app`；`test_seed.py` 补 `select`、`Base`、`DayTask`、`reset_seed` 与 `TEST_DATABASE_URL`。跑这三个用例，预期 FAIL（`deliver/get_inbox` 忽略传入时钟、`reset_seed` 无参数、`/health` 无时钟依赖）。
- [ ] **Step 3: 实现** `deliver` 删掉内部 `Clock()` 并接收 `clock`；`get_inbox` 的过期比较用传入 `clock.now()`；`reset_seed(session, clock)` 用 `clock.today()`；`/health` 加 `clock: Clock = Depends(get_clock)` 并用 `clock.now()`；letter router 的 `inbox` 把已有 `clock` 传给 service。
- [ ] **Step 4:** 把既有测试中所有 `letter_service.deliver(...)` 调用补末尾 `clock` 参数 `Clock()`；`main.dev_reset_seed` 补 `clock` 依赖并传入。
- [ ] **Step 5: 验证** `pytest backend -q` 全绿 + 架构棘轮。
- [ ] **Step 6: Commit** `fix(backend): route letter seed and health through demo clock`

### Task 7: 信件收藏校验归属（FIX-07）

**Files:**
- Modify: `backend/app/services/letter_service.py:89-102`
- Modify: `backend/app/routers/letter.py:41-55`
- Test: `backend/tests/test_letter_settle.py`

**Interfaces:**
- Consumes: `Letter.user_id`。
- Produces: `letter_service.favorite(db, letter_id, user_id) -> Letter | None`；非本人信件返回 None → 404 `{"code":"LETTER_NOT_FOUND","message":"信件不存在"}`。

- [ ] **Step 1: 写失败测试**

```python
async def test_favorite_other_users_letter_404(client, db_session):
    owner_id = await _make_user(db_session)
    other_id = await _make_user(db_session)
    sid = await _make_session_row(db_session, owner_id)
    letter = await letter_service.deliver(db_session, owner_id, sid, "别人的信", Clock())
    resp = await client.post(
        f"/api/letters/{letter.id}/favorite", headers={"X-User-Id": str(other_id)}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "LETTER_NOT_FOUND"
    row = await db_session.get(Letter, letter.id)
    assert row.favorited is False
```

- [ ] **Step 2:** 跑用例，预期 FAIL（当前 200 且收藏成功）。
- [ ] **Step 3: 实现** `favorite` 用 `select(Letter).where(Letter.id == letter_id, Letter.user_id == user_id)` 取行；router 传 `user_id` 并改结构化 404。
- [ ] **Step 4:** 更新 `test_favorite_is_idempotent` 的 `deliver` 调用补 `Clock()`。
- [ ] **Step 5: 验证** `pytest backend -q` 全绿。
- [ ] **Step 6: Commit** `fix(backend): scope letter favorite to its owner`

### Task 8: 切账号复位 `busy`（FIX-06）

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx:38-58`

**Interfaces:**
- Consumes: 无。
- Produces: 账号 effect 开始时清空 `busy`，新账号不必刷新即可操作。

- [ ] **Step 1:** 在 `useEffect(() => { ... }, [userId])` 开头、清空 `today/input/error` 的同一批 `set` 中加入 `setBusy(null)`。
- [ ] **Step 2: 验证** `npm run lint`、`npm run build`；浏览器：点「分析」后立即切账号，新账号按钮可点、不再永久禁用。
- [ ] **Step 3: Commit** `fix(frontend): reset busy state on account switch`

### Task 9: LLM `steps` 类型校验（FIX-10）

**Files:**
- Modify: `backend/app/llm/openai_compat.py:65-84`
- Test: `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: 无。
- Produces: `_parse_payload(data: object) -> tuple[str, list[str]]`；`starter_step` 非字符串、`steps` 非列表或含非字符串项一律抛 `ValueError`，由 `split()` 现有 except 走 fallback；列表截断到 5 条。

- [ ] **Step 1: 写失败测试**

```python
import pytest
from app.llm.openai_compat import _parse_payload

def test_parse_rejects_string_steps():
    with pytest.raises(ValueError):
        _parse_payload({"starter_step": "先打开资料", "steps": "打开资料"})

def test_parse_rejects_non_string_step_item():
    with pytest.raises(ValueError):
        _parse_payload({"starter_step": "先打开资料", "steps": ["打开资料", 1]})

def test_parse_truncates_to_five():
    starter, steps = _parse_payload(
        {"starter_step": "先打开资料", "steps": [f"步{i}" for i in range(7)]}
    )
    assert starter == "先打开资料"
    assert len(steps) == 5
```

- [ ] **Step 2:** 跑用例，预期 FAIL（`_parse_payload` 不存在）。
- [ ] **Step 3: 实现** 新增 `_parse_payload`（`isinstance` 三重校验 + `steps[:5]`）；`_call_llm` 改为 `starter, steps = _parse_payload(json.loads(content))`，不再 `str(s)` 逐字符转换。
- [ ] **Step 4: 验证** `pytest backend/tests/test_llm.py -q` + `pytest backend -q` 全绿（既有 fallback 用例继续覆盖异常路径）。
- [ ] **Step 5: Commit** `fix(backend): validate llm split payload types`

### Task 10: 空库自服务入口（FIX-11，P2 可选）

**Files:**
- Modify: `frontend/src/features/AccountSwitcher.tsx`

**Interfaces:**
- Consumes: `GET /api/users`（可为空）、`POST /dev/reset-seed`（根路径，非 `/api`）。
- Produces: `users.length === 0` 时显示「初始化演示数据」按钮；点击成功后重新拉取账号列表。

- [ ] **Step 1:** 抽出 `loadUsers = useCallback(async () => { ... }, [])`，`useEffect(() => { void loadUsers() }, [loadUsers])`。
- [ ] **Step 2:** 加 `resetting` 状态与 `handleResetSeed`：`await apiClient.post("/dev/reset-seed", null, { baseURL: "" })` 成功后 `await loadUsers()`；失败写入 `error`。
- [ ] **Step 3:** 渲染：`users.length === 0` 时显示提示 + `Button`（文案「初始化演示数据」，`disabled={resetting}`）。
- [ ] **Step 4: 验证** `npm run lint`、`npm run build`；浏览器：`TRUNCATE users, day_tasks, sessions, letters, action_logs, reflections RESTART IDENTITY CASCADE;` 后刷新 → 出现初始化按钮 → 点击后 3 个账号出现。
- [ ] **Step 5: Commit** `feat(frontend): seed entry for empty demo database`

### Task 11: 180 封顶与 discarded 文案浏览器复验（FIX-12）

**Files:**
- Modify: `docs/specs/003-f3-focus-session.md`（§8.3）

**Interfaces:**
- Consumes: Task 3/4 的前端行为、Task 6 的时钟注入。
- Produces: §8.3 未验证项标记为「已复验（日期）」，并记录实际观察结果。

- [ ] **Step 1:** 沙箱外启动后端（`python -m app.main`），环境变量 `SESSION_MIN_SECONDS=60`、`SESSION_MAX_SECONDS=120`；启动前端 `npm run dev`。
- [ ] **Step 2:** 有效开始后约 30 秒点结束 → 断言显示「还差 30 秒」且 2 秒后回首页、任务未锁定。
- [ ] **Step 3:** 重新开始并等待 120 秒 → 断言自动跳 `/settle`，库内该会话 `ended_at = started_at + 120s`、`duration_sec = 120`。
- [ ] **Step 4:** 回填 Spec 003 §8.3，区分「测试已编写」与「已人工复验」。
- [ ] **Step 5: Commit** `docs: backfill focus session browser verification`

---

## 不在本计划内（需人工确认 / 维持现状）

| 编号 | 处理 | 理由 |
|---|---|---|
| FIX-09 | 暂不实现 | 「首次输入即建草稿」与 Spec 002「仅输入不触发」冲突，属产品口径，需先确认；确认后单独排期。 |
| FIX-13 | 不实现唯一约束 | Demo 单客户端可接受；加约束需迁移并改变并发语义，属必须人工确认事项。 |

## 统一验收门槛

```powershell
# 后端（PostgreSQL 运行 + 沙箱外）
backend\.venv\Scripts\python.exe -m pytest backend -q

# 架构棘轮（无需 DB）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py

# 前端
cd frontend; npm run lint; npm run build

# 迁移漂移（本计划预期无迁移）
cd backend; .venv\Scripts\alembic.exe check
```
