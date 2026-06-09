from __future__ import annotations

from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, safe_float, to_ymd

# 允许在 _upsert_rate_indicator 中动态拼接SQL的列名白名单，防止SQL注入
_ALLOWED_RATE_COLUMNS = {"fear_greed", "vix", "ovx", "gvz"}


_INSERT_SQL = """
INSERT INTO trade_rate_daily
(rate_date, cn_bond_10y, us_bond_10y, fear_greed, vix, ovx, gvz, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
cn_bond_10y=COALESCE(VALUES(cn_bond_10y), cn_bond_10y),
us_bond_10y=COALESCE(VALUES(us_bond_10y), us_bond_10y),
fear_greed=COALESCE(VALUES(fear_greed), fear_greed),
vix=COALESCE(VALUES(vix), vix),
ovx=COALESCE(VALUES(ovx), ovx),
gvz=COALESCE(VALUES(gvz), gvz),
data_source=VALUES(data_source)
"""

_QVIX_INSERT_SQL = """
INSERT INTO trade_qvix_daily
(trade_date, qvix_50etf, qvix_300index, data_source)
VALUES (%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
qvix_50etf=COALESCE(VALUES(qvix_50etf), qvix_50etf),
qvix_300index=COALESCE(VALUES(qvix_300index), qvix_300index),
data_source=VALUES(data_source)
"""


def _fetch_fear_greed() -> tuple[str | None, float | None]:
    """从 alternative.me 获取恐惧贪婪指数"""
    import requests
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code == 200:
            data = r.json()
            val = int(data["data"][0]["value"])
            ts = int(data["data"][0]["timestamp"])
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            return dt, float(val)
    except Exception:
        pass
    return None, None


def _fetch_yahoo(symbol: str) -> tuple[str | None, float | None]:
    """从 Yahoo Finance 获取指数最新收盘价"""
    import requests
    import time
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(3):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 429:
                time.sleep(3)
                continue
            if r.status_code != 200:
                time.sleep(1)
                continue
            data = r.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            # 找到最后一个非空收盘价
            for i in range(len(closes) - 1, -1, -1):
                if closes[i] is not None:
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(timestamps[i], tz=timezone.utc).strftime("%Y-%m-%d")
                    return dt, float(closes[i])
        except Exception:
            time.sleep(2)
    return None, None


def _fetch_qvix() -> tuple[str | None, float | None]:
    """从 akshare 获取50ETF期权隐含波动率指数"""
    import akshare as ak
    try:
        df = ak.index_option_50etf_qvix()
        if df is not None and len(df) > 0:
            last = df.iloc[-1]
            return str(last["date"]), float(last["close"])
    except Exception:
        pass
    return None, None


def run_rate_daily(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    df = ak.bond_zh_us_rate()
    if df is None or len(df) == 0:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    date_col = df.columns[0]
    cn_col = None
    us_col = None
    for c in df.columns:
        s = str(c)
        if "中国" in s and "10" in s:
            cn_col = c
        if "美国" in s and "10" in s:
            us_col = c
    cn_col = cn_col or df.columns[min(1, len(df.columns) - 1)]
    us_col = us_col or (df.columns[min(2, len(df.columns) - 1)] if len(df.columns) > 2 else cn_col)

    df2 = pd.DataFrame(
        {
            "d": pd.to_datetime(df[date_col], errors="coerce").dt.date,
            "cn": pd.to_numeric(df[cn_col], errors="coerce"),
            "us": pd.to_numeric(df[us_col], errors="coerce"),
        }
    ).dropna(subset=["d"])

    # 获取额外市场指标
    fg_date, fg_val = _fetch_fear_greed()
    vix_date, vix_val = _fetch_yahoo("^VIX")
    ovx_date, ovx_val = _fetch_yahoo("^OVX")
    gvz_date, gvz_val = _fetch_yahoo("^GVZ")
    qvix_date, qvix_val = _fetch_qvix()

    # 构建主表数据行
    rows: list[tuple[Any, ...]] = []
    for _, r in df2.iterrows():
        d = to_ymd(r.get("d"))
        if not d:
            continue
        # 只将债券收益率数据和当天匹配的额外指标合并
        rows.append((
            d,
            safe_float(r.get("cn")),
            safe_float(r.get("us")),
            safe_float(fg_val) if fg_date == d else None,
            safe_float(vix_val) if vix_date == d else None,
            safe_float(ovx_val) if ovx_date == d else None,
            safe_float(gvz_val) if gvz_date == d else None,
            "akshare",
        ))

    # 如果有恐惧贪婪数据但不在债券收益率数据行中，单独插入
    if fg_date and fg_val is not None and fg_date not in {to_ymd(r.get("d")) if hasattr(r, "get") else None for r in df2.itertuples()}:
        pass  # 由后续的单行插入处理
    # 处理非对齐日期的额外指标 - 直接单独更新
    conn = connect(cfg)
    try:
        # 写入债券收益率数据
        written = executemany(conn, _INSERT_SQL, rows)

        # 单独插入恐惧贪婪（如果日期不在债券数据中）
        if fg_date and fg_val is not None:
            _upsert_rate_indicator(conn, fg_date, "fear_greed", fg_val)

        # 单独插入 VIX
        if vix_date and vix_val is not None:
            _upsert_rate_indicator(conn, vix_date, "vix", vix_val)

        # 单独插入 OVX
        if ovx_date and ovx_val is not None:
            _upsert_rate_indicator(conn, ovx_date, "ovx", ovx_val)

        # 单独插入 GVZ
        if gvz_date and gvz_val is not None:
            _upsert_rate_indicator(conn, gvz_date, "gvz", gvz_val)

        # 写入 QVIX 数据
        qvix_written = 0
        if qvix_date and qvix_val is not None:
            qvix_rows = [(qvix_date, qvix_val, None, "akshare")]
            qvix_written = executemany(conn, _QVIX_INSERT_SQL, qvix_rows)

        return JobStats(
            items_processed=len(rows) + (1 if fg_val else 0) + (1 if vix_val else 0) + (1 if ovx_val else 0) + (1 if gvz_val else 0) + (1 if qvix_val else 0),
            rows_written=written + qvix_written,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None,
        )
    finally:
        conn.close()


def _upsert_rate_indicator(conn, date_str: str, col: str, val: float) -> None:
    """单独更新某个指标的某天数据（upsert语义）"""
    if col not in _ALLOWED_RATE_COLUMNS:
        raise ValueError(f"不允许的列名: {col}，合法值: {_ALLOWED_RATE_COLUMNS}")
    import pymysql
    cur = conn.cursor()
    try:
        # 先检查日期是否存在
        cur.execute("SELECT 1 FROM trade_rate_daily WHERE rate_date=%s", (date_str,))
        if cur.fetchone():
            cur.execute(f"UPDATE trade_rate_daily SET {col}=%s, data_source='akshare' WHERE rate_date=%s", (val, date_str))
        else:
            placeholders = ["rate_date"] + [col] + ["data_source"]
            values = [date_str, val, "akshare"]
            cols_str = ", ".join(placeholders)
            vals_ph = ", ".join(["%s"] * len(values))
            cur.execute(f"INSERT INTO trade_rate_daily ({cols_str}) VALUES ({vals_ph})", values)
        conn.commit()
    finally:
        cur.close()

