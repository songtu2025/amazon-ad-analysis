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


class SearchTermCandidateDecision(Base):
    __tablename__ = "search_term_candidate_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(512), index=True)
    candidate_type: Mapped[str] = mapped_column(String(64), index=True)
    search_term: Mapped[str] = mapped_column(String(512), index=True)
    market_id: Mapped[int | None] = mapped_column(Integer, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    period_start: Mapped[str] = mapped_column(String(16), index=True)
    period_end: Mapped[str] = mapped_column(String(16), index=True)
    decision_type: Mapped[str] = mapped_column(String(32), index=True)
    modified_action: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    observe_period: Mapped[str | None] = mapped_column(String(16))
    operator_name: Mapped[str | None] = mapped_column(String(64), index=True)
    candidate_snapshot_json: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime)


class SearchTermGroupDecision(Base):
    __tablename__ = "search_term_group_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_key: Mapped[str] = mapped_column(String(256), index=True)
    group_label: Mapped[str] = mapped_column(String(256))
    market_id: Mapped[int | None] = mapped_column(Integer, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    semantic_category: Mapped[str] = mapped_column(String(64), index=True)
    performance_status: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[str] = mapped_column(String(16), index=True)
    period_end: Mapped[str] = mapped_column(String(16), index=True)
    decision_type: Mapped[str] = mapped_column(String(32), index=True)
    modified_action: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    observe_period: Mapped[str | None] = mapped_column(String(16))
    operator_name: Mapped[str | None] = mapped_column(String(64), index=True)
    group_snapshot_json: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
