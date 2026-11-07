# Tasks

> 按 [docs/dev-order.md](../../../docs/dev-order.md) 顺序执行，不得插队；每个任务内部按六步流水线：契约 → 迁移 → service → router → 前端 → 端到端。上游未通过第 ⑥ 步，不开始下游。

- [ ] Task 1: F9 多账号与演示辅助：接通 `X-User-Id` 身份入口、3 个演示账号、时间加速与时间旅行。
  - [ ] SubTask 1.1: 契约与迁移：`users` 加 `avatar_color / streak_current / longest_streak / total_completed_days / last_completed_date`，`name` 唯一；写迁移并双向验证。
  - [ ] SubTask 1.2: service/router：`GET /api/users`、`GET /api/me`；统一依赖解析 `X-User-Id`（缺失返回 400 `MISSING_USER`）。
  - [ ] SubTask 1.3: `clock.py` 收敛演示状态（倍率 / 偏移 / 重置），新增 `/dev/clock`、`/dev/clock/reset`；`seed.py` 改为 3 账号（A 连续 6 天 + 未处理信箱 2 封、B 有历史记录）。
  - [ ] SubTask 1.4: 前端：`client.ts` 注入请求头，页头账号切换，页脚演示控制（加速 / 时间旅行 / 重置种子）。
  - [ ] SubTask 1.5: 验证：账号切换数据隔离、加速 60 秒 = 5 分钟、时间旅行断签视图；`pytest` + `npm run lint/build`。

- [ ] Task 2: F1+F2 今日任务与拆分：一天一任务、草稿/分析/采用版、锁定与降级。
  - [ ] SubTask 2.1: 契约与迁移：`day_tasks` 加 `status / split_source / split_for_text / original_starter_step / original_steps`，`(user_id, date)` 唯一；`llm.SplitResult.steps` 改为 `{text, minutes}` 并同步 Mock/OpenAICompat/缓存。
  - [ ] SubTask 2.2: service：`GET/PUT /api/tasks/today`、`POST /api/tasks/today/analyze`、`PATCH /api/tasks/today/steps`；≤200 字、开始后 409、改标题 `analysis_stale`、8s 降级、≤5 分钟空 steps。
  - [ ] SubTask 2.3: 昨日未完成提示与一键带入；示例标签。
  - [ ] SubTask 2.4: 前端首页任务区：输入、分析、采用版编辑、锁定态、降级轻提示。
  - [ ] SubTask 2.5: 删除 `POST /api/tasks` 旧端点与 `SmokePanel`，更新相关测试。
  - [ ] SubTask 2.6: 验证：断网/超时可完整走完「输入 → 分析 → 开始」。

- [ ] Task 3: F3 计时与有效性：正计时、结束判定、中午归属与 180 封顶。
  - [ ] SubTask 3.1: 契约与迁移：`sessions` 加 `duration_sec`（仅有效场次写入）、partial unique `(user_id) WHERE status='active'`；明确 status 语义 `active|completed|settled|discarded`。
  - [ ] SubTask 3.2: service：开始复用 active、`POST /api/sessions/{id}/end`（<5 丢弃、≥5 结算、180 自动）、懒计算按归属日、跨零点处理。
  - [ ] SubTask 3.3: 前端专注页：正计时、5:00 单次轻提示与视觉变化、结束→结算、刷新续算、180 提示。
  - [ ] SubTask 3.4: 验证：4:30 结束全丢弃、12 分钟有效、跨零点归属、刷新续算、重复开始复用。

- [ ] Task 4: F4+F5 结算四步与感想。
  - [ ] SubTask 4.1: 契约：`GET /api/settle/{id}` 摘要与断点；各步业务接口同事务推进 `settle_step`；彩蛋文案字段。
  - [ ] SubTask 4.2: service：摘要计算（时长/当天累计/采用版 starter/星星/连续/专注时来信数）、感想一次写入（`reflections.session_id` 唯一）、断签文案、幂等。
  - [ ] SubTask 4.3: 前端结算页：三段式摘要 + 四步流程（写感想 → 投递 → 处理信箱 → 回顾 → 彩蛋），按 `settle_step` 直达断点。
  - [ ] SubTask 4.4: 验证：中途离开再进直达断点、刷新不重复 +1、感想只读。

- [ ] Task 5: F7 星星与连续天数。
  - [ ] SubTask 5.1: 契约与迁移：新增 `stars`（`user_id, date, level 1–3, minutes`，唯一 `(user_id, date)`）。
  - [ ] SubTask 5.2: service：有效 session 结算/里程碑时更新星星与用户 streak（5/15/25 分级、只升不降、一天 +1、断签归零懒计算保留历史最长）。
  - [ ] SubTask 5.3: `GET /api/progress`：近 14 天星墙（亮 / 当天未完成 / 空心）、当前/最长/累计。
  - [ ] SubTask 5.4: 前端首页星墙 + 连续天数 + 今天状态。
  - [ ] SubTask 5.5: 验证：种子连续 6 天 + 今天完成 → 7 天；多场只累计时长。

- [ ] Task 6: F6 信箱与投递。
  - [ ] SubTask 6.1: 契约与迁移：`letters` 重构为 `sender_id / recipient_id / status(pending|favorited|discarded|expired|undelivered) / delivered_during_focus / expired_at`；回填与删 `handled`。
  - [ ] SubTask 6.2: service：投递（先校验收件人与容量、再写幂等键与信件）、每场 1 次机会、拒收不消耗、行锁 ≤3、收藏幂等、放弃、历史仅收藏 + 100 懒清理、24:00 懒失效、专注时标记。
  - [ ] SubTask 6.3: router：`POST /api/letters`、`POST /{id}/discard`、`GET /sent`，收紧放信门槛（今日未完成 403 `INBOX_LOCKED`）。
  - [ ] SubTask 6.4: 前端：结算第 2/3 步 + 新增信箱页（未处理 / 历史 / 发出记录）。
  - [ ] SubTask 6.5: 验证：B 连投 4 封前 3 成功第 4 拒收且不消耗；A 收藏 1 放弃 2；次日历史只剩 1 封。

- [ ] Task 7: F10 随机回顾。
  - [ ] SubTask 7.1: `GET /api/settle/{id}/review`：排除本场与当天，随机一条，返回日期/任务原文/感想或空态文案。
  - [ ] SubTask 7.2: 前端结算第 4 步卡片 + 点击跳单日详情（依赖 Task 8 的详情路由，可先占位）。
  - [ ] SubTask 7.3: 验证：A 的 6 天种子出现其中一天；新账号只显示「等待宇宙的讯息」。

- [ ] Task 8: F8 记录查询。
  - [ ] SubTask 8.1: `GET /api/records`（`from/to` 可选）+ 汇总（完成天数 / 累计时长 / 完成率）；同日多场「第 X 场」。
  - [ ] SubTask 8.2: `GET /api/records/{date}` 单日详情；空态文案；起止颠倒自动纠正。
  - [ ] SubTask 8.3: 前端记录页：全部 → 区间 → 单日三步；星墙点击联动。
  - [ ] SubTask 8.4: 验证：一次演示完成「全部 → 筛 3 天 → 点进某一天」。

# Task Dependencies

- Task 2 依赖 Task 1（身份与账号隔离先落地）。
- Task 3 依赖 Task 2（任务锁定与拆分字段）。
- Task 4 依赖 Task 3（有效场次判定与结算状态）。
- Task 5 依赖 Task 3、Task 4（完成/结算事件是星星与 streak 的唯一触发点）。
- Task 6 依赖 Task 4（投递机会与结算第 2/3 步）。
- Task 7 依赖 Task 6（结算第 4 步位置）与 Task 8.2（单日详情跳转）。
- Task 8 依赖全部上游（聚合视图最后做）。

# 全局完成门（每个任务都要满足）

- [ ] 六步流水线走完，第 ⑥ 步对照 brainstorming 该功能「演示验收」通过
- [ ] 新增行为有 pytest 用例且已运行通过（`novastart_test`，沙箱外执行）
- [ ] `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py` 通过
- [ ] 有迁移时 `alembic downgrade base` → `upgrade head` 通过
- [ ] 有前端改动时 `npm run lint`、`npm run build` 通过
- [ ] 本 Spec 第 8 节回填该任务的执行结果与遗留问题
