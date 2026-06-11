import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "group_review_type": "export type SearchTermGroupDecisionReview",
    "fetch_group_review": "fetchSearchTermGroupDecisionReview",
    "group_review_endpoint": "/api/search-terms/group-decisions/${decisionId}/review",
    "delta_metrics": "delta_metrics",
}

REQUIRED_APP_MARKERS = {
    "group_review_state": "searchTermGroupDecisionReview",
    "group_review_loader": "loadSearchTermGroupDecisionReview",
    "group_review_button": "查看复盘",
    "group_review_title": "组级复盘",
    "group_review_manual_hint": "人工判断复盘",
    "before_metrics": "before_metrics",
    "after_metrics": "after_metrics",
    "delta_metrics": "delta_metrics",
}

REQUIRED_STYLE_MARKERS = {
    "group_review_panel": ".search-term-group-review-panel",
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
        fail("api.ts 组级复盘标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 组级复盘标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 组级复盘标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "group_decision_review_api_client",
                    "group_review_button",
                    "group_review_modal",
                    "before_after_delta_metrics",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
