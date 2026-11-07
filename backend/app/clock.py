from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class Clock:
    """服务端时间唯一真相源。

    所有需要"当前时间"的判定都必须走这里，客户端时间一律不可信。
    偏移量只保存在实例字段上，不做模块级可变状态，避免 uvicorn --reload 下被重复加载重置。
    """

    def __init__(self, offset_seconds: int = 0) -> None:
        self.offset_seconds = offset_seconds

    def now(self) -> datetime:
        """返回 Asia/Shanghai 时区的 tz-aware 当前时间。

        演示模式的时间偏移只在 timedelta 这一处入口生效。
        """
        return datetime.now(SHANGHAI_TZ) + timedelta(seconds=self.offset_seconds)

    def today(self) -> date:
        """返回 Asia/Shanghai 自然日。"""
        return self.now().date()


def get_clock() -> Clock:
    """FastAPI 依赖：按 settings 的演示偏移为每次请求构造时钟。

    偏移来自 DEMO_TIME_OFFSET_SECONDS（默认 0），只影响「当前时间」判定，
    不批量修改已落库的历史时间戳。
    """
    return Clock(offset_seconds=settings.demo_time_offset_seconds)
