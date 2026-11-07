from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.db import get_session
from app.deps import get_current_user_id
from app.schemas.letter import FavoriteResponse, HistoryResponse, InboxResponse, LetterOut
from app.services import letter_service

router = APIRouter(prefix="/api/letters", tags=["letters"])


@router.get("/inbox", response_model=InboxResponse)
async def inbox(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> InboxResponse:
    """未处理且未过期的信件列表（懒失效）。"""
    letters = await letter_service.get_inbox(db, user_id)
    return InboxResponse(
        letters=[LetterOut.model_validate(l) for l in letters],
        server_time=Clock().now().isoformat(),
    )


@router.get("/history", response_model=HistoryResponse)
async def history(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> HistoryResponse:
    """历史（已处理/已收藏）信件列表，返回前懒清理至 100 条。"""
    letters = await letter_service.get_history(db, user_id)
    return HistoryResponse(
        letters=[LetterOut.model_validate(l) for l in letters],
        server_time=Clock().now().isoformat(),
    )


@router.post("/{letter_id}/favorite", response_model=FavoriteResponse)
async def favorite(
    letter_id: int,
    _user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> FavoriteResponse:
    """收藏信件，幂等。"""
    letter = await letter_service.favorite(db, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail="letter not found")
    return FavoriteResponse(
        letter=LetterOut.model_validate(letter),
        server_time=Clock().now().isoformat(),
    )
