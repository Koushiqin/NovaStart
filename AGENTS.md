# AGENTS.md — NovaStart 开发入口

NovaStart：「每天主动学习五分钟」Demo 应用。React SPA + FastAPI + PostgreSQL 16，Docker Compose 交付。

## 开工必读（按顺序）

1. [docs/dev-order.md](docs/dev-order.md) — **功能开发顺序契约（强制）**：六步垂直切片与功能先后顺序
2. [docs/architecture.md](docs/architecture.md) — 模块职责与依赖边界，改代码前必读
3. [brainstorming.md](brainstorming.md) — 功能需求 F1–F10 的唯一来源
4. [docs/dev-pitfalls.md](docs/dev-pitfalls.md) — **操作性陷阱与红线**：测试库安全、工具链、运行时易错点，动手前必读
5. [TECH_STACK.md](TECH_STACK.md) — 技术选型、环境搭建、非功能需求覆盖
6. [techstack_plan.md](techstack_plan.md) — Task 1–12 实施计划主记录（已完成）

同一事实只维护一份主记录：需求看 brainstorming.md，边界看 architecture.md，先后顺序看 dev-order.md，操作陷阱看 dev-pitfalls.md，不要在新文档里复述。

## 目录速览

- `backend/app/` — FastAPI：`routers/ → services/ → models/`，`schemas/` 为 API 契约；`clock.py` 是服务端时间唯一真相源；`llm/` 可插拔任务拆分器
- `backend/alembic/` — 数据库迁移（改模型必须配迁移）
- `backend/tests/` — pytest，独立库 `novastart_test`
- `frontend/src/` — `api/` `store/` `hooks/` `pages/` `features/` `components/ui/` `lib/`
- `docs/` — architecture.md、spec-template.md、`specs/`（每次改动一份 Spec，从模板复制）
- `.agents/skills/` — 项目工作流 Skill

## 按任务找 Skill

| 任务 | Skill |
|---|---|
| 实现需求 / 修改代码 | `.agents/skills/implement-change/SKILL.md` |
| 完成前对照 Spec Review | `.agents/skills/review/SKILL.md` |
| 运行测试与验证 | `.agents/skills/run-tests/SKILL.md` |

## Skill 组合速查（按开发领域）

`.agents/skills/` 共 23 个项目 Skill。**入口永远是上面三个工作流 Skill + [docs/dev-order.md](docs/dev-order.md)**；下面按领域叠加使用——领域 Skill 只提供「怎么做」，不得改变六步切片顺序和架构硬边界。与 AGENTS.md 冲突时一律以 AGENTS.md 为准。

### 后端与数据

| 环节 | Skill | 本项目用法 / 约束 |
|---|---|---|
| 接口与契约 | `python-fastapi` | `routers/` `schemas/` 写法：Pydantic v2、依赖注入、状态码；时间字段一律走 `Clock` |
| 服务运行检查 | `production-fastapi` | 只采纳 lifespan、健康检查、结构化日志、异常处理；**不改启动方式**（仍 `python -m app.main`），不引入 Gunicorn/新中间件 |
| 模型设计 | `database-designer` | 改表前先定关系、约束、索引；结论写进 Spec 第 4 节 |
| ORM 实现 | `python-sqlalchemy` | SQLAlchemy 2.0 风格（`select()` / `Mapped` / `mapped_column`）；事务边界在 service 层 |
| PostgreSQL 与迁移 | `production-postgres` | 迁移安全、索引、查询优化；Demo 规模**不引入 PgBouncer 等新依赖** |

### 前端

| 环节 | Skill | 本项目用法 / 约束 |
|---|---|---|
| 视觉方向 | `frontend-design` | 首次做 Focus / Settle / Records 页面前先定视觉方向；基于 Tailwind 3 + shadcn 2.4 的 CSS 变量体系 |
| 组件 API | `composition-patterns`（name: vercel-composition-patterns） | 用复合组件 / children 组合替代布尔 props；**本项目是 React 18，跳过其「React 19 APIs」章节**（`ref` as prop、`use()` 不适用） |
| 动效 | 无 `ui-animation` Skill | 统一用已安装的 framer-motion ^11，只在必要处加过渡，不新增动画库 |
| shadcn 组件 | 无 `shadcn-ui` Skill | 安装必须绕过 `npx shadcn`，见 TECH_STACK.md 与项目记忆 |

### 测试

| 环节 | Skill | 本项目用法 / 约束 |
|---|---|---|
| Python 行为测试 | `python-testing` | 测试从验收条件推导；HTTP 组合层走 API 测试、repository 层用真实库；阶段顺序 test → implement → refactor |
| 运行与前置条件 | `run-tests` | 沙箱、PostgreSQL、独立测试库等前置条件 |
| 浏览器流程 | `webapp-testing` | 用 Playwright 验证前端页面与交互流程 |
| 安全差异审查 | `differential-review` | 涉及鉴权、输入校验、敏感数据的改动必做 |

### 架构

| 环节 | Skill | 本项目用法 / 约束 |
|---|---|---|
| 模块与依赖边界 | `python-architecture` | 即 architecture-patterns 的 Python 版；本项目分层已定（`routers → services → models`），**不引入 DDD 分层 / 聚合根** |
| 取舍记录 | 无 `architecture-decision-records` Skill | 取舍写进 Spec 末尾五问，并同步更新 [docs/architecture.md](docs/architecture.md)；不新建 ADR 目录 |
| React 组件 API | `composition-patterns` | 同前端章节 |

### 计划与交付

| 环节 | Skill | 本项目用法 / 约束 |
|---|---|---|
| 需求澄清 | `brainstorming` / `grilling` | F1–F10 已在 [brainstorming.md](brainstorming.md)；新需求先澄清再写 Spec |
| 计划 | `writing-plans` / `executing-plans` | 多步任务先出计划再编码，计划服从 dev-order 顺序 |
| 重构 | `refactor` | 小步、不改行为；先有测试保护 |
| 代码审查 | `review`（项目）+ `code-review-excellence` / `requesting-code-review`（通用） | 先按 Spec 对照，再做通用审查；反馈要具体、可执行、对事不对人 |
| 交付 | `verification-before-completion` | 没真跑过命令，不得说「完成 / 已通过」 |

### 引用红线

1. 不得调用本项目未内置的 Skill（`shadcn-ui`、`vercel-react-best-practices`、`web-design-guidelines`、`ui-animation`、`architecture-patterns`、`architecture-decision-records`）；需要时用上表替代项。
2. 不得因领域 Skill 建议新增依赖、改启动方式或改检查语义——属"必须人工确认"事项。
3. 测试库固定 `novastart_test`，不得按 `python-testing` 的通用建议改用 SQLite（JSONB / timestamptz 不兼容）。
4. 不得以任何 Skill 建议放宽 `tests/test_architecture.py` 棘轮、跳过测试或扩大白名单。
5. React 18 项目，frontend 建议一律以现有 `src/` 代码和已装依赖为准。

## 架构与数据归属硬边界

- **所有功能实现必须按 [docs/dev-order.md](docs/dev-order.md) 的六步垂直切片顺序进行**：契约 → 迁移 → service → router → 前端接入 → 端到端联调；不得跳步，不得让前端先定义字段。
- **功能实现顺序不得插队**：F9 → F1+F2 → F3 → F4+F5 → F7 → F6 → F10 → F8，上游未通过第 ⑥ 步不开始下游（顺序调整须在 Spec 中说明理由并人工确认）。
- 依赖方向只允许 `routers → services → models`，禁止反向，禁止 router 互相 import（由 `tests/test_architecture.py` 机械检查）。
- 后端取当前时间只能用 `app/clock.py` 的 `Clock`，禁止 `datetime.now()` 直接出现在 routers/services（同上机械检查）。
- 前端取当前时间只能用 `src/hooks/useServerClock.ts`；HTTP 只能走 `src/api/client.ts`。
- session / 结算 / 信箱状态的唯一真相源是 PostgreSQL，前端只是显示器；不为同一事实新增平行状态或第二写入路径。
- 改 ORM 模型必须同时生成 Alembic 迁移并在 Spec 中说明兼容性。
- 扩展功能优先改现有模块；新增文件 / 抽象需在 Spec 里写明理由。

## 何时必须人工确认

- 验收条件不清楚 → 先澄清再实现。
- 破坏性变更（删表、改公开 API 契约、改启动方式）、权限、计费 → 说明影响并确认后再动手。
- 修改 CI、新增依赖、改变现有检查语义 → 先说明必要性。
- 测试失败原因不明 → 报告问题，不得放宽断言、跳过测试或扩大白名单。

## 协作规则

- 已确认范围内持续执行，不反复请求批准。
- 不提交真实密钥（`.env` 不入库），不覆盖用户已有改动。
- `TECH_STACK.md` / `techstack_plan.md` 按用户意愿保持 git 未跟踪，不要主动 `git add`。

## 本机环境关键约束（AI 执行命令时必守）

1. 沙箱网络隔离：凡连本机 PostgreSQL 的命令（psql / alembic / uvicorn / API 测试）必须 `dangerouslyDisableSandbox: true`。
2. PostgreSQL 启动必须用 WMI（直接 `pg_ctl start` 会被沙箱回收）：
   `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = "D:\Javatools\pgsql\bin\pg_ctl.exe start -D D:\Javatools\pg-data" }`
3. 后端启动只能用 `python -m app.main`（`backend/start-api.bat` 已是此方式），禁止裸 `uvicorn app.main:app`（psycopg3 异步 + Windows ProactorEventLoop 冲突）。
4. 起 uvicorn 前先确认旧实例已停（WinError 10013 端口占用）。
5. shadcn/ui 组件安装不能走 `npx shadcn`，见 TECH_STACK.md 与项目记忆中的绕过方法。

## 完成验证命令（按改动范围选跑）

```powershell
# 后端架构棘轮（无需 DB，随时可跑）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py

# 后端全部测试（需 DB 运行 + 沙箱外执行，见 run-tests Skill）
cd backend; .venv\Scripts\python.exe -m pytest

# 前端
cd frontend; npm run lint; npm run build
```

每次功能开发结束：按 Spec 模板回填「执行结果、未验证项和遗留问题」，区分「测试已编写」和「测试已运行通过」。

## Skills 组合参考（按开发领域）

以下 Skill 均已内置于 `.agents/skills/`，按开发领域组合使用；未列出的外部 Skill 不在本项目使用。

### 后端与数据

- `python-fastapi` 负责接口开发（路由、校验、依赖注入、响应模型）；`production-fastapi` 补充服务运行检查（lifespan、健康检查、结构化日志、异常处理、安全加固）。
- `database-designer` 处理模型设计（表结构、关系、索引、规范化）；`python-sqlalchemy` 处理 ORM 实现（SQLAlchemy 2.0 风格、会话与事务边界）；`production-postgres` 处理 PostgreSQL 运行与迁移（迁移安全、索引策略、查询优化）。

### 前端

- `frontend-design` 提供视觉设计指导（配色、排版、布局的差异化决策）。

### 测试

- `python-testing` 处理 Python 行为测试（pytest、测试分层、fixture）；`webapp-testing` 验证浏览器流程（Playwright 脚本、截图、日志）；涉及鉴权、输入和敏感数据的改动可补 `differential-review`（安全导向的差异审查）。

### 架构

- `python-architecture` 分析模块与依赖边界（functional core / imperative shell、端口与适配器、事务归属）；React 组件 API 使用 `composition-patterns`（vercel-composition-patterns：复合组件、状态提升、children 组合，注意本项目为 React 18，跳过其 React 19 API 章节）。

### 重构与交付

- `refactor` 小步整理代码（保持行为不变、每步有测试保护）→ `code-review-excellence` 评审改动（具体可执行、对事不对人、区分 critical 与 nice-to-have，格式问题交给 linter）→ `verification-before-completion` 根据真实验证输出交付（先跑命令拿到证据，再声明完成）。
