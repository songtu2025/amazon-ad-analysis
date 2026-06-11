import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "identity_column_title": 'title: "真实产品身份"',
    "identity_cell_class": 'className="product-identity-cell"',
    "identity_name_class": 'className="product-identity-name"',
    "identity_meta_class": 'className="product-identity-meta"',
    "asin_label": "ASIN",
    "msku_label": "MSKU",
    "category_label": "类目",
    "market_source_copy": "销售表现",
    "market_formatter": "formatProductMarketLabel",
    "attribution_status_column": 'title: "归因状态"',
    "manage_attribution_button": "管理归因",
}

REQUIRED_STYLE_MARKERS = {
    "identity_cell_style": ".product-identity-cell",
    "identity_name_style": ".product-identity-name",
    "identity_meta_style": ".product-identity-meta",
    "identity_tag_style": ".product-identity-tag",
}

FORBIDDEN_APP_MARKERS = [
    'title: "ASIN / MSKU / 产品名称"',
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
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心真实身份字段缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品中心真实身份样式缺失：" + ", ".join(missing_style))

    forbidden_hits = [marker for marker in FORBIDDEN_APP_MARKERS if marker in app_source]
    if forbidden_hits:
        fail("产品中心仍包含旧口径或广告绑定输入：" + ", ".join(forbidden_hits))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_identity_column",
                    "asin_msku_category_visible",
                    "market_sales_performance_source_visible",
                    "attribution_entry_preserved",
                    "no_campaign_binding_input",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
