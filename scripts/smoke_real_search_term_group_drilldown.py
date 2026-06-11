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
    fail("未找到可用于真实搜索词组下钻验收的成功同步周期")


def main() -> None:
    period = latest_success_period()
    base_params = {
        "market_id": period["market_id"],
        "start_date": period["period_start"],
        "end_date": period["period_end"],
        "min_clicks": 10,
        "min_spend": 10,
        "target_acos": 0.35,
        "limit": 100,
    }
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    analysis = request_json("/api/search-terms/analysis", base_params)
    groups = analysis.get("group_summary") if isinstance(analysis, dict) else None
    if not isinstance(groups, list) or not groups:
        fail("真实搜索词分析缺少归类聚合组")
    group = groups[0]
    drilled = request_json(
        "/api/search-terms/analysis",
        {
            **base_params,
            "semantic_category": group["semantic_category"],
            "performance_status": group["performance_status"],
        },
    )
    rows = drilled.get("rows") if isinstance(drilled, dict) else None
    if not isinstance(rows, list) or not rows:
        fail(f"同组下钻结果为空：{group}")
    mismatched = [
        row
        for row in rows
        if row.get("semantic_category") != group["semantic_category"] or row.get("performance_status") != group["performance_status"]
    ]
    if mismatched:
        fail(f"同组下钻返回了不匹配搜索词：{mismatched[:3]}")
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    if len(bindings_before) != len(bindings_after):
        fail("同组下钻不应改变产品归因规则数量")
    hits = find_forbidden_keys({"analysis": analysis, "drilled": drilled})
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))
    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "group": {
                    "group_key": group.get("group_key"),
                    "group_label": group.get("group_label"),
                    "terms": group.get("terms"),
                },
                "drilldown_rows": len(rows),
                "active_binding_count": len(bindings_after),
                "checked": [
                    "real_group_exists",
                    "drilldown_filters_match_group",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
