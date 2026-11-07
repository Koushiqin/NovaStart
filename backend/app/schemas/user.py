from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UsersResponse(BaseModel):
    users: list[UserOut]
    server_time: str
