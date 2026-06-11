import argparse
import json
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "http://127.0.0.1:8001"
PRODUCT_CODE_PATTERN = re.compile(r"\bRB[A-Z0-9]{2,}\b", re.IGNORECASE)
DROP_WORDS = {
    "广泛",
    "短语",
    "精准",
    "词组",
    "扩展",
    "自动",
    "auto",
    "broad",
    "phrase",
    "exact",
}


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def request_json(path: str, params: dict[str, object] | None = None, payload: dict[str, object] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{API_BASE_URL}{path}{query}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    method = "POST" if payload is not None else "GET"
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            status = getattr(response, "status", 200)
            text = response.read().decode("utf-8", errors="replace")
            if status < 200 or status >= 300:
                fail(f"{url} 返回状态码 {status}：{text}")
            return json.loads(text)
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        fail(f"{url} 返回状态码 {exc.code}：{body_text}")
    except URLError as exc:
        fail(f"{url} 不可访问：{exc.reason}")


def latest_success_period() -> dict[str, object]:
    runs = request_json("/api/sync/runs", {"limit": 20})
    if not isinstance(runs, list):
        fail("同步记录接口返回格式异常")
    for run in runs:
        if (
            isinstance(run, dict)
            and run.get("status") == "success"
            and run.get("market_id") is not None
            and run.get("period_start")
            and run.get("period_end")
        ):
            return {
                "market_id": int(run["market_id"]),
                "period_start": str(run["period_start"]),
                "period_end": str(run["period_end"]),
                "source": run.get("source"),
            }
    fail("未找到可用于产品草稿生成的成功同步周期")


def extract_product_code(source: dict[str, Any]) -> str | None:
    text = " ".join(
        str(source.get(key) or "")
        for key in ["scope_name", "ad_group_name", "campaign_name"]
    )
    match = PRODUCT_CODE_PATTERN.search(text)
    return match.group(0).upper() if match else None


def clean_product_name(code: str, source: dict[str, Any]) -> str:
    raw = str(source.get("scope_name") or source.get("ad_group_name") or source.get("campaign_name") or code)
    text = raw.replace("_", " ").replace("-", " ").replace("/", " ").replace("&", " ")
    parts = [part.strip() for part in re.split(r"\s+", text) if part.strip()]
    kept = []
    for part in parts:
        if part.lower() in DROP_WORDS or part in DROP_WORDS:
            continue
        kept.append(part)
    name = " ".join(kept).strip()
    if code not in name.upper():
        name = f"{code} {name}".strip()
    return name or code


def product_exists(products: list[dict[str, Any]], code: str) -> bool:
    code_upper = code.upper()
    for product in products:
        values = [
            product.get("product_name"),
            product.get("asin"),
            product.get("msku"),
            product.get("sku"),
        ]
        text = " ".join(str(value or "").upper() for value in values)
        if code_upper in text:
            return True
    return False


def build_candidates(sources: list[dict[str, Any]], products: list[dict[str, Any]], limit: int) -> list[dict[str, object]]:
    by_code: dict[str, dict[str, Any]] = {}
    for source in sources:
        code = extract_product_code(source)
        if not code or product_exists(products, code):
            continue
        current = by_code.get(code)
        cost = float(source.get("cost") or 0)
        if current is None or cost > float(current.get("cost") or 0):
            by_code[code] = source

    selected = sorted(by_code.items(), key=lambda item: float(item[1].get("cost") or 0), reverse=True)[:limit]
    return [
        {
            "code": code,
            "product_name": clean_product_name(code, source),
            "market_id": source.get("market_id"),
            "source": {
                "scope_type": source.get("scope_type"),
                "scope_id": source.get("scope_id"),
                "scope_name": source.get("scope_name"),
                "campaign_name": source.get("campaign_name"),
                "ad_group_name": source.get("ad_group_name"),
                "cost": source.get("cost"),
                "sales": source.get("sales"),
                "orders": source.get("orders"),
            },
        }
        for code, source in selected
    ]


def create_product(candidate: dict[str, object]) -> dict[str, object]:
    code = str(candidate["code"])
    return request_json(
        "/api/products",
        payload={
            "product_name": candidate["product_name"],
            "asin": None,
            "msku": code,
            "sku": code,
            "brand": "RIVBOS",
            "category": "SP广告来源草稿",
            "market_id": candidate["market_id"],
            "inventory_quantity": None,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="从真实未归因广告来源生成本地产品草稿")
    parser.add_argument("--apply", action="store_true", help="实际创建产品草稿；不传则只预览")
    parser.add_argument("--limit", type=int, default=8, help="最多创建多少个产品草稿")
    args = parser.parse_args()

    period = latest_success_period()
    filters = {
        "market_id": period["market_id"],
        "start_date": period["period_start"],
        "end_date": period["period_end"],
        "scope_type": "ad_group",
    }
    products = request_json(
        "/api/products",
        {
            "market_id": period["market_id"],
            "start_date": period["period_start"],
            "end_date": period["period_end"],
        },
    )
    sources = request_json("/api/products/unbound-ad-sources", filters)
    if not isinstance(products, list) or not isinstance(sources, list):
        fail("产品列表或未归因广告来源返回格式异常")

    candidates = build_candidates(sources, products, max(1, args.limit))
    created = []
    if args.apply:
        for candidate in candidates:
            created.append(create_product(candidate))

    print(
        json.dumps(
            {
                "status": "success",
                "mode": "apply" if args.apply else "preview",
                "period": period,
                "candidate_count": len(candidates),
                "created_count": len(created),
                "candidates": candidates,
                "created_products": [
                    {
                        "id": product.get("id"),
                        "product_name": product.get("product_name"),
                        "msku": product.get("msku"),
                        "market_id": product.get("market_id"),
                    }
                    for product in created
                    if isinstance(product, dict)
                ],
                "checked": [
                    "latest_success_sync_period",
                    "unbound_ad_group_sources",
                    "product_code_extraction",
                    "local_product_draft_creation" if args.apply else "preview_only",
                    "no_ad_binding_created",
                    "no_ad_execution_api",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
