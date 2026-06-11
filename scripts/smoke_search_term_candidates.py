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
        "TASK027_SMOKE_DB",
        str(Path(tempfile.gettempdir()) / f"task027_search_term_candidates_{os.getpid()}.db"),
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
            market_id=927,
            product_id=None,
            campaign_id="TASK027-CAMPAIGN",
            campaign_name="TASK027 Campaign",
            ad_group_id="TASK027-GROUP",
            ad_group_name="TASK027 Group",
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
        source_id="TERM-A",
        search_term="kids sunglasses for boys",
        keyword_text="kids sunglasses",
        clicks=24,
        cost=12.0,
        orders=6,
        sales=120.0,
    )
    add_term(
        db,
        source_id="TERM-B",
        search_term="b004hvkaas",
        keyword_text="auto target",
        clicks=12,
        cost=15.0,
        orders=0,
        sales=0.0,
    )
    add_term(
        db,
        source_id="TERM-C",
        search_term="polarized sunglasses women",
        keyword_text="sunglasses",
        clicks=18,
        cost=42.0,
        orders=1,
        sales=50.0,
    )
    add_term(
        db,
        source_id="TERM-D",
        search_term="too small sample",
        keyword_text="sample",
        clicks=2,
        cost=1.0,
        orders=0,
        sales=0.0,
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
        payload = assert_success(
            client.get(
                "/api/search-terms/candidates",
                params={
                    "market_id": 927,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "min_clicks": 10,
                    "target_acos": 0.35,
                },
            ),
            "search_term_candidates",
        )
        rows = payload.get("rows") or []
        if payload.get("summary", {}).get("total_candidates") != 3:
            fail(f"候选数量异常：{payload.get('summary')}")
        by_term = {row.get("search_term"): row for row in rows}
        expected = {
            "kids sunglasses for boys": "scale_opportunity",
            "b004hvkaas": "waste_risk",
            "polarized sunglasses women": "efficiency_risk",
        }
        for term, candidate_type in expected.items():
            if by_term.get(term, {}).get("candidate_type") != candidate_type:
                fail(f"候选类型异常：{term} -> {by_term.get(term)}")
            row = by_term[term]
            for required in ["title", "recommended_manual_decision", "suggested_manual_action", "reasoning", "risk_note", "metrics", "evidence"]:
                if required not in row:
                    fail(f"候选字段缺失：{term}.{required}")
        filtered = assert_success(
            client.get(
                "/api/search-terms/candidates",
                params={
                    "market_id": 927,
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-01",
                    "candidate_type": "scale_opportunity",
                    "min_clicks": 10,
                    "target_acos": 0.35,
                },
            ),
            "search_term_candidates_filter",
        )
        filtered_rows = filtered.get("rows") or []
        if len(filtered_rows) != 1 or filtered_rows[0].get("search_term") != "kids sunglasses for boys":
            fail(f"候选类型过滤异常：{filtered}")
        hits = find_forbidden_keys({"candidates": payload, "filtered": filtered})
        if hits:
            fail("发现自动执行广告动作字段：" + ", ".join(hits))
        print(
            json.dumps(
                {
                    "status": "success",
                    "checked": [
                        "search_term_candidates_api",
                        "candidate_type_mapping",
                        "candidate_type_filter",
                        "manual_decision_fields",
                        "source_evidence",
                        "no_auto_execution_fields",
                    ],
                    "summary": payload.get("summary"),
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
