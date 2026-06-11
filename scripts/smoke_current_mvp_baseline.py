import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_APP_PATH = PROJECT_ROOT / "frontend" / "src" / "App.tsx"
API_BASE_URL = os.environ.get("SMOKE_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
sys.path.insert(0, str(BACKEND_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.sync import SyncRun  # noqa: E402
from sqlalchemy import select  # noqa: E402

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


def request_json(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE_URL}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 200 or status >= 300:
                fail(f"{path} 返回状态码 {status}")
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        fail(f"{path} 返回状态码 {exc.code}")
    except URLError as exc:
        fail(f"{path} 无法访问：{exc.reason}")
    except json.JSONDecodeError as exc:
        fail(f"{path} 返回内容不是 JSON：{exc}")


def list_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("items", "data", "records", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return 0


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.{key}"
            if str(key).lower() in FORBIDDEN_ACTION_KEYS:
                hits.append(key_path)
            hits.extend(find_forbidden_keys(child, key_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def assert_no_auto_execution_fields(payloads: dict[str, Any]) -> None:
    hits: list[str] = []
    for name, payload in payloads.items():
        hits.extend(f"{name}:{hit}" for hit in find_forbidden_keys(payload))
    if hits:
        fail("API 返回中发现自动执行广告动作字段：" + ", ".join(hits))


def assert_frontend_workflow_markers() -> list[str]:
    source = FRONTEND_APP_PATH.read_text(encoding="utf-8")
    markers = {
        "dashboard_identity": "当前数据身份",
        "primary_task": "当前主任务",
        "anomaly_queue": "查看异常队列",
        "suggestion_trace": "建议详情与溯源",
        "manual_decision": "人工处理已记录",
        "review_flow": "处理记录与复盘",
        "product_settings": "产品目标与规则设置",
        "campaign_source": "广告活动来源 Top",
    }
    missing = [name for name, marker in markers.items() if marker not in source]
    if missing:
        fail("前端主工作流标记缺失：" + ", ".join(missing))
    return list(markers)


def workflow_status(*, active_binding_count: int, product_group_count: int, product_group_decision_count: int) -> str:
    if active_binding_count <= 0:
        return "needs_manual_attribution"
    if product_group_count <= 0:
        return "needs_product_search_terms"
    if product_group_decision_count <= 0:
        return "needs_group_decision"
    return "ready_for_review"


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


def main() -> None:
    init_db()
    settings = get_settings()
    if not settings.market_ids:
        fail("GERPGO_MARKET_IDS 未配置")

    market_id = settings.market_ids[0]
    start_text, end_text = latest_complete_period(market_id)
    params = {"market_id": market_id, "start_date": start_text, "end_date": end_text}

    health = request_json("/health")
    if health.get("status") != "ok":
        fail("/health 未返回 status=ok")

    dashboard = request_json("/api/dashboard/health", params)
    overview = dashboard.get("overview") if isinstance(dashboard, dict) else None
    if not isinstance(overview, dict) or int(overview.get("metric_rows") or 0) <= 0:
        fail("dashboard 未读取到真实指标数据")

    market = dashboard.get("market")
    if not isinstance(market, dict) or not market.get("market_name"):
        fail("dashboard 未返回真实店铺名称")

    if not dashboard.get("data_sources"):
        fail("dashboard 未返回数据来源")
    if not dashboard.get("top_campaigns"):
        fail("dashboard 未返回广告活动来源 Top")

    product_binding = dashboard.get("product_binding")
    if not isinstance(product_binding, dict) or int(product_binding.get("total_rows") or 0) <= 0:
        fail("dashboard 未返回产品绑定统计")

    bindings = request_json("/api/products/ad-bindings", {"market_id": market_id})
    if not isinstance(bindings, list):
        fail("产品归因规则接口返回格式异常")
    active_bindings = [item for item in bindings if isinstance(item, dict) and item.get("status") == "active"]
    current_workflow: dict[str, Any] = {
        "workflow_status": "needs_manual_attribution",
        "active_binding_count": len(active_bindings),
        "product_id": None,
        "bound_search_term_rows": 0,
        "product_group_count": 0,
        "product_group_decision_count": 0,
    }
    if active_bindings:
        first_binding = active_bindings[0]
        product_id = int(first_binding.get("product_id") or 0)
        if product_id <= 0:
            fail(f"归因规则缺少有效 product_id：{first_binding}")
        product_params = {**params, "product_id": product_id}
        readiness = request_json("/api/search-terms/product-readiness", product_params)
        readiness_summary = readiness.get("summary") if isinstance(readiness, dict) else None
        if not isinstance(readiness_summary, dict):
            fail(f"产品维度就绪汇总格式异常：{readiness}")
        product_analysis = request_json("/api/search-terms/analysis", product_params)
        product_groups = product_analysis.get("group_summary") if isinstance(product_analysis, dict) else None
        if not isinstance(product_groups, list):
            fail("产品维度搜索词归类组格式异常")
        product_group_decisions = request_json(
            "/api/search-terms/group-decisions",
            {"market_id": market_id, "product_id": product_id},
        )
        if not isinstance(product_group_decisions, list):
            fail("产品级组判断记录接口返回格式异常")
        current_workflow = {
            "workflow_status": workflow_status(
                active_binding_count=len(active_bindings),
                product_group_count=len(product_groups),
                product_group_decision_count=len(product_group_decisions),
            ),
            "active_binding_count": len(active_bindings),
            "product_id": product_id,
            "bound_search_term_rows": int(readiness_summary.get("bound_search_term_rows") or 0),
            "product_group_count": len(product_groups),
            "product_group_decision_count": len(product_group_decisions),
        }

    payloads = {
        "dashboard": dashboard,
        "product_bindings": bindings,
        "anomalies": request_json("/api/anomalies", params),
        "suggestions": request_json("/api/suggestions", params),
        "decisions": request_json("/api/decisions", params),
        "reviews": request_json("/api/reviews"),
    }
    assert_no_auto_execution_fields(payloads)

    anomaly_count = list_count(payloads["anomalies"])
    suggestion_count = list_count(payloads["suggestions"])
    if anomaly_count <= 0:
        fail("异常队列没有可验收记录")
    if suggestion_count <= 0:
        fail("AI 建议队列没有可验收记录")

    frontend_checks = assert_frontend_workflow_markers()

    bound_rows = int(product_binding.get("bound_rows") or 0)
    total_rows = int(product_binding.get("total_rows") or 0)
    baseline_gaps: list[str] = []
    if current_workflow["active_binding_count"] <= 0 or bound_rows <= 0:
        baseline_gaps.append("产品绑定为 0，下一步应进入产品与广告归因闭环")
    elif int(current_workflow["product_group_count"] or 0) <= 0:
        baseline_gaps.append("当前已确认归因，但产品维度搜索词归类组为空，需要复核产品归因与搜索词回填")
    elif int(current_workflow["product_group_decision_count"] or 0) <= 0:
        baseline_gaps.append("当前产品级组判断未保存，需要运营在产品维度搜索词分析下人工记录产品级组判断")
    if list_count(payloads["decisions"]) <= 0:
        baseline_gaps.append("当前真实库暂无人工处理记录，需要运营跑一次人工确认流程")
    if list_count(payloads["reviews"]) <= 0:
        baseline_gaps.append("当前真实库暂无复盘记录，需要在人工处理后补 7 天 / 14 天复盘")

    if current_workflow["active_binding_count"] <= 0:
        next_task_recommended = "产品与广告归因闭环"
    elif int(current_workflow["product_group_decision_count"] or 0) <= 0:
        next_task_recommended = "人工保存产品级组判断后的真实复盘验收"
    elif list_count(payloads["decisions"]) <= 0:
        next_task_recommended = "异常人工处理与动作记录真实演练"
    elif list_count(payloads["reviews"]) <= 0:
        next_task_recommended = "人工处理后的复盘验收"
    else:
        next_task_recommended = "当前 MVP 基线复核通过"

    print(
        json.dumps(
            {
                "status": "success",
                "period": params,
                "market": market,
                "overview": {
                    "metric_rows": overview.get("metric_rows"),
                    "acos": overview.get("acos"),
                    "orders": overview.get("orders"),
                    "sales": overview.get("sales"),
                    "pending_suggestion_count": overview.get("pending_suggestion_count"),
                },
                "product_binding": product_binding,
                "current_workflow": current_workflow,
                "counts": {
                    "anomalies": anomaly_count,
                    "suggestions": suggestion_count,
                    "decisions": list_count(payloads["decisions"]),
                    "reviews": list_count(payloads["reviews"]),
                    "top_campaigns": len(dashboard.get("top_campaigns") or []),
                },
                "frontend_checks": frontend_checks,
                "baseline_gaps": baseline_gaps,
                "next_task_recommended": next_task_recommended,
                "checked": [
                    "real_dashboard_data",
                    "market_identity",
                    "campaign_sources",
                    "anomaly_queue",
                    "ai_suggestion_queue",
                    "current_product_workflow",
                    "manual_decision_api",
                    "review_api",
                    "frontend_main_workflow",
                    "no_auto_execution_fields",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
