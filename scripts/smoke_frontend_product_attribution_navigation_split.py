import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_MARKERS = {
    "product_center_tab": 'label: "产品中心"',
    "attribution_tab": 'label: "广告归因"',
    "attribution_active_title": '? "广告归因"',
    "attribution_active_description": "人工确认广告来源属于哪个产品",
    "search_terms_attribution_action": "前往广告归因确认归因",
    "attribution_tab_setter": 'setActiveTab("attribution")',
}

ATTRIBUTION_ONLY_MARKERS = [
    "真实闭环演练",
    "高可信归因候选",
    "未归因广告数据池",
    "已确认归因规则",
]

FORBIDDEN_PRODUCT_CENTER_MARKERS = [
    'title: "绑定广告活动"',
    'placeholder="广告活动 ID"',
    "前往产品设置确认归因",
    "产品目标与规则设置",
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

    missing = [name for name, marker in REQUIRED_MARKERS.items() if marker not in app_source]
    if missing:
        fail("前端产品/归因导航拆分标记缺失：" + ", ".join(missing))

    missing_attribution_markers = [marker for marker in ATTRIBUTION_ONLY_MARKERS if marker not in app_source]
    if missing_attribution_markers:
        fail("广告归因页签业务区缺失：" + ", ".join(missing_attribution_markers))

    forbidden_hits = [marker for marker in FORBIDDEN_PRODUCT_CENTER_MARKERS if marker in app_source]
    if forbidden_hits:
        fail("产品中心仍包含易混淆广告归因文案：" + ", ".join(forbidden_hits))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_center_tab",
                    "attribution_tab",
                    "attribution_workbench_moved",
                    "product_center_without_campaign_binding_input",
                    "search_terms_points_to_attribution",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
