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
    "granularity_hint_function": "getAdObjectGranularityHint",
    "family_candidate_function": "findProductFamilyCandidates",
    "family_identity_copy": "疑似商品族广告对象",
    "family_path_copy": "先选择 / 创建商品族",
    "sku_drill_down_copy": "再细分到具体 SKU",
    "family_candidate_count_copy": "同系列候选",
    "top_sales_share_copy": "Top 销售占比",
    "search_term_specificity_copy": "搜索词未命中明确 ASIN / MSKU / SKU",
    "existing_rebind_action": "关联真实商品",
    "local_attribution_boundary": "只更新本地归因关系和证据快照，不会修改广告",
}

REQUIRED_STYLE_MARKERS = {
    "family_hint_style": ".product-family-ad-object-hint",
    "family_evidence_style": ".product-family-evidence-list",
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


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心商品族广告对象路径缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品中心商品族广告对象样式缺失：" + ", ".join(missing_style))

    identity_column_start = app_source.find('title: "产品 / 广告对象身份"')
    identity_column_end = app_source.find('title: "店铺 / 数据来源"', identity_column_start)
    if identity_column_start < 0 or identity_column_end < 0:
        fail("产品身份列定位失败")
    identity_column = app_source[identity_column_start:identity_column_end]
    for marker in ["疑似商品族广告对象", "同系列候选", "Top 销售占比", "先选择 / 创建商品族", "再细分到具体 SKU"]:
        if marker not in identity_column:
            fail(f"产品身份列缺少商品族归属提示：{marker}")

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))
    _assert_no_forbidden_buttons(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_family_ad_object_hint",
                    "family_evidence_visible",
                    "manual_family_then_sku_path",
                    "existing_rebind_boundary_preserved",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
