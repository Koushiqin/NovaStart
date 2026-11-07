# 004 · F4+F5 结算四步与感想

> 来源：[brainstorming.md](../../brainstorming.md) F4、F5、第 10 节 A14/A19/A21、第 11 节「结算四步断点」；执行计划：[2026-11-07-p4-f4-f5-settle-reflection.md](../superpowers/plans/2026-11-07-p4-f4-f5-settle-reflection.md)。前置 Spec：[003 · F3 专注计时与有效性](./003-f3-focus-session.md)。

## 1. 背景与目标

P3 已把有效结束收敛到 `POST /api/sessions/{id}/end`：有效场次 `status="completed"`、`ended_at` 与 `duration_sec` 已写，前端跳 `/settle`。但 `/settle` 仍是占位页，F4 的三段式反馈与四步流程、F5 的感想全部缺失：

- 没有结算页数据源：本次时长、当天累计、本场任务与采用版 starter 都要前端拼多个接口；
- 没有感想写入入口与「只写一次」约束；
- `settle_step` 列已存在、`POST /api/settle/{id}/advance` 已实现，但没有前端按断点渲染；
- ②投递 / ③信箱 / ④回顾的真实逻辑分别属于 P6/P7，P4 需要先给出可跳过的占位与稳定契约。

目标：有效结束后进入结算页——一屏看到「本次时长 + 今天累计 + starter 原话复述」；随后固定四步（①写感想 → ②投递 → ③信箱 → ④回顾），`settle_step` 断点只进不退、中途离开下次直跳；①完整实现（选填、只读、只写一次），②③④先给占位卡片可跳过；四步走完显示「来自宇宙的音讯」。

## 2. 范围与非目标

- 范围：
  - **F4 三段式结构**：
    1. 具体成果：本次 `duration_sec`、当天累计 `today_total_sec`、本场任务当前采用版 `starter_step` 原话复述（A21）；禁止「恭喜完成任务」类空话。
    2. 星星点亮：只预留 `star_level` 槽位，本计划恒 `null`（P5 填数值与动画）。
    3. 连续天数：只预留 `streak` 槽位，本计划恒 `null`（P5 填数值与文案）。
  - **F4 固定四步**：顺序不可打乱；①②③ 可跳过；`settle_step` 为已完成步数（0–4），前端渲染第 `settle_step + 1` 步；断点恢复只读服务端 `settle_step`，不在前端另存进度。
  - **F5 感想全部规则**：挂在本次 session 上、日期为会话归属日；选填、空白 = 跳过不落库；上限 200 字；历史感想只读（A19），不提供编辑入口或编辑 API。
  - **结算末态**：第④步完成 → `settle_step=4` 且 `status="settled"`（复用既有 `advance` 的条件更新，只进不退）。
  - **宇宙音讯（A14）**：四步走完显示预置文案「5 分钟的星星，是你自己点亮的」，零外部依赖。
- 非目标（明确不做的）：
  - ②投递真实逻辑（收件人、每场 1 次机会、正文回退、未送达）与 ③未处理信箱真实逻辑（≤3 封、收藏/放弃、24:00 失效）——P6。
  - ④随机回顾真实逻辑（排除本场/当天、空态）——P7。
  - 星星亮度分级（5/15/25）、连续天数计算、断签归零与星星动画——P5。
  - `received_during_session` 真实收信数——本计划恒 `0`（P6 填）。
  - 投递机会、信件、信箱、回顾记录的任何读写。
  - 感想的编辑、删除、补写（A19）；敏感内容审核（Demo 只做长度校验）。
  - 结算页的视觉动效库选型（P5 使用既有 framer-motion，本计划不加动画依赖）。

## 3. 可测试的验收条件

1. 有效结束的本人会话 → `GET /api/sessions/{id}/summary` 返回 `200`，含 `duration_sec`（库中时长）、`today_total_sec`、`task_text`、`starter_text`（当前采用版 starter）、`settle_step`、`status`、`received_during_session=0`、`star_level=null`、`streak=null`、`server_time`。
2. `today_total_sec` 只累计有效且已结束的场次（`status ∈ {completed, settled}` 且 `ended_at IS NOT NULL`）：同账号当天另有一场 `discarded` → 不计入；另有一场仅达最短时长但未结束（`completed`、`ended_at IS NULL`）→ 不计入；本场计入。
3. 归属日按 `started_at` 的 Asia/Shanghai 自然日计算，不用「当前日」：23:30 开始 / 00:30 开始两参数化场景下，`today_total_sec` 都等于该归属日已有有效时长 + 本场，跨零点不串日。
4. `discarded` 会话、`ended_at` 为空（`active` 或仅达里程碑的 `completed`）会话、他人会话、不存在的会话请求 summary/reflection → `404 {"detail": {"code": "SESSION_NOT_FOUND"}}`，不泄露他人会话是否存在。
5. 第①步提交非空感想（≤200 字）→ `201`，`settle_step=1`；库中 `reflections` 恰好一条，`content` 为去首尾空白后的文本，`date` 等于会话 `started_at` 的 Asia/Shanghai 日期。
6. 提交空串或纯空格 → `201`，`reflection=null`、`settle_step=1`；库中不新增 `reflections` 行（跳过语义，不报错）。
7. 已有感想或 `settle_step>=1`（含空白跳过后）再次提交 → `409 {"detail": {"code": "REFLECTION_LOCKED"}}`；库中 `reflections` 仍为 0/1 条，`settle_step` 不回退。
8. `content` 超过 200 字 → `422`，不写库、不推进 `settle_step`。
9. 进入 `/settle`：以 `GET /api/sessions/current` 取权威会话 id（无会话回首页），再拉 summary；`settle_step=0` 渲染摘要 + 第①步。
10. 刷新或中途离开后回到 `/settle`（`settle_step` 为 1/2/3）→ 直接落在第 `settle_step+1` 步，不重复结算、不重复推进。
11. 第②③④占位卡片提供「跳过」→ 调用 `POST /api/settle/{id}/advance` 且只进不退；第④步完成 → `settle_step=4`、`status="settled"`，展示宇宙音讯与「回到首页」「再学一场」。
12. 宇宙音讯文案为「5 分钟的星星，是你自己点亮的」；四步未走完不显示。
13. 摘要只显示「本次 X 分钟 · 今天累计 XX 分钟」与 starter 原话；不出现「恭喜完成任务」类空话；`star_level`/`streak` 槽位无值时不伪造数字或文案。
14. 感想没有任何编辑入口：前端无编辑控件，后端无 PUT/PATCH/DELETE 感想接口（A19）。
15. 后端取当前时间只用 `app/clock.py` 的 `Clock`；前端结算页不需要当前时间，也不新增 `new Date(` 直取（架构棘轮继续通过）。
16. 结算页不新增平行进度状态：前端不写 `settleStep` 作为权威，断点一律来自 summary；`store.settleStep` 不参与判定。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：session / 结算状态唯一真相源仍是 PostgreSQL `sessions` 表（`settle_step` 条件更新）；感想唯一真相源是 `reflections` 表；「当前时间」仍是后端 `Clock`；前端身份仍是 zustand `userId`。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/session.py` | 会话与结算断点 owner | 不改；`settle_step`（默认 0）与 `status` 已存在 |
| `backend/app/models/reflection.py` | 感想 owner | 不改；`user_id/session_id/content/date/created_at` 已存在 |
| `backend/app/services/reflection_service.py`（新增） | 感想写入与一次性约束 owner | 新建理由：把「一次写入 + 归属日 + 推进 `settle_step` 同一事务」收敛为独立领域服务，避免 router 或 session_service 承担感想规则；`save(db, session_id, user_id, content, clock) -> Reflection \| None`（`None`=跳过） |
| `backend/app/services/settle_service.py` | 第②–④步推进 owner | 复用；不改条件更新语义 |
| `backend/app/routers/session.py` | 结算页两个读写的 HTTP 入口 | 新增 summary / reflection 子路由（`/api/sessions/{id}/summary`、`/api/sessions/{id}/reflection`）；理由：与既有 session 资源同前缀，避免新开第二个 `/api/sessions` 前缀 router |
| `backend/app/schemas/session.py` | API 契约唯一真相源 | 新增 `SessionSummary`、`ReflectionCreate`、`ReflectionSaved` |
| `backend/tests/test_settle_summary.py`（新增） | 结算数据源与感想规则测试 | 覆盖第 3 节 1–8、10–11 的接口侧 |
| `frontend/src/pages/SettlePage.tsx` | 结算页路由页 | 从占位页改为：取会话 → 拉 summary → 按 `settle_step` 渲染摘要与第 N 步 |
| `frontend/src/features/settle/SettleSummary.tsx`（新增） | 三段式摘要 | 新建理由：把「数字 + starter 复述 + star/streak 槽位」隔离，P5 只替换槽位内容 |
| `frontend/src/features/settle/StepReflection.tsx`（新增） | 第①步感想 | 新建理由：选填/字数/只读提交的交互独立于页面路由 |
| `frontend/src/features/settle/StepDeliver.tsx`、`StepMailbox.tsx`、`StepReview.tsx`（新增） | 第②③④占位 | 新建理由：文件名即 P6/P7 替换点；props 固定 `{sessionId: number, onDone: () => void}` |
| `frontend/src/features/settle/CosmicWhisper.tsx`（新增） | 结算末态 | 新建理由：A14 文案与完成态操作独立，P5/P6/P7 均不改文案 |
| `frontend/src/store/app.ts` | 前端身份 / 会话指针 owner | 不改；`currentSessionId` 仅作第④步当次页面的快捷入口，不作为断点权威 |
| `frontend/src/hooks/useServerClock.ts`、`api/client.ts` | 唯一时间 / HTTP 入口 | 不改，复用 |

## 5. 实现步骤

按 [dev-order.md](../dev-order.md) 六步流水线，Task 1 只完成第 0 步（Spec），其余由后续任务执行：

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：`schemas/session.py` 增加 `SessionSummary`、`ReflectionCreate`、`ReflectionSaved`；字段与 §6.1 一致，不改既有 `SessionInfo` / `SessionEnded`。
3. **迁移（六步②）**：无迁移——`sessions.settle_step`、`reflections` 表均已存在；本步只需 `alembic check` 确认无漂移。
4. **业务（六步③）**：先写 `tests/test_settle_summary.py` 失败用例（§7），确认 FAIL；实现 `reflection_service.save`（空白跳过、一次性 409、写入与 `settle_service.advance(db, id, 1, user_id)` 同一 commit）与 summary 聚合查询（§6.1 口径）。
5. **接口（六步④）**：`routers/session.py` 新增两个端点，只解析/转发/错误映射；响应带 `server_time`；`/docs` 与 curl 冒烟。
6. **前端（六步⑤）**：`SettlePage` + `features/settle/` 六个组件；按 `settle_step` 渲染、占位跳过、第④步完成态；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启，有效结束 → 一屏数字/复述 → 写感想 → 跳过②③④ → 宇宙音讯；中途刷新直跳断点；感想写完刷新不重复 +1。
8. 回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 契约

#### `GET /api/sessions/{id}/summary`

结算页唯一数据源；身份由 `X-User-Id` 注入，`server_time` 由 `Clock` 产出。

| 字段 | 类型 | 来源 / 说明 |
|---|---|---|
| `duration_sec` | int | 本场有效时长（库中 `sessions.duration_sec`） |
| `today_total_sec` | int | 归属日累计：同账号、`status ∈ {completed, settled}`、`ended_at IS NOT NULL`、`cast(func.timezone("Asia/Shanghai", started_at), Date) == 本场归属日` 的 `duration_sec` 之和（含本场）；`discarded` 与未结束场次不计 |
| `task_text` | str | 本场任务当前采用版正文 `day_tasks.raw_text`（P6 信件正文回退用） |
| `starter_text` | str | 本场任务当前采用版 `day_tasks.starter_step`（A21，结算页原话复述） |
| `settle_step` | int | 0–4，已完成步数 |
| `status` | str | `completed` \| `settled` |
| `received_during_session` | int | 本计划恒 `0`（P6 填） |
| `star_level` | int \| null | 本计划恒 `null`（P5 填） |
| `streak` | int \| null | 本计划恒 `null`（P5 填） |
| `server_time` | str | 服务端当前时间 |

- 可访问条件：本人、`ended_at` 非空、`status ∈ {completed, settled}`。
- 其余情况（不存在 / 他人 / `discarded` / 未结束）→ `404 {"detail": {"code": "SESSION_NOT_FOUND", "message": "会话不存在"}}`（不区分原因，避免泄露）。
- 归属日口径沿用 Spec 003 §6.4：禁止裸 `cast(started_at, Date)`。

#### `POST /api/sessions/{id}/reflection`

- 请求 `ReflectionCreate {content: str}`：`max_length=200`；允许空串/纯空格（Pydantic 不做非空校验）。
- 响应 `201 ReflectionSaved`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `reflection` | `{content: str} \| null` | `null` = 本次为跳过（空白） |
| `settle_step` | int | 成功写入或跳过后恒为 `1` |
| `server_time` | str | 服务端当前时间 |

- 规则（service 内闭合）：
  1. 不存在 / 他人 / `discarded` / 未结束 → `404 SESSION_NOT_FOUND`。
  2. `settle_step >= 1` 或该会话已有 `reflections` 行 → `409 {"detail": {"code": "REFLECTION_LOCKED", "message": "感想已提交或已跳过"}}`；不新增记录、不回退步骤。
  3. `content.strip()` 为空 → 不落库，仅推进 `settle_step` 到 1（跳过语义）。
  4. 否则写入一条 `Reflection`：`content = content.strip()`、`date = 会话 started_at 的 Asia/Shanghai 日期`、`user_id` / `session_id` 取自当前会话；与 `advance(..., 1)` 同一次 `commit`（先 `db.add` 再调用 `advance`，不新增第二写入路径）。
- A19：不提供任何更新/删除感想的端点。

#### `POST /api/settle/{id}/advance`（既有，不改）

- 请求 `{to_step: 1..4}`；条件更新 `settle_step < to_step`，只进不退；`to_step>=4` 同事务置 `status="settled"`。
- 本计划中它承担第②③④步的「完成/跳过」：②→2、③→3、④→4；第①步只走 reflection 端点，不重复调用 advance(1)。
- 非本人 / 未结束 / `discarded` → `404 SESSION_NOT_FOUND`；响应 `{session_id, settle_step, server_time}`。

### 6.2 数据与迁移

- **无迁移**：`sessions.settle_step`（默认 0）与 `reflections` 表（`user_id/session_id/content/date/created_at`）均已存在。
- 不新增列、不加唯一约束：感想「每场一条」由 `reflection_service.save` 的读后写保证；Demo 单客户端，不覆盖多客户端并发抢写（与 P3 的口径一致）。
- `Reflection.date` 是会话归属日而非写入日：跨零点写感想仍记在开始日，与 A20 / Spec 003 §6.4 一致。
- 不改 `sessions.status` 的既有语义：第④步完成置 `settled` 仍只由 `settle_service.advance` 一条路径写入。

### 6.3 兼容性与前端接入

- **新增端点，无破坏性变化**：不改 `SessionInfo` / `SessionEnded` / `GET /current` / `POST /end` 契约；前端 TS 类型只增不改。
- **结算页会话解析**（Task 3 消费）：
  1. `GET /api/sessions/current` 返回的 `completed` 且 `ended_at` 非空会话 → 用其 id（覆盖步骤 0–3；刷新后仍可恢复）。
  2. 否则用内存中的 `currentSessionId`（不持久化）拉 summary（覆盖第④步刚完成、会话已 `settled` 的当次页面）。
  3. 两者都无 → 回首页。
- 已知边界：第④步完成后整页刷新，`/current` 不再返回 `settled` 会话，页面回首页；完成态不跨刷新重现。会话本身已 `settled`，统计与记录不受影响。这是 P3「`/current` 只返回进行中/待结算」契约的延续，不在本计划放宽。
- 前端不写 `settleStep` 作为权威：store 里该字段保留但不参与判定；断点一律来自 summary / advance 响应。
- 第④步「再学一场」：`GET /api/tasks/today` 取 `task.id` → `POST /api/sessions {task_id}` 成功后跳 `/focus`；当天无任务（跨零点）时回首页，不新建无主任务。

### 6.4 `settle_step` 语义（P4/P6/P7 共用）

| `settle_step` | 含义 | 前端渲染 |
|---|---|---|
| 0 | 待写感想 | 摘要 + 第①步 `StepReflection` |
| 1 | 感想已写 / 已跳过 | 第②步 `StepDeliver`（P6 替换） |
| 2 | 投递已处理 / 已跳过 | 第③步 `StepMailbox`（P6 替换） |
| 3 | 信箱已处理 / 已跳过 | 第④步 `StepReview`（P7 替换） |
| 4 | 四步完成 | 摘要 + `CosmicWhisper`；`status="settled"` |

- 只进不退：所有推进都经 `settle_service.advance` 的条件更新；重复请求命中 0 行，返回当前值。
- 跳过 = 推进到下一步，不产生任何业务记录；第①步的跳过语义由空白 reflection 承载，不落库。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（`backend/tests/test_settle_summary.py`；时序一律注入 `Clock(offset_seconds=...)` 或 `get_clock` override，禁止 sleep）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_summary_fields` | `duration_sec`/`today_total_sec`/`task_text`/`starter_text`（采用版）/`settle_step`/占位字段全部符合 §6.1 |
| 2 | `test_summary_today_total_valid_only` | 同日另有一场 `discarded` → `today_total_sec` 不含它 |
| 2 | `test_summary_excludes_ongoing_completed` | 同日另一场仅达 min、`ended_at=NULL` → 不计入 |
| 3 | `test_summary_attribution_day_across_midnight`（parametrize 23:30/00:30） | 归属日按 `started_at` 的 Asia/Shanghai 日期，累计不串日 |
| 4 | `test_summary_discarded_session_404` | `404 SESSION_NOT_FOUND` |
| 4 | `test_summary_other_user_404` | 跨账号 → `404 SESSION_NOT_FOUND` |
| 5 | `test_reflection_save_advances_step` | `201`、`settle_step=1`、`Reflection.date` = `started_at` 归属日 |
| 6 | `test_reflection_blank_skips` | `"   "` → `reflection=null`、无记录、`settle_step=1` |
| 7 | `test_reflection_repeat_409` | 已有感想 → `409 REFLECTION_LOCKED`，记录仍 1 条 |
| 7 | `test_reflection_after_skip_409` | 空白跳过后再提交非空 → `409`，仍无记录 |
| 8 | `test_reflection_over_200_422` | `422`，不写库、不推进 |
| 4 | `test_reflection_discarded_404` | `404 SESSION_NOT_FOUND` |
| 11 | `test_advance_step4_marks_settled` | 连续 advance 1→4 后 `status="settled"`、`settle_step=4`，重复调用保持 4 |
| 9、10、11、12、13 | 前端 | `npm run lint` + `npm run build`；浏览器端到端由 Task 4 覆盖 |
| 14 | 契约检查 | 路由表中无感想编辑端点；前端无编辑控件 |
| 15 | `test_architecture.py` + Grep | 后端 `datetime.now(` 仅 `clock.py`；前端 `new Date(` 仅 `api/client.ts` / `hooks/useServerClock.ts` |
| 16 | 代码审查 | `SettlePage` 不把 `store.settleStep` 当权威；断点只读 summary |

验证命令：

```powershell
# 新增结算/感想测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_settle_summary.py -q

# 后端全量 + 架构棘轮
cd backend; .venv\Scripts\python.exe -m pytest -q

# 迁移漂移确认（无新迁移）
cd backend; .venv\Scripts\alembic.exe check

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

### 8.1 执行结果（已运行通过）

| 环节 | 命令 / 方式 | 结果 |
|---|---|---|
| 后端契约与实现 | `backend/tests/test_settle_summary.py`（Task 2） | 先 RED（14 failed / 1 passed，通过的为既有 `advance`），实现后 **15 passed** |
| 后端全量回归 | `cd backend; .venv\Scripts\python.exe -m pytest -q` | **132 passed** |
| 架构棘轮 | `cd backend; .venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **56 passed** |
| 迁移漂移 | `cd backend; .venv\Scripts\alembic.exe check` | No new upgrade operations（无迁移，符合 §6.2） |
| 前端静态检查 | `cd frontend; npm run lint` | **0 error**（仅既有 `button.tsx` 一条 `react-refresh` warning） |
| 前端构建 | `cd frontend; npm run build` | **通过**（tsc + vite，281.38 kB） |
| 端到端演示验收（Task 4） | 三服务同启 + 浏览器 | 见下 |

端到端验收（用户「小刚」id 34，会话 id 169，有效结束 `duration_sec=360`，`today_total_sec=360`）：

1. `/settle` 显示「本次 6 分钟 · 今天累计 6 分钟」与 starter 原话「打开资料，只看第 1 段」，并落在第①步。—— PASS
2. 填写「今天把推导写完了」提交 → 进入第②步，无错误提示。—— PASS
3. 硬刷新 `/settle` → 仍停在第②步（`settle_step=1`），摘要数字不变，未回到第①步。—— PASS（Spec Task 3 延后的断点验收）
4. 依次跳过 ②③④ → 出现「5 分钟的星星，是你自己点亮的。」+「再学一场」「回到首页」。—— PASS
5. 落库核对：`reflections` 该会话恰 **1** 条；`sessions` 为 `settle_step=4, status="settled"`，刷新后未重复 +1。—— PASS
6. 契约核对：OpenAPI 只有 `GET /api/sessions/{id}/summary`、`POST /api/sessions/{id}/reflection`，无感想编辑/删除端点；前端 `new Date(` 仍只出现在 `api/client.ts` 与 `hooks/useServerClock.ts`；`SettlePage` 未以 `store.settleStep` 作断点权威。

提交：Spec `83fc988`、后端 `ce323f1`、前端 `d879bc7`、回填本文件（本提交）。

### 8.2 未验证项

- **跨零点真实运行**：归属日跨零点仅由 `test_summary_attribution_day_across_midnight`（23:30 / 00:30 参数化）覆盖，未在真实服务上等到零点手工验证。
- **多客户端并发抢写感想**：Spec §6.2 已声明 Demo 单客户端、不加唯一约束；并发双写不保证只落一条。
- **投递 / 信箱 / 回顾真实逻辑**：本计划只给占位卡片，真实行为属 P6/P7，未验收。
- **星星亮度、连续天数、动画**：`star_level` / `streak` 恒 `null`，属 P5，未验收。

### 8.3 遗留问题与已知边界

- 第④步完成（`status="settled"`）后**整页刷新**会回首页：`GET /current` 不返回 settled 会话，内存 `currentSessionId` 也不持久化（Spec §6.3 已声明；Task 4 当次页面内走完不受影响）。
- `reflection_service.save` 按计划接口保留 `clock` 参数，但 `Reflection.date` 取会话 `started_at` 归属日，不取写入时间（以 docstring 说明）。
- 为统一「可访问会话状态」口径，`settle_service` 的私有常量改为公开 `SETTLEABLE_STATUSES`，由 session / reflection 服务复用（语义不变）。
- 演示环境：本机 `python -m app.main` 带 WatchFiles 热重载；改动后需确认 OpenAPI 已出现新路由再联调（本次曾遇到旧进程占用 8000 导致新路由缺失，重启后恢复）。

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 契约（`schemas/session.py`）→ 无迁移 → 业务（新增 `reflection_service.py`，复用 `settle_service.py`）→ 接口（`routers/session.py`）→ 前端（`pages/SettlePage.tsx` + `features/settle/`）。
> 2. **当前 owner 在哪里？** 结算断点 owner 是 `sessions.settle_step` + `settle_service.advance`；感想 owner 是 `reflections` 表 + 新增 `reflection_service`；时间 owner 是 `app/clock.py`；前端 HTTP 入口是 `api/client.ts`。
> 3. **是否引入重复状态或平行写入？** 否。感想只有 `reflection_service.save` 一条写入路径；`settle_step` 只有 `settle_service.advance` 一条推进路径；前端不另存断点、不伪造星星/连续天数。
> 4. **是否影响接口和其他模块？** 新增两个端点；`summary` 的 `today_total_sec` 与 P5 统计口径一致（仅 `completed/settled` 且 `ended_at` 非空）；占位字段名 `star_level`/`streak`/`received_during_session` 是 P5/P6 的扩展点，不得改名。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮、后端全量测试、`alembic check`、前端 lint + build、Task 4 演示验收。
