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

    _assert_contains(app_source, 'type AnomalyStatusFilter = AnomalyStatus | "all";', "status_filter_type")
    _assert_contains(app_source, "const anomalyStatusFilterOptions", "status_filter_options")
    _assert_contains(app_source, '{ value: "all", label: "全部状态" }', "all_status_option")
    _assert_contains(app_source, "function anomalyStatusParam", "status_param_helper")
    _assert_regex(app_source, r"useState<AnomalyStatusFilter>\(\"all\"\)", "default_all_status")
    _assert_regex(app_source, r"fetchAnomalies\(\{[\s\S]*status:\s*anomalyStatusParam\(status\)", "fetch_without_all_status")
    _assert_regex(app_source, r"generateSuggestions\(\{[\s\S]*status:\s*anomalyStatusParam\(status\)", "generate_without_all_status")
    _assert_regex(
        app_source,
        r"const openAnomalyQueueFromDashboard = \(\) => \{[\s\S]*setStatus\(\"all\"\)[\s\S]*setActiveTab\(\"anomalies\"\)",
        "dashboard_entry_sets_all_status",
    )
    _assert_regex(app_source, r"placeholder=\"状态\"[\s\S]*options=\{anomalyStatusFilterOptions\}", "status_select_uses_all_option")
    _assert_no_auto_execution_buttons(app_source)

    print(
        {
            "status": "success",
            "checks": [
                "status_filter_has_all",
                "default_all_status",
                "dashboard_entry_all_status",
                "api_status_param_not_all",
                "no_auto_execution_buttons",
            ],
        }
    )


if __name__ == "__main__":
    main()
