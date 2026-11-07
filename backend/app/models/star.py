from datetime import date

from sqlalchemy import Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Star(Base):
    """一天一颗星：同账号同一归属日唯一，多场有效会话累计到同一行。"""

    __tablename__ = "stars"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_stars_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # 归属日 = 会话 started_at 的 Asia/Shanghai 自然日
    date: Mapped[date] = mapped_column(Date)
    # 当天有效累计秒数 // 60
    minutes: Mapped[int] = mapped_column(default=0)
    # 1–3，只升不降（有行的日期恒 ≥1）
    level: Mapped[int] = mapped_column(default=0)
