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
    "missing_items_helper": "getProductGoalRuleMissingItems",
    "missing_goal_copy": "缺少产品目标",
    "missing_target_acos_copy": "缺少目标 ACOS",
    "real_gate_title": "需要人工设置产品目标 / 规则",
    "ad_tuning_view_guard": 'productCenterView !== "ad_tuning"',
    "current_table_scope": "productCenterProducts.filter",
    "ad_tuning_eligible_guard": "isProductAdTuningEligible(product, productBindingCount)",
    "needs_setup_with_binding": "needsProductGoalRuleSetup(product, productBindingCount)",
    "sp_metrics_copy": "当前 SP 指标",
    "guidance_metrics_class": "goal-rule-guidance-metrics",
    "missing_items_class": "goal-rule-guidance-missing",
    "drawer_entry": "openGoalRuleDrawer(product)",
    "manual_boundary_copy": "只引导运营人工设置",
    "no_auto_save_copy": "不会自动保存目标 / 规则",
    "no_auto_ads_copy": "不会自动修改广告",
}

REQUIRED_STYLE_MARKERS = {
    "guidance_style": ".product-goal-rule-guidance",
    "missing_items_style": ".goal-rule-guidance-missing",
    "metrics_style": ".goal-rule-guidance-metrics",
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


def _extract_setup_helper(app_source: str) -> str:
    marker = "const needsProductGoalRuleSetup"
    start = app_source.find(marker)
    if start < 0:
        fail("缺少 needsProductGoalRuleSetup")
    return app_source[start : start + 600]


def _extract_guidance_scope(app_source: str) -> str:
    marker = "const productsNeedingGoalRuleSetup = useMemo"
    start = app_source.find(marker)
    if start < 0:
        fail("缺少 productsNeedingGoalRuleSetup")
    end = app_source.find("const selectedGoalRuleProductDraft", start)
    if end < 0:
        fail("productsNeedingGoalRuleSetup 位置异常")
    return app_source[start:end]


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("真实目标 / 规则缺口引导缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("真实目标 / 规则缺口引导样式缺失：" + ", ".join(missing_style))

    setup_helper = _extract_setup_helper(app_source)
    if "hasProductSpMetrics(product)" not in setup_helper:
        fail("needsProductGoalRuleSetup 缺少 SP 指标门槛")
    if "isProductAdTuningEligible(product, productBindingCount)" not in setup_helper:
        fail("needsProductGoalRuleSetup 缺少广告调优资格门槛")
    if "getProductGoalRuleMissingItems(product).length > 0" not in setup_helper:
        fail("needsProductGoalRuleSetup 未复用缺失项判断")

    guidance_scope = _extract_guidance_scope(app_source)
    if 'productCenterView !== "ad_tuning"' not in guidance_scope:
        fail("引导未限定在广告调优对象视图")
    if "productCenterProducts.filter" not in guidance_scope:
        fail("引导未基于当前产品中心表格范围")
    if "needsProductGoalRuleSetup(product, productBindingCount)" not in guidance_scope:
        fail("引导未带归因数量调用缺口判断")

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "real_goal_rule_gate_guidance",
                    "ad_tuning_view_scope",
                    "ad_tuning_eligible_guard",
                    "missing_goal_rule_items",
                    "existing_drawer_entry",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
