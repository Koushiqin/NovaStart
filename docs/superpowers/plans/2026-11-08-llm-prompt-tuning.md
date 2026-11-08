# LLM 提示词优化与整合 Implementation Plan

> **For agentic workers:** 按任务序执行：Task 1 先落 Spec，Task 2 严格 TDD（红 → 实现 → 绿 → commit），Task 3 只做验证与回填。步骤用 `- [ ]` 跟踪。`test_llm.py` 不连库，可在沙箱内直接跑；全量后端测试需 PostgreSQL 已启动且沙箱外执行。

**Goal:** 用整理后的「5 分钟起步任务拆解助手」提示词替换 `OpenAICompatSplitter` 的系统提示词，在**不改变** JSON 输出契约、service 二次校验与降级策略的前提下，提升模型产出的启动目标质量。

**Architecture:** 只改「携带用户输入 → 请求模型」这一条链路，落在 `backend/app/llm/openai_compat.py`：替换 `_SYSTEM_PROMPT` 全文，并把消息组装抽成纯函数 `_build_messages(task_text, date)`，使「用户目标原文被携带」可被单元测试钉住。`response_format={"type":"json_object"}`、`_parse_payload`、LRU 缓存、fallback、`services/`、`routers/`、`schemas/` 与前端一律不动。字段映射：`starter_step` ← 5 分钟起步目标（一句话），`steps` ← 0–1 条「启动说明」。

**Tech Stack:** FastAPI + httpx + pytest（`backend/.venv`，Python 3.12）；不新增依赖、不改启动方式。

**Spec:** [008 · LLM 提示词优化与整合](../specs/008-llm-prompt-tuning.md)（Task 1 创建；需求来源：用户 2026-11-08 提示词草稿 + Spec 002 的 F2 验收条件）

## Global Constraints

- 只允许改 `backend/app/llm/openai_compat.py` 与 `backend/tests/test_llm.py`；不改 `llm/base.py`、`llm/mock.py`、`llm/__init__.py`、`services/`、`routers/`、`schemas/`、前端。
- 保留 `response_format={"type":"json_object"}` 与 `_parse_payload` 的全部校验；不新增 JSON 字段，不改 `SplitResult`。
- 沿用现有边界：`starter_step` 硬上限 60 字符（`task_service.MAX_STARTER_CHARS`）、`steps` 上限 3 条（`MAX_STEPS`）；提示词要求 starter ≤40 字符、steps 0–1 条，留出安全余量。
- 不新增依赖、不改启动方式、不放宽 `tests/test_architecture.py` 棘轮；不新增第二套 Prompt 来源（配置文件 / 运行时加载一律不做），提示词仍以常量形式内联在 `openai_compat.py`。
- 采用**完整版**提示词（质量优先；结果按「任务文本\|日期」缓存、调用频次低，token 成本可接受）。用户提供的「精简版」不写入代码，只在 Spec §2 作为备选记录：若日后要省 token，可整体替换 `_SYSTEM_PROMPT` 文本，不动任何结构。
- 本改动不涉及六步切片中的 ①契约 / ②迁移 / ④router / ⑤前端，只落 ③ 的拆分器客户端；因此只跑后端测试与手工冒烟。
- 每个任务独立 commit；未跑过验证命令不得声明完成。

## Review Focus

1. 用户目标含换行、引号、中英文混排 → user 消息必须原样携带，不得改写、截断或转义：Task 2 `test_build_messages_preserves_raw_goal`。
2. 原目标本身 5 分钟内可完成 → 模型返回 `steps: []` 必须被现有校验接受、不触发 fallback：Task 2 `test_prompt_shaped_payload_passes_normalization`（含空数组分支）。
3. 模型 `starter_step` 为空或超过 60 字符 → 仍按既有路径判不合规并降级，不得返回假成功：Task 2 `test_prompt_shaped_payload_passes_normalization` 钉住 40 字样例通过、60 字边界不越界；提示词文本断言钉住长度约束存在。
4. 模型输出缺字段 / 类型错 → `_parse_payload` 抛 `ValueError` → fallback：既有 `test_parse_rejects_string_steps`、`test_parse_rejects_non_string_step_item` 保持通过，Task 2 不得修改解析逻辑。

---

### Task 1: 落地 Spec 008（本改动的主记录）

**Files:**
- Create: `docs/specs/008-llm-prompt-tuning.md`

**Interfaces:**
- Consumes: `docs/spec-template.md` 的八节结构；本计划 Goal / Global Constraints / Review Focus。
- Produces: Spec 008 §1–§7（§8 留空待 Task 3 回填），后续任务与复审以它为准。

- [ ] **Step 1: 从模板复制并填写**

复制 `docs/spec-template.md` 到 `docs/specs/008-llm-prompt-tuning.md`，填写 §1–§7：

- §1 背景与目标：现有 `_SYSTEM_PROMPT` 只要求「一个极低门槛的启动步骤 + 不超过 5 个步骤」，未约束「只负责启动、不要求完成」等口径，模型容易把原任务原样搬进 starter；本次用用户给定的提示词替换，只改提示词与 user 消息组装。
- §2 范围与非目标：范围仅 `backend/app/llm/openai_compat.py` 的 `_SYSTEM_PROMPT` / `_build_messages`；非目标：不改 JSON 契约与 `_parse_payload`、不改 LRU 与 fallback、不改 service 的 60 字 / 3 条校验、不改 Mock/base/router/schema、不改前端、不新增配置项、不加温度等请求参数、不引入提示词文件。
- §3 验收条件（逐条可测）：① user 消息原样携带用户目标与日期；② 系统提示词包含角色、最高优先级「禁止强行拆分」、5 条拆解原则、正反示例、只输出一个 JSON 对象的字段约束、starter ≤40 字符 / 硬上限 60；③ 符合新提示词的两种产物（`steps: []` 与单条「启动说明」）都能通过 `_parse_payload` 与 `_normalize_split`；④ 既有 6 条 `test_llm.py` 用例与架构棘轮继续通过。
- §4 owner 表：`backend/app/llm/openai_compat.py`（提示词与消息组装 owner，改文本与抽函数）/ `backend/tests/test_llm.py`（测试）。
- §5 实现步骤：链接本计划，按 Task 2 → Task 3 顺序；注明不重走六步流水线的原因（无契约 / 迁移 / 接口 / 前端变化）。
- §6 兼容性：无 API、无表结构、无返回字段变化；同一进程内 LRU 可能命中旧提示词的缓存结果，重启即失效，属运行边界不属契约变更。
- §7 测试场景与验证命令：直接引用本计划 Task 2 的三个测试名与 Task 3 的命令。
- 末尾补「结构性变更五问」四行简答：只改 llm 客户端、owner 在 `openai_compat.py`、无平行写入 / 重复状态、不影响接口、需 `test_llm.py` + 架构棘轮 + 全量后端测试继续通过。

- [ ] **Step 2: Commit**

```bash
git add docs/specs/008-llm-prompt-tuning.md
git commit -m "docs: add spec 008 for llm prompt tuning"
```

### Task 2: 提示词替换与消息组装可测化

**Files:**
- Modify: `backend/app/llm/openai_compat.py:14-18`（替换 `_SYSTEM_PROMPT`）、`backend/app/llm/openai_compat.py:80-93`（新增 `_build_messages` 并在 `_call_llm` 中使用）
- Test: `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: 既有 `_parse_payload(data: object) -> tuple[str, list[str]]`、`_CACHE`、`MockSplitter` 兜底（均不修改）。
- Produces: `_build_messages(task_text: str, date: str) -> list[dict[str, str]]`，返回长度 2、`roles == ["system", "user"]` 的消息列表；`_SYSTEM_PROMPT: str` 为下文 Step 3 的全文。

- [ ] **Step 1: 写三个失败测试**（追加到 `backend/tests/test_llm.py` 末尾）

```python
def test_build_messages_preserves_raw_goal():
    goal = "复习三角函数\n附带 3 道错题"
    messages = _build_messages(goal, "2026-11-08")

    assert [m["role"] for m in messages] == ["system", "user"]
    assert goal in messages[1]["content"]
    assert "2026-11-08" in messages[1]["content"]


def test_system_prompt_encodes_starter_rules():
    prompt = _SYSTEM_PROMPT

    assert "5 分钟起步任务拆解助手" in prompt
    assert "禁止强行拆分" in prompt
    assert "只负责启动" in prompt
    assert "粗糙" in prompt
    assert "只输出一个 JSON 对象" in prompt
    assert "40 个字符" in prompt
    assert "60 字符" in prompt


def test_prompt_shaped_payload_passes_normalization():
    from app.services.task_service import _normalize_split

    # 原目标本身 5 分钟内可完成：steps 为空数组
    starter, steps = _parse_payload(
        {"starter_step": "打开单词本，读第 1 页", "steps": []}
    )
    normalized = _normalize_split(
        SplitResult(starter_step=starter, steps=steps, source="llm")
    )
    assert normalized is not None and normalized.steps == []

    # 正常拆分：steps 只含一条启动说明
    starter, steps = _parse_payload(
        {
            "starter_step": "打开文档，写下 5 条与主题相关的零散想法，不梳理逻辑",
            "steps": ["启动说明：先写下零散想法能降低开始门槛"],
        }
    )
    normalized = _normalize_split(
        SplitResult(starter_step=starter, steps=steps, source="llm")
    )
    assert normalized is not None and normalized.steps == steps
```

导入行改为：

```python
from app.llm.openai_compat import OpenAICompatSplitter, _SYSTEM_PROMPT, _build_messages, _parse_payload
```

- [ ] **Step 2: 跑测试确认 RED**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q`
Expected: FAIL —— `ImportError: cannot import name '_build_messages'`（或 `_SYSTEM_PROMPT` 断言失败），共 3 条失败。

- [ ] **Step 3: 实现**

`backend/app/llm/openai_compat.py` 中，先把 `_SYSTEM_PROMPT` 整段替换为下面全文（逐字复制；不要追加其他规则，不要改成多文件加载）：

```python
_SYSTEM_PROMPT = (
    "你是「5 分钟起步任务拆解助手」。\n"
    "\n"
    "核心理念：行动先于态度，行动触发动力——用来破除拖延与完美主义带来的启动障碍。"
    "你的任务不是把任务平均拆成多段，而是产出一个能立刻上手、启动门槛极低的 5 分钟专注行动目标。\n"
    "\n"
    "最高优先级规则：如果用户的学习目标本身 5 分钟内就能做完，禁止强行拆分，"
    "直接把原目标作为 starter_step 返回，steps 返回空数组。\n"
    "\n"
    "拆解原则（必须全部遵守）：\n"
    "1. 只负责启动：不要求在 5 分钟内完成原任务，只帮用户迈出第一步、进入学习状态；"
    "哪怕只做一点点、粗糙一点也完全可以接受。\n"
    "2. 降低心理门槛：任务描述具体、可落地，不需要提前准备大量东西，用户看完马上就能开始；"
    "不写宽泛、抽象的指令。\n"
    "3. 方向匹配：与原学习目标强相关，是原任务的前置起步动作，不能跑偏成无关任务。\n"
    "4. 结果导向是「开始」：重点是开始而不是做完，允许 5 分钟后随时停下；"
    "启动之后大脑常会自然进入专注、心流状态继续学下去。\n"
    "5. 禁止要求完美：不要求产出高质量成果，允许粗糙、半成品、草稿、零散记录。\n"
    "\n"
    "反面示例（禁止模仿）：\n"
    "- 目标「写完一篇论文」→ 起步目标「写完论文」（原任务太大，5 分钟做不完）\n"
    "- 目标「学 Python 爬虫」→ 起步目标「掌握爬虫全套原理」（太抽象，无法立刻行动）\n"
    "正面示例：\n"
    "- 目标「写论文」→ 起步目标「打开文档，随便写下 5 条与主题相关的零散想法，不梳理逻辑、不润色」\n"
    "- 目标「减肥健身」→ 起步目标「原地开合跳 5 分钟」\n"
    "\n"
    "输出要求：只输出一个 JSON 对象，不要输出 JSON 以外的任何文字或 markdown：\n"
    '{"starter_step": "...", "steps": ["..."]}\n'
    "字段约束：\n"
    "- starter_step：一句话，清晰、简短、可立刻执行，不超过 40 个字符（含标点）；"
    "硬性上限 60 字符，超出视为无效。不要以「5分钟起步目标」之类标签开头。\n"
    "- steps：0 到 1 条。仅放一句以「启动说明：」开头的解释，说明这个 5 分钟动作为什么能帮你启动"
    "（贴合「行动先于完美」）；确无补充时返回空数组 []。\n"
    "- 只输出 starter_step 与 steps 两个字段，不要增加其他字段。"
)
```

再在 `_parse_payload` 之后、类定义之前新增消息组装函数：

```python
def _build_messages(task_text: str, date: str) -> list[dict[str, str]]:
    """组装请求消息：system 为提示词，user 原样携带日期与用户目标。"""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"日期：{date}\n学习目标：{task_text}"},
    ]
```

最后把 `_call_llm` 里手写的 `messages` 列表替换为：

```python
"messages": _build_messages(task_text, date),
```

其余（`response_format`、`raise_for_status`、`json.loads` + `_parse_payload`、`SplitResult(source="llm")`）不动。

- [ ] **Step 4: 跑测试确认 GREEN**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_llm.py -q`
Expected: PASS —— 9 passed（既有 6 条 + 新增 3 条）。

- [ ] **Step 5: 架构棘轮**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_architecture.py -q`
Expected: PASS（未改依赖方向、未在服务端引入 `datetime.now()`）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/openai_compat.py backend/tests/test_llm.py
git commit -m "feat(backend): tune llm starter prompt for 5-minute kickoff"
```

### Task 3: 全量验证、真实模型冒烟与 Spec 回填

**Files:**
- Modify: `docs/specs/008-llm-prompt-tuning.md`（§8）

**Interfaces:**
- Consumes: Task 2 的 `_build_messages` / `_SYSTEM_PROMPT`；既有 `POST /api/tasks/{id}/analyze`。
- Produces: Spec 008 §8 的执行结果、未验证项与遗留问题。

- [ ] **Step 1: 后端全量测试（需 PostgreSQL 已启动 + 沙箱外执行）**

按 AGENTS.md：先确认 PostgreSQL 已启（WMI 方式启动 `D:\Javatools\pg-data`），再：

Run: `cd backend; .venv\Scripts\python.exe -m pytest -q`
Expected: 全部 passed，数量 = 改动前全量 + 3；无任何用例改写成放宽断言。

- [ ] **Step 2: 真实模型手工冒烟（可选）**

前提：有可用的 `LLM_API_KEY`。**不改 `.env`**，仅在启动进程时用环境变量覆盖：

```powershell
$env:LLM_PROVIDER="openai"; $env:LLM_API_KEY="<key>"; $env:LLM_BASE_URL="https://api.deepseek.com/v1"; $env:LLM_MODEL="deepseek-chat"
cd backend; .venv\Scripts\python.exe -m app.main
```

在首页分别输入「写一篇论文」与「读 10 页书」点「分析」，检查：starter 是可在 5 分钟内动手的具体动作（前者不得是「写完论文」）；有解释时 `steps[0]` 以「启动说明：」开头；`source` 为 `llm`。若无 key，跳过并在 §8 记为未验证项。

- [ ] **Step 3: 回填 Spec 008 §8**

写清：跑过的命令与结果（区分「测试已编写」与「测试已运行通过」）；真实模型冒烟是否执行；未验证项（例如无 key 未验证真实模型质量、LRU 同进程旧缓存需重启失效）；遗留问题（如提示词长度约束为软约束，最终仍由 service 的 60 字校验兜底）。

- [ ] **Step 4: Commit**

```bash
git add docs/specs/008-llm-prompt-tuning.md
git commit -m "docs: record spec 008 execution results"
```
