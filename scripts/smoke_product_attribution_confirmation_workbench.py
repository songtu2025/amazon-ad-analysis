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
        "TASK033_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task033_attribution_workbench_{os.getpid()}.db"),
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
from app.models.product import ProductAdBinding  # noqa: E402


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


def assert_no_auto_execution_fields(payload: Any) -> None:
    hits = find_forbidden_keys(payload)
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))


def metric_values(
    source_id: str,
    group_id: str,
    group_name: str,
    keyword_text: str,
    search_term: str,
    *,
    cost: float,
    orders: int,
    sales: float,
) -> dict[str, Any]:
    clicks = 20
    return {
        "source_id": source_id,
        "market_id": 933,
        "product_id": None,
        "campaign_id": "TASK033-CAMPAIGN",
        "campaign_name": "TASK033 campaign",
        "ad_group_id": group_id,
        "ad_group_name": group_name,
        "keyword_id": f"{source_id}-KW",
        "keyword_text": keyword_text,
        "match_type": "exact",
        "data_date": "2026-06-01",
        "impressions": 200,
        "clicks": clicks,
        "cost": cost,
        "ads_orders": orders,
        "ads_sales": sales,
        "ctr": 0.1,
        "cpc": round(cost / clicks, 4),
        "cvr": round(orders / clicks, 4),
        "acos": round(cost / sales, 4) if sales else 0,
        "roas": round(sales / cost, 4) if cost else 0,
        "raw_json": "{}",
        "synced_at": datetime.now(),
        "search_term": search_term,
    }


def add_metric_pair(db, values: dict[str, Any]) -> None:
    keyword_values = dict(values)
    keyword_values.pop("search_term")
    db.add(
        SpKeywordMetric(
            **keyword_values,
            bid=1.0,
            serving_status="ENABLED",
            cpa=4.5,
        )
    )
    db.add(SpSearchTermMetric(**values))
    db.commit()


def create_product(client: TestClient, name: str, msku: str) -> dict[str, Any]:
    return assert_success(
        client.post(
            "/api/products",
            json={
                "asin": None,
                "msku": msku,
                "sku": msku,
                "product_name": name,
                "brand": "TASK033",
                "category": "smoke",
                "market_id": 933,
                "inventory_quantity": 30,
            },
        ),
        f"create_product_{msku}",
    )


def binding_count(db) -> int:
    return len(db.execute(select(ProductAdBinding)).scalars().all())


def unbound_rows(db) -> tuple[int, int]:
    keywords = db.execute(select(SpKeywordMetric).where(SpKeywordMetric.product_id.is_(None))).scalars().all()
    terms = db.execute(select(SpSearchTermMetric).where(SpSearchTermMetric.product_id.is_(None))).scalars().all()
    return len(keywords), len(terms)


def assert_unlock_impact(top: dict[str, Any]) -> None:
    if top.get("priority_rank") != 1:
        fail(f"Top 候选 priority_rank 应为 1：{top.get('priority_rank')}")
    if "建议优先确认" not in str(top.get("priority_label") or ""):
        fail(f"Top 候选缺少建议优先确认标签：{top.get('priority_label')}")
    impact = top.get("unlock_impact")
    if not isinstance(impact, dict):
        fail(f"Top 候选缺少 unlock_impact：{top}")
    for key in ["search_term_rows", "cost", "sales", "orders", "acos"]:
        if key not in impact:
            fail(f"unlock_impact 缺少 {key}：{impact}")
    if int(impact.get("search_term_rows") or 0) <= 0:
        fail(f"确认后可解锁搜索词行数异常：{impact}")
    if float(impact.get("cost") or 0) <= 0:
        fail(f"确认后可解锁花费异常：{impact}")
    if float(impact.get("sales") or 0) <= 0:
        fail(f"确认后可解锁销售异常：{impact}")
    if int(impact.get("orders") or 0) <= 0:
        fail(f"确认后可解锁订单异常：{impact}")


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        product = create_product(client, "TASK033 RBK004 kids sunglasses", "RBK004")
        create_product(client, "TASK033 kitchen tool", "KITCHEN")
        add_metric_pair(
            db,
            metric_values(
                "TASK033-SOURCE-A",
                "TASK033-GROUP-RBK004",
                "RBK004 kids sunglasses group",
                "kids sunglasses",
                "kids sunglasses for boys",
                cost=22.0,
                orders=4,
                sales=80.0,
            ),
        )
        add_metric_pair(
            db,
            metric_values(
                "TASK033-SOURCE-B",
                "TASK033-GROUP-OTHER",
                "unknown generic group",
                "random keyword",
                "random term",
                cost=18.0,
                orders=1,
                sales=20.0,
            ),
        )

        before_bindings = binding_count(db)
        before_rows = unbound_rows(db)
        payload = assert_success(
            client.get(
                "/api/products/attribution-candidates",
                params={
                    "market_id": 933,
                    "scope_type": "ad_group",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_confidence": 50,
                },
            ),
            "get_attribution_candidates",
        )
        rows = payload.get("rows") or []
        if not rows:
            fail("归因候选队列为空")
        top = rows[0]
        if top.get("source", {}).get("scope_id") != "TASK033-GROUP-RBK004":
            fail(f"Top 候选来源异常：{top}")
        candidate = top.get("candidate_product") or {}
        if candidate.get("product_id") != product["id"]:
            fail(f"Top 候选产品异常：{candidate}")
        assert_unlock_impact(top)

        after_bindings = binding_count(db)
        after_rows = unbound_rows(db)
        if before_bindings != after_bindings:
            fail("候选确认工作台不应保存归因规则")
        if before_rows != after_rows:
            fail("候选确认工作台不应回填 product_id")

        assert_no_auto_execution_fields(payload)
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "priority_rank",
                        "priority_label",
                        "unlock_impact",
                        "read_only_no_binding",
                        "read_only_no_product_backfill",
                        "no_auto_execution_fields",
                    ],
                    "top_candidate": {
                        "candidate_id": top.get("candidate_id"),
                        "priority_rank": top.get("priority_rank"),
                        "priority_label": top.get("priority_label"),
                        "unlock_impact": top.get("unlock_impact"),
                    },
                },
                ensure_ascii=False,
            )
        )
    finally:
        app.dependency_overrides.clear()
        db.close()


if __name__ == "__main__":
    main()
