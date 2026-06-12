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
    "configured_state_helper": "isConfiguredNoAnomalyTargetMatch",
    "matched_status_guard": 'product.target_match.status === "matched"',
    "goal_guard": "!!product.goal",
    "rule_guard": "!!product.rules",
    "target_acos_guard": 'typeof product.rules.target_acos === "number"',
    "sp_metrics_guard": "hasProductSpMetrics(product)",
    "configured_copy": "目标已配置",
    "no_anomaly_copy": "当前未触发异常",
    "acos_below_target_copy": "未高于目标 ACOS",
    "configured_state_class": "target-match-ready-state",
}

REQUIRED_STYLE_MARKERS = {
    "configured_state_style": ".target-match-ready-state",
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


def _extract_target_match_column(app_source: str) -> str:
    marker = 'title: "目标与数据表现是否匹配"'
    start = app_source.find(marker)
    if start < 0:
        fail("缺少目标与数据表现是否匹配列")
    end = app_source.find('title: "产品目标"', start)
    if end < 0:
        fail("目标匹配列结束位置异常")
    return app_source[start:end]


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心已配置未触发异常状态缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("产品中心已配置未触发异常状态样式缺失：" + ", ".join(missing_style))

    target_match_column = _extract_target_match_column(app_source)
    setup_guard_pos = target_match_column.find("needsProductGoalRuleSetup(record, productBindingCount)")
    configured_state_pos = target_match_column.find("isConfiguredNoAnomalyTargetMatch(record)")
    if setup_guard_pos < 0:
        fail("目标匹配列缺少目标 / 规则待设置优先判断")
    if configured_state_pos < 0:
        fail("目标匹配列缺少已配置未触发异常判断")
    if setup_guard_pos > configured_state_pos:
        fail("已配置未触发异常判断不能抢在缺目标 / 规则引导之前")

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "configured_no_anomaly_state",
                    "matched_status_guard",
                    "goal_rule_sp_metrics_guards",
                    "goal_rule_setup_priority",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
