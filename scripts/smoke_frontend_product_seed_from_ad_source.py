import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


REQUIRED_APP_MARKERS = {
    "prefill_handler": "prefillProductFromAdSource",
    "seed_button_text": "从广告来源创建产品草稿",
    "source_prefill_name": "product_name: source.scope_name || source.ad_group_name || source.campaign_name",
    "source_prefill_market": "market_id: source.market_id ?? productMarketId ?? undefined",
    "open_create_modal": "setCreateProductOpen(true)",
    "created_product_selected": "setAttributionProductId(createdProduct.id)",
    "reload_evidence_after_create": "fetchProductAttributionEvidence",
    "product_seed_hint": "先创建产品草稿，再人工确认归因",
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
    missing = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing:
        fail("App.tsx 产品草稿入口标记缺失：" + ", ".join(missing))

    forbidden_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source]
    if forbidden_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_seed_prefill_handler",
                    "ad_source_seed_button",
                    "evidence_drawer_seed_button",
                    "source_name_market_prefill",
                    "created_product_selected",
                    "evidence_reload_after_create",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
