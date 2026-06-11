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
    "selected_product_state": "selectedGoalRuleProduct",
    "open_drawer_handler": "openGoalRuleDrawer",
    "drawer_class": "product-goal-rule-drawer",
    "drawer_title": "产品目标 / 规则设置",
    "table_entry": "设置目标 / 规则",
    "manual_boundary_title": "人工设置边界",
    "manual_boundary_copy": "只保存运营人工设置的产品目标和规则门槛",
    "no_auto_copy": "不会自动生成目标，也不会自动修改广告",
    "identity_block": "goal-rule-product-identity",
    "sp_metric_block": "goal-rule-metric-grid",
    "goal_field": "产品目标",
    "target_acos_field": "目标 ACOS",
    "target_cvr_field": "目标 CVR",
    "min_clicks_field": "最小点击",
    "min_spend_field": "最小花费",
    "min_orders_field": "最小订单",
    "max_cpc_field": "最大 CPC",
    "inventory_guard_field": "库存阈值",
    "note_field": "目标备注",
    "manual_save_button": "人工保存设置",
    "existing_save_function": "saveProductSettings(selectedGoalRuleProduct.id)",
}

REQUIRED_STYLE_MARKERS = {
    "drawer_style": ".product-goal-rule-drawer",
    "identity_style": ".goal-rule-product-identity",
    "metric_grid_style": ".goal-rule-metric-grid",
}

FORBIDDEN_BUTTON_LABELS = [
    "自动执行",
    "执行广告动作",
    "调整竞价",
    "改竞价",
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
    "自动执行广告",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def _assert_no_auto_execution_button(app_source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", app_source)
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in FORBIDDEN_BUTTON_LABELS:
            if label in normalized:
                fail(f"发现自动执行广告按钮：{label}")


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品目标 / 规则编辑抽屉缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品目标 / 规则编辑抽屉样式缺失：" + ", ".join(missing_style))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_goal_rule_drawer_entry",
                    "manual_boundary",
                    "product_identity_and_sp_metrics",
                    "goal_rule_fields",
                    "manual_save_uses_existing_function",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
