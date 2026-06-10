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
from app.services.suggestion_service import PLACEHOLDER_MODEL, generate_suggestions  # noqa: E402


REQUIRED_FIELDS = {
    "suggestion_level",
    "title",
    "summary",
    "reasoning",
    "risk_note",
    "evidence_summary",
    "recommended_manual_decision",
    "source_trace_json",
}

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

MANUAL_DECISIONS = {"adopt", "adopt_with_changes", "reject", "observe"}


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


def _make_anomaly(
    *,
    anomaly_type: str,
    suggestion_level: str,
    object_id: str,
    object_name: str,
) -> AnomalyEvent:
    now = datetime.now()
    evidence = {
        "period": {"start": "2026-05-28", "end": "2026-06-10"},
        "market_id": 1,
        "product_id": 101,
        "product_goal": "profit",
        "campaign_id": "SMOKE-CAMPAIGN",
        "campaign_name": "smoke campaign",
        "ad_group_id": "SMOKE-ADGROUP",
        "ad_group_name": "smoke ad group",
        "keyword_id": object_id,
        "keyword_text": object_name,
        "match_type": "exact",
        "clicks": 12,
        "cost": 24.0,
        "orders": 0,
        "sales": 0.0,
        "acos": None,
        "target_acos": 0.3,
    }
    rule_result = {
        "anomaly_type": anomaly_type,
        "severity": "high",
        "suggestion_level": suggestion_level,
        "object_type": "keyword",
        "object_id": object_id,
        "matched_rules": [
            {
                "rule": anomaly_type,
                "result": "failed",
                "message": "smoke 验证 AI 建议结构化输出",
            }
        ],
        "blocked_rules": [],
        "evidence": evidence,
    }
    return AnomalyEvent(
        product_id=101,
        market_id=1,
        anomaly_type=anomaly_type,
        severity="high",
        object_type="keyword",
        object_id=object_id,
        object_name=object_name,
        period_start="2026-05-28",
        period_end="2026-06-10",
        status="pending",
        rule_result_json=json.dumps(rule_result, ensure_ascii=False),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )


def _assert_suggestion_payload(suggestion: AiSuggestion) -> None:
    missing = [
        field
        for field in REQUIRED_FIELDS
        if getattr(suggestion, field) is None or getattr(suggestion, field) == ""
    ]
    if missing:
        raise SystemExit(f"status=failed reason=missing_fields suggestion_id={suggestion.id} fields={missing}")

    if suggestion.recommended_manual_decision not in MANUAL_DECISIONS:
        raise SystemExit(
            "status=failed reason=invalid_recommended_manual_decision "
            f"suggestion_id={suggestion.id} value={suggestion.recommended_manual_decision}"
        )
    if suggestion.ai_model != PLACEHOLDER_MODEL:
        raise SystemExit(f"status=failed reason=unexpected_ai_model suggestion_id={suggestion.id}")

    source_trace = json.loads(suggestion.source_trace_json)
    if source_trace.get("anomaly_event_id") != suggestion.anomaly_event_id:
        raise SystemExit(f"status=failed reason=source_trace_mismatch suggestion_id={suggestion.id}")
    if not source_trace.get("rule_result") or not source_trace.get("evidence"):
        raise SystemExit(f"status=failed reason=missing_source_trace suggestion_id={suggestion.id}")
    if _contains_forbidden_execution_key(source_trace):
        raise SystemExit(f"status=failed reason=contains_execution_field suggestion_id={suggestion.id}")

    decision_text = " ".join(
        [
            suggestion.suggested_action,
            suggestion.summary or "",
            suggestion.reasoning or "",
            suggestion.risk_note or "",
        ]
    )
    if not any(marker in decision_text for marker in ["人工", "检查", "复核", "观察", "建议"]):
        raise SystemExit(f"status=failed reason=not_decision_support_text suggestion_id={suggestion.id}")


def main() -> None:
    init_db()
    with SessionLocal() as db:
        db.add_all(
            [
                _make_anomaly(
                    anomaly_type="clicks_no_orders",
                    suggestion_level="small_test",
                    object_id="SMOKE-KW-NO-ORDER",
                    object_name="smoke no order keyword",
                ),
                _make_anomaly(
                    anomaly_type="inventory_goal_conflict",
                    suggestion_level="blocked",
                    object_id="SMOKE-PRODUCT-LOW-STOCK",
                    object_name="smoke low stock product",
                ),
            ]
        )
        db.commit()

        result = generate_suggestions(db=db, market_id=1, status="pending")
        if result.get("status") != "success" or result.get("suggestions_generated") != 2:
            raise SystemExit(f"status=failed reason=unexpected_generate_result result={result}")

        suggestions = db.execute(select(AiSuggestion).order_by(AiSuggestion.id)).scalars().all()
        if len(suggestions) != 2:
            raise SystemExit(f"status=failed reason=unexpected_suggestion_count count={len(suggestions)}")

        for suggestion in suggestions:
            _assert_suggestion_payload(suggestion)

        print(
            {
                "status": "success",
                "suggestions_generated": len(suggestions),
                "ai_model": PLACEHOLDER_MODEL,
                "recommended_manual_decisions": sorted(
                    {suggestion.recommended_manual_decision for suggestion in suggestions}
                ),
            }
        )


if __name__ == "__main__":
    main()
