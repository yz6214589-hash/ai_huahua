from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _charles_api_path() -> Path:
    return _project_root() / "charles" / "api"


def _ensure_charles_import_path() -> None:
    p = str(_charles_api_path())
    if p not in sys.path:
        sys.path.insert(0, p)


def get_job_store_dir() -> str:
    env = os.getenv("AI_QUANT_CHARLES_JOB_STORE_DIR", "").strip()
    if env:
        return env
    return str(_project_root() / "charles" / ".charles" / "job_runs")


def list_job_runs(domain: str | None, limit: int) -> list[dict[str, Any]]:
    n = max(1, min(limit, 200))
    _ensure_charles_import_path()
    from charles_api.job_store import list_runs  # type: ignore
    from charles_api.models import JobDomain  # type: ignore

    d = JobDomain(domain) if domain else None
    return list_runs(get_job_store_dir(), d, n)


def get_summary() -> dict[str, dict[str, Any]]:
    _ensure_charles_import_path()
    from charles_api.config import load_settings  # type: ignore
    from charles_api.db import MySQLConfig, connect, query_dict  # type: ignore

    settings = load_settings()
    cfg = MySQLConfig(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_db,
    )
    try:
        conn = connect(cfg)
    except Exception:
        return _empty_summary()

    try:
        return _query_summary(conn, query_dict)
    except Exception:
        return _empty_summary()
    finally:
        conn.close()


def get_watchlist() -> dict[str, Any]:
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": [], "max": 50}
    try:
        rows = query_dict_func(
            conn,
            """
            SELECT w.stock_code, w.pinned, w.sort_order, m.stock_name
            FROM trade_watchlist w
            LEFT JOIN trade_stock_master m ON m.stock_code=w.stock_code
            ORDER BY w.pinned DESC, w.sort_order ASC, w.updated_at DESC
            """,
        )
        items = [
            {
                "stock_code": r.get("stock_code"),
                "stock_name": r.get("stock_name"),
                "pinned": bool(int(r.get("pinned") or 0) == 1),
                "sortOrder": int(r.get("sort_order") or 0),
            }
            for r in rows
        ]
        return {"items": items, "max": 50}
    except Exception:
        return {"items": [], "max": 50}
    finally:
        conn.close()


def search_stocks(q: str, limit: int) -> dict[str, Any]:
    text = q.strip()
    n = max(1, min(limit, 50))
    if not text:
        return {"items": []}
    conn, query_dict_func = _get_conn_and_query()
    if conn is None or query_dict_func is None:
        return {"items": []}
    try:
        like = f"%{text}%"
        rows = query_dict_func(
            conn,
            """
            SELECT stock_code AS code, stock_name AS name
            FROM trade_stock_master
            WHERE stock_code LIKE %s OR stock_name LIKE %s
            ORDER BY stock_code
            LIMIT %s
            """,
            (like, like, n),
        )
        return {"items": rows}
    except Exception:
        return {"items": []}
    finally:
        conn.close()


def _get_conn_and_query() -> tuple[Any, Any]:
    _ensure_charles_import_path()
    try:
        from charles_api.config import load_settings  # type: ignore
        from charles_api.db import MySQLConfig, connect, query_dict  # type: ignore
    except Exception:
        return None, None

    settings = load_settings()
    cfg = MySQLConfig(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_db,
    )
    try:
        conn = connect(cfg)
    except Exception:
        return None, None
    return conn, query_dict


def _query_summary(conn: Any, query_dict_func: Any) -> dict[str, dict[str, Any]]:
    def safe(sql: str) -> list[dict[str, Any]]:
        try:
            return query_dict_func(conn, sql)
        except Exception:
            return [{"d": None, "c": 0}]

    daily = safe("SELECT MAX(trade_date) AS d, COUNT(*) AS c FROM trade_stock_daily")
    fin = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_stock_financial")
    news = safe("SELECT MAX(published_at) AS d, COUNT(*) AS c FROM trade_stock_news")
    macro = safe("SELECT MAX(indicator_date) AS d, COUNT(*) AS c FROM trade_macro_indicator")
    rate = safe("SELECT MAX(rate_date) AS d, COUNT(*) AS c FROM trade_rate_daily")
    report = safe("SELECT MAX(report_date) AS d, COUNT(*) AS c FROM trade_report_consensus")
    cal = safe("SELECT MAX(event_date) AS d, COUNT(*) AS c FROM trade_calendar_event")

    def pack(rows: list[dict[str, Any]]) -> dict[str, Any]:
        row = (rows or [{}])[0]
        return {"latest": row.get("d"), "count": int(row.get("c") or 0)}

    return {
        "trade_stock_daily": pack(daily),
        "trade_stock_financial": pack(fin),
        "trade_stock_news": pack(news),
        "trade_macro_indicator": pack(macro),
        "trade_rate_daily": pack(rate),
        "trade_report_consensus": pack(report),
        "trade_calendar_event": pack(cal),
    }


def _empty_summary() -> dict[str, dict[str, Any]]:
    return {
        "trade_stock_daily": {"latest": None, "count": 0},
        "trade_stock_financial": {"latest": None, "count": 0},
        "trade_stock_news": {"latest": None, "count": 0},
        "trade_macro_indicator": {"latest": None, "count": 0},
        "trade_rate_daily": {"latest": None, "count": 0},
        "trade_report_consensus": {"latest": None, "count": 0},
        "trade_calendar_event": {"latest": None, "count": 0},
    }
