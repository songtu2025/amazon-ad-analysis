from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import SessionLocal
from app.models.sync import SyncRun
from app.services.sync_service import sync_sp_keywords, sync_sp_search_terms


def _scheduler_sources(raw_sources: str) -> set[str]:
    return {source.strip() for source in raw_sources.split(",") if source.strip()}


def _cooldown_active(db: Session, source: str, market_id: int, cooldown_seconds: int) -> bool:
    if cooldown_seconds <= 0:
        return False
    latest = db.execute(
        select(SyncRun)
        .where(SyncRun.source == source, SyncRun.market_id == market_id, SyncRun.status.in_(["running", "success", "failed"]))
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return False
    if latest.status == "running":
        return True
    latest_time = latest.finished_at or latest.started_at
    return (datetime.now() - latest_time).total_seconds() < cooldown_seconds


async def _run_scheduled_sync(settings: Settings) -> None:
    if not settings.market_ids:
        return

    today = date.today()
    start_date = today - timedelta(days=13)
    sources = _scheduler_sources(settings.sync_scheduler_sources)

    with SessionLocal() as db:
        for market_id in settings.market_ids:
            if "sp_keywords" in sources and not _cooldown_active(db, "sp_keywords", market_id, settings.sync_cooldown_seconds):
                await sync_sp_keywords(
                    db=db,
                    market_id=market_id,
                    start_date=start_date,
                    end_date=today,
                    count=10,
                    max_pages=3,
                )
            if "sp_search_terms" in sources and not _cooldown_active(db, "sp_search_terms", market_id, settings.sync_cooldown_seconds):
                await sync_sp_search_terms(
                    db=db,
                    market_id=market_id,
                    start_date=start_date,
                    end_date=today,
                    count=10,
                    max_pages=1,
                )


def start_scheduler_if_enabled(settings: Settings) -> Any | None:
    if not settings.sync_scheduler_enabled:
        return None

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError as exc:
        raise RuntimeError("APScheduler 未安装，请先运行 pip install -r backend/requirements.txt") from exc

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_scheduled_sync,
        "interval",
        minutes=max(settings.sync_scheduler_interval_minutes, 1),
        args=[settings],
        id="sp_ads_scheduled_sync",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def stop_scheduler(scheduler: Any | None) -> None:
    if scheduler is not None and getattr(scheduler, "running", False):
        scheduler.shutdown(wait=False)
