from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
FRONTEND_API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.products import get_product, list_products  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric  # noqa: E402
from app.models.product import Product, ProductAdBinding  # noqa: E402


PERIOD_START = date.fromisoformat("2026-05-12")
PERIOD_END = date.fromisoformat("2026-06-10")
MARKET_ID = 760

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


def add_product(db, suffix: str) -> Product:
    now = datetime.now()
    product = Product(
        asin=f"B0TASK076{suffix}",
        msku=f"TASK076-{suffix}",
        sku=f"TASK076-SKU-{suffix}",
        product_name=f"TASK076 {suffix} Product",
        image_url=None,
        brand="RIVBOS",
        category="Smoke",
        market_id=MARKET_ID,
        inventory_quantity=None,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.flush()
    return product


def add_keyword_metric(db, product: Product) -> None:
    now = datetime.now()
    db.add(
        SpKeywordMetric(
            source_id="TASK076-SOURCE",
            market_id=MARKET_ID,
            product_id=product.id,
            campaign_id="TASK076-CAMPAIGN",
            campaign_name="TASK076 campaign",
            ad_group_id="TASK076-ADGROUP",
            ad_group_name="TASK076 ad group",
            keyword_id="TASK076-KW",
            keyword_text="task076 keyword",
            match_type="exact",
            data_date="2026-06-01",
            impressions=100,
            clicks=12,
            cost=15.0,
            bid=1.0,
            ads_orders=3,
            ads_sales=80.0,
            ctr=0.12,
            cpc=1.25,
            cvr=0.25,
            acos=0.1875,
            roas=5.3333,
            cpa=5.0,
            serving_status="ENABLED",
            raw_json="{}",
            synced_at=now,
        )
    )


def add_active_binding(db, product: Product) -> None:
    now = datetime.now()
    db.add(
        ProductAdBinding(
            market_id=MARKET_ID,
            product_id=product.id,
            scope_type="ad_group",
            scope_id="TASK076-BOUND-ADGROUP",
            scope_name="TASK076 bound ad group",
            status="active",
            created_by="smoke",
            evidence_json=json.dumps({"source": "TASK-076 smoke"}, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
    )


def row_by_id(rows: list[dict[str, Any]], product: Product) -> dict[str, Any]:
    row = next((item for item in rows if item.get("id") == product.id), None)
    if row is None:
        fail("产品列表未返回测试产品", {"product_id": product.id})
    return row


def assert_scope(row: dict[str, Any], expected_status: str, expected_eligible: bool) -> None:
    actual_status = row.get("ad_coverage_status")
    actual_eligible = row.get("is_ad_tuning_eligible")
    if actual_status != expected_status:
        fail("产品广告覆盖状态不正确", {"row": row, "expected_status": expected_status, "actual_status": actual_status})
    if actual_eligible is not expected_eligible:
        fail(
            "产品广告调优资格不正确",
            {"row": row, "expected_eligible": expected_eligible, "actual_eligible": actual_eligible},
        )


def assert_frontend_prefers_api_scope() -> list[str]:
    api_source = FRONTEND_API_PATH.read_text(encoding="utf-8")
    app_source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    checks = {
        "api_status_type": 'ad_coverage_status: "attributed" | "sp_unattributed" | "not_advertised"' in api_source,
        "api_eligible_type": "is_ad_tuning_eligible: boolean" in api_source,
        "frontend_status_prefers_api": "product.ad_coverage_status" in app_source,
        "frontend_eligible_prefers_api": "product.is_ad_tuning_eligible" in app_source,
        "frontend_fallback_kept": "productBindingCount > 0" in app_source and "hasProductSpMetrics(product)" in app_source,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail("前端未优先使用产品 API 对象状态：" + ", ".join(missing))
    return list(checks.keys())


def main() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        sales_only_product = add_product(db, "SALES")
        sp_unattributed_product = add_product(db, "SP")
        attributed_product = add_product(db, "BOUND")
        add_keyword_metric(db, sp_unattributed_product)
        add_active_binding(db, attributed_product)
        db.commit()

        rows = list_products(market_id=MARKET_ID, start_date=PERIOD_START, end_date=PERIOD_END, db=db)
        sales_row = row_by_id(rows, sales_only_product)
        sp_row = row_by_id(rows, sp_unattributed_product)
        attributed_row = row_by_id(rows, attributed_product)

        assert_scope(sales_row, "not_advertised", False)
        assert_scope(sp_row, "sp_unattributed", True)
        assert_scope(attributed_row, "attributed", True)

        detail = get_product(sales_only_product.id, start_date=PERIOD_START, end_date=PERIOD_END, db=db)
        assert_scope(detail, "not_advertised", False)

        forbidden_hits = find_forbidden_keys({"rows": rows, "detail": detail})
        if forbidden_hits:
            fail("产品 API 返回发现自动执行广告动作字段", {"hits": forbidden_hits})

        frontend_checks = assert_frontend_prefers_api_scope()
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "api_product_ad_coverage_status",
                        "api_product_ad_tuning_eligibility",
                        "list_products_scope_fields",
                        "get_product_scope_fields",
                        "frontend_prefers_api_scope",
                        "no_auto_execution_fields",
                    ],
                    "frontend_checks": frontend_checks,
                    "sample": {
                        "sales_only": {
                            "ad_coverage_status": sales_row["ad_coverage_status"],
                            "is_ad_tuning_eligible": sales_row["is_ad_tuning_eligible"],
                        },
                        "sp_unattributed": {
                            "ad_coverage_status": sp_row["ad_coverage_status"],
                            "is_ad_tuning_eligible": sp_row["is_ad_tuning_eligible"],
                        },
                        "attributed": {
                            "ad_coverage_status": attributed_row["ad_coverage_status"],
                            "is_ad_tuning_eligible": attributed_row["is_ad_tuning_eligible"],
                        },
                    },
                },
                ensure_ascii=False,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
