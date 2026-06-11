import re
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ad_metrics import SpSearchTermMetric
from app.models.product import Product, ProductAdBinding


SEMANTIC_LABELS = {
    "asin": "ASIN / 商品编号词",
    "accessory_or_unrelated": "疑似配件或无关词",
    "age_spec": "年龄 / 人群规格词",
    "core_product": "核心产品词",
    "generic": "泛搜索词",
}

PERFORMANCE_LABELS = {
    "high_conversion": "高转化词",
    "costly_no_order": "高花费无单词",
    "high_acos": "有单但 ACOS 高",
    "data_insufficient": "数据不足",
    "observe": "继续观察",
}

CANDIDATE_LABELS = {
    "scale_opportunity": "高转化放量候选",
    "waste_risk": "高花费无单处理候选",
    "efficiency_risk": "高 ACOS 处理候选",
}

ASIN_PATTERN = re.compile(r"\bb0[a-z0-9]{8}\b", re.IGNORECASE)
AGE_WORDS = {"baby", "infant", "toddler", "kid", "kids", "boy", "boys", "girl", "girls", "month", "months", "year", "years", "old"}
CORE_WORDS = {"sunglass", "sunglasses", "shade", "shades", "polarized"}
ACCESSORY_WORDS = {"hat", "sunhat", "cap", "strap", "case", "cloth", "holder"}


def _round(value: float | None, digits: int = 4) -> float:
    return round(float(value or 0), digits)


def classify_semantic(search_term: str) -> tuple[str, list[str]]:
    text = (search_term or "").lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    reasons: list[str] = []
    if ASIN_PATTERN.search(text):
        return "asin", ["包含 ASIN 形态的商品编号"]
    has_core = bool(tokens & CORE_WORDS)
    has_age = bool(tokens & AGE_WORDS) or bool(re.search(r"\d+\s*-\s*\d+", text))
    has_accessory = bool(tokens & ACCESSORY_WORDS)
    if has_accessory and not has_core:
        return "accessory_or_unrelated", ["包含配件词且未出现核心产品词"]
    if has_age and has_core:
        reasons.append("同时包含人群 / 年龄词和核心产品词")
        return "age_spec", reasons
    if has_core:
        return "core_product", ["包含核心产品词"]
    if has_age:
        return "age_spec", ["包含人群 / 年龄词"]
    return "generic", ["未命中明确产品、人群或编号规则"]


def classify_performance(
    *,
    clicks: int,
    cost: float,
    orders: int,
    sales: float,
    min_clicks: int,
    min_spend: float,
    target_acos: float,
) -> tuple[str, list[str]]:
    acos = cost / sales if sales else 0
    if orders > 0 and sales > 0 and acos <= target_acos:
        return "high_conversion", [f"有订单且 ACOS {acos:.2%} 不高于目标 {target_acos:.2%}"]
    if orders > 0 and sales > 0 and acos > target_acos:
        return "high_acos", [f"有订单但 ACOS {acos:.2%} 高于目标 {target_acos:.2%}"]
    if clicks < min_clicks and cost < min_spend:
        return "data_insufficient", [f"点击 {clicks}、花费 {cost:.2f} 未达到判断门槛"]
    if orders <= 0 and (clicks >= min_clicks or cost >= min_spend):
        return "costly_no_order", ["达到点击或花费门槛但没有广告订单"]
    return "observe", ["当前数据未触发明确表现分类"]


def _summary_bucket() -> dict[str, float | int]:
    return {
        "terms": 0,
        "clicks": 0,
        "cost": 0.0,
        "orders": 0,
        "sales": 0.0,
    }


def _bucket_payload(key: str, label: str, bucket: dict[str, float | int]) -> dict[str, object]:
    cost = float(bucket["cost"] or 0)
    sales = float(bucket["sales"] or 0)
    clicks = int(bucket["clicks"] or 0)
    orders = int(bucket["orders"] or 0)
    return {
        "key": key,
        "label": label,
        "terms": int(bucket["terms"] or 0),
        "clicks": clicks,
        "cost": _round(cost, 2),
        "orders": orders,
        "sales": _round(sales, 2),
        "acos": _round(cost / sales) if sales else 0,
        "cvr": _round(orders / clicks) if clicks else 0,
    }


def _group_bucket(semantic_key: str, performance_key: str) -> dict[str, object]:
    return {
        "semantic_category": semantic_key,
        "performance_status": performance_key,
        "terms": 0,
        "clicks": 0,
        "cost": 0.0,
        "orders": 0,
        "sales": 0.0,
        "representative_terms": [],
    }


def _group_payload(bucket: dict[str, object]) -> dict[str, object]:
    semantic_key = str(bucket["semantic_category"])
    performance_key = str(bucket["performance_status"])
    cost = float(bucket["cost"] or 0)
    sales = float(bucket["sales"] or 0)
    clicks = int(bucket["clicks"] or 0)
    orders = int(bucket["orders"] or 0)
    return {
        "group_key": f"{semantic_key}:{performance_key}",
        "group_label": f"{SEMANTIC_LABELS[semantic_key]} / {PERFORMANCE_LABELS[performance_key]}",
        "semantic_category": semantic_key,
        "semantic_label": SEMANTIC_LABELS[semantic_key],
        "performance_status": performance_key,
        "performance_label": PERFORMANCE_LABELS[performance_key],
        "terms": int(bucket["terms"] or 0),
        "clicks": clicks,
        "cost": _round(cost, 2),
        "orders": orders,
        "sales": _round(sales, 2),
        "acos": _round(cost / sales) if sales else 0,
        "cvr": _round(orders / clicks) if clicks else 0,
        "representative_terms": list(bucket.get("representative_terms") or []),
        "manual_hint": "按归类组先做人工复核，不会自动修改广告",
    }


def analyze_search_terms(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    product_id: int | None = None,
    semantic_category: str | None = None,
    performance_status: str | None = None,
    min_clicks: int = 10,
    min_spend: float = 10.0,
    target_acos: float = 0.35,
    limit: int = 100,
) -> dict[str, object]:
    filters = [
        SpSearchTermMetric.data_date >= period_start,
        SpSearchTermMetric.data_date <= period_end,
        SpSearchTermMetric.search_term.is_not(None),
        func.trim(SpSearchTermMetric.search_term) != "",
    ]
    if market_id is not None:
        filters.append(SpSearchTermMetric.market_id == market_id)
    if product_id is not None:
        filters.append(SpSearchTermMetric.product_id == product_id)

    rows = db.execute(
        select(
            SpSearchTermMetric.search_term,
            func.count(SpSearchTermMetric.id).label("metric_rows"),
            func.count(func.distinct(SpSearchTermMetric.campaign_id)).label("campaign_count"),
            func.count(func.distinct(SpSearchTermMetric.ad_group_id)).label("ad_group_count"),
            func.count(func.distinct(SpSearchTermMetric.keyword_id)).label("keyword_count"),
            func.coalesce(func.sum(SpSearchTermMetric.impressions), 0).label("impressions"),
            func.coalesce(func.sum(SpSearchTermMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpSearchTermMetric.cost), 0.0).label("cost"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_sales), 0.0).label("sales"),
            func.min(SpSearchTermMetric.campaign_name).label("campaign_name"),
            func.min(SpSearchTermMetric.ad_group_name).label("ad_group_name"),
            func.min(SpSearchTermMetric.keyword_text).label("keyword_text"),
        )
        .where(*filters)
        .group_by(SpSearchTermMetric.search_term)
        .order_by(func.sum(SpSearchTermMetric.cost).desc())
    ).all()

    result_rows: list[dict[str, object]] = []
    category_buckets: dict[str, dict[str, float | int]] = defaultdict(_summary_bucket)
    performance_buckets: dict[str, dict[str, float | int]] = defaultdict(_summary_bucket)
    group_buckets: dict[str, dict[str, object]] = {}
    totals = _summary_bucket()

    for row in rows:
        search_text = str(row.search_term or "")
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        semantic_key, semantic_reasons = classify_semantic(search_text)
        performance_key, performance_reasons = classify_performance(
            clicks=clicks,
            cost=cost,
            orders=orders,
            sales=sales,
            min_clicks=min_clicks,
            min_spend=min_spend,
            target_acos=target_acos,
        )
        if semantic_category and semantic_key != semantic_category:
            continue
        if performance_status and performance_key != performance_status:
            continue
        group_key = f"{semantic_key}:{performance_key}"
        if group_key not in group_buckets:
            group_buckets[group_key] = _group_bucket(semantic_key, performance_key)
        metric = {
            "search_term": search_text,
            "semantic_category": semantic_key,
            "semantic_label": SEMANTIC_LABELS[semantic_key],
            "semantic_reasons": semantic_reasons,
            "performance_status": performance_key,
            "performance_label": PERFORMANCE_LABELS[performance_key],
            "performance_reasons": performance_reasons,
            "metric_rows": int(row.metric_rows or 0),
            "campaign_count": int(row.campaign_count or 0),
            "ad_group_count": int(row.ad_group_count or 0),
            "keyword_count": int(row.keyword_count or 0),
            "impressions": int(row.impressions or 0),
            "clicks": clicks,
            "cost": _round(cost, 2),
            "orders": orders,
            "sales": _round(sales, 2),
            "acos": _round(cost / sales) if sales else 0,
            "cvr": _round(orders / clicks) if clicks else 0,
            "evidence": {
                "campaign_name": row.campaign_name,
                "ad_group_name": row.ad_group_name,
                "keyword_text": row.keyword_text,
            },
            "manual_hint": "仅供人工判断，不会自动修改广告",
        }
        result_rows.append(metric)
        for bucket in (category_buckets[semantic_key], performance_buckets[performance_key], totals):
            bucket["terms"] = int(bucket["terms"]) + 1
            bucket["clicks"] = int(bucket["clicks"]) + clicks
            bucket["cost"] = float(bucket["cost"]) + cost
            bucket["orders"] = int(bucket["orders"]) + orders
            bucket["sales"] = float(bucket["sales"]) + sales
        group_bucket = group_buckets[group_key]
        group_bucket["terms"] = int(group_bucket["terms"]) + 1
        group_bucket["clicks"] = int(group_bucket["clicks"]) + clicks
        group_bucket["cost"] = float(group_bucket["cost"]) + cost
        group_bucket["orders"] = int(group_bucket["orders"]) + orders
        group_bucket["sales"] = float(group_bucket["sales"]) + sales
        representative_terms = group_bucket.get("representative_terms")
        if isinstance(representative_terms, list) and len(representative_terms) < 5:
            representative_terms.append(search_text)

    result_rows = result_rows[: max(1, min(limit, 500))]
    category_summary = [
        _bucket_payload(key, SEMANTIC_LABELS[key], value)
        for key, value in sorted(category_buckets.items(), key=lambda item: float(item[1]["cost"]), reverse=True)
    ]
    performance_summary = [
        _bucket_payload(key, PERFORMANCE_LABELS[key], value)
        for key, value in sorted(performance_buckets.items(), key=lambda item: float(item[1]["cost"]), reverse=True)
    ]
    group_summary = [
        _group_payload(value)
        for value in sorted(group_buckets.values(), key=lambda item: float(item["cost"] or 0), reverse=True)
    ]
    return {
        "period": {"start": period_start, "end": period_end},
        "filters": {
            "market_id": market_id,
            "product_id": product_id,
            "semantic_category": semantic_category,
            "performance_status": performance_status,
            "min_clicks": min_clicks,
            "min_spend": min_spend,
            "target_acos": target_acos,
            "limit": limit,
        },
        "summary": {
            **_bucket_payload("all", "全部搜索词", totals),
            "distinct_terms": int(totals["terms"] or 0),
        },
        "category_summary": category_summary,
        "performance_summary": performance_summary,
        "group_summary": group_summary,
        "rows": result_rows,
    }


def build_product_search_term_readiness(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    product_id: int | None = None,
) -> dict[str, object]:
    binding_filters = [ProductAdBinding.status == "active"]
    product_filters = []
    metric_filters = [
        SpSearchTermMetric.data_date >= period_start,
        SpSearchTermMetric.data_date <= period_end,
        SpSearchTermMetric.product_id.is_not(None),
        SpSearchTermMetric.search_term.is_not(None),
        func.trim(SpSearchTermMetric.search_term) != "",
    ]
    if market_id is not None:
        binding_filters.append(ProductAdBinding.market_id == market_id)
        product_filters.append(Product.market_id == market_id)
        metric_filters.append(SpSearchTermMetric.market_id == market_id)
    if product_id is not None:
        binding_filters.append(ProductAdBinding.product_id == product_id)
        product_filters.append(Product.id == product_id)
        metric_filters.append(SpSearchTermMetric.product_id == product_id)

    active_binding_count = int(db.execute(select(func.count(ProductAdBinding.id)).where(*binding_filters)).scalar_one() or 0)
    product_count = int(db.execute(select(func.count(Product.id)).where(*product_filters)).scalar_one() or 0)
    bound_search_term_rows = int(db.execute(select(func.count(SpSearchTermMetric.id)).where(*metric_filters)).scalar_one() or 0)

    product_rows = db.execute(
        select(
            SpSearchTermMetric.product_id,
            func.count(SpSearchTermMetric.id).label("search_term_rows"),
            func.count(func.distinct(SpSearchTermMetric.search_term)).label("distinct_terms"),
            func.coalesce(func.sum(SpSearchTermMetric.clicks), 0).label("clicks"),
            func.coalesce(func.sum(SpSearchTermMetric.cost), 0.0).label("cost"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_orders), 0).label("orders"),
            func.coalesce(func.sum(SpSearchTermMetric.ads_sales), 0.0).label("sales"),
        )
        .where(*metric_filters)
        .group_by(SpSearchTermMetric.product_id)
        .order_by(func.sum(SpSearchTermMetric.cost).desc())
    ).all()
    product_ids = [int(row.product_id) for row in product_rows if row.product_id is not None]
    products = {}
    if product_ids:
        products = {product.id: product for product in db.execute(select(Product).where(Product.id.in_(product_ids))).scalars().all()}

    product_payloads = []
    for row in product_rows:
        row_product_id = int(row.product_id)
        product = products.get(row_product_id)
        clicks = int(row.clicks or 0)
        cost = float(row.cost or 0)
        orders = int(row.orders or 0)
        sales = float(row.sales or 0)
        product_payloads.append(
            {
                "product_id": row_product_id,
                "product_name": product.product_name if product else None,
                "asin": product.asin if product else None,
                "msku": product.msku if product else None,
                "search_term_rows": int(row.search_term_rows or 0),
                "distinct_terms": int(row.distinct_terms or 0),
                "clicks": clicks,
                "cost": _round(cost, 2),
                "orders": orders,
                "sales": _round(sales, 2),
                "acos": _round(cost / sales) if sales else 0,
                "cvr": _round(orders / clicks) if clicks else 0,
            }
        )

    ready = active_binding_count > 0 and bound_search_term_rows > 0
    if active_binding_count <= 0:
        manual_hint = "请先在产品设置页人工确认产品归因规则"
    elif bound_search_term_rows <= 0:
        manual_hint = "已存在人工确认归因规则，但当前周期没有已归因搜索词数据"
    else:
        manual_hint = "产品维度搜索词分析已就绪，可以按产品筛选查看"

    return {
        "period": {"start": period_start, "end": period_end},
        "filters": {"market_id": market_id, "product_id": product_id},
        "ready": ready,
        "status": "ready" if ready else "needs_attribution",
        "manual_hint": manual_hint,
        "summary": {
            "active_binding_count": active_binding_count,
            "bound_search_term_rows": bound_search_term_rows,
            "product_count": product_count,
            "products_with_search_terms": len(product_payloads),
        },
        "products": product_payloads,
    }


def _candidate_from_row(row: dict[str, object]) -> dict[str, object] | None:
    search_term = str(row.get("search_term") or "")
    performance_status = str(row.get("performance_status") or "")
    if performance_status == "high_conversion":
        candidate_type = "scale_opportunity"
        recommended_decision = "adopt_with_changes"
        title = f"高转化词候选：{search_term}"
        suggested_manual_action = "人工复核相关性和产品目标，确认后可考虑提高投放优先级或转入更精细的人工管理。"
        reasoning = "该搜索词有订单且 ACOS 不高于目标，说明当前流量质量相对较好。"
        risk_note = "放大前仍需确认库存、利润、Listing 承接和是否属于目标产品，系统不会自动调整广告。"
    elif performance_status == "costly_no_order":
        candidate_type = "waste_risk"
        recommended_decision = "adopt_with_changes"
        title = f"高花费无单候选：{search_term}"
        suggested_manual_action = "人工判断搜索词相关性；无关则记录为处理候选，相关但未转化则先观察或小幅收缩。"
        reasoning = "该搜索词达到点击或花费门槛，但当前周期没有广告订单。"
        risk_note = "核心词不能只凭短期无单直接处理，需要结合产品承接、价格、评价和库存判断。"
    elif performance_status == "high_acos":
        candidate_type = "efficiency_risk"
        recommended_decision = "adopt_with_changes"
        title = f"高 ACOS 候选：{search_term}"
        suggested_manual_action = "人工复核利润空间和目标 ACOS，确认后记录为观察或小步调整候选。"
        reasoning = "该搜索词有订单但 ACOS 高于目标，说明存在效率风险。"
        risk_note = "直接收缩可能影响有效订单，需要按产品目标判断是否接受更高获客成本。"
    else:
        return None

    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    metrics = {
        "impressions": row.get("impressions"),
        "clicks": row.get("clicks"),
        "cost": row.get("cost"),
        "orders": row.get("orders"),
        "sales": row.get("sales"),
        "acos": row.get("acos"),
        "cvr": row.get("cvr"),
        "metric_rows": row.get("metric_rows"),
    }
    return {
        "candidate_id": f"{candidate_type}:{search_term}",
        "candidate_type": candidate_type,
        "candidate_label": CANDIDATE_LABELS[candidate_type],
        "search_term": search_term,
        "title": title,
        "recommended_manual_decision": recommended_decision,
        "suggested_manual_action": suggested_manual_action,
        "reasoning": reasoning,
        "risk_note": risk_note,
        "semantic_category": row.get("semantic_category"),
        "semantic_label": row.get("semantic_label"),
        "performance_status": row.get("performance_status"),
        "performance_label": row.get("performance_label"),
        "metrics": metrics,
        "evidence": {
            "campaign_name": evidence.get("campaign_name"),
            "ad_group_name": evidence.get("ad_group_name"),
            "keyword_text": evidence.get("keyword_text"),
            "campaign_count": row.get("campaign_count"),
            "ad_group_count": row.get("ad_group_count"),
            "keyword_count": row.get("keyword_count"),
        },
        "source_trace": {
            "source": "sp_search_term_metrics",
            "search_term": search_term,
            "semantic_reasons": row.get("semantic_reasons"),
            "performance_reasons": row.get("performance_reasons"),
        },
        "manual_hint": "候选仅供人工判断，不会自动修改广告",
    }


def build_search_term_candidates(
    db: Session,
    *,
    market_id: int | None,
    period_start: str,
    period_end: str,
    product_id: int | None = None,
    semantic_category: str | None = None,
    performance_status: str | None = None,
    candidate_type: str | None = None,
    min_clicks: int = 10,
    min_spend: float = 10.0,
    target_acos: float = 0.35,
    limit: int = 100,
) -> dict[str, object]:
    analysis = analyze_search_terms(
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
        limit=500,
    )
    candidates = []
    for row in analysis["rows"]:
        candidate = _candidate_from_row(row)
        if candidate is None:
            continue
        if candidate_type and candidate["candidate_type"] != candidate_type:
            continue
        candidates.append(candidate)
    candidates = candidates[: max(1, min(limit, 200))]
    type_summary = []
    for key, label in CANDIDATE_LABELS.items():
        count = sum(1 for item in candidates if item["candidate_type"] == key)
        if count:
            type_summary.append({"key": key, "label": label, "count": count})
    return {
        "period": analysis["period"],
        "filters": {
            **analysis["filters"],
            "candidate_type": candidate_type,
        },
        "summary": {
            "total_candidates": len(candidates),
            "scale_opportunity_count": sum(1 for item in candidates if item["candidate_type"] == "scale_opportunity"),
            "waste_risk_count": sum(1 for item in candidates if item["candidate_type"] == "waste_risk"),
            "efficiency_risk_count": sum(1 for item in candidates if item["candidate_type"] == "efficiency_risk"),
        },
        "type_summary": type_summary,
        "rows": candidates,
    }
