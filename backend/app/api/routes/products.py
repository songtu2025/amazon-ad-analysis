from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.core.database import get_db
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric
from app.models.anomaly import AnomalyEvent
from app.models.product import Product, ProductGoal, ProductRule
from app.models.suggestion import AiSuggestion


router = APIRouter()


GOAL_TYPES = {
    "test_keywords",
    "scale",
    "profit",
    "rank_carryover",
    "clear_inventory",
    "stop_loss",
}
SUGGESTION_LEVELS = {"adoptable", "small_test", "observe", "blocked"}


class ProductIn(BaseModel):
    asin: str | None = None
    msku: str | None = None
    sku: str | None = None
    product_name: str | None = None
    image_url: str | None = None
    brand: str | None = None
    category: str | None = None
    market_id: int | None = None
    inventory_quantity: int | None = None


class ProductGoalIn(BaseModel):
    goal_type: str
    note: str | None = None


class ProductRuleIn(BaseModel):
    min_clicks: int | None = None
    min_spend: float | None = None
    min_orders: int | None = None
    target_acos: float | None = None
    target_cvr: float | None = None
    max_cpc: float | None = None
    inventory_guard: int | None = None


class CampaignBindingIn(BaseModel):
    campaign_id: str
    market_id: int | None = None


RULE_NON_NEGATIVE_FIELDS = {
    "min_clicks",
    "min_spend",
    "min_orders",
    "target_acos",
    "target_cvr",
    "max_cpc",
    "inventory_guard",
}


def _product_or_404(db: Session, product_id: int) -> Product:
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="产品 ID product_id 必须大于 0")
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


def _empty_metrics() -> dict[str, object]:
    return {
        "impressions": 0,
        "clicks": 0,
        "cost": 0.0,
        "orders": 0,
        "sales": 0.0,
        "acos": 0.0,
        "cvr": 0.0,
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


def _target_match(metrics: dict[str, object], rule: ProductRule | None) -> dict[str, str]:
    if rule is None:
        return {"status": "unknown", "reason": "未设置规则门槛"}

    if int(metrics["clicks"] or 0) == 0 and float(metrics["cost"] or 0) == 0:
        return {"status": "unknown", "reason": "当前周期暂无 SP 指标，暂不判断目标匹配"}

    acos = float(metrics["acos"])
    cvr = float(metrics["cvr"])
    reasons = []
    if rule.target_acos is not None and acos > rule.target_acos:
        reasons.append(f"ACOS {acos:.2%} 高于目标 {rule.target_acos:.2%}")
    if rule.target_cvr is not None and cvr < rule.target_cvr:
        reasons.append(f"CVR {cvr:.2%} 低于目标 {rule.target_cvr:.2%}")

    if reasons:
        return {"status": "mismatch", "reason": "；".join(reasons)}
    return {"status": "matched", "reason": "当前 SP 指标未触发目标不匹配"}


def _inventory_status(product: Product, rule: ProductRule | None) -> str:
    if product.inventory_quantity is None:
        return "未接入"
    if rule is not None and rule.inventory_guard is not None and product.inventory_quantity <= rule.inventory_guard:
        return "库存不足"
    return "库存充足"


def _validate_product_rule_values(values: dict[str, object]) -> None:
    for field in RULE_NON_NEGATIVE_FIELDS:
        value = values.get(field)
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{field} 必须大于或等于 0")


def _validate_product_values(values: dict[str, object]) -> None:
    _validate_market_id(values.get("market_id"))
    product_name = values.get("product_name")
    if "product_name" in values and (product_name is None or not str(product_name).strip()):
        raise HTTPException(status_code=400, detail="产品名称 product_name 必填")
    inventory_quantity = values.get("inventory_quantity")
    if inventory_quantity is not None and inventory_quantity < 0:
        raise HTTPException(status_code=400, detail="库存数量 inventory_quantity 必须大于或等于 0")


def _validate_campaign_binding(payload: CampaignBindingIn) -> None:
    if not payload.campaign_id.strip():
        raise HTTPException(status_code=400, detail="广告活动 ID campaign_id 必填")
    _validate_market_id(payload.market_id)


def _product_target_match(product: Product, goal: ProductGoal | None, rule: ProductRule | None, metrics: dict[str, object]) -> dict[str, str]:
    match = _target_match(metrics, rule)
    if (
        goal is not None
        and goal.goal_type in {"scale", "rank_carryover", "test_keywords"}
        and rule is not None
        and rule.inventory_guard is not None
        and product.inventory_quantity is not None
        and product.inventory_quantity <= rule.inventory_guard
    ):
        return {
            "status": "mismatch",
            "reason": f"当前库存 {product.inventory_quantity} 不高于库存阈值 {rule.inventory_guard}",
        }
    return match


def _metrics_by_product(db: Session, product_ids: list[int], period_start: str, period_end: str) -> dict[int, dict[str, object]]:
    if not product_ids:
        return {}

    rows = db.execute(
        select(
            SpKeywordMetric.product_id,
            func.coalesce(func.sum(SpKeywordMetric.impressions), 0),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0.0),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0.0),
        )
        .where(
            SpKeywordMetric.product_id.in_(product_ids),
            SpKeywordMetric.data_date >= period_start,
            SpKeywordMetric.data_date <= period_end,
        )
        .group_by(SpKeywordMetric.product_id)
    ).all()

    result: dict[int, dict[str, object]] = {}
    for row in rows:
        product_id = int(row[0])
        impressions = int(row[1] or 0)
        clicks = int(row[2] or 0)
        cost = float(row[3] or 0)
        orders = int(row[4] or 0)
        sales = float(row[5] or 0)
        result[product_id] = {
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "acos": round(cost / sales, 4) if sales > 0 else 0.0,
            "cvr": round(orders / clicks, 4) if clicks > 0 else 0.0,
        }
    return result


def _product_payload(
    product: Product,
    goal: ProductGoal | None,
    rule: ProductRule | None,
    metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    selected_metrics = metrics or _empty_metrics()
    return {
        "id": product.id,
        "asin": product.asin,
        "msku": product.msku,
        "sku": product.sku,
        "product_name": product.product_name,
        "image_url": product.image_url,
        "brand": product.brand,
        "category": product.category,
        "market_id": product.market_id,
        "inventory_quantity": product.inventory_quantity,
        "goal": None
        if goal is None
        else {
            "goal_type": goal.goal_type,
            "note": goal.note,
        },
        "rules": None
        if rule is None
        else {
            "min_clicks": rule.min_clicks,
            "min_spend": rule.min_spend,
            "min_orders": rule.min_orders,
            "target_acos": rule.target_acos,
            "target_cvr": rule.target_cvr,
            "max_cpc": rule.max_cpc,
            "inventory_guard": rule.inventory_guard,
        },
        "sp_metrics": selected_metrics,
        "sp_metrics_period": {"start": metrics.get("period_start") if metrics else None, "end": metrics.get("period_end") if metrics else None},
        "inventory_status": _inventory_status(product, rule),
        "target_match": _product_target_match(product, goal, rule, selected_metrics),
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.get("")
def list_products(
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
    period_start, period_end = _date_range(start_date, end_date)
    filters = []
    if market_id is not None:
        filters.append(Product.market_id == market_id)
    if goal_type:
        if goal_type not in GOAL_TYPES:
            raise HTTPException(status_code=400, detail="产品目标 goal_type 不在第一版支持范围内")
        filters.append(Product.id.in_(select(ProductGoal.product_id).where(ProductGoal.goal_type == goal_type)))
    anomaly_filters = [
        AnomalyEvent.period_start >= period_start,
        AnomalyEvent.period_end <= period_end,
    ]
    if market_id is not None:
        anomaly_filters.append(AnomalyEvent.market_id == market_id)
    if not is_valid_anomaly_type(anomaly_type):
        raise HTTPException(status_code=400, detail="异常类型 anomaly_type 不在第一版支持范围内")
    anomaly_type = normalize_anomaly_type(anomaly_type)
    if anomaly_type:
        anomaly_filters.append(AnomalyEvent.anomaly_type == anomaly_type)
    if suggestion_level:
        if suggestion_level not in SUGGESTION_LEVELS:
            raise HTTPException(status_code=400, detail="建议等级 suggestion_level 不在第一版支持范围内")
        anomaly_filters.append(AnomalyEvent.id.in_(select(AiSuggestion.anomaly_event_id).where(AiSuggestion.suggestion_level == suggestion_level)))
    if anomaly_type or suggestion_level:
        filters.append(Product.id.in_(select(AnomalyEvent.product_id).where(*anomaly_filters)))
    products = db.execute(select(Product).where(*filters).order_by(Product.id)).scalars().all()
    goals = {goal.product_id: goal for goal in db.execute(select(ProductGoal)).scalars().all()}
    rules = {rule.product_id: rule for rule in db.execute(select(ProductRule)).scalars().all()}
    metrics = _metrics_by_product(db, [product.id for product in products], period_start, period_end)
    rows = []
    for product in products:
        product_metrics = metrics.get(product.id) or _empty_metrics()
        product_metrics["period_start"] = period_start
        product_metrics["period_end"] = period_end
        rows.append(_product_payload(product, goals.get(product.id), rules.get(product.id), product_metrics))
    return rows


@router.post("")
def create_product(payload: ProductIn, db: Session = Depends(get_db)) -> dict[str, object]:
    now = datetime.now()
    values = payload.model_dump()
    _validate_product_values(values)
    product = Product(**values, created_at=now, updated_at=now)
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_payload(product, None, None)


@router.put("/{product_id}")
def update_product(
    product_id: int,
    payload: ProductIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = _product_or_404(db, product_id)
    values = payload.model_dump(exclude_unset=True)
    _validate_product_values(values)
    for key, value in values.items():
        setattr(product, key, value)
    product.updated_at = datetime.now()
    db.commit()
    db.refresh(product)
    goal = db.execute(select(ProductGoal).where(ProductGoal.product_id == product_id)).scalar_one_or_none()
    rule = db.execute(select(ProductRule).where(ProductRule.product_id == product_id)).scalar_one_or_none()
    return _product_payload(product, goal, rule)


@router.get("/{product_id}")
def get_product(
    product_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = _product_or_404(db, product_id)
    _validate_date_range(start_date, end_date)
    period_start, period_end = _date_range(start_date, end_date)
    goal = db.execute(select(ProductGoal).where(ProductGoal.product_id == product_id)).scalar_one_or_none()
    rule = db.execute(select(ProductRule).where(ProductRule.product_id == product_id)).scalar_one_or_none()
    metrics = _metrics_by_product(db, [product_id], period_start, period_end).get(product_id) or _empty_metrics()
    metrics["period_start"] = period_start
    metrics["period_end"] = period_end
    return _product_payload(product, goal, rule, metrics)


@router.put("/{product_id}/goal")
def update_product_goal(
    product_id: int,
    payload: ProductGoalIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = _product_or_404(db, product_id)
    if payload.goal_type not in GOAL_TYPES:
        raise HTTPException(status_code=400, detail="产品目标 goal_type 不在第一版支持范围内")

    now = datetime.now()
    goal = db.execute(select(ProductGoal).where(ProductGoal.product_id == product_id)).scalar_one_or_none()
    if goal is None:
        goal = ProductGoal(product_id=product_id, goal_type=payload.goal_type, note=payload.note, created_at=now, updated_at=now)
        db.add(goal)
    else:
        goal.goal_type = payload.goal_type
        goal.note = payload.note
        goal.updated_at = now
    product.updated_at = now
    db.commit()
    db.refresh(goal)
    return {"product_id": product_id, "goal_type": goal.goal_type, "note": goal.note}


@router.put("/{product_id}/rules")
def update_product_rules(
    product_id: int,
    payload: ProductRuleIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = _product_or_404(db, product_id)
    now = datetime.now()
    values = payload.model_dump()
    _validate_product_rule_values(values)
    rule = db.execute(select(ProductRule).where(ProductRule.product_id == product_id)).scalar_one_or_none()
    if rule is None:
        rule = ProductRule(product_id=product_id, **values, created_at=now, updated_at=now)
        db.add(rule)
    else:
        for key, value in values.items():
            setattr(rule, key, value)
        rule.updated_at = now
    product.updated_at = now
    db.commit()
    db.refresh(rule)
    return {
        "product_id": product_id,
        "min_clicks": rule.min_clicks,
        "min_spend": rule.min_spend,
        "min_orders": rule.min_orders,
        "target_acos": rule.target_acos,
        "target_cvr": rule.target_cvr,
        "max_cpc": rule.max_cpc,
        "inventory_guard": rule.inventory_guard,
    }


@router.put("/{product_id}/campaign-binding")
def bind_campaign_to_product(
    product_id: int,
    payload: CampaignBindingIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _product_or_404(db, product_id)
    _validate_campaign_binding(payload)
    keyword_filters = [SpKeywordMetric.campaign_id == payload.campaign_id]
    search_term_filters = [SpSearchTermMetric.campaign_id == payload.campaign_id]
    if payload.market_id is not None:
        keyword_filters.append(SpKeywordMetric.market_id == payload.market_id)
        search_term_filters.append(SpSearchTermMetric.market_id == payload.market_id)

    keyword_result = db.execute(
        update(SpKeywordMetric)
        .where(*keyword_filters)
        .values(product_id=product_id)
    )
    search_term_result = db.execute(
        update(SpSearchTermMetric)
        .where(*search_term_filters)
        .values(product_id=product_id)
    )
    db.commit()
    keyword_rows = int(keyword_result.rowcount or 0)
    search_term_rows = int(search_term_result.rowcount or 0)
    return {
        "product_id": product_id,
        "campaign_id": payload.campaign_id,
        "market_id": payload.market_id,
        "rows_updated": keyword_rows + search_term_rows,
        "keyword_rows_updated": keyword_rows,
        "search_term_rows_updated": search_term_rows,
    }
