from app.config import Settings
from app.llm.base import SplitResult, TaskSplitter
from app.llm.mock import MockSplitter
from app.llm.openai_compat import OpenAICompatSplitter

__all__ = ["SplitResult", "TaskSplitter", "MockSplitter", "OpenAICompatSplitter", "get_splitter"]


def get_splitter(settings: Settings) -> TaskSplitter:
    """按配置选择拆分器：provider 为 mock 或未配置 api_key 时用 Mock，否则走 OpenAI 兼容接口。"""
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        return MockSplitter()
    return OpenAICompatSplitter(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )
