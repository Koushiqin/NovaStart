# P4–P6 审查修复 Implementation Plan

> **For agentic workers:** 按任务序执行；每任务 TDD（失败测试 → 实现 → 通过 → commit）。步骤用 `- [ ]` 跟踪。后端连库命令必须沙箱外执行（`dangerouslyDisableSandbox: true`）且先确认 PostgreSQL 已启动（AGENTS.md 的 WMI 方式）。

**Goal:** 修复 `docs/review-fixes-p4-p6.md` 列出的 1 Critical + 4 Important + Minor 项（#5 补测试折入对应任务，不单列）。

**Architecture:** #1/#2/#3/#7 四项集中在 `letter_service.send` 同一函数，必须串行（主线）；其余前后端小项互不依赖、可派独立子 agent 并行。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + pytest（FixedClock 注入）+ React 18 + Alembic。

**Spec:** [review-fixes-p4-p6.md](../../review-fixes-p4-p6.md)（契约依据：specs 004/005/006；本计划不改 settle_step、四态、streak 结构等既有契约）。

## Global Constraints

- 后端时间只走 `app/clock.py` 的 `Clock`；测试用 `FixedClock` 经 `get_clock` 依赖注入，禁止 sleep 墙钟。
- 测试库固定 `novastart_test`；不改启动方式（`python -m app.main`）、不新增依赖。
- 依赖方向 `routers → services → models`；不得放宽 `tests/test_architecture.py`。
- 改 ORM 模型必须配 Alembic 迁移，autogenerate 产物人工核对后才可 upgrade。
- 前端 HTTP 只走 `apiClient`；前端无单测设施，前端任务验证 = `npm run lint` + `npm run build` + 结构审查。
- 只修清单列出的项，不顺手重构。

## Review Focus

1. 并发修复（T2/T3/T9d）的测试有时序不确定性——屏障无法注入 service 内部；正确性以代码结构（锁与 await 顺序）为准，测试作回归。每个并发修复任务附带「跑两遍全文件」步骤。
2. 跨零点归属日：T6 只改文案不改聚合口径；「当日累计」仍指归属日（`started_at` 的上海时区自然日），属接受口径，回填清单时注明。
3. 切账号竞态（T5）无自动化测试，需人工手测：登录 A 账号进信箱页，加载中途切 B 账号，确认不出现 A 的信件。
4. T9a 新增 409 错误码 `LETTER_ALREADY_HANDLED` 属公开契约扩展——**已于 2026-11-07 经人工批准**，可按计划执行。
5. T9b 迁移文件必须人工核对：只允许两个 `create_index`，夹带其他变更一律重生成。

---

### Task 1: 过期未处理信件不再占用 3 封容量（Critical #1）

**子 agent 独立性：❌ 主线**（`send` 函数串行第 1 棒）

**Files:**
- Modify: `backend/app/services/letter_service.py`（`send` 的未处理计数查询，L108–118）
- Test: `backend/tests/test_letter_send.py`

**Interfaces:** 不改签名与返回值契约。

- [ ] **Step 1: 写失败测试**（追加到 test_letter_send.py，复用 `_make_user`/`_seed_session`/`_insert_letter`/`_send`）

```python
async def test_expired_unhandled_letters_do_not_block_capacity(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    recipient = await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id)
    for i in range(3):
        await _insert_letter(
            db_session, recipient.id, content=f"过期信 {i}",
            expired_at=datetime(2026, 11, 7, 12, 0, tzinfo=SHANGHAI_TZ),  # == fixed_clock.now()，已过期
        )
    resp = await _send(client, sender.id, sid, "小美")
    assert resp.status_code == 200
    assert resp.json()["result"] == "delivered"
```

- [ ] **Step 2: 验证失败**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_send.py::test_expired_unhandled_letters_do_not_block_capacity -v`
Expected: FAIL（`result == "rejected_full"`）

- [ ] **Step 3: 实现**——计数查询 where 增加 `Letter.expired_at > clock.now()`（与 `get_inbox` L187 同口径；过期未处理行保持原样，不新增清理路径）。

- [ ] **Step 4: 验证通过 + 全文件回归**

Run: `cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_send.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/letter_service.py backend/tests/test_letter_send.py
git commit -m "fix: 过期未处理信件不再占用未处理信箱容量"
```

### Task 2: 消除同场并发投递 500（Important #2）

**子 agent 独立性：❌ 主线**（同函数，T1 之后）

**Files:**
- Modify: `backend/app/services/letter_service.py`（`send` L157–168）
- Test: `backend/tests/test_letter_send.py`

**Interfaces:** 不改签名。

- [ ] **Step 1: 写失败测试**（沿用 `test_concurrent_send_only_one_succeeds` 的独立连接模式）

```python
async def test_concurrent_deliver_same_session_idempotent(db_env, fixed_clock):
    async with db_env() as setup:
        sender = await _make_user(setup, "小明")
        await _make_user(setup, "小美")
        sid, _ = await _seed_session(setup, sender.id)
    async with db_env() as s1, db_env() as s2:
        results = await asyncio.gather(
            letter_service.send(s1, sender.id, sid, "小美", fixed_clock),
            letter_service.send(s2, sender.id, sid, "小美", fixed_clock),
        )
    assert sorted(r for r, _ in results) == ["already_sent", "delivered"]
    async with db_env() as check:
        assert await check.scalar(
            select(func.count()).select_from(Letter).where(Letter.session_id == sid)
        ) == 1
```

- [ ] **Step 2: 验证失败**——修复前 `gather` 大概率抛 `IntegrityError`（`_recipient_is_focused` 的 SELECT 触发 autoflush，在 try 外）；若偶过，按 Review Focus 1 继续修复（隐患由代码结构确认）。

- [ ] **Step 3: 实现**——把 `await _recipient_is_focused(db, recipient.id)` 移到 `db.add(ActionLog(...))` 之前，结果存局部变量传入 `Letter(...)`；保证 `db.add` 与 `try: await db.commit()` 之间不再有任何 `await`。

- [ ] **Step 4: 验证通过**——新用例 PASS；`test_focused_delivery_tag` 与全文件回归 PASS。

- [ ] **Step 5: Commit** — `fix: 同场并发投递稳定返回 already_sent 而非 500`

### Task 3: 收件人行锁防幻影行（Important #3）

**子 agent 独立性：❌ 主线**（同函数，T2 之后）

**Files:**
- Modify: `backend/app/services/letter_service.py`（imports + `send` 计数前）
- Test: 复用既有 `test_concurrent_send_only_one_succeeds`（test_letter_send.py L358）作回归

**Interfaces:** 不改签名。

- [ ] **Step 1: 基线**——先跑一遍既有并发用例记录结果（修复前依赖时序运气）。

- [ ] **Step 2: 实现**——`send` 中收件人解析后、计数查询前加：

```python
await db.scalar(select(User.id).where(User.id == recipient.id).with_for_update())
```

文件顶部补 `from app.models.user import User`；原计数查询的 `with_for_update()` 保留（锁顺序：users 行 → letters 行；dismiss/favorite 不锁 users，无环）。

- [ ] **Step 3: 验证**——`test_letter_send.py` 全量连跑两遍，全 PASS（锁先于计数快照，时序上确定性）。

- [ ] **Step 4: Commit** — `fix: 投递计数前锁收件人行，并发容量上限确定性成立`

### Task 4: 幂等键检查前移到正文校验之前（Minor #7）

**子 agent 独立性：❌ 主线**（同函数，T3 之后）

**Files:**
- Modify: `backend/app/services/letter_service.py`（`send` L97–105 顺序）
- Test: `backend/tests/test_letter_send.py`

- [ ] **Step 1: 写失败测试**

```python
async def test_retry_deliver_with_overlong_content_returns_already_sent(client, db_session, fixed_clock):
    sender = await _make_user(db_session, "小明")
    await _make_user(db_session, "小美")
    sid, _ = await _seed_session(db_session, sender.id, raw_text="长" * 201)
    db_session.add(ActionLog(session_id=sid, action_type="deliver"))
    await db_session.commit()
    resp = await _send(client, sender.id, sid, "小美")
    assert resp.status_code == 200
    assert resp.json()["result"] == "already_sent"
```

- [ ] **Step 2: 验证失败**——Expected: FAIL（422 `CONTENT_TOO_LONG`）。

- [ ] **Step 3: 实现**——把 already 查询块（L99–105）移到 `text = await _letter_content(...)` 之前。新顺序：会话校验 → 收件人解析 → already → 取正文 → 锁/计数。

- [ ] **Step 4: 验证通过 + 全文件回归。**

- [ ] **Step 5: Commit** — `fix: 已投递场次重试稳定返回 already_sent`

### Task 5: MailboxPage 账号快照守卫（Important #4）

**子 agent 独立性：✅ 可独立派子 agent**（纯前端，不依赖任何其他任务）

**Files:**
- Modify: `frontend/src/pages/MailboxPage.tsx`（`refresh` L26–40）

**Interfaces:** 不改组件 API。

- [ ] **Step 1: 实现**——参照 SettlePage L36–70 模式：`refresh` 首个 `await` 前 `const accountId = userId`；`Promise.all` 返回后先 `if (useAppStore.getState().userId !== accountId) return` 再 setState；`catch` 中同样守卫后再 `setError`。`runLetterAction` 经 `refresh` 自然继承守卫，不单独改。

- [ ] **Step 2: 验证**

Run: `cd frontend; npm run lint; npm run build`
Expected: 0 error。人工手测项见 Review Focus 3（回填清单时注明未自动化）。

- [ ] **Step 3: Commit** — `fix: 信箱页拉取加账号快照守卫`

### Task 6: 结算摘要「当日累计」文案 + 连续 0 天隐藏（Minor #6 + #10）

**子 agent 独立性：✅ 可独立派子 agent**（同文件两项合并，避免冲突）

**Files:**
- Modify: `frontend/src/features/settle/SettleSummary.tsx`（L39、L65）

**决策（已定，实施者勿改）：** #6 只改文案不改聚合口径——L39「今天累计」→「当日累计」；#10 L65 渲染条件 `data.streak !== null` → `data.streak !== null && data.streak.current > 0`。

- [ ] **Step 1: 实现**——上述两处。

- [ ] **Step 2: 验证**——`cd frontend; npm run lint; npm run build`，0 error。

- [ ] **Step 3: Commit** — `fix: 结算摘要归属日文案与断签连续天数展示`

### Task 7: seed 信件 created_at 相对时钟（Minor #8）

**子 agent 独立性：✅ 可独立派子 agent**（seed.py + test_seed.py，与主线无文件交集）

**Files:**
- Modify: `backend/app/seed.py`（L122）
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: 写失败测试**——在 test_seed.py 增断言：reset 后小明 inbox 两封信 `created_at <= clock.now()`（沿用文件内既有时钟与断言模式）。

- [ ] **Step 2: 验证失败**——Expected: FAIL（固定 12:00 在中午前是未来时刻）。

- [ ] **Step 3: 实现**——`created_at = clock.now() - timedelta(hours=1)`（`reset_seed` 已接收 `clock`；`expired_at` 不变）。

- [ ] **Step 4: 验证通过 + test_seed.py 全量回归。**

- [ ] **Step 5: Commit** — `fix: 种子信件时间改为相对服务端时钟`

### Task 8: handleDone 失败提示（Minor #9）

**子 agent 独立性：✅ 可独立派子 agent**（SettlePage.tsx，与 T5/T6 不同文件）

**Files:**
- Modify: `frontend/src/pages/SettlePage.tsx`（`handleDone` L81–91 + 渲染 L107–125）

- [ ] **Step 1: 实现**——`handleDone` 的 `catch` 对齐 `resolve` 的错误处理：`axios.isAxiosError(e) && e.response?.status === 404` 保持 `navigate("/")`；其余错误 `setError("结算信息加载失败，请稍后重试")` 留在当前步。渲染层在 `summary` 存在时也展示错误：步骤组件下方加 `{summary !== null && error !== null && <p className="text-center text-sm text-destructive">{error}</p>}`；`handleDone` 成功时 `setError(null)`。

- [ ] **Step 2: 验证**——`npm run lint; npm run build`，0 error。

- [ ] **Step 3: Commit** — `fix: 结算步进拉取失败给提示而非静默回首页`

### Task 9a: favorite 拒绝已处理信（Minor #11-a）

**子 agent 独立性：❌ 主线收尾**（同改 letter_service.py + test_letter_send.py，排在 T4 后）。契约扩展已批准（2026-11-07）。

**Files:**
- Modify: `backend/app/services/letter_service.py`（新增异常类 + `favorite` L281 附近）、`backend/app/routers/letter.py`（favorite 端点 L141–147 增映射）
- Test: `backend/tests/test_letter_send.py`

- [ ] **Step 1: 写失败测试**——`_insert_letter(handled=True)`（已放弃）后 POST `/favorite`，断言 409 且 `detail.code == "LETTER_ALREADY_HANDLED"`，库内 `favorited` 仍为 False。
- [ ] **Step 2: 验证失败**——Expected: FAIL（当前返回 200）。
- [ ] **Step 3: 实现**——新增 `class LetterAlreadyHandled(Exception)`；`favorite` 中 `if letter.favorited: return letter` 之后加 `if letter.handled: raise LetterAlreadyHandled`（幂等重试因 favorited=True 先行返回，不受影响）；router 映射 409 `{"code": "LETTER_ALREADY_HANDLED", "message": "这封信已处理，不能再收藏"}`。
- [ ] **Step 4: 验证通过 + 全文件回归。**
- [ ] **Step 5: Commit** — `fix: 已放弃信件不可再收藏复活进历史`

### Task 9b: letters 表补索引（Minor #11-b）

**子 agent 独立性：✅ 可独立派子 agent**（models/letter.py + 新迁移文件，无冲突）

**Files:**
- Modify: `backend/app/models/letter.py`（L14、L16）
- Create: `backend/alembic/versions/<新迁移>.py`

- [ ] **Step 1: 实现**——`user_id`、`session_id` 加 `index=True`（与 `sender_id` L15 同款）；`cd backend; .venv\Scripts\alembic.exe revision --autogenerate -m "letters user/session indexes"`。
- [ ] **Step 2: 人工核对迁移**（Review Focus 5）后 `alembic upgrade head`（dev 库）。
- [ ] **Step 3: 验证**——`test_architecture.py` 棘轮 + `test_letter_send.py` 全量（测试库走 `create_all` 自动带新索引）。
- [ ] **Step 4: Commit** — `chore: letters 表补 user_id/session_id 索引`

### Task 9c: 收件人重名确定性（Minor #11-c）

**子 agent 独立性：❌ 排主线后**（代码在 user_service.py 独立，但测试落 test_letter_send.py，与主线同文件）

**Files:**
- Modify: `backend/app/services/user_service.py`（L26）
- Test: `backend/tests/test_letter_send.py`

- [ ] **Step 1: 写失败测试**——两个同名用户「小美」，投递断言 200 `delivered` 且库内信件 `user_id` 为 id 较小者。
- [ ] **Step 2: 验证失败**——Expected: FAIL（`MultipleResultsFound` → 500）。
- [ ] **Step 3: 实现**——name 分支改 `await db.scalar(select(User).where(User.name == value).order_by(User.id).limit(1))`。
- [ ] **Step 4: 验证通过 + 回归。**
- [ ] **Step 5: Commit** — `fix: 收件人重名时确定性取最早注册账号`

### Task 9d: star/streak 首次建行并发保护（Minor #11-d）

**子 agent 独立性：✅ 可独立派子 agent**（progress_service.py + test_progress.py，无冲突）

**Files:**
- Modify: `backend/app/services/progress_service.py`（`recompute_day` L56–65、`mark_day_completed` L73–75）
- Test: `backend/tests/test_progress.py`

- [ ] **Step 1: 写失败测试**——沿用 db_env 独立连接 + `asyncio.gather`：两并发 `recompute_day`（同一 user/day，各自 commit），断言不抛 IntegrityError 且最终只一行。
- [ ] **Step 2: 验证失败**（偶过则按 Review Focus 1 继续）。
- [ ] **Step 3: 实现**——两处新建行的 `db.add(...)` + `flush` 包进 `async with db.begin_nested():`（沿用 letter_service.dismiss 的 savepoint 模式），`except IntegrityError` 时重新 `select` 取既有行并走更新路径；需 `from sqlalchemy.exc import IntegrityError`。
- [ ] **Step 4: 验证通过 + test_progress.py 全量连跑两遍。**
- [ ] **Step 5: Commit** — `fix: star/streak 首次建行并发改为幂等更新`

### Task 9e: get_current_session 并列排序（Minor #11-e）

**子 agent 独立性：✅ 可独立派子 agent**（session_service.py 一行，无冲突）

**Files:**
- Modify: `backend/app/services/session_service.py`（L70）

- [ ] **Step 1: 实现**——`.order_by(Session.started_at.desc())` → `.order_by(Session.started_at.desc(), Session.id.desc())`（与 `create_session` L44 一致）。
- [ ] **Step 2: 验证**——`test_session_api.py` + `test_session_end.py` + `test_settle_summary.py` 回归 PASS。
- [ ] **Step 3: Commit** — `fix: 当前会话同时间戳并列时取 id 最大者`

### Task 10: 收尾全量验证 + 回填清单

**子 agent 独立性：❌ 主会话最后执行**（需等全部任务完成）

- [ ] **Step 1: 全量验证**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
cd backend; .venv\Scripts\python.exe -m pytest        # 沙箱外、DB 运行
cd frontend; npm run lint; npm run build
```

- [ ] **Step 2: 回填** `docs/review-fixes-p4-p6.md`：各项标「已修复 + commit SHA」；T5 手测、T6 口径保留、T3/T9d 时序说明写入「遗留」。
- [ ] **Step 3: Commit** — `docs: 回填 P4-P6 审查修复状态`

---

## 并行 / 串行编排总表（2026-11-07 确认的执行方式：本表即执行路由，主线按序，✅ 行可同时派发）

- **主线 agent 路线（严格串行，一个 agent 按序执行）：T1 → T2 → T3 → T4 → T9a → T9c**——全部触及 `letter_service.py` / `test_letter_send.py`，互相依赖。
- **子 agent 并行路线（✅ 行）：T5、T6、T7、T8、T9b、T9d、T9e**——文件两两无交集，可同时各自派发，不等主线、互不等待。
- **收尾：T10** 必须等两条路线全部完成，由主会话执行全量验证与文档回填。

| 任务 | 修复项 | 触及文件 | 可独立子 agent |
|---|---|---|---|
| T1 | #1 过期占容量 | letter_service.py、test_letter_send.py | ❌ 主线第 1 棒 |
| T2 | #2 并发 500 | 同上 | ❌ 主线（T1 后） |
| T3 | #3 幻影行锁 | 同上 | ❌ 主线（T2 后） |
| T4 | #7 already 前移 | 同上 | ❌ 主线（T3 后） |
| T9a | #11-a favorite | letter_service.py、routers/letter.py、test_letter_send.py | ❌ 主线（T4 后；**契约扩展先确认**） |
| T9c | #11-c 重名 | user_service.py、test_letter_send.py | ❌ 主线（T9a 后，测试同文件） |
| T5 | #4 信箱守卫 | MailboxPage.tsx | ✅ 与一切并行 |
| T6 | #6/#10 文案与连续 0 天 | SettleSummary.tsx | ✅ 与一切并行 |
| T7 | #8 seed 时间 | seed.py、test_seed.py | ✅ 与一切并行 |
| T8 | #9 静默回首页 | SettlePage.tsx | ✅ 与一切并行 |
| T9b | #11-b 索引 | models/letter.py、新迁移 | ✅ 与一切并行 |
| T9d | #11-d 建行并发 | progress_service.py、test_progress.py | ✅ 与一切并行 |
| T9e | #11-e 排序 | session_service.py | ✅ 与一切并行 |
| T10 | 收尾 | 全量验证 + 文档回填 | ❌ 最后主会话 |

**建议：** 主线 T1→T4→T9a→T9c 由一个子 agent（或主会话）串行；7 个 ✅ 任务同时各派一个子 agent；全部完成后主会话跑 T10。
