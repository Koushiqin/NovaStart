# NovaStart 开发边界与易错点清单

> 创建：2026-11-07。定位：**操作性陷阱与红线的唯一主记录**——测试安全、工具链、运行时、冒烟方式。
> 与 [architecture.md](architecture.md) 互补：那边管结构边界（分层、数据归属），这边管动手时会踩的坑。
> 本文件**不复述**已有主记录的规则，只在一处指回；同一事实永远只维护一份。

## 0. 指回主记录（这些规则不在这里展开）

| 主题 | 主记录 |
|---|---|
| 分层方向、数据唯一真相源、Clock 时间源 | [architecture.md](architecture.md) |
| 六步流水线、功能实现顺序、完成门 | [dev-order.md](dev-order.md) |
| 本机环境约束（沙箱断网、WMI 启 PG、`python -m app.main`、端口占用、shadcn 绕 npx） | [AGENTS.md](../AGENTS.md) 末节 |
| 需求规则（F1–F10、跨天、异常兜底） | [brainstorming.md](../brainstorming.md) |

动手前先查上表；下面只列这些文档**未覆盖**的易错点。

---

## 1. 测试红线（最高优先级，违反即毁数据）

1. **测试库只允许是 `novastart_test`**。API 测试每个用例执行 `drop_all/create_all`——一旦误连开发库 `novastart`，全部演示数据与迁移记录立即清空。连接串只能出现在 `backend/tests/` 的测试配置一处，禁止从 `.env` 继承。
2. 为什么不能用 SQLite：模型含 JSONB / timestamptz，SQLite 方言不兼容。不要为"跑得快"引入 SQLite 测试路径。
3. 跑连库测试必须 `dangerouslyDisableSandbox: true`（沙箱网络隔离，连不上宿主 5432）。
4. 棘轮测试 `test_architecture.py` 不需要数据库，可随时跑；但它只查结构，不能替代行为测试。

## 2. 工具链陷阱

1. **PowerShell 下禁止用 `curl.exe` 传 JSON body**（双引号会被吞掉，后端收到 422 且难以排查）。后端手工冒烟统一用：
   `Invoke-RestMethod -Uri ... -Method Post -Body (...) -ContentType 'application/json' | ConvertTo-Json -Compress`
2. **shadcn 组件安装禁用 `npx shadcn`**（npm 12 + 用户 .npmrc allow-scripts 触发 EALLOWSCRIPTS）。必须直接 `node <npx缓存>\node_modules\shadcn\dist\index.js add ...`，且访问 ui.shadcn.com 需 `dangerouslyDisableSandbox: true`。CLI 锁 **2.4.0**——latest 4.x 是 Tailwind v4 栈，与本项目 Tailwind 3 不兼容。
3. **lint 基线**：`components/ui/button.tsx` 有 1 条 fast-refresh warning，属 shadcn 模板固有，为**通过基线**。不要为消除它重构该文件；lint 通过标准是 0 error + 仅此 1 warning。
4. 控制台里中文响应显示乱码只是控制台编码问题，不是接口 bug，不要据此改后端编码配置。

## 3. 运行时陷阱

1. **LLM 拆分缓存是模块级 LRU(128)**，只存在于单进程内存。禁止以多 worker 方式启动后端（`--workers >1`）——各 worker 缓存独立，命中率与降级统计失真，且违背"同一标题连点复用"的产品约定。Demo 一律单进程。
2. 后端启动方式固定 `python -m app.main`（见 AGENTS.md）；连带约束：`backend/app/db.py` 顶部的 `WindowsSelectorEventLoopPolicy` 四行**禁止删除或下移**，psycopg3 异步在 Windows ProactorEventLoop 下直接崩。
3. 所有模拟加速/时间旅行只改 `clock.py` 一处；测试涉及时序必须注入/控制 Clock，禁止 sleep 墙钟时间。
4. `/dev/reset-seed` 与 vite proxy 的 `/dev` 转发是演示专用链路；业务功能（F1–F10）不得依赖 `/dev` 前缀接口。
5. SmokePanel 每次点击都会 reset 种子数据，user id 随点击变化——调试用旧 id 查 `sessions/current` 必空，属预期行为，不是 bug。

## 4. 交付与仓库边界

1. Docker 链路（compose 一键交付）本机尚未端到端验证（Docker Desktop 不可用），宣布"交付可用"前必须在有 Docker 的机器上跑一次 `docker compose up -d --build` 并走通演示脚本。
2. `TECH_STACK.md` / `techstack_plan.md` 按用户要求保持 git 未跟踪，不要主动 `git add`；`.env` 永不入库。
3. 新增依赖、改 CI、改检查语义前，按 AGENTS.md 先说明必要性并确认——包括"顺手升级"某个能跑的依赖。

---

> 维护约定：踩到新坑先复现确认，再补进对应小节；某条被架构调整消化掉就删除，不留"历史遗迹"。
