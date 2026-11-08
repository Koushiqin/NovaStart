import json
from collections import OrderedDict

import httpx

from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter

_CACHE_CAPACITY = 128

# 模块级 LRU 缓存：key 为 "任务文本|日期"，超出容量时淘汰最久未使用的条目
_CACHE: OrderedDict[str, SplitResult] = OrderedDict()

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


def _parse_payload(data: object) -> tuple[str, list[str]]:
    """校验模型输出结构；类型不符一律抛 ValueError，由 split() 走 fallback。"""
    if not isinstance(data, dict):
        raise ValueError("split payload must be an object")
    starter = data.get("starter_step")
    steps = data.get("steps")
    if (
        not isinstance(starter, str)
        or not isinstance(steps, list)
        or not all(isinstance(s, str) for s in steps)
    ):
        raise ValueError("split payload has invalid types")
    return starter, steps[:5]


def _build_messages(task_text: str, date: str) -> list[dict[str, str]]:
    """组装请求消息：system 为提示词，user 原样携带日期与用户目标。"""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"日期：{date}\n学习目标：{task_text}"},
    ]


class OpenAICompatSplitter:
    """OpenAI 兼容接口拆分器（DeepSeek 等均可接入）。

    超时或任何异常都降级到 MockSplitter（source="fallback"），保证接口永远可用。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 8.0,
        fallback: TaskSplitter | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._fallback = fallback or MockSplitter()

    async def split(self, task_text: str, date: str) -> SplitResult:
        key = f"{task_text}|{date}"
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]

        try:
            result = await self._call_llm(task_text, date)
        except Exception:
            # 网络异常、超时、响应格式不符等一律降级到 Mock 结果
            mock_result = await self._fallback.split(task_text, date)
            result = SplitResult(
                starter_step=mock_result.starter_step,
                steps=mock_result.steps,
                source="fallback",
            )

        _CACHE[key] = result
        _CACHE.move_to_end(key)
        if len(_CACHE) > _CACHE_CAPACITY:
            _CACHE.popitem(last=False)
        return result

    async def _call_llm(self, task_text: str, date: str) -> SplitResult:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": _build_messages(task_text, date),
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        starter, steps = _parse_payload(json.loads(content))
        return SplitResult(starter_step=starter, steps=steps, source="llm")
