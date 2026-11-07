from pydantic import BaseModel


class TaskCreate(BaseModel):
    raw_text: str


class TaskCreated(BaseModel):
    task_id: int
    starter_step: str
    steps: list[str]
    source: str
    server_time: str
