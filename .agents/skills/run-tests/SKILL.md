---
name: run-tests
description: 运行后端 pytest、前端 lint/build 等验证命令，含本机沙箱与数据库的前置条件。
---

# 测试与验证

## 何时使用

改动完成后验证；或排查测试失败。

## 使用前必读

- `AGENTS.md` 的「本机环境关键约束」

## 检查清单与命令

### 1. 架构棘轮（无需 DB，沙箱内可跑）

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py
```

### 2. 后端行为测试（需 DB）

前置：PostgreSQL 运行中（启动方式见 AGENTS.md，必须 WMI 方式）。

- 使用独立库 `novastart_test`（模型含 JSONB/timestamptz，不能换 SQLite）。
- 连接数据库 → 命令必须 `dangerouslyDisableSandbox: true`。

```powershell
cd backend; .venv\Scripts\python.exe -m pytest
```

### 3. 前端（沙箱内可跑）

```powershell
cd frontend; npm run lint; npm run build
```

### 4. 手动冒烟（可选，需 DB + 沙箱外）

```powershell
cd backend; .venv\Scripts\python.exe -m app.main   # 禁止裸 uvicorn CLI
# PowerShell 发 JSON 用 Invoke-RestMethod，不用 curl.exe（双引号会被吞）
```

## 禁止

- 测试失败时放宽断言、加白名单、提高阈值、删测试。
- 为「跑通」把测试库换成 SQLite。
- 跑全量测试时不设沙箱外标志导致误判为代码问题。

## 完成判定

与改动相关的检查全部真实运行并通过；输出贴回 Spec 第 8 节。跑不了的（如 Docker 链路）明确标注「未验证 + 原因」。
