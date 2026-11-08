# 008 · LLM 提示词优化与整合

> 来源：用户 2026-11-08 提供的「5 分钟起步任务拆解助手」提示词草稿 + [002 · F1+F2 今日任务](./002-f1-f2-today-task.md) 的 F2 验收条件。执行计划：[2026-11-08-llm-prompt-tuning.md](../superpowers/plans/2026-11-08-llm-prompt-tuning.md)。

## 1. 背景与目标

现有拆分器 `_SYSTEM_PROMPT`（[openai_compat.py](../../backend/app/llm/openai_compat.py#L14-L18)）只要求「一个极低门槛的启动步骤 + 不超过 5 个步骤」，没有约束：

- 「只负责启动、不要求在 5 分钟内完成原任务」——模型容易把原任务原样搬进 `starter_step`（如「写完论文」→ 起步目标「写完论文」）；
- 「降低心理门槛、允许粗糙」——容易产出「掌握爬虫全套原理」这类抽象、无法立刻行动的指令；
- 「原目标 5 分钟内可完成时禁止强行拆分」——会把本已完成的小目标再切一遍；
- `starter_step` 的长度与格式（标签前缀、字符上限）——超过 60 字符会被 service 二次校验判不合规、走降级。

目标：用用户给定的完整版提示词替换 `_SYSTEM_PROMPT`，并把消息组装抽成纯函数 `_build_messages(task_text, date)`，使「用户目标原文被原样携带」可被单元测试钉住。**JSON 输出契约、`_parse_payload` 二次校验、LRU 缓存与降级策略一律不变。**

## 2. 范围与非目标

- 范围：
  - `backend/app/llm/openai_compat.py` 的 `_SYSTEM_PROMPT` 全文替换；
  - 新增 `_build_messages(task_text, date) -> list[dict[str, str]]` 并在 `_call_llm` 中使用。
- 非目标（明确不做的）：
  - 不改 JSON 输出契约与 `_parse_payload`（字段、类型校验、5 条截断均不动）；
  - 不改 `_CACHE` LRU、`_CACHE_CAPACITY`、异常 fallback 路径；
  - 不改 `services/task_service.py` 的 60 字符 / 3 条二次校验（`MAX_STARTER_CHARS` / `MAX_STEPS`）；
  - 不改 `llm/base.py`、`llm/mock.py`、`llm/__init__.py`、`routers/`、`schemas/`、前端；
  - 不新增配置项、不加温度等请求参数（仍只用 `model` / `messages` / `response_format`）；
  - 不引入提示词文件或运行时加载，提示词仍以常量内联在 `openai_compat.py`。
- 备选（不写入代码，仅记录）：用户另给了「精简版」提示词。若日后要省 token，可整体替换 `_SYSTEM_PROMPT` 文本，不动任何结构；本次采用**完整版**（质量优先；结果按「任务文本|日期」缓存、调用频次低，token 成本可接受）。

## 3. 可测试的验收条件

1. `_build_messages("复习三角函数\n附带 3 道错题", "2026-11-08")` 返回长度 2、`roles == ["system", "user"]` 的消息列表；user 消息包含用户目标原文（换行、引号、中英文混排**不得被改写、截断或转义**）与日期。
2. `_SYSTEM_PROMPT` 文本包含：角色名「5 分钟起步任务拆解助手」、最高优先级「禁止强行拆分」、「只负责启动」、「粗糙」（允许粗糙）、「只输出一个 JSON 对象」、`starter_step` 长度约束「40 个字符」与硬上限「60 字符」。
3. 符合新提示词的两种产物都能通过 `_parse_payload` 与 `_normalize_split`：① 原目标本身 5 分钟内可完成 → `steps: []`；② 正常拆分 → `steps` 只含一条「启动说明：…」。
4. 既有 6 条 `test_llm.py` 用例（Mock 契约、缓存、超时降级、`_parse_payload` 三条拒绝/截断）继续通过；`tests/test_architecture.py` 棘轮继续通过。
5. 不合规产物仍走既有降级路径：`starter_step` 为空或超过 60 字符 → `_normalize_split` 返回 `None` → `_fallback_split`，不返回假成功；缺字段 / 类型错 → `_parse_payload` 抛 `ValueError` → fallback。
6. 字段映射：`starter_step` ← 5 分钟起步目标（一句话），`steps` ← 0–1 条「启动说明」；不新增 JSON 字段，不改 `SplitResult`。
7. 不新增依赖、不改启动方式（仍 `python -m app.main`）、无表结构与迁移变化、无 API 契约变化。

## 4. 现有 owner 和受影响模块

对照 [architecture.md](../architecture.md)「关键数据的权威来源」：拆分结果仍由 `llm/` 客户端产出、由 `services/task_service.py` 校验并落库；本改动只改「携带用户输入 → 请求模型」这一段，不新增任何数据 owner。

| 模块 / 文件 | 角色 | 改动方式 |
|---|---|---|
| `backend/app/llm/openai_compat.py` | 提示词与消息组装 owner | 修改：替换 `_SYSTEM_PROMPT` 全文；新增 `_build_messages`；`_call_llm` 改用它 |
| `backend/tests/test_llm.py` | 拆分器单测 | 修改：追加 3 条用例，导入行补 `_SYSTEM_PROMPT` / `_build_messages` |
| `backend/app/llm/base.py`、`mock.py`、`__init__.py` | 拆分器接口 / 兜底 / 工厂 | 不改 |
| `backend/app/services/task_service.py` | `_normalize_split` 二次校验与降级 | 不改（继续兜底 60 字 / 3 条） |
| `backend/app/routers/`、`schemas/`、`frontend/` | 接口契约与展示 | 不改 |

## 5. 实现步骤

本改动不涉及六步切片中的 ①契约 / ②迁移 / ④router / ⑤前端，只落 ③ 的拆分器客户端（详见 [dev-order.md](../dev-order.md)：拆分器属 service 层内部实现）。按计划顺序执行：

1. 写本 Spec 并提交。
2. **TDD 红**：`backend/tests/test_llm.py` 追加 3 条用例（`test_build_messages_preserves_raw_goal`、`test_system_prompt_encodes_starter_rules`、`test_prompt_shaped_payload_passes_normalization`），跑出失败。
3. **实现**：替换 `_SYSTEM_PROMPT` 全文；新增 `_build_messages`；`_call_llm` 改为 `"messages": _build_messages(task_text, date)`。
4. **绿**：`test_llm.py` 9 passed；架构棘轮通过；提交。
5. **验证与回填**：后端全量 pytest（需 PostgreSQL + 沙箱外）+ 可选的真实模型冒烟；回填第 8 节并提交。

## 6. 接口、数据及兼容性变化

- API：无。请求体 / 响应体 / 字段均不变（`SplitResult` 不动）。
- 数据：无表结构、无迁移、无回填。
- 行为：模型产出的 `starter_step` / `steps` 内容质量变化；`_parse_payload` 与 `_normalize_split` 的判定语义不变。
- 运行边界：同一进程内 LRU（key = `任务文本|日期`）可能命中旧提示词产出的缓存结果；重启进程即失效。属运行边界，不属契约变更。
- 降级不变：超时 / 网络异常 / 输出格式不符 / 二次校验不合规，仍落到 `MockSplitter`（`source="fallback"`）。
- 长度约束为**软约束**：提示词要求 starter ≤40 字符，最终仍由 `task_service.MAX_STARTER_CHARS = 60` 硬校验兜底。

## 7. 测试场景与验证命令

| 验收条件 | 测试 | 期望 |
|---|---|---|
| 1 | `test_build_messages_preserves_raw_goal` | `roles == ["system", "user"]`；含换行的原文与日期均出现在 user 消息中 |
| 2 | `test_system_prompt_encodes_starter_rules` | 提示词含角色名、禁止强行拆分、只负责启动、粗糙、只输出一个 JSON 对象、40 个字符、60 字符 |
| 3 | `test_prompt_shaped_payload_passes_normalization` | `steps: []` 与单条「启动说明：…」均通过 `_parse_payload` + `_normalize_split` |
| 4 | `test_llm.py` 其余 6 条 + `test_architecture.py` | 继续 passed，断言不放宽 |
| 5 | `test_parse_rejects_string_steps` / `test_parse_rejects_non_string_step_item` | 仍抛 `ValueError`（解析逻辑未被修改） |
| 6–7 | 全量后端测试 + 迁移检查 | 无新增依赖 / 迁移 / 契约变化 |

验证命令：

```powershell
# 拆分器单测（不连库，沙箱内可跑）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q

# 架构棘轮（不连库）
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py -q

# 后端全量（需 PostgreSQL 已启动 + 沙箱外执行）
cd backend; .venv\Scripts\python.exe -m pytest -q
```

真实模型冒烟（可选，需要 `LLM_API_KEY`；不改 `.env`，用环境变量覆盖）：

```powershell
$env:LLM_PROVIDER="openai"; $env:LLM_API_KEY="<key>"; $env:LLM_BASE_URL="https://api.deepseek.com/v1"; $env:LLM_MODEL="deepseek-chat"
cd backend; .venv\Scripts\python.exe -m app.main
```

首页分别输入「写一篇论文」与「读 10 页书」点「分析」：starter 应为可在 5 分钟内动手的具体动作（前者不得是「写完论文」）；有解释时 `steps[0]` 以「启动说明：」开头；`source` 为 `llm`。

## 8. 执行结果、未验证项和遗留问题

### 8.1 已运行通过的验证（2026-11-08）

| 命令 / 场景 | 结果 |
|---|---|
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q`（RED） | 1 error：`ImportError: cannot import name '_build_messages'`（3 条新用例在收集阶段即失败） |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q`（GREEN） | **9 passed**（既有 6 条 + 新增 3 条） |
| `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py -q` | **70 passed**（依赖方向与 `datetime.now()` 棘轮未受影响） |
| `cd backend; .venv\Scripts\python.exe -m pytest -q`（PostgreSQL 已启动，沙箱外） | **211 passed**（改动前 208 + 新增 3），无用例被改写或放宽 |

- 全量日志：`.superpowers/sdd/2026-11-08-llm-prompt-tuning/full-pytest.log`（git-ignored 临时目录）。
- 无新增依赖、无迁移、无 API / 响应字段变化。

### 8.2 测试已编写 vs 已运行通过

- `backend/tests/test_llm.py` 新增 3 条用例**已编写并已运行通过**：`test_build_messages_preserves_raw_goal`、`test_system_prompt_encodes_starter_rules`、`test_prompt_shaped_payload_passes_normalization`。
- 既有 6 条用例未修改、继续通过（`_parse_payload` 拒绝/截断与缓存、超时降级语义不变）。

### 8.3 未验证项及原因

- **真实模型冒烟未执行**：本机 `backend/.env` 的 `LLM_API_KEY` 为空，无可用的真实模型凭据；按计划跳过（未改 `.env`，不伪造 key）。因此「模型实际产出的 starter 是否更具体」「`steps[0]` 是否真的以『启动说明：』开头」两点**无运行时证据**，只由提示词文本断言 + 结构校验覆盖。
- `steps: []` 空数组分支：仅有单元测试（`_parse_payload` + `_normalize_split`）证据，未在真实模型输出上复现。
- 提示词长度约束是软约束：未在真实模型上验证「≤40 字符」的遵守率。

### 8.4 遗留问题与边界

- 提示词为运行时软约束，最终仍由 `task_service.MAX_STARTER_CHARS = 60` 硬校验兜底；超长 starter 会被判不合规并降级到 Mock（不返回假成功）。
- 同一进程内 LRU（key = `任务文本|日期`）可能命中旧提示词产出的缓存条目；重启进程即失效，属运行边界，不属契约变更。
- 用户提供的「精简版」提示词未写入代码（§2 备选），如需省 token 可整体替换 `_SYSTEM_PROMPT` 文本，不必改结构。

---

> **结构性变更五问**
>
> 1. **修改哪一层？** 只改 ③ service 内部的 LLM 拆分器客户端（`llm/openai_compat.py`），不涉及契约、迁移、router、前端。
> 2. **当前 owner 在哪里？** 提示词与消息组装的 owner 是 `backend/app/llm/openai_compat.py`；拆分结果的校验 owner 仍是 `services/task_service.py`。
> 3. **是否引入重复状态或平行写入？** 否。仅替换常量文本并抽出纯函数，无新状态、无第二写入路径、无提示词配置文件。
> 4. **是否影响接口和其他模块？** 否。`SplitResult`、JSON 字段、API 响应、`_parse_payload`、LRU、fallback 均不变。
> 5. **哪些现有检查需要继续通过？** `backend/tests/test_llm.py`（既有 6 条 + 新增 3 条）、`tests/test_architecture.py` 棘轮、后端全量 pytest。
