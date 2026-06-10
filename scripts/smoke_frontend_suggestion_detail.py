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
    styles_source = _read(STYLES_CSS)

    _assert_contains(app_source, 'aria-label="进入详情页"', "detail_entry_button")
    _assert_contains(app_source, "setSelected(record)", "select_anomaly")
    _assert_contains(app_source, "<Drawer", "detail_drawer")
    _assert_contains(app_source, "建议详情与溯源", "detail_title")
    _assert_contains(app_source, "fetchSuggestions({ anomaly_event_id: selected.id })", "load_suggestion")

    for label in [
        "AI 建议",
        "建议等级",
        "AI 解释",
        "风险提示 / 风险说明",
        "证据摘要",
        "命中规则 / 规则判定结果",
        "规则判定原始结果",
        "证据快照原始数据",
        "人工处理按钮 / 人工处理动作",
    ]:
        _assert_contains(app_source, label, f"detail_label_{label}")

    for label in ["采纳建议", "修改后采纳", "拒绝并记录原因", "加入观察", "标记已人工处理"]:
        _assert_contains(app_source, label, f"manual_decision_{label}")

    _assert_regex(app_source, r"selectedSuggestion\?\.source_trace_json[\s\S]*<pre>", "source_trace_json_pre")
    _assert_contains(app_source, "parseJsonText(selected.rule_result_json)", "rule_result_json")
    _assert_contains(app_source, "parseJsonText(selected.evidence_json)", "evidence_json")
    _assert_contains(app_source, "detail-metric-grid", "metric_snapshot")

    _assert_contains(api_source, "export async function fetchSuggestions", "fetch_suggestions_api")
    _assert_contains(api_source, "export async function createDecision", "create_decision_api")
    _assert_contains(styles_source, ".suggestion-panel", "suggestion_panel_style")
    _assert_contains(styles_source, ".decision-actions", "decision_actions_style")

    _assert_no_auto_execution_buttons(app_source)
    _run_frontend_build()

    print(
        {
            "status": "success",
            "checks": [
                "detail_entry",
                "detail_drawer",
                "ai_suggestion",
                "source_trace",
                "rule_evidence",
                "manual_decision_entry",
                "no_auto_execution_buttons",
                "frontend_build",
            ],
        }
    )


if __name__ == "__main__":
    main()
