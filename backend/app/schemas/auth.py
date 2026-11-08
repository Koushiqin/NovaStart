from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=15)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=15)
    name: str = Field(default="", max_length=100)


class AuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserOut
    token: str
    server_time: str
