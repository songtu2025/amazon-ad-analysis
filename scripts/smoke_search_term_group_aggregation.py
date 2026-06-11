import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
SMOKE_DB_PATH = Path(
    os.environ.get(
        "TASK034_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task034_search_term_group_{os.getpid()}.db"),
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
    clicks: int,
    cost: float,
    orders: int,
    sales: float,
) -> None:
    db.add(
        SpSearchTermMetric(
            source_id=source_id,
            market_id=934,
            product_id=None,
            campaign_id="TASK034-CAMPAIGN",
            campaign_name="TASK034 Campaign",
            ad_group_id="TASK034-GROUP",
            ad_group_name="TASK034 Group",
            keyword_id=f"{source_id}-KW",
            keyword_text=keyword_text,
            search_term=search_term,
            match_type="phrase",
            data_date="2026-06-01",
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
        source_id="TERM-LOW-ORDER",
        search_term="toddler kids sunglasses",
        keyword_text="kids sunglasses",
        clicks=3,
        cost=2.0,
        orders=1,
        sales=20.0,
    )
    add_term(
        db,
        source_id="TERM-WASTE",
        search_term="kids sunglasses no order",
        keyword_text="kids sunglasses",
        clicks=14,
        cost=18.0,
        orders=0,
        sales=0.0,
    )
    add_term(
        db,
        source_id="TERM-HIGH-ACOS",
        search_term="polarized sunglasses women",
        keyword_text="sunglasses",
        clicks=8,
        cost=12.0,
        orders=1,
        sales=20.0,
    )
    db.commit()


def assert_group_summary(payload: dict[str, Any]) -> None:
    groups = payload.get("group_summary")
    if not isinstance(groups, list) or not groups:
        fail(f"缺少非空 group_summary：{payload}")
    by_key = {item.get("group_key"): item for item in groups if isinstance(item, dict)}
    target = by_key.get("age_spec:high_conversion")
    if not target:
        fail(f"缺少 age_spec:high_conversion 聚合组：{groups}")
    required = [
        "group_key",
        "group_label",
        "semantic_category",
        "semantic_label",
        "performance_status",
        "performance_label",
        "terms",
        "clicks",
        "cost",
        "orders",
        "sales",
        "acos",
        "cvr",
        "representative_terms",
        "manual_hint",
    ]
    missing = [key for key in required if key not in target]
    if missing:
        fail("聚合组字段缺失：" + ", ".join(missing))
    if "toddler kids sunglasses" not in target.get("representative_terms", []):
        fail(f"聚合组缺少代表搜索词：{target}")
    if int(target.get("orders") or 0) != 1:
        fail(f"聚合组订单汇总异常：{target}")


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        seed(db)
        client = TestClient(app)
        payload = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 934,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "min_spend": 10,
                    "target_acos": 0.35,
                },
            ),
            "search_term_analysis_group_summary",
        )
        rows = {row.get("search_term"): row for row in payload.get("rows") or []}
        low_order = rows.get("toddler kids sunglasses")
        if not low_order:
            fail("缺少低点击有订单搜索词明细")
        if low_order.get("performance_status") != "high_conversion":
            fail(f"低点击有订单搜索词不应归为数据不足：{low_order}")
        assert_group_summary(payload)
        hits = find_forbidden_keys(payload)
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "low_click_order_classified_by_acos",
                        "group_summary",
                        "group_required_fields",
                        "representative_terms",
                        "no_auto_execution_fields",
                    ],
                    "group_summary": payload.get("group_summary"),
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
