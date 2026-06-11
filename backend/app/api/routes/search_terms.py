import json
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.ad_metrics import SpSearchTermMetric
from app.models.decision import SearchTermCandidateDecision, SearchTermGroupDecision
from app.services.search_term_analysis_service import (
    CANDIDATE_LABELS,
    PERFORMANCE_LABELS,
    SEMANTIC_LABELS,
    analyze_search_terms,
    build_product_search_term_readiness,
    build_search_term_candidates,
)


router = APIRouter()

CANDIDATE_DECISION_TYPES = {"adopt_with_changes", "reject", "observe"}
OBSERVE_PERIODS = {"7d", "14d"}
REVIEW_PERIOD_DAYS = {"7d": 7, "14d": 14}


class SearchTermCandidateDecisionIn(BaseModel):
    candidate_id: str
    decision_type: str
    modified_action: str | None = None
    reason: str | None = None
    observe_period: str | None = None
    operator_name: str | None = None
    market_id: int | None = None
    product_id: int | None = None
    semantic_category: str | None = None
    performance_status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    min_clicks: int = 10
    min_spend: float = 10.0
    target_acos: float = 0.35
    limit: int = 200


class SearchTermGroupDecisionIn(BaseModel):
    group_key: str
    decision_type: str
    modified_action: str | None = None
    reason: str | None = None
    observe_period: str | None = None
    operator_name: str | None = None
    market_id: int | None = None
    product_id: int | None = None
    semantic_category: str | None = None
    performance_status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    min_clicks: int = 10
    min_spend: float = 10.0
    target_acos: float = 0.35
    limit: int = 200


def _date_range(start_date: date | None, end_date: date | None) -> tuple[str, str]:
    selected_end = end_date or date.today()
    selected_start = start_date or selected_end - timedelta(days=29)
    return selected_start.isoformat(), selected_end.isoformat()


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期 start_date 必须早于或等于结束日期 end_date")


def _validate_positive_int(name: str, value: int | None) -> None:
    if value is not None and value <= 0:
        raise HTTPException(status_code=400, detail=f"{name} 必须大于 0")


def _not_blank(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _validate_candidate_filters(
    *,
    market_id: int | None,
    product_id: int | None,
    semantic_category: str | None,
    performance_status: str | None,
    min_clicks: int,
    min_spend: float,
    target_acos: float,
    limit: int,
) -> None:
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    if min_clicks < 0:
        raise HTTPException(status_code=400, detail="min_clicks 必须大于或等于 0")
    if min_spend < 0:
        raise HTTPException(status_code=400, detail="min_spend 必须大于或等于 0")
    if target_acos < 0:
        raise HTTPException(status_code=400, detail="target_acos 必须大于或等于 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit 必须大于 0")
    if semantic_category and semantic_category not in SEMANTIC_LABELS:
        raise HTTPException(status_code=400, detail="semantic_category 不在第一版支持范围内")
    if performance_status and performance_status not in PERFORMANCE_LABELS:
        raise HTTPException(status_code=400, detail="performance_status 不在第一版支持范围内")


def _candidate_decision_payload(decision: SearchTermCandidateDecision) -> dict[str, object]:
    try:
        candidate_snapshot = json.loads(decision.candidate_snapshot_json or "{}")
    except json.JSONDecodeError:
        candidate_snapshot = {}
    return {
        "id": decision.id,
        "candidate_id": decision.candidate_id,
        "candidate_type": decision.candidate_type,
        "search_term": decision.search_term,
        "market_id": decision.market_id,
        "product_id": decision.product_id,
        "period_start": decision.period_start,
        "period_end": decision.period_end,
        "decision_type": decision.decision_type,
        "modified_action": decision.modified_action,
        "reason": decision.reason,
        "observe_period": decision.observe_period,
        "operator_name": decision.operator_name,
        "candidate_snapshot": candidate_snapshot,
        "decided_at": decision.decided_at.isoformat(),
    }


def _group_decision_payload(decision: SearchTermGroupDecision) -> dict[str, object]:
    try:
        group_snapshot = json.loads(decision.group_snapshot_json or "{}")
    except json.JSONDecodeError:
        group_snapshot = {}
    return {
        "id": decision.id,
        "group_key": decision.group_key,
        "group_label": decision.group_label,
        "market_id": decision.market_id,
        "product_id": decision.product_id,
        "semantic_category": decision.semantic_category,
        "performance_status": decision.performance_status,
        "period_start": decision.period_start,
        "period_end": decision.period_end,
        "decision_type": decision.decision_type,
        "modified_action": decision.modified_action,
        "reason": decision.reason,
        "observe_period": decision.observe_period,
        "operator_name": decision.operator_name,
        "group_snapshot": group_snapshot,
        "decided_at": decision.decided_at.isoformat(),
    }


def _metric_payload(*, impressions: object, clicks: object, cost: object, orders: object, sales: object, metric_rows: object = 0) -> dict[str, object]:
    impressions_value = int(impressions or 0)
    clicks_value = int(clicks or 0)
    cost_value = round(float(cost or 0), 2)
    orders_value = int(orders or 0)
    sales_value = round(float(sales or 0), 2)
    return {
        "metric_rows": int(metric_rows or 0),
        "impressions": impressions_value,
        "clicks": clicks_value,
        "cost": cost_value,
        "orders": orders_value,
        "sales": sales_value,
        "acos": round(cost_value / sales_value, 4) if sales_value else 0,
        "cvr": round(orders_value / clicks_value, 4) if clicks_value else 0,
    }


def _snapshot_metrics(decision: SearchTermCandidateDecision) -> dict[str, object]:
    try:
        snapshot = json.loads(decision.candidate_snapshot_json or "{}")
    except json.JSONDecodeError:
        snapshot = {}
    metrics = snapshot.get("metrics") if isinstance(snapshot.get("metrics"), dict) else {}
    return _metric_payload(
        impressions=metrics.get("impressions"),
        clicks=metrics.get("clicks"),
        cost=metrics.get("cost"),
        orders=metrics.get("orders"),
        sales=metrics.get("sales"),
        metric_rows=metrics.get("metric_rows"),
    )


def _group_snapshot_metrics(decision: SearchTermGroupDecision) -> dict[str, object]:
    try:
        snapshot = json.loads(decision.group_snapshot_json or "{}")
    except json.JSONDecodeError:
        snapshot = {}
    return _metric_payload(
        impressions=snapshot.get("impressions"),
        clicks=snapshot.get("clicks"),
        cost=snapshot.get("cost"),
        orders=snapshot.get("orders"),
        sales=snapshot.get("sales"),
        metric_rows=snapshot.get("terms") or snapshot.get("metric_rows"),
    )


def _group_metrics_from_summary(group: dict[str, object] | None) -> dict[str, object]:
    if not group:
        return _metric_payload(impressions=0, clicks=0, cost=0, orders=0, sales=0, metric_rows=0)
    return _metric_payload(
        impressions=group.get("impressions"),
        clicks=group.get("clicks"),
        cost=group.get("cost"),
        orders=group.get("orders"),
        sales=group.get("sales"),
        metric_rows=group.get("terms") or group.get("metric_rows"),
    )


def _delta_metrics(before_metrics: dict[str, object], after_metrics: dict[str, object]) -> dict[str, object]:
    return {
        "clicks_delta": int(after_metrics["clicks"] or 0) - int(before_metrics["clicks"] or 0),
        "cost_delta": round(float(after_metrics["cost"] or 0) - float(before_metrics["cost"] or 0), 2),
        "orders_delta": int(after_metrics["orders"] or 0) - int(before_metrics["orders"] or 0),
        "sales_delta": round(float(after_metrics["sales"] or 0) - float(before_metrics["sales"] or 0), 2),
        "acos_delta": round(float(after_metrics["acos"] or 0) - float(before_metrics["acos"] or 0), 4),
        "cvr_delta": round(float(after_metrics["cvr"] or 0) - float(before_metrics["cvr"] or 0), 4),
    }


def _review_result(before: dict[str, object], after: dict[str, object]) -> str:
    if int(after["metric_rows"] or 0) <= 0:
        return "data_pending"
    before_orders = int(before["orders"] or 0)
    after_orders = int(after["orders"] or 0)
    before_acos = float(before["acos"] or 0)
    after_acos = float(after["acos"] or 0)
    if after_orders >= before_orders and after_acos < before_acos:
        return "improved"
    if after_orders < before_orders or (before_acos > 0 and after_acos > before_acos):
        return "worse"
    return "unchanged"


@router.get("/analysis")
def search_term_analysis(
    market_id: int | None = None,
    product_id: int | None = None,
    semantic_category: str | None = None,
    performance_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_clicks: int = 10,
    min_spend: float = 10.0,
    target_acos: float = 0.35,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    if min_clicks < 0:
        raise HTTPException(status_code=400, detail="min_clicks 必须大于或等于 0")
    if min_spend < 0:
        raise HTTPException(status_code=400, detail="min_spend 必须大于或等于 0")
    if target_acos < 0:
        raise HTTPException(status_code=400, detail="target_acos 必须大于或等于 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit 必须大于 0")
    if semantic_category and semantic_category not in SEMANTIC_LABELS:
        raise HTTPException(status_code=400, detail="semantic_category 不在第一版支持范围内")
    if performance_status and performance_status not in PERFORMANCE_LABELS:
        raise HTTPException(status_code=400, detail="performance_status 不在第一版支持范围内")
    period_start, period_end = _date_range(start_date, end_date)
    return analyze_search_terms(
        db,
        market_id=market_id,
        product_id=product_id,
        period_start=period_start,
        period_end=period_end,
        semantic_category=semantic_category,
        performance_status=performance_status,
        min_clicks=min_clicks,
        min_spend=min_spend,
        target_acos=target_acos,
        limit=limit,
    )


@router.get("/product-readiness")
def search_term_product_readiness(
    market_id: int | None = None,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    period_start, period_end = _date_range(start_date, end_date)
    return build_product_search_term_readiness(
        db,
        market_id=market_id,
        product_id=product_id,
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/candidates")
def search_term_candidates(
    market_id: int | None = None,
    product_id: int | None = None,
    semantic_category: str | None = None,
    performance_status: str | None = None,
    candidate_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_clicks: int = 10,
    min_spend: float = 10.0,
    target_acos: float = 0.35,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    if min_clicks < 0:
        raise HTTPException(status_code=400, detail="min_clicks 必须大于或等于 0")
    if min_spend < 0:
        raise HTTPException(status_code=400, detail="min_spend 必须大于或等于 0")
    if target_acos < 0:
        raise HTTPException(status_code=400, detail="target_acos 必须大于或等于 0")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit 必须大于 0")
    if semantic_category and semantic_category not in SEMANTIC_LABELS:
        raise HTTPException(status_code=400, detail="semantic_category 不在第一版支持范围内")
    if performance_status and performance_status not in PERFORMANCE_LABELS:
        raise HTTPException(status_code=400, detail="performance_status 不在第一版支持范围内")
    if candidate_type and candidate_type not in CANDIDATE_LABELS:
        raise HTTPException(status_code=400, detail="candidate_type 不在第一版支持范围内")
    period_start, period_end = _date_range(start_date, end_date)
    return build_search_term_candidates(
        db,
        market_id=market_id,
        product_id=product_id,
        period_start=period_start,
        period_end=period_end,
        semantic_category=semantic_category,
        performance_status=performance_status,
        candidate_type=candidate_type,
        min_clicks=min_clicks,
        min_spend=min_spend,
        target_acos=target_acos,
        limit=limit,
    )


@router.post("/candidate-decisions")
def create_search_term_candidate_decision(
    payload: SearchTermCandidateDecisionIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(payload.start_date, payload.end_date)
    _validate_candidate_filters(
        market_id=payload.market_id,
        product_id=payload.product_id,
        semantic_category=payload.semantic_category,
        performance_status=payload.performance_status,
        min_clicks=payload.min_clicks,
        min_spend=payload.min_spend,
        target_acos=payload.target_acos,
        limit=payload.limit,
    )
    if not _not_blank(payload.candidate_id):
        raise HTTPException(status_code=400, detail="候选 ID candidate_id 必填")
    if payload.decision_type not in CANDIDATE_DECISION_TYPES:
        raise HTTPException(status_code=400, detail="搜索词候选处理类型 decision_type 不在第一版支持范围内")
    if not _not_blank(payload.operator_name):
        raise HTTPException(status_code=400, detail="处理人 operator_name 必填")
    if payload.decision_type == "adopt_with_changes" and not _not_blank(payload.modified_action):
        raise HTTPException(status_code=400, detail="修改后处理说明 modified_action 必填")
    if payload.decision_type in {"adopt_with_changes", "reject"} and not _not_blank(payload.reason):
        raise HTTPException(status_code=400, detail="处理原因 reason 必填")
    if payload.decision_type == "observe" and payload.observe_period not in OBSERVE_PERIODS:
        raise HTTPException(status_code=400, detail="观察周期 observe_period 只能是 7d 或 14d")

    period_start, period_end = _date_range(payload.start_date, payload.end_date)
    candidates = build_search_term_candidates(
        db,
        market_id=payload.market_id,
        product_id=payload.product_id,
        period_start=period_start,
        period_end=period_end,
        semantic_category=payload.semantic_category,
        performance_status=payload.performance_status,
        candidate_type=None,
        min_clicks=payload.min_clicks,
        min_spend=payload.min_spend,
        target_acos=payload.target_acos,
        limit=max(payload.limit, 200),
    )
    candidate = next(
        (item for item in candidates["rows"] if item.get("candidate_id") == payload.candidate_id.strip()),
        None,
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="搜索词候选不存在，请刷新候选池后再记录")

    now = datetime.now()
    decision = SearchTermCandidateDecision(
        candidate_id=str(candidate["candidate_id"]),
        candidate_type=str(candidate["candidate_type"]),
        search_term=str(candidate["search_term"]),
        market_id=payload.market_id,
        product_id=payload.product_id,
        period_start=period_start,
        period_end=period_end,
        decision_type=payload.decision_type,
        modified_action=payload.modified_action.strip() if payload.modified_action else None,
        reason=payload.reason.strip() if payload.reason else None,
        observe_period=payload.observe_period if payload.decision_type == "observe" else None,
        operator_name=payload.operator_name.strip(),
        candidate_snapshot_json=json.dumps(candidate, ensure_ascii=False),
        decided_at=now,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return {"decision": _candidate_decision_payload(decision)}


@router.get("/candidate-decisions")
def list_search_term_candidate_decisions(
    candidate_id: str | None = None,
    decision_type: str | None = None,
    operator_name: str | None = None,
    market_id: int | None = None,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    filters = []
    if candidate_id:
        filters.append(SearchTermCandidateDecision.candidate_id == candidate_id)
    if decision_type:
        if decision_type not in CANDIDATE_DECISION_TYPES:
            raise HTTPException(status_code=400, detail="搜索词候选处理类型 decision_type 不在第一版支持范围内")
        filters.append(SearchTermCandidateDecision.decision_type == decision_type)
    if operator_name:
        filters.append(SearchTermCandidateDecision.operator_name == operator_name)
    if market_id is not None:
        filters.append(SearchTermCandidateDecision.market_id == market_id)
    if product_id is not None:
        filters.append(SearchTermCandidateDecision.product_id == product_id)
    if start_date is not None:
        filters.append(SearchTermCandidateDecision.decided_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(SearchTermCandidateDecision.decided_at <= datetime.combine(end_date, time.max))

    stmt = (
        select(SearchTermCandidateDecision)
        .where(*filters)
        .order_by(SearchTermCandidateDecision.decided_at.desc(), SearchTermCandidateDecision.id.desc())
    )
    decisions = db.execute(stmt).scalars().all()
    return [_candidate_decision_payload(decision) for decision in decisions]


@router.post("/group-decisions")
def create_search_term_group_decision(
    payload: SearchTermGroupDecisionIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(payload.start_date, payload.end_date)
    _validate_candidate_filters(
        market_id=payload.market_id,
        product_id=payload.product_id,
        semantic_category=payload.semantic_category,
        performance_status=payload.performance_status,
        min_clicks=payload.min_clicks,
        min_spend=payload.min_spend,
        target_acos=payload.target_acos,
        limit=payload.limit,
    )
    if not _not_blank(payload.group_key):
        raise HTTPException(status_code=400, detail="归类组 group_key 必填")
    if payload.decision_type not in CANDIDATE_DECISION_TYPES:
        raise HTTPException(status_code=400, detail="归类组处理类型 decision_type 不在第一版支持范围内")
    if not _not_blank(payload.operator_name):
        raise HTTPException(status_code=400, detail="处理人 operator_name 必填")
    if payload.decision_type == "adopt_with_changes" and not _not_blank(payload.modified_action):
        raise HTTPException(status_code=400, detail="修改后处理说明 modified_action 必填")
    if payload.decision_type in {"adopt_with_changes", "reject"} and not _not_blank(payload.reason):
        raise HTTPException(status_code=400, detail="处理原因 reason 必填")
    if payload.decision_type == "observe" and payload.observe_period not in OBSERVE_PERIODS:
        raise HTTPException(status_code=400, detail="观察周期 observe_period 只能是 7d 或 14d")

    period_start, period_end = _date_range(payload.start_date, payload.end_date)
    analysis = analyze_search_terms(
        db,
        market_id=payload.market_id,
        product_id=payload.product_id,
        period_start=period_start,
        period_end=period_end,
        semantic_category=payload.semantic_category,
        performance_status=payload.performance_status,
        min_clicks=payload.min_clicks,
        min_spend=payload.min_spend,
        target_acos=payload.target_acos,
        limit=max(payload.limit, 500),
    )
    group = next(
        (item for item in analysis["group_summary"] if item.get("group_key") == payload.group_key.strip()),
        None,
    )
    if group is None:
        raise HTTPException(status_code=404, detail="搜索词归类组不存在，请刷新归类聚合组后再记录")

    now = datetime.now()
    decision = SearchTermGroupDecision(
        group_key=str(group["group_key"]),
        group_label=str(group["group_label"]),
        market_id=payload.market_id,
        product_id=payload.product_id,
        semantic_category=str(group["semantic_category"]),
        performance_status=str(group["performance_status"]),
        period_start=period_start,
        period_end=period_end,
        decision_type=payload.decision_type,
        modified_action=payload.modified_action.strip() if payload.modified_action else None,
        reason=payload.reason.strip() if payload.reason else None,
        observe_period=payload.observe_period if payload.decision_type == "observe" else None,
        operator_name=payload.operator_name.strip(),
        group_snapshot_json=json.dumps(group, ensure_ascii=False),
        decided_at=now,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return {"decision": _group_decision_payload(decision)}


@router.get("/group-decisions")
def list_search_term_group_decisions(
    group_key: str | None = None,
    decision_type: str | None = None,
    operator_name: str | None = None,
    market_id: int | None = None,
    product_id: int | None = None,
    semantic_category: str | None = None,
    performance_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_positive_int("market_id", market_id)
    _validate_positive_int("product_id", product_id)
    if decision_type and decision_type not in CANDIDATE_DECISION_TYPES:
        raise HTTPException(status_code=400, detail="归类组处理类型 decision_type 不在第一版支持范围内")
    if semantic_category and semantic_category not in SEMANTIC_LABELS:
        raise HTTPException(status_code=400, detail="semantic_category 不在第一版支持范围内")
    if performance_status and performance_status not in PERFORMANCE_LABELS:
        raise HTTPException(status_code=400, detail="performance_status 不在第一版支持范围内")

    filters = []
    if group_key:
        filters.append(SearchTermGroupDecision.group_key == group_key)
    if decision_type:
        filters.append(SearchTermGroupDecision.decision_type == decision_type)
    if operator_name:
        filters.append(SearchTermGroupDecision.operator_name == operator_name)
    if market_id is not None:
        filters.append(SearchTermGroupDecision.market_id == market_id)
    if product_id is not None:
        filters.append(SearchTermGroupDecision.product_id == product_id)
    if semantic_category:
        filters.append(SearchTermGroupDecision.semantic_category == semantic_category)
    if performance_status:
        filters.append(SearchTermGroupDecision.performance_status == performance_status)
    if start_date is not None:
        filters.append(SearchTermGroupDecision.decided_at >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(SearchTermGroupDecision.decided_at <= datetime.combine(end_date, time.max))

    stmt = (
        select(SearchTermGroupDecision)
        .where(*filters)
        .order_by(SearchTermGroupDecision.decided_at.desc(), SearchTermGroupDecision.id.desc())
    )
    decisions = db.execute(stmt).scalars().all()
    return [_group_decision_payload(decision) for decision in decisions]


@router.get("/group-decisions/{decision_id}/review")
def get_search_term_group_decision_review(
    decision_id: int,
    review_period: str = "7d",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if decision_id <= 0:
        raise HTTPException(status_code=400, detail="搜索词归类组处理记录 ID decision_id 必须大于 0")
    if review_period not in REVIEW_PERIOD_DAYS:
        raise HTTPException(status_code=400, detail="复盘周期 review_period 只能是 7d 或 14d")
    decision = db.get(SearchTermGroupDecision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="搜索词归类组处理记录不存在")

    base_end = date.fromisoformat(decision.period_end)
    after_start = base_end + timedelta(days=1)
    after_end = base_end + timedelta(days=REVIEW_PERIOD_DAYS[review_period])
    analysis = analyze_search_terms(
        db,
        market_id=decision.market_id,
        product_id=decision.product_id,
        period_start=after_start.isoformat(),
        period_end=after_end.isoformat(),
        semantic_category=decision.semantic_category,
        performance_status=decision.performance_status,
        min_clicks=10,
        min_spend=10.0,
        target_acos=0.35,
        limit=500,
    )
    after_group = next(
        (item for item in analysis["group_summary"] if item.get("group_key") == decision.group_key),
        None,
    )
    before_metrics = _group_snapshot_metrics(decision)
    after_metrics = _group_metrics_from_summary(after_group)
    result = _review_result(before_metrics, after_metrics)
    delta = _delta_metrics(before_metrics, after_metrics)
    return {
        "decision_id": decision.id,
        "group_key": decision.group_key,
        "group_label": decision.group_label,
        "semantic_category": decision.semantic_category,
        "performance_status": decision.performance_status,
        "decision_type": decision.decision_type,
        "review_period": review_period,
        "before_period": {"start": decision.period_start, "end": decision.period_end},
        "after_period": {"start": after_start.isoformat(), "end": after_end.isoformat()},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "result": result,
        "result_label": {
            "improved": "表现改善",
            "unchanged": "继续观察",
            "worse": "表现变差",
            "data_pending": "数据不足",
        }[result],
        "manual_hint": "组级人工判断复盘仅供人工判断，不会自动修改广告。",
    }


@router.get("/candidate-decisions/{decision_id}/review")
def get_search_term_candidate_decision_review(
    decision_id: int,
    review_period: str = "7d",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if decision_id <= 0:
        raise HTTPException(status_code=400, detail="搜索词候选处理记录 ID decision_id 必须大于 0")
    if review_period not in REVIEW_PERIOD_DAYS:
        raise HTTPException(status_code=400, detail="复盘周期 review_period 只能是 7d 或 14d")
    decision = db.get(SearchTermCandidateDecision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="搜索词候选处理记录不存在")

    base_end = date.fromisoformat(decision.period_end)
    after_start = base_end + timedelta(days=1)
    after_end = base_end + timedelta(days=REVIEW_PERIOD_DAYS[review_period])
    filters = [
        SpSearchTermMetric.search_term == decision.search_term,
        SpSearchTermMetric.data_date >= after_start.isoformat(),
        SpSearchTermMetric.data_date <= after_end.isoformat(),
    ]
    if decision.market_id is not None:
        filters.append(SpSearchTermMetric.market_id == decision.market_id)
    if decision.product_id is not None:
        filters.append(SpSearchTermMetric.product_id == decision.product_id)

    row = db.execute(
        select(
            func.count(SpSearchTermMetric.id).label("metric_rows"),
            func.coalesce(func.sum(SpSearchTermMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpSearchTermMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpSearchTermMetric.cost), 0.0).label("cost"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_sales), 0.0).label("sales"),
        ).where(*filters)
    ).one()
    before_metrics = _snapshot_metrics(decision)
    after_metrics = _metric_payload(
        impressions=row.impressions,
        clicks=row.clicks,
        cost=row.cost,
        orders=row.orders,
        sales=row.sales,
        metric_rows=row.metric_rows,
    )
    result = _review_result(before_metrics, after_metrics)
    delta = _delta_metrics(before_metrics, after_metrics)
    return {
        "decision_id": decision.id,
        "candidate_id": decision.candidate_id,
        "search_term": decision.search_term,
        "candidate_type": decision.candidate_type,
        "decision_type": decision.decision_type,
        "review_period": review_period,
        "before_period": {"start": decision.period_start, "end": decision.period_end},
        "after_period": {"start": after_start.isoformat(), "end": after_end.isoformat()},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta": delta,
        "result": result,
        "result_label": {
            "improved": "表现改善",
            "unchanged": "变化不明显",
            "worse": "表现变差",
            "data_pending": "暂无后续数据",
        }[result],
        "manual_hint": "复盘结果仅供人工判断，不会自动修改广告。",
    }
