from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class SplitResult:
    """任务拆分结果。source 标识来源：llm=真实模型，mock=规则模板，fallback=超时/异常降级。"""

    starter_step: str
    steps: list[str]
    source: Literal["llm", "mock", "fallback"]


class TaskSplitter(Protocol):
    """可插拔任务拆分器协议。"""

    async def split(self, task_text: str, date: str) -> SplitResult:
        """把任务文本拆成启动步骤 + 步骤列表。"""
        ...
