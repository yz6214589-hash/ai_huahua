from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd


ChanBackend = Literal["chanpy", "self"]


@dataclass(frozen=True)
class ChanResult:
    df: pd.DataFrame
    backend: ChanBackend


def _find_chan_case_dir() -> str:
    start = os.path.dirname(os.path.abspath(__file__))
    cur = start
    for _ in range(10):
        candidate = os.path.join(cur, "week5", "课程代码-20260314", "CASE-缠论精华量化")
        if os.path.isdir(candidate):
            return candidate
        cur = os.path.dirname(cur)
    raise RuntimeError("chan_case_dir_not_found")


def _ensure_df_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"])
    out = out.sort_values("trade_date").reset_index(drop=True)
    return out


def _to_chan_input(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d = d.set_index(pd.to_datetime(d["trade_date"]))
    cols = ["open", "high", "low", "close", "volume"]
    for c in cols:
        if c not in d.columns:
            d[c] = 0.0
    out = d[cols].copy()
    out.index.name = "date"
    return out


def _apply_zs_to_dates(dates: pd.DatetimeIndex, zs_list: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    zg = np.full(len(dates), np.nan, dtype="float64")
    zd = np.full(len(dates), np.nan, dtype="float64")
    for zs in zs_list or []:
        sd = zs.get("start_date")
        ed = zs.get("end_date")
        if sd is None or ed is None:
            continue
        try:
            sd_ts = pd.to_datetime(sd)
            ed_ts = pd.to_datetime(ed)
        except Exception:
            continue
        mask = (dates >= sd_ts) & (dates <= ed_ts)
        if not mask.any():
            continue
        try:
            zg_val = float(zs.get("ZG"))
            zd_val = float(zs.get("ZD"))
        except Exception:
            continue
        zg[mask] = zg_val
        zd[mask] = zd_val
    return zg, zd


def _apply_signals_to_dates(dates: pd.DatetimeIndex, signals: list[dict[str, Any]]) -> np.ndarray:
    sig = np.full(len(dates), np.nan, dtype="float64")
    date_to_idx = {d.date(): i for i, d in enumerate(dates)}
    for s in signals or []:
        dt = s.get("date") or s.get("bsp_date")
        if dt is None:
            continue
        try:
            d = pd.to_datetime(dt).date()
        except Exception:
            continue
        idx = date_to_idx.get(d)
        if idx is None:
            continue
        t = str(s.get("type") or s.get("bsp_type") or "")
        is_buy = s.get("bsp_is_buy")
        if t == "third_buy":
            sig[idx] = 3.0
        elif t == "third_sell":
            sig[idx] = -3.0
        else:
            tokens = [x.strip() for x in t.split(",") if x.strip()]
            buy_tokens = {"3", "3a", "3b", "2,3b"}
            if bool(is_buy) and any(tok in buy_tokens for tok in tokens):
                sig[idx] = 3.0
            if (is_buy is False) and any(tok in {"3_sell"} for tok in tokens):
                sig[idx] = -3.0
    return sig


def add_chan_fields(
    df: pd.DataFrame,
    backend: ChanBackend,
    symbol: str,
) -> ChanResult:
    base = _ensure_df_index(df)
    if base.empty:
        out = base.copy()
        out["chan_signal"] = np.nan
        out["chan_zg"] = np.nan
        out["chan_zd"] = np.nan
        return ChanResult(df=out, backend=backend)

    case_dir = _find_chan_case_dir()
    if case_dir not in sys.path:
        sys.path.insert(0, case_dir)

    dates = pd.to_datetime(base["trade_date"])
    chan_input = _to_chan_input(base)

    if backend == "chanpy":
        from chanpy_wrapper import run_chan  # type: ignore

        cp = run_chan(chan_input, symbol=symbol)
        zs_list = list(cp.get("zs_list") or [])
        bsp_list = list(cp.get("bsp_list") or [])
        zg, zd = _apply_zs_to_dates(dates, zs_list)
        sig = _apply_signals_to_dates(dates, bsp_list)
    elif backend == "self":
        from chan_analyzer import ChanAnalyzer  # type: ignore

        analyzer = ChanAnalyzer(chan_input)
        analyzer.analyze()
        zs_list = list(getattr(analyzer, "zhongshu_list", []) or [])
        signals = list(getattr(analyzer, "signals", []) or [])
        zg, zd = _apply_zs_to_dates(dates, zs_list)
        sig = _apply_signals_to_dates(dates, signals)
    else:
        raise ValueError("unknown_chan_backend")

    out = base.copy()
    out["chan_signal"] = sig
    out["chan_zg"] = zg
    out["chan_zd"] = zd
    return ChanResult(df=out, backend=backend)

