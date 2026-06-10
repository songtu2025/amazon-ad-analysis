import json
from datetime import date, timedelta, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric
from app.models.anomaly import AnomalyEvent
from app.models.product import Product, ProductGoal, ProductRule


DEFAULT_MIN_CLICKS = 20
DEFAULT_MIN_SPEND = 20.0
DEFAULT_MIN_IMPRESSIONS = 100


def _date_range(start_date: date | None, end_date: date | None) -> tuple[str, str]:
    selected_end = end_date or date.today()
    selected_start = start_date or selected_end - timedelta(days=13)
    return selected_start.isoformat(), selected_end.isoformat()


def _severity(clicks: int, cost: float, min_clicks: int, min_spend: float) -> str:
    if clicks >= min_clicks * 2 or cost >= min_spend * 2:
        return "high"
    return "medium"


def _product_goal_by_id(db: Session, product_ids: list[int | None]) -> dict[int, str]:
    selected_ids = [product_id for product_id in product_ids if product_id is not None]
    if not selected_ids:
        return {}
    return {
        goal.product_id: goal.goal_type
        for goal in db.execute(select(ProductGoal).where(ProductGoal.product_id.in_(selected_ids))).scalars().all()
    }


def _acos_severity(acos: float, target_acos: float) -> str:
    if acos >= target_acos * 1.5:
        return "high"
    return "medium"


def _is_serving_abnormal(serving_status: str | None) -> bool:
    if not serving_status:
        return False
    value = serving_status.lower()
    return "enabled" not in value and "正常" not in serving_status and "投放" not in serving_status


def generate_clicks_no_orders_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_clicks: int = DEFAULT_MIN_CLICKS,
    min_spend: float = DEFAULT_MIN_SPEND,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpKeywordMetric.impressions, 0)).label("impressions")

    stmt = (
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
        )
        .where(SpKeywordMetric.data_date >= period_start, SpKeywordMetric.data_date <= period_end)
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
        )
        .having(clicks_sum >= min_clicks, cost_sum >= min_spend, orders_sum == 0)
        .order_by(cost_sum.desc())
    )
    if market_id is not None:
        stmt = stmt.where(SpKeywordMetric.market_id == market_id)

    rows = db.execute(stmt).all()
    product_goals = _product_goal_by_id(db, [row.product_id for row in rows])

    delete_filters = [
        AnomalyEvent.anomaly_type == "clicks_no_orders",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        cvr = orders / clicks if clicks > 0 else 0.0
        severity = _severity(clicks, cost, min_clicks, min_spend)
        object_id = str(row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": product_goals.get(row.product_id),
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "match_type": row.match_type,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "cvr": round(cvr, 4),
        }
        rule_result = {
            "anomaly_type": "clicks_no_orders",
            "severity": severity,
            "suggestion_level": "adoptable" if severity == "high" else "small_test",
            "object_type": "keyword",
            "object_id": object_id,
            "matched_rules": [
                {
                    "rule": "clicks_no_orders",
                    "result": "failed",
                    "message": "关键词点击和花费达到门槛，但近 14 天没有广告订单",
                }
            ],
            "blocked_rules": [],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="clicks_no_orders",
                severity=severity,
                object_type="keyword",
                object_id=object_id,
                object_name=row.keyword_text,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()

    return {
        "status": "success",
        "rule": "clicks_no_orders",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "min_clicks": min_clicks,
        "min_spend": min_spend,
        "events_created": len(events),
    }


def generate_search_terms_clicks_no_orders_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_clicks: int = DEFAULT_MIN_CLICKS,
    min_spend: float = DEFAULT_MIN_SPEND,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpSearchTermMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpSearchTermMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpSearchTermMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpSearchTermMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpSearchTermMetric.impressions, 0)).label("impressions")

    stmt = (
        select(
            SpSearchTermMetric.market_id,
            SpSearchTermMetric.product_id,
            SpSearchTermMetric.campaign_id,
            SpSearchTermMetric.campaign_name,
            SpSearchTermMetric.ad_group_id,
            SpSearchTermMetric.ad_group_name,
            SpSearchTermMetric.keyword_id,
            SpSearchTermMetric.keyword_text,
            SpSearchTermMetric.search_term,
            SpSearchTermMetric.match_type,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
        )
        .where(SpSearchTermMetric.data_date >= period_start, SpSearchTermMetric.data_date <= period_end)
        .group_by(
            SpSearchTermMetric.market_id,
            SpSearchTermMetric.product_id,
            SpSearchTermMetric.campaign_id,
            SpSearchTermMetric.campaign_name,
            SpSearchTermMetric.ad_group_id,
            SpSearchTermMetric.ad_group_name,
            SpSearchTermMetric.keyword_id,
            SpSearchTermMetric.keyword_text,
            SpSearchTermMetric.search_term,
            SpSearchTermMetric.match_type,
        )
        .having(clicks_sum >= min_clicks, cost_sum >= min_spend, orders_sum == 0)
        .order_by(cost_sum.desc())
    )
    if market_id is not None:
        stmt = stmt.where(SpSearchTermMetric.market_id == market_id)

    rows = db.execute(stmt).all()
    product_goals = _product_goal_by_id(db, [row.product_id for row in rows])

    delete_filters = [
        AnomalyEvent.anomaly_type == "clicks_no_orders",
        AnomalyEvent.object_type == "search_term",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        cvr = orders / clicks if clicks > 0 else 0.0
        severity = _severity(clicks, cost, min_clicks, min_spend)
        object_id = str(row.search_term or row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": product_goals.get(row.product_id),
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "search_term": row.search_term,
            "match_type": row.match_type,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "cvr": round(cvr, 4),
        }
        rule_result = {
            "anomaly_type": "clicks_no_orders",
            "severity": severity,
            "suggestion_level": "adoptable" if severity == "high" else "small_test",
            "object_type": "search_term",
            "object_id": object_id,
            "matched_rules": [
                {
                    "rule": "search_term_clicks_no_orders",
                    "result": "failed",
                    "message": "搜索词点击和花费达到门槛，但近 14 天没有广告订单",
                }
            ],
            "blocked_rules": [],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="clicks_no_orders",
                severity=severity,
                object_type="search_term",
                object_id=object_id,
                object_name=row.search_term,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()

    return {
        "status": "success",
        "rule": "search_term_clicks_no_orders",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "min_clicks": min_clicks,
        "min_spend": min_spend,
        "events_created": len(events),
    }


def generate_acos_worse_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpKeywordMetric.impressions, 0)).label("impressions")

    stmt = (
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
            ProductRule.min_spend,
            ProductRule.target_acos,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
        )
        .join(ProductGoal, ProductGoal.product_id == SpKeywordMetric.product_id)
        .join(ProductRule, ProductRule.product_id == SpKeywordMetric.product_id)
        .where(
            SpKeywordMetric.product_id.is_not(None),
            SpKeywordMetric.data_date >= period_start,
            SpKeywordMetric.data_date <= period_end,
            ProductGoal.goal_type.in_(["profit", "stop_loss"]),
            ProductRule.target_acos.is_not(None),
        )
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
            ProductRule.min_spend,
            ProductRule.target_acos,
        )
        .order_by(cost_sum.desc())
    )
    if market_id is not None:
        stmt = stmt.where(SpKeywordMetric.market_id == market_id)

    rows = db.execute(stmt).all()

    delete_filters = [
        AnomalyEvent.anomaly_type == "acos_worse",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        min_clicks = int(row.min_clicks or DEFAULT_MIN_CLICKS)
        min_spend = float(row.min_spend or DEFAULT_MIN_SPEND)
        target_acos = float(row.target_acos)
        if clicks < min_clicks or cost < min_spend or sales <= 0:
            continue

        acos = cost / sales
        if acos <= target_acos:
            continue

        severity = _acos_severity(acos, target_acos)
        object_id = str(row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": row.goal_type,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "match_type": row.match_type,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "acos": round(acos, 4),
            "target_acos": target_acos,
            "min_clicks": min_clicks,
            "min_spend": min_spend,
        }
        rule_result = {
            "anomaly_type": "acos_worse",
            "severity": severity,
            "suggestion_level": "adoptable" if severity == "high" else "small_test",
            "object_type": "keyword",
            "object_id": object_id,
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
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="acos_worse",
                severity=severity,
                object_type="keyword",
                object_id=object_id,
                object_name=row.keyword_text,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()

    return {
        "status": "success",
        "rule": "acos_worse",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "events_created": len(events),
    }


def generate_spend_spike_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpKeywordMetric.impressions, 0)).label("impressions")
    cpc_avg = func.avg(SpKeywordMetric.cpc).label("cpc")

    stmt = (
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_spend,
            ProductRule.min_orders,
            ProductRule.target_acos,
            ProductRule.max_cpc,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
            cpc_avg,
        )
        .join(ProductGoal, ProductGoal.product_id == SpKeywordMetric.product_id)
        .join(ProductRule, ProductRule.product_id == SpKeywordMetric.product_id)
        .where(
            SpKeywordMetric.product_id.is_not(None),
            SpKeywordMetric.data_date >= period_start,
            SpKeywordMetric.data_date <= period_end,
        )
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_spend,
            ProductRule.min_orders,
            ProductRule.target_acos,
            ProductRule.max_cpc,
        )
        .order_by(cost_sum.desc())
    )
    if market_id is not None:
        stmt = stmt.where(SpKeywordMetric.market_id == market_id)

    rows = db.execute(stmt).all()

    delete_filters = [
        AnomalyEvent.anomaly_type == "spend_spike",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        min_spend = float(row.min_spend or DEFAULT_MIN_SPEND)
        min_orders = int(row.min_orders) if row.min_orders is not None else 1
        target_acos = float(row.target_acos) if row.target_acos is not None else None
        max_cpc = float(row.max_cpc) if row.max_cpc is not None else None
        cpc = float(row.cpc) if row.cpc is not None else (cost / clicks if clicks > 0 else None)
        acos = cost / sales if sales > 0 else None
        roas = sales / cost if cost > 0 else None
        low_orders = orders < min_orders
        high_acos = target_acos is not None and acos is not None and acos > target_acos
        high_cpc = max_cpc is not None and cpc is not None and cpc > max_cpc
        if cost < min_spend or not (low_orders or high_acos or high_cpc):
            continue

        severity = "high" if low_orders and (high_acos or high_cpc or sales <= 0) else "medium"
        object_id = str(row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": row.goal_type,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "match_type": row.match_type,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "acos": round(acos, 4) if acos is not None else None,
            "roas": round(roas, 4) if roas is not None else None,
            "target_acos": target_acos,
            "cpc": round(cpc, 4) if cpc is not None else None,
            "max_cpc": max_cpc,
            "min_spend": min_spend,
            "min_orders": min_orders,
        }
        matched_rules = []
        if low_orders:
            matched_rules.append(
                {
                    "rule": "orders_below_target",
                    "result": "failed",
                    "message": "关键词订单低于产品规则门槛",
                }
            )
        if high_acos:
            matched_rules.append(
                {
                    "rule": "acos_above_target",
                    "result": "failed",
                    "message": "关键词 ACOS 高于产品目标门槛",
                }
            )
        if high_cpc:
            matched_rules.append(
                {
                    "rule": "cpc_above_max",
                    "result": "failed",
                    "message": "关键词 CPC 高于产品最大 CPC 门槛",
                }
            )
        rule_result = {
            "anomaly_type": "spend_spike",
            "severity": severity,
            "suggestion_level": "adoptable" if severity == "high" else "small_test",
            "object_type": "keyword",
            "object_id": object_id,
            "matched_rules": matched_rules,
            "blocked_rules": [],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="spend_spike",
                severity=severity,
                object_type="keyword",
                object_id=object_id,
                object_name=row.keyword_text,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()
    return {
        "status": "success",
        "rule": "spend_spike",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "events_created": len(events),
    }


def generate_cvr_drop_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpKeywordMetric.impressions, 0)).label("impressions")

    stmt = (
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
            ProductRule.target_cvr,
            ProductRule.target_acos,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
        )
        .join(ProductGoal, ProductGoal.product_id == SpKeywordMetric.product_id)
        .join(ProductRule, ProductRule.product_id == SpKeywordMetric.product_id)
        .where(
            SpKeywordMetric.product_id.is_not(None),
            SpKeywordMetric.data_date >= period_start,
            SpKeywordMetric.data_date <= period_end,
            ProductRule.target_cvr.is_not(None),
        )
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
            ProductRule.target_cvr,
            ProductRule.target_acos,
        )
        .order_by(clicks_sum.desc())
    )
    if market_id is not None:
        stmt = stmt.where(SpKeywordMetric.market_id == market_id)

    rows = db.execute(stmt).all()

    delete_filters = [
        AnomalyEvent.anomaly_type == "cvr_drop",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        min_clicks = int(row.min_clicks or DEFAULT_MIN_CLICKS)
        target_cvr = float(row.target_cvr)
        target_acos = float(row.target_acos) if row.target_acos is not None else None
        if clicks < min_clicks:
            continue

        cvr = orders / clicks if clicks else 0
        if cvr >= target_cvr:
            continue

        acos = cost / sales if sales > 0 else None
        high_acos = target_acos is not None and acos is not None and acos > target_acos
        severity = "high" if cvr <= target_cvr * 0.5 or high_acos else "medium"
        object_id = str(row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": row.goal_type,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "match_type": row.match_type,
            "impressions": impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
            "cvr": round(cvr, 4),
            "target_cvr": target_cvr,
            "acos": round(acos, 4) if acos is not None else None,
            "target_acos": target_acos,
            "min_clicks": min_clicks,
        }
        rule_result = {
            "anomaly_type": "cvr_drop",
            "severity": severity,
            "suggestion_level": "adoptable" if severity == "high" else "small_test",
            "object_type": "keyword",
            "object_id": object_id,
            "matched_rules": [
                {
                    "rule": "cvr_below_target",
                    "result": "failed",
                    "message": "关键词 CVR 低于产品目标门槛",
                }
            ],
            "blocked_rules": [],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="cvr_drop",
                severity=severity,
                object_type="keyword",
                object_id=object_id,
                object_name=row.keyword_text,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()
    return {
        "status": "success",
        "rule": "cvr_drop",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "events_created": len(events),
    }


def generate_impression_low_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")
    impressions_sum = func.sum(func.coalesce(SpKeywordMetric.impressions, 0)).label("impressions")

    stmt = (
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            SpKeywordMetric.bid,
            SpKeywordMetric.serving_status,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
            clicks_sum,
            cost_sum,
            orders_sum,
            sales_sum,
            impressions_sum,
        )
        .join(ProductGoal, ProductGoal.product_id == SpKeywordMetric.product_id)
        .join(ProductRule, ProductRule.product_id == SpKeywordMetric.product_id)
        .where(
            SpKeywordMetric.product_id.is_not(None),
            SpKeywordMetric.data_date >= period_start,
            SpKeywordMetric.data_date <= period_end,
            ProductGoal.goal_type.in_(["scale", "rank_carryover", "test_keywords"]),
        )
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.product_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            SpKeywordMetric.match_type,
            SpKeywordMetric.bid,
            SpKeywordMetric.serving_status,
            ProductGoal.goal_type,
            ProductRule.min_clicks,
        )
        .order_by(impressions_sum.asc())
    )
    if market_id is not None:
        stmt = stmt.where(SpKeywordMetric.market_id == market_id)

    rows = db.execute(stmt).all()

    delete_filters = [
        AnomalyEvent.anomaly_type == "impression_low",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        impressions = int(row.impressions or 0)
        min_impressions = max(int(row.min_clicks or DEFAULT_MIN_CLICKS) * 20, DEFAULT_MIN_IMPRESSIONS)
        serving_abnormal = _is_serving_abnormal(row.serving_status)
        if impressions >= min_impressions and not serving_abnormal:
            continue

        severity = "high" if serving_abnormal else "medium"
        object_id = str(row.keyword_id or row.keyword_text or "")
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.product_id,
            "product_goal": row.goal_type,
            "campaign_id": row.campaign_id,
            "campaign_name": row.campaign_name,
            "ad_group_id": row.ad_group_id,
            "ad_group_name": row.ad_group_name,
            "keyword_id": row.keyword_id,
            "keyword_text": row.keyword_text,
            "match_type": row.match_type,
            "bid": row.bid,
            "serving_status": row.serving_status,
            "impressions": impressions,
            "min_impressions": min_impressions,
            "clicks": clicks,
            "cost": round(cost, 4),
            "orders": orders,
            "sales": round(sales, 4),
        }
        rule_result = {
            "anomaly_type": "impression_low",
            "severity": severity,
            "suggestion_level": "adoptable" if serving_abnormal else "observe",
            "object_type": "keyword",
            "object_id": object_id,
            "matched_rules": [
                {
                    "rule": "impression_low",
                    "result": "failed",
                    "message": "放量、排名承接或测试目标下，关键词曝光低于门槛或投放状态异常",
                }
            ],
            "blocked_rules": [],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.product_id,
                market_id=row.market_id,
                anomaly_type="impression_low",
                severity=severity,
                object_type="keyword",
                object_id=object_id,
                object_name=row.keyword_text,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()
    return {
        "status": "success",
        "rule": "impression_low",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "events_created": len(events),
    }


def generate_inventory_goal_conflict_anomalies(
    db: Session,
    market_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, object]:
    period_start, period_end = _date_range(start_date, end_date)

    stmt = (
        select(
            Product.id,
            Product.market_id,
            Product.product_name,
            Product.asin,
            Product.msku,
            Product.inventory_quantity,
            ProductGoal.goal_type,
            ProductRule.inventory_guard,
        )
        .join(ProductGoal, ProductGoal.product_id == Product.id)
        .join(ProductRule, ProductRule.product_id == Product.id)
        .where(
            ProductGoal.goal_type.in_(["scale", "rank_carryover", "test_keywords"]),
            Product.inventory_quantity.is_not(None),
            ProductRule.inventory_guard.is_not(None),
            Product.inventory_quantity <= ProductRule.inventory_guard,
        )
        .order_by(Product.id)
    )
    if market_id is not None:
        stmt = stmt.where(Product.market_id == market_id)

    rows = db.execute(stmt).all()

    delete_filters = [
        AnomalyEvent.anomaly_type == "inventory_goal_conflict",
        AnomalyEvent.period_start == period_start,
        AnomalyEvent.period_end == period_end,
        AnomalyEvent.status == "pending",
    ]
    if market_id is not None:
        delete_filters.append(AnomalyEvent.market_id == market_id)
    db.execute(delete(AnomalyEvent).where(*delete_filters))

    now = datetime.now()
    events: list[AnomalyEvent] = []
    for row in rows:
        object_name = row.product_name or row.asin or row.msku or f"产品 {row.id}"
        evidence = {
            "period": {"start": period_start, "end": period_end},
            "market_id": row.market_id,
            "product_id": row.id,
            "product_name": row.product_name,
            "asin": row.asin,
            "msku": row.msku,
            "product_goal": row.goal_type,
            "inventory_quantity": row.inventory_quantity,
            "inventory_guard": row.inventory_guard,
        }
        rule_result = {
            "anomaly_type": "inventory_goal_conflict",
            "severity": "high",
            "suggestion_level": "blocked",
            "object_type": "product",
            "object_id": str(row.id),
            "matched_rules": [
                {
                    "rule": "inventory_goal_conflict",
                    "result": "failed",
                    "message": "库存不足时不能建议放量或排名承接",
                }
            ],
            "blocked_rules": [
                {
                    "rule": "inventory_guard_blocks_scale",
                    "message": "当前库存不高于库存阈值，禁止输出放量类建议",
                }
            ],
            "evidence": evidence,
        }
        events.append(
            AnomalyEvent(
                product_id=row.id,
                market_id=row.market_id,
                anomaly_type="inventory_goal_conflict",
                severity="high",
                object_type="product",
                object_id=str(row.id),
                object_name=object_name,
                period_start=period_start,
                period_end=period_end,
                status="pending",
                rule_result_json=json.dumps(rule_result, ensure_ascii=False),
                evidence_json=json.dumps(evidence, ensure_ascii=False),
                created_at=now,
                updated_at=now,
            )
        )

    db.add_all(events)
    db.commit()
    return {
        "status": "success",
        "rule": "inventory_goal_conflict",
        "market_id": market_id,
        "period_start": period_start,
        "period_end": period_end,
        "events_created": len(events),
    }
