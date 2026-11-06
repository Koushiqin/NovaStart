import re

from app.llm.base import SplitResult

# 用于切分步骤的中英文标点
_SPLIT_PATTERN = re.compile(r"[，。！？；、,.!?;\n]+")


class MockSplitter:
    """规则模板拆分器：不依赖任何外部服务，作为默认实现与降级兜底。"""

    async def split(self, task_text: str, date: str) -> SplitResult:
        # starter_step 固定为最小启动动作，降低开始门槛
        starter_step = "打开资料，只看第 1 段"
        # 按标点把任务文本切成最多 5 段
        parts = [p.strip() for p in _SPLIT_PATTERN.split(task_text) if p.strip()]
        steps = parts[:5] if parts else [task_text.strip() or "开始任务"]
        return SplitResult(starter_step=starter_step, steps=steps, source="mock")
