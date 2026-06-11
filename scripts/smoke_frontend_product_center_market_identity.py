from __future__ import annotations

import json
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_PATH = PROJECT_ROOT / "frontend" / "src" / "api.ts"


REQUIRED_API_MARKERS = {
    "product_market_type": "market: {",
    "product_market_name": "market_name: string | null",
    "product_country_code": "country_code: string | null",
}

REQUIRED_APP_MARKERS = {
    "product_market_formatter": "formatProductMarketLabel",
    "store_unknown_fallback": "店铺未识别",
    "sales_performance_source": "销售表现",
}

FORBIDDEN_VISIBLE_MARKERS = [
    "market_id {",
    "<Text>market_id",
    "<Tag>market_id",
    "店铺 / 站点 ID",
    "店铺 / 站点 {selected.market_id",
    "店铺 / 站点 ${dashboard.market.market_id",
]

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


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(1)


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    api_source = API_PATH.read_text(encoding="utf-8")

    missing_api = [name for name, marker in REQUIRED_API_MARKERS.items() if marker not in api_source]
    if missing_api:
        fail("前端 Product 类型缺少店铺映射字段：" + ", ".join(missing_api))

    missing_app = [name for name, marker in REQUIRED_APP_MARKERS.items() if marker not in app_source]
    if missing_app:
        fail("产品中心缺少真实店铺名展示逻辑：" + ", ".join(missing_app))

    visible_hits = [marker for marker in FORBIDDEN_VISIBLE_MARKERS if marker in app_source]
    if visible_hits:
        fail("前端仍存在用户可见的 market_id / 店铺 ID 文案：" + ", ".join(visible_hits))

    auto_action_hits = [marker for marker in FORBIDDEN_AUTO_ACTION_MARKERS if marker in app_source or marker in api_source]
    if auto_action_hits:
        fail("发现自动执行广告动作标记：" + ", ".join(auto_action_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "checked": [
                    "product_market_type",
                    "product_center_store_name_display",
                    "no_visible_market_id_copy",
                    "no_auto_execution_markers",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
