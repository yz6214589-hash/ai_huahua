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
    kline: list[dict[str, Any]] = None
    indicator_data: dict[str, Any] = None

    def __post_init__(self):
        # 处理 frozen dataclass 的默认值
        if self.benchmark_nav_log is None:
            object.__setattr__(self, "benchmark_nav_log", [])
        if self.drawdown_log is None:
            object.__setattr__(self, "drawdown_log", [])
        if self.monthly_returns is None:
            object.__setattr__(self, "monthly_returns", [])
        if self.kline is None:
            object.__setattr__(self, "kline", [])
        if self.indicator_data is None:
            object.__setattr__(self, "indicator_data", {})


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
    position_pct: float = 0.95,
    stamp_duty: float = 0.001,
    transfer_fee_buy: float = 0.00001,
    transfer_fee_sell: float = 0.00001,
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
        commission_sell: 卖出佣金率，默认0.0013
        slippage_pct: 滑点百分比，默认0.0
        slippage_fixed: 固定滑点，默认0.0
        min_commission: 最低手续费，默认5.0
        position_pct: 仓位比例，范围 0.01 ~ 1.0，默认 0.95
        stamp_duty: 印花税费率，卖出时收取，默认千分之一
        transfer_fee_buy: 买入过户费率，默认十万分之一
        transfer_fee_sell: 卖出过户费率，默认十万分之一

    Returns:
        BacktestResult 回测结果
    """
    try:
        import backtrader as bt  # type: ignore
    except Exception as e:
        return BacktestResult(metrics={"error": "backtrader_missing", "detail": str(e)}, trades=[], nav_log=[])

    if df.empty:
        return BacktestResult(metrics={"error": "empty_data"}, trades=[], nav_log=[])

    # 校验仓位比例范围
    if not (0.01 <= position_pct <= 1.0):
        raise ValueError(f"仓位比例 position_pct 必须在 0.01 ~ 1.0 之间，当前为 {position_pct}")

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

    # 多费率佣金方案：买入佣金、卖出佣金、印花税、过户费分开计算
    class DualRateCommission(bt.CommInfoBase):
        params = (
            ("commission_buy", 0.0003),
            ("commission_sell", 0.0013),
            ("stamp_duty", 0.001),
            ("transfer_fee_buy", 0.00001),
            ("transfer_fee_sell", 0.00001),
            ("min_commission", 5.0),
            ("stocklike", True),
            ("commtype", bt.CommInfoBase.COMM_PERC),
        )

        def _getcommission(self, size, price, pseudoexec):
            abs_size = abs(size)
            abs_price = abs(price)
            # 佣金：受最低佣金约束
            comm_rate = self.p.commission_buy if size > 0 else self.p.commission_sell
            commission = max(abs_size * abs_price * comm_rate, self.p.min_commission)
            # 印花税（仅卖出时收取）
            stamp = abs_size * abs_price * self.p.stamp_duty if size < 0 else 0.0
            # 过户费（买入和卖出都收取）
            transfer = abs_size * abs_price * (self.p.transfer_fee_buy if size > 0 else self.p.transfer_fee_sell)
            return commission + stamp + transfer

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(float(initial_cash))

    # 设置多费率佣金方案
    comm_scheme = DualRateCommission(
        commission_buy=float(commission_buy),
        commission_sell=float(commission_sell),
        stamp_duty=float(stamp_duty),
        transfer_fee_buy=float(transfer_fee_buy),
        transfer_fee_sell=float(transfer_fee_sell),
        min_commission=float(min_commission),
    )
    cerebro.broker.addcommissioninfo(comm_scheme)

    # 注意：DualRateCommission 已通过 addcommissioninfo 注册
    # 无需再调用 setcommission，否则会覆盖双费率设置

    # 设置滑点
    if slippage_pct > 0:
        cerebro.broker.set_slippage_perc(slippage_pct)
    elif slippage_fixed > 0:
        cerebro.broker.set_slippage_fixed(slippage_fixed)

    cerebro.addsizer(bt.sizers.PercentSizer, percents=int(position_pct * 100))

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
            # 使用 FIFO 队列替代 id(trade) 字典缓存，因为 backtrader 的 Trade 对象
            # 在 justopened 和 isclosed 两次回调中可能不是同一个实例，导致 id(trade) 不一致
            self._entry_queue: list[dict[str, Any]] = []

        def _calc_fee_breakdown(self, size: int, price: float, is_buy: bool) -> str:
            abs_size = abs(size)
            abs_price = abs(price)
            comm_rate = commission_buy if is_buy else commission_sell
            trf_rate = transfer_fee_buy if is_buy else transfer_fee_sell
            comm = max(abs_size * abs_price * comm_rate, min_commission)
            stamp = abs_size * abs_price * stamp_duty if not is_buy else 0.0
            transfer = abs_size * abs_price * trf_rate
            total = comm + stamp + transfer
            if is_buy:
                parts = [f"{comm:.2f}(买入佣金)", f"{transfer:.2f}(买入过户费)"]
            else:
                parts = [f"{comm:.2f}(卖出佣金)", f"{stamp:.2f}(印花税)", f"{transfer:.2f}(卖出过户费)"]
            return f"{total:.2f}={'+'.join(parts)}"

        def notify_trade(self, trade: Any) -> None:
            dt = self.data.datetime.date(0).isoformat()
            if trade.justopened:
                entry_price = round(float(trade.price), 4)
                entry_size = abs(int(trade.size))
                # 推入 FIFO 队列，按顺序匹配后续的卖出
                self._entry_queue.append({
                    "entry_price": entry_price,
                    "entry_size": entry_size,
                })
                fee_detail = self._calc_fee_breakdown(trade.size, trade.price, is_buy=True)
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
                        "fee_detail": fee_detail,
                    }
                )
            if trade.isclosed:
                # 从 FIFO 队列中弹出最早匹配的买入记录（先进先出）
                info = self._entry_queue.pop(0) if self._entry_queue else None
                pnl = float(trade.pnl)

                if info:
                    entry_price = info["entry_price"]
                    entry_size = info["entry_size"]
                    # 主计算：exit_price = entry_price + pnl / entry_size
                    exit_price = round(entry_price + pnl / entry_size, 4) if entry_size > 0 else 0.0
                    proceeds = round(exit_price * entry_size, 2)
                else:
                    # 兜底：直接从 trade 对象获取（trade.price 和 trade.size 本身是可靠的）
                    entry_price = abs(float(trade.price))
                    entry_size = abs(int(trade.size))
                    exit_price = round(entry_price + pnl / entry_size, 4) if entry_size > 0 else 0.0
                    proceeds = round(exit_price * entry_size, 2)

                # 卖出时，trade.price 可能不可靠，改用计算出的 exit_price 和 entry_size
                fee_detail = self._calc_fee_breakdown(-entry_size, exit_price, is_buy=False)
                self._trade_log.append(
                    {
                        "trade_date": dt,
                        "action": "sell",
                        "price": exit_price,
                        "size": entry_size,
                        "cost": 0,
                        "proceeds": proceeds,
                        "pnl": pnl,
                        "pnlcomm": float(trade.pnlcomm),
                        "fee_detail": fee_detail,
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

    # 检查是否有未平仓的买入（待卖）
    pending_entries = list(strat._entry_queue)
    if pending_entries:
        last_date = data_df["trade_date"].iloc[-1]
        if hasattr(last_date, "strftime"):
            last_date = last_date.strftime("%Y-%m-%d")
        elif hasattr(last_date, "isoformat"):
            last_date = last_date.isoformat()[:10]
        else:
            last_date = str(last_date)[:10]
        last_close = float(data_df["close"].iloc[-1])
        for entry in pending_entries:
            entry_price = entry["entry_price"]
            entry_size = entry["entry_size"]
            market_value = round(last_close * entry_size, 2)
            unrealized_pnl = round((last_close - entry_price) * entry_size, 2)
            strat._trade_log.append({
                "trade_date": last_date,
                "action": "pending_sell",
                "price": last_close,
                "size": entry_size,
                "cost": 0,
                "proceeds": market_value,
                "pnl": unrealized_pnl,
                "pnlcomm": 0.0,
                "fee_detail": f"待卖（最新收盘价 {last_close:.2f}，市值 {market_value:.2f}）",
            })

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

    # 构建 K 线数据
    kline_data = []
    for _, row in data_df.iterrows():
        dt_val = row.get("trade_date", "")
        if hasattr(dt_val, "strftime"):
            dt_str = dt_val.strftime("%Y-%m-%d")
        else:
            dt_str = str(dt_val)[:10]
        kline_data.append({
            "date": dt_str,
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
        })

    # 提取策略专属指标数据（布林带/RSI）
    indicator_data = {}
    closes_series = data_df["close"]

    if hasattr(strat, "bb"):
        try:
            period = int(strat.bb.p.period)
            devfactor = float(strat.bb.p.devfactor)
            bb_mid = closes_series.rolling(window=period, min_periods=period).mean()
            bb_std = closes_series.rolling(window=period, min_periods=period).std(ddof=0)
            bb_top = bb_mid + devfactor * bb_std
            bb_bot = bb_mid - devfactor * bb_std
            values = []
            for i in range(len(data_df)):
                if pd.isna(bb_mid.iloc[i]):
                    values.append(None)
                else:
                    values.append({
                        "mid": round(float(bb_mid.iloc[i]), 4),
                        "top": round(float(bb_top.iloc[i]), 4),
                        "bot": round(float(bb_bot.iloc[i]), 4),
                    })
            indicator_data["bollinger"] = {"values": values}
        except Exception:
            pass

    if hasattr(strat, "rsi"):
        try:
            period = int(strat.rsi.p.period)
            delta = closes_series.diff()
            gains = delta.clip(lower=0)
            losses = -delta.clip(upper=0)
            avg_gain = gains.ewm(alpha=1.0 / period, adjust=False).mean()
            avg_loss = losses.ewm(alpha=1.0 / period, adjust=False).mean()
            rs = avg_gain / avg_loss
            rsi_values = 100.0 - (100.0 / (1.0 + rs))
            rsi_list = []
            for i in range(len(data_df)):
                if i == 0 or pd.isna(rsi_values.iloc[i]):
                    rsi_list.append(None)
                else:
                    rsi_list.append(round(float(rsi_values.iloc[i]), 2))
            indicator_data["rsi"] = {"values": rsi_list}
        except Exception:
            pass

    return BacktestResult(
        metrics=metrics,
        trades=_extract_trades(strat),
        nav_log=nav_log,
        benchmark_nav_log=[],
        drawdown_log=drawdown_log,
        monthly_returns=monthly_returns,
        kline=kline_data,
        indicator_data=indicator_data,
    )
