from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


ChanBackend = Literal["none"]


@dataclass(frozen=True)
class ChanResult:
    df: pd.DataFrame
    backend: str


def add_chan_fields(df: pd.DataFrame, backend: str = "none", symbol: str = "") -> ChanResult:
    """添加缠论字段到 DataFrame，降级实现直接返回 NaN。"""
    base = df.copy()
    if "trade_date" in base.columns:
        base["trade_date"] = pd.to_datetime(base["trade_date"])
        base = base.sort_values("trade_date").reset_index(drop=True)
    out = base.copy()
    out["chan_signal"] = np.nan
    out["chan_zg"] = np.nan
    out["chan_zd"] = np.nan
    return ChanResult(df=out, backend="none")
