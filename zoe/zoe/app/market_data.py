from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from zoe.app.config import Settings
from zoe.app.db import fetch_all, fetch_one


def _stock_code_candidates(stock_code: str) -> list[str]:
    s = (stock_code or "").strip()
    if not s:
        return []
    out: list[str] = []
    for v in [s, s.upper(), s.lower()]:
        if v and v not in out:
            out.append(v)
    if "." in s:
        base = s.split(".", 1)[0].strip()
        for v in [base, base.upper(), base.lower()]:
            if v and v not in out:
                out.append(v)
    return out


def load_daily_ohlcv(settings: Settings, stock_code: str, start: date, end: date) -> pd.DataFrame:
    candidates = _stock_code_candidates(stock_code)
    if not candidates:
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume", "amount"])

    placeholders = ",".join(["%s"] * len(candidates))
    sql = """
        SELECT
            stock_code,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            amount
        FROM trade_stock_daily
        WHERE stock_code IN (""" + placeholders + """)
          AND trade_date >= %s
          AND trade_date <= %s
        ORDER BY trade_date ASC
    """
    rows = fetch_all(settings, sql, tuple(candidates) + (start, end))
    if not rows:
        return pd.DataFrame(columns=["trade_date", "open", "high", "low", "close", "volume", "amount"])

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.rename(
        columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
    )
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["trade_date", "close"])
    return df


def list_stock_codes(settings: Settings, limit: int = 2000) -> list[str]:
    sql = """
        SELECT DISTINCT stock_code
        FROM trade_stock_daily
        ORDER BY stock_code
        LIMIT %s
    """
    rows = fetch_all(settings, sql, (limit,))
    return [r["stock_code"] for r in rows if r.get("stock_code")]


def latest_trade_date(settings: Settings, stock_code: str) -> date | None:
    candidates = _stock_code_candidates(stock_code)
    if not candidates:
        return None
    placeholders = ",".join(["%s"] * len(candidates))
    sql = """
        SELECT trade_date
        FROM trade_stock_daily
        WHERE stock_code IN (""" + placeholders + """)
        ORDER BY trade_date DESC
        LIMIT 1
    """
    row = fetch_one(settings, sql, tuple(candidates))
    if not row:
        return None
    v = row.get("trade_date")
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def latest_financial_row(settings: Settings, stock_code: str) -> dict[str, Any] | None:
    candidates = _stock_code_candidates(stock_code)
    if not candidates:
        return None
    placeholders = ",".join(["%s"] * len(candidates))
    sql = """
        SELECT
            stock_code,
            report_date,
            revenue,
            net_profit,
            eps,
            roe,
            roa,
            gross_margin,
            net_margin,
            debt_ratio,
            current_ratio,
            operating_cashflow,
            total_assets,
            total_equity
        FROM trade_stock_financial
        WHERE stock_code IN (""" + placeholders + """)
        ORDER BY report_date DESC
        LIMIT 1
    """
    return fetch_one(settings, sql, tuple(candidates))

