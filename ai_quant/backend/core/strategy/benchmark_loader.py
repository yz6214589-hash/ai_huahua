# -*- coding: utf-8 -*-
"""
基准数据加载模块
从数据库加载基准指数的日线数据，并计算基准净值序列
支持沪深300(000300.SH)、上证50(000016.SH)等指数代码
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.db import connect, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("benchmark_loader")


def load_benchmark_data(code: str, start: str, end: str) -> pd.DataFrame:
    """
    从数据库加载基准指数日线数据

    Args:
        code: 指数代码，如 000300.SH
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)

    Returns:
        包含 trade_date, close_price 列的 DataFrame
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception as e:
        logger.error("基准数据加载失败: 数据库连接异常", extra={"error": str(e)})
        return pd.DataFrame()
    try:
        rows = query_dict(
            conn,
            """
            SELECT trade_date, close_price
            FROM trade_stock_daily
            WHERE stock_code = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (code, start, end),
        )
        if not rows:
            logger.warning("基准数据为空", extra={"code": code, "start": start, "end": end})
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.dropna(subset=["close_price"])
        return df
    except Exception as e:
        logger.error("基准数据查询异常", extra={"code": code, "error": str(e)})
        return pd.DataFrame()
    finally:
        conn.close()


def calc_benchmark_nav(
    code: str,
    start: str,
    end: str,
    initial_cash: float = 100000.0,
) -> list[dict[str, Any]]:
    """
    计算基准净值序列
    基于指数的收盘价，按日计算净值变化

    Args:
        code: 指数代码，如 000300.SH
        start: 开始日期 (YYYY-MM-DD)
        end: 结束日期 (YYYY-MM-DD)
        initial_cash: 初始资金，默认100000

    Returns:
        基准净值列表 [{"date": "2023-01-03", "nav": 100000}, ...]
    """
    df = load_benchmark_data(code, start, end)
    if df.empty:
        return []

    df = df.sort_values("trade_date").reset_index(drop=True)
    if df.empty or "close_price" not in df.columns:
        return []

    # 用第一天的收盘价作为基准
    first_close = float(df["close_price"].iloc[0])
    if first_close <= 0:
        return []

    nav_log: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        nav = initial_cash * (float(row["close_price"]) / first_close)
        date_str = row["trade_date"].strftime("%Y-%m-%d") if pd.notna(row["trade_date"]) else ""
        nav_log.append({"date": date_str, "nav": round(nav, 2)})

    return nav_log
