import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"

REQUIRED_MARKERS = {
    "source_snapshot_label": "广告对象证据快照",
    "selected_product_label": "当前将归因到的产品",
    "product_selection_handler": "setAttributionProductId(candidate.product_id)",
    "manual_save_button": "确认归因并保存证据快照",
    "manual_boundary": "不会自动修改广告",
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


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    missing = [name for name, marker in REQUIRED_MARKERS.items() if marker not in source]
    if missing:
        fail("产品归因证据弹窗文案标记缺失：" + ", ".join(missing))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    candidate_columns = re.search(
        r"const productAttributionCandidateColumns = useMemo[\s\S]*?\n\s*\],\n\s*\[(?P<deps>[^\]]*)\]\n\s*\);",
        source,
    )
    if not candidate_columns:
        fail("未找到高可信归因候选表列定义")
    candidate_deps = candidate_columns.group("deps")
    for marker in ["productStartDate", "productEndDate"]:
        if marker not in candidate_deps:
            fail(f"高可信归因候选查看证据闭包缺少周期依赖：{marker}")

    attribution_columns = re.search(
        r"const attributionColumns = useMemo[\s\S]*?\n\s*\],\n\s*\[(?P<deps>[^\]]*)\]\n\s*\);",
        source,
    )
    if not attribution_columns:
        fail("未找到未归因广告数据池表列定义")
    attribution_deps = attribution_columns.group("deps")
    for marker in ["productStartDate", "productEndDate", "attributionProductId"]:
        if marker not in attribution_deps:
            fail(f"未归因广告数据池查看证据闭包缺少依赖：{marker}")

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "source_snapshot_label",
                    "selected_product_label",
                    "manual_product_selection",
                    "manual_save_button",
                    "fresh_period_dependency",
                    "manual_boundary_copy",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
