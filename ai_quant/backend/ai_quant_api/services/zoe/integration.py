from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _ensure_zoe_import_path() -> None:
    p = str(_project_root())
    if p not in sys.path:
        sys.path.insert(0, p)


def _sync_db_env() -> None:
    os.environ.setdefault("DB_HOST", os.getenv("WUCAI_SQL_HOST", "127.0.0.1"))
    os.environ.setdefault("DB_PORT", os.getenv("WUCAI_SQL_PORT", "3306"))
    os.environ.setdefault("DB_USER", os.getenv("WUCAI_SQL_USERNAME", "root"))
    os.environ.setdefault("DB_PASSWORD", os.getenv("WUCAI_SQL_PASSWORD", ""))
    os.environ.setdefault("DB_NAME", os.getenv("WUCAI_SQL_DB", "huahua_trade"))


def get_status() -> dict[str, Any]:
    _ensure_zoe_import_path()
    try:
        from zoe.zoe.app.indicators import has_talib, talib_backend  # type: ignore
    except Exception:
        return {"source": "zoe", "status": "ready", "features": ["signals", "factors", "backtest"]}
    return {
        "source": "zoe",
        "status": "ready",
        "features": ["signals", "factors", "backtest"],
        "talib": has_talib(),
        "talib_backend": talib_backend(),
    }


def get_sample_codes(limit: int) -> dict[str, Any]:
    n = max(1, min(limit, 500))
    _ensure_zoe_import_path()
    _sync_db_env()
    try:
        from zoe.zoe.app.config import load_settings  # type: ignore
        from zoe.zoe.app.market_data import list_stock_codes  # type: ignore

        settings = load_settings()
        return {"codes": list_stock_codes(settings, n)}
    except Exception:
        return {"codes": []}


def get_signals(stock_code: str, start: str, end: str) -> dict[str, Any]:
    _ensure_zoe_import_path()
    _sync_db_env()
    try:
        import pandas as pd
        from zoe.zoe.app.config import load_settings  # type: ignore
        from zoe.zoe.app.indicators import add_technical_indicators  # type: ignore
        from zoe.zoe.app.market_data import load_daily_ohlcv  # type: ignore
        from zoe.zoe.app.signals import generate_signals  # type: ignore

        settings = load_settings()
        start_d = pd.to_datetime(start).date()
        end_d = pd.to_datetime(end).date()
        if not isinstance(start_d, date) or not isinstance(end_d, date):
            raise ValueError("invalid date")
        df = load_daily_ohlcv(settings, stock_code, start=start_d, end=end_d)
        if df.empty:
            return {"stock_code": stock_code, "signals": []}
        tech_df = add_technical_indicators(df)
        sigs = generate_signals(tech_df)
        return {
            "stock_code": stock_code,
            "signals": [
                {
                    "trade_date": s.trade_date,
                    "signal": s.signal,
                    "score": s.score,
                    "reasons": s.reasons,
                    "snapshot": s.snapshot,
                }
                for s in sigs
            ],
        }
    except Exception:
        return {"stock_code": stock_code, "signals": []}
