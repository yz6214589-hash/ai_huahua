from __future__ import annotations

from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, normalize_stock_code, safe_float, to_ymd


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


def run_report_consensus(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH")
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 200))
    max_rows_per_stock = int((params or {}).get("max_rows_per_stock") or 50)

    codes = _get_stock_list(test_mode, test_stock, max_stocks)
    processed = 0
    failed: list[str] = []
    rows: list[tuple[Any, ...]] = []

    for code in codes:
        processed += 1
        code_num = code.split(".")[0]
        try:
            df = ak.stock_institute_recommend_detail(symbol=code_num)
        except Exception:
            failed.append(code)
            continue
        if df is None or len(df) == 0:
            continue
        try:
            df2 = df.head(max_rows_per_stock)
            if len(df2.columns) >= 8:
                df2.columns = ["stock_code_raw", "stock_name", "target_price", "rating", "broker", "analyst", "industry", "report_date"]
            df2["target_price"] = pd.to_numeric(df2.get("target_price"), errors="coerce")
            df2["report_date"] = pd.to_datetime(df2.get("report_date"), errors="coerce")
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
        except Exception:
            failed.append(code)
            continue

    conn = connect(cfg)
    try:
        written = executemany(conn, _INSERT_SQL, rows)
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

