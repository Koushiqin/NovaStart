# 005 · F7 星星与连续天数

> 来源：[brainstorming.md](../../brainstorming.md) F7、第 4 节 R1–R7、第 10 节 A5/A7/A18；执行计划：[2026-11-07-p5-f7-star-streak.md](../superpowers/plans/2026-11-07-p5-f7-star-streak.md)。前置 Spec：[003 · F3 专注计时与有效性](./003-f3-focus-session.md)、[004 · F4+F5 结算四步与感想](./004-f4-f5-settle-reflection.md)。

## 1. 背景与目标

P3 已把有效/无效场次的判定收敛到服务端（`status ∈ {completed, settled}` 且 `ended_at` 非空 = 有效；`discarded` 完全丢弃），P4 已在结算页预留 `star_level` / `streak` 槽位（恒 `null`）。F7 的进度可视化仍缺失：

- 没有「每天一颗星」的持久事实，也没有亮度分级；
- 没有连续天数与历史最长的持久事实，断签归零无处判定；
- 首页没有星星墙与「连续 X 天」；
- 结算页只有槽位，没有数值、动画与断签文案。

目标：在服务端建立 `stars`（一天一颗，亮度 Lv1–Lv3）与 `streaks`（当前连续 / 历史最长 / 最后完成日）两张表，由 `progress_service` 单一写入路径维护；首页展示最近 30 天星星墙（亮 / 暗 / 空心）与「连续 X 天 · 最长 Y 天」；结算页填入本场星星等级、连续天数大数字与一次性点亮动画；种子里小明连续 6 天，今天完成即看到 7 天。

## 2. 范围与非目标

- 范围（F7 全部规则 + 跨天规则 R1–R7）：
  - **一天一颗星**；当天**有效累计时长** ≥5 分钟点亮 Lv1、≥15 分钟 Lv2、≥25 分钟 Lv3 封顶（A5）。
  - **亮度只升不降**；同一天多场的额外时长全部计入**会话开始日**（R2、R4），不跨到次日。
  - **连续天数**：当天累计有效 ≥5 分钟即 +1，同一自然日只 +1 一次（A7、R6）；某自然日未完成 → 次日归零，保留历史最长（R7），不做补签/保护卡。
  - **展示三态**：已点亮（亮）、今天未完成（暗）、断签日（空心），首颗星星之前的日子不显示（empty）。
  - **R1/R3/R5**：所有「今天」按服务端 `Clock` 的 Asia/Shanghai 判定；满 5 分钟自动标记当天完成但不结束计时；跨零点回来后首页仍优先显示进行中场次（P3 已实现，本计划不改）。
  - **累计完成天数**：以 `stars` 行数（读侧统计）保留，不在 `streaks` 冗余列；P5 UI 不展示，供 P8 复用。
  - 首页星星墙（最近 30 天）+ `StreakBadge`；结算页星星动画 + 连续天数大数字 + 断签文案；里程碑横幅小星星发光。
  - **演示验收**：种子小明连续 6 天；今天完成一场 → 首页星墙今天点亮、「连续 7 天」，结算页动画只播一次。
- 非目标（明确不做的）：
  - 信箱与投递（P6）；记录页三种查法与「第 X 场」标注（P8）；星星点击跳单日详情（P8）。
  - 时间旅行 / 时间加速开关的具体实现（F9 既有能力，本计划只保证 `Clock` 注入可用）。
  - 补签、保护卡、连续天数编辑；累计完成天数的 UI。
  - 前端任何天数/亮度推算——只在服务端计算。

## 3. 可测试的验收条件

1. 单场有效会话按分钟参数化：5 → Lv1、14 → Lv1、15 → Lv2、24 → Lv2、25 → Lv3、40 → Lv3（天数边界钉住）。
2. 同一天两场有效会话（5 分钟 + 12 分钟）→ `stars.minutes=17`、`level=2`；连续天数只 +1 一次。
3. 跨零点：23:58 开始、00:03（时钟推进 5 分钟）达到 5 分钟 → 星星落在 23:58 那天；连续天数记在开始日。
4. 断签：昨天完成、前天未完成 → `current=1`、`was_reset=true`、`longest` 不回退。
5. 读侧归零：`last_completed_date` 早于昨天 → `GET /api/progress/summary` 的 `streak.current=0`，且 `streaks` 行不被改写（不写后台任务）。
6. 仅 `discarded` 场次（无其他有效场）→ 不产生 `stars` 行、连续天数不变。
7. 有效结束但期间从未轮询命中 5 分钟里程碑（如 285s 轮询后 360s 结束）→ 当天 star 点亮且连续天数 +1（幂等，不重复）。
8. 亮度只升不降：已有 Lv2 的日期再次 recompute 得到一个更小值时仍保持 Lv2。
9. `GET /api/progress/summary` 契约：`today {minutes, level}`、`streak {current, longest, was_reset}`、`wall` 恰好 30 项（按日期升序、最后一项为今天）、`server_time` 齐全。
10. 星星墙状态：今天的星星存在 → `lit`；今天无星 → `dim`；首颗星星之后、今天之前的无星日 → `broken`；首颗星星之前（或账号无任何星）→ `empty`（不绘制星星）。
11. 结算页 summary：本场归因日有星 → `star_level` 为该日等级，否则 `null`；`streak` 为当前账号快照，无任何完成记录时为 `null`。
12. 种子：小明最近 6 天（今天-6…今天-1）逐日有 `stars` 行（Lv1）且 `streak.current=6 / longest=6 / last_completed_date=昨天`；小美 1 天；小刚 0。种子星星/连续天数全部由 `recompute_day + mark_day_completed` 真实路径产生，不手写 star/streak 行。
13. 后端取时间只用 `Clock`；有效场次口径与 P4 一致（`status ∈ {completed, settled}` 且 `ended_at` 非空，`discarded` 排除）；归属日统一 `cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`，禁止裸 cast。
14. 前端只消费接口数据，不自行推算天数/亮度；不新增 `new Date(`（架构棘轮继续通过）；HTTP 只走 `api/client.ts`。
15. `npm run lint`、`npm run build` 通过；`backend/tests/test_architecture.py` 棘轮通过。
16. 演示验收：种子重置后首页看到 6 天星墙与「连续 6 天」；完成一场后今天点亮、显示「连续 7 天」；结算页星星动画一次性播放，`was_reset=true` 时文案为「新的一条线，从今天这 5 分钟开始」，否则为「明天再来」类钩子句。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：有效性与会话时长唯一来源仍是 `sessions` 表（P3 语义），星星唯一来源新增 `stars` 表，连续天数唯一来源新增 `streaks` 表，当前时间仍是后端 `Clock`，前端身份仍是 zustand `userId`。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/session.py` | 有效场次与归属日的事实源 | 不改；只读 |
| `backend/app/models/star.py`（新增） | 每日星星 owner | 新建理由：一天一颗星的持久事实独立于 session（多场累计到同一行），用 `(user_id, date)` 唯一约束保证不重复 |
| `backend/app/models/streak.py`（新增） | 连续天数 owner | 新建理由：当前连续 / 历史最长 / 最后完成日是跨日状态，不能由无状态查询派生 |
| `backend/app/services/progress_service.py`（新增） | 星星/连续天数的唯一写入路径与读侧口径 | 新建理由：把「从有效会话重算当天星星」「维护连续天数」「断签读侧归零」收敛为独立领域服务，session_service 只做触发 |
| `backend/app/schemas/progress.py`（新增） | progress API 契约 | 新建 |
| `backend/app/routers/progress.py`（新增） | `GET /api/progress/summary` | 新建 |
| `backend/app/services/session_service.py` | 触发点 owner | 修改：懒标记 5 分钟处、180 封顶处、有效结束处调用 progress_service（幂等）；`get_settlement_summary` 返回 star/streak 扩展值 |
| `backend/app/models/__init__.py`、`backend/app/main.py` | 模型注册 / router 注册 | 修改 |
| `backend/alembic/versions/<new>_stars_streaks.py`（新增） | 两张新表迁移 | 新建（autogenerate 后人工核对唯一约束与外键） |
| `backend/app/seed.py` | 演示数据 owner | 修改：造完会话后按用户按日期升序调 `recompute_day + mark_day_completed` |
| `backend/tests/test_progress.py`（新增） | 验收条件 1–11 的后端测试 | 新建 |
| `frontend/src/features/progress/StarWall.tsx`（新增） | 30 天星星墙 | 新建理由：状态映射与亮度三档独立于首页 |
| `frontend/src/features/progress/StreakBadge.tsx`（新增） | 「连续 X 天 · 最长 Y 天」 | 新建理由：P6 首页扩展时可复用 |
| `frontend/src/pages/HomePage.tsx` | 首页顶部进度区 | 修改：拉 `GET /api/progress/summary` 并挂载两个组件 |
| `frontend/src/features/settle/SettleSummary.tsx` | 结算摘要槽位 | 修改：星星点亮动画（framer-motion 一次）+ 连续天数大数字 + 断签文案 |
| `frontend/src/features/focus/MilestoneBanner.tsx` | 里程碑提示 | 修改：小星星图标发光，与 FocusPage 变亮同一次触发 |
| `frontend/src/api/client.ts`、`hooks/useServerClock.ts`、`store/app.ts` | 唯一 HTTP / 时间 / 身份入口 | 不改 |

## 5. 实现步骤

按 [dev-order.md](../dev-order.md) 六步流水线：

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：`models/star.py`、`models/streak.py` 定义字段与约束；`schemas/progress.py` 定义响应；P4 的 `SessionSummary` 扩展字段类型按 §6.3 定稿。
3. **迁移（六步②）**：`alembic revision --autogenerate` 生成两张表，人工核对 `(user_id, date)` 唯一约束与外键；`downgrade base → upgrade head` 双向通过。
4. **业务（六步③）**：先写 `tests/test_progress.py` 失败用例（§7），确认 FAIL；实现 `progress_service.recompute_day` / `mark_day_completed` / 读侧快照；在 `session_service` 三个触发点接入（懒标记、180 封顶、有效结束，均幂等）；`get_settlement_summary` 填 `star_level` / `streak`；`seed.py` 走真实路径。
5. **接口（六步④）**：`routers/progress.py` 新增 `GET /api/progress/summary`，`main.py` 注册；`/docs` 冒烟。
6. **前端（六步⑤）**：`StarWall` + `StreakBadge` 挂首页；`SettleSummary` 填星星动画/连续天数/文案；`MilestoneBanner` 图标发光；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启 + reset seed，按验收条件 16 走一遍；回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 `GET /api/progress/summary`

身份由 `X-User-Id` 注入（账号不存在 → 404 `USER_NOT_FOUND`），`server_time` 由 `Clock` 产出。

| 字段 | 类型 | 说明 |
|---|---|---|
| `today.minutes` | int | 今天归属日的 `stars.minutes`；无星为 `0` |
| `today.level` | int | 今天归属日的 `stars.level`；无星为 `0`（未点亮） |
| `streak.current` | int | 读侧懒计算后的当前连续天数（见 §6.4） |
| `streak.longest` | int | 历史最长连续天数（永不回退） |
| `streak.was_reset` | bool | 最近一次完成是否为断签后重开的一段 |
| `wall` | array | 最近 30 个自然日（`today-29 … today`，按日期**升序**，最后一项为今天） |
| `wall[].date` | str（`YYYY-MM-DD`） | 该自然日 |
| `wall[].state` | `"lit" \| "dim" \| "broken" \| "empty"` | 见 §6.4 |
| `wall[].level` | int \| null | `lit` 时为 1–3；其余为 `null` |
| `server_time` | str | 服务端当前时间 |

- 该端点只读：不写库、不做懒标记；断签归零只体现在响应里。
- 无任何星星的账号：`wall` 中今天为 `dim`，其余 29 天为 `empty`。

### 6.2 两张新表与迁移

`stars`（一天一颗）：

| 列 | 类型 | 约束 / 说明 |
|---|---|---|
| `id` | int | PK |
| `user_id` | int | FK `users.id`，非空 |
| `date` | Date | 非空；会话归属日（Asia/Shanghai 自然日） |
| `minutes` | int | 非空，默认 0；当天有效累计秒数 `// 60`（真实值） |
| `level` | int | 非空，默认 0；1–3（有行的日期恒 ≥1），只升不降 |
| — | — | 唯一约束 `(user_id, date)` |

`streaks`（每账号一行）：

| 列 | 类型 | 约束 / 说明 |
|---|---|---|
| `user_id` | int | PK，FK `users.id` |
| `current` | int | 非空，默认 0；当前连续天数（断签读侧归零，不写回） |
| `longest` | int | 非空，默认 0；历史最长（永不回退） |
| `last_completed_date` | Date \| null | 最近一次完成的归属日 |
| `was_reset` | bool | 非空，默认 false；最近一次完成是否为断签后重开 |

- 迁移：一张 revision 同时建两张表，`downgrade` 逆序 drop；无既有表改动、无数据回填。
- 累计完成天数 = `stars` 行数（读侧 `count`），不新增列。
- 单一写入路径：两张表只由 `progress_service.recompute_day` / `mark_day_completed` 写入；`GET` 端点与前端都不写。
- 事务：`progress_service` 内部只 `flush` 不 `commit`，由调用方（`session_service` / `seed` / 测试）在同一事务提交，保证会话状态与星星/连续天数原子。

### 6.3 P4 `SessionSummary` 扩展字段（填值）

P4 已固定字段名，本计划填值；`streak` 由占位 `int | null` 升级为结构化对象（P4 实际恒 `null`，无运行时消费者）：

| 字段 | P5 语义 |
|---|---|
| `star_level` | 本场**归属日**的 `stars.level`（1–3）；该日无星为 `null` |
| `streak` | `{current, longest, was_reset} \| null`，与 `GET /api/progress/summary` 同源同结构；账号无任何完成记录时为 `null` |

- 结算页文案：归因日为今天且 `was_reset=true` → 「新的一条线，从今天这 5 分钟开始」；否则用「明天再来」钩子句（文案可具体到剩余步骤，但不得出现「恭喜完成任务」类空话）。
- 前端 TS 类型 `SettleSummaryData` 同步改；`SettleSummary.tsx` 是仓库内唯一消费者。

### 6.4 判定口径（P6 复用）

- **有效场次**：`status IN ('completed','settled') AND ended_at IS NOT NULL`；`discarded` 与进行中场次一律排除。复用 `settle_service.SETTLEABLE_STATUSES`。
- **归属日**：`cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`（禁止裸 cast）。
- **亮级**：有效秒数 `<300 → 0`（不建行）；`<900 → 1`；`<1500 → 2`；其余 `3`。已有行取 `max(旧 level, 新 level)`。
- **星星墙状态**（按日期 `d`）：
  1. 该日有 `stars` 行 → `lit`（`level` 为该行等级）；
  2. 否则 `d == today` → `dim`；
  3. 否则账号**首颗星星日**不存在或 `d < 首颗星星日` → `empty`；
  4. 其余（首颗星星日之后、今天之前的漏掉日）→ `broken`。
- **连续天数读侧懒计算**（`GET` 与 summary 共用，不改库）：
  - `last_completed_date == today` 或 `== 昨天` → `current = streaks.current`；
  - `last_completed_date` 更早 → `current = 0`（归零只在读侧呈现）；
  - 无 `streaks` 行 → `current = 0`、`longest = 0`、`was_reset = false`。
- **`mark_day_completed(db, user_id, day)`**（幂等，只 flush）：
  - 行存在且 `last_completed_date == day` → 不改（一日只 +1）；
  - `last_completed_date == day - 1` → `current += 1`，`longest = max(longest, current)`，`was_reset = false`；
  - 其余（无行或断档）→ `current = 1`，`was_reset = 行曾存在`（全新账号首次完成为 `false`），`longest = max(旧 longest, 1)`；
  - 最后写 `last_completed_date = day`。
- **`recompute_day(db, user_id, day) -> Star | None`**（幂等，只 flush）：
  - 汇总该归属日有效场次 `duration_sec`，得有效秒数与 `minutes`；
  - `level = 0` 且无既有行 → 返回 `None`（不建行）；`level = 0` 但已有行 → 保持旧行（只升不降）；
  - 否则按 `(user_id, day)` upsert：`minutes = 有效秒数 // 60`，`level = max(旧, 新)`。
- **「当天完成」口径（P6 收信门槛复用）**：`streaks.last_completed_date == Clock.today()` 或当天 `stars.level ≥ 1`；等价关系由 `mark_day_completed` 的单一写入路径保证，不在 P6 另写第二套。

### 6.5 触发点与兼容性

- `session_service.get_current_session` 的懒标记分支（`elapsed ≥ min` 且 `active` → `completed`）与 180 封顶分支（写 `ended_at` / `duration_sec`）后，调用 `mark_day_completed` + `recompute_day`，`day = started_at` 的 Asia/Shanghai 日期。
- `session_service.end_session` 的有效分支（写 `completed` / `duration_sec` / `ended_at`）后同样调用 `mark_day_completed` + `recompute_day`；`discarded` / 重复结束分支不调用。
- 迁移新增两张表，不改既有 API 契约（除 §6.3 的 `streak` 类型升级）；P3 的 `/current`、`/end`、P4 的 `/summary`、`/reflection`、`/settle/{id}/advance` 行为不变。
- 前端：`HomePage` 在账号切换/挂载时拉一次 `GET /api/progress/summary`；异步回调带账号快照守卫（沿用 P1/P2/P3 复审结论）。`StarWall` 的 `empty` 单元格不绘制星星图形，但保留网格占位避免布局塌陷。
- 星星/连续天数只来自接口；前端不做任何天数推算，不使用 `new Date(`。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（`backend/tests/test_progress.py`；时序一律注入 `FixedClock` / `get_clock` override，禁止 sleep）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_star_levels`（parametrize 5/14/15/24/25/40） | 造对应时长有效会话 → recompute 后 level = 1/1/2/2/3/3 |
| 2 | `test_two_sessions_accumulate_one_increment` | 5+12 → `minutes=17`、`level=2`；`streak.current=1` |
| 3 | `test_cross_midnight_attributed_to_start_day` | 23:58 开始、00:03 达到 5 分钟 → star 日期 = 开始日 |
| 4 | `test_break_resets_keeps_longest` | 断档 → `current=1`、`was_reset=true`、`longest` 不回退 |
| 5 | `test_read_side_zero_does_not_write` | last 早于昨天 → 响应 `current=0`，库中 `current` 未变 |
| 6 | `test_discarded_contributes_nothing` | 仅 discarded → 无 star、streak 不变 |
| 7 | `test_end_without_milestone_marks_streak` | 无轮询直接有效结束 → star + streak +1，重复结束不重复 |
| 8 | `test_level_only_increases` | 已 Lv2 再 recompute 较小值 → 仍 Lv2 |
| 9 | `test_progress_summary_contract` | 字段齐全、wall 30 项且升序、最后一项为今天 |
| 10 | `test_summary_wall_states` | lit / dim / broken / empty 四态正确 |
| 11 | `test_settle_summary_filled` | P4 summary 的 `star_level` / `streak` 非 null 且与 progress 同源 |
| 12 | 扩展 `test_seed.py` | 小明 6 天 stars + `current=6/longest=6`；小美 1 天；小刚 0 |
| 13 | `test_architecture.py` + Grep | 后端 `datetime.now(` 仅 `clock.py`；归属日无裸 cast |
| 14 | 前端 lint/build + Grep | `new Date(` 仅 `api/client.ts` / `hooks/useServerClock.ts` |
| 16 | 浏览器端到端（Task 4） | 种子 6 天 → 今天完成 → 7 天；结算动画一次 |

验证命令：

```powershell
# 新增进度测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_progress.py -q

# 后端全量 + 架构棘轮
cd backend; .venv\Scripts\python.exe -m pytest -q

# 迁移双向（测试库）
cd backend; .venv\Scripts\alembic.exe downgrade base; .venv\Scripts\alembic.exe upgrade head

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

### 8.1 已运行通过的验证（2026-11-07）

| 命令 / 动作 | 结果 |
|---|---|
| `backend: pytest -q` | **158 passed**（含 `test_progress.py` 16 条、`test_seed.py` 扩展断言、`test_architecture` 棘轮） |
| `alembic check`（开发库） | `No new upgrade operations detected` |
| 测试库 `downgrade base → upgrade head` | 双向通过（`2cfedebff490` 建/删 `stars`、`streaks`） |
| `frontend: npm run lint` | 0 error（仅既有 `button.tsx` 1 条 react-refresh warning） |
| `frontend: npm run build` | `tsc -b && vite build` 通过 |
| 前端 `new Date(` Grep | 仅 `api/client.ts`、`hooks/useServerClock.ts`（验收 14 通过） |

- 提交：`b707c45 feat(backend): stars and streak with recompute single write path`；`670ce35 feat(frontend): star wall and settle star animation`。
- 测试已编写且已运行通过：验收条件 1–11 全部由 `test_progress.py` 覆盖；12 由 `test_seed.py` 覆盖；13 由 `test_architecture.py` 覆盖。

### 8.2 演示验收（浏览器 + API，全部 PASS；验收 16）

1. 三服务同启（PostgreSQL、`python -m app.main`、vite `localhost:5173`）后 `POST /dev/reset-seed`：小明（id=32）`GET /api/progress/summary` → `wall=30`、11-01…11-06 共 6 颗 Lv1、今天 `dim`、`streak=6/6`；浏览器首页显示 6 颗星与「6 天连续 · 最长 6 天」。
2. 今天创建任务 → 分析 → 开始 → 为压缩演示时长把该会话 `started_at` 回拨 6 分钟（**演示数据调整，非产品代码**）→ `GET /current`（命中 5 分钟懒标记）→ `POST /end` 返回 `settled`、`duration=360`。
3. 完成后 `today=6min/L1`、星星墙今天 L1、`streak=7/7`；浏览器首页 7 颗星与「7 天连续 · 最长 7 天」；`/settle` 显示金色星星、「连续 7 天」与「明天再来 5 分钟…」文案（截图 `homepage-streak-7.png`、`settle-page-streak-7.png`）。
4. 演示结束后再次 `POST /dev/reset-seed`，恢复 6 天基线（同时删除本轮演示会话），当前账号回到 `streak=6/6`、今天 `dim`。

### 8.3 未验证项

- 结算星星动画「只播一次」：代码为 framer-motion 单次 `animate`（无 `loop`、无重复 trigger），截图确认了终态；未用逐帧工具量化确认。
- 跨零点断签文案：`SessionSummary` 未暴露本场归属日，前端只能按 `was_reset` 判定，跨零点结算可能显示「从今天这 5 分钟开始」（Ruling 已记 P5 ledger）。
- 180 封顶的浏览器端到端未单独演示（P3 已记遗留）：后端由单测覆盖，前端与 5 分钟共用 `ended_at` 检测路径。
- 星星墙 30 天窗口外日期的 `broken/empty` 判定：实现按整表首颗星星日计算，窗口内四态由 `test_summary_wall_states` 覆盖，窗口外无独立用例。

### 8.4 遗留问题与边界

- 5 分钟里程碑时该场 `ended_at` 为空，按 §6.4 不算有效场次：里程碑只 +1 连续天数，星星要等有效结束/180 封顶后才点亮；专注进行中首页今天仍显示 `dim`（Ruling 已记 ledger）。
- 累计完成天数按 `stars` 行数读侧统计，未在 `streaks` 冗余；P5 不展示，留给 P8。
- 迁移只新增两张表，`downgrade` 逆序 drop 即可，无既有表改动与数据回填。

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 契约（新增 `models/star.py` / `models/streak.py` / `schemas/progress.py`，P4 `SessionSummary.streak` 类型升级）→ 迁移（两张新表）→ 业务（新增 `progress_service.py`，`session_service.py` 接三个触发点，`seed.py` 走真实路径）→ 接口（新增 `routers/progress.py`）→ 前端（`StarWall` / `StreakBadge` + `HomePage` / `SettleSummary` / `MilestoneBanner`）。
> 2. **当前 owner 在哪里？** 有效性与归属日 owner 是 `sessions` + `session_service`；星星 owner 是新增 `stars` + `progress_service`；连续天数 owner 是新增 `streaks` + `progress_service`；时间 owner 是 `clock.py`；前端身份是 `store/app.ts`。
> 3. **是否引入重复状态或平行写入？** 否。stars/streaks 只有 `progress_service` 一条写入路径（`recompute_day` / `mark_day_completed`），`session_service` 只触发；断签归零只在读侧呈现，不写库；前端不推算天数、不缓存权威进度。
> 4. **是否影响接口和其他模块？** 新增一个 GET 端点与两张表；P4 summary 两个占位字段开始有值（`streak` 类型由占位 `int` 升级为对象，P4 恒 null 无运行时破坏）；P6 可复用「当天完成」口径；P3/P4 既有行为不变。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮、后端全量测试、`alembic` 双向迁移、前端 lint + build、Task 4 演示验收。
