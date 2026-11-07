# NovaStart 完整学习闭环 Spec

> 本 Spec 是本次改动的唯一主记录（需求来源：[brainstorming.md](../../../brainstorming.md) F1–F10；顺序契约：[docs/dev-order.md](../../../docs/dev-order.md)）。为遵守「同一事实只维护一份」，不在 `docs/specs/` 另建副本；第 8 节执行结果回填在本文件末尾。

## Why

仓库当前只完成技术栈骨架与一条最小垂直切片（建任务 → 开场 → 正计时；信箱/结算仅有骨架端点），brainstorming.md 定义的 F1–F10 产品规则大部分尚未落地。本 Spec 按 dev-order 的既定顺序（F9 → F1+F2 → F3 → F4+F5 → F7 → F6 → F10 → F8）补齐剩余功能，让演示脚本可在一台电脑上完整跑通：输入任务 → 5 分钟专注 → 结算四步 → 星星/连续天数 → 投信/收信 → 三种记录查询。

## What Changes

* **F9 多账号**：接入请求头 `X-User-Id` 作为统一身份入口；3 个演示账号可切换；种子数据改为 A 连续 6 天 + 未处理信箱 2 封、B 有历史记录；演示时间加速（60 秒 = 5 分钟）与时间旅行开关统一收敛到 `clock.py`。

* **F1+F2 今日任务与拆分**：今日任务从「创建即拆分」改为「草稿 / 分析 / 采用版编辑」三段；一天一个任务；开始时锁定文案；模型原始版与当前采用版双份保存；分析后改标题只提示不自动重调；拆分结果每步带预计分钟数，任务本身 ≤5 分钟时无后续步骤。

* **F3 计时与有效性**：新增「结束会话」；<5 分钟本场无效完全丢弃；5–180 分钟有效；满 5 分钟服务端懒计算标记完成（完成时刻 = `started_at + 5min`，归属 `started_at` 自然日）；180 分钟自动结束；重复开始复用进行中会话。

* **F4+F5 结算四步与感想**：结算摘要（时长、当天累计、采用的 starter 原话、星星、连续）、`settle_step` 断点续做、感想只读一次写入、末步彩蛋文案；④ 随机回顾接口（排除本场与当天）。

* **F7 星星与连续天数**：新增 `stars` 表与用户 streak 字段；亮度 5/15/25 分钟分三级、只升不降；一天一颗星、一次连续 +1；断签次日归零并保留历史最长；首页进度视图。

* **F6 信箱与投递**：信件改为 `sender_id / recipient_id / status` 模型；每场 1 次投递机会，拒收/找不到收件人不消耗机会（修正现有「先写幂等键再判断满员」的顺序问题）；未处理 ≤3 行锁、收藏幂等、历史仅存收藏且 100 封懒清理、未收藏当日 24:00 懒失效；新增「专注时投递」标记。

* **F10 随机回顾**：结算最后一步从用户历史中抽取一条（排除当天），无历史时只显示一句空态。

* **F8 记录查询**：全部 / 区间 / 单日三查法；区间汇总；同一天多场标注「第 X 场」；全部只读。

* **前端**：补齐首页（账号切换、任务输入、示例标签、进度、信箱入口）、专注页、结算四步页、记录页、信箱页；删除临时 SmokePanel；所有请求走 `client.ts` 并注入 `X-User-Id`，时间只走 `useServerClock`。

* **BREAKING**（需在本次批准内确认）：

  * `POST /api/tasks`（创建即拆分）改为 `GET/PUT /api/tasks/today` + `POST /api/tasks/today/analyze` + `PATCH /api/tasks/today/steps`。

  * `letters` 表重构：`user_id` 语义改为 `recipient_id` 并新增 `sender_id`、`status`、`delivered_during_focus`；`handled` 字段移除。

  * `llm.SplitResult.steps` 由 `list[str]` 改为 `list[{text, minutes}]`，Mock/OpenAICompat/缓存键同步调整。

  * `POST /api/letters` 的投递语义重写（现有 `deliver` 服务函数签名与「先占幂等键」顺序必须改）。

## Impact

* 受影响能力：F1–F10 全部产品功能（本次一次性覆盖）。

* 受影响代码：

  * 后端：`backend/app/models/*`、`schemas/*`、`services/*`、`routers/*`、`llm/*`、`seed.py`、`clock.py`、`main.py`、`backend/alembic/versions/*`、`backend/tests/*`

  * 前端：`frontend/src/{api,store,hooks,pages,features,App.tsx}`

* 不受影响：技术栈与启动方式（仍 `python -m app.main`）、`docker-compose.yml` 交付链路（本机仍不验证）、`test_architecture.py` 棘轮语义（只新增依赖检查项，不放宽）。

## 现状基线（实现前必须知道）

已有且可复用：

* `Clock`（`backend/app/clock.py`）：Asia/Shanghai 时间唯一来源，`offset_seconds` 仅实例字段。

* `backend/app/llm/`：可插拔拆分器 + 8s 超时降级 + 模块级 LRU(128)。

* 端点：`POST /api/tasks`、`POST /api/sessions`、`GET /api/sessions/current`（懒计算 5/180 分钟）、`GET /api/letters/inbox|history`、`POST /api/letters/{id}/favorite`、`POST /api/settle/{id}/advance`。

* 表：`users / day_tasks / sessions / letters / reflections / action_logs`（迁移 `3f960f8ca64d`、`183ba71acbc5`）。

* 前端：`client.ts`（server\_time 偏移）、`store/app.ts`、`useServerClock.ts`、四页占位 + `SmokePanel`。

必须替换/修正：

* `session_service.get_current_session` 只标记完成，不结算、不判有效性、无归属日处理。

* `letter_service.deliver` 先写 `ActionLog(deliver)` 再判满员 → 拒收也消耗机会，违反 A9。

* `letter_service.get_history` 把「已处理」也当历史，违反 A10（历史只存收藏）。

* `POST /api/tasks` 无「一天一任务」「草稿/锁定/双版本」概念。

* 无 `stars` 表、无用户 streak 字段、无多账号身份注入。

## 范围与非目标

* 范围：F9 → F1+F2 → F3 → F4+F5 → F7 → F6 → F10 → F8，每功能按 dev-order 六步流水线走完（契约 → 迁移 → service → router → 前端 → 端到端）。

* 非目标（明确不做）：

  * 真实 LLM prompt 调优；沿用现有可插拔 + Mock 默认 + 降级策略。

  * 内容审核（只做长度截断）、补签 / 连续保护卡、日详情页展示信件往来。

  * 新增任何依赖、改造启动方式、多 worker 部署。

  * Docker 端到端验证（本机不可用，沿用 dev-pitfalls 记录）。

  * `docs/specs/` 副本（主记录仅本文件）。

***

## ADDED Requirements

### Requirement: F9 身份与演示辅助

系统 SHALL 以请求头 `X-User-Id` 作为当前用户唯一身份来源，并 SHALL 仅在演示环境提供时间加速与时间旅行。

#### Scenario: 请求头缺失

* **WHEN** 业务请求缺少 `X-User-Id`

* **THEN** 返回 400 + 稳定错误码 `MISSING_USER`，不写任何数据

#### Scenario: 账号切换

* **WHEN** 用户在页头切换到「小美」

* **THEN** 首页进度、记录、信箱一次性切换为小美的数据，后续请求头均为小美 id

#### Scenario: 演示加速

* **WHEN** 演示环境开启 5× 加速后开始一场学习

* **THEN** 真实 60 秒后前端显示 05:00、服务端按算法判定满 5 分钟；关闭后恢复真实时间

#### Scenario: 时间旅行

* **WHEN** 演示环境把「现在」设为昨天且当天有未完成记录

* **THEN** 首页展示断签归零后的连续天数与「新的一条线，从今天这 5 分钟开始」文案

### Requirement: F1 今日任务创建与编辑

系统 SHALL 每个自然日只维护一个今日任务，并 SHALL 在计时开始前允许编辑、开始后锁定。

#### Scenario: 首次进入

* **WHEN** 当天无任务进入首页

* **THEN** 展示引导语 + 示例标签 +「5 分钟只做第一步」说明，不显示空白页

#### Scenario: 编辑任务

* **WHEN** 任务为草稿或已生成且未开始，用户修改标题并保存

* **THEN** 同一任务行被更新，不新建第二天任务行

#### Scenario: 开始后修改

* **WHEN** 任务已开始计时，用户尝试改标题

* **THEN** 返回 409 + `TASK_LOCKED`，前端锁定输入框

#### Scenario: 昨日未完成

* **WHEN** 昨天存在未完成（无 ≥5 分钟有效场次）的任务

* **THEN** 首页提示「昨天没走完，今天要不要接着来？」并提供一键带入，不自动继承

### Requirement: F2 任务拆分

系统 SHALL 在学生点「分析」时调用拆分器，产出 1 个 5 分钟内 starter 与 0–3 个带分钟数的后续步骤，并 SHALL 在超时/异常时降级且不阻塞流程。

#### Scenario: 正常拆分

* **WHEN** 输入「背 20 个单词」并点「分析」

* **THEN** 返回 starter + steps（每步含预计分钟数）与 `source`，并持久化保存

#### Scenario: 任务本身 ≤5 分钟

* **WHEN** 拆分器判断任务整体可在 5 分钟内完成

* **THEN** `steps` 为空，界面不显示「继续」区

#### Scenario: 超时或异常

* **WHEN** 拆分超过 8 秒、报错或返回空/无动作

* **THEN** 立即使用规则模板并标注 `source=fallback`，流程可继续，不显示失败

#### Scenario: 改标题后保留旧拆分

* **WHEN** 已分析过，用户改了标题但未重新分析

* **THEN** 保留原拆分并标记 `analysis_stale=true`，提示「标题已修改，可重新分析」，不自动清空、不自动重调

#### Scenario: 手动编辑拆分

* **WHEN** 学生在未开始时修改 starter 或删除后续步骤

* **THEN** 当前采用版被更新，模型原始版保持不变；结算复述使用采用版

### Requirement: F3 计时与有效性

系统 SHALL 只提供正计时、不支持暂停，并 SHALL 在服务端按归属日懒计算完成标记。

#### Scenario: 满 5 分钟

* **WHEN** 进行中会话达到 `started_at + 5min`

* **THEN** 服务端标记完成并记录完成时刻为 `started_at + 5min`；界面出现一次鼓励提示，计时继续、不跳转

#### Scenario: 刷新 / 断网 / 跨零点

* **WHEN** 页面刷新或跨零点后重新进入

* **THEN** 计时按服务端时间续算；跨零点场次仍归属 `started_at` 所在自然日；首页优先显示进行中场次

#### Scenario: 提前结束

* **WHEN** 学生在 4 分 30 秒点「结束」

* **THEN** 本场 `status=discarded`、`duration_sec=NULL`，不累计时长、不加星星、不给投递机会、不计连续，只提示差额

#### Scenario: 正常结束

* **WHEN** 学生在 12 分钟点「结束」

* **THEN** `status=settled`、`duration_sec=720`，当天累计与星星亮度更新，首次达标使连续 +1

#### Scenario: 重复开始

* **WHEN** 用户已有 `active` 会话时再次点开始

* **THEN** 复用该会话，不新建

#### Scenario: 180 分钟封顶

* **WHEN** 会话到达 `started_at + 180min`

* **THEN** 自动结束为 `settled`、`ended_at=started_at+180min`、时长按 180 分钟计，提示「这次已经学够久了」

> **与 F7 的衔接说明**：Task 3 只产生「完成事实」（session 状态与有效时长），星星与连续天数的写入/展示在 Task 5（F7）接入。因此 Task 3 的第 ⑥ 步只验收计时与有效性，`星星点亮 / streak +1` 的演示验收随 Task 5 一起完成，避免在 F7 前提前建 `stars` 表造成重复迁移。

### Requirement: F4+F5 结算与感想

系统 SHALL 在有效场次结束后进入固定四步结算，并 SHALL 用 `settle_step` 支持断点直达。

#### Scenario: 结算摘要

* **WHEN** 用户结束一场有效学习

* **THEN** 一屏显示本次时长、当天累计、采用版 starter 原话、星星点亮动画、连续天数与具体钩子文案

#### Scenario: 写感想

* **WHEN** 用户在第一步提交 ≤200 字感想

* **THEN** 感想挂到该 session 且只写一次，`settle_step` 推进到 1；空提交等于跳过并推进

#### Scenario: 中途离开

* **WHEN** 用户完成第 2 步后关闭页面，下次再进入

* **THEN** 直接打开第 3 步，不重复结算、不重复加连续天数

#### Scenario: 断签后首次完成

* **WHEN** 用户断签后再次完成一场

* **THEN** 展示「新的一条线，从今天这 5 分钟开始」，不显示「你断了」

#### Scenario: 结算收尾

* **WHEN** 四步全部完成

* **THEN** 角落显示固定彩蛋文案「来自宇宙的音讯」，本场标记结束

> **与 F7 的衔接说明**：Task 4 先交付结算摘要的时长/累计/采用版 starter、四步流程与感想；摘要中的星星/连续字段与「一屏内星星动画」在 Task 5（F7）接入后补齐，属同结构内的追加字段，不改变已交付契约。

### Requirement: F7 星星与连续天数

系统 SHALL 一天一颗星、一天最多 +1 连续天数，并按有效累计时长分三级亮度。

#### Scenario: 点亮

* **WHEN** 某自然日有效累计达 5 分钟

* **THEN** 该日星星点亮 Lv1，连续天数 +1（当天已 +1 则不重复）

#### Scenario: 亮度提升

* **WHEN** 同一天有效累计达到 15 / 25 分钟

* **THEN** 亮度升到 Lv2 / Lv3，封顶 Lv3，只升不降

#### Scenario: 跨零点继续学习

* **WHEN** 23:58 开始、次日 00:10 结束

* **THEN** 全部时长计入 23:58 那颗星，不产生次日星星

#### Scenario: 断签

* **WHEN** 某自然日没有任何有效场次

* **THEN** 次日当前连续归零，历史最长与累计完成天数保留

#### Scenario: 进度展示

* **WHEN** 用户打开首页

* **THEN** 看到近 14 天星墙（亮 / 当天未完成 / 空心断签）、当前连续、历史最长、今天状态

### Requirement: F6 信箱与投递

系统 SHALL 为每场有效学习提供 1 次投递机会，并 SHALL 用行锁保证未处理信箱 ≤3 封。

#### Scenario: 投递成功

* **WHEN** 用户在第 2 步填写收件人并寄出

* **THEN** 信件进入对方未处理信箱；对方正在学习则打「专注时投递」标签；本场机会用尽

#### Scenario: 对方信箱已满

* **WHEN** 收件人未处理信箱已有 3 封

* **THEN** 发送方看到「对方信箱已满」，发出记录标「未送达」，不消耗本场机会，可改寄

#### Scenario: 收件人不存在

* **WHEN** 填写的用户名/ID 找不到

* **THEN** 提示「找不到这位同学」，不消耗机会

#### Scenario: 并发投递

* **WHEN** 两个发送方同时投给已收 2 封的用户

* **THEN** 只有 1 封成功，另一封拒收，信箱永不超 3 封

#### Scenario: 处理来信

* **WHEN** 用户在结算第 3 步逐封处理

* **THEN** 收藏 1 封进入历史信箱，放弃的信当天 24:00 后失效且不进入历史

#### Scenario: 历史信箱

* **WHEN** 收藏超过 100 封

* **THEN** 读取时静默删除最旧信件，保 100 封

#### Scenario: 收信门槛

* **WHEN** 用户今天尚未完成 5 分钟

* **THEN** 信箱入口置灰并显示「完成今天的学习后开启」

#### Scenario: 投递幂等

* **WHEN** 同一场连点发送 / 重复收藏

* **THEN** 只入库一次，返回一致结果

### Requirement: F10 随机回顾

系统 SHALL 在结算第 4 步随机展示一条本人过去的学习记录，排除本场与当天。

#### Scenario: 有历史

* **WHEN** 用户有过去记录

* **THEN** 展示日期 + 任务原文 + 感想（无感想只显示任务原文），可点击跳转到该日详情

#### Scenario: 无历史

* **WHEN** 用户第一次完成或当天只有这一场

* **THEN** 只显示「等待宇宙的讯息」，不报错、不加额外引导

### Requirement: F8 记录查询

系统 SHALL 提供全部、日期区间、指定日期三种只读查询，并在同日多场时标注场次。

#### Scenario: 全部记录

* **WHEN** 用户打开记录页

* **THEN** 按日期倒序展示日期、时长、任务原文、拆分完成情况、感想、星星亮度；同日多场标「第 X 场」并列

#### Scenario: 区间查询

* **WHEN** 选择起止日期

* **THEN** 返回区间记录与汇总（完成天数、累计时长、完成率）；起止颠倒时自动纠正并提示

#### Scenario: 单日查询

* **WHEN** 点击星墙某天

* **THEN** 进入该日详情；无数据显示「还没有记录，今天这 5 分钟就是第一条」

***

## MODIFIED Requirements

### Requirement: 任务创建接口

`POST /api/tasks` 的「创建即拆分」语义 SHALL 被今日任务三段式取代：`PUT /api/tasks/today` 建/改草稿，`POST /api/tasks/today/analyze` 触发拆分，`PATCH /api/tasks/today/steps` 保存采用版。旧端点 SHALL 在 Task 2 内删除，前端与测试同步迁移，不保留兼容层。

### Requirement: 信件数据模型与投递顺序

`letters` SHALL 使用 `sender_id / recipient_id / status`，且投递 SHALL 先校验收件人与容量、再写幂等键与信件（同一事务）；拒收/找不到不得留下「已投递」的动作记录。

### Requirement: 结算推进

`settle_step` SHALL 只进不退（现有条件更新保留），并 SHALL 由各步业务接口在同一事务内推进，不再由前端随意指定 `to_step` 跳步；`GET /api/settle/{id}` 返回断点供前端直达。

## REMOVED Requirements

### Requirement: 单端点创建并拆分任务

**Reason**: 无法表达「一天一任务 / 草稿可编辑 / 开始锁定 / 双版本 / 改标题保留旧拆分」。
**Migration**: 前端改调 `PUT /api/tasks/today` + `POST /api/tasks/today/analyze`；`test_session_api.py` 内建任务辅助函数随之改写。

### Requirement: `letters.handled` + `expired_at` 二元状态

**Reason**: 无法区分「放弃 / 收藏 / 过期 / 未送达」，且历史信箱不应包含未收藏信件。
**Migration**: 新迁移新增 `status`、`sender_id`、`recipient_id`、`delivered_during_focus`；将 `handled=true` 且 `favorited=true` 的行回填 `status='favorited'`，其余 `handled=true` 回填 `discarded`；删除 `handled` 列。

***

## 4. 现有 owner 和受影响模块

| 模块 / 文件                                          | 角色                      | 改动方式                                         |
| ------------------------------------------------ | ----------------------- | -------------------------------------------- |
| `backend/app/clock.py`                           | 时间唯一 owner              | 增加演示倍率/偏移的单一入口；保持实例无模块级可变散状态                 |
| `backend/app/models/user.py`                     | streak / 昵称 / 头像色 owner | 加字段 + 迁移                                     |
| `backend/app/models/day_task.py`                 | 今日任务与双版本 owner          | 加 status / split 字段 + 唯一约束                   |
| `backend/app/models/session.py`                  | 会话与有效性 owner            | status 语义、duration 可空、partial unique(active) |
| 新增 `backend/app/models/star.py`                  | 星星唯一 owner              | 新表 + `(user_id, date)` 唯一                    |
| `backend/app/models/letter.py`                   | 信件生命周期 owner            | 重构 sender/recipient/status                   |
| `backend/app/models/reflection.py`               | 感想 owner                | `session_id` 唯一                              |
| `backend/app/models/action_log.py`               | 幂等 owner                | 不变（语义扩展到 send/favorite）                      |
| `backend/app/services/session_service.py`        | 计时/有效性/结算入口             | 重写 end、归属日、懒计算                               |
| `backend/app/services/letter_service.py`         | 信箱容量/失效/收藏 owner        | 重写投递顺序、历史仅收藏、放弃                              |
| 新增 `backend/app/services/progress_service.py`    | 星星/连续 owner             | 新文件（理由：进度聚合与 session 生命周期独立）                 |
| 新增 `backend/app/services/record_service.py`      | 记录查询 owner              | 新文件（理由：只读聚合，避免撑大 session\_service）           |
| 新增 `backend/app/services/review_service.py`      | 随机回顾 owner              | 新文件（理由：结算末步独立只读逻辑）                           |
| `backend/app/llm/*`                              | 拆分契约 owner              | steps 带分钟数，≤5 分钟返回空 steps                    |
| `backend/app/seed.py`                            | 演示数据 owner              | 3 账号 + 6 天 + 预置信箱                            |
| `frontend/src/api/client.ts`                     | HTTP + 身份 owner         | 注入 `X-User-Id`，业务错误码透出                       |
| `frontend/src/pages/*`、`frontend/src/features/*` | 展示层                     | 重写首页/专注/结算/记录 + 新增信箱页                        |
| `backend/tests/*`                                | 行为验证                    | 每功能补 API/服务用例（`novastart_test`）              |

## 5. 实现步骤（与 tasks.md 一一对应）

1. **F9**：users 字段与演示账号 → 请求头依赖 → 前端账号切换与演示控制。
2. **F1+F2**：day\_tasks 契约与迁移 → 今日任务/分析/采用版 service → router → 首页任务区。
3. **F3**：sessions 有效性契约 → end/懒计算/归属日 → 专注页计时与结束。
4. **F4+F5**：结算摘要与四步 → 感想接口 → 结算页断点续做。
5. **F7**：stars 表与 streak → 进度接口 → 星墙。
6. **F6**：信件重构与投递顺序 → 信箱/收藏/放弃/发出记录 → 结算第 2/3 步与信箱页。
7. **F10**：回顾抽取 → 结算第 4 步卡片。
8. **F8**：三查法与汇总 → 记录页与单日详情。

## 6. 接口、数据及兼容性变化

* 迁移：按功能分 4 个 revision（users/day\_tasks → sessions → stars → letters/reflections），每个都需 `alembic downgrade base` → `upgrade head` 双向通过；不修改已应用的历史 revision。

* API：见上「ADDED / MODIFIED / REMOVED」；所有响应继续带 `server_time`；错误返回统一 `{code, message}`。

* 前端类型：全部由后端 schema 派生/跟随，不允许先定义字段。

* 数据兼容：Demo 无生产数据，迁移以「重建语义」为主；`/dev/reset-seed` 支持一键恢复种子，跑多轮演示无需手工准备。

### 6.1 API 契约明细（字段级）

所有业务接口均要求请求头 `X-User-Id`，响应均含 `server_time`（ISO8601，Asia/Shanghai）。列表中的 `→` 表示请求 → 响应。

| 接口                            | 方法    | 请求                                     | 响应关键字段                                                                                                                                                                             |
| ----------------------------- | ----- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/api/users`                  | GET   | —                                      | `users[{id,name,avatar_color}]`                                                                                                                                                    |
| `/api/me`                     | GET   | —                                      | `user{id,name,avatar_color}, progress_summary`                                                                                                                                     |
| `/api/tasks/today`            | GET   | —                                      | `task{id,raw_text,status,starter_step,steps[{text,minutes}],source,analysis_stale,can_edit}` 或 `task=null`；`yesterday_unfinished{raw_text}\|null`                                  |
| `/api/tasks/today`            | PUT   | `{raw_text}`                           | 同上 `task`（新建或更新草稿）                                                                                                                                                                 |
| `/api/tasks/today/analyze`    | POST  | —                                      | `starter_step, steps[{text,minutes}], source(llm\|mock\|fallback), from_cache`                                                                                                     |
| `/api/tasks/today/steps`      | PATCH | `{starter_step?, steps?}`              | 更新后的 `task`（仅未开始时允许）                                                                                                                                                               |
| `/api/sessions`               | POST  | `{task_id}`                            | `{session_id, started_at, elapsed_sec, status, milestone_reached}`                                                                                                                 |
| `/api/sessions/current`       | GET   | —                                      | `session{id,started_at,elapsed_sec,status,milestone_reached,task{raw_text,starter_step,steps}}\|null`                                                                              |
| `/api/sessions/{id}/end`      | POST  | —                                      | `{valid,duration_sec,today_total_minutes,status}`；无效时 `valid=false,duration_sec=null`                                                                                              |
| `/api/settle/{id}`            | GET   | —                                      | `{duration_sec,today_total_minutes,starter_text,star{date,level},streak{current,longest},letters_during_focus,settle_step,next_step,cosmic_message?}`；`star/streak` 字段自 Task 5 起返回 |
| `/api/settle/{id}/reflection` | POST  | `{content?}`                           | `{settle_step, reflection\|null}`；空内容 = 跳过                                                                                                                                         |
| `/api/settle/{id}/advance`    | POST  | `{to_step}`                            | `{settle_step}`；只进不退，跨步由业务接口调用                                                                                                                                                     |
| `/api/settle/{id}/review`     | GET   | —                                      | `{item{date,task_text,reflection\|null,session_id}\|null, message?}`；同时推进到 4                                                                                                       |
| `/api/letters`                | POST  | `{session_id, recipient, content?}`    | `{result: delivered\|undelivered, reason?: inbox_full\|unknown_recipient, letter?, chance_consumed}`                                                                               |
| `/api/letters/inbox`          | GET   | —                                      | `letters[{id,content,delivered_during_focus,created_at}]`（仅 pending 且未过期）                                                                                                          |
| `/api/letters/{id}/favorite`  | POST  | —                                      | `{letter}`（幂等）                                                                                                                                                                     |
| `/api/letters/{id}/discard`   | POST  | —                                      | `{letter}`（幂等）                                                                                                                                                                     |
| `/api/letters/history`        | GET   | —                                      | 仅 `favorited`，≤100，按收到时间倒序                                                                                                                                                         |
| `/api/letters/sent`           | GET   | —                                      | `letters[{id,recipient_label,status,created_at}]`                                                                                                                                  |
| `/api/progress`               | GET   | `?days=14`                             | `{today{date,completed,total_minutes,star_level}, streak{current,longest,total_days,last_completed_date}, stars[{date,level,minutes,state:lit\|today_pending\|missed}]}`           |
| `/api/records`                | GET   | `?from=&to=`（可选）                       | `{days:[{date,star_level,total_minutes,sessions:[{index,duration_sec,task_text,starter_text,reflection}]}], summary{completed_days,total_minutes,completion_rate}}`                |
| `/api/records/{date}`         | GET   | —                                      | `{date,star_level,total_minutes,sessions[...]}` 或空态                                                                                                                                |
| `/dev/clock`                  | POST  | `{speed_multiplier?, offset_seconds?}` | `{clock{effective_now,speed_multiplier,offset_seconds}}`，仅演示环境                                                                                                                     |
| `/dev/clock/reset`            | POST  | —                                      | 恢复真实时间                                                                                                                                                                             |

### 6.2 错误码表

| code                  | HTTP                       | 场景                               |
| --------------------- | -------------------------- | -------------------------------- |
| `MISSING_USER`        | 400                        | 缺少或非法 `X-User-Id`                |
| `USER_NOT_FOUND`      | 404                        | 请求头指向不存在的账号                      |
| `TASK_LOCKED`         | 409                        | 已开始计时后编辑任务/拆分                    |
| `TASK_TEXT_INVALID`   | 400                        | 空输入或超 200 字                      |
| `SESSION_NOT_FOUND`   | 404                        | 会话不存在或不属于当前用户                    |
| `SESSION_NOT_SETTLED` | 409                        | 对未结算会话请求结算摘要                     |
| `INBOX_LOCKED`        | 403                        | 今日未完成 5 分钟却请求信箱                  |
| `LETTER_EXPIRED`      | 409                        | 收藏已失效信件                          |
| `INBOX_FULL`          | 200 + `result=undelivered` | 对方未处理信箱已满（不作为 HTTP 错误，避免前端误判为失败） |
| `RECIPIENT_NOT_FOUND` | 200 + `result=undelivered` | 收件人不存在                           |
| `CHANCE_USED`         | 409                        | 同一场重复投递                          |

### 6.3 状态机

* **DayTask**：`draft` →（analyze）`generated` →（POST /sessions）`started`；`draft/generated` 可反复编辑，`started` 锁定。

* **Session**：`active` →（满 5min 懒计算）`completed` →（点结束或 180min 自动）`settled`；`active` →（<5min 结束）`discarded`。`settled` 后只允许 `settle_step` 递增。

* **Letter**：`pending` →（收藏）`favorited`；`pending` →（放弃）`discarded`；`pending` →（当日 24:00 懒失效）`expired`；投递即拒收/找不到 → `undelivered`（仅出现在发送方记录）。

* **settle\_step**：0 → 1（感想）→ 2（投递）→ 3（处理信箱）→ 4（随机回顾，结束）；只进不退。

### 6.4 前端路由与页面职责

| 路由         | 页面              | 职责                                                     |
| ---------- | --------------- | ------------------------------------------------------ |
| `/`        | HomePage        | 账号切换、今日状态、连续天数、14 天星墙、任务输入 + 示例标签 + 分析/采用版编辑、昨日带入、信箱入口 |
| `/focus`   | FocusPage       | 正计时、5:00 轻提示与视觉变化、结束按钮、180 分钟提示、刷新续算                   |
| `/settle`  | SettlePage      | 摘要三段式、四步流程按 `settle_step` 直达断点、彩蛋                      |
| `/records` | RecordsPage     | 全部 / 区间 / 单日三查法、多场「第 X 场」、空态                           |
| `/mailbox` | MailboxPage（新增） | 未处理（收藏/放弃）、历史（仅收藏）、发出记录                                |
| 页脚         | DemoControls    | 演示加速、时间旅行、重置种子；仅演示环境渲染                                 |

所有页面数据只经 `client.ts` + `store` + `hooks`，不得直接 `fetch` 或 `new Date()`。

## 7. 测试场景与验证命令

从第 3 节验收条件推导，至少覆盖：

* 身份：缺请求头 400；账号切换后数据隔离。

* 任务：一天一任务；开始后编辑 409；改标题 `analysis_stale`；超时降级；≤5 分钟 steps 为空。

* 计时：<5 分钟丢弃（duration 为空、无星、无机会、streak 不变）；≥5 分钟结算；刷新续算；跨零点归属；180 分钟封顶；重复开始复用。

* 结算：四步顺序、断点直达、感想一次写入、彩蛋、断签文案。

* 进度：5/15/25 三级；一天 +1；断签归零保留最长。

* 信箱：满 3 拒收且不消耗机会；并发只有 1 封成功；收藏幂等；历史仅收藏且 100 上限；24:00 失效；未完成不可收信。

* 记录：全部/区间/单日；多场标注；空态；起止颠倒纠正。

命令（本机沙箱约束见 dev-pitfalls）：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
cd backend; .venv\Scripts\python.exe -m pytest
cd frontend; npm run lint; npm run build
```

连库/起服务命令一律 `dangerouslyDisableSandbox: true`；PG 用 WMI 方式启动；后端只用 `python -m app.main`。

## 8. 执行结果、未验证项和遗留问题

（实现完成后回填：跑了哪些命令、结果如何；哪些没验证、为什么；遗留问题及边界。区分「测试已编写」与「测试已运行通过」。）

***

## 结构性变更五问

1. **修改哪一层？** 主要改 `models → services → routers` 并新增前端页面；schemas 跟随契约先行。
2. **当前 owner 在哪里？** 时间 `clock.py`、会话/结算 `sessions` 表 + `session_service`、信箱 `letter_service`、幂等 `action_logs`；新增 stars/record/review 三个只读或独立聚合 service，理由见第 4 节。
3. **是否引入重复状态或平行写入？** 不引入。星星/连续由有效 session 派生并只在 service 内写；前端只显示；不建第二套计时或信箱状态。
4. **是否影响接口和其他模块？** 影响范围见第 6 节，含 3 处 **BREAKING**（任务接口、信件模型、拆分契约），本次批准视为确认。
5. **哪些现有检查需要继续通过？** `test_architecture.py` 棘轮、`test_clock.py`、`test_llm.py`、`test_letter_settle.py`（按新语义更新）、`test_session_api.py`（按新接口更新）、`npm run lint/build`。

