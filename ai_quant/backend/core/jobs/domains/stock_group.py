"""
股票分组管理模块
提供自选股分组（trade_stock_group / trade_stock_group_item）的建表
以及按 scope_type 获取股票列表的工具函数，供 stock_news、report_consensus 等任务使用。
"""

from __future__ import annotations

from typing import Any

from core.data import get_watchlist
from core.db import connect, execute, query_dict, load_mysql_config


_CREATE_GROUP_SQL = """
CREATE TABLE IF NOT EXISTS trade_stock_group (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL COMMENT '组名称',
  description VARCHAR(500) DEFAULT '' COMMENT '描述',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_CREATE_GROUP_ITEM_SQL = """
CREATE TABLE IF NOT EXISTS trade_stock_group_item (
  id INT AUTO_INCREMENT PRIMARY KEY,
  group_id INT NOT NULL COMMENT '关联组ID',
  stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
  stock_name VARCHAR(100) DEFAULT '' COMMENT '股票名称',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (group_id) REFERENCES trade_stock_group(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def ensure_stock_group_tables() -> None:
    """
    确保股票分组相关表已创建。
    首次使用前调用此函数完成建表。
    """
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        execute(conn, _CREATE_GROUP_SQL)
        execute(conn, _CREATE_GROUP_ITEM_SQL)
    finally:
        conn.close()


def get_stock_codes_by_scope(
    scope_type: str | None,
    group_id: int | None = None,
) -> list[str]:
    """
    根据 scope_type 获取股票代码列表。

    Args:
        scope_type: 股票来源类型
            "watchlist" - 从自选股读取
            "group" - 从自定义分组读取（需提供 group_id）
            "all" 或 None - 返回空列表，由调用方自行获取全量股票
        group_id: 当 scope_type="group" 时的分组ID

    Returns:
        list[str]: 股票代码列表（带交易所后缀，如 "600519.SH"）
    """
    _st = (scope_type or "").strip().lower()
    if _st == "watchlist":
        return _get_stock_codes_from_watchlist()
    if _st == "group":
        if group_id is not None and int(group_id) > 0:
            return _get_stock_codes_from_group(int(group_id))
        return []
    # "all" 或其他情况，由调用方自行获取全量
    return []


def _get_stock_codes_from_watchlist() -> list[str]:
    """从自选股获取股票代码列表"""
    codes: list[str] = []
    wl = get_watchlist()
    items = wl.get("items") if isinstance(wl, dict) else []
    for it in items if isinstance(items, list) else []:
        code = str((it or {}).get("stock_code") or "").strip().upper()
        if code:
            codes.append(code)
    return codes


def _get_stock_codes_from_group(group_id: int) -> list[str]:
    """从指定分组获取股票代码列表"""
    cfg = load_mysql_config()
    conn = connect(cfg)
    try:
        rows = query_dict(
            conn,
            "SELECT stock_code FROM trade_stock_group_item WHERE group_id = %s",
            (group_id,),
        )
        return [str(r["stock_code"]).strip().upper() for r in rows if r.get("stock_code")]
    finally:
        conn.close()
