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
    start_midx: int = 0
    end_midx: int = 0


@dataclass
class Zhongshu:
    zg: float
    zd: float
    start_idx: int
    end_idx: int
    strokes: list[int]
    start_midx: int = 0
    end_midx: int = 0


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
            result.append(f)
    return result


def _find_strokes(
    fractals: list[Fractal],
    min_stroke_pct: float = 0.008,
    min_gap: int = 4,
    merged_klines: list[KLine] | None = None,
) -> list[Stroke]:
    idx_to_pos: dict[int, int] = {}
    if merged_klines is not None:
        for pos, k in enumerate(merged_klines):
            idx_to_pos[k.idx] = pos

    if min_gap > 0 and merged_klines is not None:
        confirmed: list[Fractal] = [fractals[0]]
        for f in fractals[1:]:
            last = confirmed[-1]
            if f.kind == last.kind:
                if (f.kind == "top" and f.price > last.price) or \
                   (f.kind == "bottom" and f.price < last.price):
                    confirmed[-1] = f
            else:
                pos_last = idx_to_pos.get(last.idx)
                pos_f = idx_to_pos.get(f.idx)
                if pos_last is not None and pos_f is not None and \
                   pos_f - pos_last >= min_gap:
                    confirmed.append(f)

        strokes = []
        for i in range(1, len(confirmed)):
            f0 = confirmed[i - 1]
            f1 = confirmed[i]
            if f0.kind == f1.kind:
                continue
            price_move = abs(f1.price - f0.price) / max(f0.price, f1.price)
            if price_move < min_stroke_pct:
                continue
            direction = "up" if f1.price > f0.price else "down"
            midx0 = idx_to_pos.get(f0.idx, 0)
            midx1 = idx_to_pos.get(f1.idx, 0)
            strokes.append(
                Stroke(
                    start_idx=f0.idx, end_idx=f1.idx,
                    start_price=f0.price, end_price=f1.price,
                    direction=direction,
                    start_midx=midx0, end_midx=midx1,
                )
            )
        return strokes

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
        midx0 = idx_to_pos.get(f0.idx, 0) if merged_klines is not None else 0
        midx1 = idx_to_pos.get(f1.idx, 0) if merged_klines is not None else 0
        strokes.append(
            Stroke(
                start_idx=f0.idx, end_idx=f1.idx,
                start_price=f0.price, end_price=f1.price,
                direction=direction,
                start_midx=midx0, end_midx=midx1,
            )
        )
    return strokes


def _find_zhongshu(
    strokes: list[Stroke],
    klines_map: dict[int, KLine],
    min_bi: int = 3,
    max_extend: int = 4,
) -> list[Zhongshu]:
    if len(strokes) < min_bi:
        return []
    results = []
    i = 0
    while i <= len(strokes) - min_bi:
        group = strokes[i:i + min_bi]
        highs = [max(s.start_price, s.end_price) for s in group]
        lows = [min(s.start_price, s.end_price) for s in group]
        zg = min(highs)
        zd = max(lows)
        if zg > zd:
            end = i + min_bi
            extend_count = 0
            while end < len(strokes) and extend_count < max_extend:
                nb = strokes[end]
                nh = max(nb.start_price, nb.end_price)
                nl = min(nb.start_price, nb.end_price)
                if nh > zd and nl < zg:
                    end += 1
                    extend_count += 1
                else:
                    break
            results.append(
                Zhongshu(
                    zg=zg, zd=zd,
                    start_idx=group[0].start_idx,
                    end_idx=strokes[end - 1].end_idx,
                    strokes=list(range(i, end)),
                    start_midx=group[0].start_midx,
                    end_midx=strokes[end - 1].end_midx,
                )
            )
            i = end
        else:
            i += 1
    return results


def _generate_signals(
    klines: list[KLine],
    fractals: list[Fractal],
    zhongshus: list[Zhongshu],
    strokes: list[Stroke] | None = None,
) -> pd.DataFrame:
    n = len(klines)
    signals = pd.Series(np.zeros(n, dtype=float), index=range(n))
    zgs = pd.Series(np.full(n, np.nan), index=range(n))
    zds = pd.Series(np.full(n, np.nan), index=range(n))

    for zs in zhongshus:
        for i in range(zs.start_idx, min(zs.end_idx + 1, n)):
            zgs.iloc[i] = zs.zg
            zds.iloc[i] = zs.zd

    if strokes:
        used_3buy = set()
        used_3sell = set()

        for idx, zs in enumerate(zhongshus):
            zg = zs.zg
            zd = zs.zd

            is_last = (idx == len(zhongshus) - 1)
            limit = n if is_last else min(zhongshus[idx + 1].start_idx, n)
            for i in range(zs.end_idx + 1, limit):
                if pd.isna(zgs.iloc[i]):
                    zgs.iloc[i] = zg
                    zds.iloc[i] = zd
                if klines[i].close > zg or klines[i].close < zd:
                    break

            post_strokes = [s for s in strokes if s.start_midx >= zs.end_midx]

            state = 'WAIT_BREAKOUT'
            for s in post_strokes:
                if state == 'WAIT_BREAKOUT':
                    if s.direction == 'up' and s.end_price > zg:
                        state = 'WAIT_PULLBACK'
                elif state == 'WAIT_PULLBACK':
                    if s.direction == 'down':
                        if s.end_price > zg and s.end_idx not in used_3buy:
                            signals.iloc[s.end_idx] = 3.0
                            used_3buy.add(s.end_idx)
                            if pd.isna(zgs.iloc[s.end_idx]):
                                zgs.iloc[s.end_idx] = zg
                                zds.iloc[s.end_idx] = zd
                        break

            state = 'WAIT_BREAKDOWN'
            for s in post_strokes:
                if state == 'WAIT_BREAKDOWN':
                    if s.direction == 'down' and s.end_price < zd:
                        state = 'WAIT_BOUNCE'
                elif state == 'WAIT_BOUNCE':
                    if s.direction == 'up':
                        if s.end_price < zd and s.end_idx not in used_3sell:
                            signals.iloc[s.end_idx] = -3.0
                            used_3sell.add(s.end_idx)
                            if pd.isna(zgs.iloc[s.end_idx]):
                                zgs.iloc[s.end_idx] = zg
                                zds.iloc[s.end_idx] = zd
                        break
    else:
        for idx, zs in enumerate(zhongshus):
            start = min(zs.end_idx + 1, n - 1)
            is_last = (idx == len(zhongshus) - 1)
            limit = n if is_last else min(zhongshus[idx + 1].start_idx, n)
            for i in range(start, limit):
                k = klines[i]
                if pd.isna(zgs.iloc[i]):
                    zgs.iloc[i] = zs.zg
                    zds.iloc[i] = zs.zd
                if k.close > zs.zg or k.close < zs.zd:
                    break
            else:
                continue

            for i in range(start, limit):
                k = klines[i]
                if k.low < zs.zd:
                    continue
                if k.close > zs.zg:
                    signals.iloc[i] = 3.0
                    break

            for i in range(start, limit):
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

    strokes = _find_strokes(fractals, min_gap=4, merged_klines=cleaned)

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

    signal_df = _generate_signals(klines, fractals, zhongshus, strokes)

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
