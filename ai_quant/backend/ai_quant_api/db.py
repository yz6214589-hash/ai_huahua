from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        return int(str(raw).strip() or default)
    except Exception:
        return default


def load_mysql_config() -> MySQLConfig:
    try:
        from dotenv import find_dotenv, load_dotenv

        env_path = find_dotenv(usecwd=True)
        if env_path:
            load_dotenv(env_path, override=False)
        else:
            load_dotenv()
    except Exception:
        pass

    host = os.getenv("WUCAI_SQL_HOST") or os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "127.0.0.1"
    port = _env_int("WUCAI_SQL_PORT", _env_int("DB_PORT", _env_int("MYSQL_PORT", 3306)))
    user = os.getenv("WUCAI_SQL_USERNAME") or os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root"
    password = os.getenv("WUCAI_SQL_PASSWORD") or os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or ""
    database = os.getenv("WUCAI_SQL_DB") or os.getenv("DB_NAME") or os.getenv("MYSQL_DB") or "huahua_trade"

    return MySQLConfig(
        host=str(host).strip() or "127.0.0.1",
        port=int(port),
        user=str(user).strip() or "root",
        password=str(password),
        database=str(database).strip() or "huahua_trade",
    )


def connect(cfg: MySQLConfig):
    import pymysql

    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=2,
        read_timeout=3,
        write_timeout=3,
        cursorclass=pymysql.cursors.DictCursor,
    )


def query_dict(conn, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return list(rows or [])


def execute(conn, sql: str, params: tuple[Any, ...] | None = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(getattr(cur, "rowcount", 0) or 0)


def executemany(conn, sql: str, rows: Iterable[tuple[Any, ...]]) -> int:
    rows_list = list(rows)
    if not rows_list:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows_list)
        return int(getattr(cur, "rowcount", 0) or 0)
