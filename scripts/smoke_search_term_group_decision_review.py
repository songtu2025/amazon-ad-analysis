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
from app.models.ad_metrics import SpSearchTermMetric  # noqa: E402


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


def add_term(
    db,
    *,
    source_id: str,
    search_term: str,
    keyword_text: str,
    data_date: str,
    clicks: int,
    cost: float,
    orders: int,
    sales: float,
) -> None:
    db.add(
        SpSearchTermMetric(
            source_id=source_id,
            market_id=941,
            product_id=None,
            campaign_id="TASK041-CAMPAIGN",
            campaign_name="TASK041 Campaign",
            ad_group_id="TASK041-GROUP",
            ad_group_name="TASK041 Group",
            keyword_id=f"{source_id}-KW",
            keyword_text=keyword_text,
            search_term=search_term,
            match_type="phrase",
            data_date=data_date,
            impressions=100,
            clicks=clicks,
            cost=cost,
            ads_orders=orders,
            ads_sales=sales,
            ctr=0.1,
            cpc=round(cost / clicks, 4) if clicks else 0,
            cvr=round(orders / clicks, 4) if clicks else 0,
            acos=round(cost / sales, 4) if sales else 0,
            roas=round(sales / cost, 4) if cost else 0,
            raw_json="{}",
            synced_at=datetime.now(),
        )
    )


def seed(db) -> None:
    add_term(
        db,
        source_id="TERM-GROUP-BEFORE-A",
        search_term="kids sunglasses for boys",
        keyword_text="kids sunglasses",
        data_date="2026-06-01",
        clicks=12,
        cost=6.0,
        orders=3,
        sales=60.0,
    )
    add_term(
        db,
        source_id="TERM-GROUP-BEFORE-B",
        search_term="toddler kids sunglasses",
        keyword_text="kids sunglasses",
        data_date="2026-06-01",
        clicks=5,
        cost=3.0,
        orders=1,
        sales=20.0,
    )
    add_term(
        db,
        source_id="TERM-GROUP-AFTER-A",
        search_term="kids sunglasses for boys",
        keyword_text="kids sunglasses",
        data_date="2026-06-03",
        clicks=14,
        cost=5.0,
        orders=4,
        sales=90.0,
    )
    add_term(
        db,
        source_id="TERM-GROUP-AFTER-B",
        search_term="toddler kids sunglasses",
        keyword_text="kids sunglasses",
        data_date="2026-06-04",
        clicks=7,
        cost=2.0,
        orders=2,
        sales=40.0,
    )
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        seed(db)
        client = TestClient(app)
        created = assert_success(
            client.post(
                "/api/search-terms/group-decisions",
                json={
                    "group_key": "age_spec:high_conversion",
                    "decision_type": "observe",
                    "observe_period": "7d",
                    "operator_name": "task041",
                    "reason": "同组高转化词先观察后续稳定性",
                    "market_id": 941,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "min_spend": 10,
                    "target_acos": 0.35,
                    "limit": 200,
                },
            ),
            "create_group_decision",
        )
        decision = created.get("decision") or {}
        decision_id = decision.get("id")
        if not isinstance(decision_id, int) or decision_id <= 0:
            fail(f"组级记录 ID 异常：{decision}")

        review = assert_success(
            client.get(f"/api/search-terms/group-decisions/{decision_id}/review", params={"review_period": "7d"}),
            "group_decision_review",
        )
        for key in ["before_metrics", "after_metrics", "delta_metrics", "result", "result_label", "manual_hint"]:
            if key not in review:
                fail(f"组级复盘缺少字段 {key}：{review}")
        if review.get("decision_id") != decision_id:
            fail(f"组级复盘 decision_id 异常：{review}")
        if review.get("group_key") != "age_spec:high_conversion":
            fail(f"组级复盘 group_key 异常：{review}")
        if review.get("review_period") != "7d":
            fail(f"组级复盘周期异常：{review}")
        before = review["before_metrics"]
        after = review["after_metrics"]
        delta = review["delta_metrics"]
        if before.get("orders") != 4 or before.get("cost") != 9.0:
            fail(f"判断前组快照指标异常：{before}")
        if after.get("orders") != 6 or after.get("cost") != 7.0:
            fail(f"判断后组指标异常：{after}")
        if delta.get("orders_delta") != 2 or delta.get("cost_delta") != -2.0:
            fail(f"组级复盘变化指标异常：{delta}")
        if review.get("result") != "improved":
            fail(f"组级复盘结论应为 improved：{review}")
        if "自动" not in str(review.get("manual_hint")):
            fail(f"组级复盘缺少人工判断提示：{review}")

        invalid = client.get(f"/api/search-terms/group-decisions/{decision_id}/review", params={"review_period": "30d"})
        if invalid.status_code != 400:
            fail(f"非法复盘周期应返回 400，实际 {invalid.status_code}：{invalid.text}")

        hits = find_forbidden_keys(review)
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "group_decision_review_endpoint",
                        "before_after_delta_metrics",
                        "review_result",
                        "invalid_period_validation",
                        "no_auto_execution_fields",
                    ],
                    "review": review,
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
