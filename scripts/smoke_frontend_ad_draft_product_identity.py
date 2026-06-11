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
    "ad_draft_category_constant": 'AD_DRAFT_PRODUCT_CATEGORY = "SP广告来源草稿"',
    "ad_draft_detector": "isAdDraftProduct",
    "identity_review_detector": "needsAdDraftIdentityReview",
    "candidate_finder": "findAdDraftIdentityCandidates",
    "drawer_candidates_value": "selectedGoalRuleIdentityCandidates",
    "identity_review_alert_title": "产品身份待核查",
    "identity_review_copy": "当前对象来自 SP 广告来源草稿，不等同于完整销售表现商品",
    "manual_review_copy": "需要人工核查后再设置产品目标和规则",
    "candidate_section": "可能相关的销售表现产品",
    "candidate_readonly_copy": "候选只读展示，不会自动合并产品、迁移归因或改广告",
    "candidate_class": "ad-draft-identity-candidates",
    "candidate_asin_label": "候选 ASIN",
    "candidate_msku_label": "候选 MSKU",
    "candidate_sales_label": "销售额",
    "candidate_orders_label": "订单",
    "ad_draft_source_label": "广告草稿",
}

REQUIRED_STYLE_MARKERS = {
    "review_alert_style": ".ad-draft-identity-alert",
    "candidate_section_style": ".ad-draft-identity-candidates",
    "candidate_card_style": ".ad-draft-identity-candidate-card",
    "candidate_metric_style": ".ad-draft-candidate-metrics",
}

FORBIDDEN_BUTTON_LABELS = [
    "自动合并",
    "合并产品",
    "迁移归因",
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
        fail("广告草稿产品身份核查前端标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("广告草稿产品身份核查样式缺失：" + ", ".join(missing_style))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_forbidden_buttons(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ad_draft_identity_review_detector",
                    "readonly_sales_product_candidates",
                    "drawer_identity_review_alert",
                    "ad_draft_source_label",
                    "no_merge_or_ad_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
