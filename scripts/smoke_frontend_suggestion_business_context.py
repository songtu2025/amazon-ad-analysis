import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
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
    styles_source = _read(STYLES_CSS)

    _assert_contains(app_source, "产品经营背景", "business_context_title")
    _assert_contains(app_source, "product_sales_snapshot", "sales_snapshot_source")
    _assert_contains(app_source, "suggestionBusinessSnapshot", "snapshot_from_suggestion_trace")
    _assert_contains(app_source, "selectedBusinessSnapshot", "snapshot_fallback_from_evidence")
    _assert_regex(
        app_source,
        r"selectedSuggestion\?\.source_trace_json[\s\S]*product_sales_snapshot",
        "source_trace_snapshot_lookup",
    )
    _assert_regex(
        app_source,
        r"selectedEvidence[\s\S]*product_sales_snapshot",
        "evidence_snapshot_fallback",
    )

    for label in ["销售额", "订单", "Sessions", "净利", "广告花费", "广告销售", "产品 ACOS", "快照周期"]:
        _assert_contains(app_source, label, f"business_context_metric_{label}")

    _assert_contains(app_source, "business-context-panel", "business_context_panel_class")
    _assert_contains(styles_source, ".business-context-panel", "business_context_panel_style")
    _assert_contains(styles_source, ".business-context-grid", "business_context_grid_style")
    _assert_contains(app_source, "parseJsonText(selectedSuggestion.source_trace_json)", "source_trace_json_kept")
    _assert_contains(app_source, "parseJsonText(selected.evidence_json)", "evidence_json_kept")
    _assert_no_auto_execution_buttons(app_source)
    _run_frontend_build()

    print(
        {
            "status": "success",
            "checks": [
                "business_context_title",
                "source_trace_snapshot",
                "evidence_snapshot_fallback",
                "business_context_metrics",
                "raw_json_kept",
                "no_auto_execution_buttons",
                "frontend_build",
            ],
        }
    )


if __name__ == "__main__":
    main()
