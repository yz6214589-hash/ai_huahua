"""
数据状态查询API模块
提供数据更新时间的查询功能
"""

from __future__ import annotations

import pymysql
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
        # 使用直接连接加长超时，避免大表 COUNT DISTINCT 超时
        conn = pymysql.connect(
            host=cfg.host, port=cfg.port, user=cfg.user,
            password=cfg.password, database=cfg.database,
            charset="utf8mb4", autocommit=True,
            connect_timeout=5, read_timeout=30, write_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
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


def _get_table_stats(table: str) -> dict[str, Any]:
    """
    获取表的统计信息：最新日期、股票数量、数据条数

    统计标准:
      - 行情(stock_daily): 全市场有行情记录的去重股票总数
      - 财务(stock_financial): 全市场有财报数据的去重股票总数
      - 数据条数: 表内总记录数

    Args:
        table: 表名（必须在 ALLOWED_TABLES 白名单中）

    Returns:
        dict: 包含 latest_date、stock_count、data_count 的字典
    """
    result = {"latest_date": None, "stock_count": 0, "data_count": 0}
    try:
        if table not in ALLOWED_TABLES:
            return result

        date_column = ALLOWED_TABLES[table]
        if not _is_valid_identifier(table) or not _is_valid_identifier(date_column):
            return result

        cfg = load_mysql_config()
        conn = pymysql.connect(
            host=cfg.host, port=cfg.port, user=cfg.user,
            password=cfg.password, database=cfg.database,
            charset="utf8mb4", autocommit=True,
            connect_timeout=5, read_timeout=60, write_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            rows = query_dict(conn, f"SELECT MAX({date_column}) as latest FROM {table}", ())
            if rows and rows[0].get("latest"):
                latest = rows[0]["latest"]
                if isinstance(latest, datetime):
                    result["latest_date"] = latest.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    result["latest_date"] = str(latest)

            # 全表去重统计：行情统计所有有行情记录的股票，财务统计所有有财报的股票
            count_rows = query_dict(conn,
                f"SELECT COUNT(DISTINCT stock_code) as stock_count, COUNT(*) as data_count FROM {table}", ())
            if count_rows:
                result["stock_count"] = count_rows[0].get("stock_count") or 0
                result["data_count"] = count_rows[0].get("data_count") or 0
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"查询表 {table} 统计信息失败: {e}")

    return result


@router.get("/data/status")
def data_status() -> dict[str, Any]:
    """
    获取数据更新状态

    返回行情数据、财务数据和指数数据的最新更新时间、股票数量、数据条数

    Returns:
        dict: 包含stock_daily、stock_financial、timestamp的对象
    """
    market_stats = _get_table_stats("trade_stock_daily")
    financial_stats = _get_table_stats("trade_stock_financial")

    return {
        "stock_daily": {
            "latest_date": market_stats["latest_date"],
            "stock_count": market_stats["stock_count"],
            "data_count": market_stats["data_count"],
        },
        "stock_financial": {
            "latest_date": financial_stats["latest_date"],
            "stock_count": financial_stats["stock_count"],
            "data_count": financial_stats["data_count"],
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
