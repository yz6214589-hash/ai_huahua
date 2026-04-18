from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


SignalType = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Signal:
    trade_date: str
    signal: SignalType
    score: float
    reasons: list[str]
    snapshot: dict


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def _score_buy(row: pd.Series, flags: dict[str, bool]) -> tuple[float, list[str]]:
    score = 50.0
    reasons: list[str] = []

    close = float(row.get("close", np.nan))
    ma20 = float(row.get("ma20", np.nan))
    boll_lower = float(row.get("boll_lower", np.nan))
    macd_hist = row.get("macd_hist", np.nan)
    rsi14 = row.get("rsi14", np.nan)

    if flags.get("trend_buy") and np.isfinite(close) and np.isfinite(ma20) and ma20 != 0:
        breakout = max(0.0, (close - ma20) / ma20)
        score += 20.0 + 20.0 * _clip01(breakout / 0.05)
        reasons.append("价格上穿MA20")
        reasons.append(f"突破幅度 {breakout:.2%}")

    if flags.get("range_buy") and np.isfinite(close) and np.isfinite(boll_lower) and boll_lower != 0:
        dev = max(0.0, (boll_lower - close) / boll_lower)
        score += 15.0 + 15.0 * _clip01(dev / 0.05)
        reasons.append("价格跌破布林下轨")
        reasons.append(f"下轨偏离 {dev:.2%}")

    if pd.notna(macd_hist):
        mh = float(macd_hist)
        if mh > 0:
            score += 8.0
            reasons.append("MACD柱体为正")
        elif mh < 0:
            score -= 4.0
            reasons.append("MACD柱体为负")

    if pd.notna(rsi14):
        r = float(rsi14)
        if r < 30:
            score += 8.0
            reasons.append("RSI处于超卖区(<30)")
        elif r > 70:
            score -= 8.0
            reasons.append("RSI处于超买区(>70)")
        elif 40 <= r <= 60:
            score += 3.0
            reasons.append("RSI处于均衡区(40-60)")

    score = float(np.clip(score, 0.0, 100.0))
    return score, reasons


def _score_sell(row: pd.Series, flags: dict[str, bool]) -> tuple[float, list[str]]:
    score = 50.0
    reasons: list[str] = []

    close = float(row.get("close", np.nan))
    ma20 = float(row.get("ma20", np.nan))
    boll_upper = float(row.get("boll_upper", np.nan))
    macd_hist = row.get("macd_hist", np.nan)
    rsi14 = row.get("rsi14", np.nan)

    if flags.get("trend_sell") and np.isfinite(close) and np.isfinite(ma20) and ma20 != 0:
        breakdown = max(0.0, (ma20 - close) / ma20)
        score += 20.0 + 20.0 * _clip01(breakdown / 0.05)
        reasons.append("价格下穿MA20")
        reasons.append(f"跌破幅度 {breakdown:.2%}")

    if flags.get("range_sell") and np.isfinite(close) and np.isfinite(boll_upper) and boll_upper != 0:
        dev = max(0.0, (close - boll_upper) / boll_upper)
        score += 15.0 + 15.0 * _clip01(dev / 0.05)
        reasons.append("价格上穿布林上轨")
        reasons.append(f"上轨偏离 {dev:.2%}")

    if pd.notna(macd_hist):
        mh = float(macd_hist)
        if mh < 0:
            score += 8.0
            reasons.append("MACD柱体为负")
        elif mh > 0:
            score -= 4.0
            reasons.append("MACD柱体为正")

    if pd.notna(rsi14):
        r = float(rsi14)
        if r > 70:
            score += 8.0
            reasons.append("RSI处于超买区(>70)")
        elif r < 30:
            score -= 8.0
            reasons.append("RSI处于超卖区(<30)")
        elif 40 <= r <= 60:
            score += 3.0
            reasons.append("RSI处于均衡区(40-60)")

    score = float(np.clip(score, 0.0, 100.0))
    return score, reasons


def generate_signals(tech_df: pd.DataFrame) -> list[Signal]:
    if tech_df.empty:
        return []

    df = tech_df.reset_index(drop=True).copy()

    def gt(a: float, b: float) -> bool:
        return np.isfinite(a) and np.isfinite(b) and a > b

    def lt(a: float, b: float) -> bool:
        return np.isfinite(a) and np.isfinite(b) and a < b

    signals: list[Signal] = []
    for i in range(1, len(df)):
        row = df.loc[i]
        prev = df.loc[i - 1]

        close = float(row.get("close", np.nan))
        ma20 = float(row.get("ma20", np.nan))
        prev_close = float(prev.get("close", np.nan))
        prev_ma20 = float(prev.get("ma20", np.nan))

        boll_lower = float(row.get("boll_lower", np.nan))
        boll_upper = float(row.get("boll_upper", np.nan))

        flags = {
            "trend_buy": gt(close, ma20) and not gt(prev_close, prev_ma20),
            "trend_sell": lt(close, ma20) and not lt(prev_close, prev_ma20),
            "range_buy": lt(close, boll_lower),
            "range_sell": gt(close, boll_upper),
        }

        trade_date = pd.to_datetime(row.get("trade_date")).date().isoformat()
        snapshot = {
            "close": close,
            "ma20": row.get("ma20"),
            "rsi14": row.get("rsi14"),
            "macd_hist": row.get("macd_hist"),
            "boll_upper": row.get("boll_upper"),
            "boll_mid": row.get("boll_mid"),
            "boll_lower": row.get("boll_lower"),
        }

        if flags["trend_buy"] or flags["range_buy"]:
            score, reasons = _score_buy(row, flags)
            signals.append(
                Signal(
                    trade_date=trade_date,
                    signal="BUY",
                    score=score,
                    reasons=reasons,
                    snapshot=snapshot,
                )
            )

        if flags["trend_sell"] or flags["range_sell"]:
            score, reasons = _score_sell(row, flags)
            signals.append(
                Signal(
                    trade_date=trade_date,
                    signal="SELL",
                    score=score,
                    reasons=reasons,
                    snapshot=snapshot,
                )
            )

    return signals

