from __future__ import annotations

import numpy as np
import pandas as pd


def SMA(close: np.ndarray, timeperiod: int) -> np.ndarray:
    s = pd.Series(close, dtype="float64")
    return s.rolling(int(timeperiod)).mean().to_numpy()


def RSI(close: np.ndarray, timeperiod: int) -> np.ndarray:
    s = pd.Series(close, dtype="float64")
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(int(timeperiod)).mean()
    avg_loss = loss.rolling(int(timeperiod)).mean()
    rs = avg_gain / (avg_loss.replace(0.0, np.nan))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.to_numpy()


def MACD(
    close: np.ndarray,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = pd.Series(close, dtype="float64")
    ema_fast = s.ewm(span=int(fastperiod), adjust=False).mean()
    ema_slow = s.ewm(span=int(slowperiod), adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=int(signalperiod), adjust=False).mean()
    hist = dif - dea
    return dif.to_numpy(), dea.to_numpy(), hist.to_numpy()


def BBANDS(
    close: np.ndarray,
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
    matype: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = pd.Series(close, dtype="float64")
    mid = s.rolling(int(timeperiod)).mean()
    std = s.rolling(int(timeperiod)).std(ddof=0)
    upper = mid + float(nbdevup) * std
    lower = mid - float(nbdevdn) * std
    return upper.to_numpy(), mid.to_numpy(), lower.to_numpy()

