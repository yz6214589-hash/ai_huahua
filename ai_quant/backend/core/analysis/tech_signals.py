from __future__ import annotations

import math
from typing import Any


def _clip01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


def _isfinite(v: Any) -> bool:
    try:
        return v is not None and math.isfinite(float(v))
    except Exception:
        return False


def _sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += float(v)
        if i >= period:
            s -= float(values[i - period])
        if i >= period - 1:
            out[i] = s / float(period)
    return out


def _rolling_std(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0:
        return out
    s = 0.0
    ss = 0.0
    for i, v in enumerate(values):
        fv = float(v)
        s += fv
        ss += fv * fv
        if i >= period:
            old = float(values[i - period])
            s -= old
            ss -= old * old
        if i >= period - 1:
            mean = s / float(period)
            var = max(0.0, (ss / float(period)) - mean * mean)
            out[i] = math.sqrt(var)
    return out


def _ema(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if not values or period <= 0:
        return out
    alpha = 2.0 / (float(period) + 1.0)
    ema = float(values[0])
    out[0] = ema
    for i in range(1, len(values)):
        ema = alpha * float(values[i]) + (1.0 - alpha) * ema
        out[i] = ema
    return out


def _rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < period + 1:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = float(values[i]) - float(values[i - 1])
        if delta >= 0:
            gains += delta
        else:
            losses += -delta
    avg_gain = gains / float(period)
    avg_loss = losses / float(period)
    out[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    for i in range(period + 1, len(values)):
        delta = float(values[i]) - float(values[i - 1])
        gain = max(0.0, delta)
        loss = max(0.0, -delta)
        avg_gain = (avg_gain * (period - 1) + gain) / float(period)
        avg_loss = (avg_loss * (period - 1) + loss) / float(period)
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def _macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    ema_fast = _ema(values, fast)
    ema_slow = _ema(values, slow)
    dif: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if ema_fast[i] is None or ema_slow[i] is None:
            dif[i] = None
        else:
            dif[i] = float(ema_fast[i]) - float(ema_slow[i])
    dif_vals = [float(x or 0.0) for x in dif]
    dea = _ema(dif_vals, signal)
    hist: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if dif[i] is None or dea[i] is None:
            hist[i] = None
        else:
            hist[i] = float(dif[i]) - float(dea[i])
    return dif, dea, hist


def _bbands(values: list[float], period: int = 20, nbdev: float = 2.0) -> tuple[list[float | None], list[float | None], list[float | None]]:
    mid = _sma(values, period)
    std = _rolling_std(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is None or std[i] is None:
            upper[i] = None
            lower[i] = None
        else:
            upper[i] = float(mid[i]) + nbdev * float(std[i])
            lower[i] = float(mid[i]) - nbdev * float(std[i])
    return upper, mid, lower


def _score_buy(
    close: float | None,
    ma20: float | None,
    boll_lower: float | None,
    macd_hist: float | None,
    rsi14: float | None,
    flags: dict[str, bool],
) -> tuple[float, list[str]]:
    score = 50.0
    reasons: list[str] = []
    if flags.get("trend_buy") and _isfinite(close) and _isfinite(ma20) and float(ma20) != 0.0:
        breakout = max(0.0, (float(close) - float(ma20)) / float(ma20))
        score += 20.0 + 20.0 * _clip01(breakout / 0.05)
        reasons.append("价格上穿MA20")
        reasons.append(f"突破幅度 {breakout:.2%}")
    if flags.get("range_buy") and _isfinite(close) and _isfinite(boll_lower) and float(boll_lower) != 0.0:
        dev = max(0.0, (float(boll_lower) - float(close)) / float(boll_lower))
        score += 15.0 + 15.0 * _clip01(dev / 0.05)
        reasons.append("价格跌破布林下轨")
        reasons.append(f"下轨偏离 {dev:.2%}")
    if _isfinite(macd_hist):
        mh = float(macd_hist)
        if mh > 0:
            score += 8.0
            reasons.append("MACD柱体为正")
        elif mh < 0:
            score -= 4.0
            reasons.append("MACD柱体为负")
    if _isfinite(rsi14):
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
    if score < 0.0:
        score = 0.0
    if score > 100.0:
        score = 100.0
    return float(score), reasons


def _score_sell(
    close: float | None,
    ma20: float | None,
    boll_upper: float | None,
    macd_hist: float | None,
    rsi14: float | None,
    flags: dict[str, bool],
) -> tuple[float, list[str]]:
    score = 50.0
    reasons: list[str] = []
    if flags.get("trend_sell") and _isfinite(close) and _isfinite(ma20) and float(ma20) != 0.0:
        breakdown = max(0.0, (float(ma20) - float(close)) / float(ma20))
        score += 20.0 + 20.0 * _clip01(breakdown / 0.05)
        reasons.append("价格下穿MA20")
        reasons.append(f"跌破幅度 {breakdown:.2%}")
    if flags.get("range_sell") and _isfinite(close) and _isfinite(boll_upper) and float(boll_upper) != 0.0:
        dev = max(0.0, (float(close) - float(boll_upper)) / float(boll_upper))
        score += 15.0 + 15.0 * _clip01(dev / 0.05)
        reasons.append("价格上穿布林上轨")
        reasons.append(f"上轨偏离 {dev:.2%}")
    if _isfinite(macd_hist):
        mh = float(macd_hist)
        if mh < 0:
            score += 8.0
            reasons.append("MACD柱体为负")
        elif mh > 0:
            score -= 4.0
            reasons.append("MACD柱体为正")
    if _isfinite(rsi14):
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
    if score < 0.0:
        score = 0.0
    if score > 100.0:
        score = 100.0
    return float(score), reasons


def generate_signals(trade_dates: list[str], closes: list[float]) -> list[dict[str, Any]]:
    if not closes or len(closes) != len(trade_dates):
        return []
    ma20 = _sma(closes, 20)
    upper, mid, lower = _bbands(closes, 20, 2.0)
    _, _, macd_hist = _macd(closes, 12, 26, 9)
    rsi14 = _rsi(closes, 14)

    def gt(a: float | None, b: float | None) -> bool:
        return _isfinite(a) and _isfinite(b) and float(a) > float(b)

    def lt(a: float | None, b: float | None) -> bool:
        return _isfinite(a) and _isfinite(b) and float(a) < float(b)

    out: list[dict[str, Any]] = []
    for i in range(1, len(closes)):
        close = float(closes[i])
        prev_close = float(closes[i - 1])
        flags = {
            "trend_buy": gt(close, ma20[i]) and not gt(prev_close, ma20[i - 1]),
            "trend_sell": lt(close, ma20[i]) and not lt(prev_close, ma20[i - 1]),
            "range_buy": lt(close, lower[i]),
            "range_sell": gt(close, upper[i]),
        }
        snapshot = {
            "close": close,
            "ma20": ma20[i],
            "rsi14": rsi14[i],
            "macd_hist": macd_hist[i],
            "boll_upper": upper[i],
            "boll_mid": mid[i],
            "boll_lower": lower[i],
        }
        if flags["trend_buy"] or flags["range_buy"]:
            score, reasons = _score_buy(close, ma20[i], lower[i], macd_hist[i], rsi14[i], flags)
            out.append(
                {
                    "trade_date": str(trade_dates[i]),
                    "signal": "BUY",
                    "score": score,
                    "reasons": reasons,
                    "snapshot": snapshot,
                }
            )
        if flags["trend_sell"] or flags["range_sell"]:
            score, reasons = _score_sell(close, ma20[i], upper[i], macd_hist[i], rsi14[i], flags)
            out.append(
                {
                    "trade_date": str(trade_dates[i]),
                    "signal": "SELL",
                    "score": score,
                    "reasons": reasons,
                    "snapshot": snapshot,
                }
            )
    return out

