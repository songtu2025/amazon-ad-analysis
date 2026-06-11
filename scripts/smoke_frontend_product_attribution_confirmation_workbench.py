import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"
STYLE_PATH = PROJECT_ROOT / "frontend" / "src" / "styles.css"


REQUIRED_API_MARKERS = {
    "candidate_row_type": "export type ProductAttributionCandidateRow",
    "priority_rank": "priority_rank",
    "priority_label": "priority_label",
    "unlock_impact": "unlock_impact",
    "candidate_fetcher": "fetchProductAttributionCandidates",
}

REQUIRED_APP_MARKERS = {
    "candidate_panel": "高可信归因候选",
    "latest_sync_period_fallback": "resolveProductAttributionFilters",
    "latest_sync_runs_lookup": "fetchSyncRuns(20)",
    "product_period_sync": "setProductStartDate(latest.period_start)",
    "priority_label": "建议优先确认",
    "unlock_impact_title": "确认后影响",
    "unlock_impact_usage": "record.unlock_impact",
    "top_priority_badge": "record.priority_rank === 1",
    "candidate_evidence_flow": "openAttributionEvidence(record.source, record.candidate_product.product_id)",
    "manual_hint": "必须查看证据并由人工确认后才会保存归因规则",
}

REQUIRED_STYLE_MARKERS = {
    "priority_badge_class": ".attribution-priority-badge",
    "unlock_impact_class": ".attribution-unlock-impact",
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
        fail("api.ts 候选确认工作台标记缺失：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("App.tsx 候选确认工作台标记缺失：" + ", ".join(missing_app))

    missing_style = [name for name, marker in REQUIRED_STYLE_MARKERS.items() if marker not in style_source]
    if missing_style:
        fail("styles.css 候选确认工作台标记缺失：" + ", ".join(missing_style))

    combined = "\n".join([app_source, api_source, style_source])
    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in combined]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "priority_rank_type",
                    "priority_label_type",
                    "unlock_impact_type",
                    "priority_badge",
                    "unlock_impact_panel",
                    "evidence_first_flow",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
