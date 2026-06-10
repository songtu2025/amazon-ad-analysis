from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SpKeywordMetric(Base):
    __tablename__ = "sp_keyword_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    market_id: Mapped[int] = mapped_column(Integer, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(255))
    ad_group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ad_group_name: Mapped[str | None] = mapped_column(String(255))
    keyword_id: Mapped[str | None] = mapped_column(String(64), index=True)
    keyword_text: Mapped[str | None] = mapped_column(String(255), index=True)
    match_type: Mapped[str | None] = mapped_column(String(32))
    bid: Mapped[float | None] = mapped_column(Float)
    serving_status: Mapped[str | None] = mapped_column(String(128))
    data_date: Mapped[str | None] = mapped_column(String(20), index=True)
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
    ads_orders: Mapped[int | None] = mapped_column(Integer)
    ads_sales: Mapped[float | None] = mapped_column(Float)
    ctr: Mapped[float | None] = mapped_column(Float)
    cpc: Mapped[float | None] = mapped_column(Float)
    cvr: Mapped[float | None] = mapped_column(Float)
    cpa: Mapped[float | None] = mapped_column(Float)
    acos: Mapped[float | None] = mapped_column(Float)
    roas: Mapped[float | None] = mapped_column(Float)
    raw_json: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(DateTime)


class SpSearchTermMetric(Base):
    __tablename__ = "sp_search_term_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    market_id: Mapped[int] = mapped_column(Integer, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(255))
    ad_group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ad_group_name: Mapped[str | None] = mapped_column(String(255))
    keyword_id: Mapped[str | None] = mapped_column(String(64), index=True)
    keyword_text: Mapped[str | None] = mapped_column(String(255), index=True)
    search_term: Mapped[str | None] = mapped_column(String(255), index=True)
    match_type: Mapped[str | None] = mapped_column(String(32))
    data_date: Mapped[str | None] = mapped_column(String(20), index=True)
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
    ads_orders: Mapped[int | None] = mapped_column(Integer)
    ads_sales: Mapped[float | None] = mapped_column(Float)
    ctr: Mapped[float | None] = mapped_column(Float)
    cpc: Mapped[float | None] = mapped_column(Float)
    cvr: Mapped[float | None] = mapped_column(Float)
    acos: Mapped[float | None] = mapped_column(Float)
    roas: Mapped[float | None] = mapped_column(Float)
    raw_json: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(DateTime)
