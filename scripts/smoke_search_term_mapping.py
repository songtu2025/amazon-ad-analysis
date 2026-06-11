import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.sync_service import _search_term_metric_from_row  # noqa: E402


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


def main() -> None:
    raw_row = {
        "id": "TASK024-ROW-1",
        "marketId": 1,
        "campaignId": "TASK024-CAMPAIGN",
        "campaignName": "TASK024 Campaign",
        "groupId": "TASK024-GROUP",
        "groupName": "TASK024 Group",
        "targetId": "TASK024-TARGET-ID",
        "targetingText": "kids sunglasses",
        "targetingType": "phrase",
        "query": "kids sunglasses for boys",
        "createDate": "2026-06-01",
        "impressions": 100,
        "clicks": 10,
        "cost": 12.5,
        "adsOrders": 2,
        "adsSales": 50.0,
        "ctr": 0.1,
        "cpc": 1.25,
        "cvr": 0.2,
        "acos": 0.25,
        "roas": 4.0,
    }
    metric = _search_term_metric_from_row(raw_row, datetime.now())
    checks = {
        "search_term_from_query": metric.search_term == "kids sunglasses for boys",
        "keyword_text_from_targeting_text": metric.keyword_text == "kids sunglasses",
        "keyword_id_from_target_id": metric.keyword_id == "TASK024-TARGET-ID",
        "match_type_from_targeting_type": metric.match_type == "phrase",
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail(
            "搜索词字段映射异常："
            + ", ".join(missing)
            + f"；actual search_term={metric.search_term!r}, keyword_text={metric.keyword_text!r}, keyword_id={metric.keyword_id!r}, match_type={metric.match_type!r}"
        )
    hits = find_forbidden_keys(raw_row)
    if hits:
        fail("发现自动执行广告动作字段：" + ", ".join(hits))
    print(json.dumps({"status": "success", "checked": list(checks.keys())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
