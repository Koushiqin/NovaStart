# 002 · F1+F2 今日任务与模型拆分

> 来源：[brainstorming.md](../../brainstorming.md) F1/F2、A15/A21/A22；执行计划：[2026-11-07-p2-f1-f2-today-task.md](../superpowers/plans/2026-11-07-p2-f1-f2-today-task.md)。前置 Spec：[001 · F9 多账号](./001-f9-multi-account.md)。

## 1. 背景与目标

当前 `POST /api/tasks` 是「创建即拆分」：收到文本立刻调 splitter 并落库，没有草稿态、没有「分析」显式触发、没有模型原始版 / 学生采用版的双版本、没有「一个自然日一个任务」与计时后锁定的语义；首页仍是临时 `SmokePanel`。

目标：把首页换成真实的「今天想学什么」入口——输入一句话或点示例标签 → 点「分析」→ 得到 1 个 5 分钟 starter + 0–3 步后续路线；学生可编辑采用版；每个自然日只有一条任务；分析后改标题保留旧拆分并可重新分析；计时开始后锁定；断网 / 超时降级模板不阻塞；点「开始学习」创建会话进入专注页（专注页 UI 归 P3）。

## 2. 范围与非目标

- 范围：
  - **F1 今日任务**：每个自然日只有一个任务；当天首次输入即建草稿；计时开始前可反复编辑、计时开始后锁定；输入去首尾空白后 1–200 字，空输入不触发生成；昨日未完成任务显示「昨天没走完，今天要不要接着来？」+「接着来」预填输入（不自动继承）。
  - **F2 模型拆分**：只有点「分析」才调用 splitter，不做随输入自动调用；输出 1 个 starter（5 分钟内可执行的具体动作）+ 0–3 个后续步骤；starter / steps 可手动编辑、可删步骤（A15）；同时保存「模型原始版」与「当前采用版」（A21，结算复述用采用版，复述实现在 P4）；分析后改标题保留拆分、提示可重新分析、不自动清空不重调（A22）；超时 / 报错 / 返回空 / 不合规 → 规则模板降级并标注「智能拆分暂不可用，先用通用路线」。
  - **首页真实 UI**：`TaskComposer` 输入 + 4 个示例标签 + 分析；`SplitEditor` 展示与编辑 starter/steps；替换并删除 `SmokePanel`。
  - **开始学习**：未分析禁用；点击创建 session、记录 `currentSessionId`、跳转 `/focus`（专注页本体归 P3）。
- 非目标（明确不做的）：
  - 专注页 UI、正计时、5 分钟里程碑、180 分钟自动结束（P3）。
  - 星星 / 连续天数 / 亮度与可视化（P5）。
  - 结算四步、感想、信件、随机回顾、记录查询（P4 / P6 / P7 / P8）。
  - 真实模型接入与 prompt 调优（沿用既有 `llm/`，只补输出二次校验口径）；多进程部署（LRU 仅单进程有效）。
  - 历史任务列表 / 跨日任务查询；预计分钟数的展示（本计划 `steps` 只存文案）。

## 3. 可测试的验收条件

1. 首页输入一句话（或点示例标签）后点「分析」，10 秒内看到 1 个 starter + 0–3 个后续步骤（F1/F2 演示验收）。
2. 只有点「分析」才调用 splitter：仅输入不触发；未分析时 `GET /api/tasks/today` 返回草稿 `analyzed=false`、`starter_step=""`、`steps=[]`。
3. 空输入 / 纯空白 / 去首尾空白后超过 200 字 → `422`，且不落库；去空白后 1–200 字 → 成功建草稿。
4. 同一账号同一自然日重复 `POST /api/tasks` → `200` 返回既有任务（同 id、不新建）；不同账号当日任务互不可见。
5. `POST /api/tasks/{id}/analyze` → `200`，双版本落库（`origin_starter_step == starter_step`、`origin_steps == steps`），`source ∈ {llm, mock, fallback}`；同一标题连点「分析」splitter 只被调用一次（先复用已存采用版，LRU 为第二道缓存）。
6. splitter 抛异常 / 超时 / 返回空或不合规 → `200` + `source="fallback"` + 模板拆分，接口不阻塞；降级后仍可 analyze → 开始学习。
7. 编辑采用版（starter / steps）→ 仅 adopted 变化，origin 不变；刷新后仍是编辑后的版本。
8. 分析后修改标题 → 旧拆分保留（origin / adopted 不清空）、不重调 splitter、响应 `split_stale=true`，界面提示「标题已修改，可重新分析」。
9. 计时开始后（已存在该任务的任意 session）`PATCH` 与 `analyze` → `409`，`code="TASK_LOCKED"`；未开始时编辑正常。
10. 昨天有任务且无 `completed` / `settled` 会话，且今天还没有任务 → `GET /api/tasks/today` 返回 `carry_over`；前端显示提示条，「接着来」只预填输入、不自动继承。
11. 「开始学习」在未分析时禁用；分析后点击 → `POST /api/sessions` 成功、store 记录 `currentSessionId`、跳转 `/focus`。
12. 账号 A 的任务对账号 B 不可见；B 对 A 的任务 `PATCH` / `analyze` → `404`。
13. 断网 / 超时降级状态下，F2 演示验收的「开始」环节可走通（5 分钟与完成由 P3 端到端覆盖，本计划只保证降级路径不阻塞进入开始）。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/day_task.py` | DayTask 权威定义（任务文本 / 双版本 / 日期） | 新增 4 个可空列（见第 6 节），不改现有 NOT NULL 列 |
| `backend/alembic/versions/<new>_daytask_versions.py`（新增） | 表结构迁移 | autogenerate 后人工核对；双向迁移通过 |
| `backend/app/schemas/task.py` | API 契约唯一真相源 | 重写为 `TaskCreate` / `TaskUpdate` / `TaskState` / `AnalyzeResult` / `TodayResponse` |
| `backend/app/routers/task.py` | HTTP 解析与转发 | 新增 `GET /today`、`POST /{id}/analyze`、`PATCH /{id}`；`POST ""` 改为建草稿；不写业务规则 |
| `backend/app/services/task_service.py`（新增） | 今日任务判定与事务边界 | 新建理由：旧 router 内直接调 splitter / 落库，拆分后「当天唯一、双版本、锁定、carry_over」需复用且必须在事务内，architecture 要求 router 不碰业务 |
| `backend/app/llm/` | 拆分器与 LRU 缓存 owner | 复用 `get_splitter(settings).split(text, date)`；输出二次校验口径见第 6 节 |
| `backend/tests/test_task_api.py`（新增） | 接口与规则测试 | 覆盖第 3 节验收条件 |
| `backend/tests/test_session_api.py` | 既有回归 | 建任务流程改走「草稿 + analyze」，断言语义不变 |
| `frontend/src/features/task/TaskComposer.tsx`（新增） | 首页输入与示例标签 | 受控输入（maxLength 200、空值禁用）+ 昨日提示条 |
| `frontend/src/features/task/SplitEditor.tsx`（新增） | 拆分结果展示与编辑 | starter / steps 编辑、降级与 `split_stale` 提示 |
| `frontend/src/pages/HomePage.tsx` | 首页路由页 | 替换 `SmokePanel` |
| `frontend/src/features/SmokePanel.tsx` | 临时冒烟组件 | 删除 |
| `frontend/src/store/app.ts` | 前端身份 / 会话状态 owner | 新增 `currentSessionId` 并持久化 |
| `frontend/src/api/client.ts`、`hooks/useServerClock.ts` | 唯一 HTTP / 时间入口 | 不改，复用 |

## 5. 实现步骤

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：改 `schemas/task.py` 与 `models/day_task.py`，字段覆盖第 3 节全部验收条件。
3. **迁移（六步②）**：`alembic revision --autogenerate` → 人工核对 → `downgrade base` + `upgrade head` 双向通过。
4. **业务（六步③）**：先写 `tests/test_task_api.py` 失败用例（见第 7 节），确认 FAIL；实现 `task_service.py`：`get_today` / `create_draft` / `analyze` / `update_task`，事务在 service 内闭合；同步修 `test_session_api.py` 的建任务调用。
5. **接口（六步④）**：`routers/task.py` 只解析转发，`main.py` 无需新增注册（同 router）；`/docs` 手工冒烟。
6. **前端（六步⑤）**：`TaskComposer` + `SplitEditor` + `HomePage` 替换，删除 `SmokePanel`；store 加 `currentSessionId`；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启 + reset seed，按 F1/F2 演示验收走一遍；手工把 `llm_provider` 指向不可用地址验一次 fallback 标注。
8. 回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 契约

`TaskState`（`GET /today`、`POST ""`、`PATCH` 共用）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int | 任务 id |
| `raw_text` | str | 当前标题（采用版输入） |
| `starter_step` | str | 当前采用版 starter；草稿为 `""` |
| `steps` | list[str] | 当前采用版后续步骤；0–3 条；草稿为 `[]` |
| `origin_starter_step` | str \| null | 模型原始版 starter；未分析为 `null` |
| `origin_steps` | list[str] \| null | 模型原始版 steps；未分析为 `null` |
| `analyzed` | bool | `analyzed_text is not null`（是否分析过） |
| `split_stale` | bool | 已分析且 `raw_text != analyzed_text`（标题已改，可重新分析） |
| `locked` | bool | 存在该任务的任意 session |
| `source` | `"llm"` \| `"mock"` \| `"fallback"` \| null | 拆分来源；未分析为 `null` |

端点：

1. `POST /api/tasks`，body `TaskCreate {raw_text}`：
   - 去首尾空白后长度 1–200，否则 `422`，不落库；落库保存去空白后的文本。
   - 今天已有任务 → `200` 返回 `{task: TaskState, server_time}`（同 id，不新建、不改文本）；否则插入草稿 → `201`。
   - 草稿：`starter_step=""`、`steps=[]`、`origin_* = null`、`analyzed_text = null`、`split_source = null`。
2. `POST /api/tasks/{id}/analyze`：
   - 非本人任务 → `404 {"code":"TASK_NOT_FOUND"}`；`locked` → `409 {"code":"TASK_LOCKED"}`（错误体沿用 FastAPI `detail` 包封）。
   - 已分析且 `analyzed_text == raw_text` → 直接返回已存采用版，不调用 splitter。
   - 否则调 `get_splitter(settings).split(raw_text, today.isoformat())`；结果二次校验与截断（starter 去空白非空且 ≤60 字、steps 每项去空白非空且最多 3 条），不合规或抛异常 → 用 `MockSplitter` 结果并标 `source="fallback"`。
   - 落库：`origin_starter_step/origin_steps`、`starter_step/steps`、`split_source`、`analyzed_text = raw_text` 同事务写入。
   - 响应：`{starter_step, steps, source, server_time}`。
3. `PATCH /api/tasks/{id}`，body `TaskUpdate {raw_text?, starter_step?, steps?}`：
   - 非本人任务 → `404`；`locked` → `409 TASK_LOCKED`。
   - 只改采用版字段；`origin_*`、`analyzed_text`、`split_source` 不动；改 `raw_text` 不触发重新分析。
   - `raw_text` 去空白后 1–200；`starter_step` 去空白后 ≤200；`steps` 每项非空且最多 3 条，允许 `[]`。
   - 响应：`{task: TaskState, server_time}`。
4. `GET /api/tasks/today`：
   - 响应 `{task: TaskState | null, carry_over: {raw_text, date} | null, server_time}`。
   - `carry_over` 仅在今天无任务时返回：取昨天该账号的任务，且不存在 `status ∈ (completed, settled)` 的会话。
   - `locked` 派生自 `sessions` 表，不落列。

### 6.2 数据与迁移

- `day_tasks` 新增 4 个可空列：`origin_starter_step String(200)`、`origin_steps JSONB`、`analyzed_text Text`、`split_source String(20)`（`llm` / `mock` / `fallback`）。
- 现有列不改可空性与类型；草稿以 `starter_step=""`、`steps=[]` 表达，靠 `analyzed` 区分状态，**状态不落列**。
- 既有行（种子历史任务）新列保持 `NULL`（等价 `analyzed=false`）；今日任务由首页新建，无需数据回填；如需演示历史任务的已分析态，用 `/dev/reset-seed` 重建演示数据。
- 同日唯一：service 先查后插，不加数据库唯一约束（Demo 单客户端，计划范围外）。
- 拆分缓存仍在 `llm/` 模块级 LRU（键「任务文本\|日期」，容量 128），不落库；禁止多 worker 启动。

### 6.3 兼容性

- **破坏性变更（内部 Demo 接口，按 AGENTS.md 流程在本计划内确认）**：`POST /api/tasks` 从「创建即拆分」改为「建草稿」，响应由 `{task_id, starter_step, steps, source, server_time}` 改为 `{task: TaskState, server_time}`，状态码 201 / 已存在 200。无外部消费者；`SmokePanel` 删除，`test_session_api.py` 的建任务 helper 同步改为「草稿 + analyze」。
- 身份仍由 `X-User-Id` 请求头注入（P1），新端点不新增 body / query 的 `user_id`。
- 前端 store 新增 `currentSessionId: number | null`，`persist` 的 `partialize` 扩为 `{ userId, currentSessionId }`，key 仍为 `novastart-user`。
- `server_time` 仍由 `Clock`（`Depends(get_clock)`）产出；前端只经 `api/client.ts` 与 `hooks/useServerClock.ts` 取时间。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（测试文件 `backend/tests/test_task_api.py`）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 2、4 | `test_create_draft_then_get_today` | 草稿 `analyzed=false`、`starter_step=""`、`steps=[]` |
| 4 | `test_create_duplicate_returns_existing` | 同日第二次 → `200`、同 id |
| 3 | `test_empty_and_over_200_rejected` | `""` / `"   "` / 201 字 → `422`，库中无行 |
| 5 | `test_analyze_stores_both_versions` | `origin == adopted`，`source ∈ {mock, llm, fallback}` |
| 6 | `test_analyze_fallback_on_splitter_error` | 注入抛异常 splitter → `200`、`source="fallback"`、有 starter/steps |
| 5 | `test_analyze_cache_reuse` | 计数 splitter：同标题两次 analyze → 调用计数 == 1 |
| 7 | `test_patch_edits_adopted_only` | 改 starter/steps → adopted 变、origin 不变 |
| 8 | `test_patch_title_keeps_split_sets_stale` | `analyzed_text` 不动、`split_stale=true`、不重调 splitter |
| 9 | `test_patch_locked_after_session_start` | 先建 session 再 PATCH → `409 TASK_LOCKED` |
| 10 | `test_carry_over_yesterday_unfinished` | 昨天任务无 completed/settled 会话 → `carry_over` 非空 |
| 12 | `test_task_not_owned_returns_404` | 账号 B 操作账号 A 的任务 → `404 TASK_NOT_FOUND` |

验证命令：

```powershell
# 新增接口测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_task_api.py -q

# 迁移双向（需 PostgreSQL）
cd backend; .venv\Scripts\alembic.exe downgrade base; .venv\Scripts\alembic.exe upgrade head

# 后端全量 + 架构棘轮 + 时钟棘轮
cd backend; .venv\Scripts\python.exe -m pytest -q

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

（实现完成后回填：跑了哪些命令、结果如何；区分「测试已编写」与「测试已运行通过」；未验证项与遗留问题。）

---

> **结构性变更五问**
>
> 1. **修改哪一层？** `schemas/` + `models/` → Alembic 迁移 → `services/` → `routers/` → 前端 `features/` `pages/` `store/`，按 dev-order 六步顺序。
> 2. **当前 owner 在哪里？** `DayTask` 表与 `models/day_task.py` 是任务事实 owner；今日任务判定新增 `task_service.py` 为唯一业务入口；「当前时间」仍是 `Clock`；前端身份仍是 zustand `userId`。
> 3. **是否引入重复状态或平行写入？** 否。`analyzed` / `locked` / `split_stale` 全部派生不落列；双版本是需求要求的两个事实，各自只有 `task_service.analyze` 一条写入路径。
> 4. **是否影响接口和其他模块？** 是。`POST /api/tasks` 契约与语义破坏性变更（内部 Demo 接口）；`test_session_api.py` 调用方式同步；`SmokePanel` 删除；P3 的「开始学习」将消费本接口的 `TaskState` 口径。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮（依赖方向、Clock 唯一时间源）、后端全量测试、Alembic 双向迁移、前端 lint + build。
