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
        "TASK025_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task025_search_term_analysis_{os.getpid()}.db"),
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
    campaign_name: str = "TASK025 Campaign",
    ad_group_name: str = "TASK025 Group",
) -> None:
    db.add(
        SpSearchTermMetric(
            source_id=source_id,
            market_id=925,
            product_id=None,
            campaign_id="TASK025-CAMPAIGN",
            campaign_name=campaign_name,
            ad_group_id="TASK025-GROUP",
            ad_group_name=ad_group_name,
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
    add_term(db, source_id="TERM-A", search_term="kids sunglasses for boys", keyword_text="kids sunglasses", clicks=20, cost=10.0, orders=5, sales=100.0)
    add_term(db, source_id="TERM-B", search_term="b004hvkaas", keyword_text="auto target", clicks=12, cost=15.0, orders=0, sales=0.0)
    add_term(db, source_id="TERM-C", search_term="6-12 month boy sunhat", keyword_text="baby sunglasses", clicks=14, cost=16.0, orders=0, sales=0.0)
    add_term(db, source_id="TERM-D", search_term="polarized sunglasses women", keyword_text="sunglasses", clicks=18, cost=42.0, orders=1, sales=50.0)
    add_term(db, source_id="TERM-E", search_term="kids sunglasses for boys", keyword_text="kids sunglasses exact", clicks=4, cost=2.0, orders=1, sales=20.0)
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
        payload = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 925,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "target_acos": 0.35,
                },
            ),
            "search_term_analysis",
        )
        rows = payload.get("rows") or []
        if payload.get("summary", {}).get("distinct_terms") != 4:
            fail(f"去重搜索词数量异常：{payload.get('summary')}")
        by_term = {row.get("search_term"): row for row in rows}
        if by_term.get("kids sunglasses for boys", {}).get("performance_status") != "high_conversion":
            fail(f"高转化词分类异常：{by_term.get('kids sunglasses for boys')}")
        if by_term.get("b004hvkaas", {}).get("semantic_category") != "asin":
            fail(f"ASIN 词分类异常：{by_term.get('b004hvkaas')}")
        if by_term.get("6-12 month boy sunhat", {}).get("semantic_category") != "accessory_or_unrelated":
            fail(f"疑似无关词分类异常：{by_term.get('6-12 month boy sunhat')}")
        if by_term.get("polarized sunglasses women", {}).get("performance_status") != "high_acos":
            fail(f"高 ACOS 词分类异常：{by_term.get('polarized sunglasses women')}")
        filtered = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 925,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "semantic_category": "asin",
                },
            ),
            "search_term_analysis_filter",
        )
        if len(filtered.get("rows") or []) != 1 or filtered["rows"][0]["search_term"] != "b004hvkaas":
            fail(f"语义分类过滤异常：{filtered}")
        hits = find_forbidden_keys({"analysis": payload, "filtered": filtered})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "search_term_analysis_api",
                        "distinct_term_grouping",
                        "semantic_category",
                        "performance_status",
                        "category_filter",
                        "no_auto_execution_fields",
                    ],
                    "summary": payload.get("summary"),
                    "category_summary": payload.get("category_summary"),
                    "performance_summary": payload.get("performance_summary"),
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
