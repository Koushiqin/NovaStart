# P3 · F3 专注计时与有效性实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。

**Goal:** 点「开始学习」→ 正计时（复用进行中会话、刷新/断网续算）→ 满 5 分钟服务端懒标记 + 界面一次性轻提示不跳转 → 点「结束」按 5–180 分钟判定：有效进结算、无效完全丢弃；180 分钟自动结束。

**Architecture:** 后端补 `POST /api/sessions/{id}/end`（唯一结束路径，判定与丢弃语义在 service 内闭合），修 `create_session` 复用 active 会话；懒标记沿用现有 `get_current_session`，补写 180 分钟时的 `duration_sec`。判定阈值收敛到 settings（演示加速 = 调阈值，不改时钟）。前端 FocusPage 实现正计时与里程碑提示。

**Tech Stack:** FastAPI + SQLAlchemy；React 18 + zustand + `useServerClock`；pytest（Clock 注入控时，禁止 sleep）。

**Spec:** [docs/specs/003-f3-focus-session.md](../../../docs/specs/003-f3-focus-session.md)（执行时从模板复制）。

**Depends on:** P2（`GET /api/tasks/today`、`POST /api/sessions {task_id}`、store `currentSessionId`、`/focus` 路由）。

**Produces（后续计划依赖的接口）:**
- `POST /api/sessions`：已存在 active 会话 → 200 返回原 `{session_id, started_at}`（不新建）。
- `POST /api/sessions/{id}/end` → `{result: "settled" | "discarded", duration_sec: int | null, short_by_sec: int | null, server_time}`；重复调用幂等返回相同结果。
- 会话语义（P4/P5/P6/P8 共用）：`status="completed"` = 有效待结算；`"discarded"` = 无效完全丢弃（`duration_sec` 为 NULL，不计任何统计）；归属日 = `started_at` 的 Asia/Shanghai 自然日。
- settings 新增 `session_min_seconds: int = 300`、`session_max_seconds: int = 10800`（演示加速只调这两个值）。

## Global Constraints

- 同 P1 全部；另：测试涉及时序必须注入/构造 `Clock(offset_seconds=...)`，禁止 sleep 墙钟；不支持暂停，不实现任何暂停入口。

## Review Focus

1. 重复点「开始」→ 不新建会话（Task 2 钉住：两次 POST 返回同一 session_id，库中 active 仅一条）。
2. 299 秒点结束 vs 300 秒点结束（边界）→ 前者 discarded 且 `duration_sec` 为 NULL，后者 settled（Task 2 钉住）。
3. 刷新/断网后回到页面 → 以服务端 `started_at` 续算，已跨 5 分钟则直接显示已完成态（Task 2 懒标记测试 + Task 4 手工验证）。
4. 超 180 分钟 → 懒标记补 `ended_at = started_at + max`、`duration_sec = 10800`，界面自动去结算（Task 2 钉住）。
5. 客户端改系统时间不得影响判定（前端只用 `useServerClock`，Task 3 grep 检查无 `new Date()` 直取）。

---

### Task 1: 写 Spec 003

- [ ] **Step 1:** 从模板复制填写：范围=F3 规则与第 5 节计时与中断（含 A12/A16/A17/A18）；非目标=星星/连续天数计算（P5）、结算页 UI（P4）；验收条件对应演示验收与 Review Focus；第 6 节写明 end 端点新增、create 行为变化（复用）、settings 两个阈值键。
- [ ] **Step 2: Commit** `docs: spec 003 f3 focus session`

### Task 2: 后端 end 端点 + 复用 + 阈值配置

**Files:**
- Modify: `backend/app/services/session_service.py`、`backend/app/routers/session.py`、`backend/app/schemas/session.py`、`backend/app/config.py`
- Test: `backend/tests/test_session_api.py`（扩写）、新建 `backend/tests/test_session_end.py`

**Interfaces:**
- Consumes: P2 的会话创建流程；`get_clock`。
- Produces: 本计划头部 Produces；`session_service.end_session(db, session_id, user_id, clock) -> tuple[str, int | None]`（`("settled", duration)` / `("discarded", short_by)`，session 不存在或不属于该用户 → None）。

- [ ] **Step 1: 写失败测试**

```python
async def test_duplicate_start_reuses_active(client): ...       # 两次 POST /sessions 同 id，active 仅 1
async def test_end_before_min_discarded(client): ...            # Clock 注入 299s → discarded, duration NULL
async def test_end_at_min_settled(client): ...                  # 300s → settled, duration_sec=300
async def test_discarded_writes_no_duration(client): ...        # 库内 duration_sec is NULL, status="discarded"
async def test_end_over_max_capped(client): ...                 # 3h+ → duration_sec==10800
async def test_lazy_180_marks_and_fills_duration(client): ...   # GET /current 在 180 后 → completed + duration 10800
async def test_repeat_end_idempotent(client): ...               # 两次 end 结果一致，duration 不变
async def test_end_other_users_session_404(client): ...         # 跨账号 → 404
```

- [ ] **Step 2:** 跑确认 FAIL（沙箱外）。
- [ ] **Step 3:** `config.py` 加两个阈值；`session_service` 常量改读 settings（经参数或模块级 `settings`，与现有风格一致）；`create_session` 先查 active 复用；实现 `end_session`：<min → `status="discarded"`（`ended_at`/`duration_sec` 保持 NULL）；≥min → `duration_sec = min(elapsed, max)`、`ended_at = started_at + duration`、status 置 `"completed"`；懒标记 180 分支补写 `duration_sec`。
- [ ] **Step 4:** 测试全 PASS + 棘轮 + 全量回归。
- [ ] **Step 5: Commit** `feat(backend): session end with validity rules and active reuse`

### Task 3: FocusPage 正计时与里程碑

**Files:**
- Modify: `frontend/src/pages/FocusPage.tsx`、`frontend/src/store/app.ts`（如需）
- Create: `frontend/src/features/focus/FocusTimer.tsx`、`MilestoneBanner.tsx`

**Interfaces:**
- Consumes: `GET /api/sessions/current`、`POST /api/sessions/{id}/end`、`GET /api/tasks/today`；store `currentSessionId`；`useServerClock`。
- Produces: 结束有效 → `navigate("/settle")`（P4 在此页面继续）；无效 → 提示差额后 `navigate("/")`。

- [ ] **Step 1:** 挂载时 `GET /sessions/current`：无会话 → 回首页；有 → 以 `started_at` + `useServerClock` 起表，1s interval 渲染 `mm:ss`。
- [ ] **Step 2:** 每 15s 轮询 `/current` 校正并触发懒标记；`status` 变为 `completed` 且未提示过 → `MilestoneBanner`（「已经 5 分钟，随时可以结束，也可以继续」+ 背景调亮，一次性，不重复弹）。
- [ ] **Step 3:** 「结束」按钮 → end 接口：`settled` → 跳 `/settle`；`discarded` → 显示「还差 X 分 X 秒」2 秒后回首页；轮询发现 `ended_at` 已写（180 封顶）→ 自动跳 `/settle`。
- [ ] **Step 4:** 任务文案来自 `GET /tasks/today` 的当前采用版 starter（页面顶部展示）。
- [ ] **Step 5:** `Grep "new Date\(" frontend/src/pages frontend/src/features` 确认无绕开 `useServerClock` 的取时（`useServerClock.ts` 自身除外）；`npm run lint` + `npm run build` 通过。
- [ ] **Step 6: Commit** `feat(frontend): focus timer with one-time milestone prompt`

### Task 4: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启；用 `session_min_seconds=60` 的演示配置走演示验收：开始→计时上走→到点轻提示不跳转→结束进结算；另起一场 <60s 结束 → 提示差额且首页无累计；刷新页面计时续算。
- [ ] **Step 2:** 全量后端测试 + 棘轮 + lint/build。
- [ ] **Step 3:** 回填 Spec 第 8 节。
- [ ] **Step 4: Commit** `docs: backfill spec 003 results`
