from typing import Literal

from pydantic import BaseModel


class DayProgress(BaseModel):
    minutes: int
    level: int


class StreakInfo(BaseModel):
    """连续天数快照：与结算页 summary 的 streak 同源同结构。"""

    current: int
    longest: int
    was_reset: bool


class WallDay(BaseModel):
    date: str
    state: Literal["lit", "dim", "broken", "empty"]
    level: int | None


class ProgressSummary(BaseModel):
    today: DayProgress
    streak: StreakInfo
    wall: list[WallDay]
    server_time: str
