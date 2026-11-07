from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Letter(Base):
    __tablename__ = "letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id = 收件人；sender_id = 发件人（既有历史行可空）
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    content: Mapped[str] = mapped_column(Text)
    # delivered | undelivered（被拒收的发出记录）
    status: Mapped[str] = mapped_column(
        String(20), default="delivered", server_default=text("'delivered'")
    )
    # 投递时收件人正在学习中
    focused_delivery: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    favorited: Mapped[bool] = mapped_column(Boolean, default=False)
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
