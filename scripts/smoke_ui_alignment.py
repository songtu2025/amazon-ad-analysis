import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "ops_positioning": "SP 广告健康监控 / 人工决策辅助",
    "read_only_tag": "只读建议",
    "manual_confirm_tag": "人工确认后记录",
    "dashboard_focus_cards": "dashboardFocusCards",
    "manual_decision_focus": "待人工确认",
    "compact_sync_band": "compact-sync-band",
    "ops_tabs_class": 'className="ops-tabs"',
    "safety_icon": "SafetyCertificateOutlined",
    "check_icon": "CheckCircleOutlined",
}

REQUIRED_STYLE_MARKERS = {
    "toolbar_visual": ".toolbar-band",
    "ops_eyebrow": ".ops-eyebrow",
    "toolbar_actions": ".toolbar-actions",
    "ops_tabs": ".ops-tabs",
    "dashboard_focus_grid": ".dashboard-focus-grid",
    "focus_card": ".focus-card",
    "compact_sync_band": ".compact-sync-band",
    "metric_card_accent": ".metric-grid .ant-card::before",
    "table_header": ".ant-table-thead > tr > th",
    "drawer_title": ".ant-drawer-title",
    "suggestion_panel": ".suggestion-panel",
}

FORBIDDEN_AUTO_ACTION_MARKERS = [
    "auto_execute",
    "execution_payload",
    "executeAd",
    "pause_ad",
    "new_bid",
    "negative_keyword",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App UI 标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("CSS UI 标记缺失：" + ", ".join(missing_style))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source or marker in style_source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ops_positioning",
                    "toolbar_status_tags",
                    "dashboard_focus_cards",
                    "compact_sync_band",
                    "ops_tabs",
                    "metric_card_accent",
                    "table_header_style",
                    "drawer_title_style",
                    "suggestion_panel_style",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
