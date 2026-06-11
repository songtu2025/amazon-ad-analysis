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
    "editable_guard": "isProductAdRuleEditable",
    "readonly_renderer": "renderNoSpCoverageAdRuleReadonly",
    "readonly_text": "只读销售档案",
    "no_ad_rule_copy": "本系统暂无 SP 覆盖证据，不配置广告目标 / 规则",
    "keep_goal_drawer": "openGoalRuleDrawer(record)",
    "manual_save": "saveProductSettings(record.id)",
}

REQUIRED_COLUMNS = [
    'title: "产品目标"',
    'title: "目标 ACOS"',
    'title: "目标 CVR"',
    'title: "最小点击"',
    'title: "最小花费"',
    'title: "最小订单"',
    'title: "最大 CPC"',
    'title: "库存阈值"',
    'title: "备注"',
]

REQUIRED_STYLE_MARKERS = {
    "readonly_style": ".product-ad-rule-readonly",
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
        fail("无 SP 覆盖产品只读规则标记缺失：" + ", ".join(missing_app))

    missing_columns = [marker for marker in REQUIRED_COLUMNS if marker not in app_source]
    if missing_columns:
        fail("产品目标 / 规则列缺失：" + ", ".join(missing_columns))

    readonly_call_count = app_source.count("renderNoSpCoverageAdRuleReadonly()")
    if readonly_call_count < len(REQUIRED_COLUMNS):
        fail(f"广告目标 / 规则列只读保护不足：{readonly_call_count} < {len(REQUIRED_COLUMNS)}")

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("无 SP 覆盖产品只读规则样式缺失：" + ", ".join(missing_style))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "no_sp_products_readonly_ad_rules",
                    "ad_rule_columns_guarded",
                    "eligible_products_keep_manual_editing",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
