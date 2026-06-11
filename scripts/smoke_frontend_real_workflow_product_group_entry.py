import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_MARKERS = {
    "product_entry_helper": "openFirstBoundProductSearchTermAnalysis",
    "product_group_decision_label": "记录产品级组判断",
    "product_group_decision_status": "productWorkflowGroupDecisionCount > 0 ? \"已记录产品级\" : \"待记录产品级\"",
    "product_scope_status_guard": "isProductSearchTermMode ? searchTermGroupDecisions.length : 0",
    "group_decision_entry_uses_product": "onClick: openFirstBoundProductSearchTermAnalysis",
    "group_review_entry_uses_product": "actionLabel: \"查看产品级组记录\"",
    "product_analysis_call": "openProductSearchTermAnalysis(productAdBindings[0])",
}

FORBIDDEN_MARKERS = {
    "old_group_decision_tab_only": 'title: "记录组级人工判断"',
    "old_group_decision_global_count": 'status: searchTermGroupDecisions.length > 0 ? "已记录" : "待记录"',
    "old_group_decision_click": 'onClick: () => setActiveTab("search_terms")',
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
    source = APP_PATH.read_text(encoding="utf-8")

    missing = [name for name, marker in REQUIRED_MARKERS.items() if marker not in source]
    if missing:
        fail("App.tsx 真实闭环产品级入口标记缺失：" + ", ".join(missing))

    old_hits = [name for name, marker in FORBIDDEN_MARKERS.items() if marker in source]
    if old_hits:
        fail("真实闭环仍存在旧全局入口标记：" + ", ".join(old_hits))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "real_workflow_product_group_entry",
                    "product_scope_status_guard",
                    "product_analysis_entry",
                    "no_global_group_decision_shortcut",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
