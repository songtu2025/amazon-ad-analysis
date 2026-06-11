import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402
from app.models.suggestion import AiSuggestion  # noqa: E402
from app.services.suggestion_service import generate_suggestions  # noqa: E402


FORBIDDEN_EXECUTION_KEYS = {
    "auto_execute",
    "execution",
    "execute",
    "bid_adjustment",
    "new_bid",
    "pause_ad",
    "enable_ad",
    "negative_keyword",
    "api_call",
}


def _contains_forbidden_execution_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_EXECUTION_KEYS:
                return True
            if _contains_forbidden_execution_key(child):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_execution_key(item) for item in value)
    return False


def _make_anomaly() -> AnomalyEvent:
    now = datetime.now()
    evidence = {
        "period": {"start": "2026-05-12", "end": "2026-06-10"},
        "market_id": 1,
        "product_id": 101,
        "product_goal": "profit",
        "campaign_id": "SNAPSHOT-CAMPAIGN",
        "campaign_name": "snapshot campaign",
        "ad_group_id": "SNAPSHOT-ADGROUP",
        "ad_group_name": "snapshot ad group",
        "keyword_id": "SNAPSHOT-KW",
        "keyword_text": "snapshot high acos",
        "match_type": "exact",
        "clicks": 40,
        "cost": 80.0,
        "orders": 2,
        "sales": 100.0,
        "acos": 0.8,
        "target_acos": 0.3,
        "product_sales_snapshot": {
            "period_start": "2026-05-12",
            "period_end": "2026-06-10",
            "units_ordered": 9,
            "orders": 7,
            "sales": 321.45,
            "sessions": 456,
            "order_cvr": 0.0154,
            "ads_spend": 33.33,
            "ads_sales": 123.45,
            "acos": 0.27,
            "gross_profit": 88.8,
            "net_profit": 44.4,
        },
    }
    rule_result = {
        "anomaly_type": "acos_worse",
        "severity": "high",
        "suggestion_level": "adoptable",
        "object_type": "keyword",
        "object_id": "SNAPSHOT-KW",
        "matched_rules": [
            {
                "rule": "acos_above_target",
                "result": "failed",
                "message": "关键词 ACOS 高于产品目标门槛",
            }
        ],
        "blocked_rules": [],
        "evidence": evidence,
    }
    return AnomalyEvent(
        product_id=101,
        market_id=1,
        anomaly_type="acos_worse",
        severity="high",
        object_type="keyword",
        object_id="SNAPSHOT-KW",
        object_name="snapshot high acos",
        period_start="2026-05-12",
        period_end="2026-06-10",
        status="pending",
        rule_result_json=json.dumps(rule_result, ensure_ascii=False),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )


def main() -> None:
    init_db()
    with SessionLocal() as db:
        db.add(_make_anomaly())
        db.commit()

        result = generate_suggestions(db=db, market_id=1, status="pending")
        if result.get("status") != "success" or result.get("suggestions_generated") != 1:
            raise SystemExit(f"status=failed reason=unexpected_generate_result result={result}")

        suggestion = db.execute(select(AiSuggestion)).scalar_one()
        if "产品经营背景" not in suggestion.evidence_summary:
            raise SystemExit(f"status=failed reason=missing_business_context summary={suggestion.evidence_summary}")
        for marker in ["销售额 321.45", "订单 7", "Sessions 456", "净利 44.4"]:
            if marker not in suggestion.evidence_summary:
                raise SystemExit(f"status=failed reason=missing_summary_marker marker={marker}")

        source_trace = json.loads(suggestion.source_trace_json)
        context_snapshot = source_trace.get("source_context", {}).get("product_sales_snapshot")
        evidence_snapshot = source_trace.get("evidence", {}).get("product_sales_snapshot")
        if not isinstance(context_snapshot, dict):
            raise SystemExit("status=failed reason=missing_context_snapshot")
        if context_snapshot != evidence_snapshot:
            raise SystemExit("status=failed reason=context_snapshot_mismatch")
        if _contains_forbidden_execution_key(source_trace):
            raise SystemExit("status=failed reason=contains_execution_field")

        print(
            {
                "status": "success",
                "suggestion_id": suggestion.id,
                "summary": suggestion.evidence_summary,
                "snapshot_sales": context_snapshot["sales"],
            }
        )


if __name__ == "__main__":
    main()
