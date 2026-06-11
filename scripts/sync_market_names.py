import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.services.market_service import sync_market_names  # noqa: E402


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


async def main() -> None:
    init_db()
    settings = get_settings()
    market_ids = settings.market_ids
    if not market_ids:
        fail("GERPGO_MARKET_IDS 未配置")

    with SessionLocal() as db:
        rows = await sync_market_names(db, market_ids)

    missing = [row["market_id"] for row in rows if not row.get("market_name")]
    if missing:
        fail("未同步到店铺名称：" + ",".join(str(item) for item in missing))

    print(
        json.dumps(
            {
                "status": "success",
                "markets": rows,
                "checked": ["gerpgo_market_names_query", "market_infos_upsert"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
