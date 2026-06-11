import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_APP_MARKERS = {
    "coverage_filter_visibility_flag": "shouldShowProductAdCoverageFilter",
    "coverage_filter_only_all_view": 'productCenterView === "all"',
    "coverage_filter_conditional_render": "{shouldShowProductAdCoverageFilter ? (",
    "coverage_filter_control_kept": "product-ad-coverage-controls",
    "coverage_filter_label_kept": "广告覆盖状态",
    "coverage_filter_reset_on_view_change": 'setProductAdCoverageFilter("all")',
    "coverage_summary_kept": "product-ad-coverage-summary",
    "coverage_cards_kept": "product-ad-coverage-cards",
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


def _assert_no_auto_execution_button(app_source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", app_source)
    forbidden_labels = ["自动执行", "执行广告动作", "调整竞价", "改竞价", "暂停广告", "开启广告", "否定关键词", "新增关键词"]
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in forbidden_labels:
            if label in normalized:
                fail(f"发现自动执行广告按钮：{label}")


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心筛选减负标记缺失：" + ", ".join(missing_app))

    if app_source.count("product-ad-coverage-controls") != 1:
        fail("广告覆盖状态筛选控件应只有一个渲染入口")

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_center_filter_reduction",
                    "coverage_filter_only_visible_in_all_products_view",
                    "coverage_summary_still_visible",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
