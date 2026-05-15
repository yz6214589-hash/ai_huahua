"""
Zoe 服务模块 - 技术分析与信号生成服务

本模块提供以下核心功能：
- 技术信号生成：基于股票历史价格数据生成技术分析信号
- 样本股票查询：获取系统中的股票代码列表
- 数据库环境管理：配置数据库连接参数

该服务主要依赖 tech_signals 模块生成技术指标信号，
包括但不限于移动平均线、MACD、RSI等常用技术指标。
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from db import connect, load_mysql_config, query_dict
from services.zoe.tech_signals import generate_signals


def _sync_db_env() -> None:
    """
    同步数据库环境变量
    
    从 WUCAI_SQL_* 环境变量读取数据库配置，
    设置到 DB_* 环境变量供 db 模块使用。
    如果环境变量未设置，则使用默认值。
    """
    os.environ.setdefault("DB_HOST", os.getenv("WUCAI_SQL_HOST", "127.0.0.1"))
    os.environ.setdefault("DB_PORT", os.getenv("WUCAI_SQL_PORT", "3306"))
    os.environ.setdefault("DB_USER", os.getenv("WUCAI_SQL_USERNAME", "root"))
    os.environ.setdefault("DB_PASSWORD", os.getenv("WUCAI_SQL_PASSWORD", ""))
    os.environ.setdefault("DB_NAME", os.getenv("WUCAI_SQL_DB", "huahua_trade"))


def get_status() -> dict[str, Any]:
    """
    获取 Zoe 服务状态信息
    
    Returns:
        dict[str, Any]: 服务状态，包括数据源名称、可用功能等
    """
    return {
        "source": "zoe",
        "status": "ready",
        "features": ["signals", "factors", "backtest"],
        "talib": False,
        "talib_backend": None,
        "mode": "embedded",
    }


def get_sample_codes(limit: int) -> dict[str, Any]:
    """
    获取样本股票代码列表
    
    从数据库获取股票代码列表，按代码排序。
    
    Args:
        limit: 返回数量上限（最大500）
    
    Returns:
        dict[str, Any]: 包含codes（股票代码列表）的字典
    """
    n = max(1, min(limit, 500))
    _sync_db_env()
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return {"codes": []}
    try:
        rows = query_dict(
            conn,
            "SELECT stock_code FROM trade_stock_master ORDER BY stock_code LIMIT %s",
            (n,),
        )
        return {"codes": [str(r.get("stock_code") or "") for r in rows if str(r.get("stock_code") or "").strip()]}
    except Exception:
        return {"codes": []}
    finally:
        conn.close()


def get_signals(stock_code: str, start: str, end: str) -> dict[str, Any]:
    """
    获取股票的技术分析信号
    
    根据指定时间范围内的历史价格数据，
    调用技术信号生成模块计算各种技术指标信号。
    
    Args:
        stock_code: 股票代码
        start: 开始日期（YYYY-MM-DD格式）
        end: 结束日期（YYYY-MM-DD格式）
    
    Returns:
        dict[str, Any]: 包含stock_code和signals（信号列表）的字典
    """
    _sync_db_env()
    # 解析日期参数
    try:
        start_d = datetime.strptime(str(start).strip(), "%Y-%m-%d").date()
        end_d = datetime.strptime(str(end).strip(), "%Y-%m-%d").date()
        if not isinstance(start_d, date) or not isinstance(end_d, date):
            raise ValueError("invalid date")
    except Exception:
        return {"stock_code": stock_code, "signals": []}

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return {"stock_code": stock_code, "signals": []}
    try:
        # 查询指定时间范围内的收盘价数据
        rows = query_dict(
            conn,
            """
            SELECT trade_date, close_price
            FROM trade_stock_daily
            WHERE stock_code=%s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (stock_code, start_d, end_d),
        )
        # 提取日期和收盘价
        trade_dates: list[str] = []
        closes: list[float] = []
        for r in rows:
            td = r.get("trade_date")
            try:
                close_v = float(r.get("close_price"))
            except Exception:
                continue
            # 跳过NaN值
            if close_v != close_v:
                continue
            trade_dates.append(td.isoformat() if hasattr(td, "isoformat") else str(td or ""))
            closes.append(close_v)
        # 需要至少2个数据点才能生成信号
        if len(closes) < 2:
            return {"stock_code": stock_code, "signals": []}
        # 生成技术信号
        sigs = generate_signals(trade_dates=trade_dates, closes=closes)
        return {"stock_code": stock_code, "signals": sigs}
    except Exception:
        return {"stock_code": stock_code, "signals": []}
    finally:
        conn.close()
