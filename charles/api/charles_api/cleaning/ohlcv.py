from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class OhlcvRow:
    trade_date: str
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    volume_shares: int | None
    amount: float | None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    if x != x:
        return None
    return x


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        x = int(float(v))
    except Exception:
        return None
    return x


def clean_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()

    out = df.copy()
    for col in ["open", "high", "low", "close", "amount"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce")

    keep_cols = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in out.columns]
    out = out[keep_cols]
    out = out.dropna(subset=[c for c in ["open", "high", "low", "close"] if c in out.columns])

    if "low" in out.columns and "high" in out.columns:
        out = out[out["low"] <= out["high"]]
    if "open" in out.columns and "high" in out.columns:
        out = out[out["open"] <= out["high"]]
    if "open" in out.columns and "low" in out.columns:
        out = out[out["open"] >= out["low"]]
    if "close" in out.columns and "high" in out.columns:
        out = out[out["close"] <= out["high"]]
    if "close" in out.columns and "low" in out.columns:
        out = out[out["close"] >= out["low"]]

    out = out[~out.index.duplicated(keep="last")]
    out = out.sort_index()
    return out

