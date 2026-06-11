import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "group_decision_type": "export type SearchTermGroupDecision",
    "group_decision_input": "export type SearchTermGroupDecisionInput",
    "create_group_decision": "createSearchTermGroupDecision",
    "fetch_group_decisions": "fetchSearchTermGroupDecisions",
    "group_decision_endpoint": "/api/search-terms/group-decisions",
}

REQUIRED_APP_MARKERS = {
    "group_decision_state": "searchTermGroupDecisions",
    "group_decision_loader": "loadSearchTermGroupDecisions",
    "group_decision_modal": "searchTermGroupDecisionGroup",
    "group_decision_submit": "submitSearchTermGroupDecision",
    "group_drilldown": "drillDownSearchTermGroup",
    "semantic_filter_set": "setSearchTermSemanticCategory(group.semantic_category)",
    "performance_filter_set": "setSearchTermPerformanceStatus(group.performance_status)",
    "refresh_after_drilldown": "refreshSearchTermWorkflow()",
    "view_group_detail_button": "查看同组明细",
    "record_group_button": "记录组判断",
    "group_record_title": "组级人工记录",
    "manual_only_copy": "不代表广告已自动修改",
}

REQUIRED_STYLE_MARKERS = {
    "group_action_style": ".search-term-group-actions",
    "group_decision_list_style": ".search-term-group-decision-list",
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
        fail("api.ts 搜索词组级记录标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 搜索词组级记录标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词组级记录标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "group_decision_api_client",
                    "group_drilldown_action",
                    "group_decision_modal",
                    "group_decision_list",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
