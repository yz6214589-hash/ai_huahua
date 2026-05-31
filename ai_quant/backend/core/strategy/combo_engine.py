# -*- coding: utf-8 -*-
"""
策略组合引擎
基于行情判别（ADX/MA/布林带）自动切换趋势/震荡/过渡模式，
分别匹配不同的买入/卖出条件，支持自定义参数。
选择"空仓"时该行情类型下不产生任何信号。
"""
from __future__ import annotations


def _safe_float(val, default: float = 0.0) -> float:
    """安全地将值转换为浮点数"""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def make_combo_strategy():
    """创建策略组合引擎的 backtrader Strategy 类"""
    import backtrader as bt

    class ComboStrategy(bt.Strategy):
        params = dict(
            # 行情判别
            detector_type="adx",
            adx_period=14,
            adx_trend_threshold=25.0,
            adx_range_threshold=20.0,
            det_ma_fast=10,
            det_ma_slow=30,
            det_boll_period=20,
            det_boll_devfactor=2.0,
            # 趋势买入
            trend_buy="macd_cross",
            tb_macd_fast=12,
            tb_macd_slow=26,
            tb_macd_signal=9,
            tb_ma_fast=5,
            tb_ma_slow=20,
            tb_breakout_period=20,
            # 趋势卖出
            trend_sell="atr_stop",
            ts_macd_fast=12,
            ts_macd_slow=26,
            ts_macd_signal=9,
            ts_atr_period=14,
            ts_atr_mult=2.5,
            ts_profit_trigger=5.0,
            ts_trail_pct=3.0,
            # 震荡买入
            range_buy="rsi_oversold",
            rb_rsi_period=14,
            rb_rsi_oversold=30.0,
            rb_boll_period=20,
            rb_boll_devfactor=2.0,
            rb_bias_period=20,
            rb_bias_threshold=-6.0,
            # 震荡卖出
            range_sell="rsi_overbought",
            rs_rsi_period=14,
            rs_rsi_overbought=70.0,
            rs_boll_period=20,
            rs_boll_devfactor=2.0,
            # 过渡买入
            trans_buy="empty",
            trb_macd_fast=12,
            trb_macd_slow=26,
            trb_macd_signal=9,
            trb_ma_fast=5,
            trb_ma_slow=20,
            trb_breakout_period=20,
            trb_rsi_period=14,
            trb_rsi_oversold=30.0,
            trb_boll_period=20,
            trb_boll_devfactor=2.0,
            # 过渡卖出
            trans_sell="empty",
            trs_macd_fast=12,
            trs_macd_slow=26,
            trs_macd_signal=9,
            trs_atr_period=14,
            trs_atr_mult=2.5,
            trs_profit_trigger=5.0,
            trs_trail_pct=3.0,
            trs_rsi_period=14,
            trs_rsi_overbought=70.0,
            trs_boll_period=20,
            trs_boll_devfactor=2.0,
            # 通用止损
            use_atr_stop=True,
            atr_stop_period=14,
            atr_stop_mult=2.0,
        )

        def __init__(self) -> None:
            # 行情判别指标
            self.adx = bt.indicators.ADX(self.data, period=int(self.p.adx_period))
            self.det_ma_fast = bt.indicators.SMA(self.data.close, period=int(self.p.det_ma_fast))
            self.det_ma_slow = bt.indicators.SMA(self.data.close, period=int(self.p.det_ma_slow))
            self.det_boll = bt.indicators.BollingerBands(
                self.data.close, period=int(self.p.det_boll_period),
                devfactor=float(self.p.det_boll_devfactor),
            )
            # 趋势买入指标
            self.tb_macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.tb_macd_fast),
                period_me2=int(self.p.tb_macd_slow),
                period_signal=int(self.p.tb_macd_signal),
            )
            self.tb_macd_cross = bt.indicators.CrossOver(self.tb_macd.macd, self.tb_macd.signal)
            self.tb_ma_fast = bt.indicators.SMA(self.data.close, period=int(self.p.tb_ma_fast))
            self.tb_ma_slow = bt.indicators.SMA(self.data.close, period=int(self.p.tb_ma_slow))
            self.tb_ma_cross = bt.indicators.CrossOver(self.tb_ma_fast, self.tb_ma_slow)
            self.tb_entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.tb_breakout_period))
            # 趋势卖出指标
            self.ts_macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.ts_macd_fast),
                period_me2=int(self.p.ts_macd_slow),
                period_signal=int(self.p.ts_macd_signal),
            )
            self.ts_macd_cross = bt.indicators.CrossOver(self.ts_macd.macd, self.ts_macd.signal)
            self.ts_atr = bt.indicators.ATR(self.data, period=int(self.p.ts_atr_period))
            # 震荡买入指标
            self.rb_rsi = bt.indicators.RSI(self.data.close, period=int(self.p.rb_rsi_period))
            self.rb_boll = bt.indicators.BollingerBands(
                self.data.close, period=int(self.p.rb_boll_period),
                devfactor=float(self.p.rb_boll_devfactor),
            )
            self.rb_bias_ma = bt.indicators.SMA(self.data.close, period=int(self.p.rb_bias_period))
            # 震荡卖出指标
            self.rs_rsi = bt.indicators.RSI(self.data.close, period=int(self.p.rs_rsi_period))
            self.rs_boll = bt.indicators.BollingerBands(
                self.data.close, period=int(self.p.rs_boll_period),
                devfactor=float(self.p.rs_boll_devfactor),
            )
            # 过渡买入指标
            self.trb_macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.trb_macd_fast),
                period_me2=int(self.p.trb_macd_slow),
                period_signal=int(self.p.trb_macd_signal),
            )
            self.trb_macd_cross = bt.indicators.CrossOver(self.trb_macd.macd, self.trb_macd.signal)
            self.trb_ma_fast = bt.indicators.SMA(self.data.close, period=int(self.p.trb_ma_fast))
            self.trb_ma_slow = bt.indicators.SMA(self.data.close, period=int(self.p.trb_ma_slow))
            self.trb_ma_cross = bt.indicators.CrossOver(self.trb_ma_fast, self.trb_ma_slow)
            self.trb_entry_high = bt.indicators.Highest(self.data.high, period=int(self.p.trb_breakout_period))
            self.trb_rsi = bt.indicators.RSI(self.data.close, period=int(self.p.trb_rsi_period))
            self.trb_boll = bt.indicators.BollingerBands(
                self.data.close, period=int(self.p.trb_boll_period),
                devfactor=float(self.p.trb_boll_devfactor),
            )
            # 过渡卖出指标
            self.trs_macd = bt.indicators.MACD(
                self.data.close,
                period_me1=int(self.p.trs_macd_fast),
                period_me2=int(self.p.trs_macd_slow),
                period_signal=int(self.p.trs_macd_signal),
            )
            self.trs_macd_cross = bt.indicators.CrossOver(self.trs_macd.macd, self.trs_macd.signal)
            self.trs_atr = bt.indicators.ATR(self.data, period=int(self.p.trs_atr_period))
            self.trs_rsi = bt.indicators.RSI(self.data.close, period=int(self.p.trs_rsi_period))
            self.trs_boll = bt.indicators.BollingerBands(
                self.data.close, period=int(self.p.trs_boll_period),
                devfactor=float(self.p.trs_boll_devfactor),
            )
            # 通用止损指标
            self.stop_atr = bt.indicators.ATR(self.data, period=int(self.p.atr_stop_period))
            # 状态
            self.entry_price = None
            self.peak_price = None
            self.stop_price = None

        def _detect_market(self) -> str:
            """行情判别：根据配置的方式判断当前为趋势/震荡/过渡"""
            dt = str(self.p.detector_type)
            if dt == "adx":
                adx_val = _safe_float(self.adx[0])
                if adx_val > float(self.p.adx_trend_threshold):
                    return "trend"
                if adx_val < float(self.p.adx_range_threshold):
                    return "range"
                return "neutral"
            if dt == "ma":
                if _safe_float(self.det_ma_fast[0]) > _safe_float(self.det_ma_slow[0]):
                    return "trend"
                return "range"
            if dt == "boll":
                close = _safe_float(self.data.close[0])
                mid = _safe_float(self.det_boll.mid[0])
                top = _safe_float(self.det_boll.top[0])
                bot = _safe_float(self.det_boll.bot[0])
                if mid > 0:
                    bw = (top - bot) / mid
                    if close > top or close < bot:
                        return "trend"
                return "range"
            return "neutral"

        def _trend_buy_signal(self) -> bool:
            """趋势买入信号判断"""
            bt_type = str(self.p.trend_buy)
            if bt_type == "empty":
                return False
            if bt_type == "macd_cross":
                return _safe_float(self.tb_macd_cross[0]) > 0
            if bt_type == "ma_cross":
                return _safe_float(self.tb_ma_cross[0]) > 0
            if bt_type == "breakout":
                return _safe_float(self.data.close[0]) > _safe_float(self.tb_entry_high[-1])
            return False

        def _trend_sell_signal(self) -> bool:
            """趋势卖出信号判断"""
            st = str(self.p.trend_sell)
            if st == "empty":
                return False
            if st == "macd_dead_cross":
                return _safe_float(self.ts_macd_cross[0]) < 0
            if st == "atr_stop":
                if self.peak_price is not None and _safe_float(self.ts_atr[0]) > 0:
                    trail = float(self.peak_price) - float(self.p.ts_atr_mult) * _safe_float(self.ts_atr[0])
                    return _safe_float(self.data.close[0]) < trail
                return False
            if st == "profit_lock":
                if self.entry_price is not None and float(self.entry_price) > 0:
                    close = _safe_float(self.data.close[0])
                    profit_pct = (close - float(self.entry_price)) / float(self.entry_price) * 100.0
                    if profit_pct >= float(self.p.ts_profit_trigger):
                        if self.peak_price is not None:
                            drop_pct = (float(self.peak_price) - close) / float(self.peak_price) * 100.0
                            return drop_pct >= float(self.p.ts_trail_pct)
                return False
            return False

        def _range_buy_signal(self) -> bool:
            """震荡买入信号判断"""
            bt_type = str(self.p.range_buy)
            if bt_type == "empty":
                return False
            if bt_type == "rsi_oversold":
                return _safe_float(self.rb_rsi[0]) < float(self.p.rb_rsi_oversold)
            if bt_type == "boll_lower":
                return _safe_float(self.data.close[0]) < _safe_float(self.rb_boll.bot[0])
            if bt_type == "bias_low":
                ma = _safe_float(self.rb_bias_ma[0])
                if ma > 0:
                    bias = (_safe_float(self.data.close[0]) - ma) / ma * 100.0
                    return bias < float(self.p.rb_bias_threshold)
                return False
            return False

        def _range_sell_signal(self) -> bool:
            """震荡卖出信号判断"""
            st = str(self.p.range_sell)
            if st == "empty":
                return False
            if st == "rsi_overbought":
                return _safe_float(self.rs_rsi[0]) > float(self.p.rs_rsi_overbought)
            if st == "boll_upper":
                return _safe_float(self.data.close[0]) > _safe_float(self.rs_boll.top[0])
            return False

        def _trans_buy_signal(self) -> bool:
            """过渡买入信号判断"""
            bt_type = str(self.p.trans_buy)
            if bt_type == "empty":
                return False
            if bt_type == "macd_cross":
                return _safe_float(self.trb_macd_cross[0]) > 0
            if bt_type == "ma_cross":
                return _safe_float(self.trb_ma_cross[0]) > 0
            if bt_type == "breakout":
                return _safe_float(self.data.close[0]) > _safe_float(self.trb_entry_high[-1])
            if bt_type == "rsi_oversold":
                return _safe_float(self.trb_rsi[0]) < float(self.p.trb_rsi_oversold)
            if bt_type == "boll_lower":
                return _safe_float(self.data.close[0]) < _safe_float(self.trb_boll.bot[0])
            return False

        def _trans_sell_signal(self) -> bool:
            """过渡卖出信号判断"""
            st = str(self.p.trans_sell)
            if st == "empty":
                return False
            if st == "macd_dead_cross":
                return _safe_float(self.trs_macd_cross[0]) < 0
            if st == "atr_stop":
                if self.peak_price is not None and _safe_float(self.trs_atr[0]) > 0:
                    trail = float(self.peak_price) - float(self.p.trs_atr_mult) * _safe_float(self.trs_atr[0])
                    return _safe_float(self.data.close[0]) < trail
                return False
            if st == "profit_lock":
                if self.entry_price is not None and float(self.entry_price) > 0:
                    close = _safe_float(self.data.close[0])
                    profit_pct = (close - float(self.entry_price)) / float(self.entry_price) * 100.0
                    if profit_pct >= float(self.p.trs_profit_trigger):
                        if self.peak_price is not None:
                            drop_pct = (float(self.peak_price) - close) / float(self.peak_price) * 100.0
                            return drop_pct >= float(self.p.trs_trail_pct)
                return False
            if st == "rsi_overbought":
                return _safe_float(self.trs_rsi[0]) > float(self.p.trs_rsi_overbought)
            if st == "boll_upper":
                return _safe_float(self.data.close[0]) > _safe_float(self.trs_boll.top[0])
            return False

        def _reset_state(self):
            """重置持仓状态"""
            self.entry_price = None
            self.peak_price = None
            self.stop_price = None

        def next(self) -> None:
            """主逻辑：行情判别 -> 信号匹配 -> 买卖执行"""
            close = _safe_float(self.data.close[0])
            market = self._detect_market()

            if self.position:
                self.peak_price = max(float(self.peak_price or close), close)

                # 通用ATR止损
                if bool(self.p.use_atr_stop) and self.entry_price is not None and _safe_float(self.stop_atr[0]) > 0:
                    candidate = close - float(self.p.atr_stop_mult) * _safe_float(self.stop_atr[0])
                    self.stop_price = max(float(self.stop_price or candidate), candidate)
                    if close < float(self.stop_price):
                        self.sell()
                        self._reset_state()
                        return

                # 行情对应的卖出信号
                if market == "trend" and self._trend_sell_signal():
                    self.sell()
                    self._reset_state()
                    return
                if market == "range" and self._range_sell_signal():
                    self.sell()
                    self._reset_state()
                    return
                if market == "neutral" and self._trans_sell_signal():
                    self.sell()
                    self._reset_state()
                    return
                return

            # 空仓时检查买入信号
            if market == "trend" and self._trend_buy_signal():
                self.buy()
                self.entry_price = close
                self.peak_price = close
                self.stop_price = None
            elif market == "range" and self._range_buy_signal():
                self.buy()
                self.entry_price = close
                self.peak_price = close
                self.stop_price = None
            elif market == "neutral" and self._trans_buy_signal():
                self.buy()
                self.entry_price = close
                self.peak_price = close
                self.stop_price = None

    return ComboStrategy
