from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ..db import MySQLConfig, connect, execute, query_dict
from ..models import DataSource
from .common import JobStats


INSERT_RECOMMEND_SQL = """
INSERT INTO trade_report_consensus
(stock_code, broker, report_date, rating, target_price, eps_forecast_current, eps_forecast_next, revenue_forecast, source_file)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
rating=VALUES(rating), target_price=VALUES(target_price)
"""


INSERT_FORECAST_SQL = """
INSERT INTO trade_report_consensus
(stock_code, broker, report_date, rating, target_price, eps_forecast_current, eps_forecast_next, revenue_forecast, source_file)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
eps_forecast_current=VALUES(eps_forecast_current),
eps_forecast_next=VALUES(eps_forecast_next),
revenue_forecast=VALUES(revenue_forecast)
"""


def _dedup_recommend(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df_sorted = df.sort_values("report_date", ascending=True).reset_index(drop=True)
    last: dict[str, dict[str, Any]] = {}
    keep = []
    for idx, row in df_sorted.iterrows():
        broker = str(row.get("broker", ""))
        rating = str(row.get("rating", ""))
        tp = row.get("target_price")
        tp_val = float(tp) if pd.notna(tp) else None
        prev = last.get(broker)
        if prev is None or prev.get("rating") != rating or prev.get("target_price") != tp_val:
            keep.append(idx)
            last[broker] = {"rating": rating, "target_price": tp_val}
    return df_sorted.loc[keep]


def run_report_consensus(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    import akshare as ak

    test_mode = (mode or "").lower() == "test"
    test_stock = (params or {}).get("test_stock") or "600519.SH"
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 200))

    conn = connect(cfg)
    try:
        codes_rows = query_dict(conn, "SELECT DISTINCT stock_code FROM trade_stock_daily")
        codes = [str(r["stock_code"]) for r in codes_rows]
        if test_mode:
            codes = [test_stock]
        else:
            codes = codes[:max_stocks]

        processed = 0
        written = 0
        failed: list[str] = []

        for code in codes:
            processed += 1
            code_num = code.split(".")[0]
            try:
                rec_df = ak.stock_institute_recommend_detail(symbol=code_num)
            except Exception:
                rec_df = None
            if rec_df is not None and len(rec_df) > 0:
                try:
                    rec_df.columns = ["stock_code_raw", "stock_name", "target_price", "rating", "broker", "analyst", "industry", "report_date"]
                    rec_df = rec_df.head(50)
                    rec_df["target_price"] = pd.to_numeric(rec_df["target_price"], errors="coerce")
                    rec_df["report_date"] = pd.to_datetime(rec_df["report_date"], errors="coerce")
                    rec_df["stock_code"] = code
                    rec_df = _dedup_recommend(rec_df)

                    existing_rows = query_dict(
                        conn,
                        "SELECT broker, rating, target_price FROM trade_report_consensus WHERE stock_code=%s AND source_file='eastmoney' ORDER BY report_date DESC",
                        (code,),
                    )
                    existing: dict[str, dict[str, Any]] = {}
                    for r in existing_rows:
                        b = str(r.get("broker"))
                        if b and b not in existing:
                            existing[b] = {"rating": r.get("rating"), "target_price": r.get("target_price")}

                    for _, row in rec_df.iterrows():
                        broker = str(row.get("broker", ""))[:50]
                        rating = str(row.get("rating", ""))[:20]
                        report_dt = row.get("report_date")
                        report_date = report_dt.strftime("%Y-%m-%d") if pd.notna(report_dt) else None
                        tp = row.get("target_price")
                        target_price = float(tp) if pd.notna(tp) else None

                        prev = existing.get(broker)
                        if prev:
                            prev_tp = float(prev["target_price"]) if prev.get("target_price") is not None else None
                            if prev.get("rating") == rating and prev_tp == target_price:
                                continue

                        execute(
                            conn,
                            INSERT_RECOMMEND_SQL,
                            (code, broker, report_date, rating, target_price, None, None, None, "eastmoney"),
                        )
                        written += 1
                        existing[broker] = {"rating": rating, "target_price": target_price}
                    conn.commit()
                except Exception:
                    failed.append(code)

            try:
                forecasts = {}
                for indicator in ["预测年报每股收益", "预测年报净利润"]:
                    try:
                        df = ak.stock_profit_forecast_ths(symbol=code_num, indicator=indicator)
                        if df is not None and len(df) > 0:
                            df.columns = ["year", "analyst_count", "min_val", "mean_val", "max_val", "industry_avg"]
                            forecasts[indicator] = df
                    except Exception:
                        pass
                eps_df = forecasts.get("预测年报每股收益")
                if eps_df is not None and len(eps_df) > 0:
                    profit_df = forecasts.get("预测年报净利润")
                    today = datetime.now().strftime("%Y-%m-%d")
                    eps_current = float(eps_df.iloc[0]["mean_val"]) if len(eps_df) > 0 else None
                    eps_next = float(eps_df.iloc[1]["mean_val"]) if len(eps_df) > 1 else None
                    profit_current = float(profit_df.iloc[0]["mean_val"]) if profit_df is not None and len(profit_df) > 0 else None
                    analyst_count = int(eps_df.iloc[0]["analyst_count"]) if len(eps_df) > 0 else 0
                    execute(
                        conn,
                        INSERT_FORECAST_SQL,
                        (code, f"一致预期({analyst_count}家)", today, None, None, eps_current, eps_next, profit_current, "ths"),
                    )
                    written += 1
                    conn.commit()
            except Exception:
                failed.append(code)

        return JobStats(
            items_processed=processed,
            rows_written=written,
            failed_items=failed,
            data_source_final=DataSource.akshare,
            fallback_chain=[DataSource.akshare],
            message=None if not failed else f"失败 {len(set(failed))} 只股票",
        )
    finally:
        conn.close()

