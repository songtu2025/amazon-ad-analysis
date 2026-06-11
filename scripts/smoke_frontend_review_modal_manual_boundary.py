import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_TSX = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


def fail(message: str) -> None:
    raise SystemExit(f"status=failed reason={message}")


def main() -> None:
    source = APP_TSX.read_text(encoding="utf-8")
    modal_match = re.search(
        r'title=\{reviewDecision \? `复盘处理记录 \$\{reviewDecision\.id\}` : "复盘"\}([\s\S]*?)</Modal>',
        source,
    )
    if not modal_match:
        fail("未找到复盘弹窗源码")

    modal_source = modal_match.group(0)
    required_texts = [
        "人工复盘边界",
        "只记录人工判断和指标快照",
        "不自动修改广告",
        "不会自动调整竞价、预算、否词、暂停或新增广告",
    ]
    missing = [text for text in required_texts if text not in modal_source]
    if missing:
        fail("复盘弹窗人工边界提示缺失：" + "、".join(missing))

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
                fail(f"前端按钮不应包含自动执行广告动作：{label}")

    print(
        {
            "status": "success",
            "checks": [
                "review_modal_found",
                "manual_boundary_notice",
                "no_auto_execution_buttons",
            ],
        }
    )


if __name__ == "__main__":
    main()
