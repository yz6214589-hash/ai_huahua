# -*- coding: utf-8 -*-
"""
chan.py 开源库适配器

封装开源 chan.py 库的调用，将分析结果转换为统一的
chan_signal / chan_zg / chan_zd 格式，并提取可视化数据。

与参考代码 chanpy_wrapper.chan_to_signal_df 逻辑保持一致：
- 使用 bsp_signal_map 映射买卖点信号
- 先填充中枢区间内的 ZG/ZD
- 在信号点也填充对应中枢的 ZG/ZD
- 最后使用 ffill() 做简单前向填充

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
        _base_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.abspath(os.path.join(_base_dir, '..', '..', '..'))
        _workspace = os.path.abspath(os.path.join(_project_root, '..'))
        _desktop = os.path.abspath(os.path.join(_workspace, '..'))

        chanpy_search_paths = [
            os.path.join(_desktop, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'chan.py'),
            os.path.join(_desktop, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'chan.py'),
            os.path.join(_workspace, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'chan.py'),
            os.path.join(_workspace, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'chan.py'),
            os.path.join(_project_root, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'chan.py'),
            os.path.join(_project_root, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'chan.py'),
            os.path.join(_project_root, '参考代码', '未命名文件夹', 'week5', '课程代码-20260314', 'CASE-缠论精华量化', 'chan.py'),
        ]
        chanpy_path = None
        for p in chanpy_search_paths:
            if os.path.isdir(p):
                chanpy_path = p
                break

        if chanpy_path and chanpy_path not in sys.path:
            sys.path.insert(0, chanpy_path)

        wrapper_search_paths = [
            os.path.join(_desktop, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_desktop, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_workspace, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_workspace, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_project_root, '参考代码', '笔记', '第五周 缠论及网格交易', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_project_root, '参考代码', 'ai_huahua-agents', 'lesson', 'week5', '课程代码-20260318', 'CASE-网格与多因子'),
            os.path.join(_project_root, '参考代码', '未命名文件夹', 'week5', '课程代码-20260314', 'CASE-缠论精华量化'),
        ]
        wrapper_path = None
        for p in wrapper_search_paths:
            if os.path.isdir(p):
                wrapper_path = p
                break

        if wrapper_path and wrapper_path not in sys.path:
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

    与参考代码 chanpy_wrapper.chan_to_signal_df 逻辑保持一致：
    - 使用 bsp_signal_map 映射买卖点信号
    - 先填充中枢区间内的 ZG/ZD
    - 在信号点也填充对应中枢的 ZG/ZD
    - 最后使用 ffill() 做简单前向填充

    信号定义：
        3.0  = 第三类买点
        -3.0 = 第三类卖点
        2.0  = 第二类买点
        1.0  = 第一类买点
        -1.0 = 第一类卖点
        0.0  = 无信号

    Args:
        df: 原始 DataFrame（DatetimeIndex）
        chan_data: run_chan() 返回的字典

    Returns:
        包含 chan_signal, chan_zg, chan_zd 列的 DataFrame
    """
    result = pd.DataFrame(index=df.index)
    result["chan_signal"] = 0.0
    result["chan_zg"] = np.nan
    result["chan_zd"] = np.nan

    bsp_list = chan_data.get("bsp_list", [])
    zs_list = chan_data.get("zs_list", [])

    # 买卖点信号映射表（与参考代码 chanpy_wrapper 一致）
    bsp_signal_map = {
        "1": (1, True), "2": (2, True), "2s": (2, True), "3": (3, True),
        "1s": (-1, False), "2_sell": (-2, False), "3_sell": (-3, False),
        "3a": (3, True),
    }

    # 映射买卖点信号
    for bi in bsp_list:
        bsp_type = bi.get("bsp_type")
        bsp_date = bi.get("bsp_date")
        if bsp_date is None or bsp_type is None:
            continue
        if bsp_date not in result.index:
            continue

        # bsp_type 可能是逗号分隔的多个类型，取优先级最高的
        best_signal = 0
        for t in bsp_type.split(","):
            t = t.strip()
            if t in bsp_signal_map:
                sig_val, _is_buy = bsp_signal_map[t]
                if abs(sig_val) > abs(best_signal):
                    best_signal = sig_val

        if best_signal != 0:
            result.loc[bsp_date, "chan_signal"] = best_signal

    # 填充中枢区间内的 ZG/ZD
    for zs in zs_list:
        start_date = zs.get("start_date")
        end_date = zs.get("end_date")
        zg = zs.get("ZG", 0)
        zd = zs.get("ZD", 0)
        if start_date is None or end_date is None:
            continue
        mask = (result.index >= start_date) & (result.index <= end_date)
        result.loc[mask, "chan_zg"] = result.loc[mask, "chan_zg"].fillna(zg)
        result.loc[mask, "chan_zd"] = result.loc[mask, "chan_zd"].fillna(zd)

    # 在信号点也填充对应中枢的 ZG/ZD
    for bi in bsp_list:
        bsp_date = bi.get("bsp_date")
        if bsp_date is None or bsp_date not in result.index:
            continue
        # 找到该信号对应的中枢（取最近的已结束中枢）
        for zs in reversed(zs_list):
            zs_end = zs.get("end_date")
            if zs_end and bsp_date >= zs_end:
                if pd.isna(result.loc[bsp_date, "chan_zg"]):
                    result.loc[bsp_date, "chan_zg"] = zs.get("ZG", 0)
                if pd.isna(result.loc[bsp_date, "chan_zd"]):
                    result.loc[bsp_date, "chan_zd"] = zs.get("ZD", 0)
                break

    # 使用 ffill() 做简单前向填充（与参考代码一致）
    result["chan_zg"] = result["chan_zg"].ffill()
    result["chan_zd"] = result["chan_zd"].ffill()

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
            "start_price": seg.get("start_price", 0),
            "end_price": seg.get("end_price", 0),
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
