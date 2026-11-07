# 006 · F6 信箱与投递

> 来源：[brainstorming.md](../../brainstorming.md) F6、第 10 节 A1–A4/A6/A8–A11/A13；执行计划：[2026-11-07-p6-f6-mailbox.md](../superpowers/plans/2026-11-07-p6-f6-mailbox.md)。前置 Spec：[003 · F3 专注计时与有效性](./003-f3-focus-session.md)、[004 · F4+F5 结算四步与感想](./004-f4-f5-settle-reflection.md)、[005 · F7 星星与连续天数](./005-f7-star-streak.md)。

## 1. 背景与目标

P4 把结算四步的断点与①写感想打通，②投递 / ③信箱仍是可跳过的占位卡片；`letters` 表与 `letter_service` 只有最小实现（收件人 → 未处理 inbox、收藏 → history），存在三处与 F6 不符：

- `deliver` 在对方未处理满 3 时**静默丢弃**，发送方拿不到「对方信箱已满」，也没有发出记录、无法改寄；
- 信件没有发件人、送达状态与「专注时投递」标签，无法区分「已投递 / 未送达」；
- 历史信箱把「放弃」的信也留在里面，违反 A10「只有收藏进入历史信箱」。

目标：每场有效学习获得 1 次投递机会——填收件人投递，正文 = 本场感想（无感想 = 任务原文）；对方未处理信箱满 3 → 拒收、不消耗机会、可改寄；收件人不存在明确提示；结算第③步逐封收藏 / 放弃；历史信箱只存收藏、≤100 懒清理；未收藏当日 24:00 失效；`/mailbox` 页展示未处理 / 历史 / 发出记录；学习期间静默投递，结算页显示「你专注时收到 N 封信」。

## 2. 范围与非目标

- 范围（F6 全部规则及已定结论 A1–A4、A6、A8–A11、A13）：
  - **投递机会**：每场有效学习（`completed/settled` 且 `ended_at` 非空）1 次；同场只能投 1 封；当天场次不限；拒收/收件人不存在不消耗，可改寄。
  - **正文来源**：本场 Reflection 存在 → 其 `content`；否则 → 本场任务当前采用版 `day_tasks.raw_text`（A2）。
  - **收件人**：填写用户名或 ID（A8）；不存在 → `rejected_unknown`，不落任何行、不消耗机会。
  - **未处理信箱**：所有来信先进这里，最多 3 封（A1/A3）；满 3 拒收（A4），发送方立即可见「对方信箱已满」，发出记录标「未送达」；行锁保证并发下 delivered+未处理永不超 3。
  - **专注时投递标签**：投递成功时若收件人正在学习（`status ∈ {active, completed}` 且 `ended_at IS NULL`），该信标 `focused_delivery=True`。
  - **收藏 / 放弃**：结算第③步逐封处理；收藏 → 写入历史信箱（A10）；放弃 → `handled=True`，不进历史；重复操作幂等。
  - **失效**：未收藏的信在收到日 24:00（Asia/Shanghai）失效；失效后不出现在 inbox，收藏/放弃返回 409；历史信箱随时可看、可手动删除（A3）。
  - **历史上限**：>100 封时读时删最旧（A4）。
  - **发出记录**：自己投出的信（含被拒收的「未送达」），展示收件人与结果、正文与时间。
  - **收信门槛**：完成当天学习（P5 `progress.summary.today.level ≥ 1`）才解锁 `/mailbox` 入口；未完成置灰并写明「完成今天的学习后开启」。
  - **结算提示**：`GET /api/sessions/{id}/summary` 的 `received_during_session` 填本场时间窗内真实收到的信数；结算页 N>0 时显示「你专注时收到 N 封信」。
  - **静默投递**：学习期间不打断专注页（信件不推送、不弹窗），只在结算页汇总。
  - **演示验收**：小明学习中，小美/小刚连投 4 封 → 前 3 成功、第 4 拒收且发出记录标「未送达」、改寄成功；小明结算页显示「专注时收到 3 封信」，③收藏 1 放弃 2；次日再进网站历史信箱只有收藏的 1 封。
  - **种子**：reset 后小明未处理信箱预置 2 封（发件人小美、正文取小美昨日感想），小美发出记录 2 条「已投递」。
- 非目标（明确不做的）：
  - ④随机回顾真实逻辑与回顾记录（P7）。
  - 「我的学习记录」页三种查法与「第 X 场」标注（P8）；信件与记录的关联查询。
  - 敏感内容审核（只做正文长度上限）；信件编辑；发件人撤回。
  - 多客户端并发下的复杂重试策略（Demo 单客户端，行锁兜住未处理上限即可）。
  - 购买/删除以外的历史操作（无置顶、无标签、无搜索）。

## 3. 可测试的验收条件

1. 本人有效会话投递（有感想）→ `result="delivered"`、返回 `letter_id`；正文 = 本场感想去首尾空白后的内容；对方 inbox 出现该信（`status="delivered"`）。
2. 本人有效会话投递（无感想 / 空白跳过）→ 正文 = 本场任务当前采用版 `raw_text`。
3. 收件人按用户名或数字 ID 均可命中；不存在 → `result="rejected_unknown"`，无 `letters` 行、无 `action_logs` 行，可立刻改投他人成功。
4. 对方未处理信箱已有 3 封 → `result="rejected_full"`；不占用 `(session_id, "deliver")` 幂等键，同一场改寄他人 → `delivered`；发送方 outbox 出现一条 `status="undelivered"` 记录，收件方 inbox 不增加。
5. 同一场已投递成功后再投 → `result="already_sent"`（200），不新增信件、不新增幂等键。
6. 会话不存在 / 非本人 / `discarded` / `ended_at` 为空 → `409 {"detail": {"code": "SESSION_NOT_VALID"}}`，无任何写入。
7. 并发：两个发送方同时投给未处理信箱已有 2 封的用户 → 恰好 1 封 `delivered`、1 封 `rejected_full`；库中该用户 delivered 且未处理 ≤3。
8. `focused_delivery`：收件人此刻有进行中会话（`active/completed` 且 `ended_at` 空）→ `True`；否则 `False`。
9. 放弃（dismiss）：收件人本人、未过期、`delivered`、未处理 → `handled=True`、`favorited=False`，通知历史信箱不出现该信；重复放弃返回 200 且状态不变（幂等）。
10. 过期信：`expired_at <= Clock.now()` → inbox 不返回；收藏/放弃均 `409 {"detail": {"code": "LETTER_EXPIRED"}}`，不写库。
11. 收藏：重复收藏只生效一次（`favorited=True`，不写重复 `favorite:{id}` 幂等键）；非本人 / 不存在 / `status="undelivered"` → `404 LETTER_NOT_FOUND`。
12. `GET /api/letters/inbox` 只返回本人 `delivered`、未处理、未过期信，≤3，按 `created_at` 倒序；`sender_name` 与 `status` 字段齐全。
13. `GET /api/letters/history` 只返回本人 `delivered` 且 `favorited=True` 的信（**放弃的信不再出现**），>100 时删除最旧并只返回 100。
14. `GET /api/letters/outbox` 返回本人 `sender_id` 的 delivered 与 undelivered 信（按 `created_at` 倒序），字段 `{id, recipient_name, content, status, created_at}`。
15. `DELETE /api/letters/{id}` 只允许删除本人 `favorited=True` 的历史信 → 204，删除后 history 不再出现；重复删除 → 404 `LETTER_NOT_FOUND`。
16. `GET /api/sessions/{id}/summary` 的 `received_during_session` = 本场 `started_at ≤ letter.created_at ≤ ended_at` 且 `status="delivered"`、`user_id=本人` 的信数；窗口外/他人信不计；无收信为 0。
17. 未收藏信的 `expired_at` = 收到日次日 00:00（Asia/Shanghai）：当天 23:59 投递的信在 00:00 后失效（`Clock` 注入钉住）。
18. 种子 reset 后：小明 inbox 2 封（`sender_name="小美"`、`status="delivered"`、未过期）；小美 outbox 2 条 `delivered`；小明再收 1 封成功、第 2 封被 `rejected_full`（总量维持 3）。
19. 前端：`StepDeliver` 展示「本场可投 1 封」并按四态提示（已投递 / 对方信箱已满，可改寄 / 找不到这位同学 / 已寄出），「不寄了」推进；`StepMailbox` 逐封收藏/放弃后刷新列表，「下一步」推进到 3；`/mailbox` 三段列表；首页入口按当天完成置灰/可点；结算摘要 N>0 显示「你专注时收到 N 封信」。
20. 后端取时间只用 `Clock`；router 不直接写 SQL（架构棘轮）；前端 HTTP 只走 `api/client.ts`，不新增 `new Date(`。
21. `backend/tests/test_architecture.py` 棘轮、后端全量 pytest、`alembic check` 无漂移、前端 `npm run lint` / `npm run build` 通过。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：信件与未处理信箱唯一来源仍是 `letters` 表 + `letter_service`（行锁 + 事务）；投递/收藏/放弃幂等仍走 `action_log` 唯一约束；当前时间仍是后端 `Clock`；收信门槛复用 `progress_service` 的「当天完成」口径；前端身份仍是 zustand `userId`。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/letter.py` | 信件事实源 | 修改：新增 `sender_id`、`status`、`focused_delivery` 三列（见 §6.2） |
| `backend/app/services/letter_service.py` | 投递 / 收藏 / 放弃 / 删除的唯一写入路径 | 重写：`send` 事务顺序（成功才占幂等键）、`dismiss`、`delete_favorited`、outbox 查询、inbox/history 按 `status` 过滤；保留行锁与懒清理 |
| `backend/app/routers/letter.py` | 信件 HTTP 入口 | 修改：新增 `POST /api/letters`、`POST /{id}/dismiss`、`GET /outbox`、`DELETE /{id}`；既有 favorite 传 `clock` |
| `backend/app/schemas/letter.py` | 信件 API 契约 | 修改：`LetterOut` 扩 `sender_name/status/focused_delivery`；新增 `LetterSend`、`LetterSendResult`、`OutboxLetter`、`OutboxResponse` |
| `backend/app/services/user_service.py` | 账号查询 | 修改：新增 `find_by_name_or_id`、`get_names`（收件人解析与 `sender_name`/`recipient_name` 拼装） |
| `backend/app/services/session_service.py` | 结算 summary | 修改：`get_settlement_summary` 计算并返回 `received_during_session`（不改其它字段） |
| `backend/app/schemas/session.py` | 结算契约 | 修改：`received_during_session` 填值（字段已存在，不改类型） |
| `backend/app/seed.py` | 演示数据 owner | 修改：小明 inbox 预置小美 2 封未处理信（直接落库，不走投递机会） |
| `backend/alembic/versions/<new>_letter_delivery.py`（新增） | `letters` 三列迁移 | 新建（autogenerate 后人工核对默认值与可空性） |
| `backend/tests/test_letter_send.py`（新增） | 本 Spec 验收条件 1–18 的后端测试 | 新建 |
| `backend/tests/test_letter_settle.py` | 既有信箱/结算回归 | 修改：适配 `send` 新签名、history 只含收藏、favorite 带 `clock`（断言不弱化） |
| `backend/tests/test_seed.py` | 种子回归 | 修改：新增小明 2 封信 + 小美 outbox 断言 |
| `frontend/src/features/settle/StepDeliver.tsx` | 结算第②步 | 替换占位：收件人输入 + 四态结果 + 「不寄了」；props `{sessionId, onDone}` 不变 |
| `frontend/src/features/settle/StepMailbox.tsx` | 结算第③步 | 替换占位：inbox ≤3 逐封收藏/放弃 + 「下一步」推进到 3；props 不变 |
| `frontend/src/features/mailbox/InboxList.tsx`、`HistoryList.tsx`、`OutboxList.tsx`（新增） | 信箱三段列表 | 新建理由：三段数据结构与空态不同，拆开后可被 `/mailbox` 与结算第③步复用 |
| `frontend/src/pages/MailboxPage.tsx`（新增） | `/mailbox` 页 | 新建理由见 §6.4 |
| `frontend/src/App.tsx`、`frontend/src/pages/HomePage.tsx`、`frontend/src/pages/SettlePage.tsx` | 路由 / 入口 / 摘要提示 | 修改：注册 `/mailbox`、首页信箱入口（门槛）、结算摘要 N 封提示 |
| `frontend/src/features/mailbox/types.ts`（新增） | 信件 TS 类型 | 新建理由：页面与结算步骤共用同一契约，避免字段两处定义 |
| `frontend/src/api/client.ts`、`hooks/useServerClock.ts`、`store/app.ts` | 唯一 HTTP / 时间 / 身份入口 | 不改 |

## 5. 实现步骤

按 [dev-order.md](../dev-order.md) 六步流水线，Task 1 只完成第 0 步（Spec），其余由后续任务执行：

1. 写本 Spec 并提交（本文件）。
2. **契约（六步①）**：`schemas/letter.py` 定义 send/dismiss/outbox 请求与响应、`LetterOut` 扩展字段；`schemas/session.py` 的 `received_during_session` 填值口径与 §6.1 一致。
3. **迁移（六步②）**：`alembic revision --autogenerate` 生成 `letters` 三列，人工核对 `status` 默认值 / `focused_delivery` 默认值 / `sender_id` 可空与索引；测试库 `downgrade base → upgrade head` 双向通过。
4. **业务（六步③）**：先写 `tests/test_letter_send.py` 失败用例（§7），确认 FAIL；实现 `letter_service.send` 事务顺序、`dismiss`、`delete_favorited`、outbox、inbox/history 过滤；`user_service` 两个查询；`get_settlement_summary` 填收信数；`seed.py` 预置信件。
5. **接口（六步④）**：`routers/letter.py` 四个新端点与 favorite 的 `clock`；`/docs` 冒烟。
6. **前端（六步⑤）**：`StepDeliver` / `StepMailbox` 真实逻辑；`MailboxPage` + 三个列表 + 路由 + 首页入口 + 结算摘要提示；`npm run lint` + `npm run build`。
7. **联调（六步⑥）**：三服务同启 + reset seed，按验收条件 19 与演示验收走一遍；回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

### 6.1 契约

身份一律由 `X-User-Id` 注入（账号不存在 → 404 `USER_NOT_FOUND`），`server_time` 由 `Clock` 产出。

#### `POST /api/letters`

请求 `LetterSend {session_id: int, recipient_name: str}`（`recipient_name` 去首尾空白后非空，`max_length=50`；空白 → 422）。

响应 `200 LetterSendResult`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `result` | `"delivered" \| "rejected_full" \| "rejected_unknown" \| "already_sent"` | 四态结果 |
| `letter_id` | int \| null | `delivered` / `rejected_full`（undelivered 行）为信件 id；其余为 `null` |
| `server_time` | str | 服务端当前时间 |

- 会话校验失败（不存在 / 非本人 / `discarded` / `ended_at` 空）→ `409 {"detail": {"code": "SESSION_NOT_VALID", "message": "只有已结束的有效学习才能投递"}}`。
- 四态语义与机会消耗见 §6.3；`already_sent` 是幂等结果，不是错误（HTTP 200）。
- 收件人解析：`recipient_name` 去空白后若全为数字 → 按 `users.id` 精确匹配；否则按 `users.name` 精确匹配；未命中 → `rejected_unknown`。

#### `POST /api/letters/{id}/dismiss`

响应 `200 DismissResponse {letter: LetterOut, server_time}`。

- 仅本人、`status="delivered"` 的信；不存在 / 他人 / `undelivered` → `404 LETTER_NOT_FOUND`。
- 已过期（`expired_at <= Clock.now()`）→ `409 {"detail": {"code": "LETTER_EXPIRED", "message": "这封信已经过了一天"}}`。
- 幂等：已 `handled=True` 直接返回当前信件（200），不再写幂等键。

#### `GET /api/letters/outbox`

响应 `200 OutboxResponse {letters: list[OutboxLetter], server_time}`；`OutboxLetter {id, recipient_name, content, status, created_at}`，按 `created_at` 倒序。`status ∈ {delivered, undelivered}`。

#### `DELETE /api/letters/{id}`

- 仅本人、`status="delivered"` 且 `favorited=True` 的历史信 → `204`（物理删除行）。
- 其余（不存在 / 他人 / 未收藏 / undelivered）→ `404 LETTER_NOT_FOUND`。

#### 既有端点变化

- `GET /api/letters/inbox`：只返回 `status="delivered"`、未处理、未过期的信；响应字段不变 + `LetterOut` 新字段。
- `GET /api/letters/history`：**收紧为只返回 `favorited=True` 且 `status="delivered"` 的信**（放弃的信不再出现，符合 A10）；>100 懒清理最旧。
- `POST /api/letters/{id}/favorite`：service 增加 `clock` 参数；已过期 → `409 LETTER_EXPIRED`；`undelivered` / 他人 / 不存在 → `404 LETTER_NOT_FOUND`；重复收藏幂等。
- `LetterOut` 扩展：`sender_name: str | null`（历史行可能为空）、`status: "delivered" | "undelivered"`、`focused_delivery: bool`；其余字段不变。

#### `GET /api/sessions/{id}/summary`

`received_during_session` 由占位 `0` 改为真实值：`user_id=本人`、`status="delivered"`、`created_at ∈ [session.started_at, session.ended_at]` 的计数（不含 undelivered、不含窗口外）。其余字段与 P4/P5 契约不变。

### 6.2 数据与迁移

`letters` 新增三列（一张 revision）：

| 列 | 类型 | 约束 / 说明 |
|---|---|---|
| `sender_id` | int \| null | FK `users.id`，可空（历史行无发件人）；新写入行必填；加索引 `ix_letters_sender_id` 供 outbox 查询 |
| `status` | `String(20)` | 非空，默认 `"delivered"`；取值 `delivered` / `undelivered` |
| `focused_delivery` | `Boolean` | 非空，默认 `False`；投递时收件人正在学习为 `True` |

- `user_id` 语义保持不变 = **收件人**；`sender_id` = 发件人。outbox 按 `sender_id` 查，inbox/history/favorite/dismiss/delete 按 `user_id` + `status="delivered"` 查。
- 迁移 `downgrade` 逆序 drop 索引与三列；无数据回填（既有行 `sender_id=NULL`、`status` 取默认）。
- 不新增表、不改既有唯一约束；幂等仍只靠 `action_logs (session_id, action_type)`。

### 6.3 行为口径（letter_service 内闭合）

- **投递正文**：`Reflection(session_id).content` 存在则用之，否则 `DayTask.raw_text`；正文长度上限 200（与感想 `max_length` 一致；超长在 service 侧拒绝写入并返回 422 由 router 映射——Demo 只对 API 直接调用生效，前端输入框 `maxLength=200`）。
- **投递事务顺序 `send(db, sender_id, session_id, recipient_name, clock) -> str`**：
  1. 校验会话（本人 + `status ∈ SETTLEABLE_STATUSES` + `ended_at` 非空），失败抛 `SessionNotValid`；
  2. 解析收件人，未命中直接返回 `rejected_unknown`（不写任何行、不占键）；
  3. 若 `ActionLog(session_id, "deliver")` 已存在 → 返回 `already_sent`；
  4. 对收件人 `status="delivered" AND handled=false` 的行加 `with_for_update()`，计数；
  5. 计数 ≥3 → 以 `ActionLog(session_id, f"deliver_undelivered:{recipient_id}")` 去重地写一条 `status="undelivered"` 的 Letter（`favorited=False`、`handled=True`、`expired_at=收到日 24:00`），commit，返回 `rejected_full`；该键**不阻止**后续 `deliver` 键，机会未消耗；
  6. 否则同一次 commit 写 `ActionLog(session_id, "deliver")` + `Letter(status="delivered")`，返回 `delivered`；commit 时若 `deliver` 键冲突（并发双击）→ rollback 后返回 `already_sent`。
- **机会消耗**只由 `deliver` 幂等键 + delivered 行定义；`rejected_*` 均不消耗。
- **`focused_delivery`**：投递时收件人存在 `status ∈ {active, completed}` 且 `ended_at IS NULL` 的会话 → `True`。
- **失效时间**：`expired_at = datetime.combine(clock.today() + 1 day, 00:00, Asia/Shanghai)`；失效判断只在查询条件与操作前的 `Clock.now()` 比较，不跑后台清扫。
- **历史信箱** = `user_id=本人 AND status="delivered" AND favorited=True`；读时按 `created_at` 倒序，超过 100 删除最旧（与 P6 前行为相比不再含 `handled` 行）。
- **删除**只允许历史信（见 §6.1），物理删除。
- **收信门槛（首页入口）**：复用 `GET /api/progress/summary` 的 `today.level ≥ 1`（P5 已定的「当天完成」等价口径），P6 不新增第二套判定；已知边界：专注进行中已满 5 分钟但尚未结束时 `today.level=0`，此时用户仍在专注页，首页入口置灰不影响演示。
- **收件人解禁不禁止寄给自己**：F6 未规定，Demo 三账号场景不加额外规则。

### 6.4 新增 `/mailbox` 页理由

F6 的信箱有三段（未处理 / 历史 / 发出记录），且历史信箱「随时可查看」——它不属于结算四步的时间线，无法塞进结算第③步的单卡片；把三段塞进首页会与今日任务输入/分析混在一屏，破坏首页「一件事」的焦点。因此新增 `/mailbox` 路由页 + 三个列表组件：首页入口按当天完成门槛开启，结算第③步只复用「未处理」列表（`InboxList`），历史与发出记录只在 `/mailbox` 展示。

### 6.5 兼容性与前端接入

- **行为变化（非破坏性 API 字段）**：`GET /api/letters/history` 不再返回已放弃的信；仓库内 P6 前无历史信箱消费者（`/mailbox` 为新页面），影响仅限测试断言与演示数据。
- `letter_service.deliver` 的旧签名（收件人 `user_id` + 无发件人）被 `send` 取代；既有 `test_letter_settle.py` 同步改造（断言不弱化，覆盖 4 封→3 封上限）。
- **不改**：P3 `/current`、`/end`，P4 `/summary` 结构、`/reflection`、`/settle/{id}/advance`，P5 `/progress/summary`；`received_during_session` 从占位 `0` 变为真实值（字段类型不变）。
- 前端：`SettlePage` 第③步之后仍按 `settle_step` 推进——第③步完成调用 `advance(to_step=3)`（P4 §6.4 语义表），不由 P6 放宽；`StepDeliver` 成功后展示结果并调用 `advance(to_step=2)`。
- 账号切换时清空信件视图并按新身份重新拉取（沿用 P1/P2/P3 的账号快照守卫）。

## 7. 测试场景与验证命令

从第 3 节验收条件推导（`backend/tests/test_letter_send.py`；时序一律注入 `get_clock` override / `FixedClock`，禁止 sleep；并发用双引擎双连接 fixture）：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_send_delivered_with_reflection_content` | `delivered`；正文 = 感想；收件人 inbox +1 |
| 2 | `test_send_falls_back_to_task_text` | 无感想 → 正文 = `raw_text` |
| 3 | `test_send_recipient_by_id_and_name` | 用户名与 ID 均可命中 |
| 3 | `test_send_unknown_recipient_no_consume` | `rejected_unknown`；无 Letter/ActionLog；改投成功 |
| 4 | `test_send_full_rejected_then_resend_succeeds` | `rejected_full` → 改寄 `delivered`；outbox 有 undelivered |
| 5 | `test_send_already_sent_idempotent` | 第二次 `already_sent`；Letter 仍 1 条 |
| 6 | `test_send_requires_valid_session` | `discarded` / `active`（未结束）/ 他人 → 409 `SESSION_NOT_VALID` |
| 7 | `test_concurrent_send_only_one_succeeds` | 双连接：1 delivered + 1 rejected_full；delivered+unhandled ≤3 |
| 8 | `test_focused_delivery_tag` | 收件人有进行中会话 → `True`；无 → `False` |
| 9 | `test_dismiss_idempotent_and_not_in_history` | 重复 dismiss 200；history 不含该信 |
| 10 | `test_dismiss_expired_409` / `test_favorite_expired_409` | 409 `LETTER_EXPIRED`，库不变 |
| 11 | `test_favorite_idempotent_and_undelivered_404` | 重复收藏一次；undelivered → 404 |
| 12 | `test_inbox_only_delivered_unexpired` | 只含 delivered、未处理、未过期；≤3 |
| 13 | `test_history_only_favorited_and_lazy_cleanup_100` | 101 封收藏 → 100，最旧被删；dismissed 不出现 |
| 14 | `test_outbox_lists_delivered_and_undelivered` | 两种状态均在，按时间倒序，recipient_name 正确 |
| 15 | `test_delete_favorited_letter` | 204；history 消失；重复删除 404 |
| 16 | `test_summary_received_during_session` | 窗口内 2 封 → `received_during_session=2`；窗口外/undelivered 不计 |
| 17 | `test_unhandled_expiry_crosses_midnight` | 注入 Clock 推进到次日 00:00 → inbox 空、收藏/放弃 409 |
| 18 | 扩展 `test_seed.py` | 小明 inbox 2 封（小美）、小美 outbox 2 条 delivered |
| 19 | 前端 | lint + build；浏览器端到端由 Task 4 覆盖 |
| 20 | `test_architecture.py` + Grep | 后端 `datetime.now(` 仅 `clock.py`；前端 `new Date(` 仅 `api/client.ts` / `hooks/useServerClock.ts` |
| 21 | 全量命令 | 见下 |

验证命令：

```powershell
# 新增信件测试（需 PostgreSQL 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_send.py -q

# 既有信箱/结算回归 + 种子 + 架构棘轮
cd backend; .venv\Scripts\python.exe -m pytest tests/test_letter_settle.py tests/test_seed.py tests/test_architecture.py -q

# 后端全量
cd backend; .venv\Scripts\python.exe -m pytest -q

# 迁移漂移 / 双向（测试库）
cd backend; .venv\Scripts\alembic.exe check

# 前端
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

（实现完成后回填；Task 1 尚未实现。）

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 契约（`schemas/letter.py` 四态响应、outbox、`LetterOut` 扩展；summary 字段填值）→ 迁移（`letters` 三列）→ 业务（`letter_service.send/dismiss/delete` 单一写入路径、`user_service` 查询、summary 计数、seed 预置）→ 接口（`routers/letter.py` 四个新端点）→ 前端（结算②③ + `/mailbox` + 首页入口 + 结算提示）。
> 2. **当前 owner 在哪里？** 信件与未处理上限 owner 是 `letters` 表 + `letter_service`；幂等 owner 是 `action_logs`；当天完成 owner 是 `progress_service`；时间 owner 是 `app/clock.py`；前端身份是 `store/app.ts`。
> 3. **是否引入重复状态或平行写入？** 否。delivered/undelivered、收藏/放弃、删除全部只有 `letter_service` 一条写入路径；机会消耗只由 `deliver` 幂等键定义；首页门槛复用 P5 已有的 today.level，不另算。
> 4. **是否影响接口和其他模块？** 新增四个信件端点；`history` 语义收紧（不再含放弃信）；summary 的 `received_during_session` 从占位变真实（类型不变）；P3/P4/P5 既有契约不变；种子多 2 封信。
> 5. **哪些现有检查需要继续通过？** `tests/test_architecture.py` 棘轮、后端全量测试、`alembic` 双向/无漂移、前端 lint + build、Task 4 演示验收。
