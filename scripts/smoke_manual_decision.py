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

from sqlalchemy import select  # noqa: E402

from app.api.routes.decisions import list_decisions  # noqa: E402
from app.api.routes.suggestions import DecisionIn, create_decision  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402
from app.models.decision import ManualDecision  # noqa: E402
from app.models.suggestion import AiSuggestion  # noqa: E402


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


def _make_anomaly(index: int) -> AnomalyEvent:
    now = datetime.now()
    evidence = {
        "period": {"start": "2026-05-28", "end": "2026-06-10"},
        "market_id": 1,
        "keyword_id": f"SMOKE-KW-{index}",
        "keyword_text": f"smoke keyword {index}",
        "clicks": 10,
        "cost": 20.0,
        "orders": 0,
    }
    rule_result = {
        "anomaly_type": "clicks_no_orders",
        "severity": "high",
        "suggestion_level": "small_test",
        "object_type": "keyword",
        "object_id": f"SMOKE-KW-{index}",
        "matched_rules": [
            {
                "rule": "clicks_no_orders",
                "result": "failed",
                "message": "smoke 验证人工确认流程",
            }
        ],
        "blocked_rules": [],
        "evidence": evidence,
    }
    return AnomalyEvent(
        product_id=101,
        market_id=1,
        anomaly_type="clicks_no_orders",
        severity="high",
        object_type="keyword",
        object_id=f"SMOKE-KW-{index}",
        object_name=f"smoke keyword {index}",
        period_start="2026-05-28",
        period_end="2026-06-10",
        status="pending",
        rule_result_json=json.dumps(rule_result, ensure_ascii=False),
        evidence_json=json.dumps(evidence, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )


def _make_suggestion(anomaly_id: int, index: int) -> AiSuggestion:
    now = datetime.now()
    source_trace = {
        "anomaly_event_id": anomaly_id,
        "anomaly_type": "clicks_no_orders",
        "recommended_manual_decision": "adopt_with_changes",
        "source_context": {"market_id": 1, "object_id": f"SMOKE-KW-{index}"},
        "rule_result": {"matched_rules": [{"rule": "clicks_no_orders"}]},
        "evidence": {"clicks": 10, "orders": 0},
    }
    return AiSuggestion(
        anomaly_event_id=anomaly_id,
        suggestion_level="small_test",
        suggested_action="人工确认后再处理该建议，不自动执行广告动作。",
        title=f"smoke suggestion {index}",
        summary="用于验证人工确认流程。",
        reasoning="基于异常事件证据生成。",
        risk_note="任何处理都需要运营人工确认。",
        evidence_summary="点击 10，订单 0",
        recommended_manual_decision="adopt_with_changes",
        source_trace_json=json.dumps(source_trace, ensure_ascii=False),
        ai_model="rule-placeholder",
        created_at=now,
        updated_at=now,
    )


def _seed_suggestions(db) -> list[int]:
    suggestion_ids = []
    for index in range(1, 5):
        anomaly = _make_anomaly(index)
        db.add(anomaly)
        db.flush()
        suggestion = _make_suggestion(anomaly.id, index)
        db.add(suggestion)
        db.flush()
        suggestion_ids.append(suggestion.id)
    db.commit()
    return suggestion_ids


def _assert_decision_response(payload: dict[str, Any], decision_type: str, expected_status: str) -> dict[str, Any]:
    if payload.get("anomaly_status") != expected_status:
        raise SystemExit(
            f"status=failed decision_type={decision_type} expected_status={expected_status} "
            f"actual_status={payload.get('anomaly_status')}"
        )
    decision = payload.get("decision") or {}
    if decision.get("decision_type") != decision_type:
        raise SystemExit(f"status=failed decision_type={decision_type} reason=decision_type_mismatch")
    if not decision.get("operator_name"):
        raise SystemExit(f"status=failed decision_type={decision_type} reason=missing_operator")
    if _contains_forbidden_execution_key(payload):
        raise SystemExit(f"status=failed decision_type={decision_type} reason=contains_execution_field")
    return payload


def main() -> None:
    init_db()
    with SessionLocal() as db:
        suggestion_ids = _seed_suggestions(db)
        requests = [
            (
                suggestion_ids[0],
                "adopt",
                DecisionIn(decision_type="adopt", operator_name="smoke-operator"),
                "handled",
            ),
            (
                suggestion_ids[1],
                "adopt_with_changes",
                DecisionIn(
                    decision_type="adopt_with_changes",
                    modified_action="人工确认后小幅调整建议，不自动执行。",
                    reason="保守测试",
                    operator_name="smoke-operator",
                ),
                "handled",
            ),
            (
                suggestion_ids[2],
                "reject",
                DecisionIn(decision_type="reject", reason="证据不足，暂不采纳", operator_name="smoke-operator"),
                "handled",
            ),
            (
                suggestion_ids[3],
                "observe",
                DecisionIn(decision_type="observe", observe_period="7d", operator_name="smoke-operator"),
                "observing",
            ),
        ]
        for suggestion_id, decision_type, payload, expected_status in requests:
            response_payload = create_decision(suggestion_id=suggestion_id, payload=payload, db=db)
            _assert_decision_response(response_payload, decision_type, expected_status)

        decisions = list_decisions(operator_name="smoke-operator", db=db)
        if len(decisions) != 4:
            raise SystemExit(f"status=failed check=list_decisions expected=4 actual={len(decisions)}")
        if _contains_forbidden_execution_key(decisions):
            raise SystemExit("status=failed check=list_decisions reason=contains_execution_field")

        saved_decisions = db.execute(select(ManualDecision).order_by(ManualDecision.id)).scalars().all()
        if len(saved_decisions) != 4:
            raise SystemExit(f"status=failed reason=decision_not_saved count={len(saved_decisions)}")

        print(
            {
                "status": "success",
                "decisions_created": len(saved_decisions),
                "decision_types": [decision.decision_type for decision in saved_decisions],
                "operator_name": "smoke-operator",
            }
        )


if __name__ == "__main__":
    main()
