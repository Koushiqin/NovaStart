from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, get_clock
from app.db import get_session
from app.deps import get_current_user_id
from app.schemas.progress import DayProgress, ProgressSummary, StreakInfo, WallDay
from app.services import progress_service

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/summary", response_model=ProgressSummary)
async def progress_summary(
    user_id: int = Depends(get_current_user_id),
    clock: Clock = Depends(get_clock),
    db: AsyncSession = Depends(get_session),
) -> ProgressSummary:
    """首页进度：今天星星、连续天数与最近 30 天星星墙。只读，不做懒计算写入。"""
    snapshot = await progress_service.progress_snapshot(db, user_id, clock)
    return ProgressSummary(
        today=DayProgress(minutes=snapshot.today_minutes, level=snapshot.today_level),
        streak=StreakInfo(
            current=snapshot.streak_current,
            longest=snapshot.streak_longest,
            was_reset=snapshot.streak_was_reset,
        ),
        wall=[
            WallDay(date=cell.date.isoformat(), state=cell.state, level=cell.level)
            for cell in snapshot.wall
        ],
        server_time=clock.now().isoformat(),
    )
