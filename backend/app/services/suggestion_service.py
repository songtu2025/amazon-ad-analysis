import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.anomaly import AnomalyEvent
from app.models.suggestion import AiSuggestion


PLACEHOLDER_MODEL = "rule-placeholder"


def _load_json(value: str) -> dict[str, object]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _suggestion_level(rule_result: dict[str, object], anomaly: AnomalyEvent) -> str:
    value = rule_result.get("suggestion_level")
    if isinstance(value, str) and value:
        return value
    return "adoptable" if anomaly.severity == "high" else "small_test"


def _product_sales_snapshot_summary(evidence: dict[str, object]) -> str | None:
    snapshot = evidence.get("product_sales_snapshot")
    if not isinstance(snapshot, dict):
        return None
    parts = []
    for key, label in [
        ("sales", "销售额"),
        ("orders", "订单"),
        ("sessions", "Sessions"),
        ("net_profit", "净利"),
    ]:
        value = snapshot.get(key)
        if value is not None:
            parts.append(f"{label} {value}")
    return f"产品经营背景 {'，'.join(parts)}" if parts else None


def _evidence_summary(evidence: dict[str, object]) -> str:
    parts = []
    for key, label in [
        ("clicks", "点击"),
        ("cost", "花费"),
        ("orders", "订单"),
        ("sales", "销售额"),
        ("acos", "ACOS"),
        ("target_acos", "目标 ACOS"),
        ("cvr", "CVR"),
        ("target_cvr", "目标 CVR"),
        ("cpc", "CPC"),
        ("max_cpc", "最大 CPC"),
        ("impressions", "曝光"),
        ("min_impressions", "曝光门槛"),
        ("inventory_quantity", "当前库存"),
        ("inventory_guard", "库存阈值"),
    ]:
        value = evidence.get(key)
        if value is not None:
            parts.append(f"{label} {value}")
    snapshot_summary = _product_sales_snapshot_summary(evidence)
    if snapshot_summary:
        parts.append(snapshot_summary)
    return "，".join(parts) if parts else "暂无可用指标快照"


def _source_context(anomaly: AnomalyEvent, evidence: dict[str, object]) -> dict[str, object]:
    return {
        "product_id": anomaly.product_id,
        "market_id": anomaly.market_id,
        "product_goal": evidence.get("product_goal"),
        "object_type": anomaly.object_type,
        "object_id": anomaly.object_id,
        "object_name": anomaly.object_name,
        "campaign_id": evidence.get("campaign_id"),
        "campaign_name": evidence.get("campaign_name"),
        "ad_group_id": evidence.get("ad_group_id"),
        "ad_group_name": evidence.get("ad_group_name"),
        "keyword_id": evidence.get("keyword_id"),
        "keyword_text": evidence.get("keyword_text"),
        "search_term": evidence.get("search_term"),
        "match_type": evidence.get("match_type"),
        "product_sales_snapshot": evidence.get("product_sales_snapshot"),
        "period_start": anomaly.period_start,
        "period_end": anomaly.period_end,
    }


def _build_text(anomaly: AnomalyEvent, evidence: dict[str, object], suggestion_level: str) -> dict[str, str]:
    object_name = anomaly.object_name or anomaly.object_id or "未知对象"
    if anomaly.anomaly_type == "acos_worse":
        return {
            "title": f"ACOS 异常升高：{object_name}",
            "suggested_action": "优先检查该关键词的竞价和预算，利润款或止损款下建议小幅降竞价并观察。",
            "summary": "该关键词在当前周期内 ACOS 高于产品目标门槛。",
            "reasoning": "规则判断基于产品目标、目标 ACOS、点击量、花费和销售额；当前广告成本占销售额比例已经超过设定门槛。",
            "risk_note": "直接降竞价可能减少曝光和订单，建议先小幅调整并保留复盘记录。",
            "evidence_summary": _evidence_summary(evidence),
        }
    if anomaly.anomaly_type == "clicks_no_orders":
        return {
            "title": f"点击多无订单：{object_name}",
            "suggested_action": "检查搜索词相关性；无关词考虑否定，相关词先降竞价或加入观察。",
            "summary": "该关键词点击和花费达到门槛，但当前周期内没有广告订单。",
            "reasoning": "规则判断基于点击量、花费和订单数；样本已达到门槛但没有产生转化。",
            "risk_note": "如果这是核心词，不建议直接否定，应先检查 Listing、价格、库存和评价承接。",
            "evidence_summary": _evidence_summary(evidence),
        }
    if anomaly.anomaly_type == "spend_spike":
        return {
            "title": f"花费异常：{object_name}",
            "suggested_action": "检查预算分配和低效关键词；优先缩减高花费低转化对象，保留高转化词。",
            "summary": "该关键词花费达到门槛，但订单或 ACOS 表现与当前目标不匹配。",
            "reasoning": "规则判断基于花费、订单、销售额、ACOS 和产品规则门槛；当前投入产出不匹配，需要人工复核预算和竞价。",
            "risk_note": "直接缩减预算可能影响有效流量，建议先处理低效关键词并复盘 7 天表现。",
            "evidence_summary": _evidence_summary(evidence),
        }
    if anomaly.anomaly_type == "cvr_drop":
        return {
            "title": f"CVR 下滑：{object_name}",
            "suggested_action": "相关词先小幅降竞价并观察；核心词优先检查 Listing、价格、库存、Review 和主图承接。",
            "summary": "该关键词点击样本达到门槛，但 CVR 低于产品目标门槛。",
            "reasoning": "规则判断基于点击量、订单数、CVR 和产品目标 CVR；当前转化效率低于目标。",
            "risk_note": "CVR 低不一定只由广告造成，需结合 Listing 和库存等承接因素判断。",
            "evidence_summary": _evidence_summary(evidence),
        }
    if anomaly.anomaly_type == "impression_low":
        if suggestion_level == "observe":
            return {
                "title": f"曝光不足待观察：{object_name}",
                "suggested_action": "先加入观察，复核目标、预算和关键词重要性；样本不足时不直接提竞价或放量。",
                "summary": "该对象曝光不足，但没有明确投放状态异常，暂不建议马上动作。",
                "reasoning": "规则判断基于产品目标、曝光量和投放状态；当前更适合补充样本和人工复核，而不是直接扩大投放。",
                "risk_note": "样本不足时直接提竞价可能放大无效花费，应先观察或确认这是核心词。",
                "evidence_summary": _evidence_summary(evidence),
            }
        return {
            "title": f"曝光异常：{object_name}",
            "suggested_action": "检查投放状态、预算和竞价；核心词可小幅提高竞价，非核心词先观察。",
            "summary": "该关键词在放量、排名承接或测试目标下曝光不足，或投放状态存在异常。",
            "reasoning": "规则判断基于产品目标、曝光量、投放状态和竞价信息；当前流量获取不足。",
            "risk_note": "提高竞价可能推高花费，建议只对核心词小步测试并保留复盘记录。",
            "evidence_summary": _evidence_summary(evidence),
        }
    if anomaly.anomaly_type == "inventory_goal_conflict":
        return {
            "title": f"库存与投放目标冲突：{object_name}",
            "suggested_action": "先阻止放量类动作，复核库存、补货节奏和产品目标；库存恢复前只保留必要观察。",
            "summary": "该产品当前库存不高于库存阈值，不满足放量或排名承接目标的库存承接条件。",
            "reasoning": "规则判断基于产品目标、当前库存和库存阈值；库存不足时继续放量会放大断货和利润风险。",
            "risk_note": "这是硬规则阻断建议，系统不会改动广告，需要人工确认后处理。",
            "evidence_summary": _evidence_summary(evidence),
        }
    return {
        "title": f"广告异常：{object_name}",
        "suggested_action": "先人工复核规则证据，再决定采纳、修改后采纳、拒绝或加入观察。",
        "summary": "该对象命中了广告异常规则。",
        "reasoning": "建议基于规则输出和指标快照生成。",
        "risk_note": "占位建议不执行任何广告动作，需要人工确认。",
        "evidence_summary": _evidence_summary(evidence),
    }


def _recommended_manual_decision(suggestion_level: str) -> str:
    if suggestion_level == "blocked":
        return "reject"
    if suggestion_level == "observe":
        return "observe"
    if suggestion_level == "small_test":
        return "adopt_with_changes"
    return "adopt"


def generate_suggestions(
    db: Session,
    market_id: int | None = None,
    product_id: int | None = None,
    anomaly_type: str | None = None,
    status: str = "pending",
) -> dict[str, object]:
    filters = [AnomalyEvent.status == status]
    if market_id is not None:
        filters.append(AnomalyEvent.market_id == market_id)
    if product_id is not None:
        filters.append(AnomalyEvent.product_id == product_id)
    if anomaly_type:
        filters.append(AnomalyEvent.anomaly_type == anomaly_type)

    anomalies = db.execute(select(AnomalyEvent).where(*filters).order_by(AnomalyEvent.id)).scalars().all()
    existing = {
        suggestion.anomaly_event_id: suggestion
        for suggestion in db.execute(select(AiSuggestion)).scalars().all()
    }

    now = datetime.now()
    generated = 0
    for anomaly in anomalies:
        rule_result = _load_json(anomaly.rule_result_json)
        evidence = _load_json(anomaly.evidence_json)
        suggestion_level = _suggestion_level(rule_result, anomaly)
        text = _build_text(anomaly, evidence, suggestion_level)
        recommended_decision = _recommended_manual_decision(suggestion_level)
        source_trace = {
            "anomaly_event_id": anomaly.id,
            "anomaly_type": anomaly.anomaly_type,
            "recommended_manual_decision": recommended_decision,
            "source_context": _source_context(anomaly, evidence),
            "rule_result": rule_result,
            "evidence": evidence,
        }

        suggestion = existing.get(anomaly.id)
        if suggestion is None:
            suggestion = AiSuggestion(
                anomaly_event_id=anomaly.id,
                suggestion_level=suggestion_level,
                suggested_action=text["suggested_action"],
                title=text["title"],
                summary=text["summary"],
                reasoning=text["reasoning"],
                risk_note=text["risk_note"],
                evidence_summary=text["evidence_summary"],
                recommended_manual_decision=recommended_decision,
                source_trace_json=json.dumps(source_trace, ensure_ascii=False),
                ai_model=PLACEHOLDER_MODEL,
                created_at=now,
                updated_at=now,
            )
            db.add(suggestion)
        else:
            suggestion.suggestion_level = suggestion_level
            suggestion.suggested_action = text["suggested_action"]
            suggestion.title = text["title"]
            suggestion.summary = text["summary"]
            suggestion.reasoning = text["reasoning"]
            suggestion.risk_note = text["risk_note"]
            suggestion.evidence_summary = text["evidence_summary"]
            suggestion.recommended_manual_decision = recommended_decision
            suggestion.source_trace_json = json.dumps(source_trace, ensure_ascii=False)
            suggestion.ai_model = PLACEHOLDER_MODEL
            suggestion.updated_at = now
        generated += 1

    db.commit()
    return {
        "status": "success",
        "ai_model": PLACEHOLDER_MODEL,
        "suggestions_generated": generated,
    }
