import json
import sys
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "http://127.0.0.1:8001"
FORBIDDEN_MARKERS = ("DEMO", "SMOKE", "TASK")


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    try:
        with urlopen(Request(url, method="GET"), timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        fail(f"请求 {path} 失败：{exc}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{path} 返回不是 JSON：{exc}")


def marker_hits(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            hits.extend(marker_hits(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(marker_hits(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        upper = value.upper()
        for marker in FORBIDDEN_MARKERS:
            if marker in upper:
                hits.append(f"{path} contains {marker}: {value}")
                break
    return hits


def assert_no_demo_payload(label: str, payload: Any) -> None:
    hits = marker_hits(payload)
    if hits:
        fail(f"{label} 不应返回 DEMO/SMOKE/TASK 测试对象：" + "；".join(hits[:5]))


def main() -> None:
    anomalies = get_json("/api/anomalies")
    suggestions = get_json("/api/suggestions")
    dashboard = get_json("/api/dashboard/anomaly-summary", {"start_date": "2026-05-12", "end_date": "2026-06-10"})
    health = get_json("/api/dashboard/health", {"start_date": "2026-05-12", "end_date": "2026-06-10"})

    if not isinstance(anomalies, list):
        fail(f"/api/anomalies 返回格式异常：{anomalies}")
    if not isinstance(suggestions, list):
        fail(f"/api/suggestions 返回格式异常：{suggestions}")

    assert_no_demo_payload("/api/anomalies", anomalies)
    assert_no_demo_payload("/api/suggestions", suggestions)

    dashboard_count = int(dashboard.get("anomaly_count") or 0)
    health_overview = health.get("overview") if isinstance(health, dict) else None
    health_count = int((health_overview or {}).get("anomaly_count") or 0)
    if dashboard_count != len(anomalies):
        fail(f"驾驶舱异常统计应与真实异常列表一致：dashboard={dashboard_count} anomalies={len(anomalies)}")
    if health_count != len(anomalies):
        fail(f"驾驶舱健康概览异常统计应与真实异常列表一致：health={health_count} anomalies={len(anomalies)}")

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "anomalies_no_demo_objects",
                    "suggestions_no_demo_objects",
                    "dashboard_counts_exclude_demo",
                    "real_empty_state_allowed",
                ],
                "anomaly_count": len(anomalies),
                "suggestion_count": len(suggestions),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
