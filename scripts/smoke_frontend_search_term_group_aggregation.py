import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "group_type": "export type SearchTermGroupSummary",
    "group_summary_field": "group_summary: SearchTermGroupSummary[]",
    "representative_terms": "representative_terms",
}

REQUIRED_APP_MARKERS = {
    "latest_sync_period_fallback": "resolveSearchTermFilters",
    "latest_sync_runs_lookup": "fetchSyncRuns(20)",
    "search_period_sync": "setSearchTermStartDate(latest.period_start)",
    "group_title": "归类聚合组",
    "group_source": "语义分类 + 表现分类",
    "group_grid": "search-term-group-grid",
    "group_data": "searchTermAnalysis.group_summary",
    "representative_terms": "group.representative_terms",
    "representative_label": "代表搜索词",
    "manual_hint": "仅供人工判断",
}

REQUIRED_STYLE_MARKERS = {
    "group_grid_style": ".search-term-group-grid",
    "group_card_style": ".search-term-group-card",
    "group_terms_style": ".search-term-group-terms",
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
        fail("api.ts 搜索词归类聚合组标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 搜索词归类聚合组标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词归类聚合组标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "group_summary_type",
                    "group_summary_section",
                    "representative_terms",
                    "group_styles",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
