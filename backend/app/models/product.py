from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asin: Mapped[str | None] = mapped_column(String(64), index=True)
    msku: Mapped[str | None] = mapped_column(String(128), index=True)
    sku: Mapped[str | None] = mapped_column(String(128), index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), index=True)
    image_url: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(128), index=True)
    category: Mapped[str | None] = mapped_column(String(128), index=True)
    market_id: Mapped[int | None] = mapped_column(Integer, index=True)
    inventory_quantity: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductSalesSnapshot(Base):
    __tablename__ = "product_sales_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    market_id: Mapped[int] = mapped_column(Integer, index=True)
    msku: Mapped[str] = mapped_column(String(128), index=True)
    period_start: Mapped[str] = mapped_column(String(16), index=True)
    period_end: Mapped[str] = mapped_column(String(16), index=True)
    units_ordered: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    sales: Mapped[float] = mapped_column(Float, default=0.0)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    order_cvr: Mapped[float] = mapped_column(Float, default=0.0)
    ads_spend: Mapped[float] = mapped_column(Float, default=0.0)
    ads_sales: Mapped[float] = mapped_column(Float, default=0.0)
    acos: Mapped[float] = mapped_column(Float, default=0.0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0.0)
    net_profit: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductGoal(Base):
    __tablename__ = "product_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    goal_type: Mapped[str] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductRule(Base):
    __tablename__ = "product_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    min_clicks: Mapped[int | None] = mapped_column(Integer)
    min_spend: Mapped[float | None] = mapped_column(Float)
    min_orders: Mapped[int | None] = mapped_column(Integer)
    target_acos: Mapped[float | None] = mapped_column(Float)
    target_cvr: Mapped[float | None] = mapped_column(Float)
    max_cpc: Mapped[float | None] = mapped_column(Float)
    inventory_guard: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class ProductAdBinding(Base):
    __tablename__ = "product_ad_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int | None] = mapped_column(Integer, index=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_id: Mapped[str] = mapped_column(String(128), index=True)
    scope_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str | None] = mapped_column(String(128))
    evidence_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
