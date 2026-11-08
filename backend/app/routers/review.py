from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.deps import get_current_user_id
from app.schemas.review import RandomReviewResponse, ReviewItem
from app.services import review_service

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/random", response_model=RandomReviewResponse)
async def random_review(
    exclude_session_id: int = Query(..., description="本场会话 id，不参与抽取"),
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> RandomReviewResponse:
    """结算第④步：随机回顾本人过去的一条记录；池空时 item 为 null。"""
    picked = await review_service.random_past(db, user_id, exclude_session_id, clock)
    item = None
    if picked is not None:
        session, day, task_text, reflection = picked
        item = ReviewItem(
            session_id=session.id,
            date=day,
            task_text=task_text,
            reflection=reflection,
        )
    return RandomReviewResponse(item=item, server_time=clock.now().isoformat())
