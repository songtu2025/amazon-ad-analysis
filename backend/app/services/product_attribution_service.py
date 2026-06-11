import json
from datetime import datetime
from typing import Any

from sqlalchemy import distinct, func, select, update
from sqlalchemy.orm import Session

from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric
from app.models.product import Product, ProductAdBinding, ProductGoal, ProductRule


VALID_SCOPE_TYPES = {"campaign", "ad_group"}


def _round(value: float | None, digits: int = 4) -> float:
    return round(float(value or 0), digits)


def _rate_metrics(cost: float, sales: float, orders: int, clicks: int) -> dict[str, float]:
    return {
        "acos": _round(cost / sales) if sales else 0,
        "cvr": _round(orders / clicks) if clicks else 0,
    }


def _candidate_unlock_impact(metrics: dict[str, object]) -> dict[str, object]:
    cost = float(metrics.get("cost") or 0)
    sales = float(metrics.get("sales") or 0)
    orders = int(metrics.get("orders") or 0)
    clicks = int(metrics.get("clicks") or 0)
    return {
        "search_term_rows": int(metrics.get("search_term_rows") or 0),
        "cost": _round(cost, 2),
        "sales": _round(sales, 2),
        "orders": orders,
        "acos": _round(cost / sales) if sales else 0,
        "cvr": _round(orders / clicks) if clicks else 0,
    }


def _scope_filters(model, scope_type: str, scope_id: str) -> list[object]:
    if scope_type == "campaign":
        return [model.campaign_id == scope_id]
    return [model.ad_group_id == scope_id]


def _binding_filters(model, binding: ProductAdBinding) -> list[object]:
    filters = _scope_filters(model, binding.scope_type, binding.scope_id)
    if binding.market_id is not None:
        filters.append(model.market_id == binding.market_id)
    return filters


def _date_filters(model, period_start: str | None, period_end: str | None) -> list[object]:
    filters: list[object] = []
    if period_start is not None:
        filters.append(model.data_date >= period_start)
    if period_end is not None:
        filters.append(model.data_date <= period_end)
    return filters


def _text_tokens(*values: object) -> set[str]:
    text = " ".join(str(value or "").lower() for value in values)
    separators = ["-", "_", "/", "&", "(", ")", "（", "）", "[", "]", ",", ".", "，"]
    for separator in separators:
        text = text.replace(separator, " ")
    return {part.strip() for part in text.split() if len(part.strip()) >= 3}


def _source_text(source: dict[str, object], top_keywords: list[dict[str, object]], top_search_terms: list[dict[str, object]]) -> str:
    values: list[object] = [
        source.get("campaign_name"),
        source.get("ad_group_name"),
        source.get("scope_name"),
        source.get("campaign_id"),
        source.get("ad_group_id"),
    ]
    values.extend(item.get("keyword_text") for item in top_keywords)
    values.extend(item.get("search_term") for item in top_search_terms)
    return " ".join(str(value or "").lower() for value in values)


def _confidence_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def apply_product_ad_binding(
    db: Session,
    binding: ProductAdBinding,
    *,
    only_unbound: bool = False,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, int]:
    keyword_filters = _binding_filters(SpKeywordMetric, binding) + _date_filters(SpKeywordMetric, period_start, period_end)
    search_term_filters = _binding_filters(SpSearchTermMetric, binding) + _date_filters(SpSearchTermMetric, period_start, period_end)
    if only_unbound:
        keyword_filters.append(SpKeywordMetric.product_id.is_(None))
        search_term_filters.append(SpSearchTermMetric.product_id.is_(None))

    keyword_result = db.execute(
        update(SpKeywordMetric)
        .where(*keyword_filters)
        .values(product_id=binding.product_id)
        .execution_options(synchronize_session=False)
    )
    search_term_result = db.execute(
        update(SpSearchTermMetric)
        .where(*search_term_filters)
        .values(product_id=binding.product_id)
        .execution_options(synchronize_session=False)
    )
    keyword_rows = int(keyword_result.rowcount or 0)
    search_term_rows = int(search_term_result.rowcount or 0)
    return {
        "keyword_rows_updated": keyword_rows,
        "search_term_rows_updated": search_term_rows,
        "rows_updated": keyword_rows + search_term_rows,
    }


def save_product_ad_binding(
    db: Session,
    *,
    product_id: int,
    scope_type: str,
    scope_id: str,
    scope_name: str | None,
    market_id: int | None,
    created_by: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ProductAdBinding:
    now = datetime.now()
    binding = db.execute(
        select(ProductAdBinding).where(
            ProductAdBinding.status == "active",
            ProductAdBinding.scope_type == scope_type,
            ProductAdBinding.scope_id == scope_id,
            ProductAdBinding.market_id == market_id,
        )
    ).scalar_one_or_none()
    evidence_json = json.dumps(evidence or {}, ensure_ascii=False)
    if binding is None:
        binding = ProductAdBinding(
            market_id=market_id,
            product_id=product_id,
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=scope_name,
            status="active",
            created_by=created_by,
            evidence_json=evidence_json,
            created_at=now,
            updated_at=now,
        )
        db.add(binding)
    else:
        binding.product_id = product_id
        binding.scope_name = scope_name or binding.scope_name
        binding.created_by = created_by or binding.created_by
        binding.evidence_json = evidence_json
        binding.updated_at = now
    db.flush()
    return binding


def apply_active_product_ad_bindings(
    db: Session,
    *,
    market_id: int | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, int]:
    filters = [ProductAdBinding.status == "active"]
    if market_id is not None:
        filters.append(ProductAdBinding.market_id == market_id)
    bindings = db.execute(select(ProductAdBinding).where(*filters).order_by(ProductAdBinding.id)).scalars().all()

    total = {
        "bindings_applied": 0,
        "keyword_rows_updated": 0,
        "search_term_rows_updated": 0,
        "rows_updated": 0,
    }
    for binding in bindings:
        result = apply_product_ad_binding(
            db,
            binding,
            only_unbound=True,
            period_start=period_start,
            period_end=period_end,
        )
        if result["rows_updated"] > 0:
            total["bindings_applied"] += 1
        total["keyword_rows_updated"] += result["keyword_rows_updated"]
        total["search_term_rows_updated"] += result["search_term_rows_updated"]
        total["rows_updated"] += result["rows_updated"]
    return total


def product_ad_binding_payload(binding: ProductAdBinding) -> dict[str, object]:
    return {
        "id": binding.id,
        "market_id": binding.market_id,
        "product_id": binding.product_id,
        "scope_type": binding.scope_type,
        "scope_id": binding.scope_id,
        "scope_name": binding.scope_name,
        "status": binding.status,
        "created_by": binding.created_by,
        "evidence_json": binding.evidence_json,
        "created_at": binding.created_at.isoformat(),
        "updated_at": binding.updated_at.isoformat(),
    }


def list_product_ad_bindings(
    db: Session,
    *,
    market_id: int | None = None,
    product_id: int | None = None,
) -> list[dict[str, object]]:
    filters = [ProductAdBinding.status == "active"]
    if market_id is not None:
        filters.append(ProductAdBinding.market_id == market_id)
    if product_id is not None:
        filters.append(ProductAdBinding.product_id == product_id)
    rows = db.execute(select(ProductAdBinding).where(*filters).order_by(ProductAdBinding.updated_at.desc())).scalars().all()
    return [product_ad_binding_payload(row) for row in rows]


def _search_term_count_map(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
) -> dict[tuple[object, ...], int]:
    filters: list[object] = [
        SpSearchTermMetric.product_id.is_(None),
        SpSearchTermMetric.data_date >= period_start,
        SpSearchTermMetric.data_date <= period_end,
    ]
    if market_id is not None:
        filters.append(SpSearchTermMetric.market_id == market_id)

    if scope_type == "campaign":
        rows = db.execute(
            select(SpSearchTermMetric.market_id, SpSearchTermMetric.campaign_id, func.count(SpSearchTermMetric.id))
            .where(*filters)
            .group_by(SpSearchTermMetric.market_id, SpSearchTermMetric.campaign_id)
        ).all()
        return {(row.market_id, row.campaign_id): int(row[2] or 0) for row in rows}

    rows = db.execute(
        select(
            SpSearchTermMetric.market_id,
            SpSearchTermMetric.campaign_id,
            SpSearchTermMetric.ad_group_id,
            func.count(SpSearchTermMetric.id),
        )
        .where(*filters)
        .group_by(SpSearchTermMetric.market_id, SpSearchTermMetric.campaign_id, SpSearchTermMetric.ad_group_id)
    ).all()
    return {(row.market_id, row.campaign_id, row.ad_group_id): int(row[3] or 0) for row in rows}


def list_unbound_ad_sources(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
) -> list[dict[str, object]]:
    filters: list[object] = [
        SpKeywordMetric.product_id.is_(None),
        SpKeywordMetric.data_date >= period_start,
        SpKeywordMetric.data_date <= period_end,
    ]
    if market_id is not None:
        filters.append(SpKeywordMetric.market_id == market_id)

    search_counts = _search_term_count_map(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
    )
    if scope_type == "campaign":
        rows = db.execute(
            select(
                SpKeywordMetric.market_id,
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
            .where(*filters)
            .group_by(SpKeywordMetric.market_id, SpKeywordMetric.campaign_id, SpKeywordMetric.campaign_name)
            .order_by(func.sum(SpKeywordMetric.cost).desc())
        ).all()
        result = []
        for row in rows:
            sales = float(row.sales or 0)
            clicks = int(row.clicks or 0)
            key = (row.market_id, row.campaign_id)
            result.append(
                {
                    "scope_type": "campaign",
                    "scope_id": row.campaign_id,
                    "scope_name": row.campaign_name,
                    "market_id": row.market_id,
                    "campaign_id": row.campaign_id,
                    "campaign_name": row.campaign_name,
                    "ad_group_id": None,
                    "ad_group_name": None,
                    "metric_rows": int(row.metric_rows or 0),
                    "keyword_count": int(row.keyword_count or 0),
                    "ad_group_count": int(row.ad_group_count or 0),
                    "search_term_rows": search_counts.get(key, 0),
                    "impressions": int(row.impressions or 0),
                    "clicks": clicks,
                    "cost": _round(row.cost, 2),
                    "orders": int(row.orders or 0),
                    "sales": _round(sales, 2),
                    "acos": _round(float(row.cost or 0) / sales) if sales else 0,
                    "cvr": _round(float(row.orders or 0) / clicks) if clicks else 0,
                }
            )
        return result

    rows = db.execute(
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            func.count(SpKeywordMetric.id).label("metric_rows"),
            func.count(distinct(SpKeywordMetric.keyword_id)).label("keyword_count"),
            func.coalesce(func.sum(SpKeywordMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0).label("sales"),
        )
        .where(*filters)
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
        )
        .order_by(func.sum(SpKeywordMetric.cost).desc())
    ).all()
    result = []
    for row in rows:
        sales = float(row.sales or 0)
        clicks = int(row.clicks or 0)
        key = (row.market_id, row.campaign_id, row.ad_group_id)
        result.append(
            {
                "scope_type": "ad_group",
                "scope_id": row.ad_group_id,
                "scope_name": row.ad_group_name,
                "market_id": row.market_id,
                "campaign_id": row.campaign_id,
                "campaign_name": row.campaign_name,
                "ad_group_id": row.ad_group_id,
                "ad_group_name": row.ad_group_name,
                "metric_rows": int(row.metric_rows or 0),
                "keyword_count": int(row.keyword_count or 0),
                "ad_group_count": 1,
                "search_term_rows": search_counts.get(key, 0),
                "impressions": int(row.impressions or 0),
                "clicks": clicks,
                "cost": _round(row.cost, 2),
                "orders": int(row.orders or 0),
                "sales": _round(sales, 2),
                "acos": _round(float(row.cost or 0) / sales) if sales else 0,
                "cvr": _round(float(row.orders or 0) / clicks) if clicks else 0,
            }
        )
    return result


def _source_summary(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
    scope_id: str,
) -> dict[str, object]:
    filters = _scope_filters(SpKeywordMetric, scope_type, scope_id) + _date_filters(SpKeywordMetric, period_start, period_end)
    if market_id is not None:
        filters.append(SpKeywordMetric.market_id == market_id)
    row = db.execute(
        select(
            SpKeywordMetric.market_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
            func.count(SpKeywordMetric.id).label("metric_rows"),
            func.count(distinct(SpKeywordMetric.keyword_id)).label("keyword_count"),
            func.coalesce(func.sum(SpKeywordMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0).label("sales"),
        )
        .where(*filters)
        .group_by(
            SpKeywordMetric.market_id,
            SpKeywordMetric.campaign_id,
            SpKeywordMetric.campaign_name,
            SpKeywordMetric.ad_group_id,
            SpKeywordMetric.ad_group_name,
        )
        .order_by(func.sum(SpKeywordMetric.cost).desc())
    ).first()
    if row is None:
        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "scope_name": None,
            "market_id": market_id,
            "campaign_id": None,
            "campaign_name": None,
            "ad_group_id": None,
            "ad_group_name": None,
            "metric_rows": 0,
            "keyword_count": 0,
            "search_term_rows": 0,
            "impressions": 0,
            "clicks": 0,
            "cost": 0.0,
            "orders": 0,
            "sales": 0.0,
            "acos": 0.0,
            "cvr": 0.0,
        }
    search_filters = _scope_filters(SpSearchTermMetric, scope_type, scope_id) + _date_filters(SpSearchTermMetric, period_start, period_end)
    if market_id is not None:
        search_filters.append(SpSearchTermMetric.market_id == market_id)
    search_term_rows = db.execute(select(func.count(SpSearchTermMetric.id)).where(*search_filters)).scalar_one()
    cost = float(row.cost or 0)
    sales = float(row.sales or 0)
    orders = int(row.orders or 0)
    clicks = int(row.clicks or 0)
    rates = _rate_metrics(cost, sales, orders, clicks)
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "scope_name": row.campaign_name if scope_type == "campaign" else row.ad_group_name,
        "market_id": row.market_id,
        "campaign_id": row.campaign_id,
        "campaign_name": row.campaign_name,
        "ad_group_id": row.ad_group_id,
        "ad_group_name": row.ad_group_name,
        "metric_rows": int(row.metric_rows or 0),
        "keyword_count": int(row.keyword_count or 0),
        "search_term_rows": int(search_term_rows or 0),
        "impressions": int(row.impressions or 0),
        "clicks": clicks,
        "cost": _round(cost, 2),
        "orders": orders,
        "sales": _round(sales, 2),
        **rates,
    }


def _top_keywords(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
    scope_id: str,
    limit: int = 5,
) -> list[dict[str, object]]:
    filters = _scope_filters(SpKeywordMetric, scope_type, scope_id) + _date_filters(SpKeywordMetric, period_start, period_end)
    if market_id is not None:
        filters.append(SpKeywordMetric.market_id == market_id)
    rows = db.execute(
        select(
            SpKeywordMetric.keyword_id,
            SpKeywordMetric.keyword_text,
            func.coalesce(func.sum(SpKeywordMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpKeywordMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpKeywordMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpKeywordMetric.ads_sales), 0).label("sales"),
        )
        .where(*filters)
        .group_by(SpKeywordMetric.keyword_id, SpKeywordMetric.keyword_text)
        .order_by(func.sum(SpKeywordMetric.cost).desc())
        .limit(limit)
    ).all()
    result = []
    for row in rows:
        cost = float(row.cost or 0)
        sales = float(row.sales or 0)
        orders = int(row.orders or 0)
        clicks = int(row.clicks or 0)
        result.append(
            {
                "keyword_id": row.keyword_id,
                "keyword_text": row.keyword_text,
                "clicks": clicks,
                "cost": _round(cost, 2),
                "orders": orders,
                "sales": _round(sales, 2),
                **_rate_metrics(cost, sales, orders, clicks),
            }
        )
    return result


def _top_search_terms(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
    scope_id: str,
    limit: int = 5,
) -> list[dict[str, object]]:
    filters = _scope_filters(SpSearchTermMetric, scope_type, scope_id) + _date_filters(SpSearchTermMetric, period_start, period_end)
    if market_id is not None:
        filters.append(SpSearchTermMetric.market_id == market_id)
    rows = db.execute(
        select(
            SpSearchTermMetric.search_term,
            SpSearchTermMetric.keyword_text,
            func.coalesce(func.sum(SpSearchTermMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpSearchTermMetric.cost), 0).label("cost"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_sales), 0).label("sales"),
        )
        .where(*filters)
        .group_by(SpSearchTermMetric.search_term, SpSearchTermMetric.keyword_text)
        .order_by(func.sum(SpSearchTermMetric.cost).desc())
        .limit(limit)
    ).all()
    result = []
    for row in rows:
        cost = float(row.cost or 0)
        sales = float(row.sales or 0)
        orders = int(row.orders or 0)
        clicks = int(row.clicks or 0)
        result.append(
            {
                "search_term": row.search_term,
                "keyword_text": row.keyword_text,
                "clicks": clicks,
                "cost": _round(cost, 2),
                "orders": orders,
                "sales": _round(sales, 2),
                **_rate_metrics(cost, sales, orders, clicks),
            }
        )
    return result


def _product_candidate_payload(
    product: Product,
    goal: ProductGoal | None,
    rule: ProductRule | None,
    *,
    source: dict[str, object],
    top_keywords: list[dict[str, object]],
    top_search_terms: list[dict[str, object]],
) -> dict[str, object]:
    score = 0
    reasons: list[str] = []
    if product.market_id is not None and product.market_id == source.get("market_id"):
        score += 20
        reasons.append("同店铺 / 站点")
    product_values = [product.product_name, product.asin, product.msku, product.sku, product.brand, product.category]
    product_text = " ".join(str(value or "").lower() for value in product_values)
    source_text = _source_text(source, top_keywords, top_search_terms)
    matched_tokens = sorted(_text_tokens(*product_values) & _text_tokens(source_text))
    if matched_tokens:
        score += min(45, len(matched_tokens) * 15)
        reasons.append("名称词匹配：" + " / ".join(matched_tokens[:5]))
    exact_codes = [value for value in [product.asin, product.msku, product.sku] if value and str(value).lower() in source_text]
    if exact_codes:
        score += 30
        reasons.append("ASIN / SKU / MSKU 匹配：" + " / ".join(str(value) for value in exact_codes[:3]))
    product_name_tokens = _text_tokens(product.product_name)
    if product_name_tokens and product_name_tokens.issubset(_text_tokens(source_text)):
        score += 10
        reasons.append("产品名称主要词完整匹配")
    if not reasons:
        reasons.append("未发现明显名称或编码匹配，需要人工谨慎判断")
    score = min(100, score)
    return {
        "product_id": product.id,
        "product_name": product.product_name,
        "asin": product.asin,
        "msku": product.msku,
        "sku": product.sku,
        "market_id": product.market_id,
        "goal_type": goal.goal_type if goal else None,
        "inventory_quantity": product.inventory_quantity,
        "target_acos": rule.target_acos if rule else None,
        "confidence_score": score,
        "confidence_level": _confidence_level(score),
        "reasons": reasons,
    }


def _conflicts(
    db: Session,
    *,
    market_id: int | None,
    scope_type: str,
    scope_id: str,
) -> list[dict[str, object]]:
    filters = [
        ProductAdBinding.status == "active",
        ProductAdBinding.scope_type == scope_type,
        ProductAdBinding.scope_id == scope_id,
    ]
    if market_id is not None:
        filters.append(ProductAdBinding.market_id == market_id)
    rows = db.execute(select(ProductAdBinding).where(*filters).order_by(ProductAdBinding.updated_at.desc())).scalars().all()
    return [
        {
            "binding_id": row.id,
            "product_id": row.product_id,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "scope_name": row.scope_name,
            "created_by": row.created_by,
            "updated_at": row.updated_at.isoformat(),
            "message": "该广告对象已有归因规则，重新确认会覆盖本地归因关系",
        }
        for row in rows
    ]


def build_product_attribution_evidence(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
    scope_id: str,
    selected_product_id: int | None = None,
) -> dict[str, object]:
    source = _source_summary(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    top_keywords = _top_keywords(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    top_search_terms = _top_search_terms(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    product_filters = []
    if market_id is not None:
        product_filters.append((Product.market_id == market_id) | (Product.market_id.is_(None)))
    products = db.execute(select(Product).where(*product_filters).order_by(Product.id)).scalars().all()
    goals = {goal.product_id: goal for goal in db.execute(select(ProductGoal)).scalars().all()}
    rules = {rule.product_id: rule for rule in db.execute(select(ProductRule)).scalars().all()}
    candidates = [
        _product_candidate_payload(
            product,
            goals.get(product.id),
            rules.get(product.id),
            source=source,
            top_keywords=top_keywords,
            top_search_terms=top_search_terms,
        )
        for product in products
    ]
    candidates.sort(key=lambda item: int(item["confidence_score"]), reverse=True)
    selected = next((item for item in candidates if item["product_id"] == selected_product_id), None)
    return {
        "period": {"start": period_start, "end": period_end},
        "source": source,
        "top_keywords": top_keywords,
        "top_search_terms": top_search_terms,
        "candidate_products": candidates,
        "selected_product": selected,
        "conflicts": _conflicts(db, market_id=market_id, scope_type=scope_type, scope_id=scope_id),
    }


def build_product_attribution_candidates(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    scope_type: str,
    min_confidence: int = 40,
    limit: int = 30,
) -> dict[str, object]:
    sources = list_unbound_ad_sources(
        db,
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        scope_type=scope_type,
    )
    rows: list[dict[str, object]] = []
    for source in sources:
        scope_id = source.get("scope_id")
        if not scope_id:
            continue
        evidence = build_product_attribution_evidence(
            db,
            market_id=market_id,
            period_start=period_start,
            period_end=period_end,
            scope_type=scope_type,
            scope_id=str(scope_id),
        )
        candidate_products = evidence.get("candidate_products") if isinstance(evidence.get("candidate_products"), list) else []
        candidate = candidate_products[0] if candidate_products else None
        if not isinstance(candidate, dict):
            continue
        score = int(candidate.get("confidence_score") or 0)
        if score < min_confidence:
            continue
        rows.append(
            {
                "candidate_id": f"{scope_type}:{scope_id}:{candidate.get('product_id')}",
                "source": source,
                "candidate_product": candidate,
                "confidence_score": score,
                "confidence_level": candidate.get("confidence_level"),
                "confidence_reasons": candidate.get("reasons") or [],
                "metrics": {
                    "clicks": source.get("clicks"),
                    "cost": source.get("cost"),
                    "orders": source.get("orders"),
                    "sales": source.get("sales"),
                    "acos": source.get("acos"),
                    "cvr": source.get("cvr"),
                    "metric_rows": source.get("metric_rows"),
                    "search_term_rows": source.get("search_term_rows"),
                },
                "evidence_preview": {
                    "top_keyword": (evidence.get("top_keywords") or [{}])[0],
                    "top_search_term": (evidence.get("top_search_terms") or [{}])[0],
                    "conflict_count": len(evidence.get("conflicts") or []),
                },
                "manual_hint": "必须查看证据并由人工确认后才会保存归因规则",
            }
        )
    rows.sort(key=lambda item: (int(item["confidence_score"]), float(item["metrics"].get("cost") or 0)), reverse=True)
    for index, row in enumerate(rows, start=1):
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        row["priority_rank"] = index
        row["priority_label"] = "建议优先确认" if index <= 3 else "可后续确认"
        row["unlock_impact"] = _candidate_unlock_impact(metrics)
    selected = rows[: max(1, min(limit, 100))]
    return {
        "period": {"start": period_start, "end": period_end},
        "filters": {
            "market_id": market_id,
            "scope_type": scope_type,
            "min_confidence": min_confidence,
            "limit": limit,
        },
        "summary": {
            "total_candidates": len(selected),
            "high_confidence_count": sum(1 for item in selected if int(item["confidence_score"]) >= 70),
            "medium_confidence_count": sum(1 for item in selected if 40 <= int(item["confidence_score"]) < 70),
        },
        "rows": selected,
    }
