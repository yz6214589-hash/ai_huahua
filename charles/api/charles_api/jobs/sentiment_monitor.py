from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from ..db import MySQLConfig, connect, execute, query_dict
from ..models import DataSource
from ..sentiment.runner import run_sentiment_run
from .common import JobStats


def run_sentiment_monitor(cfg: MySQLConfig, _mode: str | None, params: dict[str, Any] | None) -> JobStats:
    days = int((params or {}).get("days") or 3)
    use_llm = bool((params or {}).get("use_llm") is True)

    conn = connect(cfg)
    try:
        rows = query_dict(conn, "SELECT stock_code, NULL AS stock_name FROM trade_watchlist ORDER BY pinned DESC, sort_order ASC, updated_at DESC", ())
        stock_codes = [str(r.get("stock_code") or "") for r in rows if r.get("stock_code")]
        stock_names = [str(r.get("stock_name") or "") for r in rows]
        run_id = uuid4().hex
        execute(
            conn,
            """
            INSERT INTO trade_sentiment_run
              (run_id, trigger_type, stock_codes_json, stock_names_json, days, use_llm, status, created_at)
            VALUES
              (%s,%s,%s,%s,%s,%s,%s,NOW())
            """,
            (run_id, "schedule", json.dumps(stock_codes, ensure_ascii=False), json.dumps(stock_names, ensure_ascii=False), days, 1 if use_llm else 0, "waiting"),
        )
        conn.commit()
    finally:
        conn.close()

    run_sentiment_run(cfg, run_id)

    return JobStats(
        items_processed=len(stock_codes),
        rows_written=0,
        failed_items=[],
        data_source_final=DataSource.akshare,
        fallback_chain=[DataSource.akshare],
        message=None,
    )
