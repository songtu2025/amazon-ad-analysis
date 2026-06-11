import json
import re
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "source_product_state": "adDraftAttributionReviewSourceProduct",
    "sets_source_product": "setAdDraftAttributionReviewSourceProduct(selectedGoalRuleProduct)",
    "source_match_helper": "sourceMatchesProductIdentity",
    "focused_candidate_variable": "adDraftAttributionSourceCandidates",
    "focused_first_candidate": "firstAdDraftAttributionSourceCandidate",
    "focused_panel_class": "ad-draft-attribution-source-focus",
    "focused_panel_title": "建议优先核查的广告来源",
    "focused_panel_context": "已按草稿广告来源线索自动定位可能相关的广告来源，并保留候选销售表现产品作为人工确认目标",
    "focused_source_label": "广告来源证据行",
    "focused_product_label": "候选销售表现产品",
    "focused_button_label": "查看该广告来源证据",
    "focused_manual_boundary": "只做证据定位和人工核查，不会自动保存归因规则，也不会改广告",
    "focused_candidate_filter": "sourceMatchesProductIdentity(source, adDraftAttributionReviewSourceProduct)",
    "focused_evidence_click": "openAttributionEvidence(firstAdDraftAttributionSourceCandidate, adDraftAttributionReviewProduct.id)",
    "focused_table_row_class": "ad-draft-focused-candidate-row",
}

REQUIRED_STYLE_MARKERS = {
    "focused_panel_style": ".ad-draft-attribution-source-focus",
    "focused_source_style": ".ad-draft-focused-source",
    "focused_row_style": ".ad-draft-focused-candidate-row",
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

FORBIDDEN_BUTTON_LABELS = [
    "自动保存归因",
    "自动合并",
    "自动迁移",
    "执行广告动作",
    "调整竞价",
    "暂停广告",
    "开启广告",
    "否定关键词",
    "新增关键词",
]


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def _assert_no_forbidden_buttons(app_source: str) -> None:
    button_blocks = re.findall(r"<Button\b[\s\S]*?</Button>", app_source)
    for block in button_blocks:
        normalized = re.sub(r"\s+", "", block)
        for label in FORBIDDEN_BUTTON_LABELS:
            if label in normalized:
                fail(f"发现不允许的按钮：{label}")


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("草稿产品归因核查的广告来源候选定位缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("草稿产品归因核查的广告来源候选定位样式缺失：" + ", ".join(missing_style))

    auto_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if auto_hits:
        fail("发现自动执行或自动投放相关标记：" + ", ".join(auto_hits))

    _assert_no_forbidden_buttons(app_source)

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "ad_draft_attribution_source_focus",
                    "ad_draft_identity_based_source_location",
                    "evidence_first_manual_flow",
                    "no_auto_save_or_ad_execution_buttons",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
