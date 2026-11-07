# P1 · F9 多账号与请求头 userId 实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。执行前先读 [dev-order.md](../../../docs/dev-order.md) 与 [dev-pitfalls.md](../../../docs/dev-pitfalls.md)。

**Goal:** 三个固定演示账号（小明/小美/小刚）可在页面顶部切换，所有 `/api` 请求经 `X-User-Id` 请求头单点注入身份，切换后首页/记录/信箱数据整体切换。

**Architecture:** 后端新增 `app/deps.py` 提供 `get_current_user_id`（FastAPI Header 依赖，单点收敛，校验账号存在）；各 router 删除 body/query 里的 `user_id`，改用该依赖。前端 axios 请求拦截器从 zustand（persist 到 localStorage）注入请求头；`AccountSwitcher` 挂在 App 根部。种子数据扩为 3 账号：小明 6 天历史、小美 1 条历史（信件预置留待 P6）。演示时间旅行走 env 偏移。

**Tech Stack:** FastAPI Header 依赖、zustand persist、pytest + httpx（API 测试）、Alembic（本计划无表结构变更）。

**Spec:** 执行时先建 [docs/specs/001-f9-multi-account.md](../../../docs/specs/001-f9-multi-account.md)（从 [spec-template.md](../../../docs/spec-template.md) 复制），Spec 与计划同改同提交。

**Depends on:** 无（dev-order 第 1 位）。

**Produces（后续计划依赖的接口）:**
- 所有 `/api/*` 请求必须带 `X-User-Id: <int>`；缺失 → 422；账号不存在 → 404 `{code, message}`。
- `GET /api/users` → `{users: [{id, name}], server_time}`（无需请求头）。
- `app/clock.py` 提供 `get_clock() -> Clock` 依赖（读 `settings.demo_time_offset_seconds`），所有 router 经 `Depends(get_clock)` 取时钟。
- 前端 `apiClient` 自动注入请求头；store `userId` 持久化（localStorage key `novastart-user`）。

## Global Constraints

- 测试库只允许 `novastart_test`；连库命令（pytest/alembic/psql/uvicorn）必须 `dangerouslyDisableSandbox: true`。
- 后端时间只用 `Clock`/`get_clock`；前端时间只用 `useServerClock`；HTTP 只走 `api/client.ts`。
- 后端启动只用 `python -m app.main`；改模型必须配 Alembic 迁移。
- 前端验收基线：`npm run lint` = 0 error + 仅 button.tsx 1 warning；`npm run build` 通过。
- 棘轮随时可跑：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py`。
- 错误契约：稳定 `code` + 人话 `message`，前端只展示不推断。

## Review Focus

1. 缺 `X-User-Id` 头的请求 → 必须 422 而非 500（Task 2 钉住）。
2. 请求头指向不存在账号 → 统一 404，不得落库半截数据（Task 2 钉住）。
3. 切换账号后不得看到上一账号的进行中 session / 任务（Task 2 隔离测试 + Task 5 端到端）。
4. 刷新浏览器后账号不得掉回默认（persist，Task 4 手工验证）。
5. 旧 body/query `user_id` 残留造成双写入口（Task 2 全量删干净，Grep 验证）。

---

### Task 1: 写 Spec 001

**Files:**
- Create: `docs/specs/001-f9-multi-account.md`（从 `docs/specs/spec-template.md` 复制）

- [ ] **Step 1:** 按模板填：目标=上述 Goal；范围含「请求头改造、账号切换 UI、种子扩 3 账号、demo 时间偏移」；非目标含「真实鉴权、注册登录、信件预置（归 P6）、时间加速（归 P3 阈值配置）」；验收条件 5 条对应 Review Focus；第 6 节写明 `TaskCreate/SessionCreate` 删 `user_id` 字段、GET 接口删 `user_id` query（破坏性契约变更，属内部 Demo 接口，已在 AGENTS 流程内确认）。
- [ ] **Step 2: Commit** `docs: spec 001 f9 multi-account`

### Task 2: 后端请求头身份 + users 接口 + 种子 3 账号

**Files:**
- Create: `backend/app/deps.py`、`backend/app/routers/user.py`、`backend/app/schemas/user.py`、`backend/tests/test_user_header.py`
- Modify: `backend/app/routers/task.py`、`session.py`、`letter.py`、`settle.py`、`backend/app/schemas/task.py`、`session.py`、`backend/app/main.py`、`backend/app/seed.py`

**Interfaces:**
- Consumes: 无（首个计划）。
- Produces: `get_current_user_id(x_user_id: int = Header(...)) -> int`（账号不存在抛 404 `{code:"USER_NOT_FOUND"}`）；`GET /api/users`；所有业务 router 签名里的 `user_id` 形参全部改由此依赖注入。

- [ ] **Step 1: 写失败测试** `backend/tests/test_user_header.py`

```python
async def test_missing_header_422(client):  # POST /api/tasks 无 X-User-Id
    r = await client.post("/api/tasks", json={"raw_text": "背单词"})
    assert r.status_code == 422

async def test_unknown_user_404(client):  # X-User-Id: 9999
    assert (await client.post("/api/tasks", json={"raw_text": "x"}, headers={"X-User-Id": "9999"})).status_code == 404

async def test_users_endpoint_returns_seed_accounts(client):  # reset 后 3 个指定名字
    names = [u["name"] for u in (await client.get("/api/users")).json()["users"]]
    assert names == ["小明", "小美", "小刚"]

async def test_data_isolated_by_header(client):  # 两个账号各建任务，today 查询互不可见
    ...
```

- [ ] **Step 2:** 跑 `cd backend; .venv\Scripts\python.exe -m pytest tests/test_user_header.py -v`（沙箱外），确认全 FAIL。
- [ ] **Step 3:** 实现 `deps.py`（Header 解析 + `select(User)` 存在性校验 + 404 错误契约）、`routers/user.py`（`GET /api/users` 按 id 升序返回）、`schemas/user.py`；改造 4 个现有 router 与 2 个 schema 删 `user_id`；`main.py` 注册 user router；`seed.py` 改为 3 账号（小明=6 天历史，小美=1 天历史，小刚=空），`_DEMO_TOPICS` 相应调整。
- [ ] **Step 4:** 跑该测试文件 + 既有 `test_session_api.py`、`test_letter_settle.py`（它们需同步改为带请求头——允许在本任务内修测试调用方式，不改断言语义），全 PASS；跑棘轮。
- [ ] **Step 5:** `Grep "user_id" backend/app/routers backend/app/schemas` 确认无 body/query 残留。
- [ ] **Step 6: Commit** `feat(backend): X-User-Id header identity, users endpoint, 3-account seed`

### Task 3: 演示时间偏移（时间旅行）

**Files:**
- Modify: `backend/app/config.py`、`backend/app/clock.py`、4 个 router 的 `Clock()` 调用点
- Test: `backend/tests/test_clock.py`

**Interfaces:**
- Produces: `settings.demo_time_offset_seconds: int = 0`；`get_clock() -> Clock`（每次请求构造 `Clock(offset_seconds=settings.demo_time_offset_seconds)`）。

- [ ] **Step 1: 写失败测试** — `test_get_clock_applies_settings_offset`：monkeypatch settings 偏移 -86400，`get_clock().today()` 比 `Clock().today()` 早一天。
- [ ] **Step 2:** 跑测试确认 FAIL。
- [ ] **Step 3:** `config.py` 加字段；`clock.py` 加 `get_clock()`（依赖注入函数放 clock 模块内，不新建文件）；router 全部改 `clock: Clock = Depends(get_clock)`；service 签名不变（已接收 clock 参数）。
- [ ] **Step 4:** 全量后端测试 PASS + 棘轮。
- [ ] **Step 5: Commit** `feat(backend): demo time offset via get_clock dependency`

### Task 4: 前端请求头注入 + 账号切换

**Files:**
- Modify: `frontend/src/api/client.ts`、`frontend/src/store/app.ts`、`frontend/src/App.tsx`、`frontend/src/features/SmokePanel.tsx`
- Create: `frontend/src/features/AccountSwitcher.tsx`

**Interfaces:**
- Consumes: Task 2 的 `GET /api/users` 与请求头契约。
- Produces: `apiClient` 请求拦截器（后续所有计划静默继承）；store `userId` 持久化；`AccountSwitcher` 组件（P2 起留在 App 根部）。

- [ ] **Step 1:** `client.ts` 加请求拦截器：`const id = useAppStore.getState().userId; if (id != null) config.headers["X-User-Id"] = String(id)`。
- [ ] **Step 2:** `store/app.ts` 用 `persist(..., { name: "novastart-user", partialize: ({userId}) => ({userId}) })` 只持久化 userId。
- [ ] **Step 3:** `AccountSwitcher`：挂载时 `apiClient.get("/users")` 拉账号列表，渲染三个按钮，选中态高亮，点击 `setUserId`；`App.tsx` 在 `<Routes>` 上方渲染。
- [ ] **Step 4:** `SmokePanel` 删掉 payload 里的 `user_id` 字段（保持其余调试能力，P2 会整体替换首页）。
- [ ] **Step 5:** `npm run lint`（0 error + 1 既有 warning）与 `npm run build` 通过。
- [ ] **Step 6: Commit** `feat(frontend): header injection, persisted account switcher`

### Task 5: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启（PG 经 WMI、`python -m app.main`、`npm run dev`），`POST /dev/reset-seed` 后走 demo 验收：切小明 → SmokePanel 数据为小明的；切小美 → 数据整体切换；刷新页面账号保持。
- [ ] **Step 2:** 跑全量后端测试 + 棘轮 + lint/build，结果截图/日志留存。
- [ ] **Step 3:** 回填 Spec 第 8 节（区分「已编写」与「已运行通过」）。
- [ ] **Step 4: Commit** `docs: backfill spec 001 results`
