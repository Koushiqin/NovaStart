# 003 · F3 专注计时与有效性

> 来源：[brainstorming.md](../../brainstorming.md) F3、第 4 节（R2–R7）、第 5 节计时与中断、第 6 节异常兜底、第 7 节会话状态机、A12/A16/A17/A18；执行计划：[2026-11-07-p3-f3-focus-session.md](../superpowers/plans/2026-11-07-p3-f3-focus-session.md)。前置 Spec：[002 · F1+F2 今日任务与模型拆分](./002-f1-f2-today-task.md)。

## 1. 背景与目标

P2 已完成「输入 → 分析 → 开始学习」链路：`POST /api/sessions` 能建会话，`GET /api/sessions/current` 已做 5 分钟懒标记，但三者都不到位：

- `create_session` 每次都新建，重复点开始会产生多条 active 会话；
- 没有显式结束入口，`duration_sec` 永远不会写入，P4 结算无从取数；
- 懒标记在 180 分钟分支只写 `status` 与 `ended_at`，不补 `duration_sec`；
- 5 分钟阈值写死在 service 常量里，演示加速只能改代码；
- 前端 `/focus` 仍是占位页，没有正计时、里程碑提示与结束入口。

目标：把 F3 做成一条完整可演示的闭环——点「开始学习」进入专注页 → 只显示正计时（复用进行中会话，刷新/断网按服务端时间续算）→ 满 5 分钟服务端懒标记完成且界面一次性轻提示、不跳转、不停表 → 点「结束」按 5–180 分钟判定：有效进入结算流程、无效完全丢弃；180 分钟自动结束。

## 2. 范围与非目标

- 范围：
  - **正计时**：`started_at` 是唯一起点；界面时间由「服务端当前时间 − started_at」得出；不支持暂停，不提供暂停入口。
  - **重复开始复用**：同一账号已有「进行中会话」（`status ∈ {active, completed}` 且 `ended_at IS NULL`）时，`POST /api/sessions` 返回原会话，不新建。
  - **5 分钟里程碑**：服务端懒标记（任何请求按 `started_at` 求差补算），完成时刻记为 `started_at + min`，不改写 `started_at`；界面一次性提示「已经 5 分钟，随时可以结束，也可以继续」+ 背景变亮，不跳转、不停表。
  - **结束判定**：新增 `POST /api/sessions/{id}/end`，唯一结束路径；`elapsed < min` → `status="discarded"`、时长不写库；`elapsed ≥ min` → `status="completed"`、`duration_sec = min(elapsed, max)`、`ended_at = started_at + duration_sec`。
  - **180 分钟自动结束**：懒标记与显式结束共用同一封顶规则；前端轮询发现 `ended_at` 已写（且非本页主动结束）→ 自动跳 `/settle`。
  - **刷新 / 断网续算**：回到专注页一律以 `GET /api/sessions/current` 的 `started_at` 重新起表，不依赖前端本地计时状态。
  - **阈值可配置**：`session_min_seconds` / `session_max_seconds` 收敛到 settings，演示加速只调配置、不改时钟也不改代码。
- 非目标（明确不做的）：
  - 星星点亮、亮度分级（5/15/25 分钟）、连续天数计算与断签归零（F7 / P5）。
  - 结算页 UI 与四步流程（写感想 / 投递 / 处理信箱 / 随机回顾）、`settle_step` 推进（F4 / P4）。
  - 感想、信件、记录查询、随机回顾（F5/F6/F8/F10）。
  - 倒计时、暂停、手动加减时长、离开惩罚（F3 明确不做）。
  - 多标签页 / 多客户端并发抢同一会话的强一致保证（Demo 单客户端；service 保持单写入路径）。
  - 历史会话列表与跨场次统计展示（P4/P8）。
  - 里程碑文案随演示阈值动态改写（阈值配置只影响判定与提示时机，「5 分钟」文案按产品口径保留，见 §8.3）。

## 3. 可测试的验收条件

1. 同一账号对同一任务连续两次 `POST /api/sessions`：两次均 `200`，`session_id` 与 `started_at` 相同；库中该账号 `status ∈ {active, completed} AND ended_at IS NULL` 的会话仅 1 条。
2. 账号已有进行中会话（含已达成 5 分钟但未结束的 `completed` 会话）时，`POST /api/sessions` 仍返回该会话，不新建。
3. 专注页挂载 `GET /api/sessions/current`：有进行中会话 → 以 `started_at` + `useServerClock` 渲染正计时，数值随时间递增；无会话 → 回首页；账号未选 → 提示选账号，不发业务请求。
4. 刷新 / 断网后重新进入 `/focus`：计时从服务端 `started_at` 续算而非归零；已跨 5 分钟时直接显示「已完成」状态（里程碑提示每次进入最多一次）。
5. 进行中会话在 299 秒时 `GET /api/sessions/current` → `status="active"`；到 300 秒 → `status="completed"`，且 `ended_at`、`duration_sec` 仍为 `null`（计时继续）。
6. 前端轮询观察到 `status` 由 `active` 变为 `completed` → 展示 `MilestoneBanner` 一次，不跳转、不停表；同一页面生命周期内轮询不重复弹。
7. 299 秒点「结束」→ `result="discarded"`、`duration_sec=null`、`short_by_sec=1`；库中该会话 `status="discarded"`、`ended_at` 与 `duration_sec` 均为 `NULL`。
8. 300 秒点「结束」→ `result="settled"`、`duration_sec=300`；库中 `status="completed"`、`ended_at=started_at+300s`。
9. 超过 180 分钟点「结束」→ `duration_sec=10800`、`ended_at=started_at+10800s`，不按实际超长时长写库。
10. 进行中会话超过 180 分钟时任意请求触发懒标记 → `status="completed"`、`ended_at=started_at+max`、`duration_sec=max`；前端轮询看到 `ended_at` 后自动跳 `/settle`。
11. 重复调用 `POST /api/sessions/{id}/end`：结果与首次一致（`discarded` 仍 `discarded` 且 `duration_sec=null`，`settled` 仍 `settled` 且 `duration_sec` 不变），库中字段不被二次改写。
12. 结束他人会话或不存在的会话 → `404`，`detail.code="SESSION_NOT_FOUND"`，库中无任何变化。
13. 有效结束 → 前端跳 `/settle`；无效结束 → 展示「还差 X 分 X 秒」（由 `short_by_sec` 换算），2 秒后回首页，首页当天数据无新增累计（P5 实现统计后仍成立）。
14. 演示阈值 `session_min_seconds=60`：59 秒结束 → `discarded`，60 秒结束 → `settled`；到 60 秒触发里程碑提示。改配置不改代码即可生效。
15. 判定不受客户端时钟影响：后端只用 `Clock`；前端 `pages/` 与 `features/` 中除 `useServerClock.ts` 外无 `new Date(` 直取当前时间；15 秒轮询持续用 `server_time` 校正偏移。
16. 跨零点：23:58 开始、00:03 触发懒标记 → `status="completed"`，`started_at` 不变；归属日仍由 `started_at` 的 Asia/Shanghai 自然日决定（P3 只标记状态，归属日统计由 P5 消费）。
17. 专注页只展示任务文案、正计时与「结束」一个操作入口，不存在暂停按钮或暂停 API。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：session 状态的唯一真相源仍是 PostgreSQL `sessions` 表；「当前时间」仍是后端 `Clock`；前端身份仍是 zustand `userId`。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/config.py` | settings owner | 新增 `session_min_seconds: int = 300`、`session_max_seconds: int = 10800` |
| `backend/app/services/session_service.py` | 会话规则与事务边界 owner | `create_session` 先复用进行中会话；新增 `end_session`；懒标记补 180 分钟分支的 `duration_sec`；阈值改读 settings |
| `backend/app/schemas/session.py` | API 契约唯一真相源 | 新增 `SessionEnded`；`SessionInfo` 增加 `ended_at` 与 `task_starter_step` |
| `backend/app/routers/session.py` | HTTP 解析与转发 | 新增 `POST /{id}/end`；不写判定规则 |
| `backend/tests/test_session_end.py`（新增） | 结束与阈值规则测试 | 覆盖第 3 节 1–2、7–12、14–16 的接口侧 |
| `backend/tests/test_session_api.py` | 既有回归 | 扩展懒标记/复用断言，保持原有语义 |
| `frontend/src/pages/FocusPage.tsx` | 专注页路由页 | 从占位页改为计时页：拉取 current、轮询、结束、跳转 |
| `frontend/src/features/focus/FocusTimer.tsx`（新增） | 正计时展示 | 新建理由：把派生计时与 `mm:ss` 渲染隔离，便于页面与里程碑组件复用；纯展示无业务判定 |
| `frontend/src/features/focus/MilestoneBanner.tsx`（新增） | 一次性里程碑提示 | 新建理由：提示的显示/隐藏与页面生命周期分离，避免页面逻辑被一次性状态撑大 |
| `frontend/src/store/app.ts` | 前端身份 / 会话状态 owner | 不改；`currentSessionId` 保留持久化，但专注页以 `GET /current` 为权威 |
| `frontend/src/hooks/useServerClock.ts`、`api/client.ts` | 唯一时间 / HTTP 入口 | 不改，复用 |

## 5. 实现步骤

按 [dev-order.md](../dev-order.md) 六步流水线，Task 1 只完成第 0 步（Spec），其余由后续任务执行：

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：`schemas/session.py` 增加 `SessionEnded` 与 `SessionInfo.ended_at/task_starter_step`；`config.py` 增加两个阈值键。无 ORM 字段变化。
3. **迁移（六步②）**：无迁移——`sessions.ended_at` / `duration_sec` / `status` 均已存在（见 `models/session.py`）；本步只需确认 `alembic check` 无漂移。
4. **业务（六步③）**：先写 `tests/test_session_end.py` 失败用例（第 7 节），确认 FAIL；实现 `session_service` 的复用、`end_session`、180 分钟懒标记补时长；阈值每次判定读 settings（不在模块导入时冻结）。再修 `test_session_api.py` 回归。
5. **接口（六步④）**：`routers/session.py` 新增 end 端点，仅解析/转发/错误映射；`/docs` 与 curl 冒烟。响应带 `server_time`。
6. **前端（六步⑤）**：`FocusPage` + `FocusTimer` + `MilestoneBanner`；挂载拉 current、15 秒轮询、结束跳转、180 自动跳转；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启，用 `SESSION_MIN_SECONDS=60` 演示配置走完开始 → 计时 → 里程碑 → 有效/无效结束 → 刷新续算；再验一次 180 封顶（可把 max 调小临时验证）。
8. 回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 契约

#### `POST /api/sessions`

- 请求：`SessionCreate {task_id}`；身份仍由 `X-User-Id` 注入。
- 复用规则：该账号已有**进行中会话**（`status ∈ {active, completed}` 且 `ended_at IS NULL`）→ `200` 返回该会话（取 `started_at` 最新的一条），**忽略本次请求的 task_id**；否则新建 `status="active"` → `200`。
- 响应不变：`{session_id, started_at, server_time}`。
- `discarded` / `settled` / 已写 `ended_at` 的 `completed` 会话不阻塞新会话创建。
- 「进行中」判定与 `GET /current` 的「当前会话」口径分开：前者排除已写 `ended_at` 的会话，后者仍返回最新 `active/completed`（供前端检测「已结束待结算」并跳转）。

#### `POST /api/sessions/{id}/end`

- 请求：无 body；身份由 `X-User-Id` 注入。
- 响应 `SessionEnded`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `result` | `"settled"` \| `"discarded"` | `settled` = 本场有效、进入结算流程；`discarded` = 本场无效、完全丢弃 |
| `duration_sec` | int \| null | 有效时写入的最终时长（≤ `session_max_seconds`）；无效为 `null` |
| `short_by_sec` | int \| null | 无效时还差多少秒达到最短时长；有效为 `null` |
| `server_time` | str | 服务端当前时间 |

- 判定（service 内闭合）：
  1. 会话不存在或不属于当前账号 → `404 {"detail": {"code": "SESSION_NOT_FOUND", "message": "会话不存在"}}`。
  2. `status="discarded"`：幂等返回 `result="discarded"`、`duration_sec=null`；`short_by_sec` 按当前时刻重算并下限截 0（仅信息性，库中不二次写入）。
  3. `ended_at` 已写（含 `completed` 已结束、P4 的 `settled`）：幂等返回 `result="settled"`、`duration_sec` 取库中值。
  4. 否则（`active`，或 5 分钟懒标记后的 `completed` 但未写 `ended_at`）：
     - `elapsed = max(0, now - started_at)`；
     - `elapsed < session_min_seconds` → `status="discarded"`，`ended_at` / `duration_sec` 保持 `NULL`，返回 `short_by_sec = min - elapsed`；
     - `elapsed ≥ session_min_seconds` → `duration_sec = min(elapsed, session_max_seconds)`、`ended_at = started_at + duration_sec`、`status="completed"`，返回 `result="settled"`。
- **命名说明**：API 的 `result="settled"` 只表示「有效、可进结算页」；库内状态 `completed` = 有效待结算，`settled` = 结算完成。唯一迁移入口是 `settle_service.advance`：`to_step=4` 时同事务写 `status="settled"`；重复调用保持 step 4 与 `settled`。两套词义不得混用：后端状态机以 §6.4 为准。

#### `GET /api/sessions/current`

- 响应 `{session: SessionInfo | null, server_time, session_max_seconds}`；`SessionInfo` 在原有 `id` / `started_at` / `elapsed_sec` / `status` 上增加：

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_max_seconds` | int | 服务端最长时长（顶层字段，非会话字段）；前端据 `started_at + session_max_seconds` 在封顶时刻立即补一次请求触发懒结束，并按它截断计时展示 |
| `ended_at` | str \| null | 已结束（显式结束或 180 封顶）时的时间；5 分钟里程碑只置 `completed` 不写此值 |
| `task_starter_step` | str \| null | 本场任务当前采用版 starter，供专注页展示；任务缺失时为 `null` |

- `elapsed_sec` 保持现有口径：`max(0, now - started_at)` 的整数秒，不封顶（180 后前端据 `ended_at` 跳转）。
- 懒标记：
  - `ended_at IS NULL` 且 `elapsed ≥ max` → `status="completed"`、`ended_at = started_at + max`、`duration_sec = max`（对已置 `completed` 但未结束的会话同样生效，保证 5 分钟达成后继续学习到 180 分钟仍能自动结束）；
  - 否则 `active` 且 `elapsed ≥ min` → `status="completed"`，不写 `ended_at` / `duration_sec`。

### 6.2 数据与迁移

- **无迁移**：`sessions.ended_at`（可空 timestamptz）、`duration_sec`（可空 int）、`status String(20)` 已存在。
- 不新增列、不改可空性、不加唯一约束（「同日唯一」不适用于 session；同账号进行中唯一由 service 先查后复用保证，Demo 单客户端）。
- 无效场次保留会话行（`status="discarded"`，`duration_sec` / `ended_at` 为 `NULL`），以保证重复结束幂等；「完全丢弃」指不计任何统计（时长、累计、亮度、投递、连续天数），且不锁定当天任务——首页仍可重新开始，再开一场（`task_service._has_any_session` 排除 `discarded`）。
- 归属日不落列：由 `started_at` 的 Asia/Shanghai 自然日派生，P5 统计时消费。

### 6.3 兼容性与配置

- **行为变化（内部 Demo 接口）**：`POST /api/sessions` 由「每次新建」改为「有进行中会话则复用」。P2 前端在 `locked` 时已直接跳 `/focus`，正常 UI 不重复 POST；直接调 API / 跨零点回到首页时会得到同一会话而不是新会话。
- **契约增量**：`SessionInfo` 新增 `ended_at` 与 `task_starter_step`；`POST /{id}/end` 为新增端点。无删除字段，前端 TS 类型跟随更新。
- settings 新增 `session_min_seconds: int = 300`、`session_max_seconds: int = 10800`，默认值与现有常量等价；演示加速通过环境变量 `SESSION_MIN_SECONDS` / `SESSION_MAX_SECONDS` 覆盖，不新增启动方式。
- `server_time` 仍由 `Clock`（`Depends(get_clock)`）产出；前端只经 `api/client.ts` 与 `hooks/useServerClock.ts` 取时间。
- 前端 store 不变；专注页不以持久化的 `currentSessionId` 作判定依据。

### 6.4 会话语义（P4/P5/P6/P8 共用）

| 状态 | 含义 | 必须成立 |
|---|---|---|
| `active` | 进行中，未达最短时长 | `ended_at` / `duration_sec` 为 `NULL` |
| `completed` | 有效待结算 | 已达 `min`；已结束时 `duration_sec` 有值且 `ended_at = started_at + duration_sec` |
| `settled` | P4 结算流程已完成 | `duration_sec` 保持，不再改写 |
| `discarded` | 无效，完全丢弃 | `ended_at` / `duration_sec` 为 `NULL`；不计任何统计 |

- 状态迁移：`completed` --(settle_step 达 4)--> `settled`；`advance` 是唯一迁移入口，重复调用保持 4 不回退。
- 归属日 = `started_at` 的 Asia/Shanghai 自然日；跨零点继续学习不改变归属日。
- 归属日 SQL 口径：一律写 `cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`（等价 `started_at AT TIME ZONE 'Asia/Shanghai'`），禁止裸 `cast(started_at, Date)`——PostgreSQL 容器默认 UTC，会让 0–8 点场次落到前一天。
- 一天多场：每场独立；只有 `completed` / `settled` 场次参与累计与亮度，`discarded` 不参与。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（`backend/tests/test_session_end.py`；时序一律注入 `Clock(offset_seconds=...)` 或 `get_clock` override，禁止 sleep）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1、2 | `test_duplicate_start_reuses_active` | 两次 `POST /sessions` 同 `session_id` / `started_at`；库中进行中仅 1 条 |
| 2 | `test_start_reuses_completed_without_end` | 5 分钟懒标记后（`completed`、`ended_at=NULL`）再 POST → 同 `session_id` |
| 5 | `test_lazy_min_marks_completed_without_ending` | 299s `active`；300s `completed`；`ended_at` / `duration_sec` 仍 `NULL` |
| 7 | `test_end_before_min_discarded` | 299s → `result="discarded"`、`duration_sec=null`、`short_by_sec=1` |
| 7 | `test_discarded_writes_no_duration` | 库内 `status="discarded"`、`ended_at IS NULL`、`duration_sec IS NULL` |
| 8 | `test_end_at_min_settled` | 300s → `result="settled"`、`duration_sec=300`、`ended_at=started+300` |
| 9 | `test_end_over_max_capped` | 3h+ → `duration_sec==10800` |
| 10 | `test_lazy_180_marks_and_fills_duration` | `GET /current` 在 180 后 → `completed` + `duration_sec=10800` + `ended_at` 有值 |
| 11 | `test_repeat_end_idempotent` | 两次 end 的 `result` 与 `duration_sec` 一致，库内字段不变；discarded 重复调用仍 `discarded` |
| 12 | `test_end_other_users_session_404` | 跨账号 → `404 SESSION_NOT_FOUND` |
| 14 | `test_thresholds_come_from_settings` | monkeypatch 阈值后 59/60s 判定随之变化 |
| 3、6、10、13 | 前端 | lint + build；浏览器端到端由 Task 4 覆盖 |
| 15 | `test_architecture.py` + Grep | 后端 `datetime.now(` 仅 `clock.py`；前端 `new Date(` 仅允许 `useServerClock.ts` / `api/client.ts` |
| 16 | `test_lazy_uses_started_at_across_midnight` | 跨零点只改 `status`，`started_at` 不变（归属日由 `started_at` 派生） |

验证命令：

```powershell
# 新增 session 测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_session_end.py -q

# 后端全量 + 架构棘轮
cd backend; .venv\Scripts\python.exe -m pytest -q

# 迁移漂移确认（无新迁移）
cd backend; .venv\Scripts\alembic.exe check

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

（Task 4 完成后已回填，2026-11-07。）

### 8.1 已运行通过

| 验证 | 命令 / 场景 | 结果 |
|---|---|---|
| 后端全量 | `cd backend; .venv\Scripts\python.exe -m pytest -q` | 102 passed in 10.40s（含 `test_architecture.py` 棘轮） |
| 迁移漂移 | `cd backend; .venv\Scripts\alembic.exe check` | No new upgrade operations detected |
| 前端 lint | `cd frontend; npm run lint` | 0 error（仅既有 `components/ui/button.tsx` react-refresh warning） |
| 前端构建 | `cd frontend; npm run build` | 126 modules，built in 1.09s |
| 取时棘轮 | Grep `new Date(`（`frontend/src`） | 仅 `api/client.ts` 与 `hooks/useServerClock.ts` |
| E2E 演示 A（小刚，既有 `completed` 未结束会话） | 三服务同启 + `SESSION_MIN_SECONDS=60`：进入 `/focus` | 首屏即完成态：计时 42:xx、`已经 5 分钟…` 横幅显示、URL 保持 `/focus`；点结束 → `/settle`；库中 `completed`、`duration_sec=2567`（实际时长，≥ min） |
| E2E 演示 B（小明，新任务） | 开始学习 → 计时 → 里程碑 → 结束 | 计时从 00:2x 递增；约 80s 后横幅出现且 URL 保持 `/focus`、计时继续（00:59 → 01:11）；结束 → `/settle`；库中 `completed`、`duration_sec=78` |
| E2E 演示 C（小美，刷新续算 + 无效结束） | 开始 → 真实重载 → 60s 内结束 | 重载后计时 00:28（未归零）；结束 → 库中 `discarded`、`ended_at` / `duration_sec` 均为 `NULL`；界面约 2s 后回首页 |

### 8.2 验证中发现并修复的问题

- **账号切换的在途响应**：`FocusPage` 的 15s 轮询与结束回调此前只查 `leavingRef`，切账号瞬间可能用上一账号的会话/跳转覆盖新账号视图。已在两处回调比对 `useAppStore.getState().userId` 丢弃过期响应，并清理无效结束的 2 秒回首页定时器（`FocusPage.tsx`；前端无测试框架，修复以 lint + build + 端到端复验为准）。
- **无效结束后任务被锁死**：`task_service._has_any_session` 把 `discarded` 也算「已有会话」，首页只显示「进入专注」，而 `/current` 无会话会立刻弹回首页，形成死循环、当天无法重开。改为排除 `discarded`（完全丢弃不应影响任何后续入口），新增 `test_discard_unlocks_task_for_retry` RED→GREEN；§6.2 已补该口径。
- **无效结束后的按钮状态**：`discarded` 分支立即复位 `ending`，2 秒差额提示期间按钮禁用并显示「已结束」，不再停留在「结束中…」。
- **180 封顶不再等轮询**：`GET /current` 新增顶层 `session_max_seconds`；专注页本地计时一到上限就立即补一次请求触发服务端懒结束（`capTriggeredRef` 防重复，失败时下一秒重试），并把展示时长按上限截断，避免超过 180:00；15 秒轮询仍作兜底。
- E2E 为重复演示同一账号，期间删除了本轮创建的 `discarded` 会话行（两行）；无效场次本就不计任何统计，属演示数据清理，不是代码缺陷。

### 8.3 未验证项与遗留问题

- 「还差 X 分 X 秒」文案在 2 秒窗口内未被浏览器自动化截图捕获（三次均在窗口关闭后读取）；`discarded` 结果、约 2s 自动回首页与代码路径均已确认，建议人工点一次核对文案显示。
- 180 分钟封顶的浏览器自动跳转未单独演示：封顶规则与 `session_max_seconds` 字段由单测覆盖；前端「本地计时到上限即补发请求」与「15s 轮询兜底」两条路径尚未做浏览器验证。
- 首页「当天数据无新增累计」无法验证：P5 统计未实现，无累计数据可对照（验收 13 的后半句待 P5 实现后复验）。
- 有效场次（`completed` / `settled`）仍会锁定当天任务：这是 P2「计时开始后锁定文案」的既有语义，重开入口由 P4 结算后的「再学一场」承担，本轮不改。
- 演示阈值 `session_min_seconds=60` 时，里程碑文案仍写「已经 5 分钟」；这是演示压缩时间的既有口径，不随阈值改写，避免把演示配置泄漏到产品文案。
- 未处理多标签页同时点结束的并发：两次 end 都写同一 `completed` 结果，事务先后不产生重复统计（无额外统计写入）；Demo 单客户端不覆盖强一致。
- P2 遗留的 `locked` 跳转在 `currentSessionId` 可能为空/旧值；本计划专注页以 `GET /current` 为权威，已消除该风险（本次 E2E 已验证 `/focus` 不依赖持久化的 `currentSessionId`）。

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 契约（`schemas/session.py`）→ 无迁移 → 业务（`session_service.py`）→ 接口（`routers/session.py`）→ 前端（`pages/FocusPage.tsx` + `features/focus/`）；`config.py` 只加两个阈值键。
> 2. **当前 owner 在哪里？** 会话状态与有效性判定 owner 是 `session_service.py` + PostgreSQL `sessions` 表；时间 owner 是 `app/clock.py`；前端时间入口是 `hooks/useServerClock.ts`；HTTP 入口是 `api/client.ts`。
> 3. **是否引入重复状态或平行写入？** 否。结束判定只有 `end_session` 一条写入路径；5 分钟里程碑仍由 `get_current_session` 懒标记写入；前端不自行判定有效性，只消费 `result` / `status` / `ended_at`。
> 4. **是否影响接口和其他模块？** 是。新增 end 端点；`POST /api/sessions` 语义变为复用；`SessionInfo` 增加两个字段；P4 结算、P5 统计将消费 `completed/discarded/duration_sec/ended_at` 口径。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮、后端全量测试、`alembic check`、前端 lint + build、Task 4 演示验收。
