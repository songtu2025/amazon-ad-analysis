import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_MARKERS = {
    "todo_state": "productGroupDecisionTodo",
    "todo_copy": "待记录产品级组判断",
    "todo_button": "记录产品级组判断",
    "product_mode_guard": "isProductSearchTermMode &&",
    "group_summary_guard": "searchTermAnalysis?.group_summary.length",
    "no_current_product_decision_guard": "searchTermGroupDecisions.length === 0",
    "open_modal_only": "openSearchTermGroupDecisionModal(searchTermAnalysis.group_summary[0])",
    "product_id_payload_kept": "product_id: searchTermProductId ?? undefined",
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
        fail("App.tsx 产品级组判断待办入口标记缺失：" + ", ".join(missing))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_group_decision_todo",
                    "product_scope_guard",
                    "manual_modal_only",
                    "product_id_payload_kept",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
