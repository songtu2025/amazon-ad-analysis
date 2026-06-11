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
    fail("未找到可用于真实产品维度搜索词联动验收的成功同步周期")


def main() -> None:
    period = latest_success_period()
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    readiness = request_json(
        "/api/search-terms/product-readiness",
        {
            "market_id": period["market_id"],
            "start_date": period["period_start"],
            "end_date": period["period_end"],
        },
    )
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": period["market_id"]})
    if len(bindings_before) != len(bindings_after):
        fail("真实只读验收不应改变产品归因规则数量")

    summary = readiness.get("summary") if isinstance(readiness, dict) else None
    if not isinstance(summary, dict):
        fail(f"产品维度就绪返回缺少 summary：{readiness}")
    for key in ["active_binding_count", "bound_search_term_rows", "product_count", "products_with_search_terms"]:
        if key not in summary:
            fail(f"产品维度就绪 summary 缺少 {key}：{summary}")
    if int(summary.get("active_binding_count") or 0) <= 0 and readiness.get("ready") is not False:
        fail(f"无归因规则时不能判定产品维度搜索词 ready：{readiness}")

    hits = find_forbidden_keys({"readiness": readiness})
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "ready": readiness.get("ready"),
                "summary": summary,
                "active_binding_count": len(bindings_after),
                "checked": [
                    "real_readiness_read_only",
                    "binding_count_unchanged",
                    "readiness_summary_fields",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
