import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402
from app.models.product import Product, ProductGoal, ProductRule, ProductSalesSnapshot  # noqa: E402
from app.services.rule_service import generate_acos_worse_anomalies  # noqa: E402


FORBIDDEN_ACTION_KEYS = {
    "action",
    "actions",
    "ad_action",
    "execution",
    "execute",
    "operation",
    "bid_adjustment",
    "new_bid",
    "pause",
    "enable",
    "negative_keyword",
}


def _contains_forbidden_action_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                return True
            if _contains_forbidden_action_key(child):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_action_key(item) for item in value)
    return False


def _seed_data(db, market_id: int, period_start: date, period_end: date) -> int:
    now = datetime.now()
    product = Product(
        asin="SNAPSHOT-ASIN",
        msku="SNAPSHOT-MSKU",
        sku="SNAPSHOT-SKU",
        product_name="snapshot context product",
        image_url=None,
        brand="snapshot",
        category="snapshot",
        market_id=market_id,
        inventory_quantity=100,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.flush()

    db.add_all(
        [
            ProductGoal(product_id=product.id, goal_type="profit", note=None, created_at=now, updated_at=now),
            ProductRule(
                product_id=product.id,
                min_clicks=10,
                min_spend=10.0,
                min_orders=1,
                target_acos=0.3,
                target_cvr=0.1,
                max_cpc=2.0,
                inventory_guard=10,
                created_at=now,
                updated_at=now,
            ),
            ProductSalesSnapshot(
                product_id=product.id,
                market_id=market_id,
                msku=product.msku,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                units_ordered=9,
                orders=7,
                sales=321.45,
                sessions=456,
                order_cvr=0.0154,
                ads_spend=33.33,
                ads_sales=123.45,
                acos=0.27,
                gross_profit=88.8,
                net_profit=44.4,
                created_at=now,
                updated_at=now,
            ),
            SpKeywordMetric(
                source_id="SNAPSHOT-KW-ACOS",
                market_id=market_id,
                product_id=product.id,
                campaign_id="SNAPSHOT-CAMPAIGN",
                campaign_name="snapshot campaign",
                ad_group_id="SNAPSHOT-ADGROUP",
                ad_group_name="snapshot ad group",
                keyword_id="SNAPSHOT-KW",
                keyword_text="snapshot high acos",
                match_type="exact",
                bid=1.2,
                serving_status="ENABLED",
                data_date=period_end.isoformat(),
                impressions=1000,
                clicks=40,
                cost=80.0,
                ads_orders=2,
                ads_sales=100.0,
                ctr=0.04,
                cpc=2.0,
                cvr=0.05,
                cpa=40.0,
                acos=0.8,
                roas=1.25,
                raw_json="{}",
                synced_at=now,
            ),
        ]
    )
    db.commit()
    return product.id


def main() -> None:
    init_db()
    market_id = 1
    period_start = date(2026, 5, 12)
    period_end = date(2026, 6, 10)
    with SessionLocal() as db:
        product_id = _seed_data(db, market_id=market_id, period_start=period_start, period_end=period_end)
        result = generate_acos_worse_anomalies(
            db=db,
            market_id=market_id,
            start_date=period_start,
            end_date=period_end,
        )
        if result.get("events_created") != 1:
            raise SystemExit(f"status=failed reason=unexpected_event_count result={result}")

        event = db.execute(select(AnomalyEvent).where(AnomalyEvent.product_id == product_id)).scalar_one()
        evidence = json.loads(event.evidence_json)
        rule_result = json.loads(event.rule_result_json)

        snapshot = evidence.get("product_sales_snapshot")
        if not isinstance(snapshot, dict):
            raise SystemExit("status=failed reason=missing_product_sales_snapshot")
        rule_snapshot = rule_result.get("evidence", {}).get("product_sales_snapshot")
        if rule_snapshot != snapshot:
            raise SystemExit("status=failed reason=rule_result_snapshot_mismatch")

        expected = {
            "period_start": "2026-05-12",
            "period_end": "2026-06-10",
            "units_ordered": 9,
            "orders": 7,
            "sales": 321.45,
            "sessions": 456,
            "order_cvr": 0.0154,
            "ads_spend": 33.33,
            "ads_sales": 123.45,
            "acos": 0.27,
            "gross_profit": 88.8,
            "net_profit": 44.4,
        }
        mismatches = {key: snapshot.get(key) for key, value in expected.items() if snapshot.get(key) != value}
        if mismatches:
            raise SystemExit(f"status=failed reason=snapshot_field_mismatch values={mismatches}")

        if event.severity != "high":
            raise SystemExit(f"status=failed reason=severity_changed severity={event.severity}")
        if rule_result.get("suggestion_level") != "adoptable":
            raise SystemExit(f"status=failed reason=suggestion_level_changed rule_result={rule_result}")
        if _contains_forbidden_action_key(rule_result) or _contains_forbidden_action_key(evidence):
            raise SystemExit("status=failed reason=contains_auto_action_field")

        print(
            {
                "status": "success",
                "event_id": event.id,
                "product_id": product_id,
                "snapshot_sales": snapshot["sales"],
                "snapshot_orders": snapshot["orders"],
                "snapshot_sessions": snapshot["sessions"],
            }
        )


if __name__ == "__main__":
    main()
