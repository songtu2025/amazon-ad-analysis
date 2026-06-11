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
        "TASK030_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task030_product_seed_{os.getpid()}.db"),
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


def assert_no_auto_execution_fields(payloads: dict[str, Any]) -> None:
    hits: list[str] = []
    for name, payload in payloads.items():
        hits.extend(f"{name}:{hit}" for hit in find_forbidden_keys(payload))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))


def metric_values() -> dict[str, Any]:
    return {
        "source_id": "TASK030-SOURCE-A",
        "market_id": 930,
        "product_id": None,
        "campaign_id": "TASK030-CAMPAIGN-RBK004",
        "campaign_name": "RBK004 kids sunglasses broad",
        "ad_group_id": "TASK030-GROUP-RBK004",
        "ad_group_name": "RBK004 kids sunglasses group",
        "keyword_id": "TASK030-KW-KIDS",
        "keyword_text": "kids sunglasses",
        "match_type": "broad",
        "data_date": "2026-06-01",
        "impressions": 500,
        "clicks": 50,
        "cost": 45.0,
        "ads_orders": 8,
        "ads_sales": 160.0,
        "ctr": 0.1,
        "cpc": 0.9,
        "cvr": 0.16,
        "acos": 0.2812,
        "roas": 3.55,
        "raw_json": "{}",
        "synced_at": datetime.now(),
        "search_term": "kids sunglasses for boys",
    }


def seed_unbound_ad_source(db) -> None:
    values = metric_values()
    keyword_values = dict(values)
    keyword_values.pop("search_term")
    db.add(
        SpKeywordMetric(
            **keyword_values,
            bid=1.0,
            serving_status="ENABLED",
            cpa=5.62,
        )
    )
    db.add(SpSearchTermMetric(**values))
    db.commit()


def binding_count(db) -> int:
    return int(db.execute(select(ProductAdBinding)).scalars().all().__len__())


def unbound_product_rows(db) -> tuple[int, int]:
    keyword_rows = db.execute(select(SpKeywordMetric).where(SpKeywordMetric.product_id.is_(None))).scalars().all()
    search_rows = db.execute(select(SpSearchTermMetric).where(SpSearchTermMetric.product_id.is_(None))).scalars().all()
    return len(keyword_rows), len(search_rows)


def evidence_params() -> dict[str, object]:
    return {
        "market_id": 930,
        "scope_type": "ad_group",
        "scope_id": "TASK030-GROUP-RBK004",
        "start_date": "2026-06-01",
        "end_date": "2026-06-01",
    }


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        seed_unbound_ad_source(db)

        before_bindings = binding_count(db)
        before_rows = unbound_product_rows(db)
        before_evidence = assert_success(
            client.get("/api/products/ad-attribution-evidence", params=evidence_params()),
            "before_evidence",
        )
        if before_evidence.get("candidate_products"):
            fail("创建产品草稿前不应已有候选产品")

        product = assert_success(
            client.post(
                "/api/products",
                json={
                    "product_name": "RBK004 kids sunglasses",
                    "asin": "TASK030-ASIN-RBK004",
                    "msku": "RBK004",
                    "sku": "RBK004",
                    "brand": "RIVBOS",
                    "category": "kids sunglasses",
                    "market_id": 930,
                    "inventory_quantity": 100,
                },
            ),
            "create_product_seed",
        )

        after_evidence = assert_success(
            client.get("/api/products/ad-attribution-evidence", params=evidence_params()),
            "after_evidence",
        )
        candidates = after_evidence.get("candidate_products") or []
        matched = next((item for item in candidates if item.get("product_id") == product.get("id")), None)
        if not matched:
            fail("创建产品草稿后归因证据没有返回该产品候选")
        if int(matched.get("confidence_score") or 0) < 50:
            fail(f"产品候选可信度过低：{matched}")
        if not matched.get("reasons"):
            fail("产品候选缺少可信度理由")

        after_bindings = binding_count(db)
        after_rows = unbound_product_rows(db)
        if before_bindings != after_bindings:
            fail("创建产品草稿不应自动保存归因规则")
        if before_rows != after_rows:
            fail("创建产品草稿不应自动回填广告指标 product_id")

        assert_no_auto_execution_fields(
            {
                "product": product,
                "before_evidence": before_evidence,
                "after_evidence": after_evidence,
            }
        )
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "product_create_api",
                        "candidate_after_product_seed",
                        "candidate_confidence_reason",
                        "no_auto_binding_rule",
                        "no_product_id_backfill",
                        "no_auto_execution_fields",
                    ],
                    "candidate": {
                        "product_id": matched.get("product_id"),
                        "confidence_score": matched.get("confidence_score"),
                        "reasons": matched.get("reasons"),
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
