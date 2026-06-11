import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "workflow_state": "realWorkflowRehearsalSteps",
    "workflow_title": "真实闭环演练",
    "step_attribution": "确认产品归因",
    "step_product_terms": "查看产品维度搜索词",
    "step_group_decision": "记录组级人工判断",
    "step_group_review": "复盘组级判断",
    "manual_boundary": "不会自动修改广告",
    "candidate_cta": "查看证据并确认归因",
    "evidence_flow": "openAttributionEvidence(firstAttributionCandidate.source, firstAttributionCandidate.candidate_product.product_id)",
    "product_terms_flow": "openProductSearchTermAnalysis(productAdBindings[0])",
    "search_terms_tab_flow": "setActiveTab(\"search_terms\")",
}

REQUIRED_STYLE_MARKERS = {
    "workflow_panel": ".real-workflow-rehearsal",
    "workflow_steps": ".real-workflow-rehearsal-steps",
    "workflow_step": ".real-workflow-rehearsal-step",
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
        fail("App.tsx 真实闭环演练标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 真实闭环演练标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "real_workflow_rehearsal_panel",
                    "four_manual_steps",
                    "first_step_evidence_cta",
                    "product_terms_and_search_term_navigation",
                    "manual_boundary_copy",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
