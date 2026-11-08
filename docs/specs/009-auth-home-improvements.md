# 009 登录注册鉴权 + 首页美化 + 历史记录与随机感想

## 1. 背景与目标

当前 NovaStart 没有真正的鉴权：前端把 `userId` 存 localStorage，请求头 `X-User-Id` 直接携带，后端信任该头。首页直接展示任务输入流程，缺少统一的美化入口、登录/注册/登出、历史记录查询、随机感想回顾等功能。

本次改动目标：
- 引入真正的登录/注册/登出与会话（3 天有效期），用户标识为字符串 username（1-15，唯一）。
- 首页统一为美化 Hero（标题 + 激励语 + 图片占位）+「开始今日的五分钟学习」按钮（未登录不可点，已登录弹窗承载任务流程）。
- 已登录用户在首页可查看连续天数、星星墙、历史收藏信件弹窗、按日期查询历史学习记录弹窗、随机获取一条过去感想弹窗。

需求来源：用户口述（本轮盘问已对齐），不对应 brainstorming.md 既有 F1-F10 单条，属功能完善。

## 2. 范围与非目标

**范围**：
- 后端：`users.username` 字段 + `sessions` 表；`/api/auth/login|register|logout`；`get_current_user_id` 改读 Bearer token；`GET /api/sessions/by-date`；`GET /api/review/daily`；种子数据分配 username。
- 前端：store 加 `sessionToken`/`username`；`client.ts` 改 Authorization + 401 处理；`/login`、`/register` 页面与路由守卫；首页 Hero + 开始学习弹窗 + 三个功能弹窗（历史收藏信件、历史记录按日期、随机感想）；右上角账号区改造。

**非目标**：
- 星星墙视觉重做（后续单独处理，本次保留现有 StarWall）。
- 密码 / 邮箱验证（Demo 仅 username 登录）。
- JWT（用服务端 session 表）。
- `/mailbox` 完整流程改造（保留，仅在首页加历史收藏信件快速查看弹窗）。

## 3. 可测试的验收条件

### 注册
1. `POST /api/auth/register {"username": "alice"}` → 201，返回 `{user, token}`，`users.username='alice'` 存在，自动创建 session。
2. 注册 username 长度 0 或 >15 → 422。
3. 重复注册已存在 username → 409 `USERNAME_TAKEN`。
4. 并发注册同一 username → 仅一个成功，另一个 409（唯一约束 + IntegrityError 捕获）。

### 登录
5. `POST /api/auth/login {"username": "xiaoming"}` → 200，返回 token + user；`sessions` 表有记录，expires_at = now + 3 天。
6. 登录不存在 username → 404 `USER_NOT_FOUND`。

### 鉴权
7. 带有效 `Authorization: Bearer <token>` 访问业务接口 → 正常；token 无效/过期 → 401。
8. `POST /api/auth/logout`（带 token）→ 204，session 行被删；再次用该 token → 401。

### 历史记录
9. `GET /api/sessions/by-date?date=YYYY-MM-DD` → 当日（Asia/Shanghai 归属日）有效场次数组，按 started_at 升序，字段 `started_at/ended_at/task_title/reflection`。
10. 空日期 / 非法格式 → 422；无记录 → 空数组。

### 随机感想
11. `GET /api/review/daily` → 一条过去有效场次的感想（task_title + reflection + date），同一 user 同一归属日重复调用返回同一条。
12. 无历史 → `{item: null}`。

### 前端
13. 未登录访问首页 → Hero + 不可点的「开始今日的五分钟学习」+ 右上角「登录」「注册」。
14. 登录成功 → 首页显示连续天数、星星墙、三个功能按钮；右上角显示用户名 + 切换账号 + 登出。
15. 点击「开始今日的五分钟学习」→ 弹窗内任务输入→分析→开始学习，成功跳 /focus，❌ 关闭。
16. 历史记录弹窗选日期 → 展示当日场次（升序），空则「当天无学习记录」，❌ 关闭。
17. 随机感想按钮 → 展示一条感想，同日重复点击同一条。
18. 401 → 清登录态跳 /login。

## 4. 现有 owner 和受影响模块

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/models/user.py` | User 模型 | 新增 `username` 字段 |
| `backend/app/models/session.py`（新建）| Session 模型 | 新增 `sessions` 表模型 |
| `backend/app/schemas/auth.py`（新建）| auth 契约 | Login/Register/Logout 请求响应 |
| `backend/app/schemas/session.py` | session 契约 | 新增 by-date 响应 |
| `backend/app/schemas/review.py` | review 契约 | 新增 daily 响应（复用 ReviewItem） |
| `backend/app/services/auth_service.py`（新建）| auth 业务 | login/register/logout + session 校验 |
| `backend/app/services/session_service.py` | session 业务 | 新增 `list_by_date` |
| `backend/app/services/review_service.py` | review 业务 | 新增 `daily_past`（同日确定性） |
| `backend/app/routers/auth.py`（新建）| auth 路由 | login/register/logout |
| `backend/app/routers/session.py` | session 路由 | 新增 by-date |
| `backend/app/routers/review.py` | review 路由 | 新增 daily |
| `backend/app/deps.py` | 鉴权依赖 | `get_current_user_id` 改读 Bearer + 查 session |
| `backend/app/seed.py` | 种子数据 | 演示账号分配 username |
| `backend/app/main.py` | 入口 | 注册 auth router |
| `backend/alembic/versions/` | 迁移 | username 列 + sessions 表 |
| `frontend/src/store/app.ts` | 全局状态 | 加 sessionToken/username/login/logout |
| `frontend/src/api/client.ts` | HTTP 通道 | 改 Authorization + 401 处理 |
| `frontend/src/App.tsx` | 路由 | 加 /login /register + 守卫 |
| `frontend/src/pages/LoginPage.tsx`（新建）| 登录页 | username 登录 |
| `frontend/src/pages/RegisterPage.tsx`（新建）| 注册页 | username 注册 |
| `frontend/src/pages/HomePage.tsx` | 首页 | Hero + 弹窗 + 功能按钮 |
| `frontend/src/features/AccountSwitcher.tsx` | 账号区 | 改登录/注册/切换/登出 |

## 5. 实现步骤

按六步垂直切片，本次涉及多个子功能，按依赖顺序串联：

1. **契约**：User 加 `username`；新增 Session 模型；auth/session/review schemas。
2. **迁移**：`alembic revision --autogenerate` → 核对（username 列 + sessions 表 + 外键 + 索引）。
3. **业务**：
   - auth_service：create_session_token、login（查 username→建 session）、register（校验 1-15 + 唯一，原子写入，IntegrityError→409，成功建 session）、logout（删 session）、get_session_user（查 token 未过期）。
   - session_service.list_by_date(db, user_id, date)：按归属日过滤有效场次，join DayTask + Reflection，升序。
   - review_service.daily_past(db, user_id, clock)：复用 random_past 查询，按 `(user_id, 归属日)` 确定性选一条（`offset = hash(user_id, date) % count`）。
4. **接口**：auth router；session by-date；review daily；deps 改 Bearer；main 注册。
5. **前端**：store + client + 路由守卫 + 登录/注册页 + 首页重设计 + 弹窗。
6. **端到端联调**。

## 6. 接口、数据及兼容性变化

**表结构**：
- `users` 新增 `username varchar(15) not null unique`。已有演示账号迁移时回填 `xiaoming/xiaomei/xiaogang`。
- 新增 `sessions(token varchar(64) pk, user_id int fk users.id, expires_at timestamptz not null)`，`user_id` 建索引。

**接口变更**：
- 新增：`POST /api/auth/login`、`POST /api/auth/register`、`POST /api/auth/logout`、`GET /api/sessions/by-date`、`GET /api/review/daily`。
- 变更：所有业务接口的鉴权头由 `X-User-Id: <int>` 改为 `Authorization: Bearer <token>`；`X-User-Id` 不再被信任。
- `/dev/reset-seed` 行为不变（只重置数据，不自动登录）。

**兼容性**：
- 前端 localStorage 中旧的 `userId`（int）在登录后会被新 token 覆盖；旧 userId 不再作为鉴权凭据。
- 现有测试中通过 `X-User-Id` 鉴权的用例需改为先 login 拿 token（或 dependency_overrides `get_current_user_id`）。

## 7. 测试场景与验证命令

**后端测试**（需 DB，`dangerouslyDisableSandbox: true`）：
- `test_auth.py`：注册成功/长度校验/重复/并发；登录成功/不存在；鉴权有效/过期；登出失效。
- `test_session_api.py` 补：by-date 正序/空/非法日期。
- `test_review.py` 补：daily 同日确定性/无历史。

**验证命令**：
```powershell
# 棘轮（无需 DB）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
# 全量后端测试
cd backend; .venv\Scripts\python.exe -m pytest
# 迁移双向
cd backend; .venv\Scripts\python.exe -m alembic downgrade base; .venv\Scripts\python.exe -m alembic upgrade head
# 前端
cd frontend; npm run lint; npm run build
```

---

> 结构性变更五问：
> 1. **修改哪一层**：models（加字段/表）、services（auth + by-date + daily）、routers（auth + 两新 endpoint）、deps（鉴权）、前端全链路。
> 2. **owner 在哪**：用户身份 owner = users 表 + sessions 表；历史记录 owner = sessions + reflections + day_tasks；感想 owner = review_service。
> 3. **是否引入重复状态**：否。sessionToken 是服务端 sessions 表的客户端镜像；userId 仅作展示，鉴权唯一真相源是 sessions 表。
> 4. **是否影响接口**：是。鉴权头从 X-User-Id 改 Bearer，影响所有业务接口调用方（前端集中在 client.ts 一处改）。
> 5. **哪些检查须通过**：棘轮（分层 + datetime.now 仅限 clock.py）、pytest 全量、alembic 双向、前端 lint/build。

## 8. 执行结果、未验证项和遗留问题

### 执行结果

**后端（已验证通过）**：
- 模型：`users.username varchar(15) not null unique`；新建 `auth_sessions(token, user_id, expires_at)` 表。迁移 `77f07e2846ef` 含存量回填（小明→xiaoming 等）+ not null + 唯一索引，双向回滚通过。
- 业务：`auth_service`（login/register/logout/get_session_user_id），注册捕获 IntegrityError 统一 409，原子写 user+session；`session_service.list_by_date`（按 Asia/Shanghai 归属日过滤有效场次，升序）；`review_service.daily_past`（sha256(user_id+date) 取模，同日确定性）。
- 接口：`POST /api/auth/login|register|logout`、`GET /api/sessions/by-date`、`GET /api/review/daily`；`get_current_user_id` 改读 `Authorization: Bearer`，过期/无效 401。
- 种子：演示账号分配 username，清表顺序加入 AuthSession 避免外键冲突。
- 测试：新增 `test_auth.py`（注册成功/长度/重复/并发、登录成功/不存在、Bearer 鉴权、401、过期、登出）；`test_session_api.py` 补 by-date（升序/空/非法日期）；`test_review.py` 补 daily（同日确定性/空）。全量 **234 passed**，棘轮 **77 passed**。

**前端（已验证通过）**：
- store：新增 `sessionToken`/`username`，`login`/`logout` action，persist 只持久化身份字段。
- client：请求拦截器发 `Authorization: Bearer`；响应拦截器 401 清登录态。
- 路由：`/login`、`/register`，`/focus|/settle|/mailbox|/records` 加 `ProtectedRoute`。
- 首页：Hero（标题+激励语+16:9 图片占位+开始按钮，未登录 disabled）；已登录显示 streak+星星墙+三功能按钮；开始学习弹窗承载 TaskComposer+SplitEditor+开始（成功跳 /focus）；历史收藏信件弹窗（GET /letters/history）；历史记录弹窗（年/月/日三下拉 + GET /sessions/by-date）；随机感想弹窗（GET /review/daily）。
- 右上角账号区：未登录→登录/注册；已登录→用户名+切换账号+登出。
- `npm run lint` 0 error（仅 button.tsx 既有 warning）；`npm run build` 通过。

**端到端冒烟**：浏览器验证首页未登录态→注册→已登录态→开始学习弹窗→登出全链路 PASS；API 验证 by-date/daily/letters-history 返回数据正确。

### 未验证项
- 星星墙视觉（用户后续单独美化，本次保留现有 StarWall）。
- Docker 端到端（本机 Docker 不可用，待环境可用后补 `docker compose up -d --build` 验证）。

### 遗留问题
- 浏览器自动化输入框偶发失焦（自动化工具问题，非代码缺陷），登录注册逻辑经 API 与首次浏览器注册验证通过。
- 历史收藏信件弹窗复用 `/letters/history`（仅返回已收藏），完整信箱处理流程仍在 `/mailbox` 页。
