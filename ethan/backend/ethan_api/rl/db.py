from __future__ import annotations

import os
from typing import Any

import pymysql


def _db_config() -> dict[str, Any]:
    return {
        "host": str(os.getenv("WUCAI_SQL_HOST") or "localhost"),
        "user": str(os.getenv("WUCAI_SQL_USERNAME") or "root"),
        "password": str(os.getenv("WUCAI_SQL_PASSWORD") or ""),
        "database": str(os.getenv("WUCAI_SQL_DB") or "huahua_trade"),
        "port": int(os.getenv("WUCAI_SQL_PORT") or "3306"),
        "charset": "utf8mb4",
    }


def execute_query(sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    conn = pymysql.connect(**_db_config())
    cur = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return list(rows or [])
    finally:
        try:
            cur.close()
        finally:
            conn.close()

