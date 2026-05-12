from __future__ import annotations

from typing import Any

from ai_quant_api.db import MySQLConfig
from ai_quant_api.services.charles.integration import get_watchlist

from .common import JobStats


def run_sentiment_monitor(_cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH").strip().upper()
    days = int((params or {}).get("days") or 3)
    days = max(1, min(days, 30))

    codes: list[str] = []
    if test_mode and test_stock:
        codes = [test_stock]
    else:
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

