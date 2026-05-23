from __future__ import annotations

from typing import Any

from core.db import MySQLConfig
from core.data import get_watchlist
from core.jobs.common import JobStats
from core.jobs.domains.stock_group import get_stock_codes_by_scope, ensure_stock_group_tables


def run_sentiment_monitor(_cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    days = max(1, min(30, int((params or {}).get("days") or 3)))
    scope_type = str((params or {}).get("scope_type") or "watchlist").strip().lower()
    group_id = int((params or {}).get("group_id") or 0)

    codes: list[str] = []
    if scope_type == "group":
        ensure_stock_group_tables()
        codes = get_stock_codes_by_scope("group", group_id=group_id)
    else:
        # watchlist / all 默认使用自选股
        wl = get_watchlist()
        items = wl.get("items") if isinstance(wl, dict) else []
        for it in items if isinstance(items, list) else []:
            code = str((it or {}).get("stock_code") or "").strip().upper()
            if code:
                codes.append(code)
    if not codes:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="file",
            fallback_chain=["file"],
            message="自选股为空，无法扫描",
        )

    msg = f"已触发扫描（days={days}，stocks={len(codes)}）"
    return JobStats(
        items_processed=len(codes),
        rows_written=0,
        failed_items=[],
        data_source_final="file",
        fallback_chain=["file"],
        message=msg,
    )

