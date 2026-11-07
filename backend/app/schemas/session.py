from typing import Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    task_id: int


class SessionCreated(BaseModel):
    session_id: int
    started_at: str
    server_time: str


class SessionEnded(BaseModel):
    """结束判定结果：settled=有效可进结算，discarded=无效完全丢弃。"""

    result: Literal["settled", "discarded"]
    duration_sec: int | None
    short_by_sec: int | None
    server_time: str


class SessionInfo(BaseModel):
    id: int
    started_at: str
    elapsed_sec: int
    status: str
    # 已结束（显式结束或 180 封顶）的时间；5 分钟里程碑只置 completed，不写此值
    ended_at: str | None = None
    # 本场任务当前采用版 starter，供专注页展示
    task_starter_step: str | None = None


class CurrentSession(BaseModel):
    session: SessionInfo | None
    server_time: str
    # 最长时长（秒）：专注页据此在封顶时刻立即补一次懒标记，不必等 15s 轮询
    session_max_seconds: int


class SessionSummary(BaseModel):
    """结算页唯一数据源：本次时长 + 归属日累计 + starter 原话复述。"""

    duration_sec: int
    today_total_sec: int
    task_text: str
    starter_text: str
    settle_step: int
    status: str
    # P6 填真实收信数；P5 填 star_level / streak。当前占位值不得改名。
    received_during_session: int = 0
    star_level: int | None = None
    streak: int | None = None
    server_time: str


class ReflectionCreate(BaseModel):
    """感想请求：允许空串/纯空格（空白 = 跳过，不落库）。"""

    content: str = Field(max_length=200)


class ReflectionContent(BaseModel):
    content: str


class ReflectionSaved(BaseModel):
    reflection: ReflectionContent | None
    settle_step: int
    server_time: str
