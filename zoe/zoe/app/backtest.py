from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]


def _extract_trades(strat: Any) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    if not hasattr(strat, "_trade_log"):
        return trades
    for t in getattr(strat, "_trade_log", []) or []:
        if isinstance(t, dict):
            trades.append(t)
    return trades


def run_backtest(
    df: pd.DataFrame,
    strategy_cls: Any,
    strategy_params: dict[str, Any],
    initial_cash: float = 100000.0,
    commission: float = 0.001,
    requires_weekly: bool = False,
) -> BacktestResult:
    try:
        import backtrader as bt  # type: ignore
    except Exception as e:
        return BacktestResult(metrics={"error": "backtrader_missing", "detail": str(e)}, trades=[])

    if df.empty:
        return BacktestResult(metrics={"error": "empty_data"}, trades=[])

    data_df = df.copy()
    if "trade_date" not in data_df.columns:
        raise ValueError("trade_date missing")
    data_df["trade_date"] = pd.to_datetime(data_df["trade_date"])
    data_df = data_df.sort_values("trade_date").reset_index(drop=True)

    class PandasDaily(bt.feeds.PandasData):
        lines = ("chan_signal", "chan_zg", "chan_zd")
        params = (
            ("datetime", "trade_date"),
            ("open", "open"),
            ("high", "high"),
            ("low", "low"),
            ("close", "close"),
            ("volume", "volume"),
            ("chan_signal", "chan_signal"),
            ("chan_zg", "chan_zg"),
            ("chan_zd", "chan_zd"),
            ("openinterest", -1),
        )

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(float(initial_cash))
    cerebro.broker.setcommission(commission=float(commission))
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", timeframe=bt.TimeFrame.Days, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="rets")

    for col in ["chan_signal", "chan_zg", "chan_zd"]:
        if col not in data_df.columns:
            data_df[col] = np.nan

    feed = PandasDaily(dataname=data_df)
    cerebro.adddata(feed)
    if bool(requires_weekly):
        cerebro.resampledata(feed, timeframe=bt.TimeFrame.Weeks, compression=1)

    class _Wrapped(strategy_cls):  # type: ignore[misc,valid-type]
        def __init__(self) -> None:
            super().__init__()
            self._trade_log: list[dict[str, Any]] = []

        def notify_trade(self, trade: Any) -> None:
            if not trade.isclosed:
                return
            dt = self.data.datetime.date(0).isoformat()
            self._trade_log.append(
                {
                    "trade_date": dt,
                    "pnl": float(trade.pnl),
                    "pnlcomm": float(trade.pnlcomm),
                    "size": float(trade.size),
                }
            )

    cerebro.addstrategy(_Wrapped, **(strategy_params or {}))

    start_value = cerebro.broker.getvalue()
    results = cerebro.run()
    strat = results[0]
    end_value = cerebro.broker.getvalue()

    sharpe = strat.analyzers.sharpe.get_analysis()
    dd = strat.analyzers.dd.get_analysis()
    trades = strat.analyzers.trades.get_analysis()
    rets = strat.analyzers.rets.get_analysis()

    total_return = (end_value / start_value) - 1.0 if start_value else 0.0
    annual_return = float(rets.get("rnorm100", 0.0)) / 100.0
    max_dd = float(dd.get("max", {}).get("drawdown", 0.0)) / 100.0

    total_trades = int(trades.get("total", {}).get("total", 0) or 0)
    won = int(trades.get("won", {}).get("total", 0) or 0)
    lost = int(trades.get("lost", {}).get("total", 0) or 0)
    win_rate = (won / total_trades) if total_trades else 0.0

    metrics = {
        "start_value": float(start_value),
        "end_value": float(end_value),
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe": float(sharpe.get("sharperatio", np.nan)) if isinstance(sharpe, dict) else np.nan,
        "max_drawdown": float(max_dd),
        "total_trades": total_trades,
        "won": won,
        "lost": lost,
        "win_rate": float(win_rate),
    }

    return BacktestResult(metrics=metrics, trades=_extract_trades(strat))

