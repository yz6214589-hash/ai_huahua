from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from zoe.app.indicators import add_technical_indicators
from zoe.app.market_data import latest_financial_row, list_stock_codes, load_daily_ohlcv


@dataclass(frozen=True)
class FinancialFilters:
    roe_min: float | None = None
    net_margin_min: float | None = None
    gross_margin_min: float | None = None
    debt_ratio_max: float | None = None
    cashflow_to_revenue_min: float | None = None


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def screen_financial(settings, filters: FinancialFilters, stock_codes: list[str] | None, limit: int) -> list[dict]:
    codes = stock_codes or list_stock_codes(settings, limit=limit)
    out: list[dict] = []
    for code in codes:
        row = latest_financial_row(settings, code)
        if not row:
            continue

        roe = _to_float(row.get("roe"))
        net_margin = _to_float(row.get("net_margin"))
        gross_margin = _to_float(row.get("gross_margin"))
        debt_ratio = _to_float(row.get("debt_ratio"))
        revenue = _to_float(row.get("revenue"))
        op_cf = _to_float(row.get("operating_cashflow"))

        if filters.roe_min is not None and (roe is None or roe < filters.roe_min):
            continue
        if filters.net_margin_min is not None and (net_margin is None or net_margin < filters.net_margin_min):
            continue
        if filters.gross_margin_min is not None and (gross_margin is None or gross_margin < filters.gross_margin_min):
            continue
        if filters.debt_ratio_max is not None and (debt_ratio is None or debt_ratio > filters.debt_ratio_max):
            continue
        if filters.cashflow_to_revenue_min is not None:
            if revenue is None or revenue == 0 or op_cf is None:
                continue
            if (op_cf / revenue) < filters.cashflow_to_revenue_min:
                continue

        out.append(
            {
                "stock_code": code,
                "report_date": row.get("report_date").isoformat() if row.get("report_date") else None,
                "roe": roe,
                "net_margin": net_margin,
                "gross_margin": gross_margin,
                "debt_ratio": debt_ratio,
                "cashflow_to_revenue": (op_cf / revenue) if (op_cf is not None and revenue) else None,
            }
        )
    return out


def _calc_factors(df: pd.DataFrame) -> dict[str, float]:
    if df.empty or len(df) < 30:
        return {}
    d = df.copy()
    d["ret"] = d["close"].pct_change()
    mom20 = float(d["close"].iloc[-1] / d["close"].iloc[-21] - 1.0) if len(d) >= 21 else np.nan
    vol20 = float(d["ret"].iloc[-20:].std(ddof=0)) if len(d) >= 20 else np.nan
    avg_vol20 = float(d["volume"].iloc[-20:].mean()) if "volume" in d.columns and len(d) >= 20 else np.nan
    tech = add_technical_indicators(d)
    last = tech.iloc[-1]
    rsi14 = float(last.get("rsi14", np.nan))
    macd_hist = float(last.get("macd_hist", np.nan))
    return {
        "mom20": mom20,
        "vol20": vol20,
        "avg_vol20": avg_vol20,
        "rsi14": rsi14,
        "macd_hist": macd_hist,
    }


def _rank_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    s = series.copy()
    s = s.replace([np.inf, -np.inf], np.nan)
    if higher_is_better:
        return s.rank(pct=True, ascending=True)
    return s.rank(pct=True, ascending=False)


def score_factors(
    settings,
    stock_codes: list[str] | None,
    as_of: date | None,
    lookback_days: int,
    top_n: int,
    limit: int,
) -> dict[str, Any]:
    codes = stock_codes or list_stock_codes(settings, limit=limit)
    end = as_of or date.today()
    start = end - timedelta(days=int(lookback_days))

    rows: list[dict[str, Any]] = []
    for code in codes:
        df = load_daily_ohlcv(settings, code, start=start, end=end)
        factors = _calc_factors(df)
        if not factors:
            continue
        rows.append({"stock_code": code, **factors})

    if not rows:
        return {"as_of": end.isoformat(), "rows": [], "top": []}

    fdf = pd.DataFrame(rows)
    cfg = {
        "mom20": {"weight": 0.35, "higher_is_better": True},
        "vol20": {"weight": 0.20, "higher_is_better": False},
        "avg_vol20": {"weight": 0.15, "higher_is_better": True},
        "rsi14": {"weight": 0.15, "higher_is_better": False},
        "macd_hist": {"weight": 0.15, "higher_is_better": True},
    }

    score = pd.Series(0.0, index=fdf.index, dtype="float64")
    for col, meta in cfg.items():
        if col not in fdf.columns:
            continue
        r = _rank_score(fdf[col].astype(float), higher_is_better=bool(meta["higher_is_better"]))
        score += float(meta["weight"]) * r.fillna(0.0)

    fdf["score"] = (score * 100.0).round(2)
    fdf = fdf.sort_values("score", ascending=False).reset_index(drop=True)

    top = fdf.head(int(top_n)).to_dict(orient="records")
    return {"as_of": end.isoformat(), "rows": fdf.to_dict(orient="records"), "top": top}

