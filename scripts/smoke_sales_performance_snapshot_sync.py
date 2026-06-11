from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import Base  # noqa: E402
from app.models.product import Product, ProductSalesSnapshot  # noqa: E402


SYNC_SCRIPT = PROJECT_ROOT / "scripts" / "sync_sales_performance_products.py"


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_sales_performance_products", SYNC_SCRIPT)
    if spec is None or spec.loader is None:
        fail("无法加载销售表现同步脚本")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_sync_module()
    if getattr(module, "API_PATH", None) != "/operation/sts/salesAnalysis/page":
        fail("同步脚本接口路径不正确", {"api_path": getattr(module, "API_PATH", None)})
    if getattr(module, "GROUP_BY_TYPE", None) != "seller_sku":
        fail("同步脚本必须使用 seller_sku 维度", {"group_by_type": getattr(module, "GROUP_BY_TYPE", None)})
    if int(getattr(module, "PAGESIZE", 0)) != 10:
        fail("同步脚本第一版 pagesize 必须为 10", {"pagesize": getattr(module, "PAGESIZE", None)})
    if float(getattr(module, "PAGE_DELAY_SECONDS", 0)) < 5.2:
        fail("同步脚本分页间隔必须不小于 5.2 秒", {"page_delay_seconds": getattr(module, "PAGE_DELAY_SECONDS", None)})

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    rows = [
        {
            "asin": "B057SNAP01",
            "msku": "TASK057-MSKU",
            "sku": "TASK057-SKU-A",
            "productName": "TASK057 Product A",
            "marketId": 1,
            "unitsOrdered": 3,
            "orders": 2,
            "orderProductSales": 45.67,
            "sessions": 120,
            "orderCvr": 0.0167,
            "adsSpend": 6.78,
            "adsSales": 31.23,
            "acos": 0.2171,
            "salesGrossProfit": 20.5,
            "salesNetProfit": 12.34,
        },
        {
            "asin": "B057SNAP02",
            "msku": "TASK057-MSKU",
            "sku": "TASK057-SKU-B",
            "productName": "TASK057 Product B",
            "marketId": 1,
            "unitsOrdered": 5,
            "orders": 4,
            "orderProductSales": 88.99,
            "sessions": 222,
            "orderCvr": 0.018,
            "adsSpend": 7.89,
            "adsSales": 44.56,
            "acos": 0.1771,
            "salesGrossProfit": 34.56,
            "salesNetProfit": 21.23,
        },
        {
            "asin": "B057SKIP00",
            "msku": "",
            "productName": "TASK057 skipped product",
            "marketId": 1,
        },
    ]

    with Session() as db:
        summary = module.upsert_product_rows(db, rows, period_start="2026-05-12", period_end="2026-06-10")
        products = db.execute(select(Product)).scalars().all()
        snapshots = db.execute(select(ProductSalesSnapshot)).scalars().all()

    expected_summary = {"created": 1, "updated": 1, "skipped": 1, "snapshots_created": 1, "snapshots_updated": 1}
    if summary != expected_summary:
        fail("upsert 快照汇总不符合预期", {"actual": summary, "expected": expected_summary})
    if len(products) != 1:
        fail("相同 market_id + msku 应只保留一个产品", {"product_count": len(products)})
    if len(snapshots) != 1:
        fail("相同 market_id + msku + period 应只保留一条快照", {"snapshot_count": len(snapshots)})

    product = products[0]
    snapshot = snapshots[0]
    expected_values = {
        "product_id": product.id,
        "market_id": 1,
        "msku": "TASK057-MSKU",
        "period_start": "2026-05-12",
        "period_end": "2026-06-10",
        "units_ordered": 5,
        "orders": 4,
        "sales": 88.99,
        "sessions": 222,
        "order_cvr": 0.018,
        "ads_spend": 7.89,
        "ads_sales": 44.56,
        "acos": 0.1771,
        "gross_profit": 34.56,
        "net_profit": 21.23,
    }
    actual_values = {field: getattr(snapshot, field) for field in expected_values}
    if actual_values != expected_values:
        fail("经营快照字段映射不符合预期", {"actual": actual_values, "expected": expected_values})

    product_columns = {column.name for column in Product.__table__.columns}
    leaked_columns = sorted({"orderProductSales", "orders", "acos", "adsSpend", "sessions"} & product_columns)
    if leaked_columns:
        fail("products 表不应包含销售表现指标字段", {"leaked_columns": leaked_columns})

    print(
        json.dumps(
            {
                "status": "success",
                "summary": summary,
                "checked": [
                    "sales_snapshot_model",
                    "market_id_msku_period_upsert",
                    "sales_snapshot_field_mapping",
                    "no_sales_metric_columns_in_products",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
