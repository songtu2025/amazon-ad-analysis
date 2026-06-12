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
    "neutral_identity_column_title": 'title: "产品 / 广告对象身份"',
    "ad_draft_center_detector": "needsAdDraftIdentityReview(record)",
    "ad_draft_center_copy": "广告对象待关联真实商品",
    "not_sales_profile_copy": "不是销售表现商品档案",
    "ad_draft_rule_scope_copy": "当前规则挂在广告草稿对象上",
    "rule_rebind_copy": "关联真实商品后再作为产品级规则使用",
    "ad_draft_center_class": "product-center-ad-draft-identity",
    "ad_draft_rule_scope_class": "ad-draft-rule-scope-warning",
}

REQUIRED_STYLE_MARKERS = {
    "ad_draft_identity_style": ".product-center-ad-draft-identity",
    "ad_draft_rule_scope_style": ".ad-draft-rule-scope-warning",
}

FORBIDDEN_APP_MARKERS = {
    "misleading_identity_column_title": 'title: "真实产品身份"',
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


def _assert_no_forbidden_buttons(app_source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", app_source)
    forbidden_labels = ["自动执行", "执行广告动作", "调整竞价", "改竞价", "暂停广告", "开启广告", "否定关键词", "新增关键词"]
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in forbidden_labels:
            if label in normalized:
                fail(f"发现自动执行广告按钮：{label}")


def _extract_column(app_source: str, start_marker: str, end_marker: str) -> str:
    start = app_source.find(start_marker)
    if start < 0:
        fail(f"缺少列标记：{start_marker}")
    end = app_source.find(end_marker, start)
    if end < 0:
        fail(f"列结束位置异常：{start_marker}")
    return app_source[start:end]


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    forbidden = [name for name, marker in FORBIDDEN_APP_MARKERS.items() if marker in app_source]
    if forbidden:
        fail("产品中心仍存在误导性对象口径：" + ", ".join(forbidden))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心广告草稿对象口径标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品中心广告草稿对象样式缺失：" + ", ".join(missing_style))

    identity_column = _extract_column(app_source, 'title: "产品 / 广告对象身份"', 'title: "店铺 / 数据来源"')
    if "needsAdDraftIdentityReview(record)" not in identity_column:
        fail("产品身份列没有单独处理广告来源草稿")
    if "广告对象待关联真实商品" not in identity_column or "不是销售表现商品档案" not in identity_column:
        fail("产品身份列没有说明广告草稿不是真实商品档案")

    target_match_column = _extract_column(app_source, 'title: "目标与数据表现是否匹配"', 'title: "产品目标"')
    if "当前规则挂在广告草稿对象上" not in target_match_column:
        fail("目标匹配列没有说明规则当前挂在广告草稿对象上")
    if "关联真实商品后再作为产品级规则使用" not in target_match_column:
        fail("目标匹配列没有说明需关联真实商品后再作为产品级规则使用")

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))
    _assert_no_forbidden_buttons(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ad_draft_not_shown_as_real_product_identity",
                    "product_center_draft_identity_copy",
                    "ad_draft_rule_scope_warning",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
