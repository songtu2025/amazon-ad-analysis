from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.product import Product, ProductSalesSnapshot  # noqa: E402
from app.services.gerpgo_client import GerpgoClient, _looks_like_placeholder  # noqa: E402


API_PATH = "/operation/sts/salesAnalysis/page"
GROUP_BY_TYPE = "seller_sku"
PAGESIZE = 10
PAGE_DELAY_SECONDS = 5.2

FORBIDDEN_ACTION_KEYS = {
    "execute",
    "auto_execute",
    "execution_url",
    "execution_payload",
    "bid_adjustment",
    "new_bid",
    "pause_ad",
    "enable_ad",
    "negative_keyword",
    "create_keyword",
}


def fail(message: str, payload: dict[str, Any] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(1)


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def validate_settings() -> int:
    settings = get_settings()
    if settings.gerpgo_access_token and _looks_like_placeholder(settings.gerpgo_access_token):
        fail("GERPGO_ACCESS_TOKEN 仍是示例值")
    if settings.gerpgo_app_id and _looks_like_placeholder(settings.gerpgo_app_id):
        fail("GERPGO_APP_ID 仍是示例值")
    if settings.gerpgo_app_key and _looks_like_placeholder(settings.gerpgo_app_key):
        fail("GERPGO_APP_KEY 仍是示例值")
    if not settings.gerpgo_access_token and (not settings.gerpgo_app_id or not settings.gerpgo_app_key):
        fail("请先配置 GERPGO_APP_ID 和 GERPGO_APP_KEY，或设置 GERPGO_ACCESS_TOKEN")
    if not settings.market_ids:
        fail("GERPGO_MARKET_IDS 未配置")
    return settings.market_ids[0]


def default_date_range() -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=29)
    return start.isoformat(), end.isoformat()


def assert_no_auto_execution(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key)
            if normalized in FORBIDDEN_ACTION_KEYS:
                fail("销售表现响应包含疑似广告执行字段", {"field": normalized})
            assert_no_auto_execution(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_auto_execution(child)


def product_values_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    msku = clean_text(row.get("msku"))
    market_id = row.get("marketId")
    if not msku or not market_id:
        return None
    return {
        "asin": clean_text(row.get("asin")),
        "msku": msku,
        "sku": clean_text(row.get("sku")),
        "product_name": clean_text(row.get("productName")) or msku,
        "image_url": clean_text(row.get("imgUrl")),
        "brand": clean_text(row.get("brand") or row.get("amzBrand")),
        "category": clean_text(row.get("category")),
        "market_id": int(market_id),
    }


def snapshot_values_from_row(
    row: dict[str, Any],
    *,
    product_id: int,
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "market_id": int(row["marketId"]),
        "msku": clean_text(row.get("msku")),
        "period_start": period_start,
        "period_end": period_end,
        "units_ordered": to_int(row.get("unitsOrdered")),
        "orders": to_int(row.get("orders")),
        "sales": to_float(row.get("orderProductSales")),
        "sessions": to_int(row.get("sessions")),
        "order_cvr": to_float(row.get("orderCvr")),
        "ads_spend": to_float(row.get("adsSpend")),
        "ads_sales": to_float(row.get("adsSales")),
        "acos": to_float(row.get("acos")),
        "gross_profit": to_float(row.get("salesGrossProfit")),
        "net_profit": to_float(row.get("salesNetProfit")),
    }


def upsert_product_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    period_start: str,
    period_end: str,
) -> dict[str, int]:
    summary = {"created": 0, "updated": 0, "skipped": 0, "snapshots_created": 0, "snapshots_updated": 0}
    now = datetime.now()
    for row in rows:
        values = product_values_from_row(row)
        if values is None:
            summary["skipped"] += 1
            continue

        product = db.execute(
            select(Product).where(Product.market_id == values["market_id"], Product.msku == values["msku"]).limit(1)
        ).scalar_one_or_none()
        if product is None:
            product = Product(created_at=now, updated_at=now)
            db.add(product)
            summary["created"] += 1
        else:
            product.updated_at = now
            summary["updated"] += 1

        product.asin = values["asin"]
        product.msku = values["msku"]
        product.sku = values["sku"]
        product.product_name = values["product_name"]
        product.image_url = values["image_url"]
        product.brand = values["brand"]
        product.category = values["category"]
        product.market_id = values["market_id"]
        db.flush()

        snapshot_values = snapshot_values_from_row(
            row,
            product_id=product.id,
            period_start=period_start,
            period_end=period_end,
        )
        snapshot = db.execute(
            select(ProductSalesSnapshot)
            .where(
                ProductSalesSnapshot.market_id == snapshot_values["market_id"],
                ProductSalesSnapshot.msku == snapshot_values["msku"],
                ProductSalesSnapshot.period_start == period_start,
                ProductSalesSnapshot.period_end == period_end,
            )
            .limit(1)
        ).scalar_one_or_none()
        if snapshot is None:
            snapshot = ProductSalesSnapshot(created_at=now, updated_at=now)
            db.add(snapshot)
            summary["snapshots_created"] += 1
        else:
            snapshot.updated_at = now
            summary["snapshots_updated"] += 1

        for key, value in snapshot_values.items():
            setattr(snapshot, key, value)

    db.commit()
    return summary


async def fetch_sales_performance_page(
    client: GerpgoClient,
    *,
    market_id: int,
    start_date: str,
    end_date: str,
    page: int,
) -> dict[str, Any]:
    payload = {
        "groupByType": GROUP_BY_TYPE,
        "showCurrencyType": "USD",
        "beginDate": start_date,
        "endDate": end_date,
        "page": page,
        "pagesize": PAGESIZE,
        "isShowTotal": False,
        "marketId": market_id,
    }
    raw = await client.post(API_PATH, payload)
    assert_no_auto_execution(raw)
    return raw


async def sync_products(max_pages: int | None) -> dict[str, Any]:
    init_db()
    market_id = validate_settings()
    start_date, end_date = default_date_range()
    client = GerpgoClient()
    total_summary = {"created": 0, "updated": 0, "skipped": 0, "snapshots_created": 0, "snapshots_updated": 0}
    pages_synced = 0
    rows_seen = 0
    reported_total: int | None = None

    page = 1
    while True:
        time.sleep(PAGE_DELAY_SECONDS)
        raw = await fetch_sales_performance_page(
            client,
            market_id=market_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
        )
        data = raw.get("data") or {}
        rows = data.get("rows") or []
        if not isinstance(rows, list):
            fail("销售表现响应 data.rows 不是列表", {"page": page})
        reported_total = int(data.get("total") or reported_total or 0)
        rows_seen += len(rows)
        if not rows:
            break

        with SessionLocal() as db:
            page_summary = upsert_product_rows(db, rows, period_start=start_date, period_end=end_date)
        for key in total_summary:
            total_summary[key] += page_summary[key]
        pages_synced += 1

        if max_pages is not None and pages_synced >= max_pages:
            break
        if reported_total and rows_seen >= reported_total:
            break
        if len(rows) < PAGESIZE:
            break
        page += 1

    return {
        "status": "success",
        "source": "sales_performance",
        "api_path": API_PATH,
        "request": {
            "marketId": market_id,
            "groupByType": GROUP_BY_TYPE,
            "pagesize": PAGESIZE,
            "beginDate": start_date,
            "endDate": end_date,
        },
        "page_delay_seconds": PAGE_DELAY_SECONDS,
        "pages_synced": pages_synced,
        "rows_seen": rows_seen,
        "reported_total": reported_total,
        "summary": total_summary,
        "written_fields": ["asin", "msku", "sku", "product_name", "image_url", "brand", "category", "market_id"],
        "snapshot_fields": [
            "unitsOrdered",
            "orders",
            "orderProductSales",
            "sessions",
            "orderCvr",
            "adsSpend",
            "adsSales",
            "acos",
            "salesGrossProfit",
            "salesNetProfit",
        ],
        "not_written_to_products": ["orderProductSales", "orders", "acos", "sessions", "adsSpend", "adsSales"],
        "checked": [
            "seller_sku_group_by",
            "page_delay_seconds",
            "market_id_msku_upsert",
            "product_identity_fields_only",
            "product_sales_snapshot_upsert",
            "no_auto_execution_fields",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从销售表现接口同步产品基础档案")
    parser.add_argument("--max-pages", type=int, default=None, help="最多同步页数；不传则同步到接口无更多数据")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.max_pages is not None and args.max_pages < 1:
        fail("--max-pages 必须大于等于 1")
    result = await sync_products(args.max_pages)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
