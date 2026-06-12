import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_MARKERS = {
    "ad_draft_rebind_action": "关联真实商品",
    "ad_draft_rebind_handler": "openAdDraftRealProductRebind",
    "uses_existing_evidence_flow": "openAttributionEvidence(source, candidateProductId)",
    "uses_existing_binding_flow": "confirmAdSourceAttribution",
    "local_attribution_only_copy": "只更新本地归因关系和证据快照，不会修改广告",
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

    missing = [name for name, marker in REQUIRED_MARKERS.items() if marker not in app_source]
    if missing:
        fail("广告草稿关联真实商品动作缺失：" + ", ".join(missing))

    product_identity_column_start = app_source.find('title: "产品 / 广告对象身份"')
    product_identity_column_end = app_source.find('title: "店铺 / 数据来源"', product_identity_column_start)
    if product_identity_column_start < 0 or product_identity_column_end < 0:
        fail("产品身份列定位失败")
    product_identity_column = app_source[product_identity_column_start:product_identity_column_end]
    if "needsAdDraftIdentityReview(record)" not in product_identity_column:
        fail("产品身份列没有识别广告草稿对象")
    if "关联真实商品" not in product_identity_column:
        fail("广告草稿对象主行缺少关联真实商品入口")

    handler_start = app_source.find("openAdDraftRealProductRebind")
    handler_end = app_source.find("const saveProductSettings", handler_start)
    if handler_start < 0 or handler_end < 0:
        fail("广告草稿关联真实商品处理函数定位失败")
    handler_block = app_source[handler_start:handler_end]
    required_handler_markers = [
        "productAdBindings.find",
        "binding.product_id === adDraftProduct.id",
        "scope_type",
        "scope_id",
        "openAttributionEvidence(source, candidateProductId)",
    ]
    missing_handler = [marker for marker in required_handler_markers if marker not in handler_block]
    if missing_handler:
        fail("处理函数没有复用已归因广告来源进入证据流程：" + ", ".join(missing_handler))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))
    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ad_draft_rebind_action_visible",
                    "existing_evidence_flow_reused",
                    "manual_confirmation_boundary_copy",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
