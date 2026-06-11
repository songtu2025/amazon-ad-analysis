import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

API_BASE_URL = "http://127.0.0.1:8001"
TASK_MARKER = "TASK-063 smoke"
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


def request_json(path: str, params: dict[str, object] | None = None, payload: dict[str, Any] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"

    url = f"{API_BASE_URL}{path}{query}"
    request = Request(url, data=data, headers=headers, method=method)
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


def require_list(payload: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        fail(f"{label} 返回格式异常：{payload}")
    rows = [item for item in payload if isinstance(item, dict)]
    if len(rows) != len(payload):
        fail(f"{label} 包含非对象记录：{payload}")
    return rows


def parse_json_field(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} 缺少 JSON 字符串")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        fail(f"{label} JSON 无法解析：{exc}")
    if not isinstance(parsed, dict):
        fail(f"{label} JSON 不是对象：{parsed}")
    return parsed


def pick_manual_decision(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    for decision in decisions:
        suggestion = decision.get("suggestion")
        if not isinstance(suggestion, dict):
            continue
        if isinstance(decision.get("id"), int) and isinstance(suggestion.get("anomaly_event_id"), int):
            return decision
    fail("真实库暂无可复盘的人工处理记录，需要先由运营在建议详情中人工确认")


def main() -> None:
    anomalies = require_list(request_json("/api/anomalies"), "异常列表")
    suggestions = require_list(request_json("/api/suggestions"), "AI 建议列表")
    decisions = require_list(request_json("/api/decisions"), "人工处理记录")

    if not anomalies:
        fail("真实库暂无异常事件")
    if not suggestions:
        fail("真实库暂无 AI 建议")
    if not decisions:
        fail("真实库暂无人工处理记录，需要先由运营人工确认建议")

    decision = pick_manual_decision(decisions)
    decision_id = int(decision["id"])
    suggestion_id = int(decision["suggestion_id"])
    suggestion_from_decision = decision["suggestion"]
    anomaly_id = int(suggestion_from_decision["anomaly_event_id"])
    evidence = parse_json_field(suggestion_from_decision.get("evidence_json"), "人工处理记录中的异常证据")

    matching_suggestion = next((item for item in suggestions if item.get("id") == suggestion_id), None)
    if matching_suggestion is None:
        fail(f"人工处理记录无法追溯到 AI 建议：suggestion_id={suggestion_id}")
    if matching_suggestion.get("anomaly_event_id") != anomaly_id:
        fail(f"AI 建议与人工处理记录的异常 ID 不一致：{matching_suggestion}")

    matching_anomaly = next((item for item in anomalies if item.get("id") == anomaly_id), None)
    if matching_anomaly is None:
        fail(f"人工处理记录无法追溯到异常事件：anomaly_id={anomaly_id}")
    if matching_anomaly.get("status") not in {"observing", "handled"}:
        fail(f"人工处理后异常状态异常：{matching_anomaly}")

    review_payload = {
        "review_period": "7d",
        "before_metrics_json": {
            "source": TASK_MARKER,
            "decision_id": decision_id,
            "suggestion_id": suggestion_id,
            "anomaly_event_id": anomaly_id,
            "anomaly_status": matching_anomaly.get("status"),
            "evidence": {
                "acos": evidence.get("acos"),
                "cost": evidence.get("cost"),
                "orders": evidence.get("orders"),
                "sales": evidence.get("sales"),
            },
        },
        "after_metrics_json": {
            "source": TASK_MARKER,
            "review_check": "manual_review_loop_verified",
            "ad_execution_changed": False,
        },
        "result": "unchanged",
        "note": f"{TASK_MARKER}：验证人工确认后的复盘记录闭环；不代表广告已自动修改。",
    }
    review = request_json(f"/api/reviews/{decision_id}", payload=review_payload)
    if review.get("manual_decision_id") != decision_id:
        fail(f"复盘记录 decision_id 异常：{review}")
    if review.get("review_period") != "7d" or review.get("result") != "unchanged":
        fail(f"复盘记录结果异常：{review}")
    if TASK_MARKER not in str(review.get("note") or ""):
        fail(f"复盘记录缺少任务标记：{review}")

    before_metrics = parse_json_field(review.get("before_metrics_json"), "处理前指标快照")
    after_metrics = parse_json_field(review.get("after_metrics_json"), "复盘后指标快照")
    if before_metrics.get("source") != TASK_MARKER or after_metrics.get("source") != TASK_MARKER:
        fail(f"复盘指标快照缺少来源标记：before={before_metrics} after={after_metrics}")
    if after_metrics.get("ad_execution_changed") is not False:
        fail(f"复盘记录不应暗示广告动作已执行：{after_metrics}")

    listed_reviews = require_list(request_json("/api/reviews", {"decision_id": decision_id}), "复盘记录列表")
    if not any(item.get("id") == review.get("id") for item in listed_reviews):
        fail(f"复盘记录列表未返回刚保存的记录：{listed_reviews}")

    checked_payloads = [anomalies, suggestions, decisions, review, listed_reviews]
    hits: list[str] = []
    for index, payload in enumerate(checked_payloads):
        hits.extend(find_forbidden_keys(payload, f"$payload[{index}]"))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))

    print(
        json.dumps(
            {
                "status": "success",
                "decision_id": decision_id,
                "suggestion_id": suggestion_id,
                "anomaly_event_id": anomaly_id,
                "review_id": review.get("id"),
                "review_period": review.get("review_period"),
                "result": review.get("result"),
                "checked": [
                    "real_anomaly_readable",
                    "real_suggestion_readable",
                    "manual_decision_traceable",
                    "review_created_or_updated",
                    "review_list_readable",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
