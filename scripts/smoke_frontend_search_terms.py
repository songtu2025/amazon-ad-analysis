import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "search_term_type": "export type SearchTermAnalysis",
    "search_term_row_type": "export type SearchTermAnalysisRow",
    "fetch_search_term_analysis": "fetchSearchTermAnalysis",
    "analysis_endpoint": "/api/search-terms/analysis",
    "semantic_filter": "semantic_category",
    "performance_filter": "performance_status",
    "min_clicks_filter": "min_clicks",
    "min_spend_filter": "min_spend",
}

REQUIRED_APP_MARKERS = {
    "tab_label": "搜索词分析",
    "active_title": "用户搜索词归类聚合",
    "api_import": "fetchSearchTermAnalysis",
    "analysis_state": "searchTermAnalysis",
    "load_function": "loadSearchTermAnalysis",
    "semantic_filter_state": "searchTermSemanticCategory",
    "performance_filter_state": "searchTermPerformanceStatus",
    "min_clicks_state": "searchTermMinClicks",
    "min_spend_state": "searchTermMinSpend",
    "summary_grid": "search-term-summary-grid",
    "category_grid": "search-term-category-grid",
    "detail_table_columns": "searchTermColumns",
    "source_evidence": "Campaign / Ad Group / 关键词",
    "manual_only_hint": "仅供人工判断",
}

REQUIRED_STYLE_MARKERS = {
    "summary_grid_style": ".search-term-summary-grid",
    "category_grid_style": ".search-term-category-grid",
    "category_card_style": ".search-term-category-card",
    "row_meta_style": ".search-term-row-meta",
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
        fail("api.ts 搜索词分析标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 搜索词分析标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词分析标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "search_term_analysis_tab",
                    "search_term_analysis_api_client",
                    "semantic_and_performance_filters",
                    "threshold_filters",
                    "summary_cards",
                    "category_summaries",
                    "detail_table_with_source_evidence",
                    "manual_only_hint",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
