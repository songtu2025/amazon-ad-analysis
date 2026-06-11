import json
from datetime import date, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.anomalies import real_anomaly_filters
from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.core.database import get_db
from app.models.ad_metrics import SpKeywordMetric
from app.models.anomaly import AnomalyEvent
from app.models.market import MarketInfo
from app.models.product import ProductGoal
from app.models.suggestion import AiSuggestion
from app.models.sync import SyncRun


router = APIRouter()

GOAL_TYPES = {"test_keywords", "scale", "profit", "rank_carryover", "clear_inventory", "stop_loss"}
SUGGESTION_LEVELS = {"adoptable", "small_test", "observe", "blocked"}


def _round(value: float | None, digits: int = 4) -> float:
    return round(float(value or 0), digits)


def _json_cost(value: str) -> float:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(loaded, dict):
        return 0.0
    cost = loaded.get("cost")
    return float(cost) if isinstance(cost, int | float) else 0.0


def _binding_status(total_rows: int, bound_rows: int) -> str:
    if total_rows <= 0:
        return "unknown"
    if bound_rows <= 0:
        return "none"
    if bound_rows < total_rows:
        return "partial"
    return "complete"


def _market_identity(db: Session, market_ids: list[int]) -> dict[str, object]:
    if not market_ids:
        return {
            "market_id": None,
            "market_ids": [],
            "market_name": None,
            "country_code": None,
            "identity_status": "unknown",
        }
    if len(market_ids) > 1:
        return {
            "market_id": None,
            "market_ids": market_ids,
            "market_name": "多店铺汇总",
            "country_code": None,
            "identity_status": "multiple",
        }
    market_id = market_ids[0]
    info = db.get(MarketInfo, market_id)
    return {
        "market_id": market_id,
        "market_ids": market_ids,
        "market_name": info.market_name if info else None,
        "country_code": info.country_code if info else None,
        "raw_name": info.raw_name if info else None,
        "identity_status": "matched" if info and info.market_name else "name_missing",
    }


def _date_range(start_date: date | None, end_date: date | None) -> tuple[str, str]:
    selected_end = end_date or date.today()
    selected_start = start_date or selected_end - timedelta(days=13)
    return selected_start.isoformat(), selected_end.isoformat()


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期 start_date 必须早于或等于结束日期 end_date")


def _validate_market_id(market_id: int | None) -> None:
    if market_id is not None and market_id <= 0:
        raise HTTPException(status_code=400, detail="店铺 / 站点 ID market_id 必须大于 0")


def _metric_filters(
    market_id: int | None,
    goal_type: str | None,
    period_start: str,
    period_end: str,
) -> list[object]:
    filters: list[object] = [
        SpKeywordMetric.data_date >= period_start,
        SpKeywordMetric.data_date <= period_end,
    ]
    if market_id is not None:
        filters.append(SpKeywordMetric.market_id == market_id)
    if goal_type:
        filters.append(SpKeywordMetric.product_id.in_(select(ProductGoal.product_id).where(ProductGoal.goal_type == goal_type)))
    return filters


def _anomaly_filters(
    market_id: int | None,
    goal_type: str | None,
    anomaly_type: str | None,
    suggestion_level: str | None,
    period_start: str,
    period_end: str,
) -> list[object]:
    filters: list[object] = [
        AnomalyEvent.period_start >= period_start,
        AnomalyEvent.period_end <= period_end,
        *real_anomaly_filters(),
    ]
    if market_id is not None:
        filters.append(AnomalyEvent.market_id == market_id)
    if goal_type:
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
    return filters


@router.get("/summary")
def dashboard_summary(
    market_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    if goal_type and goal_type not in GOAL_TYPES:
        raise HTTPException(status_code=400, detail="产品目标 goal_type 不在第一版支持范围内")
    period_start, period_end = _date_range(start_date, end_date)
    metric_filters = _metric_filters(market_id, goal_type, period_start, period_end)
    anomaly_filters = _anomaly_filters(market_id, goal_type, anomaly_type, suggestion_level, period_start, period_end)

    latest_sync = db.execute(select(SyncRun).order_by(SyncRun.started_at.desc(), SyncRun.id.desc()).limit(1)).scalar_one_or_none()
    totals = db.execute(
        select(
            func.count(SpKeywordMetric.id),
            func.coalesce(func.sum(SpKeywordMetric.impressions), 0),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0),
        ).where(*metric_filters)
    ).one()

    rows_count, impressions, clicks, cost, orders, sales = totals
    market_ids = [
        int(value)
        for value in db.execute(
            select(SpKeywordMetric.market_id)
            .where(*metric_filters)
            .group_by(SpKeywordMetric.market_id)
            .order_by(SpKeywordMetric.market_id)
        ).scalars().all()
        if value is not None
    ]
    bound_rows = db.execute(
        select(func.coalesce(func.sum(case((SpKeywordMetric.product_id.is_not(None), 1), else_=0)), 0)).where(*metric_filters)
    ).scalar_one()
    acos = float(cost or 0) / float(sales or 0) if sales else 0
    cvr = float(orders or 0) / float(clicks or 0) if clicks else 0

    anomaly_counts = db.execute(
        select(
            func.count(AnomalyEvent.id),
            func.count(distinct(AnomalyEvent.product_id)),
            func.coalesce(func.sum(case((AnomalyEvent.severity == "high", 1), else_=0)), 0),
        ).where(*anomaly_filters)
    ).one()

    pending_suggestions = db.execute(
        select(func.count(distinct(AiSuggestion.id)))
        .join(AnomalyEvent, AiSuggestion.anomaly_event_id == AnomalyEvent.id)
        .where(AnomalyEvent.status == "pending", *anomaly_filters)
    ).scalar_one()

    waste_anomalies = db.execute(
        select(AnomalyEvent.evidence_json).where(
            AnomalyEvent.status == "pending",
            AnomalyEvent.anomaly_type.in_(["clicks_no_orders", "spend_spike"]),
            *anomaly_filters,
        )
    ).scalars().all()
    waste_cost = sum(_json_cost(value) for value in waste_anomalies)

    trend_rows = db.execute(
        select(
            SpKeywordMetric.data_date,
            func.coalesce(func.sum(SpKeywordMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0).label("sales"),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0).label("clicks"),
        )
        .where(SpKeywordMetric.data_date.is_not(None), *metric_filters)
        .group_by(SpKeywordMetric.data_date)
        .order_by(SpKeywordMetric.data_date)
    ).all()

    trend = []
    for row in trend_rows:
        row_acos = float(row.cost or 0) / float(row.sales or 0) if row.sales else 0
        row_cvr = float(row.orders or 0) / float(row.clicks or 0) if row.clicks else 0
        trend.append(
            {
                "date": row.data_date,
                "cost": _round(row.cost, 2),
                "acos": _round(row_acos),
                "cvr": _round(row_cvr),
            }
        )

    anomaly_type_rows = db.execute(
        select(AnomalyEvent.anomaly_type, func.count(AnomalyEvent.id))
        .where(*anomaly_filters)
        .group_by(AnomalyEvent.anomaly_type)
        .order_by(func.count(AnomalyEvent.id).desc())
    ).all()

    top_campaign_rows = db.execute(
        select(
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            func.count(SpKeywordMetric.id).label("metric_rows"),
            func.count(distinct(SpKeywordMetric.ad_group_id)).label("ad_group_count"),
            func.count(distinct(SpKeywordMetric.keyword_id)).label("keyword_count"),
            func.coalesce(func.sum(SpKeywordMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0).label("sales"),
        )
        .where(*metric_filters)
        .group_by(SpKeywordMetric.campaign_id, SpKeywordMetric.campaign_name)
        .order_by(func.sum(SpKeywordMetric.cost).desc())
        .limit(8)
    ).all()

    top_campaigns = []
    for row in top_campaign_rows:
        row_acos = float(row.cost or 0) / float(row.sales or 0) if row.sales else 0
        row_cvr = float(row.orders or 0) / float(row.clicks or 0) if row.clicks else 0
        top_campaigns.append(
            {
                "campaign_id": row.campaign_id,
                "campaign_name": row.campaign_name,
                "metric_rows": int(row.metric_rows or 0),
                "ad_group_count": int(row.ad_group_count or 0),
                "keyword_count": int(row.keyword_count or 0),
                "impressions": int(row.impressions or 0),
                "clicks": int(row.clicks or 0),
                "cost": _round(row.cost, 2),
                "orders": int(row.orders or 0),
                "sales": _round(row.sales, 2),
                "acos": _round(row_acos),
                "cvr": _round(row_cvr),
            }
        )

    return {
        "sync": None
        if latest_sync is None
        else {
            "source": latest_sync.source,
            "market_id": latest_sync.market_id,
            "period_start": latest_sync.period_start,
            "period_end": latest_sync.period_end,
            "status": latest_sync.status,
            "rows_synced": latest_sync.rows_synced,
            "finished_at": latest_sync.finished_at.isoformat() if latest_sync.finished_at else None,
        },
        "period": {
            "start": period_start,
            "end": period_end,
        },
        "market": _market_identity(db, market_ids),
        "data_sources": ["SP 关键词报表", "SP 搜索词报表"],
        "product_binding": {
            "status": _binding_status(int(rows_count or 0), int(bound_rows or 0)),
            "bound_rows": int(bound_rows or 0),
            "total_rows": int(rows_count or 0),
        },
        "overview": {
            "metric_rows": int(rows_count or 0),
            "impressions": int(impressions or 0),
            "clicks": int(clicks or 0),
            "cost": _round(cost, 2),
            "orders": int(orders or 0),
            "sales": _round(sales, 2),
            "acos": _round(acos),
            "cvr": _round(cvr),
            "anomaly_count": int(anomaly_counts[0] or 0),
            "anomaly_product_count": int(anomaly_counts[1] or 0),
            "high_risk_count": int(anomaly_counts[2] or 0),
            "pending_suggestion_count": int(pending_suggestions or 0),
            "waste_cost": _round(waste_cost, 2),
        },
        "trend": trend,
        "top_campaigns": top_campaigns,
        "anomaly_types": [{"anomaly_type": row[0], "count": int(row[1] or 0)} for row in anomaly_type_rows],
    }


@router.get("/health")
def dashboard_health(
    market_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    summary = dashboard_summary(
        market_id=market_id,
        goal_type=goal_type,
        anomaly_type=anomaly_type,
        suggestion_level=suggestion_level,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )
    return {
        "sync": summary["sync"],
        "period": summary["period"],
        "market": summary["market"],
        "data_sources": summary["data_sources"],
        "product_binding": summary["product_binding"],
        "overview": summary["overview"],
        "top_campaigns": summary["top_campaigns"],
    }


@router.get("/trends")
def dashboard_trends(
    market_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    summary = dashboard_summary(
        market_id=market_id,
        goal_type=goal_type,
        anomaly_type=anomaly_type,
        suggestion_level=suggestion_level,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )
    return {
        "period": summary["period"],
        "trend": summary["trend"],
    }


@router.get("/anomaly-summary")
def dashboard_anomaly_summary(
    market_id: int | None = None,
    goal_type: str | None = None,
    anomaly_type: str | None = None,
    suggestion_level: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    summary = dashboard_summary(
        market_id=market_id,
        goal_type=goal_type,
        anomaly_type=anomaly_type,
        suggestion_level=suggestion_level,
        start_date=start_date,
        end_date=end_date,
        db=db,
    )
    overview = summary["overview"]
    return {
        "period": summary["period"],
        "anomaly_count": overview["anomaly_count"],
        "anomaly_product_count": overview["anomaly_product_count"],
        "high_risk_count": overview["high_risk_count"],
        "pending_suggestion_count": overview["pending_suggestion_count"],
        "waste_cost": overview["waste_cost"],
        "anomaly_types": summary["anomaly_types"],
    }
