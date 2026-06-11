import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "coverage_status_type": "ProductAdCoverageStatus",
    "coverage_status_helper": "getProductAdCoverageStatus",
    "ad_tuning_eligible_helper": "isProductAdTuningEligible",
    "coverage_summary": "productAdCoverageSummary",
    "coverage_summary_title": "产品广告覆盖状态",
    "sales_not_ads_copy": "销售表现产品不等于广告投放产品",
    "attributed_copy": "有广告覆盖",
    "sp_unattributed_copy": "有 SP 数据待归因",
    "not_advertised_copy": "本系统暂无 SP 覆盖证据",
    "not_in_tuning_todo_copy": "只作为销售产品档案，不进入广告调优待办",
    "no_attribution_needed_action": "无需归因",
    "sales_profile_only_action": "仅销售档案",
    "coverage_sort_priority": "adCoveragePriority",
}

REQUIRED_STYLE_MARKERS = {
    "coverage_summary_style": ".product-ad-coverage-summary",
    "coverage_cards_style": ".product-ad-coverage-cards",
    "coverage_card_style": ".product-ad-coverage-card",
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
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品广告覆盖状态标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品广告覆盖状态样式缺失：" + ", ".join(missing_style))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_ad_coverage_status",
                    "sales_product_not_equal_ad_product",
                    "not_advertised_products_out_of_tuning_todo",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
