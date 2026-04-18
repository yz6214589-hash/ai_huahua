from __future__ import annotations

from datetime import date
import os
from typing import Any

import pandas as pd

from ..cleaning.ohlcv import clean_ohlcv_frame
from ..db import MySQLConfig, connect, executemany, query_dict
from ..models import DataSource
from .common import JobStats


INSERT_SQL = """
INSERT INTO trade_stock_daily
(stock_code, stock_name, trade_date, open_price, high_price, low_price, close_price, volume, amount, turnover_rate)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
stock_name=COALESCE(VALUES(stock_name), stock_name),
open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price),
volume=VALUES(volume), amount=VALUES(amount), turnover_rate=VALUES(turnover_rate)
"""


def _latest_dates(conn) -> dict[str, str]:
    rows = query_dict(conn, "SELECT stock_code, MAX(trade_date) AS max_date FROM trade_stock_daily GROUP BY stock_code")
    out: dict[str, str] = {}
    for r in rows:
        if r.get("max_date"):
            out[str(r["stock_code"])] = r["max_date"].strftime("%Y%m%d")
    return out


def _get_stock_list_qmt(test_mode: bool, test_stock: str) -> list[str]:
    from xtquant import xtdata

    if test_mode:
        return [test_stock]
    xtdata.connect()
    codes = xtdata.get_stock_list_in_sector("沪深A股")
    return [c for c in codes if "." in str(c)]


def _infer_exchange(code_num: str) -> str:
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


def _get_stock_list_fallback(test_mode: bool, test_stock: str) -> list[str]:
    if test_mode:
        return [test_stock]
    token = os.getenv("TUSHARE_TOKEN")
    if token and str(token).strip():
        import tushare as ts

        ts.set_token(str(token).strip())
        pro = ts.pro_api()
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code")
        if df is not None and len(df) > 0:
            return [str(x) for x in df["ts_code"].tolist() if "." in str(x)]

    import akshare as ak

    df = ak.stock_zh_a_spot_em()
    if df is None or len(df) == 0:
        return []
    codes = []
    for c in df["代码"].astype(str).tolist():
        ex = _infer_exchange(c)
        codes.append(f"{c}.{ex}")
    return codes


def _fetch_daily_qmt(stock_code: str, start_date: str) -> tuple[pd.DataFrame, str | None, float | None]:
    from xtquant import xtdata

    xtdata.download_history_data(stock_code, "1d", start_time=start_date)
    data = xtdata.get_market_data_ex(
        field_list=["open", "high", "low", "close", "volume", "amount"],
        stock_list=[stock_code],
        period="1d",
        start_time=start_date,
        dividend_type="front",
    )
    df = data.get(stock_code)
    if df is None or len(df) == 0:
        return pd.DataFrame(), None, None
    try:
        detail = xtdata.get_instrument_detail(stock_code) or {}
        name = detail.get("InstrumentName")
        float_shares = detail.get("NegotiableVolume") or detail.get("TotalVolume")
        float_shares = float(float_shares) if float_shares else None
    except Exception:
        name = None
        float_shares = None
    return df, (str(name) if name else None), float_shares


def _fetch_daily_tushare(stock_code: str, start_date: str) -> tuple[pd.DataFrame, str | None]:
    import tushare as ts

    token = os.getenv("TUSHARE_TOKEN")
    if not token or not str(token).strip():
        raise RuntimeError("missing TUSHARE_TOKEN")
    ts.set_token(str(token).strip())

    df = ts.pro_bar(ts_code=stock_code, start_date=start_date, end_date="", adj="qfq", freq="D")
    if df is None or len(df) == 0:
        return pd.DataFrame(), None
    df = df.rename(columns={"trade_date": "date", "vol": "volume"})
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    df["idx"] = df["date"].dt.strftime("%Y%m%d")
    keep = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    out = df.set_index("idx")[keep]
    return out, None


def _fetch_daily_akshare(stock_code: str, start_date: str) -> tuple[pd.DataFrame, str | None]:
    import akshare as ak

    code_num = stock_code.split(".")[0]
    df = ak.stock_zh_a_hist(symbol=code_num, period="daily", start_date=start_date, end_date="", adjust="qfq")
    if df is None or len(df) == 0:
        return pd.DataFrame(), None

    col_map = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    }
    df2 = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
    df2 = df2.dropna(subset=["date"]).sort_values("date")
    df2["idx"] = df2["date"].dt.strftime("%Y%m%d")
    keep = [c for c in ["open", "high", "low", "close", "volume", "amount"] if c in df2.columns]
    out = df2.set_index("idx")[keep]
    return out, None


def run_stock_daily(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    test_mode = (mode or "").lower() == "test"
    test_stock = (params or {}).get("test_stock") or "600519.SH"
    data_start = (params or {}).get("data_start") or "20230101"

    fallback_chain: list[DataSource] = []
    failed: list[str] = []
    total_rows = 0
    processed = 0

    try:
        stock_list = _get_stock_list_qmt(test_mode, test_stock)
        fallback_chain.append(DataSource.qmt)
        primary = DataSource.qmt
    except Exception:
        stock_list = _get_stock_list_fallback(test_mode, test_stock)
        primary = DataSource.tushare if os.getenv("TUSHARE_TOKEN") else DataSource.akshare
        fallback_chain.append(primary)

    source_final = primary

    conn = connect(cfg)
    try:
        latest_map = _latest_dates(conn)
        today = date.today().strftime("%Y%m%d")

        batch_rows: list[tuple[Any, ...]] = []
        for code in stock_list:
            processed += 1
            latest = latest_map.get(code)
            start = latest if latest and latest < today else (latest or data_start)
            try:
                if primary == DataSource.qmt:
                    df_raw, stock_name, float_shares = _fetch_daily_qmt(code, start)
                    df = clean_ohlcv_frame(df_raw)
                    source_final = DataSource.qmt
                    if df is None or len(df) == 0:
                        continue

                    for idx, row in df.iterrows():
                        idx_str = str(idx)
                        if len(idx_str) < 8:
                            continue
                        trade_date = f"{idx_str[:4]}-{idx_str[4:6]}-{idx_str[6:8]}"
                        vol_hands = int(float(row.get("volume", 0) or 0))
                        vol_shares = vol_hands * 100
                        turnover = None
                        if float_shares and float_shares > 0 and vol_shares > 0:
                            turnover = round(vol_shares / float_shares * 100, 4)
                        batch_rows.append(
                            (
                                code,
                                stock_name,
                                trade_date,
                                float(row["open"]),
                                float(row["high"]),
                                float(row["low"]),
                                float(row["close"]),
                                vol_shares,
                                float(row.get("amount") or 0.0),
                                turnover,
                            )
                        )
                else:
                    raise RuntimeError("skip qmt")
            except Exception:
                used = False
                tried: set[DataSource] = set()
                for src in [primary, DataSource.tushare, DataSource.akshare]:
                    if src == DataSource.qmt or src in tried:
                        continue
                    tried.add(src)
                    try:
                        if src == DataSource.tushare:
                            df_raw2, stock_name2 = _fetch_daily_tushare(code, start)
                        else:
                            df_raw2, stock_name2 = _fetch_daily_akshare(code, start)
                        df2 = clean_ohlcv_frame(df_raw2)
                        if df2 is None or len(df2) == 0:
                            continue
                        if src not in fallback_chain:
                            fallback_chain.append(src)
                        source_final = src
                        for idx, row in df2.iterrows():
                            idx_str = str(idx)
                            if len(idx_str) < 8:
                                continue
                            trade_date = f"{idx_str[:4]}-{idx_str[4:6]}-{idx_str[6:8]}"
                            vol_raw = row.get("volume", 0) or 0
                            vol_shares = int(float(vol_raw) * 100)
                            batch_rows.append(
                                (
                                    code,
                                    stock_name2,
                                    trade_date,
                                    float(row["open"]),
                                    float(row["high"]),
                                    float(row["low"]),
                                    float(row["close"]),
                                    vol_shares,
                                    float(row.get("amount") or 0.0),
                                    None,
                                )
                            )
                        used = True
                        break
                    except Exception:
                        continue
                if not used:
                    failed.append(code)

        total_rows = executemany(conn, INSERT_SQL, batch_rows)
        conn.commit()
        return JobStats(
            items_processed=processed,
            rows_written=total_rows,
            failed_items=failed,
            data_source_final=source_final,
            fallback_chain=fallback_chain,
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

