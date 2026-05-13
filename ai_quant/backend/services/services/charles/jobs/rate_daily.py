from __future__ import annotations

from typing import Any

from db import MySQLConfig, connect, executemany

from common import JobStats, safe_float, to_ymd


_INSERT_SQL = """
INSERT INTO trade_rate_daily
(rate_date, rate_name, rate_value)
VALUES (%s,%s,%s)
ON DUPLICATE KEY UPDATE
rate_value=COALESCE(VALUES(rate_value), rate_value)
"""


def run_rate_daily(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import pandas as pd
    import akshare as ak

    df = ak.bond_zh_us_rate()
    if df is None or len(df) == 0:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    date_col = df.columns[0]
    cn_col = None
    us_col = None
    for c in df.columns:
        s = str(c)
        if "中国" in s and "10" in s:
            cn_col = c
        if "美国" in s and "10" in s:
            us_col = c
    cn_col = cn_col or df.columns[min(1, len(df.columns) - 1)]
    us_col = us_col or (df.columns[min(2, len(df.columns) - 1)] if len(df.columns) > 2 else cn_col)

    df2 = pd.DataFrame(
        {
            "d": pd.to_datetime(df[date_col], errors="coerce").dt.date,
            "cn": pd.to_numeric(df[cn_col], errors="coerce"),
            "us": pd.to_numeric(df[us_col], errors="coerce"),
        }
    ).dropna(subset=["d"])

    rows: list[tuple[Any, ...]] = []
    for _, r in df2.iterrows():
        d = to_ymd(r.get("d"))
        if not d:
            continue
        rows.append((d, "cn_bond_10y", safe_float(r.get("cn"))))
        rows.append((d, "us_bond_10y", safe_float(r.get("us"))))

    conn = connect(cfg)
    try:
        written = executemany(conn, _INSERT_SQL, rows)
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None,
        )
    finally:
        conn.close()

