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


def assert_no_auto_execution_fields(payload: Any) -> None:
    hits = find_forbidden_keys(payload)
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
    fail("未找到可用于真实归因候选工作台验收的成功同步周期")


def active_binding_count(payload: Any) -> int:
    if not isinstance(payload, list):
        fail(f"归因规则接口返回格式异常：{payload}")
    return len(payload)


def assert_top_candidate(top: dict[str, Any]) -> None:
    if top.get("priority_rank") != 1:
        fail(f"真实 Top 候选 priority_rank 应为 1：{top}")
    if "建议优先确认" not in str(top.get("priority_label") or ""):
        fail(f"真实 Top 候选缺少建议优先确认标签：{top.get('priority_label')}")
    impact = top.get("unlock_impact")
    if not isinstance(impact, dict):
        fail(f"真实 Top 候选缺少 unlock_impact：{top}")
    for key in ["search_term_rows", "cost", "sales", "orders", "acos"]:
        if key not in impact:
            fail(f"真实 Top 候选 unlock_impact 缺少 {key}：{impact}")
    if int(impact.get("search_term_rows") or 0) <= 0:
        fail(f"真实 Top 候选确认后可解锁搜索词行数异常：{impact}")


def main() -> None:
    period = latest_success_period()
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    payload = request_json(
        "/api/products/attribution-candidates",
        {
            "market_id": period["market_id"],
            "scope_type": "ad_group",
            "start_date": period["period_start"],
            "end_date": period["period_end"],
            "min_confidence": 50,
            "limit": 20,
        },
    )
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})

    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        fail("归因候选接口返回 rows 格式异常")
    if not rows:
        fail("真实库没有高可信产品归因候选")
    top = rows[0]
    assert_top_candidate(top)
    before_count = active_binding_count(bindings_before)
    after_count = active_binding_count(bindings_after)
    if before_count != after_count:
        fail(f"只读工作台不应改变归因规则数量：before={before_count}, after={after_count}")

    assert_no_auto_execution_fields(payload)
    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "candidate_count": len(rows),
                "top_candidate": {
                    "scope_name": top.get("source", {}).get("scope_name"),
                    "product_name": top.get("candidate_product", {}).get("product_name"),
                    "confidence_score": top.get("confidence_score"),
                    "priority_rank": top.get("priority_rank"),
                    "priority_label": top.get("priority_label"),
                    "unlock_impact": top.get("unlock_impact"),
                },
                "active_binding_count": after_count,
                "checked": [
                    "real_priority_rank",
                    "real_priority_label",
                    "real_unlock_impact",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
