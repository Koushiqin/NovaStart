from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LetterStatus = Literal["delivered", "undelivered"]


class LetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int | None
    content: str
    favorited: bool
    handled: bool
    status: LetterStatus
    focused_delivery: bool
    # 发件人昵称；既有历史行无发件人，拼装后可空
    sender_name: str | None = None
    expired_at: datetime
    created_at: datetime


class InboxResponse(BaseModel):
    letters: list[LetterOut]
    server_time: str


class HistoryResponse(BaseModel):
    letters: list[LetterOut]
    server_time: str


class FavoriteResponse(BaseModel):
    letter: LetterOut
    server_time: str


class LetterSend(BaseModel):
    """投递请求：收件人填用户名或数字 ID，去空白后非空。"""

    session_id: int
    recipient_name: str = Field(max_length=50)

    @field_validator("recipient_name")
    @classmethod
    def _clean_recipient(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("收件人不能为空")
        return cleaned


class LetterSendResult(BaseModel):
    result: Literal["delivered", "rejected_full", "rejected_unknown", "already_sent"]
    letter_id: int | None
    server_time: str


class DismissResponse(BaseModel):
    letter: LetterOut
    server_time: str


class OutboxLetter(BaseModel):
    id: int
    recipient_name: str | None
    content: str
    status: LetterStatus
    created_at: datetime


class OutboxResponse(BaseModel):
    letters: list[OutboxLetter]
    server_time: str
