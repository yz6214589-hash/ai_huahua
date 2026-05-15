from __future__ import annotations

from typing import Any

from db import MySQLConfig, connect, executemany

from common import JobStats, safe_float, to_ymd


_INSERT_SQL = """
INSERT INTO trade_macro_indicator
(indicator_date, indicator_name, indicator_value, source)
VALUES (%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
indicator_value=COALESCE(VALUES(indicator_value), indicator_value),
source=VALUES(source)
"""


def run_macro_indicator(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import pandas as pd
    import akshare as ak

    frames: list[pd.DataFrame] = []

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

    def build(df: Any, name: str, keywords: list[str], fallback_idx: int) -> None:
        if df is None or len(df) == 0:
            return
        date_col = df.columns[0]
        value_col = pick_col(df, keywords, fallback_idx)
        if not value_col:
            return
        tmp = []
        for _, r in df.iterrows():
            ts = parse_cn_month(r.get(date_col))
            if ts is None:
                continue
            tmp.append({"d": month_end(ts), "name": name, "v": safe_float(r.get(value_col))})
        if tmp:
            frames.append(pd.DataFrame(tmp))

    build(cpi_df, "cpi_yoy", ["同比增长", "同比"], 2)
    build(ppi_df, "ppi_yoy", ["同比增长", "同比"], 2)
    build(pmi_df, "pmi", ["制造业", "PMI"], 1)
    build(m2_df, "m2_yoy", ["同比增长", "同比"], 2)
    build(shrzgm_df, "shrzgm", ["社会融资规模", "社融"], 1)

    if lpr_df is not None and len(lpr_df) > 0:
        date_col = lpr_df.columns[0]
        one_col = pick_col(lpr_df, ["1年", "1Y"], 1)
        five_col = pick_col(lpr_df, ["5年", "5Y"], 2) or one_col
        tmp2 = []
        for _, r in lpr_df.iterrows():
            ts = parse_cn_month(r.get(date_col))
            if ts is None:
                continue
            d = month_end(ts)
            tmp2.append({"d": d, "name": "lpr_1y", "v": safe_float(r.get(one_col))})
            tmp2.append({"d": d, "name": "lpr_5y", "v": safe_float(r.get(five_col))})
        if tmp2:
            frames.append(pd.DataFrame(tmp2))

    if not frames:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.dropna(subset=["d", "name"])

    rows: list[tuple[Any, ...]] = []
    for _, r in merged.iterrows():
        d = to_ymd(r.get("d"))
        n = str(r.get("name") or "").strip()
        if not d or not n:
            continue
        rows.append((d, n, safe_float(r.get("v")), "akshare"))

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

