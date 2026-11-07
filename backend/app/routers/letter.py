from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.deps import get_current_user_id
from app.models.letter import Letter
from app.schemas.letter import (
    DismissResponse,
    FavoriteResponse,
    HistoryResponse,
    InboxResponse,
    LetterOut,
    LetterSend,
    LetterSendResult,
    OutboxLetter,
    OutboxResponse,
)
from app.services import letter_service, user_service

router = APIRouter(prefix="/api/letters", tags=["letters"])


def _letter_out(letter: Letter, sender_name: str | None = None) -> LetterOut:
    """ORM 行 → 契约；sender_name 由收件人侧批量查账号名拼装。"""
    return LetterOut(
        id=letter.id,
        session_id=letter.session_id,
        content=letter.content,
        favorited=letter.favorited,
        handled=letter.handled,
        status=letter.status,
        focused_delivery=letter.focused_delivery,
        sender_name=sender_name,
        expired_at=letter.expired_at,
        created_at=letter.created_at,
    )


async def _letters_out(db: AsyncSession, letters: list[Letter]) -> list[LetterOut]:
    names = await user_service.get_names(db, [letter.sender_id for letter in letters])
    return [_letter_out(letter, names.get(letter.sender_id)) for letter in letters]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "LETTER_NOT_FOUND", "message": "信件不存在"}
    )


@router.get("/inbox", response_model=InboxResponse)
async def inbox(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> InboxResponse:
    """未处理且未过期的信件列表（懒失效），最多 3 封。"""
    letters = await letter_service.get_inbox(db, user_id, clock)
    return InboxResponse(
        letters=await _letters_out(db, letters),
        server_time=clock.now().isoformat(),
    )


@router.get("/history", response_model=HistoryResponse)
async def history(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> HistoryResponse:
    """历史信箱：只含已收藏的已投递信，返回前懒清理至 100 条。"""
    letters = await letter_service.get_history(db, user_id)
    return HistoryResponse(
        letters=await _letters_out(db, letters),
        server_time=clock.now().isoformat(),
    )


@router.get("/outbox", response_model=OutboxResponse)
async def outbox(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> OutboxResponse:
    """发出记录：本人投出的已投递与未送达信件，按时间倒序。"""
    letters = await letter_service.get_outbox(db, user_id)
    names = await user_service.get_names(db, [letter.user_id for letter in letters])
    return OutboxResponse(
        letters=[
            OutboxLetter(
                id=letter.id,
                recipient_name=names.get(letter.user_id),
                content=letter.content,
                status=letter.status,
                created_at=letter.created_at,
            )
            for letter in letters
        ],
        server_time=clock.now().isoformat(),
    )


@router.post("", response_model=LetterSendResult)
async def send_letter(
    body: LetterSend,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> LetterSendResult:
    """每场有效学习 1 次投递机会；拒收/收件人不存在不消耗机会。"""
    try:
        result, letter_id = await letter_service.send(
            db, user_id, body.session_id, body.recipient_name, clock
        )
    except letter_service.SessionNotValid:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SESSION_NOT_VALID",
                "message": "只有已结束的有效学习才能投递",
            },
        )
    except letter_service.ContentTooLong:
        raise HTTPException(
            status_code=422,
            detail={"code": "CONTENT_TOO_LONG", "message": "信件正文不能超过 200 字"},
        )
    return LetterSendResult(
        result=result, letter_id=letter_id, server_time=clock.now().isoformat()
    )


@router.post("/{letter_id}/favorite", response_model=FavoriteResponse)
async def favorite(
    letter_id: int,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> FavoriteResponse:
    """收藏信件，幂等；只能操作本人未过期、已投递的信件。"""
    try:
        letter = await letter_service.favorite(db, letter_id, user_id, clock)
    except letter_service.LetterExpired:
        raise HTTPException(
            status_code=409,
            detail={"code": "LETTER_EXPIRED", "message": "这封信已经过了一天"},
        )
    if letter is None:
        raise _not_found()
    names = await user_service.get_names(db, [letter.sender_id])
    return FavoriteResponse(
        letter=_letter_out(letter, names.get(letter.sender_id)),
        server_time=clock.now().isoformat(),
    )


@router.post("/{letter_id}/dismiss", response_model=DismissResponse)
async def dismiss(
    letter_id: int,
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> DismissResponse:
    """放弃信件：置已处理、不进历史；幂等，过期 409。"""
    try:
        letter = await letter_service.dismiss(db, letter_id, user_id, clock)
    except letter_service.LetterExpired:
        raise HTTPException(
            status_code=409,
            detail={"code": "LETTER_EXPIRED", "message": "这封信已经过了一天"},
        )
    if letter is None:
        raise _not_found()
    names = await user_service.get_names(db, [letter.sender_id])
    return DismissResponse(
        letter=_letter_out(letter, names.get(letter.sender_id)),
        server_time=clock.now().isoformat(),
    )


@router.delete("/{letter_id}", status_code=204)
async def delete_letter(
    letter_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """删除历史信箱中的收藏信；非本人 / 未收藏 / 未送达统一 404。"""
    deleted = await letter_service.delete_favorited(db, letter_id, user_id)
    if not deleted:
        raise _not_found()
    return Response(status_code=204)
