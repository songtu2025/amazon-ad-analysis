import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402
from app.models.product import Product, ProductGoal, ProductRule  # noqa: E402
from app.services.rule_service import (  # noqa: E402
    generate_acos_worse_anomalies,
    generate_clicks_no_orders_anomalies,
    generate_cvr_drop_anomalies,
    generate_impression_low_anomalies,
    generate_inventory_goal_conflict_anomalies,
    generate_search_terms_clicks_no_orders_anomalies,
    generate_spend_spike_anomalies,
)


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

REQUIRED_EVENT_FIELDS = {
    "anomaly_type",
    "severity",
    "object_type",
    "period_start",
    "period_end",
    "rule_result_json",
    "evidence_json",
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


def _seed_smoke_data(db, market_id: int, data_date: date) -> None:
    now = datetime.now()
    profit_product = Product(
        asin="SMOKE-ASIN-PROFIT",
        msku="SMOKE-MSKU-PROFIT",
        sku="SMOKE-SKU-PROFIT",
        product_name="smoke profit product",
        image_url=None,
        brand="smoke",
        category="smoke",
        market_id=market_id,
        inventory_quantity=100,
        created_at=now,
        updated_at=now,
    )
    scale_product = Product(
        asin="SMOKE-ASIN-SCALE",
        msku="SMOKE-MSKU-SCALE",
        sku="SMOKE-SKU-SCALE",
        product_name="smoke scale product",
        image_url=None,
        brand="smoke",
        category="smoke",
        market_id=market_id,
        inventory_quantity=5,
        created_at=now,
        updated_at=now,
    )
    db.add_all([profit_product, scale_product])
    db.flush()

    db.add_all(
        [
            ProductGoal(product_id=profit_product.id, goal_type="profit", note=None, created_at=now, updated_at=now),
            ProductGoal(product_id=scale_product.id, goal_type="scale", note=None, created_at=now, updated_at=now),
            ProductRule(
                product_id=profit_product.id,
                min_clicks=5,
                min_spend=5.0,
                min_orders=2,
                target_acos=0.3,
                target_cvr=0.2,
                max_cpc=1.0,
                inventory_guard=10,
                created_at=now,
                updated_at=now,
            ),
            ProductRule(
                product_id=scale_product.id,
                min_clicks=5,
                min_spend=5.0,
                min_orders=1,
                target_acos=0.5,
                target_cvr=0.1,
                max_cpc=1.0,
                inventory_guard=10,
                created_at=now,
                updated_at=now,
            ),
        ]
    )

    common = {
        "market_id": market_id,
        "campaign_id": "SMOKE-CAMPAIGN",
        "campaign_name": "smoke campaign",
        "ad_group_id": "SMOKE-ADGROUP",
        "ad_group_name": "smoke ad group",
        "match_type": "exact",
        "data_date": data_date.isoformat(),
        "raw_json": "{}",
        "synced_at": now,
    }
    db.add_all(
        [
            SpKeywordMetric(
                **common,
                source_id="SMOKE-KW-ACOS",
                product_id=profit_product.id,
                keyword_id="SMOKE-KW-ACOS",
                keyword_text="smoke high acos",
                bid=1.2,
                serving_status="ENABLED",
                impressions=200,
                clicks=10,
                cost=50.0,
                ads_orders=1,
                ads_sales=20.0,
                ctr=0.05,
                cpc=5.0,
                cvr=0.1,
                cpa=50.0,
                acos=2.5,
                roas=0.4,
            ),
            SpKeywordMetric(
                **common,
                source_id="SMOKE-KW-NO-ORDER",
                product_id=profit_product.id,
                keyword_id="SMOKE-KW-NO-ORDER",
                keyword_text="smoke no order",
                bid=0.8,
                serving_status="ENABLED",
                impressions=100,
                clicks=3,
                cost=3.0,
                ads_orders=0,
                ads_sales=0.0,
                ctr=0.03,
                cpc=1.0,
                cvr=0.0,
                cpa=None,
                acos=None,
                roas=None,
            ),
            SpKeywordMetric(
                **common,
                source_id="SMOKE-KW-LOW-IMP",
                product_id=scale_product.id,
                keyword_id="SMOKE-KW-LOW-IMP",
                keyword_text="smoke low impression",
                bid=0.8,
                serving_status="ENABLED",
                impressions=5,
                clicks=0,
                cost=0.0,
                ads_orders=0,
                ads_sales=0.0,
                ctr=0.0,
                cpc=None,
                cvr=0.0,
                cpa=None,
                acos=None,
                roas=None,
            ),
            SpSearchTermMetric(
                **common,
                source_id="SMOKE-ST-NO-ORDER",
                product_id=profit_product.id,
                keyword_id="SMOKE-KW-NO-ORDER",
                keyword_text="smoke no order",
                search_term="smoke bad query",
                impressions=90,
                clicks=3,
                cost=3.0,
                ads_orders=0,
                ads_sales=0.0,
                ctr=0.03,
                cpc=1.0,
                cvr=0.0,
                acos=None,
                roas=None,
            ),
        ]
    )
    db.commit()


def _assert_event_payload(event: AnomalyEvent) -> None:
    missing_fields = [
        field
        for field in REQUIRED_EVENT_FIELDS
        if getattr(event, field) is None or getattr(event, field) == ""
    ]
    if missing_fields:
        raise SystemExit(f"status=failed reason=missing_fields event_id={event.id} fields={missing_fields}")

    try:
        rule_result = json.loads(event.rule_result_json)
        evidence = json.loads(event.evidence_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"status=failed reason=invalid_json event_id={event.id} error={exc}") from exc

    if not isinstance(rule_result, dict) or not rule_result.get("matched_rules"):
        raise SystemExit(f"status=failed reason=missing_matched_rules event_id={event.id}")
    if not isinstance(evidence, dict) or not evidence:
        raise SystemExit(f"status=failed reason=missing_evidence event_id={event.id}")
    if _contains_forbidden_action_key(rule_result) or _contains_forbidden_action_key(evidence):
        raise SystemExit(f"status=failed reason=contains_auto_action_field event_id={event.id}")


def main() -> None:
    init_db()
    market_id = 1
    end_date = date.today()
    start_date = end_date - timedelta(days=13)
    with SessionLocal() as db:
        _seed_smoke_data(db, market_id=market_id, data_date=end_date)

        results = [
            generate_clicks_no_orders_anomalies(
                db=db,
                market_id=market_id,
                start_date=start_date,
                end_date=end_date,
                min_clicks=1,
                min_spend=1,
            ),
            generate_search_terms_clicks_no_orders_anomalies(
                db=db,
                market_id=market_id,
                start_date=start_date,
                end_date=end_date,
                min_clicks=1,
                min_spend=1,
            ),
            generate_acos_worse_anomalies(db=db, market_id=market_id, start_date=start_date, end_date=end_date),
            generate_spend_spike_anomalies(db=db, market_id=market_id, start_date=start_date, end_date=end_date),
            generate_cvr_drop_anomalies(db=db, market_id=market_id, start_date=start_date, end_date=end_date),
            generate_impression_low_anomalies(db=db, market_id=market_id, start_date=start_date, end_date=end_date),
            generate_inventory_goal_conflict_anomalies(
                db=db, market_id=market_id, start_date=start_date, end_date=end_date
            ),
        ]

        events = db.execute(
            select(AnomalyEvent).where(
                AnomalyEvent.market_id == market_id,
                AnomalyEvent.period_start == start_date.isoformat(),
                AnomalyEvent.period_end == end_date.isoformat(),
            )
        ).scalars().all()
        if not events:
            raise SystemExit("status=failed reason=no_anomaly_events_created")

        for event in events:
            _assert_event_payload(event)

        total_created = sum(int(result.get("events_created", 0)) for result in results)
        print(
            {
                "status": "success",
                "market_id": market_id,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "smoke_db": ":memory:",
                "events_created": total_created,
                "events_validated": len(events),
                "rules": results,
            }
        )


if __name__ == "__main__":
    main()
