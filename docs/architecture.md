# NovaStart 架构约定

只记录与本项目有关的规则。改代码前必读；与 [TECH_STACK.md](../TECH_STACK.md)（选型与环境）互补，不重复。

## 分层与依赖方向

### backend/app/

| 层 | 职责 | 不允许做 |
|---|---|---|
| `routers/` | HTTP 解析、调 service、返回 schema | 写业务规则、直接操作 ORM 事务细节 |
| `services/` | 业务规则与事务边界（幂等、行锁、懒计算） | import routers、感知 HTTP |
| `models/` | ORM 数据结构权威定义 | import services / routers |
| `schemas/` | Pydantic 请求/响应模型（API 契约） | 含业务逻辑 |
| `llm/` | 任务拆分客户端 | 绕过统一降级与缓存策略 |
| `clock.py` | 服务端时间唯一真相源（Asia/Shanghai） | — |
| `db.py` | 引擎 + Session | 删除顶部 Windows Selector 事件循环策略（psycopg3 依赖） |

**依赖方向：`routers → services → models`**（schemas 可被各层引用）。禁止反向、禁止 router 互引。由 `backend/tests/test_architecture.py` 机械检查，属棘轮：只能收紧，不得放宽。

### frontend/src/

- `api/client.ts` — 唯一 HTTP 入口；axios 响应拦截器读取 `server_time` 并存偏移量到 store。
- `store/app.ts` — zustand：`userId`、`serverTimeOffsetMs`、`settleStep`。
- `hooks/useServerClock.ts` — 前端唯一取「当前时间」入口（`Date.now() + offset`）。
- `pages/` 路由页、`features/` 业务组件、`components/ui/` shadcn 源码组件、`lib/` 工具。
- vite dev proxy：`/api` 与 `/dev` → `127.0.0.1:8000`。

## 关键数据的权威来源

| 事实 | 唯一来源 | 说明 |
|---|---|---|
| 当前时间 | 后端 `Clock` | 接口顺手返回 `server_time`，前端存偏移校正；客户端时钟不可信 |
| session / 结算状态 | PostgreSQL `sessions` 表 | `settle_step` 条件更新只进不退，天然幂等 |
| 动作幂等记录 | `action_log` 唯一约束 `(session_id, action_type)` | 投递/收藏只执行一次 |
| 未处理信箱 ≤3 | 行锁 `with_for_update` + 事务 | 在 letter_service 内，不开第二路径 |
| 任务拆分缓存 | `llm/` 模块级 LRU(128)，键「任务文本\|日期」 | 不落库；8s 超时/异常降级 Mock（`source="fallback"`） |
| 当前用户 | 前端 zustand `userId` | Demo 无鉴权，请求头传递 |

同一事实不得新增平行写入路径或重复状态；新功能先查这张表。

## 扩展功能优先改哪里

- 新 API → 同领域现有 router/service 文件内加；确属新领域才建新文件（Spec 中写理由）。
- 新表 / 字段 → `models/` + Alembic 迁移（`alembic revision --autogenerate` 后人工核对）。
- 新页面 → `pages/` + `App.tsx` 路由；UI 优先复用 `components/ui/`。
- 前端取时间、发请求一律走现有 hook/client，不新造入口。
- LLM 拆分行为（prompt / 降级策略）变化走普通 Software Spec。**本项目无独立 Agent Spec**，不引入第二套 Prompt 来源或运行时加载机制。

## 已接受的历史问题（保留边界）

| 问题 | 保留原因 | 删除 / 收敛条件 |
|---|---|---|
| `/dev/reset-seed` 固定挂载 | Demo 无生产环境，演示重置用 | 出现生产部署需求时加开关 |
| Docker 交付链路未本机端到端验证 | 本机 Docker 不可用（WSL/虚拟机平台未启用） | Docker 可用后跑 `docker compose up -d --build` 验证 |
| `TECH_STACK.md` / `techstack_plan.md` 未跟踪 | 用户明确要求 | 用户改主意为止 |

不因某模块「不够完整」而擅自扩大范围；历史兼容改动需说明保留原因。
