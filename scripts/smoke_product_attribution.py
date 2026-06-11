import json
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
FRONTEND_API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
SMOKE_DB_PATH = Path(os.environ.get("TASK020_SMOKE_DB", str(Path(tempfile.gettempdir()) / "task020_product_attribution.db")))

SMOKE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if SMOKE_DB_PATH.exists():
    SMOKE_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB_PATH.as_posix()}"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric  # noqa: E402


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


def assert_no_auto_execution_fields(payloads: dict[str, Any]) -> None:
    hits: list[str] = []
    for name, payload in payloads.items():
        hits.extend(f"{name}:{hit}" for hit in find_forbidden_keys(payload))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))


def metric_values(
    *,
    market_id: int,
    campaign_id: str,
    campaign_name: str,
    ad_group_id: str,
    ad_group_name: str,
    keyword_id: str,
    keyword_text: str,
    data_date: str,
    source_id: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "market_id": market_id,
        "product_id": None,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "ad_group_id": ad_group_id,
        "ad_group_name": ad_group_name,
        "keyword_id": keyword_id,
        "keyword_text": keyword_text,
        "match_type": "exact",
        "data_date": data_date,
        "impressions": 100,
        "clicks": 10,
        "cost": 12.5,
        "ads_orders": 2,
        "ads_sales": 50.0,
        "ctr": 0.1,
        "cpc": 1.25,
        "cvr": 0.2,
        "acos": 0.25,
        "roas": 4.0,
        "raw_json": "{}",
        "synced_at": datetime.now(),
    }


def add_keyword_and_search_term(db, values: dict[str, Any], search_term: str) -> None:
    db.add(
        SpKeywordMetric(
            **values,
            bid=1.0,
            serving_status="ENABLED",
            cpa=6.25,
        )
    )
    db.add(
        SpSearchTermMetric(
            **values,
            search_term=search_term,
        )
    )
    db.commit()


def seed_unbound_metrics(db, market_id: int, data_date: str) -> None:
    add_keyword_and_search_term(
        db,
        metric_values(
            market_id=market_id,
            campaign_id="TASK020-CAMPAIGN-A",
            campaign_name="TASK020 主推 Campaign",
            ad_group_id="TASK020-GROUP-A",
            ad_group_name="TASK020 主推广告组",
            keyword_id="TASK020-KW-A",
            keyword_text="task020 keyword a",
            data_date=data_date,
            source_id="TASK020-SOURCE-A",
        ),
        "task020 search a",
    )
    add_keyword_and_search_term(
        db,
        metric_values(
            market_id=market_id,
            campaign_id="TASK020-CAMPAIGN-B",
            campaign_name="TASK020 测试 Campaign",
            ad_group_id="TASK020-GROUP-B",
            ad_group_name="TASK020 测试广告组",
            keyword_id="TASK020-KW-B",
            keyword_text="task020 keyword b",
            data_date=data_date,
            source_id="TASK020-SOURCE-B",
        ),
        "task020 search b",
    )


def create_product(client: TestClient, name: str, market_id: int) -> dict[str, Any]:
    return assert_success(
        client.post(
            "/api/products",
            json={
                "asin": f"{name}-ASIN",
                "msku": f"{name}-MSKU",
                "sku": f"{name}-SKU",
                "product_name": name,
                "brand": "TASK020",
                "category": "smoke",
                "market_id": market_id,
                "inventory_quantity": 20,
            },
        ),
        f"create_product_{name}",
    )


def assert_metric_product_id(db, model, source_id: str, expected_product_id: int, label: str) -> None:
    row = db.execute(select(model).where(model.source_id == source_id)).scalar_one()
    if row.product_id != expected_product_id:
        fail(f"{label} product_id 异常：expected={expected_product_id}, actual={row.product_id}")


def assert_frontend_entries() -> list[str]:
    app_source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    api_source = FRONTEND_API_PATH.read_text(encoding="utf-8")
    checks = {
        "unbound_pool_title": "未归因广告数据池" in app_source,
        "binding_scope": "归因颗粒度" in app_source,
        "manual_confirm": "确认归因" in app_source,
        "fetch_unbound": "fetchUnboundAdSources" in api_source,
        "bind_ad_source": "bindAdSourceToProduct" in api_source,
        "fetch_bindings": "fetchProductAdBindings" in api_source,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail("前端归因入口缺失：" + ", ".join(missing))
    return list(checks.keys())


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        market_id = 920
        data_date = date.today().isoformat()
        seed_unbound_metrics(db, market_id=market_id, data_date=data_date)

        with TestClient(app) as client:
            product_a = create_product(client, "TASK020 产品 A", market_id)
            product_b = create_product(client, "TASK020 产品 B", market_id)

            unbound = assert_success(
                client.get(
                    "/api/products/unbound-ad-sources",
                    params={
                        "market_id": market_id,
                        "start_date": data_date,
                        "end_date": data_date,
                        "scope_type": "ad_group",
                    },
                ),
                "list_unbound_ad_sources",
            )
            if len(unbound) < 2:
                fail(f"未归因数据池行数不足：{len(unbound)}")
            if not all(item.get("scope_type") == "ad_group" for item in unbound):
                fail("未归因数据池没有按 Ad Group 颗粒度返回")

            campaign_binding = assert_success(
                client.put(
                    f"/api/products/{product_a['id']}/ad-binding",
                    json={
                        "scope_type": "campaign",
                        "scope_id": "TASK020-CAMPAIGN-A",
                        "scope_name": "TASK020 主推 Campaign",
                        "market_id": market_id,
                    },
                ),
                "bind_campaign_ad_source",
            )
            if campaign_binding["keyword_rows_updated"] != 1 or campaign_binding["search_term_rows_updated"] != 1:
                fail(f"Campaign 归因回填行数异常：{campaign_binding}")

            ad_group_binding = assert_success(
                client.put(
                    f"/api/products/{product_b['id']}/ad-binding",
                    json={
                        "scope_type": "ad_group",
                        "scope_id": "TASK020-GROUP-B",
                        "scope_name": "TASK020 测试广告组",
                        "market_id": market_id,
                    },
                ),
                "bind_ad_group_ad_source",
            )
            if ad_group_binding["keyword_rows_updated"] != 1 or ad_group_binding["search_term_rows_updated"] != 1:
                fail(f"Ad Group 归因回填行数异常：{ad_group_binding}")

            bindings = assert_success(
                client.get("/api/products/ad-bindings", params={"market_id": market_id}),
                "list_product_ad_bindings",
            )
            scope_types = {item.get("scope_type") for item in bindings}
            if {"campaign", "ad_group"} - scope_types:
                fail(f"归因规则未同时保存 Campaign 和 Ad Group：{scope_types}")

            assert_metric_product_id(db, SpKeywordMetric, "TASK020-SOURCE-A", product_a["id"], "Campaign 关键词")
            assert_metric_product_id(db, SpSearchTermMetric, "TASK020-SOURCE-A", product_a["id"], "Campaign 搜索词")
            assert_metric_product_id(db, SpKeywordMetric, "TASK020-SOURCE-B", product_b["id"], "Ad Group 关键词")
            assert_metric_product_id(db, SpSearchTermMetric, "TASK020-SOURCE-B", product_b["id"], "Ad Group 搜索词")

            future_values = metric_values(
                market_id=market_id,
                campaign_id="TASK020-CAMPAIGN-A",
                campaign_name="TASK020 主推 Campaign",
                ad_group_id="TASK020-GROUP-A",
                ad_group_name="TASK020 主推广告组",
                keyword_id="TASK020-KW-A2",
                keyword_text="task020 keyword a2",
                data_date=data_date,
                source_id="TASK020-SOURCE-A-FUTURE",
            )
            add_keyword_and_search_term(db, future_values, "task020 search a future")
            from app.services.product_attribution_service import apply_active_product_ad_bindings  # noqa: E402

            applied = apply_active_product_ad_bindings(
                db,
                market_id=market_id,
                period_start=data_date,
                period_end=data_date,
            )
            if applied["keyword_rows_updated"] < 1 or applied["search_term_rows_updated"] < 1:
                fail(f"后续同步归因套用失败：{applied}")
            assert_metric_product_id(db, SpKeywordMetric, "TASK020-SOURCE-A-FUTURE", product_a["id"], "后续关键词")
            assert_metric_product_id(db, SpSearchTermMetric, "TASK020-SOURCE-A-FUTURE", product_a["id"], "后续搜索词")

            dashboard = assert_success(
                client.get(
                    "/api/dashboard/summary",
                    params={
                        "market_id": market_id,
                        "start_date": data_date,
                        "end_date": data_date,
                    },
                ),
                "dashboard_summary",
            )
            if dashboard["product_binding"]["bound_rows"] < 3:
                fail(f"dashboard 产品绑定行数未提升：{dashboard['product_binding']}")

            frontend_checks = assert_frontend_entries()
            assert_no_auto_execution_fields(
                {
                    "unbound": unbound,
                    "campaign_binding": campaign_binding,
                    "ad_group_binding": ad_group_binding,
                    "bindings": bindings,
                    "applied": applied,
                    "dashboard": dashboard,
                }
            )

            print(
                json.dumps(
                    {
                        "status": "success",
                        "market_id": market_id,
                        "campaign_binding": campaign_binding,
                        "ad_group_binding": ad_group_binding,
                        "future_apply": applied,
                        "product_binding": dashboard["product_binding"],
                        "frontend_checks": frontend_checks,
                        "checked": [
                            "list_unbound_ad_sources",
                            "bind_campaign_ad_source",
                            "bind_ad_group_ad_source",
                            "list_product_ad_bindings",
                            "apply_active_product_ad_bindings",
                            "dashboard_product_binding",
                            "frontend_attribution_entries",
                            "no_auto_execution_fields",
                        ],
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        app.dependency_overrides.clear()
        db.close()


if __name__ == "__main__":
    main()
