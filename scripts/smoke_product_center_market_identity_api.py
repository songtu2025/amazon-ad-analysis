from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.products import list_products  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models.market import MarketInfo  # noqa: E402
from app.models.product import Product  # noqa: E402


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


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1)


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def main() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        now = datetime.now()
        db.add(
            MarketInfo(
                market_id=1,
                market_name="rivbos",
                country_code="US",
                raw_name="rivbos:US",
                updated_at=now,
            )
        )
        product = Product(
            asin="B058MARKET1",
            msku="TASK058-MARKET-MSKU",
            sku="TASK058-MARKET-SKU",
            product_name="TASK058 Market Product",
            image_url=None,
            brand="RIVBOS",
            category="Sunglasses",
            market_id=1,
            inventory_quantity=None,
            created_at=now,
            updated_at=now,
        )
        db.add(product)
        db.commit()

        rows = list_products(
            market_id=1,
            start_date=date.fromisoformat("2026-05-12"),
            end_date=date.fromisoformat("2026-06-10"),
            db=db,
        )
        row = next((item for item in rows if item["id"] == product.id), None)
        if row is None:
            fail("产品列表未返回测试产品")

        market = row.get("market")
        if not isinstance(market, dict):
            fail("产品列表未返回 market 店铺映射", {"row": row})
        if market.get("market_name") != "rivbos" or market.get("country_code") != "US":
            fail("产品列表 market 店铺映射不正确", {"market": market})

        forbidden_hits = find_forbidden_keys(row)
        if forbidden_hits:
            fail("产品列表返回发现自动执行广告动作字段", {"hits": forbidden_hits})

        print(
            json.dumps(
                {
                    "status": "success",
                    "market": market,
                    "checked": [
                        "product_market_identity_payload",
                        "market_name_from_market_infos",
                        "country_code_from_market_infos",
                        "no_auto_execution_fields",
                    ],
                },
                ensure_ascii=False,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
