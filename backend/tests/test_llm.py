import time

import pytest

from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter
from app.llm.openai_compat import OpenAICompatSplitter, _parse_payload


class CountingSplitter:
    """包一层计数器，记录内部 split 被真实调用的次数（用于验证缓存）。"""

    def __init__(self, inner: TaskSplitter) -> None:
        self._inner = inner
        self.calls = 0

    async def split(self, task_text: str, date: str) -> SplitResult:
        self.calls += 1
        return await self._inner.split(task_text, date)


async def test_mock_splitter_returns_mock_source_and_bounded_steps():
    result = await MockSplitter().split("读完第三章并做习题", "2026-11-06")

    assert result.source == "mock"
    assert result.starter_step  # starter_step 非空
    assert 1 <= len(result.steps) <= 5


async def test_cache_avoids_duplicate_calls():
    counting = CountingSplitter(MockSplitter())
    # 指向必然失败的地址，让每次真实调用都降级到计数器包裹的 Mock
    splitter = OpenAICompatSplitter(
        base_url="http://127.0.0.1:9",
        api_key="test-key",
        model="test-model",
        timeout=0.01,
        fallback=counting,
    )

    r1 = await splitter.split("缓存验证专用任务文本", "2026-11-06")
    r2 = await splitter.split("缓存验证专用任务文本", "2026-11-06")

    assert counting.calls == 1  # 第二次命中缓存，未再调用内部 splitter
    assert r1 == r2


async def test_openai_compat_timeout_falls_back_fast():
    splitter = OpenAICompatSplitter(
        base_url="http://127.0.0.1:9",  # 保留端口，必然连接失败/超时
        api_key="test-key",
        model="test-model",
        timeout=0.01,
    )

    start = time.monotonic()
    result = await splitter.split("超时会降级的任务", "2026-11-06")
    elapsed = time.monotonic() - start

    assert result.source == "fallback"
    assert elapsed < 2.0  # 证明走了超时降级而非同步等待


def test_parse_rejects_string_steps():
    with pytest.raises(ValueError):
        _parse_payload({"starter_step": "先打开资料", "steps": "打开资料"})


def test_parse_rejects_non_string_step_item():
    with pytest.raises(ValueError):
        _parse_payload({"starter_step": "先打开资料", "steps": ["打开资料", 1]})


def test_parse_truncates_to_five():
    starter, steps = _parse_payload(
        {"starter_step": "先打开资料", "steps": [f"步{i}" for i in range(7)]}
    )

    assert starter == "先打开资料"
    assert len(steps) == 5
