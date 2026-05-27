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


# 允许查询的表和字段白名单
ALLOWED_TABLES = {
    "trade_stock_daily": "trade_date",
    "trade_stock_financial": "report_date",
    "trade_index_daily": "trade_date",
}


def _is_valid_identifier(name: str) -> bool:
    """
    验证是否为有效的SQL标识符（字段名或表名）

    Args:
        name: 待验证的标识符名称

    Returns:
        bool: 有效返回True，否则返回False
    """
    if not name or not isinstance(name, str):
        return False
    # 只允许字母、数字、下划线，且必须以字母开头
    import re
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


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
        # 验证表名和字段名是否在白名单中
        if table not in ALLOWED_TABLES:
            logger.warning(f"不允许查询的表: {table}")
            return None

        expected_column = ALLOWED_TABLES[table]
        if date_column != expected_column:
            logger.warning(f"表 {table} 不允许查询字段 {date_column}，应为 {expected_column}")
            return None

        # 二次验证标识符格式
        if not _is_valid_identifier(table) or not _is_valid_identifier(date_column):
            logger.error(f"无效的SQL标识符: table={table}, date_column={date_column}")
            return None

        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            # 虽然table和date_column经过白名单验证，但仍使用参数化查询
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
        logger.error(f"查询表 {table} 更新时间失败: {e}")
        return None


@router.get("/data/status")
def data_status() -> dict[str, Any]:
    """
    获取数据更新状态

    返回行情数据、财务数据和指数数据的最新更新时间

    Returns:
        dict: 包含market、financial和index的更新时间
    """
    market_update = _get_latest_update_time("trade_stock_daily", "trade_date")
    financial_update = _get_latest_update_time("trade_stock_financial", "report_date")
    index_update = _get_latest_update_time("trade_index_daily", "trade_date")

    return {
        "market": market_update,
        "financial": financial_update,
        "index": index_update,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@router.get("/data/index-status")
def index_data_status() -> dict[str, Any]:
    """
    获取指数数据详细状态

    返回各指数的数据条数、时间范围和最新采集时间

    Returns:
        dict: 包含各指数数据状态详情
    """
    from core.data.index_data import INDEX_META

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            indices: list[dict[str, Any]] = []
            for code, name in INDEX_META.items():
                rows = query_dict(
                    conn,
                    """
                    SELECT COUNT(*) AS total_days,
                           MIN(trade_date) AS min_date,
                           MAX(trade_date) AS max_date,
                           MAX(collected_at) AS last_collected
                    FROM trade_index_daily
                    WHERE index_code = %s
                    """,
                    (code,),
                )
                if rows and rows[0]["total_days"] > 0:
                    row = rows[0]
                    indices.append({
                        "code": code,
                        "name": name,
                        "total_days": row["total_days"],
                        "min_date": str(row["min_date"]) if row["min_date"] else None,
                        "max_date": str(row["max_date"]) if row["max_date"] else None,
                        "last_collected": str(row["last_collected"]) if row["last_collected"] else None,
                    })
                else:
                    indices.append({
                        "code": code,
                        "name": name,
                        "total_days": 0,
                        "min_date": None,
                        "max_date": None,
                        "last_collected": None,
                    })

            return {
                "ok": True,
                "total_indices": len(indices),
                "indices": indices,
                "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        finally:
            conn.close()
    except Exception as e:
        return {"ok": False, "error": str(e)}
