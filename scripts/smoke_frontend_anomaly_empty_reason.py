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
    "empty_state_helper": "renderAnomalyQueueEmptyState",
    "configured_products_helper": "configuredNoAnomalyProducts",
    "global_empty_guard": "anomalies.length === 0",
    "filter_empty_guard": "displayedAnomalies.length === 0",
    "configured_state_reuse": "isConfiguredNoAnomalyTargetMatch(product)",
    "healthy_empty_copy": "当前已配置对象均未越线",
    "not_system_failure_copy": "不是系统无数据或异常生成失败",
    "filter_empty_copy": "当前筛选条件下暂无异常",
    "product_center_entry": "setActiveTab(\"products\")",
    "product_center_view_entry": "setProductCenterView(\"ad_tuning\")",
    "empty_class": "anomaly-empty-reason",
    "table_empty_locale": "locale={{ emptyText: renderAnomalyQueueEmptyState() }}",
}

REQUIRED_STYLE_MARKERS = {
    "empty_style": ".anomaly-empty-reason",
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


def _extract_empty_helper(app_source: str) -> str:
    marker = "const renderAnomalyQueueEmptyState"
    start = app_source.find(marker)
    if start < 0:
        fail("缺少 renderAnomalyQueueEmptyState")
    end = app_source.find("const columns", start)
    if end < 0:
        fail("renderAnomalyQueueEmptyState 位置异常")
    return app_source[start:end]


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("异常队列空态原因解释缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("异常队列空态原因解释样式缺失：" + ", ".join(missing_style))

    empty_helper = _extract_empty_helper(app_source)
    if empty_helper.find("displayedAnomalies.length === 0") > empty_helper.find("anomalies.length === 0"):
        fail("筛选空态判断应优先于全局健康空态，避免误判")
    if "configuredNoAnomalyProducts.length > 0" not in empty_helper:
        fail("全局健康空态缺少已配置未越线产品数量门槛")

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_auto_execution_button(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "anomaly_empty_reason",
                    "configured_no_anomaly_products",
                    "filter_empty_not_global_health",
                    "product_center_entry",
                    "no_auto_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
