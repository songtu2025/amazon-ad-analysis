import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric
from app.models.sync import SyncRun
from app.services.gerpgo_client import GerpgoClient


RAW_DIR = PROJECT_ROOT / "data" / "raw"


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _save_raw_payload(source: str, market_id: int, start_date: str, end_date: str, pages: list[dict[str, Any]]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    path = RAW_DIR / f"{source}_{market_id}_{start_date}_{end_date}_{timestamp}.json"
    path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _metric_from_row(row: dict[str, Any], synced_at: datetime) -> SpKeywordMetric:
    return SpKeywordMetric(
        source_id=_string(row.get("id")),
        market_id=_integer(row.get("marketId")) or 0,
        product_id=None,
        campaign_id=_string(row.get("campaignId")),
        campaign_name=_string(row.get("campaignName")),
        ad_group_id=_string(row.get("groupId")),
        ad_group_name=_string(row.get("groupName")),
        keyword_id=_string(row.get("keywordId")),
        keyword_text=_string(row.get("keywordText")),
        match_type=_string(row.get("matchType")),
        bid=_number(row.get("bid")),
        serving_status=_string(row.get("servingStatus")),
        data_date=_string(row.get("createDate")),
        impressions=_integer(row.get("impressions")),
        clicks=_integer(row.get("clicks")),
        cost=_number(row.get("cost")),
        ads_orders=_integer(row.get("adsOrders")),
        ads_sales=_number(row.get("adsSales")),
        ctr=_number(row.get("ctr")),
        cpc=_number(row.get("cpc")),
        cvr=_number(row.get("cvr")),
        cpa=_number(row.get("cpa")),
        acos=_number(row.get("acos")),
        roas=_number(row.get("roas")),
        raw_json=json.dumps(row, ensure_ascii=False),
        synced_at=synced_at,
    )


def _search_term_metric_from_row(row: dict[str, Any], synced_at: datetime) -> SpSearchTermMetric:
    return SpSearchTermMetric(
        source_id=_string(row.get("id")),
        market_id=_integer(row.get("marketId")) or 0,
        product_id=None,
        campaign_id=_string(row.get("campaignId")),
        campaign_name=_string(row.get("campaignName")),
        ad_group_id=_string(row.get("groupId")),
        ad_group_name=_string(row.get("groupName")),
        keyword_id=_string(row.get("keywordId")),
        keyword_text=_string(row.get("keywordText")),
        search_term=_string(row.get("searchTerm")),
        match_type=_string(row.get("matchType")),
        data_date=_string(row.get("createDate")),
        impressions=_integer(row.get("impressions")),
        clicks=_integer(row.get("clicks")),
        cost=_number(row.get("cost")),
        ads_orders=_integer(row.get("adsOrders")),
        ads_sales=_number(row.get("adsSales")),
        ctr=_number(row.get("ctr")),
        cpc=_number(row.get("cpc")),
        cvr=_number(row.get("cvr")),
        acos=_number(row.get("acos")),
        roas=_number(row.get("roas")),
        raw_json=json.dumps(row, ensure_ascii=False),
        synced_at=synced_at,
    )


async def sync_sp_keywords(
    db: Session,
    market_id: int,
    start_date: date,
    end_date: date,
    count: int = 10,
    max_pages: int | None = 3,
    page_delay_seconds: float = 1.2,
) -> dict[str, object]:
    started_at = datetime.now()
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    run = SyncRun(
        source="sp_keywords",
        market_id=market_id,
        period_start=start_text,
        period_end=end_text,
        status="running",
        rows_synced=0,
        started_at=started_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    pages: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    try:
        client = GerpgoClient()
        async for page in client.iter_sp_keyword_pages(
            market_id,
            start_text,
            end_text,
            count=count,
            max_pages=max_pages,
            page_delay_seconds=page_delay_seconds,
        ):
            pages.append(page.raw)
            rows.extend(page.data)

        raw_path = _save_raw_payload("sp_keywords", market_id, start_text, end_text, pages)
        synced_at = datetime.now()
        metrics = [_metric_from_row(row, synced_at) for row in rows]
        db.add_all(metrics)

        run.status = "success"
        run.rows_synced = len(metrics)
        run.raw_path = str(raw_path)
        run.finished_at = datetime.now()
        db.commit()

        return {
            "status": run.status,
            "market_id": market_id,
            "period_start": start_text,
            "period_end": end_text,
            "rows_synced": len(metrics),
            "raw_path": str(raw_path),
            "page_size": count,
            "max_pages": max_pages,
        }
    except Exception as exc:
        run.status = "failed"
        run.message = str(exc)
        run.finished_at = datetime.now()
        db.commit()
        raise


async def sync_sp_search_terms(
    db: Session,
    market_id: int,
    start_date: date,
    end_date: date,
    count: int = 10,
    max_pages: int | None = 3,
    page_delay_seconds: float = 1.2,
) -> dict[str, object]:
    started_at = datetime.now()
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    run = SyncRun(
        source="sp_search_terms",
        market_id=market_id,
        period_start=start_text,
        period_end=end_text,
        status="running",
        rows_synced=0,
        started_at=started_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    pages: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    try:
        client = GerpgoClient()
        for report_name, iterator in [
            (
                "targeting",
                client.iter_sp_search_targeting_pages(
                    market_id,
                    start_text,
                    end_text,
                    count=count,
                    max_pages=max_pages,
                    page_delay_seconds=page_delay_seconds,
                ),
            ),
            (
                "keyword",
                client.iter_sp_search_keyword_pages(
                    market_id,
                    start_text,
                    end_text,
                    count=count,
                    max_pages=max_pages,
                    page_delay_seconds=page_delay_seconds,
                ),
            ),
        ]:
            async for page in iterator:
                raw_page = dict(page.raw)
                raw_page["_local_report_type"] = report_name
                pages.append(raw_page)
                rows.extend(page.data)

        raw_path = _save_raw_payload("sp_search_terms", market_id, start_text, end_text, pages)
        synced_at = datetime.now()
        metrics = [_search_term_metric_from_row(row, synced_at) for row in rows]
        db.add_all(metrics)

        run.status = "success"
        run.rows_synced = len(metrics)
        run.raw_path = str(raw_path)
        run.finished_at = datetime.now()
        db.commit()

        return {
            "status": run.status,
            "market_id": market_id,
            "period_start": start_text,
            "period_end": end_text,
            "rows_synced": len(metrics),
            "raw_path": str(raw_path),
            "page_size": count,
            "max_pages": max_pages,
        }
    except Exception as exc:
        run.status = "failed"
        run.message = str(exc)
        run.finished_at = datetime.now()
        db.commit()
        raise
