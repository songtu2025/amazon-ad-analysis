import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = os.environ.get("SMOKE_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
MARKET_ID = int(os.environ.get("SMOKE_MARKET_ID", "1"))
FIRST_SCREEN_LIMIT = 5
NON_REAL_MARKERS = ("DEMO", "SMOKE", "TASK")


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def request_json(path: str, params: dict[str, object] | None = None) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{API_BASE_URL}{path}{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=12) as response:
            status = getattr(response, "status", 200)
            text = response.read().decode("utf-8", errors="replace")
            if status < 200 or status >= 300:
                fail(f"{url} 返回状态码 {status}：{text}")
            return json.loads(text)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        fail(f"{url} 返回状态码 {exc.code}：{body}")
    except URLError as exc:
        fail(f"{url} 不可访问：{exc.reason}")


def product_text(product: dict[str, Any]) -> str:
    values = [
        product.get("asin"),
        product.get("msku"),
        product.get("sku"),
        product.get("product_name"),
    ]
    return " ".join(str(value or "") for value in values).upper()


def has_real_asin(product: dict[str, Any]) -> bool:
    asin = str(product.get("asin") or "").strip().upper()
    return asin.startswith("B0") and len(asin) >= 10


def is_non_real_product(product: dict[str, Any]) -> bool:
    text = product_text(product)
    return any(marker in text for marker in NON_REAL_MARKERS)


def is_real_sales_product(product: dict[str, Any]) -> bool:
    return (
        has_real_asin(product)
        and bool(str(product.get("msku") or "").strip())
        and bool(str(product.get("product_name") or "").strip())
        and not is_non_real_product(product)
    )


def has_readable_product_identity(product: dict[str, Any]) -> bool:
    msku = str(product.get("msku") or "").strip()
    product_name = str(product.get("product_name") or "").strip()
    category = str(product.get("category") or "").strip()
    return bool(product_name) and product_name != msku and bool(category) and category != "-"


def compact_product(product: dict[str, Any]) -> dict[str, object]:
    return {
        "id": product.get("id"),
        "asin": product.get("asin"),
        "msku": product.get("msku"),
        "product_name": product.get("product_name"),
        "category": product.get("category"),
    }


def main() -> None:
    products = request_json("/api/products", {"market_id": MARKET_ID})
    if not isinstance(products, list):
        fail("产品列表接口返回格式异常")
    if len(products) < FIRST_SCREEN_LIMIT:
        fail(f"产品数量不足 {FIRST_SCREEN_LIMIT}，无法判断首屏展示优先级")

    first_screen = [product for product in products[:FIRST_SCREEN_LIMIT] if isinstance(product, dict)]
    if len(first_screen) < FIRST_SCREEN_LIMIT:
        fail("产品列表前 5 行存在非对象数据")

    non_real_first_screen = [product for product in first_screen if is_non_real_product(product)]
    if non_real_first_screen:
        fail(
            "产品中心前 5 行仍包含 DEMO/测试产品："
            + json.dumps([compact_product(product) for product in non_real_first_screen], ensure_ascii=False)
        )

    weak_first_screen = [product for product in first_screen if not is_real_sales_product(product)]
    if weak_first_screen:
        fail(
            "产品中心前 5 行未优先展示真实销售表现产品："
            + json.dumps([compact_product(product) for product in weak_first_screen], ensure_ascii=False)
        )

    weak_identity_first_screen = [product for product in first_screen if not has_readable_product_identity(product)]
    if weak_identity_first_screen:
        fail(
            "产品中心前 5 行仍包含产品名或类目识别度不足的产品："
            + json.dumps([compact_product(product) for product in weak_identity_first_screen], ensure_ascii=False)
        )

    real_product_count = sum(1 for product in products if isinstance(product, dict) and is_real_sales_product(product))
    non_real_product_count = sum(1 for product in products if isinstance(product, dict) and is_non_real_product(product))
    if real_product_count < FIRST_SCREEN_LIMIT:
        fail(f"真实产品数量不足 {FIRST_SCREEN_LIMIT}，无法支撑首屏优先展示")

    print(
        json.dumps(
            {
                "status": "success",
                "market_id": MARKET_ID,
                "product_count": len(products),
                "real_product_count": real_product_count,
                "non_real_product_count": non_real_product_count,
                "first_screen": [compact_product(product) for product in first_screen],
                "checked": [
                    "products_api_available",
                    "first_screen_real_sales_products",
                    "first_screen_readable_product_identity",
                    "demo_or_task_products_not_first_screen",
                    "no_database_write",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
