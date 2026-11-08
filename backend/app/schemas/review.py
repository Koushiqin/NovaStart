from pydantic import BaseModel


class ReviewItem(BaseModel):
    """一条过去的记录：日期 + 任务原文 + 感想（无感想为 None）。"""

    session_id: int
    date: str
    task_text: str
    reflection: str | None


class RandomReviewResponse(BaseModel):
    item: ReviewItem | None
    server_time: str
