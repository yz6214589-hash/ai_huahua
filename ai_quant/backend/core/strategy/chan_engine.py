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
