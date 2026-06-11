import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_APP_MARKERS = {
    "first_candidate_state": "firstAttributionCandidate",
    "empty_binding_condition": "productAdBindings.length === 0 && firstAttributionCandidate",
    "guide_title": "首条真实归因引导",
    "unlock_hint": "可解锁搜索词",
    "manual_save_boundary": "不会自动保存归因规则",
    "cta_text": "查看证据并确认归因",
    "evidence_flow": "openAttributionEvidence(firstAttributionCandidate.source, firstAttributionCandidate.candidate_product.product_id)",
    "guide_class": "first-attribution-guide",
}

REQUIRED_STYLE_MARKERS = {
    "guide_class": ".first-attribution-guide",
    "guide_header_class": ".first-attribution-guide-header",
    "guide_metrics_class": ".first-attribution-guide-metrics",
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
    app_source = APP_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 首条真实归因引导标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 首条真实归因引导标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "first_attribution_candidate",
                    "empty_binding_condition",
                    "evidence_only_cta",
                    "manual_save_boundary",
                    "guide_styles",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
