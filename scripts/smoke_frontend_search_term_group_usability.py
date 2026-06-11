import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "priority_items": "groupPriorityReviewItems",
    "priority_title": "归类组优先复核顺序",
    "source_group_summary": "searchTermAnalysis.group_summary",
    "risk_reason": "先看高风险组",
    "opportunity_reason": "高转化机会",
    "low_signal_reason": "数据不足大池",
    "drilldown_entry": "drillDownSearchTermGroup(item.group)",
    "decision_entry": "openSearchTermGroupDecisionModal(item.group)",
}

REQUIRED_STYLE_MARKERS = {
    "priority_panel": ".search-term-priority-review",
    "priority_grid": ".search-term-priority-review-list",
    "priority_item": ".search-term-priority-review-card",
    "priority_terms": ".search-term-priority-review-terms",
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
        fail("App.tsx 搜索词归类组可用性标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 搜索词归类组可用性标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "group_priority_review_items",
                    "priority_review_panel",
                    "manual_drilldown_and_decision_entries",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
