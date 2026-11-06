from pydantic import BaseModel


class TaskCreate(BaseModel):
    user_id: int
    raw_text: str


class TaskCreated(BaseModel):
    task_id: int
    starter_step: str
    steps: list[str]
    source: str
    server_time: str
