import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "decision_type": "export type SearchTermCandidateDecision",
    "decision_input": "export type SearchTermCandidateDecisionInput",
    "create_candidate_decision": "createSearchTermCandidateDecision",
    "fetch_candidate_decisions": "fetchSearchTermCandidateDecisions",
    "candidate_decision_endpoint": "/api/search-terms/candidate-decisions",
}

REQUIRED_APP_MARKERS = {
    "decision_import": "createSearchTermCandidateDecision",
    "decision_fetch_import": "fetchSearchTermCandidateDecisions",
    "decision_state": "searchTermCandidateDecisions",
    "decision_modal_state": "searchTermDecisionCandidate",
    "decision_submit": "submitSearchTermCandidateDecision",
    "decision_button": "记录人工判断",
    "decision_panel_title": "候选处理记录",
    "decision_columns": "searchTermCandidateDecisionColumns",
}

REQUIRED_STYLE_MARKERS = {
    "decision_list": ".search-term-decision-list",
    "decision_meta": ".search-term-decision-meta",
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
        fail("api.ts 搜索词候选处理记录标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 搜索词候选处理记录标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词候选处理记录标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "candidate_decision_api_client",
                    "candidate_decision_modal",
                    "candidate_decision_button",
                    "candidate_decision_record_list",
                    "candidate_decision_styles",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
