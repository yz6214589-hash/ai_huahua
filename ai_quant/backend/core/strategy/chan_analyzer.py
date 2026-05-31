from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass
class KLine:
    high: float
    low: float
    open: float
    close: float
    idx: int


@dataclass
class Fractal:
    kind: str  # "top" | "bottom"
    idx: int
    price: float
    strength: int = 0


@dataclass
class Stroke:
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    direction: str  # "up" | "down"


@dataclass
class Zhongshu:
    zg: float
    zd: float
    start_idx: int
    end_idx: int
    strokes: list[int]


def _merge_inclusive(klines: list[KLine]) -> list[KLine]:
    if not klines:
        return []
    result = [klines[0]]
    direction = None  # "up" | "down"

    for k in klines[1:]:
        prev = result[-1]

        if k.high <= prev.high and k.low >= prev.low:
            if direction == "up":
                merged = KLine(
                    high=prev.high, low=max(prev.low, k.low),
                    open=prev.open, close=prev.close if abs(prev.close - prev.open) > abs(k.close - k.open) else k.close,
                    idx=prev.idx,
                )
            elif direction == "down":
                merged = KLine(
                    high=min(prev.high, k.high), low=prev.low,
                    open=prev.open, close=prev.close if abs(prev.close - prev.open) > abs(k.close - k.open) else k.close,
                    idx=prev.idx,
                )
            else:
                merged = KLine(
                    high=prev.high, low=min(prev.low, k.low),
                    open=prev.open, close=prev.close,
                    idx=prev.idx,
                )
            result[-1] = merged
        elif k.high >= prev.high and k.low <= prev.low:
            if direction == "up":
                merged = KLine(
                    high=max(prev.high, k.high), low=prev.low,
                    open=prev.open, close=k.close if abs(k.close - k.open) > abs(prev.close - prev.open) else prev.close,
                    idx=prev.idx,
                )
            elif direction == "down":
                merged = KLine(
                    high=prev.high, low=min(prev.low, k.low),
                    open=k.open, close=k.close if abs(k.close - k.open) > abs(prev.close - prev.open) else prev.close,
                    idx=prev.idx,
                )
            else:
                merged = KLine(
                    high=max(prev.high, k.high), low=min(prev.low, k.low),
                    open=prev.open, close=prev.close,
                    idx=prev.idx,
                )
            result[-1] = merged
        else:
            if k.high > prev.high and k.low > prev.low:
                direction = "up"
            elif k.high < prev.high and k.low < prev.low:
                direction = "down"
            result.append(k)

    return result


def _find_fractals(klines: list[KLine]) -> list[Fractal]:
    result = []
    for i in range(1, len(klines) - 1):
        left = klines[i - 1]
        mid = klines[i]
        right = klines[i + 1]
        if mid.high > left.high and mid.high >= right.high:
            strength = 1
            if mid.high > left.high * 1.005 and mid.high > right.high * 1.005:
                strength = 2
            result.append(Fractal("top", mid.idx, mid.high, strength))
        if mid.low < left.low and mid.low <= right.low:
            strength = 1
            if mid.low < left.low * 0.995 and mid.low < right.low * 0.995:
                strength = 2
            result.append(Fractal("bottom", mid.idx, mid.low, strength))
    return result


def _filter_fractals(fractals: list[Fractal]) -> list[Fractal]:
    if not fractals:
        return []
    result = [fractals[0]]
    for f in fractals[1:]:
        prev = result[-1]
        if f.kind == prev.kind:
            if (f.kind == "top" and f.price > prev.price) or \
               (f.kind == "bottom" and f.price < prev.price):
                result[-1] = f
        else:
            if f.kind == "bottom":
                if f.price < prev.price:
                    result.append(f)
            else:
                if f.price > prev.price:
                    result.append(f)
    return result


def _find_strokes(fractals: list[Fractal], min_stroke_pct: float = 0.008) -> list[Stroke]:
    strokes = []
    for i in range(len(fractals) - 1):
        f0 = fractals[i]
        f1 = fractals[i + 1]
        if f0.kind == f1.kind:
            continue
        price_move = abs(f1.price - f0.price) / max(f0.price, f1.price)
        if price_move < min_stroke_pct:
            continue
        direction = "up" if f1.price > f0.price else "down"
        strokes.append(
            Stroke(
                start_idx=f0.idx, end_idx=f1.idx,
                start_price=f0.price, end_price=f1.price,
                direction=direction,
            )
        )
    return strokes


def _find_zhongshu(strokes: list[Stroke], klines_map: dict[int, KLine]) -> list[Zhongshu]:
    results = []
    for i in range(len(strokes) - 2):
        s1, s2, s3 = strokes[i], strokes[i + 1], strokes[i + 2]
        if s1.direction == s2.direction:
            continue
        if s2.direction == s3.direction:
            continue
        zg = min(s1.end_price if s1.direction == "up" else s1.start_price,
                 s2.start_price,
                 s3.end_price if s3.direction == "up" else s3.start_price)
        zd = max(s1.start_price if s1.direction == "up" else s1.end_price,
                 s2.end_price,
                 s3.start_price if s3.direction == "up" else s3.end_price)
        if zg > zd:
            results.append(
                Zhongshu(
                    zg=zg, zd=zd,
                    start_idx=s1.start_idx,
                    end_idx=s3.end_idx,
                    strokes=list(range(i, i + 3)),
                )
            )
    if not results:
        return results
    merged = [results[0]]
    for r in results[1:]:
        prev = merged[-1]
        if r.start_idx <= prev.end_idx + 1:
            merged[-1] = Zhongshu(
                zg=max(prev.zg, r.zg),
                zd=min(prev.zd, r.zd),
                start_idx=prev.start_idx,
                end_idx=max(prev.end_idx, r.end_idx),
                strokes=prev.strokes + r.strokes,
            )
        else:
            merged.append(r)
    return merged


def _generate_signals(
    klines: list[KLine],
    fractals: list[Fractal],
    zhongshus: list[Zhongshu],
) -> pd.DataFrame:
    n = len(klines)
    signals = pd.Series(np.zeros(n, dtype=float), index=range(n))
    zgs = pd.Series(np.full(n, np.nan), index=range(n))
    zds = pd.Series(np.full(n, np.nan), index=range(n))

    for zs in zhongshus:
        for i in range(zs.start_idx, min(zs.end_idx + 1, n)):
            zgs.iloc[i] = zs.zg
            zds.iloc[i] = zs.zd

    for zs in zhongshus:
        start = min(zs.end_idx + 1, n - 1)
        for i in range(start, n):
            k = klines[i]
            if zgs.iloc[i] > 0 and zds.iloc[i] > 0:
                zgs.iloc[i] = zs.zg
                zds.iloc[i] = zs.zd
            if k.close > zs.zg:
                break
        else:
            continue

        for i in range(start, n):
            k = klines[i]
            if k.low < zs.zd:
                continue
            if k.close > zs.zg:
                signals.iloc[i] = 3.0
                break

        for i in range(start, n):
            k = klines[i]
            if k.high < zs.zg:
                continue
            if k.close < zs.zd:
                signals.iloc[i] = -1.0
                break

    return pd.DataFrame({"chan_signal": signals, "chan_zg": zgs, "chan_zd": zds})


def analyze_chan(df: pd.DataFrame) -> pd.DataFrame:
    high_col = "high" if "high" in df.columns else df.columns[2]
    low_col = "low" if "low" in df.columns else df.columns[3]
    open_col = "open" if "open" in df.columns else df.columns[1]
    close_col = "close" if "close" in df.columns else df.columns[4]

    highs = df[high_col].values
    lows = df[low_col].values
    opens = df[open_col].values
    closes = df[close_col].values

    klines = []
    for i in range(len(df)):
        klines.append(
            KLine(
                high=float(highs[i]),
                low=float(lows[i]),
                open=float(opens[i]),
                close=float(closes[i]),
                idx=i,
            )
        )

    cleaned = _merge_inclusive(klines)
    fractals = _find_fractals(cleaned)
    fractals = _filter_fractals(fractals)

    if len(fractals) < 6:
        result = pd.DataFrame(index=df.index)
        result["chan_signal"] = np.nan
        result["chan_zg"] = np.nan
        result["chan_zd"] = np.nan
        result.attrs["_chan_vis_data"] = {"bi_list": [], "seg_list": [], "zs_list": []}
        return result

    strokes = _find_strokes(fractals)

    if len(strokes) < 6:
        result = pd.DataFrame(index=df.index)
        result["chan_signal"] = np.nan
        result["chan_zg"] = np.nan
        result["chan_zd"] = np.nan
        result.attrs["_chan_vis_data"] = {"bi_list": [], "seg_list": [], "zs_list": []}
        return result

    klines_map = {k.idx: k for k in klines}
    zhongshus = _find_zhongshu(strokes, klines_map)

    if not zhongshus:
        result = pd.DataFrame(index=df.index)
        result["chan_signal"] = np.nan
        result["chan_zg"] = np.nan
        result["chan_zd"] = np.nan
        result.attrs["_chan_vis_data"] = {"bi_list": [], "seg_list": [], "zs_list": []}
        return result

    signal_df = _generate_signals(klines, fractals, zhongshus)

    # 构建 idx -> 日期字符串 的映射，用于可视化数据
    date_col = "trade_date" if "trade_date" in df.columns else None
    idx_to_date: dict[int, str] = {}
    if date_col is not None:
        for i in range(len(df)):
            dt_val = df.iloc[i][date_col]
            idx_to_date[i] = str(pd.Timestamp(dt_val).date()) if pd.notna(dt_val) else ""

    # 构建可视化数据（笔和中枢）
    vis_data: dict[str, Any] = {"bi_list": [], "seg_list": [], "zs_list": []}

    for s in strokes:
        bi_item: dict[str, Any] = {
            "start_idx": s.start_idx,
            "end_idx": s.end_idx,
            "start_price": s.start_price,
            "end_price": s.end_price,
            "direction": s.direction,
        }
        # 添加日期字段（与 chanpy_adapter 输出格式对齐）
        if idx_to_date:
            bi_item["start_date"] = idx_to_date.get(s.start_idx, "")
            bi_item["end_date"] = idx_to_date.get(s.end_idx, "")
        vis_data["bi_list"].append(bi_item)

    for z in zhongshus:
        zs_item: dict[str, Any] = {
            "ZG": z.zg,
            "ZD": z.zd,
            "zg": z.zg,
            "zd": z.zd,
            "start_idx": z.start_idx,
            "end_idx": z.end_idx,
        }
        # 添加日期字段（与 chanpy_adapter 输出格式对齐）
        if idx_to_date:
            zs_item["start_date"] = idx_to_date.get(z.start_idx, "")
            zs_item["end_date"] = idx_to_date.get(z.end_idx, "")
        vis_data["zs_list"].append(zs_item)

    result = pd.DataFrame(index=df.index)
    result["chan_signal"] = signal_df["chan_signal"].values if len(signal_df) == len(df) else np.nan
    result["chan_zg"] = signal_df["chan_zg"].values if len(signal_df) == len(df) else np.nan
    result["chan_zd"] = signal_df["chan_zd"].values if len(signal_df) == len(df) else np.nan
    result.attrs["_chan_vis_data"] = vis_data
    return result
