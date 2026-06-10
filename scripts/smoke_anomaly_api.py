import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SYNC_SCHEDULER_ENABLED"] = "false"
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal, init_db, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402


FORBIDDEN_ACTION_KEYS = {
    "action",
    "actions",
    "ad_action",
    "execution",
    "execute",
    "operation",
    "bid_adjustment",
    "new_bid",
    "pause",
    "enable",
    "negative_keyword",
}


def _contains_forbidden_action_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                return True
            if _contains_forbidden_action_key(child):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_action_key(item) for item in value)
    return False


def _make_event(
    *,
    market_id: int,
    anomaly_type: str,
    status: str,
    object_id: str,
    object_name: str,
) -> AnomalyEvent:
    now = datetime.now()
    evidence = {
        "period": {"start": "2026-05-28", "end": "2026-06-10"},
        "market_id": market_id,
        "keyword_id": object_id,
        "keyword_text": object_name,
        "clicks": 10,
        "cost": 20.0,
        "orders": 0,
    }
    rule_result = {
        "anomaly_type": anomaly_type,
        "severity": "high",
        "suggestion_level": "observe",
        "object_type": "keyword",
        "object_id": object_id,
        "matched_rules": [
            {
                "rule": anomaly_type,
                "result": "failed",
                "message": "smoke 验证异常事件 API",
            }
        ],
        "blocked_rules": [],
        "evidence": evidence,
    }
    return AnomalyEvent(
        product_id=None,
        market_id=market_id,
        anomaly_type=anomaly_type,
        severity="high",
        object_type="keyword",
        object_id=object_id,
        object_name=object_name,
        period_start="2026-05-28",
        period_end="2026-06-10",
        status=status,
        rule_result_json=json.dumps(rule_result, ensure_ascii=False),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )


def _seed_anomalies(db) -> list[int]:
    events = [
        _make_event(
            market_id=1,
            anomaly_type="clicks_no_orders",
            status="pending",
            object_id="SMOKE-KW-1",
            object_name="smoke no orders",
        ),
        _make_event(
            market_id=1,
            anomaly_type="acos_worse",
            status="handled",
            object_id="SMOKE-KW-2",
            object_name="smoke high acos",
        ),
        _make_event(
            market_id=2,
            anomaly_type="impression_low",
            status="observing",
            object_id="SMOKE-KW-3",
            object_name="smoke low impression",
        ),
    ]
    db.add_all(events)
    db.commit()
    return [event.id for event in events]


def _assert_success(response, label: str) -> Any:
    if response.status_code != 200:
        raise SystemExit(f"status=failed check={label} http_status={response.status_code} body={response.text}")
    return response.json()


def _assert_no_auto_action_fields(payload: Any, label: str) -> None:
    parsed_payload = payload
    if isinstance(payload, list):
        parsed_payload = [_parse_event_json_fields(item) for item in payload]
    elif isinstance(payload, dict):
        parsed_payload = _parse_event_json_fields(payload)
    if _contains_forbidden_action_key(parsed_payload):
        raise SystemExit(f"status=failed check={label} reason=contains_auto_action_field")


def _parse_event_json_fields(event: dict[str, Any]) -> dict[str, Any]:
    parsed = dict(event)
    for field in ["rule_result_json", "evidence_json"]:
        if field in parsed and isinstance(parsed[field], str):
            parsed[field] = json.loads(parsed[field])
    return parsed


def main() -> None:
    init_db()
    db = SessionLocal()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        event_ids = _seed_anomalies(db)
        with TestClient(app) as client:
            all_events = _assert_success(client.get("/api/anomalies"), "list")
            if len(all_events) != 3:
                raise SystemExit(f"status=failed check=list expected=3 actual={len(all_events)}")
            _assert_no_auto_action_fields(all_events, "list")

            detail = _assert_success(client.get(f"/api/anomalies/{event_ids[0]}"), "detail")
            if detail["id"] != event_ids[0]:
                raise SystemExit("status=failed check=detail reason=id_mismatch")
            _assert_no_auto_action_fields(detail, "detail")

            by_market = _assert_success(client.get("/api/anomalies", params={"market_id": 1}), "filter_market")
            if len(by_market) != 2 or any(item["market_id"] != 1 for item in by_market):
                raise SystemExit("status=failed check=filter_market reason=unexpected_result")

            by_type = _assert_success(
                client.get("/api/anomalies", params={"anomaly_type": "clicks_no_orders"}),
                "filter_anomaly_type",
            )
            if len(by_type) != 1 or by_type[0]["anomaly_type"] != "clicks_no_orders":
                raise SystemExit("status=failed check=filter_anomaly_type reason=unexpected_result")

            alias_type = _assert_success(
                client.get("/api/anomalies", params={"anomaly_type": "impressions_drop"}),
                "filter_anomaly_type_alias",
            )
            if len(alias_type) != 1 or alias_type[0]["anomaly_type"] != "impression_low":
                raise SystemExit("status=failed check=filter_anomaly_type_alias reason=unexpected_result")

            by_status = _assert_success(client.get("/api/anomalies", params={"status": "handled"}), "filter_status")
            if len(by_status) != 1 or by_status[0]["status"] != "handled":
                raise SystemExit("status=failed check=filter_status reason=unexpected_result")

            print(
                {
                    "status": "success",
                    "events_seeded": len(event_ids),
                    "list_count": len(all_events),
                    "detail_id": detail["id"],
                    "filters_checked": ["market_id", "anomaly_type", "anomaly_type_alias", "status"],
                }
            )
    finally:
        app.dependency_overrides.clear()
        db.close()


if __name__ == "__main__":
    main()
