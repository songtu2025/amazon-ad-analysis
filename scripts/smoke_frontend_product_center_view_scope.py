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
    "view_type": "ProductCenterView",
    "view_options": "productCenterViewOptions",
    "view_state_default": 'useState<ProductCenterView>("ad_tuning")',
    "view_control_class": "product-center-view-controls",
    "view_control_label": "产品中心视图",
    "view_ad_tuning_copy": "广告调优对象",
    "view_sales_profile_copy": "销售档案",
    "view_all_copy": "全部产品",
    "view_filter_ad_tuning": 'productCenterView === "ad_tuning"',
    "view_filter_ad_tuning_status": 'adCoverageStatus !== "not_advertised"',
    "view_filter_sales_profile": 'productCenterView === "sales_profile"',
    "view_filter_sales_profile_status": 'adCoverageStatus === "not_advertised"',
    "reset_coverage_filter": 'setProductAdCoverageFilter("all")',
    "scoped_table_columns": "productCenterTableColumns",
    "hidden_sales_profile_columns": "productSalesProfileHiddenColumnTitles",
    "table_uses_scoped_columns": "columns={productCenterTableColumns}",
    "scoped_table_scroll": "productCenterTableScrollX",
}

REQUIRED_STYLE_MARKERS = {
    "view_controls_style": ".product-center-view-controls",
}

AD_RULE_COLUMN_TITLES = [
    "目标与数据表现是否匹配",
    "产品目标",
    "目标 ACOS",
    "目标 CVR",
    "最小点击",
    "最小花费",
    "最小订单",
    "最大 CPC",
    "库存阈值",
    "备注",
    "操作",
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
        fail("产品中心视图收敛标记缺失：" + ", ".join(missing_app))

    missing_hidden_columns = [
        title for title in AD_RULE_COLUMN_TITLES if f'"{title}"' not in app_source and f'title: "{title}"' not in app_source
    ]
    if missing_hidden_columns:
        fail("销售档案视图隐藏列清单缺失：" + ", ".join(missing_hidden_columns))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品中心视图控件样式缺失：" + ", ".join(missing_style))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_center_view_scope",
                    "ad_tuning_view_filters_out_sales_profiles",
                    "sales_profile_view_hides_ad_rule_columns",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
