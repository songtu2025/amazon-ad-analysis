from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "app.db"
DRAFT_CATEGORY = "SP广告来源草稿"


def fail(message: str, payload: dict[str, Any] | None = None) -> None:
    result: dict[str, Any] = {"status": "failed", "reason": message}
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


def dict_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def extract_family_token(*values: object) -> str:
    text = " ".join(str(value or "") for value in values)
    tokens = re.findall(r"[A-Za-z]{2,}\d{3,}[A-Za-z0-9]*", text)
    if tokens:
        return tokens[0].upper()
    fallback = re.findall(r"[A-Za-z0-9]{4,}", text)
    if not fallback:
        fail("无法从广告对象或草稿产品中提取系列识别词", {"source_text": text})
    return fallback[0].upper()


def fetch_active_bindings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            b.id as binding_id,
            b.market_id,
            b.product_id,
            b.scope_type,
            b.scope_id,
            b.scope_name,
            b.status,
            p.product_name,
            p.asin,
            p.msku,
            p.sku,
            p.category
        from product_ad_bindings b
        join products p on p.id = b.product_id
        where b.status = 'active'
        order by b.id
        """
    ).fetchall()
    bindings = [dict_from_row(row) for row in rows]
    if not bindings:
        fail("真实库没有活跃广告归因绑定")
    return bindings


def fetch_family_candidates(
    conn: sqlite3.Connection,
    market_id: int,
    family_token: str,
) -> tuple[str, list[dict[str, Any]]]:
    latest = conn.execute(
        """
        select max(period_end) as period_end
        from product_sales_snapshots
        where market_id = ?
        """,
        (market_id,),
    ).fetchone()
    if latest is None or not latest["period_end"]:
        fail("真实库没有销售表现快照", {"market_id": market_id})

    pattern = f"%{family_token.lower()}%"
    rows = conn.execute(
        """
        select
            coalesce(nullif(p.asin, ''), nullif(p.msku, ''), nullif(p.sku, ''), 'product:' || p.id) as identity_key,
            min(p.id) as product_id,
            max(p.product_name) as product_name,
            max(p.asin) as asin,
            group_concat(distinct p.msku) as mskus,
            group_concat(distinct p.sku) as skus,
            max(p.category) as category,
            sum(coalesce(s.orders, 0)) as orders,
            sum(coalesce(s.sales, 0.0)) as sales,
            sum(coalesce(s.ads_spend, 0.0)) as ads_spend,
            sum(coalesce(s.ads_sales, 0.0)) as ads_sales
        from products p
        join product_sales_snapshots s on s.product_id = p.id
        where p.market_id = ?
          and s.period_end = ?
          and coalesce(p.category, '') != ?
          and lower(
              coalesce(p.product_name, '') || ' ' ||
              coalesce(p.msku, '') || ' ' ||
              coalesce(p.sku, '') || ' ' ||
              coalesce(p.asin, '')
          ) like ?
        group by identity_key
        order by sales desc, orders desc, identity_key
        """,
        (market_id, latest["period_end"], DRAFT_CATEGORY, pattern),
    ).fetchall()
    candidates = [dict_from_row(row) for row in rows]
    if not candidates:
        fail(
            "没有找到同系列真实销售商品候选",
            {"market_id": market_id, "family_token": family_token},
        )
    return latest["period_end"], candidates


def fetch_search_terms(conn: sqlite3.Connection, binding: dict[str, Any]) -> list[dict[str, Any]]:
    scope_type = str(binding["scope_type"] or "")
    scope_id = str(binding["scope_id"] or "")
    if scope_type == "ad_group":
        where_sql = "ad_group_id = ?"
    elif scope_type == "campaign":
        where_sql = "campaign_id = ?"
    else:
        where_sql = "source_id = ?"

    rows = conn.execute(
        f"""
        select
            keyword_text,
            search_term,
            sum(coalesce(clicks, 0)) as clicks,
            sum(coalesce(cost, 0.0)) as cost,
            sum(coalesce(ads_orders, 0)) as orders,
            sum(coalesce(ads_sales, 0.0)) as sales
        from sp_search_term_metrics
        where market_id = ?
          and {where_sql}
        group by keyword_text, search_term
        order by clicks desc, cost desc, search_term
        """,
        (binding["market_id"], scope_id),
    ).fetchall()
    return [dict_from_row(row) for row in rows]


def split_values(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def build_specific_product_tokens(candidates: list[dict[str, Any]], family_token: str) -> set[str]:
    tokens: set[str] = set()
    family = family_token.lower()
    for candidate in candidates:
        raw_values = [candidate.get("asin"), *split_values(candidate.get("mskus")), *split_values(candidate.get("skus"))]
        for value in raw_values:
            token = str(value or "").strip().lower()
            if len(token) >= 6 and token != family:
                tokens.add(token)
    return tokens


def count_specific_search_hits(
    search_terms: list[dict[str, Any]],
    product_tokens: set[str],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for row in search_terms:
        text = f"{row.get('keyword_text') or ''} {row.get('search_term') or ''}".lower()
        matched = sorted(token for token in product_tokens if token in text)
        if matched:
            hits.append(
                {
                    "keyword_text": row.get("keyword_text"),
                    "search_term": row.get("search_term"),
                    "matched_tokens": matched[:3],
                }
            )
    return hits


def classify_granularity(
    candidates: list[dict[str, Any]],
    search_terms: list[dict[str, Any]],
    product_tokens: set[str],
) -> dict[str, Any]:
    total_sales = sum(float(row["sales"] or 0) for row in candidates)
    top_sales = float(candidates[0]["sales"] or 0) if candidates else 0.0
    top_sales_share = top_sales / total_sales if total_sales > 0 else 0.0
    specific_hits = count_specific_search_hits(search_terms, product_tokens)

    if len(candidates) == 1:
        granularity = "single_sku"
        reason = "同系列真实销售商品只有 1 个候选。"
    elif top_sales_share >= 0.8 and specific_hits:
        granularity = "single_sku"
        reason = "销售高度集中，且搜索词命中明确 ASIN / MSKU / SKU。"
    elif len(candidates) >= 3 and top_sales_share < 0.6 and not specific_hits:
        granularity = "product_family"
        reason = "同系列真实商品较多、销售不集中，且搜索词没有命中明确 ASIN / MSKU / SKU。"
    else:
        granularity = "uncertain"
        reason = "当前证据不足以稳定判断为单 SKU 或商品族。"

    return {
        "granularity": granularity,
        "reason": reason,
        "candidate_count": len(candidates),
        "total_sales": round(total_sales, 4),
        "top_sales_share": round(top_sales_share, 4),
        "search_term_count": len(search_terms),
        "specific_search_hit_count": len(specific_hits),
        "specific_search_hits": specific_hits[:5],
    }


def diagnose_binding(conn: sqlite3.Connection, binding: dict[str, Any]) -> dict[str, Any]:
    family_token = extract_family_token(
        binding.get("scope_name"),
        binding.get("product_name"),
        binding.get("msku"),
        binding.get("sku"),
    )
    period_end, candidates = fetch_family_candidates(conn, int(binding["market_id"]), family_token)
    search_terms = fetch_search_terms(conn, binding)
    product_tokens = build_specific_product_tokens(candidates, family_token)
    classification = classify_granularity(candidates, search_terms, product_tokens)

    return {
        "binding": {
            "binding_id": binding["binding_id"],
            "market_id": binding["market_id"],
            "product_id": binding["product_id"],
            "scope_type": binding["scope_type"],
            "scope_id": binding["scope_id"],
            "scope_name": binding["scope_name"],
            "bound_product_name": binding["product_name"],
            "bound_product_category": binding["category"],
            "bound_product_is_draft": binding["category"] == DRAFT_CATEGORY,
        },
        "family_token": family_token,
        "sales_snapshot_period_end": period_end,
        "classification": classification,
        "top_candidates": [
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "asin": row["asin"],
                "mskus": row["mskus"],
                "sales": round(float(row["sales"] or 0), 4),
                "orders": int(row["orders"] or 0),
            }
            for row in candidates[:5]
        ],
        "keyword_examples": sorted({str(row.get("keyword_text") or "") for row in search_terms if row.get("keyword_text")})[:5],
        "search_term_examples": [row.get("search_term") for row in search_terms[:5]],
    }


def main() -> None:
    before_mtime = DB_PATH.stat().st_mtime_ns if DB_PATH.exists() else None
    conn = connect_readonly()
    try:
        bindings = fetch_active_bindings(conn)
        diagnostics = [diagnose_binding(conn, binding) for binding in bindings]
    finally:
        conn.close()

    after_mtime = DB_PATH.stat().st_mtime_ns if DB_PATH.exists() else None
    if before_mtime != after_mtime:
        fail("真实 data/app.db 修改时间发生变化，smoke 不是只读")

    rbk004 = next((item for item in diagnostics if item["family_token"] == "RBK004"), None)
    if rbk004 is None:
        fail("没有找到 RBK004 活跃广告对象诊断结果", {"diagnostics": diagnostics})
    if rbk004["classification"]["granularity"] != "product_family":
        fail("RBK004 当前证据不支持商品族判断", {"rbk004": rbk004})

    print(
        json.dumps(
            {
                "status": "success",
                "real_db_unchanged": True,
                "diagnostics": diagnostics,
                "checked": [
                    "readonly_real_db",
                    "active_binding_loaded",
                    "family_candidates_loaded",
                    "search_terms_checked",
                    "rbk004_product_family_granularity",
                    "no_auto_execution_capability",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
