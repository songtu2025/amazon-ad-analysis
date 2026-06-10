from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.models.anomaly import AnomalyEvent
from app.models.product import ProductGoal
from app.models.suggestion import AiSuggestion
from app.services.rule_service import (
    DEFAULT_MIN_CLICKS,
    DEFAULT_MIN_SPEND,
    generate_acos_worse_anomalies,
    generate_clicks_no_orders_anomalies,
    generate_cvr_drop_anomalies,
    generate_impression_low_anomalies,
    generate_inventory_goal_conflict_anomalies,
    generate_search_terms_clicks_no_orders_anomalies,
    generate_spend_spike_anomalies,
)


router = APIRouter()

GOAL_TYPES = {"test_keywords", "scale", "profit", "rank_carryover", "clear_inventory", "stop_loss"}
SUGGESTION_LEVELS = {"adoptable", "small_test", "observe", "blocked"}
ANOMALY_STATUSES = {"pending", "observing", "handled"}


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期 start_date 必须早于或等于结束日期 end_date")


def _validate_market_id(market_id: int | None) -> None:
    if market_id is not None and market_id <= 0:
        raise HTTPException(status_code=400, detail="店铺 / 站点 ID market_id 必须大于 0")


def _validate_product_id(product_id: int | None) -> None:
    if product_id is not None and product_id <= 0:
        raise HTTPException(status_code=400, detail="产品 ID product_id 必须大于 0")


def _validate_anomaly_id(anomaly_id: int) -> None:
    if anomaly_id <= 0:
        raise HTTPException(status_code=400, detail="异常事件 ID anomaly_id 必须大于 0")


def _anomaly_payload(anomaly: AnomalyEvent) -> dict[str, object]:
    return {
        "id": anomaly.id,
        "product_id": anomaly.product_id,
        "market_id": anomaly.market_id,
        "anomaly_type": anomaly.anomaly_type,
        "severity": anomaly.severity,
        "object_type": anomaly.object_type,
        "object_id": anomaly.object_id,
        "object_name": anomaly.object_name,
        "period_start": anomaly.period_start,
        "period_end": anomaly.period_end,
        "status": anomaly.status,
        "rule_result_json": anomaly.rule_result_json,
        "evidence_json": anomaly.evidence_json,
        "created_at": anomaly.created_at.isoformat(),
        "updated_at": anomaly.updated_at.isoformat(),
    }


@router.get("")
def list_anomalies(
    market_id: int | None = None,
    product_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    _validate_product_id(product_id)
    filters = []
    if market_id is not None:
        filters.append(AnomalyEvent.market_id == market_id)
    if product_id is not None:
        filters.append(AnomalyEvent.product_id == product_id)
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
        filters.append(AnomalyEvent.id.in_(select(AiSuggestion.anomaly_event_id).where(AiSuggestion.suggestion_level == suggestion_level)))
    if status:
        if status not in ANOMALY_STATUSES:
            raise HTTPException(status_code=400, detail="异常状态 status 不在第一版支持范围内")
        filters.append(AnomalyEvent.status == status)
    if start_date is not None:
        filters.append(AnomalyEvent.period_start >= start_date.isoformat())
    if end_date is not None:
        filters.append(AnomalyEvent.period_end <= end_date.isoformat())

    stmt = select(AnomalyEvent).where(*filters).order_by(AnomalyEvent.created_at.desc(), AnomalyEvent.id.desc())
    return [_anomaly_payload(anomaly) for anomaly in db.execute(stmt).scalars().all()]


@router.get("/{anomaly_id}")
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    _validate_anomaly_id(anomaly_id)
    anomaly = db.get(AnomalyEvent, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="异常事件不存在")
    return _anomaly_payload(anomaly)


@router.post("/generate")
def generate_anomalies(
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_clicks: int = DEFAULT_MIN_CLICKS,
    min_spend: float = DEFAULT_MIN_SPEND,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    settings = get_settings()
    selected_market_id = market_id if market_id is not None else (settings.market_ids[0] if settings.market_ids else None)
    if selected_market_id is None:
        raise HTTPException(status_code=400, detail="请先在 .env 中配置 GERPGO_MARKET_IDS")
    _validate_market_id(selected_market_id)
    if min_clicks < 0:
        raise HTTPException(status_code=400, detail="最小点击数 min_clicks 必须大于或等于 0")
    if min_spend < 0:
        raise HTTPException(status_code=400, detail="最小花费 min_spend 必须大于或等于 0")

    clicks_result = generate_clicks_no_orders_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
        min_clicks=min_clicks,
        min_spend=min_spend,
    )
    search_terms_clicks_result = generate_search_terms_clicks_no_orders_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
        min_clicks=min_clicks,
        min_spend=min_spend,
    )
    acos_result = generate_acos_worse_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
    )
    spend_result = generate_spend_spike_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
    )
    cvr_result = generate_cvr_drop_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
    )
    impression_result = generate_impression_low_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
    )
    inventory_result = generate_inventory_goal_conflict_anomalies(
        db=db,
        market_id=selected_market_id,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "status": "success",
        "market_id": selected_market_id,
        "period_start": clicks_result["period_start"],
        "period_end": clicks_result["period_end"],
        "rules": [
            clicks_result,
            search_terms_clicks_result,
            acos_result,
            spend_result,
            cvr_result,
            impression_result,
            inventory_result,
        ],
    }
