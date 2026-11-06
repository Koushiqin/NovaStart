import json
from collections import OrderedDict

import httpx

from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter

_CACHE_CAPACITY = 128

# 模块级 LRU 缓存：key 为 "任务文本|日期"，超出容量时淘汰最久未使用的条目
_CACHE: OrderedDict[str, SplitResult] = OrderedDict()

_SYSTEM_PROMPT = (
    "你是任务拆分助手。把用户给出的任务拆成：一个极低门槛的启动步骤 starter_step，"
    "以及不超过 5 个的步骤列表 steps。只输出 JSON："
    '{"starter_step": "...", "steps": ["...", "..."]}'
)


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
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"日期：{date}\n任务：{task_text}"},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        data = json.loads(content)
        steps = [str(s) for s in data["steps"]][:5]
        return SplitResult(starter_step=str(data["starter_step"]), steps=steps, source="llm")
