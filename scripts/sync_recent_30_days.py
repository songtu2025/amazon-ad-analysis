import argparse
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric  # noqa: E402
from app.models.sync import SyncRun  # noqa: E402
from app.services.gerpgo_client import _looks_like_placeholder  # noqa: E402
from app.services.sync_service import sync_sp_keywords, sync_sp_search_terms  # noqa: E402


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def validate_settings() -> int:
    settings = get_settings()
    if not settings.gerpgo_access_token and (not settings.gerpgo_app_id or not settings.gerpgo_app_key):
        fail("请先配置 GERPGO_APP_ID 和 GERPGO_APP_KEY，或设置 GERPGO_ACCESS_TOKEN")
    if settings.gerpgo_access_token and _looks_like_placeholder(settings.gerpgo_access_token):
        fail("GERPGO_ACCESS_TOKEN 仍是示例值")
    if settings.gerpgo_app_id and _looks_like_placeholder(settings.gerpgo_app_id):
        fail("GERPGO_APP_ID 仍是示例值")
    if settings.gerpgo_app_key and _looks_like_placeholder(settings.gerpgo_app_key):
        fail("GERPGO_APP_KEY 仍是示例值")
    if not settings.market_ids:
        fail("GERPGO_MARKET_IDS 未配置")
    return settings.market_ids[0]


def latest_success_run(source: str, market_id: int, start_text: str, end_text: str) -> SyncRun | None:
    with SessionLocal() as db:
        return db.execute(
            select(SyncRun)
            .where(
                SyncRun.source == source,
                SyncRun.market_id == market_id,
                SyncRun.period_start == start_text,
                SyncRun.period_end == end_text,
                SyncRun.status == "success",
            )
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(1)
        ).scalar_one_or_none()


def prune_older_rows(model: Any, source: str, market_id: int, start_text: str, end_text: str) -> int:
    run = latest_success_run(source, market_id, start_text, end_text)
    if run is None:
        return 0

    with SessionLocal() as db:
        result = db.execute(
            delete(model).where(
                model.market_id == market_id,
                model.data_date >= start_text,
                model.data_date <= end_text,
                model.synced_at < run.started_at,
            )
        )
        db.commit()
        return int(result.rowcount or 0)


def count_rows(model: Any, market_id: int, start_text: str, end_text: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            select(
                func.count(model.id),
                func.min(model.data_date),
                func.max(model.data_date),
            ).where(
                model.market_id == market_id,
                model.data_date >= start_text,
                model.data_date <= end_text,
            )
        ).one()
        return {"rows": int(row[0] or 0), "min_date": row[1], "max_date": row[2]}


async def run_sync(days: int, count: int, max_pages: int) -> None:
    if days < 1 or days > 60:
        fail("days 必须在 1 到 60 之间")
    if count < 1 or count > 50:
        fail("count 必须在 1 到 50 之间")
    if max_pages < 1 or max_pages > 3:
        fail("max_pages 必须在 1 到 3 之间")

    market_id = validate_settings()
    init_db()

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()

    with SessionLocal() as db:
        keyword_result = await sync_sp_keywords(
            db=db,
            market_id=market_id,
            start_date=start_date,
            end_date=end_date,
            count=count,
            max_pages=max_pages,
        )

    keyword_pruned = prune_older_rows(SpKeywordMetric, "sp_keywords", market_id, start_text, end_text)

    with SessionLocal() as db:
        search_term_result = await sync_sp_search_terms(
            db=db,
            market_id=market_id,
            start_date=start_date,
            end_date=end_date,
            count=count,
            max_pages=max_pages,
        )

    search_term_pruned = prune_older_rows(SpSearchTermMetric, "sp_search_terms", market_id, start_text, end_text)

    print(
        json.dumps(
            {
                "status": "success",
                "market_id": market_id,
                "period_start": start_text,
                "period_end": end_text,
                "keyword_sync": keyword_result,
                "search_term_sync": search_term_result,
                "pruned_old_rows": {
                    "sp_keyword_metrics": keyword_pruned,
                    "sp_search_term_metrics": search_term_pruned,
                },
                "current_rows": {
                    "sp_keyword_metrics": count_rows(SpKeywordMetric, market_id, start_text, end_text),
                    "sp_search_term_metrics": count_rows(SpSearchTermMetric, market_id, start_text, end_text),
                },
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="同步近 30 天真实 SP 关键词和搜索词数据")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(run_sync(days=args.days, count=args.count, max_pages=args.max_pages))


if __name__ == "__main__":
    main()
