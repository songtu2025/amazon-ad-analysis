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
        "TASK028_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task028_search_term_candidate_decisions_{os.getpid()}.db"),
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
from app.models.ad_metrics import SpSearchTermMetric  # noqa: E402
from app.models.decision import SearchTermCandidateDecision  # noqa: E402


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
    clicks: int,
    cost: float,
    orders: int,
    sales: float,
) -> None:
    db.add(
        SpSearchTermMetric(
            source_id=source_id,
            market_id=928,
            product_id=None,
            campaign_id="TASK028-CAMPAIGN",
            campaign_name="TASK028 Campaign",
            ad_group_id="TASK028-GROUP",
            ad_group_name="TASK028 Group",
            keyword_id=f"{source_id}-KW",
            keyword_text="kids sunglasses",
            search_term=search_term,
            match_type="phrase",
            data_date="2026-06-01",
            impressions=300,
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
    add_term(db, source_id="TERM-A", search_term="kids sunglasses for boys", clicks=24, cost=12.0, orders=6, sales=120.0)
    add_term(db, source_id="TERM-B", search_term="b004hvkaas", clicks=12, cost=15.0, orders=0, sales=0.0)
    add_term(db, source_id="TERM-C", search_term="polarized sunglasses women", clicks=18, cost=42.0, orders=1, sales=50.0)
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
        candidate_payload = assert_success(
            client.get(
                "/api/search-terms/candidates",
                params={
                    "market_id": 928,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "target_acos": 0.35,
                },
            ),
            "search_term_candidates",
        )
        rows = candidate_payload.get("rows") or []
        scale_candidate = next((row for row in rows if row.get("candidate_type") == "scale_opportunity"), None)
        if not scale_candidate:
            fail("缺少高转化放量候选")

        decision_payload = {
            "candidate_id": scale_candidate["candidate_id"],
            "decision_type": "adopt_with_changes",
            "modified_action": "人工确认后先加入下一轮精细化投放观察池",
            "reason": "相关性和转化表现较好，但需要人工复核利润和库存",
            "operator_name": "task028-smoke",
            "market_id": 928,
            "start_date": "2026-06-01",
            "end_date": "2026-06-01",
            "min_clicks": 10,
            "target_acos": 0.35,
        }
        created = assert_success(client.post("/api/search-terms/candidate-decisions", json=decision_payload), "create_candidate_decision")
        decision = created.get("decision") or {}
        if decision.get("candidate_id") != scale_candidate["candidate_id"]:
            fail("写入记录 candidate_id 不匹配")
        if decision.get("decision_type") != "adopt_with_changes":
            fail("写入记录 decision_type 不匹配")
        snapshot = decision.get("candidate_snapshot") or {}
        if snapshot.get("search_term") != "kids sunglasses for boys":
            fail("候选证据快照缺少搜索词")
        if not snapshot.get("metrics") or not snapshot.get("source_trace"):
            fail("候选证据快照缺少指标或来源追踪")

        listed = assert_success(
            client.get(
                "/api/search-terms/candidate-decisions",
                params={
                    "candidate_id": scale_candidate["candidate_id"],
                    "decision_type": "adopt_with_changes",
                    "operator_name": "task028-smoke",
                },
            ),
            "list_candidate_decisions",
        )
        if len(listed) != 1:
            fail(f"候选处理记录筛选数量异常：{len(listed)}")
        saved = db.execute(select(SearchTermCandidateDecision)).scalars().all()
        if len(saved) != 1:
            fail(f"数据库未保存搜索词候选处理记录：{len(saved)}")
        saved_snapshot = json.loads(saved[0].candidate_snapshot_json or "{}")
        if saved_snapshot.get("candidate_id") != scale_candidate["candidate_id"]:
            fail("数据库证据快照 candidate_id 不匹配")
        hits = find_forbidden_keys({"created": created, "listed": listed})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "create_search_term_candidate_decision",
                        "candidate_snapshot_saved",
                        "candidate_decision_filters",
                        "local_record_only",
                        "no_auto_execution_fields",
                    ],
                    "decision": {
                        "id": decision.get("id"),
                        "candidate_id": decision.get("candidate_id"),
                        "decision_type": decision.get("decision_type"),
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
