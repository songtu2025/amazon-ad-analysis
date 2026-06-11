import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_MARKERS = {
    "product_binding_lookup": "const productBinding = productAdBindings.find((binding) => binding.product_id === record.id);",
    "binding_count_kept": "const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;",
    "search_term_button": "查看搜索词",
    "product_analysis_call": "openProductSearchTermAnalysis(productBinding)",
    "product_mode_target": 'setActiveTab("search_terms")',
}

FORBIDDEN_MARKERS = [
    'title: "绑定广告活动"',
    'placeholder="广告活动 ID"',
]

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

    missing = [name for name, marker in REQUIRED_MARKERS.items() if marker not in app_source]
    if missing:
        fail("产品中心搜索词入口标记缺失：" + ", ".join(missing))

    forbidden_hits = [marker for marker in FORBIDDEN_MARKERS if marker in app_source]
    if forbidden_hits:
        fail("产品中心仍包含广告活动绑定输入：" + ", ".join(forbidden_hits))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_center_search_term_entry",
                    "uses_existing_product_binding",
                    "opens_product_search_term_analysis",
                    "no_campaign_binding_input",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
