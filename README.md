# NovaStart 项目说明

> 一个把「今天想学点什么」压缩成「5 分钟就能开始的第一步」的学习 Demo。
> 本文面向第一次接触本项目的评审 / 开发者，说明反馈与激励设计、项目亮点、基本用法、功能实现流程，以及已经处理掉的异常与兜底。
> 需求与规则的唯一主记录是 [brainstorming.md](brainstorming.md)；本文只做导览，不复述全部规则。

---

## 1. 用户如何得到反馈，以及激励设计与项目亮点

### 1.1 反馈链：从「开始」到「被记住」

| 时刻 | 用户看到什么 | 设计意图 |
|---|---|---|
| 满 5 分钟 | 里程碑提示 + 背景变亮 + 星星效果，**不跳转、不停表** | 用提示而不是倒计时掐断，避免把刚进入状态的人拽出来 |
| 点结束 | 结算摘要：本次时长、归属日累计、starter 原话复述 | 用具体成果代替「恭喜完成任务」的空话 |
| 摘要下半 | 星星点亮动画、连续天数大数字、历史最长 | 一屏内讲清「你做成了什么」 |
| 第①步 | 写一句感想（选填，200 字，只写一次） | 趁情绪高点留下记忆，不强制 |
| 第②步 | 把这一场寄给一位同学（每场 1 次） | 把「学完」变成对别人的一次真实表达 |
| 第③步 | 处理来信：收藏或放弃，最多 3 封 | 情绪冷却后再做收藏决策 |
| 第④步 | 「过去的你」：某天的任务 + 感想 | 让积累从数字变成具体记忆 |
| 四步完成 | 「来自宇宙的音讯」一句预置文案 | 温柔收尾，零外部依赖 |

### 1.2 鼓励持续学习的四个机制

1. **门槛压到 5 分钟，且满 5 分钟自动完成**——降低「今天算了」的心理成本；正计时不设暂停、不惩罚离开（学生可能在做纸笔练习）。
2. **星星亮度只升不降**——当天有效累计 5 / 15 / 25 分钟对应 Lv1 / Lv2 / Lv3；同一天多场只累计时长，连续天数一天只 +1，防刷且把「继续学」和「打卡」分开。
3. **信件作为外部承诺**——完成今天的学习才能收信；信来自同学，社交关系成为回来的理由，而不是排行榜压力。拒收、未收藏当日失效等规则让信箱保持轻量。
4. **随机回顾作为收尾**——第④步必然出现一条过去的记录，把「坚持」翻译成「我那天写了什么」。

### 1.3 项目亮点

**产品与体验**

- 只做正计时 + 服务端自动里程碑：反馈及时但不打断。
- 一天的星星墙同时展示「已点亮 / 今天未完成 / 断签」三态，缺口可见但不刺眼；断签文案是「新的一条线，从今天这 5 分钟开始」，不指责用户。
- 结算顺序被固定为「感想 → 投递 → 处理信箱 → 回顾」：先趁热表达，再情绪冷却后理性处理来信。
- 视觉全部用 CSS 渐变 / conic 描边 / WebGL 粒子与流星实现，**不依赖任何图片资源**；专注页在 `prefers-reduced-motion` 或 WebGL2 不可用时退化为静态渐变。

**工程**

- 服务端单一真相源：`Clock`、`settle_step`、`action_logs`、行锁，均只有一条写入路径。
- 用懒计算 / 懒失效替代定时任务：5 分钟与 180 分钟判定、信件 24:00 失效、历史信箱 100 封清理，都在读取或请求时完成，不需要 Redis / Celery / pg_cron。
- 可插拔模型：同一个 `TaskSplitter` 协议下，Mock / OpenAI 兼容实现互换；8 秒超时、异常、格式不合规全部降级，且结果按「文本 + 日期」缓存。
- 工程约束机械化：架构棘轮测试检查分层、`Clock` 用法、router 互引；每个功能一份 Spec，完成门包含真实运行过的命令。

---

## 2. 项目是什么

学生输入今天的学习目标，系统把它拆成「5 分钟 starter + 后续步骤」；点开始后进入正计时，满 5 分钟由服务端自动点亮当天星星、连续天数 +1，但不打断计时。结束后进入结算四步：写感想、把感想寄给同学、处理来信、随机回顾一条过去的记录。当天可再学多场，但连续天数一天只加一次。

技术与交付：

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Tailwind 3 + shadcn/ui 2.4 + framer-motion + Zustand + Axios |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0（异步）+ Alembic |
| 数据库 | PostgreSQL 16 |
| 交付 | Docker Compose（postgres + backend + frontend/nginx）；也支持本机三服务开发 |
| 任务拆分 | 可插拔：默认 Mock 模板，配置 `LLM_API_KEY` 后走任意 OpenAI 兼容接口 |

演示数据为**模拟数据**：固定 3 个账号（小明 / 小美 / 小刚），由 `POST /dev/reset-seed` 重置；重置只保留这 3 个演示账号，并尽量复用其原有 id，避免前端已保存的登录态失效。

---

## 3. 基本用法

### 3.1 启动方式

**A. Docker 一键交付**

```powershell
# 项目根目录
start.bat            # 等价于 docker compose up -d --build
# 浏览器打开 http://localhost
```

> 说明：本机 Docker Desktop 不可用，这条链路尚未在本机端到端验证过。

**B. 本机开发（不依赖 Docker）**

```powershell
# ① 启动 PostgreSQL（绿色版实例，127.0.0.1:5432）
backend\start-db.bat

# ② 首次运行需建表
cd backend
.venv\Scripts\alembic.exe upgrade head

# ③ 启动后端（必须走 python -m app.main，不能用裸 uvicorn）
backend\start-api.bat          # http://127.0.0.1:8000/docs

# ④ 启动前端
frontend\start-web.bat         # http://localhost:5173
```

**C. 可选：接入真实模型**

复制 `.env.example` 为 `backend/.env`，配置：

```env
LLM_PROVIDER=deepseek          # mock | deepseek | openai | custom
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

不配置 Key 时自动使用 Mock 模板，完整流程仍可跑通。模型调用有 8 秒超时，超时 / 报错 / 返回不合规都会降级为模板结果。

### 3.2 一次完整使用（用户视角）

1. 打开首页 → 右上角登录或注册（Demo 只需用户名）。
2. 点 `Start learning` → 输入今天的目标，或点示例标签 → 点「分析」。
3. 页面给出 starter（5 分钟内可执行的第一步）和可选的后续步骤；starter 与步骤可手动修改。
4. 点「开始学习」→ 进入专注页，正计时从 0 往上走；没有倒计时、没有暂停。
5. 到 5:00：页面出现里程碑提示、背景变亮，但**不跳转、不停表**；此时服务端已记为完成。
6. 点「结束」：
   - ≥5 分钟：进入结算；
   - <5 分钟：本场完全丢弃，只提示还差多少秒，随后回首页。
7. 结算页按固定顺序走四步：① 写感想（选填）→ ② 投递 1 封信（选填）→ ③ 处理未处理信箱 → ④ 随机回顾一条过去的记录。
8. 中途离开不会丢进度：下次进入直接跳到断点步骤继续；四步走完出现「来自宇宙的音讯」收尾。

### 3.3 页面与入口

| 页面 / 入口 | 作用 |
|---|---|
| `/` 首页 | 首屏、Start learning 弹窗、连续天数、30 天星星墙；Mailbox / Learning log / Random reflection 三个历史入口 |
| `/focus` 专注页 | 只保留任务首步、正计时、结束入口；满 5 分钟后结束按钮由描边变为发光 |
| `/settle` 结算页 | 三段式摘要 + 四步结算（断点续做） |
| 首页 Mailbox 弹窗 | 未处理 / 历史收藏 / 发出记录（当前信箱没有独立路由页） |
| `/records` 记录页 | **当前为占位页**；单日记录查询目前通过首页「Learning log」弹窗完成 |
| `/login` `/register` | 用户名登录 / 注册；登录后首页右上角可切换账号 / 登出 |

### 3.4 推荐演示路径

1. 以小明的账号进入：首页已有连续 6 天，未处理信箱预置 2 封。
2. 输入「整理本周英语单词」，观察 starter 拆分；不配 Key（或断网后等 8 秒超时）再试，可看到模板降级但仍能完整走完。
3. 开始计时并等到 5 分钟：只出现里程碑提示，计时继续。
4. 结束后依次写感想、把信寄给小美、处理 2 封来信（收藏 1、放弃 1）。
5. 在第④步看到过去某一天的任务与感想。
6. 换到小刚（空账号）演示首次完成与空态文案；需要跨天 / 断签演示时，改后端时间偏移配置并重启服务。

> 时间偏移与时长阈值由后端配置控制（`DEMO_TIME_OFFSET_SECONDS`、`SESSION_MIN_SECONDS`、`SESSION_MAX_SECONDS`），只影响「当前时间」判定，不改已落库的历史时间戳。

---

## 4. 功能实现流程

### 4.1 功能实现顺序（不得插队）

| 序 | 功能 | 前置依赖 |
|---|---|---|
| 1 | F9 多账号与身份请求头 | 无 |
| 2 | F1 + F2 今日任务与模型拆分 | 1 |
| 3 | F3 专注计时与有效性 | 2 |
| 4 | F4 + F5 结算四步与感想 | 3 |
| 5 | F7 星星与连续天数 | 3、4 |
| 6 | F6 信箱与投递 | 4 |
| 7 | F10 随机回顾 | 6 |
| 8 | F8 记录查询 | 全部 |

排序理由：身份最先（所有数据按账号隔离）；F1–F4 是主干使用链；F7 依赖有效性判定稳定；F6 依赖 F4 产出投递机会；F8 是聚合视图，最后做。

### 4.2 分层与数据归属

- 依赖方向固定为 `routers → services → models`，由 `backend/tests/test_architecture.py` 机械检查，属棘轮：只能收紧。
- 时间唯一来源是 `app/clock.py` 的 `Clock`；前端取时间只能走 `src/hooks/useServerClock.ts`。
- HTTP 唯一入口是 `frontend/src/api/client.ts`；响应里的 `server_time` 被拦截器换算成偏移量存入 Zustand。
- 关键事实只有一个 owner：

| 事实 | 唯一来源 |
|---|---|
| 当前时间 / 归属日 | 后端 `Clock`（Asia/Shanghai） |
| 会话、结算断点、有效性 | PostgreSQL `sessions`（`settle_step` 条件更新） |
| 投递 / 收藏幂等 | `action_logs` 唯一约束 `(session_id, action_type)` |
| 未处理信箱 ≤3 | `users` 行锁 + `letters` 行锁 + 事务 |
| 任务拆分缓存 | `llm/` 模块级 LRU(128)，键为「任务文本\|日期」 |
| 当前用户 | 服务端 `auth_sessions` 解析 Bearer token，不信任客户端 user_id |

### 4.3 主流程代码链路

```
页面 → client.ts 拦截器 → /api router（schema 校验）→ service（规则 + 事务）
     → models → PostgreSQL → 响应 schema + server_time → store → 渲染
```

| 功能 | 后端落点 | 前端落点 |
|---|---|---|
| 今日任务 / 拆分 | `routers/task.py`、`services/task_service.py`、`llm/` | 首页 Start learning 弹窗、`TaskComposer`、`SplitEditor` |
| 专注计时 | `routers/session.py`、`services/session_service.py` | `/focus`、`FocusPage`、`FocusTimer` |
| 结算四步 | `routers/settle.py`、`services/settle_service.py`、`reflection_service.py` | `/settle`、`StepReflection` → `StepDeliver` → `StepMailbox` → `StepReview` |
| 星星 / 连续天数 | `routers/progress.py`、`services/progress_service.py` | 首页 `StreakBadge`、`StarWall` |
| 信箱 / 投递 | `routers/letter.py`、`services/letter_service.py` | `MailboxPanel`、`InboxList` / `HistoryList` / `OutboxList`、`LetterTicket` |
| 随机回顾 | `routers/review.py`、`services/review_service.py` | `StepReview`、首页 Random reflection |
| 单日记录 | `GET /api/sessions/by-date` | 首页 Learning log 弹窗 |

---

## 5. 已解决的异常问题与兜底实现（简要）

### 5.1 产品级兜底

| 场景 | 处理方式 | 落点 |
|---|---|---|
| 模型超时（>8s）/ 报错 / 返回空 / JSON 或类型不合规 / starter 超 60 字 | 降级为规则模板，`source="fallback"`，流程继续；二次校验后才采用 | `llm/openai_compat.py`、`task_service._normalize_split` |
| 同一标题连点「分析」 | 复用已存采用版，不再调模型、不覆盖学生编辑 | `task_service.analyze` |
| 分析后改了标题 | 保留旧拆分，前端提示「标题已修改，可重新分析」，不自动清空、不自动重调 | `split_stale` + `SplitEditor` |
| 重复点「开始」 | 复用已有进行中会话，不新建并行场次 | `session_service.create_session` |
| 刷新 / 断网 / 锁屏 | 以服务端 `started_at` + 校准后的当前时间续算；专注页每 15 秒轮询校正，单次失败不打断计时 | `FocusPage`、`useServerClock` |
| 到 5 分钟但没点结束 | 服务端懒计算把状态置为已完成并记连续天数，计时继续 | `get_current_session` |
| 单场到 180 分钟 | 懒计算自动结束，`ended_at = started_at + 180 分钟`；前端到点主动补一次请求，展示截断在 180:00 | `session_service`、`FocusPage` |
| 未满 5 分钟点结束 | 本场**完全丢弃**：不写时长、不算累计、不加亮度、不给投递机会、不计连续天数，只提示差额后回首页 | `end_session`（`discarded`） |
| 重复结束 / 重复结算 | 已结束会话不再改写；`settle_step` 带条件更新只进不退，天然幂等 | `end_session`、`settle_service.advance` |
| 结算四步中途离开 | 断点存 `settle_step`（0–4），下次直接跳到对应步骤；第④步完成置 `settled` | `settle_step` + `SettlePage` |
| 感想重复提交 / 已跳过 | 返回 409，断点已在下一步，刷新继续；感想只读，不提供编辑接口 | `reflection_service` |
| 并发投递给同一人 | 先锁 `users` 行再锁 `letters` 行，未处理达 3 封拒收；`action_logs` 唯一约束防双击重复投递 | `letter_service.send` |
| 收件人不存在 | 返回 `rejected_unknown`，提示「找不到这位同学」，**不消耗投递机会** | `letter_service.send` |
| 信箱已满被拒 | 返回 `rejected_full`，只在发送方「发出记录」标「未送达」，**机会不消耗、可改寄** | `letter_service.send` |
| 连点收藏 / 放弃 | 幂等返回；已过期返回 409「这封信已经过了一天」；已放弃的信不能收藏复活 | `letter_service.favorite/dismiss` |
| 未收藏的信 | 次日 00:00 懒失效：查询条件里过滤，不后台清扫 | `letter_service.get_inbox` |
| 历史信箱超过 100 封 | 读取时懒清理最旧信件至 100 封，不打断用户 | `letter_service.get_history` |
| 客户端时钟不准 | 所有响应带 `server_time`，前端存偏移再用 `useServerClock`；业务判定一律用服务端时间 | `client.ts`、`clock.py` |
| 跨零点学习 | 归属日 = `started_at` 的 Asia/Shanghai 日期；数据库查询用 `timezone('Asia/Shanghai', started_at)`，不裸转日期 | `session_service`、`progress_service` |
| 切换账号时有在途请求 | 在途响应按账号校验后丢弃，避免上一账号的会话覆盖当前视图 | `FocusPage` / `HomePage` |
| 结算摘要字段缺失或格式异常 | 日期标签退回「当日」，不让整页崩掉 | `SettleSummary.dayLabel` |
| WebGL2 不可用 / 用户开启减少动态效果 | 专注页背景退化为静态渐变；粒子 / 流星整层不挂载；计时与结束流程不受影响 | `Lightfall`、`FocusPage` |
| 首次使用无历史可回顾 | 只显示「等待宇宙的讯息」，不报错、不追加引导 | `StepReview` |

### 5.2 已修复的实际问题（工程层）

| 问题 | 修复 |
|---|---|
| 视觉 token 写成 `hsl(var(--x))` 而变量值是 `oklch(...)`，构建产物变成无效的 `hsl(oklch(...))`，深色主题实际不生效 | 颜色映射改为 `var(--x)`，并补通道变量 `--x-ch` 支持 `/70` 等透明度修饰符 |
| 登录 / 注册的流星层用 `fixed + z-index:-1`，被不透明页面底色遮住 | 改为 `absolute + z-index:0`，表单保持 `z-10` |
| 种子重置会改变账号 id，导致前端 localStorage 里的选中账号失效 | 3 个演示账号按名字复用原 id，缺失才新建 |
| Windows 下 psycopg3 异步与 ProactorEventLoop 冲突，裸 `uvicorn` 启动即崩 | 固定 `python -m app.main`；`db.py` 顶部保留 `WindowsSelectorEventLoopPolicy`，且在事件循环创建前生效 |
| PowerShell 用 `curl.exe` 传 JSON 导致后端 422 且难排查 | 手工冒烟统一改用 `Invoke-RestMethod` + `ConvertTo-Json` |
| 测试误连开发库会清空演示数据 | 测试库固定 `novastart_test`，连接串只出现在测试配置一处，每用例 `drop_all/create_all` |

---

> 相关主记录：[brainstorming.md](brainstorming.md)（需求）· [docs/architecture.md](docs/architecture.md)（边界）· [docs/dev-order.md](docs/dev-order.md)（顺序）· [docs/dev-pitfalls.md](docs/dev-pitfalls.md)（操作陷阱）· [TECH_STACK.md](TECH_STACK.md)（选型）
