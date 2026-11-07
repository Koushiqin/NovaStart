# NovaStart 功能开发顺序契约

**性质：强制。** 本文件规定「先做什么、再做什么」以及层与层之间的衔接方式。与本文冲突的实现顺序以本文为准；确需调整顺序时，先在 `docs/specs/` 对应 Spec 中写明理由并经人工确认。

本文只定顺序与衔接，不复述需求与边界：功能规则看 [brainstorming.md](../brainstorming.md)，模块职责与数据归属看 [architecture.md](architecture.md)。

---

## 1. 总原则

1. **契约先行** — 任何功能先定字段与接口（schemas / ORM 字段），再写实现。字段没定就写 router 或页面，返工必然发生。
2. **垂直切片** — 一次只推进一条能端到端跑通的最小链路。禁止"先把所有表建完""先做出完整前端再套接口"。
3. **单一真相源** — 判定类事实（时间、有效性、连续天数、信箱容量）只在服务端产生一次，前端只做显示。
4. **顺序按真实使用链** — 写 → 计时 → 结算 → 可视化 → 社交 → 回看，每个功能只依赖已完成的更早功能。

---

## 2. 六步流水线（每个功能都必须按此顺序走）

| 步 | 动作 | 落点 | 完成判据 |
|---|---|---|---|
| ① 定义契约 | 写请求/响应 schema 与 ORM 字段：类型、可空、约束、默认值 | `backend/app/schemas/`、`backend/app/models/` | 字段能覆盖该功能在 brainstorming 中的**全部规则**（含边界），无遗漏 |
| ② 迁移建表 | `alembic revision --autogenerate` 后人工核对，补约束/时区 | `backend/alembic/versions/` | `alembic downgrade base` → `upgrade head` 双向通过；`psql \d` 表结构与模型一致 |
| ③ 业务逻辑 | 在 service 内实现规则与事务边界，同时写 pytest | `backend/app/services/`、`backend/tests/` | 不变量（幂等、行锁、懒计算、归属日、容量上限）有用例钉住且通过 |
| ④ 挂接口 | router 只做解析与转发，main.py 注册；`/docs` 手工冒烟 | `backend/app/routers/`、`main.py` | 返回结构与 ① 的 schema 一致，响应带 `server_time` |
| ⑤ 前端接入 | 页面只经 `api/client.ts` + `store` + `hooks` 获取数据 | `frontend/src/api`、`store`、`hooks`、`pages`、`features` | 页面无第二 HTTP 入口、无 `new Date()` 直接取时间 |
| ⑥ 端到端联调 | db + api + web 三服务同启，按 brainstorming 该功能的「演示验收」原话走一遍 | 本地三服务 | 演示验收步骤全部可复现，刷新/断网行为符合约定 |

**跳步禁令**

- ③ 之前不得写 router；④ 通过前不得写页面数据逻辑；⑥ 通过前不得把功能标记为完成。
- 前端不得先于 ① 定义自己的字段结构——它只能跟随后端 schema。

---

## 3. 层间衔接规则

### 3.1 前端 ↔ 后端

- **唯一通道** `frontend/src/api/client.ts`（`baseURL=/api`）。开发期由 vite proxy 转到 `127.0.0.1:8000`，交付期由 nginx 同源反代，代码里不出现绝对地址。
- **时间** 所有响应带 `server_time`，拦截器算偏移存入 store；前端取时间只能用 `hooks/useServerClock.ts`。
- **字段权威** 后端 `schemas/` 是唯一真相源；前端 TS 类型 / zod schema 是对它的"跟随"，不允许先于后端定义字段。
- **字段变更顺序** 先改后端 schema + 模型 → 生成迁移 → 再改前端，三者必须在同一个 Spec 与同一次改动内完成，不允许"后端先上线、前端下次再跟"。
- **身份** 当前用户 id 由请求头统一注入（单点收敛），不散落在各组件。
- **错误契约** 后端返回稳定的 `code` + 人话 `message`；前端只负责展示，不自行推断业务规则。
- **一次请求的标准走向**：
  `页面/组件 → client 拦截器 → /api router（schema 校验）→ service（规则 + 事务）→ models → PostgreSQL → 响应 schema + server_time → store → 渲染`

### 3.2 后端 ↔ 数据库

- router 不碰 SQL；service 通过 `Depends(get_session)` 拿到 `AsyncSession`，事务边界在 service 内闭合。
- 建表/改表**只能**走 Alembic（autogenerate + 人工核对）；禁止手写 DDL、禁止运行时 `create_all`、禁止直接改已应用的 revision。
- 时间判定只用 `app/clock.py` 的 `Clock`；会话归属日按 `started_at` 计算，不用"当前日"。
- 每个不变量只允许一条写入路径：`action_log` 唯一约束、`settle_step` 条件更新、`with_for_update` 行锁，均在 service 内实现，不在 router 或前端补第二套。

### 3.3 交付链路

Docker Compose 不参与每个功能循环。仅在整体交付验收前跑一次 `docker compose up -d --build`，避免把开发节奏绑在容器构建上。

---

## 4. 功能实现顺序

按依赖关系排序，**不得插队**；上游未通过第 ⑥ 步，不开始下游。

| 序 | 功能 | 前置依赖 | 完成标志 |
|---|---|---|---|
| 1 | F9 多账号与请求头 `userId` | 无 | 切换账号后首页/记录/信箱数据整体切换，请求头生效 |
| 2 | F1 + F2 今日任务与模型拆分 | 1 | 输入一句话得到 starter + steps；断网/超时仍降级可走 |
| 3 | F3 专注计时与有效性 | 2 | 满 5 分钟服务端标记、刷新续算、<5 分钟完全丢弃、180 分钟自动结束 |
| 4 | F4 + F5 结算四步与感想 | 3 | `settle_step` 断点可续、复述用当前采用版、感想只读 |
| 5 | F7 星星与连续天数 | 3、4 | 亮度 5/15/25、一天 +1、断签归零并保留历史最长 |
| 6 | F6 信箱与投递 | 4 | 未处理 ≤3 行锁、拒收不消耗机会、100 封懒清理、24:00 懒失效 |
| 7 | F10 随机回顾 | 6 | 排除本场与当天，无历史时只一句空态文案 |
| 8 | F8 记录查询 | 全部 | 全部 / 区间 / 单日三查法，多场标注"第 X 场" |

**排序理由**

- F9 最先：所有数据都以账号为隔离维度，晚做等于所有接口返工。
- F1–F4 是主干使用链，必须连续完成，中间插入可视化会拿到不稳定的状态语义。
- F7 依赖 F3 的有效性判定，判定未稳定前做亮度分级必然重写。
- F6 依赖 F4 产出投递机会；F10 依赖 F6 的结算末步位置。
- F8 最后：它是聚合视图，任何早做都会随前面功能变动被反复重写。

---

## 5. 什么时候必须回到第 ① 步

| 情况 | 处理 |
|---|---|
| 验收条件新增/变化，或需要新字段 | 回到 ①，重走 ①→④，再改前端 |
| 已有接口返回结构要改 | 回到 ①；改字段属于破坏性变更，按 AGENTS.md 先人工确认 |
| 迁移已应用后发现模型漂移 | 新建 revision 修正，不改历史 revision |
| 只改文案 / 样式 / 动画 | 可在 ⑤ 内直接完成，不必重走流水线，但仍需 `npm run build` 通过 |

---

## 6. 每个功能的完成门（Definition of Done）

全部勾选才可宣布该功能完成：

- [ ] 六步流水线全部走完，第 ⑥ 步对照 brainstorming 对应「演示验收」通过
- [ ] 新增/变更行为有 pytest 用例，且**已运行通过**（区分"已编写"与"已运行"）
- [ ] 架构棘轮通过：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py`
- [ ] 有迁移时：`alembic downgrade base` → `alembic upgrade head` 通过
- [ ] 有前端改动时：`npm run lint`、`npm run build` 通过
- [ ] `docs/specs/` 下该功能 Spec 第 8 节已回填执行结果与遗留问题

---

## 7. 明确禁止

- 先把所有表建完再逐个补业务（产生大量空字段与重复迁移）。
- 先写完整前端 UI 再"套"接口（契约会跟着 UI 走，方向反了）。
- 让前端自造业务判定（计时有效性、信件失效、连续天数只能在服务端）。
- 绕过 `client.ts` 直接 `fetch`，或直接 `new Date()` 取时间。
- 用手写 SQL / 运行时建表替代 Alembic 迁移。
- 在第 ⑥ 步通过前对外宣称功能"已完成"。
