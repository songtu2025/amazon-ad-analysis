from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "app.db"
TEST_MARKERS = ("DEMO", "SMOKE", "TASK")


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1)


def connect_readonly() -> sqlite3.Connection:
    if not DB_PATH.exists():
        fail("真实 data/app.db 不存在")
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def is_test_object(row: sqlite3.Row) -> bool:
    text = " ".join(
        str(row[key] or "")
        for key in ["asin", "msku", "sku", "product_name"]
        if key in row.keys()
    ).upper()
    return any(marker in text for marker in TEST_MARKERS)


def dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def fetch_period(conn: sqlite3.Connection) -> dict[str, str]:
    row = conn.execute(
        """
        select min(data_date) as period_start, max(data_date) as period_end
        from sp_keyword_metrics
        where product_id is not null
        """
    ).fetchone()
    if row is None or not row["period_start"] or not row["period_end"]:
        fail("真实库没有已归因 SP 关键词指标")
    return {"start": row["period_start"], "end": row["period_end"]}


def fetch_ad_object_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        with metrics as (
            select
                product_id,
                market_id,
                sum(coalesce(impressions, 0)) as impressions,
                sum(coalesce(clicks, 0)) as clicks,
                sum(coalesce(cost, 0.0)) as cost,
                sum(coalesce(ads_orders, 0)) as orders,
                sum(coalesce(ads_sales, 0.0)) as sales
            from sp_keyword_metrics
            where product_id is not null
            group by product_id, market_id
        ),
        bindings as (
            select product_id, count(*) as active_binding_count
            from product_ad_bindings
            where status = 'active'
            group by product_id
        )
        select
            p.id as product_id,
            p.asin,
            p.msku,
            p.sku,
            p.product_name,
            p.market_id,
            coalesce(b.active_binding_count, 0) as active_binding_count,
            coalesce(m.impressions, 0) as impressions,
            coalesce(m.clicks, 0) as clicks,
            coalesce(m.cost, 0.0) as cost,
            coalesce(m.orders, 0) as orders,
            coalesce(m.sales, 0.0) as sales,
            g.goal_type,
            r.min_clicks,
            r.min_spend,
            r.min_orders,
            r.target_acos,
            r.target_cvr,
            r.max_cpc,
            r.inventory_guard
        from products p
        join metrics m on m.product_id = p.id
        left join bindings b on b.product_id = p.id
        left join product_goals g on g.product_id = p.id
        left join product_rules r on r.product_id = p.id
        where coalesce(b.active_binding_count, 0) > 0
          and coalesce(m.cost, 0) > 0
          and coalesce(m.sales, 0) > 0
        order by m.cost desc, p.id asc
        """
    ).fetchall()
    candidates = [dict_from_row(row) for row in rows if not is_test_object(row)]
    if not candidates:
        fail("没有找到真实广告调优对象：需要活跃归因规则和 SP 指标")
    return candidates


def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    clicks = int(candidate["clicks"] or 0)
    cost = float(candidate["cost"] or 0)
    sales = float(candidate["sales"] or 0)
    orders = int(candidate["orders"] or 0)
    acos = cost / sales if sales > 0 else 0.0

    missing: list[str] = []
    if not candidate.get("goal_type"):
        missing.append("product_goal")
    if candidate.get("target_acos") is None:
        missing.append("target_acos")

    product = {
        "product_id": candidate["product_id"],
        "product_name": candidate["product_name"],
        "asin": candidate["asin"],
        "msku": candidate["msku"],
        "market_id": candidate["market_id"],
        "active_binding_count": candidate["active_binding_count"],
    }
    metrics = {
        "clicks": clicks,
        "cost": round(cost, 4),
        "orders": orders,
        "sales": round(sales, 4),
        "acos": round(acos, 4),
    }

    if missing:
        return {
            "workflow_status": "needs_manual_goal_rule",
            "queue_ready": False,
            "product": product,
            "metrics": metrics,
            "missing": missing,
            "manual_next_step": "运营需要在前端产品中心为该广告调优对象保存产品目标和目标 ACOS 等规则门槛。",
        }

    goal_type = str(candidate["goal_type"])
    target_acos = float(candidate["target_acos"])
    min_clicks = int(candidate["min_clicks"] or 0)
    min_spend = float(candidate["min_spend"] or 0)
    rule = {
        "goal_type": goal_type,
        "target_acos": round(target_acos, 4),
        "min_clicks": min_clicks,
        "min_spend": round(min_spend, 4),
    }

    if goal_type not in {"profit", "stop_loss"}:
        return {
            "workflow_status": "configured_but_not_acos_goal",
            "queue_ready": False,
            "product": product,
            "metrics": metrics,
            "rule": rule,
            "reason": "当前 ACOS 异常规则只针对 profit / stop_loss 产品目标。",
        }
    if clicks < min_clicks or cost < min_spend:
        return {
            "workflow_status": "below_rule_threshold",
            "queue_ready": False,
            "product": product,
            "metrics": metrics,
            "rule": rule,
            "reason": "当前点击或花费未达到人工规则门槛，不应入队。",
        }
    if acos <= target_acos:
        return {
            "workflow_status": "no_anomaly_under_current_rule",
            "queue_ready": False,
            "product": product,
            "metrics": metrics,
            "rule": rule,
            "reason": "当前 ACOS 未高于人工目标 ACOS，不应入队。",
        }
    return {
        "workflow_status": "ready_for_anomaly_queue",
        "queue_ready": True,
        "product": product,
        "metrics": metrics,
        "rule": rule,
        "reason": "当前指标已高于人工目标 ACOS，运行异常生成后应进入待确认队列。",
    }


def main() -> None:
    before_mtime = DB_PATH.stat().st_mtime_ns if DB_PATH.exists() else None
    conn = connect_readonly()
    try:
        period = fetch_period(conn)
        candidates = fetch_ad_object_candidates(conn)
        evaluation = evaluate_candidate(candidates[0])
    finally:
        conn.close()

    after_mtime = DB_PATH.stat().st_mtime_ns if DB_PATH.exists() else None
    if before_mtime != after_mtime:
        fail("真实 data/app.db 修改时间发生变化，smoke 不是只读")

    print(
        json.dumps(
            {
                "status": "success",
                "real_db_unchanged": True,
                "period": period,
                "candidate_count": len(candidates),
                **evaluation,
                "checked": [
                    "readonly_real_db",
                    "real_ad_object_found",
                    "manual_goal_rule_gate",
                    "queue_readiness_explained",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
