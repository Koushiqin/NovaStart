from pydantic import BaseModel


class SessionCreate(BaseModel):
    user_id: int
    task_id: int


class SessionCreated(BaseModel):
    session_id: int
    started_at: str
    server_time: str


class SessionInfo(BaseModel):
    id: int
    started_at: str
    elapsed_sec: int
    status: str


class CurrentSession(BaseModel):
    session: SessionInfo | None
    server_time: str
