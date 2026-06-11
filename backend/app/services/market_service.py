from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import MarketInfo
from app.services.gerpgo_client import GerpgoClient


def parse_market_names(raw: str, market_ids: list[int]) -> list[dict[str, object]]:
    parts = [part.strip() for part in raw.split(";") if part.strip()]
    parsed: list[dict[str, object]] = []
    for index, market_id in enumerate(market_ids):
        part = parts[index] if index < len(parts) else ""
        market_name, country_code = part, None
        if ":" in part:
            market_name, country_code = part.split(":", 1)
        parsed.append(
            {
                "market_id": market_id,
                "market_name": market_name.strip() or None,
                "country_code": country_code.strip() if country_code else None,
                "raw_name": part or None,
            }
        )
    return parsed


async def sync_market_names(db: Session, market_ids: list[int]) -> list[dict[str, object]]:
    if not market_ids:
        return []
    raw = await GerpgoClient().fetch_market_names_text(market_ids)
    rows = parse_market_names(raw, market_ids)
    now = datetime.now()
    for row in rows:
        existing = db.get(MarketInfo, row["market_id"])
        if existing is None:
            existing = MarketInfo(market_id=int(row["market_id"]), updated_at=now)
            db.add(existing)
        existing.market_name = row["market_name"] if isinstance(row["market_name"], str) else None
        existing.country_code = row["country_code"] if isinstance(row["country_code"], str) else None
        existing.raw_name = row["raw_name"] if isinstance(row["raw_name"], str) else None
        existing.updated_at = now
    db.commit()
    return [market_info_payload(db.get(MarketInfo, int(row["market_id"]))) for row in rows]


def market_info_payload(info: MarketInfo | None) -> dict[str, object] | None:
    if info is None:
        return None
    return {
        "market_id": info.market_id,
        "market_name": info.market_name,
        "country_code": info.country_code,
        "raw_name": info.raw_name,
        "updated_at": info.updated_at.isoformat(),
    }


def get_market_info(db: Session, market_id: int) -> MarketInfo | None:
    return db.execute(select(MarketInfo).where(MarketInfo.market_id == market_id)).scalar_one_or_none()
