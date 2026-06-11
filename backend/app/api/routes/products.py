from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.normalization import is_valid_anomaly_type, normalize_anomaly_type
from app.core.database import get_db
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric
from app.models.anomaly import AnomalyEvent
from app.models.market import MarketInfo
from app.models.product import Product, ProductAdBinding, ProductGoal, ProductRule, ProductSalesSnapshot
from app.services.product_attribution_service import (
    VALID_SCOPE_TYPES,
    apply_product_ad_binding,
    build_product_attribution_candidates,
    build_product_attribution_evidence,
    list_product_ad_bindings,
    list_unbound_ad_sources,
    product_ad_binding_payload,
    save_product_ad_binding,
)
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


class AdBindingIn(BaseModel):
    scope_type: str
    scope_id: str
    scope_name: str | None = None
    market_id: int | None = None
    created_by: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    evidence_note: str | None = None


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


def _is_demo_or_test_product(product: Product) -> bool:
    text = " ".join(
        str(value or "")
        for value in [product.asin, product.msku, product.sku, product.product_name]
    ).upper()
    return any(marker in text for marker in ["DEMO", "SMOKE", "TASK"])


def _has_sales_performance_identity(product: Product) -> bool:
    asin = str(product.asin or "").strip().upper()
    return (
        asin.startswith("B0")
        and len(asin) >= 10
        and bool(str(product.msku or "").strip())
        and bool(str(product.product_name or "").strip())
        and not _is_demo_or_test_product(product)
    )


def _has_readable_product_identity(product: Product) -> bool:
    msku = str(product.msku or "").strip()
    product_name = str(product.product_name or "").strip()
    category = str(product.category or "").strip()
    return bool(product_name) and product_name != msku and bool(category) and category != "-"


def _product_display_sort_key(product: Product) -> tuple[int, int, str, int]:
    if _has_sales_performance_identity(product):
        priority = 0
    elif _is_demo_or_test_product(product):
        priority = 2
    else:
        priority = 1
    identity_priority = 0 if _has_readable_product_identity(product) else 1
    name = str(product.product_name or product.msku or product.asin or "").lower()
    return priority, identity_priority, name, product.id


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


def _has_sp_metrics(metrics: dict[str, object]) -> bool:
    return (
        int(metrics.get("clicks") or 0) > 0
        or float(metrics.get("cost") or 0) > 0
        or int(metrics.get("orders") or 0) > 0
        or float(metrics.get("sales") or 0) > 0
    )


def _product_ad_coverage_status(active_binding_count: int, metrics: dict[str, object]) -> str:
    if active_binding_count > 0:
        return "attributed"
    if _has_sp_metrics(metrics):
        return "sp_unattributed"
    return "not_advertised"


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


def _validate_ad_binding(payload: AdBindingIn) -> None:
    if payload.scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail="归因颗粒度 scope_type 只支持 campaign 或 ad_group")
    if not payload.scope_id.strip():
        raise HTTPException(status_code=400, detail="归因对象 ID scope_id 必填")
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


def _active_ad_binding_counts(db: Session, product_ids: list[int]) -> dict[int, int]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(ProductAdBinding.product_id, func.count(ProductAdBinding.id))
        .where(
            ProductAdBinding.product_id.in_(product_ids),
            ProductAdBinding.status == "active",
        )
        .group_by(ProductAdBinding.product_id)
    ).all()
    return {int(product_id): int(count or 0) for product_id, count in rows}


def _sales_snapshot_payload(snapshot: ProductSalesSnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "period_start": snapshot.period_start,
        "period_end": snapshot.period_end,
        "units_ordered": snapshot.units_ordered,
        "orders": snapshot.orders,
        "sales": snapshot.sales,
        "sessions": snapshot.sessions,
        "order_cvr": snapshot.order_cvr,
        "ads_spend": snapshot.ads_spend,
        "ads_sales": snapshot.ads_sales,
        "acos": snapshot.acos,
        "gross_profit": snapshot.gross_profit,
        "net_profit": snapshot.net_profit,
    }


def _sales_snapshots_by_product(
    db: Session,
    product_ids: list[int],
    period_start: str,
    period_end: str,
) -> dict[int, ProductSalesSnapshot]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(ProductSalesSnapshot).where(
            ProductSalesSnapshot.product_id.in_(product_ids),
            ProductSalesSnapshot.period_start == period_start,
            ProductSalesSnapshot.period_end == period_end,
        )
    ).scalars().all()
    return {int(row.product_id): row for row in rows if row.product_id is not None}


def _market_infos_by_id(db: Session, market_ids: list[int | None]) -> dict[int, MarketInfo]:
    selected_ids = sorted({int(market_id) for market_id in market_ids if market_id is not None})
    if not selected_ids:
        return {}
    rows = db.execute(select(MarketInfo).where(MarketInfo.market_id.in_(selected_ids))).scalars().all()
    return {row.market_id: row for row in rows}


def _market_payload(product: Product, market_info: MarketInfo | None = None) -> dict[str, object] | None:
    if product.market_id is None:
        return None
    return {
        "market_id": product.market_id,
        "market_name": market_info.market_name if market_info else None,
        "country_code": market_info.country_code if market_info else None,
        "raw_name": market_info.raw_name if market_info else None,
    }


def _product_payload(
    product: Product,
    goal: ProductGoal | None,
    rule: ProductRule | None,
    metrics: dict[str, object] | None = None,
    sales_snapshot: ProductSalesSnapshot | None = None,
    market_info: MarketInfo | None = None,
    active_ad_binding_count: int = 0,
) -> dict[str, object]:
    selected_metrics = metrics or _empty_metrics()
    ad_coverage_status = _product_ad_coverage_status(active_ad_binding_count, selected_metrics)
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
        "market": _market_payload(product, market_info),
        "ad_coverage_status": ad_coverage_status,
        "is_ad_tuning_eligible": ad_coverage_status != "not_advertised",
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
        "sales_snapshot": _sales_snapshot_payload(sales_snapshot),
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
    products = sorted(products, key=_product_display_sort_key)
    goals = {goal.product_id: goal for goal in db.execute(select(ProductGoal)).scalars().all()}
    rules = {rule.product_id: rule for rule in db.execute(select(ProductRule)).scalars().all()}
    product_ids = [product.id for product in products]
    metrics = _metrics_by_product(db, product_ids, period_start, period_end)
    sales_snapshots = _sales_snapshots_by_product(db, product_ids, period_start, period_end)
    market_infos = _market_infos_by_id(db, [product.market_id for product in products])
    active_ad_binding_counts = _active_ad_binding_counts(db, product_ids)
    rows = []
    for product in products:
        product_metrics = metrics.get(product.id) or _empty_metrics()
        product_metrics["period_start"] = period_start
        product_metrics["period_end"] = period_end
        rows.append(
            _product_payload(
                product,
                goals.get(product.id),
                rules.get(product.id),
                product_metrics,
                sales_snapshots.get(product.id),
                market_infos.get(product.market_id) if product.market_id is not None else None,
                active_ad_binding_counts.get(product.id, 0),
            )
        )
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
    market_infos = _market_infos_by_id(db, [product.market_id])
    return _product_payload(product, None, None, market_info=market_infos.get(product.market_id) if product.market_id is not None else None)


@router.get("/unbound-ad-sources")
def get_unbound_ad_sources(
    market_id: int | None = None,
    scope_type: str = "ad_group",
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    if scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail="归因颗粒度 scope_type 只支持 campaign 或 ad_group")
    period_start, period_end = _date_range(start_date, end_date)
    return list_unbound_ad_sources(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
    )


@router.get("/ad-bindings")
def get_product_ad_bindings(
    market_id: int | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _validate_market_id(market_id)
    if product_id is not None:
        _product_or_404(db, product_id)
    return list_product_ad_bindings(db, market_id=market_id, product_id=product_id)


@router.get("/ad-attribution-evidence")
def get_product_attribution_evidence(
    scope_type: str,
    scope_id: str,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_ad_binding(AdBindingIn(scope_type=scope_type, scope_id=scope_id, market_id=market_id))
    period_start, period_end = _date_range(start_date, end_date)
    return build_product_attribution_evidence(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
        scope_id=scope_id.strip(),
    )


@router.get("/attribution-candidates")
def get_product_attribution_candidates(
    market_id: int | None = None,
    scope_type: str = "ad_group",
    start_date: date | None = None,
    end_date: date | None = None,
    min_confidence: int = 40,
    limit: int = 30,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_date_range(start_date, end_date)
    _validate_market_id(market_id)
    if scope_type not in VALID_SCOPE_TYPES:
        raise HTTPException(status_code=400, detail="归因颗粒度 scope_type 只支持 campaign 或 ad_group")
    if min_confidence < 0 or min_confidence > 100:
        raise HTTPException(status_code=400, detail="可信度门槛 min_confidence 必须在 0 到 100 之间")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit 必须大于 0")
    period_start, period_end = _date_range(start_date, end_date)
    return build_product_attribution_candidates(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
        min_confidence=min_confidence,
        limit=limit,
    )


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
    market_infos = _market_infos_by_id(db, [product.market_id])
    active_ad_binding_count = _active_ad_binding_counts(db, [product_id]).get(product_id, 0)
    return _product_payload(
        product,
        goal,
        rule,
        market_info=market_infos.get(product.market_id) if product.market_id is not None else None,
        active_ad_binding_count=active_ad_binding_count,
    )


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
    sales_snapshot = _sales_snapshots_by_product(db, [product_id], period_start, period_end).get(product_id)
    market_infos = _market_infos_by_id(db, [product.market_id])
    active_ad_binding_count = _active_ad_binding_counts(db, [product_id]).get(product_id, 0)
    return _product_payload(
        product,
        goal,
        rule,
        metrics,
        sales_snapshot,
        market_infos.get(product.market_id) if product.market_id is not None else None,
        active_ad_binding_count,
    )


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


@router.put("/{product_id}/ad-binding")
def bind_ad_source_to_product(
    product_id: int,
    payload: AdBindingIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = _product_or_404(db, product_id)
    _validate_ad_binding(payload)
    _validate_date_range(payload.period_start, payload.period_end)
    period_start, period_end = _date_range(payload.period_start, payload.period_end)
    evidence = build_product_attribution_evidence(
        db,
        market_id=payload.market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id.strip(),
        selected_product_id=product_id,
    )
    selected_product = evidence.get("selected_product") or {
        "product_id": product.id,
        "product_name": product.product_name,
        "asin": product.asin,
        "msku": product.msku,
        "sku": product.sku,
        "market_id": product.market_id,
        "confidence_score": 0,
        "confidence_level": "low",
        "reasons": ["该产品不在当前候选列表中，需要人工额外确认"],
    }
    confidence = {
        "score": selected_product.get("confidence_score") if isinstance(selected_product, dict) else 0,
        "level": selected_product.get("confidence_level") if isinstance(selected_product, dict) else "low",
        "reasons": selected_product.get("reasons") if isinstance(selected_product, dict) else [],
    }
    evidence_snapshot = {
        "period": {"start": period_start, "end": period_end},
        "source_snapshot": evidence.get("source"),
        "selected_product": selected_product,
        "confidence": confidence,
        "conflicts": evidence.get("conflicts") or [],
        "top_keywords": evidence.get("top_keywords") or [],
        "top_search_terms": evidence.get("top_search_terms") or [],
        "confirmation": {
            "confirmed_by": payload.created_by,
            "confirmed_at": datetime.now().isoformat(),
            "note": payload.evidence_note,
        },
    }
    binding = save_product_ad_binding(
        db,
        product_id=product_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id.strip(),
        scope_name=payload.scope_name,
        market_id=payload.market_id,
        created_by=payload.created_by,
        evidence=evidence_snapshot,
    )
    applied = apply_product_ad_binding(db, binding)
    db.commit()
    db.refresh(binding)
    return {
        **product_ad_binding_payload(binding),
        **applied,
    }


@router.put("/{product_id}/campaign-binding")
def bind_campaign_to_product(
    product_id: int,
    payload: CampaignBindingIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_campaign_binding(payload)
    result = bind_ad_source_to_product(
        product_id,
        AdBindingIn(scope_type="campaign", scope_id=payload.campaign_id, market_id=payload.market_id),
        db,
    )
    return {
        **result,
        "product_id": product_id,
        "campaign_id": payload.campaign_id,
        "market_id": payload.market_id,
    }
