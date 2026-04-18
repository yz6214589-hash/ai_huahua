from __future__ import annotations

import math
from typing import Any

import pandas as pd

from ..db import MySQLConfig, connect, executemany
from ..models import DataSource
from .common import JobStats


COUNTRIES = {"中国", "美国", "欧元区", "日本", "英国"}
EVENT_TYPE_MAP = {
    "interest_rate": ["利率", "FOMC", "加息", "降息", "LPR", "基准利率", "联邦基金"],
    "inflation": ["CPI", "PPI", "通胀", "物价"],
    "employment": ["就业", "非农", "失业率", "ADP"],
    "pmi": ["PMI", "采购经理"],
    "gdp": ["GDP", "国内生产总值"],
    "trade": ["贸易", "进出口", "出口", "进口"],
    "monetary": ["M2", "货币供应", "社融", "信贷"],
    "housing": ["房价", "房屋"],
    "retail": ["零售", "消费"],
    "industry": ["工业", "产出", "产值"],
}


INSERT_SQL = """
INSERT INTO trade_calendar_event
(event_date, event_time, title, country, category, importance, forecast_value, actual_value, previous_value, source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
actual_value = COALESCE(VALUES(actual_value), actual_value),
forecast_value = COALESCE(VALUES(forecast_value), forecast_value),
previous_value = COALESCE(VALUES(previous_value), previous_value),
importance = VALUES(importance),
category = VALUES(category),
country = VALUES(country)
"""


def _classify_event(name: str) -> str:
    for etype, kws in EVENT_TYPE_MAP.items():
        for kw in kws:
            if kw in name:
                return etype
    return "other"


def _to_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    return s if s else None


def run_calendar(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak

    fallback_chain = [DataSource.akshare]
    today = pd.Timestamp.now().normalize()
    dates = pd.date_range(today - pd.Timedelta(days=7), today + pd.Timedelta(days=30))
    frames = []
    for d in dates:
        date_str = d.strftime("%Y%m%d")
        try:
            part = ak.news_economic_baidu(date=date_str)
            if part is not None and len(part) > 0:
                frames.append(part)
        except Exception:
            pass

    if not frames:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final=DataSource.akshare,
            fallback_chain=fallback_chain,
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
            data_source_final=DataSource.akshare,
            fallback_chain=fallback_chain,
            message=f"列名无法识别: {list(df.columns)}",
        )

    if "country" in col_map:
        df = df[df[col_map["country"]].isin(COUNTRIES)]

    conn = connect(cfg)
    try:
        rows = []
        for _, r in df.iterrows():
            event_date = r[col_map["date"]]
            if pd.isna(event_date):
                continue
            if hasattr(event_date, "strftime"):
                event_date_str = event_date.strftime("%Y-%m-%d")
            else:
                event_date_str = str(event_date)[:10]
            title = str(r[col_map["event"]]).strip()
            if not title:
                continue
            event_time = str(r.get(col_map.get("time", ""), "")).strip() or None
            country = str(r.get(col_map.get("country", ""), "")).strip() or ""
            importance = int(r.get(col_map.get("importance", ""), 1) or 1)
            category = _classify_event(title)
            actual = _to_str(r.get(col_map.get("actual", ""), None))
            forecast = _to_str(r.get(col_map.get("forecast", ""), None))
            previous = _to_str(r.get(col_map.get("previous", ""), None))
            rows.append((event_date_str, event_time, title, country, category, importance, forecast, actual, previous, "akshare"))

        written = executemany(conn, INSERT_SQL, rows)
        conn.commit()
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final=DataSource.akshare,
            fallback_chain=fallback_chain,
            message=None,
        )
    finally:
        conn.close()

