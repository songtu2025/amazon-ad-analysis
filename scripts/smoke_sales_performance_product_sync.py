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
    if not SYNC_SCRIPT.exists():
        fail("缺少销售表现产品同步脚本", {"expected": str(SYNC_SCRIPT)})
    spec = importlib.util.spec_from_file_location("sync_sales_performance_products", SYNC_SCRIPT)
    if spec is None or spec.loader is None:
        fail("无法加载销售表现产品同步脚本")
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
            "asin": "B012345678",
            "msku": "TASK053-MSKU",
            "sku": "TASK053-SKU-A",
            "productName": "TASK053 Product A",
            "imgUrl": "https://example.test/a.jpg",
            "brand": "RIVBOS",
            "category": "Sunglasses",
            "marketId": 1,
            "orderProductSales": 999.99,
            "orders": 88,
            "acos": 0.12,
        },
        {
            "asin": "B012345679",
            "msku": "TASK053-MSKU",
            "sku": "TASK053-SKU-B",
            "productName": "TASK053 Product B",
            "imgUrl": "https://example.test/b.jpg",
            "brand": "RIVBOS",
            "category": "Kids Sunglasses",
            "marketId": 1,
            "orderProductSales": 1000.0,
            "orders": 99,
            "acos": 0.13,
        },
        {
            "asin": "B000000000",
            "msku": "",
            "sku": "NO-MSKU",
            "productName": "Skipped Product",
            "marketId": 1,
        },
    ]

    with Session() as db:
        summary = module.upsert_product_rows(db, rows, period_start="2026-05-12", period_end="2026-06-10")
        products = db.execute(select(Product)).scalars().all()
        snapshots = db.execute(select(ProductSalesSnapshot)).scalars().all()

    expected_summary = {"created": 1, "updated": 1, "skipped": 1, "snapshots_created": 1, "snapshots_updated": 1}
    if summary != expected_summary:
        fail("upsert 汇总不符合预期", {"summary": summary})
    if len(products) != 1:
        fail("相同 market_id + msku 应只保留一个产品", {"product_count": len(products)})
    if len(snapshots) != 1:
        fail("相同 market_id + msku + period 应只保留一个销售表现快照", {"snapshot_count": len(snapshots)})

    product = products[0]
    expected_values = {
        "asin": "B012345679",
        "msku": "TASK053-MSKU",
        "sku": "TASK053-SKU-B",
        "product_name": "TASK053 Product B",
        "image_url": "https://example.test/b.jpg",
        "brand": "RIVBOS",
        "category": "Kids Sunglasses",
        "market_id": 1,
    }
    actual_values = {field: getattr(product, field) for field in expected_values}
    if actual_values != expected_values:
        fail("产品基础字段映射不符合预期", {"actual": actual_values, "expected": expected_values})

    forbidden_metric_columns = {"orderProductSales", "orders", "acos", "adsSpend", "sessions"}
    product_columns = {column.name for column in Product.__table__.columns}
    leaked_columns = sorted(forbidden_metric_columns & product_columns)
    if leaked_columns:
        fail("products 表不应包含销售表现指标字段", {"leaked_columns": leaked_columns})

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "sales_performance_api_constants",
                    "page_delay_seconds",
                    "market_id_msku_upsert",
                    "product_identity_field_mapping",
                    "sales_snapshot_separate_table",
                    "skip_missing_msku",
                    "no_sales_metric_columns_in_products",
                ],
                "summary": summary,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
