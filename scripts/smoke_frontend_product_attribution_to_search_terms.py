import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "link_function": "openProductSearchTermAnalysis",
    "set_product_filter": "setSearchTermProductId(record.product_id)",
    "set_market_filter": "setSearchTermMarketId(record.market_id ?? productMarketId)",
    "set_start_date": "setSearchTermStartDate(productStartDate)",
    "set_end_date": "setSearchTermEndDate(productEndDate)",
    "switch_tab": 'setActiveTab("search_terms")',
    "binding_button": "查看搜索词分析",
    "manual_chain_hint": "人工确认归因后，可查看该产品搜索词归类组",
}

REQUIRED_STYLE_MARKERS = {
    "binding_next_action": ".binding-search-term-action",
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
        fail("App.tsx 产品归因到搜索词分析联动标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 产品归因到搜索词分析联动样式缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "binding_search_term_analysis_entry",
                    "product_filter_handoff",
                    "market_and_period_handoff",
                    "switch_to_search_terms_tab",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
