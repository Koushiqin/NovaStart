# P4–P6 代码审查待修复清单

> 来源：对 `fdc82aa..adccb07`（P4 F4+F5 结算感想、P5 F7 星星连续天数、P6 F6 信箱）的只读代码审查（2026-11-07）。逐条核过代码；架构棘轮 65 passed，其余测试结论来自代码与断言阅读，未实跑。
> 状态：**已修复（2026-11-08）**，逐条状态、commit SHA 与遗留项见文末「修复状态与遗留」。

## 必修复（Critical）

### 1. 过期未处理信件永久占用「3 封上限」，收件箱跨天死锁

- 位置：[letter_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L107-L120)（计数）vs [letter_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L179-L192)（inbox 查询）
- 问题：`send` 统计容量只查 `delivered AND handled=false`，不加 `expired_at > now`；而 inbox 展示过滤过期信，`dismiss`/`favorite` 对过期信直接 409（[:241](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L241) / [:279](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L279)），全库没有任何清理过期行的路径。
- 后果：累计 3 封「过期且未处理」后，收件人 inbox 视觉为空，但所有新投递永久 `rejected_full`；用户无界面可操作，只能 `/dev/reset-seed`。与 F6 鼓励跨天连续使用直接冲突。
- 建议：计数加 `expired_at > clock.now()`，或在计数前把过期未处理行懒置 `handled=True`；补「3 封过期后仍能收第 4 封」测试。

## 应修复（Important）

### 2. 同场并发投递会 500 而非 `already_sent`

- 位置：[letter_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L157-L174)
- 问题：第 157 行先 `db.add(ActionLog)`，第 165 行 `_recipient_is_focused` 的 SELECT 触发 autoflush，唯一键 `uq_action_logs_session_action` 的 `IntegrityError` 会在 `try/except`（169 行才包住 commit）之外抛出。
- 后果：两个标签页/客户端同时投递同一场，其中一个收到 500，破坏 Spec 006 §6.3 的幂等承诺。
- 建议：把 `focused_delivery` 计算移到 `db.add(ActionLog)` 之前，或把 add+flush 也纳入 try；补同场并发测试断言一个 `delivered`、一个 `already_sent`。

### 3. `FOR UPDATE` 锁不住幻影行，「永不超 3」不是结构保证

- 位置：[letter_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L107-L118)
- 问题：`with_for_update()` 只锁已存在的行；收件人已有 2 封时，两个并发事务都可读到 2 并各自插入，得到 4 封（READ COMMITTED 下 `FOR UPDATE` 不防插入）。
- 后果：Spec 006:21「行锁保证并发下永不超 3」在真实并发下不成立；现有并发测试的通过依赖时序运气。
- 建议：计数前锁收件人 `users` 行（`select(User.id)...with_for_update()`）或 advisory lock；测试用事件/屏障强制两事务同时进入临界区。

### 4. `/mailbox` 缺账号快照守卫（Spec 明确项）

- 位置：[MailboxPage.tsx](file:///d:/AIAgentCode/NovaStart/frontend/src/pages/MailboxPage.tsx#L26-L48)
- 问题：`refresh` 没有捕获请求时的 `userId`、完成时对比当前账号；Spec 006:193 明确要求「沿用 P1/P2/P3 的账号快照守卫」。
- 后果：切账号瞬间，旧账号的在途 `Promise.all` 可能把旧信件写回 state，出现短暂串号（后端按 `X-User-Id` 鉴权，无越权数据）。
- 建议：请求前捕获 `userId`，响应后对比 `useAppStore.getState().userId` 再 setState（参照 SettlePage 的写法）。

### 5. 关键边界无测试

- 位置：`backend/tests/test_letter_send.py`
- 问题：缺 (a) 过期信占用容量（对应第 1 条）、(b) 同场并发幂等（对应第 2 条）、(c) 并发上限（对应第 3 条）三组用例；现有 `test_concurrent_send_only_one_succeeds` 无法证明强保证。
- 建议：随对应修复一并补测试，沿用现有 `db_env` 独立连接模式。

## 低优先（Minor，建议一并处理但不阻塞）

### 6. 「今天累计」实际是归属日累计

- 位置：[session_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/session_service.py#L173-L181) 按 `started_at` 归属日聚合；[SettleSummary.tsx](file:///d:/AIAgentCode/NovaStart/frontend/src/features/settle/SettleSummary.tsx#L39) 文案写「今天累计」。
- 问题：跨零点场次会把昨天累计显示成今天。改文案或改聚合口径，二选一。

### 7. 超长正文在 `already_sent` 之前检查

- 位置：[letter_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/letter_service.py#L97-L105)
- 问题：重试已投递场次时，若历史任务原文超 200 会得到 422 而非 `already_sent`。建议先查 deliver 幂等键再取正文。

### 8. seed 信件 `created_at` 固定当天 12:00

- 位置：[seed.py](file:///d:/AIAgentCode/NovaStart/backend/app/seed.py#L120-L137)
- 问题：中午前 reset 得到「未来」信件；且结算场次若不跨 12:00，`received_during_session` 为 0，「专注时收到 N 封」演示项可能不出现。建议用 `clock.now()` 相对时间。

### 9. `handleDone` 静默回首页

- 位置：[SettlePage.tsx](file:///d:/AIAgentCode/NovaStart/frontend/src/pages/SettlePage.tsx#L81-L90)
- 问题：拉 summary 失败无任何提示直接跳走，用户无法区分「已结算完成」和「请求失败」。（ledger 已记录为已知项，此处列全供决策。）

### 10. 可能显示「连续 0 天」

- 位置：[progress_service.py](file:///d:/AIAgentCode/NovaStart/backend/app/services/progress_service.py#L101-L106)（断档返回 0）+ [SettleSummary.tsx](file:///d:/AIAgentCode/NovaStart/frontend/src/features/settle/SettleSummary.tsx#L65-L77)（原样渲染）。
- 问题：180 封顶补结算的陈旧场次会触发「连续 0 天」。建议 `current=0` 时隐藏连续天数块。

### 11. 其余小项

- `favorite` 对已放弃信可再收藏「复活」进历史、`dismiss` 对已收藏信是 no-op —— API 语义与「放弃不进历史」不完全闭合（UI 不暴露，低危）。
- `letters` 表缺 `user_id`/`session_id` 索引，inbox/outbox 随数据量线性变慢。
- `find_by_name_or_id` 遇重名会 `MultipleResultsFound` 500（`users.name` 无唯一约束，当前仅 seed 造用户，低危）。
- `mark_day_completed`/`recompute_day` 首次建行无并发保护，双标签轮询可能触发唯一键 500（单客户端低概率）。
- `get_current_session` 只按 `started_at desc` 排序，与 `create_session` 的 `id.desc()` 不一致，同时间戳次序不稳定。

## 不需要修的（按文档接受）

- 第④步刷新回首页（P4 已知取舍）
- 满 5 分钟不建 star 行（P5 Ruling）
- 感想无唯一约束（Spec 004 §6.2 单客户端）
- 过期读时懒失效、不后台清扫（Spec 006 §6.3）

## 建议修复顺序

1 → 2 → 3 → 4 → 5（每项配测试），6–10 可同一轮收尾。

## 修复状态与遗留（2026-11-08）

全量验证：`backend/.venv/Scripts/python.exe -m pytest` → **189 passed**；`frontend` `npm run lint` → 0 error（1 条既有 `react-refresh` warning，`components/ui/button.tsx`）；`npm run build` → 成功。

遗留收口轮（2026-11-08）：`backend/.venv/Scripts/python.exe -m pytest` → **192 passed**（新增 3 个用例）；架构棘轮 `test_architecture.py` → 65 passed；`frontend` `npm run lint` → 0 error（同上 1 条既有 warning）；`npm run build` → 成功。

终审补修（独立审查发现）：`c223909` —— `already_sent` 判定在 users 行锁之前，收件人已有 2 封有效未处理信时同场并发重试会走到 `rejected_full` 并多写一条未送达记录；修法为拿锁后重查 deliver 幂等键。用例 `test_concurrent_retry_near_capacity_still_already_sent`（修复前 `['delivered','rejected_full']`）。

| 项 | 状态 | commit | 对应测试 / 说明 |
|---|---|---|---|
| 1 过期占容量 | 已修复 | eee0bbc | `test_expired_unhandled_letters_do_not_block_capacity` |
| 2 同场并发 500 | 已修复 | 06577f0 | `test_concurrent_deliver_same_session_idempotent` |
| 3 幻影行锁 | 已修复 | 4054a3c | 既有 `test_concurrent_send_only_one_succeeds` 回归；无新增用例 |
| 4 信箱账号快照 | 已修复 | bde8951 | 无自动化测试（见遗留） |
| 5 关键边界测试 | 已补 | 见 1/2/3 | 过期占容量、同场并发幂等两组新用例已补；并发上限以 3 的结构保证为准 |
| 6 「今天累计」文案 | 已修复 | 2158951 | 文案改为「当日累计」，聚合口径不变（见遗留） |
| 7 already 前移 | 已修复 | 2fd081c | `test_retry_deliver_with_overlong_content_returns_already_sent` |
| 8 seed 信件时间 | 已修复 | a2e7da8 | `test_seed.py` 断言 `created_at <= clock.now()` |
| 9 handleDone 静默回首页 | 已修复 | 5753c89 | lint + build 通过 |
| 10 连续 0 天展示 | 已修复 | 2158951 | `streak.current > 0` 才渲染 |
| 11-a favorite 复活 | 已修复 | 38d14ec | `test_favorite_handled_letter_409`；新增 409 `LETTER_ALREADY_HANDLED`（契约扩展已批准） |
| 11-b letters 索引 | 已修复 | d969e82 | 迁移 `6c2337279336`，人工核对仅两条 `create_index` |
| 11-c 重名收件人 | 已修复 | 29b2297 | `test_duplicate_recipient_name_picks_smallest_id` |
| 11-d 建行并发 | 已修复 | 2159d75 | 见遗留时序说明 |
| 11-e 当前会话排序 | 已修复 | 2218343 | 与 `create_session` 的 `id.desc()` 一致 |

### 遗留（2026-11-08 收口状态）

1. **T5 账号快照守卫无自动化测试** → 已收口（结构审查 + 人工手测口径）。`MailboxPage.refresh` 守卫保持；`runLetterAction` 已补同样的账号快照（`b90f30d`）。**不做自动化**：前端无单测设施且本轮不新增依赖（已人工确认）。人工手测 3 条（Slow 4G 切账号 / 双标签页放弃-收藏 / Offline 切账号）本轮执行环境无网络节流与离线开关，**待用户手测**。
2. **T6 聚合口径保留** → 已收口：累计口径仍是归属日（`started_at` 的上海时区自然日），但改为显式返回 `attribution_date`（additive 契约扩展，已批准）并由结算页渲染「M月D日累计」，跨零点不再被读成「今天」。用例 `test_summary_attribution_date_across_midnight`（跨零点场次断言 `attribution_date == 2026-11-06` 且 `today_total_sec == 300`）先 RED（`KeyError: 'attribution_date'`）后 GREEN（`f0426a4`）；Spec 004 §6.1 已同步。
3. **T3 / T9d 并发时序** → 已补确定性回归：`test_concurrent_send_only_one_succeeds` 改为「外部事务先锁 `users` 行 + `asyncio.wait_for` 断言必须先阻塞」，并做变异校验（注释掉 `letter_service.py` 的 `with_for_update()` → FAIL，恢复 → PASS）（`67ff9fd`）；新增 `_wait_for_ungranted_lock`（轮询 `pg_locks` 的 `granted=false`）+ `test_concurrent_first_mark_day_other_day_sets_was_reset` / `test_concurrent_first_mark_day_same_day_single_row`（`89f5f26`）。
4. **前端操作链路错误文案** → 已修复：`runLetterAction` 动作开始时捕获 `accountId`，`catch` 内所有 `setError` 先比对账号；409 先判 `LETTER_ALREADY_HANDLED`（「这封信已处理，不能再收藏」），其余 409 仍显示「这封信已经过了一天」，两类 409 都刷新列表（`b90f30d`）。切账号不串扰的 UI 手测同上**待用户手测**。
5. **`progress_service` 回退分支健壮性** → 已修复：两处 `except IntegrityError` 的回退 `select` 补 None 兜底（抛 `RuntimeError`）；`mark_day_completed` 回退后置 `existed = True`，跨日并发首次建行时 `was_reset` 不再误报 False（`89f5f26`）。

