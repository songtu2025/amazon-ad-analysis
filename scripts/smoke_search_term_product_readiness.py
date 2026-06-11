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
        "TASK032_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task032_search_term_product_readiness_{os.getpid()}.db"),
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
from sqlalchemy import func, select  # noqa: E402

from app.core.database import SessionLocal, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ad_metrics import SpSearchTermMetric  # noqa: E402
from app.models.product import Product, ProductAdBinding  # noqa: E402


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


def add_product(db, *, name: str, msku: str, market_id: int = 932) -> Product:
    now = datetime.now()
    product = Product(
        asin=None,
        msku=msku,
        sku=None,
        product_name=name,
        image_url=None,
        brand="TASK032",
        category="sunglasses",
        market_id=market_id,
        inventory_quantity=None,
        created_at=now,
        updated_at=now,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def add_binding(db, *, product: Product, scope_id: str, scope_name: str) -> ProductAdBinding:
    now = datetime.now()
    binding = ProductAdBinding(
        market_id=product.market_id,
        product_id=product.id,
        scope_type="campaign",
        scope_id=scope_id,
        scope_name=scope_name,
        status="active",
        created_by="smoke",
        evidence_json=json.dumps({"source": "task032"}, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


def add_term(
    db,
    *,
    source_id: str,
    search_term: str,
    campaign_id: str,
    campaign_name: str,
    clicks: int,
    cost: float,
    orders: int,
    sales: float,
    product_id: int | None = None,
) -> None:
    db.add(
        SpSearchTermMetric(
            source_id=source_id,
            market_id=932,
            product_id=product_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            ad_group_id=f"{campaign_id}-GROUP",
            ad_group_name=f"{campaign_name} Group",
            keyword_id=f"{source_id}-KW",
            keyword_text="kids sunglasses",
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
    db.commit()


def counts(db) -> dict[str, int]:
    return {
        "bindings": int(db.execute(select(func.count(ProductAdBinding.id))).scalar_one() or 0),
        "bound_search_terms": int(
            db.execute(select(func.count(SpSearchTermMetric.id)).where(SpSearchTermMetric.product_id.is_not(None))).scalar_one() or 0
        ),
    }


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        product = add_product(db, name="TASK032 kids sunglasses", msku="TASK032-RBK")
        add_term(
            db,
            source_id="TERM-NO-BINDING",
            search_term="kids sunglasses no attribution",
            campaign_id="TASK032-CAMPAIGN-NO-BINDING",
            campaign_name="TASK032 No Binding",
            clicks=15,
            cost=12.0,
            orders=1,
            sales=40.0,
        )
        client = TestClient(app)

        not_ready = assert_success(
            client.get(
                "/api/search-terms/product-readiness",
                params={"market_id": 932, "start_date": "2026-06-01", "end_date": "2026-06-01"},
            ),
            "product_readiness_not_ready",
        )
        if not_ready.get("ready") is not False or not_ready.get("status") != "needs_attribution":
            fail(f"缺少归因规则时就绪状态异常：{not_ready}")
        if "产品设置页" not in str(not_ready.get("manual_hint") or ""):
            fail(f"缺少人工确认归因提示：{not_ready}")

        add_binding(db, product=product, scope_id="TASK032-CAMPAIGN-READY", scope_name="TASK032 Ready Campaign")
        add_term(
            db,
            source_id="TERM-READY",
            search_term="kids sunglasses ready product",
            campaign_id="TASK032-CAMPAIGN-READY",
            campaign_name="TASK032 Ready Campaign",
            clicks=20,
            cost=10.0,
            orders=4,
            sales=100.0,
            product_id=product.id,
        )
        before = counts(db)
        ready = assert_success(
            client.get(
                "/api/search-terms/product-readiness",
                params={"market_id": 932, "start_date": "2026-06-01", "end_date": "2026-06-01"},
            ),
            "product_readiness_ready",
        )
        after = counts(db)
        if before != after:
            fail(f"就绪检查不应写库，前后计数变化：before={before}, after={after}")
        if ready.get("ready") is not True or ready.get("status") != "ready":
            fail(f"有归因规则和已归因搜索词时就绪状态异常：{ready}")
        summary = ready.get("summary") or {}
        if summary.get("active_binding_count") != 1 or summary.get("bound_search_term_rows") != 1:
            fail(f"就绪汇总异常：{summary}")
        products = ready.get("products") or []
        if not products or products[0].get("product_id") != product.id:
            fail(f"产品维度汇总缺失：{products}")

        analysis = assert_success(
            client.get(
                "/api/search-terms/analysis",
                params={
                    "market_id": 932,
                    "product_id": product.id,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                },
            ),
            "search_term_analysis_product_filter",
        )
        if analysis.get("filters", {}).get("product_id") != product.id:
            fail(f"搜索词分析未透传 product_id：{analysis.get('filters')}")
        if analysis.get("summary", {}).get("distinct_terms") != 1:
            fail(f"搜索词分析 product_id 筛选异常：{analysis.get('summary')}")

        hits = find_forbidden_keys({"not_ready": not_ready, "ready": ready, "analysis": analysis})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))

        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "product_readiness_not_ready",
                        "manual_attribution_hint",
                        "product_readiness_ready",
                        "read_only_counts_unchanged",
                        "product_level_metrics",
                        "analysis_product_id_filter",
                        "no_auto_execution_fields",
                    ],
                    "summary": ready.get("summary"),
                    "product": products[0],
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
