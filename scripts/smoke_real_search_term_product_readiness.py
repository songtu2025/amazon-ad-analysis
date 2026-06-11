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
    fail("未找到可用于产品维度搜索词就绪检查的成功同步周期")


def main() -> None:
    period = latest_success_period()
    payload = request_json(
        "/api/search-terms/product-readiness",
        {
            "market_id": period["market_id"],
            "start_date": period["period_start"],
            "end_date": period["period_end"],
        },
    )
    if payload.get("status") not in {"ready", "needs_attribution"}:
        fail(f"就绪状态枚举异常：{payload}")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        fail(f"就绪汇总格式异常：{payload}")
    for key in ["active_binding_count", "bound_search_term_rows", "product_count", "products_with_search_terms"]:
        if key not in summary:
            fail(f"就绪汇总缺少 {key}：{summary}")
    if int(summary.get("active_binding_count") or 0) <= 0 and payload.get("ready") is not False:
        fail(f"没有人工归因规则时不应判定就绪：{payload}")
    if payload.get("ready") is False and "产品设置页" not in str(payload.get("manual_hint") or ""):
        fail(f"未就绪时缺少产品设置页提示：{payload}")
    hits = find_forbidden_keys(payload)
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "period": period,
                "ready": payload.get("ready"),
                "readiness_status": payload.get("status"),
                "summary": summary,
                "checked": [
                    "latest_success_sync_period",
                    "real_product_search_term_readiness",
                    "manual_attribution_hint_when_needed",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
