from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pymysql


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def connect(cfg: MySQLConfig) -> pymysql.Connection:
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=False,
    )


def query_dict(conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: pymysql.Connection, sql: str, params: tuple[Any, ...] | None = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(cur.rowcount)


def executemany(conn: pymysql.Connection, sql: str, rows: Iterable[tuple[Any, ...]]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows_list)
        return int(cur.rowcount)

