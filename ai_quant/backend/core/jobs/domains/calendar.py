from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date
from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, to_ymd


_INSERT_SQL = """
INSERT INTO trade_calendar_event
(event_date, event_time, country, category, title, importance, previous_value, forecast_value, actual_value, impact, ai_prompt, source, source_url, status)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
event_time=COALESCE(VALUES(event_time), event_time),
country=COALESCE(VALUES(country), country),
category=COALESCE(VALUES(category), category),
importance=COALESCE(VALUES(importance), importance),
previous_value=COALESCE(VALUES(previous_value), previous_value),
forecast_value=COALESCE(VALUES(forecast_value), forecast_value),
actual_value=COALESCE(VALUES(actual_value), actual_value),
impact=COALESCE(VALUES(impact), impact),
ai_prompt=COALESCE(VALUES(ai_prompt), ai_prompt),
source=COALESCE(VALUES(source), source),
source_url=COALESCE(VALUES(source_url), source_url),
status=COALESCE(VALUES(status), status)
"""


def _country_code(v: str) -> str:
    s = (v or "").strip().upper()
    if not s:
        return "CN"
    if s in ("CN", "US", "EU", "JP"):
        return s
    if "中国" in s or "CHINA" in s:
        return "CN"
    if "美国" in s or "UNITED" in s or "USA" in s:
        return "US"
    if "欧" in s or "EURO" in s:
        return "EU"
    if "日" in s or "JAPAN" in s:
        return "JP"
    return "CN"


def _infer_category(title: str) -> str:
    t = (title or "").upper()
    if "CPI" in t or "PPI" in t or "通胀" in t or "物价" in t:
        return "inflation"
    if "PMI" in t:
        return "pmi"
    if "GDP" in t:
        return "gdp"
    if "就业" in title or "失业" in title:
        return "employment"
    if "进出口" in title or "贸易" in title:
        return "trade"
    if "LPR" in t or "利率" in title or "央行" in title or "加息" in title or "降息" in title:
        return "rate"
    if "政策" in title or "监管" in title:
        return "policy"
    return "other"


def _parse_importance(v: str) -> int:
    s = (v or "").strip()
    if not s:
        return 2
    if "高" in s or "3" in s:
        return 3
    if "低" in s or "1" in s:
        return 1
    if "中" in s or "2" in s:
        return 2
    try:
        x = int(float(s))
    except Exception:
        return 2
    return 1 if x <= 1 else 3 if x >= 3 else 2


def _status_by_date(d: str) -> str:
    try:
        y, m, dd = [int(x) for x in d.split("-", 2)]
        dt = _date(y, m, dd)
        return "upcoming" if dt > _date.today() else "released"
    except Exception:
        return "upcoming"


def _hhmm(v: str) -> str | None:
    s = (v or "").strip()
    if not s:
        return None
    if len(s) >= 5 and s[2] == ":":
        return s[:5]
    return s[:5] if len(s) >= 5 else None


def run_calendar(cfg: MySQLConfig, _mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    max_workers = max(1, int((params or {}).get("max_workers") or 4))

    today = pd.Timestamp.now().normalize()
    dates = pd.date_range(today - pd.Timedelta(days=7), today + pd.Timedelta(days=30))

    def _process_one(d):
        date_str = d.strftime("%Y%m%d")
        try:
            part = ak.news_economic_baidu(date=date_str)
            if part is not None and len(part) > 0:
                return part
        except Exception:
            pass
        return None

    frames = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_date = {executor.submit(_process_one, d): d for d in dates}
        for future in as_completed(future_to_date):
            try:
                part = future.result()
                if part is not None:
                    frames.append(part)
            except Exception:
                continue

    if not frames:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    df = pd.concat(frames, ignore_index=True)

    col_map: dict[str, str] = {}
    for col in df.columns:
        s = str(col)
        if "日期" in s:
            col_map["date"] = col
        elif "时间" in s:
            col_map["time"] = col
        elif "国家" in s or "地区" in s:
            col_map["country"] = col
        elif "事件" in s:
            col_map["event"] = col
        elif "实际" in s:
            col_map["actual"] = col
        elif "预期" in s:
            col_map["forecast"] = col
        elif "前值" in s:
            col_map["previous"] = col
        elif "重要" in s:
            col_map["importance"] = col

    if "date" not in col_map or "event" not in col_map:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="列名无法识别",
        )

    rows: list[tuple[Any, ...]] = []
    for _, r in df.iterrows():
        ed = r.get(col_map["date"])
        event_date = to_ymd(ed)
        if not event_date:
            continue
        title = str(r.get(col_map["event"]) or "").strip()
        if not title:
            continue
        country_raw = str(r.get(col_map.get("country")) or "").strip()
        importance_raw = str(r.get(col_map.get("importance")) or "").strip()
        time_raw = str(r.get(col_map.get("time")) or "").strip()
        actual = str(r.get(col_map.get("actual")) or "").strip() or None
        forecast = str(r.get(col_map.get("forecast")) or "").strip() or None
        previous = str(r.get(col_map.get("previous")) or "").strip() or None

        country = _country_code(country_raw)
        importance = _parse_importance(importance_raw)
        category = _infer_category(title)
        status = _status_by_date(event_date)
        event_time = _hhmm(time_raw)

        rows.append(
            (
                event_date,
                event_time,
                country,
                category,
                title[:200],
                importance,
                previous,
                forecast,
                actual,
                None,
                None,
                "akshare",
                None,
                status,
            )
        )

    conn = connect(cfg)
    try:
        written = executemany(conn, _INSERT_SQL, rows)
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None,
        )
    finally:
        conn.close()

