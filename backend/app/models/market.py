from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketInfo(Base):
    __tablename__ = "market_infos"

    market_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str | None] = mapped_column(String(255), index=True)
    country_code: Mapped[str | None] = mapped_column(String(32))
    raw_name: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(DateTime)
