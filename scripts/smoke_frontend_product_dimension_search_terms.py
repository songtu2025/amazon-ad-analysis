import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "product_mode_flag": "const isProductSearchTermMode = Boolean(searchTermProductId);",
    "selected_product_context": "selectedSearchTermProduct",
    "readiness_product_context": "selectedReadinessProduct",
    "context_panel": "product-search-term-context",
    "context_title": "产品维度搜索词归类聚合",
    "group_title": "产品维度归类聚合组",
    "attribution_basis": "基于人工确认归因后的产品筛选",
    "not_ready_action": "前往广告归因确认归因",
    "go_attribution_tab": "setActiveTab(\"attribution\")",
}

REQUIRED_STYLE_MARKERS = {
    "context_panel": ".product-search-term-context",
    "context_header": ".product-search-term-context-header",
    "context_metrics": ".product-search-term-context-metrics",
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
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 产品维度搜索词标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 产品维度搜索词标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_dimension_mode",
                    "selected_product_context",
                    "readiness_product_context",
                    "product_dimension_group_title",
                    "manual_attribution_basis",
                    "not_ready_attribution_tab_cta",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
