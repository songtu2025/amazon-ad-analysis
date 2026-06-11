import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
SMOKE_DB_PATH = Path(
    os.environ.get(
        "TASK036_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task036_product_attribution_to_search_terms_{os.getpid()}.db"),
    )
)

SMOKE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if SMOKE_DB_PATH.exists():
    try:
        SMOKE_DB_PATH.unlink()
    except PermissionError:
        pass

os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB_PATH.as_posix()}"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

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
        asin="TASK036-ASIN",
        msku="TASK036-MSKU",
        sku="TASK036-SKU",
        product_name="TASK036 kids sunglasses",
        image_url=None,
        brand="TASK036",
        category="sunglasses",
        market_id=936,
        inventory_quantity=50,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_metrics(db) -> None:
    common = {
        "source_id": "TASK036-SOURCE-A",
        "market_id": 936,
        "product_id": None,
        "campaign_id": "TASK036-CAMPAIGN-A",
        "campaign_name": "TASK036 Campaign A",
        "ad_group_id": "TASK036-GROUP-A",
        "ad_group_name": "TASK036 Group A",
        "keyword_id": "TASK036-KW-A",
        "keyword_text": "kids sunglasses",
        "match_type": "phrase",
        "data_date": "2026-06-01",
        "impressions": 300,
        "clicks": 30,
        "cost": 12.0,
        "ads_orders": 4,
        "ads_sales": 80.0,
        "ctr": 0.1,
        "cpc": 0.4,
        "cvr": 0.1333,
        "acos": 0.15,
        "roas": 6.6667,
        "raw_json": "{}",
        "synced_at": datetime.now(),
    }
    db.add(
        SpKeywordMetric(
            **common,
            bid=0.8,
            serving_status="ENABLED",
            cpa=3.0,
        )
    )
    db.add(
        SpSearchTermMetric(
            **common,
            search_term="kids sunglasses for boys",
        )
    )
    db.commit()


def product_id_for_source(db, model, source_id: str) -> int | None:
    row = db.execute(select(model).where(model.source_id == source_id)).scalar_one()
    return row.product_id


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

        not_ready = assert_success(
            client.get(
                "/api/search-terms/product-readiness",
                params={
                    "market_id": 936,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                },
            ),
            "product_readiness_before_binding",
        )
        if not_ready.get("ready") is not False:
            fail(f"未确认归因前不应 ready：{not_ready}")

        binding = assert_success(
            client.put(
                f"/api/products/{product.id}/ad-binding",
                json={
                    "scope_type": "ad_group",
                    "scope_id": "TASK036-GROUP-A",
                    "scope_name": "TASK036 Group A",
                    "market_id": 936,
                    "created_by": "task036",
                    "period_start": "2026-06-01",
                    "period_end": "2026-06-01",
                    "evidence_note": "临时库验证人工确认归因后可查看产品维度搜索词分析",
                },
            ),
            "bind_ad_group_to_product",
        )
        if binding.get("search_term_rows_updated") != 1:
            fail(f"归因确认后搜索词回填行数异常：{binding}")
        if product_id_for_source(db, SpKeywordMetric, "TASK036-SOURCE-A") != product.id:
            fail("归因确认后关键词 product_id 未回填")
        if product_id_for_source(db, SpSearchTermMetric, "TASK036-SOURCE-A") != product.id:
            fail("归因确认后搜索词 product_id 未回填")

        ready = assert_success(
            client.get(
                "/api/search-terms/product-readiness",
                params={
                    "market_id": 936,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                },
            ),
            "product_readiness_after_binding",
        )
        if ready.get("ready") is not True or ready.get("status") != "ready":
            fail(f"确认归因后产品维度搜索词未 ready：{ready}")

        analysis = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 936,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "min_spend": 10,
                    "target_acos": 0.35,
                },
            ),
            "product_search_term_analysis",
        )
        if analysis.get("filters", {}).get("product_id") != product.id:
            fail(f"搜索词分析未带入 product_id：{analysis.get('filters')}")
        if not analysis.get("group_summary"):
            fail(f"产品维度搜索词 group_summary 为空：{analysis}")
        if not analysis.get("rows"):
            fail(f"产品维度搜索词明细为空：{analysis}")

        hits = find_forbidden_keys({"not_ready": not_ready, "binding": binding, "ready": ready, "analysis": analysis})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))

        print(
            json.dumps(
                {
                    "status": "success",
                    "product_id": product.id,
                    "binding": binding,
                    "readiness_summary": ready.get("summary"),
                    "group_count": len(analysis.get("group_summary") or []),
                    "checked": [
                        "manual_binding_updates_search_terms_product_id",
                        "product_readiness_ready_after_binding",
                        "product_filtered_group_summary",
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
