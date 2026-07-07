"""
Repository 基类 - 封装MySQL数据访问操作

提供统一的数据库连接管理和基础CRUD操作封装，
所有具体的Repository类继承此基类以获得数据访问能力。
"""
from __future__ import annotations

from core.db import connect, load_mysql_config, query_dict, execute, executemany


class BaseRepository:
    """所有Repository的基类，封装连接池获取和生命周期管理"""

    def _connect(self):
        """获取数据库连接"""
        return connect(load_mysql_config())

    def _execute(self, sql: str, params: tuple = None) -> int:
        """执行INSERT/UPDATE/DELETE，返回影响行数"""
        conn = self._connect()
        try:
            return execute(conn, sql, params)
        finally:
            conn.close()

    def _query(self, sql: str, params: tuple = None) -> list[dict]:
        """执行SELECT，返回字典列表"""
        conn = self._connect()
        try:
            return query_dict(conn, sql, params)
        finally:
            conn.close()

    def _query_one(self, sql: str, params: tuple = None) -> dict | None:
        """执行SELECT，返回单行或None"""
        rows = self._query(sql, params)
        return rows[0] if rows else None

    def _executemany(self, sql: str, rows: list[tuple]) -> int:
        """批量执行多条SQL语句"""
        conn = self._connect()
        try:
            return executemany(conn, sql, rows)
        finally:
            conn.close()
