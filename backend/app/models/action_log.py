from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActionLog(Base):
    """幂等键：(session_id, action_type) 唯一，同一动作对同一会话只记录一次。"""

    __tablename__ = "action_logs"
    __table_args__ = (
        UniqueConstraint("session_id", "action_type", name="uq_action_logs_session_action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    action_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
