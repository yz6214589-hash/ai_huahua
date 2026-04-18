from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import talib  # type: ignore

    _TALIB_BACKEND = "native"
    _HAS_TALIB = True
    _TALIB_ERROR: str | None = None
except Exception as e:
    from zoe.app import _talib_fallback as talib

    _TALIB_BACKEND = "fallback"
    _HAS_TALIB = True
    _TALIB_ERROR = str(e)


def has_talib() -> bool:
    return _HAS_TALIB


def talib_error() -> str | None:
    return _TALIB_ERROR


def talib_backend() -> str:
    return _TALIB_BACKEND


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    close = out["close"].astype(float).to_numpy()

    out["ma5"] = talib.SMA(close, timeperiod=5)
    out["ma10"] = talib.SMA(close, timeperiod=10)
    out["ma20"] = talib.SMA(close, timeperiod=20)
    out["ma60"] = talib.SMA(close, timeperiod=60)

    dif, dea, hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    out["macd_dif"] = dif
    out["macd_dea"] = dea
    out["macd_hist"] = hist

    out["rsi14"] = talib.RSI(close, timeperiod=14)

    upper, mid, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
    out["boll_upper"] = upper
    out["boll_mid"] = mid
    out["boll_lower"] = lower
    return out

