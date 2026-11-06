from pydantic import BaseModel, Field


class SettleAdvance(BaseModel):
    to_step: int = Field(ge=1, le=4)


class SettleState(BaseModel):
    session_id: int
    settle_step: int
    server_time: str
