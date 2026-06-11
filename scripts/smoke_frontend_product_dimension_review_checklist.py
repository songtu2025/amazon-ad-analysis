import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "review_checklist_state": "productReviewChecklist",
    "review_title": "产品维度复核清单",
    "confirmed_binding": "已确认归因规则",
    "bound_terms": "已归因搜索词",
    "product_groups": "产品维度归类组",
    "group_decisions": "组级人工记录",
    "pending_attribution": "待人工确认归因",
    "readiness_source": "searchTermProductReadiness",
    "group_summary_source": "searchTermAnalysis?.group_summary.length",
    "group_decision_source": "searchTermGroupDecisions.length",
    "products_tab_cta": "setActiveTab(\"products\")",
}

REQUIRED_STYLE_MARKERS = {
    "review_panel": ".product-review-checklist",
    "review_header": ".product-review-checklist-header",
    "review_grid": ".product-review-checklist-grid",
    "review_item": ".product-review-checklist-item",
    "ready_state": ".product-review-checklist-item.is-ready",
    "pending_state": ".product-review-checklist-item.is-pending",
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
        fail("App.tsx 产品维度复核清单标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 产品维度复核清单标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_review_checklist",
                    "four_readonly_review_points",
                    "manual_attribution_pending_state",
                    "readiness_and_group_sources",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
