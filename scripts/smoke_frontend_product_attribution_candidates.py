import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "candidate_type": "export type ProductAttributionCandidateRow",
    "candidate_response_type": "export type ProductAttributionCandidates",
    "candidate_fetcher": "fetchProductAttributionCandidates",
    "candidate_endpoint": "/api/products/attribution-candidates",
    "min_confidence_filter": "min_confidence",
}

REQUIRED_APP_MARKERS = {
    "candidate_state": "productAttributionCandidates",
    "candidate_loader": "loadProductAttributionCandidates",
    "candidate_columns": "productAttributionCandidateColumns",
    "candidate_panel": "高可信归因候选",
    "candidate_warning": "人工确认前请查看证据",
    "candidate_evidence_flow": "openAttributionEvidence(record.source, record.candidate_product.product_id)",
    "candidate_refresh": "刷新候选",
    "candidate_manual_hint": "必须查看证据并由人工确认后才会保存归因规则",
}

REQUIRED_STYLE_MARKERS = {
    "candidate_panel_class": ".attribution-candidate-panel",
    "candidate_reason_class": ".attribution-candidate-reason",
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
    api_source = API_PATH.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")

    missing_api = [name for name, marker in REQUIRED_API_MARKERS.items() if marker not in api_source]
    if missing_api:
        fail("api.ts 产品归因候选标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 产品归因候选标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 产品归因候选标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_attribution_candidate_api_client",
                    "candidate_panel",
                    "candidate_table",
                    "evidence_first_flow",
                    "manual_confirmation_hint",
                    "candidate_styles",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
