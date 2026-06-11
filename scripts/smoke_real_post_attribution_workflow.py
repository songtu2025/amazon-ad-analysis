import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
        with urlopen(request, timeout=20) as response:
            text = response.read().decode("utf-8", errors="replace")
            if response.status < 200 or response.status >= 300:
                fail(f"{url} 返回状态码 {response.status}：{text}")
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
    fail("未找到可用于真实闭环验收的成功同步周期")


def main() -> None:
    period = latest_success_period()
    base_params = {
        "market_id": period["market_id"],
        "start_date": period["period_start"],
        "end_date": period["period_end"],
    }

    bindings = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    if not isinstance(bindings, list):
        fail("归因规则接口返回格式异常")
    active_bindings = [item for item in bindings if isinstance(item, dict) and item.get("status") == "active"]
    if not active_bindings:
        fail("真实库仍没有人工确认归因规则")

    first_binding = active_bindings[0]
    product_id = int(first_binding.get("product_id") or 0)
    if product_id <= 0:
        fail(f"归因规则缺少有效 product_id：{first_binding}")

    readiness = request_json("/api/search-terms/product-readiness", base_params)
    summary = readiness.get("summary")
    if not isinstance(summary, dict):
        fail(f"产品维度就绪汇总格式异常：{readiness}")
    if readiness.get("ready") is not True or readiness.get("status") != "ready":
        fail(f"人工归因后产品维度搜索词仍未就绪：{readiness}")
    if int(summary.get("active_binding_count") or 0) < 1:
        fail(f"人工归因规则数量异常：{summary}")
    if int(summary.get("bound_search_term_rows") or 0) <= 0:
        fail(f"人工归因后没有已归因搜索词行：{summary}")

    product_analysis = request_json(
        "/api/search-terms/analysis",
        {
            **base_params,
            "product_id": product_id,
        },
    )
    group_summary = product_analysis.get("group_summary")
    if not isinstance(group_summary, list) or not group_summary:
        fail(f"产品筛选下归类聚合组为空：{product_analysis}")

    group_decisions = request_json("/api/search-terms/group-decisions", base_params)
    if not isinstance(group_decisions, list):
        fail("组级人工记录接口返回格式异常")

    workflow = request_json("/api/search-terms/analysis", base_params)
    if not isinstance(workflow.get("group_summary"), list) or not workflow["group_summary"]:
        fail("全局归类聚合组不可读")

    checked_payloads = [bindings, readiness, product_analysis, group_decisions, workflow]
    hits: list[str] = []
    for index, payload in enumerate(checked_payloads):
        hits.extend(find_forbidden_keys(payload, f"$payload[{index}]"))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "workflow_status": "needs_group_decision" if not group_decisions else "has_group_decision",
                "period": period,
                "active_binding_count": len(active_bindings),
                "product_id": product_id,
                "bound_search_term_rows": int(summary.get("bound_search_term_rows") or 0),
                "product_group_count": len(group_summary),
                "group_decision_count": len(group_decisions),
                "top_product_group": group_summary[0],
                "checked": [
                    "latest_success_sync_period",
                    "real_manual_attribution_saved",
                    "product_search_term_readiness_ready",
                    "product_group_summary_readable",
                    "group_decisions_readable",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
