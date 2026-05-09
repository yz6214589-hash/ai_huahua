from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from ai_quant_api.db import connect, load_mysql_config, query_dict
from ai_quant_api.services.zoe.tech_signals import generate_signals


def _sync_db_env() -> None:
    os.environ.setdefault("DB_HOST", os.getenv("WUCAI_SQL_HOST", "127.0.0.1"))
    os.environ.setdefault("DB_PORT", os.getenv("WUCAI_SQL_PORT", "3306"))
    os.environ.setdefault("DB_USER", os.getenv("WUCAI_SQL_USERNAME", "root"))
    os.environ.setdefault("DB_PASSWORD", os.getenv("WUCAI_SQL_PASSWORD", ""))
    os.environ.setdefault("DB_NAME", os.getenv("WUCAI_SQL_DB", "huahua_trade"))


def get_status() -> dict[str, Any]:
    return {
        "source": "zoe",
        "status": "ready",
        "features": ["signals", "factors", "backtest"],
        "talib": False,
        "talib_backend": None,
        "mode": "embedded",
    }


def get_sample_codes(limit: int) -> dict[str, Any]:
    n = max(1, min(limit, 500))
    _sync_db_env()
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return {"codes": []}
    try:
        rows = query_dict(
            conn,
            "SELECT stock_code FROM trade_stock_master ORDER BY stock_code LIMIT %s",
            (n,),
        )
        return {"codes": [str(r.get("stock_code") or "") for r in rows if str(r.get("stock_code") or "").strip()]}
    except Exception:
        return {"codes": []}
    finally:
        conn.close()


def get_signals(stock_code: str, start: str, end: str) -> dict[str, Any]:
    _sync_db_env()
    try:
        start_d = datetime.strptime(str(start).strip(), "%Y-%m-%d").date()
        end_d = datetime.strptime(str(end).strip(), "%Y-%m-%d").date()
        if not isinstance(start_d, date) or not isinstance(end_d, date):
            raise ValueError("invalid date")
    except Exception:
        return {"stock_code": stock_code, "signals": []}

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return {"stock_code": stock_code, "signals": []}
    try:
        rows = query_dict(
            conn,
            """
            SELECT trade_date, close_price
            FROM trade_stock_daily
            WHERE stock_code=%s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (stock_code, start_d, end_d),
        )
        trade_dates: list[str] = []
        closes: list[float] = []
        for r in rows:
            td = r.get("trade_date")
            try:
                close_v = float(r.get("close_price"))
            except Exception:
                continue
            if close_v != close_v:
                continue
            trade_dates.append(td.isoformat() if hasattr(td, "isoformat") else str(td or ""))
            closes.append(close_v)
        if len(closes) < 2:
            return {"stock_code": stock_code, "signals": []}
        sigs = generate_signals(trade_dates=trade_dates, closes=closes)
        return {"stock_code": stock_code, "signals": sigs}
    except Exception:
        return {"stock_code": stock_code, "signals": []}
    finally:
        conn.close()
