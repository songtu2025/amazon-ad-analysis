from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.products import list_products  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.product import Product, ProductSalesSnapshot  # noqa: E402


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


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1)


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def assert_success(response, label: str) -> Any:
    if response.status_code < 200 or response.status_code >= 300:
        fail(f"{label} 返回状态码 {response.status_code}", {"body": response.text})
    return response.json()


def main() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        now = datetime.now()
        product = Product(
            asin="B057API001",
            msku="TASK057-API-MSKU",
            sku="TASK057-API-SKU",
            product_name="TASK057 API Product",
            brand="RIVBOS",
            category="Sunglasses",
            market_id=1,
            inventory_quantity=None,
            created_at=now,
            updated_at=now,
        )
        db.add(product)
        db.flush()
        db.add(
            ProductSalesSnapshot(
                product_id=product.id,
                market_id=1,
                msku=product.msku,
                period_start="2026-05-12",
                period_end="2026-06-10",
                units_ordered=9,
                orders=7,
                sales=123.45,
                sessions=345,
                order_cvr=0.0203,
                ads_spend=11.22,
                ads_sales=66.77,
                acos=0.168,
                gross_profit=55.5,
                net_profit=33.3,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()

        rows = list_products(
            market_id=1,
            start_date=date.fromisoformat("2026-05-12"),
            end_date=date.fromisoformat("2026-06-10"),
            db=db,
        )

        row = next((item for item in rows if item["id"] == product.id), None)
        if row is None:
            fail("产品列表未返回测试产品")
        snapshot = row.get("sales_snapshot")
        if not snapshot:
            fail("产品列表未返回 sales_snapshot", {"row": row})
        expected = {
            "period_start": "2026-05-12",
            "period_end": "2026-06-10",
            "units_ordered": 9,
            "orders": 7,
            "sales": 123.45,
            "sessions": 345,
            "order_cvr": 0.0203,
            "ads_spend": 11.22,
            "ads_sales": 66.77,
            "acos": 0.168,
            "gross_profit": 55.5,
            "net_profit": 33.3,
        }
        actual = {key: snapshot.get(key) for key in expected}
        if actual != expected:
            fail("sales_snapshot 字段不符合预期", {"actual": actual, "expected": expected})
        forbidden = find_forbidden_keys(rows)
        if forbidden:
            fail("产品 API 返回自动执行广告动作字段", {"hits": forbidden})

        print(
            json.dumps(
                {
                    "status": "success",
                    "product_id": product.id,
                    "checked": [
                        "product_list_sales_snapshot",
                        "snapshot_period_match",
                        "snapshot_metric_fields",
                        "no_auto_execution_fields",
                    ],
                },
                ensure_ascii=False,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
