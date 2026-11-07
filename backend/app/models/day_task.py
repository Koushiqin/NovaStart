from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DayTask(Base):
    __tablename__ = "day_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    raw_text: Mapped[str] = mapped_column(Text)
    # 当前采用版（学生可编辑）；草稿为 "" / []
    starter_step: Mapped[str] = mapped_column(String(200))
    steps: Mapped[list] = mapped_column(JSONB)
    # 模型原始版；未分析为 NULL
    origin_starter_step: Mapped[str | None] = mapped_column(String(200))
    origin_steps: Mapped[list | None] = mapped_column(JSONB)
    # 分析时的标题；沿用它判定「是否分析过」与「改标题后可重新分析」
    analyzed_text: Mapped[str | None] = mapped_column(Text)
    # 拆分来源：llm | mock | fallback；未分析为 NULL
    split_source: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
