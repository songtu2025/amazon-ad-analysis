import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.services.gerpgo_client import _looks_like_placeholder  # noqa: E402
from app.services.sync_service import sync_sp_keywords  # noqa: E402


async def main() -> None:
    settings = get_settings()
    if not settings.gerpgo_access_token and (not settings.gerpgo_app_id or not settings.gerpgo_app_key):
        raise SystemExit(
            "Configure GERPGO_APP_ID and GERPGO_APP_KEY, or set GERPGO_ACCESS_TOKEN. "
            "Create .env from .env.example first."
        )
    if settings.gerpgo_access_token and _looks_like_placeholder(settings.gerpgo_access_token):
        raise SystemExit("GERPGO_ACCESS_TOKEN still contains a placeholder value.")
    if settings.gerpgo_app_id and _looks_like_placeholder(settings.gerpgo_app_id):
        raise SystemExit("GERPGO_APP_ID still contains a placeholder value.")
    if settings.gerpgo_app_key and _looks_like_placeholder(settings.gerpgo_app_key):
        raise SystemExit("GERPGO_APP_KEY still contains a placeholder value.")
    if not settings.market_ids:
        raise SystemExit("GERPGO_MARKET_IDS is not configured. Create .env from .env.example first.")

    init_db()
    market_id = settings.market_ids[0]
    today = date.today()
    with SessionLocal() as db:
        result = await sync_sp_keywords(
            db=db,
            market_id=market_id,
            start_date=today - timedelta(days=13),
            end_date=today,
            count=10,
            max_pages=3,
        )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
