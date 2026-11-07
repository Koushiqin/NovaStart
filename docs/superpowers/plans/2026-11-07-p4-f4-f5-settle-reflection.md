# P4 · F4+F5 结算四步与感想实现计划

> **For agentic workers:** 按 `.agents/skills/executing-plans` 逐任务执行。步骤用 `- [ ]` 追踪。

**Goal:** 有效结束后进入结算页：一屏看到「本次时长 + 今天累计 + starter 原话复述」；随后固定四步（①感想 → ②投递 → ③信箱 → ④回顾），`settle_step` 断点只进不退、中途离开下次直跳；①完整实现（选填、只读），②③④先给占位卡片可跳过；四步走完显示「来自宇宙的音讯」。

**Architecture:** 后端新增 `POST /api/sessions/{id}/reflection`（写感想 + 事务内推进 settle_step 0→1，重复写 409）与 `GET /api/sessions/{id}/summary`（结算页唯一数据源）。前端 SettlePage 按 `settle_step` 渲染断点步骤；②③④占位组件文件名即 P6/P7 的替换点。

**Tech Stack:** FastAPI + SQLAlchemy（Reflection 模型已存在）；React 18 + zustand；既有 `POST /api/settle/{id}/advance` 条件更新。

**Spec:** [docs/specs/004-f4-f5-settle-reflection.md](../../../docs/specs/004-f4-f5-settle-reflection.md)（执行时从模板复制）。

**Depends on:** P3（end 接口、`settled` 语义、`/settle` 跳转）。

**Produces（后续计划依赖的接口）:**
- `GET /api/sessions/{id}/summary` → `{duration_sec, today_total_sec, task_text, starter_text, settle_step, status, received_during_session: 0, star_level: null, streak: null, server_time}`——`received_during_session` 本计划恒 0（P6 填），`star_level`/`streak` 本计划恒 null（P5 填）；字段名即扩展点，不得改名。
- `POST /api/sessions/{id}/reflection` `{content: string(≤200, 可空白)}` → `{reflection: {content} | null, settle_step: 1, server_time}`；空白 = 跳过不落库；已有感想 → 409 `{code:"REFLECTION_LOCKED"}`。
- 前端组件替换点：`features/settle/StepDeliver.tsx`、`StepMailbox.tsx`、`StepReview.tsx`（P6 替换前两个，P7 替换第三个；占位 props 签名 `{sessionId: number, onDone: () => void}` 不得改）。
- 宇宙音讯文案（A14 定稿）：「5 分钟的星星，是你自己点亮的」。

## Global Constraints

- 同 P1 全部；另：结算只发生一次，`settle_step` 条件更新只进不退；感想只读（A19），不提供任何编辑入口。
- 四步顺序固定，①②③ 可跳过；断点恢复只读 `settle_step`，不在前端另存进度。

## Review Focus

1. 重复提交感想 / 提交后刷新 → 第二次 409，不产生第二条记录（Task 2 钉住）。
2. 空白感想（空串/纯空格）→ 不落库但 settle_step 照样 +1（跳过语义，Task 2 钉住）。
3. 刷新/中途离开后回来 → 直接落在断点步骤，不重复结算（Task 3 手工 + Task 2 接口幂等）。
4. 对 discarded 会话请求 summary/reflection → 404（Task 2 钉住）。
5. `today_total_sec` 只累计有效场次（含本场），discarded 不得计入（Task 2 钉住）。

---

### Task 1: 写 Spec 004

- [ ] **Step 1:** 从模板复制填写：范围=F4 三段式 + 四步框架 + F5 全部规则（含 A14/A19/A21）；非目标=投递/信箱真实逻辑（P6）、回顾真实逻辑（P7）、星星动画（P5）；验收条件对应演示验收「一屏数字、复述、断点续做」与 Review Focus。
- [ ] **Step 2: Commit** `docs: spec 004 f4-f5 settle reflection`

### Task 2: 后端 reflection + summary

**Files:**
- Create: `backend/app/services/reflection_service.py`（新领域服务文件，Spec 写理由）、`backend/tests/test_settle_summary.py`
- Modify: `backend/app/routers/session.py`（挂 summary/reflection 子路由）或新建 `backend/app/routers/reflection.py`（二选一，Spec 写明）、`backend/app/schemas/session.py`

**Interfaces:**
- Consumes: P3 的 end 语义；`settle_service.advance`。
- Produces: 本计划头部 Produces 两个端点；`reflection_service.save(db, session_id, user_id, content, clock) -> Reflection | None`（None=跳过）。

- [ ] **Step 1: 写失败测试**

```python
async def test_summary_fields(client): ...               # duration/today_total/task_text/starter_text(采用版)/settle_step
async def test_summary_today_total_valid_only(client): ...  # 当天另有一场 discarded → 不计入
async def test_summary_discarded_session_404(client): ...
async def test_reflection_save_advances_step(client): ...  # 201, settle_step==1, Reflection.date==started_at 日期
async def test_reflection_blank_skips(client): ...         # "   " → 无记录, settle_step==1
async def test_reflection_repeat_409(client): ...          # 已有感想 → 409 REFLECTION_LOCKED，记录仍一条
async def test_reflection_over_200_422(client): ...
```

- [ ] **Step 2:** 跑确认 FAIL（沙箱外）。
- [ ] **Step 3:** 实现 service（reflection 写入与 `settle_service.advance(db, session_id, 1, user_id)` 同一事务）；summary 的 `today_total_sec` 用 `select(func.sum(duration_sec)).where(user_id, status.in_(("completed", "settled")), cast(started_at, Date)==归属日)`；占位字段按 Produces 常量返回；第④步完成时 `advance(..., 4)` 同事务置 `status="settled"`。
- [ ] **Step 4:** 测试全 PASS + 棘轮 + 全量回归。
- [ ] **Step 5: Commit** `feat(backend): settle summary and one-shot reflection`

### Task 3: SettlePage 四步框架

**Files:**
- Modify: `frontend/src/pages/SettlePage.tsx`
- Create: `frontend/src/features/settle/SettleSummary.tsx`、`StepReflection.tsx`、`StepDeliver.tsx`、`StepMailbox.tsx`、`StepReview.tsx`、`CosmicWhisper.tsx`

**Interfaces:**
- Consumes: 两个新端点 + `POST /api/settle/{id}/advance`；store `currentSessionId`。
- Produces: 占位组件 props 契约（见头部 Produces）；P5 在 `SettleSummary` 预留的 star/streak 槽位填动画。

- [ ] **Step 1:** 进入页面按 `currentSessionId` 拉 summary；`settle_step>=4` → 直接完成态（摘要 + CosmicWhisper）；否则渲染第 `settle_step+1` 步。
- [ ] **Step 2:** `SettleSummary`：「本次 X 分钟 · 今天累计 XX 分钟」+ starter 原话复述（不用「恭喜完成任务」类空话）；star/streak 槽位渲染 null 占位（P5 替换）。
- [ ] **Step 3:** `StepReflection`：textarea（maxLength 200）+「提交感想」/「跳过」→ 提交或空白提交后 `onDone` 刷新 summary。
- [ ] **Step 4:** 三个占位组件统一样式：标题 +「后续版本解锁」说明 +「跳过」按钮（`advance` 到下一步）；第 ④ 步完成后渲染 `CosmicWhisper` 文案 +「回到首页」。
- [ ] **Step 5:** `npm run lint` + `npm run build` 通过；手工验证：走到第 2 步刷新 → 仍落在第 2 步。
- [ ] **Step 6: Commit** `feat(frontend): settle four-step skeleton with reflection`

### Task 4: 端到端联调 + 完成门

- [ ] **Step 1:** 三服务同启 + 演示阈值，走演示验收：有效结束 → 一屏看到时长/累计/复述；写感想 → 跳过 ②③④ → 宇宙音讯出现；中途刷新直跳断点；感想写完刷新不重复 +1。
- [ ] **Step 2:** 全量后端测试 + 棘轮 + lint/build。
- [ ] **Step 3:** 回填 Spec 第 8 节。
- [ ] **Step 4: Commit** `docs: backfill spec 004 results`
