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
    "needs_setup_helper": "productsNeedingGoalRuleSetup",
    "has_sp_metric_guard": "hasProductSpMetrics",
    "needs_setup_guard": "needsProductGoalRuleSetup",
    "priority_order": "productCenterProducts",
    "priority_order_sort": "setupPriority",
    "priority_order_datasource": "dataSource={productCenterProducts}",
    "guidance_panel": "product-goal-rule-guidance",
    "guidance_title": "待设置目标 / 规则",
    "manual_copy": "需要运营人工设置产品目标和规则门槛",
    "no_auto_setup_copy": "系统不会自动生成目标或修改广告",
    "row_status": "目标 / 规则待设置",
    "manual_save_button": "保存设置",
}

REQUIRED_STYLE_MARKERS = {
    "guidance_style": ".product-goal-rule-guidance",
    "guidance_grid_style": ".goal-rule-guidance-grid",
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
    "自动设置目标",
    "自动生成目标",
    "自动修改广告",
    "自动执行广告",
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
        fail("产品目标 / 规则设置引导缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品目标 / 规则设置引导样式缺失：" + ", ".join(missing_style))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    allowed_manual_boundary_hits = {"自动生成目标", "自动修改广告"}
    real_hits = [marker for marker in auto_hits if marker not in allowed_manual_boundary_hits]
    if real_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(real_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_goal_rule_guidance",
                    "sp_metric_setup_guard",
                    "row_goal_rule_status",
                    "manual_save_boundary",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
