from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
REAL_DB_PATH = PROJECT_ROOT / "data" / "app.db"
TEMP_DIR = Path(os.environ.get("TEMP", str(PROJECT_ROOT / "tmp"))) / "amazon_ad_analysis_task077"
TEMP_DB_PATH = TEMP_DIR / "app_task077.db"

sys.path.insert(0, str(BACKEND_ROOT))

from app.models.ad_metrics import SpKeywordMetric  # noqa: E402
from app.models.anomaly import AnomalyEvent  # noqa: E402
from app.models.product import Product, ProductAdBinding, ProductGoal, ProductRule  # noqa: E402
from app.models.suggestion import AiSuggestion  # noqa: E402
from app.services.rule_service import generate_acos_worse_anomalies  # noqa: E402
from app.services.suggestion_service import generate_suggestions  # noqa: E402


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

TEST_MARKERS = ("DEMO", "SMOKE", "TASK")


def fail(message: str, payload: dict[str, object] | None = None) -> None:
    result = {"status": "failed", "reason": message}
    if payload:
        result.update(payload)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(1)


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def load_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def object_has_test_marker(*values: object) -> bool:
    text = " ".join(str(value or "") for value in values).upper()
    return any(marker in text for marker in TEST_MARKERS)


def compact_product(product: Product) -> dict[str, object]:
    return {
        "product_id": product.id,
        "asin": product.asin,
        "msku": product.msku,
        "product_name": product.product_name,
        "market_id": product.market_id,
    }


def prepare_temp_db() -> int:
    if not REAL_DB_PATH.exists():
        fail("真实 data/app.db 不存在，无法做真实数据链路验收")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if TEMP_DB_PATH.exists():
        TEMP_DB_PATH.unlink()
    before_mtime = REAL_DB_PATH.stat().st_mtime_ns
    shutil.copy2(REAL_DB_PATH, TEMP_DB_PATH)
    return before_mtime


def selected_period(db) -> tuple[date, date]:
    min_date, max_date = db.execute(select(func.min(SpKeywordMetric.data_date), func.max(SpKeywordMetric.data_date))).one()
    if not min_date or not max_date:
        fail("真实库没有 SP 关键词指标，无法验收异常链路")
    return date.fromisoformat(str(min_date)), date.fromisoformat(str(max_date))


def select_real_ad_object(db, period_start: date, period_end: date) -> dict[str, Any]:
    clicks_sum = func.sum(func.coalesce(SpKeywordMetric.clicks, 0)).label("clicks")
    cost_sum = func.sum(func.coalesce(SpKeywordMetric.cost, 0.0)).label("cost")
    orders_sum = func.sum(func.coalesce(SpKeywordMetric.ads_orders, 0)).label("orders")
    sales_sum = func.sum(func.coalesce(SpKeywordMetric.ads_sales, 0.0)).label("sales")

    rows = db.execute(
        select(Product, clicks_sum, cost_sum, orders_sum, sales_sum)
        .join(SpKeywordMetric, SpKeywordMetric.product_id == Product.id)
        .where(
            SpKeywordMetric.product_id.is_not(None),
            SpKeywordMetric.data_date >= period_start.isoformat(),
            SpKeywordMetric.data_date <= period_end.isoformat(),
        )
        .group_by(Product.id)
        .having(cost_sum > 0, sales_sum > 0, clicks_sum > 0)
        .order_by(cost_sum.desc())
    ).all()

    for product, clicks, cost, orders, sales in rows:
        if object_has_test_marker(product.asin, product.msku, product.sku, product.product_name):
            continue
        binding_count = int(
            db.execute(
                select(func.count(ProductAdBinding.id)).where(
                    ProductAdBinding.product_id == product.id,
                    ProductAdBinding.status == "active",
                )
            ).scalar()
            or 0
        )
        return {
            "product": product,
            "metrics": {
                "clicks": int(clicks or 0),
                "cost": float(cost or 0.0),
                "orders": int(orders or 0),
                "sales": float(sales or 0.0),
                "acos": float(cost or 0.0) / float(sales or 1.0),
            },
            "active_binding_count": binding_count,
        }

    fail("没有找到带真实 SP 指标的非测试产品，无法验收真实广告调优对象链路")


def upsert_temp_goal_rule(db, product: Product, metrics: dict[str, Any]) -> dict[str, object]:
    now = datetime.now()
    original_goal = db.execute(select(ProductGoal).where(ProductGoal.product_id == product.id)).scalar_one_or_none()
    original_rule = db.execute(select(ProductRule).where(ProductRule.product_id == product.id)).scalar_one_or_none()
    target_acos = max(0.01, min(float(metrics["acos"]) * 0.5, float(metrics["acos"]) - 0.001))

    if original_goal is None:
        goal = ProductGoal(
            product_id=product.id,
            goal_type="profit",
            note="TASK-077 临时库链路验收，不写真实库",
            created_at=now,
            updated_at=now,
        )
        db.add(goal)
    else:
        original_goal.goal_type = "profit"
        original_goal.updated_at = now

    if original_rule is None:
        rule = ProductRule(
            product_id=product.id,
            min_clicks=1,
            min_spend=0.01,
            min_orders=0,
            target_acos=target_acos,
            target_cvr=None,
            max_cpc=None,
            inventory_guard=None,
            created_at=now,
            updated_at=now,
        )
        db.add(rule)
    else:
        original_rule.min_clicks = 1
        original_rule.min_spend = 0.01
        original_rule.target_acos = target_acos
        original_rule.updated_at = now

    db.commit()
    return {
        "real_had_goal": original_goal is not None,
        "real_had_rule": original_rule is not None,
        "temp_goal_type": "profit",
        "temp_target_acos": round(target_acos, 4),
    }


def assert_generated_anomaly(event: AnomalyEvent) -> dict[str, Any]:
    if object_has_test_marker(event.object_id, event.object_name, event.evidence_json, event.rule_result_json):
        fail("生成异常包含 DEMO/SMOKE/TASK 测试标记", {"anomaly_id": event.id, "object_name": event.object_name})
    evidence = load_json(event.evidence_json)
    rule_result = load_json(event.rule_result_json)
    if not evidence or not rule_result:
        fail("生成异常缺少 evidence_json 或 rule_result_json", {"anomaly_id": event.id})
    if evidence.get("acos") is None or evidence.get("target_acos") is None:
        fail("生成异常缺少 ACOS 或目标 ACOS 证据", {"evidence": evidence})
    return {"evidence": evidence, "rule_result": rule_result}


def assert_generated_suggestion(suggestion: AiSuggestion) -> dict[str, Any]:
    trace = load_json(suggestion.source_trace_json)
    if not suggestion.evidence_summary:
        fail("AI 建议缺少 evidence_summary", {"suggestion_id": suggestion.id})
    if not suggestion.recommended_manual_decision:
        fail("AI 建议缺少 recommended_manual_decision", {"suggestion_id": suggestion.id})
    if not trace.get("rule_result") or not trace.get("evidence"):
        fail("AI 建议缺少可溯源 source_trace_json", {"suggestion_id": suggestion.id, "trace": trace})
    forbidden_hits = find_forbidden_keys(
        {
            "suggestion": {
                "suggested_action": suggestion.suggested_action,
                "evidence_summary": suggestion.evidence_summary,
                "source_trace_json": trace,
            }
        }
    )
    if forbidden_hits:
        fail("AI 建议包含自动执行广告动作字段", {"hits": forbidden_hits})
    return {
        "suggestion_id": suggestion.id,
        "suggestion_level": suggestion.suggestion_level,
        "recommended_manual_decision": suggestion.recommended_manual_decision,
        "evidence_summary": suggestion.evidence_summary,
    }


def main() -> None:
    real_mtime_before = prepare_temp_db()
    engine = create_engine(f"sqlite:///{TEMP_DB_PATH.as_posix()}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        period_start, period_end = selected_period(db)
        candidate = select_real_ad_object(db, period_start, period_end)
        product: Product = candidate["product"]
        metrics = candidate["metrics"]
        product_snapshot = compact_product(product)
        temp_rule_state = upsert_temp_goal_rule(db, product, metrics)

        anomaly_result = generate_acos_worse_anomalies(
            db=db,
            market_id=product.market_id,
            start_date=period_start,
            end_date=period_end,
        )
        if int(anomaly_result.get("events_created") or 0) <= 0:
            fail("临时库未生成真实 ACOS 异常", {"anomaly_result": anomaly_result, "product": product_snapshot, "metrics": metrics})

        event = db.execute(
            select(AnomalyEvent)
            .where(
                AnomalyEvent.product_id == product.id,
                AnomalyEvent.market_id == product.market_id,
                AnomalyEvent.anomaly_type == "acos_worse",
                AnomalyEvent.period_start == period_start.isoformat(),
                AnomalyEvent.period_end == period_end.isoformat(),
                AnomalyEvent.status == "pending",
            )
            .order_by(AnomalyEvent.id.desc())
        ).scalars().first()
        if event is None:
            fail("临时库未找到刚生成的 ACOS 异常", {"product": product_snapshot})
        anomaly_trace = assert_generated_anomaly(event)

        suggestion_result = generate_suggestions(
            db=db,
            market_id=product.market_id,
            product_id=product.id,
            anomaly_type="acos_worse",
            status="pending",
        )
        if int(suggestion_result.get("suggestions_generated") or 0) <= 0:
            fail("临时库未生成 AI 建议", {"suggestion_result": suggestion_result})

        suggestion = db.execute(
            select(AiSuggestion).where(AiSuggestion.anomaly_event_id == event.id).order_by(AiSuggestion.id.desc())
        ).scalars().first()
        if suggestion is None:
            fail("临时库未找到刚生成异常对应的 AI 建议", {"anomaly_id": event.id})
        suggestion_trace = assert_generated_suggestion(suggestion)
        event_snapshot = {
            "anomaly_id": event.id,
            "anomaly_type": event.anomaly_type,
            "severity": event.severity,
        }
        metrics_snapshot = {
            "clicks": metrics["clicks"],
            "cost": round(metrics["cost"], 4),
            "orders": metrics["orders"],
            "sales": round(metrics["sales"], 4),
            "acos": round(metrics["acos"], 4),
        }
        evidence_keys = sorted(anomaly_trace["evidence"].keys())
        rule_result_keys = sorted(anomaly_trace["rule_result"].keys())
    finally:
        db.close()
        engine.dispose()

    real_mtime_after = REAL_DB_PATH.stat().st_mtime_ns
    if real_mtime_after != real_mtime_before:
        fail("真实 data/app.db 修改时间发生变化，验收脚本可能写入了真实库")

    print(
        json.dumps(
            {
                "status": "success",
                "real_db_unchanged": True,
                "temp_db_path": str(TEMP_DB_PATH),
                "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
                "real_precondition": {
                    "active_binding_count": candidate["active_binding_count"],
                    "real_had_goal": temp_rule_state["real_had_goal"],
                    "real_had_rule": temp_rule_state["real_had_rule"],
                },
                "temp_chain": {
                    "product": product_snapshot,
                    "metrics": metrics_snapshot,
                    "temp_goal_rule": {
                        "goal_type": temp_rule_state["temp_goal_type"],
                        "target_acos": temp_rule_state["temp_target_acos"],
                    },
                    **event_snapshot,
                    "suggestion": suggestion_trace,
                    "evidence_keys": evidence_keys,
                    "rule_result_keys": rule_result_keys,
                },
                "checked": [
                    "real_db_copied_to_temp",
                    "real_ad_object_metrics_used",
                    "temp_goal_rule_only",
                    "acos_worse_anomaly_generated",
                    "ai_suggestion_generated",
                    "source_trace_present",
                    "real_db_not_modified",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
