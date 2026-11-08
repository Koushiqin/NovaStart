# NovaStart · 技术栈确认文档

> 创建日期：2026-11-06
> 版本：v1.0
> 基于：brainstorming.md v0.5（全部功能需求）

---

## 一、选型结论

**React + FastAPI + PostgreSQL + Docker Compose** 完全覆盖 brainstorming.md 中的全部功能（F1–F10 + 跨天规则 + 异常兜底）。

---

## 二、完整技术栈

### 2.1 前端

| 组件 | 版本 | 作用 | 备注 |
|---|---|---|---|
| React | 18 | UI 框架 | |
| TypeScript | 5.x | 类型安全 | |
| Vite | 5.x | 构建工具（dev 启动 + prod 打包） | 比 webpack 快 10× |
| Tailwind CSS | 3.x | 原子化样式（唯一样式方案，不写原生 CSS） | shadcn/ui 底层依赖 |
| shadcn/ui | 最新 | 组件库（基于 Radix + Tailwind） | 装源码而非 npm 包，可直接改 Tailwind 类；适合做星星墙、连续天数等主视觉 |
| lucide-react | 最新 | 图标库 | shadcn/ui 默认内置，零配置 |
| framer-motion | 11.x | 动画库 | `motion.div` + `animate` 属性做星星发光、数字弹跳、卡片进场、结算步骤过渡 |
| react-hook-form | 7.x | 表单状态管理 | 比受控组件快 5–10x，配合 zod 校验用 |
| zod | 3.x | 表单 + 接口数据校验 | `zodResolver` 接到 react-hook-form，类型安全 |
| React Router | 6.x | 页面路由 | 首页 / 专注页 / 结算四步 / 记录页 |
| Zustand | 4.x | 全局状态管理 | 账号切换、settleStep 断点、计时器状态；比 Redux 轻量 |
| Axios | 1.x | HTTP 客户端 | 封装统一拦截器（错误处理、token、时间差校正） |

### 2.2 后端

| 组件 | 版本 | 作用 | 备注 |
|---|---|---|---|
| Python | 3.11 | 运行时 | |
| FastAPI | 0.115+ | API 框架 | 自带 OpenAPI 文档、Pydantic 校验、异步支持 |
| SQLAlchemy | 2.0 | ORM | 异步模式 + 类型化查询 |
| Alembic | 1.13+ | 数据库迁移 | `alembic upgrade head` 一键建表 |
| Pydantic | v2 | 数据校验 | FastAPI 内置，定义请求/响应模型 |
| psycopg | 3.x | PostgreSQL 驱动 | SQLAlchemy asyncpg 后端 |
| python-dotenv | 最新 | 环境变量加载 | 读 .env 配置 |
| LLM 客户端（可插拔） | — | 模型拆分调用 | 抽象层：默认 Mock 模板；配 .env 里的 `LLM_API_KEY` + `LLM_BASE_URL` 即走真实模型（兼容 DeepSeek / OpenAI / 任何 OpenAI 协议端点） |

### 2.3 数据库

| 组件 | 版本 | 作用 | 备注 |
|---|---|---|---|
| PostgreSQL | 16 | 主数据库 | 事务行锁（保证未处理信箱 ≤3）、唯一约束、JSONB、`ORDER BY RANDOM()`（随机回顾） |

### 2.4 部署

| 组件 | 作用 | 备注 |
|---|---|---|
| Docker Compose | 编排全部服务 | 3 容器：postgres + backend + frontend(nginx) |
| nginx | 托管 React 构建产物 | 静态文件 + 反向代理到 FastAPI |
| start.bat / start.sh | 一键启动脚本 | 别人拿到项目后双击即可运行，无需装 Python / Node / PostgreSQL |

---

## 三、为什么是这些（对应到需求）

| 需求 | 技术实现 |
|---|---|
| F1–F8 全部 CRUD + 查询 | React + FastAPI + SQLAlchemy + PostgreSQL 标准能力 |
| F2 模型拆分 + 8s 超时降级 + 结果缓存 | FastAPI 调 HTTP 超时控制 + LRU 内存缓存（按「任务文本+日期」key）；降级为规则模板返回 |
| F3 正计时 + 懒计算完成标记 | React 前端显示计时（只显示，不存状态）；FastAPI `Clock` 模块统一返回服务端时间；任何请求进来时用 `startedAt + 5min / 180min` 补算 |
| F3 180 分钟自动结束 | 懒计算：每次进入专注页/首页都检查是否超 180 分钟，是则自动结算 |
| F4 结算四步 + settleStep 断点续做 | PostgreSQL session 表存 `settleStep` 字段（0–4）；React 根据此值直接跳到对应步骤页面 |
| F4 同一 session 只结算一次 | PostgreSQL session 表 `status` 字段做幂等，UPDATE 带 WHERE 条件 |
| F6 未处理信箱 ≤3 封 + 并发安全 | PostgreSQL 行锁（`SELECT ... FOR UPDATE`）或唯一约束 + 事务 |
| F6 历史信箱满 100 自动清理 | 懒清理：查询历史信箱时如果条数 >100，删最旧的至 100 条 |
| F6 未收藏信件当日 24:00 失效 | **懒失效**，不跑定时任务：查询时判断 `expired_at < Clock.now()` 即不展示 |
| F7 星星亮度（Lv1/Lv2/Lv3） | PostgreSQL 聚合当天有效 session 总时长，前端根据阈值映射亮度等级 |
| F7 连续天数 +1 判定 | PostgreSQL 查询当前自然日是否有有效 session，与前一天的 streak 字段对比 |
| F9 多账号切换 | Zustand store 存当前 userId，FastAPI 所有接口从请求头读 userId |
| F9 演示时间旅行 + 时间加速 | FastAPI `Clock` 模块返回伪时间（默认正常，演示模式下返回加速/偏移后的时间）；改这一处文件即可 |
| F10 随机回顾 + 排除本场/当天 | PostgreSQL `ORDER BY RANDOM() LIMIT 1` + WHERE 排除条件 |
| 跨零点归属开始日 | PostgreSQL `startedAt timestamptz` 字段，Clock 模块按 Asia/Shanghai 计算自然日 |
| 种子数据一键重置 | FastAPI `/dev/reset-seed` 接口 + Alembic seed.sql |
| 前端服务端时间同步 | FastAPI 所有时间相关接口顺手返回 `server_time`，前端存差值校正本地时钟 |

---

## 四、项目目录结构（规划）

```
NovaStart/
├── docker-compose.yml          # 一键启动全部容器
├── .env.example                # 环境变量模板（LLM Key、DB 密码等）
├── start.bat                   # Windows 一键启动
├── start.sh                    # Mac/Linux 一键启动
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                # 数据库迁移
│   ├── alembic.ini
│   └── app/
│       ├── main.py             # FastAPI 入口
│       ├── config.py           # 环境变量 + Clock 模块
│       ├── db.py               # SQLAlchemy 引擎 + session
│       ├── models/             # ORM 模型（User, Session, DayTask, Letter...）
│       ├── schemas/            # Pydantic 请求/响应模型
│       ├── services/           # 业务逻辑（session 结算、streak 计算、信箱并发锁）
│       ├── routers/            # API 路由（task, session, settle, letter, record...）
│       ├── llm/                # 模型拆分客户端（Mock 默认 / 可插拔真实模型）
│       └── seed.py             # 演示种子数据
│
└── frontend/
    ├── Dockerfile              # 构建 → nginx 托管静态产物
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── components.json         # shadcn/ui 配置（指定源码安装路径）
    ├── package.json
    └── src/
        ├── main.tsx
        ├── App.tsx             # React Router 路由配置
        ├── api/                # Axios 封装（统一拦截器、时间差校正）
        ├── store/              # Zustand store（账号、settleStep、计时器）
        ├── pages/              # 页面（Home, Focus, SettleStep1-4, Records）
        ├── components/
        │   ├── ui/             # shadcn/ui 源码（Button, Input, Card, Dialog...，非 npm 包）
        │   ├── motion/         # framer-motion 动画变体（星星发光、数字弹跳、卡片进场）
        │   └── features/       # 业务组件（StarWall, StreakBadge, LetterCard, CountUp...）
        ├── lib/
        │   ├── utils.ts        # cn() 工具、计时格式化、日期转换
        │   ├── schemas.ts      # zod 校验 schema（任务输入、信件内容、表单数据）
        │   └── motion.ts       # framer-motion 通用动画 variants 常量
        └── hooks/              # 自定义 hooks（useTimer, useSettleStep, useServerClock）
```

---

## 五、开发阶段约定

### 本地开发（完全不依赖 Docker）

> 开发机不使用 Docker Desktop。Docker 只用于最终交付打包。

| 项 | 方案 | 说明 |
|---|---|---|
| Python | **3.12**（单独安装，不覆盖系统已有 3.14） | 与 Docker 镜像版本接近；3.14 上 psycopg / pydantic-core 可能没有预编译包 |
| 虚拟环境 | `backend/.venv`（3.12 创建） | `.venv` 目录名用惯例，IDE 自动识别，gitignore 默认忽略 |
| PostgreSQL | **免安装绿色版 16.15，放在项目外共享位置** | 二进制 `D:\Javatools\pgsql\bin\`（只放一份，所有项目共用）；数据目录 `D:\Javatools\pg-data\`（一个实例，内部建 `novastart` 等多个库）。不注册 Windows 服务、不开机自启；开发时双击 `start-db.bat` 启动，`stop-db.bat` 关闭 |

> 当前状态（2026-11-06 已配置完成）：实例监听 `127.0.0.1:5432`，数据库 `novastart` 已创建，编码 UTF8、时区 Asia/Shanghai、本地认证方式 trust（开发环境无密码）。
> 为什么放项目外：二进制约 200MB+，复制到每个项目既浪费磁盘又容易被 git 收进去；且同一实例可建多个库（`novastart`、其他项目库），只占一份内存（约 150MB）。

本地启动顺序：

```
① 双击 backend/start-db.bat      → 启动 D:\Tools\pgsql-16 实例，localhost:5432
② 双击 backend/start-api.bat     → uvicorn --reload，localhost:8000/docs
③ 双击 frontend/start-web.bat    → vite dev，localhost:5173
```

只有这些情况才需要"每项目一套独立实例"：需要不同 PostgreSQL 大版本，或要求两套完全隔离的运行环境（此时错开端口 5432 / 5433）。当前 Demo 不需要。

调试手段：前端 Vite HMR 即时看页面改动；后端 `--reload` 自动重启；`/docs` 页面直接发请求验证计时、结算、信箱等全部接口逻辑。

### 环境差异（同一套代码，两种连接串）

```
# 本地开发 .env（绿色版 trust 认证，无密码）
DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/novastart

# Docker Compose 注入（主机名是服务名）
DATABASE_URL=postgresql+psycopg://postgres:dev@postgres:5432/novastart
```

### 交付（全栈 Docker Compose）

```
双击 start.bat
  → docker compose up -d --build
  → 浏览器打开 http://localhost
```

对方电脑只需装 Docker Desktop（官网下载安装包），无需 Python / Node / PostgreSQL。

### LLM 接入方式

`.env` 中配置：
```
LLM_PROVIDER=mock                # mock | deepseek | openai | custom
LLM_API_KEY=                     # 真实模型时必填
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

未配置 `LLM_API_KEY` 时自动走 Mock 模板降级，Demo 可完整跑通。

---

## 六、不在本技术栈内的组件（刻意排除）

| 组件 | 为什么排除 |
|---|---|
| Redis / Celery | Demo 规模不需要消息队列；懒计算 + 懒失效已足够 |
| pg_cron | Demo 规模不需要数据库层定时任务 |
| React Query / TanStack Query | Zustand + Axios 拦截器已够用 |
| Redux Toolkit | 比 Zustand 重，Demo 不需要 |
| WebSocket | 不需要实时推送；信件投递是静默的，下次结算页再提示 |
| Next.js | Demo 是 SPA，不需要 SSR / ISR |
| Ant Design | shadcn/ui + Tailwind 风格更现代，适合主视觉组件定制 |

---

## 七、关键非功能需求的技术覆盖

### 7.1 并发安全 ✅

| 场景 | 技术保证 |
|---|---|
| 未处理信箱永不超 3 封（并发投递） | PostgreSQL **行锁** `SELECT ... FOR UPDATE` + 事务；SQLAlchemy 2.0 原生支持 `with_for_update()` |
| 同一动作（投递/收藏）只执行一次 | PostgreSQL **唯一约束** + 幂等键（session_id + action_type） |
| FastAPI 同时处理多个请求 | ASGI 异步框架，天然高并发 |
| 同一 session 只结算一次 | PostgreSQL 事务 + `UPDATE ... WHERE status = 'active'`，带条件更新天然幂等 |

**不需要** Redis / 分布式锁；Demo 规模 PostgreSQL 单机事务隔离级别（Read Committed）已足够。

### 7.2 数据安全 ✅（按 Demo 定位）

| 要求 | 技术保证 |
|---|---|
| 无效场次（<5 分钟）完全丢弃 | 后端 INSERT session 之前先判时长，无效根本不写库 |
| 历史感想只读，不可事后编辑 | 后端**不提供 PUT 接口**，只有 GET；前端不给编辑按钮 |
| 未收藏信件当日失效 | **懒失效**：查询时 `WHERE expired_at < Clock.now()` 过滤，脏数据永远读不到 |
| 客户端时钟不可信 | 所有时间判定来自 FastAPI `Clock` 模块（返回服务端 Asia/Shanghai 时间） |
| 跨零点归属开始日 | `startedAt timestamptz` 字段，Clock 按 Asia/Shanghai 计算自然日 |

**生产级扩展预留**：未来加用户密码（bcrypt）+ JWT + HTTPS 即可，架构不需推翻。

### 7.3 断网 / 刷新 / 锁屏恢复 ✅

| 场景 | 技术保证 |
|---|---|
| 刷新页面回来计时继续 | session 存在 PostgreSQL；刷新后调 `GET /session/current` 拿到 `startedAt`，前端用 `Clock.now() - startedAt` 补算 |
| 断网回来自动续算 | 同上；后端 Clock 返回真实服务端时间，不依赖客户端时钟 |
| 锁屏 / 电脑休眠 | React `visibilitychange` 事件触发 API 调用，后端补算 |
| 结算四步中途离开 | `settleStep` 字段存在 PostgreSQL，下次进来前端直接跳到对应步骤页面 |
| 到 5 分钟但没点结束 | **懒计算**：任何请求进来都检查 `Clock.now() >= startedAt + 5min`，自动标记完成 |
| 180 分钟自动结束 | 同上；每次进入专注页/首页都检查并结算 |

**核心机制**：session 状态的**唯一真相源是 PostgreSQL**，前端只是"显示器"，刷新/断网/锁屏都不影响数据库里的 `startedAt` 和 `settleStep`。

### 7.4 动态网页效果 ✅

| 效果 | 技术 |
|---|---|
| 星星墙（亮/暗/空心断签） | Tailwind `bg-gradient` + `opacity` 切换 + `transition` 过渡 |
| 5 分钟里程碑星星短暂发光 | framer-motion `animate={{ scale: [1, 1.2, 1], opacity: [0.7, 1, 0.7] }}` |
| 连续天数大数字 +1 弹跳 | framer-motion `AnimatePresence` + `CountUp` 组件 + `spring` 物理动画 |
| 结算页步骤式流程展开 | framer-motion `motion.div` + `variants`（hidden → visible） |
| 结算页背景色调渐变 | Tailwind `bg-` 类切换 + `transition-colors duration-1000` |
| 未处理信箱卡片进出 | framer-motion `AnimatePresence` + `animate-in/out` |
| "来自宇宙的音讯"淡入 | framer-motion `motion.p` + `initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}` |
| 正计时数字滚动 | framer-motion 或 `CountUp` 组件 |

---

> 版本：v1.1（2026-11-06 更新：补充前端具体组件 lucide-react / framer-motion / react-hook-form / zod，新增第七节关键非功能需求覆盖）
