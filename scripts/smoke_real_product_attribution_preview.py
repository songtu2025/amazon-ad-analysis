import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "http://127.0.0.1:8001"
FORBIDDEN_ACTION_KEYS = {
    "execute",
    "auto_execute",
    "execution_url",
    "execution_payload",
    "bid_adjustment",
    "new_bid",
    "pause_ad",
    "enable_ad",
    "negative_keyword",
    "create_keyword",
}


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def request_json(path: str, params: dict[str, object] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{API_BASE_URL}{path}{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=12) as response:
            status = getattr(response, "status", 200)
            text = response.read().decode("utf-8", errors="replace")
            if status < 200 or status >= 300:
                fail(f"{url} 返回状态码 {status}：{text}")
            return json.loads(text)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        fail(f"{url} 返回状态码 {exc.code}：{body}")
    except URLError as exc:
        fail(f"{url} 不可访问：{exc.reason}")


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(key_path)
            hits.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def assert_no_auto_execution_fields(payloads: dict[str, Any]) -> None:
    hits: list[str] = []
    for name, payload in payloads.items():
        hits.extend(f"{name}:{hit}" for hit in find_forbidden_keys(payload))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))


def latest_success_period() -> dict[str, object]:
    runs = request_json("/api/sync/runs", {"limit": 20})
    if not isinstance(runs, list):
        fail("同步记录接口返回格式异常")
    for run in runs:
        if (
            isinstance(run, dict)
            and run.get("status") == "success"
            and run.get("market_id") is not None
            and run.get("period_start")
            and run.get("period_end")
        ):
            return {
                "market_id": int(run["market_id"]),
                "period_start": str(run["period_start"]),
                "period_end": str(run["period_end"]),
                "source": run.get("source"),
            }
    fail("未找到可用于归因预览的成功同步周期")


def top_unbound_sources(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, object]]:
    def cost(row: dict[str, Any]) -> float:
        value = row.get("cost")
        return float(value) if isinstance(value, int | float) else 0.0

    selected = sorted(rows, key=cost, reverse=True)[:limit]
    result = []
    for row in selected:
        result.append(
            {
                "scope_type": row.get("scope_type"),
                "scope_id": row.get("scope_id"),
                "scope_name": row.get("scope_name"),
                "campaign_id": row.get("campaign_id"),
                "campaign_name": row.get("campaign_name"),
                "ad_group_id": row.get("ad_group_id"),
                "ad_group_name": row.get("ad_group_name"),
                "metric_rows": row.get("metric_rows"),
                "search_term_rows": row.get("search_term_rows"),
                "cost": row.get("cost"),
                "sales": row.get("sales"),
                "orders": row.get("orders"),
                "acos": row.get("acos"),
            }
        )
    return result


def product_candidates(products: list[dict[str, Any]], limit: int = 8) -> list[dict[str, object]]:
    result = []
    for product in products[:limit]:
        metrics = product.get("sp_metrics") if isinstance(product.get("sp_metrics"), dict) else {}
        goal = product.get("goal") if isinstance(product.get("goal"), dict) else {}
        result.append(
            {
                "id": product.get("id"),
                "product_name": product.get("product_name"),
                "asin": product.get("asin"),
                "msku": product.get("msku"),
                "goal_type": goal.get("goal_type") if isinstance(goal, dict) else None,
                "cost": metrics.get("cost"),
                "sales": metrics.get("sales"),
                "orders": metrics.get("orders"),
                "acos": metrics.get("acos"),
            }
        )
    return result


def is_demo_product(product: dict[str, Any]) -> bool:
    values = [
        product.get("product_name"),
        product.get("asin"),
        product.get("msku"),
        product.get("sku"),
    ]
    text = " ".join(str(value or "") for value in values).upper()
    return any(marker in text for marker in ["DEMO", "SMOKE", "TASK010", "TASK020", "????"])


def main() -> None:
    period = latest_success_period()
    filters = {
        "market_id": period["market_id"],
        "start_date": period["period_start"],
        "end_date": period["period_end"],
    }
    dashboard = request_json("/api/dashboard/summary", filters)
    products = request_json("/api/products", filters)
    campaign_sources = request_json("/api/products/unbound-ad-sources", {**filters, "scope_type": "campaign"})
    ad_group_sources = request_json("/api/products/unbound-ad-sources", {**filters, "scope_type": "ad_group"})
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})

    if not isinstance(products, list):
        fail("产品列表接口返回格式异常")
    if not isinstance(campaign_sources, list) or not isinstance(ad_group_sources, list):
        fail("未归因数据池接口返回格式异常")
    if len(campaign_sources) <= 0 and len(ad_group_sources) <= 0:
        fail("真实库没有未归因广告来源，无法预览人工归因")
    if len(bindings_before) != len(bindings_after):
        fail("只读预览前后归因规则数量变化，疑似发生写库动作")

    assert_no_auto_execution_fields(
        {
            "dashboard": dashboard,
            "products": products,
            "campaign_sources": campaign_sources,
            "ad_group_sources": ad_group_sources,
            "bindings": bindings_after,
        }
    )

    real_products = [product for product in products if isinstance(product, dict) and not is_demo_product(product)]
    ready_for_manual_binding = bool(real_products) and bool(campaign_sources or ad_group_sources)
    blocking_reasons = []
    if not real_products:
        blocking_reasons.append("当前产品候选只有演示/测试产品，不能用于真实广告归因")
    if not (campaign_sources or ad_group_sources):
        blocking_reasons.append("当前没有未归因广告来源")

    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "market": dashboard.get("market") if isinstance(dashboard, dict) else None,
                "product_binding": dashboard.get("product_binding") if isinstance(dashboard, dict) else None,
                "ready_for_manual_binding": ready_for_manual_binding,
                "blocking_reasons": blocking_reasons,
                "product_count": len(products),
                "real_product_count": len(real_products),
                "campaign_unbound_count": len(campaign_sources),
                "ad_group_unbound_count": len(ad_group_sources),
                "active_binding_count": len(bindings_after),
                "product_candidates": product_candidates(products),
                "top_unbound_campaigns": top_unbound_sources(campaign_sources),
                "top_unbound_ad_groups": top_unbound_sources(ad_group_sources),
                "checked": [
                    "latest_success_sync_period",
                    "dashboard_identity",
                    "product_candidates",
                    "unbound_campaign_pool",
                    "unbound_ad_group_pool",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
