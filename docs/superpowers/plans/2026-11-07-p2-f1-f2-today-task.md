# P2 · F1+F2 今日任务与模型拆分实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。

**Goal:** 首页输入一句话（或点示例标签）→ 点「分析」→ 得到 starter + 0–3 步后续步骤；拆分保存「模型原始版 + 当前采用版」可编辑；每个自然日一个任务；断网/超时降级模板不阻塞；点「开始学习」创建会话进入专注页。

**Architecture:** 把现有「创建即拆分」的 `POST /api/tasks` 重构为三段式：`POST /api/tasks`（草稿）→ `POST /api/tasks/{id}/analyze`（调 splitter，双版本落库）→ `PATCH /api/tasks/{id}`（编辑采用版/标题）。DayTask 加迁移补 `origin_*` 与 `analyzed_text` 列；`GET /api/tasks/today` 是首页唯一数据源（含昨日未完任务提示）。前端用真实首页替换 SmokePanel。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic；React 18 + zustand + Tailwind/shadcn；既有 `llm/`（Mock 默认、8s 超时降级、LRU 缓存）。

**Spec:** [docs/specs/002-f1-f2-today-task.md](../../../docs/specs/002-f1-f2-today-task.md)（执行时从模板复制）。

**Depends on:** P1（请求头身份、`apiClient` 注入、AccountSwitcher）。

**Produces（后续计划依赖的接口）:**
- `GET /api/tasks/today` → `{task: {id, raw_text, starter_step, steps, origin_starter_step, origin_steps, analyzed, locked, source} | null, carry_over: {raw_text} | null, server_time}`。
- `POST /api/tasks` `{raw_text}` → 今日任务草稿（201；已存在 → 200 返回现有）。`raw_text` 1–200 字。
- `POST /api/tasks/{id}/analyze` → `{starter_step, steps, source, server_time}`，双版本落库。
- `PATCH /api/tasks/{id}` `{raw_text?, starter_step?, steps?}` → 更新采用版；有进行中/完成会话 → 409 `{code:"TASK_LOCKED"}`。
- DayTask 判定口径（P3+ 共用）：`analyzed = analyzed_text is not null`；`locked = 存在该任务会话`；状态派生不落列。

## Global Constraints

- 同 P1 全部；另：LRU 缓存只在单进程有效，禁止多 worker 启动；PowerShell 冒烟用 `Invoke-RestMethod` 不用 `curl.exe`。
- 触发方式：只有点「分析」才调 splitter，禁止随输入自动调用；降级标注 `source="fallback"`。

## Review Focus

1. 空输入 / 纯空格 / 超 200 字 → 422，不落库（Task 2 钉住）。
2. 模型超时/报错/返回空 → 200 + `source="fallback"` + 模板结果，流程不阻塞（Task 2 钉住，调用方注入会抛异常的 splitter）。
3. 同一标题连点「分析」→ splitter 只被调用一次（LRU 缓存，Task 2 用计数 fake 钉住）。
4. 分析后改标题 → 拆分保留、`analyzed=false` 提示可重新分析，**不自动清空不重调**（Task 2+3 钉住）。
5. 计时开始后再编辑 → 409，防止「学着学着换任务」（Task 2 钉住）。

---

### Task 1: 写 Spec 002

- [ ] **Step 1:** 从模板复制填写：范围=F1+F2 全部规则（含 A15/A21/A22）；非目标=专注页 UI（P3）、star/streak（P5）；验收条件对应 brainstorming F1/F2 演示验收与 Review Focus 5 条；第 6 节写明 `POST /api/tasks` 响应结构变更与 DayTask 三列迁移。
- [ ] **Step 2: Commit** `docs: spec 002 f1-f2 today task`

### Task 2: 后端三段式任务接口 + 迁移

**Files:**
- Create: `backend/tests/test_task_api.py`、`backend/alembic/versions/<new>_daytask_versions.py`
- Modify: `backend/app/models/day_task.py`、`backend/app/schemas/task.py`、`backend/app/routers/task.py`、新建 `backend/app/services/task_service.py`（新领域服务文件，Spec 写理由）

**Interfaces:**
- Consumes: P1 的 `get_current_user_id`、`get_clock`；`get_splitter(settings).split(text, date)`。
- Produces: 本计划头部 Produces 列出的 4 个端点；`task_service.get_today(db, user_id, clock)`、`create_draft(db, user_id, raw_text, clock)`、`analyze(db, task_id, splitter, clock)`、`update_task(db, task_id, fields)`。

- [ ] **Step 1: 写失败测试**（每个用例独立）

```python
async def test_create_draft_then_get_today(client, headers): ...  # 草稿 analyzed=False, starter 为空
async def test_create_duplicate_returns_existing(client): ...       # 同日第二次 → 200 同 id
async def test_empty_and_over_200_rejected(client): ...             # "" / " "*3 / 201 字 → 422
async def test_analyze_stores_both_versions(client): ...            # origin==adopted，source in {mock,llm,fallback}
async def test_analyze_fallback_on_splitter_error(client, monkeypatch): ...  # 抛异常 → 200, source="fallback"
async def test_analyze_cache_reuse(client, counting_splitter): ...  # 同标题两次 analyze → 调用计数==1
async def test_patch_edits_adopted_only(client): ...                # 改 starter/steps，origin 不变
async def test_patch_title_keeps_split_sets_unanalyzed_hint(client): ...  # analyzed_text 不动，响应 hint 字段或前端比对
async def test_patch_locked_after_session_start(client): ...        # 先建 session 再 PATCH → 409 TASK_LOCKED
async def test_carry_over_yesterday_unfinished(client): ...         # 昨天有任务无有效会话 → carry_over 非空
```

- [ ] **Step 2:** 跑确认全 FAIL（沙箱外）。
- [ ] **Step 3:** 模型加 `origin_starter_step`/`origin_steps`/`analyzed_text`（nullable）→ `alembic revision --autogenerate` 人工核对 → `downgrade base` + `upgrade head` 双向通过；实现 service 与 router（router 只解析转发）。
- [ ] **Step 4:** 测试全 PASS + 棘轮 + `test_session_api.py` 回归（其建任务流程改走新接口，可修调用不改断言语义）。
- [ ] **Step 5: Commit** `feat(backend): task draft/analyze/edit with dual-version split`

### Task 3: 首页真实 UI（替换 SmokePanel）

**Files:**
- Create: `frontend/src/features/task/TaskComposer.tsx`（输入+标签+分析）、`SplitEditor.tsx`（starter/steps 编辑）
- Modify: `frontend/src/pages/HomePage.tsx`（删除 SmokePanel 挂载）、删除 `frontend/src/features/SmokePanel.tsx`

**Interfaces:**
- Consumes: Task 2 全部端点；P1 store `userId`。
- Produces: 「开始学习」按钮：`POST /api/sessions {task_id}` → store `currentSessionId` → `navigate("/focus")`（P3 在此页面继续；store 需加 `currentSessionId: number | null`，本任务一并加入并持久化）。

- [ ] **Step 1:** `TaskComposer`：受控输入（maxLength 200、空值禁用分析按钮）+ 4 个示例标签（"背 20 个单词""复习三角函数""改一段代码""读 10 页书"）；昨日未完提示条 +「接着来」预填按钮（不自动继承）。
- [ ] **Step 2:** `SplitEditor`：展示 starter（可编辑）与 steps 列表（每条可编辑/删除，≤3 条）；`source="fallback"` 时顶部轻描提示「智能拆分暂不可用，先用通用路线」；`raw_text != analyzed_text`（响应 `analyzed=false`）时提示「标题已修改，可重新分析」。
- [ ] **Step 3:** 「开始学习」：未 analyze 禁用；点击走 Produces 的会话创建并跳转。
- [ ] **Step 4:** `npm run lint` + `npm run build` 通过（基线不变）。
- [ ] **Step 5: Commit** `feat(frontend): home task composer with split editor`

### Task 4: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启 + reset seed，走 F1/F2 演示验收：10 秒内输入/点选任务并看到拆分；改标题出现「可重新分析」；编辑 starter 后刷新仍在；降级路径由 pytest 覆盖 + 手工把 `llm_provider` 指向不可用地址验一次 fallback 标注。
- [ ] **Step 2:** 全量后端测试 + 棘轮 + lint/build。
- [ ] **Step 3:** 回填 Spec 第 8 节。
- [ ] **Step 4: Commit** `docs: backfill spec 002 results`
