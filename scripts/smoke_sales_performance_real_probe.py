from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.gerpgo_client import GerpgoClient, _looks_like_placeholder  # noqa: E402


API_PATH = "/operation/sts/salesAnalysis/page"
COOLDOWN_SECONDS = 5.2
PAGESIZE = 10
GROUP_BY_TYPE = "seller_sku"

PRODUCT_FIELDS = {"asin", "msku", "sku", "productName", "marketId", "marketName"}
SALES_FIELDS = {"unitsOrdered", "orders", "orderProductSales"}
TRAFFIC_FIELDS = {"sessions", "pageViews", "orderCvr"}
AD_FIELDS = {"adsSpend", "adsSales", "acos", "adsOrders", "adsClicks"}
FORBIDDEN_ACTION_KEYS = {
    "execute",
    "auto_execute",
    "execution_url",
    "execution_payload",
    "bid_adjustment",
    "new_bid",
    "pause_ad",
    "enable_ad",
    "negative_keyword",
    "create_keyword",
}


def fail(message: str, payload: dict[str, Any] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    sys.exit(1)


def output(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def validate_settings() -> int:
    settings = get_settings()
    if settings.gerpgo_access_token and _looks_like_placeholder(settings.gerpgo_access_token):
        fail("GERPGO_ACCESS_TOKEN 仍是示例值")
    if settings.gerpgo_app_id and _looks_like_placeholder(settings.gerpgo_app_id):
        fail("GERPGO_APP_ID 仍是示例值")
    if settings.gerpgo_app_key and _looks_like_placeholder(settings.gerpgo_app_key):
        fail("GERPGO_APP_KEY 仍是示例值")
    if not settings.gerpgo_access_token and (not settings.gerpgo_app_id or not settings.gerpgo_app_key):
        fail("请先配置 GERPGO_APP_ID 和 GERPGO_APP_KEY，或设置 GERPGO_ACCESS_TOKEN")
    if not settings.market_ids:
        fail("GERPGO_MARKET_IDS 未配置")
    return settings.market_ids[0]


def date_range() -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=29)
    return start.isoformat(), end.isoformat()


def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    return "90008" in text or "调用次数" in text or "超过限制" in text or "rate limit" in text.lower()


def assert_no_auto_execution(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key)
            if normalized in FORBIDDEN_ACTION_KEYS:
                fail("真实销售表现响应包含疑似广告执行字段", {"field": normalized})
            assert_no_auto_execution(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_auto_execution(child)


def sample_identity(row: dict[str, Any]) -> dict[str, Any]:
    sample_fields = [
        "asin",
        "msku",
        "sku",
        "productName",
        "marketId",
        "marketName",
        "unitsOrdered",
        "orders",
        "orderProductSales",
        "sessions",
        "adsSpend",
        "adsSales",
        "acos",
    ]
    return {field: row.get(field) for field in sample_fields if field in row}


async def main() -> None:
    market_id = validate_settings()
    start_date, end_date = date_range()
    payload = {
        "groupByType": GROUP_BY_TYPE,
        "showCurrencyType": "USD",
        "beginDate": start_date,
        "endDate": end_date,
        "page": 1,
        "pagesize": PAGESIZE,
        "isShowTotal": False,
        "marketId": market_id,
    }

    started_at = time.monotonic()
    time.sleep(COOLDOWN_SECONDS)
    try:
        raw = await GerpgoClient().post(API_PATH, payload)
    except Exception as exc:
        if is_rate_limit_error(exc):
            output(
                {
                    "status": "rate_limited",
                    "api_path": API_PATH,
                    "rate_limit_rule": "每 5 秒 1 次",
                    "cooldown_seconds": COOLDOWN_SECONDS,
                    "request": payload,
                    "error": str(exc),
                    "next_action": "等待积加限流恢复后重跑本脚本；不要连续重试。",
                }
            )
            return
        fail("销售表现真实接口调用失败", {"error": str(exc), "request": payload})

    elapsed_seconds = round(time.monotonic() - started_at, 2)
    assert_no_auto_execution(raw)
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        fail("销售表现响应缺少 data 对象", {"response_keys": sorted(raw.keys()) if isinstance(raw, dict) else []})
    rows = data.get("rows")
    if not isinstance(rows, list):
        fail("销售表现响应 data.rows 不是列表", {"data_keys": sorted(data.keys())})
    if not rows:
        fail(
            "销售表现真实接口未返回 rows",
            {
                "request": payload,
                "total": data.get("total"),
                "page": data.get("page"),
            },
        )

    first_row = rows[0]
    if not isinstance(first_row, dict):
        fail("销售表现 rows[0] 不是对象")

    missing_product_fields = sorted(PRODUCT_FIELDS - set(first_row))
    if missing_product_fields:
        fail("真实 rows 缺少产品基础字段", {"missing": missing_product_fields, "sample_keys": sorted(first_row.keys())})

    present_metric_groups = {
        "sales": sorted(SALES_FIELDS & set(first_row)),
        "traffic": sorted(TRAFFIC_FIELDS & set(first_row)),
        "ad": sorted(AD_FIELDS & set(first_row)),
    }
    if not any(present_metric_groups.values()):
        fail("真实 rows 缺少销售/流量/广告表现字段", {"sample_keys": sorted(first_row.keys())})

    print("SMOKE_SALES_PERFORMANCE_REAL_PROBE_OK")
    output(
        {
            "status": "success",
            "api_path": API_PATH,
            "rate_limit_rule": "每 5 秒 1 次",
            "cooldown_seconds": COOLDOWN_SECONDS,
            "elapsed_seconds": elapsed_seconds,
            "request": payload,
            "row_count": len(rows),
            "total": data.get("total"),
            "page": data.get("page"),
            "sample": sample_identity(first_row),
            "present_metric_groups": present_metric_groups,
            "checked": [
                "single_sales_performance_call",
                "seller_sku_group_by",
                "pagesize_10",
                "product_identity_fields",
                "business_metric_fields",
                "no_auto_execution_fields",
                "no_db_write",
            ],
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
