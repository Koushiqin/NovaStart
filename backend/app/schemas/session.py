from typing import Literal

from pydantic import BaseModel


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
