from datetime import datetime

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.models.anomaly import AnomalyEvent
from app.models.decision import ManualDecision
from app.models.product import ProductGoal
from app.models.suggestion import AiSuggestion
from app.api.routes.decisions import decision_payload
from app.services.suggestion_service import generate_suggestions


router = APIRouter()

DECISION_TYPES = {"adopt", "adopt_with_changes", "reject", "observe", "handled"}
OBSERVE_PERIODS = {"7d", "14d"}
GOAL_TYPES = {"test_keywords", "scale", "profit", "rank_carryover", "clear_inventory", "stop_loss"}
SUGGESTION_LEVELS = {"adoptable", "small_test", "observe", "blocked"}
ANOMALY_STATUSES = {"pending", "observing", "handled"}


class DecisionIn(BaseModel):
    decision_type: str
    modified_action: str | None = None
    reason: str | None = None
    observe_period: str | None = None
    operator_name: str | None = None


def _not_blank(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期 start_date 必须早于或等于结束日期 end_date")


def _validate_market_id(market_id: int | None) -> None:
    if market_id is not None and market_id <= 0:
        raise HTTPException(status_code=400, detail="店铺 / 站点 ID market_id 必须大于 0")


def _validate_product_id(product_id: int | None) -> None:
    if product_id is not None and product_id <= 0:
        raise HTTPException(status_code=400, detail="产品 ID product_id 必须大于 0")


def _validate_suggestion_id(suggestion_id: int) -> None:
    if suggestion_id <= 0:
        raise HTTPException(status_code=400, detail="建议 ID suggestion_id 必须大于 0")


def _validate_anomaly_event_id(anomaly_event_id: int | None) -> None:
    if anomaly_event_id is not None and anomaly_event_id <= 0:
        raise HTTPException(status_code=400, detail="异常事件 ID anomaly_event_id 必须大于 0")


def _suggestion_payload(suggestion: AiSuggestion) -> dict[str, object]:
    return {
        "id": suggestion.id,
        "anomaly_event_id": suggestion.anomaly_event_id,
        "suggestion_level": suggestion.suggestion_level,
        "suggested_action": suggestion.suggested_action,
        "title": suggestion.title,
        "summary": suggestion.summary,
        "reasoning": suggestion.reasoning,
        "risk_note": suggestion.risk_note,
        "evidence_summary": suggestion.evidence_summary,
        "recommended_manual_decision": suggestion.recommended_manual_decision,
        "source_trace_json": suggestion.source_trace_json,
        "ai_model": suggestion.ai_model,
        "created_at": suggestion.created_at.isoformat(),
        "updated_at": suggestion.updated_at.isoformat(),
    }


@router.post("/generate")
def generate_ai_suggestions(
    market_id: int | None = None,
    product_id: int | None = None,
    anomaly_type: str | None = None,
    status: str = "pending",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_market_id(market_id)
    _validate_product_id(product_id)
    if status not in ANOMALY_STATUSES:
        raise HTTPException(status_code=400, detail="建议状态 status 不在第一版支持范围内")
    if not is_valid_anomaly_type(anomaly_type):
        raise HTTPException(status_code=400, detail="异常类型 anomaly_type 不在第一版支持范围内")
    anomaly_type = normalize_anomaly_type(anomaly_type)
    return generate_suggestions(
        db=db,
        market_id=market_id,
        product_id=product_id,
        anomaly_type=anomaly_type,
        status=status,
    )


@router.get("")
def list_suggestions(
    anomaly_event_id: int | None = None,
    market_id: int | None = None,
    product_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    status: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    _validate_product_id(product_id)
    _validate_anomaly_event_id(anomaly_event_id)
    filters = []
    anomaly_filters = []
    if anomaly_event_id is not None:
        filters.append(AiSuggestion.anomaly_event_id == anomaly_event_id)
    if market_id is not None:
        anomaly_filters.append(AnomalyEvent.market_id == market_id)
    if product_id is not None:
        anomaly_filters.append(AnomalyEvent.product_id == product_id)
    if goal_type:
        if goal_type not in GOAL_TYPES:
            raise HTTPException(status_code=400, detail="产品目标 goal_type 不在第一版支持范围内")
        anomaly_filters.append(AnomalyEvent.product_id.in_(select(ProductGoal.product_id).where(ProductGoal.goal_type == goal_type)))
    if not is_valid_anomaly_type(anomaly_type):
        raise HTTPException(status_code=400, detail="异常类型 anomaly_type 不在第一版支持范围内")
    anomaly_type = normalize_anomaly_type(anomaly_type)
    if anomaly_type:
        anomaly_filters.append(AnomalyEvent.anomaly_type == anomaly_type)
    if status:
        if status not in ANOMALY_STATUSES:
            raise HTTPException(status_code=400, detail="建议状态 status 不在第一版支持范围内")
        anomaly_filters.append(AnomalyEvent.status == status)
    if start_date is not None:
        anomaly_filters.append(AnomalyEvent.period_start >= start_date.isoformat())
    if end_date is not None:
        anomaly_filters.append(AnomalyEvent.period_end <= end_date.isoformat())
    if anomaly_filters:
        filters.append(AiSuggestion.anomaly_event_id.in_(select(AnomalyEvent.id).where(*anomaly_filters)))
    if suggestion_level:
        if suggestion_level not in SUGGESTION_LEVELS:
            raise HTTPException(status_code=400, detail="建议等级 suggestion_level 不在第一版支持范围内")
        filters.append(AiSuggestion.suggestion_level == suggestion_level)

    stmt = select(AiSuggestion).where(*filters).order_by(AiSuggestion.created_at.desc(), AiSuggestion.id.desc())
    return [_suggestion_payload(suggestion) for suggestion in db.execute(stmt).scalars().all()]


@router.get("/{suggestion_id}")
def get_suggestion(suggestion_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    _validate_suggestion_id(suggestion_id)
    suggestion = db.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    return _suggestion_payload(suggestion)


@router.post("/{suggestion_id}/decision")
def create_decision(
    suggestion_id: int,
    payload: DecisionIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_suggestion_id(suggestion_id)
    if payload.decision_type not in DECISION_TYPES:
        raise HTTPException(status_code=400, detail="人工处理类型 decision_type 不在第一版支持范围内")
    if not _not_blank(payload.operator_name):
        raise HTTPException(status_code=400, detail="处理人 operator_name 必填")
    if payload.decision_type == "adopt_with_changes" and not _not_blank(payload.modified_action):
        raise HTTPException(status_code=400, detail="修改后动作 modified_action 必填")
    if payload.decision_type in {"adopt_with_changes", "reject"} and not _not_blank(payload.reason):
        raise HTTPException(status_code=400, detail="处理原因 reason 必填")
    if payload.decision_type == "observe" and payload.observe_period not in OBSERVE_PERIODS:
        raise HTTPException(status_code=400, detail="观察周期 observe_period 只能是 7d 或 14d")

    suggestion = db.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.suggestion_level == "blocked" and payload.decision_type in {"adopt", "adopt_with_changes"}:
        raise HTTPException(status_code=400, detail="禁止建议不能被采纳")

    anomaly = db.get(AnomalyEvent, suggestion.anomaly_event_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="异常事件不存在")

    now = datetime.now()
    decision = ManualDecision(
        suggestion_id=suggestion_id,
        decision_type=payload.decision_type,
        modified_action=payload.modified_action.strip() if payload.modified_action else None,
        reason=payload.reason.strip() if payload.reason else None,
        observe_period=payload.observe_period if payload.decision_type == "observe" else None,
        operator_name=payload.operator_name.strip(),
        decided_at=now,
    )
    anomaly.status = "observing" if payload.decision_type == "observe" else "handled"
    anomaly.updated_at = now
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return {
        "decision": decision_payload(decision, suggestion, anomaly),
        "anomaly_event_id": anomaly.id,
        "anomaly_status": anomaly.status,
    }
