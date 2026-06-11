import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "candidate_type": "export type SearchTermCandidate",
    "fetch_candidates": "fetchSearchTermCandidates",
    "candidate_endpoint": "/api/search-terms/candidates",
    "candidate_type_filter": "candidate_type",
    "suggested_manual_action": "suggested_manual_action",
}

REQUIRED_APP_MARKERS = {
    "candidate_import": "fetchSearchTermCandidates",
    "candidate_state": "searchTermCandidates",
    "candidate_loading": "searchTermCandidateLoading",
    "candidate_filter": "searchTermCandidateType",
    "candidate_loader": "loadSearchTermCandidates",
    "candidate_panel_title": "人工处理候选池",
    "candidate_filter_label": "候选类型",
    "candidate_columns": "searchTermCandidateColumns",
    "recommended_manual_decision": "recommended_manual_decision",
    "suggested_manual_action": "suggested_manual_action",
    "candidate_panel_class": "search-term-candidate-panel",
}

REQUIRED_STYLE_MARKERS = {
    "candidate_panel": ".search-term-candidate-panel",
    "candidate_summary": ".search-term-candidate-summary",
    "candidate_reason": ".search-term-candidate-reason",
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
        fail("api.ts 搜索词候选池标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 搜索词候选池标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词候选池标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "search_term_candidate_api_client",
                    "candidate_type_filter",
                    "candidate_pool_panel",
                    "candidate_table",
                    "manual_decision_fields",
                    "candidate_styles",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
