# P4–P6 遗留项收口 Implementation Plan

> **For agentic workers:** 按任务序执行；后端任务 TDD（失败测试 → 实现 → 通过 → commit）。步骤用 `- [ ]` 跟踪。后端连库命令必须沙箱外执行（`dangerouslyDisableSandbox: true`），并先按 AGENTS.md 的 WMI 方式确认 PostgreSQL 已启动。

**Goal:** 收口 [review-fixes-p4-p6.md](../../review-fixes-p4-p6.md)「遗留」5 项：并发测试无强保证、当日累计口径、前端账号快照无自动化测试、操作链路错误文案、progress_service 回退分支健壮性。

**Architecture:** 任务 1–2 动后端服务/测试（`letter_service.send` 的锁结构不变，仅补确定性回归；`progress_service` 补两处回退分支语义）；任务 3 为 `/summary` 追加 `attribution_date` 并改结算页文案；任务 4 只改 `MailboxPage`（操作链路快照 + 409 文案），遗留 1 的 refresh 守卫已存在、以结构审查 + 人工手测收口；任务 5 全量验证并回填清单。**不新增前端依赖**（用户已确认不引入 Vitest）。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + pytest（FixedClock 注入、双引擎并发）+ React 18（无新增依赖）。

**Spec:** [review-fixes-p4-p6.md](../../review-fixes-p4-p6.md)（契约依据仍为 specs 004/005/006；本计划不改四态、streak 结构、settle_step 语义）。

## Global Constraints

- 后端时间只走 `app/clock.py` 的 `Clock`；测试用 `FixedClock` 经 `get_clock` 注入，业务时间禁止 sleep 墙钟。
- 测试库固定 `novastart_test`；不改启动方式（`python -m app.main`）；前后端都不新增依赖。
- 依赖方向 `routers → services → models`；不得放宽 `tests/test_architecture.py` 棘轮。
- 前端 HTTP 只走 `src/api/client.ts`；前端取时间只用 `src/hooks/useServerClock.ts`。
- 只修本清单 5 项，不顺手重构；每任务结束跑该文件全量测试。

## 已人工确认（2026-11-08）

1. 前端**不新增** devDependencies：遗留 1 不做自动化测试，改为结构审查 + 人工手测（任务 4）。
2. `SessionSummary` 新增 `attribution_date`（additive 契约扩展）**已批准**；Spec 006 §6.5 需补一句。
3. `LETTER_ALREADY_HANDLED` 已于 2026-11-07 获批，本计划只补前端文案区分，不再扩展契约。

## Review Focus

1. **并发屏障的可靠性**：任务 1 用「外部事务先锁 `users` 行」制造确定性阻塞；任务 2 用「未提交插入 + `pg_locks` 轮询」制造唯一键冲突。若 `pg_locks` 未出现 `granted=false`，先查是否被探测会话干扰，不得改成 sleep 猜测。
2. **`was_reset` 语义**：回退分支的 `existed=True` 只在「旧行最后完成日早于昨天」时影响 `was_reset`；同日并发必须仍走早退分支，`current` 不得 +1。
3. **`attribution_date` 与 `server_time` 不同天**：跨零点场次的日期标签必须显示归属日（如 11月6日），不能退回「当日/今天」。
4. **切账号竞态无自动化**：验证以「每个 `setState` 前都有 `accountId` 比对」的结构审查 + lint/build + 人工手测为准，不得声称已被自动化覆盖。
5. **409 无 code 的兜底**：只有 `detail.code === LETTER_ALREADY_HANDLED` 走新文案；其余 409 与未知错误保持原文案与原刷新行为。

---

### Task 1: 并发上限的确定性回归（遗留 3 / T3）

**Files:**
- Modify: `backend/tests/test_letter_send.py`（重写 `test_concurrent_send_only_one_succeeds`，保留函数名以对齐 Spec 006 测试表）
- 不改生产代码（`send` 的 `users` 行锁已存在，本任务把「时序运气」换成结构断言）

**Interfaces:**
- Consumes: `letter_service.send(db, sender_id, session_id, recipient_name, clock) -> tuple[str, int | None]`（签名不变）
- Produces: 无新增公共接口；测试以「是否阻塞在 users 行锁」判定结构

- [ ] **Step 1: 重写测试**

```python
async def test_concurrent_send_only_one_succeeds(db_env, fixed_clock):
    """确定性并发：外部事务先锁收件人 users 行；两笔投递必须先排队再串行计数。"""
    async with db_env() as setup:
        sender_a = await _make_user(setup, "小明")
        sender_b = await _make_user(setup, "小刚")
        recipient = await _make_user(setup, "小美")
        sid_a, _ = await _seed_session(setup, sender_a.id)
        sid_b, _ = await _seed_session(
            setup, sender_b.id, started_at=datetime(2026, 11, 7, 9, 30, tzinfo=SHANGHAI_TZ)
        )
        for i in range(2):
            await _insert_letter(setup, recipient.id, content=f"旧信 {i}")

    async with db_env() as locker:
        # 占住 users 行：修复后的 send 在计数前必须等这把锁；未加锁的实现不会等
        await locker.execute(select(User.id).where(User.id == recipient.id).with_for_update())
        async with db_env() as s1, db_env() as s2:
            pending = asyncio.gather(
                letter_service.send(s1, sender_a.id, sid_a, "小美", fixed_clock),
                letter_service.send(s2, sender_b.id, sid_b, "小美", fixed_clock),
            )
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(pending), timeout=2.0)
            await locker.rollback()
            results = await pending

    assert {r for r, _ in results} == {"delivered", "rejected_full"}
    async with db_env() as check:
        unhandled = await check.scalar(
            select(func.count())
            .select_from(Letter)
            .where(
                Letter.user_id == recipient.id,
                Letter.status == "delivered",
                Letter.handled == False,  # noqa: E712
            )
        )
        assert unhandled == 3
```

- [ ] **Step 2: 跑通并做变异校验（证明测试非空转）**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_send.py::test_concurrent_send_only_one_succeeds -v`
Expected: PASS。

临时注释 [letter_service.py](../../../backend/app/services/letter_service.py#L116) 的 `select(User.id)...with_for_update()` 一行，重跑同一命令。
Expected: FAIL（`TimeoutError` 未出现，两个 send 直接完成）。**恢复该行后再跑一次确认 PASS**。

- [ ] **Step 3: 整文件回归**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_send.py -v`
Expected: 全 PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_letter_send.py
git commit -m "test: 用外部 users 行锁把并发投递上限测试改为确定性回归"
```

### Task 2: progress_service 回退分支健壮性（遗留 5 / T9d）

**Files:**
- Modify: `backend/app/services/progress_service.py:61-71`（`recompute_day` 冲突回退）、`:83-94`（`mark_day_completed` 冲突回退）
- Test: `backend/tests/test_progress.py`（追加两个并发用例 + `pg_locks` 轮询辅助）

**Interfaces:**
- Consumes: `progress_service.mark_day_completed(db, user_id, day) -> Streak`、`recompute_day(db, user_id, day) -> Star | None`（签名不变）
- Produces: 回退分支后 `was_reset` 语义修正为「旧行存在即 True」；两处 `select` 回退到 None 时抛 `RuntimeError`（不再 `AttributeError`）

- [ ] **Step 1: 写失败测试**

在 `test_progress.py` 顶部补 `from sqlalchemy import text`，并追加：

```python
async def _wait_for_ungranted_lock(env, timeout: float = 5.0) -> None:
    """轮询 pg_locks，直到出现 waiting（granted=false）的锁。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        async with env() as probe:
            waiting = await probe.scalar(text("select count(*) from pg_locks where not granted"))
        if waiting:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("未观察到等待中的锁：并发插入没有被阻塞")


async def test_concurrent_first_mark_day_other_day_sets_was_reset(db_env):
    """首次建行并发：先创建「更早日期」行的未提交事务，后到者回退后 was_reset 必须为 True。"""
    async with db_env() as setup:
        user_id = await _make_user(setup)
    older = TODAY - timedelta(days=3)

    async with db_env() as s_a:
        await progress_service.mark_day_completed(s_a, user_id, older)  # 只 flush，不提交
        async with db_env() as s_b:
            pending = asyncio.create_task(
                progress_service.mark_day_completed(s_b, user_id, TODAY)
            )
            await _wait_for_ungranted_lock(db_env)
            await s_a.commit()
            await pending
            await s_b.commit()

    async with db_env() as check:
        streak = await check.scalar(select(Streak).where(Streak.user_id == user_id))
        assert streak is not None
        assert streak.current == 1
        assert streak.was_reset is True   # 修复前为 False
        assert streak.longest == 1
        assert streak.last_completed_date == TODAY


async def test_concurrent_first_mark_day_same_day_single_row(db_env):
    """同日并发首次建行：不抛异常、只有一行、current 仍为 1（早退分支不变）。"""
    async with db_env() as setup:
        user_id = await _make_user(setup)

    async with db_env() as s_a:
        await progress_service.mark_day_completed(s_a, user_id, TODAY)
        async with db_env() as s_b:
            pending = asyncio.create_task(
                progress_service.mark_day_completed(s_b, user_id, TODAY)
            )
            await _wait_for_ungranted_lock(db_env)
            await s_a.commit()
            await pending
            await s_b.commit()

    async with db_env() as check:
        rows = await check.scalar(
            select(func.count()).select_from(Streak).where(Streak.user_id == user_id)
        )
        streak = await check.scalar(select(Streak).where(Streak.user_id == user_id))
    assert rows == 1
    assert streak.current == 1
```

- [ ] **Step 2: 验证失败**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_progress.py::test_concurrent_first_mark_day_other_day_sets_was_reset -v`
Expected: FAIL（`was_reset` 为 `False`）。

- [ ] **Step 3: 实现**

`recompute_day` 的 `except IntegrityError` 分支，回退 `select` 后：

```python
        except IntegrityError:
            star = await db.scalar(select(Star).where(Star.user_id == user_id, Star.date == day))
            if star is None:
                raise RuntimeError("stars 行在唯一键冲突后消失")
```

`mark_day_completed` 的 `except IntegrityError` 分支，回退 `select` 后：

```python
        except IntegrityError:
            streak = await db.scalar(select(Streak).where(Streak.user_id == user_id))
            if streak is None:
                raise RuntimeError("streaks 行在唯一键冲突后消失")
            # 回退说明该行由并发事务创建：账号此前已完成过某天
            existed = True
```

不新增清理/重试逻辑；`recompute_day` 的 None 分支属不可达防御，靠 Code Review 确认（本机 READ COMMITTED 下无法构造）。

- [ ] **Step 4: 验证通过 + 整文件回归**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_progress.py -v`
Expected: 全 PASS（含既有 `test_concurrent_recompute_day_keeps_single_row`）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/progress_service.py backend/tests/test_progress.py
git commit -m "fix: 首次建行并发回退分支修正 was_reset 并补齐 None 兜底"
```

### Task 3: 「当日累计」改为显式归属日（遗留 2 / T6）

**Files:**
- Modify: `backend/app/schemas/session.py:45-58`（`SessionSummary` 加 `attribution_date: str`）
- Modify: `backend/app/services/session_service.py:148`（返回类型加 `str`）、`:196-203`（返回 `attribution_day.isoformat()`）
- Modify: `backend/app/routers/session.py:115-127`（解包并透传 `attribution_date`）
- Modify: `frontend/src/features/settle/SettleSummary.tsx:12-42`（接口字段 + 日期文案）
- Test: `backend/tests/test_settle_summary.py`

**Interfaces:**
- Consumes: 既有 `GET /api/sessions/{id}/summary`
- Produces: `SessionSummary.attribution_date: str`（ISO `YYYY-MM-DD`，上海时区、按 `started_at` 归属日）；`today_total_sec` 语义与口径不变

- [ ] **Step 1: 写失败测试**

`test_settle_summary.py` 中：

```python
async def test_summary_fields(client, db_session, fixed_clock):
    fixed_clock.set_now(datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    sid = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 7, 9, 0, tzinfo=SHANGHAI_TZ)
    )
    ...
    assert data["attribution_date"] == "2026-11-07"
```

新增跨零点用例：

```python
async def test_summary_attribution_date_across_midnight(client, db_session, fixed_clock):
    """凌晨结算昨日开始的场次：日期标签取归属日，不取 clock.today()。"""
    fixed_clock.set_now(datetime(2026, 11, 7, 0, 10, tzinfo=SHANGHAI_TZ))
    user_id = await _make_user(db_session)
    sid = await _seed_session(
        db_session, user_id, started_at=datetime(2026, 11, 6, 23, 50, tzinfo=SHANGHAI_TZ)
    )

    status_code, data = await _summary(client, sid, user_id)

    assert status_code == 200
    assert data["attribution_date"] == "2026-11-06"
    assert data["today_total_sec"] == 300
```

- [ ] **Step 2: 验证失败**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_settle_summary.py::test_summary_fields tests/test_settle_summary.py::test_summary_attribution_date_across_midnight -v`
Expected: FAIL（响应缺 `attribution_date`）。

- [ ] **Step 3: 实现（后端）**

Schema 加字段并在 docstring 注明「归属日累计口径不变」；service 返回元组追加 `attribution_day.isoformat()`（`attribution_day` 已在 [session_service.py](../../../backend/app/services/session_service.py#L173) 计算）；router 解包后传 `attribution_date=attribution_date`。

- [ ] **Step 4: 验证通过（后端整文件）**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_settle_summary.py -v`
Expected: 全 PASS。

- [ ] **Step 5: 实现（前端文案）**

`SettleSummaryData` 加 `attribution_date: string`；渲染改为 `· {dayLabel(data.attribution_date)}累计 {minutes(...)} 分钟`，其中：

```tsx
function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-")
  return `${Number(month)}月${Number(day)}日`
}
```

同文件顶部注释同步为「本次时长 + 本场归属日累计」。

- [ ] **Step 6: 验证前端**

Run: `cd frontend; npm run lint; npm run build`
Expected: lint 0 error（允许既有 `components/ui/button.tsx` 的 react-refresh warning）；build 成功。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/session.py backend/app/services/session_service.py backend/app/routers/session.py backend/tests/test_settle_summary.py frontend/src/features/settle/SettleSummary.tsx
git commit -m "feat: 结算摘要新增 attribution_date，累计文案改为显式归属日"
```

### Task 4: 信箱操作链路快照 + 409 文案（遗留 4）；遗留 1 人工收口

**Files:**
- Modify: `frontend/src/pages/MailboxPage.tsx:54-72`（仅此一处生产改动）
- 遗留 1 的 refresh 守卫（[MailboxPage.tsx](../../../frontend/src/pages/MailboxPage.tsx#L26-L44)）已存在，本任务只做结构审查 + 人工手测，不改代码

**Interfaces:**
- Consumes: 后端 409 契约 `{"detail": {"code": "LETTER_EXPIRED" | "LETTER_ALREADY_HANDLED" | ...}}`
- Produces: `runLetterAction` 切账号后不写 `error`/`busyId`；`LETTER_ALREADY_HANDLED` 显示「这封信已处理，不能再收藏」

- [ ] **Step 1: 实现（无前端测试设施，按结构验收）**

`runLetterAction` 内：动作开始时 `const accountId = useAppStore.getState().userId`（为 null 直接 return）；`await run()` 后、`catch` 内、`finally` 内均以 `useAppStore.getState().userId === accountId` 守卫再写 `setError`/`setBusyId`。错误分支改为：

```tsx
const code = axios.isAxiosError(e)
  ? (e.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code
  : undefined
if (code === "LETTER_ALREADY_HANDLED") {
  setError("这封信已处理，不能再收藏")
} else if (code === "LETTER_EXPIRED" || (axios.isAxiosError(e) && e.response?.status === 409)) {
  setError("这封信已经过了一天")
  await refresh()
} else {
  setError("操作失败，请稍后重试")
}
```

`refresh` 自带快照守卫，无需改动。

- [ ] **Step 2: 结构审查（逐条对 diff）**

Run: `git diff frontend/src/pages/MailboxPage.tsx`
Expected 同时满足：
1. `runLetterAction` 开头捕获 `useAppStore.getState().userId`；
2. `setBusyId(letterId)` 只在账号未变时执行；`finally` 里的 `setBusyId(null)` 带账号比对；
3. 成功路径的 `await refresh()` 与 `catch` 里的所有 `setError` 都在账号比对之后；
4. 409 分支先判 `LETTER_ALREADY_HANDLED`，再判 `LETTER_EXPIRED`/其余 409。

- [ ] **Step 3: 人工手测（遗留 1 + 遗留 4 文案）**

前置：`backend/start-api.bat` 起后端，`cd frontend; npm run dev` 起前端。

1. **遗留 1（refresh 快照）**：登录 A 账号进 `/mailbox`，DevTools Network 切 Slow 4G 后刷新页面，请求未完成时通过右上角切到 B 账号。期望：列表先清空，最终只出现 B 的信；A 的信不出现。
2. **遗留 4（文案分流）**：同一账号开两个 `/mailbox` 标签页，收件箱至少有 1 封信。标签页 1 点「放弃」，标签页 2 点同一封的「收藏」。期望：标签页 2 显示「这封信已处理，不能再收藏」，不是「这封信已经过了一天」。
3. **遗留 4（切账号不串扰）**：标签页 1 点「收藏」前把 Network 设为 Offline，随即切到 B 账号。期望：B 页面不出现任何操作错误文案（`操作失败…` / `这封信…`）。

把 3 条结果记录到任务 5 的清单回填里。

- [ ] **Step 4: 验证**

Run: `cd frontend; npm run lint; npm run build`
Expected: lint 0 error（允许既有 react-refresh warning）；build 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MailboxPage.tsx
git commit -m "fix: 信箱操作链路补账号快照守卫并按 409 code 区分文案"
```

### Task 5: 全量验证与清单回填

**Files:**
- Modify: `docs/review-fixes-p4-p6.md`（「遗留」五项状态、验证证据与 commit SHA）

- [ ] **Step 1: 后端全量**

Run: `cd backend; .venv\Scripts\python.exe -m pytest -q`（沙箱外、PG 已启动）
Expected: 全部 PASS（原 189 + 本计划新增 3 个用例）。

- [ ] **Step 2: 架构棘轮**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py -q`
Expected: PASS（65 项，无新增豁免）。

- [ ] **Step 3: 前端全量**

Run: `cd frontend; npm run lint; npm run build`
Expected: lint 0 error（允许既有 react-refresh warning）；build 成功。

- [ ] **Step 4: 回填清单**

把 `docs/review-fixes-p4-p6.md` 的 5 条遗留改为对应状态，并写明证据：

- 遗留 1 → 人工手测通过（Task 4 Step 3 第 1 条）；**不做自动化**，原因记「无前端单测设施且本次不新增依赖」；
- 遗留 2 → 已收口（`attribution_date` + 「M月D日累计」），Task 3 commit；Spec 006 §6.5 同步一句；
- 遗留 3 → 已补确定性回归（Task 1 外部 users 锁 + 变异校验；Task 2 未提交插入 + `pg_locks`），Task 1/2 commit；
- 遗留 4 → 已修复（操作链路快照 + 409 文案分流），Task 4 commit，人工手测第 2/3 条通过；
- 遗留 5 → 已修复（`was_reset` 回退语义 + 两处 None 兜底），Task 2 commit。

- [ ] **Step 5: Commit**

```bash
git add docs/review-fixes-p4-p6.md
git commit -m "docs: 回填 P4–P6 遗留项修复状态与证据"
```

---

## Self-Review

- **Spec 覆盖**：遗留 1→Task 4（人工）；遗留 2→Task 3；遗留 3→Task 1/2；遗留 4→Task 4；遗留 5→Task 2；验证与记录→Task 5。无遗漏。
- **步骤可判定**：每个代码步给出文件/行/签名；每个测试步给出用例名与断言；每个验证步给出命令与期望输出；无可自动化的前端改动明确标注人工步骤。
- **命名一致**：`attribution_date`（后端字段/前端接口同名）；`_wait_for_ungranted_lock` 仅任务 2 使用；测试函数名 `test_concurrent_send_only_one_succeeds` 保持与 Spec 006 表一致。
- **Review Focus 对应**：第 1–2 条由任务 1/2 的阻塞与早退断言覆盖；第 3 条由任务 3 跨零点用例覆盖；第 4–5 条由任务 4 的结构审查 + 人工手测覆盖。
- **比例**：计划以测试与命令为主，生产代码只给签名与关键分支。
