# -*- coding: utf-8 -*-
"""
chan.py 开源库适配器

封装开源 chan.py 库的调用，将分析结果转换为统一的
chan_signal / chan_zg / chan_zd 格式，并提取可视化数据。

chan.py 库可能未安装，所有调用均做 try/except 降级处理。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any


def analyze_chanpy(df: pd.DataFrame, symbol: str = "stock") -> pd.DataFrame | None:
    """
    使用开源 chan.py 库进行缠论分析

    Args:
        df: 日线数据 DataFrame，需包含 open/high/low/close/volume 列
        symbol: 股票代码标识

    Returns:
        DataFrame 包含 chan_signal, chan_zg, chan_zd 列，
        以及 attrs 中的 _chan_vis_data 字典（笔/线/中枢可视化数据）。
        如果分析失败则返回 None。
    """
    try:
        import sys
        import os
        # chan.py 库路径（参考代码目录）
        chanpy_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..',
            '参考代码', '未命名文件夹', 'week5', '课程代码-20260314',
            'CASE-缠论精华量化', 'chan.py'
        ))
        if os.path.isdir(chanpy_path) and chanpy_path not in sys.path:
            sys.path.insert(0, chanpy_path)

        # chanpy_wrapper.py 所在目录也需要加入路径
        wrapper_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..',
            '参考代码', '未命名文件夹', 'week5', '课程代码-20260314',
            'CASE-缠论精华量化'
        ))
        if os.path.isdir(wrapper_path) and wrapper_path not in sys.path:
            sys.path.insert(0, wrapper_path)

        from chanpy_wrapper import run_chan

        # 准备数据（需要 DatetimeIndex）
        prep = df.copy()
        if "trade_date" in prep.columns:
            prep["trade_date"] = pd.to_datetime(prep["trade_date"])
            prep = prep.set_index("trade_date")

        chan_data = run_chan(prep, symbol=symbol)

        # 将 chan.py 结果转换为信号 DataFrame
        result_df = _chan_to_signal_df(prep, chan_data)

        # 重置索引以匹配原始 df
        result_df = result_df.reset_index()

        # 提取可视化数据
        vis_data = _extract_vis_data(chan_data)
        result_df.attrs["_chan_vis_data"] = vis_data

        return result_df

    except Exception as e:
        import logging
        logging.getLogger("chanpy_adapter").warning(f"chan.py analysis failed: {e}", exc_info=True)
        return None


def _chan_to_signal_df(df: pd.DataFrame, chan_data: dict) -> pd.DataFrame:
    """
    将 chan.py 的分析结果转换为包含 chan_signal / chan_zg / chan_zd 的 DataFrame

    信号定义：
        3.0  = 第三类买点（价格向上突破中枢 ZG 后确认）
        -1.0 = 向下跌破中枢 ZD
        -3.0 = 第三类卖点（价格向下跌破中枢 ZD 后确认）
        0.0  = 无信号

    Args:
        df: 原始 DataFrame（DatetimeIndex）
        chan_data: run_chan() 返回的字典

    Returns:
        包含 chan_signal, chan_zg, chan_zd 列的 DataFrame
    """
    n = len(df)
    signals = np.zeros(n, dtype=float)
    zgs = np.full(n, np.nan)
    zds = np.full(n, np.nan)

    # 从买卖点列表中提取信号
    bsp_list = chan_data.get("bsp_list", [])
    zs_list = chan_data.get("zs_list", [])

    # 填充中枢 ZG/ZD 数据
    for zs in zs_list:
        start_date = zs.get("start_date")
        end_date = zs.get("end_date")
        zg = zs.get("ZG", 0)
        zd = zs.get("ZD", 0)
        if zg <= 0 or zd <= 0:
            continue
        # 将中枢区间内的 ZG/ZD 填入对应日期
        for i in range(n):
            dt = df.index[i]
            if start_date is not None and end_date is not None:
                if start_date <= dt <= end_date:
                    zgs[i] = zg
                    zds[i] = zd

    # 从买卖点提取信号
    for bsp in bsp_list:
        bsp_date = bsp.get("bsp_date")
        is_buy = bsp.get("bsp_is_buy")
        bsp_type = bsp.get("bsp_type", "")

        if bsp_date is None:
            continue

        # 查找对应日期的索引
        for i in range(n):
            dt = df.index[i]
            if dt == bsp_date or (hasattr(dt, 'date') and hasattr(bsp_date, 'date') and dt.date() == bsp_date.date()):
                if is_buy and '3' in str(bsp_type):
                    signals[i] = 3.0
                elif not is_buy and '3' in str(bsp_type):
                    signals[i] = -3.0
                elif is_buy:
                    signals[i] = 1.0
                elif not is_buy:
                    signals[i] = -1.0
                break

    # 将中枢 ZG/ZD 延续到中枢结束后的位置（直到下一个中枢开始）
    if zs_list:
        for zs in zs_list:
            end_date = zs.get("end_date")
            zg = zs.get("ZG", 0)
            zd = zs.get("ZD", 0)
            if zg <= 0 or zd <= 0 or end_date is None:
                continue
            # 从中枢结束日期开始，延续 ZG/ZD 直到价格突破
            start_idx = None
            for i in range(n):
                dt = df.index[i]
                if dt > end_date or (hasattr(dt, 'date') and hasattr(end_date, 'date') and dt.date() > end_date.date()):
                    start_idx = i
                    break
            if start_idx is not None:
                for i in range(start_idx, n):
                    if not np.isnan(zgs[i]):
                        # 已经被下一个中枢覆盖
                        break
                    zgs[i] = zg
                    zds[i] = zd
                    # 价格突破中枢上沿或下沿时停止延续
                    close_val = float(df.iloc[i]["close"])
                    if close_val > zg:
                        break
                    if close_val < zd:
                        break

    result = pd.DataFrame(index=df.index)
    result["chan_signal"] = signals
    result["chan_zg"] = zgs
    result["chan_zd"] = zds
    return result


def _extract_vis_data(chan_data: dict) -> dict:
    """从 chan.py 结果中提取可视化数据"""
    vis: dict[str, Any] = {"bi_list": [], "seg_list": [], "zs_list": []}

    for bi in chan_data.get("bi_list", []):
        vis["bi_list"].append({
            "start_date": str(bi.get("start_raw_date", ""))[:10],
            "end_date": str(bi.get("end_raw_date", ""))[:10],
            "start_price": bi.get("start_price", 0),
            "end_price": bi.get("end_price", 0),
            "direction": bi.get("direction", "up"),
        })

    for seg in chan_data.get("seg_list", []):
        vis["seg_list"].append({
            "start_date": str(seg.get("start_date", ""))[:10],
            "end_date": str(seg.get("end_date", ""))[:10],
            "direction": seg.get("direction", "up"),
        })

    for zs in chan_data.get("zs_list", []):
        vis["zs_list"].append({
            "ZG": zs.get("ZG", 0),
            "ZD": zs.get("ZD", 0),
            "start_date": str(zs.get("start_date", ""))[:10],
            "end_date": str(zs.get("end_date", ""))[:10],
        })

    return vis
