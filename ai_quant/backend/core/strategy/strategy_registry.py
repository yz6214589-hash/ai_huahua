from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StrategyMeta:
    strategy_id: str
    name: str
    description: str
    params_schema: dict[str, Any]
    default_params: dict[str, Any]
    bt_strategy_factory: Any
    requires_weekly: bool = False
    requires_chan: bool = False
    requires_predictions: bool = False
    group: str = "basic"  # 策略分组 "basic" | "optimized" | "combo"


def _p_int(label: str, help: str, min_v: int | None = None, max_v: int | None = None, *, section: str | None = None, show_if: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "int", "label": label, "help": help}
    if min_v is not None:
        d["min"] = int(min_v)
    if max_v is not None:
        d["max"] = int(max_v)
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _p_float(
    label: str,
    help: str,
    min_v: float | None = None,
    max_v: float | None = None,
    step: float | None = None,
    *,
    section: str | None = None,
    show_if: dict | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "float", "label": label, "help": help}
    if min_v is not None:
        d["min"] = float(min_v)
    if max_v is not None:
        d["max"] = float(max_v)
    if step is not None:
        d["step"] = float(step)
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _p_bool(label: str, help: str, *, section: str | None = None, show_if: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "bool", "label": label, "help": help}
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _p_select(label: str, help: str, options: list[dict], *, section: str | None = None, show_if: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "select", "label": label, "help": help, "options": options}
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _p_enum(label: str, help: str, values: list[str], *, section: str | None = None, show_if: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "enum", "label": label, "help": help, "values": list(values)}
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _p_object(label: str, help: str, *, section: str | None = None, show_if: dict | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "object", "label": label, "help": help}
    if section is not None:
        d["section"] = section
    if show_if is not None:
        d["show_if"] = show_if
    return d


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _make_dual_ma():
    import backtrader as bt  # type: ignore

    class DualMAStrategy(bt.Strategy):
        params = dict(fast=10, slow=30)

        def __init__(self) -> None:
            fast_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=int(self.p.fast))
            slow_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=int(self.p.slow))
            self.crossover = bt.indicators.CrossOver(fast_ma, slow_ma)

        def next(self) -> None:
            if not self.position and self.crossover[0] > 0:
                self.buy()
                return
            if self.position and self.crossover[0] < 0:
                self.sell()

    return DualMAStrategy


def _make_macd_basic():
    import backtrader as bt  # type: ignore

    class MACDStrategy(bt.Strategy):
        params = dict(fast=12, slow=26, signal=9)

        def __init__(self) -> None:
            self.macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.fast),
                period_me2=int(self.p.slow),
                period_signal=int(self.p.signal),
            )
            self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

        def next(self) -> None:
            if not self.position and self.crossover[0] > 0:
                self.buy()
                return
            if self.position and self.crossover[0] < 0:
                self.sell()

    return MACDStrategy


def _make_rsi_basic():
    import backtrader as bt  # type: ignore

    class RSIStrategy(bt.Strategy):
        params = dict(period=14, oversold=30, overbought=70)

        def __init__(self) -> None:
            self.rsi = bt.indicators.RSI(self.data.close, period=int(self.p.period))

        def next(self) -> None:
            if not self.position and self.rsi[0] < float(self.p.oversold):
                self.buy()
                return
            if self.position and self.rsi[0] > float(self.p.overbought):
                self.sell()

    return RSIStrategy


def _make_boll_basic():
    import backtrader as bt  # type: ignore

    class BollingerStrategy(bt.Strategy):
        params = dict(period=20, devfactor=2.0)

        def __init__(self) -> None:
            self.bb = bt.indicators.BollingerBands(self.data.close, period=int(self.p.period), devfactor=float(self.p.devfactor))

        def next(self) -> None:
            if not self.position and self.data.close[0] < self.bb.bot[0]:
                self.buy()
                return
            if self.position and self.data.close[0] > self.bb.top[0]:
                self.sell()

    return BollingerStrategy


def _make_bias():
    import backtrader as bt  # type: ignore

    class BiasStrategy(bt.Strategy):
        params = dict(period=20, buy_threshold=-6.0, sell_threshold=3.0)

        def __init__(self) -> None:
            self.ma = bt.indicators.SimpleMovingAverage(self.data.close, period=int(self.p.period))

        def next(self) -> None:
            ma = float(self.ma[0])
            if ma == 0:
                return
            bias = (float(self.data.close[0]) - ma) / ma * 100.0
            if not self.position and bias < float(self.p.buy_threshold):
                self.buy()
                return
            if self.position and bias > float(self.p.sell_threshold):
                self.sell()

    return BiasStrategy


def _make_momentum():
    import backtrader as bt  # type: ignore

    class MomentumStrategy(bt.Strategy):
        params = dict(period=20, threshold=5.0)

        def __init__(self) -> None:
            self.roc = bt.indicators.ROC100(self.data.close, period=int(self.p.period))

        def next(self) -> None:
            th = float(self.p.threshold)
            if not self.position and float(self.roc[0]) > th:
                self.buy()
                return
            if self.position and float(self.roc[0]) < -th:
                self.sell()

    return MomentumStrategy


def _make_rsi_cross_confirm():
    import backtrader as bt  # type: ignore

    class RSICrossConfirm(bt.Strategy):
        params = dict(period=14, oversold=30, overbought=70)

        def __init__(self) -> None:
            self.rsi = bt.indicators.RSI(self.data.close, period=int(self.p.period))
            self.cross = bt.indicators.CrossOver(self.rsi, float(self.p.oversold))

        def next(self) -> None:
            if not self.position and self.cross[0] > 0:
                self.buy()
                return
            if self.position and float(self.rsi[0]) > float(self.p.overbought):
                self.sell()

    return RSICrossConfirm


def _make_macd_vol_confirm():
    import backtrader as bt  # type: ignore

    class MACDVolConfirm(bt.Strategy):
        params = dict(fast=12, slow=26, signal=9, vol_period=20, vol_mult=0.9)

        def __init__(self) -> None:
            self.macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.fast),
                period_me2=int(self.p.slow),
                period_signal=int(self.p.signal),
            )
            self.cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
            self.vol_ma = bt.indicators.SimpleMovingAverage(self.data.volume, period=int(self.p.vol_period))

        def next(self) -> None:
            vol_ok = float(self.data.volume[0]) > float(self.vol_ma[0]) * float(self.p.vol_mult)
            if not self.position and self.cross[0] > 0 and vol_ok:
                self.buy()
                return
            if self.position and self.cross[0] < 0:
                self.sell()

    return MACDVolConfirm


def _make_macd_profit_lock():
    import backtrader as bt  # type: ignore

    class MACDProfitLock(bt.Strategy):
        params = dict(fast=12, slow=26, signal=9, profit_trigger=5.0, trail_pct=3.0)

        def __init__(self) -> None:
            self.macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.fast),
                period_me2=int(self.p.slow),
                period_signal=int(self.p.signal),
            )
            self.cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
            self.entry_price = None
            self.peak_price = None

        def next(self) -> None:
            close = float(self.data.close[0])

            if not self.position:
                if self.cross[0] > 0:
                    self.buy()
                    self.entry_price = close
                    self.peak_price = close
                return

            if self.entry_price is None:
                self.entry_price = close
            if self.peak_price is None:
                self.peak_price = close
            self.peak_price = max(float(self.peak_price), close)

            if self.cross[0] < 0:
                self.sell()
                self.entry_price = None
                self.peak_price = None
                return

            if self.entry_price > 0 and self.peak_price > 0:
                profit_pct = (close - float(self.entry_price)) / float(self.entry_price) * 100.0
                drop_pct = (float(self.peak_price) - close) / float(self.peak_price) * 100.0
                if profit_pct >= float(self.p.profit_trigger) and drop_pct >= float(self.p.trail_pct):
                    self.sell()
                    self.entry_price = None
                    self.peak_price = None

    return MACDProfitLock


def _make_boll_mid_stop():
    import backtrader as bt  # type: ignore

    class BollMidStop(bt.Strategy):
        params = dict(period=20, devfactor=2.0)

        def __init__(self) -> None:
            self.bb = bt.indicators.BollingerBands(self.data.close, period=int(self.p.period), devfactor=float(self.p.devfactor))
            self.bounced = False

        def next(self) -> None:
            close = float(self.data.close[0])
            if not self.position:
                self.bounced = False
                if close <= float(self.bb.bot[0]):
                    self.buy()
                return

            if close >= float(self.bb.top[0]):
                self.sell()
                self.bounced = False
                return

            if close > float(self.bb.mid[0]):
                self.bounced = True

            if self.bounced and close < float(self.bb.mid[0]):
                self.sell()
                self.bounced = False

    return BollMidStop


def _make_adaptive():
    import backtrader as bt  # type: ignore

    class AdaptiveStrategy(bt.Strategy):
        params = dict(
            adx_period=14,
            adx_trend=25,
            adx_range=20,
            atr_period=14,
            atr_mult=2.0,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            rsi_period=14,
            oversold=30,
            overbought=70,
        )

        def __init__(self) -> None:
            self.adx = bt.indicators.ADX(self.data, period=int(self.p.adx_period))
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.macd_fast),
                period_me2=int(self.p.macd_slow),
                period_signal=int(self.p.macd_signal),
            )
            self.macd_cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
            self.rsi = bt.indicators.RSI(self.data.close, period=int(self.p.rsi_period))

            self.mode = None
            self.stop_price = None

        def next(self) -> None:
            close = float(self.data.close[0])
            atr = float(self.atr[0])
            adx = float(self.adx[0])

            if self.position and atr > 0:
                candidate = close - float(self.p.atr_mult) * atr
                self.stop_price = max(float(self.stop_price or candidate), candidate)
                if close < float(self.stop_price):
                    self.sell()
                    self.mode = None
                    self.stop_price = None
                    return

            if not self.position:
                if adx > float(self.p.adx_trend):
                    if self.macd_cross[0] > 0:
                        self.buy()
                        self.mode = "trend"
                        self.stop_price = close - float(self.p.atr_mult) * atr if atr > 0 else None
                elif adx < float(self.p.adx_range):
                    if float(self.rsi[0]) < float(self.p.oversold):
                        self.buy()
                        self.mode = "range"
                        self.stop_price = close - float(self.p.atr_mult) * atr if atr > 0 else None
                return

            if self.mode == "trend" and self.macd_cross[0] < 0:
                self.sell()
                self.mode = None
                self.stop_price = None
                return
            if self.mode == "range" and float(self.rsi[0]) > float(self.p.overbought):
                self.sell()
                self.mode = None
                self.stop_price = None

    return AdaptiveStrategy


def _make_macd_divergence():
    import backtrader as bt  # type: ignore

    class MACDDivergence(bt.Strategy):
        params = dict(lookback=30, fast=12, slow=26, signal=9)

        def __init__(self) -> None:
            self.macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.fast),
                period_me2=int(self.p.slow),
                period_signal=int(self.p.signal),
            )
            self.price_low = bt.indicators.Lowest(self.data.low, period=int(self.p.lookback))
            self.macd_low = bt.indicators.Lowest(self.macd.macd, period=int(self.p.lookback))

        def next(self) -> None:
            if not self.position:
                cond_price = float(self.data.low[0]) <= float(self.price_low[0]) * 1.01
                cond_macd = float(self.macd.macd[0]) > float(self.macd_low[0]) * 0.8
                cond_cross = float(self.macd.macd[0]) > float(self.macd.signal[0])
                if cond_price and cond_macd and cond_cross:
                    self.buy()
                return

            cross_down = float(self.macd.macd[0]) < float(self.macd.signal[0]) and float(self.macd.macd[-1]) >= float(self.macd.signal[-1])
            if cross_down:
                self.sell()

    return MACDDivergence


def _make_turtle_simple():
    import backtrader as bt  # type: ignore

    class SimpleTurtle(bt.Strategy):
        params = dict(entry_period=20, exit_period=10)

        def __init__(self) -> None:
            self.entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.entry_period))
            self.exit_low = bt.indicators.Lowest(self.data.low, period=int(self.p.exit_period))

        def next(self) -> None:
            if not self.position and float(self.data.close[0]) > float(self.entry_high[-1]):
                self.buy()
                return
            if self.position and float(self.data.close[0]) < float(self.exit_low[-1]):
                self.close()

    return SimpleTurtle


def _make_turtle_full():
    import backtrader as bt  # type: ignore

    class Turtle(bt.Strategy):
        params = dict(
            entry_period=20,
            exit_period=10,
            atr_period=20,
            risk_pct=0.01,
            max_units=4,
            add_n=0.5,
            stop_n=2.0,
        )

        def __init__(self) -> None:
            self.entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.entry_period))
            self.exit_low = bt.indicators.Lowest(self.data.low, period=int(self.p.exit_period))
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.units = 0
            self.entry_price = None
            self.stop_price = None
            self.next_add = None
            self.order = None

        def notify_order(self, order):
            if order.status in [order.Completed, order.Canceled, order.Margin]:
                self.order = None

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            shares = int(risk / (_safe_float(self.p.stop_n) * atr))
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            if self.order:
                return
            close = _safe_float(self.data.close[0])
            atr = _safe_float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < _safe_float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < _safe_float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > _safe_float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.entry_price = close
                        self.stop_price = close - _safe_float(self.p.stop_n) * atr
                        self.next_add = close + _safe_float(self.p.add_n) * atr
                return

            if close > _safe_float(self.entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.entry_price = close
                    self.stop_price = close - _safe_float(self.p.stop_n) * atr
                    self.next_add = close + _safe_float(self.p.add_n) * atr

    return Turtle


def _make_turtle_adx():
    import backtrader as bt  # type: ignore

    class ADXTurtle(bt.Strategy):
        params = dict(
            entry_period=20,
            exit_period=10,
            atr_period=20,
            adx_period=14,
            adx_threshold=15,
            risk_pct=0.01,
            max_units=4,
            add_n=0.5,
            stop_n=2.0,
        )

        def __init__(self) -> None:
            self.entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.entry_period))
            self.exit_low = bt.indicators.Lowest(self.data.low, period=int(self.p.exit_period))
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.adx = bt.indicators.ADX(self.data, period=int(self.p.adx_period))
            self.units = 0
            self.entry_price = None
            self.stop_price = None
            self.next_add = None
            self.order = None

        def notify_order(self, order):
            if order.status in [order.Completed, order.Canceled, order.Margin]:
                self.order = None

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            shares = int(risk / (_safe_float(self.p.stop_n) * atr))
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            if self.order:
                return
            close = _safe_float(self.data.close[0])
            atr = _safe_float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < _safe_float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < _safe_float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > _safe_float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.entry_price = close
                        self.stop_price = close - _safe_float(self.p.stop_n) * atr
                        self.next_add = close + _safe_float(self.p.add_n) * atr
                return

            if _safe_float(self.adx[0]) < _safe_float(self.p.adx_threshold):
                return

            if close > _safe_float(self.entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.entry_price = close
                    self.stop_price = close - _safe_float(self.p.stop_n) * atr
                    self.next_add = close + _safe_float(self.p.add_n) * atr

    return ADXTurtle


def _make_turtle_multi_tf():
    import backtrader as bt  # type: ignore

    class MultiTFTurtle(bt.Strategy):
        params = dict(
            daily_entry=20,
            daily_exit=10,
            weekly_period=8,
            atr_period=20,
            risk_pct=0.01,
            max_units=4,
            add_n=0.5,
            stop_n=2.0,
        )

        def __init__(self) -> None:
            self.daily_entry_high = bt.indicators.Highest(self.data0.high, period=int(self.p.daily_entry))
            self.daily_exit_low = bt.indicators.Lowest(self.data0.low, period=int(self.p.daily_exit))
            self.atr = bt.indicators.ATR(self.data0, period=int(self.p.atr_period))

            self.weekly_high = bt.indicators.Highest(self.data1.high, period=int(self.p.weekly_period))
            self.weekly_low = bt.indicators.Lowest(self.data1.low, period=int(self.p.weekly_period))

            self.units = 0
            self.stop_price = None
            self.next_add = None
            self.order = None

        def notify_order(self, order):
            if order.status in [order.Completed, order.Canceled, order.Margin]:
                self.order = None

        def _weekly_trend(self) -> str:
            wc = _safe_float(self.data1.close[0])
            if wc > _safe_float(self.weekly_high[-1]):
                return "up"
            if wc < _safe_float(self.weekly_low[-1]):
                return "down"
            return "neutral"

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            shares = int(risk / (_safe_float(self.p.stop_n) * atr))
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            if self.order:
                return
            close = _safe_float(self.data0.close[0])
            atr = _safe_float(self.atr[0])
            trend = self._weekly_trend()

            if self.position:
                if trend == "down":
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.stop_price is not None and close < _safe_float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < _safe_float(self.daily_exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > _safe_float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.stop_price = close - _safe_float(self.p.stop_n) * atr
                        self.next_add = close + _safe_float(self.p.add_n) * atr
                return

            if trend == "down":
                return

            if close > _safe_float(self.daily_entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.stop_price = close - _safe_float(self.p.stop_n) * atr
                    self.next_add = close + _safe_float(self.p.add_n) * atr

    return MultiTFTurtle


def _make_turtle_ml():
    import backtrader as bt  # type: ignore

    class MLTurtle(bt.Strategy):
        params = dict(
            entry_period=20,
            exit_period=10,
            atr_period=20,
            risk_pct=0.01,
            max_units=4,
            add_n=0.5,
            stop_n=2.0,
            ml_threshold=0.5,
            predictions={},
        )

        def __init__(self) -> None:
            self.entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.entry_period))
            self.exit_low = bt.indicators.Lowest(self.data.low, period=int(self.p.exit_period))
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.units = 0
            self.stop_price = None
            self.next_add = None
            self.order = None

        def notify_order(self, order):
            if order.status in [order.Completed, order.Canceled, order.Margin]:
                self.order = None

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            shares = int(risk / (_safe_float(self.p.stop_n) * atr))
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def _prob(self) -> float | None:
            preds = getattr(self.p, "predictions", None) or {}
            dt = self.data.datetime.date(0).isoformat()
            v = preds.get(dt)
            try:
                return float(v) if v is not None else None
            except Exception:
                return None

        def next(self) -> None:
            if self.order:
                return
            close = _safe_float(self.data.close[0])
            atr = _safe_float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < _safe_float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < _safe_float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > _safe_float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.stop_price = close - _safe_float(self.p.stop_n) * atr
                        self.next_add = close + _safe_float(self.p.add_n) * atr
                return

            if close > _safe_float(self.entry_high[-1]):
                prob = self._prob()
                if prob is None or prob < _safe_float(self.p.ml_threshold):
                    return
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.stop_price = close - _safe_float(self.p.stop_n) * atr
                    self.next_add = close + _safe_float(self.p.add_n) * atr

    return MLTurtle


def _make_chan_third_buy():
    import backtrader as bt  # type: ignore

    class ChanThirdBuy(bt.Strategy):
        params = dict(take_profit_pct=0.15, use_chan_stop=True)

        def __init__(self) -> None:
            self.entry_price = None
            self.stop_price = None

        def next(self) -> None:
            close = float(self.data.close[0])
            sig = float(getattr(self.data, "chan_signal", [0.0])[0] or 0.0)
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)

            if not self.position:
                if sig == 3:
                    self.buy()
                    self.entry_price = close
                    if bool(self.p.use_chan_stop) and zg > 0:
                        self.stop_price = zg
                    else:
                        self.stop_price = close * 0.93
                return

            if self.entry_price is None:
                self.entry_price = close
            if self.stop_price is not None and close < float(self.stop_price):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if close >= float(self.entry_price) * (1.0 + float(self.p.take_profit_pct)):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if sig == -3:
                self.sell()
                self.entry_price = None
                self.stop_price = None

    return ChanThirdBuy


def _make_chan_trailing_stop():
    import backtrader as bt  # type: ignore

    class ChanTrailing(bt.Strategy):
        params = dict(
            take_profit_pct=0.15,
            use_chan_stop=True,
            atr_period=14,
            atr_exit_mult=2.5,
            breakeven_pct=0.05,
            lock_profit_pct=0.10,
            lock_amount_pct=0.05,
        )

        def __init__(self) -> None:
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.entry_price = None
            self.stop_price = None
            self.highest = None

        def next(self) -> None:
            close = float(self.data.close[0])
            sig = float(getattr(self.data, "chan_signal", [0.0])[0] or 0.0)
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)

            if not self.position:
                if sig == 3:
                    self.buy()
                    self.entry_price = close
                    self.highest = close
                    if bool(self.p.use_chan_stop) and zg > 0:
                        self.stop_price = zg
                    else:
                        self.stop_price = close * 0.93
                return

            if self.entry_price is None:
                self.entry_price = close
            self.highest = max(float(self.highest or close), close)

            profit = (close - float(self.entry_price)) / float(self.entry_price) if float(self.entry_price) else 0.0
            if profit >= float(self.p.breakeven_pct):
                self.stop_price = max(float(self.stop_price or float(self.entry_price)), float(self.entry_price))
            if profit >= float(self.p.lock_profit_pct):
                locked = float(self.entry_price) * (1.0 + float(self.p.lock_amount_pct))
                self.stop_price = max(float(self.stop_price or locked), locked)

            atr = float(self.atr[0])
            if atr > 0 and self.highest is not None:
                trail = float(self.highest) - float(self.p.atr_exit_mult) * atr
                self.stop_price = max(float(self.stop_price or trail), trail)

            if self.stop_price is not None and close < float(self.stop_price):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                self.highest = None
                return

            if close >= float(self.entry_price) * (1.0 + float(self.p.take_profit_pct)):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                self.highest = None
                return

            if sig == -3:
                self.sell()
                self.entry_price = None
                self.stop_price = None
                self.highest = None

    return ChanTrailing


def _make_chan_multi_tf():
    import backtrader as bt  # type: ignore

    class MultiTFChan(bt.Strategy):
        params = dict(take_profit_pct=0.15, weekly_ma_period=20)

        def __init__(self) -> None:
            self.weekly_ma = bt.indicators.SimpleMovingAverage(self.data1.close, period=int(self.p.weekly_ma_period))
            self.entry_price = None
            self.stop_price = None

        def next(self) -> None:
            close = float(self.data0.close[0])
            sig = float(getattr(self.data0, "chan_signal", [0.0])[0] or 0.0)
            zg = float(getattr(self.data0, "chan_zg", [0.0])[0] or 0.0)

            weekly_trend_up = float(self.data1.close[0]) >= float(self.weekly_ma[0])
            weekly_trend_down = float(self.data1.close[0]) < float(self.weekly_ma[0])

            if self.position and weekly_trend_down:
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return

            if not self.position:
                if weekly_trend_up and sig == 3:
                    self.buy()
                    self.entry_price = close
                    self.stop_price = zg if zg > 0 else close * 0.93
                return

            if self.entry_price is None:
                self.entry_price = close
            if self.stop_price is not None and close < float(self.stop_price):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if close >= float(self.entry_price) * (1.0 + float(self.p.take_profit_pct)):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if sig == -3:
                self.sell()
                self.entry_price = None
                self.stop_price = None

    return MultiTFChan


def _make_chan_ml():
    import backtrader as bt  # type: ignore

    class ChanML(bt.Strategy):
        params = dict(take_profit_pct=0.15, ml_threshold=0.5, predictions={})

        def __init__(self) -> None:
            self.entry_price = None
            self.stop_price = None

        def _prob(self) -> float | None:
            preds = getattr(self.p, "predictions", None) or {}
            dt = self.data.datetime.date(0).isoformat()
            v = preds.get(dt)
            try:
                return float(v) if v is not None else None
            except Exception:
                return None

        def next(self) -> None:
            close = float(self.data.close[0])
            sig = float(getattr(self.data, "chan_signal", [0.0])[0] or 0.0)
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)

            if not self.position:
                if sig == 3:
                    prob = self._prob()
                    if prob is None or prob < float(self.p.ml_threshold):
                        return
                    self.buy()
                    self.entry_price = close
                    self.stop_price = zg if zg > 0 else close * 0.93
                return

            if self.entry_price is None:
                self.entry_price = close
            if self.stop_price is not None and close < float(self.stop_price):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if close >= float(self.entry_price) * (1.0 + float(self.p.take_profit_pct)):
                self.sell()
                self.entry_price = None
                self.stop_price = None
                return
            if sig == -3:
                self.sell()
                self.entry_price = None
                self.stop_price = None

    return ChanML


def _make_grid_classic():
    import backtrader as bt  # type: ignore

    from core.strategy.grid_engine import GridEngine

    class ClassicGrid(bt.Strategy):
        params = dict(lookback=60, num_grids=8, margin_pct=0.02, capital_ratio=0.90)

        def __init__(self) -> None:
            self.lookback = int(self.p.lookback)
            self.engine = None
            self.range_high = bt.indicators.Highest(self.data.high, period=self.lookback)
            self.range_low = bt.indicators.Lowest(self.data.low, period=self.lookback)

        def next(self) -> None:
            close = float(self.data.close[0])
            if self.engine is None:
                try:
                    lo = float(self.range_low[0])
                    hi = float(self.range_high[0])
                except (TypeError, IndexError, ValueError):
                    return
                if not (lo > 0 and hi > lo):
                    return
                lower = lo * (1.0 - float(self.p.margin_pct))
                upper = hi * (1.0 + float(self.p.margin_pct))
                capital = float(self.broker.getvalue()) * float(self.p.capital_ratio)
                self.engine = GridEngine(lower=lower, upper=upper, num_grids=int(self.p.num_grids), total_capital=capital)
                return

            for sig in self.engine.update(close):
                if sig.action == "BUY":
                    if float(self.broker.getcash()) >= float(sig.price) * sig.shares:
                        self.buy(size=int(sig.shares))
                elif sig.action == "SELL":
                    if int(self.position.size) >= int(sig.shares):
                        self.sell(size=int(sig.shares))

    return ClassicGrid


def _make_chan_grid():
    import backtrader as bt  # type: ignore

    from core.strategy.grid_engine import ChanGridEngine

    class ChanGrid(bt.Strategy):
        params = dict(num_grids=6, capital_ratio=0.80, exit_on_breakout=True, breakout_pct=0.005)

        def __init__(self) -> None:
            self.engine = None
            self.last_zg = None
            self.last_zd = None

        def _has_center(self) -> bool:
            try:
                zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)
                zd = float(getattr(self.data, "chan_zd", [0.0])[0] or 0.0)
            except (TypeError, IndexError, ValueError):
                return False
            return zg > 0 and zd > 0 and zg > zd

        def next(self) -> None:
            try:
                close = float(self.data.close[0])
                zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)
                zd = float(getattr(self.data, "chan_zd", [0.0])[0] or 0.0)
            except (TypeError, IndexError, ValueError):
                return

            if not self._has_center():
                self.engine = None
                return

            if self.last_zg is None or self.last_zd is None:
                self.last_zg, self.last_zd = zg, zd

            changed = (abs(zg / float(self.last_zg) - 1.0) > 0.001) or (abs(zd / float(self.last_zd) - 1.0) > 0.001)
            if self.engine is None or changed:
                if int(self.position.size) > 0:
                    self.sell(size=int(self.position.size))
                capital = float(self.broker.getvalue()) * float(self.p.capital_ratio)
                self.engine = ChanGridEngine(zg=zg, zd=zd, num_grids=int(self.p.num_grids), total_capital=capital)
                self.last_zg, self.last_zd = zg, zd
                return

            if bool(self.p.exit_on_breakout):
                if close > zg * (1.0 + float(self.p.breakout_pct)) or close < zd * (1.0 - float(self.p.breakout_pct)):
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    self.engine.deactivate()
                    return

            for s in self.engine.update(close):
                if s.action == "BUY":
                    if float(self.broker.getcash()) >= float(s.price) * s.shares:
                        self.buy(size=int(s.shares))
                elif s.action == "SELL":
                    if int(self.position.size) >= int(s.shares):
                        self.sell(size=int(s.shares))

    return ChanGrid


def _make_chan_grid_trend_linkage():
    import backtrader as bt  # type: ignore

    from core.strategy.grid_engine import ChanGridEngine

    class ChanGridTrend(bt.Strategy):
        params = dict(
            num_grids=6,
            capital_ratio=0.80,
            atr_period=14,
            atr_trail_mult=2.5,
            breakout_confirm=0.005,
        )

        def __init__(self) -> None:
            self.state = "WAIT"
            self.engine = None
            self.atr = bt.indicators.ATR(self.data, period=int(self.p.atr_period))
            self.highest = None
            self.last_zg = None
            self.last_zd = None

        def _zgzd(self) -> tuple[float, float]:
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)
            zd = float(getattr(self.data, "chan_zd", [0.0])[0] or 0.0)
            return zg, zd

        def _has_center(self, zg: float, zd: float) -> bool:
            return zg > 0 and zd > 0 and zg > zd

        def next(self) -> None:
            close = float(self.data.close[0])
            sig = float(getattr(self.data, "chan_signal", [0.0])[0] or 0.0)
            zg, zd = self._zgzd()

            if self.state == "WAIT":
                if self._has_center(zg, zd):
                    self.state = "GRID"
                    self.last_zg, self.last_zd = zg, zd
                    capital = float(self.broker.getvalue()) * float(self.p.capital_ratio)
                    self.engine = ChanGridEngine(zg=zg, zd=zd, num_grids=int(self.p.num_grids), total_capital=capital)
                return

            if self.state == "GRID":
                if not self._has_center(zg, zd):
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    self.state = "WAIT"
                    self.engine = None
                    return

                changed = False
                if self.last_zg is not None and self.last_zd is not None:
                    changed = (abs(zg / float(self.last_zg) - 1.0) > 0.001) or (abs(zd / float(self.last_zd) - 1.0) > 0.001)
                if changed:
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    capital = float(self.broker.getvalue()) * float(self.p.capital_ratio)
                    self.engine = ChanGridEngine(zg=zg, zd=zd, num_grids=int(self.p.num_grids), total_capital=capital)
                    self.last_zg, self.last_zd = zg, zd
                    return

                if close > zg * (1.0 + float(self.p.breakout_confirm)):
                    if self.engine is not None:
                        self.engine.deactivate()
                    capital = float(self.broker.getvalue()) * 0.50
                    shares = int(capital / close)
                    shares = (shares // 100) * 100
                    if shares > 0:
                        self.buy(size=shares)
                        self.highest = close
                        self.state = "TREND_UP"
                    return

                if close < zd * (1.0 - float(self.p.breakout_confirm)):
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    if self.engine is not None:
                        self.engine.deactivate()
                    self.state = "WAIT"
                    self.engine = None
                    return

                if self.engine is not None:
                    for s in self.engine.update(close):
                        if s.action == "BUY":
                            if float(self.broker.getcash()) >= float(s.price) * s.shares:
                                self.buy(size=int(s.shares))
                        elif s.action == "SELL":
                            if int(self.position.size) >= int(s.shares):
                                self.sell(size=int(s.shares))
                return

            if self.state == "TREND_UP":
                self.highest = max(float(self.highest or close), close)
                atr = float(self.atr[0])
                if atr > 0 and self.highest is not None:
                    stop = float(self.highest) - float(self.p.atr_trail_mult) * atr
                    if close < stop:
                        if int(self.position.size) > 0:
                            self.sell(size=int(self.position.size))
                        self.state = "WAIT"
                        self.engine = None
                        self.highest = None
                        return

                if sig == -3:
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    self.state = "WAIT"
                    self.engine = None
                    self.highest = None
                    return

                if self._has_center(zg, zd):
                    if int(self.position.size) > 0:
                        self.sell(size=int(self.position.size))
                    self.state = "GRID"
                    self.last_zg, self.last_zd = zg, zd
                    capital = float(self.broker.getvalue()) * float(self.p.capital_ratio)
                    self.engine = ChanGridEngine(zg=zg, zd=zd, num_grids=int(self.p.num_grids), total_capital=capital)
                    self.highest = None

    return ChanGridTrend


def _make_combo_custom():
    """自定义组合策略工厂函数，延迟导入避免循环依赖"""
    from core.strategy.combo_engine import make_combo_strategy
    return make_combo_strategy()


def get_strategy_registry() -> dict[str, StrategyMeta]:
    return {
        "ma_dual": StrategyMeta(
            strategy_id="ma_dual",
            name="MA双均线策略",
            description="快均线上穿慢均线买入，下穿卖出。震荡市可能频繁来回切换。",
            params_schema={
                "fast": _p_int("快均线周期", "快均线的周期（通常小于慢均线）。周期越小越敏感，信号越多。", 2, 250),
                "slow": _p_int("慢均线周期", "慢均线的周期（通常大于快均线）。周期越大越稳健，但信号滞后。", 3, 400),
            },
            default_params={"fast": 10, "slow": 30},
            bt_strategy_factory=_make_dual_ma,
            group="basic",
        ),
        "macd_basic": StrategyMeta(
            strategy_id="macd_basic",
            name="MACD策略",
            description="DIF 上穿 DEA（金叉）买入，下穿 DEA（死叉）卖出。",
            params_schema={
                "fast": _p_int("快线周期", "MACD 快线 EMA 周期（常用 12）。越小越敏感。", 2, 200),
                "slow": _p_int("慢线周期", "MACD 慢线 EMA 周期（常用 26）。应大于快线周期。", 3, 400),
                "signal": _p_int("信号线周期", "DEA（信号线）EMA 周期（常用 9）。越小越敏感。", 2, 200),
            },
            default_params={"fast": 12, "slow": 26, "signal": 9},
            bt_strategy_factory=_make_macd_basic,
            group="basic",
        ),
        "rsi_basic": StrategyMeta(
            strategy_id="rsi_basic",
            name="RSI策略",
            description="RSI 低于超卖阈值买入，高于超买阈值卖出。",
            params_schema={
                "period": _p_int("RSI周期", "RSI 计算周期（常用 14）。周期越小越敏感。", 2, 200),
                "oversold": _p_float("超卖阈值", "RSI 低于该阈值视为超卖区域，触发买入。常用 30。", 1, 60, 1),
                "overbought": _p_float("超买阈值", "RSI 高于该阈值视为超买区域，触发卖出。常用 70。", 40, 99, 1),
            },
            default_params={"period": 14, "oversold": 30, "overbought": 70},
            bt_strategy_factory=_make_rsi_basic,
            group="basic",
        ),
        "boll_basic": StrategyMeta(
            strategy_id="boll_basic",
            name="布林带策略",
            description="收盘价跌破下轨买入，上穿上轨卖出。",
            params_schema={
                "period": _p_int("布林周期", "布林带中轨的均线周期（常用 20）。", 5, 250),
                "devfactor": _p_float("标准差倍数", "上下轨距离中轨的标准差倍数（常用 2.0）。越大越宽，触发更少。", 0.5, 6.0, 0.1),
            },
            default_params={"period": 20, "devfactor": 2.0},
            bt_strategy_factory=_make_boll_basic,
            group="basic",
        ),
        "bias": StrategyMeta(
            strategy_id="bias",
            name="乖离率策略",
            description="BIAS=(收盘-均线)/均线*100，低于阈值买入，高于阈值卖出。",
            params_schema={
                "period": _p_int("均线周期", "用于计算 BIAS 的均线周期（常用 20）。", 2, 250),
                "buy_threshold": _p_float("买入阈值(%)", "BIAS 小于该阈值触发买入（负值表示低于均线）。例如 -6 表示低于均线 6%。", -50, 0, 0.1),
                "sell_threshold": _p_float("卖出阈值(%)", "BIAS 大于该阈值触发卖出。", 0, 50, 0.1),
            },
            default_params={"period": 20, "buy_threshold": -6.0, "sell_threshold": 3.0},
            bt_strategy_factory=_make_bias,
            group="basic",
        ),
        "momentum": StrategyMeta(
            strategy_id="momentum",
            name="动量策略",
            description="ROC(涨跌幅)高于阈值买入，低于负阈值卖出。",
            params_schema={
                "period": _p_int("ROC周期", "ROC 计算周期（常用 20）。周期越小越敏感。", 2, 250),
                "threshold": _p_float("动量阈值(%)", "ROC 高于阈值买入；低于 -threshold 卖出。", 0.1, 50, 0.1),
            },
            default_params={"period": 20, "threshold": 5.0},
            bt_strategy_factory=_make_momentum,
            group="basic",
        ),
        "rsi_cross_confirm": StrategyMeta(
            strategy_id="rsi_cross_confirm",
            name="RSI增强-穿越确认",
            description="RSI 从超卖区向上穿越阈值后买入（确认回升），RSI 超买卖出。",
            params_schema={
                "period": _p_int("RSI周期", "RSI 计算周期（常用 14）。", 2, 200),
                "oversold": _p_float("超卖阈值", "RSI 从低于该阈值回升并向上穿越时触发买入。", 1, 60, 1),
                "overbought": _p_float("超买阈值", "RSI 高于该阈值触发卖出。", 40, 99, 1),
            },
            default_params={"period": 14, "oversold": 30, "overbought": 70},
            bt_strategy_factory=_make_rsi_cross_confirm,
            group="optimized",
        ),
        "macd_vol_confirm": StrategyMeta(
            strategy_id="macd_vol_confirm",
            name="MACD增强-成交量确认",
            description="MACD 金叉且成交量放量确认才买入；MACD 死叉卖出。",
            params_schema={
                "fast": _p_int("快线周期", "MACD 快线 EMA 周期（常用 12）。", 2, 200),
                "slow": _p_int("慢线周期", "MACD 慢线 EMA 周期（常用 26）。", 3, 400),
                "signal": _p_int("信号线周期", "DEA（信号线）EMA 周期（常用 9）。", 2, 200),
                "vol_period": _p_int("成交量均线周期", "成交量均线周期，用于判断放量。常用 20。", 2, 250),
                "vol_mult": _p_float("放量倍率", "当前成交量需大于 vol_ma * vol_mult 才算放量确认。", 0.1, 10.0, 0.05),
            },
            default_params={"fast": 12, "slow": 26, "signal": 9, "vol_period": 20, "vol_mult": 0.9},
            bt_strategy_factory=_make_macd_vol_confirm,
            group="optimized",
        ),
        "macd_profit_lock": StrategyMeta(
            strategy_id="macd_profit_lock",
            name="MACD增强-利润锁定",
            description="MACD 金叉入场；盈利达到阈值后启用回撤锁定；MACD 死叉也出场。",
            params_schema={
                "fast": _p_int("快线周期", "MACD 快线 EMA 周期。", 2, 200),
                "slow": _p_int("慢线周期", "MACD 慢线 EMA 周期。", 3, 400),
                "signal": _p_int("信号线周期", "DEA（信号线）EMA 周期。", 2, 200),
                "profit_trigger": _p_float("触发利润(%)", "当持仓收益率达到该阈值后，启用回撤锁定逻辑。", 0.1, 200, 0.1),
                "trail_pct": _p_float("回撤锁定(%)", "从最高价回撤超过该比例时锁定利润出场。", 0.1, 50, 0.1),
            },
            default_params={"fast": 12, "slow": 26, "signal": 9, "profit_trigger": 5.0, "trail_pct": 3.0},
            bt_strategy_factory=_make_macd_profit_lock,
            group="optimized",
        ),
        "boll_mid_stop": StrategyMeta(
            strategy_id="boll_mid_stop",
            name="布林带增强-中轨止损",
            description="下轨买入，上轨止盈；若反弹到中轨上方后再跌破中轨，触发止损。",
            params_schema={
                "period": _p_int("布林周期", "布林带中轨周期（常用 20）。", 5, 250),
                "devfactor": _p_float("标准差倍数", "上下轨标准差倍数（常用 2.0）。", 0.5, 6.0, 0.1),
            },
            default_params={"period": 20, "devfactor": 2.0},
            bt_strategy_factory=_make_boll_mid_stop,
            group="optimized",
        ),
        "adaptive": StrategyMeta(
            strategy_id="adaptive",
            name="综合增强-自适应策略",
            description="ADX 判断趋势或震荡；趋势用 MACD 信号，震荡用 RSI 信号；统一 ATR 跟踪止损。",
            params_schema={
                "adx_period": _p_int("ADX周期", "ADX 计算周期（常用 14）。", 2, 200),
                "adx_trend": _p_float("趋势阈值", "ADX 大于该值认为趋势行情（偏趋势策略）。常用 25。", 1, 100, 1),
                "adx_range": _p_float("震荡阈值", "ADX 小于该值认为震荡行情（偏均值回归）。常用 20。", 1, 100, 1),
                "atr_period": _p_int("ATR周期", "ATR 计算周期（常用 14）。用于跟踪止损。", 2, 200),
                "atr_mult": _p_float("ATR倍数", "跟踪止损距离：close - atr_mult * ATR。倍数越大越宽松。", 0.1, 10.0, 0.1),
                "macd_fast": _p_int("MACD快线周期", "趋势模式下 MACD 快线 EMA 周期。", 2, 200),
                "macd_slow": _p_int("MACD慢线周期", "趋势模式下 MACD 慢线 EMA 周期。", 3, 400),
                "macd_signal": _p_int("MACD信号线周期", "趋势模式下 MACD 信号线 EMA 周期。", 2, 200),
                "rsi_period": _p_int("RSI周期", "震荡模式下 RSI 计算周期。", 2, 200),
                "oversold": _p_float("RSI超卖阈值", "震荡模式下 RSI 低于该值买入。", 1, 60, 1),
                "overbought": _p_float("RSI超买阈值", "震荡模式下 RSI 高于该值卖出。", 40, 99, 1),
            },
            default_params={
                "adx_period": 14,
                "adx_trend": 25,
                "adx_range": 20,
                "atr_period": 14,
                "atr_mult": 2.0,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "rsi_period": 14,
                "oversold": 30,
                "overbought": 70,
            },
            bt_strategy_factory=_make_adaptive,
            group="combo",
        ),
        "macd_divergence": StrategyMeta(
            strategy_id="macd_divergence",
            name="MACD底背离策略",
            description="价格接近阶段新低，但 MACD 不再创新低（背离）且处于金叉态买入；死叉确认卖出。",
            params_schema={
                "lookback": _p_int("回看窗口", "用于判断阶段低点与 MACD 低点的回看窗口（常用 30）。", 10, 400),
                "fast": _p_int("快线周期", "MACD 快线 EMA 周期。", 2, 200),
                "slow": _p_int("慢线周期", "MACD 慢线 EMA 周期。", 3, 400),
                "signal": _p_int("信号线周期", "DEA（信号线）EMA 周期。", 2, 200),
            },
            default_params={"lookback": 30, "fast": 12, "slow": 26, "signal": 9},
            bt_strategy_factory=_make_macd_divergence,
            group="optimized",
        ),
        "turtle_simple": StrategyMeta(
            strategy_id="turtle_simple",
            name="简单海龟交易法则",
            description="收盘价突破 N 日唐奇安上轨入场，跌破 M 日唐奇安下轨出场。",
            params_schema={
                "entry_period": _p_int("入场通道周期", "唐奇安上轨周期（常用 20）。", 2, 400),
                "exit_period": _p_int("出场通道周期", "唐奇安下轨周期（常用 10）。", 2, 400),
            },
            default_params={"entry_period": 20, "exit_period": 10},
            bt_strategy_factory=_make_turtle_simple,
            group="basic",
        ),
        "turtle_full": StrategyMeta(
            strategy_id="turtle_full",
            name="完整海龟交易法则",
            description="通道突破入场；ATR 风险仓位；金字塔加仓；2N 止损；下轨出场。",
            params_schema={
                "entry_period": _p_int("入场通道周期", "唐奇安上轨周期。", 2, 400),
                "exit_period": _p_int("出场通道周期", "唐奇安下轨周期。", 2, 400),
                "atr_period": _p_int("ATR周期", "ATR 计算周期（常用 20）。用于风险与加仓步长。", 2, 400),
                "risk_pct": _p_float("单笔风险占比", "每个单位仓位允许的风险占账户净值的比例（如 0.01=1%）。", 0.0001, 0.2, 0.0005),
                "max_units": _p_int("最大加仓单位", "最多加仓到多少个单位（常用 4）。", 1, 20),
                "add_n": _p_float("加仓步长(N)", "每上涨 add_n * ATR 加一单位仓。常用 0.5。", 0.1, 5.0, 0.1),
                "stop_n": _p_float("止损倍数(N)", "初始/加仓后的止损距离：入场价 - stop_n * ATR。常用 2。", 0.5, 10.0, 0.1),
            },
            default_params={
                "entry_period": 20,
                "exit_period": 10,
                "atr_period": 20,
                "risk_pct": 0.01,
                "max_units": 4,
                "add_n": 0.5,
                "stop_n": 2.0,
            },
            bt_strategy_factory=_make_turtle_full,
            group="optimized",
        ),
        "turtle_adx": StrategyMeta(
            strategy_id="turtle_adx",
            name="ADX海龟策略",
            description="只有 ADX 达到阈值才允许执行海龟突破入场；其余同完整海龟。",
            params_schema={
                "entry_period": _p_int("入场通道周期", "唐奇安上轨周期。", 2, 400),
                "exit_period": _p_int("出场通道周期", "唐奇安下轨周期。", 2, 400),
                "atr_period": _p_int("ATR周期", "ATR 计算周期。", 2, 400),
                "adx_period": _p_int("ADX周期", "ADX 计算周期（常用 14）。", 2, 200),
                "adx_threshold": _p_float("ADX阈值", "ADX 大于该阈值才允许突破入场（常用 15）。", 1, 100, 1),
                "risk_pct": _p_float("单笔风险占比", "每个单位仓位允许的风险占账户净值的比例。", 0.0001, 0.2, 0.0005),
                "max_units": _p_int("最大加仓单位", "最多加仓到多少个单位。", 1, 20),
                "add_n": _p_float("加仓步长(N)", "每上涨 add_n * ATR 加一单位仓。", 0.1, 5.0, 0.1),
                "stop_n": _p_float("止损倍数(N)", "止损距离：入场价 - stop_n * ATR。", 0.5, 10.0, 0.1),
            },
            default_params={
                "entry_period": 20,
                "exit_period": 10,
                "atr_period": 20,
                "adx_period": 14,
                "adx_threshold": 15,
                "risk_pct": 0.01,
                "max_units": 4,
                "add_n": 0.5,
                "stop_n": 2.0,
            },
            bt_strategy_factory=_make_turtle_adx,
            group="optimized",
        ),
        "turtle_multi_tf": StrategyMeta(
            strategy_id="turtle_multi_tf",
            name="多周期海龟策略",
            description="周线判断趋势方向，日线执行突破/出场与加仓。",
            params_schema={
                "daily_entry": _p_int("日线入场通道周期", "日线唐奇安上轨周期（常用 20）。", 2, 400),
                "daily_exit": _p_int("日线出场通道周期", "日线唐奇安下轨周期（常用 10）。", 2, 400),
                "weekly_period": _p_int("周线趋势周期", "周线通道周期（常用 8 周）。用于趋势过滤。", 2, 200),
                "atr_period": _p_int("ATR周期", "ATR 计算周期（常用 20）。", 2, 400),
                "risk_pct": _p_float("单笔风险占比", "每个单位仓位允许的风险占账户净值的比例。", 0.0001, 0.2, 0.0005),
                "max_units": _p_int("最大加仓单位", "最多加仓到多少个单位。", 1, 20),
                "add_n": _p_float("加仓步长(N)", "每上涨 add_n * ATR 加一单位仓。", 0.1, 5.0, 0.1),
                "stop_n": _p_float("止损倍数(N)", "止损距离：入场价 - stop_n * ATR。", 0.5, 10.0, 0.1),
            },
            default_params={
                "daily_entry": 20,
                "daily_exit": 10,
                "weekly_period": 8,
                "atr_period": 20,
                "risk_pct": 0.01,
                "max_units": 4,
                "add_n": 0.5,
                "stop_n": 2.0,
            },
            bt_strategy_factory=_make_turtle_multi_tf,
            requires_weekly=True,
            group="optimized",
        ),
        "turtle_ml": StrategyMeta(
            strategy_id="turtle_ml",
            name="ML增强海龟策略",
            description="突破信号需满足预测概率阈值才入场（predictions 需传入）。其余同完整海龟。",
            params_schema={
                "entry_period": _p_int("入场通道周期", "唐奇安上轨周期。", 2, 400),
                "exit_period": _p_int("出场通道周期", "唐奇安下轨周期。", 2, 400),
                "atr_period": _p_int("ATR周期", "ATR 计算周期。", 2, 400),
                "risk_pct": _p_float("单笔风险占比", "每个单位仓位允许的风险占账户净值的比例。", 0.0001, 0.2, 0.0005),
                "max_units": _p_int("最大加仓单位", "最多加仓到多少个单位。", 1, 20),
                "add_n": _p_float("加仓步长(N)", "每上涨 add_n * ATR 加一单位仓。", 0.1, 5.0, 0.1),
                "stop_n": _p_float("止损倍数(N)", "止损距离：入场价 - stop_n * ATR。", 0.5, 10.0, 0.1),
                "ml_threshold": _p_float("放行阈值", "预测概率 >= 阈值时才允许入场。", 0.0, 1.0, 0.01),
                "predictions": _p_object("预测字典", "格式：{ 'YYYY-MM-DD': 概率 }。用于过滤突破信号。"),
            },
            default_params={
                "entry_period": 20,
                "exit_period": 10,
                "atr_period": 20,
                "risk_pct": 0.01,
                "max_units": 4,
                "add_n": 0.5,
                "stop_n": 2.0,
                "ml_threshold": 0.5,
                "predictions": {},
            },
            bt_strategy_factory=_make_turtle_ml,
            requires_predictions=True,
            group="optimized",
        ),
        "chan_third_buy": StrategyMeta(
            strategy_id="chan_third_buy",
            name="经典缠论-基础三买",
            description="第三类买点入场；跌回中枢上沿止损（可选）；达到固定止盈或三卖离场。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "take_profit_pct": _p_float("止盈比例", "达到该比例收益后止盈出场（如 0.15=15%）。", 0.0, 5.0, 0.01),
                "use_chan_stop": _p_bool("使用中枢止损", "开启后优先用中枢上沿 ZG 作为止损线；否则使用固定比例兜底止损。"),
            },
            default_params={"chan_backend": "self", "take_profit_pct": 0.15, "use_chan_stop": True},
            bt_strategy_factory=_make_chan_third_buy,
            requires_chan=True,
            group="basic",
        ),
        "chan_trailing": StrategyMeta(
            strategy_id="chan_trailing",
            name="缠论-量价增强策略",
            description="三买入场；盈利后阶梯止损（保本/锁利）+ ATR 跟踪止损；三卖离场。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "take_profit_pct": _p_float("止盈比例", "达到该比例收益后止盈出场（如 0.15=15%）。", 0.0, 5.0, 0.01),
                "use_chan_stop": _p_bool("使用中枢止损", "开启后优先用中枢上沿 ZG 作为止损线；否则使用固定比例兜底止损。"),
                "atr_period": _p_int("ATR周期", "ATR 计算周期（常用 14）。用于跟踪止损。", 2, 200),
                "atr_exit_mult": _p_float("ATR出场倍数", "跟踪止损距离：最高价 - atr_exit_mult * ATR。", 0.1, 10.0, 0.1),
                "breakeven_pct": _p_float("保本触发", "收益率达到该阈值后止损抬到成本价（如 0.05=5%）。", 0.0, 1.0, 0.01),
                "lock_profit_pct": _p_float("锁利触发", "收益率达到该阈值后启动锁利止损（如 0.10=10%）。", 0.0, 2.0, 0.01),
                "lock_amount_pct": _p_float("锁定利润", "锁利后至少锁定的利润比例（如 0.05=5%）。", 0.0, 2.0, 0.01),
            },
            default_params={
                "chan_backend": "self",
                "take_profit_pct": 0.15,
                "use_chan_stop": True,
                "atr_period": 14,
                "atr_exit_mult": 2.5,
                "breakeven_pct": 0.05,
                "lock_profit_pct": 0.10,
                "lock_amount_pct": 0.05,
            },
            bt_strategy_factory=_make_chan_trailing_stop,
            requires_chan=True,
            group="optimized",
        ),
        "chan_multi_tf": StrategyMeta(
            strategy_id="chan_multi_tf",
            name="缠论-多周期缠论策略",
            description="周线向上才允许日线三买入场；其余止盈/止损/三卖离场。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "take_profit_pct": _p_float("止盈比例", "达到该比例收益后止盈出场。", 0.0, 5.0, 0.01),
                "weekly_ma_period": _p_int("周线MA周期", "周线趋势过滤的均线周期（默认 20）。周线收盘高于均线视为向上。", 2, 200),
            },
            default_params={"chan_backend": "self", "take_profit_pct": 0.15, "weekly_ma_period": 20},
            bt_strategy_factory=_make_chan_multi_tf,
            requires_chan=True,
            requires_weekly=True,
            group="optimized",
        ),
        "chan_ml": StrategyMeta(
            strategy_id="chan_ml",
            name="缠论-ML增强缠论策略",
            description="三买信号需满足预测概率阈值才入场（predictions 需传入）；其余止盈/止损/三卖离场。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "take_profit_pct": _p_float("止盈比例", "达到该比例收益后止盈出场。", 0.0, 5.0, 0.01),
                "ml_threshold": _p_float("放行阈值", "预测概率 >= 阈值时才允许入场。", 0.0, 1.0, 0.01),
                "predictions": _p_object("预测字典", "格式：{ 'YYYY-MM-DD': 概率 }。用于过滤三买信号。"),
            },
            default_params={"chan_backend": "self", "take_profit_pct": 0.15, "ml_threshold": 0.5, "predictions": {}},
            bt_strategy_factory=_make_chan_ml,
            requires_chan=True,
            requires_predictions=True,
            group="optimized",
        ),
        "grid_classic": StrategyMeta(
            strategy_id="grid_classic",
            name="经典网格交易",
            description="用回看区间的高低点构建网格，价格穿越网格线触发买卖（收租）。",
            params_schema={
                "lookback": _p_int("回看天数", "用于估计区间上下界的回看天数（常用 60）。", 10, 600),
                "num_grids": _p_int("网格数量", "区间被切分成多少个网格（常用 6~12）。", 2, 200),
                "margin_pct": _p_float("区间扩展(%)", "在回看最高/最低基础上，上下各扩展 margin_pct（如 0.02=2%）。", 0.0, 1.0, 0.001),
                "capital_ratio": _p_float("资金占比", "用于网格策略的资金占比（如 0.90=90%）。", 0.0, 1.0, 0.01),
            },
            default_params={"lookback": 60, "num_grids": 8, "margin_pct": 0.02, "capital_ratio": 0.90},
            bt_strategy_factory=_make_grid_classic,
            group="basic",
        ),
        "chan_grid": StrategyMeta(
            strategy_id="chan_grid",
            name="缠论中枢网络策略",
            description="用中枢 ZG/ZD 作为网格边界；突破中枢则清仓并停用网格。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "num_grids": _p_int("网格数量", "中枢区间被切分成多少个网格（常用 6）。", 2, 200),
                "capital_ratio": _p_float("资金占比", "用于网格策略的资金占比（如 0.80=80%）。", 0.0, 1.0, 0.01),
                "exit_on_breakout": _p_bool("突破即退出", "开启后，价格突破/跌破中枢一定比例时清仓并停用网格。"),
                "breakout_pct": _p_float("突破确认(%)", "突破确认比例（如 0.005=0.5%）。用于避免噪声突破。", 0.0, 0.2, 0.0005),
            },
            default_params={"chan_backend": "self", "num_grids": 6, "capital_ratio": 0.80, "exit_on_breakout": True, "breakout_pct": 0.005},
            bt_strategy_factory=_make_chan_grid,
            requires_chan=True,
            group="optimized",
        ),
        "chan_grid_trend": StrategyMeta(
            strategy_id="chan_grid_trend",
            name="中枢网格+趋势联动",
            description="中枢内做网格；向上突破转趋势持有并用 ATR 跟踪止损；向下跌破转空防守。",
            params_schema={
                "chan_backend": _p_select("缠论分析库", "选择缠论分析引擎：自研 ChanAnalyzer 或开源 chan.py", [
                    {"value": "self", "label": "自研 ChanAnalyzer"},
                    {"value": "chanpy", "label": "开源 chan.py"},
                ]),
                "num_grids": _p_int("网格数量", "中枢区间被切分成多少个网格。", 2, 200),
                "capital_ratio": _p_float("资金占比", "用于网格策略的资金占比。", 0.0, 1.0, 0.01),
                "atr_period": _p_int("ATR周期", "趋势模式下 ATR 跟踪止损的周期（常用 14）。", 2, 200),
                "atr_trail_mult": _p_float("ATR跟踪倍数", "趋势模式止损距离：最高价 - atr_trail_mult * ATR。", 0.1, 10.0, 0.1),
                "breakout_confirm": _p_float("突破确认(%)", "突破确认比例（如 0.005=0.5%）。", 0.0, 0.2, 0.0005),
            },
            default_params={"chan_backend": "self", "num_grids": 6, "capital_ratio": 0.80, "atr_period": 14, "atr_trail_mult": 2.5, "breakout_confirm": 0.005},
            bt_strategy_factory=_make_chan_grid_trend_linkage,
            requires_chan=True,
            group="optimized",
        ),
        "combo_custom": StrategyMeta(
            strategy_id="combo_custom",
            name="自定义组合策略",
            description="基于行情判别（ADX/MA/布林带）自动切换趋势与震荡模式，分别匹配不同的买入/卖出条件，支持自定义参数。",
            params_schema={
                # ── 行情判别 ──
                "detector_type": _p_select("行情判别方式", "选择判断趋势/震荡的方法", [
                    {"value": "adx", "label": "ADX指标"},
                    {"value": "ma", "label": "MA均线"},
                    {"value": "boll", "label": "布林带"},
                ], section="行情判别"),
                # ADX 子参数——仅当 detector_type == "adx" 时显示
                "adx_period": _p_int("ADX周期", "ADX计算周期（常用14）。", 2, 200, section="行情判别",
                                     show_if={"field": "detector_type", "value": "adx"}),
                "adx_range_threshold": _p_float("震荡阈值", "ADX < 该值，判定为震荡行情（常用20）。", 1, 100, 1, section="行情判别",
                                                show_if={"field": "detector_type", "value": "adx"}),
                "adx_trend_threshold": _p_float("趋势阈值", "ADX > 该值，判定为趋势行情（常用25）。阈值之间的区间为过渡行情。", 1, 100, 1, section="行情判别",
                                                show_if={"field": "detector_type", "value": "adx"}),
                # MA 子参数——仅当 detector_type == "ma" 时显示
                "det_ma_fast": _p_int("判别快均线", "MA判别模式的快均线周期。", 2, 200, section="行情判别",
                                      show_if={"field": "detector_type", "value": "ma"}),
                "det_ma_slow": _p_int("判别慢均线", "MA判别模式的慢均线周期。", 3, 400, section="行情判别",
                                      show_if={"field": "detector_type", "value": "ma"}),
                # 布林带 子参数——仅当 detector_type == "boll" 时显示
                "det_boll_period": _p_int("判别布林周期", "布林带判别模式的中轨周期。", 5, 250, section="行情判别",
                                          show_if={"field": "detector_type", "value": "boll"}),
                "det_boll_devfactor": _p_float("判别布林倍数", "布林带判别模式的标准差倍数。", 0.5, 6.0, 0.1, section="行情判别",
                                                show_if={"field": "detector_type", "value": "boll"}),

                # ── 趋势买入 ──
                "trend_buy": _p_select("趋势买入条件", "趋势行情下的买入信号", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "macd_cross", "label": "MACD金叉"},
                    {"value": "ma_cross", "label": "MA交叉"},
                    {"value": "breakout", "label": "突破新高"},
                ], section="趋势买入"),
                # MACD金叉 子参数
                "tb_macd_fast": _p_int("MACD快线", "MACD快线周期。", 2, 200, section="趋势买入",
                                       show_if={"field": "trend_buy", "value": "macd_cross"}),
                "tb_macd_slow": _p_int("MACD慢线", "MACD慢线周期。", 3, 400, section="趋势买入",
                                       show_if={"field": "trend_buy", "value": "macd_cross"}),
                "tb_macd_signal": _p_int("MACD信号线", "MACD信号线周期。", 2, 200, section="趋势买入",
                                         show_if={"field": "trend_buy", "value": "macd_cross"}),
                # MA交叉 子参数
                "tb_ma_fast": _p_int("MA快线", "MA交叉快线周期。", 2, 200, section="趋势买入",
                                     show_if={"field": "trend_buy", "value": "ma_cross"}),
                "tb_ma_slow": _p_int("MA慢线", "MA交叉慢线周期。", 3, 400, section="趋势买入",
                                     show_if={"field": "trend_buy", "value": "ma_cross"}),
                # 突破新高 子参数
                "tb_breakout_period": _p_int("突破回看周期", "突破新高的回看周期。", 2, 400, section="趋势买入",
                                             show_if={"field": "trend_buy", "value": "breakout"}),

                # ── 趋势卖出 ──
                "trend_sell": _p_select("趋势卖出条件", "趋势行情下的卖出信号", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "macd_dead_cross", "label": "MACD死叉"},
                    {"value": "atr_stop", "label": "ATR跟踪止损"},
                    {"value": "profit_lock", "label": "利润锁定"},
                ], section="趋势卖出"),
                # MACD死叉 子参数
                "ts_macd_fast": _p_int("MACD快线", "MACD快线周期。", 2, 200, section="趋势卖出",
                                       show_if={"field": "trend_sell", "value": "macd_dead_cross"}),
                "ts_macd_slow": _p_int("MACD慢线", "MACD慢线周期。", 3, 400, section="趋势卖出",
                                       show_if={"field": "trend_sell", "value": "macd_dead_cross"}),
                "ts_macd_signal": _p_int("MACD信号线", "MACD信号线周期。", 2, 200, section="趋势卖出",
                                         show_if={"field": "trend_sell", "value": "macd_dead_cross"}),
                # ATR跟踪止损 子参数
                "ts_atr_period": _p_int("ATR周期", "ATR计算周期。", 2, 200, section="趋势卖出",
                                        show_if={"field": "trend_sell", "value": "atr_stop"}),
                "ts_atr_mult": _p_float("ATR倍数", "ATR止损距离：最高价 - ATR倍数 * ATR。", 0.1, 10.0, 0.1, section="趋势卖出",
                                        show_if={"field": "trend_sell", "value": "atr_stop"}),
                # 利润锁定 子参数
                "ts_profit_trigger": _p_float("利润触发(%)", "收益率达到该阈值后启动利润锁定。", 0.1, 200, 0.1, section="趋势卖出",
                                              show_if={"field": "trend_sell", "value": "profit_lock"}),
                "ts_trail_pct": _p_float("回撤锁定(%)", "从最高价回撤超过该比例时卖出。", 0.1, 50, 0.1, section="趋势卖出",
                                         show_if={"field": "trend_sell", "value": "profit_lock"}),

                # ── 震荡买入 ──
                "range_buy": _p_select("震荡买入条件", "震荡行情下的买入信号", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "rsi_oversold", "label": "RSI超卖"},
                    {"value": "boll_lower", "label": "布林下轨"},
                    {"value": "bias_low", "label": "乖离率低"},
                ], section="震荡买入"),
                # RSI超卖 子参数
                "rb_rsi_period": _p_int("RSI周期", "RSI计算周期。", 2, 200, section="震荡买入",
                                        show_if={"field": "range_buy", "value": "rsi_oversold"}),
                "rb_rsi_oversold": _p_float("RSI超卖阈值", "RSI < 该值时触发买入。", 1, 60, 1, section="震荡买入",
                                             show_if={"field": "range_buy", "value": "rsi_oversold"}),
                # 布林下轨 子参数
                "rb_boll_period": _p_int("布林周期", "布林带中轨周期。", 5, 250, section="震荡买入",
                                         show_if={"field": "range_buy", "value": "boll_lower"}),
                "rb_boll_devfactor": _p_float("布林倍数", "布林带标准差倍数。", 0.5, 6.0, 0.1, section="震荡买入",
                                               show_if={"field": "range_buy", "value": "boll_lower"}),
                # 乖离率低 子参数
                "rb_bias_period": _p_int("乖离率周期", "乖离率的均线周期。", 2, 250, section="震荡买入",
                                         show_if={"field": "range_buy", "value": "bias_low"}),
                "rb_bias_threshold": _p_float("乖离率阈值(%)", "乖离率 < 该值时触发买入（负值）。", -50, 0, 0.1, section="震荡买入",
                                               show_if={"field": "range_buy", "value": "bias_low"}),

                # ── 震荡卖出 ──
                "range_sell": _p_select("震荡卖出条件", "震荡行情下的卖出信号", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "rsi_overbought", "label": "RSI超买"},
                    {"value": "boll_upper", "label": "布林上轨"},
                ], section="震荡卖出"),
                # RSI超买 子参数
                "rs_rsi_period": _p_int("RSI周期", "RSI计算周期。", 2, 200, section="震荡卖出",
                                        show_if={"field": "range_sell", "value": "rsi_overbought"}),
                "rs_rsi_overbought": _p_float("RSI超买阈值", "RSI > 该值时触发卖出。", 40, 99, 1, section="震荡卖出",
                                               show_if={"field": "range_sell", "value": "rsi_overbought"}),
                # 布林上轨 子参数
                "rs_boll_period": _p_int("布林周期", "布林带中轨周期。", 5, 250, section="震荡卖出",
                                         show_if={"field": "range_sell", "value": "boll_upper"}),
                "rs_boll_devfactor": _p_float("布林倍数", "布林带标准差倍数。", 0.5, 6.0, 0.1, section="震荡卖出",
                                               show_if={"field": "range_sell", "value": "boll_upper"}),

                # ── 过渡买入 ──
                "trans_buy": _p_select("过渡买入条件", "过渡行情下的买入信号（默认空仓，即过渡期不操作）", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "macd_cross", "label": "MACD金叉"},
                    {"value": "ma_cross", "label": "MA交叉"},
                    {"value": "breakout", "label": "突破新高"},
                    {"value": "rsi_oversold", "label": "RSI超卖"},
                    {"value": "boll_lower", "label": "布林下轨"},
                ], section="过渡买入"),
                "trb_macd_fast": _p_int("MACD快线", "MACD快线周期。", 2, 200, section="过渡买入",
                                         show_if={"field": "trans_buy", "value": "macd_cross"}),
                "trb_macd_slow": _p_int("MACD慢线", "MACD慢线周期。", 3, 400, section="过渡买入",
                                         show_if={"field": "trans_buy", "value": "macd_cross"}),
                "trb_macd_signal": _p_int("MACD信号线", "MACD信号线周期。", 2, 200, section="过渡买入",
                                           show_if={"field": "trans_buy", "value": "macd_cross"}),
                "trb_ma_fast": _p_int("MA快线", "MA交叉快线周期。", 2, 200, section="过渡买入",
                                      show_if={"field": "trans_buy", "value": "ma_cross"}),
                "trb_ma_slow": _p_int("MA慢线", "MA交叉慢线周期。", 3, 400, section="过渡买入",
                                      show_if={"field": "trans_buy", "value": "ma_cross"}),
                "trb_breakout_period": _p_int("突破回看周期", "突破新高的回看周期。", 2, 400, section="过渡买入",
                                              show_if={"field": "trans_buy", "value": "breakout"}),
                "trb_rsi_period": _p_int("RSI周期", "RSI计算周期。", 2, 200, section="过渡买入",
                                         show_if={"field": "trans_buy", "value": "rsi_oversold"}),
                "trb_rsi_oversold": _p_float("RSI超卖阈值", "RSI < 该值时触发买入。", 1, 60, 1, section="过渡买入",
                                             show_if={"field": "trans_buy", "value": "rsi_oversold"}),
                "trb_boll_period": _p_int("布林周期", "布林带中轨周期。", 5, 250, section="过渡买入",
                                          show_if={"field": "trans_buy", "value": "boll_lower"}),
                "trb_boll_devfactor": _p_float("布林倍数", "布林带标准差倍数。", 0.5, 6.0, 0.1, section="过渡买入",
                                               show_if={"field": "trans_buy", "value": "boll_lower"}),

                # ── 过渡卖出 ──
                "trans_sell": _p_select("过渡卖出条件", "过渡行情下的卖出信号（默认空仓，即过渡期不操作）", [
                    {"value": "empty", "label": "空仓"},
                    {"value": "macd_dead_cross", "label": "MACD死叉"},
                    {"value": "atr_stop", "label": "ATR跟踪止损"},
                    {"value": "profit_lock", "label": "利润锁定"},
                    {"value": "rsi_overbought", "label": "RSI超买"},
                    {"value": "boll_upper", "label": "布林上轨"},
                ], section="过渡卖出"),
                "trs_macd_fast": _p_int("MACD快线", "MACD快线周期。", 2, 200, section="过渡卖出",
                                         show_if={"field": "trans_sell", "value": "macd_dead_cross"}),
                "trs_macd_slow": _p_int("MACD慢线", "MACD慢线周期。", 3, 400, section="过渡卖出",
                                         show_if={"field": "trans_sell", "value": "macd_dead_cross"}),
                "trs_macd_signal": _p_int("MACD信号线", "MACD信号线周期。", 2, 200, section="过渡卖出",
                                           show_if={"field": "trans_sell", "value": "macd_dead_cross"}),
                "trs_atr_period": _p_int("ATR周期", "ATR计算周期。", 2, 200, section="过渡卖出",
                                         show_if={"field": "trans_sell", "value": "atr_stop"}),
                "trs_atr_mult": _p_float("ATR倍数", "ATR止损距离：最高价 - ATR倍数 * ATR。", 0.1, 10.0, 0.1, section="过渡卖出",
                                         show_if={"field": "trans_sell", "value": "atr_stop"}),
                "trs_profit_trigger": _p_float("利润触发(%)", "收益率达到该阈值后启动利润锁定。", 0.1, 200, 0.1, section="过渡卖出",
                                               show_if={"field": "trans_sell", "value": "profit_lock"}),
                "trs_trail_pct": _p_float("回撤锁定(%)", "从最高价回撤超过该比例时卖出。", 0.1, 50, 0.1, section="过渡卖出",
                                          show_if={"field": "trans_sell", "value": "profit_lock"}),
                "trs_rsi_period": _p_int("RSI周期", "RSI计算周期。", 2, 200, section="过渡卖出",
                                         show_if={"field": "trans_sell", "value": "rsi_overbought"}),
                "trs_rsi_overbought": _p_float("RSI超买阈值", "RSI > 该值时触发卖出。", 40, 99, 1, section="过渡卖出",
                                               show_if={"field": "trans_sell", "value": "rsi_overbought"}),
                "trs_boll_period": _p_int("布林周期", "布林带中轨周期。", 5, 250, section="过渡卖出",
                                          show_if={"field": "trans_sell", "value": "boll_upper"}),
                "trs_boll_devfactor": _p_float("布林倍数", "布林带标准差倍数。", 0.5, 6.0, 0.1, section="过渡卖出",
                                               show_if={"field": "trans_sell", "value": "boll_upper"}),

                # ── 通用止损 ──
                "use_atr_stop": _p_bool("启用ATR止损", "持仓期间使用ATR跟踪止损作为通用止损保护。", section="通用止损"),
                "atr_stop_period": _p_int("止损ATR周期", "通用止损ATR计算周期。", 2, 200, section="通用止损",
                                          show_if={"field": "use_atr_stop", "value": True}),
                "atr_stop_mult": _p_float("止损ATR倍数", "止损距离：收盘价 - 倍数 * ATR。", 0.1, 10.0, 0.1, section="通用止损",
                                          show_if={"field": "use_atr_stop", "value": True}),
            },
            default_params={
                "detector_type": "adx",
                "adx_period": 14, "adx_trend_threshold": 25.0, "adx_range_threshold": 20.0,
                "det_ma_fast": 10, "det_ma_slow": 30,
                "det_boll_period": 20, "det_boll_devfactor": 2.0,
                "trend_buy": "macd_cross",
                "tb_macd_fast": 12, "tb_macd_slow": 26, "tb_macd_signal": 9,
                "tb_ma_fast": 5, "tb_ma_slow": 20,
                "tb_breakout_period": 20,
                "trend_sell": "atr_stop",
                "ts_macd_fast": 12, "ts_macd_slow": 26, "ts_macd_signal": 9,
                "ts_atr_period": 14, "ts_atr_mult": 2.5,
                "ts_profit_trigger": 5.0, "ts_trail_pct": 3.0,
                "range_buy": "rsi_oversold",
                "rb_rsi_period": 14, "rb_rsi_oversold": 30.0,
                "rb_boll_period": 20, "rb_boll_devfactor": 2.0,
                "rb_bias_period": 20, "rb_bias_threshold": -6.0,
                "range_sell": "rsi_overbought",
                "rs_rsi_period": 14, "rs_rsi_overbought": 70.0,
                "rs_boll_period": 20, "rs_boll_devfactor": 2.0,
                "trans_buy": "empty",
                "trb_macd_fast": 12, "trb_macd_slow": 26, "trb_macd_signal": 9,
                "trb_ma_fast": 5, "trb_ma_slow": 20,
                "trb_breakout_period": 20,
                "trb_rsi_period": 14, "trb_rsi_oversold": 30.0,
                "trb_boll_period": 20, "trb_boll_devfactor": 2.0,
                "trans_sell": "empty",
                "trs_macd_fast": 12, "trs_macd_slow": 26, "trs_macd_signal": 9,
                "trs_atr_period": 14, "trs_atr_mult": 2.5,
                "trs_profit_trigger": 5.0, "trs_trail_pct": 3.0,
                "trs_rsi_period": 14, "trs_rsi_overbought": 70.0,
                "trs_boll_period": 20, "trs_boll_devfactor": 2.0,
                "use_atr_stop": True,
                "atr_stop_period": 14, "atr_stop_mult": 2.0,
            },
            bt_strategy_factory=_make_combo_custom,
            group="combo",
        ),
    }
