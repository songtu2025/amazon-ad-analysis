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


def latest_success_market_id() -> int:
    runs = request_json("/api/sync/runs", {"limit": 20})
    if not isinstance(runs, list):
        fail("同步记录接口返回格式异常")
    for run in runs:
        if isinstance(run, dict) and run.get("status") == "success" and run.get("market_id") is not None:
            return int(run["market_id"])
    fail("未找到可用于真实组级复盘验收的成功同步记录")


def main() -> None:
    market_id = latest_success_market_id()
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": market_id})
    decisions = request_json("/api/search-terms/group-decisions", {"market_id": market_id})
    if not isinstance(decisions, list):
        fail("组级人工记录接口返回格式异常")

    if not decisions:
        bindings_after = request_json("/api/products/ad-bindings", {"market_id": market_id})
        if len(bindings_before) != len(bindings_after):
            fail("只读检查不应改变产品归因规则数量")
        print(
            json.dumps(
                {
                    "status": "success",
                    "result": "skipped_no_group_decisions",
                    "market_id": market_id,
                    "checked": [
                        "group_decision_list_readable",
                        "no_real_group_decision_to_review",
                        "read_only_binding_count_unchanged",
                    ],
                },
                ensure_ascii=False,
            )
        )
        return

    decision = decisions[0]
    decision_id = decision.get("id")
    if not isinstance(decision_id, int):
        fail(f"组级人工记录 ID 异常：{decision}")
    review = request_json(f"/api/search-terms/group-decisions/{decision_id}/review", {"review_period": "7d"})
    for key in ["before_metrics", "after_metrics", "delta_metrics", "result", "result_label", "manual_hint"]:
        if key not in review:
            fail(f"真实组级复盘缺少字段 {key}：{review}")
    hits = find_forbidden_keys({"decision": decision, "review": review})
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": market_id})
    if len(bindings_before) != len(bindings_after):
        fail("真实组级复盘只读接口不应改变产品归因规则数量")
    print(
        json.dumps(
            {
                "status": "success",
                "market_id": market_id,
                "decision_id": decision_id,
                "result": review.get("result"),
                "checked": [
                    "group_decision_review_readable",
                    "review_metrics_present",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
