import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
SMOKE_DB_PATH = Path(
    os.environ.get(
        "TASK035_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task035_search_term_group_decisions_{os.getpid()}.db"),
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
            market_id=935,
            product_id=None,
            campaign_id="TASK035-CAMPAIGN",
            campaign_name="TASK035 Campaign",
            ad_group_id="TASK035-GROUP",
            ad_group_name="TASK035 Group",
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
        source_id="TERM-GROUP-A",
        search_term="kids sunglasses for boys",
        keyword_text="kids sunglasses",
        clicks=12,
        cost=6.0,
        orders=3,
        sales=60.0,
    )
    add_term(
        db,
        source_id="TERM-GROUP-B",
        search_term="toddler kids sunglasses",
        keyword_text="kids sunglasses",
        clicks=5,
        cost=3.0,
        orders=1,
        sales=20.0,
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
        payload = {
            "group_key": "age_spec:high_conversion",
            "decision_type": "observe",
            "observe_period": "7d",
            "operator_name": "task035",
            "reason": "同组词表现较好，先观察后续稳定性",
            "market_id": 935,
            "start_date": "2026-06-01",
            "end_date": "2026-06-01",
            "min_clicks": 10,
            "min_spend": 10,
            "target_acos": 0.35,
            "limit": 200,
        }
        created = assert_success(client.post("/api/search-terms/group-decisions", json=payload), "create_group_decision")
        decision = created.get("decision") or {}
        if decision.get("group_key") != payload["group_key"]:
            fail(f"组级记录 group_key 异常：{decision}")
        if decision.get("decision_type") != "observe" or decision.get("observe_period") != "7d":
            fail(f"组级记录人工判断异常：{decision}")
        snapshot = decision.get("group_snapshot")
        if not isinstance(snapshot, dict) or snapshot.get("group_key") != payload["group_key"]:
            fail(f"组级记录缺少组快照：{decision}")
        if not snapshot.get("representative_terms"):
            fail(f"组快照缺少代表搜索词：{snapshot}")

        listed = assert_success(
            client.get("/api/search-terms/group-decisions", params={"market_id": 935}),
            "list_group_decisions",
        )
        if not isinstance(listed, list) or len(listed) != 1:
            fail(f"组级记录列表异常：{listed}")
        if listed[0].get("group_snapshot", {}).get("group_key") != payload["group_key"]:
            fail(f"组级记录列表缺少快照：{listed}")

        invalid = client.post(
            "/api/search-terms/group-decisions",
            json={**payload, "decision_type": "adopt_with_changes", "modified_action": "", "reason": "x"},
        )
        if invalid.status_code != 400:
            fail(f"修改后采纳缺少处理说明时应返回 400，实际 {invalid.status_code}：{invalid.text}")

        hits = find_forbidden_keys({"created": created, "listed": listed})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "create_group_decision",
                        "group_snapshot",
                        "list_group_decisions",
                        "required_modified_action_validation",
                        "no_auto_execution_fields",
                    ],
                    "decision": decision,
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
