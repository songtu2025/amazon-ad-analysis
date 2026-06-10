from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ManualDecision(Base):
    __tablename__ = "manual_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suggestion_id: Mapped[int] = mapped_column(Integer, index=True)
    decision_type: Mapped[str] = mapped_column(String(32), index=True)
    modified_action: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    observe_period: Mapped[str | None] = mapped_column(String(16))
    operator_name: Mapped[str | None] = mapped_column(String(64), index=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
