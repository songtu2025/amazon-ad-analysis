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
    fail("未找到可用于产品归因复核的成功同步周期")


def is_demo_product(product: dict[str, Any]) -> bool:
    values = [
        product.get("product_name"),
        product.get("asin"),
        product.get("msku"),
        product.get("sku"),
    ]
    text = " ".join(str(value or "") for value in values).upper()
    return any(marker in text for marker in ["DEMO", "SMOKE", "TASK010", "TASK020", "TASK030", "????"])


def main() -> None:
    period = latest_success_period()
    filters = {
        "market_id": period["market_id"],
        "start_date": period["period_start"],
        "end_date": period["period_end"],
    }
    products = request_json("/api/products", filters)
    ad_group_sources = request_json("/api/products/unbound-ad-sources", {**filters, "scope_type": "ad_group"})
    bindings = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})

    if not isinstance(products, list):
        fail("产品列表接口返回格式异常")
    if not isinstance(ad_group_sources, list):
        fail("未归因 Ad Group 数据池接口返回格式异常")

    real_products = [product for product in products if isinstance(product, dict) and not is_demo_product(product)]
    if not real_products:
        fail("真实库缺少非演示产品草稿，产品归因仍不可日常使用")
    if not ad_group_sources:
        fail("真实库缺少未归因广告来源，无法复核归因可用性")

    assert_no_auto_execution_fields({"products": products, "ad_group_sources": ad_group_sources, "bindings": bindings})
    print(
        json.dumps(
            {
                "status": "success",
                "ready_for_manual_binding": True,
                "period": period,
                "real_product_count": len(real_products),
                "ad_group_unbound_count": len(ad_group_sources),
                "active_binding_count": len(bindings) if isinstance(bindings, list) else None,
                "checked": [
                    "latest_success_sync_period",
                    "real_product_seed_exists",
                    "unbound_ad_group_pool_exists",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
