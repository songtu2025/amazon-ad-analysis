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
    fail("未找到可用于真实搜索词归类组可用性复核的成功同步周期")


def priority_reason(group: dict[str, Any]) -> tuple[int, str]:
    performance_status = str(group.get("performance_status") or "")
    cost = float(group.get("cost") or 0)
    terms = int(group.get("terms") or 0)
    if performance_status in {"high_acos", "costly_no_order"}:
        return 1, "先看高风险组"
    if performance_status == "high_conversion":
        return 2, "高转化机会"
    if performance_status == "data_insufficient" and (cost >= 50 or terms >= 50):
        return 3, "数据不足大池"
    return 4, "低优先级观察"


def main() -> None:
    period = latest_success_period()
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    payload = request_json(
        "/api/search-terms/analysis",
        {
            "market_id": period["market_id"],
            "start_date": period["period_start"],
            "end_date": period["period_end"],
            "min_clicks": 10,
            "min_spend": 10,
            "target_acos": 0.35,
            "limit": 100,
        },
    )
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})

    groups = payload.get("group_summary") if isinstance(payload, dict) else None
    if not isinstance(groups, list) or not groups:
        fail("真实搜索词分析缺少非空 group_summary")

    prioritized = [
        {
            "group_key": group.get("group_key"),
            "group_label": group.get("group_label"),
            "reason": priority_reason(group)[1],
            "rank": priority_reason(group)[0],
            "cost": group.get("cost"),
            "orders": group.get("orders"),
            "terms": group.get("terms"),
        }
        for group in groups
        if priority_reason(group)[0] <= 3
    ]
    prioritized.sort(key=lambda item: (item["rank"], -(float(item["cost"] or 0)), -(int(item["terms"] or 0))))

    if not prioritized:
        fail("当前真实 group_summary 无法计算优先复核组")
    reasons = {item["reason"] for item in prioritized}
    if "先看高风险组" not in reasons and "高转化机会" not in reasons and "数据不足大池" not in reasons:
        fail(f"优先复核理由异常：{reasons}")
    if len(bindings_before) != len(bindings_after):
        fail("归类组可用性复核不应改变产品归因规则数量")

    hits = find_forbidden_keys(payload)
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "group_count": len(groups),
                "priority_count": len(prioritized),
                "top_priority": prioritized[0],
                "active_binding_count": len(bindings_after),
                "checked": [
                    "real_group_summary",
                    "priority_review_groups",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
