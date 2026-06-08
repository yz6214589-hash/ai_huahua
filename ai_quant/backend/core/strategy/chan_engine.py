from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd


ChanBackend = Literal["self", "chanpy"]


@dataclass(frozen=True)
class ChanResult:
    df: pd.DataFrame
    backend: str
    chan_vis: dict | None = None


def add_chan_fields(df: pd.DataFrame, backend: str = "self", symbol: str = "") -> ChanResult:
    """
    为 DataFrame 添加缠论字段（chan_signal, chan_zg, chan_zd）

    Args:
        df: 日线数据 DataFrame
        backend: 缠论分析引擎，"self" 使用自研 ChanAnalyzer，"chanpy" 使用开源 chan.py
        symbol: 股票代码标识（chanpy 后端需要）

    Returns:
        ChanResult 包含处理后的 DataFrame、使用的后端名称和可视化数据
    """
    base = df.copy()
    if "trade_date" in base.columns:
        base["trade_date"] = pd.to_datetime(base["trade_date"])
        base = base.sort_values("trade_date").reset_index(drop=True)

    if backend == "chanpy":
        try:
            from core.strategy.chanpy_adapter import analyze_chanpy
            chan_df = analyze_chanpy(base, symbol=symbol)
            if chan_df is not None and "chan_signal" in chan_df.columns:
                out = base.copy()
                out["chan_signal"] = chan_df["chan_signal"].values if len(chan_df) == len(base) else np.nan
                out["chan_zg"] = chan_df["chan_zg"].values if len(chan_df) == len(base) else np.nan
                out["chan_zd"] = chan_df["chan_zd"].values if len(chan_df) == len(base) else np.nan
                # 保存缠论可视化数据
                chan_vis = chan_df.attrs.get("_chan_vis_data")
                return ChanResult(df=out, backend="chanpy", chan_vis=chan_vis)
        except Exception as e:
            import logging
            logging.getLogger("chan_engine").warning(f"chanpy backend failed: {e}", exc_info=True)

    # 默认使用自研
    try:
        from core.strategy.chan_analyzer import analyze_chan
        chan_df = analyze_chan(base)
        if chan_df is not None and "chan_signal" in chan_df.columns:
            out = base.copy()
            out["chan_signal"] = chan_df["chan_signal"].values if len(chan_df) == len(base) else np.nan
            out["chan_zg"] = chan_df["chan_zg"].values if len(chan_df) == len(base) else np.nan
            out["chan_zd"] = chan_df["chan_zd"].values if len(chan_df) == len(base) else np.nan
            # 从自研分析结果中获取可视化数据
            chan_vis = chan_df.attrs.get("_chan_vis_data")
            return ChanResult(df=out, backend="self", chan_vis=chan_vis)
    except Exception:
        pass

    out = base.copy()
    out["chan_signal"] = np.nan
    out["chan_zg"] = np.nan
    out["chan_zd"] = np.nan
    return ChanResult(df=out, backend="fallback", chan_vis=None)


def calc_weekly_trend(df: pd.DataFrame) -> pd.Series:
    """
    基于周线缠论分析（中枢方向判断）+ 均线辅助 计算每日趋势方向

    优先级:
      1. 周线中枢方向（>=2个中枢时可判断）
      2. 价格与中枢位置关系（仅有1个中枢时）
      3. 周线MA20方向（兜底判断）

    Args:
        df: 日线数据 DataFrame，需包含 trade_date/open/high/low/close/volume

    Returns:
        pd.Series, 索引为 trade_date, 值为趋势方向:
          1  = 上升趋势
          -1 = 下跌趋势
          0  = 震荡
    """
    base = df.copy()
    if "trade_date" in base.columns:
        base["trade_date"] = pd.to_datetime(base["trade_date"])
        base = base.sort_values("trade_date").reset_index(drop=True)

    weekly_df = base.set_index("trade_date").resample("W").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()

    if len(weekly_df) < 20:
        return pd.Series(0, index=base["trade_date"])

    from core.strategy.chan_analyzer import analyze_chan
    w_base = weekly_df.reset_index()
    w_base.columns = ["trade_date", "open", "high", "low", "close", "volume"]
    w_chan = analyze_chan(w_base)

    weekly_trend = pd.Series(0, index=weekly_df.index)

    if w_chan is not None:
        vis = w_chan.attrs.get("_chan_vis_data")
        if vis:
            zs_list = vis.get("zs_list", [])

            if len(zs_list) >= 2:
                for i in range(1, len(zs_list)):
                    curr = zs_list[i]
                    prev = zs_list[i - 1]
                    curr_zg = curr.get("zg", 0)
                    curr_zd = curr.get("zd", 0)
                    prev_zg = prev.get("zg", 0)
                    prev_zd = prev.get("zd", 0)

                    if curr_zg > prev_zg and curr_zd > prev_zd:
                        trend = 1
                    elif curr_zg < prev_zg and curr_zd < prev_zd:
                        trend = -1
                    else:
                        trend = 0

                    end_idx = curr.get("end_idx", 0)
                    if end_idx < len(weekly_df):
                        mask = weekly_trend.index >= weekly_df.index[end_idx]
                        weekly_trend.loc[mask] = trend

            if len(zs_list) >= 1:
                for zs in zs_list:
                    zs_zg = zs.get("zg", 0)
                    zs_zd = zs.get("zd", 0)
                    zs_start = zs.get("start_idx", 0)
                    for idx in range(zs_start, len(weekly_df)):
                        date = weekly_df.index[idx]
                        if weekly_trend.loc[date] != 0:
                            continue
                        close_val = weekly_df["close"].iloc[idx]
                        if close_val > zs_zg:
                            weekly_trend.loc[date] = 1
                        elif close_val < zs_zd:
                            weekly_trend.loc[date] = -1

            ma20 = weekly_df["close"].rolling(20).mean()
            for idx in range(20, len(weekly_df)):
                date = weekly_df.index[idx]
                if weekly_trend.loc[date] != 0:
                    continue
                if weekly_df["close"].iloc[idx] > ma20.iloc[idx]:
                    weekly_trend.loc[date] = 1
                elif weekly_df["close"].iloc[idx] < ma20.iloc[idx]:
                    weekly_trend.loc[date] = -1

    daily_trend = weekly_trend.reindex(base["trade_date"], method="ffill").fillna(0).astype(int)
    return daily_trend
