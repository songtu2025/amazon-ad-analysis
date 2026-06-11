import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core import database as database_module  # noqa: E402

database_module.engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
database_module.SessionLocal.configure(bind=database_module.engine)

from app.core.database import SessionLocal, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric  # noqa: E402
from app.models.product import Product  # noqa: E402


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


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def assert_success(response, label: str) -> Any:
    if response.status_code < 200 or response.status_code >= 300:
        fail(f"{label} 返回状态码 {response.status_code}：{response.text}")
    return response.json()


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(key_path)
            hits.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def add_product(db) -> Product:
    now = datetime.now()
    product = Product(
        asin="TASK039-ASIN",
        msku="TASK039-MSKU",
        sku="TASK039-SKU",
        product_name="TASK039 kids sunglasses",
        image_url=None,
        brand="TASK039",
        category="sunglasses",
        market_id=939,
        inventory_quantity=88,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_metric_pair(db, *, source_id: str, search_term: str, clicks: int, cost: float, orders: int, sales: float) -> None:
    common = {
        "source_id": source_id,
        "market_id": 939,
        "product_id": None,
        "campaign_id": "TASK039-CAMPAIGN-A",
        "campaign_name": "TASK039 Campaign A",
        "ad_group_id": "TASK039-GROUP-A",
        "ad_group_name": "TASK039 Group A",
        "keyword_id": f"{source_id}-KW",
        "keyword_text": "kids sunglasses",
        "match_type": "phrase",
        "data_date": "2026-06-01",
        "impressions": 500,
        "clicks": clicks,
        "cost": cost,
        "ads_orders": orders,
        "ads_sales": sales,
        "ctr": 0.1,
        "cpc": cost / clicks if clicks else 0,
        "cvr": orders / clicks if clicks else 0,
        "acos": cost / sales if sales else 0,
        "roas": sales / cost if cost else 0,
        "raw_json": "{}",
        "synced_at": datetime.now(),
    }
    db.add(SpKeywordMetric(**common, bid=0.8, serving_status="ENABLED", cpa=cost / orders if orders else 0))
    db.add(SpSearchTermMetric(**common, search_term=search_term))


def seed_metrics(db) -> None:
    seed_metric_pair(
        db,
        source_id="TASK039-SOURCE-A",
        search_term="kids sunglasses for boys",
        clicks=30,
        cost=12.0,
        orders=4,
        sales=80.0,
    )
    seed_metric_pair(
        db,
        source_id="TASK039-SOURCE-B",
        search_term="baby sunglasses 0-6 months",
        clicks=14,
        cost=16.0,
        orders=0,
        sales=0.0,
    )
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        product = add_product(db)
        seed_metrics(db)
        client = TestClient(app)

        binding = assert_success(
            client.put(
                f"/api/products/{product.id}/ad-binding",
                json={
                    "scope_type": "ad_group",
                    "scope_id": "TASK039-GROUP-A",
                    "scope_name": "TASK039 Group A",
                    "market_id": 939,
                    "created_by": "task039",
                    "period_start": "2026-06-01",
                    "period_end": "2026-06-01",
                    "evidence_note": "临时库验证产品维度复核清单",
                },
            ),
            "manual_ad_group_binding",
        )
        if binding.get("search_term_rows_updated") != 2:
            fail(f"人工归因后搜索词回填行数异常：{binding}")

        readiness = assert_success(
            client.get(
                "/api/search-terms/product-readiness",
                params={
                    "market_id": 939,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                },
            ),
            "product_readiness_after_binding",
        )
        if readiness.get("summary", {}).get("active_binding_count", 0) < 1:
            fail(f"缺少已确认归因规则：{readiness}")
        selected = next((row for row in readiness.get("products", []) if row.get("product_id") == product.id), None)
        if not selected or selected.get("search_term_rows", 0) < 2:
            fail(f"缺少已归因搜索词：{readiness}")

        analysis = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 939,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "min_spend": 10,
                    "target_acos": 0.35,
                },
            ),
            "product_dimension_group_summary",
        )
        groups = analysis.get("group_summary")
        if not isinstance(groups, list) or len(groups) < 2:
            fail(f"缺少产品维度归类组：{groups}")

        decision = assert_success(
            client.post(
                "/api/search-terms/group-decisions",
                json={
                    "group_key": next(str(group["group_key"]) for group in groups if group.get("performance_status") == "high_conversion"),
                    "decision_type": "observe",
                    "reason": "产品维度高转化词先观察并人工复核",
                    "observe_period": "7d",
                    "operator_name": "task039",
                    "market_id": 939,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "min_spend": 10,
                    "target_acos": 0.35,
                },
            ),
            "product_group_decision",
        )
        decision_payload = decision.get("decision") if isinstance(decision, dict) else None
        if not isinstance(decision_payload, dict) or decision_payload.get("product_id") != product.id:
            fail(f"组级人工记录未保存 product_id：{decision}")

        listed = assert_success(
            client.get(
                "/api/search-terms/group-decisions",
                params={
                    "market_id": 939,
                    "product_id": product.id,
                },
            ),
            "list_product_group_decisions",
        )
        if not isinstance(listed, list) or not listed:
            fail(f"缺少组级人工记录列表：{listed}")

        review_points = {
            "已确认归因规则": readiness.get("summary", {}).get("active_binding_count", 0) > 0,
            "已归因搜索词": selected.get("search_term_rows", 0) > 0,
            "产品维度归类组": len(groups) > 0,
            "组级人工记录": len(listed) > 0,
        }
        if not all(review_points.values()):
            fail(f"产品维度复核清单数据不完整：{review_points}")

        hits = find_forbidden_keys(
            {"binding": binding, "readiness": readiness, "analysis": analysis, "decision": decision, "listed": listed}
        )
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))

        print(
            json.dumps(
                {
                    "status": "success",
                    "product_id": product.id,
                    "review_points": review_points,
                    "group_count": len(groups),
                    "decision_count": len(listed),
                    "checked": [
                        "confirmed_attribution_rule",
                        "attributed_search_terms",
                        "product_dimension_group_summary",
                        "group_manual_decision_records",
                        "no_auto_execution_fields",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        app.dependency_overrides.clear()
        db.close()


if __name__ == "__main__":
    main()
