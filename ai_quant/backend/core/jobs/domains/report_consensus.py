from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from core.db import MySQLConfig, connect, executemany, query_dict, load_mysql_config
from core.jobs.common import JobStats, normalize_stock_code, safe_float, to_ymd
from core.jobs.domains.stock_group import get_stock_codes_by_scope, ensure_stock_group_tables


_INSERT_SQL = """
INSERT INTO trade_report_consensus
(stock_code, broker, report_date, rating, target_price)
VALUES (%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
rating=VALUES(rating),
target_price=VALUES(target_price)
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


def run_report_consensus(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    max_stocks = int((params or {}).get("max_stocks") or 0)
    max_rows_per_stock = int((params or {}).get("max_rows_per_stock") or 50)
    max_workers = max(1, int((params or {}).get("max_workers") or 4))
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
        if 0 < max_stocks < len(codes):
            codes = codes[:max_stocks]
    else:
        # scope_type = "all" 时使用全量股票列表
        codes = _get_stock_list(max_stocks)
    total_count = len(codes)
    processed = 0
    failed: list[str] = []
    all_rows: list[tuple[Any, ...]] = []

    def _process_one(code):
        code_num = code.split(".")[0]
        try:
            df = ak.stock_institute_recommend_detail(symbol=code_num)
        except Exception:
            return None, True
        if df is None or len(df) == 0:
            return [], False
        try:
            df2 = df.head(max_rows_per_stock)
            if len(df2.columns) >= 8:
                df2.columns = ["stock_code_raw", "stock_name", "target_price", "rating", "broker", "analyst", "industry", "report_date"]
            df2["target_price"] = pd.to_numeric(df2.get("target_price"), errors="coerce")
            df2["report_date"] = pd.to_datetime(df2.get("report_date"), errors="coerce")
            rows = []
            for _, r in df2.iterrows():
                broker = str(r.get("broker") or "").strip()[:128]
                if not broker:
                    continue
                rating = str(r.get("rating") or "").strip()[:64] or None
                report_dt = r.get("report_date")
                report_date = to_ymd(report_dt)
                if not report_date:
                    continue
                tp = safe_float(r.get("target_price"))
                rows.append((code, broker, report_date, rating, tp))
            return rows, False
        except Exception:
            return None, True

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
            all_rows.extend(result_rows)

    conn = connect(cfg)
    try:
        written = executemany(conn, _INSERT_SQL, all_rows)
        return JobStats(
            items_processed=processed,
            rows_written=written,
            failed_items=failed,
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None if not failed else f"失败 {len(set(failed))} 只股票",
        )
    finally:
        conn.close()

