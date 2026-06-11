import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
FRONTEND_API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
SMOKE_DB_PATH = Path(
    os.environ.get(
        "TASK023_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task023_attribution_evidence_{os.getpid()}.db"),
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


def metric_values(source_id: str, keyword_id: str, keyword_text: str, search_term: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "market_id": 923,
        "product_id": None,
        "campaign_id": "TASK023-CAMPAIGN-KIDS",
        "campaign_name": "TASK023 kids sunglasses exact",
        "ad_group_id": "TASK023-GROUP-KIDS",
        "ad_group_name": "TASK023 kids sunglasses group",
        "keyword_id": keyword_id,
        "keyword_text": keyword_text,
        "match_type": "exact",
        "data_date": "2026-06-01",
        "impressions": 200,
        "clicks": 20,
        "cost": 18.0,
        "ads_orders": 4,
        "ads_sales": 80.0,
        "ctr": 0.1,
        "cpc": 0.9,
        "cvr": 0.2,
        "acos": 0.225,
        "roas": 4.44,
        "raw_json": "{}",
        "synced_at": datetime.now(),
        "search_term": search_term,
    }


def add_metric_pair(db, values: dict[str, Any]) -> None:
    keyword_values = dict(values)
    search_values = dict(values)
    search_values.pop("bid", None)
    db.add(
        SpKeywordMetric(
            **{key: value for key, value in keyword_values.items() if key != "search_term"},
            bid=1.0,
            serving_status="ENABLED",
            cpa=4.5,
        )
    )
    db.add(SpSearchTermMetric(**search_values))
    db.commit()


def create_product(client: TestClient, name: str, asin: str, msku: str) -> dict[str, Any]:
    return assert_success(
        client.post(
            "/api/products",
            json={
                "asin": asin,
                "msku": msku,
                "sku": msku,
                "product_name": name,
                "brand": "TASK023",
                "category": "smoke",
                "market_id": 923,
                "inventory_quantity": 50,
            },
        ),
        f"create_product_{msku}",
    )


def assert_frontend_entries() -> list[str]:
    app_source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    api_source = FRONTEND_API_PATH.read_text(encoding="utf-8")
    checks = {
        "evidence_api": "fetchProductAttributionEvidence" in api_source,
        "detail_flow": "查看证据" in app_source,
        "confidence": "可信度" in app_source,
        "snapshot": "证据快照" in app_source,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail("前端归因证据入口缺失：" + ", ".join(missing))
    return list(checks.keys())


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        product_good = create_product(client, "TASK023 Kids Sunglasses", "TASK023-KIDS-ASIN", "TASK023-KIDS")
        product_other = create_product(client, "TASK023 Kitchen Tool", "TASK023-KITCHEN-ASIN", "TASK023-KITCHEN")
        add_metric_pair(db, metric_values("TASK023-SOURCE-A", "TASK023-KW-A", "kids sunglasses", "kids sunglasses for boys"))
        add_metric_pair(db, metric_values("TASK023-SOURCE-B", "TASK023-KW-B", "toddler sunglasses", "toddler sunglasses polarized"))

        db.add(
            ProductAdBinding(
                market_id=923,
                product_id=product_other["id"],
                scope_type="ad_group",
                scope_id="TASK023-GROUP-KIDS",
                scope_name="TASK023 kids sunglasses group",
                status="active",
                created_by="smoke",
                evidence_json=json.dumps({"note": "existing conflict"}, ensure_ascii=False),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        db.commit()

        evidence = assert_success(
            client.get(
                "/api/products/ad-attribution-evidence",
                params={
                    "market_id": 923,
                    "scope_type": "ad_group",
                    "scope_id": "TASK023-GROUP-KIDS",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                },
            ),
            "get_ad_attribution_evidence",
        )
        if evidence.get("source", {}).get("scope_id") != "TASK023-GROUP-KIDS":
            fail(f"归因对象证据异常：{evidence.get('source')}")
        if not evidence.get("top_keywords") or not evidence.get("top_search_terms"):
            fail("归因证据缺少 Top 关键词或 Top 搜索词")
        candidates = evidence.get("candidate_products") or []
        selected = next((item for item in candidates if item.get("product_id") == product_good["id"]), None)
        if not selected:
            fail("产品候选缺少匹配产品")
        if selected.get("confidence_score", 0) < 50:
            fail(f"匹配产品可信度过低：{selected}")
        if not selected.get("reasons"):
            fail("匹配产品缺少可信度理由")
        if not evidence.get("conflicts"):
            fail("归因证据缺少已有归因冲突提示")

        result = assert_success(
            client.put(
                f"/api/products/{product_good['id']}/ad-binding",
                json={
                    "scope_type": "ad_group",
                    "scope_id": "TASK023-GROUP-KIDS",
                    "scope_name": "TASK023 kids sunglasses group",
                    "market_id": 923,
                    "created_by": "运营人工确认",
                    "period_start": "2026-06-01",
                    "period_end": "2026-06-01",
                    "evidence_note": "smoke 确认归因证据完整",
                },
            ),
            "bind_ad_source_with_evidence_snapshot",
        )
        snapshot = json.loads(result.get("evidence_json") or "{}")
        for key in ["period", "source_snapshot", "selected_product", "confidence", "confirmation"]:
            if key not in snapshot:
                fail(f"保存后的 evidence_json 缺少 {key}：{snapshot}")
        if snapshot["selected_product"].get("product_id") != product_good["id"]:
            fail(f"证据快照产品异常：{snapshot['selected_product']}")
        if snapshot["confidence"].get("score", 0) < 50:
            fail(f"证据快照可信度异常：{snapshot['confidence']}")

        frontend_checks = assert_frontend_entries()
        assert_no_auto_execution_fields({"evidence": evidence, "binding": result})
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": [
                        "backend_attribution_evidence",
                        "candidate_confidence",
                        "conflict_warning",
                        "binding_evidence_snapshot",
                        *frontend_checks,
                        "no_auto_execution_fields",
                    ],
                    "evidence_summary": {
                        "confidence_score": snapshot["confidence"].get("score"),
                        "keyword_count": len(evidence.get("top_keywords") or []),
                        "search_term_count": len(evidence.get("top_search_terms") or []),
                        "conflict_count": len(evidence.get("conflicts") or []),
                    },
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
