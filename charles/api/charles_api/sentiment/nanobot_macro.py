from __future__ import annotations

import os
from datetime import datetime
from typing import Any


def _safe_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def fetch_vix() -> dict[str, Any]:
    try:
        import akshare as ak

        df = ak.index_vix()
        if df is not None and not df.empty:
            last = df.iloc[-1]
            v = _safe_float(last.get("收盘") if "收盘" in last else last.iloc[-1])
            d = str(last.get("日期") if "日期" in last else df.iloc[-1, 0])
            return {"indicator": "VIX", "value": v, "date": d, "name": "标普500波动率指数"}
    except Exception:
        pass

    try:
        import yfinance as yf

        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist is not None and not hist.empty:
            last = hist.iloc[-1]
            d = str(hist.index[-1].date())
            return {"indicator": "VIX", "value": _safe_float(last["Close"]), "date": d, "name": "标普500波动率指数"}
    except Exception as e:
        return {"indicator": "VIX", "value": None, "error": f"{type(e).__name__}: {e}", "name": "标普500波动率指数"}

    return {"indicator": "VIX", "value": None, "error": "no data", "name": "标普500波动率指数"}


def fetch_us_treasury_10y() -> dict[str, Any]:
    try:
        import akshare as ak

        df = ak.bond_zh_us_rate()
        if df is not None and not df.empty:
            if "10年" in df.columns:
                last = df.iloc[-1]
                d = str(last.get("日期") if "日期" in last else df.iloc[-1, 0])
                return {"indicator": "US10Y", "value": _safe_float(last["10年"]), "date": d, "name": "美国10年期国债收益率"}
    except Exception:
        pass

    try:
        import yfinance as yf

        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        if hist is not None and not hist.empty:
            last = hist.iloc[-1]
            d = str(hist.index[-1].date())
            v = _safe_float(last["Close"])
            if v is not None:
                v = v / 100.0
            return {"indicator": "US10Y", "value": v, "date": d, "name": "美国10年期国债收益率"}
    except Exception as e:
        return {"indicator": "US10Y", "value": None, "error": f"{type(e).__name__}: {e}", "name": "美国10年期国债收益率"}

    return {"indicator": "US10Y", "value": None, "error": "no data", "name": "美国10年期国债收益率"}


def fetch_ovx_gvz() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        import yfinance as yf

        for symbol, code, name in [
            ("^OVX", "OVX", "原油ETF波动率指数"),
            ("^GVZ", "GVZ", "黄金ETF波动率指数"),
        ]:
            try:
                t = yf.Ticker(symbol)
                hist = t.history(period="5d")
                if hist is None or hist.empty:
                    out.append({"indicator": code, "value": None, "error": "no data", "name": name})
                    continue
                last = hist.iloc[-1]
                d = str(hist.index[-1].date())
                out.append({"indicator": code, "value": _safe_float(last["Close"]), "date": d, "name": name})
            except Exception as e:
                out.append({"indicator": code, "value": None, "error": f"{type(e).__name__}: {e}", "name": name})
        return out
    except Exception as e:
        return [
            {"indicator": "OVX", "value": None, "error": f"{type(e).__name__}: {e}", "name": "原油ETF波动率指数"},
            {"indicator": "GVZ", "value": None, "error": f"{type(e).__name__}: {e}", "name": "黄金ETF波动率指数"},
        ]


def _score_vix(v: float | None) -> tuple[int, str]:
    if v is None:
        return 50, "未知"
    if v < 15:
        return 80, "极度平静"
    if v < 20:
        return 60, "正常"
    if v < 25:
        return 40, "焦虑"
    if v < 35:
        return 25, "恐慌"
    return 10, "极度恐慌"


def _score_us10y(v: float | None) -> tuple[int, str]:
    if v is None:
        return 50, "未知"
    if v < 0.03:
        return 70, "偏宽松"
    if v < 0.043:
        return 55, "中性"
    if v < 0.05:
        return 35, "偏紧"
    return 20, "紧缩风险"


def compute_fear_snapshot(*, include_ashare: bool = False) -> dict[str, Any]:
    indicators: list[dict[str, Any]] = []
    vix = fetch_vix()
    indicators.append(vix)
    indicators.extend(fetch_ovx_gvz())
    us10y = fetch_us_treasury_10y()
    indicators.append(us10y)

    vix_score, vix_level = _score_vix(_safe_float(vix.get("value")))
    us10y_score, us10y_level = _score_us10y(_safe_float(us10y.get("value")))
    composite = int(round((vix_score + us10y_score) / 2.0))

    if composite <= 24:
        overall = "极度恐惧"
        suggestion = "关注超跌反弹机会，严格风控"
    elif composite <= 49:
        overall = "恐惧"
        suggestion = "适当控制仓位，关注风险事件"
    elif composite <= 60:
        overall = "中性"
        suggestion = "按策略正常操作"
    elif composite <= 74:
        overall = "贪婪"
        suggestion = "警惕回撤，适当提高止盈纪律"
    else:
        overall = "极度贪婪"
        suggestion = "警惕利好出尽，降低追高冲动"

    return {
        "indicators": indicators,
        "ashare_sentiment": None if not include_ashare else None,
        "composite": {
            "composite_fear_greed_index": composite,
            "overall_sentiment": overall,
            "action_suggestion": suggestion,
            "score_details": [
                {"name": "VIX", "score": vix_score, "level": vix_level, "value": vix.get("value")},
                {"name": "US10Y", "score": us10y_score, "level": us10y_level, "value": us10y.get("value")},
            ],
            "contagion_analysis": None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

