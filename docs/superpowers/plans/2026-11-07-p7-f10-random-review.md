# P7 · F10 随机回顾实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。

**Goal:** 结算第④步（①②③走完后自动出现，无需用户操作）：从自己过去有效场次随机抽一条，以「过去的你」卡片展示日期 + 任务原文 + 感想（无感想只显示任务原文）；排除本场与当天所有场次；无历史时只显示一句「等待宇宙的讯息」；点击卡片跳对应日期记录（P8 填详情，本计划链接到既有 `/records` 占位路由）。

**Architecture:** 后端新增 `GET /api/review/random`：候选池 = 当前用户 `status IN ('completed','settled') AND ended_at IS NOT NULL` 且归属日（`cast(func.timezone("Asia/Shanghai", Session.started_at), Date)`）< 今天的会话，排除 query 传入的本场 id；`ORDER BY random() LIMIT 1`，left join Reflection 与 DayTask。前端替换 P4 占位 `StepReview.tsx`（props 契约不变）。

**Tech Stack:** FastAPI + SQLAlchemy；React 18。

**Spec:** [docs/specs/007-f10-random-review.md](../../../docs/specs/007-f10-random-review.md)（执行时从模板复制）。

**Depends on:** P4（StepReview 占位契约、advance 流程）、P3（有效会话语义、归属日口径）。

**Produces（后续计划依赖的接口）:**
- `GET /api/review/random?exclude_session_id=<int>` → `{item: {session_id, date, task_text, reflection: string | null} | null, server_time}`。
- 前端跳转约定：`/records?date=<YYYY-MM-DD>`（P8 的记录页必须支持该 query 直开单日视图）。

## Global Constraints

- 同 P1 全部；另：候选只取有效场次（`status IN ('completed','settled') AND ended_at IS NOT NULL`；`discarded` 与仍在进行 / 仅达里程碑但未结束的场次均排除）；归属日 = `started_at` 的 Asia/Shanghai 日期；空态文案逐字「等待宇宙的讯息」，不加额外引导。

## Review Focus

1. 当天只有这一场 → 池空 → `item=null`，前端只显示空态句（Task 2 钉住）。
2. 排除正确性：本场 id 与当天其他场次都不得入选（Task 2 用「池内只剩 1 条候选」断言抽中必为那条钉住）。
3. 无感想的场次 → `reflection=null`，前端不渲染空白框（Task 2 + Task 3）。
4. 跨零点场次归属开始日：昨天 23:58 开始的场次今天可被抽到（Task 2 Clock 注入钉住）。
5. 每场结算只拉取一次（组件 mount 拉取，不随轮询重复换卡片，Task 3 手工验证）。

---

### Task 1: 写 Spec 007

- [ ] **Step 1:** 从模板复制填写：范围=F10 全部规则；非目标=记录详情页本身（P8）、不重复保证（明确「每次随机，不保证不重复」）；验收条件对应演示验收「账号 A 结算末步出现 6 天种子中某一天，点击可跳」。
- [ ] **Step 2: Commit** `docs: spec 007 f10 random review`

### Task 2: 后端 random review 接口

**Files:**
- Create: `backend/app/routers/review.py`、`backend/app/schemas/review.py`、`backend/app/services/review_service.py`（新领域文件，Spec 写理由）、`backend/tests/test_review.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: P1 `get_current_user_id`、`get_clock`；Session/Reflection/DayTask 模型。
- Produces: 本计划头部 Produces 的端点；`review_service.random_past(db, user_id, exclude_session_id, clock) -> tuple[Session, str, str | None] | None`。

- [ ] **Step 1: 写失败测试**

```python
async def test_excludes_today_and_self(client): ...        # 池内唯一合格候选必被抽中；当天场次与本场不入选
async def test_empty_pool_returns_null(client): ...        # 新账号只有今天一场 → item is None
async def test_reflection_nullable(client): ...            # 无感想候选 → reflection is None
async def test_discarded_excluded(client): ...             # 昨天的 discarded 不入选
async def test_cross_midnight_attribution(client): ...     # 昨天 23:58 开始的有效场今天可被抽到
async def test_ongoing_completed_excluded(client): ...     # 昨天开始的 completed 但 ended_at=NULL（仍在学）不入选
```

- [ ] **Step 2:** 跑确认 FAIL（沙箱外）。
- [ ] **Step 3:** 实现 service/router（router 只解析转发）；`main.py` 注册。
- [ ] **Step 4:** 测试全 PASS + 棘轮 + 全量回归。
- [ ] **Step 5: Commit** `feat(backend): random review excluding today and self`

### Task 3: StepReview 真实组件

**Files:**
- Modify: `frontend/src/features/settle/StepReview.tsx`（替换占位，props 契约 `{sessionId, onDone}` 不变）

**Interfaces:**
- Consumes: Task 2 端点；`POST /api/settle/{id}/advance`。
- Produces: `/records?date=` 跳转约定（P8 消费）。

- [ ] **Step 1:** 组件 mount 时拉一次 `GET /api/review/random?exclude_session_id={sessionId}`；`item=null` → 只渲染「等待宇宙的讯息」。
- [ ] **Step 2:** 有 item → 「过去的你 · {date}」卡片：任务原文 +（有感想才渲染）感想；整卡可点 → `navigate("/records?date=" + date)`。
- [ ] **Step 3:** 「完成」按钮 → advance 到 4 → `onDone`（P4 流程接宇宙音讯）。
- [ ] **Step 4:** `npm run lint` + `npm run build` 通过。
- [ ] **Step 5: Commit** `feat(frontend): settle step four random review card`

### Task 4: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启 + reset seed + 演示阈值：小明完成一场走到第④步 → 出现 6 天种子中某一天的任务与感想；点击卡片跳到 `/records?date=...`（占位页允许，P8 填详情）；换新账号小刚完成首场 → 只显示「等待宇宙的讯息」。
- [ ] **Step 2:** 全量后端测试 + 棘轮 + lint/build。
- [ ] **Step 3:** 回填 Spec 第 8 节。
- [ ] **Step 4: Commit** `docs: backfill spec 007 results`
