from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

DataSource = Literal["qmt", "tushare", "akshare", "qwen_search", "file", "unknown"]


@dataclass(frozen=True)
class JobStats:
    items_processed: int
    rows_written: int
    failed_items: list[str]
    data_source_final: DataSource
    fallback_chain: list[DataSource]
    message: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_stock_code(v: str) -> str:
    s = (v or "").strip().upper()
    if not s:
        return ""
    if "." in s:
        return s
    if len(s) == 6 and s.isdigit():
        ex = "SH" if s.startswith("6") else "SZ"
        return f"{s}.{ex}"
    return s


def to_ymd(d: Any) -> str | None:
    if d is None:
        return None
    if isinstance(d, date) and not isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, datetime):
        return d.date().isoformat()
    s = str(d).strip()
    if not s:
        return None
    return s[:10]


def safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def safe_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except Exception:
        return None
    if x != x:
        return None
    return x

