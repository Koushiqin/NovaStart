from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LetterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int | None
    content: str
    favorited: bool
    handled: bool
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
