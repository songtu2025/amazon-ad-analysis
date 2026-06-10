import json
import os
import sys
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FRONTEND_URL = os.environ.get("SMOKE_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")

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


class RootDivParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_root = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div":
            return
        if dict(attrs).get("id") == "root":
            self.has_root = True


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def request_text(url: str) -> str:
    request = Request(url, headers={"Accept": "text/html,application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                fail(f"{url} 返回状态码 {status}")
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        fail(f"{url} 返回状态码 {exc.code}")
    except URLError as exc:
        fail(f"{url} 无法访问：{exc.reason}")


def request_json(path: str) -> Any:
    body = request_text(f"{API_BASE_URL}{path}")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{path} 返回内容不是 JSON：{exc}")


def try_json_from_url(url: str) -> Any | None:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                return None
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


def choose_api_base_url() -> str:
    configured = os.environ.get("SMOKE_API_BASE_URL")
    candidates = [configured.rstrip("/")] if configured else ["http://127.0.0.1:8000", "http://127.0.0.1:8001"]
    last_error = ""
    for candidate in candidates:
        health = try_json_from_url(f"{candidate}/health")
        dashboard_health = try_json_from_url(f"{candidate}/api/dashboard/health")
        if isinstance(health, dict) and health.get("status") == "ok" and isinstance(dashboard_health, dict):
            return candidate
        last_error = f"{candidate} 健康检查返回不符合预期"
    fail(last_error or "未找到可用 API 服务")


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if key in FORBIDDEN_ACTION_KEYS:
                hits.append(key_path)
            hits.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def assert_no_auto_execution_fields(payloads: dict[str, Any]) -> None:
    hits: list[str] = []
    for name, payload in payloads.items():
        hits.extend(f"{name}:{hit}" for hit in find_forbidden_keys(payload))
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))


def assert_frontend_entry() -> None:
    html = request_text(FRONTEND_URL)
    parser = RootDivParser()
    parser.feed(html)
    if not parser.has_root:
        fail(f"{FRONTEND_URL} 未发现 React root 入口")


def main() -> None:
    global API_BASE_URL
    API_BASE_URL = choose_api_base_url()
    health = request_json("/health")
    if health.get("status") != "ok":
        fail("/health 未返回 status=ok")

    payloads = {
        "anomalies": request_json("/api/anomalies"),
        "suggestions": request_json("/api/suggestions"),
        "decisions": request_json("/api/decisions"),
        "dashboard_health": request_json("/api/dashboard/health"),
    }
    assert_no_auto_execution_fields(payloads)
    assert_frontend_entry()

    print(
        json.dumps(
            {
                "status": "success",
                "api_base_url": API_BASE_URL,
                "frontend_url": FRONTEND_URL,
                "checked": [
                    "/health",
                    "/api/anomalies",
                    "/api/suggestions",
                    "/api/decisions",
                    "/api/dashboard/health",
                    "frontend_root",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
