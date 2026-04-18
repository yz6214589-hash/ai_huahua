from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pymysql

from zoe.app.config import Settings


def _connect(settings: Settings) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


@contextmanager
def db_conn(settings: Settings) -> Iterator[pymysql.connections.Connection]:
    conn = _connect(settings)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(settings: Settings, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with db_conn(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return list(rows or [])


def fetch_one(settings: Settings, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    with db_conn(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row

