from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.sync import SyncRun
from app.services.gerpgo_client import GerpgoRateLimitError
from app.services.sync_service import sync_sp_keywords, sync_sp_search_terms


router = APIRouter()


def _sync_run_payload(run: SyncRun) -> dict[str, object]:
    return {
        "id": run.id,
        "source": run.source,
        "market_id": run.market_id,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "status": run.status,
        "rows_synced": run.rows_synced,
        "raw_path": run.raw_path,
        "message": run.message,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _guard_sync_cooldown(db: Session, source: str, market_id: int, cooldown_seconds: int) -> None:
    if cooldown_seconds <= 0:
        return
    latest = db.execute(
        select(SyncRun)
        .where(SyncRun.source == source, SyncRun.market_id == market_id, SyncRun.status.in_(["running", "success", "failed"]))
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return

    now = datetime.now()
    latest_time = latest.finished_at or latest.started_at
    elapsed_seconds = (now - latest_time).total_seconds()
    if latest.status == "running" or elapsed_seconds < cooldown_seconds:
        wait_seconds = max(1, int(cooldown_seconds - elapsed_seconds))
        raise HTTPException(
            status_code=429,
            detail={
                "message": "同步请求过于频繁，请稍后再试",
                "source": source,
                "market_id": market_id,
                "wait_seconds": wait_seconds,
            },
        )


def _validate_sync_params(count: int, max_pages: int | None) -> None:
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="同步条数 count 必须在 1 到 50 之间")
    if max_pages is not None and (max_pages < 1 or max_pages > 3):
        raise HTTPException(status_code=400, detail="同步页数 max_pages 必须在 1 到 3 之间")


def _validate_runs_limit(limit: int) -> None:
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="同步记录数量 limit 必须在 1 到 50 之间")


def _validate_market_id(market_id: int) -> None:
    if market_id <= 0:
        raise HTTPException(status_code=400, detail="店铺 / 站点 ID market_id 必须大于 0")


def _rate_limit_exception(source: str, market_id: int, exc: GerpgoRateLimitError) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "message": "积加接口限流，请降低同步频率后重试",
            "source": source,
            "market_id": market_id,
            "upstream_message": str(exc),
        },
    )


@router.post("/sp-keywords")
async def sync_sp_keyword_report(
    market_id: int | None = None,
    count: int = 10,
    max_pages: int | None = 3,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    selected_market_id = market_id if market_id is not None else (settings.market_ids[0] if settings.market_ids else None)
    if selected_market_id is None:
        raise HTTPException(status_code=400, detail="请先在 .env 中配置 GERPGO_MARKET_IDS")
    _validate_market_id(selected_market_id)
    _validate_sync_params(count, max_pages)
    _guard_sync_cooldown(db, "sp_keywords", selected_market_id, settings.sync_cooldown_seconds)

    today = date.today()
    try:
        result = await sync_sp_keywords(
            db=db,
            market_id=selected_market_id,
            start_date=today - timedelta(days=13),
            end_date=today,
            count=count,
            max_pages=max_pages,
        )
    except GerpgoRateLimitError as exc:
        raise _rate_limit_exception("sp_keywords", selected_market_id, exc) from exc
    return result


@router.post("/sp-ads")
async def sync_sp_ads_report(
    market_id: int | None = None,
    count: int = 10,
    max_pages: int | None = 3,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return await sync_sp_keyword_report(market_id=market_id, count=count, max_pages=max_pages, db=db)


@router.post("/sp-search-terms")
async def sync_sp_search_term_report(
    market_id: int | None = None,
    count: int = 10,
    max_pages: int | None = 3,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    selected_market_id = market_id if market_id is not None else (settings.market_ids[0] if settings.market_ids else None)
    if selected_market_id is None:
        raise HTTPException(status_code=400, detail="请先在 .env 中配置 GERPGO_MARKET_IDS")
    _validate_market_id(selected_market_id)
    _validate_sync_params(count, max_pages)
    _guard_sync_cooldown(db, "sp_search_terms", selected_market_id, settings.sync_cooldown_seconds)

    today = date.today()
    try:
        return await sync_sp_search_terms(
            db=db,
            market_id=selected_market_id,
            start_date=today - timedelta(days=13),
            end_date=today,
            count=count,
            max_pages=max_pages,
        )
    except GerpgoRateLimitError as exc:
        raise _rate_limit_exception("sp_search_terms", selected_market_id, exc) from exc


@router.get("/status")
def sync_status(db: Session = Depends(get_db)) -> dict[str, object]:
    latest = db.execute(select(SyncRun).order_by(SyncRun.started_at.desc(), SyncRun.id.desc()).limit(1)).scalar_one_or_none()
    if latest is None:
        return {"latest": None}
    return {"latest": _sync_run_payload(latest)}


@router.get("/runs")
def list_sync_runs(limit: int = 10, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    _validate_runs_limit(limit)
    runs = db.execute(
        select(SyncRun)
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(limit)
    ).scalars().all()
    return [_sync_run_payload(run) for run in runs]
