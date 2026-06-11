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
    fail("未找到可用于真实闭环演练验收的成功同步周期")


def workflow_status(*, binding_count: int, candidate_count: int, group_decision_count: int) -> str:
    if binding_count <= 0:
        return "needs_manual_attribution" if candidate_count > 0 else "needs_product_candidate"
    if group_decision_count <= 0:
        return "needs_group_decision"
    return "ready_for_review"


def main() -> None:
    period = latest_success_period()
    market_id = period["market_id"]
    bindings_before = request_json("/api/products/ad-bindings", {"market_id": market_id})
    candidates = request_json(
        "/api/products/attribution-candidates",
        {
            "market_id": market_id,
            "scope_type": "ad_group",
            "start_date": period["period_start"],
            "end_date": period["period_end"],
            "min_confidence": 50,
            "limit": 20,
        },
    )
    analysis = request_json(
        "/api/search-terms/analysis",
        {
            "market_id": market_id,
            "start_date": period["period_start"],
            "end_date": period["period_end"],
            "min_clicks": 10,
            "min_spend": 10,
            "target_acos": 0.35,
            "limit": 100,
        },
    )
    group_decisions = request_json("/api/search-terms/group-decisions", {"market_id": market_id})
    bindings_after = request_json("/api/products/ad-bindings", {"market_id": market_id})

    candidate_rows = candidates.get("rows") if isinstance(candidates, dict) else None
    group_summary = analysis.get("group_summary") if isinstance(analysis, dict) else None
    if not isinstance(candidate_rows, list):
        fail("归因候选接口返回 rows 格式异常")
    if not isinstance(group_summary, list) or not group_summary:
        fail("搜索词归类组为空，无法演练组级判断")
    if not isinstance(group_decisions, list):
        fail("组级人工记录接口返回格式异常")
    if len(bindings_before) != len(bindings_after):
        fail("真实闭环演练只读验收前后归因规则数量变化")

    hits = find_forbidden_keys(
        {
            "candidates": candidates,
            "analysis": analysis,
            "group_decisions": group_decisions,
        }
    )
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    status = workflow_status(
        binding_count=len(bindings_after),
        candidate_count=len(candidate_rows),
        group_decision_count=len(group_decisions),
    )
    print(
        json.dumps(
            {
                "status": "success",
                "workflow_status": status,
                "period": period,
                "active_binding_count": len(bindings_after),
                "candidate_count": len(candidate_rows),
                "group_count": len(group_summary),
                "group_decision_count": len(group_decisions),
                "top_candidate": candidate_rows[0] if candidate_rows else None,
                "top_group": group_summary[0],
                "checked": [
                    "latest_success_sync_period",
                    "real_attribution_candidates_readable",
                    "real_group_summary_readable",
                    "real_group_decisions_readable",
                    "read_only_binding_count_unchanged",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
