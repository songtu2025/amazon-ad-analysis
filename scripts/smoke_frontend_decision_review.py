import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_TS = PROJECT_ROOT / "frontend" / "src" / "api.ts"


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
        "自动改竞价",
        "自动暂停",
        "自动开启",
        "自动否定",
        "自动新增",
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

    _assert_contains(app_source, 'key: "decisions"', "decisions_tab_key")
    _assert_contains(app_source, 'label: "处理记录与复盘"', "decisions_tab_label")
    _assert_regex(app_source, r"<Table[\s\S]*columns=\{decisionColumns\}[\s\S]*dataSource=\{decisions\}", "decisions_table")

    for label in ["处理类型", "处理人", "异常类型", "建议等级"]:
        _assert_contains(app_source, f'placeholder="{label}"', f"filter_{label}")

    for label in ["人工处理结果", "原建议", "处理人", "修改内容", "拒绝原因", "复盘状态", "复盘指标变化"]:
        _assert_contains(app_source, f'title: "{label}"', f"decision_column_{label}")

    _assert_contains(app_source, "fetchDecisions", "fetch_decisions_usage")
    _assert_contains(app_source, "createReview", "create_review_usage")
    _assert_contains(app_source, "reviewDecision", "review_modal_state")
    _assert_contains(app_source, "保存复盘", "save_review_button")
    _assert_contains(app_source, "复盘处理记录", "review_modal_title")
    _assert_contains(app_source, "复盘周期", "review_period_field")
    _assert_contains(app_source, "7 天复盘", "review_period_7d")
    _assert_contains(app_source, "14 天复盘", "review_period_14d")
    _assert_contains(app_source, "处理前指标快照", "before_metrics")
    _assert_contains(app_source, "复盘后指标快照", "after_metrics")

    _assert_contains(api_source, "export async function fetchDecisions", "fetch_decisions_api")
    _assert_contains(api_source, "export async function createReview", "create_review_api")
    _assert_contains(api_source, 'params.set("decision_type"', "api_decision_type_filter")
    _assert_contains(api_source, 'params.set("operator_name"', "api_operator_filter")
    _assert_contains(api_source, 'params.set("anomaly_type"', "api_anomaly_type_filter")
    _assert_contains(api_source, 'params.set("suggestion_level"', "api_suggestion_level_filter")

    _assert_no_auto_execution_buttons(app_source)
    _run_frontend_build()

    print(
        {
            "status": "success",
            "checks": [
                "decision_review_tab",
                "decision_table",
                "filters",
                "review_entry",
                "review_periods",
                "review_metrics",
                "no_auto_execution_buttons",
                "frontend_build",
            ],
        }
    )


if __name__ == "__main__":
    main()
