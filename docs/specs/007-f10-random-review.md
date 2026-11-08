# 007 · F10 随机回顾

> 来源：[brainstorming.md](../../brainstorming.md) F10；执行计划：[2026-11-07-p7-f10-random-review.md](../superpowers/plans/2026-11-07-p7-f10-random-review.md)。前置 Spec：[003 · F3 专注计时与有效性](./003-f3-focus-session.md)、[004 · F4+F5 结算四步与感想](./004-f4-f5-settle-reflection.md)、[006 · F6 信箱与投递](./006-f6-mailbox.md)。

## 1. 背景与目标

P4 把结算四步的断点与①写感想打通，第④步「回顾」只是可跳过的占位卡片（[StepReview.tsx](../../frontend/src/features/settle/StepReview.tsx)），后端也没有任何回顾接口。F10 的全部规则尚未实现：

- 没有数据源：无法从本人历史里抽出一条完整记录（日期 + 任务原文 + 感想）；
- 没有「排除本场与当天所有场次」的候选池口径，容易回顾到刚才这一场；
- 没有空态（新账号 / 当天只有这一场）与「无感想只显示任务原文」的处理；
- 没有跳转目标约定，记录详情页（P8）无法被结算页直达。

目标：①②③ 走完后第④步自动出现（无需用户操作），从本人过去的有效场次随机抽一条，以「过去的你」卡片展示日期 + 任务原文 + 感想（无感想只显示任务原文，不留空白框）；无历史时只显示一句「等待宇宙的讯息」；点击卡片可跳到那一天（`/records?date=YYYY-MM-DD`，本计划落到既有占位页，P8 填详情）。

## 2. 范围与非目标

- 范围（F10 全部规则）：
  - **触发**：①②③ 完成后自动渲染第④步；沿用 P4 的 `settle_step` 断点（第③步完成 advance 到 3，`SettlePage` 的 default 分支即渲染第④步），P7 不改触发条件。
  - **候选池**：当前用户、`status IN ('completed','settled')` 且 `ended_at IS NOT NULL` 的会话；归属日 = `started_at` 的 Asia/Shanghai 自然日，必须 **早于今天**（排除当天所有场次）。
  - **排除本场**：query 传入 `exclude_session_id`，不得抽中该场（覆盖「昨天 23:58 开始、今天结束」这类归属日在昨天但仍是本场的场次）。
  - **随机**：`ORDER BY random() LIMIT 1`；每次随机抽一条，**不保证不重复**（不记忆上次结果、不做冷却）。
  - **展示**：日期（归属日 ISO `YYYY-MM-DD`）、任务原文（`day_tasks.raw_text`）、感想（本场 `reflections.content`）；无感想 → `reflection=null`，前端不渲染空白框。
  - **空态**：候选池为空（第一次完成 / 新账号 / 当天只有这一场）→ `item=null`；前端只显示「等待宇宙的讯息」一句，不报错、不加额外引导文案。
  - **频率**：组件每次 mount 只请求一次；结算页 summary 重新渲染不重复抽卡（每场结算只拉取一次）。
  - **跳转**：整卡可点 → `/records?date=<归属日>`；本计划只约定 query，记录页本身由 P8 实现（当前占位页允许忽略 query）。
  - **演示验收**：reset seed 后小明有 6 天历史；小明完成今天的场次走到第④步 → 抽中 6 天中的某一天，展示该天任务原文与感想，点击卡片跳到 `/records?date=...`；新账号小刚完成首场 → 只显示「等待宇宙的讯息」。
- 非目标（明确不做的）：
  - 记录详情页本身（三种查法、「第 X 场」标注、按日期直开单日视图）——P8；本计划只产出 `/records?date=` 跳转约定。
  - 不重复保证：不做「已回顾过」标记、不做最近 N 天冷却、不做去重表。
  - 手动换一条 / 刷新重抽 / 回顾历史列表：每场结算只出现一次。
  - 随机会话的写入、回顾记录落库、任何新表或迁移（本功能只读）。
  - 结算四步顺序、`advance` 语义、宇宙音讯文案的改动。
  - 跨账号回顾（只抽本人历史）。

## 3. 可测试的验收条件

1. 本人请求 `GET /api/review/random?exclude_session_id=<id>` → `200`，响应 `{item, server_time}`；`item` 字段齐全：`session_id: int`、`date: str`（归属日 ISO `YYYY-MM-DD`）、`task_text: str`（该场任务 `raw_text`）、`reflection: str | null`；`server_time` 为 `Clock.now()` 的 ISO 字符串。
2. 候选池只含本人、`status IN ('completed','settled')` 且 `ended_at IS NOT NULL`、归属日早于今天的场次；`discarded`、`active`、`completed` 但 `ended_at IS NULL`（仅达里程碑未结束）、他人会话均不入选。
3. 排除本场：仅有一条合格候选时，传其 `session_id` 为 `exclude_session_id` → `item=null`；不传排除自己 → 必抽中该条。
4. 排除当天所有场次：昨天开始的有效场次今天可被抽到；今天开始的场次（任意状态，含已结束）今天一律不出现。当天只有这一场 → `item=null`。
5. 跨零点归属：昨天 23:58 开始、今天 00:03 结束的场次归属昨天 → 今天可被抽到；若它正是当前场次并被 `exclude_session_id` 排除 → 不出现（`Clock` 注入钉住）。
6. 无感想候选 → `reflection=null`；有感想候选 → `reflection` 等于该场 `reflections.content`。
7. 参数与身份：缺 `X-User-Id` / `exclude_session_id` 缺失或非整数 → `422`；`X-User-Id` 账号不存在 → `404 {"detail": {"code": "USER_NOT_FOUND"}}`。
8. 演示种子：reset seed 后小明请求（排除今天的本场）→ `item` 为 6 天种子中某一天，`task_text` 与 `reflection` 与该天种子一致，`date` 为对应种子日期。
9. 前端空态：`item=null` → 回顾区域只渲染「等待宇宙的讯息」，无额外引导文案；「完成」按钮仍可用（推进结算不被阻塞）。
10. 前端有内容：渲染「过去的你 · {date}」卡片，任务原文必显示，感想为空时不渲染空白框；整卡点击 → `navigate("/records?date=" + date)`。
11. 前端频率：组件 mount 时只发一次 `GET /api/review/random`；summary 重新渲染不重复请求、不换卡片。
12. 前端完成：点击「完成」→ `POST /api/settle/{id}/advance` `{to_step: 4}` → `onDone()`（进入宇宙音讯，`settle_step=4` 且 `status="settled"`）。
13. 后端取当前时间只用 `app/clock.py` 的 `Clock`，router 不直接写 SQL（架构棘轮继续通过）；前端 HTTP 只走 `api/client.ts`，不新增 `new Date(`。
14. 无表结构 / 迁移变化，无平行状态与第二写入路径；`/records?date=` 只是跳转约定，不落库。
15. `backend/tests/test_architecture.py` 棘轮、后端全量 pytest、前端 `npm run lint` / `npm run build` 通过。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：有效场次与 `settle_step` 的唯一来源仍是 `sessions` 表（只读）；感想唯一来源仍是 `reflections` 表（只读）；任务原文唯一来源仍是 `day_tasks.raw_text`（只读）；当前时间仍是后端 `Clock`；前端身份仍是 zustand `userId`。本功能不新增写入路径。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/session.py` | 有效场次 / 归属日事实源 | 不改；只读 `status`、`started_at`、`ended_at`、`task_id` |
| `backend/app/models/reflection.py` | 感想事实源 | 不改；只读 `session_id`、`content` |
| `backend/app/models/day_task.py` | 任务原文事实源 | 不改；只读 `raw_text` |
| `backend/app/services/review_service.py`（新增） | 随机回顾唯一查询路径 | 新建理由见 §6.4；`random_past(db, user_id, exclude_session_id, clock) -> tuple[Session, str, str, str \| None] \| None`（返回会话、归属日 ISO、任务原文、感想或 `None`） |
| `backend/app/schemas/review.py`（新增） | 回顾 API 契约 | 新建：`ReviewItem`、`RandomReviewResponse`（与 service 返回结构一一对应） |
| `backend/app/routers/review.py`（新增） | 回顾 HTTP 入口 | 新建：`GET /api/review/random`，只解析 query、转发、组装 `server_time` |
| `backend/app/main.py` | 路由注册 | 修改：注册 review router |
| `backend/tests/test_review.py`（新增） | 验收条件 1–8 的后端测试 | 新建 |
| `frontend/src/features/settle/StepReview.tsx` | 结算第④步 | 替换占位：mount 拉取一次 + 卡片 / 空态 + 完成；props `{sessionId, onDone}` 契约不变 |
| `frontend/src/pages/SettlePage.tsx` | 第④步触发 | 不改：第③步 advance 到 3 后由 default 分支渲染第④步 |
| `frontend/src/pages/RecordsPage.tsx` | 跳转目标 | 不改：占位页允许忽略 `?date`，P8 实现单日视图 |
| `frontend/src/api/client.ts`、`hooks/useServerClock.ts`、`store/app.ts` | 唯一 HTTP / 时间 / 身份入口 | 不改 |

## 5. 实现步骤

按 [dev-order.md](../dev-order.md) 六步流水线；本功能只读，无迁移。Task 1 只完成第 0 步（Spec），其余由后续任务执行：

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：`schemas/review.py` 定义 `ReviewItem` 与 `RandomReviewResponse`；字段与 §6.1 一致（`reflection` 可空）。
3. **迁移（六步②）**：无（不改表结构与数据）。
4. **业务（六步③）**：先写 `tests/test_review.py` 失败用例（§7），确认 FAIL；实现 `review_service.random_past`（§6.3 候选池与随机口径）。
5. **接口（六步④）**：`routers/review.py` 单端点，只解析/转发；`main.py` 注册；`/docs` 冒烟。
6. **前端（六步⑤）**：替换 `StepReview.tsx`（mount 拉取一次、卡片/空态、点击跳转、完成推进）；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启 + reset seed，按 §3 第 8–12 条与演示验收走一遍；回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 契约

#### `GET /api/review/random`

身份由 `X-User-Id` 注入（缺失 → 422；账号不存在 → 404 `USER_NOT_FOUND`），`server_time` 由 `Clock` 产出。

Query：`exclude_session_id: int`（必填；缺失或非整数 → 422）。

响应 `200 RandomReviewResponse`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `item` | `ReviewItem \| null` | 候选池为空时 `null` |
| `item.session_id` | int | 被抽中的会话 id |
| `item.date` | str | 该场归属日，`started_at` 的 Asia/Shanghai 自然日，ISO `YYYY-MM-DD` |
| `item.task_text` | str | 该场任务 `day_tasks.raw_text` |
| `item.reflection` | str \| null | 该场 `reflections.content`；无感想为 `null` |
| `server_time` | str | 服务端当前时间（ISO） |

- 只读端点：不写库、不推进 `settle_step`、不落回顾记录。
- 不保证不重复：连续两场结算可抽到同一条历史。

### 6.2 数据与迁移

- 无新增表 / 列 / 索引 / 迁移。
- 归属日口径沿用 Spec 003 §6.4 与 Spec 004：`cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`，禁止裸 `cast(started_at, Date)`。
- 随机排序在 Demo 数据规模（单用户几十条）下不加额外索引。

### 6.3 行为口径（review_service 内闭合）

- **候选池**：`Session.user_id == user_id`、`Session.status IN ('completed','settled')`、`Session.ended_at IS NOT NULL`、`cast(func.timezone("Asia/Shanghai", Session.started_at), Date) < clock.today()`、`Session.id != exclude_session_id`。
- **随机**：`ORDER BY random() LIMIT 1`；同一候选可重复出现，不做冷却 / 记忆。
- **关联**：`join DayTask on Session.task_id` 取 `raw_text`；`outerjoin Reflection on Reflection.session_id == Session.id` 取 `content`（每场至多 1 条，P4 一次性约束保证）。
- **空态**：池空 → 返回 `None`，router 输出 `item=null`；前端只显示「等待宇宙的讯息」（回顾区域，不含额外引导），「完成」按钮保留以免卡住结算。
- **前端加载失败**（非 200 / 网络错误）：显示一行「回顾加载失败，请稍后重试」，仍渲染「完成」按钮，允许推进结算；不重试、不换卡。
- **触发与完成**：第③步完成 advance 到 3 → `SettlePage` default 分支渲染第④步；第④步「完成」→ advance 到 4（`settle_step=4`、`status="settled"`）→ `onDone`；不改变 P4 断点语义。
- **跳转**：整卡 → `/records?date=<date>`；当前 `RecordsPage` 为占位页、允许忽略 query；P8 负责支持 `?date` 直开单日视图（本 Spec 约定的接口）。
- **频率**：组件 mount 时 `useEffect` 拉取一次；summary 重新渲染不重新请求；无轮询。

### 6.4 新增文件理由

- `review_service.py` + `routers/review.py`：随机回顾是跨 `sessions` / `reflections` / `day_tasks` 的**只读查询领域**，与 `settle_service`（结算写入与断点推进）、`progress_service`（首页进度快照）职责不同。塞进 `settle_service` 会让只读跨史查询混入结算写入路径；塞进 session router 会引入非 session 资源（`/api/review/random`）。按 [architecture.md](../architecture.md)「确属新领域才建新文件（Spec 中写理由）」，单列 `review` 领域文件。
- `schemas/review.py`：嵌套的 `ReviewItem` 与顶层 `RandomReviewResponse` 需要与 `schemas/settle.py` 区分（settle 是结算写入契约，review 是回顾读取契约）；同领域同名前缀便于读者定位。
- `tests/test_review.py`：本 Spec 验收条件 1–8 同一测试库重建 fixture，沿用现有测试文件的 `FixedClock` + `app.dependency_overrides` 写法。

### 6.5 兼容性

- 不改任何既有 API 契约：`GET /api/sessions/{id}/summary`、`POST /api/settle/{id}/advance`、信件 / 进度端点均不动。
- 不改表结构与数据；无迁移、无回填。
- 前端只替换 `StepReview.tsx` 内部实现，`{sessionId, onDone}` props 与 `SettlePage` 渲染逻辑不变；`StepReview` 的「跳过」文案改为「完成」，推进语义（advance 到 4）不变。
- 记录页联调边界：本计划点击卡片跳到既有 `/records` 占位页，不实现详情；P8 必须支持 `?date=` query 直开单日视图（写入计划头部 Produces，作为 P8 的消费契约）。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（`backend/tests/test_review.py`；时序一律注入 `get_clock` override / `FixedClock`，禁止 sleep）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_random_returns_item_shape` | `item` 四字段齐全，`server_time` 为 Clock 时间；`date` 为 ISO 日期 |
| 2 | `test_discarded_excluded` | 昨天的 `discarded` 不入选 |
| 2 | `test_ongoing_completed_excluded` | 昨天开始、`completed` 但 `ended_at=NULL` 不入选 |
| 3 | `test_excludes_self_when_only_candidate` | 池内唯一候选传为本场排除 → `item=null`；不排除 → 必抽中它 |
| 4 | `test_excludes_today_and_self` | 当天场次与本场不入选 |
| 4 | `test_empty_pool_returns_null` | 新账号只有今天一场 → `item is None` |
| 5 | `test_cross_midnight_attribution` | 昨天 23:58 开始的场次今天可被抽到；作为本场排除时不出现 |
| 6 | `test_reflection_nullable` | 无感想候选 → `reflection is None`；有感想 → 内容一致 |
| 7 | `test_missing_exclude_session_id_422` / `test_unknown_user_404` | 422 / 404 `USER_NOT_FOUND` |
| 8 | 种子演示 | reset seed + 小明 → `item` 为 6 天种子之一，`task_text`/`reflection` 与种子一致 |
| 9–12 | 前端 | 空态 / 卡片 / 点击跳转 / 完成推进：lint + build；浏览器端到端由 Task 4 覆盖 |
| 13 | `test_architecture.py` + Grep | 后端 `datetime.now(` 仅 `clock.py`；前端 `new Date(` 仅 `api/client.ts` / `hooks/useServerClock.ts` |
| 14 | 迁移检查 | `alembic check` 无漂移（本功能无迁移） |
| 15 | 全量命令 | 见下 |

验证命令：

```powershell
# 新增回顾测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_review.py -q

# 种子 + 架构棘轮
cd backend; .venv\Scripts\python.exe -m pytest tests/test_seed.py tests/test_architecture.py -q

# 后端全量
cd backend; .venv\Scripts\python.exe -m pytest -q

# 迁移漂移（应无变化）
cd backend; .venv\Scripts\alembic.exe check

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

### 8.1 已运行通过的验证（2026-11-08）

| 命令 / 场景 | 结果 |
|---|---|
| `backend pytest tests/test_review.py -q` | **11 passed**；RED 阶段同一命令 11 failed（端点不存在，全部 404） |
| `backend pytest -q` | **208 passed**（含 `test_architecture` 棘轮、`test_seed`、`test_review`） |
| `frontend npm run lint` | 0 errors（1 条既有 `button.tsx` fast-refresh 警告） |
| `frontend npm run build` | `tsc -b && vite build` 通过 |
| E2E API（PostgreSQL + `python -m app.main` + Vite 5173 同启） | reset seed → 小明新场次走 ①②③ 到 step 3，`GET /api/review/random` 抽中 6 天种子之一（2026-11-04），任务原文与感想非空；小刚（新账号首场）返回 `item=null` |
| 浏览器 `/settle`（小明，session 204） | 「第④步 · 回顾」+「过去的你 · 2026-11-07」卡片（任务原文 + 感想），点击卡片跳 `/records?date=2026-11-07`（占位页），PASS |
| 浏览器 `/settle`（小刚，session 206） | 回顾区域只有「等待宇宙的讯息」+「完成」按钮，无卡片、无副标题 / 额外引导，PASS |
| 第④步推进（小刚 session 205） | 首次浏览器检查中点击「完成」，随后 API summary 确认 `settle_step=4`、`status=settled`（advance → onDone 链路真实生效） |

- 演示阈值：本次 E2E 通过 `SESSION_MIN_SECONDS=1` 启动后端加速（默认 300s），未修改 `.env` 或默认配置；仅用于本次运行。
- `main.py` 注册 review router 后 `/docs` 正常列出 `GET /api/review/random`。

### 8.2 测试已编写 vs 已运行通过

- 后端：`backend/tests/test_review.py` 11 项**已编写并已运行通过**（含验收条件 1–8 与 422/404）。
- 前端：项目无前端测试基建，未新增自动化测试；空态 / 卡片 / 点击跳转 / 完成推进为浏览器手工验证 + lint/build。

### 8.3 未验证项及原因

- `/records?date=` 的单日详情：当前记录页是占位页，允许忽略 query；真实详情属于 P8（本功能非目标），未验证。
- 「不保证不重复」：随机行为，不做确定性断言；连续两场抽中同一条属预期。
- 回顾加载失败分支（网络错误 / 非 200）：代码已实现（一行提示 + 保留完成按钮），未在浏览器制造该故障，无运行时证据。
- 「完成」推进：本轮有真实点击证据（小刚 session 205 → step 4 / settled）；P4 的 advance 回归测试仍通过。

### 8.4 遗留问题与边界

- `RecordsPage` 需由 P8 支持 `?date=` 直开单日视图（本计划已把该 query 作为消费契约写入计划头部 Produces）。
- E2E 在 dev 库留下本次演示任务 / 会话（小刚 session 205/206 等）；不影响后续 reset seed 或演示。
- 随机回顾无手动刷新 / 换一条（按 F10 非目标）。

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 契约（`schemas/review.py` 新增只读响应）→ 迁移（无）→ 业务（`review_service.random_past` 候选池 + 随机）→ 接口（`routers/review.py` 单端点，`main.py` 注册）→ 前端（`StepReview.tsx` 替换占位）。
> 2. **当前 owner 在哪里？** 有效场次与断点 owner 是 `sessions` 表；感想 owner 是 `reflections` 表；任务原文 owner 是 `day_tasks.raw_text`；当前时间 owner 是 `app/clock.py`；前端身份是 `store/app.ts`。
> 3. **是否引入重复状态或平行写入？** 否。回顾是纯只读查询，不落库、不推进 `settle_step`、不写第二份「回顾记录」；不保证不重复是需求本身，不做隐藏状态。
> 4. **是否影响接口和其他模块？** 新增一个只读端点 `GET /api/review/random`；既有 summary / advance / 信件 / 进度契约不变；前端只替换第④步组件，触发逻辑仍由 `SettlePage` 与 P4 断点决定；新增 `/records?date=` 导航约定供 P8 消费。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮、后端全量测试、`alembic check` 无漂移、前端 lint + build、Task 4 演示验收（小明 6 天种子可回顾、小刚空态）。
