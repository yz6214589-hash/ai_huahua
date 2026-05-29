# -*- coding: utf-8 -*-
"""
回测引擎模块
基于 Backtrader 框架执行策略回测，支持自定义买卖佣金率、滑点、
基准净值对比、回撤序列和月度收益等增强功能
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    nav_log: list[dict[str, Any]]
    benchmark_nav_log: list[dict[str, Any]] = None
    drawdown_log: list[dict[str, Any]] = None
    monthly_returns: list[dict[str, Any]] = None

    def __post_init__(self):
        # 处理 frozen dataclass 的默认值
        if self.benchmark_nav_log is None:
            object.__setattr__(self, "benchmark_nav_log", [])
        if self.drawdown_log is None:
            object.__setattr__(self, "drawdown_log", [])
        if self.monthly_returns is None:
            object.__setattr__(self, "monthly_returns", [])


def _extract_trades(strat: Any) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    if not hasattr(strat, "_trade_log"):
        return trades
    for t in getattr(strat, "_trade_log", []) or []:
        if isinstance(t, dict):
            trades.append(t)
    return trades


def _extract_nav_log(strat: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not hasattr(strat, "_nav_log"):
        return out
    for row in getattr(strat, "_nav_log", []) or []:
        if isinstance(row, dict):
            out.append(row)
    return out


def run_backtest(
    df: pd.DataFrame,
    strategy_cls: Any,
    strategy_params: dict[str, Any],
    initial_cash: float = 100000.0,
    commission: float = 0.001,
    requires_weekly: bool = False,
    commission_buy: float = 0.0003,
    commission_sell: float = 0.0013,
    slippage_pct: float = 0.0,
    slippage_fixed: float = 0.0,
    min_commission: float = 5.0,
) -> BacktestResult:
    """
    执行 Backtrader 回测

    Args:
        df: 日线数据 DataFrame
        strategy_cls: 策略类
        strategy_params: 策略参数字典
        initial_cash: 初始资金
        commission: 统一佣金率（向后兼容，当 commission_buy/commission_sell 未使用时生效）
        requires_weekly: 是否需要周线数据
        commission_buy: 买入佣金率，默认0.0003
        commission_sell: 卖出佣金率（含印花税），默认0.0013
        slippage_pct: 滑点百分比，默认0.0
        slippage_fixed: 固定滑点，默认0.0
        min_commission: 最低手续费，默认5.0

    Returns:
        BacktestResult 回测结果
    """
    try:
        import backtrader as bt  # type: ignore
    except Exception as e:
        return BacktestResult(metrics={"error": "backtrader_missing", "detail": str(e)}, trades=[], nav_log=[])

    if df.empty:
        return BacktestResult(metrics={"error": "empty_data"}, trades=[], nav_log=[])

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

    # 双费率佣金方案：买入和卖出使用不同佣金率
    class DualRateCommission(bt.CommInfoBase):
        params = (
            ("commission_buy", 0.0003),
            ("commission_sell", 0.0013),
            ("min_commission", 5.0),
            ("stocklike", True),
            ("commtype", bt.CommInfoBase.COMM_PERC),
        )

        def _getcommission(self, size, price, pseudoexec):
            comm = abs(size) * price * (self.p.commission_buy if size > 0 else self.p.commission_sell)
            return max(comm, self.p.min_commission)

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(float(initial_cash))

    # 设置双费率佣金（替换原来的统一佣金）
    comm_scheme = DualRateCommission(
        commission_buy=float(commission_buy),
        commission_sell=float(commission_sell),
        min_commission=float(min_commission),
    )
    cerebro.broker.addcommissioninfo(comm_scheme)

    # 保留旧的 setcommission 作为兜底（向后兼容）
    # 如果 DualRateCommission 没有生效，统一佣金仍然有效
    cerebro.broker.setcommission(commission=float(commission))

    # 设置滑点
    if slippage_pct > 0:
        cerebro.broker.set_slippage_perc(slippage_pct)
    elif slippage_fixed > 0:
        cerebro.broker.set_slippage_fixed(slippage_fixed)

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
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._trade_log: list[dict[str, Any]] = []
            self._nav_log: list[dict[str, Any]] = []
            self._entry_cache: dict[int, dict[str, Any]] = {}

        def notify_trade(self, trade: Any) -> None:
            dt = self.data.datetime.date(0).isoformat()
            tid = id(trade)
            if trade.justopened:
                entry_price = round(float(trade.price), 4)
                entry_size = abs(int(trade.size))
                self._entry_cache[tid] = {
                    "entry_price": entry_price,
                    "entry_size": entry_size,
                }
                self._trade_log.append(
                    {
                        "trade_date": dt,
                        "action": "buy",
                        "price": entry_price,
                        "size": entry_size,
                        "cost": round(entry_price * entry_size, 2),
                        "proceeds": 0,
                        "pnl": 0.0,
                        "pnlcomm": 0.0,
                    }
                )
            if trade.isclosed:
                info = self._entry_cache.pop(tid, None)
                if info:
                    entry_price = info["entry_price"]
                    entry_size = info["entry_size"]
                    pnl = float(trade.pnl)
                    exit_price = round(entry_price + pnl / entry_size, 4) if entry_size > 0 else 0.0
                    proceeds = round(exit_price * entry_size, 2)
                else:
                    exit_price = 0.0
                    entry_size = 0
                    proceeds = 0.0
                self._trade_log.append(
                    {
                        "trade_date": dt,
                        "action": "sell",
                        "price": exit_price,
                        "size": entry_size,
                        "cost": 0,
                        "proceeds": proceeds,
                        "pnl": float(trade.pnl),
                        "pnlcomm": float(trade.pnlcomm),
                    }
                )

        def next(self) -> None:
            try:
                dt = self.data.datetime.date(0).isoformat()
                nav = float(self.broker.getvalue())
                if not self._nav_log or self._nav_log[-1].get("date") != dt:
                    self._nav_log.append({"date": dt, "nav": nav})
            except Exception:
                pass
            return super().next()

    filtered_params = {}
    for k, v in (strategy_params or {}).items():
        try:
            if hasattr(strategy_cls, 'params') and hasattr(strategy_cls.params, k):
                filtered_params[k] = v
            elif not hasattr(strategy_cls, 'params'):
                filtered_params[k] = v
        except Exception:
            pass

    cerebro.addstrategy(_Wrapped, **filtered_params)

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

    # 提取每笔交易的盈亏金额，供后续指标计算使用
    trades_pnl = [float(t.get("pnlcomm", 0)) for t in _extract_trades(strat)]

    metrics = {
        "start_value": float(start_value),
        "end_value": float(end_value),
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe": float(sharpe.get("sharperatio") or np.nan) if isinstance(sharpe, dict) else np.nan,
        "max_drawdown": float(max_dd),
        "total_trades": total_trades,
        "won": won,
        "lost": lost,
        "win_rate": float(win_rate),
        "_trades_pnl": trades_pnl,
    }

    # 计算回撤序列和月度收益
    nav_log = _extract_nav_log(strat)
    from core.strategy.metrics_calculator import calc_drawdown_log, calc_monthly_returns
    drawdown_log = calc_drawdown_log(nav_log)
    monthly_returns = calc_monthly_returns(nav_log)

    return BacktestResult(
        metrics=metrics,
        trades=_extract_trades(strat),
        nav_log=nav_log,
        benchmark_nav_log=[],
        drawdown_log=drawdown_log,
        monthly_returns=monthly_returns,
    )
