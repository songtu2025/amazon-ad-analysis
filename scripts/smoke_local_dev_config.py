import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / "scripts" / "start_local_dev.ps1"
EXPECTED_API_BASE = "http://127.0.0.1:8001"
FRONTEND_URL = "http://127.0.0.1:5173"
FORBIDDEN_FILES = [
    ROOT / ".env",
    ROOT / ".env.example",
    ROOT / "frontend" / ".env.local",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def request_text(url: str) -> str:
    request = Request(url, headers={"Accept": "text/plain,text/html,application/json"})
    try:
        with urlopen(request, timeout=8) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                fail(f"{url} returned status {status}")
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        fail(f"{url} returned status {exc.code}")
    except URLError as exc:
        fail(f"{url} is not reachable: {exc.reason}")


def assert_script_config() -> None:
    if not START_SCRIPT.exists():
        fail("scripts/start_local_dev.ps1 does not exist")
    content = START_SCRIPT.read_text(encoding="utf-8")
    required_snippets = [
        "$BackendPort = 8001",
        "$FrontendPort = 5173",
        "VITE_API_BASE_URL",
        '$ApiBaseUrl = "http://127.0.0.1:$BackendPort"',
        "/api/products/unbound-ad-sources",
        "Backend port is running an old API",
        "npm run dev",
        "python -m uvicorn app.main:app",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in content]
    if missing:
        fail("start_local_dev.ps1 is missing required config: " + ", ".join(missing))


def assert_runtime_api_base() -> None:
    module = request_text(f"{FRONTEND_URL}/src/api.ts")
    expected = f'"VITE_API_BASE_URL": "{EXPECTED_API_BASE}"'
    if expected not in module:
        fail(f"frontend runtime is not using {EXPECTED_API_BASE}")


def assert_forbidden_files_unchanged_scope() -> None:
    missing = [str(path.relative_to(ROOT)) for path in FORBIDDEN_FILES if not path.exists()]
    if missing:
        fail("required local config file is missing: " + ", ".join(missing))


def main() -> None:
    assert_script_config()
    assert_forbidden_files_unchanged_scope()
    assert_runtime_api_base()
    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "start_local_dev.ps1",
                    "runtime_api_base",
                    "forbidden_config_files_exist",
                ],
                "frontend_url": FRONTEND_URL,
                "api_base_url": EXPECTED_API_BASE,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
