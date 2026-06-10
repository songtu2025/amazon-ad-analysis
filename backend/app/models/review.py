from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    manual_decision_id: Mapped[int] = mapped_column(Integer, index=True)
    review_period: Mapped[str] = mapped_column(String(16), index=True)
    before_metrics_json: Mapped[str | None] = mapped_column(Text)
    after_metrics_json: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime)
