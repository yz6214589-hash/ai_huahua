from __future__ import annotations

from typing import Any

import pandas as pd

from ..db import MySQLConfig, connect, executemany
from ..models import DataSource
from .common import JobStats


INSERT_SQL = """
INSERT INTO trade_rate_daily
(rate_date, cn_bond_10y, us_bond_10y, data_source)
VALUES (%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
cn_bond_10y=COALESCE(VALUES(cn_bond_10y), cn_bond_10y),
us_bond_10y=COALESCE(VALUES(us_bond_10y), us_bond_10y),
data_source=VALUES(data_source)
"""


def run_rate_daily(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak

    fallback_chain = [DataSource.akshare]
    conn = connect(cfg)
    try:
        df = ak.bond_zh_us_rate()
        if df is None or len(df) == 0:
            return JobStats(
                items_processed=0,
                rows_written=0,
                failed_items=[],
                data_source_final=DataSource.akshare,
                fallback_chain=fallback_chain,
                message="AkShare接口返回空",
            )

        date_col = df.columns[0]
        cn_col = None
        us_col = None
        for c in df.columns:
            if "中国" in str(c) and "10" in str(c):
                cn_col = c
            if "美国" in str(c) and "10" in str(c):
                us_col = c
        cn_col = cn_col or df.columns[min(1, len(df.columns) - 1)]
        us_col = us_col or (df.columns[min(2, len(df.columns) - 1)] if len(df.columns) > 2 else cn_col)

        df2 = pd.DataFrame(
            {
                "rate_date": pd.to_datetime(df[date_col], errors="coerce").dt.date,
                "cn": pd.to_numeric(df[cn_col], errors="coerce"),
                "us": pd.to_numeric(df[us_col], errors="coerce"),
            }
        ).dropna(subset=["rate_date"])

        rows = []
        for _, r in df2.iterrows():
            rows.append(
                (
                    str(r["rate_date"]),
                    None if pd.isna(r.get("cn")) else float(r.get("cn")),
                    None if pd.isna(r.get("us")) else float(r.get("us")),
                    "akshare",
                )
            )
        written = executemany(conn, INSERT_SQL, rows)
        conn.commit()
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final=DataSource.akshare,
            fallback_chain=fallback_chain,
            message=None,
        )
    finally:
        conn.close()

