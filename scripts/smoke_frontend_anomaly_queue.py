import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_TS = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLES_CSS = PROJECT_ROOT / "frontend" / "src" / "styles.css"


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


def _run_frontend_build() -> None:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise SystemExit("status=failed check=frontend_build reason=npm_not_found")
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=PROJECT_ROOT / "frontend",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "status=failed check=frontend_build "
            f"returncode={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
        )


def main() -> None:
    app_source = _read(APP_TSX)
    api_source = _read(API_TS)
    styles_source = _read(STYLES_CSS)

    _assert_contains(app_source, 'key: "anomalies"', "anomaly_tab_key")
    _assert_contains(app_source, 'label: "异常与 AI 建议队列"', "anomaly_tab_label")
    _assert_regex(app_source, r"<Table[\s\S]*dataSource=\{displayedAnomalies\}", "anomaly_table")

    _assert_contains(app_source, 'placeholder="异常类型"', "filter_anomaly_type")
    _assert_contains(app_source, 'placeholder="状态"', "filter_status")
    _assert_contains(app_source, 'placeholder="建议等级"', "filter_suggestion_level")
    _assert_contains(app_source, 'placeholder="产品目标"', "filter_goal_type")

    _assert_contains(app_source, 'title: "风险等级"', "severity_column")
    _assert_contains(app_source, 'title: "产品目标"', "product_goal_column")
    _assert_contains(app_source, 'title: "状态"', "status_column")
    _assert_contains(app_source, 'aria-label="进入详情页"', "detail_entry")
    _assert_contains(app_source, "<Drawer", "detail_drawer")

    _assert_contains(api_source, "export async function fetchAnomalies", "fetch_anomalies")
    _assert_contains(api_source, 'params.set("anomaly_type"', "api_anomaly_type_filter")
    _assert_contains(api_source, 'params.set("status"', "api_status_filter")
    _assert_contains(api_source, 'params.set("suggestion_level"', "api_suggestion_level_filter")
    _assert_contains(api_source, 'params.set("goal_type"', "api_goal_type_filter")

    _assert_contains(styles_source, ".filter", "filter_style")
    _assert_contains(styles_source, ".object-meta", "object_meta_style")
    _assert_contains(styles_source, ".detail-metric-grid", "detail_metric_style")
    _assert_no_auto_execution_buttons(app_source)
    _run_frontend_build()

    print(
        {
            "status": "success",
            "checks": [
                "anomaly_queue_tab",
                "anomaly_table",
                "filters",
                "detail_drawer",
                "api_filters",
                "no_auto_execution_buttons",
                "frontend_build",
            ],
        }
    )


if __name__ == "__main__":
    main()
