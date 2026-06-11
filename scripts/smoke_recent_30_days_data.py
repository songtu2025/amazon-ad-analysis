import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ad_metrics import SpKeywordMetric, SpSearchTermMetric  # noqa: E402
from app.models.sync import SyncRun  # noqa: E402


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


def fail(message: str) -> None:
    print(json.dumps({"status": "failed", "reason": message}, ensure_ascii=False))
    sys.exit(1)


def count_metric_rows(model: Any, market_id: int, start_text: str, end_text: str) -> dict[str, Any]:
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


def count_non_empty_search_terms(market_id: int, start_text: str, end_text: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            select(
                func.count(SpSearchTermMetric.id),
                func.count(func.nullif(func.trim(SpSearchTermMetric.search_term), "")),
                func.count(func.distinct(func.nullif(func.trim(SpSearchTermMetric.search_term), ""))),
            ).where(
                SpSearchTermMetric.market_id == market_id,
                SpSearchTermMetric.data_date >= start_text,
                SpSearchTermMetric.data_date <= end_text,
            )
        ).one()
        return {
            "rows": int(row[0] or 0),
            "non_empty_search_terms": int(row[1] or 0),
            "distinct_search_terms": int(row[2] or 0),
        }


def latest_run(source: str, market_id: int, start_text: str, end_text: str) -> SyncRun | None:
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


def latest_complete_period(market_id: int) -> tuple[str, str]:
    with SessionLocal() as db:
        keyword_runs = db.execute(
            select(SyncRun)
            .where(
                SyncRun.source == "sp_keywords",
                SyncRun.market_id == market_id,
                SyncRun.status == "success",
            )
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(20)
        ).scalars().all()

        for keyword_run in keyword_runs:
            search_term_run = db.execute(
                select(SyncRun)
                .where(
                    SyncRun.source == "sp_search_terms",
                    SyncRun.market_id == market_id,
                    SyncRun.period_start == keyword_run.period_start,
                    SyncRun.period_end == keyword_run.period_end,
                    SyncRun.status == "success",
                )
                .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if search_term_run is not None:
                return keyword_run.period_start, keyword_run.period_end

    fail("未找到 SP 关键词和 SP 搜索词共同成功同步的周期")


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if key in FORBIDDEN_ACTION_KEYS:
                hits.append(key_path)
            hits.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def main() -> None:
    init_db()
    settings = get_settings()
    if not settings.market_ids:
        fail("GERPGO_MARKET_IDS 未配置")

    market_id = settings.market_ids[0]
    start_text, end_text = latest_complete_period(market_id)

    keyword_rows = count_metric_rows(SpKeywordMetric, market_id, start_text, end_text)
    search_term_rows = count_metric_rows(SpSearchTermMetric, market_id, start_text, end_text)
    if keyword_rows["rows"] <= 0:
        fail("sp_keyword_metrics 未找到近 30 天真实数据")
    if search_term_rows["rows"] <= 0:
        fail("sp_search_term_metrics 未找到近 30 天真实数据")
    search_term_text_stats = count_non_empty_search_terms(market_id, start_text, end_text)
    if search_term_text_stats["non_empty_search_terms"] <= 0:
        fail("sp_search_term_metrics 近 30 天真实数据缺少非空用户搜索词，请先修复 query -> search_term 映射并回填")

    keyword_run = latest_run("sp_keywords", market_id, start_text, end_text)
    search_term_run = latest_run("sp_search_terms", market_id, start_text, end_text)
    if keyword_run is None:
        fail("未找到近 30 天 SP 关键词成功同步记录")
    if search_term_run is None:
        fail("未找到近 30 天 SP 搜索词成功同步记录")

    raw_paths = [keyword_run.raw_path, search_term_run.raw_path]
    missing_raw = [path for path in raw_paths if not path or not Path(path).exists()]
    if missing_raw:
        fail("原始响应文件缺失：" + ", ".join(str(path) for path in missing_raw))

    client = TestClient(app)
    dashboard = client.get(
        "/api/dashboard/health",
        params={"market_id": market_id, "start_date": start_text, "end_date": end_text},
    )
    if dashboard.status_code != 200:
        fail(f"dashboard health 返回状态码 {dashboard.status_code}")
    dashboard_payload = dashboard.json()
    if dashboard_payload.get("overview", {}).get("metric_rows", 0) <= 0:
        fail("dashboard 未读取到近 30 天指标数据")

    forbidden_hits = find_forbidden_keys(dashboard_payload)
    if forbidden_hits:
        fail("dashboard payload 发现自动执行广告动作字段：" + ", ".join(forbidden_hits))

    print(
        json.dumps(
            {
                "status": "success",
                "market_id": market_id,
                "period_start": start_text,
                "period_end": end_text,
                "sp_keyword_metrics": keyword_rows,
                "sp_search_term_metrics": search_term_rows,
                "search_term_text_stats": search_term_text_stats,
                "raw_paths": raw_paths,
                "dashboard_metric_rows": dashboard_payload["overview"]["metric_rows"],
                "checked": [
                    "keyword_rows",
                    "search_term_rows",
                    "non_empty_search_terms",
                    "sync_runs",
                    "raw_payload_files",
                    "dashboard_30_days",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
