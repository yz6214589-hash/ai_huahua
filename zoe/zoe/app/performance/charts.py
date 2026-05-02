from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _to_iso_dates(idx: pd.DatetimeIndex) -> list[str]:
    return [d.date().isoformat() for d in idx.to_pydatetime()]


def _nan_to_none(x: float) -> float | None:
    if x is None:
        return None
    if isinstance(x, (float, np.floating)) and (math.isnan(float(x)) or math.isinf(float(x))):
        return None
    return float(x)


def compute_chart_series(returns: pd.Series, rolling_window: int = 60) -> dict[str, Any]:
    if returns is None:
        raise ValueError("returns is required")
    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    r = r.sort_index()
    r = r.astype(float).fillna(0.0)

    nav = (1.0 + r).cumprod()
    cum_return = nav - 1.0

    peak = nav.cummax()
    drawdown = (nav / peak) - 1.0

    roll_mean = r.rolling(rolling_window).mean()
    roll_std = r.rolling(rolling_window).std(ddof=0)
    rolling_sharpe = (roll_mean / roll_std) * np.sqrt(252.0)

    monthly = (1.0 + r).resample("ME").prod() - 1.0
    monthly = monthly.dropna()
    years = sorted({int(d.year) for d in monthly.index})
    months = list(range(1, 13))
    year_pos = {y: i for i, y in enumerate(years)}
    month_pos = {m: i for i, m in enumerate(months)}
    heat_values: list[list[Any]] = []
    for dt, v in monthly.items():
        y = int(pd.to_datetime(dt).year)
        m = int(pd.to_datetime(dt).month)
        if y not in year_pos or m not in month_pos:
            continue
        heat_values.append([month_pos[m], year_pos[y], float(v)])

    return {
        "dates": _to_iso_dates(r.index),
        "nav": [float(x) for x in nav.to_numpy()],
        "cum_return": [float(x) for x in cum_return.to_numpy()],
        "drawdown": [float(x) for x in drawdown.to_numpy()],
        "rolling_sharpe": [_nan_to_none(x) for x in rolling_sharpe.to_numpy()],
        "heatmap": {"years": years, "months": months, "values": heat_values},
    }
