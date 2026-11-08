from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserOut
from app.services import auth_service
from app.services.auth_service import UsernameTakenError

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(user, token: str, clock: Clock) -> AuthResponse:
    return AuthResponse(
        user=UserOut.model_validate(user),
        token=token,
        server_time=clock.now().isoformat(),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> AuthResponse:
    result = await auth_service.login(db, body.username, clock)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": f"账号 {body.username} 不存在"},
        )
    user, token = result
    return _auth_response(user, token, clock)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> AuthResponse:
    try:
        user, token = await auth_service.register(db, body.username, body.name, clock)
    except UsernameTakenError:
        raise HTTPException(
            status_code=409,
            detail={"code": "USERNAME_TAKEN", "message": f"账号 {body.username} 已被注册"},
        )
    return _auth_response(user, token, clock)


@router.post("/logout", status_code=204)
async def logout(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_session),
) -> None:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            await auth_service.logout(db, token)
