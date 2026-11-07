from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Streak(Base):
    """每账号一行：当前连续 / 历史最长 / 最后完成日。断签归零只在读侧呈现。"""

    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    current: Mapped[int] = mapped_column(default=0)
    longest: Mapped[int] = mapped_column(default=0)
    last_completed_date: Mapped[date | None] = mapped_column(Date)
    # 最近一次完成是否为断签后重开的一段
    was_reset: Mapped[bool] = mapped_column(default=False)
