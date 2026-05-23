from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from core.db import MySQLConfig, connect, executemany, query_dict, load_mysql_config
from core.jobs.common import JobStats, normalize_stock_code
from core.jobs.domains.stock_group import get_stock_codes_by_scope, ensure_stock_group_tables


_INSERT_SQL = """
INSERT INTO trade_stock_news
(stock_code, published_at, news_type, title, content, source, source_url)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
news_type=VALUES(news_type),
title=VALUES(title),
content=VALUES(content),
source=VALUES(source),
source_url=VALUES(source_url)
"""


def _infer_exchange(code_num: str) -> str:
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


def _get_stock_list_from_db(max_stocks: int) -> list[str]:
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(conn, """
                SELECT DISTINCT stock_code
                FROM trade_stock_financial
                ORDER BY stock_code
                LIMIT %s
            """, (max_stocks,))
            return [r["stock_code"] for r in rows]
        finally:
            conn.close()
    except Exception:
        return []


def _get_stock_list(max_stocks: int) -> list[str]:
    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return _get_stock_list_from_db(max_stocks)
        out: list[str] = []
        for _, r in df.iterrows():
            code_num = str(r.get("代码") or "").strip()
            if not code_num:
                continue
            out.append(f"{code_num}.{_infer_exchange(code_num)}")
            if 0 < max_stocks <= len(out):
                break
        return out
    except Exception:
        return _get_stock_list_from_db(max_stocks)


def run_stock_news(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    max_stocks = int((params or {}).get("max_stocks") or 0)
    max_news_per_stock = int((params or {}).get("max_news_per_stock") or 30)
    max_workers = max(1, int((params or {}).get("max_workers") or 4))
    batch_size = int((params or {}).get("batch_size") or 50)
    scope_type = str((params or {}).get("scope_type") or "all").strip().lower()
    group_id = int((params or {}).get("group_id") or 0)

    # 根据 scope_type 获取股票列表
    if scope_type in ("watchlist", "group"):
        ensure_stock_group_tables()
        codes = get_stock_codes_by_scope(scope_type, group_id=group_id)
        if not codes:
            return JobStats(
                items_processed=0,
                rows_written=0,
                failed_items=[],
                data_source_final="file",
                fallback_chain=["file"],
                message="股票列表为空",
            )
        # scope_type 不为 "all" 时，max_stocks 依然生效
        if 0 < max_stocks < len(codes):
            codes = codes[:max_stocks]
    else:
        # scope_type = "all" 时使用全量股票列表
        codes = _get_stock_list(max_stocks)
    total_count = len(codes)
    processed = 0
    rows_written = 0
    failed: list[str] = []

    def _process_one(code):
        code_num = code.split(".")[0]
        try:
            df = ak.stock_news_em(symbol=code_num)
        except Exception:
            return None, True
        if df is None or len(df) == 0:
            return [], False
        rows = []
        for _, r in df.head(max_news_per_stock).iterrows():
            title = str(r.get("新闻标题") or "").strip()
            if not title:
                continue
            content = str(r.get("新闻内容") or "").strip()
            source = str(r.get("文章来源") or "").strip()[:50]
            source_url = str(r.get("新闻链接") or "").strip()[:500]
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
            rows.append((code, published_at, "news", title[:255], content[:2000], source, source_url))
        return rows, False

    print(f"开始采集: {total_count} 只股票, {max_workers} 线程")

    conn = connect(cfg)
    try:
        batch: list[tuple[Any, ...]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {executor.submit(_process_one, code): code for code in codes}
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                processed += 1
                try:
                    result_rows, is_failed = future.result()
                except Exception:
                    failed.append(code)
                    continue
                if is_failed:
                    failed.append(code)
                    continue
                batch.extend(result_rows)
                if processed % batch_size == 0 and batch:
                    rows_written += executemany(conn, _INSERT_SQL, batch)
                    batch = []
        if batch:
            rows_written += executemany(conn, _INSERT_SQL, batch)
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

