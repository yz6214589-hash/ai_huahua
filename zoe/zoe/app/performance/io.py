from __future__ import annotations

import io

import pandas as pd


def read_nav_csv_bytes(content: bytes) -> pd.Series:
    if content is None:
        raise ValueError("content is required")

    df = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc)
            break
        except Exception:
            df = None

    if df is None or df.empty:
        raise ValueError("empty_csv")

    cols = {str(c).strip().lower(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("trade_date") or cols.get("dt")
    nav_col = cols.get("nav") or cols.get("value") or cols.get("net_value")
    if not date_col or not nav_col:
        raise ValueError("missing_columns")

    out = df[[date_col, nav_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out[nav_col] = pd.to_numeric(out[nav_col], errors="coerce")
    out = out.dropna(subset=[date_col, nav_col]).sort_values(date_col)
    if out.empty:
        raise ValueError("no_valid_rows")
    s = out.set_index(date_col)[nav_col].astype(float)
    return s

