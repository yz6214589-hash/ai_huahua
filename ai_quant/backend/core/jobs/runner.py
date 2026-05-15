from __future__ import annotations

from typing import Any

from core.db import load_mysql_config
from core.jobs.common import JobStats
from core.jobs.domains.calendar import run_calendar
from core.jobs.domains.catalyst import run_catalyst
from core.jobs.domains.macro_indicator import run_macro_indicator
from core.jobs.domains.rate_daily import run_rate_daily
from core.jobs.domains.report_consensus import run_report_consensus
from core.jobs.domains.sentiment_monitor import run_sentiment_monitor
from core.jobs.domains.stock_daily import run_stock_daily
from core.jobs.domains.stock_financial import run_stock_financial
from core.jobs.domains.stock_news import run_stock_news


def run_domain(domain: str, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    cfg = load_mysql_config()
    d = str(domain or "").strip()
    if d == "stock_daily":
        return run_stock_daily(cfg, mode, params)
    if d == "stock_financial":
        return run_stock_financial(cfg, mode, params)
    if d == "stock_news":
        return run_stock_news(cfg, mode, params)
    if d == "macro_indicator":
        return run_macro_indicator(cfg, mode, params)
    if d == "rate_daily":
        return run_rate_daily(cfg, mode, params)
    if d == "calendar":
        return run_calendar(cfg, mode, params)
    if d == "report_consensus":
        return run_report_consensus(cfg, mode, params)
    if d == "catalyst":
        return run_catalyst(cfg, mode, params)
    if d == "sentiment_monitor":
        return run_sentiment_monitor(cfg, mode, params)
    raise RuntimeError("unknown domain")

