import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, expected: str, label: str) -> None:
    if expected not in source:
        raise SystemExit(f"status=failed check={label} missing={expected}")


def _assert_regex(source: str, pattern: str, label: str) -> None:
    if not re.search(pattern, source, re.S):
        raise SystemExit(f"status=failed check={label} pattern={pattern}")


def _assert_no_auto_execution_buttons(source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", source)
    forbidden_labels = [
        "自动执行",
        "执行广告动作",
        "调整竞价",
        "改竞价",
        "暂停广告",
        "开启广告",
        "否定关键词",
        "新增关键词",
    ]
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in forbidden_labels:
            if label in normalized:
                raise SystemExit(f"status=failed check=no_auto_execution_button label={label}")


def main() -> None:
    app_source = _read(APP_TSX)

    _assert_contains(app_source, "type DashboardWorkflowFilters", "dashboard_filter_type")
    _assert_contains(app_source, "const resolveDashboardFilters = async (): Promise<DashboardWorkflowFilters>", "resolve_dashboard_filters")
    _assert_regex(
        app_source,
        r"const usesDefaultPeriod = dashboardStartDate === defaultPeriod\.start && dashboardEndDate === defaultPeriod\.end",
        "default_period_guard",
    )
    _assert_regex(app_source, r"const runs = await fetchSyncRuns\(20\)", "fetch_recent_sync_runs")
    _assert_regex(
        app_source,
        r"run\.status === \"success\" && run\.period_start && run\.period_end[\s\S]*dashboardMarketId",
        "latest_success_market_scope",
    )
    _assert_contains(app_source, "setDashboardStartDate(latest.period_start)", "update_dashboard_start")
    _assert_contains(app_source, "setDashboardEndDate(latest.period_end)", "update_dashboard_end")
    _assert_contains(app_source, "setDashboardMarketId(latest.market_id)", "update_dashboard_market")
    _assert_regex(
        app_source,
        r"const filters = await resolveDashboardFilters\(\);[\s\S]*fetchDashboardHealth\(filters\)[\s\S]*fetchDashboardTrends\(filters\)[\s\S]*fetchDashboardAnomalySummary\(filters\)",
        "dashboard_uses_resolved_filters",
    )
    _assert_no_auto_execution_buttons(app_source)

    print(
        {
            "status": "success",
            "checks": [
                "dashboard_latest_sync_period_resolver",
                "default_period_guard",
                "dashboard_period_state_updates",
                "dashboard_uses_resolved_filters",
                "no_auto_execution_buttons",
            ],
        }
    )


if __name__ == "__main__":
    main()
