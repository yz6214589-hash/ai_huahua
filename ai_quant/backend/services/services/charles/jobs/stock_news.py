from __future__ import annotations

from datetime import datetime
from typing import Any

from db import MySQLConfig, connect, executemany

from common import JobStats, normalize_stock_code


_INSERT_SQL = """
INSERT INTO trade_stock_news
(stock_code, published_at, news_type, title, content)
VALUES (%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
news_type=VALUES(news_type),
title=VALUES(title),
content=VALUES(content)
"""


def _infer_exchange(code_num: str) -> str:
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


def _get_stock_list(test_mode: bool, test_stock: str, max_stocks: int) -> list[str]:
    if test_mode:
        s = normalize_stock_code(test_stock)
        return [s] if s else []
    import akshare as ak

    df = ak.stock_zh_a_spot_em()
    if df is None or len(df) == 0:
        return []
    out: list[str] = []
    for _, r in df.iterrows():
        code_num = str(r.get("代码") or "").strip()
        if not code_num:
            continue
        out.append(f"{code_num}.{_infer_exchange(code_num)}")
        if 0 < max_stocks <= len(out):
            break
    return out


def run_stock_news(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import pandas as pd
    import akshare as ak

    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH")
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 200))
    max_news_per_stock = int((params or {}).get("max_news_per_stock") or 30)

    codes = _get_stock_list(test_mode, test_stock, max_stocks)
    processed = 0
    rows_written = 0
    failed: list[str] = []

    conn = connect(cfg)
    try:
        batch: list[tuple[Any, ...]] = []
        for code in codes:
            processed += 1
            code_num = code.split(".")[0]
            try:
                df = ak.stock_news_em(symbol=code_num)
            except Exception:
                failed.append(code)
                continue
            if df is None or len(df) == 0:
                continue
            df2 = df.head(max_news_per_stock)
            for _, r in df2.iterrows():
                title = str(r.get("新闻标题") or "").strip()
                if not title:
                    continue
                content = str(r.get("新闻内容") or "").strip()
                pub_time = str(r.get("发布时间") or "").strip()
                published_at: datetime | None = None
                if pub_time:
                    try:
                        ts = pd.to_datetime(pub_time, errors="coerce")
                        published_at = None if pd.isna(ts) else ts.to_pydatetime()
                    except Exception:
                        published_at = None
                if published_at is None:
                    continue
                batch.append((code, published_at, "news", title[:255], content[:2000]))
        rows_written = executemany(conn, _INSERT_SQL, batch)
        return JobStats(
            items_processed=processed,
            rows_written=rows_written,
            failed_items=failed,
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

