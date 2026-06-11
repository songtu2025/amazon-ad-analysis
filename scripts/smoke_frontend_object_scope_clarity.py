import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_APP_MARKERS = {
    "product_object_copy": "当前对象：产品",
    "ad_source_object_copy": "当前对象：广告来源",
    "binding_rule_object_copy": "当前对象：归因规则",
    "product_scope_copy": "产品级组判断",
    "global_scope_copy": "全局组判断",
    "current_product_record_copy": "当前产品级记录",
    "decision_modal_scope_copy": "当前记录口径",
    "decision_list_scope_copy": "当前列表口径",
    "product_id_payload": "product_id: searchTermProductId ?? undefined",
    "product_mode_switch": "isProductSearchTermMode",
    "product_decision_count_source": "searchTermGroupDecisions.length",
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

    missing = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing:
        fail("App.tsx 对象口径标记缺失：" + ", ".join(missing))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_settings_object_scope",
                    "product_group_decision_scope_copy",
                    "global_group_decision_scope_copy",
                    "product_id_payload_kept",
                    "product_review_uses_filtered_group_decisions",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
