"""
行情日线采集任务（stock_daily）
数据源兜底链路：QMT（xtquant） → AkShare → Tushare
写入表：trade_stock_daily
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd

from core.db import MySQLConfig, connect, executemany, query_dict
from core.jobs.common import JobStats, normalize_stock_code, safe_float


_INSERT_SQL = """
INSERT INTO trade_stock_daily
(stock_code, trade_date, close_price, volume, rsi14, ma20, stock_name)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
close_price=VALUES(close_price),
volume=VALUES(volume),
rsi14=VALUES(rsi14),
ma20=VALUES(ma20),
stock_name=COALESCE(VALUES(stock_name), stock_name)
"""


def _latest_dates(conn) -> dict[str, str]:
    rows = query_dict(conn, "SELECT stock_code, MAX(trade_date) AS max_date FROM trade_stock_daily GROUP BY stock_code")
    out: dict[str, str] = {}
    for r in rows:
        md = r.get("max_date")
        if md:
            out[str(r["stock_code"])] = md.strftime("%Y%m%d")
    return out


def _infer_exchange(code_num: str) -> str:
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


def _get_stock_list(test_mode: bool, test_stock: str, max_stocks: int) -> tuple[list[str], dict[str, str]]:
    if test_mode:
        s = normalize_stock_code(test_stock)
        return ([s] if s else []), {}

    try:
        import akshare as ak

        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return [], {}
    except Exception:
        return [], {}

    codes: list[str] = []
    name_map: dict[str, str] = {}
    for _, r in df.iterrows():
        code_num = str(r.get("代码") or "").strip()
        name = str(r.get("名称") or "").strip()
        if not code_num:
            continue
        code = f"{code_num}.{_infer_exchange(code_num)}"
        codes.append(code)
        if name:
            name_map[code] = name
        if 0 < max_stocks <= len(codes):
            break
    return codes, name_map


def _fetch_qmt(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    try:
        from infra.qmt_gateway_client import historical_kline

        raw = historical_kline(
            stock_code=code,
            period="1d",
            start_time=start,
            end_time=end,
            dividend_type="front",
            fill_data=True,
        )
        rows = raw.get("rows") or []
        if not rows:
            return None
        df = pd.DataFrame(rows)
        if "date" not in df.columns or "close" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = None
        return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _fetch_akshare(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    try:
        import akshare as ak

        code_num = code.split(".")[0]
        df = ak.stock_zh_a_hist(symbol=code_num, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df is None or len(df) == 0:
            return None
        col_map = {"日期": "date", "收盘": "close", "成交量": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "date" not in df.columns or "close" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = None
        return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _fetch_tushare(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    token = str(os.getenv("TUSHARE_TOKEN") or "").strip()
    if not token:
        return None
    try:
        import tushare as ts

        ts.set_token(token)
        pro = ts.pro_api()
        df = pro.daily(ts_code=code, start_date=start, end_date=end)
        if df is None or len(df) == 0:
            return None
        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _rsi14(close: list[float]) -> list[float | None]:
    n = len(close)
    out: list[float | None] = [None] * n
    if n < 15:
        return out
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        d = close[i] - close[i - 1]
        gains[i] = d if d > 0 else 0.0
        losses[i] = -d if d < 0 else 0.0
    avg_gain = sum(gains[1:15]) / 14.0
    avg_loss = sum(losses[1:15]) / 14.0
    for i in range(14, n):
        if i > 14:
            avg_gain = (avg_gain * 13.0 + gains[i]) / 14.0
            avg_loss = (avg_loss * 13.0 + losses[i]) / 14.0
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _ma20(close: list[float]) -> list[float | None]:
    n = len(close)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    window: list[float] = []
    s = 0.0
    for i, v in enumerate(close):
        window.append(v)
        s += v
        if len(window) > 20:
            s -= window.pop(0)
        if i >= 19:
            out[i] = s / float(len(window))
    return out


def run_stock_daily(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None) -> JobStats:
    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH")
    data_start = str((params or {}).get("data_start") or "20230101").strip() or "20230101"
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 200))

    processed = 0
    total_rows = 0
    failed: list[str] = []
    fallback_chain: list[str] = []
    data_source_final = "unknown"

    conn = connect(cfg)
    try:
        latest_map = _latest_dates(conn)
        today_str = date.today().strftime("%Y%m%d")

        stock_list, name_map = _get_stock_list(test_mode, test_stock, max_stocks)

        batch_rows: list[tuple[Any, ...]] = []
        for code in stock_list:
            processed += 1
            latest = latest_map.get(code)
            start = latest if latest and latest < today_str else (latest or data_start)

            df: pd.DataFrame | None = None
            used_source = "unknown"

            try:
                df = _fetch_qmt(code, start, today_str)
                if df is not None and len(df) > 0:
                    used_source = "qmt"
                    fallback_chain.append("qmt")
            except Exception:
                fallback_chain.append("qmt")

            if df is None or len(df) == 0:
                try:
                    df = _fetch_akshare(code, start, today_str)
                    if df is not None and len(df) > 0:
                        used_source = "akshare"
                        fallback_chain.append("akshare")
                except Exception:
                    fallback_chain.append("akshare")

            if df is None or len(df) == 0:
                try:
                    df = _fetch_tushare(code, start, today_str)
                    if df is not None and len(df) > 0:
                        used_source = "tushare"
                        fallback_chain.append("tushare")
                except Exception:
                    fallback_chain.append("tushare")

            if df is None or len(df) == 0:
                failed.append(code)
                continue

            if used_source != "unknown":
                data_source_final = used_source

            df = df.dropna(subset=["close"])
            if len(df) == 0:
                failed.append(code)
                continue

            close_vals = [float(x) for x in df["close"].tolist() if x is not None and float(x) == float(x)]
            rsi_seq = _rsi14(close_vals)
            ma_seq = _ma20(close_vals)

            stock_name = name_map.get(code)
            rsi_map = {str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])[:10]: rsi_seq[i] for i, (_, row) in enumerate(df.iterrows()) if i < len(rsi_seq)}
            ma_map = {str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])[:10]: ma_seq[i] for i, (_, row) in enumerate(df.iterrows()) if i < len(ma_seq)}

            for _, row in df.iterrows():
                dt = row["date"]
                dstr = dt.date().isoformat() if hasattr(dt, "date") else str(dt)[:10]
                close = safe_float(row.get("close"))
                vol = row.get("volume")
                volume = int(float(vol)) if vol not in (None, "") and float(vol) == float(vol) else None
                rsi = rsi_map.get(dstr)
                ma20 = ma_map.get(dstr)
                batch_rows.append((code, dstr, close, volume, rsi, ma20, stock_name))

        total_rows = executemany(conn, _INSERT_SQL, batch_rows)
        return JobStats(
            items_processed=processed,
            rows_written=total_rows,
            failed_items=failed,
            data_source_final=data_source_final,
            fallback_chain=list(dict.fromkeys(fallback_chain)),
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()

