from typing import Dict, List, Tuple


def filter_sort_paginate_proxies(
    proxies: List[Dict],
    protocol: str = "",
    country: str = "",
    source: str = "",
    status: str = "",
    sort_by: str = "speed_ms",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Dict], int, List[str]]:
    items = list(proxies)
    protocol = (protocol or "").lower()
    country = (country or "").upper()
    source = (source or "").strip()
    status = (status or "").lower()
    sort_by = sort_by or "speed_ms"
    sort_order = (sort_order or "asc").lower()

    if protocol and protocol != "all":
        items = [item for item in items if str(item.get("protocol", "")).lower() == protocol]
    if country:
        items = [item for item in items if str(item.get("country", "")).upper() == country]
    if source:
        items = [item for item in items if str(item.get("source", "")) == source]
    if status == "working":
        items = [item for item in items if item.get("is_working")]
    elif status == "failed":
        items = [item for item in items if not item.get("is_working")]

    sources = sorted({str(item.get("source", "")).strip() for item in proxies if str(item.get("source", "")).strip()})

    def sort_key(item: Dict):
        value = item.get(sort_by)
        if sort_by in {"speed_ms", "latency", "last_tested", "country", "protocol"}:
            return (value is None, value if value is not None else float("inf"))
        return str(value or "")

    reverse = sort_order == "desc"
    items = sorted(items, key=sort_key, reverse=reverse)

    total = len(items)
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total, sources
