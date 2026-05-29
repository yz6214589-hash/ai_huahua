from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from core.strategy.chan_analyzer import analyze_chan


ChanBackend = Literal["self"]


@dataclass(frozen=True)
class ChanResult:
    df: pd.DataFrame
    backend: str


def add_chan_fields(df: pd.DataFrame, backend: str = "self", symbol: str = "") -> ChanResult:
    base = df.copy()
    if "trade_date" in base.columns:
        base["trade_date"] = pd.to_datetime(base["trade_date"])
        base = base.sort_values("trade_date").reset_index(drop=True)

    try:
        chan_df = analyze_chan(base)
        if chan_df is not None and "chan_signal" in chan_df.columns:
            out = base.copy()
            out["chan_signal"] = chan_df["chan_signal"].values if len(chan_df) == len(base) else np.nan
            out["chan_zg"] = chan_df["chan_zg"].values if len(chan_df) == len(base) else np.nan
            out["chan_zd"] = chan_df["chan_zd"].values if len(chan_df) == len(base) else np.nan
            return ChanResult(df=out, backend="self")
    except Exception:
        pass

    out = base.copy()
    out["chan_signal"] = np.nan
    out["chan_zg"] = np.nan
    out["chan_zd"] = np.nan
    return ChanResult(df=out, backend="fallback")
