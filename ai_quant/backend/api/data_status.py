"""
数据状态查询API模块
提供数据更新时间的查询功能
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from core.db import connect, load_mysql_config, query_dict
from infra.storage.logging_service import get_logger

logger = get_logger("data")

router = APIRouter(prefix="/api/v1", tags=["data"])


def _get_latest_update_time(table: str, date_column: str) -> str | None:
    """
    获取表中最新记录的更新时间

    Args:
        table: 表名
        date_column: 日期列名

    Returns:
        str | None: 最新更新时间，格式为YYYY-MM-DD HH:MM:SS
    """
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            sql = f"SELECT MAX({date_column}) as latest FROM {table}"
            result = query_dict(conn, sql, ())
            if result and len(result) > 0:
                latest = result[0].get("latest")
                if latest:
                    if isinstance(latest, datetime):
                        return latest.strftime("%Y-%m-%d %H:%M:%S")
                    return str(latest)
            return None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"查询表 {table} 更新时间失败: {e}")
        return None


@router.get("/data/status")
def data_status() -> dict[str, Any]:
    """
    获取数据更新状态

    返回行情数据和财务数据的最新更新时间

    Returns:
        dict: 包含market和financial的更新时间
    """
    market_update = _get_latest_update_time("trade_stock_daily", "trade_date")
    financial_update = _get_latest_update_time("trade_stock_financial", "report_date")

    return {
        "market": market_update,
        "financial": financial_update,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
