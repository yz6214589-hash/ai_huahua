from __future__ import annotations

from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, safe_float, to_ymd


_INSERT_SQL = """
INSERT INTO trade_macro_indicator
(indicator_date, cpi_yoy, ppi_yoy, pmi, m2_yoy, shrzgm, lpr_1y, lpr_5y, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
cpi_yoy=COALESCE(VALUES(cpi_yoy), cpi_yoy),
ppi_yoy=COALESCE(VALUES(ppi_yoy), ppi_yoy),
pmi=COALESCE(VALUES(pmi), pmi),
m2_yoy=COALESCE(VALUES(m2_yoy), m2_yoy),
shrzgm=COALESCE(VALUES(shrzgm), shrzgm),
lpr_1y=COALESCE(VALUES(lpr_1y), lpr_1y),
lpr_5y=COALESCE(VALUES(lpr_5y), lpr_5y),
data_source=VALUES(data_source)
"""


def run_macro_indicator(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    date_values: dict[str, dict[str, float | None]] = {}

    cpi_df = ak.macro_china_cpi()
    ppi_df = ak.macro_china_ppi()
    pmi_df = ak.macro_china_pmi()
    m2_df = ak.macro_china_supply_of_money()
    shrzgm_df = ak.macro_china_shrzgm()
    lpr_df = ak.macro_china_lpr()

    def parse_cn_month(x: Any) -> pd.Timestamp | None:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        digits = "".join([ch for ch in s if ch.isdigit()])
        if len(digits) >= 6:
            try:
                y = int(digits[:4])
                m = int(digits[4:6])
                return pd.Timestamp(year=y, month=m, day=1)
            except Exception:
                return None
        return None

    def month_end(ts: pd.Timestamp) -> str:
        d = (ts + pd.offsets.MonthEnd(0)).date()
        return d.isoformat()

    def pick_col(df: pd.DataFrame, includes: list[str], fallback_idx: int) -> str | None:
        cols = [str(c) for c in df.columns]
        for kw in includes:
            for c in cols:
                if kw in c:
                    return c
        if len(df.columns) > fallback_idx:
            return str(df.columns[fallback_idx])
        return str(df.columns[-1]) if len(df.columns) else None

    def accumulate(df: Any, name: str, keywords: list[str], fallback_idx: int) -> None:
        if df is None or len(df) == 0:
            return
        date_col = df.columns[0]
        value_col = pick_col(df, keywords, fallback_idx)
        if not value_col:
            return
        for _, r in df.iterrows():
            ts = parse_cn_month(r.get(date_col))
            if ts is None:
                continue
            d = month_end(ts)
            if d not in date_values:
                date_values[d] = {"cpi_yoy": None, "ppi_yoy": None, "pmi": None, "m2_yoy": None, "shrzgm": None, "lpr_1y": None, "lpr_5y": None}
            date_values[d][name] = safe_float(r.get(value_col))

    accumulate(cpi_df, "cpi_yoy", ["同比增长", "同比"], 2)
    accumulate(ppi_df, "ppi_yoy", ["同比增长", "同比"], 2)
    accumulate(pmi_df, "pmi", ["制造业", "PMI"], 1)
    accumulate(m2_df, "m2_yoy", ["同比增长", "同比"], 2)
    accumulate(shrzgm_df, "shrzgm", ["社会融资规模", "社融"], 1)

    if lpr_df is not None and len(lpr_df) > 0:
        date_col = lpr_df.columns[0]
        one_col = pick_col(lpr_df, ["1年", "1Y"], 1)
        five_col = pick_col(lpr_df, ["5年", "5Y"], 2) or one_col
        for _, r in lpr_df.iterrows():
            ts = parse_cn_month(r.get(date_col))
            if ts is None:
                continue
            d = month_end(ts)
            if d not in date_values:
                date_values[d] = {"cpi_yoy": None, "ppi_yoy": None, "pmi": None, "m2_yoy": None, "shrzgm": None, "lpr_1y": None, "lpr_5y": None}
            date_values[d]["lpr_1y"] = safe_float(r.get(one_col))
            date_values[d]["lpr_5y"] = safe_float(r.get(five_col))

    if not date_values:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    rows: list[tuple[Any, ...]] = []
    for d in sorted(date_values.keys()):
        v = date_values[d]
        ymd = to_ymd(d)
        if not ymd:
            continue
        rows.append((ymd, v["cpi_yoy"], v["ppi_yoy"], v["pmi"], v["m2_yoy"], v["shrzgm"], v["lpr_1y"], v["lpr_5y"], "akshare"))

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

