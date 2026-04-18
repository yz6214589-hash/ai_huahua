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
                self.sell()

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

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            raw_shares = risk / (float(self.p.stop_n) * atr)
            shares = int(raw_shares / price)
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            close = float(self.data.close[0])
            atr = float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.entry_price = close
                        self.stop_price = close - float(self.p.stop_n) * atr
                        self.next_add = close + float(self.p.add_n) * atr
                return

            if close > float(self.entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.entry_price = close
                    self.stop_price = close - float(self.p.stop_n) * atr
                    self.next_add = close + float(self.p.add_n) * atr

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

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            raw_shares = risk / (float(self.p.stop_n) * atr)
            shares = int(raw_shares / price)
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            close = float(self.data.close[0])
            atr = float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.entry_price = None
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.entry_price = close
                        self.stop_price = close - float(self.p.stop_n) * atr
                        self.next_add = close + float(self.p.add_n) * atr
                return

            if float(self.adx[0]) < float(self.p.adx_threshold):
                return

            if close > float(self.entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.entry_price = close
                    self.stop_price = close - float(self.p.stop_n) * atr
                    self.next_add = close + float(self.p.add_n) * atr

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

        def _weekly_trend(self) -> str:
            wc = float(self.data1.close[0])
            if wc > float(self.weekly_high[-1]):
                return "up"
            if wc < float(self.weekly_low[-1]):
                return "down"
            return "neutral"

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            raw_shares = risk / (float(self.p.stop_n) * atr)
            shares = int(raw_shares / price)
            shares = (shares // 100) * 100
            return max(100, shares) if shares > 0 else 0

        def next(self) -> None:
            close = float(self.data0.close[0])
            atr = float(self.atr[0])
            trend = self._weekly_trend()

            if self.position:
                if trend == "down":
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.stop_price is not None and close < float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < float(self.daily_exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.stop_price = close - float(self.p.stop_n) * atr
                        self.next_add = close + float(self.p.add_n) * atr
                return

            if trend == "down":
                return

            if close > float(self.daily_entry_high[-1]):
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.stop_price = close - float(self.p.stop_n) * atr
                    self.next_add = close + float(self.p.add_n) * atr

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

        def _unit_size(self, price: float, atr: float) -> int:
            if price <= 0 or atr <= 0:
                return 0
            value = float(self.broker.getvalue())
            risk = value * float(self.p.risk_pct)
            raw_shares = risk / (float(self.p.stop_n) * atr)
            shares = int(raw_shares / price)
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
            close = float(self.data.close[0])
            atr = float(self.atr[0])

            if self.position:
                if self.stop_price is not None and close < float(self.stop_price):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if close < float(self.exit_low[-1]):
                    self.sell(size=int(self.position.size))
                    self.units = 0
                    self.stop_price = None
                    self.next_add = None
                    return
                if self.units < int(self.p.max_units) and self.next_add is not None and close > float(self.next_add):
                    size = self._unit_size(close, atr)
                    if size > 0:
                        self.buy(size=size)
                        self.units += 1
                        self.stop_price = close - float(self.p.stop_n) * atr
                        self.next_add = close + float(self.p.add_n) * atr
                return

            if close > float(self.entry_high[-1]):
                prob = self._prob()
                if prob is None or prob < float(self.p.ml_threshold):
                    return
                size = self._unit_size(close, atr)
                if size > 0:
                    self.buy(size=size)
                    self.units = 1
                    self.stop_price = close - float(self.p.stop_n) * atr
                    self.next_add = close + float(self.p.add_n) * atr

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

    from zoe.app.grid_engine import GridEngine

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
                lo = float(self.range_low[0])
                hi = float(self.range_high[0])
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

    from zoe.app.grid_engine import ChanGridEngine

    class ChanGrid(bt.Strategy):
        params = dict(num_grids=6, capital_ratio=0.80, exit_on_breakout=True, breakout_pct=0.005)

        def __init__(self) -> None:
            self.engine = None
            self.last_zg = None
            self.last_zd = None

        def _has_center(self) -> bool:
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)
            zd = float(getattr(self.data, "chan_zd", [0.0])[0] or 0.0)
            return zg > 0 and zd > 0 and zg > zd

        def next(self) -> None:
            close = float(self.data.close[0])
            zg = float(getattr(self.data, "chan_zg", [0.0])[0] or 0.0)
            zd = float(getattr(self.data, "chan_zd", [0.0])[0] or 0.0)

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

    from zoe.app.grid_engine import ChanGridEngine

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


def get_strategy_registry() -> dict[str, StrategyMeta]:
    return {
        "ma_dual": StrategyMeta(
            strategy_id="ma_dual",
            name="MA双均线策略",
            description="快均线上穿慢均线买入，下穿卖出",
            params_schema={"fast": {"type": "int", "min": 2, "max": 250}, "slow": {"type": "int", "min": 3, "max": 400}},
            default_params={"fast": 10, "slow": 30},
            bt_strategy_factory=_make_dual_ma,
        ),
        "macd_basic": StrategyMeta(
            strategy_id="macd_basic",
            name="MACD策略",
            description="DIF上穿DEA买入，下穿卖出",
            params_schema={"fast": {"type": "int"}, "slow": {"type": "int"}, "signal": {"type": "int"}},
            default_params={"fast": 12, "slow": 26, "signal": 9},
            bt_strategy_factory=_make_macd_basic,
        ),
        "rsi_basic": StrategyMeta(
            strategy_id="rsi_basic",
            name="RSI策略",
            description="RSI低于超卖阈值买入，高于超买阈值卖出",
            params_schema={"period": {"type": "int"}, "oversold": {"type": "float"}, "overbought": {"type": "float"}},
            default_params={"period": 14, "oversold": 30, "overbought": 70},
            bt_strategy_factory=_make_rsi_basic,
        ),
        "boll_basic": StrategyMeta(
            strategy_id="boll_basic",
            name="布林带策略",
            description="跌破下轨买入，上穿上轨卖出",
            params_schema={"period": {"type": "int"}, "devfactor": {"type": "float"}},
            default_params={"period": 20, "devfactor": 2.0},
            bt_strategy_factory=_make_boll_basic,
        ),
        "bias": StrategyMeta(
            strategy_id="bias",
            name="乖离率策略",
            description="BIAS低于阈值买入，高于阈值卖出",
            params_schema={"period": {"type": "int"}, "buy_threshold": {"type": "float"}, "sell_threshold": {"type": "float"}},
            default_params={"period": 20, "buy_threshold": -6.0, "sell_threshold": 3.0},
            bt_strategy_factory=_make_bias,
        ),
        "momentum": StrategyMeta(
            strategy_id="momentum",
            name="动量策略",
            description="ROC高于阈值买入，低于负阈值卖出",
            params_schema={"period": {"type": "int"}, "threshold": {"type": "float"}},
            default_params={"period": 20, "threshold": 5.0},
            bt_strategy_factory=_make_momentum,
        ),
        "momentum_fast": StrategyMeta(
            strategy_id="momentum_fast",
            name="动量策略(快)",
            description="ROC更短周期版本",
            params_schema={"period": {"type": "int"}, "threshold": {"type": "float"}},
            default_params={"period": 10, "threshold": 3.0},
            bt_strategy_factory=_make_momentum,
        ),
        "rsi_cross_confirm": StrategyMeta(
            strategy_id="rsi_cross_confirm",
            name="RSI增强-穿越确认",
            description="RSI从超卖区向上穿越阈值后买入，RSI超买卖出",
            params_schema={"period": {"type": "int"}, "oversold": {"type": "float"}, "overbought": {"type": "float"}},
            default_params={"period": 14, "oversold": 30, "overbought": 70},
            bt_strategy_factory=_make_rsi_cross_confirm,
        ),
        "macd_vol_confirm": StrategyMeta(
            strategy_id="macd_vol_confirm",
            name="MACD增强-成交量确认",
            description="MACD金叉且成交量满足条件才买入，死叉卖出",
            params_schema={
                "fast": {"type": "int"},
                "slow": {"type": "int"},
                "signal": {"type": "int"},
                "vol_period": {"type": "int"},
                "vol_mult": {"type": "float"},
            },
            default_params={"fast": 12, "slow": 26, "signal": 9, "vol_period": 20, "vol_mult": 0.9},
            bt_strategy_factory=_make_macd_vol_confirm,
        ),
        "macd_profit_lock": StrategyMeta(
            strategy_id="macd_profit_lock",
            name="MACD增强-利润锁定",
            description="MACD金叉入场；达到触发利润后用回撤锁定；死叉也出场",
            params_schema={
                "fast": {"type": "int"},
                "slow": {"type": "int"},
                "signal": {"type": "int"},
                "profit_trigger": {"type": "float"},
                "trail_pct": {"type": "float"},
            },
            default_params={"fast": 12, "slow": 26, "signal": 9, "profit_trigger": 5.0, "trail_pct": 3.0},
            bt_strategy_factory=_make_macd_profit_lock,
        ),
        "boll_mid_stop": StrategyMeta(
            strategy_id="boll_mid_stop",
            name="布林带增强-中轨止损",
            description="下轨买入，上轨止盈；反弹到中轨后再跌破中轨止损",
            params_schema={"period": {"type": "int"}, "devfactor": {"type": "float"}},
            default_params={"period": 20, "devfactor": 2.0},
            bt_strategy_factory=_make_boll_mid_stop,
        ),
        "adaptive": StrategyMeta(
            strategy_id="adaptive",
            name="综合增强-自适应策略",
            description="ADX分趋势/震荡，趋势用MACD，震荡用RSI，统一ATR跟踪止损",
            params_schema={
                "adx_period": {"type": "int"},
                "adx_trend": {"type": "float"},
                "adx_range": {"type": "float"},
                "atr_period": {"type": "int"},
                "atr_mult": {"type": "float"},
                "macd_fast": {"type": "int"},
                "macd_slow": {"type": "int"},
                "macd_signal": {"type": "int"},
                "rsi_period": {"type": "int"},
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
        ),
        "macd_divergence": StrategyMeta(
            strategy_id="macd_divergence",
            name="MACD底背离策略",
            description="价格接近低点且MACD高于低点并金叉态时买入，死叉确认卖出",
            params_schema={"lookback": {"type": "int"}, "fast": {"type": "int"}, "slow": {"type": "int"}, "signal": {"type": "int"}},
            default_params={"lookback": 30, "fast": 12, "slow": 26, "signal": 9},
            bt_strategy_factory=_make_macd_divergence,
        ),
        "turtle_simple": StrategyMeta(
            strategy_id="turtle_simple",
            name="简单海龟交易法则",
            description="20日上轨突破入场，10日下轨出场",
            params_schema={"entry_period": {"type": "int"}, "exit_period": {"type": "int"}},
            default_params={"entry_period": 20, "exit_period": 10},
            bt_strategy_factory=_make_turtle_simple,
        ),
        "turtle_full": StrategyMeta(
            strategy_id="turtle_full",
            name="完整海龟交易法则",
            description="通道突破入场 + ATR风险仓位 + 金字塔加仓 + 2N止损 + 下轨出场",
            params_schema={
                "entry_period": {"type": "int"},
                "exit_period": {"type": "int"},
                "atr_period": {"type": "int"},
                "risk_pct": {"type": "float"},
                "max_units": {"type": "int"},
                "add_n": {"type": "float"},
                "stop_n": {"type": "float"},
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
        ),
        "turtle_adx": StrategyMeta(
            strategy_id="turtle_adx",
            name="ADX海龟策略",
            description="海龟突破前增加ADX过滤",
            params_schema={
                "entry_period": {"type": "int"},
                "exit_period": {"type": "int"},
                "atr_period": {"type": "int"},
                "adx_period": {"type": "int"},
                "adx_threshold": {"type": "float"},
                "risk_pct": {"type": "float"},
                "max_units": {"type": "int"},
                "add_n": {"type": "float"},
                "stop_n": {"type": "float"},
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
        ),
        "turtle_multi_tf": StrategyMeta(
            strategy_id="turtle_multi_tf",
            name="多周期海龟策略",
            description="周线定方向，日线执行突破/出场与加仓",
            params_schema={
                "daily_entry": {"type": "int"},
                "daily_exit": {"type": "int"},
                "weekly_period": {"type": "int"},
                "atr_period": {"type": "int"},
                "risk_pct": {"type": "float"},
                "max_units": {"type": "int"},
                "add_n": {"type": "float"},
                "stop_n": {"type": "float"},
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
        ),
        "turtle_ml": StrategyMeta(
            strategy_id="turtle_ml",
            name="ML增强海龟策略",
            description="突破信号需满足预测概率阈值才入场（predictions需传入）",
            params_schema={
                "entry_period": {"type": "int"},
                "exit_period": {"type": "int"},
                "atr_period": {"type": "int"},
                "risk_pct": {"type": "float"},
                "max_units": {"type": "int"},
                "add_n": {"type": "float"},
                "stop_n": {"type": "float"},
                "ml_threshold": {"type": "float"},
                "predictions": {"type": "object"},
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
        ),
        "chan_third_buy": StrategyMeta(
            strategy_id="chan_third_buy",
            name="经典缠论-基础三买",
            description="依赖数据中的 chan_signal/chan_zg/chan_zd（未提供则不会触发交易）",
            params_schema={
                "take_profit_pct": {"type": "float"},
                "use_chan_stop": {"type": "bool"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={"take_profit_pct": 0.15, "use_chan_stop": True, "chan_backend": "chanpy"},
            bt_strategy_factory=_make_chan_third_buy,
            requires_chan=True,
        ),
        "chan_trailing": StrategyMeta(
            strategy_id="chan_trailing",
            name="缠论-量价增强策略",
            description="三买入场，阶梯止损+ATR跟踪止损+三卖离场；依赖 chan_* 字段",
            params_schema={
                "take_profit_pct": {"type": "float"},
                "use_chan_stop": {"type": "bool"},
                "atr_period": {"type": "int"},
                "atr_exit_mult": {"type": "float"},
                "breakeven_pct": {"type": "float"},
                "lock_profit_pct": {"type": "float"},
                "lock_amount_pct": {"type": "float"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={
                "take_profit_pct": 0.15,
                "use_chan_stop": True,
                "atr_period": 14,
                "atr_exit_mult": 2.5,
                "breakeven_pct": 0.05,
                "lock_profit_pct": 0.10,
                "lock_amount_pct": 0.05,
                "chan_backend": "chanpy",
            },
            bt_strategy_factory=_make_chan_trailing_stop,
            requires_chan=True,
        ),
        "chan_multi_tf": StrategyMeta(
            strategy_id="chan_multi_tf",
            name="缠论-多周期缠论策略",
            description="周线过滤逆势信号（日线三买仅在周线向上时做）；依赖 chan_* 字段",
            params_schema={
                "take_profit_pct": {"type": "float"},
                "weekly_ma_period": {"type": "int"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={"take_profit_pct": 0.15, "weekly_ma_period": 20, "chan_backend": "chanpy"},
            bt_strategy_factory=_make_chan_multi_tf,
            requires_chan=True,
            requires_weekly=True,
        ),
        "chan_ml": StrategyMeta(
            strategy_id="chan_ml",
            name="缠论-ML增强缠论策略",
            description="三买信号需满足预测概率阈值才入场（predictions需传入），依赖 chan_* 字段",
            params_schema={
                "take_profit_pct": {"type": "float"},
                "ml_threshold": {"type": "float"},
                "predictions": {"type": "object"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={"take_profit_pct": 0.15, "ml_threshold": 0.5, "predictions": {}, "chan_backend": "chanpy"},
            bt_strategy_factory=_make_chan_ml,
            requires_chan=True,
            requires_predictions=True,
        ),
        "grid_classic": StrategyMeta(
            strategy_id="grid_classic",
            name="经典网格交易",
            description="回看区间构建网格，穿格买卖（震荡收租）",
            params_schema={
                "lookback": {"type": "int"},
                "num_grids": {"type": "int"},
                "margin_pct": {"type": "float"},
                "capital_ratio": {"type": "float"},
            },
            default_params={"lookback": 60, "num_grids": 8, "margin_pct": 0.02, "capital_ratio": 0.90},
            bt_strategy_factory=_make_grid_classic,
        ),
        "chan_grid": StrategyMeta(
            strategy_id="chan_grid",
            name="缠论中枢网络策略",
            description="中枢ZG/ZD作为网格边界，突破则清仓停用；依赖 chan_zg/chan_zd",
            params_schema={
                "num_grids": {"type": "int"},
                "capital_ratio": {"type": "float"},
                "exit_on_breakout": {"type": "bool"},
                "breakout_pct": {"type": "float"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={"num_grids": 6, "capital_ratio": 0.80, "exit_on_breakout": True, "breakout_pct": 0.005, "chan_backend": "chanpy"},
            bt_strategy_factory=_make_chan_grid,
            requires_chan=True,
        ),
        "chan_grid_trend": StrategyMeta(
            strategy_id="chan_grid_trend",
            name="中枢网格+趋势联动",
            description="中枢内网格，上破转趋势（ATR跟踪），下破转空；依赖 chan_* 字段",
            params_schema={
                "num_grids": {"type": "int"},
                "capital_ratio": {"type": "float"},
                "atr_period": {"type": "int"},
                "atr_trail_mult": {"type": "float"},
                "breakout_confirm": {"type": "float"},
                "chan_backend": {"type": "enum", "values": ["chanpy", "self"]},
            },
            default_params={"num_grids": 6, "capital_ratio": 0.80, "atr_period": 14, "atr_trail_mult": 2.5, "breakout_confirm": 0.005, "chan_backend": "chanpy"},
            bt_strategy_factory=_make_chan_grid_trend_linkage,
            requires_chan=True,
        ),
    }

