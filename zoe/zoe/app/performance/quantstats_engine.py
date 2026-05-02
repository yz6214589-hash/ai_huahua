from __future__ import annotations

from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import quantstats as qs


def _safe(func: Any, *args: Any, default: float = 0.0, **kwargs: Any) -> float:
    try:
        v = func(*args, **kwargs)
        if v is None:
            return float(default)
        fv = float(v)
        if np.isnan(fv) or np.isinf(fv):
            return float(default)
        return fv
    except Exception:
        return float(default)


def calc_quantstats_metrics(returns: pd.Series, benchmark: pd.Series | None = None) -> dict[str, Any]:
    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    r = r.sort_index()
    r = r.astype(float).fillna(0.0)

    metrics: dict[str, Any] = {}

    metrics["total_return"] = _safe(qs.stats.comp, r)
    metrics["cagr"] = _safe(qs.stats.cagr, r)
    metrics["best_day"] = float(r.max()) if len(r) else 0.0
    metrics["worst_day"] = float(r.min()) if len(r) else 0.0

    metrics["volatility"] = _safe(qs.stats.volatility, r)
    metrics["max_drawdown"] = _safe(qs.stats.max_drawdown, r)
    metrics["var_95"] = _safe(qs.stats.value_at_risk, r)
    metrics["cvar_95"] = _safe(qs.stats.cvar, r)

    metrics["sharpe"] = _safe(qs.stats.sharpe, r)
    metrics["sortino"] = _safe(qs.stats.sortino, r)
    metrics["calmar"] = _safe(qs.stats.calmar, r)
    metrics["omega"] = _safe(qs.stats.omega, r, default=1.0)
    metrics["gain_to_pain"] = _safe(qs.stats.gain_to_pain_ratio, r)

    metrics["skew"] = _safe(qs.stats.skew, r)
    metrics["kurtosis"] = _safe(qs.stats.kurtosis, r)

    metrics["win_rate"] = _safe(qs.stats.win_rate, r, default=0.5)
    metrics["avg_win"] = _safe(qs.stats.avg_win, r)
    metrics["avg_loss"] = _safe(qs.stats.avg_loss, r)
    metrics["profit_factor"] = _safe(qs.stats.profit_factor, r, default=1.0)
    metrics["payoff_ratio"] = _safe(qs.stats.payoff_ratio, r, default=1.0)

    metrics["consecutive_wins"] = int(_safe(qs.stats.consecutive_wins, r, default=0.0))
    metrics["consecutive_losses"] = int(_safe(qs.stats.consecutive_losses, r, default=0.0))

    if benchmark is not None:
        b = benchmark.copy()
        b.index = pd.to_datetime(b.index)
        b = b.sort_index()
        b = b.astype(float).fillna(0.0)
        common_idx = r.index.intersection(b.index)
        if len(common_idx) > 20:
            rr = r.loc[common_idx]
            bb = b.loc[common_idx]
            metrics["information_ratio"] = _safe(qs.stats.information_ratio, rr, bb)
            metrics["alpha"] = float(rr.mean() * 252.0 - bb.mean() * 252.0)
            cov = np.cov(rr.to_numpy(), bb.to_numpy())
            metrics["beta"] = float(cov[0, 1] / cov[1, 1]) if float(cov[1, 1]) > 0 else 0.0
            metrics["tracking_error"] = float((rr - bb).std() * np.sqrt(252.0))

    return metrics
