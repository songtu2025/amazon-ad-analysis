import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
FRONTEND_API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
SMOKE_DB_PATH = PROJECT_ROOT / "tmp" / "task010_product_settings.db"

SMOKE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if SMOKE_DB_PATH.exists():
    SMOKE_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{SMOKE_DB_PATH.as_posix()}"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

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


def seed_campaign_metrics(db, campaign_id: str, market_id: int) -> None:
    now = datetime.now()
    common = {
        "source_id": "TASK010-SOURCE",
        "market_id": market_id,
        "product_id": None,
        "campaign_id": campaign_id,
        "campaign_name": "task010 campaign",
        "ad_group_id": "TASK010-ADGROUP",
        "ad_group_name": "task010 ad group",
        "keyword_id": "TASK010-KW",
        "keyword_text": "task010 keyword",
        "match_type": "exact",
        "data_date": date.today().isoformat(),
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
        "synced_at": now,
    }
    db.add(
        SpKeywordMetric(
            **common,
            bid=1.0,
            serving_status="ENABLED",
            cpa=6.25,
        )
    )
    db.add(
        SpSearchTermMetric(
            **common,
            search_term="task010 search term",
        )
    )
    db.commit()


def assert_frontend_entries() -> list[str]:
    app_source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    api_source = FRONTEND_API_PATH.read_text(encoding="utf-8")
    checks = {
        "product_center_tab": 'label: "产品中心"' in app_source,
        "attribution_tab": 'label: "广告归因"' in app_source,
        "goal_filter": 'placeholder="产品目标"' in app_source,
        "save_button": "保存设置" in app_source,
        "batch_apply": "批量应用" in app_source,
        "product_basis_panel": "产品基础设置" in app_source,
        "create_product": "createProduct" in api_source,
        "update_goal": "updateProductGoal" in api_source,
        "update_rules": "updateProductRules" in api_source,
        "bind_campaign": "bindCampaignToProduct" in api_source,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail("前端产品中心入口缺失：" + ", ".join(missing))
    if "绑定广告活动" in app_source or 'placeholder="广告活动 ID"' in app_source:
        fail("产品中心仍包含广告活动绑定输入")
    return list(checks.keys())


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        campaign_id = "TASK010-CAMPAIGN"
        market_id = 910
        seed_campaign_metrics(db, campaign_id=campaign_id, market_id=market_id)

        with TestClient(app) as client:
            product = assert_success(
                client.post(
                    "/api/products",
                    json={
                        "asin": "TASK010-ASIN",
                        "msku": "TASK010-MSKU",
                        "sku": "TASK010-SKU",
                        "product_name": "TASK010 产品目标验收",
                        "brand": "TASK010",
                        "category": "smoke",
                        "market_id": market_id,
                        "inventory_quantity": 18,
                    },
                ),
                "create_product",
            )
            product_id = product["id"]

            goal = assert_success(
                client.put(
                    f"/api/products/{product_id}/goal",
                    json={"goal_type": "profit", "note": "TASK-010 smoke"},
                ),
                "update_goal",
            )
            if goal["goal_type"] != "profit":
                fail("产品目标写入后读取不一致")

            rules_payload = {
                "min_clicks": 8,
                "min_spend": 10.0,
                "min_orders": 1,
                "target_acos": 0.3,
                "target_cvr": 0.15,
                "max_cpc": 1.5,
                "inventory_guard": 12,
            }
            rules = assert_success(
                client.put(f"/api/products/{product_id}/rules", json=rules_payload),
                "update_rules",
            )
            for key, expected in rules_payload.items():
                if rules.get(key) != expected:
                    fail(f"规则字段 {key} 写入后读取不一致")

            binding = assert_success(
                client.put(
                    f"/api/products/{product_id}/campaign-binding",
                    json={"campaign_id": campaign_id, "market_id": market_id},
                ),
                "campaign_binding",
            )
            if binding["rows_updated"] != 2:
                fail(f"广告活动绑定行数异常：{binding['rows_updated']}")

            detail = assert_success(client.get(f"/api/products/{product_id}"), "get_product")
            if detail["goal"]["goal_type"] != "profit":
                fail("产品详情未返回已设置目标")
            if detail["rules"]["target_acos"] != 0.3:
                fail("产品详情未返回已设置规则")
            if detail["inventory_status"] != "库存充足":
                fail("库存阈值判断异常")
            if detail["sp_metrics"]["clicks"] != 10:
                fail("广告活动绑定后产品指标归属异常")

            listed = assert_success(client.get("/api/products", params={"market_id": market_id}), "list_products")
            if not any(item["id"] == product_id for item in listed):
                fail("产品列表未返回新建产品")

            frontend_checks = assert_frontend_entries()
            assert_no_auto_execution_fields(
                {
                    "product": product,
                    "goal": goal,
                    "rules": rules,
                    "binding": binding,
                    "detail": detail,
                    "listed": listed,
                }
            )

            print(
                json.dumps(
                    {
                        "status": "success",
                        "product_id": product_id,
                        "campaign_rows_updated": binding["rows_updated"],
                        "frontend_checks": frontend_checks,
                        "checked": [
                            "create_product",
                            "update_product_goal",
                            "update_product_rules",
                            "bind_campaign_to_product",
                            "get_product",
                            "list_products",
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
