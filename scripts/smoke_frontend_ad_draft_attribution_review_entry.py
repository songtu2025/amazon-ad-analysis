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
    "review_handler": "openAdDraftAttributionReview",
    "review_button_label": "去广告归因页核查 / 修正归因",
    "review_action_class": "ad-draft-attribution-review-action",
    "manual_review_copy": "先到广告归因页人工核查或修正归因",
    "no_auto_merge_copy": "不会自动合并产品、迁移归因或改广告",
    "uses_first_candidate": "selectedGoalRuleIdentityCandidates[0]?.id",
    "sets_candidate_product": "setAttributionProductId(candidateProductId ?? null)",
    "review_target_state": "adDraftAttributionReviewProduct",
    "sets_review_target": "setAdDraftAttributionReviewProduct(candidateProduct)",
    "review_banner_title": "从草稿产品身份核查进入",
    "review_banner_target": "当前候选销售表现产品",
    "review_banner_manual_copy": "只用于人工核查归因，不会自动保存归因规则",
    "closes_goal_drawer": "setSelectedGoalRuleProduct(null)",
    "opens_attribution_tab": 'setActiveTab("attribution")',
}

REQUIRED_STYLE_MARKERS = {
    "review_action_style": ".ad-draft-attribution-review-action",
    "review_banner_style": ".ad-draft-attribution-review-banner",
}

FORBIDDEN_BUTTON_LABELS = [
    "自动合并",
    "合并产品",
    "自动迁移",
    "执行广告动作",
    "调整竞价",
    "暂停广告",
    "开启广告",
    "否定关键词",
    "新增关键词",
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


def _assert_no_forbidden_buttons(app_source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", app_source)
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in FORBIDDEN_BUTTON_LABELS:
            if label in normalized:
                fail(f"发现不允许的按钮：{label}")


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("广告草稿产品归因核查入口缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("广告草稿产品归因核查入口样式缺失：" + ", ".join(missing_style))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_forbidden_buttons(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ad_draft_attribution_review_entry",
                    "closes_goal_drawer",
                    "opens_attribution_tab",
                    "passes_candidate_product_to_manual_review",
                    "no_auto_merge_or_ad_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
