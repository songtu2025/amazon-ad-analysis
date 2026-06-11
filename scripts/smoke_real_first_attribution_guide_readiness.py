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
    fail("未找到可用于首条真实归因引导验收的成功同步周期")


def active_binding_count(payload: Any) -> int:
    if not isinstance(payload, list):
        fail(f"归因规则接口返回格式异常：{payload}")
    return len(payload)


def assert_top_candidate(top: dict[str, Any]) -> None:
    source = top.get("source")
    product = top.get("candidate_product")
    impact = top.get("unlock_impact")
    if not isinstance(source, dict) or not source.get("scope_id"):
        fail(f"首条候选缺少广告来源：{top}")
    if not isinstance(product, dict) or not product.get("product_id"):
        fail(f"首条候选缺少推荐产品：{top}")
    if not isinstance(impact, dict):
        fail(f"首条候选缺少确认后影响：{top}")
    for key in ["search_term_rows", "cost", "sales", "orders", "acos"]:
        if key not in impact:
            fail(f"首条候选确认后影响缺少 {key}：{impact}")
    if int(impact.get("search_term_rows") or 0) <= 0:
        fail(f"首条候选不能解锁搜索词：{impact}")
    if int(top.get("confidence_score") or 0) < 50:
        fail(f"首条候选可信度低于引导门槛：{top.get('confidence_score')}")


def main() -> None:
    period = latest_success_period()
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    before_count = active_binding_count(bindings_before)
    if before_count != 0:
        fail(f"首条真实归因引导只用于暂无归因规则的状态，当前 active_binding_count={before_count}")

    candidates = request_json(
        "/api/products/attribution-candidates",
        {
            "market_id": period["market_id"],
            "scope_type": "ad_group",
            "start_date": period["period_start"],
            "end_date": period["period_end"],
            "min_confidence": 50,
            "limit": 5,
        },
    )
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    after_count = active_binding_count(bindings_after)
    if before_count != after_count:
        fail(f"真实只读引导验收不应改变归因规则数量：before={before_count}, after={after_count}")

    rows = candidates.get("rows") if isinstance(candidates, dict) else None
    if not isinstance(rows, list) or not rows:
        fail("真实库暂无可用于首条归因引导的高可信候选")
    top = rows[0]
    assert_top_candidate(top)

    hits = find_forbidden_keys({"candidates": candidates})
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "active_binding_count": after_count,
                "candidate_count": len(rows),
                "top_candidate": {
                    "scope_name": top.get("source", {}).get("scope_name"),
                    "product_name": top.get("candidate_product", {}).get("product_name"),
                    "confidence_score": top.get("confidence_score"),
                    "unlock_impact": top.get("unlock_impact"),
                },
                "checked": [
                    "no_real_binding_yet",
                    "first_candidate_ready",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
