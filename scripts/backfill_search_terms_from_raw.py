import json
import sys
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.models.ad_metrics import SpSearchTermMetric  # noqa: E402
from app.models.sync import SyncRun  # noqa: E402
from app.services.sync_service import _first_string  # noqa: E402


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def extract_rows(payload: Any) -> Iterable[dict[str, Any]]:
    pages = payload if isinstance(payload, list) else [payload]
    for page in pages:
        if not isinstance(page, dict):
            continue
        data = page.get("data") or page.get("list") or page.get("records") or page.get("rows") or []
        if isinstance(data, dict):
            data = data.get("list") or data.get("records") or data.get("rows") or data.get("data") or []
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    yield row


def latest_search_term_run(db) -> SyncRun:
    run = db.execute(
        select(SyncRun)
        .where(SyncRun.source == "sp_search_terms", SyncRun.status == "success", SyncRun.raw_path.is_not(None))
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        fail("未找到带 raw_path 的 SP 搜索词成功同步记录")
    return run


def main() -> None:
    with SessionLocal() as db:
        run = latest_search_term_run(db)
        raw_path = Path(str(run.raw_path))
        if not raw_path.exists():
            fail(f"SP 搜索词 raw 文件不存在：{raw_path}")

        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_rows = list(extract_rows(payload))
        raw_by_id = {str(row.get("id")): row for row in raw_rows if row.get("id") not in (None, "")}
        if not raw_by_id:
            fail("SP 搜索词 raw 文件没有可按 id 匹配的行")

        metrics = db.execute(
            select(SpSearchTermMetric).where(
                SpSearchTermMetric.market_id == run.market_id,
                SpSearchTermMetric.data_date >= run.period_start,
                SpSearchTermMetric.data_date <= run.period_end,
            )
        ).scalars().all()

        matched = 0
        updated = 0
        for metric in metrics:
            if not metric.source_id:
                continue
            raw = raw_by_id.get(str(metric.source_id))
            if raw is None:
                continue
            matched += 1
            before = (metric.search_term, metric.keyword_text, metric.keyword_id, metric.match_type)
            metric.search_term = _first_string(raw, "searchTerm", "query") or metric.search_term
            metric.keyword_text = _first_string(raw, "keywordText", "targetingText") or metric.keyword_text
            metric.keyword_id = _first_string(raw, "keywordId", "targetId") or metric.keyword_id
            metric.match_type = _first_string(raw, "matchType", "targetingType") or metric.match_type
            after = (metric.search_term, metric.keyword_text, metric.keyword_id, metric.match_type)
            if after != before:
                updated += 1

        db.commit()

        non_empty = db.execute(
            select(SpSearchTermMetric)
            .where(
                SpSearchTermMetric.market_id == run.market_id,
                SpSearchTermMetric.data_date >= run.period_start,
                SpSearchTermMetric.data_date <= run.period_end,
                SpSearchTermMetric.search_term.is_not(None),
            )
            .limit(5)
        ).scalars().all()
        sample_terms = [row.search_term for row in non_empty if row.search_term]

        print(
            json.dumps(
                {
                    "status": "success",
                    "market_id": run.market_id,
                    "period_start": run.period_start,
                    "period_end": run.period_end,
                    "raw_rows": len(raw_rows),
                    "db_rows": len(metrics),
                    "matched_rows": matched,
                    "updated_rows": updated,
                    "sample_search_terms": sample_terms,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
