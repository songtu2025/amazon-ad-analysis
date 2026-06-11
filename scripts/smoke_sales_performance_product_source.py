from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any


DOC_DETAIL_URL = "https://open.gerpgo.com/api/openAdmin/doc/detail?id=3375"
EXPECTED_API_URL = "/operation/sts/salesAnalysis/page"

REQUIRED_REQUEST_FIELDS = {
    "groupByType",
    "showCurrencyType",
    "beginDate",
    "endDate",
    "page",
    "pagesize",
}

FIELD_GROUPS = {
    "product_identity": {
        "label": "产品基础档案",
        "fields": {
            "asin",
            "msku",
            "sku",
            "productName",
            "variationAsin",
            "imgUrl",
            "brand",
            "category",
            "marketId",
            "marketName",
            "countryName",
        },
    },
    "sales_performance": {
        "label": "销售表现",
        "fields": {
            "unitsOrdered",
            "orders",
            "orderProductSales",
            "averageDailySales",
            "averagePrice",
        },
    },
    "traffic_conversion": {
        "label": "流量转化",
        "fields": {
            "sessions",
            "pageViews",
            "orderCvr",
            "buyBoxPercentage",
        },
    },
    "ad_support": {
        "label": "广告辅助",
        "fields": {
            "adsImpressions",
            "adsClicks",
            "adsOrders",
            "adsSpend",
            "adsSales",
            "acos",
            "cpc",
            "adsCvr",
            "spAdsOrders",
            "spAdsSales",
        },
    },
    "profit_cost": {
        "label": "利润成本",
        "fields": {
            "salesGrossProfit",
            "grossProfitRate",
            "salesNetProfit",
            "salesNetProfitRate",
            "roi",
            "purchaseCost",
            "commissionCost",
            "fbaShippingCost",
        },
    },
    "inventory_lifecycle": {
        "label": "库存生命周期",
        "fields": {
            "onInventory",
            "salesTurnoverRate",
            "listingLevel",
            "listingState",
            "addDate",
            "firstSalesDate",
        },
    },
    "promotion": {
        "label": "促销影响",
        "fields": {
            "coupon",
            "promotionDiscount",
            "couponPromotionUnitsOrdered",
            "promotionOrderProductSales",
        },
    },
}


def fail(message: str, payload: dict[str, Any] | None = None) -> None:
    if payload:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(f"SMOKE_SALES_PERFORMANCE_PRODUCT_SOURCE_FAIL: {message}")


def fetch_doc_detail() -> dict[str, Any]:
    request = urllib.request.Request(DOC_DETAIL_URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if payload.get("code") not in (0, 200, None):
        fail("官方文档详情接口返回非成功 code", {"code": payload.get("code"), "messages": payload.get("messages")})
    data = payload.get("data")
    if not isinstance(data, dict):
        fail("官方文档详情缺少 data 对象", payload)
    return data


def child_named(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for item in items:
        if item.get("name") == name:
            return item
    fail(f"字段层级缺少 {name}")


def row_fields(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    response_body = doc.get("responseBody")
    if not isinstance(response_body, list):
        fail("responseBody 不是列表")
    data_node = child_named(response_body, "data")
    rows_node = child_named(data_node.get("children") or [], "rows")
    children = rows_node.get("children") or []
    if not children:
        fail("data.rows 没有字段定义")
    return {str(item.get("name")): item for item in children if item.get("name")}


def main() -> None:
    doc = fetch_doc_detail()
    api_name = doc.get("apiName")
    api_url = doc.get("apiUrl")
    if api_name != "销售表现":
        fail("文档 id=3375 不是销售表现接口", {"apiName": api_name})
    if api_url != EXPECTED_API_URL:
        fail("销售表现接口路径不符合预期", {"apiUrl": api_url, "expected": EXPECTED_API_URL})

    request_fields = {str(item.get("name")): item for item in doc.get("requestBody") or [] if item.get("name")}
    missing_request = sorted(REQUIRED_REQUEST_FIELDS - set(request_fields))
    if missing_request:
        fail("销售表现接口请求字段不完整", {"missing_request_fields": missing_request})

    group_by_description = str(request_fields["groupByType"].get("description") or "")
    if "seller_sku" not in group_by_description:
        fail("groupByType 文档未说明 MSKU 维度使用 seller_sku", {"description": group_by_description})

    rows = row_fields(doc)
    group_results: dict[str, dict[str, Any]] = {}
    for group_key, config in FIELD_GROUPS.items():
        required = set(config["fields"])
        present = sorted(required & set(rows))
        missing = sorted(required - set(rows))
        if missing:
            fail(
                f"{config['label']}字段缺失",
                {
                    "group": group_key,
                    "missing": missing,
                    "present": present,
                },
            )
        group_results[group_key] = {
            "label": config["label"],
            "field_count": len(present),
            "fields": present,
        }

    source_text = " ".join(str(doc.get(key) or "") for key in ("apiName", "apiUrl", "erpUrl", "erpMethod"))
    forbidden_action_terms = ["bid", "pause", "enable", "negative", "delete", "update"]
    matched_forbidden = [term for term in forbidden_action_terms if term.lower() in source_text.lower()]
    if matched_forbidden:
        fail("销售表现接口元信息疑似包含广告执行动作", {"matched_forbidden": matched_forbidden})

    result = {
        "status": "ok",
        "api": {
            "apiName": api_name,
            "apiUrl": api_url,
            "erpUrl": doc.get("erpUrl"),
            "method": doc.get("erpMethod"),
            "docUrl": DOC_DETAIL_URL,
        },
        "request": {
            "required_fields": sorted(REQUIRED_REQUEST_FIELDS),
            "groupByType_note": group_by_description,
            "recommended_first_probe": {
                "groupByType": "seller_sku",
                "showCurrencyType": "USD",
                "beginDate": "2026-05-12",
                "endDate": "2026-06-10",
                "page": 1,
                "pagesize": 10,
                "isShowTotal": False,
            },
        },
        "row_field_count": len(rows),
        "usable_groups": group_results,
        "project_decision": {
            "use_for": ["产品基础档案", "产品经营表现快照", "广告判断背景证据"],
            "do_not_use_for": ["替代 SP 关键词报表", "替代 SP 搜索词报表", "自动执行广告动作"],
            "first_version_mapping": {
                "products.asin": "asin",
                "products.msku": "msku",
                "products.sku": "sku",
                "products.product_name": "productName",
                "products.image_url": "imgUrl",
                "products.brand": "brand",
                "products.category": "category",
                "products.market_id": "marketId",
            },
        },
    }
    print("SMOKE_SALES_PERFORMANCE_PRODUCT_SOURCE_OK")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        fail(f"无法读取官方文档详情接口：{exc}")
    except json.JSONDecodeError as exc:
        fail(f"官方文档详情不是合法 JSON：{exc}")
