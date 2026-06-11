import json
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_SCRIPT = PROJECT_ROOT / "scripts" / "smoke_current_mvp_baseline.py"

REQUIRED_GAPS = [
    "产品级组判断",
    "人工处理记录",
    "复盘记录",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def run_baseline() -> dict:
    result = subprocess.run(
        [sys.executable, str(BASELINE_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        fail(f"smoke_current_mvp_baseline.py 执行失败：{result.stdout}{result.stderr}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"smoke_current_mvp_baseline.py 输出不是 JSON：{exc}")
    if not isinstance(payload, dict):
        fail("smoke_current_mvp_baseline.py 输出格式异常")
    return payload


def main() -> None:
    payload = run_baseline()
    current_workflow = payload.get("current_workflow")
    if not isinstance(current_workflow, dict):
        fail("基线输出缺少 current_workflow")

    if current_workflow.get("workflow_status") != "needs_group_decision":
        fail(f"workflow_status 不符合当前真实缺口：{current_workflow}")

    if int(current_workflow.get("product_group_count") or 0) <= 0:
        fail(f"product_group_count 未体现产品维度归类组：{current_workflow}")

    product_group_decision_count = current_workflow.get("product_group_decision_count")
    if product_group_decision_count is None or int(product_group_decision_count) != 0:
        fail(f"product_group_decision_count 未保留当前真实事实：{current_workflow}")

    gaps = payload.get("baseline_gaps")
    if not isinstance(gaps, list):
        fail("baseline_gaps 格式异常")
    missing_gaps = [gap for gap in REQUIRED_GAPS if not any(gap in str(item) for item in gaps)]
    if missing_gaps:
        fail("baseline_gaps 缺少当前 MVP 缺口：" + ", ".join(missing_gaps))

    if payload.get("next_task_recommended") == "产品与广告归因闭环":
        fail("next_task_recommended 仍停留在旧归因阶段")
    if "产品级组判断" not in str(payload.get("next_task_recommended")):
        fail(f"next_task_recommended 未指向产品级组判断闭环：{payload.get('next_task_recommended')}")

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "current_workflow_status",
                    "product_group_count",
                    "product_group_decision_gap",
                    "manual_decision_gap",
                    "review_gap",
                    "next_task_recommended",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
