from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.core.database import get_db
from app.models.anomaly import AnomalyEvent
from app.models.decision import ManualDecision
from app.models.product import ProductGoal
from app.models.suggestion import AiSuggestion


router = APIRouter()

DECISION_TYPES = {"adopt", "adopt_with_changes", "reject", "observe", "handled"}
GOAL_TYPES = {"test_keywords", "scale", "profit", "rank_carryover", "clear_inventory", "stop_loss"}
SUGGESTION_LEVELS = {"adoptable", "small_test", "observe", "blocked"}


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期 start_date 必须早于或等于结束日期 end_date")


def _validate_market_id(market_id: int | None) -> None:
    if market_id is not None and market_id <= 0:
        raise HTTPException(status_code=400, detail="店铺 / 站点 ID market_id 必须大于 0")


def _validate_suggestion_id(suggestion_id: int | None) -> None:
    if suggestion_id is not None and suggestion_id <= 0:
        raise HTTPException(status_code=400, detail="建议 ID suggestion_id 必须大于 0")


def decision_payload(
    decision: ManualDecision,
    suggestion: AiSuggestion | None = None,
    anomaly: AnomalyEvent | None = None,
) -> dict[str, object]:
    return {
        "id": decision.id,
        "suggestion_id": decision.suggestion_id,
        "suggestion": None
        if suggestion is None
        else {
            "title": suggestion.title,
            "suggested_action": suggestion.suggested_action,
            "suggestion_level": suggestion.suggestion_level,
            "anomaly_event_id": suggestion.anomaly_event_id,
            "evidence_json": anomaly.evidence_json if anomaly is not None else None,
        },
        "decision_type": decision.decision_type,
        "modified_action": decision.modified_action,
        "reason": decision.reason,
        "observe_period": decision.observe_period,
        "operator_name": decision.operator_name,
        "decided_at": decision.decided_at.isoformat(),
    }


@router.get("")
def list_decisions(
    suggestion_id: int | None = None,
    decision_type: str | None = None,
    operator_name: str | None = None,
    market_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    _validate_suggestion_id(suggestion_id)
    filters = []
    if suggestion_id is not None:
        filters.append(ManualDecision.suggestion_id == suggestion_id)
    if decision_type:
        if decision_type not in DECISION_TYPES:
            raise HTTPException(status_code=400, detail="人工处理类型 decision_type 不在第一版支持范围内")
        filters.append(ManualDecision.decision_type == decision_type)
    if operator_name:
        filters.append(ManualDecision.operator_name == operator_name)
    if market_id is not None:
        filters.append(AnomalyEvent.market_id == market_id)
    if goal_type:
        if goal_type not in GOAL_TYPES:
            raise HTTPException(status_code=400, detail="产品目标 goal_type 不在第一版支持范围内")
        filters.append(AnomalyEvent.product_id.in_(select(ProductGoal.product_id).where(ProductGoal.goal_type == goal_type)))
    if not is_valid_anomaly_type(anomaly_type):
        raise HTTPException(status_code=400, detail="异常类型 anomaly_type 不在第一版支持范围内")
    anomaly_type = normalize_anomaly_type(anomaly_type)
    if anomaly_type:
        filters.append(AnomalyEvent.anomaly_type == anomaly_type)
    if suggestion_level:
        if suggestion_level not in SUGGESTION_LEVELS:
            raise HTTPException(status_code=400, detail="建议等级 suggestion_level 不在第一版支持范围内")
        filters.append(AiSuggestion.suggestion_level == suggestion_level)
    if start_date is not None:
        filters.append(ManualDecision.decided_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(ManualDecision.decided_at <= datetime.combine(end_date, time.max))

    stmt = (
        select(ManualDecision)
        .join(AiSuggestion, ManualDecision.suggestion_id == AiSuggestion.id)
        .join(AnomalyEvent, AiSuggestion.anomaly_event_id == AnomalyEvent.id)
        .where(*filters)
        .order_by(ManualDecision.decided_at.desc(), ManualDecision.id.desc())
    )
    decisions = db.execute(stmt).scalars().all()
    suggestion_ids = [decision.suggestion_id for decision in decisions]
    suggestions = {
        suggestion.id: suggestion
        for suggestion in db.execute(select(AiSuggestion).where(AiSuggestion.id.in_(suggestion_ids))).scalars().all()
    }
    anomaly_ids = [suggestion.anomaly_event_id for suggestion in suggestions.values()]
    anomalies = {
        anomaly.id: anomaly
        for anomaly in db.execute(select(AnomalyEvent).where(AnomalyEvent.id.in_(anomaly_ids))).scalars().all()
    }
    return [
        decision_payload(
            decision,
            suggestions.get(decision.suggestion_id),
            anomalies.get(suggestions[decision.suggestion_id].anomaly_event_id) if decision.suggestion_id in suggestions else None,
        )
        for decision in decisions
    ]
