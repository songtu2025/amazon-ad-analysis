import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "readiness_type": "export type SearchTermProductReadiness",
    "readiness_fetcher": "fetchSearchTermProductReadiness",
    "readiness_endpoint": "/api/search-terms/product-readiness",
    "product_filter_param": "product_id",
}

REQUIRED_APP_MARKERS = {
    "readiness_import": "fetchSearchTermProductReadiness",
    "readiness_state": "searchTermProductReadiness",
    "readiness_loader": "loadSearchTermProductReadiness",
    "product_filter_state": "searchTermProductId",
    "product_filter_label": "产品筛选",
    "not_ready_title": "产品维度分析未就绪",
    "manual_hint": "请先在广告归因页人工确认产品归因规则",
    "product_param_pass_through": "product_id: searchTermProductId ?? undefined",
}

REQUIRED_STYLE_MARKERS = {
    "readiness_panel": ".search-term-product-readiness",
}

FORBIDDEN_AUTO_ACTION_MARKERS = [
    "auto_execute",
    "execution_payload",
    "executeAd",
    "pause_ad",
    "enable_ad",
    "new_bid",
    "negative_keyword",
    "create_keyword",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    api_source = API_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_api = [name for name, marker in REQUIRED_API_MARKERS.items() if marker not in api_source]
    if missing_api:
        fail("api.ts 产品维度就绪标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 产品维度就绪标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 产品维度就绪标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_readiness_api_client",
                    "product_filter_state",
                    "product_filter_pass_through",
                    "product_readiness_panel",
                    "manual_attribution_hint",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
