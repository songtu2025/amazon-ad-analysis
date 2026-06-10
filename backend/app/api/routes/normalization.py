ANOMALY_TYPE_ALIASES = {
    "impressions_drop": "impression_low",
}
ANOMALY_TYPES = {
    "spend_spike",
    "acos_worse",
    "clicks_no_orders",
    "search_term_clicks_no_orders",
    "cvr_drop",
    "impression_low",
    "inventory_goal_conflict",
}


def normalize_anomaly_type(value: str | None) -> str | None:
    if not value:
        return value
    return ANOMALY_TYPE_ALIASES.get(value, value)


def is_valid_anomaly_type(value: str | None) -> bool:
    normalized = normalize_anomaly_type(value)
    return normalized is None or normalized in ANOMALY_TYPES
