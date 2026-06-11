import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, get_db, init_db  # noqa: E402
from app.api.routes.dashboard import dashboard_health  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric  # noqa: E402
from app.models.market import MarketInfo  # noqa: E402


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


def seed_identity_fixture(db) -> None:
    now = datetime.now()
    market_id = 917
    db.add(
        MarketInfo(
            market_id=market_id,
            market_name="TASK017 店铺",
            country_code="US",
            raw_name="TASK017 店铺:US",
            updated_at=now,
        )
    )
    rows = [
        {
            "campaign_id": "TASK017-CAMPAIGN-A",
            "campaign_name": "TASK017 主推 Campaign",
            "ad_group_id": "TASK017-GROUP-A",
            "ad_group_name": "TASK017 主推广告组",
            "keyword_id": "TASK017-KW-A",
            "keyword_text": "task017 keyword a",
            "cost": 31.5,
            "ads_orders": 4,
            "ads_sales": 126.0,
            "product_id": None,
        },
        {
            "campaign_id": "TASK017-CAMPAIGN-B",
            "campaign_name": "TASK017 扩展 Campaign",
            "ad_group_id": "TASK017-GROUP-B",
            "ad_group_name": "TASK017 扩展广告组",
            "keyword_id": "TASK017-KW-B",
            "keyword_text": "task017 keyword b",
            "cost": 18.0,
            "ads_orders": 2,
            "ads_sales": 60.0,
            "product_id": 12,
        },
    ]
    for row in rows:
        db.add(
            SpKeywordMetric(
                source_id=row["keyword_id"],
                market_id=market_id,
                product_id=row["product_id"],
                campaign_id=row["campaign_id"],
                campaign_name=row["campaign_name"],
                ad_group_id=row["ad_group_id"],
                ad_group_name=row["ad_group_name"],
                keyword_id=row["keyword_id"],
                keyword_text=row["keyword_text"],
                match_type="exact",
                bid=1.0,
                serving_status="ENABLED",
                data_date="2026-06-10",
                impressions=1000,
                clicks=40,
                cost=row["cost"],
                ads_orders=row["ads_orders"],
                ads_sales=row["ads_sales"],
                ctr=0.04,
                cpc=0.8,
                cvr=0.1,
                cpa=8.0,
                acos=row["cost"] / row["ads_sales"],
                roas=row["ads_sales"] / row["cost"],
                raw_json="{}",
                synced_at=now,
            )
        )
    db.commit()


def assert_frontend_identity_markers() -> list[str]:
    source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    checks = {
        "identity_panel": "当前数据身份" in source,
        "market_name": "market_name" in source,
        "top_campaigns": "top_campaigns" in source,
        "binding_status": "产品绑定状态" in source,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail("前端数据身份标记缺失：" + ", ".join(missing))
    return list(checks.keys())


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        seed_identity_fixture(db)
        payload = dashboard_health(
            market_id=917,
            start_date=datetime.fromisoformat("2026-06-10").date(),
            end_date=datetime.fromisoformat("2026-06-10").date(),
            db=db,
        )

        market = payload.get("market")
        if not isinstance(market, dict):
            fail("dashboard health 未返回 market 数据身份")
        if market.get("market_name") != "TASK017 店铺" or market.get("country_code") != "US":
            fail("market 店铺名称或站点返回不正确")

        binding = payload.get("product_binding")
        if not isinstance(binding, dict):
            fail("dashboard health 未返回产品绑定状态")
        if binding.get("bound_rows") != 1 or binding.get("total_rows") != 2:
            fail("产品绑定状态统计不正确")

        top_campaigns = payload.get("top_campaigns")
        if not isinstance(top_campaigns, list) or not top_campaigns:
            fail("dashboard health 未返回广告活动 Top 列表")
        if top_campaigns[0].get("campaign_name") != "TASK017 主推 Campaign":
            fail("广告活动 Top 列表排序或名称不正确")

        frontend_checks = assert_frontend_identity_markers()
        forbidden_hits = find_forbidden_keys(payload)
        if forbidden_hits:
            fail("dashboard identity payload 发现自动执行广告动作字段：" + ", ".join(forbidden_hits))

        print(
            json.dumps(
                {
                    "status": "success",
                    "market": market,
                    "product_binding": binding,
                    "top_campaign_count": len(top_campaigns),
                    "frontend_checks": frontend_checks,
                    "checked": [
                        "dashboard_market_identity",
                        "product_binding_status",
                        "top_campaigns",
                        "frontend_identity_markers",
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
