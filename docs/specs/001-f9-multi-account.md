# 001 · F9 多账号与请求头 userId

> 来源：[brainstorming.md](../../brainstorming.md) F9；执行计划：[2026-11-07-p1-f9-multi-account.md](../superpowers/plans/2026-11-07-p1-f9-multi-account.md)。

## 1. 背景与目标

Demo 需要让评委在同一台电脑上看到「互相送信」「连续 7 天」等依赖多身份的效果，而当前所有接口都靠 body / query 里的 `user_id` 传身份，前端也把 `user_id` 散落在请求载荷中，既无法在页面顶部整体切换账号，也留下多处写入入口。

目标：提供三个固定演示账号（小明 / 小美 / 小刚），可在页面顶部切换；所有 `/api` 请求经 `X-User-Id` 请求头单点注入身份，切换后首页 / 记录 / 信箱数据整体切换。同时提供仅演示环境可用的时间偏移能力，为后续跨天 / 断签演示打底。

## 2. 范围与非目标

- 范围：
  - 请求头身份改造：后端新增 `get_current_user_id` 依赖，4 个业务 router 的 `user_id` 全部改由请求头注入，`TaskCreate` / `SessionCreate` 删除 `user_id` 字段，GET 接口删除 `user_id` query。
  - 新增 `GET /api/users`（无需请求头），返回演示账号列表与 `server_time`。
  - 种子数据扩为 3 个账号：小明（连续 6 天历史）、小美（1 条历史）、小刚（空）。
  - demo 时间偏移：`settings.demo_time_offset_seconds` + `get_clock()` 依赖，所有 router 经 `Depends(get_clock)` 取时钟。
  - 前端账号切换：axios 请求拦截器注入 `X-User-Id`；store `userId` 持久化；`AccountSwitcher` 挂在 App 根部。
- 非目标（明确不做的）：
  - 真实鉴权、注册 / 登录 / 会话管理（Demo 无鉴权，请求头即身份）。
  - 信箱信件预置（归 P6，本计划只做账号与历史记录种子）。
  - 时间加速（60 秒 = 5 分钟，归 P3 阈值配置），本计划只做时间偏移。
  - 时间旅行 UI 开关（本计划只留 env 偏移能力，入口由后续演示计划决定）。

## 3. 可测试的验收条件

1. `POST /api/tasks` 等业务接口缺失 `X-User-Id` → `422`（FastAPI 请求头校验失败），不是 `500`。
2. `X-User-Id` 指向不存在的账号 → 统一 `404`，响应体含稳定 `code`（`USER_NOT_FOUND`）+ 人话 `message`；不得落库半截数据。
3. 两个账号各自建任务后，经请求头查询「今天」数据互不可见；切换账号看不到上一账号的进行中 session / 任务。
4. 浏览器刷新后账号保持（`localStorage` key `novastart-user`），不回落默认账号。
5. 旧 body / query 的 `user_id` 残留为零：`Grep "user_id" backend/app/routers backend/app/schemas` 仅出现服务层调用参数与模型字段引用，不存在请求契约字段。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/deps.py`（新增） | 当前用户解析唯一入口 | 新增 `get_current_user_id` Header 依赖 + 账号存在性校验 |
| `backend/app/routers/user.py`（新增） | 账号列表接口 | 新增 `GET /api/users` |
| `backend/app/schemas/user.py`（新增） | 账号列表契约 | 新增 `UserOut` / `UsersResponse` |
| `backend/app/routers/task.py`、`session.py`、`letter.py`、`settle.py` | 业务接口 | 删除 body / query 的 `user_id`，改 `Depends(get_current_user_id)` |
| `backend/app/schemas/task.py`、`session.py` | API 契约 | `TaskCreate` / `SessionCreate` 删除 `user_id` |
| `backend/app/main.py` | 路由注册 | 注册 user router |
| `backend/app/seed.py` | 演示数据 | 改为 3 账号（小明 6 天 / 小美 1 条 / 小刚空） |
| `backend/app/config.py` | 配置 | 新增 `demo_time_offset_seconds` |
| `backend/app/clock.py` | 服务端时间唯一真相源 | 新增 `get_clock()` 依赖（偏移来自 settings） |
| `frontend/src/api/client.ts` | 唯一 HTTP 入口 | 请求拦截器注入 `X-User-Id` |
| `frontend/src/store/app.ts` | 前端身份状态 owner | `userId` 持久化（key `novastart-user`） |
| `frontend/src/features/AccountSwitcher.tsx`（新增） | 账号切换 UI | 拉 `/api/users`、渲染切换按钮 |
| `frontend/src/App.tsx` | 路由骨架 | 挂载 `AccountSwitcher` |
| `frontend/src/features/SmokePanel.tsx` | 临时冒烟组件 | 删除 payload 中的 `user_id` |

## 5. 实现步骤

1. 写 Spec 001 并提交（本文件）。
2. 后端：先写 `backend/tests/test_user_header.py`（缺头 422 / 未知账号 404 / users 接口 / 数据隔离），确认 FAIL；实现 `deps.py`、`routers/user.py`、`schemas/user.py`，改造 4 个 router 与 2 个 schema，注册路由，扩种子为 3 账号；同步修正既有测试的调用方式（只加请求头，不改断言语义）。
3. 时间偏移：`config.py` 加 `demo_time_offset_seconds`，`clock.py` 加 `get_clock()`，router 的 `Clock()` 调用点全部改为 `Depends(get_clock)`。
4. 前端：`client.ts` 请求拦截器、`store/app.ts` persist、`AccountSwitcher` 挂 App 根部、`SmokePanel` 删 `user_id`，跑 lint + build。
5. 端到端联调三服务，走「切小明 → 切小美 → 刷新保持」演示路径；跑全量后端测试 + 架构棘轮；回填第 8 节。

## 6. 接口、数据及兼容性变化

- **破坏性契约变更（内部 Demo 接口，已在 AGENTS.md 流程内确认）**：
  - `TaskCreate` 删除 `user_id` 字段；`SessionCreate` 删除 `user_id` 字段。
  - `GET /api/sessions/current`、`GET /api/letters/inbox`、`GET /api/letters/history` 删除 `user_id` query 参数。
  - 所有 `/api/*` 业务请求必须携带 `X-User-Id: <int>`；缺失 → `422`；账号不存在 → `404 {code: "USER_NOT_FOUND", message}`。
- 新增：`GET /api/users` → `{users: [{id, name}], server_time}`（无需请求头，按 id 升序）。
- 新增配置：`DEMO_TIME_OFFSET_SECONDS`（默认 0，单位秒，可负）；仅影响 `Clock` 的「当前时间」，不批量修改历史时间戳。
- 表结构：无变更，无新迁移。`users` 表由种子数据填充 3 行。
- 时序影响：`/dev/reset-seed` 返回的账号由 2 个变 3 个，SmokePanel 等调试组件需同步（P2 会整体替换首页）。

## 7. 测试场景与验证命令

从第 3 节验收条件推导：

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_missing_header_422`：`POST /api/tasks` 无 `X-User-Id` | `422` |
| 2 | `test_unknown_user_404`：`X-User-Id: 9999` | `404`，`code == "USER_NOT_FOUND"` |
| 2 | `test_data_isolated_by_header`：两账号各建任务后查询互不可见 | 各自只见自己的数据 |
| 3 | `test_session_isolation_by_header`：账号 A 开 session 后账号 B `/sessions/current` 为空 | `session is null` |
| — | `test_users_endpoint_returns_seed_accounts`：reset 后 `GET /api/users` | `["小明", "小美", "小刚"]` |
| — | `test_get_clock_applies_settings_offset`：偏移 -86400 | `get_clock().today()` 早一天 |

验证命令：

```powershell
# 架构棘轮（无需 DB，随时可跑）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py

# 后端全量测试（需 DB 运行 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest

# 前端基线
cd frontend; npm run lint; npm run build
```

## 8. 执行结果、未验证项和遗留问题

（实现完成后回填。）
